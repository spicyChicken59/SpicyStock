"""Dated research observations over the stop-research fixtures, via the real collector.

Every file is what `src.research_observations.collect` writes for a pinned
clock and a synthetic IEX snapshot double; no provider is called. The source
publications, cohort receipts and bundles are the stop-research fixtures,
read in place: the `current` publication is the immutable production capture
(October 9, applicable October 12), the others are production-shaped offline
controls. `--check` re-derives every file and refuses a stale one.
"""
import argparse
from datetime import datetime, timedelta, timezone
import gzip
import json
import os
from pathlib import Path
import sys
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src import research_observations as observations

TARGET = Path(__file__).parent
STOP = ROOT / "tests/fixtures/stop-research"
# 8:20 Chicago on the applicable session: inside the half-hour collection
# window before the 9:30 ET open, the first scheduled morning slot.
NOW = datetime(2026, 10, 12, 13, 20, tzinfo=timezone.utc)
# Synthetic single-venue prints for the two allocation-fit rows: KE's ask sits
# under its $29.23 trigger, PSNL's quote sits between its $16.26 trigger and
# $16.42 limit. Neither is a market observation.
PRICES = {"KE": (29.10, 29.14, 29.12), "PSNL": (16.28, 16.30, 16.29)}


def encoded(value):
    return json.dumps(value, allow_nan=False, indent=2).encode() + b"\n"


def quote(symbol, at, *, bid=None, ask=None):
    base_bid, base_ask, _ = PRICES[symbol]
    return {"timestamp": at, "bid_price": base_bid if bid is None else bid, "ask_price": base_ask if ask is None else ask,
            "bid_size": 100, "ask_size": 200, "bid_exchange": "V", "ask_exchange": "V", "conditions": ["R"]}


def trade(symbol, at):
    return {"timestamp": at, "price": PRICES[symbol][2], "exchange": "V", "conditions": ["@"]}


class Client:
    """The one provider call the collector makes, answered from fixed prints."""

    def __init__(self, now=NOW, *, errors=(), edit=None):
        self.requests, self.now, self.errors, self.edit = [], now, errors, edit

    def get_stock_snapshot(self, request):
        self.requests.append(request)
        feed = request.feed.value
        if feed in self.errors:
            raise RuntimeError("private credential api-key-secret")
        result = {symbol: {"latest_trade": trade(symbol, self.now - timedelta(seconds=2)),
                           "latest_quote": quote(symbol, self.now - timedelta(seconds=1))}
                  for symbol in request.symbol_or_symbols}
        if self.edit:
            self.edit(result)
        return result


def source(name):
    publication = gzip.decompress((STOP / (name + "-publication.json.gz")).read_bytes())
    return publication, (STOP / (name + "-receipt.json")).read_bytes(), (STOP / (name + "-bundle.json")).read_bytes()


def stale_and_crossed(result):
    # PSNL's print is a minute old; KE's quote is crossed (ask under bid).
    result["PSNL"]["latest_trade"]["timestamp"] = NOW - timedelta(seconds=61)
    result["KE"]["latest_quote"]["ask_price"] = result["KE"]["latest_quote"]["bid_price"] - 0.01


def build():
    current, receipt, bundle = source("current")
    red, red_receipt, red_bundle = source("red")
    outside, outside_receipt, outside_bundle = source("outside")
    files = {}

    def collect(name, publication, cohort, *, client, clock, previous=None):
        files[name + ".json"] = encoded(observations.collect(
            publication, *cohort, client=client, clock=clock, observation_run_id="synthetic-" + name, previous_raw=previous))

    collect("observed", current, (receipt, bundle), client=Client(), clock=lambda: NOW)
    collect("partial", current, (receipt, bundle), client=Client(edit=stale_and_crossed), clock=lambda: NOW)
    collect("outage", current, (receipt, bundle), client=Client(errors=("iex",)), clock=lambda: NOW)
    with mock.patch.dict(os.environ, {"ALPACA_API_KEY": "", "ALPACA_SECRET_KEY": ""}):
        collect("no-credentials", current, (receipt, bundle), client=None, clock=lambda: NOW)
    for name, at in (("before-window", NOW.replace(hour=12, minute=30)), ("expired", NOW.replace(hour=14, minute=0)),
                     ("wrong-session", NOW + timedelta(days=1))):
        collect(name, current, (receipt, bundle), client=Client(), clock=lambda at=at: at)
    collect("no-rows", red, (red_receipt, red_bundle), client=Client(), clock=lambda: NOW)
    collect("outside", outside, (outside_receipt, outside_bundle), client=Client(),
            clock=lambda: datetime(2026, 9, 11, 13, 20, tzinfo=timezone.utc))
    collect("missing-cohort", current, (None, None), client=Client(), clock=lambda: NOW)
    collect("stale-cohort", current, (red_receipt, red_bundle), client=Client(), clock=lambda: NOW)
    later = NOW + timedelta(seconds=30)
    collect("followup", current, (receipt, bundle), client=Client(later), clock=lambda: later, previous=files["observed.json"])
    # Both legs cross the boundaries by one microsecond, retaining producer
    # timestamps and replayed statuses. Offset forms represent the same instants.
    precise = NOW.replace(microsecond=123456)
    for suffix, offset in (("", timezone.utc), ("-offset", timezone(timedelta(hours=5, minutes=30)))):
        for name, age in (("age-60s", timedelta(seconds=60)), ("age-60s-plus-microsecond", timedelta(seconds=60, microseconds=1)),
                          ("future-5s", -timedelta(seconds=5)), ("future-5s-plus-microsecond", -timedelta(seconds=5, microseconds=1))):
            def change_time(result, age=age, offset=offset):
                stamp = (precise - age).astimezone(offset)
                result["KE"]["latest_quote"]["timestamp"] = stamp
                result["KE"]["latest_trade"]["timestamp"] = stamp
            collect(name + suffix, current, (receipt, bundle), client=Client(precise, edit=change_time), clock=lambda: precise)
    for name, locked_price in (("locked-zero-spread", 29.12), ("midpoint-underflow", 5e-324)):
        def locked(result, locked_price=locked_price):
            result["KE"]["latest_quote"]["bid_price"] = locked_price
            result["KE"]["latest_quote"]["ask_price"] = locked_price
        collect(name, current, (receipt, bundle), client=Client(edit=locked), clock=lambda: NOW)
    def rounded_tie(result):
        result["KE"]["latest_quote"]["bid_price"] = 100
        result["KE"]["latest_quote"]["ask_price"] = 100.02697564293588
    collect("rounded-spread-tie", current, (receipt, bundle), client=Client(edit=rounded_tie), clock=lambda: NOW)
    def large_spread(result):
        result["KE"]["latest_quote"]["bid_price"] = 100
        result["KE"]["latest_quote"]["ask_price"] = 1e15
    collect("large-dollar-spread", current, (receipt, bundle), client=Client(edit=large_spread), clock=lambda: NOW)
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
        print("Stale research observation fixtures: " + ", ".join(stale))
        return 1
    print(f"{len(files)} research observation fixture files {'current' if args.check else 'written'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
