"""Input populations, tested with real scanning and offline transports only."""
import json
from datetime import date

import pandas as pd
import pytest

from src import market_data, pipeline, scans, universe
from tests.test_pipeline import market, claude, evening, EVENING  # noqa: F401
from tests.test_universe import ACQUISITION_ROWS, company


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


@pytest.mark.parametrize("include_acquisitions", [False, True], ids=["operating-control", "acquisition-exclusions"])
def test_directory_classification_precedes_fetch_without_hiding_missing_inputs(
        market, claude, fake_resend, fake_alpaca, tmp_path, monkeypatch, include_acquisitions):
    from src import inputs

    operating = market + ["STALE", "NOBAR"]
    rows = [company(symbol) for symbol in operating]
    if include_acquisitions:
        rows += ACQUISITION_ROWS
    fake_alpaca.add_history("STALE", breakout(), stale_sessions=1)
    monkeypatch.setattr(universe, "read_seed", lambda: [])
    monkeypatch.setattr(universe, "_directory", lambda *a: (rows, universe.SOURCE_LIVE, EVENING))
    monkeypatch.delenv("SCAN_UNIVERSE", raising=False)
    rep = pipeline.run_evening(docs=tmp_path / "docs", now=EVENING, dry_run=True)
    assert rep.published and rep.exit_code() == pipeline.EXIT_DEGRADED, rep.failure
    data = json.loads((tmp_path / "docs" / pipeline.DATA_FILE).read_text())
    requested = {s for request in fake_alpaca.bar_requests for s in request.symbol_or_symbols}
    assert requested == set(operating) | {"SPY"}
    run = data["run"]
    selection, cov = run["universe"]["selection"], run["coverage"]
    assert run["universe"]["size"] == len(operating)
    assert selection["intended"] == len(operating)
    assert selection["exclusions"] == (
        {"blank check company": universe.population(["BKHA", "EGHA", "HCMA"])}
        if include_acquisitions else {})
    assert cov["reasons"]["stale"] == universe.population(["STALE"])
    assert cov["reasons"]["no_bars"] == universe.population(["NOBAR"])
    assert cov["intended"] == cov["requested"] == len(operating) + 1
    assert cov["stale"] == cov["no_bars"] == 1
    assert cov["measured"] == len(market)
    assert sum(cov["matched"].values()) == len(market)
    assert cov["acceptance"]["status"] == "degraded"
    assert inputs.record_faults(run) == []
    assert fake_resend.sent == []


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


# ----------------------------------------------------- the stale tolerance ---
# A night whose ONLY gap is a small tail of stocks one session behind is not
# degraded; everything else keeps the rule above. The ledger and its
# acceptance stay exactly as built: the tolerance reads them and writes nothing.
TAPE_DATES = pd.to_datetime(['2026-09-04', '2026-09-08', '2026-09-09', '2026-09-10'])
#: a tape ending 1 Sep: six sessions before 10 Sep (7 Sep is Labor Day), one past the bound of five
FAR_DATES = pd.to_datetime(['2026-08-27', '2026-08-28', '2026-08-31', '2026-09-01'])
#: a tape ending 2 Sep: five sessions before 10 Sep across Labor Day, the furthest the bound allows;
#: counted in weekdays (7 Sep among them) it would be six, and refused
EDGE_DATES = pd.to_datetime(['2026-08-28', '2026-08-31', '2026-09-01', '2026-09-02'])
#: a tape whose last stamp is Labor Day itself: a date that is no session is never an allowed ending,
#: though a count of weekdays would take it
HOLIDAY_DATES = pd.to_datetime(['2026-09-02', '2026-09-03', '2026-09-04', '2026-09-07'])


def tape(behind=0, *, dates=TAPE_DATES):
    """A quiet four-session tape ending `behind` sessions before 10 Sep."""
    df = pd.DataFrame([[10.0, 10.2, 9.9, 10.1, 200_000]] * len(dates), columns=market_data.OHLCV, index=dates)
    return df.iloc[:len(df) - behind]


def q_names(count):
    return [f"Q{a}{b}{c}" for a in "ABCDE" for b in "ABCDEFGHIJ" for c in "ABCDEFGHIJ"][:count]


def ledger(stocks=200, *, stale=('QAAA', 'QAAB'), frames=None, capacity=0, **stats_kw):
    """A reconciled ledger over `stocks` quiet names and SPY, `stale` of them one
    session behind; `frames` replaces or adds any frame by name."""
    from src import inputs
    names = q_names(stocks)
    tapes = {s: tape(1 if s in stale else 0) for s in names + ['SPY']}
    tapes.update(frames or {})
    extra = [s for s in stats_kw.get('no_bars', []) + stats_kw.get('dropped_symbols', []) + stats_kw.get('unfetched', [])]
    uni = universe.build(None, explicit=names + extra)
    if capacity:
        uni.counts[universe.CAPACITY_REASON] = capacity
    held_back = len(stats_kw.get('unfetched', []))
    stats = market_data.DownloadStats(session=date(2026, 9, 10), feed='sip',
                                      requested=len(tapes) + len(extra) - held_back, with_bars=len(tapes),
                                      dropped=len(stats_kw.get('dropped_symbols', [])), batch_attempts=1, **stats_kw)
    ready = market_data.apply_session_rules(tapes, stats.session, stats)
    cov = inputs.build(uni, uni.symbols + ['SPY'], tapes, stats, ready, stats.session, stats.session,
                       closed=False, minimum=pipeline.MIN_COVERAGE_FRACTION, benchmark='SPY')
    cov['scan_ready'] = cov['scan_unattempted'] = cov['acceptance']['ready_stocks']
    inputs.evaluated(cov)
    return cov, stats


def endings_of(stats):
    """Where each stale frame ends, as the pipeline hands it to the tolerance."""
    return {t: (d.isoformat() if d else None) for t, d in stats.stale.items()}


ARCHIVED = object()   # the code's own bound, unless a test names another (None included)


def tolerance_of(cov, stats, fraction=0.01, held=(), sessions_max=ARCHIVED):
    from src import inputs
    return inputs.stale_tolerance(cov, fraction, names=sorted(stats.stale), benchmark='SPY', held=held,
                                  names_max=pipeline.STALE_NAMES_MAX, endings=endings_of(stats),
                                  sessions_max=pipeline.STALE_SESSIONS_MAX if sessions_max is ARCHIVED else sessions_max)


def with_scan_error(cov):
    cov['scan_errors'], cov['errors'], cov['scan_unattempted'] = 1, 1, cov['scan_unattempted'] - 1
    return cov


NAN_HIGH = tape()
NAN_HIGH.iloc[-1, NAN_HIGH.columns.get_loc('High')] = float('nan')


@pytest.mark.parametrize('build,fraction,held,verdict,reasons', [
    (lambda: ledger(), 0.01, (), 'tolerated', []),
    (lambda: ledger(stale=('QAAA', 'QAAB', 'QAAC')), 0.01, (), 'not_tolerated', ['over_limit']),
    # 270 stocks: 1% is 2.7, floored to 2; a ceiling or a rounding would admit 3
    (lambda: ledger(270, stale=('QAAA', 'QAAB', 'QAAC')), 0.01, (), 'not_tolerated', ['over_limit']),
    # a frame two sessions back is within the bound of five; one six back is not
    (lambda: ledger(stale=('QAAA',), frames={'QAAB': tape(2)}), 0.01, (), 'tolerated', []),
    (lambda: ledger(stale=('QAAA',), frames={'QAAB': tape(dates=FAR_DATES)}), 0.01, (), 'not_tolerated', ['behind_more']),
    (lambda: ledger(stale=('QAAA',), frames={'QAAB': tape(dates=EDGE_DATES)}), 0.01, (), 'tolerated', []),
    (lambda: ledger(stale=('QAAA',), frames={'QAAB': tape(dates=HOLIDAY_DATES)}), 0.01, (), 'not_tolerated', ['behind_more']),
    (lambda: ledger(stale=('QAAA',), frames={'QAAB': tape(dates=pd.DatetimeIndex(['2026-09-08', pd.NaT]))}),
     0.01, (), 'not_tolerated', ['behind_more']),
    (lambda: ledger(no_bars=['QZZZ']), 0.01, (), 'not_tolerated', ['other_exceptions']),
    (lambda: ledger(dropped_symbols=['QZZZ']), 0.01, (), 'not_tolerated', ['other_exceptions']),
    (lambda: ledger(unfetched=['QZZZ']), 0.01, (), 'not_tolerated', ['other_exceptions']),
    (lambda: ledger(frames={'QAAC': tape(dates=TAPE_DATES.delete(2))}), 0.01, (), 'not_tolerated', ['other_exceptions']),
    (lambda: ledger(frames={'QAAC': NAN_HIGH}), 0.01, (), 'not_tolerated', ['other_exceptions']),
    (lambda: ledger(capacity=1), 0.01, (), 'not_tolerated', ['other_exceptions']),
    (lambda: (with_scan_error(ledger()[0]), ledger()[1]), 0.01, (), 'not_tolerated', ['other_exceptions']),
    # the benchmark is outside the stock count, as it is outside acceptance: a
    # stale SPY beside two stale stocks is a tail of two against a limit of two
    (lambda: ledger(stale=('QAAA', 'QAAB', 'SPY')), 0.01, (), 'tolerated', []),
    (lambda: ledger(stale=('QAAA', 'QAAB', 'QAAC', 'SPY')), 0.01, (), 'not_tolerated', ['over_limit']),
    (lambda: ledger(), 0.01, ('QAAA',), 'not_tolerated', ['open_plan']),
    (lambda: ledger(stale=()), 0.01, (), 'complete', []),
    (lambda: ledger(), None, (), 'not_tolerated', ['over_limit']),
], ids=['two-of-200', 'three-of-200', 'three-of-270', 'two-sessions-back', 'six-sessions-back', 'five-sessions-back-across-a-holiday',
        'ending-on-a-holiday', 'unreadable-stamp', 'no-bars',
        'dropped', 'unfetched', 'gapped', 'unreadable-bar', 'capacity', 'scan-error', 'benchmark-outside-the-count',
        'benchmark-and-three-stocks', 'open-plan', 'complete', 'no-fraction'])
def test_stale_tolerance_reads_only_the_ledger(build, fraction, held, verdict, reasons):
    from src import inputs
    cov, stats = build()
    assert inputs.faults(cov) == [], 'the case must reconcile, or it tests a broken ledger'
    before = json.dumps(cov, sort_keys=True, default=str)
    tol = tolerance_of(cov, stats, fraction, held)
    assert (tol['verdict'], tol['reasons']) == (verdict, reasons), tol
    assert json.dumps(cov, sort_keys=True, default=str) == before, 'the tolerance wrote the ledger'
    assert cov['acceptance']['status'] == ('ok' if verdict == 'complete' else 'degraded')
    assert tol['names'] == sorted(stats.stale) and tol['held'] == sorted(held)
    assert tol['endings'] == endings_of(stats) and tol['sessions_max'] == pipeline.STALE_SESSIONS_MAX
    assert tol['stale_stocks'] == cov['stale'] - int('SPY' in stats.stale)


@pytest.mark.parametrize('sessions_max,verdict', [(5, 'tolerated'), (2, 'tolerated'), (1, 'not_tolerated'),
                                                  (0, 'not_tolerated'), (None, 'not_tolerated')])
def test_the_session_bound_is_the_archived_number(sessions_max, verdict):
    """A frame two sessions back is tolerated under a bound of two or more and
    refused under one; a bound of zero or none allows no stale frame at all."""
    cov, stats = ledger(stale=('QAAA',), frames={'QAAB': tape(2)})
    tol = tolerance_of(cov, stats, sessions_max=sessions_max)
    assert tol['verdict'] == verdict and tol['sessions_max'] == sessions_max, tol
    assert ('behind_more' in tol['reasons']) == (verdict == 'not_tolerated')


@pytest.mark.parametrize('stocks,fraction,limit', [(100, 0.29, 29), (270, 0.01, 2), (99, 0.01, 0),
                                                   (100, 0.01, 1), (4793, 0.01, 47), (200, 0, 0), (200, None, 0)])
def test_the_stale_limit_is_the_fraction_floored_in_exact_arithmetic(stocks, fraction, limit):
    """0.29 * 100 is 28.999999999999996 in binary floating point; floored that
    way the limit would be 28 where the rule says 29."""
    from src import inputs
    assert inputs.stale_limit(stocks, fraction) == limit


def test_the_tolerance_names_its_stocks_only_up_to_its_bound():
    from src import inputs
    cov, stats = ledger(stale=('QAAA', 'QAAB', 'QAAC'))

    def named(names_max):
        return inputs.stale_tolerance(cov, 0.01, names=sorted(stats.stale), benchmark='SPY', names_max=names_max,
                                      endings=endings_of(stats), sessions_max=pipeline.STALE_SESSIONS_MAX)
    carried = named(3)
    assert carried['names'] == ['QAAA', 'QAAB', 'QAAC']
    assert carried['endings'] == {'QAAA': '2026-09-09', 'QAAB': '2026-09-09', 'QAAC': '2026-09-09'}
    over = named(2)
    assert over['names'] is None and over['endings'] is None, 'the endings go with the names, carried or not'


ARCHIVED_VERSION = object()   # the code's own tolerance version, unless a test names another (None: archived none)


def checked(cov, tol, names_max=pipeline.STALE_NAMES_MAX, archived=ARCHIVED_VERSION, plan_tickers=frozenset()):
    """The tolerance's faults as validate() asks for them, over a run whose
    sentence is the block's and whose shortfall, if any, is named. ``archived``
    is the tolerance version the record's rules archived; None archives none,
    as every record from before the first sessions did."""
    from src import inputs
    run = {'coverage': cov, 'input_tolerance': tol, 'problems': [{'kind': 'coverage_thin'}]}
    tol['sentence'] = inputs.coverage_sentence(run)
    rules = {'stale_tolerance_fraction': 0.01, 'stale_names_max': names_max,
             'stale_sessions_max': pipeline.STALE_SESSIONS_MAX}
    if archived is not None:
        rules['input_tolerance_version'] = inputs.TOLERANCE_VERSION if archived is ARCHIVED_VERSION else archived
    return inputs.tolerance_faults(run, rules, set(plan_tickers))


def test_endings_go_with_the_names_and_an_unreadable_ending_is_one():
    """A block past the names it carries carries no endings either, and the
    validator says so on its own; a frame whose last stamp is unreadable is
    recorded as None and accepted, the ledger counting it under 'None'."""
    from src import inputs
    cov, stats = ledger()
    tol = inputs.stale_tolerance(cov, 0.01, names=sorted(stats.stale), benchmark='SPY', names_max=1,
                                 endings=endings_of(stats), sessions_max=pipeline.STALE_SESSIONS_MAX)
    assert (tol['names'], tol['endings']) == (None, None)
    assert checked(cov, tol, names_max=1) == []
    assert checked(cov, dict(tol, endings=endings_of(stats)), names_max=1) == ['input tolerance endings are not its names']
    cov, stats = ledger(stale=('QAAA',), frames={'QAAB': tape(dates=pd.DatetimeIndex(['2026-09-08', pd.NaT]))})
    tol = tolerance_of(cov, stats)
    assert tol['endings'] == {'QAAA': '2026-09-09', 'QAAB': None} and 'None' in cov['sessions']['latest_bar_dates']
    assert checked(cov, tol) == []


# ------------------- a first session: a frame with no bar before the session ---
# LCU on 19 October 2026 (Lion Copper's first Nasdaq session) and NORD on 30
# October each degraded a night alone, read as "missing the previous session":
# a frame with no bar before the session at all has no previous session to
# miss. Version 3 of the tolerance names such a stock and counts it beside the
# stale ones against the same limit; a frame with a real hole -- an earlier
# bar, but not the session before -- is the gap it always was.
#: a tape whose first bar is the evaluated session
FIRST_DATES = pd.to_datetime(['2026-09-10'])
#: a tape with earlier bars and none on 9 Sep: a hole
HOLE_DATES = TAPE_DATES.delete(2)


def tolerance_first(cov, stats, fraction=0.01, held=(), version=None):
    from src import inputs
    kw = {} if version is None else {'version': version}
    return inputs.stale_tolerance(cov, fraction, names=sorted(stats.stale), benchmark='SPY', held=held,
                                  names_max=pipeline.STALE_NAMES_MAX, endings=endings_of(stats),
                                  sessions_max=pipeline.STALE_SESSIONS_MAX,
                                  first=inputs.first_sessions(stats, 'SPY'), **kw)


def unreadable_before(column=None, stamp=False):
    """A tape whose rows before 10 Sep are all present and none readable: each
    lacks `column`, or (``stamp``) carries a date that cannot be read."""
    df = tape()
    if column:
        df.loc[df.index[:-1], column] = float('nan')
    if stamp:
        df.index = pd.DatetimeIndex([pd.NaT] * (len(df) - 1) + [df.index[-1]])
    return df


def test_first_sessions_are_the_gapped_frames_with_no_bar_before_the_session():
    from src import inputs
    cov, stats = ledger(stale=(), frames={'QAAC': tape(dates=FIRST_DATES), 'QAAD': tape(dates=HOLE_DATES),
                                          'SPY': tape(dates=FIRST_DATES)})
    assert inputs.faults(cov) == []
    assert stats.gapped == {'QAAC': date(2026, 9, 10), 'QAAD': date(2026, 9, 8), 'SPY': date(2026, 9, 10)}
    assert stats.first_session == ['QAAC', 'SPY']
    assert inputs.first_sessions(stats, 'SPY') == ['QAAC']
    assert inputs.first_sessions(stats, 'QAAC') == ['SPY']


@pytest.mark.parametrize('frame', [unreadable_before('Volume'), unreadable_before('Close'), unreadable_before(stamp=True)],
                         ids=['no-volume-before', 'no-close-before', 'unreadable-stamps-before'])
def test_a_frame_whose_earlier_rows_cannot_be_read_is_a_gap_not_a_first_session(frame):
    """drop_gapped() asks for a MEASURABLE bar before the session and maps a frame
    with none to its newest bar, the session itself -- the same date a first
    session has. A frame whose earlier rows are there but unreadable (or whose
    stamps cannot be read, so could be any date) has history the provider sent;
    it is the gap it always was, never a stock whose history begins tonight."""
    from src import inputs
    cov, stats = ledger(stale=(), frames={'QAAC': frame})
    assert stats.gapped == {'QAAC': date(2026, 9, 10)}, 'the map alone cannot tell it from a first session'
    assert stats.first_session == [] and inputs.first_sessions(stats, 'SPY') == []
    tol = tolerance_first(cov, stats)
    assert (tol['verdict'], tol['reasons'], tol['first_sessions'], tol['first_session_stocks']) == \
        ('not_tolerated', ['other_exceptions'], [], 0)


@pytest.mark.parametrize('build,held,version,verdict,reasons,first', [
    (lambda: ledger(stale=(), frames={'QAAC': tape(dates=FIRST_DATES)}), (), None, 'tolerated', [], ['QAAC']),
    (lambda: ledger(stale=('QAAA',), frames={'QAAC': tape(dates=FIRST_DATES)}), (), None, 'tolerated', [], ['QAAC']),
    # the limit counts both: two stale stocks and one first session are three against two
    (lambda: ledger(frames={'QAAC': tape(dates=FIRST_DATES)}), (), None, 'not_tolerated', ['over_limit'], ['QAAC']),
    (lambda: ledger(stale=(), frames={'QAAC': tape(dates=FIRST_DATES), 'QAAD': tape(dates=HOLE_DATES)}),
     (), None, 'not_tolerated', ['other_exceptions'], ['QAAC']),
    (lambda: ledger(stale=(), frames={'QAAC': tape(dates=FIRST_DATES)}), ('QAAC',), None,
     'not_tolerated', ['open_plan'], ['QAAC']),
    # the benchmark's first session is no stock's: its gap is the gap it always was
    (lambda: ledger(stale=('QAAA',), frames={'SPY': tape(dates=FIRST_DATES)}), (), None,
     'not_tolerated', ['other_exceptions'], []),
    # version 2, the rule as records made under it read it: the frame is a gap
    (lambda: ledger(stale=(), frames={'QAAC': tape(dates=FIRST_DATES)}), (), 2,
     'not_tolerated', ['other_exceptions'], None),
], ids=['first-alone', 'stale-and-first', 'two-stale-and-first', 'first-and-a-hole', 'first-under-an-open-plan',
        'benchmark-first', 'version-two'])
def test_a_first_session_is_counted_beside_the_stale_tail(build, held, version, verdict, reasons, first):
    from src import inputs
    cov, stats = build()
    assert inputs.faults(cov) == [], 'the case must reconcile, or it tests a broken ledger'
    before = json.dumps(cov, sort_keys=True, default=str)
    tol = tolerance_first(cov, stats, held=held, version=version)
    assert (tol['verdict'], tol['reasons']) == (verdict, reasons), tol
    assert json.dumps(cov, sort_keys=True, default=str) == before, 'the tolerance wrote the ledger'
    assert cov['acceptance']['status'] == 'degraded'
    if first is None:
        assert tol['version'] == 2 and 'first_sessions' not in tol and 'first_session_stocks' not in tol
    else:
        assert tol['version'] == inputs.TOLERANCE_VERSION
        assert (tol['first_sessions'], tol['first_session_stocks']) == (first, len(first))


def test_the_first_session_sentence_names_the_stock_and_why():
    from src import inputs
    cov, stats = ledger(stale=(), frames={'QAAC': tape(dates=FIRST_DATES)})
    tol = tolerance_first(cov, stats)
    sentence = inputs.coverage_sentence({'coverage': cov, 'input_tolerance': tol})
    assert sentence.endswith(
        " 1 returned frame (QAAC) had no bar before 2026-09-10 in this run's request window: every row the "
        "provider returned for it is dated 2026-09-10, as on an exchange listing's first day, so there is no "
        "session before to measure its move against, and it is not a measured non-match. That is within this run's input tolerance of 2 stocks (1% of the intended stocks), so this "
        "frame does not degrade the run."), sentence
    assert 'stale' not in sentence and 'missing the previous session' not in sentence


def test_the_first_session_sentence_beside_a_stale_tail_says_both():
    from src import inputs
    cov, stats = ledger(stale=('QAAA',), frames={'QAAC': tape(dates=FIRST_DATES)})
    sentence = inputs.coverage_sentence({'coverage': cov, 'input_tolerance': tolerance_first(cov, stats)})
    assert ("1 returned frame had no bar for 2026-09-10, ending on the previous session, 2026-09-09. "
            "Its 2026-09-10 input is unknown, not a measured non-match. 1 returned frame (QAAC) had no bar before "
            "2026-09-10 in this run's request window") in sentence, sentence
    assert sentence.endswith(
        f"each stale frame ending within the {pipeline.STALE_SESSIONS_MAX} sessions before, so these frames do "
        "not degrade the run; the next session's run, when it publishes, reads every session the stale frame "
        "missed again."), sentence


def test_a_hole_beside_a_first_session_is_counted_as_the_one_gap_it_is():
    from src import inputs
    cov, stats = ledger(stale=(), frames={'QAAC': tape(dates=FIRST_DATES), 'QAAD': tape(dates=HOLE_DATES)})
    sentence = inputs.coverage_sentence({'coverage': cov, 'input_tolerance': tolerance_first(cov, stats)})
    assert "Outside this run's input tolerance (2 stocks, 1%" in sentence, sentence
    assert sentence.endswith("other gaps beside the stale frames (missing the previous session: 1)."), sentence


@pytest.mark.parametrize('build', [
    lambda: ledger(), lambda: ledger(stale=('QAAA',), frames={'QAAB': tape(2)}),
    lambda: ledger(stale=('QAAA', 'QAAB', 'QAAC')), lambda: ledger(frames={'QAAC': tape(dates=HOLE_DATES)}),
    lambda: (with_scan_error(ledger()[0]), ledger()[1]),
], ids=['tolerated', 'two-back', 'over', 'a-hole', 'scan-error'])
def test_without_a_first_session_version_three_reads_as_version_two(build):
    """A night with no first session says what it said before the rule: the
    sentence a version-2 block wrote, word for word, and the same verdict."""
    from src import inputs
    cov, stats = build()
    three, two = tolerance_first(cov, stats), tolerance_first(cov, stats, version=2)
    assert three['first_session_stocks'] == 0 and three['first_sessions'] == []
    assert {k: three[k] for k in two if k != 'version'} == {k: v for k, v in two.items() if k != 'version'}
    assert (three['version'], two['version']) == (inputs.TOLERANCE_VERSION, 2)
    assert (inputs.coverage_sentence({'coverage': cov, 'input_tolerance': three})
            == inputs.coverage_sentence({'coverage': cov, 'input_tolerance': two}))


def test_the_validator_holds_first_sessions_to_the_gapped_frames():
    cov, stats = ledger(stale=('QAAA',), frames={'QAAC': tape(dates=FIRST_DATES)})
    tol = tolerance_first(cov, stats)
    assert checked(cov, dict(tol)) == []
    assert checked(cov, dict(tol, first_sessions=['QAAD'])) == \
        ['input tolerance first sessions are not the gapped population the ledger counted']
    # a count past the ledger's gapped frames: named, and read no further (a re-derivation over it
    # would only repeat it, or raise and be called malformed)
    assert checked(cov, dict(tol, first_sessions=['QAAC', 'QAAD'], first_session_stocks=2)) == \
        ['input tolerance first sessions are not a count of the gapped frames']
    assert checked(cov, dict(tol, first_sessions=['QAAC', 'QAAC'], first_session_stocks=2)) == \
        ['input tolerance first sessions are not a count of the gapped frames']
    assert checked(cov, dict(tol, first_session_stocks=0)) == \
        ['input tolerance first sessions are not the stocks it counted']
    # a shape no later check can read is named for what it is, never "malformed"
    for shape in (5, 'QAAC', {'QAAC': 1}, [1]):
        assert checked(cov, dict(tol, first_sessions=shape)) == \
            ['input tolerance first sessions are not the stocks it counted'], shape
    for count in ('1', 1.0, [1], -1):
        assert checked(cov, dict(tol, first_session_stocks=count)) == \
            ['input tolerance first sessions are not a count of the gapped frames'], count
    assert checked(cov, dict(tol, first_sessions=None)) == \
        ['input tolerance drops a first-session membership it could carry']
    assert checked(cov, dict(tol, first_session_stocks=True)) == \
        ['input tolerance first sessions are not a count of the gapped frames']
    del tol['first_sessions']
    assert checked(cov, tol) == ['input tolerance block is malformed']


def test_the_validator_never_takes_the_benchmark_as_a_first_session():
    cov, stats = ledger(stale=('QAAA',), frames={'SPY': tape(dates=FIRST_DATES)})
    tol = tolerance_first(cov, stats)
    assert tol['verdict'] == 'not_tolerated' and checked(cov, dict(tol)) == []
    # the forged block re-derives -- SPY counted away from the gaps, one stale and one first within two --
    # so the benchmark clause alone refuses it
    forged = dict(tol, first_sessions=['SPY'], first_session_stocks=1, verdict='tolerated', reasons=[])
    assert checked(cov, forged) == ['input tolerance first sessions are not the stocks it counted']


def test_the_validator_holds_an_open_plans_first_session():
    cov, stats = ledger(stale=(), frames={'QAAC': tape(dates=FIRST_DATES)})
    tol = tolerance_first(cov, stats)
    assert checked(cov, dict(tol), plan_tickers={'QAAC'}) == \
        ['input tolerance does not hold the open model plans among the stocks it names']
    held = tolerance_first(cov, stats, held=('QAAC',))
    assert checked(cov, dict(held), plan_tickers={'QAAC'}) == []
    assert checked(cov, dict(held, held=['QAAZ']), plan_tickers={'QAAC'}) == [
        'input tolerance holds a stock it does not name',
        'input tolerance does not hold the open model plans among the stocks it names']


@pytest.mark.parametrize('version,archived,faults', [
    (2, None, []), (3, ARCHIVED_VERSION, []),
    (2, ARCHIVED_VERSION, ['input tolerance version or verdict unknown']),
    (3, None, ['input tolerance version or verdict unknown']),
    (3, 4, ['input tolerance version or verdict unknown']),
    (3, '3', ['input tolerance version or verdict unknown']),
], ids=['two-under-unversioned-rules', 'three-under-its-rules', 'two-under-versioned-rules',
        'three-under-unversioned-rules', 'an-unknown-archived-version', 'a-version-that-is-not-a-number'])
def test_a_block_is_held_to_the_version_its_rules_archived(version, archived, faults):
    cov, stats = ledger()
    assert checked(cov, tolerance_first(cov, stats, version=version), archived=archived) == faults


def test_a_second_version_block_names_no_first_session_whatever_it_carries():
    """A version-2 block counts no first session: carrying the fields is a
    fault, and the mail names none from one, as the page does not."""
    from src import inputs, report
    cov, stats = ledger(stale=('QAAA',), frames={'QAAC': tape(dates=FIRST_DATES)})
    two = tolerance_first(cov, stats, version=2)
    assert 'first_sessions' not in two and checked(cov, dict(two), archived=None) == []
    for extra in ({'first_sessions': ['QAAC']}, {'first_session_stocks': 1}, {'first_sessions': [], 'first_session_stocks': 0}):
        assert checked(cov, dict(two, **extra), archived=None) == \
            ['input tolerance carries first sessions its version does not'], extra
    run = {'input_tolerance': dict(two, first_sessions=['QAAC'], first_session_stocks=1)}
    assert not inputs.first_session_version(run['input_tolerance'])
    assert 'No bar before' not in report._inputs_block(run)
    three = dict(tolerance_first(cov, stats), first_sessions=['QAAC'])
    assert 'No bar before 2026-09-10 in the request window: QAAC.' in report._inputs_block({'input_tolerance': three})


LONG_TAIL = tuple(q_names(pipeline.STALE_NAMES_MAX + 1))   # one more stale stock than a block names


@pytest.mark.parametrize('stale,gaps,said,tells', [
    (LONG_TAIL + ('SPY',), {}, 1, True),                       # not ready, and no other gap could hold it: stale
    (LONG_TAIL, {}, 0, True),                                  # ready: not stale
    (LONG_TAIL, {'no_bars': ['QZZZ']}, 0, True),               # ready beside another gap: still not stale
    (LONG_TAIL + ('SPY',), {'no_bars': ['QZZZ']}, 1, False),   # not ready beside another gap: the block's count is read
], ids=['benchmark-stale', 'benchmark-ready', 'benchmark-ready-beside-a-gap', 'benchmark-stale-beside-a-gap'])
def test_a_tail_too_long_to_name_counts_the_benchmark_off_the_ledger(stale, gaps, said, tells):
    """A block past the names it carries keeps no membership, but the ledger
    still says whether the benchmark is stale: the block the run writes is
    accepted, and a count that moves the benchmark in or out of the stocks is
    refused wherever the ledger can tell."""
    from src import inputs
    cov, stats = ledger(len(LONG_TAIL) + 2, stale=stale, **gaps)
    assert inputs.faults(cov) == [], 'the case must reconcile, or it tests a broken ledger'
    tol = tolerance_of(cov, stats)
    assert tol['names'] is None and tol['stale_stocks'] == cov['stale'] - said
    assert checked(cov, tol) == [], 'the validator refuses the block the run wrote'

    def faults_at(stale_stocks):
        return checked(cov, dict(tol, stale_stocks=stale_stocks))
    refused = ['input tolerance does not re-derive from the ledger']
    # the other reading of the benchmark: refused where the ledger can tell, accepted where it cannot
    assert faults_at(cov['stale'] - (1 - said)) == (refused if tells else [])
    assert faults_at(cov['stale'] - 2) == refused, 'no ledger has two benchmarks'


@pytest.mark.parametrize('build,fraction,says,never', [
    # within the tolerance: the stale frames do not degrade the run -- never "the run is
    # not degraded", which another problem on the same night can make false
    (lambda: ledger(), 0.01, ["2 returned frames had no bar for 2026-09-10, each ending on the previous session, "
                              "2026-09-09", "within this run's stale tolerance of 2 stocks (1% of the intended stocks), "
                              f"each ending within the {pipeline.STALE_SESSIONS_MAX} sessions before, "
                              "so the stale frames do not degrade the run; the next session's run, when it publishes, "
                              "reads every session they missed again."], ["run is not degraded"]),
    # one frame two sessions back: the dates are each said, never "each ending on the previous session", and it is within the bound
    (lambda: ledger(stale=('QAAA',), frames={'QAAB': tape(2)}), 0.01,
     ["2 returned frames had no bar for 2026-09-10, ending 1 on 2026-09-08, 1 on 2026-09-09",
      "within this run's stale tolerance"], ["each ending on the previous session", "Outside"]),
    # one frame six sessions back is past the bound, and the sentence names the bound and the date
    (lambda: ledger(stale=('QAAA',), frames={'QAAB': tape(dates=FAR_DATES)}), 0.01,
     ["ending 1 on 2026-09-01, 1 on 2026-09-09",
      f"not every stale frame ends within the {pipeline.STALE_SESSIONS_MAX} sessions before 2026-09-10 on a readable date"],
     ["each ending on the previous session", "do not degrade"]),
    # one stale stock against a limit of zero reads in the singular
    (lambda: ledger(99, stale=('QAAA',)), 0.01, ["1 stale stock is more than the limit",
                                                 f"(0 stocks, 1%, within {pipeline.STALE_SESSIONS_MAX} sessions)"],
     ["1 stale stocks"]),
    # a scan error is not a missing input, and the sentence says which gap it was
    (lambda: (with_scan_error(ledger()[0]), ledger()[1]), 0.01,
     ["other gaps beside the stale frames (scan or checklist errors: 1)"], ["missing too"]),
    # the archived fraction as it is, never re-rounded to a whole percent
    (lambda: ledger(), 0.005, [f"tolerance (1 stock, 0.5%, within {pipeline.STALE_SESSIONS_MAX} sessions)",
                               "2 stale stocks are more than the limit"], [" 0%", "1%"]),
], ids=['tolerated', 'two-sessions-back', 'six-sessions-back', 'one-stock', 'scan-error', 'half-a-percent'])
def test_the_tolerance_sentence_says_only_what_the_ledger_shows(build, fraction, says, never):
    from src import inputs
    cov, stats = build()
    tol = tolerance_of(cov, stats, fraction)
    sentence = inputs.coverage_sentence({'coverage': cov, 'input_tolerance': tol})
    for words in says:
        assert words in sentence, (words, sentence)
    for words in never:
        assert words not in sentence, (words, sentence)


# -------------------------------------- the tolerance over a whole night ----
WIDE = 187   # quiet names beside the 13 of `market`: a 200-stock night, whose limit is 2


@pytest.fixture
def wide(market, fake_alpaca, seed):
    """`market` and 187 quiet names: 200 intended stocks, so the stale limit is two."""
    from tests.synthetic import make_ohlcv
    names = q_names(WIDE)
    for i, name in enumerate(names):
        fake_alpaca.add_history(name, make_ohlcv('flat', seed=[seed, 500 + i], days=260))
    return market + names


def behind(fake_alpaca, names, sessions=1):
    for name in names:
        fake_alpaca.add_history(name, fake_alpaca.history[name], stale_sessions=sessions)


def test_a_stale_only_night_is_ok_and_still_counts_every_missing_stock(
        wide, claude, fake_resend, fake_alpaca, tmp_path):
    from src import inputs, report
    rep0, complete, _ = evening(tmp_path / 'complete', wide)
    behind(fake_alpaca, ['QAAA', 'QAAB'])
    rep, data, _ = evening(tmp_path / 'stale', wide)
    assert rep.exit_code() == 0 and rep.status == 'ok', rep.problems
    run = data['run']
    assert run['status'] == 'ok' and run['problems'] == []
    cov = run['coverage']
    assert cov['acceptance']['status'] == 'degraded' and cov['stale'] == 2 and inputs.faults(cov) == []
    assert cov['reasons']['stale'] == universe.population(['QAAA', 'QAAB'])
    tol = run['input_tolerance']
    assert (tol['verdict'], tol['names'], tol['limit'], tol['held']) == ('tolerated', ['QAAA', 'QAAB'], 2, [])
    assert data['nights'] == [{'session': '2026-09-10', 'status': 'ok', 'published_at': data['generated']}]
    dek = data['cover']['dek']
    assert ('2 returned frames had no bar for 2026-09-10, each ending on the previous session, 2026-09-09' in dek
            and "within this run's stale tolerance of 2 stocks" in dek), dek
    assert tol['sentence'] == inputs.coverage_sentence(run) and tol['sentence'] in dek
    report.validate(data)
    # the tolerance moved the run's status and nothing it decided
    assert rep0.exit_code() == 0 and complete['run']['input_tolerance']['verdict'] == 'complete'
    assert data['trades'] == complete['trades'] == ['AAA'] and run['graded'] == complete['run']['graded']
    assert data['breadth']['regime']['verdict'] == complete['breadth']['regime']['verdict']

    def decided(record):
        return [(b['ticker'], b['grade'], b['grade_mechanical'], (b.get('plan') or {}).get('limit'),
                 (b.get('plan') or {}).get('stop'), (b.get('plan') or {}).get('shares')) for b in record['bursts']]
    assert decided(data) == decided(complete)


@pytest.mark.parametrize('arrange,reasons', [
    (lambda fake: behind(fake, ['QAAA', 'QAAB', 'QAAC']), ['over_limit']),
    (lambda fake: behind(fake, ['QAAA'], sessions=pipeline.STALE_SESSIONS_MAX + 1), ['behind_more']),
    (None, ['other_exceptions']),
], ids=['three-stale', 'past-the-session-bound', 'and-a-name-with-no-bars'])
def test_past_the_stale_tolerance_the_night_is_degraded(wide, claude, fake_resend, fake_alpaca, tmp_path,
                                                         arrange, reasons):
    from src import report
    tickers = wide
    if arrange is None:
        behind(fake_alpaca, ['QAAA'])
        tickers = wide + ['NOBAR']   # registered with no history: the provider returns nothing for it
    else:
        arrange(fake_alpaca)
    rep, data, _ = evening(tmp_path, tickers)
    assert rep.exit_code() == pipeline.EXIT_DEGRADED and rep.status == 'degraded', rep.problems
    thin = [p for p in data['run']['problems'] if p['kind'] == 'coverage_thin']
    assert len(thin) == 1 and thin[0]['message'].startswith(f"stale tolerance not met ({', '.join(reasons)})"), thin
    tol = data['run']['input_tolerance']
    assert tol['verdict'] == 'not_tolerated' and tol['reasons'] == reasons, tol
    assert "Outside this run's stale tolerance" in tol['sentence']
    if 'behind_more' in reasons:
        from src import sessions
        far = sessions.sessions_before(date(2026, 9, 10), pipeline.STALE_SESSIONS_MAX + 1)[0].isoformat()
        assert 'each ending on the previous session' not in tol['sentence'] and f'1 on {far}' in tol['sentence']
        assert tol['endings'] == {'QAAA': far}
    report.validate(data)


def test_a_frame_two_sessions_behind_is_within_the_bound(wide, claude, fake_resend, fake_alpaca, tmp_path):
    """The first live night under the tolerance (7 Oct 2026) had one of sixteen
    stale frames two sessions behind and was degraded for it; a thin name skips
    days. Within the bound the night is ok, and the record says where the frame
    ends so the next session's run can read both sessions it missed."""
    from src import report, sessions
    behind(fake_alpaca, ['QAAA'], sessions=2)
    rep, data, _ = evening(tmp_path, wide)
    assert rep.status == 'ok' and data['run']['problems'] == [], rep.problems
    tol = data['run']['input_tolerance']
    second = sessions.sessions_before(date(2026, 9, 10), 2)[0].isoformat()
    assert (tol['verdict'], tol['names'], tol['endings'], tol['sessions_max']) == \
        ('tolerated', ['QAAA'], {'QAAA': second}, pipeline.STALE_SESSIONS_MAX), tol
    assert f'ending 1 on {second}' in tol['sentence'] and 'each ending within' in tol['sentence'], tol['sentence']
    assert data['cover']['dek'].endswith(tol['sentence']) or tol['sentence'] in data['cover']['dek']
    report.validate(data)


def test_a_stale_benchmark_beside_a_tolerable_tail_is_tolerated(wide, claude, fake_resend, fake_alpaca, tmp_path):
    """SPY feeds only the scorecard's comparison line and is outside the stock
    denominator; a stale SPY alone was never a degraded night, and beside a
    tail of two it neither counts as a third stock nor blocks the tolerance."""
    from src import report
    behind(fake_alpaca, ['QAAA', 'QAAB', 'SPY'])
    rep, data, _ = evening(tmp_path, wide)
    assert rep.status == 'ok' and data['run']['problems'] == [], rep.problems
    tol = data['run']['input_tolerance']
    assert (tol['verdict'], tol['stale'], tol['stale_stocks'], tol['names']) == ('tolerated', 3, 2, ['QAAA', 'QAAB', 'SPY'])
    report.validate(data)


def test_a_tolerated_tail_on_a_night_degraded_otherwise_never_says_the_run_is_not_degraded(
        wide, claude, fake_resend, fake_alpaca, tmp_path):
    from src import report
    behind(fake_alpaca, ['QAAA'])
    claude.set_error(RuntimeError('upstream connect error'))
    rep, data, _ = evening(tmp_path, wide)
    assert rep.status == 'degraded' and [p['kind'] for p in data['run']['problems']] == ['claude_unavailable']
    tol = data['run']['input_tolerance']
    assert tol['verdict'] == 'tolerated' and 'do not degrade the run' in tol['sentence']
    assert 'run is not degraded' not in tol['sentence'] and 'run is not degraded' not in data['cover']['dek']
    report.validate(data)


@pytest.mark.parametrize('shape', ['first', 'hole', 'unreadable'],
                         ids=['history-begins-tonight', 'a-hole-control', 'unreadable-history-control'])
def test_a_stock_whose_history_begins_tonight_does_not_degrade_the_night(
        wide, claude, fake_resend, fake_alpaca, tmp_path, shape):
    """The 19 October 2026 revision (LCU) and 30 October (NORD): one stock new
    to the night's directory, the only frame the night could not measure, and
    the night degraded for "missing the previous session". Served with its
    session bar alone it is named as a first session and the night is ok;
    served with a hole before its session bar, or with every earlier bar
    unreadable, it is the gap it always was."""
    from src import inputs, report
    first = shape == 'first'
    history = fake_alpaca.history['QAAC']
    if first:
        fake_alpaca.add_history('QAAC', history.iloc[-1:])
    elif shape == 'hole':
        fake_alpaca.add_history('QAAC', history, gap_before_session=True)
    else:
        unread = history.copy()
        unread.iloc[:-1, unread.columns.get_loc('Volume')] = float('nan')
        fake_alpaca.add_history('QAAC', unread)
    rep, data, _ = evening(tmp_path, wide)
    run, tol = data['run'], data['run']['input_tolerance']
    cov = run['coverage']
    assert cov['gapped'] == 1 and cov['reasons']['gapped']['sample'] == ['QAAC']
    assert cov['acceptance']['status'] == 'degraded' and cov['stale'] == 0
    assert data['rules']['pipeline']['input_tolerance_version'] == inputs.TOLERANCE_VERSION
    assert tol['version'] == inputs.TOLERANCE_VERSION
    if first:
        assert rep.status == 'ok' and run['problems'] == [], rep.problems
        assert (tol['verdict'], tol['first_sessions'], tol['first_session_stocks']) == ('tolerated', ['QAAC'], 1)
        assert "1 returned frame (QAAC) had no bar before 2026-09-10 in this run's request window" in tol['sentence']
        assert tol['sentence'] in data['cover']['dek']
        assert 'No bar before 2026-09-10 in the request window: QAAC.' in report.digest_html(data)
    else:
        assert rep.status == 'degraded', rep.problems
        assert (tol['verdict'], tol['reasons'], tol['first_sessions']) == ('not_tolerated', ['other_exceptions'], [])
        thin = [p['message'] for p in run['problems'] if p['kind'] == 'coverage_thin']
        assert len(thin) == 1 and thin[0].startswith('stale tolerance not met (other_exceptions)'), thin
        assert 'No bar before' not in report.digest_html(data)
    assert data['trades'] == ['AAA']
    report.validate(data)


NEXT_EVENING = EVENING + pd.Timedelta(days=1)   # Friday 11 Sep, the session after


@pytest.mark.parametrize('late,status', [('AAA', 'degraded'), ('QAAA', 'ok')], ids=['under-an-open-plan', 'control'])
def test_a_stale_frame_under_an_open_model_plan_keeps_the_night_degraded(
        wide, claude, fake_resend, fake_alpaca, tmp_path, late, status):
    from src import record, report
    rep, data, _ = evening(tmp_path, wide)
    assert rep.status == 'ok' and data['trades'] == ['AAA'], rep.problems
    behind(fake_alpaca, [late])
    rep, data, _ = evening(tmp_path, wide, now=NEXT_EVENING)
    assert rep.status == status, rep.problems
    tol = data['run']['input_tolerance']
    assert tol['names'] == [late] and tol['stale'] == 1
    held = {p['ticker']: p['status'] for p in data['open_plans']}
    assert 'AAA' in held and held['AAA'] not in record.FINISHED
    if status == 'degraded':
        assert (tol['verdict'], tol['reasons'], tol['held']) == ('not_tolerated', ['open_plan'], ['AAA'])
        assert [p['message'] for p in data['run']['problems'] if p['kind'] == 'coverage_thin'] == \
            ['stale frames under open model plans: AAA']
    else:
        assert (tol['verdict'], tol['held']) == ('tolerated', []) and data['run']['problems'] == []
    report.validate(data)


def test_a_frame_with_no_earlier_bar_under_an_open_model_plan_keeps_the_night_degraded(
        wide, claude, fake_resend, fake_alpaca, tmp_path):
    """A plan made on a ticker's earlier bars, whose frame tonight carries the
    session's bar alone: the provider returned none of the history the plan
    was made on, so the plan cannot be walked. It is held as a stale frame is,
    and the problem names it for what it is, never as stale."""
    from src import inputs, record, report
    rep, data, _ = evening(tmp_path, wide)
    assert rep.status == 'ok' and data['trades'] == ['AAA'], rep.problems
    fake_alpaca.add_history('AAA', fake_alpaca.history['AAA'].iloc[-1:])
    rep, data, _ = evening(tmp_path, wide, now=NEXT_EVENING)
    assert rep.status == 'degraded', rep.problems
    tol = data['run']['input_tolerance']
    assert (tol['version'], tol['stale'], tol['first_sessions'], tol['first_session_stocks']) == \
        (inputs.TOLERANCE_VERSION, 0, ['AAA'], 1)
    assert (tol['verdict'], tol['reasons'], tol['held']) == ('not_tolerated', ['open_plan'], ['AAA'])
    held = {p['ticker']: p['status'] for p in data['open_plans']}
    assert 'AAA' in held and held['AAA'] not in record.FINISHED
    assert [p['message'] for p in data['run']['problems'] if p['kind'] == 'coverage_thin'] == \
        ['frames with no bar before the session under open model plans: AAA']
    report.validate(data)


@pytest.mark.parametrize('finished', ['stopped', 'not_filled'])
def test_a_stale_frame_under_a_finished_plan_is_not_held(
        wide, claude, fake_resend, fake_alpaca, tmp_path, monkeypatch, finished):
    """A plan the walk has already finished has nothing left to walk tonight, so
    its stock's stale frame is the tail like any other: the pipeline does not
    hold it, and validate() does not ask for it to be held."""
    from src import pipeline, record, report
    assert finished in record.FINISHED
    rep, data, _ = evening(tmp_path, wide)
    assert data['trades'] == ['AAA'], rep.problems
    behind(fake_alpaca, ['AAA'])
    walk = record.open_plans

    def ended(*args, **kwargs):
        rows = walk(*args, **kwargs)
        for row in rows:
            if row.get('ticker') == 'AAA':
                row['status'] = finished
        return rows
    monkeypatch.setattr(pipeline.record, 'open_plans', ended)
    rep, data, _ = evening(tmp_path, wide, now=NEXT_EVENING)
    held = {p['ticker']: p['status'] for p in data['open_plans']}
    assert held.get('AAA') == finished, held
    tol = data['run']['input_tolerance']
    assert (tol['names'], tol['held'], tol['verdict']) == (['AAA'], [], 'tolerated'), tol
    assert rep.status == 'ok' and data['run']['problems'] == [], rep.problems
    report.validate(data)


def test_the_tolerance_moves_the_status_and_no_decision(wide, claude, fake_resend, fake_alpaca, tmp_path, monkeypatch):
    """The same tolerated night under a tolerance of zero: only its status, its
    problems, its night row, its tolerance block and its rules digest differ."""
    behind(fake_alpaca, ['QAAA', 'QAAB'])
    rep, shipped, docs = evening(tmp_path / 'shipped', wide)
    monkeypatch.setattr(pipeline, 'STALE_TOLERANCE_FRACTION', 0)
    monkeypatch.setitem(pipeline.RULES, 'pipeline.stale_tolerance_fraction', 0)
    rep0, zero, docs0 = evening(tmp_path / 'zero', wide)
    assert (rep.status, rep0.status) == ('ok', 'degraded')
    assert [p['kind'] for p in zero['run']['problems']] == ['coverage_thin']
    assert shipped['app']['rules_version'] != zero['app']['rules_version']
    assert shipped['run']['input_tolerance']['limit'] == 2 and zero['run']['input_tolerance']['limit'] == 0

    # everything else is equal once the identities that digest the rules are set aside
    identity = {'evidence', 'evidence_ref', 'rules_version', 'replay_rules_version', 'context_sha256'}

    def plain(node):
        if isinstance(node, dict):
            return {k: plain(v) for k, v in node.items() if k not in identity}
        return [plain(v) for v in node] if isinstance(node, list) else node

    def decided(data):
        data = plain(json.loads(json.dumps(data)))
        for key in ('app', 'rules', 'generated', 'nights'):
            data.pop(key)
        for key in ('status', 'problems', 'input_tolerance', 'elapsed_seconds', 'published_at', 'fetch_seconds'):
            data['run'].pop(key)
        # what the reads cost is accounting, not a decision: the second run of the
        # double reads the cached prefix the first run wrote, as the API would
        data['run'].pop('reader_usage')
        for b in data['bursts']:
            b.pop('reader_usage', None)
        data['cover'].pop('dek')
        # observations are keyed by signal identity, which carries the rules digest
        data['observations']['signals'] = sorted(data['observations']['signals'].values(), key=json.dumps)
        return data
    assert decided(shipped) == decided(zero)
    picks = [plain(json.loads((d / 'picks.json').read_text())['picks']) for d in (docs, docs0)]
    assert picks[0] == picks[1] and picks[0]


def test_the_tolerance_functions_spell_no_bare_number():
    """The literal guard test_plan keeps over plan.py, over the functions this
    contract added: every number they compare against is a named constant."""
    import ast
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / 'src'
    scope = {'followup.py': None, 'reader_coverage.py': None,
             'inputs.py': {'stale_limit', 'allowed_endings', 'stale_tolerance', '_count', '_percent', '_ending', '_why',
                           '_tolerance_clause', 'coverage_sentence', '_benchmark_stale', 'tolerance_faults',
                           'seed_stale', 'seed_stale_sentence', 'seed_stale_faults', '_canonical'}}
    literals, seen = {}, set()
    for name, functions in scope.items():
        for node in ast.walk(ast.parse((root / name).read_text())):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (functions is None or node.name in functions):
                seen.add((name, node.name))
                for inner in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                    if isinstance(inner, ast.Constant) and isinstance(inner.value, (int, float)) \
                            and not isinstance(inner.value, bool) and inner.value not in (0, 1, 2, 100):
                        literals.setdefault(f'{name}:{node.name}', []).append(inner.value)
    assert {('inputs.py', f) for f in scope['inputs.py']} <= seen, 'a named function was renamed away from the guard'
    assert sum(1 for n, _ in seen if n == 'followup.py') >= 8 and sum(1 for n, _ in seen if n == 'reader_coverage.py') >= 8
    assert not literals, literals


# --- the stale stocks the seed alone asked for ---------------------------------
RETIRE = ' A seed name is asked for again every night until it is retired from data/symbols.txt by hand.'


def _tol(names, benchmark='SPY', stale_stocks=None):
    if stale_stocks is None:
        stale_stocks = None if names is None else len([n for n in names if n != benchmark])
    return {'names': names, 'stale_stocks': stale_stocks, 'benchmark': benchmark}


def _selection(added, kind='directory'):
    return {'kind': kind, 'seed_added': universe.population(added)}


@pytest.mark.parametrize('tol,selection,expect', [
    (_tol(['QAAA', 'QAAB']), _selection(['QAAA']),
     dict(membership='complete', seed_added=1, seed_named=1, names=['QAAA'], reason=None)),
    (_tol(['QAAA', 'QAAB']), _selection([]),
     dict(membership='complete', seed_added=0, seed_named=0, names=[], reason=None)),
    (_tol(['SPY', 'QAAA']), _selection(['QAAA', 'SPY']),
     dict(membership='complete', seed_added=2, seed_named=2, names=['QAAA'], reason=None)),
    (_tol(['QAAC', 'QAAB', 'QAAA']), _selection(['QAAC', 'QAAA']),
     dict(membership='complete', seed_added=2, seed_named=2, names=['QAAA', 'QAAC'], reason=None)),
    (_tol(['QAAA']), _selection([f'Q{i:03d}' for i in range(universe.SAMPLE_LIMIT + 1)]),
     dict(membership='sampled', seed_added=universe.SAMPLE_LIMIT + 1, seed_named=universe.SAMPLE_LIMIT,
          names=None, reason='seed_additions_sampled')),
    (_tol(None, stale_stocks=150), _selection(['QAAA']),
     dict(membership='complete', seed_added=1, seed_named=1, names=None, reason='stale_names_not_carried')),
    (_tol(['QAAA']), {},
     dict(membership='unavailable', seed_added=None, seed_named=None, names=None, reason='no_directory_selection')),
    # a directory selection whose seed list is not a population (a bare list of names) is
    # one the ledger's own reconciliation refuses (universe.selection_faults); the join
    # still says it could not be made rather than indexing into it
    (_tol(['QAAA']), {'kind': 'directory', 'seed_added': ['QAAA']},
     dict(membership='unavailable', seed_added=None, seed_named=None, names=None, reason='no_directory_selection')),
    (_tol(['QAAA']), universe.manual_selection(['QAAA', 'QAAB'], 'seed'),
     dict(membership='unavailable', seed_added=None, seed_named=None, names=None, reason='seed_universe')),
    (_tol(['QAAA']), universe.manual_selection(['QAAA', 'QAAB'], 'explicit'),
     dict(membership='unavailable', seed_added=None, seed_named=None, names=None, reason='explicit_universe')),
], ids=['one-seed-only', 'none-seed-only', 'the-benchmark-is-never-a-stock', 'two-seed-only-in-symbol-order', 'seed-list-sampled',
        'stale-names-not-carried', 'no-directory-selection', 'a-directory-selection-without-its-seed-list',
        'the-seed-alone', 'an-explicit-list'])
def test_seed_stale_joins_the_records_own_lists_only_when_both_are_complete(tol, selection, expect):
    from src import inputs
    block = inputs.seed_stale(tol, selection)
    assert {k: block[k] for k in expect} == expect
    assert block['version'] == inputs.SEED_STALE_VERSION and block['stale_stocks'] == tol['stale_stocks']
    assert block['sentence'] == inputs.seed_stale_sentence(block)
    assert block['membership'] in inputs.SEED_STALE_MEMBERSHIPS
    assert block['reason'] is None or block['reason'] in inputs.SEED_STALE_REASONS


@pytest.mark.parametrize('block,says', [
    (dict(stale_stocks=0, names=[], reason=None), ''),
    (dict(stale_stocks=0, names=None, reason='no_directory_selection'), ''),
    (dict(stale_stocks=1, names=['WBD'], reason=None),
     'The stale stock is on the seed alone, not in the directory this run selected from: WBD.' + RETIRE),
    (dict(stale_stocks=20, names=['WBD'], reason=None),
     '1 of the 20 stale stocks is on the seed alone, not in the directory this run selected from: WBD.' + RETIRE),
    (dict(stale_stocks=3, names=['AAA', 'BBB'], reason=None),
     '2 of the 3 stale stocks are on the seed alone, not in the directory this run selected from: AAA, BBB.' + RETIRE),
    (dict(stale_stocks=1, names=[], reason=None),
     'The stale stock is in the directory this run selected from, not on the seed alone.'),
    (dict(stale_stocks=2, names=[], reason=None),
     'None of the 2 stale stocks is on the seed alone; each is in the directory this run selected from.'),
    (dict(stale_stocks=2, names=None, reason='no_directory_selection'),
     'Whether a stale stock is on the seed alone is not recorded: this run recorded no directory selection.'),
    (dict(stale_stocks=2, names=None, reason='seed_universe'),
     "Whether a stale stock is on the seed alone is not recorded: this run's universe was the seed file alone, "
     'so whether the directory still lists a stale stock was not read.'),
    (dict(stale_stocks=2, names=None, reason='explicit_universe'),
     "Whether a stale stock is on the seed alone is not recorded: this run's universe was an explicit list, "
     'not a directory selection.'),
    (dict(stale_stocks=2, names=None, reason='seed_additions_sampled', seed_added=9, seed_named=8),
     'Whether a stale stock is on the seed alone is not recorded: the selection names 8 of its 9 seed additions.'),
    (dict(stale_stocks=2, names=None, reason='stale_names_not_carried'),
     'Whether a stale stock is on the seed alone is not recorded: the record does not name its stale stocks.'),
], ids=['nothing-stale', 'nothing-stale-unknown', 'the-one-stale-stock', 'one-of-twenty', 'two-of-three',
        'the-one-is-listed', 'none-of-two', 'no-directory', 'the-seed-alone', 'an-explicit-list', 'sampled', 'not-carried'])
def test_the_seed_stale_sentence_says_only_what_the_lists_show(block, says):
    from src import inputs
    assert inputs.seed_stale_sentence({'seed_added': None, 'seed_named': None, **block}) == says


def _directory_universe(symbols, seeds):
    """A directory that lists every symbol but the seeds, so the seeds are seed-only additions."""
    rows = [company(s) for s in symbols if s not in seeds]
    ledger = {}
    admitted, names, flags, counts = universe.admit(rows, list(seeds), ledger=ledger)
    assert sorted(admitted) == sorted(symbols) and universe.selection_faults(ledger) == []
    return universe.Universe(admitted, names, flags, universe.SOURCE_LIVE, '2026-09-10T22:00:00+00:00', counts,
                             'test directory', selection=ledger, price_exempt=tuple(seeds))


def test_a_seed_only_stale_stock_is_named_through_the_run(wide, claude, fake_resend, fake_alpaca, tmp_path, monkeypatch):
    """Over a directory selection whose one seed addition is a stale frame, the
    run names it as the seed's own, the mail prints the sentence beside the
    stale names, and the validator re-derives the block from the record."""
    from src import inputs, report
    from tests.test_report import _mail_text
    uni = _directory_universe(wide, ['QAAA'])
    assert uni.selection['seed_added'] == universe.population(['QAAA'])
    monkeypatch.setattr(universe, 'build', lambda *a, **k: uni)
    behind(fake_alpaca, ['QAAA', 'QAAB'])
    rep, data, _ = evening(tmp_path, wide)
    assert rep.exit_code() == 0, rep.problems
    run = data['run']
    assert run['universe']['selection']['seed_added'] == universe.population(['QAAA'])
    assert run['input_tolerance']['names'] == ['QAAA', 'QAAB']
    assert run['seed_stale'] == {
        'version': inputs.SEED_STALE_VERSION, 'membership': 'complete', 'seed_added': 1, 'seed_named': 1,
        'stale_stocks': 2, 'names': ['QAAA'], 'reason': None,
        'sentence': '1 of the 2 stale stocks is on the seed alone, not in the directory this run selected from: QAAA.' + RETIRE}
    assert data['rules']['pipeline']['seed_stale_version'] == inputs.SEED_STALE_VERSION
    # the ledger's sample bound decides complete against sampled, so the record archives it
    assert data['rules']['universe']['sample_limit'] == universe.SAMPLE_LIMIT == len(universe.population([f'Q{i:03d}' for i in range(universe.SAMPLE_LIMIT + 1)])['sample'])
    report.validate(data)
    assert 'Without a 2026-09-10 bar: QAAA, QAAB. ' + run['seed_stale']['sentence'] in _mail_text(data)
    # the block moved no decision: the night is the same night as without a seed addition
    assert run['status'] == 'ok' and run['input_tolerance']['verdict'] == 'tolerated' and data['trades'] == ['AAA']


def test_a_night_with_nothing_stale_has_a_seed_block_with_nothing_to_say(wide, claude, fake_resend, fake_alpaca, tmp_path):
    from src import inputs
    rep, data, _ = evening(tmp_path, wide)
    block = data['run']['seed_stale']
    assert rep.exit_code() == 0 and block['stale_stocks'] == 0 and block['sentence'] == ''
    assert block['membership'] == 'unavailable' and block['names'] is None and block['reason'] == 'explicit_universe'
    assert inputs.seed_stale_faults(data['run'], data['rules']['pipeline']) == []
