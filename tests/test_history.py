"""Public history/coverage stays bounded, source-grounded, and independent of saves."""
from copy import deepcopy
from datetime import date, timedelta
import gzip
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from src import history, pipeline
from tests.test_pipeline import market, claude, evening

ROOT = Path(__file__).resolve().parents[1]


def record(day):
    return json.loads(gzip.decompress((ROOT / 'tests/fixtures/continuity' / f'{day}.json.gz').read_bytes()))


def frame(days):
    return pd.DataFrame({'Open': [10.] * len(days), 'High': [12.] * len(days), 'Low': [9.] * len(days),
                         'Close': list(range(10, 10 + len(days))), 'Volume': [100.] * len(days)}, index=pd.to_datetime(days))


def test_exact_sources_and_case_distinctions():
    for day, blob in [('2026-09-11','2c5ec387654d2cea9d85b1230e91b4c7c0efb534'),('2026-09-14','a89ab122d7e0160df6a63c30957668447ace1103')]:
        raw = gzip.decompress((ROOT/'tests/fixtures/continuity'/f'{day}.json.gz').read_bytes())
        assert history.git_blob(raw) == blob
    a, b = record('2026-09-11'), record('2026-09-14')
    assert [(r['ticker'], r['grade'], len(r['series'])) for r in a['bursts'] if r['ticker'] in ['ATEC','VICR']] == [('ATEC','A',120),('VICR','A',0)]
    assert 'ATEC' not in {r['ticker'] for r in b['bursts']}
    assert next(r for r in b['bursts'] if r['ticker']=='VICR')['grade'] == 'C'
    assert b['observations']['symbols']['ATEC']['c'] == 10.86
    assert not a['trades'] and not b['trades']


def test_hidden_signals_and_new_ticker_signal_get_separate_windows():
    old, new = record('2026-09-11'), record('2026-09-14')
    source = deepcopy(new)
    obs = history.observe({'VICR': frame(['2026-09-11','2026-09-14'])}, old, history.signals(new), date(2026,9,14), pipeline.series_of)
    vicr = [s for s in obs['signals'].values() if s['ticker']=='VICR']
    assert {s['session'] for s in vicr} == {'2026-09-11','2026-09-14'}
    assert len(obs['symbols']['VICR']['history']) == 2
    assert len(obs['signals']) >= len(new['bursts'])
    assert new == source  # grades, breadth, picks, model population unchanged
    expired = history.observe({}, {'observations':obs}, {}, date(2026,10,3), pipeline.series_of)
    assert {s['session'] for s in expired['signals'].values() if s['ticker']=='VICR'} == {'2026-09-14'}
    assert expired['symbols']['VICR']['since'] == '2026-09-14'


def test_missing_frame_retains_actual_date_source_and_no_fabricated_bars():
    sig={'burst:A:2026-09-01:r':{'ticker':'A','kind':'burst','session':'2026-09-01','rules_version':'r'}}
    first=history.observe({'A':frame(['2026-09-01','2026-09-04'])},None,sig,date(2026,9,4),pipeline.series_of)
    later=history.observe({}, {'observations':first}, {}, date(2026,9,8),pipeline.series_of)
    assert later['symbols']['A']['history']==first['symbols']['A']['history']
    assert later['symbols']['A']['date']=='2026-09-04'
    assert next(iter(later['signals'].values()))['coverage']=='no_new_bar'
    missing=history.observe({},None,sig,date(2026,9,4),pipeline.series_of)
    assert missing['symbols']=={}
    assert next(iter(missing['signals'].values()))['coverage']=='no_available_bar'


def test_window_edge_history_cap_and_revision_cautions():
    start=date(2026,9,1)
    sig={'id':{'ticker':'A','kind':'burst','session':start.isoformat(),'rules_version':'r'}}
    dates=[(start+timedelta(days=i)).isoformat() for i in range(22)]
    got=history.observe({'A':frame(dates)},None,sig,start+timedelta(days=21),pipeline.series_of)
    assert len(got['symbols']['A']['history'])==20 and 'id' in got['signals']
    assert not history.observe({}, {'observations':got}, {}, start+timedelta(days=22),pipeline.series_of)['signals']
    changed=frame(dates);changed.iloc[-1,changed.columns.get_loc('Close')]=90
    revised=history.observe({'A':changed},{'observations':got},sig,start+timedelta(days=21),pipeline.series_of)
    assert revised['symbols']['A']['history'][-1]['revised_from']['c']==31


def test_catalog_preserves_revisions_and_only_authentic_evidence(tmp_path):
    raw=gzip.decompress((ROOT/'tests/fixtures/continuity/2026-09-11.json.gz').read_bytes())
    index=history.publish(raw,tmp_path)
    source=history.git_blob(raw)
    entry=next(e for e in index['entries'] if e['ticker']=='ATEC')
    assert hashlib.sha256((tmp_path/entry['path']).read_bytes()).hexdigest()==entry['sha256']
    assert next(e for e in index['entries'] if e['ticker']=='VICR')['chart'] is False
    assert json.loads((tmp_path/entry['path']).read_bytes())['row']==next(r for r in json.loads(raw)['bursts'] if r['ticker']=='ATEC')
    # same source republished by a different importer must keep context hash valid
    again=history.publish(raw,tmp_path,source_commit='a'*40)
    assert hashlib.sha256((tmp_path/source/'record.json').read_bytes()).hexdigest()==again['records'][source]['context_sha256']
    revised=json.loads(raw);revised['run']['published_at']='2026-09-11T23:00:00Z'
    next_index=history.publish(history.encoded(revised),tmp_path)
    assert len(next_index['records'])==2
    assert len([e for e in next_index['entries'] if e['ticker']=='ATEC'])==2
    before=(tmp_path/'index.json').read_bytes()
    revised['bursts'][0]['series'][0]['c']=float('nan')
    with pytest.raises(ValueError):history.publish(json.dumps(revised).encode(),tmp_path)
    assert (tmp_path/'index.json').read_bytes()==before


def test_catalog_bounds_refuse_before_index_replacement(tmp_path,monkeypatch):
    raw=gzip.decompress((ROOT/'tests/fixtures/continuity/2026-09-11.json.gz').read_bytes())
    history.publish(raw,tmp_path)
    before=(tmp_path/'index.json').read_bytes()
    monkeypatch.setattr(history,'CATALOG_BYTES_MAX',10)
    with pytest.raises(ValueError,match='byte bound'):history.publish(raw,tmp_path)
    assert (tmp_path/'index.json').read_bytes()==before
    monkeypatch.setattr(history,'CATALOG_BYTES_MAX',128 * 1024 * 1024)
    later=json.loads(raw);later['run']['session']='2026-10-06'
    later['run']['published_at']='2026-10-06T22:00:00Z'
    (tmp_path/'unrelated.txt').write_text('keep')
    pruned=history.publish(history.encoded(later),tmp_path)
    assert len(pruned['records'])==1
    assert not (tmp_path/history.git_blob(raw)).exists()
    assert (tmp_path/'unrelated.txt').read_text()=='keep'


def test_pipeline_covers_every_saveable_signal_without_more_boundary_calls(market,claude,fake_resend,fake_alpaca,tmp_path):
    # The real pipeline with its normal doubles: no additional fetch/read client.
    rep,data,docs=evening(tmp_path,market)
    assert rep.exit_code()==0
    assert len(fake_alpaca.bar_requests)==1
    assert len(claude.calls)==1
    assert (docs/"history/index.json").exists()
    assert set(history.signals(data)) <= set(data['observations']['signals'])


# --- past its cap, the oldest records give way ------------------------------
def small(session, published_at, n=6):
    """A distinct authentic record: the 11 September publication's first n
    bursts, filed under another session or publication time."""
    data = record('2026-09-11')
    data['bursts'] = data['bursts'][:n]
    data['run']['session'] = session
    data['run']['published_at'] = published_at
    return history.encoded(data)


def catalog_bytes(root):
    return sum(p.stat().st_size for p in root.rglob('*.json'))


def files_of(root, source):
    return {p.name: p.read_bytes() for p in (root / source).glob('*.json')}


def test_past_the_byte_cap_the_oldest_record_inside_the_window_gives_way(tmp_path, monkeypatch, caplog):
    r1, r2, r3 = (small('2026-10-01', '2026-10-01T22:00:00Z'), small('2026-10-02', '2026-10-02T22:00:00Z'),
                  small('2026-10-05', '2026-10-05T22:00:00Z'))
    # the catalog the eviction should leave is the one r2 and r3 make alone
    fits = tmp_path / 'fits'
    history.publish(r2, fits)
    history.publish(r3, fits)
    root = tmp_path / 'catalog'
    history.publish(r1, root)
    history.publish(r2, root)
    kept = files_of(root, history.git_blob(r2))
    monkeypatch.setattr(history, 'CATALOG_BYTES_MAX', catalog_bytes(fits))
    assert catalog_bytes(fits) < catalog_bytes(root) + catalog_bytes(fits) - catalog_bytes(root / history.git_blob(r2))
    caplog.set_level('INFO', logger='spicystock.history')
    index = history.publish(r3, root)
    assert set(index['records']) == {history.git_blob(r2), history.git_blob(r3)}
    assert not (root / history.git_blob(r1)).exists()
    assert files_of(root, history.git_blob(r2)) == kept
    assert (root / 'index.json').read_bytes() == (fits / 'index.json').read_bytes()
    assert catalog_bytes(root) == catalog_bytes(fits) <= history.CATALOG_BYTES_MAX
    assert {e['source'] for e in index['entries']} == {history.git_blob(r2), history.git_blob(r3)}
    said = [r.getMessage() for r in caplog.records if r.name == 'spicystock.history']
    assert any('1 record inside its 21-day window was removed, oldest first (2026-10-01)' in m for m in said), said


def test_past_the_record_cap_the_oldest_record_gives_way(tmp_path, monkeypatch):
    monkeypatch.setattr(history, 'RECORDS_MAX', 2)
    raws = [small(f'2026-10-0{d}', f'2026-10-0{d}T22:00:00Z') for d in (1, 2, 5)]
    for raw in raws:
        index = history.publish(raw, tmp_path)
    assert set(index['records']) == {history.git_blob(raws[1]), history.git_blob(raws[2])}
    assert not (tmp_path / history.git_blob(raws[0])).exists()


def test_revisions_of_one_session_leave_in_publication_order_then_by_digest(tmp_path, monkeypatch):
    monkeypatch.setattr(history, 'RECORDS_MAX', 2)
    late, early = small('2026-10-01', '2026-10-01T23:00:00Z'), small('2026-10-01', '2026-10-01T22:00:00Z')
    history.publish(late, tmp_path)
    history.publish(early, tmp_path)
    index = history.publish(small('2026-10-02', '2026-10-02T22:00:00Z'), tmp_path)
    assert history.git_blob(late) in index['records'] and history.git_blob(early) not in index['records']
    # equal sessions and publication times leave by digest
    twin = tmp_path / 'twin'
    a, b = small('2026-10-01', '2026-10-01T22:00:00Z', 5), small('2026-10-01', '2026-10-01T22:00:00Z', 4)
    first, second = sorted([a, b], key=history.git_blob)
    history.publish(second, twin)
    history.publish(first, twin)
    index = history.publish(small('2026-10-02', '2026-10-02T22:00:00Z'), twin)
    assert history.git_blob(second) in index['records'] and history.git_blob(first) not in index['records']


def test_tonight_alone_past_the_cap_refuses_and_nothing_gives_way(tmp_path, monkeypatch):
    old = small('2026-10-01', '2026-10-01T22:00:00Z')
    history.publish(old, tmp_path)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    tonight = small('2026-10-02', '2026-10-02T22:00:00Z')
    fits = tmp_path.parent / (tmp_path.name + '-alone')
    history.publish(tonight, fits)
    monkeypatch.setattr(history, 'CATALOG_BYTES_MAX', catalog_bytes(fits) - 1)
    with pytest.raises(ValueError, match='byte bound'):
        history.publish(tonight, tmp_path)
    assert {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before


def test_tonights_record_never_gives_way_even_when_it_is_the_oldest(tmp_path, monkeypatch):
    monkeypatch.setattr(history, 'RECORDS_MAX', 1)
    newer, older = small('2026-10-02', '2026-10-02T22:00:00Z'), small('2026-10-01', '2026-10-01T22:00:00Z')
    history.publish(newer, tmp_path)
    index = history.publish(older, tmp_path)
    assert set(index['records']) == {history.git_blob(older)}
    assert (tmp_path / history.git_blob(older) / 'record.json').exists()
    assert not (tmp_path / history.git_blob(newer)).exists()


@pytest.mark.parametrize('fraction,warns', [(0.79, False), (0.81, True)])
def test_the_run_log_states_the_catalog_against_its_caps(fraction, warns, tmp_path, monkeypatch, caplog):
    raw = small('2026-10-01', '2026-10-01T22:00:00Z')
    probe = tmp_path / 'probe'
    history.publish(raw, probe)
    size = catalog_bytes(probe)
    monkeypatch.setattr(history, 'CATALOG_BYTES_MAX', int(size / fraction))
    caplog.set_level('INFO', logger='spicystock.history')
    history.publish(raw, tmp_path / 'catalog')
    line = [r for r in caplog.records if r.name == 'spicystock.history' and 'Recovery catalog:' in r.getMessage()]
    assert len(line) == 1
    assert line[0].getMessage() == (f'Recovery catalog: 1 of {history.RECORDS_MAX} records over 1 session, '
                                    f'{size} of {history.CATALOG_BYTES_MAX} bytes.')
    assert line[0].levelname == ('WARNING' if warns else 'INFO')


@pytest.mark.parametrize('email', ['delivered', 'failed'])
def test_a_catalog_that_cannot_take_tonight_still_leaves_the_night_its_ledger_entry(email, market, claude, fake_resend, tmp_path, monkeypatch):
    from src import quality_ledger
    if email == 'failed':
        fake_resend.raises = RuntimeError('Resend refused')
    monkeypatch.setattr(history, 'CATALOG_BYTES_MAX', 10)
    rep, data, docs = evening(tmp_path, market)
    assert rep.published and rep.exit_code() == pipeline.EXIT_FAILED_AFTER_PUBLISH
    assert 'byte bound' in rep.failure or email == 'failed'
    assert rep.quality_ledger['status'] == 'retained', rep.quality_ledger
    assert len(list((docs / 'quality-ledger' / 'v1').glob('*.json.gz'))) == 1
    assert not (docs / 'history' / 'index.json').exists()
    assert data['run']['email'] == email
