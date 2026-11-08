"""The earnings warning (src/earnings_risk.py): an estimate from SEC results
filings, read against each ticket's own hold window, never a refusal.

The sessions and windows below are real XNYS dates, ``plan.next_sessions``'
own answer, so Thanksgiving and its early close are the calendar's, not ours.
The synthetic filing dates ``quarters()`` writes step 91 days and are not
rolled off weekends; the rule reads a filing's date and its acceptance only.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from src import earnings_risk as E, plan, report
from tests.fakes import FakeSec

S = "2026-10-29"                       # a Thursday; its hold is Fri 30 Oct to Thu 5 Nov
NIGHT = "2026-10-29T23:00:00Z"
DAYS = E.window(S)
ACC = iter(range(1, 10**6))


def filing(day: str, accepted: str | None = "20:05:00") -> dict:
    return {"accession": f"0000939767-{int(day[2:4]):02d}-{next(ACC):06d}", "filing_date": day,
            "accepted_at": f"{day}T{accepted}Z" if accepted else None}


def quarters(anchor: str, *, through: str = S, before: int = 6) -> list[dict]:
    """Results every 91 days through ``through``, one on ``anchor``."""
    a = date.fromisoformat(anchor)
    days = [a + timedelta(days=91 * k) for k in range(-before, 8)]
    return [filing(d.isoformat()) for d in days if d <= date.fromisoformat(through)]


def verdict(filings, *, session=S, retrieved=NIGHT, start="2023-01-03", foreign=False, history_error=None):
    return E.assess(filings, session, E.window(session), retrieved, start, foreign, history_error)


# ------------------------------------------------------------------ the rule ---
def test_the_window_is_the_plans_own_hold():
    assert DAYS == [d.isoformat() for d in plan.next_sessions(date.fromisoformat(S), plan.FINAL_EXIT_DAY)]
    assert DAYS == ["2026-10-30", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"]
    # Thanksgiving is skipped and the Friday after it is a day of the hold
    assert E.window("2026-11-24") == ["2026-11-25", "2026-11-27", "2026-11-30", "2026-12-01", "2026-12-02"]


@pytest.mark.parametrize("offset, expected, placement", [
    (-1, "estimate_near", "boundary"),
    (3, "estimate_inside", "held"),
    (7, "estimate_inside", "held"),
    (1, "estimate_inside", "held"),
    (0, "estimate_inside", "pre_entry"),
    (8, "estimate_near", "boundary"),
    (14, "estimate_near", "boundary"),
    (-6, "estimate_near", "boundary"),
    (16, "estimate_outside", None),
])
def test_last_years_report_placed_against_the_hold(offset, expected, placement):
    # last year's results 364 days before the signal plus ``offset``: the estimate is S + offset
    anchor = (date.fromisoformat(S) - timedelta(days=364) + timedelta(days=offset)).isoformat()
    q = date.fromisoformat(S) + timedelta(days=offset)
    # an estimate before the signal is either still awaited or already filed;
    # these cases keep nothing filed after the anchor's quarter
    filings = quarters(anchor, through=(date.fromisoformat(S) - timedelta(days=30)).isoformat())
    got = verdict(filings)
    assert (got["verdict"], got["placement"]) == (expected, placement), (offset, got)
    assert got["projection"]["date"] == q.isoformat()
    assert got["projection"]["low"] == (q - timedelta(days=E.ESTIMATE_SLACK_DAYS)).isoformat()


def test_a_report_on_the_signal_evening_is_before_day_one():
    anchor = (date.fromisoformat(S) - timedelta(days=364)).isoformat()
    got = verdict(quarters(anchor, through="2026-09-01"))
    assert (got["verdict"], got["placement"], got["projection"]["date"]) == ("estimate_inside", "pre_entry", S)


def test_results_filed_after_the_signal_close_are_an_observed_fact():
    filings = quarters("2025-10-30", through="2026-08-01") + [filing(S, "20:30:00")]
    got = verdict(filings)
    assert (got["verdict"], got["placement"]) == ("reported_after_signal", "pre_entry")
    assert got["observed"]["accepted_at"] == f"{S}T20:30:00Z" and got["projection"] is None
    # accepted before the close is this session's own news: already reported, not after the signal
    earlier = quarters("2025-10-30", through="2026-08-01") + [filing(S, "12:00:00")]
    assert verdict(earlier)["verdict"] == "already_reported"
    # a filing accepted after the run read SEC is never named as seen after the signal
    late = quarters("2025-10-30", through="2026-08-01") + [filing(S, "23:30:00")]
    assert verdict(late)["verdict"] != "reported_after_signal"


def test_an_acceptance_at_the_close_is_not_after_it():
    # 4:00:00 PM EDT is 20:00:00 UTC: at the close, not after it; a second later is after
    base = quarters("2025-10-30", through="2026-08-01")
    assert verdict(base + [filing(S, "20:00:00")])["verdict"] == "already_reported"
    assert verdict(base + [filing(S, "20:00:01")])["verdict"] == "reported_after_signal"


def test_the_early_close_is_the_calendars():
    # Fri 27 Nov 2026 closes at 13:00 ET: a 13:30 ET acceptance is after that close
    session = "2026-11-27"
    filings = quarters("2025-11-20", through="2026-09-01", ) + [filing(session, "18:30:00")]
    got = verdict(filings, session=session, retrieved="2026-11-27T23:00:00Z")
    assert got["verdict"] == "reported_after_signal"
    # the same 13:30 ET on an ordinary Thursday is before its close
    filings = quarters("2025-11-20", through="2026-09-01") + [filing("2026-11-19", "18:30:00")]
    got = verdict(filings, session="2026-11-19", retrieved="2026-11-19T23:00:00Z")
    assert got["verdict"] != "reported_after_signal"


def test_overdue_and_already_reported():
    # last year 15 Sep 2025: estimated 14 Sep 2026, and nothing filed since July
    overdue = quarters("2025-09-15", through="2026-07-01")
    got = verdict(overdue)
    assert (got["verdict"], got["placement"], got["projection"]["date"]) == ("overdue", "any_day", "2026-09-14")
    # one results filing since the estimate's low reports the cycle, however late
    got = verdict(overdue + [filing("2026-10-20")])
    assert got["verdict"] == "already_reported" and got["observed"]["filing_date"] == "2026-10-20"
    # a report filed up to a week EARLIER than last year's date reports the cycle too
    early = quarters("2025-10-27", through="2026-07-15")      # estimated Mon 26 Oct 2026
    assert verdict(early)["verdict"] == "estimate_near"
    assert verdict(early + [filing("2026-10-20")])["verdict"] == "already_reported"
    assert verdict(early + [filing("2026-10-18")])["verdict"] == "estimate_near"
    # past the overdue horizon the old estimate no longer reads as a cycle
    stale = quarters("2025-08-01", through="2026-05-01")
    assert verdict(stale)["verdict"] in ("estimate_outside", "estimate_near", "estimate_inside")
    assert verdict(stale)["verdict"] != "overdue"


@pytest.mark.parametrize("case, reason", [
    ("late_start", "filings_short"), ("no_start", "filings_short"), ("older_unread", "history_not_read"),
    ("none", "no_results_history"), ("foreign", "foreign_issuer"), ("short", "history_short"),
    ("silent", "no_recent_results"),
])
def test_unknown_is_never_clearance(case, reason):
    # an observed filing after the signal needs no history; these have none
    kwargs = {"late_start": dict(filings=quarters("2025-10-30", through="2026-08-01"), start="2026-01-02"),
              "no_start": dict(filings=[], start=None),
              "older_unread": dict(filings=quarters("2025-10-30", through="2026-08-01"), start="2026-01-02",
                                   history_error="http_error"),
              "none": dict(filings=[], start="2023-01-03"),
              "foreign": dict(filings=[], start="2023-01-03", foreign=True),
              "short": dict(filings=[filing("2026-05-01"), filing("2026-08-01")], start="2023-01-03"),
              "silent": dict(filings=[filing("2024-08-01"), filing("2024-11-01")], start="2023-01-03")}[case]
    filings = kwargs.pop("filings")
    got = verdict(filings, **kwargs)
    assert (got["verdict"], got["reason"], got["projection"], got["placement"]) == ("unknown", reason, None, None)
    row = E._row({"stage": "burst", "ticker": "X"}, S, DAYS, E._instant(NIGHT), got)
    assert row["sentence"].startswith("Earnings date not established: ") and "before entry" in row["sentence"]


def test_timing_reads_the_acceptance_in_eastern_time_across_the_clock_change():
    # 14:00 UTC is 10:00 EDT on 27 Oct and 9:00 EST on 3 Nov 2026
    assert E.timing_of({"filing_date": "2026-10-27", "accepted_at": "2026-10-27T14:00:00Z"}) == "unknown"
    assert E.timing_of({"filing_date": "2026-11-03", "accepted_at": "2026-11-03T14:00:00Z"}) == "before_open"
    assert E.timing_of({"filing_date": "2026-11-03", "accepted_at": None}) == "unknown"
    # an acceptance the evening before is not that filing date's open
    assert E.timing_of({"filing_date": "2026-11-03", "accepted_at": "2026-11-02T23:00:00Z"}) == "unknown"


def test_every_estimate_says_it_is_one():
    for offset in (2, 10, 20):
        anchor = (date.fromisoformat(S) - timedelta(days=364) + timedelta(days=offset)).isoformat()
        got = verdict(quarters(anchor, through=(date.fromisoformat(S) - timedelta(days=30)).isoformat()))
        words = E._row({"stage": "burst", "ticker": "X"}, S, DAYS, E._instant(NIGHT), got)["sentence"]
        assert "estimated" in words and ("not an announced date" in words or "not clearance" in words), words


# ------------------------------------------------------------- the source ---
def register_exel(sec: FakeSec, offset: int = 3, **kw) -> dict:
    return sec.quarterly("EXEL", 939767, "EXELIXIS, INC.", S, offset, **kw)


def test_collect_reads_the_mapping_once_and_each_issuer_once(fake_sec):
    register_exel(fake_sec)
    tickets = [{"stage": "burst", "ticker": "EXEL"}, {"stage": "anticipation", "ticker": "EXEL"},
               {"stage": "anticipation", "ticker": "NOPE"}]
    block = E.collect(tickets, S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    assert [r["verdict"] for r in block["rows"]] == ["estimate_inside", "estimate_inside", "unknown"]
    assert block["rows"][2]["reason"] == "not_mapped" and block["status"] == "checked"
    assert block["requests"] == 2 and len(fake_sec.calls) == 2
    assert block["counts"] == {"estimate_inside": 2, "unknown": 1}
    assert E.block_faults(block, S, tickets) == []
    row = block["rows"][0]
    assert row["cik"] == 939767 and row["sources"][0]["url"] == E.SUBMISSIONS_URL.format(cik=939767)
    assert row["results_filings"] == sorted(row["results_filings"], key=lambda f: f["filing_date"])
    assert len(row["results_filings"]) <= E.MAX_RESULTS_FILINGS


def test_the_older_file_is_read_only_when_the_recent_one_is_short(fake_sec):
    register_exel(fake_sec, history_from="2026-03-01")
    block = E.collect([{"stage": "burst", "ticker": "EXEL"}], S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    row = block["rows"][0]
    assert row["verdict"] == "estimate_inside" and len(row["sources"]) == 2 and row["error"] is None
    assert any("submissions-001" in u for u in fake_sec.calls)
    # the older file refused: the recent rows stay, read as history not read, with the error named
    fake_sec.calls.clear()
    fake_sec.fail["submissions-001"] = "http_error"
    block = E.collect([{"stage": "burst", "ticker": "EXEL"}], S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    row = block["rows"][0]
    assert (row["verdict"], row["reason"], row["error"]) == ("unknown", "history_not_read", "http_error")
    assert E.block_faults(block, S, [{"stage": "burst", "ticker": "EXEL"}]) == []
    # a recent file that reaches back far enough is read alone, though SEC lists an older one
    fake_sec.fail.clear()
    fake_sec.calls.clear()
    register_exel(fake_sec, history_from="2024-06-03")
    block = E.collect([{"stage": "burst", "ticker": "EXEL"}], S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    assert block["rows"][0]["verdict"] == "estimate_inside" and len(block["rows"][0]["sources"]) == 1
    assert not any("submissions-001" in u for u in fake_sec.calls)
    # ...even an older file whose dates overlap the window, which SEC's ordering never lists
    fake_sec.calls.clear()
    entry = register_exel(fake_sec)
    fake_sec.issuer("EXEL", 939767, "EXELIXIS, INC.", entry["rows"], history=[("2026-01-05", "2026-01-05T20:05:00.000Z", "4", "")])
    E.collect([{"stage": "burst", "ticker": "EXEL"}], S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    assert not any("submissions-001" in u for u in fake_sec.calls)


def test_the_newest_results_filings_are_the_ones_kept(fake_sec):
    # fourteen quarters filed: every one inside the reach is kept, with the one before
    # it, so this quarter's filing a week ago still reports the cycle
    register_exel(fake_sec, -8, quarters=14)
    block = E.collect([{"stage": "burst", "ticker": "EXEL"}], S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    row = block["rows"][0]
    needed = date.fromisoformat(S) - timedelta(days=E.REACH_DAYS)
    dates = [date.fromisoformat(f["filing_date"]) for f in row["results_filings"]]
    assert dates[0] < needed <= dates[1] and len(dates) < 14
    assert row["verdict"] == "already_reported" and row["observed"]["filing_date"] == row["results_filings"][-1]["filing_date"]


def test_an_issuer_filing_three_results_a_quarter_is_read_whole(fake_sec):
    # a preliminary release, the results and a supplement each quarter: 39 filings back to 2023;
    # the twelve newest alone would not reach back, and the issuer would read history_short
    rows = []
    for k in range(13):
        base = date(2023, 7, 18) + timedelta(days=91 * k)
        rows += [(d.isoformat(), f"{d.isoformat()}T20:05:00.000Z", "8-K", "2.02")
                 for d in (base, base + timedelta(days=5), base + timedelta(days=9))]
    fake_sec.issuer("EXEL", 939767, "EXELIXIS, INC.", rows, start="2023-01-03")
    block = E.collect([{"stage": "burst", "ticker": "EXEL"}], S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    row = block["rows"][0]
    assert row["reason"] != "history_short" and row["verdict"] != "unknown", row["sentence"]
    assert len(row["results_filings"]) <= E.MAX_RESULTS_FILINGS


def test_sec_down_is_unavailable_never_clear(fake_sec):
    register_exel(fake_sec)
    fake_sec.fail[E.issuer_evidence.MAPPING_URL] = "http_error"
    tickets = [{"stage": "burst", "ticker": "EXEL"}]
    block = E.collect(tickets, S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    assert block["status"] == "unavailable" and block["mapping"] is None
    assert [(r["reason"], r["error"]) for r in block["rows"]] == [("source_unavailable", "http_error")]
    assert "No SEC filing list was read" in block["sentence"]
    assert E.block_faults(block, S, tickets) == []
    # the issuer's list refused after a mapping that answered: that row alone
    fake_sec.fail = {"CIK0000939767": "rate_limit"}
    block = E.collect(tickets + [{"stage": "burst", "ticker": "NOPE"}], S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    assert block["status"] == "partial" and [r["reason"] for r in block["rows"]] == ["source_unavailable", "not_mapped"]


def test_tickets_past_the_bound_are_not_checked(fake_sec, monkeypatch):
    monkeypatch.setattr(E, "MAX_TICKETS", 1)
    register_exel(fake_sec)
    tickets = [{"stage": "burst", "ticker": "EXEL"}, {"stage": "burst", "ticker": "EXEL"}]
    block = E.collect(tickets, S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    assert [r["reason"] for r in block["rows"]] == [None, "not_checked"] and block["status"] == "partial"


def test_an_unexpected_failure_is_a_block_of_unchecked_rows(fake_sec):
    def broken(url):
        raise RuntimeError("socket refused")
    tickets = [{"stage": "burst", "ticker": "EXEL"}]
    block = E.safe_collect(tickets, S, fetch=broken, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    assert block["internal"] == "RuntimeError" and block["status"] == "unavailable"
    assert [r["reason"] for r in block["rows"]] == ["not_checked"]
    assert E.block_faults(block, S, tickets) == []
    assert E.safe_collect([], S)["status"] == "not_applicable"


def test_parse_submissions_refuses_another_issuers_list(fake_sec):
    register_exel(fake_sec)
    raw = fake_sec(E.SUBMISSIONS_URL.format(cik=939767))
    with pytest.raises(E.SourceError) as err:
        E.parse_submissions(raw, 939768, "EXEL")
    assert err.value.code == "rows_unreadable"
    with pytest.raises(E.SourceError) as err:
        E.parse_submissions(raw, 939767, "ZZZ")
    assert err.value.code == "not_mapped"
    columns = json.loads(raw)["filings"]["recent"]
    columns["form"].pop()
    with pytest.raises(E.SourceError):
        E._columns(columns)


def test_only_item_two_oh_two_is_a_results_filing():
    cols = {"accessionNumber": ["0000000001-26-000001", "0000000001-26-000002", "0000000001-26-000003"],
            "filingDate": ["2026-05-01", "2026-05-02", "2026-05-03"],
            "acceptanceDateTime": ["2026-05-01T20:00:00.000Z", "2026-05-02T20:00:00.000Z", ""],
            "form": ["8-K", "8-K", "8-K/A"], "items": ["2.02,9.01", "5.02,2.020", "2.02"]}
    results, start, forms, reports = E._columns(cols)
    assert [r["accession"] for r in results] == ["0000000001-26-000001"]
    assert start == date(2026, 5, 1) and forms == {"8-K", "8-K/A"}
    # every current report is kept with its codes, 2.020 being no code at all
    assert [(r["form"], r["items"]) for r in reports] == [("8-K", ["2.02", "9.01"]), ("8-K", ["5.02"]), ("8-K/A", ["2.02"])]
    assert reports[2]["accepted_at"] is None


# ------------------------------------------------------------- validation ---
def a_block(fake_sec, tickets=None):
    register_exel(fake_sec)
    tickets = tickets or [{"stage": "burst", "ticker": "EXEL"}]
    return E.collect(tickets, S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc)), tickets


@pytest.mark.parametrize("forge, words", [
    (lambda b: b["rows"][0].update(verdict="estimate_outside"), "is not what its filings give"),
    (lambda b: b["rows"][0]["projection"].update(date="2026-12-01"), "projection"),
    (lambda b: b["rows"][0].update(sentence="Clear."), "earnings sentence for EXEL"),
    # the anchor filing dropped: the verdict the row keeps is no longer its filings'
    (lambda b: b["rows"][0]["results_filings"].remove(next(
        f for f in b["rows"][0]["results_filings"] if f["accession"] == b["rows"][0]["projection"]["from_accession"])),
     "is not what its filings give"),
    (lambda b: b.update(status="checked", rows=[]), "earnings status"),
    (lambda b: b.update(counts={}), "earnings counts"),
    (lambda b: b.update(sentence="Earnings fine."), "earnings sentence"),
    (lambda b: b["rows"][0].update(window=b["rows"][0]["window"][:4]), "is not the plan's hold"),
    (lambda b: b["rows"][0].update(extra=1), "row keys"),
    (lambda b: b["rows"][0].update(reason="not_mapped", verdict="unknown"), "beside an unread source"),
    (lambda b: b["rows"][0].update(reason="weird", verdict="unknown"), "earnings verdict"),
    (lambda b: b.update(version=1), "version"),
    (lambda b: b.update(session="2026-10-28"), "session"),
    (lambda b: b["rows"][0]["sources"].clear(), "without its SEC source"),
    (lambda b: b["rows"][0]["sources"][0].update(url="https://example.com/not-sec.json"), "without its SEC source"),
    (lambda b: b["mapping"].update(url="https://example.com/mapping.json"), "earnings mapping source"),
    (lambda b: b["rows"][0].update(retrieved_at="0001-01-01T00:00:00+01:00"), "malformed"),
    (lambda b: b["rows"][0].update(error="something"), "row fields"),
])
def test_the_validator_refuses_a_forged_block(fake_sec, forge, words):
    block, tickets = a_block(fake_sec)
    assert E.block_faults(block, S, tickets) == []
    forge(block)
    faults = E.block_faults(block, S, tickets)
    assert faults and any(words in f for f in faults), faults


def test_the_rows_are_the_records_tickets(fake_sec):
    block, tickets = a_block(fake_sec)
    assert E.block_faults(block, S, tickets + [{"stage": "anticipation", "ticker": "COIL"}]) == \
        ["earnings rows are not the record's tickets"]
    assert E.block_faults(block, S, [{"stage": "anticipation", "ticker": "EXEL"}]) == \
        ["earnings rows are not the record's tickets"]


@pytest.mark.parametrize("shape", ["x", [1], 5, None, {"rows": "x"}])
def test_a_malformed_block_is_named_never_raised(fake_sec, shape):
    block, tickets = a_block(fake_sec)
    assert E.block_faults(shape, S, tickets)
    for key in list(block):
        broken = dict(block, **{key: shape})
        assert isinstance(E.block_faults(broken, S, tickets), list)
    for key in list(block["rows"][0]):
        broken = dict(block, rows=[dict(block["rows"][0], **{key: shape})])
        assert isinstance(E.block_faults(broken, S, tickets), list)


def test_record_faults_asks_only_under_rules_that_write_the_block(fake_sec):
    assert E.record_faults({"rules": {"plan": {}}, "run": {}}) == []
    assert E.record_faults({"rules": {"earnings_risk": {"version": E.VERSION}}, "run": {"session": S}}) == \
        ["run.earnings is missing under rules that write it"]
    block, _ = a_block(fake_sec)
    data = {"rules": {"earnings_risk": {"version": E.VERSION}}, "run": {"session": S, "earnings": block, "published_at": NIGHT},
            "bursts": [{"ticker": "EXEL", "plan": {}}], "trades": ["EXEL"], "watchlist": {"top": []}}
    assert E.record_faults(data) == []
    data["trades"] = []
    assert E.record_faults(data) == ["run.earnings rows are not the record's tickets"]
    data["trades"] = ["EXEL"]
    # every SEC read lies between the signal session's close and two hours after the record's clock
    data["run"]["published_at"] = "2026-10-29T19:00:00Z"
    assert any("outside its session's close" in f for f in E.record_faults(data))
    data["run"]["published_at"] = "2026-10-29T22:30:00Z"
    assert E.record_faults(data) == []
    data["run"]["published_at"] = None
    assert E.record_faults(data) == ["run.earnings cannot be read against the record's clock (run.published_at)"]


def test_a_carried_block_is_kept_only_for_its_own_tickets(fake_sec):
    block, tickets = a_block(fake_sec)
    assert E.carried(block, S, tickets) is block
    fresh = E.carried(block, S, [], now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    assert fresh is not block and fresh["status"] == "not_applicable"
    assert E.carried(None, S, tickets, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))["rows"][0]["ticker"] == "EXEL"


def test_the_rules_are_archived_and_read_by_the_code():
    from types import SimpleNamespace
    from src import pipeline
    rules = pipeline.build_rules(SimpleNamespace(identity="test"))
    archived = rules["earnings_risk"]
    assert archived["projection_days"] == E.PROJECTION_DAYS and archived["estimate_slack_days"] == E.ESTIMATE_SLACK_DAYS
    assert archived["policy"] == "warn_only" and archived["unknown_policy"] == "never_clearance"
    assert archived["results_item"] == "2.02"
    assert archived["version"] == E.VERSION == 2 and archived["material_items"] == list(E.MATERIAL_ITEMS)
    assert archived["recent_report_days"] == E.RECENT_REPORT_DAYS and archived["max_current_reports"] == E.MAX_CURRENT_REPORTS
    assert archived["current_report_forms"] == ["8-K", "8-K/A"]


def test_the_mail_prints_each_tickets_warning_verbatim(fake_sec):
    block, _ = a_block(fake_sec)
    data = {"run": {"earnings": block}}
    row = block["rows"][0]
    line = report._earnings_line(data, "burst", "EXEL")
    # the earnings sentence first, the current-report sentence under it, each verbatim
    assert line.index(report.esc(row["sentence"])) < line.index(report.esc(row["items"]["sentence"]))
    assert line.endswith(f"{report.esc(row['items']['sentence'])}</p>")
    assert report._earnings_line(data, "anticipation", "EXEL") == ""
    assert report._earnings_line({"run": {}}, "burst", "EXEL") == ""
    # a version-1 row carries no items and prints its one sentence
    v1 = {k: v for k, v in row.items() if k != "items"}
    assert report._earnings_line({"run": {"earnings": {"rows": [v1]}}}, "burst", "EXEL").endswith(f"{report.esc(row['sentence'])}</p>")


# ------------------------------------------------------------- the review's cases ---
def test_a_preliminary_release_reports_one_of_last_years_two_filings_not_both():
    # last year a preliminary release on 23 Oct and the results on 28 Oct; this year only the
    # preliminary has come: the results estimated 27 Oct are still inside the hold
    session = "2026-10-23"
    filings = [filing(d) for d in ("2024-07-29", "2024-10-28", "2025-01-28", "2025-04-28", "2025-07-28",
                                    "2025-10-23", "2025-10-28", "2026-01-27", "2026-04-28", "2026-07-28", "2026-10-22")]
    got = verdict(filings, session=session, retrieved="2026-10-23T23:00:00Z")
    assert (got["verdict"], got["projection"]["date"]) == ("estimate_inside", "2026-10-27"), got
    # and both this year: reported
    both = filings + [filing("2026-10-23", "12:00:00")]
    assert verdict(both, session=session, retrieved="2026-10-23T23:00:00Z")["verdict"] == "already_reported"


def test_an_issuer_late_by_its_own_cadence_is_overdue_not_estimated_outside():
    # quarterly every 91 days, the report due about 28 Aug never came: 62 days late
    filings = [filing(d.isoformat()) for k in range(8)
               if (d := date(2026, 5, 29) - timedelta(days=91 * k))]
    got = verdict(filings)
    assert (got["verdict"], got["placement"], got["projection"]) == ("overdue", "any_day", None), got
    words = E._row({"stage": "burst", "ticker": "X"}, S, DAYS, E._instant(NIGHT), got)["sentence"]
    assert words.startswith("No results filing (8-K item 2.02) has come since 29 May 2026") and "any day" in words
    # 41 days late is the estimate's own overdue
    recent = [filing(d.isoformat()) for k in range(8) if (d := date(2026, 6, 19) - timedelta(days=91 * k))]
    assert verdict(recent)["verdict"] == "overdue" and verdict(recent)["projection"]["date"] == "2026-09-18"
    # an annual-only filer a year on is not late
    annual = [filing("2024-11-10"), filing("2025-11-10")]
    assert verdict(annual)["verdict"] != "overdue"


def test_an_estimate_whose_range_ends_before_day_one_is_overdue_not_near():
    # estimated 22 Oct, range 15-29 Oct: it ends on the signal day, before day 1 (Fri 30 Oct)
    got = verdict(quarters("2025-10-23", through="2026-07-25"))
    assert (got["verdict"], got["projection"]["date"]) == ("overdue", "2026-10-22"), got
    # before Thanksgiving: a range ending on the closed Thursday is before day 1 too
    got = verdict(quarters("2025-11-20", through="2026-08-21"), session="2026-11-25", retrieved="2026-11-25T23:00:00Z")
    assert got["verdict"] == "overdue", got
    # a range that reaches day 1 is near
    assert verdict(quarters("2025-10-24", through="2026-07-25"))["verdict"] == "estimate_near"


def test_acceptance_after_the_close_is_not_said_to_prove_the_release_came_after_it():
    filings = quarters("2025-10-30", through="2026-08-01") + [filing(S, "20:40:00")]
    got = verdict(filings)
    words = E._row({"stage": "burst", "ticker": "X"}, S, DAYS, E._instant(NIGHT), got)["sentence"]
    assert "accepted by the SEC after the signal session's close" in words
    assert "may have come earlier" in words and "Check the release time" in words
    assert "so the entry opens on the reaction" not in words


def test_a_later_read_sees_sec_as_it_stood_through_the_hold():
    # a backfill read on 18 Nov: a filing on 16 Nov, after the hold, is not "inside the hold"
    base = quarters("2025-11-20", through="2026-08-21")
    got = verdict(base + [filing("2026-11-16", "21:05:00")], retrieved="2026-11-18T23:00:00Z")
    assert got["verdict"] != "reported_after_signal"
    # the earliest after-close filing is the one named, and one inside the hold is held
    two = base + [filing("2026-11-02", "21:05:00"), filing("2027-02-09", "21:05:00")]
    got = verdict(two, retrieved="2027-02-10T15:00:00Z")
    assert (got["verdict"], got["placement"], got["observed"]["filing_date"]) == ("reported_after_signal", "held", "2026-11-02")
    assert "during this ticket's hold window" in E._row({"stage": "burst", "ticker": "X"}, S, DAYS,
                                                       E._instant("2027-02-10T15:00:00Z"), got)["sentence"]


def test_the_unknown_reasons_say_what_was_read(fake_sec):
    # no older file listed: the list read begins within the reach
    rows = [(d, f"{d}T20:05:00.000Z", "8-K", "2.02") for d in ("2026-05-05", "2026-08-04")]
    fake_sec.issuer("NEWCO", 1990001, "NEWCO INC", rows + [("2026-02-20", "2026-02-20T12:00:00.000Z", "S-1", "")])
    block = E.collect([{"stage": "burst", "ticker": "NEWCO"}], S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    row = block["rows"][0]
    assert (row["reason"], row["error"]) == ("filings_short", None) and "older" not in row["sentence"]
    assert f"{E.REACH_DAYS} days" in row["sentence"]
    assert "fourteen months" not in " ".join(E.REASON_WORDS.values())


def test_an_unreadable_mapping_is_sec_failing_never_a_symbol_it_lacks(fake_sec, monkeypatch):
    register_exel(fake_sec)
    monkeypatch.setattr(fake_sec, "mapping_body", b"<html>Request Rate Threshold Exceeded</html>", raising=False)
    tickets = [{"stage": "burst", "ticker": "EXEL"}]
    block = E.collect(tickets, S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    assert block["status"] == "unavailable"
    assert [(r["reason"], r["error"]) for r in block["rows"]] == [("source_unavailable", "invalid_response")]
    assert E.block_faults(block, S, tickets) == []
    # a symbol the mapping names for two companies is ambiguous, not mapped to either
    monkeypatch.setattr(fake_sec, "mapping_body", None, raising=False)
    fake_sec.issuer("EXL2", 939768, "OTHER EXELIXIS", [], tickers=["EXEL"])
    block = E.collect(tickets, S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    assert block["rows"][0]["reason"] == "identity_ambiguous" and block["status"] == "checked"


def test_a_transport_failure_of_any_kind_is_one_tickets_unknown_row(fake_sec, monkeypatch):
    import http.client
    register_exel(fake_sec)
    fake_sec.quarterly("AAPL", 320193, "Apple Inc.", S, 3)
    calls = []

    def fetch(self, url, budget):
        calls.append(url)
        if "CIK0000320193" in url:
            raise http.client.IncompleteRead(b"partial")
        return {"body": fake_sec(url)}
    monkeypatch.setattr(E.issuer_evidence._Transport, "fetch", fetch)
    monkeypatch.setattr(E, "FETCH", None)
    tickets = [{"stage": "burst", "ticker": "EXEL"}, {"stage": "burst", "ticker": "AAPL"}]
    block = E.safe_collect(tickets, S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    assert "internal" not in block and block["requests"] == 3 and len(calls) == 3
    assert [(r["verdict"], r["reason"], r["error"]) for r in block["rows"]] == \
        [("estimate_inside", None, None), ("unknown", "source_unavailable", "network_error")]


def test_an_internal_failure_keeps_the_count_of_requests_made(fake_sec):
    register_exel(fake_sec)
    count = {"n": 0}

    def fetch(url):
        count["n"] += 1
        if count["n"] == 2:
            raise RuntimeError("a bug")
        return fake_sec(url)
    block = E.safe_collect([{"stage": "burst", "ticker": "EXEL"}], S, fetch=fetch,
                           now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    assert block["internal"] == "RuntimeError" and block["requests"] == 2


def test_the_earliest_filing_after_the_close_is_the_one_named():
    # results accepted the signal evening and a second filing on day 3, both inside the
    # hold as SEC stood at its end: the evening one, before day 1, is the fact that matters
    base = quarters("2025-11-20", through="2026-08-21")
    two = base + [filing(S, "21:05:00"), filing("2026-11-03", "21:05:00")]
    got = verdict(two, retrieved="2026-11-10T15:00:00Z")
    assert (got["verdict"], got["placement"], got["observed"]["filing_date"]) == ("reported_after_signal", "pre_entry", S)


def test_the_after_close_sentence_says_only_what_acceptance_proves():
    got = verdict(quarters("2025-10-30", through="2026-08-01") + [filing(S, "20:40:00")])
    assert E._row({"stage": "burst", "ticker": "X"}, S, DAYS, E._instant(NIGHT), got)["sentence"] == (
        "Quarterly results (8-K item 2.02) were accepted by the SEC after the signal session's close and before "
        "day 1's open (Thu 29 Oct 4:40 PM ET). The release they furnish may have come earlier, even before the "
        "signal session's open; if it came after that close, the entry opens on the reaction. Check the release "
        "time before entry.")


def test_a_read_before_the_session_closed_is_refused(fake_sec):
    # a block read at 3:30 PM ET, before the 4:00 PM close: refused by the record's validator
    register_exel(fake_sec)
    tickets = [{"stage": "burst", "ticker": "EXEL"}]
    early = datetime(2026, 10, 29, 19, 30, tzinfo=timezone.utc)
    block = E.collect(tickets, S, now=early)
    assert E.block_faults(block, S, tickets) == []
    data = {"rules": {"earnings_risk": {"version": E.VERSION}}, "run": {"session": S, "earnings": block, "published_at": "2026-10-29T19:30:00Z"},
            "bursts": [{"ticker": "EXEL", "plan": {}}], "trades": ["EXEL"], "watchlist": {"top": []}}
    faults = E.record_faults(data)
    assert any("outside its session's close" in f for f in faults), faults
    assert "run.earnings mapping source" in faults


def test_a_record_clock_out_of_range_is_named_never_raised(fake_sec):
    block, tickets = a_block(fake_sec)
    data = {"rules": {"earnings_risk": {"version": E.VERSION}}, "run": {"session": S, "earnings": block,
                                                    "published_at": "0001-01-01T00:00:00+01:00"},
            "bursts": [{"ticker": "EXEL", "plan": {}}], "trades": ["EXEL"], "watchlist": {"top": []}}
    assert E.record_faults(data) == ["run.earnings cannot be read against the record's clock (run.published_at)"]


# ------------------------------------------------------------- the third review's cases ---
def test_an_overdue_estimate_says_it_is_one():
    got = verdict(quarters("2025-09-15", through="2026-07-01"))
    assert got["verdict"] == "overdue" and got["projection"] is not None
    words = E._row({"stage": "burst", "ticker": "X"}, S, DAYS, E._instant(NIGHT), got)["sentence"]
    assert "not an announced date" in words, words


def test_the_block_sentence_never_calls_an_unknown_or_overdue_ticket_clear():
    rows = [{"verdict": v} for v in E.VERDICTS]
    block = {"status": "partial", "rows": rows, "counts": {v: 1 for v in E.VERDICTS}}
    words = E.block_sentence(block)
    assert "1 not established" in words and "1 overdue, so any day" in words
    assert "clear" not in words.lower() and words.endswith("An estimate warns and never withholds a ticket.")
    assert "No SEC filing list was read" in E.block_sentence(dict(block, status="unavailable"))


def _rederive(block):
    block["counts"] = E._counts(block["rows"])
    block["status"] = E._status(block["rows"])
    block["sentence"] = E.block_sentence(block)


def test_an_unmapped_ticket_relabelled_outside_is_refused(fake_sec):
    block, tickets = a_block(fake_sec, [{"stage": "burst", "ticker": "NOPE"}])
    row = block["rows"][0]
    assert (row["verdict"], row["reason"]) == ("unknown", "not_mapped") and E.block_faults(block, S, tickets) == []
    row["verdict"] = "estimate_outside"
    row["sentence"] = E.sentence(row)
    _rederive(block)
    assert "not clearance" in row["sentence"]          # the forgery would read as an inference, not as unknown
    assert "earnings verdict for NOPE" in E.block_faults(block, S, tickets)


def test_the_validator_rederives_placement_and_reason(fake_sec):
    register_exel(fake_sec)
    # two results filings a few months apart: too short a history to estimate from
    fake_sec.issuer("SHRT", 222222, "SHORT CO", [("2026-05-01", "2026-05-01T20:05:00.000Z", "8-K", "2.02"),
                                                  ("2026-08-03", "2026-08-03T20:05:00.000Z", "8-K", "2.02")],
                    start="2023-01-03")
    tickets = [{"stage": "burst", "ticker": "EXEL"}, {"stage": "burst", "ticker": "SHRT"}]
    block = E.collect(tickets, S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    exel, shrt = block["rows"]
    assert (exel["placement"], shrt["reason"]) == ("held", "history_short") and E.block_faults(block, S, tickets) == []
    for row, key, value in ((exel, "placement", "pre_entry"), (shrt, "reason", "no_recent_results")):
        forged = json.loads(json.dumps(block))
        target = next(r for r in forged["rows"] if r["ticker"] == row["ticker"])
        target[key] = value
        target["sentence"] = E.sentence(target)
        _rederive(forged)
        faults = E.block_faults(forged, S, tickets)
        assert f"earnings {key} for {row['ticker']} is not what its filings give" in faults, faults


def test_the_validator_rederives_what_was_observed(fake_sec):
    register_exel(fake_sec)
    entry = fake_sec.issuers["EXEL"]
    entry["rows"].append((S, f"{S}T20:30:00.000Z", "8-K", "2.02,9.01"))
    tickets = [{"stage": "burst", "ticker": "EXEL"}]
    block = E.collect(tickets, S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    row = block["rows"][0]
    assert row["verdict"] == "reported_after_signal" and E.block_faults(block, S, tickets) == []
    row["observed"] = dict(row["observed"], accepted_at=f"{S}T21:30:00Z")
    row["sentence"] = E.sentence(row)
    _rederive(block)
    assert "earnings observed for EXEL is not what its filings give" in E.block_faults(block, S, tickets)


def test_a_malformed_key_is_named(fake_sec):
    block, tickets = a_block(fake_sec)
    for key, bad in (("requests", "x"), ("requests", True), ("policy", 5), ("source", 5), ("version", "1"),
                     ("version", 1.0), ("rows", "x"), ("counts", "x"), ("status", "clear"), ("mapping", "x")):
        faults = E.block_faults(dict(block, **{key: bad}), S, tickets)
        assert faults, (key, bad)
    for key, bad in (("sources", "x"), ("results_filings", "x"), ("cik", "x"), ("window", "x"), ("sentence", 5)):
        broken = dict(block, rows=[dict(block["rows"][0], **{key: bad})])
        assert E.block_faults(broken, S, tickets), (key, bad)


def test_an_acceptance_is_printed_in_eastern_time():
    assert E._et("2026-10-29T20:30:00Z") == "Thu 29 Oct 4:30 PM ET"           # EDT
    assert E._et("2026-11-03T21:30:00Z") == "Tue 3 Nov 4:30 PM ET"            # EST
    assert E._et("2026-10-29T16:00:00Z") == "Thu 29 Oct 12:00 PM ET"          # noon is PM
    assert E._et("2026-10-29T15:59:00Z") == "Thu 29 Oct 11:59 AM ET"
    assert E._et("2026-10-29T04:00:00Z") == "Thu 29 Oct 12:00 AM ET"          # midnight is 12 AM


def test_results_accepted_during_day_one_are_held_not_before_the_open():
    # a re-run made after day 1's close sees an 8-K accepted at 10:00 AM ET on day 1
    base = quarters("2025-10-30", through="2026-08-01")
    got = verdict(base + [filing(DAYS[0], "14:00:00")], retrieved="2026-10-30T23:00:00Z")
    assert (got["verdict"], got["placement"]) == ("reported_after_signal", "held")
    words = E._row({"stage": "burst", "ticker": "X"}, S, DAYS, E._instant("2026-10-30T23:00:00Z"), got)["sentence"]
    assert "during this ticket's hold window" in words and "before day 1's open" not in words, words


def test_a_foreign_issuer_is_read_as_one_through_collect(fake_sec):
    fake_sec.issuer("ZIM", 1654126, "ZIM Integrated Shipping", [("2026-08-20", "2026-08-20T11:00:00.000Z", "6-K", "")],
                    start="2023-03-01", foreign=True)
    block = E.collect([{"stage": "anticipation", "ticker": "ZIM"}], S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    assert (block["rows"][0]["verdict"], block["rows"][0]["reason"]) == ("unknown", "foreign_issuer")
    # the forms of the older file count too: a 20-F only there still makes a foreign issuer
    fake_sec.issuer("ZIM", 1654126, "ZIM Integrated Shipping", [("2026-08-20", "2026-08-20T11:00:00.000Z", "6-K", "")],
                    history=[("2025-12-01", "2025-12-01T12:00:00.000Z", "20-F", ""),
                             ("2023-03-01", "2023-03-01T12:00:00.000Z", "20-F", "")])
    fake_sec.issuers["ZIM"]["rows"] = [("2026-08-20", "2026-08-20T11:00:00.000Z", "4", "")]
    block = E.collect([{"stage": "anticipation", "ticker": "ZIM"}], S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    assert block["rows"][0]["reason"] == "foreign_issuer", block["rows"][0]


def test_the_deadline_stops_reading_and_says_so(fake_sec):
    register_exel(fake_sec)
    block = E.collect([{"stage": "burst", "ticker": "EXEL"}], S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc),
                      deadline_seconds=0)
    assert block["status"] == "unavailable" and block["requests"] == 0
    assert [(r["reason"], r["error"]) for r in block["rows"]] == [("source_unavailable", "time_budget")]


def test_last_years_before_open_report_is_named_in_the_sentence():
    anchor = (date.fromisoformat(S) - timedelta(days=364) + timedelta(days=4)).isoformat()   # Mon 3 Nov 2025
    filings = quarters(anchor, through=(date.fromisoformat(S) - timedelta(days=30)).isoformat())
    for f in filings:
        if f["filing_date"] == anchor:
            f["accepted_at"] = f"{anchor}T12:00:00Z"                                          # 7:00 AM EST
    got = verdict(filings)
    assert got["verdict"] == "estimate_inside" and got["projection"]["timing_last_year"] == "before_open"
    words = E._row({"stage": "burst", "ticker": "X"}, S, DAYS, E._instant(NIGHT), got)["sentence"]
    assert "accepted before that day's open" in words, words


def test_the_reach_is_inclusive_at_its_edge():
    edge = date.fromisoformat(S) - timedelta(days=E.REACH_DAYS)
    got = verdict([filing(edge.isoformat())])
    assert got["verdict"] == "overdue", got
    got = verdict([filing((edge - timedelta(days=1)).isoformat())])
    assert (got["verdict"], got["reason"]) == ("unknown", "no_recent_results"), got
    # a list that begins exactly at the edge reaches it; a day later does not
    assert verdict([filing(edge.isoformat())], start=edge.isoformat())["verdict"] == "overdue"
    assert verdict([filing(edge.isoformat())], start=(edge + timedelta(days=1)).isoformat())["reason"] == "filings_short"


def test_a_report_exactly_a_week_early_reports_the_cycle():
    overdue = quarters("2025-09-15", through="2026-07-01")                   # estimated 14 Sep 2026
    assert verdict(overdue + [filing("2026-09-07")])["verdict"] == "already_reported"


def test_an_unreadable_issuer_list_is_named_unreadable_not_unanswered(fake_sec, monkeypatch):
    register_exel(fake_sec)
    real = fake_sec.__class__.__call__

    def answer(self, url):
        body = real(self, url)
        if "submissions/CIK" in url:
            data = json.loads(body)
            data["filings"]["recent"].pop("items")
            return json.dumps(data).encode()
        return body
    monkeypatch.setattr(fake_sec.__class__, "__call__", answer)
    block = E.collect([{"stage": "burst", "ticker": "EXEL"}], S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    assert block["rows"][0]["reason"] == "rows_unreadable", block["rows"][0]


def test_two_tickets_of_one_stage_each_get_their_own_line(fake_sec):
    register_exel(fake_sec)
    fake_sec.quarterly("ACME", 123456, "ACME CORP", S, 40)
    tickets = [{"stage": "burst", "ticker": "EXEL"}, {"stage": "burst", "ticker": "ACME"}]
    block = E.collect(tickets, S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    first, second = block["rows"]
    assert first["sentence"] != second["sentence"]
    data = {"run": {"earnings": block}}
    assert report.esc(first["sentence"]) in report._earnings_line(data, "burst", "EXEL")
    assert report.esc(second["sentence"]) in report._earnings_line(data, "burst", "ACME")
    assert report.esc(second["sentence"]) not in report._earnings_line(data, "burst", "EXEL")


# ------------------------------------------------------- the current reports (v2) ---
NOW = datetime(2026, 10, 29, 23, tzinfo=timezone.utc)
TICKET = [{"stage": "burst", "ticker": "EXEL"}]


def current_report(day: str, accepted: str | None = "20:05:00", form: str = "8-K", items=("8.01", "9.01"),
                   unread: int = 0) -> dict:
    return {"accession": f"0000939767-{int(day[2:4]):02d}-{next(ACC):06d}", "filing_date": day,
            "accepted_at": f"{day}T{accepted}Z" if accepted else None, "form": form, "items": list(items), "unread": unread}


def items(reports, *, window=None, session=S, retrieved=NIGHT, foreign=False):
    return E.items_of(reports, window, session, E.window(session), retrieved, foreign)


NONE_MATERIAL = ("of those read, none is a material agreement (1.01), a bankruptcy (1.03), a completed acquisition or "
                 "disposition (2.01), a delisting notice (3.01) or a change in control (5.01)")


def test_a_material_item_is_named_with_its_filing_and_where_it_fell():
    got = items([current_report("2026-10-27", items=("1.01", "9.01"))])
    assert got["status"] == "material" and [m["item"] for m in got["material"]] == ["1.01"]
    assert got["material"][0]["placement"] == "before_signal_close" and got["material"][0]["title"] == E.ITEM_TITLES["1.01"]
    assert "8-K item 1.01 (Entry into a Material Definitive Agreement) filed 27 Oct 2026" in got["sentence"]
    assert "accepted Tue 27 Oct 4:05 PM ET, before the signal session's close" in got["sentence"]
    assert "not a refusal" in got["sentence"] and "read it before entry" in got["sentence"]
    assert "Other items filed in the 14 days before the signal or since: 9.01 (Financial Statements and Exhibits)." in got["sentence"]
    # accepted after the signal session's close: before day 1's open
    got = items([current_report(S, "21:30:00", items=("2.01",))])
    assert got["material"][0]["placement"] == "pre_entry" and "before day 1's open" in got["sentence"]
    # at the close (20:00Z in October) it is before it; a second later it is after
    assert items([current_report(S, "20:00:00", items=("2.01",))])["material"][0]["placement"] == "before_signal_close"
    assert items([current_report(S, "20:00:01", items=("2.01",))])["material"][0]["placement"] == "pre_entry"
    assert "Other items" not in got["sentence"]
    # accepted during the hold, seen by a read after it
    got = items([current_report("2026-11-03", "21:00:00", items=("5.01",))], retrieved="2026-11-06T23:00:00Z")
    assert got["material"][0]["placement"] == "held" and "during this ticket's hold window" in got["sentence"]
    # two material items on two reports: both named, newest report first
    got = items([current_report("2026-10-20", items=("1.01",)), current_report("2026-10-28", items=("3.01", "9.01"))])
    assert [m["item"] for m in got["material"]] == ["3.01", "1.01"]
    assert got["sentence"].index("item 3.01") < got["sentence"].index("item 1.01")


def test_a_report_without_an_acceptance_time_is_placed_by_its_filing_date():
    # a Friday signal: a filing dated the Saturday is after its close and before Monday's open
    friday = "2026-10-30"
    got = items([current_report("2026-10-31", None, items=("1.03",))], session=friday, retrieved="2026-11-06T23:00:00Z")
    assert got["material"][0]["placement"] == "pre_entry" and ", accepted" not in got["sentence"]
    # dated the signal session itself, it could have been accepted after the close: the words say so
    got = items([current_report(friday, None, items=("1.03",))], session=friday, retrieved="2026-10-30T23:00:00Z")
    assert got["material"][0]["placement"] == "signal_date"
    assert "on the signal session's date (SEC recorded no acceptance time, so before or after its close is not established)" in got["sentence"]
    assert "before the signal session's close" not in got["sentence"]
    # dated before it: before its close; dated day 1 or later: during the hold
    got = items([current_report("2026-10-29", None, items=("1.03",))], session=friday)
    assert got["material"][0]["placement"] == "before_signal_close"
    got = items([current_report("2026-11-02", None, items=("1.03",))], session=friday, retrieved="2026-11-06T23:00:00Z")
    assert got["material"][0]["placement"] == "held"
    got = items([current_report("2026-11-03", None, items=("1.03",))], session=friday, retrieved="2026-11-06T23:00:00Z")
    assert got["material"][0]["placement"] == "held"


def test_other_items_are_listed_by_heading_and_none_or_a_foreign_issuer_say_so():
    got = items([current_report("2026-10-20", items=("7.01", "9.01")), current_report("2026-10-16", form="8-K/A", items=("2.03",))])
    assert got["status"] == "listed" and got["codes"] == ["2.03", "7.01", "9.01"] and got["material"] == []
    assert got["sentence"].startswith("Recent SEC current reports: 2 (8-K) filed in the 14 days before the signal or since, items 2.03 (")
    assert "7.01 (Regulation FD Disclosure), 9.01 (Financial Statements and Exhibits); of those read, none is " in got["sentence"]
    # the kinds it rules out are every material item, in words this test spells for itself
    assert NONE_MATERIAL in got["sentence"]
    assert got["sentence"].endswith(" SEC filings are not news coverage.")
    none = items([])
    assert none["status"] == "none" and none["sentence"] == ("Recent SEC current reports: none (8-K) filed in the 14 days "
                                                              "before the signal or since. SEC filings are not news coverage.")
    foreign = items([], foreign=True)
    assert foreign["status"] == "foreign" and "a foreign issuer's reports (6-K) carry no item codes" in foreign["sentence"]
    # a code SEC's heading table does not know is printed bare, never invented
    odd = items([current_report("2026-10-20", items=("9.99",))])
    assert odd["status"] == "listed" and "items 9.99;" in odd["sentence"]


def test_the_window_is_fourteen_days_before_the_signal_through_the_read(fake_sec):
    entry = register_exel(fake_sec)
    entry["rows"] += [("2026-10-15", "2026-10-15T20:05:00.000Z", "8-K", "1.01"),      # exactly 14 days before: recent
                      ("2026-10-14", "2026-10-14T20:05:00.000Z", "8-K", "5.01"),      # fifteen: not
                      ("2026-10-29", "2026-10-29T22:00:00.000Z", "8-K", "7.01")]      # after the close, before the read
    block = E.collect(TICKET, S, now=NOW)
    row = block["rows"][0]
    # the material report is retained first, then the newest
    assert [(r["filing_date"], r["items"]) for r in row["current_reports"]] == [("2026-10-15", ["1.01"]), ("2026-10-29", ["7.01"])]
    assert row["current_report_window"] == {"count": 2, "unretained_material": 0} and row["items"]["status"] == "material"
    assert [m["item"] for m in row["items"]["material"]] == ["1.01"] and row["items"]["codes"] == ["1.01", "7.01"]
    assert row["items"]["count"] == 2 and row["items"]["seen"] == 2 and row["items"]["after_hold"] == 0
    assert block["items_counts"] == {"material": 1}
    assert block["sentence"].endswith("SEC current reports (8-K) in the 14 days before the signal or since: 1 with a "
                                      "material item; a material item names a kind of event and withholds nothing.")
    assert block["requests"] == 2 and len(fake_sec.calls) == 2          # nothing extra was asked of SEC
    assert E.block_faults(block, S, TICKET) == []
    # the earnings verdict is untouched by the reports
    assert row["verdict"] == "estimate_inside"


def test_the_newest_reports_are_kept_and_the_count_says_how_many_the_window_held(fake_sec):
    entry = register_exel(fake_sec)
    days = [f"2026-10-{d:02d}" for d in range(16, 29)]                        # thirteen reports in the window
    entry["rows"] += [(d, f"{d}T20:05:00.000Z", "8-K", "8.01") for d in days]
    block = E.collect(TICKET, S, now=NOW)
    row = block["rows"][0]
    assert len(row["current_reports"]) == E.MAX_CURRENT_REPORTS == 8 and row["current_report_window"] == {"count": 13, "unretained_material": 0}
    assert [r["filing_date"] for r in row["current_reports"]] == days[::-1][:8]
    assert "13 (8-K) filed in the 14 days before the signal or since, 8 of them retained and read, items 8.01" in row["items"]["sentence"]
    assert E.block_faults(block, S, TICKET) == []


def test_a_material_report_is_retained_before_the_newest_and_the_bound_says_what_it_dropped(fake_sec):
    # thirteen reports: the OLDEST carries a delisting notice, the rest 8.01 -- the bound keeps it first
    entry = register_exel(fake_sec)
    days = [f"2026-10-{d:02d}" for d in range(16, 29)]
    entry["rows"] += [(d, f"{d}T20:05:00.000Z", "8-K", "3.01" if d == days[0] else "8.01") for d in days]
    block = E.collect(TICKET, S, now=NOW)
    row = block["rows"][0]
    assert row["current_reports"][0]["filing_date"] == days[0] and row["current_reports"][0]["items"] == ["3.01"]
    assert [r["filing_date"] for r in row["current_reports"][1:]] == days[::-1][:7]
    assert row["items"]["status"] == "material" and row["current_report_window"] == {"count": 13, "unretained_material": 0}
    assert "8-K item 3.01 (Notice of Delisting" in row["items"]["sentence"] and "not retained" not in row["items"]["sentence"]
    assert E.block_faults(block, S, TICKET) == []
    # nine material reports: the bound drops one, and the row and the sentence say so
    entry["rows"] = [r for r in entry["rows"] if r[0] not in days]
    entry["rows"] += [(d, f"{d}T20:05:00.000Z", "8-K", "1.01") for d in days[:9]]
    block = E.collect(TICKET, S, now=NOW)
    row = block["rows"][0]
    assert row["current_report_window"] == {"count": 9, "unretained_material": 1} and len(row["current_reports"]) == 8
    assert [r["filing_date"] for r in row["current_reports"]] == days[:9][::-1][:8]
    assert "1 more report with a material item was filed in the 14 days before the signal or since and not retained." in row["items"]["sentence"]
    assert E.block_faults(block, S, TICKET) == []


def test_a_report_filed_after_the_hold_is_counted_and_said_not_read_on_a_later_read(fake_sec):
    entry = register_exel(fake_sec)
    entry["rows"] += [("2026-11-06", "2026-11-06T20:05:00.000Z", "8-K", "3.01"),     # the session after the hold's last
                      ("2026-10-27", "2026-10-27T20:05:00.000Z", "8-K", "7.01")]
    block = E.collect(TICKET, S, now=datetime(2026, 11, 10, 23, tzinfo=timezone.utc))
    row = block["rows"][0]
    assert row["current_report_window"] == {"count": 2, "unretained_material": 0} and len(row["current_reports"]) == 2
    assert row["items"]["status"] == "listed" and row["items"]["seen"] == 1 and row["items"]["after_hold"] == 1
    assert "2 (8-K) filed in the 14 days before the signal or since, 1 of them retained and read, items 7.01" in row["items"]["sentence"]
    assert "1 report filed after the hold's last close was not read." in row["items"]["sentence"]
    assert E.block_faults(block, S, TICKET) == []
    # with nothing read at all the words say none was read, not none was filed
    entry["rows"] = [r for r in entry["rows"] if r[0] != "2026-10-27"]
    row = E.collect(TICKET, S, now=datetime(2026, 11, 10, 23, tzinfo=timezone.utc))["rows"][0]
    assert row["items"]["status"] == "none" and row["items"]["sentence"].startswith(
        "Recent SEC current reports: none (8-K) read, filed in the 14 days before the signal or since through the hold's last close. 1 report filed after")
    # a report dated after the read is not the window's: the row never carries it, and a forged one is refused
    entry["rows"] += [("2026-11-20", "2026-11-20T20:05:00.000Z", "8-K", "1.01")]
    block = E.collect(TICKET, S, now=datetime(2026, 11, 10, 23, tzinfo=timezone.utc))
    assert block["rows"][0]["current_report_window"]["count"] == 1
    forged = json.loads(json.dumps(block))
    forged["rows"][0]["current_reports"].insert(0, current_report("2026-11-20", items=("1.01",)))
    forged["rows"][0]["current_report_window"]["count"] = 2
    assert any("are not the recent window's" in f for f in E.block_faults(forged, S, TICKET))


def test_an_item_token_sec_wrote_in_another_shape_is_counted_not_read(fake_sec):
    entry = register_exel(fake_sec)
    entry["rows"] += [("2026-10-27", "2026-10-27T21:05:00.000Z", "8-K", "2.020")]
    row = E.collect(TICKET, S, now=NOW)["rows"][0]
    assert row["current_reports"][0]["items"] == [] and row["current_reports"][0]["unread"] == 1
    assert row["items"]["status"] == "unreadable" and row["items"]["unread"] == 1
    assert row["items"]["sentence"] == ("Recent SEC current reports: 1 (8-K) filed in the 14 days before the signal or since; "
                                        "no item code could be read, so what they name is not established. 1 item token SEC "
                                        "wrote in another shape was not read. SEC filings are not news coverage.")
    # beside readable codes the token is counted and the readable ones are read
    entry["rows"].append(("2026-10-26", "2026-10-26T21:05:00.000Z", "8-K", "7.01, bogus"))
    block = E.collect(TICKET, S, now=NOW)
    row = block["rows"][0]
    assert row["items"]["status"] == "listed" and row["items"]["unread"] == 2 and row["items"]["codes"] == ["7.01"]
    assert "2 item tokens SEC wrote in another shape were not read." in row["items"]["sentence"]
    assert block["items_counts"] == {"listed": 1} and "1 with other items only" in block["sentence"]
    assert E.block_faults(block, S, TICKET) == []


def test_an_amendment_prints_its_own_form():
    got = items([current_report("2026-10-27", form="8-K/A", items=("2.01",))])
    assert got["material"][0]["form"] == "8-K/A" and "8-K/A item 2.01 (Completion of Acquisition" in got["sentence"]


def test_a_foreign_issuer_that_files_current_reports_is_read_like_any_other(fake_sec):
    fake_sec.issuer("SAP", 1000184, "SAP SE", [("2026-10-20", "2026-10-20T11:00:00.000Z", "6-K", ""),
                                               ("2026-10-21", "2026-10-21T11:00:00.000Z", "8-K", "7.01")],
                    start="2024-01-10", foreign=True)
    block = E.collect([{"stage": "burst", "ticker": "SAP"}], S, now=NOW)
    row = block["rows"][0]
    assert row["foreign"] and row["items"]["status"] == "listed" and row["items"]["codes"] == ["7.01"]
    assert E.block_faults(block, S, [{"stage": "burst", "ticker": "SAP"}]) == []


def test_the_block_sentence_counts_every_status_in_its_own_words(fake_sec):
    register_exel(fake_sec)                                                        # none
    fake_sec.issuer("SAP", 1000184, "SAP SE", [], start="2024-01-10", foreign=True)   # foreign
    tickets = [{"stage": "burst", "ticker": "EXEL"}, {"stage": "burst", "ticker": "SAP"}, {"stage": "anticipation", "ticker": "NOPE"}]
    block = E.collect(tickets, S, now=NOW)
    assert block["items_counts"] == {"none": 1, "foreign": 1, "not_checked": 1}
    assert block["sentence"].endswith("SEC current reports (8-K) in the 14 days before the signal or since: 1 with none; "
                                      "1 foreign (6-K, no items); 1 not checked; a material item names a kind of event and withholds nothing.")


def test_the_item_headings_are_secs_own():
    # a few headings spelled here from Form 8-K, apart from the module's table
    assert E.ITEM_TITLES["1.01"] == "Entry into a Material Definitive Agreement"
    assert E.ITEM_TITLES["2.02"] == "Results of Operations and Financial Condition"
    assert E.ITEM_TITLES["7.01"] == "Regulation FD Disclosure"
    assert E.ITEM_TITLES["8.01"] == "Other Events"
    assert E.ITEM_TITLES["9.01"] == "Financial Statements and Exhibits"
    assert E.ITEM_TITLES["2.03"].startswith("Creation of a Direct Financial Obligation")
    assert E.ITEM_TITLES["3.01"].startswith("Notice of Delisting")
    assert len(E.ITEM_TITLES) == 33 and all(E.ITEM_CODE.fullmatch(c) for c in E.ITEM_TITLES)


def test_a_report_accepted_after_the_hold_is_not_seen_by_a_later_read():
    late = current_report("2026-11-06", "20:05:00", items=("1.01",))                 # the session after the hold's last
    got = items([late], retrieved="2026-11-10T23:00:00Z")
    assert got["status"] == "none" and got["seen"] == 0 and got["count"] == 1
    inside = current_report("2026-11-05", "20:30:00", items=("1.01",))               # before the hold's last close, 21:00Z in November
    assert items([inside], retrieved="2026-11-10T23:00:00Z")["status"] == "material"
    at_close = current_report("2026-11-05", "21:00:00", items=("1.01",))
    assert items([at_close], retrieved="2026-11-10T23:00:00Z")["status"] == "material"
    past_close = current_report("2026-11-05", "21:00:01", items=("1.01",))
    assert items([past_close], retrieved="2026-11-10T23:00:00Z")["status"] == "none"


def test_an_unknown_item_token_is_left_out_of_a_reports_codes():
    cols = {"accessionNumber": ["0000000001-26-000001", "0000000001-26-000002"],
            "filingDate": ["2026-05-01", "2026-05-02"],
            "acceptanceDateTime": ["2026-05-01T20:00:00.000Z", ""],
            "form": ["8-K", "8-K"], "items": ["junk, 1.01 ,1.01", "2.020"]}
    _, _, _, reports = E._columns(cols)
    assert [r["items"] for r in reports] == [["1.01"], []]


def test_an_unread_row_carries_no_current_reports_and_says_so(fake_sec):
    fake_sec.fail["sec.gov"] = "network_error"
    block = E.collect(TICKET, S, now=NOW)
    row = block["rows"][0]
    assert row["current_reports"] == [] and row["current_report_window"] is None
    assert row["items"] == E._items_unread("source_unavailable")
    assert row["items"]["sentence"] == "Recent SEC current reports not checked: SEC did not answer."
    assert block["items_counts"] == {"not_checked": 1} and "1 not checked" in block["sentence"]
    assert E.block_faults(block, S, TICKET) == []
    # a symbol SEC's list does not name, the same way
    fake_sec.fail.clear()
    register_exel(fake_sec)
    nope = E.collect([{"stage": "anticipation", "ticker": "NOPE"}], S, now=NOW)["rows"][0]
    assert nope["items"]["status"] == "not_checked" and "does not name this symbol" in nope["items"]["sentence"]


def test_a_foreign_issuer_reads_no_items_through_collect(fake_sec):
    fake_sec.issuer("SAP", 1000184, "SAP SE", [("2026-10-20", "2026-10-20T11:00:00.000Z", "6-K", "")],
                    start="2024-01-10", foreign=True)
    row = E.collect([{"stage": "burst", "ticker": "SAP"}], S, now=NOW)["rows"][0]
    assert row["reason"] == "foreign_issuer" and row["items"]["status"] == "foreign" and row["current_reports"] == []


def a_block_with_items(fake_sec):
    entry = register_exel(fake_sec)
    entry["rows"] += [("2026-10-27", "2026-10-27T21:05:00.000Z", "8-K", "1.01,9.01"),
                      ("2026-10-20", "2026-10-20T20:05:00.000Z", "8-K", "7.01")]
    return E.collect(TICKET, S, now=NOW), TICKET


@pytest.mark.parametrize("forge, words", [
    (lambda b: b["rows"][0]["items"].update(status="none"), "are not what its reports give"),
    (lambda b: b["rows"][0]["items"]["material"].clear(), "are not what its reports give"),
    # the report carrying the material item dropped while the count stands: the items are no longer its reports'
    (lambda b: b["rows"][0]["current_reports"].pop(0), "are not what its reports give"),
    (lambda b: b["rows"][0]["items"].update(sentence="No events."), "are not what its reports give"),
    (lambda b: b["rows"][0]["items"].update(count=5), "are not what its reports give"),
    (lambda b: b["rows"][0]["current_report_window"].update(count=1), "are not the recent window's"),
    (lambda b: b["rows"][0]["current_report_window"].update(count=True), "are not the recent window's"),
    (lambda b: b["rows"][0]["current_report_window"].update(unretained_material=1), "are not the recent window's"),
    (lambda b: b["rows"][0]["current_report_window"].pop("unretained_material"), "are not the recent window's"),
    (lambda b: b["rows"][0]["current_reports"].reverse(), "are not the recent window's"),
    # nine reports, one past the bound
    (lambda b: b["rows"][0]["current_reports"].extend(dict(b["rows"][0]["current_reports"][1], accession=f"0000939767-26-{n:06d}", filing_date=f"2026-10-{n:02d}") for n in range(16, 23)), "earnings current reports for EXEL"),
    (lambda b: b["rows"][0]["current_reports"][1].update(items=["7.01", "7.01"]), "earnings current reports for EXEL"),
    (lambda b: b["rows"][0]["current_reports"][1].update(unread=-1), "earnings current reports for EXEL"),
    (lambda b: b["rows"][0]["current_reports"][1].pop("unread"), "earnings current reports for EXEL"),
    (lambda b: b["rows"][0]["current_reports"].append(dict(b["rows"][0]["current_reports"][1], accession="0000939767-26-999999", filing_date="2026-10-01")),
     "are not the recent window's"),
    (lambda b: b["rows"][0]["current_reports"].append(dict(b["rows"][0]["current_reports"][1])), "are not the recent window's"),
    # the oldest report redated before the window, its order, count and items untouched: the window rule alone refuses it
    (lambda b: b["rows"][0]["current_reports"][1].update(filing_date="2026-10-01"), "are not the recent window's"),
    (lambda b: b["rows"][0]["current_reports"][0].update(items=["1.1"]), "earnings current reports for EXEL"),
    (lambda b: b["rows"][0]["current_reports"][0].update(form="10-K"), "earnings current reports for EXEL"),
    (lambda b: b["rows"][0]["current_reports"][0].pop("form"), "earnings current reports for EXEL"),
    (lambda b: b["rows"][0]["items"].pop("codes"), "earnings current-report items for EXEL"),
    (lambda b: b["rows"][0].pop("items"), "row keys"),
    (lambda b: b.update(items_counts={}), "earnings current-report counts"),
    (lambda b: b.pop("items_counts"), "earnings block keys"),
    (lambda b: b.update(sentence=b["sentence"].replace("1 with a material item", "0 with a material item")), "earnings sentence"),
])
def test_the_validator_refuses_a_forged_current_report_row(fake_sec, forge, words):
    block, tickets = a_block_with_items(fake_sec)
    assert E.block_faults(block, S, tickets) == []
    forge(block)
    faults = E.block_faults(block, S, tickets)
    assert faults and any(words in f for f in faults), faults


def test_an_unread_row_given_a_report_or_items_is_refused(fake_sec):
    register_exel(fake_sec)
    tickets = [{"stage": "anticipation", "ticker": "NOPE"}]
    block = E.collect(tickets, S, now=NOW)
    assert block["rows"][0]["reason"] == "not_mapped" and E.block_faults(block, S, tickets) == []
    forged = json.loads(json.dumps(block))
    forged["rows"][0]["current_reports"] = [current_report("2026-10-27")]
    assert any("beside an unread source" in f for f in E.block_faults(forged, S, tickets))
    forged = json.loads(json.dumps(block))
    forged["rows"][0]["items"] = items([])
    assert any("beside an unread source" in f for f in E.block_faults(forged, S, tickets))
    forged = json.loads(json.dumps(block))
    forged["rows"][0]["current_report_window"] = {"count": 0, "unretained_material": 0}
    assert any("beside an unread source" in f for f in E.block_faults(forged, S, tickets))


def version_one(block) -> dict:
    v1 = {k: v for k, v in block.items() if k != "items_counts"}
    v1["version"] = 1
    v1["rows"] = [{k: v for k, v in r.items() if k not in ("current_reports", "current_report_window", "items")}
                  for r in v1["rows"]]
    v1["sentence"] = E.block_sentence(v1)
    return v1


def test_a_version_one_block_is_read_under_version_one_and_refused_under_two(fake_sec):
    block, tickets = a_block_with_items(fake_sec)
    v1 = version_one(block)
    assert "SEC current reports" not in v1["sentence"] and v1["sentence"] == block["sentence"].split(" SEC current reports")[0]
    assert E.block_faults(v1, S, tickets, version=1) == []
    assert E.block_faults(v1, S, tickets) == ["earnings block keys"]
    assert E.block_faults(block, S, tickets, version=1) == ["earnings block keys"]
    assert E.block_faults(block, S, tickets, version=3) == ["earnings rules version"]
    # a record: the version its rules archived decides, and an unknown one is named
    data = {"rules": {"earnings_risk": {"version": 1}}, "run": {"earnings": v1, "session": S, "published_at": NIGHT},
            "bursts": [{"ticker": "EXEL", "plan": {}}], "trades": ["EXEL"], "watchlist": {"top": []}}
    assert E.record_faults(data) == []
    data["rules"]["earnings_risk"]["version"] = 2
    assert E.record_faults(data) == ["run.earnings block keys"]
    data["run"]["earnings"] = block
    assert E.record_faults(data) == []
    for bad in (3, True, "2", None):
        data["rules"]["earnings_risk"]["version"] = bad
        assert E.record_faults(data) == ["run.earnings rules version is unknown"], bad


def test_a_closed_night_rereads_a_version_one_block(fake_sec):
    block, tickets = a_block_with_items(fake_sec)
    v1 = version_one(block)
    calls = len(fake_sec.calls)
    got = E.carried(v1, S, tickets, now=NOW)
    assert got["version"] == 2 and got["rows"][0]["items"]["status"] == "material" and len(fake_sec.calls) > calls
    # and keeps a version-2 block as it stands
    assert E.carried(block, S, tickets, now=NOW) is block
