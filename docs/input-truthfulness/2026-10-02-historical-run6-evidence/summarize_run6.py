"""Print a price-free summary of recovered SpicyStock run 6 evidence.

Usage:  python summarize_run6.py <recovered folder>

Reads only execution-diagnostics.json and reconciliation-YYYY-MM-DD.json from
the folder that `historical_package.py recover` created. Prints statuses,
reasons, counts, the recomputed regime and ticker names. It never prints a
price, a volume or any raw page content, so its output is safe to paste back.
It writes nothing and makes no network calls.
"""
import json
import sys
from collections import Counter
from pathlib import Path

LIMIT = 25  # cap on ticker names listed per line


def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def names(items):
    items = sorted(items)
    more = len(items) - LIMIT
    return ", ".join(items[:LIMIT]) + (f" (+{more} more)" if more > 0 else "") if items else "none"


def show_regime(label, regime):
    if not regime:
        print(f"    {label}: no regime (could not be computed)")
        return
    inputs = regime.get("inputs", {})
    print(f"    {label}: {str(regime.get('verdict')).upper()}  "
          f"(rules that fired: {', '.join(regime.get('active_predicates', [])) or 'none'})")
    print(f"      10-day up/down {inputs.get('up4_10d')} / {inputs.get('down4_10d')} -> ratio {inputs.get('ratio_10d')}"
          f"   |   5-day {inputs.get('up4_5d')} / {inputs.get('down4_5d')} -> {inputs.get('ratio_5d')}")
    print(f"      that day up/down {inputs.get('up4')} / {inputs.get('down4')}"
          f"   counted universe {regime.get('thresholds', {}).get('universe')}")


def session_report(folder, result):
    session = result.get("session")
    print(f"\n=== {session} ===")
    print(f"  status {result.get('status')}   formula check {result.get('same_input_formula_status')}"
          f"   regime established {result.get('reconstructed_regime_established')}")
    if result.get("reason"):
        print(f"  reason: {result['reason']}")
    print(f"  stock statuses: {result.get('population_states')}")
    print(f"  every stock has its full required window: {result.get('complete_required_input_windows')}")
    detail = load(folder / f"reconciliation-{session}.json")
    if not detail:
        print("  (no reconciliation file for this session)")
        return
    manifest = detail.get("symbol_manifest", {})
    by_status = {}
    for symbol, record in manifest.items():
        by_status.setdefault(record.get("status"), []).append(symbol)
    for status in sorted(s for s in by_status if s != "returned_with_bars"):
        print(f"  {status} ({len(by_status[status])}): {names(by_status[status])}")
    gaps = [s for s, r in manifest.items() if r.get("missing_required_sessions")]
    print(f"  stocks missing some required sessions ({len(gaps)}): {names(gaps)}")
    failures = detail.get("failures", [])
    if failures:
        print(f"  fetch failures ({len(failures)}): " +
              "; ".join(f"{f.get('query')}: {f.get('reason') or f.get('kind') or 'failure'}" for f in failures[:LIMIT]))
    for mode, title in (("C", "C  fresh bars, $3 rule on the day"), ("D", "D  what-if, $3 rule each of the 10 days")):
        part = detail.get(mode, {})
        print(f"  {title}: {part.get('status')}" + (f" ({part.get('reason')})" if part.get("reason") else ""))
        reference = part.get("reference") or {}
        if reference.get("error"):
            print(f"    calculator error: {reference['error']}")
        differences = part.get("differences") or []
        if differences:
            kinds = Counter(d.get("field") or d.get("kind") for d in differences)
            print(f"    calculator differences ({len(differences)}): {dict(kinds)}")
        if not reference:
            continue
        show_regime("independent calculator", reference.get("regime"))
        production = (part.get("production") or {}).get("regime")
        if production:
            print(f"    app's own code: {str(production.get('verdict')).upper()}")
        print(f"    regime established: {reference.get('underlying_regime_established')}")
        days = reference.get("days") or []
        if days:
            unknown = {k: v for k, v in days[-1].get("unknown", {}).items() if v}
            print(f"    unknown event counts on {days[-1].get('date')}: {unknown or 'none'}")
        target = days[-1]["date"] if days else None
        blockers = sorted({e["symbol"] for e in reference.get("events", [])
                           if e.get("included") and e.get("events", {}).get("up4") is None})
        print(f"    counted stocks with an unknown 4% event in the 10 days ({len(blockers)}): {names(blockers)}")
        if target:
            month = sorted({e["symbol"] for e in reference.get("events", [])
                            if e.get("session") == target and e.get("included")
                            and e.get("events", {}).get("up50_month") is None})
            print(f"    counted stocks with unknown up-50%-month on {target} ({len(month)}): {names(month)}")
        bounds = (reference.get("ratio_bounds") or {}).get("10") or {}
        if bounds:
            print(f"    10-day ratio could be anywhere in {bounds.get('finite_ratio_rounded')} "
                  f"given {bounds.get('unknown_contributors')} unknown contributors")
        masks = reference.get("masks") or []
        if masks:
            print(f"    population reasons on {masks[-1].get('session')}: {masks[-1].get('reason_counts')}")
    candidates = detail.get("mechanical_candidates") or {}
    print(f"  diagnostic scan matches (no grading, no tickets): {len(candidates)}")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    folder = Path(sys.argv[1])
    diagnostics = load(folder / "execution-diagnostics.json")
    if diagnostics is None:
        sys.exit(f"No execution-diagnostics.json in {folder}. Point this at the recovered folder.")
    prior = diagnostics.get("prior_acquisition", {})
    print("SpicyStock run 6 evidence summary (no prices)")
    print(f"overall status {diagnostics.get('status')}   reason {diagnostics.get('reason', '-')}")
    print(f"download: status {prior.get('status')}   queries completed {prior.get('completed_queries')} of 97"
          f"   reason {prior.get('reason', '-')}")
    print(f"ledger: {diagnostics.get('ledger') or prior.get('ledger')}")
    for result in diagnostics.get("reconciliation", []):
        session_report(folder, result)


if __name__ == "__main__":
    main()
