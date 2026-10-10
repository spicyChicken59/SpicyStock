"""Execute exact identity, cache ownership and literal transport boundaries."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from src import issuer_evidence as issuer

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "issuer-evidence"


@pytest.fixture(scope="module")
def producer():
    spec = importlib.util.spec_from_file_location("issuer_core_fixture_generator", FIXTURES / "generate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def packet(producer):
    raw = producer.publication()
    return raw, producer.collect(raw)


def repack(result, edit):
    receipt, bundle = deepcopy(result["receipt"]), deepcopy(result["bundle"])
    edit(receipt, bundle)
    raw = issuer._encode(bundle)
    sha = issuer._sha(raw)
    receipt["bundle"] = {"sha256": sha, "bytes": len(raw), "path": f"issuer-evidence/{sha}.json"}
    return issuer._encode(receipt), raw


def test_stdlib_parsers_validate_actual_producer_without_site_packages(packet, tmp_path):
    canonical, result = packet
    for name, raw in (("canonical", canonical), ("receipt", result["receipt_bytes"]), ("bundle", result["bundle_bytes"])):
        (tmp_path / name).write_bytes(raw)
    code = (f"import sys;sys.path.insert(0,{str(ROOT)!r});from pathlib import Path;"
            "from src import issuer_evidence as m;"
            f"p=Path({str(tmp_path)!r});m.validate_bundle((p/'receipt').read_bytes(),(p/'bundle').read_bytes());"
            "m.validate_for_publication((p/'canonical').read_bytes(),(p/'receipt').read_bytes(),(p/'bundle').read_bytes(),allow_fixture=True);print('PASS')")
    executed = subprocess.run([sys.executable, "-I", "-S", "-c", code], capture_output=True, timeout=20)
    assert executed.returncode == 0, executed.stderr.decode()
    assert executed.stdout == b"PASS\n"


def test_previous_publication_is_self_valid_but_cannot_attach_to_new_bytes(packet):
    raw, result = packet
    issuer.validate_bundle(result["receipt_bytes"], result["bundle_bytes"])
    with pytest.raises(ValueError, match="publication binding"):
        issuer.validate_for_publication(raw + b"\n", result["receipt_bytes"], result["bundle_bytes"], allow_fixture=True)


@pytest.mark.parametrize("edit", [
    lambda r, b: r.update(schema_version=True),
    lambda r, b: r.update(extra="unrecognized"),
    lambda r, b: r["publication"].pop("reader_sha256"),
    lambda r, b: r["publication"].update(reader_projection_version=True),
    lambda r, b: r["selection"].update(selected_issuer_count=True),
    lambda r, b: r["policy"].update(max_issuers=True),
    lambda r, b: r.update(expires_at=r["generated_at"]),
    lambda r, b: r.update(previous_receipt_sha256="A" * 64),
    lambda r, b: b.update(extra="unrecognized"),
    lambda r, b: b["candidates"][0].update(selected=False),
    lambda r, b: b["issuers"][0]["index"].update(not_selected_count=0),
    lambda r, b: b["issuers"][0]["index"].update(exhibit_links_observed=4),
    lambda r, b: b["issuers"][0]["identity"]["mapping_source"].update(url="https://data.sec.gov/submissions/CIK0000320193.json"),
    lambda r, b: b["issuers"][0]["documents"][0].update(filing_date="2026-10-01"),
    lambda r, b: b["issuers"][0]["documents"][0].update(form="6-K"),
    lambda r, b: b["issuers"][0]["documents"][0]["source"].update(url="https://www.sec.gov/Archives/edgar/data/320193/000032019326009001/different.htm"),
    lambda r, b: b["issuers"][0]["documents"][0]["excerpt"].update(text="forged displayed quote"),
    lambda r, b: b["issuers"][0]["documents"][0]["excerpt"].update(truncated=True),
    lambda r, b: b["stats"].update(downloaded_bytes=32 * 1024 * 1024 + 1),
    lambda r, b: b["stats"].update(capture_bytes=32 * 1024 * 1024 + 1),
])
def test_corruption_rejected_after_bundle_hash_is_recomputed(packet, edit):
    _, result = packet
    receipt, bundle = repack(result, edit)
    with pytest.raises((ValueError, TypeError, KeyError)):
        issuer.validate_bundle(receipt, bundle)


@pytest.mark.parametrize("path", ["../issuer-evidence/x.json", "https://example.invalid/x.json", "issuer-evidence/" + "A" * 64 + ".json", "issuer-evidence/x.json?symbol=PRIVATE"])
def test_descriptor_never_accepts_external_or_traversal_path(packet, path):
    receipt = deepcopy(packet[1]["receipt"])
    receipt["bundle"]["path"] = path
    with pytest.raises(ValueError):
        issuer.parse_receipt(issuer._encode(receipt))


def test_bundle_uses_original_bytes_not_reencoded_json(packet):
    _, result = packet
    with pytest.raises(ValueError, match="exact bytes"):
        issuer.validate_bundle(result["receipt_bytes"], result["bundle_bytes"] + b"\n")


def test_duplicate_and_nonfinite_json_are_refused(packet):
    raw = packet[1]["receipt_bytes"]
    with pytest.raises(ValueError, match="duplicate"):
        issuer.parse_receipt(b'{"schema_version":1,' + raw[1:])
    with pytest.raises(ValueError, match="nonfinite"):
        issuer.parse_receipt(raw.replace(b'"schema_version":1', b'"schema_version":NaN', 1))


def test_candidate_and_anchor_cannot_be_rebound_after_self_integrity(packet):
    canonical, result = packet
    def change(_, bundle):
        next(c for c in bundle["candidates"] if c["ticker"] == "ZIM")["anchors"][0]["reason"] = "Forged event reason"
    receipt, bundle = repack(result, change)
    issuer.validate_bundle(receipt, bundle)
    with pytest.raises(ValueError, match="candidate/anchor"):
        issuer.validate_for_publication(canonical, receipt, bundle, allow_fixture=True)


def test_cache_clock_forgery_cannot_make_old_source_look_new(packet):
    def change(_, bundle):
        source = bundle["issuers"][0]["documents"][0]["source"]
        source["cache_status"] = "verified_cache"
        source["fetched_at"] = "2026-10-09T06:20:00+00:00"
    receipt, bundle = repack(packet[1], change)
    with pytest.raises(ValueError, match="last network clock"):
        issuer.validate_bundle(receipt, bundle)


def write_cache(root, url, body, fetched):
    root.mkdir(exist_ok=True)
    key = issuer._sha(url.encode())
    (root / (key + ".bin")).write_bytes(body)
    (root / (key + ".json")).write_bytes(issuer._encode({"url": url, "sha256": issuer._sha(body), "bytes": len(body), "fetched_at": fetched.isoformat()}))
    return key


def test_verified_cache_retains_last_network_time_and_expires_owned_only(tmp_path):
    now = datetime.now(timezone.utc)
    key = write_cache(tmp_path, issuer.MAPPING_URL, b"mapping source", now - timedelta(days=1))
    transport = issuer._Transport(tmp_path)
    hit = transport._cached(issuer.MAPPING_URL, now)
    assert hit["observed_at"] == hit["fetched_at"] == now - timedelta(days=1)
    assert hit["cache_status"] == "verified_cache"
    state = issuer.validate_cache(tmp_path, now=now + timedelta(days=8), prune=True)
    assert state["entries"] == state["bytes"] == 0
    assert not (tmp_path / (key + ".bin")).exists()


@pytest.mark.parametrize("fault", ["unknown", "orphan", "wrong_hash", "wrong_url", "symlink"])
def test_bad_cache_is_preserved_and_cannot_be_reused_or_saved(tmp_path, fault):
    now = datetime.now(timezone.utc)
    key = write_cache(tmp_path, issuer.MAPPING_URL, b"original", now - timedelta(days=8))
    meta = tmp_path / (key + ".json")
    if fault == "unknown":
        (tmp_path / "unrelated.txt").write_text("unrelated evidence")
    elif fault == "orphan":
        meta.unlink()
    elif fault == "wrong_hash":
        (tmp_path / (key + ".bin")).write_bytes(b"tampered")
    elif fault == "wrong_url":
        value = json.loads(meta.read_bytes()); value["url"] = "https://example.invalid/source"
        meta.write_bytes(issuer._encode(value))
    else:
        external = tmp_path.parent / "external-cache-control"
        external.write_bytes(b"external")
        (tmp_path / (key + ".bin")).unlink()
        (tmp_path / (key + ".bin")).symlink_to(external)
    before = sorted(path.name for path in tmp_path.iterdir())
    with pytest.raises(ValueError):
        issuer.validate_cache(tmp_path, now=now, prune=True)
    assert sorted(path.name for path in tmp_path.iterdir()) == before
    transport = issuer._Transport(tmp_path)
    assert not transport.cache_usable
    assert transport._cached(issuer.MAPPING_URL, now) is None


def test_cache_capacity_refuses_addition_without_deleting_existing(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    write_cache(tmp_path, issuer.MAPPING_URL, b"original", now)
    transport = issuer._Transport(tmp_path)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    monkeypatch.setattr(issuer, "MAX_CACHE_ENTRIES", 1)
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019326009001/new.htm"
    transport._save(url, b"new body", now)
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


class Clock:
    def __init__(self):
        self.value = 0.0
    def advance(self, seconds):
        self.value += seconds


class Response:
    status = 200
    headers = {}
    def __init__(self, body, clock, step=0):
        self.body, self.clock, self.step = body, clock, step
        self.read_sizes, self.timeouts = [], []
        self.fp = SimpleNamespace(raw=SimpleNamespace(_sock=SimpleNamespace(settimeout=self.timeouts.append)))
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self, size):
        raise AssertionError("blocking read must not be selected")
    def read1(self, size):
        self.read_sizes.append(size)
        self.clock.advance(self.step)
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk


def wire_transport(monkeypatch, response):
    monkeypatch.setattr(issuer.time, "monotonic", lambda: response.clock.value)
    monkeypatch.setattr(issuer.time, "sleep", response.clock.advance)
    transport = issuer._Transport()
    transport.opener = SimpleNamespace(open=lambda request, timeout: response)
    return transport, issuer._Budget()


def test_slow_body_uses_read1_and_remaining_socket_deadline(monkeypatch):
    clock = Clock()
    response = Response(b"x" * 1000000, clock, step=3)
    transport, budget = wire_transport(monkeypatch, response)
    with pytest.raises(issuer.SourceError) as error:
        transport.fetch(issuer.MAPPING_URL, budget)
    assert error.value.code == "time_budget"
    assert response.timeouts == [10, 7, 4, 1]
    assert budget.requests == 1
    assert budget.bytes == 4 * 65536


def test_streamed_oversize_counts_the_actual_probe_byte(monkeypatch):
    response = Response(b"x" * (2 * 1024 * 1024 + 10), Clock())
    transport, budget = wire_transport(monkeypatch, response)
    with pytest.raises(issuer.SourceError) as error:
        transport.fetch(issuer.MAPPING_URL, budget)
    assert error.value.code == "size_limit"
    assert budget.bytes == 2 * 1024 * 1024 + 1
    assert response.read_sizes[-1] == 1


def test_aggregate_stream_stops_at_literal_remaining_budget(monkeypatch):
    response = Response(b"abcd", Clock())
    transport, budget = wire_transport(monkeypatch, response)
    budget.bytes = 32 * 1024 * 1024 - 3
    with pytest.raises(issuer.SourceError) as error:
        transport.fetch(issuer.MAPPING_URL, budget)
    assert error.value.code == "size_limit"
    assert budget.bytes == 32 * 1024 * 1024
    assert response.read_sizes == [3]
    assert response.body == b"d"


def test_denied_request_counts_attempt_without_reading_arbitrary_error_body(monkeypatch):
    transport, budget = wire_transport(monkeypatch, Response(b"", Clock()))
    def denied(request, timeout):
        raise HTTPError(issuer.MAPPING_URL, 429, "denied", {}, None)
    transport.opener.open = denied
    with pytest.raises(issuer.SourceError) as error:
        transport.fetch(issuer.MAPPING_URL, budget)
    assert error.value.code == "rate_limit"
    assert budget.requests == 1 and budget.bytes == 0


def test_expired_global_deadline_precedes_cache_lookup(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(issuer.time, "monotonic", lambda: clock.value)
    transport, budget = issuer._Transport(), issuer._Budget()
    def forbidden(*args):
        raise AssertionError("expired collection must not read cache")
    monkeypatch.setattr(transport, "_cached", forbidden)
    clock.advance(241)
    with pytest.raises(issuer.SourceError) as error:
        transport.fetch(issuer.MAPPING_URL, budget)
    assert error.value.code == "time_budget" and budget.requests == budget.bytes == 0


def test_cache_lookup_cannot_finish_after_deadline_and_still_succeed(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(issuer.time, "monotonic", lambda: clock.value)
    transport, budget = issuer._Transport(), issuer._Budget()
    def slow_cache(*args):
        clock.advance(241)
        return {"body": b"cache", "observed_at": datetime.now(timezone.utc)}
    monkeypatch.setattr(transport, "_cached", slow_cache)
    with pytest.raises(issuer.SourceError) as error:
        transport.fetch(issuer.MAPPING_URL, budget)
    assert error.value.code == "time_budget"


def test_warm_cache_captures_are_bounded_without_fabricated_downloads():
    now = datetime.now(timezone.utc)
    counter = []
    def cached(url):
        counter.append(url)
        return {"body": bytes([len(counter)]) * (2 * 1024 * 1024), "observed_at": now,
                "fetched_at": now, "cache_status": "verified_cache"}
    fetcher = issuer._Fetcher(cached, None, now)
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019326009001/source.htm"
    for _ in range(16):
        fetcher.get(url)
    with pytest.raises(issuer.SourceError) as error:
        fetcher.get(url)
    assert error.value.code == "size_limit"
    assert fetcher.capture_bytes == 32 * 1024 * 1024
    assert fetcher.budget.requests == fetcher.budget.bytes == 0
    assert len(fetcher.captures) == 16


def test_fake_aggregate_overshoot_is_reported_honestly():
    now = datetime.now(timezone.utc)
    fetcher = issuer._Fetcher(lambda url: {"body": b"12345", "observed_at": now}, None, now)
    fetcher.budget.bytes = 32 * 1024 * 1024 - 4
    with pytest.raises(issuer.SourceError):
        fetcher.get(issuer.MAPPING_URL)
    assert fetcher.budget.bytes == 32 * 1024 * 1024 + 1
    assert fetcher.budget.stop == "size_limit" and not fetcher.captures


def test_literal_operational_bounds():
    assert issuer.MAX_CACHE_BYTES == 128 * 1024 * 1024
    assert issuer.MAX_CACHE_ENTRIES == 256
    assert issuer.MAX_CAPTURE_BYTES == issuer.MAX_DOWNLOAD_BYTES == 32 * 1024 * 1024
    assert issuer.MAX_COLLECTION_SECONDS == 240
    assert issuer.MAX_REQUESTS == 96


def test_utf8_excerpt_uses_literal_byte_boundary_without_splitting_a_character():
    text = "é" * 20000
    excerpt = issuer._excerpt(text)
    assert len(excerpt["text"].encode("utf-8")) == 16384
    assert excerpt["characters"] == 8192
    assert excerpt["normalized_characters"] == 20000 and excerpt["truncated"] is True
    assert excerpt["sha256"] == issuer._sha(("é" * 8192).encode())


def test_legitimate_post_start_filing_waits_next_as_of_attempt(producer, packet):
    canonical, _ = packet
    data = producer.aapl_submissions()
    data["filings"]["recent"]["acceptanceDateTime"][0] = "2026-10-10T06:20:07Z"
    base = producer.transport(edits={producer.AAPL_SUBMISSIONS: producer.json_bytes(data)})
    def inflight(url):
        return {**base(url), "observed_at": producer.NOW + timedelta(seconds=8)}
    result = producer.collect(canonical, fetch=inflight, finished_at=producer.NOW + timedelta(seconds=10))
    row = next(r for r in result["bundle"]["issuers"] if r["ticker"] == "AAPL")
    assert row["index"]["coverage_status"] == "partial"
    assert row["index"]["listed_filings"][0]["accession"] == "0000320193-26-009002"
    assert "0000320193-26-009001" not in row["index"]["selected_accessions"]
    later = issuer.parse_submissions(producer.json_bytes(data), 320193, "AAPL", producer.NOW + timedelta(seconds=10))
    assert "0000320193-26-009001" in {f["accession"] for f in later["filings"]}


def test_cache_total_byte_limit_precedes_any_expiry_deletion(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    write_cache(tmp_path, issuer.MAPPING_URL, b"old bytes", now - timedelta(days=8))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    monkeypatch.setattr(issuer, "MAX_CACHE_BYTES", sum(map(len, before.values())) - 1)
    with pytest.raises(ValueError, match="total byte"):
        issuer.validate_cache(tmp_path, now=now, prune=True)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_request_spacing_cannot_count_an_attempt_that_never_started(monkeypatch):
    response = Response(b"source", Clock())
    transport, budget = wire_transport(monkeypatch, response)
    transport.last_request = 239.5
    response.clock.value = 239.5
    with pytest.raises(issuer.SourceError) as error:
        transport.fetch(issuer.MAPPING_URL, budget)
    assert error.value.code == "time_budget"
    assert budget.requests == 0 and response.read_sizes == []


def test_absolute_alarm_interrupts_a_blocked_open_before_socket_timeout(monkeypatch):
    transport, budget = issuer._Transport(), issuer._Budget()
    monkeypatch.setattr(budget, "remaining", lambda: 0.02)
    entered = []
    def blocked(request, timeout):
        entered.append(timeout)
        # A real blocking primitive allows the POSIX alarm to interrupt it;
        # merely advancing a fake clock cannot prove an absolute deadline.
        import threading
        threading.Event().wait(0.2)
        raise AssertionError("absolute request timer did not interrupt")
    transport.opener.open = blocked
    previous = issuer.signal.getsignal(issuer.signal.SIGALRM)
    with pytest.raises(issuer.SourceError) as error:
        transport.fetch(issuer.MAPPING_URL, budget)
    assert error.value.code == "timeout"
    assert entered == [0.02] and budget.requests == 1 and budget.bytes == 0
    assert issuer.signal.getitimer(issuer.signal.ITIMER_REAL) == (0.0, 0.0)
    assert issuer.signal.getsignal(issuer.signal.SIGALRM) == previous
