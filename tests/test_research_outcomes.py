"""Frozen cohort evidence, conditional daily models and append-only publication."""
from copy import deepcopy
from datetime import date
import gzip
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest import mock

import pytest
from src import research_outcomes as journal, stop_research as cohort

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/research-outcomes"


def fixture(name="pending"):
    raw = gzip.decompress((FIXTURES / (name + "-publication.json.gz")).read_bytes())
    receipt = (FIXTURES / (name + "-receipt.json")).read_bytes()
    body = (FIXTURES / (name + "-bundle.json")).read_bytes()
    return raw, receipt, body


def parsed(name="pending"):
    _, receipt, body = fixture(name)
    return journal.validate_bundle(receipt, body)


def rows(name="pending"):
    return {r["ticker"]: r for r in parsed(name)["cohorts"][0]["rows"]}


def reseal(bundle):
    body = journal._encode(bundle)
    return journal._receipt_of(body), body


def source_of(bundle):
    return bundle["cohorts"][0]["source"]["raw"].encode()


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("journal_generator", FIXTURES / "generate.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    docs = tmp_path_factory.mktemp("journal-producer")
    raw, source = module.base_source(docs)
    seed = journal.build(raw, cohorts=[source], objects=docs / "evidence", generated_at=module.PENDING_CLOCK)
    return module, docs, raw, source, seed


def test_actual_first_cohort_has_no_future_observations_or_returns():
    bundle = parsed()
    assert bundle["counts"] == {"cohorts":1,"primary_cohorts":1,"rows":5,"eligible":2,
        "by_status": {s:(2 if s == "pending" else 3 if s == "excluded" else 0) for s in journal.STATUSES}}
    assert bundle["cohorts"][0]["source"]["sha256"] == "249b60c01b702eabc05bba17b0160c7664177e34cfdf26e217c5dbbd1db788f0"
    for symbol, shares in (("KE",1),("PSNL",3)):
        row = rows()[symbol]
        assert row["model"]["original_shares"] == shares
        assert (row["model"]["day"], row["model"]["r"], row["model"]["sold_shares"], row["model"]["remaining_shares"]) == (0,None,None,None)
        assert row["model"]["expected_sessions"] == [] and "2026-10-12" in row["model"]["reason"]
        assert row["observation"]["bars"] == []
    assert rows()["ZIM"]["model"]["status"] == "excluded"
    assert rows()["MG"]["model"]["status"] == "excluded"


def test_frozen_hypothetical_shares_not_original_refused_size():
    bundle = parsed(); source = json.loads(source_of(bundle))
    original = {r["ticker"]:r for r in source["rows"]}
    assert original["KE"]["baseline"]["shares"] == 3
    assert original["PSNL"]["baseline"]["shares"] == 6
    assert rows()["KE"]["model"]["original_shares"] == 1
    assert rows()["PSNL"]["model"]["original_shares"] == 3


def test_genuine_observation_models_reconcile_one_whole_share():
    r = rows("observed")
    assert r["COIL"]["model"]["status"] == "resolved"
    assert (r["COIL"]["model"]["sold_shares"], r["COIL"]["model"]["remaining_shares"], r["COIL"]["model"]["r"]) == (1,0,2.26)
    assert r["COIL"]["model"]["events"][0]["event"] == "sell_half"
    assert r["RONE"]["model"]["uncertainty"] == "trigger_timing"
    assert r["RONE"]["model"]["entry"] is None and r["RONE"]["model"]["r"] is None
    assert r["RTHR"]["model"]["status"] == "open" and r["RTHR"]["model"]["remaining_shares"] == 1
    assert r["RTHR"]["model"]["r"] is None


def test_full_ohlc_revision_detected_when_close_is_unchanged():
    first, revision = rows("observed")["COIL"], rows("revised")["COIL"]
    assert first["observation"]["bars"][0]["c"] == revision["observation"]["bars"][0]["c"]
    assert revision["observation"]["changed_dates"] == ["2026-10-12"]
    assert revision["observation"]["revision_of"] == first["observation"]["bars_sha256"]
    assert first["model"]["r"] == 2.26 and revision["model"]["r"] == -1
    assert fixture("observed")[2] != fixture("revised")[2]


def test_missing_entry_cannot_be_replaced_by_later_bar():
    r = rows("missing")
    for symbol in ("COIL","RONE","RTHR"):
        assert r[symbol]["model"]["status"] == "missing"
        assert r[symbol]["model"]["missing_sessions"] == ["2026-10-12"]
        assert r[symbol]["model"]["expected_sessions"] == ["2026-10-12","2026-10-13"]
        assert r[symbol]["model"]["entry"] is None and r[symbol]["model"]["r"] is None


def test_basis_change_remains_distinct_from_loss_or_missing():
    assert [r["model"]["status"] for r in rows("basis-conflict").values()] == ["basis_conflict"] * 3 + ["excluded"] * 2
    assert all(r["model"]["r"] is None for r in rows("basis-conflict").values())


def test_not_filled_and_two_uncertain_sequences_never_score():
    r = rows("not-filled")
    assert r["COIL"]["model"]["status"] == "not_filled"
    assert r["RONE"]["model"]["uncertainty"] == "open_above_limit"
    assert r["RTHR"]["model"]["uncertainty"] == "stop_sequence"
    assert all(row["model"]["r"] is None for row in r.values())


def test_first_actual_before_entry_stays_primary_and_late_revision_remains():
    entries = parsed("cohort-revisions")["cohorts"]
    assert len(entries) == 2 and [e["revision"] for e in entries] == [1,2]
    assert [e["primary"] for e in entries] == [True,False]
    assert [json.loads(e["source"]["raw"])["timing"]["classification"] for e in entries] == ["before_entry","after_entry"]
    assert all(r["model"]["status"] in {"pending","excluded"} for e in entries for r in e["rows"])


@pytest.mark.parametrize("name", ["empty","red"])
def test_empty_and_refused_denominators_survive(name):
    bundle = parsed(name)
    assert bundle["counts"]["cohorts"] == 1
    assert bundle["counts"]["eligible"] == 0
    assert sum(bundle["counts"]["by_status"].values()) == bundle["counts"]["rows"]
    assert bundle["counts"]["rows"] == (0 if name == "empty" else 5)


def test_origin_unavailable_does_not_infer_basis_from_current_publication(generated):
    module, docs, raw, source, seed = generated
    follow, clock = module.follow_source(docs, raw, "observed")
    missing = journal.build(follow, cohorts=[source], objects=docs / "evidence", generated_at=clock)
    assert missing["receipt"]["counts"]["by_status"]["origin_unavailable"] == 3
    with_origin = journal.build(follow, cohorts=[source], objects=docs / "evidence", publications=lambda sha: raw, generated_at=clock)
    assert with_origin["receipt"]["counts"]["by_status"]["resolved"] == 1


def test_exact_actual_source_replay_and_no_mutation():
    raw, receipt, body = fixture()
    before = journal._sha(raw)
    journal.validate_for_publication(raw, receipt, body, cohorts=[source_of(parsed())], objects=ROOT / "docs/evidence")
    assert journal._sha(raw) == before


def test_unrelated_rules_do_not_change_supported_replay_subset():
    data = json.loads(fixture()[0])
    assert journal._supported(data)
    data["rules"]["burst"]["unrelated_display_count"] = 100
    data["rules"]["plan"]["max_stop_pct"] = 9
    assert journal._supported(data)
    data["rules"]["plan"]["sell_half_pct"] = 12
    assert not journal._supported(data)


def model_parts(name="observed", symbol="COIL"):
    entry = parsed(name)["cohorts"][0]; source = json.loads(entry["source"]["raw"])
    original = next(r for r in source["rows"] if r["ticker"] == symbol)
    observed = next(r for r in entry["rows"] if r["ticker"] == symbol)
    return source, original, deepcopy(observed["observation"])


def test_conclusive_earlier_exit_survives_later_hole_but_open_model_does_not():
    for symbol, expected in (("COIL","resolved"),("RTHR","missing")):
        source, row, obs = model_parts(symbol=symbol)
        model = journal._model(source,row,obs,["2026-10-12","2026-10-13"])
        assert model["status"] == expected
        assert model["missing_sessions"] == ["2026-10-13"]
        assert (model["r"] is not None) == (expected == "resolved")


def test_three_share_exits_reconcile_no_phantom_half():
    source, row, obs = model_parts()
    row["research"]["shares"] = 3
    first = journal._model(source,row,obs,["2026-10-12"])
    assert first["sold_shares"] == 2 and first["remaining_shares"] == 1 and first["r"] is None
    obs["bars"].append({"date":"2026-10-13","o":59,"h":59.5,"l":58,"c":59,"v":1000,"from_session":"2026-10-13"})
    last = journal._model(source,row,obs,["2026-10-12","2026-10-13"])
    assert last["status"] == "resolved" and last["sold_shares"] == 3 and last["remaining_shares"] == 0
    assert sum(e.get("shares",0) for e in last["events"]) == 3


def test_actual_frozen_research_quantity_drives_conditional_walk():
    source, row, obs = model_parts("pending", "KE")
    obs["bars"] = [{"date":"2026-10-12","o":29.23,"h":33,"l":29,"c":32,"v":1000,"from_session":"2026-10-12"}]
    modeled = journal._model(source,row,obs,["2026-10-12"])
    assert row["baseline"]["shares"] == 3
    assert modeled["status"] == "resolved" and modeled["sold_shares"] == 1 and modeled["remaining_shares"] == 0


@pytest.mark.parametrize("name", ["observed","revised","missing","not-filled"])
def test_actual_replay_helper_reproduces_each_captured_model(name):
    entry = parsed(name)["cohorts"][0]; source = json.loads(entry["source"]["raw"])
    for row, original in zip(entry["rows"], source["rows"]):
        if not original["research"]["allocation_fit"]: continue
        assert journal._model(source,original,row["observation"],row["model"]["expected_sessions"]) == row["model"]


def test_full_bar_comparison_ignores_legacy_close_only_revision_flag():
    old = parsed("observed")["cohorts"][0]; current = parsed("revised")
    source, original, obs = model_parts()
    revised, problem, _ = journal._observe(json.loads(fixture("revised")[0]),current["publication"],original,old["origin"],["2026-10-12"],obs)
    assert problem is None and revised["changed_dates"] == ["2026-10-12"]
    assert revised["revision_of"] == obs["bars_sha256"]


def test_retained_clip_keeps_old_basis_and_publication_after_history_expires():
    bundle = parsed("observed"); entry = bundle["cohorts"][0]
    source, row, obs = model_parts()
    data = json.loads(fixture("observed")[0]); data["observations"]["symbols"].pop("COIL")
    binding = deepcopy(bundle["publication"]); binding["measured_session"] = "2026-11-01"
    carried, problem, _ = journal._observe(data,binding,row,entry["origin"],["2026-10-12","2026-10-13"],obs)
    assert problem is None and carried["carried"] is True
    assert carried["publication"] == obs["publication"] and carried["bars"] == obs["bars"]
    assert journal._model(source,row,carried,["2026-10-12","2026-10-13"])["status"] == "resolved"
    data["run"]["input_basis"]["adjustment"] = "raw"
    assert journal._observe(data,binding,row,entry["origin"],["2026-10-12"],obs)[1] == "basis_conflict"


def test_partial_later_history_preserves_conclusive_dated_clip_but_not_revisions():
    old = parsed("observed")["cohorts"][0]; current = parsed("missing")
    source, original, prior = model_parts()
    data = json.loads(fixture("missing")[0])
    horizon = ["2026-10-12","2026-10-13"]
    carried, problem, _ = journal._observe(data,current["publication"],original,old["origin"],horizon,prior)
    assert problem is None and carried["carried"] and carried["publication"] == prior["publication"]
    assert journal._model(source,original,carried,horizon)["r"] == 2.26
    revised_data = json.loads(fixture("revised")[0]); revised_bundle = parsed("revised")
    fresh, problem, _ = journal._observe(revised_data,revised_bundle["publication"],original,old["origin"],horizon,prior)
    assert problem is None and not fresh["carried"]
    assert journal._model(source,original,fresh,["2026-10-12"])["r"] == -1


def test_missing_source_cohort_cannot_silently_shrink_prior_population(generated):
    module,docs,raw,source,seed = generated
    with pytest.raises(ValueError, match="previously retained cohort"):
        journal.build(raw,cohorts=[],objects=docs/"evidence",previous=(seed["receipt_bytes"],seed["bundle_bytes"]),generated_at=module.PENDING_CLOCK)


def test_fresh_anchor_revision_and_unknown_mixed_history_refuse():
    bundle = parsed("observed"); entry = bundle["cohorts"][0]
    _, row, obs = model_parts(); data = json.loads(fixture("observed")[0])
    history = data["observations"]["symbols"]["COIL"]["history"]
    anchor = next(b for b in history if b["date"] == "2026-10-09")
    anchor["c"] += .1
    assert journal._observe(data,bundle["publication"],row,entry["origin"],["2026-10-12"],obs)[1] == "basis_conflict"
    anchor["c"] -= .1; anchor["from_session"] = "2026-10-09"
    history[-1]["h"] += 1
    assert journal._observe(data,bundle["publication"],row,entry["origin"],["2026-10-12"],obs)[1] == "basis_conflict"


def test_historical_revisit_never_borrows_future_bar_evidence():
    future = parsed("observed")["cohorts"][0]
    prior = next(r for r in future["rows"] if r["ticker"] == "COIL")["observation"]
    earlier = parsed("synthetic-pending")
    original = json.loads(future["source"]["raw"])["rows"][0]
    data = json.loads(fixture("synthetic-pending")[0])
    observed, problem, _ = journal._observe(data,earlier["publication"],original,future["origin"],["2026-10-12"],prior)
    assert problem is None and observed["bars"] == [] and not observed["carried"]
    assert observed["publication"] == earlier["publication"]


def test_raw_anchor_precision_uses_exact_public_series_normalization():
    from src import pipeline
    bundle = parsed("observed"); entry = bundle["cohorts"][0]
    _, row, obs = model_parts(); data = json.loads(fixture("observed")[0])
    origin = deepcopy(entry["origin"])
    anchor = origin["anchors"][row["evidence"]["id"]]
    anchor["close"] = 55.00001234
    public_anchor = next(b for b in data["observations"]["symbols"]["COIL"]["history"] if b["date"] == anchor["date"])
    public_anchor["c"] = pipeline._num(anchor["close"])
    observed, problem, _ = journal._observe(data,bundle["publication"],row,origin,["2026-10-12"],None)
    assert problem is None and observed["anchor"]["close"] == 55.00001234
    assert public_anchor["c"] == 55.0 and journal.POLICY["observation_price_decimals"] == 4
    public_anchor["c"] = 55.0001
    assert journal._observe(data,bundle["publication"],row,origin,["2026-10-12"],None)[1] == "basis_conflict"


@pytest.mark.parametrize("change", ["quantity","r","pending_r","source","primary","basis","reader","event","bar","counts","unknown","path"])
def test_resealed_invalid_transport_does_not_gain_trust(change):
    bundle = parsed("observed")
    row = bundle["cohorts"][0]["rows"][0]
    if change == "quantity": row["model"]["original_shares"] += 1
    if change == "r": row["model"]["r"] += 1
    if change == "pending_r": row["model"]["status"] = "pending"
    if change == "source": bundle["cohorts"][0]["source"]["raw"] += " "
    if change == "primary": bundle["cohorts"][0]["primary"] = False
    if change == "basis": row["observation"]["basis"]["adjustment"] = "raw"
    if change == "reader": row["observation"]["publication"]["reader_sha256"] = "0" * 64
    if change == "event": row["model"]["events"][0]["shares"] = 2
    if change == "bar": row["observation"]["bars"][0]["h"] += 1
    if change == "counts": bundle["counts"]["eligible"] += 1
    if change == "unknown": row["model"]["order"] = "not allowed"
    receipt, body = reseal(bundle)
    if change == "path":
        receipt = json.loads(receipt); receipt["bundle"]["path"] = "../elsewhere.json"; receipt = journal._encode(receipt)
    with pytest.raises(ValueError): journal.validate_bundle(receipt,body)


def test_duplicate_nonfinite_and_oversized_json_refused():
    for raw in (b'{"schema_version":1,"schema_version":1}', b'{"x":NaN}', b' ' * (journal.MAX_RECEIPT_BYTES + 1)):
        with pytest.raises(ValueError): journal.parse_receipt(raw)


@pytest.mark.parametrize("field,value", [("missing_sessions",[]),("sessions",2)])
def test_missing_coverage_cannot_be_resealed_as_observed(field,value):
    bundle = parsed("missing")
    bundle["cohorts"][0]["rows"][0]["model"][field] = value
    with pytest.raises(ValueError, match="missing sessions differ|sessions exceed"):
        journal.validate_bundle(*reseal(bundle))


def test_stdlib_only_validator():
    code = "import sys;sys.path.insert(0,sys.argv[1]);from src import research_outcomes as j;from pathlib import Path;p=Path(sys.argv[2]);j.validate_bundle((p/'pending-receipt.json').read_bytes(),(p/'pending-bundle.json').read_bytes())"
    subprocess.run([sys.executable,"-I","-S","-c",code,str(ROOT),str(FIXTURES)],check=True)


def install_sources(docs, source):
    parsed = json.loads(source); sha = journal._sha(source)
    directory = docs / "stop-research"; directory.mkdir(exist_ok=True)
    (directory / (sha + ".json")).write_bytes(source)
    index = {"schema_version":1,"policy_id":cohort.POLICY_ID,"objects":[{"sha256":sha,"bytes":len(source),"publication_sha256":parsed["publication"]["data_sha256"],"applicable_session":parsed["publication"]["applicable_session"],"generated_at":parsed["timing"]["generated_at"]}]}
    (directory / "index.json").write_bytes(journal._encode(index))


def test_writer_preserves_first_capture_on_repeat_revisit_and_revised_bytes(generated, tmp_path):
    module, _, raw, source, seed = generated
    objects = generated[1] / "evidence"
    install_sources(tmp_path,source)
    first = journal.write_publication(raw,tmp_path,objects=objects,generated_at=module.PENDING_CLOCK)
    before = {p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    second = journal.write_publication(raw,tmp_path,objects=objects,generated_at="2026-10-12T15:00:00+00:00")
    assert first == second and before == {p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    # Independent observation publication creates a different immutable snapshot.
    follow, clock = module.follow_source(generated[1],raw,"observed")
    next_receipt = journal.write_publication(follow,tmp_path,objects=objects,generated_at=clock)
    assert next_receipt["bundle"]["sha256"] != first["bundle"]["sha256"]
    assert (tmp_path / first["bundle"]["path"]).read_bytes() == before[Path(first["bundle"]["path"])]
    revisit = journal.write_publication(raw,tmp_path,objects=objects,generated_at=clock)
    assert revisit == first
    assert len(json.loads((tmp_path / journal.INDEX_FILE).read_bytes())["objects"]) == 2


def test_cached_revisit_checks_deadline_before_replacing_receipt(generated,tmp_path,monkeypatch):
    import inspect
    module,docs,raw,source,_ = generated
    install_sources(tmp_path,source)
    journal.write_publication(raw,tmp_path,objects=docs/"evidence",generated_at=module.PENDING_CLOCK)
    elapsed = [0.0]; original = journal._cohort_raw
    def slow_source_sort(raw):
        result = original(raw)
        if inspect.currentframe().f_back.f_code.co_name == "<lambda>": elapsed[0] = journal.MAX_PROCESS_SECONDS + 1
        return result
    monkeypatch.setattr(journal.time,"monotonic",lambda:elapsed[0])
    monkeypatch.setattr(journal,"_cohort_raw",slow_source_sort)
    before = {p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with mock.patch.object(cohort,"_atomic",side_effect=AssertionError("late write")), pytest.raises(ValueError,match="deadline"):
        journal.write_publication(raw,tmp_path,objects=docs/"evidence",generated_at=module.PENDING_CLOCK)
    assert before == {p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("problem", ["symlink","unknown","capacity","orphan","clock"])
def test_writer_refusal_preserves_every_existing_byte(generated,tmp_path,monkeypatch,problem):
    module, docs, raw, source, _ = generated
    install_sources(tmp_path,source)
    if problem == "symlink": (tmp_path / journal.BUNDLE_DIR).symlink_to(docs, target_is_directory=True)
    elif problem == "unknown":
        (tmp_path / journal.BUNDLE_DIR).mkdir(); (tmp_path / journal.BUNDLE_DIR / "unknown.txt").write_text("keep")
    elif problem == "capacity": monkeypatch.setattr(journal,"MAX_SNAPSHOTS",0)
    elif problem == "orphan":
        (tmp_path / journal.BUNDLE_DIR).mkdir(); (tmp_path / journal.BUNDLE_DIR / ("0"*64+".json")).write_bytes(b" "+b"0" * journal.MAX_BUNDLE_BYTES)
    elif problem == "clock": monkeypatch.setattr(journal,"MAX_PROCESS_SECONDS",0)
    before = {p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file() and not p.is_symlink()}
    with pytest.raises(ValueError): journal.write_publication(raw,tmp_path,objects=docs/"evidence",generated_at=module.PENDING_CLOCK)
    assert before == {p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file() and not p.is_symlink()}


@pytest.mark.parametrize("clock", ["",0,False,"2026-10-10T00:00:00"])
def test_invalid_explicit_clocks_refused(generated,clock):
    _,docs,raw,source,_ = generated
    with pytest.raises((ValueError,TypeError)):
        journal.build(raw,cohorts=[source],objects=docs/"evidence",generated_at=clock)
