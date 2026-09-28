"""Synthetic, socket-blocked controls for the independent historical oracle."""
from datetime import date
from itertools import product

import numpy as np
import pandas as pd
import pytest

from src import sessions
from tools.historical_breadth_reference import (
    compare_replay, coupled_ratio_bounds, reference_regime, reference_replay,
)

TARGET = date(2026, 9, 25)
SOURCE = {'provider': 'synthetic', 'feed': 'synthetic', 'adjustment': 'split',
          'asof': '2026-09-25', 'object_sha256': 'synthetic-control'}


def frame(close=25., n=80, volume=200_000.):
    dates = sessions.sessions_before(TARGET, n - 1) + [TARGET]
    closes = np.full(n, close) if np.isscalar(close) else np.asarray(close, dtype=float)
    volumes = np.full(n, volume) if np.isscalar(volume) else np.asarray(volume, dtype=float)
    return pd.DataFrame({'Open': closes, 'High': closes, 'Low': closes,
                         'Close': closes, 'Volume': volumes}, index=pd.DatetimeIndex(dates))


def run(frames, **kwargs):
    return compare_replay(frames, TARGET, intended=kwargs.pop('intended', list(frames)),
                          source_identity=SOURCE, **kwargs)


def event(result, symbol='A', day=TARGET):
    return next(r for r in result['reference']['events'] if r['symbol'] == symbol and r['session'] == str(day))


def replace_bar(df, close, volume):
    df.loc[df.index[-1], ['Open', 'High', 'Low', 'Close', 'Volume']] = [close] * 4 + [volume]
    return df


def test_reference_and_production_all_columns_and_regime_agree():
    # Deterministic varied windows exercise every month/quarter/34-day/MA scan.
    frames = {
        'A': frame(np.linspace(10, 30, 80), volume=np.linspace(100_000, 300_000, 80)),
        'B': frame(np.linspace(40, 10, 80), volume=np.linspace(100_000, 300_000, 80)),
        'C': frame(np.array([25, 27, 25, 23] * 20), volume=np.linspace(100_000, 300_000, 80)),
    }
    result = run(frames)
    assert result['status'] == 'PASS', result['differences']
    ref = result['reference']
    assert ref['underlying_regime_established']
    assert len(ref['events']) == 30
    assert set(ref['regime']['predicates']) == {
        'red_down4_alarm', 'red_ratio_10d', 'red_ratio_5d_selling',
        'yellow_ratio_10d', 'yellow_up50_month_hot',
    }
    assert event(result)['source_identity_sha256'] == ref['source_identity_sha256']


@pytest.mark.parametrize(('close', 'volume', 'up', 'down'), [
    (26., 100_000, True, False), (24., 100_000, False, True),
    (26., 99_999, False, False), (25.999999, 100_000, False, False),
])
def test_exact_event_price_and_volume_boundaries(close, volume, up, down):
    result = run({'A': replace_bar(frame(volume=99_999), close, volume)})
    assert result['status'] == 'PASS', result['differences']
    assert event(result)['events']['up4'] is up
    assert event(result)['events']['down4'] is down


def test_equal_prior_volume_is_measured_false_and_benchmark_is_excluded():
    result = run({'A': replace_bar(frame(), 26, 200_000),
                  'SPY': replace_bar(frame(), 20, 999_999)})
    assert result['status'] == 'PASS'
    assert event(result)['events']['up4'] is False
    assert result['reference']['days'][-1]['universe'] == 1
    assert not any(r['symbol'] == 'SPY' for r in result['reference']['events'])
    assert result['reference']['regime']['inputs']['ratio_10d'] is None


def test_missing_prior_is_unknown_and_never_shortens_the_session_window():
    df = replace_bar(frame(), 26, 300_000).drop(pd.Timestamp(sessions.previous_session(TARGET)))
    result = run({'A': df, 'CONTROL': frame()})
    assert result['status'] == 'PASS'
    missing = event(result)
    assert missing['events']['up4'] is None
    assert missing['values']['prior_close'] is None
    assert missing['events']['up50_month'] is None
    assert result['reference']['days'][-1]['universe'] == 1
    assert not result['reference']['underlying_regime_established']
    assert result['reference']['ratio_bounds']['10']['undefined_possible']


def test_known_volume_failure_constrains_unknown_price_bounds():
    df = frame().drop(pd.Timestamp(sessions.previous_session(TARGET)))
    df.loc[df.index[-1], 'Volume'] = 99_999
    result = run({'A': df, 'CONTROL': frame()})
    assert event(result)['events']['up4'] is None
    assert event(result)['possible_up_down'] == [[0, 0]]


def test_no_warmup_does_not_turn_unknown_month_into_known_false():
    result = run({'A': frame(n=11)})
    assert result['status'] == 'PASS'
    assert event(result)['events']['up50_month'] is None
    assert event(result)['events']['above_40ma'] is None
    assert result['reference']['days'][-1]['predicate_denominators']['up50_month'] == 0
    assert result['reference']['days'][-1]['up50_month'] == 0
    assert not result['reference']['underlying_regime_established']


def test_pinned_population_does_not_drop_absent_members_or_restore_known_exclusions():
    result = run({'A': frame(), 'RECOVERED': frame()},
                 intended=['A', 'RECOVERED', 'ABSENT'], original_excluded=['RECOVERED'])
    assert result['status'] == 'PASS'
    assert not event(result, 'RECOVERED')['included']
    assert event(result, 'ABSENT')['included']
    assert event(result, 'ABSENT')['events']['up4'] is None
    assert result['reference']['input_symbols_with_no_rows'] == ['ABSENT']
    assert result['reference']['ratio_bounds']['10']['contributors'] == 20


def test_c_and_d_population_masks_preserve_target_price_policy_rounding():
    below = frame(close=2.0)
    recovered = replace_bar(below.copy(), 2.995, 300_000)
    result_c = run({'A': frame(), 'RECOVERED': recovered, 'LOW': below}, mode='C')
    result_d = run({'A': frame(), 'RECOVERED': recovered, 'LOW': below}, mode='D')
    assert result_c['status'] == result_d['status'] == 'PASS'
    assert event(result_c, 'RECOVERED')['included']
    assert event(result_c, 'RECOVERED', sessions.previous_session(TARGET))['included']
    assert not event(result_d, 'RECOVERED', sessions.previous_session(TARGET))['included']
    assert not event(result_c, 'LOW')['included']
    assert 'counterfactual' in result_d['reference']['scope']
    exempt = run({'LOW': below}, mode='C', price_exempt=['LOW'])
    assert event(exempt, 'LOW')['included']


def count_days(up=100, down=100, universe=6500):
    days = sessions.sessions_before(TARGET, 9) + [TARGET]
    return [{'date': str(d), 'up4': up, 'down4': down, 'universe': universe,
             'up50_month': 0, 'down25_quarter': 0} for d in days]


def test_ratio_of_sums_rounding_before_threshold_and_every_regime_predicate():
    days = count_days(up=99)
    days[-1]['up4'] = 105  # 996 / 1000 rounds to 1.00 before the <1 test.
    result = reference_regime(days)
    assert result['inputs']['ratio_10d'] == 1.0
    assert not result['predicates']['red_ratio_10d']
    assert result['predicates']['yellow_ratio_10d']
    days[-1]['up4'] = 104  # Python binary-float round(.995, 2) is .99.
    assert reference_regime(days)['predicates']['red_ratio_10d']
    hot = count_days(up=200)
    hot[-1]['up50_month'] = 20
    assert reference_regime(hot)['verdict'] == 'green'
    hot[-1]['up50_month'] = 21
    assert reference_regime(hot)['predicates']['yellow_up50_month_hot']
    alarm = count_days(up=200)
    alarm[-1]['down4'] = 700
    assert reference_regime(alarm)['predicates']['red_down4_alarm']
    selling = count_days(up=49)
    assert reference_regime(selling)['predicates']['red_ratio_5d_selling']
    assert reference_regime(selling)['oversold_extreme']


def test_count_rows_require_consecutive_exchange_sessions():
    days = count_days()
    days[3]['date'] = days[2]['date']
    with pytest.raises(ValueError, match='consecutive'):
        reference_regime(days)


def test_bounds_reserve_a_denominator_and_do_not_double_count_one_unknown_event():
    # A single unknown contributor can give 1/0 (undefined), 0/1 or 0/0,
    # but never the independently maximized impossible combination 1/1.
    result = coupled_ratio_bounds([{'possible_up_down': [[0, 0], [1, 0], [0, 1]]}])
    assert result['finite_ratio'] == [0., 0.]
    assert result['undefined_possible']
    choices = [[[0, 0], [1, 0], [0, 1]], [[1, 0]], [[0, 0], [0, 1]]]
    result = coupled_ratio_bounds([{'possible_up_down': pairs} for pairs in choices])
    ratios = [sum(x[0] for x in group) / sum(x[1] for x in group)
              for group in product(*choices) if sum(x[1] for x in group)]
    assert result['finite_ratio'] == [min(ratios), max(ratios)]
    with pytest.raises(ValueError, match='mutually exclusive'):
        coupled_ratio_bounds([{'possible_up_down': [[1, 1]]}])


def test_duplicate_wrong_session_unexpected_symbol_and_missing_identity_rejected():
    df = frame()
    duplicate = pd.concat([df, df.iloc[[-1]]])
    with pytest.raises(ValueError, match='duplicate session'):
        run({'A': duplicate})
    saturday = df.copy()
    saturday.index = pd.DatetimeIndex([pd.Timestamp('2026-09-19')] + list(df.index[1:]))
    with pytest.raises(ValueError, match='not an XNYS'):
        run({'A': saturday})
    with pytest.raises(ValueError, match='unexpected frame symbols'):
        run({'A': df}, intended=['B'])
    with pytest.raises(ValueError, match='source identity'):
        reference_replay({'A': df}, TARGET, intended=['A'], source_identity={})


def test_held_out_future_values_and_changed_source_identity():
    df = frame()
    baseline = run({'A': df})
    future = df.iloc[[-1]].copy() * 100
    future.index = pd.DatetimeIndex(sessions.next_sessions(TARGET, 1))
    extended = run({'A': pd.concat([df, future])})
    assert baseline == extended
    changed = reference_replay({'A': df}, TARGET, intended=['A'],
                               source_identity={**SOURCE, 'object_sha256': 'later-observation'})
    assert baseline['reference']['source_identity_sha256'] != changed['source_identity_sha256']
    assert baseline['reference']['regime'] == changed['regime']
    # The values are hashed separately from caller-supplied source metadata.
    changed_values = run({'A': replace_bar(df.copy(), 26, 300_000)})
    assert baseline['reference']['validated_prefix_sha256'] != changed_values['reference']['validated_prefix_sha256']


def test_reference_does_not_call_production_predicates(monkeypatch):
    from src import breadth

    def forbidden(*args, **kwargs):
        raise AssertionError('production predicate must not enter independent reference')

    for name in ('_measure', 'snapshot', 'daily_counts', 'ratios', 'regime', 'scaled_threshold'):
        monkeypatch.setattr(breadth, name, forbidden)
    result = reference_replay({'A': frame()}, TARGET, intended=['A'], source_identity=SOURCE)
    assert result['status'] == 'PASS'
