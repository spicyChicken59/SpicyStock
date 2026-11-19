"""Event and data safety: the SEC filing flags (src/sec_flags.py), the second-
source cross-check (src/cross_check.py), the event registry's review notes
(src/event_risk.py, tools/check_event_reviews.py) and what each does to a
ticket in orders.json.

Every clock here is pinned; the one check that reads the real date is the CI
step that runs tools/check_event_reviews.py, and its rule is held below at
fixed dates on both sides of a due date."""
from __future__ import annotations

import copy
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from src import cross_check, earnings_risk, event_risk, issuer_evidence, morning, orders, report, sec_flags
from tests.fakes import FakeSec

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "tests" / "fixtures" / "page"
SESSION = "2026-11-18"
NOW = datetime(2026, 11, 18, 23, 30, tzinfo=timezone.utc)


def page(name: str) -> dict:
    return json.loads((PAGE / f"{name}.json").read_text())


def days_before(n: int) -> str:
    return (date.fromisoformat(SESSION) - timedelta(days=n)).isoformat()


# ------------------------------------------------------------ SEC flags ---
def sec_with(rows_by_ticker: dict) -> FakeSec:
    sec = FakeSec()
    for i, (ticker, rows) in enumerate(rows_by_ticker.items()):
        sec.issuer(ticker, 1000 + i, f"{ticker} Inc.",
                   [(d, f"{d}T21:00:00.000Z", form, items) for d, form, items in rows], start="2024-01-02")
    return sec


def names(*tickers, stage="burst"):
    return [{"stage": stage, "ticker": t} for t in tickers]


def test_each_flagged_form_and_item_is_named_and_an_ordinary_filing_is_not():
    sec = sec_with({
        "TEND": [(days_before(3), "SC 14D9", "")],
        "PROX": [(days_before(29), "DEFM14A", "")],
        "AGRE": [(days_before(1), "8-K", "1.01,9.01")],
        "DLST": [(days_before(5), "8-K/A", "3.01")],
        "EARN": [(days_before(2), "8-K", "2.02,9.01"), (days_before(10), "10-Q", "")],
        "OLD": [(days_before(31), "SC TO-T", ""), (days_before(40), "8-K", "5.01")],
    })
    block = sec_flags.collect(names("TEND", "PROX", "AGRE", "DLST", "EARN", "OLD"), SESSION, fetch=sec, now=NOW)
    state = {r["ticker"]: r for r in block["rows"]}
    assert {t: r["state"] for t, r in state.items()} == {"TEND": "flagged", "PROX": "flagged", "AGRE": "flagged",
                                                         "DLST": "flagged", "EARN": "clear", "OLD": "clear"}
    assert state["AGRE"]["filings"][0]["items"] == ["1.01"] and state["TEND"]["filings"][0]["form"] == "SC 14D9"
    assert block["since"] == days_before(sec_flags.WINDOW_DAYS) and block["status"] == "flagged"
    assert block["requests"] == 1 + 6 and sec.calls[0] == issuer_evidence.MAPPING_URL
    assert "AGRE (8-K item 1.01 " in block["sentence"] and "flagged for review" in block["sentence"]
    assert block["sentence"].endswith("refuses nothing by itself.")


def test_a_name_sec_cannot_answer_for_is_unknown_and_unknown_is_never_clear():
    sec = sec_with({"OK": [(days_before(2), "8-K", "2.02")]})
    sec.fail["CIK0000001000"] = "http_error"
    block = sec_flags.collect(names("OK", "GONE"), SESSION, fetch=sec, now=NOW)
    assert [(r["ticker"], r["state"], r["reason"]) for r in block["rows"]] == [
        ("OK", "unknown", "http_error"), ("GONE", "unknown", "not_mapped")]
    assert block["status"] == "unknown" and "which is not clear" in block["sentence"]
    down = sec_with({"OK": []})
    down.fail[issuer_evidence.MAPPING_URL] = "timeout"
    every = sec_flags.collect(names("OK", "TWO"), SESSION, fetch=down, now=NOW)
    assert {r["reason"] for r in every["rows"]} == {"timeout"} and every["requests"] == 1


def test_a_filing_list_that_names_another_ticker_is_not_this_ticker():
    sec = sec_with({"REAL": [(days_before(2), "SC TO-T", "")]})
    sec.mapping_body = json.dumps({"fields": FakeSec.MAPPING_FIELDS,
                                   "data": [[1000, "REAL Inc.", "ALIAS", "Nasdaq"]]}).encode()
    row = sec_flags.collect(names("ALIAS"), SESSION, fetch=sec, now=NOW)["rows"][0]
    assert (row["state"], row["reason"]) == ("unknown", "not_mapped")


def test_the_bound_reads_at_most_max_names_and_names_the_rest_not_checked():
    tickers = [f"N{i:02d}" for i in range(sec_flags.MAX_NAMES + 3)]
    sec = sec_with({t: [] for t in tickers})
    block = sec_flags.collect(names(*tickers), SESSION, fetch=sec, now=NOW)
    assert [r["reason"] for r in block["rows"][sec_flags.MAX_NAMES:]] == ["not_checked"] * 3
    assert block["requests"] == 1 + sec_flags.MAX_NAMES and block["status"] == "unknown"


def test_the_names_are_the_tickets_then_each_listed_setup_that_is_not_one():
    tickets = [{"stage": "burst", "ticker": "AAA"}, {"stage": "anticipation", "ticker": "COIL"}]
    top = [{"ticker": "COIL"}, {"ticker": "WAIT"}, {"bad": 1}, "x"]
    assert sec_flags.names_of(tickets, top) == tickets + [{"stage": "anticipation", "ticker": "WAIT"}]
    assert sec_flags.collect([], SESSION, fetch=lambda u: pytest.fail("asked"), now=NOW)["status"] == "not_applicable"


def test_a_collector_that_raises_leaves_every_name_unknown_and_the_night_publishing(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("unforeseen")

    monkeypatch.setattr(sec_flags, "collect", boom)
    block = sec_flags.safe_collect(names("AAA"), SESSION)
    assert block["rows"][0]["state"] == "unknown" and block["status"] == "unknown"


def test_the_validator_holds_the_flags_block_under_the_rules_that_write_it():
    data = page("full")
    assert data["rules"]["sec_flags"]["window_days"] == sec_flags.WINDOW_DAYS and sec_flags.faults(data) == []
    for change, words in ((lambda d: d["run"].pop("sec_flags"), "missing"),
                          (lambda d: d["run"]["sec_flags"].update(status="clear" if d["run"]["sec_flags"]["status"] != "clear" else "flagged"), "status"),
                          (lambda d: d["run"]["sec_flags"]["rows"].append({"ticker": "X", "state": "flagged", "filings": [], "stage": "burst"}), "filings"),
                          (lambda d: d["run"]["sec_flags"].update(sentence=None), "sentence")):
        forged = copy.deepcopy(data)
        change(forged)
        assert any(words in f for f in sec_flags.faults(forged)), words
        with pytest.raises(ValueError):
            report.validate(forged)
    older = copy.deepcopy(data)
    del older["rules"]["sec_flags"]
    assert sec_flags.faults(older) == ["run.sec_flags present under rules that do not write it"]
    del older["run"]["sec_flags"]
    assert sec_flags.faults(older) == []


def test_a_flagged_row_must_carry_its_filings():
    data = page("full")
    forged = copy.deepcopy(data)
    forged["run"]["sec_flags"]["rows"] = [{"stage": "burst", "ticker": "X", "state": "flagged", "filings": []}]
    forged["run"]["sec_flags"]["status"] = "flagged"
    assert sec_flags.faults(forged) == ["run.sec_flags a row's state is not its filings'"]


# ---------------------------------------------------------- cross-check ---
def frame(rows: list[tuple]) -> pd.DataFrame:
    index = pd.DatetimeIndex([pd.Timestamp(d, tz="America/New_York") for d, *_ in rows])
    return pd.DataFrame([{"Open": o, "High": h, "Low": l, "Close": c, "Volume": v} for _, o, h, l, c, v in rows],
                        index=index)


DAY, PRIOR = date(2026, 11, 18), "2026-11-17"
SIP = frame([(PRIOR, 99.0, 100.0, 98.0, 99.5, 1_000_000), ("2026-11-18", 100.0, 106.0, 99.5, 105.0, 2_000_000)])


def iex(close=105.0, volume=60_000, prior_volume=30_000, open_=100.0):
    # IEX's own volume is a few percent of the tape's; its ratio to its own prior day is what agrees
    return frame([(PRIOR, 99.0, 100.0, 98.0, 99.5, prior_volume), ("2026-11-18", open_, 106.0, 99.5, close, volume)])


def test_agreeing_prices_and_agreeing_volume_ratios_pass_though_iex_is_one_venue():
    out = cross_check.compare(SIP, iex(), DAY)
    assert out == {"result": "pass", "reason": None,
                   "differences": {"open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0, "volume": 0.0}}
    # the literal comparison fails every one-venue reading, which is why the ratio is the rule
    assert cross_check.compare(SIP, iex(), DAY, basis="absolute")["result"] == "fail"


@pytest.mark.parametrize("kwargs, result, reason", [
    ({"close": 105.0 * 1.006}, "fail", "differ: close"),
    ({"close": 105.0 * 1.004}, "pass", None),
    ({"close": 105.0 * (1 + cross_check.PRICE_PCT / 100)}, "pass", None),
    ({"open_": 100.0 * 0.99}, "fail", "differ: open"),
    ({"volume": 60_000 * 1.15}, "fail", "differ: volume"),
    ({"volume": 60_000 * 1.09}, "pass", None),
    ({"volume": 60_000 * 1.5, "close": 90.0}, "fail", "differ: close, volume"),
])
def test_a_price_past_half_a_percent_or_a_volume_ratio_past_ten_fails(kwargs, result, reason):
    out = cross_check.compare(SIP, iex(**kwargs), DAY)
    assert (out["result"], out["reason"]) == (result, reason)


def test_a_missing_bar_or_a_missing_prior_volume_is_unknown_never_a_pass():
    assert cross_check.compare(SIP, None, DAY)["reason"] == "no_iex_bar"
    assert cross_check.compare(None, iex(), DAY)["reason"] == "no_sip_bar"
    assert cross_check.compare(SIP, iex().iloc[1:], DAY)["reason"] == "no_iex_bar"
    out = cross_check.compare(SIP, iex(prior_volume=0), DAY)
    assert (out["result"], out["reason"]) == ("unknown", "no_prior_volume")


def test_the_night_asks_the_iex_feed_once_for_at_most_max_names_tickets():
    tickets = [{"stage": "burst", "ticker": f"T{i:02d}"} for i in range(cross_check.MAX_NAMES + 2)]
    asked = []

    def fetch(client, symbols, session):
        asked.append(symbols)
        return {t: iex() for t in symbols}

    block = cross_check.collect(None, tickets, {t["ticker"]: SIP for t in tickets}, DAY, fetch=fetch)
    assert len(asked) == 1 and len(asked[0]) == cross_check.MAX_NAMES
    assert [r["result"] for r in block["rows"]] == ["pass"] * cross_check.MAX_NAMES + ["unknown"] * 2
    assert block["status"] == "unknown" and "2 of" not in block["sentence"]
    assert block["sentence"].startswith("Each ticket's signal-day bar was read again from the iex feed")


def test_a_provider_failure_is_every_ticket_unknown_and_never_the_nights():
    def fetch(client, symbols, session):
        raise ConnectionError("down")

    block = cross_check.collect(None, [{"stage": "burst", "ticker": "AAA"}], {"AAA": SIP}, DAY, fetch=fetch)
    assert block["rows"][0]["reason"] == "iex_unavailable (ConnectionError)" and block["status"] == "unknown"


def test_the_evening_asks_the_iex_feed_and_writes_the_block_the_validator_holds():
    data = page("full")
    block = data["run"]["cross_check"]
    assert block["feed"] == "iex" and block["price_pct"] == cross_check.PRICE_PCT == 0.5
    assert block["volume_pct"] == cross_check.VOLUME_PCT == 10.0 and cross_check.faults(data) == []
    assert [r["ticker"] for r in block["rows"]] == [t["ticker"] for t in earnings_risk.tickets_of(
        data["bursts"], data["trades"], data["watchlist"]["top"])]
    body = (ROOT / "src" / "pipeline.py").read_text().split("def run_evening", 1)[1].split("\ndef ", 1)[0]
    assert body.index('run_block["earnings"]') < body.index('run_block["sec_flags"]') \
        < body.index('run_block["cross_check"]') < body.index("record.append(")
    forged = copy.deepcopy(data)
    forged["run"]["cross_check"]["price_pct"] = 5.0
    assert cross_check.faults(forged) == ["run.cross_check tolerances are not the rules it archived"]


def test_the_cross_check_reads_the_iex_feed_through_the_records_own_transport(monkeypatch):
    from src import market_data
    seen = {}

    def download(client, symbols, session, lookback, feed, **kw):
        seen.update(symbols=symbols, feed=feed.value, lookback=lookback)
        return {}, None

    monkeypatch.setattr(market_data, "download_bars", download)
    cross_check.collect(object(), [{"stage": "burst", "ticker": "AAA"}], {"AAA": SIP}, DAY)
    assert seen == {"symbols": ["AAA"], "feed": "iex", "lookback": cross_check.LOOKBACK_DAYS}


# --------------------------------------------------- orders.json tickets ---
def ticket_of(data: dict, **run_blocks) -> dict:
    admitted = morning.admitted_rows(data)[0]
    forged = copy.deepcopy(data)
    forged["run"].update(run_blocks)
    return orders._ticket(forged, admitted, ["2026-09-14"] * 5)


def cross_block(data, result, reason=None):
    admitted = morning.admitted_rows(data)[0]
    stage = "burst" if admitted["kind"] == "burst" else "anticipation"
    rows = [{"stage": stage, "ticker": admitted["ticker"], "result": result, "reason": reason, "differences": None}]
    return {**data["run"]["cross_check"], "rows": rows, "status": cross_check.status_of(rows)}


def sec_block(data, state, filings=()):
    admitted = morning.admitted_rows(data)[0]
    stage = "burst" if admitted["kind"] == "burst" else "anticipation"
    rows = [{"stage": stage, "ticker": admitted["ticker"], "state": state, "reason": None, "cik": 1,
             "filings": list(filings)}]
    return {**data["run"]["sec_flags"], "rows": rows, "status": sec_flags.status_of(rows)}


def clean(data):
    """``data`` with its first ticket's earnings items not material, so the SEC check reads run.sec_flags alone."""
    out = copy.deepcopy(data)
    out["run"]["earnings"]["rows"] = []
    return out


@pytest.mark.parametrize("state, status, reasons", [
    ("clear", "go", []),
    ("flagged", "human_review", ["sec_flag"]),
    ("unknown", "human_review", ["sec_unknown"]),
])
def test_an_sec_flag_or_an_unread_name_holds_the_ticket_for_review(state, status, reasons):
    data = clean(page("next"))
    filing = [{"accession": "a", "filing_date": "2026-09-10", "form": "SC TO-T", "items": []}]
    t = ticket_of(data, sec_flags=sec_block(data, state, filing if state == "flagged" else ()),
                  cross_check=cross_block(data, "pass"))
    assert (t["status"], t["reasons"]) == (status, reasons)
    if state == "flagged":
        assert next(c for c in t["checks"] if c["key"] == "sec_flags")["detail"] == "SC TO-T 2026-09-10"


@pytest.mark.parametrize("result, status, reasons", [
    ("pass", "go", []),
    ("fail", "blocked", ["cross_check_failed"]),
    ("unknown", "human_review", ["cross_check_unknown"]),
])
def test_a_cross_check_that_fails_blocks_the_ticket_and_one_that_could_not_be_made_holds_it(result, status, reasons):
    data = clean(page("next"))
    t = ticket_of(data, sec_flags=sec_block(data, "clear"), cross_check=cross_block(data, result, "differ: close"))
    assert (t["status"], t["reasons"]) == (status, reasons)


def test_a_record_with_no_cross_check_holds_every_ticket_and_the_night():
    data = clean(page("next"))
    forged = copy.deepcopy(data)
    del forged["run"]["cross_check"]
    t = ticket_of(forged, sec_flags=sec_block(data, "clear"))
    assert (t["status"], t["reasons"]) == ("human_review", ["cross_check_not_run"])
    night = {c["key"]: c for c in orders._night(forged, [])}["cross_check"]
    assert (night["status"], night["reason"]) == ("not_evaluated", "cross_check_not_run")
    ran = {c["key"]: c for c in orders._night(data, [])}["cross_check"]
    assert ran["status"] == "pass" and ran["detail"] == data["run"]["cross_check"]["sentence"]


def test_a_record_from_before_the_sec_flags_reads_the_earnings_items_alone():
    data = clean(page("next"))
    del data["rules"]["sec_flags"]
    data["run"].pop("sec_flags")
    assert ticket_of(data, cross_check=cross_block(data, "pass"))["status"] == "go"


# ---------------------------------------------------- the event registry ---
def registry_with(**event_changes) -> dict:
    reg = copy.deepcopy(event_risk.REGISTRY)
    acva = next(e for e in reg["events"] if e["symbol"] == "ACVA")
    acva.update(event_changes)
    return reg


def test_the_acva_entry_stays_blocked_and_carries_its_review_note():
    acva = next(e for e in event_risk.REGISTRY["events"] if e["symbol"] == "ACVA")
    note = acva["review_note"]
    assert acva["review_due"] < note["noted_on"] <= event_risk.REGISTRY["reviewed_on"]
    assert "page bytes not captured" in note["text"] and acva["active_until"] is None
    match = event_risk.classify("ACVA", "2026-11-18")
    assert match["blocked"] is True and match["status"] == "review_required"
    assert "review_note" not in match["matches"][0]


@pytest.mark.parametrize("note, words", [
    ({"noted_on": "2026-10-15", "text": "x"}, "dated after"),          # on the due date, not after it
    ({"noted_on": "2026-11-20", "text": "x"}, "dated after"),          # after the registry's own review
    ({"noted_on": "2026-11-19"}, "object of noted_on and text"),
    ({"noted_on": "2026-11-19", "text": "x", "by": "me"}, "object of noted_on and text"),
    ({"noted_on": "2026-11-19", "text": " "}, "review_note"),
    ("a note", "object of noted_on and text"),
])
def test_a_review_note_is_dated_after_the_review_it_answers_and_is_text(note, words):
    with pytest.raises(ValueError, match=words):
        event_risk.validate_registry(registry_with(review_note=note))


def test_a_lapsed_review_is_one_past_its_due_date_with_no_note():
    reg = registry_with()
    assert event_risk.lapsed_reviews(reg, "2026-11-25") == []          # MG on its due date
    assert event_risk.lapsed_reviews(reg, "2026-11-26") == ["MG"]
    bare = copy.deepcopy(reg)
    next(e for e in bare["events"] if e["symbol"] == "ACVA").pop("review_note")
    assert event_risk.lapsed_reviews(bare, "2026-11-19") == ["ACVA"]
    assert event_risk.lapsed_reviews(bare, "2026-10-15") == []


def test_the_review_check_reads_new_yorks_date_and_names_each_lapsed_entry(tmp_path, capsys):
    from tools import check_event_reviews as tool
    assert tool.main([], now=datetime(2026, 11, 26, 4, 0, tzinfo=timezone.utc)) == 0       # still the 25th in New York
    assert tool.main([], now=datetime(2026, 11, 26, 5, 30, tzinfo=timezone.utc)) == 1
    assert "MG (review due 2026-11-25)" in capsys.readouterr().err
    assert tool.main(["--today", "2026-11-19"]) == 0
    assert "ACVA overdue, each with its note" in capsys.readouterr().out
    bad = tmp_path / "registry.json"
    bad.write_text("{}")
    assert tool.main(["--registry", str(bad), "--today", "2026-11-19"]) == 2


def test_ci_runs_the_review_check_on_the_real_date():
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text()
    assert "run: python tools/check_event_reviews.py\n" in workflow


def test_the_readme_quotes_the_flags_and_the_cross_checks_numbers_from_the_modules():
    readme = " ".join((ROOT / "README.md").read_text().split())
    forms = ", ".join(f for f in sec_flags.FORMS if not f.endswith("/A"))
    assert f"({forms} and their amendments)" in readme
    items = sec_flags.ITEMS
    assert f"every 8-K carrying item {', '.join(items[:-1])} or {items[-1]}" in readme
    assert f"filed in the {sec_flags.WINDOW_DAYS} days before the signal session" in readme
    assert f"at most {cross_check.MAX_NAMES} tickets" in readme
    assert f"more than {cross_check.PRICE_PCT:g}% from the sip bar" in readme
    assert f"a volume reading more than {cross_check.VOLUME_PCT:g}% off" in readme
    assert f"prices within {cross_check.PRICE_PCT:g}% and the two feeds' volume ratios within {cross_check.VOLUME_PCT:g}%" in readme
    assert cross_check.VOLUME_BASIS == "ratio_to_prior_session" and "(`cross_check.VOLUME_BASIS`)" in readme


def test_the_env_example_names_the_cross_checks_bound_and_needs_no_new_variable():
    env = " ".join((ROOT / ".env.example").read_text().split())
    assert f"at most {cross_check.MAX_NAMES} tickets (run.cross_check)" in env
    assert "never fails the run. No new variable." in env


def test_a_rules_block_that_is_not_an_object_is_named_and_never_raises():
    data = page("full")
    data["rules"]["cross_check"] = "x"
    assert cross_check.faults(data) == ["rules.cross_check is not an object"]
