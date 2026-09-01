"""
Orchestrator — ties all layers together. Two modes:

  evening : scan today's completed session → candidates to watch TOMORROW
  morning : re-scan the most recent completed session (yesterday) →
            follow-through watchlist for TODAY

Both modes are stateless and fully automated:
  scan → 2LYNCH gate → chart render → Claude scoring → email → CSV archive

Usage:  python -m src.pipeline morning|evening [--dry-run] [--tickers AAPL,MSFT]

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
from datetime import datetime, timezone
from pathlib import Path

from . import ledger, scanner
from .lynch import evaluate_2lynch, extra_context
from .scanner import ScanConfig, run_scan
from .scorer import MODEL as DEFAULT_MODEL
from .scorer import render_chart, score_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pipeline")

TOP_N = 5          # how many candidates the EMAIL carries. Not the archive.
MIN_LYNCH_PASSES = 3
MAX_TO_SCORE = 25  # cap Claude calls per run

#: Where render_chart() writes. Under docs/ because GitHub Pages serves that
#: directory and docs/index.html references a chart as a path relative to
#: itself: a PNG in the repo-root charts/ can be named by the dashboard and
#: never fetched by it, and that directory is gitignored besides, so the image
#: died with the runner. See ledger.chart_ref() for the other half.
CHARTS_DIR = ledger.DOCS_DIR / "charts"

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


def missing_env(dry_run: bool = False) -> list[str]:
    """Which required environment variables are absent or empty.

    Composed from each layer's own REQUIRED_ENV rather than listed here, so a
    layer that starts needing a new key cannot be preflighted against a stale
    copy of its requirements.

    Empty counts as missing. GitHub Actions passes an unset secret as '' , so
    every one of these would otherwise sail through an `in os.environ` check
    and fail as somebody else's 401 halfway through the run.
    """
    from .emailer import REQUIRED_ENV as EMAIL_ENV
    from .scanner import REQUIRED_ENV as SCAN_ENV
    from .scorer import REQUIRED_ENV as SCORE_ENV

    # --dry-run skips only delivery, so it still needs data and scoring keys.
    required = list(SCAN_ENV) + list(SCORE_ENV) + ([] if dry_run else list(EMAIL_ENV))
    return _absent(required)


def preflight(dry_run: bool = False) -> None:
    """Refuse to start a run that cannot finish. Raises PreflightError.

    Reports EVERY missing variable, not the first: an operator setting this up
    should get one list, not one round trip per key.
    """
    missing = missing_env(dry_run)
    if missing:
        raise PreflightError(
            "missing or empty required environment: " + ", ".join(missing)
            + ". Nothing has been spent — checked before the scan rather than "
            "after it. See .env.example."
        )
    log.info("Preflight OK%s", " (dry run: delivery keys not required)" if dry_run else "")


def archive(results: list[dict], run_type: str) -> Path:
    """The run's CSV, in results/ — every scored candidate, not the shortlist.

    It is handed `scored`, not the five rows that went out by email. Until step
    9 the caller passed score_all()'s truncated return, so TOP_N cut this file
    as well as the email and the other twenty judgements a run made were never
    written down anywhere. results/ is gitignored and uploaded as a 30-day
    workflow artifact; the durable record is docs/ledger.json.
    """
    out = Path("results")
    out.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = out / f"{stamp}_{run_type}.csv"
    cols = ["ticker", "date", "close", "gain_pct", "volume_ratio",
            "lynch", "score", "verdict", "reason", "key_risk"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)
    return path


def run(run_type: str, dry_run: bool = False, tickers: list[str] | None = None,
        report: RunReport | None = None) -> list[dict]:
    """One run, start to finish. Returns EVERY scored candidate, ranked.

    Not the five that went out by email: those are `scored[:TOP_N]`, cut here
    rather than inside score_all(), because the truncated list used to be the
    only thing this function ever produced and archive() wrote exactly it.

    `report`, if given, is filled with everything the shortlist cannot say:
    which stage was running, what went wrong, and the counts behind it. main()
    passes one in and exits on its code. A caller that does not pass one still
    gets the same log lines and the same email — the report is built either
    way; the argument only lets the caller read it.
    """
    report = report if report is not None else RunReport()
    cfg = ScanConfig()
    log.info("=== %s run starting ===", run_type)

    report.stage = "preflight"
    preflight(dry_run)

    # Layer 1: scan. Alpaca returns bars only up to the session the scan
    # targets, so an evening run sees today's close and a morning run sees
    # yesterday's; src.scanner drops anything that does not carry it.
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
    passed_gate = [p for p in prepared if p[1]["passes"] >= MIN_LYNCH_PASSES]
    to_score = passed_gate[:MAX_TO_SCORE]
    # Everything the scan found that will not be scored, with the reason it
    # was not. Kept rather than dropped: docs/data.json's contract is that
    # scored + gated_out accounts for every burst, and a per-check pass rate
    # computed over the survivors alone describes the survivors, not the run.
    scoring = {cand.ticker for cand, _lynch, _ctx in to_score}
    unscored = [(cand, lynch,
                 "lynch_gate" if lynch["passes"] < MIN_LYNCH_PASSES else "score_cap")
                for cand, lynch, _ctx in prepared if cand.ticker not in scoring]
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
        scored_by={"claude": score_stats.get("claude", 0),
                   "fallback": score_stats.get("fallback", 0)},
    )

    report.stage = "archive"
    path = archive(scored, run_type)
    log.info("Archived %d scored candidate(s) to %s", len(scored), path)
    published = publish(run_type=run_type, dry_run=dry_run, cfg=cfg, report=report,
                        scan_stats=scan_stats, score_stats=score_stats,
                        scored=scored, unscored=unscored, to_score=to_score,
                        n_bursts=n_bursts, n_passed=len(passed_gate),
                        shortlist_size=len(shortlist), chart_errors=chart_errors,
                        explicit_tickers=tickers)
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
            explicit_tickers: list[str] | None) -> dict:
    """Write docs/data.json and docs/ledger.json for the run that just ran.

    Everything the run knows, in the two shapes it is worth keeping: the
    dashboard's snapshot of tonight, and the ledger row per candidate that a
    later run fills a forward return into. See src.ledger.

    A failure to FETCH those later bars degrades the run rather than ending
    it — the scoring is done and the email is still worth sending — but it is
    reported, because a ledger that silently stops accumulating outcomes is
    the same class of failure step 5 exists to end.
    """
    by_ticker = {cand.ticker: (cand, lynch, ctx) for cand, lynch, ctx in to_score}
    candidates = []
    for rank, row in enumerate(scored, start=1):
        cand, lynch, ctx = by_ticker[row["ticker"]]
        candidates.append(ledger.candidate_record(
            cand, lynch, ctx, row, rank=rank, docs_dir=ledger.DOCS_DIR,
            chart_error=chart_errors.get(row["ticker"])))
    gated_out = [ledger.gated_record(cand, lynch, reason)
                 for cand, lynch, reason in unscored]

    session = scan_stats.get("session")
    # The gate's own size, read off the checklist this run computed rather
    # than copied from src.lynch as a number that could drift out of step.
    # None on a night with no bursts, because then nothing measured it.
    total_checks = next((lynch["total"] for _c, lynch, _x in to_score), None)
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
        "gate": {"min_lynch_passes": MIN_LYNCH_PASSES, "total_checks": total_checks},
        "scored_by": {"claude": score_stats.get("claude", 0),
                      "fallback": score_stats.get("fallback", 0)},
        "model": next((r["provenance"]["model"] for r in scored
                       if r["provenance"].get("model")), None) or DEFAULT_MODEL,
        "status": report.status,
        "errors": list(report.errors),
    }

    book = ledger.Ledger(ledger.DOCS_DIR).load()
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
        send_failure_notice(run_type, report.errors)
    except Exception:  # noqa: BLE001 — see the docstring
        log.exception("Could not mail the failure notice either")


def main() -> None:
    p = argparse.ArgumentParser(description="4% Momentum Burst pipeline")
    p.add_argument("run_type", choices=["morning", "evening"])
    p.add_argument("--dry-run", action="store_true", help="skip sending email")
    p.add_argument("--tickers", help="comma-separated tickers (testing only)")
    args = p.parse_args()

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
