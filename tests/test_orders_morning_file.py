"""The morning go/cancel file is always there, and its absence cancels everything.

Before 25 November 2026 ``orders-morning.json`` existed only after a morning
run whose own receipt had landed: the evening removed the previous one, and on
a morning with no check (GitHub's scheduled runs start hours late) an
execution agent found no file at all. The owner's decision: always publish it,
and cancel every ticket if it is missing. These tests hold

* the three ways the file comes to be (``pending`` from the evening,
  ``checked`` and ``no_check`` from a morning) and what each may say;
* ``orders.entry_decisions()``, the rule an agent applies, over every state of
  the file, a missing one among them;
* the morning publisher, which now writes a file whatever the receipt on main
  says, and the workflow's after-window job.
"""
import copy
import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from src import orders
from tests.test_orders import (MORNING, PUBLICATION, allowed_orders, docs_with, git, golden_orders, page,
                               receipt_for)
from tools import publish_morning

ROOT = Path(__file__).resolve().parents[1]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def go_night() -> tuple[bytes, dict]:
    """``orders.json`` for the fixture night on which trading is allowed and NVDA is go."""
    raw = orders.encode(orders.build(page("next")))
    doc = orders.validate(raw)
    assert doc["trade_allowed"] is True and [t["status"] for t in doc["tickets"]] == ["go", "human_review"]
    return raw, doc


def checked_for(raw: bytes, doc: dict, **receipt) -> bytes:
    """A checked morning file for ``raw``: one receipt row, for its first ticket."""
    out = orders.encode(orders.build_morning(raw, receipt_for(doc, doc["tickets"][0], **receipt)))
    orders.validate(out, "orders_morning")
    return out


def reseal(doc: dict, **changes) -> bytes:
    return orders.encode(orders.sealed({**{k: v for k, v in doc.items() if k != "content_sha256"}, **changes}))


# --------------------------------------------- the three ways it comes to be --
def test_the_evenings_file_cancels_every_ticket_until_a_morning_check_runs():
    raw, doc = go_night()
    pending = orders.pending_morning(raw)
    assert orders.problems(pending, "orders_morning") == []
    assert (pending["status"], pending["cancel_all"], pending["cancel_all_reason"]) == \
        ("pending", True, "morning_check_pending")
    # the night allows trading and a ticket is go: the evening's file cancels them all the same
    assert [(t["symbol"], t["decision"], t["reasons"]) for t in pending["tickets"]] == [
        ("NVDA", "cancel", ["morning_check_pending"]), ("COIL", "cancel", ["morning_check_pending"])]
    assert pending["summary"] == {"tickets": 2, "go": 0, "cancel": 2}
    assert pending["orders_sha256"] == sha(raw) and pending["data_sha256"] == doc["source"]["data_sha256"]
    assert [t["ticket_sha256"] for t in pending["tickets"]] == [t["content_sha256"] for t in doc["tickets"]]
    assert [t["valid_until"] for t in pending["tickets"]] == [t["entry"]["valid_until"] for t in doc["tickets"]]
    for key in ("morning_sha256", "morning_status", "morning_generated_at", "observation_run_id"):
        assert pending[key] is None
    assert pending["morning_bound"] is False and pending["mode"] == doc["mode"] == "paper"
    assert orders.encode(pending) == orders.encode(orders.pending_morning(raw))          # no clock


def test_a_morning_with_no_receipt_bound_to_the_record_cancels_every_ticket():
    raw, doc = go_night()
    yesterdays = (MORNING / "observed.json").read_bytes()            # bound to another publication
    for receipt in (None, yesterdays, b'{"publication": null, "rows": []}', b"[]"):
        out = orders.build_morning(raw, receipt)
        assert orders.problems(out, "orders_morning") == []
        assert (out["status"], out["cancel_all"], out["cancel_all_reason"]) == ("no_check", True, "no_morning_check")
        assert [t["decision"] for t in out["tickets"]] == ["cancel", "cancel"] and out["summary"]["go"] == 0
        assert all("no_morning_check" in t["reasons"] and t["observed"] is None for t in out["tickets"])
        # which receipt was read and found unbound is recorded; nothing of it is carried as this record's
        assert out["morning_sha256"] == (sha(receipt) if receipt is not None else None)
        assert out["morning_bound"] is False and out["morning_status"] is None and out["observation_run_id"] is None


def test_a_morning_with_a_receipt_bound_to_the_record_is_a_check_and_only_then_can_a_ticket_go():
    raw, doc = go_night()
    out = orders.validate(checked_for(raw, doc), "orders_morning")
    assert (out["status"], out["cancel_all"], out["cancel_all_reason"], out["morning_bound"]) == \
        ("checked", False, None, True)
    assert [(t["symbol"], t["decision"]) for t in out["tickets"]] == [("NVDA", "go"), ("COIL", "cancel")]
    assert out["summary"] == {"tickets": 2, "go": 1, "cancel": 1}
    assert set(orders.MORNING_STATUSES) == {"pending", "checked", "no_check"}


def test_the_golden_files_carry_one_file_of_each_status():
    golden = {name: json.loads((ROOT / "tests/fixtures/orders/morning" / f"{name}.json").read_bytes())
              for name in ("pending", "no-check", "observed")}
    assert [golden[n]["status"] for n in ("pending", "no-check", "observed")] == ["pending", "no_check", "checked"]
    assert [golden[n]["cancel_all"] for n in ("pending", "no-check", "observed")] == [True, True, False]


# ------------------------------------------------- a file that says more ---
@pytest.mark.parametrize("label, change, problem", [
    ("a pending file that is not cancel-all", {"cancel_all": False}, "cancel_all and its reason"),
    ("a pending file with no reason", {"cancel_all_reason": None}, "cancel_all and its reason"),
    ("a pending file with a no-check reason", {"cancel_all_reason": "no_morning_check"},
     "the cancel-all reason is not one this status gives"),
    ("a pending file that claims a receipt", {"morning_bound": True}, "a pending file names no morning receipt"),
    ("a pending file that names a receipt's hash", {"morning_sha256": "0" * 64},
     "a pending file names no morning receipt"),
    ("a pending file that carries a receipt's status", {"morning_status": "observed"},
     "bound to no receipt carries no receipt's fields"),
])
def test_a_resealed_pending_file_that_says_more_than_pending_is_refused(label, change, problem):
    raw, _ = go_night()
    pending = orders.pending_morning(raw)
    found = orders.problems(json.loads(reseal(pending, **change)), "orders_morning")
    assert any(problem in f for f in found), (label, found)
    with pytest.raises(ValueError, match="fails its schema"):
        orders.validate(reseal(pending, **change), "orders_morning")


def with_go(doc: dict) -> dict:
    """``doc`` with its first ticket made go and its summary counted again: only the status rule is left to refuse it."""
    doc = copy.deepcopy(doc)
    doc["tickets"][0].update(decision="go", reasons=[])
    doc["summary"] = {"tickets": len(doc["tickets"]), "go": 1, "cancel": len(doc["tickets"]) - 1}
    return doc


def test_no_ticket_is_go_in_a_file_that_is_not_a_check():
    raw, _ = go_night()
    for unchecked in (orders.pending_morning(raw), orders.build_morning(raw, None)):
        forged = json.loads(reseal(with_go(unchecked)))
        found = orders.problems(forged, "orders_morning")
        assert "a ticket is go in a morning file that cancels every ticket" in found
    pending = orders.pending_morning(raw)
    other = copy.deepcopy(pending)
    other["tickets"][0]["reasons"] = ["morning_check_pending", "stale_data"]
    assert "a pending morning file gives a ticket another reason than that it is pending" in \
        orders.problems(json.loads(reseal(other)), "orders_morning")


@pytest.mark.parametrize("label, change, problem", [
    ("a checked file that cancels all", {"cancel_all": True}, "cancel_all and its reason"),
    ("a checked file with a cancel-all reason", {"cancel_all_reason": "no_morning_check"}, "cancel_all and its reason"),
    ("a checked file bound to no receipt", {"morning_bound": False}, "checked exactly when it is bound"),
    ("an unknown status", {"status": "ready"}, "status"),
    ("a status dropped to pending over a real check", {"status": "pending"}, "cancel_all and its reason"),
])
def test_a_resealed_checked_file_whose_status_is_not_its_fields_is_refused(label, change, problem):
    raw, doc = go_night()
    checked = json.loads(checked_for(raw, doc))
    found = orders.problems(json.loads(reseal(checked, **change)), "orders_morning")
    assert any(problem in f for f in found), (label, found)


@pytest.mark.parametrize("field", ["status", "cancel_all", "cancel_all_reason"])
def test_the_schema_requires_the_three_fields_an_agent_reads_first(field):
    raw, _ = go_night()
    pending = orders.pending_morning(raw)
    pending.pop(field)
    assert orders.problems(json.loads(reseal(pending)), "orders_morning")
    defs = orders.schema()["$defs"]["orders_morning"]
    assert field in defs["required"]
    assert defs["properties"]["status"]["enum"] == list(orders.MORNING_STATUSES)
    reasons = defs["properties"]["cancel_all_reason"]["enum"]
    assert len(reasons) == len(orders.CANCEL_ALL_REASONS) + 1 and set(reasons) == {None, *orders.CANCEL_ALL_REASONS}


def test_a_file_for_an_earlier_versions_orders_is_never_live():
    earlier = json.loads(golden_orders())
    earlier["version"] = orders.VERSION - 1
    raw = orders.encode(orders.sealed(earlier))
    out = orders.earlier_version_morning(raw)
    assert orders.problems(out, "orders_morning") == [] and out["mode"] == "paper"
    assert "a morning file for an earlier version's orders.json is never live" in \
        orders.problems(json.loads(reseal(out, mode="live")), "orders_morning")


# ------------------------------------------------------ the rule an agent applies --
def before(doc: dict, minutes: int = 10) -> datetime:
    return datetime.fromisoformat(doc["tickets"][0]["entry"]["valid_until"]) - timedelta(minutes=minutes)


def decisions(raw, morning_raw, now) -> dict:
    out = orders.entry_decisions(raw, morning_raw, now)
    return {t["symbol"]: (t["decision"], t["reason"]) for t in out["tickets"].values()}


def test_orders_json_states_the_rule_and_the_module_applies_it():
    raw, doc = go_night()
    assert doc["morning_rule"] == orders.MORNING_RULE == {
        "file": "orders-morning.json", "bound_by": "orders_sha256", "required_status": "checked",
        "required_decision": "go", "deadline_field": "valid_until", "otherwise": "cancel",
        "missing_or_unbound": "cancel_all"}
    forged = copy.deepcopy(doc)
    forged["morning_rule"]["missing_or_unbound"] = "go"
    assert orders.problems(json.loads(reseal(forged)))              # the schema holds the rule to these words


def test_a_ticket_goes_only_under_a_checked_file_that_says_go_before_its_deadline():
    raw, doc = go_night()
    checked = checked_for(raw, doc)
    out = orders.entry_decisions(raw, checked, before(doc))
    assert (out["cancel_all"], out["cancel_all_reason"], out["mode"]) == (False, None, "paper")
    # COIL is held for review in orders.json: no morning file can make it go
    assert doc["tickets"][1]["status"] != "go"
    assert decisions(raw, checked, before(doc)) == {"NVDA": ("go", None), "COIL": ("cancel", "ticket_not_go")}
    assert set(out["tickets"]) == {t["id"] for t in doc["tickets"]}


def test_a_missing_file_cancels_every_ticket():
    raw, doc = go_night()
    out = orders.entry_decisions(raw, None, before(doc))
    assert (out["cancel_all"], out["cancel_all_reason"]) == (True, "morning_file_missing")
    assert decisions(raw, None, before(doc)) == {"NVDA": ("cancel", "morning_file_missing"),
                                                 "COIL": ("cancel", "morning_file_missing")}


def test_a_file_that_cannot_be_read_cancels_every_ticket():
    raw, doc = go_night()
    checked = json.loads(checked_for(raw, doc))
    unsealed = orders.encode({**checked, "status": "checked", "summary": {"tickets": 2, "go": 2, "cancel": 0}})
    deep = b"[" * 200_000 + b"]" * 200_000
    for bad in (b"", b"{", b"null", b"[]", b'{"status": "checked", "cancel_all": false}', unsealed,
                reseal(checked, cancel_all=True), reseal(with_go(orders.pending_morning(raw))),
                b"x" * (orders.MAX_BYTES + 1), deep[:orders.MAX_BYTES]):
        out = orders.entry_decisions(raw, bad, before(doc))
        assert (out["cancel_all"], out["cancel_all_reason"]) == (True, "morning_file_unreadable"), bad[:40]
        assert {t["decision"] for t in out["tickets"].values()} == {"cancel"}


def test_a_file_bound_to_other_orders_cancels_every_ticket():
    raw, doc = go_night()
    other_raw, other = allowed_orders()                              # another night's orders, its ticket go
    theirs = orders.encode(orders.build_morning(other_raw, receipt_for(other, other["tickets"][0])))
    assert orders.validate(theirs, "orders_morning")["summary"]["go"] == 1
    out = orders.entry_decisions(raw, theirs, before(doc))
    assert (out["cancel_all"], out["cancel_all_reason"]) == (True, "morning_file_unbound")
    # and a checked file whose binding alone was changed to these orders does not list these tickets' bytes
    rebound = reseal(json.loads(theirs), orders_sha256=sha(raw))
    assert decisions(raw, rebound, before(doc)) == {"NVDA": ("cancel", "ticket_not_listed"),
                                                    "COIL": ("cancel", "ticket_not_go")}


def test_a_pending_or_no_check_file_cancels_every_ticket():
    raw, doc = go_night()
    for unchecked in (orders.pending_morning(raw), orders.build_morning(raw, None),
                      orders.build_morning(raw, (MORNING / "observed.json").read_bytes())):
        out = orders.entry_decisions(raw, orders.encode(unchecked), before(doc))
        assert (out["cancel_all"], out["cancel_all_reason"]) == (True, "morning_not_checked")
        assert {t["decision"] for t in out["tickets"].values()} == {"cancel"}


def test_a_ticket_the_file_does_not_list_or_lists_other_bytes_of_is_cancelled():
    raw, doc = go_night()
    checked = json.loads(checked_for(raw, doc))
    unlisted = copy.deepcopy(checked)
    unlisted["tickets"] = unlisted["tickets"][1:]
    unlisted["summary"] = {"tickets": 1, "go": 0, "cancel": 1}
    assert decisions(raw, reseal(unlisted), before(doc))["NVDA"] == ("cancel", "ticket_not_listed")
    other_bytes = copy.deepcopy(checked)
    other_bytes["tickets"][0]["ticket_sha256"] = "0" * 64
    assert decisions(raw, reseal(other_bytes), before(doc))["NVDA"] == ("cancel", "ticket_not_listed")


def test_the_deadline_is_the_tickets_own_valid_until_and_an_unreadable_clock_cancels():
    raw, doc = go_night()
    checked = checked_for(raw, doc)
    until = datetime.fromisoformat(doc["tickets"][0]["entry"]["valid_until"])
    assert decisions(raw, checked, until - timedelta(seconds=1))["NVDA"] == ("go", None)
    assert decisions(raw, checked, until)["NVDA"] == ("cancel", "past_valid_until")
    assert decisions(raw, checked, (until - timedelta(seconds=1)).astimezone(timezone.utc))["NVDA"] == ("go", None)
    assert decisions(raw, checked, until.replace(tzinfo=None))["NVDA"] == ("cancel", "past_valid_until")
    assert decisions(raw, checked, "2026-09-14T09:00:00-04:00")["NVDA"] == ("cancel", "past_valid_until")
    assert decisions(raw, checked, None)["NVDA"] == ("cancel", "past_valid_until")


def test_every_reason_the_rule_gives_is_named_and_orders_json_itself_must_be_valid():
    raw, doc = go_night()
    assert list(orders.ENTRY_REASONS) == ["orders_earlier_version", "night_not_allowed", "morning_file_missing",
                                          "morning_file_unreadable", "morning_file_unbound", "morning_not_checked",
                                          "ticket_not_go", "ticket_not_listed", "ticket_cancelled",
                                          "past_valid_until"]
    with pytest.raises(ValueError):
        orders.entry_decisions(b"{}", None, before(doc))


def test_the_decide_command_prints_the_rule_applied_to_the_files_on_disk(tmp_path, capsys):
    docs = docs_with(tmp_path, "next")
    orders.write_publication(docs)
    raw = (docs / orders.FILE).read_bytes()
    doc = json.loads(raw)
    now = before(doc).isoformat()
    assert orders.main(["decide", "--docs", str(docs), "--now", now]) == 0
    out = json.loads(capsys.readouterr().out)
    assert (out["cancel_all"], out["cancel_all_reason"]) == (True, "morning_not_checked")     # the evening's file
    (docs / orders.MORNING_FILE).unlink()
    assert orders.main(["decide", "--docs", str(docs), "--now", now]) == 0
    assert json.loads(capsys.readouterr().out)["cancel_all_reason"] == "morning_file_missing"
    (docs / orders.MORNING_FILE).write_bytes(checked_for(raw, doc))
    assert orders.main(["decide", "--docs", str(docs), "--now", now]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["cancel_all"] is False and out["tickets"]["2026-09-11:burst:NVDA"]["decision"] == "go"
    with pytest.raises(ValueError, match="--now"):
        orders.main(["decide", "--docs", str(docs), "--now", "2026-09-14T09:00:00"])


# -------------------------------------------------- the evening's install ---
def test_the_evening_keeps_its_own_records_morning_check_and_replaces_any_other(tmp_path):
    docs = docs_with(tmp_path, "next")
    assert orders.write_publication(docs)["morning"] == "pending"
    raw = (docs / orders.FILE).read_bytes()
    receipt = receipt_for(json.loads(raw), json.loads(raw)["tickets"][0])
    checked = orders.encode(orders.build_morning(raw, receipt))
    (docs / orders.MORNING_FILE).write_bytes(checked)
    (docs / orders.MORNING_RECEIPT).write_bytes(receipt)             # the receipt it was checked against, on main
    # the same record installed again to the same bytes (a restamp, a retried step) keeps its check
    assert orders.write_publication(docs)["morning"] == "kept"
    assert (docs / orders.MORNING_FILE).read_bytes() == checked and orders.check(docs) == []
    # a file that is not this schema's, or bound to these orders by its field alone and unsealed, is replaced
    for standing in (b"{", b"null", json.dumps({"orders_sha256": sha(raw)}).encode(),
                     orders.encode({**json.loads(checked), "summary": {"tickets": 2, "go": 2, "cancel": 0}})):
        (docs / orders.MORNING_FILE).write_bytes(standing)
        assert orders.write_publication(docs)["morning"] == "pending"
        assert (docs / orders.MORNING_FILE).read_bytes() == orders.encode(orders.pending_morning(raw))


def test_a_new_record_never_inherits_the_last_records_morning_check(tmp_path):
    docs = docs_with(tmp_path, "next")
    orders.write_publication(docs)
    raw = (docs / orders.FILE).read_bytes()
    (docs / orders.MORNING_FILE).write_bytes(checked_for(raw, json.loads(raw)))
    (docs / "data.json").write_bytes(page("revised"))                # the same session, published again
    assert orders.write_publication(docs)["morning"] == "pending"
    revised = (docs / orders.FILE).read_bytes()
    assert revised != raw
    assert json.loads((docs / orders.MORNING_FILE).read_bytes())["orders_sha256"] == sha(revised)
    assert orders.check(docs) == []


def test_the_evening_refuses_a_linked_morning_file(tmp_path):
    docs = docs_with(tmp_path, "next")
    (tmp_path / "elsewhere.json").write_text("{}")
    (docs / orders.MORNING_FILE).symlink_to(tmp_path / "elsewhere.json")
    with pytest.raises(ValueError, match="must not be a symlink"):
        orders.write_publication(docs)
    assert (tmp_path / "elsewhere.json").read_text() == "{}" and not (docs / orders.FILE).exists()
    # a link to a file that IS these orders' own check is refused too: it would otherwise be kept unread by the install
    (docs / orders.MORNING_FILE).unlink()
    orders.write_publication(docs)
    raw = (docs / orders.FILE).read_bytes()
    (tmp_path / "elsewhere.json").write_bytes(checked_for(raw, json.loads(raw)))
    (docs / orders.MORNING_FILE).unlink()
    (docs / orders.MORNING_FILE).symlink_to(tmp_path / "elsewhere.json")
    with pytest.raises(ValueError, match="orders-morning.json must not be a symlink"):
        orders.write_publication(docs)


def test_the_check_names_a_missing_or_foreign_morning_file(tmp_path):
    docs = docs_with(tmp_path, "next")
    orders.write_publication(docs)
    assert orders.check(docs) == []
    pending = (docs / orders.MORNING_FILE).read_bytes()
    (docs / orders.MORNING_FILE).unlink()
    assert orders.check(docs) == [
        "orders-morning.json is missing beside orders.json: every ticket is cancelled until it is written"]
    other_raw, _ = allowed_orders()
    (docs / orders.MORNING_FILE).write_bytes(orders.encode(orders.pending_morning(other_raw)))
    assert orders.check(docs) == ["orders-morning.json is not bound to orders.json"]
    (docs / orders.MORNING_FILE).write_bytes(pending)
    assert orders.check(docs) == []


def test_a_night_that_cannot_write_the_handoff_leaves_no_morning_file_behind(tmp_path, caplog):
    from src import pipeline
    caplog.set_level("INFO")
    docs = docs_with(tmp_path, "next")
    pipeline.publish_orders(docs)
    assert "morning file pending" in caplog.text and (docs / orders.MORNING_FILE).exists()
    (docs / "data.json").write_bytes(b'{"not": "a record"}')
    pipeline.publish_orders(docs)
    assert not any((docs / n).exists() for n in (orders.FILE, orders.POSITIONS_FILE, orders.MORNING_FILE))


# ----------------------------------------------------- the morning publisher --
@pytest.fixture
def repository(tmp_path):
    """A main branch carrying the pinned publication, its orders.json and the evening's pending file."""
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    root = tmp_path / "checkout"
    subprocess.run(["git", "clone", str(remote), str(root)], check=True, capture_output=True)
    git(root, "checkout", "-b", "main")
    git(root, "config", "user.name", "test")
    git(root, "config", "user.email", "test@example.invalid")
    (root / "docs").mkdir()
    (root / "docs" / "data.json").write_bytes(PUBLICATION)
    (root / "docs" / "orders.json").write_bytes(golden_orders())
    (root / "docs" / "orders-morning.json").write_bytes(orders.encode(orders.pending_morning(golden_orders())))
    git(root, "add", ".")
    git(root, "commit", "-m", "the evening")
    git(root, "push", "-u", "origin", "main")
    return root


def commit(root: Path, message: str, **files) -> None:
    for name, raw in files.items():
        path = root / "docs" / name
        if raw is None:
            path.unlink()
        else:
            path.write_bytes(raw)
    git(root, "add", "-A")
    git(root, "commit", "-m", message)
    git(root, "push", "origin", "main")


def served(root: Path) -> dict:
    git(root, "fetch", "origin")
    return json.loads(git(root, "show", "origin/main:docs/orders-morning.json"))


def publish(root: Path, **kwargs) -> str:
    return publish_morning.publish_orders(root, ref="refs/heads/main", run_id="a-run", **kwargs)


def test_with_no_receipt_on_main_the_morning_still_publishes_and_cancels_every_ticket(repository):
    assert served(repository)["status"] == "pending"
    assert publish(repository) == "published"
    out = served(repository)
    assert (out["status"], out["cancel_all"], out["cancel_all_reason"]) == ("no_check", True, "no_morning_check")
    assert out["morning_sha256"] is None and out["orders_sha256"] == sha(golden_orders())
    assert git(repository, "diff", "--name-only", "HEAD", "origin/main").decode().split() == ["docs/orders-morning.json"]
    assert publish(repository) == "unchanged"


def test_with_yesterdays_receipt_on_main_the_morning_publishes_no_check(repository):
    yesterdays = (MORNING / "no-tickets.json").read_bytes()         # bound to another publication
    assert json.loads(yesterdays)["publication"]["data_sha256"] != sha(PUBLICATION)
    commit(repository, "an old receipt", **{"morning.json": yesterdays})
    assert publish(repository) == "published"
    out = served(repository)
    assert (out["status"], out["cancel_all_reason"], out["morning_bound"]) == ("no_check", "no_morning_check", False)
    assert out["morning_sha256"] == sha(yesterdays)


def test_with_this_records_receipt_on_main_the_morning_publishes_the_check(repository):
    receipt = (MORNING / "observed.json").read_bytes()
    commit(repository, "the receipt", **{"morning.json": receipt})
    assert publish(repository) == "published"
    out = served(repository)
    assert (out["status"], out["cancel_all"], out["morning_bound"]) == ("checked", False, True)
    assert orders.encode(out) == orders.encode(orders.build_morning(golden_orders(), receipt, PUBLICATION))


def test_a_tampered_receipt_bound_to_the_record_publishes_nothing_and_the_pending_file_stands(repository):
    receipt = json.loads((MORNING / "observed.json").read_bytes())
    receipt["rows"][0]["trade"]["price"] = 1.0
    commit(repository, "a tampered receipt", **{"morning.json": json.dumps(receipt).encode()})
    with pytest.raises(ValueError):
        publish(repository)
    assert served(repository)["status"] == "pending"                # every ticket still cancelled


def test_an_earlier_versions_orders_get_a_file_that_cancels_them_all(repository):
    earlier = json.loads(golden_orders())
    earlier["version"] = orders.VERSION - 1
    raw = orders.encode(orders.sealed(earlier))
    commit(repository, "an earlier version's evening", **{"orders.json": raw, "orders-morning.json": None,
                                                         "morning.json": (MORNING / "observed.json").read_bytes()})
    assert publish(repository) == "published"
    out = served(repository)
    assert (out["status"], out["cancel_all_reason"], out["tickets"], out["version"]) == \
        ("no_check", "orders_earlier_version", [], orders.VERSION)
    assert out["orders_sha256"] == sha(raw)
    assert publish(repository) == "unchanged"


def test_only_a_missing_or_unbound_orders_json_leaves_nothing_to_write(repository):
    commit(repository, "another record", **{"data.json": page("full")})
    assert publish(repository) == "orders_not_bound_to_record"
    assert served(repository)["status"] == "pending"                # untouched, and bound to no current record
    commit(repository, "no handoff", **{"orders.json": None})
    assert publish(repository) == "no_orders_on_main"


def cutoff() -> datetime:
    return datetime.fromisoformat(json.loads(PUBLICATION)["run"]["timing"]["cutoff_at"])


def test_the_after_window_job_writes_only_once_the_window_has_ended_on_its_own_session(repository):
    at = cutoff()
    assert publish(repository, closing=True, now=at - timedelta(seconds=1)) == "window_not_closed"
    assert publish(repository, closing=True, now=at + timedelta(days=1)) == "window_not_closed"
    assert publish(repository, closing=True, now=at - timedelta(days=1)) == "window_not_closed"
    assert served(repository)["status"] == "pending"                # nothing was written by any of them
    assert publish(repository, closing=True, now=at) == "published"
    assert served(repository)["status"] == "no_check"
    assert publish(repository, closing=True, now=at + timedelta(hours=5)) == "unchanged"


def test_the_after_window_job_keeps_a_check_made_inside_the_window(repository):
    receipt = (MORNING / "observed.json").read_bytes()
    commit(repository, "the receipt", **{"morning.json": receipt})
    assert publish(repository) == "published"
    checked = served(repository)
    assert publish(repository, closing=True, now=cutoff() + timedelta(hours=4)) == "unchanged"
    assert served(repository) == checked and checked["status"] == "checked"


@pytest.mark.parametrize("raw", [b"{}", b"[]", b'{"run": {"timing": null}}',
                                 b'{"run": {"timing": {"cutoff_at": "soon", "applicable_session": "2026-09-11"}}}',
                                 b'{"run": {"timing": {"cutoff_at": "2026-09-11T10:00:00", '
                                 b'"applicable_session": "2026-09-11"}}}'])
def test_a_record_whose_window_cannot_be_read_is_not_closed(raw):
    assert publish_morning.window_closed(raw, datetime(2026, 9, 11, 20, tzinfo=timezone.utc)) is False


def test_the_window_closes_at_the_cutoff_and_stays_closed_until_that_sessions_evening_slot():
    from src import delivery
    at = cutoff()
    assert publish_morning.window_closed(PUBLICATION, at) is True
    assert publish_morning.window_closed(PUBLICATION, at - timedelta(microseconds=1)) is False
    # a slot hours late is still closed, until the session's own evening slot: from 6:16 PM New York the
    # evening publishes the next record and its own pending file, and a late morning slot does not race it
    evening, _ = delivery.slots(at.astimezone(delivery.MARKET_TZ).date())
    assert evening.astimezone(delivery.MARKET_TZ).strftime("%H:%M") == "18:16"
    assert publish_morning.window_closed(PUBLICATION, evening - timedelta(microseconds=1)) is True
    assert publish_morning.window_closed(PUBLICATION, evening) is False
    # the next New York day is another session's morning
    assert publish_morning.window_closed(PUBLICATION, at + timedelta(days=1)) is False


@pytest.mark.parametrize("argv, closing", [(["orders"], False), (["orders", "--window-closed"], True)])
def test_the_command_passes_the_after_window_flag_to_the_publisher(argv, closing, monkeypatch, tmp_path, capsys):
    seen = []

    def publisher(root, **kwargs):
        seen.append(kwargs)
        return "window_not_closed" if kwargs["closing"] else "published"

    monkeypatch.setattr(publish_morning, "publish_orders", publisher)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_RUN_ID", "77")
    monkeypatch.setattr("sys.argv", ["publish_morning", *argv, "--root", str(tmp_path)])
    assert publish_morning.main() == 0
    assert seen == [{"ref": "refs/heads/main", "run_id": "77", "closing": closing}]
    assert ("window_not_closed" if closing else "published") in capsys.readouterr().out


# ----------------------------------------------------------- the workflow ---
def test_the_guard_tells_the_workflow_why_it_refused(tmp_path, monkeypatch, capsys):
    record = tmp_path / "data.json"
    record.write_bytes(PUBLICATION)
    output = tmp_path / "output"
    output.write_text("")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.setenv("MORNING_EVENT_SCHEDULE", "20 13 * * 1-5")
    monkeypatch.setattr("sys.argv", ["publish_morning", "guard", "--record", str(record)])
    assert publish_morning.main() == 0
    lines = output.read_text().split()
    assert lines[0] == "go=false" and lines[1].startswith("reason=") and len(lines) == 2
    assert lines[1].split("=", 1)[1] in capsys.readouterr().out


def test_the_morning_workflow_closes_the_file_when_a_scheduled_slot_arrives_after_the_window():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "morning.yml").read_text())
    assert wf["jobs"]["collect"]["outputs"]["guard_reason"] == "${{ steps.guard.outputs.reason }}"
    guard = next(s for s in wf["jobs"]["collect"]["steps"] if s.get("id") == "guard")
    assert guard["run"] == "python -m tools.publish_morning guard"
    close = wf["jobs"]["close"]
    condition = " ".join(close["if"].split())
    assert condition == ("github.ref == 'refs/heads/main' && github.event_name == 'schedule' "
                         "&& needs.collect.outputs.guard_reason == 'entry_window_ended'")
    assert close["needs"] == "collect" and close["permissions"] == {"contents": "write"}
    assert [s["run"] for s in close["steps"] if "run" in s][-1] == \
        "python -m tools.publish_morning orders --window-closed"
    assert close["steps"][0]["with"] == {"ref": "main"}
    # the job asks no provider: it holds no secret and runs no collector
    text = json.dumps(close)
    assert "secrets." not in text and "src.morning" not in text and "ALPACA" not in text
    # the word the guard writes is the word the workflow waits for
    source = (ROOT / "tools" / "publish_morning.py").read_text()
    assert "'entry_window_ended'" in source and "reason={reason}" in source


def test_the_persist_job_still_publishes_the_go_cancel_after_the_receipt():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "morning.yml").read_text())
    runs = [s.get("run") for s in wf["jobs"]["persist"]["steps"]]
    assert "python -m tools.publish_morning orders" in runs


# ----------------------------------------------------------- the documents --
def test_the_guide_and_the_readme_state_the_rule_as_the_code_does():
    guide = " ".join((ROOT / "docs" / "operations" / "orders.md").read_text().split())
    readme = " ".join((ROOT / "README.md").read_text().split())
    for word in ("pending", "checked", "no_check", "morning_check_pending", "no_morning_check",
                 "orders_earlier_version", "cancel_all", "morning_rule"):
        assert f"`{word}`" in guide, word
    assert "cancel everything without it" in guide and "a missing one is a fault and never a go" in guide
    assert "(`morning_rule`, `orders.MORNING_RULE`)" in readme
    assert "`--window-closed`" in readme and "python -m src.orders decide" in guide
    for reason in orders.ENTRY_REASONS:
        assert f"`{reason}`" in guide, reason
    # the guide's table lists the reasons in the order the rule asks them, each with its scope
    raw = (ROOT / "docs" / "operations" / "orders.md").read_text().split("## Applying the rule", 1)[1]
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in raw.splitlines()
            if line.startswith("| `")]
    assert [r[0] for r in rows] == [f"`{reason}`" for reason in orders.ENTRY_REASONS]
    whole = {"orders_earlier_version", "night_not_allowed", "morning_file_missing", "morning_file_unreadable",
             "morning_file_unbound", "morning_not_checked"}
    assert {r[0].strip("`") for r in rows if r[1] == "yes"} == whole


def test_the_morning_files_status_words_are_the_morning_receipts_and_the_gates_own():
    from src import go_live, morning
    # a check that ran is what the gate counts as a morning check; every status is the receipt's own
    assert orders.MORNING_CHECKED_STATUSES == go_live.MORNING_RAN
    assert orders.RECEIPT_STATUSES == morning.STATUSES
    assert set(orders.RECEIPT_STATUSES) - set(orders.MORNING_CHECKED_STATUSES) == {"provider_unavailable",
                                                                                   "inapplicable"}


@pytest.mark.parametrize("status", ["inapplicable", "provider_unavailable"])
def test_a_bound_receipt_that_checked_nothing_is_no_check_and_names_its_status(status):
    raw, doc = go_night()
    receipt = json.loads(receipt_for(doc, doc["tickets"][0]))
    receipt["status"] = status
    out = orders.build_morning(raw, json.dumps(receipt).encode())
    assert orders.problems(out, "orders_morning") == []
    assert (out["status"], out["cancel_all"], out["cancel_all_reason"]) == ("no_check", True, "no_morning_check")
    # it was bound and is said to be, with the status that says why it checked nothing
    assert (out["morning_bound"], out["morning_status"]) == (True, status)
    assert all(t["decision"] == "cancel" and "no_morning_check" in t["reasons"] for t in out["tickets"])
    # resealed as checked, the file is refused: a bound receipt that ran nothing is never a check
    forged = json.loads(checked_for(raw, doc))
    assert orders.problems(json.loads(reseal(forged, morning_status=status)), "orders_morning")


# ------------------------------------------- orders.json's verdicts come first ---
def test_an_earlier_versions_orders_json_is_never_read_by_the_rule():
    earlier = json.loads(golden_orders())
    earlier["version"] = orders.VERSION - 1
    raw = orders.encode(orders.sealed(earlier))
    want = {"mode": "paper", "cancel_all": True, "cancel_all_reason": "orders_earlier_version", "tickets": {}}
    assert orders.entry_decisions(raw, None, datetime(2026, 9, 11, 13, 40, tzinfo=timezone.utc)) == want
    # whatever morning file stands beside it
    standing = orders.encode(orders.earlier_version_morning(raw))
    assert orders.entry_decisions(raw, standing, datetime(2026, 9, 11, 13, 40, tzinfo=timezone.utc)) == want


def test_a_morning_file_that_says_go_on_a_night_orders_json_does_not_allow_cancels_everything():
    raw, doc = go_night()
    # the same tickets on a night whose light is red: the ticket stays go on its own checks, the night stops it
    red = copy.deepcopy(doc)
    red["night_checks"][0].update(status="fail", reason="light_red")
    red["trade_allowed"] = False
    red["reasons"] = [{"scope": "night", "code": "light_red"}] + doc["reasons"]
    red_raw = reseal(red)
    assert orders.problems(json.loads(red_raw)) == [] and red["tickets"][0]["status"] == "go"
    built = orders.build_morning(red_raw, receipt_for(red, red["tickets"][0]))
    assert built["tickets"][0]["reasons"] == ["night_not_allowed"]
    forged = reseal(with_go(built))                     # resealed to say go for it
    assert orders.validate(forged, "orders_morning")["tickets"][0]["decision"] == "go"
    out = orders.entry_decisions(red_raw, forged, before(red))
    assert (out["cancel_all"], out["cancel_all_reason"]) == (True, "night_not_allowed")
    assert decisions(red_raw, forged, before(red)) == {"NVDA": ("cancel", "night_not_allowed"),
                                                       "COIL": ("cancel", "night_not_allowed")}


def test_a_bound_file_names_the_receipt_it_was_bound_to():
    raw, doc = go_night()
    checked = json.loads(checked_for(raw, doc))
    found = orders.problems(json.loads(reseal(checked, morning_sha256=None)), "orders_morning")
    assert "a morning file bound to a receipt names that receipt's hash" in found


@pytest.mark.parametrize("label, change, problem", [
    ("the night's checks reordered", lambda d: d["night_checks"].reverse(), "night checks are not each"),
    ("a night check given twice", lambda d: d["night_checks"].__setitem__(1, copy.deepcopy(d["night_checks"][0])),
     "night checks are not each"),
    ("a ticket's checks reordered", lambda d: d["tickets"][0]["checks"].reverse(), "its checks are not each"),
])
def test_orders_json_carries_each_check_once_in_order(label, change, problem):
    raw, doc = go_night()
    forged = copy.deepcopy(doc)
    change(forged)
    if label.startswith("a ticket"):
        forged["tickets"][0] = orders.sealed({k: v for k, v in forged["tickets"][0].items() if k != "content_sha256"})
    assert any(problem in f for f in orders.problems(json.loads(reseal(forged)))), label


# ---------------------------------------------- the check over main's files ---
def test_the_check_derives_the_morning_file_again_from_mains_orders_and_receipt(tmp_path):
    docs = docs_with(tmp_path, "next")
    orders.write_publication(docs)
    raw = (docs / orders.FILE).read_bytes()
    doc = json.loads(raw)
    assert orders.check(docs) == []                                  # the evening's pending file
    receipt = receipt_for(doc, doc["tickets"][0])
    built = orders.build_morning(raw, receipt)
    (docs / orders.MORNING_FILE).write_bytes(orders.encode(built))
    # checked against a receipt main does not carry
    assert orders.check(docs) == ["orders-morning.json is checked against a morning receipt main does not carry"]
    (docs / orders.MORNING_RECEIPT).write_bytes(receipt)
    assert orders.check(docs) == []
    # the same receipt, a field of the file changed and the file resealed: not what main's files give
    (docs / orders.MORNING_FILE).write_bytes(reseal(built, observation_run_id="run-2"))
    assert orders.check(docs) == ["orders-morning.json is not what main's orders.json and morning receipt give"]
    # a pending file resealed with another ticket order is not the evening's either
    pending = orders.pending_morning(raw)
    pending["tickets"].reverse()
    (docs / orders.MORNING_FILE).write_bytes(reseal(pending))
    assert orders.check(docs) == ["orders-morning.json is not what main's orders.json and morning receipt give"]
    # a no_check file naming a receipt main no longer carries stands: it cancels everything
    other = receipt_for(doc, doc["tickets"][0], generated_at="2026-09-11T13:20:00+00:00")
    stale = json.loads(other)
    stale["status"] = "inapplicable"
    (docs / orders.MORNING_FILE).write_bytes(orders.encode(orders.build_morning(raw, json.dumps(stale).encode())))
    assert orders.check(docs) == []
