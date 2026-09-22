"""Publication contradictions must fail before replacing either public record.

The initial eight protections were executed against f744b88 before the fix:
all eight failed because the contradictory night still published.
"""
from copy import deepcopy
import gzip
import json
from pathlib import Path

import pytest

from src import pipeline, record, report
from tests.test_pipeline import market, claude, evening, qframe, ideal_bars


@pytest.mark.parametrize("case", ["discovery", "check", "mechanical", "raised_grade",
                                  "regime", "stop", "trigger", "picks"])
def test_contradiction_cannot_publish(case, market, claude, fake_alpaca, fake_resend, tmp_path, monkeypatch):
    if case == "raised_grade":
        fake_alpaca.add_history("AAA", qframe(ideal_bars(close_pos=0.55)))
    original_build = report.build
    original_append = record.append

    def build(*args, **kwargs):
        args = list(args)
        bursts = args[4]
        b = bursts[0]
        if case == "discovery":
            b["discovery"]["measurements"]["gain_pct"] = 0.0
        elif case == "check":
            b["quality"]["checks"][0]["passed"] = False
        elif case == "mechanical":
            b["grade_mechanical"] = "skip"
        elif case == "raised_grade":
            assert b["grade_mechanical"] == "B"
            b["grade"] = "A+"
        elif case == "regime":
            args[3]["regime"]["verdict"] = "red"
        elif case == "stop":
            b["plan"]["stop"] -= 0.01
        elif case == "trigger":
            b["plan"]["order_json"]["stop_price"] -= 0.01
        return original_build(*args, **kwargs)

    def append(rec, session, picks, regime="green"):
        result = original_append(rec, session, picks, regime)
        if case == "picks":
            next(p for p in result["picks"] if p["ticker"] == "AAA")["stop"] -= 0.01
        return result

    monkeypatch.setattr(report, "build", build)
    monkeypatch.setattr(record, "append", append)
    rep, data, docs = evening(tmp_path, market)
    assert not rep.published, f"{case} contradiction was published"
    assert rep.exit_code() == pipeline.EXIT_FAILED
    assert "provenance refused" in rep.failure, rep.failure
    assert data is None
    assert not (docs / record.PICKS_FILE).exists()


def test_control_actionable_publication(market, claude, fake_resend, tmp_path):
    rep, data, docs = evening(tmp_path, market)
    assert rep.published and data["trades"] == ["AAA"], rep.failure
    assert json.loads((docs / record.PICKS_FILE).read_text())["picks"]


ROOT = Path(__file__).resolve().parents[1]
OBJECTS = ROOT / "tests/fixtures/provenance/objects"


def fixture(name="full"):
    return json.loads((ROOT / f"tests/fixtures/page/{name}.json").read_bytes())


@pytest.mark.parametrize("name", ["full", "red", "yellow", "notrade", "degraded", "early", "next", "revised", "empty", "partial", "closed"])
def test_retained_fixture_chain(name):
    from src import provenance
    data = fixture(name)
    picks = fixture("full-picks") if name == "full" else None
    before = deepcopy(data)
    result = provenance.verify(data, picks, OBJECTS, require_picks=picks is not None)
    assert result["status"] == "PASS", result
    assert data == before, "verification must not repair a record"


def test_regime_and_reader_decisions_are_distinct_from_quality():
    red, yellow, lower, down = [fixture(n) for n in ("red", "yellow", "notrade", "degraded")]
    a = next(b for b in red["bursts"] if b["grade"] == "A+")
    assert a["evidence"]["gate"] == {"regime": "red", "final_grade": "A+", "allowed_grades": [], "ticket": False, "reason": "regime_gate", "detail": None}
    assert a["plan"] is None and not red["trades"]
    assert yellow["trades"]
    assert all(b["evidence"]["gate"]["allowed_grades"] == ["A+"] for b in yellow["bursts"])
    assert all(b["grade"] == "A+" for b in yellow["bursts"] if b["evidence"]["gate"]["ticket"])
    assert any(b["grade_mechanical"] == "A+" and b["grade"] == "C" and b["claude"]["returned_grade"] == "C" for b in lower["bursts"])
    for b in down["bursts"]:
        assert b["grade"] == b["grade_mechanical"]
        assert b["claude"]["source"] == "fallback"
        assert b["claude"]["score"] is None and b["claude"]["reason"] is None
        assert b["claude"]["attempts"][-1]["outcome"] == "rejected"


@pytest.mark.parametrize("case,reason", [("discovery", "discovery digest"), ("threshold", "quality digest"),
    ("mechanical", "quality digest"), ("reader", "reader result digest"), ("grade", "down-only"),
    ("plan", "plan/ticket digest"), ("calendar", "run/context"), ("regime", "run/context"),
    ("identity", "evidence identity"), ("reference", "reference mismatch"), ("missing", "run provenance"),
    ("candidate_removed", "run/context"), ("anticipation", "anticipation plan digest")])
def test_each_changed_layer_is_refused(case, reason):
    from src import provenance
    d = fixture()
    b = d["bursts"][0]
    if case == "discovery": b["discovery"]["measurements"]["gain_pct"] += 0.01
    elif case == "threshold": b["quality"]["checks"][0]["threshold"] += " changed"
    elif case == "mechanical": b["grade_mechanical"] = "B"
    elif case == "reader": b["claude"]["reason"] = "changed"
    elif case == "grade": b["grade"] = "A"
    elif case == "plan": b["plan"]["stop"] -= 0.01
    elif case == "calendar": d["run"]["timing"]["applicable_session"] = "2026-09-14"
    elif case == "regime": d["breadth"]["regime"]["verdict"] = "red"
    elif case == "identity": b["evidence"]["id"] = "0" * 64
    elif case == "reference": b["plan"]["evidence_ref"]["id"] = "0" * 64
    elif case == "missing": del d["run"]["evidence"]
    elif case == "candidate_removed": d["bursts"].pop()
    elif case == "anticipation": d["watchlist"]["top"][0]["plan"]["stop"] -= 0.01
    result = provenance.verify(d, require_sources=False)
    assert result["status"] == "FAIL" and any(reason in r for r in result["breaks"]), result


def reseal(b):
    """Simulate a builder committing a WRONG result consistently to its hashes."""
    from src import provenance
    e = b["evidence"]
    e["id"] = provenance.digest({k: v for k, v in e.items() if k != "id"})
    if b.get("plan"):
        b["plan"]["evidence_ref"] = provenance.reference(e)


def test_consistent_hashes_do_not_legalize_an_upgraded_grade():
    from src import provenance
    d = fixture()
    b = next(b for b in d["bursts"] if b["grade_mechanical"] == "B")
    b["grade"] = b["evidence"]["final_grade"] = "A+"
    reseal(b)
    result = provenance.verify(d, require_sources=False)
    assert any("down-only" in x for x in result["breaks"]), result


def test_consistent_hashes_do_not_legalize_wrong_plan_rules():
    from src import provenance
    d = fixture(); b = d["bursts"][0]
    b["plan"]["stop"] -= 0.01
    b["evidence"]["planning"]["output_sha256"] = provenance.digest(provenance.plain_plan(b))
    reseal(b)
    result = provenance.verify(d, require_sources=False)
    assert any("production plan rules" in x for x in result["breaks"]), result


def test_plan_calendar_disagreement_is_detected_even_when_plan_hash_is_updated():
    from src import provenance
    d = fixture(); b = d["bursts"][0]
    b["plan"]["exit_schedule"][0]["date"] = "2026-09-14"
    b["evidence"]["planning"]["output_sha256"] = provenance.digest(provenance.plain_plan(b))
    reseal(b)
    result = provenance.verify(d, require_sources=False)
    assert any("calendar applicability" in x for x in result["breaks"]), result


def test_picks_mismatch_and_individual_ticket_verification():
    from src import provenance
    d, p = fixture(), fixture("full-picks")
    b = d["bursts"][0]
    assert provenance.verify_setup(b["plan"], d, p, OBJECTS)["status"] == "PASS"
    candidate = deepcopy(b); candidate["discovery"]["measurements"]["gain_pct"] = 0
    assert provenance.verify_setup(candidate, d, p, OBJECTS)["status"] == "FAIL"
    pick = next(x for x in p["picks"] if x.get("evidence_ref", {}).get("id") == b["evidence"]["id"])
    pick["stop"] -= 0.01
    result = provenance.verify(d, p, OBJECTS)
    assert any("picks/data" in x for x in result["breaks"]), result


def test_source_digest_is_of_the_actual_numeric_read_views():
    import numpy as np
    from src import provenance, quality, scans
    df = qframe(ideal_bars())
    df.iloc[0, df.columns.get_loc("Close")] = 0.0
    df.iloc[1, df.columns.get_loc("Close")] = 100.00500000000001
    df.iloc[2, df.columns.get_loc("Volume")] = np.nan
    obj = provenance.source_object(df)
    restored = provenance.frame_of(json.loads(json.dumps(obj)))
    ref = provenance.source_ref(df, obj)
    assert ref == provenance.source_ref(restored, obj)
    assert ref["scan_sha256"] != ref["quality_sha256"], "zero price treatment differs between the existing readers"
    assert obj["values"][3][1] == float(df["Close"].iloc[1])
    assert scans._bars(restored, -1)._values["Close"][1] == scans._bars(df, -1)._values["Close"][1]
    assert np.isnan(quality._arrays(restored, -1).c[0])
    assert provenance.digest({"x": 1.0, "y": None}) == provenance.digest({"y": None, "x": 1.0})
    assert provenance.digest([1, 2]) != provenance.digest([2, 1])
    assert len({provenance.digest(v) for v in [None, False, 0, 0.0, -0.0]}) == 5
    with pytest.raises(ValueError, match="nonfinite"):
        provenance.digest(float("nan"))


def test_changed_source_archive_fails_without_repair(tmp_path):
    import gzip
    from src import provenance
    d = fixture(); key = d["bursts"][0]["evidence"]["source"]["sha256"]
    obj = json.loads(gzip.decompress((OBJECTS / (key + ".json.gz")).read_bytes()))
    obj["values"][3][-1] += 1.0
    result = provenance.verify(d, objects={key: obj})
    assert any("source object digest" in x for x in result["breaks"]), result


def test_legacy_records_are_explicitly_unknown_and_unchanged(tmp_path):
    from src import provenance
    data = json.loads(gzip.decompress(
        (ROOT / "tests/fixtures/continuity/2026-09-11.json.gz").read_bytes()))
    before = deepcopy(data)
    result = provenance.verify(data)
    assert result["status"] == "PARTIAL" and "legacy" in result["missing"][0]
    assert data == before
    from tools.verify_provenance import archived
    # Retained legacy originals, independent of the rolling public archive.
    for name in ("record.json", "burst-CACI.json", "burst-ROKU.json"):
        (tmp_path / name).write_bytes((ROOT / "tests/fixtures/grading" / name).read_bytes())
    old = archived(tmp_path)
    before = deepcopy(old)
    result = provenance.verify(old)
    assert result["status"] == "PARTIAL" and "legacy" in result["missing"][0]
    assert old == before


def test_new_recovery_snapshot_and_saved_plan_share_identity(market, claude, fake_resend, tmp_path):
    from src import provenance
    from tools.verify_provenance import archived
    rep, data, docs = evening(tmp_path, market)
    assert rep.published, rep.failure
    original_calls = len(claude.calls)
    source = next((docs / "history").glob("*/record.json")).parent
    rec = json.loads((docs / "picks.json").read_bytes())
    recovered = archived(source)
    result = provenance.verify(recovered, rec, docs / "evidence")
    assert result["status"] == "PASS", result
    assert recovered["bursts"][0]["evidence"] == data["bursts"][0]["evidence"]
    assert len(claude.calls) == original_calls, "verification must never call a model"


def test_mismatched_serialized_pick_does_not_replace_previous_files(market, claude, fake_resend, tmp_path, monkeypatch):
    rep, data, docs = evening(tmp_path, market)
    assert rep.published, rep.failure
    before = {n: (docs / n).read_bytes() for n in ("data.json", "picks.json")}
    save = record.save
    def corrupt(rec, target):
        result = save(rec, target)
        written = json.loads(result.read_bytes())
        next(p for p in written["picks"] if p["ticker"] == "AAA")["stop"] -= 0.01
        result.write_text(json.dumps(written))
        return result
    monkeypatch.setattr(record, "save", corrupt)
    rep, _, _ = evening(tmp_path, market)
    assert not rep.published and "picks/data" in rep.failure, rep.failure
    assert before == {n: (docs / n).read_bytes() for n in before}


def test_upstream_seal_catches_changes_before_join(market, claude, fake_resend, tmp_path, monkeypatch):
    read = pipeline.read_charts_and_grade
    def changed(bursts, *args, **kwargs):
        result = read(bursts, *args, **kwargs)
        bursts[0]["discovery"]["measurements"]["gain_pct"] += 0.01
        return result
    monkeypatch.setattr(pipeline, "read_charts_and_grade", changed)
    rep, data, docs = evening(tmp_path, market)
    assert not rep.published and "discovery changed after scan" in rep.failure
    assert data is None and not (docs / "picks.json").exists()


def test_yellow_withholds_a_even_when_mechanical_is_a_plus(market, claude, fake_resend, tmp_path, monkeypatch):
    from src import provenance
    snapshot = pipeline.breadth.snapshot
    def yellow(*args, **kwargs):
        value = snapshot(*args, **kwargs)
        value["regime"].update(verdict="yellow", size_multiplier=0.5)
        return value
    monkeypatch.setattr(pipeline.breadth, "snapshot", yellow)
    from tests.test_reader_authority import finding
    claude.set_payload({"score": 8.3, "grade": "A", "reason": "orderly but imperfect base", "key_risk": "gap", "entry_note": "watch", "findings": [finding()]})
    rep, data, docs = evening(tmp_path, market)
    assert rep.published, rep.failure
    b = data["bursts"][0]
    assert b["grade"] == "A" and b["grade_mechanical"] == "A+"
    assert b["plan"] is None and b["evidence"]["gate"]["reason"] == "regime_gate"
    assert provenance.verify(data, objects=docs / "evidence")["status"] == "PASS"


def test_discovery_contradiction_is_archived_as_fallback(market, claude, fake_alpaca, fake_resend, tmp_path, seed):
    from src import provenance
    from tests.test_pipeline import dollar_day
    fake_alpaca.add_history("AAA", dollar_day(seed, 1, ratio=0.86, gain=2.0))
    claude.set_payload({"score": 3.0, "grade": "skip", "reason": "The gain is below the required 4% burst minimum.", "key_risk": "gap", "entry_note": "pass"})
    rep, data, docs = evening(tmp_path, market)
    assert rep.published, rep.failure
    b = data["bursts"][0]
    assert b["scan"] == "dollar" and b["claude"]["source"] == "fallback"
    assert "DiscoveryConflict" in b["claude"]["error"] and b["claude"]["score"] is None
    assert b["grade"] == b["grade_mechanical"]
    assert provenance.verify(data, objects=docs / "evidence")["status"] == "PASS"


@pytest.mark.parametrize("grade,score", [("B", 7.2), ("C", 5.2), ("skip", 3.2)])
def test_reader_lowering_removes_the_provisional_ticket(grade, score, market, claude, fake_resend, tmp_path):
    from src import provenance
    from tests.test_reader_authority import finding
    claude.set_payload({"score": score, "grade": grade, "reason": "The prior base is visually uneven.",
                        "key_risk": "gap", "entry_note": "watch", "findings": [finding()]})
    rep, data, docs = evening(tmp_path, market)
    assert rep.published, rep.failure
    b = data["bursts"][0]
    assert b["grade_mechanical"] == "A+" and b["grade"] == grade
    assert b["claude"]["returned_grade"] == grade and b["evidence"]["final_grade"] == grade
    assert b["plan"] is None and b["evidence"]["gate"]["reason"] == "quality_grade"
    assert not data["trades"]
    assert provenance.verify(data, objects=docs / "evidence")["status"] == "PASS"


def test_unattempted_reader_never_invents_an_ai_result(market, claude, fake_resend, tmp_path, monkeypatch):
    from src import provenance
    monkeypatch.setattr(pipeline, "MAX_READS", 0)
    rep, data, docs = evening(tmp_path, market)
    assert rep.published, rep.failure
    b = data["bursts"][0]
    assert b["claude"] is None and "reader_input" not in b["evidence"]
    assert b["grade"] == b["grade_mechanical"]
    assert not claude.calls
    assert provenance.verify(data, objects=docs / "evidence")["status"] == "PASS"


def test_identity_repeats_for_identical_evidence_and_changes_with_inputs(market, claude, fake_alpaca, fake_resend, tmp_path):
    rep, first, _ = evening(tmp_path / "one", market)
    assert rep.published, rep.failure
    rep, same, _ = evening(tmp_path / "two", market)
    assert rep.published, rep.failure
    assert first["bursts"][0]["evidence"]["id"] == same["bursts"][0]["evidence"]["id"]
    df = a_changed = qframe(ideal_bars(burst_range_pct=0.25, base_range=0.15, prior_range=0.1))
    df.iloc[-1, df.columns.get_loc("Volume")] += 1000
    fake_alpaca.add_history("AAA", a_changed)
    rep, changed, _ = evening(tmp_path / "three", market)
    assert rep.published, rep.failure
    assert first["bursts"][0]["evidence"]["id"] != changed["bursts"][0]["evidence"]["id"]


def test_rule_version_drift_reports_partial_without_regrading_archive(monkeypatch):
    from src import provenance, quality
    d = fixture(); before = deepcopy(d)
    monkeypatch.setitem(quality.RULES, "quality.min_er", 0.999)
    result = provenance.verify(d, objects=OBJECTS)
    assert result["status"] == "PARTIAL" and "compatible verifier" in result["missing"][0], result
    assert d == before


def test_legacy_pick_migration_preserves_original_fields(tmp_path):
    p = next(p for p in fixture("full-picks")["picks"] if not p.get("evidence_ref"))
    p["historical_extension"] = {"keep": True}
    (tmp_path / "picks.json").write_text(json.dumps({"schema_version": 1, "picks": [p]}))
    loaded = record.load(tmp_path)
    assert loaded["schema_version"] == 2 and loaded["picks"][0] == p
    record.save(loaded, tmp_path)
    reread = json.loads((tmp_path / "picks.json").read_bytes())
    assert reread["picks"][0] == p and "evidence_ref" not in reread["picks"][0]


def test_future_pick_schema_is_preserved_and_refused(tmp_path):
    raw = b'{"schema_version":999,"picks":[]}'
    (tmp_path / "picks.json").write_bytes(raw)
    with pytest.raises(ValueError, match="unsupported picks schema"):
        record.load(tmp_path)
    assert (tmp_path / "picks.json").read_bytes() == raw


@pytest.mark.parametrize("failure", ["expanded", "capacity", "corrupt_existing"])
def test_source_retention_fails_closed_before_replacing_publication(failure, tmp_path, monkeypatch):
    from src import provenance
    d, p = fixture(), fixture("full-picks")
    objects = {}
    import gzip
    for path in OBJECTS.iterdir():
        key = path.name.split('.')[0]
        objects[key] = path.read_bytes() if path.suffix == '.png' else json.loads(gzip.decompress(path.read_bytes()))
    (tmp_path / "data.json").write_bytes(b"previous data")
    (tmp_path / "picks.json").write_bytes(b"previous picks")
    if failure == "expanded":
        huge = {"text": "x" * provenance.MAX_OBJECT_BYTES}
        objects[provenance.digest(huge)] = huge
    elif failure == "capacity":
        monkeypatch.setattr(provenance, "MAX_ARCHIVE_BYTES", 1)
    else:
        destination = tmp_path / provenance.OBJECT_DIR
        destination.mkdir()
        key = d["bursts"][0]["evidence"]["source"]["sha256"]
        (destination / (key + ".json.gz")).write_bytes(gzip.compress(b'{}', mtime=0))
    with pytest.raises(ValueError, match="bound|capacity|digest mismatch"):
        provenance.publish_bundle(d, p, tmp_path, objects)
    assert (tmp_path / "data.json").read_bytes() == b"previous data"
    assert (tmp_path / "picks.json").read_bytes() == b"previous picks"


@pytest.mark.parametrize("binary", [False, True], ids=["json-gzip", "binary"])
def test_object_writes_round_trip_repeat_and_reject_corruption(binary, tmp_path, monkeypatch):
    import hashlib
    from src import provenance
    obj = b"\x89PNG\r\n\x1a\n\x00fixture" if binary else {"text": "café", "values": [None, 1, 1.25]}
    key = hashlib.sha256(obj).hexdigest() if binary else provenance.digest(obj)
    path = tmp_path / (key + (".png" if binary else ".json.gz"))
    provenance.write_objects({key: obj}, tmp_path)
    expected = obj if binary else gzip.compress(json.dumps(
        obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode(), mtime=0)
    assert path.read_bytes() == expected
    assert provenance._object(tmp_path, key, binary) == obj
    assert list(tmp_path.iterdir()) == [path]

    def no_rewrite(**kwargs):
        pytest.fail("a verified existing object must not be rewritten")
    monkeypatch.setattr(provenance.tempfile, "NamedTemporaryFile", no_rewrite)
    provenance.write_objects({key: obj}, tmp_path)
    assert path.read_bytes() == expected
    corrupt = b"changed" if binary else gzip.compress(b'{}', mtime=0)
    path.write_bytes(corrupt)
    with pytest.raises(ValueError, match="digest mismatch"):
        provenance.write_objects({key: obj}, tmp_path)
    assert path.read_bytes() == corrupt


@pytest.mark.parametrize("binary", [False, True], ids=["json-gzip", "binary"])
def test_object_replacement_requires_closed_staging_handle(binary, tmp_path, monkeypatch):
    import hashlib
    from src import provenance
    original_temp, original_replace = provenance.tempfile.NamedTemporaryFile, provenance.os.replace
    handles, installed = [], []
    def track_temp(**kwargs):
        handle = original_temp(**kwargs)
        handles.append(handle)
        return handle
    def replace(source, destination):
        assert handles and all(h.closed for h in handles), "replacement saw an open staging handle"
        installed.append(Path(destination))
        return original_replace(source, destination)
    monkeypatch.setattr(provenance.tempfile, "NamedTemporaryFile", track_temp)
    monkeypatch.setattr(provenance.os, "replace", replace)
    obj = b"binary fixture" if binary else {"text": "normalized evidence"}
    key = hashlib.sha256(obj).hexdigest() if binary else provenance.digest(obj)
    provenance.write_objects({key: obj}, tmp_path)
    assert len(installed) == 1 and provenance._object(tmp_path, key, binary) == obj
    assert all(h.closed and not Path(h.name).exists() for h in handles)


@pytest.mark.parametrize("failure", ["write", "flush", "replace"])
@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_object_failure_closes_before_cleanup_and_preserves_original_error(
        failure, cleanup_fails, tmp_path, monkeypatch):
    from contextlib import contextmanager
    from src import provenance
    original_temp, original_unlink = provenance.tempfile.NamedTemporaryFile, Path.unlink
    original_error = OSError("original " + failure + " failure")
    cleanup_error = PermissionError("secondary cleanup failure")
    handles, cleaned = [], []

    class FaultyFile:
        def __init__(self, handle):
            self.handle, self.name = handle, handle.name
        def write(self, raw):
            self.handle.write(raw[:1] if failure == "write" else raw)
            if failure == "write":
                raise original_error
        def flush(self):
            self.handle.flush()
            if failure == "flush":
                raise original_error

    @contextmanager
    def stage(**kwargs):
        with original_temp(**kwargs) as handle:
            handles.append(handle)
            yield FaultyFile(handle)

    def replace(*args):
        assert failure == "replace" and all(h.closed for h in handles)
        raise original_error

    def unlink(path, *args, **kwargs):
        if handles and path == Path(handles[-1].name):
            assert all(h.closed for h in handles), "cleanup saw an open staging handle"
            cleaned.append(path)
            if cleanup_fails:
                raise cleanup_error
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(provenance.tempfile, "NamedTemporaryFile", stage)
    monkeypatch.setattr(provenance.os, "replace", replace)
    monkeypatch.setattr(Path, "unlink", unlink)
    obj = {"text": "required evidence"}
    key = provenance.digest(obj)
    with pytest.raises(OSError) as caught:
        provenance.write_objects({key: obj}, tmp_path)
    assert caught.value is original_error
    assert len(handles) == len(cleaned) == 1 and handles[0].closed
    assert not (tmp_path / (key + ".json.gz")).exists()
    assert list(tmp_path.iterdir()) == (cleaned if cleanup_fails else [])


def test_staging_creation_failure_is_preserved(tmp_path, monkeypatch):
    from src import provenance
    error = OSError("staging creation failed")
    def fail(**kwargs):
        raise error
    monkeypatch.setattr(provenance.tempfile, "NamedTemporaryFile", fail)
    obj = {"text": "required evidence"}
    with pytest.raises(OSError) as caught:
        provenance.write_objects({provenance.digest(obj): obj}, tmp_path)
    assert caught.value is error and not list(tmp_path.iterdir())


@pytest.mark.parametrize("previous", [False, True], ids=["first-publication", "replacement"])
@pytest.mark.parametrize("failure", ["evidence", "picks.json", "data.json", None],
                         ids=["evidence-failure", "picks-failure", "data-failure", "success"])
def test_real_evidence_writer_preserves_publication_order_and_rollback(
        previous, failure, tmp_path, monkeypatch):
    from src import provenance
    data, picks = fixture(), fixture("full-picks")
    picks.pop("fixture")  # Fixture label is not part of the persisted picks schema.
    objects = {p.name.split('.')[0]: p.read_bytes() if p.suffix == '.png'
               else json.loads(gzip.decompress(p.read_bytes())) for p in OBJECTS.iterdir()}
    old = {name: ("previous " + name).encode() for name in ("data.json", "picks.json")}
    if previous:
        for name, raw in old.items():
            (tmp_path / name).write_bytes(raw)
    original_replace = provenance.os.replace
    installs, failed = [], []
    error = OSError("required installation failed")
    def replace(source, destination):
        destination = Path(destination)
        if destination.parent not in (tmp_path, tmp_path / provenance.OBJECT_DIR):
            return original_replace(source, destination)
        label = "evidence" if destination.parent.name == provenance.OBJECT_DIR else destination.name
        if label in ("picks.json", "data.json"):
            assert provenance.verify(data, picks, tmp_path / provenance.OBJECT_DIR)["status"] == "PASS"
        # Fail after one successful object, exercising partial object installation.
        if label == failure and not failed and (label != "evidence" or installs):
            failed.append(label)
            raise error
        result = original_replace(source, destination)
        installs.append(label)
        return result
    monkeypatch.setattr(provenance.os, "replace", replace)
    if failure:
        with pytest.raises(OSError) as caught:
            provenance.publish_bundle(data, picks, tmp_path, objects)
        assert caught.value is error and failed == [failure]
        for name, raw in old.items():
            assert (tmp_path / name).read_bytes() == raw if previous else not (tmp_path / name).exists()
        if failure == "evidence":
            assert installs == ["evidence"]
    else:
        provenance.publish_bundle(data, picks, tmp_path, objects)
        assert installs[-2:] == ["picks.json", "data.json"]
        assert all(label == "evidence" for label in installs[:-2])
        assert json.loads((tmp_path / "data.json").read_bytes()) == data
        assert json.loads((tmp_path / "picks.json").read_bytes()) == picks
    assert not list(tmp_path.glob(".publication-*"))
    assert all(p.suffix in (".gz", ".png") for p in (tmp_path / provenance.OBJECT_DIR).iterdir())


def test_required_evidence_install_failure_keeps_pipeline_unpublished(
        market, claude, fake_resend, tmp_path, monkeypatch):
    from src import provenance
    original_replace = provenance.os.replace
    attempted = []
    def replace(source, destination):
        if Path(destination).parent.name == provenance.OBJECT_DIR:
            attempted.append(Path(destination))
            raise OSError("required evidence installation failed")
        return original_replace(source, destination)
    monkeypatch.setattr(provenance.os, "replace", replace)
    rep, data, docs = evening(tmp_path, market)
    assert attempted and not rep.published and rep.exit_code() == pipeline.EXIT_FAILED
    assert "required evidence installation failed" in rep.failure
    assert data is None and not (docs / record.PICKS_FILE).exists()
    assert not list((docs / provenance.OBJECT_DIR).iterdir())
