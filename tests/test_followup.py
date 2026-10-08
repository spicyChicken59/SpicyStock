"""The next night's read of the previous night's stale stocks: last night's
missing bars, read again from tonight's own fetch by the evening's own rules
for that session, with no provider call of their own -- accounting about a
previous publication, never a signal."""
from __future__ import annotations

import gzip
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from src import followup, market_data, pipeline, provenance, quality_ledger, record, report, sessions, universe
from tests.test_inputs import behind, q_names, wide  # noqa: F401
from tests.test_pipeline import market, claude, evening, EVENING  # noqa: F401

DAY = date(2026, 9, 9)          # last night's session
TONIGHT = date(2026, 9, 10)     # the session that reads it again
BEFORE = sessions.previous_session(DAY)   # 8 Sep: the session before last night's
ROOT = Path(__file__).resolve().parents[1]
BOUND = pipeline.STALE_SESSIONS_MAX


def faults_of(block, session=TONIGHT, names_max=100, sessions_max=BOUND):
    return followup.shape_faults(block, session, names_max, sessions_max)


def tape(end=TONIGHT, n=30, close=50.0, volume=200_000.0):
    """A quiet tape of `n` XNYS sessions ending on `end`: no scan fires on it."""
    idx = pd.DatetimeIndex(sessions.sessions_before(end + timedelta(days=1), n))
    return pd.DataFrame([[close, close * 1.002, close * 0.998, close, volume]] * n,
                        columns=market_data.OHLCV, index=idx)


def with_bar(df, day, row):
    df = df.copy()
    df.loc[pd.Timestamp(day)] = row
    return df


def live(symbols):
    return universe.Universe(list(symbols), {}, {s: set() for s in symbols}, universe.SOURCE_LIVE, None,
                             {'admitted': len(symbols)}, 'test directory')


def explicit(symbols):
    return universe.build(None, explicit=list(symbols))


def read(frames, uni=None, stocks=None):
    stocks = sorted(stocks if stocks is not None else frames)
    rows = followup._read(stocks, frames, DAY, uni or live(stocks), 'SPY', 'sip')
    return {r['ticker']: r for r in rows}


PLACEHOLDER = [50.0, 50.0, 50.0, 50.0, 0.0]
DOLLAR = [50.0, 51.6, 49.9, 51.5, 300_000.0]   # a $1.50 body on 300k shares, +3%: the dollar scan, not the 4% one


@pytest.mark.parametrize('frame,outcome,volume,flat,route', [
    # the provider's late placeholder: one price, no volume, still a session behind tonight
    (with_bar(tape(end=DAY)[:-1], DAY, PLACEHOLDER), 'no_match', 0, True, None),
    # the placeholder, then tonight's quiet bar: read at ITS session, never at tonight's
    (with_bar(with_bar(tape(end=DAY)[:-1], DAY, PLACEHOLDER), TONIGHT, [50.0, 50.1, 49.9, 50.0, 5_000.0]),
     'no_match', 0, True, None),
    (with_bar(tape(end=DAY)[:-1], DAY, DOLLAR), 'match', 300_000, False, 'dollar'),
    # a hole before the late bar: the session rules refuse it, so it is not measured
    (tape(end=DAY).drop(pd.Timestamp(sessions.previous_session(DAY))), 'unmeasurable', 200_000, False, None),
    (tape(end=sessions.previous_session(DAY)), 'still_missing', None, None, None),
], ids=['placeholder-still-behind', 'placeholder-then-ready', 'dollar-match', 'hole-before', 'still-missing'])
def test_the_late_bar_is_read_at_its_own_session(frame, outcome, volume, flat, route):
    row = read({'LATE': frame})['LATE']
    assert (row['outcome'], row['volume'], row['flat'], row['route']) == (outcome, volume, flat, route), row


def coiled(end=DAY):
    """The watchlist's own coiled tape, dated to end on ``end``: the evening's
    setting-up list takes it."""
    from tests.test_watchlist import coil
    df = coil()
    return df.set_axis(pd.DatetimeIndex(sessions.sessions_before(end + timedelta(days=1), len(df))))


def test_a_late_bar_the_setting_up_list_would_have_taken_is_a_match():
    """The previous publication listed setting-up names as well as bursts: a
    late bar the evening's own watchlist would have listed is a match too."""
    row = read({'COIL': coiled()})['COIL']
    assert (row['outcome'], row['route']) == ('match', 'setting_up'), row
    # the anticipation scan alone is not the list: GRAL's retained placeholder
    # passes the scan and the list's own stages refuse it
    address, day = RETAINED['GRAL']
    frame = provenance.frame_of(json.loads(gzip.decompress((ROOT / 'docs' / 'evidence' / f'{address}.json.gz').read_bytes())))
    upto = followup._through(frame, date.fromisoformat(day))
    from src import scans, watchlist
    assert scans.anticipation(upto) is not None and not watchlist.build({'GRAL': upto})['top']
    assert followup._read(['GRAL'], {'GRAL': frame}, date.fromisoformat(day), explicit(['GRAL']), 'SPY', 'sip')[0]['outcome'] == 'no_match'


def test_the_late_bar_meets_the_session_close_price_policy():
    cheap = with_bar(tape(end=DAY, close=2.5)[:-1], DAY, [2.5, 2.5, 2.5, 2.5, 0.0])
    assert read({'LATE': cheap})['LATE']['outcome'] == 'price_excluded'
    # a selection the policy exempts reads the same bar as a measured non-match
    assert read({'LATE': cheap}, explicit(['LATE']))['LATE']['outcome'] == 'no_match'


def test_a_stock_tonight_did_not_return_or_select_stays_unknown():
    rows = read({'HERE': tape(end=DAY)}, live(['HERE', 'GONE']), stocks=['HERE', 'GONE', 'LEFT'])
    assert rows['GONE'] == {'ticker': 'GONE', 'session': '2026-09-09', 'outcome': 'no_frame', 'volume': None, 'flat': None, 'route': None}
    assert rows['LEFT'] == {'ticker': 'LEFT', 'session': '2026-09-09', 'outcome': 'not_selected', 'volume': None, 'flat': None, 'route': None}


# ----------------------------------------------- every session a stock missed ---
@pytest.mark.parametrize('ending,sessions_max,expected', [
    (BEFORE, BOUND, [DAY]),                                              # one behind: the previous session alone
    (sessions.previous_session(BEFORE), BOUND, [BEFORE, DAY]),           # two behind: both missed sessions
    (sessions.sessions_before(DAY, 4)[0], BOUND, sessions.sessions_before(TONIGHT, 4)),   # four behind: all four
    (sessions.sessions_before(DAY, 9)[0], BOUND, sessions.sessions_before(TONIGHT, BOUND)),   # past the bound: the most recent five
    (None, BOUND, [DAY]),                                                # an unreadable or unrecorded ending: the previous session
    (DAY, BOUND, [DAY]),                                                 # an ending not before the previous session: that session
    (sessions.previous_session(BEFORE), 0, [DAY]),                       # no bound reads one session, never none
], ids=['one-behind', 'two-behind', 'four-behind', 'past-the-bound', 'unknown-ending', 'ending-at-previous', 'zero-bound'])
def test_the_sessions_a_stock_missed_run_from_its_last_bar_to_the_previous_session(ending, sessions_max, expected):
    assert followup.missed_sessions(ending, DAY, sessions_max) == expected


def test_a_stock_two_sessions_behind_is_read_at_both_sessions_it_missed():
    """Last night's record says QAAA's frame ended two sessions before last
    night; tonight's frame carries the provider's placeholder at both sessions
    it missed: two readings, one per session, each at its own session."""
    frame = with_bar(with_bar(tape(end=BEFORE)[:-1], BEFORE, PLACEHOLDER), DAY, DOLLAR)
    prev = previous(input_tolerance={'names': ['QAAA'], 'endings': {'QAAA': sessions.previous_session(BEFORE).isoformat()}})
    block = followup.night(prev, {'QAAA': frame}, TONIGHT, live(['QAAA']), closed=False, benchmark='SPY',
                           names_max=100, feed='sip', sessions_max=BOUND)
    assert (block['status'], block['for_session'], block['sessions'], block['stocks'], block['count']) == \
        ('applied', DAY.isoformat(), [BEFORE.isoformat(), DAY.isoformat()], 1, 2), block
    assert [(r['session'], r['outcome'], r['route']) for r in block['rows']] == \
        [(BEFORE.isoformat(), 'no_match', None), (DAY.isoformat(), 'match', 'dollar')]
    assert block['matched'] == ['QAAA'] and followup.matches_named(block) == f'QAAA ({DAY.isoformat()}, $ scan)'
    assert faults_of(block) == []
    assert block['sentence'] == (
        f"The {DAY} publication's 1 stock without a bar, read again from this run's split-adjusted fetch at each of "
        f"the 2 sessions missed ({BEFORE} to {DAY}), one reading per stock and session, 2 readings in all: 2 readings "
        f"now carry the session's bar (1 with zero volume); QAAA ({DAY}, $ scan) would have been listed in the "
        "publication for that session, which did not include it; 1 would not have been listed. A late bar is the "
        "bar the provider served at this run's check; it never becomes a signal, plan or ticket."), block['sentence']


def test_a_first_version_membership_is_read_at_the_previous_session_alone():
    """A publication from the tolerance's first version named its stale stocks
    and not where each frame ended: the previous session is the one read, as
    that version read it, whatever the frame shows further back."""
    frame = with_bar(with_bar(tape(end=BEFORE)[:-1], BEFORE, DOLLAR), DAY, PLACEHOLDER)
    block = night(previous(input_tolerance={'names': ['QAAA']}), frames={'QAAA': frame})
    assert (block['status'], block['sessions'], block['count'], block['matched']) == ('applied', [DAY.isoformat()], 1, []), block
    assert block['rows'][0]['outcome'] == 'no_match' and faults_of(block) == []


# The six frames the evidence archive already retains for a stock that was a
# session behind on one night and printed later: each carries, at that
# session, the provider's late bar -- one price, no volume.
RETAINED = {
    'GRAL': ('e2b41c0064ac884f709ef5d47f9c66d41d62b6e714d5e21ed1fb388a2d922222', '2026-09-23'),
    'GURE': ('e3f7bd83c5bc72e608554f8c545c2f5b82d73609655d0ea3c5e2e8c002a5410d', '2026-09-17'),
    'HBNB': ('6ecf67e9367a0c76c3eff82a431b7b6b1ace653f6319588ee1f046cc959a58d0', '2026-09-25'),
    'LBTYB': ('2ca7c14610321a4d8e11179216190dbeef0ffba8deceed3984e9b6d416772861', '2026-09-17'),
    'SANG': ('da52615b71588267cd0be5456a06ea9a421576d249b2d87101825d91f0051f43', '2026-09-25'),
    'SPHL': ('6b236571ab6c77d91fd2402e524ccd259488bbfe841fec366ab617bb4184457b', '2026-09-22'),
}


@pytest.mark.parametrize('ticker', sorted(RETAINED))
def test_retained_provider_placeholders_match_nothing(ticker):
    address, day = RETAINED[ticker]
    obj = json.loads(gzip.decompress((ROOT / 'docs' / 'evidence' / f'{address}.json.gz').read_bytes()))
    assert provenance.digest(obj) == address, 'the retained object is not the one its name addresses'
    frame = provenance.frame_of(obj)
    stale = date.fromisoformat(day)
    assert market_data.last_bar_date(frame) > stale, 'the frame must carry bars after its late one'
    rows = followup._read([ticker], {ticker: frame}, stale, explicit([ticker]), 'SPY', 'sip')
    assert [(r['outcome'], r['volume'], r['flat']) for r in rows] == [('no_match', 0, True)], rows


# ------------------------------------------------------------- whole nights ---
NEXT_EVENING = EVENING + timedelta(days=1)   # Friday 11 Sep


def late(fake_alpaca, name, rows, *, still_behind):
    """Append `rows` to `name`'s history: the double then serves them as the
    sessions after the last one it served for it."""
    df = fake_alpaca.history[name].copy()
    for row in rows:
        df.loc[df.index[-1] + pd.Timedelta(days=1)] = row
    fake_alpaca.add_history(name, df, stale_sessions=1 if still_behind else 0)


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_the_next_night_records_last_nights_stale_stocks(wide, claude, fake_resend, fake_alpaca, tmp_path):
    behind(fake_alpaca, ['QAAA', 'QAAB'])
    rep, first, docs = evening(tmp_path, wide)
    assert rep.status == 'ok' and first['run']['input_tolerance']['names'] == ['QAAA', 'QAAB'], rep.problems
    # the rolling index is rewritten every night; the records it indexes never are
    kept = {d: {k: v for k, v in files(docs / d).items() if k != 'index.json'}
            for d in ('history', quality_ledger.DIRECTORY)}
    assert all(kept.values())
    asked = len(fake_alpaca.bar_requests)
    c = float(fake_alpaca.history['QAAA']['Close'].iloc[-1])
    late(fake_alpaca, 'QAAA', [[c, c, c, c, 0.0]], still_behind=True)
    c = float(fake_alpaca.history['QAAB']['Close'].iloc[-1])
    late(fake_alpaca, 'QAAB', [[c, c, c, c, 0.0], [c, c * 1.001, c * 0.999, c, 5_000.0]], still_behind=False)

    rep, data, _ = evening(tmp_path, wide, now=NEXT_EVENING)
    assert rep.exit_code() == 0 and rep.status == 'ok', rep.problems
    block = data['run']['stale_followup']
    assert (block['status'], block['reason'], block['for_session'], block['count']) == ('applied', None, '2026-09-10', 2)
    assert block['outcomes']['no_match'] == 2 and block['zero_volume'] == block['flat'] == 2 and block['matched'] == []
    assert [(r['ticker'], r['volume']) for r in block['rows']] == [('QAAA', 0), ('QAAB', 0)]
    assert block['sentence'].startswith("The 2026-09-10 publication's 2 stocks without a 2026-09-10 bar, read again from "
                                        "this run's split-adjusted fetch: 2 now carry a 2026-09-10 bar (2 with zero "
                                        "volume); none of them would have been listed.")
    assert data['run']['input_tolerance']['names'] == ['QAAA']
    # no request of its own: tonight asked exactly what last night asked
    assert len(fake_alpaca.bar_requests) - asked == asked
    # and the previous night's archive and ledger entry are untouched, byte for byte
    for d, before in kept.items():
        after = files(docs / d)
        assert {k: after[k] for k in before} == before, d
    report.validate(data)


def test_a_late_scan_match_degrades_the_night_that_finds_it(wide, claude, fake_resend, fake_alpaca, tmp_path):
    behind(fake_alpaca, ['QAAA'])
    rep, first, docs = evening(tmp_path, wide)
    assert rep.status == 'ok', rep.problems
    c = float(fake_alpaca.history['QAAA']['Close'].iloc[-1])
    late(fake_alpaca, 'QAAA', [[c, c + 1.6, c - 0.1, c + 1.5, 300_000.0],
                               [c + 1.5, c + 1.52, c + 1.48, c + 1.5, 300_000.0]], still_behind=False)
    rep, data, docs = evening(tmp_path, wide, now=NEXT_EVENING)
    assert rep.exit_code() == pipeline_exit_degraded() and rep.status == 'degraded', rep.problems
    block = data['run']['stale_followup']
    assert block['matched'] == ['QAAA'] and block['rows'][0]['route'] == 'dollar', block
    assert [p['message'] for p in data['run']['problems'] if p['kind'] == 'coverage_thin'] == \
        ['late bars would have been listed in the publication for their session, which did not include them: QAAA (2026-09-10, $ scan)']
    assert 'QAAA ($ scan) would have been listed in that publication, which did not include it' in block['sentence']
    # accounting, never a signal: no burst, observation, plan or pick for it
    assert 'QAAA' not in {b['ticker'] for b in data['bursts']}
    assert not [s for s in data['observations']['signals'].values() if s['ticker'] == 'QAAA']
    picks = json.loads((docs / record.PICKS_FILE).read_text())['picks']
    assert 'QAAA' not in {p['ticker'] for p in picks}
    report.validate(data)
    # the record cannot drop the problem its own late match names
    forged = json.loads(json.dumps(data))
    forged['run']['problems'] = []
    with pytest.raises(ValueError, match='late bar that would have been listed is not named coverage_thin'):
        report.validate(forged)


def pipeline_exit_degraded():
    return pipeline.EXIT_DEGRADED


@pytest.mark.parametrize('earlier_row,status,matched', [
    ([None, None, None, None, 0.0], 'ok', []),                       # the placeholder at both missed sessions
    ([None, 1.6, -0.1, 1.5, 300_000.0], 'degraded', ['QAAA']),        # a $-scan bar at the EARLIER missed session
], ids=['two-placeholders', 'a-match-two-sessions-back'])
def test_the_next_night_reads_every_session_a_stock_missed(wide, claude, fake_resend, fake_alpaca, tmp_path,
                                                           earlier_row, status, matched):
    """A stock two sessions behind on Thursday night is within the bound, so the
    night is ok and the record says where its frame ended; Friday's run reads
    it at BOTH sessions it missed, and a bar at the earlier one that the
    Wednesday publication would have listed degrades Friday and is named with
    its session."""
    behind(fake_alpaca, ['QAAA'], sessions=2)
    rep, first, docs = evening(tmp_path, wide)
    assert rep.status == 'ok', rep.problems
    before = sessions.sessions_before(date(2026, 9, 10), 2)[0].isoformat()   # 8 Sep
    assert first['run']['input_tolerance']['endings'] == {'QAAA': before}
    c = float(fake_alpaca.history['QAAA']['Close'].iloc[-1])
    earlier = [c + (v or 0) if i < 4 else v for i, v in enumerate(earlier_row)]
    late(fake_alpaca, 'QAAA', [earlier, [c, c, c, c, 0.0], [c, c * 1.001, c * 0.999, c, 5_000.0]], still_behind=False)
    rep, data, _ = evening(tmp_path, wide, now=NEXT_EVENING)
    assert rep.status == status, rep.problems
    block = data['run']['stale_followup']
    assert (block['status'], block['for_session'], block['sessions'], block['stocks'], block['count']) == \
        ('applied', '2026-09-10', ['2026-09-09', '2026-09-10'], 1, 2), block
    assert [(r['ticker'], r['session'], r['outcome']) for r in block['rows']] == \
        [('QAAA', '2026-09-09', 'match' if matched else 'no_match'), ('QAAA', '2026-09-10', 'no_match')]
    assert block['matched'] == matched
    assert 'at each of the 2 sessions missed (2026-09-09 to 2026-09-10), one reading per stock and session, 2 readings in all' in block['sentence']
    if matched:
        assert [p['message'] for p in data['run']['problems'] if p['kind'] == 'coverage_thin'] == \
            ['late bars would have been listed in the publication for their session, which did not include them: QAAA (2026-09-09, $ scan)']
        assert 'QAAA (2026-09-09, $ scan) would have been listed in the publication for that session' in block['sentence']
    else:
        assert data['run']['problems'] == [] and 'none of them would have been listed' in block['sentence']
    report.validate(data)


@pytest.mark.parametrize('breakage', ['scan', 'through'])
def test_followup_never_raises(wide, claude, fake_resend, fake_alpaca, tmp_path, monkeypatch, breakage):
    behind(fake_alpaca, ['QAAA'])
    evening(tmp_path, wide)
    c = float(fake_alpaca.history['QAAA']['Close'].iloc[-1])
    late(fake_alpaca, 'QAAA', [[c, c, c, c, 0.0]], still_behind=True)

    def boom(*a, **k):
        raise RuntimeError('a defect in the check')
    if breakage == 'scan':
        monkeypatch.setattr(followup, 'scans', SimpleNamespace(scan_all=boom))
    else:
        monkeypatch.setattr(followup, '_through', boom)
    rep, data, _ = evening(tmp_path, wide, now=NEXT_EVENING)
    assert rep.exit_code() == 0 and rep.status == 'ok' and rep.published, rep.problems
    block = data['run']['stale_followup']
    if breakage == 'scan':
        assert block['status'] == 'applied' and block['rows'][0]['outcome'] == 'unmeasurable', block
    else:
        assert (block['status'], block['reason'], block['error_class']) == ('failed', 'error', 'RuntimeError'), block
        assert block['sentence'] == ("The previous publication's stocks without a 2026-09-10 bar could not be read "
                                     "again by this run; the check stopped on an error (RuntimeError).")
    report.validate(data)


# --------------------------------------------------------- applicability ----
def previous(**over):
    """A previous record's run, shaped as the pipeline writes one, with one stock a session behind."""
    names = ['QAAA']
    run = {'session': DAY.isoformat(), 'session_state': 'open',
           'coverage': {'reasons': {'stale': universe.population(names)}},
           'input_tolerance': {'names': names, 'endings': {'QAAA': BEFORE.isoformat()}}}
    run.update(over)
    return run


def night(prev, *, closed=False, session=TONIGHT, names_max=100, frames=None):
    frames = frames if frames is not None else {'QAAA': with_bar(tape(end=DAY)[:-1], DAY, PLACEHOLDER)}
    return followup.night(prev, frames, session, live(['QAAA']), closed=closed, benchmark='SPY',
                          names_max=names_max, feed='sip', sessions_max=BOUND)


@pytest.mark.parametrize('prev,kw,status,reason', [
    (previous(), {}, 'applied', None),
    (previous(), {'closed': True}, 'not_applicable', 'closed_session'),
    (None, {}, 'not_applicable', 'no_previous_record'),
    (previous(session_state='closed'), {}, 'not_applicable', 'previous_not_open'),
    (previous(session='2026-09-08'), {}, 'not_applicable', 'previous_not_adjacent'),
    (previous(input_tolerance=None), {}, 'not_applicable', 'membership_not_recorded'),
    (previous(input_tolerance={'names': None}), {}, 'not_applicable', 'membership_over_bound'),
    (previous(input_tolerance={'names': ['QAAB']}), {}, 'not_applicable', 'membership_mismatch'),
    (previous(input_tolerance={'names': []}, coverage={'reasons': {'stale': universe.population([])}}), {},
     'not_applicable', 'none_missing'),
    (previous(input_tolerance={'names': ['SPY']}, coverage={'reasons': {'stale': universe.population(['SPY'])}}), {},
     'not_applicable', 'none_missing'),
    (previous(session=TONIGHT.isoformat()), {}, 'not_applicable', 'rerun_without_block'),
    (previous(input_tolerance={'names': ['QAAA']}), {}, 'applied', None),
    (previous(input_tolerance={'names': ['QAAA'], 'endings': {'QAAA': None}}), {}, 'applied', None),
    (previous(input_tolerance={'names': ['QAAA'], 'endings': {'QAAA': 'not a date'}}), {}, 'applied', None),
], ids=['applied', 'closed-tonight', 'no-previous', 'previous-closed', 'previous-not-adjacent', 'not-recorded',
        'over-bound', 'tampered-membership', 'none-missing', 'only-the-benchmark', 'rerun-without-block',
        'first-version-membership', 'unreadable-ending', 'malformed-ending'])
def test_followup_applicability(prev, kw, status, reason):
    block = night(prev, **kw)
    assert (block['status'], block['reason']) == (status, reason), block
    assert faults_of(block) == []
    assert (block['rows'] != []) == (status == 'applied')
    if status == 'applied':
        assert block['sessions'] == [DAY.isoformat()], 'a membership without a readable ending is read at the previous session alone'


def test_a_rerun_of_the_same_session_reads_the_same_stocks_again():
    applied = night(previous())
    assert applied['outcomes']['no_match'] == 1
    # the same session re-run on later bars: QAAA's late bar has changed since,
    # and the re-run reads it from ITS fetch rather than carrying the first read
    later = {'QAAA': with_bar(tape(end=DAY)[:-1], DAY, DOLLAR)}
    rerun = followup.night(previous(session=TONIGHT.isoformat(), stale_followup=applied), later, TONIGHT,
                           live(['QAAA']), closed=False, benchmark='SPY', names_max=100, feed='sip', sessions_max=BOUND)
    assert (rerun['status'], rerun['matched'], rerun['for_session']) == ('applied', ['QAAA'], DAY.isoformat()), rerun
    assert faults_of(rerun) == []
    # a block over two sessions is re-read at the same two sessions
    two = followup.night(previous(input_tolerance={'names': ['QAAA'], 'endings': {'QAAA': sessions.previous_session(BEFORE).isoformat()}}),
                         {'QAAA': with_bar(with_bar(tape(end=BEFORE)[:-1], BEFORE, PLACEHOLDER), DAY, PLACEHOLDER)}, TONIGHT,
                         live(['QAAA']), closed=False, benchmark='SPY', names_max=100, feed='sip', sessions_max=BOUND)
    assert two['sessions'] == [BEFORE.isoformat(), DAY.isoformat()]
    # `later` carries a quiet bar at the earlier session and the $ bar at the later one
    again = followup.night(previous(session=TONIGHT.isoformat(), stale_followup=two), later, TONIGHT,
                           live(['QAAA']), closed=False, benchmark='SPY', names_max=100, feed='sip', sessions_max=BOUND)
    assert [(r['session'], r['outcome']) for r in again['rows']] == [(BEFORE.isoformat(), 'no_match'), (DAY.isoformat(), 'match')]
    # and a frame that lost its earlier bar reads still_missing there, the match untouched
    gone = {'QAAA': later['QAAA'].drop(pd.Timestamp(BEFORE))}
    again = followup.night(previous(session=TONIGHT.isoformat(), stale_followup=two), gone, TONIGHT,
                           live(['QAAA']), closed=False, benchmark='SPY', names_max=100, feed='sip', sessions_max=BOUND)
    assert [(r['session'], r['outcome']) for r in again['rows']] == [(BEFORE.isoformat(), 'still_missing'), (DAY.isoformat(), 'unmeasurable')]
    # a block that did not apply has nothing to read again and is carried as it stands
    nothing = night(None)
    assert night(previous(session=TONIGHT.isoformat(), stale_followup=nothing)) == nothing
    # a carried block that does not hold is not carried
    broken = dict(applied, count=5)
    assert night(previous(session=TONIGHT.isoformat(), stale_followup=broken))['reason'] == 'rerun_without_block'


# ------------------------------------------------------------- the words ----
CAUSES = ('halt', 'delist', 'suspend', 'did not trade', 'no trading', 'illiquid', 'merger', 'acquired', 'bankrupt')


def scenario_blocks():
    frames = {'A': with_bar(tape(end=DAY)[:-1], DAY, PLACEHOLDER), 'B': with_bar(tape(end=DAY)[:-1], DAY, DOLLAR),
              'C': tape(end=DAY).drop(pd.Timestamp(sessions.previous_session(DAY))),
              'D': tape(end=sessions.previous_session(DAY)),
              'E': with_bar(tape(end=DAY, close=2.5)[:-1], DAY, [2.5, 2.5, 2.5, 2.5, 0.0]),
              'H': coiled()}
    uni = live(['A', 'B', 'C', 'D', 'E', 'F', 'H'])
    stocks = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    rows = followup._read(stocks, frames, DAY, uni, 'SPY', 'sip')
    blocks = [followup._block(followup.APPLIED, None, DAY.isoformat(), rows)]
    blocks += [followup._block(followup.APPLIED, None, DAY.isoformat(), [r]) for r in rows]
    blocks += [followup._block(followup.NOT_APPLICABLE, r, DAY.isoformat(), []) for r in followup.REASONS]
    # the same stocks read at two sessions: every outcome, in the multi-session words
    earlier = followup._read(stocks, frames, BEFORE, uni, 'SPY', 'sip')
    blocks.append(followup._block(followup.APPLIED, None, DAY.isoformat(), rows + earlier))
    blocks += [followup._block(followup.APPLIED, None, DAY.isoformat(), [r, e]) for r, e in zip(rows, earlier)]
    return blocks


def test_followup_sentences_state_no_cause():
    blocks = scenario_blocks()
    assert {o for b in blocks for o, n in b['outcomes'].items() if n} == set(followup.OUTCOMES)
    for block in blocks:
        sentence = block['sentence'] or ''
        assert not [w for w in CAUSES if w in sentence.lower()], sentence
        assert not [w for w in ('None', 'undefined', 'nan', '{', '[') if w in sentence], sentence
        assert faults_of(block) == [], (block['sessions'], faults_of(block))
    multi = [b for b in blocks if len(b['sessions']) == 2]
    assert multi and all('one reading per stock and session' in b['sentence'] and f'({BEFORE} to {DAY})' in b['sentence'] for b in multi)
    assert not [b for b in multi if ' a 2026-09-09 bar' in b['sentence']], 'a two-session block never names one session as the bar'
    full = blocks[0]['sentence']
    assert full == ("The 2026-09-09 publication's 8 stocks without a 2026-09-09 bar, read again from this run's "
                    "split-adjusted fetch: 5 now carry a 2026-09-09 bar (2 with zero volume); B ($ scan), H (setting "
                    "up) would have been listed in that publication, which did not include them; 1 would not have "
                    "been listed; 1 cannot be measured on it (a missing or unreadable bar beside it); 1 falls under "
                    "the $3 session-close policy; 1 still has no 2026-09-09 bar; 1 returned no frame this run; 1 is "
                    "not in this run's selection, so its 2026-09-09 bar is unknown. A late bar is the bar the "
                    "provider served at this run's check; it never becomes a signal, plan or ticket."), full
    # a sentence for any day says the publication's date, never "last night": a
    # Monday reads Friday's, and the run after a holiday reads the session before it
    assert not [b for b in blocks if 'ast night' in (b['sentence'] or '')]


@pytest.mark.parametrize('field,value,message', [
    ('count', 3, 'counts do not reconcile'),
    ('matched', [], 'matched is not its matching rows'),
    ('for_session', '2026-09-08', 'not for the session before this one'),
    ('sentence', 'All clear.', 'sentence is not its own'),
    ('zero_volume', 9, 'zero-volume or flat counts are not its rows'),
    ('zero_volume', 0, 'zero-volume or flat counts are not its rows'),
    ('flat', 0, 'zero-volume or flat counts are not its rows'),
    ('sessions', ['2026-09-08'], 'sessions are not its rows'),
    ('sessions', ['2026-09-08', '2026-09-09'], 'sessions are not its rows'),
    ('stocks', 1, 'stock count is not its rows'),
    ('version', 1, 'version or status unknown'),
])
def test_the_block_holds_its_own_shape(field, value, message):
    frames = {'A': with_bar(tape(end=DAY)[:-1], DAY, PLACEHOLDER), 'B': with_bar(tape(end=DAY)[:-1], DAY, DOLLAR)}
    block = followup._block(followup.APPLIED, None, DAY.isoformat(),
                            followup._read(['A', 'B'], frames, DAY, live(['A', 'B']), 'SPY', 'sip'))
    assert faults_of(block) == []
    forged = dict(block, **{field: value})
    assert any(message in f for f in faults_of(forged)), faults_of(forged)


def test_a_block_cannot_read_outside_the_bound_before_its_night():
    """A row at a session the bound does not reach, or a row that is not for
    the publication's own stock-sessions, is refused one level in."""
    far = sessions.sessions_before(TONIGHT, BOUND + 1)[0]
    frames = {'A': with_bar(tape(end=far)[:-1], far, PLACEHOLDER)}
    rows = followup._read(['A'], frames, far, live(['A']), 'SPY', 'sip')
    block = followup._block(followup.APPLIED, None, DAY.isoformat(), rows)
    assert faults_of(block) == ['stale follow-up reads a session outside the bound before this one']
    assert faults_of(block, sessions_max=BOUND + 1) == []
    # a bound the rules do not carry asks for no block; one they carry asks for a well-formed one
    run = {'session': TONIGHT.isoformat(), 'coverage': {'version': 1}, 'stale_followup': block, 'problems': []}
    assert followup.faults(run, {'stale_tolerance_fraction': 0.01, 'stale_names_max': 100}) == []
    assert followup.faults(run, {'stale_tolerance_fraction': 0.01, 'stale_names_max': 100, 'stale_sessions_max': BOUND}) == \
        ['stale follow-up reads a session outside the bound before this one']
    # rows out of order or doubled are refused before anything is counted
    doubled = followup._block(followup.APPLIED, None, DAY.isoformat(), rows)
    doubled['rows'] = rows + rows
    doubled['count'] = 2
    doubled['outcomes']['no_match'] = 2
    assert faults_of(doubled, sessions_max=BOUND + 1) == ['stale follow-up rows are not sorted and unique']
