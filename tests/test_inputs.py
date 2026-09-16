"""Input populations, tested with real scanning and offline transports only."""
from datetime import date

import pandas as pd
import pytest

from src import market_data, pipeline, scans, universe
from tests.test_pipeline import market, claude, evening, EVENING  # noqa: F401
from tests.test_universe import company


def breakout(close=10.5, volume=150_000):
    return pd.DataFrame([
        [close / 1.05, close / 1.05, close / 1.05, close / 1.05, 50_000],
        [close / 1.05, close, close / 1.05, close, volume],
    ], columns=market_data.OHLCV, index=pd.to_datetime(['2026-09-09', '2026-09-10']))


@pytest.mark.parametrize('values,close', [({'volume': '50000'}, 10.5),
                                          ({'lastsale': '$2.90'}, 3.05)])
def test_directory_cannot_lose_a_same_session_breakout(values, close):
    frame = breakout(close)
    assert scans.burst_4pct(frame) is not None  # establish actual admission first
    symbols, _, _, _ = universe.admit([company('NEW', **values)], [])
    assert 'NEW' in symbols, 'directory metadata removed a legitimate current-session candidate'


def test_budget_unattempted_names_are_not_reported_as_requested(monkeypatch):
    monkeypatch.setattr(pipeline, 'FETCH_CHUNK', 2)
    def download(client, names, session, *args, **kwargs):
        return {n: breakout() for n in names}, market_data.DownloadStats(
            session=session, feed='sip', requested=len(names), with_bars=len(names))
    monkeypatch.setattr(market_data, 'download_bars', download)
    _, stats, _ = pipeline.fetch_universe(None, ['AAA', 'BBB', 'CCC'], date(2026, 9, 10),
                                         'sip', pipeline.RunReport(), budget_seconds=-1)
    assert stats.requested == 2, 'budget-unfetched names were never provider requests'


def test_published_run_accounts_for_all_intended_symbols(market, claude, fake_resend, tmp_path):
    rep, data, _ = evening(tmp_path, market)
    assert rep.published, rep.failure
    cov = data['run']['coverage']
    assert cov.get('intended') == len(market) + 1, 'missing population ledger, including benchmark'
    assert cov['intended'] == cov['requested'] + cov['unfetched_budget']
    assert cov['requested'] == cov['with_bars'] + cov['no_bars'] + cov['dropped']


def test_pinned_run_does_not_claim_current_directory_is_historical_membership(
        market, claude, fake_resend, tmp_path, monkeypatch):
    uni = universe.Universe(market, {}, {}, universe.SOURCE_LIVE,
                            '2026-09-15T22:00:00+00:00', {'admitted': len(market)}, 'test directory')
    monkeypatch.setattr(universe, 'build', lambda *a, **k: uni)
    rep, data, _ = evening(tmp_path, market)
    assert rep.published, rep.failure
    source = data['run']['universe']
    assert source.get('snapshot_relation') == 'after_session', 'snapshot/session relation not published'
    assert source['point_in_time_membership'] is False


@pytest.mark.parametrize('volume,matched', [(99_999, False), (100_000, True), (150_000, True)])
def test_current_session_volume_owns_the_scan_floor(volume, matched):
    df = breakout(volume=volume)
    assert df.Close.iloc[-1] / df.Close.iloc[-2] >= 1.04
    assert df.Volume.iloc[-1] > df.Volume.iloc[-2]
    assert (scans.burst_4pct(df) is not None) is matched


@pytest.mark.parametrize('close,allowed', [(2.99, False), (3.0, True), (3.05, True)])
def test_price_policy_reads_the_current_bar_after_directory_admission(close, allowed):
    symbols, names, flags, counts = universe.admit([company('NEW', lastsale='$2.90')], [])
    uni = universe.Universe(symbols, names, flags, counts=counts, source=universe.SOURCE_LIVE,
                            fetched_at=None, label='test')
    df = breakout(close)
    assert scans.burst_4pct(df), 'price policy is separate from reaction discovery'
    eligible, excluded = universe.session_eligible({'NEW': df}, uni)
    assert ('NEW' in eligible) is allowed
    assert ('NEW' in excluded) is not allowed


@pytest.mark.parametrize('values,close', [({'volume': '50000'}, 10.5), ({'lastsale': '$2.90'}, 3.05)])
def test_previously_excluded_stock_is_fetched_and_published_as_an_actual_match(
        market, claude, fake_resend, fake_alpaca, tmp_path, monkeypatch, values, close):
    fake_alpaca.add_history('NEW', breakout(close))
    selection = {}
    symbols, names, flags, counts = universe.admit([company('NEW', **values)], market, ledger=selection)
    uni = universe.Universe(symbols, names, flags, universe.SOURCE_LIVE,
                            '2026-09-10T22:00:00+00:00', counts, 'test directory', selection=selection)
    monkeypatch.setattr(universe, 'build', lambda *a, **k: uni)
    rep, data, _ = evening(tmp_path, symbols)
    assert rep.published, rep.failure
    assert any('NEW' in r.symbol_or_symbols for r in fake_alpaca.bar_requests)
    row = next(r for r in data['bursts'] if r['ticker'] == 'NEW')
    assert row['scan'] == 'burst' and row['volume'] == 150_000
    assert row['discovery']['version'] == 1


def test_capacity_and_seed_exceptions_reconcile_even_with_duplicate_and_invalid_rows(monkeypatch):
    monkeypatch.setattr(universe, 'MAX_DISCOVERY', 2)
    rows = [company('AAA'), company('AAA'), company('BBB'), company('CCC'),
            company('SEED', name='Unclassified'), company('NOPE', name='ETF'), {'symbol': []}, None]
    selection = {}
    symbols, _, _, counts = universe.admit(rows, ['SEED', 'EXTRA'], ledger=selection)
    assert symbols == ['EXTRA', 'SEED']  # no seed silently lost to capacity
    assert selection['listed'] == 8 and selection['duplicate_rows'] == 1
    assert selection['security_admitted'] == 3 and selection['security_excluded'] == 4
    assert selection['seed_overrides']['sample'] == ['SEED']
    assert selection['seed_added']['sample'] == ['EXTRA']
    assert selection['before_capacity'] == 5 and selection['capacity_excluded']['count'] == 3
    assert counts[universe.CAPACITY_REASON] == 3
    assert universe.selection_faults(selection) == []
    selection['capacity_excluded']['count'] = 2
    assert universe.selection_faults(selection)


def mixed_population():
    from src import inputs
    good = ['AAA', 'BBB', 'CCC', 'DDD', 'EEE', 'FFF']
    frames = {s: breakout() for s in good + ['SPY']}
    frames['BBB'].iloc[-1] = [9, 10, 9, 10, 150000]  # dollar only
    frames['CCC'].iloc[-1] = [9, 10.5, 9, 10.5, 150000]  # both
    for symbol in ['DDD', 'EEE', 'FFF']:
        frames[symbol].iloc[-1] = [10, 10, 10, 10, 50000]
    frames['STALE'] = breakout().iloc[:-1]
    frames['GAP'] = breakout().set_axis(pd.to_datetime(['2026-09-08', '2026-09-10']))
    frames['BAD'] = breakout()
    frames['BAD'].iloc[-1, frames['BAD'].columns.get_loc('High')] = float('nan')
    stocks = good + ['STALE', 'GAP', 'BAD', 'NONE', 'DROP', 'TAIL']
    symbols = stocks + ['SPY']
    uni = universe.build(None, explicit=stocks)
    stats = market_data.DownloadStats(session=date(2026, 9, 10), feed='sip', requested=12,
        with_bars=10, no_bars=['NONE'], dropped=1, dropped_symbols=['DROP'], unfetched=['TAIL'],
        duplicates={'AAA': 2}, batch_attempts=13)
    ready = market_data.apply_session_rules(frames, stats.session, stats)
    cov = inputs.build(uni, symbols, frames, stats, ready, stats.session, stats.session,
                       closed=False, minimum=pipeline.MIN_COVERAGE_FRACTION, benchmark='SPY')
    cov['scan_ready'] = cov['scan_unattempted'] = len(ready) - 1
    cov['reasons']['price_excluded'] = universe.population([])
    inputs.evaluated(cov)
    return uni, ready, stats, cov


def test_mixed_populations_reconcile_through_both_scans_and_quality():
    from src import inputs
    uni, ready, stats, cov = mixed_population()
    assert sorted(ready) == ['AAA', 'BBB', 'CCC', 'DDD', 'EEE', 'FFF', 'SPY']
    assert stats.stale == {'STALE': date(2026, 9, 9)}
    assert stats.gapped == {'GAP': date(2026, 9, 8)} and stats.unreadable == ['BAD']
    assert inputs.faults(cov) == []
    rows, measured, errors = pipeline.scan_frames(ready, uni, pipeline.RunReport(), ledger=cov)
    assert measured == 6 and errors == 0
    assert cov['matched'] == {'burst': 1, 'dollar': 1, 'both': 1, 'neither': 3}
    assert cov['quality_success'] == len(rows) == 3
    assert cov['acceptance']['fraction'] == .5 and cov['acceptance']['status'] == 'degraded'
    assert cov['intended'] == 13 and cov['requested'] == 12 and cov['with_bars'] == 10
    assert cov['no_bars'] == cov['dropped'] == cov['unfetched_budget'] == cov['stale'] == cov['gapped'] == cov['unreadable'] == 1
    assert cov['duplicate_symbols'] == 1 and cov['duplicate_bars'] == 2
    assert inputs.faults(cov) == []


@pytest.mark.parametrize('stage', ['scan', 'quality'])
def test_evaluation_errors_never_become_measured_nonmatches(monkeypatch, stage):
    from src import inputs, quality
    uni, ready, _, cov = mixed_population()
    monkeypatch.setattr(pipeline, 'MAX_ERROR_FRACTION', 1)
    module, name = (scans, 'scan_all') if stage == 'scan' else (quality, 'assess')
    original = getattr(module, name)
    def evaluate(frame, *a, **kw):
        if frame is ready['AAA']:
            raise ValueError('controlled failure')
        return original(frame, *a, **kw)
    monkeypatch.setattr(module, name, evaluate)
    pipeline.scan_frames(ready, uni, pipeline.RunReport(), ledger=cov)
    assert cov['errors'] == 1 and cov[stage + '_errors'] == 1
    assert cov['matched']['neither'] == 3
    assert cov['acceptance']['complete_evaluation'] is False
    assert inputs.faults(cov) == []


@pytest.mark.parametrize('field', ['requested', 'with_bars', 'no_bars', 'dropped', 'unfetched_budget',
                                 'stale', 'gapped', 'scan_ready', 'measured', 'quality_success'])
def test_any_lost_population_is_refused(field):
    from src import inputs
    _, _, _, cov = mixed_population()
    assert not inputs.faults(cov)
    cov[field] += 1
    assert inputs.faults(cov)


@pytest.mark.parametrize('stale_count,accepted', [(6, True), (7, False)])
def test_half_of_intended_stocks_is_the_publication_boundary(
        market, claude, fake_resend, fake_alpaca, tmp_path, stale_count, accepted):
    from src import inputs
    # 13 stocks plus SPY. Seven stale leaves 6/13 stocks, even though SPY
    # would incorrectly push a transport-based fraction up to exactly 50%.
    for sym in market[-stale_count:]:
        fake_alpaca.add_history(sym, fake_alpaca.history[sym], stale_sessions=1)
    rep, data, _ = evening(tmp_path, market)
    assert rep.published is accepted, rep.failure
    assert not inputs.faults(rep.input_coverage)
    if not accepted:
        assert data is None and rep.input_coverage['acceptance']['status'] == 'fail'
        assert rep.input_coverage['scan_unattempted'] == 6
        assert claude.calls == []


def test_budget_and_empty_result_are_honest_in_the_published_record(
        market, claude, fake_resend, fake_alpaca, monkeypatch, tmp_path):
    from src import inputs, report
    # First chunk contains eight quiet stocks, then the clock's budget stops
    # the remaining five stocks and benchmark from ever being requested.
    for symbol in market:
        fake_alpaca.add_history(symbol, fake_alpaca.history['BAA'])
    monkeypatch.setattr(pipeline, 'FETCH_CHUNK', 8)
    rep = pipeline.run_evening(tickers=market, docs=tmp_path / 'docs', now=EVENING, fetch_budget=-1)
    import json
    data = json.loads((tmp_path / 'docs/data.json').read_text())
    cov = data['run']['coverage']
    assert rep.published and rep.status == 'degraded', rep.failure
    assert cov['intended'] == 14 and cov['requested'] == 8 and cov['unfetched_budget'] == 6
    assert cov['acceptance']['ready_stocks'] == 8 and cov['acceptance']['intended_stocks'] == 13
    assert data['bursts'] == [] and claude.calls == []
    assert 'evaluated subset' in data['cover']['h1']
    assert '8 of 13' in data['cover']['dek'] and '6 fetch names were never attempted' in data['cover']['dek']
    assert 'evaluated subset' in report.digest_html(data)
    assert inputs.faults(cov) == []


def test_complete_empty_run_can_honestly_report_no_qualifiers(market, claude, fake_resend, fake_alpaca, tmp_path):
    for symbol in market:
        fake_alpaca.add_history(symbol, fake_alpaca.history['BAA'])
    rep, data, _ = evening(tmp_path, market)
    assert rep.published and data['bursts'] == []
    assert data['run']['coverage']['acceptance']['status'] == 'ok'
    assert data['cover']['h1'] == 'Nothing qualifies. Keep cash.'
    assert 'All 13 intended stocks' in data['cover']['dek']


def test_published_and_recovered_basis_matches_every_sdk_request(market, claude, fake_resend, fake_alpaca, tmp_path):
    import json
    from alpaca.data.enums import Adjustment
    rep, data, docs = evening(tmp_path, market)
    assert rep.published, rep.failure
    basis = data['run']['input_basis']
    assert basis['adjustment'] == 'split'
    assert all(r.adjustment is Adjustment.SPLIT and r.adjustment.value == basis['adjustment'] for r in fake_alpaca.bar_requests)
    assert all(r.feed.value == basis['feed'] for r in fake_alpaca.bar_requests)
    contexts = list((docs / 'history').glob('*/record.json'))
    assert len(contexts) == 1
    assert json.loads(contexts[0].read_text())['run']['input_basis'] == basis


@pytest.mark.parametrize('captured,relation', [('2026-09-09T22:00:00+00:00', 'before_session'),
    ('2026-09-10T22:00:00+00:00', 'same_date'), ('2026-09-15T22:00:00+00:00', 'after_session'), (None, 'unrecorded')])
def test_snapshot_time_never_claims_historical_membership(captured, relation):
    uni = universe.Universe(['AAA'], {}, {}, universe.SOURCE_CACHE, captured, {}, 'test')
    p = universe.provenance(uni, date(2026, 9, 10))
    assert p['fetched_at'] == captured and p['snapshot_relation'] == relation
    assert p['point_in_time_membership'] is False


def test_retry_failures_remain_distinct_from_empty_provider_answers(fake_alpaca, monkeypatch):
    monkeypatch.setattr(market_data.time, 'sleep', lambda *a: None)
    fake_alpaca.raise_on_bars = ConnectionError('offline fixture')
    fake_alpaca.fail_symbols = {'DROP'}
    fake_alpaca.add_history('GOOD', breakout())
    frames, stats = market_data.download_bars(market_data.get_clients(), ['GOOD', 'NONE', 'DROP'], date(2026, 9, 10), batch_size=1)
    assert list(frames) == ['GOOD']
    assert stats.no_bars == ['NONE'] and stats.dropped_symbols == ['DROP']
    assert stats.batch_attempts == 4 and stats.requested == 3
    assert stats.requested == stats.with_bars + len(stats.no_bars) + stats.dropped


def test_report_refuses_forged_coverage_or_adjustment(market, claude, fake_resend, tmp_path):
    from copy import deepcopy
    from src import report
    rep, data, _ = evening(tmp_path, market)
    assert rep.published
    corruptions = [('coverage', 'no_bars', 1), ('input_basis', 'adjustment', 'raw'),
                   ('universe', 'size', 999)]
    for block, key, value in corruptions:
        forged = deepcopy(data)
        forged['run'][block][key] = value
        with pytest.raises(ValueError):
            report.validate(forged)


def test_capacity_alone_degrades_publication(market, claude, fake_resend, tmp_path, monkeypatch):
    from dataclasses import replace
    uni = universe.build(None, explicit=market)
    selection = dict(uni.selection, before_capacity=len(market) + 1, manual_admitted=len(market) + 1,
                     capacity_excluded=universe.population(['CUT']))
    uni = replace(uni, counts={**uni.counts, universe.CAPACITY_REASON: 1}, selection=selection)
    monkeypatch.setattr(universe, 'build', lambda *a, **k: uni)
    rep, data, _ = evening(tmp_path, market)
    assert rep.published and rep.status == 'degraded'
    assert data['run']['coverage']['acceptance']['capacity_excluded'] == 1
    assert 'stocks excluded by capacity: 1' in data['cover']['dek']


def test_permanent_refusal_accounts_for_attempts_and_unrequested_tail(
        market, claude, fake_resend, fake_alpaca, tmp_path, monkeypatch):
    from src import inputs
    from tests.test_market_data import _alpaca_error
    monkeypatch.setattr(pipeline, 'FETCH_CHUNK', 1)
    fake_alpaca.raise_on_bars = _alpaca_error(403, 'forbidden')
    fake_alpaca.fail_symbols = {'ZZZ'}
    rep, data, _ = evening(tmp_path, ['AAA', 'BAA', 'BBB', 'ZZZ'])
    assert rep.failed and data is None and claude.calls == []
    cov = rep.input_coverage
    assert cov['intended'] == 5 and cov['requested'] == 4
    assert cov['with_bars'] == 3 and cov['refused'] == 1
    assert cov['unfetched_failure'] == 1 and cov['unfetched_budget'] == 0
    assert cov['dropped'] == cov['no_bars'] == 0
    assert cov['scan_unattempted'] == 3 and cov['acceptance']['fraction'] == .75
    assert cov['acceptance']['status'] == 'fail' and inputs.faults(cov) == []
