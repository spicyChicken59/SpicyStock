"""The 7 November confirmatory re-read, held to its evidence.

The study code is frozen (``tools/signal_outcomes.py`` as PR #100 merged it),
so a re-read is three files and a report: the spec, the frozen file with
publications appended and nothing else; the retained byte-level diff against
the frozen file; the study's own output; and a dated report whose every number
must be the output's. Each number the report quotes is read again here off the
rows, and anchored to the phrase it is printed in, so a number moved anywhere in
the prose cannot pass on a match elsewhere. The 24 October re-read keeps its own
guard (``tests/test_signal_outcomes_reread_24_october.py``); this one reads the
next.
"""
from __future__ import annotations

from collections import Counter
import difflib
import gzip
import hashlib
import json
from pathlib import Path
import re
from datetime import datetime
import statistics
import subprocess

import pytest

from src import pipeline, plan, record as rec
from tools import signal_outcomes as so

ROOT = Path(__file__).resolve().parent.parent
TRUTH = ROOT / "docs" / "input-truthfulness"
FROZEN = TRUTH / "2026-10-02-signal-outcomes-spec.json"
PREVIOUS = TRUTH / "2026-10-24-signal-outcomes-spec-extended.json"
SPEC = TRUTH / "2026-11-07-signal-outcomes-spec-extended.json"
EVIDENCE = TRUTH / "2026-11-07-signal-outcomes-confirmatory-evidence"
PREVIOUS_STUDY = TRUTH / "2026-10-24-signal-outcomes-confirmatory-evidence" / "signal-outcomes.json.gz"
REPORT = TRUTH / "2026-11-07-signal-outcomes-confirmatory.md"
# the ten appended, each the first publication of its session
APPENDED = (("adaf1b1a", "2026-10-26"), ("36ce7ef9", "2026-10-27"), ("dbb8358c", "2026-10-28"), ("cd6418f1", "2026-10-29"),
            ("e4063d25", "2026-10-30"), ("3cd890ec", "2026-11-02"), ("ef855d6d", "2026-11-03"), ("a0d9172e", "2026-11-04"),
            ("29d9474f", "2026-11-05"), ("f1feb636", "2026-11-06"))
UNCOMPRESSED_SHA = "eac24c37757f322d99ae02daa965c22ae181ea8896de7b199670bbef35a170e0"
STUDY_BLOB = "39d4f25ac8ffc128fe49ead8cc3d8a025e8f11a0"
PREVIOUS_READ = "2026-10-24"
NEWEST = "2026-11-06"
# the one night the report reads on its own: the first published burst tickets, and every ticket stopped
BIG_NIGHT = "2026-11-04"
NEXT_SESSION = "2026-11-05"


def load(path: Path) -> dict:
    return json.loads(gzip.decompress(path.read_bytes()))


def git_blob(data: bytes) -> str:
    """The object id git gives these bytes as a blob, computed without git."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def present(commit: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=ROOT, capture_output=True).returncode == 0


def have(commits: list[str]) -> None:
    """A shallow checkout -- CI's -- carries only its tip, so a commit named
    here is fetched by its whole id, exactly those and once; when it cannot be
    had the test fails with the reason."""
    missing = [c for c in commits if not present(c)]
    if missing:
        done = subprocess.run(["git", "fetch", "--quiet", "--no-tags", "--depth=1", "origin", *missing],
                              cwd=ROOT, capture_output=True, text=True)
        assert done.returncode == 0 and all(present(c) for c in missing), \
            f"{len(missing)} commits named here are not in this checkout and could not be fetched: {done.stderr.strip()}"


def run_record(name: str) -> dict:
    """A run record's lines, each `key: value`, every key the record must carry."""
    lines = (EVIDENCE / name).read_text(encoding="utf-8").splitlines()
    fields = dict(line.split(": ", 1) for line in lines)
    assert len(fields) == len(lines), "one key a line, none repeated"
    code = re.fullmatch(r"([0-9a-f]{40}) \(tools/signal_outcomes\.py blob ([0-9a-f]{40})\)", fields["code"])
    python = re.fullmatch(r"Python (\d+\.\d+\.\d+); pandas (\d+\.\d+\.\d+)", fields["python"])
    assert code and python, fields
    started, finished = (datetime.strptime(fields[k], "%Y-%m-%dT%H:%M:%SZ") for k in ("started", "finished"))
    wall = float(fields["wall seconds"])
    # the clock lines are truncated to the second; the wall time is measured
    assert abs((finished - started).total_seconds() - wall) < 1, fields
    return {**fields, "commit": code.group(1), "blob": code.group(2), "interpreter": python.group(1),
            "pandas": python.group(2), "wall": fields["wall seconds"], "exit": fields["exit code"]}


def study() -> dict:
    return load(EVIDENCE / "signal-outcomes.json.gz")


def report() -> str:
    # the prose is reflowed freely; a number is read in its phrase, whitespace collapsed
    return re.sub(r"\s+", " ", REPORT.read_text(encoding="utf-8"))


def normal_diff(a: list[str], b: list[str]) -> str:
    """`diff`'s normal format, which the retained file is."""
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


WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
         "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty")
TENS = {20: "twenty", 30: "thirty", 40: "forty", 50: "fifty", 60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety"}


def word(n: int) -> str:
    """A count in words, as the report spells one under a hundred."""
    if n < len(WORDS):
        return WORDS[n]
    tens, ones = divmod(n, 10)
    return TENS[tens * 10] + (f"-{WORDS[ones]}" if ones else "")


ORDINALS = ("", "first", "second", "third", "fourth")
KEY = lambda r: (r["session"], r["ticker"], r["publication"])  # noqa: E731


def day(session: str) -> int:
    return int(session[-2:])


def month(session: str) -> str:
    return datetime.strptime(session, "%Y-%m-%d").strftime("%B")


def when(session: str) -> str:
    return f"{day(session)} {month(session)}"


def listed(items: list) -> str:
    items = [str(x) for x in items]
    return ", ".join(items[:-1]) + f" and {items[-1]}" if len(items) > 1 else items[0]


def confirmatory_admitted(doc: dict) -> list[dict]:
    return [r for r in doc["rows"] if r["stratum"] == "admitted" and r["phase"] == "confirmatory"]


def by_session(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["session"], []).append(r)
    return dict(sorted(out.items()))


def withheld(r: dict) -> bool:
    return r["bucket"] == "no_ticket" and str(r.get("reason", "")).startswith("ticket withheld")


def no_order(r: dict) -> bool:
    return r["bucket"] == "no_ticket" and r.get("reason") == "no_order"


@pytest.fixture(scope="module")
def published() -> list[dict]:
    """Every record the spec names, read from git by commit and held to its
    blob by the frozen study's own reader. A shallow checkout -- CI's --
    carries only its tip, so the named commits are fetched by their whole ids,
    exactly those and once; when they cannot be had the test fails with the
    reason."""
    spec = so.load_spec(SPEC)
    have([p["commit"] for p in spec["publications"]])
    return so.load_publications(spec)


def signed(v: float, places: int) -> str:
    return ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v):.{places}f}"


def test_the_spec_is_the_frozen_file_with_publications_appended():
    frozen, previous, spec = (json.loads(p.read_bytes()) for p in (FROZEN, PREVIOUS, SPEC))
    assert {k: v for k, v in spec.items() if k != "publications"} == {k: v for k, v in frozen.items() if k != "publications"}
    assert spec["publications"][:len(frozen["publications"])] == frozen["publications"]
    assert spec["publications"][:len(previous["publications"])] == previous["publications"]
    appended = spec["publications"][len(previous["publications"]):]
    assert [(p["commit"][:8], p["session"]) for p in appended] == list(APPENDED)
    assert all(re.fullmatch(r"[0-9a-f]{40}", p["commit"]) for p in spec["publications"]), "a whole object id, never abbreviated"
    # the retained diff is the diff, and it adds the comma that joins the lists and nothing else
    retained = (EVIDENCE / "spec-diff.txt").read_text(encoding="utf-8")
    assert retained == normal_diff(FROZEN.read_text(encoding="utf-8").splitlines(keepends=True),
                                   SPEC.read_text(encoding="utf-8").splitlines(keepends=True))
    removed = [line[2:] for line in retained.splitlines() if line.startswith("< ")]
    added = [line[2:] for line in retained.splitlines() if line.startswith("> ")]
    assert len(removed) == 1 and added[0] == removed[0] + ","
    assert len(added) == 1 + len(spec["publications"]) - len(frozen["publications"]) == 31


def test_the_output_is_the_spec_s_and_the_record_names_its_run():
    doc = study()
    assert doc["spec_sha256"] == hashlib.sha256(SPEC.read_bytes()).hexdigest()
    assert hashlib.sha256(gzip.decompress((EVIDENCE / "signal-outcomes.json.gz").read_bytes())).hexdigest() == UNCOMPRESSED_SHA
    assert doc["version"] == "signal-outcomes-v1" and doc["frozen_through_session"] == "2026-10-01"
    assert doc["newest_session"] == NEWEST
    spec = json.loads(SPEC.read_bytes())
    assert [p["commit"] for p in doc["publications"]] == [p["commit"] for p in spec["publications"]]
    # the study is the frozen one: the tool in this tree, and in the commit each run named, is the merged blob
    assert git_blob((ROOT / "tools" / "signal_outcomes.py").read_bytes()) == STUDY_BLOB
    command = "python tools/signal_outcomes.py --spec docs/input-truthfulness/2026-11-07-signal-outcomes-spec-extended.json --output <dir>"
    first, second = run_record("run-record.txt"), run_record("run-record-second-interpreter.txt")
    have([first["commit"], second["commit"]])
    for run in (first, second):
        assert run["command"] == command and run["exit"] == "0" and run["blob"] == STUDY_BLOB
        named = subprocess.run(["git", "rev-parse", f"{run['commit']}:tools/signal_outcomes.py"], cwd=ROOT,
                               capture_output=True, text=True)
        assert named.returncode == 0 and named.stdout.strip() == STUDY_BLOB, (run["commit"], named.stderr)
    assert (first["interpreter"], first["pandas"]) != (second["interpreter"], second["pandas"]), "a second interpreter"
    # the second run's outputs are this run's bytes
    assert second["signal-outcomes.json sha256"] == UNCOMPRESSED_SHA
    assert second["summary.txt sha256"] == hashlib.sha256((EVIDENCE / "summary.txt").read_bytes()).hexdigest()
    summary = (EVIDENCE / "summary.txt").read_text(encoding="utf-8")
    assert f"spec {doc['spec_sha256'][:12]};" in summary and f"newest session {NEWEST}" in summary
    # the retained summary is the tool's own rendering of these rows; a JSON round trip
    # re-orders the cost ladder's keys ("0", "20", "5"), so each line is held as a set of its clauses
    rendered = so.summary_text(doc)
    assert [sorted(line.split("; ")) for line in summary.splitlines()] == [sorted(line.split("; ")) for line in rendered.splitlines()]
    text = report()
    appended = doc["publications"][-len(APPENDED):]
    assert all(p["first"] for p in appended) and len(appended) == 10
    assert f"Every one of the {word(len(appended))} is the first publication of its session and contributes signals; " \
           "none is a revision." in text
    assert f"(uncompressed SHA-256 `{UNCOMPRESSED_SHA[:12]}…`)" in text
    assert f"(SHA-256 `{doc['spec_sha256'][:12]}…`)" in text
    assert f"(blob `{STUDY_BLOB[:8]}…`, unchanged on `main` at `{first['commit'][:8]}`)" in text
    previous_sha = hashlib.sha256(PREVIOUS.read_bytes()).hexdigest()
    assert previous_sha != doc["spec_sha256"]
    # the two runs, as their records say
    assert f"Python {first['interpreter']}, pandas {first['pandas']}, exit {first['exit']}, {first['wall']} seconds of wall time" in text
    assert f"The same command under Python {second['interpreter']} and pandas {second['pandas']} wrote the same bytes, " \
           f"exit {second['exit']} in {second['wall']} seconds" in text


def test_the_first_paragraph_names_the_spec_s_own_inputs():
    """The title, the publications appended, their commits and the frozen
    file's digest, each read off the spec files."""
    frozen, previous, spec = (json.loads(p.read_bytes()) for p in (FROZEN, PREVIOUS, SPEC))
    n, n_prev, n_frozen = len(spec["publications"]), len(previous["publications"]), len(frozen["publications"])
    appended = spec["publications"][n_prev:]
    raw = REPORT.read_text(encoding="utf-8")
    assert raw.startswith(f"# The signal-outcome study over {word(n)} publications: ")
    text = report()
    parts = [f"{p['session']} (`{p['commit'][:8]}`)" for p in appended]
    named = ", ".join(parts[:-1]) + f" and {parts[-1]}"
    assert f"over {word(n)} publications: the {word(n_prev)} the 24 October extension named and the {word(len(appended))} " \
           f"published since -- run {named}." in text
    assert f"is the frozen file (SHA-256 `{hashlib.sha256(FROZEN.read_bytes()).hexdigest()[:12]}…`) with " \
           f"{word(n - n_frozen)} entries appended in its own layout -- the {word(n_prev - n_frozen)} the 24 October " \
           f"extension carried and these {word(len(appended))}:" in text


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
        nights = re.search(r"\| Nights with a settled ticket \(all rows / exploratory admitted\) \| (\d+) / (\d+) \| (\d+) / (\d+) \|", text).groups()
        assert (int(nights[2 * col]), int(nights[2 * col + 1])) == (len({r["session"] for r in doc["rows"] if r["bucket"] == "settled"}),
                                                                   len({r["session"] for r in ex if r["bucket"] == "settled"}))
        n, w, l, e, total, mean, median = settled(ex)
        assert re.search(r"\| Exploratory admitted: settled \| (\d+) \| (\d+) \|", text).group(col + 1) == str(n)
        assert re.search(r"\| Exploratory admitted: wins / losses / even \| (\d+ / \d+ / \d+) \| (\d+ / \d+ / \d+) \|", text).group(col + 1) == f"{w} / {l} / {e}"
        assert re.search(r"\| Exploratory admitted: mean R, median R \| ([^|]+) \| ([^|]+) \|", text).group(col + 1).strip() == \
            f"{signed(mean, 3)}, {signed(median, 2)}"
        boot = doc["summary"]["phases"]["exploratory"]["night_bootstrap"]
        ci = boot["ci95"]
        assert re.search(r"\| Exploratory admitted: mean of night means, 95% CI \| ([^|]+) \| ([^|]+) \|", text).group(col + 1).strip() == \
            f"{signed(boot['mean_of_night_means'], 3)} [{signed(ci[0], 3)}, {signed(ci[1], 3)}]"
        co = confirmatory_admitted(doc)
        assert re.search(r"\| Confirmatory admitted: rows / settled \| (\d+ / \d+) \| (\d+ / \d+) \|", text).group(col + 1) == f"{len(co)} / {settled(co)[0]}"
    # the table's header names the two reads
    assert "| | 24 Oct | This run, 7 Nov |" in text


def test_the_rows_that_moved_are_the_rows_own():
    """Every row of the previous run is in this one; a ticket settled in both
    runs has the same R; the rows that moved bucket are counted by what moved
    them -- the 19 to 23 October nights completing, a re-pricing setting a
    row aside, and the two oldest nights reached by the newest series -- and
    the three settled tickets that left the settled bucket are named."""
    new, old = study(), load(PREVIOUS_STUDY)
    before = {KEY(r): r for r in old["rows"]}
    now = {KEY(r): r for r in new["rows"]}
    assert all(k in now for k in before)
    assert all(now[k]["r"] == before[k]["r"] for k in before
               if before[k]["bucket"] == "settled" and now[k]["bucket"] == "settled")
    text = report()
    assert f"Every one of the {len(old['rows']):,} rows of the 24 October run is in this one under the same session, ticker and " \
           "publication, and no settled ticket changed its R." in text
    moved = [k for k in before if before[k]["bucket"] != now[k]["bucket"]]
    assert f"**{len(moved)} rows moved between buckets.**" in text
    completing = [k for k in moved if k[0] > "2026-10-16" and k[0] <= PREVIOUS_READ and now[k]["bucket"] != "basis_mismatch"]
    assert all(before[k]["bucket"] in ("open", "pending") for k in completing)
    c = Counter((before[k]["bucket"], now[k]["bucket"]) for k in completing)
    assert set(c) == {("open", "settled"), ("pending", "settled"), ("pending", "uncertain"), ("pending", "not_filled")}
    assert f"{len(completing)} are the 19 to 23 October nights completing: {c['open', 'settled']} open and " \
           f"{c['pending', 'settled']} pending rows settled, {c['pending', 'uncertain']} pending rows became uncertain and " \
           f"{c['pending', 'not_filled']} were not filled." in text
    # the re-priced rows: set aside by a later publication's history, named with the R each had
    repriced = sorted(k for k in moved if k[0] >= "2026-10-01" and now[k]["bucket"] == "basis_mismatch")
    assert [(k[0], k[1], before[k]["bucket"], now[k]["stratum"]) for k in repriced] == [
        ("2026-10-13", "BUUU", "settled", "C"), ("2026-10-19", "SUPN", "settled", "vetoed"),
        ("2026-10-20", "SUPN", "settled", "vetoed"), ("2026-10-23", "BUUU", "pending", "skip")]
    r13, r19, r20 = (before[k]["r"] for k in repriced[:3])
    assert "Four are rows set aside because a later publication re-priced their symbol's bars" in text
    assert f"BUUU of 13 October, a grade-C row settled at {signed(r13, 2)}R, and BUUU of 23 October, a skip row still pending, " \
           "its history divided by ten in the 26 October publication; and SUPN of 19 and 20 October, two vetoed rows settled at " \
           f"{signed(r19, 2)}R and {signed(r20, 2)}R, its history divided by about 1.18 in the 4 November publication." in text
    # the factors are the study's own revision rows
    for symbol, pub, factor in (("BUUU", "adaf1b1a", 10.0), ("SUPN", "a0d9172e", 1.18)):
        ratios = [x["earlier"]["c"] / x["later"]["c"] for x in new["bars"]["revision_rows"]
                  if x["symbol"] == symbol and x["later_publication"] == pub]
        assert ratios and all(abs(v - factor) < 0.02 for v in ratios), (symbol, ratios)
    left = [k for k in before if before[k]["bucket"] == "settled" and now[k]["bucket"] != "settled"]
    assert sorted(left) == repriced[:3] and not any(now[k]["stratum"] == "admitted" for k in left)
    assert "So three tickets that were settled on 24 October are settled no longer; none is admitted" in text
    # the oldest two nights
    sept = [k for k in moved if k[0] < "2026-10-01"]
    assert len(sept) + len(completing) + len(repriced) == len(moved)
    by = Counter(k[0] for k in sept)
    assert set(by) == {"2026-09-11", "2026-09-14"}
    assert f"**The remaining {word(len(sept))} are rows of the two oldest nights -- {by['2026-09-11']} of 11 September and " \
           f"{by['2026-09-14']} of 14 September -- moved the way the 24 October report described**" in text
    into = Counter(now[k]["stratum"] for k in sept if now[k]["bucket"] == "settled")
    assert all(before[k]["bucket"] != "settled" for k in sept)
    assert f"{word(sum(into.values())).capitalize()} of the {word(len(sept))} settled for the first time ({into['C']} C, " \
           f"{into['vetoed']} vetoed, {into['B']} B, {into['admitted']} admitted and {into['skip']} skip)." in text
    adm = sorted((k[0], k[1], now[k]["bucket"]) for k in sept if now[k]["stratum"] == "admitted")
    assert adm == [("2026-09-11", "EPAM", "not_filled"), ("2026-09-11", "IBM", "uncertain"), ("2026-09-11", "TRV", "settled"),
                   ("2026-09-14", "TBBB", "not_filled"), ("2026-09-14", "WSM", "settled")]
    assert f"Of the {word(len(sept))}, {word(len(adm))} are admitted rows, all walked: TRV of 11 September settled, IBM of 11 September " \
           "uncertain, EPAM of 11 September not filled, TBBB of 14 September not filled and WSM of 14 September settled" in text
    # the exploratory admitted stratum moved this time, and the report says by how much
    ex_new = [r for r in new["rows"] if r["stratum"] == "admitted" and r["phase"] == "exploratory"]
    ex_old = [r for r in old["rows"] if r["stratum"] == "admitted" and r["phase"] == "exploratory"]
    n_new, n_old = settled(ex_new), settled(ex_old)
    assert n_new[0] == n_old[0] + 2
    boot = new["summary"]["phases"]["exploratory"]["night_bootstrap"]
    assert f"{n_new[0]} settled where the 24 October run read {n_old[0]}, {signed(n_new[5], 3)}R a ticket, the mean of its " \
           f"{word(boot['nights'])} night means {signed(boot['mean_of_night_means'], 3)}R with an interval of " \
           f"[{signed(boot['ci95'][0], 3)}, {signed(boot['ci95'][1], 3)}]" in text
    assert boot["ci95"][1] < 0 and "The exploratory stratum is still negative and its interval still excludes zero" in text


def test_the_moves_come_from_the_new_publications_own_bars(published):
    """The mechanism the report names, shown rather than argued, through the
    study's own bar gatherer over the two publication lists: a moved September
    row's symbol gained bars only from the appended publications, either the
    120-session series a publication carries for the bursts it charts, reaching
    back past its September signal (and then it was walked), or observations of
    the appended sessions alone (and then it is set aside, its own session still
    missing). Which bursts a publication charts is read off the publication."""
    new, old = study(), load(PREVIOUS_STUDY)
    before = {KEY(r): r for r in old["rows"]}
    moved = [r for r in new["rows"] if KEY(r) in before and before[KEY(r)]["bucket"] != r["bucket"] and r["session"] < "2026-10-01"]
    previous = {p["commit"] for p in json.loads(PREVIOUS.read_bytes())["publications"]}
    appended = [p for p in published if p["commit"] not in previous]
    assert len(appended) == len(APPENDED)

    def tick(x) -> str:
        return x["ticker"] if isinstance(x, dict) else x
    tops, bars_rule, lengths, listed_counts = set(), set(), set(), []
    first: dict[str, tuple[str, int]] = {}  # each charted symbol's earliest series start, with that series' length
    for p in appended:
        d = p["data"]
        top, bars_n = d["rules"]["pipeline"]["series_top"], d["rules"]["pipeline"]["series_bars"]
        tops.add(top)
        bars_rule.add(bars_n)
        bursts = d.get("bursts", [])
        assert [b["rank"] for b in bursts] == list(range(1, len(bursts) + 1))
        miss = d.get("closest_miss")
        keep = {tick(x) for x in d.get("trades") or []} | {tick(x) for x in d.get("beyond_cap") or []} \
            | ({tick(miss)} if miss else set()) | {b["ticker"] for b in bursts[:top]}
        charted = [b for b in bursts if b.get("series")]
        assert {b["ticker"] for b in charted} == keep, p["commit"][:8]
        lengths |= {len(b["series"]) for b in charted}
        for b in charted:
            if b["ticker"] not in first or b["series"][0]["date"] < first[b["ticker"]][0]:
                first[b["ticker"]] = (b["series"][0]["date"], len(b["series"]))
        listed_counts.append(len(bursts))
    # a chart is the archived number of sessions, or fewer for a name listed more recently than that
    rule = bars_rule.pop()
    assert tops == {pipeline.SERIES_TOP} and not bars_rule and max(lengths) == rule and min(lengths) < rule
    bars_now, _ = so.gather_bars(published)
    bars_then, _ = so.gather_bars([p for p in published if p["commit"] in previous])
    series = {b["ticker"] for p in appended for b in p["data"].get("bursts", []) if b.get("series")}
    listed_again = {b["ticker"] for p in appended for b in p["data"].get("bursts", [])}
    observed = {s for p in appended for s in ((p["data"].get("observations") or {}).get("symbols") or {})}
    walked, aside = [], []
    for r in moved:
        gained = sorted(set(bars_now.get(r["ticker"], {})) - set(bars_then.get(r["ticker"], {})))
        assert gained, (r["ticker"], r["session"], "no bar gained, yet the row moved")
        if min(gained) < r["session"]:
            assert r["ticker"] in series, (r["ticker"], "bars before the signal, but no appended burst series")
            assert r["bucket"] in ("settled", "uncertain", "not_filled"), (r["ticker"], r["bucket"])
            walked.append(r)
        else:
            assert r["ticker"] in observed and r["ticker"] not in series, (r["ticker"], "later bars alone, yet a series")
            assert all(g > old["newest_session"] for g in gained) and 1 <= len(gained) <= len(appended), (r["ticker"], gained)
            assert (before[KEY(r)]["bucket"], r["bucket"]) == ("unmeasured", "basis_mismatch"), (r["ticker"], r["bucket"])
            aside.append(r)
    assert len(walked) + len(aside) == len(moved) == 56
    # the aside symbols: every one listed again below the charted bursts, none only observed
    aside_symbols = sorted({r["ticker"] for r in aside})
    assert all(s in listed_again for s in aside_symbols)
    for p in appended:
        for b in p["data"].get("bursts", []):
            if b["ticker"] in aside_symbols:
                assert not b.get("series") and b["rank"] > pipeline.SERIES_TOP, (b["ticker"], p["commit"][:8], b["rank"])
    walked_symbols = Counter(r["ticker"] for r in walked)
    both = [s for s, k in walked_symbols.items() if k > 1]
    assert all({r["session"] for r in walked if r["ticker"] == s} == {"2026-09-11", "2026-09-14"} for s in both)
    outcomes = Counter(r["bucket"] for r in walked)
    text = report()
    assert f"each of the {word(len(appended))} publications lists {min(listed_counts)} to {max(listed_counts)} bursts but charts only " \
           f"its tickets, its cut names, its closest miss and its top {pipeline.SERIES_TOP} bursts by rank (`pipeline.SERIES_TOP`)" in text
    assert f"bursts' {rule}-session series and from the `observations` block and nothing else" in text
    # each walked symbol's own series: a full one begins in May, a name listed more recently than the
    # archived number of sessions carries a shorter one, and every one reaches back past its signal
    full = {t: first[t][0] for t in walked_symbols if first[t][1] == rule}
    short = {t: first[t] for t in walked_symbols if first[t][1] < rule}
    assert full and short and len(full) + len(short) == len(walked_symbols)
    assert len({n for _, n in short.values()}) == 1
    short_len = next(iter(short.values()))[1]
    assert all(first[r["ticker"]][0] < r["session"] for r in walked)
    # before this run every walked row was set aside for lacking the bar of its own session, not every later bar
    assert all((before[KEY(r)]["bucket"], before[KEY(r)]["reason"]) ==
               ("basis_mismatch", "later bars exist but the signal's own session is not among them") for r in walked)
    assert f"{word(len(walked)).capitalize()} of the {word(len(moved))} rows, over {word(len(walked_symbols))} symbols " \
           f"({word(len(both))} of them on both nights), belong to symbols one of the {word(len(appended))} publications charted: " \
           f"the series begins between {when(min(full.values()))} and {when(max(full.values()))} for {word(len(full))} of them and, " \
           f"for {listed(sorted(short))}, each a {short_len}-session series for a name listed more recently, on " \
           f"{listed([when(short[t][0]) for t in sorted(short)])}, still before its September signal, so a September signal whose " \
           f"own-session bar no earlier publication had carried now has it and is walked ({outcomes['settled']} settled, " \
           f"{outcomes['uncertain']} uncertain and {outcomes['not_filled']} not filled)" in text
    assert f"The other {word(len(aside))} rows, {word(len(aside_symbols))} symbols, gained no series: every one was listed as a " \
           f"burst again between {when(appended[0]['session'])} and {when(appended[-1]['session'])} below the charted ones" in text
    assert {r["ticker"] for r in walked if r["stratum"] == "admitted"} == {"TRV", "IBM", "EPAM", "TBBB", "WSM"}
    assert not [r for r in aside if r["stratum"] == "admitted"]


def test_the_confirmatory_figure_and_its_night_table_are_the_rows_own():
    doc, text = study(), report()
    co = confirmatory_admitted(doc)
    n, w, l, e, total, mean, median = settled(co)
    block = doc["summary"]["phases"]["confirmatory"]
    assert (block["settled"]["n"], block["settled"]["mean_r"], block["settled"]["median_r"]) == (n, mean, median)
    nights = sorted({r["session"] for r in co if r["bucket"] == "settled"})
    boot = block["night_bootstrap"]
    assert boot["nights"] == len(nights)
    assert f"**Admitted, confirmatory: {n} settled** over {word(len(nights))} nights ({when(nights[0])} to {when(nights[-1])})" in text
    assert f"{w} wins, {l} losses and {e} even, sum {signed(total, 2)}R, mean {signed(mean, 3)}R, median {signed(median, 2)}R" in text
    assert f"the mean of the {word(len(nights))} night means is {signed(boot['mean_of_night_means'], 3)}R with a 95% night-bootstrap " \
           f"interval of **[{signed(boot['ci95'][0], 3)}, {signed(boot['ci95'][1], 3)}]**" in text
    assert boot["ci95"][0] < 0 < boot["ci95"][1] and "The interval includes zero" in text
    ub = block["uncertain_bound"]
    unc = [r for r in co if r["bucket"] == "uncertain"]
    bounds = [r["bound_r"] for r in unc if r["bound_r"] is not None]
    assert (len(unc), len(bounds), round(sum(bounds), 2)) == (ub["uncertain"], ub["bounded"], ub["sum_r_if_filled_at_trigger"])
    raw = sum(r["r"] for r in co if r["bucket"] == "settled")
    assert round((raw + sum(bounds)) / (n + len(bounds)), 3) == ub["pooled_mean_r_with_bound"]
    assert f"{len(unc)} uncertain tickets, {len(bounds)} of them with a bound -- the R each would have reached had its uncertain " \
           f"day filled at its trigger -- summing to {signed(sum(bounds), 2)}R, so that pooled with the {n} settled the mean " \
           f"would be {signed(ub['pooled_mean_r_with_bound'], 3)}R, and {len(unc) - len(bounds)} with no bound" in text
    assert f"so the {len(unc)} uncertain confirmatory tickets stay uncertain here" in text
    costs = block["costs_per_side_bps"]
    assert f"{signed(costs['5']['mean_r'], 3)}R at 5 basis points a side and {signed(costs['20']['mean_r'], 3)}R at 20" in text
    # the night table, row by row, in session order, no row more
    sessions = sorted({r["session"] for r in co})
    moving = 0
    for s in sessions:
        rows = [r for r in co if r["session"] == s]
        regime = {r["night_regime"] for r in rows}
        assert len(regime) == 1
        k, w1, l1, e1, t1, m1, _ = settled(rows)
        still = sum(r["bucket"] in ("open", "pending") for r in rows)
        moving += still
        cells = (f"| {day(s)} {month(s)[:3]} | {regime.pop()} | {len(rows)} | {k} | " +
                 (f"{w1} / {l1} / {e1} | {signed(t1, 2)} | {signed(m1, 3)} |" if k else "— | — | — |") + f" {still} |")
        assert cells in text, cells
    raw_md = REPORT.read_text(encoding="utf-8")
    assert re.findall(r"^\| (\d+ (?:Oct|Nov)) \|", raw_md, re.M) == [f"{day(s)} {month(s)[:3]}" for s in sessions]
    assert moving == block["buckets"]["open"] + block["buckets"]["pending"]
    pending = [r for r in co if r["bucket"] == "pending"]
    opened = [r for r in co if r["bucket"] == "open"]
    assert {r["session"] for r in pending} == {doc["newest_session"]} and {r["session"] for r in opened} == {BIG_NIGHT}
    complete = [s for s in sessions if all(r["bucket"] not in ("open", "pending") for r in co if r["session"] == s)]
    assert [s for s in sessions if s not in complete] == [BIG_NIGHT, NEWEST] and len(complete) == len(sessions) - 2
    assert f"{word(len(complete)).capitalize()} of the {word(len(sessions))} nights are complete" in text
    hz = {}
    for s in sessions:
        named = {r["horizon"] for r in co if r["session"] == s and r.get("horizon")}
        assert len(named) == 1, (s, named)
        hz[s] = named.pop()
    # the pending rows' entry session is the exchange calendar's next session after the newest one
    entry = plan.next_sessions(datetime.strptime(NEWEST, "%Y-%m-%d").date(), 1)[0]
    assert entry.weekday() == 0, entry
    assert f"The two nights that are not carry {moving} rows still open or pending: the 4 November night's {word(len(opened))} open " \
           f"rows, which reach their horizon on {when(hz[BIG_NIGHT])}, and the {len(pending)} pending rows of the 6 November night, " \
           f"whose entry session is Monday {when(entry.isoformat())}." in text
    floor = rec.SCORECARD_MIN_PLANS
    under = sum(1 for s in sessions if settled([r for r in co if r["session"] == s])[0] < floor)
    assert f"{word(under).capitalize()} of the {word(len(sessions))} nights hold fewer than {word(floor)}" in text
    reach = [s for s in sessions if settled([r for r in co if r["session"] == s])[0] >= floor]
    october, november = [day(s) for s in reach if s < "2026-11"], [day(s) for s in reach if s >= "2026-11"]
    assert len(reach) == len(sessions) - under and october and november
    assert f"only {listed(october)} October and {listed(november)} November reach {word(floor)}" in text
    assert n >= floor and f"It clears the scorecard's {word(floor)}-settled minimum" in text
    # each night's horizon is its own rows' fifth session: 30 October's is the newest session, and the
    # five November nights' run from 9 to 13 November
    tail = [s for s in sessions if s >= "2026-11"]
    assert len(tail) == 5 and hz["2026-10-30"] == NEWEST
    assert [day(hz[s]) for s in tail] == list(range(day(hz[tail[0]]), day(hz[tail[0]]) + len(tail)))
    assert f"{day(hz['2026-10-30'])} November for 30 October and {day(hz[tail[0]])} to {day(hz[tail[-1]])} November " \
           f"for {day(tail[0])} to {day(tail[-1])} November" in text
    assert f"read again after {day(hz[NEWEST])} November, when the 6 November tickets reach their fifth session" in text
    # the two estimands and their movement since 24 October, both the files' own
    old = load(PREVIOUS_STUDY)
    then = old["summary"]["phases"]["confirmatory"]
    assert f"the mean R a ticket fell from {signed(then['settled']['mean_r'], 3)}R to {signed(mean, 3)}R while the mean of night " \
           f"means rose from {signed(then['night_bootstrap']['mean_of_night_means'], 3)}R to " \
           f"{signed(boot['mean_of_night_means'], 3)}R" in text
    assert then["settled"]["mean_r"] > mean and then["night_bootstrap"]["mean_of_night_means"] < boot["mean_of_night_means"]
    big_n, _, _, _, big_sum, _, _ = settled([r for r in co if r["session"] == BIG_NIGHT])
    fraction = {0.1: "a tenth", 0.2: "a fifth", 0.3: "three tenths", 0.5: "half"}[round(big_n / n, 1)]
    assert f"the 4 November night below is {fraction} of the stratum's settled tickets and one of its {word(len(nights))} nights" in text
    # the closing paragraph repeats the two estimands, what completed, what stopped and what still moves
    old_co = [r for r in old["rows"] if r["stratum"] == "admitted" and r["phase"] == "confirmatory"]
    now_of = {KEY(r): r for r in co}
    late_total = round(sum(now_of[KEY(r)]["r"] for r in old_co if r["bucket"] in ("open", "pending")
                           and now_of[KEY(r)]["bucket"] == "settled"), 2)
    assert f"the mean of night means moved from {signed(then['night_bootstrap']['mean_of_night_means'], 3)}R to " \
           f"{signed(boot['mean_of_night_means'], 3)}R a night as the 19 to 23 October nights completed at {signed(late_total, 2)}R, " \
           f"while the mean R a ticket moved from {signed(then['settled']['mean_r'], 3)}R to {signed(mean, 3)}R as the 4 November " \
           f"night's {big_n} settled tickets all stopped, {signed(big_sum, 2)}R, and the interval still spans zero" in text
    assert f"The two nights not yet complete carry {moving} rows still moving" in text


def test_the_4_november_night_is_the_rows_and_the_records_own(published):
    doc, text = study(), report()
    co = confirmatory_admitted(doc)
    night = [r for r in co if r["session"] == BIG_NIGHT]
    k, w, l, e, total, mean, _ = settled(night)
    assert (w, e) == (0, 0)
    sums = {s: settled([r for r in co if r["session"] == s])[4] for s in {r["session"] for r in co}}
    counts = {s: settled([r for r in co if r["session"] == s])[0] for s in {r["session"] for r in co}}
    assert min(sums, key=sums.get) == BIG_NIGHT and max(counts, key=counts.get) == BIG_NIGHT
    # not the largest night by admitted rows: that is still 22 October's, as the 24 October report said
    assert Counter(r["session"] for r in co).most_common(1)[0][0] != BIG_NIGHT
    assert f"**The 4 November night is the largest single loss in the stratum, and the night with the most settled tickets: " \
           f"{len(night)} admitted rows, {k} settled, {w} wins and {l} losses, {signed(total, 2)}R.**" in text
    # the next session's breadth, read off its own record
    nxt = next(p for p in published if p["session"] == NEXT_SESSION and p["first"] if "first" in p) if any("first" in p for p in published) \
        else next(p for p in published if p["session"] == NEXT_SESSION)
    reg = nxt["data"]["breadth"]["regime"]
    assert reg["verdict"] == "red" and reg["inputs"]["down4"] >= reg["thresholds"]["down4_alarm"]
    assert f"{reg['inputs']['up4']} stocks up 4% against {reg['inputs']['down4']} down, over the scaled alarm of " \
           f"{reg['thresholds']['down4_alarm']}" in text
    events = Counter(tuple((x["day"], x["event"]) for x in r["events"]) for r in night if r["bucket"] == "settled")
    day1 = events[((1, "stopped"),)]
    held = {ev: c for ev, c in events.items() if ev[0] == (1, "stop_raised_to_entry_low")}
    assert sum(held.values()) + day1 == k and set(held) == {((1, "stop_raised_to_entry_low"), (2, "stopped_at_open")),
                                                             ((1, "stop_raised_to_entry_low"), (2, "stopped"))}
    at_open = held[((1, "stop_raised_to_entry_low"), (2, "stopped_at_open"))]
    later = held[((1, "stop_raised_to_entry_low"), (2, "stopped"))]
    assert f"every settled ticket of the night stopped: {day1} on the entry day itself, {sum(held.values())} after holding through " \
           f"it with the stop raised to the entry day's low, {at_open} of them at the next open and {later} later in that session" in text
    deep = [r["r"] for r in night if r["bucket"] == "settled" and r["r"] < -1]
    assert f"{word(len(deep))} lost more than 1R, the deepest {signed(min(deep), 2)}R" in text
    whole = [r for r in doc["rows"] if r["session"] == BIG_NIGHT]
    an, aw, al, _, atotal, _, _ = settled(whole)
    assert f"of the night's {len(whole):,} rows {an} settled, {aw} wins and {al} losses, {signed(atotal, 2)}R" in text
    rest = settled([r for r in co if r["session"] != BIG_NIGHT])
    others = len({r["session"] for r in co if r["session"] != BIG_NIGHT and r["bucket"] == "settled"})
    assert f"Without it the other {word(others)} confirmatory nights hold {rest[0]} settled at {signed(rest[4], 2)}R in sum, " \
           f"{signed(rest[5], 3)}R a ticket" in text
    # the three published tickets are the record's own trades, and every one is among the night's losses
    rec4 = next(p for p in published if p["session"] == BIG_NIGHT)
    trades = sorted(t["ticker"] if isinstance(t, dict) else t for t in rec4["data"]["trades"])
    assert trades == ["HQY", "RCBC", "VIK"]
    assert all(any(r["ticker"] == t and r["bucket"] in ("settled", "uncertain") for r in night) for t in trades)
    assert "the live policy published burst tickets -- HQY, RCBC and VIK, each A+ under an accepted review" in text
    assert all(r["grade_mechanical"] == "A+" and r["final_grade"] == "A+" and r["reader_accepted"] for r in night if r["ticker"] in trades)


def test_what_settled_since_24_october_is_the_rows_own():
    new, old = study(), load(PREVIOUS_STUDY)
    co = confirmatory_admitted(new)
    then_moving = [r for r in old["rows"] if r["stratum"] == "admitted" and r["phase"] == "confirmatory" and r["bucket"] in ("open", "pending")]
    now_of = {KEY(r): r for r in co}
    outcome = Counter(now_of[KEY(r)]["bucket"] for r in then_moving)
    assert set(outcome) == {"settled", "uncertain", "not_filled"}
    late = [now_of[KEY(r)] for r in then_moving if now_of[KEY(r)]["bucket"] == "settled"]
    n, w, l, e, total, _, _ = settled(late)
    by = Counter(r["session"] for r in late)
    text = report()
    assert set(by) == {"2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23"}
    assert f"Of the {len(then_moving)} confirmatory admitted rows still open or pending on 24 October, {n} have settled -- " \
           f"{by['2026-10-19']} of 19 October, {by['2026-10-20']} of 20 October, {by['2026-10-21']} of 21 October, " \
           f"{by['2026-10-22']} of 22 October and {by['2026-10-23']} of 23 October -- at {w} wins, {l} losses and {e} even, " \
           f"{signed(total, 2)}R in sum; {outcome['uncertain']} became uncertain and {outcome['not_filled']} were not filled." in text
    then = {s: settled([r for r in old["rows"] if r["session"] == s and r["stratum"] == "admitted"]) for s in by}
    now = {s: settled([r for r in co if r["session"] == s]) for s in by}
    late_by = {s: settled([r for r in late if r["session"] == s]) for s in by}
    assert late_by["2026-10-19"][1] == late_by["2026-10-19"][0]
    assert f"The 19 October night read {signed(then['2026-10-19'][5], 3)}R over {then['2026-10-19'][0]} settled on 24 October and reads " \
           f"{signed(now['2026-10-19'][5], 3)}R over {now['2026-10-19'][0]} now, all {late_by['2026-10-19'][0]} of its late settlers " \
           "winners; it stays the best night in the stratum by mean and by sum." in text
    means = {s: settled([r for r in co if r["session"] == s])[5] for s in {r["session"] for r in co}}
    sums = {s: settled([r for r in co if r["session"] == s])[4] for s in {r["session"] for r in co}}
    assert max((m for m in means.values() if m is not None)) == now["2026-10-19"][5] and max(sums.values()) == now["2026-10-19"][4]
    assert late_by["2026-10-20"][1] == late_by["2026-10-20"][0]
    assert f"The 20 October night read {signed(then['2026-10-20'][5], 3)}R over {then['2026-10-20'][0]} and reads " \
           f"{signed(now['2026-10-20'][5], 3)}R over {now['2026-10-20'][0]}, its {late_by['2026-10-20'][0]} late settlers all winners." in text
    s22 = [r for r in co if r["session"] == "2026-10-22"]
    stops = [r for r in s22 if r["bucket"] == "settled" and [(x["day"], x["event"]) for x in r["events"]] == [(1, "stopped")]]
    assert then["2026-10-22"][0] == 3 and then["2026-10-22"][5] == -1.0
    assert f"The 22 October night read {signed(then['2026-10-22'][5], 3)}R over its {then['2026-10-22'][0]} first-session stops and reads " \
           f"{signed(now['2026-10-22'][5], 3)}R over {now['2026-10-22'][0]}, the {late_by['2026-10-22'][0]} that settled after 24 October " \
           f"at {late_by['2026-10-22'][1]} wins, {late_by['2026-10-22'][2]} losses, {signed(late_by['2026-10-22'][4], 2)}R." in text
    assert len(stops) >= then["2026-10-22"][0]
    assert then["2026-10-23"][0] == 0 and now["2026-10-23"] == late_by["2026-10-23"]
    assert f"The 23 October night, which had no settled ticket on 24 October, settled {now['2026-10-23'][0]} at " \
           f"{now['2026-10-23'][1]} wins, {now['2026-10-23'][2]} losses and {now['2026-10-23'][3]} even, " \
           f"{signed(now['2026-10-23'][4], 2)}R." in text
    # the 19 to 23 October nights completed at the late settlers' sum, as the closing section says
    assert f"as the 19 to 23 October nights completed at {signed(total, 2)}R" in text


def test_the_new_nights_are_the_rows_own():
    doc, text = study(), report()
    co = confirmatory_admitted(doc)
    new_nights = sorted({r["session"] for r in co if r["session"] > PREVIOUS_READ})
    assert new_nights == [s for _, s in APPENDED]
    regimes = {s: {r["night_regime"] for r in co if r["session"] == s}.pop() for s in new_nights}
    assert Counter(regimes.values()) == {"yellow": 6, "red": 4}
    assert "Of the ten nights appended, six were YELLOW and four RED." in text
    st = {s: settled([r for r in co if r["session"] == s]) for s in new_nights}
    assert st["2026-11-03"][1] == 0 and st["2026-10-28"][1] > st["2026-10-28"][2]
    assert f"26 October (RED) settled {st['2026-10-26'][0]} at {signed(st['2026-10-26'][4], 2)}R; 27 October (YELLOW) " \
           f"{st['2026-10-27'][0]} at {signed(st['2026-10-27'][4], 2)}R; 28 October (YELLOW) {st['2026-10-28'][0]} at " \
           f"{signed(st['2026-10-28'][4], 2)}R, {st['2026-10-28'][1]} of them wins; 29 October (YELLOW), with " \
           f"{sum(r['session'] == '2026-10-29' for r in co)} admitted rows, {st['2026-10-29'][0]} at {signed(st['2026-10-29'][4], 2)}R; " \
           f"30 October (RED) {st['2026-10-30'][0]} at {signed(st['2026-10-30'][4], 2)}R; 2 November (YELLOW) {st['2026-11-02'][0]} at " \
           f"{signed(st['2026-11-02'][4], 2)}R; 3 November (YELLOW) {st['2026-11-03'][0]} at {signed(st['2026-11-03'][4], 2)}R, " \
           "every one a loss; 4 November (YELLOW) as above." in text
    s5 = [r for r in co if r["session"] == NEXT_SESSION]
    s6 = [r for r in co if r["session"] == NEWEST]
    b5, b6 = Counter(r["bucket"] for r in s5), Counter(r["bucket"] for r in s6)
    assert set(b5) == {"no_ticket", "uncertain"} and set(b6) == {"no_ticket", "pending"}
    assert sum(withheld(r) for r in s5) == b5["no_ticket"] and sum(withheld(r) for r in s6) == b6["no_ticket"]
    assert not any(no_order(r) for r in s5 + s6)
    assert f"The 5 November night has {len(s5)} admitted rows, {b5['no_ticket']} of them withheld by the stop rule and " \
           f"{b5['uncertain']} uncertain. The 6 November night has {len(s6)} admitted rows, {b6['pending']} of them pending " \
           f"Monday's open and {b6['no_ticket']} withheld by the stop rule." in text


def test_the_regimes_and_the_account_change_are_the_rows_own():
    doc, text = study(), report()
    co = confirmatory_admitted(doc)
    yellow = [r for r in co if r["night_regime"] == "yellow"]
    red = [r for r in co if r["night_regime"] == "red"]
    assert not [r for r in co if r["night_regime"] not in ("red", "yellow")]
    ys = sorted({r["session"] for r in yellow})
    assert ys == ["2026-10-08", "2026-10-09", "2026-10-12", "2026-10-27", "2026-10-28", "2026-10-29", "2026-11-02", "2026-11-03", "2026-11-04"]
    sessions = sorted({r["session"] for r in co})
    rs = sorted({r["session"] for r in red})
    assert f"**{word(len(ys)).capitalize()} of the {word(len(sessions))} confirmatory nights were YELLOW** -- 8, 9 and 12 October, " \
           f"27, 28 and 29 October, and 2, 3 and 4 November -- and {word(len(rs))} RED" in text
    yn, yw, yl, _, ytotal, ymean, _ = settled(yellow)
    rn, *_, rtotal, rmean, _ = settled(red)
    big = settled([r for r in yellow if r["session"] == BIG_NIGHT])
    other = settled([r for r in yellow if r["session"] != BIG_NIGHT])
    assert f"The {word(len(ys))} YELLOW nights' {yn} settled sum to {signed(ytotal, 2)}R (mean {signed(ymean, 3)}R), " \
           f"{signed(big[4], 2)}R of it the 4 November night's and the other {word(len(ys) - 1)} nights' {other[0]} settled " \
           f"{signed(other[4], 2)}R (mean {signed(other[5], 3)}R); the {word(len(rs))} RED nights' {rn} settled sum to " \
           f"{signed(rtotal, 2)}R (mean {signed(rmean, 3)}R)" in text
    aplus = settled([r for r in yellow if r["grade_mechanical"] == "A+"])
    a = settled([r for r in yellow if r["grade_mechanical"] == "A"])
    assert aplus[0] + a[0] == yn
    assert f"Of the YELLOW nights' {yn} settled, {aplus[0]} are mechanical A+ ({aplus[1]} wins, {aplus[2]} losses, " \
           f"{signed(aplus[4], 2)}R) and {a[0]} grade A ({signed(a[4], 2)}R)" in text
    assert f"A YELLOW figure of its own now has {word(len(ys))} nights and {yn} settled, but one night is {signed(big[4], 2)}R " \
           f"of its {signed(ytotal, 2)}R" in text
    # every confirmatory A+ that settled, named with its night, in session order, the sentence built from the rows
    groups: dict[str, list[str]] = {}
    for r in sorted((r for r in co if r["grade_mechanical"] == "A+" and r["bucket"] == "settled"), key=lambda r: (r["session"], r["ticker"])):
        groups.setdefault(r["session"], []).append(r["ticker"])
    parts = [f"{listed(ts)} of {when(s)}" for s, ts in groups.items()]
    k, w, l, _, total, _, _ = settled([r for r in co if r["grade_mechanical"] == "A+"])
    assert k == sum(len(ts) for ts in groups.values()) == 25
    assert f"the mechanical A+ tickets that settled are {k}: {', '.join(parts[:-1])}, and {parts[-1]} -- {w} wins, {l} losses, " \
           f"{signed(total, 2)}R" in text
    assert "this run adds the three rows the live policy published on 4 November, which no gate refused" in text
    # the rows without an order, admitted and every stratum, the week before the $30,000 nights and on them
    every_session = sorted({r["session"] for r in doc["rows"]})
    adm = Counter(r["session"] for r in doc["rows"] if r["stratum"] == "admitted" and no_order(r))
    every = Counter(r["session"] for r in doc["rows"] if no_order(r))
    before = [s for s in every_session if "2026-10-26" <= s < BIG_NIGHT]
    after = [s for s in every_session if s >= BIG_NIGHT]
    assert len(before) == 7 and len(after) == 3
    assert f"were {', '.join(str(adm[s]) for s in before[:-1])} and {adm[before[-1]]} a night on 26 October to 3 November and are " \
           f"{', '.join(str(adm[s]) for s in after[:-1])} and {adm[after[-1]]} on 4 to 6 November" in text
    assert all(adm[s] == 0 for s in after)
    assert f"across every stratum {min(every[s] for s in before)} to {max(every[s] for s in before)} a night before against " \
           f"{', '.join(str(every[s]) for s in after[:-1])} and {every[after[-1]]} after" in text
    # the admission rule is not in the frozen study: the dollar-only rows are counted
    dollar = sum(r["scan"] == "dollar" for r in co)
    dollar4 = sum(r["scan"] == "dollar" for r in co if r["session"] == BIG_NIGHT)
    assert f"so {dollar:,} of its {len(co):,} confirmatory rows came through the dollar scan alone, {dollar4} of the 4 November " \
           f"night's {sum(r['session'] == BIG_NIGHT for r in co)} among them" in text


def test_the_reader_s_own_admissions_are_the_rows_own():
    doc, text = study(), report()
    rows = [r for r in doc["rows"] if r["reader_accepted"] and r["final_grade"] in ("A+", "A")]
    assert [(r["ticker"], r["session"], r["bucket"]) for r in rows] == [
        ("DAC", "2026-10-01", "uncertain"), ("DAC", "2026-10-02", "settled"), ("LYB", "2026-10-30", "not_filled"),
        ("IBTA", "2026-11-02", "not_filled"), ("UTL", "2026-11-02", "not_filled"), ("HQY", BIG_NIGHT, "settled"),
        ("RCBC", BIG_NIGHT, "settled"), ("VIK", BIG_NIGHT, "uncertain"), ("CCI", BIG_NIGHT, "settled"), ("IDT", BIG_NIGHT, "settled"),
        ("TM", BIG_NIGHT, "not_filled"), ("TRV", BIG_NIGHT, "uncertain"), ("WEST", BIG_NIGHT, "uncertain")]
    of = {(r["ticker"], r["session"]): r for r in rows}
    assert of["DAC", "2026-10-01"]["uncertainty"] == "trigger_timing" and of["VIK", BIG_NIGHT]["uncertainty"] == "stop_sequence"
    assert {of["TRV", BIG_NIGHT]["uncertainty"], of["WEST", BIG_NIGHT]["uncertainty"]} == {"open_above_limit"}
    assert f"are {word(len(rows))} rows now: DAC of 1 October, its fill uncertain on daily bars (`trigger_timing`); DAC of 2 October, " \
           f"settled at {signed(of['DAC', '2026-10-02']['r'], 2)}R; LYB of 30 October and IBTA and UTL of 2 November, each not filled; " \
           f"and {word(sum(r['session'] == BIG_NIGHT for r in rows))} of 4 November -- HQY and RCBC, the published tickets, each stopped at " \
           f"{signed(of['HQY', BIG_NIGHT]['r'], 2)}R; VIK, the third published ticket, uncertain on daily bars (`stop_sequence`" in text
    assert of["HQY", BIG_NIGHT]["r"] == of["RCBC", BIG_NIGHT]["r"] == -1.0
    assert f"CCI, lowered to A, stopped at {signed(of['CCI', BIG_NIGHT]['r'], 2)}R; IDT, grade A, stopped at " \
           f"{signed(of['IDT', BIG_NIGHT]['r'], 2)}R; TM not filled; and TRV and WEST uncertain, each having opened above its limit." in text
    assert (of["CCI", BIG_NIGHT]["grade_mechanical"], of["CCI", BIG_NIGHT]["final_grade"]) == ("A+", "A")
    assert (of["IDT", BIG_NIGHT]["grade_mechanical"], of["IDT", BIG_NIGHT]["final_grade"]) == ("A", "A")
    block = doc["summary"]["reader_accepted"]["settled"]
    k, w, l, _, total, _, _ = settled(rows)
    assert (block["n"], block["wins"], block["losses"], block["sum_r"]) == (k, w, l, total) and k < rec.SCORECARD_MIN_PLANS
    assert f"{word(k).capitalize()} settled, {w} wins and {l} losses, {signed(total, 2)}R: under the scorecard's " \
           f"{word(rec.SCORECARD_MIN_PLANS)}-settled minimum" in text


def test_the_account_change_is_the_records_own(published):
    """The account the spec tickets each signal with is the publication's own
    block, so both boundaries the report names are read off every record."""
    doc, text = study(), report()
    acct = [(p["commit"], p["session"], p["data"]["account"]["equity"], p["data"]["account"]["risk_pct"]) for p in published]
    assert [a[0] for a in acct] == [p["commit"] for p in doc["publications"]]
    changes = [i for i in range(1, len(acct)) if acct[i][2] != acct[i - 1][2]]
    assert len(changes) == 2, "the account moved twice"
    first, second = changes
    e0, e1, e2 = acct[0][2], acct[first][2], acct[second][2]
    assert {a[3] for a in acct} == {0.5} and (e0, e1, e2) == (10000.0, 2000.0, 30000.0)
    firsts = {p["commit"]: p["first"] for p in doc["publications"]}
    c1, s1 = acct[first][:2]
    c2, s2 = acct[second][:2]
    assert not firsts[c1] and firsts[c2], "the first $2,000 publication was a revision; the first $30,000 one is a first publication"
    nth1 = sum(1 for a in acct[:first + 1] if a[1] == s1)
    nth2 = sum(1 for a in acct[:second + 1] if a[1] == s2)
    assert f"Every publication from `{c1[:8]}`, the {ORDINALS[nth1]} of {when(s1)}, carried ${e1:,.0f} of model equity at 0.5% " \
           f"risk, and every publication from `{c2[:8]}`, the {ORDINALS[nth2]} of {when(s2)}, carries ${e2:,.0f} at 0.5%" in text
    assert f"so the signals ticketed at ${e2:,.0f} are those of {when(s2)} on" in text
    co = confirmatory_admitted(doc)
    # on the $30,000 nights the stop rule still withholds, and nothing that reached sizing was short of a share
    assert sum(withheld(r) for r in co if r["session"] >= s2) > 0 and not any(no_order(r) for r in co if r["session"] >= s2)
    assert f"At ${e2 * 0.5 / 100:,.0f} of risk a ticket, every admitted setup of the three ${e2:,.0f} nights that the stop rule let " \
           "through sizes to a whole share" in text
    sessions = sorted({r["session"] for r in co})
    after1, before2 = min(s for s in sessions if s > s1), max(s for s in sessions if s < s2)
    assert f"the ${e0:,.0f} nights through {when(s1)}, the ${e1:,.0f} nights from {when(after1)} to {when(before2)}, the setups a " \
           f"${e1:,.0f} account could buy a share of, and the ${e2:,.0f} nights from {when(s2)}" in text
    assert s2 == BIG_NIGHT
    # the ten appended nights' regimes in the records are the rows' own
    regimes = {p["session"]: p["data"]["breadth"]["regime"]["verdict"] for p in published if p["session"] > PREVIOUS_READ}
    co = confirmatory_admitted(doc)
    assert all({r["night_regime"] for r in co if r["session"] == s} == {v} for s, v in regimes.items())
    assert Counter(regimes.values()) == {"yellow": 6, "red": 4}
