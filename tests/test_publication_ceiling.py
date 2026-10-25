"""The largest night 22 October's scan-ready population can make still publishes.

The design point, built from the real 22 October record (its 988 bursts the
most any retained night has published): every stock its run measured as
scan-ready (`run.coverage.scan_ready`, 3,581) bursts, and its observation
window is full -- every one of those stocks carries the window's whole history,
and the window holds signals at the record's own density (signals for each
stock and session, 22 October's own ratio of signal identities to the stocks
and sessions they name). That record must fit the canonical bound and its
projection the reader's, the sidecar and the quality-ledger entry their own;
it would not have fitted the single 32 MiB bound the canonical record and the
projection shared until 25 October.

The record is frozen bytes, so it cannot see a field the current code adds.
The growth tripwires read the regenerated `red.json` fixture: the bytes of an
unreviewed, unplanned burst, of a funnel row, of an observation signal, of a
history bar and of a symbol entry, each against what it was when the ceiling
was measured. Each component's growth is added once for every such entry the
design point carries. Only a projection past a bound fails -- a builder whose
change does that re-measures the ceiling. The ledger entry's growth is not
projected: it reads a few fields of each check, not the whole burst, and is
stated here at the frozen record's size.
"""
import hashlib
import json
import re
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from src import quality_ledger, reader, report

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
#: measured; bursts with their series removed, symbols with their history emptied. That red.json
#: is the blob below, read out of git at the commit (on main) that wrote it, by its whole id.
BASELINE = {"burst": (4, 28641), "funnel_row": (6, 203), "signal": (7, 1027), "bar": (10, 1424), "symbol": (10, 1172)}
BASELINE_COMMIT = "3ee0e427ecb42a972715736cd893e74ab8bedfaa"
BASELINE_BLOB = "579481ffe341f904568bc38d237cdf179d567269"


def compact(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def entry(key, value) -> int:
    """A member's compact bytes inside its object: key, colon and value."""
    return len(compact({key: value})) - 2


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
    """Each component's (count, compact bytes) in a record."""
    rows = {r["ticker"]: r for r in data["bursts"]}
    bursts = []
    for ticker in FIXTURE_ROWS:
        row = rows[ticker]
        assert row.get("plan") is None and row.get("claude") is None, ticker
        assert row["reader_coverage"] == "not_selected_budget", ticker
        bursts.append(len(compact({k: v for k, v in row.items() if k != "series"})))
    funnel = data["funnel"]["reaction"]["rows"]
    observations = data["observations"]
    signals, symbols = observations["signals"], observations["symbols"]
    bars = [bar for value in symbols.values() for bar in value["history"]]
    return {"burst": (len(bursts), sum(bursts)),
            "funnel_row": (len(funnel), sum(len(compact(r)) for r in funnel)),
            "signal": (len(signals), sum(entry(k, v) for k, v in signals.items())),
            "bar": (len(bars), sum(len(compact(b)) for b in bars)),
            "symbol": (len(symbols), sum(entry(k, {**v, "history": []}) for k, v in symbols.items()))}


def growth(path=None) -> dict:
    """How many bytes longer each component is under the current code than
    when the ceiling was measured, read off the regenerated fixture."""
    now = components(json.loads((path or FIXTURE).read_bytes()))
    return {name: now[name][1] / now[name][0] - total / count for name, (count, total) in BASELINE.items()}


# --- the design point ------------------------------------------------------------
def density(data) -> float:
    """Signal identities for each stock and session they name, as the record carries them."""
    signals = data["observations"]["signals"].values()
    return len(signals) / len({(s["ticker"], s["session"]) for s in signals})


def ceiling(frozen: dict) -> dict:
    """Every scan-ready stock bursting beside a full observation window."""
    data = deepcopy(frozen)
    scan_ready = data["run"]["coverage"]["scan_ready"]
    bursts, funnel = data["bursts"], data["funnel"]["reaction"]["rows"]
    stages = {row["ticker"]: row for row in funnel}
    sources = [r for r in bursts if not r.get("series") and r.get("plan") is None]
    i = 0
    while len(bursts) < scan_ready:
        source = sources[i % len(sources)]
        clone = deepcopy(source)
        clone["ticker"] = f"Z{i:05d}"
        bursts.append(clone)
        funnel.append({**stages[source["ticker"]], "ticker": clone["ticker"]})
        i += 1
    observations = data["observations"]
    symbols, signals = observations["symbols"], observations["signals"]
    window = max(len(v["history"]) for v in symbols.values())
    full = [v for v in symbols.values() if len(v["history"]) == window]
    for k, (name, value) in enumerate(list(symbols.items())):    # every symbol the window's whole history
        if len(value["history"]) < window:
            symbols[name] = deepcopy(full[k % len(full)])
    names = iter(range(10**6))
    while len(symbols) < scan_ready:
        symbols[f"Y{next(names):05d}"] = deepcopy(full[len(symbols) % len(full)])
    target = round(scan_ready * window * density(frozen))
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
    """How many entries of each component the design point carries."""
    observations = data["observations"]
    return {"burst": len(data["bursts"]),
            "funnel_row": len(data["funnel"]["reaction"]["rows"]),
            "signal": len(observations["signals"]),
            "bar": sum(len(v["history"]) for v in observations["symbols"].values()),
            "symbol": len(observations["symbols"])}


def projected(measured, grown):
    """The design point's sizes once each component is `grown[name]` bytes
    longer: the canonical record, the reader projection (no observations) and
    the sidecar (only observations)."""
    data, canonical, reader_raw, observations_raw, _ = measured
    n = counts(data)
    per_burst = sum(grown[name] * n[name] for name in ("burst", "funnel_row"))
    per_observation = sum(grown[name] * n[name] for name in ("signal", "bar", "symbol"))
    return (len(canonical) + per_burst + per_observation,
            len(reader_raw) + per_burst,
            len(observations_raw) + per_observation)


def fits(sizes):
    canonical, projection, sidecar = sizes
    return (canonical <= reader.MAX_PUBLICATION_BYTES, projection <= reader.MAX_READER_BYTES,
            sidecar <= reader.MAX_OBSERVATION_BYTES)


NONE = {name: 0 for name in BASELINE}


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
    window = max(len(v["history"]) for v in frozen["observations"]["symbols"].values())
    assert window == 16 and len(symbols) == scan_ready
    assert all(len(v["history"]) == window for v in symbols.values())          # every stock, the whole window
    assert 1.2 < density(frozen) < 1.3                                         # 22 October's own: 1.237
    assert len(data["observations"]["signals"]) == round(scan_ready * window * density(frozen))
    assert canonical.endswith(b"\n") and b"\n" not in canonical[:-1]


def test_the_design_point_fits_every_bound_with_the_current_codes_growth(measured):
    assert fits(projected(measured, growth())) == (True, True, True), projected(measured, growth())
    assert len(measured[4]) <= quality_ledger.MAX_ENTRY_BYTES


def test_the_single_bound_the_two_files_shared_would_have_refused_it(measured):
    _, canonical, reader_raw, *_ = measured
    assert len(canonical) > OLD_BOUND >= len(reader_raw)


def test_each_bound_can_be_crossed_by_the_growth_the_tripwires_carry(measured):
    """Bursts one byte past the record's headroom; past the projection's when
    smaller signals leave the record room; signals one byte past the record's;
    both at once past the record's when neither alone is; and the sidecar's own
    bound, reached when smaller bursts leave the record room for its
    observations to grow past 32 MiB."""
    data, canonical, reader_raw, observations_raw, _ = measured
    n = counts(data)
    record_room = reader.MAX_PUBLICATION_BYTES - len(canonical)
    projection_room = reader.MAX_READER_BYTES - len(reader_raw)
    sidecar_room = reader.MAX_OBSERVATION_BYTES - len(observations_raw)
    burst = record_room // n["burst"]                           # the record binds first at the design point
    assert burst < projection_room // n["burst"]
    assert fits(projected(measured, {**NONE, "burst": burst})) == (True, True, True)
    assert fits(projected(measured, {**NONE, "burst": burst + 1})) == (False, True, True)
    burst = projection_room // n["burst"]
    smaller = -(projection_room // n["signal"] + 1)             # signals that much smaller leave the record room
    assert fits(projected(measured, {**NONE, "burst": burst, "signal": smaller})) == (True, True, True)
    assert fits(projected(measured, {**NONE, "burst": burst + 1, "signal": smaller})) == (True, False, True)
    signal = record_room // n["signal"]
    assert fits(projected(measured, {**NONE, "signal": signal})) == (True, True, True)
    assert fits(projected(measured, {**NONE, "signal": signal + 1})) == (False, True, True)
    half = {**NONE, "burst": record_room // (2 * n["burst"]) + 1, "signal": record_room // (2 * n["signal"]) + 1}
    assert fits(projected(measured, {**half, "signal": 0})) == fits(projected(measured, {**half, "burst": 0})) == (True, True, True)
    assert fits(projected(measured, half)) == (False, True, True)                # neither alone, both together
    room = {**NONE, "burst": -(sidecar_room // n["burst"] + 1), "signal": sidecar_room // n["signal"] + 1}
    assert fits(projected(measured, room)) == (True, True, False)               # the sidecar's own bound


def test_the_baselines_are_the_fixture_they_were_measured_on():
    """Measured again, the red.json the ceiling was measured against gives every
    baseline exactly: a tripwire that read a component another way would not."""
    assert components(json.loads(at_commit(BASELINE_COMMIT, "tests/fixtures/page/red.json", BASELINE_BLOB))) == BASELINE


def test_each_components_growth_lands_in_the_files_that_carry_it_once_an_entry(measured):
    """A byte on every burst or funnel row lands in the record and the projection
    once a burst; a byte on every signal, history bar or symbol in the record and
    the sidecar once an entry of its own."""
    data, *_ = measured
    n, start = counts(data), projected(measured, NONE)
    symbols = data["observations"]["symbols"]
    assert n["bar"] == sum(len(v["history"]) for v in symbols.values()) == 16 * n["symbol"]
    assert n["funnel_row"] == n["burst"] and n["signal"] == len(data["observations"]["signals"])
    for name in BASELINE:
        moved = [after - before for after, before in zip(projected(measured, {**NONE, name: 1}), start)]
        reader_side = name in ("burst", "funnel_row")
        assert moved == [n[name], n[name] if reader_side else 0, 0 if reader_side else n[name]], name


@pytest.mark.parametrize("name", list(BASELINE))
def test_each_tripwire_reads_its_own_component_of_the_regenerated_fixture(name, tmp_path):
    """A field the current code adds to every entry of one component shows in
    that component's tripwire, at its own bytes, and in no other."""
    data = json.loads(FIXTURE.read_bytes())
    observations = data["observations"]
    targets = {"burst": [r for r in data["bursts"] if r["ticker"] in FIXTURE_ROWS],
               "funnel_row": data["funnel"]["reaction"]["rows"],
               "signal": list(observations["signals"].values()),
               "bar": [b for v in observations["symbols"].values() for b in v["history"]],
               "symbol": list(observations["symbols"].values())}[name]
    before = growth(FIXTURE)
    for value in targets:
        value["added_by_a_later_build"] = "x" * 89
    copy = tmp_path / "red.json"
    copy.write_text(json.dumps(data))
    after = growth(copy)
    added = entry("added_by_a_later_build", "x" * 89) + 1               # with its key, colon and comma
    assert added == 117
    assert {k: round(after[k] - before[k], 9) for k in BASELINE} == {k: (added if k == name else 0) for k in BASELINE}


def test_the_readme_quotes_the_design_points_sizes(measured):
    _, canonical, reader_raw, _, ledger = measured
    text = re.sub(r"\s+", " ", (ROOT / "README.md").read_text())
    assert (f"makes a record of {len(canonical):,} bytes, past the old bound, and a projection of "
            f"{len(reader_raw):,}") in text
    assert f"({len(ledger):,} bytes at the design point)" in text
