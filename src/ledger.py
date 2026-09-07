"""
Step 9 — the run archive: every scored candidate, and what happened next.

WHY THIS MODULE EXISTS
----------------------
The audit's central finding was that this system cannot tell you whether it
works. It scored 25 candidates a night, emailed five, and kept nothing that
could be checked against a price later — `score_all()` returned `results[:TOP_N]`
and `archive()` wrote exactly that, so TOP_N cut the archive as well as the
email and 80% of every night's judgements were discarded unrecorded. Nothing
in the repo held a score next to the return that followed it, so the ranking
had never been measured against a single realised outcome and could not be.

Two files come out of here, and the split is deliberate:

  docs/data.json    the dashboard's SNAPSHOT of the run that just finished —
                    schema_version 1, the contract in `_contract`, read by
                    docs/index.html in the browser. It is rewritten every run.

  docs/ledger.json  the RECORD. One slim row per candidate per run, kept for
                    MAX_RUNS runs, carrying the score, its provenance, the
                    six checks, and the forward returns filled in by later
                    runs. This is the file a backtest reads.

data.json alone could not be the record: it describes one run, and the run it
describes is always the newest, whose forward returns cannot exist yet. The
ledger is what accumulates. Both are written under docs/ so that whatever
publishes the dashboard publishes the evidence with it.

The ledger row is deliberately slim — no chart paths, no prose, no measured
check values. It is rewritten in full on every run and is meant to be
committed, so its size is a daily git object: ~330 bytes a row keeps a year of
runs near 2 MB, where the dashboard's full rows would be 20 MB.

FORWARD RETURNS
---------------
A candidate's d1/d3/d5 are the percentage change from its burst-day close to
the close 1, 3 and 5 SESSIONS later — sessions, not calendar days, so a
holiday cannot silently shift a horizon — each found by its DATE along the
calendar of every frame the run fetched (session_calendar), so a bar the feed
dropped cannot shift one either: from a hole on, a horizon is null.

Both ends of that division come out of the SAME frame, fetched now. The
archived `close` is deliberately not used as the denominator: a split between
the burst and today restates every price before its ex-date, so an as-traded
close from three weeks ago divided into a split-adjusted one is a -75% return
the market never printed. Two closes from one adjusted frame cannot disagree
about which scale they are on.

`as_of` is the newest session whose close was actually used, or null when none
was — so a row with three nulls and a null `as_of` says "nothing has happened
yet", and can never be read as a claim about data this pipeline does not have.

Filling is a read of bars this pipeline already knows how to fetch; there is
no second data path and no third-party service. What it needs is that the
ledger written by yesterday's run is still there tomorrow — the one thing this
module cannot arrange from the inside. `evening.yml` now commits `docs/` back
to the branch after each run for exactly that reason; see README's "Does the
history actually accumulate?". Remove that step and this file still works
perfectly while quietly measuring nothing, because every run starts from an
empty history.
"""

from __future__ import annotations

import json
import logging
import math
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

#: The dashboard contract this module writes. docs/index.html reads it and
#: README documents it.
SCHEMA_VERSION = 1

#: Forward-return horizons, in sessions after the burst.
HORIZONS = (1, 3, 5)

#: Where both files live. Relative, like archive()'s Path("results"), so the
#: test suite's per-test chdir isolates them and a real run writes the repo's
#: docs/ — which is also what GitHub Pages serves, so a chart written under it
#: is reachable by the page that references it.
DOCS_DIR = Path("docs")
DATA_NAME = "data.json"
LEDGER_NAME = "ledger.json"

#: What a ledger this module could not read is renamed to: the file's own name,
#: the UTC second it was set aside, and this. The stamp is in there because a
#: FIXED name meant the second casualty silently replaced the first — see
#: Ledger.set_aside(), and quarantined(), which is how to find them all.
QUARANTINE_SUFFIX = "unreadable"

#: How many names may be tried inside one second before giving up. Reaching the
#: end means a hundred ledgers were quarantined in the same second, which is a
#: loop somewhere, not a night's work.
QUARANTINE_ATTEMPTS = 100

#: How many runs the ledger keeps. ~260 sessions is a trading year; beyond it
#: the oldest run is dropped, and dropped means gone — the file is the record.
MAX_RUNS = 260

#: How far back a run may still have its forward returns filled in. A row that
#: is still incomplete after this many runs is a name that stopped trading, and
#: re-requesting it every night forever buys nothing. Five sessions of history
#: resolve every horizon, so this is generous by a factor of two.
FILL_WINDOW_RUNS = 10

#: WHAT COUNTS AS "THE SAME SETUP" — the one judgement behind every streak
#: number this module produces, written down once because it is a judgement
#: and not arithmetic.
#:
#: Two appearances of a ticker belong to the same setup when the second lands
#: no more than this many sessions after the first. It is deliberately
#: max(HORIZONS) rather than a fresh guess: the pipeline already commits to
#: five sessions as the window over which a burst's outcome is decided
#: (forward_returns measures d1/d3/d5 and stops), so a second burst inside it
#: happens while the first one is still being judged — the same episode
#: continuing. A burst that arrives after the whole window has resolved is a
#: name that has had a full week to base again, and calling that "day 12" of
#: anything would be a claim about a move that finished. Put the other way
#: round, which is the case that made the rule necessary: the same ticker
#: reappearing two weeks later is day 1 of a new setup, not day 12 of an old
#: one.
#:
#: NOT a claim that the two bursts are related in any deeper sense. It is a
#: grouping rule for a reader — "you saw this name on Monday and passed" — and
#: nothing downstream trades off it.
MAX_STREAK_GAP_SESSIONS = max(HORIZONS)

#: Why a streak carries no day number. Each is a statement about the RECORD,
#: never about the market, and they are kept apart because a reader who is told
#: "we cannot say" acts differently from one told "this is new" — and the file
#: error, the empty file, the undatable file and the shallow file are four
#: different repairs.
#:
#: HISTORY_UNDATED is the fourth because the third was answering for it and
#: lying: a ledger holding runs whose `date` nobody can parse reported
#: no_history, which renders as "no history has been recorded yet" over a file
#: with a year of runs in it. Nothing is recoverable from in here either way,
#: but "the file holds runs I cannot place" sends a reader to the file and "no
#: history yet" sends them nowhere.
NO_HISTORY = "no_history"                    # the ledger holds no run at all
HISTORY_UNDATED = "history_undated"          # it holds runs, none of them datable
HISTORY_UNREADABLE = "history_unreadable"    # it was set aside; see Ledger.load()
WINDOW_NOT_COVERED = "window_not_covered"    # it does not reach back far enough

#: The invariants, in the file rather than only in the docs. tools/make_fixture.py
#: imports this list rather than holding a second copy, so the hand-authored
#: fixture and the pipeline's real output can never describe different contracts
#: — the same reason that generator imports src.lynch's thresholds.
#: The reason word for a burst rule 6 refused: dollar volume below the
#: session's percentile floor. Defined here, beside the contract that names
#: it, because the ledger is where the word has to survive -- src.pipeline
#: writes it into gated_out[].reason, src.emailer and docs/index.html render
#: it, and evidence() keeps the rows carrying it in a population of their own.
#: Not a `veto_` word on purpose: those derive from src.lynch's VETO_RULES and
#: are judged on a frame the checklist has already seen; this one is judged in
#: the scanner against every other name that traded, before the checklist is
#: consulted at all.
LIQUIDITY_REASON = "liquidity_floor"

CONTRACT_INVARIANTS = [
    "candidates holds EVERY scored candidate, ranked by score descending, and is never truncated: len(candidates) == run.scored. The top run.shortlist_size of them are the shortlist that went out by email.",
    "run.scored + len(gated_out) == run.bursts. Nothing a scan found may vanish without appearing in one of the two lists.",
    "Every candidate carries provenance.source: 'claude' when the model actually returned a score, 'fallback' when the offline checklist produced it. A fallback is never labelled claude.",
    "provenance.chart_seen is true only when the scoring model actually received the chart image.",
    "forward_returns and runs[].forward_returns are null until the sessions exist -- with one exception that no session can end: a run that scored nothing has no rows for a later run to fill, so its three horizons and its n stay null and 0 for good, and a reader must be told that rather than 'pending'. Absent is null, never 0 and never a string.",
    "d1/d3/d5 divide the close 1, 3 and 5 sessions after the burst by the BURST-DAY CLOSE: what the setup did. forward_returns.from_open divides the same later closes by the NEXT session's open, the earliest price a reader of the evening email could have paid: what acting on it could have had. Both are paper prices from one venue's official prints with no slippage. Every mean and every evidence outcome carries both, the open basis nested under from_open with its own n, and enough_from_open is the open basis's own licence to be read as a rate -- a surface that shows a number says which basis it is on, and never shows a close-basis number under an open-basis label or the reverse. A row or a run from before this basis existed carries no from_open, which is not a measurement of zero.",
    "chart is a path relative to docs/, or null when the render failed. The file may legitimately not exist yet.",
    "Every burst carries lynch_detail — one row per check, with the value that was measured — whether it was scored or gated out. The dashboard's per-check pass rates are computed over all of them; without the gated ones the rates only describe the candidates that already passed.",
    "Every burst carries streak — day, unknown_reason, first_seen, last_seen, last_score, last_verdict, last_outcome, seen_before, history_from, history_sessions. day is a NUMBER only where the ledger reaches at least MAX_STREAK_GAP_SESSIONS sessions back past the session the setup started on — sessions_between(history_from, first_seen) >= MAX_STREAK_GAP_SESSIONS, which is checkable from the block itself; otherwise day and first_seen are null and unknown_reason is one of no_history, history_undated, history_unreadable, window_not_covered. day is 1 exactly when first_seen is the burst's own session, first_seen is null exactly when day is, and last_seen is null exactly when seen_before is 0. Absence of evidence is never day 1.",
    "history_from is the session of the OLDEST run the ledger holds and history_sessions is how many distinct sessions it holds runs for. Both are facts about the RECORD rather than about the name, so every burst in one run carries the same pair. history_from is null exactly when history_sessions is 0, which is exactly when unknown_reason is no_history, history_undated or history_unreadable. seen_before <= history_sessions always: a name cannot have burst on more sessions than the record holds. The pair is what an unknown day is unknown OVER — it lets a reader be told 'burst on 8 of the 8 sessions in the record, which begins 2026-08-20, and may have started before it' instead of nothing at all.",
    "last_outcome says what became of the appearance last_seen names — 'scored', or the reason it never was: 'liquidity_floor' (rule 6 refused it in the scan, for dollar volume below the session's percentile floor, before the checklist was consulted), 'veto_up_days' (an absolute rule refused it before the pass count was consulted, and it may well have passed 6/6), 'lynch_gate' (rejected by the checklist), 'score_cap' (passed the gate, but the run had already sent its limit of candidates to the scorer). The same four words are gated_out[].reason. Null exactly with last_seen. A gate rejection is never published as an absence of judgement, and neither a veto nor a liquidity refusal is ever published as a gate rejection.",
    "runs[].benchmark.universe is the universe the benchmark was measured over, and it is always the one that run's own universe block names: a run is benchmarked only from a later scan of the same universe, so a --tickers run contributes no benchmark to anything and receives none. A run whose universe no later scan has read keeps a null benchmark forever, which is the honest answer and not a zero.",
    "runs[].rules is every number this screener's rules turned on when that run was made — the scan's strategy thresholds, every threshold and window the checklist names, the vetoes in force and the gate. evidence.rules says how many distinct sets the record holds and which keys differ between them: a mean across runs is a mean over one strategy only while sets is 1, and runs_without counts entries written before the fingerprint existed, which is not the same as agreeing with it. A run from before it carries no rules block, and no surface may read that as agreement.",
    "run.liquidity records rule 6 as this run applied it: pctile (the percentile of the session's dollar volume the floor sits at), floor (that percentile in dollars, null when no name traded or the rule is off), refused (how many bursts sat below it). run.bursts COUNTS those refusals, so they are in gated_out with reason 'liquidity_floor' and carry lynch_detail like every other burst; a run written before this block exists carries none of them and no run.liquidity, which is the truth about that run and not a night with none.",
    "runs[].forward_returns.n counts SETUPS, not rows: consecutive sessions of one name collapse to the session its setup started on, because their d1/d3/d5 windows overlap and measure one move. n is the weight an average across sessions must use; rows is how many rows those setups were collapsed from, so n <= rows always.",
    "evidence is the whole RECORD's view, not this run's: every block in it is computed over docs/ledger.json by src/ledger.py's evidence(), and every mean it carries is over SETUPS (mean_returns' rule) except evidence.by_day, which counts APPEARANCES and says so, because a setup's leading row is day 1 by construction. Every mean carries the n of its own horizon, and `enough` is that n against evidence.min_setups -- a page must not decide for itself whether a number may be read as a rate.",
    "evidence.shortlist, evidence.rest, evidence.refused, evidence.crowded_out and evidence.illiquid are five disjoint populations of setups, each with the same outcomes shape and its own `enough`: the names that went out by email, the scored names that did not, the names the checklist or an absolute rule REFUSED, the names that cleared the gate and were never scored because the call budget filled, and the names rule 6 refused for dollar volume below the session's floor. refused is the alternative the north star names -- what the strategy said no to -- and crowded_out is kept apart from it because a full night must not pad the control with names the screener liked. illiquid is kept apart from refused for the opposite reason: its forward returns are bar prices on names the rule says are too thin to be traded at those prices, so they overstate what a reader could have paid, and folding them into the control would let the thinnest names flatter or damn the strategy on returns nobody could capture.",
    "runs[].benchmark is the universe's equal-weight return from that session's close (d1/d3/d5) and from the next open (from_open), over every name whose frame carries the session and whose dollar volume that session was at or above the run's own liquidity floor -- rule 6's bar that night, run.liquidity.floor -- with nN the number of symbols behind each horizon. benchmark.liquidity_floor is the floor the fill that FIRST measured the block applied -- null for a run recorded without one, when every name that traded counts -- and benchmark.below_floor is how many names that fill left out under it; the horizons a later fill adds are measured over the same population, so one block is one set of names. Null until a later run's scan carried the sessions, and null forever for a run whose universe later scans never fetched. evidence.universe pairs every scored setup with its own session's benchmark, so its outcomes are the alternative 'buy anything in the universe that day' over the same sessions in the same proportions as the picks, and evidence.universe.floored is how many of those pairings were measured over a floor and evidence.universe.unfloored how many were measured with none -- before the floor reached the benchmark, or on a night rule 6 was off, which the block cannot tell apart -- over every name that traded (a pending pairing is in neither); it is a curated list as it stands today, so the comparison carries survivorship bias in the benchmark's favour, and it is beside the control, never inside refused.",
    "d1/d3/d5 and from_open are measured on the bar of the session 1, 3 and 5 sessions after the burst, the sessions being read across every frame the run fetched rather than counted along one frame's bars: a frame with a hole at a horizon carries null there, never the next bar it happens to have, and as_of names the session of the last bar actually used. from_open's entry is the next session's open only where it lies within that bar's own low and high, the standard the checklist holds a close to; outside it the open basis is null on that row.",
    "Numbers are numbers or null. No 'n/a' strings.",
]

#: What the pipeline's own output says about itself. The fixture generator
#: keeps its own `about`, because "this is a hand-authored fixture" and "this
#: is the run that just happened" are different sentences and only one of them
#: can be true of a given file. `run.fixture` says which.
CONTRACT_ABOUT = (
    "Written by src/pipeline.py at the end of a run (see src/ledger.py) and read by "
    "docs/index.html at runtime. run.fixture is false: every number here came out of "
    "the run named in `run`. The per-candidate record with forward returns filled in "
    "by later runs is docs/ledger.json. This block is documentation, not data; "
    "consumers ignore it."
)


# ----------------------------------------------------------------- values --

def _num(value, digits: int | None = None):
    """A JSON number, or None. Never NaN, never a string, never 0 for unknown.

    The contract's "numbers are numbers or null" is enforced here rather than
    trusted: pandas and numpy hand back np.float64 and np.bool_ (which
    json.dump refuses) and NaN (which it happily writes as a bare `NaN` token
    that no JSON parser will read back, so the dashboard would fail to load
    rather than show a gap). Anything that is not a finite number becomes null.
    """
    if value is None or isinstance(value, (str, bool)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if digits is not None:
        return round(number, digits)
    return int(number) if number.is_integer() else number


def _as_date(value) -> date | None:
    """A date from a date, a datetime, a pandas Timestamp or an ISO string."""
    # NaT is an instance of datetime whose .date() is NaT again, so it has
    # to be refused before the isinstance below lets it through.
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        stamp = pd.Timestamp(value)
    except Exception:  # noqa: BLE001 — anything unparseable is simply not a date
        return None
    # NaT is a Timestamp whose .date() is NaT again, not None, and a NaT in a
    # frame's index took session_calendar() down inside publish() -- after
    # the scan and every Claude call -- on "Cannot compare NaT with date".
    return None if pd.isna(stamp) else stamp.date()


def iso_date(value) -> str | None:
    """YYYY-MM-DD, or None. Public because src.pipeline dates its run with it."""
    day = _as_date(value)
    return day.isoformat() if day else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------- checklist --

def check_rows(lynch_result: dict) -> list[dict]:
    """The 2LYNCH detail the dashboard renders: code, label, pass, value.

    Both code and label are DERIVED from the check's own name in
    src.lynch.evaluate_2lynch ("L_linear_prior_move" -> "L", "linear prior
    move"), not copied into a table here. A table would be a second place to
    edit when a check is renamed, and this project has already shipped a
    checklist whose two copies disagreed.
    """
    rows = []
    for name, check in lynch_result.get("checks", {}).items():
        code, _, rest = name.partition("_")
        rows.append({
            "code": code,
            "label": rest.replace("_", " "),
            "pass": bool(check["pass"]),
            "value": str(check["value"]),
        })
    return rows


def check_flags(lynch_result: dict) -> dict:
    """{"2": True, "L": False, ...} — the ledger's compact form of the same.

    The measured values are dropped and the pass/fail kept, because the
    question a backtest asks of an old run is "which checks did this name
    pass", and keeping six sentences per row for a year is 10 MB of git.
    """
    return {row["code"]: row["pass"] for row in check_rows(lynch_result)}


# ------------------------------------------------------------- streaks --
# Step 10. Every run before this one started from nothing: a name that burst
# on Monday and still cleared the filter on Tuesday was presented as a
# brand-new day-1 idea on both nights, with nothing telling the reader they
# had already looked at it and passed. The ledger held every one of those
# earlier appearances and the pipeline only ever wrote to it.
#
# A streak is a VIEW over the record, computed on demand, and it is
# deliberately not stored in the ledger rows themselves. The record holds what
# a run measured; the streak is arithmetic over the record, and a stored copy
# is a second thing that can disagree with the file it was derived from — the
# defect this project has already shipped in a checklist and in a fixture.


def sessions_between(earlier, later) -> int | None:
    """Trading sessions from `earlier` to `later`. None if either is not a date.

    Weekends only, no holidays — the same simplification src.scanner makes in
    current_session(), so the two cannot disagree about what a session is. A
    holiday inside the span makes the gap look one session LONGER than it was,
    which can only break a streak that should have continued. That is the safe
    direction: this code under-claims that two bursts are one episode rather
    than inventing continuity the market did not have.
    """
    start, end = _as_date(earlier), _as_date(later)
    if start is None or end is None:
        return None
    return int(np.busday_count(start, end))


def appearance_index(runs: list[dict]) -> dict[str, list[dict]]:
    """ticker -> every session it burst on in this ledger, oldest first.

    Both scored candidates and gated-out bursts count. The question a streak
    answers is "has this setup been running", and the scan found the burst
    whether or not the checklist let it through to a score — a name gated out
    on Monday and scored on Tuesday is on day 2, not day 1.

    Counting a gated burst is only honest if the reader is TOLD it was gated,
    which is what `outcome` carries: "scored", or the ledger row's own reason
    for never being scored. Without it the streak said "last seen Friday, not
    scored then" over a name the pipeline had looked at and thrown out at the
    quality gate — an absence of judgement standing in for a rejection — and
    said exactly the same words over one that passed every check and lost its
    place to twenty-five better names. `slim_row` keeps that reason; this is
    where it stops being discarded on the way to the streak.

    Keyed by session inside a ticker so that a session scanned twice (a run
    repeated after a failure writes a second entry under a different run type)
    is one appearance, not two. A scored appearance wins over a gated one for
    the same session, because it carries the judgement a reader wants back.
    """
    seen: dict[str, dict[date, dict]] = {}
    for run in runs:
        for scored, rows in ((True, run.get("candidates") or []),
                             (False, run.get("gated") or [])):
            for row in rows:
                ticker, day = row.get("ticker"), _as_date(row.get("date"))
                if not ticker or day is None:
                    continue
                by_session = seen.setdefault(ticker, {})
                if day in by_session and not (scored and by_session[day]["score"] is None):
                    continue
                by_session[day] = {
                    "date": day,
                    "score": _num(row.get("score")) if scored else None,
                    "verdict": row.get("verdict") if scored else None,
                    # The record's own word, not a word chosen here. Today the
                    # pipeline writes "lynch_gate" and "score_cap"; a reason it
                    # learns to write tomorrow arrives at the reader intact
                    # rather than flattened back into "not scored".
                    "outcome": "scored" if scored else (row.get("reason") or None),
                }
    return {ticker: [by_session[k] for k in sorted(by_session)]
            for ticker, by_session in seen.items()}


def session_dates(runs: list[dict]) -> list[date]:
    """Every session this ledger holds a run for, oldest first, one per date.

    Distinct dates, not run entries: a session scanned twice (a morning and an
    evening run, or a re-run after a failure) is one session that was looked
    at, and counting it twice would inflate how much of the record a name is
    being measured against.
    """
    days = {day for day in (_as_date(run.get("date")) for run in runs)
            if day is not None}
    return sorted(days)


def undated_runs(runs: list[dict]) -> int:
    """How many run entries carry a `date` this module cannot read.

    Such an entry is kept, not quarantined: _malformed_rows() draws the line at
    shape, and one unreadable field is not grounds for setting a year of
    outcomes aside. But it is a damaged record, and a run that reads one used
    to report itself clean -- exit 0, no band -- while publishing a snapshot
    whose own contract it broke. The count is what lets the run say so.
    """
    return sum(
        1 for run in runs
        if isinstance(run, dict) and _as_date(run.get("date")) is None
    )


def _dated_row_sessions(runs: list[dict]) -> set[date]:
    """The sessions the ledger's ROWS carry, whatever their run entry says.

    A candidate row's date is the session it burst on, which is the session the
    run that wrote it scanned. So a run whose own `date` is unreadable is still
    placeable through its rows, and the sessions it looked at are not lost from
    the record's span. Read by Record.of(); see the reasoning there.
    """
    days: set[date] = set()
    for run in runs:
        if not isinstance(run, dict):
            continue
        for rows in (run.get("candidates") or [], run.get("gated") or []):
            if not isinstance(rows, list):
                continue
            for row in rows:
                day = _as_date(row.get("date")) if isinstance(row, dict) else None
                if day is not None:
                    days.add(day)
    return days


def oldest_session(runs: list[dict]) -> date | None:
    """The oldest session this ledger holds a run for, or None if it holds none.

    How far back the record has actually LOOKED, which is a different question
    from how far back it goes: a run is a night this pipeline scanned, so a
    name absent from every run between two dates was absent from the market's
    4% bursts on those nights — and a date with no run at all says nothing
    either way. See _why_no_day().
    """
    days = session_dates(runs)
    return days[0] if days else None


class Record(NamedTuple):
    """How much the ledger has LOOKED AT — the one input every streak shares.

    Three numbers, and they travel together because every judgement below is
    made against the same record and a reader has to be able to see it:

      first     the oldest session the ledger holds a run for, or None
      sessions  how many distinct sessions that is
      entries   how many run entries the file holds, datable or not

    `entries` exists only to tell an EMPTY file from an undatable one. Both
    have `first is None` and `sessions == 0`, and the difference is whether the
    reader is told "no history has been recorded yet" — true of the first,
    false and misleading of the second, which is a file with content in it that
    this module cannot place.

    Measured over the whole file, including any run NEWER than the burst being
    judged. That only matters for a backfill, where it makes `sessions` count
    sessions after the burst as well and so makes "burst on N of the M sessions
    in the record" under-claim. Under-claiming is the direction everything in
    this module errs in: it would rather say less than invent continuity.
    """

    first: date | None
    sessions: int
    entries: int

    @classmethod
    def of(cls, runs: list[dict]) -> "Record":
        """Every session the ledger has EVIDENCE it looked at.

        Not `session_dates(runs)` alone, which reads only each run's own
        `date`. A run entry whose date will not parse is kept rather than
        quarantined -- _malformed_rows() guards shape, not content -- and its
        candidate rows still carry the session they burst on, which IS the
        session that run scanned. Counting only the run dates therefore
        published `seen_before: 8` beside `history_sessions: 0`, breaking the
        declared invariant that a name cannot have burst on more sessions than
        the record holds, on a run that reported itself clean with exit 0.

        Taking the union makes that invariant structurally true instead of
        merely asserted: every appearance appearance_index() can date is, by
        construction, a session this record holds. It can only widen the span,
        and it widens it exactly where the evidence is -- a session no run
        entry could name but whose bursts are written down.
        """
        days = sorted(set(session_dates(runs)) | _dated_row_sessions(runs))
        return cls(days[0] if days else None, len(days), len(runs))


#: What a run that has read nothing is measured against: a record with no span
#: at all. Not the same sentence as "this name is new" — see unknown_streak().
EMPTY_RECORD = Record(None, 0, 0)


def _why_no_day(record: Record, first: date | None) -> str | None:
    """Whether the record has looked far enough back to count days at all.

    ABSENCE OF EVIDENCE IS ONLY EVIDENCE OF ABSENCE ONCE YOU HAVE LOOKED FAR
    ENOUGH BACK. "day 1 — new setup" is not a reading of the ledger; it is the
    claim that nothing preceded this burst, and on an empty file that claim is
    made out of nothing at all. It shipped in the same email row as `FAIL
    2_first_or_second_burst: 2 prior 4% bursts in last 20 days`, three lines
    below — two sources answering one reader's question and contradicting each
    other, because the price frame had looked back twenty sessions and the
    ledger had looked back none.

    So a day number requires the ledger to reach at least
    MAX_STREAK_GAP_SESSIONS sessions before the session the claim is about.
    That is the window in which an earlier appearance would have joined this
    setup, so reaching past it is exactly what makes "nothing preceded this"
    a reading rather than a guess.

    Measured from `first` — where the chain of appearances starts — and not
    from the burst's own session, because `first` is where the absence claim
    is actually made. For day 1 the two are the same date and this is the rule
    as written. For a longer chain, `first` is the older one, so this only
    ever refuses a number the other reading would have allowed: a name bursting
    on every session back to the oldest run in the file is not demonstrably on
    day 6 rather than day 12.

    A FLOOR, not a proof. It says the file reaches back past the window; it
    cannot say every session inside the window was scanned, so a night the
    workflow failed can still hide an appearance. It closes the case where
    there is no evidence at all, which is the one that ships on every first
    run — docs/ledger.json is not committed, so the first production run after
    this prints it against every candidate.
    """
    if record.first is None:
        # A file holding runs nobody can date is not an empty one, and saying
        # "no history has been recorded yet" over it is a false sentence about
        # a file with content: the repair is to look at the file, not to wait
        # for it to fill up.
        return HISTORY_UNDATED if record.entries else NO_HISTORY
    reach = sessions_between(record.first, first)
    if reach is None or reach < MAX_STREAK_GAP_SESSIONS:
        return WINDOW_NOT_COVERED
    return None


def unknown_streak(reason: str) -> dict:
    """A streak block that carries no day number, and says which of the four
    reasons it does not.

    Public because src.pipeline holds the one state this module cannot see: a
    history that could not be READ. An unreadable ledger and an empty one look
    identical from in here — both are `runs == []` — and they are different
    sentences, only one of which is about the market.

    history_from and history_sessions are null and 0 for exactly the reasons
    this function serves: a record that could not be read, holds nothing, or
    holds nothing datable has no span to report. Every OTHER kind of unknown —
    window_not_covered — comes out of streak() with its span filled in, because
    there the span is precisely what the reader needs in order to see what the
    unknown is unknown over.
    """
    return {"day": None, "unknown_reason": reason, "first_seen": None,
            "last_seen": None, "last_score": None, "last_verdict": None,
            "last_outcome": None, "seen_before": 0,
            "history_from": None, "history_sessions": 0}


def streak(history: list[dict], session, *, record: Record = EMPTY_RECORD) -> dict:
    """Where a burst on `session` sits in this name's run of appearances.

      day          this appearance's place in the current setup, counting only
                   the sessions it actually burst on. `day: 3` is the third
                   such session, NOT the third calendar session since the
                   setup began — a gap cannot inflate it. NULL when the record
                   has not looked far enough back to say; see _why_no_day().
      unknown_reason  which of no_history / history_undated /
                   history_unreadable / window_not_covered left `day` null.
                   Null when day is a number, so the two can never both be
                   answers.
      first_seen   the session the current setup started on. Equals the
                   burst's own session exactly when day is 1, and is null
                   exactly when day is: it is the same claim — where this
                   setup began — and it cannot be known when day is not.
      last_seen    the most recent EARLIER appearance anywhere in the ledger,
                   or null for a name it has never carried. Deliberately not
                   restricted to the current setup: "seen three weeks ago,
                   day 1 today" is a true and useful pair of facts. It stays
                   a fact when day is unknown, so it is still reported then.
      last_score   what that earlier appearance was scored, and its verdict,
                   or null when it was a burst the gate rejected. They
                   describe the appearance `last_seen` names and no other.
      last_outcome what happened to that appearance: "scored", or the reason
                   it never was ("liquidity_floor" — rule 6 refused it before
                   the checklist saw it; "veto_up_days" — an absolute rule
                   refused it; "lynch_gate" — the checklist rejected it;
                   "score_cap" — it passed and better names filled the night's
                   calls). Null with last_seen. A null last_score means "no
                   number"; it took this field to say WHY, and until it
                   existed a rejection and a model outage read the same.
      seen_before  how many earlier sessions this ticker burst on, in the
                   runs the ledger still keeps. "Never seen before" therefore
                   means "not in the last MAX_RUNS runs", not "not ever" —
                   and 0 alongside a null day means "nothing in a record that
                   cannot answer", not "nothing ever happened".
      history_from the oldest session the RECORD holds a run for, and
      history_sessions  how many distinct sessions that is. The same pair on
                   every row of a run, because they describe the file rather
                   than the name — and they are on the row anyway, because a
                   row travels alone: into the email, into the ledger, onto
                   the page, each read without the run block beside it.

                   THEY ARE WHAT MAKES AN UNKNOWN DAY SAYABLE. `day` is
                   withheld whenever the chain of appearances reaches the
                   oldest run in the file, which is exactly what an unbroken
                   streak does — so the longer a name has been bursting every
                   session, the more certainly its day number is null, and a
                   name that took a fortnight off and burst twice reads "day 2"
                   beside it. The arithmetic is right and stays: you cannot
                   prove a chain did not begin before your record did. But with
                   these two a reader gets "burst on 8 of the 8 sessions in the
                   record, which begins 2026-08-20 — it may have started
                   earlier" where the block alone could only say "unknown", and
                   that sentence is most of what the day number was for.

    `record` is the whole ledger's span (see Record), not this ticker's own
    history: how far back the FILE looked decides whether an absence in it
    means anything.

    Appearances ON `session` itself are excluded: re-running a session already
    in the ledger must not turn every name in it into a repeat of itself, and
    a backfill of an older session must not count the newer runs sitting above
    it in the file. Both are decided by date, so neither depends on where the
    entry landed in the run order.
    """
    day_of = _as_date(session)
    prior = [row for row in history if day_of is not None and row["date"] < day_of]
    prior.sort(key=lambda row: row["date"])

    day, first, chain_end = 1, day_of, day_of
    for row in reversed(prior):
        gap = sessions_between(row["date"], chain_end)
        if gap is None or gap > MAX_STREAK_GAP_SESSIONS:
            break
        day += 1
        first = chain_end = row["date"]

    last = prior[-1] if prior else None
    block = {
        "day": day,
        "unknown_reason": None,
        "first_seen": iso_date(first),
        "last_seen": iso_date(last["date"]) if last else None,
        "last_score": last["score"] if last else None,
        "last_verdict": last["verdict"] if last else None,
        "last_outcome": last["outcome"] if last else None,
        "seen_before": len(prior),
        "history_from": iso_date(record.first),
        "history_sessions": record.sessions,
    }
    unknown = _why_no_day(record, first)
    if unknown:
        # The count and the last sighting survive: they are what the file
        # holds. `day` and `first_seen` do not, because both are claims about
        # what came BEFORE the earliest appearance in view, and that is the
        # one thing a record this shallow cannot answer.
        block.update(day=None, unknown_reason=unknown, first_seen=None)
    return block


def streak_day(block) -> int | None:
    """A streak's `day` as a number, or None for anything that is not one.

    Two callers compare `day > 1`, in src.emailer and src.pipeline, and both
    read it off a docs/data.json row on the morning run. snapshot_problem()
    checks that row's SHAPE and deliberately not its content, so a block
    carrying `"day": "3"` reaches them well-formed -- and `"3" > 1` is a
    TypeError, raised in the emailer after the band and the title were built
    and before anything was sent. The rule that a day is a number or it is
    nothing is written here once, because it used to be written as
    `(... or 0) > 1` in three places, each guarding None and nothing else.

    bool is excluded on purpose: `True > 1` is False and `True + 1` is 2, and
    a day of `true` is not day 1 of anything.
    """
    day = block.get("day") if isinstance(block, dict) else None
    if isinstance(day, bool) or not isinstance(day, (int, float)):
        return None
    return day


def streaks(runs: list[dict], tickers, session,
            *, unreadable: str | None = None) -> dict[str, dict]:
    """One streak block per ticker, against the history in `runs`.

    Four answers, and they are four because collapsing any pair of them puts
    a claim about the market where a fact about a file belongs:

      the ledger could not be READ      `unreadable` — every name unknown
      the ledger holds nothing          no_history
      it holds runs nothing can date    history_undated
      it holds too little to say        window_not_covered

    `unreadable` is passed in rather than inferred, because from here a
    history that failed to parse and one that was never written look the same:
    both are `runs == []`. Ledger.load_error is what knows the difference.
    """
    if unreadable:
        return {ticker: unknown_streak(HISTORY_UNREADABLE) for ticker in tickers}
    index = appearance_index(runs)
    record = Record.of(runs)
    return {ticker: streak(index.get(ticker, []), session, record=record)
            for ticker in tickers}


def setup_leads(runs: list[dict]) -> set[tuple[str, str]]:
    """(ticker, session) for every appearance that STARTS a setup.

    The unit an average has to be taken over. A name that bursts on five
    consecutive sessions is ONE setup, not five observations: its d1/d3/d5
    windows overlap and measure largely the same move, so counting each
    session's row weights that single move five times against a name that
    burst once. Two tickers — one bursting five sessions running at +20%, one
    one-off at -10% — published a mean of +15.0% over "6 names", where the
    honest reading is +5.0% over 2.

    README's reason for making the morning run write-free is this argument
    applied one session deep ("a second entry for one session would count that
    burst twice in every average across runs"); this is the same argument one
    session further out, where the double-counting is not a repeated row but a
    repeated MOVE.

    The setup is represented by its first appearance because that is the one
    whose horizons are furthest along, and because it is stable: a later
    session cannot change which row led. Where the record does not reach back
    to the setup's real start, the earliest appearance IN VIEW leads, which is
    the only row there is to choose.

    What it cannot do is see a session the record does not hold. A night the
    workflow failed, or a holiday inside a gap (sessions_between counts
    weekends only, so a gap reads one session longer than it was), can break
    one setup into two chains and count it twice. That is a smaller version of
    the same error, bounded to holes in the record rather than applying to
    every consecutive session — and it is the direction this module errs in
    everywhere: it under-claims that two bursts are one episode rather than
    inventing continuity the market did not have.
    """
    return set(setup_chains(runs))


def setup_chains(runs: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """(ticker, session) of every lead -> the appearances of that setup, in
    session order, both kinds. setup_leads() is its key set; this is the rule
    itself, kept in one place because two questions read it differently.

    by_check asks whether the checks' verdict on a burst predicted its
    outcome, and the verdict was passed on the FIRST appearance, so that row
    represents the setup there. by_score asks whether the SCORE predicted it,
    and a name refused on day 1 and scored on day 2 -- a 6/6 name three up
    days into a run, allowed back the next session, which is the common case
    the veto produces -- was scored on day 2, so that is the row with a score
    to judge. Keying every block on the lead made that setup invisible to
    every score-keyed view: the paid-for score and its realised outcome were
    in neither overall nor by_score nor by_month, by_ticker printed no best
    score for a name that had one, and the run's own mean skipped it. The
    committed thirty-run history held three such rows.
    """
    # The ORIGINAL rows, not appearance_index()'s reduced view of them: the
    # blocks that read a chain need checks, rank, score and forward_returns.
    # Same rule as appearance_index for one name on one session -- a scored
    # appearance wins over a gated one -- so the two cannot disagree about
    # what counts as an appearance.
    rows_of: dict[str, dict[str, dict]] = {}
    for run in runs:
        if not isinstance(run, dict):
            continue
        for scored, rows in ((True, run.get("candidates") or []),
                             (False, run.get("gated") or [])):
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("ticker"), str):
                    continue
                day = iso_date(row.get("date"))
                if day is None:
                    continue
                by_session = rows_of.setdefault(row["ticker"], {})
                if day in by_session and not (scored and not _scored(by_session[day])):
                    continue
                by_session[day] = row
    chains: dict[tuple[str, str], list[dict]] = {}
    for ticker, by_session in rows_of.items():
        previous, lead = None, None
        for day in sorted(by_session):
            row = by_session[day]
            gap = sessions_between(previous, day) if previous else None
            if gap is None or gap > MAX_STREAK_GAP_SESSIONS:
                lead = (ticker, day)
                chains[lead] = []
            chains[lead].append(row)
            previous = day
    return chains


def _scored(row: dict) -> bool:
    return (isinstance(row.get("score"), (int, float)) and not isinstance(row.get("score"), bool))


def scored_leads(runs: list[dict]) -> set[tuple[str, str]]:
    """(ticker, session) of the first SCORED appearance of every setup that
    was scored at all -- what the score-keyed blocks and the run-level means
    count over. A setup never scored contributes nothing here."""
    out = set()
    for chain in setup_chains(runs).values():
        first = next((r for r in chain if _scored(r)), None)
        if first is not None:
            out.add((first["ticker"], iso_date(first["date"])))
    return out


# ------------------------------------------------------- dashboard rows --

def chart_ref(chart_path: str | None, docs_dir: Path) -> str | None:
    """`charts/AAA.png` — the path the PAGE needs, not the one the run used.

    docs/index.html sets it as an <img src> relative to itself, so a chart the
    run wrote outside docs/ can be referenced but never served. Returns None
    for a chart outside the published directory rather than a path that 404s.
    """
    if not chart_path:
        return None
    try:
        return Path(chart_path).resolve().relative_to(Path(docs_dir).resolve()).as_posix()
    except ValueError:
        log.warning("Chart %s is outside %s, so the dashboard cannot serve it",
                    chart_path, docs_dir)
        return None


def candidate_record(cand, lynch_result: dict, context: dict, score_row: dict,
                     rank: int, docs_dir: Path, chart_error: str | None = None,
                     streak_block: dict | None = None) -> dict:
    """One scored candidate, in the shape docs/data.json's contract describes.

    `streak_block` may still be None, and null still means "unknown" the way
    every other number in this file means it. But the states that used to
    arrive as null now arrive as a BLOCK with a null `day` and an
    `unknown_reason` — "the history could not be read" and "it does not reach
    back far enough" are answers a reader can act on, and a bare null said
    neither. Nothing here ever collapses to a confident day 1.
    """
    return {
        "rank": rank,
        "ticker": cand.ticker,
        "date": iso_date(cand.date),
        "close": _num(cand.close),
        "gain_pct": _num(cand.gain_pct),
        "volume": _num(getattr(cand, "volume", None)),
        "prev_volume": _num(getattr(cand, "prev_volume", None)),
        "volume_ratio": _num(cand.volume_ratio),
        "dollar_volume": _num(cand.dollar_volume),
        "lynch": lynch_result["summary"],
        "lynch_passes": _num(lynch_result["passes"]),
        "lynch_total": _num(lynch_result["total"]),
        "lynch_detail": check_rows(lynch_result),
        "score": _num(score_row["score"]),
        "verdict": score_row.get("verdict"),
        "reason": score_row.get("reason", ""),
        "key_risk": score_row.get("key_risk", ""),
        "provenance": dict(score_row["provenance"]),
        "chart": chart_ref(score_row.get("chart"), docs_dir),
        "chart_error": chart_error,
        "context": {key: _num(value) for key, value in context.items()},
        "streak": dict(streak_block) if streak_block else None,
        "forward_returns": empty_returns(),
    }


def gated_record(cand, lynch_result: dict, context: dict, reason: str,
                 streak_block: dict | None = None) -> dict:
    """One burst that was never scored, and why.

    Carries the full checklist for the same reason the scored rows do: a
    per-check pass rate computed over the survivors alone is survivorship bias
    with a percentage sign, since the names a check rejected are exactly the
    ones missing from it.

    It carries `context` for exactly the same reason, and that argument was
    missing until an audit asked what the two Bonde measurements were for. A
    burst refused by the up-days veto may have passed all six checks, so it is
    the single most informative row the record holds about whether that rule
    earns its keep -- and it was the one row archived without the number the
    rule was applied to.
    """
    return {
        "ticker": cand.ticker,
        "date": iso_date(cand.date),
        "close": _num(cand.close),
        "gain_pct": _num(cand.gain_pct),
        "volume": _num(getattr(cand, "volume", None)),
        "volume_ratio": _num(cand.volume_ratio),
        # The number rule 6 judged, on every gated row and not only the ones
        # it refused: a reader of a liquidity_floor row needs it beside
        # run.liquidity.floor, and a reader of any other row can see how far
        # above the floor a name the checklist rejected was trading.
        "dollar_volume": _num(getattr(cand, "dollar_volume", None)),
        "lynch": lynch_result["summary"],
        "lynch_passes": _num(lynch_result["passes"]),
        "lynch_total": _num(lynch_result["total"]),
        "lynch_detail": check_rows(lynch_result),
        "context": {key: _num(value) for key, value in context.items()},
        "streak": dict(streak_block) if streak_block else None,
        "reason": reason,
    }


# ---------------------------------------------------------- ledger rows --

def empty_returns() -> dict:
    """Pending, spelled the one way the contract allows -- on both bases."""
    out = {f"d{h}": None for h in HORIZONS}
    out["as_of"] = None
    out["from_open"] = {f"d{h}": None for h in HORIZONS}
    return out


def slim_row(row: dict, lynch_result: dict | None = None, *, scored: bool) -> dict:
    """A dashboard row reduced to what a backtest needs, and no more.

    Public because tools/make_fixture.py needs it too: that generator
    hand-authors a dashboard document and then has to produce the LEDGER
    shape of the same rows to compute its evidence block. Writing that
    conversion a second time in the tool is how the fixture and the pipeline
    end up describing different runs, which this project has already shipped
    once in a checklist and once in a contract.
    """
    flags = (check_flags(lynch_result) if lynch_result is not None
             else {d["code"]: d["pass"] for d in row.get("lynch_detail", [])})
    slim = {
        "ticker": row["ticker"],
        "date": row["date"],
        "close": row["close"],
        "gain_pct": row["gain_pct"],
        "volume_ratio": row["volume_ratio"],
        "lynch_passes": row["lynch_passes"],
        "lynch_total": row["lynch_total"],
        "checks": flags,
        # Kept, where every other sentence-shaped field is dropped: these are
        # measurements taken BEFORE the outcome, which is the definition of
        # what a backtest may use, and the ledger is the only file that
        # survives the next run. Dropping them left two of this screener's
        # rules -- the up-days veto and the base-breakdown criterion -- with
        # nowhere for their evidence to accumulate, which was their whole
        # stated justification for being measured at all. Keeping all of
        # `context` rather than the two: choosing a subset here would be
        # choosing which hypotheses may ever be tested.
        "context": dict(row.get("context") or {}),
        # The number rule 6 judged, kept for the reason `context` is: a
        # measurement taken before the outcome. It was written into the
        # one-night file and dropped here, so the ledger -- the only durable
        # file, and the only one with forward returns -- held the floor on
        # every run entry and the dollar volume on none of its rows, and no
        # past refusal could be read against the floor it was refused under.
        "dollar_volume": row.get("dollar_volume"),
        "forward_returns": dict(row.get("forward_returns") or empty_returns()),
    }
    verdict = ({"rank": row["rank"], "score": row["score"], "verdict": row["verdict"],
                "source": row["provenance"]["source"]} if scored
               else {"reason": row["reason"]})
    # The judgement first, then the facts it was made from, then what happened
    # next: the row reads left to right as the question this file exists to
    # answer — was that score worth anything?
    return {"ticker": slim.pop("ticker"), "date": slim.pop("date"), **verdict, **slim}


# ------------------------------------------------------- forward returns --

def session_calendar(frames: dict) -> list[date]:
    """The sessions these frames agree happened, oldest first.

    forward_returns() measures horizon h on the bar of the h-th SESSION after
    the burst, and one frame cannot say which sessions those were: alone, it
    can only count its own bars, so a bar the feed dropped or a full-day halt
    put the third session on the fourth bar the frame had. Reproduced before
    it was touched: with 27 Aug missing from a frame, d3 read the 28 Aug close
    and d5 the 1 Sep close, each one session late, `as_of` dated to the wrong
    session, and nothing said so. That is the class _drop_gapped_symbols()
    closed for the scan, one stage further on, on every row the record holds.

    The calendar is read ACROSS frames instead. A date is a session when at
    least half of the frames that span it -- first bar on or before it, last
    bar on or after -- carry a bar on it, so one frame's hole does not remove
    a session and one frame's phantom bar does not add one. Fewer than two
    frames is NO calendar -- an empty list --
    because one frame cannot vote against its own hole: the round-9 audit
    drove README's own `--tickers BURST` smoke test through the pipeline
    with a hole on the session after the burst, and the one-frame calendar
    let forward_returns() read the two-session move as d1 and write it into
    a real universe row for good. Without a calendar forward_returns() walks
    the frame's own bars and stops at the first step that is not the next
    business day, which cannot tell a hole from a holiday and so refuses
    both; the next scan of the universe, with a calendar, measures what
    that left open.
    """
    if len([df for df in (frames or {}).values() if df is not None and len(df)]) < 2:
        return []
    carrying: dict[date, int] = {}
    spans: list[tuple[date, date]] = []
    for df in (frames or {}).values():
        if df is None or len(df) == 0:
            continue
        days = sorted({d for d in (_as_date(stamp) for stamp in df.index) if d is not None})
        if not days:
            continue
        spans.append((days[0], days[-1]))
        for day in days:
            carrying[day] = carrying.get(day, 0) + 1
    out: list[date] = []
    for day in sorted(carrying):
        spanning = sum(1 for lo, hi in spans if lo <= day <= hi)
        if carrying[day] * 2 >= spanning:
            out.append(day)
    return out


def _next_business_day(day: date) -> date:
    """The business day after `day`. Weekends only, no holidays -- the
    inverse of src.scanner.previous_session(), and wrong in the same one
    place, which is what lets a lone frame refuse a holiday and a hole
    alike rather than guess between them."""
    following = day + timedelta(days=1)
    while following.weekday() >= 5:
        following += timedelta(days=1)
    return following


def _open_within_its_bar(df: pd.DataFrame, at: int, value: float) -> bool:
    """Is this open inside its own bar's low and high?

    The checklist's H refuses a close ABOVE its own high as a bad bar rather
    than reading it as a strong close; the open basis holds its entry price
    to the same standard, since an open printed outside the day's range is a
    price nobody paid. A frame with no High or Low COLUMN (the test frames)
    cannot be checked and is taken as given; a bar whose High or Low is NaN
    is the one-bar version of the bad bar the checklist's _base() drops, and
    an open it cannot check is not a print either.
    """
    for column, outside in (("High", lambda bound: value > bound), ("Low", lambda bound: value < bound)):
        if column in df:
            bound = float(df[column].iloc[at])
            if not math.isfinite(bound) or outside(bound):
                return False
    return True


def forward_returns(df: pd.DataFrame | None, burst_date,
                    calendar: list[date] | None = None) -> dict:
    """d1/d3/d5 for one candidate, measured inside one frame.

    Returns the pending shape when the frame does not carry the burst session
    at all — a name that stopped trading, or a symbol the feed no longer
    knows. A missing measurement is null; it is never zero, and never a guess
    taken from the nearest bar, which would silently move the horizon.

    `calendar` is the sessions the run knows happened (session_calendar()).
    With one, horizon h is the bar on the h-th calendar session after the
    burst, and it is measured only where the frame carries EVERY session
    from the burst to it: a frame that lacks a bar on the way measures
    nothing from there on, rather than the next bar it happens to have, and
    a calendar carrying a date this frame lacks -- a phantom bar a few frames
    voted in -- ends the measurement the same way instead of sliding every
    later horizon onto the wrong session. Without a calendar the frame's own
    bars are walked from the burst and the walk stops at the first step that
    is not the next business day, since one frame cannot tell its own hole
    from a holiday; both are refused, and a later fill with a calendar
    measures the rest.
    """
    out = empty_returns()
    burst = _as_date(burst_date)
    if df is None or burst is None or len(df) == 0 or "Close" not in df:
        return out

    sessions = [_as_date(stamp) for stamp in df.index]
    try:
        start = sessions.index(burst)
    except ValueError:
        return out

    closes = df["Close"].to_numpy(dtype=float)
    base = float(closes[start])
    if not math.isfinite(base) or base <= 0:
        return out

    # WHICH BAR IS THE h-TH SESSION. Along the calendar when the run has one
    # and it knows the burst; along the frame's own bars otherwise. A bar is
    # then found by its DATE, never by its offset, and only while every
    # session on the way is carried too, so a hole in the frame -- or a
    # phantom in the calendar -- ends the measurement instead of sliding a
    # horizon onto a later session.
    position = {day: i for i, day in enumerate(sessions)}
    if calendar and burst in set(calendar):
        days = list(calendar)
        origin = days.index(burst)
        reach = 0                                  # how many sessions on are carried
        while origin + reach + 1 < len(days) and days[origin + reach + 1] in position:
            reach += 1
    else:
        # The frame's own bars, walked from the burst: a step that is not
        # the next business day is a hole or a holiday, and one frame cannot
        # say which. Weekend-only arithmetic, the same as previous_session()
        # in src.scanner, so the two cannot disagree about what a gap is.
        days = sessions
        origin = start
        reach = 0
        while (origin + reach + 1 < len(days)
               and days[origin + reach + 1] == _next_business_day(days[origin + reach])):
            reach += 1

    def bar(steps: int) -> tuple[date | None, int | None]:
        if steps > reach:
            return None, None
        target = days[origin + steps]
        return target, position.get(target)

    # THE SECOND BASIS. d1/d3/d5 divide by the burst-day CLOSE, which is the
    # price the screener measured and the price nobody reading an 18:16 ET
    # email can buy: the earliest a reader can act is the next session's
    # open, and the overnight gap is where a 4% burst's momentum shows up
    # first. Measured here rather than argued: burst close 100, next open
    # 110, next close 111 -- the close basis records d1 = +11.0% while the
    # price a reader could have paid returns +0.91%. from_open divides the
    # SAME later closes by that next open, so the two bases answer two
    # questions about one move: what the setup did, and what a reader who
    # acted on it could have had. Still a paper price -- one venue's official
    # open print, no slippage -- so a better upper bound, not a fill; and
    # null, never a guess from the burst close, when the frame carries no
    # usable open for that session, or an open outside that bar's own range.
    opens = df["Open"].to_numpy(dtype=float) if "Open" in df else None
    entry = None
    _next_session, at_entry = bar(1)
    if opens is not None and at_entry is not None:
        candidate = float(opens[at_entry])
        if (math.isfinite(candidate) and candidate > 0
                and _open_within_its_bar(df, at_entry, candidate)):
            entry = candidate

    measured_at = None
    for horizon in HORIZONS:
        target, at = bar(horizon)
        if at is None:
            continue
        later = float(closes[at])
        if not math.isfinite(later):
            continue
        out[f"d{horizon}"] = _num((later / base - 1) * 100, 2)
        if entry is not None:
            out["from_open"][f"d{horizon}"] = _num((later / entry - 1) * 100, 2)
        measured_at = target
    out["as_of"] = iso_date(measured_at)
    return out


def _dollar_volume_on(df: pd.DataFrame, session: date) -> float | None:
    """Close x volume on `session`'s bar, rounded the way the scan's own
    session_dollar_volume() rounds tonight's -- the same product on an
    earlier bar, so a name is on the same side of a floor here as it was
    the night the floor was set. None when the frame has no bar on the
    session or no volume column to read; 0.0 for a bar on the session that
    printed nothing usable, which is under any floor -- the scan keeps such
    a bar out of the distribution the floor is drawn from, and the round-9
    audit showed the benchmark keeping it IN the mean."""
    if df is None or "Close" not in df or "Volume" not in df:
        return None
    for stamp, close, volume in zip(df.index, df["Close"].to_numpy(dtype=float),
                                    df["Volume"].to_numpy(dtype=float)):
        if _as_date(stamp) == session:
            if not (math.isfinite(close) and math.isfinite(volume)):
                return 0.0
            value = round(close * volume)
            return float(value) if value > 0 else 0.0
    return None


def universe_returns(frames: dict, session, floor: float | None = None,
                     calendar: list[date] | None = None) -> dict:
    """The equal-weight universe return from `session`'s close, and from the
    next open, over every frame that carries the session at or above `floor`:
    the benchmark the north star was missing.

    evidence.refused compares the picks against OTHER BURSTS the gate
    refused, which judges the gate and not the strategy -- a momentum burst
    the checklist said no to is still a momentum burst. The other honest
    alternative is "buy anything in the universe on the same day", and the
    data for it was fetched and thrown away every night. One number per
    horizon, the mean over symbols of forward_returns(); `n` per horizon is
    how many symbols carried that horizon, and a horizon nobody has a value
    for is null, never 0. Names that did not trade the session are absent
    from the mean, not zeros in it.

    `floor` is rule 6's bar THAT night, in dollars (run.liquidity.floor), and
    a name whose dollar volume on the session sat under it is left out and
    counted in `below_floor`. Without it the rung averaged over every name
    that traded, the refused ones included -- 30% of them by construction,
    since the floor IS the 30th percentile of that session's dollar volume --
    so the alternative it printed was measurably not what a reader could
    have bought, on the very names rule 6 says cannot be bought at those
    prints. The same argument keeps evidence.illiquid out of the control.
    None means no floor was applied, which is what a run recorded before
    the block existed can say; it is stamped on the benchmark either way.
    """
    session = _as_date(session)
    per_symbol, excluded = [], 0
    for df in frames.values():
        if floor is not None:
            traded = _dollar_volume_on(df, session)
            if traded is not None and traded < floor:
                excluded += 1
                continue
        per_symbol.append(forward_returns(df, session, calendar))
    out: dict = {}
    from_open: dict = {}
    for horizon in HORIZONS:
        key = f"d{horizon}"
        close_values = [r[key] for r in per_symbol if r[key] is not None]
        open_values = [r["from_open"][key] for r in per_symbol if r["from_open"][key] is not None]
        out[key] = round(math.fsum(close_values) / len(close_values), 2) if close_values else None
        out[f"n{horizon}"] = len(close_values)
        from_open[key] = round(math.fsum(open_values) / len(open_values), 2) if open_values else None
        from_open[f"n{horizon}"] = len(open_values)
    out["from_open"] = from_open
    # The same keys empty_benchmark() carries, so the pending block and a
    # measured one are one shape. Which universe these frames were is the
    # caller's fact, not this function's; fill_benchmarks() stamps it.
    out["universe"] = None
    out["liquidity_floor"] = _num(floor)
    out["below_floor"] = excluded
    return out


def empty_benchmark() -> dict:
    """Pending on both bases, with zero names behind every horizon, and no
    universe yet: `universe` is the block the filling scan was measured over,
    stamped when a horizon is first filled. A benchmark whose universe is not
    the one the run itself scanned is not that run's alternative."""
    out = {f"d{h}": None for h in HORIZONS}
    out.update({f"n{h}": 0 for h in HORIZONS})
    out["from_open"] = {**{f"d{h}": None for h in HORIZONS}, **{f"n{h}": 0 for h in HORIZONS}}
    out["universe"] = None
    # The floor the fill applied (null: none, every name that traded counts)
    # and how many names it left out under it.
    out["liquidity_floor"] = None
    out["below_floor"] = 0
    return out


def _is_number(value) -> bool:
    """A JSON number: int or float, and not the bool JSON also spells as one."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _from_open(returns: dict | None) -> dict:
    """A row's from_open block, or the pending one for a row from before it
    existed. Shape only: a block that is present and not an object is the
    one-level-short class, and _malformed_rows() refuses it at load."""
    block = (returns or {}).get("from_open")
    return block if isinstance(block, dict) else {f"d{h}": None for h in HORIZONS}


def _measured(row: dict) -> bool:
    """Has this row a forward return at any horizon yet?"""
    returns = row.get("forward_returns") or {}
    return any(returns.get(f"d{h}") is not None for h in HORIZONS)


def mean_returns(rows: list[dict], leads: set[tuple[str, str]]) -> dict:
    """The run's mean forward return per horizon, over SETUPS rather than rows.

      d1/d3/d5  the mean over the rows in `leads` — one per setup. A horizon
                nobody has a value for is null rather than 0.0: the dashboard
                weights these by `n` across sessions, and a zero would be
                averaged in as a flat session that never happened.
      n         how many setups are behind those means. THE WEIGHT: the
                dashboard multiplies by it when it averages across sessions,
                so it has to be the count the mean was taken over, or the
                weighting is arithmetic over two different denominators.
      rows      how many rows in this run carry a return at all. `n` is what
                the means count; `rows` is what they were collapsed from, and
                the pair is what lets a label say which of the two it is
                showing instead of calling rows "names".

    `leads` comes from scored_leads() over the WHOLE ledger, not this run:
    whether a row starts a setup is a question about the sessions around it,
    and a run cannot answer it about itself.

    THE SUM IS math.fsum, NOT sum(), AND THAT IS NOT A STYLE CHOICE. CPython
    3.12 changed the builtin `sum()` to compensated (Neumaier) summation for
    floats, so the SAME ledger read by two interpreters published two
    different numbers: sum([9.93, 6.9, 2.86, 2.41]) is 22.099999999999998 on
    3.11 and 22.1 on 3.12, and the mean either side of that lands on opposite
    sides of round(x, 2) -- 5.52 against 5.53. Found by regenerating this
    project's own history fixture under 3.12, which is what CI runs, against a
    copy generated under 3.11, which is what the sandbox runs; two of 1788
    numbers differed and both were run-level means. A cent, and cosmetic --
    but it is the number a reader judges the screener by, and "which Python
    built the file" is not one of its inputs. fsum is correctly rounded, is
    fixed across versions, and does not depend on the order of the rows.
    """
    counted = [row for row in rows if (row.get("ticker"), row.get("date")) in leads]
    out: dict = {}
    for horizon in HORIZONS:
        key = f"d{horizon}"
        values = [row["forward_returns"][key] for row in counted
                  if row.get("forward_returns", {}).get(key) is not None]
        out[key] = round(math.fsum(values) / len(values), 2) if values else None
    out["n"] = sum(1 for row in counted if _measured(row))
    out["rows"] = sum(1 for row in rows if _measured(row))
    # The same means from the next open, over the same setups, with their
    # own n: a row whose frame carried no usable open has a close-basis
    # return and no open-basis one, and the two counts must not be one.
    from_open: dict = {}
    for horizon in HORIZONS:
        key = f"d{horizon}"
        values = [_from_open(row.get("forward_returns"))[key] for row in counted
                  if _from_open(row.get("forward_returns")).get(key) is not None]
        from_open[key] = round(math.fsum(values) / len(values), 2) if values else None
    from_open["n"] = sum(1 for row in counted
                         if any(_from_open(row.get("forward_returns")).get(f"d{h}") is not None
                                for h in HORIZONS))
    out["from_open"] = from_open
    return out


# ------------------------------------------------------------- evidence --
# Step 11. The ledger has been written since step 9 and read for streaks since
# step 10, and NONE of what it holds has ever reached the page: docs/index.html
# fetched data.json and rendered one night, so the question the whole project
# exists to answer -- does a higher score earn a higher forward return -- was
# unanswerable from the only public surface there is.
#
# WHY THIS IS COMPUTED HERE AND NOT IN THE BROWSER. Every number below is an
# average over SETUPS rather than rows, which is mean_returns()' rule and the
# reason scored_leads() exists: a name that bursts on five consecutive sessions
# is one move measured five times, and counting each row weights that one move
# five times against a name that burst once. That rule is a definition, it
# lives in this module, and a second copy of it in JavaScript is precisely the
# defect this project has already shipped twice -- a checklist whose two copies
# disagreed, and a fixture promising a contract the pipeline did not write. The
# page renders these numbers; it does not recompute them.
#
# The cost of that choice, named: the page can only ask the questions this
# function answered when the run was written. A reader who wants a cut nobody
# anticipated has to read docs/ledger.json, which is published beside it.

#: How many setups a bucket needs before its mean is printed AS A RATE rather
#: than as a handful of observations.
#:
#: NOT calibrated from this project's own numbers, which would be circular, and
#: not from the synthetic fixture, whose dispersion is invented. It comes from
#: the claim being tested: Bonde says a burst runs 8-20% over three to five
#: sessions, so the difference that matters is the ~8 points between "nothing
#: happened" and the bottom of that band. At n=30 the 95% interval around a
#: mean is about +/- 0.36 of a standard deviation, so for any dispersion this
#: strategy plausibly has, the interval is comfortably narrower than the gap the
#: claim is about. Below 30 it is not, and the honest rendering is the rows and
#: the count rather than a percentage that reads like a finding.
#:
#: A floor on ARITHMETIC, not a claim of significance. Thirty overlapping
#: momentum bursts in one market regime are not thirty independent draws, and
#: nothing here corrects for that. The page says so where it prints the number.
MIN_SETUPS_FOR_A_RATE = 30

#: The band Bonde claims a burst runs over three to five sessions. Carried into
#: the published block so the page can show whether a bucket's outcomes land in
#: it rather than only whether they are positive -- "+2% at d5" and "in the
#: band the strategy promises" are different verdicts and the second is the one
#: the strategy makes.
#:
#: UNVERIFIED AGAINST THE PRIMARY SOURCE, exactly like src.lynch's
#: MAX_CONSECUTIVE_UP_DAYS and BREAKDOWN_PCT: stockbee.blogspot.com and
#: qullamaggie.net are blocked by this sandbox's egress proxy, so this comes
#: from the brief that specified the work and not from Bonde's own words. It
#: is the number every published verdict about the strategy is measured
#: against, which makes it the one on this list that most deserves checking.
CLAIMED_BAND = (8.0, 20.0)


def outcome_summary(rows: list[dict]) -> list[dict]:
    """One entry per horizon: mean, n, best, worst, and how many hit the band.

    A LIST keyed by `horizon`, not an object keyed "d1"/"d3"/"d5", and that is
    not a style choice. Those three names already mean "a number, the return"
    everywhere else in docs/data.json -- on every candidate's forward_returns
    and on every run's mean -- so reusing them for an OBJECT would put one key
    name over two shapes in one document. The suite's own contract walker
    caught it: it checks every value under a numeric key and reported 18
    violations of "numbers are numbers or null" against a block that was
    perfectly well-formed and badly named.

    `n` is per HORIZON, never per row: a burst three sessions old has a d1 and
    a d3 and no d5, and averaging d5 over the rows that have one while
    reporting the row count would attach a d1-sized sample to a d5-sized
    answer. Every mean on the page carries the n of its own horizon.

    fsum for the same reason mean_returns uses it -- see there.
    """
    def summary(values: list) -> dict:
        return {
            "mean": round(math.fsum(values) / len(values), 2) if values else None,
            "n": len(values),
            "best": max(values) if values else None,
            "worst": min(values) if values else None,
            "in_band": sum(1 for v in values
                           if CLAIMED_BAND[0] <= v <= CLAIMED_BAND[1]),
        }

    def numbers(key: str, basis) -> list:
        return [basis(row)[key] for row in rows
                if isinstance(basis(row).get(key), (int, float))
                and not isinstance(basis(row).get(key), bool)]

    out = []
    for horizon in HORIZONS:
        key = f"d{horizon}"
        entry = {"horizon": horizon}
        entry.update(summary(numbers(key, lambda row: row.get("forward_returns")
                                     if isinstance(row.get("forward_returns"), dict) else {})))
        # The same five numbers from the next open. Nested under its own key
        # rather than spread as d1_from_open and friends, so a reader of
        # either basis walks one shape; the page picks the block by name and
        # labels every number with the basis it came from.
        entry["from_open"] = summary(numbers(key, lambda row: _from_open(row.get("forward_returns"))))
        out.append(entry)
    return out


def at_horizon(outcomes: list[dict], horizon: int) -> dict:
    """The entry for one horizon, or an empty one. Public: the page needs it
    and so does every caller here."""
    for entry in outcomes or []:
        if entry.get("horizon") == horizon:
            return entry
    return {"horizon": horizon, "mean": None, "n": 0, "best": None, "worst": None, "in_band": 0}


def _enough(outcomes: list[dict]) -> bool:
    """Has the longest horizon enough setups behind it to read as a rate?

    d5 decides, not d1: d5 and d3 ARE this strategy's profit and loss, because
    the trade is held three to five sessions and exited. d1 is an early read
    and always has the largest n, so keying on it would license a rate for a
    horizon nobody has measured yet.
    """
    return at_horizon(outcomes, max(HORIZONS))["n"] >= MIN_SETUPS_FOR_A_RATE


def _enough_from_open(outcomes: list[dict]) -> bool:
    """The same floor, on the open basis, whose n can be smaller. Published
    beside `enough` for the reason `enough` is published at all: a page must
    not decide for itself whether a number may be read as a rate, and it must
    not borrow the close basis's licence for the open one."""
    block = at_horizon(outcomes, max(HORIZONS)).get("from_open") or {}
    return (block.get("n") or 0) >= MIN_SETUPS_FOR_A_RATE


def _leading_rows(runs: list[dict], leads: set, *, gated: bool) -> list[dict]:
    """Every row that STARTS a setup, so nothing is counted twice."""
    kinds = ("candidates", "gated") if gated else ("candidates",)
    return [row for run in runs for kind in kinds
            for row in (run.get(kind) or [])
            if isinstance(row, dict) and (row.get("ticker"), row.get("date")) in leads]


def _score_buckets() -> list[tuple[float, float, str]]:
    """The rubric's own bands, not a second set of numbers.

    knowledge/strategy.md defines the verdicts and src.scorer holds them as
    VERDICT_BANDS; a bucketing invented here would be a third opinion about
    what a 7 means. Read from the bottom up so `skip` gets its own bucket.
    """
    from .scorer import VERDICT_BANDS

    edges = sorted(floor for floor, _verdict in VERDICT_BANDS)
    names = {floor: verdict for floor, verdict in VERDICT_BANDS}
    out = [(0.0, edges[0], "skip")]
    for i, floor in enumerate(edges):
        top = edges[i + 1] if i + 1 < len(edges) else 10.01
        out.append((floor, top, names[floor]))
    return out


def evidence(runs: list[dict]) -> dict:
    """The five questions the page exists to answer, computed over the record.

    Every block carries the n its mean was taken over and whether that n
    clears MIN_SETUPS_FOR_A_RATE, so the page never has to decide for itself
    whether a number is worth printing as a rate -- and cannot decide
    differently from the email or from a later reader of the same file.
    """
    chains = setup_chains(runs)
    leads = set(chains)
    # `every`: one row per setup, its FIRST appearance -- the row whose
    # checklist verdict by_check judges. `scored`: one row per setup that was
    # scored at all, its first SCORED appearance -- the row with a score for
    # the score-keyed blocks to judge. A setup is on ONE side of the control
    # below: refused only if no appearance of it was ever scored.
    every = [chain[0] for chain in chains.values()]
    scored = [next(r for r in chain if _scored(r)) for chain in chains.values()
              if any(_scored(r) for r in chain)]
    record = Record.of(runs)
    sessions = session_dates(runs)

    by_score = []
    for low, high, verdict in _score_buckets():
        rows = [r for r in scored
                if isinstance(r.get("score"), (int, float))
                and not isinstance(r.get("score"), bool)
                and low <= r["score"] < high]
        summary = outcome_summary(rows)
        by_score.append({"low": low, "high": round(min(high, 10.0), 2),
                         "verdict": verdict, "setups": len(rows),
                         "enough": _enough(summary), "enough_from_open": _enough_from_open(summary),
                         "outcomes": summary})

    # Which checks predict anything, over every burst the scan found -- scored
    # AND gated. A rate over the survivors alone is survivorship bias with a
    # percentage sign: the names a check rejected are exactly the ones missing.
    codes: list[str] = []
    for row in every:
        for code in (row.get("checks") or {}):
            if code not in codes:
                codes.append(code)
    by_check = []
    for code in codes:
        passed = [r for r in every if (r.get("checks") or {}).get(code) is True]
        failed = [r for r in every if (r.get("checks") or {}).get(code) is False]
        won, lost = outcome_summary(passed), outcome_summary(failed)
        longest = max(HORIZONS)
        win_mean = at_horizon(won, longest)["mean"]
        lose_mean = at_horizon(lost, longest)["mean"]
        separation = (None if win_mean is None or lose_mean is None
                      else round(win_mean - lose_mean, 2))
        # And the same difference on the open basis, because the page sorts
        # its "best separator" on this column and the column did not switch
        # with the basis: the sentence named the check that separated most
        # from the close while every cell beside it read from the open.
        open_win = (at_horizon(won, longest).get("from_open") or {}).get("mean")
        open_lose = (at_horizon(lost, longest).get("from_open") or {}).get("mean")
        separation_from_open = (None if open_win is None or open_lose is None
                                else round(open_win - open_lose, 2))
        by_check.append({
            "code": code,
            "passed": {"setups": len(passed), "outcomes": won},
            "failed": {"setups": len(failed), "outcomes": lost},
            "separation": separation,
            "separation_from_open": separation_from_open,
            "enough": _enough(won) and _enough(lost),
            "enough_from_open": _enough_from_open(won) and _enough_from_open(lost),
        })

    # DOES A STREAK PAY -- and this one counts APPEARANCES, not setups, which
    # is the opposite of every block above and has to be. A setup's leading row
    # is day 1 by construction (setup_leads picks the first appearance), so
    # bucketing leads by day number answers nothing: every bucket but day 1
    # would be empty. The question is precisely about the LATER appearances --
    # is day 3 of a setup worth more than day 1 -- so each appearance is one
    # observation here.
    #
    # The cost is the double-count mean_returns exists to avoid: a name that
    # bursts five sessions running contributes five overlapping windows to
    # these buckets. That is unavoidable for this question, so it is disclosed
    # on the page rather than hidden, and it is why this block is the only one
    # that says "appearances".
    index = appearance_index(runs)
    day_of: dict[tuple, int | None] = {}
    for ticker, appearances in index.items():
        for row in appearances:
            block = streak(appearances, row["date"], record=record)
            day_of[(ticker, iso_date(row["date"]))] = streak_day(block)
    by_number: dict = {}
    for run in runs:
        for row in run.get("candidates") or []:
            if not isinstance(row, dict):
                continue
            by_number.setdefault(day_of.get((row.get("ticker"), row.get("date"))), []).append(row)
    by_day = []
    for day in sorted(by_number, key=lambda d: (d is None, d)):
        summary = outcome_summary(by_number[day])
        by_day.append({"day": day, "appearances": len(by_number[day]),
                       "enough": _enough(summary), "enough_from_open": _enough_from_open(summary),
                         "outcomes": summary})

    # Is it getting better or worse? By calendar month, which is the coarsest
    # bucket a year of runs gives more than a handful of, and the one a reader
    # already thinks in.
    months: dict = {}
    for row in scored:
        if isinstance(row.get("date"), str) and len(row["date"]) >= 7:
            months.setdefault(row["date"][:7], []).append(row)
    by_month = []
    for month in sorted(months):
        summary = outcome_summary(months[month])
        by_month.append({"month": month, "setups": len(months[month]),
                         "enough": _enough(summary), "enough_from_open": _enough_from_open(summary),
                         "outcomes": summary})

    # What happened the last times THIS ticker burst. One row per name, so the
    # page can answer it without the reader fetching the whole record -- and
    # bounded by the universe, not by the number of runs.
    per_ticker: dict = {}
    appearances_of: dict = {}
    for run in runs:
        for kind in ("candidates", "gated"):
            for row in run.get(kind) or []:
                if isinstance(row, dict) and isinstance(row.get("ticker"), str):
                    appearances_of.setdefault(row["ticker"], []).append(row)
    for row in every:
        per_ticker.setdefault(row["ticker"], []).append(row)
    by_ticker = []
    for ticker in sorted(per_ticker, key=str):
        seen = appearances_of.get(ticker, [])
        # best_score over EVERY scored appearance of the name, not over its
        # leads: a name refused on day 1 and scored 8.5 on day 2 printed an
        # em dash here.
        scores = [r["score"] for r in seen if _scored(r)]
        by_ticker.append({
            "ticker": ticker,
            "setups": len(per_ticker[ticker]),
            "appearances": len(seen),
            "last_seen": max((r["date"] for r in seen if isinstance(r.get("date"), str)),
                             default=None),
            "best_score": max(scores) if scores else None,
            "outcomes": outcome_summary(per_ticker[ticker]),
        })

    # Split by the size of the run each row went out in, not by the newest
    # run's: one TOP_N across a record written under two values would put
    # older rows at a boundary their nights never used.
    size_of = {}
    for run in runs:
        if isinstance(run, dict):
            n = run.get("shortlist_size")
            for row in list(run.get("candidates") or []):
                if isinstance(row, dict):
                    size_of[id(row)] = n if isinstance(n, int) and not isinstance(n, bool) else 0
    shortlisted = [r for r in scored if isinstance(r.get("rank"), int) and r["rank"] <= size_of.get(id(r), 0)]
    # Everything scored that was not shortlisted -- including a row with no
    # usable rank, which no version of the writer produces but a hand-edited
    # or older file can hold. It used to fall out of BOTH lists, so the five
    # populations did not add up to the record and the contract walker's sum
    # check found it on a test that plants exactly such a row. A row this
    # module cannot place on the shortlist was not shown to be on it.
    others = [r for r in scored if r not in shortlisted]

    # THE ALTERNATIVE. The north star is "its picks beat the alternative", and
    # until this block the record measured the picks against the claimed band
    # and against each other -- never against the names the strategy said no
    # to, which it archives with the same forward returns and which are the
    # only control that needs no new data. Two populations, kept apart on
    # purpose: `refused` is what the checklist or an absolute rule rejected,
    # which is the strategy's own judgement and the comparison that judges it;
    # `crowded_out` cleared the gate and was never scored because the call
    # budget filled, which is a fact about MAX_TO_SCORE and not about the
    # strategy, and folding it into the refusals would let a full night pad the
    # control with names the screener actually liked. A row with no reason
    # word was written before the reasons existed, when the gate was the only
    # way out, so it counts as refused. Leading rows only, as everywhere.
    # THE BENCHMARK. For every scored setup, the universe's own return from
    # the SAME session's close (and from the same next open), read off the
    # run entry that session belongs to: "buy anything in the universe that
    # day" as the alternative, paired setup by setup so the two sides span
    # the same sessions in the same proportions. A setup whose run has no
    # benchmark yet contributes nothing, and n says how many did. The mean is
    # equal-weight over a curated large-cap list that is what it is NOW, so
    # it carries survivorship bias in the benchmark's favour, and the page
    # says so on the rung.
    benchmark_of = {}
    for run in runs:
        if isinstance(run, dict) and isinstance(run.get("benchmark"), dict):
            benchmark_of[str(run.get("date"))] = run["benchmark"]
    universe_rows = []
    for row in scored:
        bench = benchmark_of.get(str(row.get("date")))
        if not isinstance(bench, dict):
            continue
        universe_rows.append({"forward_returns": {
            **{f"d{h}": bench.get(f"d{h}") for h in HORIZONS},
            "from_open": {f"d{h}": (bench.get("from_open") or {}).get(f"d{h}") for h in HORIZONS}},
            # Whether THIS pairing's benchmark has measured anything yet, and
            # whether it left out the names under its night's floor -- so the
            # rung can say over which names it is, and a pending pairing is
            # neither floored nor unfloored.
            # The close basis alone decides: universe_returns() measures the
            # open basis from the same later close, so an open-basis number
            # without a close-basis one is a shape no writer produces, and a
            # clause for it was a mutant nothing could kill.
            "measured": any(_is_number(bench.get(f"d{h}")) for h in HORIZONS),
            "floored": _is_number(bench.get("liquidity_floor"))})
    unscored = [chain[0] for chain in chains.values() if not any(_scored(r) for r in chain)]
    crowded = [r for r in unscored if r.get("reason") == "score_cap"]
    # Rule 6's refusals are a population of their own, and NOT part of the
    # control: their forward returns are bar prices on names the rule says
    # are too thin to trade at those prices. See the contract sentence.
    illiquid = [r for r in unscored if r.get("reason") == LIQUIDITY_REASON]
    refused = [r for r in unscored if r.get("reason") not in ("score_cap", LIQUIDITY_REASON)]
    return {
        "min_setups": MIN_SETUPS_FOR_A_RATE,
        "band": {"low": CLAIMED_BAND[0], "high": CLAIMED_BAND[1]},
        "horizons": list(HORIZONS),
        "record": {
            "runs": len(runs),
            # Record.of() is what every streak's history_sessions reads; this
            # used to count run dates alone, so one undated run entry made the
            # same page publish two counts of how many sessions one file holds.
            "sessions": record.sessions,
            "from": iso_date(record.first) if record.first else None,
            "to": iso_date(sessions[-1]) if sessions else None,
            "setups": len(every),
            "scored_setups": len(scored),
            "rows": sum(len(run.get("candidates") or []) + len(run.get("gated") or [])
                        for run in runs if isinstance(run, dict)),
        },
        "overall": {"setups": len(scored), "outcomes": outcome_summary(scored)},
        "by_score": by_score,
        "by_check": by_check,
        "by_day": by_day,
        "by_month": by_month,
        "by_ticker": by_ticker,
        "shortlist": _population(shortlisted),
        "rest": _population(others),
        "refused": _population(refused),
        "crowded_out": _population(crowded),
        "illiquid": _population(illiquid),
        # floored: measured pairings whose benchmark left out the names under
        # that night's floor; unfloored: measured pairings benchmarked before
        # the floor reached the benchmark, over every name that traded. A
        # pending pairing is in neither, so the page never calls "not yet"
        # a fact about the floor.
        "universe": {**_population(universe_rows),
                     "floored": sum(1 for row in universe_rows if row["measured"] and row["floored"]),
                     "unfloored": sum(1 for row in universe_rows if row["measured"] and not row["floored"])},
        "rules": rules_view(runs),
    }


def rules_view(runs: list[dict]) -> dict:
    """Which screeners this record spans, and where they differ.

    A mean over runs is only a mean over ONE strategy if the rules did not
    move under it. `current` is the newest run's fingerprint, `sets` how many
    distinct ones the record holds, `differ` the exact keys that are not the
    same in all of them -- named, because "the rules changed" is not
    actionable and "min_gain_pct and gate.min_lynch_passes changed" is -- and
    `runs_without` how many entries predate the fingerprint, which is a
    different thing from agreeing with it and must not be counted as
    agreement.
    """
    seen: list[dict] = []
    without = 0
    for run in runs:
        block = run.get("rules") if isinstance(run, dict) else None
        if not isinstance(block, dict):
            without += 1
            continue
        if block not in seen:
            seen.append(block)
    keys = sorted({key for block in seen for key in block})
    differ = sorted(
        key for key in keys
        if len({json.dumps(block.get(key), sort_keys=True) for block in seen}) > 1)
    return {"current": dict(seen[0]) if seen else None, "sets": len(seen),
            "differ": differ, "runs_without": without}


def _population(rows: list[dict]) -> dict:
    """One comparable population: its size, its outcomes, and whether the
    longest horizon has enough behind it to read as a rate. `enough` travels
    with the block for the same reason by_score carries it -- a page must not
    decide for itself, and cannot then decide differently from a later reader
    of the same file."""
    summary = outcome_summary(rows)
    return {"setups": len(rows), "outcomes": summary, "enough": _enough(summary),
            "enough_from_open": _enough_from_open(summary)}


def _shortlist_size(runs: list[dict]) -> int:
    """How many names the runs in this record actually emailed.

    Read off the record rather than imported from src.pipeline's TOP_N,
    because the record spans runs and TOP_N is today's value: a ledger written
    before it changed would otherwise be split at a boundary those runs never
    used. The newest run that states one wins; 0 means no run said, and then
    nothing is called a shortlist.
    """
    for run in runs:
        size = run.get("shortlist_size") if isinstance(run, dict) else None
        if isinstance(size, int) and not isinstance(size, bool) and size > 0:
            return size
    return 0


# -------------------------------------------------------------- the file --

def _malformed_rows(runs: list[dict]) -> str | None:
    """What is wrong INSIDE these run entries, or None if nothing is.

    The same rule as load()'s two checks on the document itself, one level
    further in, and
    it is here because both of the alternatives are defects this module has
    already shipped once. A run entry whose `candidates` is a string is either
    skipped silently — the row-level filter again, publishing streaks and means
    over a record with holes nobody is told about — or iterated, which hands
    appearance_index() a single character and raises AttributeError out of the
    middle of a run that had already fetched its bars and paid for its scores.
    Reproduced: `{"candidates": "AAA"}` in one entry loads clean, sets no
    load_error, and takes the run down inside streaks().

    THE LINE IS SHAPE, NOT CONTENT. write() emits one document: an object,
    whose `runs` is a list of objects, each with `candidates` and `gated` lists
    of objects. That structure is what every reader in this module indexes into,
    so a break anywhere in it means the file did not come out of write() and is
    kept rather than half-read. What a row SAYS is content — a date nothing can
    parse stays a row this module can hold, count and rewrite, and the streak
    layer reports it in words (see HISTORY_UNDATED) instead of crashing over it.
    """
    for run in runs:
        # The rules block is indexed into by rules_view() inside evidence(),
        # which publish() calls after the scan and every Claude call are paid
        # for: the one-level-short class again, refused at load rather than
        # waited for. Absent is a run from before the fingerprint existed.
        if "rules" in run and not isinstance(run["rules"], dict):
            return (f"holds a run for {run.get('date')!r} whose rules is a JSON "
                    f"{type(run['rules']).__name__} rather than an object")
        # THE EIGHTH INSTANCE. Round 7 added a nested object to every entry --
        # benchmark, with from_open one level inside it -- and did not extend
        # the check round 6 added for exactly this class. fill_benchmarks()
        # and evidence() both index into it, inside publish(), after the scan
        # and every Claude call are paid for. Absent is a run from before the
        # benchmark existed; present in a shape no writer produces is refused.
        # Two audit lenses found this independently, which is the argument for
        # sweeping a class rather than closing its instances one at a time.
        bench = run.get("benchmark")
        if "benchmark" in run and not isinstance(bench, dict):
            return (f"holds a run for {run.get('date')!r} whose benchmark is a JSON "
                    f"{type(bench).__name__} rather than an object")
        if isinstance(bench, dict):
            inner = bench.get("from_open")
            if inner is not None and not isinstance(inner, dict):
                return (f"holds a run for {run.get('date')!r} whose benchmark.from_open "
                        f"is a JSON {type(inner).__name__} rather than an object")
            for block, where in ((bench, "benchmark"), (inner or {}, "benchmark.from_open")):
                for horizon in HORIZONS:
                    for key in (f"d{horizon}", f"n{horizon}"):
                        value = block.get(key)
                        if value is not None and (isinstance(value, bool)
                                                  or not isinstance(value, (int, float))):
                            return (f"holds a run for {run.get('date')!r} whose {where}.{key} "
                                    f"is a JSON {type(value).__name__} rather than a number")
            # The floor the fill applied and the count it left out: read by
            # evidence() and by the page, so a string there is the same class.
            # A floor is a positive number of dollars and a count is a whole
            # number of names; the writer produces nothing else.
            floor = bench.get("liquidity_floor")
            if floor is not None and (not _is_number(floor) or not floor > 0):
                return (f"holds a run for {run.get('date')!r} whose benchmark.liquidity_floor "
                        f"is {floor!r} rather than a positive number or null")
            left_out = bench.get("below_floor")
            if left_out is not None and (not isinstance(left_out, int) or isinstance(left_out, bool)
                                         or left_out < 0):
                return (f"holds a run for {run.get('date')!r} whose benchmark.below_floor "
                        f"is {left_out!r} rather than a count")
    for key in ("candidates", "gated"):
        for run in runs:
            rows = run.get(key)
            if not isinstance(rows, list):
                return (f"holds a run for {run.get('date')!r} whose {key} is a JSON "
                        f"{type(rows).__name__} rather than a list of rows")
            if any(not isinstance(row, dict) for row in rows):
                return (f"holds a run for {run.get('date')!r} with {key} rows that "
                        "are not ledger rows")
            # AND THE ONE OBJECT INSIDE A ROW THAT IS INDEXED INTO. A row's
            # forward_returns is written as an object by slim_row() every time,
            # and read as one by _fillable(), _measured() and mean_returns()
            # -- the last of which runs inside add_run(), which publish()
            # calls after the scan and every Claude call have been paid for.
            # A row carrying `"forward_returns": "x"` (or null: the `or {}`
            # guards elsewhere do not cover a key that is present and null)
            # loaded clean, computed every streak, and then took the evening
            # run down in _recompute_means() before write() -- the night's
            # scores gone from the record, the file still holding the row
            # that did it. Reproduced against a one-row ledger. Shape, not
            # content: the value inside the object is still whatever it is.
            for row in rows:
                if "forward_returns" in row and not isinstance(row["forward_returns"], dict):
                    return (f"holds a run for {run.get('date')!r} with a {key} row "
                            f"({row.get('ticker')!r}) whose forward_returns is a JSON "
                            f"{type(row['forward_returns']).__name__} rather than an object")
                # THE SIXTH INSTANCE of the class, found by sweeping one level
                # further than the fifth. Each of these loaded clean and took
                # the EVENING run down after the scan and every Claude call
                # were paid for: an unhashable ticker in streaks(), an
                # unhashable date in add_run(), a string return under
                # math.fsum, a list-shaped `checks` under .get() in
                # evidence(). And because the file was not set aside, every
                # night after failed the same way until someone edited it.
                if not isinstance(row.get("ticker"), str):
                    return (f"holds a run for {run.get('date')!r} with a {key} row whose "
                            f"ticker is a JSON {type(row.get('ticker')).__name__} rather than a string")
                if row.get("date") is not None and not isinstance(row.get("date"), str):
                    return (f"holds a run for {run.get('date')!r} with a {key} row "
                            f"({row['ticker']!r}) whose date is a JSON "
                            f"{type(row['date']).__name__} rather than a string")
                if row.get("checks") is not None and not isinstance(row["checks"], dict):
                    return (f"holds a run for {run.get('date')!r} with a {key} row "
                            f"({row['ticker']!r}) whose checks is a JSON "
                            f"{type(row['checks']).__name__} rather than an object")
                returns = row.get("forward_returns") or {}
                for horizon in HORIZONS:
                    value = returns.get(f"d{horizon}")
                    if value is not None and (isinstance(value, bool)
                                              or not isinstance(value, (int, float))):
                        return (f"holds a run for {run.get('date')!r} with a {key} row "
                                f"({row['ticker']!r}) whose d{horizon} return is a JSON "
                                f"{type(value).__name__} rather than a number")
                # THE SEVENTH INSTANCE, pre-empted rather than found: the open
                # basis is one object further in, read by fill_forward_returns()
                # inside publish() and by outcome_summary() inside evidence(),
                # both after the scan and every Claude call have been paid for.
                # Absent is a row from before the basis existed and is fine;
                # present and not an object, or holding a string where a number
                # belongs, is a file that did not come out of write().
                block = returns.get("from_open")
                if block is not None and not isinstance(block, dict):
                    return (f"holds a run for {run.get('date')!r} with a {key} row "
                            f"({row['ticker']!r}) whose from_open is a JSON "
                            f"{type(block).__name__} rather than an object")
                for horizon in HORIZONS:
                    value = (block or {}).get(f"d{horizon}")
                    if value is not None and (isinstance(value, bool)
                                              or not isinstance(value, (int, float))):
                        return (f"holds a run for {run.get('date')!r} with a {key} row "
                                f"({row['ticker']!r}) whose from_open d{horizon} return is a "
                                f"JSON {type(value).__name__} rather than a number")
    return None


class Ledger:
    """docs/ledger.json, plus the docs/data.json view of the run just added.

    Load it, add the run that just finished, fill in whatever forward returns
    the new bars have made knowable, write both files. Every step is separate
    so that the one which touches the network (fetching those bars) stays in
    src.pipeline with the pipeline's other boundaries, and everything here can
    be driven from a dict of frames.
    """

    def __init__(self, docs_dir: Path | str = DOCS_DIR) -> None:
        self.docs_dir = Path(docs_dir)
        self.runs: list[dict] = []       # ordered by session, newest first
        self.latest: dict | None = None  # the full record of the run just added
        #: Why `runs` is empty, when it is empty because reading failed rather
        #: than because there was nothing to read. load() only logged that
        #: distinction, and a log is not a place a run reports anything: step
        #: 10 reads the history back to tell a reader that a name is a repeat,
        #: so "there is no history" and "the history could not be read" stop
        #: being the same answer. src.pipeline puts this in the RunReport.
        self.load_error: str | None = None

    # -- persistence ---------------------------------------------------
    @property
    def path(self) -> Path:
        return self.docs_dir / LEDGER_NAME

    @property
    def data_path(self) -> Path:
        return self.docs_dir / DATA_NAME

    def load(self) -> "Ledger":
        """Read the existing ledger. A missing or unreadable one starts empty.

        A file this module cannot read is a loud warning and an empty history,
        not a crash: the run happening now is worth more than the runs already
        gone, and it would otherwise be lost to a file it never wrote.

        But it is moved aside first, never written over. Starting a fresh
        history on top of an unreadable one would destroy the record over a
        transient read error or a schema bump — the accumulated outcomes are
        the one thing here that cannot be recomputed.
        """
        try:
            raw = json.loads(self.path.read_text())
        except FileNotFoundError:
            return self
        except Exception as e:  # noqa: BLE001 — every failure keeps the file; see set_aside()
            log.error("Ledger %s is unreadable (%s) — moving it aside and starting "
                      "a new history", self.path, e)
            return self.set_aside(f"{self.path} is unreadable ({type(e).__name__}: {e})")
        if not isinstance(raw, dict):
            # Valid JSON is not the same thing as a ledger. `[]`, `null`, `4`
            # and `"docs/ledger.json"` all parse, and every one of them used to
            # raise AttributeError out of the .get() below — out of a function
            # whose whole contract is that it does not raise, with load_error
            # still unset and the file NOT moved aside, so the next write()
            # replaced it. The catch-all above covers what json.loads DOES;
            # this covers what it returns.
            log.error("Ledger %s is a %s, not a ledger object — moving it aside",
                      self.path, type(raw).__name__)
            return self.set_aside(
                f"{self.path} holds a JSON {type(raw).__name__}, not a ledger object")
        if raw.get("fixture"):
            # A FIXTURE IS NOT A RECORD -- the same rule read_snapshot() applies
            # to docs/data.json, one file over. tests/fixtures/history/ledger.json
            # is thirty invented sessions written by the real Ledger, so it loads
            # perfectly: drop it into docs/ and the next run adopts its outcomes
            # as its own, rewrites it WITHOUT the marker, and every mean and
            # streak the page publishes from then on is built on invented data
            # that no longer says it is invented. Nothing else would ever notice.
            log.error("Ledger %s is a fixture (fixture is true), not a record — "
                      "moving it aside rather than accumulating into it", self.path)
            return self.set_aside(
                f"{self.path} is a fixture (fixture is true), not a run history; its "
                "outcomes are invented and must never be adopted as this record")
        if raw.get("schema_version") != SCHEMA_VERSION:
            log.error("Ledger %s is schema_version %r, not %d — moving it aside "
                      "rather than merging into it",
                      self.path, raw.get("schema_version"), SCHEMA_VERSION)
            return self.set_aside(
                f"{self.path} is schema_version {raw.get('schema_version')!r}, "
                f"not {SCHEMA_VERSION}")
        runs = raw.get("runs")
        if not isinstance(runs, list):
            # The check above covers what json.loads RETURNED; this covers what
            # a ledger object HOLDS, and it is the same defect one level in.
            # `{"schema_version": 1, "runs": "…"}` — or "runs" missing entirely
            # — used to fall into an `else []` with load_error still None and
            # the file still in place, so the next write() put a one-run ledger
            # where a year of outcomes had been, while the run told its reader
            # "no history has been recorded yet" about a file that held one.
            what = ("carries no runs at all" if "runs" not in raw else
                    f"holds a JSON {type(runs).__name__} where its runs list should be")
            log.error("Ledger %s %s — moving it aside", self.path, what)
            return self.set_aside(f"{self.path} {what}")
        junk = sum(1 for row in runs if not isinstance(row, dict))
        if junk:
            # AND THE SAME DEFECT ONE LEVEL FURTHER IN. A row-level filter that
            # discards silently is not a milder version of the two above: it
            # publishes day numbers and means computed over whatever survived
            # the filter, which is worse than publishing none, and the next
            # write() still replaces the file the discarded rows were in.
            #
            # The tolerated fraction is ZERO, deliberately, because no other
            # fraction can be justified. write() emits every run as an object,
            # in one document, in one call; a file that parses and holds
            # something else did not come out of write() at all — a hand-edit, a
            # merge conflict resolved by hand, another tool, a schema change —
            # and there is no reading of "half the rows are junk" under which
            # the other half is a record rather than a guess. What this costs is
            # one run's streaks; what it buys is that the file is still on disk
            # to be repaired, which is the only thing here that cannot be
            # recomputed.
            log.error("Ledger %s holds %d of %d run entries that are not objects "
                      "— moving it aside", self.path, junk, len(runs))
            return self.set_aside(
                f"{self.path} holds {junk} of {len(runs)} run entries that are not "
                "ledger runs")
        inside = _malformed_rows(runs)
        if inside:
            # AND ONE LEVEL FURTHER IN AGAIN. See _malformed_rows() for where
            # this stops and why it stops there.
            log.error("Ledger %s %s — moving it aside", self.path, inside)
            return self.set_aside(f"{self.path} {inside}")
        self.runs = list(runs)
        return self

    def _claim_quarantine(self) -> Path | None:
        """An unused name for the file about to be set aside, claimed atomically.

        Named for the MOMENT it was set aside, because when a file cannot be
        read the only thing that distinguishes one casualty from the next is
        when it happened. A second is not fine enough on its own: a cron run
        and a hand-fired re-run of the same night fail within the same second,
        so the name carries a counter as well.

        The counter is CLAIMED rather than checked. `exists()` and then rename
        is two operations with room for another run in between, and the rename
        would overwrite — which is the bug this replaces: the name used to be
        fixed, `Path.replace` silently overwrote it, and a year of quarantined
        outcomes was destroyed on the next night by a 35-byte corrupt file. Two
        unreadable ledgers in a row is not exotic — a SCHEMA_VERSION bump and a
        rollback does it in two runs. O_CREAT|O_EXCL fails rather than
        overwrites, so the placeholder it leaves is a name nothing else holds.

        None when no name could be claimed — an unwritable directory, or every
        name inside this second already taken. The caller reports that rather
        than pressing on and overwriting. See set_aside().
        """
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        for attempt in range(QUARANTINE_ATTEMPTS):
            suffix = "" if attempt == 0 else f"-{attempt}"
            spoiled = self.path.with_name(
                f"{self.path.name}.{stamp}{suffix}.{QUARANTINE_SUFFIX}")
            try:
                handle = os.open(spoiled, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                continue          # somebody else's casualty already has it
            except OSError as e:  # noqa: BLE001 — an unwritable directory
                log.error("Could not claim a quarantine name next to %s (%s)",
                          self.path, e)
                return None
            os.close(handle)
            return spoiled
        log.error("Every quarantine name next to %s is taken", self.path)
        return None

    def set_aside(self, why: str) -> "Ledger":
        """Keep the file this module could not read, out of the way of the one
        it is about to write. Best effort: an unwritable directory must not
        stop the run either, and the next write is what matters.

        Public because load() is not the only way a read can fail. src.pipeline
        catches anything load() itself did not — a bug in here, an error no
        version of this file has met — and has to reach this too: the run goes
        on, and write() then puts a one-run ledger where a year of outcomes
        used to be. Every path that gives up on reading the history keeps it,
        and keeps every EARLIER one it was already keeping.
        """
        spoiled = self._claim_quarantine()
        if spoiled is None:
            why += ("; no quarantine name could be claimed beside it, so this run "
                    "overwrites it")
            self.load_error = why
            return self
        try:
            # Onto the empty placeholder claimed a moment ago. replace()
            # overwrites whatever it lands on, which is what destroyed the
            # previous casualty; here what it lands on is a nothing this call
            # created for the purpose, so there is nothing to destroy.
            self.path.replace(spoiled)
        except OSError as e:  # noqa: BLE001
            spoiled.unlink(missing_ok=True)   # never leave the empty claim behind
            log.error("Could not move %s aside (%s); this run will overwrite it",
                      self.path, e)
            why += f"; it could not be moved aside ({e}) and this run overwrites it"
        else:
            log.error("The previous ledger is at %s — it was NOT overwritten", spoiled)
            why += f"; the previous file is at {spoiled}"
        self.load_error = why
        return self

    # -- the run that just happened ------------------------------------
    def add_run(self, run: dict, candidates: list[dict], gated: list[dict]) -> dict:
        """Record this run, and hand back the entry that was stored.

        Ordered by SESSION, not by arrival: backfilling an old session puts the
        run that just executed in the middle of the ledger rather than at its
        head, and anything reading runs[0] for "the run that just happened" is
        reading somebody else's run. That is why the entry is returned.

        Same (date, type) replaces rather than duplicates: a run repeated after
        a failure is the same session scanned twice, and two rows for it would
        double-count that session in every mean computed downstream. A backfill
        older than the MAX_RUNS the ledger keeps is dropped again immediately,
        which is what "the file keeps a year" means.

        The cost of that key, named because it is a real one: a re-run that
        scanned a DEGRADED or partial universe replaces a complete entry with
        a worse one, and a name in the first attempt and missing from the
        second loses its appearance — its streak resets, and its forward
        returns start again as pending. Double-counting a session is the worse
        failure of the two (it corrupts every published mean, silently and
        permanently, where this loses one night's rows visibly), so the key
        stays; a run that knows it scanned a partial universe is better fixed
        by not writing it than by keying around it.
        """
        self.latest = {"run": dict(run), "candidates": list(candidates),
                       "gated_out": list(gated)}
        entry = {
            "date": run["date"],
            "type": run["type"],
            "bursts": run["bursts"],
            "passed_gate": run["passed_gate"],
            "scored": run["scored"],
            "shortlist_size": run["shortlist_size"],
            "score_cap": run.get("score_cap"),
            "top_score": max((c["score"] for c in candidates if c["score"] is not None),
                             default=None),
            "fallbacks": sum(1 for c in candidates
                             if c["provenance"]["source"] != "claude"),
            "model": run.get("model"),
            "status": run.get("status", "ok"),
            "dry_run": bool(run.get("dry_run")),
            # What this run SCANNED, kept with the row so the record can tell
            # a `--tickers` smoke test from a scan of the universe. Without it
            # the four-name run README documents as a local check left a row
            # nothing downstream could distinguish from a real night: the next
            # real run read it as history, every name in it carried a streak
            # that started on a run that never scanned the universe, and its
            # scored rows counted as setups in the evidence. The row is still
            # written -- the test suite and tools/make_history.py drive the
            # pipeline through this same path, and a run that writes no
            # record could not be tested for what it records -- but it says
            # what it is, and README says how to put the file back.
            "universe": run.get("universe"),
            # The universe's own return from this session, filled by a later
            # run from the frames its scan read (fill_benchmarks). Pending
            # until then, and pending forever for a run whose universe the
            # later scans never fetched -- a --tickers run's, for one.
            "benchmark": empty_benchmark(),
            # And the liquidity floor it applied, in dollars: the one number
            # the open decision about widening the universe turns on, and the
            # one a row refused under it has to be read against.
            "liquidity": run.get("liquidity"),
            "candidates": [slim_row(c, scored=True) for c in candidates],
            "gated": [slim_row(g, scored=False) for g in gated],
        }
        # The rules that produced these rows, and ONLY when the run carried
        # them: without this block every mean computed across the record
        # averages whatever screeners it spans under one label (see
        # src.pipeline.rules_fingerprint()). Written as an absent key rather
        # than a null, because the contract distinguishes the two -- a run
        # from before the fingerprint existed carries no block, and null is a
        # shape no writer produces, which _malformed_rows() refuses. Writing
        # the key unconditionally made this module refuse the file it had
        # just written, on any run whose caller had no fingerprint.
        if isinstance(run.get("rules"), dict):
            entry["rules"] = dict(run["rules"])
        self.runs = [r for r in self.runs
                     if (r.get("date"), r.get("type")) != (entry["date"], entry["type"])]
        self.runs.insert(0, entry)
        self.runs.sort(key=lambda r: (str(r.get("date")), str(r.get("type"))), reverse=True)
        del self.runs[MAX_RUNS:]
        self._recompute_means()
        # A backfill older than everything the file keeps was dropped again by
        # the line above, so _recompute_means() never saw it — and the entry
        # this hands back still has to describe itself. Alone in the ledger,
        # every appearance in it starts its own setup.
        entry.setdefault("forward_returns",
                         mean_returns(entry["candidates"], scored_leads([entry])))
        return entry

    def _recompute_means(self) -> None:
        """Every run's published mean, from the rows the ledger now holds.

        Over ALL runs, not just the one that changed, because a run's mean
        depends on runs OTHER than itself: which of its rows start a setup is
        decided by the sessions around them, so adding a session — a backfill
        especially — can demote a row that used to lead. A stored mean that
        disagrees with the rows under it is the defect this module already
        refuses to ship in a streak, and it would be worse here, because a
        mean is what somebody reads to decide whether any of this works.
        """
        # scored_leads, not setup_leads: a pick whose setup was LED by an
        # earlier refusal -- the veto's common case -- is still this run's
        # pick, and keying on the setup's first appearance dropped it from the
        # run's own mean while the score and the outcome sat in the row.
        leads = scored_leads(self.runs)
        for run in self.runs:
            run["forward_returns"] = mean_returns(run.get("candidates", []), leads)

    # -- forward returns -----------------------------------------------
    def _fillable(self, through: date | None) -> list[dict]:
        """Rows that could still gain a horizon, newest FILL_WINDOW_RUNS runs."""
        limit = _as_date(through)
        out = []
        # The window is the newest runs BY SESSION, so a SCAN_SESSION_DATE
        # backfill of a session older than the ten newest landed outside it
        # -- on the run that scored it and on every run after -- and its rows
        # stayed pending forever, while README promised a backfill resolves
        # its own outcomes. The run just added is always in the window: it is
        # the one whose outcomes this run was started to collect.
        window = list(self.runs[:FILL_WINDOW_RUNS])
        if self.latest is not None:
            key = (self.latest["run"].get("date"), self.latest["run"].get("type"))
            for run in self.runs[FILL_WINDOW_RUNS:]:
                if (run.get("date"), run.get("type")) == key:
                    window.append(run)
        for run in window:
            for row in list(run.get("candidates", [])) + list(run.get("gated", [])):
                returns = row.get("forward_returns") or {}
                if (all(returns.get(f"d{h}") is not None for h in HORIZONS)
                        and all(_from_open(returns).get(f"d{h}") is not None for h in HORIZONS)):
                    continue
                burst = _as_date(row.get("date"))
                if burst is None or (limit is not None and burst >= limit):
                    continue  # the sessions after it have not happened yet
                out.append(row)
        return out

    def pending_tickers(self, through: date | None = None) -> list[str]:
        """Which symbols this run would have to fetch to fill anything in."""
        seen: dict[str, None] = {}
        for row in self._fillable(through):
            seen.setdefault(row["ticker"], None)
        return list(seen)

    def fill_forward_returns(self, frames: dict, through: date | None = None,
                             calendar: list[date] | None = None) -> int:
        """Fill every horizon these frames make knowable. Returns how many rows moved.

        `calendar` is the sessions the run knows happened (session_calendar()
        over every frame it fetched), so a hole in one name's frame leaves a
        horizon null rather than measuring it on the next bar the frame has.

        Idempotent: a row already carrying d1 keeps the value it was given,
        because the frame it came from and the frame here are the same
        arithmetic over the same feed, and rewriting it every night would turn
        one restated bar into a silently changing record.
        """
        moved = 0
        for row in self._fillable(through):
            frame = frames.get(row["ticker"])
            if frame is None:
                continue
            fresh = forward_returns(frame, row["date"], calendar)
            current = row.setdefault("forward_returns", empty_returns())
            # A row from before the open basis existed gains the block here,
            # pending, and fills it the same way: each key once, never
            # restated. A block that is present and not an object never
            # reaches this line -- _malformed_rows() refused the file.
            if not isinstance(current.get("from_open"), dict):
                current["from_open"] = {f"d{h}": None for h in HORIZONS}
            changed = False
            for horizon in HORIZONS:
                key = f"d{horizon}"
                if current.get(key) is None and fresh[key] is not None:
                    current[key] = fresh[key]
                    changed = True
                if (current["from_open"].get(key) is None
                        and fresh["from_open"][key] is not None):
                    current["from_open"][key] = fresh["from_open"][key]
                    changed = True
            if changed:
                current["as_of"] = fresh["as_of"]
                moved += 1
        if moved:
            self._recompute_means()
            self._copy_returns_into_latest()
        return moved

    def fill_benchmarks(self, frames: dict, through: date | None = None,
                        universe: dict | None = None,
                        calendar: list[date] | None = None) -> int:
        """Fill the universe benchmark of every run in the fill window whose
        horizons the frames make knowable, from the universe `frames` came
        from. Returns how many runs moved.

        `universe` IS THE QUESTION, not decoration. The fill used to take
        whatever the caller had scanned and measure it against every earlier
        run, so the documented `--tickers BURST` smoke test filled the
        previous night's benchmark from one frame -- and that night had
        SCORED BURST, so the alternative the north star is measured against
        became the pick itself: d1 12.0 over n1 1, where the honest
        equal-weight move over that night's five names was +2.45%. Never
        corrected either, since a measured horizon keeps its value. Two
        rules close it: a caller with no universe to offer (a --tickers run)
        passes None and fills nothing, and a run is filled only from a scan
        of the universe IT scanned, compared on the label the run entry
        already carries. The block is stamped with that universe, so a
        reader can see which basket the number is over rather than infer it.

        Same window and same idempotence as fill_forward_returns(): a horizon
        already measured keeps its value, because two nights' frames are the
        same feed's arithmetic over the same bars. The `n` per horizon is
        how many of tonight's frames carried that run's session -- the
        universe as tonight's scan holds it, so a name added to or dropped
        from the symbol file since that night is counted as tonight has it,
        and the count is what says how many that was.

        Every name under the run's OWN liquidity floor that session -- the
        bar rule 6 set that night, kept in run.liquidity -- is left out of
        the mean and counted in `below_floor`, and the floor is stamped on
        the block; a run recorded before the floor existed is benchmarked
        over every name that traded and stamped null, which is the truth
        about it. See universe_returns().
        """
        # No universe, nothing to benchmark WITH. A --tickers run scanned a
        # handful of names it was handed, which is not a market.
        if not isinstance(universe, dict) or not universe.get("label"):
            return 0
        limit = _as_date(through)
        moved = 0
        window = list(self.runs[:FILL_WINDOW_RUNS])
        if self.latest is not None:
            key = (self.latest["run"].get("date"), self.latest["run"].get("type"))
            for run in self.runs[FILL_WINDOW_RUNS:]:
                if (run.get("date"), run.get("type")) == key:
                    window.append(run)
        for run in window:
            # Only from a scan of the universe this run itself scanned. A run
            # written before universes were recorded cannot be matched, so it
            # is left pending rather than filled from an assumption.
            scanned = run.get("universe")
            if not isinstance(scanned, dict) or scanned.get("label") != universe["label"]:
                continue
            current = run.get("benchmark")
            if not isinstance(current, dict):
                current = run["benchmark"] = empty_benchmark()
            if not isinstance(current.get("from_open"), dict):
                current["from_open"] = empty_benchmark()["from_open"]
            # A block from before round 9 gains the two keys, pending, so
            # every block on disk is one shape; see the stamp below for when
            # they are filled.
            current.setdefault("liquidity_floor", None)
            current.setdefault("below_floor", 0)
            if all(current.get(f"d{h}") is not None for h in HORIZONS) and \
                    all(current["from_open"].get(f"d{h}") is not None for h in HORIZONS):
                continue
            session = _as_date(run.get("date"))
            if session is None or (limit is not None and session >= limit) or not frames:
                continue
            # ONE BLOCK, ONE POPULATION. A block that already holds a
            # horizon was measured over some set of names, and the horizons
            # still open are measured over the same set: the floor it was
            # stamped with, which for a block from before round 9 is none.
            # Applying tonight's floor to d5 under a d1 that averaged every
            # name would stamp the whole block "floored" over a mean that
            # was not -- the round-9 audit's R9-C, driven through the fill.
            started = any(_is_number(current.get(f"d{h}")) for h in HORIZONS) or \
                any(_is_number(current["from_open"].get(f"d{h}")) for h in HORIZONS)
            floor = (_num(current.get("liquidity_floor")) if started else _floor_of(run))
            fresh = universe_returns(frames, session, floor=floor, calendar=calendar)
            changed = False
            for horizon in HORIZONS:
                key, count = f"d{horizon}", f"n{horizon}"
                if current.get(key) is None and fresh[key] is not None:
                    current[key], current[count] = fresh[key], fresh[count]
                    changed = True
                if current["from_open"].get(key) is None and fresh["from_open"][key] is not None:
                    current["from_open"][key] = fresh["from_open"][key]
                    current["from_open"][count] = fresh["from_open"][count]
                    changed = True
            if changed:
                # Stamped ONCE, by the fill that first measures the block:
                # the population is fixed then (see `started` above), and a
                # later fill of the horizons still open may hold a slightly
                # different frame set -- a name dropped from the symbol file
                # since, a batch that failed tonight -- whose count would
                # contradict the n the first fill froze. The round-9 audit
                # published n1 3 beside below_floor 1 that way, for a session
                # on which five names traded and two were under the floor.
                if not started:
                    current["universe"] = dict(universe)
                    current["liquidity_floor"] = fresh["liquidity_floor"]
                    current["below_floor"] = fresh["below_floor"]
                moved += 1
        return moved

    def _copy_returns_into_latest(self) -> None:
        """Keep data.json's candidate rows agreeing with the ledger's.

        They differ only when a run is scanning an OLD session — a backfill,
        `SCAN_SESSION_DATE=...` — where the sessions after the burst have
        already happened and the returns resolve in the same run that scored
        them. That is the only way the dashboard's score-against-outcome plot
        can carry a point, so it is worth the copy.

        Found by (date, type), NOT by position. `runs` is ordered by session,
        so backfilling a session older than one already recorded puts the run
        that just executed somewhere in the middle — and reading the head
        there published a file whose candidates all said "pending" while the
        ledger beside it held their returns.
        """
        if not self.latest:
            return
        key = (self.latest["run"]["date"], self.latest["run"]["type"])
        head = next((r for r in self.runs if (r.get("date"), r.get("type")) == key), None)
        if head is None:
            return
        for slim_rows, full_rows in ((head.get("candidates", []), self.latest["candidates"]),
                                     (head.get("gated", []), self.latest["gated_out"])):
            by_ticker = {row["ticker"]: row for row in slim_rows}
            for full in full_rows:
                slim_row = by_ticker.get(full["ticker"])
                if slim_row is not None and "forward_returns" in full:
                    full["forward_returns"] = dict(slim_row["forward_returns"])

    # -- output ---------------------------------------------------------
    def dashboard(self, headline: dict | None = None) -> dict:
        """docs/data.json: the newest run, plus the history's headline numbers."""
        if self.latest is None:
            raise ValueError("no run has been added, so there is nothing to publish")
        return {
            "schema_version": SCHEMA_VERSION,
            "app": "SpicyStock",
            "generated": _now_iso(),
            "_contract": {
                "about": CONTRACT_ABOUT,
                "documented_in": "README.md, 'The data contract'",
                "invariants": list(CONTRACT_INVARIANTS),
            },
            # `headline` is the top block to publish INSTEAD of the run just
            # added: the previous file's own run, candidates and gated_out,
            # handed back by publish() when the run just added is a BACKFILL
            # of an older session. Without it a SCAN_SESSION_DATE run of last
            # week rewrote the headline to last week while `runs` two lines
            # down still listed last night, and the next morning announced
            # that nothing had published for three sessions over a file that
            # named the newer run itself. The record gains the backfill; the
            # page and the morning keep the newest session.
            "run": (headline or self.latest)["run"],
            "candidates": (headline or self.latest)["candidates"],
            "gated_out": (headline or self.latest)["gated_out"],
            "runs": [{k: v for k, v in run.items()
                      if k not in ("candidates", "gated")} for run in self.runs],
            # Step 11. The answers to the questions the page exists to ask,
            # computed here rather than in the browser -- see evidence(). This
            # is the whole ledger's view, not this run's: `runs` above already
            # carried a cross-run history of per-run means, so a block spanning
            # the record is not a new kind of thing in this file.
            "evidence": evidence(self.runs),
        }

    def write(self, headline: dict | None = None) -> dict:
        """Write both files. Returns {"data": path, "ledger": path}.

        `allow_nan=False` on purpose: json.dump's default writes NaN and
        Infinity as bare tokens, which is not JSON, and the dashboard's fetch
        would fail on the whole file rather than show one gap. _num() should
        have caught it long before here; this is the check that the check ran.
        """
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        ledger = {"schema_version": SCHEMA_VERSION, "app": "SpicyStock",
                  "generated": _now_iso(), "runs": self.runs}
        _write_json(self.path, ledger)
        _write_json(self.data_path, self.dashboard(headline))
        return {"data": self.data_path, "ledger": self.path}


def _floor_of(run: dict) -> float | None:
    """The liquidity floor a run entry recorded, in dollars, or None for a
    run that recorded none. Defensive about the block's shape rather than
    trusting it: the snapshot check refuses a malformed run.liquidity and
    the ledger's does not, and a run benchmarked over every name is a
    truthful answer for a block this cannot read, where a crash after the
    scan and every Claude call is not."""
    block = run.get("liquidity")
    floor = block.get("floor") if isinstance(block, dict) else None
    # Positive, or none: a floor is a percentile of dollar volumes, and a
    # zero or negative one is a shape no writer produces -- which the load
    # check refuses on the benchmark, so stamping it here would make the
    # file it was written into unreadable the night after.
    return float(floor) if _is_number(floor) and math.isfinite(floor) and floor > 0 else None


def _quarantine_key(path: Path) -> tuple[str, int]:
    """Sort casualties by WHEN they were set aside, which their names encode.

    Sorting the names as strings puts the first casualty of a second last:
    `-` (0x2d) sorts before `.` (0x2e), so `ledger.json.<stamp>-1.unreadable`
    lands ahead of the unnumbered `ledger.json.<stamp>.unreadable` it followed,
    and `-10` lands ahead of `-2`. Twelve casualties inside one second came
    back c1, c10, c11, c2 … c9, c0 out of a function that promised oldest
    first. The stamp and the counter are the two things the name carries, so
    they are what it sorts on — the counter as a number.

    The pre-stamp name (no stamp, no counter) yields ("", 0) and sorts first,
    which is where it belongs: it can only have been written by the code that
    came before the stamp existed.
    """
    middle = path.name[len(LEDGER_NAME) + 1:-(len(QUARANTINE_SUFFIX) + 1)]
    stamp, _, counter = middle.partition("-")
    return stamp, int(counter) if counter.isdigit() else 0


def quarantined(docs_dir: Path | str = DOCS_DIR) -> list[Path]:
    """Every ledger set_aside() has kept under `docs_dir`, oldest first.

    The quarantine name carries the second it was written, so there is no
    single path to look at any more — which is the point, and why this exists:
    a caller that hard-codes one name is a caller that can only ever see the
    newest casualty, and the older ones are exactly what the fixed name used
    to destroy.

    Ordered by _quarantine_key rather than by name, because the two disagree.

    The PRE-STAMP name is looked for as well. `ledger.json.*.unreadable` needs
    two dots and so does not match the `ledger.json.unreadable` the fixed-name
    version left behind: such a file is never destroyed, and was invisible to
    the one function whose whole job is finding casualties.
    """
    room = Path(docs_dir)
    found = set(room.glob(f"{LEDGER_NAME}.*.{QUARANTINE_SUFFIX}"))
    legacy = room / f"{LEDGER_NAME}.{QUARANTINE_SUFFIX}"
    if legacy.exists():
        found.add(legacy)
    return sorted(found, key=_quarantine_key)


def _write_json(path: Path, payload: dict) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False)
    path.write_text(text + "\n", encoding="utf-8")


#: The keys a candidate row must carry for the morning follow-through to be
#: able to present it.
#:
#: NOT every key candidate_record() writes, which is what the first version of
#: this required. That version made the first morning after ANY schema-additive
#: deploy refuse a perfectly good snapshot: docs/data.json still holds
#: YESTERDAY's run, written by yesterday's code, so a key added to the writer
#: is missing from the file the next morning reads -- exactly once, by
#: construction, on a run that was fine. The screener would have degraded
#: itself on every future schema change.
#:
#: Determined by EXPERIMENT, not by reading src.emailer. Reading it is what
#: made the writer's whole key list tempting in the first place: a
#: hand-maintained list of "what the email indexes" is a second copy of the
#: emailer, and this project has already shipped two copies of one checklist
#: that disagreed. tests/test_ledger.py's
#: test_the_required_keys_are_the_ones_the_run_really_needs drops each key in
#: turn and runs the real morning path and the real email renderer, so this set
#: is checked against behaviour on every suite run: a key that becomes
#: load-bearing later fails the build rather than the 8:30 email.
SNAPSHOT_ROW_KEYS = frozenset({
    "ticker", "close", "gain_pct", "volume_ratio", "lynch",
    "score", "verdict", "reason", "key_risk",
})


def snapshot_problem(data: dict) -> str | None:
    """What is wrong with the SHAPE of a snapshot's rows, or None if nothing is.

    The fifth instance of one defect class, and the same line _malformed_rows()
    draws for the ledger: read_snapshot() checked that `candidates` was a list
    and stopped, so `"candidates": ["AAPL"]` was handed to the morning run as a
    watchlist and took it down with AttributeError -- exit 1 and a FAILED
    notice, where the design says exit 2 and "there is nothing to follow
    through on". Not a data-loss path (the morning run writes nothing; verified
    by hashing docs/ across every shape below), but the wrong exit code and the
    wrong email, on the pass whose only job is to say what state the record is
    in.

    The list of shapes here is what a sweep of 37 malformed snapshots through
    the real follow-through and the real email renderer crashed on -- twenty of
    them, in three places: a row that is not an object; an object missing a key
    the email indexes (`ticker`, `close`, `score`, `verdict`...), or carrying a
    `ticker` that is not a string (the subject line joins them); and a nested
    structure of the wrong shape (`lynch_detail` rows that are not objects, a
    `streak` that is a string, `run.status` or `run.scored_by` that is not what
    publish() writes). Everything below refuses exactly those, by naming the
    row and the field, so the morning email can say which.

    SHAPE, NOT CONTENT, as in the ledger: a score of "9" or a date nobody can
    parse is a row this pass can still hold up and print. The one exception a
    reader might expect -- a `streak.day` that is not a number -- is content,
    and src.pipeline guards its single comparison against it instead.
    """
    run = data.get("run")
    # The two counts the morning email prints as facts about the session, and
    # the only inputs to its empty-table sentence. Absent is a record that
    # says nothing about them, which the funnel prints as "not recorded" and
    # the cell defers on; present, they are counts, and a bool, a string or a
    # negative is a file no writer produces -- so the run exits 2 naming the
    # field instead of mailing "4% bursts that session: -3" beside a sentence
    # about what the market held. The class this function exists for, on the
    # one field the round that added the sentence did not widen it to.
    for field_name in ("bursts", "passed_gate"):
        if field_name in run:
            value = run[field_name]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                return (f"run.{field_name} is {value!r}, not the count publish() writes")
    for field_name, wanted in (("status", str), ("scored_by", dict), ("errors", list)):
        value = run.get(field_name)
        if field_name not in run:
            # ABSENT IS FINE, NULL IS NOT, and the difference is not pedantry:
            # follow_through() reads the status as `.get("status", "ok")`, and
            # a default only applies to a MISSING key. A key present and null
            # therefore reaches `.upper()` as None and takes the run down --
            # exit 1 and a FAILED notice where the design says exit 2. The
            # first version of this check exempted null explicitly and that is
            # exactly the value that crashes.
            continue
        if not isinstance(value, wanted) or isinstance(value, bool):
            return (f"run.{field_name} is {type(value).__name__}, not the "
                    f"{wanted.__name__} publish() writes")
    # run.liquidity, under the row rule stated above: absent is a snapshot
    # from before the block existed and is fine; present in a shape no
    # writer produces is refused, even though every reader of it is
    # type-guarded and the morning would have survived. The audit that found
    # it tolerated drove fourteen shapes through the real morning path and
    # none crashed -- the point is the rule, not a crash.
    liquidity = run.get("liquidity", None) if "liquidity" in run else "absent"
    if liquidity != "absent":
        if not isinstance(liquidity, dict):
            return f"run.liquidity is {type(liquidity).__name__}, not the object publish() writes"
        pctile, floor, refused = liquidity.get("pctile"), liquidity.get("floor"), liquidity.get("refused")
        if isinstance(pctile, bool) or not isinstance(pctile, (int, float)):
            return f"run.liquidity.pctile is {type(pctile).__name__}, not a number"
        if floor is not None and (isinstance(floor, bool) or not isinstance(floor, (int, float))):
            return f"run.liquidity.floor is {type(floor).__name__}, not a number or null"
        if isinstance(refused, bool) or not isinstance(refused, int):
            return f"run.liquidity.refused is {type(refused).__name__}, not a count"
    # One level into scored_by, because the email does ARITHMETIC on these two.
    # It does not crash on strings: "5" + "1" is "51", so the provenance line
    # rendered "Scored by Claude: 5 of 51" -- a fabricated count, which is
    # worse than a crash because nothing anywhere says it is wrong.
    # The names that stopped printing. Absent is a snapshot from before the
    # block existed and loads clean; present, it is the object publish()
    # writes, one level in -- the email joins the tickers and the page prints
    # sessions_behind, and a string where a count belongs is the class this
    # function exists to refuse before a later consumer meets it. `last` and
    # `sessions_behind` are BOTH null for a name the feed returned no bar for
    # at all (the writer produces no other null), and a number where the
    # date belongs is a shape no writer produces.
    if "stopped_printing" in run:
        block = run["stopped_printing"]
        count = block.get("count") if isinstance(block, dict) else None
        after = block.get("after_sessions") if isinstance(block, dict) else None
        if (not isinstance(block, dict) or not isinstance(block.get("names"), list)
                or isinstance(count, bool) or not isinstance(count, int) or count < 0
                # `after_sessions` is the number the whole sentence turns on --
                # "no bar for more than 5 sessions" -- and it was checked
                # nowhere while `count` was: with the key deleted the email
                # read "for more than  sessions" and the page "for more than
                # undefined sessions", and nothing said so. The block is one
                # round old, so "absent is what an older writer produced" does
                # not apply to it: every writer emits both.
                or isinstance(after, bool) or not isinstance(after, int) or after < 0):
            return ("run.stopped_printing is not the "
                    "{after_sessions, count, names} object publish() writes")
        for position, name in enumerate(block["names"], start=1):
            behind = name.get("sessions_behind") if isinstance(name, dict) else None
            last = name.get("last") if isinstance(name, dict) else None
            if (not isinstance(name, dict) or not isinstance(name.get("ticker"), str)
                    or isinstance(behind, bool)
                    or not (behind is None or isinstance(behind, int))
                    or not (last is None or isinstance(last, str))):
                return (f"run.stopped_printing.names[{position}] is not "
                        "{ticker, last, sessions_behind}")
    for name, count in (run.get("scored_by") or {}).items():
        if count is not None and (isinstance(count, bool) or not isinstance(count, (int, float))):
            return (f"run.scored_by.{name} is {type(count).__name__}, not a number, "
                    "and the email adds these together")
    for position, row in enumerate(data.get("candidates") or [], start=1):
        if not isinstance(row, dict):
            return f"candidate row {position} is a JSON {type(row).__name__}, not a row"
        missing = sorted(SNAPSHOT_ROW_KEYS - set(row))
        if missing:
            return (f"candidate row {position} ({row.get('ticker')!r}) is missing "
                    f"{', '.join(missing)}")
        if not isinstance(row["ticker"], str):
            return (f"candidate row {position} has a {type(row['ticker']).__name__} "
                    "where its ticker should be")
        # A MISSING KEY AND A WRONG-TYPED ONE ARE DIFFERENT QUESTIONS, and the
        # two halves of this function answer them differently on purpose.
        # A key that is absent is what an OLDER version of this pipeline
        # legitimately wrote, and the morning after a deploy reads exactly
        # that -- so absence is tolerated unless the run genuinely needs it
        # (see SNAPSHOT_ROW_KEYS). A key present with the wrong TYPE is not
        # something any version of the writer produces: it means a hand edit,
        # a truncation, or another tool, and that document did not come out of
        # a run. So the checks below refuse it even where the run would have
        # survived -- three of the four fields here no longer crash anything,
        # because streak_day() and the guards around them were centralised,
        # and they are still refused.
        #
        # .get() from here down, not [...]: everything below is OPTIONAL now,
        # and a row legitimately missing one (an older run's snapshot, read the
        # morning after a deploy) must reach the reader rather than a KeyError
        # inside the check that exists to prevent one.
        detail = row.get("lynch_detail")
        if detail is not None and (not isinstance(detail, list)
                                   or any(not isinstance(check, dict) for check in detail)):
            return (f"candidate row {position} ({row['ticker']}) has a lynch_detail "
                    "that is not a list of checks")
        for field_name in ("streak", "provenance", "forward_returns", "context"):
            value = row.get(field_name)
            if value is not None and not isinstance(value, dict):
                return (f"candidate row {position} ({row['ticker']}) has a "
                        f"{type(value).__name__} where its {field_name} object should be")
        # AND TWO FIELDS INSIDE THE STREAK BLOCK, because the email indexes
        # into both. `unknown_reason` is a dict KEY there (LAST_OUTCOME-style
        # lookup), so an unhashable one is a TypeError rather than a miss; and
        # `seen_before` is compared against 0, which a string or a list cannot
        # be. The seen_before comparison sits behind a short-circuit that only
        # opens when `day` is null -- so it needs BOTH, which is why a sweep
        # that varied one field at a time reported it safe.
        streak = row.get("streak") or {}
        reason = streak.get("unknown_reason")
        if reason is not None and not isinstance(reason, str):
            return (f"candidate row {position} ({row['ticker']}) has a "
                    f"{type(reason).__name__} where its streak.unknown_reason should be")
        seen = streak.get("seen_before")
        if seen is not None and (isinstance(seen, bool) or not isinstance(seen, (int, float))):
            return (f"candidate row {position} ({row['ticker']}) has a "
                    f"{type(seen).__name__} where its streak.seen_before count should be")
        # AND THE TWO BESIDE THEM, which the sweep that wrote the block above
        # stopped one field short of. `last_outcome` is the OTHER dict-key
        # lookup in the email (LAST_OUTCOME.get), so an unhashable one is the
        # same TypeError one field away from a comment naming that exact
        # mechanism; an audit found it. `history_sessions` does not crash --
        # it reaches _plural() and renders "[1, 2] sessions in the record",
        # which is the shape this project has already called worse than a
        # crash, because nothing about it says it is wrong.
        #
        # That is the whole streak block now: every remaining field is
        # interpolated into a sentence, where a wrong type is visibly wrong
        # rather than silently plausible.
        outcome = streak.get("last_outcome")
        if outcome is not None and not isinstance(outcome, str):
            return (f"candidate row {position} ({row['ticker']}) has a "
                    f"{type(outcome).__name__} where its streak.last_outcome should be")
        held = streak.get("history_sessions")
        if held is not None and (isinstance(held, bool) or not isinstance(held, (int, float))):
            return (f"candidate row {position} ({row['ticker']}) has a "
                    f"{type(held).__name__} where its streak.history_sessions count should be")
    return None


def read_snapshot(docs_dir: Path | str = DOCS_DIR) -> tuple[dict | None, str | None]:
    """The last run's docs/data.json, or (None, why not). Never raises.

    Step 10's morning mode is a follow-through pass over the run that already
    happened, so the snapshot IS its input. It is read here rather than in
    src.pipeline because this module is the one that writes the file and knows
    what a valid one looks like — including the case that matters most:

    A FIXTURE IS NOT A RUN. The docs/data.json committed to this repo is
    hand-authored (tools/make_fixture.py) and says so in run.fixture. Mailing
    its rows as a morning watchlist would put invented tickers in front of a
    reader as tonight's judgements, which is the worst failure this pipeline
    could produce and would look exactly like a working one. It is refused by
    name, with the reason, rather than silently.
    """
    path = Path(docs_dir) / DATA_NAME
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return None, (f"{path} does not exist — no run has published a snapshot here yet")
    except Exception as e:  # noqa: BLE001 — "never raises" means never; see below
        # Named failures only (OSError, ValueError) held that promise for the
        # failures somebody had thought of. json.loads raises RecursionError on
        # a deeply nested document, which is neither, so a morning run against
        # a data.json of "[" * 100000 exited FAILED where the design says
        # DEGRADED and "there is nothing to follow through on". Ledger.load()
        # was widened to the same catch-all for the same reason; this is its
        # sibling and was left behind.
        return None, f"{path} could not be read ({type(e).__name__}: {e})"
    version = data.get("schema_version") if isinstance(data, dict) else None
    if version != SCHEMA_VERSION:
        return None, f"{path} is schema_version {version!r}, not {SCHEMA_VERSION}"
    run = data.get("run")
    if not isinstance(run, dict) or not isinstance(data.get("candidates"), list):
        return None, f"{path} carries no run to follow through on"
    if run.get("fixture"):
        return None, (f"{path} is the hand-authored fixture (run.fixture is true), not a "
                      "run — its rows are invented and must never be mailed as a watchlist")
    problem = snapshot_problem(data)
    if problem:
        return None, (f"{path} did not come out of a run as it stands: {problem}. Its rows "
                      "cannot be re-presented as a watchlist")
    return data, None
