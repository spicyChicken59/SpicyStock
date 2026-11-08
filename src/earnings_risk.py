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
  the signal session's scheduled close and before the run read SEC (the
  release it furnishes may have come earlier: acceptance is the latest it
  could have been);
* ``estimate_inside`` -- the estimate falls inside the window;
* ``estimate_near`` -- the estimate's range reaches the window's days;
* ``overdue`` -- the estimate's range ended before day 1 and no results
  filing has come since, or none has come for longer than any gap between
  the issuer's own results filings, so a report could come any day;
* ``already_reported`` -- this cycle's results were filed on or before the
  signal session; the next report is about a quarter away (an inference);
* ``estimate_outside`` -- the estimate falls outside the window;
* ``unknown`` with a reason -- never clearance.

Version 2 reads one more thing off the same filing list, at no extra request:
the ticket's recent current reports (form 8-K and its amendments) filed within
``RECENT_REPORT_DAYS`` before the signal session or since it, and the item
codes each carries. An item in ``MATERIAL_ITEMS`` -- a material definitive
agreement, a completed acquisition or disposition, a delisting notice, a change
in control, a bankruptcy -- is the kind of event a cash acquisition or a
delisting announces first, and the row says so with the filing named; every
other code is listed by its heading. An item names a KIND of event and never
what the filing says: the words tell the reader to read it, and the warning
withholds nothing. A record made under version 1 is read under version 1.

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

VERSION = 2
VERSIONS = (1, 2)            # the versions a record can archive and this module can read
POLICY = "warn_only"
SOURCE = "sec_edgar_submissions"
COVERAGE = "sec_results_filings_derived"
RESULTS_FORM = "8-K"
RESULTS_ITEM = "2.02"
FOREIGN_FORMS = ("6-K", "6-K/A", "20-F", "20-F/A", "40-F", "40-F/A")
CURRENT_REPORT_FORMS = ("8-K", "8-K/A")
RECENT_REPORT_DAYS = 14      # P: a current report filed within this many calendar days before the signal, or since it, is recent
MAX_CURRENT_REPORTS = 8      # recent current reports kept per ticket, newest first; the count in the window is kept beside them
# DERIVED: the 8-K items SpicyStock warns on -- each the first filing a cash
# acquisition, a delisting or a failure tends to make -- under SEC's own item
# headings (Form 8-K; transcribed, not fetched, and a heading names a KIND of
# event, never what one filing says)
MATERIAL_ITEMS = ("1.01", "1.03", "2.01", "3.01", "5.01")
ITEM_TITLES = {
    "1.01": "Entry into a Material Definitive Agreement",
    "1.02": "Termination of a Material Definitive Agreement",
    "1.03": "Bankruptcy or Receivership",
    "1.04": "Mine Safety - Reporting of Shutdowns and Patterns of Violations",
    "1.05": "Material Cybersecurity Incidents",
    "2.01": "Completion of Acquisition or Disposition of Assets",
    "2.02": "Results of Operations and Financial Condition",
    "2.03": "Creation of a Direct Financial Obligation or an Obligation under an Off-Balance Sheet Arrangement of a Registrant",
    "2.04": "Triggering Events That Accelerate or Increase a Direct Financial Obligation or an Obligation under an Off-Balance Sheet Arrangement",
    "2.05": "Costs Associated with Exit or Disposal Activities",
    "2.06": "Material Impairments",
    "3.01": "Notice of Delisting or Failure to Satisfy a Continued Listing Rule or Standard; Transfer of Listing",
    "3.02": "Unregistered Sales of Equity Securities",
    "3.03": "Material Modification to Rights of Security Holders",
    "4.01": "Changes in Registrant's Certifying Accountant",
    "4.02": "Non-Reliance on Previously Issued Financial Statements or a Related Audit Report or Completed Interim Review",
    "5.01": "Changes in Control of Registrant",
    "5.02": "Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain Officers; Compensatory Arrangements of Certain Officers",
    "5.03": "Amendments to Articles of Incorporation or Bylaws; Change in Fiscal Year",
    "5.04": "Temporary Suspension of Trading Under Registrant's Employee Benefit Plans",
    "5.05": "Amendment to Registrant's Code of Ethics, or Waiver of a Provision of the Code of Ethics",
    "5.06": "Change in Shell Company Status",
    "5.07": "Submission of Matters to a Vote of Security Holders",
    "5.08": "Shareholder Director Nominations",
    "6.01": "ABS Informational and Computational Material",
    "6.02": "Change of Servicer or Trustee",
    "6.03": "Change in Credit Enhancement or Other External Support",
    "6.04": "Failure to Make a Required Distribution",
    "6.05": "Securities Act Updating Disclosure",
    "6.06": "Static Pool",
    "7.01": "Regulation FD Disclosure",
    "8.01": "Other Events",
    "9.01": "Financial Statements and Exhibits",
}
ITEMS_STATUSES = ("material", "listed", "none", "foreign", "not_checked")
ITEM_PLACEMENTS = ("before_signal_close", "pre_entry", "held")
PROJECTION_DAYS = 364        # DERIVED: 52 weeks, the same weekday a year on
ESTIMATE_SLACK_DAYS = 7      # P: a report a week either side of last year's is the same cycle
OVERDUE_DAYS = 45            # P: an estimate whose range ended this many days before the signal still reads as overdue
# DERIVED: how far back a projection inside the horizon can come from
REACH_DAYS = PROJECTION_DAYS + ESTIMATE_SLACK_DAYS + OVERDUE_DAYS
MAX_TICKETS = 8              # four model slots per stage; never binds on a real night
MAX_RESULTS_FILINGS = 24     # results filings kept per ticket: every one inside the reach, and the one before it
MAX_HISTORY_FILES = 1
DEADLINE_SECONDS = 60
RETRIEVAL_WINDOW_SECONDS = 7200   # P: a row's SEC read lies within two hours of its record's clock
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
HISTORY_URL = "https://data.sec.gov/submissions/{name}"
VERDICTS = ("reported_after_signal", "estimate_inside", "estimate_near", "overdue",
            "already_reported", "estimate_outside", "unknown")
UNKNOWN_REASONS = ("not_mapped", "identity_ambiguous", "foreign_issuer", "no_results_history", "no_recent_results",
                   "history_short", "filings_short", "history_not_read", "rows_unreadable", "source_unavailable",
                   "not_checked")
# the reasons a row was read for and re-derived from; the rest carry no finding
ASSESSED_REASONS = (None, "foreign_issuer", "no_results_history", "no_recent_results", "history_short",
                    "filings_short", "history_not_read")
# a reason that says SEC was not read in full; a not-mapped or ambiguous symbol is SEC's answer
UNREAD_REASONS = ("rows_unreadable", "source_unavailable", "not_checked")
PLACEMENTS = ("pre_entry", "held", "boundary", "any_day")
STATUSES = ("not_applicable", "checked", "partial", "unavailable")
STAGES = ("burst", "anticipation")
ERRORS = tuple(sorted(issuer_evidence.ERRORS | {"rows_unreadable", "not_mapped"}))

RULES = {
    "earnings_risk.version": VERSION,
    "earnings_risk.policy": POLICY,
    "earnings_risk.source": SOURCE,
    "earnings_risk.coverage": COVERAGE,
    "earnings_risk.results_form": RESULTS_FORM,
    "earnings_risk.results_item": RESULTS_ITEM,
    "earnings_risk.foreign_forms": list(FOREIGN_FORMS),
    "earnings_risk.current_report_forms": list(CURRENT_REPORT_FORMS),
    "earnings_risk.recent_report_days": RECENT_REPORT_DAYS,
    "earnings_risk.max_current_reports": MAX_CURRENT_REPORTS,
    "earnings_risk.material_items": list(MATERIAL_ITEMS),
    "earnings_risk.projection_days": PROJECTION_DAYS,
    "earnings_risk.estimate_slack_days": ESTIMATE_SLACK_DAYS,
    "earnings_risk.overdue_days": OVERDUE_DAYS,
    "earnings_risk.reach_days": REACH_DAYS,
    "earnings_risk.max_tickets": MAX_TICKETS,
    "earnings_risk.max_results_filings": MAX_RESULTS_FILINGS,
    "earnings_risk.max_history_files": MAX_HISTORY_FILES,
    "earnings_risk.deadline_seconds": DEADLINE_SECONDS,
    "earnings_risk.retrieval_window_seconds": RETRIEVAL_WINDOW_SECONDS,
    "earnings_risk.matching": "one_to_one",
    "earnings_risk.window": "plan.final_exit_day sessions after the signal session",
    "earnings_risk.unknown_policy": "never_clearance",
}

ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z")
ITEM_CODE = re.compile(r"[0-9]\.[0-9]{2}\Z")
REASON_WORDS = {
    "not_mapped": "SEC's ticker list does not name this symbol",
    "identity_ambiguous": "SEC's ticker list names this symbol for more than one company",
    "foreign_issuer": "a foreign issuer files its results on forms that carry no results item",
    "no_results_history": "no results filing (8-K item 2.02) in SEC's list",
    "no_recent_results": f"no results filing (8-K item 2.02) in the {REACH_DAYS} days before the signal",
    "history_short": f"its results filings (8-K item 2.02) begin less than {REACH_DAYS} days before the signal",
    "filings_short": f"the SEC filings read for it begin less than {REACH_DAYS} days before the signal",
    "history_not_read": f"its older SEC filing list could not be read, so its filings do not reach back {REACH_DAYS} days",
    "rows_unreadable": "SEC's filing list could not be read",
    "source_unavailable": "SEC did not answer",
    "not_checked": "not checked in this run",
}


# an injected ``fetch(url) -> bytes`` (tests, the fixture generator); None reads SEC
FETCH = None


class SourceError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code if code in ERRORS else "invalid_response"


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
    try:
        return parsed.astimezone(timezone.utc)
    except OverflowError:
        raise ValueError("earnings instant out of range") from None


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


def _brief(f) -> dict:
    return {"accession": f["accession"], "filing_date": f["filing_date"].isoformat(), "accepted_at": f["accepted_at"]}


def assess(filings, session, days, retrieved_at, coverage_start, foreign, history_error=None) -> dict:
    """One ticket's verdict from its results filings. Pure: every input is
    retained on the row, so the validator re-derives it.

    SEC is read as it stood at the earlier of the retrieval and the hold's last
    close, so a later run reading a backfilled session sees what the hold saw.
    Each of this year's filings reports at most one of last year's (one-to-one,
    earliest first), so a preliminary release cannot also stand for the full
    results still to come."""
    signal = _day(session)
    days = [_day(d) for d in days]
    retrieved = _instant(retrieved_at)
    first, last = days[0], days[-1]
    slack = timedelta(days=ESTIMATE_SLACK_DAYS)
    close, day1_open, last_close = sessions.hours(signal)[1], sessions.hours(first)[0], sessions.hours(last)[1]
    seen_until = min(retrieved, last_close)
    rows = sorted(({"accession": f["accession"], "filing_date": _day(f["filing_date"]),
                    "accepted_at": f.get("accepted_at")} for f in filings),
                  key=lambda f: (f["filing_date"], f["accession"]))
    rows = [f for f in rows if f["filing_date"] <= seen_until.astimezone(sessions.MARKET_TZ).date()
            and (f["accepted_at"] is None or _instant(f["accepted_at"]) <= seen_until)]
    out = {"verdict": "unknown", "placement": None, "projection": None, "observed": None, "reason": None}

    observed = sorted((f for f in rows if f["accepted_at"] and close < _instant(f["accepted_at"])),
                      key=lambda f: _instant(f["accepted_at"]))
    if observed:
        hit = observed[0]
        out.update(verdict="reported_after_signal",
                   placement="pre_entry" if _instant(hit["accepted_at"]) < day1_open else "held",
                   observed=_brief(hit))
        return out

    needed = signal - timedelta(days=REACH_DAYS)
    if coverage_start is None or _day(coverage_start) > needed:
        out["reason"] = "history_not_read" if history_error else "filings_short"
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

    def q_of(anchor):
        return anchor["filing_date"] + timedelta(days=PROJECTION_DAYS)

    def project(anchor):
        q = q_of(anchor)
        return {"date": q.isoformat(), "low": (q - slack).isoformat(), "high": (q + slack).isoformat(),
                "from_accession": anchor["accession"], "from_filing_date": anchor["filing_date"].isoformat(),
                "slack_days": ESTIMATE_SLACK_DAYS, "timing_last_year": timing_of(_brief(anchor))}

    horizon_low = signal - timedelta(days=OVERDUE_DAYS) - slack
    anchors = sorted((a for a in rows if q_of(a) >= horizon_low), key=lambda a: (q_of(a), a["accession"]))
    used, matched, unmatched = set(), [], []
    for anchor in anchors:
        q = q_of(anchor)
        match = next((f for f in rows if f["filing_date"] >= q - slack and f["accession"] not in used), None)
        if match is not None:
            used.add(match["accession"])
            matched.append((anchor, match))
        else:
            unmatched.append(anchor)
    inside = [a for a in unmatched if signal <= q_of(a) <= last]
    near = [a for a in unmatched if a not in inside and q_of(a) - slack <= last and q_of(a) + slack >= first]
    late = [a for a in unmatched if q_of(a) + slack < first]
    later = [a for a in unmatched if q_of(a) - slack > last]
    newest = rows[-1]
    gaps = [(b["filing_date"] - a["filing_date"]).days for a, b in zip(rows, rows[1:])]
    cadence_late = bool(gaps) and (signal - newest["filing_date"]).days > max(gaps) + ESTIMATE_SLACK_DAYS
    if inside:
        out.update(verdict="estimate_inside", placement="pre_entry" if q_of(inside[0]) < first else "held",
                   projection=project(inside[0]))
    elif near:
        out.update(verdict="estimate_near", placement="boundary", projection=project(near[0]))
    elif late:
        out.update(verdict="overdue", placement="any_day", projection=project(late[-1]))
    elif cadence_late:
        out.update(verdict="overdue", placement="any_day", observed=_brief(newest))
    elif matched:
        anchor, filed = matched[-1]
        out.update(verdict="already_reported", projection=project(anchor), observed=_brief(filed))
    else:
        out.update(verdict="estimate_outside", projection=project(later[0]) if later else None)
    return out


# ------------------------------------------------- the current reports ---
PLACEMENT_WORDS = {"before_signal_close": "before the signal session's close",
                   "pre_entry": "after the signal session's close and before day 1's open",
                   "held": "during this ticket's hold window"}
MATERIAL_WORDS = {"1.01": "a material agreement", "1.03": "a bankruptcy", "2.01": "a completed acquisition or disposition",
                  "3.01": "a delisting notice", "5.01": "a change in control"}
ITEMS_WORDS = {"material": "with a material item", "listed": "with other items only", "none": "with none",
               "foreign": "a foreign issuer whose reports carry no items", "not_checked": "not checked"}


def _parse_items(value: str) -> list[str]:
    """The item codes of one current report, each ``N.NN`` as SEC writes them;
    a token in another shape is left out, so every code a row carries is one
    the validator can hold."""
    codes: list[str] = []
    for token in value.split(","):
        code = token.strip()
        if ITEM_CODE.fullmatch(code) and code not in codes:
            codes.append(code)
    return codes


def _recent_reports(reports, session) -> tuple[list[dict], int]:
    """The current reports filed within ``RECENT_REPORT_DAYS`` before the signal
    or since it, newest first (the filing date, then the accession), the newest
    ``MAX_CURRENT_REPORTS`` kept and the whole count beside them."""
    since = (_day(session) - timedelta(days=RECENT_REPORT_DAYS)).isoformat()
    recent = sorted((r for r in reports if r["filing_date"] >= since),
                    key=lambda r: (r["filing_date"], r["accession"]), reverse=True)
    return recent[:MAX_CURRENT_REPORTS], len(recent)


def _item_placement(report, close, day1_open) -> str:
    """Where a filing fell against the hold: by its acceptance when SEC
    recorded one, else by its filing date."""
    if report.get("accepted_at"):
        moment = _instant(report["accepted_at"])
        return "before_signal_close" if moment <= close else "pre_entry" if moment < day1_open else "held"
    filed = _day(report["filing_date"])
    if filed <= close.astimezone(sessions.MARKET_TZ).date():
        return "before_signal_close"
    return "pre_entry" if filed < day1_open.astimezone(sessions.MARKET_TZ).date() else "held"


def items_of(reports, count, session, days, retrieved_at, foreign) -> dict:
    """One ticket's current-report items from the reports its row retains and
    the count the window held. Pure, so the validator re-derives it. SEC is
    read as it stood at the earlier of the retrieval and the hold's last
    close, as ``assess()`` reads the results filings."""
    signal = _day(session)
    days = [_day(d) for d in days]
    retrieved = _instant(retrieved_at)
    close, day1_open, last_close = sessions.hours(signal)[1], sessions.hours(days[0])[0], sessions.hours(days[-1])[1]
    seen_until = min(retrieved, last_close)
    seen_day = seen_until.astimezone(sessions.MARKET_TZ).date()
    rows = sorted(reports, key=lambda r: (r["filing_date"], r["accession"]), reverse=True)
    rows = [r for r in rows if _day(r["filing_date"]) <= seen_day
            and (r.get("accepted_at") is None or _instant(r["accepted_at"]) <= seen_until)]
    material = [{"item": code, "title": ITEM_TITLES[code], "accession": r["accession"], "filing_date": r["filing_date"],
                 "accepted_at": r.get("accepted_at"), "placement": _item_placement(r, close, day1_open)}
                for r in rows for code in r["items"] if code in MATERIAL_ITEMS]
    codes = sorted({code for r in rows for code in r["items"]})
    status = "material" if material else "listed" if rows else "foreign" if foreign else "none"
    out = {"status": status, "material": material, "codes": codes, "seen": len(rows),
           "count": len(reports) if count is None else count, "reason": None}
    out["sentence"] = items_sentence(out)
    return out


def _items_unread(reason) -> dict:
    out = {"status": "not_checked", "material": [], "codes": [], "seen": 0, "count": None, "reason": reason}
    out["sentence"] = items_sentence(out)
    return out


def _code_words(codes) -> str:
    return ", ".join(f"{c} ({ITEM_TITLES[c]})" if c in ITEM_TITLES else c for c in codes)


def _material_kinds() -> str:
    kinds = [f"{MATERIAL_WORDS[c]} ({c})" for c in MATERIAL_ITEMS]
    return ", ".join(kinds[:-1]) + " or " + kinds[-1]


def items_sentence(items) -> str:
    """What the page and the mail print under the earnings sentence, verbatim."""
    status = items["status"]
    if status == "not_checked":
        return f"Recent SEC current reports not checked: {REASON_WORDS[items['reason']]}."
    tail = " SEC filings are not news coverage."
    span = f"in the {RECENT_REPORT_DAYS} days before the signal or since"
    if status == "foreign":
        return f"Recent SEC current reports: a foreign issuer's reports (6-K) carry no item codes, so none was read.{tail}"
    if status == "none":
        return f"Recent SEC current reports: none (8-K) filed {span}.{tail}"
    read = f", {items['seen']} of them retained and read" if items["count"] > items["seen"] else ""
    if status == "listed":
        return (f"Recent SEC current reports: {items['count']} (8-K) filed {span}{read}, items {_code_words(items['codes'])}; "
                f"none is {_material_kinds()}.{tail}")
    found = "; ".join(f"8-K item {m['item']} ({m['title']}) filed {_long(m['filing_date'])}"
                      + (f", accepted {_et(m['accepted_at'])}" if m["accepted_at"] else "")
                      + f", {PLACEMENT_WORDS[m['placement']]}" for m in items["material"])
    others = [c for c in items["codes"] if c not in MATERIAL_ITEMS]
    return (f"Recent SEC current report: {found}. An item names a kind of event, not what the filing says: read it "
            "before entry. A warning and not a refusal; only the manual event registry withholds a ticket."
            + (f" Other items filed {span}: {_code_words(others)}." if others else ""))


def _items_counts(rows) -> dict:
    return {s: n for s in ITEMS_STATUSES
            if (n := sum(1 for r in rows if isinstance(r.get("items"), dict) and r["items"].get("status") == s))}


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
        where = ("after the signal session's close and before day 1's open" if row["placement"] == "pre_entry"
                 else f"during this ticket's hold window {span}")
        return (f"Quarterly results (8-K item 2.02) were accepted by the SEC {where} ({when}). The release they "
                "furnish may have come earlier, even before the signal session's open; if it came after that "
                "close, the entry opens on the reaction. Check the release time before entry.")
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
        if projection is None:
            return (f"No results filing (8-K item 2.02) has come since {_long(row['observed']['filing_date'])}, "
                    "longer than any gap between its earlier results filings: a report could come any day, "
                    f"including inside this ticket's hold window {span}. Check the company's announcement before entry.")
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
    lead += " An estimate warns and never withholds a ticket."
    if block.get("version") == VERSION and isinstance(block.get("items_counts"), dict):
        parts = [f"{block['items_counts'][k]} {ITEMS_WORDS[k]}" for k in ITEMS_STATUSES if block["items_counts"].get(k)]
        if parts:
            lead += (f" SEC current reports (8-K) in the {RECENT_REPORT_DAYS} days before the signal or since: "
                     + "; ".join(parts) + "; a material item names a kind of event and withholds nothing.")
    return lead


# ------------------------------------------------------------ the source ---
def _columns(value):
    """The results filings, the oldest filing date, the forms and the current
    reports (with their item codes) of one SEC filing list. The five columns it
    reads are parallel or the list is refused whole; a row it cannot read is
    left out of all four."""
    names = ("accessionNumber", "filingDate", "acceptanceDateTime", "form", "items")
    if not isinstance(value, dict) or not all(isinstance(value.get(n), list) for n in names):
        raise SourceError("rows_unreadable")
    count = len(value["accessionNumber"])
    if not all(len(value[n]) == count for n in names):
        raise SourceError("rows_unreadable")
    results, dates, forms, reports = [], [], set(), []
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
        if form in CURRENT_REPORT_FORMS:
            reports.append({"accession": accession, "filing_date": filed_day.isoformat(), "accepted_at": accepted_iso,
                            "form": form, "items": _parse_items(items)})
    return results, (min(dates) if dates else None), forms, reports


def _decode(raw):
    """SEC's JSON under the issuer collector's own bounds: a byte limit, no
    duplicate key, no non-finite number."""
    try:
        return issuer_evidence._decode(raw, issuer_evidence.MAX_RESPONSE_BYTES)
    except (ValueError, TypeError, RecursionError):
        raise SourceError("rows_unreadable") from None


def parse_mapping(raw) -> dict:
    """SEC's ticker mapping, each symbol to the companies it names. A mapping
    that cannot be read is SEC's answer failing, never a symbol it lacks."""
    try:
        value = issuer_evidence._decode(raw, issuer_evidence.MAX_RESPONSE_BYTES)
        fields, data = value["fields"], value["data"]
        if not (isinstance(fields, list) and len(set(fields)) == len(fields)
                and all(k in fields for k in ("cik", "name", "ticker")) and isinstance(data, list)):
            raise SourceError("invalid_response")
        out: dict = {}
        for row in data:
            if not (isinstance(row, list) and len(row) == len(fields)):
                raise SourceError("invalid_response")
            item = dict(zip(fields, row))
            if not (isinstance(item["ticker"], str) and type(item["cik"]) is int and 0 < item["cik"] < 10**10
                    and isinstance(item["name"], str) and item["name"]):
                continue
            pair = {"cik": item["cik"], "name": item["name"]}
            if pair not in out.setdefault(item["ticker"], []):
                out[item["ticker"]].append(pair)
        if not out:
            raise SourceError("invalid_response")
        return out
    except SourceError:
        raise
    except (KeyError, TypeError, ValueError, RecursionError):
        raise SourceError("invalid_response") from None


def parse_submissions(raw: bytes, cik: int, ticker: str):
    value = _decode(raw)
    try:
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
    except (KeyError, TypeError, AttributeError):
        raise SourceError("rows_unreadable") from None
    results, start, forms, reports = _columns(recent)
    history = []
    for item in files:
        try:
            name = item["name"]
            if isinstance(name, str) and re.fullmatch(f"CIK{cik:010d}-submissions-[0-9]{{3}}\\.json", name):
                history.append({"name": name, "filing_to": _day(item["filingTo"]).isoformat()})
        except (KeyError, TypeError, ValueError):
            continue
    return {"results": results, "coverage_start": start, "forms": forms, "history": history, "reports": reports}


def _budget(seconds):
    class Budget(issuer_evidence._Budget):
        def remaining(self):
            return seconds - (time.monotonic() - self.started)
    return Budget()


def _default_fetch(seconds):
    """SEC through the issuer collector's own transport (its User-Agent, its
    spacing, its bounds, no redirect). Every failure it can raise is a named
    source error, so one failed request is one ticket's unknown row."""
    import http.client
    transport, budget = issuer_evidence._Transport(None), _budget(seconds)

    def fetch(url):
        try:
            return transport.fetch(url, budget)["body"]
        except issuer_evidence.SourceError as exc:
            raise SourceError(exc.code) from None
        except (http.client.HTTPException, OSError):
            raise SourceError("network_error") from None
        except Exception:  # noqa: BLE001 - a bound or a shape the transport refused
            raise SourceError("invalid_response") from None
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
    # a shape the record should never carry is no ticket, never a raise: the
    # validator reads this over whatever a file holds
    named = lambda row: isinstance(row, dict) and isinstance(row.get("ticker"), str) and isinstance(row.get("plan"), dict)
    trades = {t for t in trades if isinstance(t, str)} if isinstance(trades, list) else set()
    out = [{"stage": "burst", "ticker": row["ticker"]} for row in (bursts if isinstance(bursts, list) else [])
           if named(row) and row["ticker"] in trades]
    out += [{"stage": "anticipation", "ticker": row["ticker"]} for row in (top if isinstance(top, list) else [])
            if named(row) and row["plan"].get("eligible") and isinstance(row["plan"].get("action"), str)
            and row["plan"]["action"] in plan_module.ORDER_ACTIONS]
    return out


def _counts(rows) -> dict:
    return {v: n for v in VERDICTS if (n := sum(1 for r in rows if r.get("verdict") == v))}


def _status(rows) -> str:
    if not rows:
        return "not_applicable"
    unread = sum(1 for r in rows if r.get("reason") in UNREAD_REASONS)
    return "unavailable" if unread == len(rows) else "partial" if unread else "checked"


def _row(ticket, session, days, retrieved, result=None, *, reason=None, error=None, cik=None, issuer=None,
         sources=(), filings=(), coverage_start=None, foreign=False, reports=(), report_count=None):
    row = {"stage": ticket["stage"], "ticker": ticket["ticker"], "session": session, "window": days,
           "cik": cik, "issuer": issuer, "sources": list(sources), "error": error, "retrieved_at": _iso(retrieved),
           "results_filings": list(filings), "coverage_start": coverage_start, "foreign": foreign,
           "current_reports": list(reports), "current_report_count": report_count}
    if result is None:
        row.update(verdict="unknown", placement=None, projection=None, observed=None, reason=reason)
    else:
        row.update(result)
    # the current reports are read where the results filings were: a row whose
    # source was read in full carries its items, an unread one says so
    row["items"] = (items_of(row["current_reports"], report_count, session, days, row["retrieved_at"], foreign)
                    if row["reason"] in ASSESSED_REASONS else _items_unread(row["reason"]))
    row["sentence"] = sentence(row)
    return row


def _kept(results, needed) -> list[dict]:
    """Every results filing inside the reach and the newest one before it,
    which shows the list reaches back; the newest ``MAX_RESULTS_FILINGS``."""
    results = sorted(results, key=lambda r: (r["filing_date"], r["accession"]))
    inside = [r for r in results if _day(r["filing_date"]) >= needed]
    before = [r for r in results if _day(r["filing_date"]) < needed][-1:]
    return (before + inside)[-MAX_RESULTS_FILINGS:]


def _read(get, cik, ticker, session, clock_now):
    """One issuer's results filings from its SEC list, and the older file when
    the recent one does not reach back far enough. A failed older file leaves
    the recent rows, read as ``history_not_read``, with its error named. The
    recent current reports come from the recent file alone, which holds a
    filer's newest thousand filings: the window never reaches past them."""
    url = SUBMISSIONS_URL.format(cik=cik)
    raw = get(url)
    retrieved = clock_now()
    parsed = parse_submissions(raw, cik, ticker)
    sources, error = [_source(url, raw, retrieved)], None
    results, start = list(parsed["results"]), parsed["coverage_start"]
    needed = _day(session) - timedelta(days=REACH_DAYS)
    older = sorted((h for h in parsed["history"] if _day(h["filing_to"]) >= needed),
                   key=lambda h: (h["filing_to"], h["name"]), reverse=True)[:MAX_HISTORY_FILES]
    if (start is None or start > needed) and older:
        url = HISTORY_URL.format(name=older[0]["name"])
        try:
            hraw = get(url)
            more, hstart, hforms, _ = _columns(_decode(hraw))
        except SourceError as exc:
            error = exc.code
        else:
            sources.append(_source(url, hraw, clock_now()))
            known = {r["accession"] for r in results}
            results += [r for r in more if r["accession"] not in known]
            parsed["forms"] |= hforms
            if hstart is not None:
                start = hstart if start is None else min(start, hstart)
    reports, report_count = _recent_reports(parsed["reports"], session)
    return {"filings": _kept(results, needed), "coverage_start": start.isoformat() if start else None,
            "foreign": bool(parsed["forms"] & set(FOREIGN_FORMS)), "sources": sources,
            "retrieved": retrieved, "error": error, "reports": reports, "report_count": report_count}


def collect(tickets, session, *, fetch=None, now=None, deadline_seconds=DEADLINE_SECONDS, _state=None) -> dict:
    """One evening's warnings. ``fetch(url) -> bytes`` raises
    :class:`SourceError` on failure; None reads SEC. A source failure is an
    unknown row, never a raise; ``safe_collect()`` catches the rest."""
    session = _day(session).isoformat()
    days = window(session)
    clock_now = (lambda: now) if now is not None else (lambda: datetime.now(timezone.utc))
    tickets = list(tickets)
    block = {"version": VERSION, "policy": POLICY, "source": SOURCE, "session": session,
             "status": "not_applicable", "mapping": None, "rows": [], "counts": {}, "items_counts": {}, "requests": 0}
    if _state is not None:
        _state["block"] = block
    if tickets:
        started = time.monotonic()
        fetch = fetch or FETCH or _default_fetch(deadline_seconds)

        def get(url):
            if time.monotonic() - started >= deadline_seconds:
                raise SourceError("time_budget")
            block["requests"] += 1
            return fetch(url)

        mapping, mapping_error, read = None, None, {}
        try:
            raw = get(issuer_evidence.MAPPING_URL)
            block["mapping"] = _source(issuer_evidence.MAPPING_URL, raw, clock_now())
            mapping = parse_mapping(raw)
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
            identities = mapping.get(ticket["ticker"], [])
            if len(identities) != 1:
                block["rows"].append(_row(ticket, session, days, clock_now(),
                                          reason="not_mapped" if not identities else "identity_ambiguous"))
                continue
            cik, issuer = identities[0]["cik"], identities[0]["name"]
            try:
                if ticket["ticker"] not in read:
                    read[ticket["ticker"]] = _read(get, cik, ticket["ticker"], session, clock_now)
                got = read[ticket["ticker"]]
                result = assess(got["filings"], session, days, _iso(got["retrieved"]), got["coverage_start"],
                                got["foreign"], got["error"])
                row = _row(ticket, session, days, got["retrieved"], result, cik=cik, issuer=issuer,
                           sources=got["sources"], error=got["error"], filings=got["filings"],
                           coverage_start=got["coverage_start"], foreign=got["foreign"],
                           reports=got["reports"], report_count=got["report_count"])
            except SourceError as exc:
                reason = exc.code if exc.code in ("not_mapped", "rows_unreadable") else "source_unavailable"
                row = _row(ticket, session, days, clock_now(), reason=reason, cik=cik, issuer=issuer,
                           error=exc.code if reason == "source_unavailable" else None)
            block["rows"].append(row)
    block["status"] = _status(block["rows"])
    block["counts"] = _counts(block["rows"])
    block["items_counts"] = _items_counts(block["rows"])
    block["sentence"] = block_sentence(block)
    return block


def safe_collect(tickets, session, **kwargs) -> dict:
    """The evening's call: a warning never fails a night. Anything the
    collector did not name becomes a block whose every row was not checked,
    with the requests it had already made counted."""
    tickets = list(tickets)
    state: dict = {}
    try:
        block = collect(tickets, session, _state=state, **kwargs)
        problems = block_faults(block, block["session"], tickets)
        if problems:
            raise ValueError(problems[0])
        return block
    except Exception as exc:  # noqa: BLE001 - an annotation must never stop a publication
        session = _day(session).isoformat()
        now = kwargs.get("now") or datetime.now(timezone.utc)
        rows = [_row(t, session, window(session), now, reason="not_checked") for t in tickets]
        made = (state.get("block") or {}).get("requests", 0)
        block = {"version": VERSION, "policy": POLICY, "source": SOURCE, "session": session,
                 "status": _status(rows), "mapping": None, "rows": rows, "counts": _counts(rows),
                 "items_counts": _items_counts(rows), "requests": made if type(made) is int else 0,
                 "internal": type(exc).__name__}
        block["sentence"] = block_sentence(block)
        return block


def carried(previous_block, session, tickets, **kwargs) -> dict:
    """A closed night re-presents the previous session's tickets verbatim, and
    their warnings with them as that publication read them; a previous block
    that is not those tickets', or one written under an older version, is read
    again."""
    tickets = list(tickets)
    if isinstance(previous_block, dict) and not block_faults(previous_block, _day(session).isoformat(), tickets):
        return previous_block
    return safe_collect(tickets, session, **kwargs)


# ------------------------------------------------------------ validation ---
BLOCK_KEYS_V1 = {"version", "policy", "source", "session", "status", "mapping", "rows", "counts", "requests", "sentence"}
BLOCK_KEYS = BLOCK_KEYS_V1 | {"items_counts"}
ROW_KEYS_V1 = {"stage", "ticker", "session", "window", "cik", "issuer", "sources", "error", "retrieved_at",
               "results_filings", "coverage_start", "foreign", "verdict", "placement", "projection", "observed",
               "reason", "sentence"}
ROW_KEYS = ROW_KEYS_V1 | {"current_reports", "current_report_count", "items"}
SOURCE_KEYS = {"url", "sha256", "bytes", "retrieved_at"}
FILING_KEYS = {"accession", "filing_date", "accepted_at"}
REPORT_KEYS = {"accession", "filing_date", "accepted_at", "form", "items"}
ITEMS_KEYS = {"status", "material", "codes", "seen", "count", "reason", "sentence"}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def block_faults(block, session, tickets=None, published_at=None, version=VERSION) -> list[str]:
    """The block's shape one level in, and every read row re-derived from the
    inputs it retains; ``tickets`` the record's own, in order; with
    ``published_at``, every SEC read held between the signal session's close
    and ``RETRIEVAL_WINDOW_SECONDS`` after the record's clock; ``version`` the
    one the record's rules archived, so a version-1 block is held to version
    1's shape and nothing else. Names faults; never raises."""
    try:
        return _faults(block, session, tickets, published_at, version)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, ArithmeticError, RecursionError) as exc:
        return [f"earnings block is malformed ({type(exc).__name__})"]


def _report_ok(value) -> bool:
    return (isinstance(value, dict) and set(value) == REPORT_KEYS and isinstance(value["accession"], str)
            and ACCESSION.fullmatch(value["accession"]) is not None and bool(_day(value["filing_date"]))
            and (value["accepted_at"] is None or bool(_instant(value["accepted_at"])))
            and value["form"] in CURRENT_REPORT_FORMS and isinstance(value["items"], list)
            and all(isinstance(c, str) and ITEM_CODE.fullmatch(c) for c in value["items"])
            and len(set(value["items"])) == len(value["items"]))


def _items_faults(r, session, days, name):
    """A version-2 row's current reports and items, one level in and re-derived."""
    reports, count, items = r["current_reports"], r["current_report_count"], r["items"]
    if not isinstance(reports, list) or len(reports) > MAX_CURRENT_REPORTS or not all(_report_ok(x) for x in reports):
        return f"earnings current reports for {name}"
    if not (isinstance(items, dict) and set(items) == ITEMS_KEYS):
        return f"earnings current-report items for {name}"
    if r["reason"] in ASSESSED_REASONS:
        since = (_day(session) - timedelta(days=RECENT_REPORT_DAYS)).isoformat()
        if (type(count) is not int or count < len(reports)
                or reports != sorted(reports, key=lambda x: (x["filing_date"], x["accession"]), reverse=True)
                or any(x["filing_date"] < since for x in reports)
                or len({x["accession"] for x in reports}) != len(reports)):
            return f"earnings current reports for {name} are not the recent window's"
        if items != items_of(reports, count, session, days, r["retrieved_at"], r["foreign"]):
            return f"earnings current-report items for {name} are not what its reports give"
    elif reports or count is not None or items != _items_unread(r["reason"]):
        return f"earnings current reports for {name} beside an unread source"
    return None


def _source_ok(value, url, bounds) -> bool:
    if not (isinstance(value, dict) and set(value) == SOURCE_KEYS and value["url"] == url
            and isinstance(value["sha256"], str) and SHA256.fullmatch(value["sha256"])
            and type(value["bytes"]) is int and value["bytes"] > 0):
        return False
    return _within(value["retrieved_at"], bounds)


def _within(instant, bounds) -> bool:
    moment = _instant(instant)
    return bounds is None or bounds[0] < moment <= bounds[1]


def _faults(block, session, tickets, published_at, version) -> list[str]:
    if version not in VERSIONS:
        return ["earnings rules version"]
    block_keys, row_keys = (BLOCK_KEYS, ROW_KEYS) if version >= 2 else (BLOCK_KEYS_V1, ROW_KEYS_V1)
    if not isinstance(block, dict) or not block_keys <= set(block) <= block_keys | {"internal"}:
        return ["earnings block keys"]
    out = []
    if type(block["version"]) is not int or block["version"] != version:
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
    bounds = None
    if published_at is not None:
        bounds = (sessions.hours(_day(session))[1],
                  _instant(published_at) + timedelta(seconds=RETRIEVAL_WINDOW_SECONDS))
    if block["mapping"] is not None and not _source_ok(block["mapping"], issuer_evidence.MAPPING_URL, bounds):
        out.append("earnings mapping source")
    if "internal" in block and not isinstance(block["internal"], str):
        out.append("earnings internal failure word")
    days = window(session)
    for r in rows:
        if set(r) != row_keys:
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
        if not _within(r["retrieved_at"], bounds):
            out.append(f"earnings read for {name} lies outside its session's close and its record's clock")
        filings = r["results_filings"]
        if (not isinstance(filings, list) or len(filings) > MAX_RESULTS_FILINGS
                or not all(isinstance(f, dict) and set(f) == FILING_KEYS and isinstance(f["accession"], str)
                           and ACCESSION.fullmatch(f["accession"]) and _day(f["filing_date"])
                           and (f["accepted_at"] is None or _instant(f["accepted_at"])) for f in filings)):
            out.append(f"earnings results filings for {name}")
            continue
        if (not isinstance(r["foreign"], bool) or not isinstance(r["sources"], list)
                or not (r["error"] is None or r["error"] in ERRORS)
                or not (r["cik"] is None or (type(r["cik"]) is int and 0 < r["cik"] < 10**10))
                or not (r["issuer"] is None or isinstance(r["issuer"], str))
                or not (r["coverage_start"] is None or _day(r["coverage_start"]))):
            out.append(f"earnings row fields for {name}")
            continue
        if r["reason"] in ASSESSED_REASONS:
            history = f"CIK{r['cik']:010d}-submissions-" if r["cik"] else None
            urls_ok = (r["cik"] is not None and 1 <= len(r["sources"]) <= 1 + MAX_HISTORY_FILES
                       and _source_ok(r["sources"][0], SUBMISSIONS_URL.format(cik=r["cik"]), bounds)
                       and r["sources"][0]["retrieved_at"] == r["retrieved_at"]
                       and all(isinstance(x, dict) and isinstance(x.get("url"), str)
                               and re.fullmatch(re.escape(HISTORY_URL.format(name=history)) + r"[0-9]{3}\.json", x["url"])
                               and _source_ok(x, x["url"], bounds) for x in r["sources"][1:]))
            if not urls_ok:
                out.append(f"earnings row for {name} carries a finding without its SEC source")
                continue
            expected = assess(filings, session, days, r["retrieved_at"], r["coverage_start"], r["foreign"], r["error"])
            moved = [k for k in ("verdict", "placement", "projection", "observed", "reason") if r[k] != expected[k]]
            if moved:
                out.append(f"earnings {moved[0]} for {name} is not what its filings give")
        elif (filings or r["sources"] or r["coverage_start"] is not None or r["foreign"]
              or r["projection"] is not None or r["observed"] is not None or r["placement"] is not None):
            out.append(f"earnings row for {name} carries a finding beside an unread source")
        if version >= 2:
            fault = _items_faults(r, session, days, name)
            if fault:
                out.append(fault)
        if r["sentence"] != sentence(r):
            out.append(f"earnings sentence for {name}")
    if tickets is not None and [(r.get("stage"), r.get("ticker")) for r in rows] != \
            [(t["stage"], t["ticker"]) for t in tickets]:
        out.append("earnings rows are not the record's tickets")
    if block["status"] != _status(rows):
        out.append("earnings status is not what its rows give")
    if block["counts"] != _counts(rows):
        out.append("earnings counts")
    if version >= 2 and block["items_counts"] != _items_counts(rows):
        out.append("earnings current-report counts")
    if block["sentence"] != block_sentence(block):
        out.append("earnings sentence")
    return out


def record_faults(data) -> list[str]:
    """Asked by ``report.validate()`` only under rules that archive this module."""
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, dict) or "earnings_risk" not in rules:
        return []
    # the version the record archived decides the shape it is held to: a
    # publication made under version 1 carries no current reports and is
    # refused none; one made under version 2 must carry them
    archived = rules["earnings_risk"]
    version = archived.get("version") if isinstance(archived, dict) else None
    if type(version) is not int or version not in VERSIONS:
        return ["run.earnings rules version is unknown"]
    run = data.get("run") if isinstance(data.get("run"), dict) else {}
    if "earnings" not in run:
        return ["run.earnings is missing under rules that write it"]
    watchlist = data.get("watchlist") if isinstance(data.get("watchlist"), dict) else {}
    tickets = tickets_of(data.get("bursts"), data.get("trades"), watchlist.get("top"))
    published = run.get("published_at")
    try:
        _instant(published)
    except ValueError:
        return ["run.earnings cannot be read against the record's clock (run.published_at)"]
    return [f"run.{f}" for f in block_faults(run["earnings"], run.get("session"), tickets, published, version)]
