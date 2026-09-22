"""Validate reader authority and citations, not subjective visual truth.

The concepts are the existing strategy chart-review sections. Their identifiers
and citation requirements are DERIVED SpicyStock choices, not Bonde thresholds.
"""
from __future__ import annotations
from copy import deepcopy
import json

VERSION = 1
MAX_FINDINGS = 8
MAX_CITATIONS = 8
RULES = {"grading.reader_authority_version": VERSION}
CRITERIA = {
    "measured_quality": ("strategy.quality", ("2", "L", "Y", "N", "C", "H", "RE", "VOL")),
    "base_shape": ("strategy.chart.base", ("C",)),
    "leg_shape": ("strategy.chart.leg", ("L",)),
    "trend_maturity": ("strategy.chart.trend", ("Y",)),
    "signal_shape": ("strategy.chart.signal", ("H", "RE", "VOL")),
    "overhead_supply": ("strategy.chart.supply", ("C",)),
    "extension": ("strategy.chart.extension", ("L", "Y")),
    "event_structure": ("strategy.chart.event", ("RE", "VOL", "H")),
}
OBSERVATIONS = {
    "measured_quality": ("recorded_check_defect",),
    "base_shape": ("wide_overlapping_bars", "base_gap", "declining_base"),
    "leg_shape": ("single_gap_then_drift", "choppy_prior_leg"),
    "trend_maturity": ("repeated_visible_pushes",),
    "signal_shape": ("gap_and_fade", "long_upper_tail", "gap_dominated"),
    "overhead_supply": ("prior_trading_above_signal",),
    "extension": ("visibly_spent_move",),
    "event_structure": ("apparent_catalyst_gap", "apparent_halt_or_split"),
}

class ReaderAuthorityError(ValueError):
    """A response has no authority to change the mechanical judgement."""


def evidence(checks):
    return {"version": VERSION, "checks": {
        c.letter: {"status": c.status, "values": deepcopy(c.value)} for c in checks}}


def validate(reply, metrics, *, chart_seen):
    """A lower score needs a permitted finding with truthful non-null citations.

    Measured findings cite an actual FAIL/PARTIAL. Visual findings may disagree
    with a proxy's judgement but must quote its facts faithfully and see a chart.
    Commentary never supplies executable rules, cutoffs, facts or trade orders.
    Transport-only callers lacking quality_grade have no mechanical decision.
    """
    from src import grader
    mechanical = metrics.get("quality_grade")
    if mechanical is None:
        return
    if mechanical not in grader.GRADES:
        raise ReaderAuthorityError("unknown mechanical grade")
    lower = grader.GRADES.index(reply["grade"]) > grader.GRADES.index(mechanical)
    findings = reply.get("findings", [])
    if not isinstance(findings, list) or len(findings) > MAX_FINDINGS:
        raise ReaderAuthorityError("invalid findings list")
    if lower and (not findings or not str(reply.get("reason", "")).strip()):
        raise ReaderAuthorityError("downgrade lacks source-grounded findings")
    block = metrics.get("reader_evidence")
    if findings and (not isinstance(block, dict) or block.get("version") != VERSION):
        raise ReaderAuthorityError("missing reader evidence contract")
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != {"criterion", "source", "evidence", "observation"}:
            raise ReaderAuthorityError("finding has missing or unauthorized fields")
        criterion = finding["criterion"]
        if not isinstance(criterion, str) or criterion not in CRITERIA:
            raise ReaderAuthorityError("unauthorized criterion")
        source, letters = CRITERIA[criterion]
        if finding["source"] != source:
            raise ReaderAuthorityError("criterion/source disagreement")
        observation = finding["observation"]
        if observation not in OBSERVATIONS[criterion]:
            raise ReaderAuthorityError("observation outside source-authorized concepts")
        if criterion != "measured_quality" and not chart_seen:
            raise ReaderAuthorityError("visual finding without a chart")
        citations = finding["evidence"]
        if not isinstance(citations, list) or not citations or len(citations) > MAX_CITATIONS:
            raise ReaderAuthorityError("finding lacks bounded evidence citations")
        defect = False
        for citation in citations:
            if not isinstance(citation, dict) or set(citation) != {"path", "value"}:
                raise ReaderAuthorityError("invalid evidence citation")
            path = citation["path"]
            parts = path.split(".") if isinstance(path, str) else []
            if (len(parts) not in (3, 4) or parts[0] != "checks" or parts[1] not in letters
                    or (len(parts) == 3 and parts[2] != "status")
                    or (len(parts) == 4 and parts[2] != "values")):
                raise ReaderAuthorityError("evidence outside criterion authority")
            try:
                actual = block
                for part in parts:
                    actual = actual[part]
                check = block["checks"][parts[1]]
            except (KeyError, TypeError) as exc:
                raise ReaderAuthorityError("unknown evidence path") from exc
            # Typed JSON equality: True is not 1, null is not failure.
            if json.dumps(actual, sort_keys=True, allow_nan=False) != json.dumps(citation["value"], sort_keys=True, allow_nan=False):
                raise ReaderAuthorityError("citation contradicts deterministic evidence")
            if actual is None or check["status"] == "UNMEASURED":
                raise ReaderAuthorityError("unknown evidence cannot support a defect")
            defect |= parts[-1] == "status" and actual in ("FAIL", "PARTIAL")
        if criterion == "measured_quality" and not defect:
            raise ReaderAuthorityError("measured defect requires a recorded FAIL or PARTIAL")
    return deepcopy(findings)


def instruction():
    mapping = {name: {"source": source, "checks": list(letters), "observations": list(OBSERVATIONS[name])}
               for name, (source, letters) in CRITERIA.items()}
    return ("READER AUTHORITY: any downgrade requires findings with an allowed criterion, "
            "its exact source identifier, evidence citations copied from reader_evidence, "
            "and an allowed observation identifier. Allowed criteria: " + json.dumps(mapping, sort_keys=True) + ". "
            'A citation is {"path":"checks.C.status","value":"PASS"} or a checks.C.values field. '
            "Use the actual JSON value, never reinterpret it. measured_quality needs an "
            "actual FAIL/PARTIAL status. Visual findings need the chart and must name the "
            "bars/region seen in the reason; a passing proxy does not forbid a qualitative flaw. "
            "Unknown is not failure. No discovery requirement, outcome note, new numeric "
            "cutoff, or changed deterministic fact is an authorized finding. "
            "Use [] when confirming without a defect.\n\n")
