"""``report.validate()`` names a malformed record; it never raises through its
caller. The class this repository has produced most often is code that reads a
structure off disk and indexes into a shape it never checked, and four of the
validator's own block checks had it: a fault named by one check was followed
by another check indexing into the same value. The fuzz below substitutes a
string, a list and an integer for every top-level key of a record, every child
of a top-level object and every grandchild under ``run``, and holds the
validator to a ``ValueError`` or a pass, nothing else."""
import copy
import json
from pathlib import Path

import pytest

from src.report import validate

PAGE_FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'page'
SHAPES = ('x', [1], 5)


def _record(name):
    data = json.loads((PAGE_FIXTURES / f'{name}.json').read_text(encoding='utf-8'))
    data.pop('fixture', None)
    return data


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
], ids=lambda v: str(v)[:40])
def test_each_shape_that_once_raised_is_named(path, shape, fault):
    """The six paths a probe found raising on 16 Oct 2026, and the two the
    seed-stale review found the day before: each is a named fault now."""
    data = _record('thin')
    *parents, leaf = path.split('.')
    target = data
    for key in parents:
        target = target[key]
    target[leaf] = shape
    with pytest.raises(ValueError, match=fault):
        validate(data)


def _paths(data):
    """Every top-level key, every child of a top-level object, and every
    grandchild under ``run``, whose blocks are what the validator indexes
    into."""
    for key in sorted(data):
        yield (key,), data[key]
        block = data[key]
        if isinstance(block, dict):
            for child in sorted(block):
                yield (key, child), block[child]
                if key == 'run' and isinstance(block[child], dict):
                    yield from (((key, child, leaf), block[child][leaf]) for leaf in sorted(block[child]))


@pytest.mark.parametrize('name', ['thin', 'full'])
def test_no_shape_substituted_anywhere_makes_validate_raise(name):
    base = _record(name)
    paths = list(_paths(base))
    # every top-level key, and more paths than that: the walk reached into run
    assert len(paths) > len(base) >= 20
    outcomes = {'refused': 0, 'passed': 0}
    for path, original in paths:
        for shape in SHAPES:
            if shape == original:
                continue
            data = copy.deepcopy(base)
            target = data
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = shape
            outcomes[_only_refuses_or_passes(data, '.'.join(path) + f' = {shape!r}')] += 1
    # a substitution the validator does not hold is a pass, never an exception;
    # most are refused, and the count says the fuzz reached the record
    assert outcomes['refused'] > outcomes['passed'] and sum(outcomes.values()) >= 3 * len(paths) - len(SHAPES)
