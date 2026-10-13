"""Reproduce reported trade results from a private backup, and trace each one to
the publication it came from (#110).

The Morning desk keeps the owner's broker reports in that browser only, and
*Download private backup* writes the exact stored bytes. This reads that file,
on the owner's machine (it is never committed), and for every record:

- re-derives the completed result the page prints -- gross, actual costs, net,
  and the part of a loss past the frozen protective stop -- in exact integer
  millionths of a dollar, by the page's own rules (`completedResult()` and
  `beyondStop()` in docs/app-handoff.js), and refuses a record the page's own
  validation (`validItem()`) would refuse;
- traces it to the publication it was prepared from: the record whose bytes
  hash to the SHA-256 it froze, found among --publication files or in this
  checkout's history of docs/data.json (--git), and in it the plan whose
  evidence reference, order, entry window and exit schedule are the ones frozen
  (an independent research report: the setting-up row whose evidence it names);
- puts the model's own outcome for that plan beside it, read off the newest
  supplied publication after the plan's session whose open model plans carry
  the same evidence reference: a daily-bar replay of the published plan at its
  published quantity, never added to the reported result.

It writes nothing but an explicit --json, makes no network request and decides
nothing. A reported result is the owner's account of the broker's records,
which nothing here verifies.

    python tools/private_results.py BACKUP.json --git
    python tools/private_results.py BACKUP.json --publication data.json [--publication later.json]

Exit 0: every record re-derived and, where a publication source was given,
traced. Exit 1: a record whose publication was not found, or whose frozen plan
is not the publication's. Exit 2: the backup is not one the page would accept.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = "private_results"
VERSION = 1
RECORD_PATH = "docs/data.json"

# The page's own bounds (docs/app-handoff.js).
STORE_VERSIONS = {1, 2, 3}
MAX_ITEMS = 100
MAX_BYTES = 1048576
MAX_SHARES = 1000000
MAX_CENTS = 2**53 - 1
GIT_LIMIT = 256

LEGACY_FIELDS = ("submitted_quantity", "submitted_at", "filled_quantity", "average_price", "filled_at",
                 "cancelled_quantity", "cancelled_at", "exited_quantity", "exited_at",
                 "protected_quantity", "protection_confirmed_at")
RESULT_FIELDS = ("average_exit_price", "entry_fees", "exit_fees")
QUANTITIES = ("submitted_quantity", "filled_quantity", "cancelled_quantity", "exited_quantity", "protected_quantity")
TIMES = ("submitted_at", "filled_at", "cancelled_at", "exited_at", "protection_confirmed_at")
REFERENCE_KEYS = ("version", "id", "context_sha256", "plan_sha256", "pick_sha256")
TIMING_KEYS = ("applicable_session", "opens_at", "cutoff_at", "closes_at")
MODEL_FIELDS = ("status", "day", "sessions", "shares", "fill", "uncertainty", "exit_price", "result_pct",
                "half_sold", "sold", "remaining", "last_date")
KINDS = ("planned_handoff", "independent_research")

HEX = re.compile(r"[a-f0-9]{64}")
RULES = re.compile(r"[a-f0-9]{12}")
DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
SYMBOL = re.compile(r"[A-Z][A-Z0-9.-]{0,14}")
PRICE = re.compile(r"(\d{1,10})(?:\.(\d{1,6}))?")
FEE = re.compile(r"(\d+)\.(\d{2})")
STORED_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")
# Source clocks keep their upstream spelling (microseconds, offsets).
SOURCE_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d{1,6})?)?(?:Z|[+-](?:0\d|1[0-4]):[0-5]\d)")
RUN_ID = re.compile(r"[A-Za-z0-9_-]{1,100}")
SCHEDULE_KEY = re.compile(r"[a-z0-9_]{1,80}")


class Refused(ValueError):
    """The backup is not one the page would accept; nothing is re-derived."""


# --- the page's rules -------------------------------------------------------

def _keys(value, keys) -> bool:
    return isinstance(value, dict) and set(value) == set(keys) and len(value) == len(keys)


def _int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _date(value) -> bool:
    if not isinstance(value, str) or not DAY.fullmatch(value):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _instant(value, pattern=STORED_TIME):
    """A stored clock as an aware datetime, or None."""
    if not isinstance(value, str) or not pattern.fullmatch(value) or not _date(value[:10]):
        return None
    text = value.replace("Z", "+00:00")
    text = re.sub(r"(\.\d{3})\d{1,3}(?=[+-])", r"\1", text)
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def micros(price: str) -> int:
    """A stored decimal price as exact millionths of a dollar."""
    whole, _, part = price.partition(".")
    return int(whole) * 1_000_000 + int(part.ljust(6, "0") or "0")


def _price(value) -> bool:
    """The page's stored average price: positive, at most six places, canonical."""
    if not isinstance(value, str):
        return False
    match = PRICE.fullmatch(value)
    if not match or micros(value) <= 0:
        return False
    whole, part = match.group(1), (match.group(2) or "").rstrip("0")
    return value == str(int(whole)) + ("." + part if part else "")


def _fee(value) -> bool:
    """The page's stored fee: cents, always two places."""
    match = FEE.fullmatch(value) if isinstance(value, str) else None
    return bool(match) and value == str(int(match.group(1))) + "." + match.group(2) and fee_cents(value) <= MAX_CENTS


def fee_cents(value: str) -> int:
    whole, cents = value.split(".")
    return int(whole) * 100 + int(cents)


def _cents(value) -> int | None:
    """An order price in whole cents, or None when it has finer precision."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not value > 0:
        return None
    text = repr(float(value))
    match = re.fullmatch(r"(\d+)(?:\.(\d{1,2}))?", text.removesuffix(".0") if text.endswith(".0") else text)
    if not match:
        return None
    return int(match.group(1)) * 100 + int((match.group(2) or "").ljust(2, "0"))


def report_problem(report, version: int) -> str | None:
    """Why a stored report is not one the page's normalizeReport() writes."""
    fields = LEGACY_FIELDS if version == 1 else LEGACY_FIELDS + RESULT_FIELDS
    if not _keys(report, fields):
        return "report fields"
    for key in QUANTITIES:
        value = report[key]
        if value is not None and not (_int(value) and 0 <= value <= MAX_SHARES):
            return key
    for key in ("average_price",) + (("average_exit_price",) if version >= 2 else ()):
        if report[key] is not None and not _price(report[key]):
            return key
    if version >= 2:
        for key in ("entry_fees", "exit_fees"):
            if report[key] is not None and not _fee(report[key]):
                return key
    times = {}
    for key in TIMES:
        if report[key] is not None:
            times[key] = _instant(report[key])
            if times[key] is None:
                return key
    submitted, filled = report["submitted_quantity"], report["filled_quantity"]
    cancelled, exited = report["cancelled_quantity"], report["exited_quantity"]
    if submitted is None and (filled is not None or cancelled is not None):
        return "fills or cancellations without a submitted quantity"
    if submitted is not None and ((filled is not None and filled > submitted) or (cancelled is not None and cancelled > submitted)
                                  or (filled is not None and cancelled is not None and filled + cancelled > submitted)):
        return "filled plus cancelled exceeds submitted"
    if exited is not None and (filled is None or exited > filled):
        return "exited exceeds filled"
    if version >= 2 and report["average_exit_price"] is not None and not exited:
        return "an exit price without an exit"
    if ((report["submitted_at"] and not submitted) or ((report["average_price"] is not None or report["filled_at"]) and not filled)
            or (report["cancelled_at"] and not cancelled) or (report["exited_at"] and not exited)
            or (report["protection_confirmed_at"] and report["protected_quantity"] is None)):
        return "a price or time without its quantity"
    sub = times.get("submitted_at")
    for key in ("filled_at", "cancelled_at", "exited_at"):
        if key in times and sub and times[key] < sub:
            return key + " before the submission"
    if "cancelled_at" in times and "filled_at" in times and times["cancelled_at"] < times["filled_at"]:
        return "the cancellation before the latest fill"
    if exited and exited == filled and "exited_at" in times and "filled_at" in times and times["exited_at"] < times["filled_at"]:
        return "a complete exit before the latest fill"
    return None


def reported(item) -> bool:
    return item["report_updated_at"] is not None or any(value is not None for value in item["report"].values())


def _order_problem(order, ticker) -> str | None:
    if not _keys(order, ("symbol", "action", "quantity", "order_type", "stop_price", "limit_price", "time_in_force", "conditional", "then")):
        return "plan.order"
    then = order["then"]
    if not _keys(then, ("action", "quantity", "order_type", "stop_price", "time_in_force")):
        return "plan.order.then"
    trigger, limit, stop = _cents(order["stop_price"]), _cents(order["limit_price"]), _cents(then["stop_price"])
    if (not isinstance(order["symbol"], str) or not SYMBOL.fullmatch(order["symbol"]) or order["symbol"] != ticker
            or order["action"] != "buy" or order["order_type"] != "stop_limit" or order["time_in_force"] != "day"
            or order["conditional"] != "one_triggers_the_other" or then["action"] != "sell" or then["order_type"] != "stop"
            or then["time_in_force"] != "gtc" or not _int(order["quantity"]) or not 1 <= order["quantity"] <= MAX_SHARES
            or then["quantity"] != order["quantity"] or None in (trigger, limit, stop) or not stop < trigger <= limit):
        return "plan.order"
    return None


def _planned_problem(item) -> str | None:
    pub, plan, draft = item["publication"], item["plan"], item["draft"]
    if (not _keys(pub, ("sha256", "session", "published_at", "rules_version")) or not isinstance(pub["sha256"], str)
            or not HEX.fullmatch(pub["sha256"]) or not _date(pub["session"]) or _instant(pub["published_at"], SOURCE_TIME) is None
            or not isinstance(pub["rules_version"], str) or not RULES.fullmatch(pub["rules_version"])):
        return "publication"
    if not _keys(plan, ("reference", "ticker", "stage", "order", "timing", "exit_schedule")):
        return "plan"
    ref = plan["reference"]
    if not _keys(ref, REFERENCE_KEYS) or ref["version"] != 1 or not all(isinstance(ref[k], str) and HEX.fullmatch(ref[k]) for k in REFERENCE_KEYS[1:]):
        return "plan.reference"
    if plan["stage"] not in ("bursts", "setting-up") or not isinstance(plan["ticker"], str):
        return "plan.stage"
    problem = _order_problem(plan["order"], plan["ticker"])
    if problem:
        return problem
    timing = plan["timing"]
    if not _keys(timing, TIMING_KEYS) or not _date(timing["applicable_session"]):
        return "plan.timing"
    clocks = [_instant(timing[key], SOURCE_TIME) for key in TIMING_KEYS[1:]]
    if None in clocks or not clocks[0] < clocks[1] <= clocks[2]:
        return "plan.timing"
    rows = plan["exit_schedule"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 20 or not all(
            _keys(row, ("day", "date", "key", "instruction")) and _int(row["day"]) and 0 < row["day"] <= 30 and _date(row["date"])
            and row["date"] >= timing["applicable_session"] and isinstance(row["key"], str) and SCHEDULE_KEY.fullmatch(row["key"])
            and isinstance(row["instruction"], str) and 0 < len(row["instruction"]) <= 2000 for row in rows):
        return "plan.exit_schedule"
    if item["id"] != pub["sha256"] + ":" + ref["id"]:
        return "id"
    if (not _keys(draft, ("quantity", "cash_cents", "fee_cents")) or not all(_int(draft[k]) and draft[k] >= 0 for k in draft)
            or not 1 <= draft["quantity"] <= plan["order"]["quantity"] or draft["cash_cents"] > MAX_CENTS or draft["fee_cents"] > MAX_CENTS
            or draft["quantity"] * _cents(plan["order"]["limit_price"]) + draft["fee_cents"] > draft["cash_cents"]):
        return "draft"
    return None


def _independent_problem(item) -> str | None:
    source = item["source"]
    if (not _keys(source, ("ticker", "stage", "publication", "cohort", "evidence", "baseline_admitted"))
            or not isinstance(source["ticker"], str) or not SYMBOL.fullmatch(source["ticker"]) or source["stage"] != "setting-up"
            or not isinstance(source["baseline_admitted"], bool)):
        return "source"
    pub = source["publication"]
    if (not _keys(pub, ("data_sha256", "context_sha256", "run_id", "rules_version", "measured_session", "applicable_session",
                        "published_at", "reader_projection_version", "reader_sha256"))
            or not all(isinstance(pub[k], str) and HEX.fullmatch(pub[k]) for k in ("data_sha256", "context_sha256", "reader_sha256"))
            or not isinstance(pub["run_id"], str) or not RUN_ID.fullmatch(pub["run_id"])
            or not isinstance(pub["rules_version"], str) or not RULES.fullmatch(pub["rules_version"])
            or not _date(pub["measured_session"]) or not _date(pub["applicable_session"])
            or _instant(pub["published_at"], SOURCE_TIME) is None or pub["reader_projection_version"] != 1):
        return "source.publication"
    cohort, evidence = source["cohort"], source["evidence"]
    if (not _keys(cohort, ("sha256", "bytes", "generated_at", "policy_id")) or not isinstance(cohort["sha256"], str)
            or not HEX.fullmatch(cohort["sha256"]) or not _int(cohort["bytes"]) or not 0 < cohort["bytes"] <= 128 * 1024
            or _instant(cohort["generated_at"], SOURCE_TIME) is None or cohort["policy_id"] != "anticipation_stop_width_4_to_5_v1"):
        return "source.cohort"
    if not _keys(evidence, ("id", "plan_sha256", "source_sha256", "inputs_sha256")) or not all(
            isinstance(v, str) and HEX.fullmatch(v) for v in evidence.values()):
        return "source.evidence"
    if item["id"] != pub["data_sha256"] + ":" + evidence["id"]:
        return "id"
    if item["report_updated_at"] is None:
        return "an independent report with no report"
    return None


def item_problem(item, version: int) -> str | None:
    """Why a stored record is not one the page's validItem() accepts."""
    if not isinstance(item, dict):
        return "record"
    kind = item.get("kind", "planned_handoff") if version == 3 else "planned_handoff"
    if kind not in KINDS:
        return "kind"
    fields = {"version", "id", "revision", "created_at", "updated_at", "report", "report_updated_at"}
    fields |= {"source"} if kind == "independent_research" else {"publication", "plan", "draft"}
    fields |= {"kind"} if version == 3 else set()
    if set(item) != fields:
        return "record fields"
    if item["version"] != version or not _int(item["revision"]) or item["revision"] < 1 or not isinstance(item["id"], str):
        return "record identity"
    created, updated = _instant(item["created_at"]), _instant(item["updated_at"])
    if created is None or updated is None or created > updated:
        return "record clocks"
    problem = report_problem(item["report"], version)
    if problem:
        return "report: " + problem
    if item["report_updated_at"] is None:
        if reported(item):
            return "reported facts without a report clock"
    else:
        at = _instant(item["report_updated_at"])
        if at is None or at > updated:
            return "report clock"
    return _independent_problem(item) if kind == "independent_research" else _planned_problem(item)


def load_backup(raw: bytes) -> dict:
    """The backup as the page's parseStore() reads it; Refused when it would not."""
    if not isinstance(raw, (bytes, bytearray)) or len(raw) > MAX_BYTES:
        raise Refused("the file exceeds the page's 1 MiB bound")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise Refused("the file begins with a byte-order mark the page does not write")
    try:
        store = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise Refused("the file is not UTF-8 JSON: " + str(error)[:80]) from None
    if not _keys(store, ("version", "items")) or store["version"] not in STORE_VERSIONS or not isinstance(store["items"], list):
        raise Refused("not a private-backup envelope of a version the page writes (1, 2 or 3)")
    if len(store["items"]) > MAX_ITEMS:
        raise Refused(f"more than {MAX_ITEMS} records")
    for index, item in enumerate(store["items"]):
        problem = item_problem(item, store["version"])
        if problem:
            raise Refused(f"record {index}: {problem}")
    ids = [item["id"] for item in store["items"]]
    if len(set(ids)) != len(ids):
        raise Refused("two records share one identity")
    if store["version"] < 3:
        # Read as the page normalizes it, never written back.
        for item in store["items"]:
            item["kind"] = "planned_handoff"
            if store["version"] == 1:
                item["report"].update({key: None for key in RESULT_FIELDS})
    return store


# --- the result, as the page derives it -------------------------------------

def dollars(cents: int) -> str:
    return "$" + f"{cents // 100:,}" + "." + f"{cents % 100:02d}"


def display(value: int) -> str:
    """The page's displayMicros(): cents half-up, the sign kept, <$0.01 for a non-zero amount."""
    magnitude = -value if value < 0 else value
    rounded = (magnitude + 5000) // 10000
    sign = "-" if value < 0 else ""
    if value != 0 and rounded == 0:
        return sign + "<$0.01"
    return sign + dollars(rounded)


def exact(value: int) -> str:
    """Millionths of a dollar as an exact decimal string."""
    sign = "-" if value < 0 else ""
    magnitude = -value if value < 0 else value
    return f"{sign}{magnitude // 1_000_000}.{magnitude % 1_000_000:06d}"


def completed_result(report) -> dict:
    """The page's completedResult(): a figure only for a fully exited, reconciled position."""
    reasons, missing = [], []
    if report["filled_quantity"] in (None, 0):
        missing.append("filled_quantity"); reasons.append("no positive entry fill is reported")
    if report["exited_quantity"] is None:
        missing.append("exited_quantity"); reasons.append("no exit quantity is reported")
    elif report["exited_quantity"] != report["filled_quantity"]:
        reasons.append("the position is not fully exited, so a partial exit's cost basis is not established")
    if report["submitted_quantity"] is None:
        missing.append("submitted_quantity"); reasons.append("no submitted quantity is reported")
    if report["cancelled_quantity"] is None:
        missing.append("cancelled_quantity"); reasons.append("no cancelled quantity is reported (0 when none were)")
    elif (report["filled_quantity"] is not None and report["submitted_quantity"] is not None
          and report["filled_quantity"] + report["cancelled_quantity"] != report["submitted_quantity"]):
        reasons.append("the submitted remainder is not reconciled")
    for key in ("average_price", "average_exit_price", "entry_fees", "exit_fees", "filled_at", "exited_at"):
        if report[key] is None:
            missing.append(key); reasons.append(key + " is not reported")
    if reasons:
        return {"state": "incomplete", "reasons": reasons, "missing": missing}
    quantity = report["filled_quantity"]
    gross = (micros(report["average_exit_price"]) - micros(report["average_price"])) * quantity
    costs = (fee_cents(report["entry_fees"]) + fee_cents(report["exit_fees"])) * 10_000
    net = gross - costs
    return {"state": "complete", "reasons": [], "missing": [], "quantity": quantity,
            "gross": exact(gross), "costs": exact(costs), "net": exact(net),
            "gross_microusd": gross, "costs_microusd": costs, "net_microusd": net,
            "outcome": "gain" if net > 0 else "loss" if net < 0 else "breakeven",
            "display": {"gross": display(gross), "costs": display(costs), "net": display(net)}}


def beyond_stop(item, result) -> dict | None:
    """The page's beyondStop(): an average exit under the frozen protective stop."""
    if item["kind"] != "planned_handoff" or result["state"] != "complete":
        return None
    stop = _cents(item["plan"]["order"]["then"]["stop_price"]) * 10_000
    exit_price = micros(item["report"]["average_exit_price"])
    if exit_price >= stop:
        return None
    per_share = stop - exit_price
    total = per_share * result["quantity"]
    return {"stop": exact(stop), "per_share": exact(per_share), "total": exact(total), "quantity": result["quantity"],
            "display": {"per_share": display(per_share), "total": display(total)}}


def draft_of(item) -> dict | None:
    """The draft's own arithmetic, as the page's cash preview computed it."""
    if item["kind"] != "planned_handoff":
        return None
    draft, order = item["draft"], item["plan"]["order"]
    limit, stop = _cents(order["limit_price"]), _cents(order["then"]["stop_price"])
    principal = draft["quantity"] * limit
    return {"quantity": draft["quantity"], "published_quantity": order["quantity"],
            "principal": dollars(principal), "fees_buffer": dollars(draft["fee_cents"]),
            "commitment": dollars(principal + draft["fee_cents"]), "risk_to_stop": dollars(draft["quantity"] * (limit - stop))}


# --- publications -----------------------------------------------------------

class Publication:
    """One record, hashed once. Its bytes are read again when needed rather
    than held, and a reading keeps only the small index the model lookup reads,
    so walking a long history does not hold every record in memory."""

    def __init__(self, label: str, read_bytes, position: int = 0):
        # position: later means newer, the tie-break when two publications of
        # one session carry the same clock (a re-run on later bars).
        self.label, self.position, self._read, self._meta = label, position, read_bytes, None
        self.sha256 = hashlib.sha256(read_bytes()).hexdigest()

    @property
    def data(self):
        """The whole record, parsed afresh each time it is asked for."""
        return json.loads(self._read().decode("utf-8"))

    def meta(self) -> dict:
        if self._meta is None:
            try:
                data = self.data
            except (UnicodeDecodeError, ValueError):
                data = None
            run = data.get("run") if isinstance(data, dict) else None
            run = run if isinstance(run, dict) else {}
            plans = data.get("open_plans") if isinstance(data, dict) else None
            self._meta = {
                "session": run.get("session") if isinstance(run.get("session"), str) else None,
                "published_at": run.get("published_at") if isinstance(run.get("published_at"), str) else "",
                "model": [{key: row.get(key) for key in MODEL_FIELDS + ("evidence_ref",)}
                          for row in (plans if isinstance(plans, list) else []) if isinstance(row, dict) and "evidence_ref" in row],
            }
        return self._meta

    @property
    def session(self):
        return self.meta()["session"]

    @property
    def published_at(self):
        return self.meta()["published_at"]


def from_files(paths) -> list[Publication]:
    """Publications in the order given: a later argument is the newer one."""
    return [Publication(str(path), Path(path).read_bytes, index) for index, path in enumerate(paths)]


def from_git(repo: Path, ref: str = "HEAD", limit: int = GIT_LIMIT) -> list[Publication]:
    """Every docs/data.json the history up to `ref` carried, oldest first, bounded to the newest `limit`."""
    out = subprocess.run(["git", "-C", str(repo), "log", "--format=%H", f"-{limit}", ref, "--", RECORD_PATH],
                         check=True, capture_output=True, text=True).stdout.split()
    publications = []
    for index, commit in enumerate(reversed(out)):
        spec = f"{commit}:{RECORD_PATH}"
        if subprocess.run(["git", "-C", str(repo), "cat-file", "-e", spec], capture_output=True).returncode != 0:
            continue  # the commit removed the file

        def read_bytes(spec=spec):
            return subprocess.run(["git", "-C", str(repo), "cat-file", "blob", spec], check=True, capture_output=True).stdout
        publications.append(Publication(f"{commit[:12]}:{RECORD_PATH}", read_bytes, index))
    return publications


def _row(data, stage, ticker):
    if stage == "bursts":
        rows = data.get("bursts") or []
    else:
        rows = (data.get("watchlist") or {}).get("top") or []
    found = [row for row in rows if isinstance(row, dict) and row.get("ticker") == ticker]
    return found[0] if len(found) == 1 else None


def trace(item, publications) -> dict:
    """Is this record's frozen plan the one its publication carries?"""
    if publications is None:
        return {"status": "not_checked", "publication": None, "mismatches": []}
    planned = item["kind"] == "planned_handoff"
    sha = item["publication"]["sha256"] if planned else item["source"]["publication"]["data_sha256"]
    match = next((pub for pub in publications if pub.sha256 == sha), None)
    if match is None:
        return {"status": "publication_not_found", "publication": None, "mismatches": [],
                "searched": len(publications)}
    data = match.data
    run, mismatches = data.get("run") or {}, []
    if planned:
        pub, plan = item["publication"], item["plan"]
        for name, ours, theirs in (("publication.session", pub["session"], run.get("session")),
                                   ("publication.published_at", pub["published_at"], run.get("published_at")),
                                   ("publication.rules_version", pub["rules_version"], (data.get("app") or {}).get("rules_version"))):
            if ours != theirs:
                mismatches.append(name)
        row = _row(data, plan["stage"], plan["ticker"])
        published = (row or {}).get("plan") or {}
        if row is None:
            mismatches.append("plan: no single " + plan["stage"] + " row for " + plan["ticker"])
        else:
            for name, ours, theirs in (("plan.reference", plan["reference"], published.get("evidence_ref")),
                                       ("plan.order", plan["order"], published.get("order_json")),
                                       ("plan.exit_schedule", plan["exit_schedule"], published.get("exit_schedule")),
                                       ("plan.timing", plan["timing"], {k: (run.get("timing") or {}).get(k) for k in TIMING_KEYS})):
                if ours != theirs:
                    mismatches.append(name)
    else:
        source = item["source"]
        pub = source["publication"]
        for name, ours, theirs in (("source.publication.measured_session", pub["measured_session"], run.get("session")),
                                   ("source.publication.run_id", pub["run_id"], str(run.get("run_id"))),
                                   ("source.publication.published_at", pub["published_at"], run.get("published_at")),
                                   ("source.publication.rules_version", pub["rules_version"], (data.get("app") or {}).get("rules_version"))):
            if ours != theirs:
                mismatches.append(name)
        row = _row(data, "setting-up", source["ticker"])
        evidence = (row or {}).get("evidence") or {}
        if row is None:
            mismatches.append("source: no single setting-up row for " + source["ticker"])
        else:
            for name, ours, theirs in (("source.evidence.id", source["evidence"]["id"], evidence.get("id")),
                                       ("source.evidence.plan_sha256", source["evidence"]["plan_sha256"], (evidence.get("planning") or {}).get("output_sha256")),
                                       ("source.evidence.source_sha256", source["evidence"]["source_sha256"], (evidence.get("source") or {}).get("sha256"))):
                if ours != theirs:
                    mismatches.append(name)
    return {"status": "mismatch" if mismatches else "traced", "publication": match.label, "sha256": match.sha256,
            "session": match.session, "mismatches": mismatches}


def model_outcome(item, publications) -> dict:
    """The model's own replay of the same plan, newest supplied publication first."""
    if item["kind"] != "planned_handoff":
        return {"status": "not_applicable", "reason": "an independent research report has no published model plan"}
    if publications is None:
        return {"status": "not_checked", "reason": "no publication source was supplied"}
    session, reference = item["publication"]["session"], item["plan"]["reference"]
    later = [pub for pub in publications if isinstance(pub.session, str) and pub.session > session]
    for pub in sorted(later, key=lambda p: (p.session, p.published_at, p.position), reverse=True):
        for row in pub.meta()["model"]:
            if row["evidence_ref"] == reference:
                return {"status": "observed", "publication": pub.label, "session": pub.session,
                        "basis": "daily-bar model replay of the published plan at its published quantity",
                        "plan": {key: row[key] for key in MODEL_FIELDS}}
    return {"status": "not_observed", "reason": f"no supplied publication after {session} carries this plan's model replay"}


# --- the reading --------------------------------------------------------------

def read(raw: bytes, publications=None) -> dict:
    store = load_backup(raw)
    records, total, complete = [], 0, 0
    for item in store["items"]:
        planned = item["kind"] == "planned_handoff"
        result = completed_result(item["report"])
        reported_block = {**result, "beyond_stop": beyond_stop(item, result)}
        if result["state"] == "complete":
            complete += 1
            total += result["net_microusd"]
        records.append({
            "id": item["id"], "kind": item["kind"],
            "ticker": item["plan"]["ticker"] if planned else item["source"]["ticker"],
            "stage": item["plan"]["stage"] if planned else item["source"]["stage"],
            "session": item["publication"]["session"] if planned else item["source"]["publication"]["measured_session"],
            "revision": item["revision"], "report_updated_at": item["report_updated_at"],
            "facts": item["report"], "draft": draft_of(item),
            "trace": trace(item, publications),
            "reported": reported_block,
            "model": model_outcome(item, publications),
        })
    return {
        "tool": TOOL, "version": VERSION,
        "backup": {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "version": store["version"], "records": len(records)},
        "records": records,
        "reported_totals": {"complete": complete, "net": exact(total), "net_microusd": total, "display": display(total)},
        "notes": [
            "A reported result is the owner's account of the broker's records; nothing here verifies it.",
            "A model outcome is the daily-bar replay of the published plan at its published quantity; it is never added to a reported result.",
        ],
    }


def text(reading: dict) -> str:
    count = reading["backup"]["records"]
    lines = [f"Private backup {reading['backup']['sha256'][:12]}: {count} {'record' if count == 1 else 'records'} (store version {reading['backup']['version']})."]
    for record in reading["records"]:
        trace_ = record["trace"]
        if trace_["status"] == "traced":
            where = f"traced to {trace_['publication']} (session {trace_['session']})"
        elif trace_["status"] == "mismatch":
            where = f"NOT the plan {trace_['publication']} carries: " + ", ".join(trace_["mismatches"])
        elif trace_["status"] == "publication_not_found":
            where = f"publication not found among {trace_['searched']} searched"
        else:
            where = "publication not checked"
        lines.append(f"- {record['ticker']} ({record['kind']}, scan {record['session']}): {where}")
        result = record["reported"]
        if result["state"] == "complete":
            shares = "1 share" if result["quantity"] == 1 else f"{result['quantity']} shares"
            lines.append(f"    reported: {result['outcome']} on {shares}; gross {result['display']['gross']}, "
                         f"costs {result['display']['costs']}, net {result['display']['net']} (exact {result['net']})")
            if result["beyond_stop"]:
                lines.append(f"    average exit {result['beyond_stop']['display']['per_share']} a share under the published stop: "
                             f"{result['beyond_stop']['display']['total']} past it (a gap or slippage)")
        else:
            lines.append("    reported: no completed result -- " + "; ".join(result["reasons"]))
        model = record["model"]
        if model["status"] == "observed":
            plan = model["plan"]
            lines.append(f"    model (kept apart, {plan['shares']} published shares on daily bars) in {model['publication']}: "
                         f"{plan['status']}; {plan['fill']}; result {plan['result_pct']}%")
        else:
            lines.append(f"    model (kept apart): {model['status']} -- {model['reason']}")
    totals = reading["reported_totals"]
    lines.append(f"Reported net over {totals['complete']} completed {'result' if totals['complete'] == 1 else 'results'}: "
                 f"{totals['display']} (exact {totals['net']}).")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("backup", type=Path, help="the file *Download private backup* wrote")
    parser.add_argument("--publication", type=Path, action="append", default=[], help="a published data.json (repeatable)")
    parser.add_argument("--git", nargs="?", const="HEAD", default=None, metavar="REF",
                        help="search this checkout's history of docs/data.json up to REF (default HEAD)")
    parser.add_argument("--limit", type=int, default=GIT_LIMIT, help=f"commits --git reads (default {GIT_LIMIT})")
    parser.add_argument("--json", type=Path, help="write the reading here")
    args = parser.parse_args(argv)
    publications = None
    if args.publication or args.git is not None:
        publications = from_files(args.publication)
        if args.git is not None:
            # History first, then the files: a file named on the command line
            # is read as newer than anything committed.
            history = from_git(ROOT, args.git, args.limit)
            for pub in publications:
                pub.position += len(history)
            publications = history + publications
    try:
        reading = read(args.backup.read_bytes(), publications)
    except Refused as error:
        print(f"Refused: {error}. Nothing was re-derived.", file=sys.stderr)
        return 2
    print(text(reading))
    if args.json:
        args.json.write_text(json.dumps(reading, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    unresolved = [r for r in reading["records"] if r["trace"]["status"] in ("publication_not_found", "mismatch")]
    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
