"""The archive: docs/data.json, docs/ledger.json, and the forward returns.

Two kinds of test live here.

`contract_violations()` is an INDEPENDENT reading of docs/data.json's own
`_contract` block. It recomputes every invariant from the file — it never asks
src.ledger whether src.ledger got it right — and returns the names of the ones
that do not hold. tests/test_pipeline.py runs it against the file a real
pipeline.run() produced.

A checker nobody can see fail is worth nothing, so the tests under "the checker
can fail" doctor exactly one invariant in a known-good document and assert that
the checker names exactly that one. That is tests/test_scanner.py's
_only_failing() discipline pointed at a JSON file: a test that breaks two
things and reports one is a test that would pass on the wrong evidence.

The rest exercise the arithmetic — the forward-return maths, the accumulation
across runs, the retention window — against frames whose answers are known
here, computed by hand rather than by the writer under test.
"""

from __future__ import annotations

import json
import math
import threading
from datetime import date, datetime, timezone

import pandas as pd
import pytest

from src import ledger, pipeline

# ===========================================================================
# The contract, read back out of the file
# ===========================================================================

#: Every invariant this checker knows how to break. The names are ours; the
#: rules are docs/data.json's `_contract`, which src.ledger.CONTRACT_INVARIANTS
#: writes into the file and README documents.
INVARIANTS = (
    "schema",              # schema_version, and the run block's own keys
    "not_truncated",       # len(candidates) == run.scored, ranks 1..n
    "nothing_vanished",    # run.scored + len(gated_out) == run.bursts
    "ranked",              # rank order is the pipeline's: claude first, then score
    "provenance",          # source is claude or fallback, and looks like it
    "chart_seen",          # chart_seen only where a chart exists
    "chart_path",          # docs-relative, or null WITH a reason
    "checklist",           # every burst carries one row per check, scored or not
    "streak",              # day N of this setup, internally consistent, or null
    "returns_shape",       # d1/d3/d5/as_of, null when unknown
    "numbers_or_null",     # no NaN, no "n/a", no 0 standing in for unknown
)

_RUN_KEYS = ("date", "type", "bursts", "passed_gate", "scored", "score_cap",
             "shortlist_size", "gate", "scored_by", "universe", "errors")

#: Fields that must be a number or null wherever they appear. `0` is a legal
#: value for a count; what the contract forbids is a string or a NaN in one.
_NUMERIC = ("close", "gain_pct", "volume", "prev_volume", "volume_ratio",
            "dollar_volume", "score", "lynch_passes", "lynch_total", "rank",
            "d1", "d3", "d5", "n", "rows", "bursts", "passed_gate", "scored", "size",
            "shortlist_size", "score_cap", "top_score", "fallbacks",
            "day", "seen_before", "last_score",
            "pct_off_52w_high", "pct_above_52w_low", "perf_3mo_pct", "perf_6mo_pct")


_STREAK_KEYS = {"day", "unknown_reason", "first_seen", "last_seen", "last_score",
                "last_verdict", "last_outcome", "seen_before",
                "history_from", "history_sessions"}
_UNKNOWN_REASONS = {ledger.NO_HISTORY, ledger.HISTORY_UNDATED,
                    ledger.HISTORY_UNREADABLE, ledger.WINDOW_NOT_COVERED}
#: The three reasons that leave the record with NO SPAN to report. The fourth,
#: window_not_covered, is the one where the span exists and is too short -- and
#: is therefore the one where reporting it is the whole point.
_NO_SPAN_REASONS = {ledger.NO_HISTORY, ledger.HISTORY_UNDATED,
                    ledger.HISTORY_UNREADABLE}


def _sessions_between(earlier: str, later: str) -> int | None:
    """Trading sessions between two ISO dates, computed HERE.

    pandas rather than src.ledger's numpy, on purpose: a checker that asks the
    module under test whether the module under test got it right cannot fail.
    Weekends only, which is the same simplification src.ledger makes -- a
    holiday makes a span read one session longer, which can only make this
    checker more permissive, never less.
    """
    try:
        return len(pd.bdate_range(earlier, later)) - 1
    except (ValueError, TypeError):
        return None


def _streak_ok(row) -> bool:
    """Is this burst's streak block internally consistent, or honestly absent?

    The file cannot be checked against the ledger from here -- it does not
    carry one -- so what is enforced is that the block cannot contradict
    itself: day 1 is exactly a setup that starts today, and "never seen
    before" is exactly no previous appearance. A row that claims day 4 while
    first_seen is today's session is a streak computed against nothing, which
    is the shape a broken read would take.

    A NULL day is legal and must carry the reason there is none, because that
    is the difference between "we could not read the file", "the file does not
    reach back far enough" and "this is new" -- and the last of the three is a
    claim about the market that the first two cannot support. A day number
    without a reason and a reason without a day are both refused: exactly one
    of the pair answers.

    history_from and history_sessions are the RECORD the rest of the block was
    read out of, and having them here makes two claims checkable that used to
    be unfalsifiable from the file alone:

      a day number requires the reach it says it has. day is published only
      where the record starts at least MAX_STREAK_GAP_SESSIONS sessions before
      the setup did, so "day 3, setup began Friday, record begins Thursday" is
      a number no reading of that record can produce.
      a name cannot have burst on more sessions than the record holds, so
      seen_before <= history_sessions.

    The whole block being null is legal too, and means unknown.
    """
    streak = row.get("streak")
    if streak is None:
        return "streak" in row
    if not isinstance(streak, dict) or set(streak) != _STREAK_KEYS:
        return False
    day, seen, why = streak["day"], streak["seen_before"], streak["unknown_reason"]
    span, since = streak["history_sessions"], streak["history_from"]
    if not isinstance(seen, int) or isinstance(seen, bool) or seen < 0:
        return False
    if not isinstance(span, int) or isinstance(span, bool) or span < 0:
        return False
    if (since is None) != (span == 0):
        return False   # a record that begins somewhere holds sessions, and back
    if seen > span:
        return False   # burst on more sessions than the record holds any run for
    if (day is None) != (why is not None):
        return False   # a day and a reason there is none, or neither of them
    if day is None:
        if why not in _UNKNOWN_REASONS:
            return False
        if (since is None) != (why in _NO_SPAN_REASONS):
            return False   # only window_not_covered has a record to report
        if streak["first_seen"] is not None:
            return False   # where the setup began is the claim `day` makes
    else:
        if not isinstance(day, int) or isinstance(day, bool) or day < 1:
            return False
        if since is None:
            return False   # a day number read out of a record with no span
        if (day == 1) != (streak["first_seen"] == row.get("date")):
            return False
        if day > 1 and seen < day - 1:
            return False   # more days in this setup than appearances to make them
        reach = _sessions_between(since, streak["first_seen"])
        if reach is None or reach < ledger.MAX_STREAK_GAP_SESSIONS:
            return False   # a day number the record cannot have looked far
                           # enough back to support -- see _why_no_day()
    if (seen == 0) != (streak["last_seen"] is None):
        return False
    if streak["last_seen"] is None and any(
            streak[k] is not None for k in ("last_score", "last_verdict", "last_outcome")):
        return False   # a judgement, or a rejection, from a sighting that never happened
    return True


def _bad_number(key, value) -> bool:
    if key not in _NUMERIC or value is None:
        return False
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return True
    return not math.isfinite(value)


def _walk(node, found: list) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if _bad_number(key, value):
                found.append((key, value))
            _walk(value, found)
    elif isinstance(node, list):
        for item in node:
            _walk(item, found)


def _returns_ok(returns, *, run_level: bool) -> bool:
    if not isinstance(returns, dict):
        return False
    horizons = [f"d{h}" for h in ledger.HORIZONS]
    if any(k not in returns for k in horizons):
        return False
    for key in horizons:
        value = returns[key]
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            return False
    if run_level:
        n, rows = returns.get("n"), returns.get("rows")
        if not all(isinstance(v, int) and not isinstance(v, bool) and v >= 0
                   for v in (n, rows)):
            return False
        # n counts setups and rows counts the rows they were collapsed from, so
        # a run cannot hold more setups than rows. The pair is the whole point:
        # a mean weighted by rows over-weights the name that burst five
        # sessions running, and a label saying "names" over a row count is not
        # true of either number.
        return n <= rows
    if "as_of" not in returns:
        return False
    measured = any(returns[k] is not None for k in horizons)
    # as_of dates the newest close that was USED. Nothing used, nothing to date.
    return measured == (returns["as_of"] is not None)


def contract_violations(data: dict, docs_dir=None) -> set[str]:
    """Which of docs/data.json's invariants this document does NOT satisfy."""
    bad: set[str] = set()
    run = data.get("run") or {}
    candidates = data.get("candidates")
    gated = data.get("gated_out")

    if (data.get("schema_version") != ledger.SCHEMA_VERSION
            or not isinstance(candidates, list) or not isinstance(gated, list)
            or not isinstance(data.get("runs"), list)
            or any(key not in run for key in _RUN_KEYS)):
        return {"schema"}  # nothing below can be trusted to mean anything

    if len(candidates) != run["scored"]:
        bad.add("not_truncated")
    if [c.get("rank") for c in candidates] != list(range(1, len(candidates) + 1)):
        bad.add("not_truncated")

    if run["scored"] + len(gated) != run["bursts"]:
        bad.add("nothing_vanished")
    tickers = [c["ticker"] for c in candidates] + [g["ticker"] for g in gated]
    if len(set(tickers)) != len(tickers):
        bad.add("nothing_vanished")

    # The pipeline's own rank key: every Claude score above every fallback
    # (src.scorer._rank_key), then score descending inside each group.
    keys = [((c.get("provenance") or {}).get("source") == "claude", c.get("score") or 0.0)
            for c in candidates]
    if keys != sorted(keys, reverse=True):
        bad.add("ranked")

    for row in candidates:
        prov = row.get("provenance") or {}
        source = prov.get("source")
        if source not in ("claude", "fallback"):
            bad.add("provenance")
        elif source == "fallback" and prov.get("model"):
            bad.add("provenance")   # a fallback wearing a model's name
        elif source == "claude" and not prov.get("model"):
            bad.add("provenance")
        if prov.get("chart_seen") and not row.get("chart"):
            bad.add("chart_seen")
        chart, why = row.get("chart"), row.get("chart_error")
        if chart is None:
            if not (isinstance(why, str) and why.strip()):
                bad.add("chart_path")
        elif chart.startswith("/") or chart.startswith("..") or "\\" in chart:
            bad.add("chart_path")
        elif docs_dir is not None and not (docs_dir / chart).exists():
            bad.add("chart_path")
        if not _returns_ok(row.get("forward_returns"), run_level=False):
            bad.add("returns_shape")

    for row in candidates + gated:
        detail = row.get("lynch_detail")
        if not isinstance(detail, list) or len(detail) != row.get("lynch_total"):
            bad.add("checklist")
            continue
        for check in detail:
            if (set(check) != {"code", "label", "pass", "value"}
                    or not isinstance(check["pass"], bool)
                    or not str(check["value"]).strip()):
                bad.add("checklist")
        if sum(1 for c in detail if c["pass"]) != row.get("lynch_passes"):
            bad.add("checklist")

    for row in candidates + gated:
        if not _streak_ok(row):
            bad.add("streak")

    for row in gated:
        if not _returns_ok(row.get("forward_returns", ledger.empty_returns()),
                           run_level=False):
            bad.add("returns_shape")

    for row in data["runs"]:
        if not _returns_ok(row.get("forward_returns"), run_level=True):
            bad.add("returns_shape")

    found: list = []
    _walk(data, found)
    if found:
        bad.add("numbers_or_null")
    return bad


# --------------------------------------------------------- a good document --

def _detail(passes: int) -> list[dict]:
    codes = ["2", "L", "Y", "N", "C", "H"]
    return [{"code": code, "label": f"check {code}", "pass": i < passes,
             "value": f"measured {i}"} for i, code in enumerate(codes)]


#: The record the document's streak blocks were computed against: six sessions,
#: beginning seven sessions before the burst they describe. Deep enough for a
#: day NUMBER, which needs MAX_STREAK_GAP_SESSIONS sessions of reach past where
#: the setup started -- and the document's `runs` holds exactly these sessions
#: plus the run that just finished, which is what a real file looks like: the
#: streaks were computed before tonight's run was added to the history they
#: were computed from, so `runs` is one session longer than history_sessions.
_SPAN = {"history_from": "2026-08-21", "history_sessions": 6}
_PAST_SESSIONS = ("2026-08-28", "2026-08-27", "2026-08-26", "2026-08-25",
                  "2026-08-24", "2026-08-21")


def _new_setup(session: str = "2026-08-31") -> dict:
    """A streak block for a name nobody has seen before: day 1, nothing prior.

    Day 1 is a real answer here, not the default one: it is what a ledger that
    reaches back past the streak window and holds no earlier appearance says.
    src.ledger only publishes it under that condition -- see _why_no_day().
    """
    return {"day": 1, "unknown_reason": None, "first_seen": session,
            "last_seen": None, "last_score": None, "last_verdict": None,
            "last_outcome": None, "seen_before": 0, **_SPAN}


def _candidate(ticker: str, rank: int, score: float, source: str = "claude") -> dict:
    return {
        "rank": rank, "ticker": ticker, "date": "2026-08-31", "close": 12.5,
        "gain_pct": 6.1, "volume": 9_000_000, "prev_volume": 4_000_000,
        "volume_ratio": 2.2, "dollar_volume": 112_500_000,
        "lynch": "5/6", "lynch_passes": 5, "lynch_total": 6, "lynch_detail": _detail(5),
        "score": score, "verdict": "A", "reason": "r", "key_risk": "k",
        "provenance": {"source": source,
                       "model": "claude-sonnet-4-6" if source == "claude" else None,
                       "chart_seen": True, "error": None},
        "chart": f"charts/{ticker}.png", "chart_error": None,
        "context": {"pct_off_52w_high": -4.0, "perf_3mo_pct": None},
        "streak": _new_setup(),
        "forward_returns": {"d1": None, "d3": None, "d5": None, "as_of": None},
    }


@pytest.fixture
def document() -> dict:
    """A hand-written document that satisfies every invariant.

    Hand-written on purpose: a checker only ever fed its own writer's output
    cannot tell a rule it enforces from a rule it merely describes.
    """
    return {
        "schema_version": 1, "app": "SpicyStock", "generated": "2026-09-01T00:00:00Z",
        "run": {
            "date": "2026-08-31", "type": "evening", "dry_run": False, "fixture": False,
            "universe": {"label": "data/symbols.txt (checked in)", "size": 230},
            "bursts": 3, "passed_gate": 2, "scored": 2, "score_cap": 25,
            "shortlist_size": 2, "gate": {"min_lynch_passes": 3, "total_checks": 6},
            "scored_by": {"claude": 1, "fallback": 1}, "model": "claude-sonnet-4-6",
            "errors": [],
        },
        "candidates": [_candidate("AAA", 1, 8.4), _candidate("BBB", 2, 7.0, "fallback")],
        "gated_out": [{
            "ticker": "CCC", "date": "2026-08-31", "close": 9.0, "gain_pct": 4.4,
            "volume": 5_000_000, "volume_ratio": 1.8, "lynch": "2/6",
            "lynch_passes": 2, "lynch_total": 6, "lynch_detail": _detail(2),
            "streak": _new_setup(), "reason": "lynch_gate",
        }],
        "runs": [{"date": "2026-08-31", "type": "evening", "bursts": 3, "passed_gate": 2,
                  "scored": 2, "shortlist_size": 2, "top_score": 8.4, "fallbacks": 1,
                  "forward_returns": {"d1": None, "d3": None, "d5": None,
                                      "n": 0, "rows": 0}}] + [
            # The sessions the streak blocks above say the record holds. A
            # document whose rows claim a history deeper than its own `runs`
            # is describing a file that cannot exist, and now that the block
            # carries history_from a reader can see it.
            {"date": day, "type": "evening", "bursts": 3, "passed_gate": 2,
             "scored": 2, "shortlist_size": 2, "top_score": 8.0, "fallbacks": 0,
             "forward_returns": {"d1": 1.1, "d3": None, "d5": None, "n": 2, "rows": 2}}
            for day in _PAST_SESSIONS],
    }


def test_the_hand_written_document_satisfies_every_invariant(document):
    """The precondition for every doctoring below: this one is clean."""
    assert contract_violations(document) == set()


# ===========================================================================
# The checker can fail — one doctored rule at a time, and ONLY that one
# ===========================================================================

def _only(document, expected):
    """Assert the checker names exactly the invariant that was broken.

    Exactly, not "at least": a doctoring that trips a second rule means the
    test would have passed for the wrong reason, which is the defect this
    project has already shipped three times in its rejection tests.
    """
    violations = contract_violations(document)
    assert violations == {expected}, f"expected only {expected!r}, got {violations}"


def test_a_truncated_candidate_list_is_caught(document):
    """THE invariant of step 9: the archive is not cut to the email's five.

    Deleting the last row and telling the truth about run.scored would be a
    consistent smaller run; what this catches is the file CLAIMING 2 while
    carrying 1 — which is exactly what TOP_N used to do to the archive.
    """
    document["candidates"] = document["candidates"][:1]
    _only(document, "not_truncated")


def test_a_gap_in_the_ranks_is_caught(document):
    document["candidates"][1]["rank"] = 3
    _only(document, "not_truncated")


def test_a_burst_that_vanished_is_caught(document):
    """Neither scored nor gated out: it is simply gone from the file."""
    document["gated_out"] = []
    _only(document, "nothing_vanished")


def test_the_same_ticker_twice_is_caught(document):
    document["gated_out"][0]["ticker"] = "AAA"
    _only(document, "nothing_vanished")


def test_a_fallback_ranked_above_a_real_score_is_caught(document):
    """Step 8 made this structurally impossible in src.scorer. The archive is
    where a regression would show, so the archive checks it."""
    document["candidates"][0], document["candidates"][1] = (
        document["candidates"][1], document["candidates"][0])
    document["candidates"][0]["rank"], document["candidates"][1]["rank"] = 1, 2
    _only(document, "ranked")


def test_a_fallback_labelled_claude_is_caught(document):
    document["candidates"][1]["provenance"]["source"] = "claude"
    _only(document, "provenance")


def test_chart_seen_without_a_chart_is_caught(document):
    """The row would be claiming the model looked at an image that is not there."""
    document["candidates"][0]["chart"] = None
    document["candidates"][0]["chart_error"] = "mplfinance ValueError: no renderer"
    _only(document, "chart_seen")


def test_a_missing_chart_with_no_reason_is_caught(document):
    document["candidates"][0]["chart"] = None
    document["candidates"][0]["provenance"]["chart_seen"] = False
    _only(document, "chart_path")


def test_a_chart_path_the_page_cannot_serve_is_caught(document):
    """docs/index.html sets `chart` as an <img src> relative to itself, so an
    absolute path or one climbing out of docs/ is a broken image, not a chart."""
    document["candidates"][0]["chart"] = "/home/runner/charts/AAA.png"
    _only(document, "chart_path")


def test_a_chart_path_that_does_not_exist_is_caught(document, tmp_path):
    assert contract_violations(document, docs_dir=tmp_path) == {"chart_path"}
    for row in document["candidates"]:
        (tmp_path / "charts").mkdir(exist_ok=True)
        (tmp_path / row["chart"]).write_bytes(b"png")
    assert contract_violations(document, docs_dir=tmp_path) == set()


def test_a_gated_row_without_its_checklist_is_caught(document):
    """The per-check pass rates are computed over every burst. Drop the
    checklist from the ones that failed and the rates describe the survivors."""
    del document["gated_out"][0]["lynch_detail"]
    _only(document, "checklist")


def test_a_checklist_that_does_not_add_up_to_its_own_count_is_caught(document):
    document["candidates"][0]["lynch_passes"] = 6
    _only(document, "checklist")


def test_a_streak_that_contradicts_its_own_first_sighting_is_caught(document):
    """day 4 with the setup starting today is a streak counted against a
    history that is not there -- the shape a broken read would take."""
    document["candidates"][0]["streak"] = dict(_new_setup(), day=4)
    _only(document, "streak")


def test_a_repeat_with_nothing_before_it_is_caught(document):
    """"first seen three sessions ago" and "never seen before" cannot both be
    true of one name."""
    document["candidates"][0]["streak"] = dict(_new_setup(), day=2,
                                               first_seen="2026-08-27")
    _only(document, "streak")


def test_a_verdict_from_a_sighting_that_never_happened_is_caught(document):
    document["candidates"][0]["streak"] = dict(_new_setup(), last_score=7.5,
                                               last_verdict="A")
    _only(document, "streak")


def test_a_rejection_from_a_sighting_that_never_happened_is_caught(document):
    """last_outcome describes the appearance last_seen names. With no such
    appearance there is nothing for it to describe, and "we rejected it then"
    would be a sentence about a night that did not happen."""
    document["candidates"][0]["streak"] = dict(_new_setup(), last_outcome="lynch_gate")
    _only(document, "streak")


def test_a_day_that_is_not_known_and_will_not_say_why_is_caught(document):
    """The whole point of the null. A day nobody can compute is publishable
    only with the reason attached, because "unknown" and "new" are what the
    reader is being asked to tell apart."""
    document["candidates"][0]["streak"] = dict(_new_setup(), day=None,
                                               first_seen=None)
    _only(document, "streak")


def test_a_day_number_beside_a_reason_it_could_not_be_known_is_caught(document):
    """The other direction: a block cannot both answer and decline to."""
    document["candidates"][0]["streak"] = dict(_new_setup(),
                                               unknown_reason=ledger.NO_HISTORY)
    _only(document, "streak")


def test_a_reason_nothing_in_the_ledger_can_produce_is_caught(document):
    """The three reasons are three repairs -- a corrupt file, an empty one, a
    shallow one. A fourth word means the writer invented a state, and the
    reader has nothing to do with it."""
    document["candidates"][0]["streak"] = dict(_new_setup(), day=None,
                                               first_seen=None,
                                               unknown_reason="dunno")
    _only(document, "streak")


def test_an_unknown_day_that_still_claims_where_the_setup_began_is_caught(document):
    """first_seen answers the same question day does. A record that cannot
    place the burst in a setup cannot say when that setup started either."""
    document["candidates"][0]["streak"] = dict(
        _new_setup(), day=None, unknown_reason=ledger.WINDOW_NOT_COVERED)
    _only(document, "streak")


def test_a_day_number_read_out_of_a_record_with_no_span_is_caught(document):
    """A day is a reading of a record. With no record there is nothing it can
    have been read out of, and the number is a claim about the market made from
    a file that holds nothing."""
    document["candidates"][0]["streak"] = dict(_new_setup(), history_from=None,
                                               history_sessions=0)
    _only(document, "streak")


def test_a_day_the_record_cannot_reach_back_far_enough_to_support_is_caught(document):
    """day 1 says nothing preceded this burst. Over a record beginning two
    sessions before it, that is a claim about four nights nobody scanned --
    and now that the block carries the record, it is checkable from the file
    instead of taken on trust. src.ledger's _why_no_day() is the rule; this is
    an independent reading of it."""
    document["candidates"][0]["streak"] = dict(_new_setup(), history_from="2026-08-27")
    _only(document, "streak")


def test_a_name_seen_on_more_sessions_than_the_record_holds_is_caught(document):
    """seen_before counts sessions inside the record, so it cannot exceed the
    number the record has. "Burst on 9 of the 6 sessions" is the shape of a
    count taken over one file and a span taken over another."""
    document["candidates"][0]["streak"] = dict(
        _new_setup(), day=None, first_seen=None,
        unknown_reason=ledger.WINDOW_NOT_COVERED, last_seen="2026-08-25",
        seen_before=document["candidates"][0]["streak"]["history_sessions"] + 1)
    _only(document, "streak")


def test_a_record_that_begins_somewhere_and_holds_no_sessions_is_caught(document):
    """The pair answers one question and has to answer it once: a record that
    begins on a date holds at least the session that date names."""
    document["candidates"][0]["streak"] = dict(_new_setup(), history_sessions=0)
    _only(document, "streak")


def test_an_unreadable_history_that_still_names_a_record_is_caught(document):
    """Three of the four unknowns mean there is no span to report -- the file
    could not be read, holds nothing, or holds nothing datable. Only
    window_not_covered has a record behind it, which is why it is the one that
    reports one."""
    document["candidates"][0]["streak"] = dict(
        _new_setup(), day=None, first_seen=None,
        unknown_reason=ledger.HISTORY_UNREADABLE)
    _only(document, "streak")


def test_the_block_a_run_that_read_nothing_publishes_is_a_valid_one(document):
    """The other half, and it is src.ledger's own answer rather than a
    hand-written imitation of it: the block a run with an unreadable history
    puts on every row has to satisfy the checker that reads the file back."""
    for row in document["candidates"] + document["gated_out"]:
        row["streak"] = ledger.unknown_streak(ledger.HISTORY_UNREADABLE)

    assert contract_violations(document) == set()


def test_a_history_too_shallow_to_count_days_is_still_a_valid_document(document):
    """The half that keeps the rule honest: an unknown day IS legal, so the
    invariant cannot be satisfied by always writing a number."""
    for row in document["candidates"] + document["gated_out"]:
        row["streak"] = dict(_new_setup(), day=None, first_seen=None,
                             unknown_reason=ledger.WINDOW_NOT_COVERED)
    assert contract_violations(document) == set()


def test_a_burst_with_no_streak_field_at_all_is_caught(document):
    """Absent is not the same as null. Null says "this run could not read its
    history"; missing says a writer forgot, and the reader cannot tell."""
    del document["gated_out"][0]["streak"]
    _only(document, "streak")


def test_a_run_that_could_not_read_its_history_is_still_a_valid_document(document):
    """The other half: null IS legal, so the invariant cannot be satisfied
    simply by always writing a block."""
    for row in document["candidates"] + document["gated_out"]:
        row["streak"] = None
    assert contract_violations(document) == set()


def test_a_forward_return_of_zero_for_unknown_is_caught(document):
    """`0` is a return, not an absence, and it would be averaged in as a flat
    session that never happened."""
    document["candidates"][0]["forward_returns"] = {"d1": 0.0, "d3": None,
                                                    "d5": None, "as_of": None}
    _only(document, "returns_shape")


def test_a_string_where_a_number_belongs_is_caught(document):
    document["candidates"][0]["gain_pct"] = "n/a"
    _only(document, "numbers_or_null")


def test_a_nan_is_caught(document):
    """json.dump writes NaN as a bare token no JSON parser reads back, so this
    is not a cosmetic problem: the dashboard fails to load the whole file."""
    document["candidates"][0]["dollar_volume"] = float("nan")
    _only(document, "numbers_or_null")


def test_a_run_mean_over_no_names_is_caught(document):
    document["runs"][0]["forward_returns"] = {"d1": 0.0, "d3": 0.0, "d5": 0.0}
    _only(document, "returns_shape")


def test_a_run_that_claims_more_setups_than_it_has_rows_is_caught(document):
    """n is the weight the dashboard multiplies a session's mean by, and rows
    is what those setups were collapsed from. More setups than rows is the
    shape of a run that went back to weighting by rows and kept the label."""
    document["runs"][0]["forward_returns"] = {"d1": 1.0, "d3": None, "d5": None,
                                              "n": 4, "rows": 3}
    _only(document, "returns_shape")


# ===========================================================================
# Forward returns: the arithmetic, against frames whose answers are known here
# ===========================================================================

def frame(closes: list[float], end: str = "2026-08-31") -> pd.DataFrame:
    index = pd.bdate_range(end=end, periods=len(closes), name="timestamp")
    return pd.DataFrame({"Close": [float(c) for c in closes],
                         "Volume": [1_000_000] * len(closes)}, index=index)


def test_forward_returns_are_sessions_after_the_burst_not_calendar_days():
    """Six sessions, the burst on the first: +1%, +3%, +10% by construction."""
    df = frame([100, 101, 102, 103, 104, 110])
    burst = df.index[0].date().isoformat()

    assert ledger.forward_returns(df, burst) == {
        "d1": 1.0, "d3": 3.0, "d5": 10.0,
        "as_of": df.index[5].date().isoformat(),
    }


def test_a_horizon_the_sessions_have_not_reached_is_null_not_zero():
    df = frame([100, 101, 102, 103])          # only three sessions after the burst
    burst = df.index[0].date().isoformat()

    out = ledger.forward_returns(df, burst)

    assert out["d1"] == 1.0 and out["d3"] == 3.0
    assert out["d5"] is None
    assert out["as_of"] == df.index[3].date().isoformat()


def test_nothing_after_the_burst_measures_nothing_and_dates_nothing():
    df = frame([100, 101, 102])
    burst = df.index[-1].date().isoformat()

    assert ledger.forward_returns(df, burst) == ledger.empty_returns()


def test_a_burst_session_missing_from_the_frame_stays_pending():
    """A halted or delisted name. The nearest bar is NOT used: that would
    silently move the horizon and report a return for a session it skipped."""
    df = frame([100, 101, 102, 103, 104, 110])

    assert ledger.forward_returns(df, "2026-01-05") == ledger.empty_returns()
    assert ledger.forward_returns(df, None) == ledger.empty_returns()
    assert ledger.forward_returns(None, "2026-08-31") == ledger.empty_returns()


def test_a_gap_in_the_closes_does_not_become_a_return():
    df = frame([100, float("nan"), 102, 103, 104, 110])
    burst = df.index[0].date().isoformat()

    out = ledger.forward_returns(df, burst)

    assert out["d1"] is None, "a NaN close is not a 0% session"
    assert out["d3"] == 3.0


def _row(ticker: str, session: str, **returns) -> dict:
    """One ledger row, with whatever forward returns the test gives it."""
    return {"ticker": ticker, "date": session,
            "forward_returns": {**ledger.empty_returns(), **returns}}


def _every_row_leads(rows: list[dict]) -> set:
    """The leads set for rows that are each their own setup."""
    return {(row["ticker"], row["date"]) for row in rows}


def test_the_mean_of_no_measurements_is_null_not_zero():
    rows = [_row(t, "2026-08-31") for t in ("AAA", "BBB", "CCC")]

    assert ledger.mean_returns(rows, _every_row_leads(rows)) == {
        "d1": None, "d3": None, "d5": None, "n": 0, "rows": 0}


def test_the_mean_counts_only_the_names_that_have_one():
    rows = [_row("AAA", "2026-08-31", d1=2.0, as_of="x"),
            _row("BBB", "2026-08-31", d1=-1.0, d3=4.0, as_of="x"),
            _row("CCC", "2026-08-31")]

    assert ledger.mean_returns(rows, _every_row_leads(rows)) == {
        "d1": 0.5, "d3": 4.0, "d5": None, "n": 2, "rows": 2}


def test_a_row_that_continues_a_setup_is_not_a_second_observation():
    """THE double-count. Two rows, one of them the next session of a move
    already counted: its d1 window overlaps the first's and measures the same
    move, so averaging both weights that one move twice.

    Asserted against the mean a row count would have produced, because that is
    the number this replaces: (20 + -10) / 2 = 5.0, not (20 + 20 + -10) / 3.
    """
    rows = [_row("AAA", "2026-08-31", d1=20.0, as_of="x"),
            _row("AAA", "2026-09-01", d1=20.0, as_of="x"),
            _row("BBB", "2026-09-01", d1=-10.0, as_of="x")]
    leads = {("AAA", "2026-08-31"), ("BBB", "2026-09-01")}

    out = ledger.mean_returns(rows, leads)

    assert out["d1"] == 5.0, "the repeat session is the same move, not a second one"
    assert (out["n"], out["rows"]) == (2, 3), (
        "two setups, collapsed from three rows -- and the pair says which is which")


def test_the_published_mean_is_the_one_exact_arithmetic_gives(monkeypatch):
    """The mean a reader judges the screener by must not depend on which
    Python read the file.

    CPython 3.12 changed the builtin sum() to compensated summation for
    floats. These four values -- taken from the run this really happened to in
    tests/fixtures/history -- sum to 22.099999999999998 under 3.11 and to
    22.1 under 3.12, and the mean either side of that rounds to 5.52 against
    5.53. The fixture regenerated under CI's interpreter differed from the
    committed one in exactly two numbers, and both were run-level means.

    Checked against an INDEPENDENT oracle rather than against the expression
    in mean_returns(): Fraction sums these doubles exactly, with no rounding
    at all, so it answers "what is the mean of these four numbers" without
    asking how src.ledger computes it. Comparing to a recomputed
    fsum(...)/len(...) would be the third shaped-test pattern in CLAUDE.md --
    a value checked against the name it came from.

    What this CANNOT check from inside one interpreter is the cross-version
    property itself; that was verified by running the generator under 3.11 and
    3.12 and diffing. What it does check is that naive summation cannot come
    back on any interpreter where it would round differently -- which is the
    interpreter this suite is running on, whichever that is.
    """
    from fractions import Fraction

    values = [9.93, 6.9, 2.86, 2.41]
    rows = [_row(f"N{i}", "2026-08-31", d1=v, as_of="x") for i, v in enumerate(values)]
    exact = sum((Fraction(v) for v in values), Fraction(0)) / len(values)

    published = ledger.mean_returns(rows, _every_row_leads(rows))["d1"]

    assert published == round(float(exact), 2) == 5.53, (
        f"published {published}, exact mean {float(exact)!r}"
    )


def test_the_published_mean_does_not_depend_on_the_order_of_the_rows():
    """A row's position in the file is not one of the mean's inputs.

    The same property from the other side. These four values sum to 20.9 one
    way and to 20.900000000000002 the other under naive summation, which
    rounds to 5.23 against 5.22 -- so a backfill that reordered the rows would
    move a published mean by a cent while measuring the same four numbers.
    Found by searching for a discriminating case rather than picked by eye,
    because the first values tried here (1e16, 3, 1, -1e16) passed under naive
    summation by rounding luck -- the incidental-fact shape CLAUDE.md lists.

    WHAT THIS DOES NOT COVER, stated because the search settled it: from
    CPython 3.12 the builtin sum() is compensated, and 300,000 adversarial
    inputs (up to 40 terms spanning nine orders of magnitude) produced no case
    where it disagrees with fsum. So on 3.12 -- which is what CI runs -- this
    test and the one above both stay green if fsum is swapped back for sum().
    They are load-bearing on 3.11 and earlier, which is what this sandbox
    runs, and the cross-version claim itself was settled by generating
    tests/fixtures/history under both interpreters and diffing, not by either
    of them.
    """
    values = [-22.04, 19.21, 0.52, 23.21]
    rows = [_row(f"N{i}", "2026-08-31", d1=v, as_of="x") for i, v in enumerate(values)]
    leads = _every_row_leads(rows)

    forwards = ledger.mean_returns(rows, leads)["d1"]
    backwards = ledger.mean_returns(list(reversed(rows)), leads)["d1"]

    assert forwards == backwards == 5.23, f"{forwards} forwards, {backwards} reversed"


# ===========================================================================
# The ledger across runs
# ===========================================================================

def _run(date_str: str, tickers=("AAA",), run_type: str = "evening") -> tuple:
    run = {"date": date_str, "type": run_type, "bursts": len(tickers) + 1,
           "passed_gate": len(tickers), "scored": len(tickers),
           "shortlist_size": min(5, len(tickers)), "score_cap": 25,
           "model": "claude-sonnet-4-6", "status": "ok", "dry_run": False}
    candidates = [_candidate(t, i + 1, 8.0 - i) for i, t in enumerate(tickers)]
    for row in candidates:
        row["date"] = date_str
    gated = [{"ticker": "ZZZ", "date": date_str, "close": 9.0, "gain_pct": 4.4,
              "volume": 5_000_000, "volume_ratio": 1.8, "lynch": "2/6",
              "lynch_passes": 2, "lynch_total": 6, "lynch_detail": _detail(2),
              "reason": "lynch_gate", "forward_returns": ledger.empty_returns()}]
    return run, candidates, gated


def test_a_second_run_keeps_the_first(tmp_path):
    book = ledger.Ledger(tmp_path).load()
    book.add_run(*_run("2026-08-25"))
    book.write()

    later = ledger.Ledger(tmp_path).load()
    later.add_run(*_run("2026-08-26"))
    later.write()

    saved = json.loads((tmp_path / ledger.LEDGER_NAME).read_text())
    assert [r["date"] for r in saved["runs"]] == ["2026-08-26", "2026-08-25"]


def test_re_running_a_session_replaces_it_rather_than_counting_it_twice(tmp_path):
    book = ledger.Ledger(tmp_path).load()
    book.add_run(*_run("2026-08-25", ("AAA", "BBB")))
    book.add_run(*_run("2026-08-25", ("AAA",)))

    assert len(book.runs) == 1
    assert book.runs[0]["scored"] == 1


def test_add_run_hands_back_the_entry_it_stored(tmp_path):
    """src.pipeline stamps the run's final status on it after the fetch that
    may have degraded the run. It must be the stored object, not a copy, and
    not runs[0] — the ledger is ordered by session, so a backfilled run sits
    in the middle of it."""
    book = ledger.Ledger(tmp_path).load()
    book.add_run(*_run("2026-08-31"))
    entry = book.add_run(*_run("2026-08-24"))

    entry["status"] = "degraded"

    stored = [r for r in book.runs if r["date"] == "2026-08-24"][0]
    assert stored["status"] == "degraded"
    assert book.runs[0]["status"] == "ok", "and not stamped on somebody else's run"


def test_a_morning_and_an_evening_run_on_one_session_are_two_runs(tmp_path):
    book = ledger.Ledger(tmp_path).load()
    book.add_run(*_run("2026-08-25"))
    book.add_run(*_run("2026-08-25", run_type="morning"))

    assert len(book.runs) == 2


def test_the_ledger_stops_at_max_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "MAX_RUNS", 3)
    book = ledger.Ledger(tmp_path).load()
    for day in range(1, 6):
        book.add_run(*_run(f"2026-08-0{day}"))

    assert [r["date"] for r in book.runs] == ["2026-08-05", "2026-08-04", "2026-08-03"]


def test_an_unreadable_ledger_does_not_take_the_run_with_it(tmp_path, caplog):
    (tmp_path / ledger.LEDGER_NAME).write_text("{not json")

    book = ledger.Ledger(tmp_path).load()
    book.add_run(*_run("2026-08-25"))
    book.write()

    assert len(book.runs) == 1
    assert "unreadable" in caplog.text
    assert json.loads((tmp_path / ledger.LEDGER_NAME).read_text())["runs"]


class _OneSecond(datetime):
    """A clock that never moves, so "two failures in the same second" is a
    fact of the test rather than a race it has to win."""

    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 9, 1, 19, 12, 33, tzinfo=timezone.utc)


def test_a_ledger_this_module_cannot_read_is_moved_aside_not_overwritten(tmp_path):
    """The accumulated outcomes are the one thing here that cannot be
    recomputed, so a read error must not be allowed to destroy them."""
    (tmp_path / ledger.LEDGER_NAME).write_text("{not json")

    ledger.Ledger(tmp_path).load().add_run(*_run("2026-08-25"))
    ledger.Ledger(tmp_path).load()   # again: the second load finds no ledger

    assert [q.read_text() for q in ledger.quarantined(tmp_path)] == ["{not json"]


def test_a_second_unreadable_ledger_does_not_destroy_the_first(tmp_path):
    """THE data loss this replaces. The quarantine name used to be fixed and
    Path.replace overwrites, so a year of outcomes set aside on Monday was
    gone on Tuesday under a 35-byte corrupt file -- with the log line still
    reading "it was NOT overwritten".

    Nothing exotic gets you here: a SCHEMA_VERSION bump and a rollback does it
    in two runs, and so does any cause that corrupts two writes running.
    """
    year = json.dumps({"schema_version": 99,
                       "runs": [{"date": "2025-09-01", "type": "evening"}]})
    (tmp_path / ledger.LEDGER_NAME).write_text(year)
    ledger.Ledger(tmp_path).load()

    (tmp_path / ledger.LEDGER_NAME).write_text("{corrupt")
    ledger.Ledger(tmp_path).load()

    kept = sorted(q.read_text() for q in ledger.quarantined(tmp_path))
    assert kept == sorted([year, "{corrupt"]), (
        "the irreplaceable file was destroyed by the next night's casualty")


def test_two_casualties_inside_one_second_are_two_files(tmp_path, monkeypatch):
    """The clock is the only thing that distinguishes one casualty from the
    next, and a second is not fine enough: a cron run and a hand-fired re-run
    of the same night fail together. The name carries a counter for that, and
    the counter is claimed rather than checked."""
    monkeypatch.setattr(ledger, "datetime", _OneSecond)
    (tmp_path / ledger.LEDGER_NAME).write_text("first")
    ledger.Ledger(tmp_path).load()
    (tmp_path / ledger.LEDGER_NAME).write_text("second")
    ledger.Ledger(tmp_path).load()

    assert sorted(q.read_text() for q in ledger.quarantined(tmp_path)) == [
        "first", "second"]


def test_twelve_casualties_in_one_second_come_back_in_the_order_they_happened(
        tmp_path, monkeypatch):
    """quarantined() promises oldest first, and sorting the names does not
    deliver it.

    `-` (0x2d) sorts before `.` (0x2e), so the unnumbered first casualty of a
    second lands AFTER every numbered one that followed it, and `-10` lands
    before `-2`. Twelve failures inside one second came back
    c1, c10, c11, c2 ... c9, c0 -- the first casualty last, from the function
    whose whole job is finding them. Nothing is lost, and a person reading that
    list repairs the wrong file.
    """
    monkeypatch.setattr(ledger, "datetime", _OneSecond)
    for i in range(12):
        (tmp_path / ledger.LEDGER_NAME).write_text(f"casualty {i}")
        ledger.Ledger(tmp_path).load()

    assert [q.read_text() for q in ledger.quarantined(tmp_path)] == [
        f"casualty {i}" for i in range(12)]


def test_a_casualty_from_before_the_name_carried_a_stamp_is_still_found(tmp_path):
    """`ledger.json.*.unreadable` needs two dots and the pre-stamp name has one.

    The fixed name this scheme replaced was `ledger.json.unreadable`, and a
    file left over from it is never destroyed -- and was invisible to the one
    function that exists to find casualties, so nobody would ever be told it
    was there. It sorts first, because it can only be older than anything the
    stamped scheme wrote.
    """
    (tmp_path / f"{ledger.LEDGER_NAME}.{ledger.QUARANTINE_SUFFIX}").write_text("the old one")
    (tmp_path / ledger.LEDGER_NAME).write_text("{corrupt")
    ledger.Ledger(tmp_path).load()

    assert [q.read_text() for q in ledger.quarantined(tmp_path)] == [
        "the old one", "{corrupt"]


#: How long a threaded test will wait before calling it a hang. Generous enough
#: that a loaded CI runner is not called a deadlock, short enough that a real
#: deadlock fails the job instead of burning its wall clock.
RACE_TIMEOUT_S = 30


def _run_together(target, runners: int):
    """Run `target(barrier)` on `runners` threads and FAIL rather than hang.

    Both race tests below used a bare `threading.Barrier` and a bare `join()`,
    and neither has a timeout. That makes every failure mode inside them an
    indefinite hang: a thread that dies before reaching the barrier leaves the
    others waiting on a count that can never be reached, and `join()` then
    waits on them forever. The pytest job on the merge commit sat in its "Run
    tests" step for fourteen minutes and never finished, on a suite that takes
    under a minute -- while its sibling job started in the same second and
    finished green, so it was the tests, not the runner.

    A hanging test is strictly worse than a failing one: a failure names a
    rule, a hang reports nothing at all and looks exactly like slowness. This
    project's whole posture is that a run nobody can trust must not look like
    one that worked, and a test suite owes the same.

    Exceptions raised inside a thread are collected and re-raised here. They
    used to vanish, leaving a confusing assertion about the result instead of
    the error that caused it.
    """
    barrier = threading.Barrier(runners, timeout=RACE_TIMEOUT_S)
    failures: list[BaseException] = []
    lock = threading.Lock()

    def wrapped() -> None:
        try:
            target(barrier)
        except BaseException as e:  # noqa: BLE001 -- re-raised below
            with lock:
                failures.append(e)

    threads = [threading.Thread(target=wrapped) for _ in range(runners)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(RACE_TIMEOUT_S)

    alive = [t for t in threads if t.is_alive()]
    assert not alive, (
        f"{len(alive)} of {runners} threads were still running after "
        f"{RACE_TIMEOUT_S}s -- this is a deadlock, not a slow machine. "
        f"First error from the others, if any: {failures[:1]}"
    )
    if failures:
        raise failures[0]


def test_forty_runs_failing_in_the_same_second_claim_forty_different_names(
        tmp_path, monkeypatch):
    """The race O_CREAT|O_EXCL is in there for, run rather than argued.

    `exists()` and then rename is two operations with room for another run in
    between; the atomic claim is what closes it, and until now nothing in this
    suite could tell the two apart. Replacing the claim with a check killed
    exactly one test, for the wrong reason -- and under that mutation forty
    threads produced thirty-nine collisions with the suite still green.

    The clock is frozen so that "the same second" is a fact of the test rather
    than a race it has to win, and the barrier makes the forty threads reach
    the claim together rather than in a queue.
    """
    monkeypatch.setattr(ledger, "datetime", _OneSecond)
    book = ledger.Ledger(tmp_path)
    runners = 40
    claimed: list = []
    lock = threading.Lock()

    def claim(together) -> None:
        together.wait()
        name = book._claim_quarantine()
        with lock:
            claimed.append(name)

    _run_together(claim, runners)

    assert None not in claimed, "every one of them had a name to take"
    assert len(set(claimed)) == runners, (
        f"{runners - len(set(claimed))} of {runners} runs were handed a name "
        "another run already held, and a rename onto it overwrites")
    assert all(name.exists() for name in claimed), (
        "a claim that leaves no file behind is not a claim")


def test_a_race_to_set_the_same_ledger_aside_keeps_it_exactly_once(tmp_path, monkeypatch):
    """The same race through the function that does the damage.

    Two runs discover one unreadable ledger at the same moment. Exactly one of
    them can move it; the others must find their own name taken, fail cleanly
    and take their own empty placeholder away with them -- and NOT the file the
    winner just moved into place.

    That last part is what a checked name cannot do. Sharing one name, the
    loser's failed rename is followed by an unlink of the path the winner's
    content is now sitting at, so the race does not merely collide: it destroys
    the record, which is what set_aside() exists to prevent.

    The barrier sits after the read and before the move, which is the window
    itself. Through load() the same threads race, but a thread that reads after
    the winner's rename sees no file at all and never reaches here.

    What this one guarantees, exactly: with the claim replaced by an exists()
    check it went red in six runs of eight -- whether the record is destroyed
    depends on which thread renames first and how many are already holding the
    same name when it does. The test above is the deterministic pin (eight of
    eight); this is the one that shows what the collision COSTS, which is not a
    duplicate file but the year of outcomes it was moving out of harm's way.
    """
    monkeypatch.setattr(ledger, "datetime", _OneSecond)
    year = json.dumps(_a_year_of_runs(20))
    (tmp_path / ledger.LEDGER_NAME).write_text(year)
    runners = 40

    def move_it_aside(together) -> None:
        # Built BEFORE the barrier deliberately -- the window this races on
        # opens after the read. Anything that throws here used to strand the
        # other runners on a barrier count that could never be reached.
        book = ledger.Ledger(tmp_path)
        together.wait()
        book.set_aside("unreadable")

    _run_together(move_it_aside, runners)

    kept = ledger.quarantined(tmp_path)
    assert [q.read_text() for q in kept] == [year], (
        "the record survives the race exactly once -- no copy destroyed by a "
        "loser's cleanup, and no empty placeholder left looking like one")
    assert not (tmp_path / ledger.LEDGER_NAME).exists()


def test_a_directory_where_the_ledger_should_be_is_left_where_it_is(tmp_path):
    """The failure path that cannot be moved aside at all. The run still has
    to survive it, the directory has to survive it, and the empty name the
    move had claimed must not be left behind looking like a lost history."""
    (tmp_path / ledger.LEDGER_NAME).mkdir()

    book = ledger.Ledger(tmp_path).load()

    assert (tmp_path / ledger.LEDGER_NAME).is_dir(), "still there"
    assert ledger.quarantined(tmp_path) == [], "and no empty casualty beside it"
    assert "could not be moved aside" in book.load_error


def test_valid_json_that_is_not_a_ledger_is_kept_like_any_other_bad_read(tmp_path):
    """`[]`, `null`, `4` and `"docs/ledger.json"` all parse. Every one of them
    used to raise AttributeError out of load() -- past the catch-all, which
    only wrapped json.loads -- so load_error stayed unset, the file was NOT
    set aside, and the next write() replaced it. The pipeline survived on a
    catch-all upstream; every direct caller did not.
    """
    for shape, payload in (("list", "[1, 2, 3]"), ("null", "null"),
                           ("number", "4"), ("string", '"docs/ledger.json"')):
        room = tmp_path / shape
        room.mkdir()
        (room / ledger.LEDGER_NAME).write_text(payload)

        book = ledger.Ledger(room).load()

        assert book.runs == [] and book.load_error, shape
        assert "not a ledger object" in book.load_error, shape
        assert [q.read_text() for q in ledger.quarantined(room)] == [payload]


def _a_year_of_runs(sessions: int = 252) -> dict:
    """A ledger the size this file really reaches: a trading year of runs, each
    holding a scored row and the forward returns a later run filled in.

    Written out it is a quarter of a megabyte, and every byte of it is a
    measurement that cannot be recomputed -- the burst is gone, the frame it
    was measured in has been restated, and the score was a model call nobody
    is going to make again. That is what the tests below are about keeping.
    """
    days = pd.bdate_range(end="2026-08-31", periods=sessions)
    return {
        "schema_version": ledger.SCHEMA_VERSION, "app": "SpicyStock",
        "generated": "2026-08-31T22:11:04Z",
        "runs": [{
            "date": day.date().isoformat(), "type": "evening", "bursts": 3,
            "passed_gate": 1, "scored": 1, "shortlist_size": 1, "score_cap": 25,
            "top_score": 8.1, "fallbacks": 0, "model": "claude-sonnet-4-6",
            "status": "ok", "dry_run": False,
            "candidates": [{"ticker": "AAA", "date": day.date().isoformat(),
                            "rank": 1, "score": 8.1, "verdict": "A",
                            "source": "claude", "close": 12.0, "gain_pct": 5.5,
                            "volume_ratio": 2.4, "lynch_passes": 5,
                            "lynch_total": 6, "checks": {"2": True, "H": True},
                            "forward_returns": {"d1": 1.4, "d3": 2.2, "d5": -0.6,
                                                "as_of": "2026-09-04"}}],
            "gated": [],
        } for day in reversed(days)],
    }


_MISSING = object()


def _ledger_text(year: dict, runs) -> str:
    doc = dict(year)
    if runs is _MISSING:
        doc.pop("runs")
    else:
        doc["runs"] = runs
    return json.dumps(doc, indent=2) + "\n"


@pytest.mark.parametrize("shape", ["a string", "an object", "null", "no runs key",
                                   "junk rows", "half junk rows", "nested lists",
                                   "a run whose candidates are a string",
                                   "a run with a row that is not a row",
                                   "a run missing its rows"])
def test_a_ledger_whose_runs_are_not_runs_is_kept_like_any_other_bad_read(tmp_path, shape):
    """THE line the last repair stopped one short of.

    `raw` was checked for being a dict and `raw["runs"]` was not: a runs list
    that was a string, an object, null or simply absent fell into an `else []`
    with load_error still None and the file still on disk, so the run reported
    "no history has been recorded yet" about a file holding a year -- and then
    write() replaced it. Reproduced against a real 252-run ledger: 243 kB in,
    1068 bytes out, nothing recoverable.

    A row-level filter that drops what it cannot read is the same defect one
    level further in, and it is worse, because the run then publishes day
    numbers and means computed over the rows that happened to survive.
    src.ledger tolerates none: the file either is the document write() emits or
    it is kept and a new history is started beside it.

    Driven through the whole sequence that does the damage -- load, add_run,
    write -- because it is write() that destroys, and a test that stops after
    load() would pass on a version that still lost the file.
    """
    year = _a_year_of_runs()
    real = list(year["runs"])
    runs = {
        "a string": "docs/ledger.json",
        "an object": {run["date"]: run for run in real},
        "null": None,
        "no runs key": _MISSING,
        "junk rows": ["a merge conflict left this", 4, None],
        "half junk rows": [run if i % 2 else "junk" for i, run in enumerate(real)],
        "nested lists": [[real]],
        # And the same shapes one level in, where a silent skip is not the
        # worst outcome: `"candidates": "AAA"` used to load clean, set no
        # load_error, and then raise AttributeError out of streaks() -- the run
        # dead after it had fetched its bars and paid for its scores.
        "a run whose candidates are a string": [dict(real[0], candidates="AAA"),
                                                *real[1:]],
        "a run with a row that is not a row": [dict(real[0], gated=["hand-edited"]),
                                               *real[1:]],
        "a run missing its rows": [{k: v for k, v in real[0].items()
                                    if k != "candidates"}, *real[1:]],
    }[shape]
    original = _ledger_text(year, runs)
    (tmp_path / ledger.LEDGER_NAME).write_text(original)

    book = ledger.Ledger(tmp_path).load()
    book.add_run(*_run("2026-09-01"))
    book.write()

    assert book.load_error, f"{shape}: read as an empty history rather than a bad one"
    assert [q.read_text() for q in ledger.quarantined(tmp_path)] == [original], (
        f"{shape}: the year that was in there is not recoverable")
    assert [r["date"] for r in book.runs] == ["2026-09-01"], (
        f"{shape}: the run that just happened has to survive the file it could not read")
    assert json.loads((tmp_path / ledger.LEDGER_NAME).read_text())["runs"]


def test_a_day_number_is_never_computed_over_the_rows_that_survived_a_bad_read(tmp_path):
    """The half-junk case's own harm, which is not data loss.

    A ledger whose rows are half junk used to load the other half and say
    nothing, and the run then published "day 3 of this setup" -- a confident
    number over a record it had silently mutilated. Every appearance the filter
    dropped is a session the streak thinks nobody scanned.

    Pinned from both sides so it cannot pass because the day was unknown
    anyway: the same file with the junk row removed answers day 3.
    """
    days = [d.date().isoformat() for d in pd.bdate_range(end="2026-08-31", periods=12)]
    runs = [{"date": day, "type": "evening", "gated": [],
             "candidates": ([{"ticker": "AAA", "date": day, "score": 7.0,
                              "verdict": "B"}] if day in days[-2:] else [])}
            for day in reversed(days)]
    whole = {"schema_version": ledger.SCHEMA_VERSION, "app": "SpicyStock",
             "generated": "2026-08-31T22:11:04Z", "runs": runs}

    (tmp_path / ledger.LEDGER_NAME).write_text(json.dumps(whole))
    clean = ledger.Ledger(tmp_path).load()
    assert ledger.streaks(clean.runs, ["AAA"], "2026-09-01",
                          unreadable=clean.load_error)["AAA"]["day"] == 3, (
        "the precondition: this record does answer, so the answer below is "
        "withheld by the junk row and not by the arithmetic")

    (tmp_path / ledger.LEDGER_NAME).write_text(
        json.dumps({**whole, "runs": [runs[0], "hand-edited out", *runs[1:]]}))
    book = ledger.Ledger(tmp_path).load()
    mark = ledger.streaks(book.runs, ["AAA"], "2026-09-01",
                          unreadable=book.load_error)["AAA"]

    assert mark["day"] is None, "a day counted over the rows that happened to parse"
    assert mark["unknown_reason"] == ledger.HISTORY_UNREADABLE


def test_a_ledger_from_another_schema_is_not_merged_into(tmp_path, caplog):
    (tmp_path / ledger.LEDGER_NAME).write_text(json.dumps(
        {"schema_version": 99, "runs": [{"date": "2026-01-01", "type": "evening"}]}))

    book = ledger.Ledger(tmp_path).load()

    assert book.runs == []
    assert "schema_version" in caplog.text
    assert [q.read_text() for q in ledger.quarantined(tmp_path)], (
        "a ledger from another schema is kept, not written over")


def test_forward_returns_are_filled_into_an_earlier_run(tmp_path):
    book = ledger.Ledger(tmp_path).load()
    book.add_run(*_run("2026-08-24"))
    book.add_run(*_run("2026-08-31"))
    df = frame([100, 101, 102, 103, 104, 110], end="2026-08-31")
    assert df.index[0].date() == date(2026, 8, 24)

    filled = book.fill_forward_returns({"AAA": df, "ZZZ": df}, through=date(2026, 8, 31))

    old = [r for r in book.runs if r["date"] == "2026-08-24"][0]
    assert filled == 2, "the scored row and the gated one"
    assert old["candidates"][0]["forward_returns"] == {
        "d1": 1.0, "d3": 3.0, "d5": 10.0, "as_of": "2026-08-31"}
    assert old["forward_returns"] == {"d1": 1.0, "d3": 3.0, "d5": 10.0,
                                      "n": 1, "rows": 1}, (
        "the run mean covers the scored candidates, one setup from one row")


def test_todays_own_candidates_are_not_asked_for_a_return_that_cannot_exist(tmp_path):
    book = ledger.Ledger(tmp_path).load()
    book.add_run(*_run("2026-08-31"))

    assert book.pending_tickers(through=date(2026, 8, 31)) == []


def test_a_backfill_of_a_session_older_than_the_history_still_publishes_its_own(tmp_path):
    """`runs` is ordered by session, so a run scanning an older session than
    one already recorded is NOT the head of the ledger. Reading the head
    published a snapshot whose candidates all said "pending" while the ledger
    beside it held their returns."""
    book = ledger.Ledger(tmp_path).load()
    book.add_run(*_run("2026-08-31"))                     # already recorded
    run, candidates, gated = _run("2026-08-24")           # ...now backfill an older one
    book.add_run(run, candidates, gated)
    assert book.runs[0]["date"] == "2026-08-31", "the backfill is not the head"

    book.fill_forward_returns({"AAA": frame([100, 101, 102, 103, 104, 110],
                                            end="2026-08-31")},
                              through=date(2026, 8, 31))

    (published,) = [c for c in book.latest["candidates"] if c["ticker"] == "AAA"]
    assert published["forward_returns"] == {"d1": 1.0, "d3": 3.0, "d5": 10.0,
                                            "as_of": "2026-08-31"}
    assert book.dashboard()["candidates"][0]["forward_returns"]["d1"] == 1.0


def test_a_backfill_run_resolves_its_own_candidates(tmp_path):
    """Scanning an OLD session with SCAN_SESSION_DATE: everything after that
    burst has already happened, so the outcome is knowable in the same run."""
    book = ledger.Ledger(tmp_path).load()
    book.add_run(*_run("2026-08-24"))

    assert set(book.pending_tickers(through=date(2026, 8, 31))) == {"AAA", "ZZZ"}


def test_the_burst_close_comes_from_the_same_frame_as_the_later_one(tmp_path):
    """The split defence, and it is not theoretical: a 4-for-1 forward split
    restates every close before its ex-date, so the archived as-traded close
    divided into a split-adjusted one is a -75% return the market never
    printed. Both ends of the division come out of one adjusted frame.
    """
    book = ledger.Ledger(tmp_path).load()
    run, candidates, gated = _run("2026-08-24")
    candidates[0]["close"] = 400.0          # as traded, before a 4-for-1 split
    book.add_run(run, candidates, gated)
    df = frame([100, 101, 102, 103, 104, 110], end="2026-08-31")   # restated

    book.fill_forward_returns({"AAA": df}, through=date(2026, 8, 31))

    row = book.runs[0]["candidates"][0]
    assert row["close"] == 400.0, "the archive still records what was traded"
    assert row["forward_returns"]["d1"] == 1.0, (
        "a return of -74.75% here would mean the archived close was the denominator")


def test_a_return_already_recorded_is_not_rewritten(tmp_path):
    book = ledger.Ledger(tmp_path).load()
    book.add_run(*_run("2026-08-24"))
    book.fill_forward_returns({"AAA": frame([100, 101, 102, 103], end="2026-08-27")},
                              through=date(2026, 8, 31))
    first = dict(book.runs[0]["candidates"][0]["forward_returns"])

    book.fill_forward_returns({"AAA": frame([100, 500, 102, 103, 104, 110])},
                              through=date(2026, 8, 31))
    now = book.runs[0]["candidates"][0]["forward_returns"]

    assert now["d1"] == first["d1"] == 1.0, "a filled horizon is a fact, not a view"
    assert now["d5"] == 10.0, "and an empty one is still fillable"


def test_a_run_older_than_the_fill_window_is_left_alone(tmp_path, monkeypatch):
    """A row still incomplete after this many runs is a name that stopped
    trading; re-requesting it every night forever buys nothing.

    The run outside the window carries a ticker the runs inside it do not:
    every run used to hold the same two names, pending_tickers() de-duplicates
    by name, and so the expected list was the same whether the window existed
    or not -- the whole window could be deleted with this test green, and the
    backfill defect below lived under it.
    """
    monkeypatch.setattr(ledger, "FILL_WINDOW_RUNS", 2)
    book = ledger.Ledger(tmp_path).load()
    book.add_run(*_run("2026-08-24", ("OLDIE",)))
    for day in (25, 26):
        book.add_run(*_run(f"2026-08-{day}"))

    pending = book.pending_tickers(through=date(2026, 8, 31))

    assert "OLDIE" not in pending, "the run outside the window was offered"
    assert set(pending) == {"AAA", "ZZZ"}


def test_a_backfill_older_than_the_window_still_resolves_its_own_outcomes(tmp_path, monkeypatch):
    """README: "a run pinned to an old session resolves its own outcomes". It
    did not, from the eleventh session back: the window is the newest runs by
    SESSION, a SCAN_SESSION_DATE backfill of an older one landed outside it on
    the very run that scored it, and its rows stayed pending forever. The run
    just added is always in the window."""
    monkeypatch.setattr(ledger, "FILL_WINDOW_RUNS", 2)
    book = ledger.Ledger(tmp_path).load()
    for day in (25, 26, 27):
        book.add_run(*_run(f"2026-08-{day}"))
    book.add_run(*_run("2026-08-18", ("BACKFILL",)))     # older than every run in the window
    assert [r["date"] for r in book.runs][-1] == "2026-08-18", "precondition: it sorts last"

    assert "BACKFILL" in book.pending_tickers(through=date(2026, 8, 31))
    # And only because it is the run just added: the same entry loaded from
    # disk on a later night is outside the window again, as designed.
    book.write()
    later = ledger.Ledger(tmp_path).load()
    later.add_run(*_run("2026-08-28"))
    assert "BACKFILL" not in later.pending_tickers(through=date(2026, 8, 31))


# ===========================================================================
# What lands in the file
# ===========================================================================

def test_the_written_files_are_json_a_browser_can_parse(tmp_path):
    book = ledger.Ledger(tmp_path).load()
    book.add_run(*_run("2026-08-31"))

    written = book.write()

    for path in written.values():
        json.loads(path.read_text())          # raises on a bare NaN token


def test_a_nan_is_refused_rather_than_written_as_a_bare_token(tmp_path):
    book = ledger.Ledger(tmp_path).load()
    run, candidates, gated = _run("2026-08-31")
    candidates[0]["score"] = float("nan")
    book.add_run(run, candidates, gated)

    with pytest.raises(ValueError):
        book.write()


def test_numbers_from_pandas_survive_the_trip():
    """np.float64 and np.bool_ are what a frame hands back. json.dump refuses
    np.bool_ outright and writes a NaN as a token no parser reads back, so
    every value that reaches the file goes through _num() or check_rows()."""
    series = pd.Series([1.5, float("nan")])
    numpy_bool = series.iloc[0] > 1

    with pytest.raises(TypeError):
        json.dumps({"pass": numpy_bool})          # this is what is being prevented

    assert ledger._num(series.iloc[0]) == 1.5
    assert ledger._num(series.iloc[1]) is None
    assert ledger._num("n/a") is None and ledger._num(None) is None
    row = ledger.check_rows({"checks": {"N_narrow": {"pass": numpy_bool, "value": "v"}}})
    assert json.dumps(row, allow_nan=False)


def test_a_chart_outside_docs_is_not_offered_to_a_page_that_cannot_serve_it(tmp_path):
    assert ledger.chart_ref(str(tmp_path / "charts" / "AAA.png"), tmp_path) == "charts/AAA.png"
    assert ledger.chart_ref("/elsewhere/AAA.png", tmp_path) is None
    assert ledger.chart_ref(None, tmp_path) is None


def test_the_checklist_labels_are_derived_from_the_checks_themselves():
    """Not copied into a table here: a renamed check renames its own label."""
    result = {"checks": {"2_first_or_second_burst": {"pass": True, "value": "0 prior"},
                         "H_close_near_high": {"pass": False, "value": "closed at 40%"}}}

    assert ledger.check_rows(result) == [
        {"code": "2", "label": "first or second burst", "pass": True, "value": "0 prior"},
        {"code": "H", "label": "close near high", "pass": False, "value": "closed at 40%"},
    ]
    assert ledger.check_flags(result) == {"2": True, "H": False}


def test_the_fixture_generator_and_the_pipeline_describe_one_contract():
    """tools/make_fixture.py imports this list rather than holding a copy, so
    the hand-authored fixture and a real run cannot promise different things."""
    committed = json.loads((ledger.Path(__file__).resolve().parent.parent
                            / "tests" / "fixtures" / "data.json").read_text())

    assert committed["_contract"]["invariants"] == ledger.CONTRACT_INVARIANTS


# ===========================================================================
# Step 10 -- streaks: the same setup, seen again
#
# Every run before this one started from nothing, so a name that burst on
# Monday and still cleared the filter on Tuesday arrived as a brand-new day-1
# idea both nights. The ledger held every one of those earlier appearances and
# was only ever written to.
#
# What "the same setup" means is a judgement, not arithmetic, and it lives in
# ledger.MAX_STREAK_GAP_SESSIONS. These tests read the boundary off that
# constant so a retune keeps testing the rule -- and then pin the constant
# itself, the way tests/test_scanner.py pins the scan thresholds, so that
# moving it is deliberate enough to edit a test.
# ===========================================================================

MON, TUE, WED = "2026-08-31", "2026-09-01", "2026-09-02"

#: A record that has looked back months before anything these tests scan.
#: Passed wherever a test asserts a day NUMBER, because src.ledger publishes
#: one only where the file reaches back past the streak window -- see "how far
#: back the record has looked" below, which is the section that varies this
#: instead of holding it still.
DEEP = date(2026, 1, 2)

#: The same record as a Record: how far back the file reaches, how many
#: sessions it holds, and how many run entries those came from. Passed wherever
#: a test asserts a day NUMBER, for the same reason DEEP is.
DEEP_RECORD = ledger.Record(DEEP, 160, 160)

#: What every block computed against DEEP_RECORD reports about the record it
#: was computed against. Spelled once: it is the same pair on every row of a
#: run, because it describes the file and not the name.
DEEP_SPAN = {"history_from": DEEP.isoformat(), "history_sessions": 160}


def _seen(session: str, *, score=None, verdict=None, ticker="AAA",
          gated: bool = False, reason: str = "lynch_gate") -> dict:
    """One ledger run in which `ticker` burst on `session`."""
    row = {"ticker": ticker, "date": session, "score": score, "verdict": verdict}
    if gated:
        row["reason"] = reason
    key = "gated" if gated else "candidates"
    return {"date": session, "type": "evening", key: [row]}


def _scanned(session: str) -> dict:
    """A run that scanned that session and found nothing worth recording.

    What makes a record DEEP rather than merely old: the ledger has looked at
    that night. A ledger with no run before the streak window cannot tell
    "nothing burst" from "nobody looked", which is the whole of _why_no_day().
    """
    return {"date": session, "type": "evening", "candidates": [], "gated": []}


def test_sessions_between_counts_sessions_not_calendar_days():
    """Friday to Monday is one session, not three. A streak measured in
    calendar days would break over every weekend."""
    assert ledger.sessions_between("2026-08-28", "2026-08-31") == 1
    assert ledger.sessions_between(MON, TUE) == 1
    assert ledger.sessions_between(MON, MON) == 0
    assert ledger.sessions_between("nonsense", MON) is None


def test_a_name_a_deep_record_has_never_carried_is_day_one_of_a_new_setup():
    """The precondition for every test below: day 1 is not simply what this
    function always says. It is what a record that has LOOKED far enough back
    and found nothing says -- and only then."""
    assert ledger.streak([], TUE, record=DEEP_RECORD) == {
        "day": 1, "unknown_reason": None, "first_seen": TUE, "last_seen": None,
        "last_score": None, "last_verdict": None, "last_outcome": None,
        "seen_before": 0, **DEEP_SPAN}


def test_a_name_that_burst_yesterday_is_day_two_today():
    """THE case the step exists for: seen on Monday, seen again on Tuesday."""
    history = ledger.appearance_index([_seen(MON, score=7.5, verdict="B")])

    assert ledger.streak(history["AAA"], TUE, record=DEEP_RECORD) == {
        "day": 2, "unknown_reason": None, "first_seen": MON, "last_seen": MON,
        "last_score": 7.5, "last_verdict": "B", "last_outcome": "scored",
        "seen_before": 1, **DEEP_SPAN}


def test_three_consecutive_sessions_are_day_three():
    history = ledger.appearance_index([_seen(MON), _seen(TUE)])
    assert ledger.streak(history["AAA"], WED, record=DEEP_RECORD)["day"] == 3


def test_a_gap_of_exactly_the_limit_is_still_the_same_setup():
    """Read off MAX_STREAK_GAP_SESSIONS, and asserted from BOTH sides: the
    boundary is the whole rule, and an off-by-one here is the difference
    between "day 2 of this move" and "a new setup"."""
    limit = ledger.MAX_STREAK_GAP_SESSIONS
    session = pd.bdate_range(start=MON, periods=limit + 1)[-1].date().isoformat()
    history = ledger.appearance_index([_seen(MON)])

    assert ledger.sessions_between(MON, session) == limit
    assert ledger.streak(history["AAA"], session, record=DEEP_RECORD)["day"] == 2, (
        "a burst inside the window the first one's outcome is measured over")


def test_a_gap_of_one_more_than_the_limit_starts_a_new_setup():
    """The other side. A name reappearing after a full base is day 1 of
    something new, not day N of a move that finished -- but the ledger still
    says when it was last seen, because that is a fact and a useful one."""
    limit = ledger.MAX_STREAK_GAP_SESSIONS
    session = pd.bdate_range(start=MON, periods=limit + 2)[-1].date().isoformat()
    history = ledger.appearance_index([_seen(MON, score=6.0, verdict="C")])

    assert ledger.sessions_between(MON, session) == limit + 1
    streak = ledger.streak(history["AAA"], session, record=DEEP_RECORD)
    assert streak["day"] == 1 and streak["first_seen"] == session
    assert streak["last_seen"] == MON and streak["seen_before"] == 1
    assert (streak["last_score"], streak["last_verdict"]) == (6.0, "C")


def test_a_ticker_two_weeks_later_is_not_day_twelve():
    """The example the rule was written against."""
    history = ledger.appearance_index([_seen("2026-08-17")])
    assert ledger.streak(history["AAA"], MON, record=DEEP_RECORD)["day"] == 1


def test_the_gap_that_defines_one_setup_is_the_window_outcomes_are_measured_over():
    """A strategy change has to be deliberate enough to edit a test.

    Every test above reads the boundary off the constant, so all of them keep
    passing if it is retuned -- which means not one of them would notice. This
    is the other half: the gap is max(HORIZONS), because two bursts belong to
    one episode exactly while the first one's outcome is still being measured.
    """
    assert ledger.MAX_STREAK_GAP_SESSIONS == 5
    assert ledger.MAX_STREAK_GAP_SESSIONS == max(ledger.HORIZONS)


def test_a_burst_the_gate_rejected_still_counts_as_an_appearance():
    """The setup was there whether or not the checklist let it through to a
    score, and the reader is being told about the setup."""
    history = ledger.appearance_index([_seen(MON, gated=True)])
    streak = ledger.streak(history["AAA"], TUE, record=DEEP_RECORD)

    assert streak["day"] == 2
    assert streak["last_score"] is None and streak["last_verdict"] is None, (
        "it was never scored, and the row must not invent a judgement")


def test_a_burst_the_gate_rejected_says_so_rather_than_saying_nothing():
    """"Not scored then" reads as an absence of judgement -- the night the
    model was down -- and it was being printed over a name the pipeline had
    looked at and thrown out at the quality gate. Beside "day 2", which reads
    as accumulating confirmation, that is the same reader question answered
    two contradictory ways.
    """
    history = ledger.appearance_index([_seen(MON, gated=True, reason="lynch_gate")])

    assert ledger.streak(history["AAA"], TUE,
                         record=DEEP_RECORD)["last_outcome"] == "lynch_gate"


def test_the_two_ways_a_burst_goes_unscored_do_not_render_the_same():
    """A name the checklist REJECTED and one it passed that lost its place to
    twenty-five better names are different facts about the night, and both
    used to arrive as "not scored then". The reason is in the ledger row;
    until now it was dropped on the way to the streak."""
    gated = ledger.appearance_index([_seen(MON, gated=True, reason="lynch_gate")])
    capped = ledger.appearance_index([_seen(MON, gated=True, reason="score_cap")])

    assert (ledger.streak(gated["AAA"], TUE, record=DEEP_RECORD)["last_outcome"]
            != ledger.streak(capped["AAA"], TUE, record=DEEP_RECORD)["last_outcome"])
    assert ledger.streak(capped["AAA"], TUE,
                         record=DEEP_RECORD)["last_outcome"] == "score_cap"


def test_an_appearance_that_was_scored_says_so_even_with_no_number():
    """The case "not scored then" was built for and still got wrong: Claude was
    down, the fallback produced nothing, and the row carries no score. That is
    an absence of judgement -- and it has to be distinguishable from a
    rejection, which is exactly what a null score alone could not do."""
    history = ledger.appearance_index([_seen(MON, score=None, verdict=None)])

    streak = ledger.streak(history["AAA"], TUE, record=DEEP_RECORD)

    assert streak["last_outcome"] == "scored" and streak["last_score"] is None


def test_an_appearance_on_the_session_being_scanned_is_not_a_repeat_of_itself():
    """A run repeated after a failure re-scans a session already in the
    ledger. Counting the first attempt would report every name in it as day 2
    of a setup it started that same evening."""
    history = ledger.appearance_index([_seen(TUE, score=7.0)])
    assert ledger.streak(history["AAA"], TUE, record=DEEP_RECORD)["day"] == 1


def test_a_backfill_does_not_count_the_newer_runs_sitting_above_it():
    """SCAN_SESSION_DATE puts an old session into a ledger that already holds
    newer ones. Which appearances are prior is decided by DATE, not by where
    the entry landed in the file."""
    history = ledger.appearance_index([_seen(WED), _seen(MON)])
    assert ledger.streak(history["AAA"], TUE, record=DEEP_RECORD) == {
        "day": 2, "unknown_reason": None, "first_seen": MON, "last_seen": MON,
        "last_score": None, "last_verdict": None, "last_outcome": "scored",
        "seen_before": 1, **DEEP_SPAN}


def test_one_session_scanned_twice_is_one_appearance():
    """A morning and an evening entry for the same session are two ledger
    rows and one burst. Counting both would inflate every streak by one."""
    history = ledger.appearance_index([
        dict(_seen(MON, score=7.5, verdict="B")),
        dict(_seen(MON), type="morning"),
    ])
    assert len(history["AAA"]) == 1
    assert ledger.streak(history["AAA"], TUE, record=DEEP_RECORD) == {
        "day": 2, "unknown_reason": None, "first_seen": MON, "last_seen": MON,
        "last_score": 7.5, "last_verdict": "B", "last_outcome": "scored",
        "seen_before": 1, **DEEP_SPAN}


def test_seen_before_counts_every_earlier_sighting_not_just_this_setup():
    history = ledger.appearance_index([_seen("2026-06-01"), _seen("2026-07-01"),
                                       _seen(MON)])
    streak = ledger.streak(history["AAA"], TUE, record=DEEP_RECORD)
    assert (streak["day"], streak["seen_before"]) == (2, 3)


def test_last_seen_is_the_most_recent_sighting_not_the_first():
    """With several earlier appearances the two are different dates, and only
    one of them answers "when did I last look at this". Asserted over three
    sightings on purpose: with one prior appearance the newest and the oldest
    are the same row, and a test built on that cannot tell them apart.
    """
    history = ledger.appearance_index([
        _seen("2026-06-01", score=4.0, verdict="skip"),
        _seen("2026-07-01", score=9.0, verdict="A+"),
        _seen(MON, score=6.5, verdict="B"),
    ])

    streak = ledger.streak(history["AAA"], TUE, record=DEEP_RECORD)

    assert streak["last_seen"] == MON
    assert (streak["last_score"], streak["last_verdict"]) == (6.5, "B"), (
        "the judgement belongs to the sighting last_seen names, and no other")


def test_streaks_answers_for_every_name_it_is_asked_about():
    runs = [_scanned("2026-06-01"), _seen(MON, score=7.5, verdict="B"),
            _seen(MON, ticker="BBB", gated=True)]
    marks = ledger.streaks(runs, ["AAA", "BBB", "NEW"], TUE)

    assert marks["AAA"]["day"] == 2 and marks["BBB"]["day"] == 2
    assert marks["NEW"] == {"day": 1, "unknown_reason": None, "first_seen": TUE,
                            "last_seen": None, "last_score": None,
                            "last_verdict": None, "last_outcome": None,
                            "seen_before": 0, "history_from": "2026-06-01",
                            "history_sessions": 2}, (
        "and the span it was measured over, which is the same on every row: "
        "two sessions in the file, the older of them 2026-06-01")


# --- how far back the record has looked -------------------------------------
# Absence of evidence is only evidence of absence once you have looked far
# enough back. Everything above passes a record that HAS; these are the tests
# that vary it, and they are the ones that stop "day 1 -- new setup" from
# being a sentence this module writes over an empty file.


def test_an_empty_history_will_not_say_day_one_because_it_has_not_looked():
    """REPLACES a test that asserted the opposite, and whose docstring said
    "every name really is on day 1 and the record says so" -- two different
    statements, only the second of which a file with nothing in it supports.

    It was not a corner case. docs/ledger.json is not committed, so the first
    production run prints this against every candidate; it recurs whenever
    MAX_RUNS rolls a name off and on the night after a history is set aside.
    And it shipped in the same email row as `FAIL 2_first_or_second_burst: 2
    prior 4% bursts in last 20 days`, three lines below -- the price frame had
    looked back twenty sessions, the ledger had looked back none, and they
    answered one reader's question in opposite directions.
    """
    mark = ledger.streaks([], ["AAA"], TUE)["AAA"]

    assert mark["day"] is None, "an empty file cannot know that this setup is new"
    assert mark["unknown_reason"] == ledger.NO_HISTORY
    assert mark["first_seen"] is None, "and cannot say when it began either"


def test_a_record_that_stops_short_of_the_window_cannot_count_days():
    """One night in the file is not a history. A name absent from it might
    have burst the session before, in a night nobody scanned."""
    marks = ledger.streaks([_scanned(MON)], ["AAA"], TUE)

    assert marks["AAA"]["day"] is None
    assert marks["AAA"]["unknown_reason"] == ledger.WINDOW_NOT_COVERED


def test_the_record_must_reach_back_the_whole_streak_window():
    """The boundary, from both sides and read off the constant. Reaching back
    exactly the window is enough -- an earlier appearance inside it would have
    joined this setup, so a file that covers it and holds none has looked.
    """
    limit = ledger.MAX_STREAK_GAP_SESSIONS
    days = pd.bdate_range(end=TUE, periods=limit + 1)
    just_enough, one_short = (days[0].date().isoformat(),
                              days[1].date().isoformat())

    assert ledger.sessions_between(just_enough, TUE) == limit
    assert ledger.streaks([_scanned(just_enough)], ["AAA"], TUE)["AAA"]["day"] == 1
    assert ledger.sessions_between(one_short, TUE) == limit - 1
    assert ledger.streaks([_scanned(one_short)], ["AAA"], TUE)["AAA"]["day"] is None


def test_a_repeat_the_record_cannot_place_still_says_when_it_was_last_seen():
    """The unknown is `day`, not the file. What the ledger holds -- the last
    sighting, what happened to it, how many there were -- is fact and stays;
    only the two claims about what came BEFORE the earliest one in view are
    withdrawn."""
    runs = [_seen(MON, score=7.5, verdict="B")]

    mark = ledger.streaks(runs, ["AAA"], TUE)["AAA"]

    assert mark["day"] is None and mark["first_seen"] is None
    assert mark["unknown_reason"] == ledger.WINDOW_NOT_COVERED
    assert mark["last_seen"] == MON and mark["seen_before"] == 1
    assert (mark["last_score"], mark["last_outcome"]) == (7.5, "scored")


def test_the_window_is_measured_from_where_the_setup_started():
    """A chain reaching back near the oldest run in the file makes day 1's
    claim -- "nothing preceded THIS" -- one session further back, so that is
    where the window has to be covered: before the setup's FIRST session, not
    before tonight's. A name bursting every session since the file began is
    not demonstrably on day 3 rather than day 8.

    Built so the two readings disagree, and pinned so it stays that way: the
    file reaches a full window back from TONIGHT, which is what the rule as
    first written asked for, and two sessions back from where this setup
    started, which is what the claim actually needs.
    """
    runs = [_scanned("2026-08-25"), _seen("2026-08-27"), _seen(MON)]

    assert ledger.sessions_between("2026-08-25", TUE) == ledger.MAX_STREAK_GAP_SESSIONS
    assert ledger.sessions_between("2026-08-25", "2026-08-27") == 2
    assert ledger.streaks(runs, ["AAA"], TUE)["AAA"]["day"] is None, (
        "measured from tonight the file looks deep enough, and it is not: "
        "nobody scanned the four sessions before this setup's first burst")

    reaching = [_scanned("2026-08-18")] + runs
    assert ledger.streaks(reaching, ["AAA"], TUE)["AAA"]["day"] == 3


# --- what the unknown is unknown OVER ---------------------------------------
# Every test above is about whether a day number may be published. These are
# about what is said when it may not, which until now was nothing at all.


def test_an_unbroken_streak_says_what_it_is_unknown_over():
    """THE inversion the record fields exist for, measured over nine nights.

    A name bursting every session since the ledger began has a chain that
    reaches the oldest run in it, so the reach is zero and `day` is null --
    every night, forever. A name that took a fortnight off and burst twice
    reads "day 2 of this setup" beside it. The feature is quietest about
    exactly the setups it exists to surface.

    The arithmetic is right and stays: you cannot prove a chain did not begin
    before your record did. What was wrong was saying nothing -- so the block
    now carries the record it was read out of, and a reader gets "burst on 8 of
    the 8 sessions in the record, which begins 2026-08-20, and may have started
    before it" where it could only say "streak unknown".
    """
    days = [d.date().isoformat() for d in pd.bdate_range(end="2026-09-01", periods=9)]
    every_night = [_seen(day) for day in days[:-1]]
    took_a_week_off = [_seen(days[-2], ticker="BBB")]

    marks = ledger.streaks(every_night + took_a_week_off, ["AAA", "BBB"], days[-1])

    assert marks["BBB"]["day"] == 2, (
        "the inversion, pinned: the name with one earlier burst gets a number")
    assert marks["AAA"]["day"] is None, "and the one on an eight-night run does not"
    assert marks["AAA"]["unknown_reason"] == ledger.WINDOW_NOT_COVERED
    # The three numbers the sentence is made of.
    assert marks["AAA"]["seen_before"] == 8
    assert marks["AAA"]["history_sessions"] == 8
    assert marks["AAA"]["history_from"] == days[0] == "2026-08-20"


def test_the_record_a_streak_names_is_the_files_and_not_the_names():
    """One pair per run, not per ticker: how far back the FILE looked is the
    same fact for every row in it, which is why it can be stated once on a page
    and repeated on every row of an email."""
    runs = [_scanned("2026-08-03"), _seen(MON), _seen(MON, ticker="BBB")]

    marks = ledger.streaks(runs, ["AAA", "BBB", "NEVER-SEEN"], TUE)

    assert {(m["history_from"], m["history_sessions"]) for m in marks.values()} == {
        ("2026-08-03", 2)}


def test_a_session_scanned_twice_is_one_session_of_record():
    """A morning and an evening run are two entries and one session that was
    looked at. Counting entries would inflate what a name is measured against
    -- "burst on 8 of the 14 sessions" over a file holding seven."""
    runs = [_seen(MON), dict(_seen(MON), type="morning"), _scanned("2026-08-28")]

    mark = ledger.streaks(runs, ["AAA"], TUE)["AAA"]

    assert mark["history_sessions"] == 2, "two sessions, three run entries"
    assert mark["seen_before"] <= mark["history_sessions"]


def test_a_record_with_nothing_in_it_reports_no_span_at_all():
    """The pair is null and 0 exactly when there is no record to describe, so
    a reader is never given a range a file does not cover."""
    empty = ledger.streaks([], ["AAA"], TUE)["AAA"]
    unread = ledger.streaks([], ["AAA"], TUE, unreadable="ledger.json is gibberish")["AAA"]

    for mark in (empty, unread):
        assert mark["history_from"] is None and mark["history_sessions"] == 0


def test_a_file_holding_runs_nobody_can_date_is_not_an_empty_one_either():
    """"No history has been recorded yet" is a false sentence about a file with
    a year of runs in it whose dates nothing can parse.

    Nothing is recoverable from in here either way -- both answer with no day
    number and no span -- but the two send a reader to different places: one to
    wait for the file to fill up, the other to go and look at it.
    """
    undated = [{"date": "the third", "type": "evening", "candidates": [], "gated": []},
               {"date": None, "type": "evening", "candidates": [], "gated": []}]

    mark = ledger.streaks(undated, ["AAA"], TUE)["AAA"]

    assert mark["unknown_reason"] == ledger.HISTORY_UNDATED
    assert ledger.streaks([], ["AAA"], TUE)["AAA"]["unknown_reason"] == ledger.NO_HISTORY, (
        "and an empty file still says the one true thing about itself")
    assert mark["history_from"] is None and mark["history_sessions"] == 0


def test_a_history_that_could_not_be_read_is_not_an_empty_one():
    """Two empty histories, and the difference is whether "we have never seen
    this name" is a claim about the market or about a file error. From in here
    they are the same `runs == []`, so the caller passes the difference in."""
    marks = ledger.streaks([], ["AAA"], TUE, unreadable="ledger.json is unreadable")

    assert marks["AAA"]["day"] is None
    assert marks["AAA"]["unknown_reason"] == ledger.HISTORY_UNREADABLE


def test_a_session_that_cannot_be_placed_is_not_a_new_setup_either():
    """A session this module cannot parse used to produce a confident day 1
    with a null first_seen -- a block that contradicted its own contract."""
    mark = ledger.streak([], "not a date", record=DEEP_RECORD)

    assert mark["day"] is None and mark["unknown_reason"] == ledger.WINDOW_NOT_COVERED


# --- one setup, one observation ---------------------------------------------


def test_consecutive_sessions_of_one_name_are_one_setup_to_an_average():
    """What setup_leads() is for. Five sessions of one move are five rows and
    one thing that happened, and their d1/d3/d5 windows overlap."""
    runs = [_seen(MON), _seen(TUE), _seen(WED)]

    assert ledger.setup_leads(runs) == {("AAA", MON)}, (
        "the first appearance stands for the setup: it is the one whose "
        "horizons are furthest along, and no later session can change it")


def test_a_burst_exactly_the_window_later_is_still_one_setup():
    """The boundary, read off the constant and the same one the streak uses:
    inside the window the first burst's outcome is still being measured, so the
    second session is the same episode -- and an average must not count it as a
    second observation."""
    limit = ledger.MAX_STREAK_GAP_SESSIONS
    later = pd.bdate_range(start=MON, periods=limit + 1)[-1].date().isoformat()

    assert ledger.sessions_between(MON, later) == limit
    assert ledger.setup_leads([_seen(MON), _seen(later)]) == {("AAA", MON)}


def test_a_name_that_comes_back_after_the_window_is_a_second_setup():
    """The inverse, and the reason this is not simply "one row per ticker": a
    name that based for a fortnight and burst again is a new move, and an
    average that dropped it would be under-counting rather than de-duplicating.
    """
    later = pd.bdate_range(start=MON, periods=ledger.MAX_STREAK_GAP_SESSIONS + 2)
    away = later[-1].date().isoformat()

    assert ledger.setup_leads([_seen(MON), _seen(away)]) == {("AAA", MON),
                                                             ("AAA", away)}


def test_a_gated_burst_leads_a_setup_the_same_way_a_scored_one_does():
    """Same rule as the streak: the scan found the burst either way, and a
    setup that started with a rejection is still one setup."""
    assert ledger.setup_leads([_seen(MON, gated=True), _seen(TUE)]) == {("AAA", MON)}


def test_two_names_bursting_together_are_two_setups():
    """The precondition: leads are per ticker, so this collapses appearances,
    not names."""
    assert ledger.setup_leads([_seen(MON), _seen(MON, ticker="BBB")]) == {
        ("AAA", MON), ("BBB", MON)}


# --- what load() says about why the history is empty ------------------------


def test_a_ledger_that_was_simply_never_written_is_not_an_error(tmp_path):
    """The precondition: load_error is not set on every empty history, or the
    first run this repo ever makes would report a problem it does not have."""
    book = ledger.Ledger(tmp_path).load()
    assert book.runs == [] and book.load_error is None


def test_a_ledger_that_could_not_be_read_says_so_rather_than_looking_empty(tmp_path):
    """Both empty histories used to be indistinguishable to the caller, and
    the difference is whether "we have never seen this name" is a claim about
    the market or about a file error."""
    (tmp_path / ledger.LEDGER_NAME).write_text("{not json")

    book = ledger.Ledger(tmp_path).load()

    assert book.runs == []
    assert book.load_error and "unreadable" in book.load_error


def test_a_failure_load_cannot_name_still_keeps_the_file_and_says_why(tmp_path):
    """RecursionError is neither an OSError nor a ValueError, and json.loads
    raises it on a deeply nested document. load() used to name the two
    failures it expected and let everything else out, so the one rule that
    matters here -- a history this module could not read is never written
    over -- held only for the failures somebody had thought of.
    """
    spoiled = "[" * 20_000 + "]" * 20_000
    (tmp_path / ledger.LEDGER_NAME).write_text(spoiled)

    book = ledger.Ledger(tmp_path).load()

    assert book.runs == []
    assert "RecursionError" in (book.load_error or "")
    assert [q.read_text() for q in ledger.quarantined(tmp_path)] == [spoiled]


def test_a_ledger_from_another_schema_says_which_one(tmp_path):
    (tmp_path / ledger.LEDGER_NAME).write_text(json.dumps({"schema_version": 99}))
    assert "99" in (ledger.Ledger(tmp_path).load().load_error or "")


# --- the snapshot a morning run follows through on --------------------------


def _snapshot(tmp_path, **overrides) -> dict:
    data = {"schema_version": ledger.SCHEMA_VERSION, "app": "SpicyStock",
            "run": {"date": MON, "type": "evening", "fixture": False},
            "candidates": [], "gated_out": [], "runs": []}
    data.update(overrides)
    (tmp_path / ledger.DATA_NAME).write_text(json.dumps(data))
    return data


def test_a_published_run_is_handed_back_with_no_complaint(tmp_path):
    """The precondition for the four refusals below."""
    written = _snapshot(tmp_path)
    assert ledger.read_snapshot(tmp_path) == (written, None)


def test_the_hand_authored_fixture_is_refused_by_name(tmp_path):
    """docs/data.json ships as a fixture of invented tickers. Mailing its rows
    as a morning watchlist would put made-up names in front of a reader as
    tonight's judgements, and would look exactly like a working run."""
    _snapshot(tmp_path, run={"date": MON, "type": "evening", "fixture": True})

    data, why = ledger.read_snapshot(tmp_path)

    assert data is None
    assert "fixture" in why and "never be mailed" in why


def test_a_missing_snapshot_is_a_reason_not_an_exception(tmp_path):
    data, why = ledger.read_snapshot(tmp_path)
    assert data is None and "does not exist" in why


def test_an_unparseable_snapshot_is_a_reason_not_an_exception(tmp_path):
    (tmp_path / ledger.DATA_NAME).write_text("{not json")
    data, why = ledger.read_snapshot(tmp_path)
    assert data is None and "could not be read" in why


def test_a_snapshot_too_deep_to_parse_is_a_reason_not_an_exception(tmp_path):
    """"Never raises" held only for the failures somebody had named. json.loads
    raises RecursionError -- neither an OSError nor a ValueError -- on a deeply
    nested document, and `python -m src.pipeline morning` against one exited
    FAILED where the design says DEGRADED and "there is nothing to follow
    through on". Ledger.load() was widened to a catch-all for exactly this;
    this one, its sibling, was left behind.
    """
    (tmp_path / ledger.DATA_NAME).write_text("[" * 100_000 + "]" * 100_000)

    data, why = ledger.read_snapshot(tmp_path)

    assert data is None and "RecursionError" in why


def test_a_snapshot_from_another_schema_is_refused(tmp_path):
    _snapshot(tmp_path, schema_version=99)
    data, why = ledger.read_snapshot(tmp_path)
    assert data is None and "schema_version 99" in why


def test_a_snapshot_with_no_run_in_it_is_refused(tmp_path):
    _snapshot(tmp_path, run=None)
    data, why = ledger.read_snapshot(tmp_path)
    assert data is None and "no run to follow through on" in why


# A run entry whose `date` will not parse is KEPT, not quarantined: the line is
# shape, not content, and one unreadable field is not grounds for setting a
# year of outcomes aside. But the record's span was read from those run dates
# alone while appearances were counted from the rows' own dates, so the two
# disagreed -- and a snapshot went out publishing `seen_before: 8` beside
# `history_sessions: 0`, breaking the invariant a test asserts is impossible,
# on a run that reported itself clean with exit 0.

def _undated_history(sessions: int) -> list[dict]:
    return [{"date": "not-a-date", "type": "evening",
             "candidates": [{"ticker": "RUNNER", "date": f"2026-08-{4 + i:02d}",
                             "score": 7.5, "verdict": "B+", "reason": None}],
             "gated": []}
            for i in range(sessions)]


def test_a_name_cannot_burst_on_more_sessions_than_the_record_holds():
    """The declared invariant, over the input that used to break it."""
    runs = _undated_history(8)
    streak = ledger.streaks(runs, ["RUNNER"], date(2026, 8, 14))["RUNNER"]
    assert streak["seen_before"] == 8
    assert streak["history_sessions"] >= streak["seen_before"], streak
    assert streak["history_from"] is not None, streak


def test_the_record_recovers_its_span_from_the_rows_when_the_run_dates_cannot():
    """The rows carry the session they burst on, which IS the session that run
    scanned -- so a run entry nobody can date is still placeable through them,
    and the sessions it looked at are not lost from the record."""
    record = ledger.Record.of(_undated_history(8))
    assert record.first == date(2026, 8, 4)
    assert record.sessions == 8
    assert record.entries == 8


def test_a_history_nothing_at_all_can_be_dated_still_says_so():
    """The inverse: recovering from the rows must not swallow the state where
    there is nothing to recover. An undatable file is not an empty one, and the
    reader is told different words for each."""
    runs = [{"date": "xx", "type": "evening",
             "candidates": [{"ticker": "A", "date": "yy", "score": 1}], "gated": []}]
    assert ledger.streaks(runs, ["A"], date(2026, 8, 14))["A"]["unknown_reason"] == \
        ledger.HISTORY_UNDATED
    assert ledger.streaks([], ["A"], date(2026, 8, 14))["A"]["unknown_reason"] == \
        ledger.NO_HISTORY


def test_undated_run_entries_are_counted_so_the_run_can_report_them():
    """A damaged record used to pass as clean. The count is what lets a run
    say its history is partly unreadable instead of reporting exit 0."""
    assert ledger.undated_runs(_undated_history(8)) == 8
    assert ledger.undated_runs([{"date": "2026-08-04"}]) == 0
    assert ledger.undated_runs([]) == 0
    assert ledger.undated_runs(["not a dict"]) == 0


# --- the fifth instance: the snapshot's rows, and one object inside a row ---
# read_snapshot() checked that `candidates` was a list and stopped. The same
# class as the four Ledger.load() already closes -- a reader accepts a shape
# it never indexes into, and a later consumer breaks -- one file over. And
# _malformed_rows() stopped at "rows are objects" while three readers index
# into the forward_returns object inside each one.


def _real_candidate_record() -> dict:
    """candidate_record() over a real Candidate, a real checklist and a real
    context -- the writer's own output, not a hand-written imitation of it."""
    from src.lynch import evaluate_2lynch, extra_context
    from src.scanner import Candidate
    from tests.synthetic import make_ohlcv

    frame = make_ohlcv("burst", seed=11)
    cand = Candidate(ticker="AAA", date="2026-08-31", close=44.8, gain_pct=12.0,
                     volume=25_000_000, prev_volume=3_000_000, volume_ratio=8.0,
                     avg_volume=3_100_000, dollar_volume=1.12e9, history=frame)
    score_row = {"score": 7.5, "verdict": "B+", "reason": "r", "key_risk": "k",
                 "provenance": {"source": "claude", "model": "m", "chart_seen": True,
                                "error": None},
                 "chart": "docs/charts/AAA.png"}
    return ledger.candidate_record(cand, evaluate_2lynch(frame), extra_context(frame),
                                   score_row, rank=1, docs_dir="docs",
                                   streak_block=_new_setup())


def test_every_required_key_is_one_the_pipeline_actually_writes():
    """A required key the writer never writes would refuse every snapshot for
    ever, and the first morning would be the first anyone heard of it."""
    assert ledger.SNAPSHOT_ROW_KEYS <= set(_real_candidate_record())


def test_the_required_keys_are_the_ones_the_run_really_needs(monkeypatch, tmp_path):
    """SNAPSHOT_ROW_KEYS is DERIVED here rather than maintained by hand.

    For every key candidate_record() writes: drop it from every row, bypass the
    missing-key refusal, and run the real morning follow-through and the real
    email renderer. A key whose absence breaks the run must be required; a key
    whose absence the run survives must not be, because requiring it costs a
    genuine snapshot the first morning after any deploy that adds a field --
    docs/data.json still holds yesterday's run, written by yesterday's code.

    This is what stops the required set being a second copy of src.emailer.
    Nothing here reads the emailer; it runs it. 9 of the 23 keys are
    load-bearing, and if that changes this fails rather than the 8:30 email.
    """
    import json as _json

    from tests.fakes import FakeResend

    written = _real_candidate_record()
    monkeypatch.setattr(ledger, "snapshot_problem", lambda data: None)
    monkeypatch.setenv("RESEND_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("RESEND_FROM", "tests@example.invalid")
    monkeypatch.setenv("EMAIL_TO", "one@example.invalid")
    monkeypatch.delenv("SCAN_SESSION_DATE", raising=False)
    import resend
    double = FakeResend()
    monkeypatch.setattr(resend.Emails, "send", lambda params, options=None: double.send(params))

    source = _json.loads((ledger.Path(__file__).resolve().parent
                          / "fixtures" / "history" / "data.json").read_text())
    source["run"]["fixture"] = False

    needed = set()
    for key in sorted(written):
        docs = tmp_path / key
        (docs / "docs").mkdir(parents=True)
        document = _json.loads(_json.dumps(source))
        for row in document["candidates"]:
            row.pop(key, None)
        (docs / "docs" / ledger.DATA_NAME).write_text(_json.dumps(document))
        monkeypatch.chdir(docs)
        double.sent.clear()
        try:
            pipeline.run("morning", dry_run=False, report=pipeline.RunReport())
            if not double.sent:
                needed.add(key)
        except Exception:      # noqa: BLE001 -- the point of the experiment
            needed.add(key)

    assert needed == set(ledger.SNAPSHOT_ROW_KEYS), (
        f"the run needs {sorted(needed)} but the reader requires "
        f"{sorted(ledger.SNAPSHOT_ROW_KEYS)}"
    )


def test_a_snapshot_whose_rows_are_not_rows_is_refused_by_name(tmp_path):
    """`"candidates": ["AAPL"]` loaded, passed the list check, and became an
    AttributeError out of the morning run -- FAILED and exit 1 where the design
    says DEGRADED and "there is nothing to follow through on"."""
    _snapshot(tmp_path, candidates=["AAPL"])

    data, why = ledger.read_snapshot(tmp_path)

    assert data is None
    assert "did not come out of a run" in why and "row 1 is a JSON str" in why


def _snapshot_row(**over) -> dict:
    return dict(_candidate("AAA", 1, 7.0), **over)


@pytest.mark.parametrize("candidates, names", [
    ([None], ["row 1", "NoneType"]),
    ([{"ticker": "AAA"}], ["row 1", "missing", "score", "verdict", "close"]),
    ([_snapshot_row(ticker=42)], ["row 1", "int", "ticker"]),
    ([_snapshot_row(lynch_detail="4/6")], ["AAA", "lynch_detail", "not a list of checks"]),
    ([_snapshot_row(lynch_detail=["PASS 2"])], ["AAA", "lynch_detail"]),
    ([_snapshot_row(streak="day 3")], ["AAA", "str", "streak"]),
    ([_snapshot_row(provenance="claude")], ["AAA", "str", "provenance"]),
    ([_snapshot_row(), _snapshot_row(forward_returns=[1, 2])], ["row 2", "list", "forward_returns"]),
])
def test_a_snapshot_row_of_the_wrong_shape_is_refused_and_named(tmp_path, candidates, names):
    """Every one of these reached the follow-through as a watchlist and crashed
    it somewhere downstream -- in email_row(), in the subject line's join, in
    the checklist lines. The reason names the row and the field, because the
    morning email is where an operator reads it."""
    _snapshot(tmp_path, candidates=candidates)

    data, why = ledger.read_snapshot(tmp_path)

    assert data is None
    for name in names:
        assert name in why, (name, why)


@pytest.mark.parametrize("run_field, value", [
    ("status", {"a": 1}), ("status", 5), ("scored_by", "x"), ("scored_by", [1, 2]),
])
def test_a_run_block_of_the_wrong_shape_is_refused(tmp_path, run_field, value):
    """`status` is upper-cased by the follow-through and `scored_by` is
    indexed by the email's provenance line; neither had a guard."""
    _snapshot(tmp_path, run={"date": MON, "type": "evening", "fixture": False,
                             run_field: value})

    data, why = ledger.read_snapshot(tmp_path)

    assert data is None and f"run.{run_field}" in why


def test_a_snapshot_row_the_writer_produced_is_not_refused(tmp_path):
    """The precondition for every refusal above: the writer's own row passes,
    with a null streak and a null forward return, which are both shapes the
    pipeline legitimately publishes."""
    row = dict(_real_candidate_record(), streak=None)
    _snapshot(tmp_path, candidates=[row])

    data, why = ledger.read_snapshot(tmp_path)

    assert why is None and data["candidates"] == [row]


@pytest.mark.parametrize("returns", ["x", None, [1, 2], 7])
def test_a_ledger_row_whose_forward_returns_is_not_an_object_is_set_aside(tmp_path, returns):
    """It used to load with no error, compute every streak, and then take the
    evening run down inside add_run() -- after the scan and every Claude call
    had been paid for, before write(). Reproduced with a one-row ledger.

    Set aside, not tolerated: the file is still there to be repaired, which
    is the one thing the module promises about a file it cannot read, and the
    run that follows completes.
    """
    # Written by the module and then edited on disk, the way such a file
    # arrives: add_run() cannot be made to write this shape, which is the
    # point -- a file holding it did not come out of write().
    book = ledger.Ledger(tmp_path).load()
    book.add_run(*_run("2026-08-28"))
    book.write()
    stored = json.loads((tmp_path / ledger.LEDGER_NAME).read_text())
    stored["runs"][0]["candidates"][0]["forward_returns"] = returns
    (tmp_path / ledger.LEDGER_NAME).write_text(json.dumps(stored))

    reloaded = ledger.Ledger(tmp_path).load()

    assert reloaded.runs == []
    assert "forward_returns" in reloaded.load_error and "'AAA'" in reloaded.load_error
    assert len(ledger.quarantined(tmp_path)) == 1, "the file was kept, not overwritten"
    reloaded.add_run(*_run("2026-08-31"))      # the call that used to raise
    reloaded.write()
    assert json.loads((tmp_path / ledger.LEDGER_NAME).read_text())["runs"][0]["date"] == "2026-08-31"


@pytest.mark.parametrize("block, expected", [
    ({"day": 3}, 3), ({"day": 3.0}, 3.0), ({"day": None}, None), ({"day": "3"}, None),
    ({"day": True}, None), ({}, None), ("day 3", None), (None, None),
])
def test_a_streak_day_is_a_number_or_it_is_nothing(block, expected):
    """One rule for the three places that compare `day > 1` against a value
    read off disk. `"3" > 1` is a TypeError; `True > 1` is a lie."""
    assert ledger.streak_day(block) == expected


# ===========================================================================
# Step 11 -- evidence(): the five questions, computed where the definitions are
#
# The page renders these numbers and does not recompute them, so what is
# asserted here is what the page is allowed to say. Two rules pull in opposite
# directions and both have to hold: everything is per SETUP, except by_day,
# which is per APPEARANCE and must be, because a setup's leading row is day 1
# by construction.
# ===========================================================================


def _record(sessions: list[tuple[str, tuple[str, ...]]], returns: dict | None = None,
            **run_extra) -> list[dict]:
    """A ledger's `runs`, built by the real Ledger, with returns filled in.

    `returns` maps (ticker, session) to a {d1,d3,d5} dict. Written through the
    stored rows rather than through fill_forward_returns() so a test can state
    an outcome without also having to state a price frame that produces it.
    """
    book = ledger.Ledger("unused")
    for session, tickers in sessions:
        run, candidates, gated = _run(session, tickers=tickers)
        run.update(run_extra)
        book.add_run(run, candidates, gated)
    for entry in book.runs:
        for row in entry["candidates"] + entry["gated"]:
            got = (returns or {}).get((row["ticker"], row["date"]))
            if got:
                row["forward_returns"] = {**ledger.empty_returns(), **got, "as_of": "x"}
    return book.runs


def test_the_evidence_counts_each_setup_once_however_many_sessions_it_burst_on():
    """The rule mean_returns() exists for, one level up.

    AAA bursts on three consecutive sessions -- one move, whose d5 windows
    overlap -- and BBB bursts once. Counting rows would weight AAA's move
    three times against BBB's and report a mean of the wrong thing.
    """
    runs = _record(
        [("2026-08-26", ("AAA",)), ("2026-08-25", ("AAA",)), ("2026-08-24", ("AAA", "BBB"))],
        returns={("AAA", "2026-08-24"): {"d5": 30.0}, ("AAA", "2026-08-25"): {"d5": 30.0},
                 ("AAA", "2026-08-26"): {"d5": 30.0}, ("BBB", "2026-08-24"): {"d5": 0.0}},
    )

    overall = ledger.at_horizon(ledger.evidence(runs)["overall"]["outcomes"], 5)

    assert overall["n"] == 2, "AAA's three sessions are one setup"
    assert overall["mean"] == 15.0, "not 22.5, which is what counting rows gives"


def _with_reason(runs: list[dict], ticker: str, reason, returns: dict) -> list[dict]:
    """Add one gated row to the newest run, with the reason word and outcome given.

    `_run` writes a single lynch_gate refusal per session; the control block
    splits refusals from the names the call cap crowded out, so a test of it
    needs both kinds on one night, and a row with no reason at all."""
    row = {"ticker": ticker, "date": runs[0]["date"], "close": 9.0, "gain_pct": 4.4,
           "volume": 5_000_000, "volume_ratio": 1.8, "lynch": "6/6", "lynch_passes": 6,
           "lynch_total": 6, "lynch_detail": _detail(6),
           "forward_returns": {**ledger.empty_returns(), **returns, "as_of": "x"}}
    if reason is not None:
        row["reason"] = reason
    runs[0]["gated"].append(row)
    return runs


def test_the_alternative_is_what_the_strategy_refused_and_not_what_the_budget_crowded_out():
    """The north star is "its picks beat THE ALTERNATIVE", and the record has
    always archived the alternative -- every refused burst, with the same
    forward returns -- without ever measuring against it.

    Two populations, and the split is the point. A name the checklist or a
    rule refused is the strategy's own judgement; a name that cleared the gate
    and was never scored because MAX_TO_SCORE filled is a fact about the
    budget. Folding the second into the first would let a full night pad the
    control with names the screener actually liked, which flatters the picks
    by exactly the amount those names went on to make.
    """
    runs = _record([("2026-08-24", ("AAA", "BBB"))],
                   returns={("AAA", "2026-08-24"): {"d5": 10.0}, ("BBB", "2026-08-24"): {"d5": 6.0},
                            ("ZZZ", "2026-08-24"): {"d5": 1.0}})   # _run's own lynch_gate refusal
    _with_reason(runs, "VVV", "veto_up_days", {"d5": 3.0})
    _with_reason(runs, "CCC", "score_cap", {"d5": 20.0})
    _with_reason(runs, "OLD", None, {"d5": 5.0})                      # written before reasons existed

    ev = ledger.evidence(runs)
    d5 = lambda block: ledger.at_horizon(ev[block]["outcomes"], 5)   # noqa: E731

    assert d5("overall")["mean"] == 8.0 and d5("overall")["n"] == 2
    assert ev["refused"]["setups"] == 3 and d5("refused")["mean"] == 3.0, (
        "the gate rejection, the veto and the reason-less row, and NOT the crowded-out one")
    assert ev["crowded_out"]["setups"] == 1 and d5("crowded_out")["mean"] == 20.0
    assert not ev["refused"]["enough"], "three setups is not a rate"


def test_the_illiquid_population_is_kept_beside_the_control_and_not_in_it():
    """Rule 6's refusals get a fifth population with the same shape as the
    other four, and they are NOT part of `refused`: their forward returns are
    bar prices on names the rule says are too thin to trade at those prices.
    Folding them in would let the thinnest names flatter or damn the
    strategy on returns nobody could capture. Deleting the population, or
    letting `refused` keep the rows, both fail here."""
    runs = _record([("2026-08-24", ("AAA",))],
                   returns={("AAA", "2026-08-24"): {"d5": 6.0}, ("ZZZ", "2026-08-24"): {"d5": 3.0}})
    _with_reason(runs, "VVV", "veto_up_days", {"d5": 3.0})
    _with_reason(runs, "CCC", "score_cap", {"d5": 20.0})
    _with_reason(runs, "THIN", ledger.LIQUIDITY_REASON, {"d5": 40.0})
    _with_reason(runs, "THN2", ledger.LIQUIDITY_REASON, {"d5": -10.0})

    ev = ledger.evidence(runs)
    d5 = lambda block: ledger.at_horizon(ev[block]["outcomes"], 5)   # noqa: E731

    assert ev["illiquid"]["setups"] == 2 and d5("illiquid")["mean"] == 15.0
    assert ev["refused"]["setups"] == 2 and d5("refused")["mean"] == 3.0, (
        "the control is the checklist's and the veto's verdict, not the floor's")
    assert ev["crowded_out"]["setups"] == 1
    assert set(ev["illiquid"]) == set(ev["refused"]) == {"setups", "outcomes", "enough"}
    assert not ev["illiquid"]["enough"]
    assert (ev["shortlist"]["setups"] + ev["rest"]["setups"] + ev["refused"]["setups"]
            + ev["crowded_out"]["setups"] + ev["illiquid"]["setups"]) == ev["record"]["setups"], (
        "five disjoint populations that together are every setup")


def test_a_setup_that_was_scored_once_is_a_pick_even_if_it_was_later_refused():
    """Leading rows only, the same rule every other block follows. AAA is
    scored on the 24th and refused by the gate on the 25th: one move, one
    setup, and it belongs to the population that led it. Counting the refusal
    too would put the same move on both sides of the comparison."""
    runs = _record([("2026-08-25", ()), ("2026-08-24", ("AAA",))],
                   returns={("AAA", "2026-08-24"): {"d5": 12.0}})
    runs[1]["gated"] = []   # _run plants a refused ZZZ on every session; not this test's subject
    # the 25th's run: AAA appears again, refused, with its own (later) window
    runs[0]["gated"] = [{"ticker": "AAA", "date": "2026-08-25", "close": 9.0, "gain_pct": 4.4,
                         "volume": 5_000_000, "volume_ratio": 1.8, "lynch": "2/6",
                         "lynch_passes": 2, "lynch_total": 6, "lynch_detail": _detail(2),
                         "reason": "lynch_gate",
                         "forward_returns": {**ledger.empty_returns(), "d5": -4.0, "as_of": "x"}}]

    ev = ledger.evidence(runs)

    assert ev["overall"]["setups"] == 1 and ledger.at_horizon(ev["overall"]["outcomes"], 5)["mean"] == 12.0
    assert ev["refused"]["setups"] == 0, "the 25th is the same setup, already counted as a pick"


def test_a_setup_refused_on_day_one_and_scored_on_day_two_is_a_pick_with_its_score():
    """The common case the veto produces -- a 6/6 name three up days into a
    run, allowed back the next session -- was invisible to every score-keyed
    block: the setup's LEAD is the refused row, `scored` kept only leads that
    were candidates, so the paid-for score and its outcome were in neither
    overall nor by_score nor by_month, by_ticker printed no best score, and
    the run's own mean skipped it. The committed history held three of them.
    And the same setup must be on ONE side of the control: a pick, not also
    a refusal."""
    runs = _record([("2026-08-25", ("AAA",)), ("2026-08-24", ())],
                   returns={("AAA", "2026-08-25"): {"d5": 15.0}})
    runs[1]["gated"] = [{"ticker": "AAA", "date": "2026-08-24", "close": 9.0, "gain_pct": 4.4,
                         "volume": 5_000_000, "volume_ratio": 1.8, "lynch": "6/6",
                         "lynch_passes": 6, "lynch_total": 6, "lynch_detail": _detail(6),
                         "reason": "veto_up_days", "checks": {"2": True},
                         "forward_returns": {**ledger.empty_returns(), "d5": 20.0, "as_of": "x"}}]
    runs[0]["gated"] = []
    runs[0]["candidates"][0]["score"] = 8.5

    ev = ledger.evidence(runs)

    assert ev["overall"]["setups"] == 1 and ledger.at_horizon(ev["overall"]["outcomes"], 5)["mean"] == 15.0
    assert ev["record"]["scored_setups"] == 1 and ev["record"]["setups"] == 1
    assert [b["verdict"] for b in ev["by_score"] if b["setups"]] == ["A"]
    assert ev["by_ticker"][0]["best_score"] == 8.5
    assert ev["refused"]["setups"] == 0, "the same move counted on both sides of the control"
    passed = next(c for c in ev["by_check"] if c["code"] == "2")
    assert passed["passed"]["setups"] == 1 and ledger.at_horizon(passed["passed"]["outcomes"], 5)["mean"] == 20.0, (
        "by_check still judges the FIRST appearance, whose verdict was passed on that day")


def test_a_run_scores_its_own_pick_even_when_an_earlier_refusal_led_the_setup():
    """The run-level mean, the same rule one level down -- and through the
    ledger's own recomputation, not with the lead set handed in by hand: the
    first version of this test did that, and a mutant that put the caller
    back on setup_leads() passed it."""
    book = ledger.Ledger("unused")
    day1, cands1, _ = _run("2026-08-24", ())
    day2, cands2, _ = _run("2026-08-25", ("AAA",))
    refused = {"ticker": "AAA", "date": "2026-08-24", "close": 9.0, "gain_pct": 4.4,
               "volume": 5_000_000, "volume_ratio": 1.8, "lynch": "6/6", "lynch_passes": 6,
               "lynch_total": 6, "lynch_detail": _detail(6), "reason": "veto_up_days",
               "forward_returns": ledger.empty_returns()}
    book.add_run(day1, cands1, [refused])
    book.add_run(day2, cands2, [])
    book.runs[0]["candidates"][0]["forward_returns"] = {**ledger.empty_returns(), "d5": 15.0, "as_of": "x"}

    book._recompute_means()

    assert book.runs[0]["forward_returns"]["n"] == 1
    assert book.runs[0]["forward_returns"]["d5"] == 15.0


@pytest.mark.parametrize("field, value, says", [
    ("checks", ["2", "L"], "checks is a JSON list"),
    ("checks", "2,L", "checks is a JSON str"),
    ("ticker", ["AAA"], "ticker is a JSON list"),
    ("ticker", 7, "ticker is a JSON int"),
    ("date", ["2026-08-25"], "date is a JSON list"),
    ("d5", "1.2", "d5 return is a JSON str"),
    ("d5", [1.2], "d5 return is a JSON list"),
    ("d5", True, "d5 return is a JSON bool"),
])
def test_the_sixth_instance_a_row_shape_the_readers_index_into_is_refused_at_load(
    tmp_path, field, value, says
):
    """Each of these loaded clean and took the EVENING run down after the scan
    and every Claude call were paid for -- and because the file was not set
    aside, every night after failed the same way. Refused at load now, set
    aside, and the run goes on over an empty history."""
    book = ledger.Ledger(tmp_path).load()
    book.add_run(*_run("2026-08-25"))
    book.write()
    saved = json.loads((tmp_path / ledger.LEDGER_NAME).read_text())
    row = saved["runs"][0]["candidates"][0]
    if field == "d5":
        row["forward_returns"]["d5"] = value
    else:
        row[field] = value
    (tmp_path / ledger.LEDGER_NAME).write_text(json.dumps(saved))

    later = ledger.Ledger(tmp_path).load()

    assert later.load_error and says in later.load_error, later.load_error
    assert later.runs == []
    assert len(ledger.quarantined(tmp_path)) == 1


def test_a_claude_scored_row_lands_in_its_verdict_bucket_with_its_outcome():
    """No test asserted that a scored row lands in a by_score bucket at all:
    a mutant restricting by_score to fallback rows -- emptying every bucket for
    real scores -- passed the suite, because the floor test compared an empty
    list to an empty list."""
    runs = _record([("2026-08-25", ("AAA",))], returns={("AAA", "2026-08-25"): {"d5": 12.0}})
    runs[0]["candidates"][0]["score"] = 8.5
    runs[0]["candidates"][0]["source"] = "claude"

    buckets = {b["verdict"]: b for b in ledger.evidence(runs)["by_score"] if b["setups"]}

    assert list(buckets) == ["A"]
    assert ledger.at_horizon(buckets["A"]["outcomes"], 5) == {
        "horizon": 5, "mean": 12.0, "n": 1, "best": 12.0, "worst": 12.0, "in_band": 1}


def test_both_edges_of_the_claimed_band_count_as_inside_it():
    """forward_returns() writes two decimals, so exactly 8.0 and exactly 20.0
    are values a row carries. Making either edge exclusive passed the suite."""
    low, high = ledger.CLAIMED_BAND
    rows = [{"forward_returns": {"d5": low}}, {"forward_returns": {"d5": high}},
            {"forward_returns": {"d5": low - 0.01}}, {"forward_returns": {"d5": high + 0.01}}]
    assert ledger.at_horizon(ledger.outcome_summary(rows), 5)["in_band"] == 2


def test_top_score_is_the_best_score_of_the_run(tmp_path):
    """Printed in the runs table; max -> min passed the suite."""
    book = ledger.Ledger(tmp_path).load()
    entry = book.add_run(*_run("2026-08-25", ("AAA", "BBB", "CCC")))
    assert entry["top_score"] == max(c["score"] for c in book.latest["candidates"]) == 8.0


def test_the_evidence_means_are_correctly_rounded_like_the_run_means():
    """CLAUDE.md says the fsum tests are load-bearing on 3.11, and only
    mean_returns() was pinned: outcome_summary() -- every mean in the published
    evidence block -- could go back to sum() with the suite green. The same
    Fraction oracle, against evidence()['overall']."""
    from fractions import Fraction

    values = [9.93, 6.9, 2.86, 2.41]
    exact = sum((Fraction(v) for v in values), Fraction(0)) / len(values)
    rows = [{"forward_returns": {"d5": v}} for v in values]

    got = ledger.at_horizon(ledger.outcome_summary(rows), 5)["mean"]

    assert got == round(float(exact), 2) == 5.53
    assert got == round(math.fsum(values) / len(values), 2)


def test_the_records_session_count_is_the_one_the_streaks_read():
    """evidence.record.sessions counted run dates alone while every streak's
    history_sessions came from Record.of(), which also counts sessions the
    rows prove -- so one undated run entry made one page publish two counts
    of how many sessions one file holds."""
    runs = _record([("2026-08-25", ("AAA",)), ("2026-08-24", ("BBB",))])
    runs[0]["date"] = None            # the entry lost its date; its rows still say 2026-08-25

    ev = ledger.evidence(runs)

    assert ev["record"]["sessions"] == ledger.Record.of(runs).sessions == 2
    assert ev["record"]["from"] == "2026-08-24"


def test_the_shortlist_split_uses_each_runs_own_size():
    """One shortlist size -- the newest run's -- split every run in the record,
    so a TOP_N change re-split older nights at a boundary they never used."""
    runs = _record([("2026-08-25", ("AAA", "BBB", "CCC")), ("2026-08-24", ("DDD", "EEE", "FFF"))],
                   returns={(t, d): {"d5": 1.0} for t, d in
                            [("AAA", "2026-08-25"), ("BBB", "2026-08-25"), ("CCC", "2026-08-25"),
                             ("DDD", "2026-08-24"), ("EEE", "2026-08-24"), ("FFF", "2026-08-24")]})
    runs[0]["shortlist_size"] = 1     # the newest night mailed one name
    runs[1]["shortlist_size"] = 3     # the night before mailed three

    ev = ledger.evidence(runs)

    assert ev["shortlist"]["setups"] == 4 and ev["rest"]["setups"] == 2


def test_the_streak_view_counts_appearances_because_a_setup_lead_is_always_day_one():
    """by_day is the one block per appearance, and the reason is structural.

    setup_leads() picks the FIRST appearance of each setup, so if this block
    counted setups every row in it would be day 1 and the question -- is day 3
    worth more than day 1 -- would have no rows to answer it with.
    """
    # The record has to reach MAX_STREAK_GAP_SESSIONS back past where the
    # setup starts before src.ledger will put a NUMBER on a day at all -- see
    # _why_no_day(). Without the filler sessions every row here is an honest
    # "cannot say", which is the right answer to a different question.
    filler = [(day.date().isoformat(), ("QQQ",))
              for day in pd.bdate_range(end="2026-08-21", periods=8)]
    runs = _record(
        [("2026-08-26", ("AAA",)), ("2026-08-25", ("AAA",)), ("2026-08-24", ("AAA",))] + filler,
        returns={("AAA", "2026-08-24"): {"d5": 1.0}, ("AAA", "2026-08-25"): {"d5": 2.0},
                 ("AAA", "2026-08-26"): {"d5": 3.0}},
    )

    by_day = {row["day"]: row for row in ledger.evidence(runs)["by_day"]}

    assert set(by_day) >= {1, 2, 3}, f"only {sorted(by_day)} -- the later days were collapsed away"
    assert [by_day[d]["appearances"] for d in (1, 2, 3)] == [1, 1, 1]
    assert [ledger.at_horizon(by_day[d]["outcomes"], 5)["mean"]
            for d in (1, 2, 3)] == [1.0, 2.0, 3.0]


def test_whether_a_number_may_be_read_as_a_rate_is_decided_on_the_horizon_that_is_traded():
    """d5 decides `enough`, not d1.

    d1 always has the largest n -- it closes first -- so keying on it would
    license a rate for a horizon nobody has measured. d3 and d5 are what this
    strategy trades; a bucket with a hundred d1s and two d5s knows nothing
    about the trade.
    """
    floor = ledger.MIN_SETUPS_FOR_A_RATE
    sessions = [(f"2026-0{7 + i // 20}-{(i % 20) + 1:02d}", (f"T{i:02d}",)) for i in range(floor + 4)]
    plenty = {(f"T{i:02d}", session): {"d1": 1.0} for i, (session, _t) in enumerate(sessions)}
    runs = _record(sessions, returns=plenty)

    everything = ledger.evidence(runs)

    outcomes = everything["overall"]["outcomes"]
    assert ledger.at_horizon(outcomes, 1)["n"] > floor, "the precondition: d1 has plenty"
    assert ledger.at_horizon(outcomes, 5)["n"] == 0
    assert not any(bucket["enough"] for bucket in everything["by_score"]), (
        "a bucket with no five-session outcome at all was reported readable"
    )


def test_a_bucket_is_readable_at_the_floor_and_not_one_setup_below_it():
    """The boundary itself, from both sides, so a >= cannot drift to a >."""
    floor = ledger.MIN_SETUPS_FOR_A_RATE
    for count, readable in ((floor, True), (floor - 1, False)):
        sessions = [(d.date().isoformat(), (f"T{i:02d}",))
                    for i, d in enumerate(pd.bdate_range(end="2026-08-31", periods=count))]
        runs = _record(sessions, returns={(f"T{i:02d}", session): {"d5": 5.0}
                                          for i, (session, _t) in enumerate(sessions)})

        buckets = [b for b in ledger.evidence(runs)["by_score"] if b["setups"]]

        assert [b["enough"] for b in buckets] == [readable] * len(buckets), (
            f"{count} setups against a floor of {floor} read as enough={not readable}"
        )


def test_each_horizon_carries_the_n_of_its_own_measurements():
    """A burst three sessions old has a d1 and a d3 and no d5.

    Reporting one row count beside all three means attaching a d1-sized sample
    to a d5-sized answer, which is how a mean of two things gets read as a
    mean of thirty.
    """
    runs = _record([("2026-08-24", ("AAA", "BBB", "CCC"))],
                   returns={("AAA", "2026-08-24"): {"d1": 1.0, "d3": 2.0, "d5": 3.0},
                            ("BBB", "2026-08-24"): {"d1": 5.0, "d3": 6.0},
                            ("CCC", "2026-08-24"): {"d1": 9.0}})

    outcomes = ledger.evidence(runs)["overall"]["outcomes"]

    assert [e["horizon"] for e in outcomes] == list(ledger.HORIZONS)
    assert [e["n"] for e in outcomes] == [3, 2, 1]
    assert [e["mean"] for e in outcomes] == [5.0, 4.0, 3.0]


def test_the_score_bands_are_the_rubric_s_own_verdicts():
    """The buckets are not a third opinion about what a 7 means.

    Checked against src.scorer's verdict for a score inside each band -- the
    function the pipeline really labels a candidate with -- rather than against
    the table evidence() read them from, which would be a value compared with
    the name it came from.
    """
    from src.scorer import _verdict_for

    for bucket in ledger.evidence(_record([("2026-08-24", ("AAA",))]))["by_score"]:
        inside = (bucket["low"] + min(bucket["high"], 10.0)) / 2
        assert bucket["verdict"] == _verdict_for(inside), (
            f"band {bucket['low']}-{bucket['high']} is labelled {bucket['verdict']}, "
            f"but the scorer calls {inside} a {_verdict_for(inside)}"
        )


def test_a_check_is_measured_over_the_bursts_it_rejected_as_well():
    """A per-check rate over the scored survivors is survivorship bias with a
    percentage sign: the names a check threw out are exactly the ones missing
    from it. _run()'s gated row fails every check, so it must appear on the
    failed side of each one."""
    runs = _record([("2026-08-24", ("AAA",))],
                   returns={("AAA", "2026-08-24"): {"d5": 10.0}, ("ZZZ", "2026-08-24"): {"d5": -4.0}})

    by_check = {row["code"]: row for row in ledger.evidence(runs)["by_check"]}

    assert by_check, "no checks were measured at all"
    gated_seen = [code for code, row in by_check.items() if row["failed"]["setups"]]
    assert gated_seen, "every check counted only the candidate that was scored"
    assert ledger.at_horizon(by_check[gated_seen[0]]["failed"]["outcomes"], 5)["mean"] == -4.0


def test_the_claimed_band_is_counted_not_just_the_sign_of_the_return():
    """"+2% at five sessions" and "inside the 8-20% a burst is claimed to run"
    are different verdicts, and the strategy makes the second."""
    low, high = ledger.CLAIMED_BAND
    runs = _record([("2026-08-24", ("AAA", "BBB", "CCC"))],
                   returns={("AAA", "2026-08-24"): {"d5": (low + high) / 2},
                            ("BBB", "2026-08-24"): {"d5": low - 0.5},
                            ("CCC", "2026-08-24"): {"d5": high + 0.5}})

    overall = ledger.at_horizon(ledger.evidence(runs)["overall"]["outcomes"], 5)

    assert overall["n"] == 3 and overall["in_band"] == 1
    assert overall["mean"] > 0, "all three are positive; only one is in the band"


def test_the_shortlist_split_uses_the_size_the_runs_really_emailed():
    """Not src.pipeline's TOP_N, which is today's value. A record spans runs,
    and splitting an older one at a boundary it never used would put names in
    a shortlist that never received them."""
    runs = _record([("2026-08-24", tuple(f"T{i}" for i in range(6)))], shortlist_size=2)

    everything = ledger.evidence(runs)

    assert everything["shortlist"]["setups"] == 2
    assert everything["rest"]["setups"] == 4


def test_the_published_snapshot_carries_the_record_s_view(tmp_path):
    """docs/data.json is what the page reads, so the block has to be in it --
    and the contract has to say what it is."""
    book = ledger.Ledger(tmp_path)
    book.add_run(*_run("2026-08-24"))

    published = book.dashboard()

    assert "evidence" in published
    assert published["evidence"]["min_setups"] == ledger.MIN_SETUPS_FOR_A_RATE
    assert any("evidence" in invariant for invariant in published["_contract"]["invariants"])


def test_a_ledger_marked_as_a_fixture_is_never_adopted_as_the_record(tmp_path):
    """tests/fixtures/history/ledger.json is thirty INVENTED sessions written
    by this very class, so it loads perfectly. Dropped into docs/ -- by a hand
    copy, a bad merge, someone seeding a local page -- the next real run would
    adopt its outcomes as its own history, rewrite it without the marker, and
    every mean and streak published afterwards would rest on invented data that
    no longer said it was invented. Nothing else in the pipeline would notice.

    Read from the committed fixture rather than a hand-written stand-in: what
    has to be refused is the real file, and a stand-in could drift from it.
    """
    real_fixture = (ledger.Path(__file__).resolve().parent
                    / "fixtures" / "history" / "ledger.json")
    (tmp_path / ledger.LEDGER_NAME).write_text(real_fixture.read_text())

    book = ledger.Ledger(tmp_path).load()

    assert book.runs == [], "thirty invented sessions were adopted as the record"
    assert "fixture" in (book.load_error or "")
    assert len(ledger.quarantined(tmp_path)) == 1, "the file was kept, not overwritten"


def test_the_history_fixture_pins_the_model_it_writes(monkeypatch):
    """src.scorer reads CLAUDE_MODEL at IMPORT time and the pipeline copies that
    name into every run, so regenerating tools/make_history.py with the variable
    set produced a different fixture -- and failed tools/check_fixture_fresh.py
    for the developer who had it set, on a file nobody had touched. Verified by
    regenerating with CLAUDE_MODEL=claude-opus-4-5: run.model changed.

    Patched rather than set in the environment, because an env var set at
    generation time arrives after the import that read it.
    """
    import tools.make_history as make_history
    from src import pipeline, scorer

    monkeypatch.setattr(scorer, "MODEL", "claude-somebody-elses-model")
    monkeypatch.setattr(pipeline, "DEFAULT_MODEL", "claude-somebody-elses-model")

    with make_history._patched(make_history.DatedAlpaca()):
        assert scorer.MODEL == make_history.MODEL
        assert pipeline.DEFAULT_MODEL == make_history.MODEL

    assert scorer.MODEL == "claude-somebody-elses-model", "the patch leaked out"
    assert pipeline.DEFAULT_MODEL == "claude-somebody-elses-model"


def test_the_committed_history_fixture_carries_that_pinned_model():
    """The other half: the file on disk really was generated with the pin."""
    import json as _json

    import tools.make_history as make_history

    data = _json.loads((ledger.Path(__file__).resolve().parent
                        / "fixtures" / "history" / "data.json").read_text())

    assert data["run"]["model"] == make_history.MODEL
