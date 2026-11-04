"""Versioned chart-review allocation, never order or grade authority.

Use the private mechanical plan to cover feasible candidates first. Spare
capacity retains a bounded near-admission research sample; it is not a random
sample of the market. Neither selection nor a successful preview is a ticket.
"""
from collections import Counter
from datetime import date
import hashlib

from src import admission, event_risk, plan, reader_coverage

# 2 (4 Nov 2026): a name the discovery admission stops (src/admission.py: the
# dollar scan alone, without a range-expansion, higher-volume day) is blocked
# as `route_not_admitted` and is not research either, so no chart read is
# spent on a name that cannot be planned. Version 1 had no such blocker and
# its research pool was every infeasible mechanical A-band name; a record that
# archived it is replayed with that pool, because its rows carry no admission
# block (admission.admitted() reads such a row as admitted).
VERSION = 2
POLICY = "account_feasible_first_research_v2"
RESEARCH_MAX = 2
RANKED_RESEARCH = 1
GRADE_ORDER = ("A+", "A", "B", "C", "skip")
PURPOSES = ("opportunity", "research_ranked", "research_rotating")
BLOCKERS = ("grade_not_admitted", "quality_veto", "route_not_admitted", "preview_unavailable",
            "known_event", "plan_withheld", "no_whole_share", "no_order")
#: the blocker that also keeps a name out of the research pool
ROUTE_BLOCKER = "route_not_admitted"
POLICY_V1 = "account_feasible_first_research_v1"
#: each archived policy's version and the blockers its receipt counted, in order
VERSION_BY_POLICY = {POLICY_V1: 1, POLICY: VERSION}
BLOCKERS_BY_POLICY = {POLICY_V1: tuple(b for b in BLOCKERS if b != ROUTE_BLOCKER), POLICY: BLOCKERS}
RULES = {
    "review_selection.version": VERSION,
    "review_selection.policy": POLICY,
    "review_selection.research_max": RESEARCH_MAX,
    "review_selection.ranked_research": RANKED_RESEARCH,
    "review_selection.grade_order": list(GRADE_ORDER),
    "review_selection.order": "mechanical_grade,descending_score,ticker",
    "review_selection.rotation": "sha256(policy|measured_session|ticker),ticker",
    "review_selection.research_pool": "infeasible mechanical pipeline.trade_grades, discovery admitted",
    "review_selection.feasibility": "private per-candidate plan before reader and combined allocation",
}
#: version 1's archived rules, frozen as every publication from 10 October to
#: 3 November 2026 carries them, so such a record is replayed under its own
#: policy: no route blocker, its research pool every infeasible A-band name
RULES_V1 = {
    "version": 1, "policy": POLICY_V1, "research_max": RESEARCH_MAX, "ranked_research": RANKED_RESEARCH,
    "grade_order": list(GRADE_ORDER), "order": "mechanical_grade,descending_score,ticker",
    "rotation": "sha256(policy|measured_session|ticker),ticker",
    "research_pool": "infeasible mechanical pipeline.trade_grades",
    "feasibility": "private per-candidate plan before reader and combined allocation",
}
def replayable_rules() -> tuple:
    """The rules families this module replays a record under: its own, read at
    call time so a changed constant is seen, and version 1's frozen copy."""
    return ({k.partition(".")[2]: v for k, v in RULES.items()}, RULES_V1)


def supported(archived) -> bool:
    """Whether a record's archived selection rules are ones this module replays
    exactly: the current family, or version 1's frozen copy."""
    return isinstance(archived, dict) and any(archived == rules for rules in replayable_rules())


def rank_key(row):
    grade = row.get("grade_mechanical")
    return (GRADE_ORDER.index(grade) if grade in GRADE_ORDER else len(GRADE_ORDER),
            -(row.get("score") or 0), row["ticker"])


def blockers(row, admitted, policy=POLICY):
    """Only claim checks actually performed by the private preview; the route
    blocker is version 2's, and a version-1 row carries no admission block."""
    reasons = []
    if row.get("grade_mechanical") not in admitted:
        reasons.append("grade_not_admitted")
    if row.get("vetoes"):
        reasons.append("quality_veto")
    if ROUTE_BLOCKER in BLOCKERS_BY_POLICY[policy] and not admission.admitted(row):
        reasons.append(ROUTE_BLOCKER)
    preview = row.get("plan")
    if not isinstance(preview, dict):
        return reasons or ["preview_unavailable"]
    if (preview.get("event_risk") or {}).get("blocked"):
        reasons.append("known_event")
    elif preview.get("eligible") is not True:
        reasons.append("plan_withheld")
    if type(preview.get("shares")) is not int or preview["shares"] <= 0:
        reasons.append("no_whole_share")
    if not reasons and preview.get("action") not in plan.ORDER_ACTIONS:
        reasons.append("no_order")
    return reasons


def select(rows, session, *, max_reads, admitted, research_grades, policy=POLICY):
    """Return ordered ticker decisions without changing rows or their plans,
    under ``policy``: the current one, or an archived one a record is replayed
    under (``replay()``), whose blockers and rotation seed are its own."""
    if type(max_reads) is not int or max_reads < 0:
        raise ValueError("review budget must be a nonnegative integer")
    if policy not in BLOCKERS_BY_POLICY:
        raise ValueError(f"unknown review selection policy {policy!r}")
    session = date.fromisoformat(str(session)).isoformat()
    ordered = sorted(rows, key=rank_key)
    if len({r["ticker"] for r in ordered}) != len(ordered):
        raise ValueError("duplicate review candidate")
    decisions = {}
    for row in ordered:
        blocked = blockers(row, admitted, policy)
        research = bool(blocked) and row.get("grade_mechanical") in research_grades and ROUTE_BLOCKER not in blocked
        decisions[row["ticker"]] = {
            "policy": policy, "feasible": not blocked, "blockers": blocked,
            "research_pool": research, "selected": False,
            "purpose": "budget_not_selected" if not blocked else
                       "research_cap_not_selected" if research else "outside_research_pool",
        }
    opportunity = [t for t, d in decisions.items() if d["feasible"]][:max_reads]
    for ticker in opportunity:
        decisions[ticker].update(selected=True, purpose="opportunity")
    research = [t for t, d in decisions.items() if d["research_pool"]]
    room = min(RESEARCH_MAX, max_reads - len(opportunity), len(research))
    ranked = research[:min(RANKED_RESEARCH, room)]
    for ticker in ranked:
        decisions[ticker].update(selected=True, purpose="research_ranked")
    rotating = sorted(research[len(ranked):], key=lambda t:
        (hashlib.sha256(f"{policy}|{session}|{t}".encode()).hexdigest(), t))[:room - len(ranked)]
    for ticker in rotating:
        decisions[ticker].update(selected=True, purpose="research_rotating")
    return decisions, opportunity + ranked + rotating


def receipt(rows, decisions, selected, session, *, max_reads, policy=POLICY):
    """Selection counts and observed attempts; no estimated token/dollar costs.
    The receipt's version and blocker keys are the ``policy``'s own."""
    if policy not in BLOCKERS_BY_POLICY:
        raise ValueError(f"unknown review selection policy {policy!r}")
    by_ticker = {r["ticker"]: r for r in rows}
    counts = {p: {"requested": 0, "accepted": 0, "unaccepted": 0, "refused": 0, "attempts": 0}
              for p in PURPOSES}
    for ticker in selected:
        row = by_ticker[ticker]
        bucket = counts[decisions[ticker]["purpose"]]
        accepted = reader_coverage.accepted(row)
        reader = row.get("claude") or {}
        bucket["requested"] += 1
        bucket["accepted" if accepted else "unaccepted"] += 1
        bucket["refused"] += int(not accepted and reader_coverage.failure_of(reader.get("error")) == "refused")
        bucket["attempts"] += len(reader.get("attempts") or [])
    blocked = Counter(reason for d in decisions.values() for reason in d["blockers"])
    return {
        "version": VERSION_BY_POLICY[policy], "policy": policy, "session": str(session),
        "max_reads": max_reads, "research_max": RESEARCH_MAX,
        "discovered": len(rows), "feasible": sum(d["feasible"] for d in decisions.values()),
        "blockers": {reason: blocked[reason] for reason in BLOCKERS_BY_POLICY[policy]},
        "research_pool": sum(d["research_pool"] for d in decisions.values()),
        "selected": [{"ticker": t, "purpose": decisions[t]["purpose"]} for t in selected],
        "requested": len(selected), "by_purpose": counts,
        "feasible_unselected": sum(d["feasible"] and not d["selected"] for d in decisions.values()),
        "unused_capacity": max_reads - len(selected),
        "attempts": sum(c["attempts"] for c in counts.values()),
    }


def replay(data):
    """Reproduce previews with the production planner and archived event facts,
    under the selection policy the record archived (``supported()``: this
    module's own or version 1's frozen rules; any other is refused by name).

    Call only with compatible planner rules. Original review results stay
    unchanged: replaying a selection cannot invent a missing model response.
    """
    archived = data["rules"].get("review_selection")
    if not supported(archived):
        raise ValueError("archived review selection rules are not ones this module replays")
    policy = archived["policy"]
    rules = data["rules"]["pipeline"]
    regime = data["breadth"]["regime"]
    admitted = reader_coverage.admitted(regime["verdict"], rules["trade_grades"], rules["yellow_grades"])
    account = plan.Account(**{k: data["account"][k] for k in
                             ("equity", "risk_pct", "max_position_pct", "max_open_positions")})
    rows = []
    for original in data["bursts"]:
        row = {**original, "plan": None}
        # the preview the policy would have made: under version 2 a stopped name has none
        # (the run never previews it); version 1 read no block, so neither does its replay
        if row["grade_mechanical"] in admitted and not row["vetoes"] and (
                ROUTE_BLOCKER not in BLOCKERS_BY_POLICY[policy] or admission.admitted(row)):
            try:
                preview = plan.burst_plan(ticker=row["ticker"], close=row["close"], low=row["low"], high=row["high"],
                    open_=row["open"], prev_close=row["prev_close"], gain_pct=row["gain_pct"] or 0.0,
                    account=account, size_multiplier=float(regime["size_multiplier"]),
                    scan="dollar" if row["scan"] == "dollar" else "4pct", extension_pct=row.get("extension_pct"))
            except ValueError:
                pass
            else:
                if "event_risk" in data["rules"]:
                    preview = event_risk.apply(preview, row["ticker"], data["run"]["session"],
                                              registry=data["rules"]["event_risk"]["registry"])
                row["plan"] = preview
        rows.append(row)
    decisions, selected = select(rows, data["run"]["session"], max_reads=rules["max_reads"],
                                 admitted=admitted, research_grades=rules["trade_grades"], policy=policy)
    return decisions, receipt(rows, decisions, selected, data["run"]["session"], max_reads=rules["max_reads"],
                              policy=policy)
