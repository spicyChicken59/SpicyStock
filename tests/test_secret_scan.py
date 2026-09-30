"""The public-response disposition cannot broaden path, value or detectors.

The companion secret_scan_controls.py also exercises the actual 8.24.3 engine
with these boundaries; it takes an explicit installed binary and no network.
"""
import hashlib
import json
import re
import tomllib

import pytest

from tests.secret_scan_controls import OBSERVATION, PUBLIC_VALUES, ROOT


def dispositions():
    config = tomllib.loads((ROOT / ".gitleaks.toml").read_text(encoding="utf-8"))
    assert config["extend"] == {"useDefault": True}
    assert "allowlist" not in config and "allowlists" not in config
    assert len(config["rules"]) == 1
    rule = config["rules"][0]
    assert set(rule) == {"id", "allowlists"}
    assert rule["id"] == "generic-api-key"
    return rule["allowlists"]


def allowed(path, value):
    return any(item.get("condition") == "AND" and item.get("regexTarget") == "secret" and
               any(re.search(pattern, path) for pattern in item["paths"]) and
               any(re.search(pattern, value) for pattern in item["regexes"])
               for item in dispositions())


def test_only_two_existing_public_response_hashes_are_dispositioned():
    document = json.loads((ROOT / OBSERVATION).read_bytes())
    assert tuple(document["retained_response_sha256"].values()) == PUBLIC_VALUES
    assert all(allowed(OBSERVATION, value) for value in PUBLIC_VALUES)
    entry = next(item for item in dispositions() if "PR97 CI observation" in item["description"])
    assert set(entry) == {"description", "condition", "regexTarget", "regexes", "paths"}
    assert entry["paths"] == ["^" + re.escape(OBSERVATION).replace(r"\-", "-") + "$"]
    assert entry["regexes"] == ["^(" + "|".join(PUBLIC_VALUES) + ")$"]


@pytest.mark.parametrize("path", [OBSERVATION + ".backup", "copied/" + OBSERVATION,
    OBSERVATION.replace("secret_scan-api.json", "another.json"), "unrelated.txt"])
def test_public_values_elsewhere_remain_detectable(path):
    assert all(not allowed(path, value) for value in PUBLIC_VALUES)


@pytest.mark.parametrize("value", [hashlib.sha256(b"unrelated invented scanner regression value").hexdigest(),
    "x" + PUBLIC_VALUES[0], PUBLIC_VALUES[0] + "x", PUBLIC_VALUES[1].upper()])
def test_unrelated_or_altered_values_at_the_exact_path_remain_detectable(value):
    assert not allowed(OBSERVATION, value)


def test_existing_default_and_historical_dispositions_are_preserved():
    assert allowed("tests/fixtures/grading/record.json", "down25_quarter")
    assert allowed("tests/fixtures/grading/reader-commentary/record.json", "pct_above_40ma")
    assert not allowed(OBSERVATION, "down25_quarter")
    assert not allowed("tests/fixtures/grading/record.json", PUBLIC_VALUES[0])
