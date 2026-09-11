"""The Anthropic boundary of src.grader: the request, the parser, the fallback
and the call budget.

The rubric lives in the system prompt and is the model's business, so nothing
here asserts what a score SHOULD be. What is asserted is everything around
it: that the request is the one decided on, that it is identical for
identical input, that the replies a model really produces are parsed rather
than discarded, that the grade is the score's band, and that every row says
who produced it.

The double is scripted here rather than in tests/fakes.py because these tests
script a SEQUENCE of replies and set `stop_reason`; it bills a cached prefix
by the same `billed_usage` rule the shared double does, which is what makes
the caching test load-bearing. Nothing here opens a socket.
"""

from __future__ import annotations

import inspect
import json
import logging
from pathlib import Path

import pytest

from src.charts import render_chart
from src.grader import (
    ATTEMPTS,
    GRADE_BANDS,
    GRADES,
    MAX_TOKENS,
    NOT_GRADED_REASON,
    RETRY_CORRECTION,
    SAMPLING_MODELS,
    SCORE_SCHEMA,
    SKIP,
    SOURCE_CLAUDE,
    SOURCE_FALLBACK,
    SOURCE_NOT_GRADED,
    STRUCTURED_OUTPUT_MODELS,
    UNGRADED,
    _error_text,
    _fallback_score,
    cache_usage,
    grade_all,
    grade_candidate,
    grade_for,
    is_fatal_auth_failure,
    request_kwargs,
    user_text,
)
from tests.fakes import FakeTextBlock, billed_usage

#: A rulebook long enough to be a cacheable prefix; the words do not matter.
SYSTEM = "Grade momentum bursts by the rules of this document. " * 120

REPLY = {"score": 7.5, "grade": "B", "reason": "synthetic", "key_risk": "synthetic",
         "entry_note": "synthetic"}


# ------------------------------------------------------- the scripted double --


class _Reply:
    """One `messages.create` return value, with the stop_reason a real one has."""

    def __init__(self, text: str, stop_reason: str = "end_turn") -> None:
        self.content = [FakeTextBlock(text=text)]
        self.stop_reason = stop_reason
        self.usage = None


class _ScriptedAnthropic:
    """Replies from a script; the last entry repeats for every later call."""

    script: list = []
    calls: list = []

    def __init__(self, *args, **kwargs) -> None:
        self.messages = _ScriptedMessages(type(self))


class _ScriptedMessages:
    def __init__(self, owner) -> None:
        self._owner = owner

    def create(self, **kwargs):
        self._owner.calls.append(kwargs)
        script = self._owner.script
        assert script, "the test scripted no reply"
        step = script[min(len(self._owner.calls) - 1, len(script) - 1)]
        if isinstance(step, BaseException):
            raise step
        step.usage = billed_usage(kwargs, self._owner.calls)
        return step


class _Claude:
    """Handle on the double: script the replies, read the requests."""

    def __init__(self, cls) -> None:
        self._cls = cls

    @property
    def calls(self) -> list[dict]:
        return self._cls.calls

    def replies(self, *steps) -> None:
        """Each step is reply text, a `_Reply`, or an exception to raise."""
        self._cls.script = [
            s if isinstance(s, (_Reply, BaseException)) else _Reply(s) for s in steps
        ]

    def payload(self, **fields) -> None:
        self.replies(json.dumps({**REPLY, **fields}))


@pytest.fixture
def claude(monkeypatch) -> _Claude:
    """Replace anthropic.Anthropic with the scripted double, a fresh subclass
    per test so a recorded call never leaks. Defaults to one well-formed reply."""
    import anthropic

    cls = type("ScriptedAnthropicForTest", (_ScriptedAnthropic,), {"script": [], "calls": []})
    monkeypatch.setattr(anthropic, "Anthropic", cls)
    control = _Claude(cls)
    control.payload()
    return control


def metrics(passes: int = 7, of: int = 9, **extra) -> dict:
    """A metrics block of a given checklist strength, built by hand: this
    file must keep working whatever the quality layer measures."""
    return {"ticker": "AAA", "date": "2026-09-10", "close": 44.8, "gain_pct": 12.0,
            "volume_ratio": 8.0, "passes": passes, "of": of,
            "checks": [f"PASS  check_{i}" for i in range(passes)], **extra}


def candidates(*passes: int) -> list[dict]:
    return [{"ticker": f"T{i}", "metrics": metrics(p, ticker=f"T{i}"), "chart": None}
            for i, p in enumerate(passes)]


def _text_of(call: dict) -> str:
    blocks = call["messages"][0]["content"]
    return "".join(b["text"] for b in blocks if b["type"] == "text")


def _metrics_of(call: dict) -> dict:
    return json.loads(_text_of(call).split("METRICS:\n", 1)[1].split("\n\nRespond", 1)[0])


# ----------------------------------------------------------- the request ----


def test_the_default_model_gets_temperature_and_no_output_config():
    """claude-sonnet-4-6 accepts sampling parameters and does NOT support
    structured outputs: output_config to it is a 400, and no temperature is
    the unpinned sort key."""
    kwargs = request_kwargs("sys", [{"type": "text", "text": "t"}], model="claude-sonnet-4-6")
    assert kwargs["extra_body"] == {"temperature": 0}
    assert "output_config" not in kwargs
    assert kwargs["max_tokens"] == MAX_TOKENS


def test_a_structured_output_model_gets_the_schema_and_no_temperature():
    """The gating runs the other way on a current model: output_config is
    supported and `temperature` is rejected with a 400."""
    kwargs = request_kwargs("sys", [{"type": "text", "text": "t"}], model="claude-opus-5")
    fmt = kwargs["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["schema"]["required"] == ["score", "grade", "reason", "key_risk", "entry_note"]
    assert fmt["schema"]["properties"]["grade"]["enum"] == list(GRADES)
    assert fmt["schema"]["additionalProperties"] is False
    assert "extra_body" not in kwargs


def test_an_unrecognised_model_is_sent_neither_gated_parameter():
    """A model newer than this file must not be guessed at: an unsupported
    parameter is a 400 on every call of the run."""
    kwargs = request_kwargs("sys", [{"type": "text", "text": "t"}],
                            model="claude-not-released-yet-9")
    assert "extra_body" not in kwargs and "output_config" not in kwargs


def test_the_two_capability_lists_do_not_overlap_by_accident():
    """An id in both lists would be sent a schema it may not support and a
    sampling parameter it may reject."""
    overlap = STRUCTURED_OUTPUT_MODELS & SAMPLING_MODELS
    assert overlap <= {"claude-haiku-4-5", "claude-opus-4-5"}, overlap


@pytest.mark.parametrize("model", ["claude-sonnet-4-6", "claude-opus-5", "claude-unknown-9"])
def test_the_request_binds_to_the_real_sdk_signature(model):
    """anthropic 1.x removed `temperature` from Messages.create(); a named
    argument is a TypeError before any request, which the grader's own
    except-clause would turn into a fallback for every candidate."""
    import anthropic

    real = anthropic.Anthropic(api_key="unused-by-a-signature-check")
    kwargs = request_kwargs("sys", [{"type": "text", "text": "t"}], model=model)
    inspect.signature(real.messages.create).bind(**kwargs)


def test_the_rulebook_is_sent_as_a_cacheable_block(claude):
    """The system prompt is byte-identical on every call of a run and most of
    each request. Asserted on the block, because the saving is invisible from
    inside the run."""
    grade_candidate("AAA", metrics(), None, SYSTEM)

    system = claude.calls[0]["system"]
    assert system[0]["cache_control"] == {"type": "ephemeral"}, system[0]
    assert "ttl" not in system[0]["cache_control"], "five minutes is the cheap write"
    assert len(system) == 1, "two blocks would split the prefix"
    assert system[0]["text"] == SYSTEM


def test_the_cacheable_block_is_a_shape_the_installed_sdk_accepts():
    """The SDK's own TextBlockParam says the block is well formed, offline."""
    from anthropic.types import TextBlockParam

    block = request_kwargs("the rulebook", [{"type": "text", "text": "t"}])["system"][0]
    assert set(block) <= set(TextBlockParam.__annotations__), (
        f"the SDK does not know these keys: {set(block) - set(TextBlockParam.__annotations__)}")
    assert "cache_control" in TextBlockParam.__annotations__


def test_the_request_asks_for_every_field_the_schema_requires():
    """The shape line is spelled from SCORE_SCHEMA, so the model asked in
    prose and the model held to a schema are asked for one object."""
    text = user_text(metrics())
    shape = text.rsplit("\n", 1)[1]
    for field in SCORE_SCHEMA["required"]:
        assert f'"{field}":' in shape, field
    assert "|".join(GRADES) in shape
    assert "tomorrow's open" in shape
    assert "three sentences" in shape and "decisive factor" in shape


def test_the_request_carries_the_metrics(claude):
    block = metrics(gap_pct=1.2)
    grade_candidate("AAA", block, None, SYSTEM)
    call = claude.calls[0]
    assert call["model"]
    assert _metrics_of(call) == block
    assert "AAA" in _text_of(call)


def test_the_same_metrics_produce_the_same_request_twice(claude):
    """The score is a sort key and an archived number: nothing on our side of
    the request may differ between two runs over one candidate, and a key
    order that changed would be a cache miss on every call."""
    block = metrics(gap_pct=1.2, extension_pct=4.4)
    first = grade_candidate("AAA", block, None, SYSTEM)
    second = grade_candidate("AAA", dict(reversed(list(block.items()))), None, SYSTEM)
    assert claude.calls[0] == claude.calls[1]
    assert first == second


# ------------------------------------------------------------- the cache ----


def test_cache_usage_reads_what_the_reply_reports_and_survives_one_that_does_not():
    class Usage:
        cache_creation_input_tokens = 1590
        cache_read_input_tokens = 0
        input_tokens = 1109

    class Reply:
        usage = Usage()

    assert cache_usage(Reply()) == {"cache_write": 1590, "cache_read": 0, "uncached": 1109}

    class Hit(Reply):
        usage = type("U", (), {"cache_creation_input_tokens": 0,
                               "cache_read_input_tokens": 1590, "input_tokens": 1109})()

    assert cache_usage(Hit())["cache_read"] == 1590

    for reply in (object(),
                  type("R", (), {"usage": None})(),
                  type("R", (), {"usage": type("U", (), {})()})(),
                  type("R", (), {"usage": type("U", (), {
                      "cache_read_input_tokens": "1590",
                      "cache_creation_input_tokens": True,
                      "input_tokens": None})()})()):
        assert cache_usage(reply) == {"cache_write": 0, "cache_read": 0, "uncached": 0}, reply


def test_a_run_totals_the_cache_across_every_call(claude):
    """One write and N-1 reads is the whole shape of the saving. The double
    bills the way the API does, so a flat per-call number cannot pass."""
    usage: dict = {}
    n = 3

    grade_all(candidates(7, 7, 7), SYSTEM, max_calls=n, usage=usage)

    prefix = len(SYSTEM) // 4
    assert usage == {
        "cache_write": prefix,            # once, on the first call
        "cache_read": prefix * (n - 1),   # every call after
        "uncached": 1109 * n,             # metrics and chart, per candidate
    }, usage


def test_a_request_that_stops_asking_for_caching_reports_none(claude, monkeypatch):
    """The inverse, and what makes the test above load-bearing: the double
    reports a cached prefix only for a block that CARRIES cache_control."""
    import src.grader as grader_mod

    real = grader_mod.request_kwargs

    def uncached(system, content, model=None):
        kwargs = real(system, content, model)
        kwargs["system"] = system  # a bare string, the old shape
        return kwargs

    monkeypatch.setattr(grader_mod, "request_kwargs", uncached)
    usage: dict = {}

    grade_all(candidates(7, 7, 7), SYSTEM, max_calls=3, usage=usage)

    assert usage["cache_read"] == 0 and usage["cache_write"] == 0


def test_grade_all_logs_one_cache_line_per_run(claude, caplog):
    with caplog.at_level(logging.INFO, logger="src.grader"):
        grade_all(candidates(7, 7), SYSTEM, max_calls=2)
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Prompt cache")]
    assert len(lines) == 1, lines
    assert "read from cache" in lines[0]


# -------------------------------------------------------------- the retry ----


def test_an_unparseable_reply_is_asked_again_differently_not_resent(claude, ohlcv, tmp_path):
    """A prose reply used to produce two IDENTICAL requests at temperature 0,
    both unparseable, and a fallback paid for twice."""
    prose = "I'd rate this setup around 7 out of 10 -- the base is tight."
    claude.replies(prose, json.dumps(REPLY))
    # A real chart, so the check that the image survives the retry is about
    # an image that is there.
    chart = render_chart("AAA", ohlcv("burst"), str(tmp_path))

    out = grade_candidate("AAA", metrics(), chart, SYSTEM)

    first, second = claude.calls
    assert first != second, "the retry resent the same request"
    assert RETRY_CORRECTION not in _text_of(first)
    assert RETRY_CORRECTION in _text_of(second)
    # ADDED to the request, not substituted for it: a retry carrying the
    # correction alone asks the model to grade a candidate it can no longer
    # see, and the reply would parse.
    assert "AAA" in _text_of(second)
    sent = second["messages"][0]["content"]
    assert first["messages"][0]["content"] == sent[:-1]
    assert sent[0]["type"] == "image", "the retry dropped the chart image"
    assert sent[-1] == {"type": "text", "text": RETRY_CORRECTION}
    # The system prompt is untouched, so the cached prefix still hits.
    assert first["system"] == second["system"]
    assert out["provenance"]["source"] == SOURCE_CLAUDE, "and the second ask landed"


def test_a_transport_failure_retries_the_request_it_already_had(claude):
    """An API error says nothing about the request's shape; correcting a
    request that was fine tells the model its output was wrong when it never
    produced any."""
    claude.replies(RuntimeError("overloaded_error: server is busy"), json.dumps(REPLY))

    out = grade_candidate("AAA", metrics(), None, SYSTEM)

    first, second = claude.calls
    assert first == second
    assert RETRY_CORRECTION not in _text_of(second)
    assert out["provenance"]["source"] == SOURCE_CLAUDE


def test_one_bad_reply_is_retried_before_anything_falls_back(claude):
    claude.replies("sorry, I cannot produce JSON here", json.dumps({**REPLY, "score": 7.7}))
    result = grade_candidate("AAA", metrics(), None, SYSTEM)
    assert len(claude.calls) == 2
    assert result["score"] == 7.7
    assert result["provenance"]["source"] == SOURCE_CLAUDE


def test_a_transient_failure_is_still_retried_then_falls_back(claude):
    claude.replies(RuntimeError("Error code: 503 - overloaded"))
    result = grade_candidate("AAA", metrics(), None, SYSTEM)
    assert len(claude.calls) == ATTEMPTS == 2, "one retry before giving up"
    assert result["provenance"]["source"] == SOURCE_FALLBACK


# ------------------------------------------------------- a refused key ----


@pytest.mark.parametrize("text", [
    "anthropic.AuthenticationError: Error code: 401 - invalid x-api-key",
    "anthropic.PermissionDeniedError: Error code: 403 - forbidden",
    "RuntimeError: Could not resolve authentication method",
])
def test_a_refused_credential_is_recognised(text):
    assert is_fatal_auth_failure(text)


@pytest.mark.parametrize("text", [
    "anthropic.APIStatusError: Error code: 503 - overloaded",
    "anthropic.APIConnectionError: connection reset by peer",
    "src.grader.ScoreFormatError: no scoreable JSON object in 812 characters of reply",
    "",
])
def test_a_transient_failure_is_not_mistaken_for_a_refused_credential(text):
    assert not is_fatal_auth_failure(text)


def test_a_refused_credential_is_not_retried(claude):
    """Same code path, same fallback, one call instead of two."""
    claude.replies(RuntimeError("Error code: 401 - invalid x-api-key"))
    result = grade_candidate("AAA", metrics(), None, SYSTEM)
    assert len(claude.calls) == 1, "a rejected key is not transient; do not retry it"
    assert result["provenance"]["source"] == SOURCE_FALLBACK


def test_a_refused_credential_is_not_bought_again_for_every_candidate(claude):
    """Three candidates, one refusal: one call, three honest fallback rows."""
    claude.replies(RuntimeError("Error code: 401 - invalid x-api-key"))

    rows = grade_all(candidates(9, 7, 5), SYSTEM, max_calls=3)

    assert len(claude.calls) == 1, "the first refusal settles it for the run"
    assert [r["provenance"]["source"] for r in rows] == [SOURCE_FALLBACK] * 3
    assert all("401" in r["provenance"]["error"] for r in rows), (
        "every row must carry the reason, including the ones never sent")


def test_a_transient_failure_does_not_stop_the_remaining_candidates(claude):
    claude.replies(RuntimeError("503"), RuntimeError("503"), json.dumps(REPLY))

    rows = grade_all(candidates(9, 9, 9), SYSTEM, max_calls=3)

    assert len(claude.calls) == 4, "two attempts for T0, then one each for T1 and T2"
    assert [r["provenance"]["source"] for r in rows] == [SOURCE_FALLBACK, SOURCE_CLAUDE,
                                                         SOURCE_CLAUDE]


# ------------------------------------------------------------- the parser ----


def test_grade_candidate_parses_the_model_reply(claude):
    claude.payload(score=8.4, grade="A", reason="tight base", key_risk="breadth",
                   entry_note="a gap above 46 at the open")
    result = grade_candidate("AAA", metrics(), None, SYSTEM)
    assert result["score"] == 8.4
    assert result["grade"] == "A"
    assert result["reason"] == "tight base"
    assert result["key_risk"] == "breadth"
    assert result["entry_note"] == "a gap above 46 at the open"
    assert len(claude.calls) == 1


def test_grade_candidate_parses_a_fenced_reply(claude):
    claude.replies('Here you go:\n```json\n' + json.dumps({**REPLY, "score": 6}) + '\n```')
    result = grade_candidate("AAA", metrics(), None, SYSTEM)
    assert result["score"] == 6.0 and isinstance(result["score"], float)


def test_a_reply_with_trailing_prose_containing_a_brace_is_parsed(claude):
    claude.replies(json.dumps({**REPLY, "score": 7.1}) + "\nNote: the {R} check fails here.")
    result = grade_candidate("AAA", metrics(), None, SYSTEM)
    assert result["score"] == 7.1
    assert result["provenance"]["source"] == SOURCE_CLAUDE


def test_a_reply_with_leading_prose_containing_a_brace_is_parsed(claude):
    claude.replies("Reading the {checklist} first.\n" + json.dumps({**REPLY, "score": 4.5}))
    assert grade_candidate("AAA", metrics(), None, SYSTEM)["score"] == 4.5


def test_a_raw_newline_inside_the_reason_is_parsed(claude):
    claude.replies('{"score": 6.5, "reason": "tight base,\nvolume expanding", '
                   '"grade": "B", "key_risk": "gap", "entry_note": "n"}')
    result = grade_candidate("AAA", metrics(), None, SYSTEM)
    assert result["score"] == 6.5
    assert "volume expanding" in result["reason"]


def test_a_truncated_reply_is_refused_rather_than_parsed(claude):
    cut = _Reply('{"score": 8.1, "reason": "a very long sentence that ran ou',
                 stop_reason="max_tokens")
    claude.replies(cut, cut)
    result = grade_candidate("AAA", metrics(), None, SYSTEM)
    assert result["provenance"]["source"] == SOURCE_FALLBACK
    assert "max_tokens" in result["provenance"]["error"]


def test_an_unbalanced_object_does_not_crash_the_candidate(claude):
    claude.replies('{"score": 8.1, "reason": "cut off here')
    assert grade_candidate("AAA", metrics(), None, SYSTEM)["provenance"]["source"] == SOURCE_FALLBACK


def test_a_score_outside_the_rubric_is_refused(claude):
    """A 0-10 number is what ranks the shortlist. 85 sorts above everything."""
    claude.replies(json.dumps({**REPLY, "score": 85}))
    assert grade_candidate("AAA", metrics(), None, SYSTEM)["provenance"]["source"] == SOURCE_FALLBACK


# -------------------------------------------------------------- the bands ----


def test_the_grade_bands_are_the_five_words_at_the_rubrics_floors():
    """A+ 9-10, A 8-8.9, B 6.5-7.9, C 5-6.4, skip under 5 -- pinned at both
    edges of every band, since a floor moved by a tenth passes any test that
    sits in the middle."""
    assert GRADE_BANDS == ((9.0, "A+"), (8.0, "A"), (6.5, "B"), (5.0, "C"))
    assert GRADES == ("A+", "A", "B", "C", "skip")
    assert SKIP not in dict((g, f) for f, g in GRADE_BANDS), "skip has no floor of its own"
    for score, grade in ((10.0, "A+"), (9.0, "A+"), (8.9, "A"), (8.0, "A"), (7.9, "B"),
                         (6.5, "B"), (6.4, "C"), (5.0, "C"), (4.9, "skip"), (0.0, "skip")):
        assert grade_for(score) == grade, (score, grade)


def test_the_schema_and_the_shape_line_use_the_bands_own_vocabulary():
    assert SCORE_SCHEMA["properties"]["grade"]["enum"] == list(GRADES)
    assert UNGRADED not in GRADES, "the fallback's word is outside the rubric"


@pytest.mark.parametrize("score, said, band", [
    (9.5, "skip", "A+"),   # ranked first and labelled skip, both archived
    (3.0, "A+", "skip"),   # a kill criterion wearing the top label
    (7.0, "C", "B"),       # one band off, the common case
    (6.5, "C", "B"),       # on the floor
    (8.0, "A", "A"),       # agrees: kept, and nothing is logged
])
def test_a_grade_that_contradicts_its_own_score_is_the_bands(claude, caplog, score, said, band):
    """The rubric defines the grade AS the score's band, so a reply carrying
    score 9.5 and grade skip contradicts the rubric it was asked to apply.
    The score is the judgement; the band wins; the disagreement is logged."""
    claude.payload(score=score, grade=said)
    with caplog.at_level(logging.WARNING, logger="src.grader"):
        result = grade_candidate("AAA", metrics(), None, SYSTEM)
    assert (result["score"], result["grade"]) == (score, band)
    assert result["provenance"]["source"] == SOURCE_CLAUDE, "a contradiction is not a format error"
    disagreed = [r for r in caplog.records if "rubric's band" in r.getMessage()]
    assert bool(disagreed) == (said != band)
    if disagreed:
        assert repr(said) in disagreed[0].getMessage() and repr(band) in disagreed[0].getMessage()


def test_an_unknown_grade_word_is_derived_from_the_score(claude):
    """Losing a real score over a label the rubric does not list would hand
    the slot to a candidate nobody reviewed."""
    claude.payload(score=8.3, grade="Buy")
    result = grade_candidate("AAA", metrics(), None, SYSTEM)
    assert (result["score"], result["grade"]) == (8.3, "A")
    assert result["provenance"]["source"] == SOURCE_CLAUDE


# ----------------------------------------------------------- the fallback ----


def test_api_failure_falls_back_to_the_checklist(claude):
    claude.replies(RuntimeError("503 overloaded"))
    result = grade_candidate("AAA", metrics(7, 9), None, SYSTEM)
    assert isinstance(result["score"], float) and 0.0 <= result["score"] <= 10.0
    assert result["reason"] == "AI unavailable; checklist 7/9."
    assert result["key_risk"]
    assert len(claude.calls) == 2


def test_the_fallback_does_not_borrow_the_rubrics_vocabulary(claude):
    claude.replies(RuntimeError("401 invalid api key"))
    assert grade_candidate("AAA", metrics(9, 9), None, SYSTEM)["grade"] == UNGRADED


def test_the_fallback_never_scores_above_the_rubrics_own_anchor():
    """Never rises with fewer checks passed, never reaches the top of the
    scale, and a full checklist is A's floor and not A+: no chart adjustment
    is available to earn more than the anchor."""
    of = 9
    scores = [_fallback_score(passes, of) for passes in range(of + 1)]
    assert scores == sorted(scores), f"a worse checklist scores better: {scores}"
    assert _fallback_score(of, of) == 8.0 == dict((g, f) for f, g in GRADE_BANDS)["A"]
    assert grade_for(_fallback_score(of, of)) == "A"
    assert _fallback_score(0, of) == 0.0
    floors = {f for f, _ in GRADE_BANDS}
    assert all(s in floors for s in scores if s >= 5.0), "the low end of a band, always"


@pytest.mark.parametrize("passes, of", [(None, 9), (7, None), (7, 0), ("x", 9), (7, "y")])
def test_a_fallback_over_metrics_without_a_readable_checklist_is_zero_not_a_crash(passes, of):
    assert _fallback_score(passes, of) == 0.0


def test_a_fallback_row_names_the_error_and_no_model(claude):
    claude.replies(RuntimeError("401 invalid x-api-key"))
    prov = grade_candidate("AAA", metrics(), None, SYSTEM)["provenance"]
    assert prov["source"] == SOURCE_FALLBACK
    assert prov["model"] is None
    assert prov["chart_seen"] is False
    assert prov["error"] == "RuntimeError: 401 invalid x-api-key"


def test_error_text_names_the_top_level_module_and_the_class():
    import anthropic

    assert _error_text(ValueError("bad")) == "ValueError: bad"
    assert _error_text(anthropic.AnthropicError("x")) == "anthropic.AnthropicError: x"


# --------------------------------------------------------- the provenance ----


def test_a_graded_row_records_the_model_and_that_the_chart_was_seen(claude, ohlcv, tmp_path):
    chart = render_chart("AAA", ohlcv("burst"), str(tmp_path))
    result = grade_candidate("AAA", metrics(), chart, SYSTEM)
    prov = result["provenance"]
    assert prov == {"source": SOURCE_CLAUDE, "model": claude.calls[0]["model"],
                    "chart_seen": True, "error": None}
    blocks = claude.calls[0]["messages"][0]["content"]
    images = [b for b in blocks if b["type"] == "image"]
    assert len(images) == 1
    assert images[0]["source"]["media_type"] == "image/png"
    assert images[0]["source"]["data"], "the PNG was not base64-encoded into the request"


def test_a_grade_made_without_the_chart_says_so_and_attaches_nothing(claude):
    result = grade_candidate("AAA", metrics(), "charts/never-rendered.png", SYSTEM)
    assert result["provenance"]["chart_seen"] is False
    assert result["provenance"]["source"] == SOURCE_CLAUDE
    assert [b["type"] for b in claude.calls[0]["messages"][0]["content"]] == ["text"]


def test_a_row_carries_exactly_the_published_keys(claude):
    result = grade_candidate("AAA", metrics(), None, SYSTEM)
    assert set(result) == {"grade", "score", "reason", "key_risk", "entry_note", "provenance"}
    assert set(result["provenance"]) == {"source", "model", "chart_seen", "error"}


# ------------------------------------------------------------- the budget ----


def test_grade_all_stops_at_the_call_budget_and_says_so_on_every_row_past_it(claude):
    rows = grade_all(candidates(9, 8, 7, 6, 5), SYSTEM, max_calls=2)

    assert len(claude.calls) == 2, "the budget is a count of candidates asked about"
    assert [r["ticker"] for r in rows] == ["T0", "T1", "T2", "T3", "T4"], "in the order given"
    assert [r["provenance"]["source"] for r in rows] == [SOURCE_CLAUDE] * 2 + [SOURCE_NOT_GRADED] * 3
    for row in rows[2:]:
        assert row["reason"] == NOT_GRADED_REASON == "call budget"
        assert row["score"] is None, "nobody produced a number"
        assert row["grade"] == UNGRADED
        assert row["provenance"] == {"source": SOURCE_NOT_GRADED, "model": None,
                                     "chart_seen": False, "error": None}


def test_a_budget_of_zero_makes_no_call_at_all(claude):
    rows = grade_all(candidates(9, 9), SYSTEM, max_calls=0)
    assert claude.calls == []
    assert [r["provenance"]["source"] for r in rows] == [SOURCE_NOT_GRADED] * 2


def test_the_budget_is_a_count_of_candidates_and_a_retry_is_inside_it(claude):
    claude.replies("not json", json.dumps(REPLY))
    rows = grade_all(candidates(9, 9), SYSTEM, max_calls=2)
    assert len(claude.calls) == 3, "T0 retried once, then T1"
    assert [r["provenance"]["source"] for r in rows] == [SOURCE_CLAUDE, SOURCE_CLAUDE]


def test_a_crowded_out_row_is_not_a_fallback_even_on_an_outage_night(claude):
    """The two states are kept apart: a fallback was asked about and refused,
    a not-graded row was never asked about."""
    claude.replies(RuntimeError("Error code: 401 - invalid x-api-key"))
    rows = grade_all(candidates(9, 9, 9), SYSTEM, max_calls=2)
    assert [r["provenance"]["source"] for r in rows] == [SOURCE_FALLBACK, SOURCE_FALLBACK,
                                                         SOURCE_NOT_GRADED]
    assert rows[2]["provenance"]["error"] is None


# ------------------------------------------------- the real SDK transport ----


def test_the_actual_client_has_explicit_timeouts_and_no_hidden_retries(monkeypatch):
    from src import grader

    monkeypatch.setenv("ANTHROPIC_API_KEY", "offline-transport-test")
    client = grader._client()
    try:
        assert client.timeout.connect == 5.0
        assert client.timeout.read == 30.0
        assert client.timeout.write == 30.0
        assert client.timeout.pool == 30.0
        assert client.max_retries == 0
    finally:
        client.close()


def test_real_sdk_timeouts_make_only_two_attempts_then_return_a_marked_fallback(monkeypatch):
    """Through the installed SDK on a local transport: the application's one
    retry is the only repetition, and a timeout is a marked fallback."""
    import anthropic
    import httpx2 as httpx

    monkeypatch.setenv("ANTHROPIC_API_KEY", "offline-transport-test")
    real_client = anthropic.Anthropic
    clients, requests = [], []

    def timeout(request):
        requests.append(request)
        raise httpx.ReadTimeout("offline simulated read timeout", request=request)

    def client_with_local_transport(**kwargs):
        client = real_client(
            http_client=httpx.Client(transport=httpx.MockTransport(timeout)), **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(anthropic, "Anthropic", client_with_local_transport)
    try:
        row = grade_candidate("AAA", metrics(), None, SYSTEM)
    finally:
        for client in clients:
            client.close()

    assert len(requests) == 2, "only the application's one retry may repeat a request"
    assert all(request.extensions["timeout"] == {
        "connect": 5.0, "read": 30.0, "write": 30.0, "pool": 30.0,
    } for request in requests)
    assert row["provenance"]["source"] == SOURCE_FALLBACK
    assert "timeout" in row["provenance"]["error"].lower()
    assert row["grade"] == UNGRADED
