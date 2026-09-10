"""Threshold, session-boundary and persistence checks for the research sidecar."""
from copy import deepcopy
from datetime import date
import json

import pandas as pd
import pytest

from src import ledger, pipeline, stockbee
from src.scanner import ScanConfig


def frame(n=80, *, close=100, volume=90000):
    index = pd.bdate_range(end="2026-08-28", periods=n)
    return pd.DataFrame({"open": close, "high": close * 1.02, "low": close * .98,
                         "close": close, "volume": volume}, index=index, dtype=float)


def burst(*, last_close=104, last_volume=100000, prior_volume=90000):
    df = frame(volume=prior_volume)
    df.loc[df.index[-1], ["open", "high", "low", "close", "volume"]] = [100, max(106, last_close), 99, last_close, last_volume]
    return df


def anticipation():
    df = frame(close=10, volume=100000)
    for stamp in df.index[-7:]:
        df.loc[stamp, ["open", "high", "low", "close"]] = [12, 12.024, 11.976, 12]
    return df


def build(frames, *, through=date(2026, 8, 28), previous=None):
    return stockbee.build(frames, through, requested=len(frames), label="test basket",
                         previous_session=previous, calendar=ledger.session_calendar(frames))


@pytest.mark.parametrize("close,volume,previous_volume,expected", [
    (104, 100000, 90000, 1),  # Both inclusive boundaries qualify.
    (103.9999, 100000, 90000, 0),
    (104, 99999, 90000, 0),
    (104, 100000, 100000, 0),  # Yesterday's volume is a strict comparison.
    (104, 100001, 100000, 1),
])
def test_canonical_scan_boundaries(close, volume, previous_volume, expected):
    data = build({"SCAN": burst(last_close=close, last_volume=volume, prior_volume=previous_volume)})
    assert data["scope"]["measured"] == 1
    assert data["scan"]["matched"] == expected
    assert stockbee.problem(data, session="2026-08-28") is None


def test_scan_coverage_excludes_stale_invalid_and_missing_previous_bars():
    valid = burst()
    hole = valid.drop(valid.index[-2])
    invalid = valid.copy()
    invalid.loc[invalid.index[-1], "low"] = 110
    invalid_previous = valid.copy()
    invalid_previous.loc[invalid_previous.index[-2], "close"] = float("nan")
    data = build({"GOOD": valid, "HOLE": hole, "INVALID": invalid,
                  "BADPREV": invalid_previous, "STALE": valid.iloc[:-1]})
    assert data["scope"] == {"label": "test basket", "requested": 5, "measured": 1, "whole_market": False}
    assert [row["ticker"] for row in data["scan"]["rows"]] == ["GOOD"]
    assert data["breadth"]["days"][-1]["measured"] == 1


def test_future_rows_cannot_change_session_metrics_or_chart():
    original = burst()
    later = pd.concat([original, pd.DataFrame({"open": [1000], "high": [1100], "low": [900], "close": [1050], "volume": [999999]}, index=[pd.Timestamp("2026-08-31")])])
    assert build({"ONE": original}) == build({"ONE": later})


def test_observed_holiday_and_a_lone_hole_have_different_answers():
    df = burst()
    df.index = pd.bdate_range(end="2026-09-08", periods=len(df))
    df = df.drop(pd.Timestamp("2026-09-07"))
    data = build({"ONE": df, "TWO": df.copy()}, through=date(2026, 9, 8), previous=date(2026, 9, 4))
    assert data["scope"]["measured"] == 2
    assert data["scan"]["matched"] == 2
    lone = build({"ONE": df}, through=date(2026, 9, 8))
    assert lone["scope"]["measured"] == 0


def test_one_printed_previous_session_defeats_a_majority_of_holes():
    complete = burst()
    missing = complete.drop(complete.index[-2])
    data = build({"GOOD": complete, "BAD1": missing, "BAD2": missing, "BAD3": missing})
    assert data["scope"]["measured"] == 1
    assert [r["ticker"] for r in data["scan"]["rows"]] == ["GOOD"]


def test_anticipation_measures_tight_existing_trend_without_an_active_burst():
    df = anticipation()
    data = build({"READY": df})
    assert data["scan"]["matched"] == 0
    assert data["anticipation"]["matched"] == 1
    row = data["anticipation"]["rows"][0]
    assert row["compression_ratio"] == pytest.approx(0.1)
    assert row["trend_intensity"] == pytest.approx(12 / ((58 * 10 + 7 * 12) / 65))
    assert row["prior_up_days"] == 0
    assert len(row["series"]) == 30
    assert data["anticipation"]["rules"]["min_contiguous_sessions"] == 67


@pytest.mark.parametrize("failure", ["price", "prior_volume", "trend", "day_move", "wide", "short", "history_hole"])
def test_each_anticipation_filter_removes_an_otherwise_qualifying_name(failure):
    df = anticipation()
    assert build({"READY": df})["anticipation"]["matched"] == 1
    if failure == "price":
        df.loc[:, ["open", "high", "low", "close"]] *= .2
    elif failure == "prior_volume":
        df.loc[df.index[-4], "volume"] = 99999
    elif failure == "trend":
        df.loc[df.index[:-7], ["open", "high", "low", "close"]] *= 1.2
    elif failure == "day_move":
        df.loc[df.index[-1], ["open", "high", "low", "close"]] *= 1.02
    elif failure == "wide":
        df.loc[df.index[-7:], "high"] = 12.24
        df.loc[df.index[-7:], "low"] = 11.76
    elif failure == "short":
        df = df.iloc[-66:]
    else:
        df = df.drop(df.index[-30])
        # A complete second name supplies the date the broken history lost.
        assert build({"READY": df, "CALENDAR": frame()})["anticipation"]["matched"] == 0
        return
    assert build({"READY": df})["anticipation"]["matched"] == 0


def test_missing_lookback_is_null_and_duplicate_daily_bars_are_unmeasured():
    df = burst().iloc[-2:]
    row = build({"NEW": df})["scan"]["rows"][0]
    assert row["trend_intensity"] is None
    assert row["volume_vs_average"] is None
    assert row["prior_up_days"] is None
    assert row["range_expansion"] is None
    duplicate = pd.concat([df, df.iloc[-1:]])
    assert build({"DUP": duplicate})["scope"]["measured"] == 0
    title_case = df.rename(columns=str.title)
    assert build({"NEW": title_case}) == build({"NEW": df})
    title_case["close"] = title_case["Close"]
    assert build({"AMBIGUOUS": title_case}) is None


def test_breadth_counts_each_day_and_ratios_require_coverage_and_a_denominator():
    up, down = frame(n=12), frame(n=12)
    for df, ratio in ((up, 1.04), (down, .96)):
        for at, stamp in enumerate(df.index):
            close = 100 * ratio ** at
            df.loc[stamp] = [close, close * 1.01, close * .99, close, 100000 + at]
    data = build({"UP": up, "DOWN": down})
    assert len(data["breadth"]["days"]) == 10
    assert all(row["measured"] == 2 for row in data["breadth"]["days"])
    # Exact float powers need not land on the boundary; use unambiguous moves.
    for df, ratio in ((up, 1.05), (down, .95)):
        for at, stamp in enumerate(df.index):
            close = 100 * ratio ** at
            df.loc[stamp] = [close, close * 1.01, close * .99, close, 100000 + at]
    data = build({"UP": up, "DOWN": down})
    assert all(row["up4"] == row["down4"] == 1 for row in data["breadth"]["days"])
    assert data["breadth"]["ratios"] == {"d5": 1, "d10": 1}
    assert build({"UP": up})["breadth"]["ratios"] == {"d5": None, "d10": None}
    assert build({"UP": up.iloc[-4:], "DOWN": down.iloc[-4:]})["breadth"]["ratios"] == {"d5": None, "d10": None}
    for df in (up, down):
        df.loc[df.index[-2], "close"] = float("nan")
    assert build({"UP": up, "DOWN": down})["breadth"]["ratios"] == {"d5": None, "d10": None}


def test_rows_are_capped_but_match_totals_are_not():
    frames = {f"B{n}": burst() for n in range(43)}
    frames.update({f"A{n}": anticipation() for n in range(27)})
    data = build(frames)
    assert (data["scan"]["matched"], data["scan"]["shown"]) == (43, 40)
    assert (data["anticipation"]["matched"], data["anticipation"]["shown"]) == (27, 25)
    assert stockbee.problem(data, session="2026-08-28") is None


def test_publish_uses_scan_frames_preserves_metadata_and_keeps_summary_slim(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "DOCS_DIR", tmp_path)
    monkeypatch.setattr(pipeline.scanner, "current_session", lambda: date(2026, 8, 28))
    requests = []
    monkeypatch.setattr(pipeline, "forward_bars", lambda *args: requests.append(args) or {})
    book = ledger.Ledger(tmp_path)
    report = pipeline.RunReport("evening")
    pipeline.publish(run_type="evening", dry_run=True, cfg=ScanConfig(), report=report,
                     scan_stats={"session": date(2026, 8, 28), "requested": 1, "previous_session": date(2026, 8, 27)},
                     score_stats={}, scored=[], unscored=[], to_score=[], n_bursts=0,
                     n_passed=0, shortlist_size=0, chart_errors={}, explicit_tickers=["SCAN"],
                     book=book, marks={}, frames={"SCAN": burst()})
    data = json.loads((tmp_path / "data.json").read_text())
    record = json.loads((tmp_path / "ledger.json").read_text())
    assert data["run"]["stockbee"]["scan"]["matched"] == 1
    assert data["run"]["bursts"] == 0 and data["candidates"] == []
    assert len(data["run"]["stockbee"]["scan"]["rows"][0]["series"]) == 30
    assert "series" not in record["runs"][0]["stockbee"]["scan"]["rows"][0]
    assert "stockbee" not in data["runs"][0]
    assert ledger.Ledger(tmp_path).load().load_error is None
    assert ledger.read_snapshot(tmp_path)[1] is None
    assert len(requests) == 1, "research makes no additional bar request"


@pytest.mark.parametrize("damage", ["version", "coverage", "row", "series", "ratio"])
def test_persisted_metadata_is_validated_before_use(damage):
    data = deepcopy(build({"SCAN": burst()}))
    for legacy_date in (None, 20260901, {"a": 1}, "unreadable"):
        assert stockbee.problem(data, session=legacy_date) is None
    assert stockbee.problem(data, session="2026-08-27")
    invalid_date = {**data, "date": {"a": 1}}
    assert stockbee.problem(invalid_date, session=None)
    if damage == "version":
        data["version"] = True
    elif damage == "coverage":
        data["scope"]["measured"] = 2
    elif damage == "row":
        data["scan"]["rows"][0]["close"] = 101
    elif damage == "series":
        data["scan"]["rows"][0]["series"][-1]["date"] = "2026-08-31"
    else:
        data["breadth"]["ratios"]["d5"] = "12"
    assert stockbee.problem(data, session="2026-08-28")


def test_no_frames_does_not_invent_a_zero_scan():
    assert stockbee.build({}, date(2026, 8, 28), requested=228, label="basket") is None


# ---------------------------------------------------------------------------
# The canonical scan is MEASURED. Before this, src.stockbee ran Bonde's own
# scan over the same universe every night and archived what it matched, and
# nothing ever measured a row of it: read off the committed ledger, 39 of 60
# canonical rows were in neither `candidates` nor `gated`, all 37 anticipation
# rows were, and no sidecar row carried a forward_returns key at all. So the
# one question the sidecar exists to ask -- does the narrower production scan
# keep the better bursts? -- was structurally unanswerable however long the
# record ran.
# ---------------------------------------------------------------------------

def _sidecar_run(session, scan_names, anticipation_names, *, admitted=(), matched=None):
    """A run entry carrying a sidecar, shaped the way add_run() archives one.

    Hand-built rather than driven through build(): what is under test here is
    the ledger's reading of the block, and a synthetic market that produces a
    named list of matches on demand would be a bigger fixture than the rule.
    """
    def row(ticker):
        return {"ticker": ticker, "date": session, "close": 10.0, "prev_close": 9.5,
                "volume": 200000.0, "prev_volume": 100000.0, "gain_pct": 5.26}
    scan = list(scan_names)
    return {
        "date": session, "type": "evening", "status": "ok",
        "candidates": [{"ticker": t, "date": session, "score": 7} for t in admitted],
        "gated": [],
        "stockbee": {
            "version": 1, "date": session,
            "scan": {"matched": matched if matched is not None else len(scan),
                     "shown": len(scan), "rows": [row(t) for t in scan]},
            "anticipation": {"matched": len(anticipation_names), "shown": len(anticipation_names),
                             "rows": [row(t) for t in anticipation_names], "rules": {}},
            "breadth": {"days": [], "ratios": {}}, "measurement_rules": {},
        },
    }


def _frame_through(session, sessions=9, drift=1.0):
    """Bars from the burst session forward, in the SCANNER's column case.

    Capitalised on purpose: src.scanner hands the fill capitalised columns and
    ledger.forward_returns() reads them that way, so a lowercase frame here
    would measure nothing and this file's other helpers -- which feed
    stockbee.build(), a lowercase reader -- are not interchangeable with it.
    """
    index = pd.bdate_range(start=session, periods=sessions)
    closes = [100 + drift * i for i in range(sessions)]
    return pd.DataFrame({"Open": closes, "High": [c + 2 for c in closes],
                         "Low": [c - 2 for c in closes], "Close": closes,
                         "Volume": [1e6] * sessions}, index=index, dtype=float)


def test_a_canonical_row_the_production_scan_never_admitted_is_measured(tmp_path):
    """The 39-of-60 case: a name only Bonde's scan found now gains outcomes.

    MISS is in no candidate and no gated row, so before this change it was in
    no fill queue and could never carry a number.
    """
    book = ledger.Ledger(tmp_path)
    book.runs = [_sidecar_run("2026-09-08", ["MISS", "BOTH"], ["ANTIC"], admitted=["BOTH"])]
    assert "MISS" in book.pending_tickers(date(2026, 9, 22))
    frames = {t: _frame_through("2026-09-08") for t in ("MISS", "BOTH", "ANTIC")}
    book.fill_forward_returns(frames, date(2026, 9, 22), ledger.session_calendar(frames))
    rows = {r["ticker"]: r for r in book.runs[0]["stockbee"]["scan"]["rows"]}
    assert rows["MISS"]["forward_returns"]["d5"] is not None
    assert rows["BOTH"]["forward_returns"]["d5"] == rows["MISS"]["forward_returns"]["d5"]
    antic = book.runs[0]["stockbee"]["anticipation"]["rows"][0]
    assert antic["forward_returns"]["d5"] is not None


def test_a_canonical_row_is_not_in_the_runs_own_scorecard_of_what_its_picks_did(tmp_path):
    """run.settled is what the run's OWN picks did, and a name our scan never
    admitted is not one. The fill measures it and hands nothing back for it."""
    book = ledger.Ledger(tmp_path)
    book.runs = [_sidecar_run("2026-09-08", ["MISS"], ["ANTIC"])]
    frames = {t: _frame_through("2026-09-08") for t in ("MISS", "ANTIC")}
    moved = book.fill_forward_returns(frames, date(2026, 9, 22), ledger.session_calendar(frames))
    assert moved == []
    # ... and it really was measured, so the empty list is about the scorecard
    # and not about the fill having skipped the row.
    assert book.runs[0]["stockbee"]["scan"]["rows"][0]["forward_returns"]["d5"] is not None


def test_the_control_splits_the_canonical_scan_by_what_our_scan_admitted(tmp_path):
    book = ledger.Ledger(tmp_path)
    book.runs = [_sidecar_run("2026-09-08", ["MISS", "ALSO", "BOTH"], ["ANTIC", "ANTIC2"],
                              admitted=["BOTH", "NOTINSCAN"])]
    control = ledger.evidence(book.runs)["stockbee"]
    assert control["caught"]["setups"] == 1
    assert control["missed"]["setups"] == 2
    assert control["anticipation"]["setups"] == 2
    assert control["truncated_sessions"] == {"scan": 0, "dollar": 0, "anticipation": 0}


def test_the_control_counts_a_session_whose_cap_bit(tmp_path):
    """A mean over a capped list is a fact about the cap as well as the market."""
    book = ledger.Ledger(tmp_path)
    book.runs = [_sidecar_run("2026-09-08", ["A", "B"], [], matched=70)]
    assert ledger.evidence(book.runs)["stockbee"]["truncated_sessions"]["scan"] == 1


def test_the_control_counts_every_match_the_scan_printed_not_every_setup(tmp_path):
    """setup_chains() collapses consecutive sessions of one name into one
    setup, which is right for the record's own picks and wrong here: the
    question is about the SCAN, and each session it printed a name is one
    thing the scan said. Two consecutive sessions of AAA are two."""
    book = ledger.Ledger(tmp_path)
    book.runs = [_sidecar_run("2026-09-09", ["AAA"], []),
                 _sidecar_run("2026-09-08", ["AAA"], [])]
    assert ledger.evidence(book.runs)["stockbee"]["missed"]["setups"] == 2


@pytest.mark.parametrize("returns", [
    "measured", 7, [1, 2], {"d1": "up"}, {"from_open": "later"},
    {"from_open": {"d3": True}}, {"as_of": 20260916},
])
def test_a_sidecar_row_whose_returns_are_the_wrong_shape_is_refused(returns):
    """The one-level-short class, closed on the commit that opens the door
    rather than after an audit finds it. One rule, shared with the ledger."""
    data = build({"SCAN": burst()})
    assert stockbee.problem(data, session="2026-08-28") is None
    data["scan"]["rows"][0]["forward_returns"] = returns
    assert stockbee.problem(data, session="2026-08-28")


def test_a_measured_sidecar_row_passes_its_own_validator():
    data = build({"SCAN": burst()})
    data["scan"]["rows"][0]["forward_returns"] = {
        "d1": 1.0, "d3": None, "d5": 4.5, "as_of": "2026-09-04",
        "from_open": {"d1": 0.5, "d3": None, "d5": 4.0}}
    assert stockbee.problem(data, session="2026-08-28") is None


@pytest.mark.parametrize("run,expected", [
    ({}, 0), ({"stockbee": None}, 0), ({"stockbee": []}, 0),
    ({"stockbee": {"scan": None}}, 0), ({"stockbee": {"scan": {"rows": None}}}, 0),
    ({"stockbee": {"scan": {"rows": "AAA"}}}, 0),
    ({"stockbee": {"scan": {"rows": ["AAA"]}}}, 0),
    ({"stockbee": {"scan": {"rows": [{"ticker": 7}]}}}, 0),
    ({"stockbee": {"scan": {"rows": [{"ticker": "AAA"}, {"ticker": None}]}}}, 1),
])
def test_the_sidecar_accessor_never_raises_on_a_shape_a_file_can_hold(run, expected):
    """It is read inside publish(), after the scan and every Claude call have
    been paid for, and by evidence() over runs from before the sidecar
    existed. A list of dicts or nothing, never an exception."""
    assert len(ledger._sidecar_rows(run, "scan")) == expected
    assert ledger._sidecar_rows("not a run", "scan") == []


# ---------------------------------------------------------------------------
# Bonde's OTHER daily scan. He built the $ breakout for exactly the cohort
# this repo's universe is made of -- "more useful on high priced stocks above
# 40 as they do not often breakout with 4% move" -- and it had no counterpart
# here, so the sidecar measured his method only where his own words say the
# 4% trigger does not fit.
# ---------------------------------------------------------------------------

def dollar_bar(*, open_=200.0, close=201.0, volume=150000, prior_close=None):
    """A frame whose last bar has a chosen body, gap and volume."""
    df = frame(close=open_, volume=120000)
    if prior_close is not None:
        df.loc[df.index[-2], ["open", "high", "low", "close"]] = [prior_close] * 4
    df.loc[df.index[-1], ["open", "high", "low", "close", "volume"]] = [
        open_, max(open_, close) + 1, min(open_, close) - 1, close, volume]
    return df


@pytest.mark.parametrize("open_,close,volume,expected", [
    (200.0, 200.90, 150000, 1),    # exactly $0.90 of body qualifies
    # The rule compares the body ROUNDED TO CENTS, and both sides of that
    # boundary are pinned because the decision and the archived `dollar_move`
    # are one number: 89.99 cents PRINTS as $0.90 and is admitted, 89.49
    # prints as $0.89 and is not. An unrounded compare refused 23.90 - 23.00,
    # which is 0.8999999999999986 in binary, under a row reading $0.90.
    (200.0, 200.8999, 150000, 1),
    (200.0, 200.895, 150000, 1),
    (200.0, 200.8949, 150000, 0),
    (200.0, 200.80, 150000, 0),
    (200.0, 200.90, 100000, 1),    # the share floor is inclusive, as in the 4% scan
    (200.0, 200.90, 99999, 0),
])
def test_the_dollar_breakout_boundaries(open_, close, volume, expected):
    data = build({"DOLR": dollar_bar(open_=open_, close=close, volume=volume)})
    assert data["dollar"]["matched"] == expected
    assert stockbee.problem(data, session="2026-08-28") is None


def test_the_dollar_scan_carries_no_price_floor_and_the_disjointness_is_the_real_one():
    """His formula has no price term, and the section still ends up high-priced.

    Measured rather than asserted: $0.90 of body is 4% or more of any close
    under $22.50, so on a name that did not gap, the 4% scan takes every
    cheap dollar breakout and the dollar section is left with the cohort
    Bonde built it for. The floor is emergent, not a rule -- which is why the
    rule states none and every row archives its close.

    A $5 name IS admitted when the gap breaks the identity: crash open, hard
    intraday rally, close still below the previous close.
    """
    cheap = dollar_bar(open_=5.0, close=5.95, volume=150000, prior_close=8.0)
    data = build({"CHEAP": cheap})
    assert data["scan"]["matched"] == 0 and data["dollar"]["matched"] == 1
    assert data["dollar"]["rows"][0]["close"] == pytest.approx(5.95)
    assert stockbee.DOLLAR_RULES["min_price"] is None

    # And the identity itself, at the boundary the arithmetic gives. On a bar
    # that did not gap, the body IS the close-to-close move, so a $0.90 body
    # is 4% or more of any previous close at or under $22.50 and the 4% scan
    # takes it; above that the same body is under 4% and only the $ scan sees
    # it. Both sides asserted, because one alone is satisfied by a rule that
    # never matches anything.
    body = stockbee.DOLLAR_BREAKOUT_MOVE
    assert body / 0.04 == pytest.approx(22.5)
    for previous, expect_dollar in ((22.0, 0), (23.0, 1)):
        gapless = dollar_bar(open_=previous, close=previous + body,
                             volume=150000, prior_close=previous)
        section = build({"X": gapless})
        assert section["dollar"]["matched"] == expect_dollar
        assert section["scan"]["matched"] == 1 - expect_dollar


def test_the_dollar_scan_measures_the_days_body_and_not_the_overnight_gap():
    """His $ scan is c-o, deliberately, where the 4% scan is c/c1.

    A name that gapped $8 and then went nowhere has a huge close-to-close
    move and no body: it is a 4% match and NOT a dollar breakout, and this is
    the one case that tells the two arithmetics apart.
    """
    gapped = dollar_bar(open_=200.0, close=200.10, volume=150000, prior_close=100.0)
    data = build({"GAP": gapped})
    assert data["scan"]["matched"] == 1        # +100% close to close
    assert data["dollar"]["matched"] == 0      # ten cents of body
    assert data["scan"]["rows"][0]["dollar_move"] == pytest.approx(0.10)


def test_a_name_both_scans_match_is_archived_once_under_the_four_percent_scan():
    """The sections are disjoint on purpose: a row in both would be one event
    counted twice by a control that compares populations."""
    both = dollar_bar(open_=200.0, close=210.0, volume=150000, prior_close=200.0)
    data = build({"BOTH": both})
    assert data["scan"]["matched"] == 1
    assert data["dollar"]["matched"] == 0
    assert data["dollar"]["rules"]["excludes_current_4pct_scan_matches"] is True


def test_every_row_carries_the_dollar_move_not_only_the_dollar_sections():
    data = build({"SCAN": burst(), "DOLR": dollar_bar()})
    assert data["scan"]["rows"][0]["dollar_move"] is not None
    assert data["dollar"]["rows"][0]["dollar_move"] == pytest.approx(1.0)


def test_a_dollar_row_that_is_really_a_four_percent_match_is_refused():
    """The validator re-derives both predicates, so a hand-edited record
    cannot move a row between the two populations the control compares."""
    data = build({"SCAN": burst(), "DOLR": dollar_bar()})
    assert stockbee.problem(data, session="2026-08-28") is None
    data["dollar"]["rows"].append(deepcopy(data["scan"]["rows"][0]))
    data["dollar"]["shown"] = data["dollar"]["matched"] = 2
    assert stockbee.problem(data, session="2026-08-28")


def test_a_record_written_before_the_dollar_scan_existed_still_loads():
    data = build({"DOLR": dollar_bar()})
    del data["dollar"]
    assert stockbee.problem(data, session="2026-08-28") is None


def test_the_dollar_population_is_kept_out_of_the_four_percent_controls_split(tmp_path):
    """A dollar row can never be `caught`, since production admits only 4%
    bursts -- so a caught column of zeros would read as a finding rather than
    as arithmetic. It is its own population."""
    run = _sidecar_run("2026-09-08", ["MISS"], [], admitted=["DOLR"])
    run["stockbee"]["dollar"] = {"matched": 1, "shown": 1, "rules": {}, "rows": [
        {"ticker": "DOLR", "date": "2026-09-08", "close": 201.0, "prev_close": 200.5,
         "volume": 200000.0, "prev_volume": 100000.0, "dollar_move": 1.0}]}
    control = ledger.evidence([run])["stockbee"]
    assert control["dollar"]["setups"] == 1
    assert control["caught"]["setups"] == 0 and control["missed"]["setups"] == 1


def test_no_file_keeps_its_own_copy_of_the_sidecar_section_list():
    """One list, read off src.stockbee, everywhere a section is enumerated.

    A hand-kept copy of it went stale THREE separate ways on the commit that
    added a third section, and each failed silently in its own direction:
    the ledger's slimmer stopped dropping `series` from the new rows, which
    alone put 29 MB on the projected year; the contract walker's numeric
    exemption stopped covering them, which turned 56 end-to-end tests red for
    a reason unrelated to any of them; and tools/make_history.py stopped
    rounding their floats, which is what makes the fixture regenerate
    byte-identically on another CPU -- a defect whose only symptom would have
    been a fixture that differs between machines for no visible reason.

    So this reads the source of every file that enumerates sections and
    refuses a literal pair. The one legitimate literal is stockbee's own
    SECTION_LIMITS, and tests/test_history_serialization.py builds a
    deliberately two-section input to exercise the normaliser's tolerance.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parent.parent
    allowed = {"src/stockbee.py", "tests/test_stockbee.py",
               "tests/test_history_serialization.py"}
    pattern = re.compile(r'\("scan",\s*"anticipation"\)|\("anticipation",\s*"scan"\)')
    offenders = []
    for path in sorted((*root.glob("src/*.py"), *root.glob("tools/*.py"),
                        *root.glob("tests/*.py"))):
        relative = path.relative_to(root).as_posix()
        if relative in allowed:
            continue
        if pattern.search(path.read_text()):
            offenders.append(relative)
    assert not offenders, (
        f"{offenders} enumerate the sidecar's sections by hand; read "
        "stockbee.SECTION_LIMITS (or ledger.SIDECAR_SECTIONS) instead")
    assert tuple(stockbee.SECTION_LIMITS) == ledger.SIDECAR_SECTIONS


def test_a_canonical_row_our_scan_found_and_the_gate_rejected_is_caught(tmp_path):
    """`caught` is about what the SCAN found, not what survived the checklist.

    A burst production scanned and then rejected at the gate is a row in
    `gated`, and reading only `candidates` would file it under `missed` — a
    verdict about the scan assembled out of a decision the gate made. The
    control's whole question is whether the narrower SCAN keeps the better
    bursts, so a gate rejection must not move a name across it.

    This case is why the record's own split into `candidates` and `gated`
    exists, and no earlier test here put a canonical name in the second list.
    """
    run = _sidecar_run("2026-09-08", ["SCORED", "GATEDOUT", "NEVERSEEN"], [],
                       admitted=["SCORED"])
    run["gated"] = [{"ticker": "GATEDOUT", "date": "2026-09-08", "reason": "lynch_gate"}]
    control = ledger.evidence([run])["stockbee"]
    assert control["caught"]["setups"] == 2
    assert control["missed"]["setups"] == 1


def test_the_dollar_move_is_rounded_once_and_the_record_shows_what_decided():
    """The other half of the rounding class, and the half that is cheapest to
    reintroduce: rounding again downstream.

    `_dollar_move()` rounds to cents and the row archives that number. A
    second rounding — to a tenth, say — would publish $1.00 for a body of
    $1.04, so the number under the note and the number the rule compared
    would differ again, by more than the first rounding ever moved anything.
    Needs a body whose cents are not zero, which no other test here has.
    """
    data = build({"DOLR": dollar_bar(open_=200.0, close=201.04, volume=150000)})
    assert data["dollar"]["rows"][0]["dollar_move"] == 1.04
