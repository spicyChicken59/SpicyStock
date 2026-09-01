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
the close 1, 3 and 5 SESSIONS later, positionally within the frame — sessions,
not calendar days, so a holiday cannot silently shift a horizon.

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
from datetime import date, datetime, timezone
from pathlib import Path

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

#: The invariants, in the file rather than only in the docs. tools/make_fixture.py
#: imports this list rather than holding a second copy, so the hand-authored
#: fixture and the pipeline's real output can never describe different contracts
#: — the same reason that generator imports src.lynch's thresholds.
CONTRACT_INVARIANTS = [
    "candidates holds EVERY scored candidate, ranked by score descending, and is never truncated: len(candidates) == run.scored. The top run.shortlist_size of them are the shortlist that went out by email.",
    "run.scored + len(gated_out) == run.bursts. Nothing a scan found may vanish without appearing in one of the two lists.",
    "Every candidate carries provenance.source: 'claude' when the model actually returned a score, 'fallback' when the offline checklist produced it. A fallback is never labelled claude.",
    "provenance.chart_seen is true only when the scoring model actually received the chart image.",
    "forward_returns and runs[].forward_returns are null until the sessions exist. Absent is null, never 0 and never a string.",
    "chart is a path relative to docs/, or null when the render failed. The file may legitimately not exist yet.",
    "Every burst carries lynch_detail — one row per check, with the value that was measured — whether it was scored or gated out. The dashboard's per-check pass rates are computed over all of them; without the gated ones the rates only describe the candidates that already passed.",
    "Every burst carries streak — day (1 for a setup starting today), first_seen, last_seen, last_score, last_verdict, seen_before — or null when the run could not read its own history. day is 1 exactly when first_seen is the burst's own session, and last_seen is null exactly when seen_before is 0. A null streak means unknown; it never collapses to a confident day 1.",
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
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return pd.Timestamp(value).date()
    except Exception:  # noqa: BLE001 — anything unparseable is simply not a date
        return None


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
                }
    return {ticker: [by_session[k] for k in sorted(by_session)]
            for ticker, by_session in seen.items()}


def streak(history: list[dict], session) -> dict:
    """Where a burst on `session` sits in this name's run of appearances.

      day          this appearance's place in the current setup, counting only
                   the sessions it actually burst on. `day: 3` is the third
                   such session, NOT the third calendar session since the
                   setup began — a gap cannot inflate it.
      first_seen   the session the current setup started on. Equals the
                   burst's own session exactly when day is 1.
      last_seen    the most recent EARLIER appearance anywhere in the ledger,
                   or null for a name it has never carried. Deliberately not
                   restricted to the current setup: "seen three weeks ago,
                   day 1 today" is a true and useful pair of facts.
      last_score   what that earlier appearance was scored, and its verdict,
                   or null when it was a burst the gate rejected. They
                   describe the appearance `last_seen` names and no other.
      seen_before  how many earlier sessions this ticker burst on, in the
                   runs the ledger still keeps. "Never seen before" therefore
                   means "not in the last MAX_RUNS runs", not "not ever".

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
    return {
        "day": day,
        "first_seen": iso_date(first),
        "last_seen": iso_date(last["date"]) if last else None,
        "last_score": last["score"] if last else None,
        "last_verdict": last["verdict"] if last else None,
        "seen_before": len(prior),
    }


def streaks(runs: list[dict], tickers, session) -> dict[str, dict]:
    """One streak block per ticker, against the history in `runs`.

    An empty ledger is a fine answer — every name is on day 1 and the record
    says so. An UNREADABLE ledger is not: see Ledger.load_error and the null
    `streak` src.pipeline publishes for it, because "we have never seen this
    name" and "we could not read the file that would know" are different
    sentences and only one of them is a claim about the market.
    """
    index = appearance_index(runs)
    return {ticker: streak(index.get(ticker, []), session) for ticker in tickers}


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

    `streak_block` is None when this run could not read its history — see
    streaks(). Null there means "unknown", the same way every other number in
    this file means it; it never collapses to a confident day 1.
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


def gated_record(cand, lynch_result: dict, reason: str,
                 streak_block: dict | None = None) -> dict:
    """One burst that was never scored, and why.

    Carries the full checklist for the same reason the scored rows do: a
    per-check pass rate computed over the survivors alone is survivorship bias
    with a percentage sign, since the names a check rejected are exactly the
    ones missing from it.
    """
    return {
        "ticker": cand.ticker,
        "date": iso_date(cand.date),
        "close": _num(cand.close),
        "gain_pct": _num(cand.gain_pct),
        "volume": _num(getattr(cand, "volume", None)),
        "volume_ratio": _num(cand.volume_ratio),
        "lynch": lynch_result["summary"],
        "lynch_passes": _num(lynch_result["passes"]),
        "lynch_total": _num(lynch_result["total"]),
        "lynch_detail": check_rows(lynch_result),
        "streak": dict(streak_block) if streak_block else None,
        "reason": reason,
    }


# ---------------------------------------------------------- ledger rows --

def empty_returns() -> dict:
    """Pending, spelled the one way the contract allows."""
    out = {f"d{h}": None for h in HORIZONS}
    out["as_of"] = None
    return out


def _slim(row: dict, lynch_result: dict | None = None, *, scored: bool) -> dict:
    """A dashboard row reduced to what a backtest needs, and no more."""
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

def forward_returns(df: pd.DataFrame | None, burst_date) -> dict:
    """d1/d3/d5 for one candidate, measured inside one frame.

    Returns the pending shape when the frame does not carry the burst session
    at all — a name that stopped trading, or a symbol the feed no longer
    knows. A missing measurement is null; it is never zero, and never a guess
    taken from the nearest bar, which would silently move the horizon.
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

    measured_at = None
    for horizon in HORIZONS:
        position = start + horizon
        if position >= len(closes):
            continue
        later = float(closes[position])
        if not math.isfinite(later):
            continue
        out[f"d{horizon}"] = _num((later / base - 1) * 100, 2)
        measured_at = sessions[position]
    out["as_of"] = iso_date(measured_at)
    return out


def mean_returns(rows: list[dict]) -> dict:
    """The run's mean forward return per horizon, and how many names are behind it.

    A horizon nobody has a value for is null rather than 0.0: the dashboard
    weights these by `n` across sessions, and a zero would be averaged in as a
    flat session that never happened.
    """
    out: dict = {}
    for horizon in HORIZONS:
        key = f"d{horizon}"
        values = [row["forward_returns"][key] for row in rows
                  if row.get("forward_returns", {}).get(key) is not None]
        out[key] = round(sum(values) / len(values), 2) if values else None
    out["n"] = sum(1 for row in rows
                   if any(row.get("forward_returns", {}).get(f"d{h}") is not None
                          for h in HORIZONS))
    return out


# -------------------------------------------------------------- the file --

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
        if raw.get("schema_version") != SCHEMA_VERSION:
            log.error("Ledger %s is schema_version %r, not %d — moving it aside "
                      "rather than merging into it",
                      self.path, raw.get("schema_version"), SCHEMA_VERSION)
            return self.set_aside(
                f"{self.path} is schema_version {raw.get('schema_version')!r}, "
                f"not {SCHEMA_VERSION}")
        runs = raw.get("runs")
        self.runs = [r for r in runs if isinstance(r, dict)] if isinstance(runs, list) else []
        return self

    def set_aside(self, why: str) -> "Ledger":
        """Keep the file this module could not read, out of the way of the one
        it is about to write. Best effort: an unwritable directory must not
        stop the run either, and the next write is what matters.

        Public because load() is not the only way a read can fail. src.pipeline
        catches anything load() itself did not — a bug in here, an error no
        version of this file has met — and has to reach this too: the run goes
        on, and write() then puts a one-run ledger where a year of outcomes
        used to be. Every path that gives up on reading the history keeps it.
        """
        spoiled = self.path.with_name(self.path.name + ".unreadable")
        try:
            self.path.replace(spoiled)
            log.error("The previous ledger is at %s — it was NOT overwritten", spoiled)
            why += f"; the previous file is at {spoiled}"
        except OSError as e:  # noqa: BLE001
            log.error("Could not move %s aside (%s); this run will overwrite it",
                      self.path, e)
            why += f"; it could not be moved aside ({e}) and this run overwrites it"
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
            "candidates": [_slim(c, scored=True) for c in candidates],
            "gated": [_slim(g, scored=False) for g in gated],
        }
        entry["forward_returns"] = mean_returns(entry["candidates"])
        self.runs = [r for r in self.runs
                     if (r.get("date"), r.get("type")) != (entry["date"], entry["type"])]
        self.runs.insert(0, entry)
        self.runs.sort(key=lambda r: (str(r.get("date")), str(r.get("type"))), reverse=True)
        del self.runs[MAX_RUNS:]
        return entry

    # -- forward returns -----------------------------------------------
    def _fillable(self, through: date | None) -> list[dict]:
        """Rows that could still gain a horizon, newest FILL_WINDOW_RUNS runs."""
        limit = _as_date(through)
        out = []
        for run in self.runs[:FILL_WINDOW_RUNS]:
            for row in list(run.get("candidates", [])) + list(run.get("gated", [])):
                returns = row.get("forward_returns") or {}
                if all(returns.get(f"d{h}") is not None for h in HORIZONS):
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

    def fill_forward_returns(self, frames: dict, through: date | None = None) -> int:
        """Fill every horizon these frames make knowable. Returns how many rows moved.

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
            fresh = forward_returns(frame, row["date"])
            current = row.setdefault("forward_returns", empty_returns())
            changed = False
            for horizon in HORIZONS:
                key = f"d{horizon}"
                if current.get(key) is None and fresh[key] is not None:
                    current[key] = fresh[key]
                    changed = True
            if changed:
                current["as_of"] = fresh["as_of"]
                moved += 1
        if moved:
            for run in self.runs[:FILL_WINDOW_RUNS]:
                run["forward_returns"] = mean_returns(run.get("candidates", []))
            self._copy_returns_into_latest()
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
    def dashboard(self) -> dict:
        """docs/data.json: the newest run, plus the history's headline numbers."""
        if self.latest is None:
            raise ValueError("no run has been added, so there is nothing to publish")
        return {
            "schema_version": SCHEMA_VERSION,
            "app": "SpicyStock",
            "generated": _now_iso(),
            "_contract": {
                "about": CONTRACT_ABOUT,
                "documented_in": "README.md, 'The dashboard contract'",
                "invariants": list(CONTRACT_INVARIANTS),
            },
            "run": self.latest["run"],
            "candidates": self.latest["candidates"],
            "gated_out": self.latest["gated_out"],
            "runs": [{k: v for k, v in run.items()
                      if k not in ("candidates", "gated")} for run in self.runs],
        }

    def write(self) -> dict:
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
        _write_json(self.data_path, self.dashboard())
        return {"data": self.data_path, "ledger": self.path}


def _write_json(path: Path, payload: dict) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False)
    path.write_text(text + "\n", encoding="utf-8")


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
    except (OSError, ValueError) as e:
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
    return data, None
