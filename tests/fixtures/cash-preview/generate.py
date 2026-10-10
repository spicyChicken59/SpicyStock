"""Build $2,000 cash-preview browser controls through the offline producers."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest import mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src import event_risk, morning, morning_halts, provenance
from tests.fixtures.morning.generate import encoded, synthetic_feed, synthetic_registry
from tests.test_morning import Client, NOW
from tools import make_fixture

TARGET = Path(__file__).parent
ACCOUNT_FIELDS = ("equity", "risk_pct", "max_position_pct", "max_open_positions")


def events(state="empty"):
    """Use the real halt adapter over a dated synthetic COIL RSS response."""
    rss = ET.fromstring(synthetic_feed(state, NOW))
    for symbol in rss.iter(morning_halts.NAMESPACE + "IssueSymbol"):
        symbol.text = "COIL"
    body = ET.tostring(rss)

    def observe(symbols, clock, *, previous=None):
        return morning_halts.observe(symbols, clock, previous=previous,
            fetcher=lambda: {"body": body, "fetched_at": NOW.isoformat()})

    return observe


def corporate_registry():
    """An invented event narrow enough to refuse only this browser control."""
    registry = deepcopy(synthetic_registry())
    event = registry["events"][0]
    event["symbol"] = "COIL"
    event["issuer"] = "Synthetic COIL fixture issuer"
    event["id"] = "synthetic_coil_cash_event"
    quote = "Synthetic COIL cash deal used only in this offline browser fixture."
    event["reason"] = quote
    event["sources"][0]["quote"] = quote
    event["sources"][0]["sha256"] = hashlib.sha256(quote.encode()).hexdigest()
    return event_risk.validate_registry(registry)


def publication(*, multiple=False):
    original_register = make_fixture.register

    def register(fake, variant):
        symbols = original_register(fake, variant)
        if multiple:
            # Hypothetical input prices make AAPL whole-share viable under the
            # unchanged account/strategy rules; orders are still producer output.
            frame = fake.history["AAPL"].copy()
            for column in ("Open", "High", "Low", "Close"):
                frame[column] *= 0.5
            fake.history["AAPL"] = frame
        return symbols

    with tempfile.TemporaryDirectory(prefix="spicystock-cash-preview-fixture-") as temporary:
        env = {"ACCOUNT_EQUITY": "2000", "RISK_PCT": "0.5",
               "MAX_POSITION_PCT": "25", "MAX_OPEN_POSITIONS": "4",
               "GITHUB_RUN_ID_FOR_RECORD": "synthetic-cash-preview" + ("-multiple" if multiple else "")}
        # A fresh model ledger is an explicit input double, not a modification
        # of the historical $10,000 fixture's picks or published quantities.
        with mock.patch.dict(os.environ, env), mock.patch.object(make_fixture, "prior_picks",
                return_value={"schema_version": 1, "picks": []}), \
                mock.patch.object(make_fixture, "register", register):
            data = make_fixture.run_variant("full", Path(temporary))
    data.pop("fixture")
    provenance.verify(data)
    assert {k: data["account"][k] for k in ACCOUNT_FIELDS} == {
        "equity": 2000, "risk_pct": 0.5, "max_position_pct": 25, "max_open_positions": 4}
    rows = morning.admitted_rows(data)
    assert [(row["kind"], row["ticker"]) for row in rows] == (
        [("burst", "AAPL"), ("anticipation", "COIL")] if multiple else [("anticipation", "COIL")])
    planned = next(row["plan"] for row in data["watchlist"]["top"] if row["ticker"] == "COIL")
    assert (planned["shares"], planned["trigger"], planned["limit"], planned["stop"],
            planned["position_usd"], planned["risk_usd"]) == (4, 110.61, 111.72, 109.50, 446.88, 8.88)
    if multiple:
        planned = next(row["plan"] for row in data["bursts"] if row["ticker"] == "AAPL")
        assert (planned["shares"], planned["entry_ref"], planned["limit"], planned["stop"],
                planned["position_usd"], planned["risk_usd"]) == (1, 62.10, 63.22, 60.70, 63.22, 2.52)
        assert data["cash_budget"]["committed_usd"] == 510.10
    return encoded(data)


def build():
    raw = publication()
    files = {"publication.json": raw}
    for name, observer in (("observed", events()), ("halted", events("halted"))):
        receipt = morning.collect(raw, client=Client(), clock=lambda: NOW,
            event_observer=observer, observation_run_id="synthetic-cash-preview-" + name)
        files[name + ".json"] = encoded(receipt)
    with mock.patch.object(event_risk, "REGISTRY", corporate_registry()):
        receipt = morning.collect(raw, client=Client(), clock=lambda: NOW,
            event_observer=events(), observation_run_id="synthetic-cash-preview-corporate-excluded")
        files["corporate-excluded.json"] = encoded(receipt)
    multiple = publication(multiple=True)
    files["publication-multiple.json"] = multiple
    files["observed-multiple.json"] = encoded(morning.collect(multiple, client=Client(), clock=lambda: NOW,
        event_observer=events(), observation_run_id="synthetic-cash-preview-observed-multiple"))
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    files = build()
    for name, body in files.items():
        path = TARGET / name
        if args.check:
            if not path.is_file() or path.read_bytes() != body:
                stale.append(name)
        else:
            path.write_bytes(body)
    if stale:
        print("Stale cash-preview fixtures: " + ", ".join(stale))
        return 1
    print(str(len(files)) + " cash-preview fixture files " + ("current" if args.check else "written"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
