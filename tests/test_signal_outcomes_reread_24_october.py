"""The 24 October confirmatory re-read, held to its evidence.

The study code is frozen (``tools/signal_outcomes.py`` as PR #100 merged it),
so a re-read is three files and a report: the spec, the frozen file with
publications appended and nothing else; the retained byte-level diff against
the frozen file; the study's own output; and a dated report whose every number
must be the output's. Each number the report quotes is read again here off the
rows, and anchored to the phrase it is printed in, so a number moved anywhere in
the prose cannot pass on a match elsewhere. The 17 October re-read keeps its own
guard (``tests/test_signal_outcomes_reread.py``); this one reads the next.
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

from src import pipeline, record as rec
from tools import signal_outcomes as so

ROOT = Path(__file__).resolve().parent.parent
TRUTH = ROOT / "docs" / "input-truthfulness"
FROZEN = TRUTH / "2026-10-02-signal-outcomes-spec.json"
PREVIOUS = TRUTH / "2026-10-17-signal-outcomes-spec-extended.json"
SPEC = TRUTH / "2026-10-24-signal-outcomes-spec-extended.json"
EVIDENCE = TRUTH / "2026-10-24-signal-outcomes-confirmatory-evidence"
PREVIOUS_STUDY = TRUTH / "2026-10-17-signal-outcomes-confirmatory-evidence" / "signal-outcomes.json.gz"
REPORT = TRUTH / "2026-10-24-signal-outcomes-confirmatory.md"
#: the six publications this re-read appends, in the order they landed
APPENDED = (("a34a2978", "2026-10-19"), ("d179f206", "2026-10-19"), ("0d8494fc", "2026-10-20"),
            ("2eb0e0be", "2026-10-21"), ("fb70e706", "2026-10-22"), ("cd239b20", "2026-10-23"))
UNCOMPRESSED_SHA = "310a2fdecb3f967f9abcdb09fe20e5808d963b0ce1aca97dc9ed02f58b985eb0"
STUDY_BLOB = "39d4f25ac8ffc128fe49ead8cc3d8a025e8f11a0"
PREVIOUS_READ = "2026-10-17"


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


def listed(days: list[int]) -> str:
    return ", ".join(str(d) for d in days[:-1]) + f" and {days[-1]}" if len(days) > 1 else str(days[0])


def confirmatory_admitted(doc: dict) -> list[dict]:
    return [r for r in doc["rows"] if r["stratum"] == "admitted" and r["phase"] == "confirmatory"]


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
    assert len(added) == 1 + len(spec["publications"]) - len(frozen["publications"]) == 21


def test_the_output_is_the_spec_s_and_the_record_names_its_run():
    doc = study()
    assert doc["spec_sha256"] == hashlib.sha256(SPEC.read_bytes()).hexdigest()
    assert hashlib.sha256(gzip.decompress((EVIDENCE / "signal-outcomes.json.gz").read_bytes())).hexdigest() == UNCOMPRESSED_SHA
    assert doc["version"] == "signal-outcomes-v1" and doc["frozen_through_session"] == "2026-10-01"
    assert doc["newest_session"] == "2026-10-23"
    spec = json.loads(SPEC.read_bytes())
    assert [p["commit"] for p in doc["publications"]] == [p["commit"] for p in spec["publications"]]
    # the study is the frozen one: the tool in this tree, and in the commit each run named, is the merged blob
    assert git_blob((ROOT / "tools" / "signal_outcomes.py").read_bytes()) == STUDY_BLOB
    command = "python tools/signal_outcomes.py --spec docs/input-truthfulness/2026-10-24-signal-outcomes-spec-extended.json --output <dir>"
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
    assert f"spec {doc['spec_sha256'][:12]};" in summary and "newest session 2026-10-23" in summary
    # the retained summary is the tool's own rendering of these rows; a JSON round trip
    # re-orders the cost ladder's keys ("0", "20", "5"), so each line is held as a set of its clauses
    rendered = so.summary_text(doc)
    assert [sorted(line.split("; ")) for line in summary.splitlines()] == [sorted(line.split("; ")) for line in rendered.splitlines()]
    text = report()
    appended = doc["publications"][-len(APPENDED):]
    firsts = sum(p["first"] for p in appended)
    revisions = [p for p in appended if not p["first"]]
    assert len(revisions) == 1 and revisions[0]["session"] == "2026-10-19"
    assert sum(1 for p in doc["publications"] if p["session"] == "2026-10-19") == 2
    assert f"{WORDS[firsts].capitalize()} of them are the first publication of their session and contribute signals; " \
           "the one later one, the second 19 October publication, is a revision and contributes bars." in text
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
    # the appended commits, grouped by session in the order they landed, a revision named as one
    by_session: dict[str, list[str]] = {}
    for p in appended:
        by_session.setdefault(p["session"], []).append(p["commit"][:8])
    parts = [f"{s} (`{cs[0]}`" + "".join(f", and its revision `{c}`" for c in cs[1:]) + ")" for s, cs in by_session.items()]
    named = ", ".join(parts[:-1]) + f" and {parts[-1]}"
    assert f"over {word(n)} publications: the {word(n_prev)} the 17 October extension named and the {word(len(appended))} " \
           f"published since -- run {named}." in text
    assert f"is the frozen file (SHA-256 `{hashlib.sha256(FROZEN.read_bytes()).hexdigest()[:12]}…`) with " \
           f"{word(n - n_frozen)} entries appended in its own layout -- the {word(n_prev - n_frozen)} the 17 October " \
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
    assert "| | 17 Oct | This run, 24 Oct |" in text


def test_the_exploratory_rows_that_moved_are_the_rows_own():
    """The newest publication wins each bar, so a later publication's series can
    give a September signal bars it lacked: the moves are counted off the rows,
    and no settled ticket changed its R."""
    new, old = study(), load(PREVIOUS_STUDY)
    before = {KEY(r): r for r in old["rows"]}
    now = {KEY(r): r for r in new["rows"]}
    assert all(k in now for k in before)
    assert all(now[k]["bucket"] == "settled" and now[k]["r"] == before[k]["r"] for k in before if before[k]["bucket"] == "settled")
    text = report()
    assert f"Every one of the {len(old['rows']):,} rows of the 17 October run is in this one under the same session, ticker and " \
           "publication; no settled ticket changed its R, and the exploratory admitted stratum's settled figures did not move." in text
    ex_new = [r for r in new["rows"] if r["stratum"] == "admitted" and r["phase"] == "exploratory"]
    ex_old = [r for r in old["rows"] if r["stratum"] == "admitted" and r["phase"] == "exploratory"]
    assert settled(ex_new) == settled(ex_old)
    assert new["summary"]["phases"]["exploratory"]["settled"] == old["summary"]["phases"]["exploratory"]["settled"]
    assert new["summary"]["phases"]["exploratory"]["night_bootstrap"] == old["summary"]["phases"]["exploratory"]["night_bootstrap"]
    moved = [now[k] for k in before if before[k]["bucket"] != now[k]["bucket"] and now[k]["phase"] == "exploratory"]
    assert len(moved) == 40
    by_session = Counter(r["session"] for r in moved)
    assert set(by_session) == {"2026-09-11", "2026-09-14"}
    into_settled = Counter(r["stratum"] for r in moved if r["bucket"] == "settled")
    assert "admitted" not in into_settled and all(before[KEY(r)]["bucket"] != "settled" for r in moved)
    assert f"**{word(len(moved)).capitalize()} rows of the two oldest nights did move between buckets, " \
           f"none of them settled before**: {by_session['2026-09-11']} of 11 September and {by_session['2026-09-14']} of 14 September, " \
           f"{sum(into_settled.values())} of them settling for the first time ({into_settled['vetoed']} vetoed, {into_settled['C']} C, " \
           f"{into_settled['B']} B and {into_settled['skip']} skip, none admitted)." in text
    # the admitted stratum's three moves, named, and its non-settled buckets before and after
    admitted_moves = sorted((r["ticker"], r["session"], before[KEY(r)]["bucket"], r["bucket"]) for r in moved if r["stratum"] == "admitted")
    assert admitted_moves == [("ROKU", "2026-09-14", "basis_mismatch", "not_filled"),
                              ("TWFG", "2026-09-14", "unmeasured", "basis_mismatch"),
                              ("VRDN", "2026-09-14", "unmeasured", "basis_mismatch")]
    assert f"Of the {word(len(moved))}, {word(len(admitted_moves))} are admitted rows -- TWFG and VRDN of 14 September the second way, " \
           "from `unmeasured` to `basis_mismatch`, and ROKU of 14 September the first, from `basis_mismatch` to `not_filled`" in text
    bn, bo = Counter(r["bucket"] for r in ex_new), Counter(r["bucket"] for r in ex_old)
    assert f"so the exploratory admitted stratum's non-settled buckets read {bn['not_filled']} not filled, {bn['unmeasured']} unmeasured " \
           f"and {bn['basis_mismatch']} set aside where the 17 October run read {bo['not_filled']}, {bo['unmeasured']} and " \
           f"{bo['basis_mismatch']}" in text
    lo, hi = new["summary"]["phases"]["exploratory"]["night_bootstrap"]["ci95"]
    assert hi < 0 and "The exploratory stratum is still negative and its interval still excludes zero" in text


def test_the_moves_come_from_the_new_publications_own_bars(published):
    """The mechanism the report names, shown rather than argued, through the
    study's own bar gatherer over the two publication lists: a moved row's
    symbol gained bars only from the appended publications, either the 120-session
    series a publication carries for the bursts it charts, reaching back past its
    September signal (and then it was walked), or two to five October
    observations alone (and then it is set aside, its own session still
    missing). Which bursts a publication charts is read off the publication."""
    new, old = study(), load(PREVIOUS_STUDY)
    before = {KEY(r): r for r in old["rows"]}
    moved = [r for r in new["rows"] if KEY(r) in before and before[KEY(r)]["bucket"] != r["bucket"] and r["phase"] == "exploratory"]
    previous = {p["commit"] for p in json.loads(PREVIOUS.read_bytes())["publications"]}
    appended = [p for p in published if p["commit"] not in previous]
    assert len(appended) == len(APPENDED)
    # each appended publication charts exactly its tickets, its cut names, its closest
    # miss and its top bursts by rank, every chart the archived number of sessions
    def tick(x) -> str:
        return x["ticker"] if isinstance(x, dict) else x
    tops, lengths, starts, listed_counts = set(), set(), [], []
    for p in appended:
        d = p["data"]
        top, bars_n = d["rules"]["pipeline"]["series_top"], d["rules"]["pipeline"]["series_bars"]
        tops.add(top)
        bursts = d.get("bursts", [])
        assert [b["rank"] for b in bursts] == list(range(1, len(bursts) + 1))
        miss = d.get("closest_miss")
        keep = {tick(x) for x in d.get("trades") or []} | {tick(x) for x in d.get("beyond_cap") or []} \
            | ({tick(miss)} if miss else set()) | {b["ticker"] for b in bursts[:top]}
        charted = [b for b in bursts if b.get("series")]
        assert {b["ticker"] for b in charted} == keep, p["commit"][:8]
        lengths |= {len(b["series"]) for b in charted} | {bars_n}
        starts.append(min(b["series"][0]["date"] for b in charted))
        listed_counts.append(len(bursts))
    assert tops == {pipeline.SERIES_TOP} and len(lengths) == 1
    bars_now, _ = so.gather_bars(published)
    bars_then, _ = so.gather_bars([p for p in published if p["commit"] in previous])
    series = {b["ticker"] for p in appended for b in p["data"].get("bursts", []) if b.get("series")}
    listed_again = {b["ticker"]: b for p in appended for b in p["data"].get("bursts", [])}
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
            assert r["ticker"] in observed and r["ticker"] not in series, (r["ticker"], "October bars alone, yet a series")
            assert all(g > old["newest_session"] for g in gained) and 2 <= len(gained) <= 5, (r["ticker"], gained)
            assert (before[KEY(r)]["bucket"], r["bucket"]) == ("unmeasured", "basis_mismatch"), (r["ticker"], r["bucket"])
            aside.append(r)
    assert len(walked) + len(aside) == len(moved) == 40
    # the aside symbols: listed again below the charted bursts, or only observed
    aside_symbols = sorted({r["ticker"] for r in aside})
    relisted = [s for s in aside_symbols if s in listed_again]
    only_observed = [s for s in aside_symbols if s not in listed_again]
    for p in appended:
        for b in p["data"].get("bursts", []):
            if b["ticker"] in relisted:
                assert not b.get("series") and b["rank"] > pipeline.SERIES_TOP, (b["ticker"], p["commit"][:8], b["rank"])
    walked_symbols = Counter(r["ticker"] for r in walked)
    both = [s for s, k in walked_symbols.items() if k > 1]
    assert all({r["session"] for r in walked if r["ticker"] == s} == {"2026-09-11", "2026-09-14"} for s in both)
    outcomes = Counter(r["bucket"] for r in walked)
    def when(iso: str) -> str:
        d = datetime.strptime(iso, "%Y-%m-%d")
        return f"{d.day} {d:%B}"
    text = report()
    assert f"each of the {word(len(appended))} publications lists {min(listed_counts)} to {max(listed_counts)} bursts but charts only " \
           f"its tickets, its cut names, its closest miss and its top {pipeline.SERIES_TOP} bursts by rank (`pipeline.SERIES_TOP`)" in text
    assert f"bursts' {lengths.pop()}-session series and from the `observations` block and nothing else" in text
    assert f"{word(len(walked)).capitalize()} of the {word(len(moved))} rows, over {word(len(walked_symbols))} symbols " \
           f"({word(len(both))} of them on both nights), belong to symbols one of the {word(len(appended))} publications charted: " \
           f"the series begins between {when(min(starts))} and {when(max(starts))}" in text
    assert f"is walked ({outcomes['settled']} settled, {outcomes['uncertain']} uncertain and {outcomes['not_filled']} not filled)" in text
    assert len(only_observed) == 1
    assert f"The other {word(len(aside))} rows, {word(len(aside_symbols))} symbols, gained no series: {word(len(relisted))} were " \
           f"listed as bursts again between 19 and 23 October below the charted ones and {word(len(only_observed))}, " \
           f"{only_observed[0]}, was only observed" in text
    assert "supplies two to five bars of 19 to 23 October and nothing earlier" in text
    assert {r["ticker"] for r in aside if r["stratum"] == "admitted"} == {"TWFG", "VRDN"}
    assert {r["ticker"] for r in walked if r["stratum"] == "admitted"} == {"ROKU"}


def test_the_confirmatory_figure_and_its_night_table_are_the_rows_own():
    doc, text = study(), report()
    co = confirmatory_admitted(doc)
    n, w, l, e, total, mean, median = settled(co)
    block = doc["summary"]["phases"]["confirmatory"]
    assert (block["settled"]["n"], block["settled"]["mean_r"], block["settled"]["median_r"]) == (n, mean, median)
    nights = sorted({r["session"] for r in co if r["bucket"] == "settled"})
    boot = block["night_bootstrap"]
    assert boot["nights"] == len(nights)
    assert f"**Admitted, confirmatory: {n} settled** over {WORDS[len(nights)]} nights ({day(nights[0])} to {day(nights[-1])} October)" in text
    assert f"{w} wins, {l} losses and {e} even, sum {signed(total, 2)}R, mean {signed(mean, 3)}R, median {signed(median, 2)}R" in text
    assert f"the mean of the {WORDS[len(nights)]} night means is {signed(boot['mean_of_night_means'], 3)}R with a 95% night-bootstrap " \
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
        cells = (f"| {day(s)} Oct | {regime.pop()} | {len(rows)} | {k} | " +
                 (f"{w1} / {l1} / {e1} | {signed(t1, 2)} | {signed(m1, 3)} |" if k else "— | — | — |") + f" {still} |")
        assert cells in text, cells
    assert moving == block["buckets"]["open"] + block["buckets"]["pending"]
    pending = [r for r in co if r["bucket"] == "pending"]
    assert {r["session"] for r in pending} == {doc["newest_session"]}
    assert f"The five nights since carry {moving} rows still open or pending, {len(pending)} of them the 23 October night's tickets, " \
           "whose entry session is Monday 26 October." in text
    complete = [s for s in sessions if all(r["bucket"] not in ("open", "pending") for r in co if r["session"] == s)]
    assert complete == [s for s in sessions if s <= "2026-10-16"] and len(complete) == 11
    assert "The eleven nights through 16 October are complete" in text
    floor = rec.SCORECARD_MIN_PLANS
    under = sum(1 for s in sessions if settled([r for r in co if r["session"] == s])[0] < floor)
    assert f"{WORDS[under].capitalize()} of the {WORDS[len(sessions)]} nights hold fewer than {word(floor)}" in text
    reach = [day(s) for s in sessions if settled([r for r in co if r["session"] == s])[0] >= floor]
    assert len(reach) == len(sessions) - under and f"only {listed(reach)} October reach {word(floor)}" in text
    assert n >= floor and f"It clears the scorecard's {word(floor)}-settled minimum" in text
    # the table carries exactly the study's nights, in order, no row more, whatever its regime word
    raw = REPORT.read_text(encoding="utf-8")
    assert [int(d) for d in re.findall(r"^\| (\d+) Oct \|", raw, re.M)] == [day(s) for s in sessions]
    assert f"The {word(len(sessions) - len(complete))} RED nights since 16 October carry the {moving} rows still moving" in text
    # each night's horizon is its own rows' fifth session
    hz = {}
    for s in sessions:
        named = {r["horizon"] for r in co if r["session"] == s and r.get("horizon")}
        assert len(named) == 1, (s, named)
        hz[s] = named.pop()
    tail = ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23"]
    assert [day(hz[s]) for s in tail] == list(range(day(hz[tail[0]]), day(hz[tail[0]]) + len(tail)))
    assert f"{day(hz['2026-10-16'])} October for 16 October and {day(hz[tail[0]])} to {day(hz[tail[-1]])} October " \
           f"for {day(tail[0])} to {day(tail[-1])} October" in text
    assert hz["2026-10-16"] <= doc["newest_session"] < hz[tail[0]]
    assert f"read again after {day(hz['2026-10-23'])} October, when the 23 October tickets reach their fifth session" in text


def test_what_settled_since_17_october_is_the_rows_own():
    new, old = study(), load(PREVIOUS_STUDY)
    before = {KEY(r): r for r in old["rows"]}
    co = confirmatory_admitted(new)
    then_moving = [r for r in old["rows"] if r["stratum"] == "admitted" and r["phase"] == "confirmatory" and r["bucket"] in ("open", "pending")]
    now_of = {KEY(r): r for r in co}
    outcome = Counter(now_of[KEY(r)]["bucket"] for r in then_moving)
    assert set(outcome) == {"settled", "uncertain", "not_filled"}
    late = [now_of[KEY(r)] for r in then_moving if now_of[KEY(r)]["bucket"] == "settled"]
    n, w, l, e, total, _, _ = settled(late)
    by = Counter(r["session"] for r in late)
    text = report()
    assert f"Of the {len(then_moving)} confirmatory admitted rows still open or pending on 17 October, {n} have settled -- " \
           f"{by['2026-10-12']} of 12 October, {by['2026-10-13']} of 13 October, {by['2026-10-14']} of 14 October, " \
           f"{by['2026-10-15']} of 15 October and {by['2026-10-16']} of 16 October -- at {w} wins, {l} losses and {e} even, " \
           f"{signed(total, 2)}R in sum; {outcome['uncertain']} became uncertain and {outcome['not_filled']} were not filled." in text
    assert set(by) == {"2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"}
    # the 14 October night, then and now
    old14 = settled([r for r in old["rows"] if r["session"] == "2026-10-14" and r["stratum"] == "admitted"])
    new14 = settled([r for r in co if r["session"] == "2026-10-14"])
    late14 = settled([r for r in late if r["session"] == "2026-10-14"])
    assert f"The 14 October night read {signed(old14[5], 3)}R over {old14[0]} settled on 17 October and reads {signed(new14[5], 3)}R " \
           f"over {new14[0]} now, {late14[1]} of its {late14[0]} late settlers winners." in text
    # the 15 October night: its first-session stops and what settled after
    s15 = [r for r in co if r["session"] == "2026-10-15"]
    stops = [r for r in s15 if r["bucket"] == "settled" and [(x["day"], x["event"]) for x in r["events"]] == [(1, "stopped")]]
    late15 = settled([r for r in late if r["session"] == "2026-10-15"])
    whole15 = settled(s15)
    assert whole15[0] == len(stops) + late15[0]
    stop_mean = round(sum(r["r"] for r in stops) / len(stops), 3)
    assert f"**The 15 October night's {whole15[0]} settled are its {len(stops)} first-session stops and the {late15[0]} that settled " \
           f"after 17 October** ({late15[1]} wins, {late15[2]} losses and {late15[3]} even, {signed(late15[4], 2)}R): read whole it is " \
           f"{signed(whole15[5], 3)}R a ticket where its first-session stops alone read {signed(stop_mean, 3)}R" in text
    assert settled([r for r in old["rows"] if r["session"] == "2026-10-15" and r["stratum"] == "admitted"])[0] == len(stops)
    # the largest single loss in the stratum, by a night's sum
    sums = {s: settled([r for r in co if r["session"] == s])[4] for s in {r["session"] for r in co}}
    assert min(sums, key=sums.get) == "2026-10-15" and "the largest single loss in the stratum" in text
    s16 = settled([r for r in co if r["session"] == "2026-10-16"])
    assert s16[:4] == (3, 0, 3, 0) and "The 16 October night settled its three at three losses." in text
    # the confirmatory night mean then and now
    then = old["summary"]["phases"]["confirmatory"]["night_bootstrap"]["mean_of_night_means"]
    now = new["summary"]["phases"]["confirmatory"]["night_bootstrap"]["mean_of_night_means"]
    moving_then = sorted({r["session"] for r in then_moving})
    confirmatory_sessions = sorted({r["session"] for r in co})
    first, last = confirmatory_sessions.index(moving_then[0]), confirmatory_sessions.index(moving_then[-1])
    assert confirmatory_sessions[first:last + 1] == moving_then, "the nights that were moving are one run of sessions"
    assert all(now_of[KEY(r)]["bucket"] not in ("open", "pending") for r in then_moving)
    assert f"it moved from {signed(then, 3)}R to {signed(now, 3)}R a night as the {day(moving_then[0])} to " \
           f"{day(moving_then[-1])} October nights completed" in text


def test_the_new_nights_are_the_rows_own():
    doc, text = study(), report()
    co = confirmatory_admitted(doc)
    new_nights = sorted({r["session"] for r in co if r["session"] > PREVIOUS_READ})
    assert new_nights == sorted({s for _, s in APPENDED}) and len(new_nights) == 5
    assert all({r["night_regime"] for r in co if r["session"] == s} == {"red"} for s in new_nights)
    assert "The five new nights are all RED." in text
    s19 = [r for r in co if r["session"] == "2026-10-19"]
    k, w, l, e, total, mean, _ = settled(s19)
    means = {s: settled([r for r in co if r["session"] == s])[5] for s in {r["session"] for r in co}}
    sums = {s: settled([r for r in co if r["session"] == s])[4] for s in {r["session"] for r in co}}
    assert max((m for m in means.values() if m is not None)) == mean and max(sums.values()) == total
    open19 = sum(r["bucket"] == "open" for r in s19)
    hz19 = {r["horizon"] for r in s19 if r.get("horizon")}.pop()
    assert f"The 19 October night is the best in the stratum: {k} settled, {w} wins, {signed(total, 2)}R, mean {signed(mean, 3)}R, " \
           f"with {open19} rows still open until {day(hz19)} October." in text
    s20, s21 = settled([r for r in co if r["session"] == "2026-10-20"]), settled([r for r in co if r["session"] == "2026-10-21"])
    s22 = [r for r in co if r["session"] == "2026-10-22"]
    b22 = Counter(r["bucket"] for r in s22)
    no_order = sum(1 for r in s22 if r["bucket"] == "no_ticket" and r.get("reason") == "no_order")
    withheld = sum(1 for r in s22 if r["bucket"] == "no_ticket" and str(r.get("reason", "")).startswith("ticket withheld"))
    assert no_order + withheld == b22["no_ticket"]
    assert all([(x["day"], x["event"]) for x in r["events"]] == [(1, "stopped")] for r in s22 if r["bucket"] == "settled")
    largest = Counter(r["session"] for r in doc["rows"] if r["stratum"] == "admitted").most_common(1)[0]
    assert largest == ("2026-10-22", len(s22)), largest
    assert f"The 20 October night is {signed(s20[4], 2)}R over {s20[0]}; 21 October {signed(s21[4], 2)}R over {s21[0]}; and 22 October, " \
           f"with {len(s22)} admitted rows the largest night the study has read, has {b22['settled']} first-session stops settled, " \
           f"{b22['open']} open, {b22['uncertain']} uncertain, {b22['not_filled']} not filled and {b22['no_ticket']} rows without a " \
           f"ticket, {no_order} of them because the $2,000 account could not size a whole share and {withheld} withheld by the stop rule." in text


def test_the_regimes_and_the_account_change_are_the_rows_own():
    doc, text = study(), report()
    co = confirmatory_admitted(doc)
    yellow = [r for r in co if r["night_regime"] == "yellow"]
    red = [r for r in co if r["night_regime"] == "red"]
    assert not [r for r in co if r["night_regime"] not in ("red", "yellow")]
    ys = sorted({r["session"] for r in yellow})
    assert ys == ["2026-10-08", "2026-10-09", "2026-10-12"]
    sessions = sorted({r["session"] for r in co})
    assert all({r["night_regime"] for r in co if r["session"] == s} == {"red"} for s in sessions if s > ys[-1])
    assert f"**Three of the {WORDS[len(sessions)]} confirmatory nights were YELLOW** -- 8, 9 and 12 October -- and every night since has been RED." in text
    assert f"A YELLOW figure of its own still needs more YELLOW nights than {word(len(ys))}, and there has been none since " \
           f"{day(ys[-1])} October." in text
    yn, yw, yl, _, ytotal, ymean, _ = settled(yellow)
    rn, *_, rtotal, rmean, _ = settled(red)
    assert len({r["session"] for r in red}) == 13
    assert f"The three YELLOW nights' {yn} settled sum to {signed(ytotal, 2)}R (mean {signed(ymean, 3)}R); the thirteen RED nights' " \
           f"{rn} settled sum to {signed(rtotal, 2)}R (mean {signed(rmean, 3)}R)" in text
    aplus = [r for r in yellow if r["grade_mechanical"] == "A+"]
    an, *_, atotal, _, _ = settled(aplus)
    assert sorted((r["ticker"], r["reader_accepted"], r["final_grade"]) for r in aplus if r["bucket"] == "settled") == \
        [("HAE", False, "A+"), ("MANH", True, "C")]
    assert {r["session"] for r in aplus if r["bucket"] == "settled"} == {"2026-10-08"}
    assert f"Of the yellow nights' {yn} settled, {an} are A+ (both 8 October, {signed(atotal, 2)}R between them: an accepted review " \
           "lowered MANH to C, which the band then refused, and reader authority refused HAE's reply, so the accepted-review " \
           f"requirement withheld its ticket); the other {yn - an} are grade A" in text
    assert all(r["grade_mechanical"] == "A" for r in yellow if r["bucket"] == "settled" and r["grade_mechanical"] != "A+")
    # every confirmatory A+ that settled, named with its night, in session order
    all_aplus = sorted(((r["session"], r["ticker"], r["r"]) for r in co if r["grade_mechanical"] == "A+" and r["bucket"] == "settled"))
    k, w, l, _, total, _, _ = settled([r for r in co if r["grade_mechanical"] == "A+"])
    assert [t for _, t, _ in all_aplus] == ["BDX", "MMSI", "ROKU", "HAE", "MANH", "RAL", "JAKK", "CSV"]
    assert f"the mechanical A+ tickets that settled are {k}: BDX, MMSI and ROKU of 5 October, HAE and MANH of 8 October, RAL of 13 October, " \
           f"JAKK of 15 October and CSV of 22 October -- {w} wins, {l} losses, {signed(total, 2)}R" in text
    # the rows without an order, admitted and every stratum, before and from the first $2,000 night
    def no_order(rows):
        return Counter(r["session"] for r in rows if r["bucket"] == "no_ticket" and r.get("reason") == "no_order")
    every_session = sorted({r["session"] for r in doc["rows"]})
    adm = no_order([r for r in doc["rows"] if r["stratum"] == "admitted"])
    every = no_order(doc["rows"])
    before = [s for s in every_session if s < "2026-10-09"]
    after = [s for s in every_session if s >= "2026-10-09"]
    assert f"were {min(adm[s] for s in before)} to {max(adm[s] for s in before)} a night through 8 October and are " \
           f"{', '.join(str(adm[s]) for s in after[:-1])} and {adm[after[-1]]} on 9 to 23 October ({sum(adm[s] for s in after)} in all)" in text
    assert f"across every stratum {min(every[s] for s in before)} to {max(every[s] for s in before)} a night before against " \
           f"{min(every[s] for s in after)} to {max(every[s] for s in after)} after" in text


def test_the_reader_s_own_admissions_are_the_rows_own():
    doc, text = study(), report()
    rows = [r for r in doc["rows"] if r["reader_accepted"] and r["final_grade"] in ("A+", "A")]
    assert [(r["ticker"], r["session"], r["bucket"]) for r in rows] == [("DAC", "2026-10-01", "uncertain"), ("DAC", "2026-10-02", "settled")]
    assert rows[0]["uncertainty"] == "trigger_timing"
    assert f"both DAC: the {day(rows[0]['session'])} October signal, its fill uncertain on daily bars (`{rows[0]['uncertainty']}`), " \
           f"and the {day(rows[1]['session'])} October signal, settled at {signed(rows[1]['r'], 2)}R." in text
    assert not [r for r in rows if r["session"] > PREVIOUS_READ]
    assert "No accepted review since 17 October has left a grade in the band." in text


def test_the_account_change_is_the_records_own(published):
    """The account the spec tickets each signal with is the publication's own
    block, so the boundary the report names is read off every record."""
    doc, text = study(), report()
    acct = [(p["commit"], p["session"], p["data"]["account"]["equity"], p["data"]["account"]["risk_pct"]) for p in published]
    assert [a[0] for a in acct] == [p["commit"] for p in doc["publications"]]
    first = next(i for i, a in enumerate(acct) if a[2] != acct[0][2])
    old, new = acct[0][2], acct[first][2]
    assert all(a[2] == old for a in acct[:first]) and all(a[2] == new for a in acct[first:]), "the account moved once"
    assert {a[3] for a in acct} == {0.5}
    commit, session = acct[first][:2]
    firsts = {p["commit"]: p["first"] for p in doc["publications"]}
    assert not firsts[commit], "the first $2,000 publication is a revision, which contributes bars only"
    nth = sum(1 for a in acct[:first + 1] if a[1] == session)
    signal = next(a[1] for a in acct[first:] if firsts[a[0]])
    assert f"Every publication from `{commit[:8]}`, the {ORDINALS[nth]} of {day(session)} October, carries ${new:,.0f} of model " \
           f"equity at 0.5% risk, and every earlier one carried ${old:,.0f}." in text
    assert f"so the signals ticketed at ${new:,.0f} are those of {day(signal)} October on" in text
    risk = {a[3] for a in acct}.pop()
    assert f"At ${new * risk / 100:,.0f} of risk a ticket, halved again by the stop-risk rule on a stop-constrained ticket" in text
    # the five new nights are red in the records, as the rows say
    for p in published:
        if p["session"] > PREVIOUS_READ and firsts[p["commit"]]:
            assert p["data"]["breadth"]["regime"]["verdict"] == "red", p["session"]
