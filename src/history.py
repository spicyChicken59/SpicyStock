"""Bounded public signal recovery and observation coverage. No network or private inputs.

The catalog contains only published v2 records. It is independent of model picks
and browser saves. Evidence is lazy, immutable and addressed by source Git blob.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
import logging
import math
from pathlib import Path
import re

DAYS = 21
OBSERVATIONS_MAX = 20
RECORDS_MAX = 84
SIGNALS_MAX = 10000
CATALOG_BYTES_MAX = 128 * 1024 * 1024
CATALOG_WARN_FRACTION = 0.8  # of either cap: the run log warns past it
SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9.-]{0,15}\Z")
log = logging.getLogger("spicystock.history")


def encoded(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def rows(data):
    for row in data.get("bursts", []):
        yield "burst", row, False
    seen = set()
    wl = data.get("watchlist", {})
    for quiet, key in [(False, "top"), (True, "also_quiet")]:
        for row in wl.get(key, []):
            if row["ticker"] not in seen:
                yield "anticipation", row, quiet
                seen.add(row["ticker"])


def signals(data):
    session = data["run"]["session"]
    rules = data["app"]["rules_version"]
    return {f"{kind}:{r['ticker']}:{session}:{rules}": {
        "ticker": r["ticker"], "session": session, "kind": kind, "rules_version": rules
    } for kind, r, _ in rows(data)}


def valid_bar(row):
    try:
        date.fromisoformat(row["date"])
        return isinstance(row["c"], (int, float)) and not isinstance(row["c"], bool) and math.isfinite(row["c"]) and row["c"] > 0
    except (ValueError, TypeError, KeyError):
        return False


def observe(frames, previous, current_signals, session, series_of, extra_symbols=()):
    """Up to 20 real dated bars, covering every public signal's own 21-day window.

    A repeated ticker gets a NEW identity/window. Its older signals keep their
    own dates. Missing frames retain prior real bars; no bars are interpolated.
    """
    prior = (previous or {}).get("observations", {})
    prior = prior if isinstance(prior, dict) else {}
    saved_signals = prior.get("signals", {})
    retained = dict(saved_signals) if isinstance(saved_signals, dict) else {}
    # Upgrade coverage from the actual previous published candidates, not picks.
    if previous and previous.get("app", {}).get("schema") == 2:
        retained.update(signals(previous))
    elif previous and previous.get("run", {}).get("session") and previous.get("app", {}).get("rules_version"):
        retained.update(signals(previous))
    retained.update(current_signals)
    def eligible(sig):
        try:
            return (isinstance(sig, dict) and isinstance(sig.get("ticker"), str)
                    and SYMBOL.fullmatch(sig["ticker"]) and sig.get("kind") in {"burst", "anticipation"}
                    and isinstance(sig.get("rules_version"), str)
                    and 0 <= (session - date.fromisoformat(sig["session"])).days <= DAYS)
        except (ValueError, KeyError, TypeError):
            return False
    retained = {key: dict(sig) for key, sig in retained.items() if eligible(sig)}
    by_symbol = {}
    for key, sig in retained.items():
        by_symbol.setdefault(sig["ticker"], []).append((key, sig))
    old_symbols = prior.get("symbols", {})
    old_symbols = old_symbols if isinstance(old_symbols, dict) else {}
    for sym in extra_symbols:
        by_symbol.setdefault(sym, [])
    # Read older v2 observations during transition, with their actual since date.
    for sym, old in old_symbols.items():
        try:
            if 0 <= (session - date.fromisoformat(old["since"])).days <= DAYS:
                by_symbol.setdefault(sym, [])
        except (ValueError, KeyError, TypeError):
            pass
    out = {}
    for sym, identities in sorted(by_symbol.items()):
        old = old_symbols.get(sym, {})
        old = old if isinstance(old, dict) else {}
        dates = [sig["session"] for _, sig in identities]
        since = min(dates) if dates else old.get("since", session.isoformat())
        cutoff = max(since, (session - timedelta(days=DAYS)).isoformat())
        bars = {b["date"]: dict(b) for b in (old.get("history") if isinstance(old.get("history"), list) else [old]) if valid_bar(b) and cutoff <= b["date"] <= session.isoformat()}
        df = frames.get(sym)
        fetched = series_of(df, OBSERVATIONS_MAX + DAYS) if df is not None and len(df) else []
        for b in fetched:
            if valid_bar(b) and cutoff <= b["date"] <= session.isoformat():
                was = bars.get(b["date"])
                new = dict(b, from_session=session.isoformat(), source="public observation history")
                if was and was["c"] != b["c"]:
                    new.update(revised=True, revised_from={"c": was["c"], "from_session": was.get("from_session")})
                elif was and was.get("revised"):
                    new.update(revised=True, revised_from=was.get("revised_from"))
                bars[b["date"]] = new
        history = [bars[d] for d in sorted(bars)[-OBSERVATIONS_MAX:]]
        if history:
            latest = history[-1]
            out[sym] = {k: latest.get(k) for k in ("date", "o", "h", "l", "c", "v")}
            out[sym].update(since=since, history=history)
        for _, sig in identities:
            sig["coverage"] = "observed" if history and history[-1]["date"] == session.isoformat() else "no_new_bar" if history else "no_available_bar"
    return {"as_of": session.isoformat(), "days": DAYS, "symbols": out, "signals": retained, "history_max": OBSERVATIONS_MAX}


def publish(raw, root, *, source_commit=None):
    """Append one authentic publication, then prune only owned catalog files.

    Refuse malformed/oversized input before replacing the index. A changed
    publication is a separate source even on the same signal date/rules.

    Past either cap (``RECORDS_MAX`` records, ``CATALOG_BYTES_MAX`` bytes) the
    records still inside their window give way, oldest session first, then
    the earlier publication, then the digest, until tonight's fits; tonight's
    record never does. Of the caps, only tonight's record alone past the byte
    cap refuses; the evidence and identity checks above refuse as before. Each
    refusal leaves the existing index and every file as they were. An evicted
    record's originals stay in git; the page reads it as unavailable, as it
    does an expired one.
    """
    data = json.loads(raw)
    if data.get("fixture") or data.get("app", {}).get("version") != "2.0":
        raise ValueError("only published v2 records belong in recovery")
    session = data["run"]["session"]
    date.fromisoformat(session)
    rules = data["app"]["rules_version"]
    if not re.fullmatch(r"[a-f0-9]{12}", rules):
        raise ValueError("invalid rules identity")
    candidates = list(rows(data))
    if len(candidates) > SIGNALS_MAX:
        raise ValueError("recovery signal bound exceeded")
    root = Path(root)
    old = json.loads((root / "index.json").read_bytes()) if (root / "index.json").exists() else {"records": {}, "entries": []}
    source = git_blob(raw)
    as_of = max(session, old.get("as_of", session))
    cutoff = (date.fromisoformat(as_of) - timedelta(days=DAYS)).isoformat()
    records = {k: v for k, v in old["records"].items() if cutoff <= v["session"] <= as_of}
    entries = [e for e in old["entries"] if e["source"] in records and e["source"] != source]
    if session < cutoff:
        return old
    provenance = {"record_id": source, "git_blob": source, "commit": source_commit or old["records"].get(source, {}).get("commit"),
                  "session": session, "published_at": data["run"].get("published_at"),
                  "rules_version": rules, "run_id": data["run"].get("run_id")}
    records[source] = provenance
    context = {k: deepcopy(data.get(k, {})) for k in ["app", "run", "rules", "breadth", "cash_budget"]}
    if data.get("run", {}).get("evidence"):
        context["account"] = deepcopy(data["account"])
        context["evidence_candidates"] = [[kind, row["ticker"], quiet] for kind, row, quiet in candidates]
    context["trades"] = data.get("trades", [])
    context["provenance"] = provenance
    files = {f"{source}/record.json": encoded(context)}
    if len(files[f"{source}/record.json"]) > 256 * 1024:
        raise ValueError("recovery context bound exceeded")
    existing_context = root / source / "record.json"
    if existing_context.exists():
        files[f"{source}/record.json"] = existing_context.read_bytes()
    provenance["context_sha256"] = hashlib.sha256(files[f"{source}/record.json"]).hexdigest()
    for kind, row, quiet in candidates:
        ticker = row["ticker"]
        if not SYMBOL.fullmatch(ticker):
            raise ValueError("unsafe signal symbol")
        row = deepcopy(row)
        series = row.get("series", [])
        if len(series) > 120 or any(not valid_bar(b) or b["date"] > session for b in series):
            raise ValueError("invalid original evidence")
        name = f"{source}/{kind}-{ticker}.json"
        evidence = encoded({"kind": kind, "quiet": quiet, "row": row, "source": source})
        if len(evidence) > 256 * 1024:
            raise ValueError("original evidence bound exceeded")
        files[name] = evidence
        entries.append({"ticker": ticker, "kind": kind, "grade": row.get("grade"), "rank": row.get("rank"),
                        "scan": row.get("scan"), "source": source, "path": name,
                        "sha256": hashlib.sha256(evidence).hexdigest(), "chart": bool(series)})
        if row.get("evidence"):
            entries[-1]["evidence_id"] = row["evidence"]["id"]
    kept_bytes = {k: sum(p.stat().st_size for p in (root / k).glob('*') if p.is_file()) for k in records if k != source}
    oldest_first = sorted(kept_bytes, key=lambda k: (records[k]["session"], records[k].get("published_at") or "", k))
    evicted = []
    while True:
        entries = [e for e in entries if e["source"] in records]
        index = {"version": 1, "as_of": as_of, "days": DAYS, "records_max": RECORDS_MAX,
                 "dates": sorted({v["session"] for v in records.values()}), "records": records,
                 "entries": sorted(entries, key=lambda e: (records[e["source"]]["session"], e["ticker"], e["source"]), reverse=True)}
        files["index.json"] = encoded(index)
        size = sum(kept_bytes[k] for k in records if k != source) + sum(map(len, files.values()))
        if len(records) <= RECORDS_MAX and size <= CATALOG_BYTES_MAX:
            break
        if not oldest_first:
            raise ValueError("recovery byte bound exceeded; existing index left intact")
        gone = oldest_first.pop(0)
        evicted.append(records.pop(gone)["session"])
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and name != "index.json" and path.read_bytes() != body:
            # A later importer may know a commit the publication did not yet
            # know. Keep immutable context; index carries added provenance.
            if name.endswith('/record.json'):
                continue
            raise ValueError("attempt to replace immutable evidence")
        temp = path.with_suffix('.tmp')
        temp.write_bytes(body)
        temp.replace(path)
    # Only source IDs formerly owned by our index can be pruned. Every file in
    # such a directory is the catalog's own (an interrupted write leaves a .tmp),
    # a directory already gone is already pruned, and one that cannot be removed
    # is named without stopping the others.
    stranded = []
    for expired in sorted(set(old["records"]) - set(records)):
        if not re.fullmatch(r"[a-f0-9]{40}", expired):
            continue
        folder = root / expired
        try:
            if folder.is_symlink():
                folder.unlink()
            elif folder.is_dir():
                for p in folder.iterdir():
                    if p.is_symlink() or not p.is_dir():
                        p.unlink()
                folder.rmdir()
        except OSError:
            stranded.append(expired)
    _log_catalog(index, size, evicted, stranded)
    return index


def _log_catalog(index, size, evicted, stranded=()):
    """State the catalog against both caps, once a night; never raises."""
    try:
        if stranded:
            one = len(stranded) == 1
            log.warning("Recovery catalog: %d record %s could not be removed (%s); %s no longer catalogued.",
                        len(stranded), "directory" if one else "directories", ", ".join(stranded),
                        "it is" if one else "they are")
        if evicted:
            one = len(evicted) == 1
            log.warning("Recovery catalog: %d %s inside %s %d-day window %s removed, oldest first (%s), "
                        "so tonight's fits the caps of %d records and %d bytes; %s originals stay in git.",
                        len(evicted), "record" if one else "records", "its" if one else "their", DAYS,
                        "was" if one else "were", ", ".join(evicted), RECORDS_MAX, CATALOG_BYTES_MAX,
                        "its" if one else "their")
        records, sessions = len(index["records"]), len(index["dates"])
        full = size > CATALOG_BYTES_MAX * CATALOG_WARN_FRACTION or records > RECORDS_MAX * CATALOG_WARN_FRACTION
        log.log(logging.WARNING if full else logging.INFO,
                "Recovery catalog: %d of %d records over %d %s, %d of %d bytes.", records, RECORDS_MAX,
                sessions, "session" if sessions == 1 else "sessions", size, CATALOG_BYTES_MAX)
    except Exception as exc:  # noqa: BLE001 -- a log line never fails the night
        log.warning("Recovery catalog could not be stated (%s).", type(exc).__name__)
