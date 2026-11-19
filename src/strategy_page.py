"""``docs/strategy.html``: the strategy as the code and tonight's record state it.

Every number the page prints is read from a module constant or from the
installed record, never typed: the market light's five rules with tonight's
scaled thresholds and values, the two discovery scans and the admission
gate, the checklist's weights, bands, gate letters and vetoes, the ticket's
trigger, limit and stop, every exit rule from ``plan.EXIT_RULES`` with its
source mark (the one third-party rule attributed to the EP9M backtest it
comes from), and the night's candidate funnel. ``build()`` is a pure
function of the record's bytes; the evening writes the page after the
record (``pipeline.publish_strategy()``), and ``tools/build_strategy_page.py
--check`` refuses a committed page that is not what the code and the
committed record write. The page decides nothing and recommends nothing.
"""
from __future__ import annotations

import hashlib
from html import escape
import json
from pathlib import Path
import re

VERSION = 1
FILE = "strategy.html"
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


def _e(value) -> str:
    return escape(str(value))


def _pct(value) -> str:
    return f"{value:g}%" if isinstance(value, (int, float)) else "an unrecorded percentage"


def _table(head: list[str], rows: list[list], cls: str = "sc-table sc-table--compact") -> str:
    th = "".join(f"<th>{_e(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<div class="sc-table-scroll"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def _section(title: str, eyebrow: str, body: str) -> str:
    return (f'<section class="sc-section"><p class="sc-eyebrow">{_e(eyebrow)}</p>'
            f'<h2>{_e(title)}</h2>{body}</section>')


# ----------------------------------------------------------- the sections ---
def market(data: dict) -> str:
    from src import breadth, pipeline
    regime = data.get("breadth", {}).get("regime", {}) if isinstance(data.get("breadth"), dict) else {}
    t, i = regime.get("thresholds") or {}, regime.get("inputs") or {}
    raw = (data.get("rules") or {}).get("breadth") or {}
    rows = []
    if t and i:
        rows = [
            ["red", f"down {_e(f'{breadth.BURST_PCT:g}')}% today at or over {_e(t['down4_alarm'])} ({_e(raw.get('down4_alarm'))} of {_e(f"{t['reference_universe']:,}")} scaled to {_e(t['universe'])} names)",
             _e(i["down4"]), _e("fired" if i["down4"] >= t["down4_alarm"] else "clear")],
            ["red", f"{_e(breadth.RATIO_LONG_SESSIONS)}-session up/down ratio under {_e(t['ratio_10d_red'])}",
             _e(i["ratio_10d"]), _e("fired" if i["ratio_10d"] is not None and i["ratio_10d"] < t["ratio_10d_red"] else "clear")],
            ["red", f"{_e(breadth.RATIO_SHORT_SESSIONS)}-session ratio under {_e(t['ratio_5d_red'])} while today's down count exceeds its up count",
             f"{_e(i['ratio_5d'])} ({_e(i['down4'])} down, {_e(i['up4'])} up)",
             _e("fired" if i["ratio_5d"] is not None and i["ratio_5d"] < t["ratio_5d_red"] and i["down4"] > i["up4"] else "clear")],
            ["yellow", f"{_e(breadth.RATIO_LONG_SESSIONS)}-session ratio under {_e(t['ratio_10d_yellow'])}",
             _e(i["ratio_10d"]), _e("fired" if i["ratio_10d"] is not None and i["ratio_10d"] < t["ratio_10d_yellow"] else "clear")],
            ["yellow", f"up {_e(f'{breadth.MONTH_BIG_MOVE_PCT:g}')}% in a month over {_e(t['up50_month_hot'])} ({_e(raw.get('up50_month_hot'))} of {_e(f"{t['reference_universe']:,}")} scaled)",
             _e(i["up50_month"]), _e("fired" if i["up50_month"] > t["up50_month_hot"] else "clear")],
        ]
    grades = {"green": ", ".join(pipeline.TRADE_GRADES), "yellow": ", ".join(pipeline.YELLOW_GRADES), "red": "none"}
    lights = _table(["light", "size multiplier", "grades admitted"],
                    [[_e(k), _e(f"{breadth.SIZE_MULTIPLIER[k]:g}"), _e(grades[k])] for k in LIGHTS])
    verdict = regime.get("verdict")
    return _section(
        "The market light", "the regime gate",
        f"<p>Tonight's light is <strong>{_e(verdict or 'not recorded')}</strong>. Red on any red rule, yellow on any "
        f"yellow rule, green otherwise. The two count thresholds are Bonde's counts over his reference universe of "
        f"{_e(f'{breadth.REFERENCE_UNIVERSE:,}')} names, scaled to tonight's measurable universe; the ratios are not "
        f"scaled. This gate is this project's reading of his Market Monitor; it is not shown here to improve "
        f"outcomes.</p>"
        + (_table(["tier", "rule (tonight's thresholds)", "tonight's value", "tonight"], rows) if rows
           else "<p>The record carries no regime inputs to print.</p>")
        + "<h3>What each light admits</h3>" + lights)


def discovery(data: dict) -> str:
    from src import admission, scans
    words = dict(admission.DOLLAR_CHECKS)
    burst_pct = f"{(scans.BURST_RATIO - 1) * 100:g}%"
    return _section(
        "Discovery", "what the scans find",
        "<ul>"
        f"<li><strong>The {_e(burst_pct)} burst scan</strong>: the close at least {_e(scans.BURST_RATIO)}× the previous close, "
        f"volume above the previous session's, and at least {_e(f'{scans.MIN_VOLUME:,}')} shares.</li>"
        f"<li><strong>The dollar scan</strong>: the close at least ${_e(f'{scans.DOLLAR_MOVE:.2f}')} over the "
        f"session's own open (the day's body, the gap excluded), on more than {_e(f'{scans.MIN_VOLUME:,}')} shares.</li>"
        f"<li><strong>The admission gate</strong> (<code>{_e(admission.POLICY)}</code>): a name the {_e(burst_pct)} scan found is "
        f"admitted; a name the dollar scan alone found is admitted only on a {_e(words['RE'].replace('_', ' '))} and "
        f"{_e(words['VOL'].replace('_', ' '))} day (the checklist's RE and VOL checks). Otherwise: "
        f"{_e(admission.NOT_ADMITTED_WORDS)}: research only, no ticket.</li>"
        "</ul>")


def checklist(data: dict) -> str:
    from src import grader, quality
    labels = {}
    for b in data.get("bursts", []) if isinstance(data.get("bursts"), list) else []:
        for c in ((b.get("quality") or {}).get("checks") or []) if isinstance(b, dict) else []:
            if isinstance(c, dict) and c.get("letter") and c.get("label"):
                labels.setdefault(c["letter"], c["label"])
    weights = _table(["letter", "what it checks", "points"],
                     [[_e(k), _e(labels.get(k, "")), _e(f"{w:g}")] for k, w in quality.WEIGHTS.items()]
                     + [[_e(k), _e(labels.get(k, "")), "no points (counts toward the A+ tally only)"] for k in quality.EXTRA_CHECKS])
    bands = ", ".join(f"{g} from {s:g}" for s, g in grader.GRADE_BANDS) + f", {grader.SKIP} under {grader.GRADE_BANDS[-1][0]:g}"
    vetoes = {}
    for b in data.get("bursts", []) if isinstance(data.get("bursts"), list) else []:
        for c in ((b.get("quality") or {}).get("checks") or []) if isinstance(b, dict) else []:
            if isinstance(c, dict) and c.get("key") in VETO_CHECKS and c.get("threshold"):
                vetoes.setdefault(c["key"], (c.get("letter"), c["threshold"]))
    return _section(
        "The checklist", "how a name is graded",
        weights
        + f"<p>A passed letter earns its points, a partial half. Bands: {_e(bands)}. A+ also needs "
          f"{_e(quality.MIN_A_PLUS_LETTERS)} checks at their A+ standard, and the top bands ({_e(', '.join(quality.GATED_GRADES))}) need "
          f"{_e(' and '.join(quality.GRADE_GATE_LETTERS))} passed outright or the grade is capped at "
          f"{_e(quality.GATE_CAP)}. The weighting is this project's: Bonde publishes no weights or pass count.</p>"
        + f"<p>Vetoes ({_e(', '.join(quality.VETO_NAMES))}): <code>{_e(quality.VETO_UP_DAYS_NAME)}</code> at "
          f"{_e(quality.VETO_UP_DAYS)} or more rising closes of any size before the burst; "
          f"<code>{_e(quality.VETO_NOT_LINEAR)}</code> when the prior leg fails linearity (ER under {_e(quality.MIN_ER)})."
          + (" Tonight's records state them as: " + "; ".join(f"{_e(vetoes[k][0])} — {_e(vetoes[k][1])}" for k in VETO_CHECKS) + "."
             if set(VETO_CHECKS) <= set(vetoes) else "")
          + "</p>")


def ticket(data: dict) -> str:
    from src import plan
    account = data.get("account") if isinstance(data.get("account"), dict) else {}
    archived = ((data.get("rules") or {}).get("plan") or {}) if isinstance(data.get("rules"), dict) else {}
    return _section(
        "The ticket", "a day buy stop-limit with a one-triggers-the-other sell stop",
        "<ul>"
        f"<li><strong>Buy stop</strong> (<code>{_e(plan.BURST_TRIGGER_RULE)}</code>): the burst close plus the larger of "
        f"${_e(f'{plan.TRIGGER_CENTS:.2f}')} and {_e(_pct(plan.TRIGGER_FRACTION * 100))} of the close.</li>"
        f"<li><strong>Limit</strong>: the close plus {_e(_pct(archived.get('entry_above_pct')))} (the outer extension line, as the record archives it), narrowed to the highest "
        f"price at which the stop is still within {_e(_pct(plan.MAX_STOP_PCT))} of the limit.</li>"
        f"<li><strong>Stop</strong>: the burst day's low, else its range midpoint, the first within "
        f"{_e(_pct(plan.MAX_STOP_PCT))} of the limit and under the buy stop; a ticket neither can carry is withheld. "
        f"A stop wider than {_e(_pct(plan.IDEAL_STOP_PCT))} multiplies the risk by {_e(f'{plan.STOP_RISK_MULTIPLIER:g}')}.</li>"
        f"<li><strong>Size</strong>: shares at the limit (<code>{_e(plan.SIZING_BASIS)}</code>) risking "
        f"{_e(_pct(account.get('risk_pct', 0)))} of the ${_e(f'{account.get('equity', 0):,.0f}')} model account times "
        f"the light's multiplier, capped at {_e(_pct(account.get('max_position_pct', 0)))} of it, "
        f"{_e(account.get('max_open_positions'))} model slots. Model sizing, never the owner's holdings.</li>"
        "</ul>")


def exits(data: dict) -> str:
    from src import brief, plan, scans
    rows = []
    for rule in brief.exit_rules(plan):
        mark = rule["source"]
        rows.append([f"<code>{_e(rule['step'])}</code>", _e(rule["when"]), _e(rule["rule"]),
                     f'<span class="sc-chip sc-chip--neutral" title="{_e(SOURCE_MARKS.get(mark, mark))}">{_e(mark)}</span>'])
    marks = "; ".join(f"{k}: {v}" for k, v in SOURCE_MARKS.items())
    third = [r for r in plan.EXIT_RULES if r["source"] == "T"]
    named = {r["key"]: re.search(r"\(([^:()]+):", r["rule"]) for r in third}
    return _section(
        "The exits", "in the order the model applies them",
        _table(["rule", "when", "then", "source"], rows)
        + f"<p class=\"sc-hint\">Source marks: {_e(marks)}.</p>"
        + "".join(f"<p><strong>Attribution.</strong> <code>{_e(key)}</code> is a third party's measurement, "
                  f"{_e(m.group(1) if m else 'unnamed in the rule')}, of a different setup (the episodic pivot on at "
                  f"least {_e(f'{scans.EP9M_MIN_VOLUME:,}')} shares), carried over by this build and not validated "
                  f"on bursts here.</p>" for key, m in named.items()))


def funnel(data: dict) -> str:
    f = data.get("funnel") if isinstance(data.get("funnel"), dict) else None
    if not f:
        return _section("Tonight's candidate funnel", "where each candidate stopped",
                        "<p>This record carries no funnel.</p>")
    labels = f.get("labels") or {}
    stages = ((f.get("reaction") or {}).get("stages") or {})
    rows = [[_e(labels.get(k, k)), _e(f"{n:,}")] for k, n in stages.items() if isinstance(n, int) and n]
    return _section(
        "Tonight's candidate funnel", "where each candidate stopped",
        f"<p>{_e(f.get('sentence', ''))}</p>" + (_table(["stage", "reaction candidates"], rows) if rows else ""))


# ------------------------------------------------------------------- page ---
def build(canonical_raw: bytes) -> str:
    """The page for one installed record's bytes."""
    data = json.loads(canonical_raw)
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
        f'<header class="sc-section"><p class="sc-eyebrow">SpicyStock</p><h1 class="sc-title">The strategy, as the code states it</h1>'
        f'<p class="sc-dek">Generated from the rules version <code>{_e(rules_version)}</code> and the record for '
        f'{_e(run.get("session"))} (published {_e(run.get("published_at"))}). Every number here is read from the '
        f'code\'s constants or that record; <code>tools/build_strategy_page.py --check</code> refuses a stale page. '
        f'It decides nothing and recommends nothing: the owner places every order.</p>'
        f'<p><a href="./">Back to the latest scan</a></p></header>')
    body = "".join(part(data) for part in (market, discovery, checklist, ticket, exits, funnel))
    return head + f'<body>\n<main class="sc-page sc-wrap sc-wrap--prose">{intro}{body}</main>\n</body>\n</html>\n'


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
    path = docs / FILE
    if not path.exists():
        return [f"{FILE} is missing"]
    want = build((docs / "data.json").read_bytes())
    return [] if path.read_text(encoding="utf-8") == want else [f"{FILE} is not what the code and the committed record write"]
