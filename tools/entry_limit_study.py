"""Read-only comparison of two entry ceilings over an archived record.

The question is the one CLAUDE.md defers: his +4% ceiling and his 4% stop
line cannot both hold at the ticket's limit, so nearly every real burst is
withheld. This reads a record that has already been written, recomputes each
burst's plan through ``plan.burst_plan()`` -- the production path, unchanged
-- and beside it computes what the ticket WOULD be if the ceiling were
constrained by the structural stop instead of fixed:

    limit' = min(entry_high, floor_to_cents(stop / (1 - MAX_STOP_PCT/100)))

The structural stop candidates are the existing ones in their existing
priority order (``plan.burst_stop``'s cascade: the burst day's low, then the
bar's midpoint). The synthetic ``max_stop`` fallback -- a level the bar does
not support -- is never consulted here: it can rescue nothing, which is the
whole point of the comparison. A proposal is admitted only when
``stop < trigger <= limit`` still holds at the rounded ceiling, and the
shares are sized at that effective limit, as ``plan.SIZING_BASIS`` requires.

It writes nothing. It changes no rule, no record, no regime, no ticket and no
scorecard, and it is not a backtest: it counts eligibility under two ceilings
over one archived session and reports what a narrower limit would drag with
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


#: The candidates the proposal may read, in ``plan.burst_stop``'s own order.
#: ``plan.STOP_BASES`` ends with the synthetic fallback; this is that tuple
#: with the fallback dropped, so a new structural basis appears here by
#: adding it there and nothing else.
STRUCTURAL_BASES = tuple(b for b in plan.STOP_BASES if b != "max_stop")
#: The synthetic level the proposal must never read. Named so the refusal is
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


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" + ("" if n == 1 else "s")


def floor_to_cents(value: float) -> float:
    """A ceiling rounded DOWN, so rounding can never widen the stop past the
    line it was derived from."""
    scale = 10 ** CEILING_DECIMALS
    return math.floor(value * scale + 1e-9) / scale


def structural_candidates(low: float, high: float) -> list[tuple[str, float]]:
    """The structural stops ``plan.burst_stop`` would try, in its order, off
    the same cent-rounded bar it reads. The record carries raw four-decimal
    lows for some names; ``burst_plan`` rounds the bar once on the way in, and
    a study that skipped that step proposed stops a cent away from the ones
    the run would write. A basis named in ``plan.STOP_BASES`` that this has no
    price for is refused out loud: a study that silently skipped one would
    answer a question about a cascade it had not read."""
    low, high = plan._price(low, "low"), plan._price(high, "high")
    prices = {"burst_low": low, "half_range": plan._money((low + high) / 2)}
    unknown = [b for b in STRUCTURAL_BASES if b not in prices]
    if unknown:
        raise ValueError(f"plan.STOP_BASES names structural bases this study cannot price: {unknown}")
    return [(basis, prices[basis]) for basis in STRUCTURAL_BASES]


def constrained_ceiling(close: float, low: float, high: float) -> dict[str, Any] | None:
    """The proposed ticket for one burst bar, or None when no structural stop
    supports one. ``close`` is the buy stop (the trigger) as ``burst_plan``
    sets it, and the bar is cent-rounded once, as ``burst_plan`` rounds it."""
    close = plan._price(close, "close")
    trigger = close
    fixed = plan._at_pct(close, plan.ENTRY_ABOVE_PCT)
    tried: list[dict[str, Any]] = []
    for basis, stop in structural_candidates(low, high):
        cap = floor_to_cents(stop / (1 - plan.MAX_STOP_PCT / 100.0))
        limit = min(fixed, cap)
        ok = stop < trigger <= limit
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


def production_agrees(proposal: Mapping[str, Any], low: float, high: float) -> bool:
    """The proposal is a narrower CEILING, not a second stop rule: run
    ``plan.burst_stop`` -- the production cascade, untouched -- at the proposed
    limit and it must reach the same structural basis at the same price, inside
    his line. If it ever does not, the study is proposing something the
    existing rule would not accept, and says so rather than reporting it."""
    got = plan.burst_stop(proposal["limit"], low, high, trigger=proposal["trigger"])
    return (got["stop_basis"] == proposal["basis"] and got["stop"] == proposal["stop"]
            and got["stop_pct"] <= plan.MAX_STOP_PCT)


def proposed_sizing(row: dict, proposal: dict, multiplier: float) -> plan.Sizing:
    """The proposed ticket's shares, at the effective limit and under the same
    multiplier chain the production plan applies -- the regime's, the hazards
    from the bar, and the stop-risk halving from the stop's own width -- so
    the two columns are the same arithmetic over two ceilings."""
    found = plan.hazards(row.get("gain_pct") or 0.0, row.get("extension_pct"))
    hazard = min([h["multiplier"] for h in found], default=1.0)
    stop_multiplier, _ = plan.stop_risk(proposal["stop_pct_at_limit"])
    return plan.size(proposal["limit"], proposal["stop"], plan.Account(), multiplier * hazard * stop_multiplier)


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
        except (ValueError, KeyError) as exc:   # the pipeline logs and skips; so does this
            missing.append({"ticker": row.get("ticker"), "why": str(exc)[:80]})
            continue
        proposal = constrained_ceiling(row["close"], row["low"], row["high"])
        admitted = proposal.get("basis") is not None
        sized = None
        if admitted:
            if not production_agrees(proposal, row["low"], row["high"]):
                raise AssertionError(
                    f"{row['ticker']}: plan.burst_stop at the proposed {proposal['limit']} limit does not "
                    f"reach {proposal['basis']} at {proposal['stop']}; the proposal is not the same rule")
            sized = proposed_sizing(row, proposal, multiplier)
            # and at full size, because the regime's multiplier is 0 on a red
            # night and the ceiling question is about the nights that trade
            full = proposed_sizing(row, proposal, 1.0)
        rows.append({
            "ticker": row["ticker"], "grade": row.get("grade"), "vetoed": bool(row.get("vetoes")),
            "admitted_by_regime": row.get("grade") in admits and not row.get("vetoes"),
            "cut_kind": cut.get(row["ticker"]),
            "close": row["close"], "low": row["low"], "high": row["high"],
            "current": {"limit": now["limit"], "stop": now["stop"], "basis": now["stop_basis"],
                        "eligible": now["eligible"], "shares": now["shares"],
                        "shares_at_full_size": now_full["shares"],
                        "stop_pct": now["stop_pct"], "action": now["action"]},
            "proposed": ({"limit": proposal["limit"], "stop": proposal["stop"], "basis": proposal["basis"],
                          "narrowed": proposal["narrowed"], "stop_pct": proposal["stop_pct_at_limit"],
                          "band_pct": proposal["band_pct"], "shares": sized.shares,
                          "shares_at_full_size": full.shares, "risk_usd": sized.risk_usd,
                          "risk_usd_at_full_size": full.risk_usd}
                         if admitted else {"limit": None, "basis": None,
                                           "tried": proposal.get("tried", [])}),
        })

    counts = {
        "bursts": len(bursts),
        "missing_inputs": len(missing),
        "candidate_coverage": len(rows),
        "current_eligible": sum(1 for r in rows if r["current"]["eligible"]),
        "current_stop_rule_rejections": sum(1 for r in rows if not r["current"]["eligible"]),
        "proposed_eligible": sum(1 for r in rows if r["proposed"]["basis"]),
        "proposed_rejections": sum(1 for r in rows if not r["proposed"]["basis"]),
        "rescued": sum(1 for r in rows if r["proposed"]["basis"] and not r["current"]["eligible"]),
        # a plan the account cannot size to a whole share is not a ticket:
        # production writes no_order and the budget cuts it as no_shares
        "rescued_with_an_order": sum(1 for r in rows if r["proposed"]["basis"] and not r["current"]["eligible"]
                                     and (r["proposed"].get("shares") or 0) >= 1),
        "rescued_with_an_order_at_full_size": sum(
            1 for r in rows if r["proposed"]["basis"] and not r["current"]["eligible"]
            and (r["proposed"].get("shares_at_full_size") or 0) >= 1),
        "narrowed_while_already_eligible": sum(
            1 for r in rows if r["current"]["eligible"] and r["proposed"]["basis"]
            and r["proposed"]["limit"] != r["current"]["limit"]),
        "by_proposed_basis": {b: sum(1 for r in rows if r["proposed"]["basis"] == b) for b in STRUCTURAL_BASES},
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
        "current_eligible": sum(1 for r in green if r["current"]["eligible"]),
        "current_stop_rule_rejections": sum(1 for r in green if not r["current"]["eligible"]),
        "proposed_eligible": sum(1 for r in green if r["proposed"]["basis"]),
        "proposed_rejections": sum(1 for r in green if not r["proposed"]["basis"]),
        "proposed_with_an_order_at_full_size": sum(
            1 for r in green if (r["proposed"].get("shares_at_full_size") or 0) >= 1),
    }
    return {"session": (record.get("run") or {}).get("session"), "counts": counts,
            "exclusions": exclusions, "missing": missing, "rows": rows,
            "downstream": downstream(rows)}


def downstream(rows: list[dict]) -> dict[str, Any]:
    """What a narrower limit drags with it. Each entry is a field the run
    writes or the page prints that is derived from the close or from the
    fixed ceiling and would no longer agree with the order."""
    eligible = [r for r in rows if r["proposed"]["basis"]]
    if not eligible:
        return {"proposed_eligible": 0}
    indicative_above = [r for r in eligible
                        if plan._at_pct(r["close"], plan.ASSUMED_SLIPPAGE_PCT) > r["proposed"]["limit"]]
    narrowed = [r for r in eligible if r["proposed"]["narrowed"]]
    # the band the ticket can still fill in. limit == stop is impossible by
    # the admission rule; limit == trigger is not, and it is a buy stop-limit
    # with no room above its own trigger at all
    no_band = [r for r in eligible if r["proposed"]["limit"] == plan._price(r["close"], "close")]
    thin_band = [r for r in eligible if r["proposed"]["band_pct"] < 0.5]
    return {
        "proposed_eligible": len(eligible),
        "indicative_entry_above_the_limit": len(indicative_above),
        "indicative_entry_examples": [
            {"ticker": r["ticker"], "close": r["close"],
             "indicative": plan._at_pct(r["close"], plan.ASSUMED_SLIPPAGE_PCT),
             "proposed_limit": r["proposed"]["limit"]}
            for r in indicative_above[:5]],
        "limit_below_the_displayed_skip_line": len(narrowed),
        "no_band_at_all": len(no_band),
        "band_under_half_a_percent": len(thin_band),
        "fields_affected": [
            "plan.limit and the Fidelity ticket's limit price (plan.fidelity_orders)",
            f"plan.planned_entry, the indicative entry at the close +{plan.ASSUMED_SLIPPAGE_PCT:g}%,"
            " which plan.targets() and plan.exit_schedule() are quoted from",
            f"plan.skip_if_open_above and plan.entry_high, printed as the +{plan.ENTRY_ABOVE_PCT:g}%"
            " line in the page's order disclosure and in plan.pre_open_check",
            "plan.sizing_price and the share count, sized at the effective limit"
            f" ({plan.SIZING_BASIS})",
            "the Following snapshot's saved levels and suggested quantity (docs/app-follow.js)",
            "report.digest_html()'s ticket terms and the page's order disclosure",
        ],
    }


def report_text(name: str, s: dict[str, Any]) -> str:
    c, x, d = s["counts"], s["exclusions"], s["downstream"]
    x_mult = f"{x['size_multiplier']:g}×"
    out: list[str] = []
    w = out.append
    w(f"=== {name} — session {s['session']} ===")
    w(f"the current ceiling is the close +{plan.ENTRY_ABOVE_PCT:g}% ({plan.SIZING_BASIS} sizing);")
    w(f"the proposed ceiling is min(that, stop / (1 - {plan.MAX_STOP_PCT:g}%)) rounded down to cents,")
    w(f"over {', '.join(STRUCTURAL_BASES)} in that order; {SYNTHETIC_BASIS} is never read.")
    w("")
    w(f"  bursts in the record                         {c['bursts']}")
    w(f"  missing inputs (no readable bar)             {c['missing_inputs']}")
    w(f"  candidate coverage (a bar the cascade reads) {c['candidate_coverage']}")
    w("")
    w("  -- the stop rule, over the covered candidates --")
    w(f"  eligible under the current ceiling           {c['current_eligible']}")
    w(f"  rejected by the stop rule today              {c['current_stop_rule_rejections']}")
    w(f"  eligible under the proposed ceiling          {c['proposed_eligible']}")
    w(f"  still rejected under the proposal            {c['proposed_rejections']}")
    w(f"     of which rescued (withheld now, eligible) {c['rescued']}")
    w(f"     of those, sized to a whole share            {c['rescued_with_an_order']}"
      f" at the regime's {x_mult}, {c['rescued_with_an_order_at_full_size']} at full size")
    w(f"     already eligible, limit moved             {c['narrowed_while_already_eligible']}")
    w(f"  structural basis the proposal used           {c['by_proposed_basis']}")
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
    w(f"  cut as withheld — the stop rule's own refusal, counted above, not here: {x['cut_as_withheld_by_the_stop_rule']}")
    w(f"  cut for no new longs (the regime) {x['cut_for_no_new_longs']}; for no whole share (the sizing) {x['cut_for_no_whole_share']}")
    w(f"  the regime's size multiplier, which both columns are sized at: {x['size_multiplier']:g}×")
    g = c["green_night"]
    w(f"  would reach the stop rule on a green night   {g['population']}")
    w(f"     of those: eligible today {g['current_eligible']}, rejected today {g['current_stop_rule_rejections']};"
      f" eligible proposed {g['proposed_eligible']}, rejected proposed {g['proposed_rejections']},"
      f" of which {g['proposed_with_an_order_at_full_size']} size to a whole share at full size")
    w("")
    w("  -- representative cases --")
    for line in examples(s):
        w("  " + line)
    w("")
    w("  -- downstream of a narrower limit --")
    if d.get("proposed_eligible"):
        w(f"  indicative entry (close +{plan.ASSUMED_SLIPPAGE_PCT:g}%) above the proposed limit:"
          f" {d['indicative_entry_above_the_limit']} of {d['proposed_eligible']}")
        for e in d["indicative_entry_examples"]:
            w(f"     {e['ticker']}: close {plan._usd(e['close'])}, indicative {plan._usd(e['indicative'])},"
              f" proposed limit {plan._usd(e['proposed_limit'])}")
        w(f"  limit below the displayed +{plan.ENTRY_ABOVE_PCT:g}% skip line:"
          f" {d['limit_below_the_displayed_skip_line']} of {d['proposed_eligible']}")
        w(f"  a limit with no room above its own trigger: {d['no_band_at_all']};"
          f" a band under 0.5%: {d['band_under_half_a_percent']}")
        for f in d["fields_affected"]:
            w(f"     · {f}")
    else:
        w("  no proposed ticket on this record")
    w("")
    w("  This counts eligibility under two ceilings on one archived session.")
    w("  It reads no forward return and makes no claim about either ceiling's edge.")
    return "\n".join(out)


def examples(s: dict[str, Any]) -> list[str]:
    rows = s["rows"]
    picks: list[str] = []
    rescued = [r for r in rows if r["proposed"]["basis"] and not r["current"]["eligible"]]
    rescued.sort(key=lambda r: (r["grade"] != "A+", r["grade"] != "A", r["ticker"]))
    for r in rescued[:3]:
        p, n = r["proposed"], r["current"]
        picks.append(f"rescued  {r['ticker']:6s} {r['grade']:3s} close {plan._usd(r['close'])}: "
                     f"today limit {plan._usd(n['limit'])} stop {plan._usd(n['stop'])} ({n['basis']}, "
                     f"{n['stop_pct']:g}%) -> withheld; proposed limit {plan._usd(p['limit'])} "
                     f"stop {plan._usd(p['stop'])} ({p['basis']}, {p['stop_pct']:g}%), "
                     f"band +{p['band_pct']:g}%, {_plural(p['shares_at_full_size'], 'share')} at full size")
    still = [r for r in rows if not r["proposed"]["basis"]]
    for r in still[:2]:
        tried = ", ".join(f"{t['basis']} {plan._usd(t['stop'])} -> ceiling {plan._usd(t['cap'])}"
                          for t in r["proposed"].get("tried", []))
        picks.append(f"refused  {r['ticker']:6s} {r['grade']:3s} close {plan._usd(r['close'])}: "
                     f"{tried or 'no structural candidate'}; none leaves the trigger inside the limit")
    moved = [r for r in rows if r["current"]["eligible"] and r["proposed"]["basis"]
             and r["proposed"]["limit"] != r["current"]["limit"]]
    for r in moved[:2]:
        p, n = r["proposed"], r["current"]
        picks.append(f"moved    {r['ticker']:6s} {r['grade']:3s} close {plan._usd(r['close'])}: "
                     f"eligible today at {plan._usd(n['limit'])} ({n['basis']}); proposed "
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
        for field in ("limit", "stop", "stop_basis", "stop_pct", "eligible", "reason",
                      "entry_low", "entry_high", "planned_entry", "extended_above",
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
