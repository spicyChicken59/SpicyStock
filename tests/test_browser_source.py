"""The browser reads Python's retained source identity, never a market replay."""
import base64
from copy import deepcopy
import gzip
import json
from pathlib import Path
import subprocess

import pytest

from src import provenance

ROOT = Path(__file__).resolve().parents[1]
FULL = json.loads((ROOT / "tests/fixtures/page/full.json").read_bytes())
OBJECTS = ROOT / "tests/fixtures/provenance/objects"

# Execute the actual shipped reader with web platform primitives, no network.
RUNNER = r"""
const fs = require('node:fs'), vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8')); let requests = [];
global.window = { SCStock: {}, crypto: require('node:crypto').webcrypto,
  DecompressionStream, setTimeout, clearTimeout,
  fetch: async (url, options) => {
    requests.push({url, credentials: options.credentials, redirect: options.redirect});
    return new Response(Buffer.from(input.bytes, 'base64'), {status: input.status || 200});
  }
};
const shipped = fs.readFileSync('docs/app.js', 'utf8');
vm.runInThisContext(shipped.slice(0, shipped.indexOf('})(window);') + '})(window);'.length));
(async () => {
  try {
    const series = await window.SCStock.loadSourceChart(input.row, input.record);
    const again = await window.SCStock.loadSourceChart(input.row, input.record);
    if (input.secondRef) { input.row.evidence.source.rows++; await window.SCStock.loadSourceChart(input.row, input.record); }
    process.stdout.write(JSON.stringify({series, requests, same: JSON.stringify(series) === JSON.stringify(again)}));
  } catch(e) { process.stdout.write(JSON.stringify({error: e.message, requests})); }
})();
"""


def read_browser(row, record=FULL, raw=None, **kwargs):
    if raw is None:
        raw = (OBJECTS / (row["evidence"]["source"]["sha256"] + ".json.gz")).read_bytes()
    result = subprocess.run(["node", "-e", RUNNER], cwd=ROOT, text=True,
                            input=json.dumps(dict(row=row, record=record, bytes=base64.b64encode(raw).decode(), **kwargs)),
                            capture_output=True, check=True, timeout=20)
    return json.loads(result.stdout)


@pytest.mark.parametrize("row", FULL["bursts"], ids=lambda row: row["ticker"])
def test_exact_python_source_frame_identity_and_cached_chart(row):
    result = read_browser(row)
    obj = json.loads(gzip.decompress((OBJECTS / (row["evidence"]["source"]["sha256"] + ".json.gz")).read_bytes()))
    expected = [dict(date=date, **dict(zip("ohlcv", values)))
                for date, *values in zip(obj["dates"], *obj["values"])][-120:]
    assert result.get("series") == expected, result
    assert result["same"]
    assert result["requests"] == [{"url": "evidence/" + row["evidence"]["source"]["sha256"] + ".json.gz",
                                    "credentials": "omit", "redirect": "error"}]


@pytest.mark.parametrize("change", ["hash", "row_count", "previous", "session", "ticker", "context", "version", "rules", "traversal"])
def test_wrong_object_or_reference_cannot_draw_a_chart(change):
    row = deepcopy(FULL["bursts"][0]); e = row["evidence"]
    raw = (OBJECTS / (e["source"]["sha256"] + ".json.gz")).read_bytes()
    if change == "hash": e["source"]["sha256"] = "0" * 64
    elif change == "row_count": e["source"]["rows"] += 1
    elif change == "previous": e["source"]["previous_session"] = "2026-09-08"
    elif change == "session": e["session"] = "2026-09-09"
    elif change == "ticker": e["ticker"] = "OTHER"
    elif change == "context": e["context_sha256"] = "0" * 64
    elif change == "version": e["version"] = 2
    elif change == "rules": e["rules_version"] = "other"
    elif change == "traversal": e["source"]["sha256"] = "../data"
    result = read_browser(row, raw=raw)
    assert "error" in result and "series" not in result
    assert len(result["requests"]) == (1 if change in ("hash", "row_count") else 0)


def test_cached_frame_still_checks_each_reference():
    result = read_browser(FULL["bursts"][0], secondRef=True)
    assert "sessions or row count" in result["error"]
    assert len(result["requests"]) == 1


@pytest.mark.parametrize("raw", [b"not gzip or json", gzip.compress(b" " * (provenance.MAX_OBJECT_BYTES + 1)),
                                  b"x" * (provenance.MAX_OBJECT_BYTES + 1)], ids=["malformed", "expanded_bound", "raw_bound"])
def test_invalid_or_overlarge_source_fails_closed(raw):
    assert "error" in read_browser(FULL["bursts"][0], raw=raw)


def test_http_failure_is_not_a_claim_of_no_market_data():
    result = read_browser(FULL["bursts"][0], status=404)
    assert "does not mean the stock has no data" in result["error"]


@pytest.mark.parametrize("decoded", [False, True])
def test_typed_float_identity_including_null_signed_zero_and_subnormal(decoded):
    # A source frame can contain gaps. Do not convert them into candles or lose
    # the float/int distinction just because JSON renders 100.0 as a number.
    frame = {"version": 1, "type": "frame", "columns": list(provenance.COLUMNS),
             "dates": ["2026-09-09", "2026-09-10"],
             "values": [[-0.0, 100.0], [float.fromhex("0x0.0000000000001p-1022"), 101.0],
                        [None, 99.0], [1.2345678912345678, 100.1], [1e20, 100000.0]]}
    row = deepcopy(FULL["bursts"][0]); row["evidence"]["source"].update(sha256=provenance.digest(frame), rows=2)
    raw = json.dumps(frame).encode()
    result = read_browser(row, raw=raw if decoded else gzip.compress(raw))
    assert "error" not in result, result
    assert result["series"][0]["l"] is None
    assert result["series"][0]["h"] == float.fromhex("0x0.0000000000001p-1022")


@pytest.mark.parametrize("damage", ["columns", "date_order", "invalid_date", "dimensions", "extra", "nonfinite"])
def test_even_a_matching_hash_must_have_a_valid_frame_shape(damage):
    row = deepcopy(FULL["bursts"][0]); source = row["evidence"]["source"]
    frame = json.loads(gzip.decompress((OBJECTS / (source["sha256"] + ".json.gz")).read_bytes()))
    if damage == "columns": frame["columns"][0] = "AdjustedOpen"
    elif damage == "date_order": frame["dates"][0] = frame["dates"][1]
    elif damage == "invalid_date": frame["dates"][0] = "2026-02-30"
    elif damage == "dimensions": frame["values"][0].pop()
    elif damage == "extra": frame["extra"] = "unrecognized"
    elif damage == "nonfinite": frame["values"][0][0] = "Infinity"
    source["sha256"] = provenance.digest(frame)
    assert "error" in read_browser(row, raw=gzip.compress(json.dumps(frame).encode()))
