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
from datetime import date

import pandas as pd
import pytest

from src import ledger

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
            "d1", "d3", "d5", "n", "bursts", "passed_gate", "scored", "size",
            "shortlist_size", "score_cap", "top_score", "fallbacks",
            "day", "seen_before", "last_score",
            "pct_off_52w_high", "pct_above_52w_low", "perf_3mo_pct", "perf_6mo_pct")


def _streak_ok(row) -> bool:
    """Is this burst's streak block internally consistent, or honestly absent?

    The file cannot be checked against the ledger from here -- it does not
    carry one -- so what is enforced is that the block cannot contradict
    itself: day 1 is exactly a setup that starts today, and "never seen
    before" is exactly no previous appearance. A row that claims day 4 while
    first_seen is today's session is a streak computed against nothing, which
    is the shape a broken read would take.

    null is legal. It is what a run publishes when it could not read its own
    history, and it is deliberately not the same as day 1.
    """
    streak = row.get("streak")
    if streak is None:
        return "streak" in row
    if not isinstance(streak, dict):
        return False
    if set(streak) != {"day", "first_seen", "last_seen", "last_score",
                       "last_verdict", "seen_before"}:
        return False
    day, seen = streak["day"], streak["seen_before"]
    if not isinstance(day, int) or isinstance(day, bool) or day < 1:
        return False
    if not isinstance(seen, int) or isinstance(seen, bool) or seen < 0:
        return False
    if (day == 1) != (streak["first_seen"] == row.get("date")):
        return False
    if (seen == 0) != (streak["last_seen"] is None):
        return False
    if day > 1 and seen < day - 1:
        return False   # more days in this setup than appearances to make them
    if streak["last_seen"] is None and (streak["last_score"] is not None
                                        or streak["last_verdict"] is not None):
        return False   # a judgement from a sighting that never happened
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
        return isinstance(returns.get("n"), int) and returns["n"] >= 0
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


def _new_setup(session: str = "2026-08-31") -> dict:
    """A streak block for a name nobody has seen before: day 1, nothing prior."""
    return {"day": 1, "first_seen": session, "last_seen": None,
            "last_score": None, "last_verdict": None, "seen_before": 0}


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
                  "forward_returns": {"d1": None, "d3": None, "d5": None, "n": 0}}],
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


def test_the_mean_of_no_measurements_is_null_not_zero():
    rows = [{"forward_returns": ledger.empty_returns()} for _ in range(3)]

    assert ledger.mean_returns(rows) == {"d1": None, "d3": None, "d5": None, "n": 0}


def test_the_mean_counts_only_the_names_that_have_one():
    rows = [{"forward_returns": {"d1": 2.0, "d3": None, "d5": None, "as_of": "x"}},
            {"forward_returns": {"d1": -1.0, "d3": 4.0, "d5": None, "as_of": "x"}},
            {"forward_returns": ledger.empty_returns()}]

    assert ledger.mean_returns(rows) == {"d1": 0.5, "d3": 4.0, "d5": None, "n": 2}


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


def test_a_ledger_this_module_cannot_read_is_moved_aside_not_overwritten(tmp_path):
    """The accumulated outcomes are the one thing here that cannot be
    recomputed, so a read error must not be allowed to destroy them."""
    (tmp_path / ledger.LEDGER_NAME).write_text("{not json")

    ledger.Ledger(tmp_path).load().add_run(*_run("2026-08-25"))
    ledger.Ledger(tmp_path).load()   # again: the second load finds no ledger

    assert (tmp_path / (ledger.LEDGER_NAME + ".unreadable")).read_text() == "{not json"


def test_a_ledger_from_another_schema_is_not_merged_into(tmp_path, caplog):
    (tmp_path / ledger.LEDGER_NAME).write_text(json.dumps(
        {"schema_version": 99, "runs": [{"date": "2026-01-01", "type": "evening"}]}))

    book = ledger.Ledger(tmp_path).load()

    assert book.runs == []
    assert "schema_version" in caplog.text
    assert (tmp_path / (ledger.LEDGER_NAME + ".unreadable")).exists(), (
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
    assert old["forward_returns"] == {"d1": 1.0, "d3": 3.0, "d5": 10.0, "n": 1}, (
        "the run mean covers the scored candidates")


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
    trading; re-requesting it every night forever buys nothing."""
    monkeypatch.setattr(ledger, "FILL_WINDOW_RUNS", 2)
    book = ledger.Ledger(tmp_path).load()
    for day in (24, 25, 26):
        book.add_run(*_run(f"2026-08-{day}"))

    assert book.pending_tickers(through=date(2026, 8, 31)) == ["AAA", "ZZZ"]


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
                            / "docs" / "data.json").read_text())

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


def _seen(session: str, *, score=None, verdict=None, ticker="AAA",
          gated: bool = False) -> dict:
    """One ledger run in which `ticker` burst on `session`."""
    row = {"ticker": ticker, "date": session, "score": score, "verdict": verdict}
    key = "gated" if gated else "candidates"
    return {"date": session, "type": "evening", key: [row]}


def test_sessions_between_counts_sessions_not_calendar_days():
    """Friday to Monday is one session, not three. A streak measured in
    calendar days would break over every weekend."""
    assert ledger.sessions_between("2026-08-28", "2026-08-31") == 1
    assert ledger.sessions_between(MON, TUE) == 1
    assert ledger.sessions_between(MON, MON) == 0
    assert ledger.sessions_between("nonsense", MON) is None


def test_a_name_with_no_history_is_day_one_of_a_new_setup():
    """The precondition for every test below: day 1 is not simply what this
    function always says."""
    assert ledger.streak([], TUE) == {
        "day": 1, "first_seen": TUE, "last_seen": None,
        "last_score": None, "last_verdict": None, "seen_before": 0}


def test_a_name_that_burst_yesterday_is_day_two_today():
    """THE case the step exists for: seen on Monday, seen again on Tuesday."""
    history = ledger.appearance_index([_seen(MON, score=7.5, verdict="B")])

    assert ledger.streak(history["AAA"], TUE) == {
        "day": 2, "first_seen": MON, "last_seen": MON,
        "last_score": 7.5, "last_verdict": "B", "seen_before": 1}


def test_three_consecutive_sessions_are_day_three():
    history = ledger.appearance_index([_seen(MON), _seen(TUE)])
    assert ledger.streak(history["AAA"], WED)["day"] == 3


def test_a_gap_of_exactly_the_limit_is_still_the_same_setup():
    """Read off MAX_STREAK_GAP_SESSIONS, and asserted from BOTH sides: the
    boundary is the whole rule, and an off-by-one here is the difference
    between "day 2 of this move" and "a new setup"."""
    limit = ledger.MAX_STREAK_GAP_SESSIONS
    session = pd.bdate_range(start=MON, periods=limit + 1)[-1].date().isoformat()
    history = ledger.appearance_index([_seen(MON)])

    assert ledger.sessions_between(MON, session) == limit
    assert ledger.streak(history["AAA"], session)["day"] == 2, (
        "a burst inside the window the first one's outcome is measured over")


def test_a_gap_of_one_more_than_the_limit_starts_a_new_setup():
    """The other side. A name reappearing after a full base is day 1 of
    something new, not day N of a move that finished -- but the ledger still
    says when it was last seen, because that is a fact and a useful one."""
    limit = ledger.MAX_STREAK_GAP_SESSIONS
    session = pd.bdate_range(start=MON, periods=limit + 2)[-1].date().isoformat()
    history = ledger.appearance_index([_seen(MON, score=6.0, verdict="C")])

    assert ledger.sessions_between(MON, session) == limit + 1
    streak = ledger.streak(history["AAA"], session)
    assert streak["day"] == 1 and streak["first_seen"] == session
    assert streak["last_seen"] == MON and streak["seen_before"] == 1
    assert (streak["last_score"], streak["last_verdict"]) == (6.0, "C")


def test_a_ticker_two_weeks_later_is_not_day_twelve():
    """The example the rule was written against."""
    history = ledger.appearance_index([_seen("2026-08-17")])
    assert ledger.streak(history["AAA"], "2026-08-31")["day"] == 1


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
    streak = ledger.streak(history["AAA"], TUE)

    assert streak["day"] == 2
    assert streak["last_score"] is None and streak["last_verdict"] is None, (
        "it was never scored, and the row must not invent a judgement")


def test_an_appearance_on_the_session_being_scanned_is_not_a_repeat_of_itself():
    """A run repeated after a failure re-scans a session already in the
    ledger. Counting the first attempt would report every name in it as day 2
    of a setup it started that same evening."""
    history = ledger.appearance_index([_seen(TUE, score=7.0)])
    assert ledger.streak(history["AAA"], TUE)["day"] == 1


def test_a_backfill_does_not_count_the_newer_runs_sitting_above_it():
    """SCAN_SESSION_DATE puts an old session into a ledger that already holds
    newer ones. Which appearances are prior is decided by DATE, not by where
    the entry landed in the file."""
    history = ledger.appearance_index([_seen(WED), _seen(MON)])
    assert ledger.streak(history["AAA"], TUE) == {
        "day": 2, "first_seen": MON, "last_seen": MON,
        "last_score": None, "last_verdict": None, "seen_before": 1}


def test_one_session_scanned_twice_is_one_appearance():
    """A morning and an evening entry for the same session are two ledger
    rows and one burst. Counting both would inflate every streak by one."""
    history = ledger.appearance_index([
        dict(_seen(MON, score=7.5, verdict="B")),
        dict(_seen(MON), type="morning"),
    ])
    assert len(history["AAA"]) == 1
    assert ledger.streak(history["AAA"], TUE) == {
        "day": 2, "first_seen": MON, "last_seen": MON,
        "last_score": 7.5, "last_verdict": "B", "seen_before": 1}


def test_seen_before_counts_every_earlier_sighting_not_just_this_setup():
    history = ledger.appearance_index([_seen("2026-06-01"), _seen("2026-07-01"),
                                       _seen(MON)])
    streak = ledger.streak(history["AAA"], TUE)
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

    streak = ledger.streak(history["AAA"], TUE)

    assert streak["last_seen"] == MON
    assert (streak["last_score"], streak["last_verdict"]) == (6.5, "B"), (
        "the judgement belongs to the sighting last_seen names, and no other")


def test_streaks_answers_for_every_name_it_is_asked_about():
    runs = [_seen(MON, score=7.5, verdict="B"), _seen(MON, ticker="BBB", gated=True)]
    marks = ledger.streaks(runs, ["AAA", "BBB", "NEW"], TUE)

    assert marks["AAA"]["day"] == 2 and marks["BBB"]["day"] == 2
    assert marks["NEW"] == {"day": 1, "first_seen": TUE, "last_seen": None,
                            "last_score": None, "last_verdict": None,
                            "seen_before": 0}


def test_an_empty_history_says_day_one_because_that_is_what_it_knows():
    """An empty ledger and an unreadable one are different answers. This is
    the empty one: every name really is on day 1 and the record says so.
    src.pipeline publishes null for the unreadable one."""
    assert ledger.streaks([], ["AAA"], TUE)["AAA"]["day"] == 1


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
    assert (tmp_path / (ledger.LEDGER_NAME + ".unreadable")).read_text() == spoiled


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


def test_a_snapshot_from_another_schema_is_refused(tmp_path):
    _snapshot(tmp_path, schema_version=99)
    data, why = ledger.read_snapshot(tmp_path)
    assert data is None and "schema_version 99" in why


def test_a_snapshot_with_no_run_in_it_is_refused(tmp_path):
    _snapshot(tmp_path, run=None)
    data, why = ledger.read_snapshot(tmp_path)
    assert data is None and "no run to follow through on" in why
