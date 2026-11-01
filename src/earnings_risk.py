"""Earnings warnings for each published ticket, estimated from SEC results filings.

No free source lets a public site print a company's announced earnings date
(the October 2026 research behind this module read every calendar's terms), so
this module estimates one from SEC EDGAR, whose filings are public: the dates a
company furnished its results (form 8-K, item 2.02) over the last fourteen
months. Most companies report in the same week each year, so a filing a year
ago puts this year's report about ``PROJECTION_DAYS`` later, within
``ESTIMATE_SLACK_DAYS``. That is an ESTIMATE and every sentence says so: it is
not an announced date, and a result 8-K can be filed up to four business days
after the release it furnishes.

Policy ``warn_only``: the module never refuses, sizes or cuts a ticket. It
annotates each ticket the evening run admitted with one verdict, read against
the plan's own hold window (``plan.dated_schedule()``'s five sessions after the
signal session):

* ``reported_after_signal`` -- an observed fact: a results 8-K accepted after
  the signal session's scheduled close and before the run read SEC, so the
  entry opens on the reaction;
* ``estimate_inside`` -- the estimate falls inside the window;
* ``estimate_near`` -- the estimate's slack reaches the window;
* ``overdue`` -- the estimate passed by more than its slack and no results
  filing has come since, so a report could come any day;
* ``already_reported`` -- this cycle's results were filed on or before the
  signal session; the next report is about a quarter away (an inference);
* ``estimate_outside`` -- the estimate falls outside the window;
* ``unknown`` with a reason -- never clearance.

Nothing here is Bonde's rule: it is SpicyStock's warning about a gap a stop
does not protect against.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import re
import time

from src import sessions
from src import issuer_evidence

VERSION = 1
POLICY = "warn_only"
SOURCE = "sec_edgar_submissions"
COVERAGE = "sec_results_filings_derived"
RESULTS_FORM = "8-K"
RESULTS_ITEM = "2.02"
FOREIGN_FORMS = ("6-K", "6-K/A", "20-F", "20-F/A", "40-F", "40-F/A")
PROJECTION_DAYS = 364        # DERIVED: 52 weeks, the same weekday a year on
ESTIMATE_SLACK_DAYS = 7      # P: a report a week either side of last year's is the same cycle
OVERDUE_DAYS = 45            # P: an estimate whose range ended this many days before the signal still reads as overdue
MAX_TICKETS = 8              # four model slots per stage; never binds on a real night
MAX_RESULTS_FILINGS = 12     # newest results filings kept per ticket (about three years of quarters)
MAX_HISTORY_FILES = 1
DEADLINE_SECONDS = 60
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
HISTORY_URL = "https://data.sec.gov/submissions/{name}"
VERDICTS = ("reported_after_signal", "estimate_inside", "estimate_near", "overdue",
            "already_reported", "estimate_outside", "unknown")
UNKNOWN_REASONS = ("not_mapped", "foreign_issuer", "no_results_history", "no_recent_results", "history_short",
                   "history_not_read", "rows_unreadable", "source_unavailable", "not_checked")
# the reasons a row was read for and re-derived from; the rest carry no finding
ASSESSED_REASONS = (None, "foreign_issuer", "no_results_history", "no_recent_results", "history_short",
                    "history_not_read")
UNREAD_REASONS = ("not_mapped", "rows_unreadable", "source_unavailable", "not_checked")
PLACEMENTS = ("pre_entry", "held", "boundary", "any_day")
STATUSES = ("not_applicable", "checked", "partial", "unavailable")
STAGES = ("burst", "anticipation")

RULES = {
    "earnings_risk.version": VERSION,
    "earnings_risk.policy": POLICY,
    "earnings_risk.source": SOURCE,
    "earnings_risk.coverage": COVERAGE,
    "earnings_risk.results_form": RESULTS_FORM,
    "earnings_risk.results_item": RESULTS_ITEM,
    "earnings_risk.foreign_forms": list(FOREIGN_FORMS),
    "earnings_risk.projection_days": PROJECTION_DAYS,
    "earnings_risk.estimate_slack_days": ESTIMATE_SLACK_DAYS,
    "earnings_risk.overdue_days": OVERDUE_DAYS,
    "earnings_risk.max_tickets": MAX_TICKETS,
    "earnings_risk.max_results_filings": MAX_RESULTS_FILINGS,
    "earnings_risk.max_history_files": MAX_HISTORY_FILES,
    "earnings_risk.deadline_seconds": DEADLINE_SECONDS,
    "earnings_risk.window": "plan.final_exit_day sessions after the signal session",
    "earnings_risk.unknown_policy": "never_clearance",
}

ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z")
REASON_WORDS = {
    "not_mapped": "SEC's ticker list does not name this symbol",
    "foreign_issuer": "a foreign issuer files its results on forms that carry no results item",
    "no_results_history": "no results filing (8-K item 2.02) in SEC's list",
    "no_recent_results": "no results filing (8-K item 2.02) in the fourteen months before the signal",
    "history_short": "its results filings do not reach back a year",
    "history_not_read": "the filings SEC returned do not reach back a year and the older file was not read",
    "rows_unreadable": "SEC's filing list could not be read",
    "source_unavailable": "SEC did not answer",
    "not_checked": "not checked in this run",
}


# an injected ``fetch(url) -> bytes`` (tests, the fixture generator); None reads SEC
FETCH = None


class SourceError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


# ------------------------------------------------------------ the rule ---
def _day(value) -> date:
    if isinstance(value, datetime) or not isinstance(value, (date, str)):
        raise ValueError("earnings date must be YYYY-MM-DD")
    if isinstance(value, date):
        return value
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("earnings date must be YYYY-MM-DD")
    return parsed


def _instant(value) -> datetime:
    if not isinstance(value, str):
        raise ValueError("earnings instant must be ISO 8601")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("earnings instant needs an offset")
    return parsed.astimezone(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def window(session) -> list[str]:
    """The plan's hold: ``plan.FINAL_EXIT_DAY`` sessions after the signal."""
    from src import plan
    return [d.isoformat() for d in plan.next_sessions(_day(session), plan.FINAL_EXIT_DAY)]


def timing_of(filing) -> str:
    """Acceptance is the latest the release could have been, so an acceptance
    before the open on the filing date proves a release before the open;
    nothing in the metadata proves one after the close."""
    if not filing.get("accepted_at"):
        return "unknown"
    accepted = _instant(filing["accepted_at"]).astimezone(sessions.MARKET_TZ)
    filed = _day(filing["filing_date"])
    if accepted.date() == filed and sessions.is_session(filed):
        opens = sessions.hours(filed)[0]
        if accepted < opens:
            return "before_open"
    return "unknown"


def assess(filings, session, days, retrieved_at, coverage_start, foreign) -> dict:
    """One ticket's verdict from its results filings. Pure: every input is
    retained on the row, so the validator re-derives it."""
    signal = _day(session)
    days = [_day(d) for d in days]
    retrieved = _instant(retrieved_at)
    first, last = days[0], days[-1]
    slack = timedelta(days=ESTIMATE_SLACK_DAYS)
    rows = sorted(({"accession": f["accession"], "filing_date": _day(f["filing_date"]),
                    "accepted_at": f.get("accepted_at")} for f in filings),
                  key=lambda f: (f["filing_date"], f["accession"]))
    rows = [f for f in rows if f["filing_date"] <= retrieved.date()]
    out = {"verdict": "unknown", "placement": None, "projection": None, "observed": None, "reason": None}

    close = sessions.hours(signal)[1]
    day1_open = sessions.hours(first)[0]
    observed = [f for f in rows if f["accepted_at"] and close < _instant(f["accepted_at"]) <= retrieved]
    if observed:
        hit = observed[-1]
        accepted = _instant(hit["accepted_at"])
        out.update(verdict="reported_after_signal",
                   placement="pre_entry" if accepted < day1_open else "held",
                   observed={"accession": hit["accession"], "filing_date": hit["filing_date"].isoformat(),
                             "accepted_at": hit["accepted_at"]})
        return out

    # the oldest filing a projection inside the horizon can come from
    needed = signal - timedelta(days=PROJECTION_DAYS) - slack - timedelta(days=OVERDUE_DAYS)
    if coverage_start is None or _day(coverage_start) > needed:
        out["reason"] = "history_not_read"
        return out
    if not rows:
        out["reason"] = "foreign_issuer" if foreign else "no_results_history"
        return out
    if rows[0]["filing_date"] > needed:
        out["reason"] = "history_short"
        return out
    if rows[-1]["filing_date"] < needed:
        out["reason"] = "no_recent_results"
        return out

    def project(anchor):
        q = anchor["filing_date"] + timedelta(days=PROJECTION_DAYS)
        return {"date": q.isoformat(), "low": (q - slack).isoformat(), "high": (q + slack).isoformat(),
                "from_accession": anchor["accession"], "from_filing_date": anchor["filing_date"].isoformat(),
                "slack_days": ESTIMATE_SLACK_DAYS, "timing_last_year": timing_of(
                    {"filing_date": anchor["filing_date"].isoformat(), "accepted_at": anchor["accepted_at"]})}

    horizon_low = signal - timedelta(days=OVERDUE_DAYS) - slack
    classes = {"inside": [], "near": [], "overdue": [], "reported": []}
    later = []
    for anchor in rows:
        q = anchor["filing_date"] + timedelta(days=PROJECTION_DAYS)
        if q > last + slack:
            later.append(anchor)
            continue
        if q < horizon_low:
            continue
        # any results filing since the estimate's low reports this cycle,
        # however late against last year's date
        reported = [f for f in rows if f["filing_date"] >= q - slack]
        if reported:
            classes["reported"].append((anchor, reported[0]))
        elif signal <= q <= last:
            classes["inside"].append(anchor)
        elif q - slack <= last and q + slack >= signal:
            classes["near"].append(anchor)
        elif q + slack < signal:
            classes["overdue"].append(anchor)
    if classes["inside"]:
        anchor = classes["inside"][0]
        q = anchor["filing_date"] + timedelta(days=PROJECTION_DAYS)
        out.update(verdict="estimate_inside", placement="pre_entry" if q < first else "held",
                   projection=project(anchor))
    elif classes["near"]:
        out.update(verdict="estimate_near", placement="boundary", projection=project(classes["near"][0]))
    elif classes["overdue"]:
        out.update(verdict="overdue", placement="any_day", projection=project(classes["overdue"][-1]))
    elif classes["reported"]:
        anchor, filed = classes["reported"][-1]
        out.update(verdict="already_reported", projection=project(anchor),
                   observed={"accession": filed["accession"], "filing_date": filed["filing_date"].isoformat(),
                             "accepted_at": filed["accepted_at"]})
    else:
        out.update(verdict="estimate_outside", projection=project(later[0]) if later else None)
    return out


# ------------------------------------------------------------ the words ---
def _short(value) -> str:
    d = _day(value)
    return f"{d.strftime('%a')} {d.day} {d.strftime('%b')}"


def _long(value) -> str:
    d = _day(value)
    return f"{d.day} {d.strftime('%b')} {d.year}"


def _et(value) -> str:
    moment = _instant(value).astimezone(sessions.MARKET_TZ)
    hour = moment.hour % 12 or 12
    return f"{_short(moment.date().isoformat())} {hour}:{moment.minute:02d} {'AM' if moment.hour < 12 else 'PM'} ET"


def sentence(row) -> str:
    """What the page and the mail print beside the ticket, verbatim."""
    days = row["window"]
    span = f"{_short(days[0])}–{_short(days[-1])}"
    verdict, projection = row["verdict"], row.get("projection")
    tail = " An estimate from SEC filings, not an announced date: check the company's announcement before entry."
    if verdict == "reported_after_signal":
        when = _et(row["observed"]["accepted_at"])
        lead = ("before day 1's open, so the entry opens on the reaction" if row["placement"] == "pre_entry"
                else "inside the hold window")
        return (f"Quarterly results (8-K item 2.02) were filed with the SEC after the signal session's close "
                f"(accepted {when}), {lead}.")
    if verdict == "unknown":
        return (f"Earnings date not established: {REASON_WORDS[row['reason']]}. "
                "Check the company's announcement before entry.")
    source = (f"from last year's results filing of {_long(projection['from_filing_date'])}"
              + (", accepted before that day's open" if projection.get("timing_last_year") == "before_open" else "")
              if projection else "")
    about = (f"about {_short(projection['date'])} (±{projection['slack_days']} days)" if projection else "")
    if verdict == "estimate_inside":
        where = ("before day 1, so the entry may open on the reaction" if row["placement"] == "pre_entry"
                 else f"inside this ticket's hold window {span}")
        return f"Earnings estimated {about}, {source}: {where}.{tail}"
    if verdict == "estimate_near":
        return f"Earnings estimated {about}, {source}: its range reaches this ticket's hold window {span}.{tail}"
    if verdict == "overdue":
        return (f"Earnings were estimated {about}, {source}, and no results filing has come since: "
                f"a report could come any day, including inside this ticket's hold window {span}.{tail}")
    if verdict == "already_reported":
        return (f"This quarter's results were filed {_long(row['observed']['filing_date'])}; the next earnings report is "
                f"not estimated inside this ticket's hold window {span} (an inference from filing history, "
                "not clearance).")
    if projection is None:
        return (f"No earnings report is estimated inside this ticket's hold window {span} from its results filings "
                "(an inference, not clearance).")
    return (f"The next earnings report is estimated {about}, {source}: outside this ticket's hold window {span} "
            "(an inference, not clearance).")


def block_sentence(block) -> str:
    rows = block["rows"]
    if block["status"] == "not_applicable":
        return "Earnings: no ticket to check."
    counts = block["counts"]
    parts = []
    for verdict, words in (("reported_after_signal", "reported after the signal"),
                           ("estimate_inside", "estimated inside the hold window"),
                           ("estimate_near", "estimated near it"),
                           ("overdue", "overdue, so any day"),
                           ("already_reported", "already reported this quarter"),
                           ("estimate_outside", "estimated outside it"),
                           ("unknown", "not established")):
        if counts.get(verdict):
            parts.append(f"{counts[verdict]} {words}")
    noun = "ticket" if len(rows) == 1 else "tickets"
    lead = f"Earnings, estimated from SEC results filings for {len(rows)} {noun}: " + "; ".join(parts) + "."
    if block["status"] == "unavailable":
        lead += " No SEC filing list was read, so no date is established."
    return lead + " An estimate warns and never withholds a ticket."


# ------------------------------------------------------------ the source ---
def _columns(value):
    """The results filings, the oldest filing date and the forms of one SEC
    filing list. The five columns it reads are parallel or the list is refused
    whole; a row it cannot read is left out of all three."""
    names = ("accessionNumber", "filingDate", "acceptanceDateTime", "form", "items")
    if not isinstance(value, dict) or not all(isinstance(value.get(n), list) for n in names):
        raise SourceError("rows_unreadable")
    count = len(value["accessionNumber"])
    if not all(len(value[n]) == count for n in names):
        raise SourceError("rows_unreadable")
    results, dates, forms = [], [], set()
    for i in range(count):
        accession, filed, accepted = value["accessionNumber"][i], value["filingDate"][i], value["acceptanceDateTime"][i]
        form, items = value["form"][i], value["items"][i]
        try:
            if not (isinstance(accession, str) and ACCESSION.fullmatch(accession)
                    and isinstance(form, str) and isinstance(items, str)):
                continue
            filed_day = _day(filed)
            accepted_iso = _iso(_instant(accepted)) if accepted else None
        except (ValueError, TypeError):
            continue
        dates.append(filed_day)
        forms.add(form)
        if form == RESULTS_FORM and RESULTS_ITEM in [x.strip() for x in items.split(",")]:
            results.append({"accession": accession, "filing_date": filed_day.isoformat(), "accepted_at": accepted_iso})
    return results, (min(dates) if dates else None), forms


def parse_submissions(raw: bytes, cik: int, ticker: str):
    try:
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict) or str(value.get("cik", "")).lstrip("0") != str(cik):
            raise SourceError("rows_unreadable")
        tickers = value.get("tickers")
        if not isinstance(tickers, list) or ticker not in tickers:
            raise SourceError("not_mapped")
        recent = value["filings"]["recent"]
        files = value["filings"].get("files", [])
        if not isinstance(files, list):
            raise SourceError("rows_unreadable")
    except SourceError:
        raise
    except (KeyError, TypeError, ValueError, UnicodeDecodeError):
        raise SourceError("rows_unreadable") from None
    results, start, forms = _columns(recent)
    history = []
    for item in files:
        try:
            name = item["name"]
            if (isinstance(name, str) and re.fullmatch(f"CIK{cik:010d}-submissions-[0-9]{{3}}\\.json", name)):
                history.append({"name": name, "filing_to": _day(item["filingTo"]).isoformat()})
        except (KeyError, TypeError, ValueError):
            continue
    return {"results": results, "coverage_start": start, "forms": forms, "history": history}


def _budget(seconds):
    class Budget(issuer_evidence._Budget):
        def remaining(self):
            return seconds - (time.monotonic() - self.started)
    return Budget()


def _default_fetch(seconds):
    transport, budget = issuer_evidence._Transport(None), _budget(seconds)

    def fetch(url):
        try:
            return transport.fetch(url, budget)["body"]
        except issuer_evidence.SourceError as exc:
            raise SourceError(exc.code if exc.code in issuer_evidence.ERRORS else "invalid_response") from None
    fetch.remaining = budget.remaining
    return fetch


def _source(url, raw, retrieved) -> dict:
    return {"url": url, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "retrieved_at": _iso(retrieved)}


# ------------------------------------------------------------ the block ---
def tickets_of(bursts, trades, top) -> list[dict]:
    """Every ticket the record publishes, in its order: the bursts in
    ``trades``, then the setting-up list's plans that still carry an order
    after the combined allocation -- the same two rules the picks are written by."""
    from src import plan as plan_module
    trades = set(trades or [])
    out = [{"stage": "burst", "ticker": row["ticker"]} for row in bursts or []
           if isinstance(row, dict) and row.get("ticker") in trades and isinstance(row.get("plan"), dict)]
    out += [{"stage": "anticipation", "ticker": row["ticker"]} for row in top or []
            if isinstance(row, dict) and isinstance(row.get("plan"), dict) and row["plan"].get("eligible")
            and row["plan"].get("action") in plan_module.ORDER_ACTIONS]
    return out


def _counts(rows) -> dict:
    return {v: n for v in VERDICTS if (n := sum(1 for r in rows if r.get("verdict") == v))}


def _status(rows) -> str:
    if not rows:
        return "not_applicable"
    unread = sum(1 for r in rows if r.get("reason") in UNREAD_REASONS and r.get("reason") != "not_mapped")
    return "unavailable" if unread == len(rows) else "partial" if unread else "checked"


def _row(ticket, session, days, retrieved, result=None, *, reason=None, error=None, cik=None, issuer=None,
         sources=(), filings=(), coverage_start=None, foreign=False):
    row = {"stage": ticket["stage"], "ticker": ticket["ticker"], "session": session, "window": days,
           "cik": cik, "issuer": issuer, "sources": list(sources), "error": error, "retrieved_at": _iso(retrieved),
           "results_filings": list(filings), "coverage_start": coverage_start, "foreign": foreign}
    if result is None:
        row.update(verdict="unknown", placement=None, projection=None, observed=None, reason=reason)
    else:
        row.update(result)
    row["sentence"] = sentence(row)
    return row


def _read(get, cik, ticker, session, clock_now):
    """One issuer's results filings from its SEC list, and the older file when
    the recent one does not reach back far enough. A failed older file leaves
    the recent rows, read as ``history_not_read``, with its error named."""
    url = SUBMISSIONS_URL.format(cik=cik)
    raw = get(url)
    retrieved = clock_now()
    parsed = parse_submissions(raw, cik, ticker)
    sources, error = [_source(url, raw, retrieved)], None
    results, start = list(parsed["results"]), parsed["coverage_start"]
    needed = _day(session) - timedelta(days=PROJECTION_DAYS + ESTIMATE_SLACK_DAYS + OVERDUE_DAYS)
    older = sorted((h for h in parsed["history"] if _day(h["filing_to"]) >= needed),
                   key=lambda h: (h["filing_to"], h["name"]), reverse=True)[:MAX_HISTORY_FILES]
    if (start is None or start > needed) and older:
        url = HISTORY_URL.format(name=older[0]["name"])
        try:
            hraw = get(url)
            more, hstart, hforms = _columns(json.loads(hraw.decode("utf-8")))
        except SourceError as exc:
            error = exc.code
        except (UnicodeDecodeError, ValueError):
            error = "rows_unreadable"
        else:
            sources.append(_source(url, hraw, clock_now()))
            known = {r["accession"] for r in results}
            results += [r for r in more if r["accession"] not in known]
            parsed["forms"] |= hforms
            if hstart is not None:
                start = hstart if start is None else min(start, hstart)
    results = sorted(results, key=lambda r: (r["filing_date"], r["accession"]), reverse=True)[:MAX_RESULTS_FILINGS]
    results.sort(key=lambda r: (r["filing_date"], r["accession"]))
    return {"filings": results, "coverage_start": start.isoformat() if start else None,
            "foreign": bool(parsed["forms"] & set(FOREIGN_FORMS)), "sources": sources,
            "retrieved": retrieved, "error": error}


def collect(tickets, session, *, fetch=None, now=None, deadline_seconds=DEADLINE_SECONDS) -> dict:
    """One evening's warnings. ``fetch(url) -> bytes`` raises
    :class:`SourceError` on failure; None reads SEC. A source failure is an
    unknown row, never a raise; ``safe_collect()`` catches the rest."""
    session = _day(session).isoformat()
    days = window(session)
    clock_now = (lambda: now) if now is not None else (lambda: datetime.now(timezone.utc))
    tickets = list(tickets)
    block = {"version": VERSION, "policy": POLICY, "source": SOURCE, "session": session,
             "status": "not_applicable", "mapping": None, "rows": [], "counts": {}, "requests": 0}
    if tickets:
        started = time.monotonic()
        fetch = fetch or FETCH or _default_fetch(deadline_seconds)

        def get(url):
            if time.monotonic() - started >= deadline_seconds:
                raise SourceError("time_budget")
            block["requests"] += 1
            return fetch(url)

        mapping_raw, mapping_error, read = None, None, {}
        try:
            mapping_raw = get(issuer_evidence.MAPPING_URL)
            block["mapping"] = _source(issuer_evidence.MAPPING_URL, mapping_raw, clock_now())
        except SourceError as exc:
            mapping_error = exc.code
        for i, ticket in enumerate(tickets):
            if i >= MAX_TICKETS:
                block["rows"].append(_row(ticket, session, days, clock_now(), reason="not_checked"))
                continue
            if mapping_error is not None:
                block["rows"].append(_row(ticket, session, days, clock_now(), reason="source_unavailable",
                                          error=mapping_error))
                continue
            try:
                identity = issuer_evidence.parse_mapping(mapping_raw, ticket["ticker"])
            except issuer_evidence.SourceError:
                block["rows"].append(_row(ticket, session, days, clock_now(), reason="not_mapped"))
                continue
            cik, issuer = identity["cik"], identity["name"]
            try:
                if ticket["ticker"] not in read:
                    read[ticket["ticker"]] = _read(get, cik, ticket["ticker"], session, clock_now)
                got = read[ticket["ticker"]]
                result = assess(got["filings"], session, days, _iso(got["retrieved"]),
                                got["coverage_start"], got["foreign"])
                row = _row(ticket, session, days, got["retrieved"], result, cik=cik, issuer=issuer,
                           sources=got["sources"], error=got["error"], filings=got["filings"],
                           coverage_start=got["coverage_start"], foreign=got["foreign"])
            except SourceError as exc:
                reason = exc.code if exc.code in ("not_mapped", "rows_unreadable") else "source_unavailable"
                row = _row(ticket, session, days, clock_now(), reason=reason, cik=cik, issuer=issuer,
                           error=exc.code if reason == "source_unavailable" else None)
            block["rows"].append(row)
    block["status"] = _status(block["rows"])
    block["counts"] = _counts(block["rows"])
    block["sentence"] = block_sentence(block)
    return block


def safe_collect(tickets, session, **kwargs) -> dict:
    """The evening's call: a warning never fails a night. Anything the
    collector did not name becomes a block whose every row was not checked."""
    tickets = list(tickets)
    try:
        block = collect(tickets, session, **kwargs)
        problems = block_faults(block, block["session"], tickets)
        if problems:
            raise ValueError(problems[0])
        return block
    except Exception as exc:  # noqa: BLE001 - an annotation must never stop a publication
        session = _day(session).isoformat()
        now = kwargs.get("now") or datetime.now(timezone.utc)
        rows = [_row(t, session, window(session), now, reason="not_checked") for t in tickets]
        block = {"version": VERSION, "policy": POLICY, "source": SOURCE, "session": session,
                 "status": _status(rows), "mapping": None, "rows": rows, "counts": _counts(rows),
                 "requests": 0, "internal": type(exc).__name__}
        block["sentence"] = block_sentence(block)
        return block


def carried(previous_block, session, tickets, **kwargs) -> dict:
    """A closed night re-presents the previous session's tickets verbatim, and
    their warnings with them as that publication read them; a previous block
    that is not those tickets' is read again."""
    tickets = list(tickets)
    if isinstance(previous_block, dict) and not block_faults(previous_block, _day(session).isoformat(), tickets):
        return previous_block
    return safe_collect(tickets, session, **kwargs)


# ------------------------------------------------------------ validation ---
BLOCK_KEYS = {"version", "policy", "source", "session", "status", "mapping", "rows", "counts", "requests", "sentence"}
ROW_KEYS = {"stage", "ticker", "session", "window", "cik", "issuer", "sources", "error", "retrieved_at",
            "results_filings", "coverage_start", "foreign", "verdict", "placement", "projection", "observed",
            "reason", "sentence"}
SOURCE_KEYS = {"url", "sha256", "bytes", "retrieved_at"}
FILING_KEYS = {"accession", "filing_date", "accepted_at"}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def block_faults(block, session, tickets=None) -> list[str]:
    """The block's shape one level in, and every read row re-derived from the
    inputs it retains; ``tickets`` the record's own, in order. Names faults;
    never raises."""
    try:
        return _faults(block, session, tickets)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
        return [f"earnings block is malformed ({type(exc).__name__})"]


def _source_ok(value) -> bool:
    if not (isinstance(value, dict) and set(value) == SOURCE_KEYS and isinstance(value["url"], str)
            and isinstance(value["sha256"], str) and SHA256.fullmatch(value["sha256"])
            and type(value["bytes"]) is int and value["bytes"] > 0):
        return False
    _instant(value["retrieved_at"])
    return True


def _faults(block, session, tickets) -> list[str]:
    if not isinstance(block, dict) or not BLOCK_KEYS <= set(block) <= BLOCK_KEYS | {"internal"}:
        return ["earnings block keys"]
    out = []
    if type(block["version"]) is not int or block["version"] != VERSION:
        return ["earnings block version"]
    if block["policy"] != POLICY or block["source"] != SOURCE:
        out.append("earnings block policy or source")
    if block["session"] != session:
        out.append("earnings block session differs from the run's")
        return out
    rows = block["rows"]
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        return out + ["earnings rows are not a list of objects"]
    if type(block["requests"]) is not int or block["requests"] < 0:
        out.append("earnings request count")
    if block["mapping"] is not None and not _source_ok(block["mapping"]):
        out.append("earnings mapping source")
    if "internal" in block and not isinstance(block["internal"], str):
        out.append("earnings internal failure word")
    days = window(session)
    for r in rows:
        if set(r) != ROW_KEYS:
            out.append(f"earnings row keys for {r.get('ticker')!r}")
            continue
        name = r["ticker"]
        if r["stage"] not in STAGES or not isinstance(name, str) or not name:
            out.append("earnings row identity")
            continue
        if r["session"] != session or r["window"] != days:
            out.append(f"earnings window for {name} is not the plan's hold")
        if r["verdict"] not in VERDICTS or r["reason"] not in UNKNOWN_REASONS + (None,) \
                or (r["verdict"] == "unknown") != (r["reason"] is not None):
            out.append(f"earnings verdict for {name}")
            continue
        _instant(r["retrieved_at"])
        filings = r["results_filings"]
        if (not isinstance(filings, list) or len(filings) > MAX_RESULTS_FILINGS
                or not all(isinstance(f, dict) and set(f) == FILING_KEYS and isinstance(f["accession"], str)
                           and ACCESSION.fullmatch(f["accession"]) and _day(f["filing_date"])
                           and (f["accepted_at"] is None or _instant(f["accepted_at"])) for f in filings)):
            out.append(f"earnings results filings for {name}")
            continue
        if (not isinstance(r["foreign"], bool) or not isinstance(r["sources"], list)
                or not all(_source_ok(x) for x in r["sources"])
                or not (r["error"] is None or isinstance(r["error"], str))
                or not (r["cik"] is None or (type(r["cik"]) is int and r["cik"] > 0))
                or not (r["issuer"] is None or isinstance(r["issuer"], str))
                or not (r["coverage_start"] is None or _day(r["coverage_start"]))):
            out.append(f"earnings row fields for {name}")
            continue
        if r["reason"] in ASSESSED_REASONS:
            if not r["sources"] or r["cik"] is None:
                out.append(f"earnings row for {name} carries a finding without its source")
                continue
            expected = assess(filings, session, days, r["retrieved_at"], r["coverage_start"], r["foreign"])
            moved = [k for k in ("verdict", "placement", "projection", "observed", "reason") if r[k] != expected[k]]
            if moved:
                out.append(f"earnings {moved[0]} for {name} is not what its filings give")
        elif (filings or r["sources"] or r["coverage_start"] is not None or r["foreign"]
              or r["projection"] is not None or r["observed"] is not None or r["placement"] is not None):
            out.append(f"earnings row for {name} carries a finding beside an unread source")
        if r["sentence"] != sentence(r):
            out.append(f"earnings sentence for {name}")
    if tickets is not None and [(r.get("stage"), r.get("ticker")) for r in rows] != \
            [(t["stage"], t["ticker"]) for t in tickets]:
        out.append("earnings rows are not the record's tickets")
    if block["status"] != _status(rows):
        out.append("earnings status is not what its rows give")
    if block["counts"] != _counts(rows):
        out.append("earnings counts")
    if block["sentence"] != block_sentence(block):
        out.append("earnings sentence")
    return out


def record_faults(data) -> list[str]:
    """Asked by ``report.validate()`` only under rules that archive this module."""
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, dict) or "earnings_risk" not in rules:
        return []
    run = data.get("run") if isinstance(data.get("run"), dict) else {}
    if "earnings" not in run:
        return ["run.earnings is missing under rules that write it"]
    watchlist = data.get("watchlist") if isinstance(data.get("watchlist"), dict) else {}
    tickets = tickets_of(data.get("bursts") if isinstance(data.get("bursts"), list) else [],
                         data.get("trades") if isinstance(data.get("trades"), list) else [],
                         watchlist.get("top") if isinstance(watchlist.get("top"), list) else [])
    return [f"run.{f}" for f in block_faults(run["earnings"], run.get("session"), tickets)]
