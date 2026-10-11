"""Reader coverage is a planning prerequisite, never a quality measurement.

The raw/accepted reader result stays untouched. Selection is recorded by the
pipeline, which knows its budget; missing legacy evidence stays unknown.
"""
from fractions import Fraction
import math

from src import grader, reader_authority

POLICY = "accepted_required_v1"
ACCEPTED = "accepted"
FALLBACK = "fallback"
NOT_SELECTED = "not_selected_budget"
UNKNOWN = "unknown"
STATES = (ACCEPTED, FALLBACK, NOT_SELECTED, UNKNOWN)


def accepted(row):
    reader = row.get("claude") or {}
    return (reader.get("source") == grader.SOURCE_CLAUDE
            and reader.get("grade") in grader.GRADES
            and reader.get("grade") == row.get("grade")
            and not reader.get("error"))


def state(row, *, selected=None):
    if accepted(row):
        return ACCEPTED
    reader = row.get("claude") or {}
    if reader.get("source") == grader.SOURCE_FALLBACK:
        return FALLBACK
    if selected is False or reader.get("source") == grader.SOURCE_NOT_GRADED:
        return NOT_SELECTED
    if selected is True:
        return FALLBACK
    return UNKNOWN


# ------------------------------------------------- the night's reads ----
# run.reads counts the chart reader's shortfall by cause, so a night can tell
# a reply the reply checks refused (the reader answered; reader authority or
# the discovery contract refused its answer, and the name keeps its checklist
# grade and earns no ticket) from a reply that never arrived or could not be
# read. The fraction of the night's reads that may be refused before the night
# is degraded is a strategy number and lives in pipeline.RULES; these are the
# block's own words.
READS_VERSION = 1
#: why a selected name has no accepted reading, one word each; no word names a
#: gitleaks keyword ("credential", "key") as a JSON key
FAILURES = ("refused", "format", "account", "credit", "transport")
VERDICTS = ("not_asked", "complete", "tolerated", "partial", "unavailable")
#: the errors that are the reply checks refusing a reply that arrived
REFUSED_BY = (grader.DiscoveryConflict, reader_authority.ReaderAuthorityError)


def admitted(verdict, trade, yellow):
    """The grades the night's regime admits to a plan: one rule for the
    planner and for the reads, read off the pipeline's own grades."""
    return () if verdict == "red" else tuple(yellow) if verdict == "yellow" else tuple(trade)


def failure_of(error):
    """The cause a fallback's recorded error names, by its class prefix; an
    error this does not know is ``transport`` -- which degrades: it fails safe."""
    text = error if isinstance(error, str) else ""
    if any(text.startswith(grader.error_label(c) + ":") for c in REFUSED_BY):
        return "refused"
    if text.startswith(grader.error_label(grader.ScoreFormatError) + ":"):
        return "format"
    if grader.is_fatal_auth_failure(text):
        return "account"
    if grader.is_fatal_credit_failure(text):
        return "credit"
    return "transport"


def _limit(requested, fraction):
    return math.floor(int(requested) * Fraction(str(fraction or 0)))


def _verdict(requested, done, causes, limit, refused_admissible):
    if requested == 0:
        return "not_asked"
    if done == 0:
        return "unavailable"
    if done == requested:
        return "complete"
    others = sum(v for k, v in causes.items() if k != "refused")
    if not others and causes["refused"] <= limit and not refused_admissible:
        return "tolerated"
    return "partial"


def reads(rows, *, admitted_grades, refusal_fraction):
    """The night's reads, from the selected bursts after grading. A refusal
    is tolerated -- not a run problem -- only while every other read was
    accepted, refusals are no more than the night's limit, and none of the
    refused names is one the regime would otherwise have planned
    (``admitted_grades``, None for every grade, no veto)."""
    requested = len(rows)
    done = sum(1 for b in rows if (b.get("claude") or {}).get("source") == grader.SOURCE_CLAUDE)
    causes = {f: 0 for f in FAILURES}
    refused = []
    for b in rows:
        c = b.get("claude") or {}
        if c.get("source") == grader.SOURCE_CLAUDE:
            continue
        cause = failure_of(c.get("error"))
        causes[cause] += 1
        if cause == "refused":
            refused.append(b)
    limit = _limit(requested, refusal_fraction)
    refused_admissible = sorted(b["ticker"] for b in refused if not b.get("vetoes")
                                and (admitted_grades is None or b.get("grade") in admitted_grades))
    verdict = _verdict(requested, done, causes, limit, refused_admissible)
    out = {"requested": requested, "done": done,
           "unavailable_reason": None if verdict in ("not_asked", "complete") else
           "refused within the tolerance" if verdict == "tolerated" else "see problems",
           "version": READS_VERSION, "causes": causes, "refusal_limit": limit,
           "refused_names": sorted(b["ticker"] for b in refused),
           "refused_admissible": refused_admissible, "verdict": verdict}
    out["sentence"] = reads_sentence(out)
    return out


def _names(n, one, many):
    return f"{n} {one if n == 1 else many}"


def reads_sentence(r):
    """The night's reads in words, composed from counts and tickers only: no
    provider text reaches the page or the mail."""
    if r.get("verdict") in (None, "not_asked", "complete"):
        return None
    c, limit = r["causes"], r["refusal_limit"]
    parts = [f"Chart reader: {r['done']} of {_names(r['requested'], 'judgement', 'judgements')} accepted."]
    if c["refused"]:
        names = ", ".join(r.get("refused_names") or [])
        s = (f"{_names(c['refused'], 'reply', 'replies')} ({names}) refused by reader authority or the discovery "
             "contract")
        if r["verdict"] == "tolerated":
            s += (f", within this run's tolerance of {limit}; "
                  f"{'that name stays' if c['refused'] == 1 else 'those names stay'} research only, without a ticket")
        else:
            s += (f"; the tolerance of {limit} applies only while every other read is accepted and no refused "
                  "name would otherwise have been planned")
        if r["refused_admissible"]:
            s += f"; {', '.join(r['refused_admissible'])} would otherwise have been planned"
        parts.append(s + ".")
    if c["credit"]:
        parts.append("The API answered that the account's credit balance is too low; the run stopped asking after "
                     f"that answer and {_names(c['credit'], 'name', 'names')} went unread. Top up the Anthropic "
                     "account before the next run.")
    if c["account"]:
        parts.append(f"The API refused the account; the run stopped asking after that answer and "
                     f"{_names(c['account'], 'name', 'names')} went unread.")
    if c["transport"]:
        parts.append(f"{_names(c['transport'], 'name', 'names')} got no usable answer from the API in "
                     f"{grader.ATTEMPTS} attempts each.")
    if c["format"]:
        parts.append(f"{_names(c['format'], 'reply', 'replies')} could not be read as a score in "
                     f"{grader.ATTEMPTS} attempts.")
    return " ".join(parts)


# ------------------------------------------------ what the reads cost ----
# run.reader_usage says what the night's reads cost in the API's own units:
# the calls sent, the replies received and the four token classes a reply
# reports. The run archives counts, never a price: a price is the provider's
# list, which changes under the record, and a reading can apply one later.
# The block records a cost and decides nothing, so its version sits in
# pipeline.RULES beside run.reads' own rule and outside the provenance
# verifier's replay set: a record made before it still replays in full.
USAGE_VERSION = 1
#: the token classes a reply reports, in the order the block carries them
TOKEN_CLASSES = ("cache_write", "cache_read", "uncached", "output")
INPUT_CLASSES = ("cache_write", "cache_read", "uncached")


def usage_block(rows, usage, *, model):
    """run.reader_usage from the grader's own accounting over the selected
    rows: ``usage`` is the dict ``grader.grade_all`` accumulated (calls,
    responses and the token classes), ``model`` the model the run asked."""
    usage = usage or {}
    tokens = {k: int(usage.get(k, 0)) for k in TOKEN_CLASSES}
    out = {"version": USAGE_VERSION, "model": model, "candidates": len(rows),
           "calls": int(usage.get("calls", 0)), "responses": int(usage.get("responses", 0)),
           "tokens": tokens, "input_tokens": sum(tokens[k] for k in INPUT_CLASSES)}
    out["sentence"] = usage_sentence(out)
    return out


def usage_sentence(u):
    """The night's reader cost in words, composed from counts and the model
    name alone; no price, because the record archives none."""
    if u["candidates"] == 0 and u["calls"] == 0:
        return "Chart reader cost: no calls."
    t = u["tokens"]
    return (f"Chart reader cost: {_names(u['calls'], 'call', 'calls')} for "
            f"{_names(u['candidates'], 'name', 'names')}, {_names(u['responses'], 'reply', 'replies')}; "
            f"{u['input_tokens']:,} input tokens ({t['uncached']:,} uncached, {t['cache_write']:,} written to the "
            f"cache, {t['cache_read']:,} read from it) and {t['output']:,} output tokens, under {u['model']}. "
            "Token counts as the API reported them; the record carries no price.")


def _bill(usage):
    return isinstance(usage, dict) and set(usage) == set(TOKEN_CLASSES) \
        and not any(type(v) is not int or v < 0 for v in usage.values())


def row_usage(attempts, billing):
    """One selected name's cost, beside its reader result and outside it: one
    call per attempt, one reply per attempt that carries a response, the bill
    of each (None where no reply arrived) and their sum."""
    bills = [b if _bill(b) else None for b in (billing or [])]
    tokens = {k: sum(b[k] for b in bills if b) for k in TOKEN_CLASSES}
    return {"calls": len(attempts or []), "responses": sum(1 for b in bills if b), "tokens": tokens, "attempts": bills}


def _row_faults(row):
    """Why a selected name's cost block is not its attempts' own, or None."""
    u, attempts = row.get("reader_usage"), (row.get("claude") or {}).get("attempts")
    if not isinstance(u, dict) or not isinstance(attempts, list) or set(u) != {"calls", "responses", "tokens", "attempts"}:
        return "a selected name has no readable cost block"
    bills = u["attempts"]
    if not isinstance(bills, list) or len(bills) != len(attempts) or u["calls"] != len(attempts):
        return "a name's bills are not one per attempt"
    for a, bill in zip(attempts, bills):
        if (bill is None) != ("response" not in (a if isinstance(a, dict) else {})):
            return "a name bills a reply that did not arrive, or none for one that did"
        if bill is not None and not _bill(bill):
            return "a name's bill is malformed"
    if u["responses"] != sum(1 for b in bills if b) or not isinstance(u["tokens"], dict) \
            or u["tokens"] != {k: sum(b[k] for b in bills if b) for k in TOKEN_CLASSES}:
        return "a name's cost does not sum its bills"
    return None


def _attempt_usage(bursts):
    """The night's cost re-derived from the selected names' own cost blocks,
    each held to its attempts first; the first fault names why it cannot be."""
    calls = responses = 0
    tokens = {k: 0 for k in TOKEN_CLASSES}
    for b in bursts:
        why = _row_faults(b)
        if why:
            return why
        u = b["reader_usage"]
        calls += u["calls"]
        responses += u["responses"]
        for k in TOKEN_CLASSES:
            tokens[k] += u["tokens"][k]
    return {"calls": calls, "responses": responses, "tokens": tokens}


def usage_faults(data):
    """run.reader_usage held to the record it sits in, one level in: present
    under rules that write it, its shape whole, its counts reconciled with
    run.reads and with each other, the bursts' own on an open night, and its
    sentence its own."""
    rules = ((data.get("rules") or {}).get("pipeline") or {}) if isinstance(data.get("rules"), dict) else {}
    if not isinstance(rules, dict) or "reader_usage_version" not in rules:
        return []
    run = data.get("run") if isinstance(data.get("run"), dict) else {}
    u = run.get("reader_usage")
    try:
        if not isinstance(u, dict) or u.get("version") != USAGE_VERSION:
            return ["run.reader_usage is missing or of an unknown version"]
        if set(u) != {"version", "model", "candidates", "calls", "responses", "tokens", "input_tokens", "sentence"}:
            return ["run.reader_usage carries fields this rule does not write"]
        if not isinstance(u["model"], str) or not u["model"].strip() or u["model"] != run.get("model"):
            return ["run.reader_usage model is not the run's"]
        counts = (u["candidates"], u["calls"], u["responses"], u["input_tokens"])
        t = u["tokens"]
        if any(type(v) is not int or v < 0 for v in counts) or not isinstance(t, dict) or set(t) != set(TOKEN_CLASSES) \
                or any(type(v) is not int or v < 0 for v in t.values()):
            return ["run.reader_usage counts are malformed"]
        if u["input_tokens"] != sum(t[k] for k in INPUT_CLASSES):
            return ["run.reader_usage input tokens are not the sum of their classes"]
        if u["responses"] > u["calls"] or u["calls"] > u["candidates"] * grader.ATTEMPTS:
            return ["run.reader_usage calls and replies do not reconcile"]
        if u["responses"] == 0 and any(t.values()):
            return ["run.reader_usage bills tokens to no reply"]
        reads = run.get("reads")
        if isinstance(reads, dict):
            if u["candidates"] != reads.get("requested"):
                return ["run.reader_usage names are not the night's reads"]
            if type(reads.get("done")) is int and u["responses"] < reads["done"]:
                return ["run.reader_usage has fewer replies than accepted readings"]
        if run.get("session_state") == "open" and isinstance(data.get("bursts"), list):
            selected = [b for b in data["bursts"] if isinstance(b, dict) and isinstance(b.get("claude"), dict)]
            again = _attempt_usage(selected)
            if isinstance(again, str):
                return ["run.reader_usage cannot be re-derived: " + again]
            if any(again[k] != u[k] for k in ("calls", "responses", "tokens")):
                return ["run.reader_usage is not the bursts' own"]
        if u["sentence"] != usage_sentence(u):
            return ["run.reader_usage sentence is not its own"]
    except (KeyError, TypeError, AttributeError):
        return ["run.reader_usage is malformed"]
    return []


def reads_faults(data):
    """run.reads held to the record it sits in, one level in: present under
    rules that write it, its counts reconciled, its verdict re-derived, its
    causes the bursts' own on an open night, and a shortfall it did not
    tolerate named by its problem word."""
    rules = ((data.get("rules") or {}).get("pipeline") or {}) if isinstance(data.get("rules"), dict) else {}
    if not isinstance(rules, dict) or "reader_refusal_fraction" not in rules:
        return []
    run = data.get("run") if isinstance(data.get("run"), dict) else {}
    r = run.get("reads")
    try:
        if not isinstance(r, dict) or r.get("version") != READS_VERSION or r["verdict"] not in VERDICTS:
            return ["run.reads is missing or of an unknown version"]
        c = r["causes"]
        if set(c) != set(FAILURES) or any(type(v) is not int or v < 0 for v in c.values()):
            return ["run.reads causes are malformed"]
        if r["requested"] != r["done"] + sum(c.values()):
            return ["run.reads counts do not reconcile"]
        if len(r["refused_names"]) != c["refused"] or not set(r["refused_admissible"]) <= set(r["refused_names"]):
            return ["run.reads refused names are not its refusals"]
        if r["refusal_limit"] != _limit(r["requested"], rules["reader_refusal_fraction"]):
            return ["run.reads refusal limit is not the archived reader_refusal_fraction"]
        if r["verdict"] != _verdict(r["requested"], r["done"], c, r["refusal_limit"], r["refused_admissible"]):
            return ["run.reads verdict does not re-derive from its counts"]
        if run.get("session_state") == "open" and isinstance(data.get("bursts"), list):
            selected = [b for b in data["bursts"] if isinstance(b, dict) and isinstance(b.get("claude"), dict)]
            reg = (((data.get("breadth") or {}).get("regime") or {}).get("verdict"))
            again = reads(selected, admitted_grades=admitted(reg, rules["trade_grades"], rules["yellow_grades"]),
                          refusal_fraction=rules["reader_refusal_fraction"])
            if any(again[k] != r[k] for k in ("requested", "done", "causes", "refused_names", "refused_admissible", "verdict")):
                return ["run.reads is not the bursts' own"]
        if r.get("sentence") != reads_sentence(r):
            return ["run.reads sentence is not its own"]
        kinds = {p.get("kind") for p in run.get("problems") or [] if isinstance(p, dict)}
        if r["verdict"] == "partial" and "claude_partial" not in kinds:
            return ["a partial read is not named claude_partial"]
        if r["verdict"] == "unavailable" and "claude_unavailable" not in kinds:
            return ["an unavailable reader is not named claude_unavailable"]
        return []
    except (KeyError, TypeError, ValueError, AttributeError):
        return ["run.reads is malformed"]
