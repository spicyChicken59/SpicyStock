"""A multi-week history fixture, written by the REAL pipeline over a synthetic market.

    python3 tools/make_history.py tests/fixtures/history

Writes data.json and ledger.json into that directory: what docs/ would hold
after SESSIONS consecutive evening runs, with the forward returns the later
runs filled in, every streak the ledger could read back, a session Claude
was down for, a chart that would not render, and the last week's outcomes
still pending -- the states the one-night fixture from tools/make_fixture.py
cannot hold and the states a first visitor to the published page will see
once the commit-back has been running for a month.

WHY IT DRIVES THE PIPELINE INSTEAD OF WRITING ROWS
--------------------------------------------------
tools/make_fixture.py hand-authors one night and imports the real thresholds
so its pass flags cannot disagree with src/lynch.py. Thirty nights of rows
cannot be hand-authored, and a second generator that IMITATES the pipeline's
output is a second place the contract can drift -- which is how this project
already shipped a checklist whose two copies disagreed. So this runs
src.pipeline.discover() once per session, oldest first, against the same
doubles the test suite uses (tests/fakes.py): a data client that answers from
synthetic frames, a scorer that answers from a hidden quality per burst, and
no network. Every row here was written by candidate_record(), every forward
return by forward_returns(), every streak by streaks(), every mean by
mean_returns(). If the pipeline's output shape changes, this fixture changes
with it on the next regeneration, and tools/check_fixture_fresh.py fails
until it is regenerated.

WHAT IS INVENTED, AND HOW MUCH
------------------------------
The market. Each name is a seeded random walk with bursts planted on chosen
sessions; each burst carries a hidden quality q in [0, 1] that shapes three
things at once -- how quiet the week before it was, how the next five
sessions drift, and what the stand-in scorer says -- so a score and a d3/d5
return are RELATED in this fixture, noisily, and so are the checks and the
outcome. That relation is the thing the page exists to test for, and a
fixture with none in it could not exercise the views that report one. It is
not evidence of anything: run.fixture is true, the page says so above every
number, and tests/fixtures/README.md says it again. The relation is also
deliberately weak at d1 and noisy everywhere, so a page that refuses to call
a small n a result has something to refuse.

Deterministic: fixed seed, fixed session dates, the pipeline's own clock
overridden nowhere it matters (SCAN_SESSION_DATE pins each run, which also
exempts it from the mode/clock check by design), timestamps rewritten to a
constant afterwards. Regenerating twice writes identical bytes, and
tools/check_fixture_fresh.py relies on that.
"""
from __future__ import annotations

import contextlib
import json
import os
import pathlib
import struct
import sys
import tempfile
import zlib

import numpy as np
import pandas as pd

_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from src.lynch import MAX_CONSECUTIVE_UP_DAYS
from src import ledger, pipeline, scanner, scorer  # noqa: E402
from src.scorer import VERDICT_BANDS, _balanced_spans  # noqa: E402
from tests.fakes import FakeAlpaca, FakeDataClient  # noqa: E402

SEED = 20260901
#: The newest session in the fixture, and how many sessions of runs precede it.
LAST_SESSION = "2026-09-01"
SESSIONS = 30
#: Every third name in data/symbols.txt -- real symbols, as make_fixture.py
#: uses, because a fixture naming a symbol the scanner cannot see describes a
#: run this pipeline could not produce. Nothing about their histories is real.
#: 77 names: dense enough for repeats, sparse enough that one name bursts about
#: twice in six weeks rather than five times, which is what made the first
#: generation's shaping windows overlap and every forward return come out
#: positive.
UNIVERSE_STRIDE = 3
#: Sessions of price history behind the first run: src.lynch wants 67 for its
#: range norm and extra_context 126 for six-month performance, and ScanConfig
#: asks for 260.
WARMUP = 300

#: How often a planted burst is GIVEN a run of up days long enough to be
#: refused, before quality tilts it. Stated rather than inherited from the
#: walk: with nothing choosing it the rate was 33% of every planted burst and
#: cut the scored population by a quarter, which is a large fact about this
#: fixture decided by a seed. A poor setup drifts up into its burst more often
#: than a good one, so the roll is scaled by (1 - q) and this is its average.
#:
#: It is NOT the refusal rate the fixture ends up with, and saying so is the
#: point: 17 of 184 bursts are given a long run and 34 are refused, because a
#: name that bursts again two or three sessions later has a real run of up days
#: behind it -- 16 of the other 17 have another planted burst inside their own
#: run window. That is the rule doing what it is for, not the fixture leaking,
#: and it is why this constant is named for what it plants rather than for what
#: comes out. (One frame is unexplained by either, and is written down here
#: rather than rounded away.)
VETO_RATE = 0.10
GENERATED = "2026-09-01T22:14:07Z"
#: The model name written into the fixture's run block. PINNED, because
#: src.scorer reads CLAUDE_MODEL at import time and the pipeline copies that
#: name into every run -- so regenerating with CLAUDE_MODEL set produced a
#: different fixture and failed tools/check_fixture_fresh.py for the developer
#: who had it set, on a file nobody had touched. Verified by regenerating with
#: CLAUDE_MODEL=claude-opus-4-5: run.model changed. This constant existed for
#: exactly that and was never wired up.
MODEL = "claude-sonnet-4-6"

ABOUT_DATA = (
    "docs/data.json is written by src/pipeline.py at the end of every run (see "
    "src/ledger.py) and read by docs/index.html at runtime. THIS copy is a fixture: "
    "the multi-session one from tools/make_history.py, produced by running the real "
    "pipeline over a synthetic market with a stand-in scorer, so its shape is the "
    "pipeline's own and its numbers are invented. run.fixture is true, which is how "
    "the morning run refuses to mail these rows and how the page raises its sample-data "
    "banner. This block is documentation, not data; consumers ignore it."
)
ABOUT_LEDGER = (
    "docs/ledger.json is the record src/ledger.py accumulates across runs. THIS copy "
    "is a fixture from tools/make_history.py -- written by the real Ledger over a "
    "synthetic market -- and is never committed to docs/: a real run must never load "
    "invented history as its own. Ledger.load() ignores this key; the page reads it."
)

# A 1x1 PNG, so the stand-in chart renderer can put a real file where
# render_chart() would, and provenance.chart_seen is decided by the real rule
# (the file exists) rather than by a stub saying so.
def _png_1x1() -> bytes:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))
    raw = zlib.compress(b"\x00\x00\x00\x00\x00")
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


def universe() -> list[str]:
    names = []
    for line in (_ROOT / "data" / "symbols.txt").read_text().splitlines():
        sym = line.split("#")[0].strip()
        if sym:
            names.append(sym)
    return names[::UNIVERSE_STRIDE]


# ------------------------------------------------------------ the market --

class Burst:
    """One planted burst: where, how big, and the hidden quality behind it."""

    def __init__(self, ticker: str, day: int, q: float, rng: np.random.Generator) -> None:
        self.ticker, self.day, self.q = ticker, day, q
        self.gain = float(rng.uniform(4.3, 6.0) + q * rng.uniform(0, 5))       # %
        self.rvol = float(rng.uniform(1.6, 2.4) + q * rng.uniform(0, 4))
        self.close_pos = float(np.clip(0.5 + 0.5 * q + rng.normal(0, 0.15), 0.2, 0.99))
        # What the next five sessions do. Centred on the median burst so a
        # high-q burst tends to run into the 8-20% band the strategy claims
        # and a low-q one fades by as much, with enough noise that no single
        # row proves anything -- and so the population's mean is near zero,
        # which is what a page that refuses to call a small n a result has to
        # be able to show. The first generation centred lower and every
        # horizon came out positive, which no honest page could render as
        # anything but "it works".
        self.drift5 = float((q - 0.5) * 26 + rng.normal(0, 6))                 # % over 5 sessions
        self.quiet = bool(rng.random() < 0.25 + 0.6 * q)       # tight, calm week before
        self.prior_bursts = int(rng.poisson(1.6 * (1 - q)))    # earlier 4% days in the window
        self.extended = bool(rng.random() < 0.55 * (1 - q))    # already up a lot this month
        # The run of up days into the burst, CHOSEN rather than whatever the
        # walk happened to do. This is the same class the burst-frame builder
        # in tests/synthetic.py had, and the round that closed it there did not
        # sweep here: the veto's rate in this fixture was an accident of the
        # seed, and it landed at 33% of every planted burst -- a third of the
        # record refused, and the scored population cut by a quarter, decided
        # by nothing. A worse setup drifts up into its burst more often, which
        # is the relation this fixture exists to hold; VETO_RATE is what makes
        # it a stated one. Anything above MAX_CONSECUTIVE_UP_DAYS is refused.
        self.up_run = int(rng.integers(0, MAX_CONSECUTIVE_UP_DAYS + 1))
        if rng.random() < VETO_RATE * (1 - q) * 2:
            self.up_run = int(MAX_CONSECUTIVE_UP_DAYS + 1 + rng.integers(0, 3))
        self.scorer_down = False


def plan_bursts(names: list[str], rng: np.random.Generator) -> list[Burst]:
    """Which names burst on which of the SESSIONS run days, and how good each is.

    Session index 0 is the first run day; WARMUP days precede it. About five
    bursts a session on a 77-name universe -- more on the newest one, so the
    snapshot the page leads with is not two rows -- with a quarter of them
    followed by a day-2 burst and a few by a day-3, so the streak states the
    ledger computes (day 2, day 3, last seen a fortnight ago, seen and gated)
    all occur without being placed by hand.
    """
    bursts: list[Burst] = []
    busy: dict[str, int] = {}                      # ticker -> last burst day
    for day in range(SESSIONS):
        continuing = [b for b in bursts if b.day == day - 1 and rng.random() < 0.28]
        fresh_n = max(2, int(rng.poisson(4.2)))
        if day == SESSIONS - 1:
            fresh_n = max(fresh_n, 8)
        pool = [n for n in names if busy.get(n, -99) < day - 1]
        rng.shuffle(pool)
        for b in continuing:
            q = float(np.clip(b.q + rng.normal(0, 0.1), 0, 1))
            bursts.append(Burst(b.ticker, day, q, rng))
            busy[b.ticker] = day
        for name in pool[:fresh_n]:
            if busy.get(name, -99) == day:
                continue
            bursts.append(Burst(name, day, float(rng.beta(2, 2)), rng))
            busy[name] = day
    # A state the run history has to carry and one night's fixture cannot: a
    # session the scorer was down for every call. It lands on the busiest
    # session six to fourteen sessions back (SESSIONS - 15 .. SESSIONS - 6),
    # which is far enough in that its outcomes have all closed and near enough
    # that the page still shows it -- so it has gate survivors to
    # fall back on; the first generation put it on a fixed day that happened
    # to have none, and the fixture came out with a "scorer down" night nobody
    # could see. (The other such state, a chart that would not render, is
    # decided at render time -- see _patched() -- because which planted burst
    # survives the liquidity percentile is not knowable here.)
    counts = {day: sum(1 for b in bursts if b.day == day) for day in range(SESSIONS - 15, SESSIONS - 6)}
    down_day = max(counts, key=lambda day: (counts[day], -day))
    for b in bursts:
        if b.day == down_day:
            b.scorer_down = True
    return bursts


def build_frames(names: list[str], bursts: list[Burst], rng: np.random.Generator) -> dict[str, pd.DataFrame]:
    """Daily OHLCV for every name over WARMUP + SESSIONS sessions, ending LAST_SESSION."""
    total = WARMUP + SESSIONS
    index = pd.bdate_range(end=LAST_SESSION, periods=total, name="timestamp")
    by_name: dict[str, list[Burst]] = {}
    for b in bursts:
        by_name.setdefault(b.ticker, []).append(b)
    frames = {}
    for i, name in enumerate(names):
        start_price = float(rng.uniform(10, 140))
        base_volume = float(10 ** rng.uniform(6.0, 7.2))
        rets = np.clip(rng.normal(0.0004, 0.014, total), -0.035, 0.035)
        vol_noise = np.exp(np.clip(rng.normal(0, 0.25, total), -0.7, 0.9))
        wick = np.abs(rng.normal(0.012, 0.004, total))
        close_pos = np.clip(rng.normal(0.5, 0.25, total), 0.02, 0.98)
        planted = sorted(by_name.get(name, []), key=lambda b: b.day)
        # Two passes, and the order is the point. The shaping around a burst
        # (the month before, the quiet week, the five sessions after) is
        # written first for every burst; the burst days themselves are
        # written last, so a later burst's pre-window on the same name cannot
        # overwrite an earlier burst's own day. In one pass it did, and 149 of
        # 216 planted bursts reached the scanner with a 0.7% gain.
        for b in planted:
            t = WARMUP + b.day
            # The month before: an orderly advance for a good burst, chop or a
            # run-up for a poor one, so L and Y have something to separate on.
            for k in range(t - 21, t - 8):
                rets[k] = (0.004 if b.q > 0.5 else 0.0) + rng.normal(0, 0.008 if b.q > 0.5 else 0.02)
                if b.extended:
                    rets[k] += 0.008
            # Earlier 4% days inside check 2's window, for the bursts that fail it.
            for k in rng.choice(np.arange(t - 19, t - 8), size=min(b.prior_bursts, 5), replace=False):
                rets[k] = float(rng.uniform(0.042, 0.07))
            # The week before: quiet for a good burst, ordinary otherwise.
            if b.quiet:
                for k in range(t - 7, t):
                    rets[k] = rng.normal(0, 0.004)
                    vol_noise[k] *= 0.65
                    wick[k] *= 0.45
            # The prior day, calm or not (check C).
            rets[t - 1] = rng.normal(0, 0.003 if b.quiet else 0.02)
            # The five sessions after -- unless another planted burst overrides.
            steps = rng.normal(b.drift5 / 5 / 100, 0.016, 5)
            for j, k in enumerate(range(t + 1, min(t + 6, total))):
                rets[k] = steps[j]
        # THE UP-RUNS, in a pass of their own and for the same reason the burst
        # days get one. Written inside the shaping loop they were clobbered by
        # the NEXT burst's own pre-window on the same name: 19 of 184 planted
        # bursts reached the scanner with a run they were never given, and the
        # veto's rate in this fixture came out at 21.7% against an intended
        # 9.2%. The day before the run is forced down so the run stops where it
        # is meant to; 0.4%/day keeps it quiet enough that check C still calls
        # the prior session calm, which is the tired drift the rule is about.
        for b in planted:
            t = WARMUP + b.day
            anchor = t - 1 - b.up_run
            if anchor > 0:
                rets[anchor] = -0.003
                for k in range(anchor + 1, t):
                    rets[k] = 0.004
        # And the burst days LAST, because a burst one session after another
        # has that other burst's day inside its own run window, and 0.4% there
        # would erase a 5% burst.
        for b in planted:
            t = WARMUP + b.day
            rets[t] = b.gain / 100
            close_pos[t] = b.close_pos
            wick[t] = 0.004
        close = start_price * np.exp(np.cumsum(rets))
        prev_close = np.concatenate([[start_price], close[:-1]])
        volume = base_volume * vol_noise
        for b in planted:
            t = WARMUP + b.day
            avg = volume[t - 50:t].mean()
            volume[t] = max(avg * b.rvol, volume[t - 1] * 1.05)
            for j, k in enumerate(range(t + 1, min(t + 4, total))):
                volume[k] = avg * max(1.0, b.rvol * (0.7 - 0.2 * j)) * vol_noise[k]
        # An intraday envelope around each close, with the close sitting at
        # close_pos of the day's range: low <= min(open, close), high >= max.
        span = np.maximum(np.abs(close - prev_close), close * wick) * 1.3 + close * 0.002
        low = close - close_pos * span
        high = low + span
        open_ = np.clip(prev_close * (1 + rng.normal(0, 0.003, total)), low, high)
        frames[name] = pd.DataFrame({"Open": open_, "High": high, "Low": low,
                                     "Close": close, "Volume": np.round(volume)},
                                    index=index)
    return frames


# ------------------------------------------------------------ the doubles --

class DatedAlpaca(FakeAlpaca):
    """FakeAlpaca whose bars have fixed dates.

    The suite's double re-dates a registered frame so its newest bar lands on
    whatever session was asked for -- right for a test that wants "today", and
    wrong for thirty consecutive runs over one market, where a request ending
    on the 12th must return the bars up to the 12th and no others. This one
    truncates instead, which is what a live feed does.
    """

    def bars_frame(self, symbols, end=None, adjustment=None) -> pd.DataFrame:
        frames, keys = [], []
        cutoff = None if end is None else pd.Timestamp(getattr(end, "date", lambda: end)())
        for sym in symbols:
            df = self.history.get(sym)
            if df is None:
                continue
            lower = df.rename(columns=str.lower).copy()
            lower["trade_count"] = (lower["volume"] / 100.0).round()
            lower["vwap"] = (lower["high"] + lower["low"] + lower["close"]) / 3.0
            if cutoff is not None:
                lower = lower[lower.index.normalize() <= cutoff.normalize()]
            if lower.empty:
                continue
            frames.append(lower)
            keys.append(sym)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, keys=keys, names=["symbol", "timestamp"])


class _Scored:
    def __init__(self, text: str) -> None:
        self.content = [type("Block", (), {"type": "text", "text": text})()]
        self.stop_reason = "end_turn"


class QualityScorer:
    """Stands in for anthropic.Anthropic: scores from the burst's hidden quality.

    Reads the ticker and burst_date out of the METRICS block the real
    src.scorer sends, so it scores the same candidate the pipeline asked
    about; a burst it does not know (one the walk produced by chance rather
    than by plan) gets a middling score from the checklist count in the
    prompt. On the scorer-down session every call raises the way an overloaded
    API does, so that night's rows are checklist fallbacks and the run is
    degraded -- the state the email, the page and the ledger all have words for.
    """

    lookup: dict[tuple[str, str], Burst] = {}
    down_sessions: set[str] = set()
    rng: np.random.Generator = np.random.default_rng(SEED + 1)
    calls = 0

    def __init__(self, *args, **kwargs) -> None:
        self.messages = self

    def create(self, **kwargs):
        cls = type(self)
        cls.calls += 1
        text = next(block["text"] for block in kwargs["messages"][0]["content"]
                    if block.get("type") == "text")
        # The prompt holds two objects: the METRICS block and the reply
        # template. src.scorer's own brace matcher finds the first one; a
        # first-brace-to-last-brace slice spanned both and every call fell
        # back, which is how the first generation of this fixture came out
        # with 44 fallbacks and no score.
        metrics = json.loads(next(_balanced_spans(text)))
        burst = cls.lookup.get((metrics["ticker"], metrics["burst_date"]))
        if metrics["burst_date"] in cls.down_sessions:
            raise RuntimeError("Error code: 529 - overloaded_error (fixture: the scorer was down)")
        passes = int(metrics["2lynch_summary"].split("/")[0])
        q = burst.q if burst is not None else 0.45
        score = float(np.clip(1.5 + 6.5 * q + 0.35 * passes - 1.2 + cls.rng.normal(0, 0.9), 0.5, 9.9))
        score = round(score, 1)
        verdict = next((v for floor, v in VERDICT_BANDS if score >= floor), "skip")
        reasons = REASONS_GOOD if q > 0.6 else REASONS_MID if q > 0.35 else REASONS_POOR
        pick = int(cls.rng.integers(len(reasons)))
        reason, risk = reasons[pick]
        return _Scored(json.dumps({"score": score, "reason": reason, "verdict": verdict,
                                   "key_risk": risk}))


REASONS_GOOD = [
    ("First burst out of a tight base on expanding volume, closing near the high.", "earnings inside the hold window"),
    ("Clean second leg after an orderly advance; the week before was quiet and narrow.", "group already extended"),
    ("Breakout from a multi-week shelf on 3x volume with no overhead supply.", "gap risk on the open"),
]
REASONS_MID = [
    ("Decent burst but the prior advance was choppy rather than linear.", "loose base"),
    ("Volume expanded but the close gave back part of the range.", "mid-range close"),
    ("Second burst in the leg; base quality is ordinary and the move is already known.", "late in the leg"),
]
REASONS_POOR = [
    ("Third or fourth push in an extended move; this is buying exhaustion.", "extended above the 20-day"),
    ("No consolidation behind the burst and a weak close — noise, not a setup.", "no base under the move"),
    ("Sharp day on a wide, overlapping chart with no edge.", "prone to fade"),
]


# ---------------------------------------------------------------- the runs --

@contextlib.contextmanager
def _patched(alpaca: DatedAlpaca):
    """The three boundaries, replaced the way tests/conftest.py replaces them.

    The chart stub fails exactly once, on the first render the newest session
    asks for, so the snapshot the page leads with carries one chart_error and
    one row scored without its chart. Decided here rather than on a planted
    burst because two earlier attempts marked bursts the liquidity percentile
    then removed; the first candidate the pipeline renders a chart for is by
    construction one that reached scoring.
    """
    import anthropic

    saved = (scanner.StockHistoricalDataClient, anthropic.Anthropic, pipeline.render_chart,
             scorer.MODEL, pipeline.DEFAULT_MODEL)
    env = {k: os.environ.get(k) for k in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY",
                                          "ANTHROPIC_API_KEY", "SCAN_SESSION_DATE", "SCAN_FEED")}
    os.environ.update(ALPACA_API_KEY="fixture", ALPACA_SECRET_KEY="fixture",
                      ANTHROPIC_API_KEY="fixture")
    os.environ.pop("SCAN_FEED", None)

    failed_once = {"done": False}

    def chart(ticker, df, out_dir="charts"):
        session = str(pd.Timestamp(df.index[-1]).date())
        if session == LAST_SESSION and not failed_once["done"]:
            failed_once["done"] = True
            raise ValueError("fixture: mplfinance refused this frame")
        path = pathlib.Path(out_dir) / f"{ticker}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_png_1x1())
        return str(path)

    scanner.StockHistoricalDataClient = lambda *a, **k: FakeDataClient(alpaca, *a, **k)
    anthropic.Anthropic = QualityScorer
    pipeline.render_chart = chart
    # Patched, not set in the environment: scorer reads CLAUDE_MODEL at import
    # time, so an env var set here would arrive too late to change anything.
    scorer.MODEL = pipeline.DEFAULT_MODEL = MODEL
    try:
        yield
    finally:
        (scanner.StockHistoricalDataClient, anthropic.Anthropic, pipeline.render_chart,
         scorer.MODEL, pipeline.DEFAULT_MODEL) = saved
        for k, v in env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def generate(out_dir: pathlib.Path) -> dict:
    rng = np.random.default_rng(SEED)
    names = universe()
    bursts = plan_bursts(names, rng)
    frames = build_frames(names, bursts, rng)
    sessions = [d.date().isoformat() for d in
                pd.bdate_range(end=LAST_SESSION, periods=SESSIONS)]
    QualityScorer.lookup = {(b.ticker, sessions[b.day]): b for b in bursts}
    QualityScorer.down_sessions = {sessions[b.day] for b in bursts if b.scorer_down}
    QualityScorer.rng = np.random.default_rng(SEED + 1)
    QualityScorer.calls = 0

    alpaca = DatedAlpaca()
    for name, frame in frames.items():
        alpaca.add_history(name, frame)

    reports = []
    with tempfile.TemporaryDirectory() as tmp, _patched(alpaca):
        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            for session in sessions:
                os.environ["SCAN_SESSION_DATE"] = session
                report = pipeline.RunReport()
                pipeline.discover(pipeline.MODES["evening"], dry_run=True,
                                  tickers=names, report=report)
                reports.append((session, report.status, len(report.errors)))
        finally:
            os.chdir(cwd)
        data = json.loads((pathlib.Path(tmp) / "docs" / ledger.DATA_NAME).read_text())
        book = json.loads((pathlib.Path(tmp) / "docs" / ledger.LEDGER_NAME).read_text())

    # Label it. run.fixture is what the morning run and the page key on; the
    # universe label would otherwise read "--tickers, 46 named on the command
    # line", which is how the run was driven and not what a reader should
    # take from it.
    data["generated"] = GENERATED
    data["run"]["fixture"] = True
    data["run"]["universe"]["label"] = f"synthetic fixture universe ({len(names)} invented histories)"
    data["_contract"]["about"] = ABOUT_DATA
    book["generated"] = GENERATED
    book["fixture"] = True
    book["about"] = ABOUT_LEDGER

    out_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in ((ledger.DATA_NAME, data), (ledger.LEDGER_NAME, book)):
        (out_dir / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False,
                                               allow_nan=False) + "\n", encoding="utf-8")
    return {"sessions": reports, "bursts": len(bursts), "names": len(names),
            "rows": sum(len(r["candidates"]) + len(r["gated"]) for r in book["runs"]),
            "scorer_calls": QualityScorer.calls}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    out = pathlib.Path(argv[1])
    summary = generate(out)
    degraded = [s for s, status, _n in summary["sessions"] if status != "ok"]
    print(f"wrote {out / ledger.DATA_NAME} and {out / ledger.LEDGER_NAME}: "
          f"{len(summary['sessions'])} sessions over {summary['names']} names, "
          f"{summary['bursts']} planted bursts, {summary['rows']} ledger rows, "
          f"{summary['scorer_calls']} scorer calls; degraded sessions: {degraded}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
