"""The trade plan: entry zone, stop, share count, exit schedule, order line.

Pure functions over plain floats and small dicts; no I/O beyond
``Account.from_env()`` reading four optional variables. Every number a plan
prints is a named constant here, archived in ``RULES`` under ``plan.<name>``
so the record says which plan rules produced a row.

Source marks on every constant:

* (B) Bonde's own number, quoted in ``knowledge/method.md`` and the research
  notes behind it (stops, exits, the 8-20% band, the trigger, the 2% gap).
* (P) this module's provisional number: a reading of a rule he states in
  words with no figure, or a small-account scaling of one of his. Each says
  what it is a reading OF.
* (T) a third party's measurement, not his: the theStrat Lab EP9M backtest
  and the Fluxus-Trade-Lab event study, both via the field guide.
* (R) a regulation or a broker rule, not a strategy number at all.

Three conventions the callers rely on. Prices are rounded to cents ONCE, on
the way in, and every derived price is rounded to cents again, so the number
a reader sees is the number the rule compared. Share counts are computed in
integer cents (``_cents_int``), never by flooring a float quotient, so $50
over an $0.80 stop is exactly 62 shares on every interpreter. And every
distance a plan judges -- the stop cascade, eligibility, the stop-risk
multiplier -- is measured from the PLANNED FILL, the price the shares are
sized at, so one number is compared everywhere.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta

import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

# --- the account -----------------------------------------------------------
#: (P) the brief's account. Overridden by ACCOUNT_EQUITY.
DEFAULT_EQUITY = 10_000.0
#: (B) inside his band: "most trades are around .25% to 1% risk". RISK_PCT.
DEFAULT_RISK_PCT = 0.5
#: (P) his "fully invested across 3-4 positions" scaled to a small account:
#: four quarters is fully invested. MAX_POSITION_PCT.
DEFAULT_MAX_POSITION_PCT = 25.0
#: (P) the other half of the same sentence. MAX_OPEN_POSITIONS.
DEFAULT_MAX_OPEN_POSITIONS = 4
#: (B) the low end of "most trades are around .25% to 1% risk".
RISK_PCT_BAND_LOW = 0.25
#: (B) the high end of the same band; he goes to 4% only on rare EPs.
RISK_PCT_BAND_HIGH = 1.0

# --- the burst entry (next morning, after an end-of-day scan) --------------
#: (P) an open more than this far UNDER the burst close is a burst already
#: failing; he expects "immediate follow through", not a give-back. The buy
#: stop sits AT the close, so such an open never fills unless it recovers.
ENTRY_BELOW_PCT = 2.0
#: (P) an open more than this far OVER the burst close has already delivered
#: his day-2 follow-through ("4 to 5% plus on second or third day"): day 2
#: spent before the fill. The buy stop-limit's ceiling.
ENTRY_ABOVE_PCT = 4.0
#: (B) "+8% same or next day -> exit 50%": a gap of that size is an entry he
#: would be SELLING into. The hard ceiling above ENTRY_ABOVE_PCT.
SKIP_GAP_PCT = 8.0
#: (B) "I enter most breakouts in first 30 minutes."
ENTRY_WINDOW = "first 30 minutes"
#: (P) the fill the shares are sized at: the burst close plus this. A real
#: fill is re-sized by the resize rule the plan prints.
ASSUMED_SLIPPAGE_PCT = 1.0

# --- the stop --------------------------------------------------------------
#: (B) "as far as possible I try and keep stop less than 4%". Wider is
#: refused (eligible False), the risk lens's rule 3.
MAX_STOP_PCT = 4.0
#: (B) "... and ideally less than 2%".
IDEAL_STOP_PCT = 2.0
#: (P) the risk lens's DERIVED reading of those two numbers: between the
#: ideal and the maximum the risk is halved (0.5% -> 0.25% of equity).
STOP_RISK_MULTIPLIER = 0.5

# --- the hazards (size, never eligibility) ---------------------------------
#: (T) Fluxus-Trade-Lab: >=15% burst days return -9.3% at 20 sessions with a
#: 36% win rate over 587 events, the worst cell in the only event study.
GAIN_CEILING_PCT = 15.0
#: (P) a close this far above its EXTENSION_SESSIONS-session average is
#: extended; the same hazard from the other side.
EXTENSION_HAZARD_PCT = 20.0
#: (P) the average the extension is measured over (the caller measures it).
EXTENSION_SESSIONS = 20
#: (P) what a hazard does to the risk budget: halves it.
HAZARD_MULTIPLIER = 0.5

# --- the targets -----------------------------------------------------------
#: (B) "8 to 20% in 3 to 5 days".
TARGET_LOW_PCT = 8.0
TARGET_HIGH_PCT = 20.0
#: (B) "lower priced stocks below 5 can go up to 40%": the band and its range.
LOW_PRICE_BAND_USD = 5.0
LOW_PRICE_TARGET_LOW_PCT = 20.0
LOW_PRICE_TARGET_HIGH_PCT = 40.0
#: (B) "above 40 ... 5 to 25 dollars": he measures those in dollars.
HIGH_PRICE_BAND_USD = 40.0
HIGH_PRICE_TARGET_LOW_USD = 5.0
HIGH_PRICE_TARGET_HIGH_USD = 25.0

# --- the exits (his 2018 exit guidelines) ---------------------------------
#: (B) "if the stock goes up 8% or more exit 50% of the position".
SELL_HALF_PCT = 8.0
#: (B) "abnormal profit in one day of 10% plus (at least part exit ...)".
ABNORMAL_DAY_PCT = 10.0
#: (B) "exit ... at open if it gaps up 20% or more after your entry".
GAP_EXIT_PCT = 20.0
#: (B) "move stop 25 to 50 cents below the high of the day": the two ends.
TRAIL_CENTS = 0.25
TRAIL_CENTS_MAX = 0.50
#: (B) "Exit at least 50% of position on third day at close."
SELL_HALF_DAY = 3
#: (B) "Exit on 3rd ... day if stock does not move much post entry."
NO_PROGRESS_DAY = 3
#: (P) a reading of "After 3rd day ... keep moving stop to low of day
#: everyday": the trail starts at the close of day 3, so day 4 opens with the
#: stop under day 3's low.
TRAIL_FROM_DAY = 3
#: (B) the "3 to 5 days" hold: the remainder goes on day 5.
FINAL_EXIT_DAY = 5
#: (B) "stop the low of entry day": once day 1 has closed the stop rises to
#: its low (the burst-day low was the stand-in before the entry day existed).
ENTRY_DAY = 1
#: (T) theStrat Lab EP9M backtest: break-even on day 2 collapses the win rate
#: (29.8% -> 7.25%); delaying to day 5 restores it. Not his; he moved KOD to
#: break-even inside 17 minutes. Recorded, not chosen between.
NO_BREAKEVEN_BEFORE_DAY = 5

# --- the anticipation entry ------------------------------------------------
#: (P) the cents in "order a few cents above the consolidation" (B).
TRIGGER_CENTS = 0.02
#: (P) the same, scaled for a high-priced name: 0.1% of the close.
TRIGGER_FRACTION = 0.001
#: (P) the buy-stop's limit: his BSLO has "a cap on price at which you will
#: buy"; the cap is not a number he gives.
TRIGGER_LIMIT_PCT = 1.0
#: (B) "A gap up of 2% is fine. If it gaps up more there is likely to be some
#: catalyst".
GAP_OK_PCT = 2.0
#: (B) "put in a stop near low of the day or low of last 2 to 3 days".
STOP_LOOKBACK_SESSIONS = 3
#: (P) the MOO/OPG open entry is for "the very best 1-2 names" (research
#: reading of his KOD trade), not the whole list.
OPEN_ENTRY_TOP_N = 2

# --- account constraints the page states (regulation and broker) -----------
#: (R) FINRA's pattern-day-trader count, as Fidelity may still apply it: a
#: margin account under this equity ...
PDT_EQUITY_USD = 25_000.0
#: (R) ... may make at most this many same-day round trips ...
PDT_MAX_DAY_TRADES = 3
#: (R) ... per rolling window of this many business days.
PDT_WINDOW_DAYS = 5
#: (R) FINRA deleted the count rule on this date (Regulatory Notice 26-10) ...
PDT_RULE_DELETED_ON = "2026-06-04"
#: (R) ... and lets a member keep applying it per account until this date.
#: Fidelity has announced no migration date.
PDT_PHASE_IN_ENDS = "2027-10-20"
#: (R) US equities settle T+1 since May 2024.
SETTLEMENT_DAYS = 1
#: (R) Fidelity: this many good-faith violations ...
GFV_LIMIT = 3
#: (R) ... in a rolling window of this many months ...
GFV_WINDOW_MONTHS = 12
#: (R) ... restricts the account to settled cash for this many days.
GFV_RESTRICTION_DAYS = 90

# --- precision -------------------------------------------------------------
#: Prices and money are rounded to cents, once.
CENTS = 2
#: Percentages are published to two decimals.
PCT_DECIMALS = 2

#: The archived constants. Every upper-case number this module names is read
#: here (a test derives that from the source), so a number added later cannot
#: escape the record in silence. Marks: see the module docstring.
RULES: dict[str, Any] = {
    "plan.default_equity": DEFAULT_EQUITY,
    "plan.default_risk_pct": DEFAULT_RISK_PCT,
    "plan.default_max_position_pct": DEFAULT_MAX_POSITION_PCT,
    "plan.default_max_open_positions": DEFAULT_MAX_OPEN_POSITIONS,
    "plan.risk_pct_band_low": RISK_PCT_BAND_LOW,
    "plan.risk_pct_band_high": RISK_PCT_BAND_HIGH,
    "plan.entry_below_pct": ENTRY_BELOW_PCT,
    "plan.entry_above_pct": ENTRY_ABOVE_PCT,
    "plan.skip_gap_pct": SKIP_GAP_PCT,
    "plan.entry_window": ENTRY_WINDOW,
    "plan.assumed_slippage_pct": ASSUMED_SLIPPAGE_PCT,
    "plan.max_stop_pct": MAX_STOP_PCT,
    "plan.ideal_stop_pct": IDEAL_STOP_PCT,
    "plan.stop_risk_multiplier": STOP_RISK_MULTIPLIER,
    "plan.gain_ceiling_pct": GAIN_CEILING_PCT,
    "plan.extension_hazard_pct": EXTENSION_HAZARD_PCT,
    "plan.extension_sessions": EXTENSION_SESSIONS,
    "plan.hazard_multiplier": HAZARD_MULTIPLIER,
    "plan.target_low_pct": TARGET_LOW_PCT,
    "plan.target_high_pct": TARGET_HIGH_PCT,
    "plan.low_price_band_usd": LOW_PRICE_BAND_USD,
    "plan.low_price_target_low_pct": LOW_PRICE_TARGET_LOW_PCT,
    "plan.low_price_target_high_pct": LOW_PRICE_TARGET_HIGH_PCT,
    "plan.high_price_band_usd": HIGH_PRICE_BAND_USD,
    "plan.high_price_target_low_usd": HIGH_PRICE_TARGET_LOW_USD,
    "plan.high_price_target_high_usd": HIGH_PRICE_TARGET_HIGH_USD,
    "plan.sell_half_pct": SELL_HALF_PCT,
    "plan.abnormal_day_pct": ABNORMAL_DAY_PCT,
    "plan.gap_exit_pct": GAP_EXIT_PCT,
    "plan.trail_cents": TRAIL_CENTS,
    "plan.trail_cents_max": TRAIL_CENTS_MAX,
    "plan.sell_half_day": SELL_HALF_DAY,
    "plan.no_progress_day": NO_PROGRESS_DAY,
    "plan.trail_from_day": TRAIL_FROM_DAY,
    "plan.final_exit_day": FINAL_EXIT_DAY,
    "plan.entry_day": ENTRY_DAY,
    "plan.no_breakeven_before_day": NO_BREAKEVEN_BEFORE_DAY,
    "plan.trigger_cents": TRIGGER_CENTS,
    "plan.trigger_fraction": TRIGGER_FRACTION,
    "plan.trigger_limit_pct": TRIGGER_LIMIT_PCT,
    "plan.gap_ok_pct": GAP_OK_PCT,
    "plan.stop_lookback_sessions": STOP_LOOKBACK_SESSIONS,
    "plan.open_entry_top_n": OPEN_ENTRY_TOP_N,
    "plan.pdt_equity_usd": PDT_EQUITY_USD,
    "plan.pdt_max_day_trades": PDT_MAX_DAY_TRADES,
    "plan.pdt_window_days": PDT_WINDOW_DAYS,
    "plan.pdt_rule_deleted_on": PDT_RULE_DELETED_ON,
    "plan.pdt_phase_in_ends": PDT_PHASE_IN_ENDS,
    "plan.settlement_days": SETTLEMENT_DAYS,
    "plan.gfv_limit": GFV_LIMIT,
    "plan.gfv_window_months": GFV_WINDOW_MONTHS,
    "plan.gfv_restriction_days": GFV_RESTRICTION_DAYS,
    "plan.precision.cents": CENTS,
    "plan.precision.pct_decimals": PCT_DECIMALS,
}

#: The environment variables ``Account.from_env()`` reads, and the field each
#: one fills. Blank or unset means the default.
ENV_VARS = {
    "ACCOUNT_EQUITY": "equity",
    "RISK_PCT": "risk_pct",
    "MAX_POSITION_PCT": "max_position_pct",
    "MAX_OPEN_POSITIONS": "max_open_positions",
}

#: What a sizing was decided by.
CAPPED_BY = ("risk", "position_cap", "multiplier", "none")
#: What a plan tells the reader to do. Only the first two carry an order.
ACTIONS = ("buy_at_open", "place_buy_stop", "no_new_longs", "no_order", "refused")
ORDER_ACTIONS = ("buy_at_open", "place_buy_stop")
#: The follow-through statuses, in the order the walk can produce them.
FOLLOW_STATUSES = ("pending", "hold", "sell_half", "sell_into_strength", "exit", "stopped", "expired")
#: The statuses of a plan that is still held (the red-regime clause applies).
HELD_STATUSES = ("hold", "sell_half", "sell_into_strength")
#: Where a burst stop came from.
STOP_BASES = ("burst_low", "half_range", "max_stop")
#: The two kinds of pick ``follow()`` walks.
KINDS = ("burst", "anticipation")
#: The breadth verdict that changes an open plan's instruction.
RED_REGIME = "red"
#: The clause a held plan's instruction gains under a red regime.
RED_CLAUSE = "Breadth is red: sell into any strength; do not add."
#: The same for a plan not yet opened.
RED_PENDING_CLAUSE = "Breadth is red: do not open it."


# ------------------------------------------------------------- helpers -----


def _money(value: float) -> float:
    """Round money or a price to cents, once."""
    return round(float(value), CENTS)


def _pct(value: float) -> float:
    return round(float(value), PCT_DECIMALS)


def _cents_int(value: float) -> int:
    """A price or a sum as whole cents, so share arithmetic is exact."""
    return int(round(value * 100))


def _price(value: Any, name: str) -> float:
    """A finite, positive number rounded to cents; anything else is refused
    by name, because a plan built on a NaN prints a NaN order line."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {value!r}")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number, got {value!r}")
    return _money(value)


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, got {value!r}")
    return float(value)


def _usd(value: float) -> str:
    return f"${value:,.2f}"


def _plus_pct(pct: float) -> str:
    return f"{pct:+.1f}%"


def _at_pct(price: float, pct: float) -> float:
    """``price`` moved by ``pct`` percent, rounded to cents."""
    return _money(price * (1 + pct / 100))


# ------------------------------------------------------------- account -----


@dataclass(frozen=True)
class Account:
    """The account a plan is sized for. All four have defaults; see ``RULES``."""

    equity: float = DEFAULT_EQUITY
    risk_pct: float = DEFAULT_RISK_PCT
    max_position_pct: float = DEFAULT_MAX_POSITION_PCT
    max_open_positions: int = DEFAULT_MAX_OPEN_POSITIONS

    def __post_init__(self) -> None:
        for name in ("equity", "risk_pct", "max_position_pct"):
            _price(getattr(self, name), name)
        if isinstance(self.max_open_positions, bool) or not isinstance(self.max_open_positions, int) \
                or self.max_open_positions < 1:
            raise ValueError(f"max_open_positions must be a whole number of at least 1, "
                             f"got {self.max_open_positions!r}")

    @property
    def risk_usd(self) -> float:
        """Dollars at risk per trade at the full multiplier."""
        return _money(self.equity * self.risk_pct / 100)

    @property
    def max_position_usd(self) -> float:
        return _money(self.equity * self.max_position_pct / 100)

    @property
    def within_bonde_band(self) -> bool:
        """Whether risk_pct sits in his ".25% to 1%" band."""
        return RISK_PCT_BAND_LOW <= self.risk_pct <= RISK_PCT_BAND_HIGH

    def to_dict(self) -> dict[str, Any]:
        """The ``account`` block of data.json."""
        return asdict(self)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Account":
        """Read ``ENV_VARS`` from ``env`` (default: the process environment).

        Blank or unset means the default; a value that is not a number raises
        ValueError naming the variable. MAX_OPEN_POSITIONS must be a whole
        number.
        """
        source = os.environ if env is None else env
        values: dict[str, Any] = {}
        for var, field in ENV_VARS.items():
            raw = (source.get(var) or "").strip()
            if not raw:
                continue
            try:
                values[field] = int(raw) if field == "max_open_positions" else float(raw)
            except ValueError:
                kind = "a whole number" if field == "max_open_positions" else "a number"
                raise ValueError(f"{var} must be {kind}, got {raw!r}") from None
        try:
            return cls(**values)
        except ValueError as exc:
            field = str(exc).split(" ", 1)[0]
            var = next((v for v, f in ENV_VARS.items() if f == field), field)
            raise ValueError(f"{var}: {exc}") from None


# ------------------------------------------------------------- sizing ------


@dataclass(frozen=True)
class Sizing:
    """A share count and what decided it.

    ``capped_by`` is the rule that produced ``shares``: ``risk`` when the
    risk budget did, ``position_cap`` when the cap cut the risk count,
    ``multiplier`` when the multiplier is 0, and ``none`` when the budget
    could not buy a single share, so no rule had anything to cap.
    """

    shares: int
    position_usd: float
    position_pct: float
    risk_usd: float
    risk_per_share: float
    stop_pct: float
    capped_by: str
    note: str | None
    multiplier: float
    budget_usd: float
    cap_usd: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def size(entry: float, stop: float, account: Account, multiplier: float = 1.0) -> Sizing:
    """Shares = floor(equity * risk% * multiplier / (entry - stop)), then no
    more than the position cap buys. (B: "shares = risk$/(entry - stop)".)

    Prices are rounded to cents first; the division is done in whole cents.
    """
    entry, stop = _price(entry, "entry"), _price(stop, "stop")
    multiplier = _number(multiplier, "multiplier")
    if multiplier < 0:
        raise ValueError(f"multiplier must not be negative, got {multiplier!r}")
    if entry <= stop:
        raise ValueError(f"entry {entry} must be above stop {stop}")
    risk_per_share = _money(entry - stop)   # at least a cent: both were rounded to cents above
    stop_pct = _pct(100 * (entry - stop) / entry)
    budget = _money(account.equity * account.risk_pct / 100 * multiplier)
    cap_usd = account.max_position_usd

    def built(shares: int, capped_by: str, note: str | None) -> Sizing:
        position = _money(shares * entry)
        return Sizing(shares=shares, position_usd=position,
                      position_pct=_pct(100 * position / account.equity),
                      risk_usd=_money(shares * risk_per_share), risk_per_share=risk_per_share,
                      stop_pct=stop_pct, capped_by=capped_by, note=note, multiplier=multiplier,
                      budget_usd=budget, cap_usd=cap_usd)

    if multiplier == 0:
        return built(0, "multiplier", "no new longs: the size multiplier is 0")
    by_risk = _cents_int(budget) // _cents_int(risk_per_share)
    if by_risk == 0:
        return built(0, "none", f"the {_usd(budget)} risk budget cannot buy one share "
                                f"at a {_usd(risk_per_share)} stop")
    by_cap = _cents_int(cap_usd) // _cents_int(entry)
    if by_risk > by_cap:
        return built(by_cap, "position_cap",
                     f"the risk budget buys {by_risk} shares ({_usd(_money(by_risk * entry))}), over the "
                     f"{account.max_position_pct:g}% cap of {_usd(cap_usd)}: cut to {by_cap}")
    return built(by_risk, "risk", None)


def resize_rule(budget_usd: float, stop: float, cap_usd: float) -> str:
    """The sentence a reader re-sizes a different fill with."""
    return (f"if your fill differs, shares = {_usd(budget_usd)} / (fill - {_usd(stop)}), "
            f"and no more than {_usd(cap_usd)} of stock")


def stop_risk(stop_pct: float) -> tuple[float, str | None]:
    """The stop-risk multiplier: 1 at or under the ideal stop, halved between
    the ideal and the maximum, and 1 past the maximum (that plan is refused
    on eligibility, not sized down)."""
    if IDEAL_STOP_PCT < stop_pct <= MAX_STOP_PCT:
        return STOP_RISK_MULTIPLIER, (f"the stop is {stop_pct:g}% from the planned fill: inside his "
                                      f"{MAX_STOP_PCT:g}% line, wider than his ideal {IDEAL_STOP_PCT:g}%, "
                                      f"so the risk is multiplied by {STOP_RISK_MULTIPLIER:g}")
    return 1.0, None


def hazards(gain_pct: float, extension_pct: float | None) -> list[dict[str, Any]]:
    """The size hazards a burst carries: each halves the risk, none vetoes."""
    found: list[dict[str, Any]] = []
    if gain_pct >= GAIN_CEILING_PCT:
        found.append({"kind": "gain_over_15", "multiplier": HAZARD_MULTIPLIER,
                      "detail": (f"a {gain_pct:g}% burst day is at or past {GAIN_CEILING_PCT:g}%, the worst "
                                 f"cell in the only event study (-9.3% at 20 sessions, 36% win rate)")})
    if extension_pct is not None and _number(extension_pct, "extension_pct") > EXTENSION_HAZARD_PCT:
        found.append({"kind": "extended", "multiplier": HAZARD_MULTIPLIER,
                      "detail": (f"the close is {_pct(extension_pct):g}% above its {EXTENSION_SESSIONS}-session "
                                 f"average, past {EXTENSION_HAZARD_PCT:g}%")})
    return found


# ------------------------------------------------------------- orders ------

#: The order block of a plan with nothing to place.
NO_ORDER: dict[str, Any] = {"order_line": None, "order_json": None, "order_readback": None,
                            "fallback_line": None}

#: The conditional word Fidelity's ticket uses for "then": the sell stop is
#: placed the moment the buy fills, never before.
OTO = "one_triggers_the_other"


def fidelity_orders(ticker: str, shares: int, *, trigger: float, limit: float, stop: float) -> dict[str, Any]:
    """A Fidelity buy stop-limit with the protective stop attached, as the
    line to type, the JSON, the preview read-back and a plain-limit fallback.

    The exit leg is a stop-MARKET order (never a stop-limit: a gap through the
    limit leaves it unfilled), the risk lens's rule 2.
    """
    trigger, limit, stop = _price(trigger, "trigger"), _price(limit, "limit"), _price(stop, "stop")
    if not (stop < trigger <= limit):
        raise ValueError(f"orders need stop < trigger <= limit, got {stop} / {trigger} / {limit}")
    if isinstance(shares, bool) or not isinstance(shares, int) or shares < 1:
        raise ValueError(f"an order needs a whole positive share count, got {shares!r}")
    return {
        "order_line": (f"Buy {shares} {ticker} stop-limit: stop {_usd(trigger)} limit {_usd(limit)}, day · "
                       f"OTO sell {shares} {ticker} stop-loss {_usd(stop)} GTC"),
        # Fidelity's field order: action, quantity, symbol, order type, stop,
        # limit, time in force; then the conditional leg, a stop-MARKET sell.
        "order_json": {"symbol": ticker, "action": "buy", "quantity": shares, "order_type": "stop_limit",
                       "stop_price": trigger, "limit_price": limit, "time_in_force": "day",
                       "conditional": OTO,
                       "then": {"action": "sell", "quantity": shares, "order_type": "stop",
                                "stop_price": stop, "time_in_force": "gtc"}},
        "order_readback": (f"Buy {shares} {ticker} stop limit {trigger:.2f} / {limit:.2f} day, "
                           f"one-triggers-the-other sell {shares} {ticker} stop loss {stop:.2f} GTC"),
        "fallback_line": (f"If your app has no stop-limit: buy {shares} {ticker} limit {_usd(limit)} (day) "
                          f"with the same sell stop attached."),
    }


# ------------------------------------------------------------- exits -------

#: The exit rules in his words made concrete, in the order ``follow()``
#: applies them. Templates are filled by ``exit_schedule()``.
EXIT_RULES: tuple[dict[str, str], ...] = (
    {"key": "sell_half_8pct", "source": "B",
     "when": "same or next day, the price reaches {sell_half} (+{sell_half_pct}% from {entry})",
     "rule": "sell half and move the stop to {trail_cents}-{trail_cents_max} cents under that day's high"},
    {"key": "abnormal_10pct", "source": "B",
     "when": "any single day closes at or above {abnormal} (+{abnormal_pct}%)",
     "rule": "take at least partial profit and move the stop up to protect the rest"},
    {"key": "gap_20pct", "source": "B",
     "when": "it opens at or above {gap_exit} (+{gap_exit_pct}%) after entry",
     "rule": "sell at the open (or pre-market)"},
    {"key": "entry_day_low", "source": "B",
     "when": "the close of day {entry_day}",
     "rule": "the stop rises to the entry day's low if that is above {stop}"},
    {"key": "day3_sell_half", "source": "B",
     "when": "day {sell_half_day} close",
     "rule": "sell at least half at the close"},
    {"key": "day3_no_progress", "source": "B",
     "when": "day {no_progress_day} closes at or below {entry}",
     "rule": "exit: no follow-through"},
    {"key": "trail_after_day3", "source": "P",
     "when": "from the close of day {trail_from_day}",
     "rule": "raise the stop to each day's low (it never moves down)"},
    {"key": "day5_exit", "source": "B",
     "when": "day {final_exit_day} close",
     "rule": "exit the remainder into strength"},
    {"key": "stop", "source": "B",
     "when": "the protective stop at {stop} is a stop-market order, live intraday from the moment the "
             "buy fills",
     "rule": "if it is somehow not filled, exit on any close below it"},
    {"key": "no_breakeven", "source": "T",
     "when": "day 2 is green",
     "rule": "do not move the stop to break-even before day {no_breakeven_day} just because it is green "
             "(theStrat Lab EP9M backtest: the win rate collapses from 29.8% to 7.25%; delaying to day "
             "{no_breakeven_day} restores it); the +{sell_half_pct}% raise above is a different rule"},
)


def exit_levels(entry_price: float) -> dict[str, float]:
    """The three price levels the exit rules name, from an entry price."""
    entry = _price(entry_price, "entry_price")
    return {"sell_half": _at_pct(entry, SELL_HALF_PCT),
            "abnormal": _at_pct(entry, ABNORMAL_DAY_PCT),
            "gap_exit": _at_pct(entry, GAP_EXIT_PCT)}


def exit_schedule(entry_price: float, stop: float | None = None) -> list[dict[str, Any]]:
    """``EXIT_RULES`` with the prices filled in from ``entry_price``."""
    entry = _price(entry_price, "entry_price")
    levels = exit_levels(entry)
    stop_price = _price(stop, "stop") if stop is not None else None
    values = {
        "entry": _usd(entry),
        "sell_half": _usd(levels["sell_half"]), "sell_half_pct": f"{SELL_HALF_PCT:g}",
        "abnormal": _usd(levels["abnormal"]), "abnormal_pct": f"{ABNORMAL_DAY_PCT:g}",
        "gap_exit": _usd(levels["gap_exit"]), "gap_exit_pct": f"{GAP_EXIT_PCT:g}",
        "trail_cents": f"{_cents_int(TRAIL_CENTS)}", "trail_cents_max": f"{_cents_int(TRAIL_CENTS_MAX)}",
        "entry_day": ENTRY_DAY, "sell_half_day": SELL_HALF_DAY, "no_progress_day": NO_PROGRESS_DAY,
        "trail_from_day": TRAIL_FROM_DAY, "final_exit_day": FINAL_EXIT_DAY,
        "no_breakeven_day": NO_BREAKEVEN_BEFORE_DAY,
        "stop": _usd(stop_price) if stop_price is not None else "the stop",
    }
    prices = {"sell_half_8pct": levels["sell_half"], "abnormal_10pct": levels["abnormal"],
              "gap_20pct": levels["gap_exit"], "day3_no_progress": entry, "stop": stop_price}
    return [{"key": rule["key"], "source": rule["source"],
             "when": rule["when"].format(**values), "rule": rule["rule"].format(**values),
             "price": prices.get(rule["key"])}
            for rule in EXIT_RULES]


def next_sessions(session: date, n: int) -> list[date]:
    """The next ``n`` weekdays after ``session``. No holiday calendar: a
    holiday shifts every later date by one, and the page says "day N" beside
    each date so the day count is the authority."""
    out: list[date] = []
    d = session
    while len(out) < n:
        d = d + timedelta(days=1)
        if d.weekday() < calendar.SATURDAY:
            out.append(d)
    return out


def dated_schedule(p: Mapping[str, Any], session: date) -> list[dict[str, Any]]:
    """The hold as a dated timeline for a plan published after ``session``:
    day 1 is the next weekday. Every price comes off the plan (``exits``,
    ``entry_low``/``entry_high`` or ``trigger``/``limit``, ``stop``); the
    sentences are the exit rules in his order."""
    days = next_sessions(session, FINAL_EXIT_DAY)
    by_key = {row["key"]: row for row in p.get("exits") or []}
    stop = p.get("stop")
    stop_words = f"the sell stop at {_usd(stop)} is live from the fill" if stop is not None else "attach the sell stop at the fill"
    if p.get("kind") == "anticipation":
        entry = (f"buy only if it trades through {_usd(p['trigger'])} (limit {_usd(p['limit'])}) in the "
                 f"{ENTRY_WINDOW}; {stop_words}.")
    else:
        lo, hi = p.get("entry_low"), p.get("entry_high")
        entry = (f"buy in the {ENTRY_WINDOW} inside {_usd(lo)}\u2013{_usd(hi)}; {stop_words}. "
                 f"Skip it if it opens above {_usd(hi)}.") if lo is not None and hi is not None else \
                f"buy in the {ENTRY_WINDOW}; {stop_words}."
    rows = [{"day": ENTRY_DAY, "date": days[0].isoformat(), "key": "entry", "instruction": entry}]

    def add(day: int, key: str, text: str) -> None:
        rows.append({"day": day, "date": days[day - 1].isoformat(), "key": key, "instruction": text})

    half = by_key.get("sell_half_8pct")
    if half:
        add(ENTRY_DAY, "sell_half_8pct", f"if {half['when']}: {half['rule']}.")
    low = by_key.get("entry_day_low")
    if low:
        add(ENTRY_DAY, "entry_day_low", f"at {low['when']}: {low['rule']}.")
    nb = by_key.get("no_breakeven")
    if nb:
        add(2, "no_breakeven", f"if {nb['when']}: {nb['rule'].split(' (')[0]}.")
    prog = by_key.get("day3_no_progress")
    d3 = by_key.get("day3_sell_half")
    if d3 or prog:
        text = " ".join(x for x in ((f"at the {d3['when']}: {d3['rule']}." if d3 else ""),
                                    (f"If {prog['when']}: {prog['rule']}." if prog else "")) if x)
        add(SELL_HALF_DAY, "day3", text)
    trail = by_key.get("trail_after_day3")
    if trail and TRAIL_FROM_DAY + 1 <= FINAL_EXIT_DAY:
        add(TRAIL_FROM_DAY + 1, "trail", f"{trail['rule']}; sell the rest into strength.")
    last = by_key.get("day5_exit")
    if last:
        add(FINAL_EXIT_DAY, "day5_exit", f"at the {last['when']}: {last['rule']}.")
    return rows


# ------------------------------------------------------------- targets -----


def targets(entry_price: float, close: float) -> dict[str, Any]:
    """His 8-20% band from the planned entry, with the price-band notes."""
    entry = _price(entry_price, "entry_price")
    close = _price(close, "close")
    block: dict[str, Any] = {
        "low_pct": TARGET_LOW_PCT, "high_pct": TARGET_HIGH_PCT,
        "low": _at_pct(entry, TARGET_LOW_PCT), "high": _at_pct(entry, TARGET_HIGH_PCT),
        "note": None, "dollar_low": None, "dollar_high": None,
    }
    if close < LOW_PRICE_BAND_USD:
        block["note"] = (f"under ${LOW_PRICE_BAND_USD:g} bursts can run "
                         f"{LOW_PRICE_TARGET_LOW_PCT:g}-{LOW_PRICE_TARGET_HIGH_PCT:g}%")
    elif close > HIGH_PRICE_BAND_USD:
        block["note"] = (f"above ${HIGH_PRICE_BAND_USD:g} he measures the move in dollars: "
                         f"${HIGH_PRICE_TARGET_LOW_USD:g}-{HIGH_PRICE_TARGET_HIGH_USD:g}")
        block["dollar_low"] = _money(entry + HIGH_PRICE_TARGET_LOW_USD)
        block["dollar_high"] = _money(entry + HIGH_PRICE_TARGET_HIGH_USD)
    return block


# ------------------------------------------------------------- the stop ----


def burst_stop(entry: float, low: float, high: float) -> dict[str, Any]:
    """The stop cascade, measured from the planned fill: the burst day's low,
    else its range midpoint, the first within MAX_STOP_PCT of ``entry``; else
    MAX_STOP_PCT under ``entry`` with a note (P), which is a stop the bar does
    not support and the plan refuses."""
    entry, low, high = _price(entry, "entry"), _price(low, "low"), _price(high, "high")
    candidates = []
    for basis, price in (("burst_low", low), ("half_range", _money((low + high) / 2))):
        pct = _pct(100 * (entry - price) / entry)
        candidates.append({"basis": basis, "price": price, "pct_below_entry": pct,
                           "within_max": pct <= MAX_STOP_PCT})
    for cand in candidates:
        if cand["within_max"]:
            return {"stop": cand["price"], "stop_basis": cand["basis"],
                    "stop_pct": cand["pct_below_entry"], "stop_note": None,
                    "stop_candidates": candidates}
    stop = _at_pct(entry, -MAX_STOP_PCT)
    return {"stop": stop, "stop_basis": "max_stop", "stop_pct": _pct(100 * (entry - stop) / entry),
            "stop_note": (f"the bar's low {_usd(low)} is {candidates[0]['pct_below_entry']:g}% below the "
                          f"planned fill {_usd(entry)} and its midpoint {candidates[1]['pct_below_entry']:g}%, "
                          f"both past his {MAX_STOP_PCT:g}% line; the stop was set at {MAX_STOP_PCT:g}% "
                          f"({_usd(stop)}), a level the bar does not support"),
            "stop_candidates": candidates}


# ------------------------------------------------------------- burst plan --


def _action(eligible: bool, sizing: Sizing, when_sized: str) -> str:
    if not eligible:
        return "refused"
    if sizing.capped_by == "multiplier":
        return "no_new_longs"
    if sizing.shares == 0:
        return "no_order"
    return when_sized


def _sizing_block(sizing: Sizing, stop: float) -> dict[str, Any]:
    return {
        "risk_per_share": sizing.risk_per_share, "shares": sizing.shares,
        "position_usd": sizing.position_usd, "position_pct": sizing.position_pct,
        "risk_usd": sizing.risk_usd, "capped_by": sizing.capped_by,
        "size_multiplier": sizing.multiplier, "sizing": sizing.to_dict(),
        "resize_rule": resize_rule(sizing.budget_usd, stop, sizing.cap_usd),
    }


def burst_plan(*, ticker: str, close: float, low: float, high: float, open_: float,
               prev_close: float, gain_pct: float, account: Account,
               size_multiplier: float = 1.0, scan: str = "4pct",
               extension_pct: float | None = None) -> dict[str, Any]:
    """The plan for entering yesterday's burst at tomorrow's open (B: "You
    can also use it for end of the day scanning and enter next day", taking
    only the ones that are "not extended").

    The order is a buy stop-limit with the stop AT the burst close and the
    limit at entry_high, so a gap down never fills. ``size_multiplier`` is
    the breadth regime's; the hazards and the stop width multiply it.
    Prices are validated as a bar: low <= open, close <= high.
    """
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError(f"ticker must be a non-empty string, got {ticker!r}")
    close, low, high = _price(close, "close"), _price(low, "low"), _price(high, "high")
    open_, prev_close = _price(open_, "open_"), _price(prev_close, "prev_close")
    gain_pct = _pct(_number(gain_pct, "gain_pct"))
    if low > high or not (low <= close <= high) or not (low <= open_ <= high):
        raise ValueError(f"{ticker}: open {open_} and close {close} must sit inside the bar "
                         f"{low}-{high}")

    entry_ref = close
    entry_low, entry_high = _at_pct(close, -ENTRY_BELOW_PCT), _at_pct(close, ENTRY_ABOVE_PCT)
    extended_above = _at_pct(close, SKIP_GAP_PCT)
    planned_entry = _at_pct(close, ASSUMED_SLIPPAGE_PCT)
    stop_block = burst_stop(planned_entry, low, high)
    stop = stop_block["stop"]
    eligible = stop_block["stop_basis"] != "max_stop"
    reason = None if eligible else (
        f"stop wider than {MAX_STOP_PCT:g}%: the burst low {_usd(low)} is "
        f"{stop_block['stop_candidates'][0]['pct_below_entry']:g}% under the planned fill {_usd(planned_entry)}")

    found = hazards(gain_pct, extension_pct)
    hazard_multiplier = min([h["multiplier"] for h in found], default=1.0)
    regime_multiplier = _number(size_multiplier, "size_multiplier")
    stop_multiplier, stop_reason = stop_risk(stop_block["stop_pct"])
    total = regime_multiplier * hazard_multiplier * stop_multiplier
    sizing = size(planned_entry, stop, account, total)
    action = _action(eligible, sizing, "buy_at_open")

    flags = [h["kind"] for h in found]
    notes = [h["detail"] for h in found]
    if not eligible:
        flags.append("wide_stop")
        notes.append(reason)
    if stop_reason:
        flags.append("risk_halved")
        notes.append(stop_reason)
    if sizing.capped_by == "position_cap":
        flags.append("position_capped")
    if stop_block["stop_note"]:
        notes.append(stop_block["stop_note"])
    if sizing.note:
        notes.append(sizing.note)
    orders = (fidelity_orders(ticker, sizing.shares, trigger=close, limit=entry_high, stop=stop)
              if action == "buy_at_open" else dict(NO_ORDER))

    return {
        "ticker": ticker, "kind": "burst", "scan": scan, "action": action,
        "eligible": eligible, "reason": reason,
        "entry_ref": entry_ref, "entry_low": entry_low, "entry_high": entry_high,
        "skip_if_open_above": entry_high, "skip_if_open_below": entry_low,
        "extended_above": extended_above, "entry_window": ENTRY_WINDOW,
        "pre_open_check": (f"before the open: if the pre-market print is under {_usd(entry_low)} the burst "
                           f"is failing, over {_usd(entry_high)} day 2 is spent, and over "
                           f"{_usd(extended_above)} (+{SKIP_GAP_PCT:g}%) he would be selling; do not "
                           f"place the order in any of the three"),
        "planned_entry": planned_entry, "assumed_slippage_pct": ASSUMED_SLIPPAGE_PCT,
        **stop_block,
        **_sizing_block(sizing, stop),
        "multipliers": {"regime": regime_multiplier, "hazard": hazard_multiplier,
                        "stop_risk": stop_multiplier, "total": total},
        "hazards": found, "hazard_multiplier": hazard_multiplier,
        "stop_risk_multiplier": stop_multiplier, "stop_risk_reason": stop_reason,
        "extension_pct": None if extension_pct is None else _pct(extension_pct),
        "targets": targets(planned_entry, close),
        "exits": exit_schedule(planned_entry, stop),
        **orders,
        "burst": {"close": close, "low": low, "high": high, "open": open_, "prev_close": prev_close,
                  "gain_pct": gain_pct, "gap_pct": _pct(100 * (open_ / prev_close - 1)),
                  "dollar_move": _money(close - open_),
                  "close_in_range_pct": (_pct(100 * (close - low) / (high - low)) if high > low else None)},
        "flags": flags, "notes": notes,
    }


# ------------------------------------------------------------- anticipation


#: The one sentence over the anticipation list, from the numbers the plans use.
ANTICIPATION_INSTRUCTION = (f"Buy only if it clears its trigger in the {ENTRY_WINDOW} on volume already above "
                            f"yesterday's pace; an open more than {GAP_OK_PCT:g}% above the close is gapped and "
                            f"needs a catalyst check before you buy.")


def anticipation_plan(*, ticker: str, close: float, box_high: float, box_low: float,
                      lows_last3: Sequence[float], account: Account,
                      size_multiplier: float = 1.0) -> dict[str, Any]:
    """A buy stop-limit a few cents over the consolidation high, the stop under
    the last sessions' low, refused when the stop is past MAX_STOP_PCT."""
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError(f"ticker must be a non-empty string, got {ticker!r}")
    close, box_high, box_low = _price(close, "close"), _price(box_high, "box_high"), _price(box_low, "box_low")
    if box_low > box_high:
        raise ValueError(f"{ticker}: box_low {box_low} is above box_high {box_high}")
    if not isinstance(lows_last3, (list, tuple)) or not 1 <= len(lows_last3) <= STOP_LOOKBACK_SESSIONS:
        raise ValueError(f"{ticker}: lows_last3 must hold 1 to {STOP_LOOKBACK_SESSIONS} lows, "
                         f"got {lows_last3!r}")
    lows = [_price(low, f"lows_last3[{i}]") for i, low in enumerate(lows_last3)]
    if max(lows) > box_high:
        raise ValueError(f"{ticker}: a low {max(lows)} above box_high {box_high} is not a consolidation")

    cushion = max(TRIGGER_CENTS, _money(TRIGGER_FRACTION * close))
    trigger = _money(box_high + cushion)
    limit = _at_pct(trigger, TRIGGER_LIMIT_PCT)
    stop_primary, stop_alt = min(lows), lows[-1]
    risk_pct = _pct(100 * (trigger / stop_primary - 1))
    eligible = risk_pct <= MAX_STOP_PCT
    reason = None if eligible else (f"stop wider than {MAX_STOP_PCT:g}%: the stop {_usd(stop_primary)} is "
                                    f"{risk_pct:g}% under the trigger {_usd(trigger)}")
    regime_multiplier = _number(size_multiplier, "size_multiplier")
    stop_multiplier, stop_reason = stop_risk(risk_pct)
    total = regime_multiplier * stop_multiplier
    sizing = size(trigger, stop_primary, account, total)
    action = _action(eligible, sizing, "place_buy_stop")
    gap_ok_above = _at_pct(close, GAP_OK_PCT)
    orders = (fidelity_orders(ticker, sizing.shares, trigger=trigger, limit=limit, stop=stop_primary)
              if action == "place_buy_stop" else dict(NO_ORDER))

    flags: list[str] = []
    notes: list[str] = []
    if not eligible:
        flags.append("wide_stop")
        notes.append(reason)
    if stop_reason:
        flags.append("risk_halved")
        notes.append(stop_reason)
    if sizing.capped_by == "position_cap":
        flags.append("position_capped")
    if sizing.note:
        notes.append(sizing.note)
    return {
        "ticker": ticker, "kind": "anticipation", "action": action, "eligible": eligible, "reason": reason,
        "entry_ref": trigger, "trigger": trigger, "limit": limit, "trigger_cushion": cushion,
        "box_high": box_high, "box_low": box_low, "close": close,
        "stop": stop_primary, "stop_alt": stop_alt, "stop_basis": f"lowest low of the last {len(lows)} sessions",
        "stop_pct": risk_pct, "lows_last3": lows,
        **_sizing_block(sizing, stop_primary),
        "multipliers": {"regime": regime_multiplier, "hazard": 1.0, "stop_risk": stop_multiplier,
                        "total": total},
        "hazards": [], "hazard_multiplier": 1.0,
        "stop_risk_multiplier": stop_multiplier, "stop_risk_reason": stop_reason,
        "gap_ok_above": gap_ok_above,
        "gap_rule": (f"an open more than {GAP_OK_PCT:g}% above {_usd(close)} (over {_usd(gap_ok_above)}) "
                     f"is gapped: catalyst check before buying"),
        "open_entry": (f"MOO/OPG at the open only for the top {OPEN_ENTRY_TOP_N} names on the list, and "
                       f"only if it opens within +{GAP_OK_PCT:g}% of {_usd(close)}"),
        "targets": targets(trigger, close),
        "exits": exit_schedule(trigger, stop_primary),
        **orders,
        "flags": flags, "notes": notes,
    }


# ------------------------------------------------------------- follow ------


def _bar(raw: Mapping[str, Any], index: int) -> dict[str, Any]:
    """A later session as validated floats."""
    if not isinstance(raw, Mapping):
        raise ValueError(f"later[{index}] must be a mapping, got {raw!r}")
    bar = {k: _price(raw.get(k), f"later[{index}].{k}") for k in ("o", "h", "l", "c")}
    if not (bar["l"] <= min(bar["o"], bar["c"]) and max(bar["o"], bar["c"]) <= bar["h"]):
        raise ValueError(f"later[{index}]: open {bar['o']} and close {bar['c']} must sit inside the bar "
                         f"{bar['l']}-{bar['h']}")
    bar["date"] = raw.get("date")
    return bar


def follow(pick: Mapping[str, Any], later: Sequence[Mapping[str, Any]],
           regime: str = "green") -> dict[str, Any]:
    """The open-plan instruction from bars alone.

    ``pick`` holds ticker, date, entry_ref, stop, shares and kind; ``later``
    the sessions after the pick date, oldest first. The walk applies the exit
    rules in ``EXIT_RULES``' order, one session at a time, on the published
    numbers: within one bar the open is read first, then the low against the
    stop (the order of a bar's high and low is unknown, so the stop wins),
    then the high against the sell-half level, then the close. At the close
    of day 1 the stop rises to the entry day's low; from day 3 it trails each
    day's low; it never moves down. Under a red ``regime`` a held plan's
    instruction gains ``RED_CLAUSE``; the status is the walk's.
    """
    ticker = pick.get("ticker")
    kind = pick.get("kind", "burst")
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    if not isinstance(regime, str):
        raise ValueError(f"regime must be a string, got {regime!r}")
    entry, stop = _price(pick.get("entry_ref"), "entry_ref"), _price(pick.get("stop"), "stop")
    shares = pick.get("shares", 0)
    if isinstance(shares, bool) or not isinstance(shares, int) or shares < 0:
        raise ValueError(f"shares must be a whole number, got {shares!r}")
    if entry <= stop:
        raise ValueError(f"entry_ref {entry} must be above stop {stop}")
    bars = [_bar(raw, i) for i, raw in enumerate(later)]
    levels = exit_levels(entry)
    half = shares - shares // 2  # "at least half"
    tag = f"{shares} {ticker}".strip()

    def pct(price: float) -> float:
        return _pct(100 * (price / entry - 1))

    events: list[dict[str, Any]] = []
    status, instruction, day = "pending", None, 0
    exit_price: float | None = None
    half_sold = False
    last: dict[str, Any] | None = None

    if not bars:
        instruction = (f"No session since the {pick.get('date')} pick yet: buy {tag} per the plan and "
                       f"attach the sell stop at {_usd(stop)}.")

    for day, bar in enumerate(bars, 1):
        if day > FINAL_EXIT_DAY:
            status = "expired"
            instruction = (f"Day {day}: the {FINAL_EXIT_DAY}-session window is over; if {tag} is still "
                           f"held, exit.")
            day = len(bars)
            break
        last = bar
        date, o, h, l, c = bar["date"], bar["o"], bar["h"], bar["l"], bar["c"]

        if day == ENTRY_DAY and kind == "anticipation" and h < entry:
            status = "expired"
            events.append({"day": day, "date": date, "event": "not_triggered", "price": h})
            instruction = (f"Day {day}: the buy stop at {_usd(entry)} was never reached (high {_usd(h)}); "
                           f"the day order expired unfilled.")
            break
        if o <= stop:
            status, exit_price = "stopped", o
            events.append({"day": day, "date": date, "event": "stopped_at_open", "price": o})
            instruction = (f"Day {day}: opened at {_usd(o)}, under the {_usd(stop)} stop: stopped at the "
                           f"open ({_plus_pct(pct(o))}).")
            break
        if o >= levels["gap_exit"]:
            status, exit_price = "exit", o
            events.append({"day": day, "date": date, "event": "gap_exit", "price": o})
            instruction = (f"Day {day}: opened at {_usd(o)} ({_plus_pct(pct(o))}, a +{GAP_EXIT_PCT:g}% "
                           f"gap): sell {tag} at the open.")
            break
        if l <= stop:
            status, exit_price = "stopped", stop
            events.append({"day": day, "date": date, "event": "stopped", "price": stop})
            instruction = f"Day {day}: stopped at {_usd(stop)} ({_plus_pct(pct(stop))})."
            break

        sold_today = False
        if h >= levels["sell_half"] and not half_sold:
            price = max(o, levels["sell_half"])
            stop = max(stop, _money(h - TRAIL_CENTS))
            half_sold, sold_today = True, True
            events.append({"day": day, "date": date, "event": "sell_half", "price": price})
            events.append({"day": day, "date": date, "event": "stop_raised", "price": stop})
            instruction = (f"Day {day}: sell half ({half} of {tag}) at {_usd(price)} "
                           f"({_plus_pct(pct(price))}) and raise the stop to {_usd(stop)} "
                           f"({_cents_int(TRAIL_CENTS)} cents under the day's high {_usd(h)}).")
        if c >= levels["abnormal"]:
            stop = max(stop, _money(h - TRAIL_CENTS))
            events.append({"day": day, "date": date, "event": "abnormal_day", "price": c})
            if not sold_today:
                instruction = (f"Day {day}: closed at {_usd(c)} ({_plus_pct(pct(c))}), an abnormal "
                               f"+{ABNORMAL_DAY_PCT:g}% day: take at least partial profit and hold the "
                               f"stop at {_usd(stop)}.")
        if day == NO_PROGRESS_DAY and c <= entry:
            status, exit_price = "exit", c
            events.append({"day": day, "date": date, "event": "no_progress", "price": c})
            instruction = (f"Day {NO_PROGRESS_DAY}: closed at {_usd(c)}, at or below the {_usd(entry)} "
                           f"entry: no follow-through, exit {tag}.")
            break
        if day == SELL_HALF_DAY and not half_sold:
            half_sold, sold_today = True, True
            events.append({"day": day, "date": date, "event": "sell_half", "price": c})
            instruction = (f"Day {SELL_HALF_DAY}: closed at {_usd(c)} ({_plus_pct(pct(c))}): sell at "
                           f"least half ({half} of {tag}) at the close.")
        if day == ENTRY_DAY and l > stop:
            stop = l
            events.append({"day": day, "date": date, "event": "stop_raised_to_entry_low", "price": stop})
        elif day >= TRAIL_FROM_DAY and l > stop:
            stop = l
            events.append({"day": day, "date": date, "event": "stop_trailed", "price": stop})
        if day >= FINAL_EXIT_DAY:
            status, exit_price = "exit", c
            events.append({"day": day, "date": date, "event": "day5_exit", "price": c})
            instruction = (f"Day {FINAL_EXIT_DAY}: closed at {_usd(c)} ({_plus_pct(pct(c))}): exit the "
                           f"remainder of {tag} into strength.")
            continue
        if sold_today:
            status = "sell_half"
            instruction = f"{instruction} The stop is {_usd(stop)}."
        elif half_sold:
            status = "sell_into_strength"
            instruction = (f"Day {day}: closed at {_usd(c)} ({_plus_pct(pct(c))}); half is sold, sell "
                           f"the rest into strength by day {FINAL_EXIT_DAY} with the stop at {_usd(stop)}.")
        else:
            status = "hold"
            instruction = (f"Day {day}: hold {tag} with the stop at {_usd(stop)} (closed {_usd(c)}, "
                           f"{_plus_pct(pct(c))}).")

    if regime == RED_REGIME:
        if status in HELD_STATUSES:
            instruction = f"{instruction} {RED_CLAUSE}"
        elif status == "pending":
            instruction = f"{instruction} {RED_PENDING_CLAUSE}"

    return {
        "ticker": ticker, "kind": kind, "picked": pick.get("date"), "day": day, "sessions": len(bars),
        "status": status, "instruction": instruction, "events": events, "regime": regime,
        "entry_ref": entry, "shares": shares, "current_stop": stop,
        "last_close": last["c"] if last else None,
        "last_date": last["date"] if last else None,
        "unrealised_pct": pct(last["c"]) if last else None,
        "exit_price": exit_price, "result_pct": pct(exit_price) if exit_price is not None else None,
        "half_sold": half_sold,
    }


# ------------------------------------------------------------- budget ------


def cash_budget(plans: Sequence[Mapping[str, Any]], account: Account,
                open_positions: int = 0) -> dict[str, Any]:
    """What tomorrow's plans commit, in rank order, against the slot cap and
    the equity: a plan with no order takes no slot; a plan past the free
    slots or past the equity is listed under ``beyond`` with its reason."""
    if isinstance(open_positions, bool) or not isinstance(open_positions, int) or open_positions < 0:
        raise ValueError(f"open_positions must be a whole number, got {open_positions!r}")
    free = max(0, account.max_open_positions - open_positions)
    committed = 0.0
    within: list[str] = []
    beyond: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for rank, plan in enumerate(plans, 1):
        ticker = plan.get("ticker")
        shares = plan.get("shares") or 0
        position = _money(plan.get("position_usd") or 0)
        if plan.get("action") not in ORDER_ACTIONS or shares <= 0:
            skipped.append({"ticker": ticker, "rank": rank, "reason": "no_order"})
        elif len(within) >= free:
            beyond.append({"ticker": ticker, "rank": rank, "reason": "slot_cap", "position_usd": position})
        elif committed + position > account.equity:
            beyond.append({"ticker": ticker, "rank": rank, "reason": "equity", "position_usd": position})
        else:
            committed = _money(committed + position)
            within.append(ticker)
    used = open_positions + len(within)
    already = f" ({open_positions} already open)" if open_positions else ""
    at_risk = _money(sum(_money(p.get("risk_usd") or 0) for p in plans
                         if p.get("ticker") in within))
    cut = []
    for row in beyond:
        if row["reason"] == "slot_cap":
            holders = ", ".join(within) if within else "the open plans"
            reason = (f"the {account.max_open_positions}-slot cap: {open_positions} already open and "
                      f"{holders} take the rest; take {row['ticker']} only if a HOLD above stops out")
        else:
            reason = (f"the equity: {_usd(row['position_usd'])} more than the {_usd(account.equity)} "
                      f"account can commit beside the orders above")
        cut.append({"ticker": row["ticker"], "reason": reason})
    return {
        "committed_usd": committed, "at_risk_usd": at_risk, "equity": account.equity,
        "slots_used": used, "slots_max": account.max_open_positions, "open_positions": open_positions,
        "within": within, "beyond": beyond, "cut": cut, "skipped": skipped,
        "sentence": (f"Tomorrow's plans commit {_usd(committed)} of {_usd(account.equity)}; "
                     f"{used} of {account.max_open_positions} slots{already}"),
    }


# ------------------------------------------------------------- notes -------

#: The constraints the page states, as templates so a later lens can correct
#: the wording in one place. ``account_notes()`` fills them.
NOTE_RISK = "Risk per trade: {risk_usd} ({risk_pct:g}% of {equity}; his band is {band_low:g}-{band_high:g}%{band})."
NOTE_POSITION_CAP = "Position cap: {cap_usd} ({max_position_pct:g}% of equity) in any one name."
NOTE_MAX_OPEN = "Max {max_open} open positions ({invested:g}% of equity if all are at the cap)."
NOTE_PDT = ("Day trades: FINRA deleted the pattern-day-trader count on {pdt_deleted}, but Fidelity has "
            "announced no migration date and may keep applying it per account until {pdt_phase_in}, so run "
            "the account as if the old rule binds: at most {pdt_trades} same-day round trips per rolling "
            "{pdt_days} business days in a margin account under {pdt_equity}; a same-day stop-out counts; "
            "a position held overnight never counts.")
NOTE_ACCOUNT_TYPE = ("Account type: margin with debt protection (no borrowing, no good-faith violations). "
                     "In a cash account buy only against settled cash (T+{settle}); {gfv_limit} good-faith "
                     "violations in {gfv_months} months means {gfv_days} days of settled-cash-only.")
NOTE_ATTACH_STOP = ("Attach the protective stop the moment the buy fills, as a stop-MARKET order and never a "
                    "stop-limit (Fidelity mobile: \"Market + Stop Loss Protection\"; Active Trader Pro: "
                    "OTO/OTOCO).")
NOTE_TEMPLATES = (NOTE_RISK, NOTE_POSITION_CAP, NOTE_MAX_OPEN, NOTE_PDT, NOTE_ACCOUNT_TYPE, NOTE_ATTACH_STOP)


def account_notes(account: Account) -> list[str]:
    """Plain-English constraints for the page, one sentence each."""
    values = {
        "risk_usd": _usd(account.risk_usd), "risk_pct": account.risk_pct, "equity": _usd(account.equity),
        "band_low": RISK_PCT_BAND_LOW, "band_high": RISK_PCT_BAND_HIGH,
        "band": "" if account.within_bonde_band else ", and this is outside it",
        "cap_usd": _usd(account.max_position_usd), "max_position_pct": account.max_position_pct,
        "max_open": account.max_open_positions,
        "invested": _pct(account.max_open_positions * account.max_position_pct),
        "pdt_equity": _usd(PDT_EQUITY_USD), "pdt_trades": PDT_MAX_DAY_TRADES, "pdt_days": PDT_WINDOW_DAYS,
        "pdt_deleted": PDT_RULE_DELETED_ON, "pdt_phase_in": PDT_PHASE_IN_ENDS,
        "settle": SETTLEMENT_DAYS, "gfv_limit": GFV_LIMIT, "gfv_months": GFV_WINDOW_MONTHS,
        "gfv_days": GFV_RESTRICTION_DAYS,
    }
    return [template.format(**values) for template in NOTE_TEMPLATES]
