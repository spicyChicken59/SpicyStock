"""Bounded outer-codec measurement on the unchanged, authorized PR96 fixtures."""
import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import sys
import tarfile
import time

WORK = Path(__file__).resolve().parent
REPO = WORK / "SpicyStock-compaction"
BASELINE = REPO / "docs/input-truthfulness/2026-09-30-projection-compaction-evidence"
OUT = WORK / "synthetic-codec-comparison"
OUT.mkdir(mode=0o700, exist_ok=True)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def memory():
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD), *[(n, ctypes.c_size_t) for n in
                    ("peak_rss", "rss", "quota_peak_paged", "quota_paged", "quota_peak_nonpaged", "quota_nonpaged", "commit", "peak_commit")]]
    values = Counters()
    values.cb = ctypes.sizeof(values)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    library = ctypes.WinDLL("psapi", use_last_error=True)
    library.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    assert library.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(values), values.cb)
    return {"peak_rss_bytes": values.peak_rss, "peak_private_commit_bytes": values.peak_commit,
            "method": "native Windows GetProcessMemoryInfo"}


def inputs(case):
    root = WORK / ("synthetic-compaction-" + case) / "synthetic-storage"
    inventory_path = BASELINE / ("benchmark-" + case + "-members.json")
    inventory = json.loads(inventory_path.read_bytes())
    baseline = json.loads((BASELINE / ("benchmark-" + case + ".json")).read_bytes())
    assert len(inventory) == 390 and sha(inventory_path) == baseline["source_member_inventory_sha256"]
    return root, inventory, baseline


def verify():
    result = {"schema": "historical-original-synthetic-verification-v1", "status": "PASS", "cases": {}}
    for case in ("central", "stress"):
        root, inventory, baseline = inputs(case)
        actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name != "acquisition.lock"}
        assert actual == set(inventory)
        for name, expected in inventory.items():
            path = root / name
            assert not path.is_symlink() and not path.is_junction()
            assert path.stat().st_size == expected["bytes"] and sha(path) == expected["sha256"]
        result["cases"][case] = {"member_count": 390, "source_bytes": sum(v["bytes"] for v in inventory.values()),
                                  "inventory_sha256": baseline["source_member_inventory_sha256"],
                                  "all_lengths_and_sha256_match": True}
    result.update(verified_at=datetime.now(timezone.utc).isoformat(), provider_requests=0, owner_key_access="NOT RUN")
    (OUT / "original-member-verification.json").write_bytes(encode(result))
    print(json.dumps(result), flush=True)


class CheckedReader:
    def __init__(self, stream, deadline):
        self.stream, self.deadline, self.hasher = stream, deadline, hashlib.sha256()
    def read(self, size):
        if time.perf_counter() > self.deadline:
            raise TimeoutError("bounded_compression_600_second_limit")
        raw = self.stream.read(size)
        self.hasher.update(raw)
        return raw


def compress(case, preset, codec):
    verified = json.loads((OUT / "original-member-verification.json").read_bytes())
    assert verified["status"] == "PASS"
    root, inventory, baseline = inputs(case)
    assert verified["cases"][case]["inventory_sha256"] == baseline["source_member_inventory_sha256"]
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name != "acquisition.lock"}
    assert actual == set(inventory)
    for name, entry in inventory.items():
        path = root / name
        assert not path.is_symlink() and not path.is_junction() and path.stat().st_size == entry["bytes"]
    prior = json.loads((BASELINE / "benchmark-central-package-index.json").read_bytes())
    manifest = REPO / "docs/input-truthfulness/2026-09-28-historical-input-evidence/acquisition-manifest.json"
    extras = {"_package/manifest.json": encode(json.loads(manifest.read_bytes())), "_package/execution.json": encode(prior["execution"]),
              "_package/diagnostics.json": encode({"synthetic_only": True, "case": case})}
    for item in prior["members"]:
        if item["path"] in ("_package/manifest.json", "_package/execution.json"):
            assert len(extras[item["path"]]) == item["bytes"]
            assert hashlib.sha256(extras[item["path"]]).hexdigest() == item["sha256"]
    # Prior fixture execution metadata is public, explicitly fictional, and is
    # used only to keep comparison tar shape fixed. No receipt or release made.
    members = [{"path": n, "bytes": e["bytes"], "sha256": e["sha256"]} for n, e in inventory.items()]
    members.extend({"path": n, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for n, raw in extras.items())
    index = {**prior, "members": sorted(members, key=lambda value: value["path"])}
    index_raw = encode(index)
    payload = sum(e["bytes"] for e in members) + len(index_raw)
    assert payload <= 2 * 1024**3
    label = f"xz-preset{preset}" if codec == "xz" else "zstd9-long30"
    archive = OUT / f"{case}-{label}-canonical.tar.{codec}"
    assert not archive.exists()
    wall, cpu = time.perf_counter(), time.process_time()
    result = {"schema": "historical-outer-codec-comparison-v1", "case": case, "codec": codec, "synthetic_only": True,
              "source_inventory_sha256": baseline["source_member_inventory_sha256"], "source_bytes": sum(v["bytes"] for v in inventory.values()),
              "member_count": 390, "index_bytes": len(index_raw), "expanded_bytes": payload, "provider_requests": 0,
              "comparison_script_sha256": sha(Path(__file__)), "comparison_only": True, "encryption": "NOT RUN", "reconciliation_regeneration": "NOT RUN",
              "execution_metadata_scope": "unchanged public PR96 fictional test fixture metadata; not a live execution or release",
              "started_at": datetime.now(timezone.utc).isoformat(), "python": sys.version}
    tar_bytes = 512 + ((len(index_raw)+511)//512)*512 + sum(512+((e["bytes"]+511)//512)*512 for e in members) + 1024
    tar_bytes = ((tar_bytes+10239)//10240)*10240
    result["tar_archive_bytes"] = tar_bytes
    if codec == "xz":
        result.update(preset=preset, dictionary_bytes={6: 8*1024**2, 9: 64*1024**2}[preset])
        writer = lambda raw: lzma.LZMAFile(raw, "w", format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64, preset=preset)
    else:
        sys.path.insert(0, str(WORK / "codecdeps"))
        import zstandard as zstd
        params = zstd.ZstdCompressionParameters.from_level(9, window_log=30, enable_ldm=True,
                    write_checksum=True, write_content_size=True, threads=0)
        result.update(level=9, window_bytes=1024**3, long_distance_matching=True,
                      zstandard_version=zstd.__version__, libzstd_version=zstd.ZSTD_VERSION, threads=0)
        compressor = zstd.ZstdCompressor(compression_params=params)
        writer = lambda raw: compressor.stream_writer(raw, size=tar_bytes, closefd=False)
    try:
        with archive.open("xb") as raw:
            with writer(raw) as compressed:
                with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.USTAR_FORMAT) as tar:
                    values = [{"path": "_package/index.json", "bytes": len(index_raw)}, *index["members"]]
                    for entry in values:
                        info = tarfile.TarInfo(entry["path"])
                        info.size, info.mode, info.mtime = entry["bytes"], 0o600, 0
                        if entry["path"] == "_package/index.json":
                            tar.addfile(info, io.BytesIO(index_raw))
                        elif entry["path"] in extras:
                            tar.addfile(info, io.BytesIO(extras[entry["path"]]))
                        else:
                            with (root / entry["path"]).open("rb") as source:
                                checked = CheckedReader(source, wall + 600)
                                tar.addfile(info, checked)
                                assert checked.hasher.hexdigest() == entry["sha256"]
        result.update(status="PASS" if archive.stat().st_size <= 199 * 1024**2 else "FAIL", archive_bytes=archive.stat().st_size,
                      archive_sha256=sha(archive), source_hashes_verified_while_compressing=True,
                      archive_headroom_bytes=199 * 1024**2 - archive.stat().st_size)
    except Exception as error:
        reason = "bounded_compression_600_second_limit" if time.perf_counter()-wall >= 600 else type(error).__name__
        result.update(status="FAIL", reason=reason, incomplete_archive_bytes=archive.stat().st_size)
    finally:
        result.update(wall_seconds=time.perf_counter()-wall, cpu_seconds=time.process_time()-cpu, memory=memory(),
                      completed_at=datetime.now(timezone.utc).isoformat())
        (OUT / f"{case}-{label}-canonical.json").write_bytes(encode(result))
        print(json.dumps(result), flush=True)


parser = argparse.ArgumentParser()
parser.add_argument("command", choices=("verify", "compress"))
parser.add_argument("--case", choices=("central", "stress"))
parser.add_argument("--preset", choices=(6, 9), type=int)
parser.add_argument("--codec", choices=("xz", "zstd"), default="xz")
args = parser.parse_args()
verify() if args.command == "verify" else compress(args.case, args.preset, args.codec)
