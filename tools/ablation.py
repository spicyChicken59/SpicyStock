#!/usr/bin/env python3
"""The pre-registered ablation: six rule changes, each read against the
production mechanics over the retained publications.

Analysis only. It changes no rule, no threshold, no record and no ticket;
it writes nothing but its own two files; and it is not a backtest of the
live policy, because the chart reader is not run and the slot cap and the
cash budget are not applied. The spec
(``docs/input-truthfulness/2026-11-19-ablation/spec.json``) was committed
before this tool wrote a result, and the tool refuses a spec other than that
one.

The method is the frozen signal-outcome study (``tools/signal_outcomes.py``):
its loading, its bars, its basis check, its walk and its summary, over the
population ``tools/burst_trigger_comparison.population`` reads on the
spec's pinned ref. The study tickets every burst row; a variant is the set
of rows its gate admits (``admits()``), and the one variant that changes the
ticket itself (``stop_burst_low_only``) is the study run again with the stop
cascade narrowed.

    python tools/ablation.py            # write ablation.json and the report
    python tools/ablation.py --check    # refuse unless both are what this writes
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import admission, pipeline, plan, quality, record  # noqa: E402
from tools import burst_trigger_comparison as cmp  # noqa: E402
from tools import signal_outcomes as so  # noqa: E402

VERSION = "ablation-v1"
FOLDER = ROOT / "docs" / "input-truthfulness" / "2026-11-19-ablation"
SPEC = FOLDER / "spec.json"
#: the pre-registered spec's digest: a different spec is a different study
SPEC_SHA256 = "92711a426c241bf1c1580d069d5e3fddb7b0048aed1599726714069ff68db694"
OUT = FOLDER / "ablation.json"
REPORT = ROOT / "docs" / "input-truthfulness" / "2026-11-19-ablation.md"
VARIANTS = ("production", "no_regime_gate", "yellow_admits_a", "unscaled_thresholds", "admission_off",
            "stop_burst_low_only", "equal_checklist_weights")
#: each of the six scored letters weighted equally, ten points over six
EQUAL_WEIGHTS = {letter: round(sum(quality.WEIGHTS.values()) / len(quality.WEIGHTS), 4) for letter in quality.WEIGHTS}


class AblationError(RuntimeError):
    """The spec, the population or a publication could not be read as it must be."""


# --------------------------------------------------------------- the gates ---
def verdict(inputs: dict, thresholds: dict, breadth_rules: dict, *, scaled: bool = True) -> str | None:
    """``breadth.regime()``'s five rules over a record's own inputs: the scaled
    count thresholds the record printed, or, unscaled, the archived raw counts.
    None when the record carries no inputs to read."""
    try:
        down4, up4, up50 = inputs["down4"], inputs["up4"], inputs["up50_month"]
        r10, r5 = inputs["ratio_10d"], inputs["ratio_5d"]
        alarm = thresholds["down4_alarm"] if scaled else breadth_rules["down4_alarm"]
        hot = thresholds["up50_month_hot"] if scaled else breadth_rules["up50_month_hot"]
        red10, red5, yellow10 = thresholds["ratio_10d_red"], thresholds["ratio_5d_red"], thresholds["ratio_10d_yellow"]
    except (KeyError, TypeError):
        return None
    if down4 >= alarm or (r10 is not None and r10 < red10) or (r5 is not None and r5 < red5 and down4 > up4):
        return "red"
    if (r10 is not None and r10 < yellow10) or up50 > hot:
        return "yellow"
    return "green"


def light_grades(light: str | None, *, yellow_admits_a: bool = False) -> tuple:
    if light == "green" or (light == "yellow" and yellow_admits_a):
        return tuple(pipeline.TRADE_GRADES)
    if light == "yellow":
        return tuple(pipeline.YELLOW_GRADES)
    return ()


def equal_weight_grade(burst: dict) -> str | None:
    """The row's grade read again from its recorded checks with every scored
    letter weighted alike; ``quality.grade_of`` with the row's own A+ tally,
    vetoes and gate letters. None when the checks are not recorded."""
    q = burst.get("quality")
    checks = q.get("checks") if isinstance(q, dict) else None
    if not isinstance(checks, list) or not all(isinstance(c, dict) for c in checks):
        return None
    return quality_grade(checks, q.get("a_plus_count"), burst.get("vetoes"), EQUAL_WEIGHTS)


def quality_grade(checks: list, a_plus, vetoes, weights: dict) -> str | None:
    if not isinstance(a_plus, int):
        return None
    score = 0.0
    for c in checks:
        w = weights.get(c.get("letter"))
        if w is None:
            continue
        if c.get("passed"):
            score += w
        elif c.get("partial"):
            score += w / 2
    gates = all(any(c.get("letter") == g and c.get("passed") for c in checks) for g in quality.GRADE_GATE_LETTERS)
    return quality.grade_of(round(score, quality.RATIO_DECIMALS), a_plus, bool(vetoes), gates)


def admits(variant: str, burst: dict, night: dict) -> bool:
    """Whether ``variant``'s gate admits one burst row of one night."""
    if burst.get("vetoes"):
        return False
    grade = equal_weight_grade(burst) if variant == "equal_checklist_weights" else burst.get("grade_mechanical")
    if variant == "no_regime_gate":
        allowed = tuple(pipeline.TRADE_GRADES)
    elif variant == "unscaled_thresholds":
        allowed = light_grades(night["unscaled"])
    else:
        allowed = light_grades(night["light"], yellow_admits_a=variant == "yellow_admits_a")
    if grade not in allowed:
        return False
    return True if variant == "admission_off" else admission.admitted({**burst, "admission": admission.block(burst)})


# -------------------------------------------------------------- the study ---
def load_spec() -> dict:
    raw = SPEC.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SPEC_SHA256:
        raise AblationError("the spec is not the pre-registered one")
    spec = json.loads(raw)
    if [v["key"] for v in spec["variants"]] != list(VARIANTS):
        raise AblationError("the spec's variants are not this tool's")
    return spec


#: the reason a ticket the burst day's low cannot carry is withheld under ``stop_burst_low_only``
LOW_ONLY_REASON = "withheld: the burst day's low is not inside the stop line at the ticket's limit"


def low_only_ticket(production):
    """The ticket with the stop cascade narrowed to the burst day's low.
    ``plan.burst_limit`` and ``plan.burst_stop`` try the low first, so a
    production ticket whose stop is the low is the same ticket under the
    narrowed cascade, and one whose stop fell to the midpoint has no ticket."""
    def ticket(row: dict, account: plan.Account):
        p, bucket, reason = production(row, account)
        if p is not None and p.get("stop_basis") != "burst_low":
            return None, so.NO_TICKET, LOW_ONLY_REASON
        return p, bucket, reason
    return ticket


def run_study(publications: list[dict], study_spec: dict, *, stop_low_only: bool = False) -> dict:
    production = cmp.ticket_under(plan.BURST_TRIGGER_RULE)
    with mock.patch.object(so, "ticket", low_only_ticket(production) if stop_low_only else production):
        return so.study(publications, study_spec)


def nights_of(publications: list[dict]) -> dict:
    """Each ticketed publication's light as recorded, the light read again
    from its inputs (which must give the recorded one), and unscaled."""
    out = {}
    for p in so.first_publications(publications):
        data = p["data"]
        regime = data["breadth"]["regime"]
        inputs, thresholds = regime.get("inputs"), regime.get("thresholds")
        rules = (data.get("rules") or {}).get("breadth") or {}
        again = verdict(inputs, thresholds, rules) if inputs and thresholds else None
        out[p["commit"][:8]] = {"session": p["session"], "light": regime["verdict"], "read_again": again,
                                "unscaled": verdict(inputs, thresholds, rules, scaled=False) if inputs and thresholds else None}
    return out


def summary_of(rows: list[dict], spec: dict) -> dict:
    s = so._stratum_summary(rows, spec)
    settled = s["settled"]
    return {"admitted": len(rows), "tickets": sum(1 for r in rows if r["ticket"] is not None),
            "withheld": sum(1 for r in rows if r["bucket"] == so.NO_TICKET),
            "buckets": {k: v for k, v in s["buckets"].items() if v},
            "uncertain_by_reason": dict(sorted(Counter(r.get("uncertainty") or "unnamed" for r in rows
                                                       if r["bucket"] == record.UNCERTAIN).items())),
            "settled": settled,
            "win_rate": round(settled["wins"] / settled["n"], 3) if settled["n"] else None,
            "readable": settled["n"] >= record.SCORECARD_MIN_PLANS,
            "night_bootstrap": s["night_bootstrap"],
            "costs_per_side_bps": s["costs_per_side_bps"]}


def build() -> dict:
    spec = load_spec()
    base = json.loads((ROOT / spec["base_spec"]).read_text())
    entries = cmp.population(spec["ref"], base)
    study_spec = cmp.spec_of({**base, "cost_bps_per_side": spec["metrics"]["cost_bps_per_side"]}, entries)
    publications = so.load_publications(study_spec)
    nights = nights_of(publications)
    disagree = sorted(k for k, n in nights.items() if n["read_again"] not in (None, n["light"]))
    if disagree:
        raise AblationError("the regime read again disagrees with the recorded light for " + ", ".join(disagree))
    bursts = {(p["commit"][:8], b["ticker"]): b for p in so.first_publications(publications)
              for b in p["data"].get("bursts", [])}
    base_rows = run_study(publications, study_spec)["rows"]
    low_rows = run_study(publications, study_spec, stop_low_only=True)["rows"]
    out = {}
    for variant in VARIANTS:
        rows = low_rows if variant == "stop_burst_low_only" else base_rows
        chosen = [r for r in rows if admits("production" if variant == "stop_burst_low_only" else variant,
                                            bursts[(r["publication"], r["ticker"])], nights[r["publication"]])]
        out[variant] = summary_of(chosen, study_spec)
    regraded = [b for b in bursts.values() if not b.get("vetoes")]
    same = sum(1 for b in regraded
               if quality_grade(b["quality"]["checks"], b["quality"].get("a_plus_count"), b.get("vetoes"),
                                quality.WEIGHTS) == b.get("grade_mechanical"))
    lights = Counter(n["light"] for n in nights.values())
    unscaled = Counter(n["unscaled"] for n in nights.values())
    return {"version": VERSION, "spec": SPEC.relative_to(ROOT).as_posix(), "spec_sha256": SPEC_SHA256,
            "ref": spec["ref"], "publications": len(publications), "nights": len(nights),
            "first_session": min(n["session"] for n in nights.values()),
            "newest_session": max(p["session"] for p in publications),
            "rows": len(base_rows),
            "lights": {k: lights[k] for k in ("green", "yellow", "red") if lights[k]},
            "lights_unscaled": {k: unscaled[k] for k in ("green", "yellow", "red") if unscaled[k]},
            "regime_read_again": {"nights": len(nights), "agree": sum(n["read_again"] == n["light"] for n in nights.values()),
                                  "no_inputs": sum(n["read_again"] is None for n in nights.values())},
            "grades_read_again": {"rows": len(regraded), "reproduced": same,
                                  "changed_by_equal_weights": sum(1 for b in regraded
                                                                  if equal_weight_grade(b) != b.get("grade_mechanical"))},
            "equal_weight": EQUAL_WEIGHTS["L"],
            "min_settled_for_a_rate": record.SCORECARD_MIN_PLANS,
            "variants": out}


# -------------------------------------------------------------- the report ---
def _r(v) -> str:
    return "—" if v is None else f"{v:+.3f}".replace("-", "−")


def _interval(b) -> str:
    return "—" if not b else f"[{_r(b['ci95'][0])}, {_r(b['ci95'][1])}] over {b['nights']} nights"


def _lights(counts: dict) -> str:
    return ", ".join(f"{counts[k]} {k}" for k in ("green", "yellow", "red") if k in counts)


def render(result: dict) -> str:
    """The dated report, every figure read off ``result`` as its file holds it."""
    result = json.loads(encoded(result))
    spec = json.loads(SPEC.read_text())
    change = {v["key"]: v["change"] for v in spec["variants"]}
    v = result["variants"]
    lines = [
        "# The ablation, 19 November 2026",
        "",
        f"Pre-registered in [`{result['spec']}`]({Path(result['spec']).relative_to('docs/input-truthfulness').as_posix()}) "
        f"(SHA-256 `{result['spec_sha256'][:12]}…`) before any result was written, and read by "
        f"`tools/ablation.py` over {result['publications']} publications, the first of each of "
        f"{result['nights']} sessions ticketed ({result['first_session']} to {result['newest_session']}), "
        f"{result['rows']:,} burst rows, on the pinned ref `{result['ref'][:8]}`.",
        "",
        "**Analysis only.** No rule changes here and none is promoted. The chart reader is not run, and the slot cap, "
        "the cash budget and the event registry are not applied: every admitted row stands on its own, as in the "
        "frozen signal-outcome study whose walk this is. Every night was read with its later bars already public, and "
        "the variants share most of their rows, so the differences between them are not independent tests.",
        "",
        f"The lights: {_lights(result['lights'])}; read again unscaled, "
        f"{_lights(result['lights_unscaled'])}. The regime read again from each "
        f"record's own inputs gives its recorded light on {result['regime_read_again']['agree']} of "
        f"{result['regime_read_again']['nights']} nights ({result['regime_read_again']['no_inputs']} carry no inputs). "
        f"The checklist's own weights reproduce {result['grades_read_again']['reproduced']:,} of "
        f"{result['grades_read_again']['rows']:,} unvetoed rows' recorded grades; equal weights give each scored "
        f"letter {result['equal_weight']:g} points and change "
        f"{result['grades_read_again']['changed_by_equal_weights']:,} of those grades.",
        "",
        "| variant | admitted | tickets | withheld | settled | win rate | mean R | median R | mean of night means | 95% night interval | uncertain |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for key in VARIANTS:
        s = v[key]
        st = s["settled"]
        nb = s["night_bootstrap"]
        lines.append(f"| `{key}` | {s['admitted']:,} | {s['tickets']:,} | {s['withheld']:,} | {st['n']:,} | "
                     f"{'—' if s['win_rate'] is None else format(s['win_rate'], '.3f')} | {_r(st['mean_r'])} | "
                     f"{_r(st['median_r'])} | {_r(nb['mean_of_night_means'] if nb else None)} | {_interval(nb)} | "
                     f"{s['buckets'].get(record.UNCERTAIN, 0):,} |")
    lines += ["", f"A rate is read only at {result['min_settled_for_a_rate']} settled tickets or more "
              "(`record.SCORECARD_MIN_PLANS`); an interval that includes zero establishes no sign.", "",
              "## Each variant", ""]
    for key in VARIANTS:
        s = v[key]
        costs = "; ".join(f"{bps} bps a side {_r(c['mean_r'])} over {c['n']:,}"
                          for bps, c in sorted(s["costs_per_side_bps"].items(), key=lambda kv: int(kv[0])))
        reasons = ", ".join(f"{k} {n:,}" for k, n in s["uncertain_by_reason"].items()) or "none"
        buckets = ", ".join(f"{k} {s['buckets'][k]:,}" for k in so.BUCKETS if k in s["buckets"])
        lines += [f"**`{key}`** — {change[key]}.", "",
                  f"Buckets: {buckets}. Uncertain by reason: {reasons}. Settled: {s['settled']['wins']:,} wins, "
                  f"{s['settled']['losses']:,} losses, {s['settled']['breakeven']:,} even; mean R after costs: {costs}."
                  + ("" if s["readable"] else " Under the floor: no rate is read."), ""]
    lines += ["## What it does not establish", "",
              "An edge for any variant, or a reason to adopt one. The reader, which lowers most A-band names on a live "
              "night, is not run; GREEN nights are few or none in this population; and every population here was "
              "chosen before these numbers, which is the only thing the spec makes true.", ""]
    return "\n".join(lines)


def encoded(result: dict) -> str:
    return json.dumps(result, indent=1, sort_keys=True) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="refuse unless both committed files are what this writes")
    args = parser.parse_args(argv)
    try:
        result = build()
    except (AblationError, cmp.ComparisonError, so.StudyError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    text, report = encoded(result), render(result)
    if args.check:
        stale = [p.relative_to(ROOT).as_posix() for p, want in ((OUT, text), (REPORT, report))
                 if not p.exists() or p.read_text() != want]
        if stale:
            print("stale: " + ", ".join(stale), file=sys.stderr)
            return 1
        print("current: ablation.json and the report are what the tool writes")
        return 0
    OUT.write_text(text)
    REPORT.write_text(report)
    print(f"wrote {OUT.relative_to(ROOT)} and {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
