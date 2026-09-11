"""Annotated candlestick PNGs for Claude's eyes and the page.

Eighty-five READABLE daily sessions of candles, volume and three moving
averages, ending on the bar the caller names; a bar missing a price is
blanked and kept, so a hole is a gap in the picture rather than a splice.
On top, optionally: a shaded consolidation box, a stop line, a trigger line
and a caption.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

#: Sessions a reader can read, counted over the readable bars so a night with
#: holes still shows this many candles and the holes sit between them.
SESSIONS = 85
MOVING_AVERAGES = (10, 20, 50)
#: A bar missing any of these is blanked. Volume is deliberately not among
#: them: a NaN there renders, and the volume panel is the half a reader can
#: still read across a hole.
PRICE_COLUMNS = ("Open", "High", "Low", "Close")
STYLE = "yahoo"
FIGSIZE = (10, 6)
DPI = 110

STOP_COLOR = "#d62828"
TRIGGER_COLOR = "#2a9d8f"
BOX_COLOR = "#457b9d"
BOX_ALPHA = 0.18


def render_chart(ticker: str, df: pd.DataFrame, out_dir: str = "charts", *,
                 through: int | None = None,
                 box: tuple[int, int, float, float] | None = None,
                 stop: float | None = None, trigger: float | None = None,
                 title: str | None = None) -> str:
    """Render `df`'s last SESSIONS readable bars to `<out_dir>/<ticker>.png`.

    `through` is the position in `df` of the last bar drawn -- the bar the
    checklist graded and the metrics describe -- or None for the whole frame.
    `box` is `(first, last, low, high)`: positions in `df`, inclusive, and
    the price span to shade; a box outside the picture is not drawn and one
    straddling its left edge is clipped. `stop` and `trigger` are prices
    drawn as horizontal lines. `title` is the caption; the default names
    the ticker.

    A bar missing one of PRICE_COLUMNS is BLANKED rather than dropped. Both
    satisfy mplfinance's equal-missing rule; only blanking leaves a slot for
    the session, and the picture of a session that happened and could not
    be read must differ from the picture of one that never happened.
    """
    import mplfinance as mpf

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = str(Path(out_dir) / f"{ticker}.png")
    frame = df if through is None else df.iloc[:through + 1]
    price = [c for c in PRICE_COLUMNS if c in frame.columns]
    readable = (frame[price].notna().all(axis=1).to_numpy() if price
                else np.zeros(len(frame), dtype=bool))
    drawn = np.flatnonzero(readable)[-SESSIONS:]
    start = int(drawn[0]) if len(drawn) else 0
    plot_df = frame.iloc[start:].copy()
    blank = np.flatnonzero(~readable[start:])
    if len(blank) and price:
        plot_df.iloc[blank, [plot_df.columns.get_loc(c) for c in price]] = float("nan")
    plot_df.index = pd.to_datetime(plot_df.index)

    kwargs: dict = dict(
        type="candle",
        volume=True,
        mav=MOVING_AVERAGES,
        style=STYLE,
        title=title if title is not None else f"{ticker} — daily",
        savefig=dict(fname=path, dpi=DPI, bbox_inches="tight"),
        figsize=FIGSIZE,
    )
    lines = _hlines(stop, trigger)
    if lines:
        kwargs["hlines"] = lines
    shade = _box(box, start, len(plot_df))
    if shade:
        kwargs["fill_between"] = shade
    mpf.plot(plot_df, **kwargs)
    return path


def _finite(value) -> bool:
    try:
        return value is not None and bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _hlines(stop, trigger) -> dict | None:
    """mplfinance's `hlines` spec for whichever of the two prices is given."""
    prices, colors = [], []
    for value, color in ((stop, STOP_COLOR), (trigger, TRIGGER_COLOR)):
        if _finite(value):
            prices.append(float(value))
            colors.append(color)
    if not prices:
        return None
    return dict(hlines=prices, colors=colors, linestyle="--", linewidths=1.0)


def _box(box, start: int, n: int) -> dict | None:
    """mplfinance's `fill_between` spec for the consolidation box, over the
    `n` plotted positions that begin at `start` in the frame, or None when
    the box lies outside the picture or has no readable edge."""
    if box is None:
        return None
    first, last, low, high = box
    if not (_finite(low) and _finite(high)):
        return None
    lo, hi = max(int(first) - start, 0), min(int(last) - start, n - 1)
    if lo > hi:
        return None
    where = np.zeros(n, dtype=bool)
    where[lo:hi + 1] = True
    return dict(y1=float(low), y2=float(high), where=where,
                color=BOX_COLOR, alpha=BOX_ALPHA, linewidth=0)
