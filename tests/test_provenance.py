"""Publication contradictions must fail before replacing either public record.

The initial eight protections were executed against f744b88 before the fix:
all eight failed because the contradictory night still published.
"""
from copy import deepcopy
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


def test_legacy_records_are_explicitly_unknown_and_unchanged():
    from src import provenance
    data = json.loads((ROOT / "docs/data.json").read_bytes())
    before = deepcopy(data)
    result = provenance.verify(data)
    assert result["status"] == "PARTIAL" and "legacy" in result["missing"][0]
    assert data == before
    from tools.verify_provenance import archived
    old = next(p.parent for p in (ROOT / "docs/history").glob("*/record.json"))
    assert provenance.verify(archived(old))["status"] == "PARTIAL"


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
    claude.set_payload({"score": 8.3, "grade": "A", "reason": "orderly but imperfect base", "key_risk": "gap", "entry_note": "watch"})
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
    claude.set_payload({"score": score, "grade": grade, "reason": "The prior base is visually uneven.",
                        "key_risk": "gap", "entry_note": "watch"})
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
