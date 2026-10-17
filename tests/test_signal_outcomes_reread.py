"""The 17 October confirmatory re-read, held to its evidence.

The study code is frozen (``tools/signal_outcomes.py`` as PR #100 merged it),
so a re-read is three files and a report: the spec, the frozen file with
publications appended and nothing else; the retained byte-level diff against
the frozen file; the study's own output; and a dated report whose every number
must be the output's. Each number the report quotes is read again here off the
rows, and anchored to the phrase it is printed in, so a number moved anywhere in
the prose cannot pass on a match elsewhere.
"""
from __future__ import annotations

from collections import Counter
import difflib
import gzip
import hashlib
import json
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parent.parent
TRUTH = ROOT / "docs" / "input-truthfulness"
FROZEN = TRUTH / "2026-10-02-signal-outcomes-spec.json"
PREVIOUS = TRUTH / "2026-10-06-signal-outcomes-spec-extended.json"
SPEC = TRUTH / "2026-10-17-signal-outcomes-spec-extended.json"
EVIDENCE = TRUTH / "2026-10-17-signal-outcomes-confirmatory-evidence"
PREVIOUS_STUDY = TRUTH / "2026-10-06-signal-outcomes-confirmatory-evidence" / "signal-outcomes.json.gz"
REPORT = TRUTH / "2026-10-17-signal-outcomes-confirmatory.md"
#: the twelve publications this re-read appends, in the order they landed
APPENDED = (("b0c6b60e", "2026-10-06"), ("a8f9a36f", "2026-10-07"), ("1e1ffe9c", "2026-10-08"),
            ("e67f8cba", "2026-10-08"), ("62bce72d", "2026-10-09"), ("dcb12a0b", "2026-10-09"),
            ("43dcb8d7", "2026-10-09"), ("9936e971", "2026-10-12"), ("8772006f", "2026-10-13"),
            ("16032f05", "2026-10-14"), ("0f951414", "2026-10-15"), ("7a1a9e49", "2026-10-16"))
UNCOMPRESSED_SHA = "95ab5a36441145f742f67f376f5a447f8c38f6d480b8b669042587abb9ce2818"
STUDY_BLOB = "39d4f25ac8ffc128fe49ead8cc3d8a025e8f11a0"


def load(path: Path) -> dict:
    return json.loads(gzip.decompress(path.read_bytes()))


def study() -> dict:
    return load(EVIDENCE / "signal-outcomes.json.gz")


def report() -> str:
    # the prose is reflowed freely; a number is read in its phrase, whitespace collapsed
    return re.sub(r"\s+", " ", REPORT.read_text(encoding="utf-8"))


def normal_diff(a: list[str], b: list[str]) -> str:
    """`diff`'s normal format, which the retained file is: hunks of `NcM`,
    `NaM` or `NdM` lines, `<` the old lines and `>` the new ones."""
    def span(i, j):
        return f"{i + 1}" if j - i == 1 else f"{i + 1},{j}"
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        code = {"replace": "c", "delete": "d", "insert": "a"}[tag]
        left = span(i1, i2) if tag != "insert" else f"{i1}"
        right = span(j1, j2) if tag != "delete" else f"{j1}"
        out.append(f"{left}{code}{right}\n")
        out += [f"< {line}" for line in a[i1:i2]]
        if tag == "replace":
            out.append("---\n")
        out += [f"> {line}" for line in b[j1:j2]]
    return "".join(out)


def settled(rows: list[dict]) -> tuple:
    r = [x["r"] for x in rows if x["bucket"] == "settled"]
    return (len(r), sum(v > 0 for v in r), sum(v < 0 for v in r), sum(v == 0 for v in r),
            round(sum(r), 2), round(sum(r) / len(r), 3) if r else None, round(statistics.median(r), 2) if r else None)


WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve")


def signed(v: float, places: int) -> str:
    return ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v):.{places}f}"


def test_the_spec_is_the_frozen_file_with_publications_appended():
    frozen, previous, spec = (json.loads(p.read_bytes()) for p in (FROZEN, PREVIOUS, SPEC))
    assert {k: v for k, v in spec.items() if k != "publications"} == {k: v for k, v in frozen.items() if k != "publications"}
    assert spec["publications"][:len(frozen["publications"])] == frozen["publications"]
    assert spec["publications"][:len(previous["publications"])] == previous["publications"]
    appended = spec["publications"][len(previous["publications"]):]
    assert [(p["commit"][:8], p["session"]) for p in appended] == list(APPENDED)
    # the retained diff is the diff, and it adds the comma that joins the lists and nothing else
    retained = (EVIDENCE / "spec-diff.txt").read_text(encoding="utf-8")
    assert retained == normal_diff(FROZEN.read_text(encoding="utf-8").splitlines(keepends=True),
                                   SPEC.read_text(encoding="utf-8").splitlines(keepends=True))
    removed = [line[2:] for line in retained.splitlines() if line.startswith("< ")]
    added = [line[2:] for line in retained.splitlines() if line.startswith("> ")]
    assert len(removed) == 1 and added[0] == removed[0] + ","
    assert len(added) == 1 + len(spec["publications"]) - len(frozen["publications"])


def test_the_output_is_the_spec_s_and_the_record_names_its_run():
    doc = study()
    assert doc["spec_sha256"] == hashlib.sha256(SPEC.read_bytes()).hexdigest()
    assert hashlib.sha256(gzip.decompress((EVIDENCE / "signal-outcomes.json.gz").read_bytes())).hexdigest() == UNCOMPRESSED_SHA
    assert doc["version"] == "signal-outcomes-v1" and doc["frozen_through_session"] == "2026-10-01"
    assert doc["newest_session"] == "2026-10-16"
    spec = json.loads(SPEC.read_bytes())
    assert [p["commit"] for p in doc["publications"]] == [p["commit"] for p in spec["publications"]]
    record = (EVIDENCE / "run-record.txt").read_text(encoding="utf-8")
    assert f"tools/signal_outcomes.py blob {STUDY_BLOB}" in record
    assert "--spec docs/input-truthfulness/2026-10-17-signal-outcomes-spec-extended.json" in record
    assert re.search(r"^exit code: 0$", record, re.M)
    summary = (EVIDENCE / "summary.txt").read_text(encoding="utf-8")
    assert f"spec {doc['spec_sha256'][:12]};" in summary and "newest session 2026-10-16" in summary
    text = report()
    assert f"(uncompressed SHA-256 `{UNCOMPRESSED_SHA[:12]}…`)" in text
    assert f"(SHA-256 `{doc['spec_sha256'][:12]}…`)" in text and f"(blob `{STUDY_BLOB[:8]}…`" in text


def test_the_comparison_table_is_both_runs_own():
    new, old = study(), load(PREVIOUS_STUDY)
    text = report()
    for doc, col in ((old, 0), (new, 1)):
        pubs = doc["publications"]
        assert [len(pubs), sum(p["first"] for p in pubs)] == [int(x) for x in
            re.search(r"\| Publications / first-of-session \| (\d+) / (\d+) \| (\d+) / (\d+) \|", text).groups()[2 * col:2 * col + 2]]
        cells = re.search(r"\| Rows \| ([\d,]+) \| ([\d,]+) \|", text).groups()
        assert int(cells[col].replace(",", "")) == len(doc["rows"])
        bars = re.search(r"\| Bars / symbols \| ([\d,]+) / ([\d,]+) \| ([\d,]+) / ([\d,]+) \|", text).groups()
        assert (int(bars[2 * col].replace(",", "")), int(bars[2 * col + 1].replace(",", ""))) == (doc["bars"]["observations"], doc["bars"]["symbols"])
        ex = [r for r in doc["rows"] if r["stratum"] == "admitted" and r["phase"] == "exploratory"]
        n, w, l, e, total, mean, median = settled(ex)
        assert re.search(r"\| Exploratory admitted: settled \| (\d+) \| (\d+) \|", text).group(col + 1) == str(n)
        assert re.search(r"\| Exploratory admitted: wins / losses / even \| (\d+ / \d+ / \d+) \| (\d+ / \d+ / \d+) \|", text).group(col + 1) == f"{w} / {l} / {e}"
        assert re.search(r"\| Exploratory admitted: mean R, median R \| ([^|]+) \| ([^|]+) \|", text).group(col + 1).strip() == \
            f"{signed(mean, 3)}, {signed(median, 2)}"
        boot = doc["summary"]["phases"]["exploratory"]["night_bootstrap"]
        ci = boot["ci95"]
        assert re.search(r"\| Exploratory admitted: mean of night means, 95% CI \| ([^|]+) \| ([^|]+) \|", text).group(col + 1).strip() == \
            f"{signed(boot['mean_of_night_means'], 3)} [{signed(ci[0], 3)}, {signed(ci[1], 3)}]"
        co = [r for r in doc["rows"] if r["stratum"] == "admitted" and r["phase"] == "confirmatory"]
        assert re.search(r"\| Confirmatory admitted: rows / settled \| (\d+ / \d+) \| (\d+ / \d+) \|", text).group(col + 1) == f"{len(co)} / {settled(co)[0]}"


def test_what_settled_since_6_october_is_the_rows_own():
    new, old = study(), load(PREVIOUS_STUDY)
    key = lambda r: (r["session"], r["ticker"], r["publication"])
    before = {key(r): r for r in old["rows"]}
    assert all(key(r) in {key(x) for x in new["rows"]} for r in old["rows"])
    # no settled ticket changed its R, in any stratum
    assert all(r["bucket"] == "settled" and r["r"] == before[key(r)]["r"] for r in new["rows"]
               if key(r) in before and before[key(r)]["bucket"] == "settled")
    late = [r for r in new["rows"] if r["stratum"] == "admitted" and r["phase"] == "exploratory" and r["bucket"] == "settled"
            and before[key(r)]["bucket"] != "settled"]
    by = Counter(r["session"] for r in late)
    n, w, l, _, total, _, _ = settled(late)
    text = report()
    assert f"{n} of its tickets that were open on 6 October have settled since -- {by['2026-10-01']} of 1 October, " \
           f"{by['2026-09-29']} of 29 September and {by['2026-09-30']} of 30 September -- at {w} wins and {l} losses, {signed(total, 2)}R" in text
    assert len(by) == 3
    for doc, phrase in ((old, "read {mean}R over {n} settled with no win on 6 October"), (new, "reads {mean}R over {n} settled with {w} wins now")):
        n1, w1, _, _, _, mean1, _ = settled([r for r in doc["rows"] if r["session"] == "2026-10-01" and r["stratum"] == "admitted"])
        assert phrase.format(mean=signed(mean1, 3), n=n1, w=w1) in text
    assert settled([r for r in old["rows"] if r["session"] == "2026-10-01" and r["stratum"] == "admitted"])[1] == 0


def test_the_confirmatory_figure_and_its_night_table_are_the_rows_own():
    doc, text = study(), report()
    co = [r for r in doc["rows"] if r["stratum"] == "admitted" and r["phase"] == "confirmatory"]
    n, w, l, e, total, mean, median = settled(co)
    block = doc["summary"]["phases"]["confirmatory"]
    assert (block["settled"]["n"], block["settled"]["mean_r"], block["settled"]["median_r"]) == (n, mean, median)
    nights = sorted({r["session"] for r in co if r["bucket"] == "settled"})
    boot = block["night_bootstrap"]
    assert boot["nights"] == len(nights)
    assert f"**Admitted, confirmatory: {n} settled** over {WORDS[len(nights)]} nights ({int(nights[0][-2:])} to {int(nights[-1][-2:])} October)" in text
    assert f"{w} wins, {l} losses and {e} even, sum {signed(total, 2)}R, mean {signed(mean, 3)}R, median {signed(median, 2)}R" in text
    assert f"the mean of the {WORDS[len(nights)]} night means is {signed(boot['mean_of_night_means'], 3)}R with a 95% night-bootstrap " \
           f"interval of **[{signed(boot['ci95'][0], 3)}, {signed(boot['ci95'][1], 3)}]**" in text
    assert boot["ci95"][0] < 0 < boot["ci95"][1] and "The interval includes zero" in text
    ub = block["uncertain_bound"]
    assert f"{ub['uncertain']} uncertain tickets, {ub['bounded']} of them bounded, whose pooled mean would be {signed(ub['pooled_mean_r_with_bound'], 3)}R" in text
    costs = block["costs_per_side_bps"]
    assert f"{signed(costs['5']['mean_r'], 3)}R at 5 basis points a side and {signed(costs['20']['mean_r'], 3)}R at 20" in text
    # the night table, row by row
    sessions = sorted({r["session"] for r in co})
    moving = 0
    for s in sessions:
        rows = [r for r in co if r["session"] == s]
        regime = {r["night_regime"] for r in rows}
        assert len(regime) == 1
        k, w1, l1, e1, t1, m1, _ = settled(rows)
        still = sum(r["bucket"] in ("open", "pending") for r in rows)
        moving += still
        day = int(s[-2:])
        cells = (f"| {day} Oct | {regime.pop()} | {len(rows)} | {k} | " +
                 (f"{w1} / {l1} / {e1} | {signed(t1, 2)} | {signed(m1, 3)} |" if k else "— | — | — |") + f" {still} |")
        assert cells in text, cells
    assert moving == block["buckets"]["open"] + block["buckets"]["pending"]
    inside = sum(still for s in sessions if s >= "2026-10-13"
                 for still in [sum(r["bucket"] in ("open", "pending") for r in co if r["session"] == s)])
    assert f"carry {inside} of the stratum's {moving} rows still open or pending" in text
    under = sum(1 for s in sessions if settled([r for r in co if r["session"] == s])[0] < 20)
    assert f"{WORDS[under].capitalize()} of the {WORDS[len(sessions)]} nights hold fewer than twenty" in text


def test_the_yellow_nights_and_the_account_change_are_the_rows_own():
    doc, text = study(), report()
    co = [r for r in doc["rows"] if r["stratum"] == "admitted" and r["phase"] == "confirmatory"]
    yellow = [r for r in co if r["night_regime"] == "yellow"]
    red = [r for r in co if r["night_regime"] == "red"]
    ys = sorted({r["session"] for r in yellow})
    assert ys == ["2026-10-08", "2026-10-09", "2026-10-12"]
    assert "**Three of the eleven confirmatory nights were YELLOW** -- 8, 9 and 12 October" in text
    yn, *_ , ytotal, _, _ = settled(yellow)
    rn, *_ , rtotal, rmean, _ = settled(red)
    aplus = [r for r in yellow if r["grade_mechanical"] == "A+"]
    an, *_ , atotal, _, _ = settled(aplus)
    assert f"Of the {yn} admitted tickets settled on those three nights, {an} are A+ (both 8 October, {signed(atotal, 2)}R between them); the other {yn - an} are grade A" in text
    assert {r["session"] for r in aplus if r["bucket"] == "settled"} == {"2026-10-08"}
    assert f"The YELLOW nights' {yn} settled sum to {signed(ytotal, 2)}R; the eight RED nights' {rn} to {signed(rtotal, 2)}R (mean {signed(rmean, 3)}R)" in text
    assert len({r["session"] for r in red}) == 8
    # the rows without an order, admitted and every stratum, before and from the first $2,000 night
    def no_order(rows):
        return Counter(r["session"] for r in rows if r["bucket"] == "no_ticket" and r.get("reason") == "no_order")
    sessions = sorted({r["session"] for r in doc["rows"]})
    adm = no_order([r for r in doc["rows"] if r["stratum"] == "admitted"])
    every = no_order(doc["rows"])
    before = [s for s in sessions if s < "2026-10-09"]
    after = [s for s in sessions if s >= "2026-10-09"]
    assert f"rose from {min(adm[s] for s in before)} to {max(adm[s] for s in before)} a night through 8 October to " \
           f"{', '.join(str(adm[s]) for s in after[:-1])} and {adm[after[-1]]} on 9 to 16 October ({sum(adm[s] for s in after)} in all)" in text
    assert f"from {min(every[s] for s in before)} to {max(every[s] for s in before)} a night across every stratum to " \
           f"{min(every[s] for s in after)} to {max(every[s] for s in after)}" in text


def test_the_reader_s_own_admissions_are_the_rows_own():
    doc, text = study(), report()
    rows = [r for r in doc["rows"] if r["reader_accepted"] and r["final_grade"] in ("A+", "A")]
    assert [(r["ticker"], r["session"], r["bucket"]) for r in rows] == [("DAC", "2026-10-01", "uncertain"), ("DAC", "2026-10-02", "settled")]
    assert rows[0]["uncertainty"] == "trigger_timing"
    assert f"settled at {signed(rows[1]['r'], 2)}R" in text and "(`trigger_timing`)" in text
