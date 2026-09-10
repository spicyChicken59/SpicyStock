"""A dated, deliberately shadow-only calibration of recorded setup outcomes.

This module learns a small ridge regression, never calls an AI or data API,
and never changes the scanner, scoring prompt, orders, or production ranking.
Only outcomes whose first observation date is recorded can enter a fit.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
import math
import re

import numpy as np


VERSION = 1
MIN_TRAIN = 100
MIN_VALIDATION = 30
MIN_DATES = 20
MIN_VALIDATION_DATES = 10
ROUND_TRIP_COST_BPS = 20
RIDGE_PENALTY = 2.0
FEATURES = ("score_divided_by_10", "log1p_volume_ratio_divided_by_log11",
            "lynch_pass_fraction")
MAX_PRIORITIES = 40


def _date(value, *, session=True):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        parsed = date.fromisoformat(value)
        return parsed if not session or parsed.weekday() < 5 else None
    except ValueError:
        return None


def _number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except (ValueError, OverflowError):
        return False


def _source(row):
    provenance = row.get("provenance")
    return provenance.get("source") if isinstance(provenance, dict) else row.get("source")


def _signature(run):
    """Which screener produced this run's rows, for the purpose of fitting them.

    The PRODUCTION half of the fingerprint only. This fit reads a row's score,
    volume ratio and checklist passes and labels it with the open-basis d5;
    the research sidecar supplies none of the four, so a constant moved there
    must not split the corpus. Reproduced before it was narrowed: moving one
    sidecar constant took a twelve-setup fit to one, every excluded run's own
    score and outcome unchanged. src.pipeline.production_rules() is the one
    rule, and evidence.rules deliberately keeps reading every key, because
    the question it asks is the wider one.

    Imported here for the reason is_named_basket() is, below: src.ledger
    imports this module, so the edge is taken at call time rather than at
    import time.
    """
    from src.pipeline import production_rules

    rules, model = run.get("rules"), run.get("model")
    if (not isinstance(rules, dict) or not isinstance(model, str) or not model
            or not isinstance(rules.get("score.prompt"), str) or not rules["score.prompt"]):
        return None
    try:
        serialized = json.dumps({"model": model, "rules": production_rules(rules)},
                                sort_keys=True,
                                allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def _features(row):
    score, volume = row.get("score"), row.get("volume_ratio")
    passed, total = row.get("lynch_passes"), row.get("lynch_total")
    if (not all(_number(x) for x in (score, volume, passed, total))
            or not 0 <= score <= 10 or not 0 < volume <= 1000
            or not 0 <= passed <= total or not 1 <= total <= 20):
        return None
    return [score / 10, math.log1p(volume) / math.log(11), passed / total]


def _eligible_run(run, through):
    if not isinstance(run, dict):
        return "malformed_run"
    day = _date(run.get("date"))
    if day is None or day > through:
        return "undated_or_future_run"
    if run.get("fixture") is not None and run.get("fixture") is not False:
        return "fixture"
    if run.get("dry_run") is not False:
        return "dry_run_or_unknown"
    if run.get("type") != "evening" or run.get("status") != "ok":
        return "non_evening_or_degraded"
    # One predicate for "a basket named on the command line", shared with the
    # ledger rather than restated here. The structural test this replaces --
    # `"tickers" in universe` -- was written when only a --tickers run carried
    # that key, and the adaptive selector now stamps it on every production
    # scan beside a `selection` block: on the committed record, the clean
    # 2026-09-09 scan of 500 names was excluded as a named basket, so no real
    # night could ever enter a fit. is_named_basket() reads both keys.
    # Imported here for the same reason setup_chains is, below: ledger
    # validation imports this module.
    from src.ledger import is_named_basket

    if not isinstance(run.get("universe"), dict):
        return "unknown_universe"
    if is_named_basket(run):
        return "named_basket"
    if not isinstance(run.get("candidates"), list) or not isinstance(run.get("gated", []), list):
        return "malformed_rows"
    return None


def _observations(runs, through, signature):
    # Share the existing episode rule, including gated appearances that bridge
    # two scored days. Import here so ledger validation can import this module.
    from src.ledger import setup_chains

    excluded = Counter()
    cleaned, owner = [], {}
    for run in runs:
        why = _eligible_run(run, through)
        if why:
            excluded[why] += 1
            continue
        copy = {"candidates": [], "gated": []}
        for kind in ("candidates", "gated"):
            for row in run.get(kind, []):
                if (not isinstance(row, dict) or not isinstance(row.get("ticker"), str)
                        or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", row["ticker"])
                        or _date(row.get("date")) != _date(run["date"])):
                    excluded["malformed_row"] += 1
                    continue
                copy[kind].append(row)
                owner[id(row)] = run
        cleaned.append(copy)
    observations, eligible = [], 0
    for chain in setup_chains(cleaned).values():
        row = next((item for item in chain if _number(item.get("score"))), None)
        if row is None:
            continue
        run = owner[id(row)]
        if _source(row) != "claude":
            excluded["fallback_or_unknown_scorer"] += 1
            continue
        if signature is None or _signature(run) != signature:
            excluded["different_or_unknown_rules"] += 1
            continue
        x = _features(row)
        if x is None:
            excluded["incomplete_features"] += 1
            continue
        eligible += 1
        returns = row.get("forward_returns")
        opened = returns.get("from_open") if isinstance(returns, dict) else None
        raw = opened.get("d5") if isinstance(opened, dict) else None
        if not _number(raw) or not -100 <= raw <= 10000:
            excluded["pending_or_invalid_outcome"] += 1
            continue
        target = _date(returns.get("as_of"))
        observed = _date(returns.get("observed_at"), session=False)
        day = _date(row["date"])
        # The bar date alone cannot prove when a delayed backfill became known.
        if observed is None:
            excluded["outcome_observation_date_missing"] += 1
            continue
        if (target is None or int(np.busday_count(day, target)) < 5
                or not target <= observed <= through):
            excluded["outcome_not_available_or_invalid_date"] += 1
            continue
        observations.append({"ticker": row["ticker"], "date": row["date"],
                             "observed_at": observed.isoformat(), "target_date": target.isoformat(),
                             "score": float(row["score"]), "x": x,
                             "y": float(raw) - ROUND_TRIP_COST_BPS / 100})
    return sorted(observations, key=lambda row: (row["date"], row["ticker"])), eligible, excluded


def _fit(rows, width=3):
    x = np.asarray([[1.0, *row["x"][:width]] for row in rows], dtype=float)
    y = np.asarray([row["y"] for row in rows], dtype=float)
    penalty = np.eye(width + 1) * RIDGE_PENALTY
    penalty[0, 0] = 0
    return np.linalg.solve(x.T @ x + penalty, x.T @ y)


def _predict(coefficients, row):
    return float(np.dot(coefficients, [1.0, *row["x"][:len(coefficients) - 1]]))


def _wilson(wins, count):
    if not count:
        return [None, None]
    z = 1.959963984540054
    p = wins / count
    denominator = 1 + z * z / count
    center = (p + z * z / (2 * count)) / denominator
    half = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / denominator
    return [round(max(0, center - half) * 100, 2), round(min(1, center + half) * 100, 2)]


def _calibration(rows):
    out = []
    for low, high, label in ((0, 4, "0–<4"), (4, 6, "4–<6"), (6, 8, "6–<8"), (8, 10.01, "8–10")):
        bucket = [row for row in rows if low <= row["score"] < high]
        n = len(bucket)
        wins = sum(row["y"] > 0 for row in bucket)
        out.append({"label": label, "n": n, "wins": wins,
                    "win_rate_pct": round(wins / n * 100, 2) if n else None,
                    "interval_pct": _wilson(wins, n),
                    "mean_net_return_pct": round(float(np.mean([r["y"] for r in bucket])), 4) if n else None})
    return out


def _model(coefficients, train, cutoff, signature):
    parameters = {"method": "ridge_linear_v1", "features": list(FEATURES),
                  "ridge_penalty": RIDGE_PENALTY, "intercept": round(float(coefficients[0]), 10),
                  "coefficients": [round(float(value), 10) for value in coefficients[1:]],
                  "training_from": train[0]["date"], "training_through": train[-1]["date"],
                  "latest_observed_at": max(row["observed_at"] for row in train),
                  "label_cutoff": cutoff, "training_setups": len(train), "scoring_signature": signature}
    # Include the dated training observations in the digest, but never publish
    # those rows. An outcome correction therefore changes the model version.
    hashed = json.dumps({"parameters": parameters, "observations": train}, sort_keys=True,
                        separators=(",", ":"), allow_nan=False)
    return {"version": hashlib.sha256(hashed.encode()).hexdigest()[:16], **parameters}


def _selection_lifts(predictions):
    by_day = defaultdict(list)
    for row in predictions:
        by_day[row["date"]].append(row)
    lifts = []
    for day, rows in sorted(by_day.items()):
        if len(rows) < 3:
            continue
        top = max(1, math.ceil(len(rows) / 3))
        chosen = sorted(rows, key=lambda row: (-row["prediction"], row["ticker"]))[:top]
        baseline = sorted(rows, key=lambda row: (-row["score"], row["ticker"]))[:top]
        lifts.append({"date": day, "lift": float(np.mean([row["y"] for row in chosen])
                                                 - np.mean([row["y"] for row in baseline]))})
    return lifts


def build(runs, current_run, current_candidates=None):
    """Return a bounded public evidence summary; no input is mutated.

    ``runs`` accepts the ledger's list, or its full document so the top-level
    fixture marker can be honored. Legacy labels without ``observed_at`` are
    excluded. ``qualified`` means a research gate passed, never promotion.
    """
    if not isinstance(current_run, dict) or _date(current_run.get("date")) is None:
        return None
    through = _date(current_run["date"])
    if current_run.get("fixture") is not None and current_run.get("fixture") is not False:
        return None
    fixture_document = isinstance(runs, dict) and runs.get("fixture") is not None and runs.get("fixture") is not False
    if isinstance(runs, dict):
        runs = runs.get("runs", [])
    if not isinstance(runs, list):
        runs = []
    signature = _signature(current_run)
    rows, eligible, excluded = _observations([] if fixture_document else runs, through, signature)
    if fixture_document:
        excluded["fixture_document"] += 1
    dates = sorted({row["date"] for row in rows})
    out = {
        "version": VERSION, "as_of": through.isoformat(), "status": "collecting", "mode": "shadow_only",
        "reason": "Collecting dated outcomes before a model can be evaluated.",
        "scope": "Real, successful evening Claude-scored setups under the current model and the production rules that made them; research-only measurements archived beside a row do not split the sample; one observation per setup.",
        "target": {"horizon": 5, "basis": "next_session_open_to_fifth_session_close",
                   "round_trip_cost_bps": ROUND_TRIP_COST_BPS, "returns": "hypothetical"},
        "requirements": {"train_setups": MIN_TRAIN, "validation_setups": MIN_VALIDATION,
                         "total_dates": MIN_DATES, "validation_dates": MIN_VALIDATION_DATES},
        "counts": {"eligible": eligible, "matured": len(rows), "train": 0, "validation": 0,
                   "dates": len(dates), "excluded": dict(excluded), "purged": 0},
        "scoring_signature": signature, "model": None, "validation": None,
        "calibration": _calibration(rows), "priorities": [],
        "limitations": [
            "Research only. Production scores, rules and order decisions are unchanged; promotion requires a separate review.",
            "Bar-price outcomes are hypothetical next-open entries, not your trades, stop-managed returns or portfolio performance.",
            "The 20-basis-point round-trip deduction is a fixed cost scenario, not measured commissions, spread or slippage.",
            "This is a selected sample of scored setups from whatever basket that night scanned -- the adaptive selection on a production night, the reviewed seed as a fallback -- not all Stockbee scan matches or the whole market.",
            "Calibration bins describe all eligible matured history; their 95% Wilson intervals are not out-of-sample forecasts.",
            "Two expanding chronological validation windows use only labels first observed before each window begins.",
            "Setup grouping uses the ledger's five-business-day gap convention, which does not adjust for exchange holidays.",
            "Repeated validation and correlated stocks can overstate evidence; a qualified challenger remains in shadow mode.",
        ],
    }
    if signature is None:
        out["reason"] = "The current scorer model and rules fingerprint must be recorded before calibration."
        return out
    if len(rows) < MIN_TRAIN + MIN_VALIDATION or len(dates) < MIN_DATES:
        return out

    validation_dates = max(MIN_VALIDATION_DATES, math.ceil(len(dates) * .25))
    if validation_dates >= len(dates):
        return out
    start = dates[-validation_dates]
    train = [row for row in rows if row["date"] < start and row["observed_at"] < start]
    validation = [row for row in rows if row["date"] >= start]
    purged = sum(row["date"] < start and row["observed_at"] >= start for row in rows)
    out["counts"].update(train=len(train), validation=len(validation), purged=purged)
    if len(train) < MIN_TRAIN or len(validation) < MIN_VALIDATION:
        out["reason"] = "More outcomes are needed after separating training from later validation and purging unfinished labels."
        return out

    window_dates = dates[-validation_dates:]
    midpoint = len(window_dates) // 2
    windows = (window_dates[:midpoint], window_dates[midpoint:])
    folds, predictions, final_model, final_coefficients = [], [], None, None
    for window in windows:
        cutoff = window[0]
        fit_rows = [row for row in rows if row["date"] < cutoff and row["observed_at"] < cutoff]
        test_rows = [row for row in rows if row["date"] in window]
        if len(fit_rows) < MIN_TRAIN or not test_rows:
            return out
        coefficients, baseline = _fit(fit_rows), _fit(fit_rows, width=1)
        evaluated = [{**row, "prediction": _predict(coefficients, row),
                      "baseline": _predict(baseline, row)} for row in test_rows]
        challenger_mae = float(np.mean([abs(row["prediction"] - row["y"]) for row in evaluated]))
        baseline_mae = float(np.mean([abs(row["baseline"] - row["y"]) for row in evaluated]))
        fold_lifts = _selection_lifts(evaluated)
        folds.append({"training_setups": len(fit_rows), "validation_setups": len(test_rows),
                      "training_through": fit_rows[-1]["date"],
                      "latest_observed_at": max(row["observed_at"] for row in fit_rows),
                      "validation_from": cutoff, "validation_through": window[-1],
                      "baseline_mae": round(baseline_mae, 4), "challenger_mae": round(challenger_mae, 4),
                      "selection_lift_pct": round(float(np.mean([item["lift"] for item in fold_lifts])), 4)
                      if fold_lifts else None})
        predictions.extend(evaluated)
        final_model, final_coefficients = _model(coefficients, fit_rows, cutoff, signature), coefficients

    baseline_mae = float(np.mean([abs(row["baseline"] - row["y"]) for row in predictions]))
    challenger_mae = float(np.mean([abs(row["prediction"] - row["y"]) for row in predictions]))
    improvement = (baseline_mae - challenger_mae) / baseline_mae * 100 if baseline_mae > 0 else None
    lifts = [item["lift"] for item in _selection_lifts(predictions)]
    lift = float(np.mean(lifts)) if lifts else None
    # Student-t 95% critical value is 2.262 for nine degrees of freedom;
    # keeping it for larger samples is conservative. No interval with <10 days.
    half = 2.262 * float(np.std(lifts, ddof=1)) / math.sqrt(len(lifts)) if len(lifts) >= 10 else None
    interval = [lift - half, lift + half] if half is not None else [None, None]
    qualified = (improvement is not None and improvement >= 5 and lift is not None and lift >= .25
                 and interval[0] is not None and interval[0] > 0
                 and all(fold["challenger_mae"] < fold["baseline_mae"]
                         and fold["selection_lift_pct"] is not None and fold["selection_lift_pct"] > 0
                         for fold in folds))
    out.update(status="qualified" if qualified else "shadow", model=final_model,
               reason=("The challenger passed the research gates and remains in shadow mode for review."
                       if qualified else "The challenger is being measured in shadow mode; evidence has not passed every improvement gate."))
    out["validation"] = {
        "method": "two_expanding_chronological_windows", "folds": folds,
        "baseline": "Original score ranking; a training-only score-to-return ridge calibration supplies the MAE comparison.",
        "baseline_mae": round(baseline_mae, 4), "challenger_mae": round(challenger_mae, 4),
        "mae_improvement_pct": round(improvement, 4) if improvement is not None else None,
        "selection": "Equal-weight top third within each scored date; dates with fewer than three setups are excluded.",
        "selection_lift_pct": round(lift, 4) if lift is not None else None,
        "selection_lift_interval": [round(value, 4) if value is not None else None for value in interval],
        "selection_dates": len(lifts), "interval_method": "Approximate 95% paired-date t interval; correlated dates remain a limitation.",
        "gates": {"mae_improvement_pct": 5, "selection_lift_pct": .25,
                  "positive_interval_lower_bound": True, "both_folds_improve": True},
        "passed": qualified,
    }
    # The current research priorities use the last evaluated fold's parameters.
    # Never refit on the validation outcomes and present that fit as validated.
    current_allowed = (current_run.get("type") == "evening" and current_run.get("status") == "ok"
                       and current_run.get("dry_run") is False)
    if current_allowed and isinstance(current_candidates, list):
        priorities, seen = [], set()
        for row in current_candidates:
            if not isinstance(row, dict) or _source(row) != "claude" or row.get("date") != through.isoformat():
                continue
            ticker, x = row.get("ticker"), _features(row)
            if (not isinstance(ticker, str) or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", ticker)
                    or ticker in seen or x is None):
                continue
            seen.add(ticker)
            priorities.append({"ticker": ticker, "score": row["score"],
                               "expected_net_return_pct": round(_predict(final_coefficients, {"x": x}), 4),
                               "model_version": final_model["version"]})
        priorities.sort(key=lambda row: (-row["expected_net_return_pct"], row["ticker"]))
        out["priorities"] = [{**row, "review_priority": rank} for rank, row in enumerate(priorities[:MAX_PRIORITIES], 1)]
    return out
