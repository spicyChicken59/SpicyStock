"""The SEC access diagnostic: requests for a few issuers through the collector's transport, no address."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from src import issuer_evidence
from tools import probe_sec_access as probe

CIK = 320193
SUBMISSIONS = f"https://data.sec.gov/submissions/CIK{CIK:010d}.json"
AT = datetime(2026, 10, 19, 13, 30, tzinfo=timezone.utc)


def mapping(rows=(( CIK, "Apple Inc.", "AAPL", "Nasdaq"), (789019, "MICROSOFT CORP", "MSFT", "Nasdaq"))):
    return json.dumps({"fields": ["cik", "name", "ticker", "exchange"], "data": [list(r) for r in rows]}).encode()


def submissions(cik=CIK, tickers=("AAPL",), forms=("8-K", "10-Q", "DEF 14A")):
    recent = {"accessionNumber": [], "filingDate": [], "reportDate": [], "acceptanceDateTime": [],
              "form": [], "items": [], "primaryDocument": []}
    for i, form in enumerate(forms):
        day = (AT.date() - timedelta(days=10 + i)).isoformat()
        recent["accessionNumber"].append(f"0000320193-26-{i + 1:06d}")
        recent["filingDate"].append(day)
        recent["reportDate"].append(day)
        recent["acceptanceDateTime"].append(f"{day}T16:30:00.000Z")
        recent["form"].append(form)
        recent["items"].append("")
        recent["primaryDocument"].append(f"doc{i}.htm")
    return json.dumps({"cik": str(cik), "tickers": list(tickers), "filings": {"recent": recent, "files": []}}).encode()


class Transport:
    """The real transport's contract: begin a request on the budget, then answer or raise."""

    def __init__(self, answers):
        self.answers = dict(answers)
        self.calls = []

    def fetch(self, url, budget):
        budget.begin_request()
        self.calls.append(url)
        answer = self.answers[url]
        if isinstance(answer, Exception):
            raise answer
        return {"body": answer, "observed_at": AT}


def run(answers, tickers=("AAPL",)):
    transport = Transport(answers)
    return probe.probe(transport=transport, clock=lambda: AT, tickers=tickers), transport


def one(result):
    (issuer,) = result["issuers"]
    return issuer


def test_both_answers_name_the_issuer_and_carry_no_body_or_address():
    result, transport = run({issuer_evidence.MAPPING_URL: mapping(), SUBMISSIONS: submissions()})
    assert transport.calls == [issuer_evidence.MAPPING_URL, SUBMISSIONS]
    assert result["answered"] is True and result["refused_statuses"] == []
    assert result["request_count"] == 2
    assert [r["phase"] for r in result["requests"]] == ["mapping", "submissions:AAPL"]
    assert [r["outcome"] for r in result["requests"]] == ["ok", "ok"]
    assert result["requests"][1]["sha256"] == issuer_evidence._sha(submissions())
    assert result["requests"][1]["bytes"] == len(submissions())
    assert one(result)["identity"] == {"status": "verified", "cik": CIK, "name": "Apple Inc.", "reason": None}
    assert one(result)["submissions"] == {"status": "parsed", "filings_in_window": 3, "history_files_advertised": 0,
                                          "invalid_count": 0,
                                          "rejected_rows": {"count": 0, "by_rule": {}, "by_form": {}, "rows": []}}
    assert result["tickers"] == ["AAPL"] and result["schema"] == "spicystock-sec-probe-v3"
    assert result["sentence"] == "SEC answered all 2 requests from this runner."
    assert result["user_agent"] == {"names_sender": True, "names_contact": True}
    text = json.dumps(result)
    assert "@" not in text and issuer_evidence.USER_AGENT not in text
    assert "Apple Inc." in text and "doc0.htm" not in text  # the identity, never a filing body
    assert result["limits"] == probe.LIMITS and "publication" not in result


def test_a_refused_mapping_asks_nothing_more_and_names_its_status():
    result, transport = run({issuer_evidence.MAPPING_URL: issuer_evidence.SourceError("http_error", http_status=403)})
    assert transport.calls == [issuer_evidence.MAPPING_URL]
    assert result["answered"] is False and result["refused_statuses"] == [403]
    assert result["requests"] == [{"phase": "mapping", "url": issuer_evidence.MAPPING_URL, "outcome": "http_error",
                                   "http_status": 403, "bytes": None, "sha256": None, "checked_at": None}]
    assert one(result)["identity"]["status"] == one(result)["submissions"]["status"] == "not_reached"
    assert result["sentence"] == "SEC did not answer the mapping request from this runner: HTTP 403."


def test_a_refused_submissions_request_is_named_after_a_verified_identity():
    result, transport = run({issuer_evidence.MAPPING_URL: mapping(),
                             SUBMISSIONS: issuer_evidence.SourceError("rate_limit", http_status=429)})
    assert transport.calls == [issuer_evidence.MAPPING_URL, SUBMISSIONS]
    assert one(result)["identity"]["status"] == "verified" and one(result)["submissions"]["status"] == "unavailable"
    assert result["answered"] is False and result["refused_statuses"] == [429]
    assert result["sentence"] == "SEC did not answer the submissions:AAPL request from this runner: HTTP 429."


def test_a_network_failure_has_no_status_and_says_so():
    result, _ = run({issuer_evidence.MAPPING_URL: issuer_evidence.SourceError("network_error")})
    assert result["requests"][0]["http_status"] is None and result["refused_statuses"] == []
    assert result["sentence"] == "SEC did not answer the mapping request from this runner: network_error."


def test_an_answer_that_does_not_establish_the_issuer_is_not_access():
    result, transport = run({issuer_evidence.MAPPING_URL: mapping(rows=((789019, "MICROSOFT CORP", "MSFT", "Nasdaq"),))})
    assert transport.calls == [issuer_evidence.MAPPING_URL]
    assert one(result)["identity"] == {"status": "unverified", "cik": None, "name": None, "reason": "identity_unverified"}
    assert result["answered"] is False
    assert result["sentence"] == "SEC answered, and the answer did not establish every issuer asked for (AAPL)."
    other, _ = run({issuer_evidence.MAPPING_URL: mapping(), SUBMISSIONS: submissions(tickers=("MSFT",))})
    assert one(other)["submissions"]["status"] == "invalid" and other["answered"] is False
    assert other["sentence"] == "SEC answered, and the answer did not establish every issuer asked for (AAPL)."
    empty, _ = run({issuer_evidence.MAPPING_URL: b""})
    assert empty["requests"][0]["outcome"] == "invalid_response" and empty["answered"] is False


def test_the_probe_measures_the_network_through_the_collectors_transport(monkeypatch):
    made = []

    class Recorder(Transport):
        def __init__(self, cache_dir="unset"):
            made.append(cache_dir)
            super().__init__({issuer_evidence.MAPPING_URL: issuer_evidence.SourceError("timeout")})

    monkeypatch.setattr(issuer_evidence, "_Transport", Recorder)
    result = probe.probe(clock=lambda: AT)
    assert made == [None]  # no cache: a cached mapping would say nothing of today's access
    assert result["requests"][0]["outcome"] == "timeout" and result["request_count"] == 1


def test_the_user_agent_is_described_and_never_copied():
    assert probe.user_agent_shape() == {"names_sender": True, "names_contact": True}
    assert probe.user_agent_shape("SpicyStock https://example.com/x") == {"names_sender": True, "names_contact": False}
    assert probe.user_agent_shape("someone@example.com") == {"names_sender": False, "names_contact": True}
    assert probe.user_agent_shape("") == {"names_sender": False, "names_contact": False}


def test_the_diagnostic_cannot_reach_public_files_overwrite_or_carry_the_address(tmp_path, monkeypatch):
    public = tmp_path / "docs"
    public.mkdir()
    monkeypatch.setattr(probe, "PUBLIC_ROOT", public)
    with pytest.raises(ValueError, match="public docs"):
        probe.write_probe(public / "issuer-evidence.json", {})
    with pytest.raises(ValueError, match="public docs"):
        probe.write_probe(public, {})
    kept = tmp_path / "probe.json"
    kept.write_text("keep")
    with pytest.raises(FileExistsError):
        probe.write_probe(kept, {})
    assert kept.read_text() == "keep"
    with pytest.raises(ValueError, match="contact address"):
        probe.write_probe(tmp_path / "leak.json", {"agent": issuer_evidence.USER_AGENT})
    with pytest.raises(ValueError, match="contact address"):
        probe.write_probe(tmp_path / "leak2.json", {"note": "write to someone@example.com"})
    assert not (tmp_path / "leak.json").exists() and not (tmp_path / "leak2.json").exists()
    result, _ = run({issuer_evidence.MAPPING_URL: mapping(), SUBMISSIONS: submissions()})
    payload = probe.write_probe(tmp_path / "new.json", result)
    assert json.loads((tmp_path / "new.json").read_text()) == result == json.loads(payload)


def test_main_prints_the_result_and_hides_a_raw_failure(tmp_path, monkeypatch, capsys):
    result, _ = run({issuer_evidence.MAPPING_URL: issuer_evidence.SourceError("http_error", http_status=403)})
    monkeypatch.setattr(probe, "probe", lambda tickers: result)
    assert probe.main(["--output", str(tmp_path / "out.json")]) == 0
    printed = capsys.readouterr().out
    assert json.loads(printed) == result == json.loads((tmp_path / "out.json").read_text())

    def broken(tickers):
        raise RuntimeError("secret detail from a raw response")

    monkeypatch.setattr(probe, "probe", broken)
    assert probe.main(["--output", str(tmp_path / "other.json")]) == 1
    printed = capsys.readouterr().out
    assert printed == "SEC access diagnostic failed; no raw error was logged.\n"
    assert not (tmp_path / "other.json").exists()


def test_a_clock_that_moves_backwards_is_refused():
    ticks = iter([AT, AT - timedelta(seconds=1)])
    with pytest.raises(ValueError, match="backwards"):
        probe.probe(transport=Transport({issuer_evidence.MAPPING_URL: issuer_evidence.SourceError("timeout")}),
                    clock=lambda: next(ticks))


ZIM_CIK = 1654126
ZIM_SUBMISSIONS = f"https://data.sec.gov/submissions/CIK{ZIM_CIK:010d}.json"


def rows_submissions(rows, cik=CIK, tickers=("AAPL",)):
    """A submissions answer whose recent rows are given whole, one dict a row."""
    keys = ("accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form", "items", "primaryDocument")
    recent = {key: [row[key] for row in rows] for key in keys}
    recent["size"] = [1 for _ in rows]  # another parallel SEC column the collector reads past
    return json.dumps({"cik": str(cik), "tickers": list(tickers), "filings": {"recent": recent, "files": []}}).encode()


def good_row(n, **changes):
    day = (AT.date() - timedelta(days=5 + n)).isoformat()
    row = {"accessionNumber": f"0000320193-26-{n + 1:06d}", "filingDate": day, "reportDate": day,
           "acceptanceDateTime": f"{day}T16:30:00.000Z", "form": "8-K", "items": "2.02,9.01",
           "primaryDocument": f"doc{n}.htm"}
    row.update(changes)
    return row


# One row per rule, each failing only that rule, in the collector's order.
REFUSED = [
    ("accepted_at", good_row(1, acceptanceDateTime="2026-10-01 16:30:00"), "2026-10-01 16:30:00"),
    ("accession", good_row(2, accessionNumber="0000320193-26-12"), "0000320193-26-12"),
    ("form", good_row(3, form="X" * 33), "X" * 33),
    # A current report is listed and fetched by its document: never under a rendering directory.
    ("primary_document", good_row(4, primaryDocument="xslF345X05/wf-form4.xml"), "xslF345X05/wf-form4.xml"),
    # An acquisition form is listed and linked by its document: never without one.
    ("primary_document", good_row(5, form="SC 14D9", primaryDocument=""), ""),
    ("items", good_row(6, items=None), "<null>"),
    ("filing_date", good_row(7, filingDate="2026-9-30"), "2026-9-30"),
    ("report_date", good_row(8, reportDate="2026-02-30"), "2026-02-30"),
    ("future_acceptance", good_row(9, acceptanceDateTime="2026-10-19T13:31:00Z"), "2026-10-19T13:31:00Z"),
    ("future_filing_date", good_row(10, filingDate="2026-10-20"), "2026-10-20"),
]


def test_each_refused_row_is_named_by_the_rule_the_collector_refused_it_under():
    rows = [good_row(0)] + [row for _, row, _ in REFUSED]
    raw = rows_submissions(rows)
    parsed = issuer_evidence.parse_submissions(raw, CIK, "AAPL", AT)
    assert parsed["invalid_count"] == len(REFUSED) and len(parsed["filings"]) == 1
    result, _ = run({issuer_evidence.MAPPING_URL: mapping(), SUBMISSIONS: raw})
    submissions = one(result)["submissions"]
    assert submissions["status"] == "parsed" and submissions["invalid_count"] == len(REFUSED)
    rejected = submissions["rejected_rows"]
    assert rejected["count"] == len(REFUSED)
    assert [(r["rule"], r["value"]) for r in rejected["rows"]] == [(rule, value) for rule, _, value in REFUSED]
    assert [r["form"] for r in rejected["rows"]] == [row["form"] for _, row, _ in REFUSED]
    # Each refused row's filing date, in its own characters, says whether it falls in the window.
    assert [r["filing_date"] for r in rejected["rows"]] == [row["filingDate"] for _, row, _ in REFUSED]
    assert rejected["by_rule"] == {rule: sum(1 for r, _, _ in REFUSED if r == rule) for rule, _, _ in REFUSED}
    assert rejected["by_form"] == {"8-K": 8, "SC 14D9": 1, "X" * 33: 1}
    assert list(rejected["by_rule"]) == sorted(rejected["by_rule"])
    assert {rule for rule, _, _ in REFUSED} == set(probe.ROW_RULES)


def test_the_rules_are_asked_in_the_collectors_order():
    # A row failing two rules is named by the first the collector asks.
    both = good_row(1, accessionNumber="bad", primaryDocument="a/b.xml")
    result, _ = run({issuer_evidence.MAPPING_URL: mapping(), SUBMISSIONS: rows_submissions([good_row(0), both])})
    assert one(result)["submissions"]["rejected_rows"]["rows"] == [{"form": "8-K", "rule": "accession", "value": "bad",
                                                                     "filing_date": both["filingDate"]}]


def test_a_refused_value_is_printed_in_its_own_characters_only_and_bounded():
    assert probe.shown("xslF345X05/wf-form4_1.xml") == "xslF345X05/wf-form4_1.xml"
    assert probe.shown("a b:c+d-e.f") == "a b:c+d-e.f"
    assert probe.shown("x@y.z\n<script>") == "x?y.z??script?"
    assert probe.shown("z" * 200) == "z" * probe.MAX_VALUE_CHARS + "..."
    assert probe.shown(None) == "<null>" and probe.shown(7) == "<int>" and probe.shown(["a"]) == "<list>"
    leaky = good_row(1, primaryDocument="someone@example.com.htm")
    result, _ = run({issuer_evidence.MAPPING_URL: mapping(), SUBMISSIONS: rows_submissions([leaky])})
    assert one(result)["submissions"]["rejected_rows"]["rows"][0]["value"] == "someone?example.com.htm"
    assert "@" not in json.dumps(result)


def test_every_refused_row_is_counted_and_only_the_first_are_printed():
    many = [good_row(i, form="4", primaryDocument=f"xslF345X05/{i}/f.xml") for i in range(probe.MAX_REJECTED_ROWS + 5)]
    result, _ = run({issuer_evidence.MAPPING_URL: mapping(), SUBMISSIONS: rows_submissions(many)})
    rejected = one(result)["submissions"]["rejected_rows"]
    assert rejected["count"] == len(many) == one(result)["submissions"]["invalid_count"]
    assert len(rejected["rows"]) == probe.MAX_REJECTED_ROWS
    assert rejected["rows"][-1]["value"] == f"xslF345X05/{probe.MAX_REJECTED_ROWS - 1}/f.xml"
    assert rejected["by_form"] == {"4": len(many)} and rejected["by_rule"] == {"primary_document": len(many)}


def test_rules_that_drift_from_the_collectors_are_said_and_never_read_as_access(monkeypatch):
    raw = rows_submissions([good_row(0), good_row(1, primaryDocument="xslF345X05/f.xml")])  # an 8-K: refused
    monkeypatch.setattr(probe, "row_problem", lambda columns, i, as_of: None)
    result, _ = run({issuer_evidence.MAPPING_URL: mapping(), SUBMISSIONS: raw})
    submissions = one(result)["submissions"]
    assert submissions["status"] == "classification_mismatch" and submissions["invalid_count"] == 1
    assert submissions["rejected_rows"]["count"] == 0
    assert result["answered"] is False
    assert result["sentence"] == "SEC answered, and the answer did not establish every issuer asked for (AAPL)."


def test_the_fixed_issuers_are_asked_after_one_mapping():
    two = mapping(rows=((CIK, "Apple Inc.", "AAPL", "Nasdaq"), (ZIM_CIK, "ZIM Integrated Shipping Services Ltd.", "ZIM", "NYSE")))
    zim = rows_submissions([good_row(0, accessionNumber="0001178913-26-004777", form="6-K", items="")],
                           cik=ZIM_CIK, tickers=("ZIM",))
    transport = Transport({issuer_evidence.MAPPING_URL: two, SUBMISSIONS: submissions(), ZIM_SUBMISSIONS: zim})
    result = probe.probe(transport=transport, clock=lambda: AT)
    assert probe.TICKERS == ("AAPL", "ZIM") and result["tickers"] == ["AAPL", "ZIM"]
    assert transport.calls == [issuer_evidence.MAPPING_URL, SUBMISSIONS, ZIM_SUBMISSIONS]
    assert result["request_count"] == 3 and result["answered"] is True
    assert [i["ticker"] for i in result["issuers"]] == ["AAPL", "ZIM"]
    assert [i["identity"]["cik"] for i in result["issuers"]] == [CIK, ZIM_CIK]
    assert result["sentence"] == "SEC answered all 3 requests from this runner."
    # An issuer the mapping does not name is asked nothing and names itself.
    other = Transport({issuer_evidence.MAPPING_URL: mapping(), SUBMISSIONS: submissions()})
    partial = probe.probe(transport=other, clock=lambda: AT)
    assert other.calls == [issuer_evidence.MAPPING_URL, SUBMISSIONS]
    assert partial["issuers"][1]["identity"]["status"] == "unverified" and partial["answered"] is False
    assert partial["sentence"] == "SEC answered, and the answer did not establish every issuer asked for (ZIM)."


def test_a_form_the_collector_never_stores_is_read_under_its_rendering_directory():
    # SEC's own shape for an XML filing; the collector reads it, so the probe names nothing.
    rows = [good_row(0), good_row(1, form="4", primaryDocument="xslF345X06/form4.xml", items=""),
            good_row(2, form="SCHEDULE 13D/A", primaryDocument="xslSCHEDULE_13D_X01/primary_doc.xml", items="")]
    result, _ = run({issuer_evidence.MAPPING_URL: mapping(), SUBMISSIONS: rows_submissions(rows)})
    submissions = one(result)["submissions"]
    assert submissions["invalid_count"] == 0 and submissions["filings_in_window"] == 3
    assert submissions["rejected_rows"] == {"count": 0, "by_rule": {}, "by_form": {}, "rows": []}


# One accession SEC lists twice, once without a usable document: the unnamed
# copy is refused as it was before such a row was counted, and the index is
# read; two copies that both name a usable document and differ still refuse it.
TWINS = [
    ("an unnamed copy after a named one", [("SC 13G/A", "marcus.corp.txt"), ("SC 13G/A", "marcus.corp..txt")], 1),
    ("an unnamed copy before a named one", [("SC 13G/A", ""), ("SC 13G/A", "marcus.corp.txt")], 1),
    ("two differing unnamed copies", [("SC 13G", ""), ("SC 13G", "qiagen.n.v..txt")], 2),
    ("two equal unnamed copies", [("SC 13G", ""), ("SC 13G", "")], 0),
]


def test_a_copy_the_row_rules_refuse_refuses_its_unnamed_twin_and_the_probe_names_both():
    rows = [good_row(0), good_row(1, form="SC 13G", primaryDocument="", items=""),
            good_row(1, form="SC 13G", primaryDocument="a/b.txt", items="")]
    raw = rows_submissions(rows)
    assert issuer_evidence.parse_submissions(raw, CIK, "AAPL", AT)["invalid_count"] == 2
    result, _ = run({issuer_evidence.MAPPING_URL: mapping(), SUBMISSIONS: raw})
    submissions = one(result)["submissions"]
    assert submissions["status"] == "parsed" and submissions["invalid_count"] == 2
    assert submissions["rejected_rows"]["by_rule"] == {"primary_document": 1, probe.TWIN_RULE: 1}


@pytest.mark.parametrize("name, copies, refused", TWINS, ids=[name for name, _, _ in TWINS])
def test_an_unnamed_copy_of_a_listed_accession_is_refused_by_the_collector_and_named_by_the_probe(name, copies, refused):
    rows = [good_row(0)] + [good_row(1, form=form, primaryDocument=document, items="") for form, document in copies]
    raw = rows_submissions(rows)
    parsed = issuer_evidence.parse_submissions(raw, CIK, "AAPL", AT)
    assert parsed["invalid_count"] == refused and len(parsed["filings"]) == len(copies) + 1 - refused - (refused == 0)
    result, _ = run({issuer_evidence.MAPPING_URL: mapping(), SUBMISSIONS: raw})
    submissions = one(result)["submissions"]
    assert submissions["status"] == "parsed" and submissions["invalid_count"] == refused
    rejected = submissions["rejected_rows"]
    assert rejected["by_rule"] == ({probe.TWIN_RULE: refused} if refused else {})
    # Each refused copy is printed with its own document and filing date.
    unnamed = [(d, rows[n + 1]["filingDate"]) for n, (_, d) in enumerate(copies) if not issuer_evidence._basename(d)]
    assert [(r["value"], r["filing_date"]) for r in rejected["rows"]] == (unnamed if refused else [])


def test_two_differing_copies_that_both_name_a_document_still_refuse_the_index():
    rows = [good_row(0), good_row(1, form="SC 13G", primaryDocument="a.txt"), good_row(1, form="SC 13G", primaryDocument="b.txt")]
    with pytest.raises(issuer_evidence.SourceError):
        issuer_evidence.parse_submissions(rows_submissions(rows), CIK, "AAPL", AT)


def test_a_form_the_collector_never_stores_is_counted_without_a_usable_document():
    # The shapes the probe named for MCS and QGEN on 31 October 2026 (run 41149821846).
    shapes = [("SC 13G/A", "marcus.corp..txt"), ("SC 13G/A", "qiagen.n.v..txt"), ("SC 13G/A", "qiagen.nv.reg.shs..txt"),
              ("SC 13G", "qiagen.nv.reg.shs..txt"), ("SC 13G/A", ""), ("SC 13G", "")]
    rows = [good_row(0)] + [good_row(n, form=form, primaryDocument=document, items="")
                            for n, (form, document) in enumerate(shapes, start=1)]
    result, _ = run({issuer_evidence.MAPPING_URL: mapping(), SUBMISSIONS: rows_submissions(rows)})
    submissions = one(result)["submissions"]
    assert submissions["status"] == "parsed"
    assert submissions["invalid_count"] == 0 and submissions["filings_in_window"] == len(rows)
    assert submissions["rejected_rows"] == {"count": 0, "by_rule": {}, "by_form": {}, "rows": []}


@pytest.mark.parametrize("text,expected", [
    ("", probe.TICKERS), ("  ", probe.TICKERS), ("MCS QGEN", ("MCS", "QGEN")), ("MCS,QGEN", ("MCS", "QGEN")),
    ("BRK-B", ("BRK-B",)), ("BF-B ZIM", ("BF-B", "ZIM")), ("GOOGL", ("GOOGL",)), ("ABCDE-FG", ("ABCDE-FG",)),
    ("MCS QGEN BF-B ZIM", ("MCS", "QGEN", "BF-B", "ZIM"))])
def test_a_dispatch_may_name_the_issuers_to_ask_for(text, expected):
    assert probe.tickers_from(text) == expected


@pytest.mark.parametrize("text", ["mcs", "A B C D E", "MCS MCS", "TOOLONG", "A;rm", "$(x)", "A/B", "AAPL\nZIM..",
                                  "BRK.B", "ABCDEF", "BRK-ABC", "A1", "-B", "BRK-"])
def test_anything_but_up_to_four_distinct_exchange_tickers_is_refused(text):
    with pytest.raises(ValueError):
        probe.tickers_from(text)


def test_main_asks_for_the_named_issuers_and_refuses_malformed_ones_before_any_request(tmp_path, monkeypatch, capsys):
    asked = []
    monkeypatch.setattr(probe, "probe", lambda tickers=probe.TICKERS: asked.append(tickers) or {"tickers": list(tickers)})
    monkeypatch.setattr(probe, "write_probe", lambda output, result: json.dumps(result) + "\n")
    assert probe.main(["--output", str(tmp_path / "a.json"), "--tickers", "MCS QGEN"]) == 0
    assert asked == [("MCS", "QGEN")]
    assert probe.main(["--output", str(tmp_path / "b.json")]) == 0
    assert asked[-1] == probe.TICKERS
    capsys.readouterr()
    assert probe.main(["--output", str(tmp_path / "c.json"), "--tickers", "MCS; rm -rf /"]) == 2
    assert asked == [("MCS", "QGEN"), probe.TICKERS] and not (tmp_path / "c.json").exists()
    assert capsys.readouterr().out.startswith("SEC access diagnostic refused: tickers must be")
