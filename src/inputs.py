"""Bounded public input ledger, composed from the existing download/session stats.

Counts are disjoint except explicitly labeled diagnostics. The benchmark is
transported but excluded from the stock coverage denominator and strategy scan.
An incomplete input is never counted as a measured non-match.
"""
from collections import Counter
from fractions import Fraction
import math

from src import market_data, universe

VERSION = 1

# The stale tolerance (run.input_tolerance). A degraded acceptance whose ONLY
# gap is a small tail of stocks one session behind is counted and named, the
# next session's run reads those stocks again, and the tail does not make the
# run degraded; anything else keeps today's rule. The benchmark is outside the
# stock denominator here as it is in acceptance (it feeds only the scorecard's
# comparison line), so a stale benchmark neither counts against the limit nor
# blocks it. The fraction itself is a strategy number and lives in
# pipeline.RULES; these are the block's own words.
TOLERANCE_VERSION = 1
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


def stale_limit(intended_stocks, fraction):
    """The most stale stocks a run tolerates: the fraction of the intended
    stocks, floored, in exact arithmetic so the boundary never rounds up.
    A missing fraction tolerates nothing."""
    return math.floor(int(intended_stocks) * Fraction(str(fraction or 0)))


def stale_tolerance(cov, fraction, *, names, benchmark, held=(), names_max):
    """Whether a degraded acceptance is ONLY the stale tail the run tolerates.

    Pure: it reads the ledger and never writes it, so acceptance stays
    'degraded' and every count stays exactly what build() wrote. The tail is
    tolerated when every gap is a stale frame, every stale frame ends on the
    previous session, no open model plan's stock is among them, and no more
    than ``stale_limit()`` stocks are stale. ``names`` are every stale frame's
    symbol; the benchmark among them is not a stock."""
    a = cov['acceptance']
    limit = stale_limit(a['intended_stocks'], fraction)
    sess = cov['sessions']
    stale_stocks = cov['stale'] - int(benchmark in names)
    reasons = []
    if a['status'] == 'ok':
        verdict = COMPLETE
    else:
        if (any(cov[k] for k in OTHER_EXCEPTIONS) or a['capacity_excluded']
                or a['status'] != 'degraded'):
            reasons.append('other_exceptions')
        # every frame that does not end on the evaluated session ends on the previous one
        if cov['stale'] and set(sess['latest_bar_dates']) - {sess['evaluated']} != {sess['previous']}:
            reasons.append('behind_more')
        if stale_stocks > limit:
            reasons.append('over_limit')
        if held:
            reasons.append('open_plan')
        verdict = NOT_TOLERATED if reasons else TOLERATED
    names = sorted(names)
    return {'version': TOLERANCE_VERSION, 'verdict': verdict, 'reasons': reasons,
            'fraction': fraction, 'limit': limit, 'stale': cov['stale'], 'stale_stocks': stale_stocks,
            'benchmark': benchmark, 'evaluated': sess['evaluated'], 'previous': sess['previous'],
            'names': names if len(names) <= names_max else None, 'held': sorted(held)}


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


def _why(cov, tol):
    words = []
    for r in tol['reasons']:
        if r == 'other_exceptions':
            gaps = [f"{OTHER_WORDS[k]}: {cov[k]}" for k in OTHER_EXCEPTIONS if cov[k]]
            if cov['acceptance']['capacity_excluded']:
                gaps.append(f"{OTHER_WORDS['capacity_excluded']}: {cov['acceptance']['capacity_excluded']}")
            words.append("other gaps beside the stale frames (" + ", ".join(gaps or ["coverage refused"]) + ")")
        elif r == 'behind_more':
            words.append("not every stale frame ends on the previous session")
        elif r == 'over_limit':
            words.append(f"{_count(tol['stale_stocks'], 'stale stock is', 'stale stocks are')} more than the limit")
        elif r == 'open_plan':
            words.append(f"an open model plan's stock is among them ({', '.join(tol['held'])})")
    return "; ".join(words)


def _tolerance_clause(cov, tol):
    """The stale tail in words, appended to the incomplete-coverage sentence."""
    one = cov['stale'] == 1
    s = (f" {_count(cov['stale'], 'returned frame', 'returned frames')} had no bar for {tol['evaluated']}, "
         f"{_ending(cov, tol)}. "
         f"{'Its' if one else 'Their'} {tol['evaluated']} input{' is' if one else 's are'} unknown, "
         f"not {'a measured non-match' if one else 'measured non-matches'}.")
    if tol['verdict'] == TOLERATED:
        return s + (f" That is within this run's stale tolerance of {_count(tol['limit'], 'stock', 'stocks')} "
                    f"({_percent(tol['fraction'])} of the intended stocks), so the stale frames do not degrade "
                    f"the run; the next session's run, when it publishes, reads "
                    f"{'its' if one else 'their'} {tol['evaluated']} bar{'' if one else 's'} again.")
    return s + (f" Outside this run's stale tolerance ({_count(tol['limit'], 'stock', 'stocks')}, "
                f"{_percent(tol['fraction'])}): {_why(cov, tol)}.")


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
                  and accept.get('status') == 'degraded' and cov.get('stale') else "")
        return (f"Incomplete input coverage: {accept['ready_stocks']} of {accept['intended_stocks']} "
                f"intended stocks had usable session bars. {cov.get('unfetched_budget', 0)} fetch names were never attempted "
                f"(fetch counts include the benchmark); stocks excluded by capacity: {accept.get('capacity_excluded', 0)}; "
                f"{cov.get('errors', 0)} scan/quality errors occurred. Results describe only the evaluated subset.") + clause
    if accept.get('status') == 'ok':
        return f"All {accept['intended_stocks']} intended stocks had usable session bars; {cov['measured']} were measured after session price eligibility. Coverage is of this selection, not every listed security."
    return 'Input completeness was not recorded for this publication; an empty result does not establish that no setups existed.'


def tolerance_faults(run, pipeline_rules, plan_tickers):
    """The stale tolerance block held to the record it sits in, one level in.

    A record made under rules without the tolerance is not asked for one.
    Otherwise the block must carry the record's OWN archived fraction, name
    exactly the stale population the ledger counted, re-derive to the same
    verdict, and print the sentence it was written with; and a shortfall it
    did not tolerate must be named coverage_thin. ``plan_tickers`` are the
    tickers of the record's unfinished open model plans, or None when the
    caller cannot say (a closed night carries the previous plans)."""
    if not isinstance(pipeline_rules, dict) or 'stale_tolerance_fraction' not in pipeline_rules:
        return []
    cov = run.get('coverage')
    if not isinstance(cov, dict) or 'version' not in cov:
        return []
    tol = run.get('input_tolerance')
    if tol is None:
        return ['input tolerance block missing']
    try:
        if tol['version'] != TOLERANCE_VERSION or tol['verdict'] not in TOLERANCE_VERDICTS:
            return ['input tolerance version or verdict unknown']
        if tol['fraction'] != pipeline_rules['stale_tolerance_fraction']:
            return ['input tolerance is not the archived stale_tolerance_fraction']
        names, held = tol['names'], tol['held']
        faults = []
        if names is None:
            if cov['stale'] <= pipeline_rules['stale_names_max']:
                faults.append('input tolerance drops a stale membership it could carry')
        elif (names != sorted(set(names)) or not all(isinstance(n, str) for n in names)
              or len(names) != cov['stale'] or universe.identity(names) != cov['reasons']['stale']['identity']):
            faults.append('input tolerance names are not the stale population the ledger counted')
        if held != sorted(set(held)) or (names is not None and not set(held) <= set(names)):
            faults.append('input tolerance holds a stock it does not name')
        if plan_tickers is not None and names is not None and held != sorted(set(names) & set(plan_tickers)):
            faults.append('input tolerance does not hold the open model plans among the stale stocks')
        again = stale_tolerance(cov, tol['fraction'], names=names or [], benchmark=tol['benchmark'], held=held,
                                names_max=pipeline_rules['stale_names_max'])
        if any(again[k] != tol[k] for k in ('verdict', 'reasons', 'limit', 'stale', 'stale_stocks', 'evaluated', 'previous')):
            faults.append('input tolerance does not re-derive from the ledger')
        if tol.get('sentence') != coverage_sentence(run):
            faults.append('input tolerance sentence is not the coverage sentence it was written with')
        kinds = {p.get('kind') for p in run.get('problems') or [] if isinstance(p, dict)}
        if cov['acceptance']['status'] == 'degraded' and tol['verdict'] != TOLERATED and 'coverage_thin' not in kinds:
            faults.append('an input shortfall outside the recorded tolerance is not named coverage_thin')
        return faults
    except (KeyError, TypeError, ValueError, AttributeError):
        return ['input tolerance block is malformed']
