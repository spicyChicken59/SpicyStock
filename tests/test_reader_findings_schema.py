"""The findings schema offers a reply only the citations its criterion may make.

reader_authority.validate() is the authority and is unchanged by request
version 3. The schema -- sent as output_config.format and printed in the
instruction -- is held to it: every path a branch offers, the validator
accepts under that criterion, and every path the validator refuses as outside
the criterion, no branch offers. The 30 replies reader authority refused from
23 September to 29 October 2026 (tests/fixtures/grading/reader-authority-
refusals/) are the evidence the schema was built from: 26 carried a citation no
branch offers, and the other 4 cited a measured defect without its FAIL or
PARTIAL status, a value condition no schema can carry.
"""
from __future__ import annotations

import glob
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from src import grader, reader_authority as ra

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/grading/reader-authority-refusals/refusals.json"
REFUSALS = json.loads(FIXTURE.read_text(encoding="utf-8"))["refusals"]
EVERY_PATH = [p for letter, names in ra.CHECK_VALUES.items()
              for p in (f"checks.{letter}.status", *(f"checks.{letter}.values.{n}" for n in names))]
FOREIGN = ["burst.gap_pct", "checks.C", "checks.C.values", "checks.C.values.nope", "checks.Z.status", "flags"]


def _block(status="FAIL"):
    return {"version": 1, "checks": {letter: {"status": status, "values": {n: 1.5 for n in names}}
                                      for letter, names in ra.CHECK_VALUES.items()}}


def _value(block, path):
    out = block
    for part in path.split("."):
        out = out[part]
    return out


def _verdict(criterion, path, block):
    try:
        value = _value(block, path)
    except (KeyError, TypeError):
        value = 1.5
    finding = {"criterion": criterion, "source": ra.CRITERIA[criterion][0],
               "evidence": [{"path": path, "value": value}],
               "observation": ra.OBSERVATIONS[criterion][0]}
    try:
        ra.validate({"grade": "C", "reason": "r", "findings": [finding]},
                    {"quality_grade": "A+", "reader_evidence": block}, chart_seen=True)
    except ra.ReaderAuthorityError as error:
        return str(error)
    return "accepted"


def _branch(criterion):
    return next(b for b in ra.FINDINGS_SCHEMA["items"]["anyOf"]
                if b["properties"]["criterion"]["const"] == criterion)


def conforms(finding):
    """Whether one finding is an instance of some branch, as constrained decoding reads it."""
    if not isinstance(finding, dict) or set(finding) != set(ra.FINDING_FIELDS):
        return False
    criterion = finding["criterion"]
    if criterion not in ra.CRITERIA:
        return False
    props = _branch(criterion)["properties"]
    citations = finding["evidence"]
    return (finding["source"] == props["source"]["const"]
            and finding["observation"] in props["observation"]["enum"]
            and isinstance(citations, list)
            and all(isinstance(c, dict) and set(c) == set(ra.CITATION_FIELDS)
                    and c["path"] in props["evidence"]["items"]["properties"]["path"]["enum"]
                    for c in citations))


@pytest.mark.parametrize("criterion", list(ra.CRITERIA))
def test_every_offered_path_is_one_the_validator_accepts_under_its_criterion(criterion):
    block = _block()
    offered = _branch(criterion)["properties"]["evidence"]["items"]["properties"]["path"]["enum"]
    assert offered == ra.paths(criterion)
    for path in EVERY_PATH + FOREIGN:
        verdict = _verdict(criterion, path, block)
        if path in offered:
            # A value citation under measured_quality still needs a FAIL or
            # PARTIAL status beside it: that is the validator's, not the path's.
            assert verdict in ("accepted", "measured defect requires a recorded FAIL or PARTIAL"), (path, verdict)
        else:
            assert verdict in ("evidence outside criterion authority", "unknown evidence path"), (path, verdict)


def test_every_path_the_validator_refuses_as_outside_a_criterion_is_offered_by_no_branch():
    block = _block()
    for criterion in ra.CRITERIA:
        refused = {p for p in EVERY_PATH + FOREIGN
                   if _verdict(criterion, p, block) == "evidence outside criterion authority"}
        assert refused and not refused & set(ra.paths(criterion)), criterion


def test_the_check_values_are_the_keys_quality_writes_in_the_order_it_writes_them():
    seen = 0
    for path in sorted(glob.glob(str(ROOT / "tests/fixtures/page/*.json"))):
        record = json.loads(Path(path).read_text(encoding="utf-8"))
        for burst in record.get("bursts", []):
            for check in burst["quality"]["checks"]:
                assert tuple(check["values"]) == ra.CHECK_VALUES[check["letter"]], (path, check["letter"])
                seen += 1
    assert seen > 100
    statuses = {check["status"] for path in glob.glob(str(ROOT / "tests/fixtures/page/*.json"))
                for burst in json.loads(Path(path).read_text(encoding="utf-8")).get("bursts", [])
                for check in burst["quality"]["checks"]}
    assert "UNMEASURED" in statuses, "an unmeasured check writes its keys too"


def test_the_retained_refusals_are_whole_and_still_refused_by_the_unchanged_validator():
    assert len(REFUSALS) == 30
    for entry in REFUSALS:
        assert hashlib.sha256(entry["text"].encode()).hexdigest() == entry["text_sha256"]
        reply = json.loads(entry["text"])
        with pytest.raises(ra.ReaderAuthorityError) as caught:
            ra.validate(reply, {"quality_grade": entry["mechanical_grade"],
                                "reader_evidence": entry["reader_evidence"]}, chart_seen=True)
        assert entry["error"] == f"src.ReaderAuthorityError: {caught.value}", entry["ticker"]


def test_26_of_the_30_carried_a_citation_no_branch_offers_and_the_other_4_a_measured_defect_without_its_status():
    excluded, rest = [], []
    for entry in REFUSALS:
        findings = json.loads(entry["text"])["findings"]
        (excluded if not all(conforms(f) for f in findings) else rest).append(entry)
    assert len(excluded) == 26 and len(rest) == 4
    assert all("outside criterion authority" in e["error"] for e in excluded)
    assert {e["error"] for e in rest} == {
        "src.ReaderAuthorityError: measured defect requires a recorded FAIL or PARTIAL"}
    assert sorted(e["ticker"] for e in rest) == ["INGN", "JAKK", "MSM", "RVTY"]


def test_every_finding_a_branch_admits_conforms_and_a_cross_letter_one_does_not():
    good = {"criterion": "overhead_supply", "source": "strategy.chart.supply",
            "evidence": [{"path": "checks.C.values.giveback", "value": 0.2}],
            "observation": "prior_trading_above_signal"}
    assert conforms(good)
    for path in ("checks.Y.values.gain_since_move_start_pct", "checks.L.values.leg_gain_pct", "burst.gap_pct"):
        assert not conforms({**good, "evidence": [{"path": path, "value": 1}]})
    assert not conforms({**good, "source": "strategy.quality"})
    assert not conforms({**good, "observation": "gap_dominated"})


def _schema_nodes(node):
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from _schema_nodes(value)
    elif isinstance(node, list):
        for value in node:
            yield from _schema_nodes(value)


def test_the_score_schema_uses_only_what_structured_outputs_document():
    """https://platform.claude.com/docs/en/build-with-claude/structured-outputs, read 30 October 2026."""
    schema = grader.SCORE_SCHEMA
    # Unsupported there, or supported with limits this schema does not need.
    avoided = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
               "minLength", "maxLength", "minItems", "maxItems", "oneOf", "not", "if", "then", "else",
               "pattern", "patternProperties", "uniqueItems", "$ref", "$defs", "allOf"}
    unions = 0
    for node in _schema_nodes(schema):
        if not isinstance(node, dict):
            continue
        if "properties" in node and isinstance(node["properties"], dict) and node.get("type") == "object":
            assert node.get("additionalProperties") is False
            assert set(node.get("required", [])) == set(node["properties"]), "no optional parameters"
        if isinstance(node.get("type"), list) or "anyOf" in node:
            unions += 1
        if "enum" in node:
            assert all(isinstance(v, (str, int, float, bool)) or v is None for v in node["enum"])
        assert not avoided & set(node), sorted(avoided & set(node))
    assert unions <= 16, "parameters with union types across a request"
    assert unions == 1 + len(ra.CRITERIA)


def test_request_version_3_is_archived_and_the_default_model_gets_the_branches():
    assert grader.REQUEST_VERSION == 3 and grader.RULES == {"grading.reader_request_version": 3}
    kwargs = grader.request_kwargs("system", [{"type": "text", "text": "x"}], "claude-sonnet-4-6")
    findings = kwargs["output_config"]["format"]["schema"]["properties"]["findings"]
    assert findings == ra.FINDINGS_SCHEMA and len(findings["items"]["anyOf"]) == len(ra.CRITERIA)


def test_the_instruction_says_a_citation_names_only_its_criterions_checks():
    text = ra.instruction()
    assert "A citation names only a check its own criterion lists" in text
    assert "One citation outside its criterion refuses the whole reply" in text
    assert "cited as that check's status path" in text


def _have(commit):
    return subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=ROOT,
                          capture_output=True).returncode == 0


@pytest.fixture(scope="module")
def commits():
    named = sorted({e["commit"] for e in REFUSALS})
    assert all(len(c) == 40 and all(ch in "0123456789abcdef" for ch in c) for c in named)
    missing = [c for c in named if not _have(c)]
    if missing:
        done = subprocess.run(["git", "fetch", "--quiet", "--no-tags", "--depth=1", "origin", *missing],
                              cwd=ROOT, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
    return named


def test_each_frozen_refusal_is_the_one_its_publication_recorded(commits):
    by_commit = {}
    for entry in REFUSALS:
        by_commit.setdefault(entry["commit"], []).append(entry)
    for commit, entries in by_commit.items():
        record = json.loads(subprocess.run(["git", "show", f"{commit}:docs/data.json"], cwd=ROOT,
                                           capture_output=True, check=True).stdout)
        assert record["run"]["session"] == entries[0]["session"]
        bursts = {b["ticker"]: b for b in record["bursts"]}
        for entry in entries:
            burst = bursts[entry["ticker"]]
            attempt = next(a for a in burst["claude"]["attempts"]
                           if (a.get("response") or {}).get("text_sha256") == entry["text_sha256"])
            assert attempt["response"]["text"] == entry["text"] and attempt["error"] == entry["error"]
            assert burst["quality"]["grade"] == entry["mechanical_grade"]
            assert entry["reader_evidence"]["checks"] == {
                c["letter"]: {"status": c["status"], "values": c["values"]} for c in burst["quality"]["checks"]}


# ---------------------------------------------------------- replay of v2 ----
#: SHA-256 of the authority instruction and of the findings schema request
#: version 2 sent, computed from src/reader_authority.py at 13b4da23 (the last
#: commit before request version 3), so a later edit cannot move what the
#: verifier rebuilds for a version-2 record.
V2_INSTRUCTION_SHA256 = "13e1c585a8eae0dd9f775eb62e7e3a4722d171e23cc80a35f22683c923da8745"
V2_SCHEMA_SHA256 = "a7aecd2c35932a11edc50c43080267e7edb0e41a9d310079cddb8ee987d06a7d"


def test_request_version_2_is_rebuilt_byte_for_byte():
    assert hashlib.sha256(ra.instruction(2).encode()).hexdigest() == V2_INSTRUCTION_SHA256
    assert hashlib.sha256(json.dumps(ra.findings_schema(2), sort_keys=True).encode()).hexdigest() == V2_SCHEMA_SHA256
    assert grader.score_schema(2)["properties"]["findings"] is ra.FINDINGS_SCHEMA_V2
    assert grader.score_schema(3) == grader.SCORE_SCHEMA
    kwargs = grader.request_kwargs("s", [{"type": "text", "text": "x"}], "claude-sonnet-4-6", request_version=2)
    assert kwargs["output_config"]["format"]["schema"]["properties"]["findings"] == ra.FINDINGS_SCHEMA_V2
    assert ra.instruction(2) != ra.instruction(3) and ra.instruction() == ra.instruction(3)


@pytest.mark.parametrize("version", [0, 1, 4, "3", 3.0, True, None])
def test_no_findings_schema_is_invented_for_another_request_version(version):
    with pytest.raises(ValueError):
        ra.findings_schema(version)


def _october_9():
    """The real 9 October 2026 publication (request version 2) and its retained objects."""
    import gzip
    raw = gzip.decompress((ROOT / "tests/fixtures/stop-research/current-publication.json.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == "f5cbe38eaa38647364f4994bb867bbb7da4354e6a8f7f28315fb96e9b650ef0d"
    return json.loads(raw), ROOT / "tests/fixtures/retained-evidence"


def test_a_request_version_2_publication_still_verifies_with_its_reader_requests_rebuilt():
    from src import provenance
    data, objects = _october_9()
    assert data["rules"]["grading"]["reader_request_version"] == 2
    read = [r["ticker"] for r in data["bursts"] if (r.get("evidence") or {}).get("reader_input")]
    assert read, "the record carries reader requests for the verifier to rebuild"
    result = provenance.verify(data, objects=objects, require_sources=True)
    assert result["status"] == "PASS", (result["breaks"][:3], result["missing"][:3])


def test_a_request_version_the_grader_cannot_rebuild_is_partial_never_pass(monkeypatch):
    from src import provenance
    data, objects = _october_9()
    monkeypatch.setattr(grader, "REPLAYABLE_REQUEST_VERSIONS", (3,))
    result = provenance.verify(data, objects=objects, require_sources=True)
    assert result["status"] == "PARTIAL" and not result["breaks"]
    assert any("grading.reader_request_version" in m for m in result["missing"])
