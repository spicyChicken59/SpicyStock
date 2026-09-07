"""Hand-authored fixture: the canonical copy is tests/fixtures/data.json.

    python3 tools/make_fixture.py tests/fixtures/data.json

docs/data.json was seeded from that file so a repo that has never published
still renders a page, and it stays a copy of it only until evening.yml commits
a real run back -- which in this repo happened on 6 Sep 2026, so docs/data.json
is a run now and this fixture lives on where tools/check_fixture_fresh.py and
tools/dashboard_smoke.mjs read it. Do not regenerate straight into docs/ over a
real run.

Every 2LYNCH pass flag is COMPUTED from its measurement using the same
thresholds src/lynch.py applies, and every fallback score is computed with
src/scorer.py's own formula, so the fixture cannot disagree with the code it
stands in for.
"""
import collections, json, pathlib, sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
from src.pipeline import MIN_LYNCH_PASSES
from src.scorer import _fallback_score
from src import ledger                        # the real evidence block, not a copy
from src.ledger import CONTRACT_INVARIANTS    # the real contract, not a copy
from src.scanner import ScanConfig            # the real floors, not a copy
from src.lynch import (                       # the real thresholds, not a copy
    MAX_PRIOR_BURSTS, MIN_LINEAR_R2, MIN_LINEAR_SLOPE, MAX_RUN_UP_1MO,
    MAX_EXT_VS_SMA20, MAX_TIGHTNESS, MAX_D1_MOVE, MAX_D1_VOL_RATIO,
    MAX_D1_RANGE_RATIO, MIN_CLOSE_POS, PRIOR_BURST_PCT,
    MAX_CONSECUTIVE_UP_DAYS, BREAKDOWN_PCT, BREAKDOWN_LOOKBACK,
    WINDOWS,                                  # and the windows its lines print
)
from src.pipeline import VETO_REASONS, rules_fingerprint, scan_coverage, stopped_printing
_CFG = ScanConfig()

def _universe():
    """The symbols the scanner can actually see. A fixture naming anything else
    describes a run this pipeline cannot produce."""
    out = []
    for line in (_ROOT / "data" / "symbols.txt").read_text().splitlines():
        sym = line.split("#")[0].strip()
        if sym:
            out.append(sym)
    return out

UNIVERSE = _universe()

def _remap(specs, start):
    """Rebind each row to a real symbol, keeping row order so the deliberate
    states (the fallback at rank 2, the chart-less score) stay where they are.
    Also lift any price or volume that would not survive detect_setup."""
    out = []
    for i, spec in enumerate(specs):
        sym = UNIVERSE[(start + i) % len(UNIVERSE)]
        d = spec._asdict()
        d["t"] = sym
        if d["close"] <= _CFG.min_price:
            d["close"] = round(_CFG.min_price + 1.25 + (i % 7) * 0.9, 2)
        # Lift thin rows to a volume that clears the relative gate against a
        # plausible trailing average. detect_setup no longer applies an
        # absolute share floor; this is only to keep the fixture realistic.
        # Except the rows rule 6 refused, whose whole point is to be thin:
        # lifting them put a $92M/day row under a $12.4M floor, and the
        # assertion in build_gated() is what caught it.
        if d["vol"] <= 5_000_000 and d.get("reason") != ledger.LIQUIDITY_REASON:
            d["vol"] = 5_000_000 + 1_200_000 + i * 137_000
        if d["prev"] >= d["vol"]:
            d["prev"] = int(d["vol"] * 0.42)
        out.append(type(spec)(**d))
    return out


SESSION = "2026-09-01"
MODEL = "claude-sonnet-4-6"


#: The record every streak below was read out of: the seven sessions in `runs`
#: that precede SESSION, the oldest of them 2026-08-21. The same pair on every
#: row, because it describes the FILE and not the name -- and one session
#: shorter than `runs`, because a run's streaks are computed before that run is
#: added to the history they were computed from.
SPAN = {"history_from": "2026-08-21", "history_sessions": 7}


def streak(i):
    """Step 10's streak block, hand-authored and consistent with `runs` below.

    Keyed on the row's POSITION so the file regenerates byte-identically, and
    written to exercise the states a reader has to be able to tell apart:

      day 3     a setup that has been running for three sessions
      day 2     one that started yesterday, after a burst the CHECKLIST threw
                out -- last_outcome says which, because "not scored then" read
                as an absence of judgement over a rejection
      unknown   a chain reaching back to near the oldest run this file holds,
                where nothing before it was ever scanned: day 3 and day 13 are
                both possible and the record cannot say which. It is not silent
                about that any more -- history_from and history_sessions say
                what the unknown is unknown over, so the page can print "burst
                on 2 of the 7 sessions in the record, which begins 2026-08-21,
                and may have started before it". last_outcome is score_cap
                there -- it passed and better names took the night's calls,
                which is a different sentence from lynch_gate
      day 1     a name last seen a fortnight ago, which is day 1 of something
                new rather than day 13 of something old; and a name nothing
                has ever carried

    src/ledger.py's MAX_STREAK_GAP_SESSIONS and _why_no_day() hold the rules;
    these rows only have to obey them, and now they can be CHECKED against them
    from the file alone, which is what carrying the record in the block bought:

      a day number needs the record to begin MAX_STREAK_GAP_SESSIONS sessions
      before the setup did. 2026-08-21 is five sessions before the day-3 row's
      2026-08-28 and seven before the day-2 row's 2026-08-31.
      the unknown row must NOT have that reach: its chain starts 2026-08-25,
      two sessions after the record does, which is why it is unknown.
      every last_seen has to be a session the record holds. The day-1 row's
      was 2026-08-17 against a file beginning 2026-08-25 -- a sighting on a
      night that was never scanned, in a fixture nothing could check.
    """
    if i % 7 == 1:
        return {"day": 3, "unknown_reason": None, "first_seen": "2026-08-28",
                "last_seen": "2026-08-31", "last_score": 7.4, "last_verdict": "B",
                "last_outcome": "scored", "seen_before": 2, **SPAN}
    if i % 7 == 2:
        return {"day": None, "unknown_reason": "window_not_covered",
                "first_seen": None, "last_seen": "2026-08-31", "last_score": None,
                "last_verdict": None, "last_outcome": "score_cap", "seen_before": 2,
                **SPAN}
    if i % 7 == 3:
        return {"day": 2, "unknown_reason": None, "first_seen": "2026-08-31",
                "last_seen": "2026-08-31", "last_score": None, "last_verdict": None,
                "last_outcome": "lynch_gate", "seen_before": 1, **SPAN}
    if i % 7 == 5:
        return {"day": 1, "unknown_reason": None, "first_seen": SESSION,
                "last_seen": "2026-08-21", "last_score": 5.2, "last_verdict": "skip",
                "last_outcome": "scored", "seen_before": 1, **SPAN}
    return {"day": 1, "unknown_reason": None, "first_seen": SESSION,
            "last_seen": None, "last_score": None, "last_verdict": None,
            "last_outcome": None, "seen_before": 0, **SPAN}

LABELS = {
    "2": "first or second burst",
    "L": "linear prior move",
    "Y": "young trend",
    "N": "narrow consolidation",
    "C": "calm pre-burst day",
    "H": "closed near the high",
}

def lynch(prior_bursts, r2, run_up, ext, recent_range, tightness, d1_move, d1_range, d1_vol, close_pos, gain=0.0):
    """The same rules src/lynch.py applies, over hand-authored measurements.

    The thresholds are IMPORTED from src.lynch, not copied, so a numeric drift
    is impossible. This function once held its own copies and silently fell
    behind the step-7 fixes, so the dashboard reported pass rates the real
    checklist would never produce. tests/test_lynch.py pins the predicates.
    """
    # Everything src/lynch.py needs that this spec did not carry is DERIVED here
    # rather than added to 47 hand-written rows:
    #   L's slope   -- run_up is the prior month's move, so its sign is the
    #                  fitted trend's sign.
    #   Y's values  -- src measures through the burst day; the spec's run_up and
    #                  ext are pre-burst, so compound in the row's own gain.
    #   C's ratio   -- norm_range = recent_range / tightness, by N's definition.
    fitted = run_up
    run_up_through = ((1 + run_up / 100) * (1 + gain / 100) - 1) * 100
    ext_through = ((1 + ext / 100) * (1 + gain / 100) - 1) * 100
    norm_range = (recent_range / tightness) if tightness else 0.0
    d1_range_ratio = (d1_range / norm_range) if norm_range else 0.0
    return [
        {"code": "2", "label": LABELS["2"], "pass": prior_bursts <= MAX_PRIOR_BURSTS,
         "value": (f"{prior_bursts} prior {PRIOR_BURST_PCT:g}% bursts in last "
                   f"{WINDOWS['prior_burst_lookback']} days")},
        {"code": "L", "label": LABELS["L"],
         "pass": r2 >= MIN_LINEAR_R2 and fitted >= MIN_LINEAR_SLOPE,
         "value": (f"R²={r2:.2f}, fitted trend {fitted:+.1f}% over prior "
                   f"{WINDOWS['linear_fit_sessions']} days")},
        {"code": "Y", "label": LABELS["Y"],
         "pass": run_up_through < MAX_RUN_UP_1MO and ext_through < MAX_EXT_VS_SMA20,
         "value": (f"{run_up_through:+.1f}% past month, {ext_through:+.1f}% vs "
                   f"{WINDOWS['sma_sessions']}SMA (through today's burst)")},
        {"code": "N", "label": LABELS["N"], "pass": tightness <= MAX_TIGHTNESS,
         "value": f"pre-burst range {recent_range:.1f}%/day = {tightness:.2f}x its norm"},
        {"code": "C", "label": LABELS["C"],
         "pass": d1_move < MAX_D1_MOVE and d1_vol < MAX_D1_VOL_RATIO and d1_range_ratio <= MAX_D1_RANGE_RATIO,
         "value": f"prior day {d1_move:.1f}% move, {d1_range:.1f}% range = {d1_range_ratio:.2f}x its norm, {d1_vol:.2f}x volume"},
        {"code": "H", "label": LABELS["H"], "pass": close_pos >= MIN_CLOSE_POS,
         "value": f"closed at {close_pos:.0%} of day's range"},
    ]

# ticker, close, gain%, volume, prev_volume, verdict, reason, key_risk, source, chart_ok,
#   lynch measurements, context (off52wHigh, above52wLow, perf3m, perf6m), claude score
C = collections.namedtuple("C", "t close gain vol prev score verdict reason risk src chart lm ctx")

SPEC = [
    C("AEHR", 23.87, 8.42, 6142300, 1974500, 8.7, "A",
      "Second burst out of a five-week base on 3x volume, closing at the high with no overhead supply.",
      "earnings in 9 sessions", "claude", True,
      (1, 0.81, 14.2, 6.4, 3.1, 0.72, 0.8, 2.2, 0.91, 0.94),
      (-4.2, 168.3, 61.4, 88.9)),
    C("NVTS", 7.41, 6.18, 18420100, 7106400, None, None, None, None, "fallback", True,
      (2, 0.68, 11.9, 4.8, 2.9, 0.83, 1.1, 2.6, 1.04, 0.88),
      (-11.7, 94.2, 38.6, 21.4)),
    C("RGTI", 31.06, 9.94, 41883700, 15992000, 8.1, "A",
      "First burst off a tight three-week shelf, volume 2.6x prior day, but the group is already extended.",
      "sector-wide unwind risk", "claude", True,
      (1, 0.74, 26.4, 9.1, 4.4, 0.88, 1.6, 3.4, 1.11, 0.86),
      (-8.9, 412.7, 96.3, 174.2)),
    C("IONQ", 48.22, 5.31, 22140600, 9832100, 7.6, "B+",
      "Clean second burst on a linear advance; close near the high but the prior day was heavy.",
      "prior day already ran on volume", "claude", True,
      (1, 0.79, 21.4, 11.2, 3.8, 0.94, 2.3, 4.1, 1.38, 0.82),
      (-14.1, 233.8, 44.7, 61.9)),
    C("SEZL", 92.44, 7.08, 1204800, 486300, 7.4, "B+",
      "Tight consolidation broke on good volume, but the prior advance was choppy rather than linear.",
      "liquidity thinner than the tape suggests", "claude", False,
      (2, 0.41, 16.3, 8.7, 2.6, 0.79, 0.9, 2.1, 0.98, 0.89),
      (-6.3, 287.4, 52.1, 118.6)),
    C("AMSC", 41.18, 4.62, 3287400, 1442900, 7.1, "B+",
      "Third burst in the leg, which is late, but the base is narrow and the close is strong.",
      "third burst — trend no longer young", "claude", True,
      (2, 0.77, 19.8, 12.4, 3.3, 0.86, 1.2, 2.8, 1.07, 0.91),
      (-3.1, 141.6, 33.9, 57.2)),
    C("LUNR", 14.73, 6.87, 12994100, 5218700, None, None, None, None, "fallback", True,
      (1, 0.48, 27.4, 13.1, 4.1, 0.91, 1.4, 3.2, 1.09, 0.78),
      (-22.4, 118.9, 29.7, 12.8)),
    C("CIFR", 9.62, 11.34, 34118200, 12440300, 6.6, "B",
      "Big burst but it comes after a 34% month, so the trend is no longer young and risk is stretched.",
      "extended above the 20-day", "claude", True,
      (1, 0.71, 34.2, 18.9, 4.8, 0.93, 1.8, 3.9, 1.16, 0.84),
      (-18.6, 203.1, 71.4, 44.3)),
    C("HIMS", 58.91, 4.88, 9847200, 4103800, 6.4, "B",
      "Orderly base and a good close, but this is the fourth burst in the leg and volume only doubled.",
      "fourth burst in the leg", "claude", True,
      (3, 0.83, 12.7, 5.9, 2.8, 0.81, 1.0, 2.4, 1.02, 0.87),
      (-9.4, 87.3, 26.8, 39.1)),
    C("OKLO", 112.37, 5.94, 8214600, 3387100, 6.2, "B",
      "Burst is clean but the pre-burst week was wider than this name's own norm, so the base is loose.",
      "loose base", "claude", True,
      (1, 0.69, 23.8, 14.2, 6.7, 1.24, 1.7, 3.6, 1.14, 0.81),
      (-12.8, 318.4, 58.9, 96.7)),
    C("BE", 34.55, 4.21, 11208400, 5641200, 5.9, "C",
      "Marginal burst on a 2x volume day; the advance into it was choppy and the close is mid-range.",
      "close only mid-range", "claude", True,
      (1, 0.48, 17.1, 8.3, 3.4, 0.89, 1.3, 2.9, 1.08, 0.64),
      (-16.2, 96.4, 21.3, 34.8)),
    C("UEC", 11.84, 4.73, 14663900, 6892400, 5.7, "C",
      "Volume barely cleared the prior day and the pre-burst session was already active.",
      "no volume expansion", "claude", True,
      (1, 0.58, 29.6, 16.4, 5.2, 1.11, 2.4, 4.3, 1.41, 0.83),
      (-7.8, 74.9, 18.6, 27.4)),
    C("RKLB", 68.19, 4.34, 16482300, 7913600, None, None, None, None, "fallback", True,
      (1, 0.61, 31.2, 17.8, 5.9, 1.18, 1.9, 4.0, 1.22, 0.79),
      (-5.4, 264.8, 63.2, 108.4)),
    C("FCEL", 6.28, 5.62, 22947100, 9184200, None, None, None, None, "fallback", True,
      (3, 0.58, 12.4, 6.1, 6.3, 1.32, 2.6, 5.1, 1.47, 0.72),
      (-41.7, 38.2, 9.4, -6.8)),
    C("PLUG", 3.94, 6.49, 48213700, 21094800, 4.9, "C",
      "Low-priced name near the price floor; three prior bursts and a wide base make this a poor setup.",
      "low base quality, prone to fades", "claude", True,
      (3, 0.39, 14.8, 7.2, 7.1, 1.29, 1.5, 3.3, 1.13, 0.74),
      (-52.3, 24.6, 4.2, -18.9)),
    C("SMR", 27.41, 4.09, 9932100, 4761300, 4.7, "C",
      "Barely a 4% day and the prior session was heavier than the burst; nothing to lean on here.",
      "burst day is not the volume day", "claude", True,
      (2, 0.56, 21.4, 11.8, 4.6, 1.04, 2.1, 4.4, 1.34, 0.77),
      (-24.1, 88.7, 14.9, 22.6)),
    C("ACHR", 12.06, 5.18, 19446800, 8712400, 4.5, "C",
      "Choppy prior move and a mid-range close; the burst has no base behind it.",
      "no base", "claude", True,
      (1, 0.37, 22.9, 13.7, 5.4, 1.16, 1.6, 3.7, 1.19, 0.68),
      (-19.8, 61.4, 11.7, 8.3)),
    C("JOBY", 15.72, 4.46, 13884200, 6207900, 4.3, "C",
      "Fifth burst in the leg. The move is old and the close gave back most of the day's gain.",
      "trend is old", "claude", True,
      (4, 0.66, 18.3, 10.9, 3.9, 0.97, 1.2, 2.7, 1.06, 0.61),
      (-13.6, 79.2, 16.4, 31.8)),
    C("INDI", 4.87, 7.21, 8137400, 3624100, 4.1, "skip",
      "Erratic prior action, no consolidation and a weak close — this is noise, not a setup.",
      "no consolidation", "claude", True,
      (1, 0.31, 9.6, 4.4, 6.8, 1.41, 1.8, 4.2, 1.08, 0.58),
      (-63.4, 19.7, -3.2, -27.1)),
    C("LAES", 5.34, 8.96, 6742900, 2938700, 3.9, "skip",
      "Sharp move with nothing behind it: the prior 30 days show no trend to continue.",
      "no prior trend", "claude", True,
      (1, 0.22, 8.1, 3.7, 7.4, 1.53, 1.4, 3.8, 1.17, 0.63),
      (-58.9, 27.3, -1.8, -14.6)),
    C("QUBT", 18.62, 5.77, 15208600, 6841200, 3.6, "skip",
      "Already up 41% on the month; a burst this late in a parabolic move is a distribution risk.",
      "parabolic, late", "claude", True,
      (4, 0.72, 41.3, 24.8, 5.7, 0.94, 2.7, 5.4, 1.52, 0.71),
      (-11.2, 388.6, 118.4, 204.7)),
    C("WULF", 8.19, 4.92, 27391400, 12064700, 3.4, "skip",
      "Group-wide move rather than a stock-specific setup; base is wide and the close is soft.",
      "moved with the group, not alone", "claude", True,
      (1, 0.64, 24.6, 14.1, 6.2, 1.27, 2.2, 4.7, 1.36, 0.66),
      (-31.4, 52.8, 8.7, -2.4)),
    C("HUT", 22.14, 4.18, 7628300, 3491600, 3.2, "skip",
      "Marginal gain, marginal volume, and the prior day already moved 3% — nothing is quiet here.",
      "prior day was not calm", "claude", True,
      (1, 0.63, 20.4, 12.6, 5.1, 1.09, 3.1, 5.8, 1.44, 0.69),
      (-27.6, 64.1, 12.3, 18.9)),
    C("BTDR", 13.47, 6.03, 11742800, 5108300, 3.0, "skip",
      "The base is twice as wide as this name's own norm; there is no coil to release.",
      "wide base", "claude", True,
      (1, 0.45, 16.8, 9.4, 8.3, 1.68, 1.9, 4.1, 1.24, 0.73),
      (-36.2, 41.9, 5.6, -9.7)),
    C("GEVO", 3.12, 9.47, 19883100, 8214600, 2.8, "skip",
      "A 9% pop on no base; historically these give it all back within days.",
      "no base under the move", "claude", True,
      (4, 0.28, 11.2, 5.8, 9.1, 1.74, 1.7, 4.6, 1.09, 0.75),
      (-71.8, 14.2, -8.4, -34.2)),
]

def _consistent_with_the_checklist(specs):
    """Make the hand-authored measurements possible under the CURRENT rules.

    These tuples were written against the pre-step-7 checklist, where Y ignored
    the burst day and C ignored the prior day's range. Under the real rules some
    rows now gate out, which the assertions below catch. Rather than loosen the
    rules to fit invented numbers, walk the numbers back until they describe a
    candidate the real checklist would actually pass: shrink the prior run-up so
    run-up-through-the-burst clears Y, and the prior day's range so it sits
    inside its own norm for C. Nothing else is touched.
    """
    out = []
    for spec in specs:
        d = spec._asdict()
        lm = list(d["lm"])
        gain = d["gain"]
        for _ in range(40):
            passes = sum(1 for c in lynch(*lm, gain=gain) if c["pass"])
            if passes >= 3:
                break
            lm[2] *= 0.80          # run_up
            lm[3] *= 0.80          # ext vs 20SMA
            lm[7] *= 0.85          # prior day's range
        d["lm"] = tuple(lm)
        out.append(type(spec)(**d))
    return out


SPEC = _consistent_with_the_checklist(_remap(SPEC, 0))


def burst_bar(gain, close_pos, recent_range, i):
    """The burst bar's own geometry, in src.lynch.BURST_BAR_KEYS' shape.

    DERIVED FROM THE ROW'S OWN MEASUREMENTS, not invented beside them. The
    three numbers describe one bar and cannot be chosen independently: the
    part of the day's gain that happened overnight fixes the open, the low
    sits a little under it, and `close_pos` -- the number the `H` line
    already prints -- fixes the high. A row whose gap and width were authored
    separately would describe a bar no session can produce, which is the
    class check_fixture_fresh.py exists to close.

    `range_expansion` divides by the `N` line's own pre-burst range, because
    that is the number src.lynch.burst_bar_shape() divides by -- one window,
    named once, in the module that owns it, and one arithmetic: the mean of
    the raw widths rounded once, which is what `N` prints. It divided by the
    mean of the ROUNDED widths until round 11's audit, so this assertion was
    a true statement about this generator and a false one about the pipeline,
    and every row here was a shape src.lynch could not produce.

    This generator holds measurements and never slices a frame, so the
    numbers are authored rather than measured; what makes them honest is
    that they are consistent with each other and with the rest of the row.
    """
    share = (i % 4) / 3.0            # how much of the move happened overnight
    tail = 0.2 + (i % 3) * 0.35      # how far the low sat under the open, %
    close = 1.0 + gain / 100.0
    open_ = 1.0 + gain * share / 100.0
    low = min(open_, close) * (1.0 - tail / 100.0)
    high = low + (close - low) / close_pos
    assert low <= open_ <= high, (
        f"row {i}: an open outside its own bar is a price nobody paid")
    width = round((high - low) / close * 100, 1)
    return {
        "gap_pct": round((open_ - 1.0) * 100, 1),
        "bar_range_pct": width,
        "range_expansion": round(width / recent_range, 2) if recent_range else None,
    }


def build_candidate(s, i):
    detail = lynch(*s.lm, gain=s.gain)
    passes = sum(1 for d in detail if d["pass"])
    assert passes >= 3, f"{s.t} would have been gated out at {passes}/6"
    if s.src == "fallback":
        # src/scorer.py's own fallback formula, verbatim
        # THE SCORER'S OWN RULE, not a formula typed here. This was
        # `round(passes / len(detail) * 10, 1)`, which is the pre-step-8
        # arithmetic: src.scorer._fallback_score() has mapped the pass count
        # to the LOW end of its rubric band since then (5/6 is 7.0, not 8.3),
        # so the fixture, the page's sentence about the fallback and the code
        # were three different rules -- and the sentence and the fixture
        # agreed, which is why nothing noticed.
        score = _fallback_score({"passes": passes, "total": len(detail), "summary": ""})
        verdict = "B" if score >= 6 else "skip"
        reason = f"AI unavailable; checklist score {passes}/{len(detail)}."
        risk = "not AI-reviewed"
        prov = {"source": "fallback", "model": None, "chart_seen": False,
                "error": "anthropic.APIStatusError: 529 overloaded_error (3 retries exhausted)"}
    else:
        score, verdict, reason, risk = s.score, s.verdict, s.reason, s.risk
        prov = {"source": "claude", "model": MODEL, "chart_seen": s.chart, "error": None}
    off_hi, abv_lo, p3, p6 = s.ctx
    # The three burst-bar numbers describe ONE bar, and the expansion is the
    # width over the `N` line's own pre-burst range -- read back OUT of the
    # finished row rather than trusted, so a generator dividing by anything
    # else fails here rather than shipping a row whose two printed numbers
    # cannot be reconciled by the reader they are printed for.
    bar = burst_bar(s.gain, s.lm[9], s.lm[4], i)
    printed = float(next(d["value"] for d in detail if d["code"] == "N")
                    .split("range ")[1].split("%")[0])
    assert bar["range_expansion"] == round(bar["bar_range_pct"] / printed, 2), (
        f"{s.t}: {bar['bar_range_pct']}% over a {printed}%/day base is not "
        f"{bar['range_expansion']}x")
    # Bonde's two measurements. This fixture holds MEASUREMENTS and not frames,
    # so there is no walk here to count a run of up days off; they are authored
    # from the row's position, spread across every value a SCORED row can
    # legitimately carry. Up days cannot exceed MAX_CONSECUTIVE_UP_DAYS -- past
    # that the pipeline's veto would have refused the row, so a scored one
    # carrying 3 describes a run this pipeline cannot produce. The worst base
    # day can be anything, including past BREAKDOWN_PCT, because that criterion
    # rejects nothing: every third row here is one that broke down and was
    # scored anyway, which is the state the page has to render.
    up_days = i % (MAX_CONSECUTIVE_UP_DAYS + 1)
    worst_base = round(BREAKDOWN_PCT + (1.4 if i % 3 else -0.6), 1)
    return {
        "rank": None,
        "ticker": s.t,
        "date": SESSION,
        "close": s.close,
        "gain_pct": s.gain,
        "volume": s.vol,
        "prev_volume": s.prev,
        "volume_ratio": round(s.vol / s.prev, 2),
        "dollar_volume": round(s.close * s.vol),
        "lynch": f"{passes}/{len(detail)}",
        "lynch_passes": passes,
        "lynch_total": len(detail),
        "lynch_detail": detail,
        "score": score,
        "verdict": verdict,
        "reason": reason,
        "key_risk": risk,
        "provenance": prov,
        "chart": (f"charts/{s.t}.png" if s.chart else None),
        "chart_error": (None if s.chart else
                        "mplfinance ValueError: only 41 sessions of history, need 85"),
        "context": {"pct_off_52w_high": off_hi, "pct_above_52w_low": abv_lo,
                    "perf_3mo_pct": p3, "perf_6mo_pct": p6,
                    "consecutive_up_days": up_days, "worst_base_day_pct": worst_base,
                    **bar},
        "streak": streak(i),
        # Pending on both bases, in the shape the ledger writes.
        "forward_returns": ledger.empty_returns(),
    }

candidates = [build_candidate(s, i) for i, s in enumerate(SPEC)]
candidates.sort(key=lambda c: c["score"], reverse=True)
for i, c in enumerate(candidates, 1):
    c["rank"] = i

# --- what did not get scored ------------------------------------------------
# 48 bursts - 25 scored = 23. Sixteen failed the >=3/6 gate; six cleared it but
# fell outside MAX_TO_SCORE, which sorts on (passes, gain_pct) descending; and
# one was vetoed outright, which is neither of those and has to read as neither.
#
# These rows carry their 2LYNCH MEASUREMENTS (lm), not just a pass count, for
# the same reason the scored rows do: the dashboard's per-check aggregate asks
# which of the six checks is doing the gating, and that question cannot be
# answered from the names that passed the gate. A rate computed over the scored
# 25 alone is survivorship bias wearing a percentage sign — the candidates a
# check rejected are exactly the ones missing from it. `passes` stays declared
# because the gate/cap arithmetic below is built on it, and build_gated asserts
# the measurements compute back to it.
G = collections.namedtuple("G", "t close gain vol prev passes reason lm")
GATED = [
    #                                                    2LYNCH measurements, in lynch()'s argument order
    G("SOUN",  8.94,  5.12, 14208700,  6104300, 2, "lynch_gate",
      (1, 0.44, 28.3, 16.4, 4.2, 1.21, 2.6, 4.9, 1.38, 0.91)),
    G("MARA",  19.83, 4.71, 28417200, 13092400, 2, "lynch_gate",
      (3, 0.31, 18.1, 9.4, 6.0, 1.44, 3.2, 5.7, 1.51, 0.84)),
    G("RIOT",  14.26, 6.38, 31844100, 14208900, 2, "lynch_gate",
      (4, 0.22, 26.9, 15.8, 7.7, 1.63, 1.6, 3.2, 1.13, 0.78)),
    G("CLSK",  11.07, 4.29, 22193600, 10847100, 1, "lynch_gate",
      (2, 0.48, 41.2, 24.3, 9.2, 1.32, 2.9, 5.2, 1.29, 0.88)),
    G("AI",    27.61, 5.84,  9214800,  4108600, 2, "lynch_gate",
      (0, 0.36, 31.4, 17.7, 10.9, 1.77, 3.6, 6.1, 1.64, 0.73)),
    G("BBAI",   6.42, 8.13, 18774200,  7442800, 1, "lynch_gate",
      (3, 0.19, 47.6, 28.4, 4.9, 1.18, 2.4, 4.6, 1.73, 0.95)),
    G("VRT",   142.9, 4.06,  7118400,  3402700, 2, "lynch_gate",
      (2, 0.41, 23.8, 13.9, 8.3, 1.51, 4.1, 7.2, 1.47, 0.81)),
    G("SMCI",  38.74, 4.92, 26094300, 11884200, 2, "lynch_gate",
      (1, 0.64, 36.2, 21.7, 12.0, 1.94, 2.2, 4.4, 1.33, 0.64)),
    G("APLD",  16.38, 7.44, 13627900,  5814300, 1, "lynch_gate",
      (1, 0.50, 25.4, 15.2, 5.3, 1.27, 3.4, 5.9, 1.88, 0.41)),
    G("NNE",   34.12, 6.71,  6483100,  2914700, 2, "lynch_gate",
      (2, 0.34, 52.1, 31.6, 10.0, 1.68, 1.7, 3.4, 1.19, 0.71)),
    G("CRML",   4.18, 11.62, 9847300,  3218400, 0, "lynch_gate",
      (6, 0.13, 38.9, 22.8, 6.9, 2.13, 4.7, 8.0, 1.57, 0.36)),
    G("MVIS",   1.94, 9.88, 21094600,  8412700, 0, "lynch_gate",
      (2, 0.44, 28.3, 16.4, 4.2, 1.21, 2.6, 4.9, 1.38, 0.61)),
    G("GRRR",   3.47, 14.21, 7482100,  2104800, 0, "lynch_gate",
      (3, 0.31, 33.7, 19.1, 6.0, 1.44, 3.2, 5.7, 1.51, 0.52)),
    G("SERV",  12.83, 5.47, 10428300,  4816200, 2, "lynch_gate",
      (1, 0.22, 26.9, 15.8, 7.7, 1.63, 2.1, 4.3, 1.42, 0.78)),
    G("LTBR",  17.29, 4.83,  5218700,  2408100, 2, "lynch_gate",
      (2, 0.48, 21.6, 11.8, 9.2, 1.32, 2.9, 5.2, 1.29, 0.88)),
    G("KTOS",  41.62, 4.11,  6104200,  2884300, 2, "lynch_gate",
      (5, 0.66, 31.4, 17.7, 10.9, 1.77, 0.7, 1.9, 0.88, 0.38)),
    # cleared the gate at 3/6 but ranked below the top 25 on (passes, gain_pct)
    G("EOSE",   7.83, 4.07, 12048600,  5417300, 3, "score_cap",
      (1, 0.19, 11.3, 5.4, 4.9, 1.18, 2.4, 4.6, 1.73, 0.95)),
    G("MP",     48.16, 4.05, 8114700,  3982400, 3, "score_cap",
      (2, 0.41, 23.8, 13.9, 8.3, 1.51, 0.5, 1.6, 0.79, 0.81)),
    G("ASTS",   61.94, 4.04, 11384200, 5208900, 3, "score_cap",
      (1, 0.27, 36.2, 21.7, 12.0, 1.94, 1.4, 3.0, 1.11, 0.76)),
    G("VSAT",   28.37, 4.03,  4917200, 2314600, 3, "score_cap",
      (1, 0.50, 7.9, 3.2, 5.3, 1.27, 3.4, 5.9, 1.88, 0.86)),
    G("NPWR",    9.16, 4.02,  6742800, 3108400, 3, "score_cap",
      (0, 0.56, 52.1, 31.6, 10.0, 1.68, 2.8, 5.1, 1.26, 0.71)),
    G("TMC",     4.71, 4.01, 15208400, 7014900, 3, "score_cap",
      (6, 0.13, 12.6, 6.9, 4.2, 0.86, 4.7, 8.0, 1.57, 0.93)),
    # Refused outright, and the only row here that passed the whole checklist:
    # a 6/6 setup three up days into a run is what Bonde's cardinal rule is
    # about, and it is the row the page and the email have to describe without
    # saying the checklist rejected it. Its `lm` clears every check -- the
    # assertion in build_gated() is what proves that, not this comment.
    G("PLTR",  178.4,  4.62, 31840200, 12417600, 6, VETO_REASONS["up_days"],
      (0, 0.86, 8.1, 3.4, 1.9, 0.61, 0.4, 1.1, 0.82, 0.96)),
    # Refused by rule 6 before the checklist saw them: dollar volume below
    # FLOOR, the session's 30th-percentile cut. Their pass counts are whatever
    # the measurements say -- one clears the gate, one does not -- because the
    # rule never asked. The row the record used to lose entirely (round 5).
    G("WBD",    9.84,  6.27,  1042600,   418300, 4, ledger.LIQUIDITY_REASON,
      (1, 0.58, 12.4, 6.1, 5.8, 1.14, 1.9, 3.7, 1.08, 0.82)),
    G("TTWO",  14.62,  4.38,   612400,   287900, 2, ledger.LIQUIDITY_REASON,
      (2, 0.29, 34.7, 20.9, 9.6, 1.71, 3.3, 5.8, 1.62, 0.44)),
]

#: Rule 6's floor for this session, in dollars: the 30th percentile of every
#: name that traded. Below every scored and gated row's dollar volume except
#: the two rows marked LIQUIDITY_REASON, which the assertions below hold.
FLOOR = 12_400_000
PCTILE = 30.0
def _still_gated_out(specs):
    """Make each gated row consistent with the reason it declares.

    Two different targets, which the first version of this loop conflated:
      lynch_gate rows must FAIL the checklist -- walk down the check that is
        actually passing (H, the weakest), not one already failing. Widening a
        red check can never converge; the first attempt inflated a prior-day
        range to 166,000% before the iteration cap stopped it.
      score_cap rows must CLEAR the checklist and be cut by MAX_TO_SCORE
        instead -- walk them up, or the fixture claims a row was cap-dropped
        when the gate would have taken it first.
    """
    out = []
    for spec in specs:
        d = spec._asdict()
        lm = list(d["lm"])
        if d["reason"] in VETO_REASONS.values() or d["reason"] == ledger.LIQUIDITY_REASON:
            # Nothing to converge: a vetoed row's pass count is not constrained
            # by the gate, and this one is hand-authored to clear every check;
            # a liquidity row's pass count was never consulted at all.
            out.append(spec)
            continue
        wants_gate_fail = d["reason"] == "lynch_gate"
        for _ in range(60):
            passes = sum(1 for c in lynch(*lm, gain=d["gain"]) if c["pass"])
            if wants_gate_fail and passes < MIN_LYNCH_PASSES:
                break
            if not wants_gate_fail and passes >= MIN_LYNCH_PASSES:
                break
            if wants_gate_fail:
                lm[9] = max(lm[9] * 0.90, 0.05)    # close_pos down -- H fails
            else:
                lm[2] *= 0.80                      # run_up down -- Y clears
                lm[3] *= 0.80                      # ext down
                lm[7] *= 0.85                      # prior-day range down -- C clears
        d["lm"] = tuple(lm)
        out.append(type(spec)(**d))
    return out


GATED = _still_gated_out(_remap(GATED, len(SPEC)))

def build_gated(g, i):
    detail = lynch(*g.lm, gain=g.gain)
    # The same two Bonde measurements the scored rows carry, and for the
    # stronger reason: a vetoed row is the one the record needs if the veto is
    # ever to be judged. Authored, not derived from a frame, because this
    # generator holds measurements and not walks -- but a VETOED row must
    # carry more than MAX_CONSECUTIVE_UP_DAYS, since that is why it was
    # refused, and a gate or cap row must not.
    vetoed = g.reason in VETO_REASONS.values()
    up_days = (MAX_CONSECUTIVE_UP_DAYS + 1 if vetoed
               else i % (MAX_CONSECUTIVE_UP_DAYS + 1))
    worst_base = round(BREAKDOWN_PCT + (1.4 if i % 3 else -0.6), 1)
    passes = sum(1 for d in detail if d["pass"])
    # The measurements are the source of truth, exactly as they are for a scored
    # row; `passes` is what the gate and cap arithmetic below counts on. If the
    # two ever disagree the fixture is describing a run the checklist could not
    # produce, so fail here rather than ship it.
    # The count is DERIVED from the measurements, not declared beside them. It
    # used to be asserted equal to a hand-written number, so the step-7 rule
    # changes broke the generator instead of simply producing a stricter -- and
    # correct -- fixture. What must hold is that each row is consistent with the
    # reason it gives for not being scored, using the pipeline's own gate.
    if g.reason in VETO_REASONS.values():
        # The only reason with nothing to prove about the pass count: a veto
        # is absolute, so a vetoed row may sit anywhere from 0/6 to 6/6. What
        # IS asserted is that this one is the interesting end of that range --
        # a fixture whose vetoed row also failed the checklist would let the
        # page call it a gate rejection and still look right.
        assert passes == len(detail), (
            f"{g.t}: {passes}/6, so this row cannot show that a veto refuses a "
            "burst the checklist was happy with")
    elif g.reason == ledger.LIQUIDITY_REASON:
        # Nothing to prove about the pass count either -- the rule that
        # refused it is about dollar volume, and THAT is what is asserted.
        assert round(g.close * g.vol) < FLOOR, (
            f"{g.t}: ${g.close * g.vol:,.0f}/day is not below the ${FLOOR:,} floor "
            "that this row says refused it")
    elif g.reason == "lynch_gate":
        assert passes < MIN_LYNCH_PASSES, (
            f"{g.t}: {passes}/6 clears the gate, so it was not gated out by the checklist")
    else:
        assert passes >= MIN_LYNCH_PASSES, (
            f"{g.t}: {passes}/6 never cleared the gate, so the call cap is not why it went unscored")
    if g.reason != ledger.LIQUIDITY_REASON:
        assert round(g.close * g.vol) >= FLOOR, (
            f"{g.t}: ${g.close * g.vol:,.0f}/day sits below the ${FLOOR:,} floor, so rule 6 "
            f"would have refused it before the reason it gives ({g.reason}) applied")
    return {
        "ticker": g.t, "date": SESSION, "close": g.close, "gain_pct": g.gain,
        "volume": g.vol, "volume_ratio": round(g.vol / g.prev, 2),
        # src.ledger.gated_record keeps the number rule 6 judged on every row.
        "dollar_volume": round(g.close * g.vol),
        "lynch": f"{passes}/{len(detail)}", "lynch_passes": passes,
        "lynch_total": len(detail), "lynch_detail": detail,
        # The burst bar's shape on a refused row too, for the reason the two
        # Bonde numbers are here: the record's whole use is judging what was
        # refused, and a row archived without its measurements can never be.
        "context": {"consecutive_up_days": up_days, "worst_base_day_pct": worst_base,
                    **burst_bar(g.gain, g.lm[9], g.lm[4], i)},
        "streak": streak(i), "reason": g.reason,
    }

gated_out = [build_gated(g, i) for i, g in enumerate(GATED)]

# every 3/6 score_cap row must sit below the weakest scored 3/6 row on gain_pct
worst_scored_3 = min((c["gain_pct"] for c in candidates if c["lynch_passes"] == 3), default=99)
for g in gated_out:
    if g["reason"] == "score_cap":
        assert g["gain_pct"] < worst_scored_3, g["ticker"]

BURSTS = 50
PASSED = 31
CAP = 25
VETOED = 1
ILLIQUID = 2
assert len(candidates) + len(gated_out) == BURSTS
assert ILLIQUID == sum(1 for g in gated_out if g["reason"] == ledger.LIQUIDITY_REASON)
for _c in candidates:
    assert _c["dollar_volume"] >= FLOOR, (
        f"{_c['ticker']} was scored on ${_c['dollar_volume']:,}/day, below the ${FLOOR:,} floor")
assert len(candidates) == CAP
assert PASSED - CAP == sum(1 for g in gated_out if g["reason"] == "score_cap")
# A vetoed burst never reached the gate, so it is not part of PASSED -- and
# this last sum used to be written as "everything that is not score_cap",
# which counted a veto as a checklist rejection. Four reasons, four counts.
assert VETOED == sum(1 for g in gated_out if g["reason"] in VETO_REASONS.values())
# The invariant the comment in build_candidate() states, now asserted rather
# than described. An audit set the scored rows' up-day counts to 0-4, and the
# generator, the freshness guard, the suite and 134 dashboard checks all passed
# while the page rendered "4 up days" on a scored card under a rule that
# refuses 3 or more -- a fixture describing a run this pipeline cannot produce,
# which is the exact class check_fixture_fresh.py exists to close.
for _c in candidates:
    assert _c["context"]["consecutive_up_days"] <= MAX_CONSECUTIVE_UP_DAYS, (
        f"{_c['ticker']} was scored with {_c['context']['consecutive_up_days']} up days "
        f"into its burst; the veto refuses {MAX_CONSECUTIVE_UP_DAYS + 1} or more, so this "
        "row describes a run the pipeline cannot produce")
for _g in gated_out:
    _refused = _g["reason"] in VETO_REASONS.values()
    _up = _g["context"]["consecutive_up_days"]
    assert (_up > MAX_CONSECUTIVE_UP_DAYS) == _refused, (
        f"{_g['ticker']} carries {_up} up days and reason {_g['reason']}: a vetoed row "
        "must exceed the threshold that refused it, and one that does must be vetoed")
assert BURSTS - PASSED - VETOED - ILLIQUID == sum(1 for g in gated_out if g["reason"] == "lynch_gate")

# What the scan SAW, in one block, because two consumers read it: the names
# that have stopped printing and the coverage counts are the same night, and
# hand-authoring them separately is how a fixture ends up describing a file
# the pipeline cannot produce. Three names never bursting are the ones the
# feed had trouble with -- two behind the session, one it answered with
# nothing at all -- and everything else answered and was measured.
_QUIET = [s for s in UNIVERSE
          if s not in {r["ticker"] for r in candidates + gated_out}]
MEASURED = len(UNIVERSE) - 3
SCAN_STATS = {
    "session": SESSION,
    "stale": dict(zip(_QUIET[:2], ["2026-06-12", "2026-08-03"])),
    "no_bars_names": _QUIET[2:3],
    "requested": len(UNIVERSE),
    "with_bars": len(UNIVERSE) - 1,
    "fresh": MEASURED,
    "measured": MEASURED,
    "gapped": {},
    "no_bars": 1,
    "dropped": 0,
    "duplicate_bars": 0,
}
assert SCAN_STATS["with_bars"] - len(SCAN_STATS["stale"]) == MEASURED, (
    "the coverage counts have to add up the way a real scan's do")
assert MEASURED < SCAN_STATS["with_bars"] < SCAN_STATS["requested"], (
    "this fixture is the THIN night -- some names never answered and some "
    "answers could not be measured -- and three prose surfaces called it a "
    "clean one, whose caption is the bare 'no 4% gain on the day'. That is "
    "history/, which is 77 of 77 of 77. If this stops being true, sweep "
    "tests/fixtures/README.md and the comments beside `coverage` here.")

by_src = collections.Counter(c["provenance"]["source"] for c in candidates)

# `n` counts SETUPS and `rows` the rows they were collapsed from: a name that
# burst on three consecutive sessions is one observation, not three, because
# its d1/d3/d5 windows overlap and measure one move (src/ledger.py's
# setup_leads). n < rows on every session that carries a repeat, and the two
# are equal on 2026-08-21 because it is the oldest run this file holds -- with
# nothing before it, every appearance in it leads its own setup as far as the
# record can tell.
#
# These sessions are also the record the streak blocks above name: seven of
# them before SESSION, the oldest 2026-08-21, which is what SPAN says and what
# makes the day numbers up there ones the real code could have written.
runs = [
    {"date": SESSION, "type": "evening", "bursts": BURSTS, "passed_gate": PASSED,
     "scored": len(candidates), "shortlist_size": 5, "top_score": candidates[0]["score"],
     "fallbacks": by_src["fallback"],
     "forward_returns": {"d1": None, "d3": None, "d5": None, "n": 0, "rows": 0}},
    {"date": "2026-08-31", "type": "evening", "bursts": 39, "passed_gate": 21, "scored": 21,
     "shortlist_size": 5, "top_score": 8.4, "fallbacks": 0,
     "forward_returns": {"d1": 1.12, "d3": None, "d5": None, "n": 19, "rows": 21}},
    {"date": "2026-08-28", "type": "evening", "bursts": 52, "passed_gate": 28, "scored": 25,
     "shortlist_size": 5, "top_score": 9.1, "fallbacks": 2,
     "forward_returns": {"d1": -0.63, "d3": None, "d5": None, "n": 23, "rows": 25}},
    {"date": "2026-08-27", "type": "evening", "bursts": 44, "passed_gate": 24, "scored": 24,
     "shortlist_size": 5, "top_score": 8.8, "fallbacks": 0,
     "forward_returns": {"d1": 2.07, "d3": 1.44, "d5": None, "n": 22, "rows": 24}},
    {"date": "2026-08-26", "type": "evening", "bursts": 33, "passed_gate": 18, "scored": 18,
     "shortlist_size": 5, "top_score": 7.9, "fallbacks": 1,
     "forward_returns": {"d1": 0.88, "d3": 2.31, "d5": None, "n": 17, "rows": 18}},
    {"date": "2026-08-25", "type": "evening", "bursts": 38, "passed_gate": 22, "scored": 22,
     "shortlist_size": 5, "top_score": 9.0, "fallbacks": 0,
     "forward_returns": {"d1": 1.84, "d3": 2.97, "d5": -0.42, "n": 21, "rows": 22}},
    {"date": "2026-08-24", "type": "evening", "bursts": 41, "passed_gate": 23, "scored": 23,
     "shortlist_size": 5, "top_score": 8.6, "fallbacks": 1,
     "forward_returns": {"d1": -1.07, "d3": 0.94, "d5": 1.62, "n": 22, "rows": 23}},
    {"date": "2026-08-21", "type": "evening", "bursts": 36, "passed_gate": 20, "scored": 20,
     "shortlist_size": 5, "top_score": 8.2, "fallbacks": 0,
     "forward_returns": {"d1": 0.41, "d3": 1.18, "d5": 2.05, "n": 20, "rows": 20}},
]
# src.ledger.add_run keeps the universe on every entry, so a --tickers smoke
# test can be told from a scan; these were all "scans" of the checked-in file.
for _i, _run in enumerate(runs):
    # The open basis beside the close basis on every run mean (src.ledger's
    # mean_returns), with its own n. Hand-authored a little below the close
    # basis, which is what an overnight gap in the direction of the burst
    # does to the price a reader could have paid; the headline run has
    # nothing on either basis yet.
    _fr = _run["forward_returns"]
    _fr["from_open"] = {k: (None if _fr[k] is None else round(_fr[k] - 0.6 - 0.05 * _i, 2))
                        for k in ("d1", "d3", "d5")}
    _fr["from_open"]["n"] = 0 if _fr["n"] == 0 else _fr["n"] - (1 if _i % 3 == 0 else 0)
    # The universe's own return from each session (src.ledger.add_run writes
    # the pending shape; fill_benchmarks fills it on the evening five sessions
    # later). Hand-authored where the run's own returns are in: a little
    # below the picks, over most of the names the file holds.
    # The floor each night applied (src.ledger.add_run keeps it): the
    # headline run's is FLOOR; the older ones vary the way a percentile of
    # the day's tape would, with a refusal count that goes with it.
    _run["liquidity"] = ({"pctile": PCTILE, "floor": FLOOR, "refused": ILLIQUID} if _i == 0
                         else {"pctile": PCTILE, "floor": FLOOR + 400_000 * ((_i * 7) % 5 - 2),
                               "refused": (_i * 3) % 4})
    _bench = ledger.empty_benchmark()
    for _h in ("d1", "d3", "d5"):
        if _fr[_h] is not None:
            _bench[_h] = round(_fr[_h] - 0.9 + 0.1 * (_i % 3), 2)
            # Over the names at or above that night's floor: the fill leaves
            # out the ones under it (universe_returns), and stamps both the
            # floor and the count, so n is the universe less those and less
            # a couple that did not carry the session.
            _bench["liquidity_floor"] = _run["liquidity"]["floor"]
            _bench["below_floor"] = 60 + (_i * 5) % 11
            _bench["n" + _h[1:]] = len(UNIVERSE) - _bench["below_floor"] - 2 - (_i % 4)
            _bench["from_open"][_h] = round(_bench[_h] - 0.3, 2)
            _bench["from_open"]["n" + _h[1:]] = _bench["n" + _h[1:]] - 1
    _run["benchmark"] = _bench
    _run["universe"] = {"label": "data/symbols.txt (checked in)", "size": len(UNIVERSE)}
    # How many names each night measured (src.ledger.add_run copies it off
    # run.coverage). Never 0 here: a blind night is a state the page and the
    # streak rules both have their own sentence for, and a fixture cannot
    # hold both it and the clean night it exists to show -- the smoke's
    # `blindscan` variant is that one.
    _run["measured"] = MEASURED if _i == 0 else MEASURED - (_i % 4)
    # One screener across the whole file: these eight sessions were scanned by
    # the rules this checkout holds, so evidence.rules reports one set and
    # nothing on the page warns about a blended record. The drifted state is a
    # smoke variant, because a fixture cannot hold both.
    _run["rules"] = rules_fingerprint()
    # Which side of the fill window each entry is on (src.ledger.dashboard
    # stamps it off _fill_window()). Eight runs is inside FILL_WINDOW_RUNS,
    # so every one of them is still fetched for and none may say otherwise;
    # the page's other state -- a run past the window whose horizon stays
    # null for good -- needs eleven runs and is a smoke variant, because a
    # fixture this size cannot hold it.
    assert len(runs) <= ledger.FILL_WINDOW_RUNS, "an entry past the window would be stamped closed"
    _run["fills_closed"] = False

# The evidence block, computed by the REAL src/ledger.py over this fixture's
# own rows rather than hand-authored. One run, whose forward returns have not
# happened yet -- so every mean in it is null and every n is zero, which is
# exactly the state of the page on the first day it publishes anything, and
# the state a reader sees until five sessions have closed. The thirty-run
# fixture in tests/fixtures/history is the populated twin; between them the
# page's empty and full paths are both exercised.
#
# Which means this file describes TWO records at once, and says so here and
# in tests/fixtures/README.md rather than leaving a reader to find it: `runs`
# and the streak blocks above are a hand-authored seven-session history, so
# the runs table and the day numbers have something to show, while `evidence`
# is the real code's view of the one run this file actually holds rows for,
# so evidence.record says runs: 1 beside a runs table of eight. A file a real
# run writes never disagrees with itself this way -- both come off the same
# ledger there -- and the history fixture is where the two agree.
_LEDGER_RUNS = [{
    "date": SESSION, "type": "evening", "shortlist_size": 5,
    # The same rules the run block names, so evidence.rules reports one set
    # rather than a run that predates the fingerprint -- which is what this
    # file would otherwise describe, and is not true of it.
    "rules": rules_fingerprint(),
    # And the benchmark Ledger.add_run() would have written for this run:
    # pending, because nothing after this session has happened. Without it
    # evidence.universe.setups was 0 where the pipeline writes 25 for the
    # same record -- the fixture describing a file the pipeline cannot
    # produce, which is the one thing this generator exists to prevent.
    "benchmark": {**ledger.empty_benchmark(),
                  "universe": {"label": "data/symbols.txt (checked in)", "size": len(UNIVERSE)}},
    "candidates": [ledger.slim_row(c, scored=True) for c in candidates],
    "gated": [ledger.slim_row(g, scored=False) for g in gated_out],
}]
EVIDENCE = ledger.evidence(_LEDGER_RUNS)
assert all(entry["n"] == 0 for entry in EVIDENCE["overall"]["outcomes"]), (
    "this fixture is one session old; nothing in it can have an outcome yet")

data = {
    "schema_version": 1,
    "app": "SpicyStock",
    "generated": "2026-09-01T22:14:07Z",
    "_contract": {
        "about": "docs/data.json is written by src/pipeline.py at the end of every run (see src/ledger.py) and read by docs/index.html at runtime. THIS copy is not one of those: it is the hand-authored fixture from tools/make_fixture.py, and run.fixture is true, which is how the morning run refuses to mail its invented tickers as a watchlist. A real run overwrites it and sets run.fixture false. This block is documentation, not data; consumers ignore it.",
        "documented_in": "README.md, 'The data contract'",
        # IMPORTED from src.ledger, which is what the pipeline writes into its
        # own output. A second copy here is a second contract, and a fixture
        # promising something the real file does not is the exact failure this
        # generator exists to make impossible.
        "invariants": list(CONTRACT_INVARIANTS),
    },
    "run": {
        "date": SESSION,
        "type": "evening",
        "dry_run": False,
        "fixture": True,
        "universe": {"label": "data/symbols.txt (checked in)", "size": len(UNIVERSE)},
        # Two names in the file that have stopped printing, and a third the
        # feed returned no bar for at all, through the pipeline's own function
        # rather than a hand-typed block, so the shape and the threshold cannot
        # drift from what publish() writes. Chosen from the names no burst
        # uses, so the page is not told a name both burst and stopped printing.
        "stopped_printing": stopped_printing(SCAN_STATS),
        # A clean feed's count, which is what every night so far has had:
        # publish() writes this key on every run, and a fixture missing it
        # would describe a file the pipeline does not produce.
        "duplicate_bars": 0,
        # How much of the night was read, through the pipeline's own function
        # over the same stats block the stopped-printing names come from --
        # not a hand-typed set of counts that could disagree with them. A THIN
        # night, not a clean one: 228 asked, 227 answered, 225 measured,
        # because the two stopped-printing names are stale. So every surface
        # derived from this file appends the clause -- the page captions the
        # first cut "no 4% gain on the day; 3 of the 228 asked could not be
        # measured for this session" -- and history/ is the clean one. The
        # assertion beside SCAN_STATS is what stops that sentence drifting.
        "coverage": scan_coverage(SCAN_STATS),
        "bursts": BURSTS,
        "passed_gate": PASSED,
        "scored": len(candidates),
        "score_cap": CAP,
        "shortlist_size": 5,
        "gate": {"min_lynch_passes": 3, "total_checks": 6,
                 "vetoes": list(VETO_REASONS)},
        "rules": rules_fingerprint(),
        # `over` is how many names the percentile was drawn FROM -- those whose
        # session bar carried a readable, positive dollar volume. Not the same
        # count as run.coverage.measured, which is what the DETECTOR read and
        # answered about; they coincide on this night and diverge on any night
        # with a zero-volume bar or a detector error in it. A null floor beside
        # `over: 0` is a third sentence again -- no name's dollar volume could
        # be ranked.
        "liquidity": {"pctile": PCTILE, "floor": FLOOR, "over": MEASURED,
                      "refused": ILLIQUID},
        "scored_by": {"claude": by_src["claude"], "fallback": by_src["fallback"]},
        "model": MODEL,
        # The verdict word publish() stamps on every run, and the one key of
        # the run block this file did not write: a clean night's is "ok", and
        # its absence made the fixture a shape the pipeline cannot produce.
        # Found by deriving the parity rather than remembering it -- an
        # end-to-end run's own keys are the standard in
        # tests/test_pipeline.py -- because check_fixture_fresh.py compares
        # this file to the fixture it wrote and agrees with itself either way.
        "status": "ok",
        "errors": [],
    },
    "candidates": candidates,
    "gated_out": gated_out,
    "runs": runs,
    "evidence": EVIDENCE,
}

import sys
out = sys.argv[1]
# --- the assertions that make this fixture regenerable rather than hand-trusted ---
_uni = set(UNIVERSE)
for _row in candidates + gated_out:
    assert _row["ticker"] in _uni, f'{_row["ticker"]} is not in data/symbols.txt'
    assert _row["close"] > _CFG.min_price, f'{_row["ticker"]} close {_row["close"]} <= ${_CFG.min_price}'
    assert _row["volume"] > 0, f'{_row["ticker"]} has no volume'
    if "prev_volume" in _row:
        assert _row["volume"] >= _row["prev_volume"], f'{_row["ticker"]} volume < prev_volume'
    assert _row["gain_pct"] >= _CFG.min_gain_pct, f'{_row["ticker"]} gain {_row["gain_pct"]} < 4%'
assert len({r["ticker"] for r in candidates + gated_out}) == len(candidates) + len(gated_out)

# _remap rebinds every row to a different symbol and may lift its price, so any
# prose naming an absolute price would contradict the numbers shipped beside it.
import re as _re
for _row in candidates:
    _txt = " ".join(str(_row.get(k) or "") for k in ("reason", "key_risk"))
    for _m in _re.finditer(r"(?:under|sub-|below)\s*\$?(\d+(?:\.\d+)?)", _txt, _re.I):
        assert _row["close"] <= float(_m.group(1)), (
            f'{_row["ticker"]} close ${_row["close"]} contradicts its own text "{_m.group(0)}"')
print(f"fixture: {len(candidates)} scored + {len(gated_out)} gated, all in a {len(UNIVERSE)}-name universe, all clearing Layer-1")

with open(out, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
print(f"wrote {out}: {len(candidates)} candidates "
      f"({by_src['claude']} claude / {by_src['fallback']} fallback), "
      f"{len(gated_out)} gated out ({ILLIQUID} below the liquidity floor), {len(runs)} runs")
for c in candidates[:6]:
    print(f"  #{c['rank']:2d} {c['ticker']:5s} {c['score']:>4} {c['verdict']:5s} "
          f"{c['lynch']} {c['provenance']['source']}")
