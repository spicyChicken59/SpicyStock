"""tools/service_watch.py: the two answers, at every boundary, on a record whose
instants are known. The record is the committed page fixture ``full``
(covers Thursday 10 September 2026; the next session is Friday the 11th,
complete 4:15 PM ET, slots 6:16 and 8:16 PM ET, recoverable until Monday the
14th's 9:30 AM ET open; its own plans are for the 11th, window 9:30 to 10:00
AM ET, collection from 9:00). Every clock here is pinned; no test reads the
machine's clock, the network or docs/."""
from __future__ import annotations

import copy
import hashlib
import html
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src import freshness, morning as morning_module, reader
from tools import service_watch as sw

FULL = Path(__file__).parent / "fixtures" / "page" / "full.json"
UTC = timezone.utc
COMPLETION = datetime(2026, 9, 11, 20, 15, tzinfo=UTC)
PRIMARY = datetime(2026, 9, 11, 22, 16, tzinfo=UTC)
RETRY = datetime(2026, 9, 12, 0, 16, tzinfo=UTC)
LIMIT = datetime(2026, 9, 14, 13, 30, tzinfo=UTC)
COLLECT = datetime(2026, 9, 11, 13, 0, tzinfo=UTC)
CUTOFF = datetime(2026, 9, 11, 14, 0, tzinfo=UTC)
DUE = datetime(2026, 9, 11, 13, 45, tzinfo=UTC)               # 8:45 AM CDT, sw.MORNING_DUE_CT
SECOND = timedelta(seconds=1)


@pytest.fixture(scope="module")
def record() -> dict:
    return json.loads(FULL.read_bytes())


def encode(record: dict) -> bytes:
    return json.dumps(record, separators=(",", ":")).encode("utf-8")


def receipt(raw: bytes, generated: datetime, **changes) -> dict:
    """SYNTHETIC morning receipt: only the fields the watch reads."""
    out = {"publication": {"data_sha256": hashlib.sha256(raw).hexdigest()}, "generated_at": generated.isoformat(),
           "status": "observed", "dry_run": False}
    out.update(changes)
    return out


def docs_with(tmp_path: Path, record: dict, morning: dict | None = None) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / sw.DATA_FILE).write_bytes(encode(record))
    if morning is not None:
        (docs / sw.MORNING_FILE).write_text(json.dumps(morning))
    return docs


# ------------------------------------------------------------ the fixture ---
def test_the_fixtures_instants_are_the_ones_these_tests_pin(record):
    expected = freshness.expected(record)
    assert expected["covers_through"] == "2026-09-10" and expected["next_session"] == "2026-09-11"
    assert [datetime.fromisoformat(expected[name]).astimezone(UTC) for name in
            ("completion_at", "primary_slot_at", "retry_slot_at", "recovery_until")] == [COMPLETION, PRIMARY, RETRY, LIMIT]
    window = freshness.morning_window(record)
    assert datetime.fromisoformat(window["collection_starts_at"]).astimezone(UTC) == COLLECT
    assert datetime.fromisoformat(window["window_cutoff_at"]).astimezone(UTC) == CUTOFF
    assert sw.ticket_count(record) == 1


def test_the_watchs_bounds_are_the_modules_own():
    assert sw.MAX_RECORD_BYTES == reader.MAX_PUBLICATION_BYTES
    assert sw.MAX_MORNING_BYTES == morning_module.MAX_OBSERVATION_BYTES
    assert 0 < sw.ALERT_WITHIN_HOURS and 0 < sw.MISSING_ALERT_HOURS and 0 < sw.MORNING_ALERT_HOURS


# ---------------------------------------------------------------- evening ---
@pytest.mark.parametrize("now,state", [
    (COMPLETION - SECOND, "newest"),
    (COMPLETION, "not_due"),
    (PRIMARY, "pending"),
    (RETRY, "late"),
    (LIMIT - timedelta(hours=sw.ALERT_WITHIN_HOURS) - SECOND, "late"),
])
def test_a_publication_that_is_not_yet_near_its_limit_is_never_flagged(record, now, state):
    out = sw.evening(record, now)
    assert (out["state"], out["judgement"], out["alert"], out["action"]) == (state, sw.OK, False, None)
    assert out["next_session"] == "2026-09-11" and out["covers_through"] == "2026-09-10"


@pytest.mark.parametrize("now", [LIMIT - timedelta(hours=sw.ALERT_WITHIN_HOURS), LIMIT - timedelta(hours=1), LIMIT - SECOND])
def test_a_late_publication_is_flagged_once_its_limit_is_near(record, now):
    out = sw.evening(record, now)
    assert (out["state"], out["judgement"], out["alert"]) == ("late", sw.LATE_NEAR_LIMIT, True)
    assert out["action"] == sw.DISPATCH_HINT and "only_if_unpublished" in out["action"]
    assert "2026-09-11 session is not published yet" in out["sentence"]
    assert f"{out['hours_to_limit']:g} hours after this watch's clock" in out["sentence"]
    assert out["hours_to_limit"] == round((LIMIT - now).total_seconds() / 3600, 2)


MONDAY_DONE = datetime(2026, 9, 14, 20, 15, tzinfo=UTC)      # the session after the missed one completes
TUESDAY_OPEN = datetime(2026, 9, 15, 13, 30, tzinfo=UTC)     # and this is its own recovery limit


@pytest.mark.parametrize("now,alert,behind", [
    (LIMIT, True, 1),
    (MONDAY_DONE - SECOND, True, 1),                                  # 6 h 45 min after the limit: still flagged
    (LIMIT + timedelta(hours=sw.MISSING_ALERT_HOURS) - SECOND, True, 2),    # the first night's own twelve hours
])
def test_a_missing_publication_is_flagged_for_a_bounded_time(record, now, alert, behind):
    out = sw.evening(record, now)
    assert (out["state"], out["judgement"], out["alert"]) == ("missing", sw.MISSING, alert)
    assert out["sessions_behind"]["count"] == behind
    assert sw.MISSING_HINT in out["action"]
    assert "was not published" in out["sentence"] and "still covers 2026-09-10" in out["sentence"]
    assert out["hours_to_limit"] <= 0


def test_one_missed_night_goes_quiet_after_its_bound_while_no_later_session_has_completed(record):
    """The fixture's missed session is a Friday: its limit is Monday's open, and until Monday completes the
    record is one session behind. Twelve hours after the limit Monday has completed, so the one-night case is
    held on a schedule whose next session is made to complete later."""
    late = copy.deepcopy(record)
    for row in late["run"]["calendar"]["schedule"]["sessions"]:
        if row["session"] == "2026-09-14":
            row["completion_at"] = "2026-09-15T08:00:00-04:00"     # SYNTHETIC: Monday completes after the bound
    edge = LIMIT + timedelta(hours=sw.MISSING_ALERT_HOURS)
    assert sw.evening(late, edge - SECOND)["alert"] is True
    out = sw.evening(late, edge)
    assert (out["judgement"], out["alert"], out["sessions_behind"]["count"]) == (sw.MISSING, False, 1)
    assert out["action"] == sw.MISSING_HINT
    # on the real schedule Monday HAS completed by then and its own limit is 13 hours off: quiet as well
    real = sw.evening(record, edge)
    assert (real["alert"], real["sessions_behind"]["count"], real["sessions_behind"]["newest"]) == (False, 2, "2026-09-14")


@pytest.mark.parametrize("now,alert", [
    (TUESDAY_OPEN - timedelta(hours=sw.ALERT_WITHIN_HOURS) - SECOND, False),   # Monday may still publish tonight
    (TUESDAY_OPEN - timedelta(hours=sw.ALERT_WITHIN_HOURS), True),             # near ITS limit: a second night
    (TUESDAY_OPEN, True),
    (TUESDAY_OPEN + timedelta(hours=6), True),                                 # missed, inside its twelve hours
    (datetime(2026, 9, 15, 20, 15, 1, tzinfo=UTC), False),                     # Tuesday is done: it is judged now,
])                                                                             # and its own limit is 17 hours off
def test_a_second_missed_night_in_a_row_is_flagged_by_the_first_nights_own_rule(record, now, alert):
    """The record still names the first missed session, so ``missing`` alone would go quiet after twelve hours
    while the service is two sessions behind. The newest completed session is judged too."""
    out = sw.evening(record, now)
    assert (out["judgement"], out["alert"]) == (sw.MISSING, alert)
    assert out["sessions_behind"]["count"] >= 2 and out["sessions_behind"]["newest"] >= "2026-09-14"
    assert "none of them is published" in out["sentence"] and sw.BEHIND_HINT in out["action"]
    # the first night's hint names the first night; the newest is offered what can still publish it
    newest_limit = sw._instant(out["sessions_behind"]["newest_limit"])
    assert f"The first, {out['next_session']}: {sw.MISSING_HINT}" in out["action"]
    can_still = f"The newest, {out['sessions_behind']['newest']}, can still be published: {sw.DISPATCH_HINT}"
    assert (can_still in out["action"]) == (now < newest_limit)


def test_the_missing_hint_does_not_say_nothing_can_publish_the_session():
    assert "Nothing can publish" not in sw.MISSING_HINT
    assert "plain dispatch" in sw.MISSING_HINT and "session box filled still can" in sw.MISSING_HINT


def test_a_record_with_no_readable_delivery_policy_is_flagged_on_its_limit_all_the_same(record):
    """Without ``run.delivery`` freshness answers `pending` until the limit: the alert reads the limit, not the word."""
    bare = copy.deepcopy(record)
    del bare["run"]["delivery"]
    near = LIMIT - timedelta(hours=1)
    out = sw.evening(bare, near)
    assert (out["state"], out["judgement"], out["alert"]) == ("pending", sw.LATE_NEAR_LIMIT, True)
    assert "its publication is still pending" in out["sentence"] and out["action"] == sw.DISPATCH_HINT
    far = sw.evening(bare, LIMIT - timedelta(hours=sw.ALERT_WITHIN_HOURS) - SECOND)
    assert (far["state"], far["judgement"], far["alert"]) == ("pending", sw.OK, False)


def test_a_record_that_cannot_say_answers_unknown_and_flags_nothing(record):
    bare = copy.deepcopy(record)
    del bare["run"]["calendar"]
    out = sw.evening(bare, LIMIT - SECOND)
    assert (out["state"], out["judgement"], out["alert"], out["hours_to_limit"]) == ("unknown", sw.UNKNOWN, False, None)
    assert "research only" in out["sentence"]


# ---------------------------------------------------------------- morning ---
def test_the_morning_check_is_not_judged_before_its_due_time(record):
    raw = encode(record)
    assert sw.morning_due("2026-09-11") == DUE and sw.MORNING_DUE_CT == "08:45"
    assert sw.morning_due("2026-12-15").astimezone(UTC).hour == 14            # 8:45 AM CST
    out = sw.morning(record, raw, None, "morning.json is not a regular file", DUE - SECOND)
    assert (out["judgement"], out["alert"], out["receipt"]) == (sw.NOT_DUE, False, None)
    at = sw.morning(record, raw, None, "morning.json is not a regular file", DUE)
    assert (at["judgement"], at["alert"]) == (sw.NOT_LANDED, True) and at["due_at"] == "2026-09-11T08:45:00-05:00"
    assert "landed by 2026-09-11T08:45:00-05:00" in at["sentence"]


@pytest.mark.parametrize("generated", [COLLECT, COLLECT + timedelta(minutes=22), CUTOFF])
def test_a_check_bound_to_this_record_inside_its_window_has_landed(record, generated):
    raw = encode(record)
    out = sw.morning(record, raw, receipt(raw, generated), None, CUTOFF)
    assert (out["judgement"], out["alert"], out["action"]) == (sw.LANDED, False, None)
    opens = COLLECT + timedelta(minutes=30)
    assert out["receipt"] == {"generated_at": generated.isoformat(), "status": "observed", "bound_to_this_record": True,
                              "same_session_other_publication": False, "before_window_opened": generated < opens,
                              "ticket_rows": 0, "rows_with_recent_price": 0}
    assert "landed inside its collection window" in out["sentence"]


def test_a_check_that_landed_says_when_it_ran_and_how_many_rows_it_priced(record):
    """Every real ticket morning from 3 to 16 November 2026 was a receipt generated before the open with every
    price stale. That is a check that landed and quoted nothing, and the sentence says so; it is not an alert."""
    raw = encode(record)
    stale = {"trade": {"status": "stale"}, "quote": {"status": "stale"}}
    early = receipt(raw, COLLECT + timedelta(minutes=22), status="partial", rows=[stale])
    out = sw.morning(record, raw, early, None, CUTOFF)
    assert (out["judgement"], out["alert"]) == (sw.LANDED, False)
    assert "generated before the entry window opened, and 0 of its 1 ticket row carried a recent price" in out["sentence"]
    priced = receipt(raw, COLLECT + timedelta(minutes=35), rows=[{"trade": {"status": "recent"}, "quote": {"status": "stale"}}, stale])
    out = sw.morning(record, raw, priced, None, CUTOFF)
    assert "generated after the entry window opened, and 1 of its 2 ticket rows carried a recent price" in out["sentence"]


@pytest.mark.parametrize("status", ["provider_unavailable", "inapplicable", "unavailable", None, 7])
def test_a_receipt_that_says_it_quoted_nothing_has_not_landed(record, status):
    raw = encode(record)
    out = sw.morning(record, raw, receipt(raw, COLLECT + timedelta(minutes=22), status=status), None, CUTOFF)
    assert (out["judgement"], out["alert"]) == (sw.NOT_LANDED, True) and "it quoted nothing" in out["sentence"]


def test_the_statuses_that_count_as_a_check_that_ran_are_the_collectors_own():
    from src import morning
    assert set(sw.RAN_STATUSES) < set(morning.STATUSES)
    assert set(morning.STATUSES) - set(sw.RAN_STATUSES) == {"provider_unavailable", "inapplicable"}


def test_a_check_for_an_earlier_publication_of_the_same_session_has_landed(record):
    """The session is published again after the morning: the receipt on disk is bound to the earlier bytes.
    Saying no check landed would be false, and on a ticket night it would mail."""
    raw = encode(record)
    session = sw.freshness.morning_window(record)["applicable_session"]
    earlier = receipt(raw, COLLECT + timedelta(minutes=22),
                      publication={"data_sha256": "0" * 64, "measured_session": record["run"]["session"],
                                   "applicable_session": session})
    out = sw.morning(record, raw, earlier, None, CUTOFF)
    assert (out["judgement"], out["alert"]) == (sw.LANDED, False)
    assert "for an earlier publication of this session" in out["sentence"]
    other = receipt(raw, COLLECT + timedelta(minutes=22),
                    publication={"data_sha256": "0" * 64, "measured_session": "2026-09-09", "applicable_session": session})
    assert sw.morning(record, raw, other, None, CUTOFF)["judgement"] == sw.NOT_LANDED


@pytest.mark.parametrize("change,words", [
    ({"publication": {"data_sha256": "0" * 64}}, "bound to another publication"),
    ({"publication": None}, "bound to another publication"),
    ({"generated_at": (COLLECT - SECOND).isoformat()}, "before the collection window opened"),
    ({"generated_at": (CUTOFF + SECOND).isoformat()}, "after the entry window closed"),
    ({"generated_at": "2026-09-11T13:22:00"}, "names no generation instant"),       # no offset
    ({"generated_at": None}, "names no generation instant"),
    ({"dry_run": True}, "is a rehearsal"),
    ({"dry_run": None}, "is a rehearsal"),
])
def test_a_check_that_is_not_this_records_or_not_in_its_window_has_not_landed(record, change, words):
    raw = encode(record)
    out = sw.morning(record, raw, receipt(raw, COLLECT + timedelta(minutes=22), **change), None, CUTOFF)
    assert out["judgement"] == sw.NOT_LANDED and words in out["sentence"]
    assert "the record published 1 ticket." in out["sentence"]
    assert out["alert"] is True and out["action"] == sw.MORNING_HINT


def test_an_absent_morning_file_has_not_landed_and_says_why(record):
    raw = encode(record)
    out = sw.morning(record, raw, None, "morning.json is not a regular file", CUTOFF)
    assert out["judgement"] == sw.NOT_LANDED and out["receipt"] is None and out["alert"] is True
    assert "morning.json is not a regular file" in out["sentence"]


@pytest.mark.parametrize("now,alert", [
    (DUE + timedelta(hours=sw.MORNING_ALERT_HOURS) - SECOND, True),
    (DUE + timedelta(hours=sw.MORNING_ALERT_HOURS), False),
])
def test_a_check_that_did_not_land_is_flagged_for_a_bounded_time(record, now, alert):
    raw = encode(record)
    out = sw.morning(record, raw, None, "morning.json is not a regular file", now)
    assert (out["judgement"], out["alert"]) == (sw.NOT_LANDED, alert)


@pytest.mark.parametrize("stages,count,words", [
    ({"reaction": 0, "anticipation": 0}, 0, "the record published 0 tickets."),
    ({"reaction": 2, "anticipation": 1}, 3, "the record published 3 tickets."),
])
def test_a_missing_check_is_flagged_with_or_without_a_ticket(record, stages, count, words):
    changed = copy.deepcopy(record)
    for family, value in stages.items():
        changed["funnel"][family]["stages"]["ticket"] = value
    raw = encode(changed)
    out = sw.morning(changed, raw, None, "morning.json is not a regular file", CUTOFF)
    assert out["tickets"] == count and out["judgement"] == sw.NOT_LANDED and words in out["sentence"]
    # every session's morning check is the service's: a record with no ticket still needs one
    assert out["alert"] is True


@pytest.mark.parametrize("break_it", [
    lambda r: r.pop("funnel"),
    lambda r: r["funnel"].__setitem__("reaction", []),
    lambda r: r["funnel"]["anticipation"]["stages"].__setitem__("ticket", True),
    lambda r: r["funnel"]["reaction"]["stages"].__setitem__("ticket", -1),
    lambda r: r["funnel"]["reaction"]["stages"].pop("ticket"),
])
def test_a_record_that_does_not_count_its_tickets_is_flagged_and_says_so(record, break_it):
    changed = copy.deepcopy(record)
    break_it(changed)
    assert sw.ticket_count(changed) is None
    out = sw.morning(changed, encode(changed), None, "morning.json is not a regular file", CUTOFF)
    assert out["judgement"] == sw.NOT_LANDED and out["alert"] is True
    assert "does not say how many tickets it published" in out["sentence"]


def test_a_record_without_an_entry_window_cannot_be_judged(record):
    bare = copy.deepcopy(record)
    del bare["run"]["timing"]
    out = sw.morning(bare, encode(bare), None, None, CUTOFF)
    assert (out["judgement"], out["alert"]) == (sw.UNKNOWN, False) and "cannot be judged" in out["sentence"]


# ------------------------------------------------------------------ watch ---
def test_the_watch_reads_the_two_files_and_combines_the_answers(record, tmp_path):
    raw = encode(record)
    docs = docs_with(tmp_path, record, receipt(raw, COLLECT + timedelta(minutes=22)))
    quiet = sw.watch(docs, CUTOFF + timedelta(hours=1))
    assert quiet["version"] == sw.VERSION and quiet["record_sha256"] == hashlib.sha256(raw).hexdigest()
    assert (quiet["evening"]["judgement"], quiet["morning"]["judgement"]) == (sw.OK, sw.LANDED)
    assert quiet["alert"] is False and quiet["exit_code"] == sw.EXIT_OK
    assert quiet["clock"] == (CUTOFF + timedelta(hours=1)).isoformat()
    near = sw.watch(docs, LIMIT - timedelta(hours=2))
    assert near["evening"]["alert"] is True and near["morning"]["alert"] is False
    assert near["alert"] is True and near["exit_code"] == sw.EXIT_ALERT
    (docs / sw.MORNING_FILE).unlink()
    morning_only = sw.watch(docs, CUTOFF + timedelta(hours=1))
    assert morning_only["evening"]["alert"] is False and morning_only["morning"]["alert"] is True
    assert morning_only["exit_code"] == sw.EXIT_ALERT


def test_an_unknown_evening_is_its_own_exit_code(record, tmp_path):
    bare = copy.deepcopy(record)
    del bare["run"]["calendar"]
    out = sw.watch(docs_with(tmp_path, bare), DUE - SECOND)
    assert out["evening"]["judgement"] == sw.UNKNOWN and out["alert"] is False and out["exit_code"] == sw.EXIT_UNKNOWN


def test_the_watch_refuses_a_clock_without_an_offset_before_it_reads_anything(record, tmp_path):
    with pytest.raises(ValueError, match="the watch needs its clock as an instant with an offset"):
        sw.watch(docs_with(tmp_path, record), datetime(2026, 9, 11, 15, 0))
    # its own refusal, ahead of the files: a directory with no record is never reached
    with pytest.raises(ValueError, match="the watch needs its clock"):
        sw.watch(tmp_path / "absent", datetime(2026, 9, 11, 15, 0))


@pytest.mark.parametrize("content,words", [
    (b"{incomplete", "is not JSON"),
    (b"[]", "is not a JSON object"),
    (b"\xff\xfe", "is not JSON"),
])
def test_a_record_that_is_not_a_json_object_is_named_not_raised(tmp_path, content, words):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / sw.DATA_FILE).write_bytes(content)
    with pytest.raises(sw.Unreadable, match=words):
        sw.watch(docs, CUTOFF)
    assert sw.main(["--docs", str(docs), "--now", CUTOFF.isoformat()]) == sw.EXIT_UNKNOWN


def test_an_absent_linked_or_oversize_record_is_refused(record, tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    with pytest.raises(sw.Unreadable, match="not a regular file"):
        sw.watch(docs, CUTOFF)
    real = tmp_path / "real.json"
    real.write_bytes(encode(record))
    (docs / sw.DATA_FILE).symlink_to(real)
    with pytest.raises(sw.Unreadable, match="not a regular file"):
        sw.watch(docs, CUTOFF)
    (docs / sw.DATA_FILE).unlink()
    (docs / sw.DATA_FILE).write_bytes(encode(record))
    monkeypatch.setattr(sw, "MAX_RECORD_BYTES", len(encode(record)) - 1)
    with pytest.raises(sw.Unreadable, match="over the"):
        sw.watch(docs, CUTOFF)
    monkeypatch.setattr(sw, "MAX_RECORD_BYTES", len(encode(record)))
    assert sw.watch(docs, DUE - SECOND)["exit_code"] == sw.EXIT_OK


def test_an_oversize_morning_file_is_a_check_that_did_not_land(record, tmp_path, monkeypatch):
    raw = encode(record)
    docs = docs_with(tmp_path, record, receipt(raw, COLLECT + timedelta(minutes=22)))
    monkeypatch.setattr(sw, "MAX_MORNING_BYTES", 10)
    out = sw.watch(docs, CUTOFF)
    assert out["morning"]["judgement"] == sw.NOT_LANDED and "over the 10 this watch reads" in out["morning"]["sentence"]


# ------------------------------------------------------- the command, mail ---
def test_the_command_prints_both_answers_and_exits_by_the_judgement(record, tmp_path, capsys):
    raw = encode(record)
    docs = docs_with(tmp_path, record, receipt(raw, COLLECT + timedelta(minutes=22)))
    assert sw.main(["--docs", str(docs), "--now", (CUTOFF + timedelta(hours=1)).isoformat()]) == sw.EXIT_OK
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("Service watch at 2026-09-11T15:00:00+00:00")
    assert out[1].startswith("Evening: ok (newest).") and out[2].startswith("Morning: landed.") and out[-1] == "Nothing to flag."
    assert sw.main(["--docs", str(docs), "--now", (LIMIT - timedelta(hours=2)).isoformat(), "--json"]) == sw.EXIT_ALERT
    printed = json.loads(capsys.readouterr().out)
    assert printed == sw.watch(docs, LIMIT - timedelta(hours=2))
    assert sw.main(["--docs", str(docs), "--now", "2026-09-11T15:00:00"]) == sw.EXIT_UNKNOWN      # no offset
    assert "not an instant with an offset" in capsys.readouterr().err


def test_mail_goes_once_per_alert_through_the_evenings_transport_and_only_when_asked(record, tmp_path, monkeypatch, capsys):
    from src import report
    sent = []
    monkeypatch.setattr(report, "deliver", lambda subject, body, attachments=None: sent.append((subject, body)) or {"id": "x"})
    docs = docs_with(tmp_path, record)                 # no morning file: both answers can alert
    both = (LIMIT - timedelta(hours=2)).isoformat()    # 11:30 UTC Monday: the morning alert window has long passed
    assert sw.main(["--docs", str(docs), "--now", both]) == sw.EXIT_ALERT and sent == []          # not asked
    assert sw.main(["--docs", str(docs), "--now", both, "--mail"]) == sw.EXIT_ALERT
    assert [subject for subject, _ in sent] == ["SpicyStock watch: 2026-09-11 is not published"]
    body = sent[0][1]
    assert "only_if_unpublished" in body and "Watch clock: 2026-09-14T11:30:00+00:00" in body
    assert html.escape(sw.LATE_ITSELF) in body
    assert "<script" not in body and body.startswith("<p>") and body.endswith("</p>")
    sent.clear()
    assert sw.main(["--docs", str(docs), "--now", (CUTOFF + timedelta(hours=1)).isoformat(), "--mail"]) == sw.EXIT_ALERT
    assert [subject for subject, _ in sent] == ["SpicyStock watch: no morning check landed for 2026-09-11"]
    sent.clear()
    assert sw.main(["--docs", str(docs), "--now", (DUE - SECOND).isoformat(), "--mail"]) == sw.EXIT_OK
    assert sent == []                                   # nothing to flag: nothing mailed
    capsys.readouterr()


def test_an_unreadable_record_is_mailed_when_mail_is_asked_for_and_never_otherwise(tmp_path, monkeypatch, capsys):
    """The state in which the site itself can show no record. The run is red either way; with --mail a person
    hears of it, in one message that names the reason and nothing from the file."""
    from src import report
    sent = []
    monkeypatch.setattr(report, "deliver", lambda subject, body, attachments=None: sent.append((subject, body)) or {"id": "x"})
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / sw.DATA_FILE).write_text('{"run": <script>')            # truncated: not JSON
    now = "2026-09-14T11:30:00+00:00"
    assert sw.main(["--docs", str(docs), "--now", now]) == sw.EXIT_UNKNOWN and sent == []
    assert sw.main(["--docs", str(docs), "--now", now, "--mail"]) == sw.EXIT_UNKNOWN
    assert [subject for subject, _ in sent] == [sw.UNREADABLE_SUBJECT]
    body = sent[0][1]
    assert "data.json is not JSON (JSONDecodeError)" in body and "Watch clock: 2026-09-14T11:30:00+00:00" in body
    assert "<script" not in body
    assert "Mailed 1 alert." in capsys.readouterr().err


def test_a_message_escapes_what_it_quotes(record):
    result = {"clock": "2026-09-14T11:30:00+00:00",
              "evening": {"alert": True, "sentence": "a <b>record</b> & its words", "action": None, "next_session": None},
              "morning": {"alert": False, "sentence": None, "action": None, "applicable_session": None}}
    (subject, body), = sw.messages(result)
    assert subject == "SpicyStock watch: the next session is not published"
    assert "a &lt;b&gt;record&lt;/b&gt; &amp; its words" in body and "<b>" not in body


def test_the_log_lines_carry_each_action_under_its_answer(record, tmp_path):
    docs = docs_with(tmp_path, record)
    printed = sw.lines(sw.watch(docs, LIMIT - timedelta(hours=2)))
    assert printed[1].startswith("Evening: late_near_limit (late).") and printed[2] == f"  {sw.DISPATCH_HINT}"
    assert printed[3].startswith("Morning: not_landed.") and printed[-1] == "Alert."


# ------------------------------------------------------------------ start ---
#: the record's own primary slot: the 10 September evening that wrote it
STARTED_SLOT = datetime(2026, 9, 10, 22, 16, tzinfo=UTC)


def late(record, minutes):
    changed = copy.deepcopy(record)
    changed["run"]["delivery"]["after_primary_minutes"] = minutes
    return changed


def test_an_evening_that_started_near_its_slot_is_on_time(record):
    assert sw._instant(record["run"]["delivery"]["primary_slot_at"]) == STARTED_SLOT
    out = sw.start(record, STARTED_SLOT + timedelta(hours=1))
    assert record["run"]["delivery"]["after_primary_minutes"] <= sw.LATE_START_MINUTES
    assert (out["judgement"], out["alert"], out["session"]) == (sw.ON_TIME, False, "2026-09-10")
    assert out["sentence"].startswith("The 2026-09-10 evening run started 14 minutes after its primary slot")


@pytest.mark.parametrize("minutes, judgement", [(sw.LATE_START_MINUTES, sw.ON_TIME), (sw.LATE_START_MINUTES + 0.1, sw.LATE_START),
                                                (298.3, sw.LATE_START)])
def test_an_evening_that_started_more_than_an_hour_late_is_flagged(record, minutes, judgement):
    out = sw.start(late(record, minutes), STARTED_SLOT + timedelta(minutes=minutes, hours=1))
    assert out["judgement"] == judgement and out["alert"] is (judgement == sw.LATE_START)
    if judgement == sw.LATE_START:
        assert f"more than {sw.LATE_START_MINUTES} minutes late" in out["sentence"] and out["action"] == sw.START_HINT


@pytest.mark.parametrize("hours, alert", [(sw.LATE_START_ALERT_HOURS, False), (sw.LATE_START_ALERT_HOURS - 0.01, True)])
def test_a_late_start_is_flagged_for_a_bounded_time(record, hours, alert):
    started = STARTED_SLOT + timedelta(minutes=200)
    out = sw.start(late(record, 200), started + timedelta(hours=hours))
    assert (out["judgement"], out["alert"]) == (sw.LATE_START, alert)


@pytest.mark.parametrize("value", [None, True, "298"])
def test_a_record_without_a_readable_start_says_so_and_flags_nothing(record, value):
    out = sw.start(late(record, value), STARTED_SLOT)
    assert (out["judgement"], out["alert"]) == (sw.UNKNOWN, False)


def test_a_late_start_reaches_the_watchs_exit_code_and_its_mail(record, tmp_path):
    raw = encode(late(record, 298.3))
    changed = json.loads(raw)
    docs = docs_with(tmp_path, changed, receipt(raw, COLLECT + timedelta(minutes=22)))
    out = sw.watch(docs, STARTED_SLOT + timedelta(hours=6))
    assert out["start"]["alert"] is True and out["exit_code"] == sw.EXIT_ALERT
    assert any(subject == "SpicyStock watch: the 2026-09-10 evening run started late" for subject, _ in sw.messages(out))
    assert any(line.startswith("Start: late_start. ") for line in sw.lines(out))
