"""What the production scan found, against what Bonde's own scan would have.

`src/stockbee.py` already runs the canonical scan every night, over the same
frames production scanned, and writes the matches into the run's `stockbee`
block. Nothing has ever compared the two lists. This does, from the committed
record alone -- no market data, no network -- so the answer is reproducible
from a checkout on any machine.

The canonical scan is three predicates (`stockbee.MEASUREMENT_RULES["scan"]`):
close / previous close >= 1.04, volume > the previous session's volume, and
volume >= 100,000 shares. Production applies its own: `min_gain_pct`,
`min_price`, `min_rvol` against a `rvol_lookback`-session trailing average,
and then rule 6's cross-sectional dollar-volume percentile. Only the gain is
common to both.

Two divergences, and they run in opposite directions, so a single count of
"how many did we find" hides both:

  MISSED   a name the canonical scan matched and production did not. Every one
           is a burst Bonde's method would have put in front of a trader.
  EXTRA    a name production called a burst that fails the canonical scan.
           On the record these are all names whose volume did NOT exceed the
           previous session's -- day two or later of a volume event, which is
           exactly what `volume > previous volume` exists to exclude.

A MISSED name is classified by the first production rule that can be shown to
reject it from the sidecar's own measurements. That classification is
DELIBERATELY approximate in one place and says so: the sidecar measures volume
against a 20-session average and `ScanConfig.rvol_lookback` is 50, so a name
at or above `min_rvol` on the sidecar's window may still be under it on
production's. Those are reported as `rvol_window` rather than folded into
`rvol_threshold`, because the two say different things about the rule -- one
is the bar being too high, the other is the window being too long -- and a
report that merged them would answer neither.

THE CALL BUDGET is reported beside all of that, because on this record the two
facts belong together: the scoring cap has never once bound, while the scan it
feeds was dropping the setups the method is named for. A budget that is 70%
idle is not a budget problem -- it is a funnel that is not delivering enough to
spend it on -- and the report says which of the two the record shows.

The $ BREAKOUT is reported with them. It is Bonde's other daily scan
(`stockbee.DOLLAR_RULES`), the one his own words point at a universe like this
repo's, and every row of it is by construction a name production never scored:
the sections are disjoint, and production admits only 4% bursts.

Run: python tools/fidelity_report.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import scanner, stockbee  # noqa: E402

LEDGER = ROOT / "docs" / "ledger.json"

#: The sidecar averages volume over this many prior sessions
#: (`stockbee.MEASUREMENT_RULES["volume_vs_average"]`). Production's own window
#: is `ScanConfig.rvol_lookback`, and the gap between them is the whole reason
#: `rvol_window` is a separate verdict below. Read from the rule string rather
#: than retyped, so a change to the sidecar cannot leave this report quoting a
#: window nobody measures.
SIDECAR_VOLUME_SESSIONS = 20


def _prod_rows(run: dict) -> dict:
    """Every burst production found that night, scored or refused.

    `candidates` are the ones that reached the scorer and `gated` the ones a
    rule turned away, and the union is what `run.bursts` counts. Reading only
    `candidates` would report the gate's rejections as scan misses, which is
    the one collapse this report exists to avoid.
    """
    rows = {c["ticker"]: c for c in run.get("candidates") or [] if isinstance(c, dict) and c.get("ticker")}
    for g in run.get("gated") or []:
        if isinstance(g, dict) and g.get("ticker"):
            rows.setdefault(g["ticker"], g)
    return rows


def _why_missed(row: dict, cfg: scanner.ScanConfig) -> str:
    """The first production rule that provably rejects this canonical match.

    Order matters and follows the scan's own: price, then gain, then relative
    volume, then rule 6. A name can fail several; naming the first one keeps
    the tally a partition rather than a set of overlapping counts.
    """
    close = row.get("close")
    if close is not None and close <= cfg.min_price:
        return "min_price"
    gain = row.get("gain_pct")
    if gain is not None and gain < cfg.min_gain_pct:
        return "min_gain_pct"          # cannot happen for a canonical match; kept so the partition is total
    ratio = row.get("volume_vs_average")
    if ratio is None:
        return "unmeasured"
    if ratio < cfg.min_rvol:
        return "rvol_threshold"
    return "rvol_window"               # passes on 20 sessions; production's 50 is the remaining difference


def compare(run: dict) -> dict | None:
    """One night, both directions. None when the run carries no sidecar."""
    sidecar = run.get("stockbee")
    if not isinstance(sidecar, dict):
        return None
    scan = sidecar.get("scan") or {}
    rows = scan.get("rows")
    if not isinstance(rows, list):
        return None
    # `shown` truncates the rows at stockbee.SCAN_LIMIT; comparing against a
    # truncated list would invent misses. Say so rather than reporting a number
    # the record cannot support.
    truncated = scan.get("matched") != scan.get("shown")

    dollar = sidecar.get("dollar") if isinstance(sidecar.get("dollar"), dict) else None
    dollar_rows = [r for r in (dollar or {}).get("rows", [])
                   if isinstance(r, dict) and r.get("ticker")]

    canonical = {r["ticker"]: r for r in rows if isinstance(r, dict) and r.get("ticker")}
    production = _prod_rows(run)
    cfg = scanner.ScanConfig()

    missed = sorted(set(canonical) - set(production))
    extra = sorted(set(production) - set(canonical))
    reasons: dict[str, int] = {}
    for ticker in missed:
        reason = _why_missed(canonical[ticker], cfg)
        reasons[reason] = reasons.get(reason, 0) + 1

    return {
        "date": run.get("date"),
        "universe": (run.get("universe") or {}).get("label"),
        "measured": run.get("measured"),
        "canonical_matched": scan.get("matched"),
        "canonical_listed": len(canonical),
        "canonical_truncated": truncated,
        "production_bursts": run.get("bursts"),
        "overlap": len(set(canonical) & set(production)),
        "missed": missed,
        "missed_by_rule": reasons,
        "extra": extra,
        "scored": run.get("scored"),
        "score_cap": run.get("score_cap"),
        "top_score": run.get("top_score"),
        "unspent_calls": _unspent(run),
        "dollar_matched": (dollar or {}).get("matched"),
        "dollar_listed": len(dollar_rows),
        "dollar_names": [r["ticker"] for r in dollar_rows],
    }


def _unspent(run: dict) -> int | None:
    """Calls the budget allowed and the night did not make.

    None rather than 0 when either number is missing: a run entry from before
    the field existed says nothing about the budget, and calling that "nothing
    unspent" would put a fact into the total that the record does not hold.
    """
    cap, spent = run.get("score_cap"), run.get("scored")
    if any(not isinstance(v, int) or isinstance(v, bool) for v in (cap, spent)):
        return None  # `True` is an int, and it is not a call count
    return max(0, cap - spent)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--ledger", default=str(LEDGER))
    args = parser.parse_args(argv)

    try:
        book = json.loads(Path(args.ledger).read_text())
    except (OSError, ValueError) as exc:
        print(f"cannot read {args.ledger}: {type(exc).__name__}", file=sys.stderr)
        return 1

    reports = [r for r in (compare(run) for run in book.get("runs") or []) if r]
    if not reports:
        print("No run in this ledger carries a stockbee block, so there is nothing to compare.")
        return 0

    if args.json:
        print(json.dumps(reports, indent=2))
        return 0

    print(f"Canonical Stockbee scan against production, over {len(reports)} run(s) of "
          f"{Path(args.ledger).name}.")
    print(f"Canonical rule: {stockbee.MEASUREMENT_RULES['scan']}")
    cfg = scanner.ScanConfig()
    print(f"Production rule: gain >= {cfg.min_gain_pct}%, price > ${cfg.min_price}, "
          f"volume >= {cfg.min_rvol}x its own {cfg.rvol_lookback}-session average, "
          f"then rule 6 at the {cfg.min_dollar_volume_pctile:g}th percentile of dollar volume.")
    print()
    for r in reports:
        if r["canonical_matched"] is None or r["canonical_listed"] == 0:
            continue
        kept = 100.0 * r["overlap"] / r["canonical_listed"]
        print(f"  {r['date']}  universe {r['measured']} names")
        note = " (rows truncated; misses undercounted)" if r["canonical_truncated"] else ""
        print(f"    canonical scan matched {r['canonical_matched']}{note}; "
              f"production called {r['production_bursts']} a burst; {r['overlap']} in both "
              f"({kept:.0f}% of the canonical list kept)")
        if r["missed"]:
            by = ", ".join(f"{k} {v}" for k, v in sorted(r["missed_by_rule"].items()))
            print(f"    missed {len(r['missed'])}: {by}")
            print(f"      {' '.join(r['missed'])}")
        if r["extra"]:
            print(f"    admitted {len(r['extra'])} that fail the canonical scan "
                  f"(volume did not exceed the previous session): {' '.join(r['extra'])}")
        if r["dollar_listed"]:
            note = "" if r["dollar_matched"] == r["dollar_listed"] else " (rows truncated)"
            print(f"    $ breakout matched {r['dollar_matched']}{note} that the 4% scan did not, "
                  f"none of them scored: {' '.join(r['dollar_names'][:12])}"
                  + (" ..." if len(r["dollar_names"]) > 12 else ""))
        print(f"    scored {r['scored']} of a {r['score_cap']}-call budget; top score {r['top_score']}")
        print()

    # THE BUDGET, over the whole record. Two numbers and one sentence, because
    # the answer to "are we spending our calls well?" on this record is not a
    # ranking problem: the cap has never bound.
    allowed = sum(r["score_cap"] for r in reports if isinstance(r["score_cap"], int))
    spent = sum(r["scored"] for r in reports if isinstance(r["scored"], int))
    idle = sum(r["unspent_calls"] for r in reports if r["unspent_calls"] is not None)
    missed_total = sum(len(r["missed"]) for r in reports)
    dollar_total = sum(r["dollar_listed"] for r in reports)
    print(f"  Call budget over these {len(reports)} run(s): {spent} of {allowed} allowed, "
          f"{idle} unspent.")
    if idle:
        print(f"    The cap did not bind on any of them. {missed_total} canonical 4% match(es) "
              f"and {dollar_total} $ breakout(s) went unscored over the same nights, "
              f"against {idle} idle call(s).")
        print("    That is a funnel that is not delivering enough to spend the budget on, "
              "not a budget that is too small.")
    else:
        print("    The cap bound on at least one night, so ranking what to spend it on "
              "is a live question here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
