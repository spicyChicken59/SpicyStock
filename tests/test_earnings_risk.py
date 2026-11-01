"""The earnings warning (src/earnings_risk.py): an estimate from SEC results
filings, read against each ticket's own hold window, never a refusal.

Every date below is a real XNYS date; the windows are ``plan.next_sessions``'
own answer, so Thanksgiving and its early close are the calendar's, not ours.
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


def verdict(filings, *, session=S, retrieved=NIGHT, start="2023-01-03", foreign=False):
    return E.assess(filings, session, E.window(session), retrieved, start, foreign)


# ------------------------------------------------------------------ the rule ---
def test_the_window_is_the_plans_own_hold():
    assert DAYS == [d.isoformat() for d in plan.next_sessions(date.fromisoformat(S), plan.FINAL_EXIT_DAY)]
    assert DAYS == ["2026-10-30", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"]
    # Thanksgiving is skipped and the Friday after it is a day of the hold
    assert E.window("2026-11-24") == ["2026-11-25", "2026-11-27", "2026-11-30", "2026-12-01", "2026-12-02"]


@pytest.mark.parametrize("offset, expected, placement", [
    (-1, "estimate_inside", "held"),
    (3, "estimate_inside", "held"),
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
    if q < date.fromisoformat(S) and expected == "estimate_inside":
        expected, placement = "estimate_near", "boundary"
    if q < date.fromisoformat(DAYS[0]) and q >= date.fromisoformat(S) and expected == "estimate_inside":
        placement = "pre_entry"
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
    # accepted after the run read SEC is not something the run saw
    late = quarters("2025-10-30", through="2026-08-01") + [filing(S, "23:30:00")]
    assert verdict(late)["verdict"] != "reported_after_signal"


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
    # past the overdue horizon the old estimate no longer reads as a cycle
    stale = quarters("2025-08-01", through="2026-05-01")
    assert verdict(stale)["verdict"] in ("estimate_outside", "estimate_near", "estimate_inside")
    assert verdict(stale)["verdict"] != "overdue"


@pytest.mark.parametrize("case, reason", [
    ("late_start", "history_not_read"), ("no_start", "history_not_read"), ("none", "no_results_history"),
    ("foreign", "foreign_issuer"), ("short", "history_short"), ("silent", "no_recent_results"),
])
def test_unknown_is_never_clearance(case, reason):
    # an observed filing after the signal needs no history; these have none
    kwargs = {"late_start": dict(filings=quarters("2025-10-30", through="2026-08-01"), start="2026-01-02"),
              "no_start": dict(filings=[], start=None),
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
    # a long recent file needs no older one
    fake_sec.fail.clear()
    fake_sec.calls.clear()
    register_exel(fake_sec)
    E.collect([{"stage": "burst", "ticker": "EXEL"}], S, now=datetime(2026, 10, 29, 23, tzinfo=timezone.utc))
    assert not any("submissions-001" in u for u in fake_sec.calls)


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
    results, start, forms = E._columns(cols)
    assert [r["accession"] for r in results] == ["0000000001-26-000001"]
    assert start == date(2026, 5, 1) and forms == {"8-K", "8-K/A"}


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
    (lambda b: b.update(version=2), "version"),
    (lambda b: b.update(session="2026-10-28"), "session"),
    (lambda b: b["rows"][0]["sources"].clear(), "without its source"),
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
    assert E.record_faults({"rules": {"earnings_risk": {}}, "run": {"session": S}}) == \
        ["run.earnings is missing under rules that write it"]
    block, _ = a_block(fake_sec)
    data = {"rules": {"earnings_risk": {}}, "run": {"session": S, "earnings": block},
            "bursts": [{"ticker": "EXEL", "plan": {}}], "trades": ["EXEL"], "watchlist": {"top": []}}
    assert E.record_faults(data) == []
    data["trades"] = []
    assert E.record_faults(data) == ["run.earnings rows are not the record's tickets"]


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


def test_the_mail_prints_each_tickets_warning_verbatim(fake_sec):
    block, _ = a_block(fake_sec)
    data = {"run": {"earnings": block}}
    assert report._earnings_line(data, "burst", "EXEL").endswith(f"{report.esc(block['rows'][0]['sentence'])}</p>")
    assert report._earnings_line(data, "anticipation", "EXEL") == ""
    assert report._earnings_line({"run": {}}, "burst", "EXEL") == ""
