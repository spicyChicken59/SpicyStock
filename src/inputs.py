"""Bounded public input ledger, composed from the existing download/session stats.

Counts are disjoint except explicitly labeled diagnostics. The benchmark is
transported but excluded from the stock coverage denominator and strategy scan.
An incomplete input is never counted as a measured non-match.
"""
from collections import Counter
from datetime import date
from fractions import Fraction
import json
import math

from src import market_data, sessions, universe

VERSION = 1

# The stale tolerance (run.input_tolerance). A degraded acceptance whose ONLY
# gap is a small tail of stocks a few sessions behind is counted and named, the
# next session's run reads every session each of them missed, and the tail
# does not make the run degraded; anything else keeps today's rule. The
# benchmark is outside the stock denominator here as it is in acceptance (it
# feeds only the scorecard's comparison line), so a stale benchmark neither
# counts against the limit nor blocks it. The fraction and the session bound
# are strategy numbers and live in pipeline.RULES; these are the block's own
# words. Version 2 carries where each stale frame ends (``endings``) and the
# bound it was judged by (``sessions_max``); version 1 held every frame to the
# previous session and the follow-up read that session alone. Version 3 also
# names the stocks whose provider history BEGINS on the evaluated session
# (``first_sessions``): a gapped frame with no bar before the session at all,
# which is an exchange listing's first day (LCU, 19 October 2026: Lion Copper's
# first Nasdaq session; NORD, 30 October) or a symbol new to the provider, not
# an input that went missing. Each night those two were degraded by that one
# frame alone. It is still set aside, never measured, and counted against the
# same limit as the stale stocks; a gapped frame with a real hole -- an earlier
# bar, but not the session before -- is the gap it always was.
TOLERANCE_VERSION = 3
#: the version a record wrote under rules that archive no tolerance version
UNVERSIONED_TOLERANCE = 2
#: the first version that names the stocks whose history begins on the session
FIRST_SESSIONS_VERSION = 3
#: the block versions a record can carry, read under the rules it archived
TOLERANCE_VERSIONS = (UNVERSIONED_TOLERANCE, FIRST_SESSIONS_VERSION)
COMPLETE, TOLERATED, NOT_TOLERATED = "complete", "tolerated", "not_tolerated"
TOLERANCE_VERDICTS = (COMPLETE, TOLERATED, NOT_TOLERATED)
TOLERANCE_REASONS = ("other_exceptions", "behind_more", "over_limit", "open_plan")
#: the ledger's gaps other than a stale frame: any one of them is not the stale tail
OTHER_EXCEPTIONS = ("no_bars", "dropped", "unfetched_budget", "unfetched_failure", "refused",
                    "gapped", "unreadable", "errors")
#: each such gap in words, for the sentence that says why the tolerance did not hold
OTHER_WORDS = {"no_bars": "no bars", "dropped": "failed after retry", "unfetched_budget": "never attempted",
               "unfetched_failure": "not requested after a failure", "refused": "refused by the provider",
               "gapped": "missing the previous session", "unreadable": "unreadable bars",
               "errors": "scan or checklist errors", "capacity_excluded": "excluded by capacity"}
#: the ledger's gaps a benchmark frame that is not ready can sit in, beside a stale frame
BENCHMARK_GAPS = ("no_bars", "dropped", "unfetched_budget", "unfetched_failure", "refused", "gapped", "unreadable")

def build(uni, symbols, frames, stats, ready, expected, session, *, closed,
          minimum, benchmark):
    stocks = set(uni.symbols) - {benchmark}
    stock_ready = len(stocks & ready.keys())
    fraction = stock_ready / len(stocks) if stocks else 0.0
    capacity = uni.counts.get(universe.CAPACITY_REASON, 0)
    status = 'fail' if stats.refused or not stocks or fraction < minimum else (
        'degraded' if stock_ready < len(stocks) or capacity else 'ok')
    actual = Counter(str(market_data.last_bar_date(df)) for df in frames.values())
    cov = {
        'version': VERSION, 'intended': len(symbols), 'requested': stats.requested,
        'with_bars': stats.with_bars, 'no_bars': len(stats.no_bars), 'dropped': stats.dropped,
        'unfetched_budget': len(stats.unfetched), 'unfetched_failure': len(stats.unrequested),
        'refused': len(stats.refused), 'stale': len(stats.stale),
        'gapped': len(stats.gapped), 'unreadable': len(stats.unreadable),
        'on_session': stats.fresh, 'session_ready': len(ready),
        'benchmark_ready': int(benchmark in ready), 'scan_ready': 0 if closed else stock_ready,
        'price_excluded': 0, 'not_scanned_closed': stock_ready if closed else 0,
        'measured': 0, 'scan_errors': 0, 'scan_unattempted': 0 if closed else stock_ready, 'quality_success': 0, 'quality_errors': 0,
        'matched': {'burst': 0, 'dollar': 0, 'both': 0, 'neither': 0}, 'errors': 0,
        'duplicate_symbols': len(stats.duplicates), 'duplicate_bars': stats.duplicate_bars,
        'returned_bars': sum(len(df) for df in frames.values()),
        'batch_attempts': stats.batch_attempts,
        'intended_identity': universe.identity(symbols), 'benchmark_added': int(benchmark not in uni.symbols),
        'acceptance': {'status': status, 'denominator': 'intended stocks, excluding benchmark',
                       'intended_stocks': len(stocks), 'ready_stocks': stock_ready,
                       'fraction': fraction, 'minimum_fraction': minimum,
                       'complete_evaluation': False,
                       'complete_intended': stock_ready == len(stocks),
                       'capacity_excluded': capacity},
        'sessions': {'expected': str(expected), 'evaluated': str(session),
                     'expected_present': sum(market_data.last_bar_date(df) == expected for df in frames.values()),
                     'latest_bar_dates': dict(sorted(actual.items())),
                     'previous': str(stats.previous_session) if stats.previous_session else None,
                     'previous_observed': stats.previous_session_observed,
                     'previous_printed': stats.previous_session_printed,
                     'closure_voters': stats.closure_voters, 'closure_agreed': stats.closure_agreed},
        'reasons': {k: universe.population(v) for k, v in {
            'no_bars': stats.no_bars, 'dropped': stats.dropped_symbols,
            'unfetched_budget': stats.unfetched, 'stale': stats.stale,
            'gapped': stats.gapped, 'unreadable': stats.unreadable,
            'duplicate_repaired': stats.duplicates, 'refused': stats.refused,
            'unfetched_failure': stats.unrequested, 'price_excluded': []}.items()},
    }
    return cov


def faults(cov):
    """Conservation at publication; legacy records have no versioned ledger."""
    if not isinstance(cov, dict) or 'version' not in cov:
        return []
    try:
        quantities = ('intended', 'requested', 'with_bars', 'no_bars', 'dropped', 'unfetched_budget',
                      'refused', 'unfetched_failure', 'stale', 'gapped', 'unreadable', 'on_session', 'session_ready', 'benchmark_ready',
                      'scan_ready', 'price_excluded', 'not_scanned_closed', 'measured', 'scan_errors', 'scan_unattempted',
                      'quality_success', 'quality_errors', 'errors', 'benchmark_added')
        if cov['version'] != VERSION or any(type(cov[k]) is not int or cov[k] < 0 for k in quantities):
            return ['invalid input ledger counts/version']
        m = cov['matched']
        if set(m) != {'burst', 'dollar', 'both', 'neither'} or any(type(v) is not int or v < 0 for v in m.values()):
            return ['invalid input match populations']
        equations = [
            cov['intended'] == cov['requested'] + cov['unfetched_budget'] + cov['unfetched_failure'],
            cov['requested'] == cov['with_bars'] + cov['no_bars'] + cov['dropped'] + cov['refused'],
            cov['with_bars'] == cov['stale'] + cov['on_session'],
            cov['on_session'] == cov['gapped'] + cov['unreadable'] + cov['session_ready'],
            cov['session_ready'] == cov['benchmark_ready'] + cov['price_excluded'] + cov['scan_ready'] + cov['not_scanned_closed'],
            cov['scan_ready'] == cov['measured'] + cov['scan_errors'] + cov['scan_unattempted'],
            cov['measured'] == sum(m.values()),
            m['burst'] + m['dollar'] + m['both'] == cov['quality_success'] + cov['quality_errors'],
            cov['errors'] == cov['scan_errors'] + cov['quality_errors'],
            cov['acceptance']['ready_stocks'] == cov['session_ready'] - cov['benchmark_ready'],
        ]
        a = cov['acceptance']
        expected_fraction = a['ready_stocks'] / a['intended_stocks'] if a['intended_stocks'] else 0.0
        expected_status = ('fail' if cov['refused'] or not a['intended_stocks'] or expected_fraction < a['minimum_fraction'] else
                           'degraded' if a['ready_stocks'] != a['intended_stocks'] or a['capacity_excluded'] or cov['errors'] else 'ok')
        equations.extend([
            cov['intended'] == a['intended_stocks'] + 1,
            cov['benchmark_added'] in (0, 1) and cov['benchmark_ready'] in (0, 1),
            a['fraction'] == expected_fraction,
            a['status'] == expected_status,
            a['complete_intended'] == (a['ready_stocks'] == a['intended_stocks']),
            a['complete_evaluation'] == (cov['scan_unattempted'] == 0 and cov['errors'] == 0),
            sum(cov['sessions']['latest_bar_dates'].values()) == cov['with_bars'],
        ])
        for reason in ('no_bars', 'dropped', 'unfetched_budget', 'stale', 'gapped', 'unreadable', 'price_excluded', 'refused', 'unfetched_failure'):
            equations.append(cov['reasons'][reason]['count'] == cov[reason])
        return [] if all(equations) else ['input population ledger does not reconcile']
    except (KeyError, TypeError, ValueError, AttributeError):  # a block that is not an object has no .values()
        return ['incomplete input population ledger']



def evaluated(cov):
    """Finalize evaluation status after scanning or a terminal coverage refusal."""
    cov['acceptance']['complete_evaluation'] = not (cov['scan_unattempted'] or cov['errors'])
    if cov['errors'] and cov['acceptance']['status'] == 'ok':
        cov['acceptance']['status'] = 'degraded'


def record_faults(run):
    cov = run.get('coverage')
    if not isinstance(cov, dict) or 'version' not in cov:
        return []  # archives predating this contract remain unknown, never backfilled
    errors = faults(cov)
    uni, basis = run.get('universe') or {}, run.get('input_basis') or {}
    if not isinstance(uni, dict) or not isinstance(basis, dict):
        errors.append('run.universe or run.input_basis is not an object')
        return errors
    errors.extend(universe.selection_faults(uni.get('selection')))
    if basis.get('adjustment') != market_data.BAR_ADJUSTMENT.value or basis.get('feed') != run.get('feed'):
        errors.append('bar request basis is missing or inconsistent')
    if basis.get('expected_session') != run.get('expected_session') or basis.get('evaluated_session') != run.get('session'):
        errors.append('bar session basis is inconsistent')
    acceptance = cov.get('acceptance')
    if not isinstance(acceptance, dict):
        errors.append('coverage acceptance is not an object')
    elif acceptance.get('status') == 'fail' or cov.get('scan_unattempted'):
        errors.append('unaccepted coverage cannot be published')
    size, added = uni.get('size', 0), cov.get('benchmark_added', 0)
    if type(size) is not int or type(added) is not int:
        errors.append('universe size or benchmark count is not an integer')
    elif cov.get('intended') != size + added:
        errors.append('universe and fetch populations disagree')
    selection = uni.get('selection')
    if selection and isinstance(selection, dict) and selection.get('intended') != uni.get('size'):
        errors.append('universe selection size is inconsistent')
    return errors


def stale_limit(intended_stocks, fraction):
    """The most stale stocks a run tolerates: the fraction of the intended
    stocks, floored, in exact arithmetic so the boundary never rounds up.
    A missing fraction tolerates nothing."""
    return math.floor(int(intended_stocks) * Fraction(str(fraction or 0)))


def allowed_endings(evaluated, sessions_max):
    """The sessions a tolerated stale frame may end on: the ``sessions_max``
    exchange sessions before the evaluated one, as ISO dates. None or zero
    allows none."""
    if not sessions_max or type(sessions_max) is not int or sessions_max < 0:
        return set()
    return {d.isoformat() for d in sessions.sessions_before(date.fromisoformat(str(evaluated)), sessions_max)}


def first_sessions(gapped, session, benchmark):
    """The stocks among the gapped frames whose provider history begins on
    ``session``: no bar before it at all. ``gapped`` is
    market_data.drop_gapped()'s map, which holds the bar a frame has before the
    session, or -- when it has none -- its own newest bar, the session itself.
    The benchmark is never one: its gap is the gap it always was."""
    return sorted(t for t, day in gapped.items() if t != benchmark and day == session)


def stale_tolerance(cov, fraction, *, names, benchmark, held=(), names_max, endings, sessions_max,
                    first=(), first_count=None, version=TOLERANCE_VERSION):
    """Whether a degraded acceptance is ONLY the stale tail the run tolerates.

    Pure: it reads the ledger and never writes it, so acceptance stays
    'degraded' and every count stays exactly what build() wrote. The tail is
    tolerated when every gap is a stale frame, every stale frame ends within
    the ``sessions_max`` sessions before the evaluated one (on a readable
    date), no open model plan's stock is among them, and no more than
    ``stale_limit()`` stocks are stale. ``names`` are every stale frame's
    symbol; the benchmark among them is not a stock. ``endings`` is where each
    named frame ends (ISO date, None when unreadable), carried so the next
    session's run can read every session each one missed.

    Under version 3 a gapped frame whose provider history begins on the
    evaluated session (``first``, from first_sessions(); ``first_count`` when
    the names are not carried) is not one of the other gaps: it is counted
    beside the stale stocks against the same limit, and an open model plan's
    stock among them is held as a stale one is. Version 2 is the rule as it
    was, for the records made under it."""
    if version not in TOLERANCE_VERSIONS:
        raise ValueError(f"unknown input tolerance version {version!r}")
    a = cov['acceptance']
    limit = stale_limit(a['intended_stocks'], fraction)
    sess = cov['sessions']
    stale_stocks = cov['stale'] - int(benchmark in names)
    first = sorted(first) if version >= FIRST_SESSIONS_VERSION else []
    first_stocks = (len(first) if first_count is None else first_count) if version >= FIRST_SESSIONS_VERSION else 0
    reasons = []
    if a['status'] == 'ok':
        verdict = COMPLETE
    else:
        gaps = {k: cov[k] for k in OTHER_EXCEPTIONS}
        gaps['gapped'] -= first_stocks
        if (any(gaps.values()) or a['capacity_excluded']
                or a['status'] != 'degraded'):
            reasons.append('other_exceptions')
        # every frame that does not end on the evaluated session ends within the bound before it
        behind = set(sess['latest_bar_dates']) - {sess['evaluated']}
        if cov['stale'] and not behind <= allowed_endings(sess['evaluated'], sessions_max):
            reasons.append('behind_more')
        if stale_stocks + first_stocks > limit:
            reasons.append('over_limit')
        if held:
            reasons.append('open_plan')
        verdict = NOT_TOLERATED if reasons else TOLERATED
    names = sorted(names)
    carried = len(names) <= names_max
    block = {'version': version, 'verdict': verdict, 'reasons': reasons,
             'fraction': fraction, 'limit': limit, 'sessions_max': sessions_max,
             'stale': cov['stale'], 'stale_stocks': stale_stocks,
             'benchmark': benchmark, 'evaluated': sess['evaluated'], 'previous': sess['previous'],
             'names': names if carried else None,
             'endings': {n: endings.get(n) for n in names} if carried else None,
             'held': sorted(held)}
    if version >= FIRST_SESSIONS_VERSION:
        block['first_sessions'] = first if first_stocks <= names_max else None
        block['first_session_stocks'] = first_stocks
    return block


def _count(n, one, many):
    return f"{n} {one if n == 1 else many}"


def _percent(fraction):
    """The archived fraction as the percentage it is, never re-rounded to a whole one."""
    return f"{float(fraction or 0) * 100:.4f}".rstrip("0").rstrip(".") + "%"


def _ending(cov, tol):
    """Where the stale frames end: the previous session when they all do, else each date."""
    dates = {d: n for d, n in cov['sessions']['latest_bar_dates'].items() if d != tol['evaluated']}
    if set(dates) == {tol['previous']}:
        return f"{'ending' if cov['stale'] == 1 else 'each ending'} on the previous session, {tol['previous']}"
    parts = [f"{n} on {d}" if d not in (None, 'None') else f"{n} on an unreadable date"
             for d, n in sorted(dates.items(), key=lambda kv: str(kv[0]))]
    return "ending " + ", ".join(parts)


def _first(tol):
    """The version-3 count of stocks whose provider history begins on the
    evaluated session; 0 under version 2, which has no such count."""
    n = tol.get('first_session_stocks')
    return (n if type(tol.get('version')) is int and tol['version'] >= FIRST_SESSIONS_VERSION
            and type(n) is int and n > 0 else 0)


def _why(cov, tol):
    words = []
    first = _first(tol)
    for r in tol['reasons']:
        if r == 'other_exceptions':
            counts = {k: cov[k] - (first if k == 'gapped' else 0) for k in OTHER_EXCEPTIONS}
            gaps = [f"{OTHER_WORDS[k]}: {counts[k]}" for k in OTHER_EXCEPTIONS if counts[k]]
            if cov['acceptance']['capacity_excluded']:
                gaps.append(f"{OTHER_WORDS['capacity_excluded']}: {cov['acceptance']['capacity_excluded']}")
            words.append("other gaps beside the stale frames (" + ", ".join(gaps or ["coverage refused"]) + ")")
        elif r == 'behind_more':
            words.append(f"not every stale frame ends within the {_count(tol['sessions_max'] or 0, 'session', 'sessions')} "
                         f"before {tol['evaluated']} on a readable date")
        elif r == 'over_limit' and first:
            words.append(f"{_count(tol['stale_stocks'], 'stale stock', 'stale stocks')} and "
                         f"{_count(first, 'stock with no earlier bar', 'stocks with no earlier bar')} "
                         "are more than the limit")
        elif r == 'over_limit':
            words.append(f"{_count(tol['stale_stocks'], 'stale stock is', 'stale stocks are')} more than the limit")
        elif r == 'open_plan':
            words.append(f"an open model plan's stock is among them ({', '.join(tol['held'])})")
    return "; ".join(words)


def _first_clause(tol, first):
    """The stocks whose provider history begins on the evaluated session, in words."""
    one = first == 1
    named = tol.get('first_sessions')
    who = f" ({', '.join(named)})" if isinstance(named, list) and named else ""
    return (f" {_count(first, 'returned frame', 'returned frames')}{who} had no bar before {tol['evaluated']} "
            f"at all: the provider's history for {'it' if one else 'them'} begins on {tol['evaluated']}, "
            f"so there is no session before to measure {'its' if one else 'their'} move against, and "
            f"{'it is not a measured non-match' if one else 'they are not measured non-matches'}.")


def _tolerance_clause(cov, tol):
    """The stale tail in words, appended to the incomplete-coverage sentence."""
    first = _first(tol)
    if first:
        return _clause_with_first(cov, tol, first)
    one = cov['stale'] == 1
    s = (f" {_count(cov['stale'], 'returned frame', 'returned frames')} had no bar for {tol['evaluated']}, "
         f"{_ending(cov, tol)}. "
         f"{'Its' if one else 'Their'} {tol['evaluated']} input{' is' if one else 's are'} unknown, "
         f"not {'a measured non-match' if one else 'measured non-matches'}.")
    if tol['verdict'] == TOLERATED:
        return s + (f" That is within this run's stale tolerance of {_count(tol['limit'], 'stock', 'stocks')} "
                    f"({_percent(tol['fraction'])} of the intended stocks), each ending within the "
                    f"{_count(tol['sessions_max'], 'session', 'sessions')} before, so the stale frames do not degrade "
                    f"the run; the next session's run, when it publishes, reads every session "
                    f"{'it' if one else 'they'} missed again.")
    return s + (f" Outside this run's stale tolerance ({_count(tol['limit'], 'stock', 'stocks')}, "
                f"{_percent(tol['fraction'])}, within {_count(tol['sessions_max'] or 0, 'session', 'sessions')}): "
                f"{_why(cov, tol)}.")


def _clause_with_first(cov, tol, first):
    """The clause of a version-3 night with at least one stock whose provider
    history begins on the evaluated session: the stale tail first when there
    is one, then those stocks, then the one verdict over both."""
    stale = cov['stale']
    s = ""
    if stale:
        one = stale == 1
        s = (f" {_count(stale, 'returned frame', 'returned frames')} had no bar for {tol['evaluated']}, "
             f"{_ending(cov, tol)}. "
             f"{'Its' if one else 'Their'} {tol['evaluated']} input{' is' if one else 's are'} unknown, "
             f"not {'a measured non-match' if one else 'measured non-matches'}.")
    s += _first_clause(tol, first)
    if tol['verdict'] == TOLERATED:
        ending = (f", each stale frame ending within the {_count(tol['sessions_max'], 'session', 'sessions')} before"
                  if stale else "")
        reads = (f"; the next session's run, when it publishes, reads every session "
                 f"{'the stale frame' if stale == 1 else 'the stale frames'} missed again." if stale else ".")
        return s + (f" That is within this run's input tolerance of {_count(tol['limit'], 'stock', 'stocks')} "
                    f"({_percent(tol['fraction'])} of the intended stocks){ending}, so "
                    f"{'this frame does' if stale + first == 1 else 'these frames do'} not degrade the run{reads}")
    return s + (f" Outside this run's input tolerance ({_count(tol['limit'], 'stock', 'stocks')}, "
                f"{_percent(tol['fraction'])}, within {_count(tol['sessions_max'] or 0, 'session', 'sessions')}): "
                f"{_why(cov, tol)}.")


def coverage_sentence(run):
    """Published scope: complete means this selection, never the whole market.

    A record that carries a stale tolerance block (run.input_tolerance) adds
    what its stale frames were and whether the tolerance held; a record
    without one reads exactly as it was published."""
    cov = run.get('coverage') or {}
    accept = cov.get('acceptance') or {}
    if accept.get('status') in ('degraded', 'fail'):
        tol = run.get('input_tolerance')
        clause = (_tolerance_clause(cov, tol) if isinstance(tol, dict) and 'version' in tol
                  and accept.get('status') == 'degraded' and (cov.get('stale') or _first(tol)) else "")
        return (f"Incomplete input coverage: {accept['ready_stocks']} of {accept['intended_stocks']} "
                f"intended stocks had usable session bars. {cov.get('unfetched_budget', 0)} fetch names were never attempted "
                f"(fetch counts include the benchmark); stocks excluded by capacity: {accept.get('capacity_excluded', 0)}; "
                f"{cov.get('errors', 0)} scan/quality errors occurred. Results describe only the evaluated subset.") + clause
    if accept.get('status') == 'ok':
        return f"All {accept['intended_stocks']} intended stocks had usable session bars; {cov['measured']} were measured after session price eligibility. Coverage is of this selection, not every listed security."
    return 'Input completeness was not recorded for this publication; an empty result does not establish that no setups existed.'


def _benchmark_stale(cov, tol):
    """Whether the benchmark is among the stale frames of a block that does not
    carry their names (a tail longer than the names it carries), read off the
    ledger: a benchmark that was ready is not stale, and one that was not ready
    while no other gap could hold it is. Only when the ledger cannot tell (a
    long stale tail beside another gap) is the block's own stock count read,
    as one benchmark or none; any other count then fails to re-derive."""
    if cov['benchmark_ready']:
        return False
    if not any(cov[k] for k in BENCHMARK_GAPS):
        return True
    return cov['stale'] - tol['stale_stocks'] == 1


def tolerance_faults(run, pipeline_rules, plan_tickers):
    """The stale tolerance block held to the record it sits in, one level in.

    A record made under rules without the tolerance is not asked for one.
    Otherwise the block must carry the record's OWN archived fraction, name
    exactly the stale population the ledger counted, re-derive to the same
    verdict, and print the sentence it was written with; and a shortfall it
    did not tolerate must be named coverage_thin. ``plan_tickers`` are the
    tickers of the record's unfinished open model plans, or None when the
    caller cannot say (a closed night carries the previous plans)."""
    if (not isinstance(pipeline_rules, dict) or 'stale_tolerance_fraction' not in pipeline_rules
            or 'stale_sessions_max' not in pipeline_rules):
        return []
    cov = run.get('coverage')
    if not isinstance(cov, dict) or 'version' not in cov:
        return []
    tol = run.get('input_tolerance')
    if tol is None:
        return ['input tolerance block missing']
    # rules that archive the block's version hold it to that version; rules from
    # before archived none and wrote version 2
    expected = pipeline_rules.get('input_tolerance_version', UNVERSIONED_TOLERANCE)
    try:
        if (type(expected) is not int or expected not in TOLERANCE_VERSIONS or tol['version'] != expected
                or tol['verdict'] not in TOLERANCE_VERDICTS):
            return ['input tolerance version or verdict unknown']
        if tol['fraction'] != pipeline_rules['stale_tolerance_fraction']:
            return ['input tolerance is not the archived stale_tolerance_fraction']
        if tol['sessions_max'] != pipeline_rules['stale_sessions_max']:
            return ['input tolerance is not the archived stale_sessions_max']
        names, held, endings = tol['names'], tol['held'], tol['endings']
        faults = []
        if names is None:
            if cov['stale'] <= pipeline_rules['stale_names_max']:
                faults.append('input tolerance drops a stale membership it could carry')
            if endings is not None:
                faults.append('input tolerance endings are not its names')
        elif (names != sorted(set(names)) or not all(isinstance(n, str) for n in names)
              or len(names) != cov['stale'] or universe.identity(names) != cov['reasons']['stale']['identity']):
            faults.append('input tolerance names are not the stale population the ledger counted')
        elif not isinstance(endings, dict) or set(endings) != set(names):
            faults.append('input tolerance endings are not its names')
        elif (not all(e is None or (isinstance(e, str) and date.fromisoformat(e)) for e in endings.values())
              or Counter(str(e) for e in endings.values())
              != {d: n for d, n in cov['sessions']['latest_bar_dates'].items() if d != cov['sessions']['evaluated']}):
            faults.append("input tolerance endings are not the ledger's stale dates")
        first, first_count = [], 0
        if expected >= FIRST_SESSIONS_VERSION:
            first, first_count = tol['first_sessions'], tol['first_session_stocks']
            faults.extend(_first_faults(cov, tol, first, first_count, pipeline_rules['stale_names_max']))
        named = set(names or []) | set(first or [])
        if held != sorted(set(held)) or ((names is not None and first is not None) and not set(held) <= named):
            faults.append('input tolerance holds a stock it does not name')
        if (plan_tickers is not None and names is not None and first is not None
                and held != sorted(named & set(plan_tickers))):
            faults.append('input tolerance does not hold the open model plans among the stale stocks')
        # without its names the block is re-derived over the one fact they carried: the benchmark's
        carried = names if names is not None else ([tol['benchmark']] if _benchmark_stale(cov, tol) else [])
        again = stale_tolerance(cov, tol['fraction'], names=carried, benchmark=tol['benchmark'], held=held,
                                names_max=pipeline_rules['stale_names_max'], endings=endings or {},
                                sessions_max=tol['sessions_max'], first=first or [],
                                first_count=first_count, version=expected)
        if any(again[k] != tol[k] for k in ('verdict', 'reasons', 'limit', 'sessions_max', 'stale', 'stale_stocks',
                                             'evaluated', 'previous')):
            faults.append('input tolerance does not re-derive from the ledger')
        if tol.get('sentence') != coverage_sentence(run):
            faults.append('input tolerance sentence is not the coverage sentence it was written with')
        kinds = {p.get('kind') for p in run.get('problems') or [] if isinstance(p, dict)}
        if cov['acceptance']['status'] == 'degraded' and tol['verdict'] != TOLERATED and 'coverage_thin' not in kinds:
            faults.append('an input shortfall outside the recorded tolerance is not named coverage_thin')
        return faults
    except (KeyError, TypeError, ValueError, AttributeError):
        return ['input tolerance block is malformed']


def _first_faults(cov, tol, first, count, names_max):
    """A version-3 block's first sessions held to the ledger it sits beside:
    a count of gapped stocks no larger than the ledger's gapped count, names
    carried whenever the bound allows, never the benchmark, and -- when every
    gapped frame is one -- exactly the gapped population the ledger counted."""
    if type(count) is not int or count < 0 or count > cov['gapped']:
        return ['input tolerance first sessions are not a count of the gapped frames']
    if first is None:
        return ['input tolerance drops a first-session membership it could carry'] if count <= names_max else []
    if (not isinstance(first, list) or not all(isinstance(n, str) for n in first)
            or first != sorted(set(first)) or len(first) != count or tol['benchmark'] in first):
        return ['input tolerance first sessions are not the stocks it counted']
    gapped = cov['reasons']['gapped']
    if count == cov['gapped'] and universe.identity(first) != gapped['identity']:
        return ['input tolerance first sessions are not the gapped population the ledger counted']
    if cov['gapped'] == len(gapped['sample']) and not set(first) <= set(gapped['sample']):
        return ['input tolerance first sessions are not the gapped population the ledger counted']
    return []


# -- the stale stocks the seed alone asked for -----------------------------------
#: A seed name the directory no longer lists keeps being asked for every night,
#: and once it stops trading it is stale every night until a human retires it
#: from data/symbols.txt: WBD, 13-15 October 2026, three nights degraded as the
#: one frame past the session bound while the record said only that it was
#: stale. The block below joins the record's own two lists -- the tolerance's
#: stale names and the selection's seed additions -- and only when both are
#: complete; otherwise it says what it cannot say. It decides nothing.
SEED_STALE_VERSION = 1
SEED_STALE_MEMBERSHIPS = ('complete', 'sampled', 'unavailable')
SEED_STALE_REASONS = ('no_directory_selection', 'seed_universe', 'explicit_universe',
                      'seed_additions_sampled', 'stale_names_not_carried')


def seed_stale(tol, selection):
    """Which stale stocks the seed alone asked for, read off the record.

    ``tol`` is the run's stale tolerance block (its ``names`` are every stale
    frame's symbol, or None past the carrying bound; the benchmark among them
    is not a stock); ``selection`` is the universe's selection ledger, whose
    ``seed_added`` carries a count and a sample bounded by ``universe.SAMPLE_LIMIT``
    (archived as ``universe.sample_limit``). The join is made only
    over a directory selection whose sample IS the membership, with the stale
    names carried; a seed or explicit universe (whose selection ledger is the
    manual kind), a record without a selection, a sampled seed list or an
    uncarried stale list is a named reason and no names. Pure, and re-derived
    by ``seed_stale_faults``."""
    kind = selection.get('kind') if isinstance(selection, dict) else None
    added = selection.get('seed_added') if kind == 'directory' else None
    names = tol.get('names')
    if not isinstance(added, dict):
        membership, count, named = 'unavailable', None, None
    else:
        count, sample = added['count'], list(added['sample'])
        named = len(sample)
        membership = 'complete' if count == named else 'sampled'
    if membership == 'unavailable':
        reason = {'seed': 'seed_universe', 'explicit': 'explicit_universe'}.get(kind, 'no_directory_selection')
        found = None
    elif membership == 'sampled':
        reason, found = 'seed_additions_sampled', None
    elif names is None:
        reason, found = 'stale_names_not_carried', None
    else:
        reason, found = None, sorted((set(names) - {tol.get('benchmark')}) & set(sample))
    block = {'version': SEED_STALE_VERSION, 'membership': membership, 'seed_added': count, 'seed_named': named,
             'stale_stocks': tol['stale_stocks'], 'names': found, 'reason': reason}
    block['sentence'] = seed_stale_sentence(block)
    return block


def seed_stale_sentence(block):
    """The block in words; empty when there is no stale stock to speak of."""
    n = block['stale_stocks']
    if not n:
        return ''
    names = block['names']
    if names is None:
        why = {'no_directory_selection': 'this run recorded no directory selection',
               'seed_universe': "this run's universe was the seed file alone, so whether the directory "
                                'still lists a stale stock was not read',
               'explicit_universe': "this run's universe was an explicit list, not a directory selection",
               'seed_additions_sampled': f"the selection names {block['seed_named']} of its {block['seed_added']} seed additions",
               'stale_names_not_carried': 'the record does not name its stale stocks'}[block['reason']]
        return f'Whether a stale stock is on the seed alone is not recorded: {why}.'
    if not names:
        return ('The stale stock is in the directory this run selected from, not on the seed alone.' if n == 1
                else f'None of the {n} stale stocks is on the seed alone; each is in the directory this run selected from.')
    k = len(names)
    lead = ('The stale stock is' if n == 1
            else f"{k} of the {n} stale stocks {'is' if k == 1 else 'are'}")
    return (f"{lead} on the seed alone, not in the directory this run selected from: {', '.join(names)}. "
            'A seed name is asked for again every night until it is retired from data/symbols.txt by hand.')


def seed_stale_faults(run, pipeline_rules):
    """The seed-only stale block held to the record it sits in, one level in:
    asked for only under rules that write it, and refused unless it is exactly
    what the record's own tolerance names and selection re-derive, type for
    type (a JSON ``true`` or ``1.0`` is not the ``1`` the run writes)."""
    if not isinstance(pipeline_rules, dict) or 'seed_stale_version' not in pipeline_rules:
        return []
    cov, tol = run.get('coverage'), run.get('input_tolerance')
    if not isinstance(cov, dict) or 'version' not in cov or not isinstance(tol, dict) or 'version' not in tol:
        return []  # a record without a versioned coverage ledger and tolerance block predates these contracts
    block = run.get('seed_stale')
    if block is None:
        return ['seed-only stale block missing']
    try:
        if block['version'] != SEED_STALE_VERSION or pipeline_rules['seed_stale_version'] != SEED_STALE_VERSION:
            return ['seed-only stale block version unknown']
        selection = (run.get('universe') or {}).get('selection') or {}
        if _canonical(block) != _canonical(seed_stale(tol, selection)):
            return ['seed-only stale block does not re-derive from the record']
        return []
    except (KeyError, TypeError, ValueError, AttributeError):
        return ['seed-only stale block malformed']


def _canonical(block):
    """The block as the JSON bytes the record carries, so a forged type is a
    different block (``json.dumps`` refuses a NaN and an object JSON lacks)."""
    return json.dumps(block, sort_keys=True, allow_nan=False)
