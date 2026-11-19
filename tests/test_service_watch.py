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


@pytest.mark.parametrize("now,alert", [
    (LIMIT, True),
    (LIMIT + timedelta(hours=sw.MISSING_ALERT_HOURS) - SECOND, True),
    (LIMIT + timedelta(hours=sw.MISSING_ALERT_HOURS), False),      # said once, then left until the record changes
    (LIMIT + timedelta(days=3), False),
])
def test_a_missing_publication_is_flagged_for_a_bounded_time(record, now, alert):
    out = sw.evening(record, now)
    assert (out["state"], out["judgement"], out["alert"]) == ("missing", sw.MISSING, alert)
    assert out["action"] == sw.MISSING_HINT
    assert "was not published" in out["sentence"] and "still covers 2026-09-10" in out["sentence"]
    assert out["hours_to_limit"] <= 0


def test_a_record_that_cannot_say_answers_unknown_and_flags_nothing(record):
    bare = copy.deepcopy(record)
    del bare["run"]["calendar"]
    out = sw.evening(bare, LIMIT - SECOND)
    assert (out["state"], out["judgement"], out["alert"], out["hours_to_limit"]) == ("unknown", sw.UNKNOWN, False, None)
    assert "research only" in out["sentence"]


# ---------------------------------------------------------------- morning ---
def test_the_morning_check_is_not_judged_before_its_window_closes(record):
    raw = encode(record)
    out = sw.morning(record, raw, None, "morning.json is not a regular file", CUTOFF - SECOND)
    assert (out["judgement"], out["alert"], out["receipt"]) == (sw.NOT_DUE, False, None)


@pytest.mark.parametrize("generated", [COLLECT, COLLECT + timedelta(minutes=22), CUTOFF])
def test_a_check_bound_to_this_record_inside_its_window_has_landed(record, generated):
    raw = encode(record)
    out = sw.morning(record, raw, receipt(raw, generated), None, CUTOFF)
    assert (out["judgement"], out["alert"], out["action"]) == (sw.LANDED, False, None)
    assert out["receipt"] == {"generated_at": generated.isoformat(), "status": "observed", "bound_to_this_record": True}
    assert "landed inside its collection window" in out["sentence"]


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
    (CUTOFF + timedelta(hours=sw.MORNING_ALERT_HOURS) - SECOND, True),
    (CUTOFF + timedelta(hours=sw.MORNING_ALERT_HOURS), False),
])
def test_a_check_that_did_not_land_is_flagged_for_a_bounded_time(record, now, alert):
    raw = encode(record)
    out = sw.morning(record, raw, None, "morning.json is not a regular file", now)
    assert (out["judgement"], out["alert"]) == (sw.NOT_LANDED, alert)


@pytest.mark.parametrize("stages,count,words", [
    ({"reaction": 0, "anticipation": 0}, 0, "the record published 0 tickets."),
    ({"reaction": 2, "anticipation": 1}, 3, "the record published 3 tickets."),
])
def test_a_record_with_no_ticket_is_reported_and_never_flagged(record, stages, count, words):
    changed = copy.deepcopy(record)
    for family, value in stages.items():
        changed["funnel"][family]["stages"]["ticket"] = value
    raw = encode(changed)
    out = sw.morning(changed, raw, None, "morning.json is not a regular file", CUTOFF)
    assert out["tickets"] == count and out["judgement"] == sw.NOT_LANDED and words in out["sentence"]
    assert out["alert"] is (count > 0)


@pytest.mark.parametrize("break_it", [
    lambda r: r.pop("funnel"),
    lambda r: r["funnel"].__setitem__("reaction", []),
    lambda r: r["funnel"]["anticipation"]["stages"].__setitem__("ticket", True),
    lambda r: r["funnel"]["reaction"]["stages"].__setitem__("ticket", -1),
    lambda r: r["funnel"]["reaction"]["stages"].pop("ticket"),
])
def test_a_record_that_does_not_count_its_tickets_is_never_flagged(record, break_it):
    changed = copy.deepcopy(record)
    break_it(changed)
    assert sw.ticket_count(changed) is None
    out = sw.morning(changed, encode(changed), None, "morning.json is not a regular file", CUTOFF)
    assert out["judgement"] == sw.NOT_LANDED and out["alert"] is False
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
    out = sw.watch(docs_with(tmp_path, bare), CUTOFF - SECOND)
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
    assert sw.watch(docs, CUTOFF - SECOND)["exit_code"] == sw.EXIT_OK


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
    assert sw.main(["--docs", str(docs), "--now", (CUTOFF - SECOND).isoformat(), "--mail"]) == sw.EXIT_OK
    assert sent == []                                   # nothing to flag: nothing mailed
    capsys.readouterr()


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
