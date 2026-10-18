"""The SEC access diagnostic: two fixed requests through the collector's transport, no address."""
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


def run(answers):
    transport = Transport(answers)
    return probe.probe(transport=transport, clock=lambda: AT), transport


def test_both_answers_name_the_issuer_and_carry_no_body_or_address():
    result, transport = run({issuer_evidence.MAPPING_URL: mapping(), SUBMISSIONS: submissions()})
    assert transport.calls == [issuer_evidence.MAPPING_URL, SUBMISSIONS]
    assert result["answered"] is True and result["refused_statuses"] == []
    assert result["request_count"] == 2
    assert [r["phase"] for r in result["requests"]] == ["mapping", "submissions"]
    assert [r["outcome"] for r in result["requests"]] == ["ok", "ok"]
    assert result["requests"][1]["sha256"] == issuer_evidence._sha(submissions())
    assert result["requests"][1]["bytes"] == len(submissions())
    assert result["identity"] == {"status": "verified", "cik": CIK, "name": "Apple Inc.", "reason": None}
    assert result["submissions"] == {"status": "parsed", "filings_in_window": 3, "history_files_advertised": 0}
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
    assert result["identity"]["status"] == result["submissions"]["status"] == "not_reached"
    assert result["sentence"] == "SEC did not answer the mapping request from this runner: HTTP 403."


def test_a_refused_submissions_request_is_named_after_a_verified_identity():
    result, transport = run({issuer_evidence.MAPPING_URL: mapping(),
                             SUBMISSIONS: issuer_evidence.SourceError("rate_limit", http_status=429)})
    assert transport.calls == [issuer_evidence.MAPPING_URL, SUBMISSIONS]
    assert result["identity"]["status"] == "verified" and result["submissions"]["status"] == "unavailable"
    assert result["answered"] is False and result["refused_statuses"] == [429]
    assert result["sentence"] == "SEC did not answer the submissions request from this runner: HTTP 429."


def test_a_network_failure_has_no_status_and_says_so():
    result, _ = run({issuer_evidence.MAPPING_URL: issuer_evidence.SourceError("network_error")})
    assert result["requests"][0]["http_status"] is None and result["refused_statuses"] == []
    assert result["sentence"] == "SEC did not answer the mapping request from this runner: network_error."


def test_an_answer_that_does_not_establish_the_issuer_is_not_access():
    result, transport = run({issuer_evidence.MAPPING_URL: mapping(rows=((789019, "MICROSOFT CORP", "MSFT", "Nasdaq"),))})
    assert transport.calls == [issuer_evidence.MAPPING_URL]
    assert result["identity"] == {"status": "unverified", "cik": None, "name": None, "reason": "identity_unverified"}
    assert result["answered"] is False
    assert result["sentence"] == "SEC answered, and the answer did not establish the fixed issuer."
    other, _ = run({issuer_evidence.MAPPING_URL: mapping(), SUBMISSIONS: submissions(tickers=("MSFT",))})
    assert other["submissions"]["status"] == "invalid" and other["answered"] is False
    assert other["sentence"] == "SEC answered, and the answer did not establish the fixed issuer."
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
    monkeypatch.setattr(probe, "probe", lambda: result)
    assert probe.main(["--output", str(tmp_path / "out.json")]) == 0
    printed = capsys.readouterr().out
    assert json.loads(printed) == result == json.loads((tmp_path / "out.json").read_text())

    def broken():
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
