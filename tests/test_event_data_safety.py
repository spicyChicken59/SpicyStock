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
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

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
def synthetic_registry() -> tuple[dict, dict, date]:
    """The committed registry with its dates moved so these tests read none of the real ones: one
    unresolved entry (``target``) falls due on its own review date, every other one a month after
    the registry's review, so a real review of any entry never turns a test here red."""
    reg = copy.deepcopy(event_risk.REGISTRY)
    later = date.fromisoformat(reg["reviewed_on"]) + timedelta(days=30)
    reg["reviewed_on"] = later.isoformat()
    unresolved = [e for e in reg["events"] if e.get("active_until") is None]
    for e in unresolved:
        e.pop("review_note", None)
        e["review_due"] = later.isoformat()
    target = unresolved[0]
    target["review_due"] = target["reviewed_on"]
    return event_risk.validate_registry(reg), target, date.fromisoformat(target["review_due"])


def test_the_acva_entry_is_resolved_by_a_captured_source_and_classifies_with_no_note():
    acva = next(e for e in event_risk.REGISTRY["events"] if e["symbol"] == "ACVA")
    assert acva["active_until"] == "2026-10-16" and "review_note" not in acva
    assert re.fullmatch(r"[0-9a-f]{64}", acva["resolution"]["sha256"])
    match = event_risk.classify("ACVA", "2026-11-18")
    assert match["blocked"] is False and match["status"] == "not_in_registry"
    inside = event_risk.classify("ACVA", "2026-10-15")
    assert inside["blocked"] is True and all("review_note" not in m for m in inside["matches"])


def test_the_committed_registry_is_valid_and_lapses_nothing_on_its_own_review_date():
    assert event_risk.lapsed_reviews(event_risk.REGISTRY, event_risk.REGISTRY["reviewed_on"]) == []


@pytest.mark.parametrize("offset, words", [
    (0, "dated after"),                     # on the due date, not after it
    (None, "dated after"),                  # after the registry's own review
])
def test_a_review_note_is_dated_after_the_review_it_answers_and_before_the_registrys(offset, words):
    reg, target, due = synthetic_registry()
    noted = (due + timedelta(days=offset)) if offset is not None else \
        date.fromisoformat(reg["reviewed_on"]) + timedelta(days=1)
    target["review_note"] = {"noted_on": noted.isoformat(), "text": "x"}
    with pytest.raises(ValueError, match=words):
        event_risk.validate_registry(reg)


@pytest.mark.parametrize("note, words", [
    ({"noted_on": None}, "object of noted_on and text"),
    ({"noted_on": None, "text": "x", "by": "me"}, "object of noted_on and text"),
    ({"noted_on": None, "text": " "}, "review_note"),
    ("a note", "object of noted_on and text"),
])
def test_a_review_note_is_an_object_of_its_date_and_its_text(note, words):
    reg, target, due = synthetic_registry()
    if isinstance(note, dict):
        note = {**note, "noted_on": (due + timedelta(days=1)).isoformat()}
    target["review_note"] = note
    with pytest.raises(ValueError, match=words):
        event_risk.validate_registry(reg)


def test_a_lapsed_review_is_one_past_its_due_date_with_no_note_in_force():
    reg, target, due = synthetic_registry()
    day = lambda n: (due + timedelta(days=n)).isoformat()            # noqa: E731
    assert event_risk.lapsed_reviews(reg, day(0)) == []                   # on its due date
    assert event_risk.lapsed_reviews(reg, day(1)) == [target["symbol"]]
    noted = copy.deepcopy(reg)
    next(e for e in noted["events"] if e["symbol"] == target["symbol"])["review_note"] = \
        {"noted_on": day(1), "text": "stands as it is, and why"}
    noted = event_risk.validate_registry(noted)
    span = event_risk.REVIEW_NOTE_DAYS
    assert event_risk.lapsed_reviews(noted, day(1)) == []
    assert event_risk.lapsed_reviews(noted, day(1 + span)) == []          # the note's last day
    assert event_risk.lapsed_reviews(noted, day(2 + span)) == [target["symbol"]]   # due again


def test_the_review_check_reads_new_yorks_date_and_names_each_lapsed_entry(tmp_path, capsys):
    from tools import check_event_reviews as tool
    reg, target, due = synthetic_registry()
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(reg))
    midnight = datetime.combine(due + timedelta(days=1), datetime.min.time(), tzinfo=ZoneInfo("America/New_York"))
    before, after = midnight - timedelta(minutes=30), midnight + timedelta(minutes=30)
    assert tool.main(["--registry", str(path)], now=before.astimezone(timezone.utc)) == 0    # still the due date
    assert tool.main(["--registry", str(path)], now=after.astimezone(timezone.utc)) == 1
    assert f"{target['symbol']} (review due {target['review_due']})" in capsys.readouterr().err
    assert tool.main(["--registry", str(path), "--today", due.isoformat()]) == 0
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    assert tool.main(["--registry", str(bad), "--today", due.isoformat()]) == 2


def test_ci_runs_the_review_check_on_the_real_date():
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text()
    assert "run: python tools/check_event_reviews.py\n" in workflow


def test_the_readme_quotes_the_flags_and_the_cross_checks_numbers_from_the_modules():
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert f"({', '.join(sec_flags.FORMS)})" in readme
    items = sec_flags.ITEMS
    assert f"every 8-K carrying item {', '.join(items[:-1])} or {items[-1]}" in readme
    assert f"filed in the {sec_flags.WINDOW_DAYS} days before the signal session" in readme
    assert f"at most {cross_check.MAX_NAMES} tickets" in readme
    assert f"more than {cross_check.PRICE_PCT:g}% from the sip bar" in readme
    assert f"a volume reading more than {cross_check.VOLUME_PCT:g}% off" in readme
    assert f"prices within {cross_check.PRICE_PCT:g}% and the two feeds' volume ratios within {cross_check.VOLUME_PCT:g}%" in readme
    assert cross_check.VOLUME_BASIS == "ratio_to_prior_session"
    assert "(`cross_check.VOLUME_BASIS`, a departure from the program's literal volume rule" in readme


def test_the_env_example_names_the_cross_checks_bound_and_needs_no_new_variable():
    env = " ".join((ROOT / ".env.example").read_text().split())
    assert f"at most {cross_check.MAX_NAMES} tickets (run.cross_check)" in env
    assert "never fails the run. No new variable." in env


def test_a_rules_block_that_is_not_an_object_is_named_and_never_raises():
    data = page("full")
    data["rules"]["cross_check"] = "x"
    assert cross_check.faults(data) == ["rules.cross_check is not an object"]


# ------------------------------------------- the review's holes, closed ---
NAN = float("nan")


@pytest.mark.parametrize("sip, x, reason", [
    (SIP, frame([(PRIOR, 99.0, 100.0, 98.0, 99.5, 30_000), ("2026-11-18", NAN, NAN, NAN, NAN, NAN)]),
     "bar_not_finite"),
    (SIP, iex(close=NAN), "bar_not_finite"),
    (SIP, iex(volume=NAN), "bar_not_finite"),
    (SIP, iex(prior_volume=NAN), "no_prior_volume"),
    (frame([(PRIOR, 99.0, 100.0, 98.0, 99.5, NAN), ("2026-11-18", 100.0, 106.0, 99.5, 105.0, 2_000_000)]),
     iex(), "no_prior_volume"),
    (SIP, iex(close=float("inf")), "bar_not_finite"),
])
def test_a_value_that_is_not_a_finite_number_is_unknown_never_a_pass(sip, x, reason):
    out = cross_check.compare(sip, x, DAY)
    assert (out["result"], out["reason"], out["differences"]) == ("unknown", reason, None)


def test_a_prior_row_that_is_not_the_session_before_in_both_feeds_is_unknown():
    gapped = frame([("2026-11-10", 99.0, 100.0, 98.0, 99.5, 30_000), ("2026-11-18", 100.0, 106.0, 99.5, 105.0, 60_000)])
    out = cross_check.compare(SIP, gapped, DAY)
    assert (out["result"], out["reason"]) == ("unknown", "no_prior_session")
    sip_gapped = frame([("2026-11-10", 99.0, 100.0, 98.0, 99.5, 1_000_000),
                        ("2026-11-18", 100.0, 106.0, 99.5, 105.0, 2_000_000)])
    assert cross_check.compare(sip_gapped, gapped, DAY)["reason"] == "no_prior_session"
    # the same frames compared on the absolute basis never ask the prior row
    assert cross_check.compare(SIP, gapped, DAY, basis="absolute")["reason"] != "no_prior_session"


@pytest.mark.parametrize("kwargs, field", [
    ({"close": 105.0 * 1.005004}, "close"),
    ({"volume": 60_000 * 1.10004}, "volume"),
])
def test_a_difference_just_past_its_tolerance_fails_unrounded(kwargs, field):
    out = cross_check.compare(SIP, iex(**kwargs), DAY)
    assert (out["result"], out["reason"]) == ("fail", f"differ: {field}")
    tolerance = cross_check.PRICE_PCT if field == "close" else cross_check.VOLUME_PCT
    assert tolerance < out["differences"][field] < tolerance + 0.01


def _crossed() -> dict:
    data = page("full")
    data.pop("fixture", None)
    rows = data["run"]["cross_check"]["rows"]
    assert rows and data["run"]["cross_check"]["volume_basis"] == cross_check.VOLUME_BASIS
    return data


def test_the_validator_rederives_each_rows_result_from_its_differences():
    data = _crossed()
    assert cross_check.faults(data) == []
    report.validate(data)
    row = data["run"]["cross_check"]["rows"][0]
    for diffs, result, words in (
            ({"open": 9.0, "high": 9.0, "low": 9.0, "close": 9.0, "volume": 80.0}, "pass", "is not what its differences give"),
            ({"open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0, "volume": 0.0}, "fail", "is not what its differences give"),
            (None, "pass", "carries no finite differences"),
            ({"open": None, "high": 0.0, "low": 0.0, "close": 0.0, "volume": 0.0}, "pass", "carries no finite differences")):
        forged = copy.deepcopy(data)
        target = forged["run"]["cross_check"]["rows"][0]
        target.update(result=result, differences=diffs, reason=None if result == "pass" else "differ: x")
        forged["run"]["cross_check"]["status"] = cross_check.status_of(forged["run"]["cross_check"]["rows"])
        assert any(words in f for f in cross_check.faults(forged)), words
        with pytest.raises(ValueError, match="cross_check"):
            report.validate(forged)
    assert row["ticker"]
    loosened = copy.deepcopy(data)
    loosened["run"]["cross_check"]["price_pct"] = 9.0
    assert "run.cross_check tolerances are not the rules it archived" in cross_check.faults(loosened)


def test_an_amended_merger_proxy_is_flagged_as_the_issuer_reader_reads_it():
    # the forms the issuer reader counts as an acquisition's, and no other
    assert set(sec_flags.FORMS) == issuer_evidence.ACQUISITION_FORMS
    sec = sec_with({"AMDP": [(days_before(8), "DEFM14A/A", "")], "AMPR": [(days_before(9), "PREM14A/A", "")]})
    block = sec_flags.collect(names("AMDP", "AMPR"), SESSION, fetch=sec, now=NOW)
    assert [(r["ticker"], r["state"], r["filings"][0]["form"]) for r in block["rows"]] == [
        ("AMDP", "flagged", "DEFM14A/A"), ("AMPR", "flagged", "PREM14A/A")]


def test_the_window_holds_its_first_day_and_not_the_day_before():
    sec = sec_with({"EDGE": [(days_before(sec_flags.WINDOW_DAYS), "SC TO-T", "")],
                    "PAST": [(days_before(sec_flags.WINDOW_DAYS + 1), "SC TO-T", "")]})
    state = {r["ticker"]: r["state"] for r in sec_flags.collect(names("EDGE", "PAST"), SESSION, fetch=sec, now=NOW)["rows"]}
    assert state == {"EDGE": "flagged", "PAST": "clear"}


def test_a_spent_deadline_asks_nothing_and_leaves_every_name_unknown():
    sec = sec_with({"AAA": [(days_before(2), "SC TO-T", "")], "BBB": []})
    block = sec_flags.collect(names("AAA", "BBB"), SESSION, fetch=sec, now=NOW, deadline_seconds=0)
    assert [(r["state"], r["reason"]) for r in block["rows"]] == [("unknown", "time_budget")] * 2
    assert block["requests"] == 0 and sec.calls == [] and block["status"] == "unknown"


def _flagged() -> dict:
    data = page("full")
    data.pop("fixture", None)
    assert sec_flags.faults(data) == []
    return data


@pytest.mark.parametrize("change, words", [
    (lambda b: b.update(forms=b["forms"][:-1]), "not the rules it archived"),
    (lambda b: b.update(window_days=b["window_days"] + 1), "not the rules it archived"),
    (lambda b: b.update(items=["9.01"]), "not the rules it archived"),
    (lambda b: b["rows"][0].update(state="clear", cik=None, filings=[]), "names no CIK"),
    (lambda b: b["rows"][0].update(state="flagged", cik=b["rows"][0].get("cik") or 1,
                                   filings=[{"accession": "a", "filing_date": "2000-01-03", "form": "SC TO-T",
                                             "items": []}]), "outside the window"),
    (lambda b: b["rows"][0].update(state="flagged", cik=b["rows"][0].get("cik") or 1,
                                   filings=[{"accession": "a", "filing_date": b["session"], "form": "10-Q",
                                             "items": []}]), "of no listed form or item"),
])
def test_the_flags_validator_holds_each_row_to_the_window_and_the_archived_forms(change, words):
    data = _flagged()
    block = data["run"]["sec_flags"]
    if not block["rows"]:
        block["rows"].append({"stage": "burst", "ticker": "X", "state": "clear", "reason": None, "cik": 1,
                              "filings": []})
    change(block)
    block["status"] = sec_flags.status_of(block["rows"])
    assert any(words in f for f in sec_flags.faults(data)), (words, sec_flags.faults(data))
    with pytest.raises(ValueError, match="sec_flags"):
        report.validate(data)


def test_a_lapsed_note_is_named_with_its_date_by_the_review_check(tmp_path, capsys):
    from tools import check_event_reviews as tool
    reg, target, due = synthetic_registry()
    noted = (due + timedelta(days=1)).isoformat()
    target["review_note"] = {"noted_on": noted, "text": "stands as it is, and why"}
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(reg))
    last = (due + timedelta(days=1 + event_risk.REVIEW_NOTE_DAYS)).isoformat()
    after = (due + timedelta(days=2 + event_risk.REVIEW_NOTE_DAYS)).isoformat()
    assert tool.main(["--registry", str(path), "--today", last]) == 0
    assert "with a note in force" in capsys.readouterr().out
    assert tool.main(["--registry", str(path), "--today", after]) == 1
    assert f"its note of {noted} answered for {event_risk.REVIEW_NOTE_DAYS} days" in capsys.readouterr().err
