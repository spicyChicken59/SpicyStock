"""The item strings the Morning desk's parser must read as the evening reads
them, each with `earnings_risk._parse_items`'s own answer. The browser suite
(`tools/issuer_evidence_cases.mjs`) runs the page's `parseItems` over every case
and `tests/test_issuer_items_parity.py` holds this file to the generator and to
the module. Usage: python items_parity.py [--check]"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src import earnings_risk  # noqa: E402

OUT = Path(__file__).resolve().parent / "items-parity.json"
# Every code point one side strips and the other might not: what str.strip()
# removes, what JavaScript's trim() removes (the same, plus U+FEFF), and the
# zero-width and control characters neither removes.
PYTHON_SPACE = [c for c in range(0x10000) if chr(c).isspace()]
JS_TRIM_ONLY = [0xFEFF]
NEITHER = [0x00, 0x08, 0x7F, 0x180E, 0x200B, 0x200C, 0x200D, 0x2060, 0xFFFE]
SHAPES = ["", ",", ",,", " , ", "1.01", "1.01,", ",1.01", "1.01,1.01", "1.01, 1.01", "1.01,\t1.01",
          "9.01,1.01", "2.02,9.01,1.01,5.01", "1.010", "01.01", "1.1", "11.01", "1.01.", "1,01", "1.01;2.02",
          "1.01|2.02", "1.01 2.02", "1.01\n2.02", "abc", "2.020,abc", "1.0１", "１.01", "١.٠١",
          "¹.01", "1․0.1", "1.01\ud800", "\ud800", "9.99", "0.00", "1.01,1.01 ,　1.01"]


def cases():
    out = [s for s in SHAPES]
    for c in PYTHON_SPACE + JS_TRIM_ONLY + NEITHER:
        ch = chr(c)
        out += [ch + "1.01", "1.01" + ch, ch, "1.01" + ch + ",2.02", ch + ch + "3.01" + ch]
    long = ",".join(["2.02", "9.01", "1.01"] * 21)
    out += [long[:256], (long * 5)[:1024]]
    seen, unique = set(), []
    for s in out:
        if s not in seen:
            seen.add(s); unique.append(s)
    return [{"items": s, "codes": earnings_risk._parse_items(s)[0], "unread": earnings_risk._parse_items(s)[1]} for s in unique]


def render():
    return json.dumps({"generator": "tests/fixtures/issuer-evidence/items_parity.py", "cases": cases()},
                      indent=1, ensure_ascii=True) + "\n"


if __name__ == "__main__":
    text = render()
    if "--check" in sys.argv[1:]:
        current = OUT.read_text() if OUT.exists() else None
        print("items parity corpus " + ("current" if current == text else "STALE"))
        sys.exit(0 if current == text else 1)
    OUT.write_text(text)
    print(f"wrote {len(json.loads(text)['cases'])} cases")
