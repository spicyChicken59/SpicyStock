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

from .lynch import evaluate_2lynch, extra_context
from .scanner import ScanConfig, run_scan
from .scorer import render_chart, score_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pipeline")

TOP_N = 5
MIN_LYNCH_PASSES = 3
MAX_TO_SCORE = 25  # cap Claude calls per run

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
    """One run, start to finish. Returns the shortlist that went out.

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
    gated = [p for p in prepared if p[1]["passes"] >= MIN_LYNCH_PASSES][:MAX_TO_SCORE]
    log.info("%d bursts → %d passed 2LYNCH gate (scoring top %d)",
             n_bursts, sum(1 for p in prepared if p[1]["passes"] >= MIN_LYNCH_PASSES), len(gated))

    # Layers 3-5: charts + Claude scoring
    report.stage = "chart"
    scored_inputs = []
    chart_failures: list[str] = []
    for cand, lynch, ctx in gated:
        chart = None
        try:
            chart = render_chart(cand.ticker, cand.history)
        except Exception as e:  # noqa: BLE001
            # Survivable — the candidate is still scored — but not free: the
            # model is told to trust the chart over the numbers, and without
            # one it is scoring blind. provenance.chart_seen records that per
            # row; this records that the run had to do it at all.
            log.warning("Chart render failed for %s: %s", cand.ticker, e)
            chart_failures.append(f"{cand.ticker} ({type(e).__name__}: {e})")
        scored_inputs.append((cand, lynch, ctx, chart))
    if chart_failures:
        report.problem("chart", f"{len(chart_failures)} of {len(gated)} charts failed to "
                                "render; those candidates were scored without the image: "
                                + ", ".join(chart_failures[:5]))

    report.stage = "score"
    score_stats: dict = {}
    results = score_all(scored_inputs, top_n=TOP_N, min_lynch=MIN_LYNCH_PASSES,
                        stats=score_stats)
    _check_scoring(score_stats, report)

    # Report the universe actually scanned. This said "US common stocks" while
    # the scan had been narrowed to a checked-in list, so the daily email
    # described a market it no longer looks at. The count comes from the scan
    # that just ran rather than from a second read of the symbol file, which
    # could disagree with it.
    scanned = scan_stats.get("requested", len(tickers or []))
    report.counts.update({"universe": scanned, "bursts": n_bursts, "gated": len(gated),
                          **{k: v for k, v in scan_stats.items() if k != "stale"},
                          "stale": len(scan_stats.get("stale", {})),
                          "scored": score_stats.get("scored", 0),
                          "claude": score_stats.get("claude", 0),
                          "fallback": score_stats.get("fallback", 0)})
    stats = report.email_stats(
        universe=f"{scanned} checked-in US common stocks",
        bursts=n_bursts, gated=len(gated),
        scored_by={"claude": score_stats.get("claude", 0),
                   "fallback": score_stats.get("fallback", 0)},
    )

    report.stage = "archive"
    path = archive(results, run_type)
    log.info("Archived shortlist to %s", path)

    # Layer 6: email. A degraded run still sends. Suppressing it would replace
    # a misleading email with no email, and no email is the failure this step
    # exists to end — the operator cannot tell it from a market holiday. It
    # goes out marked instead: DEGRADED in the subject, the reasons in a band
    # above the table.
    report.stage = "email"
    if dry_run:
        log.info("DRY RUN — skipping email. Shortlist:")
        for r in results:
            log.info("  %s  %s/10 (%s) %s", r["ticker"], r["score"], r["verdict"], r["reason"])
    else:
        from .emailer import send_email
        send_email(results, run_type, stats)

    report.stage = "complete"
    report.log_summary(run_type)
    return results


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
