"""Data quality in the execution handoff, read where it applies.

Before 25 November 2026 ``orders.json``'s night check read the run's status
word: one ``degraded`` (a refused chart review, a mail that failed, a single
stale stock) stopped every ticket of the night. The owner's decision is to
check each ticket's own data instead. These tests hold the three readings:

* the night's ``market_inputs`` check, off the record's own input ledger and
  never off the status word;
* each ticket's ``inputs`` check, off its own sealed frame and archived bars,
  with the record's lists read as evidence against a stock and never for it;
* each ticket's ``reader`` check.

Every forgery starts from a fixture night on which a ticket is ``go`` and the
night allows trading, so a rule that stops it is seen stopping it.
"""
import copy
import json
from pathlib import Path

import pytest

from src import inputs, morning, orders, report

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "tests" / "fixtures" / "page"
SEALED_PUBLICATION = morning._publication          # the record's own integrity check, as build() asks it


def record(name: str = "next") -> dict:
    return json.loads((PAGE / f"{name}.json").read_bytes())


def build(data: dict) -> dict:
    doc = orders.build(json.dumps(data).encode())
    assert orders.problems(doc) == []
    return doc


def night_check(data: dict, key: str = "market_inputs") -> dict:
    return next(c for c in orders._night(data, []) if c["key"] == key)


def night_codes(doc: dict) -> list:
    return [r["code"] for r in doc["reasons"] if r["scope"] == "night"]


def build_past_the_seal(monkeypatch, data: dict) -> dict:
    """``orders.json`` over a record whose input ledger was changed after it was sealed. The
    record's own integrity check refuses such bytes before any check here is asked (asserted),
    so the binding is taken from the unchanged night and the changed record is read as given:
    the rule under test is what the handoff says of a ledger like this one."""
    with pytest.raises(ValueError, match="publication"):
        SEALED_PUBLICATION(json.dumps(data).encode(), allow_fixture=True)
    binding = SEALED_PUBLICATION((PAGE / "next.json").read_bytes(), allow_fixture=True)[1]
    monkeypatch.setattr(morning, "_publication", lambda raw, allow_fixture=False: (data, binding))
    doc = orders.build(json.dumps(data).encode())
    assert orders.problems(doc) == []
    return doc


def test_the_go_night_these_tests_start_from_allows_trading_with_one_ticket_go():
    doc = build(record())
    assert doc["trade_allowed"] is True and night_codes(doc) == []
    assert [(t["symbol"], t["status"]) for t in doc["tickets"]] == [("NVDA", "go"), ("COIL", "human_review")]
    assert [c["key"] for c in doc["night_checks"]] == list(orders.NIGHT_CHECKS)
    assert [c["key"] for c in doc["tickets"][0]["checks"]] == list(orders.TICKET_CHECKS)
    assert "data" not in orders.NIGHT_CHECKS and "data_degraded" not in orders.REASONS


# ----------------------------------------------- the status word decides nothing --
#: every problem word a published record can carry that says nothing about the market's inputs
NOT_MARKET_WIDE = ("claude_unavailable", "claude_partial", "chart_missing", "email_failed", "push_retried")


def test_the_problem_words_named_here_are_the_reports_own():
    # a new problem word must be placed: market-wide (read off the ledger) or not
    assert set(NOT_MARKET_WIDE) | {"coverage_thin", "universe_cached"} == set(report.PROBLEM_KINDS)


@pytest.mark.parametrize("word", NOT_MARKET_WIDE)
def test_a_night_degraded_by_a_word_that_is_not_about_the_markets_inputs_still_trades(word):
    data = record()
    data["run"]["status"] = "degraded"
    data["run"]["problems"] = [{"kind": word, "message": "a synthetic problem"}]
    doc = build(data)
    check = next(c for c in doc["night_checks"] if c["key"] == "market_inputs")
    assert (check["status"], check["reason"]) == ("pass", None)
    assert f"run status degraded ({word})" in check["detail"]
    assert doc["trade_allowed"] is True and night_codes(doc) == []
    assert doc["tickets"][0]["status"] == "go"
    assert (doc["source"]["run_status"], doc["source"]["run_problems"]) == ("degraded", [word])


def test_the_runs_status_and_problem_words_are_carried_for_reference_only():
    data = record()
    data["run"]["status"] = "degraded"
    data["run"]["problems"] = [{"kind": "email_failed"}, {"kind": "claude_partial"}, {"kind": "email_failed"}]
    doc = build(data)
    assert doc["source"]["run_problems"] == ["email_failed", "claude_partial"]       # once each, in order
    assert doc["trade_allowed"] is True


# --------------------------------------------------- the market's inputs ---
def short_night(missing: int, *, intended: int = 400) -> dict:
    """The go night with ``intended`` stocks of which ``missing`` had no usable bars, its
    tolerance block's limit the record's own archived fraction of them."""
    data = record()
    fraction = data["rules"]["pipeline"]["stale_tolerance_fraction"]
    acceptance = data["run"]["coverage"]["acceptance"]
    acceptance.update(intended_stocks=intended, ready_stocks=intended - missing)
    data["run"]["input_tolerance"]["limit"] = inputs.stale_limit(intended, fraction)
    return data


def test_the_limit_is_the_records_own_archived_fraction_and_the_boundary_is_inclusive(monkeypatch):
    data = short_night(0)
    limit = data["run"]["input_tolerance"]["limit"]
    assert limit == 4 == inputs.stale_limit(400, data["rules"]["pipeline"]["stale_tolerance_fraction"])
    at = night_check(short_night(limit))
    assert (at["status"], at["reason"]) == ("pass", None)
    assert at["detail"].startswith(f"{400 - limit} of 400 intended stocks had usable bars; {limit} without, "
                                   f"against a limit of {limit}")
    over = night_check(short_night(limit + 1))
    assert (over["status"], over["reason"]) == ("fail", "market_inputs_incomplete")
    doc = build_past_the_seal(monkeypatch, short_night(limit + 1))
    assert doc["trade_allowed"] is False and night_codes(doc) == ["market_inputs_incomplete"]
    assert doc["tickets"][0]["status"] == "go"          # the ticket's own checks are its own; the night stops it
    assert build_past_the_seal(monkeypatch, short_night(limit))["trade_allowed"] is True


def test_the_count_is_every_kind_of_gap_not_the_stale_tail_alone():
    # twelve stocks the fetch never reached: no stale stock at all, and the night is short
    partial = record("partial")
    assert partial["run"]["input_tolerance"]["stale_stocks"] == 0
    assert partial["run"]["coverage"]["reasons"]["unfetched_budget"]["count"] == 12
    check = night_check(partial)
    assert (check["status"], check["reason"]) == ("fail", "market_inputs_incomplete")
    assert "21 of 32 intended stocks had usable bars; 11 without, against a limit of 0" in check["detail"]
    thin = night_check(record("thin"))                  # one stale stock of a hundred, inside its limit of one
    assert (thin["status"], thin["reason"]) == ("pass", None)


@pytest.mark.parametrize("errors, unattempted", [(1, 0), (0, 2), (3, 1)])
def test_a_night_on_which_not_every_measured_stock_was_scanned_and_checked_stops(errors, unattempted):
    data = record()
    coverage = data["run"]["coverage"]
    assert coverage["acceptance"]["complete_evaluation"] is True and coverage["errors"] == 0
    coverage.update(errors=errors, scan_unattempted=unattempted)
    coverage["acceptance"]["complete_evaluation"] = False
    check = night_check(data)
    assert (check["status"], check["reason"]) == ("fail", "market_inputs_incomplete")
    assert (f"not every measured stock was scanned and checked ({errors} scan or checklist errors, "
            f"{unattempted} not attempted)") in check["detail"]
    assert "scanned and checked" not in night_check(record())["detail"]


def test_a_selection_cut_at_its_capacity_or_a_seed_fallback_stops_the_night():
    cut = record()
    cut["run"]["coverage"]["acceptance"]["capacity_excluded"] = 1
    check = night_check(cut)
    assert (check["status"], check["reason"]) == ("fail", "market_inputs_incomplete")
    assert "1 cut at the selection's capacity" in check["detail"]
    for kind, status in (("directory_cache", "pass"), ("seed", "fail"), ("explicit", "fail"), ("unknown", "fail"),
                         (None, "fail")):
        cached = record()
        cached["run"]["status"] = "degraded"
        cached["run"]["problems"] = [{"kind": "universe_cached", "message": "the directory did not answer"}]
        cached["run"]["universe"]["source_kind"] = kind
        check = night_check(cached)
        assert check["status"] == status, kind
        assert ("the seed list stood in" in check["detail"]) is (status == "fail")
    # the seed list as the owner's own configured universe carries no problem word, and is not a fallback
    chosen = record()
    chosen["run"]["universe"]["source_kind"] = "seed"
    assert night_check(chosen)["status"] == "pass"


@pytest.mark.parametrize("label, change", [
    ("a status this file does not read", lambda d: d["run"].update(status="failed")),
    ("no status", lambda d: d["run"].pop("status")),
    ("a problem word this file does not read", lambda d: d["run"].update(problems=[{"kind": "new_word"}])),
    ("a problem that is not an object", lambda d: d["run"].update(problems=["coverage_thin"])),
    ("problems that are not a list", lambda d: d["run"].update(problems={"kind": "email_failed"})),
    ("no ledger", lambda d: d["run"].pop("coverage")),
    ("a ledger with no version", lambda d: d["run"]["coverage"].pop("version")),
    ("no acceptance block", lambda d: d["run"]["coverage"].pop("acceptance")),
    ("a count that is a float", lambda d: d["run"]["coverage"]["acceptance"].update(ready_stocks=32.0)),
    ("a count that is a bool", lambda d: d["run"]["coverage"]["acceptance"].update(capacity_excluded=False)),
    ("a negative count", lambda d: d["run"]["coverage"]["acceptance"].update(capacity_excluded=-1)),
    ("more ready than intended", lambda d: d["run"]["coverage"]["acceptance"].update(ready_stocks=33)),
    ("no archived fraction", lambda d: d["rules"]["pipeline"].pop("stale_tolerance_fraction")),
    ("a fraction that is not a number", lambda d: d["rules"]["pipeline"].update(stale_tolerance_fraction="1%")),
    ("no tolerance block", lambda d: d["run"].pop("input_tolerance")),
    ("a limit that is not the archived fraction's", lambda d: d["run"]["input_tolerance"].update(limit=3)),
    ("a limit that is a float", lambda d: d["run"]["input_tolerance"].update(limit=0.0)),
    ("no word on whether every stock was scanned", lambda d: d["run"]["coverage"]["acceptance"].pop(
        "complete_evaluation")),
    ("a scan word that is not true or false", lambda d: d["run"]["coverage"]["acceptance"].update(
        complete_evaluation=1)),
    ("no scan error count", lambda d: d["run"]["coverage"].pop("errors")),
    ("an unattempted count that is a float", lambda d: d["run"]["coverage"].update(scan_unattempted=0.0)),
])
def test_what_cannot_be_read_is_not_complete(label, change):
    data = record()
    change(data)
    check = night_check(data)
    assert (check["status"], check["reason"]) == ("not_evaluated", "market_inputs_unknown"), label


def test_a_night_whose_ledger_cannot_be_read_allows_no_trade(monkeypatch):
    data = record()
    for key in ("coverage", "input_tolerance"):         # a record from before the ledger
        data["run"].pop(key)
    doc = build_past_the_seal(monkeypatch, data)
    assert doc["trade_allowed"] is False and night_codes(doc) == ["market_inputs_unknown"]
    assert doc["tickets"][0]["status"] == "go"


# ------------------------------------------------------ a ticket's own inputs --
def ticket_of(data: dict, symbol: str = "NVDA", change=None) -> dict:
    """The ticket ``orders._ticket()`` writes for ``symbol`` after ``change(row, data)``."""
    data = copy.deepcopy(data)
    admitted = next(r for r in morning.admitted_rows(data) if r["ticker"] == symbol)
    rows = data["bursts"] if admitted["kind"] == "burst" else data["watchlist"]["top"]
    if change is not None:
        change(next(r for r in rows if r["ticker"] == symbol), data)
    return orders._ticket(data, admitted, ["2026-09-14"] * 5)


def check_of(ticket: dict, key: str) -> dict:
    return next(c for c in ticket["checks"] if c["key"] == key)


def test_a_tickets_inputs_pass_on_its_own_sealed_frame_and_its_last_two_bars():
    ticket = ticket_of(record())
    own = check_of(ticket, "inputs")
    assert (own["status"], own["reason"]) == ("pass", None)
    assert own["detail"] == "source frame and last two bars dated 2026-09-10 and 2026-09-11"
    assert ticket["status"] == "go"
    # a setting-up ticket is read the same way, off its own row
    coil = ticket_of(record("notrade"), "COIL")
    assert check_of(coil, "inputs")["detail"] == "source frame and last two bars dated 2026-09-09 and 2026-09-10"


def name_in_tolerance(key):
    return lambda row, d: d["run"]["input_tolerance"].update({key: ["AAA", row["ticker"]]})


def name_in_ledger(key):
    def change(row, d):
        d["run"]["coverage"]["reasons"][key] = {"count": 2, "identity": "0" * 16, "sample": ["AAA", row["ticker"]]}
    return change


@pytest.mark.parametrize("where, change", (
    [(f"input_tolerance.{k}", name_in_tolerance(k)) for k in ("names", "held", "first_sessions")]
    + [(f"coverage.{k}", name_in_ledger(k)) for k in orders.EXCEPTION_LISTS]))
def test_a_stock_the_record_names_without_a_usable_frame_blocks_its_ticket(where, change):
    ticket = ticket_of(record(), change=change)
    own = check_of(ticket, "inputs")
    assert (own["status"], own["reason"], own["detail"]) == ("fail", "inputs_exception", f"named in {where}")
    assert (ticket["status"], ticket["reasons"]) == ("blocked", ["inputs_exception"])


def test_the_exception_lists_read_are_the_ledgers_own():
    reasons = record()["run"]["coverage"]["reasons"]
    # every list the ledger samples that names a stock without a usable session frame is read
    assert {"no_bars", "stale", "gapped", "unreadable", "refused", "dropped", "unfetched_budget",
            "unfetched_failure"} == set(orders.EXCEPTION_LISTS)
    assert set(orders.EXCEPTION_LISTS) <= set(reasons), "a list this file reads is not one the ledger writes"


def test_another_stocks_exception_blocks_no_other_ticket_and_stops_no_night_inside_the_limit(monkeypatch):
    data = short_night(1)                               # one stale stock of 400, inside the limit of 4
    data["run"]["status"] = "degraded"
    data["run"]["problems"] = [{"kind": "coverage_thin", "message": "one stock was a session behind"}]
    data["run"]["input_tolerance"].update(names=["ZZZZ"], stale_stocks=1)
    data["run"]["coverage"]["reasons"]["stale"] = {"count": 1, "identity": "0" * 16, "sample": ["ZZZZ"]}
    doc = build_past_the_seal(monkeypatch, data)
    assert doc["trade_allowed"] is True and doc["tickets"][0]["status"] == "go"
    assert check_of(doc["tickets"][0], "inputs")["status"] == "pass"


def test_a_sampled_list_is_never_evidence_for_a_stock_and_the_detail_says_which_were_short():
    def sampled(row, d):
        d["run"]["input_tolerance"].update(names=None, first_sessions=None)     # counted past the bound, not named
        d["run"]["coverage"]["reasons"]["stale"] = {"count": 30, "identity": "0" * 16, "sample": ["AAA", "BBB"]}
    ticket = ticket_of(record(), change=sampled)
    own = check_of(ticket, "inputs")
    # the row's own frame and bars still say it was read through the session: that is the evidence
    assert own["status"] == "pass"
    assert own["detail"].endswith("; sampled short, so no evidence either way: input_tolerance.names, "
                                  "input_tolerance.first_sessions, coverage.stale")

    def sampled_and_unshown(row, d):
        sampled(row, d)
        row["series"] = row["series"][:-1]
    held = ticket_of(record(), change=sampled_and_unshown)
    assert (held["status"], held["reasons"]) == ("human_review", ["inputs_unknown"])
    assert "sampled short" in check_of(held, "inputs")["detail"]


def test_the_ledgers_sampled_stale_list_is_no_gap_when_the_tolerance_names_every_stale_stock():
    def named(row, d):
        d["run"]["input_tolerance"].update(names=["AAA", "BBB", "CCC"], stale_stocks=3)
        d["run"]["coverage"]["reasons"]["stale"] = {"count": 3, "identity": "0" * 16, "sample": ["AAA", "BBB"]}
    own = check_of(ticket_of(record(), change=named), "inputs")
    assert own["status"] == "pass" and "sampled short" not in own["detail"]

    def counted_more(row, d):                      # the tolerance's list is shorter than its own count
        named(row, d)
        d["run"]["input_tolerance"]["stale_stocks"] = 4
    assert own["detail"] != check_of(ticket_of(record(), change=counted_more), "inputs")["detail"]
    assert check_of(ticket_of(record(), change=counted_more), "inputs")["detail"].endswith(
        "sampled short, so no evidence either way: coverage.stale")

    def other_list(row, d):                        # another list short of its count is still a gap
        named(row, d)
        d["run"]["coverage"]["reasons"]["gapped"] = {"count": 3, "identity": "0" * 16, "sample": ["DDD"]}
    assert check_of(ticket_of(record(), change=other_list), "inputs")["detail"].endswith(
        "sampled short, so no evidence either way: coverage.gapped")


def test_a_tolerance_block_from_before_first_sessions_is_not_called_short_for_lacking_them():
    def older(row, d):
        d["run"]["input_tolerance"]["version"] = 2
        d["run"]["input_tolerance"].pop("first_sessions")
    assert check_of(ticket_of(record(), change=older), "inputs")["detail"] == \
        "source frame and last two bars dated 2026-09-10 and 2026-09-11"

    def newer(row, d):
        d["run"]["input_tolerance"].pop("first_sessions")
    assert "input_tolerance.first_sessions" in check_of(ticket_of(record(), change=newer), "inputs")["detail"]


def bar(**changes):
    return lambda row, d: row["series"][-1].update(changes)


def previous_bar(**changes):
    """The bar of the session before: the second of the two the check reads."""
    return lambda row, d: row["series"][-2].update(changes)


@pytest.mark.parametrize("label, change, missing", [
    ("a frame evaluated at another session", lambda row, d: row["evidence"]["source"].update(
        evaluated_session="2026-09-10"), "sealed source frame"),
    ("a frame whose previous session is another", lambda row, d: row["evidence"]["source"].update(
        previous_session="2026-09-08"), "sealed source frame"),
    ("no sealed source", lambda row, d: row["evidence"].pop("source"), "sealed source frame"),
    ("no calendar to name the previous session", lambda row, d: d["run"].pop("calendar"), "sealed source frame"),
    ("no archived bars", lambda row, d: row.pop("series"), "last two archived bars"),
    ("one archived bar", lambda row, d: row.update(series=row["series"][-1:]), "last two archived bars"),
    ("a last bar of the session before", lambda row, d: row["series"].pop(), "last two archived bars"),
    ("a gap before the session", lambda row, d: row["series"].pop(-2), "last two archived bars"),
    ("a bar that is not an object", lambda row, d: row["series"].__setitem__(-1, "2026-09-11"),
     "last two archived bars"),
    ("a null close", bar(c=None), "last two archived bars"),
    ("a zero price", bar(l=0.0), "last two archived bars"),
    ("a negative volume", bar(v=-1.0), "last two archived bars"),
    ("a low over the open", bar(l=130.0), "last two archived bars"),
    ("a high under the close", bar(h=133.0), "last two archived bars"),
    ("a price that is a bool", bar(o=True), "last two archived bars"),
    ("a price that is text", bar(c="133.99"), "last two archived bars"),
    ("a null close the session before", previous_bar(c=None), "last two archived bars"),
    ("a high under the close the session before", previous_bar(h=0.5), "last two archived bars"),
    ("a previous bar that is not an object", lambda row, d: row["series"].__setitem__(-2, None),
     "last two archived bars"),
])
def test_a_ticket_the_record_does_not_show_through_the_session_is_held_for_a_person(label, change, missing):
    ticket = ticket_of(record(), change=change)
    own = check_of(ticket, "inputs")
    assert (own["status"], own["reason"]) == ("not_evaluated", "inputs_unknown"), label
    assert missing in own["detail"]
    assert (ticket["status"], ticket["reasons"]) == ("human_review", ["inputs_unknown"])
    assert "inputs_unknown" in orders.REVIEW_REASONS and "inputs_exception" not in orders.REVIEW_REASONS


def test_a_zero_volume_bar_is_a_readable_bar_as_the_frames_own_rule_reads_it():
    # the provider's placeholder for a session with no trade passes the frame rule; the scans refuse it elsewhere
    assert check_of(ticket_of(record(), change=bar(v=0.0)), "inputs")["status"] == "pass"
    assert orders._readable_bar({"o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0, "v": 0})
    assert not orders._readable_bar({"o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0})
    assert not orders._readable_bar({"o": 1.0, "h": float("inf"), "l": 1.0, "c": 1.0, "v": 1})
    assert not orders._readable_bar({"o": float("nan"), "h": 1.0, "l": 1.0, "c": 1.0, "v": 1})


def test_named_beats_shown_a_stock_on_a_list_is_blocked_whatever_its_row_shows():
    def both(row, d):
        d["run"]["input_tolerance"]["names"] = [row["ticker"]]
        d["run"]["coverage"]["reasons"]["stale"] = {"count": 1, "identity": "0" * 16, "sample": [row["ticker"]]}
    own = check_of(ticket_of(record(), change=both), "inputs")
    assert (own["status"], own["detail"]) == ("fail", "named in input_tolerance.names, coverage.stale")


# ------------------------------------------------------- the chart reader ---
def test_a_burst_ticket_passes_on_an_accepted_review_made_with_its_chart():
    reader = check_of(ticket_of(record()), "reader")
    assert (reader["status"], reader["reason"], reader["detail"]) == ("pass", None, "accepted, chart seen")


@pytest.mark.parametrize("label, change", [
    ("the row's coverage is a fallback", lambda row, d: row.update(reader_coverage="fallback")),
    ("the row carries no coverage", lambda row, d: row.pop("reader_coverage")),
    ("the sealed gate's coverage is not accepted", lambda row, d: row["evidence"]["gate"].update(
        reader_coverage="not_selected")),
    ("the reading is the checklist's own", lambda row, d: row["claude"].update(source="mechanical")),
    ("no reading", lambda row, d: row.pop("claude")),
])
def test_a_burst_ticket_without_an_accepted_review_is_blocked(label, change):
    ticket = ticket_of(record(), change=change)
    reader = check_of(ticket, "reader")
    assert (reader["status"], reader["reason"]) == ("fail", "reader_not_accepted"), label
    assert (ticket["status"], ticket["reasons"]) == ("blocked", ["reader_not_accepted"])


@pytest.mark.parametrize("seen", [False, None, "yes", 1])
def test_an_accepted_review_made_without_its_chart_is_held_for_a_person(seen):
    ticket = ticket_of(record(), change=lambda row, d: row["claude"].update(chart_seen=seen))
    reader = check_of(ticket, "reader")
    assert (reader["status"], reader["reason"]) == ("not_evaluated", "reader_chart_missing")
    assert (ticket["status"], ticket["reasons"]) == ("human_review", ["reader_chart_missing"])


def test_a_setting_up_ticket_is_measured_and_never_chart_read():
    data = record("notrade")
    coil = ticket_of(data, "COIL")
    reader = check_of(coil, "reader")
    assert (reader["status"], reader["reason"]) == ("pass", None) and reader["detail"].startswith("not applicable")
    # nothing about a reader on its row can stop it
    stripped = ticket_of(data, "COIL", change=lambda row, d: row.pop("claude", None))
    assert check_of(stripped, "reader")["status"] == "pass"


def test_a_reader_outage_stops_no_setting_up_ticket_and_no_night():
    """The night the old rule stopped whole: the chart reader unavailable, a chart that did not
    render, the run degraded. Its setting-up ticket is read on its own checks."""
    degraded = record("degraded")
    assert degraded["run"]["status"] == "degraded"
    assert [p["kind"] for p in degraded["run"]["problems"]] == ["chart_missing", "claude_unavailable"]
    doc = build(degraded)
    assert night_codes(doc) == []                       # every night check passes
    ticket = doc["tickets"][0]
    assert (ticket["symbol"], ticket["setup_type"]) == ("COIL", "anticipation")
    assert check_of(ticket, "inputs")["status"] == check_of(ticket, "reader")["status"] == "pass"
    # what holds it is its own SEC read, not the night's status word
    assert ticket["reasons"] == ["sec_unknown"] and doc["trade_allowed"] is False
    assert doc["reasons"] == [{"scope": "COIL", "code": "sec_unknown"}]


# ----------------------------------------------------------- the documents --
def test_the_guide_and_the_readme_name_each_check_and_reason_as_the_code_spells_it():
    guide = " ".join((ROOT / "docs" / "operations" / "orders.md").read_text().split())
    readme = " ".join((ROOT / "README.md").read_text().split())
    for word in ("market_inputs_incomplete", "market_inputs_unknown", "inputs_unknown", "inputs_exception",
                 "reader_chart_missing", "reader_not_accepted"):
        assert f"`{word}`" in guide and word in orders.REASONS, word
    assert "`light`, `market_inputs`, `publication_time`, `cross_check`, `account`" in readme
    assert "never off the run's status word" in readme and "never the run's status word" in guide
    assert "`data_degraded`" not in guide and "`data_degraded`" not in readme
    assert "(`inputs.stale_limit()`" in readme and callable(inputs.stale_limit)
