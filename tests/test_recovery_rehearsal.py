"""The recovery rehearsal (#111): one failure a night through the doubles, the
evening guard asked before and after. The rehearsal is run once here and every
fact a night records is stated by hand; the committed files are held equal to
that fresh run, and `check()` is held to refuse drift."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from src import grader, pipeline
from tests.fakes import FakeAlpaca, FakeResend
from tools import recovery_rehearsal as rr


@pytest.fixture(scope="module")
def result() -> dict:
    return rr.rehearse()


def night(result: dict, name: str) -> dict:
    return next(n for n in result["nights"] if n["name"] == name)


def decision(n: dict, when: str) -> dict:
    found = [d for d in n["guard"] if d["when"].startswith(when)]
    assert len(found) == 1, [d["when"] for d in n["guard"]]
    return found[0]


def test_the_nights_are_the_scenarios_in_order_over_the_suites_market(result):
    assert [n["name"] for n in result["nights"]] == [s["name"] for s in rr.SCENARIOS]
    assert [n["session"] for n in result["nights"]] == [s["session"] for s in rr.SCENARIOS]
    assert result["policy"] == rr.POLICY and result["version"] == rr.VERSION
    assert result["source"]["market"]["names"] == sorted(["AAA", "AAB", "COIL"] + [f"B{c}{c}" for c in "ABCDEFGHIJK"])
    assert result["source"]["market"]["benchmark"] == pipeline.BENCHMARK_SYMBOL == "SPY"
    assert result["source"]["attempts"] == grader.ATTEMPTS == 2
    assert result["source"]["guard_sha256"] == rr.sha256(rr.guard_source().encode("utf-8"))


def test_a_clean_night_publishes_two_tickets_and_the_retry_slot_is_then_refused(result):
    n = night(result, "clean")
    assert n["run"] == {"exit_code": 0, "status": "ok", "published": True, "failed": False, "failure": None,
                        "skipped": None, "stage": "email", "problems": [], "calendar_outcome": "ready"}
    pub = n["publication"]
    assert pub["session"] == "2026-09-04" and pub["status"] == "ok" and pub["email"] == "delivered"
    assert pub["trades"] == ["AAA", "AAB"] and pub["reaction_tickets"] == 2 and pub["anticipation_tickets"] == 1
    assert pub["reads"] == {"requested": 2, "done": 2, "verdict": "complete",
                            "causes": {"refused": 0, "format": 0, "account": 0, "credit": 0, "transport": 0}}
    assert n["calls"]["reader_calls"] == 2 and n["calls"]["bars_requests"] == 1 and n["calls"]["mails"] == 1
    assert n["calls"]["mail_subjects"][0].startswith("Trade next session. 2 A-quality bursts.")
    assert n["previous"] == {"publication": None, "outcome": "none"} and n["files_changed"] > 0
    assert n["publication_identity"]["data_json_without_clock_fields"] and n["publication_identity"]["picks_json"]
    before, after = decision(n, "before"), decision(n, "after")
    assert before["go"] is True and before["session"] == "2026-09-04" and before["cron"] == rr.PRIMARY_CRON
    assert after["go"] is False and after["session"] is None and after["reason"] == "2026-09-04 is already published"


def test_labor_day_fetches_asks_writes_and_mails_nothing(result):
    n = night(result, "holiday")
    assert n["run"]["status"] == "no_session" and n["run"]["skipped"] == "no_session" and n["run"]["exit_code"] == 0
    assert n["run"]["published"] is False and n["run"]["calendar_outcome"] == "no_session"
    assert n["calls"] == {"bars_requests": 0, "reader_calls": 0, "mails": 0, "mail_subjects": []}
    assert n["files_changed"] == 0 and n["previous"]["outcome"] == "preserved"
    assert n["previous"]["publication"] == night(result, "clean")["publication_identity"]
    for d in n["guard"]:
        assert d["go"] is False and d["reason"] == "2026-09-07 is not an exchange session"


def test_a_provider_outage_publishes_nothing_keeps_the_record_and_leaves_the_retry_slot_open(result):
    n = night(result, "provider_outage")
    assert n["run"]["exit_code"] == pipeline.EXIT_FAILED == 1 and n["run"]["status"] == "failed"
    assert n["run"]["published"] is False and n["run"]["failed"] is True and n["run"]["stage"] == "session"
    assert n["run"]["failure"].startswith("RuntimeError: insufficient usable coverage: 0 of 14 intended stocks")
    assert n["publication"] is None and n["publication_identity"] is None
    assert n["previous"]["outcome"] == "preserved" and n["files_changed"] == 0
    assert n["previous"]["publication"] == night(result, "clean")["publication_identity"]
    # one batch, tried twice, then dropped: the fetch's own bound
    assert n["calls"]["bars_requests"] == 2 == n["bars_requests_bound"]["maximum"] and n["bars_requests_bound"]["within"]
    assert n["calls"]["reader_calls"] == 0 and n["reader_calls_bound"]["within"] is True
    assert n["calls"]["mails"] == 1 and n["calls"]["mail_subjects"] == ["FAILED — no plan for 2026-09-08"]
    assert decision(n, "before")["go"] is True
    retry = decision(n, "after: the retry slot")
    assert retry["go"] is True and retry["session"] == "2026-09-08" and retry["cron"] == rr.RETRY_CRON
    expired = decision(n, "after: the next session's open")
    assert expired["go"] is False and expired["reason"] == "2026-09-08 recovery expired at the next session open"


def test_the_retry_slot_recovers_once_and_every_later_or_delayed_slot_is_refused(result):
    n = night(result, "provider_recovered_at_retry")
    assert n["run"]["exit_code"] == 0 and n["run"]["published"] is True
    assert n["publication"]["session"] == "2026-09-08" and n["clock"] == "2026-09-09T00:30:00+00:00"
    assert n["previous"]["outcome"] == "replaced"
    assert n["previous"]["publication"] == night(result, "clean")["publication_identity"]
    assert decision(n, "before")["go"] is True and decision(n, "before")["session"] == "2026-09-08"
    again = decision(n, "after: the retry slot again")
    assert again["go"] is False and again["reason"] == "2026-09-08 is already published"
    delayed = decision(n, "after: a delayed primary event")
    assert delayed["go"] is False and delayed["cron"] == rr.PRIMARY_CRON and delayed["reason"] == "2026-09-08 is already published"
    older = decision(n, "after: a delayed retry event for the 4 September slot")
    assert older["go"] is False and older["reason"] == "A newer session than 2026-09-04 is already published"


def test_an_empty_credit_balance_stops_after_one_call_and_earns_no_ticket(result):
    n = night(result, "reader_credit")
    assert n["run"]["exit_code"] == pipeline.EXIT_DEGRADED == 2 and n["run"]["problems"] == ["claude_unavailable"]
    assert n["calls"]["reader_calls"] == 1 and n["reader_calls_bound"] == {"requested": 2, "attempts": 2, "maximum": 4, "within": True}
    pub = n["publication"]
    assert pub["reads"]["requested"] == 2 and pub["reads"]["done"] == 0 and pub["reads"]["verdict"] == "unavailable"
    assert pub["reads"]["causes"]["credit"] == 2 and sum(pub["reads"]["causes"].values()) == 2
    assert pub["trades"] == [] and pub["reaction_tickets"] == 0 and pub["status"] == "degraded"
    assert pub["cover"] == "No new burst tickets. Reader review incomplete."
    assert pub["reader_usage"]["calls"] == 1
    assert n["calls"]["mails"] == 1 and n["previous"]["outcome"] == "replaced"
    assert decision(n, "after")["reason"] == "2026-09-09 is already published"


def test_a_dead_transport_is_bounded_by_the_attempts_per_name(result):
    n = night(result, "reader_transport")
    assert n["calls"]["reader_calls"] == 2 * grader.ATTEMPTS == 4 == n["reader_calls_bound"]["maximum"]
    assert n["reader_calls_bound"]["within"] is True
    pub = n["publication"]
    assert pub["reads"]["causes"]["transport"] == 2 and pub["reads"]["verdict"] == "unavailable"
    assert pub["reaction_tickets"] == 0 and n["run"]["exit_code"] == 2 and pub["reader_usage"]["calls"] == 4


def test_a_refused_mail_keeps_the_record_and_exits_three(result):
    n = night(result, "email_failed")
    assert n["run"]["exit_code"] == pipeline.EXIT_FAILED_AFTER_PUBLISH == 3
    assert n["run"]["published"] is True and n["run"]["failed"] is True and n["run"]["stage"] == "email"
    assert n["run"]["status"] == "degraded" and n["run"]["problems"] == ["email_failed"]
    pub = n["publication"]
    assert pub["session"] == "2026-09-11" and pub["email"] == "failed" and pub["problems"] == ["email_failed"]
    assert pub["reaction_tickets"] == 2 and n["calls"]["mails"] == 0 and n["calls"]["mail_subjects"] == []
    assert n["previous"]["outcome"] == "replaced"
    assert decision(n, "after")["reason"] == "2026-09-11 is already published"


def test_stale_frames_on_every_name_are_an_outage_that_keeps_the_record(result):
    n = night(result, "stale_feed")
    assert n["run"]["exit_code"] == 1 and n["run"]["published"] is False and n["run"]["stage"] == "session"
    assert n["previous"]["outcome"] == "preserved" and n["files_changed"] == 0
    assert n["previous"]["publication"] == night(result, "email_failed")["publication_identity"]
    assert n["calls"]["reader_calls"] == 0 and n["calls"]["bars_requests"] == 1
    assert n["calls"]["mail_subjects"] == ["FAILED — no plan for 2026-09-14"]
    assert decision(n, "after: the retry slot")["go"] is True
    assert decision(n, "after: the next session's open")["reason"] == "2026-09-14 recovery expired at the next session open"


def test_the_night_after_a_missed_one_publishes_again(result):
    n = night(result, "next_session_after_a_missed_night")
    assert n["run"]["exit_code"] == 0 and n["publication"]["session"] == "2026-09-15"
    assert n["previous"]["outcome"] == "replaced"
    assert n["previous"]["publication"] == night(result, "email_failed")["publication_identity"]


def test_the_summary_is_the_nights_added_up(result):
    s, nights = result["summary"], result["nights"]
    assert s["nights"] == 9 and s["published"] == 6 and s["failed_before_publishing"] == 2 and s["skipped"] == 1
    assert s["sessions_published"] == ["2026-09-04", "2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11", "2026-09-15"]
    assert s["exit_codes"] == {"clean": 0, "holiday": 0, "provider_outage": 1, "provider_recovered_at_retry": 0,
                               "reader_credit": 2, "reader_transport": 2, "email_failed": 3, "stale_feed": 1,
                               "next_session_after_a_missed_night": 0}
    assert s["previous_outcomes"] == {n["name"]: n["previous"]["outcome"] for n in nights}
    assert s["previous_preserved_on_every_night_that_published_nothing"] is True
    assert s["reader_calls_within_bound_every_night"] is True
    assert s["reader_calls"] == {n["name"]: n["calls"]["reader_calls"] for n in nights}
    assert s["guard"] == {"permitted": 10, "already_published": 7, "newer_published": 1, "expired": 2, "not_a_session": 2, "other": 0}
    assert sum(s["guard"].values()) == sum(len(n["guard"]) for n in nights)
    assert s["slots_admitted_after_a_publication"] == 0 and s["slots_admitted_after_a_failure"] == 2
    assert rr.summary(nights) == s


def test_the_guard_is_the_workflows_own_body_run_as_written(result, tmp_path):
    code = rr.guard_source()
    assert "def decide():" in code and "GITHUB_OUTPUT" in code and "python - <<'PY'" not in code
    (tmp_path / "docs").mkdir()
    empty = rr.guard(tmp_path, "2026-09-04T22:20:00+00:00", rr.PRIMARY_CRON, code)
    recorded = decision(night(result, "clean"), "before")
    assert empty == {k: v for k, v in recorded.items() if k != "when"}
    (tmp_path / "docs" / "data.json").write_text(json.dumps({"run": {"session": "2026-09-04", "status": "ok", "dry_run": False}}))
    assert rr.guard(tmp_path, "2026-09-05T00:20:00+00:00", rr.RETRY_CRON, code)["reason"] == "2026-09-04 is already published"
    with pytest.raises(rr.RehearsalError, match="no offset"):
        rr.guard(tmp_path, "2026-09-04T22:20:00", rr.PRIMARY_CRON, code)


def test_a_night_that_published_nothing_and_changed_a_file_is_refused():
    before = {"data.json": "a", "picks.json": "b"}
    assert rr.previous_outcome(before, dict(before), published=False) == "preserved"
    assert rr.previous_outcome(before, {**before, "history/x": "c"}, published=False) == "preserved"
    assert rr.previous_outcome(before, {"data.json": "z", "picks.json": "b"}, published=True) == "replaced"
    assert rr.previous_outcome({}, {"data.json": "a"}, published=True) == "none"
    with pytest.raises(rr.RehearsalError, match="changed the previous publication"):
        rr.previous_outcome(before, {"data.json": "z", "picks.json": "b"}, published=False)
    with pytest.raises(rr.RehearsalError, match="changed the previous publication"):
        rr.previous_outcome(before, {"data.json": "a"}, published=False)


def test_an_injection_the_rehearsal_does_not_know_is_refused():
    n = rr.Night(FakeAlpaca(), type("C", (), {"raises": None}), FakeResend(), {}, Path("/nonexistent"), "")
    with pytest.raises(rr.RehearsalError, match="unknown injection"):
        n.inject("bogus")
    assert set(rr.INJECTIONS) == {s["inject"] for s in rr.SCENARIOS}


def test_the_committed_files_are_this_fresh_run(result):
    assert json.loads(rr.OUTPUT_JSON.read_text(encoding="utf-8")) == result
    assert rr.OUTPUT_JSON.read_text(encoding="utf-8") == json.dumps(result, indent=1, sort_keys=True) + "\n"
    assert rr.OUTPUT_MD.read_text(encoding="utf-8") == rr.markdown(result)


def test_check_refuses_a_drifted_number_a_rewritten_report_and_missing_files(result, tmp_path, monkeypatch):
    monkeypatch.setattr(rr, "rehearse", lambda: result)
    rr.write(result, tmp_path)
    assert rr.check(tmp_path) == []
    drifted = json.loads((tmp_path / rr.OUTPUT_JSON.name).read_text())
    drifted["summary"]["slots_admitted_after_a_publication"] = 1
    (tmp_path / rr.OUTPUT_JSON.name).write_text(json.dumps(drifted, indent=1, sort_keys=True) + "\n")
    assert rr.check(tmp_path) == [f"{rr.OUTPUT_JSON.name} is not what the rehearsal writes"]
    rr.write(result, tmp_path)
    (tmp_path / rr.OUTPUT_MD.name).write_text("# something else\n")
    assert rr.check(tmp_path) == [f"{rr.OUTPUT_MD.name} is not what the rehearsal writes"]
    (tmp_path / rr.OUTPUT_MD.name).unlink()
    assert rr.check(tmp_path) == [f"{rr.OUTPUT_MD.name}: [Errno 2] No such file or directory: '{tmp_path / rr.OUTPUT_MD.name}'"]
    assert rr.check(tmp_path / "nowhere")[0].startswith(f"{rr.OUTPUT_JSON.name}: ")


def test_the_command_line_writes_and_checks(result, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(rr, "rehearse", lambda: result)
    assert rr.main(["--output-dir", str(tmp_path)]) == 0
    assert "9 nights: 6 published, 2 failed before publishing, 1 skipped" in capsys.readouterr().out
    assert rr.main(["--check", "--output-dir", str(tmp_path)]) == 0
    assert capsys.readouterr().out.startswith("current:")
    (tmp_path / rr.OUTPUT_MD.name).write_text("drift\n")
    assert rr.main(["--check", "--output-dir", str(tmp_path)]) == 1
    assert capsys.readouterr().out.startswith("stale:")
    monkeypatch.setattr(rr, "rehearse", lambda: (_ for _ in ()).throw(rr.RehearsalError("as written")))
    assert rr.main(["--output-dir", str(tmp_path)]) == 2
    assert "refused: as written" in capsys.readouterr().err


def test_the_command_line_quiets_the_pipeline_only_while_it_runs(result, tmp_path, monkeypatch):
    """main() lowers the root logger to ERROR for its own run and puts the
    caller's level back: a test calling it must not silence the warnings later
    tests capture (the publication-unavailable warnings, for two)."""
    root = logging.getLogger()
    monkeypatch.setattr(root, "level", logging.WARNING)
    seen = []
    monkeypatch.setattr(rr, "rehearse", lambda: seen.append(root.level) or result)
    assert rr.main(["--output-dir", str(tmp_path)]) == 0
    assert seen == [logging.ERROR] and root.level == logging.WARNING
    monkeypatch.setattr(rr, "rehearse", lambda: (_ for _ in ()).throw(rr.RehearsalError("as written")))
    assert rr.main(["--output-dir", str(tmp_path)]) == 2 and root.level == logging.WARNING
