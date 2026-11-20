"""``docs/strategy.html``: the strategy as the installed record's rules state it.

Every number the page prints is read from the rules the record archived
(``data["rules"]``), or, where the record archives none, from the code's own
constant -- and the page names every rule it read from the code, and every
rule whose code constant now differs from the record's, so a merge that moves
a constant is never attributed to an older record. It prints the market
light's five rules with tonight's scaled thresholds and values, the two
discovery scans and the admission gate, the checklist's weights, bands, gate
letters and vetoes, the chart-reader requirement, the burst ticket and the
setting-up ticket (trigger, limit, stop, size, entry window, skip lines), every
exit rule of ``plan.EXIT_RULES`` with its source mark and the order the model's
walk (``plan.follow()``) applies them in, and the night's candidate funnel.
``build()`` is a pure function of the record's bytes; the evening writes the
page after the record (``pipeline.publish_strategy()``), and
``tools/build_strategy_page.py --check`` refuses a committed page that is not
what the code and the committed record write. The page decides nothing and
recommends nothing.
"""
from __future__ import annotations

import hashlib
from html import escape
import json
from pathlib import Path
import re

VERSION = 2
FILE = "strategy.html"
#: a unit, not a rule: a fraction times this is a percentage
PERCENT = 100
#: what each source mark on a rule means (plan's own module docstring)
SOURCE_MARKS = {
    "B": "Bonde's own number or rule",
    "P": "this project's provisional reading of a rule he states without a figure",
    "T": "a third party's measurement, not his",
    "R": "a regulation or a broker rule",
}
LIGHTS = ("green", "yellow", "red")
#: the two checks whose failure is a veto, by the key the checklist records them under
VETO_CHECKS = ("two_days", "linearity")
#: what the page prints for a value the record does not carry
UNRECORDED = "not recorded"
#: ``plan.follow()``'s precedence within one session, in its own order: each
#: step's words name the level or the day constant it reads, never a figure
WALK = (
    ("stop_at_open", "an open at or under the stop: stopped at the open"),
    ("gap_20pct", "an open at or over the gap-exit level: the whole position sold at the open"),
    ("stop_intraday", "a low at or under the stop: stopped at the stop (the stop wins over any later level that day)"),
    ("sell_half_8pct", "a high at or over the sell-half level, once: half sold at that level (or the open, if "
                       "higher), and the stop raised under the day's high"),
    ("abnormal_10pct", "a close at or over the abnormal-close level: the stop raised under the day's high; the "
                       "model sells nothing on it"),
    ("day3_no_progress", "on the no-progress day, a close at or under the fill: the whole position exits at the close"),
    ("day3_sell_half", "on the sell-half day, half not yet sold: half sold at the close"),
    ("entry_day_low", "on the entry day the stop rises to that day's low; from the trail day it rises to each day's low"),
    ("day5_exit", "on the final day: the remainder sold at the close"),
)


def _e(value) -> str:
    return escape(str(value))


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _pct(value) -> str:
    return f"{value:g}%" if _num(value) else "an unrecorded percentage"


def _g(value) -> str:
    return f"{value:g}" if _num(value) else UNRECORDED


def _int(value) -> str:
    return f"{value:,}" if isinstance(value, int) and not isinstance(value, bool) else UNRECORDED


def _table(head: list[str], rows: list[list], cls: str = "sc-table sc-table--compact") -> str:
    th = "".join(f"<th>{_e(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<div class="sc-table-scroll"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def _section(title: str, eyebrow: str, body: str) -> str:
    return (f'<section class="sc-section"><p class="sc-eyebrow">{_e(eyebrow)}</p>'
            f'<h2>{_e(title)}</h2>{body}</section>')


class Rules:
    """The rules a record archived, read one key at a time. A key the record
    does not archive is the code's constant, and is named; a key whose code
    constant now differs from the record's is named with both values."""

    def __init__(self, data: dict):
        rules = data.get("rules")
        self.archived = rules if isinstance(rules, dict) else {}
        self.from_code: list[str] = []
        self.differ: list[tuple[str, object, object]] = []

    def get(self, family: str, key: str, code):
        fam = self.archived.get(family)
        name = f"{family}.{key}"
        if isinstance(fam, dict) and key in fam:
            value = fam[key]
            if value != code and name not in [d[0] for d in self.differ]:
                self.differ.append((name, value, code))
            return value
        if name not in self.from_code:
            self.from_code.append(name)
        return code


# ----------------------------------------------------------- the sections ---
def _ratio(value) -> str:
    return "undefined" if value is None else _g(value)


def _fired(value, threshold, under: bool) -> str:
    if not (_num(value) and _num(threshold)):
        return "not read"
    return "fired" if (value < threshold if under else value >= threshold) else "clear"


def market(data: dict, r: Rules) -> str:
    from src import breadth, pipeline
    regime = data.get("breadth", {}).get("regime", {}) if isinstance(data.get("breadth"), dict) else {}
    regime = regime if isinstance(regime, dict) else {}
    t = regime.get("thresholds") if isinstance(regime.get("thresholds"), dict) else {}
    i = regime.get("inputs") if isinstance(regime.get("inputs"), dict) else {}
    burst_pct = r.get("breadth", "burst_pct", breadth.BURST_PCT)
    big = r.get("breadth", "month_big_move_pct", breadth.MONTH_BIG_MOVE_PCT)
    long_n = r.get("breadth", "ratio_long_sessions", breadth.RATIO_LONG_SESSIONS)
    short_n = r.get("breadth", "ratio_short_sessions", breadth.RATIO_SHORT_SESSIONS)
    rows = []
    if t and i:
        five = _fired(i.get("ratio_5d"), t.get("ratio_5d_red"), under=True)
        if five == "fired" and not (_num(i.get("down4")) and _num(i.get("up4")) and i["down4"] > i["up4"]):
            five = "clear"
        up50 = i.get("up50_month")
        rows = [
            ["red", f"down {_e(_g(burst_pct))}% today at or over {_e(_g(t.get('down4_alarm')))} "
                    f"({_e(_g(r.get('breadth', 'down4_alarm', breadth.DOWN4_ALARM)))} of "
                    f"{_e(_int(t.get('reference_universe')))} scaled to {_e(_int(t.get('universe')))} names)",
             _e(_g(i.get("down4"))), _e(_fired(i.get("down4"), t.get("down4_alarm"), under=False))],
            ["red", f"{_e(_g(long_n))}-session up/down ratio under {_e(_g(t.get('ratio_10d_red')))}",
             _e(_ratio(i.get("ratio_10d"))), _e(_fired(i.get("ratio_10d"), t.get("ratio_10d_red"), under=True))],
            ["red", f"{_e(_g(short_n))}-session ratio under {_e(_g(t.get('ratio_5d_red')))} while today's down "
                    f"count exceeds its up count",
             f"{_e(_ratio(i.get('ratio_5d')))} ({_e(_g(i.get('down4')))} down, {_e(_g(i.get('up4')))} up)", _e(five)],
            ["yellow", f"{_e(_g(long_n))}-session ratio under {_e(_g(t.get('ratio_10d_yellow')))}",
             _e(_ratio(i.get("ratio_10d"))), _e(_fired(i.get("ratio_10d"), t.get("ratio_10d_yellow"), under=True))],
            ["yellow", f"up {_e(_g(big))}% in a month over {_e(_g(t.get('up50_month_hot')))} "
                       f"({_e(_g(r.get('breadth', 'up50_month_hot', breadth.UP50_MONTH_HOT)))} of "
                       f"{_e(_int(t.get('reference_universe')))} scaled)",
             _e(_g(up50)),
             _e("not read" if not (_num(up50) and _num(t.get("up50_month_hot")))
                else "fired" if up50 > t["up50_month_hot"] else "clear")],
        ]
    multipliers = r.get("breadth", "size_multiplier", breadth.SIZE_MULTIPLIER)
    multipliers = multipliers if isinstance(multipliers, dict) else {}
    trade = r.get("pipeline", "trade_grades", list(pipeline.TRADE_GRADES))
    yellow = r.get("pipeline", "yellow_grades", list(pipeline.YELLOW_GRADES))
    grades = {"green": ", ".join(trade), "yellow": ", ".join(yellow), "red": "none"}
    lights = _table(["light", "size multiplier", "grades admitted"],
                    [[_e(k), _e(_g(multipliers.get(k))), _e(grades[k])] for k in LIGHTS])
    verdict = regime.get("verdict")
    reference = r.get("breadth", "reference_universe", breadth.REFERENCE_UNIVERSE)
    return _section(
        "The market light", "the regime gate",
        f"<p>Tonight's light is <strong>{_e(verdict or UNRECORDED)}</strong>. Red on any red rule, yellow on any "
        f"yellow rule, green otherwise. The two count thresholds are Bonde's counts over his reference universe of "
        f"{_e(_int(reference))} names, scaled to tonight's measurable universe; the ratios are not "
        f"scaled. This gate is this project's reading of his Market Monitor; it is not shown here to improve "
        f"outcomes.</p>"
        + (_table(["tier", "rule (tonight's thresholds)", "tonight's value", "tonight"], rows) if rows
           else "<p>The record carries no regime inputs to print.</p>")
        + "<h3>What each light admits</h3>" + lights)


def discovery(data: dict, r: Rules) -> str:
    from src import admission, scans
    words = dict(admission.DOLLAR_CHECKS)
    ratio = r.get("burst", "min_ratio", scans.BURST_RATIO)
    burst_pct = f"{ratio * PERCENT - PERCENT:g}%" if _num(ratio) else "an unrecorded percentage"
    burst_volume = r.get("burst", "min_volume", scans.MIN_VOLUME)
    dollar = r.get("dollar", "min_move", scans.DOLLAR_MOVE)
    dollar_volume = r.get("dollar", "min_volume_exclusive", scans.MIN_VOLUME)
    policy = r.get("admission", "policy", admission.POLICY)
    return _section(
        "Discovery", "what the scans find",
        "<ul>"
        f"<li><strong>The {_e(burst_pct)} burst scan</strong>: the close at least {_e(_g(ratio))}× the previous close, "
        f"volume above the previous session's, and at least {_e(_int(burst_volume))} shares.</li>"
        f"<li><strong>The dollar scan</strong>: the close at least "
        f"{_e(f'${dollar:.2f}' if _num(dollar) else UNRECORDED)} over the session's own open (the day's body, the "
        f"gap excluded), on more than {_e(_int(dollar_volume))} shares.</li>"
        f"<li><strong>The admission gate</strong> (<code>{_e(policy)}</code>): a name the {_e(burst_pct)} scan found is "
        f"admitted; a name the dollar scan alone found is admitted only on a {_e(words['RE'].replace('_', ' '))} and "
        f"{_e(words['VOL'].replace('_', ' '))} day (the checklist's RE and VOL checks). Otherwise: "
        f"{_e(admission.NOT_ADMITTED_WORDS)}: research only, no ticket.</li>"
        "</ul>")


def checklist(data: dict, r: Rules) -> str:
    from src import grader, pipeline, quality, reader_coverage
    labels = {}
    bursts = data.get("bursts") if isinstance(data.get("bursts"), list) else []
    for b in bursts:
        for c in ((b.get("quality") or {}).get("checks") or []) if isinstance(b, dict) else []:
            if isinstance(c, dict) and c.get("letter") and c.get("label"):
                labels.setdefault(c["letter"], c["label"])
    weights = {k: r.get("quality", f"weight_{k.lower()}", w) for k, w in quality.WEIGHTS.items()}
    unlabelled = "(no candidate tonight recorded its words)"
    table = _table(["letter", "what it checks", "points"],
                   [[_e(k), _e(labels.get(k, unlabelled)), _e(_g(w))] for k, w in weights.items()]
                   + [[_e(k), _e(labels.get(k, unlabelled)), "no points (counts toward the A+ tally only)"]
                      for k in quality.EXTRA_CHECKS])
    bands = ", ".join(f"{g} from {s:g}" for s, g in grader.GRADE_BANDS) + f", {grader.SKIP} under {grader.GRADE_BANDS[-1][0]:g}"
    vetoes = {}
    for b in bursts:
        for c in ((b.get("quality") or {}).get("checks") or []) if isinstance(b, dict) else []:
            if isinstance(c, dict) and c.get("key") in VETO_CHECKS and c.get("threshold"):
                vetoes.setdefault(c["key"], (c.get("letter"), c["threshold"]))
    letters = r.get("quality", "min_a_plus_letters", quality.MIN_A_PLUS_LETTERS)
    up_days = r.get("quality", "veto_up_days", quality.VETO_UP_DAYS)
    min_er = r.get("quality", "min_er", quality.MIN_ER)
    min_r2 = r.get("quality", "min_r2", quality.MIN_R2)
    leg = r.get("quality", "min_leg_sessions", quality.MIN_LEG_SESSIONS)
    policy = r.get("pipeline", "reader_policy", reader_coverage.POLICY)
    trade = r.get("pipeline", "trade_grades", list(pipeline.TRADE_GRADES))
    return _section(
        "The checklist", "how a name is graded",
        table
        + f"<p>A passed letter earns its points, a partial half. Bands: {_e(bands)}. A+ also needs "
          f"{_e(_g(letters))} checks at their A+ standard, and the top bands ({_e(', '.join(quality.GATED_GRADES))}) need "
          f"{_e(' and '.join(quality.GRADE_GATE_LETTERS))} passed outright or the grade is capped at "
          f"{_e(quality.GATE_CAP)}. The weighting is this project's: Bonde publishes no weights or pass count.</p>"
        + f"<p>Vetoes ({_e(', '.join(quality.VETO_NAMES))}): <code>{_e(quality.VETO_UP_DAYS_NAME)}</code> at "
          f"{_e(_g(up_days))} or more rising closes in a row into the burst, of any size; "
          f"<code>{_e(quality.VETO_NOT_LINEAR)}</code> when the prior leg's efficiency ratio is under {_e(_g(min_er))} "
          f"and its R² under {_e(_g(min_r2))} (either one at its line passes; a leg of fewer than {_e(_g(leg))} sessions "
          f"is unmeasured, and no veto)."
          + (" Tonight's records state them as: " + "; ".join(f"{_e(vetoes[k][0])} — {_e(vetoes[k][1])}" for k in VETO_CHECKS) + "."
             if set(VETO_CHECKS) <= set(vetoes) else "")
          + "</p>"
        + f"<p><strong>The chart reader</strong> (<code>{_e(policy)}</code>): a burst ticket needs an accepted "
          f"chart-reader review as well as a mechanical grade the light admits ({_e(', '.join(trade))} on a green "
          f"night). The reader can lower a grade and never raise one; a name with no accepted review keeps its "
          f"mechanical grade as research and gets no ticket.</p>")


def _size(data: dict, r: Rules) -> str:
    from src import plan
    account = data.get("account") if isinstance(data.get("account"), dict) else {}
    equity = account.get("equity")
    ceiling = r.get("plan", "gain_ceiling_pct", plan.GAIN_CEILING_PCT)
    extension = r.get("plan", "extension_hazard_pct", plan.EXTENSION_HAZARD_PCT)
    sessions = r.get("plan", "extension_sessions", plan.EXTENSION_SESSIONS)
    hazard = r.get("plan", "hazard_multiplier", plan.HAZARD_MULTIPLIER)
    ideal = r.get("plan", "ideal_stop_pct", plan.IDEAL_STOP_PCT)
    stop_multiplier = r.get("plan", "stop_risk_multiplier", plan.STOP_RISK_MULTIPLIER)
    return (f"<li><strong>Size</strong>: shares at the limit (<code>{_e(r.get('plan', 'sizing_basis', plan.SIZING_BASIS))}</code>) "
            f"risking {_e(_pct(account.get('risk_pct')))} of the "
            f"{_e(f'${equity:,.0f}' if _num(equity) else 'unrecorded')} model account times the light's multiplier, "
            f"times {_e(_g(stop_multiplier))} for a stop wider than {_e(_pct(ideal))} of the limit, and times "
            f"{_e(_g(hazard))} for either hazard: a burst day up {_e(_pct(ceiling))} or more, or a close more than "
            f"{_e(_pct(extension))} over its {_e(_g(sessions))}-session average (the two hazards take the smaller, "
            f"never their product); capped at {_e(_pct(account.get('max_position_pct')))} of the account, "
            f"{_e(_int(account.get('max_open_positions')) if _num(account.get('max_open_positions')) else 'an unrecorded number of')} "
            f"model slots. Model sizing, never the owner's holdings.</li>")


def ticket(data: dict, r: Rules) -> str:
    from src import plan
    trigger_rule = plan.archived_burst_trigger_rule(r.archived)
    if trigger_rule != plan.BURST_TRIGGER_RULE:
        # a record made before the rule was archived reads as the legacy rule, never the code's
        r.differ.append(("plan.burst_trigger_rule", trigger_rule, plan.BURST_TRIGGER_RULE))
    cents = r.get("plan", "trigger_cents", plan.TRIGGER_CENTS)
    fraction = r.get("plan", "trigger_fraction", plan.TRIGGER_FRACTION)
    # the outer extension line is read off the record alone: only plan.py derives anything from its constant
    family = r.archived.get("plan")
    above = family.get("entry_above_pct") if isinstance(family, dict) else None
    below = r.get("plan", "entry_below_pct", plan.ENTRY_BELOW_PCT)
    gap = r.get("plan", "skip_gap_pct", plan.SKIP_GAP_PCT)
    max_stop = r.get("plan", "max_stop_pct", plan.MAX_STOP_PCT)
    window = r.get("plan", "entry_window_minutes", plan.ENTRY_WINDOW_MINUTES)
    cushion = (f"the larger of {_e(f'${cents:.2f}' if _num(cents) else UNRECORDED)} and "
               f"{_e(_pct(fraction * PERCENT if _num(fraction) else None))} of the close")
    buy = ("the burst close plus " + cushion if trigger_rule == "close_plus_cushion"
           else "the burst close itself")
    return _section(
        "The burst ticket", "a day buy stop-limit with a one-triggers-the-other sell stop",
        "<ul>"
        f"<li><strong>Buy stop</strong> (<code>{_e(trigger_rule)}</code>, the rule this record was made under): {buy}.</li>"
        f"<li><strong>Limit</strong>: the close plus {_e(_pct(above))} (the outer extension line), narrowed to the "
        f"highest price at which the stop is still within {_e(_pct(max_stop))} of the limit.</li>"
        f"<li><strong>Stop</strong>: the burst day's low, else its range midpoint, the first within "
        f"{_e(_pct(max_stop))} of the limit and under the buy stop; a ticket neither can carry is withheld.</li>"
        + _size(data, r)
        + f"<li><strong>Entry window</strong>: the first {_e(_g(window))} minutes of the session; an unfilled order "
          f"is cancelled at the window's end. Skip lines: an open more than {_e(_pct(below))} under the burst close "
          f"(a burst already failing), or more than {_e(_pct(above))} over it (the follow-through spent before the fill; over "
          f"{_e(_pct(gap))} it is an entry the exits would be selling into).</li>"
        "</ul>")


def setup_ticket(data: dict, r: Rules) -> str:
    from src import breadth, plan, watchlist
    cents = r.get("plan", "trigger_cents", plan.TRIGGER_CENTS)
    fraction = r.get("plan", "trigger_fraction", plan.TRIGGER_FRACTION)
    multipliers = r.get("breadth", "size_multiplier", breadth.SIZE_MULTIPLIER)
    red = multipliers.get("red") if isinstance(multipliers, dict) else None
    limit_pct = r.get("plan", "trigger_limit_pct", plan.TRIGGER_LIMIT_PCT)
    lookback = r.get("plan", "stop_lookback_sessions", plan.STOP_LOOKBACK_SESSIONS)
    max_stop = r.get("plan", "max_stop_pct", plan.MAX_STOP_PCT)
    gap_ok = r.get("plan", "gap_ok_pct", plan.GAP_OK_PCT)
    top_n = r.get("watchlist", "top_n", watchlist.TOP_N)
    return _section(
        "The setting-up ticket", "a coil listed before it bursts",
        "<ul>"
        f"<li><strong>Which names</strong>: the top {_e(_g(top_n))} of the setting-up list (a tight consolidation "
        f"with its box and its volume dried up), measured and not graded: no checklist band and no chart-reader "
        f"review. Each is sized by the light's multiplier, so the red light's ({_e(_g(red))}) gives it no "
        f"shares.</li>"
        f"<li><strong>Buy stop</strong>: the box's high plus the larger of "
        f"{_e(f'${cents:.2f}' if _num(cents) else UNRECORDED)} and "
        f"{_e(_pct(fraction * PERCENT if _num(fraction) else None))} of the close. <strong>Limit</strong>: the buy "
        f"stop plus {_e(_pct(limit_pct))}.</li>"
        f"<li><strong>Stop</strong>: the lowest low of the last {_e(_g(lookback))} sessions; a stop more than "
        f"{_e(_pct(max_stop))} under the limit withholds the ticket.</li>"
        f"<li><strong>The open</strong>: it has no skip line; a gap over {_e(_pct(gap_ok))} asks for a catalyst check "
        f"before entry. Sized as the burst ticket is, at its limit.</li>"
        "</ul>")


def _exit_values(r: Rules) -> dict:
    from src import plan
    cents = r.get("plan", "trail_cents", plan.TRAIL_CENTS)
    cents_max = r.get("plan", "trail_cents_max", plan.TRAIL_CENTS_MAX)
    return {
        "entry": "the fill", "sell_half": "the sell-half level", "abnormal": "the abnormal-close level",
        "gap_exit": "the gap-exit level", "stop": "the ticket's stop price",
        "sell_half_pct": _g(r.get("plan", "sell_half_pct", plan.SELL_HALF_PCT)),
        "abnormal_pct": _g(r.get("plan", "abnormal_day_pct", plan.ABNORMAL_DAY_PCT)),
        "gap_exit_pct": _g(r.get("plan", "gap_exit_pct", plan.GAP_EXIT_PCT)),
        "trail_cents": plan._cents_int(cents) if _num(cents) else UNRECORDED,
        "trail_cents_max": plan._cents_int(cents_max) if _num(cents_max) else UNRECORDED,
        "entry_day": _g(r.get("plan", "entry_day", plan.ENTRY_DAY)),
        "sell_half_day": _g(r.get("plan", "sell_half_day", plan.SELL_HALF_DAY)),
        "no_progress_day": _g(r.get("plan", "no_progress_day", plan.NO_PROGRESS_DAY)),
        "trail_from_day": _g(r.get("plan", "trail_from_day", plan.TRAIL_FROM_DAY)),
        "final_exit_day": _g(r.get("plan", "final_exit_day", plan.FINAL_EXIT_DAY)),
        "no_breakeven_day": _g(r.get("plan", "no_breakeven_before_day", plan.NO_BREAKEVEN_BEFORE_DAY)),
    }


def exits(data: dict, r: Rules) -> str:
    from src import plan, scans
    values = _exit_values(r)
    rows = [[f"<code>{_e(rule['key'])}</code>", _e(rule["when"].format(**values)), _e(rule["rule"].format(**values)),
             f'<span class="sc-chip sc-chip--neutral" title="{_e(SOURCE_MARKS.get(rule["source"], rule["source"]))}">'
             f'{_e(rule["source"])}</span>'] for rule in plan.EXIT_RULES]
    walk = "".join(f"<li><code>{_e(key)}</code>: {_e(words)}</li>" for key, words in WALK)
    marks = "; ".join(f"{k}: {v}" for k, v in SOURCE_MARKS.items())
    third = [rule for rule in plan.EXIT_RULES if rule["source"] == "T"]
    named = {rule["key"]: re.search(r"\(([^:()]+):", rule["rule"]) for rule in third}
    return _section(
        "The exits", "the rulebook's rules, then the order the model applies them in",
        _table(["rule", "when", "then", "source"], rows)
        + f"<p class=\"sc-hint\">Source marks: {_e(marks)}. Each level is measured from the booked fill, the price "
          f"the model's walk takes as its entry. The table's words are <code>plan.EXIT_RULES</code> as written, "
          f"including the figures its third-party rule quotes.</p>"
        + "<h3>The order the model applies them in</h3>"
        + f"<p>The model's walk (<code>plan.follow()</code>) reads each session in this order, and the first step "
          f"that closes the position ends it:</p><ol>{walk}</ol>"
        + "".join(f"<p><strong>Attribution.</strong> <code>{_e(key)}</code> is a third party's measurement, "
                  f"{_e(m.groups()[0] if m else 'unnamed in the rule')}, of a different setup (the episodic pivot on at "
                  f"least {_e(f'{scans.EP9M_MIN_VOLUME:,}')} shares), carried over by this build and not validated "
                  f"on bursts here.</p>" for key, m in named.items()))


def funnel(data: dict, r: Rules) -> str:
    f = data.get("funnel") if isinstance(data.get("funnel"), dict) else None
    if not f:
        return _section("Tonight's candidate funnel", "where each candidate stopped",
                        "<p>This record carries no funnel.</p>")
    labels = f.get("labels") if isinstance(f.get("labels"), dict) else {}
    stages = (f.get("reaction") or {}).get("stages") if isinstance(f.get("reaction"), dict) else None
    stages = stages if isinstance(stages, dict) else {}
    rows = [[_e(labels.get(k, k)), _e(f"{n:,}")] for k, n in stages.items()
            if isinstance(n, int) and not isinstance(n, bool) and n]
    return _section(
        "Tonight's candidate funnel", "where each candidate stopped",
        f"<p>{_e(f.get('sentence', ''))}</p>" + (_table(["stage", "reaction candidates"], rows) if rows else ""))


def provenance_note(r: Rules) -> str:
    from_code = (f"<p class=\"sc-hint\">Read from the code because this record archives no such rule: "
                 f"{_e(', '.join(r.from_code))}.</p>" if r.from_code else "")
    differ = (f"<p class=\"sc-hint\"><strong>The code has moved since this record.</strong> Each rule above is "
              f"printed as the record archived it; the code now holds another value for "
              + _e("; ".join(f"{name} (record {value}, code {code})" for name, value, code in r.differ))
              + ".</p>" if r.differ else "")
    return _section("Where each rule comes from", "the record's rules, and the code's",
                    "<p>Every rule above is the one this record archived in its <code>rules</code>, which is what its "
                    "tickets were made under. The grade bands, the gate letters, the walk's order and the exit "
                    "table's words are the code's (<code>grader.GRADE_BANDS</code>, "
                    "<code>quality.GRADE_GATE_LETTERS</code>, <code>plan.follow()</code>, "
                    "<code>plan.EXIT_RULES</code>).</p>" + from_code + differ)


# ------------------------------------------------------------------- page ---
SECTIONS = (market, discovery, checklist, ticket, setup_ticket, exits, funnel)


def build(canonical_raw: bytes) -> str:
    """The page for one installed record's bytes."""
    data = json.loads(canonical_raw)
    if not isinstance(data, dict):
        raise ValueError("the record is not a JSON object")
    run = data.get("run") if isinstance(data.get("run"), dict) else {}
    digest = hashlib.sha256(canonical_raw).hexdigest()
    rules_version = (data.get("app") or {}).get("rules_version") if isinstance(data.get("app"), dict) else None
    head = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<meta name=\"color-scheme\" content=\"dark light\">\n"
        "<title>SpicyStock strategy</title>\n"
        "<link rel=\"icon\" href=\"design-system/assets/favicon.ico\" sizes=\"16x16 32x32 48x48\">\n"
        "<link rel=\"stylesheet\" href=\"design-system/sc.css\">\n"
        "<script src=\"design-system/sc-theme.js\"></script>\n"
        f"<meta name=\"spicystock-strategy\" content=\"version {VERSION}; record sha256 {digest}\">\n"
        "</head>\n")
    intro = (
        f'<header class="sc-section"><p class="sc-eyebrow">SpicyStock</p><h1 class="sc-title">The strategy, as the record\'s rules state it</h1>'
        f'<p class="sc-dek">Generated from the record for {_e(run.get("session") or UNRECORDED)} (published '
        f'{_e(run.get("published_at") or UNRECORDED)}, rules version <code>{_e(rules_version or UNRECORDED)}</code>). '
        f'Every number here is a rule that record archived, or the code\'s own constant where it archives none, '
        f'named at the end; <code>tools/build_strategy_page.py --check</code> refuses a stale page. It decides '
        f'nothing and recommends nothing: the owner places every order.</p>'
        f'<p><a href="./">Back to the latest scan</a></p></header>')
    r = Rules(data)
    body = "".join(part(data, r) for part in SECTIONS) + provenance_note(r)
    return head + f'<body>\n<main class="sc-page sc-wrap sc-wrap--prose">{intro}{body}</main>\n</body>\n</html>\n'


def record_digest(page: str) -> str | None:
    """The record digest a page names in its meta, or None."""
    m = re.search(r'<meta name="spicystock-strategy" content="version [^;"]+; record sha256 ([0-9a-f]{64})">', page)
    return m.groups()[0] if m else None


def write(docs: Path) -> Path:
    """Write the page beside the installed record, atomically."""
    import os
    import tempfile
    raw = (docs / "data.json").read_bytes()
    text = build(raw)
    fd, tmp = tempfile.mkstemp(dir=docs, prefix=".strategy-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, docs / FILE)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return docs / FILE


def check(docs: Path) -> list[str]:
    """Every way the committed page is not what the code and the committed record write, named."""
    path = docs / FILE
    if not path.exists():
        return [f"{FILE} is missing"]
    try:
        want = build((docs / "data.json").read_bytes())
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return [f"{FILE} cannot be built from data.json: {type(exc).__name__}: {exc}"]
    try:
        have = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{FILE} cannot be read: {type(exc).__name__}"]
    return [] if have == want else [f"{FILE} is not what the code and the committed record write"]
