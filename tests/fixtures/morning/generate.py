"""Build synthetic browser observations via the real offline pipeline and collector."""
import argparse
from datetime import datetime, timedelta, timezone
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

from src import event_risk, morning, morning_halts
from tests.test_morning import Client, NOW
from tools.make_fixture import run_variant

TARGET = Path(__file__).parent


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def synthetic_feed(state, now=NOW):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "pubDate").text = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    ET.SubElement(channel, morning_halts.NAMESPACE + "numItems").text = "0" if state == "empty" else "1"
    if state != "empty":
        item = ET.SubElement(channel, "item")
        fields = {"HaltDate": "09/11/2026", "HaltTime": "09:33:00", "IssueSymbol": "AAPL",
                  "IssueName": "SYNTHETIC BROWSER TEST ONLY", "Market": "NYSE", "ReasonCode": "T1",
                  "ResumptionDate": "09/11/2026" if state == "resumed" else "",
                  "ResumptionQuoteTime": "09:34:00" if state == "resumed" else "",
                  "ResumptionTradeTime": "09:34:30" if state == "resumed" else ""}
        for key, value in fields.items():
            ET.SubElement(item, morning_halts.NAMESPACE + key).text = value
    return ET.tostring(rss)


def events(state="empty", now=NOW):
    def observe(symbols, clock, *, previous=None):
        return morning_halts.observe(symbols, clock, previous=previous,
                                     fetcher=lambda: {"body": synthetic_feed(state, now), "fetched_at": now.isoformat()})
    return observe


def synthetic_registry():
    quote = "Synthetic AAPL cash deal used only in this offline browser fixture."
    source = {"title": "Synthetic event fixture", "quote": quote, "url": "https://example.invalid/synthetic-event",
              "sha256": hashlib.sha256(quote.encode()).hexdigest(), "published_on": "2026-09-10"}
    return {"version": 1, "coverage": event_risk.COVERAGE, "reviewed_on": "2026-09-11",
            "coverage_note": "Synthetic browser fixture; not a real corporate event.",
            "events": [{"id": "synthetic_cash_event", "symbol": "AAPL", "issuer": "Synthetic fixture issuer",
                        "kind": "cash_acquisition", "announced_on": "2026-09-10", "active_from": "2026-09-10",
                        "evidence_as_of": "2026-09-10", "reviewed_on": "2026-09-11", "review_due": "2026-09-12",
                        "reason": quote, "sources": [source]}]}


def build():
    files = {}
    with tempfile.TemporaryDirectory() as temporary:
        for variant in ("full", "red"):
            with mock.patch.dict(os.environ, {"GITHUB_RUN_ID_FOR_RECORD": "synthetic-morning-" + variant}):
                data = run_variant(variant, Path(temporary) / variant)
            data.pop("fixture")
            files[variant + "-publication.json"] = encoded(data)
    full, red = files["full-publication.json"], files["red-publication.json"]
    for name, raw, client, observer in (
        ("observed", full, Client(), events()), ("outage", full, Client(errors=("iex", "delayed_sip")), events()),
        ("no-tickets", red, Client(), events()), ("halted", full, Client(), events("halted")),
    ):
        files[name + ".json"] = encoded(morning.collect(raw, client=client, clock=lambda: NOW,
                                          event_observer=observer, observation_run_id="synthetic-" + name))
    later = NOW + timedelta(seconds=30)
    files["resumed.json"] = encoded(morning.collect(full, client=Client(), clock=lambda: later,
                                     event_observer=events("resumed", later), observation_run_id="synthetic-resumed",
                                     previous_raw=files["halted.json"]))
    with mock.patch.object(event_risk, "REGISTRY", event_risk.validate_registry(synthetic_registry())):
        files["corporate-excluded.json"] = encoded(morning.collect(full, client=Client(), clock=lambda: NOW,
                                      event_observer=events(), observation_run_id="synthetic-corporate-excluded"))
    files["corporate-retained.json"] = encoded(morning.collect(full, client=Client(), clock=lambda: later,
                                  event_observer=events(now=later), observation_run_id="synthetic-corporate-retained",
                                  previous_raw=files["corporate-excluded.json"]))
    resolved = synthetic_registry()
    resolution = {**resolved["events"][0]["sources"][0], "published_on": "2026-09-11",
                  "title": "Synthetic explicit resolution", "quote": "The synthetic fixture deal ended; test only."}
    resolution["sha256"] = hashlib.sha256(resolution["quote"].encode()).hexdigest()
    resolved["events"][0].update(active_until="2026-09-11", resolution=resolution)
    with mock.patch.object(event_risk, "REGISTRY", event_risk.validate_registry(resolved)):
        files["corporate-resolved.json"] = encoded(morning.collect(full, client=Client(), clock=lambda: later,
                                 event_observer=events(now=later), observation_run_id="synthetic-corporate-resolved",
                                 previous_raw=files["corporate-excluded.json"]))
    carried_at = NOW + timedelta(seconds=45)
    files["corporate-resolution-carried.json"] = encoded(morning.collect(full, client=Client(), clock=lambda: carried_at,
                                  event_observer=events(now=carried_at), observation_run_id="synthetic-corporate-resolution-carried",
                                  previous_raw=files["corporate-resolved.json"]))
    capture = TARGET.parent / "morning_halts"
    metadata = json.loads((capture / "capture.json").read_bytes())
    now = datetime(2026, 10, 9, 15, 26, 22, tzinfo=timezone.utc)
    files["qeta-captured.json"] = encoded(morning_halts.observe(["QETA"], now, fetcher=lambda: {
        "body": (capture / "nasdaq-current.xml").read_bytes(), "fetched_at": metadata["captured_at"],
        "http_date": metadata["http_date"]}))
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
        print("Stale morning fixtures: " + ", ".join(stale))
        return 1
    print(f"{len(files)} morning fixture files {'current' if args.check else 'written'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
