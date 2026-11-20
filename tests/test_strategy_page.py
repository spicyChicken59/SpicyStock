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


@pytest.mark.parametrize("family, key, value, words", [
    ("plan", "max_stop_pct", 5.0, "within 5% of the limit"),
    ("plan", "trigger_cents", 0.03, "the larger of $0.03"),
    ("plan", "ideal_stop_pct", 2.5, "for a stop wider than 2.5% of the limit"),
    ("plan", "gain_ceiling_pct", 16.0, "a burst day up 16% or more"),
    ("plan", "entry_window_minutes", 25, "the first 25 minutes of the session"),
    ("plan", "entry_below_pct", 3.0, "an open more than 3% under the burst close"),
    ("dollar", "min_move", 1.25, "at least $1.25 over the session's own open"),
    ("burst", "min_volume", 250_000, "at least 250,000 shares"),
    ("quality", "min_a_plus_letters", 5, "A+ also needs 5 checks"),
    ("quality", "veto_up_days", 4, "at 4 or more rising closes in a row"),
    ("quality", "min_r2", 0.6, "its R² under 0.6"),
    ("breadth", "reference_universe", 7000, "reference universe of 7,000 names"),
    ("pipeline", "yellow_grades", ["A+", "A"], "yellow 0.5 A+, A"),
])
def test_a_rule_the_record_archived_moves_the_page(family, key, value, words):
    data = json.loads(RAW)
    before = text_of(sp.build(RAW))
    assert words not in before
    data["rules"][family][key] = value
    page = text_of(sp.build(json.dumps(data).encode()))
    assert words in page
    # the record's value is what prints, and the code's own constant is named beside it as moved
    assert f"{family}.{key} (record " in page


@pytest.mark.parametrize("module, name, value, family, key, words", [
    (plan, "MAX_STOP_PCT", 5.0, "plan", "max_stop_pct", "within 5% of the limit"),
    (quality, "MIN_ER", 0.5, "quality", "min_er", "efficiency ratio is under 0.5"),
])
def test_a_rule_the_record_does_not_archive_is_the_codes_and_named(monkeypatch, module, name, value, family, key, words):
    data = json.loads(RAW)
    del data["rules"][family][key]
    monkeypatch.setattr(module, name, value)
    page = text_of(sp.build(json.dumps(data).encode()))
    assert words in page
    assert "Read from the code because this record archives no such rule:" in page and f"{family}.{key}" in page


def test_a_code_constant_that_moved_since_the_record_is_named_and_never_printed_as_the_records(monkeypatch):
    monkeypatch.setattr(plan, "MAX_STOP_PCT", 5.0)
    page = text_of(sp.build(RAW))
    archived = json.loads(RAW)["rules"]["plan"]["max_stop_pct"]
    assert f"within {archived:g}% of the limit" in page and "within 5% of the limit" not in page
    assert f"plan.max_stop_pct (record {archived}, code 5.0)" in page and "The code has moved since this record." in page


def test_the_buy_stop_rule_is_the_one_the_record_was_made_under():
    data = json.loads(RAW)
    data["rules"]["plan"].pop("burst_trigger_rule", None)
    legacy = text_of(sp.build(json.dumps(data).encode()))
    assert "Buy stop ( close , the rule this record was made under): the burst close itself." in legacy
    assert f"plan.burst_trigger_rule (record close, code {plan.BURST_TRIGGER_RULE})" in legacy
    data["rules"]["plan"]["burst_trigger_rule"] = "close_plus_cushion"
    current = text_of(sp.build(json.dumps(data).encode()))
    assert "( close_plus_cushion , the rule this record was made under): the burst close plus the larger of" in current
    assert "plan.burst_trigger_rule (record" not in current


def test_tonights_thresholds_and_values_are_the_records():
    data = json.loads(RAW)
    data["rules"]["plan"]["entry_above_pct"] = 6.0
    assert "the close plus 6% (the outer extension line)" in text_of(sp.build(json.dumps(data).encode()))
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


def _numbers_typed(source: str) -> list:
    """Every digit the module's own text could print: a string constant with a
    digit outside its HTML scaffolding, anywhere but a docstring, and every
    int or float literal that is not an index, the unit ``PERCENT`` or the
    module's ``VERSION``."""
    tree = ast.parse(source)
    allowed = re.compile(r"</?h[123][ >]|16x16 32x32 48x48|utf-8|initial-scale=1|sha256|\[0-9a-f\]\{64\}|^,?\.\d+f$")
    docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                  if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and ast.get_docstring(node)}
    indexes = {id(node.slice) for node in ast.walk(tree) if isinstance(node, ast.Subscript)}
    indexes |= {id(node.slice.operand) for node in ast.walk(tree)
                if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.UnaryOp)}
    declared = {id(node.value) for node in tree.body if isinstance(node, ast.Assign)
                and [getattr(t, "id", None) for t in node.targets] in (["PERCENT"], ["VERSION"])}
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or id(node) in docstrings:
            continue
        if isinstance(node.value, str):
            if not re.fullmatch(r"[a-z][a-z0-9_]*", node.value) and re.search(r"\d", allowed.sub("", node.value)):
                found.append(node.value)
        elif isinstance(node.value, (int, float)) and not isinstance(node.value, bool) \
                and id(node) not in indexes | declared:
            found.append(node.value)
    return found


def test_the_module_types_no_number_of_its_own():
    """Every digit the page prints comes from a rule the record archived, a
    constant or the record: the module's own text carries none outside its
    HTML scaffolding, and no number literal but an index and its unit."""
    assert _numbers_typed((ROOT / "src" / "strategy_page.py").read_text()) == []


@pytest.mark.parametrize("snippet", [
    'CAVEAT = "Never risk more than 3% of one name."\n',
    "def f(x):\n    return x.get('slots', 4)\n",
    "def f(x):\n    return x * 2.5\n",
])
def test_the_guard_refuses_a_typed_number_anywhere(snippet):
    assert _numbers_typed(snippet) != []


def test_a_record_without_an_account_prints_no_typed_figure():
    data = json.loads(RAW)
    del data["account"]
    page = text_of(sp.build(json.dumps(data).encode()))
    assert "risking an unrecorded percentage of the unrecorded model account" in page
    assert "an unrecorded number of model slots" in page and not re.search(r"\$0(?![.\d])", page)
    assert "None" not in page


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


def test_the_gate_serves_the_page_bound_to_the_committed_record_and_refuses_a_link(tmp_path):
    from tools import publish_dashboard as gate
    root = tmp_path
    docs = root / "docs"
    docs.mkdir()
    (docs / "data.json").write_bytes(RAW)
    assert gate.strategy_files(root) == ()
    (docs / sp.FILE).write_text(sp.build(RAW))
    assert gate.strategy_files(root) == (sp.FILE,)
    other = json.loads(RAW)
    other["run"]["session"] = "2000-01-03"
    (docs / sp.FILE).write_text(sp.build(json.dumps(other).encode()))     # another record's page
    with pytest.raises(RuntimeError, match="not bound to the committed data.json"):
        gate.strategy_files(root)
    (docs / sp.FILE).write_text("x")
    with pytest.raises(RuntimeError, match="not bound"):
        gate.strategy_files(root)
    (docs / sp.FILE).unlink()
    (docs / sp.FILE).mkdir()
    with pytest.raises(RuntimeError, match="not a file"):
        gate.strategy_files(root)
    (docs / sp.FILE).rmdir()
    (docs / sp.FILE).symlink_to(root / "elsewhere.html")
    with pytest.raises(RuntimeError, match="symlink"):
        gate.strategy_files(root)
    assert sp.record_digest(sp.build(RAW)) == __import__("hashlib").sha256(RAW).hexdigest()


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


@pytest.mark.parametrize("ratio_5d, down4, up4, fired", [
    (0.4, 60, 50, "fired"),        # under its line with more down than up
    (0.4, 50, 50, "clear"),        # under its line, down not more than up
    (0.5, 60, 50, "clear"),        # at its line
])
def test_the_five_session_rule_needs_both_halves(ratio_5d, down4, up4, fired):
    data = json.loads(RAW)
    regime = data["breadth"]["regime"]
    regime["thresholds"].update(ratio_5d_red=0.5, down4_alarm=400.0)
    regime["inputs"].update(ratio_5d=ratio_5d, down4=down4, up4=up4)
    rows = [text_of(r) for r in re.findall(r"<tr>(.*?)</tr>", sp.build(json.dumps(data).encode()), re.S)]
    row = next(r for r in rows if "while today's down count exceeds" in r)
    assert row.rstrip().endswith(fired), row


@pytest.mark.parametrize("ratio_10d, fired", [(1.99, "fired"), (2.0, "clear")])
def test_the_yellow_ratio_fires_under_its_line_and_not_at_it(ratio_10d, fired):
    data = json.loads(RAW)
    regime = data["breadth"]["regime"]
    regime["thresholds"].update(ratio_10d_yellow=2.0, ratio_10d_red=1.0)
    regime["inputs"]["ratio_10d"] = ratio_10d
    rows = [text_of(r) for r in re.findall(r"<tr>(.*?)</tr>", sp.build(json.dumps(data).encode()), re.S)]
    yellow = next(r for r in rows if r.startswith(" yellow") and "-session ratio under 2" in r)
    assert yellow.rstrip().endswith(fired), yellow


def test_each_printed_rule_is_its_constant_or_the_records():
    data = json.loads(RAW)
    data["account"]["max_open_positions"] = 7
    data["account"]["max_position_pct"] = 30
    page = text_of(sp.build(json.dumps(data).encode()))
    assert "red 0 none" in page                                             # red admits nothing
    assert "capped at 30% of the account, 7 model slots" in page            # the slots are max_open_positions
    assert f"{' and '.join(quality.GRADE_GATE_LETTERS)} passed outright" in page
    assert len(quality.GRADE_GATE_LETTERS) > 1
    stages = data["funnel"]["reaction"]["stages"]
    for key, n in stages.items():
        line = f"{data['funnel']['labels'][key]} {n:,}"
        assert (line in page) is bool(n), key                               # every nonzero stage, no zero one
    assert f"its R² under {data['rules']['quality']['min_r2']:g}" in page


def test_an_edge_record_prints_no_python_word_and_says_what_it_lacks():
    raw = (ROOT / "tests" / "fixtures" / "page" / "empty.json").read_bytes()
    page = text_of(sp.build(raw))
    assert "None" not in page and "nan" not in page.lower().split()
    data = json.loads(RAW)
    data["breadth"]["regime"]["inputs"].update(ratio_10d=None, ratio_5d=None, down4=None)
    page = text_of(sp.build(json.dumps(data).encode()))
    assert "None" not in page and "undefined" in page and "not read" in page
    assert "(no candidate tonight recorded its words)" in text_of(sp.build(raw)) or json.loads(raw).get("bursts")


def test_check_names_a_record_it_cannot_build_from_and_never_raises(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / sp.FILE).write_text("x")
    assert sp.check(docs)[0].startswith(f"{sp.FILE} cannot be built from data.json: FileNotFoundError")
    (docs / "data.json").write_text("[1]")
    assert sp.check(docs) == [f"{sp.FILE} cannot be built from data.json: ValueError: the record is not a JSON object"]
    from tools import build_strategy_page as tool
    assert tool.main(["--docs", str(docs), "--check"]) == 1


def _walk(bars, entry=100.0, stop=96.0, shares=10):
    days = [f"2026-11-{2 + i:02d}" for i in range(len(bars))]
    pick = {"ticker": "X", "kind": "burst", "entry_ref": entry, "stop": stop, "shares": shares}
    return plan.follow(pick, [{"date": d, "o": o, "h": h, "l": l, "c": c} for d, (o, h, l, c) in zip(days, bars)])


def test_the_walk_the_page_states_is_the_models_own_order():
    keys = [k for k, _ in sp.WALK]
    assert set(keys) - {"stop_at_open", "stop_intraday"} <= {r["key"] for r in plan.EXIT_RULES}
    assert keys.index("stop_intraday") < keys.index("sell_half_8pct")          # the stop wins on one bar
    out = _walk([(101, 109, 95, 100)])
    assert out["status"] == "stopped" and not any(e["event"] == "sell_half" for e in out["events"])
    assert keys.index("day3_no_progress") < keys.index("day3_sell_half")       # no progress closes it all
    out = _walk([(101, 102, 99.5, 101), (101, 102, 99.6, 100.5), (100, 101, 99.7, 99.8)])
    assert out["status"] == "exit" and [e["event"] for e in out["events"] if e.get("shares")] == ["no_progress"]
    assert keys.index("gap_20pct") < keys.index("stop_intraday")               # a gap exit at the open
    out = _walk([(121, 122, 90, 95)])
    assert out["status"] == "exit" and out["events"][-1]["price"] == 121
    # an abnormal close sells nothing: after the half is sold, a day closing past the level only raises the stop
    out = _walk([(101, 109, 99.5, 105), (109.5, 112, 109, 111)])
    second = [e for e in out["events"] if e["day"] == 2]
    assert any(e["event"] == "abnormal_day" for e in second) and not any(e.get("shares") for e in second)


def test_every_exit_row_reads_as_a_sentence_and_the_levels_are_from_the_fill():
    page = text_of(sp.build(RAW))
    assert "the protective stop at the ticket's stop price is a stop-market order" in page
    assert "(+8% from the fill)" in page.replace(f"+{plan.SELL_HALF_PCT:g}%", "+8%")
    assert "Each level is measured from the booked fill" in page


def test_the_method_view_links_the_page():
    app = (ROOT / "docs" / "app.js").read_text()
    assert "el('a', { href: 'strategy.html', 'data-strategy-page': ''" in app
