"""Input artifacts over existing doubles. All symbols here are synthetic.

The nineteen-name case is deliberately not a reconstruction of the eleven
unidentified historical names. No test opens a provider connection.
"""
import copy
import gzip
import hashlib
import json
import string
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from src import inputs, market_data, pipeline, universe

NOW = datetime(2026, 9, 18, 22, 30, tzinfo=timezone.utc)
DAY = NOW.date()


def flat(n=20):
    return pd.DataFrame({"Open": [10.] * n, "High": [11.] * n, "Low": [9.] * n,
                         "Close": [10.] * n, "Volume": [200_000] * n},
                        index=pd.date_range(end=DAY, periods=n, freq="B", tz="UTC"))


def retained(rep):
    from src import input_diagnostics as diag
    assert rep.input_diagnostic["status"] == "retained", rep.input_diagnostic
    path = Path(rep.input_diagnostic["path"])
    record = json.loads((path / diag.RECORD_NAME).read_bytes())
    raw = (path / diag.DIRECTORY_NAME).read_bytes() if (path / diag.DIRECTORY_NAME).exists() else None
    diag.validate(record, expected_run=record["run"], ledger=rep.input_coverage, directory_bytes=raw)
    return record


def test_nineteen_stale_names_keep_eight_public_samples_and_all_observations(
        mocked_boundaries, fake_alpaca, tmp_path):
    stale = ["STA" + letter for letter in string.ascii_uppercase[:19]]
    healthy = ["OKA" + letter for letter in string.ascii_uppercase[:20]]
    for symbol in stale + healthy + ["SPY"]:
        fake_alpaca.add_history(symbol, flat(), stale_sessions=int(symbol in stale))
    rep = pipeline.run_evening(docs=tmp_path / "docs", tickers=stale + healthy, now=NOW)
    assert rep.published and rep.exit_code() == 2, rep.failure
    public = json.loads((tmp_path / "docs/data.json").read_bytes())
    reason = public["run"]["coverage"]["reasons"]["stale"]
    assert reason == universe.population(stale) and len(reason["sample"]) == 8
    # This is the failing-before assertion on the unmodified release base.
    assert len(list((tmp_path / "input-diagnostics").glob("*/input-exceptions.json"))) == 1
    record = retained(rep)
    assert record["exceptions"]["stale"]["symbols"] == stale
    assert record["exceptions"]["stale"]["identity"] == reason["identity"]
    assert record["capture"]["evaluation"] == "not_started"
    assert "measured" not in record["input_counts"] and public["run"]["coverage"]["measured"] == 20
    for symbol in stale:
        obs = record["observations"][symbol]
        assert obs["frame"] == "available" and obs["attempted"]
        assert len(obs["rows"]) == 8 and obs["rows_omitted"] == 12
        assert obs["rows"][-1]["timestamp"]["session"] == "2026-09-17"
        assert obs["session_rows"]["2026-09-18"] == {"present": 0, "retained": 0}
    assert not list((tmp_path / "docs").rglob("input-exceptions.json"))
    assert len(fake_alpaca.bar_requests) == 1


def snapshot(frames, stats, names=None):
    from src import input_diagnostics as diag
    names = names or sorted(set(frames) | {"SPY"})
    uni = universe._explicit_universe(names)
    ready = market_data.apply_session_rules(frames, DAY, stats)
    cov = inputs.build(uni, names, frames, stats, ready, DAY, DAY,
                       closed=False, minimum=.5, benchmark="SPY")
    record = diag.build(identity={"run_id": "123", "attempt": "2", "execution_revision": "a" * 40,
                                 "workflow_revision": "b" * 40, "invocation": "c" * 32},
                        captured_at=NOW, uni=uni, symbols=names, frames=frames, stats=stats, ready=ready,
                        coverage=cov, expected=DAY, session=DAY, now=NOW, lookback=260,
                        chunk_size=500, budget=900)
    record["directory"] = {"status": "not_used"}
    record["record_sha256"] = diag.digest(record)
    diag.validate(record, expected_run=record["run"], ledger=cov)
    return record, cov


def test_distinct_input_outcomes_and_overlapping_duplicate_repairs():
    stale, gap, unreadable = flat().iloc[:-1], flat().drop(flat().index[-2]), flat()
    unreadable.loc[unreadable.index[-1], "High"] = float("inf")
    frames = {"STALE": stale, "GAP": gap, "BAD": unreadable, "GOOD": flat(), "SPY": flat()}
    stats = market_data.DownloadStats(session=DAY, feed="sip", requested=8, with_bars=5,
             no_bars=["NONE"], dropped=1, dropped_symbols=["DROP"], refused=["DENY"],
             unfetched=["WAIT"], unrequested=["LATER"], duplicates={"STALE": 2, "GOOD": 1})
    names = sorted(set(frames) | {"NONE", "DROP", "DENY", "WAIT", "LATER"})
    record, _ = snapshot(frames, stats, names)
    expected = {"stale": ["STALE"], "gapped": ["GAP"], "unreadable": ["BAD"], "no_bars": ["NONE"],
                "dropped": ["DROP"], "refused": ["DENY"], "unfetched_budget": ["WAIT"], "unfetched_failure": ["LATER"]}
    assert {k: v["symbols"] for k, v in record["exceptions"].items()} == expected
    assert record["duplicate_repaired"]["symbols"] == ["GOOD", "STALE"]
    assert record["input_counts"]["duplicate_bars"] == 3
    for symbol in ("NONE", "DROP", "DENY", "WAIT", "LATER"):
        assert record["observations"][symbol]["frame"] == "missing"
        assert record["observations"][symbol]["rows"] == []
        assert record["observations"][symbol]["attempted"] == (symbol not in {"WAIT", "LATER"})


def test_refusal_keeps_earlier_batches_and_never_attempted_tail(
        mocked_boundaries, fake_alpaca, monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "FETCH_CHUNK", 2)
    original = market_data.download_bars
    monkeypatch.setattr(market_data, "download_bars", lambda *a, **kw: original(*a, batch_size=1, **kw))
    fake_alpaca.add_history("AAA", flat(), stale_sessions=1)
    fake_alpaca.add_history("BBB", flat())
    fake_alpaca.raise_on_bars = RuntimeError("403 subscription does not permit querying recent SIP data")
    fake_alpaca.fail_symbols = {"CCC"}
    rep = pipeline.run_evening(docs=tmp_path / "docs", tickers=["AAA", "BBB", "CCC", "DDD", "EEE"], now=NOW)
    assert rep.exit_code() == 1 and "FeedNotAuthorizedError" in rep.failure
    record = retained(rep)
    assert record["capture"]["fetch"] == "permanent_refusal"
    assert record["returned"]["symbols"] == ["AAA", "BBB"]
    assert record["exceptions"]["refused"]["symbols"] == ["CCC"]
    assert record["exceptions"]["unfetched_failure"]["symbols"] == ["DDD", "EEE", "SPY"]
    assert record["observations"]["AAA"]["rows"]
    assert len(fake_alpaca.bar_requests) == 3
    assert "sdk_internal_partial_pages_unavailable" in record["limits"]


@pytest.mark.parametrize("kind", ["budget", "batch_failure", "no_bars"])
def test_transport_omissions_keep_their_actual_meaning(kind, mocked_boundaries, fake_alpaca, monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "FETCH_CHUNK", 1)
    monkeypatch.setattr(market_data.time, "sleep", lambda *a: None)
    for sym in ["AAA", "BBB", "SPY"]:
        fake_alpaca.add_history(sym, flat())
    if kind == "batch_failure":
        fake_alpaca.raise_on_bars, fake_alpaca.fail_symbols = ConnectionError("fixture"), {"BBB"}
    if kind == "no_bars":
        del fake_alpaca.history["BBB"]
    rep = pipeline.run_evening(docs=tmp_path / "docs", tickers=["AAA", "BBB"], now=NOW,
                               fetch_budget=-1 if kind == "budget" else 900)
    record = retained(rep)
    reason = {"budget": "unfetched_budget", "batch_failure": "dropped", "no_bars": "no_bars"}[kind]
    assert record["exceptions"][reason]["symbols"] == (["BBB", "SPY"] if kind == "budget" else ["BBB"])
    assert len(fake_alpaca.bar_requests) == {"budget": 1, "batch_failure": 4, "no_bars": 3}[kind]


def test_missing_invalid_values_timestamps_and_tail_are_never_zeroed():
    from src import input_diagnostics as diag
    frame = flat(25).astype({"Close": object})
    frame.iloc[0, frame.columns.get_loc("Close")] = None
    frame.iloc[1, frame.columns.get_loc("Close")] = pd.NA
    frame.iloc[2, frame.columns.get_loc("Close")] = float("nan")
    frame.iloc[3, frame.columns.get_loc("Close")] = float("inf")
    frame.iloc[4, frame.columns.get_loc("Close")] = -float("inf")
    frame.iloc[5, frame.columns.get_loc("Close")] = "SECRET_SENTINEL"
    assert [diag.value_cell(v)["state"] for v in frame.Close.iloc[:6]] == ["null", "missing", "nan", "positive_infinity", "negative_infinity", "invalid"]
    # Put both anchor dates outside the tail; frame order is preserved, not reclassified.
    index = list(frame.index)
    index[0], index[-1] = index[-1], index[0]
    index[1], index[-2] = index[-2], index[1]
    index[2], index[3] = pd.NaT, "SECRET_SENTINEL"
    frame.index = pd.Index(index)
    frame["Volume"] = [2**53 + 1] * len(frame)
    frame["Open"] = [1.0000000000000002] * len(frame)
    frame["private"] = "SECRET_SENTINEL"
    del frame["High"]
    obs = diag.observations(frame, DAY, date(2026, 9, 17), remaining=100)
    assert len(obs["rows"]) == 10 and obs["rows_omitted"] == 15
    assert [r["position"] for r in obs["rows"]] == [0, 1] + list(range(17, 25))
    assert obs["rows"][0]["values"]["Volume"]["value"] == 2**53 + 1
    assert obs["rows"][0]["values"]["Open"]["value"] == 1.0000000000000002
    assert obs["rows"][0]["values"]["High"] == {"state": "absent_field"}
    assert diag.timestamp_cell(pd.Timestamp("2026-09-18T04:00:00.123456789Z"))["value"] == "2026-09-18T04:00:00.123456789+00:00"
    assert diag.timestamp_cell(pd.NaT) == {"state": "nat"}
    assert diag.timestamp_cell("SECRET_SENTINEL") == {"state": "unreadable"}
    assert "SECRET_SENTINEL" not in diag.canonical(obs).decode()


def test_global_observation_budget_never_truncates_membership(monkeypatch):
    from src import input_diagnostics as diag
    monkeypatch.setattr(diag, "MAX_TOTAL_ROWS", 8)
    record, _ = snapshot({"AAA": flat().iloc[:-1], "BBB": flat().iloc[:-1], "SPY": flat()},
                         market_data.DownloadStats(DAY, "sip", requested=3, with_bars=3))
    assert record["exceptions"]["stale"]["symbols"] == ["AAA", "BBB"]
    assert record["observations"]["BBB"]["rows"] == []
    assert record["observations"]["BBB"]["rows_omitted"] == 19
    assert record["observations"]["BBB"]["partial"]
    assert not record["bounds"]["membership_truncated"]


@pytest.mark.parametrize("change", ["member", "digest", "run", "attempt", "revision", "ledger"])
def test_validation_rejects_tampering_or_mismatched_run(change):
    from src import input_diagnostics as diag
    record, cov = snapshot({"AAA": flat().iloc[:-1], "SPY": flat()},
                           market_data.DownloadStats(DAY, "sip", requested=2, with_bars=2))
    expected = copy.deepcopy(record["run"])
    if change == "member":
        record["exceptions"]["stale"] = diag.population(["BBB"])
        record["record_sha256"] = diag.digest({k: v for k, v in record.items() if k != "record_sha256"})
    elif change == "digest":
        record["observations"]["AAA"]["rows"][0]["values"]["Close"]["value"] = 999
    elif change == "ledger":
        cov["stale"] = 0
    else:
        expected[{"run": "run_id", "attempt": "attempt", "revision": "execution_revision"}[change]] = "different"
    with pytest.raises(ValueError, match="invalid input diagnostic"):
        diag.validate(record, expected_run=expected, ledger=cov)


def test_directory_requires_used_source_and_exact_capture_identity(tmp_path):
    from src import input_diagnostics as diag
    rows = [{k: "AAA" if k == "symbol" else "" for k in universe.DIRECTORY_FIELDS}]
    universe._save_directory_cache(tmp_path, rows, NOW.isoformat())
    original = (tmp_path / universe.DIRECTORY_CACHE).read_bytes()
    fingerprint = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    uni = replace(universe._explicit_universe(["AAA"]), source=universe.SOURCE_LIVE,
                  fetched_at=NOW.isoformat(), snapshot_sha256=fingerprint)
    metadata, raw = diag.directory_snapshot(tmp_path, uni)
    assert raw == original and metadata["sha256"] == hashlib.sha256(original).hexdigest()
    assert diag.directory_snapshot(tmp_path, replace(uni, source=universe.SOURCE_SEED)) == ({"status": "not_used"}, None)
    assert diag.directory_snapshot(tmp_path, replace(uni, source=universe.SOURCE_EXPLICIT)) == ({"status": "not_used"}, None)
    assert diag.directory_snapshot(tmp_path, replace(uni, fetched_at="2026-09-17T22:30:00+00:00"))[1] is None
    data = json.loads(gzip.decompress(original))
    data["private"] = "SECRET_SENTINEL"
    (tmp_path / universe.DIRECTORY_CACHE).write_bytes(gzip.compress(json.dumps(data).encode()))
    assert diag.directory_snapshot(tmp_path, uni)[1] is None


def test_run_identity_uses_checkout_not_workflow_revision_and_ignores_arbitrary_environment(monkeypatch):
    from src import input_diagnostics as diag
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.delenv("GITHUB_RUN_ID_FOR_RECORD", raising=False)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    monkeypatch.setenv("EMAIL_TO", "SECRET_SENTINEL")
    monkeypatch.setattr(diag.subprocess, "run", lambda *a, **kw: type("Result", (), {"stdout": "a" * 40})())
    ident = diag.run_identity()
    assert ident["run_id"] == "123" and ident["attempt"] == "2"
    assert ident["execution_revision"] == "a" * 40 and ident["workflow_revision"] == "b" * 40
    assert "SECRET_SENTINEL" not in diag.canonical(ident).decode()


def test_skips_preflight_and_consecutive_runs_never_reuse_evidence(mocked_boundaries, fake_alpaca, tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    for symbol in ["AAA", "SPY"]:
        fake_alpaca.add_history(symbol, flat())
    first = pipeline.run_evening(docs=docs, tickers=["AAA"], now=NOW)
    first_bytes = Path(first.input_diagnostic["path"], "input-exceptions.json").read_bytes()
    fake_alpaca.bar_requests.clear()
    for now in (datetime(2026, 9, 19, 22, 30, tzinfo=timezone.utc), NOW.replace(hour=15)):
        skipped = pipeline.run_evening(docs=docs, tickers=["AAA"], now=now)
        assert skipped.input_diagnostic == {"status": "not_attempted", "path": None}
        assert fake_alpaca.bar_requests == []
    with monkeypatch.context() as m:
        m.delenv("ALPACA_API_KEY")
        with pytest.raises(pipeline.PreflightError):
            pipeline.run_evening(docs=docs, tickers=["AAA"], now=NOW)
    assert len(list((tmp_path / "input-diagnostics").iterdir())) == 1
    second = pipeline.run_evening(docs=docs, tickers=["AAA"], now=NOW)
    assert first.input_diagnostic["path"] != second.input_diagnostic["path"]
    assert Path(first.input_diagnostic["path"], "input-exceptions.json").read_bytes() == first_bytes


@pytest.mark.parametrize("failure", ["none", "write", "serialize", "coverage", "grade", "publish", "email"])
def test_diagnostics_preserve_records_decisions_calls_and_exit_codes(
        failure, mocked_boundaries, fake_alpaca, fake_anthropic, fake_resend, monkeypatch, tmp_path, caplog):
    from src import input_diagnostics as diag, provenance
    monkeypatch.setattr(pipeline.time, "monotonic", lambda: 100.0)
    for symbol in ["AAA", "BBB", "CCC", "SPY"]:
        fake_alpaca.add_history(symbol, flat(), stale_sessions=int(failure == "coverage" and symbol != "SPY"))
    def fail(*a, **kw):
        raise OSError("SECRET_SENTINEL")
    if failure == "grade":
        monkeypatch.setattr(pipeline, "rank", fail)
    elif failure == "publish":
        monkeypatch.setattr(provenance, "publish_bundle", fail)
    elif failure == "email":
        monkeypatch.setattr(pipeline.report, "send_digest", fail)
    original = diag.capture
    results = []
    for enabled in (False, True):
        fake_alpaca.bar_requests.clear()
        fake_anthropic.calls.clear()
        fake_resend.sent.clear()
        docs = tmp_path / str(enabled) / "docs"
        with monkeypatch.context() as m:
            m.setattr(diag, "capture", original if enabled else lambda **kw: {"status": "disabled", "path": None})
            if failure == "write":
                m.setattr(diag, "_atomic_write", fail)
            if failure == "serialize":
                m.setattr(diag, "canonical", fail)
            rep = pipeline.run_evening(docs=docs, tickers=["AAA", "BBB", "CCC"], now=NOW)
        results.append(({p.relative_to(docs).as_posix(): p.read_bytes() for p in docs.rglob("*") if p.is_file()},
                        rep.exit_code(), rep.input_coverage,
                        [{k: str(v) for k, v in r.items()} for r in fake_alpaca.request_fields[-len(fake_alpaca.bar_requests):]],
                        len(fake_alpaca.bar_requests), len(fake_anthropic.calls), len(fake_resend.sent)))
        if enabled:
            if failure in {"write", "serialize"}:
                assert rep.input_diagnostic["status"] == "failed"
                assert "Input diagnostic capture failed" in caplog.text
                assert "SECRET_SENTINEL" not in caplog.text
            else:
                retained(rep)
    assert results[0] == results[1]
    assert results[1][1] == {"none": 0, "write": 0, "serialize": 0, "coverage": 1, "grade": 1, "publish": 1, "email": 3}[failure]


def test_large_exception_cohort_has_complete_membership_and_bounded_size():
    from tools.input_diagnostic_size import fixture, measure
    record = fixture()
    assert len(record["exceptions"]["stale"]["symbols"]) == 8001
    assert len(record["exceptions"]["stale"]["sample"]) == 8
    measured = measure(record)
    assert measured["rows_retained"] == 80_010
    assert measured["json_bytes"] < 60 * 1024 * 1024
    assert measured["gzip_bytes"] < 2 * 1024 * 1024


def test_candidate_publication_plans_grades_and_rules_are_identical(
        mocked_boundaries, fake_alpaca, fake_anthropic, fake_resend, monkeypatch, tmp_path):
    from src import input_diagnostics as diag
    from tests.test_pipeline import a_plus_frame, CLAUDE_A_PLUS
    from tests.test_watchlist import coil
    for symbol in ["AAA", "BBB", "CCC", "SPY"]:
        fake_alpaca.add_history(symbol, flat(260))
    fake_alpaca.add_history("AAA", a_plus_frame())
    fake_alpaca.add_history("COIL", coil())
    fake_anthropic.set_payload(dict(CLAUDE_A_PLUS))
    monkeypatch.setattr(pipeline.time, "monotonic", lambda: 100.0)
    captured = []
    publish = pipeline.provenance.publish_bundle
    def observe_publication(data, rec, docs, objects, **kwargs):
        captured.append((copy.deepcopy(data), copy.deepcopy(rec), dict(objects)))
        return publish(data, rec, docs, objects, **kwargs)
    monkeypatch.setattr(pipeline.provenance, "publish_bundle", observe_publication)
    outcomes = []
    for enabled in (False, True):
        fake_alpaca.bar_requests.clear()
        fake_anthropic.calls.clear()
        fake_resend.sent.clear()
        docs = tmp_path / str(enabled) / "docs"
        with monkeypatch.context() as m:
            if not enabled:
                m.setattr(diag, "capture", lambda **kw: {"status": "disabled", "path": None})
            rep = pipeline.run_evening(docs=docs, tickers=["AAA", "BBB", "CCC", "COIL"], now=NOW)
        outcomes.append((rep.exit_code(), rep.input_coverage, len(fake_alpaca.bar_requests), len(fake_anthropic.calls),
                         {p.name: p.read_bytes() for p in docs.glob("*.json")}))
        if enabled:
            retained(rep)
    assert len(captured) == 2 and captured[0] == captured[1]
    assert captured[0][0]["bursts"][0]["grade"] == "A+" and captured[0][0]["trades"] == ["AAA"]
    assert outcomes[0] == outcomes[1] and outcomes[1][2:4] == (1, 1)
    # The release runner is Linux. Windows' already-reproduced source-object
    # rename defect remains visible here; comparison above still tests all
    # prepared records/receipts and grading calls without replacing that writer.
    if __import__("os").name != "nt":
        assert outcomes[1][0] == 0 and set(outcomes[1][4]) >= {"data.json", "picks.json"}
    else:
        assert outcomes[1][0] == 1 and "WinError 32" in rep.failure


def test_verifier_rejects_wrong_external_identity_and_publication(tmp_path, capsys):
    from src import input_diagnostics as diag
    from tools.verify_input_diagnostics import main
    record, cov = snapshot({"AAA": flat().iloc[:-1], "SPY": flat()},
                           market_data.DownloadStats(DAY, "sip", requested=2, with_bars=2))
    (tmp_path / diag.RECORD_NAME).write_bytes(diag.canonical(record))
    args = [str(tmp_path), "--run-id", "123", "--attempt", "2", "--revision", "a" * 40]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["validated"]
    with pytest.raises(ValueError):
        main(args[:-1] + ["b" * 40])
    publication = tmp_path / "data.json"
    publication.write_text(json.dumps({"run": {"run_id": "wrong", "coverage": cov}}))
    with pytest.raises(ValueError, match="run/session differ"):
        main(args + ["--publication", str(publication)])


def test_capture_failure_keeps_original_refusal_and_never_uploads_prior_record(
        mocked_boundaries, fake_alpaca, monkeypatch, tmp_path):
    from src import input_diagnostics as diag
    for symbol in ["AAA", "SPY"]:
        fake_alpaca.add_history(symbol, flat())
    docs = tmp_path / "docs"
    first = pipeline.run_evening(docs=docs, tickers=["AAA"], now=NOW)
    old = Path(first.input_diagnostic["path"], diag.RECORD_NAME)
    old_bytes = old.read_bytes()
    fake_alpaca.raise_on_bars = RuntimeError("403 subscription does not permit querying recent SIP data")
    def fail(*args):
        raise OSError("SECRET_SENTINEL")
    monkeypatch.setattr(diag, "_atomic_write", fail)
    fake_alpaca.bar_requests.clear()
    second = pipeline.run_evening(docs=docs, tickers=["AAA"], now=NOW)
    assert second.exit_code() == 1 and "FeedNotAuthorizedError" in second.failure
    assert second.input_diagnostic["path"] is None and second.input_diagnostic["status"] == "failed"
    assert len(fake_alpaca.bar_requests) == 1 and old.read_bytes() == old_bytes


def test_package_copies_only_used_directory_bytes_and_allowlisted_fields(
        mocked_boundaries, fake_alpaca, monkeypatch, tmp_path):
    from src import input_diagnostics as diag
    docs = tmp_path / "docs"
    docs.mkdir()
    rows = [{k: "AAA" if k == "symbol" else "" for k in universe.DIRECTORY_FIELDS}]
    universe._save_directory_cache(docs, rows, NOW.isoformat())
    raw = (docs / universe.DIRECTORY_CACHE).read_bytes()
    fingerprint = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    uni = replace(universe._explicit_universe(["AAA", "BBB"]), source=universe.SOURCE_LIVE,
                  fetched_at=NOW.isoformat(), snapshot_sha256=fingerprint,
                  label="SECRET_SENTINEL", names={"AAA": "SECRET_SENTINEL"})
    monkeypatch.setattr(universe, "build", lambda *a, **kw: uni)
    monkeypatch.setenv("UNRELATED_CREDENTIAL", "SECRET_SENTINEL")
    for symbol in ["AAA", "BBB", "SPY"]:
        frame = flat()
        frame["private"] = "SECRET_SENTINEL"
        fake_alpaca.add_history(symbol, frame, stale_sessions=int(symbol == "AAA"))
    rep = pipeline.run_evening(docs=docs, now=NOW)
    record = retained(rep)
    path = Path(rep.input_diagnostic["path"])
    assert (path / diag.DIRECTORY_NAME).read_bytes() == raw
    assert record["directory"]["status"] == "retained"
    assert b"SECRET_SENTINEL" not in (path / diag.RECORD_NAME).read_bytes()
    with pytest.raises(ValueError):
        diag.validate(record, expected_run=record["run"], directory_bytes=raw + b"tampered")


def test_atomic_write_closes_file_before_replacement_and_removes_temporary(tmp_path, monkeypatch):
    from src import input_diagnostics as diag
    opened = []
    original = diag.tempfile.NamedTemporaryFile
    def track(*a, **kw):
        handle = original(*a, **kw)
        opened.append(handle)
        return handle
    replace_file = diag.os.replace
    def verify_closed(src, dest):
        assert opened[-1].closed
        replace_file(src, dest)
    monkeypatch.setattr(diag.tempfile, "NamedTemporaryFile", track)
    monkeypatch.setattr(diag.os, "replace", verify_closed)
    target = tmp_path / "record.json"
    diag._atomic_write(target, b"first")
    diag._atomic_write(target, b"second")
    assert target.read_bytes() == b"second" and list(tmp_path.iterdir()) == [target]
