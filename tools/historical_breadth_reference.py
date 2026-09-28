"""Offline, scalar reference for the selected SpicyStock Market Monitor formula.

This is an arithmetic oracle, not independent price evidence or validation of
the formula's attribution to Stockbee. No production predicate is used by the
reference. ``compare_replay`` calls production only after constructing the
reference and gives it exactly the same population and observation prefixes.

Input frames must already be normalized to unique, ordered exchange-session
dates. Raw response retention and normalization belong to the acquisition tool.
Absent rows remain absent. Unknown events are distinct from measured false
events, even though production's observed totals count neither.
"""
from __future__ import annotations

import hashlib
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

import pandas as pd

from src import sessions

VERSION = 1
COUNTS = (
    'up4', 'down4', 'up25_quarter', 'down25_quarter', 'up25_month',
    'down25_month', 'up50_month', 'down50_month', 'up13_34d', 'down13_34d',
)
RULES = {
    'events': '100*(C-C1)/C1 >= 4 or <= -4; V >= 100000 and V > V1',
    'month': '100*(C-C20)/C20; C20 >= 5; AVGC20*AVGV20 >= 250000',
    'quarter': '100*((C+.01)-(MINC65+.01))/(MINC65+.01) >= 25; '
               '100*((C+.01)-(MAXC65+.01))/(MAXC65+.01) <= -25; liquid',
    '34_sessions': 'same penny-guarded min/max formula with 34 sessions and +/-13%; liquid',
    'ma': 'C > mean(last 40 closes), percent denominator = measurable 40-session windows',
    'windows': 'consecutive XNYS sessions, trailing extrema/averages include today; C20 is 20 sessions earlier',
    'rounding': 'Python round(up_sum/down_sum, 2) before regime comparison; '
                'scaled counts round(reference*measured_universe/6500, 1); pct above MA round(..., 1)',
    'zero_denominator': 'ratio is null and its ratio predicates do not fire',
    'validity': 'missing/non-finite/non-positive prices and negative volumes become unknown; '
                'volume zero is valid; no missing session is filled',
    'population': 'B original mask; C target-day readiness and round(C,2)>=3; '
                  'D same eligibility recomputed on each observation day (counterfactual)',
    'source_scope': 'Selected SPICYSTOCK formula, recorded as LATER BONDE in knowledge/method.md; '
                    'arithmetic agreement is not an independent source-fidelity finding.',
}


def membership_sha256(symbols: Sequence[str]) -> str:
    """Canonical sorted unique symbols, newline separated, no final newline."""
    return hashlib.sha256('\n'.join(sorted(set(symbols))).encode()).hexdigest()


def _number(value, *, volume=False):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and (value >= 0 if volume else value > 0) else None


def _rows(frame: pd.DataFrame | None, target: date) -> dict:
    if frame is None:
        return {}
    result = {}
    last = None
    for stamp, row in frame.iterrows():
        stamp = pd.Timestamp(stamp)
        if pd.isna(stamp):
            raise ValueError('NaT session requires explicit normalization before reference replay')
        day = stamp.date()
        if day > target:
            continue  # a held-out tail is never visible to a historical consumer
        sessions.require_session(day)
        if day in result:
            raise ValueError(f'duplicate session {day}; normalize with retained row lineage first')
        if last is not None and day < last:
            raise ValueError('frames must be in increasing session order')
        last = day
        result[day] = {k: _number(row.get(k), volume=k == 'Volume')
                       for k in ('Open', 'High', 'Low', 'Close', 'Volume')}
    return result


def _readable(row) -> bool:
    if not row or any(row[k] is None for k in ('Open', 'High', 'Low', 'Close', 'Volume')):
        return False
    return row['Low'] <= min(row['Open'], row['Close']) <= max(row['Open'], row['Close']) <= row['High']


def _eligibility(rows: dict, day: date, exempt: bool) -> tuple[bool, str]:
    current = rows.get(day)
    previous = rows.get(sessions.previous_session(day))
    if current is None:
        return False, 'absent_target'
    if previous is None:
        return False, 'absent_prior'
    if not _readable(current) or not _readable(previous):
        return False, 'unreadable_pair'
    if not exempt and round(current['Close'], 2) < 3.0:
        return False, 'price_below_3_after_rounding'
    return True, 'eligible'


def _state(test, values):
    return None if any(v is None for v in values) else bool(test())


def _possible_events(c, c1, v, v1):
    """Coupled possibilities: one security/session can never be up AND down.

    Known false price/volume conditions restrict unknowns. Possibilities across
    adjacent sessions remain a conservative relaxation because those events
    share prices/volumes; the bounds never assert all endpoints are attainable.
    """
    volume_false = (v is not None and v < 100_000) or (
        v is not None and v1 is not None and v <= v1)
    if volume_false:
        return [[0, 0]]
    move = None if c is None or c1 is None else 100.0 * (c - c1) / c1
    if None not in (c, c1, v, v1):
        return [[int(move >= 4.0), int(move <= -4.0)]]
    result = [[0, 0]]
    if move is None or move >= 4.0:
        result.append([1, 0])
    if move is None or move <= -4.0:
        result.append([0, 1])
    return result


def _measure(rows, day, calendar, position):
    at = position[day]

    def value(offset, field='Close'):
        if at < offset:
            return None
        return rows.get(calendar[at - offset], {}).get(field)

    def window(size, field='Close'):
        values = [value(i, field) for i in range(size)]
        return values if all(v is not None for v in values) else None

    c, c1, c20, v, v1 = value(0), value(1), value(20), value(0, 'Volume'), value(1, 'Volume')
    w20, v20, w34, w40, w65 = window(20), window(20, 'Volume'), window(34), window(40), window(65)
    avgc20 = sum(w20) / 20 if w20 else None
    avgv20 = sum(v20) / 20 if v20 else None
    liquid = None if avgc20 is None or avgv20 is None else avgc20 * avgv20 >= 250_000
    move = None if c is None or c1 is None else 100.0 * (c - c1) / c1
    events = {
        'up4': _state(lambda: move >= 4.0 and v >= 100_000 and v > v1, (c, c1, v, v1)),
        'down4': _state(lambda: move <= -4.0 and v >= 100_000 and v > v1, (c, c1, v, v1)),
    }
    for size, win, up, down, threshold in (
            (65, w65, 'up25_quarter', 'down25_quarter', 25),
            (34, w34, 'up13_34d', 'down13_34d', 13)):
        for name, extreme, compare in (
                (up, min(win) if win else None, lambda x: x >= threshold),
                (down, max(win) if win else None, lambda x: x <= -threshold)):
            events[name] = _state(
                lambda: liquid and compare(100.0 * ((c + .01) - (extreme + .01)) / (extreme + .01)),
                (c, extreme, liquid))
    for amount in (25, 50):
        events[f'up{amount}_month'] = _state(
            lambda: liquid and c20 >= 5 and 100.0 * (c - c20) / c20 >= amount, (c, c20, liquid))
        events[f'down{amount}_month'] = _state(
            lambda: liquid and c20 >= 5 and 100.0 * (c - c20) / c20 <= -amount, (c, c20, liquid))
    avgc40 = sum(w40) / 40 if w40 else None
    events['above_40ma'] = _state(lambda: c > avgc40, (c, avgc40))
    return {
        'events': events,
        'measured_4': None not in (c, c1, v, v1),
        'possible_up_down': _possible_events(c, c1, v, v1),
        'values': {'close': c, 'prior_close': c1, 'volume': v, 'prior_volume': v1,
                   'change_pct': move, 'close_20_sessions_ago': c20,
                   'average_close_20': avgc20, 'average_volume_20': avgv20,
                   'minimum_close_65': min(w65) if w65 else None,
                   'maximum_close_65': max(w65) if w65 else None,
                   'minimum_close_34': min(w34) if w34 else None,
                   'maximum_close_34': max(w34) if w34 else None,
                   'average_close_40': avgc40},
    }


def coupled_ratio_bounds(event_rows: Sequence[dict]) -> dict:
    """Outer bounds over allowed event pairs, preserving their exclusivity.

    The finite upper bound with zero mandatory downs reserves one contributor
    for the denominator. That contributor cannot simultaneously supply an up.
    Undefined ratios remain separate; infinity is never substituted for null.
    """
    choices = [row['possible_up_down'] for row in event_rows if row.get('included', True)]
    if any(not pairs or any(pair not in ([0, 0], [1, 0], [0, 1]) for pair in pairs) for pairs in choices):
        raise ValueError('event pairs must be nonempty and mutually exclusive up/down events')
    up_min = sum(min(p[0] for p in pairs) for pairs in choices)
    up_max = sum(max(p[0] for p in pairs) for pairs in choices)
    down_min = sum(min(p[1] for p in pairs) for pairs in choices)
    down_max = sum(max(p[1] for p in pairs) for pairs in choices)
    lower = up_min / down_max if down_max else None
    upper = None
    if down_min:
        upper = up_max / down_min
    elif down_max:
        # A denominator of one maximizes any nonnegative finite ratio.
        lost_up = min(max(p[0] for p in pairs) for pairs in choices if [0, 1] in pairs)
        upper = float(up_max - lost_up)
    return {
        'up': [up_min, up_max], 'down': [down_min, down_max],
        'finite_ratio': [lower, upper],
        'finite_ratio_rounded': [round(x, 2) if x is not None else None for x in (lower, upper)],
        'undefined_possible': down_min == 0,
        'all_completions_defined': down_min > 0,
        'contributors': len(choices),
        'unknown_contributors': sum(len(p) > 1 for p in choices),
        'scope': 'Conservative outer bounds on the declared included population. Up/down are '
                 'mutually exclusive within each symbol/session. Shared prices and volumes '
                 'across sessions are relaxed; endpoints need not be jointly attainable. '
                 'Excluded members are outside this claim.',
    }


def reference_regime(days: Sequence[dict]) -> dict:
    """Independent regime arithmetic over ten consecutive XNYS count rows."""
    if len(days) < 10:
        raise ValueError('ten consecutive exchange sessions required')
    target = date.fromisoformat(days[-1]['date'])
    expected = sessions.sessions_before(target, 9) + [target]
    if [d['date'] for d in days[-10:]] != [str(d) for d in expected]:
        raise ValueError('ten consecutive exchange sessions required')
    today = days[-1]
    if today['universe'] <= 0:
        raise ValueError('no measurable symbol at target session')
    inputs = {k: today[k] for k in ('date', 'up4', 'down4', 'up50_month', 'down25_quarter')}
    for n in (5, 10):
        up = sum(d['up4'] for d in days[-n:])
        down = sum(d['down4'] for d in days[-n:])
        inputs.update({f'up4_{n}d': up, f'down4_{n}d': down,
                       f'ratio_{n}d': round(up / down, 2) if down else None})
    alarm, hot, oversold = [round(n * today['universe'] / 6500, 1) for n in (700, 20, 200)]
    r5, r10 = inputs['ratio_5d'], inputs['ratio_10d']
    checks = {
        'red_down4_alarm': today['down4'] >= alarm,
        'red_ratio_10d': r10 is not None and r10 < 1.0,
        'red_ratio_5d_selling': r5 is not None and r5 < .5 and today['down4'] > today['up4'],
        'yellow_ratio_10d': r10 is not None and r10 < 2.0,
        'yellow_up50_month_hot': today['up50_month'] > hot,
    }
    verdict = 'red' if any(v for k, v in checks.items() if k.startswith('red_')) else (
        'yellow' if any(checks.values()) else 'green')
    return {
        'verdict': verdict, 'size_multiplier': {'red': 0.0, 'yellow': .5, 'green': 1.0}[verdict],
        'active_predicates': [k for k, v in checks.items() if v], 'predicates': checks,
        'oversold_extreme': today['down25_quarter'] < oversold,
        'thresholds': {'universe': today['universe'], 'reference_universe': 6500,
                       'down4_alarm': alarm, 'up50_month_hot': hot,
                       'down25_quarter_oversold': oversold, 'ratio_10d_red': 1.0,
                       'ratio_5d_red': .5, 'ratio_10d_yellow': 2.0},
        'inputs': inputs,
    }


def _prepare(frames, target, intended, original_excluded, price_exempt, mode):
    sessions.require_session(target)
    if mode not in ('B', 'C', 'D'):
        raise ValueError('mode must be B (pinned mask), C (later readiness), or D (counterfactual)')
    names = sorted(set(intended) - {'SPY'})
    if len(intended) != len(set(intended)):
        raise ValueError('duplicate intended symbols')
    if set(frames) - set(intended) - {'SPY'}:
        raise ValueError('unexpected frame symbols outside intended population and SPY')
    excluded = set(original_excluded)
    if excluded - set(names):
        raise ValueError('original exclusions must belong to intended stock membership')
    exempt = set(price_exempt)
    rows = {name: _rows(frames.get(name), target) for name in names}
    # 65-session features on the oldest of the ten event days need 74 days.
    calendar = sessions.sessions_before(target, 73) + [target]
    masks = {}
    for day in calendar[-10:]:
        masks[day] = {}
        for name in names:
            if mode == 'B':
                masks[day][name] = (name not in excluded, 'original_excluded' if name in excluded else 'original_included')
            else:
                masks[day][name] = _eligibility(rows[name], day if mode == 'D' else target, name in exempt)
    prefixes = {name: frame.loc[[pd.Timestamp(t).date() <= target for t in frame.index]].copy()
                for name, frame in frames.items() if name in names}
    return names, rows, calendar, masks, prefixes


def reference_replay(frames: Mapping[str, pd.DataFrame], session: date, *,
                     intended: Sequence[str], source_identity: Mapping,
                     mode='B', original_excluded=(), price_exempt=()) -> dict:
    """Return JSON-ready scalar events, observed totals, masks and missingness.

    ``source_identity`` must identify the frozen input object(s), mapping and
    value basis; callers may include a per-symbol object-hash map. It is retained
    verbatim once and each event carries its digest. Original input gaps must
    not be supplied from a later acquisition under an original source identity.
    """
    import json

    if not source_identity:
        raise ValueError('a nonempty frozen-input source identity is required')
    source_hash = hashlib.sha256(json.dumps(dict(source_identity), sort_keys=True,
                                            separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    names, rows, calendar, masks, _ = _prepare(frames, session, intended, original_excluded, price_exempt, mode)
    # A separately computed value digest makes a changed prefix visible even
    # when a caller accidentally reuses its declared source identity.
    value_hashes = {
        name: hashlib.sha256(json.dumps({str(day): values for day, values in rows[name].items()},
                                       sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        for name in names
    }
    position = {day: i for i, day in enumerate(calendar)}
    events, days, daily_masks = [], [], []
    for day in calendar[-10:]:
        today_events = []
        mask = masks[day]
        for name in names:
            measured = _measure(rows[name], day, calendar, position)
            item = {'symbol': name, 'session': str(day), 'prior_session': str(sessions.previous_session(day)),
                    'source_identity_sha256': source_hash, 'included': mask[name][0],
                    'validated_prefix_sha256': value_hashes[name],
                    'population_reason': mask[name][1], **measured}
            events.append(item)
            if item['included']:
                today_events.append(item)
        daily = {'date': str(day), **{k: sum(e['events'][k] is True for e in today_events) for k in COUNTS},
                 'universe': sum(e['measured_4'] for e in today_events)}
        ma_measured = sum(e['events']['above_40ma'] is not None for e in today_events)
        daily['pct_above_40ma'] = (round(100 * sum(e['events']['above_40ma'] is True for e in today_events) / ma_measured, 1)
                                   if ma_measured else None)
        daily['unknown'] = {k: sum(e['events'][k] is None for e in today_events) for k in (*COUNTS, 'above_40ma')}
        daily['predicate_denominators'] = {k: len(today_events) - v for k, v in daily['unknown'].items()}
        days.append(daily)
        included = [s for s in names if mask[s][0]]
        daily_masks.append({'session': str(day), 'included': included, 'sha256': membership_sha256(included),
                            'excluded': {s: mask[s][1] for s in names if not mask[s][0]},
                            'reason_counts': dict(Counter(v[1] for v in mask.values()))})
    try:
        regime = reference_regime(days)
        status, error = 'PASS', None
    except ValueError as exc:
        regime, status, error = None, 'BLOCKED', str(exc)
    bounds = {str(n): coupled_ratio_bounds([e for e in events if e['session'] in {str(x) for x in calendar[-n:]}])
              for n in (5, 10)}
    unknown_target = days[-1]['unknown']
    decisive_unknown = any(e['included'] and e['events']['up4'] is None for e in events) or unknown_target['up50_month'] > 0
    return {
        'version': VERSION, 'status': status, 'error': error, 'session': str(session), 'mode': mode,
        'scope': {'B': 'pinned original population mask on the declared value basis',
                  'C': 'later values with target-day eligibility reevaluated',
                  'D': 'counterfactual per-observation-day eligibility policy'}[mode],
        'source_identity': dict(source_identity), 'source_identity_sha256': source_hash,
        'validated_prefix_sha256': value_hashes,
        'intended': names, 'intended_sha256': membership_sha256(names), 'benchmark_excluded': 'SPY',
        'input_symbols_with_no_rows': [s for s in names if not rows[s]],
        'rules': RULES, 'units': {'prices': 'USD, caller-declared adjustment', 'volume': 'shares', 'change': 'percent'},
        'calendar': {'authority': sessions.authority(), 'warmup_start': str(calendar[0]),
                     'event_sessions': [str(x) for x in calendar[-10:]]},
        'masks': daily_masks, 'events': events, 'days': days, 'regime': regime, 'ratio_bounds': bounds,
        'underlying_regime_established': regime is not None and not decisive_unknown,
        'limitations': ['Observed counts omit unknown contributions; they do not establish complete-input counts.',
                       'A supported regime describes only the declared included population, never excluded intended stocks.',
                       'Formula agreement does not establish input correctness or source fidelity.',
                       'Accepted reader review/final grade remains a separate prerequisite; no reviews or plans are created.'],
    }


def compare_replay(frames: Mapping[str, pd.DataFrame], session: date, *,
                   intended: Sequence[str], source_identity: Mapping, mode='B',
                   original_excluded=(), price_exempt=()) -> dict:
    """Reference + production on identical prefixes and explicit B/C/D masks.

    D invokes production daily_counts with each day's mask, then its regime
    over those count rows. It deliberately does not claim production snapshot
    implements this counterfactual policy.
    """
    reference = reference_replay(frames, session, intended=intended, source_identity=source_identity,
                                 mode=mode, original_excluded=original_excluded, price_exempt=price_exempt)
    from src import breadth  # deliberately confined to comparison, never the oracle

    _, _, calendar, masks, prefixes = _prepare(frames, session, intended, original_excluded, price_exempt, mode)
    production_days, failures = [], []
    for day, expected in zip(calendar[-10:], reference['days']):
        selected = {s: df for s, df in prefixes.items() if masks[day][s][0] and not df.empty}
        try:
            measured = breadth.daily_counts(selected, [day])[0]
        except (ValueError, IndexError) as exc:
            failures.append({'session': str(day), 'kind': 'production_unavailable', 'error': str(exc)})
            continue
        production_days.append(measured)
        actual = measured.to_dict()
        for field, value in actual.items():
            if value != expected[field]:
                failures.append({'session': str(day), 'field': field, 'reference': expected[field], 'production': value})
    production_regime = None
    if len(production_days) == 10:
        try:
            production_regime = breadth.regime(production_days)
        except ValueError as exc:
            failures.append({'kind': 'production_regime_unavailable', 'error': str(exc)})
    if reference['regime'] and production_regime:
        for key in ('verdict', 'size_multiplier', 'oversold_extreme', 'thresholds', 'inputs'):
            if reference['regime'][key] != production_regime[key]:
                failures.append({'field': f'regime.{key}', 'reference': reference['regime'][key],
                                 'production': production_regime[key]})
    mismatch = any('field' in failure for failure in failures)
    return {'status': 'FAIL' if mismatch else 'BLOCKED' if failures or not reference['regime'] else 'PASS',
            'reference': reference,
            'production': {'days': [d.to_dict() for d in production_days], 'regime': production_regime,
                           'implementation_sha256': hashlib.sha256(Path(breadth.__file__).read_bytes()).hexdigest()},
            'differences': failures}
