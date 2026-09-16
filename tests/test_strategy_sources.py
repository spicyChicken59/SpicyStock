"""Dated source attribution and its operational boundary, without market replay.

These assertions pin inspected publications, not search results or community
titles. The Markdown table is the single source-mapped discovery contract.
Existing scan/grader/provenance suites exercise the wider decision pipeline.
"""
from copy import deepcopy
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from src import discovery, pipeline, provenance, report, scans
from tests.test_scans import bar, flat, frame

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "knowledge/reaction-discovery.md"


def mapped_routes():
    text = CONTRACT.read_text()
    rows = {}
    for line in text.splitlines():
        if line.startswith(("| burst |", "| dollar |")):
            route, classification, date, formula, source = [s.strip() for s in line.strip("|").split("|")]
            assert route not in rows
            rows[route] = (classification, date, formula.strip("`"), source)
    return rows, dict(re.findall(r"^\[([^]]+)\]: (https://\S+)$", text, re.M))


@pytest.mark.parametrize("route,expected,url", [
    ("burst", ("PRIMARY", "2015-05-21", "c/c1>=1.04 and v>v1 and v>=100000", "[P15]"),
     "https://stockbee.blogspot.com/2015/05/how-do-stock-move-on-3-to-5-day-time.html"),
    ("dollar", ("PRIMARY", "2017-07-13", "c-o>=.90 and v>100000", "[L17]"),
     "https://stockbee.blogspot.com/2017/07/my-process-loop-to-trade-4-bo-and-bo.html"),
])
def test_selected_formula_has_its_inspected_primary_version(route, expected, url):
    rows, references = mapped_routes()
    assert set(rows) == {"burst", "dollar"}
    assert rows[route] == expected
    assert references[expected[-1].strip("[]")] == url


def test_source_contract_exposes_variants_and_separates_implementation():
    text = " ".join(CONTRACT.read_text().split())
    _, references = mapped_routes()
    assert "**LATER BONDE" in text
    assert "`c-o>=.90 and v>=100000`" in text  # 2016 inclusive variant, not selected
    assert references["P16"] == "https://stockbee.blogspot.com/2016/09/how-i-scan-for-swing-trade-ideas.html"
    assert "**COMMUNITY:** [C22]" in text and "underlying Pine source was not retrieved" in text
    assert references["C22"] == "https://www.tradingview.com/script/Rf67M40u-StockBee-MB-Bullish/"
    assert "**IMPLEMENTATION — normalization:**" in text
    assert "not a claim of bit-for-bit TC2000 equivalence" in text
    assert "No claim that the selected 2017 formula is his latest or only version" in text


@pytest.mark.parametrize("volume,expected", [(100_000, ["burst"]), (100_001, ["burst", "dollar"])])
def test_selected_source_versions_have_different_volume_boundaries(volume, expected):
    # Both price clauses pass exactly, and burst's prior-volume test passes.
    # Only the dated inclusive/strict current-volume distinction decides this.
    df = frame([bar(100, v=99_999), bar(104, o=103.10, v=volume)])
    found = {"burst": scans.burst_4pct(df), "dollar": scans.dollar_breakout(df)}
    assert [route for route, result in found.items() if result is not None] == expected


def test_dollar_admission_does_not_import_community_or_quality_filters():
    # Sub-4%, lower volume than yesterday, and far from the high. Discovery
    # still admits the body; the actual quality layer records the H failure.
    df = frame(flat(260) + [bar(100.90, o=100, h=110, l=99, v=100_001)])
    rows, _, _ = pipeline.scan_frames({"SYN": df}, SimpleNamespace(names={}, flags={}), pipeline.RunReport())
    row = rows[0]
    assert row["scan"] == "dollar" and row["gain_pct"] == 0.9
    assert row["discovery"]["admitted_by"] == ["dollar"]
    assert row["discovery"]["applicable_rules"] == {"dollar": {"min_move": .9, "min_volume_exclusive": 100000}}
    assert row["volume_vs_prior"] < 1
    assert next(c for c in row["quality"]["checks"] if c["letter"] == "H")["passed"] is False
    assert discovery.conflicting_fields(row["discovery"], {"reason": "Below the 4% minimum."}) == ["reason"]
    assert discovery.conflicting_fields(row["discovery"], {"reason": "The close is far from the high."}) == []


def test_dollar_reference_is_the_open_even_when_previous_close_differs():
    gap = frame([bar(90), bar(100.50, o=100, v=100_001)])
    recovery = frame([bar(102), bar(100.90, o=100, v=100_001)])
    assert scans.dollar_breakout(gap) is None  # $10.50 from prior close, $0.50 body
    assert scans.dollar_breakout(recovery)["move"] == .9  # negative vs prior close


def test_source_only_revision_preserves_runtime_rules_and_provenance_v1():
    data = json.loads((ROOT / "tests/fixtures/page/full.json").read_bytes())
    picks = json.loads((ROOT / "tests/fixtures/page/full-picks.json").read_bytes())
    before = deepcopy((data, picks))
    current = pipeline.build_rules(SimpleNamespace(identity=data["rules"]["universe"]["identity"]))
    assert current == data["rules"]
    assert report.rules_version(current) == data["app"]["rules_version"]
    assert discovery.VERSION == provenance.VERSION == 1
    result = provenance.verify(data, picks, ROOT / "tests/fixtures/provenance/objects", require_picks=True)
    assert result["status"] == "PASS", result
    assert (data, picks) == before


def test_a_future_formula_change_cannot_reuse_rules_or_evidence_identity():
    # Demonstrate the existing identity mechanism, without changing a rule or
    # asserting any alternative threshold improves trading outcomes.
    data = json.loads((ROOT / "tests/fixtures/page/full.json").read_bytes())
    changed = deepcopy(data)
    changed["rules"]["dollar"]["min_move"] = 1.23
    assert report.rules_version(changed["rules"]) != data["app"]["rules_version"]
    assert provenance.digest(provenance.context(changed)) != data["run"]["evidence"]["context_sha256"]
    result = provenance.verify(changed, objects=ROOT / "tests/fixtures/provenance/objects")
    assert result["status"] == "FAIL" and any("context digest" in s for s in result["breaks"])


def test_public_method_and_readme_do_not_assert_a_universal_four_percent_day():
    for path in ("README.md", "docs/app.js"):
        text = " ".join((ROOT / path).read_text().split())
        assert "a 4% range-expansion day out of a quiet base" not in text
        assert "reaction-discovery.md" in text
    method = (ROOT / "knowledge/method.md").read_text()
    assert "[source contract](reaction-discovery.md)" in method
    assert "2015/2017" not in method  # those printed burst volume operators differ
