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
