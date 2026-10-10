"""Build browser observations from frozen pipeline inputs and the real collector."""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
from unittest import mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src import event_risk, morning, morning_halts
from tests.test_morning import Client, NOW

TARGET = Path(__file__).parent
ARCHIVED_PUBLICATIONS = {
    "full": "9e34f06249d04c55a2480695a29d6e4dfaa620f16fe1de0041883f47784bc44f",
    "red": "7495f4172806974cbb34a1c4582dd85b693bdab2c235b744cb794ebfdf373489",
}


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


def build_receipts(full, red, *, legacy=False):
    files = {}

    def receipt(raw, **kwargs):
        value = morning.collect(raw, **kwargs)
        if legacy:
            # Freeze the original fixture contract without a production switch.
            # Removing only the transport extension reproduces the original
            # receipt bytes; all canonical identity and prior-byte CAS remain.
            del value["publication"]["reader_projection_version"]
            del value["publication"]["reader_sha256"]
            morning.validate_observation(value, raw, previous_raw=kwargs.get("previous_raw"),
                                         require_continuity=True)
        return encoded(value)

    for name, raw, client, observer in (
        ("observed", full, Client(), events()), ("outage", full, Client(errors=("iex", "delayed_sip")), events()),
        ("no-tickets", red, Client(), events()), ("halted", full, Client(), events("halted")),
    ):
        files[name + ".json"] = receipt(raw, client=client, clock=lambda: NOW,
                                          event_observer=observer, observation_run_id="synthetic-" + name)
    later = NOW + timedelta(seconds=30)
    files["resumed.json"] = receipt(full, client=Client(), clock=lambda: later,
                                     event_observer=events("resumed", later), observation_run_id="synthetic-resumed",
                                     previous_raw=files["halted.json"])
    with mock.patch.object(event_risk, "REGISTRY", event_risk.validate_registry(synthetic_registry())):
        files["corporate-excluded.json"] = receipt(full, client=Client(), clock=lambda: NOW,
                                      event_observer=events(), observation_run_id="synthetic-corporate-excluded")
    files["corporate-retained.json"] = receipt(full, client=Client(), clock=lambda: later,
                                  event_observer=events(now=later), observation_run_id="synthetic-corporate-retained",
                                  previous_raw=files["corporate-excluded.json"])
    resolved = synthetic_registry()
    resolution = {**resolved["events"][0]["sources"][0], "published_on": "2026-09-11",
                  "title": "Synthetic explicit resolution", "quote": "The synthetic fixture deal ended; test only."}
    resolution["sha256"] = hashlib.sha256(resolution["quote"].encode()).hexdigest()
    resolved["events"][0].update(active_until="2026-09-11", resolution=resolution)
    with mock.patch.object(event_risk, "REGISTRY", event_risk.validate_registry(resolved)):
        files["corporate-resolved.json"] = receipt(full, client=Client(), clock=lambda: later,
                                 event_observer=events(now=later), observation_run_id="synthetic-corporate-resolved",
                                 previous_raw=files["corporate-excluded.json"])
    carried_at = NOW + timedelta(seconds=45)
    files["corporate-resolution-carried.json"] = receipt(full, client=Client(), clock=lambda: carried_at,
                                  event_observer=events(now=carried_at), observation_run_id="synthetic-corporate-resolution-carried",
                                  previous_raw=files["corporate-resolved.json"])
    return files


def build():
    # These exact publications were produced by the prior real pipeline and
    # now serve as immutable migration inputs. Today's pipeline remains
    # exercised separately by page fixtures; it cannot recreate old code.
    inputs = {}
    for name, digest in ARCHIVED_PUBLICATIONS.items():
        raw = (TARGET / (name + "-publication.json")).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Archived morning publication bytes changed: " + name)
        inputs[name] = raw
    authority = json.loads(inputs["full"])["rules"]["event_risk"]
    if json.loads(inputs["red"])["rules"]["event_risk"] != authority:
        raise ValueError("Archived morning event authorities differ")
    registry = event_risk.validate_registry(deepcopy(authority["registry"]))
    if event_risk.registry_digest(registry) != authority["registry_sha256"]:
        raise ValueError("Archived morning event registry digest differs")
    rules = {"event_risk." + key: deepcopy(value) for key, value in authority.items()}
    with mock.patch.object(event_risk, "REGISTRY", registry), mock.patch.object(event_risk, "RULES", rules):
        return _build(inputs["full"], inputs["red"])


def _build(full, red):
    files = {}
    files.update(build_receipts(full, red, legacy=True))
    files.update({"reader-" + name: body for name, body in build_receipts(full, red).items()})
    from tests.test_morning import event_outage
    outage_at = NOW + timedelta(seconds=30)
    files["reader-halt-outage.json"] = encoded(morning.collect(
        full, client=Client(errors=("iex", "delayed_sip")), clock=lambda: outage_at,
        event_observer=event_outage, observation_run_id="synthetic-reader-halt-outage",
        previous_raw=files["halted.json"]))
    resumed_at = NOW + timedelta(seconds=45)
    files["reader-halt-recovered.json"] = encoded(morning.collect(
        full, client=Client(), clock=lambda: resumed_at,
        event_observer=events("resumed", resumed_at), observation_run_id="synthetic-reader-halt-recovered",
        previous_raw=files["reader-halt-outage.json"]))
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
