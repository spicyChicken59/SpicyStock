"""Reaction admission: which discovered candidates the trade band and the chart
reads may consider, read off fields the run already wrote (4 November 2026).

Two routes discover a reaction candidate (``src/scans.py``, discovery v1): the
4% scan -- a close at least 4% over the previous close on volume above the
previous session's -- and the dollar scan -- a close at least $0.90 over the
OPEN on 100,000 shares. The dollar day is a body in dollars. It asks nothing
of the day's gain, its range or its volume against the previous session, so on
a $500 stock a 0.2% day passes it, and so does a day that gapped down and
recovered. The checklist (``src/quality.py``) scores the base and the trend;
the one burst-day fact among its six scored letters is a close above the open,
which the dollar scan guarantees, and the two expansion checks it measures --
RE and VOL -- carry no weight. Over the 35 retained publications from 16
September to 3 November 2026, 1,913 of the 2,473 mechanical A-band grades came
through the dollar scan alone, 1,757 of them on a day under +4% and 91 on a day
that closed down, and 187 of the 244 chart reads went to such names.

The rule, the owner's decision of 4 November 2026 (the second of three options
put to him): a name the 4% scan discovered is admitted; a name the dollar scan
alone discovered is admitted only when its burst day shows the two expansion
checks the checklist already measures -- RE, today's range at least the
largest of the prior five sessions', and VOL, volume above the previous
session's (with the +CV rule where its base is long). Both are Bonde's own
words for a burst day ("bigger than the last 5 to 10 days bars", "volume above
yesterday"); no new number is written, the checks are the recorded ones, and
the pinned scan and checklist modules are untouched. Admission is never a
grade: the checklist's grade stands on every row, and a row that is not
admitted keeps it as research.

What admission reaches: the planning preview and the final plan
(``pipeline._make_plans``), the chart reads (``review_selection``: an
unadmitted name is blocked and is not research either), the refusal tolerance
(``reader_coverage.reads``: an unadmitted refused name would not have been
planned), the funnel (stage ``route``, after the grade and the veto), the
sealed plan gate (``provenance.gate``), the headline
(``report.reader_pending``) and the page's A-quality lens. A record from
before the rule -- no ``admission`` block on its rows, no ``admission`` family
in its rules -- is read as it was written: every graded name admitted.
"""
from __future__ import annotations

import json

VERSION = 1
POLICY = "burst_route_or_dollar_expansion_v1"
#: the discovery routes (``bursts[].scan``) the 4% scan is part of
BURST_ROUTES = ("burst", "both")
DOLLAR_ROUTE = "dollar"
#: the checklist letters a dollar-only day must pass, and the block's word for each
DOLLAR_CHECKS = (("RE", "range_expansion"), ("VOL", "higher_volume"))
BASES = ("burst_route", "dollar_expansion", "dollar_no_expansion")
#: the words a row that is not admitted is stopped under: the funnel's stage label
#: and the start of the row's own reason
NOT_ADMITTED_WORDS = "dollar scan alone, without a range-expansion, higher-volume day"
LABELS = {
    "burst_route": "admitted by the 4% scan",
    "dollar_expansion": "admitted by the dollar scan on a range-expansion, higher-volume day",
    "dollar_no_expansion": NOT_ADMITTED_WORDS + ": research only, no ticket and no chart read",
}
RULES = {"admission.version": VERSION, "admission.policy": POLICY,
         "admission.burst_routes": list(BURST_ROUTES),
         "admission.dollar_checks": [letter for letter, _ in DOLLAR_CHECKS]}
#: how many rows a validator fault names before it counts the rest
NAMED_FAULTS = 5


def expansion(row: dict) -> dict:
    """The two expansion checks as the checklist recorded them for this row,
    by the block's word for each: True or False as recorded, None when the
    check could not be read (an unreadable prior session) or the row carries
    no such check."""
    quality = row.get("quality") if isinstance(row, dict) else None
    checks = quality.get("checks") if isinstance(quality, dict) else None
    words = dict(DOLLAR_CHECKS)
    found: dict = {}
    for check in checks if isinstance(checks, list) else []:
        if isinstance(check, dict) and check.get("letter") in words and words[check["letter"]] not in found:
            passed = check.get("passed")
            found[words[check["letter"]]] = passed if isinstance(passed, bool) else None
    return {name: found.get(name) for _, name in DOLLAR_CHECKS}


def basis_of(route, shown: dict) -> str:
    """The basis a route and its expansion checks admit a row under; a route
    the scanner does not write is refused by name."""
    if route in BURST_ROUTES:
        return "burst_route"
    if route == DOLLAR_ROUTE:
        return "dollar_expansion" if all(v is True for v in shown.values()) else "dollar_no_expansion"
    raise ValueError(f"unknown discovery route {route!r}")


def block(row: dict) -> dict:
    """``bursts[].admission``: the route, the basis it is admitted under or
    stopped at, the two expansion checks as recorded, and the reason in the
    words the page and the mail print. Read off ``scan`` and
    ``quality.checks`` alone, so the validator re-derives it from the row."""
    shown = expansion(row)
    basis = basis_of(row.get("scan"), shown)
    return {"version": VERSION, "policy": POLICY, "route": row.get("scan"), "basis": basis,
            "admitted": basis != "dollar_no_expansion", "expansion": shown, "reason": LABELS[basis]}


def admitted(row: dict) -> bool:
    """Whether a row may be planned and read: its block's answer; True for a
    row from before the rule, which carries none; False for a block that does
    not say so, so a half-written block earns nothing."""
    blk = row.get("admission") if isinstance(row, dict) else None
    if blk is None:
        return True
    return isinstance(blk, dict) and blk.get("admitted") is True


def _canonical(value) -> str | None:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        return None


def summary(bursts: list, trade_grades) -> dict:
    """``run.admission``: how many candidates each basis admitted or stopped,
    and the same over the names in the trade band without a veto -- the ones
    the grade and the veto alone would have let through -- with one sentence.
    Read off the rows' own blocks, so a record is held to it."""
    rows = [b for b in (bursts or []) if isinstance(b, dict)]
    trade = tuple(trade_grades) if isinstance(trade_grades, (list, tuple)) else ()
    by_basis = {k: 0 for k in BASES}
    in_band = {"total": 0, **{k: 0 for k in BASES}}
    for b in rows:
        blk = b.get("admission")
        basis = blk.get("basis") if isinstance(blk, dict) else None
        if basis in by_basis:
            by_basis[basis] += 1
        if b.get("grade_mechanical") in trade and not b.get("vetoes"):
            in_band["total"] += 1
            if basis in by_basis:
                in_band[basis] += 1
    out = {"version": VERSION, "policy": POLICY, "candidates": len(rows),
           "admitted": by_basis["burst_route"] + by_basis["dollar_expansion"],
           "by_basis": by_basis, "in_band": in_band}
    out["sentence"] = sentence(out)
    return out


def _n(count: int, one: str, many: str | None = None) -> str:
    return f"{count} {one if count == 1 else (many or one + 's')}"


def _are(count: int) -> str:
    return "is" if count == 1 else "are"


def sentence(block: dict) -> str:
    """The night's admission in words, composed from the block's counts alone."""
    n, by, band = block["candidates"], block["by_basis"], block["in_band"]
    if n == 0:
        return "Admission: no reaction candidate was discovered."
    parts = [f"Admission: {_n(n, 'reaction candidate')}, {block['admitted']} admitted to the trade band and the "
             f"chart reads ({by['burst_route']} by the 4% scan, {by['dollar_expansion']} by the dollar scan on a "
             f"range-expansion, higher-volume day); {by['dollar_no_expansion']} came through the dollar scan alone "
             f"without one and {_are(by['dollar_no_expansion'])} research only."]
    if band["total"] == 0:
        parts.append("No mechanical A-band name without a veto tonight.")
    else:
        kept = band["burst_route"] + band["dollar_expansion"]
        parts.append(f"Of the {_n(band['total'], 'mechanical A-band name')} without a veto, {kept} {_are(kept)} "
                     f"admitted and {band['dollar_no_expansion']} {_are(band['dollar_no_expansion'])} not.")
    parts.append("Admission is read off the recorded discovery route and the checklist's own range-expansion and "
                 "volume checks; it is never a grade, and the chart reader never sees a name it stops.")
    return " ".join(parts)


def faults(data: dict) -> list[str]:
    """The admission blocks held to the record they sit in: under rules that
    archive the admission family, every reaction row carries the block its
    own ``scan`` and checklist re-derive, and ``run.admission`` is the summary
    over the RE-DERIVED blocks under the archived trade grades (so a forged or
    missing row block is one fault, and a forged run block another); under
    rules that archive none, no row and no run carries one. A version this
    module does not know is a fault by name."""
    rules = data.get("rules") if isinstance(data.get("rules"), dict) else {}
    archived = rules.get("admission")
    bursts = [b for b in (data.get("bursts") or []) if isinstance(b, dict)]
    run = data.get("run") if isinstance(data.get("run"), dict) else {}
    if not isinstance(archived, dict):
        out = []
        if any("admission" in b for b in bursts):
            out.append("admission block beside rules that archive no admission rule")
        if "admission" in run:
            out.append("run.admission beside rules that archive no admission rule")
        return out
    if type(archived.get("version")) is not int or archived["version"] != VERSION:
        return ["admission archived version is unknown"]
    out: list[str] = []
    wrong: list[str] = []
    # the rows as their own route and checks re-derive them: what run.admission
    # is held to, so one forged or missing row block is one fault and never two
    truth: list[dict] = []
    for b in bursts:
        ticker = str(b.get("ticker", "?"))
        try:
            again = block(b)
        except ValueError:
            wrong.append(f"{ticker}: admission cannot be re-derived from its route")
            truth.append(b)
            continue
        truth.append({**b, "admission": again})
        if "admission" not in b:
            wrong.append(f"{ticker}: admission block missing")
            continue
        mine = _canonical(b["admission"])
        if mine is None or mine != _canonical(again):
            wrong.append(f"{ticker}: admission is not the row's own")
    if len(wrong) > NAMED_FAULTS:
        out.extend(wrong[:NAMED_FAULTS])
        out.append(f"{len(wrong) - NAMED_FAULTS} more rows' admission blocks are not the record's own")
    else:
        out.extend(wrong)
    trade = (rules.get("pipeline") or {}).get("trade_grades") if isinstance(rules.get("pipeline"), dict) else None
    if not isinstance(trade, list):
        out.append("admission needs the archived pipeline.trade_grades")
        return out
    expected = _canonical(summary(truth, trade))
    mine = _canonical(run.get("admission")) if "admission" in run else None
    if mine is None or mine != expected:
        out.append("run.admission is not the record's own" if "admission" in run else "run.admission missing")
    return out
