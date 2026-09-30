"""Fresh synthetic projection representation; never uses retained provider data.

The untouched adapter fixture is the exact function from main 6284cb9, extracted
before comparison without importing the replacement implementation as its oracle.
"""
from copy import deepcopy
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

import pandas as pd
import pytest

from tools import historical_normalization as normalization

FIELDS = ("Open", "High", "Low", "Close", "Volume")
LEGACY = "historical-float64-projection-v1"
COMPACT = "historical-float64-projection-v2"
FIXTURE = Path(__file__).parent / "fixtures/projection-compaction/legacy_adapter.py"
FIXTURE_SHA = "9bdebd9b247d04a12898a59cfbb76ca9b57c4b60abaf6a706bc56832127a2956"


def old_adapter(normalized):
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA
    namespace = {"Decimal": Decimal, "math": math}
    exec(compile(raw, str(FIXTURE), "exec"), namespace)
    return namespace["frames_for_replay"](normalized)


def wire_row(day, mask=31, **overrides):
    exact = ("10", "20.5", "1.25", "11.1250", "100")
    inexact = ("10.1000", "20.2000000001", "1.00000000001", "1.11e1", "100.100000000001")
    values = {field: (inexact[bit] if mask & (1 << bit) else exact[bit])
              for bit, field in enumerate(("o", "h", "l", "c", "v"))}
    values.update(overrides)
    return '{"t":"' + day + 'T04:00:00Z",' + ','.join('"' + k + '":' + str(v) for k, v in values.items()) + '}'


def normalized(mask=31, *, overrides=None, duplicate=False, partial=False, empty=False, query_id="synthetic-query"):
    query = dict(symbols=["ALPHA", "BETA", "INVALID", "MISSING"],
                 start="2026-09-23T00:00:00Z", end="2026-09-25T23:59:59Z", asof="2026-09-26",
                 feed="sip", timeframe="1Day", adjustment="split", currency="USD", limit=10000, sort="asc")
    old = wire_row("2026-09-24", mask)
    latest = wire_row("2026-09-25", mask, **(overrides or {}))
    bars = {} if empty else {"ALPHA": [old, latest], "BETA": [latest],
                            "INVALID": [wire_row("2026-09-25", mask, v="-1")]}
    pages = []

    def add(items, token):
        raw = ('{"bars":{' + ','.join(json.dumps(s) + ':[' + ','.join(rows) + ']' for s, rows in items.items()) +
               '},"next_page_token":' + json.dumps(token) + '}').encode()
        pages.append(dict(raw=raw, sha256=hashlib.sha256(raw).hexdigest(), query=query,
                          query_id=query_id, page_index=len(pages)))

    add(bars, "next" if duplicate or partial else None)
    if duplicate:
        add({"ALPHA": [wire_row("2026-09-25", mask, c="11.300"),
                        wire_row("2026-09-25", mask, c="11.400000001")]}, "more")
        add({"ALPHA": [wire_row("2026-09-25", mask, c="11.50000000001")]}, None)
    return normalization.normalize_pages(pages, query=query, terminal=not partial,
        target_session="2026-09-25", required_sessions=["2026-09-24", "2026-09-25"])


def compact(value):
    return normalization.frames_for_replay(value, projection_contract=COMPACT)


def expanded(projection, value):
    return list(normalization.iter_projection_conversions(projection, value))


def assert_frames_equal(left, right):
    assert list(left) == list(right)
    for symbol in left:
        pd.testing.assert_frame_equal(left[symbol], right[symbol], check_exact=True)
        assert [[float(v).hex() for v in r] for r in left[symbol].itertuples(index=False, name=None)] == [
            [float(v).hex() for v in r] for r in right[symbol].itertuples(index=False, name=None)]


@pytest.mark.parametrize("mask", range(32))
def test_compact_all_field_combinations_equal_untouched_adapter(mask):
    value = normalized(mask)
    saved = deepcopy(value)
    before_frames, before = old_adapter(value)
    frames, projection = compact(value)
    assert_frames_equal(frames, before_frames)
    assert expanded(projection, value) == before["inexact_conversions"], "conversion facts differ from untouched adapter"
    assert projection["rows"] == [[i, mask, [fact["float64_hex"] for fact in before["inexact_conversions"][
        i * mask.bit_count():(i + 1) * mask.bit_count()]]] for i in range(3)]
    assert projection["conversion_count"] == 3 * mask.bit_count()
    assert value == saved
    assert "inexact_conversions" not in projection


def test_legacy_explicit_contract_is_untouched_adapter_control():
    value = normalized(31, duplicate=True)
    frames, facts = normalization.frames_for_replay(value, projection_contract=LEGACY)
    before_frames, before_facts = old_adapter(value)
    assert_frames_equal(frames, before_frames)
    assert facts == before_facts
    assert "schema" not in facts


@pytest.mark.parametrize("volume", ["0", "-0.00", "0E-9", "-0e5", "100.1250", "1.00100000000001e2"])
def test_compact_decimal_spelling_exponent_and_zero_equal_original(volume):
    value = normalized(31, overrides={"v": volume})
    before_frames, before = old_adapter(value)
    frames, projection = compact(value)
    assert_frames_equal(frames, before_frames)
    assert expanded(projection, value) == before["inexact_conversions"]
    assert value["symbols"]["ALPHA"]["rows"][-1]["values"]["Volume"] == str(Decimal(volume))


def test_compact_decimal_binary_values_have_independent_known_answers():
    value = normalized(31)
    frames, projection = compact(value)
    facts = expanded(projection, value)
    assert facts[0] == dict(symbol="ALPHA", session="2026-09-24", field="Open",
                           decimal="10.1000", float64_hex="0x1.4333333333333p+3")
    assert Decimal.from_float(float.fromhex(facts[0]["float64_hex"])) == Decimal(
        "10.0999999999999996447286321199499070644378662109375")
    assert Decimal(facts[0]["decimal"]) == Decimal("10.1")
    assert frames["ALPHA"].Open.iloc[0].hex() == "0x1.4333333333333p+3"
    assert next(f for f in facts if f["field"] == "Close")["decimal"] == "11.1"
    # Exact rational distances independently check nearest rounding for long
    # OHLC decimals and fractional volume, without float(decimal) as an oracle.
    # These deliberately chosen observations are inexact and are not midpoint ties.
    for fact in facts:
        exact = Fraction(Decimal(fact["decimal"]))
        represented = float.fromhex(fact["float64_hex"])
        error = abs(exact - Fraction.from_float(represented))
        assert error > 0
        for direction in (-math.inf, math.inf):
            neighbor = Fraction.from_float(math.nextafter(represented, direction))
            assert error < abs(exact - neighbor), fact


def test_compact_duplicate_lineage_binds_final_selected_source_and_every_replacement():
    value = normalized(31, duplicate=True)
    old_frames, old = old_adapter(value)
    frames, projection = compact(value)
    assert_frames_equal(frames, old_frames)
    assert expanded(projection, value) == old["inexact_conversions"]
    record = value["symbols"]["ALPHA"]
    assert len(record["duplicates"]) == 3
    assert record["rows"][-1]["source"]["page_index"] == 2
    assert record["rows"][-1]["source"]["row_index"] == 0
    assert next(f for f in expanded(projection, value) if f["symbol"] == "ALPHA" and
                f["session"] == "2026-09-25" and f["field"] == "Close")["decimal"] == "11.50000000001"


@pytest.mark.parametrize("partial,empty", [(False, False), (True, False), (False, True), (True, True)])
def test_compact_missing_invalid_partial_and_unknowns_preserve_all_normalization(partial, empty):
    value = normalized(31, partial=partial, empty=empty)
    saved = deepcopy(value)
    before_frames, before = old_adapter(value)
    audit = normalization.decimal_event_audit(value)
    frames, projection = compact(value)
    assert_frames_equal(frames, before_frames)
    assert expanded(projection, value) == before["inexact_conversions"]
    assert "INVALID" not in frames and "MISSING" not in frames
    assert value == saved and normalization.decimal_event_audit(value) == audit


def test_compact_sorted_json_roundtrip_is_deterministic_and_decodes_original_order():
    value = normalized(31, duplicate=True)
    value["decimal_event_audit"] = normalization.decimal_event_audit(value)
    frames, projection = compact(value)
    before = old_adapter(value)[1]["inexact_conversions"]
    encode = lambda x: json.dumps(x, sort_keys=True, separators=(",", ":")).encode()
    assert encode(projection) == encode(compact(value)[1])
    parsed_value, parsed_projection = json.loads(encode(value)), json.loads(encode(projection))
    assert expanded(parsed_projection, parsed_value) == before
    assert encode(projection) == encode(compact(parsed_value)[1])


@pytest.mark.parametrize("change", [
    lambda p: p.update(schema="historical-float64-projection-v99"),
    lambda p: p.pop("rows"),
    lambda p: p.update(unrecognized=True),
    lambda p: p.update(operation="another operation"),
    lambda p: p["fields"].reverse(),
    lambda p: p.update(query_id="other-query"),
    lambda p: p.update(query_sha256="0" * 64),
    lambda p: p.update(normalization_sha256="0" * 64),
    lambda p: p.update(conversion_count=True),
    lambda p: p.update(conversion_count=-1),
    lambda p: p.update(conversion_count=p["conversion_count"] + 1),
    lambda p: p["rows"].pop(),
    lambda p: p["rows"].append(deepcopy(p["rows"][-1])),
    lambda p: p["rows"].reverse(),
    lambda p: p["rows"][0].__setitem__(0, 1),
    lambda p: p["rows"][0].__setitem__(0, False),
    lambda p: p["rows"][0].__setitem__(1, True),
    lambda p: p["rows"][0].__setitem__(1, 32),
    lambda p: p["rows"][0].__setitem__(1, -1),
    lambda p: p["rows"][0].__setitem__(2, "not a list"),
    lambda p: p["rows"][0][2].pop(),
    lambda p: p["rows"][0][2].append("0x1.0p+0"),
    lambda p: p["rows"][0][2].__setitem__(0, "0x1.0p+0"),
    lambda p: p["rows"][0][2].__setitem__(0, "0X1.4333333333333P+3"),
    lambda p: p["rows"][0][2].__setitem__(0, float("nan")),
    lambda p: p["rows"][0][2].__setitem__(0, "x" * 33),
    lambda p: p["rows"].__setitem__(0, [0, 15, p["rows"][0][2][:4]]),
], ids=["schema", "missing_rows_key", "extra_key", "operation", "field_order", "query_id", "query_digest",
        "normalization_digest", "boolean_count", "negative_count", "wrong_count", "omitted_row", "extra_row",
        "reordered_rows", "other_valid_row_ref", "boolean_ref", "boolean_mask", "unknown_mask_bit",
        "negative_mask", "values_type", "missing_value", "extra_value", "wrong_float", "noncanonical_hex",
        "non_string_value", "oversized_hex", "omitted_inexact_field"])
def test_compact_decoder_rejects_malformed_or_lossy_representation_before_yield(change):
    value = normalized(31)
    projection = compact(value)[1]
    change(projection)
    iterator = normalization.iter_projection_conversions(projection, value)
    with pytest.raises(ValueError, match="projection"):
        next(iterator)


@pytest.mark.parametrize("field,new", [("asof", "2026-09-25"), ("start", "2026-09-22T00:00:00Z"),
    ("end", "2026-09-24T23:59:59Z"), ("feed", "iex"), ("currency", "EUR"),
    ("adjustment", "raw"), ("timeframe", "1Hour"), ("sort", "desc"), ("limit", 9999)])
def test_compact_decoder_binds_complete_query_basis(field, new):
    value = normalized(31)
    projection = compact(value)[1]
    value["query"][field] = new
    with pytest.raises(ValueError, match="binding"):
        expanded(projection, value)


@pytest.mark.parametrize("change", [
    lambda n: n.update(query_id="different-security-query"),
    lambda n: n.update(target_session="2026-09-24"),
    lambda n: n["symbols"]["ALPHA"]["rows"][0]["values"].update(Open="10.10000"),
    lambda n: n["symbols"]["ALPHA"]["rows"][0]["values"].update(Open="10.2"),
    lambda n: n["symbols"]["ALPHA"]["rows"][0].update(session="2026-09-23"),
    lambda n: n["symbols"]["ALPHA"]["rows"][0].update(timestamp="2026-09-23T04:00:00Z"),
    lambda n: n["symbols"]["ALPHA"]["rows"][0]["source"].update(symbol="BETA"),
    lambda n: n["symbols"]["ALPHA"]["rows"][0]["source"].update(row_index=1),
    lambda n: n["symbols"]["ALPHA"]["rows"][0]["source"].update(page_sha256="0" * 64),
    lambda n: n["symbols"]["ALPHA"]["duplicates"][0]["discarded"].update(row_index=0),
    lambda n: n["symbols"]["INVALID"].update(invalid_rows=[]),
    lambda n: n["symbols"]["ALPHA"]["rows"].reverse(),
], ids=["query_identity", "target", "decimal_spelling", "decimal_value", "session", "timestamp", "security",
        "source_row", "source_page", "discarded_lineage", "invalid_status", "selected_order"])
def test_compact_decoder_binds_exact_selected_normalization_and_lineage(change):
    value = normalized(31, duplicate=True)
    projection = compact(value)[1]
    change(value)
    with pytest.raises(ValueError, match="binding"):
        expanded(projection, value)


def test_compact_zero_mask_row_omission_is_not_empty_evidence():
    value = normalized(0)
    projection = compact(value)[1]
    assert projection["conversion_count"] == 0 and len(projection["rows"]) == 3
    projection["rows"].pop()
    with pytest.raises(ValueError, match="missing"):
        expanded(projection, value)


def test_compact_decoder_explicit_row_bound_is_enforced(monkeypatch):
    value = normalized(31)
    projection = compact(value)[1]
    monkeypatch.setattr(normalization, "MAX_PROJECTION_ROWS", 2)
    with pytest.raises(ValueError, match="bounds"):
        expanded(projection, value)
    with pytest.raises(ValueError, match="row limit"):
        compact(value)


def test_compact_does_not_reuse_projection_for_repeated_ticker_session_query():
    first = normalized(31, query_id="observation-one")
    second = normalized(31, query_id="observation-two")
    projection = compact(first)[1]
    assert old_adapter(first)[1] == old_adapter(second)[1]
    with pytest.raises(ValueError, match="binding"):
        expanded(projection, second)


def test_compact_unsupported_encoder_contract_is_refused():
    with pytest.raises(ValueError, match="contract"):
        normalization.frames_for_replay(normalized(), projection_contract="future-v99")


@pytest.mark.parametrize("change", [
    lambda n: n.update(version="future-normalization-v99"),
    lambda n: n["symbols"]["ALPHA"].update(selected_rows=True),
    lambda n: n["symbols"]["ALPHA"].update(selected_rows=99),
    lambda n: n["symbols"]["ALPHA"]["rows"].append(deepcopy(n["symbols"]["ALPHA"]["rows"][-1])),
    lambda n: n["symbols"]["ALPHA"]["rows"].reverse(),
    lambda n: n["symbols"]["ALPHA"]["rows"][0].update(session="2026-09-23"),
    lambda n: n["symbols"]["ALPHA"]["rows"][0]["source"].update(symbol="BETA"),
    lambda n: n["symbols"]["ALPHA"]["rows"][0]["source"].update(page_index=999),
    lambda n: n["symbols"]["ALPHA"]["rows"][0]["source"].update(page_index=True),
    lambda n: n["symbols"]["ALPHA"]["rows"][0]["source"].update(row_index=True),
    lambda n: n["symbols"]["ALPHA"]["rows"][0]["source"].update(row_index=-1),
    lambda n: n["symbols"]["ALPHA"]["rows"][0]["source"].update(row_index=n["query"]["limit"]),
    lambda n: n["symbols"]["ALPHA"]["rows"][0]["source"].update(page_sha256="0" * 64),
    lambda n: n["symbols"]["ALPHA"]["rows"][0]["source"].update(extra="unexpected"),
    lambda n: n["symbols"]["ALPHA"]["rows"][0]["values"].update(Open=10.1),
    lambda n: n["symbols"]["ALPHA"]["rows"][0]["values"].update(Volume=100),
    lambda n: n["symbols"]["ALPHA"]["rows"][0]["values"].pop("Close"),
], ids=["version", "boolean_row_count", "row_count", "duplicate_selected_row", "row_order", "session",
        "source_symbol", "source_page_index", "source_boolean_page", "source_boolean_row", "source_negative_row",
        "source_past_page_limit", "source_hash", "source_extra_key", "numeric_decimal", "integer_decimal", "missing_field"])
def test_compact_recomputed_context_cannot_legitimize_malformed_normalized_selection(change):
    value = normalized(31)
    projection = compact(value)[1]
    change(value)
    # Bypass only the digest mismatch so this tests the malformed selected-row
    # contract itself. A hash of a malformed context is not normalization proof.
    projection["normalization_sha256"] = normalization._projection_digest(value)
    with pytest.raises(ValueError, match="projection"):
        expanded(projection, value)
    with pytest.raises(ValueError, match="projection"):
        compact(value)


def test_compact_recomputed_context_rejects_duplicate_even_with_matching_count():
    value = normalized(31)
    projection = compact(value)[1]
    record = value["symbols"]["ALPHA"]
    record["rows"].append(deepcopy(record["rows"][-1]))
    record["selected_rows"] += 1
    projection["normalization_sha256"] = normalization._projection_digest(value)
    with pytest.raises(ValueError, match="ambiguous"):
        expanded(projection, value)
    with pytest.raises(ValueError, match="ambiguous"):
        compact(value)


def test_compact_complete_validation_precedes_first_fact_even_if_last_row_corrupt():
    value = normalized(31)
    projection = compact(value)[1]
    projection["rows"][-1][2][-1] = "0x1.0p+0"
    with pytest.raises(ValueError, match="float64"):
        next(normalization.iter_projection_conversions(projection, value))


def test_compact_recomputed_context_rejects_one_raw_source_used_for_two_sessions():
    value = normalized(31)
    projection = compact(value)[1]
    rows = value["symbols"]["ALPHA"]["rows"]
    rows[1]["source"] = deepcopy(rows[0]["source"])
    projection["normalization_sha256"] = normalization._projection_digest(value)
    with pytest.raises(ValueError, match="source identity is ambiguous"):
        expanded(projection, value)
    with pytest.raises(ValueError, match="source identity is ambiguous"):
        compact(value)


def test_compact_same_page_and_row_index_for_different_symbols_is_valid_control():
    value = normalized(31)
    alpha = value["symbols"]["ALPHA"]["rows"][0]["source"]
    beta = value["symbols"]["BETA"]["rows"][0]["source"]
    assert (alpha["page_index"], alpha["row_index"]) == (beta["page_index"], beta["row_index"]) == (0, 0)
    assert alpha["symbol"] != beta["symbol"]
    assert expanded(compact(value)[1], value) == old_adapter(value)[1]["inexact_conversions"]


@pytest.mark.parametrize("digest", ["not-a-sha256", "A" * 64, "g" * 64, "0" * 63, 0])
def test_compact_recomputed_matching_page_hash_must_still_be_canonical(digest):
    value = normalized(31)
    projection = compact(value)[1]
    for record in value["symbols"].values():
        for row in record["rows"]:
            row["source"]["page_sha256"] = digest
    value["page_sha256"] = [digest]
    projection["normalization_sha256"] = normalization._projection_digest(value)
    with pytest.raises(ValueError, match="source identity"):
        expanded(projection, value)
    with pytest.raises(ValueError, match="source identity"):
        compact(value)


@pytest.mark.parametrize("limit", [None, True, 0, -1, 10001, "10000"])
def test_compact_recomputed_query_limit_must_be_bounded_integer(limit):
    value = normalized(31)
    projection = compact(value)[1]
    value["query"]["limit"] = limit
    projection["query_sha256"] = normalization._projection_digest(value["query"])
    projection["normalization_sha256"] = normalization._projection_digest(value)
    with pytest.raises(ValueError, match="aggregate page limit"):
        expanded(projection, value)
    with pytest.raises(ValueError, match="aggregate page limit"):
        compact(value)


def test_compact_inexactness_rule_restored_defect_is_observable(monkeypatch):
    value = normalized(31)
    before = old_adapter(value)[1]["inexact_conversions"]
    monkeypatch.setattr(normalization, "_projection_row_values", lambda row: (0, []))
    projection = compact(value)[1]
    # This is the reviewed size-model defect: reporting no conversion evidence
    # for genuinely inexact decimals. Compare to the independently frozen oracle.
    assert expanded(projection, value) != before
    assert len(before) == 15


def test_compact_unrelated_audit_mutation_does_not_change_projection_facts(monkeypatch):
    value = normalized(31)
    before = old_adapter(value)[1]["inexact_conversions"]
    monkeypatch.setattr(normalization, "decimal_event_audit", lambda _: {"unrelated": "mutant"})
    assert expanded(compact(value)[1], value) == before
