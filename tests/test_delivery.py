"""src.delivery -- where a publication fell against the service's own schedule.

Every instant is pinned; nothing here reads the wall clock. The slots are the
evening workflow's crons as wall clock in the exchange's zone, so the November
change is asserted on both sides of it; the next open crosses a holiday and an
early close; the block is held to its own re-derivation and refused on every
forgery a page would otherwise print.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone

import pytest

from src import delivery, sessions

ET = sessions.MARKET_TZ
RULES = {k.split(".", 1)[1]: v for k, v in delivery.RULES.items()}   # as `rules.pipeline` nests them


def run_for(session: date, published: str) -> dict:
    return {"session": session.isoformat(), "published_at": published, "delivery": delivery.block(session, published)}


# ------------------------------------------------------------------ slots ---

def test_the_slots_are_the_crons_wall_clock_on_both_sides_of_the_november_change():
    # 16 22 * * 1-5 (EDT) and 16 23 * * 1-5 (EST) are one instant, 6:16 PM ET; the retry pair is 8:16 PM ET
    primary, retry = delivery.slots(date(2026, 10, 9))
    assert (primary.isoformat(), retry.isoformat()) == ("2026-10-09T18:16:00-04:00", "2026-10-09T20:16:00-04:00")
    assert (primary.astimezone(timezone.utc).hour, primary.astimezone(timezone.utc).minute) == (22, 16)
    assert (retry.astimezone(timezone.utc).hour, retry.astimezone(timezone.utc).minute) == (0, 16)
    primary, retry = delivery.slots(date(2026, 11, 2))
    assert (primary.isoformat(), retry.isoformat()) == ("2026-11-02T18:16:00-05:00", "2026-11-02T20:16:00-05:00")
    assert (primary.astimezone(timezone.utc).hour, retry.astimezone(timezone.utc).hour) == (23, 1)


def test_the_slot_times_are_archived_as_the_policy_words_the_block_carries():
    assert RULES == {"delivery_version": 1, "delivery_primary_et": "18:16", "delivery_retry_et": "20:16",
                     "delivery_recovery_until": "next_session_open"}
    b = delivery.block(date(2026, 10, 7), "2026-10-08T01:54:00+00:00")
    assert b["policy"] == {"timezone": "America/New_York", "primary_et": "18:16", "retry_et": "20:16", "recovery_until": "next_session_open"}
    assert set(b) == delivery.FIELDS and set(b["policy"]) == delivery.POLICY_FIELDS


# ------------------------------------------------------------------ block ---

def test_the_seventh_of_october_as_it_actually_landed():
    """Session 7 Oct 2026, published 01:54 UTC on the 8th: 9:54 PM ET, 339 minutes
    after the 4:15 PM completion, after both slots, before Thursday's open."""
    b = delivery.block(date(2026, 10, 7), "2026-10-08T01:54:00+00:00")
    assert b["version"] == 1 and b["session"] == "2026-10-07" and b["published_at"] == "2026-10-08T01:54:00+00:00"
    assert b["completion_at"] == "2026-10-07T16:15:00-04:00"
    assert b["latency_minutes"] == 339.0 and b["after_primary_minutes"] == 218.0
    assert b["slot"] == "after_retry"
    assert (b["next_session"], b["next_open_at"], b["before_next_open"]) == ("2026-10-08", "2026-10-08T09:30:00-04:00", True)
    assert b["sentence"] == ("Published 9:54 PM ET on Wed 7 Oct, 339 minutes after the measured session's completion (4:15 PM ET); "
                             "after both scheduled slots (6:16 PM and 8:16 PM ET); before the next session's open (Thu 8 Oct, 9:30 AM ET).")


@pytest.mark.parametrize("published,slot,words", [
    ("2026-10-09T22:15:59+00:00", "before_primary", "before the primary slot (6:16 PM ET)"),
    ("2026-10-09T22:16:00+00:00", "after_primary", "after the primary slot (6:16 PM ET) and before the retry slot (8:16 PM ET)"),
    ("2026-10-10T00:15:59+00:00", "after_primary", "after the primary slot (6:16 PM ET) and before the retry slot (8:16 PM ET)"),
    ("2026-10-10T00:16:00+00:00", "after_retry", "after both scheduled slots (6:16 PM and 8:16 PM ET)"),
], ids=["a-second-before-primary", "at-primary", "a-second-before-retry", "at-retry"])
def test_the_slot_boundaries_are_inclusive_of_the_slot_itself(published, slot, words):
    b = delivery.block(date(2026, 10, 9), published)
    assert b["slot"] == slot and words in b["sentence"]


def test_before_and_after_the_next_open_either_side_of_the_bell():
    friday = date(2026, 10, 9)   # the next session is Monday 12 October, 9:30 AM ET = 13:30 UTC
    before = delivery.block(friday, "2026-10-12T13:29:59+00:00")
    after = delivery.block(friday, "2026-10-12T13:30:00+00:00")
    assert before["before_next_open"] is True and "before the next session's open (Mon 12 Oct, 9:30 AM ET)" in before["sentence"]
    assert after["before_next_open"] is False and "after the next session's open (Mon 12 Oct, 9:30 AM ET)" in after["sentence"]
    assert after["latency_minutes"] - before["latency_minutes"] == pytest.approx(0.0, abs=0.11)   # one second apart, same session


def test_the_next_open_crosses_a_holiday_and_an_early_close_keeps_its_own_completion():
    thanksgiving_eve = delivery.block(date(2026, 11, 25), "2026-11-25T22:00:00+00:00")
    assert (thanksgiving_eve["next_session"], thanksgiving_eve["next_open_at"]) == ("2026-11-27", "2026-11-27T09:30:00-05:00")
    assert thanksgiving_eve["slot"] == "before_primary"   # 5:00 PM ET
    early = delivery.block(date(2026, 11, 27), "2026-11-27T18:30:00+00:00")   # the 1 PM close plus the buffer is 1:15 PM ET
    assert early["completion_at"] == "2026-11-27T13:15:00-05:00" and early["latency_minutes"] == 15.0
    assert early["primary_slot_at"] == "2026-11-27T18:16:00-05:00"   # the cron does not move for a shortened session
    assert "15 minutes after the measured session's completion (1:15 PM ET)" in early["sentence"]


def test_a_publication_ahead_of_its_completion_is_said_so_rather_than_negative():
    b = delivery.block(date(2026, 10, 9), "2026-10-09T20:00:00+00:00")   # 4:00 PM ET, before the 4:15 buffer
    assert b["latency_minutes"] == -15.0
    assert "15 minutes before the measured session's completion (4:15 PM ET)" in b["sentence"]


def test_the_block_refuses_a_non_session_and_an_instant_without_an_offset():
    with pytest.raises(ValueError):
        delivery.block(date(2026, 10, 10), "2026-10-10T22:30:00+00:00")   # a Saturday
    with pytest.raises(ValueError):
        delivery.block(date(2026, 10, 9), "2026-10-09T22:30:00")
    with pytest.raises(ValueError):
        delivery.block(date(2026, 10, 9), "last night")


def test_the_block_under_other_archived_slots_re_derives_under_them():
    b = delivery.block(date(2026, 10, 9), "2026-10-09T22:30:00+00:00", primary_et=time(19, 0), retry_et=time(21, 0))   # 6:30 PM ET
    assert b["slot"] == "before_primary" and b["policy"]["primary_et"] == "19:00" and b["policy"]["retry_et"] == "21:00"
    assert "before the primary slot (7:00 PM ET)" in b["sentence"]


def test_minutes_are_rounded_once_to_a_tenth_and_printed_as_written():
    b = delivery.block(date(2026, 10, 9), "2026-10-09T20:15:30+00:00")   # 30 seconds after completion
    assert b["latency_minutes"] == 0.5 and "0.5 minutes after" in b["sentence"]
    one = delivery.block(date(2026, 10, 9), "2026-10-09T20:16:00+00:00")
    assert one["latency_minutes"] == 1.0 and "1 minute after" in one["sentence"]


# ----------------------------------------------------------------- faults ---

def test_a_record_made_under_rules_without_the_block_is_not_asked_for_one():
    assert delivery.faults({"session": "2026-10-09", "published_at": "2026-10-09T22:30:00+00:00"}, {}) == []
    assert delivery.faults({"session": "2026-10-09"}, None) == []
    assert delivery.faults({"session": "2026-10-09"}, {"stale_tolerance_fraction": 0.01}) == []


def test_the_block_is_required_under_rules_that_write_it_and_held_to_them():
    run = run_for(date(2026, 10, 9), "2026-10-10T01:54:00+00:00")
    assert delivery.faults(run, RULES) == []
    assert delivery.faults({k: v for k, v in run.items() if k != "delivery"}, RULES) == ["run.delivery is missing"]
    assert delivery.faults(dict(run, delivery=None), RULES) == ["run.delivery is missing"]


@pytest.mark.parametrize("forge,says", [
    (lambda b: b.update(latency_minutes=12.0), "latency_minutes"),
    (lambda b: b.update(slot="before_primary"), "slot"),
    (lambda b: b.update(before_next_open=False), "before_next_open"),
    (lambda b: b.update(next_open_at="2026-10-13T09:30:00-04:00", next_session="2026-10-13"), "next_open_at"),
    (lambda b: b.update(published_at="2026-10-09T22:30:00+00:00"), "published_at"),
    (lambda b: b.update(sentence=b["sentence"].replace("339", "39")), "sentence"),
    (lambda b: b.update(completion_at="2026-10-09T16:00:00-04:00"), "completion_at"),
    (lambda b: b.update(primary_slot_at="2026-10-09T19:16:00-04:00"), "primary_slot_at"),
    (lambda b: b["policy"].update(primary_et="19:16"), "policy"),
], ids=["latency", "slot", "before-next-open", "next-open", "published-at", "sentence", "completion", "primary-slot", "policy-slot"])
def test_a_forged_field_is_named(forge, says):
    run = run_for(date(2026, 10, 9), "2026-10-10T01:54:00+00:00")
    forge(run["delivery"])
    faults = delivery.faults(run, RULES)
    assert len(faults) == 1 and faults[0].startswith("run.delivery does not re-derive") and says in faults[0], faults


@pytest.mark.parametrize("forge,says", [
    (lambda b: b.pop("slot"), "malformed"),
    (lambda b: b.update(extra=1), "malformed"),
    (lambda b: b.update(policy=None), "malformed"),
    (lambda b: b["policy"].pop("timezone"), "malformed"),
    (lambda b: b["policy"].update(recovery_until="whenever"), "recovery policy is not the archived one"),
], ids=["field-dropped", "field-added", "policy-dropped", "policy-field-dropped", "policy-unknown"])
def test_a_malformed_block_is_refused_whole(forge, says):
    run = run_for(date(2026, 10, 9), "2026-10-10T01:54:00+00:00")
    forge(run["delivery"])
    faults = delivery.faults(run, RULES)
    assert len(faults) == 1 and says in faults[0], faults
    assert delivery.faults(dict(run, delivery="late"), RULES) == ["run.delivery is malformed"]
    assert delivery.faults(dict(run, delivery=[1, 2]), RULES) == ["run.delivery is malformed"]


def test_the_block_is_held_to_the_slots_the_record_archived_not_the_codes():
    """A record archived under a 7:16 PM slot re-derives under 7:16, and the
    code's own 6:16 would call it forged: the archived rule wins, as the
    tolerance's archived fraction does."""
    archived = dict(RULES, delivery_primary_et="19:16")
    run = {"session": "2026-10-09", "published_at": "2026-10-09T23:00:00+00:00",
           "delivery": delivery.block(date(2026, 10, 9), "2026-10-09T23:00:00+00:00", primary_et=time(19, 16))}
    assert delivery.faults(run, archived) == []
    assert delivery.faults(run, RULES)[0].startswith("run.delivery does not re-derive")
    assert delivery.faults(run_for(date(2026, 10, 9), "2026-10-09T23:00:00+00:00"), archived)[0].startswith("run.delivery does not re-derive")


def test_an_archived_version_this_code_does_not_know_is_named_not_guessed():
    run = run_for(date(2026, 10, 9), "2026-10-10T01:54:00+00:00")
    assert delivery.faults(run, dict(RULES, delivery_version=2)) == ["run.delivery archived version 2 is not one this code re-derives"]


def test_a_run_whose_own_facts_cannot_be_read_is_malformed_not_a_crash():
    run = run_for(date(2026, 10, 9), "2026-10-10T01:54:00+00:00")
    assert delivery.faults(dict(run, session="a Friday"), RULES) == ["run.delivery is malformed"]
    assert delivery.faults(dict(run, published_at=None), RULES) == ["run.delivery is malformed"]
    assert delivery.faults(dict(run, session="2026-10-10"), RULES) == ["run.delivery is malformed"]   # a Saturday
