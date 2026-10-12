#!/usr/bin/env python3
"""The service's failures, rehearsed through the doubles, and its recovery.

#111 asks the service to "rehearse provider, reader and publication failures;
recover idempotently without duplicate work, stale overwrite or unbounded
calls". This drives ``pipeline.run_evening()`` -- the real evening, every
stage -- through the same doubles the suite and the fixture generator use
(``tests.fakes``: the Alpaca client, the Anthropic client, Resend), one pinned
night after another over one small synthetic market, breaking one boundary a
night, and before and after each night asks the evening workflow's OWN guard
(the Python body of ``evening.yml``'s guard step, executed as written under a
frozen clock) what a scheduled slot would do. It records what each night did:
the exit code, the status, whether a publication was written and for which
session, whether the previous publication's files survived byte for byte, how
many times each boundary was asked, what was mailed, and what the guard
decided at the primary slot, the retry slot, the next open and a delayed
event. It decides nothing, changes no rule and calls no provider; it writes
two files under OUT_DIR, and ``--check`` runs the whole rehearsal again and
holds both.

What a rehearsal is and is not: the market is synthetic and every failure is
injected, so it shows that the code does what it says under a failure it was
told to have. It does not show that a real provider fails that way, that a
runner starts on time, or that GitHub accepts the commit.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import datetime as datetime_module
import hashlib
import io
import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from src import charts, funnel, grader, market_data, pipeline  # noqa: E402
from tests.fakes import FakeAlpaca, FakeAnthropic, FakeDataClient, FakeResend  # noqa: E402
from tests.synthetic import make_ohlcv  # noqa: E402
from tests.test_quality import frame as qframe, ideal_bars  # noqa: E402
from tests.test_watchlist import coil  # noqa: E402

VERSION = 1
POLICY = "recovery_rehearsal_v1"
OUT_DIR = ROOT / "docs" / "input-truthfulness" / "2026-10-12-recovery-rehearsal-evidence"
OUTPUT_JSON = OUT_DIR / "rehearsal.json"
OUTPUT_MD = OUT_DIR / "rehearsal.md"
WORKFLOW = ROOT / ".github" / "workflows" / "evening.yml"
SEED = 20261012
#: the synthetic provider's precision, as the fixture generator rounds it: a
#: rehearsal must reproduce on every CPU dispatch path (see #71's drift)
INPUT_DECIMALS = {"Open": 8, "High": 8, "Low": 8, "Close": 8, "Volume": 0}
#: the evening cron's two EDT slots, as evening.yml spells them
PRIMARY_CRON = "16 22 * * 1-5"
RETRY_CRON = "16 0 * * 2-6"
#: download_bars tries a failed batch once more (market_data.RETRY_WAIT_SECONDS
#: between), then drops it: two attempts a batch is the fetch's own bound
BARS_ATTEMPTS_PER_BATCH = 2
#: the clock fields a record carries that are wall-clock facts, not market facts
CLOCK_FIELDS = ("elapsed_seconds", "fetch_seconds")
#: how the empty balance and a dead transport announce themselves; the first
#: text is what the provider answered on 6 October 2026 (grader.FATAL_CREDIT_MARKERS)
CREDIT_ERROR = ("Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
                "'message': 'Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.'}}")
TRANSPORT_ERROR = "upstream connect error or disconnect/reset before headers"
PROVIDER_ERROR = "no route to host"
RESEND_ERROR = "Resend refused the request"
#: the reader's reply for an A+ chart, in the rubric's shape (the suite's own)
READER_REPLY = {"score": 9.2, "grade": "A+", "reason": "a clean leg into a tight base and a 6% burst that closed at its high",
                "key_risk": "the gap at the open", "entry_note": "skip it above the ceiling"}
PNG_1X1 = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j8WQAAAAASUVORK5CYII=")
ENV = {"ALPACA_API_KEY": "rehearsal-not-a-key", "ALPACA_SECRET_KEY": "rehearsal-not-a-secret",
       "ANTHROPIC_API_KEY": "rehearsal-not-a-key", "RESEND_API_KEY": "rehearsal-not-a-key",
       "RESEND_FROM": "rehearsal@example.invalid", "EMAIL_TO": "owner@example.invalid",
       "SCAN_SEND_EMAIL": "true", "MPLBACKEND": "Agg", "CLAUDE_MODEL": "claude-sonnet-4-6"}
#: variables a real runner may carry that would change the record
UNSET = ("SCAN_SESSION_DATE", "ACCOUNT_EQUITY", "RISK_PCT", "GITHUB_RUN_ID_FOR_RECORD", "SCAN_DRY_RUN",
         "SCAN_INPUT_DIAGNOSTICS", "UNIVERSE_SOURCE", "ALPACA_FEED")

#: one night after another, each injecting one failure (or none); every clock
#: is pinned, EDT throughout (September 2026), and 7 September is Labor Day
SCENARIOS = (
    {"name": "clean", "at": "2026-09-04T22:30:00+00:00", "session": "2026-09-04", "inject": "none",
     "words": "a clean night: every boundary answers"},
    {"name": "holiday", "at": "2026-09-07T22:30:00+00:00", "session": None, "inject": "none",
     "words": "Labor Day: the calendar says no session, so nothing is fetched, asked, written or mailed"},
    {"name": "provider_outage", "at": "2026-09-08T22:30:00+00:00", "session": "2026-09-08", "inject": "bars_raise",
     "words": "the bars endpoint refuses every batch"},
    {"name": "provider_recovered_at_retry", "at": "2026-09-09T00:30:00+00:00", "session": "2026-09-08", "inject": "none",
     "words": "the retry slot, 8:30 PM ET the same evening: the provider answers again"},
    {"name": "reader_credit", "at": "2026-09-09T22:30:00+00:00", "session": "2026-09-09", "inject": "reader_credit",
     "words": "the reader's account has no credit left"},
    {"name": "reader_transport", "at": "2026-09-10T22:30:00+00:00", "session": "2026-09-10", "inject": "reader_transport",
     "words": "the reader's transport fails on every call"},
    {"name": "email_failed", "at": "2026-09-11T22:30:00+00:00", "session": "2026-09-11", "inject": "resend_raise",
     "words": "the record publishes and the mail provider refuses the digest"},
    {"name": "stale_feed", "at": "2026-09-14T22:30:00+00:00", "session": "2026-09-14", "inject": "stale_every_name",
     "words": "every frame the provider serves ends two sessions back"},
    {"name": "next_session_after_a_missed_night", "at": "2026-09-15T22:30:00+00:00", "session": "2026-09-15", "inject": "none",
     "words": "the night after a missed one: every boundary answers again"},
)
INJECTIONS = {
    "none": "nothing injected",
    "bars_raise": f"the Alpaca double raises ConnectionError({PROVIDER_ERROR!r}) on every bars request",
    "reader_credit": "the Anthropic double raises the provider's empty-balance error on every call",
    "reader_transport": f"the Anthropic double raises RuntimeError({TRANSPORT_ERROR!r}) on every call",
    "resend_raise": f"the Resend double raises RuntimeError({RESEND_ERROR!r}) on every send",
    "stale_every_name": "every registered frame, the benchmark's included, is served two sessions stale",
}


class RehearsalError(RuntimeError):
    """The rehearsal could not be run as written; nothing is recorded."""


# ------------------------------------------------------------------ market ---
def market(seed: int = SEED) -> dict[str, pd.DataFrame]:
    """The suite's own night, plus a second A+ burst: two names the reader is
    asked about, one coiled name, eleven quiet names and the benchmark."""
    frames = {"AAA": qframe(ideal_bars(burst_range_pct=0.25, base_range=0.15, prior_range=0.1)),
              "AAB": qframe(ideal_bars(burst_range_pct=0.35, base_range=0.15, prior_range=0.1)),
              "COIL": coil()}
    for i in range(11):
        letter = chr(65 + i)
        frames[f"B{letter}{letter}"] = make_ohlcv("base", seed=[seed, i], days=260)
    frames["SPY"] = make_ohlcv("base", seed=[seed, 999], days=260)
    return {name: df.round(INPUT_DECIMALS) for name, df in frames.items()}


def register(fake: FakeAlpaca, frames: dict[str, pd.DataFrame], *, stale_sessions: int = 0) -> None:
    for name, df in frames.items():
        fake.add_history(name, df, stale_sessions=stale_sessions)


# ------------------------------------------------------------------- guard ---
def guard_source() -> str:
    """The Python body of evening.yml's guard step, exactly as the workflow runs it."""
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    step = next((s for s in wf["jobs"]["scan"]["steps"] if s.get("id") == "guard"), None)
    if step is None:
        raise RehearsalError("evening.yml has no step with id guard")
    run = step["run"]
    if "python - <<'PY'\n" not in run or "\nPY" not in run:
        raise RehearsalError("the guard step is not the heredoc this rehearsal knows how to execute")
    return run.split("python - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]


def guard(root: Path, at: str, cron: str, code: str) -> dict:
    """What the scheduled guard decides at `at` (UTC, offset-aware) for a slot
    `cron`, over the docs/data.json under `root` -- run as written, with the
    clock frozen and nothing else."""
    instant = datetime.fromisoformat(at)
    if instant.tzinfo is None:
        raise RehearsalError(f"guard clock {at!r} has no offset")
    real = datetime_module.datetime

    class Frozen(real):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    printed = io.StringIO()
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "github-output"
        env = {"SCAN_EVENT_NAME": "schedule", "SCAN_EVENT_SCHEDULE": cron, "SCAN_REQUESTED_SESSION": "",
               "GITHUB_OUTPUT": str(output)}
        try:
            os.chdir(root)
            datetime_module.datetime = Frozen
            with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(printed):
                exec(compile(code, "evening.yml scheduled guard", "exec"), {})
        finally:
            datetime_module.datetime = real
            os.chdir(cwd)
        fields = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())
    if set(fields) != {"go", "session"} or fields["go"] not in ("true", "false"):
        raise RehearsalError(f"the guard wrote {fields!r}")
    return {"at": at, "cron": cron, "go": fields["go"] == "true", "session": fields["session"] or None,
            "reason": printed.getvalue().strip()}


def slot_checks(scenario: dict) -> list[tuple[str, str, str]]:
    """(label, clock, cron) the guard is asked, before and after this night."""
    at = datetime.fromisoformat(scenario["at"])
    day = at.date()
    if scenario["name"] == "provider_recovered_at_retry":
        # the retry slot itself ran this one; after it, the same slot again and
        # a primary event for the same evening that GitHub delivered late
        return [("before: the retry slot", "2026-09-09T00:20:00+00:00", RETRY_CRON),
                ("after: the retry slot again", "2026-09-09T01:00:00+00:00", RETRY_CRON),
                ("after: a delayed primary event for the same evening", "2026-09-09T00:40:00+00:00", PRIMARY_CRON),
                ("after: a delayed retry event for the 4 September slot (a synthetic clock, to show the rule)",
                 "2026-09-05T06:00:00+00:00", RETRY_CRON)]
    before = f"{day.isoformat()}T22:20:00+00:00"
    retry = f"{(day + datetime_module.timedelta(days=1)).isoformat()}T00:20:00+00:00"
    checks = [("before: the primary slot", before, PRIMARY_CRON), ("after: the retry slot", retry, RETRY_CRON)]
    if scenario["inject"] in ("bars_raise", "stale_every_name"):
        checks.append(("after: the next session's open, with nothing recovered",
                       f"{(day + datetime_module.timedelta(days=1)).isoformat()}T13:30:00+00:00", RETRY_CRON))
    return checks


# ---------------------------------------------------------------- the night ---
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snapshot(docs: Path) -> dict[str, str]:
    if not docs.exists():
        return {}
    return {str(p.relative_to(docs)).replace(os.sep, "/"): sha256(p.read_bytes()) for p in docs.rglob("*") if p.is_file()}


def identity(docs: Path) -> dict | None:
    """The publication's content, with the wall-clock fields nulled: two runs of
    this rehearsal write the same market and the same decisions, and nothing
    else of the record is a fact a rerun could change."""
    path = docs / pipeline.DATA_FILE
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in CLOCK_FIELDS:
        data.get("run", {})[key] = None
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    picks = docs / "picks.json"
    return {"data_json_without_clock_fields": sha256(canonical),
            "picks_json": sha256(picks.read_bytes()) if picks.exists() else None}


def record_facts(docs: Path) -> dict | None:
    path = docs / pipeline.DATA_FILE
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    run = data.get("run") or {}
    reads = run.get("reads") or {}
    stages = funnel.build(data)
    return {"session": run.get("session"), "status": run.get("status"), "email": run.get("email"),
            "published_at": run.get("published_at"), "problems": [p.get("kind") for p in run.get("problems") or []],
            "reads": {"requested": reads.get("requested"), "done": reads.get("done"), "verdict": reads.get("verdict"),
                      "causes": reads.get("causes")},
            "reader_usage": run.get("reader_usage"),
            "trades": list(data.get("trades") or []),
            "reaction_tickets": stages["reaction"]["stages"].get("ticket"),
            "anticipation_tickets": stages["anticipation"]["stages"].get("ticket"),
            "regime": stages.get("regime"), "cover": (data.get("cover") or {}).get("h1")}


def previous_outcome(before: dict[str, str], after: dict[str, str], *, published: bool) -> str:
    """What became of the files that were under docs before the night: `none`
    when there were none, `replaced` when the night published, `preserved` when
    it published nothing and every one of them is byte-identical still. A night
    that published nothing and changed a file is not recorded: it is refused."""
    if not before:
        return "none"
    if published:
        return "replaced"
    changed = sorted(k for k in before if after.get(k) != before[k])
    if changed:
        raise RehearsalError(f"a night that published nothing changed the previous publication: {changed}")
    return "preserved"


def bars_bound(symbols: int) -> int:
    """How many bars requests a night may make: one batch per
    min(FETCH_CHUNK, DEFAULT_BATCH_SIZE) symbols, each tried at most twice."""
    batch = min(pipeline.FETCH_CHUNK, market_data.DEFAULT_BATCH_SIZE)
    return -(-symbols // batch) * BARS_ATTEMPTS_PER_BATCH


class Night:
    """One scenario, run and measured."""

    def __init__(self, fake: FakeAlpaca, claude: type, resend: FakeResend, frames: dict, docs: Path, code: str) -> None:
        self.fake, self.claude, self.resend, self.frames, self.docs, self.code = fake, claude, resend, frames, docs, code

    def reset(self) -> None:
        self.fake.raise_on_bars = None
        self.claude.raises = None
        self.resend.raises = None
        register(self.fake, self.frames)

    def inject(self, kind: str) -> None:
        if kind == "bars_raise":
            self.fake.raise_on_bars = ConnectionError(PROVIDER_ERROR)
        elif kind == "reader_credit":
            self.claude.raises = RuntimeError(CREDIT_ERROR)
        elif kind == "reader_transport":
            self.claude.raises = RuntimeError(TRANSPORT_ERROR)
        elif kind == "resend_raise":
            self.resend.raises = RuntimeError(RESEND_ERROR)
        elif kind == "stale_every_name":
            register(self.fake, self.frames, stale_sessions=2)
        elif kind != "none":
            raise RehearsalError(f"unknown injection {kind!r}")

    def run(self, scenario: dict, root: Path) -> dict:
        self.reset()
        self.inject(scenario["inject"])
        before = snapshot(self.docs)
        before_identity = identity(self.docs)
        counts = (len(self.fake.bar_requests), len(self.claude.calls), len(self.resend.sent))
        checks = slot_checks(scenario)
        decisions = [dict(when=label, **guard(root, at, cron, self.code)) for label, at, cron in checks if label.startswith("before")]
        rep = pipeline.run_evening(tickers=[n for n in self.frames if n != pipeline.BENCHMARK_SYMBOL],
                                   docs=self.docs, now=datetime.fromisoformat(scenario["at"]))
        after = snapshot(self.docs)
        decisions += [dict(when=label, **guard(root, at, cron, self.code)) for label, at, cron in checks if label.startswith("after")]
        changed = sorted(set(k for k in set(before) | set(after) if before.get(k) != after.get(k)))
        requested = (record_facts(self.docs) or {}).get("reads", {}).get("requested") if rep.published else None
        reader_calls = len(self.claude.calls) - counts[1]
        try:
            outcome = previous_outcome(before, after, published=rep.published)
        except RehearsalError as exc:
            raise RehearsalError(f"{scenario['name']}: {exc}") from exc
        bars = len(self.fake.bar_requests) - counts[0]
        facts = {
            "name": scenario["name"], "words": scenario["words"], "clock": scenario["at"],
            "session": scenario["session"], "injected": INJECTIONS[scenario["inject"]],
            "run": {"exit_code": rep.exit_code(), "status": rep.status, "published": rep.published,
                    "failed": rep.failed, "failure": rep.failure, "skipped": rep.skipped, "stage": rep.stage,
                    "problems": [p.get("kind") for p in rep.problems],
                    "calendar_outcome": (rep.calendar_outcome or {}).get("outcome")},
            "calls": {"bars_requests": bars, "reader_calls": reader_calls,
                      "mails": len(self.resend.sent) - counts[2],
                      "mail_subjects": [m.get("subject") for m in self.resend.sent[counts[2]:]]},
            "previous": {"publication": before_identity, "outcome": outcome},
            "files_changed": len(changed),
            "bars_requests_bound": {"symbols": len(self.frames), "attempts_per_batch": BARS_ATTEMPTS_PER_BATCH,
                                    "maximum": bars_bound(len(self.frames)), "within": bars <= bars_bound(len(self.frames))},
            "publication": record_facts(self.docs) if rep.published else None,
            "publication_identity": identity(self.docs) if rep.published else None,
            "reader_calls_bound": {"requested": requested, "attempts": grader.ATTEMPTS,
                                   "maximum": (requested or 0) * grader.ATTEMPTS if requested is not None else None,
                                   "within": reader_calls <= (requested or 0) * grader.ATTEMPTS if requested is not None else reader_calls == 0},
            "guard": decisions,
        }
        return facts


def rehearse() -> dict:
    """Every scenario in order, over one market and one docs directory."""
    code = guard_source()
    frames = market()
    fake = FakeAlpaca()
    claude = type("RehearsalAnthropic", (FakeAnthropic,), {"calls": [], "payload": dict(READER_REPLY), "raw": None, "raises": None})
    resend = FakeResend()

    def render(ticker, df, out_dir, **kw):
        # a fixed PNG, as the fixture generator uses: the renderer is checked
        # by tests/test_charts.py, and its bytes are not a fact of this rehearsal
        target = Path(out_dir) / f"{ticker}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(PNG_1X1)
        return str(target)

    import anthropic
    import resend as resend_module
    env = dict(ENV)
    nights = []
    with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, env):
        for name in UNSET:
            os.environ.pop(name, None)
        root = Path(tmp)
        docs = root / "docs"
        with mock.patch.object(market_data, "StockHistoricalDataClient", lambda *a, **k: FakeDataClient(fake, *a, **k)), \
                mock.patch.object(anthropic, "Anthropic", claude), \
                mock.patch.object(resend_module.Emails, "send", lambda params, options=None: resend.send(params)), \
                mock.patch.object(resend_module, "api_key", None, create=True), \
                mock.patch.object(charts, "render_chart", render), \
                mock.patch.object(pipeline.grader, "MODEL", env["CLAUDE_MODEL"]):
            night = Night(fake, claude, resend, frames, docs, code)
            for scenario in SCENARIOS:
                nights.append(night.run(scenario, root))
    return {"version": VERSION, "policy": POLICY,
            "source": {"workflow": str(WORKFLOW.relative_to(ROOT)).replace(os.sep, "/"),
                       "guard_sha256": sha256(code.encode("utf-8")), "pipeline": "src/pipeline.py:run_evening",
                       "doubles": "tests/fakes.py", "seed": SEED, "attempts": grader.ATTEMPTS,
                       "market": {"names": sorted(n for n in frames if n != pipeline.BENCHMARK_SYMBOL),
                                  "benchmark": pipeline.BENCHMARK_SYMBOL, "reader_names": ["AAA", "AAB"]}},
            "nights": nights, "summary": summary(nights)}


def summary(nights: list[dict]) -> dict:
    published = [n for n in nights if n["run"]["published"]]
    failed = [n for n in nights if n["run"]["failed"] and not n["run"]["published"]]
    skipped = [n for n in nights if n["run"]["skipped"]]
    decisions = [d for n in nights for d in n["guard"]]
    kinds = {"permitted": 0, "already_published": 0, "newer_published": 0, "expired": 0, "not_a_session": 0, "other": 0}
    for d in decisions:
        if d["go"]:
            kinds["permitted"] += 1
        elif "already published" in d["reason"] and "newer" in d["reason"]:
            kinds["newer_published"] += 1
        elif "already published" in d["reason"]:
            kinds["already_published"] += 1
        elif "expired" in d["reason"]:
            kinds["expired"] += 1
        elif "not an exchange session" in d["reason"]:
            kinds["not_a_session"] += 1
        else:
            kinds["other"] += 1
    after_publication = [d for n in nights if n["run"]["published"] for d in n["guard"] if d["when"].startswith("after")]
    return {
        "nights": len(nights), "published": len(published), "failed_before_publishing": len(failed), "skipped": len(skipped),
        "sessions_published": sorted({n["publication"]["session"] for n in published}),
        "previous_preserved_on_every_night_that_published_nothing": all(
            n["previous"]["outcome"] in ("none", "preserved") for n in nights if not n["run"]["published"]),
        "previous_outcomes": {n["name"]: n["previous"]["outcome"] for n in nights},
        "exit_codes": {n["name"]: n["run"]["exit_code"] for n in nights},
        "reader_calls_within_bound_every_night": all(n["reader_calls_bound"]["within"] for n in nights),
        "bars_requests_within_bound_every_night": all(n["bars_requests_bound"]["within"] for n in nights),
        "reader_calls": {n["name"]: n["calls"]["reader_calls"] for n in nights},
        "bars_requests": {n["name"]: n["calls"]["bars_requests"] for n in nights},
        "mails": {n["name"]: n["calls"]["mails"] for n in nights},
        "guard": kinds,
        "slots_admitted_after_a_publication": sum(1 for d in after_publication if d["go"]),
        "slots_admitted_after_a_failure": sum(1 for n in failed for d in n["guard"] if d["when"].startswith("after") and d["go"]),
    }


# ----------------------------------------------------------------- output ---
def markdown(result: dict) -> str:
    s = result["summary"]
    lines = ["# The service's failures, rehearsed, and its recovery", "",
             f"Policy `{result['policy']}` (version {result['version']}). `pipeline.run_evening()` through the suite's doubles "
             f"(`{result['source']['doubles']}`) over one synthetic market of {len(result['source']['market']['names'])} names plus "
             f"`{result['source']['market']['benchmark']}`, seed {result['source']['seed']}; the evening workflow's guard "
             f"(`{result['source']['workflow']}`, SHA-256 `{result['source']['guard_sha256'][:12]}…`) executed as written under a frozen clock. "
             "Every failure is injected; nothing here is a live provider, a runner or GitHub.", "",
             "## Nights", "",
             "| night | session | clock (UTC) | injected | exit | status | published | previous publication | bars requests (bound) | reader calls (bound) | mails |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for n in result["nights"]:
        pub = n["publication"]
        bound = n["reader_calls_bound"]
        previous = n["previous"]["outcome"]
        bars = n["bars_requests_bound"]
        lines.append(f"| {n['name']} | {n['session'] or '—'} | {n['clock'][:16]} | {n['injected']} | {n['run']['exit_code']} | "
                     f"{n['run']['status']} | {'yes, ' + pub['session'] + ' (' + pub['status'] + ', mail ' + str(pub['email']) + ')' if pub else 'no'} | "
                     f"{previous} | {n['calls']['bars_requests']} (≤ {bars['maximum']}) | {n['calls']['reader_calls']} (≤ {bound['maximum'] if bound['maximum'] is not None else 0}) | "
                     f"{n['calls']['mails']} |")
    lines += ["", "## What each night did", ""]
    for n in result["nights"]:
        pub = n["publication"]
        lines.append(f"**{n['name']}** — {n['words']}. Exit {n['run']['exit_code']}, status `{n['run']['status']}`"
                     + (f", failed at `{n['run']['stage']}`: `{n['run']['failure']}`" if n["run"]["failure"] else "")
                     + (f"; problems {', '.join(n['run']['problems'])}" if n["run"]["problems"] else "")
                     + ". "
                     + (f"Published {pub['session']} ({pub['status']}; reads {pub['reads']['done']} of {pub['reads']['requested']}, "
                        f"verdict {pub['reads']['verdict']}; {pub['reaction_tickets']} reaction and {pub['anticipation_tickets']} anticipation ticket(s); "
                        f"cover \"{pub['cover']}\")." if pub else "Published nothing.")
                     + (f" Mailed: {'; '.join(repr(x) for x in n['calls']['mail_subjects'])}." if n["calls"]["mail_subjects"] else " Mailed nothing.")
                     + f" {n['files_changed']} file(s) under docs changed.")
        for d in n["guard"]:
            lines.append(f"- guard {d['when']} ({d['at'][:16]}, `{d['cron']}`): go={'true' if d['go'] else 'false'}"
                         + (f", session {d['session']}" if d["session"] else "") + f" — {d['reason']}")
        lines.append("")
    lines += ["## Summary", "",
              f"- {s['nights']} nights: {s['published']} published, {s['failed_before_publishing']} failed before publishing, {s['skipped']} skipped by the calendar.",
              f"- Sessions published: {', '.join(s['sessions_published'])}.",
              f"- The previous publication's files survived every night that published nothing: {'yes' if s['previous_preserved_on_every_night_that_published_nothing'] else 'NO'}.",
              f"- Bars requests within batches × {BARS_ATTEMPTS_PER_BATCH} attempts every night: {'yes' if s['bars_requests_within_bound_every_night'] else 'NO'}; by night: "
              + ", ".join(f"{k} {v}" for k, v in s["bars_requests"].items()) + ".",
              f"- Reader calls within names × {result['source']['attempts']} attempts every night: {'yes' if s['reader_calls_within_bound_every_night'] else 'NO'}; by night: "
              + ", ".join(f"{k} {v}" for k, v in s["reader_calls"].items()) + ".",
              f"- Guard decisions: {s['guard']['permitted']} permitted, {s['guard']['already_published']} refused as already published, "
              f"{s['guard']['newer_published']} refused because a newer session was published, {s['guard']['expired']} refused as expired at the next open, "
              f"{s['guard']['not_a_session']} refused as not a session, {s['guard']['other']} other.",
              f"- Scheduled slots the guard would have admitted after a publication: {s['slots_admitted_after_a_publication']} (duplicate work). "
              f"After a failure, before the next open: {s['slots_admitted_after_a_failure']} (recovery).", "",
              "The exit codes are the pipeline's own (0 clean, 1 failed before publishing, 2 degraded but published, 3 failed after publishing). "
              "A night that published nothing is proved by the bytes: every file under docs before the run is byte-identical after it (previous publication `preserved`); a night that published replaced them (`replaced`). "
              "Nothing here measures a real provider, a runner's start time or a commit landing."]
    return "\n".join(lines) + "\n"


def write(result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / OUTPUT_JSON.name).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / OUTPUT_MD.name).write_text(markdown(result), encoding="utf-8")


def check(out_dir: Path) -> list[str]:
    """The committed files are what the rehearsal writes, run again now."""
    problems = []
    try:
        committed = (out_dir / OUTPUT_JSON.name).read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{OUTPUT_JSON.name}: {exc}"]
    result = rehearse()
    if committed != json.dumps(result, indent=1, sort_keys=True) + "\n":
        problems.append(f"{OUTPUT_JSON.name} is not what the rehearsal writes")
    try:
        current_md = (out_dir / OUTPUT_MD.name).read_text(encoding="utf-8")
    except OSError as exc:
        return problems + [f"{OUTPUT_MD.name}: {exc}"]
    if current_md != markdown(result):
        problems.append(f"{OUTPUT_MD.name} is not what the rehearsal writes")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--check", action="store_true", help="run the rehearsal again and hold the committed files to it")
    args = parser.parse_args(argv)
    root = logging.getLogger()
    previous_level = root.level
    # the pipeline narrates every injected failure; the files carry the facts.
    # Quiet only for this command, and put back whatever level the caller had:
    # a test that calls main() must not leave later tests' warnings unheard.
    root.setLevel(logging.ERROR)
    try:
        if args.check:
            problems = check(args.output_dir)
            for p in problems:
                print(f"stale: {p}")
            if not problems:
                print(f"current: {OUTPUT_JSON.name} and {OUTPUT_MD.name} are what the rehearsal writes")
            return 1 if problems else 0
        result = rehearse()
    except RehearsalError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    finally:
        root.setLevel(previous_level)
    write(result, args.output_dir)
    s = result["summary"]
    print(f"{s['nights']} nights: {s['published']} published, {s['failed_before_publishing']} failed before publishing, "
          f"{s['skipped']} skipped; previous preserved on every empty night: {s['previous_preserved_on_every_night_that_published_nothing']}; "
          f"reader calls bounded: {s['reader_calls_within_bound_every_night']}; guard {s['guard']}; "
          f"admitted after a publication {s['slots_admitted_after_a_publication']}, after a failure {s['slots_admitted_after_a_failure']}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
