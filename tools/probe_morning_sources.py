"""A fixed-symbol transport diagnostic, never a publication or entry check.

This uses the collector's feed adapter and normalizers with SPY only. The
result has no publication binding, plan, order or candidate status and must
remain outside docs/. It verifies transport even when no ticket is admitted.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from src import market_data, morning, sessions

SYMBOL = "SPY"
PUBLIC_ROOT = Path(__file__).resolve().parents[1] / "docs"


def probe(*, client=None, clock=None):
    clock = clock or (lambda: datetime.now(timezone.utc))
    started = clock()
    day = sessions.market_time(started).date()
    previous = sessions.previous_session(day).isoformat()
    client = client or market_data.get_clients()
    responses, sources = {}, {}
    for feed in ("iex", "delayed_sip"):
        responses[feed], sources[feed] = morning._fetch(client, [SYMBOL], feed, clock)
    completed = clock()
    if completed < started:
        raise ValueError("diagnostic clock moved backwards")
    live = responses["iex"].get(SYMBOL)
    delayed = responses["delayed_sip"].get(SYMBOL)
    return {
        "schema": "spicystock-source-probe-v1", "purpose": "transport_diagnostic_only",
        "symbol": SYMBOL, "collection_started_at": started.isoformat(),
        "generated_at": completed.isoformat(), "sources": sources,
        "trade": morning.trade_observation(morning._get(live, "latest_trade"), completed,
                                             day.isoformat(), sources["iex"]["status"] == "ok",
                                             observed_at=morning._instant(sources["iex"]["checked_at"])),
        "quote": morning.quote_observation(morning._get(live, "latest_quote"), completed,
                                             day.isoformat(), sources["iex"]["status"] == "ok",
                                             observed_at=morning._instant(sources["iex"]["checked_at"])),
        "delayed_volume": morning.volume_observation(delayed, completed, day.isoformat(),
                                                       previous, sources["delayed_sip"]["status"] == "ok",
                                                       observed_at=morning._instant(sources["delayed_sip"]["checked_at"])),
        "limits": ["not_a_candidate_or_ticket", "not_an_entry_check", "never_publish_to_site"],
    }


def write_probe(output: Path, result: dict):
    output = output.resolve()
    if output == PUBLIC_ROOT or PUBLIC_ROOT in output.parents:
        raise ValueError("diagnostics cannot be written into public docs")
    payload = json.dumps(result, allow_nan=False, indent=2) + "\n"
    # A diagnostic must not replace an existing observation or user file.
    with output.open("x", encoding="utf-8") as handle:
        handle.write(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = probe()
        write_probe(args.output, result)
    except Exception:
        # SDK exceptions can include request details; retain only a fixed error.
        print("Morning source diagnostic failed; no raw provider error was logged.")
        return 1
    print("Morning source diagnostic retained outside the public site.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
