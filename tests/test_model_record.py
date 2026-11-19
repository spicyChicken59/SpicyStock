"""The model's own record: setups, accounts, stop bounds (``src/model_record.py``).

Every night here is pinned: the sessions are named dates on the exchange
calendar, the bars and the picks are written out, and each expected R is
worked by hand beside its case. The frozen 17 November 2026 record
(``tests/fixtures/model-record``) is the one real shape: the 22 retained
picks, the bars their scorecard walked and the five minute objects.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from src import breadth, intraday, model_record, pipeline, plan, quality_ledger, record
from src import sessions as exchange_sessions
from tools import make_fixture

ROOT = Path(__file__).resolve().parent.parent
FROZEN = ROOT / "tests" / "fixtures" / "model-record" / "record-2026-11-17.json.gz"

#: thirty consecutive sessions from Monday 2 March 2026
S = [str(d) for d in exchange_sessions.next_sessions(date(2026, 2, 27), 30)]
OWN_CONTEXT = "c" * 64
ACCOUNT = {"equity": 30000.0, "risk_pct": 0.5}


# ---------------------------------------------------------------- helpers ----

def frame(*rows):
    """A daily frame from ``(date, open, high, low, close)`` rows."""
    return pd.DataFrame({"Open": [r[1] for r in rows], "High": [r[2] for r in rows],
                         "Low": [r[3] for r in rows], "Close": [r[4] for r in rows]},
                        index=pd.to_datetime([r[0] for r in rows]))


def burst(ticker, day, *, shares=10, evidence=None, context=None):
    """A burst ticket: buy stop 100, limit 102, skip line 98, stop 97."""
    pick = {"ticker": ticker, "date": day, "kind": "burst", "regime": "green", "entry_ref": 100.0,
            "entry_low": 98.0, "entry_high": 102.0, "limit": 102.0, "stop": 97.0, "shares": shares}
    return _with_evidence(pick, evidence, context)


def coil(ticker, day, *, shares=10, stop=97.0, evidence=None, context=None):
    """An anticipation ticket: buy stop 100, limit 101."""
    pick = {"ticker": ticker, "date": day, "kind": "anticipation", "regime": "green", "entry_ref": 100.0,
            "trigger": 100.0, "limit": 101.0, "stop": stop, "shares": shares}
    return _with_evidence(pick, evidence, context)


def _with_evidence(pick, evidence, context):
    if evidence is not None:
        pick["evidence_ref"] = {"id": evidence, **({"context_sha256": context} if context else {})}
    return pick


def quiet(day):
    """A session that never reaches a 100 trigger: the day order expires."""
    return (day, 99.0, 99.5, 98.5, 99.2)


def published(picks, frames, session, minutes=None, account=ACCOUNT):
    """The record a run would publish over these picks: its session, its
    context, its account and the scorecard ``record.scorecard()`` writes."""
    rec = {"schema_version": 2, "picks": sorted(picks, key=lambda p: (p["date"], p["ticker"]))}
    data = {"run": {"session": session, "evidence": {"version": 1, "context_sha256": OWN_CONTEXT}},
            "account": dict(account), "scorecard": record.scorecard(rec, frames, session, minutes=minutes)}
    return rec, data


def block_of(picks, frames, session, minutes=None, docs=None, account=ACCOUNT):
    rec, data = published(picks, frames, session, minutes, account)
    return model_record.build(rec, frames, minutes, data, docs)


def row_of(block, ticker, day=None, kind=None):
    rows = [p for p in block["plans"] if p["ticker"] == ticker and (day is None or p["picked"] == day)
            and (kind is None or p["kind"] == kind)]
    assert len(rows) == 1, rows
    return rows[0]


def minute_object(pick, rows):
    """A retained minute object for the pick's entry session from
    ``(offset, o, h, l, c)`` rows, built as the run builds one."""
    opens, _, _ = exchange_sessions.hours(intraday.entry_session(pick))
    return intraday.build(pick, [(opens + timedelta(minutes=m), o, h, low, c) for m, o, h, low, c in rows])


def write_ledger(docs, entries):
    """Ledger entries on disk as ``quality_ledger.append()`` writes them:
    canonical JSON in a deterministic gzip, named by the publication's hash."""
    folder = Path(docs) / quality_ledger.DIRECTORY
    folder.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        buffer = io.BytesIO()
        with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as handle:
            handle.write(quality_ledger.encoded(entry))
        (folder / (entry["publication"]["sha256"] + ".json.gz")).write_bytes(buffer.getvalue())


def ledger_entry(name, session, at, *, coils=(), bursts=(), **extra):
    """One entry: ``coils`` and ``bursts`` are ``(ticker, evidence id, ticket, reason)``."""
    def rows(items):
        return [{"ticker": t, "evidence_id": e, "gate": {"ticket": ok, "reason": why}} for t, e, ok, why in items]
    return {"schema_version": 1, "publication": {"session": session, "published_at": at, "sha256": name},
            "signal": {"candidates": rows(bursts), "anticipation": rows(coils)}, **extra}


def frozen():
    return json.loads(gzip.decompress(FROZEN.read_bytes()))


def frozen_frames(fixture, without=()):
    return {t: frame(*[(r["date"], r["o"], r["h"], r["l"], r["c"]) for r in e["rows"]])
            for t, e in fixture["bars"].items() if t not in without}


def frozen_block(tmp_path, with_ledger=True):
    fixture = frozen()
    if with_ledger:
        write_ledger(tmp_path, fixture["ledger_entries"])
    return model_record.build({"picks": fixture["picks"]}, frozen_frames(fixture), fixture["minutes"],
                              fixture["data"], tmp_path if with_ledger else None)


# ----------------------------------------------------------- the setups ------

def test_a_ticket_issued_again_inside_the_window_is_one_setup_and_past_it_another():
    """AAA is offered on S0, again the next night, again five sessions after
    that (the last session the second ticket's window reaches) and once more
    six sessions later, past the third ticket's window. Nothing ever fills.
    Three tickets are one setup; the fourth starts another."""
    picks = [coil("AAA", S[0], shares=10), coil("AAA", S[1], shares=12, stop=97.5), coil("AAA", S[6], shares=12,
                                                                                        stop=97.5),
             coil("AAA", S[12])]
    frames = {"AAA": frame(*[quiet(d) for d in S[1:19]])}
    block = block_of(picks, frames, S[18])
    assert block["status"] == model_record.COMPUTED, block["reason"]
    assert (block["tickets"], block["distinct_setups"], block["reissued_tickets"]) == (4, 2, 2)
    assert [(p["picked"], p["setup"], p["issue_no"], p["issues"]) for p in block["plans"]] == [
        (S[0], f"anticipation:AAA:{S[0]}", 1, 3), (S[1], f"anticipation:AAA:{S[0]}", 2, 3),
        (S[6], f"anticipation:AAA:{S[0]}", 3, 3), (S[12], f"anticipation:AAA:{S[12]}", 1, 1)]
    # what changed against the issue before: the second night moved the stop and the size, the third nothing
    assert [p["changed"] for p in block["plans"]] == [[], ["stop", "shares"], [], []]
    assert block["setups"][0] == {"setup": f"anticipation:AAA:{S[0]}", "ticker": "AAA", "kind": "anticipation",
                                  "first": S[0], "last": S[6], "issues": 3, "tickets": [S[0], S[1], S[6]],
                                  "bucket": "not_filled", "r": None, "changed": [["stop", "shares"], []]}
    assert block["buckets"]["not_filled"] == 4 and block["buckets_by_setup"]["not_filled"] == 2
    assert sum(block["buckets"].values()) == 4 and sum(block["buckets_by_setup"].values()) == 2


def test_a_chain_is_per_ticker_and_per_kind():
    """Two tickers offered on the same two nights are two setups, and a
    burst ticket of AAA the night after its unfilled anticipation tickets is
    not a re-issue of them: only its kind keeps it out of their chain."""
    picks = [coil("AAA", S[0]), coil("AAA", S[1]), coil("BBB", S[0]), coil("BBB", S[1]), burst("AAA", S[2])]
    frames = {t: frame(*[quiet(d) for d in S[1:9]]) for t in ("AAA", "BBB")}
    block = block_of(picks, frames, S[8])
    assert block["status"] == model_record.COMPUTED, block["reason"]
    assert {p["bucket"] for p in block["plans"]} == {"not_filled"}
    assert (block["tickets"], block["distinct_setups"], block["reissued_tickets"]) == (5, 3, 2)
    assert sorted(s["setup"] for s in block["setups"]) == [
        f"anticipation:AAA:{S[0]}", f"anticipation:BBB:{S[0]}", f"burst:AAA:{S[2]}"]


def test_a_fill_ends_the_chain_and_so_does_a_fill_the_bars_cannot_place():
    """BBB's first ticket fills at its first open, so the ticket offered the
    next night is another setup. UUU's first ticket opened over its limit and
    traded back (uncertain: it may have filled), so its next ticket is
    another setup too. NNN's first ticket never triggered and its second
    filled: one setup, and the setup's bucket is its last ticket's."""
    filled = (S[1], 100.5, 103.0, 100.2, 102.0)             # opens inside the zone: filled at the open
    over = (S[1], 101.5, 102.0, 99.0, 100.0)                # opens over the 101 limit and trades back under it
    picks = [burst("BBB", S[0]), burst("BBB", S[1]), coil("UUU", S[0]), coil("UUU", S[1]),
             coil("NNN", S[0], shares=1), coil("NNN", S[1], shares=1)]
    frames = {
        # the second BBB ticket's own first day opens over its 102 limit and never trades back: not filled
        "BBB": frame(filled, (S[2], 102.5, 103.5, 102.2, 103.0), *[(d, 102.0, 103.0, 101.0, 102.5) for d in S[3:7]]),
        "UUU": frame(over, *[quiet(d) for d in S[2:7]]),
        # day 1 of the first ticket is quiet; the second fills at S2's open and sells its one share at +8%
        "NNN": frame(quiet(S[1]), (S[2], 100.4, 109.0, 100.1, 108.6), *[quiet(d) for d in S[3:8]]),
    }
    block = block_of(picks, frames, S[7])
    assert block["status"] == model_record.COMPUTED, block["reason"]
    assert [(p["ticker"], p["picked"], p["bucket"], p["issue_no"], p["issues"]) for p in block["plans"]] == [
        ("BBB", S[0], "settled", 1, 1), ("NNN", S[0], "not_filled", 1, 2), ("UUU", S[0], "uncertain", 1, 1),
        ("BBB", S[1], "not_filled", 1, 1), ("NNN", S[1], "settled", 2, 2), ("UUU", S[1], "not_filled", 1, 1)]
    assert (block["tickets"], block["distinct_setups"], block["reissued_tickets"]) == (6, 5, 1)
    nnn = next(s for s in block["setups"] if s["ticker"] == "NNN")
    assert (nnn["bucket"], nnn["r"]) == ("settled", row_of(block, "NNN", S[1])["r"])
    assert block["buckets"] == {"settled": 2, "open": 0, "pending": 0, "uncertain": 1, "not_filled": 3,
                                "unmeasured": 0, "unreadable": 0, "unscored": 0}
    assert block["buckets_by_setup"] == {"settled": 2, "open": 0, "pending": 0, "uncertain": 1, "not_filled": 2,
                                         "unmeasured": 0, "unreadable": 0, "unscored": 0}


def test_the_bucket_names_are_the_scorecards():
    assert set(model_record.BUCKET_WORDS) == set(record.SCORECARD_BUCKETS)
    assert set(model_record.REISSUE_AFTER) <= set(record.SCORECARD_BUCKETS)
    for name in (model_record.SETTLED, model_record.OPEN, model_record.PENDING, model_record.UNMEASURED,
                 model_record.UNSCORED):
        assert name in record.SCORECARD_BUCKETS


# ------------------------------------------------------------ the stops ------

HALF_THEN_STOP = [(S[1], 100.5, 103.0, 100.2, 102.0),       # filled at the open, 100.50
                  (S[2], 102.0, 110.0, 101.5, 109.0),       # +8% is 108.54: 5 of 10 sold, stop to 109.75
                  (S[3], 109.9, 110.2, 104.0, 105.0)]       # low under the raised stop: 5 stopped at 109.75


def test_half_sold_then_stopped_moves_only_the_stopped_shares():
    """Ten shares filled at 100.50 with the stop at 97: one R is 3.50 a
    share. Five are sold at 108.54 (+8.04 each, 40.20). The other five are
    stopped at 109.75 (+9.25 each, 46.25): booked (40.20 + 46.25) / 35 =
    2.47R. With those five at that day's close, 105 (+4.50 each, 22.50):
    62.70 / 35 = 1.79R. At its low, 104 (+3.50 each, 17.50): 57.70 / 35 =
    1.65R. The five sold at +8% keep their price in every reading."""
    block = block_of([burst("CCC", S[0])], {"CCC": frame(*HALF_THEN_STOP)}, S[10])
    assert block["status"] == model_record.COMPUTED, block["reason"]
    row = row_of(block, "CCC")
    assert (row["bucket"], row["r"], row["entry"], row["exit_price"], row["model_usd"]) == (
        "settled", 2.47, 100.5, 109.75, 86.45)
    assert [(e["event"], e["price"], e["shares"]) for e in row["sales"]] == [
        ("sell_half", 108.54, 5), ("stopped", 109.75, 5)]
    (bounds,) = block["stops"]["rows"]
    assert (bounds["date"], bounds["day"], bounds["event"], bounds["stopped_shares"]) == (S[3], 3, "stopped", 5)
    assert (bounds["stop_price"], bounds["close"], bounds["low"]) == (109.75, 105.0, 104.0)
    assert bounds["r"] == {"booked": 2.47, "at_close": 1.79, "at_low": 1.65}
    assert bounds["usd"] == {"booked": 86.45, "at_close": 62.7, "at_low": 57.7}
    assert bounds["minute"] is None
    assert block["stops"]["sum_r"] == block["stops"]["settled_sum_r"] == {
        "booked": 2.47, "at_close": 1.79, "at_low": 1.65}


def test_a_gap_open_through_the_stop_is_booked_at_the_open_and_bounded():
    """Filled at 100.50; the entry day's low, 100, becomes the stop at its
    close. The next session opens at 94, under it: booked at the open,
    (94 - 100.5) / 3.5 = -1.86R, not at the stop. That day's close, 91, is
    -2.71R and its low, 90, is -3.00R."""
    bars = [(S[1], 100.5, 103.0, 100.0, 102.0), (S[2], 94.0, 95.0, 90.0, 91.0)]
    block = block_of([burst("DDD", S[0])], {"DDD": frame(*bars)}, S[10])
    (bounds,) = block["stops"]["rows"]
    assert (bounds["event"], bounds["stop_price"], bounds["day"]) == ("stopped_at_open", 94.0, 2)
    assert bounds["r"] == {"booked": -1.86, "at_close": -2.71, "at_low": -3.0}
    assert bounds["usd"] == {"booked": -65.0, "at_close": -95.0, "at_low": -105.0}
    assert bounds["minute"] is None and row_of(block, "DDD")["r"] == -1.86


def test_the_stop_readings_are_summed_over_the_stopped_and_replace_them_in_the_settled_sum():
    """Two stopped tickets and one that left at day 5: the stop sums are the
    two, and the settled sum under each reading keeps the third as it is."""
    gap = [(S[1], 100.5, 103.0, 100.0, 102.0), (S[2], 94.0, 95.0, 90.0, 91.0)]
    held = [(S[1], 100.5, 101.0, 100.4, 100.8), (S[2], 100.8, 101.5, 100.6, 101.2),
            (S[3], 101.2, 102.0, 101.0, 101.8), (S[4], 101.8, 102.5, 101.5, 102.2),
            (S[5], 102.2, 103.0, 102.0, 102.6)]
    block = block_of([burst("CCC", S[0]), burst("DDD", S[0]), burst("HHH", S[0])],
                     {"CCC": frame(*HALF_THEN_STOP), "DDD": frame(*gap), "HHH": frame(*held)}, S[10])
    held_r = row_of(block, "HHH")["r"]
    # day 3 sells half at the close (101.80), day 5 the rest (102.60): (5 x 1.30 + 5 x 2.10) / 35 = 0.49
    assert held_r == 0.49 and block["stops"]["count"] == 2
    assert block["stops"]["sum_r"] == {"booked": 0.61, "at_close": -0.92, "at_low": -1.35}
    assert block["stops"]["sum_usd"] == {"booked": 21.45, "at_close": -32.3, "at_low": -47.3}
    assert block["stops"]["settled_sum_r"] == {"booked": 1.1, "at_close": -0.43, "at_low": -0.86}
    assert block["sum_r"] == 1.1


def test_minute_bars_name_the_first_minute_at_the_stop_from_the_fill_on():
    """The day opens at 99 under the 100 trigger and its first minute trades
    down to 96.90, under the 97 stop, before any fill. The minute at 09:33
    crosses the trigger: filled at 100. The minute at 10:10 is the first
    from the fill on at or under the stop (low 96): a stop filled at that
    low is (96 - 100) / 3 = -1.33R, against -1.00R booked, -1.17R at the
    close (96.50) and -2.67R at the day's low (92)."""
    pick = burst("EEE", S[0])
    minutes = {intraday.key(pick): minute_object(pick, [
        (0, 99.0, 99.5, 96.9, 99.4), (3, 99.8, 100.5, 99.7, 100.3), (40, 98.0, 98.2, 96.0, 96.4),
        (41, 96.4, 96.5, 92.0, 92.5), (389, 96.4, 96.6, 96.3, 96.5)])}
    block = block_of([pick], {"EEE": frame((S[1], 99.0, 100.5, 92.0, 96.5))}, S[10], minutes)
    assert block["status"] == model_record.COMPUTED, block["reason"]
    row = row_of(block, "EEE")
    assert (row["bucket"], row["r"], row["entry"], row["minute_fill"]) == ("settled", -1.0, 100.0, True)
    assert row["minute_evidence"] == intraday.name_of(minutes[intraday.key(pick)])
    (bounds,) = block["stops"]["rows"]
    assert bounds["r"] == {"booked": -1.0, "at_close": -1.17, "at_low": -2.67}
    assert bounds["minute"] == {"offset": 40, "at": "10:10 ET", "open": 98.0, "low": 96.0,
                                "opened_at_or_under_stop": False, "r_at_low": -1.33, "usd_at_low": -40.0,
                                "evidence": row["minute_evidence"]}
    assert any("10:10 ET" in s and "-1.33R" in s for s in block["sentences"])


def test_minute_bars_of_another_session_bound_nothing():
    """CCC's stop came on its third day; minute bars exist only for a first
    day, so none bound it even when the archive holds that pick's object."""
    pick = burst("CCC", S[0])
    minutes = {intraday.key(pick): minute_object(pick, [(0, 100.5, 103.0, 100.2, 102.0)])}
    block = block_of([pick], {"CCC": frame(*HALF_THEN_STOP)}, S[10], minutes)
    assert block["stops"]["rows"][0]["minute"] is None and block["status"] == model_record.COMPUTED


# -------------------------------------------------- one share, uncertain -----

ONE_SHARE_BARS = [(S[1], 100.4, 102.0, 100.1, 101.5),       # filled at the open, 100.40; stop to 100.10
                  (S[2], 102.0, 109.0, 101.8, 108.6),       # +8% is 108.43
                  (S[3], 104.0, 105.0, 103.0, 104.5)]       # opens under the stop raised to 108.75


def test_a_one_share_ticket_sold_whole_at_the_half_sale_is_walked_again_at_two_shares():
    """One share filled at 100.40, stop 97: one R is 3.40. It is sold whole
    at +8%, 108.43: 8.03 / 3.40 = 2.36R. At two shares one is sold there, the
    stop rises to 108.75, and the other is stopped at the next open, 104:
    (8.03 + 3.60) / 6.80 = 1.71R. GGG, one share stopped on its first day,
    and HHH, two shares, are not such tickets."""
    stopped = [(S[1], 100.4, 101.0, 96.0, 96.5)]
    picks = [coil("FFF", S[0], shares=1), coil("GGG", S[0], shares=1), coil("HHH", S[0], shares=2)]
    frames = {"FFF": frame(*ONE_SHARE_BARS), "GGG": frame(*stopped), "HHH": frame(*ONE_SHARE_BARS)}
    block = block_of(picks, frames, S[10])
    assert block["status"] == model_record.COMPUTED, block["reason"]
    assert [row_of(block, t)["r"] for t in ("FFF", "GGG", "HHH")] == [2.36, -1.0, 1.71]
    assert block["one_share"]["rows"] == [{"ticker": "FFF", "kind": "anticipation", "picked": S[0], "r": 2.36,
                                           "shares": 2, "status_at_two": "stopped", "r_at_two": 1.71}]
    assert block["one_share"]["count"] == 1 and block["one_share"]["unexamined"] == 0
    assert block["sum_r"] == 3.07                            # 2.36 - 1.00 + 1.71
    assert block["one_share"]["settled_sum_r"] == 2.42       # 1.71 - 1.00 + 1.71
    assert any("FFF +2.36R" in s and "FFF +1.71R" in s and "+2.42R" in s for s in block["sentences"])


def test_any_even_size_reads_as_two_shares_does():
    """Why two is the size walked: an even position halves exactly, so its R
    is the same at 2, 10 and 40 shares."""
    reads = []
    for shares in (2, 10, 40):
        block = block_of([coil("FFF", S[0], shares=shares)], {"FFF": frame(*ONE_SHARE_BARS)}, S[10])
        reads.append(row_of(block, "FFF")["r"])
    assert reads == [1.71, 1.71, 1.71]


def test_a_half_sold_position_still_open_is_not_a_one_share_case():
    """Ten shares, five sold at +8% yesterday and five still held tonight:
    its last sale is a half-sale, and it is neither settled nor one share."""
    block = block_of([burst("CCC", S[0])], {"CCC": frame(*HALF_THEN_STOP[:2])}, S[2])
    row = row_of(block, "CCC")
    assert (row["bucket"], row["status"], [e["event"] for e in row["sales"]]) == ("open", "sell_half", ["sell_half"])
    assert block["one_share"]["rows"] == [] and block["status"] == model_record.COMPUTED


def test_the_two_share_sum_is_withheld_when_the_second_share_has_not_settled():
    """With bars only through the half-sale day the two-share walk is still
    open: its row says so and no settled sum is given."""
    block = block_of([coil("FFF", S[0], shares=1)], {"FFF": frame(*ONE_SHARE_BARS[:2])}, S[2])
    (again,) = block["one_share"]["rows"]
    assert (again["r"], again["status_at_two"], again["r_at_two"]) == (2.36, "sell_half", None)
    assert block["one_share"]["settled_sum_r"] is None
    assert any("is not given" in s for s in block["sentences"])


UNCERTAIN_BARS = [(S[1], 101.5, 102.0, 99.0, 100.0),        # opens over the 101 limit, trades back under it
                  (S[2], 100.0, 100.5, 96.0, 96.5)]         # the stop, raised to day 1's low 99, is taken


def test_an_uncertain_ticket_is_bounded_at_its_limit_and_its_trigger_and_is_in_no_sum():
    """If it filled at the 101 limit, the stop at 99 gives (99 - 101) / 4 =
    -0.50R; at the 100 trigger, (99 - 100) / 3 = -0.33R. Neither is a
    result: the ticket stays uncertain and nothing is summed."""
    block = block_of([coil("UUU", S[0], shares=4)], {"UUU": frame(*UNCERTAIN_BARS)}, S[10])
    assert block["status"] == model_record.COMPUTED, block["reason"]
    assert block["uncertain"]["rows"] == [{
        "ticker": "UUU", "kind": "anticipation", "picked": S[0], "reason": "open_above_limit",
        "trigger": 100.0, "limit": 101.0, "status_if_filled_at_limit": "stopped", "r_if_filled_at_limit": -0.5,
        "status_if_filled_at_trigger": "stopped", "r_if_filled_at_trigger": -0.33}]
    row = row_of(block, "UUU")
    assert (row["bucket"], row["r"], row["model_usd"], row["entry"]) == ("uncertain", None, None, None)
    assert block["sum_r"] is None and block["model_usd"] is None and block["stops"]["count"] == 0
    assert any("-0.50R if filled at its $101.00 limit and -0.33R if filled at its $100.00 trigger" in s
               for s in block["sentences"])


def test_a_bound_that_cannot_settle_is_left_empty():
    """An uncertain day with no later bar: neither walk has ended, so
    neither bound has an R."""
    block = block_of([coil("UUU", S[0], shares=4)], {"UUU": frame(UNCERTAIN_BARS[0])}, S[1])
    (bound,) = block["uncertain"]["rows"]
    assert (bound["r_if_filled_at_limit"], bound["r_if_filled_at_trigger"]) == (None, None)
    assert bound["status_if_filled_at_limit"] == "hold"


def test_a_bound_over_a_bar_the_walk_refuses_is_left_empty():
    """A later bar whose close sits outside its own range: ``plan.follow()``
    refuses it, so the bounds say nothing rather than fail the block."""
    bars = [UNCERTAIN_BARS[0], (S[2], 100.0, 100.5, 96.0, 101.0)]
    block = block_of([coil("UUU", S[0], shares=4)], {"UUU": frame(*bars)}, S[10])
    (bound,) = block["uncertain"]["rows"]
    assert block["status"] == model_record.COMPUTED, block["reason"]
    assert [bound[k] for k in ("status_if_filled_at_limit", "r_if_filled_at_limit", "status_if_filled_at_trigger",
                               "r_if_filled_at_trigger")] == [None, None, None, None]
    assert any(s.startswith("1 ticket is uncertain") and "bounds" not in s for s in block["sentences"])


# ---------------------------------------------------------- the accounts -----

def previous_brief(docs, rows, version=model_record.VERSION):
    (Path(docs) / model_record.BRIEF_FILE).write_text(json.dumps(
        {"version": 1, model_record.BRIEF_BLOCK: {"version": version, "plans": rows}}))


def test_the_account_is_the_records_own_tonight_carried_by_evidence_id_then_the_seed_then_unknown(tmp_path):
    seed_context = next(iter(model_record.SEED_ACCOUNTS)) + "0" * 48
    seed_account = model_record.SEED_ACCOUNTS[seed_context[:model_record.SEED_PREFIX_CHARS]]
    picks = [                                               # one share each: 4.00 at risk, inside every budget below
        coil("NEW", S[8], shares=1, evidence="a" * 64, context=OWN_CONTEXT),    # issued by this publication
        coil("OLD", S[2], shares=1, evidence="b" * 64, context="1" * 64),       # the previous brief recorded it
        coil("SEE", S[2], shares=1, evidence="d" * 64, context=seed_context),   # only the seed knows its publication
        coil("NON", S[2], shares=1, evidence="e" * 64, context="2" * 64),       # nobody does
        coil("BAR", S[2], shares=1),                                            # no evidence reference at all
        coil("SED", S[2], shares=1, evidence="f" * 64, context="3" * 64),       # carried, and it was the seed's
    ]
    previous_brief(tmp_path, [
        {"evidence_id": "b" * 64, "issued_equity": 5000.0, "risk_pct": 0.25, "account_basis": "record"},
        {"evidence_id": "f" * 64, "issued_equity": 2000.0, "risk_pct": 0.5, "account_basis": "seed"},
        # tonight's own ticket is also in the previous brief (a re-run), under an account its size
        # would fit: the record's own account still stands
        {"evidence_id": "a" * 64, "issued_equity": 7770.0, "risk_pct": 0.5, "account_basis": "record"},
    ])
    frames = {t: frame(*[quiet(d) for d in S[3:9]]) for t in ("NEW", "OLD", "SEE", "NON", "BAR", "SED")}
    block = block_of(picks, frames, S[8], docs=tmp_path)
    assert block["status"] == model_record.COMPUTED, block["reason"]
    got = {p["ticker"]: (p["issued_equity"], p["risk_pct"], p["account_basis"]) for p in block["plans"]}
    assert got == {"NEW": (30000.0, 0.5, "record"), "OLD": (5000.0, 0.25, "carried"),
                   "SEE": (*seed_account, "seed"), "NON": (None, None, "unknown"),
                   "BAR": (None, None, "unknown"), "SED": (2000.0, 0.5, "seed")}
    assert block["accounts"] == {"previous_brief": "read", "record": 1, "carried": 1, "seed": 2, "unknown": 2}
    assert [e["label"] for e in block["eras"]][-1] == "account not recorded"
    assert block["eras"][-1]["tickets"] == 2
    assert any("No account is recorded for 2 more tickets" in s for s in block["sentences"])


CARRIED_ROW = {"evidence_id": "b" * 64, "issued_equity": 5000.0, "risk_pct": 0.5, "account_basis": "record"}


@pytest.mark.parametrize("row, basis", [
    (CARRIED_ROW, "carried"),                                # the control: this row, whole, is carried
    ({**CARRIED_ROW, "issued_equity": "5000"}, "unknown"),
    ({**CARRIED_ROW, "issued_equity": -5000.0}, "unknown"),
    ({**CARRIED_ROW, "issued_equity": True}, "unknown"),
    ({**CARRIED_ROW, "issued_equity": float("inf")}, "unknown"),
    ({**CARRIED_ROW, "risk_pct": None}, "unknown"),
    ({**CARRIED_ROW, "risk_pct": 0}, "unknown"),
    ({**CARRIED_ROW, "account_basis": "unknown"}, "unknown"),
    ({**CARRIED_ROW, "account_basis": "guess"}, "unknown"),
    ({**CARRIED_ROW, "evidence_id": "e" * 64}, "unknown"),   # another ticket's row is not this one's
    ({**CARRIED_ROW, "evidence_id": None}, "unknown"),
    ("not a row", "unknown"),
])
def test_a_carried_account_that_is_not_one_is_not_taken(tmp_path, row, basis):
    (tmp_path / model_record.BRIEF_FILE).write_text(json.dumps(
        {model_record.BRIEF_BLOCK: {"version": model_record.VERSION, "plans": [row]}}).replace("Infinity", "1e999"))
    block = block_of([coil("OLD", S[2], shares=1, evidence="b" * 64, context="1" * 64)],
                     {"OLD": frame(*[quiet(d) for d in S[3:9]])}, S[8], docs=tmp_path)
    assert row_of(block, "OLD")["account_basis"] == basis
    assert (row_of(block, "OLD")["issued_equity"] is None) == (basis == "unknown")


@pytest.mark.parametrize("write, why", [
    (lambda d: None, "no previous brief"),
    (lambda d: (d / "brief.json").write_text("{not json"), "the previous brief could not be read"),
    (lambda d: (d / "brief.json").write_text("[1, 2]"), "the previous brief carries no model record of this version"),
    (lambda d: previous_brief(d, [{"evidence_id": "b" * 64, "issued_equity": 5000.0, "risk_pct": 0.5,
                                   "account_basis": "record"}], version=model_record.VERSION + 1),
     "the previous brief carries no model record of this version"),
    (lambda d: (d / "brief.json").write_text(json.dumps({"model_record": {"version": 1, "plans": "x"}})),
     "the previous brief carries no model record of this version"),
])
def test_a_previous_brief_that_cannot_be_read_carries_nothing_and_says_why(tmp_path, write, why):
    write(tmp_path)
    block = block_of([coil("OLD", S[2], shares=1, evidence="b" * 64, context="1" * 64)],
                     {"OLD": frame(*[quiet(d) for d in S[3:9]])}, S[8], docs=tmp_path)
    assert block["accounts"]["previous_brief"] == why and row_of(block, "OLD")["account_basis"] == "unknown"
    assert block["status"] == model_record.COMPUTED


def test_a_previous_brief_over_its_read_bound_is_not_read(tmp_path, monkeypatch):
    previous_brief(tmp_path, [CARRIED_ROW])
    pick, frames = coil("OLD", S[2], shares=1, evidence="b" * 64, context="1" * 64), {}
    assert row_of(block_of([pick], frames, S[8], docs=tmp_path), "OLD")["account_basis"] == "carried"
    monkeypatch.setattr(model_record, "BRIEF_MAX_BYTES", (tmp_path / model_record.BRIEF_FILE).stat().st_size - 1)
    block = block_of([pick], frames, S[8], docs=tmp_path)
    assert row_of(block, "OLD")["account_basis"] == "unknown"
    assert block["accounts"]["previous_brief"] == "the previous brief is over its read bound"


def test_what_the_previous_brief_recorded_stands_over_the_seed(tmp_path):
    """A ticket the seed lists and the previous brief also recorded: the
    brief's account is the record's own at issue, so it is the one taken."""
    prefix, seeded = next(iter(model_record.SEED_ACCOUNTS.items()))
    pick = coil("OLD", S[2], shares=1, evidence="b" * 64, context=prefix + "0" * 48)
    frames = {"OLD": frame(*[quiet(d) for d in S[3:9]])}
    assert row_of(block_of([pick], frames, S[8], docs=tmp_path), "OLD")["account_basis"] == "seed"
    previous_brief(tmp_path, [{**CARRIED_ROW, "issued_equity": seeded[0] + 1000.0}])
    row = row_of(block_of([pick], frames, S[8], docs=tmp_path), "OLD")
    assert (row["issued_equity"], row["account_basis"]) == (seeded[0] + 1000.0, "carried")


def test_an_account_the_tickets_own_risk_does_not_fit_is_not_taken(tmp_path):
    """Ten shares with 4.00 between limit and stop put 40.00 at risk. A
    carried $5,000 at 0.5% has a 25.00 budget: it cannot be the account that
    sized this ticket. $8,000 (40.00, the budget exactly) can."""
    pick = coil("OLD", S[2], evidence="b" * 64, context="1" * 64)
    frames = {"OLD": frame(*[quiet(d) for d in S[3:9]])}
    for equity, basis in ((5000.0, "unknown"), (8000.0, "carried")):
        previous_brief(tmp_path, [{"evidence_id": "b" * 64, "issued_equity": equity, "risk_pct": 0.5,
                                   "account_basis": "record"}])
        row = row_of(block_of([pick], frames, S[8], docs=tmp_path), "OLD")
        assert (row["planned_risk_usd"], row["account_basis"]) == (40.0, basis)


def test_a_ticket_of_tonights_session_from_an_earlier_run_is_not_given_this_runs_account(tmp_path):
    """A re-run of a session keeps a pick it no longer issues. That pick
    carries the first run's context, so it is not sized by this run's
    account, and it is withdrawn, read off the record itself."""
    earlier = coil("GON", S[8], evidence="b" * 64, context="1" * 64)
    burst_earlier = burst("GON", S[8], evidence="d" * 64, context="1" * 64)
    unlisted = coil("OFF", S[8], evidence="e" * 64, context="1" * 64)
    tonight = coil("NEW", S[8], evidence="a" * 64, context=OWN_CONTEXT)
    frames = {t: frame(*[quiet(d) for d in S[3:9]]) for t in ("GON", "NEW", "OFF")}
    rec, data = published([earlier, burst_earlier, unlisted, tonight], frames, S[8])
    data["run"]["published_at"] = "2026-03-13T02:00:00+00:00"
    data["watchlist"] = {"top": [{"ticker": "GON", "evidence": {"id": "9" * 64, "gate": {
        "ticket": False, "reason": "plan_withheld"}}}]}
    data["bursts"] = [{"ticker": "GON", "evidence": {"id": "8" * 64, "gate": {
        "ticket": False, "reason": "quality_grade"}}}]
    block = model_record.build(rec, frames, None, data, tmp_path)
    gone, new = row_of(block, "GON", kind="anticipation"), row_of(block, "NEW")
    assert (gone["account_basis"], gone["issued_equity"], gone["withdrawn"]) == ("unknown", None, True)
    # tonight's own ticket is this run's: not withdrawn, and no ledger is needed to say so
    assert (new["account_basis"], new["issued_equity"], new["withdrawn"]) == ("record", 30000.0, False)
    assert (block["withdrawn"]["unknown"], block["withdrawn"]["ledger"]["entries"]) == (0, 0)
    later = {"published_at": "2026-03-13T02:00:00+00:00", "listed": True, "ticket": False}
    assert block["withdrawn"]["tickets"] == [
        {"ticker": "GON", "kind": "anticipation", "picked": S[8], "evidence_id": "b" * 64, "basis": "record",
         "bucket": "pending", "r": None, "later": {**later, "reason": "plan_withheld"}},
        {"ticker": "GON", "kind": "burst", "picked": S[8], "evidence_id": "d" * 64, "basis": "record",
         "bucket": "pending", "r": None, "later": {**later, "reason": "quality_grade"}},
        # the later run does not list OFF at all
        {"ticker": "OFF", "kind": "anticipation", "picked": S[8], "evidence_id": "e" * 64, "basis": "record",
         "bucket": "pending", "r": None,
         "later": {"published_at": "2026-03-13T02:00:00+00:00", "listed": False, "ticket": None, "reason": None}}]
    assert block["status"] == model_record.COMPUTED, block["reason"]


def test_the_eras_split_the_counts_the_r_and_the_dollars_by_account(tmp_path):
    """CCC (10 shares, +2.47R, +86.45) was sized at $5,000 and DDD (10
    shares, -1.86R, -65.00) by tonight's $30,000: the R sums to +0.61 and
    the dollars to +21.45, and each era keeps its own."""
    gap = [(S[1], 100.5, 103.0, 100.0, 102.0), (S[2], 94.0, 95.0, 90.0, 91.0)]
    previous_brief(tmp_path, [{"evidence_id": "b" * 64, "issued_equity": 12000.0, "risk_pct": 0.5,
                               "account_basis": "carried"}])
    picks = [burst("CCC", S[0], evidence="b" * 64, context="1" * 64), burst("DDD", S[0], evidence="b" * 63 + "c",
                                                                           context="1" * 64),
             coil("NEW", S[10], evidence="a" * 64, context=OWN_CONTEXT)]
    frames = {"CCC": frame(*HALF_THEN_STOP), "DDD": frame(*gap), "NEW": frame(quiet(S[10]))}
    block = block_of(picks, frames, S[10], docs=tmp_path)
    assert block["status"] == model_record.COMPUTED, block["reason"]
    assert [(e["label"], e["tickets"], e["setups"], e["settled"], e["sum_r"], e["model_usd"],
             e["risk_at_fill_usd"]) for e in block["eras"]] == [
        ("$12,000 at 0.5% risk", 1, 1, 1, 2.47, 86.45, 35.0),
        ("$30,000 at 0.5% risk", 1, 1, 0, None, None, None),
        ("account not recorded", 1, 1, 1, -1.86, -65.0, 35.0)]
    assert block["eras"][0]["planned_risk_usd"] == {"min": 50.0, "max": 50.0, "sum": 50.0}
    assert (block["sum_r"], block["model_usd"]) == (0.61, 21.45)
    assert sum(e["tickets"] for e in block["eras"]) == block["tickets"]
    assert any(s.startswith("A sum of R is not a sum of dollars") and "+0.61R" in s and "+$21.45" in s
               for s in block["sentences"])


def test_a_setup_issued_again_under_another_account_is_counted_once_in_the_era_of_its_first_ticket(tmp_path):
    """AAA is offered on S[3] under the $5,000 account the previous brief
    recorded and never fills. It is offered again on S[8], the last session
    the first ticket's window reaches, by tonight's publication at $30,000.
    Two tickets in two eras are ONE setup: the era of its first ticket counts
    it and the other counts none, so the eras' setups sum to the block's. BBB
    beside it is one ticket and one setup of tonight's era."""
    previous_brief(tmp_path, [{"evidence_id": "b" * 64, "issued_equity": 5000.0, "risk_pct": 0.5,
                               "account_basis": "record"}])
    picks = [coil("AAA", S[3], shares=1, evidence="b" * 64, context="1" * 64),
             coil("AAA", S[8], shares=1, evidence="a" * 64, context=OWN_CONTEXT),
             coil("BBB", S[8], shares=1, evidence="d" * 64, context=OWN_CONTEXT)]
    frames = {t: frame(*[quiet(d) for d in S[4:9]]) for t in ("AAA", "BBB")}
    block = block_of(picks, frames, S[8], docs=tmp_path)
    assert block["status"] == model_record.COMPUTED, block["reason"]
    assert (block["tickets"], block["distinct_setups"], block["reissued_tickets"]) == (3, 2, 1)
    assert [(p["ticker"], p["picked"], p["setup"], p["issue_no"], p["issued_equity"], p["bucket"])
            for p in block["plans"]] == [
        ("AAA", S[3], f"anticipation:AAA:{S[3]}", 1, 5000.0, "not_filled"),
        ("AAA", S[8], f"anticipation:AAA:{S[3]}", 2, 30000.0, "pending"),
        ("BBB", S[8], f"anticipation:BBB:{S[8]}", 1, 30000.0, "pending")]
    assert [(e["label"], e["tickets"], e["setups"]) for e in block["eras"]] == [
        ("$5,000 at 0.5% risk", 1, 1), ("$30,000 at 0.5% risk", 2, 1)]
    # every setup is in exactly one era, and every ticket is
    assert sum(e["setups"] for e in block["eras"]) == block["distinct_setups"] == len(block["setups"])
    assert sum(e["tickets"] for e in block["eras"]) == block["tickets"]
    # the stated rule, on the frozen record too: 17 setups over its three accounts
    frozen_eras = frozen_block(tmp_path / "frozen")["eras"]
    assert sum(e["setups"] for e in frozen_eras) == 17


# --------------------------------------------------------- the withdrawn -----

def withdrawn_case(tmp_path, entries, picks=None):
    picks = picks or [coil("GON", S[0], evidence="a" * 64, context="1" * 64),
                      coil("KEP", S[0], evidence="b" * 64, context="1" * 64),
                      coil("LST", S[0], evidence="d" * 64, context="1" * 64)]
    write_ledger(tmp_path, entries)
    frames = {p["ticker"]: frame(*[quiet(d) for d in S[1:7]]) for p in picks}
    return block_of(picks, frames, S[8], docs=tmp_path)


def two_runs():
    """S0 was published twice. The first run ticketed GON and KEP; the
    second, later, withheld GON and ticketed KEP again with the same
    evidence. The later run's file name sorts FIRST, so only the stamp
    orders them. LST is in neither."""
    return [ledger_entry("f" * 64, S[0], "2026-03-03T02:00:00+00:00",
                         coils=[("GON", "a" * 64, True, None), ("KEP", "b" * 64, True, None)]),
            # the later run's GON row carries no evidence id (a row from before the evidence layer): it is
            # still what that run said of the ticker
            ledger_entry("0" * 64, S[0], "2026-03-03T12:00:00+00:00",
                         coils=[("GON", None, False, "plan_withheld"), ("KEP", "b" * 64, True, None)]),
            ledger_entry("5" * 64, S[1], "2026-03-04T02:00:00+00:00", coils=[("GON", "8" * 64, False, None)])]


def test_a_ticket_a_later_run_of_its_session_withdrew_is_found_in_the_ledger(tmp_path):
    block = withdrawn_case(tmp_path, two_runs())
    assert block["status"] == model_record.COMPUTED, block["reason"]
    assert {p["ticker"]: p["withdrawn"] for p in block["plans"]} == {"GON": True, "KEP": False, "LST": None}
    gone = block["withdrawn"]
    assert (gone["status"], gone["count"], gone["unknown"], gone["settled"]) == ("scanned", 1, 1, 0)
    assert gone["tickets"] == [{
        "ticker": "GON", "kind": "anticipation", "picked": S[0], "evidence_id": "a" * 64,
        "basis": "quality_ledger", "bucket": "not_filled", "r": None,
        "later": {"published_at": "2026-03-03T12:00:00+00:00", "listed": True, "ticket": False,
                  "reason": "plan_withheld"}}]
    # three entries on disk, the two of the wanted session parsed whole
    assert (gone["ledger"]["entries"], gone["ledger"]["parsed"], gone["ledger"]["unread"]) == (3, 2, 0)
    assert any(s.startswith("1 counted ticket was withdrawn") and f"GON {S[0]}" in s for s in block["sentences"])
    assert any("is not known for 1 ticket" in s for s in block["limits"])


def test_a_ticket_issued_by_the_sessions_last_run_is_not_withdrawn(tmp_path):
    """The other order: the first run withheld GON and the second, later,
    ticketed it. The retained pick is the later run's and nothing withdrew it."""
    first, second, other = two_runs()
    first["publication"]["published_at"], second["publication"]["published_at"] = (
        second["publication"]["published_at"], first["publication"]["published_at"])
    block = withdrawn_case(tmp_path, [first, second, other])
    assert row_of(block, "GON")["withdrawn"] is False and block["withdrawn"]["count"] == 0
    assert not any("withdrawn" in s for s in block["sentences"])


def test_the_ledger_is_not_read_without_docs_and_says_so():
    picks = [coil("GON", S[0], evidence="a" * 64, context="1" * 64)]
    block = block_of(picks, {"GON": frame(*[quiet(d) for d in S[1:7]])}, S[8])
    assert row_of(block, "GON")["withdrawn"] is None
    assert (block["withdrawn"]["status"], block["withdrawn"]["reason"]) == ("skipped", "no docs directory was given")
    assert any("no docs directory was given" in s for s in block["limits"])


def test_the_ledger_scan_is_all_or_nothing_past_its_bound(tmp_path, monkeypatch):
    monkeypatch.setattr(model_record, "LEDGER_SCAN_MAX_ENTRIES", 2)
    block = withdrawn_case(tmp_path, two_runs())
    assert block["withdrawn"]["status"] == "skipped" and "3 entries" in block["withdrawn"]["reason"]
    assert {p["withdrawn"] for p in block["plans"]} == {None} and block["withdrawn"]["count"] == 0
    assert block["withdrawn"]["ledger"] == {"entries": 3, "unread": 0, "parsed": 0, "expanded_bytes": 0}


def test_an_entry_that_cannot_be_read_leaves_not_withdrawn_unknown_and_withdrawn_standing(tmp_path):
    """One corrupt entry could be a later run of any session: a ticket found
    withdrawn stays found, and one not found is unknown, not cleared."""
    block = withdrawn_case(tmp_path, two_runs())
    (tmp_path / quality_ledger.DIRECTORY / ("7" * 64 + ".json.gz")).write_bytes(b"not gzip")
    again = withdrawn_case(tmp_path, [])
    assert row_of(block, "KEP")["withdrawn"] is False and row_of(again, "KEP")["withdrawn"] is None
    assert row_of(again, "GON")["withdrawn"] is True and again["withdrawn"]["ledger"]["unread"] == 1
    assert any("could not be read" in s for s in again["limits"])


def test_an_entry_over_the_ledgers_own_bound_is_not_read(tmp_path, monkeypatch):
    """At the bound an entry is read; one byte over it is not, though that
    one byte more would still have been expanded whole."""
    first = two_runs()[0]
    write_ledger(tmp_path, [first])
    size = len(quality_ledger.encoded(first))
    monkeypatch.setattr(quality_ledger, "MAX_ENTRY_BYTES", size)
    scan = model_record.ledger_sessions(tmp_path, {S[0]})
    assert (scan["unread"], scan["parsed"], scan["expanded_bytes"]) == (0, 1, size)
    monkeypatch.setattr(quality_ledger, "MAX_ENTRY_BYTES", size - 1)
    scan = model_record.ledger_sessions(tmp_path, {S[0]})
    assert (scan["status"], scan["unread"], scan["parsed"], scan["sessions"]) == ("scanned", 1, 0, {})


def test_the_publication_block_is_the_one_whose_hash_is_the_files_name():
    """The quick read takes the first ``"publication":`` object whose hash is
    the file's name. An entry that carries another object under that word
    first is still read by its own; one that carries none is parsed whole."""
    name = "f" * 64
    decoy = {"input": {"publication": {"session": "1999-01-01", "sha256": "0" * 64}},
             "publication": {"session": S[0], "sha256": name}}
    text = json.dumps(decoy, sort_keys=True, separators=(",", ":"))
    assert model_record._publication_block(text, name) == {"session": S[0], "sha256": name}
    assert model_record._publication_block(text, "1" * 64) is None
    assert model_record._publication_block(json.dumps(decoy, indent=1), name) is None   # spaced: not the quick read


def test_an_entry_the_quick_read_cannot_place_is_parsed_whole(tmp_path):
    """Indented JSON defeats the quick read; the entry is still read."""
    folder = tmp_path / quality_ledger.DIRECTORY
    folder.mkdir(parents=True)
    for entry in two_runs():
        (folder / (entry["publication"]["sha256"] + ".json.gz")).write_bytes(
            gzip.compress(json.dumps(entry, indent=1).encode()))
    scan = model_record.ledger_sessions(tmp_path, {S[0]})
    assert (scan["status"], scan["unread"], scan["parsed"]) == ("scanned", 0, 2)
    assert [e["sha256"] for e in scan["sessions"][S[0]]] == ["f" * 64, "0" * 64]


def test_an_entry_that_is_not_json_is_counted_unread(tmp_path):
    """One entry is not JSON at all; another is cut off after a publication
    block the quick read can place. Neither is used and both are counted."""
    first, second, _ = two_runs()
    write_ledger(tmp_path, [first])
    folder = tmp_path / quality_ledger.DIRECTORY
    (folder / ("3" * 64 + ".json.gz")).write_bytes(gzip.compress(b"not json at all"))
    cut = quality_ledger.encoded(second).decode()
    cut = cut[:cut.index('"signal"')]
    (folder / (second["publication"]["sha256"] + ".json.gz")).write_bytes(gzip.compress(cut.encode()))
    scan = model_record.ledger_sessions(tmp_path, {S[0]})
    assert (scan["entries"], scan["unread"], scan["parsed"]) == (3, 2, 1)
    assert [e["sha256"] for e in scan["sessions"][S[0]]] == ["f" * 64]


def test_an_entry_whose_stamp_is_not_its_own_is_not_used(tmp_path):
    """An entry filed under another name, with no readable stamp, or with a
    stamp that names no offset, is counted unread: it cannot be placed in
    its session's order."""
    first, second, other = two_runs()
    second["publication"]["published_at"] = "yesterday"
    write_ledger(tmp_path, [first, second])
    assert model_record.ledger_sessions(tmp_path, {S[0]})["unread"] == 1
    second["publication"]["published_at"] = "2026-03-03T12:00:00"          # no offset: when is not known
    write_ledger(tmp_path, [second])
    assert model_record.ledger_sessions(tmp_path, {S[0]})["unread"] == 1
    (tmp_path / quality_ledger.DIRECTORY / ("4" * 64 + ".json.gz")).write_bytes(
        gzip.compress(quality_ledger.encoded(other)))
    scan = model_record.ledger_sessions(tmp_path, {S[0], S[1]})
    assert (scan["unread"], scan["parsed"], list(scan["sessions"])) == (2, 1, [S[0]])


# ------------------------------------------------- the scorecard's own -------

def test_a_ticket_with_no_frame_is_unmeasured_as_the_scorecard_counts_it():
    picks = [coil("AAA", S[0]), coil("ZZZ", S[0])]
    for frames, minutes in (({"AAA": frame(*[quiet(d) for d in S[1:7]])}, None), (None, None), ({}, {})):
        rec, data = published(picks, frames or {}, S[8])
        block = model_record.build(rec, frames, minutes, data)
        assert block["status"] == model_record.COMPUTED, block["reason"]
        assert row_of(block, "ZZZ")["bucket"] == "unmeasured" and row_of(block, "ZZZ")["bars"] is None
        assert block["buckets"]["unmeasured"] == data["scorecard"]["unmeasured"] >= 1


def test_a_ticket_of_tonight_awaits_its_first_session():
    block = block_of([coil("NEW", S[8]), coil("OLD", S[7])], {"NEW": frame(quiet(S[8])),
                                                             "OLD": frame(quiet(S[8]))}, S[8])
    assert (row_of(block, "NEW")["bucket"], row_of(block, "OLD")["bucket"]) == ("pending", "not_filled")
    assert block["status"] == model_record.COMPUTED and "1 awaiting first session" in block["sentences"][1]


def test_an_open_ticket_and_one_whose_bars_stopped_short_are_counted_as_the_scorecard_counts_them():
    """OPN filled yesterday and is held with bars through tonight: open. STL
    filled the same day but its frame has no bar for tonight: unmeasured,
    not open. Neither has an R or model dollars yet."""
    filled = (S[1], 100.5, 103.0, 100.2, 102.0)
    frames = {"OPN": frame(filled, (S[2], 102.0, 103.0, 101.0, 102.5)), "STL": frame(filled)}
    block = block_of([burst("OPN", S[0]), burst("STL", S[0])], frames, S[2])
    assert block["status"] == model_record.COMPUTED, block["reason"]
    assert [(p["ticker"], p["bucket"], p["status"], p["r"], p["model_usd"], p["entry"], p["through"])
            for p in block["plans"]] == [("OPN", "open", "hold", None, None, 100.5, S[2]),
                                         ("STL", "unmeasured", "hold", None, None, 100.5, S[1])]
    assert block["sum_r"] is None and "No ticket has settled, so there is no R to sum." in block["sentences"]


def test_tonights_ticket_has_no_account_when_the_record_carries_none():
    pick = coil("NEW", S[8], shares=1, evidence="a" * 64, context=OWN_CONTEXT)
    for account in ({}, {"equity": 30000.0}, {"equity": "30000", "risk_pct": 0.5}, {"equity": 0, "risk_pct": 0.5}):
        block = block_of([pick], {}, S[8], account=account)
        assert (row_of(block, "NEW")["account_basis"], row_of(block, "NEW")["issued_equity"]) == ("unknown", None)
    assert any(s == "No account is recorded for the 1 ticket." for s in block["sentences"])
    assert row_of(block_of([pick], {}, S[8]), "NEW")["account_basis"] == "record"


def test_a_ticket_older_than_the_scorecards_window_is_not_counted():
    old = str(exchange_sessions.sessions_before(date.fromisoformat(S[8]), record.SCORECARD_SESSIONS + 1)[0])
    edge = str(exchange_sessions.sessions_before(date.fromisoformat(S[8]), record.SCORECARD_SESSIONS)[0])
    block = block_of([coil("OUT", old), coil("EDG", edge)], {}, S[8])
    assert [p["ticker"] for p in block["plans"]] == ["EDG"] and block["window"] == {
        "from": edge, "through": S[8], "sessions": record.SCORECARD_SESSIONS, "includes_current": True}


def test_every_figure_is_the_scorecards_or_the_block_says_it_is_not():
    picks = [burst("CCC", S[0]), coil("AAA", S[0])]
    frames = {"CCC": frame(*HALF_THEN_STOP), "AAA": frame(*[quiet(d) for d in S[1:7]])}
    rec, data = published(picks, frames, S[10])
    assert model_record.build(rec, frames, None, data)["status"] == model_record.COMPUTED
    for name, value in (("sum_r", 2.48), ("settled", 2), ("not_filled", 0), ("plans", 3), ("unmeasured", 1)):
        block = model_record.build(rec, frames, None, {**data, "scorecard": {**data["scorecard"], name: value}})
        assert block["status"] == model_record.UNRECONCILED and name in block["reason"], name
        assert block["sentences"] == [f"The model record's figures do not reconcile with the record's own "
                                      f"scorecard and are not to be quoted: {block['reason']}."]
    block = model_record.build(rec, frames, None, {**data, "scorecard": None})
    assert block["status"] == model_record.UNRECONCILED and "carries no scorecard" in block["reason"]


def test_a_ticket_the_scorecard_reads_otherwise_is_named(monkeypatch):
    """Each ticket is held to ``record.scorecard_rows()`` over the same
    inputs. A row that says otherwise, or a row with no ticket, or a ticket
    with no row, is the reason."""
    picks = [burst("CCC", S[0]), coil("AAA", S[0])]
    frames = {"CCC": frame(*HALF_THEN_STOP), "AAA": frame(*[quiet(d) for d in S[1:7]])}
    rec, data = published(picks, frames, S[10])
    rows = record.scorecard_rows(rec, frames, S[10])

    def reading(changed):
        monkeypatch.setattr(record, "scorecard_rows", lambda *a, **k: changed)
        return model_record.build(rec, frames, None, data)

    other_r = [dict(r, r=2.5) if r["ticker"] == "CCC" else r for r in rows]
    block = reading(other_r)
    assert block["status"] == model_record.UNRECONCILED
    assert f"CCC {S[0]} reads settled at R 2.47 here and settled at R 2.5 in the scorecard's own row" in block["reason"]
    other_bucket = [dict(r, bucket="uncertain") if r["ticker"] == "AAA" else r for r in rows]
    assert f"AAA {S[0]} reads not_filled" in reading(other_bucket)["reason"]
    assert f"AAA {S[0]} has no scorecard row" in reading([r for r in rows if r["ticker"] == "CCC"])["reason"]
    assert "1 scorecard row has no ticket here" in reading(rows + [dict(rows[0], ticker="XXX")])["reason"]
    assert reading(rows)["status"] == model_record.COMPUTED


@pytest.mark.parametrize("variant, tickets, unmeasured", [("full", 48, 0), ("closed", 48, 0), ("partial", 47, 16)])
def test_the_block_reconciles_on_what_the_evening_run_holds(tmp_path, monkeypatch, variant, tickets, unmeasured):
    """``run_evening()`` driven through the doubles the fixtures use: the
    block is built from the very ``rec``, ``frames``, ``minutes`` and ``data``
    that ``pipeline.finish_publication()`` holds, on an ordinary night, a
    closed one and one whose fetch left sixteen plans without a frame, and
    each time its counts and its R are the published scorecard's."""
    held = {}
    retain = pipeline.retain_publication

    def capture(rep, docs, data, rec, frames, stats, minutes):
        held.update(docs=docs, data=data, rec=rec, frames=frames, minutes=minutes)
        return retain(rep, docs, data, rec, frames, stats, minutes)

    monkeypatch.setattr(pipeline, "retain_publication", capture)
    make_fixture.run_variant(variant, tmp_path / "docs")
    block = model_record.build(held["rec"], held["frames"], held["minutes"], held["data"], held["docs"])
    card = held["data"]["scorecard"]
    assert block["status"] == model_record.COMPUTED, block["reason"]
    assert (block["tickets"], block["buckets"]["unmeasured"]) == (tickets, unmeasured) == (
        card["plans"], card["unmeasured"])
    assert block["sum_r"] == card["sum_r"] and block["session"] == held["data"]["run"]["session"]
    assert all(block["buckets"][name] == card[name] for name in record.SCORECARD_BUCKETS)
    assert block["distinct_setups"] == tickets and block["stops"]["count"] > 10
    json.dumps(block, allow_nan=False)


def test_a_long_list_of_reasons_is_bounded():
    picks = [coil(f"T{i:02d}", S[0]) for i in range(12)]
    frames = {p["ticker"]: frame(*[quiet(d) for d in S[1:7]]) for p in picks}
    rec, data = published(picks, frames, S[10])
    block = model_record.build({"picks": picks}, frames, None, {**data, "scorecard": {
        **data["scorecard"], **{n: -1 for n in record.SCORECARD_BUCKETS}}})
    assert block["reason"].count(";") == model_record.RECONCILE_REASONS_MAX
    assert block["reason"].endswith(f"and {len(record.SCORECARD_BUCKETS) - model_record.RECONCILE_REASONS_MAX} more")


def test_the_rate_sentence_is_said_only_below_the_scorecards_own_floor():
    """With as many settled tickets as ``record.SCORECARD_MIN_PLANS`` the
    record prints its rates, so the block does not say it prints none."""
    floor = record.SCORECARD_MIN_PLANS

    def said(count):
        picks = [burst(f"T{i:02d}", S[0]) for i in range(count)]
        block = block_of(picks, {p["ticker"]: frame(*HALF_THEN_STOP) for p in picks}, S[10])
        assert block["status"] == model_record.COMPUTED and block["buckets"]["settled"] == count
        return block["sentences"][2]

    assert said(floor - 1).endswith(f" Below {floor} settled tickets the record prints no rate.")
    assert said(floor) == (f"The {floor} settled tickets sum to {2.47 * floor:+.2f}R ({floor} wins, 0 losses, "
                           f"0 breakeven).")


def test_a_record_with_no_session_is_refused_in_words():
    block = model_record.build({"picks": [coil("AAA", S[0])]}, {}, None, {"run": {}})
    assert (block["status"], block["reason"], block["tickets"], block["window"]) == (
        model_record.UNRECONCILED, "the record names no session", 0, None)
    assert model_record.build(None, None, None, None)["reason"] == "the record names no session"
    # a record whose picks are not a list holds no ticket, as an empty one does
    rec, data = published([], {}, S[8])
    block = model_record.build({"picks": {"AAA": 1}}, {}, None, data)
    assert (block["status"], block["tickets"]) == (model_record.COMPUTED, 0)


def test_no_ticket_is_said_in_one_sentence():
    block = block_of([], {}, S[8])
    assert block["status"] == model_record.COMPUTED and block["tickets"] == 0
    assert block["sentences"] == ["The model record holds no ticket in its window."]


def test_the_block_is_json_the_same_twice_and_changes_nothing_it_was_given(tmp_path):
    fixture = frozen()
    write_ledger(tmp_path, fixture["ledger_entries"])
    rec, frames = {"picks": fixture["picks"]}, frozen_frames(fixture)
    before = json.dumps([rec, fixture["minutes"], fixture["data"]], sort_keys=True)
    first = model_record.build(rec, frames, fixture["minutes"], fixture["data"], tmp_path)
    second = model_record.build(rec, frames, fixture["minutes"], fixture["data"], tmp_path)
    assert json.dumps(first, allow_nan=False) == json.dumps(second, allow_nan=False)
    assert json.dumps([rec, fixture["minutes"], fixture["data"]], sort_keys=True) == before
    assert first["version"] == model_record.VERSION == 1
    for name in ("version", "status", "window", "tickets", "distinct_setups", "reissued_tickets", "buckets",
                 "buckets_by_setup", "sum_r", "plans", "setups", "eras", "stops", "uncertain", "sentences",
                 "limits"):
        assert name in first, name


#: what the secret scan reads as a credential's name (gitleaks' generic-api-key keywords)
CREDENTIAL_NAME = re.compile(r"access|auth|api|credential|creds|key|passw|secret|token", re.I)


def test_no_property_of_the_block_is_named_like_a_credential(tmp_path):
    """The brief is a served file: a property named like a credential beside
    an evidence id or an object name is what the secret scan flags."""
    names = set()

    def walk(value):
        if isinstance(value, dict):
            for name, inner in value.items():
                names.add(name)
                walk(inner)
        elif isinstance(value, list):
            for inner in value:
                walk(inner)

    walk(frozen_block(tmp_path))
    assert len(names) > 60 and not [n for n in names if CREDENTIAL_NAME.search(n)]


def test_the_words_a_reader_takes_carry_no_dash_and_end_as_sentences(tmp_path):
    block = frozen_block(tmp_path)
    said = [*block["sentences"], *block["limits"], *block["definitions"]]
    labels = [*block["stops"]["labels"].values(), block["uncertain"]["label"], block["one_share"]["label"]]
    assert len(said) > 15
    for text in said + labels:
        assert "—" not in text and "–" not in text and "  " not in text, text
    for text in said:
        assert text.endswith(".") and (text[0].isupper() or text[0].isdigit()), text


# ------------------------------------------- the frozen 17 November record ---

def test_the_frozen_record_is_22_tickets_17_setups_and_5_reissues(tmp_path):
    block = frozen_block(tmp_path)
    assert block["status"] == model_record.COMPUTED, block["reason"]
    assert (block["session"], block["tickets"], block["distinct_setups"], block["reissued_tickets"]) == (
        "2026-11-17", 22, 17, 5)
    assert block["buckets"] == {"settled": 5, "open": 0, "pending": 0, "uncertain": 1, "not_filled": 16,
                                "unmeasured": 0, "unreadable": 0, "unscored": 0}
    assert block["buckets_by_setup"] == {"settled": 5, "open": 0, "pending": 0, "uncertain": 1, "not_filled": 11,
                                         "unmeasured": 0, "unreadable": 0, "unscored": 0}
    assert {(s["ticker"], s["issues"], s["first"], s["last"]) for s in block["setups"] if s["issues"] > 1} == {
        ("MFIC", 4, "2026-11-09", "2026-11-13"), ("UTZ", 2, "2026-11-10", "2026-11-11"),
        ("OGN", 2, "2026-10-27", "2026-10-28")}
    # MFIC's fourth ticket came a session after a night without one, with its trigger two cents lower
    last = row_of(block, "MFIC", "2026-11-13")
    assert (last["issue_no"], last["changed"]) == (4, ["trigger", "limit", "stop", "shares"])
    assert (block["sum_r"], block["model_usd"], block["model_usd_missing"]) == (0.43, -83.14, 0)


def test_the_frozen_record_in_the_words_a_reader_takes(tmp_path):
    block = frozen_block(tmp_path)
    assert block["sentences"] == [
        "The model record counts 22 tickets issued from 2026-10-08 through 2026-11-13: 17 distinct setups, and "
        "5 tickets that issued a setup again on a later night.",
        "By ticket: 5 settled, 1 uncertain, 16 not filled. By setup: 5 settled, 1 uncertain, 11 not filled.",
        "Issued more than once: OGN anticipation 2 times (2026-10-27 to 2026-10-28); MFIC anticipation 4 times "
        "(2026-11-09 to 2026-11-13); UTZ anticipation 2 times (2026-11-10 to 2026-11-11). No ticket that was "
        "later issued again has a fill known, so re-issues raise the ticket counts and add nothing to the sum "
        "of R.",
        "The 5 settled tickets sum to +0.43R (2 wins, 3 losses, 0 breakeven). Below 20 settled tickets the "
        "record prints no rate.",
        "The tickets were sized against 3 model accounts: $10,000 at 0.5% risk (2 tickets, 1 settled, +0.41R, "
        "+$2.24 in model dollars); $2,000 at 0.5% risk (8 tickets, 1 settled, +3.02R, +$5.25 in model "
        "dollars); $30,000 at 0.5% risk (12 tickets, 3 settled, -3.00R, -$90.63 in model dollars).",
        "A sum of R is not a sum of dollars: R counts each ticket as one unit whatever its size. The settled "
        "tickets sum to +0.43R and to -$83.14 in model dollars.",
        "3 settled tickets ended on a stop. As the model books them, a stop first reached inside a session at "
        "exactly the stop price, the sum is -3.00R (-$90.63). With the same exits at the stop day's close it "
        "is -4.66R (-$140.78): what holding to the close would have been, not a fill estimate. At the stop "
        "day's low, a worst-case bound, it is -5.78R (-$174.64).",
        "Under those readings the settled sum is +0.43R as booked, -1.23R at the closes and -2.35R at the lows.",
        "VIK 2026-11-04: the retained minute bars first reach the stop at 09:58 ET, in a minute that opened at "
        "$88.26 with a low of $88.09; at that low the ticket reads -1.03R.",
        "2 settled tickets held 1 share and sold it whole at the half-sale step, because 1 share cannot be "
        "halved: SN +0.41R, EXEL +3.02R. Walked over the same bars at 2 shares: SN +0.22R, EXEL +2.62R. With "
        "those readings the settled sum is -0.16R.",
        "1 ticket is uncertain: the bars cannot say whether it filled, and it is in no sum. MCS 2026-10-28 "
        "reads -0.91R if filled at its $28.75 limit and -0.88R if filled at its $28.47 trigger. These are "
        "bounds, not results.",
        "3 counted tickets were withdrawn by a later run of their own session and stay in the record and in "
        "these counts: MG 2026-10-08, SN 2026-10-08 (settled, +0.41R), ZIM 2026-10-09.",
    ]
    assert block["limits"] == [
        "A model from bars alone, not a brokerage record: no fees, spread, slippage, tax or real execution is "
        "measured, and nothing here knows what anyone holds.",
        "Minute bars are retained only for a first day the daily bar could not place, so a stop day usually "
        "has its daily bar alone and its range stays between that day's low and the stop.",
        "A ticket's account is the publishing record's own, the previous brief's for the same evidence id, or "
        "the seed read off the publications in git; an account none of them gives is not guessed.",
    ]
    assert block["definitions"] == model_record.DEFINITIONS and len(block["definitions"]) == 5


def test_the_frozen_tickets_are_the_ledgers_own_rows(tmp_path):
    """Every ticket's bucket and R is the row the quality ledger retained
    for that publication, and the totals are its published scorecard's."""
    fixture, block = frozen(), frozen_block(tmp_path)
    assert [(p["ticker"], p["kind"], p["picked"], p["bucket"], p["status"], p["r"]) for p in block["plans"]] == [
        (r["ticker"], r["kind"], r["picked"], r["bucket"], r["status"], r["r"])
        for r in sorted(fixture["ledger_rows"], key=lambda r: (r["picked"], r["ticker"], r["kind"]))]
    card = fixture["data"]["scorecard"]
    assert (block["tickets"], block["sum_r"]) == (card["plans"], card["sum_r"])
    assert all(block["buckets"][name] == card[name] for name in record.SCORECARD_BUCKETS)
    assert sorted(p["ticker"] for p in block["plans"] if p["minute_fill"]) == ["EXEL", "SN", "VIK"]


def test_the_frozen_eras_are_three_accounts_and_r_is_not_dollars(tmp_path):
    block = frozen_block(tmp_path)
    assert [(e["label"], e["tickets"], e["setups"], e["settled"], e["buckets"]["uncertain"], e["sum_r"],
             e["model_usd"], e["risk_at_fill_usd"]) for e in block["eras"]] == [
        ("$10,000 at 0.5% risk", 2, 2, 1, 0, 0.41, 2.24, 5.46),
        ("$2,000 at 0.5% risk", 8, 7, 1, 1, 3.02, 5.25, 1.74),
        ("$30,000 at 0.5% risk", 12, 8, 3, 0, -3.0, -90.63, 90.63)]
    assert [(e["planned_risk_usd"]["min"], e["planned_risk_usd"]["max"]) for e in block["eras"]] == [
        (7.27, 12.48), (1.28, 4.84), (35.36, 75.0)]
    assert {p["account_basis"] for p in block["plans"]} == {"seed"}
    assert ("A sum of R is not a sum of dollars: R counts each ticket as one unit whatever its size. The settled "
            "tickets sum to +0.43R and to -$83.14 in model dollars.") in block["sentences"]


def test_the_frozen_stops_are_booked_at_the_stop_and_bounded_by_close_and_low(tmp_path):
    stops = frozen_block(tmp_path)["stops"]
    assert [(b["ticker"], b["date"], b["event"], b["entry"], b["stop_price"], b["close"], b["low"])
            for b in stops["rows"]] == [
        ("HQY", "2026-11-05", "stopped", 109.92, 106.11, 103.46, 102.14),
        ("RCBC", "2026-11-05", "stopped", 60.94, 58.93, 58.34, 58.0),
        ("VIK", "2026-11-05", "stopped", 91.17, 88.17, 86.16, 84.34)]
    assert [(b["r"], b["usd"]) for b in stops["rows"]] == [
        ({"booked": -1.0, "at_close": -1.7, "at_low": -2.04}, {"booked": -30.48, "at_close": -51.68, "at_low": -62.24}),
        ({"booked": -1.0, "at_close": -1.29, "at_low": -1.46}, {"booked": -30.15, "at_close": -39.0, "at_low": -44.1}),
        ({"booked": -1.0, "at_close": -1.67, "at_low": -2.28}, {"booked": -30.0, "at_close": -50.1, "at_low": -68.3})]
    assert [b["minute"] and (b["minute"]["at"], b["minute"]["open"], b["minute"]["low"], b["minute"]["r_at_low"])
            for b in stops["rows"]] == [None, None, ("09:58 ET", 88.26, 88.09, -1.03)]
    assert stops["sum_r"] == {"booked": -3.0, "at_close": -4.66, "at_low": -5.78}
    assert stops["sum_usd"] == {"booked": -90.63, "at_close": -140.78, "at_low": -174.64}
    assert stops["settled_sum_r"] == {"booked": 0.43, "at_close": -1.23, "at_low": -2.35}
    assert set(stops["labels"]) == {"booked", "at_close", "at_low", "minute"}
    assert "not a fill estimate" in stops["labels"]["at_close"] and "worst-case bound" in stops["labels"]["at_low"]


def test_the_frozen_one_share_wins_the_uncertain_ticket_and_the_withdrawn_three(tmp_path):
    block = frozen_block(tmp_path)
    assert [(o["ticker"], o["r"], o["r_at_two"]) for o in block["one_share"]["rows"]] == [
        ("SN", 0.41, 0.22), ("EXEL", 3.02, 2.62)]
    assert block["one_share"]["settled_sum_r"] == -0.16
    assert [(u["ticker"], u["reason"], u["r_if_filled_at_limit"], u["r_if_filled_at_trigger"])
            for u in block["uncertain"]["rows"]] == [("MCS", "open_above_limit", -0.91, -0.88)]
    gone = block["withdrawn"]
    assert [(w["ticker"], w["picked"], w["bucket"], w["r"], w["later"]["reason"], w["later"]["ticket"])
            for w in gone["tickets"]] == [
        ("MG", "2026-10-08", "not_filled", None, "plan_withheld", False),
        ("SN", "2026-10-08", "settled", 0.41, "no_order", False),
        ("ZIM", "2026-10-09", "not_filled", None, "plan_withheld", False)]
    assert (gone["count"], gone["settled"], gone["unknown"], gone["status"]) == (3, 1, 0, "scanned")
    assert sum(p["withdrawn"] is False for p in block["plans"]) == 19


def test_the_seed_is_each_frozen_tickets_own_account_by_its_own_size():
    """The seed is a hand-entered table, held here by the tickets themselves.
    Each ticket's planned risk at its limit is inside its seed account's risk
    budget for that night (equity x risk% x the regime's multiplier x the
    stop-risk multiplier): $12.50 at $10,000, $2.50 or $5.00 at $2,000,
    $37.50 or $75.00 at $30,000. And ``plan.size()`` gives the ticket's own
    share count under its seed account and under neither other account."""
    fixture = frozen()
    accounts = sorted(set(model_record.SEED_ACCOUNTS.values()))
    assert accounts == [(2000.0, 0.5), (10000.0, 0.5), (30000.0, 0.5)]
    used = set()
    for pick in fixture["picks"]:
        prefix = pick["evidence_ref"]["context_sha256"][:model_record.SEED_PREFIX_CHARS]
        used.add(prefix)
        levels = record.ticket_levels(pick)
        limit, stop = float(levels["limit"]), levels["stop"]

        def sized(account):
            at_full = plan.size(limit, stop, plan.Account(equity=account[0], risk_pct=account[1]))
            multiplier = breadth.SIZE_MULTIPLIER[pick["regime"]] * plan.stop_risk(at_full.stop_pct)[0]
            return plan.size(limit, stop, plan.Account(equity=account[0], risk_pct=account[1]), multiplier)

        own = sized(model_record.SEED_ACCOUNTS[prefix])
        assert own.shares == pick["shares"], pick["ticker"]
        assert round(pick["shares"] * (limit - stop), 2) <= own.budget_usd, pick["ticker"]
        assert own.budget_usd in {(2000.0, 0.5): (2.5, 5.0), (10000.0, 0.5): (12.5, 25.0),
                                  (30000.0, 0.5): (37.5, 75.0)}[model_record.SEED_ACCOUNTS[prefix]]
        for other in accounts:
            if other != model_record.SEED_ACCOUNTS[prefix]:
                assert sized(other).shares != pick["shares"], (pick["ticker"], other)
    assert used == set(model_record.SEED_ACCOUNTS)          # no row no ticket uses, no ticket without a row
    assert all(len(p) == model_record.SEED_PREFIX_CHARS and re.fullmatch(r"[0-9a-f]+", p)
               for p in model_record.SEED_ACCOUNTS)


# ------------------------------------------------------------ offline --------

def offline_docs(tmp_path, *, drop=("MG", "SN", "ZIM"), without=None, ledger_rows=True, change=None):
    """A docs directory holding the frozen record as the site holds it: the
    record with an observations block (without the bars of ``drop``, and
    without the dated bars ``without`` names for a ticker), the picks, the
    minute objects, and the publication's ledger entry."""
    fixture = frozen()
    symbols = {}
    for ticker, entry in fixture["bars"].items():
        if ticker not in drop:
            rows = [dict(r) for r in entry["rows"] if r["date"] not in (without or {}).get(ticker, ())]
            symbols[ticker] = {**rows[-1], "since": rows[0]["date"], "history": rows}
    data = {**fixture["data"], "observations": {"as_of": "2026-11-17", "symbols": symbols}}
    raw = (json.dumps(data, separators=(",", ":")) + "\n").encode()
    (tmp_path / "data.json").write_bytes(raw)
    (tmp_path / "picks.json").write_text(json.dumps(
        {"schema_version": 2, "picks": fixture["picks"] + [
            {"ticker": "BAD"},
            # dated and shaped like a pick, with its stop over its entry: record.pick_problem() refuses it
            {"ticker": "BAD", "date": "2026-11-13", "kind": "burst", "entry_ref": 10.0, "stop": 20.0, "shares": 1}]}))
    intraday.store(tmp_path, list(fixture["minutes"].values()))
    name = hashlib.sha256(raw).hexdigest()
    rows = [dict(r) for r in fixture["ledger_rows"]]
    if change:
        change(rows)
    if ledger_rows:
        write_ledger(tmp_path, [ledger_entry(name, "2026-11-17", "2026-11-18T04:26:01+00:00",
                                             outcome={"rows": rows})])
    return fixture


def test_offline_walks_what_the_record_carries_and_marks_what_it_does_not(tmp_path):
    """From docs alone: the 19 tickets whose bars the observations block
    still holds are walked and held to the ledger's rows; MG, SN and ZIM
    take their rows as they are, with no walk, no dollars, and no part in a
    sum they cannot be read for."""
    offline_docs(tmp_path)
    block = model_record.offline(tmp_path)
    assert block["status"] == model_record.COMPUTED, block["reason"]
    assert block["bars_source"] == "record_observations"
    assert (block["tickets"], block["distinct_setups"], block["reissued_tickets"], block["sum_r"]) == (22, 17, 5, 0.43)
    assert sorted(p["ticker"] for p in block["plans"] if p["bars"] == "not_carried") == ["MG", "SN", "ZIM"]
    sn = row_of(block, "SN")
    assert (sn["bucket"], sn["r"], sn["model_usd"], sn["entry"], sn["sales"]) == ("settled", 0.41, None, None, [])
    # the ledger row says the minute object placed SN's fill, and names the last bar its walk read
    assert (sn["minute_fill"], sn["through"]) == (True, "2026-10-15")
    assert sn["minute_evidence"] == intraday.name_of(frozen()["minutes"]["anticipation:SN:2026-10-08"])
    # ZIM's minute object placed no fill: the evidence is named and no minute fill is claimed
    zim = row_of(block, "ZIM")
    assert (zim["minute_fill"], zim["bucket"]) == (False, "not_filled") and zim["minute_evidence"] is not None
    assert (row_of(block, "MG")["minute_fill"], row_of(block, "MG")["minute_evidence"]) == (False, None)
    assert (block["model_usd"], block["model_usd_missing"]) == (-85.38, 1)
    assert (block["eras"][0]["sum_r"], block["eras"][0]["model_usd"], block["eras"][0]["model_usd_missing"]) == (
        0.41, None, 1)
    assert not any("in model dollars" in s and "+0.43R" in s for s in block["sentences"])
    # SN's one share cannot be walked again without its bars: EXEL's reading is given, the sum is not
    assert [o["ticker"] for o in block["one_share"]["rows"]] == ["EXEL"]
    assert (block["one_share"]["unexamined"], block["one_share"]["settled_sum_r"]) == (1, None)
    assert block["stops"]["sum_r"] == {"booked": -3.0, "at_close": -4.66, "at_low": -5.78}
    assert any(s.startswith("Built from the record's own observations block") and "3 tickets have bars" in s
               for s in block["limits"])
    # a pick the walk cannot read was left out, as record.load() leaves it out
    assert "BAD" not in {p["ticker"] for p in block["plans"]}


def test_offline_withholds_a_sum_a_ticket_without_bars_belongs_to(tmp_path):
    """With HQY's bars gone its row is still a settled stop, so the stop
    readings are not summed over the two that can be read."""
    offline_docs(tmp_path, drop=("HQY",))
    block = model_record.offline(tmp_path)
    assert block["status"] == model_record.COMPUTED, block["reason"]
    assert (block["stops"]["count"], block["stops"]["unexamined"]) == (2, 1)
    assert block["stops"]["sum_r"] == block["stops"]["settled_sum_r"] == {
        "booked": None, "at_close": None, "at_low": None}
    assert any("ended on a stop whose bars are not carried here" in s for s in block["sentences"])
    assert not any("Under those readings" in s for s in block["sentences"])
    # the $30,000 era has two settled tickets with dollars and one without: its dollars are not said
    era = block["eras"][-1]
    assert (era["settled"], era["model_usd"], era["model_usd_missing"]) == (3, -60.15, 1)
    assert any("$30,000 at 0.5% risk (12 tickets, 3 settled, -3.00R)" in s for s in block["sentences"])
    assert not any("-$60.15" in s for s in block["sentences"])


def test_offline_counts_an_uncertain_ticket_without_bars_and_bounds_nothing_for_it(tmp_path):
    """MCS without its bars is still the ledger's uncertain ticket: counted,
    said, and given no bound, because there is nothing to walk."""
    offline_docs(tmp_path, drop=("MCS",))
    block = model_record.offline(tmp_path)
    assert block["status"] == model_record.COMPUTED, block["reason"]
    mcs = row_of(block, "MCS")
    assert (mcs["bucket"], mcs["uncertainty"], mcs["bars"]) == ("uncertain", "open_above_limit", "not_carried")
    assert block["uncertain"] == {"label": model_record.UNCERTAIN_LABEL, "count": 1, "unexamined": 1, "rows": []}
    assert ("1 ticket is uncertain: the bars cannot say whether it filled, and it is in no sum."
            in block["sentences"])


def test_offline_claims_no_walk_over_bars_that_are_only_partly_carried(tmp_path):
    """EXEL's last session is gone from the block and the four before it are
    there: what those four would walk to is not the ticket's walk, so the row
    is the ledger's and carries no fill, no entry, no sale and no dollars."""
    fixture = offline_docs(tmp_path, without={"EXEL": {"2026-11-03"}})
    exel_pick = next(p for p in fixture["picks"] if p["ticker"] == "EXEL")
    rows = [r for r in fixture["bars"]["EXEL"]["rows"] if r["date"] != "2026-11-03"]
    partial = model_record.measure(exel_pick, {"EXEL": frame(*[(r["date"], r["o"], r["h"], r["l"], r["c"])
                                                               for r in rows])},
                                   {intraday.key(exel_pick): fixture["minutes"][intraday.key(exel_pick)]},
                                   "2026-11-17")
    # the four bars alone do walk to a fill: that is the walk the row must not carry
    assert partial["filled"] and partial["walk"] is not None and not partial["complete"]
    block = model_record.offline(tmp_path)
    assert block["status"] == model_record.COMPUTED, block["reason"]
    exel = row_of(block, "EXEL")
    assert (exel["bucket"], exel["r"], exel["bars"], exel["through"]) == ("settled", 3.02, "not_carried", "2026-11-03")
    assert (exel["fill"], exel["entry"], exel["exit_price"], exel["sales"], exel["model_usd"]) == (
        None, None, None, [], None)
    assert exel["minute_fill"] is True
    # neither one-share ticket can be walked again: no reading and no sum
    assert block["one_share"]["rows"] == []
    assert (block["one_share"]["unexamined"], block["one_share"]["settled_sum_r"]) == (2, None)
    assert block["model_usd_missing"] == 2


def test_offline_holds_a_walked_ticket_to_the_ledgers_row(tmp_path):
    def other(rows):
        next(r for r in rows if r["ticker"] == "HQY")["r"] = -1.2
    offline_docs(tmp_path, change=other)
    block = model_record.offline(tmp_path)
    assert block["status"] == model_record.UNRECONCILED
    assert "HQY 2026-11-04 reads settled at R -1.0 here and settled at R -1.2" in block["reason"]


def test_offline_without_the_publications_ledger_entry_does_not_reconcile(tmp_path):
    offline_docs(tmp_path, ledger_rows=False)
    block = model_record.offline(tmp_path)
    assert block["status"] == model_record.UNRECONCILED and "has no scorecard row" in block["reason"]
    # with no row to take, a ticket whose bars are gone is unmeasured and still marked as not carried
    gone = [p for p in block["plans"] if p["bars"] == "not_carried"]
    assert sorted(p["ticker"] for p in gone) == ["MG", "SN", "ZIM"]
    assert {p["bucket"] for p in gone} == {"unmeasured"}


def test_the_recorded_rows_are_only_the_entry_filed_under_these_bytes(tmp_path):
    raw = b'{"run": {"session": "2026-03-02"}}\n'
    name = hashlib.sha256(raw).hexdigest()
    rows = [{"ticker": "AAA", "kind": "burst", "picked": S[0], "bucket": "settled", "r": 1.0}]
    path = tmp_path / quality_ledger.DIRECTORY / (name + ".json.gz")
    assert model_record.recorded_rows(tmp_path, raw) is None                     # no entry
    write_ledger(tmp_path, [ledger_entry(name, S[0], "2026-03-03T02:00:00+00:00", outcome={"rows": rows + ["x", {}]})])
    assert model_record.recorded_rows(tmp_path, raw) == rows                     # the rows that are rows
    assert model_record.recorded_rows(tmp_path, raw + b" ") is None              # other bytes, other entry
    for entry in (ledger_entry("0" * 64, S[0], "2026-03-03T02:00:00+00:00", outcome={"rows": rows}),
                  ledger_entry(name, S[0], "2026-03-03T02:00:00+00:00", outcome={"rows": "none"})):
        path.write_bytes(gzip.compress(quality_ledger.encoded(entry)))
        assert model_record.recorded_rows(tmp_path, raw) is None                 # another's entry; no rows
    path.write_bytes(gzip.compress(b"{cut"))
    assert model_record.recorded_rows(tmp_path, raw) is None


def test_offline_with_picks_it_cannot_read_counts_none_and_does_not_reconcile(tmp_path):
    offline_docs(tmp_path)
    (tmp_path / "picks.json").write_text("{cut")
    block = model_record.offline(tmp_path)
    assert (block["status"], block["tickets"]) == (model_record.UNRECONCILED, 0)
    assert "22 scorecard rows have no ticket here" in block["reason"]


def test_the_command_prints_the_record_and_exits_by_its_status(tmp_path, capsys):
    offline_docs(tmp_path)
    assert model_record.main(["--docs", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "2026-11-04 HQY" in out and "[bars not carried]" in out and "22 tickets" in out
    assert model_record.main(["--docs", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["distinct_setups"] == 17
    assert model_record.main(["--docs", str(tmp_path / "nowhere")]) == 2
    assert "could not be read" in capsys.readouterr().err
    for path in (tmp_path / quality_ledger.DIRECTORY).iterdir():
        path.unlink()                                        # without its ledger entry the block does not reconcile
    assert model_record.main(["--docs", str(tmp_path)]) == 1
    assert "do not reconcile" in capsys.readouterr().out


def test_frames_from_observations_are_one_row_a_date_and_only_whole_bars():
    data = {"observations": {"symbols": {
        "AAA": {"date": S[2], "o": 3.0, "h": 4.0, "l": 2.0, "c": 3.5, "history": [
            {"date": S[2], "o": 9.0, "h": 9.0, "l": 9.0, "c": 9.0},
            {"date": S[1], "o": 1.0, "h": 2.0, "l": 0.5, "c": 1.5},
            {"date": S[0], "o": 1.0, "h": None, "l": 0.5, "c": 1.5}, "junk"]},
        "BBB": "junk"}}}
    frames = model_record.frames_from_observations(data, {"AAA", "BBB", "CCC"})
    assert list(frames) == ["AAA"]
    assert [str(d.date()) for d in frames["AAA"].index] == [S[1], S[2]]
    assert list(frames["AAA"]["Close"]) == [1.5, 3.5]         # the newest bar stands over its history copy
    assert model_record.frames_from_observations({}, {"AAA"}) == {}
