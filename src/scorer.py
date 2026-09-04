"""
Layers 3-5 — Chart rendering + Claude scoring engine.

For each surviving candidate, we render a 4-month daily candlestick chart,
send it to Claude together with the numeric metrics and the 2LYNCH results,
and get back a structured score (0-10), a one-sentence reason, and a verdict.

The knowledge base (knowledge/strategy.md) is injected as the system prompt,
so the model is scoring against Stockbee/Qullamaggie rules — not vibes.

WHAT STEP 8 CHANGED, AND WHAT IT COULD NOT
------------------------------------------
The score this module produces is a sort key. It orders the shortlist, cuts it
to five, and is archived for the backtest the rebuild is aimed at. Four
properties follow from that, and none of them held before:

*Reproducible-ish.* `temperature` is NOT a parameter of `Messages.create()` on
the installed SDK (anthropic 1.x removed it from the typed surface — passing it
is a local `TypeError`, which the old blanket `except Exception` would have
swallowed into a fallback for every single candidate). Where the configured
model still accepts sampling parameters on the wire it is sent through
`extra_body` instead; see SAMPLING_MODELS. This narrows run-to-run variance,
and honestly: it does not remove it. `temperature=0` never guaranteed identical
outputs on any model, and on Opus 4.7+/Sonnet 5/Opus 5 the parameter is
rejected outright, so a run under those models has no determinism lever at all.
What IS guaranteed is that nothing on OUR side of the request varies between
two runs over the same candidate — the metrics block is serialised with sorted
keys, carries no clock, and the request kwargs are built by one function
(`request_kwargs()`) that a test can read.

*Parseable.* The reply used to be sliced between the first `{` and the last
`}` and handed to `json.loads`, which raises on a truncated object, on trailing
prose containing a brace, and on the unescaped newline a model puts inside a
`reason` string maybe one time in fifty. Each raise silently became a fallback.
Now: structured outputs where the model supports them (`output_config.format`,
see STRUCTURED_OUTPUT_MODELS — the default model is NOT one of them), a
brace-matcher that ignores braces inside strings and tries every balanced span,
tolerance for raw control characters, an explicit check for
`stop_reason == "max_tokens"` rather than parsing a truncated object, and one
retry before anything gives up.

*Rankable.* A fallback can no longer outrank a real score. Not "usually does
not" — cannot: `score_all()` sorts on `(scored_by_claude, score)`, so every
Claude score sorts above every fallback whatever the numbers are.

*Countable.* Every result carries `provenance`, and `score_all()` fills an
optional `stats` dict and logs an error naming how many candidates were never
seen by Claude. A revoked API key used to produce a green run and a
normal-looking email; it now produces a shortlist in which every row says
`source: fallback` and a log line saying so. Step 5 consumed those counts:
src.pipeline reads the same `stats` dict, so a fallback also reaches the
operator as a banner on the email and a non-zero exit code, and a credential
the API rejects stops the run calling again (see is_fatal_auth_failure) rather
than buying the same refusal once per candidate.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

#: Environment this layer cannot run without. Collected by src.pipeline's
#: preflight, so a run without a key fails before the scan rather than after
#: every candidate has quietly fallen back to checklist arithmetic. Empty
#: counts as missing — an unset GitHub secret arrives as ''.
REQUIRED_ENV: tuple[str, ...] = ("ANTHROPIC_API_KEY",)

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
KNOWLEDGE_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "strategy.md"

# The requested object is four short fields — roughly 120 tokens including the
# 25-word reason. 400 left so little headroom that a model adding one sentence
# of preamble truncated the JSON, and a truncated reply is indistinguishable
# from a broken one: it became a fallback. 4096 is ~30x the shape and also
# covers a thinking-capable model spending tokens before it answers. Truncation
# is additionally DETECTED (see _reply_text) instead of being parsed.
MAX_TOKENS = 4096

# knowledge/strategy.md: "Verdicts: A+ (9-10), A (8-8.9), B+ (7-7.9),
# B (6-6.9), C (5-5.9), skip (<5)." Kept in the same order so _verdict_for()
# below reads as that table does.
VERDICT_BANDS: tuple[tuple[float, str], ...] = (
    (9.0, "A+"), (8.0, "A"), (7.0, "B+"), (6.0, "B"), (5.0, "C"),
)
VERDICTS = frozenset({"A+", "A", "B+", "B", "C", "skip"})

#: `verdict` when nobody scored the candidate. Deliberately not one of
#: VERDICTS: the fallback used to emit "B", borrowing the rubric's vocabulary
#: for a judgement no model ever made.
UNSCORED_VERDICT = "unscored"

# ---------------------------------------------------------------- models ----
# The two hardening levers this step wanted are model-gated in OPPOSITE
# directions, so neither can be hard-coded onto a request. Both lists are from
# the claude-api skill (shared/tool-use-concepts.md, shared/models.md), checked
# rather than remembered, and CLAUDE_MODEL lets an operator pick either side.
#
# Structured outputs (`output_config.format`) — Fable 5, Opus 5, Opus 4.8,
# Sonnet 5, Haiku 4.5, and legacy Opus 4.5/4.1. NOT claude-sonnet-4-6, which is
# what MODEL defaults to and what README documents. So on today's default the
# schema cannot be enforced server-side and the parser below is what stands
# between a chatty reply and a fallback; point CLAUDE_MODEL at one of these and
# the schema is enforced with no code change.
STRUCTURED_OUTPUT_MODELS = frozenset({
    "claude-fable-5", "claude-mythos-5", "claude-opus-5", "claude-opus-4-8",
    "claude-sonnet-5", "claude-haiku-4-5", "claude-opus-4-5", "claude-opus-4-1",
})

# Sampling parameters (`temperature`/`top_p`/`top_k`) — allowed on Sonnet 4.6,
# Opus 4.6 and earlier; REMOVED on Opus 4.7, Opus 4.8, Opus 5, Sonnet 5 and
# Fable 5, where sending one is a 400 on every call. An allowlist, not a
# denylist, on purpose: an unrecognised model (a release newer than this file)
# gets no temperature and scores fine, whereas guessing the other way would
# fail every request of the run.
SAMPLING_MODELS = frozenset({
    "claude-sonnet-4-6", "claude-opus-4-6", "claude-sonnet-4-5",
    "claude-opus-4-5", "claude-haiku-4-5", "claude-sonnet-4-0", "claude-opus-4-0",
})

# Sent as `output_config.format` where supported. No `minimum`/`maximum` on
# `score`: the skill's schema limitations say numerical constraints are not
# supported, and an unsupported keyword is not a silent no-op. The range is
# checked by _validated() instead, which has to exist anyway for the models
# that cannot enforce a schema at all.
SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "number"},
        "reason": {"type": "string"},
        "verdict": {"type": "string", "enum": sorted(VERDICTS)},
        "key_risk": {"type": "string"},
    },
    "required": ["score", "reason", "verdict", "key_risk"],
    "additionalProperties": False,
}


class ScoreFormatError(ValueError):
    """The model replied, but not with a score this pipeline can rank."""


# ---------------------------------------------------------------- charts ----
def render_chart(ticker: str, df: pd.DataFrame, out_dir: str = "charts") -> str:
    """Render a daily candlestick + volume chart (last ~85 sessions) to PNG."""
    import mplfinance as mpf

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = str(Path(out_dir) / f"{ticker}.png")
    plot_df = df.iloc[-85:].copy()
    plot_df.index = pd.to_datetime(plot_df.index)

    mpf.plot(
        plot_df,
        type="candle",
        volume=True,
        mav=(10, 20, 50),
        style="yahoo",
        title=f"{ticker} — daily",
        savefig=dict(fname=path, dpi=110, bbox_inches="tight"),
        figsize=(10, 6),
    )
    return path


# ---------------------------------------------------------------- claude ----
def _client():
    import anthropic

    return anthropic.Anthropic()  # ANTHROPIC_API_KEY from env


def _b64(path: str) -> str:
    return base64.standard_b64encode(Path(path).read_bytes()).decode()


def _error_text(exc: BaseException) -> str:
    """`module.ClassName: message`, the shape docs/data.json's provenance uses."""
    cls = type(exc)
    module = getattr(cls, "__module__", "")
    name = cls.__qualname__ if module in ("", "builtins") else f"{module.split('.')[0]}.{cls.__qualname__}"
    return f"{name}: {exc}"


#: Substrings of `_error_text()` that mean the next call will fail the same
#: way. Sibling of the scanner's _is_feed_denied(), for the same reason and
#: with the same caveat: a credential the API rejects is a property of the RUN,
#: not of the candidate, so retrying it 25 times buys 50 identical failures, a
#: log nobody can read, and a shortlist that is entirely fallbacks either way.
#: Matched against the text rather than the exception because that is what
#: survives into `provenance.error`, which is where score_all() reads it and
#: where step 9 will archive it. Heuristic, and unconfirmed against a live
#: refusal — everything it misses simply costs the old retries.
FATAL_AUTH_MARKERS = (
    "authenticationerror", "permissiondeniederror",
    "could not resolve authentication", "invalid x-api-key",
    "error code: 401", "error code: 403",
)


def is_fatal_auth_failure(error_text: str) -> bool:
    """Will every remaining call fail the way this one did?"""
    lowered = (error_text or "").lower()
    return any(marker in lowered for marker in FATAL_AUTH_MARKERS)


def _verdict_for(score: float) -> str:
    """The verdict knowledge/strategy.md assigns to a score."""
    for floor, verdict in VERDICT_BANDS:
        if score >= floor:
            return verdict
    return "skip"


# ------------------------------------------------------------- the payload --
def volume_ratio_basis(cand) -> str:
    """What `cand.volume_ratio` is a ratio OF, derived rather than asserted.

    This block used to label the field `volume_ratio_vs_50d_avg` while the
    scanner divided by YESTERDAY, so every candidate was described to Claude
    with a false statement — and not a harmless one: strategy.md keys its
    largest upward adjustment, the Episodic Pivot, off "3x+" on this number,
    and a one-day denominator inflates it exactly when the previous session was
    quiet, which is the consolidation the setup screens for.

    Nothing here asserts a denominator. The scanner's own numbers are divided
    out and the answer is whichever one reproduces the ratio, so this stays
    true across a change to detect_setup() that this module never hears about.
    An explicit `volume_ratio_basis` on the Candidate, if one is ever added,
    wins outright.
    """
    declared = getattr(cand, "volume_ratio_basis", None)
    if declared:
        return str(declared)

    volume = getattr(cand, "volume", None)
    ratio = getattr(cand, "volume_ratio", None)
    if not volume or not ratio:
        return "unknown — the scanner supplied no volume or no ratio"

    def reproduces(denominator) -> bool:
        # detect_setup() rounds the ratio to 2dp; match at that resolution.
        return bool(denominator) and round(volume / denominator, 2) == round(ratio, 2)

    average = getattr(cand, "avg_volume", None)
    if reproduces(average):
        return (f"today's volume divided by this stock's own trailing average of "
                f"{average:,.0f} shares, measured over the sessions BEFORE today")
    previous = getattr(cand, "prev_volume", None)
    if reproduces(previous):
        return (f"today's volume divided by the PREVIOUS SESSION's {previous:,.0f} "
                f"shares — a one-day comparison, not a trailing average, so a "
                f"single quiet day inflates it")
    return (f"today's volume divided by a baseline of about {volume / ratio:,.0f} "
            f"shares, which the scanner did not name")


def metrics_payload(cand, lynch_result: dict, context: dict) -> dict:
    """The numbers Claude is asked to score. Every key means what it says."""
    payload = {
        "ticker": cand.ticker,
        "burst_date": cand.date,
        "close": cand.close,
        "gain_pct": cand.gain_pct,
        "volume": getattr(cand, "volume", None),
        "prev_session_volume": getattr(cand, "prev_volume", None),
        "volume_ratio": cand.volume_ratio,
        "volume_ratio_basis": volume_ratio_basis(cand),
        "dollar_volume": cand.dollar_volume,
        **context,
        "2lynch_summary": lynch_result["summary"],
        "2lynch_detail": lynch_result["detail_lines"],
        # Measured criteria that are NOT checklist votes and do not move the
        # pass count -- kept out of 2lynch_detail for exactly that reason,
        # since a model told to anchor on "N of 6" must not be handed a
        # seventh line under that heading. knowledge/strategy.md says how to
        # weigh them; the line carries the threshold the code applied, so the
        # rulebook never holds a second copy of the number.
        "quality_notes": [
            f"{'PASS' if c['pass'] else 'FAIL'}  {name}: {c['value']}"
            for name, c in lynch_result.get("context_checks", {}).items()
        ],
    }
    average = getattr(cand, "avg_volume", None)
    if average is not None:
        payload["avg_volume"] = average
    return payload


def user_text(metrics: dict) -> str:
    """The text block. `sort_keys` so two runs over one candidate are byte-identical."""
    return (
        "Score this 4% Momentum Burst candidate strictly according to the "
        "strategy rules in your instructions.\n\n"
        f"METRICS:\n{json.dumps(metrics, indent=2, sort_keys=True, default=str)}\n\n"
        "Respond with ONLY a JSON object, no markdown fences, in this exact shape:\n"
        '{"score": <0-10 number, one decimal allowed>, '
        '"reason": "<one sentence, max 25 words>", '
        '"verdict": "<A+|A|B+|B|C|skip>", '
        '"key_risk": "<one short phrase>"}'
    )


def request_kwargs(system: str, content: list[dict], model: str | None = None) -> dict:
    """Exactly what goes to `messages.create`, built where a test can read it.

    Separate from score_candidate() because the two model-gated parameters
    below are the whole of step 8's request change, and a claim about a request
    that can only be checked by sending one is not checkable here at all — the
    suite has no network.
    """
    model = model or MODEL
    kwargs: dict = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": content}],
    }
    if model in STRUCTURED_OUTPUT_MODELS:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": SCORE_SCHEMA}}
    if model in SAMPLING_MODELS:
        # Through extra_body because anthropic 1.x dropped `temperature` from
        # Messages.create()'s signature; passing it as a named argument raises
        # TypeError before any request is made.
        kwargs["extra_body"] = {"temperature": 0}
    return kwargs


# -------------------------------------------------------------- the parser --
def _balanced_spans(text: str):
    """Every top-level `{...}` in `text`, ignoring braces inside strings.

    A brace-counting scan rather than `find("{")`/`rfind("}")`, because that
    slice spans from the first brace of a preamble to the last brace of a
    trailing sentence and parses neither. An unterminated object — a truncated
    reply — yields nothing at all, which is the correct answer for one.
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

    `strict=False` accepts the raw control characters a model leaves in a
    `reason` when it writes a line break inside the sentence — legal JSON says
    no, and a rejected reply used to cost the candidate its score.
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
    """Coerce a parsed reply into the four fields, or raise.

    A verdict outside the rubric is DERIVED from the score rather than
    rejected: the score is the thing that ranks, and losing a real one over a
    cosmetic label would hand the slot to a candidate nobody reviewed.
    """
    try:
        score = float(obj["score"])
    except (KeyError, TypeError, ValueError) as e:
        raise ScoreFormatError(f"score {obj.get('score')!r} is not a number") from e
    if not 0.0 <= score <= 10.0:
        raise ScoreFormatError(f"score {score} is outside the 0-10 the rubric defines")

    score = round(score, 1)
    verdict = str(obj.get("verdict", "")).strip()
    if verdict not in VERDICTS:
        verdict = _verdict_for(score)
    return {
        "score": score,
        "reason": str(obj.get("reason", "")).strip(),
        "verdict": verdict,
        "key_risk": str(obj.get("key_risk", "")).strip(),
    }


def _reply_text(resp) -> str:
    """The text of a reply, refusing a truncated one.

    `stop_reason == "max_tokens"` means the object is cut off mid-write. The
    old code parsed whatever arrived and raised somewhere further down, where
    the reason for the failure was no longer visible.
    """
    if getattr(resp, "stop_reason", None) == "max_tokens":
        raise ScoreFormatError(
            f"reply hit max_tokens={MAX_TOKENS} and is truncated"
        )
    return "".join(b.text for b in resp.content if b.type == "text")


# ------------------------------------------------------------ scoring one --
def _fallback_score(lynch_result: dict) -> float:
    """A checklist-only score: the LOW end of the band the rubric anchors.

    knowledge/strategy.md tells Claude to anchor on the pass count — "6/6 ~
    8-10, 5/6 ~ 7-8, 4/6 ~ 5-7, 3/6 ~ 3-5" — and then adjust from the chart.
    The old fallback was `passes / total * 10`, which lands 5/6 at 8.3, above
    the top of that band, and 6/6 at a flat 10.0. A candidate nobody looked at
    scored better than most candidates somebody did. The low end is the
    conservative reading of the same table, and no chart adjustment is
    available to earn more than it.
    """
    anchors = {0: 0.0, 1: 1.0, 2: 2.0, 3: 3.0, 4: 5.0, 5: 7.0, 6: 8.0}
    total = lynch_result.get("total") or 6
    sixths = max(0, min(6, round(lynch_result["passes"] / total * 6)))
    return anchors[sixths]


def _fallback(cand, lynch_result: dict, error: str) -> dict:
    return {
        "score": _fallback_score(lynch_result),
        "reason": f"AI unavailable; checklist score {lynch_result['summary']}.",
        "verdict": UNSCORED_VERDICT,
        "key_risk": "not AI-reviewed",
        "provenance": {
            "source": "fallback",
            "model": None,
            "chart_seen": False,
            "error": error,
        },
    }


def score_candidate(cand, lynch_result: dict, context: dict, chart_path: str | None,
                    attempts: int = 2) -> dict:
    """Ask Claude to score one candidate.

    Returns score/reason/verdict/key_risk plus `provenance`, which says who
    produced the number, under which model, and whether the chart was actually
    in front of it. The success and failure paths used to return the same four
    keys, so a score made blind — the render failed and the image block was
    quietly dropped — was indistinguishable from one made with the chart.
    """
    system = KNOWLEDGE_PATH.read_text()
    metrics = metrics_payload(cand, lynch_result, context)

    content: list[dict] = []
    chart_seen = bool(chart_path) and Path(chart_path).exists()
    if chart_seen:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": _b64(chart_path)},
        })
    content.append({"type": "text", "text": user_text(metrics)})

    kwargs = request_kwargs(system, content)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            resp = _client().messages.create(**kwargs)
            parsed = _validated(_extract_json(_reply_text(resp)))
        except Exception as e:  # noqa: BLE001 — narrowed by the retry+provenance below
            last_error = e
            log.warning("Claude scoring attempt %d/%d failed for %s: %s",
                        attempt, attempts, cand.ticker, _error_text(e))
            if is_fatal_auth_failure(_error_text(e)):
                break  # a rejected key is not transient; the retry is theatre
            continue
        parsed["provenance"] = {
            "source": "claude",
            "model": kwargs["model"],
            "chart_seen": chart_seen,
            "error": None,
        }
        return parsed

    # Never dies on one bad call — but says so, in the row and in the log.
    log.error("Claude scoring failed for %s after %d attempts (%s) — checklist fallback",
              cand.ticker, attempts, _error_text(last_error))
    return _fallback(cand, lynch_result, _error_text(last_error))


# ------------------------------------------------------------ scoring all --
def _rank_key(row: dict) -> tuple[bool, float]:
    """Claude's scores rank above every fallback, whatever the numbers say.

    Structural, not arithmetic: with `reverse=True`, True sorts before False,
    so no fallback value can displace a reviewed candidate even if the
    checklist maths changes again. A total outage still emails a shortlist —
    the run must not die on one bad call — but it is a shortlist of rows that
    all say `unscored`, in checklist order, not a plausible-looking ranking.
    """
    return (row["provenance"]["source"] == "claude", row["score"])


def score_all(scored_inputs: list[tuple], top_n: int = 5, min_lynch: int = 3,
              stats: dict | None = None) -> list[dict]:
    """scored_inputs: list of (candidate, lynch_result, context, chart_path).

    Applies the hard checklist gate, has Claude score survivors, and returns
    the top N as plain dicts ready for the email layer.

    `stats`, if given, is filled with what the returned slice cannot show:
    every scored row in rank order (`rows`, untruncated — what step 9 archives),
    how many were really scored (`claude`), how many fell back (`fallback`),
    and one `(ticker, error)` per failure. The count has to be taken over all
    of them: fallbacks now sort last, so on a partial outage the failures are
    exactly the rows `top_n` cuts away.
    """
    results = []
    outage: str | None = None
    for cand, lynch_result, context, chart_path in scored_inputs:
        if lynch_result["passes"] < min_lynch:
            log.info("%s gated out (2LYNCH %s)", cand.ticker, lynch_result["summary"])
            continue
        if outage is not None:
            # The first candidate already proved the credential is refused.
            # Every row still gets a fallback and says so; none of them costs
            # another doomed request.
            ai = _fallback(cand, lynch_result, outage)
        else:
            ai = score_candidate(cand, lynch_result, context, chart_path)
            error = ai["provenance"]["error"]
            if ai["provenance"]["source"] != "claude" and is_fatal_auth_failure(error):
                outage = error
                log.error("Claude refused the credential (%s) — scoring the "
                          "remaining candidates from the checklist without "
                          "calling again", error)
        results.append({
            "ticker": cand.ticker,
            "date": cand.date,
            "close": cand.close,
            "gain_pct": cand.gain_pct,
            "volume_ratio": cand.volume_ratio,
            "lynch": lynch_result["summary"],
            "lynch_detail": lynch_result["detail_lines"],
            "score": ai["score"],
            "verdict": ai.get("verdict", "?"),
            "reason": ai.get("reason", ""),
            "key_risk": ai.get("key_risk", ""),
            "provenance": ai["provenance"],
            "chart": chart_path,
        })

    results.sort(key=_rank_key, reverse=True)

    failures = [(r["ticker"], r["provenance"]["error"]) for r in results
                if r["provenance"]["source"] != "claude"]
    if failures:
        log.error("%d of %d candidates were NOT scored by Claude and carry a "
                  "checklist fallback: %s", len(failures), len(results),
                  ", ".join(f"{t} ({e})" for t, e in failures[:5]))
    if stats is not None:
        stats.update({
            "scored": len(results),
            "claude": len(results) - len(failures),
            "fallback": len(failures),
            "errors": failures,
            "rows": results,
        })
    return results[:top_n]
