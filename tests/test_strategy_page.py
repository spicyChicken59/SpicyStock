"""The strategy page (src/strategy_page.py, tools/build_strategy_page.py).

These hold the committed page to what the code and the committed record
write, every number on it to a constant or a record field (a change to
either moves the page, and the module types no digit of its own), every
exit rule and the EP9M attribution to plan.EXIT_RULES, the funnel to the
record's own sentence, and the evening's write and the gate's inventory to
the page."""
from __future__ import annotations

import ast
import copy
import json
import re
from html import unescape
from pathlib import Path

import pytest

from src import breadth, pipeline, plan, quality, scans, strategy_page as sp

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
RAW = (DOCS / "data.json").read_bytes()


def text_of(page: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page)))


def test_the_committed_page_is_what_the_code_and_the_committed_record_write():
    assert sp.check(DOCS) == []
    assert (DOCS / sp.FILE).read_text() == sp.build(RAW)


def test_the_page_names_the_record_it_was_built_from():
    data = json.loads(RAW)
    page = sp.build(RAW)
    assert data["app"]["rules_version"] in page and data["run"]["session"] in page
    import hashlib
    assert f"record sha256 {hashlib.sha256(RAW).hexdigest()}" in page


@pytest.mark.parametrize("module, name, value, words", [
    (plan, "MAX_STOP_PCT", 5.0, "within 5% of the limit"),
    (plan, "TRIGGER_CENTS", 0.03, "the larger of $0.03"),
    (plan, "IDEAL_STOP_PCT", 2.5, "A stop wider than 2.5%"),
    (scans, "DOLLAR_MOVE", 1.25, "at least $1.25 over the session's own open"),
    (scans, "MIN_VOLUME", 250_000, "at least 250,000 shares"),
    (quality, "MIN_A_PLUS_LETTERS", 5, "A+ also needs 5 checks"),
    (quality, "VETO_UP_DAYS", 4, "at 4 or more rising closes"),
    (breadth, "REFERENCE_UNIVERSE", 7000, "reference universe of 7,000 names"),
    (pipeline, "YELLOW_GRADES", ("A+", "A"), "yellow 0.5 A+, A"),
])
def test_a_constant_the_page_prints_moves_the_page(monkeypatch, module, name, value, words):
    before = text_of(sp.build(RAW))
    assert words not in before
    monkeypatch.setattr(module, name, value)
    assert words in text_of(sp.build(RAW))


def test_tonights_thresholds_and_values_are_the_records():
    data = json.loads(RAW)
    data["rules"]["plan"]["entry_above_pct"] = 6.0
    assert "the close plus 6% (the outer extension line, as the record archives it)" in text_of(
        sp.build(json.dumps(data).encode()))
    data["breadth"]["regime"]["thresholds"]["down4_alarm"] = 123.4
    data["breadth"]["regime"]["inputs"]["down4"] = 999
    page = text_of(sp.build(json.dumps(data).encode()))
    assert "today at or over 123.4" in page and "999 fired" in page
    data["breadth"]["regime"]["verdict"] = "green"
    assert "Tonight's light is green" in text_of(sp.build(json.dumps(data).encode()))
    bare = copy.deepcopy(data)
    del bare["breadth"]["regime"]["inputs"]
    assert "The record carries no regime inputs to print." in text_of(sp.build(json.dumps(bare).encode()))


def test_every_exit_rule_is_printed_with_its_source_and_the_third_party_rule_is_attributed():
    page = sp.build(RAW)
    for rule in plan.EXIT_RULES:
        assert f"<code>{rule['key']}</code>" in page
    third = [r["key"] for r in plan.EXIT_RULES if r["source"] == "T"]
    assert third == ["no_breakeven"]
    text = text_of(page)
    assert f"{third[0]} is a third party's measurement, theStrat Lab EP9M backtest, of a different setup" in text
    assert f"at least {scans.EP9M_MIN_VOLUME:,} shares" in text
    assert all(f"{k}: {v}" in text for k, v in sp.SOURCE_MARKS.items())


def test_the_funnel_is_the_records_own_sentence_and_its_stages():
    data = json.loads(RAW)
    text = text_of(sp.build(RAW))
    assert data["funnel"]["sentence"] in text
    for key, n in data["funnel"]["reaction"]["stages"].items():
        if n:
            assert f"{data['funnel']['labels'][key]} {n:,}" in text
    del data["funnel"]
    assert "This record carries no funnel." in text_of(sp.build(json.dumps(data).encode()))


def test_the_module_types_no_number_of_its_own():
    """Every digit the page prints comes from a constant or the record: the
    module's own text carries none outside its HTML scaffolding."""
    tree = ast.parse((ROOT / "src" / "strategy_page.py").read_text())
    allowed = re.compile(r"</?h[123][ >]|16x16 32x32 48x48|utf-8|initial-scale=1|sha256|^,?\.\d+f$")
    found = []
    for fn in (n for n in tree.body if isinstance(n, ast.FunctionDef)):
        body = fn.body[1:] if ast.get_docstring(fn) else fn.body
        for node in (x for stmt in body for x in ast.walk(stmt)):
            # a bare identifier is a field name the module reads, never page text
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and not re.fullmatch(r"[a-z][a-z0-9_]*", node.value):
                rest = allowed.sub("", node.value)
                if re.search(r"\d", rest):
                    found.append((fn.name, node.value))
    assert found == []


def test_the_evening_writes_the_page_after_the_handoff_and_removes_one_it_cannot_write(tmp_path, monkeypatch):
    body = (ROOT / "src" / "pipeline.py").read_text()
    assert body.index("    publish_orders(docs)\n") < body.index("    publish_strategy(docs)\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "data.json").write_bytes(RAW)
    pipeline.publish_strategy(docs)
    assert (docs / sp.FILE).read_text() == sp.build(RAW) and sp.check(docs) == []

    def boom(raw):
        raise ValueError("unreadable")

    monkeypatch.setattr(sp, "build", boom)
    pipeline.publish_strategy(docs)
    assert not (docs / sp.FILE).exists()
    assert list(docs.iterdir()) == [docs / "data.json"]


def test_a_stale_or_missing_page_is_named(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "data.json").write_bytes(RAW)
    assert sp.check(docs) == [f"{sp.FILE} is missing"]
    (docs / sp.FILE).write_text("<html></html>")
    assert sp.check(docs) == [f"{sp.FILE} is not what the code and the committed record write"]
    from tools import build_strategy_page as tool
    assert tool.main(["--docs", str(docs), "--check"]) == 1
    assert tool.main(["--docs", str(docs)]) == 0 and tool.main(["--docs", str(docs), "--check"]) == 0


def test_the_gate_serves_the_page_and_refuses_a_link(tmp_path):
    from tools import publish_dashboard as gate
    root = tmp_path
    (root / "docs").mkdir()
    assert gate.strategy_files(root) == ()
    (root / "docs" / sp.FILE).write_text("x")
    assert gate.strategy_files(root) == (sp.FILE,)
    (root / "docs" / sp.FILE).unlink()
    (root / "docs" / sp.FILE).symlink_to(root / "elsewhere.html")
    with pytest.raises(RuntimeError, match="symlink"):
        gate.strategy_files(root)


def test_ci_checks_the_page():
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text()
    assert "          python tools/build_strategy_page.py --check\n" in workflow


@pytest.mark.parametrize("field, threshold, at, fired", [
    ("down4", "down4_alarm", 0, "fired"),            # at or over the alarm fires
    ("down4", "down4_alarm", -1, "clear"),
    ("ratio_10d", "ratio_10d_red", 0, "clear"),      # under the ratio fires, at it does not
    ("ratio_10d", "ratio_10d_red", -0.01, "fired"),
    ("up50_month", "up50_month_hot", 0, "clear"),    # over the hot mark fires, at it does not
    ("up50_month", "up50_month_hot", 1, "fired"),
])
def test_each_rule_reads_fired_or_clear_at_its_own_boundary(field, threshold, at, fired):
    data = json.loads(RAW)
    regime = data["breadth"]["regime"]
    regime["thresholds"]["down4_alarm"] = 400.0
    regime["thresholds"]["up50_month_hot"] = 20.0
    regime["thresholds"]["ratio_10d_red"] = 1.0
    regime["thresholds"]["ratio_10d_yellow"] = 0.5
    regime["inputs"].update({"down4": 10, "up4": 50, "ratio_10d": 3.0, "ratio_5d": 3.0, "up50_month": 1})
    regime["inputs"][field] = regime["thresholds"][threshold] + at
    if field in ("down4", "up50_month"):
        regime["inputs"][field] = int(regime["inputs"][field])
    page = sp.build(json.dumps(data).encode())
    rows = re.findall(r"<tr>(.*?)</tr>", page, re.S)
    words = {"down4": "today at or over", "ratio_10d": "-session up/down ratio under", "up50_month": "in a month over"}
    row = next(text_of(r) for r in rows if words[field] in text_of(r))
    assert row.rstrip().endswith(fired), row
