"""The canonical record is written compact and stated against its 32 MiB bound.

Past the bound a night is refused before anything is installed, and the
refusal names the size and the bound. A restamp after delivery that alone
crosses it leaves the record first installed, which is still retained. Every copy of the bound, the browser's
included, is the reader's own number.
"""
import hashlib
import json
import logging
import re
from pathlib import Path

import pytest

from src import pipeline, reader
from tests.test_pipeline import market, claude, evening

ROOT = Path(__file__).resolve().parents[1]


def compact(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"


def indented(data):
    return json.dumps(data, ensure_ascii=False, indent=1, allow_nan=False).encode("utf-8") + b"\n"


# --- the published record ------------------------------------------------------
def test_the_published_record_is_compact_and_the_reader_binds_its_exact_bytes(market, claude, fake_resend, tmp_path):
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0 and data["run"]["email"] == "delivered"   # the restamp wrote the final bytes
    raw = (docs / "data.json").read_bytes()
    assert raw == compact(json.loads(raw))
    assert raw.startswith(b'{"schema_version":2,') and b"\n" not in raw[:-1]
    canonical = json.loads((docs / "reader.json").read_bytes())["canonical"]
    assert canonical == {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def test_a_night_that_fits_only_compact_is_published(market, claude, fake_resend, tmp_path, monkeypatch):
    _, data, _ = evening(tmp_path / "measure", market)
    small, large = len(compact(data)), len(indented(data))
    bound = (small + large) // 2
    assert small < bound < large
    monkeypatch.setattr(reader, "MAX_PUBLICATION_BYTES", bound)
    rep, data, docs = evening(tmp_path / "night", market)
    assert rep.exit_code() == 0 and rep.published, rep.failure
    assert len((docs / "data.json").read_bytes()) <= bound


def snapshot(docs):
    """Every file the night writes under docs/, by its bytes. The charts are
    drawn at grade time and gitignored, so they are left out."""
    return {str(p.relative_to(docs)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(docs.rglob("*")) if p.is_file() and p.relative_to(docs).parts[0] != "charts"}


def test_a_record_over_its_bound_is_refused_before_anything_is_installed_and_says_why(market, claude, fake_resend, tmp_path, monkeypatch, caplog):
    _, data, docs = evening(tmp_path, market)          # night one publishes everything a night keeps
    before = snapshot(docs)
    assert {"data.json", "picks.json", "reader.json", "history/index.json"} <= set(before)
    assert any(k.startswith("evidence/") for k in before) and any(k.startswith("reader-observations/") for k in before)
    assert any(k.startswith("quality-ledger/") for k in before)
    bound = len(compact(data)) // 2
    monkeypatch.setattr(reader, "MAX_PUBLICATION_BYTES", bound)
    caplog.set_level("INFO", logger="spicystock.reader")
    rep, _, _ = evening(tmp_path, market)              # night two, the same docs, over the bound
    assert rep.exit_code() == pipeline.EXIT_FAILED and not rep.published and rep.stage == "publish"
    assert snapshot(docs) == before                   # nothing pruned, written or installed
    said = re.search(r"canonical publication is (\d+) bytes, over its (\d+)-byte bound", rep.failure)
    assert said and int(said.group(2)) == bound and int(said.group(1)) > bound, rep.failure
    line = [r for r in caplog.records if r.getMessage().startswith("Canonical record")]
    assert len(line) == 1 and line[0].levelname == "ERROR"
    assert line[0].getMessage().startswith(f"Canonical record: {said.group(1)} of {bound} bytes, with ")
    assert line[0].getMessage().endswith("; over its bound, so the night is refused before anything is installed.")


def logged(caplog, name):
    lines = [r for r in caplog.records if r.name == "spicystock.reader" and r.getMessage().startswith(name + ": ")]
    assert len(lines) == 1, [r.getMessage() for r in caplog.records]
    return lines[0], int(lines[0].getMessage()[len(name) + 2:].split(" ", 1)[0])


def test_a_restamp_that_crosses_the_bound_leaves_the_first_record_installed_and_retained(market, claude, fake_resend, tmp_path, monkeypatch, caplog):
    caplog.set_level("INFO", logger="spicystock.reader")
    evening(tmp_path / "measure", market)
    _, first = logged(caplog, "Canonical record")
    _, final = logged(caplog, "Canonical record after delivery")
    assert final > first                                # "delivered" is longer than the word first installed
    caplog.clear()
    monkeypatch.setattr(reader, "MAX_PUBLICATION_BYTES", first)
    rep, data, docs = evening(tmp_path / "night", market)
    assert rep.exit_code() == pipeline.EXIT_FAILED_AFTER_PUBLISH and rep.published, rep.failure
    assert rep.stage == "restamp" and rep.failure == (
        f"ValueError: canonical publication is {final} bytes, over its {first}-byte bound")
    raw = (docs / "data.json").read_bytes()
    assert len(raw) == first and data["run"]["email"] != "delivered"   # the record first installed stays
    canonical = json.loads((docs / "reader.json").read_bytes())["canonical"]
    assert canonical == {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": first}
    index = json.loads((docs / "history/index.json").read_bytes())          # retained after the refusal
    assert hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest() in json.dumps(index)
    assert rep.quality_ledger["status"] == "retained" and Path(rep.quality_ledger["path"]).exists()
    line, size = logged(caplog, "Canonical record after delivery")
    assert size == final and line.levelname == "ERROR"
    assert line.getMessage().endswith("; over its bound, so this write is refused and the record first installed stays.")


# --- the derive refusal --------------------------------------------------------
def test_derive_refuses_a_record_one_byte_over_its_bound_and_names_both_numbers(monkeypatch):
    monkeypatch.setattr(reader, "MAX_PUBLICATION_BYTES", 100)
    with pytest.raises(ValueError, match=r"^canonical publication is 101 bytes, over its 100-byte bound$"):
        reader.derive(b" " * 101)
    with pytest.raises(ValueError) as exc:   # at the bound it is the record's own shape that is read
        reader.derive(b" " * 100)
    assert "over its" not in str(exc.value)


# --- the run log ---------------------------------------------------------------
def night(bursts, observations):
    return {"bursts": [{}] * bursts, "observations": observations}


@pytest.mark.parametrize("size,level", [(800, "INFO"), (801, "WARNING"), (1000, "WARNING"), (1001, "ERROR")])
def test_the_run_log_states_the_record_against_its_bound(size, level, monkeypatch, caplog):
    monkeypatch.setattr(reader, "MAX_PUBLICATION_BYTES", 1000)
    caplog.set_level("INFO", logger="spicystock.reader")
    observations = {"symbols": {"AAA": {"c": 1}}}
    reader.log_publication(size, night(3, observations))
    [record] = [r for r in caplog.records if r.name == "spicystock.reader"]
    assert record.levelname == level
    tail = "; over its bound, so the night is refused before anything is installed." if size > 1000 else "."
    assert record.getMessage() == (f"Canonical record: {size} of 1000 bytes, with 3 bursts and "
                                   f"{len(compact(observations)) - 1} bytes of observations{tail}")


def test_the_run_log_says_one_burst(caplog):
    caplog.set_level("INFO", logger="spicystock.reader")
    reader.log_publication(10, night(1, {}))
    assert "with 1 burst and 2 bytes of observations." in caplog.records[0].getMessage()


@pytest.mark.parametrize("data", [{}, {"bursts": None, "observations": {}}, None, {"bursts": [], "observations": float("nan")}])
def test_unreadable_counts_still_state_the_size_against_the_bound(data, monkeypatch, caplog):
    monkeypatch.setattr(reader, "MAX_PUBLICATION_BYTES", 1000)
    caplog.set_level("INFO", logger="spicystock.reader")
    for size, level in ((10, "INFO"), (2000, "ERROR")):
        caplog.clear()
        reader.log_publication(size, data)
        [record] = [r for r in caplog.records if r.name == "spicystock.reader"]
        assert record.levelname == level
        assert re.fullmatch(rf"Canonical record: {size} of 1000 bytes, its burst and observation counts unreadable "
                            r"\(\w+\)(; over its bound, so the night is refused before anything is installed)?\.",
                            record.getMessage()), record.getMessage()


def test_the_run_log_never_fails_the_night(caplog):
    caplog.set_level("INFO", logger="spicystock.reader")
    reader.log_publication(None, {"bursts": [], "observations": {}})
    [record] = [r for r in caplog.records if r.name == "spicystock.reader"]
    assert record.levelname == "WARNING" and record.getMessage() == "Canonical record could not be measured (TypeError)."


def test_the_restamp_is_stated_in_its_own_words(monkeypatch, caplog):
    monkeypatch.setattr(reader, "MAX_PUBLICATION_BYTES", 1000)
    caplog.set_level("INFO", logger="spicystock.reader")
    reader.log_publication(1001, night(2, {}), after_delivery=True)
    [record] = caplog.records
    assert record.levelname == "ERROR" and record.getMessage() == (
        "Canonical record after delivery: 1001 of 1000 bytes, with 2 bursts and 2 bytes of observations; "
        "over its bound, so this write is refused and the record first installed stays.")


# --- every copy of the bound -------------------------------------------------
def test_every_copy_of_the_canonical_bound_is_the_readers():
    from src import issuer_evidence, morning, stop_research
    from tools import publish_issuer_evidence
    bound = reader.MAX_PUBLICATION_BYTES
    assert bound == 32 * 1024 * 1024
    assert (morning.MAX_PUBLICATION_BYTES, issuer_evidence.MAX_PUBLICATION_BYTES, stop_research.MAX_PUBLICATION_BYTES,
            publish_issuer_evidence.MAX_RECORD_BYTES) == (bound,) * 4
    js = (ROOT / "docs/app-reader.js").read_text()
    literal = re.search(r"const MAX_BYTES = ([0-9 *]+),", js)
    assert literal and eval(literal.group(1), {"__builtins__": {}}) == bound   # digits and * only
