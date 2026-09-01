"""Hand-authored fixture for docs/data.json.

Every 2LYNCH pass flag is COMPUTED from its measurement using the same
thresholds src/lynch.py applies, and every fallback score is computed with
src/scorer.py's own formula, so the fixture cannot disagree with the code it
stands in for.
"""
import collections, json, pathlib, sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
from src.scanner import ScanConfig            # the real floors, not a copy
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
        if d["vol"] <= _CFG.min_today_volume:
            d["vol"] = _CFG.min_today_volume + 1_200_000 + i * 137_000
        if d["prev"] >= d["vol"]:
            d["prev"] = int(d["vol"] * 0.42)
        out.append(type(spec)(**d))
    return out


SESSION = "2026-09-01"
MODEL = "claude-sonnet-4-6"

LABELS = {
    "2": "first or second burst",
    "L": "linear prior move",
    "Y": "young trend",
    "N": "narrow consolidation",
    "C": "calm pre-burst day",
    "H": "closed near the high",
}

def lynch(prior_bursts, r2, run_up, ext, recent_range, tightness, d1_move, d1_range, d1_vol, close_pos):
    """Mirrors src/lynch.py: same thresholds, same value strings."""
    return [
        {"code": "2", "label": LABELS["2"], "pass": prior_bursts <= 1,
         "value": f"{prior_bursts} prior 4% bursts in last 20 days"},
        {"code": "L", "label": LABELS["L"], "pass": r2 >= 0.55,
         "value": f"R²={r2:.2f} over prior 30 days"},
        {"code": "Y", "label": LABELS["Y"], "pass": run_up < 25.0 and ext < 15.0,
         "value": f"+{run_up:.1f}% past month, {ext:+.1f}% vs 20SMA"},
        {"code": "N", "label": LABELS["N"], "pass": tightness <= 1.0,
         "value": f"pre-burst range {recent_range:.1f}%/day = {tightness:.2f}x its norm"},
        {"code": "C", "label": LABELS["C"], "pass": d1_move < 2.0 and d1_vol < 1.2,
         "value": f"prior day {d1_move:.1f}% move, {d1_range:.1f}% range, {d1_vol:.2f}x volume"},
        {"code": "H", "label": LABELS["H"], "pass": close_pos >= 0.70,
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
      "thin float, wide spreads", "claude", False,
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
      "under $4, prone to fades", "claude", True,
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
      "Sub-$4 name with a 9% pop on no base; historically these give it all back within days.",
      "sub-$4, no base", "claude", True,
      (4, 0.28, 11.2, 5.8, 9.1, 1.74, 1.7, 4.6, 1.09, 0.75),
      (-71.8, 14.2, -8.4, -34.2)),
]

SPEC = _remap(SPEC, 0)


def build_candidate(s):
    detail = lynch(*s.lm)
    passes = sum(1 for d in detail if d["pass"])
    assert passes >= 3, f"{s.t} would have been gated out at {passes}/6"
    if s.src == "fallback":
        # src/scorer.py's own fallback formula, verbatim
        score = round(passes / len(detail) * 10, 1)
        verdict = "B" if score >= 6 else "skip"
        reason = f"AI unavailable; checklist score {passes}/{len(detail)}."
        risk = "not AI-reviewed"
        prov = {"source": "fallback", "model": None, "chart_seen": False,
                "error": "anthropic.APIStatusError: 529 overloaded_error (3 retries exhausted)"}
    else:
        score, verdict, reason, risk = s.score, s.verdict, s.reason, s.risk
        prov = {"source": "claude", "model": MODEL, "chart_seen": s.chart, "error": None}
    off_hi, abv_lo, p3, p6 = s.ctx
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
                    "perf_3mo_pct": p3, "perf_6mo_pct": p6},
        "forward_returns": {"d1": None, "d3": None, "d5": None, "as_of": None},
    }

candidates = [build_candidate(s) for s in SPEC]
candidates.sort(key=lambda c: c["score"], reverse=True)
for i, c in enumerate(candidates, 1):
    c["rank"] = i

# --- what did not get scored ------------------------------------------------
# 47 bursts - 25 scored = 22. Sixteen failed the >=3/6 gate; six cleared it but
# fell outside MAX_TO_SCORE, which sorts on (passes, gain_pct) descending.
G = collections.namedtuple("G", "t close gain vol prev passes reason")
GATED = [
    G("SOUN",  8.94,  5.12, 14208700,  6104300, 2, "lynch_gate"),
    G("MARA",  19.83, 4.71, 28417200, 13092400, 2, "lynch_gate"),
    G("RIOT",  14.26, 6.38, 31844100, 14208900, 2, "lynch_gate"),
    G("CLSK",  11.07, 4.29, 22193600, 10847100, 1, "lynch_gate"),
    G("AI",    27.61, 5.84,  9214800,  4108600, 2, "lynch_gate"),
    G("BBAI",   6.42, 8.13, 18774200,  7442800, 1, "lynch_gate"),
    G("VRT",   142.9, 4.06,  7118400,  3402700, 2, "lynch_gate"),
    G("SMCI",  38.74, 4.92, 26094300, 11884200, 2, "lynch_gate"),
    G("APLD",  16.38, 7.44, 13627900,  5814300, 1, "lynch_gate"),
    G("NNE",   34.12, 6.71,  6483100,  2914700, 2, "lynch_gate"),
    G("CRML",   4.18, 11.62, 9847300,  3218400, 0, "lynch_gate"),
    G("MVIS",   1.94, 9.88, 21094600,  8412700, 0, "lynch_gate"),
    G("GRRR",   3.47, 14.21, 7482100,  2104800, 0, "lynch_gate"),
    G("SERV",  12.83, 5.47, 10428300,  4816200, 2, "lynch_gate"),
    G("LTBR",  17.29, 4.83,  5218700,  2408100, 2, "lynch_gate"),
    G("KTOS",  41.62, 4.11,  6104200,  2884300, 2, "lynch_gate"),
    # cleared the gate at 3/6 but ranked below the top 25 on (passes, gain_pct)
    G("EOSE",   7.83, 4.07, 12048600,  5417300, 3, "score_cap"),
    G("MP",     48.16, 4.05, 8114700,  3982400, 3, "score_cap"),
    G("ASTS",   61.94, 4.04, 11384200, 5208900, 3, "score_cap"),
    G("VSAT",   28.37, 4.03,  4917200, 2314600, 3, "score_cap"),
    G("NPWR",    9.16, 4.02,  6742800, 3108400, 3, "score_cap"),
    G("TMC",     4.71, 4.01, 15208400, 7014900, 3, "score_cap"),
]
GATED = _remap(GATED, len(SPEC))

gated_out = [{
    "ticker": g.t, "date": SESSION, "close": g.close, "gain_pct": g.gain,
    "volume": g.vol, "volume_ratio": round(g.vol / g.prev, 2),
    "lynch": f"{g.passes}/6", "lynch_passes": g.passes, "reason": g.reason,
} for g in GATED]

# every 3/6 score_cap row must sit below the weakest scored 3/6 row on gain_pct
worst_scored_3 = min((c["gain_pct"] for c in candidates if c["lynch_passes"] == 3), default=99)
for g in gated_out:
    if g["reason"] == "score_cap":
        assert g["gain_pct"] < worst_scored_3, g["ticker"]

BURSTS = 47
PASSED = 31
CAP = 25
assert len(candidates) + len(gated_out) == BURSTS
assert len(candidates) == CAP
assert PASSED - CAP == sum(1 for g in gated_out if g["reason"] == "score_cap")
assert BURSTS - PASSED == sum(1 for g in gated_out if g["reason"] == "lynch_gate")

by_src = collections.Counter(c["provenance"]["source"] for c in candidates)

runs = [
    {"date": SESSION, "type": "evening", "bursts": BURSTS, "passed_gate": PASSED,
     "scored": len(candidates), "shortlist_size": 5, "top_score": candidates[0]["score"],
     "fallbacks": by_src["fallback"],
     "forward_returns": {"d1": None, "d3": None, "d5": None, "n": 0}},
    {"date": "2026-08-31", "type": "evening", "bursts": 39, "passed_gate": 21, "scored": 21,
     "shortlist_size": 5, "top_score": 8.4, "fallbacks": 0,
     "forward_returns": {"d1": 1.12, "d3": None, "d5": None, "n": 21}},
    {"date": "2026-08-28", "type": "evening", "bursts": 52, "passed_gate": 28, "scored": 25,
     "shortlist_size": 5, "top_score": 9.1, "fallbacks": 2,
     "forward_returns": {"d1": -0.63, "d3": None, "d5": None, "n": 25}},
    {"date": "2026-08-27", "type": "evening", "bursts": 44, "passed_gate": 24, "scored": 24,
     "shortlist_size": 5, "top_score": 8.8, "fallbacks": 0,
     "forward_returns": {"d1": 2.07, "d3": 1.44, "d5": None, "n": 24}},
    {"date": "2026-08-26", "type": "evening", "bursts": 33, "passed_gate": 18, "scored": 18,
     "shortlist_size": 5, "top_score": 7.9, "fallbacks": 1,
     "forward_returns": {"d1": 0.88, "d3": 2.31, "d5": None, "n": 18}},
    {"date": "2026-08-25", "type": "evening", "bursts": 38, "passed_gate": 22, "scored": 22,
     "shortlist_size": 5, "top_score": 9.0, "fallbacks": 0,
     "forward_returns": {"d1": 1.84, "d3": 2.97, "d5": -0.42, "n": 22}},
]

data = {
    "schema_version": 1,
    "app": "SpicyStock",
    "generated": "2026-09-01T22:14:07Z",
    "_contract": {
        "about": "docs/data.json will be written by src/pipeline.py (step 9) and is read by docs/index.html at runtime. Today it is a hand-authored fixture from tools/make_fixture.py; run.fixture is true. This block is documentation, not data; consumers ignore it.",
        "documented_in": "README.md, 'The dashboard contract'",
        "invariants": [
            "candidates holds EVERY scored candidate, ranked by score descending, and is never truncated: len(candidates) == run.scored. The top run.shortlist_size of them are the shortlist that went out by email.",
            "run.scored + len(gated_out) == run.bursts. Nothing a scan found may vanish without appearing in one of the two lists.",
            "Every candidate carries provenance.source: 'claude' when the model actually returned a score, 'fallback' when the offline checklist produced it. A fallback is never labelled claude.",
            "provenance.chart_seen is true only when the scoring model actually received the chart image.",
            "forward_returns and runs[].forward_returns are null until the sessions exist. Absent is null, never 0 and never a string.",
            "chart is a path relative to docs/, or null when the render failed. The file may legitimately not exist yet.",
            "Numbers are numbers or null. No 'n/a' strings.",
        ],
    },
    "run": {
        "date": SESSION,
        "type": "evening",
        "dry_run": False,
        "fixture": True,
        "universe": {"label": "data/symbols.txt (checked in)", "size": len(UNIVERSE)},
        "bursts": BURSTS,
        "passed_gate": PASSED,
        "scored": len(candidates),
        "score_cap": CAP,
        "shortlist_size": 5,
        "gate": {"min_lynch_passes": 3, "total_checks": 6},
        "scored_by": {"claude": by_src["claude"], "fallback": by_src["fallback"]},
        "model": MODEL,
        "errors": [],
    },
    "candidates": candidates,
    "gated_out": gated_out,
    "runs": runs,
}

import sys
out = sys.argv[1]
# --- the assertions that make this fixture regenerable rather than hand-trusted ---
_uni = set(UNIVERSE)
for _row in candidates + gated_out:
    assert _row["ticker"] in _uni, f'{_row["ticker"]} is not in data/symbols.txt'
    assert _row["close"] > _CFG.min_price, f'{_row["ticker"]} close {_row["close"]} <= ${_CFG.min_price}'
    assert _row["volume"] > _CFG.min_today_volume, f'{_row["ticker"]} volume {_row["volume"]:,} <= floor'
    if "prev_volume" in _row:
        assert _row["volume"] >= _row["prev_volume"], f'{_row["ticker"]} volume < prev_volume'
    assert _row["gain_pct"] >= _CFG.min_gain_pct, f'{_row["ticker"]} gain {_row["gain_pct"]} < 4%'
assert len({r["ticker"] for r in candidates + gated_out}) == len(candidates) + len(gated_out)
print(f"fixture: {len(candidates)} scored + {len(gated_out)} gated, all in a {len(UNIVERSE)}-name universe, all clearing Layer-1")

with open(out, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
print(f"wrote {out}: {len(candidates)} candidates "
      f"({by_src['claude']} claude / {by_src['fallback']} fallback), "
      f"{len(gated_out)} gated out, {len(runs)} runs")
for c in candidates[:6]:
    print(f"  #{c['rank']:2d} {c['ticker']:5s} {c['score']:>4} {c['verdict']:5s} "
          f"{c['lynch']} {c['provenance']['source']}")
