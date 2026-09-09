"""Synthetic history must survive platform float noise without hiding drift."""
from copy import deepcopy

from tools.check_fixture_fresh import _first_difference
from tools.make_history import _normalize_stockbee_measurements


def _run(price):
    row = {
        "ticker": "DHI", "date": "2026-09-01", "open": price,
        "high": price, "low": price, "close": price, "prev_close": price,
        "volume": 1483851.0, "gain_pct": 0.64904418, "prior_up_days": 0,
        "series": [{"date": "2026-07-31", "open": price, "high": price,
                    "low": price, "close": price, "volume": 1483851.0}],
    }
    return {"fixture": True, "date": "2026-09-01", "coverage": {"measured": 77},
            "stockbee": {queue: {"rows": [deepcopy(row)]}
                         for queue in ("scan", "anticipation")}}


def test_history_prices_serialize_the_reported_cross_platform_difference_identically():
    # The exact committed/regenerated pair reported by Actions run 34203390122.
    left, right = _run(161.8601472119932), _run(161.86014721199325)
    assert left != right
    for run in (left, right):
        _normalize_stockbee_measurements(run)
    assert left == right
    assert left["stockbee"]["anticipation"]["rows"][0]["series"][0]["close"] == 161.86014721
    again = deepcopy(left)
    _normalize_stockbee_measurements(again)
    assert again == left


def test_history_normalization_preserves_decisions_metadata_and_detectable_drift():
    baseline = _run(161.8601472119932)
    _normalize_stockbee_measurements(baseline)
    changed = deepcopy(baseline)
    changed["fixture"] = False
    changed["date"] = "2026-09-02"
    changed["coverage"]["measured"] = 76
    changed["stockbee"]["scan"]["rows"] = []
    row = changed["stockbee"]["anticipation"]["rows"][0]
    row["series"][0]["close"] += 0.01
    row["series"][0]["volume"] += 1
    row["series"][0]["date"] = "2026-08-03"
    row["unrecognized_metric"] = 0.123456789123
    expected = deepcopy(changed)
    expected["stockbee"]["anticipation"]["rows"][0]["series"][0]["close"] = 161.87014721
    _normalize_stockbee_measurements(changed)
    assert changed == expected
    assert _first_difference(baseline, changed) is not None
    # The freshness guard still reports a changed price even without metadata drift.
    price_only = deepcopy(baseline)
    price_only["stockbee"]["scan"]["rows"][0]["close"] += 0.01
    _normalize_stockbee_measurements(price_only)
    assert '["close"]' in _first_difference(baseline, price_only)
