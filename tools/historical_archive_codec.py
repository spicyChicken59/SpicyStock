"""Bounded, single-stream codecs for historical evidence's outer USTAR archive.

The format is deliberately narrower than general gzip/Zstandard: no dictionary,
concatenated/skippable frames or trailing bytes. Archive contents are validated
separately by historical_package; this module never extracts files.
"""
from __future__ import annotations

import os
import zlib

FORMAT = "ustar-zstandard-v1"
LEGACY_FORMAT = "ustar-gzip-v1"
ZSTANDARD_VERSION = "0.25.0"
LIBZSTD_VERSION = (1, 5, 7)
WINDOW_BYTES = 1024 ** 3
CHUNK_BYTES = 1024 ** 2
BLOCK_BYTES = 128 * 1024
COMPRESSION_PARAMETERS = {"window_log": 30, "enable_ldm": True,
                          "write_checksum": True, "write_content_size": True,
                          "threads": 0}


class CodecError(RuntimeError):
    """Constant codes only; callers must not expose decoder exception text."""


def _fail(reason):
    raise CodecError(reason)


def _zstandard():
    try:
        import zstandard
    except ImportError:
        _fail("archive_codec_unavailable")
    if (zstandard.__version__ != ZSTANDARD_VERSION or
            zstandard.ZSTD_VERSION != LIBZSTD_VERSION or zstandard.backend != "cext"):
        _fail("archive_codec_version_mismatch")
    return zstandard


def compressor(output, size):
    """Pledged-size, checksummed, one-frame encoder; its version is pinned."""
    zstd = _zstandard()
    parameters = zstd.ZstdCompressionParameters.from_level(19, **COMPRESSION_PARAMETERS)
    return zstd.ZstdCompressor(compression_params=parameters).stream_writer(
        output, size=size, closefd=False)


def _zstandard_frame(archive, max_decoded):
    """Check framing before decoding; bounded reads never allocate frame payloads.

    python-zstandard's streaming reader bounds output allocations but permits
    multiple frames. This independent frame walk rejects extra input, truncation,
    unknown content sizes and excessive decoder windows before creating a reader.
    It follows the v1.5.7 frame/block layout; libzstd verifies compressed contents
    and checksum during the subsequent bounded decode.
    """
    zstd = _zstandard()
    length = archive.stat().st_size
    with archive.open("rb") as source:
        prefix = source.read(18)
        if len(prefix) < 6 or prefix[:4] != b"\x28\xb5\x2f\xfd" or prefix[4] & 0x18:
            _fail("invalid_archive_frame")
        try:
            header_size = zstd.frame_header_size(prefix)
            params = zstd.get_frame_parameters(prefix)
        except zstd.ZstdError:
            _fail("invalid_archive_frame")
        if (params.content_size in (zstd.CONTENTSIZE_UNKNOWN, zstd.CONTENTSIZE_ERROR) or
                params.content_size > max_decoded or params.window_size > WINDOW_BYTES or
                params.dict_id != 0 or not params.has_checksum):
            _fail("archive_frame_resource_limit")
        offset, blocks = header_size, 0
        # Our writer uses ordinary 128 KiB blocks without intermediate flushes.
        # A small final block is allowed; arbitrary empty-block CPU bombs are not.
        max_blocks = (max_decoded + BLOCK_BYTES - 1) // BLOCK_BYTES + 1
        while True:
            source.seek(offset)
            raw = source.read(3)
            if len(raw) != 3:
                _fail("truncated_archive_frame")
            header = int.from_bytes(raw, "little")
            last, kind, size = header & 1, (header >> 1) & 3, header >> 3
            blocks += 1
            if kind == 3 or size > BLOCK_BYTES or blocks > max_blocks:
                _fail("invalid_archive_block")
            offset += 3 + (1 if kind == 1 else size)
            if offset > length:
                _fail("truncated_archive_frame")
            if last:
                if offset + 4 != length:
                    _fail("archive_trailing_or_truncated_data")
                return params.content_size


def decode(archive, destination, archive_format, *, max_decoded):
    """Decode to a new bounded spool, validating complete input and checksum.

    max_window_size is bytes in pinned python-zstandard 0.25.0's C backend:
    its constructor passes the integer directly to ZSTD_DCtx_setMaxWindowSize.
    The explicit frame-header check independently enforces the same byte bound.
    """
    if archive_format not in (FORMAT, LEGACY_FORMAT):
        _fail("unsupported_archive_codec")
    total = 0
    try:
        expected = _zstandard_frame(archive, max_decoded) if archive_format == FORMAT else None
        with archive.open("rb") as source, destination.open("xb") as output:
            os.chmod(destination, 0o600)

            def retain(block):
                nonlocal total
                total += len(block)
                if total > max_decoded:
                    _fail("expanded_archive_limit")
                output.write(block)

            if archive_format == FORMAT:
                zstd = _zstandard()
                decoder = zstd.ZstdDecompressor(max_window_size=WINDOW_BYTES)
                with decoder.stream_reader(source, read_across_frames=False) as reader:
                    while block := reader.read(CHUNK_BYTES):
                        retain(block)
                if total != expected:
                    _fail("truncated_archive_frame")
            else:
                decoder = zlib.decompressobj(31)
                while not decoder.eof:
                    block = decoder.unconsumed_tail or source.read(CHUNK_BYTES)
                    if not block:
                        _fail("truncated_archive_frame")
                    retain(decoder.decompress(block, CHUNK_BYTES))
                if decoder.unused_data or source.read(1):
                    _fail("archive_trailing_data")
            output.flush()
        return total
    except CodecError:
        raise
    except Exception:
        _fail("invalid_compressed_archive")
