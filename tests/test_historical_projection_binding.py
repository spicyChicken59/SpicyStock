"""A representation change cannot inherit an earlier execution approval.

All GitHub responses and proposed revisions are invented fixture values. These
tests exercise the existing guard; they neither create readiness nor open a slot.
"""
from copy import deepcopy

import pytest

from tests.test_historical_execution_guard import APPROVED, CURRENT, TODAY
from tests.test_historical_execution_guard import setup as github_setup
from tools import historical_execution_guard as guard


PROPOSED = "9" * 40


def verify(case):
    policy, env, record, _, _, api = case
    return guard.verify(api, policy, env, record["mode"], 123, TODAY)


def proposed_checkout(case):
    """Keep every other synthetic check valid to isolate each refusal below."""
    _, _, record, responses, _, _ = case
    record["checkout_sha"] = PROPOSED
    responses["/pulls/95"]["head"]["sha"] = PROPOSED
    for prefix in (f"/compare/{guard.ORIGINAL_MERGE}...", "/git/trees/",
                   f"/contents/{guard.WORKFLOW}?ref="):
        responses[prefix + PROPOSED] = deepcopy(responses[prefix + APPROVED])


def test_unchanged_synthetic_review_and_recovery_still_pass(github_setup):
    result = verify(github_setup)
    assert result["checkout_sha"] == APPROVED
    assert result["implementation_pr"] == 95
    assert result["run_number"] == 5 and result["assignment_phase"] == 2
    assert result["evidence"]["local_recovery"]["checkout_sha"] == APPROVED


def test_new_checkout_cannot_borrow_original_pr_review(github_setup):
    proposed_checkout(github_setup)
    # A matching synthetic recovery cannot supply the missing reviewed PR head.
    github_setup[2]["evidence"]["local_recovery"]["checkout_sha"] = PROPOSED
    github_setup[3]["/pulls/95"]["head"]["sha"] = APPROVED
    with pytest.raises(guard.GuardError, match="^unreviewed_checkout$"):
        verify(github_setup)


def test_changed_tools_cannot_borrow_original_review(github_setup):
    tree = github_setup[3][f"/git/trees/{CURRENT}"]["tree"]
    next(item for item in tree if item["path"] == "tools")["sha"] = PROPOSED
    with pytest.raises(guard.GuardError, match="^execution_code_changed$"):
        verify(github_setup)


def test_original_recovery_cannot_attest_changed_checkout(github_setup):
    proposed_checkout(github_setup)
    # The synthetic PR now reviews the proposed head; the old recovery does not.
    with pytest.raises(guard.GuardError, match="^stale_recovery_binding$"):
        verify(github_setup)
