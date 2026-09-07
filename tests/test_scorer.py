"""Layers 3-5 -- chart rendering and the Anthropic boundary.

The scoring rubric itself lives in knowledge/strategy.md and is the model's
business, so nothing here asserts what a score SHOULD be. What is asserted is
everything around it: that the request is the one step 8 decided to send, that
it is identical for identical input, that the replies a model really produces
are parsed instead of discarded, that a candidate nobody scored cannot outrank
one Claude reviewed, and that every row says which of those two it is.

The Anthropic double is local to this file rather than tests/fakes.py because
these tests script a SEQUENCE of replies and set `stop_reason`, neither of
which the shared double does. Nothing here opens a socket.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import ledger
from src.scanner import Candidate, ScanConfig, detect_setup
from src.scorer import (
    KNOWLEDGE_PATH,
    MAX_TOKENS,
    RETRY_CORRECTION,
    SAMPLING_MODELS,
    STRUCTURED_OUTPUT_MODELS,
    RECORD_KEYS,
    UNSCORED_VERDICT,
    _fallback_score,
    cache_usage,
    is_fatal_auth_failure,
    metrics_payload,
    record_context,
    render_chart,
    request_kwargs,
    score_all,
    score_candidate,
    volume_ratio_basis,
)
from tests.fakes import FakeTextBlock, billed_usage

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


# ------------------------------------------------------- the scripted double --


class _Reply:
    """One `messages.create` return value, with the stop_reason a real one has.

    `usage` is attached by _ScriptedMessages rather than here, because what a
    reply is billed depends on the REQUEST that produced it -- whether it
    asked for caching, and whether it was the first of the run to do so.
    """

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
        # Billed by the same rule tests/fakes.py uses, so the two doubles in
        # this suite cannot disagree about what a cached prefix costs.
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
        base = {"score": 7.5, "reason": "synthetic", "verdict": "B+", "key_risk": "synthetic"}
        self.replies(json.dumps({**base, **fields}))


@pytest.fixture
def claude(monkeypatch) -> _Claude:
    """Replace anthropic.Anthropic with the scripted double.

    A fresh subclass per test, so a recorded call never leaks between tests.
    Defaults to one well-formed reply, which most tests do not need to change.
    """
    import anthropic

    cls = type("ScriptedAnthropicForTest", (_ScriptedAnthropic,), {"script": [], "calls": []})
    monkeypatch.setattr(anthropic, "Anthropic", cls)
    control = _Claude(cls)
    control.payload()
    return control


@pytest.fixture
def candidate(ohlcv):
    df = ohlcv("burst")
    metrics = detect_setup(df, ScanConfig())
    assert metrics, "the burst fixture must produce a candidate for this test"
    return Candidate(ticker="AAA", history=df, **metrics)


def make_lynch(passes: int = 5) -> dict:
    """A checklist result of a given strength, built by hand.

    Hand-built on purpose: this file must keep working when the 2LYNCH maths
    change what a real frame scores.
    """
    return {
        "checks": {},
        "passes": passes,
        "total": 6,
        "summary": f"{passes}/6",
        "detail_lines": [f"PASS  check_{i}: measured" for i in range(passes)],
    }


CONTEXT = {
    "pct_off_52w_high": -2.0,
    "pct_above_52w_low": 40.0,
    "perf_3mo_pct": 12.0,
    "perf_6mo_pct": 18.0,
}


def _text_of(call: dict) -> str:
    blocks = call["messages"][0]["content"]
    return "".join(b["text"] for b in blocks if b["type"] == "text")


# ------------------------------------------------------------------ charts --


def test_render_chart_writes_a_real_png(ohlcv, tmp_path):
    out = tmp_path / "charts"
    path = Path(render_chart("AAA", ohlcv("burst"), out_dir=str(out)))
    assert path == out / "AAA.png"
    data = path.read_bytes()
    assert data.startswith(PNG_MAGIC)
    assert len(data) > 20_000, "a chart this small is probably an empty canvas"


def test_render_chart_defaults_into_the_working_directory(ohlcv, tmp_path):
    """The default out_dir is relative, which is why the whole suite runs
    inside tmp_path -- see the _isolated_cwd fixture."""
    render_chart("AAA", ohlcv("burst"))
    assert (tmp_path / "charts" / "AAA.png").exists()


# ----------------------------------------------------------- the request ----


def test_the_default_model_gets_temperature_and_no_output_config():
    """claude-sonnet-4-6 accepts sampling parameters and does NOT support
    structured outputs. Both halves matter: sending output_config to it is a
    400, and omitting temperature is the unpinned sort key step 8 exists for."""
    kwargs = request_kwargs("sys", [{"type": "text", "text": "t"}],
                            model="claude-sonnet-4-6")
    assert kwargs["extra_body"] == {"temperature": 0}
    assert "output_config" not in kwargs
    assert kwargs["max_tokens"] == MAX_TOKENS


def test_a_structured_output_model_gets_the_schema_and_no_temperature():
    """The gating is per model and runs the other way round on a current one:
    output_config is supported, `temperature` is rejected with a 400."""
    kwargs = request_kwargs("sys", [{"type": "text", "text": "t"}], model="claude-opus-5")
    fmt = kwargs["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["schema"]["required"] == ["score", "reason", "verdict", "key_risk"]
    assert fmt["schema"]["additionalProperties"] is False
    assert "extra_body" not in kwargs


def test_an_unrecognised_model_is_sent_neither_gated_parameter():
    """A model newer than this file must not be guessed at: an unsupported
    parameter is a 400 on every call of the run, i.e. a total outage."""
    kwargs = request_kwargs("sys", [{"type": "text", "text": "t"}],
                            model="claude-not-released-yet-9")
    assert "extra_body" not in kwargs and "output_config" not in kwargs


def test_the_two_capability_lists_do_not_overlap_by_accident():
    """Not a style check. An id in both lists would send a model both a schema
    it may not support and a sampling parameter it may reject."""
    overlap = STRUCTURED_OUTPUT_MODELS & SAMPLING_MODELS
    assert overlap <= {"claude-haiku-4-5", "claude-opus-4-5"}, overlap


@pytest.mark.parametrize("model", ["claude-sonnet-4-6", "claude-opus-5", "claude-unknown-9"])
def test_the_request_binds_to_the_real_sdk_signature(model):
    """The one wire-shape claim this suite CAN check offline.

    anthropic 1.x removed `temperature` from Messages.create(); passing it as a
    named argument is a TypeError raised before any request is made, which the
    scorer's own except-clause would have turned into a fallback for every
    candidate of every run. Binding the built kwargs against the installed
    SDK's real signature catches that class of mistake without a socket.
    """
    import anthropic

    real = anthropic.Anthropic(api_key="unused-by-a-signature-check")
    kwargs = request_kwargs("sys", [{"type": "text", "text": "t"}], model=model)
    inspect.signature(real.messages.create).bind(**kwargs)


def test_an_unparseable_reply_is_asked_again_differently_not_resent(candidate, claude,
                                                                    tmp_path):
    """The retry used to resend the request byte-for-byte at temperature 0.

    Measured before the fix: a prose reply produced two IDENTICAL requests,
    both unparseable, and the candidate fell back anyway having been paid for
    twice. That is exactly the reasoning this function already applies to a
    rejected credential -- "a rejected key is not transient; the retry is
    theatre" -- and it was not applied to a reply that arrived in the wrong
    shape, which is equally a fact about the request that produced it.
    """
    prose = ("I'd rate this setup around 7 out of 10 -- the base is tight and "
             "the volume expansion is convincing.")
    claude.replies(prose, json.dumps({"score": 7.5, "reason": "r",
                                      "verdict": "B+", "key_risk": "k"}))
    # With a real chart, so the assertion below that the image survives the
    # retry is about an image that is actually there. Without one the content
    # is a single text block and that check cannot fail.
    chart = render_chart(candidate.ticker, candidate.history, out_dir=str(tmp_path))

    out = score_candidate(candidate, make_lynch(4), CONTEXT, chart)

    first, second = claude.calls
    assert first != second, "the retry resent the same request"
    assert RETRY_CORRECTION not in _text_of(first), "the first ask carries no correction"
    assert RETRY_CORRECTION in _text_of(second)
    # ADDED to the request, not substituted for it. A retry carrying the
    # correction alone would ask the model to score a candidate it can no
    # longer see, and the reply would parse -- so nothing downstream would
    # notice. Found by mutation: this assertion is the only thing that does.
    assert candidate.ticker in _text_of(second)
    assert make_lynch(4)["summary"] in _text_of(second)
    sent = second["messages"][0]["content"]
    assert first["messages"][0]["content"] == sent[:-1], (
        "the retry did not simply append the correction to what it already sent")
    assert sent[0]["type"] == "image", "the retry dropped the chart image"
    # The system prompt is untouched, so the cached prefix still hits -- a
    # correction that edited it would pay a second write on every retry.
    assert first["system"] == second["system"]
    assert out["provenance"]["source"] == "claude", "and the second ask landed"


def test_a_transport_failure_retries_the_request_it_already_had(candidate, claude):
    """The other half, and the reason this is not "always add a correction":
    an API error says nothing about the request's shape. Correcting a request
    that was fine tells the model its own output was wrong when it never
    produced any.
    """
    claude.replies(RuntimeError("overloaded_error: server is busy"),
                   json.dumps({"score": 6.0, "reason": "r", "verdict": "B", "key_risk": "k"}))

    out = score_candidate(candidate, make_lynch(4), CONTEXT, None)

    first, second = claude.calls
    assert first == second, "a transport error should resend what it had"
    assert RETRY_CORRECTION not in _text_of(second)
    assert out["provenance"]["source"] == "claude"


def test_the_knowledge_base_is_sent_as_a_cacheable_block(candidate, claude):
    """knowledge/strategy.md is byte-identical on every call of a run and is
    64% of each request -- measured at ~2,040 system tokens against ~430 of
    metrics and ~721 for an 869x622 chart. Without cache_control the run paid
    full price to send the same document up to MAX_TO_SCORE times a night; a
    write costs 1.25x and a read 0.1x, so break-even is the second call (1.28)
    and a full night is 46% cheaper.

    Asserted on the block, because the saving is invisible from inside the run
    -- the reply is identical either way -- and nothing else here would notice
    it being dropped.
    """
    score_candidate(candidate, make_lynch(4), CONTEXT, None)

    system = claude.calls[0]["system"]
    assert system[0]["cache_control"] == {"type": "ephemeral"}, system[0]
    # No explicit ttl: 5 minutes is the default and the cheap write. An hour
    # costs 2x, and every cache READ resets the window, so a run's sequential
    # calls hold the entry without one.
    assert "ttl" not in system[0]["cache_control"]
    # One block. Two would split the prefix and cache only the first.
    assert len(system) == 1, system


def test_the_cacheable_block_is_a_shape_the_installed_sdk_accepts():
    """A signature bind proves `system` may be a list; it does not prove the
    BLOCK is well formed. The SDK's own TextBlockParam is what says that, and
    it is checkable here with no socket -- which is the only kind of check
    this suite can make about a wire shape.
    """
    from anthropic.types import TextBlockParam

    kwargs = request_kwargs("the knowledge base", [{"type": "text", "text": "t"}])
    block = kwargs["system"][0]

    assert set(block) <= set(TextBlockParam.__annotations__), (
        f"the SDK does not know these keys: {set(block) - set(TextBlockParam.__annotations__)}")
    assert "cache_control" in TextBlockParam.__annotations__, (
        "this SDK build has no cache_control on a system block; the request "
        "would be sending an unknown field")


def test_cache_usage_reads_what_the_reply_reports_and_survives_one_that_does_not():
    """The saving is invisible from inside the run, so a cache that silently
    stopped working would cost 1.25x forever. This is the only thing that
    would say so -- and it runs after a reply has been paid for and parsed, so
    a missing or malformed usage block must not raise.
    """
    class Usage:
        cache_creation_input_tokens = 1590
        cache_read_input_tokens = 0
        input_tokens = 1109

    class Reply:
        usage = Usage()

    assert cache_usage(Reply()) == {"cache_write": 1590, "cache_read": 0, "uncached": 1109}

    class Hit(Reply):
        usage = type("U", (), {"cache_creation_input_tokens": 0,
                               "cache_read_input_tokens": 1590,
                               "input_tokens": 1109})()

    assert cache_usage(Hit())["cache_read"] == 1590

    # Every way a reply can fail to carry the numbers.
    for reply in (object(),
                  type("R", (), {"usage": None})(),
                  type("R", (), {"usage": type("U", (), {})()})(),
                  type("R", (), {"usage": type("U", (), {
                      "cache_read_input_tokens": "1590",       # a string
                      "cache_creation_input_tokens": True,     # a bool is not a count
                      "input_tokens": None})()})()):
        assert cache_usage(reply) == {"cache_write": 0, "cache_read": 0, "uncached": 0}, reply


def test_a_run_totals_the_cache_across_every_call(candidate, claude):
    """One write and N-1 reads is the whole shape of the saving, and totalling
    is what makes it visible in a log the operator can check. The double bills
    the way the API does -- the first call of a run writes the prefix, the
    rest read it -- so a flat per-call number cannot make this pass."""
    stats: dict = {}
    lynch_result = make_lynch(4)
    n = 3

    score_all([(candidate, lynch_result, CONTEXT, None)] * n, stats=stats)

    prefix = len(KNOWLEDGE_PATH.read_text()) // 4
    assert stats["cache"] == {
        "cache_write": prefix,               # once, on the first call
        "cache_read": prefix * (n - 1),      # every call after
        "uncached": 1109 * n,                # metrics and chart, per candidate
    }, stats["cache"]


def test_a_request_that_stops_asking_for_caching_reports_none(candidate, claude,
                                                              monkeypatch):
    """The inverse check, and the one that makes the test above load-bearing:
    the double reports a cached prefix only for a block that CARRIES
    cache_control, so dropping it shows up as zeroes rather than as the same
    numbers."""
    import src.scorer as scorer_mod

    real = scorer_mod.request_kwargs

    def uncached(system, content, model=None):
        kwargs = real(system, content, model)
        kwargs["system"] = system          # a bare string, the old shape
        return kwargs

    monkeypatch.setattr(scorer_mod, "request_kwargs", uncached)
    stats: dict = {}

    score_all([(candidate, make_lynch(4), CONTEXT, None)] * 3, stats=stats)

    assert stats["cache"]["cache_read"] == 0 and stats["cache"]["cache_write"] == 0


def test_the_request_carries_the_metrics_and_the_checklist(candidate, claude):
    lynch = make_lynch(4)
    score_candidate(candidate, lynch, CONTEXT, None)
    call = claude.calls[0]

    assert call["model"]
    # Not just truthy: `system` is a LIST of blocks now, and a bare string is
    # truthy too -- so the old assertion passed either way and could not see
    # the caching go away. The knowledge base has to be IN there.
    assert isinstance(call["system"], list) and call["system"], call["system"]
    assert KNOWLEDGE_PATH.read_text() in call["system"][0]["text"]
    text = _text_of(call)
    assert candidate.ticker in text
    assert lynch["summary"] in text
    for line in lynch["detail_lines"]:
        assert line in text
    assert "pct_off_52w_high" in text


def test_a_measured_criterion_that_is_not_a_check_reaches_the_model_as_one(candidate, claude):
    """`quality_notes` carries what the screener measures and does NOT vote on.

    Two things are asserted, and the second is the reason the list exists.
    The note has to arrive -- knowledge/strategy.md tells the model to weigh
    it, and an empty list would leave that instruction describing nothing.
    And it must not arrive inside `2lynch_detail`: the rulebook tells the
    model to anchor on "N of 6", so a seventh line under that heading turns
    a 6/6 into a 6/7 in the one place the anchor is read.
    """
    lynch = dict(make_lynch(4), context_checks={
        "base_breakdown": {"pass": False, "value": "worst base day -5.1% in the prior 20"},
    })

    score_candidate(candidate, lynch, CONTEXT, None)

    payload = json.loads(_text_of(claude.calls[0]).split("METRICS:\n", 1)[1]
                         .split("\n\nRespond", 1)[0])
    assert payload["quality_notes"] == ["FAIL  base_breakdown: worst base day -5.1% "
                                        "in the prior 20"]
    assert len(payload["2lynch_detail"]) == 4, "the checklist is still the checklist"
    assert not any("base_breakdown" in line for line in payload["2lynch_detail"])


def test_a_result_with_no_measured_criteria_sends_an_empty_list_not_a_missing_key(
    candidate, claude
):
    """An older archived result, or a double built before the criteria existed,
    carries no `context_checks`. The payload keeps the key so the rulebook's
    instruction about `quality_notes` never points at something absent."""
    score_candidate(candidate, make_lynch(4), CONTEXT, None)

    payload = json.loads(_text_of(claude.calls[0]).split("METRICS:\n", 1)[1]
                         .split("\n\nRespond", 1)[0])
    assert payload["quality_notes"] == []


@pytest.mark.parametrize("shape", [None, [], "x", 3, True, {"a": None}, {"a": "x"},
                                   {"a": {}}, {"a": {"pass": True}}])
def test_a_malformed_context_checks_block_sends_no_notes_rather_than_crashing(
    shape, candidate, claude
):
    """`quality_notes` is built from a block this function does not own.

    It was `.get("context_checks", {})`, whose default applies to a MISSING key
    and not to an explicit null — the exact spelling that cost this project a
    morning run once already — and its entries were hard-indexed. A wrong shape
    now produces no notes, which is what "the screener measured nothing to
    report" should look like, rather than an AttributeError inside a paid call.
    """
    lynch = dict(make_lynch(4), context_checks=shape)

    score_candidate(candidate, lynch, CONTEXT, None)

    payload = json.loads(_text_of(claude.calls[0]).split("METRICS:\n", 1)[1]
                         .split("\n\nRespond", 1)[0])
    assert payload["quality_notes"] == []


def test_the_chart_is_attached_as_an_image_block(candidate, claude, ohlcv):
    chart = render_chart("AAA", ohlcv("burst"))
    score_candidate(candidate, make_lynch(), CONTEXT, chart)
    blocks = claude.calls[0]["messages"][0]["content"]
    images = [b for b in blocks if b["type"] == "image"]
    assert len(images) == 1
    assert images[0]["source"]["media_type"] == "image/png"
    assert images[0]["source"]["data"], "the PNG was not base64-encoded into the request"


def test_a_missing_chart_is_simply_not_attached(candidate, claude):
    score_candidate(candidate, make_lynch(), CONTEXT, "charts/does-not-exist.png")
    blocks = claude.calls[0]["messages"][0]["content"]
    assert [b["type"] for b in blocks] == ["text"]


# ------------------------------------------------------- reproducibility ----


def test_the_same_candidate_produces_the_same_request_twice(candidate, claude):
    """The score is a sort key and an archived number. Nothing on our side of
    the request may differ between two runs over one candidate."""
    claude.replies(json.dumps({"score": 6.2, "reason": "r", "verdict": "B", "key_risk": "k"}))
    first = score_candidate(candidate, make_lynch(5), CONTEXT, None)
    second = score_candidate(candidate, make_lynch(5), CONTEXT, None)
    assert claude.calls[0] == claude.calls[1]
    assert first == second


def test_the_metrics_block_does_not_depend_on_dict_ordering(candidate, claude):
    """extra_context() builds the context dict, and a key order that changed
    would change the prompt bytes -- a different prompt for the same candidate,
    and a cache miss on every call."""
    score_candidate(candidate, make_lynch(5), CONTEXT, None)
    shuffled = dict(reversed(list(CONTEXT.items())))
    score_candidate(candidate, make_lynch(5), shuffled, None)
    assert _text_of(claude.calls[0]) == _text_of(claude.calls[1])


# ------------------------------------------------------------- the parser ----


def test_score_candidate_parses_the_model_reply(candidate, claude):
    claude.payload(score=8.4, reason="tight base", verdict="A", key_risk="breadth")
    result = score_candidate(candidate, make_lynch(), CONTEXT, None)
    assert result["score"] == 8.4
    assert result["verdict"] == "A"
    assert result["reason"] == "tight base"
    assert result["key_risk"] == "breadth"
    assert len(claude.calls) == 1


def test_score_candidate_parses_a_fenced_reply(candidate, claude):
    """The model sometimes wraps JSON in a markdown fence."""
    claude.replies(
        'Here you go:\n```json\n'
        '{"score": 6, "reason": "ok", "verdict": "B", "key_risk": "gap"}\n```'
    )
    result = score_candidate(candidate, make_lynch(), CONTEXT, None)
    assert isinstance(result["score"], float)
    assert result["score"] == 6.0
    assert result["verdict"] == "B"


def test_a_reply_with_trailing_prose_containing_a_brace_is_parsed(candidate, claude):
    """The old slice ran from the first `{` to the LAST `}`, so a closing brace
    anywhere in a trailing sentence made the span unparseable."""
    claude.replies(
        '{"score": 7.1, "reason": "ok", "verdict": "B+", "key_risk": "gap"}\n'
        "Note: the {Y} check fails by construction on a gap this size."
    )
    result = score_candidate(candidate, make_lynch(), CONTEXT, None)
    assert result["score"] == 7.1
    assert result["provenance"]["source"] == "claude"


def test_a_reply_with_leading_prose_containing_a_brace_is_parsed(candidate, claude):
    """And the first `{` is not always the object's: a preamble can open one."""
    claude.replies(
        "Scoring the {2LYNCH} block first.\n"
        '{"score": 4.5, "reason": "extended", "verdict": "skip", "key_risk": "chase"}'
    )
    result = score_candidate(candidate, make_lynch(), CONTEXT, None)
    assert result["score"] == 4.5


def test_a_raw_newline_inside_the_reason_is_parsed(candidate, claude):
    """A literal line break inside a JSON string is illegal JSON and a thing
    models do. It used to cost the candidate its score."""
    claude.replies('{"score": 6.5, "reason": "tight base,\nvolume expanding", '
                   '"verdict": "B", "key_risk": "gap"}')
    result = score_candidate(candidate, make_lynch(), CONTEXT, None)
    assert result["score"] == 6.5
    assert "volume expanding" in result["reason"]


def test_a_truncated_reply_is_refused_rather_than_parsed(candidate, claude):
    """stop_reason=max_tokens means the object is cut off mid-write. Parsing
    whatever arrived reports a JSON error from somewhere further down, with the
    real cause -- a cap set too low -- nowhere in the log."""
    cut = _Reply('{"score": 8.1, "reason": "a very long sentence that ran ou',
                 stop_reason="max_tokens")
    claude.replies(cut, cut)
    result = score_candidate(candidate, make_lynch(4), CONTEXT, None)
    assert result["provenance"]["source"] == "fallback"
    assert "max_tokens" in result["provenance"]["error"]


def test_an_unbalanced_object_does_not_crash_the_candidate(candidate, claude):
    """Truncation without a stop_reason to prove it: no balanced span exists."""
    claude.replies('{"score": 8.1, "reason": "cut off here')
    result = score_candidate(candidate, make_lynch(4), CONTEXT, None)
    assert result["provenance"]["source"] == "fallback"


def test_a_score_outside_the_rubric_is_refused(candidate, claude):
    """A 0-10 number is what ranks the shortlist. 85 sorts above everything."""
    claude.replies(json.dumps({"score": 85, "reason": "r", "verdict": "A+", "key_risk": "k"}))
    result = score_candidate(candidate, make_lynch(4), CONTEXT, None)
    assert result["provenance"]["source"] == "fallback"


def test_an_unknown_verdict_is_derived_from_the_score(candidate, claude):
    """The score is the thing that ranks; losing a real one over a label the
    rubric does not list would hand the slot to a candidate nobody reviewed.
    knowledge/strategy.md: "A+ (9-10), A (8-8.9), B+ (7-7.9)..."."""
    claude.replies(json.dumps({"score": 8.3, "reason": "r", "verdict": "Buy", "key_risk": "k"}))
    result = score_candidate(candidate, make_lynch(), CONTEXT, None)
    assert result["score"] == 8.3
    assert result["verdict"] == "A"
    assert result["provenance"]["source"] == "claude"


@pytest.mark.parametrize("score, said, band", [
    (9.5, "skip", "A+"),   # ranked first and labelled skip, both archived
    (3.0, "A+", "skip"),   # a kill criterion wearing the top label
    (7.0, "B", "B+"),      # one band off, the common case
    (8.0, "A", "A"),       # agrees: kept, and nothing is logged
])
def test_a_verdict_that_contradicts_its_own_score_is_the_bands(candidate, claude, caplog,
                                                                score, said, band):
    """knowledge/strategy.md defines the verdict AS the score's band -- "A+
    (9-10), A (8-8.9) ... skip (<5)" -- and _validated() derived it only for
    a word outside the rubric. A reply carrying score 9.5 and verdict "skip"
    contradicts the rubric it was asked to apply, and both halves were kept:
    the email ranked the name first and printed skip beside it. The score is
    the judgement; the label is derived from it as the rubric says, and the
    disagreement is logged so a model that keeps doing it is visible."""
    import logging

    claude.replies(json.dumps({"score": score, "reason": "r", "verdict": said, "key_risk": "k"}))
    with caplog.at_level(logging.WARNING, logger="src.scorer"):
        result = score_candidate(candidate, make_lynch(), CONTEXT, None)
    assert (result["score"], result["verdict"]) == (score, band)
    assert result["provenance"]["source"] == "claude", "a contradiction is not a format error"
    disagreed = [r for r in caplog.records if "rubric's band" in r.getMessage()]
    assert bool(disagreed) == (said != band)
    if disagreed:
        assert repr(said) in disagreed[0].getMessage() and repr(band) in disagreed[0].getMessage()


def test_one_bad_reply_is_retried_before_anything_falls_back(candidate, claude):
    """A single malformed reply used to cost the candidate its score outright."""
    claude.replies(
        "sorry, I cannot produce JSON here",
        json.dumps({"score": 7.7, "reason": "r", "verdict": "B+", "key_risk": "k"}),
    )
    result = score_candidate(candidate, make_lynch(), CONTEXT, None)
    assert len(claude.calls) == 2
    assert result["score"] == 7.7
    assert result["provenance"]["source"] == "claude"


def test_a_transient_api_error_is_retried(candidate, claude):
    claude.replies(
        RuntimeError("529 overloaded_error"),
        json.dumps({"score": 5.5, "reason": "r", "verdict": "C", "key_risk": "k"}),
    )
    result = score_candidate(candidate, make_lynch(), CONTEXT, None)
    assert len(claude.calls) == 2
    assert result["provenance"]["source"] == "claude"


# ---------------------------------------------------------- the fallback ----


def test_api_failure_falls_back_to_the_checklist(candidate, claude):
    claude.replies(RuntimeError("503 overloaded"))
    result = score_candidate(candidate, make_lynch(4), CONTEXT, None)
    assert isinstance(result["score"], float)
    assert 0.0 <= result["score"] <= 10.0
    assert result["reason"] and result["key_risk"]
    assert len(claude.calls) == 2, "a failure must be retried once before giving up"


def test_the_fallback_does_not_borrow_the_rubrics_verdict_vocabulary(candidate, claude):
    """It used to emit "B" -- a verdict from knowledge/strategy.md's table, for
    a judgement no model ever made. The email prints this string."""
    claude.replies(RuntimeError("401 invalid api key"))
    result = score_candidate(candidate, make_lynch(6), CONTEXT, None)
    assert result["verdict"] == UNSCORED_VERDICT


def test_the_fallback_never_scores_above_the_rubrics_own_anchor(candidate):
    """knowledge/strategy.md anchors the pass count: "6/6 ~ 8-10, 5/6 ~ 7-8,
    4/6 ~ 5-7, 3/6 ~ 3-5". `passes / total * 10` put 5/6 at 8.3 -- above the
    top of its band -- and 6/6 at a flat 10.0, the maximum of the whole scale,
    for a candidate no model looked at."""
    anchor_low = {3: 3.0, 4: 5.0, 5: 7.0, 6: 8.0}
    for passes, low in anchor_low.items():
        assert _fallback_score(make_lynch(passes)) == low
    assert _fallback_score(make_lynch(6)) < 10.0


# --------------------------------------------------------- the provenance ----


def test_a_scored_row_records_the_model_and_that_the_chart_was_seen(
        candidate, claude, ohlcv):
    chart = render_chart("AAA", ohlcv("burst"))
    result = score_candidate(candidate, make_lynch(), CONTEXT, chart)
    prov = result["provenance"]
    assert prov["source"] == "claude"
    assert prov["model"] == claude.calls[0]["model"]
    assert prov["chart_seen"] is True
    assert prov["error"] is None


def test_a_score_made_without_the_chart_says_so(candidate, claude):
    """score_candidate silently drops the image block when the render failed,
    so a score made blind used to be indistinguishable from one made with the
    chart -- and knowledge/strategy.md tells the model to trust the chart over
    the numbers."""
    result = score_candidate(candidate, make_lynch(), CONTEXT, "charts/never-rendered.png")
    assert result["provenance"]["chart_seen"] is False
    assert result["provenance"]["source"] == "claude"


def test_a_fallback_row_names_the_error_and_no_model(candidate, claude):
    """docs/data.json's contract: source 'fallback', a null model, and an error
    string. A fallback is never labelled claude."""
    claude.replies(RuntimeError("401 invalid x-api-key"))
    result = score_candidate(candidate, make_lynch(4), CONTEXT, None)
    prov = result["provenance"]
    assert prov["source"] == "fallback"
    assert prov["model"] is None
    assert prov["chart_seen"] is False
    assert "401 invalid x-api-key" in prov["error"]
    assert prov["error"].startswith("RuntimeError:")


# ------------------------------------------------------- the record block ----


def _streak_block(**fields):
    """A streak block in the shape src.ledger.streak() returns."""
    base = {"day": 3, "unknown_reason": None, "first_seen": "2026-08-28",
            "last_seen": "2026-09-01", "last_score": 7.5, "last_verdict": "B+",
            "last_outcome": "scored", "seen_before": 2,
            "history_from": "2026-08-03", "history_sessions": 22}
    return {**base, **fields}


def test_the_record_reaches_the_model_under_the_names_the_rulebook_uses():
    """What the ledger knows about a name is scoring input, not archive-only
    decoration: day 2 of a setup is a later entry into a move already
    underway, and until this block existed the model was told nothing about
    it. The keys are the ones knowledge/strategy.md instructs on."""
    payload = record_context(_streak_block())

    assert payload == {"setup_day": 3, "setup_unknown_reason": None,
                       "seen_before": 2, "last_seen": "2026-09-01",
                       "last_score": 7.5, "last_outcome": "scored"}


def test_a_record_that_cannot_answer_is_an_unknown_and_never_a_day_one():
    """The rule every other surface holds, held here too. A run whose history
    could not be read must not tell the model this is a fresh setup: that is a
    claim about the market assembled out of a file error."""
    payload = record_context(ledger.unknown_streak(ledger.HISTORY_UNREADABLE))

    assert payload["setup_day"] is None
    assert payload["setup_unknown_reason"] == "history_unreadable"
    assert payload["seen_before"] == 0


@pytest.mark.parametrize("streak", [None, [], "day 2", 3, {"day": "3"}, {"day": True}])
def test_no_block_the_record_cannot_produce_becomes_a_day_number(streak):
    """A block that is absent, the wrong type, or carries a day that is not a
    number reaches the model as an unknown. `"3" > 1` is a TypeError two
    surfaces already guard against with ledger.streak_day(), which is the one
    rule this reads through rather than repeating."""
    payload = record_context(streak)

    assert payload["setup_day"] is None
    assert set(payload) == {name for name, _key in RECORD_KEYS}, (
        "the keys are always the same set: a missing key reads as a fact "
        "about the candidate rather than about the record")


def test_a_day_number_and_a_reason_are_never_both_answers():
    """src.ledger keeps them exclusive at the source. A hand-edited or older
    block can carry both, and 'day 3, and also the record cannot say' is two
    answers to one question."""
    payload = record_context(_streak_block(day=3, unknown_reason="no_history"))

    assert payload["setup_day"] == 3
    assert payload["setup_unknown_reason"] is None


def test_the_record_travels_in_the_request_the_model_actually_reads(candidate, claude):
    """End of the wire this module owns: the block reaches the text block, not
    just the payload dict."""
    score_candidate(candidate, make_lynch(4), CONTEXT, None,
                    streak=_streak_block(day=2, last_outcome="lynch_gate", last_score=None))

    text = _text_of(claude.calls[0])
    assert '"setup_day": 2' in text
    assert '"last_outcome": "lynch_gate"' in text


def test_score_all_hands_each_candidate_its_own_record(candidate, claude):
    """One dict keyed by ticker, so a name with no entry is scored with the
    record's keys null rather than with another name's streak."""
    other = SimpleNamespace(**{**candidate.__dict__, "ticker": "ZZZ"})
    score_all([(candidate, make_lynch(4), CONTEXT, None),
               (other, make_lynch(4), CONTEXT, None)],
              streaks={candidate.ticker: _streak_block(day=4)})

    first, second = (_text_of(c) for c in claude.calls)
    assert '"setup_day": 4' in first
    assert '"setup_day": null' in second, "and never the previous candidate's"


def test_the_metrics_context_cannot_displace_the_record(candidate):
    """`**context` is splatted into the same dict. A measurement named like a
    record key must not answer for the record."""
    payload = metrics_payload(candidate, make_lynch(), {**CONTEXT, "setup_day": 99},
                              _streak_block(day=2))

    assert payload["setup_day"] == 2


# ------------------------------------------------- the volume-ratio label ----


def test_the_payload_does_not_carry_the_old_false_label(candidate, claude):
    """The block used to label the ratio `volume_ratio_vs_50d_avg` while the
    scanner divided by yesterday, so every candidate was described to Claude
    with a false statement -- keyed to the rubric's largest upward adjustment."""
    payload = metrics_payload(candidate, make_lynch(), CONTEXT)
    assert "volume_ratio_vs_50d_avg" not in payload
    assert payload["volume_ratio"] == candidate.volume_ratio
    assert payload["volume_ratio_basis"]


def test_the_stated_basis_actually_reproduces_the_ratio(candidate):
    """The honesty property, asserted against a candidate the real scanner
    built: whatever denominator the payload names, dividing by it must give
    back the ratio. Holds whichever denominator detect_setup() is using."""
    payload = metrics_payload(candidate, make_lynch(), CONTEXT)
    basis = payload["volume_ratio_basis"]
    if "trailing average" in basis:
        denominator = candidate.avg_volume
    elif "PREVIOUS SESSION" in basis:
        denominator = candidate.prev_volume
    else:
        pytest.fail(f"the payload named no denominator this test can check: {basis}")
    assert round(candidate.volume / denominator, 2) == round(candidate.volume_ratio, 2)


def _stand_in(**fields):
    """A candidate-shaped object. volume_ratio_basis() reads only attributes,
    which is what lets it stay true across a change to the scanner."""
    base = dict(ticker="AAA", date="2026-09-01", close=10.0, gain_pct=5.0,
                dollar_volume=1_000_000, volume=3_000_000, prev_volume=1_000_000,
                volume_ratio=3.0)
    return SimpleNamespace(**{**base, **fields})


def test_a_trailing_average_denominator_is_named_as_one():
    cand = _stand_in(avg_volume=1_000_000.0, prev_volume=2_500_000, volume_ratio=3.0)
    basis = volume_ratio_basis(cand)
    assert "trailing average" in basis and "1,000,000" in basis


def test_a_previous_session_denominator_is_named_as_one():
    """The state the code was actually in: a one-day ratio. Saying so is what
    stops the rubric's 3x Episodic Pivot rule firing on a quiet-day artefact."""
    cand = _stand_in(prev_volume=1_000_000, volume_ratio=3.0)
    basis = volume_ratio_basis(cand)
    assert "PREVIOUS SESSION" in basis
    assert "not a trailing average" in basis


def test_an_unrecognised_denominator_is_admitted_to_rather_than_guessed():
    cand = _stand_in(avg_volume=99.0, prev_volume=77, volume_ratio=3.0)
    basis = volume_ratio_basis(cand)
    assert "did not name" in basis
    assert "1,000,000" in basis, "the derived denominator should still be reported"


def test_a_basis_the_scanner_declares_wins_outright():
    cand = _stand_in(volume_ratio_basis="today's volume over the 20-day median")
    assert volume_ratio_basis(cand) == "today's volume over the 20-day median"


def test_the_prompt_tells_the_model_to_read_the_basis():
    """knowledge/strategy.md keys the Episodic Pivot adjustment off "3x+" on
    this field. The prompt and the payload have to agree about what it is."""
    from src.scorer import KNOWLEDGE_PATH

    strategy = KNOWLEDGE_PATH.read_text()
    assert "volume_ratio_basis" in strategy


# ------------------------------------------------------------- scoring all --


def _inputs(*passes: int) -> list[tuple]:
    from tests.synthetic import make_ohlcv

    out = []
    for i, p in enumerate(passes):
        df = make_ohlcv("burst", seed=[1000 + i])
        metrics = detect_setup(df, ScanConfig())
        cand = Candidate(ticker=f"T{i}", history=df, **metrics)
        out.append((cand, make_lynch(p), CONTEXT, None))
    return out


def test_score_all_drops_candidates_below_the_gate(claude):
    results = score_all(_inputs(6, 4, 1), top_n=5, min_lynch=3)
    assert {r["ticker"] for r in results} == {"T0", "T1"}
    assert len(claude.calls) == 2, "a gated-out candidate must not cost an API call"


def test_score_all_truncates_to_top_n(claude):
    results = score_all(_inputs(6, 6, 6, 6), top_n=2, min_lynch=3)
    assert len(results) == 2


def test_score_all_rows_carry_everything_the_email_needs(claude):
    (result,) = score_all(_inputs(5), top_n=5, min_lynch=3)
    assert set(result) == {
        "ticker", "date", "close", "gain_pct", "volume_ratio",
        "lynch", "lynch_detail", "score", "verdict", "reason", "key_risk",
        "provenance", "chart",
    }


def test_a_fallback_cannot_outrank_a_score_claude_actually_gave(claude):
    """The failure this ordering exists for: T0's call fails, so it keeps a
    6/6 checklist score, while T1 is reviewed and earns a bad one. Sorting on
    the number alone puts the candidate nobody looked at first."""
    claude.replies(
        RuntimeError("503"), RuntimeError("503"),
        json.dumps({"score": 1.0, "reason": "chop", "verdict": "skip", "key_risk": "k"}),
    )
    results = score_all(_inputs(6, 6), top_n=5, min_lynch=3)
    assert [r["ticker"] for r in results] == ["T1", "T0"]
    assert results[0]["score"] < results[1]["score"], (
        "the reviewed candidate ranks first while scoring lower -- which is the point"
    )
    assert results[0]["provenance"]["source"] == "claude"


def test_a_total_outage_is_countable_rather_than_silent(claude):
    """A revoked key produced a green run and a normal-looking email. Now every
    row says fallback and the counts are on the stats dict."""
    claude.replies(RuntimeError("401 invalid x-api-key"))
    stats: dict = {}
    results = score_all(_inputs(6, 5, 4), top_n=5, min_lynch=3, stats=stats)
    assert stats["scored"] == 3
    assert stats["claude"] == 0
    assert stats["fallback"] == 3
    assert [t for t, _ in stats["errors"]] == ["T0", "T1", "T2"]
    assert all(r["provenance"]["source"] == "fallback" for r in results)


def test_the_stats_rows_are_every_scored_candidate_not_the_shortlist(claude):
    """Fallbacks sort last, so on a partial outage the failures are exactly the
    rows top_n cuts away. Step 9 archives `rows`, not the returned slice."""
    claude.replies(RuntimeError("503"), RuntimeError("503"),
                   json.dumps({"score": 6.0, "reason": "r", "verdict": "B", "key_risk": "k"}))
    stats: dict = {}
    results = score_all(_inputs(6, 6, 6), top_n=1, min_lynch=3, stats=stats)
    assert len(results) == 1
    assert len(stats["rows"]) == 3
    assert stats["fallback"] == 1
    assert stats["rows"][0] == results[0]


def test_score_all_counts_nothing_when_every_candidate_was_scored(claude):
    stats: dict = {}
    score_all(_inputs(6, 5), top_n=5, min_lynch=3, stats=stats)
    assert stats["fallback"] == 0
    assert stats["errors"] == []


# --- a refused credential is not a per-candidate problem -------------------
# Sibling of the scanner's refused-feed handling: the key is a property of the
# run, so retrying it once per candidate buys the same 401 fifty times, fills
# the log with it, and reaches the same all-fallback shortlist either way.


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
    "src.scorer.ScoreFormatError: no scoreable JSON object in 812 characters of reply",
    "",
])
def test_a_transient_failure_is_not_mistaken_for_a_refused_credential(text):
    assert not is_fatal_auth_failure(text)


def test_a_refused_credential_is_not_retried(claude, candidate):
    """The pair below is the whole classification: same code path, same
    fallback, one call instead of two -- and the transient case must keep its
    retry, or this is just a broken retry rather than a recognised refusal."""
    claude.replies(RuntimeError("Error code: 401 - invalid x-api-key"))
    result = score_candidate(candidate, make_lynch(5), CONTEXT, None)

    assert len(claude.calls) == 1, "a rejected key is not transient; do not retry it"
    assert result["provenance"]["source"] == "fallback"


def test_a_transient_failure_is_still_retried(claude, candidate):
    claude.replies(RuntimeError("Error code: 503 - overloaded"))
    result = score_candidate(candidate, make_lynch(5), CONTEXT, None)

    assert len(claude.calls) == 2, "one retry before giving up"
    assert result["provenance"]["source"] == "fallback"


def test_a_refused_credential_is_not_bought_again_for_every_candidate(claude):
    """Three candidates, one refusal: one call, three honest fallback rows."""
    claude.replies(RuntimeError("Error code: 401 - invalid x-api-key"))
    stats: dict = {}
    results = score_all(_inputs(6, 5, 4), top_n=5, min_lynch=3, stats=stats)

    assert len(claude.calls) == 1, "the first refusal settles it for the run"
    assert stats["claude"] == 0 and stats["fallback"] == 3
    assert [r["provenance"]["source"] for r in results] == ["fallback"] * 3
    assert all("401" in r["provenance"]["error"] for r in results), (
        "every row must carry the reason, including the ones never sent"
    )


def test_a_transient_failure_does_not_stop_the_remaining_candidates(claude):
    """The inverse, and the brittleness guard: one flaky call must not silence
    the rest of the shortlist."""
    claude.replies(
        RuntimeError("503"), RuntimeError("503"),
        json.dumps({"score": 6.0, "reason": "r", "verdict": "B", "key_risk": "k"}),
    )
    stats: dict = {}
    score_all(_inputs(6, 6, 6), top_n=5, min_lynch=3, stats=stats)

    assert len(claude.calls) == 4, "two attempts for T0, then one each for T1 and T2"
    assert stats["claude"] == 2 and stats["fallback"] == 1
