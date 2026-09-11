"""The anticipation watchlist over hand-built coils: every Stage C rule alone,
both sides of every threshold on the rounded number, the box search, the
trigger and stop arithmetic, the ranking and the night's split.

Every rejection test here holds the repo's `_only_failing` discipline: a
second implementation of Stage C (`by_hand`, plain pandas on the same
rounding grid) names the rules a frame fails BEFORE the module is asked, so
a test cannot pass on a rule it did not mean to break, and a threshold moved
in the module disagrees with the hand copy rather than with nothing.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import scans, watchlist
from src.watchlist import COLUMNS

END = "2026-09-10"
SOURCE = Path(__file__).resolve().parent.parent / "src" / "watchlist.py"
SESSIONS = 300


# ------------------------------------------------------------- builders ----


def bar(c: float, *, o: float | None = None, h: float | None = None, l: float | None = None,
        v: float = 200_000) -> tuple:
    """One (Open, High, Low, Close, Volume) bar; the envelope defaults to half a
    dollar either side of the body."""
    o = c if o is None else o
    h = max(o, c) + 0.5 if h is None else h
    l = min(o, c) - 0.5 if l is None else l
    return (o, h, l, c, v)


def frame(bars: list[tuple], scale: float = 1.0) -> pd.DataFrame:
    """Oldest first, one business day per bar, ending on END; prices scaled
    and rounded to the cent so a $5 and an $80 name share one shape."""
    index = pd.bdate_range(end=END, periods=len(bars), name="timestamp")
    df = pd.DataFrame(bars, index=index, columns=list(COLUMNS), dtype=float)
    for column in ("Open", "High", "Low", "Close"):
        df[column] = (df[column] * scale).round(2)
    return df


def coil(*, base_c: float = 100.0, base_range: float = 3.0, base_v: float = 200_000,
         jump_h: float = 114.0, jump_v: float = 600_000,
         shelf_c: float = 113.0, shelf_h: float = 114.0, shelf_l: float = 112.6, shelf_v: float = 180_000,
         coil_n: int = 5, coil_c: float = 110.0, coil_range: float = 1.0, coil_v: float = 120_000,
         coil_closes: list[float] | None = None, coil_highs: list[float] | None = None,
         coil_lows: list[float] | None = None, breakdown_at: tuple[int, ...] = (),
         n: int = SESSIONS, scale: float = 1.0) -> pd.DataFrame:
    """The textbook coil, oldest first: a long flat base at base_c ranging
    base_range dollars a day, a breakout session twelve back (open base_c,
    close shelf_c, high jump_h, low base_c), a shelf at shelf_c that runs to
    the coil, and the last coil_n sessions coiling at coil_c inside
    coil_range dollars. A breakdown_at position (negative, inside the shelf)
    becomes a narrow gap-down day closing 4.1% under the shelf on more volume
    than the day before, which is what scans.breakdown_4pct counts."""
    shelf_n = 11 - coil_n
    bars = [bar(base_c, h=base_c + base_range / 2, l=base_c - base_range / 2, v=base_v)] * (n - 12)
    bars.append((base_c, jump_h, base_c, shelf_c, jump_v))
    bd_c = round(shelf_c * 0.959, 2)
    for pos in range(-11, -coil_n):
        if pos in breakdown_at:
            bars.append((bd_c, bd_c + 0.6, bd_c - 0.6, bd_c, shelf_v + 10_000))
        else:
            bars.append((shelf_c, shelf_h, shelf_l, shelf_c, shelf_v))
    assert len(bars) == n - coil_n
    closes = coil_closes or [coil_c] * coil_n
    for i, c in enumerate(closes):
        h = coil_highs[i] if coil_highs else c + coil_range / 2
        l = coil_lows[i] if coil_lows else c - coil_range / 2
        bars.append((c, h, l, c, coil_v))
    return frame(bars, scale)


def by_hand(df: pd.DataFrame) -> dict:
    """Stage C recomputed in pandas: a second arithmetic on the same grid --
    cent prices, ranges and means at a tenth of a percent, ratios at a
    hundredth -- so the module's answer has something to disagree with."""
    px = df[["Open", "High", "Low", "Close"]].round(2)
    v = df["Volume"].round(0)
    c = px["Close"]
    rng = 100 * (px["High"] - px["Low"]) / c
    adr = round(rng.iloc[-21:-1].mean(), 1)
    limit = round(0.7 * adr, 1)
    tight = [round(r, 1) < limit for r in rng.iloc[-10:]]
    tight_n, ttt, tt = sum(tight), all(tight[-3:]), all(tight[-2:])
    compress = round(round(rng.iloc[-7:].mean(), 1) / round(rng.iloc[-67:-7].mean(), 1), 2)
    volume_ratio = round(round(v.iloc[-5:].mean()) / round(v.iloc[-50:].mean()), 2)
    ratio = (c / c.shift(1)).round(4)
    breakdowns = int(((ratio <= 0.96) & (v > v.shift(1)) & (v >= 100_000)).iloc[-10:].sum())
    up_run = 0
    while c.iloc[-1 - up_run] > c.iloc[-2 - up_run]:
        up_run += 1
    extension = round(c.iloc[-1] / round(c.iloc[-20:].mean(), 2), 2)
    spread_limit = round(adr / 100 * c.iloc[-1], 2)
    box_len = next((k for k in range(10, 2, -1)
                    if round(px["High"].iloc[-k:].max() - px["High"].iloc[-k:].min(), 2) <= spread_limit), None)
    trigger = None if box_len is None else round(px["High"].iloc[-box_len:].max() + max(0.02, 0.001 * c.iloc[-1]), 2)
    stop = px["Low"].iloc[-3:].min()
    risk = None if trigger is None else round(100 * (trigger / stop - 1), 1)
    passing = {"tight": ttt or tight_n >= 3, "compress": compress <= 0.75, "breakdowns": breakdowns <= 1,
               "up_run": up_run <= 2, "extension": extension <= 1.10, "box": box_len is not None}
    return {"adr20_pct": adr, "tight_limit_pct": limit, "tight_n": tight_n, "ttt": ttt, "tt": tt,
            "compress": compress, "volume_ratio": volume_ratio, "breakdowns": breakdowns,
            "up_run": up_run, "extension": extension, "box_len": box_len, "trigger": trigger,
            "stop_primary": float(stop), "stop_alt": float(px["Low"].iloc[-1]), "risk_pct": risk,
            "failing": {rule for rule, ok in passing.items() if not ok}}


def base_bar(v: float = 200_000) -> tuple:
    return (100.0, 101.5, 98.5, 100.0, v)


def momentum_frame(tail: list[tuple], n: int = SESSIONS) -> pd.DataFrame:
    """A flat base at 100 under an explicit tail of bars, oldest first; the
    tail carries its own breakout so Stage A matches on TI65."""
    return frame([base_bar()] * (n - len(tail)) + tail)


JUMP = (100.0, 111.0, 100.0, 110.0, 600_000)


def tight_boundary_frame(today: tuple) -> pd.DataFrame:
    """Twenty sessions ending yesterday all ranging 2.0% at 110, so ADR20 is
    2.0 and the tight limit 1.4; ``today`` is the bar under test."""
    return momentum_frame([JUMP] + [(110.0, 111.1, 108.9, 110.0, 150_000)] * 20 + [today])


def compress_boundary_frame(recent: tuple) -> pd.DataFrame:
    """Sixty sessions ranging 10.0% (45 at 100, the jump, 14 at 110), then
    seven of ``recent``: compress is the recent range over 10.0."""
    return momentum_frame([(100.0, 105.0, 95.0, 100.0, 200_000)] * 45 + [JUMP]
                          + [(110.0, 115.5, 104.5, 110.0, 150_000)] * 14 + [recent] * 7)


def only_failing(df: pd.DataFrame, *rules: str) -> None:
    """Precondition: the hand copy of Stage C says exactly these rules fail."""
    assert by_hand(df)["failing"] == set(rules)


# ---------------------------------------------------------- the textbook ----


def test_the_textbook_coil_is_admitted_with_the_numbers_computed_by_hand():
    """Base ranging 3.0% at 100, a breakout to 113 twelve sessions back, a
    1.2% shelf at 113, five sessions coiling in one dollar at 110 on drying
    volume. Every number below was computed by hand before the module ran:
    ADR20 over the 20 sessions ending yesterday is 9 base bars, the breakout
    bar (14/113 = 12.4%), 6 shelf bars (1.4/113 = 1.2%) and 4 coil bars
    (1/110 = 0.9%) -- (27 + 12.4 + 7.4 + 3.6)/20 = 2.5 -- so the tight limit
    is 0.7 * 2.5 = 1.75, printed 1.8; the recent seven range 1.0 against a
    base of 3.0; the box is the five coil highs at 110.50, one dollar above
    the shelf's 114.00 is 3.5 apart against a limit of 2.5% of 110 = 2.75;
    the trigger is 110.50 + max(0.02, 0.11) and the stop the coil low."""
    df = coil()
    got = watchlist.measure(df)
    assert got["admitted"] is True and got["reasons_failed"] == []
    assert got["setups"] == ["TI65"] and got["ti65"] == 1.085 and got["dt"] is None and got["mdt"] is None
    assert got["pct_change_today"] == 0.0 and got["narrow_range_days"] == 7 and got["close"] == 110.0
    assert got["adr20_pct"] == 2.5 and got["tight_limit_pct"] == 1.8
    assert got["range_pct_today"] == 0.9 and got["tight_today"] is True
    assert got["tight_n"] == 10 and got["ttt"] is True and got["tt"] is True
    assert got["range_recent_pct"] == 1.0 and got["range_base_pct"] == 3.0 and got["compress"] == 0.33
    assert got["volume_ratio"] == 0.61 and got["vol_dry"] is True
    assert got["breakdowns"] == 0 and got["up_run"] == 0
    assert got["close_avg"] == 107.05 and got["extension"] == 1.03
    assert got["box"] == {"high": 110.5, "low": 109.5, "length": 5, "spread": 0.0, "spread_limit": 2.75,
                          "start": "2026-09-04", "end": END}
    assert got["trigger"] == 110.61 and got["stop_primary"] == 109.5 and got["stop_alt"] == 109.5
    assert got["risk_pct"] == 1.0 and got["eligible"] is True
    hand = by_hand(df)
    for key in ("adr20_pct", "tight_limit_pct", "tight_n", "ttt", "tt", "compress", "volume_ratio",
                "breakdowns", "up_run", "extension", "trigger", "stop_primary", "stop_alt", "risk_pct"):
        assert got[key] == hand[key], key


def test_at_names_the_session_judged_and_refuses_what_is_not_a_position():
    df = coil()
    assert watchlist.measure(df, at=len(df) - 1) == watchlist.measure(df, at=-1)
    earlier = watchlist.measure(df, at=-2)
    assert earlier is not None and earlier["box"]["end"] == "2026-09-09" and earlier["box"]["length"] == 4
    assert watchlist.measure(df, at=len(df)) is None
    assert watchlist.measure(df, at=True) is None
    assert watchlist.measure("not a frame") is None


def test_stage_a_values_pass_through_from_scans():
    """A DT match on a flat tape: the ratio scans measured is on the row, and
    the flat ranges fail the tight and compression rules and nothing else."""
    bars = [bar(100.0)] * 252
    bars[100] = bar(100.0, l=50.0)
    df = frame(bars)
    only_failing(df, "tight", "compress")
    got = watchlist.measure(df)
    assert got["setups"] == ["DT"] and got["dt"] == 2.0 and got["ti65"] is None and got["mdt"] is None
    assert got["reasons_failed"] == ["tight", "compress"] and got["admitted"] is False
    assert got["box"]["length"] == watchlist.BOX_MAX


# ------------------------------------------------ each rule failing alone ----


ALONE = {
    "tight": dict(coil_range=2.42, shelf_h=114.24, shelf_l=111.76),
    "compress": dict(base_range=0.9),
    "breakdowns": dict(breakdown_at=(-9, -7)),
    "up_run": dict(coil_closes=[110.0, 108.4, 108.9, 109.4, 110.0]),
    "extension": dict(base_c=81.0),
    "box": dict(coil_highs=[110.5, 114.0, 110.5, 114.0, 110.5]),
}


@pytest.mark.parametrize("rule", list(ALONE))
def test_each_stage_c_rule_can_fail_alone(rule):
    """The hand copy names exactly this rule as failing before the module is
    asked, so the refusal is on the rule the test is about and no other."""
    df = coil(**ALONE[rule])
    only_failing(df, rule)
    got = watchlist.measure(df)
    assert got["reasons_failed"] == [rule] and got["admitted"] is False
    assert rule in watchlist.STAGE_C


def test_the_reasons_are_named_in_stage_c_order():
    df = coil(breakdown_at=(-9, -7), coil_closes=[110.0, 108.4, 108.9, 109.4, 110.0])
    only_failing(df, "breakdowns", "up_run")
    assert watchlist.measure(df)["reasons_failed"] == ["breakdowns", "up_run"]


# ------------------------------------------------------------ boundaries ----


@pytest.mark.parametrize("today,range_pct,tight", [
    ((110.0, 110.77, 109.23, 110.0, 150_000), 1.4, False),   # 1.54/110: exactly 0.70 x ADR20
    ((110.0, 110.72, 109.28, 110.0, 150_000), 1.3, True),    # 1.44/110
])
def test_a_range_at_exactly_seventy_percent_of_adr_is_not_tight(today, range_pct, tight):
    got = watchlist.measure(tight_boundary_frame(today))
    assert got["adr20_pct"] == 2.0 and got["tight_limit_pct"] == 1.4
    assert got["range_pct_today"] == range_pct and got["tight_today"] is tight
    assert got["tight_n"] == int(tight) and got["ttt"] is False and got["tt"] is False


@pytest.mark.parametrize("recent,compress,passes", [
    ((110.0, 114.13, 105.88, 110.0, 150_000), 0.75, True),   # 8.25/110 = 7.5%
    ((110.0, 114.18, 105.82, 110.0, 150_000), 0.76, False),  # 8.36/110 = 7.6%
])
def test_compress_passes_at_the_limit_and_fails_one_hundredth_over(recent, compress, passes):
    df = compress_boundary_frame(recent)
    assert by_hand(df)["compress"] == compress
    got = watchlist.measure(df)
    assert got["range_base_pct"] == 10.0 and got["compress"] == compress
    assert ("compress" not in got["reasons_failed"]) is passes


def test_compress_divides_the_printed_means_and_not_the_raw_ones():
    """Coil bars ranging 1.1 dollars: the recent seven average 1.068% raw,
    printed 1.1, over a base printed 3.0 -- 0.37 off the record's own
    numbers, where the raw means give 0.35. The reader's arithmetic and the
    module's are one."""
    df = coil(coil_range=1.1)
    assert by_hand(df)["compress"] == 0.37
    got = watchlist.measure(df)
    assert got["range_recent_pct"] == 1.1 and got["range_base_pct"] == 3.0 and got["compress"] == 0.37


@pytest.mark.parametrize("base_c,extension,passes", [(82.4, 1.10, True), (81.0, 1.11, False)])
def test_extension_passes_at_ten_percent_over_the_average_and_fails_at_eleven(base_c, extension, passes):
    df = coil(base_c=base_c)
    only_failing(df, *([] if passes else ["extension"]))
    got = watchlist.measure(df)
    assert got["extension"] == extension
    assert ("extension" not in got["reasons_failed"]) is passes


def test_extension_divides_the_printed_average_and_not_the_raw_one():
    """Twenty closes averaging 99.5455: printed 99.55, and 110 over that is
    1.10 (admitted) where 110 over the raw mean is 1.11 (refused). The
    record's own two numbers decide, not a third the reader cannot see."""
    df = coil(base_c=80.81, shelf_c=113.49)
    only_failing(df)
    got = watchlist.measure(df)
    assert got["close_avg"] == 99.55 and got["extension"] == 1.10 == by_hand(df)["extension"]
    assert got["admitted"] is True


def test_the_volume_ratio_divides_the_printed_means_and_not_the_raw_ones():
    """Five sessions at 164,686 shares over a fifty-session mean of 202,068.6:
    printed 202,069, and the ratio off that is 0.81 where the raw one is 0.82."""
    df = coil(coil_v=164_686, shelf_v=180_000)
    assert by_hand(df)["volume_ratio"] == 0.81
    assert watchlist.measure(df)["volume_ratio"] == 0.81


def test_the_stop_wider_reason_follows_the_risk_constant():
    """The module re-run under a moved MAX_RISK_PCT: the reason names the
    moved number, so the string cannot be a second spelling of 4."""
    source = SOURCE.read_text()
    moved = source.replace("MAX_RISK_PCT = 4.0", "MAX_RISK_PCT = 3.5")
    assert moved != source
    namespace = {"__name__": "watchlist_under_test"}
    exec(compile(moved, str(SOURCE), "exec"), namespace)
    assert namespace["STOP_WIDER"] == "stop wider than 3.5%" and namespace["RULES"]["watchlist.max_risk_pct"] == 3.5
    assert watchlist.STOP_WIDER == "stop wider than 4%"


@pytest.mark.parametrize("at,count,passes", [((-7,), 1, True), ((-9, -7), 2, False)])
def test_one_breakdown_in_the_consolidation_is_allowed_and_two_are_not(at, count, passes):
    df = coil(breakdown_at=at)
    only_failing(df, *([] if passes else ["breakdowns"]))
    got = watchlist.measure(df)
    assert got["breakdowns"] == count and got["admitted"] is passes


def test_a_breakdown_is_what_scans_counts_and_a_quiet_down_day_is_not():
    """The count reads scans.breakdown_4pct, volume clauses included: the
    same 4.1% gap down on LESS volume than the day before is not a 4% b/d."""
    df = coil(breakdown_at=(-9, -7))
    df.loc[df.index[-9], "Volume"] = 170_000
    df.loc[df.index[-7], "Volume"] = 170_000
    assert watchlist.measure(df)["breakdowns"] == 0
    assert scans.breakdown_4pct(df, at=-7) is None


@pytest.mark.parametrize("closes,run,passes", [
    ([110.0, 110.0, 108.9, 109.4, 110.0], 2, True),
    ([110.0, 108.4, 108.9, 109.4, 110.0], 3, False),
])
def test_two_up_closes_in_a_row_pass_and_three_fail(closes, run, passes):
    df = coil(coil_closes=closes)
    only_failing(df, *([] if passes else ["up_run"]))
    got = watchlist.measure(df)
    assert got["up_run"] == run and got["admitted"] is passes and got["pct_change_today"] == 0.55


def test_an_equal_close_ends_the_up_run():
    df = coil(coil_closes=[108.4, 108.9, 109.4, 110.0, 110.0])
    assert by_hand(df)["up_run"] == 0
    assert watchlist.measure(df)["up_run"] == 0


@pytest.mark.parametrize("low,risk,eligible", [(106.32, 4.0, True), (106.30, 4.1, False)])
def test_a_four_percent_stop_is_eligible_and_a_tenth_wider_is_not(low, risk, eligible):
    """The stop is the lowest low of the last three sessions, here the one
    three back; the trigger is 110.61 either way."""
    df = coil(coil_lows=[109.5, 109.5, low, 109.5, 109.5])
    only_failing(df)
    got = watchlist.measure(df)
    assert got["admitted"] is True and got["trigger"] == 110.61
    assert got["stop_primary"] == low and got["stop_alt"] == 109.5
    assert got["risk_pct"] == risk and got["eligible"] is eligible


def test_the_stop_reads_the_last_three_sessions_and_not_a_fourth():
    df = coil(coil_lows=[109.5, 106.0, 109.5, 109.5, 109.5])
    assert watchlist.measure(df)["stop_primary"] == 109.5
    df = coil(coil_lows=[109.5, 109.5, 106.0, 109.5, 109.5])
    assert watchlist.measure(df)["stop_primary"] == 106.0


@pytest.mark.parametrize("scale,close,bump", [(5 / 110, 5.0, 0.02), (80 / 110, 80.0, 0.08)])
def test_the_trigger_is_two_cents_or_a_tenth_of_a_percent_whichever_is_more(scale, close, bump):
    got = watchlist.measure(coil(scale=scale))
    assert got["close"] == close and got["admitted"] is True
    assert got["trigger"] == round(got["box"]["high"] + bump, 2)
    assert got["trigger"] == by_hand(coil(scale=scale))["trigger"]


@pytest.mark.parametrize("coil_v,ratio,dry", [(208_889, 1.0, False), (206_000, 0.99, True)])
def test_volume_is_dry_below_the_fifty_session_average_and_decides_nothing(coil_v, ratio, dry):
    df = coil(coil_v=coil_v, shelf_v=200_000)
    assert by_hand(df)["volume_ratio"] == ratio
    got = watchlist.measure(df)
    assert got["volume_ratio"] == ratio and got["vol_dry"] is dry and got["admitted"] is True


def test_tt_and_ttt_are_read_off_the_last_two_and_three_sessions():
    wide = coil(coil_highs=[110.5, 110.5, 110.5, 111.9, 110.5], coil_lows=[109.5, 109.5, 109.5, 108.1, 109.5])
    got = watchlist.measure(wide)
    assert got["tight_n"] == 9 and got["ttt"] is False and got["tt"] is False and got["admitted"] is True
    wide = coil(coil_highs=[110.5, 110.5, 111.9, 110.5, 110.5], coil_lows=[109.5, 109.5, 108.1, 109.5, 109.5])
    got = watchlist.measure(wide)
    assert got["tight_n"] == 9 and got["ttt"] is False and got["tt"] is True


def test_ttt_implies_the_tight_gate_at_these_constants():
    """`ttt or tight_n >= MIN_TIGHT` reads as written in the spec; while
    MIN_TIGHT <= TTT_SESSIONS <= TIGHT_LOOKBACK the first clause implies the
    second, and this pins the relation so the clause is not a silent no-op
    under a later constant."""
    assert watchlist.MIN_TIGHT <= watchlist.TTT_SESSIONS <= watchlist.TIGHT_LOOKBACK
    assert watchlist.TT_SESSIONS < watchlist.TTT_SESSIONS


# ------------------------------------------------------------------ box ----


def test_a_four_session_run_beats_none_and_ten_is_the_cap():
    four = watchlist.measure(coil(coil_n=4))
    assert four["box"]["length"] == 4 and four["box"]["high"] == 110.5 and four["admitted"] is True
    ten = watchlist.measure(coil(coil_n=10))
    assert ten["box"]["length"] == 10
    eleven = watchlist.measure(coil(coil_n=11))
    assert eleven["box"]["length"] == watchlist.BOX_MAX == 10


def test_highs_spread_beyond_one_adr_break_the_run():
    """Alternating highs at 110.5 and 114.0 under a 3.08 limit: no three
    consecutive sessions sit together, so there is no box, no trigger and no
    risk, and the name fails on the box alone."""
    df = coil(coil_highs=[110.5, 114.0, 110.5, 114.0, 110.5])
    only_failing(df, "box")
    got = watchlist.measure(df)
    assert got["box"] is None and got["trigger"] is None and got["risk_pct"] is None
    assert got["eligible"] is False and got["reasons_failed"] == ["box"]


@pytest.mark.parametrize("sixth_back,length", [(113.25, 6), (113.26, 5)])
def test_the_box_edge_is_inclusive_on_the_rounded_spread(sixth_back, length):
    """The limit is 2.5% of 110 = 2.75; a sixth-back high 2.75 above the coil
    is inside the box, 2.76 is not."""
    df = coil()
    df.loc[df.index[-6], "High"] = sixth_back
    assert by_hand(df)["box_len"] == length
    got = watchlist.measure(df)
    assert got["box"]["spread_limit"] == 2.75 and got["box"]["length"] == length


# ----------------------------------------------------------- unreadable ----


def test_a_nan_in_a_stage_c_window_is_none_and_not_a_number():
    for column, back in (("High", 3), ("Volume", 40), ("Low", 1), ("Close", 65)):
        df = coil()
        df.loc[df.index[-back], column] = np.nan
        assert watchlist.measure(df) is None, (column, back)


def test_a_frame_shorter_than_the_compression_base_is_none():
    df = coil()
    assert watchlist.measure(df.iloc[-66:]) is None
    assert scans.anticipation(df.iloc[-66:]) is not None
    assert watchlist.measure(df.iloc[-67:]) is not None


def test_no_stage_a_or_b_match_is_none():
    assert watchlist.measure(frame([bar(100.0)] * SESSIONS)) is None
    loud = coil(coil_closes=[110.0, 110.0, 110.0, 110.0, 112.5])
    assert scans.trend_intensity(loud) is not None and scans.anticipation(loud) is None
    assert watchlist.measure(loud) is None


# -------------------------------------------------------------- ranking ----


def test_ttt_ranks_first_then_ti65_descending_then_compress_ascending():
    rows = {
        "A": watchlist.measure(coil()),                              # ttt, TI65 1.085, compress 0.33
        "B": watchlist.measure(coil(base_c=95.0, coil_highs=[110.5, 110.5, 110.5, 111.9, 110.5],
                                    coil_lows=[109.5, 109.5, 109.5, 108.1, 109.5])),  # no ttt, TI65 1.13
        "C": watchlist.measure(coil(base_range=3.5)),                # ttt, TI65 1.085, compress 0.29
        "D": watchlist.measure(coil(base_c=99.0)),                   # ttt, TI65 1.0938
    }
    assert rows["B"]["ttt"] is False and rows["B"]["ti65"] == 1.1301
    assert rows["A"]["ti65"] == rows["C"]["ti65"] == 1.085 and rows["D"]["ti65"] == 1.0938
    assert rows["C"]["compress"] == 0.29 < rows["A"]["compress"] == 0.33
    assert all(row["admitted"] for row in rows.values())
    ranked = sorted(rows, key=lambda t: watchlist.rank_key(rows[t]))
    assert ranked == ["D", "C", "A", "B"]


def test_rank_key_reads_a_missing_ti65_as_zero():
    a = {"ttt": True, "ti65": None, "compress": 0.3, "ticker": "A"}
    b = {"ttt": True, "ti65": 0.99, "compress": 0.3, "ticker": "B"}
    assert watchlist.rank_key(b) < watchlist.rank_key(a)


# ---------------------------------------------------------------- build ----


def night() -> dict[str, pd.DataFrame]:
    frames = {t: coil(base_range=r) for t, r in zip("ABCDEF", (3.5, 3.4, 3.3, 3.2, 3.1, 3.0))}
    frames["G"] = coil(coil_lows=[109.5, 109.5, 106.30, 109.5, 109.5])   # admitted, risk 4.1%
    frames["H"] = coil(base_range=0.9)                                    # short by compress alone
    frames["I"] = coil(breakdown_at=(-9, -7), coil_closes=[110.0, 108.4, 108.9, 109.4, 110.0])  # short by two
    frames["J"] = coil(coil_closes=[110.0, 110.0, 110.0, 110.0, 112.5])   # momentum, not quiet
    frames["K"] = frame([bar(100.0)] * SESSIONS)                          # nothing
    frames["L"] = None                                                    # not a frame
    bars = [bar(100.0)] * 252                                             # DT alone, short by two
    bars[100] = bar(100.0, l=50.0)
    frames["M"] = frame(bars)
    return frames


def test_build_splits_the_night_into_top_also_quiet_and_counts():
    got = watchlist.build(night())
    assert [row["ticker"] for row in got["top"]] == ["A", "B", "C", "D", "E"]
    assert [(row["ticker"], row["why"]) for row in got["also_quiet"]] == [
        ("F", "outside the top 5"), ("G", "stop wider than 4%"), ("H", "failed compress")]
    assert got["counts"] == {"momentum": 11, "quiet": 10, "admitted": 7, "eligible": 6}
    assert got["rules"] == watchlist.RULES
    assert all(row["admitted"] and row["eligible"] for row in got["top"])
    keys = [watchlist.rank_key(row) for row in got["top"]]
    assert keys == sorted(keys)
    assert watchlist.STOP_WIDER == "stop wider than 4%" and watchlist.MAX_RISK_PCT == 4.0


def test_build_honours_top_n_and_also_n():
    got = watchlist.build(night(), top_n=2, also_n=3)
    assert [row["ticker"] for row in got["top"]] == ["A", "B"]
    assert [row["ticker"] for row in got["also_quiet"]] == ["C", "D", "E"]
    assert got["also_quiet"][0]["why"] == "outside the top 2"
    assert got["counts"]["eligible"] == 6
    assert watchlist.build({})["counts"] == {"momentum": 0, "quiet": 0, "admitted": 0, "eligible": 0}


def test_build_defaults_are_the_archived_top_and_also_counts():
    assert watchlist.TOP_N == 5 and watchlist.ALSO_N == 10
    frames = {f"T{i}": coil(base_range=3.0 + i / 100) for i in range(7)}
    got = watchlist.build(frames)
    assert len(got["top"]) == 5 and len(got["also_quiet"]) == 2
    assert all(row["why"] == "outside the top 5" for row in got["also_quiet"])


def test_every_value_is_one_the_record_can_hold():
    def plain(value) -> bool:
        if value is None or isinstance(value, (bool, int, float, str)):
            return type(value) in (bool, int, float, str, type(None))
        if isinstance(value, list):
            return all(plain(v) for v in value)
        return isinstance(value, dict) and all(plain(v) for v in value.values())

    for df in (coil(), coil(coil_highs=[110.5, 114.0, 110.5, 114.0, 110.5]), coil(scale=5 / 110)):
        got = watchlist.measure(df)
        assert plain(got) and json.loads(json.dumps(got)) == got
    got = watchlist.build(night())
    assert plain(got) and json.loads(json.dumps(got)) == got


# ---------------------------------------------------------------- rules ----


def _module_ast() -> ast.Module:
    return ast.parse(SOURCE.read_text())


def _named_constants() -> dict[str, float]:
    """Every upper-case module-level name bound to a number."""
    found = {}
    for node in _module_ast().body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id.isupper() \
                and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, (int, float)) \
                and not isinstance(node.value.value, bool):
            found[node.targets[0].id] = node.value.value
    return found


def test_every_named_number_is_archived_in_rules_with_its_provenance():
    """RULES is read off the source: the names its values are bound to must
    cover every upper-case number the module names, every key is a
    watchlist.* key, PROVENANCE marks each one (B) or (P), and the numbers
    the spec states are the numbers archived."""
    constants = _named_constants()
    assert len(constants) >= 25
    rules_node = next(node for node in _module_ast().body
                      if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                      and node.targets[0].id == "RULES")
    read = {value.id for value in rules_node.value.values if isinstance(value, ast.Name)}
    assert set(constants) <= read, f"named but not archived: {set(constants) - read}"
    assert all(key.startswith("watchlist.") for key in watchlist.RULES)
    assert all(isinstance(v, (int, float, bool)) for v in watchlist.RULES.values())
    assert set(watchlist.PROVENANCE) == set(watchlist.RULES)
    assert set(watchlist.PROVENANCE.values()) == {"B", "P"}
    R = watchlist.RULES
    assert R["watchlist.tight_fraction_exclusive"] == 0.70 and R["watchlist.min_tight"] == 3
    assert R["watchlist.max_compress"] == 0.75 and R["watchlist.max_breakdowns"] == 1
    assert R["watchlist.max_up_run"] == 2 and R["watchlist.max_extension"] == 1.10
    assert R["watchlist.box_min_sessions"] == 3 and R["watchlist.box_max_sessions"] == 10
    assert R["watchlist.trigger_cents"] == 0.02 and R["watchlist.trigger_fraction"] == 0.001
    assert R["watchlist.stop_sessions"] == 3 and R["watchlist.max_risk_pct"] == 4.0
    assert R["watchlist.top_n"] == 5 and R["watchlist.also_n"] == 10
    assert R["watchlist.adr_sessions"] == 20 and R["watchlist.tight_lookback"] == 10
    assert R["watchlist.ttt_sessions"] == 3 and R["watchlist.tt_sessions"] == 2
    assert R["watchlist.compress_recent_sessions"] == 7 and R["watchlist.compress_base_sessions"] == 60
    assert R["watchlist.vol_dry_recent_sessions"] == 5 and R["watchlist.vol_dry_base_sessions"] == 50
    assert R["watchlist.breakdown_lookback"] == 10 and R["watchlist.extension_sessions"] == 20
    assert R["watchlist.box_spread_adrs"] == 1 and R["watchlist.price_decimals"] == scans.CENTS == 2
    assert R["watchlist.ratio_decimals"] == 2 and R["watchlist.pct_decimals"] == 1
    bonde = {k for k, v in watchlist.PROVENANCE.items() if v == "B"}
    assert bonde == {"watchlist.tight_lookback", "watchlist.ttt_sessions", "watchlist.tt_sessions",
                     "watchlist.max_breakdowns", "watchlist.max_up_run", "watchlist.box_min_sessions",
                     "watchlist.box_max_sessions", "watchlist.stop_sessions", "watchlist.max_risk_pct",
                     "watchlist.top_n"}


def test_no_function_spells_a_threshold_as_a_literal():
    """A number inside a function body is arithmetic (0, 1, 100) or a
    threshold that should have been a named constant; the guard reads the
    source because a value check cannot tell a literal from a name that
    agrees with it tonight."""
    literals = {}
    for node in ast.walk(_module_ast()):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                if isinstance(inner, ast.Constant) and isinstance(inner.value, (int, float)) \
                        and not isinstance(inner.value, bool) and inner.value not in (0, 1, 100):
                    literals.setdefault(node.name, []).append(inner.value)
    assert not literals, literals


def test_stage_c_names_every_rule_reasons_failed_can_carry():
    assert watchlist.STAGE_C == ("tight", "compress", "breakdowns", "up_run", "extension", "box")
    seen = set()
    for kw in ALONE.values():
        seen.update(watchlist.measure(coil(**kw))["reasons_failed"])
    assert seen == set(watchlist.STAGE_C)
