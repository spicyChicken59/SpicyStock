"""End-to-end: the real pipeline.run(), with all three boundaries mocked.

This is the test the old file was trying to be. It runs the actual
orchestrator -- scan, checklist, chart, score, archive -- against in-memory
Alpaca bars, a stubbed Claude and a stubbed Resend, in a temporary working
directory, with no network and no API keys.

What it asserts is wiring, not strategy: that the run completes, that a CSV
lands with the columns the workflow uploads, that the row count matches the
shortlist, and that a dry run does not send mail. The 2LYNCH gate is opened
in most tests so that steps 4 and 7 can move their thresholds without
turning this file into a no-op.
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from src import emailer
from src import ledger
from src import lynch
from src import pipeline
from src import scanner
from src.scanner import ScanConfig
from src.scorer import render_chart
from tests.test_ledger import contract_violations

#: What Alpaca says when the plan does not carry the feed the scan asked for.
#: The scanner classifies this as a refusal of the RUN rather than of the
#: batch, and stops instead of retrying every batch into an empty shortlist.
FEED_DENIAL = RuntimeError("subscription does not permit querying recent SIP data")

ARCHIVE_COLUMNS = [
    "ticker", "date", "close", "gain_pct", "volume_ratio",
    "lynch", "score", "verdict", "reason", "key_risk",
]


@pytest.fixture
def universe(fake_alpaca, ohlcv) -> list[str]:
    """Three symbols: one unmistakable burst, two that cannot be one."""
    fake_alpaca.add_history("BURST", ohlcv("burst"))
    fake_alpaca.add_history("QUIET", ohlcv("flat"))
    fake_alpaca.add_history("WALK", ohlcv("base"))
    return ["BURST", "QUIET", "WALK"]


@pytest.fixture(autouse=True)
def market_clock(monkeypatch):
    """Put every test in this file on a definite side of the 16:15 ET close.

    Step 10 made the run type a promise about the clock: an evening run
    expects the session to have closed, a morning run expects it not to have,
    and a disagreement degrades the run. Without a pin, whether an end-to-end
    test here saw a clean run or a degraded one would depend on the hour the
    suite happened to run -- green all evening and red all morning, which is
    the worst kind of test there is.

    The pin applies ONLY when the caller does not say what time it is:

        scanner.session_has_closed()              -> what this fixture was told
        scanner.session_has_closed(an_instant)    -> the real arithmetic

    so a test that names an instant is still testing the real predicate, and
    the tests that exercise the check itself pass one. `after_the_close` is the
    default because it is the only side an evening run belongs on, and most of
    this file is an evening run.
    """
    real = scanner.session_has_closed
    real_weekday = scanner.is_trading_weekday
    state = {"closed": True, "weekday": True}

    def pinned(now=None):
        return real(now) if now is not None else state["closed"]

    # The weekday is pinned by the same rule, or the sentence the clock check
    # writes would depend on whether the suite ran on a Saturday: a weekend
    # dispatch is told there is no session today, a weekday one that the
    # session has not closed yet, and the check reads the weekday alone.
    def pinned_weekday(now=None):
        return real_weekday(now) if now is not None else state["weekday"]

    monkeypatch.setattr(scanner, "session_has_closed", pinned)
    monkeypatch.setattr(scanner, "is_trading_weekday", pinned_weekday)

    class Clock:
        def after_the_close(self) -> None:
            state["closed"], state["weekday"] = True, True

        def before_the_open(self) -> None:
            state["closed"], state["weekday"] = False, True

        def weekend(self) -> None:
            state["closed"], state["weekday"] = False, False

    return Clock()


@pytest.fixture
def open_gate(monkeypatch):
    """Neutralise the 2LYNCH gate for the end-to-end tests.

    The gate's pass/fail arithmetic is step 7's to change. Opening it here
    means the run always reaches the chart, scoring and archive stages, so
    this file keeps testing wiring rather than accidentally testing where
    today's checklist thresholds happen to sit.
    """
    monkeypatch.setattr(pipeline, "MIN_LYNCH_PASSES", 0)


def archived_csv(tmp_path: Path) -> Path:
    files = sorted((tmp_path / "results").glob("*.csv"))
    assert len(files) == 1, f"expected exactly one archive, found {files}"
    return files[0]


# ----------------------------------------------------------- the whole run --


def test_dry_run_completes_and_archives_a_csv(universe, mocked_boundaries, open_gate, tmp_path):
    results = pipeline.run("evening", dry_run=True, tickers=universe)

    assert isinstance(results, list)
    assert results, "the burst symbol should have reached the shortlist"

    path = archived_csv(tmp_path)
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == ARCHIVE_COLUMNS
    assert len(rows) == len(results)
    assert {r["ticker"] for r in rows} == {r["ticker"] for r in results}
    assert "BURST" in {r["ticker"] for r in rows}


def test_dry_run_does_not_send_email(universe, mocked_boundaries, open_gate):
    pipeline.run("evening", dry_run=True, tickers=universe)
    assert mocked_boundaries["resend"].sent == [], "--dry-run must skip delivery"


def test_every_scored_candidate_cost_exactly_one_model_call(
    universe, mocked_boundaries, open_gate
):
    results = pipeline.run("evening", dry_run=True, tickers=universe)
    assert len(mocked_boundaries["anthropic"].calls) == len(results)


def test_a_chart_is_rendered_for_each_scored_candidate(
    universe, mocked_boundaries, open_gate, tmp_path
):
    """Under docs/, because that is the directory GitHub Pages serves and the
    dashboard names a chart as a path relative to itself."""
    results = pipeline.run("evening", dry_run=True, tickers=universe)
    charts = sorted(p.stem for p in (tmp_path / "docs" / "charts").glob("*.png"))
    assert charts == sorted(r["ticker"] for r in results)


def test_the_run_writes_only_inside_the_working_directory(
    universe, mocked_boundaries, open_gate, tmp_path
):
    """archive(), render_chart() and the ledger all use paths relative to the
    process working directory. That is why the suite chdirs into tmp_path."""
    pipeline.run("evening", dry_run=True, tickers=universe)
    assert Path("results").resolve().is_relative_to(tmp_path)
    assert Path("docs").resolve().is_relative_to(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["docs", "results"]
    assert sorted(p.name for p in (tmp_path / "docs").iterdir()) == [
        "charts", "data.json", "ledger.json"]


def test_live_run_sends_through_the_mocked_transport(universe, mocked_boundaries, open_gate):
    results = pipeline.run("evening", dry_run=False, tickers=universe)

    sent = mocked_boundaries["resend"].sent
    assert len(sent) == 1
    for row in results[:pipeline.TOP_N]:
        assert row["ticker"] in sent[0]["html"]


def test_the_evening_csv_is_named_for_the_session_it_scanned(
    universe, mocked_boundaries, open_gate, tmp_path
):
    """Not for the day the run happened. Those are the same date on a normal
    evening and differ on exactly the runs that used to lie about it."""
    pipeline.run("evening", dry_run=True, tickers=universe)
    assert archived_csv(tmp_path).name == f"{scanner.current_session()}_evening.csv"


def test_a_scan_with_no_candidates_still_completes(fake_alpaca, mocked_boundaries, ohlcv, tmp_path):
    fake_alpaca.add_history("QUIET", ohlcv("flat"))
    fake_alpaca.add_history("WALK", ohlcv("base"))

    results = pipeline.run("evening", dry_run=True, tickers=["QUIET", "WALK"])

    assert results == []
    assert mocked_boundaries["anthropic"].calls == []
    with archived_csv(tmp_path).open(newline="") as f:
        assert next(csv.reader(f)) == ARCHIVE_COLUMNS
        assert list(csv.reader(f)) == []


# --------------------------------------------------------------- archiving --


def test_archive_writes_the_documented_columns(tmp_path):
    path = pipeline.archive([], "evening")
    assert path.parent.name == "results"
    with path.open(newline="") as f:
        assert next(csv.reader(f)) == ARCHIVE_COLUMNS


def test_archive_drops_the_columns_the_csv_does_not_carry(tmp_path):
    """score_all() rows also carry lynch_detail and chart; the archive is
    declared with extrasaction='ignore' so those are dropped, not an error."""
    row = {c: c.upper() for c in ARCHIVE_COLUMNS}
    row["lynch_detail"] = ["PASS  a: b"]
    row["chart"] = "charts/AAA.png"

    path = pipeline.archive([row], "evening")
    with path.open(newline="") as f:
        written = list(csv.DictReader(f))

    assert list(written[0]) == ARCHIVE_COLUMNS
    assert written[0]["ticker"] == "TICKER"


def test_archive_names_the_file_by_date_and_run_type(tmp_path):
    evening = pipeline.archive([], "evening")
    morning = pipeline.archive([], "morning")
    assert evening.name.endswith("_evening.csv")
    assert morning.name.endswith("_morning.csv")
    assert evening.name[:10] == morning.name[:10], "both should carry the same UTC date stamp"


# ===========================================================================
# Step 5 -- failing loudly.
#
# Every failure below used to end the same way: a cheerful email, an INFO line
# saying the run was complete, and exit 0. What each test pins is the
# difference an operator can now see -- the exit code Actions reads, the log,
# and whether an email went out and what it said.
# ===========================================================================


def visible(html: str) -> str:
    """What a mail client shows, through a real parser. Every free-text leaf in
    the email is escaped now, so an apostrophe in a sentence is an entity in
    the source; a test that greps the source for the sentence reads the
    escaping as the sentence going missing. The reader is the standard."""
    from html.parser import HTMLParser

    class Reader(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []

        def handle_data(self, data):
            self.parts.append(data)

    reader = Reader()
    reader.feed(html)
    return " ".join(" ".join(reader.parts).split())


def _main(monkeypatch, *argv: str) -> int:
    """Run the real main() and return the exit code it chose."""
    monkeypatch.setattr(sys, "argv", ["pipeline", *argv])
    with pytest.raises(SystemExit) as exc:
        pipeline.main()
    return exc.value.code


def _wide_universe(fake_alpaca, ohlcv, *, fresh: int, stale: int = 0) -> list[str]:
    """A universe big enough for a fraction of it to mean something."""
    names = []
    for i in range(fresh):
        fake_alpaca.add_history(f"F{i}", ohlcv("burst", variant=i))
        names.append(f"F{i}")
    for i in range(stale):
        fake_alpaca.add_history(f"S{i}", ohlcv("burst", variant=50 + i), stale_sessions=1)
        names.append(f"S{i}")
    return names


# ----------------------------------------------------------- preflight -----


@pytest.mark.parametrize("var", ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ANTHROPIC_API_KEY",
                                 "RESEND_API_KEY", "EMAIL_TO"])
def test_a_missing_key_stops_the_run_before_it_spends_anything(
    monkeypatch, universe, mocked_boundaries, open_gate, var, tmp_path
):
    """RESEND_API_KEY and EMAIL_TO were read on the LAST line of the run, so a
    missing one cost the whole scan and every paid Claude call and then mailed
    nothing. Nothing may be spent on the way to that error."""
    monkeypatch.delenv(var)

    with pytest.raises(pipeline.PreflightError, match=var):
        pipeline.run("evening", dry_run=False, tickers=universe)

    assert mocked_boundaries["alpaca"].bar_requests == [], "no data was fetched"
    assert mocked_boundaries["anthropic"].calls == [], "no model call was paid for"
    assert mocked_boundaries["resend"].sent == []
    assert not (tmp_path / "results").exists(), "and nothing was archived"


@pytest.mark.parametrize("var", ["ALPACA_API_KEY", "ANTHROPIC_API_KEY"])
def test_a_dry_run_still_needs_the_keys_it_still_uses(
    monkeypatch, universe, mocked_boundaries, open_gate, var
):
    """--dry-run skips only delivery. It still scans and still calls Claude."""
    monkeypatch.delenv(var)
    with pytest.raises(pipeline.PreflightError, match=var):
        pipeline.run("evening", dry_run=True, tickers=universe)


@pytest.mark.parametrize("var", ["RESEND_API_KEY", "EMAIL_TO"])
def test_a_dry_run_does_not_need_the_keys_it_does_not_use(
    monkeypatch, universe, mocked_boundaries, open_gate, var
):
    monkeypatch.delenv(var)
    assert pipeline.run("evening", dry_run=True, tickers=universe), "the run completes"


def test_an_empty_variable_counts_as_missing(monkeypatch, mocked_boundaries):
    """An unset GitHub secret arrives as '', which every `os.environ[...]` and
    `in os.environ` check in this pipeline used to accept."""
    monkeypatch.setenv("RESEND_API_KEY", "")
    assert "RESEND_API_KEY" in pipeline.missing_env(dry_run=False)
    assert "RESEND_API_KEY" not in pipeline.missing_env(dry_run=True)


def test_preflight_names_every_missing_variable_at_once(monkeypatch, mocked_boundaries):
    """One list, not one round trip per key."""
    monkeypatch.delenv("ALPACA_API_KEY")
    monkeypatch.delenv("EMAIL_TO")
    with pytest.raises(pipeline.PreflightError) as exc:
        pipeline.preflight(dry_run=False)
    assert "ALPACA_API_KEY" in str(exc.value) and "EMAIL_TO" in str(exc.value)


# ---------------------------------------------------------- exit codes -----


def test_a_clean_run_exits_zero(monkeypatch, universe, mocked_boundaries, open_gate):
    assert _main(monkeypatch, "evening", "--tickers", ",".join(universe)) == pipeline.EXIT_OK
    assert len(mocked_boundaries["resend"].sent) == 1


def test_a_run_that_could_not_score_exits_degraded_and_still_mails(
    monkeypatch, universe, mocked_boundaries, open_gate
):
    """The dangerous case: the run completes and the email looks normal. It
    still goes out -- an email that never arrives is another silent failure --
    but it is marked, and Actions goes red."""
    mocked_boundaries["anthropic"].set_error(RuntimeError("Error code: 401 - invalid x-api-key"))

    code = _main(monkeypatch, "evening", "--tickers", ",".join(universe))

    assert code == pipeline.EXIT_DEGRADED
    (sent,) = mocked_boundaries["resend"].sent
    assert sent["subject"].startswith("[4% Burst] DEGRADED — ")
    assert "NOT ONE" in sent["html"] and "invalid x-api-key" in sent["html"]


def test_a_run_that_could_not_scan_exits_failed_and_mails_the_reason(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv
):
    """A run that dies sends nothing today, and nothing in an inbox looks
    exactly like a public holiday."""
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    fake_alpaca.raise_on_bars = FEED_DENIAL

    code = _main(monkeypatch, "evening", "--tickers", "AAA")

    assert code == pipeline.EXIT_FAILED
    (sent,) = mocked_boundaries["resend"].sent
    assert sent["subject"].startswith("[4% Burst] FAILED — ")
    from html import unescape
    # The phrase, unescaped, because the quotes are entities in the source and
    # the notice also lists every feed the SDK knows, so a bare "sip" matched
    # with the refused feed dropped from the sentence.
    assert "FeedNotAuthorizedError" in sent["html"]
    assert f"refused the {scanner.DEFAULT_FEED.value!r} data feed" in unescape(sent["html"])


def test_a_failure_notice_names_the_session_the_run_was_going_for(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv
):
    """Both failure notices printed "Session scanned: not recorded", and the
    morning one "4% bursts that session: ?", in the one email where an operator
    most wants to know which night broke. The session does not need the scan:
    the clock knows it, or SCAN_SESSION_DATE does, before anything is spent.

    It is labelled as the session the run was GOING FOR, not the one it read.
    Nothing read it -- putting it under "Session scanned" would be the same
    silent relabelling the session line was added to end."""
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    fake_alpaca.raise_on_bars = FEED_DENIAL
    session = str(scanner.current_session())

    assert _main(monkeypatch, "evening", "--tickers", "AAA") == pipeline.EXIT_FAILED

    (sent,) = mocked_boundaries["resend"].sent
    assert f"Session it was scanning: {session}" in sent["html"]
    assert "Session scanned" not in sent["html"], "it scanned nothing"
    assert "not recorded" not in sent["html"].split("Universe")[0]
    assert session in sent["subject"]


def test_a_pinned_session_is_the_one_a_failure_notice_names(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv
):
    """The precondition: it comes from expected_session(), the one definition
    both modes use, so a deliberate backfill that dies reports the session it
    was backfilling and not today."""
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    fake_alpaca.raise_on_bars = FEED_DENIAL
    monkeypatch.setenv("SCAN_SESSION_DATE", "2026-08-14")

    assert _main(monkeypatch, "evening", "--tickers", "AAA") == pipeline.EXIT_FAILED

    assert "Session it was scanning: 2026-08-14" in mocked_boundaries["resend"].sent[0]["html"]


def test_a_failure_notice_survives_a_session_it_cannot_name(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, caplog
):
    """Best effort, like everything else on this path: a run that died inside
    ScanConfig() -- a malformed SCAN_SESSION_DATE is exactly that -- still gets
    its email, with the session unrecorded, rather than losing the notice to a
    second failure."""
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    monkeypatch.setenv("SCAN_SESSION_DATE", "the day before yesterday")

    assert _main(monkeypatch, "evening", "--tickers", "AAA") == pipeline.EXIT_FAILED

    (sent,) = mocked_boundaries["resend"].sent
    assert sent["subject"].startswith("[4% Burst] FAILED — ")
    assert "Session it was scanning: not recorded" in sent["html"]


def test_a_failed_dry_run_exits_failed_without_mailing(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv
):
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    fake_alpaca.raise_on_bars = FEED_DENIAL

    code = _main(monkeypatch, "evening", "--dry-run", "--tickers", "AAA")

    assert code == pipeline.EXIT_FAILED
    assert mocked_boundaries["resend"].sent == []


def test_a_run_that_cannot_start_still_mails_why(monkeypatch, universe, mocked_boundaries):
    """The case that most needs an email is the one where a key is missing --
    and the notice needs only the DELIVERY keys, so a missing Alpaca key must
    not withhold the notice about the missing Alpaca key."""
    monkeypatch.delenv("ALPACA_API_KEY")

    assert _main(monkeypatch, "evening", "--tickers", ",".join(universe)) == pipeline.EXIT_FAILED

    (sent,) = mocked_boundaries["resend"].sent
    assert sent["subject"].startswith("[4% Burst] FAILED — ")
    assert "ALPACA_API_KEY" in sent["html"]


def test_nothing_is_mailed_when_the_delivery_keys_are_the_missing_ones(
    monkeypatch, universe, mocked_boundaries, caplog
):
    """The inverse: there is nothing to send with, and the exit code is all
    that is left. It must say so rather than trying and dying again."""
    monkeypatch.delenv("EMAIL_TO")

    assert _main(monkeypatch, "evening", "--tickers", ",".join(universe)) == pipeline.EXIT_FAILED
    assert mocked_boundaries["resend"].sent == []
    assert "only remaining signal is this exit code" in caplog.text


def test_a_failure_notice_that_cannot_be_sent_does_not_replace_the_failure(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, caplog
):
    """The notice is best effort. A second failure here must not mask the
    first, which is the one the operator has to read."""
    import resend

    fake_alpaca.add_history("AAA", ohlcv("burst"))
    fake_alpaca.raise_on_bars = FEED_DENIAL
    monkeypatch.setattr(resend.Emails, "send",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("resend is down")))

    assert _main(monkeypatch, "evening", "--tickers", "AAA") == pipeline.EXIT_FAILED
    assert "FeedNotAuthorizedError" in caplog.text
    assert "Could not mail the failure notice" in caplog.text


# -------------------------------------------------- what degrades a run ----


def test_a_partly_stale_scan_degrades_the_run_without_stopping_it(
    fake_alpaca, mocked_boundaries, ohlcv, open_gate
):
    """Two of fourteen names halted is 14% of the scan: above the line where
    the run says so, well below the line where src.scanner refuses to report
    it at all."""
    universe = _wide_universe(fake_alpaca, ohlcv, fresh=12, stale=2)
    report = pipeline.RunReport()

    pipeline.run("evening", dry_run=False, tickers=universe, report=report)

    assert report.status == "degraded" and report.exit_code == pipeline.EXIT_DEGRADED
    (scan_problem,) = [e for e in report.errors if e["stage"] == "scan"]
    assert "carried no bar" in scan_problem["message"]
    assert "DEGRADED" in mocked_boundaries["resend"].sent[0]["subject"]


def test_a_handful_of_halted_names_is_a_normal_day(
    fake_alpaca, mocked_boundaries, ohlcv, open_gate
):
    """The inverse. One name in twenty is what halts and delistings look like,
    and a screener that cried wolf every day would be as useless as one that
    never did."""
    universe = _wide_universe(fake_alpaca, ohlcv, fresh=19, stale=1)
    report = pipeline.RunReport()

    pipeline.run("evening", dry_run=True, tickers=universe, report=report)

    assert report.status == "ok", report.errors


def test_symbols_the_feed_knows_nothing_about_degrade_the_run(
    fake_alpaca, mocked_boundaries, ohlcv, open_gate
):
    """Neither dropped nor stale: the request succeeds and simply carries no
    bars for them. A symbol file that has drifted from what the feed lists
    shrinks the universe silently, and every count downstream still looks
    healthy because it is a count of what came back."""
    universe = _wide_universe(fake_alpaca, ohlcv, fresh=10) + ["NOSUCH1", "NOSUCH2"]
    report = pipeline.RunReport()

    pipeline.run("evening", dry_run=True, tickers=universe, report=report)

    assert report.status == "degraded"
    (problem,) = [e for e in report.errors if "no bars at all" in e["message"]]
    assert "2 of 12" in problem["message"]


def test_a_dropped_batch_degrades_the_run(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate
):
    """One flaky symbol must not kill the run -- but it must not vanish either.
    Its batch was never examined, so the shortlist is missing part of the
    market and an empty one would not mean a quiet day."""
    import time as time_module

    monkeypatch.setattr(time_module, "sleep", lambda *_: None)
    universe = _wide_universe(fake_alpaca, ohlcv, fresh=12)
    fake_alpaca.raise_on_bars = ConnectionError("connection reset by peer")
    fake_alpaca.fail_symbols = {"F0"}
    # One symbol per request, so one flaky symbol is one dropped batch. The
    # default 100 would put the whole universe in the batch it kills.
    monkeypatch.setattr(pipeline, "ScanConfig", lambda: scanner.ScanConfig(batch_size=1))
    report = pipeline.RunReport()

    results = pipeline.run("evening", dry_run=True, tickers=universe, report=report)

    assert results, "the rest of the universe was still scanned"
    assert report.status == "degraded"
    assert any("dropped" in e["message"] for e in report.errors)


def test_a_failed_chart_render_degrades_the_run(
    monkeypatch, universe, mocked_boundaries, open_gate
):
    """The candidate is still scored, but blind: the model is told to trust
    the chart over the numbers and there was no chart."""
    monkeypatch.setattr(pipeline, "render_chart",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("no renderer")))
    report = pipeline.RunReport()

    results = pipeline.run("evening", dry_run=True, tickers=universe, report=report)

    assert results, "a missing chart does not stop the run"
    assert [e["stage"] for e in report.errors] == ["chart"]
    assert "no renderer" in report.errors[0]["message"]


def test_a_clean_run_reports_no_problems_at_all(universe, mocked_boundaries, open_gate):
    """The precondition every degradation test above depends on: `degraded` is
    not simply what this pipeline always says."""
    report = pipeline.RunReport()
    pipeline.run("evening", dry_run=True, tickers=universe, report=report)
    assert report.errors == [] and report.status == "ok"
    assert report.exit_code == pipeline.EXIT_OK


def test_the_report_hands_step_9_the_shape_docs_data_json_asks_for(
    universe, mocked_boundaries, open_gate
):
    """run.errors is a list of {stage, message}; the dashboard renders it and
    the email prints it. One description of a failure, three audiences."""
    report = pipeline.RunReport()
    report.problem("scan", "something")
    report.fail("score", RuntimeError("boom"))

    assert [set(e) for e in report.errors] == [{"stage", "message"}, {"stage", "message"}]
    assert report.errors[1] == {"stage": "score", "message": "RuntimeError: boom"}
    assert report.status == "failed"


# ===========================================================================
# Step 9 -- the archive.
#
# The audit's central finding was that this system cannot tell you whether it
# works: TOP_N cut the archive as well as the email, so four fifths of every
# night's judgements were discarded unrecorded and no score was ever held next
# to the return that followed it. Every test below is about what SURVIVES a
# run -- the two files under docs/, what is in them, and what a later run adds.
#
# contract_violations() (tests/test_ledger.py) reads docs/data.json's own
# invariants back out of the file it is given, so each test asserts the whole
# contract as well as the one thing it is about: a change that fixes the named
# claim by breaking another one cannot pass here.
# ===========================================================================


def published(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "docs" / "data.json").read_text())


def recorded(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "docs" / "ledger.json").read_text())


def clean(tmp_path: Path) -> dict:
    """The published run, asserted against every invariant it declares."""
    data = published(tmp_path)
    assert contract_violations(data, docs_dir=tmp_path / "docs") == set()
    return data


def session_offset(days: int) -> str:
    """The session `days` trading days from the newest completed one.

    Negative is the past. Positive is a session that has not happened yet,
    which is how "run this again tomorrow" is expressed to a double that dates
    its bars from the request: src.scanner reads SCAN_SESSION_DATE and asks
    for bars up to that session, and the fake answers with bars ending there.
    """
    end = scanner.current_session()
    if days <= 0:
        return pd.bdate_range(end=end, periods=abs(days) + 1)[0].date().isoformat()
    return pd.bdate_range(start=end, periods=days + 1)[-1].date().isoformat()


def served(fake_alpaca, ticker: str, session: str) -> pd.DataFrame:
    """The bars the double would return for a request ending at `session`.

    Used to recompute a forward return independently of the code that wrote
    it: the double re-dates a registered frame so its newest bar lands on the
    session asked for, exactly as a live feed returns bars up to the moment.
    """
    frame = fake_alpaca.bars_frame([ticker], end=pd.Timestamp(session).date())
    return frame.loc[ticker]


def expected_returns(frame: pd.DataFrame, burst: str, horizons=(1, 3, 5)) -> dict:
    """Both bases, recomputed by hand from the served frame: the close basis
    divides by the burst-day close, the open basis by the NEXT session's open.

    By DATE -- the h-th business day after the burst, weekend-only, looked up
    in the frame -- and not by offset along the frame's bars. The doubles
    serve contiguous frames, so the two readings agree here; counting bars
    would agree with the code by accident and stop agreeing with it on the
    one input round 9 is about, a frame with a hole in it.
    """
    by_date = {stamp.date(): row for stamp, row in frame.iterrows()}
    start = date.fromisoformat(burst)

    def session(n: int) -> date:
        day = start
        for _ in range(n):
            day += timedelta(days=1)
            while day.weekday() >= 5:
                day += timedelta(days=1)
        return day

    base = float(by_date[start]["close"])
    out = {f"d{h}": round((float(by_date[session(h)]["close"]) / base - 1) * 100, 2)
           for h in horizons if session(h) in by_date}
    entry = float(by_date[session(1)]["open"]) if session(1) in by_date else None
    out["from_open"] = {f"d{h}": (round((float(by_date[session(h)]["close"]) / entry - 1) * 100, 2)
                                  if entry and session(h) in by_date else None)
                        for h in (1, 3, 5)}
    return out


def test_the_published_run_satisfies_every_invariant_it_declares(
    universe, mocked_boundaries, open_gate, tmp_path
):
    results = pipeline.run("evening", dry_run=True, tickers=universe)

    data = clean(tmp_path)
    assert data["run"]["fixture"] is False, "this file is a run, not the fixture"
    assert data["run"]["dry_run"] is True
    assert data["run"]["date"] == scanner.current_session().isoformat()
    assert len(data["candidates"]) == data["run"]["scored"] == len(results)
    assert [c["ticker"] for c in data["candidates"]] == [r["ticker"] for r in results]


def test_top_n_cuts_the_email_and_nothing_else(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """THE step-9 invariant. score_all() returned results[:TOP_N] and archive()
    wrote exactly that, so the shortlist size silently decided how much of the
    run was ever recorded. Now the cut belongs to the email alone."""
    monkeypatch.setattr(pipeline, "TOP_N", 1)
    names = _wide_universe(fake_alpaca, ohlcv, fresh=3)

    scored = pipeline.run("evening", dry_run=False, tickers=names)

    data = clean(tmp_path)
    assert len(scored) == 3, "run() returns every scored candidate"
    assert data["run"]["scored"] == len(data["candidates"]) == 3
    assert len(recorded(tmp_path)["runs"][0]["candidates"]) == 3
    with archived_csv(tmp_path).open(newline="") as f:
        assert len(list(csv.DictReader(f))) == 3

    (sent,) = mocked_boundaries["resend"].sent
    assert data["run"]["shortlist_size"] == 1
    emailed = [name for name in names if name in sent["html"]]
    assert emailed == [scored[0]["ticker"]], "the email still carries TOP_N of them"


def test_a_burst_the_gate_rejected_is_archived_with_its_checklist(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, tmp_path
):
    """Nothing a scan found may vanish. The gated names carry their
    measurements too, because a per-check pass rate computed over the
    survivors alone is survivorship bias with a percentage sign."""
    monkeypatch.setattr(pipeline, "MIN_LYNCH_PASSES", 99)
    names = _wide_universe(fake_alpaca, ohlcv, fresh=3)

    scored = pipeline.run("evening", dry_run=True, tickers=names)

    data = clean(tmp_path)
    assert scored == [] and data["run"]["scored"] == 0
    assert data["run"]["bursts"] == 3 and len(data["gated_out"]) == 3
    assert {g["reason"] for g in data["gated_out"]} == {"lynch_gate"}
    assert all(len(g["lynch_detail"]) == g["lynch_total"] for g in data["gated_out"])
    assert mocked_boundaries["anthropic"].calls == [], "and nothing was paid for"


def test_a_night_that_scored_nothing_still_publishes_the_size_of_its_own_gate(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, tmp_path
):
    """`run.gate.total_checks` is what the page and the email interpolate into
    "rejected at the >=3/6 2LYNCH gate". It was read off the SCORED rows
    alone, so a night that scored nothing published null there -- and the page
    concatenated it, printing a threshold against a total that does not exist
    over rows correctly showing 5/6 beside it. The checklist was measured for
    every one of these bursts; only the scoring was skipped."""
    monkeypatch.setattr(pipeline, "MIN_LYNCH_PASSES", 99)
    names = _wide_universe(fake_alpaca, ohlcv, fresh=3)

    pipeline.run("evening", dry_run=True, tickers=names)

    data = clean(tmp_path)
    assert data["run"]["scored"] == 0, "precondition: nothing reached the scorer"
    assert data["run"]["bursts"] == 3, "and the checklist ran on all three"
    measured = lynch.evaluate_2lynch(ohlcv("burst", variant=0))["total"]
    assert data["run"]["gate"]["total_checks"] == measured
    assert data["run"]["gate"]["total_checks"] == data["gated_out"][0]["lynch_total"], (
        "the same number the rows beneath it print"
    )


def test_a_night_that_found_no_burst_at_all_publishes_no_gate_size(
    fake_alpaca, mocked_boundaries, ohlcv, tmp_path
):
    """The other side of that fix, and the reason it is `next(..., None)` and
    not a constant read off src.lynch. Nothing measured a checklist here, so
    there is no measurement to report; publishing a 6 anyway would be the same
    invention in the opposite direction. The page's job is to say the part it
    knows -- the pass threshold -- and drop the part it does not."""
    for i in range(3):
        fake_alpaca.add_history(f"Q{i}", ohlcv("flat", variant=i))

    pipeline.run("evening", dry_run=True, tickers=[f"Q{i}" for i in range(3)])

    data = clean(tmp_path)
    assert data["run"]["bursts"] == 0 and data["gated_out"] == []
    assert data["run"]["gate"]["total_checks"] is None
    assert data["run"]["gate"]["min_lynch_passes"] == pipeline.MIN_LYNCH_PASSES, (
        "the threshold is a rule, not a measurement, and is published either way"
    )


def test_the_email_says_how_many_cleared_the_gate_and_were_never_looked_at(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The funnel went "Passed 2LYNCH gate: 54" straight to "Shortlisted: 1".

    On any night with more survivors than the call budget, the names that
    cleared the checklist and were never scored appeared NOWHERE -- while the
    line beside it read "Scored by Claude: 25 of 25", which a reader takes for
    complete coverage of the 54. The page's funnel has had this cut since step
    9 and names the same cause; the email did not have it at all.

    Asserted on the mail the real run actually sent, not on a stats block
    written here: the numbers have to be the ones the pipeline computed, and
    a hand-built block is a second opinion about them.
    """
    monkeypatch.setattr(pipeline, "MAX_TO_SCORE", 2)
    names = _wide_universe(fake_alpaca, ohlcv, fresh=5)

    pipeline.run("evening", dry_run=False, tickers=names)

    data = clean(tmp_path)
    passed, scored = data["run"]["passed_gate"], data["run"]["scored"]
    assert passed > scored, f"precondition: the cap must bite ({passed} through, {scored} scored)"

    html = mocked_boundaries["resend"].sent[-1]["html"]
    assert f"Passed 2LYNCH gate: {passed}" in html
    assert f"Crowded out by the 2-call cap: {passed - scored}" in html
    # The label carries the cap the RUN applied, not this module's constant --
    # a morning email re-presenting an older night must not relabel it with
    # today's budget.
    assert data["run"]["score_cap"] == 2


def test_the_crowded_out_count_is_the_call_cap_alone_and_not_every_unscored_burst(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """Four reasons send a burst away unscored and only ONE of them is the
    call budget. Counting every unscored row would report names an absolute
    rule refused as names the cap crowded out -- two of the three facts this
    project forbids collapsing, folded into a line that states the third.

    Needs a night with both kinds in it, or the wrong count and the right one
    are the same number: with nothing vetoed, every unscored burst IS a
    score_cap one, and the check passes on a fixture rather than on the rule.
    """
    names = []
    for i in range(3):   # refused outright, whatever the checklist says
        fake_alpaca.add_history(f"V{i}", ohlcv("burst", variant=i,
                                               up_run=lynch.MAX_CONSECUTIVE_UP_DAYS + 1))
        names.append(f"V{i}")
    for i in range(4):   # clean, and more than the budget below allows
        fake_alpaca.add_history(f"C{i}", ohlcv("burst", variant=10 + i, up_run=1))
        names.append(f"C{i}")
    monkeypatch.setattr(pipeline, "MAX_TO_SCORE", 2)

    pipeline.run("evening", dry_run=False, tickers=names)

    data = clean(tmp_path)
    reasons = [g["reason"] for g in data["gated_out"]]
    vetoed = sum(1 for r in reasons if r.startswith("veto_"))
    capped = sum(1 for r in reasons if r == "score_cap")
    assert vetoed and capped and vetoed != capped, (
        f"precondition: the night needs both kinds, and in different "
        f"numbers, or the two counts cannot be told apart: {reasons}")

    html = mocked_boundaries["resend"].sent[-1]["html"]
    assert f"Crowded out by the 2-call cap: {capped}" in html
    assert f"Refused by an absolute rule: {vetoed}" in html
    assert f"Crowded out by the 2-call cap: {len(reasons)}" not in html, (
        "every unscored burst counted as the budget's doing")


def test_a_night_the_cap_never_reached_says_nothing_about_it(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The other side of the same rule the refusals line follows: a night that
    scored everything that got through reads exactly as it did before, and a
    "Crowded out by the 25-call cap: 0" would be noise dressed as a finding."""
    monkeypatch.setattr(pipeline, "MAX_TO_SCORE", 50)
    names = _wide_universe(fake_alpaca, ohlcv, fresh=3)

    pipeline.run("evening", dry_run=False, tickers=names)

    data = clean(tmp_path)
    assert data["run"]["passed_gate"] == data["run"]["scored"], "precondition"
    assert "Crowded out" not in mocked_boundaries["resend"].sent[-1]["html"]


def test_a_hole_before_the_session_and_a_raising_detector_both_degrade_the_run():
    """The scan reports both now (src.scanner); the run must say so. A hole is
    a symbol that could not be measured for the session, the same class as a
    stale one, and is counted with it against the same fraction. A detector
    that raised is a defect and is reported at any count."""
    report = pipeline.RunReport()
    pipeline._check_scan({"requested": 100, "with_bars": 100, "stale": {}, "no_bars": 0,
                          "dropped": 0, "session": "2026-09-04",
                          "gapped": {f"G{i}": "2026-09-02" for i in range(11)},
                          "detector_errors": {}}, report)
    assert [e["stage"] for e in report.errors] == ["scan"]
    assert "11 had no bar for the session before it" in report.errors[0]["message"]

    report = pipeline.RunReport()
    pipeline._check_scan({"requested": 100, "with_bars": 100, "stale": {}, "no_bars": 0,
                          "dropped": 0, "session": "2026-09-04", "gapped": {},
                          "detector_errors": {"B3": "ValueError: a dtype surprise"}}, report)
    assert report.status == "degraded"
    assert "raised on 1 of 100" in report.errors[0]["message"]
    assert "ValueError: a dtype surprise" in report.errors[0]["message"]


def test_the_email_names_a_command_line_universe_the_way_the_archive_does(
    fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """With --tickers the funnel line said "N checked-in US common stocks" over
    names typed on the command line, while docs/data.json beside it correctly
    said --tickers. One label now, read by both."""
    names = _wide_universe(fake_alpaca, ohlcv, fresh=3)

    pipeline.run("evening", dry_run=False, tickers=names)

    html = mocked_boundaries["resend"].sent[-1]["html"]
    label = clean(tmp_path)["run"]["universe"]["label"]
    assert "named on the command line" in html and "checked-in" not in html
    assert "named on the command line" in label, label


def _two_bursts_one_thin(fake_alpaca, ohlcv):
    """Two genuine bursts and a small universe to rank them against: the
    thinner one sits below the 30th percentile of what traded."""
    from tests.test_scanner import _thin

    fake_alpaca.add_history("FAT", _thin(ohlcv, "burst", price=200.0, volume=5_000_000))
    fake_alpaca.add_history("THIN", _thin(ohlcv, "burst", price=5.0, volume=200_000, variant=1))
    names = ["FAT", "THIN"]
    for i in range(8):
        fake_alpaca.add_history(f"Q{i}", _thin(ohlcv, "flat", price=80.0,
                                               volume=2_000_000, variant=i + 2))
        names.append(f"Q{i}")
    return names


def test_a_burst_the_liquidity_floor_refused_is_in_the_record_and_says_why(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The finding two refuters confirmed by execution: a genuine burst rule 6
    refused was in no count, no gated_out row, no ledger row and no line of
    the email, while the funnel printed "4% bursts found: 1" over it. Every
    surface holds it now under its own word -- neither a veto nor a gate
    rejection, because the checklist was never consulted -- and the run
    records the floor it applied, in dollars, beside the count."""
    names = _two_bursts_one_thin(fake_alpaca, ohlcv)

    pipeline.run("evening", dry_run=False, tickers=names)

    data = published(tmp_path)
    assert data["run"]["bursts"] == 2, "the refused burst is a burst the scan found"
    assert [c["ticker"] for c in data["candidates"]] == ["FAT"]
    (row,) = data["gated_out"]
    assert row["ticker"] == "THIN" and row["reason"] == ledger.LIQUIDITY_REASON
    assert row["lynch_detail"], "the checklist still ran on it, so its row can be judged later"
    liquidity = data["run"]["liquidity"]
    assert liquidity["refused"] == 1 and liquidity["pctile"] == scanner.ScanConfig().min_dollar_volume_pctile
    assert row["dollar_volume"] < liquidity["floor"] <= data["candidates"][0]["dollar_volume"]
    assert data["run"]["scored"] + len(data["gated_out"]) == data["run"]["bursts"]
    # The ledger keeps the row, the floor and the population apart.
    (entry,) = recorded(tmp_path)["runs"]
    assert entry["liquidity"] == liquidity
    assert [g["reason"] for g in entry["gated"]] == [ledger.LIQUIDITY_REASON]
    assert data["evidence"]["illiquid"]["setups"] == 1
    assert data["evidence"]["refused"]["setups"] == 0, "rule 6's refusals are not the control"
    # And the email says so, with the floor.
    html = visible(mocked_boundaries["resend"].sent[-1]["html"])
    assert "4% bursts found: 2" in html
    assert f"Below the liquidity floor ({emailer.compact_dollars(liquidity['floor'])}/day, the 30th percentile): 1" in html
    assert "THIN" not in html.split("Passed 2LYNCH gate")[0].split("Below the liquidity floor")[0], (
        "the thin name is not passed off as scored")


def test_a_run_records_the_rules_it_applied_and_the_record_reads_them_back(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The record kept `model` and nothing about the rules, so changing the
    gate or the 4% made every published mean an average over two screeners
    under one label. Every run carries the numbers now, in the snapshot and
    in the ledger entry, and the record says how many distinct sets it holds
    and which keys differ."""
    fake_alpaca.add_history("BURST", ohlcv("burst"))

    pipeline.run("evening", dry_run=True, tickers=["BURST"])

    data, book = published(tmp_path), recorded(tmp_path)
    rules = data["run"]["rules"]
    assert rules == pipeline.rules_fingerprint(), "what the run applied, not a copy"
    assert rules["gate.min_lynch_passes"] == pipeline.MIN_LYNCH_PASSES
    assert rules["scan.min_gain_pct"] == scanner.ScanConfig().min_gain_pct
    assert rules["check.max_consecutive_up_days"] == lynch.MAX_CONSECUTIVE_UP_DAYS
    assert book["runs"][0]["rules"] == rules, "and the durable file keeps it"
    view = data["evidence"]["rules"]
    assert view["sets"] == 1 and view["differ"] == [] and view["runs_without"] == 0
    assert view["current"] == rules


def test_a_record_written_under_two_screeners_says_so_and_names_what_moved(tmp_path):
    """The state this exists for. Two runs, one threshold apart, and a third
    from before the fingerprint existed: the record must not report the third
    as agreeing, and must name the key that moved rather than saying only
    that something did."""
    runs = [
        {"date": "2026-09-02", "type": "evening", "candidates": [], "gated": [],
         "rules": {"scan.min_gain_pct": 5.0, "gate.min_lynch_passes": 3}},
        {"date": "2026-09-01", "type": "evening", "candidates": [], "gated": [],
         "rules": {"scan.min_gain_pct": 4.0, "gate.min_lynch_passes": 3}},
        {"date": "2026-08-31", "type": "evening", "candidates": [], "gated": []},
    ]

    view = ledger.rules_view(runs)

    assert view["sets"] == 2 and view["runs_without"] == 1
    assert view["differ"] == ["scan.min_gain_pct"], "the key that moved, not just that one did"
    assert view["current"]["scan.min_gain_pct"] == 5.0, "the newest run's rules"

    # `sets` counts DISTINCT rules, not runs that carry them: a month of
    # nights under one screener is one set. Without this a record of thirty
    # identical runs would have told the reader it spanned thirty screeners
    # and that every mean on the page blended them.
    same = [dict(runs[1], date="2026-09-03"), runs[1], dict(runs[1], date="2026-08-30")]
    steady = ledger.rules_view(same)
    assert steady["sets"] == 1 and steady["differ"] == [] and steady["runs_without"] == 0


def _universe_file(monkeypatch, tmp_path, names) -> None:
    """Point the scanner at a symbol file of these names, so the run is a
    genuine UNIVERSE scan rather than a --tickers one. The difference is not
    cosmetic: a --tickers run has no universe, so it neither gives a
    benchmark nor gets one."""
    path = tmp_path / "symbols.txt"
    path.write_text("\n".join(names) + "\n", encoding="utf-8")
    monkeypatch.setattr(scanner, "SYMBOLS_FILE", path)


def _five_name_market(fake_alpaca, ohlcv) -> list:
    from tests.test_scanner import _thin

    fake_alpaca.add_history("BURST", ohlcv("burst"))
    names = ["BURST"]
    # Letters only: the symbol-file parser refuses a digit, and this market
    # has to be readable as a real universe file.
    for i, suffix in enumerate("ABCD"):
        fake_alpaca.add_history(f"Q{suffix}", _thin(ohlcv, "flat", price=40.0 + i,
                                                    volume=3_000_000, variant=i + 2))
        names.append(f"Q{suffix}")
    return names


def test_a_later_scan_fills_the_earlier_runs_universe_benchmark_from_its_own_frames(
    monkeypatch, market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The scan reads the whole universe with a year of lookback and used to
    keep only the bursting names' frames. The evening after, those frames
    carry every name's close on the earlier session and the sessions since,
    so the earlier run's "buy anything in the universe that day" resolves at
    no extra request -- and equals the equal-weight mean, recomputed here by
    hand from the frames the double served."""
    names = _five_name_market(fake_alpaca, ohlcv)
    _universe_file(monkeypatch, tmp_path, names)
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(-1))
    pipeline.run("evening", dry_run=True)
    first_session = recorded(tmp_path)["runs"][0]["date"]
    assert recorded(tmp_path)["runs"][0]["benchmark"] == ledger.empty_benchmark(), (
        "nothing after that session exists yet")
    before = len(mocked_boundaries["alpaca"].bar_requests)
    # The frames the fill is handed, captured as it is handed them: the
    # equal-weight mean is then recomputed BY HAND from the same inputs,
    # which is the comparison worth making. Re-fetching them from the double
    # afterwards is a second path with its own arithmetic, and the two
    # disagreed by 0.03 on a synthetic market that re-dates per call.
    used: dict = {}
    real_fill = ledger.Ledger.fill_benchmarks

    def capture(self, frames, through=None, universe=None, calendar=None):
        used.update(frames)
        return real_fill(self, frames, through, universe, calendar)

    monkeypatch.setattr(ledger.Ledger, "fill_benchmarks", capture)

    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(0))
    pipeline.run("evening", dry_run=True)

    book = recorded(tmp_path)
    older = next(r for r in book["runs"] if r["date"] == first_session)
    assert set(used) == set(names), "every name the scan read, burst or not"
    # Over the names at or above THAT night's floor: rule 6's bar, kept in
    # the run entry, applied to each frame's own dollar volume on the session
    # -- recomputed here from the bars rather than asked of the module.
    floor = older["liquidity"]["floor"]
    traded = {name: float(f.loc[first_session, "Close"]) * float(f.loc[first_session, "Volume"])
              for name, f in used.items()}
    kept = [name for name, dv in traded.items() if round(dv) >= floor]
    # The double re-dates every frame per request, so tonight's bar for the
    # earlier session is not the bar the floor was set against, and how many
    # fall under it is the market's business; that some do and not all is
    # the precondition, and the mean over the rest is the claim.
    assert 1 <= len(names) - len(kept) < len(names), "precondition: the floor bites and spares someone"
    by_hand = [ledger.forward_returns(used[name], first_session) for name in kept]
    closes = [r["d1"] for r in by_hand if r["d1"] is not None]
    opens = [r["from_open"]["d1"] for r in by_hand if r["from_open"]["d1"] is not None]
    assert older["benchmark"]["d1"] == round(sum(closes) / len(closes), 2)
    assert older["benchmark"]["n1"] == len(kept) == len(closes)
    assert older["benchmark"]["from_open"]["d1"] == round(sum(opens) / len(opens), 2)
    assert older["benchmark"]["liquidity_floor"] == floor, "stamped with the floor it applied"
    assert older["benchmark"]["below_floor"] == len(names) - len(kept)
    assert older["benchmark"]["d3"] is None, "three sessions have not passed"
    assert older["benchmark"]["universe"] == older["universe"], (
        "stamped with the basket it was measured over, which is this run's own")
    assert len(mocked_boundaries["alpaca"].bar_requests) - before == 1 + 1, (
        "the scan's own batch and the forward-returns fetch; the benchmark cost no request")
    assert published(tmp_path)["evidence"]["universe"]["setups"] >= 1


def test_a_tickers_run_neither_gives_a_benchmark_nor_gets_one(
    monkeypatch, market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """THE defect this rule exists for. The smoke test README documents is
    `--tickers BURST`, and the fill took whatever the caller had scanned: it
    measured one frame against the previous night's run, which had SCORED
    BURST -- so the alternative the north star is measured against became
    the pick itself, at n=1, and was never corrected, because a measured
    horizon keeps its value. A run with no universe offers no benchmark and
    receives none; the earlier night's stays pending until a real scan of
    the universe IT scanned comes along, which is the honest answer."""
    names = _five_name_market(fake_alpaca, ohlcv)
    _universe_file(monkeypatch, tmp_path, names)
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(-1))
    pipeline.run("evening", dry_run=True)
    scored_that_night = [c["ticker"] for c in recorded(tmp_path)["runs"][0]["candidates"]]
    assert "BURST" in scored_that_night, "precondition: the name the smoke test names was scored"

    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(0))
    pipeline.run("evening", dry_run=True, tickers=["BURST"])

    book = recorded(tmp_path)
    older = next(r for r in book["runs"] if r["date"] == session_offset(-1))
    assert older["benchmark"] == ledger.empty_benchmark(), (
        "one name is not a market, and its return is not anyone's alternative")
    smoke = next(r for r in book["runs"] if r["date"] == session_offset(0))
    assert smoke["benchmark"] == ledger.empty_benchmark()
    rung = published(tmp_path)["evidence"]["universe"]
    assert all(entry["n"] == 0 for entry in rung["outcomes"]), "nothing measured, rather than the pick"

    # Nor does a SECOND --tickers run on the same names benchmark the first:
    # their universe labels match each other, so label-matching alone would
    # let one smoke test become the other's alternative. Running the
    # documented smoke test twice is not an exotic state.
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(1))
    pipeline.run("evening", dry_run=True, tickers=["BURST"])
    for entry in recorded(tmp_path)["runs"]:
        assert entry["benchmark"] == ledger.empty_benchmark(), entry["date"]

    # And a genuine scan of that universe afterwards still fills it.
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(2))
    pipeline.run("evening", dry_run=True)
    older = next(r for r in recorded(tmp_path)["runs"] if r["date"] == session_offset(-1))
    assert older["benchmark"]["d1"] is not None
    assert older["benchmark"]["n1"] == len(names) - older["benchmark"]["below_floor"] < len(names), (
        "over the names at or above that night's floor")


def test_a_liquidity_refused_row_carries_the_streak_the_run_read_for_it(
    monkeypatch, market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The streak lookup covered the kept candidates and not the refused
    ones, so every liquidity_floor row was archived with streak: null -- the
    value the contract reserves for a run that could NOT read its history --
    one line under a lynch_gate row carrying a full block from the same
    read. The page rendered "streak unknown -- this run recorded none" for
    a run that demonstrably read its history. Two nights: the first records
    the honest no_history block, the second remembers the first and says
    what became of it, in the fourth reason word."""
    names = _two_bursts_one_thin(fake_alpaca, ohlcv)
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(-1))
    pipeline.run("evening", dry_run=True, tickers=names)
    (thin,) = published(tmp_path)["gated_out"]
    assert thin["reason"] == ledger.LIQUIDITY_REASON
    assert isinstance(thin["streak"], dict), "the row carries the block the run read, not null"
    assert thin["streak"]["unknown_reason"] == ledger.NO_HISTORY and thin["streak"]["seen_before"] == 0
    assert thin["dollar_volume"] == recorded(tmp_path)["runs"][0]["gated"][0]["dollar_volume"], (
        "and the ledger row keeps the number rule 6 judged")

    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(0))
    pipeline.run("evening", dry_run=True, tickers=names)

    (thin,) = published(tmp_path)["gated_out"]
    assert thin["streak"]["seen_before"] == 1 and thin["streak"]["last_outcome"] == ledger.LIQUIDITY_REASON
    assert thin["streak"]["last_seen"] == session_offset(-1)


def test_the_morning_re_presents_the_liquidity_refusals_the_evening_recorded(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The follow-through reads the funnel off the snapshot's own rows, and
    the floor it prints is the one THAT run recorded."""
    names = _two_bursts_one_thin(fake_alpaca, ohlcv)
    pipeline.run("evening", dry_run=True, tickers=names)
    floor = published(tmp_path)["run"]["liquidity"]["floor"]
    market_clock.before_the_open()

    pipeline.run("morning", dry_run=False)

    html = visible(mocked_boundaries["resend"].sent[-1]["html"])
    assert f"Below the liquidity floor ({emailer.compact_dollars(floor)}/day" in html and "4% bursts that session: 2" in html


def test_a_night_every_burst_was_below_the_floor_says_so_and_never_blames_the_checklist(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """One thin burst among fat non-bursting names: the scan found one burst
    and rule 6 refused it. The note under the empty table must say that,
    not that the checklist rejected it, and not that the market was quiet."""
    from tests.test_scanner import _thin

    fake_alpaca.add_history("THIN", _thin(ohlcv, "burst", price=5.0, volume=200_000, variant=1))
    names = ["THIN"]
    for i in range(8):
        fake_alpaca.add_history(f"Q{i}", _thin(ohlcv, "flat", price=80.0, volume=2_000_000, variant=i + 2))
        names.append(f"Q{i}")

    pipeline.run("evening", dry_run=False, tickers=names)

    data = published(tmp_path)
    assert data["run"]["bursts"] == 1 and data["candidates"] == []
    html = visible(mocked_boundaries["resend"].sent[-1]["html"])
    assert "The one burst the scan found was below the liquidity floor. The checklist never got a say." in html
    assert "No candidate passed the 2LYNCH checklist" not in html and "quiet market" not in html


def test_the_record_says_what_each_run_scanned(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """README documents a four-ticker --tickers run as the local smoke test,
    and that run writes docs/ledger.json like any other: one row per name,
    read as history by the next real run on another session, committed by
    the next `git add docs`. The row used to carry nothing that told it from
    a scan -- data.json's headline said "named on the command line" and the
    ledger entry beside it said nothing -- so the record could not answer
    whether a streak, or a scored setup in the evidence, came from a night
    that scanned the universe. Every entry carries its universe now, in the
    ledger and in the runs table the page reads."""
    snapshot = evening_run(tmp_path, fake_alpaca, ohlcv)

    (entry,) = recorded(tmp_path)["runs"]
    assert entry["universe"] == snapshot["run"]["universe"]
    assert "named on the command line" in entry["universe"]["label"]
    assert entry["universe"]["size"] == 1
    (run,) = snapshot["runs"]
    assert run["universe"] == entry["universe"], "the page's runs table drops the marker"
    # And it survives a reload as the shape it was written in: a later run
    # reads this entry back, and the marker is only useful if it is still
    # there for a reader of the file the commit-back keeps.
    book = ledger.Ledger(tmp_path / "docs").load()
    assert book.runs[0]["universe"] == entry["universe"]


def test_a_delivery_failure_is_written_into_the_record_it_leaves_behind(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """Exit 3 keeps the record -- and the record said run.status "ok" with
    errors [], so the page and the next morning presented the night as clean
    and nothing in it said the shortlist never arrived. Only the Actions
    colour knew. The failure is stamped into both files before it is raised."""
    import resend

    names = _wide_universe(fake_alpaca, ohlcv, fresh=3)
    monkeypatch.setattr(sys, "argv", ["pipeline", "evening", "--tickers", ",".join(names)])
    monkeypatch.setattr(resend.Emails, "send", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("The example.invalid domain is not verified.")))

    with pytest.raises(SystemExit) as exc:
        pipeline.main()

    assert exc.value.code == pipeline.EXIT_FAILED_AFTER_PUBLISH, "the exit code is unchanged"
    data = clean(tmp_path)
    assert data["run"]["status"] == "degraded"
    assert any(e["stage"] == "email" and "not delivered" in e["message"] for e in data["run"]["errors"])
    ledger_file = json.loads((tmp_path / "docs" / "ledger.json").read_text())
    assert ledger_file["runs"][0]["status"] == "degraded"


def test_a_lunchtime_evening_dispatch_re_presents_the_published_session_instead_of_re_scanning(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """A Run-workflow click before the close, to test the secrets, is an
    evening run whose newest completed session is YESTERDAY's -- which the
    ledger already holds as a clean run. It used to re-scan it, pay Claude
    again, and hand add_run() a DEGRADED entry that replaced the clean one;
    exit 2 qualifies for the commit-back, so the overwrite reached the branch.
    Reproduced: ok -> degraded, six Claude calls for one session."""
    names = _wide_universe(fake_alpaca, ohlcv, fresh=3)
    market_clock.after_the_close()
    pipeline.run("evening", dry_run=False, tickers=names)
    ledger_of = lambda: [(r["date"], r["status"]) for r in   # noqa: E731
                         json.loads((tmp_path / "docs" / "ledger.json").read_text())["runs"]]
    assert ledger_of() == [ledger_of()[0]] and ledger_of()[0][1] == "ok"
    paid = len(mocked_boundaries["anthropic"].calls)

    market_clock.before_the_open()          # the next day at lunch: not closed
    report = pipeline.RunReport()
    pipeline.run("evening", dry_run=False, tickers=names, report=report)

    assert ledger_of()[0][1] == "ok", "the clean record was replaced by a degraded re-scan"
    assert len(mocked_boundaries["anthropic"].calls) == paid, "and the session was paid for twice"
    assert report.exit_code == pipeline.EXIT_DEGRADED, "the clock disagreement is still reported"
    assert any("already published" in e["message"] for e in report.errors)
    assert "follow-through" in mocked_boundaries["resend"].sent[-1]["subject"].lower()


def test_a_backfill_does_not_make_the_morning_say_nothing_has_published(
    monkeypatch, market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """SCAN_SESSION_DATE is README's way to seed a history. It rewrote
    docs/data.json's headline to the OLDER session while the same file's
    `runs` still listed last night, and the next morning announced that
    nothing had published for three sessions -- over a file naming the newer
    run two lines further down. The record gains the backfill; the headline
    keeps the newest session."""
    names = _wide_universe(fake_alpaca, ohlcv, fresh=3)
    market_clock.after_the_close()
    pipeline.run("evening", dry_run=True, tickers=names)
    tonight = clean(tmp_path)["run"]["date"]

    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(-3))
    pipeline.run("evening", dry_run=True, tickers=names)
    monkeypatch.delenv("SCAN_SESSION_DATE")

    data = clean(tmp_path)
    assert data["run"]["date"] == tonight, "the headline moved to the backfilled session"
    assert [r["date"] for r in data["runs"]] == [tonight, session_offset(-3)], "and the record has both"

    market_clock.before_the_open()
    report = pipeline.RunReport()
    pipeline.run("morning", dry_run=False, report=report)

    subject = mocked_boundaries["resend"].sent[-1]["subject"]
    assert "NOTHING PUBLISHED" not in subject, subject
    assert report.exit_code == pipeline.EXIT_OK, [e["message"] for e in report.errors]


@pytest.mark.parametrize("mutation", ["checks_list", "ticker_list", "date_list", "d5_string"])
def test_a_ledger_row_shaped_one_level_wrong_cannot_kill_the_run_after_claude_was_paid(
    mutation, market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The sixth instance of the class, driven through the real evening path
    the way the fifth was: publish a run, bend ONE stored row on disk, run
    again. Each of these loaded clean and crashed at archive -- after the scan
    and every Claude call -- and was never set aside, so the next night died
    the same way. Now: refused at load, set aside, exit 2, record written."""
    names = _wide_universe(fake_alpaca, ohlcv, fresh=2)
    market_clock.after_the_close()
    pipeline.run("evening", dry_run=True, tickers=names)
    path = tmp_path / "docs" / "ledger.json"
    led = json.loads(path.read_text())
    run = led["runs"][0]
    run["date"] = session_offset(-5)
    for row in run["candidates"] + run["gated"]:
        row["date"] = session_offset(-5)
    row = run["candidates"][0]
    {"checks_list": lambda: row.__setitem__("checks", ["2", "L"]),
     "ticker_list": lambda: row.__setitem__("ticker", ["F0"]),
     "date_list": lambda: row.__setitem__("date", [session_offset(-5)]),
     "d5_string": lambda: row["forward_returns"].__setitem__("d5", "1.2")}[mutation]()
    path.write_text(json.dumps(led))
    report = pipeline.RunReport()

    pipeline.run("evening", dry_run=True, tickers=names, report=report)   # must not raise

    assert report.exit_code == pipeline.EXIT_DEGRADED
    assert any("set aside" in e["message"] or "could not be read" in e["message"] for e in report.errors)
    assert len(ledger.quarantined(tmp_path / "docs")) == 1
    assert json.loads(path.read_text())["runs"], "and tonight's record was written"


def test_a_morning_with_nothing_to_read_invents_no_market_counts(
    market_clock, mocked_boundaries, tmp_path
):
    """The guaranteed state of the first production morning: docs/data.json
    is the fixture (refused by name) or absent. The funnel printed "4% bursts
    that session: 0 | Passed 2LYNCH gate: 0" under a session it called "not
    recorded" -- two invented counts three lines above a cell saying this is
    not a statement about the market."""
    market_clock.before_the_open()

    pipeline.run("morning", dry_run=False)

    text = visible(mocked_boundaries["resend"].sent[-1]["html"])
    assert "4% bursts that session: not recorded" in text
    assert "Passed 2LYNCH gate: not recorded" in text
    assert "4% bursts that session: 0" not in text


def test_the_morning_email_shows_a_candidate_exactly_as_the_evening_one_did(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """One name, two emails a night apart, and the checklist lines and the
    three numbers read differently: the evening path prints src.lynch's own
    lines and raw floats, the morning rebuilt the lines off disk with the
    code and label split ("PASS  2 first or second burst") and printed values
    ledger._num() had turned to ints ("+12%", "8x", "7/10"). The reader who
    gets both sees two vocabularies for one judgement."""
    names = _wide_universe(fake_alpaca, ohlcv, fresh=2)
    market_clock.after_the_close()
    pipeline.run("evening", dry_run=False, tickers=names)
    evening = visible(mocked_boundaries["resend"].sent[-1]["html"])

    market_clock.before_the_open()
    pipeline.run("morning", dry_run=False)
    morning = visible(mocked_boundaries["resend"].sent[-1]["html"])

    def cells(text: str, ticker: str) -> str:
        # from the ticker to the next candidate's rank marker or the table's end
        start = text.index(f"1. {ticker}") if f"1. {ticker}" in text else text.index(ticker)
        chunk = text[start:start + 700]
        return chunk.split(" 2. ")[0]

    for ticker in names[:1]:
        e, m = cells(evening, ticker), cells(morning, ticker)
        for line in ("PASS  2_", "FAIL  2_", "PASS  L_", "FAIL  L_"):
            assert (line in e) == (line in m), (line, e[:200], m[:200])
        for token in ("_first_or_second_burst", "%", "x"):
            assert token in e and token in m
        import re
        assert re.findall(r"[+-]\d+\.\d%", e)[:1] == re.findall(r"[+-]\d+\.\d%", m)[:1], "the gain"
        assert re.findall(r"\d+\.\d\dx", e)[:1] == re.findall(r"\d+\.\d\dx", m)[:1], "the ratio"
        assert re.findall(r"\d+\.\d/10", e)[:1] == re.findall(r"\d+\.\d/10", m)[:1], "the score"


def test_a_delivery_failure_keeps_the_night_the_run_already_paid_for(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The record is written BEFORE the email, and 1 was hiding that.

    A run that dies delivering -- an unverified RESEND_FROM domain is the
    likely one, and the message below is the one Resend actually returns --
    has already scanned, rendered every chart, paid for every Claude call and
    written a complete docs/data.json and docs/ledger.json. It exited 1, the
    same code as a preflight that spent nothing, and evening.yml reasonably
    read 1 as "nothing trustworthy to commit" and skipped the persist step.

    Exactly the defect the degraded-run fix closed, one stage later. This is
    the code that tells the two nights apart; the workflow half is pinned in
    tests/test_docs_are_true.py.
    """
    import resend

    names = _wide_universe(fake_alpaca, ohlcv, fresh=3)
    monkeypatch.setattr(sys, "argv", ["pipeline", "evening", "--tickers", ",".join(names)])

    def refuse(params, options=None):
        raise RuntimeError("The example.invalid domain is not verified. Please add "
                           "and verify your domain on https://resend.com/domains")
    monkeypatch.setattr(resend.Emails, "send", refuse)

    with pytest.raises(SystemExit) as exc:
        pipeline.main()

    assert exc.value.code == pipeline.EXIT_FAILED_AFTER_PUBLISH
    assert exc.value.code != pipeline.EXIT_OK, "the job must still go red"

    data = clean(tmp_path)
    assert data["run"]["bursts"] == 3 and len(data["candidates"]) == 3, (
        "the night that was paid for is on disk, complete"
    )
    ledger_file = json.loads((tmp_path / "docs" / "ledger.json").read_text())
    assert len(ledger_file["runs"]) == 1
    assert len(ledger_file["runs"][0]["candidates"]) == 3
    assert len(mocked_boundaries["anthropic"].calls) == 3, "and it was paid for"


def test_a_failure_before_the_record_exists_is_still_a_plain_failure(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The other side, and the reason the new code is a THIRD one rather than
    a widening of the persist condition to "any non-zero". A preflight that
    spent nothing has no record to keep, and must not claim one -- the
    workflow would commit whatever docs/ the checkout happened to carry and
    call it tonight's run."""
    names = _wide_universe(fake_alpaca, ohlcv, fresh=3)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["pipeline", "evening", "--tickers", ",".join(names)])

    with pytest.raises(SystemExit) as exc:
        pipeline.main()

    assert exc.value.code == pipeline.EXIT_FAILED
    assert not (tmp_path / "docs" / "data.json").exists(), "nothing was published"
    assert mocked_boundaries["anthropic"].calls == [], "and nothing was spent"


def test_a_burst_the_call_cap_dropped_says_so_rather_than_disappearing(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The other way a burst goes unscored, and the two must not look alike:
    one failed the checklist, the other simply cost too much to score."""
    monkeypatch.setattr(pipeline, "MAX_TO_SCORE", 1)
    names = _wide_universe(fake_alpaca, ohlcv, fresh=3)

    pipeline.run("evening", dry_run=True, tickers=names)

    data = clean(tmp_path)
    assert data["run"]["bursts"] == 3
    assert data["run"]["passed_gate"] == 3, "all three cleared the gate"
    assert data["run"]["scored"] == 1 and data["run"]["score_cap"] == 1
    assert [g["reason"] for g in data["gated_out"]] == ["score_cap", "score_cap"]


def _perfect_burst(ohlcv, **kwargs):
    """The first synthetic burst frame that passes all six checks.

    Searched for rather than written down as a variant number: the `ohlcv`
    fixture seeds from the TEST's own name, so the variant that scores 6/6
    here scores something else in the next test and a number written in would
    rot the first time either was renamed. The search is deterministic, and it
    raises rather than falling back to a weaker frame -- a test about a rule
    that overrules a perfect checklist proves nothing on a 5/6 one.
    """
    for variant in range(80):
        frame = ohlcv("burst", variant=variant, **kwargs)
        if lynch.evaluate_2lynch(frame)["passes"] == 6:
            return frame
    raise AssertionError(f"no 6/6 burst frame in 80 variants of {kwargs}")


def test_a_burst_an_absolute_rule_refused_never_reaches_the_scorer(
    fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The third way a burst goes unscored, and the one that must not look like
    either of the others: the checklist was happy with it.

    Both names here pass 6/6. One of them burst three sessions into a run up,
    which Bonde refuses outright -- so it is dropped BEFORE the pass count is
    consulted, no scoring call is made for it, and the archived row names the
    rule rather than the gate. If the veto were a seventh checklist item this
    name would score 6/7 and be scored.
    """
    # Three names, not two: the liquidity percentile gate needs a population
    # to take a percentile OF, and it drops one of any pair.
    names = ["KEEP0", "KEEP1", "DRIFT"]
    for i, ticker in enumerate(names[:2]):
        fake_alpaca.add_history(ticker, ohlcv("burst", variant=i, up_run=2))
    fake_alpaca.add_history("DRIFT", _perfect_burst(
        ohlcv, up_run=lynch.MAX_CONSECUTIVE_UP_DAYS + 1))

    pipeline.run("evening", dry_run=True, tickers=names)

    data = clean(tmp_path)
    assert data["run"]["bursts"] == 3
    assert data["run"]["passed_gate"] == 2, "the vetoed name never reached the gate"
    assert sorted(c["ticker"] for c in data["candidates"]) == ["KEEP0", "KEEP1"]

    (refused,) = data["gated_out"]
    assert refused["ticker"] == "DRIFT"
    assert refused["reason"] == pipeline.VETO_REASONS["up_days"]
    assert refused["lynch_passes"] == refused["lynch_total"], (
        "this row only proves anything if the checklist passed it")
    assert [call["ticker"] for call in mocked_boundaries["anthropic"].calls
            if "ticker" in call] == [], "and nothing was paid for either name"
    assert "DRIFT" not in json.dumps(mocked_boundaries["anthropic"].calls)


def test_a_vetoed_burst_outranks_the_checklist_as_the_reason_it_went_unscored(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """A name that breaks the veto AND fails the checklist reports the veto.

    The order is the judgement: "rejected at the 2LYNCH gate" would name the
    weaker of two reasons and hide the cardinal one, and the reader would have
    no way to tell this row from the sixteen that simply were not good enough.
    """
    monkeypatch.setattr(pipeline, "MIN_LYNCH_PASSES", 99)
    names = ["BOTH0", "BOTH1", "BOTH2"]
    for i, ticker in enumerate(names):
        fake_alpaca.add_history(ticker, ohlcv("burst", variant=i,
                                              up_run=lynch.MAX_CONSECUTIVE_UP_DAYS + 1))

    pipeline.run("evening", dry_run=True, tickers=names)

    gated = clean(tmp_path)["gated_out"]
    assert gated, "the scan found nothing to refuse, so this proves nothing"
    for refused in gated:
        assert refused["lynch_passes"] < 99, "this name really does fail the checklist too"
        assert refused["reason"] == pipeline.VETO_REASONS["up_days"]


def test_the_run_records_which_absolute_rules_it_applied(
    fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """docs/index.html reads this to decide whether to tell the reader that a
    veto could have cut a name at the gate stage. A snapshot written before the
    rule existed carries no such list, and the page must not name a rule that
    run did not enforce -- so the list has to be what the run really applied,
    not a constant the page could have hard-coded."""
    names = _wide_universe(fake_alpaca, ohlcv, fresh=3)

    pipeline.run("evening", dry_run=True, tickers=names)

    gate = clean(tmp_path)["run"]["gate"]
    assert gate["vetoes"] == list(pipeline.VETO_REASONS)
    assert gate["vetoes"], "a run that applied no absolute rule would say so with []"


def test_every_reason_a_burst_can_carry_can_be_said_in_words_on_both_surfaces():
    """A reason word nothing can render is a row the reader is told nothing
    about. The email and the page each hold their own copy of this vocabulary
    -- they are different languages -- so the guard is that both are complete,
    not that one is derived from the other.

    This is the check that makes adding a veto safe: src.pipeline names the
    rule, and this fails until both surfaces can say it.
    """
    page = (pathlib.Path(pipeline.__file__).resolve().parent.parent
            / "docs" / "index.html").read_text()

    for reason in list(pipeline.VETO_REASONS.values()) + ["lynch_gate", "score_cap"]:
        assert emailer.LAST_OUTCOME.get(reason), f"src/emailer.py cannot say {reason}"
        for table in ("LAST_OUTCOME", "OUTCOME_SHORT"):
            block = page.split("var " + table + " = {", 1)[1].split("};", 1)[0]
            assert f"{reason}:" in block, f"docs/index.html's {table} cannot say {reason}"


def test_the_chart_a_candidate_carries_is_one_the_page_can_serve(
    universe, mocked_boundaries, open_gate, tmp_path
):
    """`charts/BURST.png` relative to docs/, not the repo-root charts/ that
    GitHub Pages does not publish and .gitignore drops."""
    pipeline.run("evening", dry_run=True, tickers=universe)

    (burst,) = [c for c in clean(tmp_path)["candidates"] if c["ticker"] == "BURST"]
    assert burst["chart"] == "charts/BURST.png"
    assert (tmp_path / "docs" / burst["chart"]).is_file()
    assert burst["chart_error"] is None
    assert burst["provenance"]["chart_seen"] is True


def test_a_chart_that_failed_to_render_is_null_with_the_reason_on_the_row(
    monkeypatch, universe, mocked_boundaries, open_gate, tmp_path
):
    """The candidate is still scored, and the row says it was scored blind."""
    monkeypatch.setattr(pipeline, "render_chart",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("no renderer")))

    pipeline.run("evening", dry_run=True, tickers=universe)

    (burst,) = [c for c in clean(tmp_path)["candidates"] if c["ticker"] == "BURST"]
    assert burst["chart"] is None
    assert "no renderer" in burst["chart_error"]
    assert burst["provenance"]["chart_seen"] is False


def test_a_fallback_is_labelled_as_one_everywhere_it_is_archived(
    universe, mocked_boundaries, open_gate, tmp_path
):
    """A checklist score is not a judgement anybody made. The archive is the
    input to the backtest, so a row nobody reviewed must never read as one
    that was."""
    mocked_boundaries["anthropic"].set_error(RuntimeError("Error code: 401 - invalid x-api-key"))

    pipeline.run("evening", dry_run=True, tickers=universe)

    data = clean(tmp_path)
    (burst,) = [c for c in data["candidates"] if c["ticker"] == "BURST"]
    assert burst["provenance"] == {"source": "fallback", "model": None,
                                   "chart_seen": False,
                                   "error": "RuntimeError: Error code: 401 - invalid x-api-key"}
    assert data["run"]["scored_by"] == {"claude": 0, "fallback": 1}
    assert recorded(tmp_path)["runs"][0]["candidates"][0]["source"] == "fallback"
    assert recorded(tmp_path)["runs"][0]["fallbacks"] == 1


def test_a_second_run_keeps_the_first_and_fills_its_forward_returns(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The point of the exercise: a score recorded on one session, and what
    the market did afterwards recorded against it by a later run.

    Every expected number is recomputed here from the bars the double served,
    not read back from the writer under test.
    """
    fake_alpaca.add_history("BURST", ohlcv("burst"))
    burst_session, next_session = session_offset(-2), session_offset(3)

    monkeypatch.setenv("SCAN_SESSION_DATE", burst_session)
    pipeline.run("evening", dry_run=True, tickers=["BURST"])

    first = recorded(tmp_path)["runs"][0]["candidates"][0]
    want_d1 = expected_returns(served(fake_alpaca, "BURST", session_offset(0)),
                               burst_session, horizons=(1,))
    assert first["forward_returns"]["d1"] == want_d1["d1"], "one session had closed"
    assert first["forward_returns"]["d3"] is None, "the others had not"
    assert first["forward_returns"]["from_open"]["d1"] == want_d1["from_open"]["d1"], (
        "and the open basis closed with it, from the next session's open")
    assert first["forward_returns"]["from_open"]["d3"] is None

    # ...and now it is three sessions later.
    monkeypatch.setenv("SCAN_SESSION_DATE", next_session)
    pipeline.run("evening", dry_run=True, tickers=["BURST"])

    book = recorded(tmp_path)
    assert [r["date"] for r in book["runs"]] == [next_session, burst_session], (
        "the earlier run is still in the ledger")
    older = book["runs"][1]["candidates"][0]
    want = expected_returns(served(fake_alpaca, "BURST", next_session), burst_session)
    assert older["forward_returns"]["d1"] == first["forward_returns"]["d1"], (
        "a horizon already measured is not restated")
    assert (older["forward_returns"]["d3"], older["forward_returns"]["d5"]) == (
        want["d3"], want["d5"])
    assert older["forward_returns"]["as_of"] == next_session
    # `n` is the SETUPS the mean was taken over and `rows` is what they were
    # collapsed from -- one candidate here, so the two agree and the pair says
    # nothing was deduplicated away.
    assert older["forward_returns"]["from_open"] == {
        "d1": first["forward_returns"]["from_open"]["d1"],
        "d3": want["from_open"]["d3"], "d5": want["from_open"]["d5"]}, (
        "the open basis fills the same way: the recorded horizon kept, the rest measured")
    assert book["runs"][1]["forward_returns"] == {
        "d1": first["forward_returns"]["d1"], "d3": want["d3"], "d5": want["d5"],
        "n": 1, "rows": 1,
        "from_open": {"d1": first["forward_returns"]["from_open"]["d1"],
                      "d3": want["from_open"]["d3"], "d5": want["from_open"]["d5"], "n": 1}}
    assert clean(tmp_path)["runs"][1]["forward_returns"]["d5"] == want["d5"], (
        "and the dashboard reads the same history")


def test_a_run_that_scans_an_old_session_resolves_its_own_outcomes(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """SCAN_SESSION_DATE points at a session whose next week has already
    happened, so the candidates this run scores are measurable immediately.
    That is how a history is seeded without waiting a year for one."""
    fake_alpaca.add_history("BURST", ohlcv("burst"))
    burst_session = session_offset(-6)
    monkeypatch.setenv("SCAN_SESSION_DATE", burst_session)

    pipeline.run("evening", dry_run=True, tickers=["BURST"])

    (candidate,) = clean(tmp_path)["candidates"]
    want = expected_returns(served(fake_alpaca, "BURST", session_offset(0)), burst_session)
    assert candidate["forward_returns"] == {**want, "as_of": session_offset(-1)}


def test_todays_candidates_are_published_pending_rather_than_guessed(
    universe, mocked_boundaries, open_gate, tmp_path
):
    """The inverse of the two above. Tonight's burst closed at tonight's
    close; there is no session after it yet, and a 0 in that field would be a
    return the market never printed."""
    pipeline.run("evening", dry_run=True, tickers=universe)

    data = clean(tmp_path)
    assert all(c["forward_returns"] == ledger.empty_returns() for c in data["candidates"]), (
        "pending on both bases")
    assert data["runs"][0]["forward_returns"] == {"d1": None, "d3": None, "d5": None,
                                                  "n": 0, "rows": 0,
                                                  "from_open": {"d1": None, "d3": None, "d5": None, "n": 0}}
    assert len(mocked_boundaries["alpaca"].bar_requests) == 1, (
        "and no second request was made for returns that cannot exist")


def test_a_failed_forward_return_fetch_degrades_the_run_but_still_publishes(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """A ledger that silently stops accumulating outcomes is exactly the class
    of failure step 5 exists to end -- and the run itself is still worth
    publishing and mailing."""
    fake_alpaca.add_history("OLD", ohlcv("burst"))
    fake_alpaca.add_history("NEW", ohlcv("burst", variant=1))
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(-2))
    pipeline.run("evening", dry_run=True, tickers=["OLD"])

    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(3))
    fake_alpaca.raise_on_bars = ConnectionError("connection reset by peer")
    fake_alpaca.fail_symbols = {"OLD"}          # the scan of NEW still succeeds
    report = pipeline.RunReport()

    scored = pipeline.run("evening", dry_run=True, tickers=["NEW"], report=report)

    assert scored, "the run that just happened is unaffected"
    assert report.status == "degraded"
    (problem,) = [e for e in report.errors if e["stage"] == "archive"]
    assert "forward returns" in problem["message"] and "connection reset" in problem["message"]

    data = clean(tmp_path)
    assert data["run"]["errors"] == report.errors, "the file says so too"
    older = recorded(tmp_path)["runs"][1]["candidates"][0]
    assert older["forward_returns"]["d3"] is None, "still pending, not zeroed"


def test_the_ledger_row_is_the_judgement_next_to_what_followed_it(
    universe, mocked_boundaries, open_gate, tmp_path
):
    """What a backtest needs from one row, and the reason this file exists."""
    pipeline.run("evening", dry_run=True, tickers=universe)

    (row,) = [r for r in recorded(tmp_path)["runs"][0]["candidates"]
              if r["ticker"] == "BURST"]
    assert set(row) == {"ticker", "date", "rank", "score", "verdict", "source", "dollar_volume",
                        "close", "gain_pct", "volume_ratio", "lynch_passes",
                        "lynch_total", "checks", "context", "forward_returns"}
    assert set(row["checks"]) == {"2", "L", "Y", "N", "C", "H"}
    assert sum(row["checks"].values()) == row["lynch_passes"]
    # `context` is here because the ledger is the only file that survives the
    # next run, and everything in it was measured BEFORE the outcome beside it.
    # Two of this screener's rules -- the up-days veto and the base-breakdown
    # criterion -- are justified by being evaluable later, and until this key
    # was kept there was nowhere for that evidence to accumulate.
    assert {"consecutive_up_days", "worst_base_day_pct"} <= set(row["context"])
    assert all(v is None or isinstance(v, (int, float)) for v in row["context"].values())


# ===========================================================================
# Step 10 -- the mode means something, and a repeat looks like one.
#
# `run_type` used to change four cosmetic things and nothing else: both modes
# ran the identical scan, and WHICH session that scan read was decided
# entirely by the wall clock. Nothing compared the two, so `evening` before
# the close scanned yesterday and mailed it as tonight's candidates, and
# `morning` after the close mailed a watchlist for a day that had finished.
#
# Every test here uses the `market_clock` fixture at the top of this file to
# say which side of the 16:15 ET close it is on. The predicate itself is
# pinned in tests/test_scanner.py, against real instants.
# ===========================================================================

MORNING = pipeline.MODES["morning"]
EVENING = pipeline.MODES["evening"]

#: 11:00 and 18:30 ET on a Tuesday: one side of the close each.
BEFORE = datetime(2026, 9, 1, 11, 0, tzinfo=scanner.MARKET_TZ)
AFTER = datetime(2026, 9, 1, 18, 30, tzinfo=scanner.MARKET_TZ)


# --- the check itself ------------------------------------------------------


def test_a_mode_on_the_side_of_the_close_it_belongs_on_reports_nothing():
    """The precondition for all four below: a disagreement is not simply what
    this function always says."""
    assert pipeline.session_disagreement(EVENING, ScanConfig(), now=AFTER) is None
    assert pipeline.session_disagreement(MORNING, ScanConfig(), now=BEFORE) is None


def test_an_evening_run_before_the_close_says_which_session_it_really_read():
    """The defect, in one sentence: this run scans YESTERDAY and used to mail
    it as tonight's candidates with today's date on it."""
    said = pipeline.session_disagreement(EVENING, ScanConfig(), now=BEFORE)

    assert said is not None
    assert "has not closed yet" in said
    assert str(scanner.current_session(BEFORE)) in said, "and names the session it read"


def test_a_morning_run_after_the_close_says_it_is_not_a_pre_open_pass():
    said = pipeline.session_disagreement(MORNING, ScanConfig(), now=AFTER)
    assert said is not None and "already closed" in said


def test_a_pinned_session_is_the_user_overruling_the_clock_on_purpose():
    """SCAN_SESSION_DATE is how README says to seed a history, and a
    deliberate backfill must not be reported as a mistake -- a warning that
    fires on a documented workflow teaches a reader to ignore it."""
    pinned = ScanConfig(session_date=date(2026, 8, 24))

    assert pipeline.session_disagreement(EVENING, pinned, now=BEFORE) is None
    assert pipeline.session_disagreement(MORNING, pinned, now=AFTER) is None


def test_a_pinned_session_is_the_session_both_modes_are_about():
    """One definition of "which session is this run about", so a pin cannot
    mean the scanned session in one place and be ignored in the other."""
    pinned = ScanConfig(session_date=date(2026, 8, 24))
    assert pipeline.expected_session(pinned, now=AFTER) == date(2026, 8, 24)
    assert pipeline.expected_session(ScanConfig(), now=AFTER) == scanner.current_session(AFTER)


def test_the_two_modes_disagree_about_the_clock_in_opposite_directions():
    """Each mode is on exactly one side, and they are not the same side --
    a Mode table where both said the same thing would pass every test above
    while making the run type mean nothing again."""
    assert EVENING.after_the_close is not MORNING.after_the_close
    assert EVENING.scans and not MORNING.scans


def test_an_unknown_run_type_names_the_ones_that_exist():
    with pytest.raises(ValueError, match="morning"):
        pipeline.mode_for("afternoon")


# --- what the run does about it --------------------------------------------


def test_an_evening_run_before_the_close_degrades_and_says_so_everywhere(
    monkeypatch, market_clock, universe, mocked_boundaries, open_gate, tmp_path
):
    """Degraded, not refused: refusing trades a mislabelled email for no
    email, and no email is indistinguishable from a market holiday. The
    reason has to reach all four places an operator might look."""
    market_clock.before_the_open()
    report = pipeline.RunReport()

    scored = pipeline.run("evening", dry_run=False, tickers=universe, report=report)

    assert scored, "the scan still happened and is still worth reading"
    assert report.status == "degraded" and report.exit_code == pipeline.EXIT_DEGRADED
    # EXACTLY the session problem, not "at least" it: a test that accepted a
    # longer list would pass while a stale scan or a failed chart did the
    # degrading and the clock check had been deleted.
    assert [e["stage"] for e in report.errors] == ["session"], report.errors
    (problem,) = report.errors
    assert "has not closed yet" in problem["message"]
    # the email
    (sent,) = mocked_boundaries["resend"].sent
    assert sent["subject"].startswith("[4% Burst] DEGRADED — ")
    assert problem["message"] in visible(sent["html"])
    # the ledger and the dashboard snapshot
    assert published(tmp_path)["run"]["errors"] == report.errors
    assert recorded(tmp_path)["runs"][0]["status"] == "degraded"


def test_a_run_on_the_right_side_of_the_close_is_clean(
    market_clock, universe, mocked_boundaries, open_gate
):
    """The inverse check. If this degraded too, the test above would be
    passing on a pipeline that simply always degrades."""
    market_clock.after_the_close()
    report = pipeline.RunReport()

    pipeline.run("evening", dry_run=True, tickers=universe, report=report)

    assert report.errors == [] and report.exit_code == pipeline.EXIT_OK


def test_a_deliberate_backfill_is_not_reported_as_a_clock_mistake(
    monkeypatch, market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """A pinned session on the wrong side of the close is the documented way
    to seed a history, and it stays clean."""
    market_clock.before_the_open()
    fake_alpaca.add_history("BURST", ohlcv("burst"))
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(-6))
    report = pipeline.RunReport()

    pipeline.run("evening", dry_run=True, tickers=["BURST"], report=report)

    assert [e["stage"] for e in report.errors] == [], report.errors
    assert archived_csv(tmp_path).name == f"{session_offset(-6)}_evening.csv", (
        "and the CSV is named for the session it actually scanned")


def test_the_email_names_the_session_that_was_scanned(
    universe, mocked_boundaries, open_gate
):
    """The cheapest half of the fix, and the only half a phone shows: a run
    that read yesterday's bars says so in the artifact a person opens."""
    pipeline.run("evening", dry_run=False, tickers=universe)

    (sent,) = mocked_boundaries["resend"].sent
    session = scanner.current_session().isoformat()
    assert session in sent["subject"]
    assert f"Session scanned: {session}" in sent["html"]


# --- a repeat is visible as a repeat ---------------------------------------


def seed_history(monkeypatch, fake_alpaca, ohlcv, back: int = 8) -> None:
    """One old run, so the record has LOOKED further back than a streak reaches.

    src.ledger puts a day number on a streak only when the ledger holds a run
    at least MAX_STREAK_GAP_SESSIONS sessions before the appearance it counts
    from: "day 1 — new setup" is the claim that nothing preceded this burst,
    and against a file that has only ever seen tonight that claim is made out
    of nothing. So a test ABOUT day numbers has to give the record something to
    have looked at, or it is quietly testing the unknown branch instead.

    A session with no burst in it, deliberately: it moves the ledger's reach
    back without adding an appearance the streak under test would then have to
    account for.
    """
    fake_alpaca.add_history("QUIET", ohlcv("flat"))
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(-back))
    pipeline.run("evening", dry_run=True, tickers=["QUIET"])
    monkeypatch.delenv("SCAN_SESSION_DATE")


def test_a_name_that_burst_yesterday_is_day_two_tonight(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """THE step-10 statefulness test. Two runs on consecutive sessions, and
    the second one knows it has seen this name before -- in the file the
    dashboard reads and in the email a person reads."""
    seed_history(monkeypatch, fake_alpaca, ohlcv)
    fake_alpaca.add_history("BURST", ohlcv("burst"))
    first, second = session_offset(-1), session_offset(0)

    monkeypatch.setenv("SCAN_SESSION_DATE", first)
    pipeline.run("evening", dry_run=True, tickers=["BURST"])
    (day_one,) = clean(tmp_path)["candidates"]
    assert day_one["streak"]["day"] == 1, "nothing preceded it"

    monkeypatch.setenv("SCAN_SESSION_DATE", second)
    scored = pipeline.run("evening", dry_run=False, tickers=["BURST"])

    (day_two,) = clean(tmp_path)["candidates"]
    assert day_two["streak"] == {
        "day": 2, "unknown_reason": None, "first_seen": first, "last_seen": first,
        "last_score": day_one["score"], "last_verdict": day_one["verdict"],
        "last_outcome": "scored", "seen_before": 1,
        # The span of the RECORD, the same on every row of the run: the seeded
        # session eight back, and the two sessions the ledger held when this
        # streak was computed (seeded + first; tonight is not in it yet).
        "history_from": session_offset(-8), "history_sessions": 2}
    assert scored[0]["streak"] == day_two["streak"], "the email row carries the same block"
    (sent,) = mocked_boundaries["resend"].sent
    assert "day 2 of this setup" in sent["html"]
    assert f"last seen {first}, scored " in sent["html"], (
        "and what was done with it then, which is not the same as a bare score")


def test_a_first_sighting_says_so_rather_than_saying_nothing(
    monkeypatch, fake_alpaca, universe, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The inverse: over a record that HAS looked back, a name with nothing
    behind it is on day 1 and the email says which -- absence is not a readable
    signal."""
    seed_history(monkeypatch, fake_alpaca, ohlcv)

    pipeline.run("evening", dry_run=False, tickers=universe)

    assert all(c["streak"]["day"] == 1 for c in clean(tmp_path)["candidates"])
    assert "day 1 — new setup" in mocked_boundaries["resend"].sent[-1]["html"]


def test_a_burst_the_gate_rejected_carries_its_streak_too(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, tmp_path
):
    """Otherwise the record disagrees with itself the next time the name comes
    back: tonight it was never here, tomorrow it is on day 2 of nothing."""
    seed_history(monkeypatch, fake_alpaca, ohlcv)
    monkeypatch.setattr(pipeline, "MIN_LYNCH_PASSES", 99)   # nothing can pass
    fake_alpaca.add_history("BURST", ohlcv("burst"))
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(-1))
    pipeline.run("evening", dry_run=True, tickers=["BURST"])

    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(0))
    pipeline.run("evening", dry_run=True, tickers=["BURST"])

    (gated,) = clean(tmp_path)["gated_out"]
    assert gated["streak"]["day"] == 2
    assert gated["streak"]["last_outcome"] == "lynch_gate", (
        "and says the gate rejected it, which is what makes counting it honest")


def test_re_running_one_session_does_not_make_every_name_a_repeat(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """A run repeated after a failure re-scans a session already in the
    ledger. Counting the first attempt would report day 2 of a setup that
    started that same evening."""
    seed_history(monkeypatch, fake_alpaca, ohlcv)
    fake_alpaca.add_history("BURST", ohlcv("burst"))
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(0))

    pipeline.run("evening", dry_run=True, tickers=["BURST"])
    pipeline.run("evening", dry_run=True, tickers=["BURST"])

    (again,) = clean(tmp_path)["candidates"]
    assert again["streak"]["day"] == 1
    assert again["streak"]["seen_before"] == 0


def test_a_history_that_cannot_be_read_never_takes_the_run_with_it(
    universe, mocked_boundaries, open_gate, tmp_path
):
    """The run happening now is worth more than the runs already gone: market
    data is live-only and cannot be re-fetched, the history has already been
    written down once. But it is REPORTED, and the streaks go out null --
    "we have never seen this name" and "we could not read the file that would
    know" are different sentences."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / ledger.LEDGER_NAME).write_text("{not json")
    report = pipeline.RunReport()

    scored = pipeline.run("evening", dry_run=False, tickers=universe, report=report)

    assert scored, "the run finished"
    assert [e["stage"] for e in report.errors] == ["history"], report.errors
    (problem,) = report.errors
    assert "could not be read" in problem["message"]
    data = clean(tmp_path)
    assert all(c["streak"]["day"] is None for c in data["candidates"]), (
        "no day number; it must not collapse to a confident day 1")
    assert {c["streak"]["unknown_reason"] for c in data["candidates"]} == {
        "history_unreadable"}, "and it says WHICH unknown, not just that it is one"
    html = mocked_boundaries["resend"].sent[0]["html"]
    assert "new setup" not in html and "of this setup" not in html, (
        "an unknown streak is never dressed up as a first sighting")
    assert "streak unknown — the run could not read its history" in html, (
        "and it is not silent either: a row saying nothing reads as day 1 too")
    assert problem["message"] in html, "and the band says why the column is missing"


def test_a_history_read_that_raises_outright_still_cannot_kill_the_run(
    monkeypatch, universe, mocked_boundaries, open_gate, tmp_path
):
    """Ledger.load() handles the failures it can name -- unreadable JSON, a
    schema it does not know. This is the one it cannot: anything else a read
    can do, from a permission change to a bug in this module. Market data is
    live-only and cannot be re-fetched; the history has already been written
    down once, so the run wins.
    """
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / ledger.LEDGER_NAME).write_text(
        json.dumps({"schema_version": ledger.SCHEMA_VERSION, "runs": [{"date": "2026-01-02"}]}))
    was = (tmp_path / "docs" / ledger.LEDGER_NAME).read_text()

    def boom(self):
        raise RuntimeError("something nobody predicted")

    monkeypatch.setattr(ledger.Ledger, "load", boom)
    report = pipeline.RunReport()

    scored = pipeline.run("evening", dry_run=False, tickers=universe, report=report)

    assert scored, "the run finished anyway"
    assert [e["stage"] for e in report.errors] == ["history"], report.errors
    (problem,) = report.errors
    assert "something nobody predicted" in problem["message"]
    assert all(c["streak"]["unknown_reason"] == "history_unreadable"
               for c in clean(tmp_path)["candidates"])
    # AND the year of outcomes it could not read is still on disk. The run
    # carries on with an empty history and then writes one — so a read that
    # gives up without moving the old file aside destroys it, which is the
    # loss Ledger.set_aside() exists to prevent and which this catch-all
    # would otherwise have quietly reopened a door to.
    (kept,) = ledger.quarantined(tmp_path / "docs")
    assert kept.read_text() == was, (
        "the previous ledger was overwritten by a run that could not read it")
    assert json.loads((tmp_path / "docs" / ledger.LEDGER_NAME).read_text())["runs"]


def test_a_quarantined_ledger_survives_the_commit_back_and_the_next_night_heals(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """Ledger.set_aside() keeps the casualty on the container's disk, which is
    worth nothing on its own: in Actions the container is thrown away. What
    makes it a real rescue is that `git add docs` STAGES it -- .gitignore
    blocks docs/charts/ and nothing else under docs/ -- so the file a run
    could not read is committed for a human to look at.

    And the night after must not repeat the whole thing. The persist step
    commits on exit 2, and an unreadable history is exactly an exit 2, so the
    FRESH ledger reaches the branch and the next run reads it. Before that fix
    a corrupt ledger was permanent: every night quarantined it again, wrote a
    good one, and threw the good one away with the container.

    Simulated against a real `git` in a real repository rather than reasoned
    about, because both halves are claims about what a command does.
    """
    import subprocess

    docs = tmp_path / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    corrupt = "{not json at all"
    (docs / ledger.LEDGER_NAME).write_text(corrupt)

    def git(*args):
        return subprocess.run(("git",) + args, cwd=tmp_path, capture_output=True, text=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    # The one rule under docs/ that this repo's .gitignore carries, copied
    # from it rather than invented: if a later round gitignores the casualty
    # too, that is the change this test exists to fail on.
    (tmp_path / ".gitignore").write_text(_docs_ignore_rules())
    git("add", "-A")
    git("commit", "-qm", "a ledger nothing can read")

    names = _wide_universe(fake_alpaca, ohlcv, fresh=2)
    pipeline.run("evening", dry_run=True, tickers=names)

    git("add", "docs")   # exactly what evening.yml's persist step runs
    staged = git("diff", "--cached", "--name-only").stdout.split()
    (kept,) = ledger.quarantined(docs)
    assert f"docs/{kept.name}" in staged, (
        f"the casualty is not staged, so it dies with the container: {staged}")
    assert kept.read_text() == corrupt
    assert not any(p.startswith("docs/charts/") for p in staged), (
        "the charts are the one thing under docs/ that must NOT be committed")
    git("commit", "-qm", "night one")

    # Night two, over what night one committed.
    before = set(ledger.quarantined(docs))
    pipeline.run("evening", dry_run=True, tickers=names)

    assert set(ledger.quarantined(docs)) == before, (
        "the second night quarantined again, so nothing healed")
    assert json.loads((docs / ledger.LEDGER_NAME).read_text())["runs"]


def _docs_ignore_rules() -> str:
    """This repo's own .gitignore rules that mention docs/, and only those.

    Read rather than retyped: the test above is about which files under docs/
    reach a commit, and a hand-copied rule set would go on asserting the
    answer for rules the repo no longer has.
    """
    root = pathlib.Path(__file__).resolve().parents[1]
    return "".join(line for line in root.joinpath(".gitignore").read_text().splitlines(True)
                   if "docs" in line and not line.lstrip().startswith("#"))


def test_the_history_is_read_once_and_the_two_files_agree_about_it(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The streak in docs/data.json and the one the email carried come from a
    single read, taken before this run was added to the ledger."""
    fake_alpaca.add_history("BURST", ohlcv("burst"))
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(-1))
    pipeline.run("evening", dry_run=True, tickers=["BURST"])

    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(0))
    scored = pipeline.run("evening", dry_run=True, tickers=["BURST"])

    (published_row,) = published(tmp_path)["candidates"]
    assert scored[0]["streak"] == published_row["streak"]


# --- the morning mode: a follow-through pass, not a second scan -------------


def evening_run(tmp_path, fake_alpaca, ohlcv, **kwargs) -> dict:
    """One published evening run for a morning pass to follow through on."""
    fake_alpaca.add_history("BURST", ohlcv("burst"))
    pipeline.run("evening", dry_run=True, tickers=["BURST"], **kwargs)
    return published(tmp_path)


def test_a_morning_run_re_presents_the_evening_run_and_scans_nothing(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The whole design decision, asserted: a morning run before the open has
    no market data an evening run did not have -- the daily bar it would read
    is the same bar -- so it does not scan, does not call Claude, and does not
    spend anything. What it adds is these names at the hour someone might act
    on them, with what the record says about each."""
    evening = evening_run(tmp_path, fake_alpaca, ohlcv)
    market_clock.before_the_open()
    before = (len(mocked_boundaries["alpaca"].bar_requests),
              len(mocked_boundaries["anthropic"].calls))

    rows = pipeline.run("morning", dry_run=False)

    assert [r["ticker"] for r in rows] == [c["ticker"] for c in evening["candidates"]]
    assert (len(mocked_boundaries["alpaca"].bar_requests),
            len(mocked_boundaries["anthropic"].calls)) == before, "nothing was spent"
    (sent,) = mocked_boundaries["resend"].sent
    assert sent["subject"].startswith(
        f"[4% Burst] Morning follow-through {evening['run']['date']}: BURST")
    assert f"{evening['run']['date']}&rsquo;s shortlist, at today&rsquo;s open" in sent["html"], (
        "the heading names the session the rows are from, not just TODAY")
    assert f"Following through on the session of: {evening['run']['date']}" in sent["html"]


def test_the_morning_email_attaches_no_chart_and_says_why(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """THE bug this replaces: docs/charts holds one PNG per ticker, rewritten
    by every evening run, and docs/data.json is only rewritten at publish().
    An evening run that rendered and then died left the directory a session
    ahead of the snapshot -- and the morning row resolved its chart by bare
    path, so every number in the row was Monday's and the attached picture was
    Tuesday's, with nothing in the email showing it. Here the file on disk is
    replaced with a different image after publishing, which is exactly what
    that half-finished run does.

    THE SETUP IS LOAD-BEARING, and it did not use to be. A published row names
    its chart as "charts/BURST.png" -- relative to docs/, because that is what
    the dashboard resolves it against -- and from the repo root that path is
    simply absent, so the assertions below passed on a path shape whatever
    email_row() did with `chart`. Deleting `chart=None` left the whole suite
    green. render_chart()'s default out_dir IS "charts" at the repo root, so
    the file is put where the published path really points and the rule is
    what decides the outcome: with the suppression removed this attaches a
    stale PNG and emits cid:chart_BURST.

    The evening email is unaffected and keeps its charts: it attaches the PNGs
    it rendered moments earlier, in the same process."""
    fake_alpaca.add_history("BURST", ohlcv("burst"))
    pipeline.run("evening", dry_run=False, tickers=["BURST"])
    (evening_mail,) = mocked_boundaries["resend"].sent
    assert [a["filename"] for a in evening_mail["attachments"]] == ["BURST.png"], (
        "the evening email still carries the chart it just rendered")

    chart = tmp_path / "docs" / "charts" / "BURST.png"
    was = chart.read_bytes()
    chart.write_bytes(was + b"a later session's picture")
    # The published row says "charts/BURST.png". Put a PNG exactly there, the
    # way render_chart() does when nobody overrides out_dir, so that resolving
    # the row's path finds a real file and the suppression is the only thing
    # standing between it and the email.
    stale = Path(render_chart("BURST", ohlcv("burst", variant=1)))
    (row,) = published(tmp_path)["candidates"]
    assert stale == Path(row["chart"]) and stale.exists(), (
        "the published path resolves to a file this codebase writes")
    market_clock.before_the_open()

    pipeline.run("morning", dry_run=False)

    morning_mail = mocked_boundaries["resend"].sent[1]
    assert morning_mail["attachments"] == [], "no picture this pass cannot date"
    assert "cid:chart_BURST" not in morning_mail["html"], "and nothing referencing one"
    assert pipeline.MORNING_CHART_NOTE in morning_mail["html"], (
        "the cell where the chart was says what happened")
    assert pipeline.email_row(row)["chart"] is None, (
        "and the rule itself: the row the morning pass renders names no chart")
    assert chart.read_bytes() == was + b"a later session's picture", (
        "and the run did not touch either file")
    assert stale.exists()


def test_a_morning_run_writes_nothing(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """docs/ledger.json is the record of what was SCANNED, and add_run() keys
    its entries on (date, type): a morning entry beside the evening one would
    carry the same candidates and count that burst twice in every mean across
    runs. A view over the record does not belong inside it."""
    evening_run(tmp_path, fake_alpaca, ohlcv)
    market_clock.before_the_open()
    def written():
        return {p: p.read_bytes() for p in sorted(tmp_path.rglob("*")) if p.is_file()}

    before = written()

    pipeline.run("morning", dry_run=True)

    assert written() == before, (
        "docs/ is untouched and no CSV was written for a scan that did not happen")


def test_a_morning_run_needs_no_market_or_model_keys(
    monkeypatch, market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """It runs neither layer, so demanding their keys would refuse a run that
    would have worked perfectly."""
    evening_run(tmp_path, fake_alpaca, ohlcv)
    market_clock.before_the_open()
    for var in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var)

    assert pipeline.run("morning", dry_run=False)
    assert pipeline.missing_env(dry_run=False, run_type="morning") == []
    assert "ALPACA_API_KEY" in pipeline.missing_env(dry_run=False, run_type="evening"), (
        "and an evening run still cannot start without them")


def test_a_morning_run_carries_the_streaks_the_evening_run_recorded(
    monkeypatch, market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """Read out of the published run rather than recomputed: one arithmetic,
    one answer, no second rule that can drift from the first."""
    seed_history(monkeypatch, fake_alpaca, ohlcv)
    fake_alpaca.add_history("BURST", ohlcv("burst"))
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(-1))
    pipeline.run("evening", dry_run=True, tickers=["BURST"])
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(0))
    pipeline.run("evening", dry_run=True, tickers=["BURST"])
    monkeypatch.delenv("SCAN_SESSION_DATE")

    market_clock.before_the_open()
    pipeline.run("morning", dry_run=False)

    assert "day 2 of this setup" in mocked_boundaries["resend"].sent[-1]["html"]


def test_a_morning_run_with_nothing_published_says_so_and_still_mails(
    market_clock, mocked_boundaries, tmp_path
):
    """Its whole input is the snapshot the last run published, so an absent
    one is the interesting failure, not an edge case."""
    market_clock.before_the_open()
    report = pipeline.RunReport()

    rows = pipeline.run("morning", dry_run=False, report=report)

    assert rows == []
    assert report.exit_code == pipeline.EXIT_DEGRADED
    assert [e["stage"] for e in report.errors] == ["history"], report.errors
    (problem,) = report.errors
    assert "nothing to follow through on" in problem["message"]
    (sent,) = mocked_boundaries["resend"].sent
    assert sent["subject"].startswith("[4% Burst] DEGRADED — ")
    assert "not a statement about the market" in sent["html"]


def test_a_morning_run_refuses_to_mail_the_hand_authored_fixture(
    market_clock, mocked_boundaries, tmp_path
):
    """docs/data.json ships as a fixture of invented rows -- a copy of
    tests/fixtures/data.json, which is what this reads, because docs/ stops
    being the fixture the night evening.yml first commits a real run back.
    Mailing those rows as a watchlist would put made-up names in front of a
    reader as last night's judgements, and would look exactly like a working
    run."""
    market_clock.before_the_open()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / ledger.DATA_NAME).write_text(
        (Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "data.json").read_text())
    report = pipeline.RunReport()

    rows = pipeline.run("morning", dry_run=False, report=report)

    assert rows == []
    assert [e["stage"] for e in report.errors] == ["history"], report.errors
    assert "fixture" in report.errors[0]["message"]
    assert "GOOGL" not in mocked_boundaries["resend"].sent[0]["html"]


def test_a_morning_run_following_a_stale_evening_run_says_which_session(
    monkeypatch, market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """A week-old snapshot means the evening run has been failing and nobody
    noticed -- exactly what this pipeline exists to stop being invisible."""
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(-4))
    evening_run(tmp_path, fake_alpaca, ohlcv)
    monkeypatch.delenv("SCAN_SESSION_DATE")
    market_clock.before_the_open()
    report = pipeline.RunReport()

    pipeline.run("morning", dry_run=False, report=report)

    assert [e["stage"] for e in report.errors] == ["session"], report.errors
    (problem,) = report.errors
    assert session_offset(-4) in problem["message"]
    assert str(scanner.current_session()) in problem["message"]
    assert report.exit_code == pipeline.EXIT_DEGRADED
    assert problem["message"] in visible(mocked_boundaries["resend"].sent[0]["html"])


def test_a_morning_run_three_weeks_stale_says_so_in_the_subject_line(
    monkeypatch, market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The whole path, end to end: the gap the band computes is the gap the
    subject escalates on, and a phone shows only the second. One session late
    and fifteen sessions dead used to produce the same subject."""
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(-15))
    evening_run(tmp_path, fake_alpaca, ohlcv)
    monkeypatch.delenv("SCAN_SESSION_DATE")
    market_clock.before_the_open()

    pipeline.run("morning", dry_run=False)

    (sent,) = mocked_boundaries["resend"].sent
    assert sent["subject"].startswith("[4% Burst] NOTHING PUBLISHED IN 15 SESSIONS — ")
    assert "NOTHING HAS PUBLISHED FOR 15 SESSIONS" in sent["html"]
    assert "that is 15 sessions ago" in sent["html"]


def test_a_morning_run_one_session_stale_stays_ambiguous_everywhere(
    monkeypatch, market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The precondition for the test above, and the boundary itself: at a gap
    of one a holiday really is a live explanation, so nothing escalates."""
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(-1))
    evening_run(tmp_path, fake_alpaca, ohlcv)
    monkeypatch.delenv("SCAN_SESSION_DATE")
    market_clock.before_the_open()

    pipeline.run("morning", dry_run=False)

    (sent,) = mocked_boundaries["resend"].sent
    assert sent["subject"].startswith("[4% Burst] DEGRADED — ")
    assert "NOTHING PUBLISHED IN" not in sent["subject"]
    assert "that is 1 session ago" in sent["html"]
    assert "the market held no session for it to scan" in sent["html"]


def test_the_stale_snapshot_band_never_asserts_that_a_session_existed():
    """The morning after every market holiday, this band used to read "the
    session to follow through on is 2026-11-26" over a day the market never
    held: expected_session() subtracts weekends and nothing else. Nine or ten
    mornings a year of a confident false sentence, in the one place a reader
    looks before risking money -- and each one teaching that the red band is
    routine, which is what makes "the evening run has been failing" invisible
    when it is the true reason.

    A holiday calendar is deliberately NOT the fix (an approximate one used to
    make a confident claim is a worse defect), so what this asserts is that the
    sentence stops making the claim: it says what published, that nothing has
    since, and BOTH reasons that could explain it.

    THE HEDGE IS ONLY LIVE AT A GAP OF ONE, which is what this case is (a
    Wednesday snapshot on a Thursday morning). Stated at any gap it becomes
    false in exactly the case it was written to protect -- see the two tests
    above it."""
    said = pipeline.stale_snapshot_note(
        {"type": "evening", "status": "ok"}, "2026-11-25", "2026-11-26")

    assert "that is 1 session ago" in said
    assert "the newest published run is the evening run of 2026-11-25" in said
    assert "nothing has published a later session" in said
    # Neither explanation may be presented as the one that happened.
    assert "did not publish" in said and "no session for it to scan" in said
    # And the date the clock would have named appears only as something to
    # check, never as a session that was held.
    assert "the session to follow through on is" not in said
    assert "If the market did trade on 2026-11-26" in said


def test_a_gap_of_two_kills_the_holiday_explanation_on_arithmetic_alone():
    """The band the test above describes was rendered at 1, 3 and 15 sessions
    and came out byte-identical but for a date -- so at fifteen it hedged with
    an explanation that is itself false, because no US market holiday closes
    the tape for fifteen consecutive sessions. None of the market's SCHEDULED
    holidays are adjacent either, which is the whole rule and needs no
    calendar: from a gap of two, at least one of those days was a scheduled
    session. Unscheduled closures have run to consecutive sessions -- 9/11,
    Sandy, the 2007 day of mourning the day after New Year's Day -- so one
    clause is kept for them, named as the exception rather than offered as the
    routine explanation."""
    said = pipeline.stale_snapshot_note(
        {"type": "evening", "status": "ok"}, "2026-08-27", "2026-08-31")

    assert "that is 2 sessions ago" in said
    assert "at least one of those 2 days was a scheduled session" in said
    assert "The evening run has stopped publishing" in said
    # The exception is kept, and named as one: unscheduled closures HAVE run to
    # consecutive sessions. What must not survive is the routine hedge.
    assert "UNSCHEDULED closure" in said and "9/11" in said
    # The hedge the one-session band carries must NOT appear here.
    assert "no session for it to scan" not in said
    assert "cannot tell them apart" not in said


def test_a_three_week_gap_says_three_weeks_and_not_one_session():
    """The case the whole fix exists for: a screener dead for three weeks must
    not wear the same clothes as the Tuesday after Presidents' Day."""
    said = pipeline.stale_snapshot_note(
        {"type": "evening", "status": "ok"}, "2026-08-10", "2026-08-31")

    assert "that is 15 sessions ago, counting through 2026-08-31" in said
    assert "at least one of those 15 days was a scheduled session" in said


def test_a_snapshot_ahead_of_the_expected_session_is_not_called_stale():
    """SCAN_SESSION_DATE can pin a run forward. "N sessions ago" would be a
    negative number dressed as a delay, and the repair is a different one."""
    said = pipeline.stale_snapshot_note(
        {"type": "evening", "status": "ok"}, "2026-09-07", "2026-08-31")

    assert "LATER than the session this run expected" in said
    assert "sessions ago" not in said
    assert "pinned forward with SCAN_SESSION_DATE" in said


def test_a_snapshot_dated_on_a_non_session_is_neither_stale_nor_ahead():
    """A Saturday and the Monday after are different dates with no trading
    session between them. "0 sessions ago" is not a sentence, "1 session ago"
    is wrong, and "LATER than expected" is wrong in the other direction --
    a SCAN_SESSION_DATE pinned to a weekend produces exactly this."""
    said = pipeline.stale_snapshot_note(
        {"type": "evening"}, "2026-08-29", "2026-08-31")

    assert pipeline.stale_sessions("2026-08-29", "2026-08-31") == 0
    assert "no trading session separates the two dates" in said
    assert "sessions ago" not in said and "LATER" not in said


def test_a_snapshot_with_no_usable_date_says_the_gap_is_unknown():
    """It comes off disk. A hand-edited or truncated snapshot must not make
    this sentence claim a number it could not compute."""
    said = pipeline.stale_snapshot_note({"type": "evening"}, None, "2026-08-31")

    assert "cannot be compared with it" in said
    assert "sessions ago" not in said and "at least one of those" not in said


def test_the_gap_the_band_states_is_the_one_the_subject_escalates_on():
    """One arithmetic, two surfaces. A band saying 15 sessions over a subject
    saying DEGRADED would be the same split this fix exists to close."""
    assert pipeline.stale_sessions("2026-08-10", "2026-08-31") == 15
    assert pipeline.stale_sessions("2026-08-28", "2026-08-31") == 1
    assert pipeline.stale_sessions("2026-09-07", "2026-08-31") == -5
    assert pipeline.stale_sessions(None, "2026-08-31") is None


def test_the_stale_snapshot_band_still_names_the_older_run_it_is_showing():
    """The precondition for the test above: dropping the claim must not drop
    the facts. Which run is on the table, and that it is not today's."""
    said = pipeline.stale_snapshot_note(
        {"type": "evening", "status": "degraded"}, "2026-08-24", "2026-08-31")

    assert "the rows below are 2026-08-24's" in said
    assert "not a scan of any session since" in said


def test_a_morning_run_carries_last_nights_reasons_and_not_just_the_word(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The morning band said "was itself a DEGRADED run" and dropped every
    sentence behind it -- so "NOT ONE of 12 candidates was scored by Claude;
    the order is not a ranking", which is what a reader needs before acting on
    a ranking, arrived as one word. src.emailer._banner() makes exactly this
    argument for the evening email: the problems are printed in full because
    "138 of 230 symbols had no bar" tells an operator where to look and
    "degraded" does not."""
    data = evening_run(tmp_path, fake_alpaca, ohlcv)
    data["run"]["status"] = "degraded"
    data["run"]["errors"] = [
        {"stage": "scan", "message": "138 of 230 symbols carried no bar for that session"},
        {"stage": "score", "message": "NOT ONE of 12 candidates was scored by Claude"},
    ]
    (tmp_path / "docs" / ledger.DATA_NAME).write_text(json.dumps(data))
    market_clock.before_the_open()
    report = pipeline.RunReport()

    pipeline.run("morning", dry_run=False, report=report)

    session = data["run"]["date"]
    assert [e["stage"] for e in report.errors] == [
        "history", f"{session} evening · scan", f"{session} evening · score"], report.errors
    html = mocked_boundaries["resend"].sent[0]["html"]
    for problem in data["run"]["errors"]:
        assert problem["message"] in html, "the reason itself, not a summary of it"
    assert f"{session} evening" in html, "and whose problem it is, in a band holding two runs'"


def test_a_morning_run_carries_no_reasons_when_there_were_none(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The precondition: a status word with no sentences behind it does not
    invent any, and a clean run carries nothing at all."""
    data = evening_run(tmp_path, fake_alpaca, ohlcv)
    data["run"]["status"] = "degraded"
    (tmp_path / "docs" / ledger.DATA_NAME).write_text(json.dumps(data))
    market_clock.before_the_open()
    report = pipeline.RunReport()

    pipeline.run("morning", dry_run=True, report=report)

    assert [e["stage"] for e in report.errors] == ["history"]
    assert "Its own reasons follow" not in report.errors[0]["message"]


def test_a_snapshot_whose_errors_are_not_error_shaped_still_mails(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """run.errors comes off disk. A truncated or hand-edited file must not take
    the 8:30 email down -- the email is the monitor, and losing it is the
    failure the whole of step 5 exists to end."""
    data = evening_run(tmp_path, fake_alpaca, ohlcv)
    data["run"]["status"] = "degraded"
    data["run"]["errors"] = ["a bare string", None, {"stage": "scan"}, {"message": "   "},
                             {"message": "the one real sentence"}]
    (tmp_path / "docs" / ledger.DATA_NAME).write_text(json.dumps(data))
    market_clock.before_the_open()
    report = pipeline.RunReport()

    pipeline.run("morning", dry_run=False, report=report)

    session = data["run"]["date"]
    assert [e["stage"] for e in report.errors] == [
        "history", f"{session} evening · unknown"], report.errors
    assert "the one real sentence" in mocked_boundaries["resend"].sent[0]["html"]


def test_a_morning_run_on_the_session_it_should_follow_is_clean(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The precondition for the test above: a fresh snapshot is not reported."""
    evening_run(tmp_path, fake_alpaca, ohlcv)
    market_clock.before_the_open()
    report = pipeline.RunReport()

    pipeline.run("morning", dry_run=True, report=report)

    assert report.errors == [] and report.exit_code == pipeline.EXIT_OK


@pytest.mark.parametrize("status", ["failed", "degraded"])
def test_a_morning_run_says_when_the_run_it_follows_was_not_clean(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path, status
):
    """A shortlist from an incomplete scan is not a shortlist of the market,
    and the reader of the 8:30 email is not the reader who saw last night's
    red band. Both non-clean statuses carry forward, not just the loudest."""
    data = evening_run(tmp_path, fake_alpaca, ohlcv)
    data["run"]["status"] = status
    (tmp_path / "docs" / ledger.DATA_NAME).write_text(json.dumps(data))
    market_clock.before_the_open()
    report = pipeline.RunReport()

    pipeline.run("morning", dry_run=True, report=report)

    assert [e["stage"] for e in report.errors] == ["history"], report.errors
    assert status.upper() in report.errors[0]["message"]


def test_a_morning_run_after_a_clean_evening_run_carries_no_such_warning(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The precondition for the two above: `ok` is not simply reported too."""
    assert evening_run(tmp_path, fake_alpaca, ohlcv)["run"]["status"] == "ok"
    market_clock.before_the_open()
    report = pipeline.RunReport()

    pipeline.run("morning", dry_run=True, report=report)

    assert report.errors == []


def test_tickers_is_refused_for_a_mode_that_does_not_scan(monkeypatch, capsys):
    """A flag that silently does nothing is how a smoke test convinces someone
    they tested something they did not."""
    monkeypatch.setattr(sys, "argv", ["pipeline", "morning", "--tickers", "AAA"])
    with pytest.raises(SystemExit) as exc:
        pipeline.main()
    assert exc.value.code == 2  # argparse's usage error, not EXIT_DEGRADED
    assert "does not scan" in capsys.readouterr().err


def test_a_history_with_unreadable_dates_reports_itself_instead_of_passing_as_clean(
    universe, mocked_boundaries, open_gate, tmp_path
):
    """A run entry whose `date` will not parse is kept rather than
    quarantined -- src.ledger draws the line at shape, not content, and one
    bad field is not grounds for setting a year of outcomes aside.

    But the run that read it used to report itself CLEAN: exit 0, no band,
    nothing in the email, while publishing a snapshot that broke its own
    declared contract. A damaged record is a thing the operator has to be told
    about, in the same place every other problem is told.
    """
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / ledger.LEDGER_NAME).write_text(json.dumps({
        "schema_version": ledger.SCHEMA_VERSION,
        "runs": [{"date": "not-a-date", "type": "evening",
                  "candidates": [{"ticker": "AAPL", "date": "2026-01-02", "score": 7}],
                  "gated": []}],
    }))
    report = pipeline.RunReport()

    pipeline.run("evening", dry_run=False, tickers=universe, report=report)

    assert [e["stage"] for e in report.errors] == ["history"], report.errors
    assert "1 of 1 runs" in report.errors[0]["message"]
    assert report.exit_code == pipeline.EXIT_DEGRADED

    # And the snapshot it published does not contradict itself: the record's
    # span was recovered from the rows, which carry the session they burst on.
    for candidate in clean(tmp_path)["candidates"]:
        streak = candidate["streak"]
        assert streak["seen_before"] <= (streak["history_sessions"] or 0), streak



def test_the_exit_codes_are_the_numbers_actions_reads():
    """Every other test in this file asserts `== pipeline.EXIT_DEGRADED` and
    friends, which compares the code against the name it came from: change the
    constant to 0 and all fifteen of them stay green, verified by mutation.
    They are not wrong to read that way -- the name is what makes them
    legible -- they just need one place that pins the name to a number.

    This is that place. The contract is with GitHub Actions, which reads the
    integer and knows nothing about the name: 0 is a run to trust, 1 is a run
    that produced nothing, 2 is the one that matters -- a run that finished
    and must not be traded off as a complete scan -- and 3 is a run that
    failed with its record already written, which the workflow keeps and
    still reports red. A 2 that silently became a 0 would turn every degraded
    night green, which is the failure step 5 exists to end; a 3 that became a
    1 would throw away a night that was paid for, which is the failure the
    persist condition exists to end.
    """
    assert (pipeline.EXIT_OK, pipeline.EXIT_FAILED, pipeline.EXIT_DEGRADED,
            pipeline.EXIT_FAILED_AFTER_PUBLISH) == (0, 1, 2, 3)


def test_the_three_numbers_that_decide_what_a_run_costs_and_shows():
    """The same shape of pin as the exit codes above, for the same reason.

    Truncation IS tested -- that the email carries TOP_N rows, that the gate
    keeps candidates with at least MIN_LYNCH_PASSES, that no more than
    MAX_TO_SCORE go to Claude -- but every one of those tests reads the
    constant it is checking, so all three could be changed with the suite
    green. Verified by mutation: 3 -> 4, 5 -> 6 and 25 -> 26 each left 676
    tests passing.

    They are not wrong to read that way; the names are what make them legible.
    They need one place that says what the numbers are, because each is a real
    commitment. MAX_TO_SCORE is the night's Claude bill and the cap the
    "crowded out by the call budget" language exists for. TOP_N is how many
    names a reader is asked to act on, and nothing else -- it has never cut the
    archive since step 9. MIN_LYNCH_PASSES is half of six, the point where a
    checklist stops being a majority verdict.
    """
    assert (pipeline.MIN_LYNCH_PASSES, pipeline.TOP_N, pipeline.MAX_TO_SCORE) == (3, 5, 25)


# --- a snapshot that did not come out of a run ---------------------------
# Thirty-seven ways docs/data.json can be malformed, each run through the real
# follow-through and the real email renderer. Twenty of them used to escape as
# an exception: FAILED, exit 1 and a failure notice, where the design says
# DEGRADED, exit 2 and "there is nothing to follow through on". Not a data-loss
# path -- a morning run writes nothing, and docs/ is hashed before and after
# to prove it on every shape -- but the wrong exit code and the wrong email on
# the pass whose only job is to say what state the record is in.
#
# Two kinds of shape, and the table says which each is. REFUSED: the reader
# names the row and the field and the run degrades with nothing to show --
# the table carries the words the refusal must use, since `candidates` that
# is not a list at all is turned away one check earlier, in older words.
# TOLERATED: a field the follow-through never indexes, or content rather than
# shape (a date nobody can parse, a score that is a string), which the run
# carries and prints; the assertion there is only that nothing raised and
# nothing was written.
NOT_A_RUN = "did not come out of a run"

def _drop(key):
    return lambda d: d["candidates"].__setitem__(0, {k: v for k, v in d["candidates"][0].items() if k != key})


def _row(**over):
    return lambda d: d["candidates"][0].update(over)


def _streak(**over):
    return lambda d: d["candidates"][0]["streak"].update(over)


def _run_field(**over):
    return lambda d: d["run"].update(over)


MALFORMED_SNAPSHOTS = {
    # name: (mutation, the refusal's words -- or False when the shape is tolerated)
    "candidates are strings": (lambda d: d.update(candidates=["AAPL"]), NOT_A_RUN),
    # The names that stopped printing: absent is an older snapshot; anything
    # present that is not the object publish() writes is refused one level in.
    "stopped_printing is absent": (lambda d: d["run"].pop("stopped_printing", None), False),
    "stopped_printing is a list": (lambda d: d["run"].update(stopped_printing=["EA"]), NOT_A_RUN),
    "stopped_printing has no count": (lambda d: d["run"].update(stopped_printing={"names": []}), NOT_A_RUN),
    "a stopped name is a string": (lambda d: d["run"].update(
        stopped_printing={"after_sessions": 5, "count": 1, "names": ["EA"]}), NOT_A_RUN),
    "a stopped name's sessions_behind is a string": (lambda d: d["run"].update(
        stopped_printing={"after_sessions": 5, "count": 1,
                          "names": [{"ticker": "EA", "last": "2026-08-04", "sessions_behind": "23"}]}), NOT_A_RUN),
    # A name the feed returned no bar for at all: the one null pair the writer
    # produces, tolerated; a number where the date belongs is not.
    "a stopped name the feed returned nothing for": (lambda d: d["run"].update(
        stopped_printing={"after_sessions": 5, "count": 1,
                          "names": [{"ticker": "NOSUCH", "last": None, "sessions_behind": None}]}), False),
    "a stopped name's last is a number": (lambda d: d["run"].update(
        stopped_printing={"after_sessions": 5, "count": 1,
                          "names": [{"ticker": "EA", "last": 20260804, "sessions_behind": 23}]}), NOT_A_RUN),
    "a candidate is null": (lambda d: d.update(candidates=[None]), NOT_A_RUN),
    "a candidate is a number": (lambda d: d.update(candidates=[7]), NOT_A_RUN),
    "a candidate is a list": (lambda d: d.update(candidates=[["AAPL"]]), NOT_A_RUN),
    "a candidate is an empty object": (lambda d: d.update(candidates=[{}]), NOT_A_RUN),
    "a row has no ticker": (_drop("ticker"), NOT_A_RUN),
    "a row has no score": (_drop("score"), NOT_A_RUN),
    "a row has no verdict": (_drop("verdict"), NOT_A_RUN),
    "a row has no close": (_drop("close"), NOT_A_RUN),
    # lynch_detail is optional now: the email rebuilds its lines with a
    # default, so a row without one is presented rather than refused.
    "a row has no lynch_detail": (_drop("lynch_detail"), False),
    "lynch_detail is a string": (_row(lynch_detail="4/6"), NOT_A_RUN),
    "lynch_detail rows are strings": (_row(lynch_detail=["PASS 2"]), NOT_A_RUN),
    "streak is a string": (_row(streak="day 3"), NOT_A_RUN),
    "streak is a list": (_row(streak=[1]), NOT_A_RUN),
    "streak day is a string": (_streak(day="3"), False),
    "forward_returns is a string": (_row(forward_returns="x"), NOT_A_RUN),
    "provenance is a string": (_row(provenance="claude"), NOT_A_RUN),
    "score is a string": (_row(score="9"), False),
    "ticker is null": (_row(ticker=None), NOT_A_RUN),
    "ticker is a number": (_row(ticker=42), NOT_A_RUN),
    "run.date is an object": (_run_field(date={"a": 1}), False),
    "run.date is a number": (_run_field(date=20260901), False),
    "run.date is null": (_run_field(date=None), False),
    "run.type is an object": (_run_field(type={"a": 1}), False),
    "run.errors is a string": (_run_field(errors="boom"), "run.errors"),
    "run.errors is an object": (_run_field(errors={"stage": "x", "message": "y"}), "run.errors"),
    "run.errors holds a string": (_run_field(errors=["boom"]), False),
    "run.status is an object": (_run_field(status={"a": 1}), NOT_A_RUN),
    "run.status is a number": (_run_field(status=5), NOT_A_RUN),
    "run.scored_by is a string": (_run_field(scored_by="x"), NOT_A_RUN),
    "run.scored_by is a list": (_run_field(scored_by=[1, 2]), NOT_A_RUN),
    "run.bursts is a string": (_run_field(bursts="many"), False),
    "run.passed_gate is a list": (_run_field(passed_gate=[1]), False),
    "gated_out is a string": (lambda d: d.update(gated_out="x"), False),
    "gated_out rows are strings": (lambda d: d.update(gated_out=["x"]), False),
    "runs is a string": (lambda d: d.update(runs="x"), False),
    "candidates is an object": (lambda d: d.update(candidates={"a": 1}), "carries no run to follow through on"),
    # --- one level further in again, found by the 3.1 audit ---------------
    # Each of these was ACCEPTED by read_snapshot and then crashed the real
    # morning path or the real email renderer. A dry run does not render the
    # email, which is how the first sweep called some of them safe. The last
    # two need `day` null as well: the seen_before comparison sits behind a
    # short-circuit that only opens when there is no day number, so a sweep
    # varying one field at a time reports it safe.
    "run.status is null": (_run_field(status=None), "run.status"),
    # run.liquidity, under the same rule as the rows: absent is a snapshot
    # from before the block, present in a shape no writer produces is refused.
    "run.liquidity is a list": (_run_field(liquidity=[30, 1e8, 1]), "run.liquidity"),
    "run.liquidity is a string": (_run_field(liquidity="30th"), "run.liquidity"),
    "run.liquidity is null": (_run_field(liquidity=None), "run.liquidity"),
    "run.liquidity.floor is a string": (_run_field(liquidity={"pctile": 30.0, "floor": "1e8", "refused": 0}), "run.liquidity.floor"),
    "run.liquidity.pctile is a string": (_run_field(liquidity={"pctile": "30", "floor": 1e8, "refused": 0}), "run.liquidity.pctile"),
    "run.liquidity.refused is a string": (_run_field(liquidity={"pctile": 30.0, "floor": 1e8, "refused": "1"}), "run.liquidity.refused"),
    "run.liquidity.floor is null": (_run_field(liquidity={"pctile": 30.0, "floor": None, "refused": 0}), False),
    "run.errors is a number": (_run_field(errors=3), "run.errors"),
    "run.errors is a bool": (_run_field(errors=True), "run.errors"),
    "run.scored_by counts are strings": (
        _run_field(scored_by={"claude": "5", "fallback": "1"}), "scored_by"),
    "run.scored_by counts are lists": (
        _run_field(scored_by={"claude": [1], "fallback": []}), "scored_by"),
    # The context clause was the one shape check with no case naming it, so it
    # could have been deleted with the suite green -- a guard reporting safety
    # nothing measured.
    "context is a string": (_row(context="x"), "context"),
    "context is a list": (_row(context=[1]), "context"),
    "streak.unknown_reason is unhashable": (_streak(day=None, unknown_reason=["x"]), "unknown_reason"),
    # last_outcome sits ONE FIELD from unknown_reason and is looked up the same
    # way -- LAST_OUTCOME.get(outcome) -- so an unhashable one is a TypeError
    # and not a miss. The guard was written for unknown_reason, with a comment
    # naming that exact mechanism, and its neighbour was not swept. Found by
    # an audit of the commit that edited LAST_OUTCOME.
    "streak.last_outcome is a list": (_streak(last_outcome=["scored"]), "last_outcome"),
    "streak.last_outcome is a dict": (_streak(last_outcome={"was": "scored"}), "last_outcome"),
    "streak.last_outcome is a number": (_streak(last_outcome=3), "last_outcome"),
    # The sweep that finding prompted. This one does not crash: it reaches
    # _plural() and renders "[1, 2] sessions in the record", a fabricated
    # sentence with nothing about it saying it is wrong.
    "streak.history_sessions is a list": (
        _streak(day=None, unknown_reason="window_not_covered", history_sessions=[1, 2]),
        "history_sessions"),
    "streak.history_sessions is a string": (
        _streak(day=None, unknown_reason="window_not_covered", history_sessions="8"),
        "history_sessions"),
    "streak.seen_before is a string": (
        _streak(day=None, unknown_reason="no_history", seen_before="3"), "seen_before"),
    "streak.seen_before is a list": (
        _streak(day=None, unknown_reason="no_history", seen_before=[1]), "seen_before"),
}


def _docs_digest(tmp_path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    for file in sorted((tmp_path / "docs").rglob("*")):
        if file.is_file():
            digest.update(file.name.encode())
            digest.update(file.read_bytes())
    return digest.hexdigest()


@pytest.mark.parametrize("shape", sorted(MALFORMED_SNAPSHOTS))
def test_a_malformed_snapshot_degrades_the_morning_run_instead_of_failing_it(
    shape, market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    mutate, refused = MALFORMED_SNAPSHOTS[shape]
    evening_run(tmp_path, fake_alpaca, ohlcv)
    path = tmp_path / "docs" / ledger.DATA_NAME
    data = json.loads(path.read_text())
    mutate(data)
    path.write_text(json.dumps(data))
    before = _docs_digest(tmp_path)
    market_clock.before_the_open()
    report = pipeline.RunReport()

    pipeline.run("morning", dry_run=False, report=report)       # must not raise

    assert _docs_digest(tmp_path) == before, "a morning run writes nothing, whatever it read"
    (sent,) = mocked_boundaries["resend"].sent
    assert not report.failed
    if refused:
        assert report.exit_code == pipeline.EXIT_DEGRADED
        (problem,) = [e for e in report.errors if e["stage"] == "history"]
        assert "nothing to follow through on" in problem["message"]
        assert refused in problem["message"]
        assert sent["subject"].startswith("[4% Burst] DEGRADED — ")
        assert "No shortlist" in sent["html"]
    else:
        # A tolerated shape is READ, not refused. This branch used to assert
        # exit 0 or 2 alone, and a refusal exits 2 -- so every tolerated row
        # in the table could be refused with the suite green, which a mutant
        # that refused the null pair a dateless name carries showed. The
        # inverse of the refused branch is what tells the two states apart.
        assert report.exit_code in (pipeline.EXIT_OK, pipeline.EXIT_DEGRADED)
        assert not [e for e in report.errors if e["stage"] == "history"], (
            "a tolerated shape was refused: " + str(report.errors))


def test_the_fill_reads_each_horizon_by_its_session_across_every_frame_the_run_fetched(
    monkeypatch, market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """forward_returns() counted bars along one frame, so a bar the feed
    dropped between the burst and its horizons slid every later horizon one
    session late and dated it wrong -- the class _drop_gapped_symbols()
    closed for the scan, one stage on, on every row the record holds. The
    fill reads the calendar off every frame the night fetched now: a name
    with a hole on its first session after the burst has NO d1, rather than
    the two-session move the next bar it holds would have printed."""
    from tests.test_scanner import _thin

    # BURST on ten times the usual volume, so that on the SECOND night --
    # when the double has re-dated its frame and the bar on the burst
    # session is an ordinary pre-burst one -- it still clears the floor the
    # first night set, and the benchmark half of this test is about the
    # hole and not about rule 6.
    fake_alpaca.add_history("BURST", ohlcv("burst", base_volume=30_000_000.0))
    names = ["BURST"]
    for i, suffix in enumerate("ABCD"):
        fake_alpaca.add_history(f"Q{suffix}", _thin(ohlcv, "flat", price=40.0 + i,
                                                    volume=3_000_000, variant=i + 2))
        names.append(f"Q{suffix}")
    _universe_file(monkeypatch, tmp_path, names)
    # Tonight, so nothing after the burst exists yet: a run pinned to an
    # OLDER session resolves its own outcomes at once, from bars the hole
    # below has not yet been registered in.
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(0))
    pipeline.run("evening", dry_run=True)
    burst_session = recorded(tmp_path)["runs"][0]["date"]
    row = next(c for c in recorded(tmp_path)["runs"][0]["candidates"] if c["ticker"] == "BURST")
    assert row["forward_returns"]["d1"] is None, "precondition: the session after has not happened"

    # Two sessions on, the feed serves BURST with the bar before the newest
    # one missing -- the session right after the burst. The other four
    # names carry it, so the calendar does.
    fake_alpaca.add_history("BURST", ohlcv("burst", base_volume=30_000_000.0), gap_before_session=True)
    used: dict = {}
    real_fill = ledger.Ledger.fill_benchmarks

    def capture(self, frames, through=None, universe=None, calendar=None):
        used.update(frames)
        return real_fill(self, frames, through, universe, calendar)

    monkeypatch.setattr(ledger.Ledger, "fill_benchmarks", capture)
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(2))
    pipeline.run("evening", dry_run=True)

    book = recorded(tmp_path)
    older = next(r for r in book["runs"] if r["date"] == burst_session)
    row = next(c for c in older["candidates"] if c["ticker"] == "BURST")
    assert row["forward_returns"]["d1"] is None, (
        "the first session's bar is missing from this frame; the next bar is not it")
    assert row["forward_returns"]["as_of"] is None
    assert row["forward_returns"]["from_open"]["d1"] is None
    # And the positional reading it replaced would have printed a number:
    # the burst-day close against the bar two sessions on, called +1d. The
    # benchmark reads the same calendar, over whoever cleared the floor:
    # recomputed by hand from the frames the fill was handed, because the
    # double re-dates every frame per request and which names sit under
    # the floor on tonight's bars is the market's business, not the test's.
    first_after = date.fromisoformat(session_offset(1))
    days_of = {name: {stamp.date() for stamp in frame.index} for name, frame in used.items()}
    assert first_after not in days_of["BURST"], "precondition: the hole is the first session after the burst"
    assert all(first_after in days for name, days in days_of.items() if name != "BURST")
    floor = older["liquidity"]["floor"]
    kept = [name for name, frame in used.items()
            if round(float(frame.loc[burst_session, "Close"]) * float(frame.loc[burst_session, "Volume"])) >= floor]
    assert "BURST" in kept, "precondition: the holed name is above the floor, so only the hole can drop it"
    bench = older["benchmark"]
    assert bench["d1"] is not None, "the whole names still benchmark the session"
    assert bench["below_floor"] == len(names) - len(kept)
    assert bench["n1"] == len(kept) - 1, "every kept name but the holed one, which has no bar on that session"


def test_the_documented_smoke_test_cannot_write_a_slid_horizon_into_a_universe_row(
    monkeypatch, market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """R9-A, the round-9 audit's high finding: README's `--tickers BURST`
    smoke test handed the fill a calendar of ONE frame, which is the
    positional reading round 9 exists to end, so a hole on the session after
    the burst put the two-session move into d1 of the earlier universe run's
    row -- for good, since a horizon is filled once. One frame is no
    calendar; alone, the frame's walk stops at the hole; and the next scan
    of the universe, with a calendar, measures what that left open."""
    from tests.test_scanner import _thin

    fake_alpaca.add_history("BURST", ohlcv("burst", base_volume=30_000_000.0))
    names = ["BURST"]
    for i, suffix in enumerate("ABCD"):
        fake_alpaca.add_history(f"Q{suffix}", _thin(ohlcv, "flat", price=40.0 + i,
                                                    volume=3_000_000, variant=i + 2))
        names.append(f"Q{suffix}")
    _universe_file(monkeypatch, tmp_path, names)
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(0))
    pipeline.run("evening", dry_run=True)
    burst_session = recorded(tmp_path)["runs"][0]["date"]

    fake_alpaca.add_history("BURST", ohlcv("burst", base_volume=30_000_000.0), gap_before_session=True)
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(2))
    pipeline.run("evening", dry_run=True, tickers=["BURST"])

    older = next(r for r in recorded(tmp_path)["runs"] if r["date"] == burst_session)
    row = next(c for c in older["candidates"] if c["ticker"] == "BURST")
    assert row["forward_returns"]["d1"] is None, "the two-session move is not d1, and one frame cannot say what is"
    assert row["forward_returns"]["as_of"] is None

    # The next universe scan has a calendar. The double's hole sits on the
    # bar before the newest one, so on this scan it has moved to the second
    # session after the burst: the first is there, and d1 is measured on
    # that bar -- by date -- while d3, which would have to be read across
    # the hole, is refused.
    monkeypatch.setenv("SCAN_SESSION_DATE", session_offset(3))
    pipeline.run("evening", dry_run=True)
    older = next(r for r in recorded(tmp_path)["runs"] if r["date"] == burst_session)
    row = next(c for c in older["candidates"] if c["ticker"] == "BURST")
    assert row["forward_returns"]["d1"] is not None
    assert row["forward_returns"]["as_of"] == session_offset(1), "the bar the calendar names, not the next one"
    assert row["forward_returns"]["d3"] is None, "across the hole is refused"


# --- the public record carries no email address ------------------------------


@pytest.mark.parametrize("text, expected", [
    ("You can only send testing emails to your own email address (owner@example.invalid). Verify",
     "You can only send testing emails to your own email address (…@example.invalid). Verify"),
    ("first.last+tag@mail.example.co.uk and Second_One@Example.ORG refused",
     "…@mail.example.co.uk and …@Example.ORG refused"),
    ("no address here, only 4% and an @ sign alone", "no address here, only 4% and an @ sign alone"),
])
def test_a_recorded_problem_masks_addresses_to_their_domain(text, expected):
    """run.errors is the one leaf of free text from outside the codebase, and
    the record is public. The domain stays, because "…@gmail.com" still says
    which account a refusal is about."""
    report = pipeline.RunReport()
    report.problem("email", text)
    assert report.errors == [{"stage": "email", "message": expected}]


def test_the_resend_refusal_reaches_the_record_without_the_accounts_address(
    monkeypatch, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The first live night, driven here: Resend named the owner's address
    in its refusal, the pipeline stamped the sentence into docs/data.json,
    and GitHub Pages served it. The log keeps the sentence; the record and
    the page get the domain."""
    import resend

    names = _wide_universe(fake_alpaca, ohlcv, fresh=3)
    monkeypatch.setattr(sys, "argv", ["pipeline", "evening", "--tickers", ",".join(names)])

    def refuse(params, options=None):
        raise RuntimeError("You can only send testing emails to your own email address "
                           "(owner@example.invalid). To send emails to other recipients, "
                           "please verify a domain at resend.com/domains")
    monkeypatch.setattr(resend.Emails, "send", refuse)

    with pytest.raises(SystemExit) as exc:
        pipeline.main()
    assert exc.value.code == pipeline.EXIT_FAILED_AFTER_PUBLISH

    data = clean(tmp_path)
    (email_problem,) = [e for e in data["run"]["errors"] if e["stage"] == "email"]
    assert "…@example.invalid" in email_problem["message"], email_problem
    assert "owner@" not in json.dumps(data), "the address is in no leaf of the public record"


# --- a weekend dispatch is told there is no session today ------------------


SATURDAY = datetime(2026, 9, 5, 22, 16, tzinfo=timezone.utc)   # 18:16 ET, the cron's hour
SUNDAY = datetime(2026, 9, 6, 5, 34, tzinfo=timezone.utc)      # the first live dispatch, 01:34 ET


@pytest.mark.parametrize("instant, day", [(SATURDAY, "Saturday"), (SUNDAY, "Sunday")])
def test_a_weekend_evening_dispatch_is_told_there_is_no_session_today(instant, day):
    """Three weekend dispatches on the first live day were told "today's
    session has not closed yet" -- true of the weekday cron the sentence was
    written for, false on a Saturday, and carried into run.errors and onto
    the page. Real instants, so the real arithmetic is what is tested."""
    said = pipeline.session_disagreement(EVENING, ScanConfig(), now=instant)

    assert said is not None
    assert day in said and "no session to close" in said, said
    assert "has not closed yet" not in said
    assert "2026-09-04" in said, "and it still names the session it read"


def test_a_weekday_evening_run_before_the_close_keeps_its_own_sentence():
    said = pipeline.session_disagreement(EVENING, ScanConfig(), now=BEFORE)
    assert "has not closed yet" in said and "no session to close" not in said


def test_a_weekend_evening_run_still_degrades_and_says_so_on_every_surface(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The wording changes; nothing else does. Exit 2, the session problem
    alone, the DEGRADED subject."""
    universe = _wide_universe(fake_alpaca, ohlcv, fresh=3)
    market_clock.weekend()
    report = pipeline.RunReport()

    scored = pipeline.run("evening", dry_run=False, tickers=universe, report=report)

    assert scored
    assert report.status == "degraded" and report.exit_code == pipeline.EXIT_DEGRADED
    assert [e["stage"] for e in report.errors] == ["session"], report.errors
    assert "no session to close" in report.errors[0]["message"]
    (sent,) = mocked_boundaries["resend"].sent
    assert sent["subject"].startswith("[4% Burst] DEGRADED — ")


# --- the names that have stopped printing ------------------------------------


def test_stopped_printing_keeps_the_names_more_than_a_week_behind_most_behind_first():
    """A halt is one or two sessions; a delisting never comes back. The
    boundary is MORE than STOPPED_PRINTING_SESSIONS, so a name exactly that
    far behind is still a halt to this list. Most-behind first, ties by
    ticker, the count exact and the names capped."""
    session = date(2026, 9, 4)
    stale = {"HALT": date(2026, 9, 3), "EDGE": date(2026, 8, 28),      # 1 and 5 behind: not listed
             "FI": date(2025, 11, 10), "EA": date(2026, 8, 4), "BK": date(2026, 5, 20)}
    block = pipeline.stopped_printing({"session": session, "stale": stale})

    assert block["after_sessions"] == pipeline.STOPPED_PRINTING_SESSIONS == 5
    assert [n["ticker"] for n in block["names"]] == ["FI", "BK", "EA"]
    assert block["names"][2] == {"ticker": "EA", "last": "2026-08-04", "sessions_behind": 23}
    assert block["count"] == 3
    assert ledger.sessions_between(stale["EDGE"], session) == 5, "the boundary case really sits on it"


def test_stopped_printing_names_at_most_the_cap_and_counts_the_rest():
    session = date(2026, 9, 4)
    stale = {f"X{i:02d}": date(2026, 1, 5) - timedelta(days=i) for i in range(14)}
    block = pipeline.stopped_printing({"session": session, "stale": stale})
    assert block["count"] == 14 and len(block["names"]) == pipeline.STOPPED_PRINTING_MAX == 10
    behinds = [n["sessions_behind"] for n in block["names"]]
    assert behinds == sorted(behinds, reverse=True)


def test_stopped_printing_puts_the_names_the_feed_returned_nothing_for_first_with_no_date():
    """A symbol the feed answered with no bar at all -- unknown to it, or the
    old symbol of a rename once purged -- is behind by more than any date can
    say: first, dateless, counted, and still under the cap."""
    session = date(2026, 9, 4)
    block = pipeline.stopped_printing({
        "session": session, "stale": {"FI": date(2025, 11, 10), "HALT": date(2026, 9, 3)},
        "no_bars_names": ["ZZZ", "AAA"]})
    assert [n["ticker"] for n in block["names"]] == ["AAA", "ZZZ", "FI"]
    assert block["names"][0] == {"ticker": "AAA", "last": None, "sessions_behind": None}
    assert block["count"] == 3
    capped = pipeline.stopped_printing({"session": session, "stale": {},
                                        "no_bars_names": [f"N{i:02d}" for i in range(12)]})
    assert capped["count"] == 12 and len(capped["names"]) == pipeline.STOPPED_PRINTING_MAX


def test_stopped_printing_is_empty_and_still_an_object_on_a_clean_night():
    assert pipeline.stopped_printing({"session": date(2026, 9, 4), "stale": {}}) == {
        "after_sessions": pipeline.STOPPED_PRINTING_SESSIONS, "count": 0, "names": []}
    assert pipeline.stopped_printing({}) == {
        "after_sessions": pipeline.STOPPED_PRINTING_SESSIONS, "count": 0, "names": []}


def test_a_name_that_stopped_printing_reaches_the_record_and_the_email(
    market_clock, fake_alpaca, mocked_boundaries, ohlcv, open_gate, tmp_path
):
    """The first live scan: three names in the list had not printed for a
    month or more, and the only trace was a WARNING line. Driven through the
    real evening path with one name thirty sessions behind and one halted for
    a day: the record names the first, the email prints it, and the halt is
    the stale count's business as before."""
    names = _wide_universe(fake_alpaca, ohlcv, fresh=24)
    fake_alpaca.add_history("GONE", ohlcv("burst", variant=90), stale_sessions=30)
    fake_alpaca.add_history("HALT", ohlcv("burst", variant=91), stale_sessions=1)
    # ...and one the double was never given, so the feed answers nothing for
    # it: the state a rename leaves its old symbol in once purged, which
    # reached no surface until it had a place in this block.
    report = pipeline.RunReport()

    pipeline.run("evening", dry_run=False, tickers=names + ["GONE", "HALT", "NOSUCH"], report=report)

    data = clean(tmp_path)
    block = data["run"]["stopped_printing"]
    assert [n["ticker"] for n in block["names"]] == ["NOSUCH", "GONE"], block
    assert block["names"][0] == {"ticker": "NOSUCH", "last": None, "sessions_behind": None}
    assert block["names"][1]["sessions_behind"] == 30 and block["count"] == 2
    assert block["after_sessions"] == pipeline.STOPPED_PRINTING_SESSIONS
    (sent,) = mocked_boundaries["resend"].sent
    assert "Not printing: NOSUCH (no bar at all), GONE (since " in sent["html"]
    assert "HALT" not in sent["html"].split("Not printing")[1].split("</p>")[0]
    assert "since None" not in sent["html"]
    assert f"more than {pipeline.STOPPED_PRINTING_SESSIONS} sessions" in sent["html"]
    assert report.status == "ok", report.errors
