"""``report.validate()`` names a malformed record; it never raises through its
caller. The class this repository has produced most often is code that reads a
structure off disk and indexes into a shape it never checked, and the
validator's own block checks had it in nine places: a fault named by one check
was followed by another check indexing into the same value, a set asked to
hold a list, an ``except`` that did not name ``AttributeError``. The fuzz below
substitutes a string, a list and an integer for every top-level key of a
record, every child of a top-level object, every grandchild and
great-grandchild under ``run``, and the first item of every top-level list
with each of its children, and holds the validator to a ``ValueError`` or a
pass, nothing else."""
import copy
import json
import re
from pathlib import Path

import pytest

from src.report import validate

PAGE_FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'page'
SHAPES = ('x', [1], 5)


def _record(name):
    data = json.loads((PAGE_FIXTURES / f'{name}.json').read_text(encoding='utf-8'))
    data.pop('fixture', None)
    return data


def _set(data, path, value):
    """``path`` is dotted; a segment of digits indexes a list."""
    target = data
    *parents, leaf = [int(k) if k.isdigit() else k for k in path.split('.')]
    for key in parents:
        target = target[key]
    target[leaf] = value


def _only_refuses_or_passes(data, where):
    try:
        validate(data)
    except ValueError:
        return 'refused'
    except Exception as exc:  # noqa: BLE001 -- the point of the test
        pytest.fail(f'validate() raised {type(exc).__name__} rather than naming {where}: {exc}')
    return 'passed'


@pytest.mark.parametrize('name', ['thin', 'full'])
def test_the_fixtures_validate_as_committed(name):
    validate(_record(name))


@pytest.mark.parametrize('path,shape,fault', [
    ('run.problems', 5, 'run.problems is not a list'),
    ('run.problems', True, 'run.problems is not a list'),
    ('run.timing', 'x', 'run timing is not an object beside its calendar'),
    ('observations.symbols', 'x', 'observations is not an object with a symbols object'),
    ('run.coverage.acceptance', 'x', 'coverage acceptance is not an object'),
    ('run.coverage.benchmark_added', 'x', 'universe size or benchmark count is not an integer'),
    ('run.universe.size', 'x', 'universe size or benchmark count is not an integer'),
    ('run.universe', 'x', 'run.universe or run.input_basis is not an object'),
    ('run.universe.selection', [1], 'universe selection does not reconcile'),
    ('run.coverage.sessions.latest_bar_dates', 'x', 'incomplete input population ledger'),
    ('run.universe.selection.exclusions', 'x', 'universe selection does not reconcile'),
    ('bursts.0.ticker', [1], 'bursts[0].ticker is not a string'),
], ids=lambda v: str(v)[:40])
def test_each_shape_that_once_raised_is_named(path, shape, fault):
    """The six paths a probe found raising on 16 Oct 2026, the two the
    seed-stale review found the day before, and the three a review one level
    deeper found the same evening: each is a named fault now."""
    data = _record('thin')
    _set(data, path, shape)
    with pytest.raises(ValueError, match=re.escape(fault)):
        validate(data)


@pytest.mark.parametrize('path,shape,fault', [
    ('trades.0', [1], 'trades names a value that is not a ticker'),
    ('beyond_cap.0', {}, 'beyond_cap names a value that is not a ticker'),
], ids=lambda v: str(v)[:40])
def test_a_list_of_tickers_holding_a_value_a_set_cannot_is_named(path, shape, fault):
    """Only the ``full`` night carries trades and a beyond-cap list; the set
    the validator checks them against cannot be asked for a list or an object."""
    data = _record('full')
    _set(data, path, shape)
    with pytest.raises(ValueError, match=re.escape(fault)):
        validate(data)


def test_a_wrong_calendar_beside_a_timing_that_is_not_an_object_names_both():
    """The shape fault does not mask the calendar's own, which the sessions
    module checks before it reads the timing."""
    data = _record('thin')
    data['run']['calendar']['measured']['session'] = '2020-01-02'
    data['run']['timing'] = 'x'
    with pytest.raises(ValueError) as refused:
        validate(data)
    faults = str(refused.value)
    assert 'run timing is not an object beside its calendar' in faults
    assert 'run.calendar differs from the versioned XNYS schedule' in faults


def _paths(data):
    """Every top-level key; every child of a top-level object; every grandchild
    and great-grandchild under ``run``, whose blocks are what the validator
    indexes into; and the first item of every top-level list with each of its
    children, which the validator walks by index."""
    for key in sorted(data):
        yield (key,)
        block = data[key]
        if isinstance(block, dict):
            for child in sorted(block):
                yield (key, child)
                grand = block[child]
                if key == 'run' and isinstance(grand, dict):
                    for leaf in sorted(grand):
                        yield (key, child, leaf)
                        if isinstance(grand[leaf], dict):
                            yield from (((key, child, leaf, deep),) for deep in sorted(grand[leaf]))
        elif isinstance(block, list) and block:
            yield (key, 0)
            if isinstance(block[0], dict):
                yield from (((key, 0, child),) for child in sorted(block[0]))


def _lookup(data, path):
    target = data
    for key in path:
        target = target[key]
    return target


@pytest.mark.parametrize('name', ['thin', 'full'])
def test_no_shape_substituted_anywhere_makes_validate_raise(name):
    data = _record(name)
    untouched = copy.deepcopy(data)
    paths = [p[0] if isinstance(p[0], tuple) else p for p in _paths(data)]
    # the walk reached past the top level: into run's great-grandchildren and into a list
    assert len(paths) > len(data) >= 20
    assert any(len(path) == 4 for path in paths) and any(path[1] == 0 for path in paths if len(path) > 1)
    outcomes = {'refused': 0, 'passed': 0}
    already = 0  # a path whose value IS one of the shapes is not substituted with it
    for path in paths:
        original = _lookup(data, path)
        for shape in SHAPES:
            if shape == original:
                already += 1
                continue
            _lookup(data, path[:-1])[path[-1]] = shape
            try:
                outcomes[_only_refuses_or_passes(data, '.'.join(map(str, path)) + f' = {shape!r}')] += 1
            finally:
                _lookup(data, path[:-1])[path[-1]] = original
    # a substitution the validator does not hold is a pass, never an exception;
    # most are refused, the count says the fuzz reached the record, and the
    # validator wrote nothing into it
    assert outcomes['refused'] > outcomes['passed'] and sum(outcomes.values()) == 3 * len(paths) - already
    assert data == untouched
