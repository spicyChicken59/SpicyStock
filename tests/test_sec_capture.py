"""The SEC document capture: one filing document's identity for a registry review, and nothing else."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from src import issuer_evidence
from tools import capture_sec_document as capture

ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.sec.gov/Archives/edgar/data/900075/000119312526423478/d129535dex991.htm"
AT = datetime(2026, 11, 25, 15, 0, tzinfo=timezone.utc)
BODY = (b"<html><head><title>EX-99.1</title><style>p {color: red}</style></head><body>"
        b"<p>Company A today announced that it has <b>completed</b> its acquisition of Company B.</p>"
        b"<p>As a result, shares of Company B   ceased trading.</p>"
        b"<p>The transaction was Completed on the date above.</p>"
        b"<script>var completed = 1;</script></body></html>")


class Transport:
    """The real transport's contract: begin a request on the budget, then answer or raise."""

    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def fetch(self, url, budget):
        budget.begin_request()
        self.calls.append(url)
        if isinstance(self.answer, Exception):
            raise self.answer
        return {"body": self.answer, "observed_at": AT}


def run(answer=BODY, phrases=("completed", "ceased trading"), url=URL, clock=None):
    transport = Transport(answer)
    result, body = capture.capture(url, phrases, transport=transport, clock=clock or (lambda: AT))
    return result, body, transport


def test_one_request_gives_the_documents_identity_and_its_own_words():
    result, body, transport = run()
    assert transport.calls == [URL] and result["request_count"] == 1
    assert body == BODY
    assert result["request"] == {"url": URL, "outcome": "ok", "http_status": None, "bytes": len(BODY),
                                 "sha256": issuer_evidence._sha(BODY), "checked_at": issuer_evidence._iso(AT)}
    assert result["schema"] == "spicystock-sec-capture-v1" and result["purpose"] == "registry_review_source_capture"
    document = result["document"]
    text = issuer_evidence.parse_primary(BODY, URL)["text"]
    assert (document["status"], document["normalized_characters"]) == ("read", len(text))
    first, second = document["finds"]
    # counted case-folded over the text the collector reads: the script and the style are not text
    assert (first["phrase"], first["count"]) == ("completed", 2)
    assert (second["phrase"], second["count"]) == ("ceased trading", 1)
    assert all(e in text for f in document["finds"] for e in f["excerpts"])
    assert "has completed its acquisition of Company B" in first["excerpts"][0]
    assert "shares of Company B ceased trading" in second["excerpts"][0]          # whitespace collapsed
    assert result["sentence"] == (f"SEC answered: {len(BODY)} bytes, SHA-256 {issuer_evidence._sha(BODY)}; "
                                  "2 of 2 phrases asked for are in its text.")
    assert result["limits"] == list(capture.LIMITS) and "resolves_no_registry_entry" in result["limits"]


def test_a_phrase_the_document_does_not_carry_is_counted_as_absent():
    result, _, _ = run(phrases=("terminated", "completed"))
    assert [(f["phrase"], f["count"], len(f["excerpts"])) for f in result["document"]["finds"]] == [
        ("terminated", 0, 0), ("completed", 2, 2)]
    assert "1 of 2 phrases asked for are in its text" in result["sentence"]
    assert run(phrases=())[0]["document"]["finds"] == []


def test_excerpts_are_bounded_in_count_and_width_and_every_occurrence_is_counted():
    body = ("<html><body>" + " ".join(f"filler{i} " * 40 + "the merger was completed" for i in range(7))
            + "</body></html>").encode()
    result, _, _ = run(answer=body, phrases=("completed",))
    (found,) = result["document"]["finds"]
    assert found["count"] == 7 and len(found["excerpts"]) == capture.MAX_EXCERPTS == 3
    assert all(len(e) <= 2 * capture.EXCERPT_SIDE_CHARS + len("completed") for e in found["excerpts"])
    assert all("completed" in e for e in found["excerpts"])
    # the first excerpt begins at the text's start when the occurrence is nearer than a side's width
    near, _, _ = run(answer=b"<html><body>completed at once</body></html>", phrases=("completed",))
    assert near["document"]["finds"][0]["excerpts"] == ["completed at once"]


@pytest.mark.parametrize("error, outcome, status", [
    (issuer_evidence.SourceError("http_error", http_status=403), "http_error", 403),
    (issuer_evidence.SourceError("http_error", http_status=404), "http_error", 404),
    (issuer_evidence.SourceError("network_error"), "network_error", None),
    (KeyError("body"), "invalid_response", None),
])
def test_a_refusal_is_a_result_with_no_bytes_no_digest_and_no_excerpt(error, outcome, status):
    result, body, _ = run(answer=error)
    assert body is None
    assert (result["request"]["outcome"], result["request"]["http_status"]) == (outcome, status)
    assert result["request"]["bytes"] is None and result["request"]["sha256"] is None
    assert result["document"] == {"status": "not_read", "normalized_characters": None, "finds": []}
    said = f"HTTP {status}" if status is not None else outcome
    assert result["sentence"] == f"SEC did not give this document to this runner: {said}."


def test_an_empty_answer_is_not_a_document():
    result, body, _ = run(answer=b"")
    assert body is None and result["request"]["outcome"] == "invalid_response"


def test_bytes_whose_text_cannot_be_read_keep_their_identity_and_claim_no_words():
    raw = b"<html><head><meta charset=\"klingon\"></head><body>completed</body></html>"
    result, body, _ = run(answer=raw, phrases=("completed",))
    assert body == raw and result["request"]["sha256"] == issuer_evidence._sha(raw)
    assert result["document"] == {"status": "text_unreadable", "normalized_characters": None, "finds": []}
    assert "its text could not be read as the collector reads a filing" in result["sentence"]


@pytest.mark.parametrize("url", [
    "https://www.sec.gov/Archives/edgar/data/0000900075/000119312526423478/d129535dex991.htm",   # leading zeros
    "http://www.sec.gov/Archives/edgar/data/900075/000119312526423478/d129535dex991.htm",
    "https://www.sec.gov/Archives/edgar/data/900075/000119312526423478/d129535dex991.htm?x=1",
    "https://www.sec.gov/Archives/edgar/data/900075/000119312526423478/../d129535dex991.htm",
    "https://example.com/Archives/edgar/data/900075/000119312526423478/d129535dex991.htm",
    "https://www.sec.gov/cgi-bin/browse-edgar",
    issuer_evidence.MAPPING_URL,                                       # the probe's, not a filing document
    "https://data.sec.gov/submissions/CIK0000900075.json",
    "", None, 5,
])
def test_a_url_that_is_not_a_filing_document_is_refused_before_any_request(url):
    transport = Transport(BODY)
    with pytest.raises(ValueError, match="URL"):
        capture.capture(url, (), transport=transport, clock=lambda: AT)
    assert transport.calls == []


@pytest.mark.parametrize("text, phrases", [
    ("", ()), ("  ", ()), ("completed", ("completed",)),
    ("completed | ceased trading|$10.50 per share", ("completed", "ceased trading", "$10.50 per share")),
])
def test_phrases_are_split_on_the_bar_and_trimmed(text, phrases):
    assert capture.phrases_from(text) == phrases


@pytest.mark.parametrize("text", [
    "ab", "x" * 81, "completed|Completed", "a|b|c|d|e|f|g".replace("a", "aaa").replace("b", "bbb"),
    "<script>", "completed; rm -rf", "one\ntwo", "quote\"d", "back\\slash",
    "|".join(f"phrase {i}" for i in range(7)),
])
def test_malformed_phrases_refuse_the_whole_dispatch(text):
    with pytest.raises(ValueError, match="phrases"):
        capture.phrases_from(text)


def test_the_result_and_the_bytes_are_written_once_outside_docs_and_never_carry_the_address(tmp_path):
    result, body, _ = run()
    out, raw = tmp_path / "capture.json", tmp_path / "document.bin"
    payload = capture.write_capture(out, result, body=body, save_bytes=raw)
    assert out.read_text() == payload and json.loads(payload) == result and raw.read_bytes() == BODY
    assert issuer_evidence.USER_AGENT not in payload and "@" not in payload
    with pytest.raises(FileExistsError):
        capture.write_capture(out, result)                              # never replaces a file
    with pytest.raises(FileExistsError):
        capture.write_capture(tmp_path / "other.json", result, body=body, save_bytes=raw)
    for inside in (capture.PUBLIC_ROOT / "capture.json", capture.PUBLIC_ROOT / "evidence" / "x.json"):
        with pytest.raises(ValueError, match="public docs"):
            capture.write_capture(inside, result)
        with pytest.raises(ValueError, match="public docs"):
            capture.write_capture(tmp_path / "ok.json", result, body=body, save_bytes=inside)
    assert not (tmp_path / "ok.json").exists()
    # a refusal writes its result and no bytes file
    refused, none, _ = run(answer=issuer_evidence.SourceError("http_error", http_status=403))
    capture.write_capture(tmp_path / "refused.json", refused, body=none, save_bytes=tmp_path / "refused.bin")
    assert not (tmp_path / "refused.bin").exists()


def test_a_result_that_would_carry_the_contact_address_is_refused(tmp_path):
    address = capture.ADDRESS.search(issuer_evidence.USER_AGENT).group(0)
    body = f"<html><body>completed, write to {address} for details</body></html>".encode()
    result, _, _ = run(answer=body, phrases=("completed",))
    with pytest.raises(ValueError, match="contact address"):
        capture.write_capture(tmp_path / "capture.json", result)
    assert not (tmp_path / "capture.json").exists()


def test_a_clock_that_moves_backwards_is_refused():
    ticks = iter([AT, AT - timedelta(seconds=1)])
    with pytest.raises(ValueError, match="clock"):
        run(clock=lambda: next(ticks))


def test_the_command_refuses_before_asking_and_never_prints_a_raw_error(tmp_path, monkeypatch, capsys):
    asked = []
    monkeypatch.setattr(capture, "capture", lambda *a, **k: asked.append(a) or (_ for _ in ()).throw(
        RuntimeError("secret detail")))
    assert capture.main(["--url", "https://example.com/x", "--output", str(tmp_path / "a.json")]) == 2
    assert capture.main(["--url", URL, "--find", "ab", "--output", str(tmp_path / "a.json")]) == 2
    assert asked == [] and "refused" in capsys.readouterr().out
    assert capture.main(["--url", URL, "--output", str(tmp_path / "a.json")]) == 1
    out = capsys.readouterr().out
    assert out == "SEC document capture failed; no raw error was logged.\n" and "secret detail" not in out
    assert not (tmp_path / "a.json").exists()


def test_the_command_prints_what_it_wrote_and_exits_by_the_outcome(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(issuer_evidence, "_Transport", lambda cache_dir=None: Transport(BODY))
    out = tmp_path / "sec-capture" / "capture.json"
    out.parent.mkdir()
    assert capture.main(["--url", f"  {URL} ", "--find", "completed|ceased trading", "--output", str(out),
                         "--save-bytes", str(out.parent / "document.bin")]) == 0
    assert capsys.readouterr().out == out.read_text()
    assert (out.parent / "document.bin").read_bytes() == BODY
    monkeypatch.setattr(issuer_evidence, "_Transport", lambda cache_dir=None: Transport(
        issuer_evidence.SourceError("http_error", http_status=403)))
    assert capture.main(["--url", URL, "--output", str(tmp_path / "refused.json")]) == 1
    assert json.loads((tmp_path / "refused.json").read_text())["request"]["http_status"] == 403


def test_the_capture_asks_through_the_collectors_transport_with_no_cache(monkeypatch):
    made = []

    def transport(cache_dir="unset"):
        made.append(cache_dir)
        return Transport(BODY)

    monkeypatch.setattr(issuer_evidence, "_Transport", transport)
    capture.capture(URL, ())
    assert made == [None]


def test_the_readme_states_the_bounds_the_tool_holds():
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert (f"up to {capture.MAX_PHRASES} phrases in **capture_find** (separated by `|`)" in readme
            and f"at most {capture.MAX_EXCERPTS} excerpts of {capture.EXCERPT_SIDE_CHARS} characters either side"
            in readme)
    assert "(`tools/capture_sec_document.py`)" in readme and "resolves nothing" in readme
