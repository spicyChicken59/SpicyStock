#!/usr/bin/env python3
"""Measure continuity using only the two authentic published records (no live calls)."""
from copy import deepcopy
from datetime import date
import gzip
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from src import history, pipeline

ROOT=Path(__file__).resolve().parents[1]

def size(raw):
    return {'raw':len(raw),'gzip':len(gzip.compress(raw,mtime=0))}

def main():
    raw={day:gzip.decompress((ROOT/'tests/fixtures/continuity'/f'{day}.json.gz').read_bytes()) for day in ['2026-09-11','2026-09-14']}
    a,b=[json.loads(raw[d]) for d in raw]
    # Only prices actually present in these immutable publications. The
    # unavailable original full provider frames are not reconstructed.
    bars={}
    for record in [a,b]:
        session=record['run']['session']
        for kind,row,_ in history.rows(record):
            dest=bars.setdefault(row['ticker'],{})
            for bar in row.get('series',[]):dest[bar['date']]=bar
            if row.get('close'):
                dest[session]={'date':session,'o':row.get('open'),'h':row.get('high'),'l':row.get('low'),'c':row['close'],'v':row.get('volume')}
        for ticker,bar in record['observations']['symbols'].items():bars.setdefault(ticker,{})[bar['date']]=bar
    frames={}
    for ticker,by_date in bars.items():
        df=pd.DataFrame(list(by_date.values())).set_index('date').rename(columns={'o':'Open','h':'High','l':'Low','c':'Close','v':'Volume'})
        # series_of is a serializer of complete provider bars. Keep only real
        # complete OHLCV rows; no invented open/high/low or volume is inserted.
        df=df.reindex(columns=['Open','High','Low','Close','Volume']).dropna()
        df.index=pd.to_datetime(df.index);frames[ticker]=df.sort_index()
    expanded=history.observe(frames,a,history.signals(b),date(2026,9,14),pipeline.series_of)
    after=deepcopy(b);after['observations']=expanded
    whole=json.dumps(after,indent=1,ensure_ascii=False,allow_nan=False).encode()+b'\n'
    files=list((ROOT/'docs/history').rglob('*.json')); index=json.loads((ROOT/'docs/history/index.json').read_bytes())
    samples={}
    for ticker in ['ATEC','VICR']:
        entry=next(e for e in index['entries'] if e['ticker']==ticker and e['source']=='2c5ec387654d2cea9d85b1230e91b4c7c0efb534')
        samples[ticker]=size((ROOT/'docs/history'/entry['path']).read_bytes())
    result={
        'basis':'Offline replay from available published bars only; actual subsequent provider-frame payload is not measured.',
        'before':{'observations':size(history.encoded(b['observations'])),'data':size(raw['2026-09-14']),'symbols':len(b['observations']['symbols']),'bursts':len(b['bursts'])},
        'after_replay':{'observations':size(history.encoded(expanded)),'data':size(whole),'symbols':len(expanded['symbols']),'signal_identities':len(expanded['signals']),'actual_dated_bars':sum(len(o['history']) for o in expanded['symbols'].values())},
        'recovery':{'index':size((ROOT/'docs/history/index.json').read_bytes()),'files':len(files),'total_raw':sum(p.stat().st_size for p in files),'sum_individual_gzip':sum(len(gzip.compress(p.read_bytes(),mtime=0)) for p in files),'records':len(index['records']),'entries':len(index['entries']),'dates':index['dates'],'on_demand_examples':samples},
        'requests':{'additional_initial':0,'first_history_search':1,'inspect_original':2,'provider_increment':0,'paid_chart_reader_increment':0},
        'bounds':{'public_days':history.DAYS,'public_revisions':history.RECORDS_MAX,'signals_per_publication':history.SIGNALS_MAX,'catalog_bytes':history.CATALOG_BYTES_MAX,'original_bars_per_setup':120,'local_observations_per_setup':20,'private_store_growth':'O(saved setups), originals <=120 bars, observations <=20; no append-only operation log. Fixed legacy backups are retained.'}
    }
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
