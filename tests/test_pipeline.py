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
from pathlib import Path

import pandas as pd
import pytest

from src import pipeline
from src import scanner
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


def test_morning_and_evening_both_run(universe, mocked_boundaries, open_gate, tmp_path):
    pipeline.run("morning", dry_run=True, tickers=universe)
    assert archived_csv(tmp_path).name.endswith("_morning.csv")


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
    assert book["runs"][1]["forward_returns"] == {
        "d1": first["forward_returns"]["d1"], "d3": want["d3"], "d5": want["d5"], "n": 1}
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
    assert data["runs"][0]["forward_returns"] == {"d1": None, "d3": None, "d5": None, "n": 0}
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
