"""The canonical record is written compact and stated against its 48 MiB bound;
reader.json and its observation sidecar, the files the browser downloads,
against their own 32 MiB each.

Past any of the three bounds a night is refused before anything is installed,
and the refusal names the size and the bound. A restamp after delivery that
alone crosses one leaves the record first installed, which is still retained.
Every copy of the canonical bound, the browser's included, is the reader's own
number; the browser's reader module bounds what it downloads by the projection's.
"""
import hashlib
import json
import logging
import re
from pathlib import Path

import pytest

from src import pipeline, reader, report
from tests.test_pipeline import market, claude, evening
from tests.test_quality import frame as qframe, ideal_bars
from tests.test_report import _rendered

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


def test_a_record_over_its_bound_is_refused_before_anything_is_installed_and_says_why(market, claude, fake_alpaca, fake_resend, tmp_path, monkeypatch, caplog):
    _, data, docs = evening(tmp_path, market)          # night one publishes everything a night keeps
    before = snapshot(docs)
    assert {"data.json", "picks.json", "reader.json", "history/index.json"} <= set(before)
    assert any(k.startswith("evidence/") for k in before) and any(k.startswith("reader-observations/") for k in before)
    assert any(k.startswith("quality-ledger/") for k in before)
    # Night two re-runs the session on a revised burst bar, so it brings evidence objects of its own: a
    # refusal that came after the evidence write would change the archive (held here before it is asked).
    fake_alpaca.add_history("AAA", qframe(ideal_bars(burst_range_pct=0.3, base_range=0.15, prior_range=0.1)))
    _, _, other = evening(tmp_path / "unbounded", market)
    assert {k for k in snapshot(other) if k.startswith("evidence/")} - set(before)
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
    # the projection is made only from a record within its bound, so neither downloaded file is stated
    assert not [r for r in caplog.records if r.getMessage().startswith("Reader ")]
    # mailed by the stage it stopped at, not as missing inputs, and never with the size
    text = _rendered(fake_resend.sent[-1]["html"])
    assert fake_resend.sent[-1]["subject"].startswith("FAILED — no plan for ")
    assert "It stopped at its publish stage, after its universe, fetch and session stages had passed;" in text
    assert report.PROBLEM_SENTENCES["coverage_thin"] not in text and said.group(1) not in text


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
    assert not [r for r in caplog.records if r.getMessage().startswith("Reader projection after delivery")]


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
    assert bound == 48 * 1024 * 1024 and reader.MAX_READER_BYTES == 32 * 1024 * 1024
    assert reader.MAX_OBSERVATION_BYTES == 32 * 1024 * 1024
    assert (morning.MAX_PUBLICATION_BYTES, issuer_evidence.MAX_PUBLICATION_BYTES, stop_research.MAX_PUBLICATION_BYTES,
            publish_issuer_evidence.MAX_RECORD_BYTES) == (bound,) * 4
    # the issuer's download and capture bounds are archived in every receipt's policy: not this number
    assert issuer_evidence.MAX_DOWNLOAD_BYTES == issuer_evidence.MAX_CAPTURE_BYTES == 32 * 1024 * 1024
    assert issuer_evidence.POLICY["max_download_bytes"] == 32 * 1024 * 1024
    js = (ROOT / "docs/app-reader.js").read_text()
    literal = re.search(r"const MAX_BYTES = ([0-9 *]+), MAX_CANONICAL_BYTES = ([0-9 *]+),", js)
    assert literal, "app-reader.js declares MAX_BYTES and MAX_CANONICAL_BYTES together"
    assert eval(literal.group(1), {"__builtins__": {}}) == reader.MAX_READER_BYTES   # digits and * only
    assert eval(literal.group(2), {"__builtins__": {}}) == bound
    # the page holds the record's identity to the canonical bound and what this module downloads to the reader's
    assert js.count("canonical.bytes <= MAX_CANONICAL_BYTES") == 1 and "canonical.bytes <= MAX_BYTES" not in js
    assert "MAX_BYTES, MAX_CANONICAL_BYTES };" in js     # both exported on SCStock.reader
    # the evidence retention scan reads every docs file whole, the record among them, under its own
    # bound: never below the record's, or a publishable record would stop the archive's pruning
    from src import provenance
    assert provenance.RETENTION_SCAN_BYTES >= bound


# --- the files the browser downloads: their own bounds ------------------------
def tiny():
    return compact({"schema_version": 2, "run": {}, "bursts": [], "observations": {"symbols": {"AAA": {"c": 1}}}})


def test_derive_refuses_a_projection_one_byte_over_its_own_bound_and_names_both_numbers(monkeypatch):
    raw = tiny()
    size = len(reader.derive(raw)[0])
    monkeypatch.setattr(reader, "MAX_READER_BYTES", size - 1)
    with pytest.raises(ValueError, match=rf"^reader projection is {size} bytes, over its {size - 1}-byte bound$"):
        reader.derive(raw)
    monkeypatch.setattr(reader, "MAX_READER_BYTES", size)      # at the bound it is published
    assert len(reader.derive(raw)[0]) == size


def test_derive_refuses_observations_one_byte_over_their_own_bound_and_names_both_numbers(monkeypatch):
    raw = tiny()
    size = len(reader.derive(raw)[1])
    monkeypatch.setattr(reader, "MAX_OBSERVATION_BYTES", size - 1)
    with pytest.raises(ValueError, match=rf"^reader observations are {size} bytes, over their {size - 1}-byte bound$"):
        reader.derive(raw)
    monkeypatch.setattr(reader, "MAX_OBSERVATION_BYTES", size)
    assert len(reader.derive(raw)[1]) == size


def test_derive_names_the_sidecar_when_both_downloaded_files_are_over_their_bounds(monkeypatch):
    """`_bounds()` asks the sidecar first, as `derive()` always has: a record
    whose projection and sidecar are both over is refused in the sidecar's words."""
    raw = tiny()
    projection, observations = map(len, reader.derive(raw))
    monkeypatch.setattr(reader, "MAX_READER_BYTES", projection - 1)
    monkeypatch.setattr(reader, "MAX_OBSERVATION_BYTES", observations - 1)
    with pytest.raises(ValueError, match=rf"^reader observations are {observations} bytes, "
                                         rf"over their {observations - 1}-byte bound$"):
        reader.derive(raw)


@pytest.mark.parametrize("size,level", [(800, "INFO"), (801, "WARNING"), (1000, "WARNING"), (1001, "ERROR")])
def test_the_run_log_states_each_downloaded_file_against_its_own_bound(size, level, monkeypatch, caplog):
    monkeypatch.setattr(reader, "MAX_READER_BYTES", 1000)
    monkeypatch.setattr(reader, "MAX_OBSERVATION_BYTES", 2000)  # a different number: each line reads its own
    monkeypatch.setattr(reader, "MAX_PUBLICATION_BYTES", 10)    # the canonical bound is not the one read
    caplog.set_level("INFO", logger="spicystock.reader")
    reader.log_projection(size, size * 2)
    projection, observations = [r for r in caplog.records if r.name == "spicystock.reader"]
    assert projection.levelname == observations.levelname == level
    over = size > 1000
    assert projection.getMessage() == f"Reader projection: {size} of 1000 bytes" + (
        "; over its bound, so the night is refused before anything is installed." if over else ".")
    assert observations.getMessage() == f"Reader observations: {size * 2} of 2000 bytes" + (
        "; over their bound, so the night is refused before anything is installed." if over else ".")


def test_the_downloaded_files_after_delivery_are_stated_in_their_own_words(monkeypatch, caplog):
    monkeypatch.setattr(reader, "MAX_READER_BYTES", 1000)
    caplog.set_level("INFO", logger="spicystock.reader")
    reader.log_projection(1001, reader.MAX_OBSERVATION_BYTES + 1, after_delivery=True)
    projection, observations = caplog.records
    assert projection.levelname == observations.levelname == "ERROR"
    assert projection.getMessage() == (
        "Reader projection after delivery: 1001 of 1000 bytes; "
        "over its bound, so this write is refused and the record first installed stays.")
    assert observations.getMessage() == (
        f"Reader observations after delivery: {reader.MAX_OBSERVATION_BYTES + 1} of {reader.MAX_OBSERVATION_BYTES} "
        "bytes; over their bound, so this write is refused and the record first installed stays.")


def test_the_downloaded_files_lines_never_fail_the_night(caplog):
    caplog.set_level("INFO", logger="spicystock.reader")
    reader.log_projection(None, 10)
    projection, observations = [r for r in caplog.records if r.name == "spicystock.reader"]
    assert projection.levelname == "WARNING" and projection.getMessage() == "Reader projection could not be measured (TypeError)."
    assert observations.levelname == "INFO" and observations.getMessage().startswith("Reader observations: 10 of ")


def sizes(caplog, after=""):
    """The night's three lines, each once: the canonical record's, the projection's and the sidecar's."""
    return tuple(logged(caplog, name + after)[1] for name in ("Canonical record", "Reader projection", "Reader observations"))


def test_a_night_with_every_file_exactly_at_its_bound_publishes(market, claude, fake_resend, tmp_path, monkeypatch, caplog):
    caplog.set_level("INFO", logger="spicystock.reader")
    evening(tmp_path / "measure", market)
    canonical, projection, observations = sizes(caplog, " after delivery")
    assert projection < canonical and observations < canonical  # the projection defers the observations
    caplog.clear()
    # each bound at exactly its night's final size: every bound is inclusive, and the night publishes
    # with every file at its bound (which bound refuses which file, the refusal tests hold)
    monkeypatch.setattr(reader, "MAX_PUBLICATION_BYTES", canonical)
    monkeypatch.setattr(reader, "MAX_READER_BYTES", projection)
    monkeypatch.setattr(reader, "MAX_OBSERVATION_BYTES", observations)
    rep, data, docs = evening(tmp_path / "night", market)
    assert rep.exit_code() == 0 and rep.published and data["run"]["email"] == "delivered", rep.failure
    assert len((docs / "data.json").read_bytes()) == canonical > max(projection, observations)
    assert len((docs / "reader.json").read_bytes()) == projection
    ref = reader.check_assets(docs)                  # the committed companions check under the same three bounds
    assert ref["bytes"] == observations and len((docs / ref["path"]).read_bytes()) == observations


@pytest.mark.parametrize("which", ["projection", "observations"])
def test_a_downloaded_file_over_its_bound_is_refused_before_anything_is_installed_and_says_why(which, market, claude, fake_alpaca, fake_resend, tmp_path, monkeypatch, caplog):
    caplog.set_level("INFO", logger="spicystock.reader")
    _, data, docs = evening(tmp_path, market)          # night one publishes everything a night keeps
    _, projection, observations = sizes(caplog)
    before = snapshot(docs)
    fake_alpaca.add_history("AAA", qframe(ideal_bars(burst_range_pct=0.3, base_range=0.15, prior_range=0.1)))
    caplog.clear()
    name, constant, size, words = {
        "projection": ("Reader projection", "MAX_READER_BYTES", projection, ("reader projection is", "its")),
        "observations": ("Reader observations", "MAX_OBSERVATION_BYTES", observations, ("reader observations are", "their")),
    }[which]
    bound = size // 2
    monkeypatch.setattr(reader, constant, bound)                  # the canonical bound is left at 48 MiB
    rep, _, _ = evening(tmp_path, market)              # night two, the same docs, one downloaded file over its bound
    assert rep.exit_code() == pipeline.EXIT_FAILED and not rep.published and rep.stage == "publish"
    assert snapshot(docs) == before                   # nothing pruned, written or installed
    said = re.search(rf"{words[0]} (\d+) bytes, over {words[1]} (\d+)-byte bound", rep.failure)
    assert said and int(said.group(2)) == bound and int(said.group(1)) > bound, rep.failure
    record, line = logged(caplog, "Canonical record"), logged(caplog, name)
    assert record[0].levelname == "INFO" and record[1] < reader.MAX_PUBLICATION_BYTES
    assert line[0].levelname == "ERROR" and line[1] == int(said.group(1))
    assert line[0].getMessage() == (f"{name}: {said.group(1)} of {bound} bytes; "
                                    f"over {words[1]} bound, so the night is refused before anything is installed.")
    text = _rendered(fake_resend.sent[-1]["html"])
    assert "It stopped at its publish stage" in text and said.group(1) not in text


def test_a_restamp_whose_projection_crosses_its_bound_leaves_the_first_record_installed(market, claude, fake_resend, tmp_path, monkeypatch, caplog):
    caplog.set_level("INFO", logger="spicystock.reader")
    evening(tmp_path / "measure", market)
    _, first = logged(caplog, "Reader projection")
    _, final = logged(caplog, "Reader projection after delivery")
    assert final > first                                # "delivered" is longer than the word first installed
    caplog.clear()
    monkeypatch.setattr(reader, "MAX_READER_BYTES", first)
    rep, data, docs = evening(tmp_path / "night", market)
    assert rep.exit_code() == pipeline.EXIT_FAILED_AFTER_PUBLISH and rep.published, rep.failure
    assert rep.stage == "restamp" and rep.failure == (
        f"ValueError: reader projection is {final} bytes, over its {first}-byte bound")
    assert len((docs / "reader.json").read_bytes()) == first and data["run"]["email"] != "delivered"
    raw = (docs / "data.json").read_bytes()
    assert json.loads((docs / "reader.json").read_bytes())["canonical"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert rep.quality_ledger["status"] == "retained" and Path(rep.quality_ledger["path"]).exists()
    line, size = logged(caplog, "Reader projection after delivery")
    assert size == final and line.levelname == "ERROR"
