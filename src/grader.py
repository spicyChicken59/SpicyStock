"""Claude grading: the request, the parser, the fallback and the call budget.

One candidate at a time: a metrics dict the quality layer built, a chart the
model can see, and the rulebook as a cached system prompt. Back comes a
score, a grade derived from the score's band, and three sentences. Nothing
here decides what a good burst is; knowledge/strategy.md does.

Four properties the transport keeps, each verified on the old scorer:

* Nothing on our side of the request varies between two runs over the same
  metrics: the block is serialised with sorted keys, and every request is
  built by `request_kwargs()` where a test can read it.
* A reply is parsed by a brace-matcher that ignores braces inside strings and
  tolerates raw control characters; a truncated one is refused by its
  `stop_reason` rather than parsed.
* A fallback row never claims to be Claude's: every row carries `provenance`.
* A credential the API rejects is a fact about the run, not the candidate,
  and stops the run calling again.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

#: Environment this layer cannot run without; the pipeline's preflight
#: collects it so a missing key fails before the scan. Empty counts as
#: missing -- an unset GitHub secret arrives as ''.
REQUIRED_ENV: tuple[str, ...] = ("ANTHROPIC_API_KEY",)

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

#: ~30x the reply's own size. At 400 one sentence of preamble truncated the
#: JSON, and a truncated reply is a fallback; this also covers a
#: thinking-capable model spending tokens before it answers. Truncation is
#: DETECTED (see _reply_text) rather than parsed.
MAX_TOKENS = 4096

#: Without these the SDK waits ten minutes per read and retries twice inside
#: each application attempt: six wire requests for one candidate.
GRADING_IO_TIMEOUT_SECONDS = 30.0
GRADING_CONNECT_TIMEOUT_SECONDS = 5.0

#: Application-level attempts per candidate: one retry, then the fallback.
ATTEMPTS = 2

#: The rubric's score floors, highest first; a score under the last floor is
#: `SKIP`. The band decides the grade: a model's word that disagrees with its
#: own score is replaced by the band and the disagreement is logged.
GRADE_BANDS: tuple[tuple[float, str], ...] = (
    (9.0, "A+"), (8.0, "A"), (6.5, "B"), (5.0, "C"),
)
SKIP = "skip"
#: The whole vocabulary, in rank order. One copy: the schema's enum and the
#: request's shape line are both built from it.
GRADES: tuple[str, ...] = tuple(grade for _, grade in GRADE_BANDS) + (SKIP,)

#: The grade of a row no model graded. Outside GRADES on purpose: a fallback
#: must not borrow the rubric's vocabulary for a judgement nobody made.
UNGRADED = "ungraded"

#: `provenance.source` values. A not-graded row is a name the screener liked
#: and could not afford to ask about; it is never counted with the fallbacks.
SOURCE_CLAUDE = "claude"
SOURCE_FALLBACK = "fallback"
SOURCE_NOT_GRADED = "not_graded"
NOT_GRADED_REASON = "call budget"

# ---------------------------------------------------------------- models ----
# The two request levers are model-gated in OPPOSITE directions, so neither
# can be hard-coded onto a request. Both lists come from the claude-api
# skill's model tables, and CLAUDE_MODEL lets an operator pick either side.
#
# Structured outputs (`output_config.format`): supported on these and NOT on
# claude-sonnet-4-6, the default. On the default the schema cannot be
# enforced server-side and the parser below is what stands between a chatty
# reply and a fallback.
STRUCTURED_OUTPUT_MODELS = frozenset({
    "claude-fable-5", "claude-mythos-5", "claude-opus-5", "claude-opus-4-8",
    "claude-sonnet-5", "claude-haiku-4-5", "claude-opus-4-5", "claude-opus-4-1",
})

# Sampling parameters (`temperature`): allowed on Sonnet 4.6, Opus 4.6 and
# earlier; a 400 on every call of Opus 4.7+, Sonnet 5 and Fable 5. An
# allowlist, so a model newer than this file gets no temperature and grades
# fine, where guessing the other way would fail every request of the run.
SAMPLING_MODELS = frozenset({
    "claude-sonnet-4-6", "claude-opus-4-6", "claude-sonnet-4-5",
    "claude-opus-4-5", "claude-haiku-4-5", "claude-sonnet-4-0", "claude-opus-4-0",
})

#: Sent as `output_config.format` where supported, and the source of the
#: shape line every request carries. No `minimum`/`maximum` on `score`:
#: numerical constraints are not supported by structured outputs, and the
#: range is checked by _validated() instead.
SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "number", "description": "0-10 number, one decimal allowed"},
        "grade": {"type": "string", "enum": list(GRADES),
                  "description": "the band the score falls in"},
        "reason": {"type": "string",
                   "description": ("one paragraph of at most three sentences, plain "
                                   "English, naming the single most decisive factor")},
        "key_risk": {"type": "string", "description": "one sentence"},
        "entry_note": {"type": "string",
                       "description": ("one sentence: what would make you skip it at "
                                       "tomorrow's open")},
    },
    "required": ["score", "grade", "reason", "key_risk", "entry_note"],
    "additionalProperties": False,
}

#: Appended to the request when a reply could not be parsed, and ONLY then.
#: A reply in the wrong shape is a fact about the request that produced it,
#: so resending it byte-for-byte at temperature 0 is theatre; the system
#: prompt is left untouched so the cached prefix still hits.
RETRY_CORRECTION = (
    "Your previous reply could not be parsed. Reply with ONLY the JSON object "
    "described above: no prose before or after it, no markdown fences, no "
    "explanation. The object itself is the entire reply."
)

#: Substrings of `_error_text()` that mean the next call will fail the same
#: way. Matched on the text because that is what survives into
#: `provenance.error`. Heuristic, and anything it misses costs one retry.
FATAL_AUTH_MARKERS = (
    "authenticationerror", "permissiondeniederror",
    "could not resolve authentication", "invalid x-api-key",
    "error code: 401", "error code: 403",
)


class ScoreFormatError(ValueError):
    """The model replied, but not with a score this pipeline can rank."""


# ---------------------------------------------------------------- client ----
def _client():
    import anthropic

    return anthropic.Anthropic(
        timeout=anthropic.Timeout(GRADING_IO_TIMEOUT_SECONDS,
                                  connect=GRADING_CONNECT_TIMEOUT_SECONDS),
        max_retries=0,  # grade_candidate owns the one retry and the fallback
    )  # ANTHROPIC_API_KEY from env


def _b64(path: str) -> str:
    return base64.standard_b64encode(Path(path).read_bytes()).decode()


def _error_text(exc: BaseException) -> str:
    """`module.ClassName: message`, the shape docs/data.json's provenance uses."""
    cls = type(exc)
    module = getattr(cls, "__module__", "")
    name = (cls.__qualname__ if module in ("", "builtins")
            else f"{module.split('.')[0]}.{cls.__qualname__}")
    return f"{name}: {exc}"


def is_fatal_auth_failure(error_text: str) -> bool:
    """Will every remaining call fail the way this one did?"""
    lowered = (error_text or "").lower()
    return any(marker in lowered for marker in FATAL_AUTH_MARKERS)


def grade_for(score: float) -> str:
    """The grade GRADE_BANDS assigns to a score."""
    for floor, grade in GRADE_BANDS:
        if score >= floor:
            return grade
    return SKIP


# --------------------------------------------------------------- request ----
def _reply_shape() -> str:
    """The JSON shape the request asks for, spelled from SCORE_SCHEMA."""
    parts = []
    for name in SCORE_SCHEMA["required"]:
        spec = SCORE_SCHEMA["properties"][name]
        hint = "|".join(spec["enum"]) if "enum" in spec else spec["description"]
        parts.append(f'"{name}": "<{hint}>"' if spec["type"] == "string"
                     else f'"{name}": <{hint}>')
    return "{" + ", ".join(parts) + "}"


def user_text(metrics: dict) -> str:
    """The text block; `sort_keys` so two runs over one candidate are byte-identical."""
    return (
        "Grade this momentum burst candidate strictly according to the "
        "strategy rules in your instructions.\n\n"
        f"METRICS:\n{json.dumps(metrics, indent=2, sort_keys=True, default=str)}\n\n"
        "Respond with ONLY a JSON object, no markdown fences, in this exact shape:\n"
        f"{_reply_shape()}"
    )


def request_kwargs(system: str, content: list[dict], model: str | None = None) -> dict:
    """Exactly what goes to `messages.create`, built where a test can read it.

    `system` is a LIST of one block carrying `cache_control`, because the
    rulebook is byte-identical on every call of a run and most of each
    request: a cache write costs 1.25x and a read 0.1x, so the second call
    is already ahead. No `ttl`: five minutes is the cheap write and every
    read resets the window. cache_usage() reports what actually happened.
    """
    model = model or MODEL
    kwargs: dict = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": system,
                    "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": content}],
    }
    if model in STRUCTURED_OUTPUT_MODELS:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": SCORE_SCHEMA}}
    if model in SAMPLING_MODELS:
        # Through extra_body: anthropic 1.x dropped `temperature` from
        # Messages.create()'s signature, and a named argument is a TypeError
        # before any request is made.
        kwargs["extra_body"] = {"temperature": 0}
    return kwargs


# ---------------------------------------------------------------- parser ----
def _balanced_spans(text: str):
    """Every top-level `{...}` in `text`, ignoring braces inside strings.

    An unterminated object -- a truncated reply -- yields nothing at all.
    """
    depth, start, in_string, escaped = 0, -1, False, False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0:
                yield text[start:i + 1]


def _extract_json(text: str) -> dict:
    """The first balanced object that parses and carries a score.

    `strict=False` accepts the raw line break a model leaves inside a
    `reason` string, which legal JSON refuses.
    """
    problem: Exception | None = None
    for span in _balanced_spans(text):
        try:
            obj = json.loads(span, strict=False)
        except ValueError as e:
            problem = e
            continue
        if isinstance(obj, dict) and "score" in obj:
            return obj
        problem = ScoreFormatError("a JSON object with no 'score' key")
    raise ScoreFormatError(
        f"no scoreable JSON object in {len(text)} characters of reply"
    ) from problem


def _validated(obj: dict) -> dict:
    """Coerce a parsed reply into the five fields, or raise.

    The score is the judgement the model was asked for; the grade is derived
    from it as GRADE_BANDS says. A word outside the rubric is derived
    silently; a word inside it that disagrees with its own score is replaced
    and logged, because a model that keeps doing it is worth knowing about.
    """
    try:
        score = float(obj["score"])
    except (KeyError, TypeError, ValueError) as e:
        raise ScoreFormatError(f"score {obj.get('score')!r} is not a number") from e
    if not 0.0 <= score <= 10.0:
        raise ScoreFormatError(f"score {score} is outside the 0-10 the rubric defines")

    score = round(score, 1)
    said = str(obj.get("grade", "")).strip()
    grade = grade_for(score)
    if said != grade and said in GRADES:
        log.warning("Reply scored %.1f and said %r; the rubric's band for that score "
                    "is %r, which is what is kept", score, said, grade)
    return {
        "grade": grade,
        "score": score,
        "reason": str(obj.get("reason", "")).strip(),
        "key_risk": str(obj.get("key_risk", "")).strip(),
        "entry_note": str(obj.get("entry_note", "")).strip(),
    }


def _reply_text(resp) -> str:
    """The text of a reply, refusing a truncated one by its stop_reason."""
    if getattr(resp, "stop_reason", None) == "max_tokens":
        raise ScoreFormatError(f"reply hit max_tokens={MAX_TOKENS} and is truncated")
    return "".join(b.text for b in resp.content if b.type == "text")


# -------------------------------------------------------------- fallback ----
def _band_floor(grade: str) -> float:
    return next(floor for floor, name in GRADE_BANDS if name == grade)


def _fallback_score(passes, of) -> float:
    """A checklist-only score: the LOW end of the band the pass fraction anchors.

    A full checklist earns A's floor and never A+, each sixth of the
    checklist short drops a band, and below half the map is this function's
    own conservative extension. The rubric anchors on the pass count and
    then adjusts from the chart; with no chart read, nothing can earn more
    than the anchor.
    """
    anchors = {6: _band_floor("A"), 5: _band_floor("B"), 4: _band_floor("C"),
               3: 3.0, 2: 2.0, 1: 1.0, 0: 0.0}
    try:
        fraction = float(passes) / float(of)
    except (TypeError, ValueError, ZeroDivisionError):
        fraction = 0.0
    return anchors[max(0, min(6, round(fraction * 6)))]


def _checklist_summary(metrics: dict) -> str:
    passes, of = metrics.get("passes"), metrics.get("of")
    return f"{passes}/{of}" if passes is not None and of is not None else "not measured"


def _row(grade: str, score, reason: str, source: str, error: str | None) -> dict:
    return {
        "grade": grade,
        "score": score,
        "reason": reason,
        "key_risk": "not AI-reviewed",
        "entry_note": "",
        "provenance": {"source": source, "model": None, "chart_seen": False, "error": error},
    }


def _fallback(metrics: dict, error: str) -> dict:
    """The row for a candidate Claude was asked about and did not grade."""
    return _row(UNGRADED, _fallback_score(metrics.get("passes"), metrics.get("of")),
                f"AI unavailable; checklist {_checklist_summary(metrics)}.",
                SOURCE_FALLBACK, error)


def _not_graded() -> dict:
    """The row for a candidate the call budget never reached. `score` is None:
    nobody produced a number, and a name the screener liked but could not
    afford must not be dressed as a fallback."""
    return _row(UNGRADED, None, NOT_GRADED_REASON, SOURCE_NOT_GRADED, None)


def cache_usage(resp) -> dict:
    """What the prompt cache did on one reply, as three token counts.

    The saving is invisible from inside the run -- the reply is identical
    either way -- so this is the only evidence the cache is working. Absent
    or malformed usage counts as zeroes: an accounting field is not worth
    losing a paid-for score over.
    """
    usage = getattr(resp, "usage", None)

    def _n(name: str) -> int:
        value = getattr(usage, name, None)
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    return {"cache_write": _n("cache_creation_input_tokens"),
            "cache_read": _n("cache_read_input_tokens"),
            "uncached": _n("input_tokens")}


# ----------------------------------------------------------- grading one ----
def grade_candidate(ticker: str, metrics: dict, chart_path: str | None, system_prompt: str,
                    usage: dict | None = None, attempts: int = ATTEMPTS) -> dict:
    """Ask Claude to grade one candidate.

    `metrics` is the already-built block the model reads (its `passes` and
    `of` feed the fallback); `chart_path` a PNG or None. Returns grade, score,
    reason, key_risk, entry_note and `provenance` -- who produced the number,
    under which model, and whether the chart was in front of it. `usage`, if
    given, accumulates cache_usage() across calls.
    """
    content: list[dict] = []
    chart_seen = bool(chart_path) and Path(chart_path).exists()
    if chart_seen:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": _b64(chart_path)},
        })
    content.append({"type": "text", "text": user_text(metrics)})

    kwargs = request_kwargs(system_prompt, content)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            resp = _client().messages.create(**kwargs)
            parsed = _validated(_extract_json(_reply_text(resp)))
        except Exception as e:  # noqa: BLE001 -- narrowed by the retry and provenance below
            last_error = e
            log.warning("Claude grading attempt %d/%d failed for %s: %s",
                        attempt, attempts, ticker, _error_text(e))
            if is_fatal_auth_failure(_error_text(e)):
                break  # a rejected key is not transient; the retry is theatre
            if isinstance(e, ScoreFormatError):
                # Ask again, differently. A transport error keeps the
                # original request: there was nothing wrong with it.
                kwargs = request_kwargs(
                    system_prompt, [*content, {"type": "text", "text": RETRY_CORRECTION}])
            continue
        if usage is not None:
            for key, value in cache_usage(resp).items():
                usage[key] = usage.get(key, 0) + value
        parsed["provenance"] = {
            "source": SOURCE_CLAUDE,
            "model": kwargs["model"],
            "chart_seen": chart_seen,
            "error": None,
        }
        return parsed

    log.error("Claude grading failed for %s after %d attempts (%s) -- checklist fallback",
              ticker, attempts, _error_text(last_error))
    return _fallback(metrics, _error_text(last_error))


# ----------------------------------------------------------- grading all ----
def grade_all(candidates: list[dict], system_prompt: str, max_calls: int,
              usage: dict | None = None) -> list[dict]:
    """Grade `candidates` in the order given; one row each, in the same order.

    Each candidate is `{"ticker", "metrics", "chart"}`. The first `max_calls`
    are asked about (a count of candidates; a candidate's one retry is inside
    it) and every later one is a `not_graded` row. A credential the API
    refuses is a fact about the run: after one, the remaining candidates
    within the budget are fallback rows carrying the refusal, with no further
    call. Every row carries its `ticker`. One log line says what the prompt
    cache did, written whenever a call was made.
    """
    cache = usage if usage is not None else {}
    rows: list[dict] = []
    outage: str | None = None
    asked = 0
    for position, cand in enumerate(candidates):
        ticker = cand["ticker"]
        metrics = cand.get("metrics") or {}
        if position >= max_calls:
            row = _not_graded()
        elif outage is not None:
            row = _fallback(metrics, outage)
        else:
            asked += 1
            row = grade_candidate(ticker, metrics, cand.get("chart"), system_prompt,
                                  usage=cache)
            error = row["provenance"]["error"]
            if row["provenance"]["source"] != SOURCE_CLAUDE and is_fatal_auth_failure(error):
                outage = error
                log.error("Claude refused the credential (%s) -- grading the remaining "
                          "candidates from the checklist without calling again", error)
        rows.append({"ticker": ticker, **row})

    failures = [(r["ticker"], r["provenance"]["error"]) for r in rows
                if r["provenance"]["source"] == SOURCE_FALLBACK]
    if failures:
        log.error("%d of %d candidates were NOT graded by Claude and carry a checklist "
                  "fallback: %s", len(failures), len(rows),
                  ", ".join(f"{t} ({e})" for t, e in failures[:5]))
    skipped = sum(1 for r in rows if r["provenance"]["source"] == SOURCE_NOT_GRADED)
    if skipped:
        log.warning("%d of %d candidates were never graded: the %d-call budget filled",
                    skipped, len(rows), max_calls)
    if asked:
        # "No line" and "no hits" are the states worth telling apart.
        log.info("Prompt cache: %d tokens read from cache, %d written, %d sent uncached",
                 cache.get("cache_read", 0), cache.get("cache_write", 0),
                 cache.get("uncached", 0))
    return rows
