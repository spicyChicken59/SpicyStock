#!/usr/bin/env python3
"""The rehearsal the sandbox cannot run: every boundary that needs a socket, once.

Run this ON YOUR OWN MACHINE with the real keys in the environment, before the
first scheduled night:

    set -a; . ./.env; set +a
    python tools/live_check.py            # everything, ~$0.02 and one email
    python tools/live_check.py --no-spend # the free checks only
    python tools/live_check.py --only alpaca,clock

It drives the pipeline's OWN code paths -- scanner.get_clients() and
_download_batch(), scorer.score_candidate() over a chart render_chart() drew,
emailer.deliver() -- so a pass means the nightly run's own calls work, not
that some other call did. Each boundary is asked once, in isolation, with the
smallest spend that answers the question, and the failure messages are the
pipeline's own (a 401 is told apart from a 403 the way run_scan() tells them
apart), because the point is to see the first night's failure HERE, for cents,
instead of in the Actions log after a scan and twenty-five paid calls.

What it can settle that nothing else has: that the credentials query the feed;
which feed; that the feed carries today's session; that Claude accepts the
model name, returns something the parser reads, and honours cache_control;
that the cache actually HITS on a second call; and that Resend delivers from
RESEND_FROM. What it cannot settle: the commit-back push, which only Actions
can exercise -- and has, since 6 Sep 2026; its commits are in this branch's
history, one per published run.

Every line of this file is exercised offline in tests/test_live_check.py
through the same doubles the pipeline tests use, so the tool that checks the
first run has itself been checked.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from src import emailer, lynch, pipeline, scanner, scorer  # noqa: E402

#: A ticker every real universe carries and every plan can query. Only the
#: default -- --symbol overrides it -- and read off the checked-in list so
#: this file does not hard-code a name the universe may later drop.
DEFAULT_SYMBOL = "AAPL"

ALL_CHECKS = ("env", "clock", "alpaca", "claude", "cache", "resend")
#: The two that cost money or send mail. --no-spend skips exactly these.
SPENDING = ("claude", "cache", "resend")

TEST_SUBJECT = "SpicyStock live check — this is a test message, not a run"


@dataclass
class Check:
    name: str
    status: str            # "ok" | "FAIL" | "skip"
    detail: str
    spend: str = ""
    data: dict = field(default_factory=dict)   # what a later check may reuse

    @property
    def ok(self) -> bool:
        return self.status == "ok"


# ------------------------------------------------------------------ env ----
def check_env() -> Check:
    """The six variables, judged by the pipeline's own preflight rule."""
    evening = pipeline.missing_env(dry_run=False, run_type="evening")
    morning = pipeline.missing_env(dry_run=False, run_type="morning")
    optional = [] if os.environ.get("RESEND_FROM", "").strip() else ["RESEND_FROM"]
    if evening:
        return Check("env", "FAIL",
                     "missing or empty: " + ", ".join(evening)
                     + (f" (the morning run alone would still miss: {', '.join(morning)})"
                        if morning else " (the morning run has what it needs)"))
    note = ("RESEND_FROM is unset, so mail goes out from Resend's sandbox sender, "
            "which only delivers to the address that owns the Resend account"
            if optional else "all six set")
    return Check("env", "ok", note)


# ---------------------------------------------------------------- clock ----
def check_clock(now: datetime | None = None) -> Check:
    """Which session a run started now would scan, and which mode fits."""
    now = now or datetime.now(timezone.utc)
    session = scanner.current_session(now)
    closed = scanner.session_has_closed(now)
    et = now.astimezone(scanner.MARKET_TZ)
    mode = "evening" if closed else "morning"
    return Check("clock", "ok",
                 f"{et:%a %Y-%m-%d %H:%M} ET; an evening run now would scan {session}; "
                 f"the mode that fits this hour is '{mode}'"
                 + ("" if et.weekday() < 5 else " (weekend: a scheduled run would not fire)"),
                 data={"session": session})


# --------------------------------------------------------------- alpaca ----
def check_alpaca(symbol: str, cfg: scanner.ScanConfig | None = None) -> Check:
    """One bars request through the scan's own downloader, for one name.

    Reports the feed, whether the newest bar is the session the clock names,
    how many bars it dropped as duplicates when the response repeated a
    timestamp, and -- on refusal -- the same 401-versus-403 message run_scan()
    raises. A clean response says nothing about duplicates, the rule every
    other surface follows; the bar count is the de-duplicated frame's, because
    that is the frame the rules would read.
    """
    cfg = cfg or scanner.ScanConfig()
    session = cfg.session_date or scanner.current_session()
    # The third caller of the scan's downloader, and the one that reads the
    # LIVE feed -- so it is the likeliest place a first real duplicate is met,
    # and the bar count below is taken AFTER the de-dup. Counted here for the
    # same reason run_scan() and forward_bars() count it: the frame that comes
    # out cannot show it ever chose.
    duplicates: dict[str, int] = {}
    try:
        client = scanner.get_clients()
        bars = scanner._download_batch(client, [symbol], cfg, session, duplicates=duplicates)
    except Exception as e:  # noqa: BLE001 -- every kind is a finding here
        if scanner._is_permanent_refusal(e):
            return Check("alpaca", "FAIL", str(scanner._refusal_error(cfg.feed, e)))
        return Check("alpaca", "FAIL", f"{type(e).__name__}: {e} (feed {cfg.feed.value!r})")
    frame = bars.get(symbol)
    if frame is None or frame.empty:
        return Check("alpaca", "FAIL",
                     f"the {cfg.feed.value!r} feed accepted the request and returned no bars "
                     f"for {symbol} -- a name the plan cannot see, or a feed with nothing in "
                     "this window")
    newest = scanner._last_bar_date(frame)
    fresh = newest == session
    dropped = duplicates.get(symbol, 0)
    detail = (f"{cfg.feed.value!r} feed OK: {len(frame)} bars for {symbol}, newest {newest}"
              + (f" -- {dropped} extra bar(s) dropped as duplicates, keeping the copy that "
                 "arrived last" if dropped else "")
              + ("" if fresh else f" -- BEHIND the session the clock names ({session}); "
                 "fine before today's close or on a holiday, and a stale feed otherwise"))
    return Check("alpaca", "ok", detail, data={"frame": frame, "fresh": fresh})


# --------------------------------------------------------------- claude ----
def _synthetic_burst():
    """A frame the checklist passes, for when Alpaca gave us nothing to draw."""
    from tests.synthetic import make_ohlcv  # a test helper, as tools/make_history.py does

    return make_ohlcv("burst", seed=7, up_run=1)


def _candidate(ticker: str, frame) -> scanner.Candidate:
    """A Candidate off the frame's own last two bars, the shape score_candidate() takes.

    Not detect_setup(): a real name's last bar is usually not a burst, and the
    question here is whether the MODEL boundary works, not whether the name
    set up tonight.
    """
    last, prev = frame.iloc[-1], frame.iloc[-2]
    avg = float(frame["Volume"].iloc[-51:-1].mean()) or 1.0
    return scanner.Candidate(
        ticker=ticker, date=str(scanner._last_bar_date(frame)),
        close=float(last["Close"]),
        gain_pct=round((float(last["Close"]) / float(prev["Close"]) - 1) * 100, 2),
        volume=int(last["Volume"]), prev_volume=int(prev["Volume"]),
        volume_ratio=round(float(last["Volume"]) / avg, 2), avg_volume=int(avg),
        dollar_volume=float(last["Close"]) * float(last["Volume"]),
        history=frame,
    )


def check_claude(frame=None, ticker: str = "SYNTHETIC", out_dir: str | None = None) -> Check:
    """One real scoring call over one real chart, through score_candidate().

    A fallback is a FAIL here even though the pipeline survives one: this is
    the check that the key, the model name and the parser all work, and a
    fallback means at least one of them does not.

    NO STREAK IS PASSED, and that is deliberate: this tool has no ledger and
    inventing a record block would make the one request that reaches the live
    endpoint the one request the pipeline never sends. What it sends instead
    is the state src.scorer names -- a null `setup_day` under
    src.ledger.NO_STREAK_RECORDED -- which is a shape the rulebook defines.
    Until round 11 it was a null day with a null REASON, under a system prompt
    promising that could not happen.
    """
    if frame is None or len(frame) < 85:
        frame, ticker, source = _synthetic_burst(), "SYNTHETIC", "a synthetic chart"
    else:
        source = f"a real chart of {ticker}"
    out_dir = out_dir or tempfile.mkdtemp(prefix="spicystock-live-")
    try:
        chart = scorer.render_chart(ticker, frame, out_dir=out_dir)
    except Exception as e:  # noqa: BLE001
        return Check("claude", "FAIL", f"the chart could not be rendered: {type(e).__name__}: {e}")
    cand = _candidate(ticker, frame)
    result = lynch.evaluate_2lynch(frame)
    context = lynch.extra_context(frame)
    usage: dict = {}
    row = scorer.score_candidate(cand, result, context, chart, usage=usage)
    prov = row["provenance"]
    if prov["source"] != "claude":
        return Check("claude", "FAIL",
                     f"fell back to the checklist: {prov.get('error')}", spend="paid for the attempts",
                     data={"usage": usage})
    cached = usage.get("cache_write", 0)
    detail = (f"{prov['model']} scored {source}: {row['score']}/10 {row['verdict']}; "
              + (f"cache_control accepted ({cached} tokens written)" if cached
                 else "but NO cached prefix was written -- caching is not taking effect"))
    return Check("claude", "ok" if cached else "FAIL", detail, spend="one scoring call",
                 data={"usage": usage, "inputs": (cand, result, context, chart)})


def check_cache(inputs) -> Check:
    """A second identical call. The first wrote the prefix; this one must read it.

    Without this the 50% cheaper a cached night is meant to be is a comment in
    request_kwargs(), not a fact: a system prompt edited below the minimum
    cacheable size, or an account the feature is off for, pays full price
    forever and nothing says so.
    """
    cand, result, context, chart = inputs
    usage: dict = {}
    row = scorer.score_candidate(cand, result, context, chart, usage=usage)
    if row["provenance"]["source"] != "claude":
        return Check("cache", "FAIL", f"the second call fell back: {row['provenance'].get('error')}",
                     spend="paid for the attempts")
    read = usage.get("cache_read", 0)
    if read:
        return Check("cache", "ok", f"the second call read {read} tokens from cache",
                     spend="one scoring call, mostly cached")
    return Check("cache", "FAIL",
                 f"the second call read nothing from cache (wrote {usage.get('cache_write', 0)}); "
                 "every night will pay full price for the system prompt 25 times",
                 spend="one scoring call")


# --------------------------------------------------------------- resend ----
def check_resend(now: datetime | None = None) -> Check:
    """One plainly labelled message through the pipeline's only send path."""
    now = now or datetime.now(timezone.utc)
    html = ("<p>This is <b>SpicyStock's live check</b>, sent by tools/live_check.py at "
            f"{now:%Y-%m-%d %H:%M} UTC from <code>{emailer.esc(emailer.sender_address())}</code>. "
            "It is not a run and carries no candidates. If you are reading it, delivery works.</p>")
    try:
        response = emailer.deliver(TEST_SUBJECT, html, [])
    except Exception as e:  # noqa: BLE001
        return Check("resend", "FAIL",
                     f"{type(e).__name__}: {e} (from {emailer.sender_address()!r}). An unverified "
                     "sender domain is the usual cause; the nightly run would exit 3 on it, "
                     "keeping its record but mailing nothing", spend="")
    return Check("resend", "ok",
                 f"delivered from {emailer.sender_address()!r}, id={response.get('id')}",
                 spend="one email")


# ------------------------------------------------------------- the run ----
def run_checks(only: tuple[str, ...] | None = None, spend: bool = True,
               symbol: str = DEFAULT_SYMBOL, now: datetime | None = None) -> list[Check]:
    """Every check, in dependency order, with the skips said out loud."""
    wanted = set(only or ALL_CHECKS)
    checks: list[Check] = []

    # --no-spend must leave a SKIP row for each paid check, not drop the check
    # from the plan: the first version did the latter, and render() then saw
    # nothing skipped and printed READY over a run that had tried neither
    # Claude nor Resend. A verdict that cannot tell "passed" from "not tried"
    # is the confidently false sentence, in the tool meant to prevent one.
    def unpaid(name: str) -> Check | None:
        if spend or name not in SPENDING:
            return None
        return Check(name, "skip", "not attempted: --no-spend")

    env = check_env()
    if "env" in wanted:
        checks.append(env)
    if "clock" in wanted:
        checks.append(check_clock(now))

    def needs(names: tuple[str, ...]) -> str | None:
        missing = pipeline._absent(names)
        return ", ".join(missing) if missing else None

    frame, ticker = None, symbol
    if "alpaca" in wanted:
        gap = needs(scanner.REQUIRED_ENV)
        if gap:
            checks.append(Check("alpaca", "skip", f"not attempted: {gap} unset"))
        else:
            c = check_alpaca(symbol)
            checks.append(c)
            frame = c.data.get("frame")

    inputs, claude_row = None, None
    if "claude" in wanted:
        gap = needs(scorer.REQUIRED_ENV)
        if unpaid("claude"):
            checks.append(unpaid("claude"))
        elif gap:
            checks.append(Check("claude", "skip", f"not attempted: {gap} unset"))
        else:
            c = check_claude(frame, ticker)
            checks.append(c)
            inputs = c.data.get("inputs")
        claude_row = checks[-1]
    if "cache" in wanted:
        if unpaid("cache"):
            checks.append(unpaid("cache"))
        elif inputs is None:
            # Two different reasons, said apart: the first call was never made,
            # or it was made and failed. "did not succeed" covered both and was
            # wrong about the first, which is the state a machine with no keys
            # is always in.
            why = ("the first scoring call was not made" if claude_row is None or claude_row.status == "skip"
                   else "the first scoring call failed")
            checks.append(Check("cache", "skip", f"not attempted: {why}"))
        else:
            checks.append(check_cache(inputs))

    if "resend" in wanted:
        gap = needs(emailer.REQUIRED_ENV)
        if unpaid("resend"):
            checks.append(unpaid("resend"))
        elif gap:
            checks.append(Check("resend", "skip", f"not attempted: {gap} unset"))
        else:
            checks.append(check_resend(now))

    for name in ALL_CHECKS:
        if name in wanted and name not in {c.name for c in checks}:
            checks.append(Check(name, "skip", "not attempted"))
    for name in (set(only or ()) - set(ALL_CHECKS)):
        checks.append(Check(name, "skip", f"no such check; the checks are {', '.join(ALL_CHECKS)}"))
    return checks


def render(checks: list[Check]) -> str:
    width = max(len(c.name) for c in checks)
    lines = [f"  {c.status:4s}  {c.name:{width}s}  {c.detail}" + (f"  [{c.spend}]" if c.spend else "")
             for c in checks]
    failed = [c for c in checks if c.status == "FAIL"]
    skipped = [c for c in checks if c.status == "skip"]
    if failed:
        verdict = (f"NOT READY: {len(failed)} check(s) failed -- "
                   + ", ".join(c.name for c in failed))
    elif skipped and any(s.name in SPENDING for s in skipped):
        verdict = ("the free checks pass; the paid boundaries were not tried "
                   f"({', '.join(c.name for c in skipped)})")
    else:
        verdict = "READY for the first scheduled run -- watch its 'Persist the run' step, the one thing this cannot try"
    return "\n".join(lines) + "\n\n" + verdict


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--only", help="comma-separated subset of: " + ", ".join(ALL_CHECKS))
    p.add_argument("--no-spend", action="store_true",
                   help="skip the checks that cost money or send mail: " + ", ".join(SPENDING))
    p.add_argument("--symbol", default=DEFAULT_SYMBOL, help="the one name to ask Alpaca for")
    args = p.parse_args(argv)
    only = tuple(s.strip() for s in args.only.split(",") if s.strip()) if args.only else None
    checks = run_checks(only=only, spend=not args.no_spend, symbol=args.symbol.upper())
    print(render(checks))
    return 1 if any(c.status == "FAIL" for c in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
