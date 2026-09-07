"""
Layers 3-4 — Chart rendering + Claude scoring engine.
(Layer 5 is the archive, and it lives in src/ledger.py.)

For each surviving candidate, we render a 4-month daily candlestick chart,
send it to Claude together with the numeric metrics, the 2LYNCH results and
what the RECORD already knows about the name (record_context), and get back a
structured score (0-10), a one-sentence reason, and a verdict.

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
two runs over the same candidate GIVEN THE SAME RECORD — the metrics block is
serialised with sorted keys, carries no clock, and the request kwargs are built
by one function (`request_kwargs()`) that a test can read. The record is the
qualification: the block record_context() carries is read off docs/ledger.json,
and streak() excludes appearances on the session itself so a re-scan is stable,
but a backfill of an OLDER session landing between two runs of the same one
changes what the file says and therefore what the request carries.

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

from .ledger import NO_STREAK_RECORDED, UNCOUNTED_UNKNOWNS, streak_day

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

# Fail into the existing marked fallback while the workflow still has time
# to publish. The SDK otherwise waits ten minutes per read and retries twice
# inside each application attempt: six wire requests for one candidate.
SCORING_IO_TIMEOUT_SECONDS = 30.0
SCORING_CONNECT_TIMEOUT_SECONDS = 5.0

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
    """Render a daily candlestick + volume chart (last ~85 sessions) to PNG.

    A bar missing one of O, H, L or C is dropped BEFORE the tail is taken, so
    one hole is a gap in the picture rather than no picture. mplfinance
    refuses a frame whose four price columns do not share their missing rows
    -- "O,H,L,C must have the same amount of missing data!", reproduced on
    each of the four -- and src.pipeline catches that, records `chart_seen`
    false and scores the candidate on the numbers alone, which
    knowledge/strategy.md tells the model to trust LESS than the picture. One
    unreadable bar in eighty-five is not a reason to show none. Dropped
    before the slice rather than after, so a night with holes still shows
    eighty-five sessions. Volume is deliberately not in the set: a NaN there
    renders, checked rather than assumed, and the volume panel is the half a
    reader can still read across a hole.
    """
    import mplfinance as mpf

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = str(Path(out_dir) / f"{ticker}.png")
    plot_df = df.dropna(subset=[c for c in ("Open", "High", "Low", "Close")
                                if c in df.columns]).iloc[-85:].copy()
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

    return anthropic.Anthropic(
        timeout=anthropic.Timeout(SCORING_IO_TIMEOUT_SECONDS,
                                  connect=SCORING_CONNECT_TIMEOUT_SECONDS),
        max_retries=0,  # score_candidate owns the one retry and the fallback
    )  # ANTHROPIC_API_KEY from env


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
        # detect_setup() rounds the ratio to 2dp -- so match at that
        # resolution, and allow ONE step of it. The two numbers in the payload
        # are rounded from different originals: `volume_ratio` is
        # round(volume / mean, 2) off the unrounded trailing mean, while
        # `avg_volume` is round(mean) -- whole shares. Dividing by the archived
        # average therefore lands a cent away from the archived ratio whenever
        # the rounding falls badly, and an exact comparison then told the model
        # "a baseline of about 137,177 shares, which the scanner did not name"
        # with avg_volume 137,235 in the same block. Reproduced on that pair
        # (1,611,825 / 137,234.66 -> 11.75, and 11.74 through the archived
        # average); measured at about 1 candidate in 8,000 over 200,000
        # plausible volume/average pairs, which is rare and is not zero, and
        # the failure is a false denial rather than a wrong number. (That
        # baseline is 1,611,825 / 11.75 = 137,177, and this comment quoted it
        # as 137,220 -- a number the function cannot print; and "three lines
        # above" was a claim about a payload user_text() serialises with
        # sort_keys, which puts avg_volume near the top of the block and this
        # near the bottom. Both were retyped from the sentence rather than run.)
        #
        # ONE STEP AND NOT TWO, and what two would cost is measurable rather
        # than rhetorical. The AVERAGE is tried first, so the mislabel a wider
        # slack buys is the trailing average claiming a ratio the PREVIOUS
        # SESSION produced -- this comment had it the other way round, and put
        # the boundary at 0.1 when the discrimination is already gone at 0.02:
        # test_one_rounding_step_of_slack_does_not_let_yesterday_pose_as_the_average
        # fails at two steps, on a pair whose average is two steps out and
        # whose previous session is exact. One step is not free either. In the
        # counterfactual this function is built for -- detect_setup dividing by
        # YESTERDAY, an unrelated trailing average in the payload -- the
        # average falsely reproduces the ratio about three times as often at
        # one step as at exact equality (0.70% against 0.24% over 500,000
        # plausible pairs, measured here). The trade is the right way round
        # today, because detect_setup does divide by the trailing mean, so the
        # slack fixes a real false denial while the false positive is
        # counterfactual -- but the promise in the docstring above, that this
        # stays true across a change to detect_setup() this module never hears
        # about, is weaker than it was by that factor.
        #
        # The difference is ROUNDED before it is compared, and that is the
        # same defect one level down rather than a flourish: 0.01 is not a
        # double, so the gap between two 2dp numbers one step apart lands
        # either side of it depending on their magnitude. Measured over two
        # million plausible pairs, 69 of 209 one-step straddles came out at
        # 0.010000000000000009 and would have been refused by a bare
        # `<= 0.01` -- a third of the cases this exists for, failing the same
        # way the thing it fixes does.
        return (bool(denominator)
                and round(abs(round(volume / denominator, 2) - round(ratio, 2)), 2) <= 0.01)

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


def _as_dict(value) -> dict:
    """`value` when it is a dict, {} otherwise — no exceptions, ever.

    `or {}` is not enough and `.get(k, {})` is less: the first lets a truthy
    non-dict through to .items(), the second only defends a MISSING key and
    not an explicit null. Both spellings have cost this project a run.
    """
    return value if isinstance(value, dict) else {}


#: What a streak block contributes to the metrics, and under which names. The
#: order is the streak's own; `sort_keys` on the payload is what a reader sees.
RECORD_KEYS: tuple[tuple[str, str], ...] = (
    ("setup_day", "day"),
    ("setup_unknown_reason", "unknown_reason"),
    ("seen_before", "seen_before"),
    ("last_seen", "last_seen"),
    ("last_score", "last_score"),
    ("last_outcome", "last_outcome"),
    # The record's own span, which is what makes an unknown sayable. Without
    # these the model was handed the bare word -- and on the first scheduled
    # night, and every night until the file reaches MAX_STREAK_GAP_SESSIONS
    # sessions back, EVERY candidate is a window_not_covered unknown, so the
    # bare word was the whole answer. src.emailer's _no_day_note() has told
    # the human "burst on 8 of the 8 sessions in the record, which begins
    # 2026-08-20" since step 10; an unknown over a one-session record is not
    # the same evidence as one over two hundred, and the model could not tell
    # them apart.
    ("history_sessions", "history_sessions"),
    ("history_from", "history_from"),
)


def record_context(streak) -> dict:
    """What the RECORD already knows about this name, for the scoring request.

    The strategy is named after Day 1, and until this existed the model was
    never told which day it was looking at: src.pipeline read the ledger AFTER
    the score stage, so night 2 of a two-night burst was scored as if the file
    had never seen the name. The block travels here in the shape src.ledger
    built and src.emailer renders, one rename per key and no arithmetic.

    THE NULLS ARE THE POINT. A record that cannot answer -- unreadable, empty,
    undatable, or not reaching back far enough -- publishes `day: null` with
    the reason word, and every surface is forbidden to dress that up as a
    confident day 1. So is this one: an absent or malformed block produces the
    same keys with nulls, never a day number, and `setup_unknown_reason`
    carries the record's own word rather than a sentence invented here -- or,
    where there is no block to carry one, src.ledger's word for that
    (NO_STREAK_RECORDED), because a null day beside a null reason is a fifth
    state the rulebook says cannot exist and the model has no word for.

    AND THE SAME RULE ONE FIELD OVER, which this function used to break:
    `seen_before` is 0 in the states where nobody counted (see
    src.ledger.UNCOUNTED_UNKNOWNS), and 0 earlier sightings over a file that
    could not be opened is exactly the confident sentence the day number is
    refused. Those send null; the unknowns whose count IS a reading -- an
    empty record, and a record that simply does not reach back far enough --
    keep it, and the span keys say what it was counted over.

    `setup_day` goes through ledger.streak_day(), the one rule that says what
    counts as a day: a block carrying `"day": "3"` is not day 3 to a reader
    and must not be day 3 to the model either.
    """
    block = _as_dict(streak)
    payload = {name: block.get(key) for name, key in RECORD_KEYS}
    payload["setup_day"] = streak_day(block)
    if payload["setup_day"] is not None:
        # Both filled would be two answers to one question. src.ledger keeps
        # them exclusive at the source; this keeps them exclusive if a
        # hand-edited or older block does not.
        payload["setup_unknown_reason"] = None
    elif not payload["setup_unknown_reason"]:
        # A null day with no reason at all was a fifth state the rulebook
        # says cannot exist -- and the one tools/live_check.py sends to the
        # live endpoint, since it scores a candidate with no record block.
        # The email and the page have had a sentence for it since step 10
        # (NO_STREAK_BLOCK, "this run recorded none"); the model had silence.
        payload["setup_unknown_reason"] = NO_STREAK_RECORDED
    reason = payload["setup_unknown_reason"]
    if isinstance(reason, str) and reason in UNCOUNTED_UNKNOWNS:
        # 0 earlier sightings is a reading of the record on some unknowns and
        # a placeholder on others (see UNCOUNTED_UNKNOWNS). The placeholder is
        # the same claim this function exists to refuse, one field over: a
        # record that could not be asked must not answer "none".
        payload["seen_before"] = None
    return payload


def metrics_payload(cand, lynch_result: dict, context: dict, streak=None) -> dict:
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
        # What the record already knows about this name -- day N of this
        # setup, when it was last seen and what was done with it then. AFTER
        # **context, so a context key of the same name can never displace the
        # record's answer with a measurement.
        **record_context(streak),
        "2lynch_summary": lynch_result["summary"],
        "2lynch_detail": lynch_result["detail_lines"],
        # Measured criteria that are NOT checklist votes and do not move the
        # pass count -- kept out of 2lynch_detail for exactly that reason,
        # since a model told to anchor on "N of 6" must not be handed a
        # seventh line under that heading. knowledge/strategy.md says how to
        # weigh them; the line carries the threshold the code applied, so the
        # rulebook never holds a second copy of the number.
        # `or {}`, not a .get default: the default applies to a MISSING key and
        # not to an explicit null, which is the distinction that cost this
        # project a morning run once already. The entries are checked one level
        # in for the same reason -- a block of the wrong shape must produce no
        # notes, not an AttributeError inside the scoring call.
        "quality_notes": [
            f"{'PASS' if c['pass'] else 'FAIL'}  {name}: {c['value']}"
            for name, c in _as_dict(lynch_result.get("context_checks")).items()
            if isinstance(c, dict) and "pass" in c and "value" in c
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


#: Appended to the request when a reply could not be parsed, and ONLY then.
#: The retry used to resend the request byte-for-byte at temperature 0, which
#: is the same reasoning score_candidate() already applies to a rejected
#: credential -- "the retry is theatre" -- and did not apply here. Measured: a
#: prose reply produced two identical requests, both unparseable, and the
#: candidate fell back anyway having been paid for twice.
#:
#: temperature 0 is not a guarantee of an identical reply, so the second call
#: was not certain to be wasted; it just had no reason to go differently. This
#: gives it one, at the cost of a few dozen tokens, and leaves the system
#: prompt untouched so the cached prefix still hits.
RETRY_CORRECTION = (
    "Your previous reply could not be parsed. Reply with ONLY the JSON object "
    "described above: no prose before or after it, no markdown fences, no "
    "explanation. The object itself is the entire reply."
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
        # A LIST, not a string, so the knowledge base can carry cache_control.
        # knowledge/strategy.md is byte-identical on every call of a run and is
        # 73% of each request -- measured: ~3,120 tokens of system against ~460
        # of metrics and ~721 for an 869x622 chart. Without this the run paid
        # full price to send the same document up to MAX_TO_SCORE times a
        # night. A cache write costs 1.25x and a read 0.1x, so break-even is
        # the second call (1.28 calls -- the write costs 0.25x more than the
        # uncached call it replaces, each read saves 0.9x): a night that
        # scores two candidates is already ahead, and a full one is 54%
        # cheaper.
        #
        # No `ttl`: the default 5-minute window is the cheap one (an hour costs
        # 2x to write), and every read RESETS it, so a run's sequential calls
        # hold the entry as long as no two are five minutes apart. The system
        # prompt clears Sonnet's 1,024-token minimum cacheable prefix with room
        # to spare; a shorter one would silently cache nothing, which is why
        # cache_usage() exists to report what actually happened rather than
        # leaving this comment as the only evidence.
        "system": [{"type": "text", "text": system,
                    "cache_control": {"type": "ephemeral"}}],
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

    So is a verdict INSIDE the rubric that disagrees with the score's own
    band. knowledge/strategy.md defines the verdict as a function of the
    score -- "A+ (9-10), A (8-8.9) ... skip (<5)" -- so a reply carrying
    score 9.5 and verdict "skip" contradicts the rubric it was asked to
    apply, and this used to keep both: the email then ranked the name first
    and labelled it skip, and the ledger archived the pair. The score is
    the judgement the model was asked for; the label is derived from it
    here exactly as the rubric says, and the disagreement is logged rather
    than lost, because a model that keeps doing it is worth knowing about.
    """
    try:
        score = float(obj["score"])
    except (KeyError, TypeError, ValueError) as e:
        raise ScoreFormatError(f"score {obj.get('score')!r} is not a number") from e
    if not 0.0 <= score <= 10.0:
        raise ScoreFormatError(f"score {score} is outside the 0-10 the rubric defines")

    score = round(score, 1)
    verdict = str(obj.get("verdict", "")).strip()
    expected = _verdict_for(score)
    if verdict != expected:
        if verdict in VERDICTS:
            log.warning("Reply scored %.1f and said %r; the rubric's band for that score "
                        "is %r, which is what is kept", score, verdict, expected)
        verdict = expected
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

    The four anchors the rubric states are the four this map has to agree
    with, and it is a SECOND COPY of them: nothing here reads
    knowledge/strategy.md, because parsing the system prompt at scoring time
    to decide a number would make a prose edit a code path. The agreement is a
    guard instead -- test_the_fallback_anchors_are_the_rubrics_own_bands parses
    the rubric's sentence and asserts this function against it, so an edit to
    either half turns red. Below 3/6 the rubric says nothing (the gate refuses
    those before a call is made, and 3 is MIN_LYNCH_PASSES), so 0-2 are this
    function's own conservative extension and the guard leaves them alone.
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


def cache_usage(resp) -> dict:
    """What the prompt cache did on one reply, as two numbers.

    The saving from cache_control is invisible from inside the run -- the
    reply is identical either way -- so a cache that silently stopped working
    would cost 1.25x forever with nothing to say so, and the comment in
    request_kwargs would be the only evidence it was ever meant to. There are
    real ways for it to stop: a system prompt edited below the 1,024-token
    minimum caches nothing at all, and two calls more than the TTL apart each
    pay a write.

    Absent or malformed usage counts as zeroes rather than raising. This runs
    after a reply has been paid for and parsed; an accounting field is not
    worth losing a score over, and a double that does not model usage must not
    fail the run either.
    """
    usage = getattr(resp, "usage", None)

    def _n(name: str) -> int:
        value = getattr(usage, name, None)
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    return {"cache_write": _n("cache_creation_input_tokens"),
            "cache_read": _n("cache_read_input_tokens"),
            "uncached": _n("input_tokens")}


def score_candidate(cand, lynch_result: dict, context: dict, chart_path: str | None,
                    attempts: int = 2, usage: dict | None = None, streak=None) -> dict:
    """Ask Claude to score one candidate.

    Returns score/reason/verdict/key_risk plus `provenance`, which says who
    produced the number, under which model, and whether the chart was actually
    in front of it. The success and failure paths used to return the same four
    keys, so a score made blind — the render failed and the image block was
    quietly dropped — was indistinguishable from one made with the chart.
    """
    system = KNOWLEDGE_PATH.read_text()
    metrics = metrics_payload(cand, lynch_result, context, streak)

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
            if isinstance(e, ScoreFormatError):
                # The reply arrived and was the wrong SHAPE, which is a fact
                # about this request -- so resending it unchanged, at
                # temperature 0, is the theatre the line above refuses for a
                # rejected key. Ask again, differently. A transport error is
                # the opposite case and keeps the original request: there was
                # nothing wrong with it.
                kwargs = request_kwargs(
                    system, [*content, {"type": "text", "text": RETRY_CORRECTION}])
            continue
        if usage is not None:
            for key, value in cache_usage(resp).items():
                usage[key] = usage.get(key, 0) + value
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
              stats: dict | None = None, streaks: dict | None = None) -> list[dict]:
    """scored_inputs: list of (candidate, lynch_result, context, chart_path).

    `streaks`, if given, is one src.ledger streak block per ticker -- what the
    record already knows about each name, read BEFORE this stage so the model
    sees it. A ticker the dict does not carry is scored with the record's keys
    present and null under src.ledger.NO_STREAK_RECORDED -- which is NOT the
    shape a run whose history could not be read produces, and this docstring
    said it was: that one names its own reason word and this one says nothing
    computed a block at all. Never a day 1 either way.

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
    cache: dict = {}
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
            ai = score_candidate(cand, lynch_result, context, chart_path, usage=cache,
                                 streak=(streaks or {}).get(cand.ticker))
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
    # One line saying whether the prompt cache actually did anything. Written
    # even when it did nothing, because "no line" and "no hits" are the states
    # worth telling apart -- the first means this code did not run.
    if cache:
        log.info("Prompt cache: %d tokens read from cache, %d written, %d sent "
                 "uncached", cache.get("cache_read", 0), cache.get("cache_write", 0),
                 cache.get("uncached", 0))
    if stats is not None:
        stats.update({
            "cache": cache,
            "scored": len(results),
            "claude": len(results) - len(failures),
            "fallback": len(failures),
            "errors": failures,
            "rows": results,
        })
    return results[:top_n]
