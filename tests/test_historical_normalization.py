"""Synthetic wire-only regressions; no provider data or credentials."""
from copy import deepcopy
import hashlib
import json

import pytest

from tools.historical_normalization import frames_for_replay, normalize_pages, decimal_event_audit


def query():
    return dict(symbols=["TEST"], start="2026-09-23T00:00:00Z", end="2026-09-25T23:59:59Z",
                asof="2026-09-26", feed="sip", timeframe="1Day", adjustment="split", currency="USD",
                limit=10000, sort="asc")


def row(day="2026-09-25", **changes):
    return dict(t=day + "T04:00:00Z", o=10, h=11, l=9, c=10, v=100001, **changes)


def page(rows, *, index=0, token=None, params=None, raw=None):
    raw = raw or json.dumps({"bars": {"TEST": rows}, "next_page_token": token}).encode()
    return dict(raw=raw, sha256=hashlib.sha256(raw).hexdigest(), query=params or query(),
                query_id="synthetic", page_index=index)


def normalize(pages, **kwargs):
    return normalize_pages(pages, query=query(), terminal=True, target_session="2026-09-25", **kwargs)


def test_complete_window_and_missing_anchors_do_not_fill():
    out = normalize([page([row("2026-09-23"), row("2026-09-24"), row()])])
    assert out["symbols"]["TEST"]["complete_required_window"]
    assert not out["publication_allowed"] and not out["reader_reviews_reusable"]
    missing = normalize([page([row()])])["symbols"]["TEST"]
    assert missing["status"] == "partial"
    assert missing["missing_anchors"] == ["2026-09-24"]
    assert missing["selected_rows"] == 1


def test_duplicate_retains_both_identities_selects_last_across_pages():
    a, b = row(), row()
    b["c"] = 10.25
    out = normalize([page([a], token="next"), page([b], index=1)])
    record = out["symbols"]["TEST"]
    assert record["returned_rows"] == 2 and record["selected_rows"] == 1
    assert record["rows"][0]["values"]["Close"] == "10.25"
    assert record["duplicates"][0]["discarded"]["page_index"] == 0
    assert record["duplicates"][0]["selected"]["page_index"] == 1


def test_decimal_wire_precision_survives_until_explicit_projection():
    raw = b'{"bars":{"TEST":[{"t":"2026-09-25T04:00:00Z","o":10,"h":11,"l":9,"c":10.00000000000000001,"v":100001}]},"next_page_token":null}'
    out = normalize([page([], raw=raw)])
    assert out["symbols"]["TEST"]["rows"][0]["values"]["Close"] == "10.00000000000000001"
    frames, projection = frames_for_replay(out)
    assert frames["TEST"].Close.iloc[0] == 10
    assert projection["inexact_conversions"][0]["decimal"] == "10.00000000000000001"


@pytest.mark.parametrize("field,value", [("c",0),("o",-1),("h",9.5),("l",10.5),("v",-1),
                                           ("c",None),("c",True),("t","2026-09-25"),
                                           ("t","2026-09-26T04:00:00Z"),
                                           ("t","2026-09-25T05:00:00Z")])
def test_malformed_row_is_unresolved_never_cleaned_into_replay(field, value):
    r = row(); r[field] = value
    out = normalize([page([r])])
    assert out["symbols"]["TEST"]["status"] == "unresolved"
    assert frames_for_replay(out)[0] == {}


@pytest.mark.parametrize("field,value", [("asof","2026-09-25"),("adjustment","raw"),
                                           ("symbols",["OTHER"]),("feed","iex")])
def test_mixed_mapping_symbols_or_split_raw_is_refused(field, value):
    p = page([row()]); p["query"][field] = value
    with pytest.raises(ValueError, match="mixed query"):
        normalize([p])


def test_interrupted_absent_cycle_and_duplicate_page_are_distinct():
    partial = normalize_pages([page([row()], token="next")], query=query(), terminal=False,
                              target_session="2026-09-25")
    assert partial["symbols"]["TEST"]["status"] == "partial"
    with pytest.raises(ValueError, match="terminal claim"):
        normalize([page([row()], token="next")])
    assert normalize([page([])])["symbols"]["TEST"]["status"] == "absent"
    with pytest.raises(ValueError, match="cyclic"):
        normalize([page([row()], token="a"), page([row("2026-09-24")], index=1, token="a")])
    p = page([row()], token="next"); duplicate = deepcopy(p); duplicate["page_index"] = 1
    with pytest.raises(ValueError, match="duplicated"):
        normalize([p, duplicate])
    p = page([row()]); p["raw"] += b" "
    with pytest.raises(ValueError, match="changed"):
        normalize([p])


def test_unexpected_symbol_and_outside_exchange_session_are_detected():
    p = page([], raw=b'{"bars":{"OTHER":[]},"next_page_token":null}')
    with pytest.raises(ValueError, match="unexpected symbol"):
        normalize([p])
    params = query(); params["start"] = "2026-09-19T00:00:00Z"
    out = normalize_pages([page([row("2026-09-19")], params=params)], query=params,
                          terminal=True, target_session="2026-09-25")
    assert out["symbols"]["TEST"]["status"] == "unresolved"


def test_zero_volume_is_valid_without_becoming_missing():
    r = row(); r["v"] = 0
    out = normalize([page([r])], required_sessions=["2026-09-25"])
    assert out["symbols"]["TEST"]["complete_required_window"]
    assert frames_for_replay(out)[0]["TEST"].Volume.iloc[0] == 0


def test_duplicate_json_keys_do_not_silently_replace_observations():
    p = page([], raw=b'{"bars":{"TEST":[],"TEST":[]},"next_page_token":null}')
    with pytest.raises(ValueError, match="duplicate JSON"):
        normalize([p])


def test_exact_wire_boundary_difference_survives_float_projection():
    raw = b'{"bars":{"TEST":[{"t":"2026-09-24T04:00:00Z","o":10,"h":11,"l":9,"c":10,"v":100000},{"t":"2026-09-25T04:00:00Z","o":10,"h":11,"l":9,"c":10.39999999999999999,"v":100001}]},"next_page_token":null}'
    audit = decimal_event_audit(normalize([page([], raw=raw)]))
    assert audit["differences"][0]["wire_decimal"]["up4"] is False
    assert audit["differences"][0]["production_float64"]["up4"] is True


def test_non_string_timestamp_remains_quarantined():
    r = row(); r["t"] = None
    assert normalize([page([r])])["symbols"]["TEST"]["status"] == "unresolved"
