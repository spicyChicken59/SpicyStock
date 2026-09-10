"""Bonde's own 2LYNCH over a canonical scan row, one letter at a time.

Each case moves ONE measurement across ONE boundary, so a verdict that changed
can only have changed for the rule the test names. The three-valued cases are
here in force because the two combining checks are the only place this function
can be quietly wrong: `N` is an OR and `C` is an AND, an unknown arm means
opposite things in the two, and the first version of the function had both
backwards.
"""
import pytest

from src import stockbee


def row(**over):
    """A row that passes every measurable check, so one edit fails one letter."""
    base = {"ticker": "AAA", "close": 50.0, "high": 51.0, "low": 45.0,
            "gain_pct": 8.0,
            "prior_up_days": 0,          # 2: not up two days in a row
            "prior_day_move_pct": -0.5,  # N: a negative day before the breakout
            "prior_bursts_20": 0,        # Y: first breakout of the leg
            "base_down4_count": 0,       # C: no 4% breakdown in the base
            "compression_ratio": 0.6,    # C: compact against its own 60 sessions
            "close_position": 0.9,       # H: closed in the top 30%
            # Carried because a real row carries it, and because `L` is the
            # one letter this function refuses to answer: a mutant that
            # guesses L from trend_intensity is invisible on a row that has
            # no trend_intensity, which is how it survived the first sweep.
            "trend_intensity": 1.08,
            "series": [{"high": 51, "low": 49, "close": 50} for _ in range(10)]}
    base.update(over)
    return base


def checks(**over):
    return stockbee.qualify(row(**over))["checks"]


def test_a_row_that_passes_everything_measurable_passes_five_and_not_six():
    """L is a fit over the prior move; a row carries no fit. Five of six is the
    honest answer and the function must not round it up to six."""
    result = stockbee.qualify(row())
    assert result["passes"] == 5 and result["measured"] == 5
    assert result["checks"]["L"] is None
    assert result["unmeasured"] == ["L"]


@pytest.mark.parametrize("letter,over", [
    ("2", {"prior_up_days": 2, "prior_day_move_pct": 1.5}),
    ("Y", {"prior_bursts_20": 2}),
    # A wide, POSITIVE prior day. The wide bar has to be second from the end:
    # the last bar of a series is the breakout itself, which the base excludes,
    # so a wide bar in that slot tests nothing. The first version of this case
    # put it there and `N` passed on a base of narrow bars.
    ("N", {"prior_day_move_pct": 0.5,
           "series": [{"high": 51, "low": 49, "close": 50} for _ in range(9)]
                     + [{"high": 60, "low": 40, "close": 50}]
                     + [{"high": 62, "low": 41, "close": 60}]}),
    ("C", {"base_down4_count": 2}),
    ("H", {"close_position": 0.5}),
])
def test_each_letter_fails_alone_when_its_own_measurement_crosses(letter, over):
    """The inverse half of this project's mutation rule: breaking one rule must
    fail THAT letter and leave the other four standing, rather than passing
    while some other letter does the rejecting."""
    got = checks(**over)
    assert got[letter] is False, f"{letter} should have failed"
    others = {k: v for k, v in got.items() if k not in (letter, "L")}
    assert all(v is True for v in others.values()), f"{letter} took others with it: {others}"


@pytest.mark.parametrize("ups,move,expected", [
    (0, -0.5, True),    # not up at all
    (1, 0.5, True),     # up one day is not "two days in a row"
    (2, 0.5, True),     # up two, but the last was under 1% -- Bonde's own exception
    (2, 0.99, True),    # just inside the exception
    (2, 1.0, False),    # the exception is "less than 1%", so 1.0 is not small
    (2, 1.5, False),
    (5, 0.1, True),     # the exception is about the day before, not the run's length
    (None, -0.5, None),  # a streak that ran off the end of the history is unknown
])
def test_the_two_rule_applies_bondes_own_small_up_day_exception(ups, move, expected):
    """"Not up two days in a row on breakout day. A small up day of less than
    1% before b/o is fine." The exception is what makes this rule his and not
    a plain streak count, and it is the half an implementation drops."""
    assert checks(prior_up_days=ups, prior_day_move_pct=move)["2"] is expected


@pytest.mark.parametrize("move,widths,expected", [
    (-0.5, 2.0, True),    # negative day: passes whatever the width was
    (0.0, 2.0, True),     # "negative" is inclusive of unchanged
    (0.5, 0.5, True),     # positive but narrow: the OR's other arm carries it
    (0.5, 2.0, False),    # positive AND wide: the only way N fails
    (None, 0.5, True),    # narrow alone is enough
    (None, 2.0, None),    # wide, and whether it was negative is unknown -> unknown
])
def test_the_narrow_or_negative_rule_is_an_or_and_never_fails_on_one_unknown_arm(move, widths, expected):
    """An OR with one failed arm and one unknown arm is UNKNOWN, not failed:
    the unknown arm could still carry it. Reporting False there would assert a
    rejection the row cannot support."""
    series = [{"high": 51, "low": 49, "close": 50} for _ in range(9)]
    prior = 2.0 * widths  # the base bar is 2.0 wide; scale the prior day against it
    series.append({"high": 50 + prior / 2, "low": 50 - prior / 2, "close": 50})
    series.append({"high": 60, "low": 40, "close": 55})  # the breakout bar, excluded from the base
    assert checks(prior_day_move_pct=move, series=series)["N"] is expected


@pytest.mark.parametrize("breakdowns,compression,expected", [
    (0, 0.6, True),
    (1, 0.6, True),      # Bonde allows exactly one 4% breakdown
    (2, 0.6, False),
    (0, 1.5, False),     # a base wider than its own norm is not compact
    (2, None, False),    # an AND with one failed arm is failed, whatever the other says
    (None, 1.5, False),
    (None, 0.6, None),   # unknown beside a pass is unknown
    (0, None, None),
])
def test_the_consolidation_rule_is_an_and_and_a_failed_arm_decides_it(breakdowns, compression, expected):
    """The mirror of the N case, and deliberately NOT written the same way. An
    AND with one failed arm is failed even when the other arm is unknown; only
    unknown-beside-a-pass is unknown."""
    assert checks(base_down4_count=breakdowns, compression_ratio=compression)["C"] is expected


def test_an_unknown_is_never_counted_as_a_pass_or_as_a_fail():
    """`passes` counts True and `measured` counts not-None, so a row that can
    answer nothing reports 0 of 0 rather than 0 of 6 -- which would read as six
    failures."""
    empty = stockbee.qualify({"ticker": "AAA"})
    assert empty["passes"] == 0 and empty["measured"] == 0
    assert set(empty["unmeasured"]) == {"2", "L", "Y", "N", "C", "H"}
    assert all(v is None for v in empty["checks"].values())


def test_the_thresholds_are_read_from_the_named_table_and_not_retyped():
    """Every bar this function applies is in QUALIFYING_THRESHOLDS, so moving
    one there moves the rule. A constant inlined at its own value would pass a
    membership check, so this moves each one and reads the verdict back."""
    for key, worse in (("close_near_high", 0.95), ("max_prior_bursts", 0),
                       ("max_base_breakdowns", 0), ("compact_base", 0.1),
                       ("small_up_day_pct", 0.1)):
        original = stockbee.QUALIFYING_THRESHOLDS[key]
        stockbee.QUALIFYING_THRESHOLDS[key] = worse
        try:
            tightened = stockbee.qualify(row(prior_up_days=2, prior_day_move_pct=0.5,
                                             prior_bursts_20=1, base_down4_count=1,
                                             compression_ratio=0.6, close_position=0.9))
        finally:
            stockbee.QUALIFYING_THRESHOLDS[key] = original
        assert tightened["passes"] < 5, f"{key} is not read from the table"


def test_the_letters_are_bondes_and_the_module_says_where_they_differ_from_lynch():
    """The whole point of this function is that `src/lynch.py` uses the same
    six letters for a different mapping. If the rules table ever loses that,
    a reader comparing the two has nothing to compare."""
    rules = stockbee.QUALIFYING_RULES
    assert set("2LYNCH") <= set(rules)
    assert "not up two days in a row" in rules["2"]
    assert "first or second" in rules["Y"]
    assert "negative day" in rules["N"] and "before the breakout" in rules["N"]
    assert "one 4% breakdown" in rules["C"]
    assert "continuation" in rules["scope"]


def test_it_runs_over_this_repos_own_committed_scan_rows():
    """The rows this function exists for are the ones already in the record.
    It must answer on every one of them without raising, and it must actually
    separate them -- a function that returns the same verdict for every real
    row would pass every test above and be useless."""
    import json
    from pathlib import Path
    book = json.loads((Path(__file__).resolve().parent.parent / "docs" / "ledger.json").read_text())
    seen = []
    for run in book.get("runs") or []:
        for scan_row in (((run.get("stockbee") or {}).get("scan") or {}).get("rows") or []):
            answer = stockbee.qualify(scan_row)
            # Every real row carries `trend_intensity`, and L must still be
            # None on all of them: this is where a guess would show up, since
            # a hand-built fixture can simply omit the field a guess reads.
            assert answer["checks"]["L"] is None, f"{scan_row.get('ticker')} answered L"
            assert 0 <= answer["passes"] <= answer["measured"] <= 6
            seen.append(answer["passes"])
    if seen:
        assert len(set(seen)) > 1, "every real row scored the same; the checklist is not discriminating"
