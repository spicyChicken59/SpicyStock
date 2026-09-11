"""Generate the page fixtures by driving the REAL evening pipeline offline.

Every fixture under tests/fixtures/page/ is a docs/data.json the pipeline
itself wrote, over a synthetic market registered with the same doubles the
test suite uses (tests/fakes.py, tests/synthetic.py, the textbook frames in
tests/test_quality.py and tests/test_watchlist.py). A generator that took a
different path from the code it is a fixture FOR could only be checked
against itself; this one cannot drift from the pipeline because it is the
pipeline.

    python tools/make_fixture.py            # rewrite every fixture
    python tools/make_fixture.py --check    # exit 1 if any fixture is stale

Variants (each a night, all pinned to the same Thursday evening):
  full      four A-quality bursts: one ticket, two cut by the slot cap, one
            withheld by the stop rule at its limit (the textbook bar); a
            coiled name; three open model plans (a hold, a whole-share half
            sale holding its last share, an uncertain fill); a readable
            scorecard with uncertain fills counted      -> "Trade tomorrow."
  degraded  Claude down and a chart that would not render -> the same night,
            graded by the checklist alone, run.status degraded
  notrade   Claude lowers every grade to C                -> "Nothing qualifies."
  yellow    three names break down: the 10-day ratio
            falls under Bonde's line, A+ alone trades     -> "Trade small."
  red       six names break down: the down-4% alarm       -> "Stand aside."
  closed    no bar for the expected session               -> "Market closed."
The `full` variant's data.json is also what docs/data.json holds on a fresh
clone, so the page renders before the first real run replaces it.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src import charts, market_data, pipeline, plan, record, scans  # noqa: E402
from tests.fakes import FakeAlpaca, FakeAnthropic, FakeDataClient  # noqa: E402
from tests.synthetic import make_ohlcv  # noqa: E402
from tests.test_quality import frame as qframe, ideal_bars  # noqa: E402
from tests.test_watchlist import coil  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "page"
VARIANTS = ("full", "degraded", "notrade", "yellow", "red", "closed")
EVENING = datetime(2026, 9, 10, 22, 30, tzinfo=timezone.utc)   # Thursday, after the close
SESSION = date(2026, 9, 10)
SEED = 20260910
CLAUDE = {"A+": {"score": 9.3, "grade": "A+",
                 "reason": "A clean fifteen-session leg into a sixteen-session base that gave back under a quarter of the move, a negative narrow day, then a burst that closed at the high on three times the volume.",
                 "key_risk": "A gap over the ceiling at the open leaves no stop the bar supports.",
                 "entry_note": "Skip it if the first print is above the ceiling; a print under the skip line says the burst is failing."},
          "A": {"score": 8.4, "grade": "A",
                "reason": "The base is orderly and the burst is real, but the close sits inside the top fifth of the range rather than at the high.",
                "key_risk": "A weak open would put the entry under the burst bar's midpoint.",
                "entry_note": "Buy only inside the zone in the first thirty minutes."},
          "C": {"score": 5.2, "grade": "C",
                "reason": "The leg is there but the base is loose and the burst bar closed off its high; not the tight, linear shape the method wants.",
                "key_risk": "It reverses through the burst low.", "entry_note": "Pass."}}
BASE_NAMES = ["ANET", "CRDO", "DELL", "ELF", "FIX", "GLW", "HOOD", "IONQ", "JBL", "KTOS", "LITE", "MU", "NBIS", "ONTO", "PLTR", "QTWO", "RKLB", "SMCI", "TOST", "UBER", "VRT", "WDC", "XPEV", "ZS"]


# ---------------------------------------------------------------- market ---
#: A burst bar this many percent of its close wide keeps its midpoint inside
#: his 4% stop line at the +4% ceiling (the ticket's limit). The field guide's
#: textbook bar, with its low 4.7% under the close, does not: its ticket is
#: withheld at the limit, and TSLA below carries it to show that.
TIGHT_BAR = dict(burst_range_pct=0.25, base_range=0.15, prior_range=0.1)


def burst_frames() -> dict[str, pd.DataFrame]:
    """Four A-quality bursts -- three whose tickets qualify at their limit and
    the textbook one whose ticket is withheld -- one loose-base B, one H-only
    miss (an anticipation setup), one $-only day, and the coil."""
    return {
        "AAPL": qframe(ideal_bars(burst_gain=6.0, close_pos=0.95, burst_vol=3_000_000, **TIGHT_BAR)),
        "AMD": qframe(ideal_bars(burst_gain=5.2, close_pos=0.9, burst_vol=2_600_000, base_quiet=12, **TIGHT_BAR)),
        "NVDA": qframe(ideal_bars(burst_gain=7.4, close_pos=0.85, burst_vol=3_400_000, base_quiet=18, leg_steps=[1.4] * 14, **TIGHT_BAR)),
        "TSLA": qframe(ideal_bars(burst_gain=6.0, close_pos=0.95, burst_vol=3_000_000)),
        "PLUG": qframe(ideal_bars(burst_gain=5.0, close_pos=0.55)),
        "DLLR": dollar_only(),
        "COIL": coil(),
    }


def dollar_only() -> pd.DataFrame:
    """A quiet walk near $70 whose last session opens at the previous close and
    closes 2% up on 0.8649 of the previous session's volume: the dollar
    scan's day alone (a body over $0.90, no 4% burst), with a volume ratio
    under 1 that is a measurement and not a hole -- RVTY's shape on the first
    real night, a $1.91 body, +2.8%, on 0.86x the previous session. Four
    places in the row, two in the checklist's block, as the real record has."""
    df = make_ohlcv("base", seed=[SEED, 501], days=280, start_price=60.0)
    prev_close, prev_volume = float(df["Close"].iloc[-2]), float(df["Volume"].iloc[-2])
    o, c = round(prev_close, 2), round(prev_close * 1.02, 2)
    assert c / prev_close < scans.BURST_RATIO and c - o >= scans.DOLLAR_MOVE, (prev_close, c)
    df.iloc[-1, df.columns.get_loc("Open")] = o
    df.iloc[-1, df.columns.get_loc("High")] = round(c + 1.2, 2)
    df.iloc[-1, df.columns.get_loc("Low")] = round(o - 0.3, 2)
    df.iloc[-1, df.columns.get_loc("Close")] = c
    df.iloc[-1, df.columns.get_loc("Volume")] = round(prev_volume * 0.8649)
    return df


def base_frames() -> dict[str, pd.DataFrame]:
    """The quiet names: random walks, each with one 4% breakdown day and one
    4% up day somewhere in its last forty sessions, so the Market Monitor's
    ratios have a denominator and a history worth a chart."""
    frames = {}
    for i, name in enumerate(BASE_NAMES):
        # VRT trades near $200 so its model plan is three shares: the
        # whole-share half sale (2 of 3) shows on the page
        df = make_ohlcv("base", seed=[SEED, i], days=280, start_price=200.0 if name == "VRT" else 25.0)
        big_day(df, -(3 + (i * 7) % 37), 0.955)
        big_day(df, -(2 + (i * 11) % 39), 1.045)
        frames[name] = df
    return frames


def big_day(df: pd.DataFrame, pos: int, ratio: float) -> None:
    """Rewrite the bar at ``pos`` as a ``ratio`` move off the previous close on
    double volume, inside a bar that contains it."""
    prev = float(df["Close"].iloc[pos - 1])
    close = round(prev * ratio, 2)
    lo, hi = min(prev, close), max(prev, close)
    df.iloc[pos, df.columns.get_loc("Open")] = round(prev * (0.995 if ratio < 1 else 1.005), 2)
    df.iloc[pos, df.columns.get_loc("High")] = round(hi * 1.004, 2)
    df.iloc[pos, df.columns.get_loc("Low")] = round(lo * 0.996, 2)
    df.iloc[pos, df.columns.get_loc("Close")] = close
    df.iloc[pos, df.columns.get_loc("Volume")] = float(df["Volume"].iloc[pos - 1]) * 2


def red_tape(frames: dict[str, pd.DataFrame], names: int) -> None:
    """``names`` of the quiet names close 5% down on double volume. Three
    drag the 10-session ratio under the yellow line for a universe this
    size; six pass the scaled down-4% alarm."""
    for name in BASE_NAMES[:names]:
        df = frames[name]
        prev = float(df["Close"].iloc[-2])
        close = round(prev * 0.95, 2)
        df.iloc[-1, df.columns.get_loc("Open")] = round(prev * 0.99, 2)
        df.iloc[-1, df.columns.get_loc("High")] = round(prev * 0.995, 2)
        df.iloc[-1, df.columns.get_loc("Low")] = round(close * 0.995, 2)
        df.iloc[-1, df.columns.get_loc("Close")] = close
        df.iloc[-1, df.columns.get_loc("Volume")] = float(df["Volume"].iloc[-2]) * 2


def hold_tape(frames: dict[str, pd.DataFrame]) -> None:
    """The three open-plan tapes, each written so the walk reads one thing.
    NBIS rises gently over its last six sessions: every open at or over the
    pick's close (a known fill at the open), every low above the stop, and
    nothing near +8%: a hold. VRT (three shares) reaches +9% on its first
    session after the pick, so the model sells 2 of 3 at +8% and raises the
    stop under that high; the days after open and hold above it and close
    under +10%: the last share is held into strength. SMCI opens under its
    pick's close and reaches it later in the day: a fill the bars cannot
    time, uncertain."""
    for name in ("NBIS", "VRT", "SMCI"):
        df = frames[name]
        start = float(df["Close"].iloc[-7])
        for k, pos in enumerate(range(-6, 0), 1):
            close = round(start * (1 + 0.006 * k), 2)
            df.iloc[pos, df.columns.get_loc("Open")] = round(close * 0.997, 2)
            df.iloc[pos, df.columns.get_loc("High")] = round(close * 1.008, 2)
            df.iloc[pos, df.columns.get_loc("Low")] = round(close * 0.99, 2)
            df.iloc[pos, df.columns.get_loc("Close")] = close

    def write(df: pd.DataFrame, pos: int, o: float, h: float, l: float, c: float) -> None:
        for col, value in (("Open", o), ("High", h), ("Low", l), ("Close", c)):
            df.iloc[pos, df.columns.get_loc(col)] = round(value, 2)

    # VRT: picked four sessions back (position -5). The whole frame is scaled
    # so that close is 180 (no invented jump inside the breadth window) and
    # the pick-day bar is pinned around it, so the plan is three shares:
    # $25 (halved) over the $7.49 between the 187.20 limit and its 4% line.
    # Its first session after the pick opens at the close and runs +9%.
    vrt = frames["VRT"]
    scale = 180.0 / float(vrt["Close"].iloc[-5])
    for col in ("Open", "High", "Low", "Close"):
        vrt[col] = (vrt[col] * scale).round(2)
    write(vrt, -5, 177.0, 181.0, 176.5, 180.0)
    picked = float(vrt["Close"].iloc[-5])
    high = round(picked * 1.09, 2)
    write(vrt, -4, picked, high, picked * 0.998, picked * 1.07)
    level = high
    for pos in (-3, -2, -1):
        write(vrt, pos, level + 0.30, level + 0.90, level + 0.10, level + 0.60)
        level += 0.60
    # SMCI: picked three sessions back (position -4); its first session after
    # opens 0.5% under the close and reaches +1% at a time the bar cannot give
    smci = frames["SMCI"]
    picked = float(smci["Close"].iloc[-4])
    write(smci, -3, picked * 0.995, picked * 1.01, picked * 0.99, picked * 1.004)
    for pos in (-2, -1):
        write(smci, pos, picked * 1.004, picked * 1.012, picked * 0.998, picked * 1.006)


def register(fake: FakeAlpaca, variant: str) -> list[str]:
    frames = {**burst_frames(), **base_frames()}
    hold_tape(frames)
    if variant == "yellow":
        red_tape(frames, 3)
    elif variant == "red":
        red_tape(frames, 6)
    for name, df in frames.items():
        fake.add_history(name, df)
    fake.add_history("SPY", make_ohlcv("base", seed=[SEED, 999], days=280, start_price=560.0))
    if variant == "closed":
        fake.close_session(SESSION)
    return list(frames)


# ---------------------------------------------------------------- picks ----
def prior_picks(fake: FakeAlpaca) -> dict:
    """A picks.json the night inherits: three picks from the last five
    sessions (the open model plans: a hold, the whole-share half sale, an
    uncertain fill) and one a session for the forty-four before those (a
    readable scorecard, uncertain fills among them), each priced off the
    frame it names as the double will serve it. The stop is the pick day's
    low or 4% under the close, whichever is lower, and the recorded ticket's
    sell leg carries that same stop."""
    sessions = pd.bdate_range(end=SESSION, periods=60)
    picks = []

    def pick(name: str, back: int, kind: str = "burst") -> dict:
        df = fake.history[name]
        pos = len(df) - 1 - back
        close = round(float(df["Close"].iloc[pos]), 2)
        low = round(float(df["Low"].iloc[pos]), 2)
        stop = round(min(low, close * 0.96), 2)
        account = plan.Account()
        p = plan.burst_plan(ticker=name, close=close, low=low, high=round(float(df["High"].iloc[pos]), 2),
                            open_=round(float(df["Open"].iloc[pos]), 2), prev_close=round(close / 1.05, 2),
                            gain_pct=5.0, account=account, size_multiplier=1.0, scan="4pct", extension_pct=None)
        row = pipeline.pick_of(p, kind, "A", 8.5)
        row["stop"] = stop
        if p["shares"] > 0:
            row["order_json"] = plan.fidelity_orders(name, p["shares"], trigger=close, limit=p["entry_high"], stop=stop,
                                                     skip_below=p["entry_low"])["order_json"]
        return {**row, "date": sessions[-1 - back].date().isoformat(), "regime": "green"}

    picks.append(pick("NBIS", 2))
    picks.append(pick("SMCI", 3))
    picks.append(pick("VRT", 4))
    for i, back in enumerate(range(6, 50)):
        picks.append(pick(BASE_NAMES[i % len(BASE_NAMES)], back))
    picks.sort(key=lambda p: (p["date"], p["ticker"]))
    return {"schema_version": record.SCHEMA_VERSION, "picks": picks}


# ------------------------------------------------------------------ run ----
def run_variant(variant: str, docs: Path) -> dict:
    fake = FakeAlpaca()
    tickers = register(fake, variant)
    docs.mkdir(parents=True, exist_ok=True)
    record.save(prior_picks(fake), docs)
    claude = type("FixtureClaude", (FakeAnthropic,), {"calls": [], "payload": {}, "raw": None, "raises": None})

    def answer(metrics: dict) -> dict:
        grade = metrics.get("quality_grade")
        if variant == "notrade":
            return CLAUDE["C"]
        return CLAUDE.get(grade, CLAUDE["C"])

    class Messages:
        def __init__(self, owner):
            self.owner = owner

        def create(self, **kwargs):
            from tests.fakes import FakeMessage, FakeTextBlock, billed_usage
            self.owner.calls.append(kwargs)
            if self.owner.raises is not None:
                raise self.owner.raises
            text = json.dumps(answer(_metrics_of(kwargs)))
            return FakeMessage(content=[FakeTextBlock(text=text)],
                               usage=billed_usage(kwargs, self.owner.calls, self.owner.uncached_tokens))

    def make_client(*a, **k):
        inst = claude(*a, **k)
        inst.messages = Messages(claude)
        return inst

    if variant == "degraded":
        claude.raises = RuntimeError("upstream connect error")
    real_render = charts.render_chart

    def render(ticker, df, out_dir, **kw):
        if variant == "degraded" and ticker == "AMD":
            raise RuntimeError("the renderer refused the frame")
        return real_render(ticker, df, out_dir, **kw)

    env = {"ALPACA_API_KEY": "fixture", "ALPACA_SECRET_KEY": "fixture", "ANTHROPIC_API_KEY": "fixture",
           "SCAN_SEND_EMAIL": "false", "MPLBACKEND": "Agg", "CLAUDE_MODEL": "claude-sonnet-4-6"}
    with mock.patch.dict(os.environ, env), \
            mock.patch.object(market_data, "StockHistoricalDataClient", lambda *a, **k: FakeDataClient(fake, *a, **k)), \
            mock.patch("anthropic.Anthropic", make_client), \
            mock.patch.object(charts, "render_chart", render), \
            mock.patch.object(pipeline.grader, "MODEL", "claude-sonnet-4-6"):
        rep = pipeline.run_evening(tickers=tickers, docs=docs, now=EVENING)
    if not rep.published:
        raise SystemExit(f"{variant}: the pipeline did not publish ({rep.failure})")
    data = json.loads((docs / pipeline.DATA_FILE).read_text())
    data["fixture"] = variant
    # two runs of this generator must be byte-identical: the wall clock is
    # not a fact about the market
    data["run"]["elapsed_seconds"] = 0.0
    data["run"]["fetch_seconds"] = 0.0
    return data


def _metrics_of(kwargs: dict) -> dict:
    """The metrics block back out of the request's user text: the JSON
    between the METRICS heading and the reply-shape paragraph."""
    for msg in kwargs.get("messages", []):
        for block in msg.get("content", []):
            if block.get("type") == "text" and "METRICS:\n" in block["text"]:
                text = block["text"].split("METRICS:\n", 1)[1]
                text = text.split("\n\nRespond", 1)[0]
                try:
                    return json.loads(text)
                except ValueError:
                    continue
    return {}


def expected_shape(variant: str, data: dict) -> None:
    """What each variant exists to show; a generator that no longer produces
    it fails here rather than shipping a fixture that shows nothing."""
    h1 = data["cover"]["h1"]
    problems = [p["kind"] for p in data["run"]["problems"]]
    if variant == "full":
        assert h1.startswith("Trade tomorrow."), h1
        assert len(data["trades"]) >= 1 and data["beyond_cap"], (data["trades"], data["beyond_cap"])
        kinds = {c["ticker"]: c["kind"] for c in data["cash_budget"]["cut"]}
        assert "withheld" in kinds.values() and "slot_cap" in kinds.values(), kinds
        assert kinds.get("TSLA") == "withheld", kinds
        assert data["scorecard"]["readable"] and data["scorecard"]["uncertain"] > 0, data["scorecard"]
        statuses = {p["ticker"]: p["status"] for p in data["open_plans"]}
        assert statuses == {"NBIS": "hold", "SMCI": record.UNCERTAIN, "VRT": "sell_into_strength"}, statuses
        vrt = next(p for p in data["open_plans"] if p["ticker"] == "VRT")
        assert vrt["shares"] == 3 and vrt["sold"] == 2 and vrt["remaining"] == 1, (vrt["shares"], vrt["sold"], vrt["remaining"])
        assert data["watchlist"]["top"], "no coiled name"
        dollar = [b for b in data["bursts"] if b["scan"] == "dollar"]
        assert dollar and all(isinstance(b["volume_vs_prior"], float) and 0 < b["volume_vs_prior"] < 1 for b in dollar), \
            [(b["ticker"], b.get("volume_vs_prior")) for b in dollar]
        assert problems == []
    elif variant == "degraded":
        assert set(problems) == {"claude_unavailable", "chart_missing"}, problems
        assert data["run"]["status"] == "degraded"
    elif variant == "notrade":
        assert h1 == "Nothing qualifies. Keep cash." and data["closest_miss"], h1
    elif variant == "yellow":
        assert h1.startswith("Trade small.") and data["breadth"]["regime"]["verdict"] == "yellow", h1
        graded = {b["ticker"]: b["grade"] for b in data["bursts"]}
        assert all(graded[t] == "A+" for t in data["trades"]), graded
    elif variant == "red":
        assert h1 == "Stand aside." and data["breadth"]["regime"]["verdict"] == "red", h1
    elif variant == "closed":
        assert h1 == "Market closed. Plans unchanged." and data["run"]["session_state"] == "closed", h1


def build_all() -> dict[str, dict]:
    out = {}
    for variant in VARIANTS:
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs"
            data = run_variant(variant, docs)
            expected_shape(variant, data)
            out[variant] = data
            if variant == "full":
                out["full-picks"] = {"fixture": "full", **json.loads((docs / record.PICKS_FILE).read_text())}
    return out


def write(name: str, data: dict, target: Path) -> str:
    text = json.dumps(data, indent=1, ensure_ascii=False, allow_nan=False) + "\n"
    target.write_text(text)
    return text


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--check", action="store_true", help="compare rather than write; exit 1 on a difference")
    args = p.parse_args(argv)
    built = build_all()
    FIXTURES.mkdir(parents=True, exist_ok=True)
    stale = []
    for name, data in built.items():
        target = FIXTURES / f"{name}.json"
        text = json.dumps(data, indent=1, ensure_ascii=False, allow_nan=False) + "\n"
        if args.check:
            if not target.exists() or target.read_text() != text:
                stale.append(target.name)
        else:
            target.write_text(text)
    # docs/ on a fresh clone: the full fixture and its picks, both marked, so
    # the page renders before the first real night and the first real night
    # inherits neither the invented nights nor the invented picks.
    placeholders = {ROOT / "docs" / pipeline.DATA_FILE: built["full"], ROOT / "docs" / record.PICKS_FILE: built["full-picks"]}
    if args.check:
        for target, data in placeholders.items():
            text = json.dumps(data, indent=1, ensure_ascii=False, allow_nan=False) + "\n"
            if not target.exists() or (json.loads(target.read_text()).get("fixture") == "full" and target.read_text() != text):
                stale.append(f"docs/{target.name}")
        if stale:
            print("stale fixtures: " + ", ".join(stale) + " -- run python tools/make_fixture.py")
            return 1
        print(f"{len(built)} fixtures current")
        return 0
    for target, data in placeholders.items():
        current = json.loads(target.read_text()) if target.exists() else {}
        if not target.exists() or current.get("fixture") == "full" or current.get("schema_version") != data.get("schema_version"):
            target.write_text(json.dumps(data, indent=1, ensure_ascii=False, allow_nan=False) + "\n")
            print(f"docs/{target.name} <- the full fixture (it still claimed to be one, or was not this schema)")
    for name in list(built):
        print(f"wrote tests/fixtures/page/{name}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
