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
