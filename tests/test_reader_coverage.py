"""Synthetic coverage/regime controls and real offline pipeline integration."""
from collections import Counter
from copy import deepcopy
import json
import re

import pytest

from src import pipeline, plan, reader_coverage, report
from tests.test_pipeline import market, claude, evening, a_plus_frame
from tests.test_reader_coverage_retained import retained, replay


@pytest.mark.parametrize("verdict,grade,permitted", [
    ("green", "A+", True), ("green", "A", True), ("green", "B", False),
    ("yellow", "A+", True), ("yellow", "A", False), ("red", "A+", False)])
@pytest.mark.parametrize("source", ["claude", "fallback", "not_graded", None, "unrecognized"])
def test_synthetic_reader_states_and_market_permission_are_separate(verdict, grade, permitted, source):
    row = deepcopy(next(b for b in retained()["bursts"] if b["ticker"] == "OPY"))
    row["grade"] = row["grade_mechanical"] = grade  # explicitly synthetic grade controls
    row["claude"] = {"source": source, "grade": grade, "error": None} if source else None
    row["reader_coverage"] = reader_coverage.state(row)
    trades, _, _ = pipeline.make_plans([row], {}, plan.Account(),
        {"verdict": verdict, "size_multiplier": 0 if verdict == "red" else 0.5 if verdict == "yellow" else 1}, 0)
    expected = permitted and source == "claude"
    assert bool(row["plan"]) is expected
    assert (row["ticker"] in trades) is expected
    assert row["grade"] == grade


@pytest.mark.parametrize("reader", [None, {"source": "fallback"},
    {"source": "claude", "grade": None}, {"source": "claude", "grade": "A", "error": "unavailable"},
    {"source": "claude", "grade": "B"}])
def test_a_coverage_label_alone_cannot_grant_permission(reader):
    row = next(b for b in retained()["bursts"] if b["ticker"] == "NDSN")
    row.update(claude=reader, reader_coverage="accepted")
    trades, _, _ = pipeline.make_plans([row], {}, plan.Account(), {"verdict": "green"}, 0)
    assert row["plan"] is None and trades == []


def test_pipeline_records_budget_coverage_and_keeps_reader_chart_stops(market, claude, fake_alpaca,
        fake_resend, tmp_path, monkeypatch):
    # 13 identical mechanical A+ inputs, 12 scripted accepted replies. No API.
    symbols = ["AAA"] + [f"A{chr(66 + i)}A" for i in range(12)]
    for ticker in symbols:
        fake_alpaca.add_history(ticker, a_plus_frame())
    stops = {}
    def chart(ticker, frame, *args, **kwargs):
        stops[ticker] = kwargs.get("stop")
        return None
    monkeypatch.setattr(pipeline.charts, "render_chart", chart)
    rep, data, docs = evening(tmp_path, market + symbols[1:])
    assert rep.published, rep.failure
    assert len(claude.calls) == 12
    rows = {b["ticker"]: b for b in data["bursts"]}
    assert set(rows) == set(symbols)
    assert Counter(b["reader_coverage"] for b in rows.values()) == {"accepted": 12, "not_selected_budget": 1}
    skipped = rows[symbols[-1]]
    assert skipped["claude"] is None and skipped["grade"] == skipped["grade_mechanical"] == "A+"
    assert skipped["plan"] is None and skipped["ticker"] not in data["trades"]
    assert skipped["evidence"]["gate"]["reason"] == "reader_coverage"
    assert skipped["evidence"]["reader_coverage"] == "not_selected_budget"
    for ticker, stop in stops.items():
        assert stop == rows[ticker]["plan"]["stop"], "pre-review chart input changed"
    picks = json.loads((docs / "picks.json").read_text())["picks"]
    assert skipped["ticker"] not in {p["ticker"] for p in picks}


def test_coverage_receipt_cannot_be_changed_after_grading(market, claude, fake_resend, tmp_path, monkeypatch):
    read = pipeline.read_charts_and_grade
    def changed(bursts, *args, **kwargs):
        result = read(bursts, *args, **kwargs)
        bursts[0]["reader_coverage"] = "not_selected_budget"
        return result
    monkeypatch.setattr(pipeline, "read_charts_and_grade", changed)
    rep, data, _ = evening(tmp_path, market)
    assert not rep.published and data is None
    assert "reader coverage changed after grading" in rep.failure


def test_publication_refuses_a_preview_plan_that_bypasses_final_coverage(market, claude, fake_resend, tmp_path, monkeypatch):
    claude.set_error(RuntimeError("scripted unavailable reader"))
    def bypass(bursts, frames, account, regime, open_count, session=None):
        return pipeline._make_plans(bursts, account, regime, open_count, session, require_reader=False)
    monkeypatch.setattr(pipeline, "make_plans", bypass)
    rep, data, docs = evening(tmp_path, market)
    assert not rep.published and data is None
    assert "plan requires accepted reader review" in rep.failure
    assert not (docs / "picks.json").exists()


@pytest.mark.parametrize("verdict", ["green", "yellow", "red"])
def test_cover_never_calls_missing_reader_coverage_bad_quality(verdict):
    data, (trades, _, _) = replay(verdict)
    for row in data["bursts"]:
        row["reader_coverage"] = reader_coverage.state(row, selected=row["claude"] is not None)
    data["breadth"]["regime"]["verdict"] = verdict
    veev = next(b for b in data["bursts"] if b["ticker"] == "VEEV")
    assert "accepted reader review missing" in report.miss_reason(veev)
    cover = report.cover(data["run"], data["breadth"], trades, data["bursts"], None)
    if verdict == "red":
        assert cover == retained()["cover"]
    else:
        assert cover["h1"] == "No new burst tickets. Reader review incomplete."
        assert "7 with mechanical A+/A grades lack accepted reader review" in cover["dek"]
        assert "not a measured setup failure" in cover["dek"]
        assert "none A-quality" not in cover["dek"]


# ----------------------------------------------------- the night's reads ---
# The chart reader's shortfall counted by cause. A refusal by reader authority
# (the reply arrived; its answer broke the contract) keeps the checklist's
# grade and earns no ticket either way; within a quarter of the night's reads,
# with every other read accepted and no refused name one the regime would have
# planned, it is counted and is not a run problem. Everything else degrades.
from src import grader, reader_authority, universe  # noqa: E402

CREDIT = ("Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': "
          "'Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade "
          "or purchase credits.'}, 'request_id': 'req_011Cfn1utEjKSsuBrit8LD3V'}")   # 6 Oct 2026, verbatim


@pytest.mark.parametrize("error,cause", [
    (reader_authority.ReaderAuthorityError("findings cite a status the record does not carry"), "refused"),
    (grader.DiscoveryConflict("the reply applied a 4% gate to a dollar-only candidate"), "refused"),
    (grader.ScoreFormatError("no scoreable JSON object in 812 characters of reply"), "format"),
    (RuntimeError("Error code: 401 - invalid x-api-key"), "account"),
    (RuntimeError(CREDIT), "credit"),
    (RuntimeError("upstream connect error"), "transport"),
    (RuntimeError("Error code: 400 - image exceeds 5 MB maximum"), "transport"),
])
def test_failure_of_spells_the_real_classes(error, cause):
    assert reader_coverage.failure_of(grader._error_text(error)) == cause
    assert reader_coverage.failure_of(None) == "transport", "an error this does not know degrades: it fails safe"


def scripted(monkeypatch, script):
    """The Anthropic double, answering per ticker: 'ok' an accepted A+ reading,
    'refuse' a reading reader authority refuses, else the exception to raise."""
    from tests.fakes import FakeMessage, FakeTextBlock, billed_usage
    from tests.test_reader_authority import finding
    from tools.make_fixture import CLAUDE, _metrics_of
    calls = []

    class Messages:
        def create(self, **kwargs):
            calls.append(kwargs)
            metrics = _metrics_of(kwargs)
            how = script.get(metrics.get("ticker"), "ok")
            if isinstance(how, Exception):
                raise how
            if how == "refuse":
                status = metrics["reader_evidence"]["checks"]["C"]["status"]
                wrong = next(s for s in ("PASS", "FAIL", "PARTIAL") if s != status)
                reply = {**CLAUDE["C"], "findings": [finding(evidence=[{"path": "checks.C.status", "value": wrong}])]}
            else:
                reply = {**CLAUDE["A+"], "findings": []}
            return FakeMessage(content=[FakeTextBlock(text=json.dumps(reply))], usage=billed_usage(kwargs, calls, 1000))

    class Client:
        def __init__(self, *args, **kwargs):
            self.messages = Messages()
    monkeypatch.setattr("anthropic.Anthropic", Client)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    return calls


def four_reads(tmp_path, monkeypatch, script, admitted):
    frames = {t: a_plus_frame() for t in ("AAA", "BBB", "CCC", "DDD")}
    rows, _, _ = pipeline.scan_frames(frames, universe.build(None, explicit=list(frames)), pipeline.RunReport())
    assert [(r["ticker"], r["grade_mechanical"], r["vetoes"]) for r in rows] == \
        [(t, "A+", []) for t in frames], "four admissible A+ bursts, or the case tests something else"
    calls = scripted(monkeypatch, script)
    rep = pipeline.RunReport()
    reads = pipeline.read_charts_and_grade(rows, frames, rep, tmp_path, pipeline.grader_prompt(), False,
                                           admitted=admitted)
    return reads, [p["kind"] for p in rep.problems], calls, {r["ticker"]: r for r in rows}


@pytest.mark.parametrize("script,verdict,causes,problems", [
    ({}, "complete", {}, []),
    ({"BBB": "refuse"}, "tolerated", {"refused": 1}, []),                  # 1 of 4: the limit, floor(4/4)
    ({"BBB": "refuse", "CCC": "refuse"}, "partial", {"refused": 2}, ["claude_partial"]),
    ({"BBB": RuntimeError("upstream connect error")}, "partial", {"transport": 1}, ["claude_partial"]),
    ({"BBB": "refuse", "CCC": RuntimeError("upstream connect error")}, "partial",
     {"refused": 1, "transport": 1}, ["claude_partial"]),
    ({t: "refuse" for t in ("AAA", "BBB", "CCC", "DDD")}, "unavailable", {"refused": 4}, ["claude_unavailable"]),
], ids=["all-accepted", "one-refused", "two-refused", "one-unanswered", "refused-and-unanswered", "all-refused"])
def test_refusals_within_the_limit_are_counted_not_problems(tmp_path, monkeypatch, script, verdict, causes, problems):
    reads, kinds, _, rows = four_reads(tmp_path, monkeypatch, script, admitted=())
    assert reads["verdict"] == verdict and kinds == problems, (reads, kinds)
    assert {k: v for k, v in reads["causes"].items() if v} == causes
    assert reads["refusal_limit"] == 1 and reads["requested"] == 4 and reads["done"] == 4 - sum(causes.values())
    assert reads["sentence"] == reader_coverage.reads_sentence(reads)
    for ticker, how in script.items():
        row = rows[ticker]
        assert row["grade"] == row["grade_mechanical"] and row["reader_coverage"] == "fallback", row["claude"]
    assert reads["refused_names"] == sorted(t for t, how in script.items() if how == "refuse")
    if verdict == "tolerated":
        assert reads["sentence"] == ("Chart reader: 3 of 4 judgements accepted. 1 reply (BBB) refused by reader "
                                     "authority or the discovery contract, within this run's tolerance of 1; that "
                                     "name stays research only, without a ticket.")
    elif reads["causes"]["refused"]:
        assert "within this run's tolerance" not in reads["sentence"], reads["sentence"]


def test_an_empty_credit_balance_stops_the_calls_and_says_so(tmp_path, monkeypatch):
    reads, kinds, calls, _ = four_reads(tmp_path, monkeypatch, {t: RuntimeError(CREDIT) for t in "AAA BBB CCC DDD".split()},
                                        admitted=())
    assert len(calls) == 1, "an empty balance answers every call the same way: one call, not eight"
    assert (reads["verdict"], reads["causes"]["credit"], kinds) == ("unavailable", 4, ["claude_unavailable"])
    assert "Top up the Anthropic account before the next run." in reads["sentence"]
    # the problem's own sentence already says every grade is the checklist's; the reads do not say it twice
    assert "checklist's alone" not in reads["sentence"]


def test_a_refusal_that_cost_a_ticket_degrades(tmp_path, monkeypatch):
    reads, kinds, _, _ = four_reads(tmp_path, monkeypatch, {"BBB": "refuse"}, admitted=tuple(pipeline.TRADE_GRADES))
    assert (reads["verdict"], reads["refused_admissible"], kinds) == ("partial", ["BBB"], ["claude_partial"])
    assert "BBB would otherwise have been planned" in reads["sentence"]
    assert "within this run's tolerance" not in reads["sentence"], "a refusal the tolerance did not cover is not 'within' it"
    reads, kinds, _, _ = four_reads(tmp_path, monkeypatch, {"BBB": "refuse"}, admitted=None)
    assert reads["refused_admissible"] == ["BBB"], "None admits every grade"


@pytest.mark.parametrize("vetoes,admissible,verdict", [([], ["T0"], "partial"), (["up_days"], [], "tolerated")])
def test_a_refused_name_a_veto_already_refuses_cost_no_ticket(vetoes, admissible, verdict):
    """The planner refuses a vetoed burst whatever its grade, so its refused
    reading cost no ticket: the same rule, one place each side."""
    rows = [{"ticker": "T0", "grade": "A+", "vetoes": vetoes,
             "claude": {"source": "fallback", "error": "src.ReaderAuthorityError: refused"}}]
    rows += [{"ticker": f"T{i}", "grade": "B", "vetoes": [], "claude": {"source": "claude"}} for i in range(1, 4)]
    reads = reader_coverage.reads(rows, admitted_grades=tuple(pipeline.TRADE_GRADES), refusal_fraction=0.25)
    assert (reads["refused_admissible"], reads["verdict"]) == (admissible, verdict), reads


@pytest.mark.parametrize("fraction,refused,requested,verdict", [
    (1.0, 4, 4, "unavailable"),   # nothing accepted is never tolerated, whatever the limit
    (1.0, 3, 4, "tolerated"), (0.25, 1, 3, "partial"), (0, 1, 4, "partial"), (0.25, 3, 12, "tolerated"),
    (0.25, 4, 12, "partial")])
def test_reads_verdict_by_counts(fraction, refused, requested, verdict):
    rows = [{"ticker": f"T{i}", "grade": "B", "vetoes": [],
             "claude": {"source": "fallback", "error": "src.ReaderAuthorityError: refused"} if i < refused
             else {"source": "claude"}} for i in range(requested)]
    reads = reader_coverage.reads(rows, admitted_grades=(), refusal_fraction=fraction)
    assert reads["verdict"] == verdict, reads


def test_admitted_grades_is_one_rule_for_planning_and_the_reader(market, claude, fake_resend, tmp_path, monkeypatch):
    assert pipeline.admitted_grades("green") == tuple(pipeline.TRADE_GRADES)
    assert pipeline.admitted_grades("yellow") == tuple(pipeline.YELLOW_GRADES)
    assert pipeline.admitted_grades("red") == ()
    rep, data, _ = evening(tmp_path / "shipped", market)
    assert data["trades"] == ["AAA"], rep.problems
    # one rule moves the planner and the reads together
    monkeypatch.setattr(reader_coverage, "admitted", lambda verdict, trade, yellow: ())
    assert pipeline.admitted_grades("green") == ()
    rep, data, _ = evening(tmp_path / "moved", market)
    assert data["trades"] == [] and data["bursts"][0]["plan"] is None
    report.validate(data)


@pytest.mark.parametrize("moved,admissible", [(False, ["AAA"]), (True, [])], ids=["shipped", "moved"])
def test_the_evening_hands_the_reads_the_same_rule_as_the_planner(market, claude, fake_resend, tmp_path,
                                                                  monkeypatch, moved, admissible):
    """The reader half of the one rule: a refused A+ on the evening's own regime
    is one the planner would have planned, and it stops being one exactly when
    the rule moves -- so the evening cannot hand the reads a rule of its own."""
    scripted(monkeypatch, {"AAA": "refuse"})
    if moved:
        monkeypatch.setattr(reader_coverage, "admitted", lambda verdict, trade, yellow: ())
    rep, data, _ = evening(tmp_path, market)
    reads = data["run"]["reads"]
    assert reads["refused_names"] == ["AAA"] and reads["refused_admissible"] == admissible, reads
    assert data["bursts"][0]["grade_mechanical"] == "A+" and data["breadth"]["regime"]["verdict"] == "green"
    report.validate(data)


def test_validate_refuses_forged_reads(market, claude, fake_resend, tmp_path):
    rep, data, _ = evening(tmp_path, market)
    report.validate(data)
    # each forge names the one check it is for: a forge another check also
    # refuses would pass with its own check deleted
    cases = {
        "a cause count": (lambda r: r["run"]["reads"]["causes"].update(refused=1),
                          "run.reads counts do not reconcile"),
        "the limit": (lambda r: r["run"]["reads"].update(refusal_limit=3),
                      "run.reads refusal limit is not the archived reader_refusal_fraction"),
        "the verdict": (lambda r: r["run"]["reads"].update(verdict="tolerated"),
                        "run.reads verdict does not re-derive from its counts"),
        "the sentence": (lambda r: r["run"]["reads"].update(sentence="All read."),
                         "run.reads sentence is not its own"),
        "the refused names": (lambda r: r["run"]["reads"].update(refused_names=["AAA"]),
                              "run.reads refused names are not its refusals"),
        "the bursts' own causes": (lambda r: (r["run"]["reads"].update(
            done=0, causes=dict(r["run"]["reads"]["causes"], transport=1), verdict="unavailable",
            sentence=reader_coverage.reads_sentence(dict(r["run"]["reads"], done=0, verdict="unavailable",
                causes=dict(r["run"]["reads"]["causes"], transport=1)))),
            r["run"]["problems"].append({"stage": "grade", "kind": "claude_unavailable", "message": "forged"})),
            "run.reads is not the bursts' own"),
        "the block": (lambda r: r["run"].pop("reads"), "run.reads is missing"),
    }
    for name, (forge, message) in cases.items():
        forged = json.loads(json.dumps(data))
        forge(forged)
        with pytest.raises(ValueError, match=re.escape(message)):
            report.validate(forged)
