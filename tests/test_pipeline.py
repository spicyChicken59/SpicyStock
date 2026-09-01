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
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from src import ledger
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
    state = {"closed": True}

    def pinned(now=None):
        return real(now) if now is not None else state["closed"]

    monkeypatch.setattr(scanner, "session_has_closed", pinned)

    class Clock:
        def after_the_close(self) -> None:
            state["closed"] = True

        def before_the_open(self) -> None:
            state["closed"] = False

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
    assert "FeedNotAuthorizedError" in sent["html"] and "delayed_sip" in sent["html"]


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
    sessions = [stamp.date().isoformat() for stamp in frame.index]
    start = sessions.index(burst)
    base = float(frame["close"].iloc[start])
    return {f"d{h}": round((float(frame["close"].iloc[start + h]) / base - 1) * 100, 2)
            for h in horizons if start + h < len(sessions)}


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
    assert book["runs"][1]["forward_returns"] == {
        "d1": first["forward_returns"]["d1"], "d3": want["d3"], "d5": want["d5"],
        "n": 1, "rows": 1}
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
    assert all(c["forward_returns"] == {"d1": None, "d3": None, "d5": None, "as_of": None}
               for c in data["candidates"])
    assert data["runs"][0]["forward_returns"] == {"d1": None, "d3": None, "d5": None,
                                                  "n": 0, "rows": 0}
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
    assert set(row) == {"ticker", "date", "rank", "score", "verdict", "source",
                        "close", "gain_pct", "volume_ratio", "lynch_passes",
                        "lynch_total", "checks", "forward_returns"}
    assert set(row["checks"]) == {"2", "L", "Y", "N", "C", "H"}
    assert sum(row["checks"].values()) == row["lynch_passes"]


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
    assert problem["message"] in sent["html"]
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
    """docs/data.json ships as a fixture of invented rows. Mailing them as a
    watchlist would put made-up names in front of a reader as last night's
    judgements, and would look exactly like a working run."""
    market_clock.before_the_open()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / ledger.DATA_NAME).write_text(
        (Path(__file__).resolve().parent.parent / "docs" / "data.json").read_text())
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
    assert problem["message"] in mocked_boundaries["resend"].sent[0]["html"]


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
