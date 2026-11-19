"""The analyst's brief as the evening writes it, through the doubles: after
``run_evening()`` the pair exists beside the record and validates against the
record's final bytes; nothing the brief does can cost the night its record,
its exit code or a problem word; and a failed install puts the previous pair
back. Every night here is pinned to an instant."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

import src
from src import brief, pipeline, record
from tests.test_pipeline import EVENING, claude, evening, market  # noqa: F401  (fixtures)

PAGE = Path(__file__).parent / "fixtures" / "page"


def pair(docs: Path) -> tuple:
    data_raw = (docs / pipeline.DATA_FILE).read_bytes()
    picks_path = docs / record.PICKS_FILE
    picks_raw = picks_path.read_bytes() if picks_path.exists() else None
    return data_raw, picks_raw, (docs / brief.JSON_FILE).read_bytes(), (docs / brief.MD_FILE).read_bytes()


def agreeing_block(data: dict) -> dict:
    """SYNTHETIC model-record block that agrees with the record's own scorecard."""
    card = data["scorecard"]
    return {"version": 1, "status": "computed", "tickets": card["plans"],
            "buckets": {name: card[name] for name in record.SCORECARD_BUCKETS}, "sum_r": card["sum_r"],
            "sentences": ["SYNTHETIC: a sentence the test's own model record wrote."],
            "plans": [{"ticker": "SYNTH", "bucket": "pending", "r": None}]}


def install_model_record(monkeypatch, module) -> None:
    """Make ``from src import model_record`` find ``module`` (None: an ImportError), whatever the tree holds."""
    monkeypatch.setitem(sys.modules, "src.model_record", module)
    if module is None:
        monkeypatch.delattr(src, "model_record", raising=False)
    else:
        monkeypatch.setattr(src, "model_record", module, raising=False)


class _Module:
    def __init__(self, build):
        self.build = build


# ------------------------------------------------------------ the three nights
def test_a_clean_night_writes_a_brief_bound_to_the_records_final_bytes(market, claude, fake_resend, tmp_path):
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0 and rep.status == "ok" and rep.problems == [] and rep.stage == "email"
    data_raw, picks_raw, json_raw, md_raw = pair(docs)
    out = brief.validate(data_raw, picks_raw, json_raw, md_raw)
    assert out["status"] == "derived"
    # bound to the bytes on disk after the restamp that follows delivery, not to an earlier write
    assert data["run"]["email"] == "delivered"
    assert out["identity"]["canonical"] == {"path": "data.json", "sha256": hashlib.sha256(data_raw).hexdigest(),
                                            "bytes": len(data_raw)}
    assert out["identity"]["picks"]["sha256"] == hashlib.sha256(picks_raw).hexdigest()
    assert out["service"]["morning"]["receipt"]["must_carry"] == {
        "publication.data_sha256": out["identity"]["canonical"]["sha256"]}
    assert [(t["stage"], t["ticker"]) for t in out["tickets"]] == [("burst", "AAA"), ("anticipation", "COIL")]
    assert out["model_record"]["status"] in ("computed", "unreconciled", "not_computed")
    assert not list(docs.glob(".brief-*"))          # the staging directory is gone


def test_a_dry_run_writes_the_pair_for_the_record_it_wrote(market, claude, fake_resend, tmp_path):
    rep, data, docs = evening(tmp_path, market, dry_run=True)
    assert rep.exit_code() == 0 and data["run"]["dry_run"] is True
    data_raw, picks_raw, json_raw, md_raw = pair(docs)
    assert picks_raw is None                         # a dry run records no pick
    out = brief.validate(data_raw, picks_raw, json_raw, md_raw)
    assert out["status"] == "derived" and out["identity"]["picks"] is None and out["identity"]["dry_run"] is True


def test_a_known_holiday_leaves_the_pair_bound_to_the_publication_it_preserves(market, claude, fake_resend, tmp_path):
    first, data, docs = evening(tmp_path, market, now=datetime(2026, 9, 4, 22, 30, tzinfo=timezone.utc))
    assert first.published
    before = pair(docs)
    rep = pipeline.run_evening(docs=docs, now=datetime(2026, 9, 7, 22, 30, tzinfo=timezone.utc))
    assert rep.status == "no_session" and not rep.published
    assert pair(docs) == before
    out = brief.validate(*before)
    # Labor Day: the brief's own next expected session is Tuesday the 8th, read off the record's calendar
    assert out["identity"]["measured_session"] == "2026-09-04" and out["service"]["expected"]["next_session"] == "2026-09-08"


# ------------------------------------------------------------ the model record
def test_the_evening_carries_the_model_record_it_computed(market, claude, fake_resend, tmp_path, monkeypatch):
    seen = {}

    def build(rec, frames, minutes, data, docs=None):
        seen.update(rec=rec, frames=frames, minutes=minutes, data=data, docs=docs)
        return agreeing_block(data)
    install_model_record(monkeypatch, _Module(build))
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0
    assert seen["docs"] == docs and "AAA" in seen["frames"] and seen["data"]["run"]["email"] == "delivered"
    assert [p["ticker"] for p in seen["rec"]["picks"]] == ["AAA", "COIL"]
    out = brief.validate(*pair(docs))
    assert out["model_record"] == agreeing_block(data) and out["bounds"]["model_record_carried"] is True
    assert "SYNTHETIC: a sentence the test's own model record wrote." in (docs / brief.MD_FILE).read_text()


@pytest.mark.parametrize("failure", ["raises", "absent"])
def test_a_model_record_that_cannot_be_built_costs_the_night_nothing(market, claude, fake_resend, tmp_path,
                                                                     monkeypatch, caplog, failure):
    def build(*args, **kwargs):
        raise RuntimeError("a sentence that must not reach a published file")
    install_model_record(monkeypatch, _Module(build) if failure == "raises" else None)
    with caplog.at_level(logging.WARNING, logger=pipeline.log.name):
        rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0 and rep.status == "ok" and rep.problems == [] and rep.stage == "email"
    assert data["run"]["status"] == "ok" and data["run"]["problems"] == []
    out = brief.validate(*pair(docs))
    assert out["status"] == "derived"
    assert out["model_record"] == {"status": "not_computed", "reason": brief.NOT_COMPUTED_FAILED}
    warned = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Model record unavailable")]
    assert len(warned) == 1 and ("(RuntimeError)" if failure == "raises" else "(ModuleNotFoundError)") in warned[0]
    assert b"must not reach" not in (docs / brief.JSON_FILE).read_bytes() + (docs / brief.MD_FILE).read_bytes()


def test_a_model_record_that_disagrees_with_the_scorecard_is_not_carried(market, claude, fake_resend, tmp_path,
                                                                        monkeypatch):
    def build(rec, frames, minutes, data, docs=None):
        return {**agreeing_block(data), "tickets": data["scorecard"]["plans"] + 1}
    install_model_record(monkeypatch, _Module(build))
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0
    out = brief.validate(*pair(docs))
    assert out["model_record"] == {"status": "not_computed", "reason": brief.NOT_CARRIED_DISAGREES}


# ------------------------------------------------------------ failures of the brief itself
def test_a_derive_that_raises_installs_the_unavailable_pair_and_changes_nothing_else(market, claude, fake_resend,
                                                                                    tmp_path, monkeypatch, caplog):
    def boom(*args, **kwargs):
        raise RuntimeError("a sentence that must not reach a published file")
    monkeypatch.setattr(brief, "derive", boom)
    with caplog.at_level(logging.WARNING, logger=pipeline.log.name):
        rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0 and rep.status == "ok" and rep.problems == [] and rep.stage == "email"
    assert data["run"]["status"] == "ok" and data["run"]["problems"] == [] and data["trades"] == ["AAA"]
    data_raw, picks_raw, json_raw, md_raw = pair(docs)
    out = brief.validate_binding(data_raw, picks_raw, json_raw, md_raw)
    assert out["status"] == "unavailable" and "RuntimeError" in out["reason"]
    assert out["identity"]["canonical"]["sha256"] == hashlib.sha256(data_raw).hexdigest()
    assert "tickets" not in out and "candidates" not in out
    assert b"must not reach" not in json_raw + md_raw
    assert md_raw.startswith(b"# SpicyStock daily brief: unavailable")
    assert [r.levelno for r in caplog.records if r.getMessage().startswith("Analyst brief: unavailable")] == [logging.WARNING]


def test_a_brief_that_cannot_be_written_is_one_warning_and_the_night_stands(market, claude, fake_resend, tmp_path,
                                                                           monkeypatch, caplog):
    def refuse(*args, **kwargs):
        raise OSError("no space left")
    monkeypatch.setattr(brief, "write_publication", refuse)
    with caplog.at_level(logging.WARNING, logger=pipeline.log.name):
        rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0 and rep.status == "ok" and rep.problems == [] and rep.stage == "email"
    assert not (docs / brief.JSON_FILE).exists() and not (docs / brief.MD_FILE).exists()
    assert [r.getMessage() for r in caplog.records if "Analyst brief unavailable" in r.getMessage()] == [
        "Analyst brief unavailable (OSError); evening record retained."]


def _fixture_docs(tmp_path: Path, name: str) -> tuple:
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    data_raw = (PAGE / f"{name}.json").read_bytes()
    picks_raw = (PAGE / "full-picks.json").read_bytes()
    (docs / brief.DATA_FILE).write_bytes(data_raw)
    (docs / brief.PICKS_FILE).write_bytes(picks_raw)
    return docs, data_raw, picks_raw


@pytest.mark.parametrize("fail_on", [1, 2])
def test_a_rename_that_fails_restores_the_previous_pair(tmp_path, monkeypatch, fail_on):
    docs, first_raw, picks_raw = _fixture_docs(tmp_path, "full")
    assert brief.write_publication(first_raw, picks_raw, docs)["status"] == "derived"
    previous = ((docs / brief.JSON_FILE).read_bytes(), (docs / brief.MD_FILE).read_bytes())
    second_raw = (PAGE / "yellow.json").read_bytes()
    real, calls = os.replace, []

    def failing(source, target):
        calls.append(Path(target).name)
        if len(calls) == fail_on:
            raise OSError("rename refused")
        return real(source, target)
    monkeypatch.setattr(os, "replace", failing)
    with pytest.raises(OSError, match="rename refused"):
        brief.write_publication(second_raw, picks_raw, docs)
    monkeypatch.setattr(os, "replace", real)
    assert calls[:fail_on] == [brief.MD_FILE, brief.JSON_FILE][:fail_on]      # brief.json is installed last
    assert ((docs / brief.JSON_FILE).read_bytes(), (docs / brief.MD_FILE).read_bytes()) == previous
    brief.validate(first_raw, picks_raw, *previous)          # still the first publication's pair, whole
    assert not list(docs.glob(".brief-*"))


def test_a_rename_that_fails_on_a_first_night_leaves_no_half_pair(tmp_path, monkeypatch):
    docs, data_raw, picks_raw = _fixture_docs(tmp_path, "full")
    real, calls = os.replace, []

    def failing(source, target):
        calls.append(Path(target).name)
        if len(calls) == 2:
            raise OSError("rename refused")
        return real(source, target)
    monkeypatch.setattr(os, "replace", failing)
    with pytest.raises(OSError):
        brief.write_publication(data_raw, picks_raw, docs)
    assert not (docs / brief.JSON_FILE).exists() and not (docs / brief.MD_FILE).exists()


def test_the_evening_survives_a_rename_failure_with_the_previous_pair_in_place(tmp_path, monkeypatch, caplog):
    docs, first_raw, picks_raw = _fixture_docs(tmp_path, "full")
    brief.write_publication(first_raw, picks_raw, docs)
    previous = ((docs / brief.JSON_FILE).read_bytes(), (docs / brief.MD_FILE).read_bytes())
    (docs / brief.DATA_FILE).write_bytes((PAGE / "yellow.json").read_bytes())
    real, calls = os.replace, []

    def failing(source, target):
        calls.append(1)
        if len(calls) == 2:
            raise OSError("rename refused")
        return real(source, target)
    monkeypatch.setattr(os, "replace", failing)
    install_model_record(monkeypatch, None)
    with caplog.at_level(logging.WARNING, logger=pipeline.log.name):
        pipeline.publish_brief(docs, {}, {}, {}, {})          # never raises
    assert ((docs / brief.JSON_FILE).read_bytes(), (docs / brief.MD_FILE).read_bytes()) == previous
    assert "Analyst brief unavailable (OSError); evening record retained." in [r.getMessage() for r in caplog.records]


def test_the_brief_is_derived_after_the_research_companions_and_before_retention():
    import inspect
    source = inspect.getsource(pipeline.finish_publication)
    order = [source.index(call) for call in ("publish_research_outcomes(docs, rec)",
                                             "publish_brief(docs, data, rec, frames, minutes)",
                                             "retain_publication(")]
    assert order == sorted(order)
