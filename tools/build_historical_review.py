"""Publish a compact, read-only study projection, never a trading record.

python tools/build_historical_review.py /tmp/poc-repaired
The fixed case selection was named as development challenges in POC v1.
"""
import argparse
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(results_dir):
    r = json.loads((results_dir/'results.json').read_bytes())
    events = json.loads(gzip.decompress((results_dir/'event-study.json.gz').read_bytes()))
    index = json.loads((ROOT/'docs/history/index.json').read_bytes())
    cases = []
    for session,ticker in [('2026-09-24','CRL'),('2026-09-24','IQV'),('2026-09-25','MSFT')]:
        entries = [e for e in index['entries'] if e['ticker']==ticker and e['kind']=='burst'
                   and index['records'][e['source']]['session']==session]
        entry = min(entries,key=lambda e:index['records'][e['source']]['published_at'])
        event = next(e for e in events['rows'] if e['session']==session and e['ticker']==ticker)
        cases.append({'ticker':ticker,'session':session,'entry':entry,'source':index['records'][entry['source']],
                      'next_session':event['next_session'],'later_observation':event['later_observation'],
                      'close_change_pct':event['close_change_pct']})
    return {'version':r['version'],'spec_sha256':r['spec_sha256'],'base':r['baseline'],
            'from':'2026-09-11','through':'2026-09-25','publications':r['publications'],
            'unique_sessions':r['unique_sessions'],'candidate_publications':r['candidate_publications'],
            'unique_candidate_sessions':r['unique_candidate_sessions'],
            'published_tickets':r['performance']['published_tickets'],'settled':0,
            'selection':'Complete retained rebuild publications; repeated sessions are revisions. Displayed CRL/IQV/MSFT cases were named development challenges, not a holdout or a representative performance sample.',
            'original_policy':'recorded rules for each publication; reader authority v1',
            'proposed_policy':'reader request v2; old replies are not reviews of the new request',
            'cases':cases}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('results_dir',type=Path);args=p.parse_args()
    target=ROOT/'docs/historical-validation.json'
    target.write_text(json.dumps(build(args.results_dir),indent=2,ensure_ascii=False)+'\n')
