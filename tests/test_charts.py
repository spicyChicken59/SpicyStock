"""src.charts: the picture Claude reads, and what is drawn on it.

Rendering is checked two ways. A spy stands in for mplfinance to read the
frame and the kwargs the chart hands it, which is where the eighty-five-bar
window, the cut and the annotation specs are decided; and the real renderer
writes PNGs whose BYTES are compared, because "a PNG was produced" passes
whether or not a hole was blanked or a line was drawn.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.charts import MOVING_AVERAGES, PRICE_COLUMNS, SESSIONS, render_chart

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _plot_spy(monkeypatch, seen: dict):
    """Replace mplfinance with a recorder that writes a stub PNG."""

    class _Spy:
        @staticmethod
        def plot(df, **kwargs):
            seen["frame"] = df
            seen["index"] = df.index
            seen["kwargs"] = kwargs
            Path(kwargs["savefig"]["fname"]).write_bytes(PNG_MAGIC + b"x" * 32)

    monkeypatch.setitem(sys.modules, "mplfinance", _Spy)


def _png(path: str) -> bytes:
    data = Path(path).read_bytes()
    assert data.startswith(PNG_MAGIC)
    assert len(data) > 20_000, "a chart this small is probably an empty canvas"
    return data


# --------------------------------------------------------------- the file ----


def test_render_chart_writes_a_real_png(ohlcv, tmp_path):
    out = tmp_path / "charts"
    path = Path(render_chart("AAA", ohlcv("burst"), str(out)))
    assert path == out / "AAA.png"
    _png(str(path))


def test_render_chart_defaults_into_the_working_directory(ohlcv, tmp_path):
    """The default out_dir is relative, which is why the suite runs inside
    tmp_path (see conftest's _isolated_cwd)."""
    render_chart("AAA", ohlcv("burst"))
    assert (tmp_path / "charts" / "AAA.png").exists()


def test_the_plot_is_candles_volume_and_the_three_averages_in_the_clean_style(ohlcv, tmp_path,
                                                                             monkeypatch):
    seen: dict = {}
    _plot_spy(monkeypatch, seen)
    render_chart("AAA", ohlcv("burst"), str(tmp_path))
    kwargs = seen["kwargs"]
    assert kwargs["type"] == "candle" and kwargs["volume"] is True
    assert kwargs["mav"] == MOVING_AVERAGES == (10, 20, 50)
    assert kwargs["style"] == "yahoo"
    assert kwargs["figsize"] == (10, 6)
    assert kwargs["savefig"]["dpi"] == 110
    assert kwargs["title"] == "AAA — daily"
    assert "hlines" not in kwargs and "fill_between" not in kwargs, "nothing asked for"


# -------------------------------------------------------------- the holes ----


@pytest.mark.parametrize("column", [*PRICE_COLUMNS, "Volume"])
def test_a_bar_missing_one_field_is_a_gap_in_the_picture_not_no_picture(ohlcv, tmp_path, column):
    """mplfinance refuses a frame whose O, H, L and C do not share their
    missing rows; one unreadable bar in eighty-five is not a reason to show
    no picture. NaN Volume renders either way and is included so the rule is
    the one mplfinance actually has."""
    frame = ohlcv("burst").copy()
    frame.iloc[-10, frame.columns.get_loc(column)] = float("nan")
    _png(render_chart(f"H{column}", frame, str(tmp_path)))


def test_the_chart_keeps_eighty_five_readable_bars_rather_than_eighty_five_rows(ohlcv, tmp_path,
                                                                               monkeypatch):
    """The tail is taken over the READABLE bars, so a night with holes still
    shows eighty-five candles and the holes sit between them."""
    seen: dict = {}
    _plot_spy(monkeypatch, seen)
    frame = ohlcv("burst").copy()
    assert len(frame) > SESSIONS + 10, "precondition: more history than the chart shows"
    for offset in (5, 30, 70):
        frame.iloc[-offset, frame.columns.get_loc("High")] = float("nan")
    # A bar whose Volume alone the feed lost keeps its candle.
    frame.iloc[-12, frame.columns.get_loc("Volume")] = float("nan")

    render_chart("AAA", frame, str(tmp_path))

    drawn = seen["frame"].dropna(subset=list(PRICE_COLUMNS))
    assert len(drawn) == SESSIONS == 85
    assert frame.index[-12] in drawn.index
    for offset in (5, 30, 70):
        assert frame.index[-offset] in seen["index"], (
            "the session is missing from the picture rather than blank in it")
        assert seen["frame"].loc[frame.index[-offset], list(PRICE_COLUMNS)].isna().all(), (
            "a holed bar is blanked on every price column, not just the one it lost")


def test_a_hole_is_a_gap_in_the_picture_and_not_a_splice(ohlcv, tmp_path):
    """Dropping the row also satisfies mplfinance and draws the neighbours
    adjacent, so the chart of a frame with a holed bar was byte-identical to
    the chart of a frame in which that session had been DELETED. The
    inequality is the assertion, because a PNG is produced either way."""
    frame = ohlcv("burst").copy()
    hole = len(frame) - 40
    holed = frame.copy()
    holed.iloc[hole, holed.columns.get_loc("High")] = float("nan")
    spliced = frame.drop(frame.index[hole])

    gap = _png(render_chart("AAA", holed, str(tmp_path / "gap")))
    splice = _png(render_chart("AAA", spliced, str(tmp_path / "splice")))

    assert gap != splice, "the hole is drawn as a splice"


# ---------------------------------------------------------------- the cut ----


def test_through_ends_the_picture_on_the_bar_named_and_none_draws_the_whole_frame(
        ohlcv, tmp_path, monkeypatch):
    """One request, one bar: the caller names the bar the checklist graded
    and the picture ends there, however many newer bars the frame carries."""
    seen: dict = {}
    _plot_spy(monkeypatch, seen)
    frame = ohlcv("burst")

    render_chart("AAA", frame, str(tmp_path), through=len(frame) - 2)
    assert seen["index"][-1] == frame.index[-2]
    assert len(seen["frame"]) == SESSIONS, "the window still fills up behind the cut"

    render_chart("AAA", frame, str(tmp_path), through=None)
    assert seen["index"][-1] == frame.index[-1]

    render_chart("AAA", frame, str(tmp_path), through=0)
    assert list(seen["index"]) == [frame.index[0]]


# -------------------------------------------------------- the annotations ----


def _box_for(frame, first: int, last: int) -> tuple[int, int, float, float]:
    window = frame.iloc[first:last + 1]
    return (first, last, float(window["Low"].min()), float(window["High"].max()))


def test_every_annotation_is_drawn_and_none_of_them_raises(ohlcv, tmp_path):
    """Each annotation alone changes the picture, and all four together
    render: a kwarg mplfinance silently dropped would pass "does not raise"
    and fail this."""
    frame = ohlcv("burst")
    n = len(frame)
    bare = _png(render_chart("AAA", frame, str(tmp_path / "bare")))
    close = float(frame["Close"].iloc[-1])
    alone = {
        "box": dict(box=_box_for(frame, n - 25, n - 2)),
        "stop": dict(stop=close * 0.93),
        "trigger": dict(trigger=close * 1.02),
        "title": dict(title="AAA — 4% burst · stop 41.66 · trigger 45.70"),
    }
    for name, kwargs in alone.items():
        drawn = _png(render_chart("AAA", frame, str(tmp_path / name), **kwargs))
        assert drawn != bare, f"{name} was not drawn"

    everything = _png(render_chart("AAA", frame, str(tmp_path / "all"), through=n - 1,
                                   **{k: v for kw in alone.values() for k, v in kw.items()}))
    assert everything != bare


def test_the_stop_and_trigger_reach_mplfinance_as_horizontal_lines(ohlcv, tmp_path, monkeypatch):
    seen: dict = {}
    _plot_spy(monkeypatch, seen)
    render_chart("AAA", ohlcv("burst"), str(tmp_path), stop=41.5, trigger=45.25)
    lines = seen["kwargs"]["hlines"]
    assert lines["hlines"] == [41.5, 45.25]
    assert len(lines["colors"]) == 2 and lines["colors"][0] != lines["colors"][1]

    render_chart("AAA", ohlcv("burst"), str(tmp_path), trigger=45.25)
    assert seen["kwargs"]["hlines"]["hlines"] == [45.25], "one line when one price is given"

    render_chart("AAA", ohlcv("burst"), str(tmp_path), stop=float("nan"), trigger=None)
    assert "hlines" not in seen["kwargs"], "a price that cannot be read draws nothing"


def test_the_box_shades_the_named_sessions_at_the_named_prices(ohlcv, tmp_path, monkeypatch):
    """Positions are the frame's; the spec mplfinance gets is over the
    plotted window, so a box is shifted by where the window starts."""
    seen: dict = {}
    _plot_spy(monkeypatch, seen)
    frame = ohlcv("burst")
    n = len(frame)
    first, last = n - 30, n - 6

    render_chart("AAA", frame, str(tmp_path), box=(first, last, 38.5, 41.0))

    start = frame.index.get_loc(seen["index"][0])
    fill = seen["kwargs"]["fill_between"]
    assert (fill["y1"], fill["y2"]) == (38.5, 41.0)
    where = fill["where"]
    assert len(where) == len(seen["frame"])
    assert list(where.nonzero()[0]) == list(range(first - start, last - start + 1))


def test_a_box_before_the_window_is_clipped_or_left_out(ohlcv, tmp_path, monkeypatch):
    seen: dict = {}
    _plot_spy(monkeypatch, seen)
    frame = ohlcv("burst")
    n = len(frame)

    render_chart("AAA", frame, str(tmp_path), box=(0, n - 80, 38.5, 41.0))
    start = frame.index.get_loc(seen["index"][0])
    assert start > 0, "precondition: the window does not begin at the frame's first bar"
    where = seen["kwargs"]["fill_between"]["where"]
    assert where[0] and list(where.nonzero()[0]) == list(range(0, n - 80 - start + 1))

    render_chart("AAA", frame, str(tmp_path), box=(0, start - 1, 38.5, 41.0))
    assert "fill_between" not in seen["kwargs"], "wholly before the window: nothing to shade"

    render_chart("AAA", frame, str(tmp_path), box=(n - 20, n - 5, float("nan"), 41.0))
    assert "fill_between" not in seen["kwargs"], "an edge that cannot be read: nothing to shade"


def test_a_box_past_the_cut_is_clipped_to_the_last_bar_drawn(ohlcv, tmp_path, monkeypatch):
    seen: dict = {}
    _plot_spy(monkeypatch, seen)
    frame = ohlcv("burst")
    n = len(frame)

    render_chart("AAA", frame, str(tmp_path), through=n - 10, box=(n - 20, n - 1, 38.5, 41.0))

    where = seen["kwargs"]["fill_between"]["where"]
    assert where[-1], "the box runs to the last bar drawn"
    assert where.sum() == 11, "n-20 through n-10 inclusive"


def test_the_caption_is_the_title_mplfinance_prints(ohlcv, tmp_path, monkeypatch):
    seen: dict = {}
    _plot_spy(monkeypatch, seen)
    caption = "AAA — 4% burst · stop 41.66 · trigger 45.70"
    render_chart("AAA", ohlcv("burst"), str(tmp_path), title=caption)
    assert seen["kwargs"]["title"] == caption
