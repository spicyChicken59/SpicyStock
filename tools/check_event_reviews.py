#!/usr/bin/env python3
"""Refuse a manual event registry whose review has lapsed without a note.

Every unresolved entry of ``knowledge/event-risk.json`` carries a
``review_due``. Past it the entry still withholds every new ticket
(``event_risk.classify()`` reads it as overdue), and nothing says whether
anyone looked. This exits 1, naming each such entry, until the entry is
reviewed again (a new ``reviewed_on`` and ``review_due``) or carries a
``review_note`` dated after its due date saying why it stands as it is.

It reads today's date in New York, so it is the one check in CI whose answer
moves with the calendar, on purpose: the day after a review falls due, every
pull request is red until the registry is reviewed. ``--today`` pins it for a
test or a rehearsal.

    python tools/check_event_reviews.py
    python tools/check_event_reviews.py --today 2026-11-26
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import event_risk  # noqa: E402

MARKET_TZ = ZoneInfo("America/New_York")


def main(argv=None, now=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--registry", type=Path, default=event_risk.REGISTRY_PATH)
    parser.add_argument("--today", default=None, help="YYYY-MM-DD; defaults to today in New York")
    args = parser.parse_args(argv)
    today = args.today or (now or datetime.now(timezone.utc)).astimezone(MARKET_TZ).date().isoformat()
    try:
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        lapsed = event_risk.lapsed_reviews(registry, today)
    except (OSError, ValueError) as exc:
        print(f"refused: the event registry cannot be read: {exc}", file=sys.stderr)
        return 2
    if lapsed:
        due = {e["symbol"]: e["review_due"] for e in registry["events"]}
        print(f"lapsed on {today}: " + "; ".join(f"{s} (review due {due[s]})" for s in lapsed)
              + ". Review each entry again, or add a review_note dated after its due date.", file=sys.stderr)
        return 1
    overdue = [e["symbol"] for e in registry["events"] if e.get("active_until") is None and e["review_due"] < today]
    print(f"current on {today}: no unresolved entry's review has lapsed without a note"
          + (f" ({', '.join(overdue)} overdue, each with its note)" if overdue else "") + ".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
