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
