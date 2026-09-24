"""Reader coverage is a planning prerequisite, never a quality measurement.

The raw/accepted reader result stays untouched. Selection is recorded by the
pipeline, which knows its budget; missing legacy evidence stays unknown.
"""
from src import grader

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
