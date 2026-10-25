"""The design point -- every stock 22 October's run measured as scan-ready,
bursting beside a full observation window -- still publishes.

The design point is built from the real 22 October record (its 988 bursts the
most any retained night has published): every stock its run measured as
scan-ready (`run.coverage.scan_ready`, 3,581) bursts, and its observation
window is full -- every one of those stocks carries the window's whole history,
and every stock and session of the window holds the record's own number of
signal identities for each stock and session that carried one (1.237). It is
one chosen point, not the largest night that population can make: a stock and
session of that record carries up to four signal identities. That record must
fit the canonical bound and its projection the reader's, the sidecar and the
quality-ledger entry their own; it would not have fitted the single 32 MiB
bound the canonical record and the projection shared until 25 October.

The record is frozen bytes, so it cannot see a field the current code adds.
The growth tripwires read the regenerated `red.json` fixture against what it
was when the ceiling was measured: an unreviewed, unplanned burst, a funnel
row, an observation signal, a history bar and a symbol entry, each added once
for every such entry the design point carries; the rules, added once; the
ledger's candidate for one of those bursts, once a burst; and everything else,
in the record and in its ledger entry, as if it came once a burst. That last is
an overestimate for anything written once a night -- a fixed addition of a few
kilobytes already asks for a re-measure -- and never an underestimate for a new
block written once a candidate. At most twelve bursts a night are reviewed or
planned, so what the code adds to those alone is not carried. Only a
projection past a bound fails; a builder whose change does that re-measures
the ceiling.

The README's crossings -- the burst counts at which the same construction
reaches each bound -- are computed here from the bytes each further burst
appends, and that arithmetic is held to a real build at the burst before two
of them.
"""
import hashlib
import json
import re
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from src import morning_service_journal, morning_service_report, quality_ledger, reader, report

ROOT = Path(__file__).resolve().parents[1]
#: The 22 October publication, by its whole object id: a shallow checkout can
#: fetch a commit it lacks only by the id GitHub serves it by.
COMMIT = "fb70e70638a3488bf7fbe61c7c54012c48eb1b96"
BLOB = "5fbc06804566f84a79dd1ff67d541240ccfc61a8"
OLD_BOUND = 32 * 1024 * 1024
FIXTURE = ROOT / "tests/fixtures/page/red.json"
#: The bursts the tripwire reads: red.json's four that no review selected and no plan carries.
FIXTURE_ROWS = ("AMD", "NVDA", "PLUG", "DLLR")
#: Each component's (count, compact bytes) on the regenerated red.json the day the ceiling was
#: measured: bursts with their series removed, symbols with their history emptied, the ledger's
#: candidates and the rest of its entry in the ledger's own encoding, and the record's rest -- every
#: byte outside its bursts, its funnel rows, its rules and its observation entries. That red.json is
#: the blob below, read out of git at the commit (on main) that wrote it, by its whole id, and measured
#: with the current code.
BASELINE = {"burst": (4, 28641), "funnel_row": (6, 203), "signal": (7, 1027), "bar": (10, 1424),
            "symbol": (10, 1172), "rules": (1, 16402), "residual": (6, 58050),
            "ledger_candidate": (4, 7221), "ledger_residual": (6, 8965)}
BASELINE_COMMIT = "3ee0e427ecb42a972715736cd893e74ab8bedfaa"
BASELINE_BLOB = "579481ffe341f904568bc38d237cdf179d567269"
#: The components whose total is a whole record's rest: their growth is spread over its bursts.
SPREAD = ("residual", "ledger_residual")
#: Where each component lands: what it is added once for, and the files it grows -- 0 the record,
#: 1 the projection, 2 the sidecar, 3 the ledger entry. The record's rest is let land in all three
#: of the record's files; the record's headroom is the smallest, so that never trips first.
LANDS = {"burst": ("burst", (0, 1)), "funnel_row": ("burst", (0, 1)),
         "signal": ("signal", (0, 2)), "bar": ("bar", (0, 2)), "symbol": ("symbol", (0, 2)),
         "rules": ("once", (0, 1, 3)), "residual": ("burst", (0, 1, 2)),
         "ledger_candidate": ("burst", (3,)), "ledger_residual": ("burst", (3,))}
#: The length of every clone's ticker and every added symbol's name: a letter and five digits.
CLONE, SYMBOL = "Z00000", "Y00000"
#: How far the crossings are grown: past every bound the README names.
TOP = 6000


def compact(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def entry(key, value) -> int:
    """A member's compact bytes inside its object: key, colon and value."""
    return len(compact({key: value})) - 2


def ledger_bytes(value) -> int:
    """A value's bytes in the ledger's own encoding, without the entry's newline."""
    return len(quality_ledger.encoded(value)) - 1


def written(data) -> bytes:
    """The bytes `report.write()` writes; the synthetic record carries no
    provenance of its own, so its write (which asks for it) is not called."""
    return compact(data) + b"\n"


def at_commit(commit: str, path: str, blob: str) -> bytes:
    """A file read out of git by commit and held to its blob; the commit is
    fetched when the checkout lacks it, and the test is never skipped."""
    def present() -> bool:
        return subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"],
                              cwd=ROOT, capture_output=True).returncode == 0
    if not present():
        done = subprocess.run(["git", "fetch", "--quiet", "--no-tags", "--depth=1", "origin", commit],
                              cwd=ROOT, capture_output=True, text=True)
        assert done.returncode == 0 and present(), \
            f"{commit} is not in this checkout and could not be fetched: {done.stderr.strip()}"
    found = subprocess.run(["git", "rev-parse", f"{commit}:{path}"], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.strip()
    assert found == blob, found
    return subprocess.run(["git", "cat-file", "-p", f"{commit}:{path}"], cwd=ROOT,
                          capture_output=True, check=True).stdout


@pytest.fixture(scope="module")
def frozen() -> dict:
    """The 22 October record."""
    return json.loads(at_commit(COMMIT, "docs/data.json", BLOB))


# --- the growth tripwires -------------------------------------------------------
def components(data) -> dict:
    """Each component's (count, bytes) in a record."""
    rows = {r["ticker"]: r for r in data["bursts"]}
    bursts, candidates = [], []
    for ticker in FIXTURE_ROWS:
        row = rows[ticker]
        assert row.get("plan") is None and row.get("claude") is None, ticker
        assert row["reader_coverage"] == "not_selected_budget", ticker
        bursts.append(len(compact({k: v for k, v in row.items() if k != "series"})))
        candidates.append(ledger_bytes(quality_ledger.candidate(row, data["trades"])))
    funnel = data["funnel"]["reaction"]["rows"]
    observations = data["observations"]
    signals, symbols = observations["signals"], observations["symbols"]
    bars = [bar for value in symbols.values() for bar in value["history"]]
    rest = {**data, "bursts": [], "rules": {},
            "funnel": {**data["funnel"], "reaction": {**data["funnel"]["reaction"], "rows": []}},
            "observations": {**observations, "symbols": {}, "signals": {}}}
    ledger_rest = quality_ledger.build({**data, "bursts": [], "rules": {}}, "0" * 64, [])
    return {"burst": (len(bursts), sum(bursts)),
            "funnel_row": (len(funnel), sum(len(compact(r)) for r in funnel)),
            "signal": (len(signals), sum(entry(k, v) for k, v in signals.items())),
            "bar": (len(bars), sum(len(compact(b)) for b in bars)),
            "symbol": (len(symbols), sum(entry(k, {**v, "history": []}) for k, v in symbols.items())),
            "rules": (1, len(compact(data["rules"]))),
            "residual": (len(data["bursts"]), len(compact(rest))),
            "ledger_candidate": (len(candidates), sum(candidates)),
            "ledger_residual": (len(data["bursts"]), ledger_bytes(ledger_rest))}


def growth(path=None) -> dict:
    """How many bytes longer each component is under the current code than
    when the ceiling was measured, read off the regenerated fixture: an entry's
    mean for the counted components, the rest's whole difference spread over
    the fixture's bursts for the two that are a record's rest."""
    now = components(json.loads((path or FIXTURE).read_bytes()))
    return {name: (now[name][1] - total) / now[name][0] if name in SPREAD
            else now[name][1] / now[name][0] - total / count
            for name, (count, total) in BASELINE.items()}


# --- the design point ------------------------------------------------------------
def density(data) -> float:
    """Signal identities for each stock and session that carries one, as the record carries them."""
    signals = data["observations"]["signals"].values()
    return len(signals) / len({(s["ticker"], s["session"]) for s in signals})


def sources(data) -> list:
    """The bursts a clone copies, in turn: those without a series and without a plan."""
    return [r for r in data["bursts"] if not r.get("series") and r.get("plan") is None]


def cloned(data: dict, n: int) -> dict:
    """`data` with clones of its sources appended, in turn, until it holds `n`
    bursts, each beside a copy of its source's funnel row."""
    bursts, funnel = data["bursts"], data["funnel"]["reaction"]["rows"]
    stages = {row["ticker"]: row for row in funnel}
    rows = sources(data)
    i = 0
    while len(bursts) < n:
        source = rows[i % len(rows)]
        clone = deepcopy(source)
        clone["ticker"] = f"Z{i:05d}"
        bursts.append(clone)
        funnel.append({**stages[source["ticker"]], "ticker": clone["ticker"]})
        i += 1
    return data


def window_of(data) -> int:
    return max(len(v["history"]) for v in data["observations"]["symbols"].values())


def ceiling(frozen: dict, n: int | None = None) -> dict:
    """`n` stocks -- by default every scan-ready one -- bursting beside a full
    observation window of `n` stocks."""
    data = deepcopy(frozen)
    n = n or data["run"]["coverage"]["scan_ready"]
    cloned(data, n)
    observations = data["observations"]
    symbols, signals = observations["symbols"], observations["signals"]
    window = window_of(frozen)
    full = [v for v in symbols.values() if len(v["history"]) == window]
    for k, (name, value) in enumerate(list(symbols.items())):    # every symbol the window's whole history
        if len(value["history"]) < window:
            symbols[name] = deepcopy(full[k % len(full)])
    names = iter(range(10**6))
    while len(symbols) < n:
        symbols[f"Y{next(names):05d}"] = deepcopy(full[len(symbols) % len(full)])
    target = round(n * window * density(frozen))
    originals = list(signals.items())
    while len(signals) < target:
        key, value = originals[len(signals) % len(originals)]
        signals[f"{key}#{len(signals)}"] = value
    return data


@pytest.fixture(scope="module")
def measured(frozen):
    data = ceiling(frozen)
    canonical = written(data)
    reader_raw, observations_raw = reader.derive(canonical)
    ledger = quality_ledger.encoded(quality_ledger.build(data, hashlib.sha256(canonical).hexdigest(), []))
    return data, canonical, reader_raw, observations_raw, ledger


def counts(data) -> dict:
    """How many entries of each kind the design point carries."""
    observations = data["observations"]
    return {"burst": len(data["bursts"]),
            "signal": len(observations["signals"]),
            "bar": sum(len(v["history"]) for v in observations["symbols"].values()),
            "symbol": len(observations["symbols"]),
            "once": 1}


def projected(measured, grown):
    """The design point's four sizes -- the record, the reader projection (no
    observations), the sidecar (only observations) and the ledger entry --
    once each component is `grown[name]` bytes longer."""
    data, canonical, reader_raw, observations_raw, ledger = measured
    n = counts(data)
    sizes = [len(canonical), len(reader_raw), len(observations_raw), len(ledger)]
    for name, (count, files) in LANDS.items():
        for f in files:
            sizes[f] += grown[name] * n[count]
    return tuple(sizes)


def fits(sizes):
    canonical, projection, sidecar, ledger = sizes
    return (canonical <= reader.MAX_PUBLICATION_BYTES, projection <= reader.MAX_READER_BYTES,
            sidecar <= reader.MAX_OBSERVATION_BYTES, ledger <= quality_ledger.MAX_ENTRY_BYTES)


NONE = {name: 0 for name in BASELINE}
FITS = (True, True, True, True)


# --- the crossings ------------------------------------------------------------------
def appended(frozen) -> list:
    """What each further burst appends, per source in `cloned()`'s order: to the
    record and the projection its burst row and its funnel row, to the ledger
    its candidate -- each with the comma before it, every list it joins being
    nonempty."""
    stages = {row["ticker"]: row for row in frozen["funnel"]["reaction"]["rows"]}
    each = []
    for source in sources(frozen):
        clone = {**source, "ticker": CLONE}
        row = len(compact(clone)) + len(compact({**stages[source["ticker"]], "ticker": CLONE})) + 2
        each.append((row, ledger_bytes(quality_ledger.candidate(clone, frozen["trades"])) + 1))
    return each


def grow(start, base, frozen, full_window: bool) -> dict:
    """The four sizes at every burst count from `start` (whose sizes are `base`)
    to TOP: each further burst appends its rows and, over a full window, the
    stock's symbol and the window's signals for one more stock."""
    each, began = appended(frozen), len(frozen["bursts"])
    window, signals = window_of(frozen), list(frozen["observations"]["signals"].items())
    full = [v for v in frozen["observations"]["symbols"].values() if len(v["history"]) == window]

    def target(n):
        return round(n * window * density(frozen))

    record, projection, sidecar, ledger = base
    sizes = {start: base}
    for n in range(start + 1, TOP + 1):
        row, candidate = each[(n - 1 - began) % len(each)]
        added = 0
        if full_window:
            added = entry(SYMBOL, full[(n - 1) % len(full)]) + 1
            added += sum(entry(f"{signals[j % len(signals)][0]}#{j}", signals[j % len(signals)][1]) + 1
                         for j in range(target(n - 1), target(n)))
        record, sidecar = record + row + added, sidecar + added
        projection += row               # its envelope names both sizes, whose digits the range never changes
        ledger += candidate
        sizes[n] = (record, projection, sidecar, ledger)
    return sizes


@pytest.fixture(scope="module")
def crossings(frozen, measured):
    """The four sizes at every burst count up to TOP: over a full window, grown
    from the design point (`ceiling(frozen, n)`); over 22 October's own window,
    grown from the record itself (`cloned(frozen, n)`)."""
    _, canonical, reader_raw, observations_raw, ledger = measured
    full = grow(len(measured[0]["bursts"]), (len(canonical), len(reader_raw), len(observations_raw), len(ledger)),
                frozen, True)
    record = written(frozen)
    projection, sidecar = reader._project(record)
    base = (len(record), len(projection), len(sidecar),
            len(quality_ledger.encoded(quality_ledger.build(frozen, "0" * 64, []))))
    return full, grow(len(frozen["bursts"]), base, frozen, False)


def first_over(sizes, which, bound) -> int:
    return min(n for n, size in sizes.items() if size[which] > bound)


def built(data) -> tuple:
    canonical = written(data)
    projection, sidecar = reader._project(canonical)
    return (len(canonical), len(projection), len(sidecar),
            len(quality_ledger.encoded(quality_ledger.build(data, hashlib.sha256(canonical).hexdigest(), []))))


def prose(path) -> str:
    return re.sub(r"\s+", " ", (ROOT / path).read_text())


# --- the tests --------------------------------------------------------------------
def test_the_ceiling_is_written_as_production_writes_a_record(tmp_path):
    data = {"schema_version": 2, "run": {"session": "2026-10-22"}, "bursts": [{"ticker": "Ä"}], "observations": {}}
    report.write(data, tmp_path / "data.json")
    assert (tmp_path / "data.json").read_bytes() == written(data)


def test_the_design_point_is_every_scan_ready_stock_beside_a_full_window(frozen, measured):
    data, canonical, *_ = measured
    scan_ready = frozen["run"]["coverage"]["scan_ready"]
    assert scan_ready == 3581 and len(frozen["bursts"]) == 988
    assert len(data["bursts"]) == len(data["funnel"]["reaction"]["rows"]) == scan_ready
    assert len({r["ticker"] for r in data["bursts"]}) == scan_ready
    symbols = data["observations"]["symbols"]
    window = window_of(frozen)
    assert window == 16 and len(symbols) == scan_ready
    assert all(len(v["history"]) == window for v in symbols.values())          # every stock, the whole window
    assert 1.2 < density(frozen) < 1.3                                         # 22 October's own: 1.237
    assert len(data["observations"]["signals"]) == round(scan_ready * window * density(frozen))
    assert canonical.endswith(b"\n") and b"\n" not in canonical[:-1]


def test_the_design_point_is_not_the_largest_night_its_population_can_make(frozen):
    """A stock and session carries up to four signal identities; the design
    point gives every one the record's mean."""
    pairs = {}
    for signal in frozen["observations"]["signals"].values():
        key = (signal["ticker"], signal["session"])
        pairs[key] = pairs.get(key, 0) + 1
    assert max(pairs.values()) == 4 > density(frozen)


def test_the_design_point_fits_every_bound_with_the_current_codes_growth(measured):
    assert fits(projected(measured, growth())) == FITS, projected(measured, growth())


def test_the_single_bound_the_two_files_shared_would_have_refused_it(measured):
    _, canonical, reader_raw, *_ = measured
    assert len(canonical) > OLD_BOUND >= len(reader_raw)


def test_each_bound_can_be_crossed_by_the_growth_the_tripwires_carry(measured):
    """Bursts one byte past the record's headroom; past the projection's when
    smaller signals leave the record room; signals one byte past the record's;
    both at once past the record's when neither alone is; the sidecar's own
    bound, reached when smaller bursts leave the record room for its
    observations to grow past 32 MiB; the record's rest one byte past the
    record's headroom; and the ledger's candidate one byte past the ledger's."""
    data, canonical, reader_raw, observations_raw, ledger = measured
    n = counts(data)
    record_room = reader.MAX_PUBLICATION_BYTES - len(canonical)
    projection_room = reader.MAX_READER_BYTES - len(reader_raw)
    sidecar_room = reader.MAX_OBSERVATION_BYTES - len(observations_raw)
    ledger_room = quality_ledger.MAX_ENTRY_BYTES - len(ledger)
    burst = record_room // n["burst"]                           # the record binds first at the design point
    assert burst < projection_room // n["burst"]
    assert fits(projected(measured, {**NONE, "burst": burst})) == FITS
    assert fits(projected(measured, {**NONE, "burst": burst + 1})) == (False, True, True, True)
    burst = projection_room // n["burst"]
    smaller = -(projection_room // n["signal"] + 1)             # signals that much smaller leave the record room
    assert fits(projected(measured, {**NONE, "burst": burst, "signal": smaller})) == FITS
    assert fits(projected(measured, {**NONE, "burst": burst + 1, "signal": smaller})) == (True, False, True, True)
    signal = record_room // n["signal"]
    assert fits(projected(measured, {**NONE, "signal": signal})) == FITS
    assert fits(projected(measured, {**NONE, "signal": signal + 1})) == (False, True, True, True)
    half = {**NONE, "burst": record_room // (2 * n["burst"]) + 1, "signal": record_room // (2 * n["signal"]) + 1}
    assert fits(projected(measured, {**half, "signal": 0})) == fits(projected(measured, {**half, "burst": 0})) == FITS
    assert fits(projected(measured, half)) == (False, True, True, True)          # neither alone, both together
    room = {**NONE, "burst": -(sidecar_room // n["burst"] + 1), "signal": sidecar_room // n["signal"] + 1}
    assert fits(projected(measured, room)) == (True, True, False, True)         # the sidecar's own bound
    rest = record_room // n["burst"]
    assert fits(projected(measured, {**NONE, "residual": rest})) == FITS
    assert fits(projected(measured, {**NONE, "residual": rest + 1})) == (False, True, True, True)
    candidate = ledger_room // n["burst"]
    assert candidate < rest                                     # the ledger's headroom is the smaller, a burst
    assert fits(projected(measured, {**NONE, "ledger_candidate": candidate})) == FITS
    assert fits(projected(measured, {**NONE, "ledger_candidate": candidate + 1})) == (True, True, True, False)


def test_the_baselines_are_the_fixture_they_were_measured_on():
    """Measured again, the red.json the ceiling was measured against gives every
    baseline exactly: a tripwire that read a component another way would not."""
    assert components(json.loads(at_commit(BASELINE_COMMIT, "tests/fixtures/page/red.json", BASELINE_BLOB))) == BASELINE


def test_each_components_growth_lands_in_the_files_that_carry_it_once_an_entry(measured):
    """A byte on every burst or funnel row lands in the record and the projection
    once a burst; on every signal, history bar or symbol in the record and the
    sidecar once an entry of its own; on the rules once, in the record, the
    projection and the ledger; on the record's rest once a burst, in all three of
    the record's files; on the ledger's candidate or its rest once a burst, in
    the ledger alone."""
    data, *_ = measured
    n, start = counts(data), projected(measured, NONE)
    symbols = data["observations"]["symbols"]
    assert n["bar"] == sum(len(v["history"]) for v in symbols.values()) == 16 * n["symbol"]
    assert len(data["funnel"]["reaction"]["rows"]) == n["burst"] and n["signal"] == len(data["observations"]["signals"])
    b, s, bar, sym = n["burst"], n["signal"], n["bar"], n["symbol"]
    expected = {"burst": [b, b, 0, 0], "funnel_row": [b, b, 0, 0], "signal": [s, 0, s, 0],
                "bar": [bar, 0, bar, 0], "symbol": [sym, 0, sym, 0], "rules": [1, 1, 0, 1],
                "residual": [b, b, b, 0], "ledger_candidate": [0, 0, 0, b], "ledger_residual": [0, 0, 0, b]}
    assert set(expected) == set(BASELINE)
    for name in BASELINE:
        moved = [after - before for after, before in zip(projected(measured, {**NONE, name: 1}), start)]
        assert moved == expected[name], name


KEY = "added_by_a_later_build"
ADDED = entry(KEY, "x" * 89) + 1                                    # with its key, colon and comma


def mutate(data, name):
    """A field a later build adds to every entry of one component of `data`, and
    how many entries took it. The record's rest takes one value long enough to
    come to ADDED bytes once a burst."""
    observations = data["observations"]
    rows = [r for r in data["bursts"] if r["ticker"] in FIXTURE_ROWS]
    spread = ADDED * len(data["bursts"]) - entry(KEY, "") - 1
    if name in ("residual", "ledger_residual"):
        (data["run"] if name == "residual" else data["run"]["coverage"])[KEY] = "x" * spread
        return 1
    targets = {"burst": rows,
               "funnel_row": data["funnel"]["reaction"]["rows"],
               "signal": list(observations["signals"].values()),
               "bar": [b for v in observations["symbols"].values() for b in v["history"]],
               "symbol": list(observations["symbols"].values()),
               "rules": [data["rules"]],
               "ledger_candidate": [r["quality"]["checks"][0]["values"] for r in rows]}[name]
    for value in targets:
        value[KEY] = "x" * 89
    return len(targets)


#: Which tripwires each mutation moves, besides its own; the ledger copies a check's values, the
#: run's coverage and the rules from the record, so those move the record's own tripwires too.
ALSO = {"ledger_candidate": ("burst",), "ledger_residual": ("residual",)}
#: The files each mutation of the fixture really grows. The run's rest lands in the record and the
#: projection, never in the sidecar the projection lets it reach.
REAL = {"burst": (0, 1), "funnel_row": (0, 1), "signal": (0, 2), "bar": (0, 2), "symbol": (0, 2),
        "rules": (0, 1, 3), "residual": (0, 1), "ledger_candidate": (0, 1, 3), "ledger_residual": (0, 1, 3)}


def test_the_rests_tripwires_spread_a_difference_not_a_mean(tmp_path):
    """A fixture with a burst fewer, all else the same, moves no tripwire: the
    rest is spread over the bursts as a difference, never divided anew."""
    data = json.loads(FIXTURE.read_bytes())
    data["bursts"] = [r for r in data["bursts"] if r["ticker"] != "AAPL"]
    copy = tmp_path / "red.json"
    copy.write_text(json.dumps(data))
    assert {k: round(after - before, 9) for (k, after), before in zip(growth(copy).items(), growth().values())} == NONE


@pytest.mark.parametrize("name", list(BASELINE))
def test_each_tripwire_reads_its_own_component_of_the_regenerated_fixture(name, tmp_path):
    """A field the current code adds to every entry of one component shows in
    that component's tripwire, at its own bytes, and in no other but the ones a
    copy of it lands in; and in the fixture's own files it lands where the
    projection lets it land."""
    data = json.loads(FIXTURE.read_bytes())
    before, files = growth(FIXTURE), built(data)
    entries = mutate(data, name)
    copy = tmp_path / "red.json"
    copy.write_text(json.dumps(data))
    after = growth(copy)
    assert ADDED == 117
    moved = (name,) + ALSO.get(name, ())
    assert {k: round(after[k] - before[k], 9) for k in BASELINE} == {k: (ADDED if k in moved else 0) for k in BASELINE}
    grew = [now - was for now, was in zip(built(data), files)]
    added = ADDED * (len(data["bursts"]) if name in SPREAD else entries)
    assert grew == [added if f in REAL[name] else 0 for f in range(4)], (name, grew)
    assert set(REAL[name]) <= {f for k in moved for f in LANDS[k][1]}, name     # it lands nowhere unprojected


def test_the_crossing_arithmetic_is_what_a_real_build_makes(frozen, measured, crossings):
    """The design point grown by arithmetic agrees with the design point built,
    the burst before each of two crossings agrees with a real build of it, and
    every step to the first adds what that build holds for its stock."""
    full, held = crossings
    start = len(measured[0]["bursts"])
    assert held[start][3] == full[start][3] == len(measured[4])          # the ledger reads no observations
    for sizes in (full, held):                   # the projection names these two, at one length throughout
        assert all(len({len(str(size[f])) for size in sizes.values()}) == 1 for f in (0, 2))
    record = first_over(full, 0, reader.MAX_PUBLICATION_BYTES)
    data = ceiling(frozen, record - 1)
    assert full[record - 1] == built(data)
    # and every step on the way: what the sidecar gains for the nth stock is the
    # real build's own nth symbol and the signals it holds for that stock, by
    # position, so an entry miscounted at one step cannot cancel another's.
    symbols, signals = (list(data["observations"][k].items()) for k in ("symbols", "signals"))
    window, signal_density = window_of(frozen), density(frozen)
    stock = [round(n * window * signal_density) for n in range(record)]
    for n in range(start + 1, record):
        real = entry(*symbols[n - 1]) + 1 + sum(entry(k, v) + 1 for k, v in signals[stock[n - 1]:stock[n]])
        assert full[n][2] - full[n - 1][2] == real, n
    projection = first_over(held, 1, reader.MAX_READER_BYTES)
    assert held[projection - 1] == built(cloned(deepcopy(frozen), projection - 1))


def test_the_readme_quotes_the_design_point_and_the_crossings(frozen, measured, crossings):
    _, canonical, reader_raw, _, ledger = measured
    full, held = crossings
    record = first_over(full, 0, reader.MAX_PUBLICATION_BYTES)
    assert fits(full[record - 1]) == FITS and fits(full[record]) == (False, True, True, True)
    projection = first_over(held, 1, reader.MAX_READER_BYTES)
    held_record = first_over(held, 0, reader.MAX_PUBLICATION_BYTES)
    assert fits(held[projection - 1]) == FITS and fits(held[projection]) == (True, False, True, True)
    entry_over = first_over(held, 3, quality_ledger.MAX_ENTRY_BYTES)
    assert entry_over == first_over(full, 3, quality_ledger.MAX_ENTRY_BYTES)          # either way
    assert projection < entry_over < held_record
    text = prose("README.md")
    assert (f"(1.237 signal identities for each stock and session that carried one, given to every stock "
            f"and session of the window)") in text and f"{density(frozen):.3f}" == "1.237"
    assert (f"makes a record of {len(canonical):,} bytes, past the old bound, and a projection of "
            f"{len(reader_raw):,}") in text
    mib = quality_ledger.MAX_ENTRY_BYTES // (1024 * 1024)
    assert (f"while every bursting stock keeps a full window the record's own bound is reached first, at "
            f"{record:,} bursts; with 22 October's observation window held, the projection's is, at "
            f"{projection:,} (the record's at {held_record:,}). The quality ledger's {mib} MiB entry is reached "
            f"at {entry_over:,} either way ({len(ledger):,} bytes at the design point, with no scorecard rows "
            f"or exception membership; a night's entry adds its own)") in text


def test_the_morning_report_counts_the_design_points_publications(measured):
    """How many design-point publications the report may read and the journal
    keeps -- the publications alone; their receipts and events share the bound."""
    size = len(measured[1])
    words = {4: "four", 5: "five", 6: "six"}
    read = morning_service_report.MAX_READ_BYTES // size
    kept = morning_service_journal.MAX_BYTES // size
    assert morning_service_report.MAX_READ_BYTES == 256 * 1024 * 1024 and morning_service_journal.MAX_BYTES == 1024 ** 3
    assert (f"the design point the 22 October scan-ready population makes is {size:,} bytes. At that size "
            f"{words[read]} publications fit the 256 MiB a report may read and at most {kept} the 1 GiB the "
            f"journal keeps") in prose("docs/operations/morning-service-report.md")
