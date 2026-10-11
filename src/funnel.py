"""One reconciled account of where every discovered candidate stopped.

The funnel is derived from fields the run already wrote -- the regime, the
mechanical and final grades, the vetoes, the review selection and the reader's
state, each plan and the combined allocation -- and adds no measurement, no
gate and no permission. Every reaction candidate and every top anticipation
row is given exactly one terminal stage, in the order the pipeline applies its
gates, so the stage counts sum to the discovered count by construction and the
page prints them without arithmetic of its own. A field a record does not
carry is named ``unknown``, never guessed: an older publication is read for
what it recorded.
"""
from collections import Counter

from src import allocation, grader, plan, reader_coverage

VERSION = 1
POLICY = "candidate_funnel_v1"
RULES = {"funnel.version": VERSION, "funnel.policy": POLICY}

#: the terminal stages a reaction candidate can stop at, in gate order
REACTION_STAGES = (
    "market", "grade", "veto",
    "preview_event", "preview_geometry", "preview_sizing", "preview_no_order", "preview_unavailable",
    "review_budget", "review_unselected", "review_refused", "review_format", "review_account",
    "review_credit", "review_transport", "review_downgraded", "review_unknown",
    "plan_error", "plan_unavailable",
    "event", "geometry", "sizing", "allocation_slot", "allocation_cash", "allocation_occupied",
    "allocation_unknown", "ticket", "unknown",
)
#: the terminal stages a listed anticipation setup can stop at
ANTICIPATION_STAGES = (
    "market", "plan_error", "plan_unavailable",
    "event", "geometry", "sizing", "allocation_slot", "allocation_cash", "allocation_occupied",
    "allocation_unknown", "ticket", "unknown",
)
#: the group each stage is printed under
GROUPS = {
    "market": "market", "grade": "grade", "veto": "veto",
    "preview_event": "preview", "preview_geometry": "preview", "preview_sizing": "preview",
    "preview_no_order": "preview", "preview_unavailable": "preview",
    "review_budget": "review", "review_unselected": "review", "review_refused": "review",
    "review_format": "review", "review_account": "review", "review_credit": "review",
    "review_transport": "review", "review_downgraded": "review", "review_unknown": "review",
    "plan_error": "plan", "plan_unavailable": "plan",
    "event": "event", "geometry": "geometry", "sizing": "sizing",
    "allocation_slot": "allocation", "allocation_cash": "allocation",
    "allocation_occupied": "allocation", "allocation_unknown": "allocation",
    "ticket": "ticket", "unknown": "unknown",
}
#: one vocabulary, written into the record so the page and the mail print it
LABELS = {
    "market": "market gate: the regime admits no new longs",
    "grade": "mechanical grade below the regime's admitted band",
    "veto": "quality veto",
    "preview_event": "known corporate event, in the pre-review preview",
    "preview_geometry": "stop rule at the limit, in the pre-review preview",
    "preview_sizing": "no whole share, in the pre-review preview",
    "preview_no_order": "no order action, in the pre-review preview",
    "preview_unavailable": "pre-review preview unavailable",
    "review_budget": "feasible, beyond the night's review budget",
    "review_unselected": "not selected for review; the selection's reasons were not archived",
    "review_refused": "review refused by reader authority or the discovery contract",
    "review_format": "review reply could not be read as a score",
    "review_account": "review stopped: the API refused the account",
    "review_credit": "review stopped: the API credit balance was too low",
    "review_transport": "review got no usable answer from the API",
    "review_downgraded": "review lowered the grade below the admitted band",
    "review_unknown": "review state not readable from this record",
    "plan_error": "planner error",
    "plan_unavailable": "plan not recorded",
    "event": "known corporate event",
    "geometry": "ticket withheld: stop rule at the limit",
    "sizing": "no whole share fits the risk budget",
    "allocation_slot": "slot cap",
    "allocation_cash": "model cash cap",
    "allocation_occupied": "symbol already held by an open model plan, or duplicated",
    "allocation_unknown": "allocation outcome not recorded",
    "ticket": "ticket",
    "unknown": "not readable from this record",
}
#: the pre-review preview's blockers, first match wins, in the selector's own order
PREVIEW_BLOCKERS = (("known_event", "preview_event"), ("plan_withheld", "preview_geometry"),
                    ("no_whole_share", "preview_sizing"), ("no_order", "preview_no_order"),
                    ("preview_unavailable", "preview_unavailable"))
#: the combined allocation's cut kinds, to the stage each is
CUT_STAGES = {"slot_cap": "allocation_slot", "equity": "allocation_cash", "no_shares": "sizing",
              "existing_position": "allocation_occupied", "duplicate": "allocation_occupied",
              "no_new_longs": "market"}
WATCH_COUNTS = ("momentum", "quiet", "admitted", "top", "also_quiet")


def _get(obj, *keys):
    for key in keys:
        obj = obj.get(key) if isinstance(obj, dict) else None
    return obj


def admitted_grades(data):
    """The grades the record's regime admitted to a plan, read off the record's
    own archived rules; None when the record does not carry them."""
    rules = _get(data, "rules", "pipeline")
    verdict = _get(data, "breadth", "regime", "verdict")
    if not isinstance(rules, dict) or verdict not in ("green", "yellow", "red"):
        return None
    trade, yellow = rules.get("trade_grades"), rules.get("yellow_grades")
    if not isinstance(trade, list) or not isinstance(yellow, list):
        return None
    return reader_coverage.admitted(verdict, trade, yellow)


def _planned_stage(p, cash_budget, trades, kind, ticker):
    """Where a constructed plan stopped: the combined allocation's own answer
    first, the cash budget's cut when a record predates that block, the trade
    list for a legacy ticket, and ``allocation_unknown`` otherwise."""
    blocked = bool(_get(p, "event_risk", "blocked"))
    alloc = p.get("allocation")
    if isinstance(alloc, dict):
        if alloc.get("admitted") is True:
            return "ticket"
        reason = alloc.get("reason")
        if reason == "withheld":
            return "event" if blocked else "geometry"
        return CUT_STAGES.get(reason, "allocation_unknown")
    cut = allocation.cut_for({"ticker": ticker, "kind": kind}, cash_budget if isinstance(cash_budget, dict) else {})
    if cut:
        if cut.get("kind") == "withheld":
            return "event" if blocked else "geometry"
        return CUT_STAGES.get(cut.get("kind"), "allocation_unknown")
    # a record from before the combined allocation: a reaction ticket is a name in
    # trades with an order, an anticipation ticket an eligible plan with an order
    # and a whole share -- the record's own old definitions, never a new one
    ordered = p.get("action") in plan.ORDER_ACTIONS
    if kind == "burst" and isinstance(trades, list) and ticker in trades and ordered:
        return "ticket"
    if kind == "anticipation" and ordered and p.get("eligible") is True \
            and type(p.get("shares")) is int and p["shares"] > 0:
        return "ticket"
    if p.get("eligible") is False or p.get("action") == "refused":
        return "event" if blocked else "geometry"
    if p.get("action") == "no_new_longs":
        return "market"
    if p.get("shares") == 0:
        return "sizing"
    return "allocation_unknown"


def _unplanned_stage(row):
    error = _get(row, "evidence", "planning", "error")
    return "plan_error" if isinstance(error, str) and error else "plan_unavailable"


def reaction_stage(row, admitted, cash_budget, trades):
    """The one terminal stage of a reaction candidate, in the pipeline's order:
    the regime, the mechanical grade, the veto, then the review selection's
    recorded reasons for an unreviewed name, the reader's state for a reviewed
    one, and the constructed plan's own allocation."""
    if admitted is None:
        return "unknown"
    if not admitted:
        return "market"
    mechanical = row.get("grade_mechanical")
    if not isinstance(mechanical, str):
        return "unknown"
    if mechanical not in admitted:
        return "grade"
    if row.get("vetoes"):
        return "veto"
    selection = row.get("review_selection")
    reader = row.get("claude")
    # a record from before the selection block names a selected name by its reader
    # block; the grader's own "not graded" row is a name it was handed and never read
    selected = (selection.get("selected") if isinstance(selection, dict)
                else isinstance(reader, dict) and reader.get("source") != grader.SOURCE_NOT_GRADED)
    if selected is not True:
        if not isinstance(selection, dict):
            return "review_unselected"
        blockers = selection.get("blockers") if isinstance(selection.get("blockers"), list) else []
        for blocker, stage in PREVIEW_BLOCKERS:
            if blocker in blockers:
                return stage
        return "review_budget" if not blockers else "review_unknown"
    if not isinstance(reader, dict):
        return "review_unknown"
    if not reader_coverage.accepted(row):
        if reader.get("source") == grader.SOURCE_CLAUDE:
            return "review_unknown"
        return "review_" + reader_coverage.failure_of(reader.get("error"))
    if row.get("grade") not in admitted:
        return "review_downgraded"
    p = row.get("plan")
    if not isinstance(p, dict):
        return _unplanned_stage(row)
    return _planned_stage(p, cash_budget, trades, "burst", row.get("ticker"))


def anticipation_stage(row, admitted, cash_budget):
    """The one terminal stage of a listed anticipation setup: the regime first,
    as for a reaction, then the plan's own allocation; a listed name without a
    plan names the planner's error."""
    if admitted is None:
        return "unknown"
    if not admitted:
        return "market"
    p = row.get("plan")
    if not isinstance(p, dict):
        return _unplanned_stage(row)
    return _planned_stage(p, cash_budget, None, "anticipation", row.get("ticker"))


def _counts(stages, names):
    counter = Counter(names)
    return {stage: counter.get(stage, 0) for stage in stages}


def build(data):
    """The funnel block for a record, read off the record alone."""
    admitted = admitted_grades(data)
    cash_budget = data.get("cash_budget") if isinstance(data.get("cash_budget"), dict) else {}
    trades = data.get("trades") if isinstance(data.get("trades"), list) else []
    bursts = [b for b in (data.get("bursts") or []) if isinstance(b, dict)]
    top = [r for r in (_get(data, "watchlist", "top") or []) if isinstance(r, dict)]
    reaction_rows = [{"ticker": b.get("ticker"), "stage": reaction_stage(b, admitted, cash_budget, trades)} for b in bursts]
    anticipation_rows = [{"ticker": r.get("ticker"), "stage": anticipation_stage(r, admitted, cash_budget)} for r in top]
    usable = sum(1 for b in bursts if admitted and b.get("grade_mechanical") in admitted and not b.get("vetoes"))
    counts = _get(data, "watchlist", "counts")
    counts = counts if isinstance(counts, dict) else {}
    block = {
        "version": VERSION, "policy": POLICY,
        "regime": _get(data, "breadth", "regime", "verdict"),
        "admitted_grades": list(admitted) if admitted is not None else None,
        "reaction": {
            "discovered": len(bursts),
            "potentially_usable": usable,
            "by_mechanical_grade": {g: sum(1 for b in bursts if b.get("grade_mechanical") == g) for g in grader.GRADES},
            "stages": _counts(REACTION_STAGES, (r["stage"] for r in reaction_rows)),
            "rows": reaction_rows,
        },
        "anticipation": {
            "listed": len(top),
            "counts": {k: counts.get(k) for k in WATCH_COUNTS},
            "stages": _counts(ANTICIPATION_STAGES, (r["stage"] for r in anticipation_rows)),
            "rows": anticipation_rows,
        },
        "groups": dict(GROUPS), "labels": dict(LABELS),
    }
    block["sentence"] = sentence(block)
    return block


def _stopped(stages):
    return ", ".join(f"{n} {LABELS[s]}" for s, n in stages.items() if n and s != "ticket")


def _plural(n, one, many=None):
    return f"{n} {one if n == 1 else (many or one + 's')}"


def sentence(block):
    """The funnel in words, composed from its counts and labels only."""
    r, a = block["reaction"], block["anticipation"]
    regime = block.get("regime")
    market = (f"under a {regime.upper()} market" if isinstance(regime, str) and regime
              else "under a market this record does not name")
    parts = [f"Candidate funnel {market}: {r['discovered']} reaction "
             f"{'candidate' if r['discovered'] == 1 else 'candidates'} discovered, "
             f"{r['potentially_usable']} potentially usable (mechanical grade in the admitted band, no veto), "
             f"{r['stages'].get('ticket', 0)} reaction {'ticket' if r['stages'].get('ticket', 0) == 1 else 'tickets'}."]
    stopped = _stopped(r["stages"])
    if stopped:
        parts.append(f"Reaction candidates stopped at: {stopped}.")
    c = a["counts"]
    known = all(type(c.get(k)) is int for k in ("momentum", "quiet", "admitted"))
    # the watchlist's own counts: names with momentum, quiet ones, and the ones its coil checks admitted
    lead = (f"Anticipation: {_plural(c['momentum'], 'momentum name')}, {c['quiet']} quiet, "
            f"{c['admitted']} passing the coil checks, "
            if known else "Anticipation: ") + f"{a['listed']} listed, " \
           f"{_plural(a['stages'].get('ticket', 0), 'ticket')}."
    parts.append(lead)
    stopped = _stopped(a["stages"])
    if stopped:
        parts.append(f"Listed setups stopped at: {stopped}.")
    parts.append("A stage is where the record's own gates stopped a name; it is not a judgement of the setup "
                 "and establishes no entry.")
    return " ".join(parts)


def faults(data):
    """The funnel held to the record it sits in: present under rules that write
    it, and exactly what those rules re-derive from the record's own fields.
    A record made under older rules is not asked for one."""
    rules = data.get("rules") if isinstance(data.get("rules"), dict) else {}
    if not isinstance(rules.get("funnel"), dict):
        return []
    block = data.get("funnel")
    if not isinstance(block, dict):
        return ["funnel block missing"]
    try:
        again = build(data)
    except (KeyError, TypeError, ValueError, AttributeError):
        return ["funnel cannot be re-derived from this record"]
    if block != again:
        return ["funnel is not the record's own"]
    return []
