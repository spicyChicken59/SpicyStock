"""docs/data.json writer, the cover and summary sentences, and the email digest.

Three surfaces read what this module writes -- the page, the email and the
Actions log -- and every sentence they print about a night is composed HERE
from published numbers, so the three cannot disagree. Nothing in this file
computes a rule: the regime, the grades and the plan arrive decided, and the
report says what they are.

The Resend transport is the proven one from the old emailer, ported
unchanged in behaviour: the test-mode respelling, the recipient diagnosis
that names domains and never addresses, and the count-not-addresses log
line. `redact_addresses()` is the old pipeline's, applied to every recorded
problem before it can reach a public file.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import logging
import math
import os
import re
from pathlib import Path
from typing import Any

import resend

log = logging.getLogger(__name__)

# --- identity ----------------------------------------------------------------

SCHEMA_VERSION = 2
APP_NAME = "SpicyStock"
APP_VERSION = "2.0"
PAGE_URL = "https://spicychicken59.github.io/SpicyStock/"

#: Environment the digest cannot go out without, collected by preflight.
#: Empty counts as missing: an unset GitHub secret arrives as ''.
REQUIRED_ENV: tuple[str, ...] = ("RESEND_API_KEY", "EMAIL_TO")
DEFAULT_SENDER = "onboarding@resend.dev"

# --- run.problems: the seven words --------------------------------------------

PROBLEM_KINDS: tuple[str, ...] = (
    "universe_cached", "coverage_thin", "claude_unavailable", "claude_partial",
    "chart_missing", "email_failed", "push_retried",
)

#: The one fixed sentence the page and the email print per kind. No free
#: text from outside the codebase reaches either surface through a problem.
PROBLEM_SENTENCES: dict[str, str] = {
    "universe_cached": "The stock directory could not be refreshed; tonight's universe is the cached one.",
    "coverage_thin": "Part of the universe was not read: the bars fetch ran out of time or names answered late.",
    "claude_unavailable": "The model did not answer; every grade tonight is the checklist's alone.",
    "claude_partial": "The model answered for some names and not others; the rest are graded by the checklist alone.",
    "chart_missing": "A chart did not render; the grade stands on the numbers.",
    "email_failed": "The digest could not be delivered; the page is the record.",
    "push_retried": "Committing the record took more than one push.",
}
MESSAGE_MAX_CHARS = 200

# --- the vocabularies the record is validated against -------------------------

RUN_STATUSES: tuple[str, ...] = ("ok", "degraded", "closed", "failed")
SESSION_STATES: tuple[str, ...] = ("open", "closed")
GRADES: tuple[str, ...] = ("A+", "A", "B", "C", "skip")
REGIMES: tuple[str, ...] = ("green", "yellow", "red")
SERIES_KEYS: tuple[str, ...] = ("date", "o", "h", "l", "c", "v")

# --- the cover -----------------------------------------------------------------

H1_TRADE = "Trade tomorrow. {n} A-quality {noun}."
H1_TRADE_SMALL = "Trade small. {n} A+ {noun}."
H1_STAND_ASIDE = "Stand aside."
H1_KEEP_CASH = "Nothing qualifies. Keep cash."
H1_CLOSED = "Market closed. Plans unchanged."
H1_FAILED = "No verdict for {expected}."

VERBS: tuple[str, ...] = ("trade", "trade small", "stand aside", "keep cash", "hold", "none")
ORDERS_ACTION = ("Tomorrow's orders", "#orders")
HOLD_ACTION = ("Open model plans", "#hold")

#: What the regime's size multiplier says in words. Read off the published
#: number, never off the verdict, so a moved multiplier moves the sentence.
SIZE_WORDS: dict[float, str] = {1.0: "Full size.", 0.5: "Half size.", 0.0: "No new positions."}

#: The chip word for an open plan's status. An unknown word is printed as
#: itself, upper-cased, rather than mapped onto the nearest known one.
#: One word per status src.record can write; docs/app.js prints the same
#: eleven (tests/test_docs.py holds the two equal). UNCERTAIN is a fill the
#: bars cannot establish: not held, not out, not freed.
PLAN_STATUS_WORDS: dict[str, str] = {
    "hold": "HOLD", "sell_half": "SELL HALF", "sell_into_strength": "SELL INTO STRENGTH",
    "exit": "SELL", "stopped": "STOPPED", "expired": "EXPIRED", "pending": "PENDING",
    "not_filled": "NOT FILLED", "uncertain": "UNCERTAIN", "unreadable": "UNREADABLE", "unmeasured": "UNMEASURED",
}

CLOSED_SUBJECT = "Market closed — plans unchanged"
FAILED_SUBJECT = "FAILED — no plan for {expected}"

#: One paragraph per top-level key of docs/data.json: what it means and what
#: it never means. Validation holds this to the keys the file carries.
CONTRACT: dict[str, str] = {
    "schema_version": "2. The page refuses any other number rather than guessing at an older shape.",
    "generated": "When this file was written, ISO-8601 UTC. The page reads staleness off run.session, "
                 "run.session_state and this, against the browser's clock in ET.",
    "app": "Who wrote the file: the app name, its version, and rules_version -- a 12-hex digest of the "
           "rules block, so two nights under different constants never read as one screener.",
    "cover": "The night's verdict as sentences: h1 (one of six fixed forms), dek, the primary action's label "
             "and anchor, and the verb. Composed from the numbers below; never edited by hand.",
    "run": "The run that produced this file: session, session_state, expected_session, status "
           "(ok|degraded|closed|failed), problems (stage, kind, message -- kind is one of seven words and the "
           "page prints one fixed sentence per kind), coverage, counts, email state, timings. run.sanitised "
           "counts the non-finite numbers replaced with null on the way in.",
    "nights": "The last twenty runs as a ring: session, status, published_at. The reliability dots.",
    "account": "The configured sizing assumptions every plan below was computed from: equity, risk per "
               "trade, the position cap, the slot count. Not a balance, not settled cash, not buying power.",
    "rules": "Every strategy constant, keyed by module. Archived so the record says which screener made it.",
    "breadth": "The Market Monitor for the session and the regime verdict with its reasons verbatim. "
               "The size multiplier is the regime's; the plans already carry it.",
    "bursts": "Every 4% or $ breakout the scan found, graded, with its plan when it has one, its summary "
              "sentence and its series (last 120 bars, trades and the closest miss only). Scored or refused, "
              "a burst is here; a name that never burst is not.",
    "trades": "Tickers of the bursts to trade tomorrow, ranked; those with order lines first. On a red "
              "regime this is empty whatever the grades say.",
    "beyond_cap": "Tickers of A-quality bursts with a plan and no ticket: withheld by the stop rule at the "
                  "limit, past the slots or the configured equity, or sized to no whole share. Each has a "
                  "reason in cash_budget.cut. Not checklist refusals.",
    "cash_budget": "Model allocation: what tomorrow's tickets would commit against the configured equity, the "
                   "model slots used (open model plans count), and every plan without a ticket with its kind "
                   "and reason. Never a balance or buying power.",
    "watchlist": "Anticipation names: top (with a plan each) and also_quiet, with counts. Alerts, not trades.",
    "open_plans": "Every published plan still inside its window, replayed to this session as a model: status "
                  "word, the instruction sentence, and for an uncertain fill the reason. SpicyStock does not "
                  "know what you hold: a plan you never took is a row to ignore.",
    "scorecard": "The rules' record over the published plans as a model of their fills, always with n, the "
                 "read threshold and the uncertain count by reason. Rates are over settled plans alone. The "
                 "rules' record, not yours. Null until a plan has settled.",
    "closest_miss": "On any night, the highest-scored burst not in trades and why it missed; the page shows "
                    "it when trades is empty. Null when every burst is a trade or there were none.",
    "_contract": "This paragraph per key. If a key is here and not above, or above and not here, the file is refused.",
}

# --- small formatters ----------------------------------------------------------

_DASH = "—"


def esc(value: Any) -> str:
    """Text on its way into HTML, made safe to be text.

    A reason of "Breakout above <resistance> on 3x volume" renders in a mail
    client as "Breakout above" -- the parser takes `<resistance>` for a tag
    and swallows the rest, silently. Applied to LEAVES, never to the
    fragments this module builds, which carry their own tags on purpose.
    """
    return html.escape("" if value is None else str(value), quote=True)


def _num(value: Any) -> float | None:
    """A finite number or None; bools and strings are not numbers here."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _int(value: Any) -> int | None:
    f = _num(value)
    return int(f) if f is not None and float(f).is_integer() else None


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _price(value: Any) -> str | None:
    f = _num(value)
    return f"{f:.2f}" if f is not None else None


def _money(value: Any) -> str | None:
    f = _num(value)
    return f"${f:,.0f}" if f is not None else None


def _show(value: str | None) -> str:
    """A formatted value for a cell, or the dash -- never the word None."""
    return value if value is not None else _DASH


def _plural(n: int, noun: str) -> str:
    return noun if n == 1 else noun + "s"


def _get(mapping: Any, *path: str) -> Any:
    """Walk nested dicts; None the moment a step is not a dict or is absent."""
    node = mapping
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _first(*values: Any) -> Any:
    for v in values:
        if v is not None:
            return v
    return None


# --- redaction and problems ----------------------------------------------------

_ADDRESS = re.compile(r"[A-Za-z0-9._%+\-]+@((?:[A-Za-z0-9\-]+\.)+[A-Za-z]{2,})")
_TAG = re.compile(r"<[^>]*>")
_WS = re.compile(r"\s+")


def redact_addresses(text: str) -> str:
    """An email address inside a recorded sentence becomes its domain alone.

    A recorded problem is the one place free text from OUTSIDE the codebase
    enters the record, and the record is public. Resend's test-mode refusal
    names the address the account is registered under -- the owner's
    personal one -- and the first live night put it on the page. The domain
    is kept, because "…@gmail.com" still says which account it is about.
    """
    return _ADDRESS.sub(lambda m: "…@" + m.group(1), text)


def problem(stage: str, kind: str, message: Any) -> dict:
    """One run.problems entry: a known kind, a stage, and a plain-text
    message with its tags stripped, its addresses masked and its length
    held to MESSAGE_MAX_CHARS. Any other kind is refused."""
    if kind not in PROBLEM_KINDS:
        raise ValueError(f"unknown problem kind {kind!r}; the words are {', '.join(PROBLEM_KINDS)}")
    stage_word = _text(stage)
    if stage_word is None:
        raise ValueError("a problem names the stage it happened in")
    text = html.unescape(_TAG.sub(" ", "" if message is None else str(message)))
    text = redact_addresses(_WS.sub(" ", text).strip())
    if len(text) > MESSAGE_MAX_CHARS:
        text = text[:MESSAGE_MAX_CHARS - 1].rstrip() + "…"
    return {"stage": stage_word, "kind": kind, "message": text}


def problem_sentences(problems: Any) -> list[str]:
    """The fixed sentence for each kind present, once each, in first-seen order."""
    seen: dict[str, None] = {}
    for p in problems if isinstance(problems, list) else []:
        kind = _get(p, "kind")
        sentence = PROBLEM_SENTENCES.get(kind) if isinstance(kind, str) else None
        seen[sentence or "A problem this report has no sentence for was recorded."] = None
    return list(seen)


# --- the sentences ---------------------------------------------------------------

def breadth_sentence(breadth: Any) -> str:
    """"Breadth is green: 412 up 4% vs 96 down, 10-day ratio 2.9. Full size."

    The counts and the ratio are the snapshot's own; the size rule is read
    off the regime's multiplier; on a yellow or red night the regime's
    reasons follow, verbatim, because that is when the verb changed.
    """
    regime = _get(breadth, "regime") or {}
    verdict = _get(regime, "verdict")
    if verdict not in REGIMES:
        return "Breadth could not be measured; no size rule applies."
    numbers = _get(regime, "numbers") or {}
    up4 = _int(_first(_get(breadth, "up4"), numbers.get("up4")))
    down4 = _int(_first(_get(breadth, "down4"), numbers.get("down4")))
    r10 = _num(_first(_get(breadth, "ratio_10d"), numbers.get("ratio_10d")))
    facts = []
    if up4 is not None and down4 is not None:
        facts.append(f"{up4:,} up 4% vs {down4:,} down")
    if r10 is not None:
        facts.append(f"10-day ratio {_ratio(r10)}")
    head = f"Breadth is {verdict}: {', '.join(facts)}." if facts else f"Breadth is {verdict}."
    mult = _num(_get(regime, "size_multiplier"))
    size = SIZE_WORDS.get(mult, f"{mult:g}× size.") if mult is not None else None
    parts = [head] + ([size] if size else [])
    if verdict != "green":
        reasons = [r.strip() for r in (regime.get("reasons") or []) if _text(r)]
        if reasons:
            joined = "; ".join(reasons)
            parts.append(joined if joined.endswith(".") else joined + ".")
    return " ".join(parts)


def no_trade_sentence(bursts: Any, closest_miss: Any) -> str:
    """"14 bursts found, none A-quality. The closest miss is below." -- or,
    when a burst qualified and its ticket did not, "14 bursts found, 2 with
    a qualifying setup and no ticket; each card says why." A qualifying
    setup is a burst that carries a plan (the run plans admitted grades
    only); its ticket was withheld by the stop rule, or cut."""
    rows = bursts if isinstance(bursts, list) else []
    n = len(rows)
    planned = sum(1 for b in rows if isinstance(b, dict) and isinstance(b.get("plan"), dict))
    if n == 0:
        head = "No bursts found."
    elif planned:
        head = (f"{n} {_plural(n, 'burst')} found, {planned} with a qualifying setup and no ticket "
                f"(withheld by the stop rule at the limit, or cut); each card says why.")
    elif n == 1:
        head = "1 burst found, not A-quality."
    else:
        head = f"{n} bursts found, none A-quality."
    return head + (" The closest miss is below." if closest_miss else "")


def _cover(h1: str, dek: str, action: tuple[str, str], verb: str) -> dict:
    return {"h1": h1, "dek": dek, "action_label": action[0], "action_target": action[1], "verb": verb}


def cover(run: dict, breadth: dict | None, trades: list, bursts: list,
          closest_miss: dict | None) -> dict:
    """The h1, dek, primary action and verb for the night -- six h1 forms.

    Precedence is the order a reader needs it: a run with no verdict, then a
    closed market, then a red regime (which empties the trade list whatever
    the grades say), then the trades under the regime's size, then nothing.
    On a yellow night the list is A+ by the plan's own rule, and the h1 names
    it so; the count is the list's, not a recount of grades.
    """
    run = run if isinstance(run, dict) else {}
    expected = _first(_text(run.get("expected_session")), _text(run.get("session")), "the next session")
    session = _text(run.get("session"))
    problems = problem_sentences(run.get("problems"))
    if run.get("status") == "failed":
        dek = "The evening run stopped before it published a plan. The open model plans are unchanged."
        if problems:
            dek += " " + problems[0]
        return _cover(H1_FAILED.format(expected=expected), dek, HOLD_ACTION, "none")
    if run.get("session_state") == "closed" or run.get("status") == "closed":
        dek = f"No session on {expected}."
        if session:
            dek += f" The plans from {session} stand; day counts did not advance."
        return _cover(H1_CLOSED, dek, HOLD_ACTION, "hold")
    verdict = _get(breadth, "regime", "verdict")
    sentence = breadth_sentence(breadth)
    n = len(trades) if isinstance(trades, list) else 0
    if verdict == "red":
        return _cover(H1_STAND_ASIDE, sentence, HOLD_ACTION, "stand aside")
    if n and verdict == "yellow":
        return _cover(H1_TRADE_SMALL.format(n=n, noun=_plural(n, "burst")), sentence,
                      ORDERS_ACTION, "trade small")
    if n:
        return _cover(H1_TRADE.format(n=n, noun=_plural(n, "burst")), sentence, ORDERS_ACTION, "trade")
    return _cover(H1_KEEP_CASH, no_trade_sentence(bursts, closest_miss), HOLD_ACTION, "keep cash")


def summary(burst: dict) -> str:
    """One sentence per burst, from published numbers only, for the chart's
    aria-label, the card caption and the email line. A missing field drops
    its clause; nothing here prints None."""
    burst = burst if isinstance(burst, dict) else {}
    ticker = _text(burst.get("ticker")) or "Unnamed"
    quality = burst.get("quality") if isinstance(burst.get("quality"), dict) else {}
    plan = burst.get("plan") if isinstance(burst.get("plan"), dict) else {}

    move = []
    gain = _num(burst.get("gain_pct"))
    if gain is not None:
        move.append(f"{gain:+.1f}%")
    vol = _num(burst.get("volume_vs_prior"))
    if vol is not None:
        move.append(f"on {vol:.1f}× volume")
    sessions = _int(_first(quality.get("base_sessions"), _get(quality, "base", "length"),
                           _get(burst, "base", "sessions")))
    depth = _base_depth_pct(burst, quality)
    if sessions is not None and depth is not None:
        move.append(f"out of a {sessions}-session base {depth:.1f}% deep")
    elif sessions is not None:
        move.append(f"out of a {sessions}-session base")
    elif depth is not None:
        move.append(f"out of a base {depth:.1f}% deep")
    first = f"{ticker}: {' '.join(move)}." if move else f"{ticker}: no measurements published."

    clauses = []
    lo, hi = _price(plan.get("entry_low")), _price(plan.get("entry_high"))
    if lo and hi:
        buy = f"buy {lo}–{hi} tomorrow"
    elif lo or hi:
        buy = f"buy at {lo or hi} tomorrow"
    else:
        buy = None
    if buy:
        window = _first(_text(plan.get("entry_window")), _int(plan.get("entry_window_minutes")))
        if isinstance(window, str):
            buy += f" in the {window}"
        elif window is not None:
            buy += f" in the first {window} minutes"
        clauses.append(buy)
    stop = _price(plan.get("stop"))
    if stop:
        clauses.append(f"stop {stop}")
    t_lo = _price(_first(plan.get("target_low"), _get(plan, "targets", "low")))
    t_hi = _price(_first(plan.get("target_high"), _get(plan, "targets", "high")))
    if t_lo and t_hi:
        aim = f"aim {t_lo}–{t_hi}"
    elif t_lo or t_hi:
        aim = f"aim {t_lo or t_hi}"
    else:
        aim = None
    if aim:
        horizon = _int(_first(plan.get("final_exit_day"), plan.get("horizon_sessions"),
                              plan.get("hold_sessions")))
        if horizon is not None:
            aim += f" by day {horizon}"
        clauses.append(aim)
    second = (", ".join(clauses)[0].upper() + ", ".join(clauses)[1:] + ".") if clauses else None

    grade = _text(_first(burst.get("grade"), quality.get("grade_mechanical"), quality.get("grade")))
    score = _num(_first(burst.get("score"), quality.get("score")))
    passes, of = _int(quality.get("passes")), _int(quality.get("of"))
    verdict = []
    if grade and score is not None:
        verdict.append(f"{grade} {score:.1f}")
    elif grade:
        verdict.append(grade)
    elif score is not None:
        verdict.append(f"score {score:.1f}")
    if passes is not None and of is not None:
        verdict.append(f"{passes} of {of} criteria")
    third = (", ".join(verdict) + ".") if verdict else None

    return " ".join(s for s in (first, second, third) if s)


def _base_depth_pct(burst: dict, quality: dict) -> float | None:
    """How deep the base is, as a percentage of its high: a published depth
    if the record carries one, else the base's own high and low, which the
    checklist publishes beside its length."""
    stated = _num(_first(quality.get("base_depth_pct"), _get(quality, "base", "depth_pct"),
                         _get(burst, "base", "depth_pct")))
    if stated is not None:
        return stated
    high, low = _num(_get(quality, "base", "high")), _num(_get(quality, "base", "low"))
    if high is None or low is None or high <= 0 or low > high:
        return None
    return round(100.0 * (high - low) / high, 1)


def miss_reason(burst: dict) -> str | None:
    """Why a burst is not a trade, off its own quality block: the stated
    reason, else its vetoes, else the first failing check's label."""
    quality = burst.get("quality") if isinstance(burst.get("quality"), dict) else {}
    stated = _text(_first(quality.get("why"), quality.get("first_fail")))
    if stated:
        return stated
    vetoes = [v for v in (quality.get("vetoes") or []) if _text(v)] if isinstance(quality.get("vetoes"), list) else []
    if vetoes:
        return "vetoed: " + ", ".join(str(v) for v in vetoes)
    checks = quality.get("checks") if isinstance(quality.get("checks"), list) else []
    for check in checks:
        if isinstance(check, dict) and check.get("pass") is False:
            label = _text(_first(check.get("label"), check.get("key"), check.get("letter")))
            if label:
                return f"fails {label}"
    return None


def _ratio(value: float) -> str:
    """A breadth ratio as the record holds it (two places at most), printed
    the way the page prints it: 2.88 stays 2.88, 2.5 stays 2.5, 2 stays 2."""
    return f"{value:.2f}".rstrip("0").rstrip(".")


def closest_miss(bursts: list, trades: list, cut: list | None = None) -> dict | None:
    """The highest-scored burst that is neither a trade nor a plan the budget
    cut (a name with an order the slots could not take is not a miss), ties
    broken by ticker."""
    taken = set(trades) if isinstance(trades, list) else set()
    taken |= set(cut) if isinstance(cut, list) else set()
    rest = [b for b in (bursts or []) if isinstance(b, dict) and b.get("ticker") not in taken]
    if not rest:
        return None
    best = min(rest, key=lambda b: (-(_num(b.get("score")) if _num(b.get("score")) is not None else -math.inf),
                                    str(b.get("ticker"))))
    ticker, grade, score, why = best.get("ticker"), best.get("grade"), _num(best.get("score")), miss_reason(best)
    verdict = " ".join(str(x) for x in (grade, f"{score:.1f}" if score is not None else None) if x)
    sentence = f"{ticker} came closest" + (f" at {verdict}" if verdict else "") + (f": {why}." if why else ".")
    return {"ticker": ticker, "grade": grade, "score": score, "why": why, "sentence": sentence}


# --- the file ---------------------------------------------------------------------

def rules_version(rules: Any) -> str:
    """A 12-hex prefix of the sha256 of the rules block, serialised canonically."""
    blob = json.dumps(rules, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def _iso(value: Any) -> str:
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value)


def _sanitise(value: Any, path: str, replaced: list[str]) -> Any:
    """A JSON-ready copy: NaN and Infinity become null (their paths kept),
    numpy scalars become Python ones, dates become ISO strings."""
    if isinstance(value, dict):
        return {str(k): _sanitise(v, f"{path}.{k}" if path else str(k), replaced) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitise(v, path + "[]", replaced) for v in value]
    if isinstance(value, (bool, str)) or value is None:
        return value
    if isinstance(value, (dt.datetime, dt.date)):
        return _iso(value)
    if isinstance(value, Path):
        return str(value)
    if not isinstance(value, (int, float)) and hasattr(value, "item"):
        try:
            value = value.item()
        except (TypeError, ValueError):
            return value
    if isinstance(value, float) and not math.isfinite(value):
        replaced.append(path)
        return None
    return value


def validate(data: dict) -> None:
    """Refuse a file the page could not render honestly. Every failure is
    named, in one ValueError, so a night with two is not fixed twice."""
    faults: list[str] = []
    run = data.get("run")
    if not isinstance(run, dict):
        faults.append("run is not an object")
        run = {}
    if run.get("status") not in RUN_STATUSES:
        faults.append(f"run.status {run.get('status')!r} is not one of {RUN_STATUSES}")
    if run.get("session_state") is not None and run.get("session_state") not in SESSION_STATES:
        faults.append(f"run.session_state {run.get('session_state')!r} is not one of {SESSION_STATES}")
    problems = run.get("problems")
    if not isinstance(problems, list):
        faults.append("run.problems is not a list")
    else:
        for i, p in enumerate(problems):
            if not isinstance(p, dict) or not {"stage", "kind", "message"} <= set(p):
                faults.append(f"run.problems[{i}] lacks stage, kind or message")
                continue
            if p["kind"] not in PROBLEM_KINDS:
                faults.append(f"run.problems[{i}].kind {p['kind']!r} is not one of the seven words")
            if not isinstance(p["message"], str) or len(p["message"]) > MESSAGE_MAX_CHARS:
                faults.append(f"run.problems[{i}].message is not plain text of at most {MESSAGE_MAX_CHARS} chars")
    verdict = _get(data, "breadth", "regime", "verdict")
    if verdict is not None and verdict not in REGIMES:
        faults.append(f"breadth.regime.verdict {verdict!r} is not one of {REGIMES}")
    bursts = data.get("bursts")
    tickers: set = set()
    if not isinstance(bursts, list):
        faults.append("bursts is not a list")
    else:
        for i, b in enumerate(bursts):
            if not isinstance(b, dict):
                faults.append(f"bursts[{i}] is not an object")
                continue
            tickers.add(b.get("ticker"))
            for where, grade in (("grade", b.get("grade")),
                                 ("quality.grade_mechanical", _get(b, "quality", "grade_mechanical")),
                                 ("claude.grade", _get(b, "claude", "grade"))):
                if (where == "grade" or grade is not None) and grade not in GRADES:
                    faults.append(f"bursts[{i}].{where} {grade!r} is not one of {GRADES}")
            series = b.get("series")
            if series is not None:
                if not isinstance(series, list):
                    faults.append(f"bursts[{i}].series is not a list")
                else:
                    for j, bar in enumerate(series):
                        if not isinstance(bar, dict) or not set(SERIES_KEYS) <= set(bar):
                            faults.append(f"bursts[{i}].series[{j}] lacks one of {SERIES_KEYS}")
                            break
            if not isinstance(b.get("summary"), str) or not b["summary"]:
                faults.append(f"bursts[{i}].summary is not a sentence")
    for key in ("trades", "beyond_cap"):
        names = data.get(key)
        if not isinstance(names, list):
            faults.append(f"{key} is not a list")
        else:
            for name in names:
                if name not in tickers:
                    faults.append(f"{key} names {name!r}, which is not a burst")
    for key in ("nights", "open_plans"):
        if not isinstance(data.get(key), list):
            faults.append(f"{key} is not a list")
    if not isinstance(data.get("cover"), dict) or not _text(_get(data, "cover", "h1")):
        faults.append("cover.h1 is missing")
    version = _get(data, "app", "rules_version")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9a-f]{12}", version):
        faults.append("app.rules_version is not a 12-hex digest")
    contract = data.get("_contract")
    if not isinstance(contract, dict) or set(contract) != set(data):
        faults.append("_contract does not name exactly the top-level keys")
    if faults:
        raise ValueError("docs/data.json refused:\n  " + "\n  ".join(faults))


def build(run: dict, account: dict, rules: dict, breadth: dict, bursts: list[dict], trades: list[str],
          beyond_cap: list[str], cash_budget: dict, watchlist: dict, open_plans: list[dict],
          scorecard: dict | None, nights: list[dict], generated: Any) -> dict:
    """Assemble and validate the docs/data.json object (schema 2).

    Non-finite numbers are replaced with null and counted in run.sanitised
    before anything reads them; every burst without a summary sentence gets
    one; the cover and the closest miss are composed last, off the cleaned
    record, and the whole is validated before it is returned.
    """
    replaced: list[str] = []
    body = _sanitise({
        "run": dict(run or {}), "nights": list(nights or []), "account": dict(account or {}),
        "rules": dict(rules or {}), "breadth": dict(breadth or {}), "bursts": list(bursts or []),
        "trades": list(trades or []), "beyond_cap": list(beyond_cap or []),
        "cash_budget": dict(cash_budget or {}),
        "watchlist": dict(watchlist or {"top": [], "also_quiet": [], "counts": {}}),
        "open_plans": list(open_plans or []), "scorecard": scorecard,
    }, "", replaced)
    body["run"]["sanitised"] = {"replaced": len(replaced), "paths": replaced[:20]}
    for burst in body["bursts"]:
        if isinstance(burst, dict) and not _text(burst.get("summary")):
            burst["summary"] = summary(burst)
    miss = closest_miss(body["bursts"], body["trades"], body["beyond_cap"])
    data = {
        "schema_version": SCHEMA_VERSION,
        "generated": _iso(generated),
        "app": {"name": APP_NAME, "version": APP_VERSION, "rules_version": rules_version(body["rules"])},
        "cover": cover(body["run"], body["breadth"], body["trades"], body["bursts"], miss),
    }
    data.update(body)
    data["closest_miss"] = miss
    data["_contract"] = dict(CONTRACT)
    validate(data)
    return data


def write(data: dict, path: Path) -> None:
    """Write the file atomically: the bytes land in a sibling temp file and
    are renamed over the target, so a reader never sees a half-written one."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=1, sort_keys=False, ensure_ascii=False, allow_nan=False)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def contract_paths(data: Any) -> set[str]:
    """Every JSON path the object carries, dotted, arrays as [] -- so a
    manifest of the keys the page reads can be checked against a file."""
    paths: set[str] = set()

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                paths.add(child_path)
                walk(child, child_path)
        elif isinstance(value, list):
            child_path = path + "[]"
            paths.add(child_path)
            for item in value:
                walk(item, child_path)

    walk(data, "")
    return paths


# --- the email: HTML ------------------------------------------------------------------

_F_BODY = "'Instrument Sans',system-ui,-apple-system,sans-serif"
_F_DISPLAY = "'Bricolage Grotesque','Instrument Sans',system-ui,sans-serif"
_F_MONO = "'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

# Every surface below paints its own background and text colour, so the
# message reads the same in a dark and a light client: the light card set on
# the light page ground, and the ink callout, which is one colour in both.
_S_PAGE = f"background:#F2F4F8;padding:24px 16px;color:#2F3741;font:400 15px/1.6 {_F_BODY}"
_S_EYEBROW = (f"margin:0 0 10px;font:600 12px/1 {_F_MONO};letter-spacing:.4px;"
              "text-transform:lowercase;color:#165194")
_S_EYEBROW_SLASH = "color:#638AB7"
_S_INK = f"background:#111F31;border-radius:10px;padding:18px 20px;margin:0 0 16px;color:#F4F7FB;font:400 15px/1.6 {_F_BODY}"
_S_INK_LABEL = f"margin:0 0 7px;font:600 11px/1 {_F_MONO};letter-spacing:.4px;text-transform:lowercase;color:#A3C4EE"
_S_H1 = f"margin:0 0 8px;font:700 26px/1.15 {_F_DISPLAY};letter-spacing:-.3px;color:#F4F7FB"
_S_H2 = f"margin:22px 0 10px;font:700 18px/1.2 {_F_DISPLAY};letter-spacing:-.2px;color:#182E4B"
_S_CARD = (f"background:#FFFFFF;border:1px solid #CFD6DE;border-radius:14px;padding:16px 18px;margin:0 0 12px;"
           f"color:#2F3741;font:400 15px/1.6 {_F_BODY};box-shadow:0 1px 3px rgba(24,46,75,.08)")
_S_MUTED = "margin:6px 0 0;font-size:13px;color:#5D6671"
_S_TICKER = f"font:700 17px/1.2 {_F_MONO};color:#182E4B"
_S_PRE = (f"margin:10px 0 0;padding:10px 12px;background:#F3F7FC;border:1px solid #CFD6DE;border-radius:8px;"
          f"font:500 13px/1.5 {_F_MONO};color:#182E4B;white-space:pre-wrap;word-break:break-word")
_S_WARN = f"background:#FFE8E7;border:2px solid #BE2132;border-radius:10px;padding:14px 18px;margin:16px 0;color:#2F3741;font:400 15px/1.6 {_F_BODY}"
_S_WARN_LABEL = f"margin:0 0 7px;font:600 11px/1 {_F_MONO};letter-spacing:.4px;text-transform:lowercase;color:#BE2132"
_S_LINK = "color:#AC3400;text-decoration:underline"
_S_FOOT = f"margin:20px 0 0;font:400 12px/1.5 {_F_MONO};color:#5D6671"

_CHIP_TONES = {
    "brand": ("#E5EEF9", "#165194", "1px solid #9DB7D6"),
    "neutral": ("#F3F7FC", "#5D6671", "1px solid #CFD6DE"),
    "spice": ("#FFE9E2", "#AC3400", "1px solid #E2AA93"),
    "good": ("#E3F4E2", "#1B7E2A", "1px solid #9DCBA2"),
    "danger": ("transparent", "#BE2132", "1.5px solid #BE2132"),
}
_GRADE_TONE = {"A+": "good", "A": "good", "B": "brand", "C": "neutral", "skip": "neutral"}
_STATUS_TONE = {"HOLD": "brand", "SELL HALF": "spice", "SELL INTO STRENGTH": "spice", "SELL": "danger",
                "STOPPED": "danger", "EXPIRED": "neutral", "NOT FILLED": "neutral", "UNCERTAIN": "spice"}


def _chip(text: str, tone: str = "brand", code: bool = True) -> str:
    bg, fg, border = _CHIP_TONES.get(tone, _CHIP_TONES["neutral"])
    transform = "" if code else "text-transform:lowercase;"
    return (f'<span style="display:inline-block;font:600 10.5px/1 {_F_MONO};letter-spacing:.2px;{transform}'
            f'padding:4px 8px;border-radius:6px;background:{bg};color:{fg};border:{border};white-space:nowrap">'
            f"{esc(text)}</span>")


def _status_word(status: Any) -> str:
    word = _text(status)
    if word is None:
        return _DASH
    return PLAN_STATUS_WORDS.get(word, word.replace("_", " ").upper())


def _bursts_by_ticker(data: dict) -> dict[str, dict]:
    return {b.get("ticker"): b for b in data.get("bursts", []) if isinstance(b, dict) and b.get("ticker")}


def _trade_block(burst: dict, breadth: dict | None) -> str:
    plan = burst.get("plan") if isinstance(burst.get("plan"), dict) else {}
    grade, score = _text(burst.get("grade")), _num(burst.get("score"))
    chip = _chip(f"{grade or _DASH} · {score:.1f}" if score is not None else (grade or _DASH),
                 _GRADE_TONE.get(grade or "", "neutral"))
    lo, hi = _price(plan.get("entry_low")), _price(plan.get("entry_high"))
    zone = f"{lo}–{hi}" if lo and hi else _show(lo or hi)
    facts = [f"Buy zone {esc(zone)}", f"Stop {esc(_show(_price(plan.get('stop'))))}",
             f"Shares {esc(_show(str(_int(plan.get('shares'))) if _int(plan.get('shares')) is not None else None))}"]
    position = _money(plan.get("position_usd"))
    if position:
        facts.append(f"Position {esc(position)}")
    order = _text(plan.get("order_line"))
    reason = _text(_get(burst, "claude", "reason"))
    parts = [f'<div style="{_S_CARD}">',
             f'<div><span style="{_S_TICKER}">{esc(burst.get("ticker"))}</span> &nbsp;{chip}</div>',
             f'<p style="margin:8px 0 0">{" · ".join(facts)}</p>']
    if order:
        parts.append(f'<pre style="{_S_PRE}">{esc(order)}</pre>')
    sizing_note = _text(plan.get("sizing_note"))
    if sizing_note:
        parts.append(f'<p style="{_S_MUTED}">{esc(sizing_note)}.</p>')
    terms = [t for t in (plan.get("order_terms") or []) if _text(t)] if isinstance(plan.get("order_terms"), list) else []
    if terms:
        parts.append(f'<p style="{_S_MUTED}">{esc(terms[0])}</p>')
    parts.append(f'<p style="{_S_MUTED}">{esc(burst.get("summary") or summary(burst))}</p>')
    if reason:
        parts.append(f'<p style="{_S_MUTED}">Why: {esc(reason)}</p>')
    parts.append("</div>")
    return "".join(parts)


def _open_plan_row(plan: dict, hold_days: Any = None) -> str:
    word = _status_word(plan.get("status"))
    day, of = _int(plan.get("day")), _int(_first(plan.get("of"), plan.get("horizon_sessions"), hold_days))
    when = []
    if day is not None:
        when.append(f"day {day}" + (f" of {of}" if of is not None else ""))
    picked = _text(plan.get("picked"))
    if picked:
        when.append(f"picked {picked}")
    instruction = _text(plan.get("instruction")) or "No instruction was recorded for this plan."
    return (f'<div style="{_S_CARD}"><div><span style="{_S_TICKER}">{esc(plan.get("ticker"))}</span> &nbsp;'
            f'{_chip(word, _STATUS_TONE.get(word, "neutral"))}'
            + (f' <span style="font-size:13px;color:#5D6671">{esc(" · ".join(when))}</span>' if when else "")
            + f'</div><p style="margin:8px 0 0">{esc(instruction)}</p></div>')


def _alert_row(row: dict) -> str:
    plan = row.get("plan") if isinstance(row.get("plan"), dict) else {}
    trigger = _price(_first(row.get("trigger"), plan.get("trigger")))
    stop = _price(_first(row.get("stop"), plan.get("stop")))
    shares = _int(_first(row.get("shares"), plan.get("shares")))
    order = _text(_first(row.get("order_line"), plan.get("order_line")))
    facts = [f"Trigger {esc(_show(trigger))}", f"Stop {esc(_show(stop))}",
             f"Shares {esc(_show(str(shares) if shares is not None else None))}"]
    setups = row.get("setups") if isinstance(row.get("setups"), list) else []
    chips = " ".join(_chip(str(s), "neutral") for s in setups if _text(str(s)))
    if order:
        ticket = f'<pre style="{_S_PRE}">{esc(order)}</pre>'
    else:
        # an alert with no ticket says so, in the words the page uses
        why = ("breadth sizes new positions at zero tonight; keep the alert, place nothing"
               if plan.get("action") == "no_new_longs" else _text(plan.get("reason")) or "no order tonight")
        ticket = f'<p style="{_S_MUTED}">No order · {esc(why)}</p>'
    return (f'<div style="{_S_CARD}"><div><span style="{_S_TICKER}">{esc(row.get("ticker"))}</span>'
            + (f" &nbsp;{chips}" if chips else "")
            + f'</div><p style="margin:8px 0 0">{" · ".join(facts)}</p>' + ticket + "</div>")


def _no_ticket_lines(data: dict) -> list[str]:
    """One line per A-quality plan without a ticket, with the budget's
    reason: withheld by the stop rule, past the slots or the equity, or
    sized to no whole share."""
    beyond = [t for t in data.get("beyond_cap", []) if _text(str(t))] if isinstance(data.get("beyond_cap"), list) else []
    if not beyond:
        return []
    reasons = {c.get("ticker"): _text(c.get("reason")) for c in (_get(data, "cash_budget", "cut") or [])
               if isinstance(c, dict)}
    return [f'<p style="{_S_MUTED}">No ticket for {esc(t)}: {esc(reasons.get(t) or "see the page")}.</p>' for t in beyond]


def _problems_block(problems: Any) -> str:
    """The fixed sentence for each problem kind and nothing else: the message
    the run recorded stays in the run log, on the page and in the mail alike."""
    sentences = problem_sentences(problems)
    if not sentences:
        return ""
    items = "".join(f"<li>{esc(s)}</li>" for s in sentences)
    return (f'<div style="{_S_WARN}"><p style="{_S_WARN_LABEL}"><span style="color:#BE2132">// </span>'
            f'what went wrong tonight</p><ul style="margin:0;padding-left:18px">{items}</ul></div>')


def _breadth_line(breadth: Any) -> str:
    verdict = _get(breadth, "regime", "verdict")
    if verdict not in REGIMES:
        return f'<p style="margin:0 0 12px">{esc(breadth_sentence(breadth))}</p>'
    tone = {"green": "good", "yellow": "spice", "red": "danger"}[verdict]
    facts = []
    up4, down4 = _int(_get(breadth, "up4")), _int(_get(breadth, "down4"))
    if up4 is not None:
        facts.append(f"{up4:,} up 4%")
    if down4 is not None:
        facts.append(f"{down4:,} down 4%")
    for key, label in (("ratio_5d", "5-day ratio"), ("ratio_10d", "10-day ratio")):
        value = _num(_get(breadth, key))
        if value is not None:
            facts.append(f"{label} {_ratio(value)}")
    return (f'<p style="margin:0 0 12px">{_chip(verdict, tone, code=False)} '
            f'<span>{esc(" · ".join(facts))}</span></p>')


def digest_subject(data: dict) -> str:
    """The cover's h1 and the session it is about."""
    return f"{_get(data, 'cover', 'h1') or H1_FAILED.format(expected='the next session')} · " \
           f"{_text(_get(data, 'run', 'session')) or 'no session'}"


def digest_html(data: dict, problems: list[dict] | None = None) -> str:
    """The digest: verdict, breadth, one block per trade, the open plans, the
    alerts, the problems and the link. Inline styles only; every dynamic
    string through esc(). `problems` adds to the record's own, for the notice
    that goes out after a delivery failure."""
    run = data.get("run") if isinstance(data.get("run"), dict) else {}
    cover_block = data.get("cover") if isinstance(data.get("cover"), dict) else {}
    session = _text(run.get("session")) or "no session"
    by_ticker = _bursts_by_ticker(data)
    trades = [by_ticker[t] for t in data.get("trades", []) if t in by_ticker] if isinstance(data.get("trades"), list) else []
    open_plans = [p for p in data.get("open_plans", []) if isinstance(p, dict)] if isinstance(data.get("open_plans"), list) else []
    alerts = [r for r in (_get(data, "watchlist", "top") or []) if isinstance(r, dict)]
    recorded = list(run.get("problems") or []) if isinstance(run.get("problems"), list) else []
    for extra in problems or []:
        if isinstance(extra, dict) and extra not in recorded:
            recorded.append(extra)

    out = [f'<div style="{_S_PAGE}">',
           f'<p style="{_S_EYEBROW}"><span style="{_S_EYEBROW_SLASH}">// </span>spicystock · {esc(session)} · '
           f'{esc(run.get("type") or "evening")} run</p>',
           f'<div style="{_S_INK}"><p style="{_S_INK_LABEL}">// tonight\'s verdict</p>'
           f'<h1 style="{_S_H1}">{esc(cover_block.get("h1") or H1_KEEP_CASH)}</h1>'
           f'<p style="margin:0">{esc(cover_block.get("dek") or "")}</p></div>',
           _breadth_line(data.get("breadth"))]
    out.append(f'<h2 style="{_S_H2}">Tomorrow\'s orders</h2>')
    if trades:
        out.extend(_trade_block(b, data.get("breadth")) for b in trades)
    else:
        out.append(f'<p style="margin:0 0 12px">No orders for tomorrow.</p>')
    out.extend(_no_ticket_lines(data))
    if trades:
        sentence = _text(_get(data, "cash_budget", "sentence"))
        if sentence is None:
            committed, equity = _money(_get(data, "cash_budget", "committed_usd")), _money(_get(data, "account", "equity"))
            used, slots = _int(_get(data, "cash_budget", "slots_used")), _int(_get(data, "cash_budget", "slots_max"))
            budget = []
            if committed and equity:
                budget.append(f"Model allocation: tomorrow's tickets would commit {committed} of the configured {equity}")
            if used is not None and slots is not None:
                budget.append(f"{used} of {slots} slots")
            sentence = " · ".join(budget) if budget else None
        if sentence:
            out.append(f'<p style="{_S_MUTED}">{esc(sentence)}. Not a balance or buying power.</p>')
    out.append(f'<h2 style="{_S_H2}">Open model plans</h2>')
    hold_days = _get(data, "rules", "plan", "final_exit_day")
    if open_plans:
        out.append(f'<p style="{_S_MUTED}">Walked from daily bars by the published ticket\'s own rules; SpicyStock '
                   f'does not know what you hold. If you took a plan, this is what its rules say next.</p>')
    out.extend(_open_plan_row(p, hold_days) for p in open_plans)
    if not open_plans:
        out.append('<p style="margin:0 0 12px">No open model plans. SpicyStock does not know what you hold; '
                   'if you hold nothing from this screener, nothing to do.</p>')
    out.append(f'<h2 style="{_S_H2}">Alerts — set these before the open</h2>')
    out.extend(_alert_row(r) for r in alerts)
    if not alerts:
        out.append('<p style="margin:0 0 12px">No anticipation names tonight.</p>')
    out.append(_problems_block(recorded))
    out.append(f'<p style="margin:16px 0 0">Full plan, charts and the order sheet: '
               f'<a href="{esc(PAGE_URL)}" style="{_S_LINK}">{esc(PAGE_URL)}</a></p>')
    foot = [f"model {model}" if (model := _text(run.get("model"))) else None,
            f"feed {feed}" if (feed := _text(run.get("feed"))) else None,
            f"rules {version}" if (version := _text(_get(data, "app", "rules_version"))) else None,
            f"generated {generated}" if (generated := _text(data.get("generated"))) else None]
    out.append(f'<p style="{_S_FOOT}">{esc(" · ".join(f for f in foot if f))}</p></div>')
    return "".join(out)


def failure_html(run_type: str, problems: list[dict], expected: str) -> str:
    """The notice for a run that died before it published: the verdict it
    cannot give, the fixed problem sentences, and the link."""
    return "".join([
        f'<div style="{_S_PAGE}">',
        f'<p style="{_S_EYEBROW}"><span style="{_S_EYEBROW_SLASH}">// </span>spicystock · {esc(run_type)} run</p>',
        f'<div style="{_S_INK}"><p style="{_S_INK_LABEL}">// tonight\'s verdict</p>'
        f'<h1 style="{_S_H1}">{esc(H1_FAILED.format(expected=expected))}</h1>'
        f'<p style="margin:0">The {esc(run_type)} run stopped before it published a plan. The open model plans '
        f'are unchanged: if you hold one, keep the stops from the last plan you acted on.</p></div>',
        _problems_block(problems) or f'<p style="margin:0 0 12px">No problem was recorded before it stopped.</p>',
        f'<p style="margin:16px 0 0">The last published plan: '
        f'<a href="{esc(PAGE_URL)}" style="{_S_LINK}">{esc(PAGE_URL)}</a></p></div>',
    ])


# --- the email: transport (ported) -------------------------------------------------------

def _required(name: str) -> str:
    """An env var that must be present AND non-empty."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise KeyError(
            f"{name} is unset or empty, so this run cannot deliver its email. "
            "preflight checks this before the scan spends anything; reaching it "
            "here means deliver() was called directly."
        )
    return value


def sender_address() -> str:
    """Who the mail is from: RESEND_FROM, or Resend's sandbox sender.

    EMPTY COUNTS AS ABSENT. evening.yml always sets RESEND_FROM from a secret
    and GitHub expands an unset secret to '', so the variable is present and
    empty; os.environ.get's default fires only on a MISSING key, and the
    documented fallback was unreachable in the one place it was written for.
    """
    return os.environ.get("RESEND_FROM", "").strip() or DEFAULT_SENDER


def deliver(subject: str, body: str, attachments: list[dict] | None = None) -> dict:
    """Hand one message to Resend and return its reply. The ONLY send path.

    Resend's test-mode check is an exact string match, and the first live
    account's EMAIL_TO differed from the address Resend named by
    capitalisation alone -- three dispatches of one identical refusal. On
    that refusal, and only when every recipient IS the named address up to
    case, the message is sent once more as Resend spells it, out loud. A
    second refusal is raised as any other; every other refusal is diagnosed
    (domains and counts, never addresses) and raised.
    """
    to = [addr.strip() for addr in _required("EMAIL_TO").split(",")]
    resend.api_key = _required("RESEND_API_KEY")
    payload = {
        "from": sender_address(),
        "to": to,
        "subject": subject,
        "html": body,
        "attachments": list(attachments or []),
    }
    try:
        response = resend.Emails.send(payload)
    except Exception as exc:
        respelt = _recipients_as_resend_spells_them(to, exc)
        if respelt is None:
            _explain_test_mode_refusal(to, exc)
            raise
        log.warning("Resend's test mode named the account's address in different "
                    "capitalisation from EMAIL_TO; sending to it as Resend spells it, "
                    "since that check is exact. Re-save EMAIL_TO in that spelling.")
        payload["to"] = respelt
        try:
            response = resend.Emails.send(payload)
        except Exception as again:
            _explain_test_mode_refusal(respelt, again)
            raise
    # The count, not the addresses: EMAIL_TO is a repository secret and
    # Actions masks only exact occurrences of it, which split() breaks.
    log.info("Email sent via Resend to %d recipient(s), id=%s", len(to), response.get("id"))
    return response


_OWN_ADDRESS_IN_REFUSAL = re.compile(r"own email address \(([^)\s]+)\)")


def _recipients_as_resend_spells_them(to: list[str], exc: Exception) -> list[str] | None:
    """The recipient list in Resend's own spelling, if that is the only
    difference; None for any other refusal, a second recipient, an address
    that differs by more than case, or one that already matches."""
    named = _OWN_ADDRESS_IN_REFUSAL.search(str(exc))
    if not named:
        return None
    own = named.group(1)
    if not to or any(addr.lower() != own.lower() for addr in to):
        return None
    if all(addr == own for addr in to):
        return None
    return [own for _ in to]


def _explain_test_mode_refusal(to: list[str], exc: Exception) -> None:
    """Say how EMAIL_TO compares to the one address Resend's test mode
    allows -- the count, each recipient's domain, and whether it IS the
    named address -- without printing a recipient. Any other refusal is
    left to speak for itself."""
    named = _OWN_ADDRESS_IN_REFUSAL.search(str(exc))
    if not named:
        return
    own = named.group(1)
    parts = []
    for addr in to:
        domain = addr.rsplit("@", 1)[1].lower() if "@" in addr else "no domain"
        if addr == own:
            parts.append(f"the address Resend named, at {domain}")
        elif addr.lower() == own.lower():
            parts.append(f"the address Resend named in different capitalisation, at {domain}")
        else:
            parts.append(f"a different address, at {domain}")
    log.error(
        "Resend's test mode refused the recipients. EMAIL_TO holds %d recipient(s): %s. "
        "Until a domain is verified at resend.com/domains, EMAIL_TO has to be exactly the "
        "one address Resend named, alone -- and it has to be the REPOSITORY secret, since "
        "the workflow reads no environment.",
        len(to), "; ".join(parts),
    )


# --- the email: what goes out --------------------------------------------------------------

def send_digest(data: dict) -> dict:
    """Mail the night's digest; a closed market gets its own subject."""
    if _get(data, "run", "session_state") == "closed":
        return closed_market_digest(data)
    return deliver(digest_subject(data), digest_html(data))


def closed_market_digest(data: dict) -> dict:
    """The digest under the closed-market subject: the plans stand as they were."""
    return deliver(CLOSED_SUBJECT, digest_html(data))


def send_failure_notice(run_type: str, problems: list[dict], data: dict | None = None, *,
                        expected_session: str | None = None) -> dict:
    """Mail the fact that there is no plan -- or, when the record published
    and only the delivery failed, mail the digest itself again with the
    problems it now carries. A run that dies mid-scan sends nothing, and
    nothing looks exactly like a weekend."""
    if data is not None:
        return deliver(digest_subject(data), digest_html(data, problems=problems))
    expected = _text(expected_session) or "the next session"
    return deliver(FAILED_SUBJECT.format(expected=expected), failure_html(run_type, problems, expected))
