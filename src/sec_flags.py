"""SEC filing flags for the night's tickets and listed setups (``run.sec_flags``).

A flag, never a refusal and never a clearance. For every ticket the record
publishes and every setup the setting-up list lists, this reads the issuer's
own SEC filing list (the earnings warning's transport and bounds:
``earnings_risk.FETCH``, its mapping and its submissions URL) and names each
filing of ``FORMS`` -- a tender offer, the target's response to one, a merger
proxy -- or each current report carrying an item of ``ITEMS`` -- a material
agreement, a completed acquisition, a delisting notice, a change in control
-- filed within ``WINDOW_DAYS`` before the signal session or since it. Any
flag sets that ticket to human review in ``orders.json``. A name SEC could
not be read for is ``unknown``, and unknown is never clear.

It reads what a filing is, by its form and its item codes, and never what it
says. It is not news coverage and not the manual event registry
(``knowledge/event-risk.json``), which alone refuses a ticket.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

VERSION = 1
#: (P) the forms a cash deal or a change of control files under, and their amendments
FORMS = ("SC TO-T", "SC TO-T/A", "SC 14D9", "SC 14D9/A", "DEFM14A", "DEFM14A/A", "PREM14A", "PREM14A/A")
#: (P) the 8-K items that name a deal, a completed acquisition, a delisting notice or a change in control
ITEMS = ("1.01", "2.01", "3.01", "5.01")
#: (P) a filing within this many calendar days before the signal session, or since it, is recent
WINDOW_DAYS = 30
#: the names one night reads: four model slots a stage and the listed setups
MAX_NAMES = 20
FLAGGED, CLEAR, UNKNOWN = "flagged", "clear", "unknown"
STATES = (FLAGGED, CLEAR, UNKNOWN)
RULES = {"sec_flags.version": VERSION, "sec_flags.forms": list(FORMS), "sec_flags.items": list(ITEMS),
         "sec_flags.window_days": WINDOW_DAYS, "sec_flags.max_names": MAX_NAMES}


def _rows(value) -> list[dict]:
    """The filings of one ``recent`` block that are flags, oldest first."""
    from src import earnings_risk
    names = ("accessionNumber", "filingDate", "form", "items")
    if not isinstance(value, dict) or not all(isinstance(value.get(n), list) for n in names):
        raise earnings_risk.SourceError("rows_unreadable")
    count = len(value["accessionNumber"])
    if not all(len(value[n]) == count for n in names):
        raise earnings_risk.SourceError("rows_unreadable")
    out = []
    for i in range(count):
        accession, filed, form, items = (value[n][i] for n in names)
        if not (isinstance(accession, str) and isinstance(form, str) and isinstance(items, str)):
            continue
        try:
            day = earnings_risk._day(filed).isoformat()
        except (ValueError, TypeError):
            continue
        codes, _ = earnings_risk._parse_items(items) if form in earnings_risk.CURRENT_REPORT_FORMS else ([], 0)
        named = sorted(set(codes) & set(ITEMS))
        if form in FORMS or named:
            out.append({"accession": accession, "filing_date": day, "form": form, "items": named})
    return sorted(out, key=lambda r: (r["filing_date"], r["accession"]))


def _row(name: dict, state: str, *, reason=None, cik=None, filings=()) -> dict:
    return {"stage": name["stage"], "ticker": name["ticker"], "state": state, "reason": reason, "cik": cik,
            "filings": list(filings)}


def names_of(tickets: list[dict], top: list) -> list[dict]:
    """The tickets, then every listed setup that is not one, in the record's order."""
    seen = {(t["stage"], t["ticker"]) for t in tickets}
    out = list(tickets)
    for row in top if isinstance(top, list) else []:
        if isinstance(row, dict) and isinstance(row.get("ticker"), str) and ("anticipation", row["ticker"]) not in seen:
            out.append({"stage": "anticipation", "ticker": row["ticker"]})
            seen.add(("anticipation", row["ticker"]))
    return out


def collect(names: list[dict], session: str, *, fetch=None, now=None, deadline_seconds: float | None = None) -> dict:
    """One night's flags. A source failure is an unknown row, never a raise."""
    import time
    from src import earnings_risk, issuer_evidence
    session = earnings_risk._day(session)
    since = (session - timedelta(days=WINDOW_DAYS)).isoformat()
    clock = (lambda: now) if now is not None else (lambda: datetime.now(timezone.utc))
    deadline = earnings_risk.DEADLINE_SECONDS if deadline_seconds is None else deadline_seconds
    block: dict[str, Any] = {"version": VERSION, "session": session.isoformat(), "since": since,
                             "forms": list(FORMS), "items": list(ITEMS), "window_days": WINDOW_DAYS,
                             "rows": [], "requests": 0, "status": "not_applicable"}
    if names:
        fetch = fetch or earnings_risk.FETCH or earnings_risk._default_fetch(deadline)
        started = time.monotonic()

        def get(url):
            if time.monotonic() - started >= deadline:
                raise earnings_risk.SourceError("time_budget")
            block["requests"] += 1
            return fetch(url)

        try:
            mapping, mapping_error = earnings_risk.parse_mapping(get(issuer_evidence.MAPPING_URL)), None
        except earnings_risk.SourceError as exc:
            mapping, mapping_error = None, exc.code
        for i, name in enumerate(names):
            if i >= MAX_NAMES:
                block["rows"].append(_row(name, UNKNOWN, reason="not_checked"))
                continue
            if mapping_error is not None:
                block["rows"].append(_row(name, UNKNOWN, reason=mapping_error))
                continue
            identities = mapping.get(name["ticker"], [])
            if len(identities) != 1:
                block["rows"].append(_row(name, UNKNOWN, reason="not_mapped" if not identities else "identity_ambiguous"))
                continue
            cik = identities[0]["cik"]
            try:
                raw = get(earnings_risk.SUBMISSIONS_URL.format(cik=cik))
                value = earnings_risk._decode(raw)
                if not isinstance(value.get("tickers"), list) or name["ticker"] not in value["tickers"]:
                    raise earnings_risk.SourceError("not_mapped")
                recent = value["filings"]["recent"]
                flags = [r for r in _rows(recent) if r["filing_date"] >= since]
            except earnings_risk.SourceError as exc:
                block["rows"].append(_row(name, UNKNOWN, reason=exc.code, cik=cik))
                continue
            except (KeyError, TypeError, AttributeError):
                block["rows"].append(_row(name, UNKNOWN, reason="rows_unreadable", cik=cik))
                continue
            block["rows"].append(_row(name, FLAGGED if flags else CLEAR, cik=cik, filings=flags))
        block["retrieved_at"] = clock().astimezone(timezone.utc).isoformat()
    block["status"] = status_of(block["rows"])
    block["sentence"] = sentence(block)
    return block


def status_of(rows: list[dict]) -> str:
    if not rows:
        return "not_applicable"
    return "flagged" if any(r["state"] == FLAGGED for r in rows) else \
        "unknown" if any(r["state"] == UNKNOWN for r in rows) else "clear"


def sentence(block: dict) -> str:
    rows = block["rows"]
    if not rows:
        return "No ticket or listed setup to check SEC filings for."
    flagged = [r for r in rows if r["state"] == FLAGGED]
    unknown = [r for r in rows if r["state"] == UNKNOWN]
    words = (f"SEC filings since {block['since']} were read for {len(rows)} name{'' if len(rows) == 1 else 's'}: "
             + (", ".join(f"{r['ticker']} ({'; '.join(f['form'] + (' item ' + ', '.join(f['items']) if f['items'] else '') + ' ' + f['filing_date'] for f in r['filings'])})"
                          for r in flagged) + " flagged for review" if flagged else "none flagged"))
    if unknown:
        words += f"; {len(unknown)} could not be read ({', '.join(r['ticker'] for r in unknown)}), which is not clear"
    return words + ". A flag names a filing's form or item, never what it says, and refuses nothing by itself."


def safe_collect(names: list[dict], session: str, **kwargs) -> dict:
    """The evening's call: a flag never fails a night. Anything the collector
    did not name makes every row unknown."""
    try:
        return collect(names, session, **kwargs)
    except Exception:  # noqa: BLE001 -- a flag must never stop a publication
        from src import earnings_risk
        day = earnings_risk._day(session)
        block = {"version": VERSION, "session": day.isoformat(),
                 "since": (day - timedelta(days=WINDOW_DAYS)).isoformat(), "forms": list(FORMS),
                 "items": list(ITEMS), "window_days": WINDOW_DAYS, "requests": 0,
                 "rows": [_row(n, UNKNOWN, reason="not_checked") for n in names]}
        block["status"] = status_of(block["rows"])
        block["sentence"] = sentence(block)
        return block


def faults(data: dict) -> list[str]:
    """The block one level in, under rules that archive it: its forms, items and
    window are the archived ones, a row that was read names its CIK, and each
    flagged filing is inside the window and of a listed form or item. A ticket
    with no row reads as unknown in ``orders.json``, so a dropped row holds the
    ticket for review rather than clearing it."""
    archived = (data.get("rules") or {}).get("sec_flags") if isinstance(data.get("rules"), dict) else None
    run = data.get("run") if isinstance(data.get("run"), dict) else {}
    block = run.get("sec_flags")
    if archived is None:
        return [] if block is None else ["run.sec_flags present under rules that do not write it"]
    if not isinstance(archived, dict):
        return ["rules.sec_flags is not an object"]
    if not isinstance(block, dict) or block.get("version") != VERSION:
        return ["run.sec_flags is missing or not this version"]
    if (block.get("forms"), block.get("items"), block.get("window_days")) != \
            (archived.get("forms"), archived.get("items"), archived.get("window_days")):
        return ["run.sec_flags forms, items or window are not the rules it archived"]
    out = []
    rows = block.get("rows")
    if not isinstance(rows, list) or not all(isinstance(r, dict) and r.get("state") in STATES
                                             and isinstance(r.get("ticker"), str) and isinstance(r.get("filings"), list)
                                             for r in rows):
        out.append("run.sec_flags rows are not readable")
    elif block.get("status") != status_of(rows):
        out.append("run.sec_flags status is not its rows'")
    elif any((r["state"] == FLAGGED) != bool(r["filings"]) for r in rows):
        out.append("run.sec_flags a row's state is not its filings'")
    elif any(r["state"] != UNKNOWN and not isinstance(r.get("cik"), (str, int)) for r in rows):
        out.append("run.sec_flags a row read as flagged or clear names no CIK")
    elif not isinstance(block.get("since"), str) or any(
            not isinstance(f, dict) or not isinstance(f.get("filing_date"), str) or f["filing_date"] < block["since"]
            or not (f.get("form") in block["forms"] or (isinstance(f.get("items"), list) and f["items"]
                                                        and set(f["items"]) <= set(block["items"])))
            for r in rows for f in r["filings"]):
        out.append("run.sec_flags a flagged filing is outside the window or of no listed form or item")
    if not isinstance(block.get("sentence"), str):
        out.append("run.sec_flags sentence is not text")
    return out
