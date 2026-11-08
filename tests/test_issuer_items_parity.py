"""The Morning desk reads a listed filing's SEC item string as the evening's
earnings block does. The corpus under tests/fixtures/issuer-evidence/ carries
`earnings_risk._parse_items`'s own answer for every case; this test holds the
file to its generator and to the module, and the browser suite holds the page's
`parseItems` to the same file."""
import importlib.util
import json
from pathlib import Path

from src import earnings_risk

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "tests" / "fixtures" / "issuer-evidence"
CORPUS = json.loads((DIR / "items-parity.json").read_text())


def _generator():
    spec = importlib.util.spec_from_file_location("items_parity", DIR / "items_parity.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_corpus_is_its_generator_s_output():
    assert (DIR / "items-parity.json").read_text() == _generator().render()


def test_every_case_carries_the_evening_s_own_reading():
    for case in CORPUS["cases"]:
        codes, unread = earnings_risk._parse_items(case["items"])
        assert (case["codes"], case["unread"]) == (codes, unread), repr(case["items"])


def test_the_corpus_reaches_every_character_either_side_might_strip():
    strings = [case["items"] for case in CORPUS["cases"]]
    python_strip = {c for c in range(0x10000) if chr(c).isspace()}
    javascript_trim = {0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0xA0, 0x1680, *range(0x2000, 0x200B),
                       0x2028, 0x2029, 0x202F, 0x205F, 0x3000, 0xFEFF}
    for c in sorted(python_strip | javascript_trim | {0x200B, 0x180E}):
        assert chr(c) + "1.01" in strings and "1.01" + chr(c) in strings, hex(c)
    # A character each side reads differently must sit in a case whose answers
    # differ, or a parser using the wrong set would agree with every case.
    assert any(earnings_risk._parse_items(s) != (["1.01"], 0) for s in ("﻿1.01",))
    assert earnings_risk._parse_items("\x851.01") == (["1.01"], 0)


def test_the_corpus_reaches_the_other_separators_and_shapes():
    strings = {case["items"] for case in CORPUS["cases"]}
    for shape in ("1.01;2.02", "1.01|2.02", "1.01 2.02", "1.010", "01.01", "9.01,1.01", "1.0１", "\ud800",
                  "1.01,1.01 ,　1.01", ""):
        assert shape in strings, repr(shape)
    assert any(len(s) == 256 for s in strings) and any(len(s) == 1024 for s in strings)
    answers = {(tuple(c["codes"]), c["unread"]) for c in CORPUS["cases"]}
    assert len(answers) >= 10
