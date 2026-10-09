"""One model allocation for reaction and anticipation tickets.

This records model principal, never the owner's broker balance or settled cash.
Unfinished or unmeasured plans retain their full original principal until the
model resolves them; partial sales do not free spending capacity here.
"""
from copy import deepcopy
import math

from src import plan

POLICY = "combined_stages_reserved_principal_v1"
OCCUPIED_STATUSES = ("hold", "sell_half", "sell_into_strength", "pending", "uncertain", "unmeasured", "unreadable")


def reservation(rows, account):
    occupied = [row for row in rows if row.get("status") in OCCUPIED_STATUSES]
    amounts = []
    for row in occupied:
        shares = row.get("shares")
        prices = [row.get("entry_ref"), row.get("limit")]
        prices = [p for p in prices if isinstance(p, (int, float)) and not isinstance(p, bool)
                  and math.isfinite(p) and p > 0]
        if not prices or not isinstance(shares, int) or isinstance(shares, bool) or shares < 0:
            # An unknown commitment must never become free capacity.
            amounts.append(account.equity)
        else:
            amounts.append(plan._money(shares * max(prices)))
    return {"open_positions": len(occupied), "open_committed_usd": plan._money(math.fsum(amounts)),
            "open_symbols": sorted({row["ticker"] for row in occupied if row.get("ticker")})}


def budget(plans, account, open_plans):
    return plan.cash_budget(plans, account, **reservation(open_plans, account))


def cut_for(p, cash_budget):
    return next((cut for cut in cash_budget.get("cut", [])
                 if cut["ticker"] == p["ticker"] and cut.get("setup_kind", p.get("kind")) == p.get("kind")), None)


def apply(p, cash_budget):
    """Remove every cut ticket's executable order, retaining its setup levels."""
    out = deepcopy(p)
    cut = cut_for(p, cash_budget)
    admitted = any(row["ticker"] == p["ticker"] and row.get("setup_kind") == p.get("kind")
                   for row in cash_budget.get("admitted", []))
    out["allocation"] = {"policy": POLICY, "admitted": admitted,
                         "reason": cut["kind"] if cut else None}
    if cut and p.get("action") in plan.ORDER_ACTIONS:
        out.update(action="refused", reason=cut["reason"], **plan.NO_ORDER)
    return out
