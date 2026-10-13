"""Source-recovery receipts over retained publications, via the real collector.

Every file is what `src.source_recovery.collect` writes for a pinned clock and
the suite's own Alpaca double; no provider is called. The primary source is the
immutable production capture the stop-research fixtures retain (the 9 October
2026 publication, one stale stock, WBD, ending 5 October; applicable session 12
October) with its real quality-ledger entry read in place. The `thin` page
fixture (QAA stale, ending 9 September) stands in where a receipt must be
drawn against a page the smoke can load, and a copy of it with its stale names
withheld exercises the ledger-named and unnamed paths; a `full` night has no
deficit. Every bar the double serves is synthetic. `--check` re-derives every
file and refuses a stale one.
"""
import argparse
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from unittest import mock

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src import market_data, quality_ledger, source_recovery  # noqa: E402
from tests.fakes import FakeAlpaca, FakeDataClient  # noqa: E402
from tests.synthetic import make_ohlcv  # noqa: E402

TARGET = Path(__file__).parent
STOP = ROOT / "tests/fixtures/stop-research"
PAGE = ROOT / "tests/fixtures/page"
LEDGER = ROOT / "docs" / quality_ledger.DIRECTORY
# 8:20 Chicago on Monday 12 October 2026: the first scheduled morning slot,
# ten minutes before the 9:30 ET open the capture's plans are for
NOW = datetime(2026, 10, 12, 13, 20, tzinfo=timezone.utc)
# the same slot on Friday 11 September 2026, the session after the page fixtures' night
THIN_NOW = datetime(2026, 9, 11, 13, 20, tzinfo=timezone.utc)
SEED = [20261012, 7]


class Refused(Exception):
    """What the SDK raises for a rejected key, as the scan transport classifies it."""
    status_code = 401


def encoded(value):
    return json.dumps(value, allow_nan=False, indent=2).encode() + b"\n"


def capture():
    raw = gzip.decompress((STOP / "current-publication.json.gz").read_bytes())
    ledger = (LEDGER / (hashlib.sha256(raw).hexdigest() + ".json.gz")).read_bytes()
    return raw, ledger


def page(name):
    return (PAGE / f"{name}.json").read_bytes()


def unnamed(raw):
    """The thin night with its stale names withheld, as a record over the
    naming bound records them; the tolerance block sits outside the sealed
    run facts, so the publication still verifies."""
    data = json.loads(raw)
    data["run"]["input_tolerance"]["names"] = None
    data["run"]["input_tolerance"]["endings"] = None
    return json.dumps(data, allow_nan=False, indent=2).encode() + b"\n"


def ledger_for(raw, exceptions):
    """A quality-ledger entry built by the ledger's own builder over the record,
    in the container `append()` writes; `capture()` refuses fixtures, so the
    entry is built here with the exception membership a run would have retained."""
    data = json.loads(raw)
    entry = quality_ledger.build(data, hashlib.sha256(raw).hexdigest(), [], exceptions=exceptions, revision=None)
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as handle:
        handle.write(quality_ledger.encoded(entry))
    return buffer.getvalue()


def double(symbol, *, stale_sessions=0, hole=None, placeholder=False, nan_close=False, raise_on_bars=None, history=True):
    fake = FakeAlpaca()
    if history:
        df = make_ohlcv("flat", seed=SEED, days=260)
        if placeholder:
            # the provider's placeholder bar: one price, zero volume
            last = df.index[-1]
            close = float(df.loc[last, "Close"])
            for column in ("Open", "High", "Low", "Close"):
                df.loc[last, column] = close
            df.loc[last, "Volume"] = 0
        if nan_close:
            # a session bar that arrived without a close: present, and unreadable
            df.loc[df.index[-1], "Close"] = float("nan")
        fake.add_history(symbol, df, stale_sessions=stale_sessions)
        if hole is not None:
            fake.hole_on(symbol, hole)
    fake.raise_on_bars = raise_on_bars
    return fake


def build():
    raw, ledger = capture()
    files = {}

    def collect(name, publication, ledger_raw, *, fake=None, clock=lambda: NOW, previous=None, dry_run=False, client="double"):
        provider = None if client is None else FakeDataClient(fake or FakeAlpaca())
        files[name + ".json"] = encoded(source_recovery.collect(
            publication, ledger_raw, client=provider, clock=clock, dry_run=dry_run,
            observation_run_id="synthetic-" + name, previous_raw=previous))

    with mock.patch.object(market_data, "RETRY_WAIT_SECONDS", 0):
        collect("recovered", raw, ledger, fake=double("WBD"))
        collect("still-stale", raw, ledger, fake=double("WBD", stale_sessions=4))
        collect("still-missing", raw, ledger, fake=double("WBD", history=False))
        collect("arrived-not-ready", raw, ledger, fake=double("WBD", hole=datetime(2026, 10, 8).date()))
        collect("placeholder", raw, ledger, fake=double("WBD", placeholder=True))
        collect("unreadable", raw, ledger, fake=double("WBD", nan_close=True))
        collect("outage", raw, ledger, fake=double("WBD", raise_on_bars=RuntimeError("transport failed")))
        collect("refused", raw, ledger, fake=double("WBD", raise_on_bars=Refused("rejected")))
        with mock.patch.dict(os.environ, {"ALPACA_API_KEY": "", "ALPACA_SECRET_KEY": ""}):
            collect("no-credentials", raw, ledger, client=None)
        collect("window-ended", raw, ledger, fake=double("WBD"), clock=lambda: NOW.replace(hour=13, minute=30))
        collect("stale-publication", raw, ledger, fake=double("WBD"), clock=lambda: NOW.replace(hour=21, minute=30))
        collect("future-publication", raw, ledger, fake=double("WBD"),
                clock=lambda: datetime(2026, 10, 10, 7, 0, tzinfo=timezone.utc))
        collect("already-attempted", raw, ledger, fake=double("WBD"), previous=files["recovered.json"])
        collect("no-ledger", raw, None, fake=double("WBD"))
        # the page fixtures: a night with no deficit, and the thin night the smoke can load
        collect("no-deficit", page("full"), None, fake=FakeAlpaca(), clock=lambda: THIN_NOW, dry_run=True)
        collect("thin-recovered", page("thin"), None, fake=double("QAA"), clock=lambda: THIN_NOW, dry_run=True)
        collect("thin-inapplicable", page("thin"), None, fake=double("QAA"),
                clock=lambda: THIN_NOW.replace(hour=13, minute=30), dry_run=True)
        # the thin night over the naming bound: the ledger names the stock, or nothing does
        withheld = unnamed(page("thin"))
        named = ledger_for(withheld, {"stale": ["QAA"], **{k: [] for k in ("no_bars", "dropped", "unfetched_budget",
                                                                            "unfetched_failure", "refused", "gapped", "unreadable")}})
        collect("ledger-named-stale", withheld, named, fake=double("QAA"), clock=lambda: THIN_NOW, dry_run=True)
        collect("deficit-not-named", withheld, None, fake=double("QAA"), clock=lambda: THIN_NOW, dry_run=True)
        wrong = ledger_for(withheld, {"stale": ["QAB"], **{k: [] for k in ("no_bars", "dropped", "unfetched_budget",
                                                                           "unfetched_failure", "refused", "gapped", "unreadable")}})
        collect("ledger-mismatch", withheld, wrong, fake=double("QAA"), clock=lambda: THIN_NOW, dry_run=True)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = build()
    stale = []
    for name, body in files.items():
        path = TARGET / name
        if args.check:
            if not path.exists() or path.read_bytes() != body:
                stale.append(name)
        else:
            path.write_bytes(body)
    if stale:
        print("Stale source recovery fixtures: " + ", ".join(stale))
        return 1
    print(f"{len(files)} source recovery fixture files {'current' if args.check else 'written'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
