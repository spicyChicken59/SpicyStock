"""Offline sensitivity to the retained public-page volume observations.

No source is adjudicated as correct, and no new price/provider data is requested.
python tools/replay_volume_observations.py --check
"""
import argparse
import gzip
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src import provenance,scans,quality
FILE=ROOT/'docs/input-truthfulness/2026-09-28-evidence/volume-corroboration.json'


def result(frame):
    q=quality.assess(frame).to_dict()
    return {'routes':[k for k,v in scans.scan_all(frame).items() if v],
            'score':q['score'],'grade':q['grade'],
            'checks':{c['letter']:{'status':c['status'],'values':c['values']} for c in q['checks']}}


def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
    rows=json.loads(FILE.read_bytes())
    original=json.loads(gzip.decompress((ROOT/'tests/fixtures/chart-keyboard/2026-09-24.json.gz').read_bytes()))
    for row in rows:
        b=next(b for b in original['bursts'] if b['ticker']==row['ticker'])
        ref=b['evidence']['source']['sha256'];raw=gzip.decompress((ROOT/'docs/evidence'/f'{ref}.json.gz').read_bytes())
        f=provenance.frame_of(json.loads(raw));g=f.copy()
        assert row['provider_volumes']==list(f.Volume.iloc[-2:])
        g.loc[g.index[-2:],'Volume']=row['public_volumes']
        old,new=result(f),result(g)
        if args.check:assert row['before']==old and row['substituted_public_volumes']==new
        row.update(before=old,substituted_public_volumes=new)
    if not args.check:FILE.write_text(json.dumps(rows,indent=2)+'\n')
    print('PASS: two frozen-volume component sensitivities; no source-error or execution claim')


if __name__=='__main__':main()
