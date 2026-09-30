"""The public-response disposition cannot broaden path, value or detectors.

The companion secret_scan_controls.py also exercises the actual 8.24.3 engine
with these boundaries; it takes an explicit installed binary and no network.
"""
import hashlib
import json
import re
import tomllib

import pytest

from tests.secret_scan_controls import (
    BOUNDED_PATHS, BOUNDED_VALUES, OBSERVATION, PUBLIC_VALUES, ROOT,
    retained_documents, NATIVE5_PRESERVATION, NATIVE5_PUBLIC_BLOB,
    NATIVE5_WORKFLOW, native5_public_preservation,
)


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


def test_retained_evidence_keeps_historical_public_file_identities():
    assert len(retained_documents()) == 3


def test_continuation_dispositions_have_exact_values_and_paths():
    entries = [item for item in dispositions() if "PR97 retained public" in item["description"]]
    assert len(entries) == 2
    for entry, paths, values in zip(entries, (BOUNDED_PATHS[:2], BOUNDED_PATHS[2:]),
                                   (BOUNDED_VALUES[:1], BOUNDED_VALUES[1:])):
        assert set(entry) == {"description", "condition", "regexTarget", "regexes", "paths"}
        assert entry["condition"] == "AND"
        assert entry["regexTarget"] == "secret"
        assert entry["paths"] == ["^" + re.escape(path).replace(r"\-", "-") + "$" for path in paths]
        assert entry["regexes"] == ["^(" + "|".join(values) + ")$"]


@pytest.mark.parametrize("path_index", range(3))
@pytest.mark.parametrize("value_index", range(3))
def test_continuation_values_cannot_cross_their_exact_paths(path_index, value_index):
    expected = (path_index < 2 and value_index == 0) or (path_index == 2 and value_index > 0)
    assert allowed(BOUNDED_PATHS[path_index], BOUNDED_VALUES[value_index]) is expected


@pytest.mark.parametrize("path", BOUNDED_PATHS)
@pytest.mark.parametrize("variant", ("prefix", "suffix", "sibling"))
def test_continuation_values_elsewhere_remain_detectable(path, variant):
    altered = {"prefix": "copied/" + path, "suffix": path + ".backup",
               "sibling": path.rsplit("/", 1)[0] + "/another.json"}[variant]
    assert all(not allowed(altered, value) for value in BOUNDED_VALUES)


@pytest.mark.parametrize("path", BOUNDED_PATHS)
@pytest.mark.parametrize("value", [hashlib.sha256(b"unrelated invented scanner regression value").hexdigest(),
    "x" + BOUNDED_VALUES[0], BOUNDED_VALUES[0] + "x", BOUNDED_VALUES[0].upper()])
def test_continuation_paths_do_not_allow_other_values(path, value):
    assert not allowed(path, value)


def test_native5_disposition_is_exact_public_blob_at_exact_preservation_path():
    document = json.loads(native5_public_preservation())
    assert document["protected_git_objects"][NATIVE5_WORKFLOW] == NATIVE5_PUBLIC_BLOB
    assert allowed(NATIVE5_PRESERVATION, NATIVE5_PUBLIC_BLOB)
    assert len(dispositions()) == 6
    entry = next(item for item in dispositions() if item["description"].startswith("Native5 recovery"))
    assert set(entry) == {"description", "condition", "regexTarget", "regexes", "paths"}
    assert entry["condition"] == "AND" and entry["regexTarget"] == "secret"
    assert entry["paths"] == ["^" + re.escape(NATIVE5_PRESERVATION).replace(r"\-", "-") + "$"]
    assert entry["regexes"] == ["^(" + NATIVE5_PUBLIC_BLOB + ")$"]


@pytest.mark.parametrize("path", ["copied/" + NATIVE5_PRESERVATION, NATIVE5_PRESERVATION + ".backup",
    NATIVE5_PRESERVATION.replace("preservation.json", "another.json"), "unrelated.txt", OBSERVATION])
def test_native5_public_blob_remains_detectable_elsewhere(path):
    assert not allowed(path, NATIVE5_PUBLIC_BLOB)


@pytest.mark.parametrize("value", [hashlib.sha256(b"unrelated invented scanner regression value").hexdigest(),
    "x" + NATIVE5_PUBLIC_BLOB, NATIVE5_PUBLIC_BLOB + "x", NATIVE5_PUBLIC_BLOB.upper(), PUBLIC_VALUES[0]])
def test_native5_path_does_not_allow_unrelated_or_altered_values(value):
    assert not allowed(NATIVE5_PRESERVATION, value)
