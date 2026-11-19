"""The publication gate and the analyst's brief: ``brief_files()`` holds the
committed pair to the committed record by its hashes, with the standard
library alone, and names the two files for the served-byte comparison. It
holds the binding and nothing else, so a merge that rewords a sentence does
not turn the gate red before the next evening run rewrites the pair."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src import brief, reader
from tools import publish_dashboard as publisher

PAGE = Path(__file__).parent / "fixtures" / "page"
ROOT = Path(__file__).parent.parent
REFUSAL = "The daily brief does not match the committed canonical publication."


def install_record(docs: Path, canonical: bytes) -> None:
    projected, observations = reader.derive(canonical)
    descriptor = json.loads(projected)["retained_observations"]
    (docs / "data.json").write_bytes(canonical)
    (docs / "reader.json").write_bytes(projected)
    (docs / "reader-observations").mkdir(exist_ok=True)
    (docs / descriptor["path"]).write_bytes(observations)


@pytest.fixture
def publication(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.html").write_text('<script src="app.js"></script>')
    (docs / "app.js").write_text("// synthetic page module")
    install_record(docs, (PAGE / "full.json").read_bytes())
    (docs / "picks.json").write_bytes((PAGE / "full-picks.json").read_bytes())
    for name in ("historical-validation.json", "historical-findings.json"):
        (docs / name).write_bytes(b"{}")
    return tmp_path, docs


def write_brief(docs: Path) -> dict:
    return brief.write_publication((docs / "data.json").read_bytes(), (docs / "picks.json").read_bytes(), docs)


def test_no_brief_names_no_files_and_the_rest_of_the_inventory_is_unchanged(publication):
    root, docs = publication
    assert publisher.brief_files(root) == ()
    assert not {"brief.json", "brief.md"} & set(publisher.public_files(root))


def test_a_bound_pair_is_part_of_the_served_byte_inventory(publication):
    root, docs = publication
    assert write_brief(docs)["status"] == "derived"
    assert publisher.brief_files(root) == ("brief.json", "brief.md")
    files = publisher.public_files(root)
    assert files.count("brief.json") == files.count("brief.md") == 1
    assert files.index("reader.json") < files.index("brief.json") < files.index("brief.md")


def test_a_pair_left_behind_by_an_older_record_fails_publication(publication):
    root, docs = publication
    write_brief(docs)
    install_record(docs, (PAGE / "yellow.json").read_bytes())          # a newer record; the pair was not rewritten
    with pytest.raises(RuntimeError, match=REFUSAL):
        publisher.brief_files(root)
    with pytest.raises(RuntimeError, match=REFUSAL):
        publisher.public_files(root)
    write_brief(docs)
    assert publisher.brief_files(root) == ("brief.json", "brief.md")


def test_a_pair_bound_to_another_pick_ledger_fails_publication(publication):
    root, docs = publication
    write_brief(docs)
    (docs / "picks.json").write_bytes((docs / "picks.json").read_bytes() + b" ")
    with pytest.raises(RuntimeError, match=REFUSAL):
        publisher.brief_files(root)
    (docs / "picks.json").unlink()                                      # the brief names a ledger the checkout lacks
    with pytest.raises(RuntimeError, match=REFUSAL):
        publisher.brief_files(root)


@pytest.mark.parametrize("missing", ["brief.json", "brief.md"])
def test_half_a_pair_fails_publication(publication, missing):
    root, docs = publication
    write_brief(docs)
    (docs / missing).unlink()
    with pytest.raises(RuntimeError, match=REFUSAL):
        publisher.brief_files(root)


@pytest.mark.parametrize("fault", ["symlink", "one_byte", "markdown_of_another", "over_bound", "not_json"])
def test_a_pair_the_gate_cannot_hold_to_the_record_fails_publication(publication, fault, tmp_path):
    root, docs = publication
    write_brief(docs)
    if fault == "symlink":
        kept = tmp_path / "kept.md"
        kept.write_bytes((docs / "brief.md").read_bytes())
        (docs / "brief.md").unlink()
        (docs / "brief.md").symlink_to(kept)
    elif fault == "one_byte":
        raw = (docs / "brief.json").read_bytes()
        (docs / "brief.json").write_bytes(raw.replace(b'"trigger":124.21', b'"trigger":124.22', 1))
    elif fault == "markdown_of_another":
        other = brief.compose((PAGE / "yellow.json").read_bytes(), None)[1]
        (docs / "brief.md").write_bytes(other)
    elif fault == "over_bound":
        (docs / "brief.md").write_bytes((docs / "brief.md").read_bytes() + b" " * brief.MAX_MD_BYTES)
    else:
        (docs / "brief.json").write_bytes(b"not json\n")
    with pytest.raises(RuntimeError, match=REFUSAL):
        publisher.brief_files(root)


def test_the_gate_holds_the_binding_and_not_this_codes_wording(publication):
    """The pair on main was written by the code of the last evening run. A pair whose sentences are not this
    code's, bound to the committed bytes, passes the gate; ``brief.validate()`` is what refuses it."""
    root, docs = publication
    write_brief(docs)
    data_raw, picks_raw = (docs / "data.json").read_bytes(), (docs / "picks.json").read_bytes()
    older = json.loads((docs / "brief.json").read_bytes())
    older["limits"] = ["A sentence an earlier version of the code wrote."]
    older_json = brief._encode(older)
    older_md = brief.fit_md(older, older_json)
    (docs / "brief.json").write_bytes(older_json)
    (docs / "brief.md").write_bytes(older_md)
    assert publisher.brief_files(root) == ("brief.json", "brief.md")
    with pytest.raises(ValueError, match="brief limits differ"):
        brief.validate(data_raw, picks_raw, older_json, older_md)


def test_the_unavailable_pair_is_bound_and_passes(publication):
    root, docs = publication
    json_raw, md_raw = brief.unavailable((docs / "data.json").read_bytes(), (docs / "picks.json").read_bytes(), "KeyError")
    (docs / "brief.json").write_bytes(json_raw)
    (docs / "brief.md").write_bytes(md_raw)
    assert publisher.brief_files(root) == ("brief.json", "brief.md")


def test_the_brief_inventory_needs_only_the_standard_library(publication):
    root, docs = publication
    write_brief(docs)
    code = ("import sys; sys.path.insert(0, sys.argv[1]); from pathlib import Path; "
            "from tools.publish_dashboard import brief_files; print(brief_files(Path(sys.argv[2]))); "
            "sys.exit(1 if any(m in sys.modules for m in ('pandas', 'numpy', 'exchange_calendars')) else 0)")
    done = subprocess.run([sys.executable, "-S", "-c", code, str(ROOT), str(root)], capture_output=True, text=True)
    assert done.returncode == 0 and done.stdout.strip() == "('brief.json', 'brief.md')", done.stdout + done.stderr


def test_the_committed_tree_carries_no_production_brief_or_a_bound_one():
    # the evening run writes the pair; until it has, the gate names no brief file for the committed docs
    names = publisher.brief_files(ROOT)
    assert names in ((), ("brief.json", "brief.md"))
