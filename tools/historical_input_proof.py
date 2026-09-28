"""Socket-blocked audit of the two retained publications and acquisition freeze.

No provider/model clients, production invocation, or new raw-data retention.
Run: python tools/historical_input_proof.py --output <evidence-directory>
The manifest is written before the retained-value reconciliation. A later
acquisition must preserve its byte hash; asof is mapping, never data vintage.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date
import gzip
import hashlib
import importlib.metadata
import json
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
VERSION = "historical-input-proof-v1"
EVIDENCE = ROOT / "docs/input-truthfulness/2026-09-28-evidence"
REFERENCES = {
    "2026-09-24": {
        "publication_commit": "6822dddd14d0a541083e7caaecca9c945b451af2",
        "publication_sha256": "97da76d4f0eae671a5168760b79852c2eb6c4539bef3a144df6ef6bfe20c93f4",
        "execution_revision": "470c358c06bc9c997184d829c63845c4db0dc4f5",
        "run_id": "36077970591", "evening_artifact": "10841015914",
        "exception_artifact": "10841205634", "intended": 4779,
        "ready": 4763, "stale": 16,
    },
    "2026-09-25": {
        "publication_commit": "8be007f68deaa417b85a512d2e16a37899d27011",
        "publication_sha256": "37255a5457472d47452ea326e6b6b84cec2d6bd1da07ab391e173daf73a62ce5",
        "execution_revision": "e1359495ad267365dae9b6d03712fe7f17dc70cb",
        "run_id": "36205470985", "evening_artifact": "10893835913",
        "exception_artifact": "10893820885", "intended": 4780,
        "ready": 4758, "stale": 22,
    },
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = encoded(value)
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == ".gz" else raw)


def symbol_hash(symbols):
    """Full canonical membership; final LF is part of the new manifest identity."""
    return sha(("\n".join(sorted(set(symbols))) + "\n").encode())


def full_population(obj):
    """Reject a displayed sample or truncated list masquerading as membership."""
    names = obj.get("symbols")
    if not isinstance(names, list) or names != sorted(set(names)) or len(names) != obj["count"]:
        raise ValueError("complete sorted population required; a sample is insufficient")
    original = sha("\n".join(names).encode())[:16]
    if original != obj["identity"]:
        raise ValueError("retained membership identity mismatch")
    return names


def git_bytes(revision, path):
    return subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=ROOT)


@contextmanager
def network_blocked():
    def denied(*args, **kwargs):
        raise RuntimeError("historical input proof: network forbidden")
    original = (socket.socket.connect, socket.socket.connect_ex, socket.create_connection)
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = denied
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex, socket.create_connection = original


def load_originals():
    from src import input_diagnostics
    identities = json.loads((EVIDENCE / "artifact-identities.json").read_bytes())
    originals = {}
    for day, ref in REFERENCES.items():
        folder = ROOT / "tests/fixtures/historical-validation" / day
        raw = gzip.decompress((folder / "input-exceptions.json.gz").read_bytes())
        package = json.loads(raw)
        publication_raw = git_bytes(ref["publication_commit"], "docs/data.json")
        publication = json.loads(publication_raw)
        if sha(publication_raw) != ref["publication_sha256"]:
            raise ValueError(f"publication bytes do not match supplied identity: {day}")
        artifact = next(x for x in identities if x["artifact_id"] == ref["exception_artifact"])
        if sha(raw) != artifact["original_json_sha256"]:
            raise ValueError(f"exception package bytes do not match retained identity: {day}")
        if package["run"]["execution_revision"] != ref["execution_revision"]:
            raise ValueError("execution revision mismatch")
        if package["run"]["run_id"] != ref["run_id"] or package["run"]["attempt"] != "1":
            raise ValueError("run identity mismatch")
        input_diagnostics.validate(package, expected_run=package["run"],
                                   ledger=publication["run"]["coverage"],
                                   directory_bytes=(folder / "universe-directory.json.gz").read_bytes())
        for key in ("intended", "intended_stocks", "returned", "session_ready", "universe_membership"):
            full_population(package[key])
        for pop in package["exceptions"].values():
            full_population(pop)
        assert len(package["intended_stocks"]["symbols"]) == ref["intended"]
        assert len(set(package["session_ready"]["symbols"]) - {"SPY"}) == ref["ready"]
        assert package["exceptions"]["stale"]["count"] == ref["stale"]
        originals[day] = (package, publication, {
            "publication_sha256": sha(publication_raw), "exceptions_json_sha256": sha(raw),
            "exceptions_gzip_sha256": sha((folder / "input-exceptions.json.gz").read_bytes()),
            "directory_gzip_sha256": package["directory"]["sha256"],
            "retained_artifact_identity": artifact,
        })
    return originals


def make_manifest(originals):
    from src import sessions
    populations, queries, original_basis = {}, [], {}
    calendars = {}
    for day, (package, _, _) in originals.items():
        names = full_population(package["intended_stocks"])
        seed_raw = git_bytes(REFERENCES[day]["execution_revision"], "data/symbols.txt")
        seeds = sorted(line.split("#", 1)[0].strip() for line in seed_raw.decode().splitlines() if line.split("#", 1)[0].strip())
        if not set(seeds) <= set(names):
            raise ValueError("original price-exempt seed missing from intended list")
        populations[day] = {"symbols": names, "sha256": symbol_hash(names),
                            "count": len(names), "original_identity": package["intended_stocks"]["identity"],
                            "price_exempt": seeds, "price_exempt_basis": "data/symbols.txt at original execution revision; universe.build passes all seeds as price_exempt",
                            "price_exempt_source_sha256": sha(seed_raw),
                            "original_known_excluded": package["exceptions"]["stale"]["symbols"],
                            "original_final_mask_complete": False}
        window = package["basis"]["window"]
        # This is a declared reconstruction of the provider's omitted default,
        # not a claim that an asof parameter survived in a raw wire request.
        mapping_day = package["basis"]["fetch_arguments"]["now"][:10]
        calendars[day] = [x.isoformat() for x in sessions.dates(date.fromisoformat(window["start"][:10]), date.fromisoformat(day))]
        query_names = sorted(names + ["SPY"])
        for offset in range(0, len(query_names), 100):
            queries.append({"id": f"canonical-{day}-{offset // 100 + 1:03d}", "target_session": day,
                            "scope": "bulk", "symbols": query_names[offset:offset + 100],
                            "start": window["start"], "end": window["end"], "asof": mapping_day,
                            "feed": "sip", "timeframe": "1Day", "adjustment": "split",
                            "currency": "USD", "limit": 10000, "sort": "asc", "purpose": "canonical",
                            "required_sessions_ref": day})
        original_basis[day] = {
            "observed_application_basis": {k: v for k, v in package["basis"].items() if k != "fetch_arguments"},
            "observed_fetch_arguments": {k: v for k, v in package["basis"]["fetch_arguments"].items() if k != "symbols_in_order"},
            "observed_diagnostic_capture": package["capture"],
            "asof_wire_value": None, "currency_wire_value": None,
            "asof_reconstruction": mapping_day,
            "asof_reconstruction_reason": "Original application omitted asof; pin the documented current-day mapping default to the observed UTC fetch date. Original provider default timezone and mapping result were not retained.",
            "wire_requests_pages_headers_and_exact_acquisition_instants": "not retained; batch attempts and run clock are not wire requests/timestamps",
        }
    union = sorted(set().union(*(set(x["symbols"]) for x in populations.values())))
    queries.insert(0, {"id": "access-probe", "target_session": "2026-09-24", "scope": "probe", "symbols": ["SPY"],
                       "start": "2026-09-23T04:00:00+00:00", "end": "2026-09-24T23:59:59+00:00",
                       "asof": "2026-09-25", "feed": "sip", "timeframe": "1Day", "adjustment": "split",
                       "currency": "USD", "limit": 10000, "sort": "asc", "purpose": "canonical",
                       "required_sessions": ["2026-09-23", "2026-09-24"]})
    return {
        "schema": "historical-acquisition-v1", "assignment_id": "spicystock-historical-input-2026-09-28",
        "freeze_basis": "created before any new provider request; no new values acquired",
        "populations": populations, "allowed_symbols": sorted(union + ["SPY"]),
        "allowed_symbols_sha256": symbol_hash(union + ["SPY"]), "queries": queries, "required_sessions": calendars,
        "limits": {"requests": 400, "retained_bytes": 1073741824, "requests_per_minute": 20, "page_bytes": 8388608},
        "documentation": {"verified_at": "2026-09-28", "stockbars_url": "https://docs.alpaca.markets/us/reference/stockbars",
                          "faq_url": "https://docs.alpaca.markets/us/docs/market-data-faq",
                          "verification_recorded_at": "2026-09-28T17:08:52Z",
                          "timestamp_meaning": "Verification recorded after pages were checked this turn, not an asserted exact page-access instant.",
                          "reverify_at_execution": True},
        "time_semantics": {"request_start": "inclusive UTC instant", "request_end": "inclusive UTC instant",
                           "sessions": "XNYS session labels in America/New_York", "envelope": "2025-08-01 through 2026-09-25 only",
                           "asof": "symbol mapping date only; does not freeze data vintage, corrections, splits or provider revisions"},
        "warmup": {"original_fetch_lookback_argument": 260, "calendar_multiplier": 1.6,
                   "discovery_max_sessions": 252, "quality_prior_warmup_sessions": 110,
                   "breadth_quarter_sessions": 65, "breadth_history_sessions": 30,
                   "breadth_ratio_sessions": [5, 10],
                   "target_windows": {day: {"discovery_252_start": str(sessions.sessions_before(date.fromisoformat(day), 251)[0]),
                                             "quality_110_prior_start": str(sessions.sessions_before(date.fromisoformat(day), 110)[0]),
                                             "breadth_65_start": str(sessions.sessions_before(date.fromisoformat(day), 64)[0]),
                                             "ratio_10_start": str(sessions.sessions_before(date.fromisoformat(day), 9)[0]),
                                             "ratio_10_prior_anchor": str(sessions.sessions_before(date.fromisoformat(day), 10)[0]),
                                             "ratio_5_start": str(sessions.sessions_before(date.fromisoformat(day), 4)[0])}
                                      for day in originals},
                   "rationale": "Preserve the original request spans: discovery includes the 252-session low, rolling quality features need 110 prior sessions, and quality._check_two walks the entire available prefix until a run breaks. Truncating earlier values could change those recorded run counts. Dates before targets supply features, not point-in-time universes."},
        "original_basis": original_basis,
        "transport": {"sdk": "none; standard-library direct GET with raw response retention", "endpoint": "https://data.alpaca.markets/v2/stocks/bars",
                      "one_process_one_request_in_flight": True, "retries_per_transient_request": 1,
                      "successful_pages_cached": True, "caps_across_restarts": True, "pagination": "follow until actual terminal token; aggregate limit not per symbol"},
        "request_estimate": {"bulk_chunks": len(queries) - 1, "symbols_per_chunk_maximum": 100,
                             "expected_pages_if_about_288_rows_per_symbol": 289,
                             "includes_initial_probe": True, "remaining_shared_cap_for_retries_or_extra_pages": 111,
                             "limit": "Estimate only; actual terminal pagination determines completeness and shared caps can stop acquisition."},
        "normalization": {"identity": "historical-normalization-v1",
                          "no_forward_fill": True, "duplicate_policy": "retain originals; deterministic selected row and conflict log",
                          "precision": "retain JSON numeric lexemes/Decimal before explicitly checked production float64 conversion",
                          "calendar": sessions.authority()},
        "comparisons": [
            {"id": "A", "name": "ORIGINAL PUBLICATION", "basis": "retained original aggregates, classifications and surviving observations"},
            {"id": "B", "name": "PINNED-POPULATION RECONSTRUCTION", "basis": "later values, original intended and known readiness exclusion masks; original price mask incomplete, unknown members must stay unknown"},
            {"id": "C", "name": "LATER-RETRIEVAL REPLAY", "basis": "later values, original intended list, re-evaluated current-session readiness/cent-price policy"},
            {"id": "D", "name": "ISOLATED POPULATION SENSITIVITY", "basis": "same data/mapping with per-observation-day eligibility; counterfactual policy only"},
        ],
        "predeclared_discrepancy_classes": ["changed_provider_observation", "symbol_mapping", "adjustment", "missingness", "population_selection", "application_behavior", "unresolved"],
        "decisive_checks": ["every up/down event in 5/10 consecutive sessions", "ratio-of-sums and zero denominators", "round once before threshold",
                            "down4 alarm", "10-session RED", "5-session fast selling RED", "10-session YELLOW", "up50-month YELLOW", "benchmark excluded"],
        "new_reader_actionability": "unknown for changed inputs; no model calls, order copy or publication",
        "additional_spend_ceiling_usd": 0,
    }


def reconcile_aggregate(block):
    """Independent scalar reconstruction of EVERY recorded permission predicate.

    This validates aggregate algebra, not unknown underlying stock values.
    It deliberately does not import breadth or its predicate implementations.
    """
    from src import sessions

    rules, history = block["rules"], block["history"]
    target = date.fromisoformat(block["date"])
    sessions.require_session(target)
    expected_dates = [str(day) for day in sessions.sessions_before(target, 9) + [target]]
    observed_dates = [row["date"] for row in history[-10:]]
    sums = {}
    for window in (5, 10):
        if len(history) < window:
            raise ValueError("insufficient aggregate history")
        up = sum(x["up4"] for x in history[-window:])
        down = sum(x["down4"] for x in history[-window:])
        ratio = None if down == 0 else round(up / down, 2)
        sums.update({f"up4_{window}d": up, f"down4_{window}d": down, f"ratio_{window}d": ratio})
    threshold = lambda name: round(rules[name] * block["universe"] / rules["reference_universe"], 1)
    predicates = [
        {"id": "red_down4_alarm", "tier": "red", "left": block["down4"], "operator": ">=", "right": threshold("down4_alarm"), "active": block["down4"] >= threshold("down4_alarm")},
        {"id": "red_ratio_10d", "tier": "red", "left": sums["ratio_10d"], "operator": "<", "right": rules["red_ratio_10d"], "active": sums["ratio_10d"] is not None and sums["ratio_10d"] < rules["red_ratio_10d"]},
        {"id": "red_fast_selling", "tier": "red", "left": sums["ratio_5d"], "operator": "< AND today down > up", "right": rules["red_ratio_5d"], "today_down": block["down4"], "today_up": block["up4"], "active": sums["ratio_5d"] is not None and sums["ratio_5d"] < rules["red_ratio_5d"] and block["down4"] > block["up4"]},
        {"id": "yellow_ratio_10d", "tier": "yellow", "left": sums["ratio_10d"], "operator": "<", "right": rules["yellow_ratio_10d"], "active": sums["ratio_10d"] is not None and sums["ratio_10d"] < rules["yellow_ratio_10d"]},
        {"id": "yellow_up50_month", "tier": "yellow", "left": block["up50_month"], "operator": ">", "right": threshold("up50_month_hot"), "active": block["up50_month"] > threshold("up50_month_hot")},
    ]
    verdict = "red" if any(p["active"] and p["tier"] == "red" for p in predicates) else "yellow" if any(p["active"] for p in predicates) else "green"
    mismatches = {key: [block[key], val] for key, val in sums.items() if block[key] != val}
    if observed_dates != expected_dates:
        mismatches["history.last10_dates"] = [observed_dates, expected_dates]
    for key in ("up4", "down4"):
        if block[key] != history[-1][key]:
            mismatches[f"history.last.{key}"] = [history[-1][key], block[key]]
    if history[-1].get("ratio_10d") != sums["ratio_10d"]:
        mismatches["history.last.ratio_10d"] = [history[-1].get("ratio_10d"), sums["ratio_10d"]]
    expected_inputs = {"date": block["date"], **sums,
                       **{k: block[k] for k in ("up4", "down4", "up50_month", "down25_quarter")}}
    expected_thresholds = {"universe": block["universe"], "reference_universe": rules["reference_universe"],
                           "down4_alarm": threshold("down4_alarm"), "up50_month_hot": threshold("up50_month_hot"),
                           "down25_quarter_oversold": threshold("down25_quarter_oversold"),
                           "ratio_10d_red": rules["red_ratio_10d"], "ratio_5d_red": rules["red_ratio_5d"],
                           "ratio_10d_yellow": rules["yellow_ratio_10d"]}
    expected_multiplier = rules["size_multiplier"][verdict]
    expected_oversold = block["down25_quarter"] < threshold("down25_quarter_oversold")
    for key, expected in (("inputs", expected_inputs), ("thresholds", expected_thresholds),
                          ("size_multiplier", expected_multiplier), ("oversold_extreme", expected_oversold)):
        if block["regime"].get(key) != expected:
            mismatches[f"regime.{key}"] = [block["regime"].get(key), expected]
    if verdict != block["regime"]["verdict"]:
        mismatches["verdict"] = [block["regime"]["verdict"], verdict]
    return {"status": "PASS" if not mismatches else "FAIL", "sums": sums, "predicates": predicates,
            "verdict": verdict, "original_reasons": block["regime"]["reasons"], "mismatches": mismatches,
            "validated_consecutive_XNYS_sessions": expected_dates,
            "reconstructed_archived_regime": {"inputs": expected_inputs, "thresholds": expected_thresholds,
                                               "size_multiplier": expected_multiplier, "oversold_extreme": expected_oversold},
            "oversold_informational_only": expected_oversold,
            "scope": "original retained aggregate algebra; independent stock-input corroboration BLOCKED",
            "source_fidelity": "Selected SpicyStock formula agreement only; broad B attribution in knowledge/method.md does not independently verify the gate's primary-source provenance."}


def retained_sources(publication):
    from src import provenance
    frames, objects = {}, []
    rows = publication["bursts"] + publication.get("watchlist", {}).get("top", [])
    for row in rows:
        ref = row.get("evidence", {}).get("source", {})
        if not ref.get("sha256"):
            continue
        path = ROOT / "docs/evidence" / (ref["sha256"] + ".json.gz")
        raw = gzip.decompress(path.read_bytes())
        obj = json.loads(raw)
        if provenance.digest(obj) != ref["sha256"]:
            raise ValueError("retained frame typed identity mismatch")
        if obj["dates"][-1] != publication["run"]["session"]:
            raise ValueError("retained frame belongs to another session")
        frame = provenance.frame_of(obj)
        if row["ticker"] in frames and not frame.equals(frames[row["ticker"]]):
            raise ValueError("same-run source conflict")
        frames[row["ticker"]] = frame
        objects.append({"ticker": row["ticker"], "typed_sha256": ref["sha256"],
                        "json_sha256": sha(raw), "rows": len(frame), "start": obj["dates"][0], "end": obj["dates"][-1]})
    return frames, objects


def population_mask(package, publication, frames):
    intended = set(full_population(package["intended_stocks"]))
    ready = set(full_population(package["session_ready"])) - {"SPY"}
    stale = set(full_population(package["exceptions"]["stale"]))
    price = publication["run"]["coverage"]["reasons"]["price_excluded"]
    included = set(frames)
    excluded_sample = set(price["sample"])
    if not included <= ready or not excluded_sample <= ready or included & excluded_sample:
        raise ValueError("contradictory original price-mask witnesses")
    unknown = ready - included - excluded_sample
    return {"intended_count": len(intended), "intended_sha256": symbol_hash(intended),
            "ready_stock_count": len(ready), "ready_stocks": sorted(ready), "ready_sha256": symbol_hash(ready),
            "known_stale_excluded": sorted(stale), "recorded_price_excluded": price,
            "known_final_included": sorted(included), "known_price_excluded": sorted(excluded_sample),
            "final_price_mask_unknown": sorted(unknown), "final_price_mask_unknown_count": len(unknown),
            "recorded_final_population_count": publication["run"]["coverage"]["scan_ready"],
            "exact_original_final_mask": "BLOCKED", "reason": "Only price-exclusion count/hash/sample retained; a later close cannot establish an original unknown exclusion.",
            "population_execution_order": "session readiness -> target-session cent-rounded price >=3 (seed/explicit exceptions, SPY exemption) -> exclude SPY -> breadth.snapshot; historical windows inherit target-day population"}


def exception_rows(day, package):
    result = []
    for symbol in full_population(package["exceptions"]["stale"]):
        obs = package["observations"][symbol]
        last = obs["rows"][-1]
        result.append({"session": day, "ticker": symbol, "original_last_observation_session": last["timestamp"]["session"],
                       "original_last_timestamp": last["timestamp"]["value"],
                       "original_last_values": last["values"],
                       "original_target_prior_presence": obs["session_rows"],
                       "retained_tail_rows": len(obs["rows"]), "original_full_rows": obs["rows_total"],
                       "observation_source": f"tests/fixtures/historical-validation/{day}/input-exceptions.json.gz",
                       "new_target_prior_comparison": "BLOCKED", "later_mapping_asof": package["basis"]["fetch_arguments"]["now"][:10],
                       "supported_explanation": "Original application-normalized history ends before target; provider cause unresolved. No new retrieval, inactivity/delisting or historical availability inference.",
                       "classification": "missingness; unresolved cause"})
    return result


def volume_sensitivity(originals):
    from src import plan, provenance, quality, scans
    from tools.historical_breadth_reference import reference_replay
    retained = json.loads((EVIDENCE / "volume-corroboration.json").read_bytes())
    publication = originals["2026-09-24"][1]
    result = []
    for observation in retained:
        row = next(x for x in publication["bursts"] if x["ticker"] == observation["ticker"])
        ref = row["evidence"]["source"]["sha256"]
        obj = json.loads(gzip.decompress((ROOT / "docs/evidence" / f"{ref}.json.gz").read_bytes()))
        frame = provenance.frame_of(obj)
        changed = frame.copy()
        changed.loc[changed.index[-2:], "Volume"] = observation["public_volumes"]
        cases = []
        for name, data in (("original_retained", frame), ("dated_public_two_volume_substitution", changed)):
            c, p, v, pv = float(data.Close.iloc[-1]), float(data.Close.iloc[-2]), int(data.Volume.iloc[-1]), int(data.Volume.iloc[-2])
            measured = quality.assess(data).to_dict()
            cases.append({"basis": name, "close": c, "prior_close": p, "volume_shares": v, "prior_volume_shares": pv,
                          "volume_above_prior": v > pv, "volume_floor_100000": v >= 100000,
                          "breadth_gain_percent_unrounded": 100 * (c - p) / p,
                          "reference_breadth_up4": 100 * (c - p) / p >= 4 and v >= 100000 and v > pv,
                          "reference_breadth_down4": 100 * (c - p) / p <= -4 and v >= 100000 and v > pv,
                          "discovery_routes": [k for k, value in scans.scan_all(data).items() if value],
                          "mechanical_grade": measured["grade"], "mechanical_score": measured["score"],
                          "checks": {c["letter"]: {"status": c["status"], "values": c["values"]} for c in measured["checks"]}})
        baseline, substituted = cases
        # Reproduce the prior component evidence, including CRL's independent Dollar route.
        for expected, actual in ((observation["before"], baseline), (observation["substituted_public_volumes"], substituted)):
            assert expected["routes"] == actual["discovery_routes"] and expected["grade"] == actual["mechanical_grade"]
            assert expected["checks"] == actual["checks"]
        b = publication["breadth"]
        delta_up = int(substituted["reference_breadth_up4"]) - int(baseline["reference_breadth_up4"])
        delta_down = int(substituted["reference_breadth_down4"]) - int(baseline["reference_breadth_down4"])
        event_comparison = []
        replay_pair = [reference_replay({row["ticker"]: data}, date(2026, 9, 24), intended=[row["ticker"]],
                                       source_identity={"type": name, "original_object": ref,
                                                        "volume_observation_date": observation["retrieved_on"] if data is changed else None})
                       for name, data in (("original", frame), ("two_volume_substitution", changed))]
        for before, after in zip(replay_pair[0]["events"], replay_pair[1]["events"]):
            event_comparison.append({"session": before["session"],
                                     "original": {k: before["events"][k] for k in ("up4", "down4")},
                                     "substituted": {k: after["events"][k] for k in ("up4", "down4")}})
        full_deltas = {key: sum(int(e["substituted"][key] is True) - int(e["original"][key] is True) for e in event_comparison) for key in ("up4", "down4")}
        structural = plan.burst_plan(ticker=row["ticker"], close=row["close"], low=row["low"], high=row["high"],
                                     open_=row["open"], prev_close=row["prev_close"], gain_pct=row["gain_pct"] or 0,
                                     account=plan.Account(**{k: publication["account"][k] for k in provenance.ACCOUNT_FIELDS}),
                                     size_multiplier=1, scan="dollar" if row["scan"] == "dollar" else "4pct",
                                     extension_pct=row.get("extension_pct"))
        result.append({"ticker": observation["ticker"], "session": observation["session"],
                       "status": "PASS", "source_typed_sha256": ref, "source_url": observation["source"],
                       "public_observation_date": observation["retrieved_on"], "basis_limits": observation["basis"],
                       "identity_limit": observation["identity_limit"], "cases": cases,
                       "target_event_delta": {"up4": delta_up, "down4": delta_down},
                       "complete_ten_session_event_comparison": event_comparison,
                       "ten_session_event_deltas": full_deltas,
                       "all_affected_events_ratio_10d": round((b["up4_10d"] + full_deltas["up4"]) / (b["down4_10d"] + full_deltas["down4"]), 2),
                       "target_event_only_ratio_10d": round((b["up4_10d"] + delta_up) / (b["down4_10d"] + delta_down), 2),
                       "target_event_only_bound_scope": "Holds all other original events fixed. Prior-date volume can also change the prior event; full substitution is emitted by the independent retained-frame comparison, not inferred from this target-only diagnostic.",
                       "new_provider_comparison": "BLOCKED", "new_reader_judgment": "unknown",
                       "original_final_grade": row["grade"], "plan_prerequisites": "Recorded RED and final B independently block plans. Changed metrics invalidate reader-response reuse.",
                       "isolated_structural_feasibility": {"market_multiplier_substitution": 1,
                           "eligible_structural_band": structural["eligible"], "nonzero_whole_share_size": structural["shares"] > 0,
                           "same_for_both_volume_cases": True,
                           "scope": "Diagnostic arithmetic only using recorded account and unchanged prices. Reader-dependent actionability unknown; order terms omitted, no publication."},
                       "trade_condition_adjudication": "BLOCKED: needs specifically authorized condition-coded CRL/IQV trades for Sep23/24 plus provider daily inclusion/adjustment rules; trade/quote requests are outside this permission."})
    return result


def selected_reference(day, package, publication, frames, objects, output):
    """Execute the reference on every surviving original same-run source frame.

    Full original price membership remains tri-state. We never supply unknown
    members as included merely to make a B reconstruction executable.
    """
    from tools.historical_breadth_reference import compare_replay
    source = {"basis": "original same-run candidate/watch source objects; selected population only",
              "publication": REFERENCES[day]["publication_sha256"],
              "objects": {x["ticker"]: x["typed_sha256"] for x in objects},
              "mapping": "original mapping result unknown; no later values mixed", "feed": "sip", "adjustment": "split"}
    comparison = compare_replay(frames, date.fromisoformat(day), intended=sorted(frames), source_identity=source)
    comparison["scope"] = "SELECTED RETAINED ORIGINAL FRAMES ONLY; neither full original nor later-retrieval reconstruction"
    save(output / f"selected-reference-{day}.json.gz", comparison)
    mask = population_mask(package, publication, frames)
    known_excluded = set(mask["known_stale_excluded"]) | set(mask["known_price_excluded"])
    measured = {(e["symbol"], e["session"]): e for e in comparison["reference"]["events"]}
    events = []
    for session in comparison["reference"]["calendar"]["event_sessions"]:
        for symbol in package["intended_stocks"]["symbols"]:
            event = measured.get((symbol, session))
            events.append({"symbol": symbol, "session": session,
                           "original_final_population_included": True if event else False if symbol in known_excluded else None,
                           "up4": event["events"]["up4"] if event else None,
                           "down4": event["events"]["down4"] if event else None,
                           "source_identity_sha256": event["source_identity_sha256"] if event else None,
                           "reason": "retained same-run source" if event else "original excluded; no complete event observations" if symbol in known_excluded else "original price mask and/or underlying observations unknown"})
    save(output / f"original-event-availability-{day}.json.gz", {
        "status": "BLOCKED", "session": day, "units": {"price": "USD split-adjusted", "volume": "shares"},
        "rules": comparison["reference"]["rules"], "events": events,
        "denominator": "known included / known excluded / unknown final original population; null is not false",
        "event_values_path": f"selected-reference-{day}.json.gz",
        "scope": "Full intended stock coverage inventory; missing original observations are not supplied from later data."})
    # Conservative outer bounds under a SPECIFIC assumption: unknown original
    # contributors can replace all missing contributors; each cell is up/down/
    # neither, never simultaneously up AND down. Adjacent-day dependencies can
    # narrow these bounds; endpoints are not asserted jointly attainable.
    bounds = {}
    for window in (5, 10):
        tail = comparison["reference"]["days"][-window:]
        up, down = sum(x["up4"] for x in tail), sum(x["down4"] for x in tail)
        missing = (mask["recorded_final_population_count"] - len(frames)) * window
        missing += sum(x["unknown"]["up4"] for x in tail)
        bounds[str(window)] = {"known_up": up, "known_down": down, "unresolved_event_cells_upper": missing,
                               "ratio_lower_outer": up / (down + missing) if down + missing else None,
                               "ratio_upper_outer": (up + missing) / down if down else None,
                               "upper_unbounded_or_undefined": down == 0,
                               "assumptions": "Recorded final population count is accurate; known same-run frames are included. Each unresolved cell is up OR down OR neither. Separate endpoint assignments; shared adjacent prices/volumes may make endpoints unattainable.",
                               "scope": "Partial outer bound only; unknown price membership, input correctness and other RED predicates preclude a full-universe verdict."}
    return {"status": comparison["status"], "symbols": len(frames), "event_count": len(measured),
            "full_intended_event_cells": len(events), "differences": comparison["differences"],
            "scope": comparison["scope"], "bounds": bounds,
            "reference_file": f"selected-reference-{day}.json.gz",
            "event_availability_file": f"original-event-availability-{day}.json.gz"}


def run(output):
    with network_blocked():
        originals = load_originals()
        manifest = make_manifest(originals)
        save(output / "acquisition-manifest.json", manifest)
        save(output / "manifest-freeze.json", {"status": "PASS", "manifest_bytes_sha256": sha(encoded(manifest)),
             "manifest_sha256": sha((json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()),
             "manifest_sha256_encoding": "sorted-key compact JSON plus LF; matches acquisition approval/ledger identity",
             "manifest_bytes_sha256_encoding": "exact committed pretty-printed acquisition-manifest.json bytes",
             "new_provider_requests_before_freeze": 0, "new_provider_responses_examined": 0,
             "timestamp_limit": "No fabricated pre-experiment wall-clock claim; git commit and manifest byte hash freeze the declared acquisition. Only retained original/public corroboration values have been examined."})
        reports, exceptions = {}, []
        all_stale = set()
        for day, (package, publication, identities) in originals.items():
            frames, objects = retained_sources(publication)
            mask = population_mask(package, publication, frames)
            all_stale.update(mask["known_stale_excluded"])
            exceptions.extend(exception_rows(day, package))
            code = {}
            for path in ("src/market_data.py", "src/universe.py", "src/inputs.py", "src/breadth.py", "src/scans.py", "src/quality.py", "src/pipeline.py"):
                raw = git_bytes(REFERENCES[day]["execution_revision"], path)
                current = (ROOT / path).read_bytes()
                code[path] = {"execution_sha256": sha(raw), "current_sha256": sha(current), "same_bytes": raw == current,
                              "same_text_after_CRLF_to_LF": raw.replace(b"\r\n", b"\n") == current.replace(b"\r\n", b"\n")}
            reports[day] = {"identity_check": "PASS", "reference": REFERENCES[day], "identities": identities,
                            "execution_code": code, "population": mask, "aggregate_reconciliation": reconcile_aggregate(publication["breadth"]),
                            "retained_frame_count": len(frames), "retained_objects": objects,
                            "selected_reference_comparison": selected_reference(day, package, publication, frames, objects, output),
                            "complete_original_stock_inputs": "BLOCKED", "complete_original_benchmark": "BLOCKED",
                            "original_candidate_count": len(publication["bursts"]),
                            "discovery_counts": publication["run"]["coverage"]["matched"],
                            "original_published_reaction_plans": len(publication["trades"]),
                            "accepted_final_A_or_A_plus": sum(r["grade"] in ("A", "A+") and r.get("evidence", {}).get("reader_source") == "accepted" for r in publication["bursts"])}
        assert len(all_stale) == 31
        status = "FAIL" if any(r["aggregate_reconciliation"]["status"] == "FAIL" or r["selected_reference_comparison"]["status"] == "FAIL" for r in reports.values()) else "PASS"
        save(output / "original-reconciliation.json", {"version": VERSION, "status": status, "sessions": reports,
             "scope": "Identity, complete retained membership, original aggregate algebra and selected retained source identities only.",
             "reconstructed_full_population_RED": "BLOCKED", "verdict": "RED is supported by retained published aggregates; RED on a complete later-retrieved stock-by-stock basis is not established.",
             "later_retrieval": "NOT RUN", "independent_provider_corroboration": "Limited dated CRL/IQV public volume observations only."})
        save(output / "complete-exceptions.json", {"status": "PASS", "union": sorted(all_stale), "union_sha256": symbol_hash(all_stale),
             "union_count": len(all_stale), "session_exception_occurrences": len(exceptions), "exceptions": exceptions,
             "new_data_comparisons": "BLOCKED"})
        save(output / "volume-materiality.json", volume_sensitivity(originals))
        save(output / "offline-runtime.json", {"status": "PASS", "runner": VERSION, "runner_sha256": sha(Path(__file__).read_bytes()),
             "python": sys.version.split()[0], "packages": {k: importlib.metadata.version(k) for k in ("pandas", "numpy", "exchange_calendars")},
             "socket_connect_blocked": True, "provider_requests": 0, "new_retained_response_bytes": 0, "new_model_calls": 0})
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports = run(args.output)
    status = "FAIL" if any(r["aggregate_reconciliation"]["status"] == "FAIL" or r["selected_reference_comparison"]["status"] == "FAIL" for r in reports.values()) else "PASS"
    print(json.dumps({"status": status, "sessions": list(reports), "new_requests": 0,
                      "full_population_reconstruction": "BLOCKED"}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
