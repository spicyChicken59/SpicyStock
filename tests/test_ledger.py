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
from datetime import date, datetime, timedelta, timezone

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
    "quiet_run",           # a run entry's `scored` against the mean it publishes
    "fills_closed",        # which runs a later run will still fetch bars for
    "numbers_or_null",     # no NaN, no "n/a", no 0 standing in for unknown
    "liquidity",           # run.liquidity agrees with the rows and the populations are disjoint
    "benchmark",           # runs[].benchmark and evidence.universe hold together
    "coverage",            # run.coverage's counts order, and a burst came from a measured name
)

_RUN_KEYS = ("date", "type", "bursts", "passed_gate", "scored", "score_cap",
             "shortlist_size", "gate", "scored_by", "universe", "coverage", "errors")

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
                    ledger.HISTORY_UNREADABLE, ledger.WINDOW_NOT_COVERED,
                    ledger.BLIND_SESSION}
#: The three reasons that leave the record with NO SPAN to report. The other
#: two -- window_not_covered, where the span exists and is too short, and
#: blind_session, where it is long enough and one night inside it read nothing
#: -- are the ones where reporting the span is the whole point.
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
            return False   # only the two window reasons have a record to report
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
        if n > rows:
            return False
        # AND THE WEIGHT IS PER HORIZON. n is every setup that measured
        # SOMETHING, so a run holding one setup holed after d1 and one
        # measured throughout publishes d5 over one setup with n 2 -- and the
        # page multiplies by that. Each horizon's own count, on both bases,
        # against three things the writer guarantees: it is a count, it is 0
        # exactly when its mean is null (a weight of 0 under a number, or a
        # weight under a null, is a session that would be averaged wrong in
        # either direction), and it cannot exceed the setups the run has.
        # from_open is checked only when it is there: a run from before the
        # open basis carries none, which the contract calls a fact about that
        # run rather than a measurement of zero.
        for block, total in ((returns, n), (returns.get("from_open"), (returns.get("from_open") or {}).get("n"))):
            if block is None:
                continue
            if not isinstance(total, int) or isinstance(total, bool) or total < 0:
                return False
            for key in horizons:
                count = block.get("n" + key[1:])
                if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                    return False
                if (count > 0) != (block.get(key) is not None) or count > total:
                    return False
        return True
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

    for index, row in enumerate(data["runs"]):
        if not _returns_ok(row.get("forward_returns"), run_level=True):
            bad.add("returns_shape")
        if not _quiet_run_ok(row):
            bad.add("quiet_run")
        # Only one direction of the fill window is checkable from the file:
        # the newest FILL_WINDOW_RUNS entries are in it whatever else is true,
        # while an entry past them may be either, because the run just added
        # is exempt wherever its session put it. Absent is a file written
        # before the stamp existed.
        closed = row.get("fills_closed")
        if closed is not None and not isinstance(closed, bool):
            bad.add("fills_closed")
        elif closed and index < ledger.FILL_WINDOW_RUNS:
            bad.add("fills_closed")

    # Round 5's sentences. run.liquidity.refused is the count of the rows that
    # carry the word; every such row sits below the floor and every other
    # gated row at or above it; and the five evidence populations are
    # disjoint and together are every setup. The checker every end-to-end
    # test asserts "the whole contract" through did not check any of these,
    # so a run that published the block and dropped the rows was clean.
    liquidity = run.get("liquidity")
    if liquidity is not None:
        refused = [g for g in gated if g.get("reason") == ledger.LIQUIDITY_REASON]
        floor = liquidity.get("floor") if isinstance(liquidity, dict) else None
        if not isinstance(liquidity, dict) or liquidity.get("refused") != len(refused):
            bad.add("liquidity")
        elif isinstance(floor, (int, float)):
            if any(not isinstance(g.get("dollar_volume"), (int, float)) or g["dollar_volume"] >= floor
                   for g in refused):
                bad.add("liquidity")
            if any(isinstance(g.get("dollar_volume"), (int, float)) and g["dollar_volume"] < floor
                   for g in gated if g.get("reason") != ledger.LIQUIDITY_REASON):
                bad.add("liquidity")
        elif refused:
            bad.add("liquidity")   # refusals under a floor the run says it never had
        # And `over` -- how many names the percentile was drawn FROM. Nothing
        # checked it at all, so -5 was a legal document; and a floor is a
        # percentile of a population, so a run that recorded one recorded
        # ranking at least one name. The reverse is not a rule: a positive
        # `over` under a null floor is the rule switched off (pctile <= 0),
        # which is a shape the pipeline writes.
        if isinstance(liquidity, dict) and "over" in liquidity:
            over = _count_or_none(liquidity, "over")
            if over is None or over < 0:
                bad.add("liquidity")
            elif isinstance(floor, (int, float)) and not isinstance(floor, bool) and not over:
                bad.add("liquidity")
    ev = data.get("evidence")
    if isinstance(ev, dict) and isinstance(ev.get("record"), dict):
        populations = ("shortlist", "rest", "refused", "crowded_out", "illiquid")
        if all(isinstance(ev.get(k), dict) for k in populations):
            if sum(ev[k]["setups"] for k in populations) != ev["record"]["setups"]:
                bad.add("liquidity")

    # Round 7's and round 9's sentences about the benchmark. The walker
    # checked nothing under runs[].benchmark or evidence.universe, so the
    # sentences CONTRACT_INVARIANTS wrote into every docs/data.json were
    # documentation only -- the round-9 audit set n1 to 9999, below_floor to
    # -5, the stamped floor to a number the run never applied and floored to
    # 999, and this returned the same set. Each of those is a violation now.
    for entry in data["runs"]:
        if not _benchmark_ok(entry):
            bad.add("benchmark")
    if isinstance(ev, dict) and isinstance(ev.get("universe"), dict):
        rung = ev["universe"]
        floored, unfloored = rung.get("floored"), rung.get("unfloored")
        if not all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in (floored, unfloored)):
            bad.add("benchmark")
        elif floored + unfloored > rung.get("setups", -1):
            bad.add("benchmark")

    # Round 11's block, and the gap round 9's R9-B closed one block over. The
    # walker every end-to-end test asserts through clean() as "the whole
    # contract" returned an identical answer for the canonical fixture and for
    # `coverage` deleted, `measured: 9999` beside `with_bars: 227`, `measured:
    # 0` beside `bursts: 50`, a `measured` that is a string, and a negative
    # `liquidity.over`. Every one of those is a violation now, and the
    # consequences of the accepted-but-impossible shape were real: both
    # surfaces silently reverted to the pre-round behaviour, and the evening
    # cell printed "the other -9772 that answered could not be".
    if not _coverage_ok(run):
        bad.add("coverage")
    # A burst can only have come from a name that was measured, which is what
    # makes `measured: 0` a BLIND night rather than a quiet one.
    if run["bursts"] and _count_or_none(run.get("coverage"), "measured") == 0:
        bad.add("coverage")

    found: list = []
    _walk(data, found)
    if found:
        bad.add("numbers_or_null")
    return bad


def _count_or_none(block, key):
    """One count out of a block, or None when it is absent or not a count."""
    if not isinstance(block, dict):
        return None
    value = block.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _coverage_ok(run: dict) -> bool:
    """run.coverage's counts against the sentences that describe them.

    Every count present is a non-negative whole number, and the four that
    narrow do narrow: measured <= fresh <= with_bars <= requested. The two
    maps the scanner keeps come through as counts, and neither way of missing
    the session can exceed the names that answered. An absent count was never
    reached -- a run that died early carries fewer of them -- so absent is
    skipped rather than read as 0.
    """
    counts = run.get("coverage")
    if not isinstance(counts, dict):
        return False
    for key in ("requested", "with_bars", "fresh", "measured", "stale", "gapped",
                "no_bars", "dropped", "duplicate_bars"):
        if key in counts and _count_or_none(counts, key) is None:
            return False
        if key in counts and counts[key] < 0:
            return False
    ladder = [counts[key] for key in ("requested", "with_bars", "fresh", "measured")
              if key in counts]
    if ladder != sorted(ladder, reverse=True):
        return False
    answered = _count_or_none(counts, "with_bars")
    missed = sum(counts[key] for key in ("stale", "gapped") if key in counts)
    if answered is not None and missed > answered:
        return False
    return True


def _quiet_run_ok(entry: dict) -> bool:
    """One run entry's `scored` against the mean it publishes.

    The forward-returns invariant gained an exception no session can end -- a
    run that scored nothing has no rows for a later run to fill, so its three
    horizons and its n stay null and 0 for good -- and this walker read
    nothing under it. That is the R9-B shape one round on, and it costs more
    here than it did there: docs/index.html now acts on `scored` ALONE, so an
    entry claiming it scored nothing SUPPRESSES the measured numbers beside it
    rather than being contradicted by them on screen, and drops that session
    out of every horizon's denominator.

    `scored` is held to a non-bool int >= 0 for the same reason, and that is
    what makes the page's `row.scored === 0` and `row.scored == 0`
    indistinguishable on any document this checker accepts: "0", false and []
    are refused here, so the strict comparison is a rule about documents, not
    a rule the page can be mutated out of. An entry with no `scored` key at
    all is not this rule's business; a shape `_returns_ok` already refuses is
    not either, so one doctoring names one invariant.
    """
    if "scored" not in entry:
        return True
    scored = entry["scored"]
    if isinstance(scored, bool) or not isinstance(scored, int) or scored < 0:
        return False
    returns = entry.get("forward_returns")
    if scored and isinstance(returns, dict):
        # The other exception no session can end: every scored row measured
        # and none of them the first scored appearance of its setup, so the
        # run has nothing to average and never will -- a lead only ever moves
        # EARLIER. A run still waiting for its rows has rows < scored, which
        # is what separates the two.
        return not (returns.get("rows") == scored and not returns.get("n")
                    and any(block.get(f"d{h}") is not None
                            for h in ledger.HORIZONS
                            for block in (returns, returns.get("from_open") or {})))
    if scored:
        return True
    if not isinstance(returns, dict):
        return True
    blocks = [returns]
    if isinstance(returns.get("from_open"), dict):
        blocks.append(returns["from_open"])
    for block in blocks:
        if any(block.get(f"d{h}") is not None for h in ledger.HORIZONS):
            return False
        if block.get("n"):
            return False
    # rows counts the rows those setups were collapsed from, and a run that
    # scored nothing has no rows at all -- mean_returns() takes them off the
    # run's own candidates.
    return not returns.get("rows")


def _benchmark_ok(entry: dict) -> bool:
    """One run entry's benchmark block against the sentences that describe it.

    Absent is a run from before the benchmark and is fine. Present: every
    nN a count, a horizon with a mean has names behind it and one without
    has none, the open basis's n never exceeds the close basis's (a frame
    with a usable open has a close), below_floor a count, the stamped floor
    null or positive -- and equal to the run's own floor when the entry
    carries one, because the sentence says it IS that floor.
    """
    bench = entry.get("benchmark")
    if bench is None:
        return True
    if not isinstance(bench, dict) or not isinstance(bench.get("from_open"), dict):
        return False
    counts = lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 0   # noqa: E731
    for h in ledger.HORIZONS:
        for block in (bench, bench["from_open"]):
            n, mean = block.get(f"n{h}"), block.get(f"d{h}")
            if not counts(n) or (mean is None) != (n == 0):
                return False
        if bench["from_open"][f"n{h}"] > bench[f"n{h}"]:
            return False
    if not counts(bench.get("below_floor", 0)):
        return False
    floor = bench.get("liquidity_floor")
    if floor is not None:
        if isinstance(floor, bool) or not isinstance(floor, (int, float)) or floor <= 0:
            return False
        own = (entry.get("liquidity") or {}).get("floor") if isinstance(entry.get("liquidity"), dict) else None
        if own is not None and own != floor:
            return False
    return True


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
            # How much of the night was read: 230 asked, two names the feed
            # answered with nothing, two of the answers behind the session.
            # The four counts narrow, which is what the invariant reads.
            "coverage": {"requested": 230, "with_bars": 228, "fresh": 226,
                         "measured": 226, "stale": 2, "gapped": 0, "no_bars": 2,
                         "dropped": 0, "duplicate_bars": 0, "session": "2026-08-31"},
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
                                      "n1": 0, "n3": 0, "n5": 0,
                                      "n": 0, "rows": 0}}] + [
            # The sessions the streak blocks above say the record holds. A
            # document whose rows claim a history deeper than its own `runs`
            # is describing a file that cannot exist, and now that the block
            # carries history_from a reader can see it. Each carries the
            # benchmark the fill would have written for a session whose d1
            # is in: over the names at or above that night's floor, which
            # the entry's own liquidity block names.
            {"date": day, "type": "evening", "bursts": 3, "passed_gate": 2,
             "scored": 2, "shortlist_size": 2, "top_score": 8.0, "fallbacks": 0,
             # One count per horizon, the weight the page multiplies by:
             # d1 is over both setups and the two horizons no session has
             # reached yet are over none. Same shape as `benchmark` below.
             "forward_returns": {"d1": 1.1, "d3": None, "d5": None,
                                 "n1": 2, "n3": 0, "n5": 0, "n": 2, "rows": 2},
             "liquidity": {"pctile": 30, "floor": 200_000_000.0, "refused": 0},
             "benchmark": {"d1": 0.4, "d3": None, "d5": None, "n1": 150, "n3": 0, "n5": 0,
                           "from_open": {"d1": 0.1, "d3": None, "d5": None, "n1": 148, "n3": 0, "n5": 0},
                           "universe": {"label": "data/symbols.txt (checked in)", "size": 230},
                           "liquidity_floor": 200_000_000.0, "below_floor": 69}}
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


def test_a_liquidity_population_that_contradicts_the_floor_is_caught(document):
    """`over` reached the record with nothing checking it against anything.
    A floor IS a percentile of a population, so a run that recorded one
    ranked at least one name -- and a count that is not a count is a shape no
    writer produces. The rule-off state is deliberately NOT a violation: a
    positive `over` under a null floor is exactly what `pctile: 0` writes,
    which the published contract said could not happen."""
    def doctored(edit):
        fresh = json.loads(json.dumps(document))
        fresh["run"]["liquidity"] = {"pctile": 30, "floor": 200_000_000.0,
                                     "over": 190, "refused": 0}
        edit(fresh["run"]["liquidity"])
        _only(fresh, "liquidity")

    doctored(lambda block: block.update(over=-5))
    doctored(lambda block: block.update(over="190"))
    doctored(lambda block: block.update(over=0))     # a floor drawn from nobody

    legal = json.loads(json.dumps(document))
    legal["run"]["liquidity"] = {"pctile": 0.0, "floor": None, "over": 226, "refused": 0}
    assert contract_violations(legal) == set(), (
        "rule 6 switched off writes a positive `over` under a null floor")


def test_a_coverage_block_that_contradicts_its_counts_is_caught(document):
    """The gap R9-B closed for the benchmark, one block over. Six edits, all
    of which this walker used to answer identically to the clean document --
    while the surfaces reading them reverted to the pre-round behaviour and
    the evening cell printed a negative.

    `coverage` deleted is a `schema` violation rather than this one, because
    the run block the pipeline writes always carries it: a run that reached
    publish() reached the scan.
    """
    def doctored(edit):
        fresh = json.loads(json.dumps(document))
        edit(fresh["run"])
        _only(fresh, "coverage")

    doctored(lambda run: run["coverage"].update(measured=9999))       # past what answered
    doctored(lambda run: run["coverage"].update(with_bars=231))       # past what was asked
    doctored(lambda run: run["coverage"].update(fresh=229))           # past what answered
    doctored(lambda run: run["coverage"].update(measured="226"))      # not a count
    doctored(lambda run: run["coverage"].update(gapped=-1))           # not a count either
    doctored(lambda run: run["coverage"].update(stale=200, gapped=200))  # more than answered
    # A burst can only come from a name that was measured, which is the shape
    # that makes ledger.is_blind() misfire: `measured: 0` beside three bursts.
    doctored(lambda run: run["coverage"].update(measured=0))

    gone = json.loads(json.dumps(document))
    del gone["run"]["coverage"]
    assert contract_violations(gone) == {"schema"}

    # And the inverse, so this cannot pass by refusing everything: a run that
    # measured nothing and found nothing is a legal document.
    blind = json.loads(json.dumps(document))
    blind["run"]["coverage"].update(measured=0, fresh=0)
    blind["run"].update(bursts=0, passed_gate=0, scored=0)
    blind["candidates"], blind["gated_out"] = [], []
    assert "coverage" not in contract_violations(blind)


def test_a_benchmark_block_that_contradicts_its_sentences_is_caught(document):
    """R9-B. Four edits the round-9 audit made to the fixture, none of which
    the checker saw: a count the universe cannot hold under a null mean, a
    negative count of names left out, a stamped floor the run never applied,
    and a rung claiming more floored pairings than it has."""
    def doctored(edit):
        fresh = json.loads(json.dumps(document))
        entry = next(r for r in fresh["runs"] if isinstance(r.get("benchmark"), dict))
        edit(fresh, entry)
        _only(fresh, "benchmark")

    doctored(lambda d, e: e["benchmark"].update(n1=9999, d1=None))
    doctored(lambda d, e: e["benchmark"].update(below_floor=-5))
    doctored(lambda d, e: e["benchmark"].update(liquidity_floor=1.0))
    doctored(lambda d, e: e["benchmark"]["from_open"].update(n1=e["benchmark"]["n1"] + 1))
    # The rung: more floored pairings than the record has pairings. The
    # hand-written document carries no evidence block, so the one planted
    # here is the smallest the checker reads.
    doctored(lambda d, e: d.update(evidence={"universe": {"setups": 2, "floored": 999, "unfloored": 0,
                                                          "outcomes": []}}))


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


def _history_with_one_refusal() -> dict:
    """The thirty-run fixture's headline (contract-clean, and its headline
    night refused nothing) with one liquidity refusal planted: a gated row
    under the floor, the block's count raised with it."""
    import pathlib as _pathlib
    doc = json.loads((_pathlib.Path(__file__).resolve().parent / "fixtures" / "history" / "data.json").read_text())
    floor = doc["run"]["liquidity"]["floor"]
    donor = next(g for g in doc["gated_out"] if g["reason"] != ledger.LIQUIDITY_REASON)
    thin = json.loads(json.dumps(donor))
    thin.update(ticker="THIN", reason=ledger.LIQUIDITY_REASON, dollar_volume=floor / 2)
    doc["gated_out"].append(thin)
    doc["run"]["bursts"] += 1
    doc["run"]["liquidity"]["refused"] += 1
    assert contract_violations(doc) == set(), contract_violations(doc)
    return doc


def test_a_liquidity_block_that_disagrees_with_its_rows_is_caught():
    """The count the block states, the floor the rows sit against, and the
    populations that must sum to the record: each broken alone, each named.
    The checker every end-to-end test asserts "the whole contract" through
    did not check any of round 5's sentences, so a run that published the
    block and dropped the rows was clean."""
    doc = _history_with_one_refusal()
    doc["run"]["liquidity"]["refused"] += 1
    _only(doc, "liquidity")

    doc = _history_with_one_refusal()
    thin = next(g for g in doc["gated_out"] if g["reason"] == ledger.LIQUIDITY_REASON)
    thin["dollar_volume"] = doc["run"]["liquidity"]["floor"] + 1
    _only(doc, "liquidity")

    doc = _history_with_one_refusal()
    fat = next(g for g in doc["gated_out"] if g["reason"] != ledger.LIQUIDITY_REASON)
    fat["dollar_volume"] = doc["run"]["liquidity"]["floor"] - 1
    _only(doc, "liquidity")

    doc = _history_with_one_refusal()
    doc["evidence"]["illiquid"]["setups"] += 1
    _only(doc, "liquidity")

    doc = _history_with_one_refusal()
    del doc["run"]["liquidity"]
    assert "liquidity" not in contract_violations(doc), "a snapshot from before the block is not held to it"


def test_a_scored_row_with_no_usable_rank_is_still_one_of_the_five_populations():
    """A scored lead with no rank fell out of both `shortlist` and `rest`, so
    the five populations did not add up to the record. No writer produces
    such a row; a hand-edited or older file can, and the contract walker's
    sum check is what found it. Not shown to be on the shortlist is `rest`."""
    runs = _record([("2026-08-24", ("AAA", "BBB"))],
                   returns={("AAA", "2026-08-24"): {"d5": 4.0}, ("BBB", "2026-08-24"): {"d5": 2.0}})
    del runs[0]["candidates"][0]["rank"]

    ev = ledger.evidence(runs)

    assert ev["shortlist"]["setups"] + ev["rest"]["setups"] == ev["overall"]["setups"] == 2
    assert (ev["shortlist"]["setups"] + ev["rest"]["setups"] + ev["refused"]["setups"]
            + ev["crowded_out"]["setups"] + ev["illiquid"]["setups"]) == ev["record"]["setups"]


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
    """n is how many setups the run measured at any horizon and rows is what
    those setups were collapsed from. More setups than rows is the shape of a
    run that went back to weighting by rows and kept the label. (The weight
    the dashboard multiplies by is n1/n3/n5, one per horizon; this pair is
    what the runs table prints.)"""
    document["runs"][0]["forward_returns"] = {"d1": 1.0, "d3": None, "d5": None,
                                              "n": 4, "rows": 3}
    _only(document, "returns_shape")


def test_a_horizon_count_that_is_not_that_horizon_s_weight_is_caught(document):
    """n1/n3/n5 are what the page multiplies each horizon's mean by, so each
    one is held to what mean_returns() guarantees: a count, 0 exactly when
    its own mean is null, and never more setups than the run measured at all.
    Both bases, because the page switches and the open basis carries its own.

    Every plant here is a file no writer produces and a reader cannot tell
    from a real one -- a weight is not contradicted by anything else on the
    page -- which is why it is refused rather than rendered.
    """
    entry = next(r for r in document["runs"] if (r.get("forward_returns") or {}).get("d1") is not None)
    returns = entry["forward_returns"]
    assert (returns["n1"], returns["n"]) == (2, 2), "the precondition, from the clean document"

    for bad in ("2", None, True, 1.5, -1):
        returns["n1"] = bad
        _only(document, "returns_shape")
    returns["n1"] = returns["n"] + 1
    _only(document, "returns_shape")
    returns["n1"] = 0                       # a weight of nothing under a number
    _only(document, "returns_shape")
    returns["n1"] = 2
    returns["n3"] = 1                       # a weight under a null mean
    _only(document, "returns_shape")
    returns["n3"] = 0
    assert contract_violations(document) == set(), "the plants are one field wide"

    # And one level in, on the basis the page can switch to.
    returns["from_open"] = {"d1": 0.5, "n1": "2", "d3": None, "n3": 0,
                            "d5": None, "n5": 0, "n": 2}
    _only(document, "returns_shape")
    returns["from_open"]["n1"] = 3          # more than the open basis's own n
    _only(document, "returns_shape")
    returns["from_open"]["n1"] = 2
    assert contract_violations(document) == set()
    # A run from before the open basis carries no from_open at all, which is
    # a fact about that run and not a weight of zero.
    del returns["from_open"]
    assert contract_violations(document) == set()


def test_a_run_that_says_it_scored_nothing_beside_a_measured_mean_is_caught(document):
    """The exception no session can end, checked rather than described.

    Round 10 gave the page a fifth state and made it act on `scored` alone,
    which is what turned a contradiction that used to correct itself on
    screen -- the nulls said one thing, the count another -- into three cells
    reading "nothing scored" over three measured returns, and a session
    dropped from every horizon's denominator. Planted on a past session
    rather than on the newest entry, because the newest is the one the run
    block describes and the point is a rule about entries.
    """
    entry = next(r for r in document["runs"] if (r.get("forward_returns") or {}).get("d1") is not None)
    entry["scored"] = 0
    _only(document, "quiet_run")
    # And the horizon on its own, with the counts it should have: a mean with
    # no rows behind it is the same lie one field over, and the first version
    # of this test could not see it -- every plant it made tripped the row
    # count first, so the clause that reads the horizons was deletable. It is
    # TWO violations since the weight became per horizon: d1 1.1 needs n1 >= 1
    # and n1 cannot exceed an n of 0, so the shape rule refuses this file one
    # rule earlier. The pair is asserted exactly, which is what still makes
    # the horizon clause load-bearing -- delete it and this reads
    # {returns_shape} alone.
    entry["forward_returns"].update(n=0, rows=0)
    assert contract_violations(document) == {"quiet_run", "returns_shape"}


def test_a_run_that_scored_nothing_may_not_claim_setups_either(document):
    """n is how many setups a run measured at any horizon, rows is what they
    were collapsed from, and a run with no candidates has neither --
    mean_returns() takes both off the run's own rows. The open
    basis is checked with the close one, because a mean is published on both
    and only one of them was ever read here."""
    entry = document["runs"][0]
    assert entry["scored"] == 2 and entry["forward_returns"]["n"] == 0
    entry["scored"] = 0
    entry["forward_returns"].update(n=3, rows=3)
    _only(document, "quiet_run")
    entry["forward_returns"].update(n=0, rows=2)
    _only(document, "quiet_run")
    entry["forward_returns"].update(rows=0,
                                    from_open={"d1": 1.0, "d3": None, "d5": None,
                                               "n1": 1, "n3": 0, "n5": 0, "n": 1})
    _only(document, "quiet_run")
    # The open basis's n with nothing measured beside it. This is the ONLY
    # shape that reaches the setup count on its own: the close basis's n
    # cannot exceed rows (returns_shape), so a quiet run claiming one there
    # is caught by the row count first, and from_open carries no rows.
    entry["forward_returns"].update(from_open={"d1": None, "d3": None, "d5": None,
                                               "n1": 0, "n3": 0, "n5": 0, "n": 1})
    _only(document, "quiet_run")


def test_a_run_whose_every_scored_row_is_a_repeat_may_not_read_as_waiting(document):
    """The second exception no session can end. A run all of whose scored
    rows are repeats of setups counted on an earlier session averages an
    empty list -- rows == scored, n == 0 -- and no later fill changes it,
    because a lead only ever moves earlier. What the file may not do is
    claim that state and publish a mean anyway."""
    entry = document["runs"][0]
    entry["forward_returns"].update(rows=entry["scored"], n=0, d1=1.2)
    # Two violations, and both are true of this file: the mean is published
    # over a d1 whose own count is 0, which the per-horizon weight refuses on
    # its own. Exactly two, so the clause above stays load-bearing -- delete
    # it and this set loses "quiet_run".
    assert contract_violations(document) == {"quiet_run", "returns_shape"}
    # A run still WAITING is the same shape with fewer rows measured, and is
    # not this state: the precondition that keeps the rule from swallowing it.
    # Its d1 goes back to null with the count, because a mean over no setups
    # is not a number in any file mean_returns() writes.
    entry["forward_returns"].update(rows=entry["scored"] - 1, d1=None)
    assert contract_violations(document) == set()


def test_a_run_inside_the_fill_window_may_not_say_its_fills_are_closed(document):
    """The one direction of the window a file can be held to: the newest
    FILL_WINDOW_RUNS entries are in it whatever else is true. Past them the
    run just added is exempt wherever its session put it, so `true` there is
    not a violation -- and a stamp that is not a boolean is."""
    assert len(document["runs"]) <= ledger.FILL_WINDOW_RUNS
    for entry in document["runs"]:
        entry["fills_closed"] = False
    assert contract_violations(document) == set()
    document["runs"][0]["fills_closed"] = True
    _only(document, "fills_closed")
    document["runs"][0]["fills_closed"] = "no"
    _only(document, "fills_closed")
    # A FALSY non-boolean, which the index rule below it cannot catch: it is
    # what makes the type clause load-bearing rather than a second reading of
    # the same fact.
    document["runs"][0]["fills_closed"] = 0
    _only(document, "fills_closed")


def test_a_scored_count_that_is_not_a_count_is_caught(document):
    """What the page reads to decide a run can never contribute a mean.

    "0", false and [] are each falsy or `== 0` in JavaScript and none of them
    is a count, so refusing them here is what makes docs/index.html's strict
    `row.scored === 0` and a loose `==` indistinguishable on any document
    this checker accepts -- an equivalence about documents rather than a rule
    the page could be mutated out of. Three of the five trip
    numbers_or_null as well, which is a second true sentence about the same
    field and not a second defect, so those are asserted as members.
    """
    for value in (-1, 2.5):
        fresh = json.loads(json.dumps(document))
        fresh["runs"][0]["scored"] = value
        _only(fresh, "quiet_run")
    for value in (True, "0", []):
        fresh = json.loads(json.dumps(document))
        fresh["runs"][0]["scored"] = value
        assert contract_violations(fresh) == {"quiet_run", "numbers_or_null"}


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
        # no Open column in this frame, so the open basis is pending
        "from_open": {"d1": None, "d3": None, "d5": None},
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


def frame_with_opens(closes: list[float], opens: list[float], end: str = "2026-08-31") -> pd.DataFrame:
    index = pd.bdate_range(end=end, periods=len(closes), name="timestamp")
    return pd.DataFrame({"Open": [float(o) for o in opens], "Close": [float(c) for c in closes],
                         "Volume": [1_000_000] * len(closes)}, index=index)


def test_the_open_basis_divides_the_same_closes_by_the_next_sessions_open():
    """The example that motivated the second basis, measured rather than
    argued: burst close 100, next open 110, next close 111. The close basis
    records d1 = +11.0% -- what the setup did -- while the price a reader of
    an 18:16 ET email could actually have paid returns +0.91%. Same later
    closes, two denominators, and both are kept."""
    df = frame_with_opens(closes=[100, 111, 112, 113, 114, 121],
                          opens=[99, 110, 111, 112, 113, 114])
    burst = df.index[0].date().isoformat()

    out = ledger.forward_returns(df, burst)

    assert (out["d1"], out["d3"], out["d5"]) == (11.0, 13.0, 21.0)
    assert out["from_open"] == {"d1": 0.91, "d3": 2.73, "d5": 10.0}
    assert out["as_of"] == df.index[5].date().isoformat()


def test_a_frame_with_no_usable_open_measures_the_close_basis_alone():
    """No Open column, a NaN open, or a zero open: the close basis is still
    a measurement and the open basis is null -- never a guess taken from the
    burst close, which would silently make the two bases one."""
    df = frame([100, 101, 102, 103, 104, 110])
    burst = df.index[0].date().isoformat()
    assert ledger.forward_returns(df, burst)["d1"] == 1.0
    assert ledger.forward_returns(df, burst)["from_open"] == {"d1": None, "d3": None, "d5": None}

    for bad in (float("nan"), 0.0, -1.0):
        df = frame_with_opens(closes=[100, 101, 102, 103, 104, 110],
                              opens=[100, bad, 101, 102, 103, 104])
        out = ledger.forward_returns(df, df.index[0].date().isoformat())
        assert out["d5"] == 10.0 and out["from_open"] == {"d1": None, "d3": None, "d5": None}, bad


def test_a_horizon_the_open_basis_cannot_reach_is_null_on_that_basis_too():
    df = frame_with_opens(closes=[100, 101, 102, 103], opens=[100, 100.5, 101, 102])
    out = ledger.forward_returns(df, df.index[0].date().isoformat())
    assert out["from_open"]["d1"] == 0.5 and out["from_open"]["d3"] == 2.49
    assert out["from_open"]["d5"] is None and out["d5"] is None


def test_the_universe_benchmark_is_the_equal_weight_mean_over_the_frames_that_carry_the_session():
    """Two names whose returns from the session are known by construction,
    a third that does not trade the session and so is absent from the mean
    rather than a zero in it, on both bases, with n per horizon."""
    aaa = frame_with_opens(closes=[100, 101, 102, 103, 104, 110], opens=[99, 100, 101, 102, 103, 104])
    bbb = frame_with_opens(closes=[50, 51.5, 52, 52.5, 53, 56], opens=[49, 50.5, 51, 52, 52.5, 53])
    session = aaa.index[0].date().isoformat()
    ccc = frame_with_opens(closes=[10, 11, 12], opens=[10, 10.5, 11.5], end="2026-08-20")   # before the session

    # A fourth name with NO Open column: it has a close-basis return and no
    # open-basis one, so the two n's differ and neither can borrow the other.
    # With both at 2 the mutant that reads len(close_values) for the open
    # basis was invisible, which is how this test first shipped.
    ddd = frame([200, 202, 204, 206, 208, 220])

    bench = ledger.universe_returns({"AAA": aaa, "BBB": bbb, "CCC": ccc, "DDD": ddd}, session)

    # AAA 1/3/10, BBB 3/5/12, DDD 1/3/10; CCC does not trade the session.
    assert (bench["d1"], bench["d3"], bench["d5"]) == (
        round(5 / 3, 2), round(11 / 3, 2), round(32 / 3, 2))
    assert (bench["n1"], bench["n3"], bench["n5"]) == (3, 3, 3), "three frames carry the session"
    assert bench["from_open"]["d1"] == round((1.0 + round((51.5 / 50.5 - 1) * 100, 2)) / 2, 2)
    assert (bench["from_open"]["n1"], bench["from_open"]["n5"]) == (2, 2), (
        "and only two of them carry a usable open")
    assert ledger.universe_returns({"CCC": ccc}, session) == ledger.empty_benchmark()
    assert ledger.universe_returns({}, session) == ledger.empty_benchmark()


def test_the_universe_mean_is_summed_the_way_every_other_mean_here_is():
    """math.fsum, not sum(). CPython 3.12 made the builtin compensated for
    floats, so the same frames read by two interpreters published two
    different benchmarks -- the defect mean_returns() already carries this
    argument for, one function further out. These four returns are the ones
    CLAUDE.md records: sum() gives 22.099999999999998 on 3.11 and 22.1 on
    3.12, and the mean either side of that lands on opposite sides of
    round(x, 2). On 3.12 the two are indistinguishable and this test is
    documentation; on 3.11 it is load-bearing."""
    wanted = [9.93, 6.9, 2.86, 2.41]
    frames = {f"T{i}": frame([100.0, 100.0 * (1 + v / 100)]) for i, v in enumerate(wanted)}
    session = next(iter(frames.values())).index[0].date().isoformat()

    bench = ledger.universe_returns(frames, session)

    assert [ledger.forward_returns(f, session)["d1"] for f in frames.values()] == wanted
    assert bench["d1"] == round(math.fsum(wanted) / 4, 2)
    if sum(wanted) != math.fsum(wanted):        # true on 3.11, false on 3.12
        assert bench["d1"] != round(sum(wanted) / 4, 2), "sum() and fsum() disagree here and fsum wins"


def test_fill_benchmarks_fills_the_window_once_and_never_before_the_sessions_exist(tmp_path):
    """Same window and same idempotence as the forward returns: a run in the
    window gains its benchmark from tonight's frames, keeps a horizon once
    measured, and a run whose session is not behind `through` stays pending."""
    book = ledger.Ledger(tmp_path / "docs")
    universe = {"label": "data/symbols.txt (checked in)", "size": 2}
    for session in ("2026-08-24", "2026-08-31"):
        run, cands, gated = _run(session, tickers=("AAA",))
        run["universe"] = dict(universe)
        book.add_run(run, cands, gated)
    assert all(r["benchmark"] == ledger.empty_benchmark() for r in book.runs)
    aaa = frame_with_opens(closes=[100, 101, 102, 103, 104, 110], opens=[99, 100, 101, 102, 103, 104],
                           end="2026-08-31")   # sessions 24..31 Aug
    bbb = frame_with_opens(closes=[10, 10, 10, 10, 10, 10], opens=[10] * 6, end="2026-08-31")

    # A caller with no universe to offer fills nothing at all: a --tickers run
    # scanned a handful of names it was handed, and that is not a market.
    assert book.fill_benchmarks({"AAA": aaa, "BBB": bbb}, date(2026, 9, 4), universe=None) == 0
    assert book.runs[0]["benchmark"]["d1"] is None
    # Nor does a scan of a DIFFERENT universe fill this one's.
    assert book.fill_benchmarks({"AAA": aaa, "BBB": bbb}, date(2026, 9, 4),
                                universe={"label": "somewhere else", "size": 2}) == 0
    assert book.runs[0]["benchmark"]["d1"] is None

    moved = book.fill_benchmarks({"AAA": aaa, "BBB": bbb}, date(2026, 9, 4), universe=universe)

    older = next(r for r in book.runs if r["date"] == "2026-08-24")
    newer = next(r for r in book.runs if r["date"] == "2026-08-31")
    assert moved == 1
    assert (older["benchmark"]["d1"], older["benchmark"]["d5"], older["benchmark"]["n5"]) == (0.5, 5.0, 2)
    assert older["benchmark"]["universe"] == universe, "stamped with the basket it is over"
    assert older["benchmark"]["from_open"]["d1"] == round((round((101 / 100 - 1) * 100, 2) + 0.0) / 2, 2)
    assert newer["benchmark"]["d1"] is None, "the sessions after it are in no frame yet"
    # A later, different frame restates nothing already measured -- and the
    # run has to be INCOMPLETE for that to be the rule under test: a run whose
    # horizons are all filled is skipped by the early return above, so a
    # restating fill was invisible until this row had a horizon still open.
    partial = next(r for r in book.runs if r["date"] == "2026-08-31")
    partial["benchmark"]["d1"], partial["benchmark"]["n1"] = 99.0, 7
    partial["benchmark"]["from_open"]["d1"], partial["benchmark"]["from_open"]["n1"] = 88.0, 7
    aaa2 = frame_with_opens(closes=[100, 150, 150, 150, 150, 150], opens=[99, 100, 101, 102, 103, 104],
                            end="2026-09-07")   # carries 31 Aug and the sessions after it
    bbb2 = frame_with_opens(closes=[10] * 6, opens=[10] * 6, end="2026-09-07")

    assert book.fill_benchmarks({"AAA": aaa2, "BBB": bbb2}, date(2026, 9, 8), universe=universe) == 1
    assert (partial["benchmark"]["d1"], partial["benchmark"]["n1"]) == (99.0, 7), (
        "the horizon already measured keeps the value it was given")
    assert partial["benchmark"]["from_open"]["d1"] == 88.0
    assert partial["benchmark"]["d3"] is not None, "and the horizons still open were filled"
    assert older["benchmark"]["d1"] == 0.5, "a complete run is untouched"

    # Not behind `through`: pending, on a run with nothing measured yet, or
    # the completed rows above would hide the rule by short-circuiting first.
    fresh_book = ledger.Ledger(tmp_path / "docs2")
    run, cands, gated = _run("2026-08-24", tickers=("AAA",))
    run["universe"] = dict(universe)
    fresh_book.add_run(run, cands, gated)
    assert fresh_book.fill_benchmarks({"AAA": aaa, "BBB": bbb}, date(2026, 8, 24), universe=universe) == 0
    assert fresh_book.runs[0]["benchmark"] == ledger.empty_benchmark()
    assert fresh_book.fill_benchmarks({"AAA": aaa, "BBB": bbb}, date(2026, 9, 4), universe=universe) == 1


def test_the_evidence_pairs_every_scored_setup_with_its_own_sessions_benchmark():
    """The universe rung is the alternative "buy anything in the universe that
    day", paired setup by setup so both sides span the same sessions in the
    same proportions: a session with three picks weighs three times a
    session with one. A setup whose run has no benchmark contributes nothing
    and n says how many did."""
    runs = _record([("2026-08-24", ("AAA", "BBB", "CCC")), ("2026-08-31", ("DDD",))],
                   returns={(t, "2026-08-24"): {"d5": 10.0} for t in ("AAA", "BBB", "CCC")}
                   | {("DDD", "2026-08-31"): {"d5": 4.0}})
    for run in runs:
        run["benchmark"] = ledger.empty_benchmark()
    first = next(r for r in runs if r["date"] == "2026-08-24")
    first["benchmark"].update(d5=1.0, n5=200)
    first["benchmark"]["from_open"].update(d5=0.5, n5=199)
    next(r for r in runs if r["date"] == "2026-08-31")["benchmark"].update(d5=4.0, n5=200)

    ev = ledger.evidence(runs)
    d5 = ledger.at_horizon(ev["universe"]["outcomes"], 5)

    assert ev["universe"]["setups"] == 4 and d5["n"] == 4
    assert d5["mean"] == round((1.0 * 3 + 4.0) / 4, 2), "three picks on the first session, one on the second"
    # The rung carries the benchmark's OWN open basis, paired the same way,
    # with its own n: only the first session recorded one, and its three
    # picks are what weigh it. Asserting n == 0 here (which it was, before
    # any run carried an open-basis benchmark) could not see the rung
    # dropping the block.
    assert d5["from_open"]["mean"] == 0.5 and d5["from_open"]["n"] == 3
    assert not ev["universe"]["enough"]
    next(r for r in runs if r["date"] == "2026-08-31")["benchmark"] = None
    assert ledger.at_horizon(ledger.evidence(runs)["universe"]["outcomes"], 5)["n"] == 3
    assert "universe" not in ("shortlist", "rest", "refused", "crowded_out", "illiquid")


def test_the_pending_shape_is_pending_on_both_bases():
    assert ledger.empty_returns() == {"d1": None, "d3": None, "d5": None, "as_of": None,
                                      "from_open": {"d1": None, "d3": None, "d5": None}}


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
        "d1": None, "d3": None, "d5": None, "n1": 0, "n3": 0, "n5": 0,
        "n": 0, "rows": 0,
        "from_open": {"d1": None, "d3": None, "d5": None, "n1": 0, "n3": 0, "n5": 0, "n": 0}}


def test_the_mean_counts_only_the_names_that_have_one():
    rows = [_row("AAA", "2026-08-31", d1=2.0, as_of="x"),
            _row("BBB", "2026-08-31", d1=-1.0, d3=4.0, as_of="x"),
            _row("CCC", "2026-08-31")]

    assert ledger.mean_returns(rows, _every_row_leads(rows)) == {
        "d1": 0.5, "d3": 4.0, "d5": None, "n1": 2, "n3": 1, "n5": 0,
        "n": 2, "rows": 2,
        "from_open": {"d1": None, "d3": None, "d5": None, "n1": 0, "n3": 0, "n5": 0, "n": 0}}


def test_each_horizon_is_weighted_by_the_setups_that_actually_have_it():
    """THE HOLE. forward_returns() ends a row's measurement at the first
    session its frame does not carry, so a setup can hold d1 and nothing
    after it -- and ONE n for three horizons then tells the page that d5 was
    measured over setups which have no d5.

    Reproduced through this function before it was changed: these two rows
    published d5 6.0 beside n 2, and a second session that measured both of
    its setups at 0.0 gave the page (6*2 + 0*2)/4 = 3.00% where the honest
    weighting is (6*1 + 0*2)/3 = 2.00%. The weight is per horizon now, which
    is the shape runs[].benchmark has carried since round 7.

    `n` stays what it was -- the setups this run contributed at any horizon,
    which is what the runs table prints -- so the two counts are asserted
    against each other here rather than one being renamed into the other.
    """
    rows = [_row("AAA", "2026-08-31", d1=30.0, as_of="x",
                 from_open={"d1": 29.0, "d3": None, "d5": None}),
            _row("BBB", "2026-08-31", d1=2.0, d3=2.0, d5=6.0, as_of="x",
                 from_open={"d1": 1.0, "d3": 1.0, "d5": 5.0})]

    out = ledger.mean_returns(rows, _every_row_leads(rows))

    assert (out["n1"], out["n3"], out["n5"]) == (2, 1, 1), (
        "d3 and d5 are one setup's, and only the horizon's own count says so")
    assert out["d5"] == 6.0 and out["n"] == 2, (
        "n is every setup that measured SOMETHING -- not the weight for d5")
    assert (out["from_open"]["n1"], out["from_open"]["n3"], out["from_open"]["n5"]) == (2, 1, 1)
    assert out["from_open"]["n"] == 2


def test_a_horizon_measured_without_the_one_before_it_is_counted_where_it_is():
    """The counts are NOT a prefix, which is why nothing asserts
    n1 >= n3 >= n5 and the contract says so out loud. A hole ends a row's
    measurement, but a bar that is THERE and prints a non-finite close does
    not: forward_returns() skips that horizon and measures the next one. The
    row is produced by the real function rather than hand-written, because
    the claim is about what the writer emits -- a walker taught the prefix
    would refuse a file this scanner really produces."""
    index = pd.to_datetime(["2026-08-31", "2026-09-01", "2026-09-02",
                            "2026-09-03", "2026-09-04", "2026-09-07"])
    frame = pd.DataFrame({"Open": [10.0] * 6, "High": [12.0] * 6, "Low": [9.0] * 6,
                          "Close": [10.0, float("nan"), 10.5, 10.4, 10.2, 11.0],
                          "Volume": [1e6] * 6}, index=index)
    holed = ledger.forward_returns(frame, date(2026, 8, 31))
    assert holed["d1"] is None and holed["d3"] == 4.0, "the premise, from the writer"

    rows = [{"ticker": "AAA", "date": "2026-08-31", "forward_returns": holed},
            _row("BBB", "2026-08-31", d1=1.0, d3=2.0, as_of="x")]

    out = ledger.mean_returns(rows, _every_row_leads(rows))

    assert (out["n1"], out["n3"]) == (1, 2)
    assert out["n"] == 2


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


def test_the_run_entry_keeps_the_bars_the_feed_repeated_and_omits_what_it_was_not_told(tmp_path):
    """docs/data.json is rewritten by every later run, so the count of bars a
    feed repeated survived exactly one night: the durable record -- the only
    file that keeps a year of nights and the one a reader asks "which nights
    had duplicates?" of -- had no trace of it.

    An ABSENT key and not a null for a run that carried no count, the rule
    `rules` follows: absent is a run from before the field existed, and null
    is a shape no writer produces (and one _malformed_rows() is free to refuse
    later)."""
    book = ledger.Ledger(tmp_path).load()
    run, cands, gated = _run("2026-08-25")

    older = book.add_run(run, cands, gated)
    assert "duplicate_bars" not in older, "a run block from before the count says nothing"

    entry = book.add_run({**run, "date": "2026-08-26", "duplicate_bars": 3}, cands, gated)
    assert entry["duplicate_bars"] == 3
    book.write()
    stored = json.loads((tmp_path / ledger.LEDGER_NAME).read_text())["runs"]
    assert [r.get("duplicate_bars") for r in stored] == [3, None], (
        "on the file itself, and on the newer run alone", stored)

    weird = book.add_run({**run, "date": "2026-08-27", "duplicate_bars": "lots"}, cands, gated)
    assert "duplicate_bars" not in weird, "and a shape no writer produces is not stored either"


def test_the_view_says_which_runs_a_later_run_will_still_fetch_for(tmp_path):
    """`fills_closed` is _fillable()'s own window, published for the page.

    A horizon still null on a run past the window is null for good -- the
    constant's own comment says why nothing is re-requested there -- and the
    runs table called it "pending", which is the same promise-that-cannot-be-
    kept the quiet run's cells were making one state over. The page cannot
    derive it: FILL_WINDOW_RUNS lives here, and the run just added is exempt
    wherever its session put it, which is a fact about this object and not
    about the list's order. So it is computed here, by the method the fills
    themselves walk, and stamped on the view.
    """
    book = ledger.Ledger(tmp_path).load()
    for day in range(1, ledger.FILL_WINDOW_RUNS + 3):
        book.add_run(*_run(f"2026-08-{day:02d}"))
    view = book.dashboard()

    stamped = [(entry["date"], entry["fills_closed"]) for entry in view["runs"]]
    assert [s for _, s in stamped[:ledger.FILL_WINDOW_RUNS]] == [False] * ledger.FILL_WINDOW_RUNS
    assert all(closed for _, closed in stamped[ledger.FILL_WINDOW_RUNS:]), stamped
    assert {d for d, closed in stamped if not closed} == {
        r["date"] for r in book._fill_window()}


def test_the_run_just_added_is_never_stamped_closed_however_old_its_session(tmp_path):
    """A backfill lands deep in a list ordered by session, and it is the one
    run whose outcomes this run exists to collect. _fillable() exempts it;
    the view has to say the same thing, or the page tells a reader the
    backfill's own horizons will never fill on the night it wrote them."""
    book = ledger.Ledger(tmp_path).load()
    for day in range(1, ledger.FILL_WINDOW_RUNS + 3):
        book.add_run(*_run(f"2026-08-{day:02d}"))
    book.write()

    backfill = ledger.Ledger(tmp_path).load()
    backfill.add_run(*_run("2026-08-02", tickers=("BBB",)))
    view = backfill.dashboard()

    entry = next(e for e in view["runs"] if e["date"] == "2026-08-02")
    assert view["runs"].index(entry) >= ledger.FILL_WINDOW_RUNS, "not past the window"
    assert entry["fills_closed"] is False


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
        "d1": 1.0, "d3": 3.0, "d5": 10.0, "as_of": "2026-08-31",
        "from_open": {"d1": None, "d3": None, "d5": None}}
    assert old["forward_returns"] == {"d1": 1.0, "d3": 3.0, "d5": 10.0,
                                      "n1": 1, "n3": 1, "n5": 1, "n": 1, "rows": 1,
                                      "from_open": {"d1": None, "d3": None, "d5": None,
                                                    "n1": 0, "n3": 0, "n5": 0, "n": 0}}, (
        "the run mean covers the scored candidates, one setup from one row")


def test_a_stored_run_mean_is_rebuilt_rather_than_republished(tmp_path):
    """WHY THE PER-HORIZON COUNTS ARE NOT A LOAD CHECK, executed rather than
    argued. Every other nested block this record gained -- benchmark, rules,
    the row's own from_open -- is refused at load, because a shape no writer
    produces reaches a consumer that indexes into it. A run's MEAN does not:
    add_run() calls _recompute_means() over every entry before write(), so
    the block on disk is thrown away and rebuilt from the rows, and there is
    no path from a stored n5 to the page.

    Driven here with a string, a null, a list and a string `n` in one entry:
    they load clean and the entry the next run publishes carries the counts
    its own rows give. If a later round ever publishes a stored mean without
    recomputing it, this test is what says the load check is now needed.
    """
    book = ledger.Ledger(tmp_path).load()
    book.add_run(*_run("2026-08-24"))
    book.write()
    stored = json.loads((tmp_path / "ledger.json").read_text())
    entry = next(r for r in stored["runs"] if r["date"] == "2026-08-24")
    entry["forward_returns"] = {"d1": 9.9, "n1": "three", "n3": None, "n5": [],
                                "n": "x", "rows": 1,
                                "from_open": {"d1": None, "n1": "?", "n": 0}}
    (tmp_path / "ledger.json").write_text(json.dumps(stored))

    again = ledger.Ledger(tmp_path).load()
    assert again.load_error is None, "a run mean is not what the load check is for"
    again.add_run(*_run("2026-08-25"))
    published = next(r for r in again.runs if r["date"] == "2026-08-24")["forward_returns"]

    assert published == {"d1": None, "n1": 0, "d3": None, "n3": 0, "d5": None, "n5": 0,
                         "n": 0, "rows": 0,
                         "from_open": {"d1": None, "n1": 0, "d3": None, "n3": 0,
                                       "d5": None, "n5": 0, "n": 0}}, (
        "the stored block is rebuilt from the rows, so nothing on disk reaches the page")


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
                                            "as_of": "2026-08-31",
                                            "from_open": {"d1": None, "d3": None, "d5": None}}
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


def test_a_blind_night_inside_the_window_withholds_the_day_instead_of_claiming_day_one():
    """"day 1 — new setup" is the claim that nothing preceded this burst. A
    night the scan measured NO NAME AT ALL is a session the record holds an
    entry for and has no evidence about, so an earlier appearance on it would
    have been invisible -- and the claim is made over it anyway. Reproduced
    end to end: a blind Tuesday, a burst on Wednesday, "day 1, never seen".

    Not window_not_covered: this record reaches back 160 sessions. That reason
    resolves as the file fills up and this one never does, so telling an
    operator to wait would be advice that cannot come true."""
    blind = ledger.Record(DEEP, 160, 160, frozenset({date.fromisoformat(MON)}))

    block = ledger.streak([], TUE, record=blind)

    assert block["day"] is None and block["first_seen"] is None
    assert block["unknown_reason"] == ledger.BLIND_SESSION
    # The span is still reported -- what the unknown is unknown OVER -- the
    # way window_not_covered's is, because the record does have one.
    assert (block["history_from"], block["history_sessions"]) == (DEEP.isoformat(), 160)
    # And the inverse: the same record with nothing blind in it says day 1, so
    # this cannot pass by withholding every day number.
    assert ledger.streak([], TUE, record=DEEP_RECORD)["day"] == 1


def test_a_blind_night_outside_the_streak_window_leaves_the_day_alone():
    """Only the window matters. A night nobody read three months before the
    setup started could not have held an appearance of THIS chain -- an
    earlier burst that far back is a different setup by
    MAX_STREAK_GAP_SESSIONS' own rule -- so withholding the number for it
    would refuse one the record can support."""
    far = date.fromisoformat(TUE) - timedelta(days=90)
    record = ledger.Record(DEEP, 160, 160, frozenset({far}))
    assert ledger.streak([], TUE, record=record)["day"] == 1

    # The boundary, from both sides: MAX_STREAK_GAP_SESSIONS sessions before
    # the setup began is inside the window, one more is outside it.
    sessions = pd.bdate_range(end=TUE, periods=ledger.MAX_STREAK_GAP_SESSIONS + 2)
    edge, beyond = sessions[1].date(), sessions[0].date()
    assert ledger.sessions_between(edge, TUE) == ledger.MAX_STREAK_GAP_SESSIONS
    assert ledger.streak([], TUE, record=ledger.Record(DEEP, 160, 160, frozenset({edge})))["day"] is None
    assert ledger.streak([], TUE, record=ledger.Record(DEEP, 160, 160, frozenset({beyond})))["day"] == 1


def test_only_a_run_that_recorded_measuring_nothing_counts_as_blind():
    """`measured` is a count the run wrote down. An entry from before the
    field existed says nothing about how much it read, and reading its absence
    as 0 would make every historical run blind and every day number in the
    file disappear -- absence of evidence again, one field over."""
    assert ledger.Record.of([{"date": MON, "measured": 0}]).blind == {date.fromisoformat(MON)}
    for entry in ({"date": MON},                      # before the count existed
                  {"date": MON, "measured": 1},       # it read one name
                  {"date": MON, "measured": None},
                  {"date": MON, "measured": False},   # a bool is not a count
                  {"date": MON, "measured": "0"},
                  {"date": "nonsense", "measured": 0}):
        assert ledger.Record.of([entry]).blind == frozenset(), entry


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


def test_run_means_and_evidence_outcomes_carry_the_open_basis_with_its_own_n():
    """Every mean the file publishes carries both bases, and the open
    basis's n is its own: a row whose frame had no usable open has a
    close-basis return and no open-basis one, and the two counts must not
    be read as one. `enough` and `enough_from_open` are each basis's own
    licence to be read as a rate -- the page must not borrow one for the
    other."""
    # One open-basis d5 inside the claimed band, so in_band is load-bearing.
    rows = [_row("AAA", "2026-08-31", d1=2.0, d5=6.0, as_of="x", from_open={"d1": 1.0, "d3": None, "d5": 9.0}),
            _row("BBB", "2026-08-31", d1=4.0, d5=8.0, as_of="x", from_open={"d1": 3.0, "d3": None, "d5": 6.0}),
            _row("CCC", "2026-08-31", d1=-1.0, d5=2.0, as_of="x"),   # no open basis at all
            _row("DDD", "2026-08-31")]

    means = ledger.mean_returns(rows, _every_row_leads(rows))
    assert (means["d1"], means["d5"], means["n"]) == (round(5 / 3, 2), round(16 / 3, 2), 3)
    assert means["from_open"] == {"d1": 2.0, "d3": None, "d5": 7.5,
                                  "n1": 2, "n3": 0, "n5": 2, "n": 2}

    summary = ledger.outcome_summary(rows)
    d5 = ledger.at_horizon(summary, 5)
    assert (d5["mean"], d5["n"]) == (round(16 / 3, 2), 3)
    assert d5["from_open"] == {"mean": 7.5, "n": 2, "best": 9.0, "worst": 6.0, "in_band": 1}
    assert ledger.at_horizon(summary, 3)["from_open"]["n"] == 0

    many = [_row(f"T{i}", "2026-08-31", d5=9.0, as_of="x",
                 from_open={"d1": None, "d3": None, "d5": 9.0} if i % 2 == 0 else None)
            for i in range(2 * ledger.MIN_SETUPS_FOR_A_RATE - 2)]
    ev = ledger.evidence([{"date": "2026-08-31", "type": "evening", "shortlist_size": 5,
                           "candidates": [dict(r, rank=i + 1, score=8.0, source="claude", checks={})
                                          for i, r in enumerate(many)], "gated": []}])
    assert ev["overall"]["outcomes"][2]["n"] == 2 * ledger.MIN_SETUPS_FOR_A_RATE - 2
    assert ev["overall"]["outcomes"][2]["from_open"]["n"] == ledger.MIN_SETUPS_FOR_A_RATE - 1
    band = next(b for b in ev["by_score"] if b["verdict"] == "A")
    assert band["enough"] and not band["enough_from_open"], (
        "the close basis clears the floor and the open basis does not; the file says both")
    assert "enough_from_open" in ev["shortlist"] and "enough_from_open" in ev["by_check"][0] if ev["by_check"] else True


@pytest.mark.parametrize("bad", [
    "x", ["d1"], 3,
    {"d1": "1.0", "n1": 0, "from_open": {}},
    {"d1": 1.0, "n1": "5", "from_open": {}},
    {"d1": 1.0, "n1": 5, "from_open": "x"},
    {"d1": 1.0, "n1": 5, "from_open": {"d1": [1.0]}},
    # JSON true, which Python calls an int: without the bool clause it loads
    # and every mean over it silently counts the horizon as +1%.
    {"d1": True, "n1": 5, "from_open": {}},
    {"d1": 1.0, "n1": 5, "from_open": {"n1": False}},
    # Round 9's two keys: the floor the fill applied and the count it left
    # out, read by evidence() and by the page.
    {"d1": 1.0, "n1": 5, "from_open": {}, "liquidity_floor": "12400000"},
    {"d1": 1.0, "n1": 5, "from_open": {}, "below_floor": True},
    # A floor is a positive number of dollars and a count is a whole number
    # of names: the writer produces nothing else, and the fill applied a
    # negative floor as given when the audit planted one.
    {"d1": 1.0, "n1": 5, "from_open": {}, "liquidity_floor": -5.0},
    {"d1": 1.0, "n1": 5, "from_open": {}, "liquidity_floor": 0},
    {"d1": 1.0, "n1": 5, "from_open": {}, "below_floor": -3},
    {"d1": 1.0, "n1": 5, "from_open": {}, "below_floor": 2.5},
])
def test_a_benchmark_block_of_the_wrong_shape_is_refused_at_load(tmp_path, bad):
    """The eighth instance of the one-level-short class, and the first found
    by two audit lenses independently. fill_benchmarks() and evidence() both
    index into this block inside publish(), after the scan and every Claude
    call are paid for; round 7 added it and did not extend the check round 6
    had added for exactly this shape."""
    docs = tmp_path / f"docs-{abs(hash(str(bad)))}"
    docs.mkdir()
    (docs / ledger.LEDGER_NAME).write_text(json.dumps({
        "schema_version": ledger.SCHEMA_VERSION, "app": "SpicyStock", "generated": "x",
        "runs": [{"date": "2026-08-24", "type": "evening", "benchmark": bad,
                  "candidates": [], "gated": []}]}))

    book = ledger.Ledger(docs).load()

    assert book.runs == [] and book.load_error and "benchmark" in book.load_error, bad
    assert ledger.quarantined(docs), "the unreadable file is set aside, not overwritten"


@pytest.mark.parametrize("bad", ["0", True, -1, 2.5, None, [0]])
def test_a_measured_count_that_is_not_a_count_is_refused_at_load(tmp_path, bad):
    """Two readers index this inside publish(), after the scan and every
    Claude call are paid for: the streak window (a night nobody read cannot
    support "nothing preceded this setup") and the benchmark fill. The class
    this check exists for, on the round's own new key."""
    docs = tmp_path / f"docs-{abs(hash(str(bad)))}"
    docs.mkdir()
    (docs / ledger.LEDGER_NAME).write_text(json.dumps({
        "schema_version": ledger.SCHEMA_VERSION, "app": "SpicyStock", "generated": "x",
        "runs": [{"date": "2026-08-24", "type": "evening", "measured": bad,
                  "candidates": [], "gated": []}]}))

    book = ledger.Ledger(docs).load()

    assert book.runs == [] and book.load_error and "measured" in book.load_error, bad


def test_the_run_entry_keeps_how_many_names_the_night_measured(tmp_path):
    """docs/data.json is rewritten every night, and both readers of this
    number are LATER runs, so the ledger entry is the only place it can
    survive to be read. Absent when the run recorded no coverage -- the rule
    `rules` and `duplicate_bars` follow -- because a run from before the count
    existed says nothing about how much it read."""
    book = ledger.Ledger(tmp_path).load()
    run, candidates, gated = _run("2026-09-08")
    run["coverage"] = {"requested": 228, "with_bars": 227, "measured": 225}

    assert book.add_run(run, candidates, gated)["measured"] == 225

    silent, candidates, gated = _run("2026-09-09")
    assert "measured" not in book.add_run(silent, candidates, gated)
    for coverage in ("x", {"measured": "225"}, {"measured": True}, {}):
        run, candidates, gated = _run("2026-09-10")
        run["coverage"] = coverage
        assert "measured" not in book.add_run(run, candidates, gated), coverage


def test_a_run_from_before_the_benchmark_loads_clean(tmp_path):
    """Absent is not broken: a run written before round 7 has no benchmark
    key, loads, and is simply one the rung cannot pair."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / ledger.LEDGER_NAME).write_text(json.dumps({
        "schema_version": ledger.SCHEMA_VERSION, "app": "SpicyStock", "generated": "x",
        "runs": [{"date": "2026-08-24", "type": "evening", "candidates": [], "gated": []}]}))

    book = ledger.Ledger(docs).load()

    assert len(book.runs) == 1 and not book.load_error


@pytest.mark.parametrize("bad", ["x", ["gate.min_lynch_passes"], 3, None])
def test_a_rules_block_of_the_wrong_shape_is_refused_at_load(tmp_path, bad):
    """rules_view() indexes into this block inside evidence(), which publish()
    calls after the scan and every Claude call are paid for -- the
    one-level-short class, refused at load rather than waited for. Null is in
    the list on purpose: the contract says a run from before the fingerprint
    carries NO key, so a null is a shape no writer produces, and this module
    briefly wrote one itself and then refused the file it had written."""
    docs = tmp_path / f"docs-{abs(hash(str(bad)))}"
    docs.mkdir()
    (docs / ledger.LEDGER_NAME).write_text(json.dumps({
        "schema_version": ledger.SCHEMA_VERSION, "app": "SpicyStock", "generated": "x",
        "runs": [{"date": "2026-08-24", "type": "evening", "rules": bad,
                  "candidates": [], "gated": []}]}))

    book = ledger.Ledger(docs).load()

    assert book.runs == [] and book.load_error and "rules" in book.load_error, bad
    assert ledger.quarantined(docs), "the unreadable file is set aside, not overwritten"


def test_a_run_from_before_the_fingerprint_loads_clean(tmp_path):
    """Absent is not the same as broken: a run written before round 8 has no
    rules key and must load, count as one the record cannot attribute, and
    take nothing down."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / ledger.LEDGER_NAME).write_text(json.dumps({
        "schema_version": ledger.SCHEMA_VERSION, "app": "SpicyStock", "generated": "x",
        "runs": [{"date": "2026-08-24", "type": "evening", "candidates": [], "gated": []}]}))

    book = ledger.Ledger(docs).load()

    assert len(book.runs) == 1 and not book.load_error
    assert ledger.rules_view(book.runs) == {"current": None, "sets": 0,
                                            "differ": [], "runs_without": 1}


def test_a_from_open_block_of_the_wrong_shape_is_refused_at_load(tmp_path):
    """The seventh instance of the one-level-short class, closed before it
    could open: a stored row whose from_open is a string, or whose from_open
    d5 is a string, would load clean and take the evening run down inside
    fill_forward_returns() or outcome_summary() after every Claude call had
    been paid for. Refused at load and set aside instead, like the six
    before it."""
    for bad in ("x", ["d1"], 3, {"d1": "1.0", "d3": None, "d5": None}):
        docs = tmp_path / f"docs-{abs(hash(str(bad)))}"
        docs.mkdir()
        row = {"ticker": "AAA", "date": "2026-08-24", "reason": "lynch_gate", "close": 9.0,
               "gain_pct": 4.4, "volume_ratio": 1.8, "lynch_passes": 3, "lynch_total": 6,
               "checks": {}, "context": {},
               "forward_returns": {"d1": None, "d3": None, "d5": None, "as_of": None, "from_open": bad}}
        (docs / ledger.LEDGER_NAME).write_text(json.dumps({
            "schema_version": ledger.SCHEMA_VERSION, "app": "SpicyStock", "generated": "x",
            "runs": [{"date": "2026-08-24", "type": "evening", "candidates": [], "gated": [row]}]}))

        book = ledger.Ledger(docs).load()

        assert book.runs == [] and book.load_error and "from_open" in book.load_error, bad
        assert ledger.quarantined(docs), "the unreadable file is set aside, not overwritten"


def test_an_older_row_gains_the_open_basis_when_its_bars_are_fetched(tmp_path):
    """A row written before the basis existed carries no from_open. The fill
    window still picks it up while a horizon is open on EITHER basis, and
    fills the block key by key, never restating the close basis it already
    holds."""
    book = ledger.Ledger(tmp_path / "docs")
    run, cands, gated = _run("2026-08-24", tickers=("AAA", "BBB"))
    book.add_run(run, cands, gated)
    old, done = book.runs[0]["candidates"][:2]
    old["forward_returns"] = {"d1": 1.0, "d3": None, "d5": None, "as_of": "2026-08-25"}   # pre-basis shape
    # And a row COMPLETE on the close basis in the pre-basis shape: the fill
    # window used to stop at "every d is filled", which would have left this
    # row without an open basis forever.
    done["forward_returns"] = {"d1": 1.0, "d3": 3.0, "d5": 10.0, "as_of": "2026-08-31"}

    assert {"AAA", "BBB"} <= set(book.pending_tickers(date(2026, 9, 4)))
    df = frame_with_opens(closes=[100, 101, 102, 103, 104, 110], opens=[99, 100.5, 101, 102, 103, 104],
                          end="2026-08-31")
    moved = book.fill_forward_returns({"AAA": df, "BBB": df}, date(2026, 9, 4))

    assert moved == 2
    got = book.runs[0]["candidates"][0]["forward_returns"]
    assert got["d1"] == 1.0, "the close-basis value already recorded is never restated"
    assert got["d3"] == 3.0 and got["d5"] == 10.0
    assert got["from_open"] == {"d1": 0.5, "d3": 2.49, "d5": 9.45}
    complete = book.runs[0]["candidates"][1]["forward_returns"]
    assert (complete["d1"], complete["d3"], complete["d5"]) == (1.0, 3.0, 10.0)
    assert complete["from_open"] == {"d1": 0.5, "d3": 2.49, "d5": 9.45}
    assert "BBB" not in book.pending_tickers(date(2026, 9, 4)), "complete on both bases now"


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


def test_the_ledger_row_keeps_the_dollar_volume_rule_6_judged():
    """slim_row() wrote a fixed key set and dollar_volume was not in it, so
    the ledger held the floor on every run entry and the number it was
    compared against on none of its rows. A measurement taken before the
    outcome, kept for the reason `context` is."""
    row = {"ticker": "T", "date": "2026-09-01", "close": 9.0, "gain_pct": 5.0, "volume_ratio": 2.0,
           "lynch_passes": 3, "lynch_total": 6, "lynch_detail": [], "context": {},
           "reason": ledger.LIQUIDITY_REASON, "dollar_volume": 1_000_000}
    assert ledger.slim_row(row, scored=False)["dollar_volume"] == 1_000_000
    assert ledger.slim_row({**row, "rank": 1, "score": 8.0, "verdict": "A",
                            "provenance": {"source": "claude"}}, scored=True)["dollar_volume"] == 1_000_000


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
    assert set(ev["illiquid"]) == set(ev["refused"]) == {"setups", "outcomes", "enough", "enough_from_open"}
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
        "horizon": 5, "mean": 12.0, "n": 1, "best": 12.0, "worst": 12.0, "in_band": 1,
        "from_open": {"mean": None, "n": 0, "best": None, "worst": None, "in_band": 0}}


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


# ===========================================================================
# Round 9: the horizon is a session, not a bar; the entry is a print; the
# benchmark is the names a reader could have bought
# ===========================================================================

def _dated(closes: list, dates: list[str], **columns) -> pd.DataFrame:
    """A frame on the exact dates given, so a hole can be put where the
    test wants it rather than where bdate_range would close it."""
    index = pd.DatetimeIndex(pd.to_datetime(dates), name="timestamp")
    data = {"Close": [float(c) for c in closes], "Volume": [1_000_000] * len(closes)}
    data.update({k: [float(v) for v in vals] for k, vals in columns.items()})
    return pd.DataFrame(data, index=index)


_WEEK = ["2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28",
         "2026-08-31", "2026-09-01"]


def test_the_session_calendar_is_read_across_frames_by_majority():
    """One frame's hole does not remove a session; one frame's phantom bar
    does not add one; a lone frame is its own calendar."""
    whole = _dated(range(7), _WEEK)
    holed = _dated(range(6), _WEEK[:3] + _WEEK[4:])                 # 27 Aug missing
    phantom = _dated(range(8), _WEEK[:5] + ["2026-08-29"] + _WEEK[5:])   # a Saturday bar, mid-frame
    late = _dated(range(2), ["2026-09-01", "2026-09-02"])            # spans only the end

    days = [d.isoformat() for d in ledger.session_calendar({"A": whole, "B": holed, "C": phantom})]

    assert days == _WEEK, "the majority rule settles both"
    assert "2026-08-27" in days, "two of three frames carry the session the third lacks"
    # The Saturday: one of three spanning frames carries it, so it is out. A
    # phantom bar PAST every other frame's last bar would be spanned by its
    # own frame alone and kept -- the rule is a majority of the frames that
    # reach the date, because frames legitimately start and end apart (a
    # new listing, a delisting), and the scan bounds every frame at the
    # session, so nothing it fetches reaches past the others.
    assert "2026-08-29" not in days
    # A phantom bar that is the LAST bar of one frame, on a Saturday two
    # other frames run past without carrying: one of three spanning frames,
    # so out. The spanning test is inclusive of a frame's own first and last
    # bar; a strict one would not count the frame that carries it as
    # spanning it, and 1 of 2 would keep the phantom -- a mutant the
    # round-9 audit's harness lens found surviving.
    ends_on_saturday = _dated(range(6), _WEEK[:5] + ["2026-08-29"])
    past = [d.isoformat() for d in ledger.session_calendar({"E": ends_on_saturday, "A": whole, "B": holed})]
    assert "2026-08-29" not in past and past == _WEEK
    assert ledger.session_calendar({"B": holed}) == [], (
        "one frame is no calendar: it cannot vote against its own hole")
    # A frame that does not span a date has no vote on it: `late` starts on
    # 1 Sep and says nothing about 27 Aug.
    assert "2026-08-27" in [d.isoformat() for d in ledger.session_calendar({"B": holed, "A": whole, "L": late})]
    assert ledger.session_calendar({}) == [] and ledger.session_calendar({"X": None}) == []


def test_a_hole_in_a_frame_leaves_the_horizon_null_rather_than_sliding_it():
    """Reproduced before it was touched: with 27 Aug missing, d3 read the 28
    Aug close (+4%) and d5 the 1 Sep close, each one session late, and
    as_of named the wrong session. Along the calendar of every frame the run
    fetched, the third session's bar is simply absent from this frame, so d3
    is null and d5 is the 31 Aug close it always should have been."""
    holed = _dated([100, 101, 102, 104, 105, 106], _WEEK[:3] + _WEEK[4:])
    whole = _dated([50, 51, 52, 53, 54, 55, 56], _WEEK)
    calendar = ledger.session_calendar({"HOLED": holed, "WHOLE": whole})

    out = ledger.forward_returns(holed, "2026-08-24", calendar)

    assert out["d1"] == 1.0
    assert out["d3"] is None, "the frame has no bar on the third session; that is not the fourth bar"
    # And nothing past the hole either, though the fifth session's bar is
    # there: a calendar date this frame lacks is a hole in the frame or a
    # phantom in the calendar, and past it the two readings disagree about
    # which bar is the fifth session. Refused rather than guessed.
    assert out["d5"] is None
    assert out["as_of"] == "2026-08-25"
    # Without a calendar the frame's own bars are walked and the walk stops
    # at the hole, which alone it cannot tell from a holiday: d1 and no more.
    alone = ledger.forward_returns(holed, "2026-08-24")
    assert (alone["d1"], alone["d3"], alone["d5"], alone["as_of"]) == (1.0, None, None, "2026-08-25")
    # A calendar that does not know the burst is no calendar for this frame.
    assert ledger.forward_returns(holed, "2026-08-24", [date(2027, 1, 4)]) == alone


def test_the_entry_open_must_lie_within_its_own_bar():
    """H refuses a close above its own high as a bad bar; the open basis
    holds the price it says a reader could have paid to the same standard.
    An open outside the bar's range is null on the open basis and leaves
    the close basis untouched; at the edge it is a print."""
    closes, opens = [100, 110, 111], [99, 150, 110]
    highs, lows = [101, 112, 112], [98, 108, 108]
    dates = _WEEK[:3]
    above = _dated(closes, dates, Open=opens, High=highs, Low=lows)
    below = _dated(closes, dates, Open=[99, 50, 110], High=highs, Low=lows)
    edge = _dated(closes, dates, Open=[99, 112, 110], High=highs, Low=lows)
    unchecked = _dated(closes, dates, Open=opens)                      # no High or Low to check

    assert ledger.forward_returns(above, dates[0])["from_open"]["d1"] is None
    assert ledger.forward_returns(above, dates[0])["d1"] == 10.0, "the close basis is not the open's problem"
    assert ledger.forward_returns(below, dates[0])["from_open"]["d1"] is None
    assert ledger.forward_returns(edge, dates[0])["from_open"]["d1"] == round((110 / 112 - 1) * 100, 2)
    # And at the low, the other edge: a print too. Without this the bound
    # could be made strict green (the harness lens's open_low_inclusive).
    at_low = _dated(closes, dates, Open=[99, 108, 110], High=highs, Low=lows)
    assert ledger.forward_returns(at_low, dates[0])["from_open"]["d1"] == round((110 / 108 - 1) * 100, 2)
    assert ledger.forward_returns(unchecked, dates[0])["from_open"]["d1"] == round((110 / 150 - 1) * 100, 2), (
        "a frame with no envelope cannot be checked and is taken as given")


def _traded(closes: list, volume: float, end: str = "2026-08-31") -> pd.DataFrame:
    index = pd.bdate_range(end=end, periods=len(closes), name="timestamp")
    return pd.DataFrame({"Close": [float(c) for c in closes], "Volume": [volume] * len(closes)}, index=index)


def test_the_universe_benchmark_leaves_out_the_names_under_the_floor():
    """The rung averaged over every name that traded, rule 6's refusals
    included -- 30% of them by construction -- so the alternative it printed
    was measurably not what a reader could have bought. With the night's
    floor, a name whose dollar volume on the SESSION sat under it is out and
    counted; without one, every name counts and the block says so."""
    thick = _traded([100, 101, 102, 103, 104, 110], 5_000_000)      # $500M on the session
    thin = _traded([10, 20, 20, 20, 20, 20], 100_000)              # $1M: +100% at d1, and out
    session = thick.index[0].date().isoformat()

    floored = ledger.universe_returns({"THICK": thick, "THIN": thin}, session, floor=2_000_000.0)
    assert (floored["d1"], floored["n1"]) == (1.0, 1), "the thin name's +100% is not in the mean"
    assert (floored["liquidity_floor"], floored["below_floor"]) == (2_000_000.0, 1)

    every = ledger.universe_returns({"THICK": thick, "THIN": thin}, session)
    assert (every["d1"], every["n1"]) == (50.5, 2)
    assert (every["liquidity_floor"], every["below_floor"]) == (None, 0)

    # Inclusive at the floor, the way liquidity_split() keeps a name AT it.
    at_floor = ledger.universe_returns({"THICK": thick, "THIN": thin}, session, floor=1_000_000.0)
    assert (at_floor["n1"], at_floor["below_floor"]) == (2, 0)
    # And rounded to the dollar the way session_dollar_volume() rounds the
    # scan's own, so a name a fraction of a cent under the floor here was
    # AT it the night the floor was set: 9.9999995 x 100,000 is $999,999.95,
    # which the scan calls $1,000,000.
    hair = _traded([9.9999995, 20, 20, 20, 20, 20], 100_000)
    assert ledger.universe_returns({"HAIR": hair}, session, floor=1_000_000.0)["below_floor"] == 0
    # A frame that does not carry the session cannot be under its floor: it
    # is absent from the mean for the reason it always was, not counted twice.
    absent = _traded([10, 20, 20], 100_000, end="2026-08-20")
    gone = ledger.universe_returns({"THICK": thick, "GONE": absent}, session, floor=2_000_000.0)
    assert (gone["n1"], gone["below_floor"]) == (1, 0)


def test_fill_benchmarks_applies_the_runs_own_floor_and_stamps_it(tmp_path):
    """The floor is the RUN's -- rule 6's bar that night, kept in its
    liquidity block -- not tonight's, and a run recorded without one is
    benchmarked over every name and stamped null, which is the truth."""
    book = ledger.Ledger(tmp_path / "docs")
    universe = {"label": "data/symbols.txt (checked in)", "size": 2}
    with_floor, cands, gated = _run("2026-08-24", tickers=("AAA",))
    with_floor["universe"] = dict(universe)
    with_floor["liquidity"] = {"pctile": 30, "floor": 2_000_000.0, "refused": 0}
    book.add_run(with_floor, cands, gated)
    without, cands, gated = _run("2026-08-21", tickers=("AAA",))
    without["universe"] = dict(universe)
    book.add_run(without, cands, gated)
    thick = _traded([100, 101, 102, 103, 104, 110, 111, 112], 5_000_000, end="2026-09-02")   # from 24 Aug
    thin = _traded([10, 20, 20, 20, 20, 20, 20, 20], 100_000, end="2026-09-02")

    moved = book.fill_benchmarks({"THICK": thick, "THIN": thin}, date(2026, 9, 4), universe=universe)

    assert moved == 1, "the 21 Aug run's session is in neither frame"
    floored = next(r for r in book.runs if r["date"] == "2026-08-24")["benchmark"]
    assert (floored["d1"], floored["n1"], floored["liquidity_floor"], floored["below_floor"]) == (1.0, 1, 2_000_000.0, 1)
    assert floored["universe"] == universe

    older = _traded([100, 100, 101, 102, 103, 104, 110], 5_000_000, end="2026-08-31")       # from 21 Aug
    thin_older = _traded([10, 10, 20, 20, 20, 20, 20], 100_000, end="2026-08-31")
    assert book.fill_benchmarks({"THICK": older, "THIN": thin_older}, date(2026, 9, 4), universe=universe) == 1
    unfloored = next(r for r in book.runs if r["date"] == "2026-08-21")["benchmark"]
    assert (unfloored["d1"], unfloored["n1"]) == (0.0, 2), "no floor: every name that traded"
    assert (unfloored["liquidity_floor"], unfloored["below_floor"]) == (None, 0)


def test_a_night_that_measured_nothing_is_left_pending_rather_than_stamped_unfloored(tmp_path):
    """A BLIND night applied no liquidity floor, because it had no dollar
    volumes to draw a percentile from -- so filling its benchmark measured
    every name that traded and stamped the block `liquidity_floor: null`,
    which four surfaces read as "before the floor reached the benchmark, or a
    night rule 6 was off". Neither is this cause, and a measured horizon keeps
    its value, so the false attribution is permanent. Reproduced through the
    fill before this rule existed: d1 filled, below_floor 0, universe stamped.

    It costs nothing to leave pending: a blind night scored no setup, so
    evidence pairs nothing with it."""
    book = ledger.Ledger(tmp_path / "docs")
    universe = {"label": "data/symbols.txt (checked in)", "size": 2}
    blind, cands, gated = _run("2026-08-24", tickers=("AAA",))
    blind["universe"] = dict(universe)
    blind["liquidity"] = {"pctile": 30, "floor": None, "over": 0, "refused": 0}
    blind["coverage"] = {"requested": 2, "with_bars": 2, "measured": 0}
    entry = book.add_run(blind, cands, gated)
    assert entry["measured"] == 0, "the premise: the record says this night read nothing"
    thick = _traded([100, 101, 102, 103, 104, 110, 111, 112], 5_000_000, end="2026-09-02")
    thin = _traded([10, 20, 20, 20, 20, 20, 20, 20], 100_000, end="2026-09-02")

    moved = book.fill_benchmarks({"THICK": thick, "THIN": thin}, date(2026, 9, 4),
                                 universe=universe)

    assert moved == 0
    assert entry["benchmark"] == ledger.empty_benchmark(), (
        "a blind night has no alternative to be measured against")

    # The inverse, on the same frames and the same session: a night that DID
    # measure names is filled, so this rule cannot be satisfied by filling
    # nothing at all.
    seeing = ledger.Ledger(tmp_path / "seeing")
    run, cands, gated = _run("2026-08-24", tickers=("AAA",))
    run["universe"] = dict(universe)
    run["coverage"] = {"requested": 2, "with_bars": 2, "measured": 2}
    kept = seeing.add_run(run, cands, gated)
    assert seeing.fill_benchmarks({"THICK": thick, "THIN": thin}, date(2026, 9, 4),
                                  universe=universe) == 1
    assert kept["benchmark"]["d1"] is not None


def test_the_benchmark_window_is_the_fill_window(tmp_path, monkeypatch):
    """Same window as the forward returns, and until now pinned by nothing
    of its own: a run outside the newest FILL_WINDOW_RUNS is not
    benchmarked, and the run just added always is, backfill or not."""
    monkeypatch.setattr(ledger, "FILL_WINDOW_RUNS", 2)
    universe = {"label": "data/symbols.txt (checked in)", "size": 1}
    book = ledger.Ledger(tmp_path / "docs").load()
    for day in ("2026-08-24", "2026-08-25", "2026-08-26"):
        run, cands, gated = _run(day, tickers=("AAA",))
        run["universe"] = dict(universe)
        book.add_run(run, cands, gated)
    aaa = frame_with_opens(closes=[100, 101, 102, 103, 104, 110, 111, 112, 113],
                           opens=[99, 100, 101, 102, 103, 104, 105, 106, 107], end="2026-09-03")   # from 24 Aug

    assert book.fill_benchmarks({"AAA": aaa}, date(2026, 9, 4), universe=universe) == 2
    outside = next(r for r in book.runs if r["date"] == "2026-08-24")
    assert outside["benchmark"] == ledger.empty_benchmark(), "the third-newest run is outside a window of two"
    assert all(r["benchmark"]["d1"] is not None for r in book.runs if r["date"] != "2026-08-24")

    # The run just added is in the window whatever its session: a backfill.
    book.write()
    later = ledger.Ledger(tmp_path / "docs").load()
    run, cands, gated = _run("2026-08-18", tickers=("AAA",))
    run["universe"] = dict(universe)
    later.add_run(run, cands, gated)
    assert [r["date"] for r in later.runs][-1] == "2026-08-18", "precondition: it sorts last"
    older = frame_with_opens(closes=[100] * 4 + [101, 102, 103, 104, 110, 111, 112, 113, 114],
                             opens=[99] * 13, end="2026-09-03")                               # from 18 Aug
    assert later.fill_benchmarks({"AAA": older}, date(2026, 9, 4), universe=universe) == 1
    assert next(r for r in later.runs if r["date"] == "2026-08-18")["benchmark"]["d5"] is not None


def test_a_benchmark_block_with_no_from_open_is_filled_rather_than_crashed(tmp_path):
    """The one mutant of the rounds 6-7 audit that survived: the fill's
    coercion of a benchmark with no from_open was reachable by no writer, so
    deleting it stayed green. A hand-edited file can hold one -- the shape
    check accepts an absent inner block, since absent is not a shape a
    writer produces wrongly -- and the fill must gain the block rather than
    die on None inside publish()."""
    docs = tmp_path / "docs"
    docs.mkdir()
    universe = {"label": "u", "size": 1}
    (docs / ledger.LEDGER_NAME).write_text(json.dumps({
        "schema_version": ledger.SCHEMA_VERSION, "app": "SpicyStock", "generated": "x",
        "runs": [{"date": "2026-08-24", "type": "evening", "universe": universe,
                  "benchmark": {"d1": None, "d3": None, "d5": None, "n1": 0, "n3": 0, "n5": 0},
                  "candidates": [], "gated": []}]}))
    book = ledger.Ledger(docs).load()
    assert not book.load_error, "precondition: the shape is accepted at load"
    aaa = frame_with_opens(closes=[100, 101, 102, 103, 104, 110], opens=[99, 100, 101, 102, 103, 104])

    assert book.fill_benchmarks({"AAA": aaa}, date(2026, 9, 4), universe=universe) == 1
    bench = book.runs[0]["benchmark"]
    assert bench["from_open"]["d1"] == 1.0 and bench["from_open"]["n1"] == 1


def test_by_check_separation_is_published_per_basis():
    """The page sorts its "best separator" on this column, and the column
    did not switch with the basis. Two checks, one that separates on the
    close basis only and one on the open basis only."""
    rows = []
    for i in range(2 * ledger.MIN_SETUPS_FOR_A_RATE):
        passed_a = i % 2 == 0
        rows.append(dict(_row(f"T{i}", "2026-08-31", d5=10.0 if passed_a else 0.0, as_of="x",
                              from_open={"d1": None, "d3": None, "d5": 5.0}),
                         checks={"A": passed_a, "B": not passed_a},
                         score=8.0, source="claude", rank=i + 1))
    runs = [{"date": "2026-08-31", "type": "evening", "shortlist_size": 5, "candidates": rows, "gated": []}]

    by_code = {c["code"]: c for c in ledger.evidence(runs)["by_check"]}

    assert by_code["A"]["separation"] == 10.0 and by_code["A"]["separation_from_open"] == 0.0
    assert by_code["B"]["separation"] == -10.0 and by_code["B"]["separation_from_open"] == 0.0
    # And null where a side has no open-basis mean, never the close's.
    for row in rows[::2]:
        row["forward_returns"]["from_open"]["d5"] = None
    by_code = {c["code"]: c for c in ledger.evidence(runs)["by_check"]}
    assert by_code["A"]["separation"] == 10.0 and by_code["A"]["separation_from_open"] is None


def test_the_rung_counts_floored_and_unfloored_pairings_apart_from_pending():
    """Three runs: one benchmarked over a floor, one before the floor
    reached the benchmark, one still pending. The page says over which names
    the rung is, so it needs the first two counted and the third in neither
    -- a pending pairing is not a fact about the floor."""
    runs = _record([("2026-08-24", ("AAA",)), ("2026-08-25", ("BBB",)), ("2026-08-31", ("CCC",)),
                    ("2026-09-01", ("DDD",))],
                   returns={("AAA", "2026-08-24"): {"d5": 1.0}, ("BBB", "2026-08-25"): {"d5": 1.0}})
    for run in runs:
        run["benchmark"] = ledger.empty_benchmark()
    by_date = {r["date"]: r for r in runs}
    by_date["2026-08-24"]["benchmark"].update(d5=2.0, n5=150, liquidity_floor=200_000_000.0, below_floor=60)
    by_date["2026-08-25"]["benchmark"].update(d5=3.0, n5=210)                      # measured, no floor
    # Two pending pairings. One carries a floor, which no writer produces --
    # fill_benchmarks() stamps the floor only with a measurement -- and one
    # is the plain empty_benchmark() every not-yet-benchmarked run carries.
    # Both counts are DEFINED over measured pairings, and each of the two
    # `measured` clauses could be deleted green without its own row: the
    # stamped one pins `floored`, the plain one pins `unfloored` (the
    # round-9 audit's R9-3, a mutant the first version of this test missed).
    by_date["2026-08-31"]["benchmark"]["liquidity_floor"] = 100.0

    rung = ledger.evidence(runs)["universe"]

    assert rung["setups"] == 4 and (rung["floored"], rung["unfloored"]) == (1, 1)
    assert ledger.at_horizon(rung["outcomes"], 5)["n"] == 2


# The round-9 audit's findings, each reproduced here before it was fixed.

def test_one_frame_is_no_calendar_and_alone_a_frame_stops_at_the_first_gap():
    """README's own `--tickers BURST` smoke test handed the fill a calendar
    of ONE frame, which is the positional reading round 9 exists to end: a
    hole on the session after the burst put the two-session move into d1 of
    the earlier universe run's row, for good. One frame is no calendar now,
    and without one the walk stops at the first gap wider than a weekend --
    a hole or a holiday, and one frame cannot say which, so both are refused
    and the next scan with a calendar measures what that left open."""
    holed = _dated([100, 101, 102, 104, 105, 106], _WEEK[:3] + _WEEK[4:])   # 27 Aug missing
    assert ledger.session_calendar({"HOLED": holed}) == []

    out = ledger.forward_returns(holed, "2026-08-24")
    assert (out["d1"], out["d3"], out["d5"], out["as_of"]) == (1.0, None, None, "2026-08-25")

    # A Fri -> Tue gap is a holiday or a hole; alone, the frame refuses both.
    holiday = _dated([100, 101, 102, 103, 104, 105],
                     ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04", "2026-09-08", "2026-09-09"])
    out = ledger.forward_returns(holiday, "2026-09-01")
    assert (out["d1"], out["d3"], out["d5"], out["as_of"]) == (1.0, 3.0, None, "2026-09-04")
    # And a weekend is not a gap: Fri -> Mon measures.
    weekend = _dated([100, 101, 102], ["2026-08-28", "2026-08-31", "2026-09-01"])
    assert ledger.forward_returns(weekend, "2026-08-28")["d1"] == 1.0


def test_a_calendar_date_the_frame_lacks_ends_the_measurement_rather_than_sliding_it():
    """A phantom bar a few frames voted into the calendar sits between the
    burst and its horizons; a frame that lacks it must not have its later
    horizons moved onto the wrong session, which is what indexing the
    calendar past it would do. It measures up to the phantom and stops."""
    whole = _dated([100, 101, 102, 103, 104, 110, 111], _WEEK)
    calendar = [date.fromisoformat(d) for d in _WEEK[:5] + ["2026-08-29"] + _WEEK[5:]]    # a Saturday between 28 and 31 Aug

    out = ledger.forward_returns(whole, "2026-08-24", calendar)

    assert (out["d1"], out["d3"]) == (1.0, 3.0), "up to the phantom, the calendar and the frame agree"
    assert out["d5"] is None, "past it the calendar's fifth session is the frame's fourth; refused, not slid"
    assert out["as_of"] == "2026-08-27"
    # And a hole ON THE WAY ends it too, even where the target bar exists:
    # this frame lacks 26 Aug and carries 31 Aug, and d5 stays null.
    gapped = _dated([100, 101, 103, 104, 110, 111], _WEEK[:2] + _WEEK[3:])
    out = ledger.forward_returns(gapped, "2026-08-24", [date.fromisoformat(d) for d in _WEEK])
    assert (out["d1"], out["d3"], out["d5"]) == (1.0, None, None)


def test_a_block_measured_over_every_name_keeps_that_population_when_its_later_horizons_fill(tmp_path):
    """R9-C. A benchmark from before round 9 holds d1 over every name and no
    floor. When a later night fills d3 and d5, applying the run's floor to
    those alone would stamp the WHOLE block 'floored' over a d1 that was
    not, and the rung would count the pairing as measured over a floor.
    One block is one population: the horizons still open are measured over
    the set the block started with, and the stamp stays null."""
    docs = tmp_path / "docs"
    docs.mkdir()
    universe = {"label": "u", "size": 2}
    (docs / ledger.LEDGER_NAME).write_text(json.dumps({
        "schema_version": ledger.SCHEMA_VERSION, "app": "SpicyStock", "generated": "x",
        "runs": [{"date": "2026-08-24", "type": "evening", "universe": universe,
                  "liquidity": {"pctile": 30, "floor": 2_000_000.0, "refused": 0},
                  "benchmark": {"d1": 50.5, "d3": None, "d5": None, "n1": 2, "n3": 0, "n5": 0,
                                "from_open": {"d1": None, "d3": None, "d5": None, "n1": 0, "n3": 0, "n5": 0}},
                  "candidates": [], "gated": []}]}))
    book = ledger.Ledger(docs).load()
    assert not book.load_error
    thick = _traded([100, 101, 102, 103, 104, 110], 5_000_000)
    thin = _traded([10, 20, 20, 20, 20, 20], 100_000)

    assert book.fill_benchmarks({"THICK": thick, "THIN": thin}, date(2026, 9, 4), universe=universe) == 1
    bench = book.runs[0]["benchmark"]
    assert (bench["d1"], bench["n1"]) == (50.5, 2), "the measured horizon keeps its value"
    assert (bench["d3"], bench["n3"]) == (round((3.0 + 100.0) / 2, 2), 2), "over the same two names, not one"
    assert (bench["liquidity_floor"], bench["below_floor"]) == (None, 0)
    assert ledger.evidence([dict(book.runs[0], candidates=[{"ticker": "AAA", "date": "2026-08-24", "score": 8.0,
                                                             "source": "claude", "rank": 1, "checks": {},
                                                             "forward_returns": ledger.empty_returns()}])]
                           )["universe"]["unfloored"] == 1


def test_a_session_bar_that_printed_nothing_is_under_any_floor():
    """R9-D. The scan keeps a bar with no usable dollar volume OUT of the
    distribution the floor is drawn from; the benchmark was keeping the
    same bar IN the mean, on the argument that None is not below the floor.
    A name that traded nothing on the session is under any floor."""
    thick = _traded([100, 101, 102, 103, 104, 110], 5_000_000)
    halt = _traded([10, 20, 20, 20, 20, 20], 0)                      # a +100% d1 on no volume
    session = thick.index[0].date().isoformat()

    out = ledger.universe_returns({"THICK": thick, "HALT": halt}, session, floor=2_000_000.0)

    assert (out["d1"], out["n1"], out["below_floor"]) == (1.0, 1, 1)
    # Without a floor the bar still counts: no rule said it should not.
    assert ledger.universe_returns({"THICK": thick, "HALT": halt}, session)["n1"] == 2


def test_a_nat_in_a_frames_index_is_not_a_session_and_does_not_end_the_run():
    """L2. pd.Timestamp(NaT).date() is NaT again, not None, so a NaT in one
    frame's index took session_calendar() down on "Cannot compare NaT with
    date" -- inside publish(), after the scan and every Claude call. It is
    no date now, everywhere _as_date() is read."""
    nat = _dated([100, 101, 102, 103, 104, 110, 111], _WEEK)
    nat.index = pd.DatetimeIndex([pd.NaT if i == 3 else stamp for i, stamp in enumerate(nat.index)])
    whole = _dated([50, 51, 52, 53, 54, 55, 56], _WEEK)

    assert ledger._as_date(pd.NaT) is None
    assert [d.isoformat() for d in ledger.session_calendar({"N": nat, "W": whole})] == _WEEK
    out = ledger.forward_returns(nat, "2026-08-24", ledger.session_calendar({"N": nat, "W": whole}))
    assert out["d1"] == 1.0 and out["d3"] is None, "the NaT bar is 27 Aug's, which this frame therefore lacks"


def test_an_envelope_that_cannot_be_read_refuses_the_open():
    """L4. A NaN High or Low on the entry bar skipped the check, so an open
    outside the bar was taken as the price paid. The one-bar version of the
    bad bar the checklist drops: an open the bar cannot vouch for is null."""
    closes, opens, dates = [100, 110, 111], [99, 150, 110], _WEEK[:3]
    nan_high = _dated(closes, dates, Open=opens, High=[101, float("nan"), 112], Low=[98, 108, 108])
    assert ledger.forward_returns(nan_high, dates[0])["from_open"]["d1"] is None
    assert ledger.forward_returns(nan_high, dates[0])["d1"] == 10.0
    inside = _dated(closes, dates, Open=[99, 110, 110], High=[101, float("nan"), 112], Low=[98, 108, 108])
    assert ledger.forward_returns(inside, dates[0])["from_open"]["d1"] is None, (
        "not even an open that would have been inside: the bar cannot say so")


def test_the_benchmarks_population_is_stamped_by_the_fill_that_first_measured_it(tmp_path):
    """L1. below_floor was restamped by every fill that moved a horizon while
    each n was frozen the night it filled, so a later fill over a different
    frame set -- a name dropped from the symbol file since -- published
    n1 3 beside below_floor 1 for a session on which five names traded and
    two were under the floor. Stamped once now, by the first fill."""
    book = ledger.Ledger(tmp_path / "docs")
    universe = {"label": "data/symbols.txt (checked in)", "size": 3}
    run, cands, gated = _run("2026-08-24", tickers=("AAA",))
    run["universe"] = dict(universe)
    run["liquidity"] = {"pctile": 30, "floor": 2_000_000.0, "refused": 0}
    book.add_run(run, cands, gated)
    thick = _traded([100, 101, 102], 5_000_000, end="2026-08-26")
    thin = _traded([10, 20, 20], 100_000, end="2026-08-26")
    thin_too = _traded([10, 20, 20], 150_000, end="2026-08-26")
    assert book.fill_benchmarks({"THICK": thick, "THIN": thin, "THINTOO": thin_too},
                                date(2026, 8, 27), universe=universe) == 1
    first = dict(book.runs[0]["benchmark"])
    assert (first["n1"], first["below_floor"], first["d3"]) == (1, 2, None)

    # Two sessions on, one thin name is gone from the file: the horizons
    # still open fill over what is there, and the stamp does not move.
    thick2 = _traded([100, 101, 102, 103, 104, 110], 5_000_000)
    thin2 = _traded([10, 20, 20, 20, 20, 20], 100_000)
    smaller = {"label": universe["label"], "size": 2}
    assert book.fill_benchmarks({"THICK": thick2, "THIN": thin2}, date(2026, 9, 4), universe=smaller) == 1
    bench = book.runs[0]["benchmark"]
    assert (bench["n1"], bench["n3"], bench["n5"]) == (1, 1, 1)
    assert (bench["below_floor"], bench["liquidity_floor"]) == (2, 2_000_000.0), "the first fill's stamp"
    assert bench["universe"] == universe, "and the first fill's universe"


def test_the_entry_is_the_next_sessions_open_not_the_next_bars():
    """R9-1. The entry index moved onto the calendar with the horizons and
    no test could tell: a bar the calendar does not know -- a Saturday print
    -- sits between the burst and the next session, and the entry is the
    next SESSION's open, found by date, not the next bar's."""
    dates = [_WEEK[4], "2026-08-29", _WEEK[5], _WEEK[6]]                  # Fri, a Saturday bar, Mon, Tue
    frame = _dated([100, 100, 110, 111], dates, Open=[99, 150, 105, 110],
                   High=[101, 151, 112, 112], Low=[98, 149, 104, 108])
    whole = _dated([50, 51, 52], [_WEEK[4], _WEEK[5], _WEEK[6]])
    calendar = ledger.session_calendar({"F": frame, "W": whole, "X": whole})

    out = ledger.forward_returns(frame, _WEEK[4], calendar)

    assert [d.isoformat() for d in calendar] == [_WEEK[4], _WEEK[5], _WEEK[6]], "the Saturday is one of three"
    assert out["d1"] == 10.0, "Monday's close against Friday's"
    assert out["from_open"]["d1"] == round((110 / 105 - 1) * 100, 2), "from Monday's open, not the Saturday bar's 150"


@pytest.mark.parametrize("floor", ["abc", "2000000", True, float("nan"), -1.0, None])
def test_a_floor_the_run_entry_cannot_vouch_for_is_no_floor(tmp_path, floor):
    """R9-4. _floor_of()'s defence was documented and dead to the suite: the
    ledger's load check does not read run.liquidity, so a string there
    loaded clean, and a bare float() would have raised inside publish()
    after every Claude call, while isinstance() alone would have taken JSON
    true as a one-dollar floor. Every one of these benchmarks over every
    name and stamps null."""
    docs = tmp_path / "docs"
    docs.mkdir()
    universe = {"label": "u", "size": 2}
    (docs / ledger.LEDGER_NAME).write_text(json.dumps({
        "schema_version": ledger.SCHEMA_VERSION, "app": "SpicyStock", "generated": "x",
        "runs": [{"date": "2026-08-24", "type": "evening", "universe": universe,
                  "liquidity": {"pctile": 30, "floor": floor, "refused": 0},
                  "candidates": [], "gated": []}]}, allow_nan=True))
    book = ledger.Ledger(docs).load()
    assert not book.load_error, "precondition: the shape loads"
    thick = _traded([100, 101, 102, 103, 104, 110], 5_000_000)
    thin = _traded([10, 20, 20, 20, 20, 20], 100_000)

    assert book.fill_benchmarks({"THICK": thick, "THIN": thin}, date(2026, 9, 4), universe=universe) == 1
    bench = book.runs[0]["benchmark"]
    assert (bench["n1"], bench["liquidity_floor"], bench["below_floor"]) == (2, None, 0)


def test_a_named_basket_that_measured_nothing_is_not_a_blind_night():
    """A `--tickers` rehearsal that measured nothing must not blank the day
    number on every burst the next real universe scan finds.

    Reproduced end to end before this rule existed: three universe nights,
    then a two-name rehearsal on the day after a holiday -- both frames holed,
    `measured: 0` -- and the next universe scan printed `blind_session` on a
    name the record had seen three times. The rehearsal read nothing about the
    market either way: it never asked about it. That is the same reasoning
    Ledger.fill_benchmarks() applies when it fills a run only from a scan of
    the universe that run itself scanned, and blind_sessions() did not make it.

    Both halves, so neither can pass by withholding everything: a blind
    UNIVERSE run in the same window still withholds the day.
    """
    basket = {"date": MON, "measured": 0,
              "universe": {"label": "2 named on the command line (--tickers)",
                           "size": 2, "tickers": ["AAA", "BBB"]}}
    assert ledger.Record.of([basket]).blind == frozenset()
    assert ledger.streak([], TUE, record=ledger.Record(DEEP, 160, 160,
                                                      ledger.Record.of([basket]).blind))["day"] == 1

    universe = {"date": MON, "measured": 0,
                "universe": {"label": "data/symbols.txt (checked in)", "size": 228}}
    assert ledger.Record.of([universe]).blind == {date.fromisoformat(MON)}
    assert ledger.streak([], TUE, record=ledger.Record(DEEP, 160, 160,
                                                      ledger.Record.of([universe]).blind))["day"] is None


def test_a_re_scan_of_the_session_the_record_holds_as_blind_still_counts_day_one():
    """The lower edge of the blind window, which is the documented recovery.

    A night measures nothing; the operator fixes the feed and re-runs that
    same session with SCAN_SESSION_DATE. The streak is computed against the
    history as it stands, which still holds the blind entry FOR THAT SESSION
    -- and the burst in front of it is the proof somebody read the session
    after all. `0 < gap` is what allows it; widening the test to `0 <= gap`
    withholds the day number on the very session that was just re-read, and
    no test sat on that edge.
    """
    record = ledger.Record(DEEP, 160, 160, frozenset({date.fromisoformat(TUE)}))
    assert ledger.streak([], TUE, record=record)["day"] == 1
    # And the session before it is inside the window, so this cannot pass by
    # ignoring the blind set.
    day_before = pd.bdate_range(end=TUE, periods=2)[0].date()
    assert ledger.streak([], TUE, record=ledger.Record(DEEP, 160, 160,
                                                      frozenset({day_before})))["day"] is None
