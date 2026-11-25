"""tools/service_watch.py: every answer, at every boundary, on a record whose
instants are known. The record is the committed page fixture ``full``
(covers Thursday 10 September 2026; the next session is Friday the 11th,
complete 4:15 PM ET, slots 6:16 and 8:16 PM ET, recoverable until Monday the
14th's 9:30 AM ET open; its own plans are for the 11th, window 9:30 to 10:00
AM ET, collection from 9:00). Every clock here is pinned; no test reads the
machine's clock or docs/, and the network is refused: GitHub's run listing is
a double."""
from __future__ import annotations

import copy
import functools
import hashlib
import html
import http.client
import json
import os
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src import freshness, morning as morning_module, orders, reader
from tools import dispatch_schedule as ds
from tools import service_watch as sw

FULL = Path(__file__).parent / "fixtures" / "page" / "full.json"
UTC = timezone.utc
COMPLETION = datetime(2026, 9, 11, 20, 15, tzinfo=UTC)
PRIMARY = datetime(2026, 9, 11, 22, 16, tzinfo=UTC)
RETRY = datetime(2026, 9, 12, 0, 16, tzinfo=UTC)
LIMIT = datetime(2026, 9, 14, 13, 30, tzinfo=UTC)
#: 10 hours after Friday's primary slot: earlier than six hours before Monday's open
NOT_PUBLISHED_FROM = datetime(2026, 9, 12, 8, 16, tzinfo=UTC)
COLLECT = datetime(2026, 9, 11, 13, 0, tzinfo=UTC)
CUTOFF = datetime(2026, 9, 11, 14, 0, tzinfo=UTC)
ALERT = datetime(2026, 9, 11, 13, 25, tzinfo=UTC)             # 8:25 AM CDT, sw.MORNING_ALERT_CT
DUE = datetime(2026, 9, 11, 13, 45, tzinfo=UTC)               # 8:45 AM CDT, sw.MORNING_DUE_CT
SECOND = timedelta(seconds=1)
EVENING_FIRST_SLOT = datetime(2026, 9, 11, 22, 20, tzinfo=UTC)   # the dispatcher's 6:20 PM EDT start
STARTED_BY = datetime(2026, 9, 11, 22, 50, tzinfo=UTC)           # 6:50 PM EDT
PUBLISHED_BY = datetime(2026, 9, 12, 1, 45, tzinfo=UTC)          # 9:45 PM EDT


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """No test here talks to GitHub: a token in this machine's environment is removed, and a request refused."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def refuse(self, method, path, body=None):
        raise AssertionError(f"a test asked GitHub for {method} {path}")
    monkeypatch.setattr(ds.GitHub, "send", refuse)


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


@functools.lru_cache(maxsize=None)
def orders_for(raw: bytes) -> bytes:
    """The real orders.json the evening would write beside these record bytes."""
    return orders.encode(orders.build(raw))


def handoff(raw: bytes, morning: dict | None, *, checked: bool = True) -> dict:
    """orders.json and orders-morning.json beside ``raw``: the morning file is the morning run's own
    (``orders.build_morning()``) for ``morning``, or the evening's pending one."""
    orders_raw = orders_for(raw)
    if morning is not None and checked:
        morning_raw = orders.encode(orders.build_morning(orders_raw, json.dumps(morning).encode()))
    else:
        morning_raw = orders.encode(orders.pending_morning(orders_raw))
    return {"orders_raw": orders_raw, "orders_morning_raw": morning_raw}


def docs_with(tmp_path: Path, record: dict, morning: dict | None = None, *, checked: bool = True,
              handoff_files: bool = True) -> Path:
    """The docs directory the watch reads. A record a test has changed is no longer one ``orders.build()``
    accepts (its provenance no longer holds), so such a test writes no handoff files and stubs that answer."""
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    raw = encode(record)
    (docs / sw.DATA_FILE).write_bytes(raw)
    if morning is not None:
        (docs / sw.MORNING_FILE).write_text(json.dumps(morning))
    if not handoff_files:
        return docs
    files = handoff(raw, morning, checked=checked)
    (docs / orders.FILE).write_bytes(files["orders_raw"])
    template = orders.positions_template(json.loads(files["orders_raw"]), files["orders_raw"])
    (docs / orders.POSITIONS_FILE).write_bytes(orders.encode(template))
    (docs / orders.MORNING_FILE).write_bytes(files["orders_morning_raw"])
    return docs


@pytest.fixture
def bound_handoff(monkeypatch):
    """The handoff answer of a night whose files are bound, for a test about something else."""
    def bound(docs, record, record_raw):
        return {"session": freshness.covers_through(record), "problems": [], "judgement": sw.BOUND, "alert": False,
                "action": None, "key": None, "sentence": "SYNTHETIC: bound."}
    monkeypatch.setattr(sw, "handoff", bound)


def run(**fields) -> dict:
    """SYNTHETIC run as GitHub lists it, cut to ds.RUN_FIELDS."""
    out = {"id": 7001, "event": "schedule", "display_title": "Evening cron 16 22 * * 1-5",
           "created_at": "2026-09-12T03:30:00Z", "status": "completed", "conclusion": "success",
           "head_branch": "main", "run_attempt": 1}
    out.update(fields)
    if isinstance(out["created_at"], datetime):
        out["created_at"] = out["created_at"].astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return out


class Listing:
    """A double of ``ds.GitHub.runs``: the runs given, every workflow, filtered by ``since`` as GitHub filters."""

    def __init__(self, runs: dict[str, list[dict]] | None = None, raises: Exception | None = None):
        self.runs_by = runs or {}
        self.raises = raises
        self.asked: list[tuple[str, datetime]] = []

    def runs(self, workflow, since):
        self.asked.append((workflow, since))
        if self.raises is not None:
            raise self.raises
        return [r for r in self.runs_by.get(workflow, []) if ds._created(r["created_at"]) >= since]


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
    assert sw.not_published_from(record, "2026-09-11", LIMIT) == NOT_PUBLISHED_FROM


def test_the_watchs_bounds_are_the_modules_own():
    assert sw.MAX_RECORD_BYTES == reader.MAX_PUBLICATION_BYTES
    assert sw.MAX_MORNING_BYTES == morning_module.MAX_OBSERVATION_BYTES
    assert 0 < sw.ALERT_WITHIN_HOURS and 0 < sw.MISSING_ALERT_HOURS and 0 < sw.MORNING_ALERT_HOURS
    assert 0 < sw.NOT_PUBLISHED_AFTER_PRIMARY_HOURS and 0 < sw.REPEAT_DAYS
    assert (sw.ORDERS_FILE, sw.ORDERS_MORNING_FILE) == (orders.FILE, orders.MORNING_FILE)


def test_the_watchs_deadlines_are_the_dispatchers_slots():
    """The evening is not started from the dispatcher's first evening start plus its due window; the morning
    is judged at the dispatcher's own watch slot, after its morning start and before the 8:30 AM CT open."""
    evening = next(times for wf, _, zone, times in ds.SLOTS if wf == "evening.yml")
    first = datetime.combine(datetime(2026, 9, 11).date(), datetime.strptime(evening[0], "%H:%M").time())
    assert (first + timedelta(minutes=ds.DUE_MINUTES)).strftime("%H:%M") == sw.EVENING_STARTED_BY_ET
    watch_et = [times for wf, _, zone, times in ds.SLOTS if wf == "service-watch.yml" and zone == ds.ET][0]
    watch_ct = [times for wf, _, zone, times in ds.SLOTS if wf == "service-watch.yml" and zone == ds.CT][0]
    assert watch_et[0] >= sw.EVENING_STARTED_BY_ET and watch_et[-1] >= sw.EVENING_PUBLISHED_BY_ET
    assert sw.EVENING_PUBLISHED_BY_ET > evening[-1]
    assert sw.MORNING_ALERT_CT in watch_ct
    morning_slot = next(times for wf, _, zone, times in ds.SLOTS if wf == "morning.yml")[0]
    gap = (datetime.strptime(sw.MORNING_ALERT_CT, "%H:%M") - datetime.strptime(morning_slot, "%H:%M")).seconds / 60
    assert 4 <= gap and sw.MORNING_ALERT_CT < "08:30" < sw.MORNING_DUE_CT


# ---------------------------------------------------------------- evening ---
@pytest.mark.parametrize("now,state", [
    (COMPLETION - SECOND, "newest"),
    (COMPLETION, "not_due"),
    (PRIMARY, "pending"),
    (RETRY, "late"),
    (NOT_PUBLISHED_FROM - SECOND, "late"),
])
def test_a_publication_that_is_not_yet_due_to_be_flagged_is_never_flagged(record, now, state):
    out = sw.evening(record, now)
    assert (out["state"], out["judgement"], out["alert"], out["action"], out["key"]) == (state, sw.OK, False, None, None)
    assert out["next_session"] == "2026-09-11" and out["covers_through"] == "2026-09-10"


@pytest.mark.parametrize("now", [NOT_PUBLISHED_FROM, LIMIT - timedelta(hours=sw.ALERT_WITHIN_HOURS),
                                 LIMIT - timedelta(hours=1), LIMIT - SECOND])
def test_a_late_publication_is_flagged_from_the_earlier_of_its_two_deadlines(record, now):
    out = sw.evening(record, now)
    assert (out["state"], out["judgement"], out["alert"]) == ("late", sw.NOT_PUBLISHED, True)
    assert out["key"] == "evening:not_published:2026-09-11"
    assert out["action"] == sw.DISPATCH_HINT and "only_if_unpublished" in out["action"]
    assert "2026-09-11 session is not published yet" in out["sentence"]
    assert f"{out['hours_to_limit']:g} hours after this watch's clock" in out["sentence"]
    assert out["hours_to_limit"] == round((LIMIT - now).total_seconds() / 3600, 2)
    assert sw._instant(out["not_published_from"]) == NOT_PUBLISHED_FROM


def test_on_an_ordinary_night_the_limit_rule_is_the_earlier_deadline(record):
    """Six hours before a weekday open is earlier than ten hours after the evening's slot."""
    primary = datetime(2026, 9, 14, 22, 16, tzinfo=UTC)               # Monday 6:16 PM EDT
    tuesday_open = datetime(2026, 9, 15, 13, 30, tzinfo=UTC)
    assert sw.not_published_from(record, "2026-09-14", tuesday_open) == tuesday_open - timedelta(hours=6)
    assert tuesday_open - timedelta(hours=6) < primary + timedelta(hours=sw.NOT_PUBLISHED_AFTER_PRIMARY_HOURS)
    # with no readable policy there is no primary slot: the limit rule alone
    bare = copy.deepcopy(record)
    del bare["run"]["delivery"]
    assert sw.not_published_from(bare, "2026-09-11", LIMIT) == LIMIT - timedelta(hours=sw.ALERT_WITHIN_HOURS)
    assert sw.not_published_from(bare, "2026-09-11", None) is None


def test_an_on_time_start_that_did_not_publish_is_flagged_at_quarter_to_ten(record):
    assert sw.evening(record, PUBLISHED_BY - SECOND, on_time_start=True)["judgement"] == sw.OK
    out = sw.evening(record, PUBLISHED_BY, on_time_start=True)
    assert (out["judgement"], out["alert"], out["key"]) == (sw.NOT_PUBLISHED, True, "evening:not_published:2026-09-11")
    assert "a dispatch in the dispatcher's first evening slot started its evening, and it was still not on main at" in out["sentence"]
    # without an on-time start listed, 9:45 PM ET says nothing: the run may have been started late
    quiet = sw.evening(record, PUBLISHED_BY)
    assert (quiet["judgement"], quiet["alert"], quiet["published_by"]) == (sw.OK, False, None)


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
    assert out["key"] == "evening:missing:2026-09-11"
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
    assert (out["judgement"], out["alert"], out["sessions_behind"]["count"], out["key"]) == (sw.MISSING, False, 1, None)
    assert out["action"] == sw.MISSING_HINT
    # on the real schedule Monday HAS completed by then and its own limit is 13 hours off: quiet as well
    real = sw.evening(record, edge)
    assert (real["alert"], real["sessions_behind"]["count"], real["sessions_behind"]["newest"]) == (False, 2, "2026-09-14")


@pytest.mark.parametrize("now,alert,key", [
    (TUESDAY_OPEN - timedelta(hours=sw.ALERT_WITHIN_HOURS) - SECOND, False, None),   # Monday may still publish
    (TUESDAY_OPEN - timedelta(hours=sw.ALERT_WITHIN_HOURS), True, "evening:not_published:2026-09-14"),
    (TUESDAY_OPEN, True, "evening:missing:2026-09-14"),
    (TUESDAY_OPEN + timedelta(hours=6), True, "evening:missing:2026-09-14"),       # inside its twelve hours
    (datetime(2026, 9, 15, 20, 15, 1, tzinfo=UTC), False, None),                   # Tuesday is done: it is judged now,
])                                                                                 # and its own limit is 17 hours off
def test_a_second_missed_night_in_a_row_is_flagged_by_the_first_nights_own_rule_under_its_own_key(record, now, alert,
                                                                                                    key):
    """The record still names the first missed session, so ``missing`` alone would go quiet after twelve hours
    while the service is two sessions behind. The newest completed session is judged too, under its own key."""
    out = sw.evening(record, now)
    assert (out["judgement"], out["alert"], out["key"]) == (sw.MISSING, alert, key)
    assert out["sessions_behind"]["count"] >= 2 and out["sessions_behind"]["newest"] >= "2026-09-14"
    assert "none of them is published" in out["sentence"] and sw.BEHIND_HINT in out["action"]
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
    assert (out["state"], out["judgement"], out["alert"]) == ("pending", sw.NOT_PUBLISHED, True)
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
def test_the_morning_check_is_judged_from_its_alert_time_and_keeps_its_answer_through_the_gates_line(record):
    raw = encode(record)
    files = handoff(raw, None)
    assert sw.morning_alert("2026-09-11") == ALERT and sw.MORNING_ALERT_CT == "08:25"
    assert sw.morning_due("2026-09-11") == DUE and sw.MORNING_DUE_CT == "08:45"
    assert sw.morning_alert("2026-12-15").astimezone(UTC).strftime("%H:%M") == "14:25"     # 8:25 AM CST
    out = sw.morning(record, raw, None, "morning.json is not a regular file", ALERT - SECOND, **files)
    assert (out["judgement"], out["alert"], out["receipt"], out["key"]) == (sw.NOT_DUE, False, None, None)
    at = sw.morning(record, raw, None, "morning.json is not a regular file", ALERT, **files)
    assert (at["judgement"], at["alert"], at["key"]) == (sw.NOT_LANDED, True, "morning:not_landed:2026-09-11")
    assert at["alert_at"] == "2026-09-11T08:25:00-05:00" and "landed by 2026-09-11T08:25:00-05:00" in at["sentence"]
    later = sw.morning(record, raw, None, "morning.json is not a regular file", DUE, **files)
    assert (later["judgement"], later["key"]) == (at["judgement"], at["key"])         # the same key: nothing more
    assert later["due_at"] == "2026-09-11T08:45:00-05:00" and "landed by 2026-09-11T08:45:00-05:00" in later["sentence"]


@pytest.mark.parametrize("generated", [COLLECT, COLLECT + timedelta(minutes=22), CUTOFF])
def test_a_check_bound_to_this_record_inside_its_window_has_landed(record, generated):
    raw = encode(record)
    seen = receipt(raw, generated)
    out = sw.morning(record, raw, seen, None, CUTOFF, **handoff(raw, seen))
    assert (out["judgement"], out["alert"], out["action"], out["key"]) == (sw.LANDED, False, None, None)
    opens = COLLECT + timedelta(minutes=30)
    assert out["receipt"] == {"generated_at": generated.isoformat(), "status": "observed", "bound_to_this_record": True,
                              "same_session_other_publication": False, "before_window_opened": generated < opens,
                              "ticket_rows": 0, "rows_with_recent_price": 0, "observation_run_id": None}
    assert "landed inside its collection window" in out["sentence"]
    assert "orders-morning.json is checked for this orders.json" in out["sentence"]
    assert out["orders_morning"] == orders.CHECKED


def test_a_check_that_landed_says_when_it_ran_and_how_many_rows_it_priced(record):
    """Every real ticket morning from 3 to 16 November 2026 was a receipt generated before the open with every
    price stale. That is a check that landed and quoted nothing, and the sentence says so; it is not an alert."""
    raw = encode(record)
    stale = {"trade": {"status": "stale"}, "quote": {"status": "stale"}}
    early = receipt(raw, COLLECT + timedelta(minutes=22), status="partial", rows=[stale])
    out = sw.morning(record, raw, early, None, CUTOFF, **handoff(raw, early))
    assert (out["judgement"], out["alert"]) == (sw.LANDED, False)
    assert "generated before the entry window opened, and 0 of its 1 ticket row carried a recent price" in out["sentence"]
    priced = receipt(raw, COLLECT + timedelta(minutes=35), rows=[{"trade": {"status": "recent"}, "quote": {"status": "stale"}}, stale])
    out = sw.morning(record, raw, priced, None, CUTOFF, **handoff(raw, priced))
    assert "generated after the entry window opened, and 1 of its 2 ticket rows carried a recent price" in out["sentence"]


def _broken(raw: bytes, seen: dict, how: str) -> dict:
    files = handoff(raw, seen)
    if how == "absent":
        files["orders_morning_raw"] = None
    elif how == "pending":
        files = handoff(raw, seen, checked=False)
    elif how == "no_check":
        files["orders_morning_raw"] = orders.encode(orders.build_morning(files["orders_raw"], None))
    elif how == "other_orders":
        other = orders_for(raw + b" ")                  # another night's orders.json
        files["orders_morning_raw"] = orders.encode(orders.build_morning(other, json.dumps(seen).encode()))
    elif how == "schema":
        value = json.loads(files["orders_morning_raw"])
        value["status"] = "maybe"
        files["orders_morning_raw"] = json.dumps(value).encode()
    elif how == "earlier":
        value = json.loads(files["orders_morning_raw"])
        value["version"] = 1
        files["orders_morning_raw"] = json.dumps(value).encode()
    elif how == "no_orders":
        files["orders_raw"] = None
    elif how == "unbound_orders":
        files["orders_raw"] = orders_for(raw + b"\n")
    elif how == "unreadable_orders":
        files["orders_raw"] = b"{not json"
    return files


@pytest.mark.parametrize("how,words", [
    ("absent", "there is no orders-morning.json beside orders.json"),
    ("pending", "orders-morning.json says pending: no morning check was applied to these orders"),
    ("no_check", "orders-morning.json says no_check: no morning check was applied to these orders"),
    ("other_orders", "orders-morning.json is bound to another orders.json"),
    ("schema", "orders-morning.json does not meet its schema or hold its hash"),
    ("earlier", "orders-morning.json was written under an earlier version of this code"),
    ("no_orders", "there is no orders.json beside the record"),
    ("unbound_orders", "orders.json is not bound to this record"),
    ("unreadable_orders", "orders.json cannot be read"),
])
def test_a_receipt_that_landed_without_a_checked_orders_morning_is_not_checked(record, how, words):
    raw = encode(record)
    seen = receipt(raw, COLLECT + timedelta(minutes=22))
    out = sw.morning(record, raw, seen, None, ALERT, **_broken(raw, seen, how))
    assert (out["judgement"], out["alert"], out["key"]) == (sw.NOT_CHECKED, True, "morning:not_checked:2026-09-11")
    assert words in out["sentence"] and out["orders_morning"] == words
    assert out["action"] == sw.NOT_CHECKED_HINT
    assert "landed inside its collection window" in out["sentence"] and "by 2026-09-11T08:25:00-05:00" in out["sentence"]
    assert sw.morning(record, raw, seen, None, ALERT - SECOND, **_broken(raw, seen, how))["judgement"] == sw.NOT_DUE


@pytest.mark.parametrize("status", ["provider_unavailable", "inapplicable", "unavailable", None, 7])
def test_a_receipt_that_says_it_quoted_nothing_has_not_landed(record, status):
    raw = encode(record)
    seen = receipt(raw, COLLECT + timedelta(minutes=22), status=status)
    out = sw.morning(record, raw, seen, None, CUTOFF, **handoff(raw, seen))
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
    out = sw.morning(record, raw, earlier, None, CUTOFF, **handoff(raw, None))
    assert (out["judgement"], out["alert"]) == (sw.LANDED, False)
    assert "for an earlier publication of this session" in out["sentence"]
    other = receipt(raw, COLLECT + timedelta(minutes=22),
                    publication={"data_sha256": "0" * 64, "measured_session": "2026-09-09", "applicable_session": session})
    assert sw.morning(record, raw, other, None, CUTOFF, **handoff(raw, None))["judgement"] == sw.NOT_LANDED


@pytest.mark.parametrize("change", [
    {"dry_run": True}, {"dry_run": None},                                       # a rehearsal
    {"status": "provider_unavailable"}, {"status": "inapplicable"},             # one that quoted nothing
    {"generated_at": (CUTOFF + timedelta(hours=3)).isoformat()},                 # after the entry window
    {"generated_at": (COLLECT - SECOND).isoformat()},                            # before the collection window
    {"applicable": "2026-09-14"},                                               # for another applicable session
], ids=["rehearsal", "dry-run-unsaid", "provider-unavailable", "inapplicable", "after-cutoff", "before-collection",
        "other-applicable"])
def test_a_same_session_check_counts_only_when_it_is_one_that_ran_inside_its_window(record, change):
    """Each guard of the earlier-publication branch, one at a time: a rehearsal, a check that quoted nothing, a
    receipt from outside its window and one for another applicable session never silence the morning alert."""
    raw = encode(record)
    session = sw.freshness.morning_window(record)["applicable_session"]
    change = dict(change)
    applicable = change.pop("applicable", session)
    earlier = receipt(raw, COLLECT + timedelta(minutes=22),
                      publication={"data_sha256": "0" * 64, "measured_session": record["run"]["session"],
                                   "applicable_session": applicable}, **change)
    out = sw.morning(record, raw, earlier, None, CUTOFF, **handoff(raw, None))
    assert (out["judgement"], out["alert"], out["key"]) == (sw.NOT_LANDED, True, "morning:not_landed:2026-09-11")


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
    seen = receipt(raw, COLLECT + timedelta(minutes=22), **change)
    out = sw.morning(record, raw, seen, None, CUTOFF, **handoff(raw, None))
    assert out["judgement"] == sw.NOT_LANDED and words in out["sentence"]
    assert "the record published 1 ticket." in out["sentence"]
    assert out["alert"] is True and out["action"] == sw.MORNING_HINT


def test_an_absent_morning_file_has_not_landed_and_says_why(record):
    raw = encode(record)
    out = sw.morning(record, raw, None, "morning.json is not a regular file", CUTOFF, **handoff(raw, None))
    assert out["judgement"] == sw.NOT_LANDED and out["receipt"] is None and out["alert"] is True
    assert "morning.json is not a regular file" in out["sentence"]


@pytest.mark.parametrize("now,alert", [
    (ALERT + timedelta(hours=sw.MORNING_ALERT_HOURS) - SECOND, True),
    (ALERT + timedelta(hours=sw.MORNING_ALERT_HOURS), False),
])
def test_a_check_that_did_not_land_is_flagged_for_a_bounded_time(record, now, alert):
    raw = encode(record)
    out = sw.morning(record, raw, None, "morning.json is not a regular file", now, **handoff(raw, None))
    assert (out["judgement"], out["alert"], out["key"] is not None) == (sw.NOT_LANDED, alert, alert)


@pytest.mark.parametrize("stages,count,words", [
    ({"reaction": 0, "anticipation": 0}, 0, "the record published 0 tickets."),
    ({"reaction": 2, "anticipation": 1}, 3, "the record published 3 tickets."),
])
def test_a_missing_check_is_flagged_with_or_without_a_ticket(record, stages, count, words):
    changed = copy.deepcopy(record)
    for family, value in stages.items():
        changed["funnel"][family]["stages"]["ticket"] = value
    raw = encode(changed)
    out = sw.morning(changed, raw, None, "morning.json is not a regular file", CUTOFF, **handoff(encode(record), None))
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
    out = sw.morning(changed, encode(changed), None, "morning.json is not a regular file", CUTOFF,
                     orders_raw=None, orders_morning_raw=None)
    assert out["judgement"] == sw.NOT_LANDED and out["alert"] is True
    assert "does not say how many tickets it published" in out["sentence"]


def test_a_record_without_an_entry_window_cannot_be_judged(record):
    bare = copy.deepcopy(record)
    del bare["run"]["timing"]
    out = sw.morning(bare, encode(bare), None, None, CUTOFF, orders_raw=None, orders_morning_raw=None)
    assert (out["judgement"], out["alert"]) == (sw.UNKNOWN, False) and "cannot be judged" in out["sentence"]


# ---------------------------------------------------------------- handoff ---
def test_the_handoff_files_the_evening_writes_are_bound_and_quiet(record, tmp_path):
    docs = docs_with(tmp_path, record)
    out = sw.handoff(docs, record, encode(record))
    assert (out["judgement"], out["alert"], out["problems"], out["key"]) == (sw.BOUND, False, [], None)


def _break_handoff(docs: Path, how: str) -> None:
    if how == "no_orders":
        (docs / orders.FILE).unlink()
    elif how == "linked_orders":
        real = docs.parent / "orders-elsewhere.json"
        real.write_bytes((docs / orders.FILE).read_bytes())
        (docs / orders.FILE).unlink()
        (docs / orders.FILE).symlink_to(real)
    elif how == "unbound":
        (docs / sw.DATA_FILE).write_bytes((docs / sw.DATA_FILE).read_bytes() + b"\n")
    elif how == "no_morning":
        (docs / orders.MORNING_FILE).unlink()
    elif how == "morning_unbound":
        other = orders.encode(orders.pending_morning(orders_for((docs / sw.DATA_FILE).read_bytes() + b" ")))
        (docs / orders.MORNING_FILE).write_bytes(other)
    elif how == "morning_schema":
        (docs / orders.MORNING_FILE).write_text('{"version": 6, "kind": "orders_morning"}')
    elif how == "positions_unbound":
        other = orders_for((docs / sw.DATA_FILE).read_bytes() + b" ")
        (docs / orders.POSITIONS_FILE).write_bytes(
            orders.encode(orders.positions_template(json.loads(other), other)))
    elif how == "orders_schema":
        (docs / orders.FILE).write_text('{"version": 6}')


@pytest.mark.parametrize("how,phrase", [
    ("no_orders", sw.HANDOFF_MISSING),
    ("linked_orders", sw.HANDOFF_MISSING),
    ("unbound", "orders.json is not bound to data.json"),
    ("no_morning", "orders-morning.json is missing beside orders.json: every ticket is cancelled until it is written"),
    ("morning_unbound", "orders-morning.json is not bound to orders.json"),
    ("morning_schema", "orders-morning.json cannot be read or does not meet its schema"),
    ("positions_unbound", "positions-template.json is not bound to orders.json"),
    ("orders_schema", "orders.json cannot be read or does not meet its schema"),
])
def test_each_handoff_problem_is_a_fixed_phrase_with_no_path_or_exception_text(record, tmp_path, how, phrase):
    docs = docs_with(tmp_path, record)
    _break_handoff(docs, how)
    data = json.loads((docs / sw.DATA_FILE).read_bytes())
    out = sw.handoff(docs, data, (docs / sw.DATA_FILE).read_bytes())
    assert out["judgement"] == sw.UNBOUND and out["alert"] is True and phrase in out["problems"]
    assert out["key"] == "handoff:unbound:2026-09-10" and out["action"] == sw.HANDOFF_HINT
    for text in out["problems"] + [out["sentence"]]:
        assert str(tmp_path) not in text and "/" not in text and "Errno" not in text and "Error" not in text
        assert text == sw.HANDOFF_MISSING or text == sw.HANDOFF_UNCHECKABLE or text in sw.HANDOFF_PHRASES \
            or text.endswith("cannot be read or does not meet its schema") or text == out["sentence"]


def test_the_fixed_phrases_are_the_ones_orders_check_writes():
    """Every phrase the watch passes through verbatim is a sentence src/orders.check() can return: written out
    in its source, or as its f-string over the one file name it names."""
    source = Path(orders.__file__).read_text()
    for phrase in sw.HANDOFF_PHRASES:
        spellings = {phrase} | {phrase.replace(name, placeholder)
                                for name in (orders.MORNING_FILE, orders.POSITIONS_FILE)
                                for placeholder in ("{MORNING_FILE}", "{name}")}
        assert any(spelling in source for spelling in spellings), phrase


def test_a_morning_file_main_cannot_derive_again_is_said_in_its_own_phrase(record, tmp_path):
    """orders-morning.json checked against one receipt, then main's receipt changed: orders.check()'s own path-free
    sentence passes through, never folded into the schema phrase."""
    raw = encode(record)
    docs = docs_with(tmp_path, record, receipt(raw, COLLECT + timedelta(minutes=22)))
    (docs / sw.MORNING_FILE).write_text(json.dumps(receipt(raw, COLLECT + timedelta(minutes=23))))
    out = sw.handoff(docs, record, raw)
    assert out["problems"] == [f"{orders.MORNING_FILE} is checked against a morning receipt main does not carry"]


def _check_sentences() -> list[tuple[str, bool]]:
    """Every sentence orders.check() and _morning_problems() can write, as (text, names a path or quotes an
    exception), read off the source: a {name} loop is rendered for both companion files."""
    import ast
    tree = ast.parse(Path(orders.__file__).read_text())
    names = {"MORNING_FILE": orders.MORNING_FILE, "POSITIONS_FILE": orders.POSITIONS_FILE, "FILE": orders.FILE}
    out = []

    def render(node, name):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value, False
        text, quotes = "", False
        for part in node.values:
            if isinstance(part, ast.Constant):
                text += part.value
            elif isinstance(part.value, ast.Name) and part.value.id in names:
                text += names[part.value.id]
            elif isinstance(part.value, ast.Name) and part.value.id == "name":
                text += name
            else:
                quotes = True
                text += "{...}"
        return text, quotes
    for function in (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("check", "_morning_problems")):
        for node in ast.walk(function):
            values = []
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "append" and node.args:
                values = [node.args[0]]
            elif isinstance(node, ast.Return) and isinstance(node.value, (ast.List, ast.IfExp)):
                lists = [node.value] if isinstance(node.value, ast.List) else [node.value.body, node.value.orelse]
                values = [element for item in lists if isinstance(item, ast.List) for element in item.elts]
            for value in values:
                if isinstance(value, (ast.Constant, ast.JoinedStr)):
                    for name in (orders.POSITIONS_FILE, orders.MORNING_FILE):
                        out.append(render(value, name))
    return sorted(set(out))


def test_every_sentence_orders_check_writes_is_passed_through_or_named_by_its_file():
    sentences = _check_sentences()
    assert len(sentences) >= 12                                   # the parse found the function's sentences
    for text, quotes in sentences:
        if quotes:
            # one that quotes an exception (a path, a schema's words) is said by the file it names
            assert sw.handoff_phrase(text) in [f"{name} cannot be read or does not meet its schema"
                                               for name in (orders.FILE, orders.POSITIONS_FILE, orders.MORNING_FILE)], text
        else:
            assert sw.handoff_phrase(text) == text and text in sw.HANDOFF_PHRASES, text


def test_a_check_that_raises_is_a_check_that_could_not_be_made(record, tmp_path, monkeypatch):
    docs = docs_with(tmp_path, record)

    def raises(_docs):
        raise OSError("/somewhere/private: permission denied")
    monkeypatch.setattr(orders, "check", raises)
    out = sw.handoff(docs, record, encode(record))
    assert out["problems"] == [sw.HANDOFF_UNCHECKABLE] and "private" not in out["sentence"]
    assert sw.handoff_phrase("something new: /a/b") == sw.HANDOFF_UNCHECKABLE


# -------------------------------------------------------------- scheduler ---
def evening_run(created, **fields) -> dict:
    return run(created_at=created, **fields)


DISPATCH = {"event": "workflow_dispatch", "display_title": sw.EVENING_DISPATCH_TITLE}


@pytest.mark.parametrize("runs,now,judgement,key", [
    ([], STARTED_BY - SECOND, sw.NOT_DUE, None),                                  # none, before its deadline
    ([], STARTED_BY, sw.NOT_STARTED, "evening:not_started:2026-09-11"),           # none, at it
    ([evening_run(datetime(2026, 9, 12, 3, 30, tzinfo=UTC))], RETRY + timedelta(hours=4), sw.STARTED_LATE,
     "scheduler:evening:started_late"),                                            # the backup cron only
    ([evening_run(EVENING_FIRST_SLOT + timedelta(minutes=1), **DISPATCH)], STARTED_BY, sw.ON_TIME, None),
    ([evening_run(EVENING_FIRST_SLOT, **DISPATCH)], STARTED_BY, sw.ON_TIME, None),           # at the slot
    ([evening_run(EVENING_FIRST_SLOT + timedelta(minutes=ds.DUE_MINUTES) - SECOND, **DISPATCH)], STARTED_BY,
     sw.ON_TIME, None),                                                            # the last second of its window
    ([evening_run(EVENING_FIRST_SLOT + timedelta(minutes=ds.DUE_MINUTES), **DISPATCH)], STARTED_BY + SECOND,
     sw.STARTED_LATE, "scheduler:evening:started_late"),                           # exactly at the due bound
    ([evening_run(EVENING_FIRST_SLOT + timedelta(minutes=1), event="workflow_dispatch",
                  display_title="Evening dispatch")], STARTED_BY, sw.STARTED_LATE,
     "scheduler:evening:started_late"),                                            # a hand dispatch is not the dispatcher's
    ([evening_run(EVENING_FIRST_SLOT + timedelta(minutes=1), event="workflow_dispatch",
                  display_title=sw.EVENING_REHEARSAL_TITLE)], STARTED_BY, sw.NOT_STARTED,
     "evening:not_started:2026-09-11"),                                            # a rehearsal is ignored
    ([evening_run(EVENING_FIRST_SLOT + timedelta(minutes=1), event="workflow_dispatch",
                  display_title="Evening backfill 2026-09-09")], STARTED_BY, sw.NOT_STARTED,
     "evening:not_started:2026-09-11"),                                            # so is another session's backfill
    ([evening_run(EVENING_FIRST_SLOT + timedelta(minutes=1), event="workflow_dispatch",
                  display_title="Evening backfill 2026-09-11")], STARTED_BY, sw.STARTED_LATE,
     "scheduler:evening:started_late"),                                            # this session's backfill counts
    ([evening_run(EVENING_FIRST_SLOT + timedelta(minutes=1), head_branch="other", **DISPATCH)], STARTED_BY,
     sw.NOT_STARTED, "evening:not_started:2026-09-11"),                            # another branch is ignored
    ([evening_run(COMPLETION - SECOND, **DISPATCH)], STARTED_BY, sw.NOT_STARTED,
     "evening:not_started:2026-09-11"),                                            # before the session completed
    ([evening_run(EVENING_FIRST_SLOT + timedelta(minutes=1), conclusion="failure", **DISPATCH),
      evening_run(EVENING_FIRST_SLOT + timedelta(hours=1), id=7002, conclusion="cancelled"),
      evening_run(EVENING_FIRST_SLOT + timedelta(hours=2), id=7003, conclusion="timed_out"),
      evening_run(EVENING_FIRST_SLOT + timedelta(hours=3), id=7004, conclusion="startup_failure")],
     RETRY + timedelta(hours=2), sw.FAILED, "evening:failed:2026-09-11"),           # every run failed
    ([evening_run(EVENING_FIRST_SLOT + timedelta(minutes=1), conclusion="startup_failure", **DISPATCH)],
     RETRY, sw.FAILED, "evening:failed:2026-09-11"),                               # a workflow file that will not start
    ([evening_run(COMPLETION, event="workflow_dispatch", display_title="Evening dispatch")], STARTED_BY, sw.STARTED_LATE,
     "scheduler:evening:started_late"),                                            # created at completion: listed
    ([evening_run(EVENING_FIRST_SLOT + timedelta(minutes=1), conclusion="failure", **DISPATCH),
      evening_run(EVENING_FIRST_SLOT + timedelta(hours=1), id=7002, status="in_progress", conclusion=None)],
     RETRY, sw.ON_TIME, None),                                                     # one still in progress
    ([evening_run(EVENING_FIRST_SLOT + timedelta(minutes=1), conclusion="failure", **DISPATCH),
      evening_run(EVENING_FIRST_SLOT + timedelta(hours=1), id=7002, status="in_progress", conclusion="failure",
                  run_attempt=2)],
     RETRY, sw.ON_TIME, None),     # SYNTHETIC: a re-run in progress that still carries its first attempt's ending
])
def test_the_evenings_scheduler_answer_for_an_unpublished_session(record, runs, now, judgement, key):
    out = sw.judge_evening(record, now, runs, None)
    assert (out["about"], out["session"], out["judgement"], out["key"]) == ("session", "2026-09-11", judgement, key)
    assert out["alert"] is (key is not None)
    assert out["first_slot_at"] == "2026-09-11T18:20:00-04:00" and out["started_by_at"] == "2026-09-11T18:50:00-04:00"
    if judgement == sw.ON_TIME:
        assert out["on_time_run"] == runs[0]["id"]


def test_an_unreadable_listing_leaves_the_evenings_own_block_unknown_and_quiet(record):
    out = sw.judge_evening(record, RETRY, None, "the run listing answered HTTP 403")
    assert (out["judgement"], out["alert"], out["key"]) == (sw.UNKNOWN, False, None)
    assert "HTTP 403" in out["sentence"]


def test_the_session_is_judged_from_its_own_primary_slot(record):
    """evening_target(): the session's primary slot itself is in; one second before it is not."""
    assert sw.evening_target(record, PRIMARY - SECOND) is None
    assert sw.evening_target(record, PRIMARY)["session"] == "2026-09-11"
    assert sw.evening_target(record, LIMIT - SECOND)["session"] == "2026-09-11"
    assert sw.evening_target(record, LIMIT) is None


#: The guard skips a cron that is not the active UTC slot for the date's offset: 11 September is EDT, so the
#: EST pair (16 23, 16 1) fires and does nothing; in December the EDT pair (16 22, 16 0) does.
@pytest.mark.parametrize("cron,created,skipped", [
    ("16 22 * * 1-5", datetime(2026, 9, 11, 22, 16, 30, tzinfo=UTC), False),       # EDT primary in EDT
    ("16 23 * * 1-5", datetime(2026, 9, 11, 23, 16, 30, tzinfo=UTC), True),        # EST primary in EDT
    ("16 0 * * 2-6", datetime(2026, 9, 12, 0, 16, 30, tzinfo=UTC), False),         # EDT retry in EDT
    ("16 1 * * 2-6", datetime(2026, 9, 12, 1, 16, 30, tzinfo=UTC), True),          # EST retry in EDT
    ("16 23 * * 1-5", datetime(2026, 9, 12, 5, 0, tzinfo=UTC), True),              # hours late: still its slot's
    ("16 22 * * 1-5", datetime(2026, 12, 4, 22, 16, 30, tzinfo=UTC), True),        # EDT primary in EST
    ("16 23 * * 1-5", datetime(2026, 12, 4, 23, 16, 30, tzinfo=UTC), False),       # EST primary in EST
    ("16 0 * * 2-6", datetime(2026, 12, 5, 0, 16, 30, tzinfo=UTC), True),          # EDT retry in EST
    ("16 1 * * 2-6", datetime(2026, 12, 5, 1, 16, 30, tzinfo=UTC), False),         # EST retry in EST
    ("16 23 * * 1-5", datetime(2026, 12, 5, 6, 0, tzinfo=UTC), False),             # hours late, in season
    ("7 22 * * 1-5", datetime(2026, 9, 11, 22, 7, tzinfo=UTC), True),              # a cron the guard does not know
])
def test_an_evening_cron_its_guard_skips_is_read_off_its_title_and_creation(cron, created, skipped):
    assert sw.skipped_evening_cron(run(display_title=f"Evening cron {cron}", created_at=created)) is skipped
    # a dispatch, or a scheduled run of another workflow, is never one
    assert sw.skipped_evening_cron(run(display_title=f"Evening cron {cron}", created_at=created,
                                       event="workflow_dispatch")) is False
    assert sw.skipped_evening_cron(run(display_title=f"Morning cron {cron}", created_at=created)) is False


def test_the_skipped_crons_are_the_evening_guards_own_table():
    """EVENING_CRONS is evening.yml's guard, entry for entry, and its keys are the workflow's crons."""
    import re as regex
    import yaml
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github" / "workflows" / "evening.yml").read_text())
    crons = [c["cron"] for c in (workflow.get("on") or workflow.get(True))["schedule"]]
    assert sorted(crons) == sorted(sw.EVENING_CRONS)
    guard = next(step["run"] for step in workflow["jobs"]["scan"]["steps"] if step.get("id") == "guard")
    table = dict((cron, (int(hour), offset, range(int(a), int(b)))) for cron, hour, offset, a, b in regex.findall(
        r"'([0-9 *-]+)': \((\d+), '([+-]\d{4})', range\((\d+), (\d+)\)\)", guard))
    assert table == sw.EVENING_CRONS


SKIP = {"event": "schedule", "display_title": "Evening cron 16 23 * * 1-5"}        # EST primary: skipped in EDT


@pytest.mark.parametrize("runs,now,judgement,key", [
    ([evening_run(datetime(2026, 9, 11, 23, 20, tzinfo=UTC), **SKIP)], datetime(2026, 9, 12, 2, 30, tzinfo=UTC),
     sw.NOT_STARTED, "evening:not_started:2026-09-11"),                            # the skip alone is no run
    ([evening_run(EVENING_FIRST_SLOT + timedelta(minutes=1), conclusion="failure", **DISPATCH),
      evening_run(datetime(2026, 9, 11, 23, 20, tzinfo=UTC), id=7009, **SKIP)],
     datetime(2026, 9, 12, 2, 30, tzinfo=UTC), sw.FAILED, "evening:failed:2026-09-11"),   # it cannot hide a failure
    ([evening_run(datetime(2026, 9, 12, 3, 0, tzinfo=UTC), conclusion="failure"),
      evening_run(datetime(2026, 9, 12, 4, 0, tzinfo=UTC), id=7010, conclusion="failure",
                  display_title="Evening cron 16 0 * * 2-6"),
      evening_run(datetime(2026, 9, 12, 3, 30, tzinfo=UTC), id=7011, **SKIP),
      evening_run(datetime(2026, 9, 12, 4, 30, tzinfo=UTC), id=7012, event="schedule",
                  display_title="Evening cron 16 1 * * 2-6")],
     datetime(2026, 9, 12, 5, 0, tzinfo=UTC), sw.FAILED, "evening:failed:2026-09-11"),     # both off-season skips
])
def test_an_off_season_evening_cron_is_never_an_evening_run(record, runs, now, judgement, key):
    out = sw.judge_evening(record, now, runs, None)
    assert (out["judgement"], out["key"]) == (judgement, key)
    assert all(r["display_title"] not in ("Evening cron 16 23 * * 1-5", "Evening cron 16 1 * * 2-6")
               for r in out["runs"])


LATER = datetime(2026, 9, 11, 23, 20, tzinfo=UTC)                 # the dispatcher's 7:20 PM EDT evening start


@pytest.mark.parametrize("created", [LATER, LATER + timedelta(hours=1), LATER + timedelta(hours=2, minutes=29)])
def test_a_later_slot_of_the_dispatcher_is_named_as_its_own_start_and_is_still_not_on_time(record, created):
    out = sw.judge_evening(record, RETRY + timedelta(hours=1), [evening_run(created, **DISPATCH)], None)
    assert (out["judgement"], out["key"], out["action"]) == (
        sw.STARTED_LATE, "scheduler:evening:started_late", sw.LATER_SLOT_HINT)
    assert "a later slot of the dispatcher's" in out["sentence"] and "not started by" not in out["sentence"]
    subject = sw._alert(out["key"], out["sentence"], out["action"])["subject"]
    assert "dispatcher" not in subject                       # the subject never says the dispatcher did not start it
    # outside every one of the dispatcher's windows: not a dispatch in any of its slots
    off = sw.judge_evening(record, RETRY + timedelta(hours=1), [evening_run(LATER - timedelta(minutes=1), **DISPATCH)],
                           None)
    assert off["action"] == sw.SCHEDULER_HINT and "not started by a dispatch in any of the dispatcher's slots" \
        in off["sentence"]


def test_the_dispatchers_evening_slots_run_to_the_next_open_over_a_weekend():
    friday = sw.dispatcher_evening_slots("2026-09-11", LIMIT)
    assert [at.astimezone(UTC).strftime("%m-%d %H:%M") for at in friday] == [
        "09-11 22:20", "09-11 23:20", "09-12 00:20", "09-12 01:20",        # Friday's own
        "09-12 22:20", "09-12 23:20", "09-13 00:20", "09-13 01:20",        # Saturday's recovery
        "09-13 22:20", "09-13 23:20", "09-14 00:20", "09-14 01:20"]        # Sunday's; Monday's are Monday's own
    assert sw.dispatcher_evening_slots("2026-09-11", None) == friday[:4]
    assert sw.dispatcher_evening_slots("not a date", LIMIT) == [] and sw.dispatcher_evening_slots(None, LIMIT) == []


@pytest.mark.parametrize("created,judgement,later", [
    (datetime(2026, 9, 10, 23, 22, tzinfo=UTC), sw.STARTED_LATE, True),            # its 7:20 PM EDT start
    (datetime(2026, 9, 11, 3, 0, tzinfo=UTC), sw.STARTED_LATE, False),             # GitHub's backup cron
])
def test_the_run_that_wrote_the_record_from_a_later_dispatcher_slot_is_named_so(record, created, judgement, later):
    listed = [run(id=9001, created_at=created, **(DISPATCH if later else {}))]
    out = sw.judge_evening(with_run_id(record), FRIDAY_MORNING, listed, None)
    assert (out["about"], out["judgement"]) == ("record_run", judgement)
    assert ("a later slot of the dispatcher's" in out["sentence"]) is later
    assert out["action"] == (sw.LATER_SLOT_HINT if later else sw.SCHEDULER_HINT)


def test_a_friday_record_written_by_the_saturday_recovery_start_is_the_dispatchers_later_start(record):
    friday = with_run_id(record)
    friday["run"]["session"] = "2026-09-11"
    friday["run"]["delivery"]["completion_at"] = COMPLETION.isoformat()
    saturday = run(id=9001, created_at=datetime(2026, 9, 12, 22, 20, 4, tzinfo=UTC), **DISPATCH)
    out = sw._judge_record_run(friday, datetime(2026, 9, 12, 23, 0, tzinfo=UTC), [saturday], None)
    assert out["judgement"] == sw.STARTED_LATE and "2026-09-12T18:20:00-04:00" in out["sentence"]
    assert "a later slot of the dispatcher's" in out["sentence"]


def with_run_id(record, run_id="9001"):
    changed = copy.deepcopy(record)
    changed["run"]["run_id"] = run_id
    return changed


RECORD_FIRST_SLOT = datetime(2026, 9, 10, 22, 20, tzinfo=UTC)   # the dispatcher's start for the record's own session


FRIDAY_MORNING = datetime(2026, 9, 11, 8, 0, tzinfo=UTC)       # before the next session's primary slot


@pytest.mark.parametrize("listed,now,judgement,alert", [
    ([run(id=9001, created_at=RECORD_FIRST_SLOT + timedelta(minutes=1), **DISPATCH)], FRIDAY_MORNING,
     sw.ON_TIME, False),
    ([run(id=9001, created_at=datetime(2026, 9, 11, 3, 0, tzinfo=UTC))], FRIDAY_MORNING, sw.STARTED_LATE, True),
    ([run(id=9001, created_at=datetime(2026, 9, 11, 3, 0, tzinfo=UTC))],
     datetime(2026, 9, 11, 17, 0, tzinfo=UTC), sw.STARTED_LATE, False),             # at its fourteen hours
    ([run(id=4444, created_at=RECORD_FIRST_SLOT + timedelta(minutes=1), **DISPATCH)], FRIDAY_MORNING,
     sw.UNKNOWN, False),                                                            # its run is not listed
])
def test_the_run_that_wrote_the_record_is_read_off_the_listing_by_its_run_id(record, listed, now, judgement, alert):
    out = sw.judge_evening(with_run_id(record), now, listed, None)
    assert (out["about"], out["session"], out["judgement"], out["alert"]) == ("record_run", "2026-09-10", judgement, alert)
    assert out["key"] == ("scheduler:evening:started_late" if alert else None)
    # the record names no run at all: unknown
    assert sw.judge_evening(record, now, listed, None)["judgement"] == sw.UNKNOWN


MORNING_SLOT = datetime(2026, 9, 11, 13, 20, tzinfo=UTC)        # 8:20 AM CDT


@pytest.mark.parametrize("runs,now,judgement,key", [
    ([], ALERT - SECOND, sw.NOT_DUE, None),
    ([], ALERT, sw.NOT_STARTED, None),                              # folded into the morning's own alert
    ([run(event="workflow_dispatch", display_title=sw.MORNING_DISPATCH_TITLE, created_at=MORNING_SLOT)], ALERT,
     sw.ON_TIME, None),
    ([run(event="schedule", display_title="Morning cron 20 13 * * 1-5",
          created_at=datetime(2026, 9, 11, 18, 0, tzinfo=UTC))], datetime(2026, 9, 11, 18, 5, tzinfo=UTC),
     sw.STARTED_LATE, "scheduler:morning:started_late"),
    ([run(event="workflow_dispatch", display_title=sw.MORNING_REHEARSAL_TITLE, created_at=MORNING_SLOT)], ALERT,
     sw.NOT_STARTED, None),
    ([run(event="workflow_dispatch", display_title=sw.MORNING_DISPATCH_TITLE, created_at=MORNING_SLOT,
          head_branch="other")], ALERT, sw.NOT_STARTED, None),
    ([run(event="workflow_dispatch", display_title=sw.MORNING_DISPATCH_TITLE, created_at=MORNING_SLOT,
          conclusion="failure")], ALERT, sw.FAILED, None),
    ([run(event="workflow_dispatch", display_title=sw.MORNING_DISPATCH_TITLE,
          created_at=MORNING_SLOT + timedelta(minutes=ds.DUE_MINUTES))], CUTOFF, sw.STARTED_LATE,
     "scheduler:morning:started_late"),
])
def test_the_morning_checks_scheduler_answer(record, runs, now, judgement, key):
    raw = encode(record)
    out = sw.judge_morning(record, None, raw, now, runs, None)
    assert (out["session"], out["judgement"], out["key"], out["alert"]) == ("2026-09-11", judgement, key, key is not None)
    assert out["slot_at"] == "2026-09-11T08:20:00-05:00"


def test_a_later_days_morning_run_is_not_this_sessions(record):
    """A morning dispatch of the next session, listed against this record's applicable session, is not its."""
    raw = encode(record)
    next_day = run(event="workflow_dispatch", display_title=sw.MORNING_DISPATCH_TITLE,
                   created_at=MORNING_SLOT + timedelta(days=1))
    out = sw.judge_morning(record, None, raw, MORNING_SLOT + timedelta(days=1, minutes=10), [next_day], None)
    assert out["judgement"] == sw.NOT_STARTED and out["runs"] == []


def test_a_morning_run_created_at_the_collection_windows_start_is_this_mornings(record):
    raw = encode(record)
    at_start = run(event="schedule", display_title="Morning cron 0 13 * * 1-5", created_at=COLLECT)
    out = sw.judge_morning(record, None, raw, ALERT, [at_start], None)
    assert out["judgement"] == sw.STARTED_LATE and [r["id"] for r in out["runs"]] == [at_start["id"]]
    early = run(event="schedule", display_title="Morning cron 0 13 * * 1-5", created_at=COLLECT - SECOND)
    assert sw.judge_morning(record, None, raw, ALERT, [early], None)["judgement"] == sw.NOT_STARTED


@pytest.mark.parametrize("hours,alert", [(sw.MORNING_ALERT_HOURS - 0.01, True), (sw.MORNING_ALERT_HOURS, False)])
def test_a_morning_check_started_late_is_flagged_for_a_bounded_time(record, hours, alert):
    raw = encode(record)
    late_run = run(event="schedule", display_title="Morning cron 20 13 * * 1-5",
                   created_at=datetime(2026, 9, 11, 18, 0, tzinfo=UTC))
    out = sw.judge_morning(record, None, raw, ALERT + timedelta(hours=hours), [late_run], None)
    assert (out["judgement"], out["alert"]) == (sw.STARTED_LATE, alert)
    assert out["key"] == ("scheduler:morning:started_late" if alert else None)


def test_the_morning_receipt_is_tied_to_the_run_that_wrote_it(record):
    raw = encode(record)
    seen = receipt(raw, COLLECT + timedelta(minutes=21), observation_run_id="8123")
    runs = [run(id=8123, event="workflow_dispatch", display_title=sw.MORNING_DISPATCH_TITLE, created_at=MORNING_SLOT)]
    out = sw.judge_morning(record, seen, raw, ALERT, runs, None)
    assert out["receipt_run"] == 8123 and "The receipt on main was written by run 8123." in out["sentence"]
    other = receipt(b"other", COLLECT + timedelta(minutes=21), observation_run_id="8123")
    assert sw.judge_morning(record, other, raw, ALERT, runs, None)["receipt_run"] is None


#: The 9:05 AM CT watch slot on Friday 11 September (14:05 UTC) and its due window's end.
WATCH_SLOT = datetime(2026, 9, 11, 14, 5, tzinfo=UTC)


def test_the_watchs_previous_slot_is_the_latest_whose_window_has_closed():
    end = WATCH_SLOT + timedelta(minutes=ds.DUE_MINUTES)
    assert sw.previous_watch_slot(end) == WATCH_SLOT
    assert sw.previous_watch_slot(end - SECOND) == datetime(2026, 9, 11, 13, 25, tzinfo=UTC)       # 8:25 AM CDT
    # Saturday and Sunday have no watch slot: the previous one is Friday's 9:50 PM EDT
    assert sw.previous_watch_slot(datetime(2026, 9, 13, 18, 0, tzinfo=UTC)) == datetime(2026, 9, 12, 1, 50, tzinfo=UTC)
    # Monday 30 November, 6:31 AM CST: past Monday's first slot, which is the previous one
    assert sw.previous_watch_slot(datetime(2026, 11, 30, 12, 31, tzinfo=UTC)) == datetime(2026, 11, 30, 12, 0, tzinfo=UTC)
    # Monday 6:00 AM CST itself: its window is open, so the previous slot is Friday's 9:50 PM EST, three days back
    assert sw.previous_watch_slot(datetime(2026, 11, 30, 12, 0, tzinfo=UTC)) == datetime(2026, 11, 28, 2, 50, tzinfo=UTC)
    # and the Monday after Good Friday 2027 (26 March, closed): Thursday's 9:50 PM EDT, four days back
    assert sw.previous_watch_slot(datetime(2027, 3, 29, 11, 0, tzinfo=UTC)) == datetime(2027, 3, 26, 1, 50, tzinfo=UTC)


@pytest.mark.parametrize("runs,judgement,key", [
    ([run(event="workflow_dispatch", display_title=sw.WATCH_DISPATCH_TITLE, created_at=WATCH_SLOT)], sw.ON_TIME, None),
    ([run(event="workflow_dispatch", display_title=sw.WATCH_DISPATCH_TITLE,
          created_at=WATCH_SLOT + timedelta(minutes=ds.DUE_MINUTES) - SECOND)], sw.ON_TIME, None),
    ([run(event="workflow_dispatch", display_title=sw.WATCH_DISPATCH_TITLE, created_at=WATCH_SLOT,
          status="in_progress", conclusion=None)], sw.ON_TIME, None),                # still running: it started
    # a dispatched watch that ended without its work did not finish: it is not a start
    ([run(event="workflow_dispatch", display_title=sw.WATCH_DISPATCH_TITLE, created_at=WATCH_SLOT,
          conclusion="failure")], sw.NOT_STARTED, "scheduler:watch:not_started"),
    ([run(event="workflow_dispatch", display_title=sw.WATCH_DISPATCH_TITLE, created_at=WATCH_SLOT,
          conclusion="cancelled")], sw.NOT_STARTED, "scheduler:watch:not_started"),
    ([run(event="workflow_dispatch", display_title=sw.WATCH_DISPATCH_TITLE, created_at=WATCH_SLOT,
          conclusion="startup_failure")], sw.NOT_STARTED, "scheduler:watch:not_started"),
    ([run(event="workflow_dispatch", display_title=sw.WATCH_DISPATCH_TITLE, created_at=WATCH_SLOT,
          conclusion="failure"),
      run(id=7002, event="workflow_dispatch", display_title=sw.WATCH_DISPATCH_TITLE,
          created_at=WATCH_SLOT + timedelta(minutes=5))], sw.ON_TIME, None),        # a second dispatch that finished
    ([], sw.NOT_STARTED, "scheduler:watch:not_started"),
    ([run(event="schedule", display_title="Service watch cron 7 9 * * *", created_at=WATCH_SLOT)], sw.NOT_STARTED,
     "scheduler:watch:not_started"),                                                # a cron is not the dispatcher
    ([run(event="workflow_dispatch", display_title=sw.WATCH_DISPATCH_TITLE,
          created_at=WATCH_SLOT + timedelta(minutes=ds.DUE_MINUTES))], sw.NOT_STARTED, "scheduler:watch:not_started"),
    ([run(event="workflow_dispatch", display_title=sw.WATCH_DISPATCH_TITLE, created_at=WATCH_SLOT,
          head_branch="other")], sw.NOT_STARTED, "scheduler:watch:not_started"),
])
def test_the_watch_reports_a_gap_in_its_own_previous_slot_after_the_fact(runs, judgement, key):
    now = WATCH_SLOT + timedelta(minutes=ds.DUE_MINUTES, hours=1)
    out = sw.judge_watch(now, runs, None)
    assert (sw._instant(out["slot_at"]), out["judgement"], out["key"], out["alert"]) == (
        WATCH_SLOT, judgement, key, key is not None)
    assert out["slot_at"] == "2026-09-11T09:05:00-05:00"                 # said in the slot's own zone
    assert sw.judge_watch(now, None, "no token")["judgement"] == sw.UNKNOWN
    if judgement == sw.ON_TIME:
        assert sw.WHO in out["sentence"]                                  # the listing does not name the dispatcher
    elif runs and runs[0]["head_branch"] == "main" and runs[0]["conclusion"] in sw.FAILED_CONCLUSIONS:
        assert "did not finish" in out["sentence"]


def test_the_watchs_pre_open_slot_is_judged_by_its_own_window_which_ends_at_the_open():
    """The 8:25 AM CT watch slot is due only until the 8:30 AM CT open (the dispatcher's BEFORE_OPEN): a dispatch
    at 8:31 was not one in its slot, and the slot is judged from 8:30, not from the end of a 30-minute window."""
    slot, opens = ALERT, datetime(2026, 9, 11, 13, 30, tzinfo=UTC)
    assert ds.slot_end("service-watch.yml", slot) == opens
    assert sw.previous_watch_slot(opens - SECOND) != slot and sw.previous_watch_slot(opens) == slot
    inside = run(event="workflow_dispatch", display_title=sw.WATCH_DISPATCH_TITLE, created_at=opens - SECOND)
    after = run(event="workflow_dispatch", display_title=sw.WATCH_DISPATCH_TITLE, created_at=opens)
    assert sw.judge_watch(opens, [inside], None)["judgement"] == sw.ON_TIME
    out = sw.judge_watch(opens, [after], None)
    assert (out["judgement"], out["key"]) == (sw.NOT_STARTED, "scheduler:watch:not_started")
    assert f"due until {opens.astimezone(ds.CT).isoformat()}" in out["sentence"]


def test_with_no_watch_slot_to_look_back_on_the_watch_has_nothing_to_judge(monkeypatch):
    monkeypatch.setattr(ds, "SLOTS", tuple(s for s in ds.SLOTS if s[0] != "service-watch.yml"))
    assert sw.previous_watch_slot(WATCH_SLOT) is None
    assert sw.judge_watch(WATCH_SLOT, [], None)["judgement"] == sw.NOT_DUE


def test_without_a_token_every_scheduler_answer_is_unknown_and_the_files_still_answer(record, tmp_path):
    docs = docs_with(tmp_path, record)
    out = sw.watch(docs, LIMIT - timedelta(hours=2))
    sched = out["scheduler"]
    assert sched["listing"] == sw.UNKNOWN and sched["reason"] == sw.NO_TOKEN
    assert [sched[name]["judgement"] for name in ("evening", "watch")] == [sw.UNKNOWN, sw.UNKNOWN]
    assert sched["morning"]["judgement"] == sw.UNKNOWN and "GITHUB_TOKEN" in sched["morning"]["sentence"]
    assert [a["key"] for a in out["alerts"]] == ["evening:not_published:2026-09-11"]


@pytest.mark.parametrize("raises,words", [
    (ds.HTTPFailure(403, "listing"), "the run listing answered HTTP 403"),
    (ds.Incomplete("a full page"), "the run listing could not be read whole"),
    (urllib.error.URLError("refused"), "the run listing could not be read (URLError)"),
    (TimeoutError(), "the run listing could not be read (TimeoutError)"),
    (ConnectionResetError(), "the run listing could not be read (ConnectionResetError)"),
    (http.client.IncompleteRead(b"x"), "the run listing could not be read (IncompleteRead)"),
    (http.client.BadStatusLine("garbled"), "the run listing could not be read (BadStatusLine)"),
    (http.client.LineTooLong("header"), "the run listing could not be read (LineTooLong)"),
    (ValueError("anything else"), "the run listing could not be read (ValueError)"),
])
def test_a_listing_that_cannot_be_read_is_unknown_and_is_an_alert_of_its_own(record, tmp_path, raises, words):
    """No fault of the run listing aborts the run: each answer that needed it is unknown with its reason, the file
    answers stand, and a listing a token could not read is itself an alert, standing."""
    docs = docs_with(tmp_path, record)
    out = sw.watch(docs, LIMIT - timedelta(hours=2), github=Listing(raises=raises))
    for name in ("evening", "morning", "watch"):
        assert out["scheduler"][name]["judgement"] == sw.UNKNOWN and words in out["scheduler"][name]["sentence"]
    assert out["evening"]["judgement"] == sw.NOT_PUBLISHED                        # the file answers stand
    sched = out["scheduler"]
    assert sched["listing"] == sw.LISTING_FAILED != sw.LISTING_READ and words in sched["reason"]
    assert [a["key"] for a in out["alerts"]] == ["evening:not_published:2026-09-11", "scheduler:listing:unreadable"]
    (listing,) = [a for a in out["alerts"] if a["key"] == "scheduler:listing:unreadable"]
    assert listing["standing"] is True and listing["action"] == sw.LISTING_HINT
    assert listing["subject"] == "SpicyStock watch: the Actions run listing could not be read"
    assert "3 of the 3 workflows" in listing["sentence"] and "scheduler:listing:unreadable" not in out["clears"]
    assert out["exit_code"] == sw.EXIT_ALERT


def test_each_workflows_listing_stands_or_falls_alone(record, tmp_path):
    class OneFails(Listing):
        def runs(self, workflow, since):
            if workflow == sw.MORNING_WORKFLOW:
                raise http.client.IncompleteRead(b"cut")
            return super().runs(workflow, since)
    docs = docs_with(tmp_path, record)
    out = sw.watch(docs, ALERT, github=OneFails())
    sched = out["scheduler"]
    assert sched["morning"]["judgement"] == sw.UNKNOWN and "IncompleteRead" in sched["morning"]["sentence"]
    assert "IncompleteRead" not in sched["evening"]["sentence"] + sched["watch"]["sentence"]
    assert sched["watch"]["judgement"] == sw.NOT_STARTED                           # its own listing was read
    assert sched["listing"] == sw.LISTING_FAILED and sched["reason"] == (
        "morning.yml: the run listing could not be read (IncompleteRead)")
    assert "1 of the 3 workflows" in sched["listing_answer"]["sentence"]
    assert "scheduler:listing:unreadable" in [a["key"] for a in out["alerts"]]


def test_the_listing_says_it_was_read_only_when_it_was(record, tmp_path):
    docs = docs_with(tmp_path, record)
    read = sw.watch(docs, ALERT, github=Listing())["scheduler"]
    assert (read["listing"], read["reason"], read["listing_answer"]["alert"]) == (sw.LISTING_READ, None, False)
    assert [c["workflow"] for c in read["listing_answer"]["calls"] if c["asked"]] == [
        "evening.yml", "morning.yml", "service-watch.yml"]
    none = sw.watch(docs, ALERT)["scheduler"]
    assert (none["listing"], none["reason"], none["listing_answer"]["alert"]) == (sw.UNKNOWN, sw.NO_TOKEN, False)


@pytest.mark.parametrize("raises", [http.client.IncompleteRead(b"cut"), http.client.BadStatusLine("x"),
                                    ConnectionResetError(), ds.Incomplete("a full page")])
def test_a_transport_fault_in_the_listing_never_stops_the_evening_alert_from_being_mailed(record, tmp_path, monkeypatch,
                                                                                         capsys, raises):
    """The real client, its answer cut or garbled: main() still judges the files and mails the evening's alert,
    and the listing's own."""
    sent = deliveries(monkeypatch)

    def send(self, method, path, body=None):
        raise raises
    monkeypatch.setattr(ds.GitHub, "send", send)
    docs = docs_with(tmp_path, record)
    code = sw.main(["--docs", str(docs), "--now", (LIMIT - timedelta(hours=2)).isoformat(), "--mail"],
                   env={"GITHUB_TOKEN": "synthetic-token"})
    assert code == sw.EXIT_ALERT and len(sent) == 1
    subject, text = sent[0]
    assert "is not published" in subject and "Alert key: evening:not_published:2026-09-11." in text
    assert "Alert key: scheduler:listing:unreadable." in text
    assert "synthetic-token" not in capsys.readouterr().out + text


def test_the_listing_is_asked_from_the_instants_the_answers_need(record, tmp_path):
    docs = docs_with(tmp_path, record)
    listing = Listing()
    sw.watch(docs, ALERT - SECOND, github=listing)
    # before the morning is due its runs are not asked for
    assert [w for w, _ in listing.asked] == ["evening.yml", "service-watch.yml"]
    listing = Listing()
    sw.watch(docs, STARTED_BY, github=listing)
    assert listing.asked == [("evening.yml", COMPLETION), ("morning.yml", COLLECT),
                             ("service-watch.yml", datetime(2026, 9, 11, 14, 5, tzinfo=UTC))]


def test_the_start_block_gives_way_to_the_listing_that_read_the_same_run(record, tmp_path, bound_handoff):
    late = with_run_id(record)
    late["run"]["delivery"]["after_primary_minutes"] = 74.0     # SYNTHETIC: queued an hour after an on-time dispatch
    raw = encode(late)
    docs = docs_with(tmp_path, late, receipt(raw, COLLECT + timedelta(minutes=22)), handoff_files=False)
    now = FRIDAY_MORNING
    on_time = Listing({"evening.yml": [run(id=9001, created_at=RECORD_FIRST_SLOT + timedelta(minutes=1), **DISPATCH)]})
    out = sw.watch(docs, now, github=on_time)
    assert out["start"]["judgement"] == sw.STARTED_LATE and out["start"]["alert"] is True
    assert out["scheduler"]["evening"]["judgement"] == sw.ON_TIME
    assert "scheduler:evening:started_late" not in [a["key"] for a in out["alerts"]]
    # with no listing the record's own clock answers
    alone = sw.watch(docs, now)
    assert "scheduler:evening:started_late" in [a["key"] for a in alone["alerts"]]


def test_one_key_is_one_alert_however_many_answers_raise_it(record, tmp_path, bound_handoff):
    """The record's own run started late (its delivery block) and tonight's session's runs started late (the
    listing): two answers, one standing key, one alert."""
    late = with_run_id(record)
    late["run"]["delivery"]["after_primary_minutes"] = 1200.0      # SYNTHETIC: started at 18:16 UTC on the 11th
    raw = encode(late)
    docs = docs_with(tmp_path, late, receipt(raw, COLLECT + timedelta(minutes=22)), handoff_files=False)
    now = datetime(2026, 9, 12, 3, 30, tzinfo=UTC)
    listing = Listing({"evening.yml": [run(id=7100, created_at=datetime(2026, 9, 12, 3, 0, tzinfo=UTC))]})
    out = sw.watch(docs, now, github=listing)
    assert out["start"]["alert"] is True and out["scheduler"]["evening"]["judgement"] == sw.STARTED_LATE
    assert out["scheduler"]["evening"]["about"] == "session"
    keys = [a["key"] for a in out["alerts"]]
    assert keys.count("scheduler:evening:started_late") == 1 and len(keys) == len(set(keys))


def test_the_morning_alert_carries_the_scheduler_reason_beside_it(record, tmp_path):
    docs = docs_with(tmp_path, record)
    out = sw.watch(docs, ALERT, github=Listing())
    morning_alert = next(a for a in out["alerts"] if a["key"] == "morning:not_landed:2026-09-11")
    assert "No morning run for 2026-09-11 is listed on main" in morning_alert["detail"]
    (message,) = [m for m in sw.messages(out) if m["key"] == morning_alert["key"]]
    assert "No morning run for 2026-09-11 is listed on main" in message["body"]
    # a morning started on time carries no scheduler detail: the check was started, and did not land
    on_time = Listing({"morning.yml": [run(event="workflow_dispatch", display_title=sw.MORNING_DISPATCH_TITLE,
                                           created_at=MORNING_SLOT)]})
    quiet = sw.watch(docs, ALERT, github=on_time)
    morning_alert = next(a for a in quiet["alerts"] if a["key"] == "morning:not_landed:2026-09-11")
    assert quiet["scheduler"]["morning"]["judgement"] == sw.ON_TIME and morning_alert["detail"] is None


@pytest.mark.parametrize("listing,now,key", [
    (Listing(), STARTED_BY, "evening:not_started:2026-09-11"),
    (Listing({"evening.yml": [run(created_at=EVENING_FIRST_SLOT + timedelta(minutes=1), conclusion="failure",
                                  event="workflow_dispatch", display_title=sw.EVENING_DISPATCH_TITLE)]}),
     RETRY + timedelta(hours=1), "evening:failed:2026-09-11"),
    (Listing({"morning.yml": [run(event="schedule", display_title="Morning cron 20 13 * * 1-5",
                                  created_at=datetime(2026, 9, 11, 18, 0, tzinfo=UTC))]}),
     datetime(2026, 9, 11, 18, 5, tzinfo=UTC), "scheduler:morning:started_late"),
    (Listing(), WATCH_SLOT + timedelta(minutes=ds.DUE_MINUTES), "scheduler:watch:not_started"),
], ids=["evening-not-started", "evening-failed", "morning-started-late", "watch-not-started"])
def test_each_scheduler_answer_reaches_the_alerts_the_message_and_the_mail_once(record, tmp_path, monkeypatch, listing,
                                                                               now, key):
    sent = deliveries(monkeypatch)
    docs, ledger = docs_with(tmp_path, record), tmp_path / "ledger.json"
    out = sw.watch(docs, now, github=listing)
    assert key in [a["key"] for a in out["alerts"]]
    assert key in [m["key"] for m in sw.messages(out)]
    main_mail_with(docs, now, ledger, listing)
    main_mail_with(docs, now + timedelta(minutes=5), ledger, listing)
    assert sum(f"Alert key: {key}." in text for _, text in sent) == 1


def test_an_on_time_dispatch_that_did_not_publish_is_flagged_at_quarter_to_ten_through_the_watch(record, tmp_path):
    """The 9:50 PM ET watch slot's purpose: a dispatch in the first slot, listed, and no publication by 9:45."""
    docs = docs_with(tmp_path, record)
    on_time = Listing({"evening.yml": [run(event="workflow_dispatch", display_title=sw.EVENING_DISPATCH_TITLE,
                                           created_at=EVENING_FIRST_SLOT + timedelta(minutes=1))]})
    early = sw.watch(docs, PUBLISHED_BY - SECOND, github=on_time)
    assert early["evening"]["judgement"] == sw.OK
    out = sw.watch(docs, PUBLISHED_BY, github=on_time)
    assert out["evening"]["judgement"] == sw.NOT_PUBLISHED and "evening:not_published:2026-09-11" in [
        a["key"] for a in out["alerts"]]
    assert "a dispatch in the dispatcher's first evening slot started its evening" in out["evening"]["sentence"]
    assert "The on-time dispatcher started" not in out["evening"]["sentence"]
    # GitHub's backup cron alone is no on-time start: no evening alert at 9:45, only the scheduler's
    backup = Listing({"evening.yml": [run(created_at=datetime(2026, 9, 12, 1, 30, tzinfo=UTC))]})
    late = sw.watch(docs, PUBLISHED_BY, github=backup)
    assert late["evening"]["judgement"] == sw.OK and not [a for a in late["alerts"] if a["key"].startswith("evening:")]
    # the on-time start of another session is not this one's: the record covering the 11th is judged ok
    behind = sw.watch(docs, PUBLISHED_BY + timedelta(days=3), github=on_time)
    assert behind["evening"]["published_by"] is None


# ------------------------------------------------------------------ watch ---
def test_the_watch_reads_the_files_and_combines_the_answers(record, tmp_path):
    raw = encode(record)
    docs = docs_with(tmp_path, record, receipt(raw, COLLECT + timedelta(minutes=22)))
    quiet = sw.watch(docs, CUTOFF + timedelta(hours=1))
    assert quiet["version"] == sw.VERSION == 2 and quiet["record_sha256"] == hashlib.sha256(raw).hexdigest()
    assert (quiet["evening"]["judgement"], quiet["morning"]["judgement"], quiet["handoff"]["judgement"]) == (
        sw.OK, sw.LANDED, sw.BOUND)
    assert quiet["alert"] is False and quiet["alerts"] == [] and quiet["exit_code"] == sw.EXIT_OK
    assert quiet["clock"] == (CUTOFF + timedelta(hours=1)).isoformat()
    near = sw.watch(docs, LIMIT - timedelta(hours=2))
    assert near["evening"]["alert"] is True and near["morning"]["alert"] is False
    assert near["alert"] is True and near["exit_code"] == sw.EXIT_ALERT
    (docs / sw.MORNING_FILE).unlink()
    morning_only = sw.watch(docs, CUTOFF + timedelta(hours=1))
    assert morning_only["evening"]["alert"] is False and morning_only["morning"]["alert"] is True
    assert morning_only["exit_code"] == sw.EXIT_ALERT
    (docs / orders.FILE).unlink()
    unbound = sw.watch(docs, ALERT - SECOND)
    assert [a["key"] for a in unbound["alerts"]] == ["handoff:unbound:2026-09-10"]


def test_an_unknown_evening_is_its_own_exit_code_and_is_said_once_per_bytes(record, tmp_path, bound_handoff):
    bare = copy.deepcopy(record)
    del bare["run"]["calendar"]
    out = sw.watch(docs_with(tmp_path, bare, handoff_files=False), ALERT - SECOND)
    assert out["evening"]["judgement"] == sw.UNKNOWN and out["evening"]["alert"] is False
    digest = hashlib.sha256(encode(bare)).hexdigest()
    assert [a["key"] for a in out["alerts"]] == [f"record:unknown:{digest}"] and out["exit_code"] == sw.EXIT_UNKNOWN
    (alert,) = out["alerts"]
    assert alert["subject"] == sw.UNKNOWN_SUBJECT and alert["action"] == sw.UNKNOWN_HINT
    assert sw.KEY_PATTERN.fullmatch(alert["key"])


def test_a_record_that_cannot_answer_exits_2_whatever_else_it_flags_or_drops(record, tmp_path, monkeypatch):
    """An unknown evening beside another alert is 2, mailed or dropped as a repeat: never green on a repeat."""
    sent = deliveries(monkeypatch)
    bare = copy.deepcopy(record)
    del bare["run"]["calendar"]
    docs, ledger = docs_with(tmp_path, bare, handoff_files=False), tmp_path / "ledger.json"
    first = ALERT - timedelta(hours=1)
    out = sw.watch(docs, first)
    assert len(out["alerts"]) == 2 and out["exit_code"] == sw.EXIT_UNKNOWN       # its own key and the handoff's
    assert main_mail(docs, first, ledger) == sw.EXIT_UNKNOWN and len(sent) == 1
    assert main_mail(docs, ALERT - SECOND, ledger) == sw.EXIT_UNKNOWN and len(sent) == 1   # every alert a repeat


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
    assert sw.main(["--docs", str(docs), "--now", CUTOFF.isoformat()], env={}) == sw.EXIT_UNKNOWN


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
    docs = docs_with(tmp_path, record)
    monkeypatch.setattr(sw, "MAX_RECORD_BYTES", len(encode(record)) - 1)
    with pytest.raises(sw.Unreadable, match="over the"):
        sw.watch(docs, CUTOFF)
    monkeypatch.setattr(sw, "MAX_RECORD_BYTES", len(encode(record)))
    assert sw.watch(docs, ALERT - SECOND)["exit_code"] == sw.EXIT_OK


def test_an_oversize_morning_file_is_a_check_that_did_not_land(record, tmp_path, monkeypatch):
    raw = encode(record)
    docs = docs_with(tmp_path, record, receipt(raw, COLLECT + timedelta(minutes=22)))
    monkeypatch.setattr(sw, "MAX_MORNING_BYTES", 10)
    out = sw.watch(docs, CUTOFF)
    assert out["morning"]["judgement"] == sw.NOT_LANDED and "over the 10 this watch reads" in out["morning"]["sentence"]


# ------------------------------------------------------- the command, mail ---
def test_the_command_prints_every_answer_and_exits_by_the_judgement(record, tmp_path, capsys):
    raw = encode(record)
    docs = docs_with(tmp_path, record, receipt(raw, COLLECT + timedelta(minutes=22)))
    assert sw.main(["--docs", str(docs), "--now", (CUTOFF + timedelta(hours=1)).isoformat()], env={}) == sw.EXIT_OK
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("Service watch at 2026-09-11T15:00:00+00:00")
    assert out[1].startswith("Evening: ok (newest).") and out[2].startswith("Morning: landed.") and out[-1] == "Nothing to flag."
    assert any(line.startswith("Handoff: bound.") for line in out)
    assert any(line.startswith("Scheduler watch: unknown.") for line in out)
    assert sw.main(["--docs", str(docs), "--now", (LIMIT - timedelta(hours=2)).isoformat(), "--json"], env={}) == sw.EXIT_ALERT
    printed = json.loads(capsys.readouterr().out)
    assert printed == sw.watch(docs, LIMIT - timedelta(hours=2))
    assert sw.main(["--docs", str(docs), "--now", "2026-09-11T15:00:00"], env={}) == sw.EXIT_UNKNOWN      # no offset
    assert "not an instant with an offset" in capsys.readouterr().err


class Sent(list):
    """The messages the transport accepted, as (subject, body), with every attempt counted (``tries``) and the
    retry's pauses recorded (``waits``), never slept."""
    tries = 0


def deliveries(monkeypatch, fail: set | None = None, refuse: int = 0) -> Sent:
    """The evening's transport, recorded: a message whose subject or body carries a word of ``fail`` is refused
    every time, and the first ``refuse`` attempts are refused whatever they say."""
    from src import report
    sent = Sent()
    sent.waits = []

    def deliver(subject, body, attachments=None):
        sent.tries += 1
        if (fail and any(word in subject or word in body for word in fail)) or sent.tries <= refuse:
            raise RuntimeError("SYNTHETIC: the transport refused")
        sent.append((subject, body))
        return {"id": "x"}
    monkeypatch.setattr(report, "deliver", deliver)
    monkeypatch.setattr(sw, "_wait", sent.waits.append)
    return sent


def test_mail_goes_once_per_alert_through_the_evenings_transport_and_only_when_asked(record, tmp_path, monkeypatch, capsys):
    sent = deliveries(monkeypatch)
    docs = docs_with(tmp_path, record)                 # no morning file: both answers can alert
    both = (LIMIT - timedelta(hours=2)).isoformat()    # 11:30 UTC Monday: the morning alert window has long passed
    assert sw.main(["--docs", str(docs), "--now", both], env={}) == sw.EXIT_ALERT and sent == []      # not asked
    assert sw.main(["--docs", str(docs), "--now", both, "--mail"], env={}) == sw.EXIT_ALERT
    assert [subject for subject, _ in sent] == ["SpicyStock watch: 2026-09-11 is not published"]
    body = sent[0][1]
    assert "only_if_unpublished" in body and "Watch clock: 2026-09-14T11:30:00+00:00" in body
    assert html.escape(sw.LATE_ITSELF) in body and "Alert key: evening:not_published:2026-09-11." in body
    assert "<script" not in body and body.startswith("<p>") and body.endswith("</p>")
    sent.clear()
    assert sw.main(["--docs", str(docs), "--now", (CUTOFF + timedelta(hours=1)).isoformat(), "--mail"], env={}) == sw.EXIT_ALERT
    assert [subject for subject, _ in sent] == ["SpicyStock watch: no morning check landed for 2026-09-11"]
    sent.clear()
    assert sw.main(["--docs", str(docs), "--now", (ALERT - SECOND).isoformat(), "--mail"], env={}) == sw.EXIT_OK
    assert sent == []                                   # nothing to flag: nothing mailed
    capsys.readouterr()


def test_an_unreadable_record_is_mailed_when_mail_is_asked_for_and_never_otherwise(tmp_path, monkeypatch, capsys):
    """The state in which the site itself can show no record. Without --mail the run is red; with it a person
    hears of it, in one message that names the reason and nothing from the file."""
    sent = deliveries(monkeypatch)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / sw.DATA_FILE).write_text('{"run": <script>')            # truncated: not JSON
    now = "2026-09-14T11:30:00+00:00"
    assert sw.main(["--docs", str(docs), "--now", now], env={}) == sw.EXIT_UNKNOWN and sent == []
    assert sw.main(["--docs", str(docs), "--now", now, "--mail"], env={}) == sw.EXIT_UNKNOWN
    assert [subject for subject, _ in sent] == [sw.UNREADABLE_SUBJECT]
    body = sent[0][1]
    assert "data.json is not JSON (JSONDecodeError)" in body and "Watch clock: 2026-09-14T11:30:00+00:00" in body
    assert "<script" not in body
    digest = hashlib.sha256(b'{"run": <script>').hexdigest()
    assert f"Alert key: record:unreadable:{digest}." in body
    assert "Mailed 1 alert." in capsys.readouterr().err


def test_a_message_escapes_what_it_quotes(record):
    result = {"clock": "2026-09-14T11:30:00+00:00",
              "alerts": [sw._alert("evening:not_published:2026-09-11", "a <b>record</b> & its words", None)]}
    (message,) = sw.messages(result)
    assert message["subject"] == "SpicyStock watch: 2026-09-11 is not published"
    assert "a &lt;b&gt;record&lt;/b&gt; &amp; its words" in message["body"] and "<b>" not in message["body"]


@pytest.mark.parametrize("key,subject", [
    ("evening:missing:2026-09-11", "SpicyStock watch: 2026-09-11 was not published before the next open"),
    ("evening:not_started:2026-09-11", "SpicyStock watch: the 2026-09-11 evening run has not started"),
    ("evening:failed:2026-09-11", "SpicyStock watch: the 2026-09-11 evening run failed"),
    ("morning:not_checked:2026-09-11", "SpicyStock watch: orders-morning.json is not checked for 2026-09-11"),
    ("handoff:unbound:2026-09-10", "SpicyStock watch: the 2026-09-10 handoff files do not pass their check"),
    ("scheduler:evening:started_late", "SpicyStock watch: the evening was not started at its first slot"),
    ("scheduler:morning:started_late", "SpicyStock watch: the morning check was not started at its slot"),
    ("scheduler:watch:not_started", "SpicyStock watch: the watch was not started at its slot"),
    ("scheduler:listing:unreadable", "SpicyStock watch: the Actions run listing could not be read"),
    ("record:unreadable:absent", sw.UNREADABLE_SUBJECT),
    (f"record:unknown:{'a' * 64}", sw.UNKNOWN_SUBJECT),
])
def test_every_key_has_its_subject_and_is_a_key_the_ledger_reads(key, subject):
    alert = sw._alert(key, "words", None)
    assert alert["subject"] == subject and sw.KEY_PATTERN.fullmatch(key)
    assert alert["standing"] is key.startswith("scheduler:")


def test_the_log_lines_carry_each_action_under_its_answer(record, tmp_path):
    docs = docs_with(tmp_path, record)
    printed = sw.lines(sw.watch(docs, LIMIT - timedelta(hours=2)))
    assert printed[1].startswith("Evening: not_published (late).") and printed[2] == f"  {sw.DISPATCH_HINT}"
    assert printed[3].startswith("Morning: not_landed.") and printed[-1] == "Alert."
    assert "Alert evening:not_published:2026-09-11: SpicyStock watch: 2026-09-11 is not published" in printed


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
    assert (out["judgement"], out["alert"], out["session"], out["key"]) == (sw.ON_TIME, False, "2026-09-10", None)
    assert out["sentence"].startswith("The 2026-09-10 evening run started 14 minutes after its primary slot")


@pytest.mark.parametrize("minutes, judgement", [(sw.LATE_START_MINUTES, sw.ON_TIME),
                                                (sw.LATE_START_MINUTES + 0.1, sw.STARTED_LATE),
                                                (298.3, sw.STARTED_LATE)])
def test_an_evening_that_started_more_than_an_hour_late_is_flagged_under_the_standing_key(record, minutes, judgement):
    out = sw.start(late(record, minutes), STARTED_SLOT + timedelta(minutes=minutes, hours=1))
    assert out["judgement"] == judgement and out["alert"] is (judgement == sw.STARTED_LATE)
    if judgement == sw.STARTED_LATE:
        assert f"more than {sw.LATE_START_MINUTES} minutes late" in out["sentence"] and out["action"] == sw.START_HINT
        assert out["key"] == "scheduler:evening:started_late"                # no session: a standing condition


@pytest.mark.parametrize("hours, alert", [(sw.LATE_START_ALERT_HOURS, False), (sw.LATE_START_ALERT_HOURS - 0.01, True)])
def test_a_late_start_is_flagged_for_a_bounded_time(record, hours, alert):
    started = STARTED_SLOT + timedelta(minutes=200)
    out = sw.start(late(record, 200), started + timedelta(hours=hours))
    assert (out["judgement"], out["alert"], out["key"] is not None) == (sw.STARTED_LATE, alert, alert)


@pytest.mark.parametrize("value", [None, True, "298"])
def test_a_record_without_a_readable_start_says_so_and_flags_nothing(record, value):
    out = sw.start(late(record, value), STARTED_SLOT)
    assert (out["judgement"], out["alert"], out["key"]) == (sw.UNKNOWN, False, None)


def test_a_late_start_reaches_the_watchs_exit_code_and_its_mail(record, tmp_path, bound_handoff):
    raw = encode(late(record, 298.3))
    changed = json.loads(raw)
    docs = docs_with(tmp_path, changed, receipt(raw, COLLECT + timedelta(minutes=22)), handoff_files=False)
    out = sw.watch(docs, STARTED_SLOT + timedelta(hours=6))
    assert out["start"]["alert"] is True and out["exit_code"] == sw.EXIT_ALERT
    assert [m["subject"] for m in sw.messages(out)] == [
        "SpicyStock watch: the evening was not started at its first slot"]
    assert any(line.startswith("Start: started_late. ") for line in sw.lines(out))


# ----------------------------------------------------------------- ledger ---
def main_mail(docs, now, ledger, env=None, extra=()):
    return sw.main(["--docs", str(docs), "--now", now.isoformat(), "--mail", "--ledger", str(ledger), *extra],
                   env=env or {})


def test_a_second_and_third_run_mail_nothing_and_exit_by_the_judgement(record, tmp_path, monkeypatch, capsys):
    """A repeat is dropped, and the run still exits 1: the exit code is the judgement's, mailed or dropped."""
    sent = deliveries(monkeypatch)
    docs, ledger = docs_with(tmp_path, record), tmp_path / "cache" / "ledger.json"
    near = LIMIT - timedelta(hours=2)
    assert main_mail(docs, near, ledger) == sw.EXIT_ALERT and len(sent) == 1
    for later in (near + timedelta(minutes=30), near + timedelta(hours=1)):
        assert main_mail(docs, later, ledger) == sw.EXIT_ALERT
    assert len(sent) == 1
    err = capsys.readouterr().err
    assert f"Not mailed again: evening:not_published:2026-09-11 was mailed at {near.isoformat()}." in err
    assert json.loads(ledger.read_text()) == {"version": sw.LEDGER_VERSION, "cleared": {},
                                              "sent": {"evening:not_published:2026-09-11": near.isoformat()}}


def test_a_change_of_state_mails_once_more(record, tmp_path, monkeypatch):
    sent = deliveries(monkeypatch)
    docs, ledger = docs_with(tmp_path, record), tmp_path / "ledger.json"
    for now in (LIMIT - timedelta(hours=1), LIMIT - SECOND, LIMIT, LIMIT + timedelta(hours=1)):
        main_mail(docs, now, ledger)
    assert [s for s, _ in sent] == ["SpicyStock watch: 2026-09-11 is not published",
                                    "SpicyStock watch: 2026-09-11 was not published before the next open"]


MAILED_KEY = "evening:not_published:2026-09-11"


def spoiled(change):
    """The real ledger with one thing about it changed: the key it holds stays in it, so the ledger reads empty
    for that one fault and not for an incidental one."""
    def spoil(path, now):
        value = json.loads(path.read_text())
        change(value, now)
        path.write_text(json.dumps(value))
    return spoil


@pytest.mark.parametrize("spoil", [
    lambda p, now: p.unlink(),
    lambda p, now: p.write_text("{not json"),
    spoiled(lambda v, now: v.__setitem__("version", sw.LEDGER_VERSION + 1)),             # another version
    spoiled(lambda v, now: v.__setitem__("version", True)),                                # not a version at all
    spoiled(lambda v, now: v.__setitem__("sent", [list(item) for item in v["sent"].items()])),
    spoiled(lambda v, now: v.__setitem__("cleared", [])),                                  # clears not a map
    spoiled(lambda v, now: v.pop("cleared")),                                              # no clears at all
    spoiled(lambda v, now: v["sent"].__setitem__(MAILED_KEY, (now + timedelta(minutes=1)).isoformat())),   # future
    spoiled(lambda v, now: v["cleared"].__setitem__("scheduler:watch:not_started",
                                                    (now + timedelta(minutes=1)).isoformat())),    # a future clear
    spoiled(lambda v, now: v["sent"].__setitem__("Mail to owner@example.com", now.isoformat())),  # not a key
    spoiled(lambda v, now: v["cleared"].__setitem__("owner@example.com", now.isoformat())),       # a clear, not a key
    spoiled(lambda v, now: v["sent"].__setitem__("evening:not_published:2026-09-12", "yesterday")),   # not an instant
    spoiled(lambda v, now: v.__setitem__("body", "<p>hi</p>")),                            # more than keys
    lambda p, now: p.write_text(p.read_text() + " " * sw.MAX_LEDGER_BYTES),                # too large
], ids=["deleted", "not-json", "other-version", "bool-version", "sent-not-a-map", "cleared-not-a-map", "no-cleared",
        "future-dated", "future-clear", "not-a-key", "clear-not-a-key", "not-an-instant", "more-than-keys", "too-large"])
def test_a_ledger_that_cannot_be_read_as_this_watchs_reads_empty_and_mails_again(record, tmp_path, monkeypatch, spoil):
    sent = deliveries(monkeypatch)
    docs, ledger = docs_with(tmp_path, record), tmp_path / "ledger.json"
    first = LIMIT - timedelta(hours=2)
    main_mail(docs, first, ledger)
    # unspoiled, it drops the repeat
    assert main_mail(docs, first + timedelta(minutes=15), ledger) == sw.EXIT_ALERT and len(sent) == 1
    spoil(ledger, first + timedelta(minutes=30))
    assert main_mail(docs, first + timedelta(minutes=30), ledger) == sw.EXIT_ALERT
    assert len(sent) == 2


def test_a_linked_ledger_is_not_read(record, tmp_path, monkeypatch):
    sent = deliveries(monkeypatch)
    docs, real, ledger = docs_with(tmp_path, record), tmp_path / "real.json", tmp_path / "ledger.json"
    first = LIMIT - timedelta(hours=2)
    main_mail(docs, first, real)
    ledger.symlink_to(real)
    assert sw.read_ledger(ledger, first) == {"sent": {}, "cleared": {}}
    assert len(sw.read_ledger(real, first)["sent"]) == 1
    main_mail(docs, first + timedelta(minutes=5), ledger)
    assert len(sent) == 2


def test_a_mail_the_transport_refuses_is_tried_once_more_and_not_remembered(record, tmp_path, monkeypatch, capsys):
    sent = deliveries(monkeypatch, fail={"is not published"})
    docs, ledger = docs_with(tmp_path, record), tmp_path / "ledger.json"
    near = LIMIT - timedelta(hours=2)
    assert main_mail(docs, near, ledger) == sw.EXIT_UNFINISHED           # refused twice: the run did not finish
    assert sent == [] and sent.tries == 2 and sent.waits == [sw.MAIL_RETRY_SECONDS]
    assert not ledger.exists()                                            # nothing was mailed and nothing cleared
    assert "Mail failed twice for evening:not_published:2026-09-11 (RuntimeError)" in capsys.readouterr().err
    sent = deliveries(monkeypatch)
    assert main_mail(docs, near + timedelta(minutes=5), ledger) == sw.EXIT_ALERT and len(sent) == 1


def test_a_mail_refused_once_is_mailed_by_its_retry_in_the_same_run(record, tmp_path, monkeypatch, capsys):
    sent = deliveries(monkeypatch, refuse=1)
    docs, ledger = docs_with(tmp_path, record), tmp_path / "ledger.json"
    assert main_mail(docs, LIMIT - timedelta(hours=2), ledger) == sw.EXIT_ALERT
    assert len(sent) == 1 and sent.tries == 2 and sent.waits == [sw.MAIL_RETRY_SECONDS]
    assert MAILED_KEY in json.loads(ledger.read_text())["sent"]
    assert "(after a refused first try)" in capsys.readouterr().err


def test_a_key_past_its_repeat_days_is_mailed_again_and_old_entries_are_pruned(record, tmp_path, monkeypatch):
    sent = deliveries(monkeypatch)
    ledger = tmp_path / "ledger.json"
    first = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    alert = sw._alert("scheduler:watch:not_started", "words", None)
    gone = sw._alert("evening:not_published:2026-08-01", "words", None)
    sw.send([alert, gone], first, ledger)
    assert len(sent) == 1                                          # one message for both
    edge = first + timedelta(days=sw.REPEAT_DAYS)
    assert sw.send([alert], edge - SECOND, ledger)["dropped"]                  # a standing key: dropped for a week
    again = sw.send([alert], edge, ledger)
    assert again["mailed"] == ["scheduler:watch:not_started"] and len(sent) == 2
    assert json.loads(ledger.read_text())["sent"] == {"scheduler:watch:not_started": edge.isoformat()}


def watch_slot_runs(*slots, conclusion="success"):
    """SYNTHETIC: the dispatcher's watch dispatched at each of ``slots``."""
    return [run(id=8000 + n, event="workflow_dispatch", display_title=sw.WATCH_DISPATCH_TITLE, created_at=at,
                conclusion=conclusion) for n, at in enumerate(slots)]


def test_a_standing_key_that_clears_and_returns_inside_its_repeat_days_is_mailed_again(record, tmp_path, monkeypatch):
    """Not started, then on time, then not started again two days later: the return is a new condition, mailed
    before the window; a run of the same condition with no clear in between is still dropped."""
    sent = deliveries(monkeypatch)
    ledger = tmp_path / "ledger.json"
    alert = sw._alert("scheduler:watch:not_started", "words", None)
    first = datetime(2026, 12, 1, 14, 27, tzinfo=UTC)
    assert sw.send([alert], first, ledger)["mailed"] == ["scheduler:watch:not_started"]
    assert sw.send([alert], first + timedelta(hours=1), ledger)["dropped"]             # uninterrupted: a repeat
    cleared = sw.send([], first + timedelta(days=1), ledger, cleared=["scheduler:watch:not_started"])
    assert cleared["cleared"] == ["scheduler:watch:not_started"] and cleared["ledger_written"] is True
    held = json.loads(ledger.read_text())
    assert held["cleared"] == {"scheduler:watch:not_started": (first + timedelta(days=1)).isoformat()}
    # a second on-time run records nothing more and writes nothing
    assert sw.send([], first + timedelta(days=1, hours=1), ledger, cleared=["scheduler:watch:not_started"]) == {
        "mailed": [], "dropped": [], "failed": [], "cleared": [], "attempts": 0, "ledger_written": False,
        "ledger_error": None}
    back = sw.send([alert], first + timedelta(days=3), ledger)
    assert back["mailed"] == ["scheduler:watch:not_started"] and len(sent) == 2
    held = json.loads(ledger.read_text())
    assert held["sent"] == {"scheduler:watch:not_started": (first + timedelta(days=3)).isoformat()} \
        and held["cleared"] == {}
    assert sw.send([alert], first + timedelta(days=3, hours=1), ledger)["dropped"]     # and a repeat of the return


def test_a_clear_is_recorded_only_for_a_key_mailed_and_never_for_one_alerting(tmp_path, monkeypatch):
    deliveries(monkeypatch)
    ledger = tmp_path / "ledger.json"
    now = datetime(2026, 12, 1, 14, 27, tzinfo=UTC)
    # never mailed: nothing to clear, nothing written
    out = sw.send([], now, ledger, cleared=["scheduler:watch:not_started"])
    assert out["cleared"] == [] and not ledger.exists()
    alert = sw._alert("scheduler:watch:not_started", "words", None)
    sw.send([alert], now, ledger)
    # a key a result both raises and clears is alerting: no clear
    assert sw.send([alert], now + timedelta(hours=1), ledger, cleared=["scheduler:watch:not_started"])["cleared"] == []


@pytest.mark.parametrize("key,listing,judge", [
    ("scheduler:watch:not_started", None, "watch"),
    ("scheduler:morning:started_late", None, "morning"),
    ("scheduler:evening:started_late", None, "evening"),
    ("scheduler:listing:unreadable", sw.LISTING_READ, None),
])
def test_each_standing_key_is_cleared_by_its_own_answer_on_time(key, listing, judge):
    def result(judgement, alerts=(), start=None, **sched):
        block = {"judgement": judgement} if judge else {}
        scheduler = {"listing": listing or sw.UNKNOWN, **({judge: block} if judge else {}), **sched}
        return {"scheduler": scheduler, "start": start or {}, "alerts": [{"key": k} for k in alerts]}
    assert key in sw.clears_of(result(sw.ON_TIME))
    assert key not in sw.clears_of(result(sw.ON_TIME, alerts=[key]))          # raised in the same run: no clear
    if judge:
        assert key not in sw.clears_of(result(sw.NOT_DUE)) or judge == "evening"
        assert key not in sw.clears_of(result(sw.UNKNOWN))
    else:
        assert key not in sw.clears_of({"scheduler": {"listing": sw.LISTING_FAILED}, "alerts": []})
        assert key not in sw.clears_of({"scheduler": {"listing": sw.UNKNOWN}, "alerts": []})


def test_the_evenings_standing_key_is_cleared_by_the_records_own_on_time_start_when_the_listing_says_nothing(record):
    on_time = {"judgement": sw.ON_TIME}
    for answer in (sw.UNKNOWN, sw.NOT_DUE):
        assert "scheduler:evening:started_late" in sw.clears_of(
            {"scheduler": {"evening": {"judgement": answer}}, "start": on_time, "alerts": []})
    for answer in (sw.STARTED_LATE, sw.NOT_STARTED, sw.FAILED):
        assert "scheduler:evening:started_late" not in sw.clears_of(
            {"scheduler": {"evening": {"judgement": answer}}, "start": on_time, "alerts": []})
    assert "scheduler:evening:started_late" not in sw.clears_of(
        {"scheduler": {"evening": {"judgement": sw.UNKNOWN}}, "start": {"judgement": sw.STARTED_LATE}, "alerts": []})


def test_a_dispatcher_outage_that_returns_after_an_on_time_day_is_mailed_before_the_window(record, tmp_path,
                                                                                         monkeypatch):
    """The finding, end to end: the 8:25 AM CT watch slot missed on Thursday 10 September and mailed; on time on
    Friday morning; missed again on Friday's 9:05 slot. The return is mailed by the next watch, within the week."""
    sent = deliveries(monkeypatch)
    docs, ledger = docs_with(tmp_path, record), tmp_path / "ledger.json"
    thursday_slot, friday_slot = datetime(2026, 9, 10, 13, 25, tzinfo=UTC), datetime(2026, 9, 11, 13, 25, tzinfo=UTC)

    def watch_mails():
        return sum("Alert key: scheduler:watch:not_started." in text for _, text in sent)
    main_mail_with(docs, thursday_slot + timedelta(minutes=10), ledger, Listing({}))
    assert watch_mails() == 1
    on_time = Listing({"service-watch.yml": watch_slot_runs(friday_slot)})
    main_mail_with(docs, friday_slot + timedelta(minutes=10), ledger, on_time)
    assert watch_mails() == 1 and "scheduler:watch:not_started" in json.loads(ledger.read_text())["cleared"]
    main_mail_with(docs, WATCH_SLOT + timedelta(minutes=ds.DUE_MINUTES, seconds=5), ledger,
                   Listing({"service-watch.yml": watch_slot_runs(friday_slot)}))
    assert watch_mails() == 2                         # the return, two days after the first mail


def main_mail_with(docs, now, ledger, listing):
    """main() with --mail and --ledger, its run listing the double ``listing``."""
    import unittest.mock
    with unittest.mock.patch.object(sw, "github_from", lambda env: listing):
        return main_mail(docs, now, ledger)


def test_the_ledger_holds_keys_and_instants_only(record, tmp_path, monkeypatch):
    monkeypatch.setenv("EMAIL_TO", "owner@example.com")
    deliveries(monkeypatch)
    docs, ledger = docs_with(tmp_path, record), tmp_path / "ledger.json"
    main_mail(docs, LIMIT - timedelta(hours=2), ledger)
    main_mail(docs, CUTOFF + timedelta(hours=1), ledger)
    text = ledger.read_text()
    value = json.loads(text)
    assert set(value) == {"version", "sent", "cleared"}
    assert all(sw.KEY_PATTERN.fullmatch(k) and sw._instant(v) for part in ("sent", "cleared")
               for k, v in value[part].items())
    assert "@" not in text and "<p>" not in text and "only_if_unpublished" not in text


def outputs(path: Path) -> dict:
    return dict(line.split("=", 1) for line in path.read_text().splitlines())


def test_the_workflow_is_told_to_save_the_ledger_only_when_it_was_written(record, tmp_path, monkeypatch):
    deliveries(monkeypatch)
    docs, ledger = docs_with(tmp_path, record), tmp_path / "ledger.json"
    near = LIMIT - timedelta(hours=2)
    first, second = tmp_path / "output-1", tmp_path / "output-2"
    main_mail(docs, near, ledger, env={"GITHUB_OUTPUT": str(first)})
    assert outputs(first)["ledger"] == "written"
    main_mail(docs, near + timedelta(minutes=5), ledger, env={"GITHUB_OUTPUT": str(second)})     # a repeat: dropped
    assert "ledger" not in outputs(second) and outputs(second)["mail"] == "dropped"


def test_the_workflow_is_told_the_judgement_the_alerts_and_that_the_watch_finished(record, tmp_path, monkeypatch):
    deliveries(monkeypatch)
    docs, ledger, summary = docs_with(tmp_path, record), tmp_path / "ledger.json", tmp_path / "summary.md"
    output = tmp_path / "output"
    env = {"GITHUB_OUTPUT": str(output), "GITHUB_STEP_SUMMARY": str(summary)}
    assert main_mail(docs, LIMIT - timedelta(hours=2), ledger, env=env) == sw.EXIT_ALERT
    told = outputs(output)
    assert told == {"exit_code": "1", "alerts": MAILED_KEY, "mail": "mailed", "ledger": "written", "finished": "true"}
    assert output.read_text().splitlines()[-1] == "finished=true"                 # its last act
    text = summary.read_text()
    assert text.startswith("## Service watch") and "Evening: not_published (late)." in text
    assert f"Alert {MAILED_KEY}: SpicyStock watch: 2026-09-11 is not published" in text
    assert "Mailed one message for evening:not_published:2026-09-11." in text


def test_a_watch_whose_mail_failed_twice_does_not_say_it_finished(record, tmp_path, monkeypatch):
    deliveries(monkeypatch, fail={"is not published"})
    docs, output = docs_with(tmp_path, record), tmp_path / "output"
    code = main_mail(docs, LIMIT - timedelta(hours=2), tmp_path / "ledger.json", env={"GITHUB_OUTPUT": str(output)})
    assert code == sw.EXIT_UNFINISHED
    told = outputs(output)
    assert told["mail"] == "failed" and told["exit_code"] == str(sw.EXIT_UNFINISHED) and "finished" not in told


def test_without_mail_the_workflow_is_still_told_what_the_watch_judged(record, tmp_path):
    docs, output = docs_with(tmp_path, record), tmp_path / "output"
    assert sw.main(["--docs", str(docs), "--now", (LIMIT - timedelta(hours=2)).isoformat()],
                   env={"GITHUB_OUTPUT": str(output)}) == sw.EXIT_ALERT
    assert outputs(output) == {"exit_code": "1", "alerts": MAILED_KEY, "mail": "not_asked", "finished": "true"}


def test_an_unreadable_record_is_mailed_once_per_bytes_and_exits_2_mailed_or_dropped(tmp_path, monkeypatch):
    sent = deliveries(monkeypatch)
    docs, ledger = tmp_path / "docs", tmp_path / "ledger.json"
    docs.mkdir()
    (docs / sw.DATA_FILE).write_text("{truncated")
    now = datetime(2026, 9, 14, 11, 30, tzinfo=UTC)
    assert main_mail(docs, now, ledger) == sw.EXIT_UNKNOWN
    assert main_mail(docs, now + timedelta(days=1), ledger) == sw.EXIT_UNKNOWN     # the same bytes: dropped, still 2
    (docs / sw.DATA_FILE).write_text("{truncated again")
    assert main_mail(docs, now + timedelta(days=2), ledger) == sw.EXIT_UNKNOWN     # other bytes: another key
    (docs / sw.DATA_FILE).unlink()
    assert main_mail(docs, now + timedelta(days=3), ledger) == sw.EXIT_UNKNOWN     # absent
    assert len(sent) == 3
    assert "record:unreadable:absent" in json.loads(ledger.read_text())["sent"]
    # the same bytes a week after their first mail: mailed again while they stand
    (docs / sw.DATA_FILE).write_text("{truncated")
    assert main_mail(docs, now + timedelta(days=sw.REPEAT_DAYS), ledger) == sw.EXIT_UNKNOWN and len(sent) == 4


def test_an_unreadable_record_whose_mail_is_refused_twice_does_not_finish(tmp_path, monkeypatch, capsys):
    sent = deliveries(monkeypatch, fail={"could not be read"})
    docs, ledger, output = tmp_path / "docs", tmp_path / "ledger.json", tmp_path / "output"
    docs.mkdir()
    (docs / sw.DATA_FILE).write_text("{truncated")
    now = datetime(2026, 9, 14, 11, 30, tzinfo=UTC)
    assert main_mail(docs, now, ledger, env={"GITHUB_OUTPUT": str(output)}) == sw.EXIT_UNFINISHED
    assert sent == [] and sent.tries == 2 and not ledger.exists()
    assert "finished" not in outputs(output) and outputs(output)["mail"] == "failed"
    # without --mail it is 2 and it finished: nothing was owed
    output.unlink()
    assert sw.main(["--docs", str(docs), "--now", now.isoformat()], env={"GITHUB_OUTPUT": str(output)}) \
        == sw.EXIT_UNKNOWN and outputs(output)["finished"] == "true"


def test_one_run_sends_one_message_naming_every_new_alert(record, tmp_path, monkeypatch):
    sent = deliveries(monkeypatch)
    docs, ledger = docs_with(tmp_path, record), tmp_path / "ledger.json"
    now = STARTED_BY                                    # no morning file, no evening run, no watch run listed
    listing = Listing()
    result = sw.watch(docs, now, github=listing)
    keys = [a["key"] for a in result["alerts"]]
    assert len(keys) >= 3
    assert main_mail_with(docs, now, ledger, Listing()) == sw.EXIT_ALERT
    (message,) = sent
    subject, text = message
    assert subject == f"SpicyStock watch: {len(keys)} alerts: {result['alerts'][0]['subject'][len('SpicyStock watch: '):]}, " \
                      f"and {len(keys) - 1} more"
    for alert in result["alerts"]:
        assert f"Alert key: {alert['key']}." in text and html.escape(alert["subject"]) in text
    assert text.count("Watch clock:") == 1
    assert sorted(json.loads(ledger.read_text())["sent"]) == sorted(keys)


def test_a_refused_message_is_not_remembered_even_when_the_run_writes_the_ledger_for_a_clear(record, tmp_path,
                                                                                             monkeypatch):
    """A run that records a clear writes the ledger; a message the same run could not send is not in it, and the
    next run mails it."""
    deliveries(monkeypatch)
    ledger = tmp_path / "ledger.json"
    now = datetime(2026, 12, 1, 14, 27, tzinfo=UTC)
    watch_key = sw._alert("scheduler:watch:not_started", "words", None)
    sw.send([watch_key], now, ledger)
    refused = deliveries(monkeypatch, fail={"evening"})
    evening_key = sw._alert("evening:not_published:2026-12-01", "words", None)
    out = sw.send([evening_key], now + timedelta(hours=1), ledger, cleared=["scheduler:watch:not_started"])
    assert out["failed"] and out["cleared"] == ["scheduler:watch:not_started"] and out["ledger_written"] is True
    held = json.loads(ledger.read_text())
    assert "evening:not_published:2026-12-01" not in held["sent"] and refused == []
    again = deliveries(monkeypatch)
    assert sw.send([evening_key], now + timedelta(hours=2), ledger)["mailed"] == ["evening:not_published:2026-12-01"]
    assert len(again) == 1


def test_a_token_in_the_environment_is_what_the_watch_lists_runs_with(record, tmp_path, monkeypatch):
    asked = []

    def send(self, method, path, body=None):
        asked.append((method, path, self.token))
        return 200, json.dumps({"total_count": 0, "workflow_runs": []}).encode()
    monkeypatch.setattr(ds.GitHub, "send", send)
    docs = docs_with(tmp_path, record)
    assert sw.github_from({}) is None and sw.github_from({"GITHUB_TOKEN": "  "}) is None
    sw.main(["--docs", str(docs), "--now", STARTED_BY.isoformat()], env={"GITHUB_TOKEN": "synthetic-token"})
    assert {method for method, _, _ in asked} == {"GET"} and {token for _, _, token in asked} == {"synthetic-token"}
    assert all("/actions/workflows/" in path and "branch=main" in path for _, path, _ in asked) and len(asked) == 3
    asked.clear()
    sw.main(["--docs", str(docs), "--now", STARTED_BY.isoformat()], env={})
    assert asked == []                                  # no token: nothing is asked
