"""
Orchestrator — ties all layers together. Two modes:

  evening : DISCOVERY. Scan the session that closed today → candidates to
            watch TOMORROW. Everything downstream — charts, Claude, the
            archive, the ledger — belongs to this mode.
  morning : FOLLOW-THROUGH. No scan. Re-present the last evening run's
            candidates before today's open, with what the record says about
            each one, and cost nothing to do it.

Usage:  python -m src.pipeline morning|evening [--dry-run] [--tickers AAPL,MSFT]

THE MODE IS A PROMISE ABOUT THE CLOCK (step 10)
-----------------------------------------------
`run_type` used to change four cosmetic things — the email subject, a heading,
the CSV filename and a field in the ledger — and nothing else. Both modes ran
the identical scan, and WHICH session that scan read was decided entirely by
the wall clock in scanner.current_session(): today's session once 16:15 ET has
passed, otherwise the previous one. Nothing compared the two. So
`python -m src.pipeline evening` at lunchtime scanned YESTERDAY and mailed it
as "Evening candidates", and `morning` after the close mailed a "Morning
watchlist" for a day that had already finished. Neither was visible from the
email, the CSV or the ledger — the same silent wrongness step 5 exists to end.

Each mode now DECLARES the side of the close it belongs on (see MODES), and
the run checks that against the clock before it spends anything. A
disagreement does not stop the run: it degrades it, exactly like every other
survivable problem here, so the reason lands in the RunReport, in the red band
at the top of the email, in docs/data.json's run.errors and in the exit code.
Not in docs/ledger.json — add_run() keeps a status word per run and not the
sentences behind it, and README and this docstring both claimed otherwise for
a whole step. A morning run writes neither file, so for that mode the email
and the exit code are the whole record. Refusing would trade a mislabelled
email for no email, and no email is indistinguishable from a market holiday —
the failure this pipeline was built around.

One thing makes the label unable to lie in the first place, whatever the
clock says: the session that was actually scanned is named wherever the run
speaks — the email subject, its header line, and the CSV's filename. A run that read
yesterday's bars now says "session 2026-08-31" everywhere it speaks.

SCAN_SESSION_DATE is exempt from the check by design. A run pinned to an old
session is the user overruling the clock on purpose — README documents it as
the way to seed a history — and a deliberate backfill must not be reported as
a mistake. The pinned session then stands in for "what the clock would have
said" everywhere in this module, so the morning mode's freshness check follows
the same pin rather than contradicting it.

A NAME IS NOT NEW JUST BECAUSE THE RUN IS (step 10)
---------------------------------------------------
Every run also used to start from nothing. A name that burst on Monday and
still cleared the filter on Tuesday was presented as a brand-new day-1 idea on
both nights, with nothing telling the reader they had already looked at it.
Step 9 built the store that knows better — docs/ledger.json holds every scored
and gated candidate for up to 260 runs — and the pipeline only ever wrote to
it. It is now read back before the email goes out, and every burst the run
reports carries a streak: which day of this setup it is, when the name last
appeared, and what it was scored then. src.ledger.MAX_STREAK_GAP_SESSIONS
holds the one judgement behind it (what "the same setup" means) and the
reasoning for it.

Reading that history can never kill a run. See load_history(): the run
happening now is worth more than the runs already gone, which is the posture
Ledger.load() already took for an unreadable file. But a history that could
not be read is reported and every streak goes out with no day number and the
reason it has none, because "we have never seen this name" and "we could not
read the file that would know" are different sentences and only one of them is
a claim about the market. Unknown is a state every surface renders in words —
the email, both dashboard tables and the pick card — because the failure it
guards against is a reader seeing nothing and reading it as day 1.

FAILING LOUDLY (step 5)
-----------------------
Every failure this pipeline had used to end in the same cheerful email, so a
working screener and a dead one were indistinguishable from the inbox — and
GitHub Actions, the only monitor this project has, went green for all of them.
Three things now separate them:

  PREFLIGHT.  Every layer declares the environment it cannot run without
  (scanner/scorer/emailer REQUIRED_ENV), and preflight() checks the union
  before the run spends anything. RESEND_API_KEY and EMAIL_TO used to be read
  with os.environ[...] on the last line of the run, so a missing one cost the
  whole scan and every paid Claude call and then mailed nothing.

  EXIT CODES.  0 clean · 1 the run failed and there is no shortlist · 2 the run
  finished but is degraded and must not be traded off as a complete scan.
  Actions turns red for 1 and 2, which is the point: a run nobody can trust
  should not look like a run that worked.

  THE EMAIL SAYS SO.  A degraded run carries DEGRADED in its subject and a red
  band listing every problem above the table; a failed one sends the same
  artifact with FAILED and no rows. Nothing is suppressed — an email that does
  not arrive is another silent failure, and the whole point is to end those.

What counts as degraded is one judgement, written once, in DEGRADED_* below
and in the checks in run(). The scanner draws a separate and much higher line
for when a scan cannot be reported at all (ScanConfig.max_stale_fraction and
friends) and raises there; this module never overrules it.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from . import ledger, scanner
from .lynch import VETO_RULES, evaluate_2lynch, extra_context, failed_vetoes, veto_reason
from .scanner import ScanConfig, run_scan
from .scorer import MODEL as DEFAULT_MODEL
from .scorer import render_chart, score_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pipeline")

TOP_N = 5          # how many candidates the EMAIL carries. Not the archive.
MIN_LYNCH_PASSES = 3
MAX_TO_SCORE = 25  # cap Claude calls per run

#: The reason word an unscored burst carries, one per absolute rule in
#: src.lynch, and the vocabulary docs/data.json's `gated_out[].reason` and the
#: ledger's `streak.last_outcome` are written in. DERIVED from src.lynch's own
#: VETO_RULES -- this was a hand-kept tuple of the same names, and an audit
#: showed that adding a second veto to src.lynch alone left the whole suite
#: green and killed the evening run on KeyError, which is the opposite of what
#: this comment used to promise. A test asserts the email and the page can both
#: say every word in here: a reason nothing can render is a row the reader is
#: told nothing about.
VETO_REASONS = {name: veto_reason(name) for name in VETO_RULES}


def unscored_reason(lynch: dict) -> str:
    """Why this burst was not scored — the veto first, because it is absolute.

    The order is the judgement. A candidate three up days into a run that also
    fails the checklist is refused by the up-days rule whatever the checklist
    said, so "veto_up_days" is what the reader needs; reporting "lynch_gate"
    would name the weaker of two reasons and hide the cardinal one.
    """
    broken = failed_vetoes(lynch)
    if broken:
        # veto_reason(), not VETO_REASONS[...]: a rule this module has never
        # heard of must not take the run down after the scan has been paid for.
        return veto_reason(broken[0])
    if lynch["passes"] < MIN_LYNCH_PASSES:
        return "lynch_gate"
    return "score_cap"

#: Where render_chart() writes. Under docs/ because docs/index.html names a
#: chart as a path relative to itself, so a dashboard opened on the machine
#: that ran the pipeline shows the same image the model was given. See
#: ledger.chart_ref() for the other half.
#:
#: THESE ARE NOT COMMITTED, and that is a decision, not an oversight (step 10).
#: .gitignore blocks /docs/charts/, so what GitHub Pages serves carries no PNGs
#: and the page degrades to an explained frame. Two reasons, and the second is
#: the one that costs money:
#:
#:   Size. A chart is ~57 KB and a night renders up to MAX_TO_SCORE of them —
#:   about 360 MB a year of history that does not delta-compress and cannot be
#:   removed after the fact. Nothing had ever been committed only because the
#:   persist step was aborting before its commit on every run.
#:
#:   A chart here cannot say which session drew it. One file per ticker,
#:   overwritten by every evening run, with the session nowhere in the name or
#:   the file. An evening run that renders and then dies before publish()
#:   leaves this directory a session AHEAD of docs/data.json, and anything that
#:   later resolves a chart by bare path attaches the newer picture to the
#:   older numbers with nothing showing it — reproduced with file hashes. The
#:   evening email is unaffected: it attaches the PNGs it rendered moments
#:   earlier in the same process. The morning email carries no chart at all
#:   and says so, which is the one thing a stale chart could not do; see
#:   MORNING_CHART_NOTE.
CHARTS_DIR = ledger.DOCS_DIR / "charts"

#: What the morning email prints where a chart would be. The model is told to
#: trust the chart over the numbers and a reader will do the same, so a picture
#: that might belong to a different session is worse than no picture: it is
#: wrong in the direction of confidence, and silently.
MORNING_CHART_NOTE = (
    "no chart — the PNG on disk is overwritten by every evening run and records no "
    "session, so this pass cannot show that it is the one these numbers came from. "
    "Last night's email carried the chart it had just rendered."
)

# Exit codes. 2 exists because "the screener is broken" and "the screener ran
# and found nothing" must not be the same signal to the only monitor there is.
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_DEGRADED = 2

# When a scan stops being clean. Well below the fractions at which src.scanner
# refuses to report a scan at all: this is the line for "say so", that one is
# for "do not say anything". A handful of halted or delisted names is a normal
# day on any universe, so neither of these fires on one.
DEGRADED_STALE_FRACTION = 0.10    # symbols whose newest bar is an older session
DEGRADED_NO_BARS_FRACTION = 0.10  # symbols the feed returned nothing for at all


class PreflightError(RuntimeError):
    """The run cannot finish with the environment it has, so it does not start."""


@dataclass(frozen=True)
class Mode:
    """What a run type promises, declared once instead of implied four times.

    `scans` is the whole difference in behaviour, and it is deliberately not a
    third state: a mode either goes and looks at the market or it re-presents
    what the last one found. There is no honest middle, because a morning run
    before the open has NO data an evening run did not have — the daily bar it
    would read is the same bar, so a "morning scan" is the evening scan again
    at a different hour, at the same cost in Claude calls, for the identical
    answer. That is what made the old morning mode a label.

    `after_the_close` is the side of 16:15 ET the mode belongs on, checked
    against scanner.session_has_closed(). `expects` is the sentence a reader
    gets when the two disagree; it is written here, next to the promise, so
    the report cannot describe a rule different from the one being enforced.
    """

    name: str
    scans: bool
    after_the_close: bool
    expects: str


MODES: dict[str, Mode] = {
    "evening": Mode(
        name="evening", scans=True, after_the_close=True,
        expects="an evening run is the discovery pass over the session that closed "
                "today, so it expects to start after the 16:15 ET close",
    ),
    "morning": Mode(
        name="morning", scans=False, after_the_close=False,
        expects="a morning run is the follow-through pass over the last evening run, "
                "so it expects to start before today's 16:15 ET close",
    ),
}


def mode_for(run_type: str) -> Mode:
    """The declared mode, or a ValueError naming the ones that exist."""
    try:
        return MODES[run_type]
    except KeyError:
        raise ValueError(
            f"unknown run type {run_type!r}; expected one of: " + ", ".join(MODES)
        ) from None


def expected_session(cfg: ScanConfig, now: datetime | None = None) -> date:
    """The session this run is about — the pin if there is one, else the clock.

    One definition, used by both modes, so a pinned session cannot mean the
    scanned session in one place and be ignored in the other.
    """
    return cfg.session_date or scanner.current_session(now)


def session_disagreement(mode: Mode, cfg: ScanConfig,
                         now: datetime | None = None) -> str | None:
    """The sentence to report when the mode and the clock disagree, else None.

    None whenever SCAN_SESSION_DATE is set: an explicitly pinned session is
    the user overruling the clock on purpose (seeding a history, re-running a
    day the market was closed), and reporting a deliberate backfill as a
    mistake would teach a reader to ignore this line on the day it is right.
    """
    if cfg.session_date is not None:
        return None
    if scanner.session_has_closed(now) == mode.after_the_close:
        return None
    session = scanner.current_session(now)
    if mode.after_the_close:
        return (f"{mode.expects}, but today's session has not closed yet. The newest "
                f"completed session is {session}, so that is what was read — it is "
                f"yesterday's market, not tonight's. Everything below is labelled "
                f"{session} and nothing has been relabelled as today.")
    return (f"{mode.expects}, but today's session has already closed — the newest "
            f"completed session is now {session}. This is a follow-through pass over "
            f"a run that is no longer the latest one, however the subject line reads.")


@dataclass
class RunReport:
    """What the run would otherwise only whisper into a log nobody reads.

    `errors` is a list of {"stage", "message"} — deliberately the shape
    docs/data.json's `run.errors` takes, so step 9 archives this object
    directly and the dashboard's "this run degraded" band renders from the
    same sentences the email does. One description of a failure, three
    audiences.

    A `problem` is survivable and downgrades the run to degraded; `fail` is
    the exception that ended it. Both are the same shape, because to a reader
    they are the same question: what went wrong.
    """

    stage: str = "startup"
    errors: list[dict] = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    failed: bool = False

    def problem(self, stage: str, message: str) -> None:
        self.errors.append({"stage": stage, "message": message})

    def fail(self, stage: str, exc: BaseException) -> None:
        self.failed = True
        self.problem(stage, f"{type(exc).__name__}: {exc}")

    @property
    def status(self) -> str:
        if self.failed:
            return "failed"
        return "degraded" if self.errors else "ok"

    @property
    def exit_code(self) -> int:
        return {"ok": EXIT_OK, "degraded": EXIT_DEGRADED, "failed": EXIT_FAILED}[self.status]

    def email_stats(self, **extra) -> dict:
        """The stats block the emailer reads, with the status in it."""
        return {"status": self.status, "errors": self.errors, **extra}

    def log_summary(self, run_type: str) -> None:
        """One terminal line that states the verdict, then every reason.

        At ERROR when the run is not clean: an INFO line saying "run complete"
        is what every one of these failures used to print.
        """
        if self.status == "ok":
            log.info("=== %s run complete: CLEAN (exit %d) ===", run_type, self.exit_code)
            return
        log.error("=== %s run complete: %s — %d problem(s), exit %d ===",
                  run_type, self.status.upper(), len(self.errors), self.exit_code)
        for e in self.errors:
            log.error("    [%s] %s", e["stage"], e["message"])


# --------------------------------------------------------------- preflight --

def _absent(names) -> list[str]:
    """Which of these are unset or empty."""
    return [name for name in names if not os.environ.get(name, "").strip()]


def missing_delivery_env() -> list[str]:
    """Just the email layer's requirements.

    Separate from missing_env() because the question is different: that one
    asks whether the run can start, this one asks whether the run can report
    that it could not. A missing ALPACA_API_KEY is a reason to send the failure
    notice, not a reason to withhold it — answering it with the union of every
    layer's requirements withheld the notice from exactly the failures it
    exists for.
    """
    from .emailer import REQUIRED_ENV as EMAIL_ENV

    return _absent(EMAIL_ENV)


def missing_env(dry_run: bool = False, run_type: str = "evening") -> list[str]:
    """Which required environment variables are absent or empty.

    Composed from each layer's own REQUIRED_ENV rather than listed here, so a
    layer that starts needing a new key cannot be preflighted against a stale
    copy of its requirements.

    Only the layers the mode actually runs: a morning follow-through reads two
    files this repo already contains and sends an email, so demanding Alpaca
    and Anthropic keys for it would refuse a run that would have worked
    perfectly. The default is "evening" — the mode that needs the most —
    because a caller who forgets to say is then over-strict rather than
    under-strict, and over-strict fails loudly at the start of a run instead of
    quietly in the middle of one.

    Empty counts as missing. GitHub Actions passes an unset secret as '' , so
    every one of these would otherwise sail through an `in os.environ` check
    and fail as somebody else's 401 halfway through the run.
    """
    from .emailer import REQUIRED_ENV as EMAIL_ENV
    from .scanner import REQUIRED_ENV as SCAN_ENV
    from .scorer import REQUIRED_ENV as SCORE_ENV

    market = list(SCAN_ENV) + list(SCORE_ENV) if mode_for(run_type).scans else []
    # --dry-run skips only delivery, so it still needs data and scoring keys.
    required = market + ([] if dry_run else list(EMAIL_ENV))
    return _absent(required)


def preflight(dry_run: bool = False, run_type: str = "evening") -> None:
    """Refuse to start a run that cannot finish. Raises PreflightError.

    Reports EVERY missing variable, not the first: an operator setting this up
    should get one list, not one round trip per key.
    """
    missing = missing_env(dry_run, run_type)
    if missing:
        raise PreflightError(
            "missing or empty required environment: " + ", ".join(missing)
            + ". Nothing has been spent — checked before the scan rather than "
            "after it. See .env.example."
        )
    log.info("Preflight OK%s", " (dry run: delivery keys not required)" if dry_run else "")


def archive(results: list[dict], run_type: str, session: date | None = None) -> Path:
    """The run's CSV, in results/ — every scored candidate, not the shortlist.

    It is handed `scored`, not the five rows that went out by email. Until step
    9 the caller passed score_all()'s truncated return, so TOP_N cut this file
    as well as the email and the other twenty judgements a run made were never
    written down anywhere. results/ is gitignored and uploaded as a 30-day
    workflow artifact; the durable record is docs/ledger.json.

    Named for the SESSION it scanned, not for the day it ran. Those are the
    same date on a normal evening run and differ on exactly the runs that used
    to lie: an evening run started before the close wrote yesterday's bursts
    into a file stamped today, and a backfill of an old session wrote it into
    a file stamped now. `session` of None falls back to the UTC date, which is
    all a caller with no scan behind it can honestly say.
    """
    out = Path("results")
    out.mkdir(exist_ok=True)
    stamp = (session or datetime.now(timezone.utc).date()).strftime("%Y-%m-%d")
    path = out / f"{stamp}_{run_type}.csv"
    cols = ["ticker", "date", "close", "gain_pct", "volume_ratio",
            "lynch", "score", "verdict", "reason", "key_risk"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)
    return path


def load_history(report: RunReport) -> ledger.Ledger:
    """The ledger, read back. NEVER raises — a run is not lost to its history.

    Ledger.load() already takes that posture for a file it cannot parse (it
    moves it aside and starts empty), and this matches it for everything else
    a read can do: a directory where a file should be, a permission change, an
    interrupted write. The run happening now is the thing that cannot be
    re-fetched, because market data is live-only; the history has already been
    written down once.

    What is NOT swallowed is the fact of it. A failed read costs this run its
    streak numbers, and saying nothing would leave every candidate looking
    like a first-ever sighting — a claim about the market made out of a file
    error. It degrades the run instead, and streaks_for() below answers with a
    block whose `day` is null and whose reason is "history_unreadable".
    """
    book = ledger.Ledger(ledger.DOCS_DIR)
    try:
        book.load()
    except Exception as e:  # noqa: BLE001 — reported, never raised: see the docstring
        log.exception("Could not read the run history at %s", book.path)
        # Move it aside FIRST. Without this the run carries on with an empty
        # history and write() replaces a year of accumulated outcomes with a
        # one-run ledger — the exact loss Ledger.set_aside() exists to prevent,
        # reintroduced through the door this catch-all opened.
        book.set_aside(f"{book.path} could not be read ({type(e).__name__}: {e})")
    undated = ledger.undated_runs(book.runs)
    if undated:
        report.problem("history",
                       f"{undated} of {len(book.runs)} runs in the history carry a date "
                       "this run cannot read, so the record cannot say when they "
                       "happened. Their bursts still count -- the rows carry their own "
                       "sessions -- but the record's span is only what the readable "
                       "dates prove, so some day numbers will be withheld that a whole "
                       "history would have given")
    if book.load_error:
        report.problem("history",
                       f"the run history could not be read ({book.load_error}), so this "
                       "run cannot tell a name it has seen before from a new one: every "
                       "streak below is null rather than day 1. The scan itself is "
                       "unaffected, and this run still writes its own record")
    return book


def streaks_for(book: ledger.Ledger, session, tickers) -> dict[str, dict]:
    """Day-N-of-this-setup for each ticker. One block per ticker, always.

    An EMPTY ledger and an UNREADABLE one answer differently on purpose, and
    src.ledger cannot tell them apart from the inside — both are `runs == []`.
    Ledger.load_error is what knows, so it is passed in: an unreadable history
    makes every block `day: null` with the reason, rather than a confident
    day 1 assembled out of a file error.

    Nothing returns an EMPTY dict any more. It used to for an unreadable
    history and for a run with no session, and the caller's `marks.get()` then
    turned that into `streak: null` on the row — a shape the email and the
    dashboard each rendered differently, and two of the three rendered as
    nothing at all. A block that says which kind of unknown it is can be
    rendered; an absence cannot.
    """
    return ledger.streaks(book.runs, tickers, session, unreadable=book.load_error)


def run(run_type: str, dry_run: bool = False, tickers: list[str] | None = None,
        report: RunReport | None = None) -> list[dict]:
    """One run, start to finish, in whichever mode was asked for.

    Returns the rows the run reported — every scored candidate for an evening
    discovery run, the rows it followed through on for a morning one. Never
    the five that went out by email: TOP_N cuts the email and nothing else.

    `report`, if given, is filled with everything the returned rows cannot
    say: which stage was running, what went wrong, and the counts behind it.
    main() passes one in and exits on its code. A caller that does not pass one
    still gets the same log lines and the same email — the report is built
    either way; the argument only lets the caller read it.
    """
    report = report if report is not None else RunReport()
    mode = mode_for(run_type)
    if not mode.scans:
        return follow_through(mode, dry_run=dry_run, report=report)
    return discover(mode, dry_run=dry_run, tickers=tickers, report=report)


def discover(mode: Mode, dry_run: bool = False, tickers: list[str] | None = None,
             report: RunReport | None = None) -> list[dict]:
    """The evening run: scan, gate, chart, score, archive, publish, mail.

    Returns EVERY scored candidate, ranked. Not the five that went out by
    email: those are `scored[:TOP_N]`, cut here rather than inside
    score_all(), because the truncated list used to be the only thing this
    function ever produced and archive() wrote exactly it.
    """
    report = report if report is not None else RunReport()
    run_type = mode.name
    cfg = ScanConfig()
    log.info("=== %s run starting ===", run_type)

    report.stage = "preflight"
    preflight(dry_run, run_type)

    # Does the mode match the clock it is running on? Before the scan, so the
    # reason reaches the email band, the ledger and the exit code even if a
    # later stage fails; and reported rather than raised, because a run that
    # says which session it read is a usable run.
    report.stage = "session"
    disagreement = session_disagreement(mode, cfg)
    if disagreement:
        report.problem("session", disagreement)

    # Layer 1: scan. Alpaca returns bars only up to the session the scan
    # targets, and src.scanner drops anything that does not carry it. Which
    # session that is comes from the clock (or SCAN_SESSION_DATE) — the check
    # above is what makes sure it is the one this mode said it would read.
    report.stage = "scan"
    scan_stats: dict = {}
    candidates = run_scan(cfg, universe=tickers, stats=scan_stats)
    n_bursts = len(candidates)
    _check_scan(scan_stats, report)

    # Layer 2: 2LYNCH checklist + context, hard gate, keep the best
    prepared = []
    for cand in candidates:
        lynch = evaluate_2lynch(cand.history)
        ctx = extra_context(cand.history)
        prepared.append((cand, lynch, ctx))

    prepared.sort(key=lambda x: (x[1]["passes"], x[0].gain_pct), reverse=True)
    # A veto outranks the pass count. Bonde's up-days rule is stated as "never
    # buy", so a burst that breaks it is refused however many checks it passed;
    # a 6/6 name three up days into a run is exactly the case the rule is about.
    passed_gate = [p for p in prepared
                   if not failed_vetoes(p[1]) and p[1]["passes"] >= MIN_LYNCH_PASSES]
    to_score = passed_gate[:MAX_TO_SCORE]
    # Everything the scan found that will not be scored, with the reason it
    # was not. Kept rather than dropped: docs/data.json's contract is that
    # scored + gated_out accounts for every burst, and a per-check pass rate
    # computed over the survivors alone describes the survivors, not the run.
    scoring = {cand.ticker for cand, _lynch, _ctx in to_score}
    # The context travels with the unscored rows too. It used to be dropped
    # here, so the burst a rule refused -- the one case that could show whether
    # the rule earns its keep -- was archived without the measurement the rule
    # was applied to.
    unscored = [(cand, lynch, ctx, unscored_reason(lynch))
                for cand, lynch, ctx in prepared if cand.ticker not in scoring]
    log.info("%d bursts → %d passed 2LYNCH gate (scoring top %d)",
             n_bursts, len(passed_gate), len(to_score))

    # Layers 3-5: charts + Claude scoring
    report.stage = "chart"
    scored_inputs = []
    chart_errors: dict[str, str] = {}
    for cand, lynch, ctx in to_score:
        chart = None
        try:
            chart = render_chart(cand.ticker, cand.history, out_dir=str(CHARTS_DIR))
        except Exception as e:  # noqa: BLE001
            # Survivable — the candidate is still scored — but not free: the
            # model is told to trust the chart over the numbers, and without
            # one it is scoring blind. provenance.chart_seen records that per
            # row; chart_error carries the reason into the archive, and this
            # records that the run had to do it at all.
            log.warning("Chart render failed for %s: %s", cand.ticker, e)
            chart_errors[cand.ticker] = f"{type(e).__name__}: {e}"
        scored_inputs.append((cand, lynch, ctx, chart))
    if chart_errors:
        report.problem("chart", f"{len(chart_errors)} of {len(to_score)} charts failed to "
                                "render; those candidates were scored without the image: "
                                + ", ".join(f"{t} ({e})" for t, e
                                            in list(chart_errors.items())[:5]))

    report.stage = "score"
    score_stats: dict = {}
    returned = score_all(scored_inputs, top_n=TOP_N, min_lynch=MIN_LYNCH_PASSES,
                         stats=score_stats)
    # Every scored row, in rank order, untruncated. score_all() also returns
    # its own top-N slice; `rows` is the list step 9 archives.
    scored = score_stats.get("rows")
    if scored is None:  # a caller who replaced score_all without filling stats
        scored = list(returned)
    # THE CUT — and the only one left. It used to happen inside score_all(),
    # and archive() wrote that truncated return, so TOP_N threw away four
    # fifths of every night's judgements before anything could record them.
    # The email carries five; the archive carries all of them.
    shortlist = scored[:TOP_N]
    _check_scoring(score_stats, report)

    # What the record already knows about these names. Read BEFORE this run is
    # added to it — publish() adds it below out of the same object — so that
    # a session scanned twice does not turn every name in it into a repeat of
    # itself. The ledger is loaded once here and handed on, rather than opened
    # again inside publish(), because two reads of one file can disagree.
    report.stage = "history"
    session = scan_stats.get("session")
    book = load_history(report)
    marks = streaks_for(book, session,
                        [c.ticker for c, _lynch, _ctx in prepared])
    for row in scored:
        # The email reads this off the scored row; docs/data.json gets it from
        # the same dict below. One lookup, two audiences, no second rule.
        row["streak"] = marks.get(row["ticker"])
    # `day` is None when the record cannot say, so it is compared as a number
    # only after that is ruled out: `None > 1` is a TypeError, and it would be
    # raised by the log line at the end of a run that had already succeeded.
    repeats = sum(1 for row in scored
                  if ((row.get("streak") or {}).get("day") or 0) > 1)
    if repeats:
        log.info("%d of %d scored candidate(s) are a repeat of a setup already in "
                 "the ledger", repeats, len(scored))

    # Report the universe actually scanned. This said "US common stocks" while
    # the scan had been narrowed to a checked-in list, so the daily email
    # described a market it no longer looks at. The count comes from the scan
    # that just ran rather than from a second read of the symbol file, which
    # could disagree with it.
    scanned = scan_stats.get("requested", len(tickers or []))
    report.counts.update({"universe": scanned, "bursts": n_bursts,
                          "gated": len(passed_gate), "to_score": len(to_score),
                          **{k: v for k, v in scan_stats.items() if k != "stale"},
                          "stale": len(scan_stats.get("stale", {})),
                          "scored": score_stats.get("scored", 0),
                          "claude": score_stats.get("claude", 0),
                          "fallback": score_stats.get("fallback", 0)})
    stats = report.email_stats(
        universe=f"{scanned} checked-in US common stocks",
        # How many CLEARED the gate, not how many fitted under the call cap
        # afterwards. The email prints this as "Passed 2LYNCH gate", and on any
        # night with more than MAX_TO_SCORE survivors the capped number was a
        # smaller answer to a question nobody asked.
        bursts=n_bursts, gated=len(passed_gate),
        # And how many an absolute rule refused, because `gated` excludes them
        # and is printed under the label "Passed 2LYNCH gate". Without this the
        # email told the reader a 6/6 name had not passed the checklist, which
        # is the one collapse this project forbids by name.
        vetoed=sum(1 for _c, _l, _x, reason in unscored
                   if reason in VETO_REASONS.values()),
        scored_by={"claude": score_stats.get("claude", 0),
                   "fallback": score_stats.get("fallback", 0)},
        # The session that was actually read, in the subject line and above the
        # table. This is what stops a mode from lying whatever the clock says:
        # a run that scanned yesterday now says so in the artifact a person
        # reads, instead of only in a JSON field nobody opens.
        session=ledger.iso_date(session),
    )

    report.stage = "archive"
    path = archive(scored, run_type, session=session)
    log.info("Archived %d scored candidate(s) to %s", len(scored), path)
    published = publish(run_type=run_type, dry_run=dry_run, cfg=cfg, report=report,
                        scan_stats=scan_stats, score_stats=score_stats,
                        scored=scored, unscored=unscored, to_score=to_score,
                        n_bursts=n_bursts, n_passed=len(passed_gate),
                        shortlist_size=len(shortlist), chart_errors=chart_errors,
                        explicit_tickers=tickers, book=book, marks=marks)
    log.info("Published %s (%d candidates, %d not scored) and %s (%d runs, %d "
             "forward return(s) filled this run)",
             published["data"], len(scored), len(unscored),
             published["ledger"], published["runs"], published["filled"])

    # Layer 6: email. A degraded run still sends. Suppressing it would replace
    # a misleading email with no email, and no email is the failure this step
    # exists to end — the operator cannot tell it from a market holiday. It
    # goes out marked instead: DEGRADED in the subject, the reasons in a band
    # above the table.
    report.stage = "email"
    if dry_run:
        log.info("DRY RUN — skipping email. Shortlist:")
        for r in shortlist:
            log.info("  %s  %s/10 (%s) %s", r["ticker"], r["score"], r["verdict"], r["reason"])
    else:
        from .emailer import send_email
        send_email(shortlist, run_type, stats)

    report.stage = "complete"
    report.log_summary(run_type)
    return scored


def email_row(row: dict) -> dict:
    """A published candidate, in the shape src.emailer renders.

    docs/data.json and the email are two shapes of one judgement, and this is
    the ONLY place they are converted — the alternative is a second rendering
    rule that drifts from the first. Two differences do real work:

      lynch_detail  the dashboard keeps one dict per check so it can draw
                    them; the email wants the same six lines src.lynch built
                    for it, so they are rebuilt from the same fields.
      chart         DROPPED, with MORNING_CHART_NOTE printed where the picture
                    would have been. This used to resolve the published path
                    back under docs/ and attach whatever PNG was sitting
                    there — and docs/charts is one file per ticker, rewritten
                    by every evening run and stamped with no session, while
                    docs/data.json is only rewritten at publish(). An evening
                    run that rendered and then died left the two a session
                    apart, and this row then paired Monday's numbers with
                    Tuesday's picture with nothing anywhere saying so.
    """
    detail = [f"{'PASS' if d.get('pass') else 'FAIL'}  {d.get('code')} "
              f"{d.get('label')}: {d.get('value')}"
              for d in (row.get("lynch_detail") or [])]
    return dict(row, lynch_detail=detail, chart=None, chart_note=MORNING_CHART_NOTE)


def _day_number(row: dict) -> int:
    """The row's streak day as a number, or 0 when it is not one.

    A morning row comes off disk, and ledger.snapshot_problem() checks its
    SHAPE, not its content: a `streak.day` of "3" is a well-formed block with
    a wrong value in it. The old `(... or 0) > 1` guarded None and nothing
    else, so that one string was a TypeError out of the counts block. The
    rule is ledger.streak_day()'s; this only spells "not a number" as 0 for
    a count.
    """
    return ledger.streak_day(row.get("streak")) or 0


def stale_sessions(session, expected) -> int | None:
    """How many sessions behind the snapshot is. None when that is not a number.

    src.ledger.sessions_between is the one definition of a session gap in this
    project (weekends subtracted, holidays not), so this is a name for it and
    not a second arithmetic. Zero or negative means the snapshot is not behind
    at all — a session pinned into the future by SCAN_SESSION_DATE reaches here
    too, and it is a different sentence from a stale one.
    """
    return ledger.sessions_between(session, expected)


def stale_snapshot_note(source: dict, session, expected) -> str:
    """What to say when nothing has published for the session this run expected.

    It used to say "the session to follow through on is 2026-11-26" — a
    sentence that asserts a session existed. Nothing here can know that:
    expected_session() subtracts weekends and nothing else, so on the morning
    after every market holiday this named a day the market never held and the
    red band asserted it in confident prose. Reproduced at Friday 2026-11-27
    08:30 ET against a Wednesday snapshot, and again the Tuesday after MLK
    day: nine or ten mornings a year of a red band and a red Actions run,
    each one teaching the reader that the band is routine — and the message
    that matters, "the evening run has been failing and nobody noticed", is
    that same band.

    A holiday calendar is not the fix. An approximate one (pandas'
    USFederalHolidayCalendar disagrees with the NYSE on Good Friday, among
    others) used to make a confident claim is a worse defect than the one it
    replaces, and the evening run deliberately has none either — it discovers
    a closed market from the feed and fails on evidence. This run has no feed.

    BUT THE HEDGE IS ONLY LIVE AT A GAP OF ONE, and stating it at any gap made
    it false in exactly the case it was written to protect. None of the US
    market's SCHEDULED holidays are adjacent — there is no pair of consecutive
    weekday closures on the calendar — so from a gap of two sessions up, at
    least one of those days was a scheduled session and "the market held no
    session for it to scan" cannot account for the silence. Unscheduled
    closures HAVE run to consecutive sessions (9/11, Hurricane Sandy, the 2007
    day of mourning the day after New Year's Day), so that clause stays, named
    as the exception it is: each was news the reader already has.

    None of this needs a calendar — it is arithmetic on the gap, which is why
    the gap is stated in every branch. Rendered at 1, 3 and 15 sessions the
    three bands used to be byte-identical but for a date.

    Degraded and exit 2 either way: a follow-through on a snapshot that is not
    last night's must not look clean, however it got that way.
    """
    published = source.get("type") or "evening"
    gap = stale_sessions(session, expected)
    def tail(lead: str) -> str:
        # "Either way" belongs to the branch that names two explanations, and
        # only one branch still does. The facts after it are the same in all
        # of them: which run is on the table, and that it is not today's.
        return (f"{lead} the rows below are {session}'s, labelled {session} "
                f"everywhere, and are not a scan of any session since")
    if gap is None:
        return (
            f"the newest published run is the {published} run of {session}, which is not "
            f"the session this run expected ({expected}) and cannot be compared with it — "
            f"the date on the snapshot is missing or unreadable, so how far behind it is "
            f"is unknown. " + tail("Meanwhile")
        )
    if gap == 0:
        # Not "0 sessions ago": the two dates differ and NO trading session
        # separates them, which happens when the published date is not a
        # session at all — a SCAN_SESSION_DATE pinned to a weekend does it.
        # Calling that "later" or "1 session ago" would both be wrong.
        return (
            f"the newest published run is the {published} run of {session}, which is not "
            f"the session this run expected ({expected}) — though no trading session "
            f"separates the two dates, so one of them is not a session the market held. "
            f"A SCAN_SESSION_DATE pinned to a weekend does exactly this. " + tail("Meanwhile")
        )
    if gap < 0:
        return (
            f"the newest published run is the {published} run of {session}, which is "
            f"LATER than the session this run expected ({expected}). A follow-through "
            f"pass runs before today's close, so a published session ahead of it means "
            f"a run was pinned forward with SCAN_SESSION_DATE, not that time has moved. "
            + tail("Meanwhile")
        )
    if gap == 1:
        return (
            f"the newest published run is the {published} run of {session}, and nothing "
            f"has published a later session — that is 1 session ago. There are two "
            f"explanations and at a gap of one this run cannot tell them apart: last "
            f"night's evening run did not publish (it failed, or it never ran), or the "
            f"market held no session for it to scan. There is no holiday calendar here "
            f"to choose between them, deliberately — an approximate one would name the "
            f"wrong reason with confidence. If the market did trade on {expected}, then "
            f"the evening run is what broke, and its own email and its Actions run say "
            f"how. " + tail("Either way")
        )
    return (
        f"the newest published run is the {published} run of {session}, and nothing has "
        f"published a later session — that is {gap} sessions ago, counting through "
        f"{expected}. A market holiday does not explain a gap this long: none of the "
        f"market's scheduled holidays are adjacent, so at least one of those {gap} days "
        f"was a scheduled session and nothing scanned it. The evening run has stopped "
        f"publishing — its own email and its Actions run say how it broke, and if "
        f"neither exists it did not run at all. (An UNSCHEDULED closure can run to "
        f"consecutive sessions — 9/11, Hurricane Sandy, the 2007 day of mourning that "
        f"fell the day after New Year's Day — but each of those was news you would "
        f"already have, which is the difference from silence.) " + tail("Meanwhile")
    )


def carried_problems(source: dict, session) -> list[dict]:
    """Last night's own problems, in last night's words, for this morning's reader.

    src.emailer._banner() already argues this for the evening email: "138 of
    230 symbols had no bar" tells an operator where to look and "degraded"
    does not. The morning email carried the status word forward and dropped
    every sentence behind it, so "NOT ONE of 12 candidates was scored by
    Claude; the order is not a ranking" — the one thing a reader needs before
    acting on a ranking — reached the 8:30 reader as the word DEGRADED.

    The stage is prefixed with the run the problem belongs to, because one red
    band now carries two runs' problems and a reader must be able to tell
    which is which. Anything not shaped like {stage, message} is skipped: this
    comes off disk, and a truncated or hand-edited snapshot must not take the
    email down with it.
    """
    carried = []
    for problem in source.get("errors") or []:
        if not isinstance(problem, dict):
            continue
        message = str(problem.get("message", "")).strip()
        if not message:
            continue
        carried.append({
            "stage": f"{session} {source.get('type') or 'evening'} · "
                     f"{problem.get('stage') or 'unknown'}",
            "message": message,
        })
    return carried


def follow_through(mode: Mode, dry_run: bool = False,
                   report: RunReport | None = None) -> list[dict]:
    """The morning run: last night's candidates again, before today's open.

    IT DOES NOT SCAN, AND THAT IS THE POINT. A morning run has no market data
    an evening run did not have — the daily bar it would read is the same
    daily bar — so a "morning scan" is the evening scan repeated at a different
    hour, for the identical answer, at the same cost in Claude calls. What it
    can honestly add is the thing the evening email could not: these names in
    front of a reader at the hour they might act on them, each one with what
    the record says about it — which day of this setup it is, when it last
    appeared, what it scored then.

    IT ATTACHES NO CHART, for a reason of the same shape: the only picture it
    could attach is whatever is in docs/charts right now, which is one file per
    ticker with no session in it and is rewritten by every evening run. See
    CHARTS_DIR and MORNING_CHART_NOTE. The evening email keeps its charts —
    it attaches the ones it rendered moments earlier.

    IT WRITES NOTHING, and that is also deliberate. docs/ledger.json is the
    record of what was SCANNED; add_run() keys its entries on (date, type), so
    a morning entry for a session an evening run already recorded would sit
    beside it carrying the same candidates, and every mean computed across
    runs would count that one burst twice. A view over the record does not
    belong inside it.

    Its whole input is the snapshot the last run published, so a stale or
    absent one is the interesting failure, not an edge case: it is reported
    and the email goes out empty and marked, rather than showing yesterday's
    week-old list as today's watchlist.
    """
    report = report if report is not None else RunReport()
    cfg = ScanConfig()
    run_type = mode.name
    log.info("=== %s run starting ===", run_type)

    report.stage = "preflight"
    preflight(dry_run, run_type)

    report.stage = "session"
    disagreement = session_disagreement(mode, cfg)
    if disagreement:
        report.problem("session", disagreement)

    report.stage = "history"
    snapshot, why = ledger.read_snapshot(ledger.DOCS_DIR)
    rows: list[dict] = []
    source: dict = {}
    session = None
    behind: int | None = None
    if snapshot is None:
        report.problem("history",
                       f"there is nothing to follow through on: {why}. A morning run "
                       "presents the last evening run's candidates; it does not scan, "
                       "so with no published run there is nothing for it to show")
    else:
        source = snapshot["run"]
        session = source.get("date")
        rows = [email_row(row) for row in snapshot["candidates"]]
        expected = ledger.iso_date(expected_session(cfg))
        if session != expected:
            # The check that makes this mode honest about WHICH session it is
            # following through on. Monday morning after a Friday evening run
            # is the normal case and passes. What it must NOT do is assert
            # that the missing session existed — see stale_snapshot_note().
            behind = stale_sessions(session, expected)
            report.problem("session", stale_snapshot_note(source, session, expected))
        status = source.get("status", "ok")
        # Carried forward, not re-derived, and not summarised into the status
        # word either. A follow-through over an incomplete scan presented as a
        # complete one is the same silent wrongness this mode was built to
        # stop — and the reader of the 8:30 email is not the reader who saw
        # last night's red band, which is the argument for carrying the
        # reasons, not just the verdict.
        carried = carried_problems(source, session)
        if status != "ok":
            report.problem("history",
                           f"the {session} run this follows through on was itself a "
                           f"{status.upper()} run, so its shortlist is not a complete "
                           "scan of that session"
                           + (". Its own reasons follow, in the words it reported them"
                              if carried else ""))
        report.errors.extend(carried)

    shortlist = rows[:TOP_N]
    # No `universe` in this block. src.emailer._funnel_line's morning branch
    # prints none, because this pass scanned none; a sentence saying so was
    # built here for a whole step and never rendered anywhere, which reads as
    # a feature that exists. What replaced the old "Universe scanned: 230
    # checked-in US common stocks" line — printed over a run that had scanned
    # nothing — is the funnel line naming the run being followed instead.
    stats = report.email_stats(
        session=session,
        bursts=source.get("bursts", 0), gated=source.get("passed_gate", 0),
        # Counted off the snapshot's own rows, since the run block records no
        # veto total. A snapshot written before the rule existed has none, and
        # reports 0, which is the truth about that run.
        vetoed=sum(1 for row in ((snapshot or {}).get("gated_out") or [])
                   if isinstance(row, dict)
                   and str(row.get("reason") or "").startswith("veto_")),
        scored_by=source.get("scored_by") or {},
        # How far behind, in sessions, so the SUBJECT LINE can escalate. Every
        # staleness read DEGRADED before this, and a screener dead for three
        # weeks is not the Tuesday after Presidents' Day. src.emailer._prefix()
        # and _headline() are what read it; the reason is in the band already.
        stale_sessions=behind,
    )

    report.counts.update({"followed": len(rows), "shortlist": len(shortlist),
                          "session": session, "stale_sessions": behind,
                          "repeats": sum(1 for r in shortlist if _day_number(r) > 1)})

    report.stage = "email"
    if dry_run:
        log.info("DRY RUN — skipping email. Following through on %s:",
                 session or "nothing — no run to follow")
        for r in shortlist:
            log.info("  %s  %s/10 (%s) day %s", r["ticker"], r["score"], r["verdict"],
                     (r.get("streak") or {}).get("day") or "unknown")
    else:
        from .emailer import send_email
        send_email(shortlist, run_type, stats)

    report.stage = "complete"
    report.log_summary(run_type)
    return rows


def forward_bars(cfg: ScanConfig, tickers: list[str], through) -> dict:
    """Daily bars for names whose forward returns are still open.

    Deliberately the scan's own downloader (src.scanner's _download_batch)
    rather than a second request built here: it is the one place that decides
    split adjustment, the feed and the window, and a second copy of those
    decisions is a second thing to keep in step. This is the only extra data
    call step 9 adds — one per batch_size names, on a free feed.

    `through` is the newest session to read, which is the newest COMPLETED
    session now, not the session the scan targeted. They are the same on a
    normal evening run. They differ when a run deliberately scans an old
    session (SCAN_SESSION_DATE), and then everything after that burst has
    already happened, so the returns resolve inside the same run.
    """
    if not tickers:
        return {}
    client = scanner.get_clients()
    frames: dict = {}
    for i in range(0, len(tickers), cfg.batch_size):
        frames.update(scanner._download_batch(client, tickers[i: i + cfg.batch_size],
                                              cfg, through))
    return frames


def publish(*, run_type: str, dry_run: bool, cfg: ScanConfig, report: RunReport,
            scan_stats: dict, score_stats: dict, scored: list[dict],
            unscored: list[tuple], to_score: list[tuple], n_bursts: int,
            n_passed: int, shortlist_size: int, chart_errors: dict,
            explicit_tickers: list[str] | None, book: ledger.Ledger,
            marks: dict[str, dict]) -> dict:
    """Write docs/data.json and docs/ledger.json for the run that just ran.

    Everything the run knows, in the two shapes it is worth keeping: the
    dashboard's snapshot of tonight, and the ledger row per candidate that a
    later run fills a forward return into. See src.ledger.

    A failure to FETCH those later bars degrades the run rather than ending
    it — the scoring is done and the email is still worth sending — but it is
    reported, because a ledger that silently stops accumulating outcomes is
    the same class of failure step 5 exists to end.

    `book` arrives already loaded, and `marks` was computed from it before
    this run was added: the caller reads the history once and hands both on,
    so the streaks published here are the same numbers the email carries.
    """
    by_ticker = {cand.ticker: (cand, lynch, ctx) for cand, lynch, ctx in to_score}
    candidates = []
    for rank, row in enumerate(scored, start=1):
        cand, lynch, ctx = by_ticker[row["ticker"]]
        candidates.append(ledger.candidate_record(
            cand, lynch, ctx, row, rank=rank, docs_dir=ledger.DOCS_DIR,
            chart_error=chart_errors.get(row["ticker"]),
            streak_block=marks.get(row["ticker"])))
    # Gated bursts carry a streak too, for the same reason they carry a
    # checklist: a repeat that the gate rejected tonight is part of the setup's
    # history, and dropping it would make the record disagree with itself the
    # next time the name comes back.
    gated_out = [ledger.gated_record(cand, lynch, ctx, reason,
                                     streak_block=marks.get(cand.ticker))
                 for cand, lynch, ctx, reason in unscored]

    session = scan_stats.get("session")
    # The gate's own size, read off the checklist this run computed rather
    # than copied from src.lynch as a number that could drift out of step.
    #
    # Off EVERY burst that was measured, not just the scored ones. It read
    # `to_score` alone, so any night where nothing reached the scorer published
    # total_checks: null — and docs/index.html concatenates it straight into
    # prose, so the page said "rejected at the >=3/null 2LYNCH gate" and "under
    # 3 of null checks" while the rows beneath it correctly printed 5/6. A
    # confidently false sentence about the screener's own rule, on its only
    # published surface, with every check green. The checklist was computed for
    # all of them; only the scoring was skipped.
    #
    # Still None on a night with NO BURSTS AT ALL, because then nothing
    # measured it and inventing a 6 would be the same class of lie. The page
    # has to handle that, and now does.
    measured = list(to_score) + [(c, lynch, x) for c, lynch, x, _reason in unscored]
    total_checks = next((lynch["total"] for _c, lynch, _x in measured), None)
    run = {
        "date": ledger.iso_date(session) or ledger.iso_date(datetime.now(timezone.utc)),
        "type": run_type,
        "dry_run": bool(dry_run),
        "fixture": False,
        "universe": {
            "label": ("data/symbols.txt (checked in)" if explicit_tickers is None
                      else f"--tickers, {len(explicit_tickers)} named on the command line"),
            "size": scan_stats.get("requested", len(explicit_tickers or [])),
        },
        "bursts": n_bursts,
        "passed_gate": n_passed,
        "scored": len(scored),
        "score_cap": MAX_TO_SCORE,
        "shortlist_size": shortlist_size,
        "gate": {"min_lynch_passes": MIN_LYNCH_PASSES, "total_checks": total_checks,
                 # The RULE NAMES, not the reason words: this block describes
                 # what the run applied, and `gated_out[].reason` describes what
                 # happened to a row. Both vocabularies are in one file, so the
                 # difference is stated here rather than left to be inferred.
                 "vetoes": list(VETO_REASONS)},
        "scored_by": {"claude": score_stats.get("claude", 0),
                      "fallback": score_stats.get("fallback", 0)},
        "model": next((r["provenance"]["model"] for r in scored
                       if r["provenance"].get("model")), None) or DEFAULT_MODEL,
        "status": report.status,
        "errors": list(report.errors),
    }

    entry = book.add_run(run, candidates, gated_out)

    # Measure forward returns through the newest completed session, which is
    # at least the one just scanned.
    through = max(scanner.current_session(), session) if session else scanner.current_session()
    pending = book.pending_tickers(through)
    filled = 0
    try:
        frames = forward_bars(cfg, pending, through)
    except Exception as e:  # noqa: BLE001 — reported, not raised: see the docstring
        log.exception("Could not fetch bars for %d pending candidate(s)", len(pending))
        report.problem("archive",
                       f"forward returns for {len(pending)} candidate(s) from earlier runs "
                       f"could not be updated ({type(e).__name__}: {e}); their outcomes stay "
                       "pending in docs/ledger.json and will be retried next run")
    else:
        filled = book.fill_forward_returns(frames, through)

    # Re-read the report AFTER the fetch: a problem raised in the two lines
    # above is one of the run's problems, and the file that renders them must
    # not be the one artifact that leaves it out. Stamped on the entry add_run
    # handed back, never on runs[0] — the ledger is ordered by session, so
    # backfilling an older one puts this run in the middle of it.

    book.latest["run"]["errors"] = list(report.errors)
    book.latest["run"]["status"] = entry["status"] = report.status

    written = book.write()
    return {"data": written["data"], "ledger": written["ledger"],
            "runs": len(book.runs), "pending": len(pending), "filled": filled}


def _check_scan(scan_stats: dict, report: RunReport) -> None:
    """Turn what the scan saw into what the run is worth.

    src.scanner already raised on the fractions at which a scan cannot be
    reported at all. Everything here is survivable and was previously a log
    line at most: the run continues, and says so.
    """
    requested = scan_stats.get("requested", 0)
    with_bars = scan_stats.get("with_bars", 0)
    stale = len(scan_stats.get("stale", {}))
    dropped = scan_stats.get("dropped", 0)
    no_bars = scan_stats.get("no_bars", 0)
    session = scan_stats.get("session")

    if dropped:
        report.problem("scan", f"{dropped} of {requested} symbols were dropped after "
                               "their batch failed twice — they were never examined, "
                               "and an empty shortlist does not mean a quiet market")
    if with_bars and stale / with_bars > DEGRADED_STALE_FRACTION:
        report.problem("scan", f"{stale} of {with_bars} symbols with data ({stale / with_bars:.0%}) "
                               f"carried no bar for {session} and were skipped")
    if requested and no_bars / requested > DEGRADED_NO_BARS_FRACTION:
        report.problem("scan", f"{no_bars} of {requested} symbols returned no bars at all "
                               "— check the symbol file against what the feed carries")


def _check_scoring(score_stats: dict, report: RunReport) -> None:
    """A fallback is a score no model produced. Say how many there were.

    There is no threshold below which the email is withheld. The two states
    that matter are "some rows are checklist arithmetic" and "all of them
    are", because the second means the order is not a ranking at all — and
    both are things to tell a reader, not reasons to tell them nothing.
    """
    scored = score_stats.get("scored", 0)
    fallback = score_stats.get("fallback", 0)
    if not scored or not fallback:
        return
    first = ", ".join(f"{t} ({e})" for t, e in (score_stats.get("errors") or [])[:3])
    if fallback == scored:
        report.problem("score", f"NOT ONE of {scored} candidates was scored by Claude; "
                                f"every row is checklist arithmetic and the order is not "
                                f"a ranking. First failures: {first}")
    else:
        report.problem("score", f"{fallback} of {scored} candidates were not scored by "
                                f"Claude and carry a checklist fallback: {first}")


def attempted_session() -> dict:
    """The session a dead run was going for, for the email that reports it.

    Both failure notices used to print "Session scanned: not recorded" and the
    morning one "4% bursts that session: ?", because notify_failure() sent no
    stats at all — in the one email where an operator most wants to know which
    night broke. The session does not need the scan: expected_session() reads
    it off the clock, or off SCAN_SESSION_DATE, and both are knowable before
    the run spends anything.

    It is NOT presented as the session that was read — src.emailer._funnel_line
    relabels it on a failed run — because nothing read it. Best effort, like
    everything else on this path: a run that died inside ScanConfig() (a
    malformed SCAN_SESSION_DATE is exactly that) still gets its email, with
    the session unrecorded, rather than losing the notice to a second failure.
    """
    try:
        return {"session": ledger.iso_date(expected_session(ScanConfig()))}
    except Exception:  # noqa: BLE001 — the notice matters more than the date on it
        log.warning("Could not name the session the run was attempting", exc_info=True)
        return {}


def notify_failure(run_type: str, report: RunReport, dry_run: bool) -> None:
    """Best-effort: mail the fact that the run died. Never raises.

    A run that fails mid-scan sends nothing, and nothing in an inbox looks
    exactly like a public holiday. This is the only stage allowed to swallow
    an exception, because the caller is already reporting one and a delivery
    failure must not replace it in the log.
    """
    if dry_run:
        log.info("DRY RUN — not mailing the failure notice")
        return
    undeliverable = missing_delivery_env()
    if undeliverable:
        log.error("Cannot mail the failure notice: %s unset. The only remaining "
                  "signal is this exit code.", ", ".join(undeliverable))
        return
    try:
        from .emailer import send_failure_notice
        send_failure_notice(run_type, report.errors, attempted_session())
    except Exception:  # noqa: BLE001 — see the docstring
        log.exception("Could not mail the failure notice either")


def main() -> None:
    p = argparse.ArgumentParser(description="4% Momentum Burst pipeline")
    # The choices come from the mode table, so a mode cannot exist in one and
    # not the other — the morning mode spent this whole rebuild being a name
    # the parser accepted and the code did nothing with.
    p.add_argument("run_type", choices=sorted(MODES),
                   help="evening: scan the session that closed today. "
                        "morning: re-present the last evening run before the open")
    p.add_argument("--dry-run", action="store_true", help="skip sending email")
    p.add_argument("--tickers", help="comma-separated tickers (testing only)")
    args = p.parse_args()

    if args.tickers and not mode_for(args.run_type).scans:
        # Refused rather than ignored. A flag that silently does nothing is how
        # a smoke test convinces someone they tested something they did not.
        p.error(f"--tickers is a scan option; the {args.run_type} run does not scan, "
                "it re-presents the run docs/data.json already holds")

    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else None
    report = RunReport()
    try:
        run(args.run_type, dry_run=args.dry_run, tickers=tickers, report=report)
    except Exception as e:  # noqa: BLE001 — recorded, mailed, then re-raised as an exit code
        log.exception("Pipeline failed during the %s stage", report.stage)
        report.fail(report.stage, e)
        report.log_summary(args.run_type)
        notify_failure(args.run_type, report, dry_run=args.dry_run)
        sys.exit(EXIT_FAILED)
    # Exit 2 when the run finished but cannot be trusted as a complete scan.
    # Actions has no other way to tell the difference, and a green tick on a
    # half-scanned market is how this project went a rebuild without noticing.
    sys.exit(report.exit_code)


if __name__ == "__main__":
    main()
