"""The largest night this universe can make still publishes.

The design point, built from the real 22 October record (its 988 bursts the
most any retained night has published): every stock its run measured as
scan-ready (`run.coverage.scan_ready`, 3,581) bursts, and its observation
window is full -- every one of those stocks with the window's whole history
and a signal on every session of it, published once a session. That record
must fit the canonical bound and its projection the reader's, the sidecar
and the quality-ledger entry their own; it would not have fitted the single
32 MiB bound the canonical record and the projection shared until 25 October.

The record is frozen bytes, so it cannot see a field the current code adds to
every burst or to every observation. Two tripwires carry that growth into the
design point: the compact bytes of the regenerated `red.json` fixture's
unreviewed, unplanned bursts and of its observations block, each held to the
size it had when this ceiling was measured. A burst the current code writes N
bytes longer adds N bytes to every burst of the design point; observations a
fraction longer scale its window by that fraction. Only a projection past a
bound fails -- a builder whose change does that re-measures the ceiling.
The ledger entry's growth is not projected: it reads a few fields of each
check, not the whole burst, and is stated here at the frozen record's size.
"""
import hashlib
import json
import subprocess
import sys
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
#: The growth tripwires' baselines, measured on the regenerated red.json the
#: day the ceiling was measured: its four bursts no review selected and no plan
#: carries, their series removed, and its observations block, all compact.
FIXTURE = ROOT / "tests/fixtures/page/red.json"
FIXTURE_ROWS = ("AMD", "NVDA", "PLUG", "DLLR")
FIXTURE_ROW_BYTES = 28641
FIXTURE_OBSERVATION_BYTES = 3713


def compact(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


@pytest.fixture(scope="module")
def frozen() -> dict:
    """The 22 October record, read out of git by commit and held to its blob;
    fetched when the checkout lacks it, and never skipped."""
    def present() -> bool:
        return subprocess.run(["git", "cat-file", "-e", f"{COMMIT}^{{commit}}"],
                              cwd=ROOT, capture_output=True).returncode == 0
    if not present():
        done = subprocess.run(["git", "fetch", "--quiet", "--no-tags", "--depth=1", "origin", COMMIT],
                              cwd=ROOT, capture_output=True, text=True)
        assert done.returncode == 0 and present(), \
            f"the 22 October publication is not in this checkout and could not be fetched: {done.stderr.strip()}"
    blob = subprocess.run(["git", "rev-parse", f"{COMMIT}:docs/data.json"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()
    assert blob == BLOB, blob
    raw = subprocess.run(["git", "cat-file", "-p", f"{COMMIT}:docs/data.json"], cwd=ROOT,
                         capture_output=True, check=True).stdout
    return json.loads(raw)


def unplanned_row_bytes(data) -> int:
    """The tripwire rows' compact bytes, series removed; held to the kind of row they are."""
    rows = {r["ticker"]: r for r in data["bursts"]}
    total = 0
    for ticker in FIXTURE_ROWS:
        row = rows[ticker]
        assert row.get("plan") is None and row.get("claude") is None, ticker
        assert row["reader_coverage"] == "not_selected_budget", ticker
        total += len(compact({k: v for k, v in row.items() if k != "series"}))
    return total


def growth():
    """How much longer a burst and the observations are under the current code
    than when the ceiling was measured: bytes a burst, and a ratio."""
    data = json.loads(FIXTURE.read_bytes())
    per_row = (unplanned_row_bytes(data) - FIXTURE_ROW_BYTES) / len(FIXTURE_ROWS)
    return per_row, len(compact(data["observations"])) / FIXTURE_OBSERVATION_BYTES


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
    names = iter(range(10**6))
    while len(symbols) < scan_ready:
        symbols[f"Y{next(names):05d}"] = deepcopy(full[len(symbols) % len(full)])
    originals = list(signals.items())
    while len(signals) < scan_ready * window:
        key, value = originals[len(signals) % len(originals)]
        signals[f"{key}#{len(signals)}"] = value
    return data


def written(data) -> bytes:
    """The bytes `report.write()` writes; the synthetic record carries no
    provenance of its own, so its write (which asks for it) is not called."""
    return compact(data) + b"\n"


def test_the_ceiling_is_written_as_production_writes_a_record(tmp_path):
    data = {"schema_version": 2, "run": {"session": "2026-10-22"}, "bursts": [{"ticker": "Ä"}], "observations": {}}
    report.write(data, tmp_path / "data.json")
    assert (tmp_path / "data.json").read_bytes() == written(data)


@pytest.fixture(scope="module")
def measured(frozen):
    data = ceiling(frozen)
    canonical = written(data)
    reader_raw, observations_raw = reader.derive(canonical)
    entry = quality_ledger.encoded(quality_ledger.build(data, hashlib.sha256(canonical).hexdigest(), []))
    return data, canonical, reader_raw, observations_raw, entry


def test_the_design_point_is_every_scan_ready_stock_beside_a_full_window(frozen, measured):
    data, canonical, *_ = measured
    scan_ready = frozen["run"]["coverage"]["scan_ready"]
    assert scan_ready == 3581 and len(frozen["bursts"]) == 988
    assert len(data["bursts"]) == len(data["funnel"]["reaction"]["rows"]) == scan_ready
    assert len({r["ticker"] for r in data["bursts"]}) == scan_ready
    symbols = data["observations"]["symbols"]
    window = max(len(v["history"]) for v in symbols.values())
    assert window == 16 and len(symbols) == scan_ready
    assert len(data["observations"]["signals"]) == scan_ready * window
    assert canonical > b"" and canonical.endswith(b"\n") and b"\n" not in canonical[:-1]


def projected(measured, per_row, ratio):
    """The design point's sizes once every burst is `per_row` bytes longer and
    the observations `ratio` times as long: the canonical record, the reader
    projection (no observations) and the sidecar (only observations)."""
    data, canonical, reader_raw, observations_raw, _ = measured
    bursts = len(data["bursts"])
    observations = len(compact(data["observations"]))
    return (len(canonical) + per_row * bursts + (ratio - 1) * observations,
            len(reader_raw) + per_row * bursts,
            len(observations_raw) * ratio)


def fits(sizes):
    canonical, projection, sidecar = sizes
    return (canonical <= reader.MAX_PUBLICATION_BYTES, projection <= reader.MAX_READER_BYTES,
            sidecar <= reader.MAX_OBSERVATION_BYTES)


def test_the_design_point_fits_every_bound_with_the_current_codes_growth(measured):
    assert fits(projected(measured, *growth())) == (True, True, True), projected(measured, *growth())
    assert len(measured[4]) <= quality_ledger.MAX_ENTRY_BYTES


def test_the_single_bound_the_two_files_shared_would_have_refused_it(measured):
    _, canonical, reader_raw, *_ = measured
    assert len(canonical) > OLD_BOUND >= len(reader_raw)


def test_a_burst_or_an_observation_grown_past_the_headroom_fails_the_design_point(measured):
    """Each bound can be crossed by the growth the tripwires carry: a burst one
    byte past the reader's headroom, observations a fraction past the record's."""
    data, canonical, reader_raw, *_ = measured
    bursts = len(data["bursts"])
    room = (reader.MAX_READER_BYTES - len(reader_raw)) // bursts
    assert fits(projected(measured, room, 1))[1] and not fits(projected(measured, room + 1, 1))[1]
    observations = len(compact(data["observations"]))
    ratio = 1 + (reader.MAX_PUBLICATION_BYTES - len(canonical)) / observations
    assert not fits(projected(measured, 0, ratio * 1.001))[0]


def test_the_tripwires_read_the_regenerated_fixture(tmp_path, monkeypatch):
    """A field the current code adds to every burst, and to every observation
    bar, shows in the fixture the tripwires read."""
    data = json.loads(FIXTURE.read_bytes())
    for row in data["bursts"]:
        row["added_by_a_later_build"] = "x" * 89                    # 116 bytes compact, with its key
    for value in data["observations"]["symbols"].values():
        for bar in value["history"]:
            bar["added"] = 1
    copy = tmp_path / "red.json"
    copy.write_text(json.dumps(data))
    monkeypatch.setattr(sys.modules[__name__], "FIXTURE", copy)
    per_row, ratio = growth()
    assert per_row == len(compact({"added_by_a_later_build": "x" * 89})) - 2 + 1   # less the braces, plus a comma
    assert ratio > 1
