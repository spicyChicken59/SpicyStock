"""Freeze the 17 November 2026 model record: the picks, the bars and the minute evidence its scorecard walked.

Read-only over git at one pinned commit (`THROUGH`), so a later publication
never makes the file stale:

- the 22 retained picks (`docs/picks.json`), whole, so each still passes
  `record.pick_problem()` with its own evidence reference;
- for each pick, the daily bars of its five sessions as the publications
  carried them in `observations`: the 17 November record's own where it still
  holds them, else the newest earlier publication that holds all of them
  (MG, SN and ZIM of 8 and 9 October), each source commit named;
- the five retained minute objects (`docs/intraday/`), whole;
- the record's session, context digest, account and scorecard;
- the quality ledger's outcome rows for that publication (bucket, status, R,
  whether it filled, the uncertainty, the last bar and the minute object),
  and, for every session a pick was issued in, each ledger entry's
  publication stamp and the rows that carry an evidence id and a ticket gate.

The file is what `tests/test_model_record.py` reads; it needs the full
history to rebuild, so no test runs this.

    python tests/fixtures/model-record/build.py [--check]
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from datetime import date
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src import record                                    # noqa: E402
from src import sessions as exchange_sessions             # noqa: E402

OUT = Path(__file__).resolve().with_name("record-2026-11-17.json.gz")
THROUGH = "0e1a3e107b55556539b2d9198df5d75790bab649"


def git(*args, text=True):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=text, check=True).stdout


def bars_of(data, ticker):
    seen = (data.get("observations") or {}).get("symbols", {}).get(ticker) or {}
    out = {}
    for bar in [*(seen.get("history") or []), seen]:
        if isinstance(bar.get("date"), str) and all(isinstance(bar.get(k), (int, float)) for k in "ohlc"):
            out[bar["date"]] = {k: bar[k] for k in ("date", "o", "h", "l", "c")}
    return out


def build():
    commits = git("log", "--format=%H", THROUGH, "--", "docs/data.json").split()
    cache = {}

    def data_at(commit):
        if commit not in cache:
            try:
                cache[commit] = json.loads(git("show", f"{commit}:docs/data.json", text=False))
            except (subprocess.CalledProcessError, ValueError):
                cache[commit] = {}
        return cache[commit]

    raw = git("show", f"{THROUGH}:docs/data.json", text=False)
    data = json.loads(raw)
    session = data["run"]["session"]
    picks_raw = git("show", f"{THROUGH}:docs/picks.json", text=False)
    picks = json.loads(picks_raw)["picks"]
    bars = {}
    for pick in picks:
        horizon = [str(d) for d in exchange_sessions.next_sessions(date.fromisoformat(pick["date"]),
                                                                   record.OPEN_PLAN_SESSIONS)]
        need = [d for d in horizon if d <= session]
        for commit in commits:                       # newest first: the nearest account of those sessions
            got = bars_of(data_at(commit), pick["ticker"]) if isinstance(data_at(commit), dict) else {}
            if all(d in got for d in need):
                entry = bars.setdefault(pick["ticker"], {"rows": {}, "from": {}})
                for d in need:
                    entry["rows"].setdefault(d, got[d])
                    entry["from"].setdefault(d, commit)
                break
        else:
            raise SystemExit(f"no publication carries {pick['ticker']}'s bars for {need}")
    minutes = {}
    for name in git("ls-tree", "--name-only", THROUGH, "docs/intraday/").split():
        obj = json.loads(git("show", f"{THROUGH}:{name}", text=False))
        minutes[obj["key"]] = obj
    name = hashlib.sha256(raw).hexdigest()
    sessions_issued = {p["date"] for p in picks}
    tickers = {p["ticker"] for p in picks}
    outcome, entries = None, []
    for path in git("ls-tree", "--name-only", THROUGH, "docs/quality-ledger/v1/").split():
        entry = json.loads(gzip.decompress(git("show", f"{THROUGH}:{path}", text=False)))
        pub = entry["publication"]
        if pub["sha256"] == name:
            outcome = [{k: r.get(k) for k in ("ticker", "kind", "picked", "bucket", "status", "r", "filled",
                                              "uncertainty", "through", "minute_evidence") if k in r}
                       for r in entry["outcome"]["rows"]]
        if pub["session"] in sessions_issued:
            def rows(items, keep_all):
                return [{"ticker": r["ticker"], "evidence_id": r.get("evidence_id"),
                         "gate": {k: (r.get("gate") or {}).get(k) for k in ("ticket", "reason")}}
                        for r in items if keep_all or (r.get("gate") or {}).get("ticket") or r["ticker"] in tickers]
            entries.append({"publication": {k: pub[k] for k in ("session", "published_at", "sha256")},
                            "signal": {"candidates": rows(entry["signal"]["candidates"], False),
                                       "anticipation": rows(entry["signal"]["anticipation"], True)}})
    entries.sort(key=lambda e: (e["publication"]["published_at"], e["publication"]["sha256"]))
    return {
        "through": THROUGH,
        "source": {"data_sha256": name, "picks_sha256": hashlib.sha256(picks_raw).hexdigest()},
        "data": {"run": {"session": session, "evidence": data["run"]["evidence"]},
                 "account": {k: data["account"][k] for k in ("equity", "risk_pct")},
                 "scorecard": data["scorecard"]},
        "picks": picks,
        "bars": {t: {"rows": [e["rows"][d] for d in sorted(e["rows"])],
                     "from": {d: e["from"][d][:8] for d in sorted(e["from"])}} for t, e in sorted(bars.items())},
        "minutes": {k: minutes[k] for k in sorted(minutes)},
        "ledger_rows": outcome,
        "ledger_entries": entries,
    }


def encoded(fixture):
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as handle:
        handle.write((json.dumps(fixture, sort_keys=True, separators=(",", ":")) + "\n").encode())
    return buffer.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = encoded(build())
    if args.check:
        if not OUT.exists() or OUT.read_bytes() != data:
            raise SystemExit(f"{OUT.name} is not what git at {THROUGH[:8]} gives")
        print(f"{OUT.name} current")
        return
    OUT.write_bytes(data)
    print(f"{OUT.name}: {len(data)} bytes")


if __name__ == "__main__":
    main()
