"""src.brief -- the analyst's daily brief: one publication, compact enough for an outside reader.

SpicyStock is a view and a daily output. An outside analyst (a person, or a
bot the owner runs) takes the candidates from it, does its own research and
recommends; the owner decides and places every order. The canonical record is
megabytes long (8 to 15 MB in November 2026), too large for that reader, so
each evening two companions are derived from it:

* ``brief.json`` -- machine readable, at most ``MAX_JSON_BYTES``;
* ``brief.md``   -- the same facts as Markdown, rendered from brief.json's own
  parsed content and naming its SHA-256, at most ``MAX_MD_BYTES``.

The pair is a function of three things and nothing else: the canonical
``data.json`` bytes, the ``picks.json`` bytes, and one optional block the
evening run carries in (``model_record``, computed from that run's fetched
bars). No other file, no clock and no network: ``derive()`` twice gives the
same bytes, and ``validate()`` holds a committed pair to that. Freshness is
the reader's own computation with its own clock (``src/freshness.py``); the
file carries the instants and the rule, never a "built at" or an "is newest".

What the brief adds to the record's own words is labelled where it stands:
research levels for a candidate the record published no plan for (the record's
plan rule over the row's own bar, never a ticket), each regime rule with its
measured value, the event registry read against every listed row, and what
none of it establishes (``LIMITS``).

Module level imports are the standard library and two standard-library-only
siblings, so the publication gate (``tools/publish_dashboard.py``, which runs
without the repository's dependencies) can import this file and hold the
binding. ``derive()`` imports ``src.plan``, ``src.event_risk`` and
``src.admission`` lazily.

    python -m src.brief --docs docs            # derive and install the pair
    python -m src.brief --docs docs --check    # hold the committed pair to its derivation
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date
from urllib.parse import quote

from src import freshness, reader

VERSION = 1
SCHEMA = "spicystock-brief-v1"
JSON_FILE = "brief.json"
MD_FILE = "brief.md"
DATA_FILE = "data.json"
PICKS_FILE = "picks.json"
MAX_JSON_BYTES = 250_000
MAX_MD_BYTES = 80_000
MAX_SOURCE_BYTES = reader.MAX_PUBLICATION_BYTES
MAX_PICKS_BYTES = 4 * 1024 * 1024
#: ``report.PAGE_URL``; tests/test_brief.py holds the two equal (report imports the mail client).
SITE_URL = "https://spicychicken59.github.io/SpicyStock/"
REPO_URL = "https://github.com/spicyChicken59/SpicyStock"
#: The same bytes without the Pages build.
RAW_URL = "https://raw.githubusercontent.com/spicyChicken59/SpicyStock/main/docs/"
HEX = re.compile(r"[a-f0-9]{64}\Z")

# Row bounds. Each list keeps the largest multiple of its step (or every row) that keeps the file within its
# byte bound, found by bisection over a size that only grows with the rows; the chosen count, the rows left out
# and the rule are written into the file's own `bounds` block.
DETAIL_STEP = 4                # brief.json: candidates in detail beyond the tickets and reviewed names
COMPACT_STEP = 10              # brief.json: compact rows, once no further candidate can be detailed
MD_DETAIL_STEP = 2             # brief.md: the same, for the Markdown
MD_COMPACT_STEP = 5
MD_TAIL_STEP = 50              # brief.md: research-tail tickers named
TAIL_MAX = 4000                # research-tail tickers a file names, in rank order
OPEN_PLANS_MAX = 24
LEDGER_MAX = 40
STALE_NAMES_MAX = 25
HISTORY_DAYS = 10
ALSO_QUIET_MAX = 10
EVENT_SOURCES_MAX = 4          # dated sources printed beside one registry match
TEXT_MAX = 900                 # one copied sentence or reader paragraph
ERROR_MAX = 200
MODEL_RECORD_MAX_BYTES = 60_000    # the carried model-record block, in its canonical encoding
MODEL_MD_ROWS = 30             # brief.md: rows printed of one model-record table
MODEL_MD_COLUMNS = 12
MODEL_MD_CELL = 80
MD_SHORT_TEXT = 240            # brief.md: one reader sentence of a reviewed name in its short form

#: Label bounds of this project's own (P): neither is a rule, and nothing is gated on them.
#: A published ratio this close to a regime line sits inside the largest later
#: re-reading of a published ratio seen through 17 November 2026.
NEAR_LINE_BAND = 0.06
#: A burst whose volume is this close to the previous session's can flip its
#: volume check on the provider's later corrections.
NEAR_VOLUME_BAND = 0.05
RATIO_UNROUNDED_DECIMALS = 4
#: SpicyStock reads prices from one provider (``src/market_data.py``).
PRICE_SOURCES = 1

ORDER_ACTIONS = ("buy_at_open", "place_buy_stop")          # plan.ORDER_ACTIONS
#: record.SCORECARD_BUCKETS; tests/test_brief.py holds the two equal.
SCORECARD_BUCKETS = ("settled", "open", "pending", "uncertain", "not_filled", "unmeasured", "unreadable", "unscored")
STATUS_MARK = {"PASS": "", "PARTIAL": "~", "FAIL": "x"}
TICKET = "TICKET"
RESEARCH_ONLY = "RESEARCH ONLY: no SpicyStock ticket"
RESEARCH_SHORT = "RESEARCH ONLY"
RESEARCH_LEVELS_LABEL = ("research levels from the record's plan rule over this row's own bar, at the archived model "
                         "account; SpicyStock offers no order at these levels")
ORDER_KIND = "buy_stop_limit_oto"
#: What a buy stop at the last close means at a broker. Fixed text.
BUY_STOP_NOTE = ("a broker takes a buy stop only above the current price, so the order can be entered as written only "
                 "while the stock trades under its last close")
#: The words of ``morning.price_state()`` (``morning.PRICE_STATES`` without its "unknown"), in price order.
PRICE_STATES = ("below_stop", "below_entry_floor", "below_trigger", "within_published_band", "above_limit",
                "above_day2_extension")

#: The Markdown's sections, numbered and stable: an analyst prompt refers to them by name.
SECTIONS = ("Identity and binding", "Service state", "Market regime", "Model account", "Published model tickets",
            "Admitted trade-band candidates", "Research tail", "Setting up", "Open model plans", "Model record",
            "Event registry and coverage", "Rules", "Bounds", "What this file does not establish")

#: The first thing either file says. Fixed text.
READ_FIRST = (
    "This is SpicyStock's daily brief: one evening publication's model output, derived from that publication's "
    "record and its pick ledger and from nothing else, for an outside analyst to read in place of the full record.",
    "Check that it is current before using it: `status` must be `derived`, and the freshness rule in section 2 "
    "(`service.freshness_rule`) is applied with your own clock.",
    "Only the rows in section 5 (`tickets`) are published model tickets. Every other row is research only: its "
    "levels are reference arithmetic and SpicyStock offers no order for it.",
    "SpicyStock places, cancels and observes no order and reads no brokerage account. The owner decides and places "
    "every order.",
)

#: What the file does not establish. Fixed, timeless text; held by a test to appear in both files.
LIMITS = (
    "This is a model's output from one provider's daily bars. This brief places and observes no order, and "
    "SpicyStock reads no brokerage account, balance, position or fill.",
    "Every price is the measured session's bar as published; nothing here is a live quote. Check the current "
    "price, spread and halt state before acting.",
    "A grade is a checklist score over daily bars and, where a review is recorded, one chart reader's judgement. "
    "It is not a forecast.",
    "The model record establishes no edge. Its counts are model plans walked on bars, not trades; read "
    "`scorecard.readable` and its counts before any rate, and a sum of R is not a sum of dollars.",
    "A model fill at the open assumes a buy stop-limit order already resting at the broker before the open. "
    "Whether the broker accepts that order for a burst ticket, whose buy stop is the last close, is unconfirmed.",
    "A stop reached inside a session is booked at exactly the stop price. A real stop order fills at the next "
    "available price, which can be worse, and a gap through the stop loses more.",
    "Research levels are what the record's own plan rule gives for the recorded bar at the archived model "
    "account. The record published no plan for those names; they are not tickets, and no chart review accepted "
    "them unless the row's reader state says so.",
    "A model ticket is sized for the archived model account (`account`), not for the reader's account. Shares, "
    "cost and risk are planned price-to-stop arithmetic at the limit, not a maximum loss.",
    "The market regime is SpicyStock's gate for its own model tickets: an input to weigh, not an instruction. The "
    "scaling of its count thresholds, the admission rule, the checklist weights and the chart reader are this "
    "project's own rules (knowledge/method.md says whose number each is), and the record does not establish that "
    "the gate improves outcomes.",
    "SpicyStock reads no company news. Earnings and SEC 8-K items are read for published tickets only, from SEC "
    "filings: a projected date is an estimate, never an announced date, unknown is never clear, and filings are "
    "not news coverage.",
    "The event registry is a hand-kept list of known cash acquisitions. A stock that is not in it has not been "
    "cleared: issuer news, offerings, guidance and other corporate events are not checked.",
    "One provider's bars as of the run's fetch; a session's volume can be revised afterwards. The universe is the "
    "selection named in `service.universe`, not point-in-time membership, and a stock named stale had no bar for "
    "the session: its inputs are unknown, not a measured non-match.",
    "Whether the broker accepts the printed order form (a day buy stop-limit with a one-triggers-the-other sell "
    "stop) is unconfirmed; see knowledge/broker-fidelity.md.",
    "Rows are bounded. `bounds` states every list that was cut, how many rows were left out and the rule that "
    "chose the kept ones; the canonical record carries every row.",
    "This brief is bound to one publication by the SHA-256 and byte length in `identity.canonical`. Whether a "
    "newer publication exists is not in this file: apply `service.freshness_rule` with your own clock.",
)

#: What SpicyStock does not check about a company, whatever the night. Fixed text.
NOT_CHECKED = (
    "company news and press releases", "announced earnings dates", "offerings and shelf takedowns",
    "FDA and trial dates", "halts outside the morning check", "delisting notices beyond 8-K item 3.01 on tickets",
    "index changes", "lockup expiries", "ex-dividend dates",
)
EVENT_STATUS_WORDS = {
    "known_event": "in the registry and blocked for a SpicyStock ticket; its manual review is current",
    "review_required": "in the registry and blocked for a SpicyStock ticket; its manual review is overdue",
    "not_in_registry": "not in the registry: NOT a clearance, nothing was checked",
}

#: Why the model-record block is absent, one fixed reason each.
NOT_COMPUTED = "computed only inside an evening run, from that run's fetched bars"
NOT_COMPUTED_FAILED = "the evening run could not compute it"
NOT_CARRIED_UNREADABLE = "the computed block was not a readable JSON object and was not carried"
NOT_CARRIED_NAMES = "the computed block used a property name the secret scan reads as a credential and was not carried"
NOT_CARRIED_SIZE = f"the computed block was over its {MODEL_RECORD_MAX_BYTES}-byte bound and was not carried"
NOT_CARRIED_DISAGREES = "the computed block disagreed with the record's own scorecard and was not carried"
NOT_CARRIED_ROOM = "the computed block left no room for the brief within its byte bounds and was not carried"
NOT_COMPUTED_REASONS = (NOT_COMPUTED, NOT_COMPUTED_FAILED, NOT_CARRIED_UNREADABLE, NOT_CARRIED_NAMES, NOT_CARRIED_ROOM,
                        NOT_CARRIED_SIZE, NOT_CARRIED_DISAGREES)
MODEL_TABLES = ("plans", "setups", "eras", "stops")
#: the statuses of a block the evening run computed (``src/model_record.py``): its figures are the scorecard's, or
#: the block itself says they do not reconcile with it and names why
MODEL_COMPUTED, MODEL_UNRECONCILED, MODEL_NOT_COMPUTED = "computed", "unreconciled", "not_computed"
MODEL_CARRIED = (MODEL_COMPUTED, MODEL_UNRECONCILED)
#: brief.md: the columns one model-record table shows first when it has them; the rest follow in the block's order
MODEL_MD_FIRST = ("picked", "ticker", "kind", "shares", "bucket", "r", "model_usd", "issued_equity", "account_basis",
                  "issue_no", "issues", "withdrawn", "label", "tickets", "settled", "sum_r")
#: A property name carrying one of these is read by the secret scan's generic rule as a credential's name.
SCANNER_WORDS = ("key", "token", "secret", "auth", "api", "access", "credential", "creds", "passw")


class Refusal(ValueError):
    """A derivation refused for a reason the file may print: fixed words, never an exception's own text."""


class DoesNotFit(Refusal):
    """A file past its byte bound at its smallest row bounds."""


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _encode(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _decode(raw: bytes, maximum: int):
    _require(isinstance(raw, bytes) and 0 < len(raw) <= maximum, "brief source bytes exceed bound")

    def invalid(_):
        raise ValueError("nonfinite JSON")
    return json.loads(raw, parse_constant=invalid)


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _text(value, maximum=TEXT_MAX):
    """A copied sentence, bounded; the cut is marked, never silent."""
    if not isinstance(value, str):
        return None
    return value if len(value) <= maximum else value[:maximum - 1].rstrip() + "\u2026"


def _pick(source: dict, names) -> dict:
    return {name: source.get(name) for name in names if name in source}


def _link(stage: str, ticker) -> str:
    return f"{SITE_URL}#/explore/{stage}/{quote(str(ticker), safe='')}"


def _days_between(later, earlier):
    try:
        return (date.fromisoformat(str(later)[:10]) - date.fromisoformat(str(earlier)[:10])).days
    except ValueError:
        return None


def rules_digest(rules) -> str:
    """``report.rules_version()``: a 12-hex prefix of the SHA-256 of the rules
    block, serialised canonically. Kept here because ``src.report`` imports the
    mail client; tests/test_brief.py holds the two functions equal."""
    blob = json.dumps(rules, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def scanner_names(value, found=None) -> list:
    """Every property name in ``value`` the secret scan's generic rule would read as a credential's name."""
    found = [] if found is None else found
    if isinstance(value, dict):
        for name, inner in value.items():
            if any(word in str(name).lower() for word in SCANNER_WORDS) and str(name) not in found:
                found.append(str(name))
            scanner_names(inner, found)
    elif isinstance(value, list):
        for inner in value:
            scanner_names(inner, found)
    return found


# ----------------------------------------------------------------- blocks ---
def identity(data: dict, canonical_raw: bytes, picks_raw: bytes | None) -> dict:
    run, timing = _dict(data.get("run")), _dict(_dict(data.get("run")).get("timing"))
    run_id = run.get("run_id")
    return {
        "measured_session": run.get("session"),
        "session_state": run.get("session_state"),
        "expected_session": run.get("expected_session"),
        "applicable_session": timing.get("applicable_session"),
        "entry_window": _pick(timing, ("timezone", "opens_at", "cutoff_at", "prepare_by", "closes_at", "shortened",
                                       "window", "closed_session")) or None,
        "published_at": run.get("published_at"),
        "rules_version": _dict(data.get("app")).get("rules_version"),
        "run_id": run_id, "run_type": run.get("type"), "dry_run": run.get("dry_run"),
        "fixture": data.get("fixture") or None,
        "canonical": {"path": DATA_FILE, "sha256": _hash(canonical_raw), "bytes": len(canonical_raw)},
        "picks": ({"path": PICKS_FILE, "sha256": _hash(picks_raw), "bytes": len(picks_raw)}
                  if picks_raw is not None else None),
        "urls": {"page": SITE_URL, "record": SITE_URL + DATA_FILE, "picks": SITE_URL + PICKS_FILE,
                 "brief_json": SITE_URL + JSON_FILE, "brief_md": SITE_URL + MD_FILE,
                 "brief_md_raw": RAW_URL + MD_FILE, "brief_json_raw": RAW_URL + JSON_FILE,
                 "morning_receipt": SITE_URL + "morning.json",
                 "run_log": f"{REPO_URL}/actions/runs/{run_id}" if run_id else None,
                 "method": f"{REPO_URL}/blob/main/knowledge/method.md",
                 "rulebook": f"{REPO_URL}/blob/main/knowledge/strategy.md",
                 "broker_note": f"{REPO_URL}/blob/main/knowledge/broker-fidelity.md"},
    }


def input_unknowns(data: dict) -> list:
    """What the record's inputs do not establish. Fixed sentences; the one figure is the record's own fetch time."""
    fetched = _dict(_dict(data.get("run")).get("universe")).get("fetched_at")
    return [
        "Why a stale stock had no session bar is not established; its session inputs are unknown, not a measured "
        "non-match, until a later run reads the session again.",
        "These bars are the provider's as of the run's fetch"
        + (f" at {fetched}" if isinstance(fetched, str) else "")
        + "; a session's volume can be revised afterwards, and this file does not measure by how much.",
        "One price source: nothing cross-checks a close, a volume or a split. Bars are adjusted as "
        "`service.inputs.basis.adjustment` says and for nothing else.",
        "The universe is the selection named in `service.universe`, as fetched; it does not establish which stocks "
        "were listed during the session, and the record does not name the stocks that entered or left since the "
        "previous publication.",
    ]


def service(data: dict, canonical_sha: str) -> dict:
    run = _dict(data.get("run"))
    cov, tol = _dict(run.get("coverage")), _dict(run.get("input_tolerance"))
    acc = _dict(cov.get("acceptance"))
    names = _list(tol.get("names"))
    follow = _dict(run.get("stale_followup"))
    reads, usage, sel = _dict(run.get("reads")), _dict(run.get("reader_usage")), _dict(run.get("review_selection"))
    earn, uni = _dict(run.get("earnings")), _dict(run.get("universe"))
    spent = _dict(usage.get("tokens"))
    previous = tol.get("previous")
    morning = freshness.morning_window(data)
    return {
        "status": run.get("status"),
        "problems": [{"kind": p.get("kind"), "message": _text(p.get("message"))} if isinstance(p, dict)
                     else {"kind": str(p)} for p in _list(run.get("problems"))],
        "email": run.get("email"), "elapsed_seconds": run.get("elapsed_seconds"),
        "fetch_seconds": run.get("fetch_seconds"),
        "delivery": _pick(_dict(run.get("delivery")), (
            "completion_at", "published_at", "latency_minutes", "primary_slot_at", "retry_slot_at",
            "after_primary_minutes", "slot", "next_session", "next_open_at", "before_next_open", "sentence")) or None,
        "expected": freshness.expected(data),
        "freshness_rule": list(freshness.RULE),
        "freshness_states": list(freshness.STATES),
        "morning": {
            **morning,
            "receipt": {
                "url": SITE_URL + "morning.json",
                "must_carry": {"publication.data_sha256": canonical_sha},
                "rule": "A morning receipt belongs to this publication only when its `publication.data_sha256` "
                        "equals `identity.canonical.sha256`. One generated before `window_opens_at` carries no "
                        "quote from inside the entry window. The receipt is not part of this file: it lands the "
                        "next morning, if a morning check runs.",
            },
        },
        "inputs": {
            "basis": run.get("input_basis"),
            "lookback_days": _dict(_dict(data.get("rules")).get("pipeline")).get("lookback_days"),
            "fetched_at": uni.get("fetched_at"), "price_sources": PRICE_SOURCES,
            "intended_stocks": acc.get("intended_stocks"), "ready_stocks": acc.get("ready_stocks"),
            "fraction": acc.get("fraction"), "acceptance": acc.get("status"),
            "complete_evaluation": acc.get("complete_evaluation"),
            "counts": _pick(cov, ("with_bars", "no_bars", "stale", "gapped", "unreadable", "refused", "unfetched_budget",
                                  "unfetched_failure", "price_excluded", "scan_ready", "measured", "scan_errors",
                                  "quality_success", "quality_errors")),
            "matched": cov.get("matched"),
            "tolerance": ({"version": tol.get("version"), "verdict": tol.get("verdict"), "reasons": tol.get("reasons"),
                           "limit": tol.get("limit"), "sessions_max": tol.get("sessions_max"),
                           "stale_stocks": tol.get("stale_stocks"),
                           "names": names[:STALE_NAMES_MAX], "names_left_out": max(0, len(names) - STALE_NAMES_MAX),
                           "endings_not_previous_session": {
                               name: ending for name, ending in _dict(tol.get("endings")).items()
                               if ending != previous and name in names[:STALE_NAMES_MAX]} or None,
                           "first_sessions": tol.get("first_sessions"), "held": tol.get("held"),
                           "sentence": _text(tol.get("sentence"), 1400)} if tol else None),
            "seed_stale": _text(_dict(run.get("seed_stale")).get("sentence")),
            "stale_followup": ({**_pick(follow, ("status", "for_session", "stocks", "count", "outcomes",
                                                 "zero_volume", "flat", "matched")),
                                "sentence": _text(follow.get("sentence"))} if follow else None),
            "intraday": _text(_dict(run.get("intraday")).get("sentence")),
            "unknown": input_unknowns(data),
        },
        "universe": ({**_pick(uni, ("label", "size", "source", "source_kind", "fetched_at", "identity",
                                    "snapshot_relation", "point_in_time_membership", "membership_limit")),
                      "counts": uni.get("counts")} if uni else None),
        "reader": {
            "model": run.get("model"),
            "reads": _pick(reads, ("version", "requested", "done", "verdict", "causes", "refusal_limit", "refused_names",
                                   "refused_admissible", "unasked", "unavailable_reason", "sentence")) or None,
            "cost": ({"calls": usage.get("calls"), "replies": usage.get("responses"),
                      "input": usage.get("input_tokens"), "input_uncached": spent.get("uncached"),
                      "input_cache_write": spent.get("cache_write"), "input_cache_read": spent.get("cache_read"),
                      "output": spent.get("output"), "sentence": _text(usage.get("sentence"))} if usage else None),
            "selection": ({**_pick(sel, ("version", "policy", "max_reads", "research_max", "discovered", "feasible",
                                         "blockers", "research_pool", "requested", "feasible_unselected",
                                         "unused_capacity", "attempts", "by_purpose")),
                           "selected": _list(sel.get("selected"))} if sel else None),
        },
        "earnings": _pick(earn, ("version", "policy", "source", "status", "counts", "items_counts", "requests",
                                 "sentence")) or None,
        "admission": _pick(_dict(run.get("admission")), ("version", "policy", "candidates", "admitted", "by_basis",
                                                         "in_band", "sentence")) or None,
        "graded": run.get("graded"), "bursts": run.get("bursts"),
    }


THRESHOLD_SOURCES = {  # regime.thresholds name -> (breadth.rules reference name, regime.inputs measurement)
    "down4_alarm": ("down4_alarm", "down4"), "up50_month_hot": ("up50_month_hot", "up50_month"),
    "down25_quarter_oversold": ("down25_quarter_oversold", "down25_quarter"),
    "ratio_10d_red": ("red_ratio_10d", "ratio_10d"), "ratio_5d_red": ("red_ratio_5d", "ratio_5d"),
    "ratio_10d_yellow": ("yellow_ratio_10d", "ratio_10d"),
}

GATE_NOTE = ("The light is SpicyStock's gate for its own model tickets: an input to weigh, not an instruction to "
             "the reader.")
SCALING_NOTE = ("Count thresholds are the reference count times the stocks measured over the reference universe; "
                "that scaling is this project's own. Ratio thresholds are not scaled.")


def admits(data: dict) -> list:
    """The grades tonight's regime admits to a plan: reader_coverage.admitted(), read off the record."""
    funnel = _dict(data.get("funnel"))
    if isinstance(funnel.get("admitted_grades"), list):
        return list(funnel["admitted_grades"])
    rules = _dict(_dict(data.get("rules")).get("pipeline"))
    verdict = _dict(_dict(data.get("breadth")).get("regime")).get("verdict")
    return [] if verdict == "red" else list(rules.get("yellow_grades") or []) if verdict == "yellow" \
        else list(rules.get("trade_grades") or [])


def _unrounded(up, down):
    return round(up / down, RATIO_UNROUNDED_DECIMALS) if _num(up) and _num(down) and down else None


def regime_rules(data: dict) -> dict:
    """All five regime rules in the order ``breadth.regime()`` asks them, fired
    or not, re-derived from the record's own ``regime.inputs`` and
    ``regime.thresholds``. The verdict they give must be the record's: a
    record whose is not is refused, because every line below it would then
    describe a different night. A record without the inputs (one from before
    they were archived) gets no rules and the reason."""
    breadth = _dict(data.get("breadth"))
    regime, reference = _dict(breadth.get("regime")), _dict(breadth.get("rules"))
    inputs, th = _dict(regime.get("inputs")), _dict(regime.get("thresholds"))
    counts = ("down4", "up4", "up50_month")
    lines = ("down4_alarm", "ratio_10d_red", "ratio_5d_red", "ratio_10d_yellow", "up50_month_hot")
    ratios_ok = all(inputs.get(name) is None or _num(inputs.get(name)) for name in ("ratio_10d", "ratio_5d"))
    if not all(_num(inputs.get(name)) for name in counts) or not all(_num(th.get(name)) for name in lines) \
            or "ratio_10d" not in inputs or "ratio_5d" not in inputs or not ratios_ok:
        return {"rules": None, "rules_unavailable": "this record does not carry the regime's inputs and thresholds "
                                                    "(breadth.regime.inputs, breadth.regime.thresholds)"}
    down4, up4, hot = inputs["down4"], inputs["up4"], inputs["up50_month"]
    r10, r5 = inputs["ratio_10d"], inputs["ratio_5d"]
    of = th.get("reference_universe")

    def row(rule, tier, measure, measured, comparison, fired, *, scaled=False, extra=None):
        ref_name = THRESHOLD_SOURCES[rule][0]
        return {"rule": rule, "tier": tier, "measure": measure, "measured": measured, "comparison": comparison,
                "threshold_tonight": th[rule], "scaled": scaled,
                "reference": reference.get(ref_name), "reference_universe": of if scaled else None,
                **(extra or {}), "fired": bool(fired)}

    rows = [
        row("down4_alarm", "red", "down4", down4, "at or over", down4 >= th["down4_alarm"], scaled=True),
        row("ratio_10d_red", "red", "ratio_10d", r10, "under", r10 is not None and r10 < th["ratio_10d_red"]),
        row("ratio_5d_red", "red", "ratio_5d", r5, "under, with more names down 4% than up 4% today",
            r5 is not None and r5 < th["ratio_5d_red"] and down4 > up4, extra={"down4_today": down4, "up4_today": up4}),
        row("ratio_10d_yellow", "yellow", "ratio_10d", r10, "under",
            r10 is not None and r10 < th["ratio_10d_yellow"]),
        row("up50_month_hot", "yellow", "up50_month", hot, "over", hot > th["up50_month_hot"], scaled=True),
    ]
    verdict = ("red" if any(r["fired"] for r in rows if r["tier"] == "red")
               else "yellow" if any(r["fired"] for r in rows if r["tier"] == "yellow") else "green")
    if verdict != regime.get("verdict"):
        raise Refusal(f"the regime rules re-derived from the record's own inputs give {verdict}, and the record "
                      f"says {regime.get('verdict')}")
    for r in rows:
        r["decides"] = r["fired"] and r["tier"] == verdict
        r["masked"] = r["fired"] and r["tier"] != verdict
    up10, down10, up5, down5 = (inputs.get(name) for name in ("up4_10d", "down4_10d", "up4_5d", "down4_5d"))
    by_rounding = bool(_num(up10) and _num(down10) and up10 < down10 and not rows[1]["fired"])
    near = None
    if _num(r10):
        to_red = round(r10 - th["ratio_10d_red"], 2)
        to_yellow = round(r10 - th["ratio_10d_yellow"], 2)
        near = {"band": NEAR_LINE_BAND, "to_red_line": to_red, "to_yellow_line": to_yellow,
                "inside_band": min(abs(to_red), abs(to_yellow)) <= NEAR_LINE_BAND,
                "note": "the band is this project's own label bound, the largest later re-reading of a published "
                        "ratio seen through 17 November 2026; it is not a rule and gates nothing"}
    green = (
        f"GREEN needs all five rules quiet: fewer than {th['down4_alarm']:g} names down 4% today (it is {down4:g}); a "
        f"10-session ratio at or over {th['ratio_10d_yellow']:g} (it is {_ratio(r10)}: {_count(up10)} up against "
        f"{_count(down10)} down); no 5-session ratio under {th['ratio_5d_red']:g} with more names down 4% than up 4% "
        f"today (it is {_ratio(r5)}, with {down4:g} down against {up4:g} up); and no more than "
        f"{th['up50_month_hot']:g} names up 50% in a month (it is {hot:g}).")
    return {
        "rules": rows, "rules_unavailable": None,
        "rules_order": "the order breadth.regime() asks them: red rules first; a verdict is red when any red rule "
                       "fires, else yellow when any yellow rule fires, else green",
        "sums": {"up4_5d": up5, "down4_5d": down5, "up4_10d": up10, "down4_10d": down10,
                 "ratio_5d_published": r5, "ratio_10d_published": r10,
                 "ratio_5d_unrounded": _unrounded(up5, down5), "ratio_10d_unrounded": _unrounded(up10, down10),
                 "note": "the published ratios are rounded to two decimals and the rules compare the rounded number"},
        "green_needs": green,
        "flags": {"yellow_by_rounding": by_rounding,
                  "yellow_by_rounding_meaning": "more ten-session breakdowns than breakouts while the rounded "
                                                "ratio is not under the red line",
                  "near_line": near},
    }


def _ratio(value) -> str:
    return "not measured" if value is None else f"{value:g}"


def _count(value) -> str:
    return "n/a" if not _num(value) else f"{value:,}"


def market(data: dict) -> dict:
    breadth = _dict(data.get("breadth"))
    regime, rules = _dict(breadth.get("regime")), _dict(breadth.get("rules"))
    thresholds, inputs = _dict(regime.get("thresholds")), _dict(regime.get("inputs"))
    cov = _dict(_dict(data.get("run")).get("coverage"))
    acc = _dict(cov.get("acceptance"))
    rows = []
    for name, value in thresholds.items():
        if name in ("universe", "reference_universe"):
            continue
        ref, measure = THRESHOLD_SOURCES.get(name, (None, None))
        rows.append({"rule": name, "threshold_tonight": value, "reference": rules.get(ref) if ref else None,
                     "measure": measure, "measured": inputs.get(measure) if measure else None})
    return {
        "date": breadth.get("date"), "verdict": regime.get("verdict"), "size_multiplier": regime.get("size_multiplier"),
        "admits_grades": admits(data), "gate_note": GATE_NOTE,
        "reasons": _list(regime.get("reasons")),
        "reasons_note": "the record lists only the fired rules of the verdict's tier; `rules` lists all five",
        **regime_rules(data),
        "oversold_extreme": regime.get("oversold_extreme"),
        "scaling": {"universe": thresholds.get("universe"), "reference_universe": thresholds.get("reference_universe"),
                    "note": SCALING_NOTE},
        "population": {"measured": thresholds.get("universe"), "intended_stocks": acc.get("intended_stocks"),
                       "with_a_session_bar": acc.get("ready_stocks"), "stale": cov.get("stale"),
                       "under_the_session_price_floor": cov.get("price_excluded"),
                       "session_price_floor": _dict(_dict(data.get("rules")).get("universe")).get("session_min_price")},
        "thresholds": rows,
        "counts": _pick(breadth, ("up4", "down4", "up25_quarter", "down25_quarter", "up25_month", "down25_month",
                                  "up50_month", "down50_month", "up13_34d", "down13_34d", "pct_above_40ma", "universe")),
        "ratios": _pick(breadth, ("ratio_5d", "ratio_10d", "up4_5d", "down4_5d", "up4_10d", "down4_10d")),
        "history": _list(breadth.get("history"))[-HISTORY_DAYS:],
        "history_rule": f"the newest {HISTORY_DAYS} sessions of the record's own breadth history, each read again "
                        "tonight over tonight's stocks: an earlier session's counts can differ from what its own "
                        "night published",
        "size_multipliers": rules.get("size_multiplier"),
        "notes": [n.get("text") for n in _list(breadth.get("notes")) if isinstance(n, dict)],
    }


def schedule_days(data: dict, final_day: int) -> list:
    """Day 1..N of a plan published tonight: the sessions after the measured one, off the record's own calendar."""
    run = _dict(data.get("run"))
    session = run.get("session")
    sessions = [s.get("session") for s in _list(_dict(_dict(run.get("calendar")).get("schedule")).get("sessions"))
                if isinstance(s, dict)]
    later = [s for s in sessions if isinstance(s, str) and isinstance(session, str) and s > session][:final_day]
    return [{"day": i, "date": s} for i, s in enumerate(later, 1)]


def exit_rules(plan) -> list:
    """plan.EXIT_RULES once, the prices named instead of filled: a candidate row carries the prices."""
    values = {
        "entry": "the planned entry", "sell_half": "the sell-half level", "abnormal": "the abnormal-close level",
        "gap_exit": "the gap-exit level", "stop": "the stop",
        "sell_half_pct": f"{plan.SELL_HALF_PCT:g}", "abnormal_pct": f"{plan.ABNORMAL_DAY_PCT:g}",
        "gap_exit_pct": f"{plan.GAP_EXIT_PCT:g}", "trail_cents": f"{plan._cents_int(plan.TRAIL_CENTS)}",
        "trail_cents_max": f"{plan._cents_int(plan.TRAIL_CENTS_MAX)}", "entry_day": plan.ENTRY_DAY,
        "sell_half_day": plan.SELL_HALF_DAY, "no_progress_day": plan.NO_PROGRESS_DAY,
        "trail_from_day": plan.TRAIL_FROM_DAY, "final_exit_day": plan.FINAL_EXIT_DAY,
        "no_breakeven_day": plan.NO_BREAKEVEN_BEFORE_DAY,
    }
    return [{"step": rule["key"], "source": rule["source"], "when": rule["when"].format(**values),
             "rule": rule["rule"].format(**values)} for rule in plan.EXIT_RULES]


SIZE_FIELDS = ("shares", "cost", "risk", "multiplier", "capped_by")
PRICE_FIELDS = ("limit", "limit_basis", "stop", "stop_basis", "stop_pct_at_limit", "risk_per_share_at_limit",
                "planned_entry", "sell_half", "abnormal_close", "gap_exit", "target_low", "target_high")


def levels(p: dict, source: str, plan, account, regime_multiplier, yellow_multiplier=None) -> dict:
    """The prices a plan names, one field per rule, from a plan object (the
    record's or a derived one). Never an order: no order line, no order JSON
    and no action word leave this function. A plan the rule refused prints its
    refusal and no share count; a burst no limit can hold a stop under prints
    no limit and no stop either."""
    exits = {row.get("key"): row.get("price") for row in _list(p.get("exits")) if isinstance(row, dict)}
    burst = p.get("kind") == "burst"
    out = {
        "source": source,
        "trigger": p.get("entry_ref"), "limit": p.get("limit"),
        "limit_basis": p.get("limit_basis") if burst else "trigger_plus_cushion",
        "stop": p.get("stop"), "stop_basis": p.get("stop_basis"), "stop_pct_at_limit": p.get("stop_pct"),
        "risk_per_share_at_limit": p.get("risk_per_share"),
        "day2_line": p.get("day2_spent_above") if burst else None,
        "skip_if_open_below": p.get("skip_if_open_below") if burst else None,
        "selling_above": p.get("extended_above") if burst else None,
        "gap_check_above": None if burst else p.get("gap_ok_above"),
        "planned_entry": p.get("planned_entry"),
        "sell_half": exits.get("sell_half_8pct"), "abnormal_close": exits.get("abnormal_10pct"),
        "gap_exit": exits.get("gap_20pct"),
        "target_low": _dict(p.get("targets")).get("low"), "target_high": _dict(p.get("targets")).get("high"),
        "plan_rule_eligible": p.get("eligible"),
        # an eligible plan's reason is the allocation's (a slot cap, the cash budget): the row's own
        # why_no_ticket says it, and it is not a refusal by the plan rule
        "refusal": _text(p.get("reason")) if p.get("eligible") is not True else None,
        "flags": _list(p.get("flags")) or None,
        "shares": p.get("shares"), "cost": p.get("position_usd"), "risk": p.get("risk_usd"),
        "multiplier": _dict(p.get("multipliers")).get("total", p.get("size_multiplier")),
        "capped_by": p.get("capped_by") if p.get("capped_by") not in (None, "risk") else None,
        "size_note": _text(_dict(p.get("sizing")).get("note")) if p.get("shares") == 0 else None,
    }
    withheld = burst and p.get("ticket_refusal")
    if withheld:
        # burst_plan() could find no structural stop inside the stop line: its `stop` is then the synthetic
        # max_stop and its `limit` the day-2 line itself. Neither is a level anyone could trade from.
        for name in PRICE_FIELDS:
            out[name] = None
        out["withheld"] = p.get("ticket_refusal")
    if p.get("eligible") is not True:
        # a refused plan dict still carries a share count; a refusal prints none
        for name in (*SIZE_FIELDS, "size_note"):
            out[name] = None
    else:
        # the same plan at another regime's size: stated counterfactuals, shown only where tonight's size differs
        m = _dict(p.get("multipliers"))
        try:
            own = float(m.get("hazard", 1.0)) * float(m.get("stop_risk", 1.0))
            for label, factor in (("at_full_size", 1.0), ("at_yellow_size", yellow_multiplier)):
                if factor is None or factor == regime_multiplier or p.get("limit") is None or p.get("stop") is None:
                    continue
                sized = plan.size(p["limit"], p["stop"], account, own * float(factor))
                out[label] = {"shares": sized.shares, "cost": sized.position_usd, "risk": sized.risk_usd,
                              "multiplier": sized.multiplier}
        except (TypeError, ValueError):
            pass
    return {k: v for k, v in out.items()
            if v is not None or (k in ("trigger", "limit", "stop") and not withheld)}


def plan_rules_match(data: dict, plan) -> list:
    """The archived plan rules this code's plan module does not reproduce (provenance.verify()'s own comparison)."""
    rules = _dict(data.get("rules"))
    bad = []
    for name, value in plan.RULES.items():
        family, _, leaf = name.partition(".")
        if json.dumps(_dict(rules.get(family)).get(leaf), sort_keys=True) != json.dumps(value, sort_keys=True):
            bad.append(name)
    return bad


def derived_plan(row: dict, data: dict, modules, account, multiplier, mismatched) -> tuple:
    """(plan, None) for a burst row the record published no plan for, or (None, why)."""
    plan, event_risk = modules["plan"], modules["event_risk"]
    if mismatched:
        return None, "the archived plan rules differ from this code's (" + ", ".join(mismatched[:4]) + ")"
    try:
        p = plan.burst_plan(ticker=row["ticker"], close=row["close"], low=row["low"], high=row["high"],
                            open_=row["open"], prev_close=row["prev_close"], gain_pct=row.get("gain_pct") or 0.0,
                            account=account, size_multiplier=multiplier,
                            scan="dollar" if row.get("scan") == "dollar" else "4pct",
                            extension_pct=row.get("extension_pct"))
        registry = _dict(_dict(data.get("rules")).get("event_risk")).get("registry")
        if registry is not None:
            p = event_risk.apply(p, row["ticker"], data["run"]["session"], registry=registry)
        return p, None
    except (KeyError, TypeError, ValueError) as exc:      # named by its type alone, never by its text
        return None, f"the record's plan rule could not be run on this row ({type(exc).__name__})"


def event_state(p: dict | None) -> dict | None:
    block = _dict(_dict(p).get("event_risk"))
    if not block:
        return None
    out = {"status": block.get("status"), "blocked": block.get("blocked")}
    if block.get("blocked"):
        out["reason"] = _text(block.get("reason"))
        out["review_overdue"] = any(_dict(m).get("review_overdue") for m in _list(block.get("matches")))
    return out


def reader_block(row: dict) -> dict:
    claude, sel = _dict(row.get("claude")), _dict(row.get("review_selection"))
    out = {"state": row.get("reader_coverage"), "selected": sel.get("selected"), "purpose": sel.get("purpose"),
           "feasible": sel.get("feasible"), "blockers": sel.get("blockers")}
    if claude:
        out.update({"source": claude.get("source"), "grade": claude.get("grade"), "score": claude.get("score"),
                    "agree": claude.get("agree"), "chart_seen": claude.get("chart_seen"), "model": claude.get("model"),
                    "reason": _text(claude.get("reason")), "risk": _text(claude.get("key_risk")),
                    "entry_note": _text(claude.get("entry_note")),
                    "commentary_note": "the reader's sentences are its commentary, not checked measurements; its "
                                       "entry note is not the ticket",
                    "findings": len(_list(claude.get("findings"))),
                    "error": _text(claude.get("error"), ERROR_MAX)})
    return {k: v for k, v in out.items() if v is not None}


def would_pass(row: dict, trade, yellow, admission) -> dict:
    """The gates after the market gate, re-derived from the row's own recorded
    fields in the planner's order (``pipeline._make_plans``), so a RED night,
    which stops every name at the market, does not hide them: the grade the
    gate reads against the GREEN and the YELLOW band, the quality veto, the
    discovery admission, and the chart reader's recorded state. The stop rule,
    the event registry, sizing and the slot allocation follow these gates;
    the row's levels show the first three."""
    grade, state = row.get("grade"), row.get("reader_coverage")
    green = grade in trade if trade else None
    amber = grade in yellow if yellow is not None else None
    no_veto, admitted = not row.get("vetoes"), bool(admission.admitted(row))
    accepted = (state == "accepted") if isinstance(state, str) else None
    rest = no_veto and admitted and accepted is True
    return {"grade_the_gate_reads": grade, "grade_band_green": green, "grade_band_yellow": amber,
            "no_veto": no_veto, "admission": admitted,
            "reader": state if isinstance(state, str) else "not recorded", "reader_accepted": accepted,
            "every_later_gate_green": bool(green) and rest, "every_later_gate_yellow": bool(amber) and rest}


def earnings_rows(data: dict) -> dict:
    out = {}
    for row in _list(_dict(_dict(data.get("run")).get("earnings")).get("rows")):
        if isinstance(row, dict):
            items = _dict(row.get("items"))
            out[(row.get("stage"), row.get("ticker"))] = {
                "verdict": row.get("verdict"), "reason": row.get("reason"), "sentence": _text(row.get("sentence")),
                "items_status": items.get("status"), "items_sentence": _text(items.get("sentence")),
                "window": row.get("window")}
    return out


def check_marks(row: dict) -> str:
    """Eight checks in one string: the letter, then + for an A+ pass, ~ partial, x fail, ? unmeasured."""
    out = []
    for c in _list(_dict(row.get("quality")).get("checks")):
        status = c.get("status")
        mark = "+" if status == "PASS" and c.get("a_plus") else STATUS_MARK.get(status, "?")
        out.append(f"{c.get('letter')}{mark}")
    return " ".join(out)


def near_volume_boundary(row: dict):
    """Whether the burst's volume sits within ``NEAR_VOLUME_BAND`` of the previous session's; None when the ratio is not recorded."""
    ratio = row.get("volume_vs_prior")
    return round(abs(ratio - 1), 6) <= NEAR_VOLUME_BAND if _num(ratio) else None


BAR = ("close", "prev_close", "open", "high", "low", "gain_pct", "volume", "prev_volume", "volume_vs_prior",
       "dollar_volume", "dollar_move", "extension_pct")
BAR_EXTRA = ("gap_pct", "bar_range_pct", "close_pos", "volume_vs_avg50", "volume_rank_60")   # quality.burst, not repeated


def candidate(row: dict, cls: str, stage, label, lv, lv_missing, event, earn, passes) -> dict:
    quality = _dict(row.get("quality"))
    adm = _dict(row.get("admission"))
    ticket = cls == "ticket"
    out = {
        "ticker": row.get("ticker"), "name": row.get("name"), "rank": row.get("rank"), "class": cls,
        "model_status": TICKET if ticket else RESEARCH_ONLY,
        "route": row.get("scan"), "admission": adm.get("basis"), "flags": _list(row.get("flags")),
        "vetoes": _list(row.get("vetoes")),
        "bar": {**_pick(row, BAR), **_pick(_dict(quality.get("burst")), BAR_EXTRA),
                "near_volume_boundary": near_volume_boundary(row)},
        "grade_mechanical": row.get("grade_mechanical"), "score": row.get("score"), "grade": row.get("grade"),
        "checks": [{"id": c.get("letter"), "status": c.get("status"), "a_plus": c.get("a_plus"),
                    "measured": c.get("values"), **({"note": c["note"]} if c.get("note") else {})}
                   for c in _list(quality.get("checks"))],
        "base": _pick(_dict(quality.get("base")), ("start", "end", "sessions", "high", "low", "depth_pct",
                                                   "breakdown_dates")) or None,
        "leg": _pick(_dict(quality.get("leg")), ("length", "gain_pct", "er", "r2")) or None,
        "quality_notes": _list(quality.get("notes")),
        "reader": reader_block(row),
        "stage": stage, "why_no_ticket": None if stage == "ticket" else label,
        "would_pass": passes,
        # a ticket's levels are the record's own plan; every other row's are research levels, whatever their source
        "levels" if ticket else "research_levels": lv,
        "research_levels_label": None if ticket or not lv else RESEARCH_LEVELS_LABEL,
        "levels_unavailable": lv_missing,
        "event": event, "earnings": earn,
        "link": _link("bursts", row.get("ticker")),
    }
    return {k: v for k, v in out.items() if v is not None}


def compact(full: dict) -> dict:
    """The same candidate in one short row: every number its research levels name, the checks as marks. A compact
    row is never a ticket and never a reviewed name (those are always detailed), so its levels are always derived
    and it is always research only."""
    lv = _dict(full.get("research_levels"))
    bar = _dict(full.get("bar"))
    event = _dict(full.get("event")).get("status")
    out = {
        "ticker": full.get("ticker"), "rank": full.get("rank"), "model_status": RESEARCH_SHORT,
        "route": full.get("route"),
        "close": bar.get("close"), "gain_pct": bar.get("gain_pct"), "volume_vs_prior": bar.get("volume_vs_prior"),
        "near_volume_boundary": True if bar.get("near_volume_boundary") else None,
        "dollar_volume": bar.get("dollar_volume"), "extension_pct": bar.get("extension_pct"),
        "grade": full.get("grade_mechanical"), "score": full.get("score"),
        "checks": full.get("_marks"), "flags": full.get("flags") or None,
        "trigger": lv.get("trigger"), "limit": lv.get("limit"), "stop": lv.get("stop"),
        "stop_basis": lv.get("stop_basis"), "day2_line": lv.get("day2_line"),
        "skip_if_open_below": lv.get("skip_if_open_below"), "sell_half": lv.get("sell_half"),
        "risk_per_share_at_limit": lv.get("risk_per_share_at_limit"),
        "shares": lv.get("shares"), "cost": lv.get("cost"),
        "shares_at_full_size": _dict(lv.get("at_full_size")).get("shares"),
        "withheld": lv.get("withheld"),
        "refusal": lv.get("refusal") if lv.get("plan_rule_eligible") is False and not lv.get("withheld") else None,
        "levels_unavailable": full.get("levels_unavailable"),
        "event": event if event not in (None, "not_in_registry") else None,
        "stage": full.get("stage"),
    }
    return {k: v for k, v in out.items() if v is not None}


def setting_up(data: dict, modules, account, regime_multiplier, yellow_multiplier, earn) -> dict:
    watch = _dict(data.get("watchlist"))
    plan = modules["plan"]
    stages = {r.get("ticker"): r.get("stage") for r in
              _list(_dict(_dict(data.get("funnel")).get("anticipation")).get("rows")) if isinstance(r, dict)}
    labels = _dict(_dict(data.get("funnel")).get("labels"))
    cuts = {c.get("ticker"): c for c in _list(_dict(data.get("cash_budget")).get("cut"))
            if isinstance(c, dict) and c.get("setup_kind") == "anticipation"}
    listed = []
    for i, row in enumerate(_list(watch.get("top")), 1):
        if not isinstance(row, dict):
            continue
        p = _dict(row.get("plan"))
        stage = stages.get(row.get("ticker"))
        ticket = is_ticket_plan(p)
        why = None if ticket else _text(_dict(cuts.get(row.get("ticker"))).get("reason") or p.get("reason")
                                         or labels.get(stage) or ("no plan was recorded" if not p else None))
        lv = levels(p, "record", plan, account, regime_multiplier, yellow_multiplier) if p else None
        listed.append({k: v for k, v in {
            "ticker": row.get("ticker"), "name": row.get("name"), "rank": i, "setups": row.get("setups"),
            "model_status": TICKET if ticket else RESEARCH_ONLY,
            "measured": _pick(row, ("close", "pct_change_today", "adr20_pct", "range_pct_today", "tight_limit_pct",
                                    "tight_n", "ttt", "tt", "quiet_days", "range_recent_pct", "range_base_pct",
                                    "compress", "volume_ratio", "vol_dry", "breakdowns", "up_run", "close_avg",
                                    "extension", "ti65", "dt", "mdt")),
            "box": _pick(_dict(row.get("box")), ("high", "low", "sessions", "start", "end", "spread", "spread_limit")),
            "risk_pct": row.get("risk_pct"), "passes_coil_checks": row.get("admitted"),
            "eligible": row.get("eligible"), "reasons_failed": row.get("reasons_failed"),
            "ticket": bool(ticket), "stage": stage, "why_no_ticket": why,
            "levels" if ticket else "research_levels": lv,
            "research_levels_label": None if ticket or not lv else
            "the record's own plan for this setup; SpicyStock offers no order at these levels",
            "stop_alt": row.get("stop_alt"),
            "gap_rule": _text(p.get("gap_rule")),
            "open_entry_note": ({"text": _text(p.get("open_entry")), "label": "a research note in the record; not the ticket"}
                                if p.get("open_entry") else None),
            "event": event_state(p), "earnings": earn.get(("anticipation", row.get("ticker"))),
            "link": _link("setting-up", row.get("ticker")),
        }.items() if v is not None})
    quiet = [r for r in _list(watch.get("also_quiet")) if isinstance(r, dict)]
    return {
        "counts": watch.get("counts"), "instruction": _text(watch.get("instruction")),
        "instruction_note": "the record's own sentence over its list; SpicyStock's model rule, not an instruction to "
                            "the reader",
        "listed": listed,
        "also_quiet": [{k: v for k, v in {
            "ticker": r.get("ticker"), "name": r.get("name"), "model_status": RESEARCH_SHORT,
            "setups": r.get("setups"), "close": r.get("close"),
            "compress": r.get("compress"), "tight_n": r.get("tight_n"), "volume_ratio": r.get("volume_ratio"),
            "trigger": r.get("trigger"), "stop": r.get("stop_primary"), "risk_pct": r.get("risk_pct"),
            "why": r.get("why") or "; ".join(str(x) for x in _list(r.get("reasons_failed"))) or None,
            "link": _link("setting-up", r.get("ticker"))}.items() if v is not None} for r in quiet[:ALSO_QUIET_MAX]],
        "also_quiet_left_out": max(0, len(quiet) - ALSO_QUIET_MAX),
    }


def is_ticket_plan(p) -> bool:
    """A setting-up row is a ticket when its recorded plan is eligible, carries an order action and the allocation admitted it."""
    p = _dict(p)
    return bool(p) and p.get("eligible") is True and p.get("action") in ORDER_ACTIONS \
        and _dict(p.get("allocation")).get("admitted", True) is True


def price_states(stop, floor, trigger, limit, day2) -> list:
    """The six words of ``morning.price_state()`` with this ticket's own
    boundaries, in price order, so the brief, the morning receipt's
    ``rows[].price_checks`` and the morning host speak one vocabulary. An
    interval that cannot occur for this ticket says so."""
    def band(state, low, low_in, high, high_in, note=None):
        return {"state": state, "from": low, "from_inclusive": low_in, "to": high, "to_inclusive": high_in,
                "applies": note is None, **({"note": note} if note else {})}

    return [
        band("below_stop", None, False, stop, True),
        band("below_entry_floor", stop, False, floor, False),
        band("below_trigger", floor, True, trigger, False,
             None if _num(floor) and _num(trigger) and floor < trigger
             else "this ticket's entry floor is its trigger, so no price is in this state"),
        band("within_published_band", trigger, True, limit, True),
        band("above_limit", limit, False, day2, True if day2 is not None else False),
        band("above_day2_extension", day2, False, None, False,
             None if day2 is not None else "this ticket has no day-2 line, so no price is in this state"),
    ]


def order_entry(stage: str, row: dict, p: dict, data: dict) -> dict:
    """What an outside reader needs to enter one published ticket as written,
    read off the record's plan: the lines, where the buy stop sits against the
    last close, the order as the record wrote it, and the price-state words.
    The record's action word is carried and labelled, because ``buy_at_open``
    never meant a market-on-open order."""
    burst = p.get("kind") == "burst"
    trigger = p.get("entry_ref") if burst else p.get("trigger")
    floor = p.get("entry_low") if burst else trigger
    day2 = p.get("day2_spent_above") if burst else None
    close = _dict(p.get("burst")).get("close") if burst else p.get("close")
    stop, limit = p.get("stop"), p.get("limit")
    versus = None
    if _num(trigger) and _num(close):
        versus = "equal" if trigger == close else "above" if trigger > close else "below"
    timing = _dict(_dict(data.get("run")).get("timing"))
    ref = _dict(p.get("evidence_ref"))
    not_ticket = {name: text for name, text in (
        ("open_entry", _text(p.get("open_entry"))),
        ("reader_entry_note", _text(_dict(row.get("claude")).get("entry_note")))) if text}
    out = {
        "order_kind": ORDER_KIND,
        "order_kind_meaning": "a day buy stop-limit whose fill triggers a good-til-cancelled sell stop "
                              "(one-triggers-the-other)",
        "record_action_word": p.get("action"),
        "record_action_note": "a legacy word for an eligible ticket and never means a market-on-open order: "
                              "the order is `order_as_written`",
        "shares": p.get("shares"), "last_close": close,
        "lines": {name: value for name, value in (
            ("stop", stop), ("skip_below", p.get("skip_if_open_below") if burst else None), ("trigger", trigger),
            ("limit", limit), ("day2_line", day2), ("extended_above", p.get("extended_above") if burst else None),
            ("gap_ok_above", None if burst else p.get("gap_ok_above"))) if value is not None},
        "buy_stop_vs_last_close": versus,
        "buy_stop_note": BUY_STOP_NOTE if versus == "equal" else None,
        "order_as_written": p.get("order_json"),
        "entry_window": _pick(timing, ("opens_at", "cutoff_at", "prepare_by")) or None,
        "evidence": {"evidence_id": ref.get("id"), "plan_sha256": ref.get("plan_sha256")} if ref else None,
        "price_states": price_states(stop, floor, trigger, limit, day2),
        "price_states_note": "the words of the morning receipt's rows[].price_checks: where a price sits against "
                             "the ticket's lines, never an entry or a cancellation instruction",
        "not_the_ticket": ({**not_ticket, "label": "not the ticket: a note in the record beside it"}
                           if not_ticket else None),
    }
    return {k: v for k, v in out.items() if v is not None}


def ticket(stage: str, row: dict, p: dict, lv: dict, earn, data: dict) -> dict:
    e = earn.get((stage, row.get("ticker")))
    out = {
        "stage": stage, "ticker": row.get("ticker"), "name": row.get("name"), "model_status": TICKET,
        "grade": row.get("grade") if stage == "burst" else "watch", "score": row.get("score") if stage == "burst" else None,
        "order": p.get("order_line"), "order_readback": p.get("order_readback"),
        "order_terms": _list(p.get("order_terms")),
        "order_entry": order_entry(stage, row, p, data),
        "levels": lv,
        "sizing_note": _text(p.get("sizing_note")), "resize_rule": _text(p.get("resize_rule")),
        "limit_note": _text(p.get("limit_note")), "pre_open_check": _text(p.get("pre_open_check")),
        "notes": _list(p.get("notes")),
        "schedule": [{"day": s.get("day"), "date": s.get("date"), "step": s.get("key"),
                      "instruction": _text(s.get("instruction"))} for s in _list(p.get("exit_schedule"))
                     if isinstance(s, dict)],
        "event": event_state(p), "earnings": e,
        "link": _link("bursts" if stage == "burst" else "setting-up", row.get("ticker")),
    }
    return {k: v for k, v in out.items() if v is not None}


def open_plans(data: dict) -> tuple:
    rows = [o for o in _list(data.get("open_plans")) if isinstance(o, dict)]
    out = []
    for o in rows[:OPEN_PLANS_MAX]:
        out.append({k: v for k, v in {
            **_pick(o, ("ticker", "kind", "picked", "grade", "regime", "day", "sessions", "status", "uncertainty",
                        "entry_ref", "limit", "stop", "current_stop", "shares", "sold", "remaining", "half_sold",
                        "last_close", "last_date", "unrealised_pct", "exit_price", "result_pct")),
            "fill": _text(o.get("fill")), "instruction": _text(o.get("instruction")),
            "events": o.get("events"), "minute_bars": bool(o.get("minute_evidence")) or None,
        }.items() if v is not None})
    return out, max(0, len(rows) - OPEN_PLANS_MAX)


def ledger(picks, scorecard: dict) -> dict | None:
    if picks is None:
        return None
    rows = [p for p in _list(_dict(picks).get("picks")) if isinstance(p, dict)]
    tickers = [p.get("ticker") for p in rows]
    counts = {}
    for t in tickers:
        counts[t] = counts.get(t, 0) + 1
    kinds, regimes = {}, {}
    for p in rows:
        kinds[str(p.get("kind"))] = kinds.get(str(p.get("kind")), 0) + 1
        regimes[str(p.get("regime"))] = regimes.get(str(p.get("regime")), 0) + 1
    newest = sorted(rows, key=lambda p: (str(p.get("date")), str(p.get("ticker"))), reverse=True)
    pop = _dict(scorecard.get("population"))
    in_window = [p for p in rows if pop.get("from") and pop.get("through")
                 and str(pop["from"]) <= str(p.get("date")) <= str(pop["through"])]
    return {
        "retained": len(rows), "in_scorecard_window": len(in_window), "scorecard_plans": scorecard.get("plans"),
        "reconciles": len(in_window) == scorecard.get("plans"),
        "distinct_tickers": len(set(tickers)),
        "repeated": {str(t): n for t, n in sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0]))) if n > 1},
        "by_kind": kinds, "by_regime": regimes,
        "rows": [{**_pick(p, ("date", "ticker", "kind", "grade", "regime", "shares")),
                  "trigger": p.get("trigger") if p.get("trigger") is not None else p.get("entry_ref"),
                  "limit": p.get("limit"), "stop": p.get("stop")} for p in newest[:LEDGER_MAX]],
        "rows_left_out": max(0, len(newest) - LEDGER_MAX),
        "rows_rule": f"the newest {LEDGER_MAX} retained picks by pick date; picks.json carries every one",
        "note": "A pick is one published model ticket; the same stock listed on several nights is several picks, "
                "and each counts as its own plan in the scorecard. Picks made under different archived accounts "
                "are sized differently; a pick carries its shares, not the account it was sized for.",
    }


# ------------------------------------------------------------ model record ---
def not_computed(reason: str = NOT_COMPUTED) -> dict:
    return {"status": MODEL_NOT_COMPUTED, "reason": reason}


def model_record_faults(block, record) -> list:
    """What the record can check of a computed model-record block: it counts
    the plans the scorecard counts, bucket by bucket, and its sum of R rounds
    to the scorecard's. Everything else in the block (its tables, its
    sentences) is the evening run's own computation from bars the record does
    not carry, and is carried, not checked."""
    block = _dict(block)
    if block.get("status") != MODEL_COMPUTED:
        return []
    scorecard = _dict(_dict(record).get("scorecard"))
    faults = []
    if type(block.get("version")) is not int:
        faults.append("version is not a whole number")
    if type(block.get("tickets")) is not int or block.get("tickets") != scorecard.get("plans"):
        faults.append(f"tickets {block.get('tickets')!r} is not the scorecard's {scorecard.get('plans')!r} plans")
    buckets = block.get("buckets")
    if not isinstance(buckets, dict):
        faults.append("buckets is not an object")
    else:
        for name in dict.fromkeys((*SCORECARD_BUCKETS, *buckets)):
            ours, theirs = buckets.get(name, 0), scorecard.get(name, 0) if name in SCORECARD_BUCKETS else 0
            if type(ours) is not int or ours != theirs:
                faults.append(f"bucket {name} {ours!r} is not the scorecard's {theirs!r}")
    total, theirs = block.get("sum_r"), scorecard.get("sum_r")
    if theirs is None:
        if total not in (None, 0) or isinstance(total, bool):
            faults.append(f"sum_r {total!r} beside a scorecard with no settled plan")
    elif not _num(total) or round(total, 2) != theirs:
        faults.append(f"sum_r {total!r} does not round to the scorecard's {theirs!r}")
    sentences = block.get("sentences")
    if not isinstance(sentences, list) or not all(isinstance(s, str) for s in sentences):
        faults.append("sentences is not a list of sentences")
    return faults


def model_block(model_record, data: dict) -> dict:
    """The block the brief carries: the evening run's block verbatim, or the reason there is none. A block that
    says of itself that it does not reconcile with the scorecard is carried as it is, with that status and its
    reason; one that calls itself computed and disagrees with the scorecard is not carried. Total over its input,
    so a block that cannot be carried never costs the night its brief, and the file says why it is absent."""
    if model_record is None:
        return not_computed()
    if not isinstance(model_record, dict):
        return not_computed(NOT_CARRIED_UNREADABLE)
    if model_record.get("status") == MODEL_NOT_COMPUTED:
        reason = model_record.get("reason")
        return not_computed(reason if isinstance(reason, str) and reason in NOT_COMPUTED_REASONS
                            else NOT_CARRIED_UNREADABLE)
    if model_record.get("status") not in MODEL_CARRIED:
        return not_computed(NOT_CARRIED_UNREADABLE)
    try:
        raw = _encode(model_record)
        block = json.loads(raw)
    except (TypeError, ValueError):
        return not_computed(NOT_CARRIED_UNREADABLE)
    if scanner_names(block):
        return not_computed(NOT_CARRIED_NAMES)
    if len(raw) > MODEL_RECORD_MAX_BYTES:
        return not_computed(NOT_CARRIED_SIZE)
    if model_record_faults(block, data):
        return not_computed(NOT_CARRIED_DISAGREES)
    return block


# ------------------------------------------------------------------ events ---
def events_block(data: dict, event_risk) -> dict:
    """The archived registry's age and every overdue review at the measured
    session, and ``event_risk.classify()`` under that ARCHIVED registry for
    every listed row: a burst or an also-quiet coil carries no event flag in
    the record unless it has a plan, so this is where an outside reader learns
    that a listed name is a known deal. A name that is not in the registry is
    never called clear."""
    run = _dict(data.get("run"))
    session = run.get("session")
    rules = _dict(_dict(data.get("rules")).get("event_risk"))
    reg = _dict(rules.get("registry"))
    watch = _dict(data.get("watchlist"))
    stages = (("bursts", _list(data.get("bursts"))), ("setting_up", _list(watch.get("top"))),
              ("also_quiet", _list(watch.get("also_quiet"))))
    listed = {stage: sum(1 for r in rows if isinstance(r, dict)) for stage, rows in stages}
    names = {r.get("ticker") for _, rows in stages for r in rows if isinstance(r, dict)}
    earn = _dict(run.get("earnings"))
    checked = {r.get("ticker") for r in _list(earn.get("rows")) if isinstance(r, dict)} & names
    earnings = {"status": earn.get("status") if earn else None,
                "recorded": bool(earn),
                "ticket_rows": len([r for r in _list(earn.get("rows")) if isinstance(r, dict)]),
                "listed_names": len(names), "listed_names_with_a_check": len(checked),
                "listed_names_not_checked": len(names) - len(checked),
                "note": "earnings and SEC 8-K items are read for published tickets only"}
    total = sum(listed.values())
    counts_words = (f"{total} listed rows ({listed['bursts']} bursts, {listed['setting_up']} setting up, "
                    f"{listed['also_quiet']} also quiet)")
    coverage_words = (f"A stock that is not in the registry has not been cleared: SpicyStock reads no company news, "
                      f"and its earnings and SEC checks ran for {len(checked)} of the {len(names)} listed names "
                      "(they run for tickets only).")
    if not reg:
        return {"registry": None, "listed": listed, "listed_matches": None, "earnings": earnings,
                "status_words": EVENT_STATUS_WORDS, "not_checked": list(NOT_CHECKED),
                "sentence": "This record predates the event registry: no listed row was read against one. " + coverage_words}
    events = []
    for e in _list(reg.get("events")):
        if isinstance(e, dict):
            overdue = _days_between(session, e.get("review_due"))
            events.append({"symbol": e.get("symbol"), "kind": e.get("kind"), "announced_on": e.get("announced_on"),
                           "reviewed_on": e.get("reviewed_on"), "review_due": e.get("review_due"),
                           "active_until": e.get("active_until"),
                           "review_overdue": overdue is not None and overdue > 0,
                           "days_overdue": overdue if overdue is not None and overdue > 0 else None})
    unresolved = [e for e in events if not e["active_until"]]
    overdue = sorted((e for e in unresolved if e["review_overdue"]),
                     key=lambda e: (-e["days_overdue"], str(e["symbol"])))
    current = sorted(str(e["review_due"]) for e in unresolved if not e["review_overdue"] and e["review_due"])
    age = _days_between(session, reg.get("reviewed_on"))
    symbols = {e["symbol"] for e in events}
    matches, unreadable = [], False
    for stage, rows in stages:
        for row in rows:
            if not isinstance(row, dict) or row.get("ticker") not in symbols:
                continue
            try:
                found = event_risk.classify(row["ticker"], session, registry=reg)
            except (KeyError, TypeError, ValueError):
                unreadable = True       # the archived registry does not validate: no row is matched, and it is said
                continue
            if not found.get("blocked"):
                continue
            sources = [s for m in _list(found.get("matches")) for s in _list(_dict(m).get("sources"))
                       if isinstance(s, dict)]
            matches.append({
                "stage": stage, "ticker": row["ticker"], "status": found.get("status"),
                "review_overdue": any(_dict(m).get("review_overdue") for m in _list(found.get("matches"))),
                "has_plan": bool(row.get("plan")),
                "flagged_in_the_record": bool(_dict(_dict(row.get("plan")).get("event_risk")).get("blocked")),
                "reason": _text(found.get("reason")),
                "sources": [_pick(s, ("title", "published_on", "url")) for s in sources[:EVENT_SOURCES_MAX]],
                "sources_left_out": max(0, len(sources) - EVENT_SOURCES_MAX)})
    registry = {"coverage": reg.get("coverage"), "policy": rules.get("policy"), "reviewed_on": reg.get("reviewed_on"),
                "age_days": age, "entries": len(events), "unresolved": len(unresolved),
                "resolved": len(events) - len(unresolved),
                "overdue": [{"symbol": e["symbol"], "review_due": e["review_due"], "days_overdue": e["days_overdue"]}
                            for e in overdue],
                "next_review_due": current[0] if current else None,
                "sha256": rules.get("registry_sha256"), "coverage_note": _text(reg.get("coverage_note")),
                "events": events}
    parts = [f"Event registry (manual; known cash acquisitions only): {len(events)} entries, last reviewed "
             f"{reg.get('reviewed_on')}"
             + ("." if age is None else f", {age} days before the measured session {session}." if age >= 0
                else f", {-age} days after the measured session {session}: the archived registry is newer than "
                     "the session it is read against.")]
    if overdue:
        parts.append(f"{len(overdue)} of {len(unresolved)} unresolved entries are past their review date: "
                     + ", ".join(f"{e['symbol']} {e['days_overdue']} days" for e in overdue)
                     + ". Each stays blocked for a SpicyStock ticket; this record does not establish its current "
                       "status.")
    else:
        parts.append(f"None of its {len(unresolved)} unresolved entries is past its review date"
                     + (f" (next due {current[0]})." if current else "."))
    if unreadable:
        matches = None
        parts.append(f"The archived registry does not validate under this code, so none of the {counts_words} was "
                     "matched against it: treat every listed name as unchecked.")
    elif matches:
        parts.append(f"{len(matches)} of the {counts_words} are in the registry: "
                     + ", ".join(f"{m['ticker']} ({m['stage'].replace('_', ' ')}, {m['status']}"
                                 + ("" if m["flagged_in_the_record"] else ", not flagged on its row in the record")
                                 + ")" for m in matches) + ".")
    else:
        parts.append(f"None of the {counts_words} is in the registry.")
    parts.append(coverage_words)
    return {"registry": registry, "listed": listed, "listed_matches": matches, "earnings": earnings,
            "status_words": EVENT_STATUS_WORDS, "not_checked": list(NOT_CHECKED), "sentence": " ".join(parts)}


RULES_SHOWN = {
    "pipeline": ("trade_grades", "yellow_grades", "max_reads", "reader_policy", "reader_refusal_fraction",
                 "reader_refusal_min", "stale_tolerance_fraction", "stale_sessions_max", "min_coverage_fraction"),
    "plan": ("entry_below_pct", "entry_above_pct", "skip_gap_pct", "entry_window_minutes", "assumed_slippage_pct",
             "limit_rule", "sizing_basis", "max_stop_pct", "ideal_stop_pct", "stop_risk_multiplier",
             "gain_ceiling_pct", "extension_hazard_pct", "hazard_multiplier", "sell_half_pct", "abnormal_day_pct",
             "gap_exit_pct", "sell_half_day", "no_progress_day", "trail_from_day", "final_exit_day",
             "allocation_policy"),
    "admission": ("version", "policy"),
    "grading": ("reader_request_version",),
    "record": ("scorecard_min_plans", "scorecard_sessions"),
}


def rules_block(data: dict) -> dict:
    rules = _dict(data.get("rules"))
    without = json.loads(json.dumps(rules, default=str))
    membership = _dict(without.get("universe")).pop("identity", None)
    return {
        "digest": _dict(data.get("app")).get("rules_version"),
        "digest_without_membership": rules_digest(without),
        "membership_identity": membership,
        "digest_note": "the record's digest nests the universe membership identity, so it moves on any night the "
                       "selection's membership moves; `digest_without_membership` is the same digest with that "
                       "identity removed, and moves only when an archived rule changes",
        "selected": {family: _pick(_dict(rules.get(family)), names) for family, names in RULES_SHOWN.items()
                     if _dict(rules.get(family))},
    }


# ------------------------------------------------------------------ derive ---
def build(data: dict, picks, canonical_raw: bytes, picks_raw: bytes | None, modules, model_record=None) -> dict:
    """Everything, unbounded: `shape()` cuts it to the byte bounds."""
    plan, admission, event_risk = modules["plan"], modules["admission"], modules["event_risk"]
    run = _dict(data.get("run"))
    rules = _dict(data.get("rules"))
    pipeline_rules = _dict(rules.get("pipeline"))
    trade = list(pipeline_rules.get("trade_grades") or [])
    yellow = list(pipeline_rules["yellow_grades"]) if isinstance(pipeline_rules.get("yellow_grades"), list) else None
    breadth = _dict(data.get("breadth"))
    regime = _dict(breadth.get("regime"))
    multiplier = float(regime["size_multiplier"]) if _num(regime.get("size_multiplier")) else 1.0
    yellow_size = _dict(_dict(breadth.get("rules")).get("size_multiplier")).get("yellow")
    yellow_size = float(yellow_size) if _num(yellow_size) else None
    recorded = _dict(data.get("account"))
    defaults = plan.Account().to_dict()
    account = plan.Account(**{name: recorded.get(name, value) for name, value in defaults.items()})
    mismatched = plan_rules_match(data, plan)
    funnel = _dict(data.get("funnel"))
    stages = {r.get("ticker"): r.get("stage") for r in _list(_dict(funnel.get("reaction")).get("rows"))
              if isinstance(r, dict)}
    labels = _dict(funnel.get("labels"))
    earn = earnings_rows(data)
    trades = [t for t in _list(data.get("trades")) if isinstance(t, str)]
    bursts = [b for b in _list(data.get("bursts")) if isinstance(b, dict)]
    selected = {s.get("ticker") for s in _list(_dict(run.get("review_selection")).get("selected")) if isinstance(s, dict)}
    selected |= {b.get("ticker") for b in bursts if _dict(b.get("review_selection")).get("selected") or b.get("claude")}

    def in_band(b):
        return b.get("grade_mechanical") in trade and not b.get("vetoes")

    cands, tail = [], []
    near_volume = 0
    for b in bursts:
        admitted = admission.admitted(b)
        near_volume += 1 if near_volume_boundary(b) else 0
        if (in_band(b) and admitted) or b.get("ticker") in trades or b.get("ticker") in selected:
            cls = "ticket" if b.get("ticker") in trades else "reviewed" if b.get("ticker") in selected else "candidate"
            p, missing, source = _dict(b.get("plan")), None, "record"
            if not p:
                p, missing = derived_plan(b, data, modules, account, multiplier, mismatched)
                p, source = _dict(p), "derived"
            lv = levels(p, source, plan, account, multiplier, yellow_size) if p else None
            stage = stages.get(b.get("ticker"))
            row = candidate(b, cls, stage, labels.get(stage), lv, missing, event_state(p),
                            earn.get(("burst", b.get("ticker"))), would_pass(b, trade, yellow, admission))
            row["_marks"] = check_marks(b)
            row["_in_band"] = bool(in_band(b) and admitted)
            cands.append(row)
        else:
            if b.get("vetoes"):
                why = "quality veto: " + ", ".join(str(v) for v in b["vetoes"])
            elif b.get("grade_mechanical") not in trade:
                why = f"mechanical grade {b.get('grade_mechanical')}, below the trade band"
            else:
                why = "not admitted: " + str(_dict(b.get("admission")).get("basis") or "admission not recorded")
            tail.append((why, b.get("ticker"), b.get("grade_mechanical"), b.get("grade")))
    order = {"ticket": 0, "reviewed": 1, "candidate": 2}
    cands.sort(key=lambda r: (order[r["class"]], r.get("rank") if isinstance(r.get("rank"), int) else 10 ** 9))

    tickets = []
    by_ticker = {b.get("ticker"): b for b in bursts}
    for t in trades:
        b = by_ticker.get(t)
        if b and b.get("plan"):
            tickets.append(ticket("burst", b, b["plan"], levels(b["plan"], "record", plan, account, multiplier,
                                                                yellow_size), earn, data))
    for row in _list(_dict(data.get("watchlist")).get("top")):
        p = _dict(_dict(row).get("plan"))
        if is_ticket_plan(p):
            tickets.append(ticket("anticipation", row, p, levels(p, "record", plan, account, multiplier, yellow_size),
                                  earn, data))

    first = next((b for b in bursts if _list(_dict(b.get("quality")).get("checks"))), None)
    weights = _dict(_dict(_dict(first).get("quality")).get("weights"))
    checklist = [{"id": c.get("letter"), "check": c.get("key"), "label": c.get("label"), "threshold": c.get("threshold"),
                  "weight": weights.get(c.get("letter"))}
                 for c in _list(_dict(_dict(first).get("quality")).get("checks"))]
    plans, plans_left = open_plans(data)
    scorecard = _dict(data.get("scorecard"))
    cover = _dict(data.get("cover"))
    canonical_sha = _hash(canonical_raw)
    verdict = str(regime.get("verdict") or "unknown")
    return {
        "schema": SCHEMA, "version": VERSION, "status": "derived",
        "read_first": list(READ_FIRST),
        "identity": identity(data, canonical_raw, picks_raw),
        "headline": {
            "model_gate": f"Model gate {verdict.upper()}: size multiplier {regime.get('size_multiplier')}; "
                          f"{len(tickets)} published model ticket{'' if len(tickets) == 1 else 's'} for the "
                          "applicable session.",
            "record_cover": cover.get("h1"),
            "record_cover_note": "the record's own cover sentence, written for its model tickets; it is not an "
                                 "instruction to the reader",
        },
        "service": service(data, canonical_sha),
        "market": market(data),
        "account": {**_pick(recorded, ("equity", "risk_pct", "max_position_pct", "max_open_positions")),
                    "notes": _list(recorded.get("notes")),
                    "meaning": "the model's configured sizing assumptions; not a brokerage balance"},
        "tickets": tickets,
        "candidates": {
            "definition": "reaction candidates whose mechanical grade is in the trade band "
                          f"({', '.join(trade)}), with no quality veto, that the discovery admission admits; plus "
                          "any other name with a published ticket or a selected chart review",
            "order": "published tickets, then names selected for a chart review, then the rest; each in the "
                     "record's rank order (grade, score descending, ticker)",
            "model_status": f"a row is `{TICKET}` only when the record published a model ticket for it (its order "
                            f"is in `tickets`); every other row is `{RESEARCH_ONLY}`",
            "would_pass_note": "the gates after the market gate, re-derived from the row's recorded fields so a "
                               "RED night does not hide them; passing them is not a ticket: the stop rule, the event "
                               "registry, sizing and the slot allocation follow, and the market gate stands",
            "compact_note": f"every compact row is {RESEARCH_SHORT}: its mechanical grade is in the trade band, it "
                            "has no veto, the admission admits it and the chart reader did not read it"
                            + (f"; under YELLOW the band is {', '.join(yellow)} only" if yellow else ""),
            "near_volume_boundary": {
                "band": NEAR_VOLUME_BAND, "bursts_inside": near_volume,
                "meaning": "the burst's volume is within this fraction of the previous session's, so its "
                           "higher-volume check can flip on the provider's later corrections; the bound is this "
                           "project's own label, not a rule"},
            "counts": {"discovered": len(bursts), "in_trade_band_no_veto": sum(1 for b in bursts if in_band(b)),
                       "admitted_in_trade_band": sum(1 for r in cands if r["_in_band"]),
                       "listed_here": len(cands), "tickets": sum(1 for r in cands if r["class"] == "ticket"),
                       "reviewed": sum(1 for r in cands if _dict(r.get("reader")).get("selected")),
                       "levels_from_record": sum(1 for r in cands if _dict(_row_levels(r)).get("source") == "record"),
                       "levels_derived": sum(1 for r in cands if _dict(_row_levels(r)).get("source") == "derived"),
                       "levels_unavailable": sum(1 for r in cands if not _row_levels(r))},
            "checklist": checklist,
            "check_marks": "letter then + (pass at the A+ level), nothing (pass), ~ (partial), x (fail), ? (not measured)",
            "schedule_days": schedule_days(data, plan.FINAL_EXIT_DAY),
            "exit_rules": exit_rules(plan),
            "exit_sources": {"B": "Bonde", "P": "this project", "T": "a third party's test"},
            "link_pattern": SITE_URL + "#/explore/bursts/<TICKER>",
            "_rows": cands,
        },
        "_tail": tail,
        "funnel": ({"version": funnel.get("version"), "regime": funnel.get("regime"),
                    "admitted_grades": funnel.get("admitted_grades"), "sentence": _text(funnel.get("sentence"), 1400),
                    "labels": {k: v for k, v in labels.items()
                               if _dict(_dict(funnel.get("reaction")).get("stages")).get(k)
                               or _dict(_dict(funnel.get("anticipation")).get("stages")).get(k)},
                    "reaction": {"discovered": _dict(funnel.get("reaction")).get("discovered"),
                                 "potentially_usable": _dict(funnel.get("reaction")).get("potentially_usable"),
                                 "by_mechanical_grade": _dict(funnel.get("reaction")).get("by_mechanical_grade"),
                                 "stages": {k: v for k, v in _dict(_dict(funnel.get("reaction")).get("stages")).items() if v}},
                    "anticipation": {"listed": _dict(funnel.get("anticipation")).get("listed"),
                                     "stages": {k: v for k, v in _dict(_dict(funnel.get("anticipation")).get("stages")).items() if v}}}
                   if funnel else None),
        "closest_miss": data.get("closest_miss"),
        "setting_up": setting_up(data, modules, account, multiplier, yellow_size, earn),
        "open_plans": {"rows": plans, "rows_left_out": plans_left,
                       "total": len([o for o in _list(data.get("open_plans")) if isinstance(o, dict)]),
                       "meaning": "Open MODEL plans walked on daily (and retained minute) bars; not holdings"},
        "scorecard": scorecard or None,
        "pick_ledger": ledger(picks, scorecard),
        "model_record": model_block(model_record, data),
        "cash_budget": data.get("cash_budget"),
        "events": events_block(data, event_risk),
        "rules": rules_block(data),
        "limits": list(LIMITS),
    }


def _row_levels(row: dict):
    return row.get("levels") or row.get("research_levels")


def shape(full: dict, detail, compact_n) -> dict:
    """The brief at one pair of row bounds; `full` is not modified."""
    out = json.loads(json.dumps(full))       # a deep copy of plain JSON
    rows = out["candidates"].pop("_rows")
    tail = out.pop("_tail")
    always = [r for r in rows if r["class"] in ("ticket", "reviewed")]
    rest = [r for r in rows if r["class"] == "candidate"]
    n_detail = len(rest) if detail is None else min(detail, len(rest))
    detailed, remainder = always + rest[:n_detail], rest[n_detail:]
    n_compact = len(remainder) if compact_n is None else min(compact_n, len(remainder))
    compact_rows, dropped = remainder[:n_compact], remainder[n_compact:]
    groups: dict = {}
    for r in dropped:
        tail.append(("in the trade band and admitted; its row was left out for size", r["ticker"],
                     r.get("grade_mechanical"), r.get("grade")))
    kept_tail, cut_tail = tail[:TAIL_MAX], tail[TAIL_MAX:]
    for why, ticker, mech, final in kept_tail:
        group = groups.setdefault(why, {"reason": why, "count": 0, "tickers": []})
        group["count"] += 1
        group["tickers"].append(ticker if mech == final else f"{ticker} ({mech}>{final})")
    left_by_reason: dict = {}
    for why, *_ in cut_tail:
        left_by_reason[why] = left_by_reason.get(why, 0) + 1
    compact_out = [compact(r) for r in compact_rows]
    for r in detailed:
        r.pop("_marks", None)
        r.pop("_in_band", None)
    out["candidates"]["detailed"] = detailed
    out["candidates"]["compact"] = compact_out
    out["research_tail"] = {
        "meaning": f"Every other reaction candidate: {RESEARCH_SHORT}, no SpicyStock ticket and no levels. Tickers "
                   "in the record's rank order, grouped by the one reason; a ticker whose final grade differs from "
                   "its mechanical grade shows both",
        "total": len(tail), "groups": list(groups.values()),
        "left_out": len(cut_tail), "left_out_by_reason": left_by_reason,
    }
    model = _dict(out.get("model_record"))
    out["bounds"] = {
        "json_bytes_max": MAX_JSON_BYTES, "md_bytes_max": MAX_MD_BYTES,
        "candidates_detailed": len(detailed), "candidates_compact": len(compact_out),
        "candidates_moved_to_tail": len(dropped),
        "candidates_rule": "Tickets and reviewed names are always detailed; of the rest, in the stated order, the "
                           f"largest multiple of {DETAIL_STEP} (or all) is detailed that keeps brief.json within "
                           f"{MAX_JSON_BYTES} bytes, and the others are compact rows; only if none can be detailed "
                           f"are compact rows cut, to the largest multiple of {COMPACT_STEP} that fits, the rest "
                           "moving to the research tail",
        "research_tail_named": len(kept_tail), "research_tail_left_out": len(cut_tail),
        "research_tail_rule": f"the first {TAIL_MAX} by the record's rank order",
        "open_plans_left_out": out["open_plans"]["rows_left_out"],
        "open_plans_rule": f"the first {OPEN_PLANS_MAX} in the record's own order",
        "pick_ledger_left_out": _dict(out.get("pick_ledger")).get("rows_left_out"),
        "stale_names_left_out": _dict(_dict(_dict(out["service"]).get("inputs")).get("tolerance")).get("names_left_out"),
        "also_quiet_left_out": out["setting_up"]["also_quiet_left_out"],
        "model_record_carried": model.get("status") in MODEL_CARRIED,
        "model_record_rule": f"The evening run's model-record block is carried whole when its canonical encoding is "
                             f"within {MODEL_RECORD_MAX_BYTES} bytes and the brief still fits with it, and not at "
                             f"all otherwise; brief.md prints its sentences and, while they fit, the first "
                             f"{MODEL_MD_ROWS} rows and {MODEL_MD_COLUMNS} columns of each of its tables",
        "text_rule": f"A copied sentence over {TEXT_MAX} characters is cut and ends with an ellipsis",
    }
    return out


def _largest(total: int, step: int, fits) -> int | None:
    """The largest n in {total, the multiples of step below it} with fits(n) true; None when even 0 does not fit.
    `fits` must be monotonic: true at n implies true at every smaller n."""
    if fits(total):
        return total
    grid = list(range(0, total, step))             # ascending; total itself already failed
    if not grid or not fits(grid[0]):
        return None
    lo, hi = 0, len(grid) - 1                      # grid[lo] fits
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if fits(grid[mid]):
            lo = mid
        else:
            hi = mid - 1
    return grid[lo]


def fit_json(full: dict) -> bytes:
    others = sum(1 for r in full["candidates"]["_rows"] if r["class"] == "candidate")

    def size(detail, compact_n):
        return len(_encode(shape(full, detail, compact_n)))
    detail = _largest(others, DETAIL_STEP, lambda n: size(n, None) <= MAX_JSON_BYTES)
    if detail is not None:
        return _encode(shape(full, detail, None))
    compact_n = _largest(others, COMPACT_STEP, lambda n: size(0, n) <= MAX_JSON_BYTES)
    if compact_n is None:
        raise DoesNotFit(f"brief.json does not fit {MAX_JSON_BYTES} bytes at its smallest row bounds")
    return _encode(shape(full, 0, compact_n))


# ---------------------------------------------------------------- markdown ---
NA = "n/a"


def _stop(text) -> str:
    """The text without a trailing full stop, so a line that adds its own does not print two."""
    return str(text).rstrip().rstrip(".")


def _n(value, digits=2) -> str:
    if value is None:
        return NA
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    return str(value)


def _usd(value) -> str:
    return NA if not _num(value) else f"${value:,.2f}"


def _day(value) -> str:
    try:
        d = date.fromisoformat(str(value)[:10])
        return f"{d:%a} {d.day} {d:%b %Y}"
    except ValueError:
        return str(value)


def _cell(value) -> str:
    return str(value if value is not None else NA).replace("|", "\\|").replace("\n", " ")


def _table(header, rows) -> list:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return out


def _short(value, digits=2) -> str:
    """A table number: no thousands separator, no trailing zeros."""
    if value is None:
        return NA
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        text = f"{value:.{digits}f}"
        return text.rstrip("0").rstrip(".") if "." in text else text
    return str(value)


def _levels_line(lv: dict, research: bool) -> str:
    """One line of levels. A research row's line says so, and a refused plan prints its refusal and no share count."""
    head = f"research levels ({lv.get('source')}; no order is offered at them)" if research \
        else f"levels ({lv.get('source')})"
    if not lv:
        return "levels: not available"
    if lv.get("withheld"):
        return (f"{head}: trigger {_usd(lv.get('trigger'))}; ticket withheld ({lv.get('withheld')}): no "
                f"limit above the trigger keeps a structural stop inside the stop line; day-2 line {_usd(lv.get('day2_line'))}; "
                f"skip if it opens under {_usd(lv.get('skip_if_open_below'))}")
    parts = [f"trigger {_usd(lv.get('trigger'))}", f"limit {_usd(lv.get('limit'))}",
             f"stop {_usd(lv.get('stop'))} ({lv.get('stop_basis')}, {_n(lv.get('stop_pct_at_limit'))}% under the limit)"]
    if lv.get("day2_line") is not None:
        parts.append(f"day-2 line {_usd(lv.get('day2_line'))}")
    if lv.get("skip_if_open_below") is not None:
        parts.append(f"skip if it opens under {_usd(lv.get('skip_if_open_below'))}")
    if lv.get("gap_check_above") is not None:
        parts.append(f"gap check above {_usd(lv.get('gap_check_above'))}")
    parts.append(f"sell-half {_usd(lv.get('sell_half'))}")
    parts.append(f"risk a share at the limit {_usd(lv.get('risk_per_share_at_limit'))}")
    if lv.get("plan_rule_eligible") is not True:
        parts.append("the plan rule refused it, so no model size is stated")
    else:
        size = (f"model size {_n(lv.get('shares'))} shares, {_usd(lv.get('cost'))} cost, {_usd(lv.get('risk'))} risk "
                f"(multiplier {_n(lv.get('multiplier'))})")
        for label, name in (("at full size", "at_full_size"), ("at the YELLOW size", "at_yellow_size")):
            other = lv.get(name)
            if other:
                size += f"; {label} {_n(other.get('shares'))} shares, {_usd(other.get('cost'))}"
        if lv.get("size_note"):
            size += f"; {lv['size_note']}"
        parts.append(size)
    return f"{head}: " + "; ".join(parts)


def _marks_of(r: dict) -> str:
    marks = []
    for c in _list(r.get("checks")):
        status = c.get("status")
        marks.append(f"{c.get('id')}{'+' if status == 'PASS' and c.get('a_plus') else STATUS_MARK.get(status, '?')}")
    return " ".join(marks)


def _gate(value) -> str:
    return "not recorded" if value is None else "pass" if value else "fail"


def _would_pass_line(w: dict) -> str:
    return (f"Later gates: GREEN band {_gate(w.get('grade_band_green'))}, YELLOW band "
            f"{_gate(w.get('grade_band_yellow'))}, veto {_gate(w.get('no_veto'))}, admission "
            f"{_gate(w.get('admission'))}, reader `{w.get('reader')}`; all of them under GREEN "
            f"{_n(w.get('every_later_gate_green'))}, under YELLOW {_n(w.get('every_later_gate_yellow'))}.")


def _candidate_md(r: dict, short: bool = False) -> list:
    """One candidate in detail. ``short`` is the form a reviewed name takes when the file would not otherwise fit:
    its checks as marks, no base line, and of the reader's sentences its reason alone, cut to ``MD_SHORT_TEXT``."""
    bar, reader = _dict(r.get("bar")), _dict(r.get("reader"))
    ticket = r.get("class") == "ticket"
    short = short and r.get("class") == "reviewed"
    head = (f"### {r.get('ticker')} · " + (f"{r['name']} · " if r.get("name") else "") + f"rank {r.get('rank')} · "
            f"{r.get('grade_mechanical')} {_n(r.get('score'))}"
            + (f", final {r.get('grade')}" if r.get("grade") != r.get("grade_mechanical") else "")
            + (f" · {TICKET} (order and schedule in section 5)" if ticket else f" · {r.get('class')} · {RESEARCH_ONLY}"))
    out = [head, "",
           f"- Bar: close {_usd(bar.get('close'))} ({_n(bar.get('gain_pct'))}% from {_usd(bar.get('prev_close'))}), "
           f"open {_usd(bar.get('open'))}, high {_usd(bar.get('high'))}, low {_usd(bar.get('low'))}; volume "
           f"{_n(bar.get('volume'), 0)} ({_n(bar.get('volume_vs_prior'))}x the prior session"
           + (", inside the near-volume band" if bar.get("near_volume_boundary") else "")
           + f", {_n(bar.get('volume_vs_avg50'))}x its "
           f"50-session average), dollar volume ${_short((bar.get('dollar_volume') or 0) / 1e6, 1)}M; {_n(bar.get('extension_pct'), 1)}% over its "
           f"20-session average; route {r.get('route')} ({r.get('admission')})"
           + (f"; flags {', '.join(r['flags'])}" if r.get("flags") else "")
           + (f"; vetoes {', '.join(str(v) for v in r['vetoes'])}" if r.get("vetoes") else "") + "."]
    if short:
        out.append(f"- Checks (marks only; measurements in brief.json): {_marks_of(r)}.")
    else:
        checks = []
        for c in _list(r.get("checks")):
            status = c.get("status")
            mark = "+" if status == "PASS" and c.get("a_plus") else STATUS_MARK.get(status, "?")
            measured = " ".join(f"{k}={_short(v)}" for k, v in _dict(c.get("measured")).items())
            checks.append(f"**{c.get('id')}{mark}** {measured}")
        base = _dict(r.get("base"))
        out.append("- Checks: " + " · ".join(checks)
                   + (f". Base {base.get('start')} to {base.get('end')}, {_usd(base.get('low'))} to {_usd(base.get('high'))}" if base else "")
                   + ("; " + "; ".join(r["quality_notes"]) if r.get("quality_notes") else "") + ".")
    line = f"- Chart reader: {reader.get('state')}"
    if reader.get("grade"):
        line += f", {reader.get('grade')} {_n(reader.get('score'), 1)} ({reader.get('purpose')})"
    if reader.get("blockers"):
        line += f"; selection blockers: {', '.join(reader['blockers'])}"
    if reader.get("error"):
        line += f"; error: {reader['error']}"
    out.append(line + ".")
    if short and reader.get("reason"):
        out.append(f"  - Reader's reason (commentary, cut; its risk and entry note are in brief.json): "
                   f"{_text(reader['reason'], MD_SHORT_TEXT)}")
    for label, field in (("Reader's reason (commentary)", "reason"), ("Reader's main risk (commentary)", "risk"),
                         ("Reader's entry note (not the ticket)", "entry_note")):
        if reader.get(field) and not short:
            out.append(f"  - {label}: {reader[field]}")
    if r.get("would_pass"):
        out.append("- " + _would_pass_line(r["would_pass"]))
    lv = _dict(_row_levels(r))
    if not ticket:
        out.append("- " + (_levels_line(lv, True) if lv else f"research levels: not available ({r.get('levels_unavailable')})") + ".")
        if lv.get("refusal"):
            out.append(f"- Plan rule refusal: {lv['refusal']}")
        if r.get("why_no_ticket"):
            out.append(f"- No ticket: {r['why_no_ticket']} (stage `{r.get('stage')}`).")
        event = _dict(r.get("event"))
        if event.get("status") != "not_in_registry":
            out.append(f"- Event registry: {event.get('status') or 'not read'}" + (f": {_stop(event['reason'])}" if event.get("reason") else "") + ".")
    out.append("")
    return out


COMPACT_HEADER = ("ticker", "gain %", "vol x", "$ vol M", "ext %", "grade", "checks", "trigger", "limit", "stop",
                  "sell-half", "risk/sh", "shares")
STOP_BASIS_MARK = {"burst_low": "L", "half_range": "M"}


def _compact_md_row(c: dict, modal_stage) -> list:
    dollars = c.get("dollar_volume")
    stop = _short(c.get("stop")) + (STOP_BASIS_MARK.get(c.get("stop_basis"), "") if c.get("stop") is not None else "")
    shares = f"{_short(c.get('shares'))}" + (f"/{_short(c.get('shares_at_full_size'))}" if c.get("shares_at_full_size") is not None else "")
    if c.get("refusal"):
        shares = "refused"
    ticker = str(c.get("ticker")) + (f" [{c.get('stage')}]" if c.get("stage") != modal_stage else "") \
        + (f" [{c.get('event')}]" if c.get("event") else "")
    return [ticker, _short(c.get("gain_pct")),
            _short(c.get("volume_vs_prior")) + ("*" if c.get("near_volume_boundary") else ""),
            _short(dollars / 1e6 if _num(dollars) else None, 1), _short(c.get("extension_pct"), 1),
            f"{c.get('grade')} {_short(c.get('score'))}", c.get("checks"),
            _short(c.get("trigger")), "withheld" if c.get("withheld") else _short(c.get("limit")), stop,
            _short(c.get("sell_half")), _short(c.get("risk_per_share_at_limit")), shares]


def _compact_from_detailed(r: dict) -> dict:
    return compact({**r, "_marks": _marks_of(r)})


def _state_range(s: dict) -> str:
    if not s.get("applies"):
        return str(s.get("note"))
    low, high = s.get("from"), s.get("to")
    if low is None:
        return f"at or under {_usd(high)}" if s.get("to_inclusive") else f"under {_usd(high)}"
    if high is None:
        return f"at or over {_usd(low)}" if s.get("from_inclusive") else f"over {_usd(low)}"
    return (f"{'from' if s.get('from_inclusive') else 'over'} {_usd(low)} "
            f"{'through' if s.get('to_inclusive') else 'to under'} {_usd(high)}")


def _model_cell(value, maximum=MODEL_MD_CELL) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    elif isinstance(value, bool):
        value = "yes" if value else "no"
    elif isinstance(value, float):
        value = _short(value, 4)
    elif value is None:
        value = NA
    text = str(value)
    return text if len(text) <= maximum else text[:maximum - 1] + "\u2026"


def _scalar(value) -> bool:
    return not isinstance(value, (dict, list))


def _model_rows(name: str, table) -> tuple:
    """(rows, other entries) of one model-record table, whatever its shape: a list of rows, an object holding a
    `rows` list, or an object of named rows."""
    if isinstance(table, list):
        return [r if isinstance(r, dict) else {name: r} for r in table], {}
    if isinstance(table, dict):
        if isinstance(table.get("rows"), list):
            rows = [r if isinstance(r, dict) else {name: r} for r in table["rows"]]
            return rows, {k: v for k, v in table.items() if k != "rows"}
        if table and all(isinstance(v, dict) for v in table.values()):
            return [{name: k, **v} for k, v in table.items()], {}
        return [], dict(table)
    return [], {name: table}


def _model_entry(name: str, value) -> list:
    """One named entry beside a table's rows, in lines: an object of plain values on one line, its entries of
    sentences one line each."""
    if isinstance(value, dict) and value and all(_scalar(v) for v in value.values()):
        if any(isinstance(v, str) and len(v) > MODEL_MD_CELL for v in value.values()):
            return [f"- {name}.{k}: {_model_cell(v, TEXT_MAX)}" for k, v in value.items()]
        return [f"- {name}: " + ", ".join(f"{k} {_model_cell(v)}" for k, v in value.items())]
    return [f"- {name}: {_model_cell(value, TEXT_MAX)}"]


def _model_md(block: dict, tables: bool = True) -> list:
    """The model-record block, rendered without knowing its tables: its sentences, its counts, every other list of
    sentences it carries under that list's own name, then (with ``tables``) whichever of ``MODEL_TABLES`` are
    present. A block that says it does not reconcile prints its sentences and no figure."""
    status = block.get("status")
    if status not in MODEL_CARRIED:
        return [f"- Model-record block: not computed ({block.get('reason')})."]
    out = [f"- {s}" for s in _list(block.get("sentences")) if isinstance(s, str)]
    if status == MODEL_UNRECONCILED:
        out.append("- Model-record block: carried as the evening run wrote it, with the status `unreconciled`. Its "
                   "tables are in brief.json and none of its figures is printed here.")
        return out
    buckets = _dict(block.get("buckets"))
    out.append(f"- Model-record block (version {_n(block.get('version'))}): {_n(block.get('tickets'))} tickets; "
               + (", ".join(f"{k} {_n(v)}" for k, v in buckets.items()) or "no buckets")
               + f"; sum of R {_short(block.get('sum_r'))}. Computed by the evening run from that run's fetched bars; "
                 "its ticket count, bucket counts and sum of R are held to the record's scorecard, the rest is "
                 "carried as computed.")
    for name, value in block.items():
        if name != "sentences" and isinstance(value, list) and value and all(isinstance(v, str) for v in value):
            out.extend(f"- Model record, {name}: {_model_cell(v, TEXT_MAX)}" for v in value)
    if not tables:
        out.append("- Model-record tables: not printed here, to keep this file within its bound; brief.json "
                   "carries every one.")
        return out
    for name in MODEL_TABLES:
        if name not in block:
            continue
        rows, others = _model_rows(name, block[name])
        for k, v in others.items():
            out.extend(_model_entry(f"{name}.{k}", v))
        if not rows:
            continue
        seen = list(dict.fromkeys(k for r in rows[:MODEL_MD_ROWS] for k in r))
        columns = [c for c in MODEL_MD_FIRST if c in seen] + [c for c in seen if c not in MODEL_MD_FIRST]
        shown = columns[:MODEL_MD_COLUMNS]
        out.append("")
        out.append(f"Model record, {name} ({min(len(rows), MODEL_MD_ROWS)} of {len(rows)} rows"
                   + (f", {len(shown)} of {len(columns)} columns" if len(columns) > len(shown) else "")
                   + "; brief.json carries every one):")
        out.append("")
        out.extend(_table(shown, [[_model_cell(r.get(c)) for c in shown] for r in rows[:MODEL_MD_ROWS]]))
    return out


def render_markdown(brief: dict, json_raw: bytes, md_detail=None, md_compact=None, md_tail=None,
                    md_short: bool = False, md_model_tables: bool = True) -> bytes:
    """brief.md from brief.json's parsed content and its exact bytes. Pure; standard library only."""
    ident, svc, mkt = _dict(brief.get("identity")), _dict(brief.get("service")), _dict(brief.get("market"))
    urls, win = _dict(ident.get("urls")), _dict(ident.get("entry_window"))
    head = _dict(brief.get("headline"))
    L: list = []
    add = L.append

    def section(number: int, extra: str = ""):
        add(f"## {number}. {SECTIONS[number - 1]}{extra}")
        add("")

    add(f"# SpicyStock daily brief: measured {_day(ident.get('measured_session'))}, plans for {_day(ident.get('applicable_session'))}")
    add("")
    for sentence in _list(brief.get("read_first")):
        add(f"> {sentence}")
    add("")
    add(f"**{head.get('model_gate')}** The record's own cover sentence, written for its model tickets and not an "
        f"instruction to the reader: \"{head.get('record_cover')}\"")
    add("")
    section(1)
    add(f"- Measured session: {ident.get('measured_session')} ({ident.get('session_state')}); plans are for "
        f"**{ident.get('applicable_session')}**, entry window {win.get('opens_at')} to {win.get('cutoff_at')} "
        f"({win.get('timezone')}), full session closes {win.get('closes_at')}"
        + ("; a shortened session" if win.get("shortened") else "") + ".")
    add(f"- Published {ident.get('published_at')} (" + (f"run {ident.get('run_id')}, " if ident.get("run_id") else "")
        + f"{ident.get('run_type')}"
        + (", DRY RUN" if ident.get("dry_run") else "") + (f", FIXTURE {ident.get('fixture')}" if ident.get("fixture") else "")
        + f"); rules version `{ident.get('rules_version')}`.")
    canon = _dict(ident.get("canonical"))
    add(f"- Canonical record `data.json`: {_n(canon.get('bytes'))} bytes, SHA-256 `{canon.get('sha256')}`.")
    if ident.get("picks"):
        add(f"- `picks.json`: {_n(ident['picks'].get('bytes'))} bytes, SHA-256 `{ident['picks'].get('sha256')}`.")
    add(f"- This file renders `brief.json` ({_n(len(json_raw))} bytes, SHA-256 `{_hash(json_raw)}`).")
    add(f"- Page {urls.get('page')} · record {urls.get('record')} · brief {urls.get('brief_json')} and {urls.get('brief_md')}"
        + (f" · run log {urls.get('run_log')}" if urls.get("run_log") else "") + ".")
    add("")
    section(2)
    add(f"- Run status: **{svc.get('status')}**; problems: "
        + ("; ".join(f"{p.get('kind')}: {p.get('message')}" for p in _list(svc.get("problems"))) or "none") + f"; mail {svc.get('email')}.")
    if svc.get("delivery"):
        add(f"- Delivery: {svc['delivery'].get('sentence')} (slot `{svc['delivery'].get('slot')}`, "
            f"{_n(svc['delivery'].get('latency_minutes'), 1)} minutes after completion).")
    exp = _dict(svc.get("expected"))
    add(f"- Next publication (`service.expected`): the next session is {exp.get('next_session') or NA}; it completes "
        f"at {exp.get('completion_at') or NA}; primary slot {exp.get('primary_slot_at') or NA}; retry slot "
        f"{exp.get('retry_slot_at') or NA}; recovery limit {exp.get('recovery_until') or NA}."
        + ("".join(f" Unknown {k}: {v}." for k, v in _dict(exp.get("unknown")).items())))
    add("- Freshness rule (states: " + ", ".join(f"`{s}`" for s in _list(svc.get("freshness_states"))) + "):")
    for line in _list(svc.get("freshness_rule")):
        add(f"  - {line}")
    mor = _dict(svc.get("morning"))
    receipt = _dict(mor.get("receipt"))
    add(f"- Morning check: plans are for {mor.get('applicable_session') or NA}; entry window "
        f"{mor.get('window_opens_at') or NA} to {mor.get('window_cutoff_at') or NA}; the morning collection starts "
        f"at {mor.get('collection_starts_at') or NA}. Receipt {receipt.get('url')}: {receipt.get('rule')}"
        + (f" Unknown: {mor.get('unknown')}." if mor.get("unknown") else ""))
    inputs = _dict(svc.get("inputs"))
    basis = _dict(inputs.get("basis"))
    add(f"- Inputs: {basis.get('provider')} `{basis.get('feed')}`, {basis.get('adjustment')}-adjusted {basis.get('timeframe')} bars, "
        + (f"fetched {inputs.get('fetched_at')}; " if inputs.get("fetched_at") else "the fetch time is not recorded; ")
        + f"{_n(inputs.get('ready_stocks'))} of {_n(inputs.get('intended_stocks'))} intended stocks ready "
        f"(acceptance `{inputs.get('acceptance')}`); {_n(_dict(inputs.get('counts')).get('measured'))} measured, "
        f"{_n(_dict(inputs.get('counts')).get('stale'))} stale.")
    tol = _dict(inputs.get("tolerance"))
    if tol:
        add(f"- Stale tolerance: `{tol.get('verdict')}` ({_n(tol.get('stale_stocks'))} stale against a limit of {_n(tol.get('limit'))})."
            + (f" Stale: {', '.join(_list(tol.get('names')))}" + (f" and {tol.get('names_left_out')} more" if tol.get("names_left_out") else "") + "."
               if tol.get("names") else ""))
    for label, text in (("Seed", inputs.get("seed_stale")), ("Follow-up", _dict(inputs.get("stale_followup")).get("sentence")),
                        ("Minute bars", inputs.get("intraday"))):
        if text:
            add(f"- {label}: {text}")
    add("- What the inputs do not establish: " + " ".join(_list(inputs.get("unknown"))))
    rd = _dict(svc.get("reader"))
    reads, cost, sel = _dict(rd.get("reads")), _dict(rd.get("cost")), _dict(rd.get("selection"))
    add(f"- Chart reader ({rd.get('model')}): {_n(reads.get('done'))} of {_n(reads.get('requested'))} reads accepted, "
        f"verdict `{reads.get('verdict')}`"
        + (f"; refused: {', '.join(reads['refused_names'])}" if reads.get("refused_names") else "")
        + (f". {reads.get('sentence')}" if reads.get("sentence") else ".")
        + (f" {cost.get('sentence')}" if cost.get("sentence") else ""))
    if sel:
        add(f"- Review selection (`{sel.get('policy')}`): {_n(sel.get('feasible'))} feasible, {_n(sel.get('requested'))} requested of "
            f"{_n(sel.get('max_reads'))}; selected: "
            + (", ".join(f"{s.get('ticker')} ({s.get('purpose')})" for s in _list(sel.get("selected")) if isinstance(s, dict)) or "none") + ".")
    if _dict(svc.get("admission")).get("sentence"):
        add(f"- {svc['admission']['sentence']}")
    if _dict(svc.get("earnings")).get("sentence"):
        add(f"- Earnings and 8-K items (status `{svc['earnings'].get('status')}`): {svc['earnings'].get('sentence')}")
    funnel = _dict(brief.get("funnel"))
    if funnel.get("sentence"):
        add(f"- {funnel['sentence']}")
    if _dict(brief.get("closest_miss")).get("sentence"):
        add(f"- Closest miss: {brief['closest_miss']['sentence']}")
    add("")
    section(3)
    add(f"- Verdict **{str(mkt.get('verdict')).upper()}** for {mkt.get('date')}: size multiplier {_n(mkt.get('size_multiplier'))}; "
        f"grades the regime admits to a ticket: {', '.join(_list(mkt.get('admits_grades'))) or 'none'}. {mkt.get('gate_note')}")
    for reason in _list(mkt.get("reasons")):
        add(f"- Recorded reason: {reason}")
    counts, ratios = _dict(mkt.get("counts")), _dict(mkt.get("ratios"))
    pop = _dict(mkt.get("population"))
    add(f"- Counts over {_n(counts.get('universe'))} measured stocks ({_n(pop.get('intended_stocks'))} intended, "
        f"{_n(pop.get('with_a_session_bar'))} with a session bar, {_n(pop.get('under_the_session_price_floor'))} under "
        f"the {_usd(pop.get('session_price_floor'))} session close floor): up 4% {_n(counts.get('up4'))}, down 4% {_n(counts.get('down4'))}; "
        f"up/down 25% in a quarter {_n(counts.get('up25_quarter'))}/{_n(counts.get('down25_quarter'))}; up/down 25% in a month "
        f"{_n(counts.get('up25_month'))}/{_n(counts.get('down25_month'))}; up/down 50% in a month {_n(counts.get('up50_month'))}/"
        f"{_n(counts.get('down50_month'))}; up/down 13% in 34 days {_n(counts.get('up13_34d'))}/{_n(counts.get('down13_34d'))}; "
        f"{_n(counts.get('pct_above_40ma'), 1)}% above the 40-day average.")
    sums = _dict(mkt.get("sums"))
    add(f"- Ratios: 5-session {_n(ratios.get('ratio_5d'))} ({_n(ratios.get('up4_5d'))} up, {_n(ratios.get('down4_5d'))} down"
        + (f", unrounded {_short(sums.get('ratio_5d_unrounded'), 4)}" if sums.get("ratio_5d_unrounded") is not None else "")
        + f"); 10-session {_n(ratios.get('ratio_10d'))} ({_n(ratios.get('up4_10d'))} up, {_n(ratios.get('down4_10d'))} down"
        + (f", unrounded {_short(sums.get('ratio_10d_unrounded'), 4)}" if sums.get("ratio_10d_unrounded") is not None else "")
        + "). The rules compare the rounded number.")
    add("")
    scaling = _dict(mkt.get("scaling"))
    rules_rows = mkt.get("rules")
    if rules_rows:
        add(f"All five regime rules, in the order they are asked (universe {_n(scaling.get('universe'))} against a "
            f"reference of {_n(scaling.get('reference_universe'))}). {scaling.get('note')}")
        add("")
        L.extend(_table(("rule", "tier", "measured", "comparison", "threshold tonight", "reference", "fired", "decides", "masked"),
                        [(r.get("rule"), r.get("tier"), f"{r.get('measure')} {_short(r.get('measured'))}", r.get("comparison"),
                          _short(r.get("threshold_tonight")),
                          (f"{_short(r.get('reference'))} of {_n(r.get('reference_universe'))}" if r.get("scaled")
                           else f"{_short(r.get('reference'))}, not scaled"),
                          _n(r.get("fired")), _n(r.get("decides")), _n(r.get("masked"))) for r in rules_rows]))
        add("")
        add(f"- {mkt.get('green_needs')}")
        flags = _dict(mkt.get("flags"))
        near = _dict(flags.get("near_line"))
        add(f"- Yellow by rounding (more ten-session breakdowns than breakouts while the rounded ratio is not under "
            f"the red line): {_n(flags.get('yellow_by_rounding'))}. Near a line: "
            + (f"{_n(near.get('inside_band'))} (the 10-session ratio is {_short(near.get('to_red_line'))} from the red line "
               f"and {_short(near.get('to_yellow_line'))} from the yellow line; band {_short(near.get('band'))}, {near.get('note')})."
               if near else "not measured."))
    else:
        add(f"The regime rules are not re-derived here: {mkt.get('rules_unavailable')}. Thresholds as recorded "
            f"(universe {_n(scaling.get('universe'))} against a reference of {_n(scaling.get('reference_universe'))}):")
        add("")
        L.extend(_table(("rule", "threshold tonight", "reference", "measured"),
                        [(t.get("rule"), _n(t.get("threshold_tonight")), _n(t.get("reference")),
                          f"{t.get('measure')} {_n(t.get('measured'))}") for t in _list(mkt.get("thresholds"))]))
    add("")
    add("Breadth history (" + str(mkt.get("history_rule")) + "): "
        + "; ".join(f"{h.get('date')} {_n(h.get('up4'))}/{_n(h.get('down4'))} r10 {_n(h.get('ratio_10d'))}"
                    for h in _list(mkt.get("history")) if isinstance(h, dict)) + ".")
    add("")
    acct = _dict(brief.get("account"))
    section(4)
    add(f"- Model account ({acct.get('meaning')}): equity {_usd(acct.get('equity'))}, risk {_n(acct.get('risk_pct'))}% a trade, position cap "
        f"{_n(acct.get('max_position_pct'))}%, {_n(acct.get('max_open_positions'))} slots.")
    budget = _dict(brief.get("cash_budget"))
    if budget.get("sentence"):
        add(f"- {budget['sentence']}.")
    for cut in _list(budget.get("cut")):
        if isinstance(cut, dict):
            add(f"- Cut: {cut.get('ticker')} ({cut.get('setup_kind')}, {cut.get('kind')}): {cut.get('reason')}")
    add("")
    tickets = _list(brief.get("tickets"))
    section(5, f" ({len(tickets)})")
    if not tickets:
        add("None. The record published no model ticket for the applicable session.")
        add("")
    else:
        first = _dict(tickets[0].get("order_entry"))
        add(f"Every ticket here is a MODEL ticket sized for the model account in section 4; SpicyStock places no order. "
            f"Order kind `{first.get('order_kind')}`: {first.get('order_kind_meaning')}. The record's action word is "
            f"{first.get('record_action_note')}. Where the buy stop is `equal` the last close, {BUY_STOP_NOTE}. "
            f"Price states are {first.get('price_states_note')}. The dated lines are the model's own schedule.")
        add("")
    for t in tickets:
        add(f"### {t.get('ticker')} · {t.get('stage')} · {t.get('grade')}" + (f" {_n(t.get('score'))}" if t.get("score") is not None else "")
            + f" · {TICKET}")
        add("")
        add(f"- Order as the record wrote it: `{t.get('order')}`")
        add("- " + _levels_line(_dict(t.get("levels")), False) + ".")
        oe = _dict(t.get("order_entry"))
        lines = _dict(oe.get("lines"))
        add(f"- Order entry: kind `{oe.get('order_kind')}`; {_n(oe.get('shares'))} shares; last close "
            f"{_usd(oe.get('last_close'))}; the buy stop is `{oe.get('buy_stop_vs_last_close')}` the last close"
            + "".join(f"; {name.replace('_', ' ')} {_usd(lines.get(name))}" for name in ("extended_above", "gap_ok_above")
                      if lines.get(name) is not None)
            + f"; record action word `{oe.get('record_action_word')}` (legacy).")
        add("- Price states: " + "; ".join(f"`{s.get('state')}` {_state_range(s)}" for s in _list(oe.get("price_states"))
                                             if s.get("applies")) + ".")
        note = _dict(oe.get("not_the_ticket"))
        for label, field in (("Open-entry note", "open_entry"), ("Reader's entry note", "reader_entry_note")):
            if note.get(field):
                add(f"- {label} (not the ticket): {note[field]}")
        for label, field in (("Limit", "limit_note"), ("Pre-open check", "pre_open_check"), ("Sizing", "sizing_note"), ("Resize", "resize_rule")):
            if t.get(field):
                add(f"- {label}: {t[field]}")
        for term in _list(t.get("order_terms")):
            add(f"- Term: {term}")
        for s in _list(t.get("schedule")):
            add(f"- Day {s.get('day')} ({s.get('date')}): {s.get('instruction')}")
        event = _dict(t.get("event"))
        add(f"- Event registry: {event.get('status') or 'not read'}.")
        earn = _dict(t.get("earnings"))
        add(f"- Earnings: {earn.get('sentence') or 'no row recorded'}")
        if earn.get("items_sentence"):
            add(f"- SEC current reports: {earn['items_sentence']}")
        add("")
    cands = _dict(brief.get("candidates"))
    detailed, compact_rows = _list(cands.get("detailed")), _list(cands.get("compact"))
    always = [r for r in detailed if r.get("class") in ("ticket", "reviewed")]
    others = [r for r in detailed if r.get("class") not in ("ticket", "reviewed")]
    k = len(others) if md_detail is None else min(md_detail, len(others))
    in_detail = always + others[:k]
    as_rows = [_compact_from_detailed(r) for r in others[k:]] + compact_rows
    m = len(as_rows) if md_compact is None else min(md_compact, len(as_rows))
    c = _dict(cands.get("counts"))
    section(6, f" ({_n(c.get('admitted_in_trade_band'))} of {_n(c.get('in_trade_band_no_veto'))} in the band; {_n(c.get('discovered'))} discovered)")
    add(f"Definition: {cands.get('definition')}. Order: {cands.get('order')}. Model status: {cands.get('model_status')}. "
        f"Later gates: {cands.get('would_pass_note')}.")
    add("")
    add("Checklist, the same thresholds for every name. " + " ".join(
        f"**{x.get('id')}** {x.get('label')}: {x.get('threshold')}" + (f" (weight {_n(x.get('weight'), 1)})." if x.get("weight") is not None else " (recorded, no weight).")
        for x in _list(cands.get("checklist"))))
    add(f"Check marks: {cands.get('check_marks')}.")
    add("")
    days = _list(cands.get("schedule_days"))
    add("Hold days for a plan entered on the applicable session: " + ", ".join(f"day {d.get('day')} = {d.get('date')}" for d in days) + ". "
        "The model's exit rules (source B Bonde, P this project, T a third party's test): "
        + " ".join(f"[{x.get('source')}] when {x.get('when')}: {x.get('rule')}." for x in _list(cands.get("exit_rules"))))
    add("")
    near_volume = _dict(cands.get("near_volume_boundary"))
    add(f"Page for any ticker here: {cands.get('link_pattern')} (setting-up names: the same with `setting-up` in place of `bursts`). "
        f"Near-volume band: {_n(near_volume.get('bursts_inside'))} of the discovered bursts have a volume within "
        f"{_short(near_volume.get('band'))} of the previous session's ({near_volume.get('meaning')}).")
    add("")
    add(f"### 6a. In detail ({len(in_detail)} of {len(detailed) + len(compact_rows)} listed: every ticket and reviewed name, then the first {k} others"
        + ("; reviewed names in their short form" if md_short else "") + ")")
    add("")
    for r in in_detail:
        L.extend(_candidate_md(r, md_short))
    add(f"### 6b. Compact rows ({m} shown; {len(as_rows) - m} left out of this file; brief.json carries every one)")
    add("")
    stage_counts: dict = {}
    for x in as_rows[:m]:
        stage_counts[x.get("stage")] = stage_counts.get(x.get("stage"), 0) + 1
    modal = max(stage_counts, key=lambda name: (stage_counts[name], str(name))) if stage_counts else None
    labels = _dict(_dict(brief.get("funnel")).get("labels"))
    add(f"Every row here is {RESEARCH_SHORT} (no SpicyStock ticket, no chart review). Research levels are derived from the "
        "recorded bar by the record's plan rules: `limit` is the "
        "highest fill the plan permits; stop basis L is the burst day's low, M the bar's midpoint; the day-2 line (too extended to enter) is the "
        "trigger plus the archived entry_above_pct and the skip-under line the trigger minus entry_below_pct (both exact in brief.json); `shares` "
        "is the model size under tonight's regime multiplier, then the same plan at full size; `refused` means the plan rule refused it; "
        "`*` after the volume ratio marks the near-volume band. "
        + (f"Every row stopped at stage `{modal}` ({labels.get(modal) or 'no label recorded'}) unless its ticker carries another in brackets. " if modal else "")
        )
    add("")
    if m:
        L.extend(_table(COMPACT_HEADER, [_compact_md_row(x, modal) for x in as_rows[:m]]))
        add("")
    tail = _dict(brief.get("research_tail"))
    section(7, f" ({_n(tail.get('total'))} names)")
    add(str(tail.get("meaning")) + ".")
    add("")
    budget_left = TAIL_MAX if md_tail is None else md_tail
    hidden = 0
    for g in _list(tail.get("groups")):
        names = _list(g.get("tickers"))
        shown = names[:max(0, budget_left)]
        budget_left -= len(shown)
        hidden += len(names) - len(shown)
        add(f"- {g.get('reason')} ({_n(g.get('count'))}): " + (", ".join(str(n) for n in shown) if shown else "not listed here")
            + (f" … and {len(names) - len(shown)} more" if len(shown) < len(names) and shown else ""))
    if tail.get("left_out") or hidden:
        add(f"- Not named here: {_n((tail.get('left_out') or 0) + hidden)} of these, the lowest by rank; brief.json names {_n(sum(len(_list(g.get('tickers'))) for g in _list(tail.get('groups'))))} and the canonical record carries every one.")
    add("")
    su = _dict(brief.get("setting_up"))
    counts = _dict(su.get("counts"))
    section(8, f" (anticipation): {_n(counts.get('top'))} listed, {_n(counts.get('also_quiet'))} also quiet")
    add(f"Of {_n(counts.get('momentum'))} momentum names, {_n(counts.get('quiet'))} quiet, {_n(counts.get('admitted'))} pass the coil checks. "
        + (f"The record's own sentence over its list (the model's rule, not an instruction to the reader): \"{su.get('instruction')}\"" if su.get("instruction") else ""))
    add("")
    for r in _list(su.get("listed")):
        ms, box = _dict(r.get("measured")), _dict(r.get("box"))
        is_ticket = bool(r.get("ticket"))
        add(f"### {r.get('ticker')} · " + (f"{r['name']} · " if r.get("name") else "") + f"listed {r.get('rank')} · "
            + (f"{TICKET} (order and schedule in section 5)" if is_ticket else RESEARCH_ONLY))
        add("")
        add(f"- Measured: close {_usd(ms.get('close'))} ({_n(ms.get('pct_change_today'))}% today); setups {', '.join(_list(r.get('setups')))}; "
            f"compress {_n(ms.get('compress'))}, tight days {_n(ms.get('tight_n'))}, quiet days {_n(ms.get('quiet_days'))}, volume ratio {_n(ms.get('volume_ratio'))}, "
            f"ADR {_n(ms.get('adr20_pct'), 1)}%, extension {_n(ms.get('extension'))}; box {_usd(box.get('low'))} to {_usd(box.get('high'))} over {_n(box.get('sessions'))} sessions "
            f"({box.get('start')} to {box.get('end')}).")
        if is_ticket:
            add("- Its order, levels, event state and earnings warning are in section 5.")
            add("")
            continue
        lv = _dict(_row_levels(r))
        add("- " + (_levels_line(lv, True) if lv else "levels: no plan recorded") + ".")
        if r.get("why_no_ticket"):
            add(f"- No ticket: {r['why_no_ticket']} (stage `{r.get('stage')}`).")
        if _dict(r.get("open_entry_note")).get("text"):
            add(f"- Open-entry note (not the ticket): {r['open_entry_note']['text']}")
        event = _dict(r.get("event"))
        add(f"- Event registry: {event.get('status') or 'not read'}"
            + (f": {_stop(event['reason'])}" if event.get("reason") and event.get("reason") != r.get("why_no_ticket") else "")
            + ("; review overdue" if event.get("review_overdue") else "") + ".")
        earn = _dict(r.get("earnings"))
        if earn:
            add(f"- Earnings: {earn.get('sentence')}")
            if earn.get("items_sentence"):
                add(f"- SEC current reports: {earn['items_sentence']}")
        add("")
    quiet = _list(su.get("also_quiet"))
    if quiet:
        add(f"Also quiet (not listed; no plan; every row {RESEARCH_ONLY}):")
        add("")
        L.extend(_table(("ticker", "setups", "close", "compress", "tight", "vol ratio", "trigger", "stop", "risk %", "why not listed"),
                        [(q.get("ticker"), "/".join(_list(q.get("setups"))), _n(q.get("close")), _n(q.get("compress")), _n(q.get("tight_n")),
                          _n(q.get("volume_ratio")), _n(q.get("trigger")), _n(q.get("stop")), _n(q.get("risk_pct"), 1), q.get("why")) for q in quiet]))
        add("")
    plans = _dict(brief.get("open_plans"))
    section(9, f" ({_n(plans.get('total'))})")
    add(str(plans.get("meaning")) + ".")
    add("")
    for o in _list(plans.get("rows")):
        add(f"- **{o.get('ticker')}** ({o.get('kind')}, picked {o.get('picked')}, {o.get('regime')}): status `{o.get('status')}`"
            + (f", uncertainty `{o.get('uncertainty')}`" if o.get("uncertainty") else "")
            + f", day {_n(o.get('day'))}; trigger {_usd(o.get('entry_ref'))}, limit {_usd(o.get('limit'))}, stop {_usd(o.get('current_stop'))}; "
            f"{_n(o.get('shares'))} shares ({_n(o.get('remaining'))} remaining); last close {_usd(o.get('last_close'))} on {o.get('last_date')}"
            + (f"; result {_n(o.get('result_pct'))}%" if o.get("result_pct") is not None else "") + f". {o.get('instruction') or ''}")
    if plans.get("rows_left_out"):
        add(f"- Left out: {plans['rows_left_out']} more open model plans.")
    add("")
    sc = _dict(brief.get("scorecard"))
    section(10)
    add(f"- Scorecard: {_n(sc.get('plans'))} plans in {_n(sc.get('sessions'))} sessions ({_dict(sc.get('population')).get('from')} to {_dict(sc.get('population')).get('through')}): "
        f"{_n(sc.get('settled'))} settled ({_n(sc.get('wins'))} wins, {_n(sc.get('losses'))} losses, {_n(sc.get('breakeven'))} even), "
        f"{_n(sc.get('open'))} open, {_n(sc.get('pending'))} pending, {_n(sc.get('uncertain'))} uncertain, {_n(sc.get('not_filled'))} not filled, "
        f"{_n(sc.get('unmeasured'))} unmeasured; sum of R {_n(sc.get('sum_r'))}.")
    add(f"- Readable as a rate: **{_n(sc.get('readable'))}** (needs {_n(sc.get('min_read'))} settled); win rate {_n(sc.get('win_rate'))}, "
        f"average R {_n(sc.get('avg_r'))}, median R {_n(sc.get('median_r'))}. These are model plans walked on bars, not trades, and no edge is established.")
    if sc.get("note"):
        add(f"- How it is counted: {sc['note']}")
    L.extend(_model_md(_dict(brief.get("model_record")), md_model_tables))
    led = _dict(brief.get("pick_ledger"))
    if led:
        add(f"- Pick ledger (picks.json): {_n(led.get('retained'))} picks over {_n(led.get('distinct_tickers'))} distinct tickers; repeated: "
            + (", ".join(f"{t} x{n}" for t, n in _dict(led.get("repeated")).items()) or "none")
            + "; by kind " + ", ".join(f"{k} {v}" for k, v in _dict(led.get("by_kind")).items())
            + "; by regime at the pick " + ", ".join(f"{k} {v}" for k, v in _dict(led.get("by_regime")).items())
            + f"; picks in the scorecard window {_n(led.get('in_scorecard_window'))} against {_n(led.get('scorecard_plans'))} plans counted. {led.get('note')}")
        L.append("")
        L.extend(_table(("picked", "ticker", "kind", "regime", "shares", "trigger", "limit", "stop"),
                        [(p.get("date"), p.get("ticker"), p.get("kind"), p.get("regime"), _n(p.get("shares")),
                          _n(p.get("trigger")), _n(p.get("limit")), _n(p.get("stop"))) for p in _list(led.get("rows"))]))
        if led.get("rows_left_out"):
            add(f"\n{led['rows_left_out']} older picks left out ({led.get('rows_rule')}).")
    add("")
    ev = _dict(brief.get("events"))
    reg = _dict(ev.get("registry"))
    section(11)
    add(f"- {ev.get('sentence')}")
    if reg:
        add("- Entries: " + "; ".join(f"{e.get('symbol')} ({e.get('kind')}, announced {e.get('announced_on')}, review due {e.get('review_due')}"
                                       + (f", ended {e.get('active_until')}" if e.get("active_until") else "") + ")" for e in _list(reg.get("events"))) + ".")
    for match in _list(ev.get("listed_matches")):
        add(f"- Listed and in the registry: **{match.get('ticker')}** ({str(match.get('stage')).replace('_', ' ')}, `{match.get('status')}`"
            + ("" if match.get("flagged_in_the_record") else ", not flagged on its row in the record") + f"): {match.get('reason')}"
            + "".join(f" Source: {s.get('title')} ({s.get('published_on')}) {s.get('url')}." for s in _list(match.get("sources"))))
    add("- Status words: " + "; ".join(f"`{k}` = {v}" for k, v in _dict(ev.get("status_words")).items()) + ".")
    earn = _dict(ev.get("earnings"))
    add(f"- Earnings and 8-K check: status `{earn.get('status')}`; {_n(earn.get('ticket_rows'))} ticket rows; "
        f"{_n(earn.get('listed_names_not_checked'))} of {_n(earn.get('listed_names'))} listed names had no check at all.")
    add("- Not checked by SpicyStock: " + ", ".join(_list(ev.get("not_checked"))) + ".")
    add("")
    section(12)
    rules = _dict(brief.get("rules"))
    add(f"- Rules digest `{rules.get('digest')}`; without the universe membership identity `{rules.get('digest_without_membership')}` "
        f"(membership identity `{rules.get('membership_identity')}`): {rules.get('digest_note')}.")
    for family, values in _dict(rules.get("selected")).items():
        add(f"- {family}: " + ", ".join(f"{k} {json.dumps(v)}" for k, v in _dict(values).items()))
    add("")
    b = _dict(brief.get("bounds"))
    section(13)
    add(f"- brief.json: {b.get('candidates_detailed')} candidates in detail, {b.get('candidates_compact')} compact, "
        f"{b.get('candidates_moved_to_tail')} moved to the tail for size. {b.get('candidates_rule')}.")
    add(f"- This file: {len(in_detail)} in detail, {m} compact rows, {len(as_rows) - m} compact rows left out, {_n(hidden)} research-tail names not "
        f"named; reviewed names in their short form: {_n(md_short)}; model-record tables printed: {_n(md_model_tables)}. Rule: tickets and "
        f"reviewed names always in detail; then, to stay within {MAX_MD_BYTES} bytes, the model-record tables are given up first, then the "
        f"other names' detail (largest multiple of {MD_DETAIL_STEP} that fits), then tail names "
        f"(multiple of {MD_TAIL_STEP}), then the reviewed names' check measurements and all but a cut reason of their reader sentences (the "
        f"short form), then compact rows (multiple of {MD_COMPACT_STEP}); brief.json carries what this file leaves out.")
    add(f"- Research tail: {b.get('research_tail_named')} named, {b.get('research_tail_left_out')} left out ({b.get('research_tail_rule')}). "
        f"Open plans left out: {b.get('open_plans_left_out')}. Stale names left out: {b.get('stale_names_left_out')}. "
        f"{b.get('model_record_rule')}. {b.get('text_rule')}.")
    add("")
    section(14)
    for limit in _list(brief.get("limits")):
        add(f"- {limit}")
    add("")
    return ("\n".join(L)).encode("utf-8")


def fit_md(brief: dict, json_raw: bytes) -> bytes:
    """Tickets and reviewed names are always in detail. Given up in this order until the file fits: the
    model-record tables (its sentences stay), the other names' detail (they become compact rows), the research
    tail's names (its counts stay), the reviewed names' check measurements and all but a cut reason of their reader
    sentences (their short form), compact rows."""
    cands = _dict(brief.get("candidates"))
    others = sum(1 for r in _list(cands.get("detailed")) if r.get("class") not in ("ticket", "reviewed"))
    rows = others + len(_list(cands.get("compact")))
    tail = sum(len(_list(g.get("tickers"))) for g in _list(_dict(brief.get("research_tail")).get("groups")))

    whole = render_markdown(brief, json_raw, others, rows, tail, False, True)
    if len(whole) <= MAX_MD_BYTES:
        return whole

    def render(detail, compact_n, tail_n, short=False):
        return render_markdown(brief, json_raw, detail, compact_n, tail_n, short, False)
    detail = _largest(others, MD_DETAIL_STEP, lambda n: len(render(n, rows, tail)) <= MAX_MD_BYTES)
    if detail is not None:
        return render(detail, rows, tail)
    tail_n = _largest(tail, MD_TAIL_STEP, lambda n: len(render(0, rows, n)) <= MAX_MD_BYTES)
    if tail_n is not None:
        return render(0, rows, tail_n)
    compact_n = _largest(rows, MD_COMPACT_STEP, lambda n: len(render(0, n, 0, True)) <= MAX_MD_BYTES)
    if compact_n is None:
        raise DoesNotFit(f"brief.md does not fit {MAX_MD_BYTES} bytes at its smallest row bounds")
    return render(0, compact_n, 0, True)


def derive(canonical_raw: bytes, picks_raw: bytes | None = None, model_record=None) -> tuple:
    """(brief.json bytes, brief.md bytes) from the canonical record bytes, the
    picks.json bytes and the optional carried model-record block. Pure: the
    same three inputs give the same bytes, with no clock, no network and no
    other file."""
    from src import admission, event_risk, plan      # lazy: the publication gate imports this module without them
    data = _decode(canonical_raw, MAX_SOURCE_BYTES)
    if not (isinstance(data, dict) and data.get("schema_version") == 2 and isinstance(data.get("run"), dict)
            and isinstance(data.get("bursts"), list)):
        raise Refusal("the publication is not a schema-2 record this brief can read")
    picks = _decode(picks_raw, MAX_PICKS_BYTES) if picks_raw is not None else None
    modules = {"plan": plan, "event_risk": event_risk, "admission": admission}

    def fitted(block):
        json_raw = fit_json(build(data, picks, canonical_raw, picks_raw, modules, block))
        return json_raw, fit_md(json.loads(json_raw), json_raw)
    try:
        return fitted(model_record)
    except DoesNotFit:
        if model_block(model_record, data).get("status") not in MODEL_CARRIED:
            raise
        return fitted(not_computed(NOT_CARRIED_ROOM))    # the night keeps its brief; the file says what it lacks


def unavailable(canonical_raw: bytes, picks_raw: bytes | None, why: str) -> tuple:
    """The pair written when derivation fails: bound to the bytes, saying so, never a stale brief."""
    brief = {"schema": SCHEMA, "version": VERSION, "status": "unavailable",
             "reason": f"the brief could not be derived from this publication ({why}); the canonical record is unaffected",
             "read_first": list(READ_FIRST),
             "identity": {"canonical": {"path": DATA_FILE, "sha256": _hash(canonical_raw), "bytes": len(canonical_raw)},
                          "picks": ({"path": PICKS_FILE, "sha256": _hash(picks_raw), "bytes": len(picks_raw)}
                                    if picks_raw is not None else None),
                          "urls": {"page": SITE_URL, "record": SITE_URL + DATA_FILE}},
             "limits": list(LIMITS)}
    json_raw = _encode(brief)
    md = (f"# SpicyStock daily brief: unavailable\n\n> {brief['reason']}. Nothing in this file is a ticket or a "
          f"candidate; read the page or the record.\n\n- Canonical record `data.json`: "
          f"{len(canonical_raw):,} bytes, SHA-256 `{_hash(canonical_raw)}`.\n- This file renders `brief.json` "
          f"({len(json_raw):,} bytes, SHA-256 `{_hash(json_raw)}`).\n- Page {SITE_URL}\n")
    return json_raw, md.encode("utf-8")


def compose(canonical_raw: bytes, picks_raw: bytes | None = None, model_record=None) -> tuple:
    """(brief.json bytes, brief.md bytes, why): the derived pair with ``why``
    None, or the `unavailable` pair bound to the same bytes and the reason it
    carries. A refusal's own fixed words are printed; any other failure is
    named by its type alone, never by an exception's text."""
    try:
        json_raw, md_raw = derive(canonical_raw, picks_raw, model_record)
        return json_raw, md_raw, None
    except Refusal as exc:
        why = str(exc)
    except Exception as exc:  # noqa: BLE001 -- named in the file and the log; the record is unaffected
        why = type(exc).__name__
    json_raw, md_raw = unavailable(canonical_raw, picks_raw, why)
    return json_raw, md_raw, why


MD_BINDING = re.compile(rb"This file renders `brief\.json` \(([0-9,]+) bytes, SHA-256 `([a-f0-9]{64})`\)")
MD_CANONICAL = re.compile(rb"Canonical record `data\.json`: ([0-9,]+) bytes, SHA-256 `([a-f0-9]{64})`")


def validate_binding(canonical_raw: bytes, picks_raw: bytes | None, json_raw: bytes, md_raw: bytes) -> dict:
    """What the publication gate holds, with the standard library alone: the byte bounds, the envelope, and the
    three hashes that tie brief.md to brief.json and brief.json to the committed record and picks.

    It deliberately compares nothing against this module's own text or version (the limits, the renderer): the
    pair on main was written by the code of the last evening run, and a merge that rewords a sentence must not
    turn the gate red until the next run. Byte-for-byte re-derivation is `validate()`."""
    _require(isinstance(json_raw, bytes) and 0 < len(json_raw) <= MAX_JSON_BYTES, "brief.json exceeds its byte bound")
    _require(isinstance(md_raw, bytes) and 0 < len(md_raw) <= MAX_MD_BYTES, "brief.md exceeds its byte bound")
    brief = _decode(json_raw, MAX_JSON_BYTES)
    _require(isinstance(brief, dict) and brief.get("schema") == SCHEMA and type(brief.get("version")) is int
             and 1 <= brief["version"] <= VERSION and brief.get("status") in ("derived", "unavailable"),
             "unsupported brief")
    canon = _dict(_dict(brief.get("identity")).get("canonical"))
    _require(canon.get("sha256") == _hash(canonical_raw) and canon.get("bytes") == len(canonical_raw),
             "brief.json is bound to another canonical publication")
    picks = _dict(brief.get("identity")).get("picks")
    _require((picks is None) == (picks_raw is None), "brief.json and picks.json disagree about picks")
    if picks_raw is not None:
        _require(_dict(picks).get("sha256") == _hash(picks_raw) and _dict(picks).get("bytes") == len(picks_raw),
                 "brief.json is bound to another picks.json")
    _require(_encode(brief) == json_raw, "brief.json is not in its canonical encoding")
    found = MD_BINDING.search(md_raw)
    _require(found is not None and found.group(2).decode() == _hash(json_raw)
             and int(found.group(1).replace(b",", b"")) == len(json_raw), "brief.md does not render this brief.json")
    found = MD_CANONICAL.search(md_raw)
    _require(found is not None and found.group(2).decode() == canon["sha256"], "brief.md names another publication")
    return brief


def validate(canonical_raw: bytes, picks_raw: bytes | None, json_raw: bytes, md_raw: bytes) -> dict:
    """The full check, where the repository's dependencies are installed (the
    tests, ``python -m src.brief --check``): the binding, then byte-for-byte
    re-derivation of both files with the model-record block the file itself
    carries. A carried block that disagrees with the record's scorecard does
    not survive it: ``model_block()`` replaces such a block with its reason,
    so the re-derived file differs."""
    brief = validate_binding(canonical_raw, picks_raw, json_raw, md_raw)
    _require(brief["version"] == VERSION and list(brief.get("limits") or []) == list(LIMITS), "brief limits differ")
    carried = brief.get("model_record") if brief["status"] == "derived" else None
    expected_json, expected_md, _ = compose(canonical_raw, picks_raw, carried)
    _require(json_raw == expected_json, "brief.json differs from its derivation")
    _require(md_raw == expected_md, "brief.md differs from its derivation")
    return brief


def _regular(path, maximum: int) -> bytes:
    from pathlib import Path
    path = Path(path)
    _require(not path.is_symlink() and path.is_file(), "brief asset must be a regular file")
    with path.open("rb") as handle:
        raw = handle.read(maximum + 1)
    _require(len(raw) <= maximum, "brief asset bytes exceed bound")
    return raw


def write_publication(canonical_raw: bytes, picks_raw: bytes | None, docs, model_record=None) -> dict:
    """Derive both files from the final installed bytes and install them together.

    A derivation that fails for any reason installs the `unavailable` pair bound to the same bytes, so the public
    brief is never a stale one that reads as current. Both files are staged beside docs/, read back and validated
    before either is installed; an ordinary rename failure restores the previous pair. Process death between the
    two renames is the same multi-file limitation the reader companions have. Returns what the run log says."""
    import os
    import tempfile
    from pathlib import Path
    docs = Path(docs)
    json_raw, md_raw, failure = compose(canonical_raw, picks_raw, model_record)
    names = (MD_FILE, JSON_FILE)                    # brief.json last: it is the file the Markdown is bound to
    with tempfile.TemporaryDirectory(prefix=".brief-", dir=docs) as tmp:
        stage = Path(tmp)
        for name, raw in ((JSON_FILE, json_raw), (MD_FILE, md_raw)):
            with (stage / name).open("wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        validate_binding(canonical_raw, picks_raw, _regular(stage / JSON_FILE, MAX_JSON_BYTES),
                         _regular(stage / MD_FILE, MAX_MD_BYTES))
        previous = {}
        for name in names:
            target = docs / name
            _require(not target.is_symlink(), "brief target must not be a symlink")
            previous[name] = target.read_bytes() if target.exists() else None
        installed = []
        try:
            for name in names:
                os.replace(stage / name, docs / name)
                installed.append(name)
        except OSError:
            for name in reversed(installed):
                if previous[name] is None:
                    (docs / name).unlink()
                else:
                    (stage / name).write_bytes(previous[name])
                    os.replace(stage / name, docs / name)
            raise
    brief = json.loads(json_raw)
    bounds = _dict(brief.get("bounds"))
    model = _dict(brief.get("model_record"))
    sizes = (f"brief.json {len(json_raw)} of {MAX_JSON_BYTES} bytes, brief.md {len(md_raw)} of {MAX_MD_BYTES} bytes")
    return {"status": brief["status"], "failure": failure, "json_bytes": len(json_raw), "md_bytes": len(md_raw),
            "model_record": model.get("status"), "model_record_reason": model.get("reason"),
            "sentence": (f"{sizes}; {bounds.get('candidates_detailed')} candidates in detail, "
                         f"{bounds.get('candidates_compact')} compact, {bounds.get('candidates_moved_to_tail')} moved "
                         f"to the tail; model record {model.get('status')}"
                         + (f" ({model.get('reason')})" if model.get("reason") else "")
                         if failure is None else
                         f"unavailable ({failure}); {sizes}; the pair says so and is bound to this record")}


def check_assets(docs, *, rederive: bool = True) -> dict:
    """Check the committed pair against the committed record; nothing is repaired."""
    from pathlib import Path
    docs = Path(docs)
    canonical_raw = _regular(docs / DATA_FILE, MAX_SOURCE_BYTES)
    picks_path = docs / PICKS_FILE
    picks_raw = _regular(picks_path, MAX_PICKS_BYTES) if picks_path.exists() else None
    json_raw, md_raw = _regular(docs / JSON_FILE, MAX_JSON_BYTES), _regular(docs / MD_FILE, MAX_MD_BYTES)
    return (validate if rederive else validate_binding)(canonical_raw, picks_raw, json_raw, md_raw)


def main(argv=None) -> int:
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Derive the analyst's daily brief from a docs directory's record.")
    parser.add_argument("--docs", default="docs", help="the directory holding data.json and picks.json")
    parser.add_argument("--check", action="store_true",
                        help="hold the committed pair to its derivation; write nothing")
    args = parser.parse_args(argv)
    docs = Path(args.docs)
    try:
        if args.check:
            brief = check_assets(docs)
            print(f"brief current: status {brief['status']}, bound to data.json {brief['identity']['canonical']['sha256']}")
            return 0
        canonical_raw = _regular(docs / DATA_FILE, MAX_SOURCE_BYTES)
        picks_path = docs / PICKS_FILE
        picks_raw = _regular(picks_path, MAX_PICKS_BYTES) if picks_path.exists() else None
        result = write_publication(canonical_raw, picks_raw, docs)
    except (OSError, ValueError) as exc:
        print(f"brief: {exc}", file=sys.stderr)
        return 1
    print(f"brief: {result['sentence']}")
    return 0 if result["status"] == "derived" else 2


if __name__ == "__main__":
    raise SystemExit(main())
