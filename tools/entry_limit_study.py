"""Read-only comparison of two entry ceilings over an archived record.

The question CLAUDE.md deferred three times -- his +4% ceiling and his 4%
stop line cannot both hold at the ticket's limit, so nearly every real burst
was withheld -- has been decided: the constrained ceiling

    limit = min(close + ENTRY_ABOVE_PCT, floor_to_cents(stop / (1 - MAX_STOP_PCT/100)))

is production (``plan.burst_limit``). This tool outlived that decision by
changing sides, not by comparing production with itself. It now reads a
record that has already been written and puts THREE readings beside each
other, per burst:

* **fixed** -- the retired ceiling, the close plus ``ENTRY_ABOVE_PCT`` with
  the stop cascade judged there. It is no longer in ``src/``, so the study
  carries it: this is the counterfactual column, and the only place that
  arithmetic still exists.
* **production** -- ``plan.burst_plan()`` itself, unchanged and uncalled-out.
  ``verify()`` reproduces every plan the record carries down to the share
  count, the action and the money, so this column IS the run's own answer.
* **oracle** -- the constrained ceiling re-derived HERE from the spec, over
  ``plan.burst_stop``'s candidates in their order, and held against what
  production wrote. Two implementations of one rule is a defect in ``src/``;
  as an independent check of an adopted rule against the words it was
  adopted under, it is the point. A disagreement raises rather than prints.

The synthetic ``max_stop`` fallback -- a level the bar does not support -- is
never read by the oracle, so nothing here can manufacture eligibility. A
ticket is admitted only where ``stop < trigger < limit`` still holds at the
rounded ceiling: strictly under and strictly over, because a limit at the
buy stop is a ticket with no band to fill in, which production withholds.

It writes nothing. It changes no rule, no record, no regime, no ticket and no
scorecard, and it is not a backtest: it counts eligibility under two ceilings
over one archived session and reports what the narrower limit carried with
it. No forward return is read, computed or implied.

    python tools/entry_limit_study.py [record.json ...] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import pipeline, plan  # noqa: E402


#: The candidates the oracle may read, in ``plan.burst_stop``'s own order.
#: ``plan.STOP_BASES`` ends with the synthetic fallback; this is that tuple
#: with the fallback dropped, so a new structural basis appears here by
#: adding it there and nothing else.
STRUCTURAL_BASES = tuple(b for b in plan.STOP_BASES if b != "max_stop")
#: The synthetic level the oracle must never read. Named so the refusal is
#: a rule with a name and not an omission.
SYNTHETIC_BASIS = "max_stop"
#: What the ceiling is rounded to. The order's limit is a price.
CEILING_DECIMALS = plan.CENTS
#: Of ``plan.CUT_KINDS`` only these two are the cash budget refusing a ticket
#: it cannot fit. ``withheld`` is the STOP RULE's own refusal, carrying
#: ``burst_plan``'s reason verbatim, and counting it here would report one
#: burst under two gates; ``no_new_longs`` is the regime and ``no_shares`` is
#: the sizing. Each is reported under its own heading instead.
BUDGET_CUT_KINDS = ("slot_cap", "equity")
#: A band this thin is a ticket that can only fill within a rounding error of
#: its own trigger. Reported, never a rule: production refuses only a band of
#: nothing at all.
BAND_THIN_PCT = 0.5
#: How many of each kind of case the report prints.
EXAMPLES = 5
EXAMPLES_SHOWN, EXAMPLES_REFUSED, EXAMPLES_MOVED = 3, 2, 2


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" + ("" if n == 1 else "s")


def floor_to_cents(value: float) -> float:
    """A ceiling rounded DOWN, so rounding can never widen the stop past the
    line it was derived from."""
    scale = 10 ** CEILING_DECIMALS
    return math.floor(value * scale + 1e-9) / scale


def structural_candidates(low: float, high: float) -> list[tuple[str, float]]:
    """The structural stops ``plan.burst_stop`` would try, in its order, off
    the same cent-rounded bar it reads -- derived HERE rather than read from
    ``plan.stop_candidates()``, because this is the oracle and an oracle that
    called the code it checks would check nothing. The record carries raw
    four-decimal lows for some names; ``burst_plan`` rounds the bar once on
    the way in, and a study that skipped that step proposed stops a cent away
    from the ones the run would write. A basis named in ``plan.STOP_BASES``
    that this has no price for is refused out loud."""
    low, high = plan._price(low, "low"), plan._price(high, "high")
    prices = {"burst_low": low, "half_range": plan._money((low + high) / 2)}
    unknown = [b for b in STRUCTURAL_BASES if b not in prices]
    if unknown:
        raise ValueError(f"plan.STOP_BASES names structural bases this study cannot price: {unknown}")
    return [(basis, prices[basis]) for basis in STRUCTURAL_BASES]


def constrained_ceiling(close: float, low: float, high: float) -> dict[str, Any] | None:
    """THE ORACLE: the constrained ticket for one burst bar, re-derived from
    the spec, or a refusal when no structural stop supports one. ``close`` is
    the buy stop (the trigger) as ``burst_plan`` sets it, and the bar is
    cent-rounded once, as ``burst_plan`` rounds it. The band must be strictly
    open -- ``stop < trigger < limit`` -- because a limit AT the buy stop is a
    ticket with no room to fill in, which production withholds."""
    close = plan._price(close, "close")
    trigger = close
    fixed = plan._at_pct(close, plan.ENTRY_ABOVE_PCT)
    tried: list[dict[str, Any]] = []
    for basis, stop in structural_candidates(low, high):
        cap = floor_to_cents(stop / (1 - plan.MAX_STOP_PCT / 100.0))
        limit = min(fixed, cap)
        ok = stop < trigger < limit
        tried.append({"basis": basis, "stop": stop, "cap": cap, "limit": limit, "admitted": ok})
        if ok:
            return {
                "basis": basis, "stop": stop, "limit": limit, "fixed_limit": fixed,
                "trigger": trigger, "narrowed": limit < fixed,
                "stop_pct_at_limit": plan._pct(100 * (limit - stop) / limit),
                "band_pct": plan._pct(100 * (limit / close - 1)),
                "tried": tried,
            }
    return {"basis": None, "tried": tried, "fixed_limit": fixed, "trigger": trigger} if tried else None


def production_matches(oracle: Mapping[str, Any], row: Mapping[str, Any], now: Mapping[str, Any]) -> str | None:
    """Why production and the oracle disagree about this bar, or None. The
    oracle's limit, stop and basis must be what ``plan.burst_limit()`` names
    AND what ``plan.burst_plan()`` wrote, and the cascade run at that limit
    must reach the same stop inside his line. A disagreement means the
    adopted rule is not the rule it was adopted as, and the study raises."""
    got = plan.burst_limit(row["close"], row["low"], row["high"])
    admitted = oracle["basis"] is not None
    if bool(got["admitted"]) != admitted:
        return f"oracle admits {admitted}, plan.burst_limit admits {got['admitted']}"
    if not admitted:
        return None if not now["eligible"] else "oracle refuses a ticket the run published"
    for field, mine in (("limit", oracle["limit"]), ("stop", oracle["stop"]), ("stop_basis", oracle["basis"])):
        if got[field] != mine:
            return f"oracle {field} {mine!r} != plan.burst_limit {got[field]!r}"
        if now[field] != mine:
            return f"oracle {field} {mine!r} != the published plan's {now[field]!r}"
    cascade = plan.burst_stop(oracle["limit"], row["low"], row["high"], trigger=oracle["trigger"])
    if (cascade["stop_basis"] != oracle["basis"] or cascade["stop"] != oracle["stop"]
            or cascade["stop_pct"] > plan.MAX_STOP_PCT):
        return (f"the cascade at {oracle['limit']} reaches {cascade['stop_basis']} {cascade['stop']} "
                f"at {cascade['stop_pct']}%, not {oracle['basis']} {oracle['stop']}")
    return None


def fixed_ceiling_plan(row: dict, multiplier: float) -> dict[str, Any]:
    """THE COUNTERFACTUAL: the ticket the retired fixed ceiling would write.
    The limit is the close plus ``ENTRY_ABOVE_PCT`` whatever the bar says; the
    stop cascade, the eligibility and the shares are judged there, which is
    what ``burst_plan`` did before ``burst_limit`` existed. This arithmetic is
    no longer in ``src/``, so it lives here or nowhere."""
    close = plan._price(row["close"], "close")
    limit = plan._at_pct(close, plan.ENTRY_ABOVE_PCT)
    block = plan.burst_stop(limit, row["low"], row["high"], trigger=close)
    eligible = block["stop_basis"] != SYNTHETIC_BASIS
    found = plan.hazards(row.get("gain_pct") or 0.0, row.get("extension_pct"))
    hazard = min([h["multiplier"] for h in found], default=1.0)
    stop_multiplier, _ = plan.stop_risk(block["stop_pct"])
    sizing = plan.size(limit, block["stop"], plan.Account(), multiplier * hazard * stop_multiplier)
    full = plan.size(limit, block["stop"], plan.Account(), hazard * stop_multiplier)
    return {"limit": limit, "stop": block["stop"], "basis": block["stop_basis"], "eligible": eligible,
            "stop_pct": block["stop_pct"], "shares": sizing.shares, "shares_at_full_size": full.shares,
            "risk_usd": sizing.risk_usd, "risk_usd_at_full_size": full.risk_usd}


def usable_bar(row: dict) -> str | None:
    """Why this row cannot be read as a bar, or None when it can -- the prices,
    and the other fields ``burst_plan`` and ``hazards`` validate. A row the
    pipeline itself only logs and skips (``make_plans`` catches ValueError)
    must land in the study's 'missing inputs' class, not end the run."""
    if not isinstance(row.get("ticker"), str) or not row["ticker"].strip():
        return f"ticker must be a non-empty string, got {row.get('ticker')!r}"
    try:
        values = {k: plan._price(row[k], k) for k in ("close", "low", "high", "open", "prev_close")}
        plan._number(row.get("gain_pct") or 0.0, "gain_pct")
        if row.get("extension_pct") is not None:
            plan._number(row["extension_pct"], "extension_pct")
    except (KeyError, TypeError, ValueError) as exc:
        return str(exc)[:80]
    low, high, close, open_ = values["low"], values["high"], values["close"], values["open"]
    if low > high or not (low <= close <= high) or not (low <= open_ <= high):
        return f"open {open_} and close {close} outside the bar {low}-{high}"
    return None


def current_plan(row: dict, multiplier: float) -> dict:
    """What the pipeline writes today for this bar, through the production
    function, at the regime's OWN size multiplier -- so the share count is the
    run's too and ``verify()`` can hold it to the record. Eligibility and the
    prices do not depend on the multiplier; the shares do."""
    return plan.burst_plan(
        ticker=row["ticker"], close=row["close"], low=row["low"], high=row["high"],
        open_=row["open"], prev_close=row["prev_close"], gain_pct=row.get("gain_pct") or 0.0,
        account=plan.Account(), size_multiplier=multiplier,
        scan="dollar" if row.get("scan") == "dollar" else "4pct",
        extension_pct=row.get("extension_pct"),
    )


def admitted_grades(verdict: str | None) -> tuple[str, ...]:
    """The grades the regime admits, read off the pipeline."""
    if verdict == "red":
        return ()
    return pipeline.YELLOW_GRADES if verdict == "yellow" else pipeline.TRADE_GRADES


def study(record: dict) -> dict[str, Any]:
    """The comparison over one record."""
    bursts = record.get("bursts") or []
    regime = ((record.get("breadth") or {}).get("regime") or {})
    verdict = regime.get("verdict")
    admits = admitted_grades(verdict)
    budget = record.get("cash_budget") or {}
    cut = {c.get("ticker"): c.get("kind") for c in (budget.get("cut") or [])}
    multiplier = float(regime.get("size_multiplier") or 0.0) if "size_multiplier" in regime else 1.0

    rows: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    for row in bursts:
        why = usable_bar(row)
        if why:
            missing.append({"ticker": row.get("ticker"), "why": why})
            continue
        try:
            now = current_plan(row, multiplier)
            # and the same ticket at full size, so the two columns can be
            # compared on a night whose regime sized everything at zero
            now_full = current_plan(row, 1.0)
            fixed = fixed_ceiling_plan(row, multiplier)
        except (ValueError, KeyError) as exc:   # the pipeline logs and skips; so does this
            missing.append({"ticker": row.get("ticker"), "why": str(exc)[:80]})
            continue
        oracle = constrained_ceiling(row["close"], row["low"], row["high"])
        disagreement = production_matches(oracle, row, now)
        if disagreement:
            raise AssertionError(f"{row['ticker']}: {disagreement}; the adopted rule is not the rule "
                                 f"this study re-derives from the spec")
        rows.append({
            "ticker": row["ticker"], "grade": row.get("grade"), "vetoed": bool(row.get("vetoes")),
            "admitted_by_regime": row.get("grade") in admits and not row.get("vetoes"),
            "cut_kind": cut.get(row["ticker"]),
            "close": row["close"], "low": row["low"], "high": row["high"],
            "fixed": fixed,
            "production": {"limit": now["limit"], "stop": now["stop"], "basis": now["stop_basis"],
                           "limit_basis": now["limit_basis"], "narrowed": now["limit_narrowed"],
                           "day2_spent_above": now["day2_spent_above"], "refusal": now["ticket_refusal"],
                           "eligible": now["eligible"], "shares": now["shares"],
                           "shares_at_full_size": now_full["shares"], "risk_usd": now["risk_usd"],
                           "risk_usd_at_full_size": now_full["risk_usd"],
                           "stop_pct": now["stop_pct"], "action": now["action"],
                           "planned_entry": now["planned_entry"], "planned_entry_capped": now["planned_entry_capped"],
                           "band_pct": plan._pct(100 * (now["limit"] / plan._price(row["close"], "close") - 1))},
        })

    counts = {
        "bursts": len(bursts),
        "missing_inputs": len(missing),
        "candidate_coverage": len(rows),
        "fixed_eligible": sum(1 for r in rows if r["fixed"]["eligible"]),
        "fixed_stop_rule_rejections": sum(1 for r in rows if not r["fixed"]["eligible"]),
        "production_eligible": sum(1 for r in rows if r["production"]["eligible"]),
        "production_rejections": sum(1 for r in rows if not r["production"]["eligible"]),
        "rescued": sum(1 for r in rows if r["production"]["eligible"] and not r["fixed"]["eligible"]),
        # a plan the account cannot size to a whole share is not a ticket:
        # production writes no_order and the budget cuts it as no_shares
        "rescued_with_an_order": sum(1 for r in rows if r["production"]["eligible"] and not r["fixed"]["eligible"]
                                     and (r["production"].get("shares") or 0) >= 1),
        "rescued_with_an_order_at_full_size": sum(
            1 for r in rows if r["production"]["eligible"] and not r["fixed"]["eligible"]
            and (r["production"].get("shares_at_full_size") or 0) >= 1),
        "narrowed_while_already_eligible": sum(
            1 for r in rows if r["fixed"]["eligible"] and r["production"]["eligible"]
            and r["production"]["limit"] != r["fixed"]["limit"]),
        "by_production_basis": {b: sum(1 for r in rows if r["production"]["eligible"]
                                       and r["production"]["basis"] == b) for b in STRUCTURAL_BASES},
        "by_limit_basis": {b: sum(1 for r in rows if r["production"]["eligible"]
                                  and r["production"]["limit_basis"] == b) for b in plan.LIMIT_BASES},
        "by_refusal": {k: sum(1 for r in rows if r["production"]["refusal"] == k) for k in plan.TICKET_REFUSALS},
    }
    exclusions = {
        "regime_verdict": verdict,
        "grades_admitted": list(admits),
        "excluded_by_regime": len(rows) if not admits else 0,
        "excluded_by_grade": sum(1 for r in rows if r["grade"] not in pipeline.TRADE_GRADES),
        # a yellow night admits a narrower set than the standing trade grades,
        # so the two numbers differ and the report says which is which
        "excluded_by_grade_tonight": (sum(1 for r in rows if r["grade"] not in admits)
                                      if admits and tuple(admits) != tuple(pipeline.TRADE_GRADES) else None),
        "excluded_by_veto": sum(1 for r in rows if r["vetoed"]),
        "would_reach_the_stop_rule_on_a_green_night": sum(
            1 for r in rows if r["grade"] in pipeline.TRADE_GRADES and not r["vetoed"]),
        "size_multiplier": multiplier,
        "excluded_by_budget": {k: sum(1 for v in cut.values() if v == k)
                               for k in sorted(set(cut.values())) if k in BUDGET_CUT_KINDS},
        # kept out of the budget line on purpose, each under its own gate
        "cut_as_withheld_by_the_stop_rule": sum(1 for v in cut.values() if v == "withheld"),
        "cut_for_no_new_longs": sum(1 for v in cut.values() if v == "no_new_longs"),
        "cut_for_no_whole_share": sum(1 for v in cut.values() if v == "no_shares"),
    }
    green = [r for r in rows if r["grade"] in pipeline.TRADE_GRADES and not r["vetoed"]]
    counts["green_night"] = {
        "population": len(green),
        "fixed_eligible": sum(1 for r in green if r["fixed"]["eligible"]),
        "fixed_stop_rule_rejections": sum(1 for r in green if not r["fixed"]["eligible"]),
        "production_eligible": sum(1 for r in green if r["production"]["eligible"]),
        "production_rejections": sum(1 for r in green if not r["production"]["eligible"]),
        # a refused plan still carries a share count -- production sizes it at
        # the day-2 ceiling against the synthetic stop so the card can show a
        # size -- and counting those would report tickets that do not exist
        "production_with_an_order_at_full_size": sum(
            1 for r in green if r["production"]["eligible"]
            and (r["production"].get("shares_at_full_size") or 0) >= 1),
    }
    return {"session": (record.get("run") or {}).get("session"), "counts": counts,
            "exclusions": exclusions, "missing": missing, "rows": rows,
            "adopted": adopted(rows)}


def adopted(rows: list[dict]) -> dict[str, Any]:
    """What the narrower limit CARRIED WITH IT, read off the fields the run
    wrote rather than predicted. Each entry was a downstream assumption of
    the fixed ceiling that the adoption had to settle."""
    live = [r for r in rows if r["production"]["eligible"]]
    if not live:
        return {"production_eligible": 0}
    capped = [r for r in live if r["production"]["planned_entry_capped"]]
    narrowed = [r for r in live if r["production"]["narrowed"]]
    thin_band = [r for r in live if r["production"]["band_pct"] < BAND_THIN_PCT]
    return {
        "production_eligible": len(live),
        "indicative_entry_capped_at_the_limit": len(capped),
        "indicative_entry_examples": [
            {"ticker": r["ticker"], "close": r["close"],
             "uncapped": plan._at_pct(r["close"], plan.ASSUMED_SLIPPAGE_PCT),
             "planned_entry": r["production"]["planned_entry"], "limit": r["production"]["limit"]}
            for r in capped[:EXAMPLES]],
        "limit_below_the_day2_line": len(narrowed),
        "band_under_half_a_percent": len(thin_band),
        "fields_settled": [
            "plan.limit and plan.entry_high are the ticket's executable limit, and the Fidelity"
            " ticket is written at it (plan.fidelity_orders)",
            f"plan.planned_entry is min(close +{plan.ASSUMED_SLIPPAGE_PCT:g}%, that limit), so the"
            " targets and the exit schedule quoted from it are never over a price the ticket can fill at",
            f"plan.day2_spent_above carries the close +{plan.ENTRY_ABOVE_PCT:g}% on its own, as"
            " plan.skip_if_open_above and in plan.pre_open_check: the outer extension threshold, not the limit",
            f"plan.sizing_price and the share count are at the effective limit ({plan.SIZING_BASIS})",
            "the Following snapshot saves both prices (docs/app-follow.js, buildModel)",
            "report.digest_html()'s ticket facts and the page's order disclosure name both",
        ],
    }


def report_text(name: str, s: dict[str, Any]) -> str:
    c, x, d = s["counts"], s["exclusions"], s["adopted"]
    x_mult = f"{x['size_multiplier']:g}\u00d7"
    out: list[str] = []
    w = out.append
    w(f"=== {name} \u2014 session {s['session']} ===")
    w(f"the RETIRED ceiling is the close +{plan.ENTRY_ABOVE_PCT:g}% ({plan.SIZING_BASIS} sizing), carried here;")
    w(f"PRODUCTION is min(that, stop / (1 - {plan.MAX_STOP_PCT:g}%)) rounded down to cents,")
    w(f"over {', '.join(STRUCTURAL_BASES)} in that order; {SYNTHETIC_BASIS} is never read.")
    w("")
    w(f"  bursts in the record                         {c['bursts']}")
    w(f"  missing inputs (no readable bar)             {c['missing_inputs']}")
    w(f"  candidate coverage (a bar the cascade reads) {c['candidate_coverage']}")
    w("")
    w("  -- the stop rule, over the covered candidates --")
    w(f"  eligible under the retired fixed ceiling     {c['fixed_eligible']}")
    w(f"  rejected by the stop rule at that ceiling    {c['fixed_stop_rule_rejections']}")
    w(f"  eligible in production                       {c['production_eligible']}")
    w(f"  still refused in production                  {c['production_rejections']} {c['by_refusal']}")
    w(f"     of which rescued (withheld then, live now) {c['rescued']}")
    w(f"     of those, sized to a whole share            {c['rescued_with_an_order']}"
      f" at the regime's {x_mult}, {c['rescued_with_an_order_at_full_size']} at full size")
    w(f"     eligible either way, limit moved          {c['narrowed_while_already_eligible']}")
    w(f"  structural basis production used             {c['by_production_basis']}")
    w(f"  what set the limit                           {c['by_limit_basis']}")
    w("")
    w("  -- not the stop rule: the gates before and after it --")
    w(f"  regime verdict                               {x['regime_verdict']} (admits {x['grades_admitted'] or 'no grade'})")
    w(f"  excluded by the regime                       {x['excluded_by_regime']}")
    w(f"  excluded by grade (not {'/'.join(pipeline.TRADE_GRADES)})                 {x['excluded_by_grade']}")
    if x["excluded_by_grade_tonight"] is not None:
        w(f"  excluded by grade tonight (this regime admits {'/'.join(x['grades_admitted'])} only) "
          f"{x['excluded_by_grade_tonight']}")
    w(f"  excluded by a veto                           {x['excluded_by_veto']}")
    w(f"  excluded by the budget (slot cap, equity)    {x['excluded_by_budget'] or 'none recorded'}")
    w(f"  cut as withheld \u2014 the stop rule's own refusal, counted above, not here: {x['cut_as_withheld_by_the_stop_rule']}")
    w(f"  cut for no new longs (the regime) {x['cut_for_no_new_longs']}; for no whole share (the sizing) {x['cut_for_no_whole_share']}")
    w(f"  the regime's size multiplier, which both columns are sized at: {x['size_multiplier']:g}\u00d7")
    g = c["green_night"]
    w(f"  would reach the stop rule on a green night   {g['population']}")
    w(f"     of those: eligible at the fixed ceiling {g['fixed_eligible']}, rejected there {g['fixed_stop_rule_rejections']};"
      f" eligible in production {g['production_eligible']}, refused {g['production_rejections']},"
      f" of which {g['production_with_an_order_at_full_size']} size to a whole share at full size")
    w("")
    w("  -- representative cases --")
    for line in examples(s):
        w("  " + line)
    w("")
    w("  -- what the narrower limit carried with it --")
    if d.get("production_eligible"):
        w(f"  indicative entry capped at the limit (close +{plan.ASSUMED_SLIPPAGE_PCT:g}% would be over it):"
          f" {d['indicative_entry_capped_at_the_limit']} of {d['production_eligible']}")
        for e in d["indicative_entry_examples"]:
            w(f"     {e['ticker']}: close {plan._usd(e['close'])}, uncapped {plan._usd(e['uncapped'])},"
              f" planned entry {plan._usd(e['planned_entry'])} = the {plan._usd(e['limit'])} limit")
        w(f"  limit under the +{plan.ENTRY_ABOVE_PCT:g}% day-2 line:"
          f" {d['limit_below_the_day2_line']} of {d['production_eligible']}")
        w(f"  a band under {BAND_THIN_PCT:g}%: {d['band_under_half_a_percent']}"
          f" (a limit at the buy stop is refused, not narrowed: see by_refusal above)")
        for f in d["fields_settled"]:
            w(f"     \u00b7 {f}")
    else:
        w("  no ticket in production on this record")
    w("")
    w("  This counts eligibility under two ceilings on one archived session.")
    w("  It reads no forward return and makes no claim about either ceiling's edge.")
    return "\n".join(out)


def examples(s: dict[str, Any]) -> list[str]:
    rows = s["rows"]
    picks: list[str] = []
    rescued = [r for r in rows if r["production"]["eligible"] and not r["fixed"]["eligible"]]
    rescued.sort(key=lambda r: (r["grade"] != "A+", r["grade"] != "A", r["ticker"]))
    for r in rescued[:EXAMPLES_SHOWN]:
        p, n = r["production"], r["fixed"]
        picks.append(f"rescued  {r['ticker']:6s} {str(r['grade']):3s} close {plan._usd(r['close'])}: "
                     f"at the fixed {plan._usd(n['limit'])} the stop was {plan._usd(n['stop'])} ({n['basis']}, "
                     f"{n['stop_pct']:g}%) -> withheld; production limit {plan._usd(p['limit'])} "
                     f"stop {plan._usd(p['stop'])} ({p['basis']}, {p['stop_pct']:g}%), "
                     f"band +{p['band_pct']:g}%, {_plural(p['shares_at_full_size'], 'share')} at full size")
    still = [r for r in rows if not r["production"]["eligible"]]
    for r in still[:EXAMPLES_REFUSED]:
        tried = ", ".join(f"{t['basis']} {plan._usd(t['stop'])} -> ceiling {plan._usd(t['cap'])}"
                          for t in constrained_ceiling(r["close"], r["low"], r["high"])["tried"])
        picks.append(f"refused  {r['ticker']:6s} {str(r['grade']):3s} close {plan._usd(r['close'])}: "
                     f"{tried or 'no structural candidate'}; {r['production']['refusal']}")
    moved = [r for r in rows if r["fixed"]["eligible"] and r["production"]["eligible"]
             and r["production"]["limit"] != r["fixed"]["limit"]]
    for r in moved[:EXAMPLES_MOVED]:
        p, n = r["production"], r["fixed"]
        picks.append(f"moved    {r['ticker']:6s} {str(r['grade']):3s} close {plan._usd(r['close'])}: "
                     f"eligible either way; fixed {plan._usd(n['limit'])} ({n['basis']}) -> production "
                     f"{plan._usd(p['limit'])} ({p['basis']}), stop {plan._usd(n['stop'])} -> "
                     f"{plan._usd(p['stop'])}, at full size {_plural(n['shares_at_full_size'], 'share')} -> "
                     f"{_plural(p['shares_at_full_size'], 'share')}")
    return picks or ["no burst on this record reaches the stop rule"]


def regime_multiplier(record: dict) -> float:
    regime = ((record.get("breadth") or {}).get("regime") or {})
    return float(regime.get("size_multiplier") or 0.0) if "size_multiplier" in regime else 1.0


def verify(record: dict) -> list[str]:
    """Every plan the record already carries is reproduced by the production
    path this study calls, so the 'current' column is the run's own answer
    and not a second implementation of it."""
    bad: list[str] = []
    for row in record.get("bursts") or []:
        recorded = row.get("plan")
        if not recorded or usable_bar(row):
            continue
        now = current_plan(row, regime_multiplier(record))
        # the ticket's own prices, its eligibility, the hazards the bar itself
        # raises -- and the share count, the action and the money, because the
        # study sizes at the regime's own multiplier and so does the run. If
        # this reproduces, the "current" column IS the record's answer.
        for field in ("limit", "limit_basis", "stop", "stop_basis", "stop_pct", "eligible", "reason",
                      "entry_low", "entry_high", "day2_spent_above", "planned_entry", "extended_above",
                      "hazards", "hazard_multiplier", "stop_risk_multiplier",
                      "shares", "action", "risk_usd", "position_usd"):
            if now[field] != recorded.get(field):
                bad.append(f"{row['ticker']}.{field}: recomputed {now[field]!r} != recorded {recorded.get(field)!r}")
    return bad


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("records", nargs="*", default=["docs/data.json"],
                    help="records to read (default: docs/data.json)")
    ap.add_argument("--json", dest="out", default=None, help="also write the whole study here")
    args = ap.parse_args(list(argv) if argv is not None else None)

    whole: dict[str, Any] = {}
    drifted = False
    for name in args.records:
        path = Path(name)
        record = json.loads(path.read_text())
        if not record.get("bursts"):
            print(f"=== {path.name} — no bursts to read ===\n")
            continue
        mismatches = verify(record)
        s = study(record)
        whole[name] = s   # keyed as given: two records may share a basename
        print(report_text(path.name, s))
        carried = sum(1 for b in record["bursts"] if b.get("plan"))
        if mismatches:
            drifted = True
            print("  !! the recorded plans do not reproduce: " + "; ".join(mismatches[:5]))
        elif carried:
            print(f"  ({carried} recorded plan(s) reproduced exactly by the production path,"
                  f" so the current column is the run's own answer)")
        else:
            print("  (this record carries no plan of its own -- the regime wrote none -- so the"
                  " current column is the production path run over its archived bars)")
        print()
    if args.out:
        Path(args.out).write_text(json.dumps(whole, indent=1, sort_keys=True) + "\n")
        print(f"wrote {args.out}")
    # a record whose own plans this path cannot reproduce is a drift, and the
    # repo reads exit codes: it must not look like a clean reading
    return 1 if drifted else 0


if __name__ == "__main__":
    raise SystemExit(main())
