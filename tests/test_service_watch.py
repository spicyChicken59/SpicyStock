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
    assert "The on-time dispatcher started its evening, and it was still not on main at" in out["sentence"]
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
      evening_run(EVENING_FIRST_SLOT + timedelta(hours=2), id=7003, conclusion="timed_out")],
     RETRY + timedelta(hours=1), sw.FAILED, "evening:failed:2026-09-11"),           # every run failed
    ([evening_run(EVENING_FIRST_SLOT + timedelta(minutes=1), conclusion="failure", **DISPATCH),
      evening_run(EVENING_FIRST_SLOT + timedelta(hours=1), id=7002, status="in_progress", conclusion=None)],
     RETRY, sw.ON_TIME, None),                                                     # one still in progress
])
def test_the_evenings_scheduler_answer_for_an_unpublished_session(record, runs, now, judgement, key):
    out = sw.judge_evening(record, now, runs, None)
    assert (out["about"], out["session"], out["judgement"], out["key"]) == ("session", "2026-09-11", judgement, key)
    assert out["alert"] is (key is not None)
    assert out["first_slot_at"] == "2026-09-11T18:20:00-04:00" and out["started_by_at"] == "2026-09-11T18:50:00-04:00"
    if judgement == sw.ON_TIME:
        assert out["on_time_run"] == runs[0]["id"]


def test_an_unreadable_listing_is_unknown_and_never_an_alert(record):
    out = sw.judge_evening(record, RETRY, None, "the run listing answered HTTP 403")
    assert (out["judgement"], out["alert"], out["key"]) == (sw.UNKNOWN, False, None)
    assert "HTTP 403" in out["sentence"]


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


@pytest.mark.parametrize("runs,judgement,key", [
    ([run(event="workflow_dispatch", display_title=sw.WATCH_DISPATCH_TITLE, created_at=WATCH_SLOT)], sw.ON_TIME, None),
    ([run(event="workflow_dispatch", display_title=sw.WATCH_DISPATCH_TITLE,
          created_at=WATCH_SLOT + timedelta(minutes=ds.DUE_MINUTES) - SECOND, conclusion="failure")], sw.ON_TIME, None),
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
])
def test_a_listing_that_cannot_be_read_is_unknown_for_that_workflow_alone(record, tmp_path, raises, words):
    docs = docs_with(tmp_path, record)
    out = sw.watch(docs, LIMIT - timedelta(hours=2), github=Listing(raises=raises))
    for name in ("evening", "morning", "watch"):
        assert out["scheduler"][name]["judgement"] == sw.UNKNOWN and words in out["scheduler"][name]["sentence"]
    assert not [a for a in out["alerts"] if a["key"].startswith("scheduler:")]
    assert out["evening"]["judgement"] == sw.NOT_PUBLISHED                        # the file answers stand


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


def test_an_unknown_evening_is_its_own_exit_code(record, tmp_path, bound_handoff):
    bare = copy.deepcopy(record)
    del bare["run"]["calendar"]
    out = sw.watch(docs_with(tmp_path, bare, handoff_files=False), ALERT - SECOND)
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


def deliveries(monkeypatch, fail: set | None = None):
    from src import report
    sent = []

    def deliver(subject, body, attachments=None):
        if fail and any(word in subject for word in fail):
            raise RuntimeError("SYNTHETIC: the transport refused")
        sent.append((subject, body))
        return {"id": "x"}
    monkeypatch.setattr(report, "deliver", deliver)
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
    ("scheduler:evening:started_late", "SpicyStock watch: the evening was not started by the on-time dispatcher"),
    ("scheduler:morning:started_late", "SpicyStock watch: the morning check was not started by the on-time dispatcher"),
    ("scheduler:watch:not_started", "SpicyStock watch: the watch was not started at its slot"),
    ("record:unreadable:absent", sw.UNREADABLE_SUBJECT),
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


# ----------------------------------------------------------------- ledger ---
def main_mail(docs, now, ledger, env=None, extra=()):
    return sw.main(["--docs", str(docs), "--now", now.isoformat(), "--mail", "--ledger", str(ledger), *extra],
                   env=env or {})


def test_a_second_and_third_run_mail_nothing_and_are_green(record, tmp_path, monkeypatch, capsys):
    sent = deliveries(monkeypatch)
    docs, ledger = docs_with(tmp_path, record), tmp_path / "cache" / "ledger.json"
    near = LIMIT - timedelta(hours=2)
    assert main_mail(docs, near, ledger) == sw.EXIT_ALERT and len(sent) == 1
    for later in (near + timedelta(minutes=30), near + timedelta(hours=1)):
        assert main_mail(docs, later, ledger) == sw.EXIT_OK
    assert len(sent) == 1
    err = capsys.readouterr().err
    assert f"Not mailed again: evening:not_published:2026-09-11 was mailed at {near.isoformat()}." in err
    assert json.loads(ledger.read_text()) == {"version": sw.LEDGER_VERSION,
                                              "sent": {"evening:not_published:2026-09-11": near.isoformat()}}


def test_a_change_of_state_mails_once_more(record, tmp_path, monkeypatch):
    sent = deliveries(monkeypatch)
    docs, ledger = docs_with(tmp_path, record), tmp_path / "ledger.json"
    for now in (LIMIT - timedelta(hours=1), LIMIT - SECOND, LIMIT, LIMIT + timedelta(hours=1)):
        main_mail(docs, now, ledger)
    assert [s for s, _ in sent] == ["SpicyStock watch: 2026-09-11 is not published",
                                    "SpicyStock watch: 2026-09-11 was not published before the next open"]


@pytest.mark.parametrize("spoil", [
    lambda p, now: p.unlink(),
    lambda p, now: p.write_text("{not json"),
    lambda p, now: p.write_text(json.dumps({"version": 2, "sent": {}})),
    lambda p, now: p.write_text(json.dumps({"version": True, "sent": {}})),
    lambda p, now: p.write_text(json.dumps({"version": 1, "sent": []})),
    lambda p, now: p.write_text(json.dumps({"version": 1, "sent": {"evening:not_published:2026-09-11":
                                                                    (now + timedelta(minutes=1)).isoformat()}})),
    lambda p, now: p.write_text(json.dumps({"version": 1, "sent": {"Mail to owner@example.com": now.isoformat()}})),
    lambda p, now: p.write_text(json.dumps({"version": 1, "sent": {"evening:not_published:2026-09-11": "yesterday"}})),
    lambda p, now: p.write_text(json.dumps({"version": 1, "sent": {}, "body": "<p>hi</p>"})),
    lambda p, now: p.write_bytes(b" " * (sw.MAX_LEDGER_BYTES + 1)),
])
def test_a_ledger_that_cannot_be_read_as_this_watchs_reads_empty_and_mails_again(record, tmp_path, monkeypatch, spoil):
    sent = deliveries(monkeypatch)
    docs, ledger = docs_with(tmp_path, record), tmp_path / "ledger.json"
    first = LIMIT - timedelta(hours=2)
    main_mail(docs, first, ledger)
    spoil(ledger, first + timedelta(minutes=30))
    assert main_mail(docs, first + timedelta(minutes=30), ledger) == sw.EXIT_ALERT
    assert len(sent) == 2


def test_a_linked_ledger_is_not_read(record, tmp_path, monkeypatch):
    sent = deliveries(monkeypatch)
    docs, real, ledger = docs_with(tmp_path, record), tmp_path / "real.json", tmp_path / "ledger.json"
    first = LIMIT - timedelta(hours=2)
    main_mail(docs, first, real)
    ledger.symlink_to(real)
    assert sw.read_ledger(ledger, first) == {} and len(sw.read_ledger(real, first)) == 1
    main_mail(docs, first + timedelta(minutes=5), ledger)
    assert len(sent) == 2


def test_a_mail_the_transport_refuses_is_not_remembered(record, tmp_path, monkeypatch, capsys):
    sent = deliveries(monkeypatch, fail={"is not published"})
    docs, ledger = docs_with(tmp_path, record), tmp_path / "ledger.json"
    near = LIMIT - timedelta(hours=2)
    assert main_mail(docs, near, ledger) == sw.EXIT_ALERT            # a failed mail is red
    assert sent == [] and not ledger.exists()                         # written only after a mail is accepted
    assert "Mail failed for evening:not_published:2026-09-11 (RuntimeError)" in capsys.readouterr().err
    sent = deliveries(monkeypatch)
    assert main_mail(docs, near + timedelta(minutes=5), ledger) == sw.EXIT_ALERT and len(sent) == 1


def test_a_key_past_its_repeat_days_is_mailed_again_and_old_entries_are_pruned(record, tmp_path, monkeypatch):
    sent = deliveries(monkeypatch)
    ledger = tmp_path / "ledger.json"
    first = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    alert = sw._alert("scheduler:watch:not_started", "words", None)
    gone = sw._alert("evening:not_published:2026-08-01", "words", None)
    sw.send([alert, gone], first, ledger)
    assert len(sent) == 2
    edge = first + timedelta(days=sw.REPEAT_DAYS)
    assert sw.send([alert], edge - SECOND, ledger)["dropped"]                  # a standing key: dropped for a week
    again = sw.send([alert], edge, ledger)
    assert again["mailed"] == ["scheduler:watch:not_started"] and len(sent) == 3
    assert json.loads(ledger.read_text())["sent"] == {"scheduler:watch:not_started": edge.isoformat()}


def test_the_ledger_holds_keys_and_instants_only(record, tmp_path, monkeypatch):
    monkeypatch.setenv("EMAIL_TO", "owner@example.com")
    deliveries(monkeypatch)
    docs, ledger = docs_with(tmp_path, record), tmp_path / "ledger.json"
    main_mail(docs, LIMIT - timedelta(hours=2), ledger)
    main_mail(docs, CUTOFF + timedelta(hours=1), ledger)
    text = ledger.read_text()
    value = json.loads(text)
    assert set(value) == {"version", "sent"}
    assert all(sw.KEY_PATTERN.fullmatch(k) and sw._instant(v) for k, v in value["sent"].items())
    assert "@" not in text and "<p>" not in text and "only_if_unpublished" not in text


def test_the_workflow_is_told_to_save_the_ledger_only_when_it_was_written(record, tmp_path, monkeypatch):
    deliveries(monkeypatch)
    docs, ledger, output = docs_with(tmp_path, record), tmp_path / "ledger.json", tmp_path / "github-output"
    near = LIMIT - timedelta(hours=2)
    main_mail(docs, near, ledger, env={"GITHUB_OUTPUT": str(output)})
    assert output.read_text() == "ledger=written\n"
    main_mail(docs, near + timedelta(minutes=5), ledger, env={"GITHUB_OUTPUT": str(output)})     # a repeat: dropped
    assert output.read_text() == "ledger=written\n"


def test_an_unreadable_record_is_mailed_once_per_bytes(tmp_path, monkeypatch):
    sent = deliveries(monkeypatch)
    docs, ledger = tmp_path / "docs", tmp_path / "ledger.json"
    docs.mkdir()
    (docs / sw.DATA_FILE).write_text("{truncated")
    now = datetime(2026, 9, 14, 11, 30, tzinfo=UTC)
    assert main_mail(docs, now, ledger) == sw.EXIT_UNKNOWN
    assert main_mail(docs, now + timedelta(days=1), ledger) == sw.EXIT_OK          # the same bytes: dropped, green
    (docs / sw.DATA_FILE).write_text("{truncated again")
    assert main_mail(docs, now + timedelta(days=2), ledger) == sw.EXIT_UNKNOWN     # other bytes: another key
    (docs / sw.DATA_FILE).unlink()
    assert main_mail(docs, now + timedelta(days=3), ledger) == sw.EXIT_UNKNOWN     # absent
    assert len(sent) == 3
    assert "record:unreadable:absent" in json.loads(ledger.read_text())["sent"]


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
