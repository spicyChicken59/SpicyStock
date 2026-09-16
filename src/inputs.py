"""Bounded public input ledger, composed from the existing download/session stats.

Counts are disjoint except explicitly labeled diagnostics. The benchmark is
transported but excluded from the stock coverage denominator and strategy scan.
An incomplete input is never counted as a measured non-match.
"""
from collections import Counter

from src import market_data, universe

VERSION = 1


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
    except (KeyError, TypeError, ValueError):
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
    errors.extend(universe.selection_faults(uni.get('selection')))
    if basis.get('adjustment') != market_data.BAR_ADJUSTMENT.value or basis.get('feed') != run.get('feed'):
        errors.append('bar request basis is missing or inconsistent')
    if basis.get('expected_session') != run.get('expected_session') or basis.get('evaluated_session') != run.get('session'):
        errors.append('bar session basis is inconsistent')
    if cov.get('acceptance', {}).get('status') == 'fail' or cov.get('scan_unattempted'):
        errors.append('unaccepted coverage cannot be published')
    if cov.get('intended') != uni.get('size', 0) + cov.get('benchmark_added', 0):
        errors.append('universe and fetch populations disagree')
    if uni.get('selection') and uni['selection']['intended'] != uni.get('size'):
        errors.append('universe selection size is inconsistent')
    return errors


def coverage_sentence(run):
    """Published scope: complete means this selection, never the whole market."""
    cov = run.get('coverage') or {}
    accept = cov.get('acceptance') or {}
    if accept.get('status') in ('degraded', 'fail'):
        return (f"Incomplete input coverage: {accept['ready_stocks']} of {accept['intended_stocks']} "
                f"intended stocks had usable session bars. {cov.get('unfetched_budget', 0)} fetch names were never attempted "
                f"(fetch counts include the benchmark); stocks excluded by capacity: {accept.get('capacity_excluded', 0)}; "
                f"{cov.get('errors', 0)} scan/quality errors occurred. Results describe only the evaluated subset.")
    if accept.get('status') == 'ok':
        return f"All {accept['intended_stocks']} intended stocks had usable session bars; {cov['measured']} were measured after session price eligibility. Coverage is of this selection, not every listed security."
    return 'Input completeness was not recorded for this publication; an empty result does not establish that no setups existed.'
