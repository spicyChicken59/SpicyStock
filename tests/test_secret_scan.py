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
    PUBLIC_SITE_CAPTURE, PUBLIC_SITE_CAPTURE_SHA256, public_site_capture,
    CASH_PUBLICATIONS, CASH_RULE_IDENTIFIERS, ISSUER_PUBLICATIONS,
    ISSUER_RULE_IDENTIFIERS, ISSUER_DISPOSITION, public_rule_occurrences,
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
    assert len(dispositions()) == 11
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


def test_morning_rule_disposition_requires_exact_generated_path_and_public_value():
    values = ("abnormal_10pct", "down25_quarter", "pct_above_40ma")
    entry = next(item for item in dispositions() if "generated morning publication" in item["description"])
    assert set(entry) == {"description", "condition", "regexTarget", "regexes", "paths"}
    assert entry["condition"] == "AND" and entry["regexTarget"] == "secret"
    assert entry["regexes"] == ["^(" + "|".join(values) + ")$"]
    assert entry["paths"] == [r"^tests/fixtures/morning/(full|red)-publication\.json$"]
    for name in ("full", "red"):
        path = f"tests/fixtures/morning/{name}-publication.json"
        assert all(allowed(path, value) for value in values)
        for altered in ("copied/" + path, path + ".backup", path.replace(name + "-publication", "another")):
            assert all(not allowed(altered, value) for value in values)
        for value in (*PUBLIC_VALUES, "unrelated_rule", "x" + values[0], values[0] + "x", values[0].upper()):
            assert not allowed(path, value)


def test_reader_rule_disposition_requires_exact_asset_and_public_value():
    values = ("abnormal_10pct", "down25_quarter", "pct_above_40ma")
    entry = next(item for item in dispositions() if "generated compact reader" in item["description"])
    assert set(entry) == {"description", "condition", "regexTarget", "regexes", "paths"}
    assert entry["condition"] == "AND" and entry["regexTarget"] == "secret"
    assert entry["paths"] == [r"^docs/reader\.json$"]
    assert entry["regexes"] == ["^(" + "|".join(values) + ")$"]
    assert all(allowed("docs/reader.json", value) for value in values)
    for path in ("copied/docs/reader.json", "docs/reader.json.backup", "docs/another-reader.json"):
        assert all(not allowed(path, value) for value in values)
    for value in (*PUBLIC_VALUES, "unrelated_rule", "x" + values[0], values[0] + "x", values[0].upper()):
        assert not allowed("docs/reader.json", value)


def test_public_site_disposition_requires_pinned_capture_and_client_context():
    raw, identifier = public_site_capture()
    assert hashlib.sha256(raw).hexdigest() == PUBLIC_SITE_CAPTURE_SHA256
    assert allowed(PUBLIC_SITE_CAPTURE, identifier)
    entry = next(item for item in dispositions() if item["description"].startswith("Captured public reCAPTCHA"))
    assert set(entry) == {"description", "condition", "regexTarget", "regexes", "paths"}
    assert entry["condition"] == "AND" and entry["regexTarget"] == "secret"
    assert entry["paths"] == ["^" + re.escape(PUBLIC_SITE_CAPTURE).replace(r"\-", "-") + "$"]
    assert entry["regexes"] == ["^(" + re.escape(identifier).replace(r"\-", "-") + ")$"]


def test_public_site_identifier_remains_detectable_elsewhere():
    _, identifier = public_site_capture()
    for path in ("copied/" + PUBLIC_SITE_CAPTURE, PUBLIC_SITE_CAPTURE + ".backup",
                 PUBLIC_SITE_CAPTURE.replace("ir-merger-announcement.html", "another.html"), OBSERVATION):
        assert not allowed(path, identifier)


def test_public_site_path_does_not_allow_unrelated_or_altered_values():
    _, identifier = public_site_capture()
    altered = ("A" if identifier[0] != "A" else "B") + identifier[1:]
    for value in (altered, "x" + identifier, identifier + "x", identifier.upper(), PUBLIC_VALUES[0]):
        assert not allowed(PUBLIC_SITE_CAPTURE, value)


def test_cash_rule_disposition_requires_exact_publications_and_identifiers():
    entry = next(item for item in dispositions() if "generated cash-preview publications" in item["description"])
    assert set(entry) == {"description", "condition", "regexTarget", "regexes", "paths"}
    assert entry["condition"] == "AND" and entry["regexTarget"] == "secret"
    assert entry["regexes"] == ["^(" + "|".join(CASH_RULE_IDENTIFIERS) + ")$"]
    assert entry["paths"] == [r"^tests/fixtures/cash-preview/publication(-multiple)?\.json$"]
    for path in CASH_PUBLICATIONS:
        assert all(allowed(path, value) for value in CASH_RULE_IDENTIFIERS)


def test_cash_public_identifiers_remain_detectable_elsewhere():
    for path in CASH_PUBLICATIONS:
        for altered in ("copied/" + path, path + ".backup", path.replace("publication", "another")):
            assert all(not allowed(altered, value) for value in CASH_RULE_IDENTIFIERS)
    for name in ("observed", "observed-multiple", "halted", "corporate-excluded"):
        assert all(not allowed(f"tests/fixtures/cash-preview/{name}.json", value) for value in CASH_RULE_IDENTIFIERS)


def test_cash_publication_paths_do_not_allow_unrelated_or_altered_values():
    for path in CASH_PUBLICATIONS:
        for value in CASH_RULE_IDENTIFIERS:
            for altered in ("x" + value, value + "x", value.upper(), PUBLIC_VALUES[0]):
                assert not allowed(path, altered)


def test_issuer_rule_disposition_requires_exact_two_paths_and_three_identifiers():
    entry = next(item for item in dispositions() if item["description"] == ISSUER_DISPOSITION)
    assert set(entry) == {"description", "condition", "regexTarget", "regexes", "paths"}
    assert entry["condition"] == "AND" and entry["regexTarget"] == "secret"
    assert entry["regexes"] == ["^(" + "|".join(ISSUER_RULE_IDENTIFIERS) + ")$"]
    assert entry["paths"] == [r"^tests/fixtures/issuer-evidence/(publication|reader)\.json$"]
    for path in ISSUER_PUBLICATIONS:
        assert all(allowed(path, value) for value in ISSUER_RULE_IDENTIFIERS)
        occurrences = public_rule_occurrences((ROOT / path).read_bytes(), ISSUER_RULE_IDENTIFIERS)
        assert set(occurrences) == set(ISSUER_RULE_IDENTIFIERS)
        assert all(type(count) is int and count > 0 for count in occurrences.values())


@pytest.mark.parametrize("path", ISSUER_PUBLICATIONS)
@pytest.mark.parametrize("variant", ("prefix", "suffix", "sibling", "receipt", "bundle"))
def test_issuer_public_identifiers_remain_detectable_outside_exact_paths(path, variant):
    altered = {"prefix": "copied/" + path, "suffix": path + ".backup",
               "sibling": path.rsplit("/", 1)[0] + "/another.json",
               "receipt": "tests/fixtures/issuer-evidence/collected-receipt.json",
               "bundle": "tests/fixtures/issuer-evidence/collected-bundle.json"}[variant]
    assert all(not allowed(altered, value) for value in ISSUER_RULE_IDENTIFIERS)


@pytest.mark.parametrize("path", ISSUER_PUBLICATIONS)
@pytest.mark.parametrize("value", ISSUER_RULE_IDENTIFIERS)
def test_issuer_paths_do_not_allow_other_or_altered_values(path, value):
    for altered in ("x" + value, value + "x", value.upper(), "unrelated_rule", PUBLIC_VALUES[0]):
        assert not allowed(path, altered)


def test_rule_occurrence_count_requires_each_dispositioned_value():
    raw = json.dumps({"key": ISSUER_RULE_IDENTIFIERS[0]}).encode()
    with pytest.raises(ValueError, match="not_exercised"):
        public_rule_occurrences(raw, ISSUER_RULE_IDENTIFIERS)
