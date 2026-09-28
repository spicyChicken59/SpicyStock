"""Frozen, socket-blocked evidence study. Never writes a production publication.

python tools/historical_validation.py --output /tmp/stock-poc --original-replay
Inputs are Git's retained main publications and docs/evidence; optional retained
exception packages live in tests/fixtures/historical-validation. No credentials.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
from decimal import Decimal, ROUND_FLOOR
import gzip
import hashlib
import importlib.metadata
import io
import json
import math
from pathlib import Path
import resource
import socket
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.audit_retained_quality import inventory, git
from src import (charts, grader, input_diagnostics, inputs, market_data, pipeline, plan,
                 provenance, quality, reader_authority, reader_coverage, record,
                 scans, sessions, universe)

BASE = '8be007f68deaa417b85a512d2e16a37899d27011'
SPEC = 'docs/input-truthfulness/2026-09-28-poc-spec.md'
VERSION = 'historical-validation-v1'
CLOCK = '2026-09-28T13:15:00Z'
OBJECTS = ROOT / 'docs/evidence'


def offline(*args, **kwargs):
    raise RuntimeError('historical validation: network forbidden')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode(value))


def account(data):
    return plan.Account(**{k: data['account'][k] for k in provenance.ACCOUNT_FIELDS})


def preview(row, acct, multiplier=1):
    """Production arithmetic with explicitly substituted nonzero market sizing."""
    return plan.burst_plan(ticker=row['ticker'], close=row['close'], low=row['low'],
        high=row['high'], open_=row['open'], prev_close=row['prev_close'],
        gain_pct=row['gain_pct'] or 0., account=acct, size_multiplier=multiplier,
        scan='dollar' if row['scan'] == 'dollar' else '4pct', extension_pct=row.get('extension_pct'))


def independent_band(row):
    """Reference equation in integer cents/Decimal, not production helpers.

    Source prices enter on the established Python cent grid; every subsequent
    constraint is exact decimal arithmetic. This does not redefine that grid.
    """
    D = lambda x: Decimal(str(round(float(x), 2)))
    close, low, high = (D(row[k]) for k in ('close', 'low', 'high'))
    # Keep the established binary-float round-to-cent convention at the
    # two producer boundaries. Replacing it with Decimal midpoint rounding
    # would test a different price policy (e.g. 17.11/17.88 -> 17.49).
    outer = D(float(close) * 1.04)
    midpoint = D((float(low) + float(high)) / 2)
    tried = []
    for basis, stop in [('burst_low', low), ('half_range', midpoint)]:
        ceiling = (stop / Decimal('.96')).quantize(Decimal('.01'), rounding=ROUND_FLOOR)
        limit = min(outer, ceiling)
        tried.append({'basis': basis, 'stop': float(stop), 'limit': float(limit),
                      'feasible': stop < close < limit})
    feasible = next((x for x in tried if x['feasible']), None)
    return {'admitted': feasible is not None, 'selected': feasible, 'tried': tried}


def plan_oracle(p):
    failures = []
    if not p['eligible']:
        return failures
    D = lambda x: Decimal(str(x))
    stop, trigger, limit = (D(p[k]) for k in ('stop', 'entry_ref', 'limit'))
    if not stop < trigger < limit:
        failures.append('cent_band')
    if (limit - stop) / limit > Decimal('.04'):
        failures.append('worst_fill_stop_width')
    sz = p['sizing']
    risk_cents = int((limit-stop)*100)
    risk_shares = int(D(sz['budget_usd'])*100) // risk_cents
    cap_shares = int(D(sz['cap_usd'])*100) // int(limit*100)
    if p['shares'] != min(risk_shares, cap_shares):
        failures.append('whole_share_sizing')
    return failures


def trace(data, item):
    rows, acct = [], account(data)
    ordered = sorted(data['bursts'], key=lambda b: (pipeline.GRADE_ORDER.get(b['grade_mechanical'], 9),
                                                   -(b['score'] or 0), b['ticker']))
    selected = {b['ticker'] for b in ordered[:data['rules']['pipeline']['max_reads']]}
    cutoff = ordered[min(len(ordered), pipeline.MAX_READS)-1] if ordered else None
    tie = [b['ticker'] for b in ordered if cutoff and
           (b['grade_mechanical'], b['score']) == (cutoff['grade_mechanical'], cutoff['score'])]
    for b in data['bursts']:
        cl = b.get('claude') or {}
        accepted = reader_coverage.accepted(b)
        status = ('accepted' if accepted else 'rejected' if cl.get('source') == 'fallback'
                  else 'not_selected' if b['ticker'] not in selected else 'unknown')
        p, err = None, None
        try:
            p = preview(b, acct)
        except (ValueError, KeyError, TypeError) as exc:
            err = str(exc)
        ref = independent_band(b)
        oracle = [] if p is None else plan_oracle(p)
        if p and (p['eligible'] != ref['admitted'] or p['eligible'] and
                  (p['stop'], p['limit']) != (ref['selected']['stop'], ref['selected']['limit'])):
            oracle.append('independent_band_disagrees')
        veto = bool(b.get('vetoes'))
        grade = b['grade'] in pipeline.TRADE_GRADES
        blocks = []
        if data['breadth']['regime']['verdict'] == 'red': blocks.append('market_red')
        if veto: blocks.append('quality_veto')
        if not grade: blocks.append('final_grade_below_A')
        if not accepted: blocks.append('review_' + status)
        if p is None: blocks.append('plan_error')
        elif not p['eligible']: blocks.append('structural_stop_band')
        elif p['shares'] == 0: blocks.append('zero_shares_under_substituted_GREEN')
        cut = next((x for x in data.get('cash_budget', {}).get('cut', []) if x['ticker'] == b['ticker']), None)
        if cut: blocks.append('allocation_' + cut['kind'])
        qchecks = {c['letter']: c for c in b['quality']['checks']}
        rows.append({'publication': item['sha256'], 'session': item['session'], 'ticker': b['ticker'],
            'security_name': b.get('name'), 'evidence_id': (b.get('evidence') or {}).get('id'),
            'discovery': b['scan'], 'mechanical_grade': b['grade_mechanical'], 'mechanical_score': b['score'],
            'final_grade': b['grade'], 'vetoes': b.get('vetoes'), 'review': status,
            'selected': b['ticker'] in selected, 'reader_error': cl.get('error'),
            'recorded_first_blocker': (b.get('evidence') or {}).get('gate', {}).get('reason'),
            'independent_blockers': blocks, 'structural_feasible': None if p is None else p['eligible'],
            'sized_if_GREEN': None if p is None else p['shares'], 'oracle_errors': oracle,
            'plan_error': err, 'published_plan': b.get('plan') is not None,
            'published_ticket': b['ticker'] in data['trades'], 'allocation': cut,
            'current_entry_available': False, 'model_execution': 'NOT RUN: no published ticket' if b['ticker'] not in data['trades'] else 'requires subsequent evidence',
            'check_statuses': {k: v['status'] for k,v in qchecks.items()},
            'composite_with_RE_VOL_C_failure': b['grade_mechanical'] in ('A+', 'A') and
                any(qchecks[k]['status'] in ('FAIL','PARTIAL') for k in ('RE','VOL','C'))})
    cf = {}
    for name, regime, require in [
        ('recorded_market_current_reader_gate', data['breadth']['regime'], True),
        ('substituted_GREEN_recorded_reader_results', {'verdict':'green','size_multiplier':1.}, True),
        ('substituted_YELLOW_recorded_reader_results', {'verdict':'yellow','size_multiplier':.5}, True),
        ('omitted_reader_recorded_market', data['breadth']['regime'], False),
        ('substituted_GREEN_omitted_reader', {'verdict':'green','size_multiplier':1.}, False),
    ]:
        copy = deepcopy(data['bursts'])
        t,c,budget = pipeline._make_plans(copy, acct, regime, len(data.get('open_plans', [])),
                                        date.fromisoformat(item['session']), require_reader=require)
        cf[name] = {'tickets':t,'cut':c,'plan_count':sum(b['plan'] is not None for b in copy),
                    'label':'ISOLATED COUNTERFACTUAL; not historical publication or new reader acceptance'}
    rd = [r for r in rows if r['selected']]
    feasible_unreviewed = [r['ticker'] for r in rows if not r['selected'] and r['structural_feasible']
                          and r['mechanical_grade'] in ('A+','A') and not r['vetoes'] and r['sized_if_GREEN']]
    cov=data['run'].get('coverage',{})
    summary = {'identity':item, 'rules':data['app']['rules_version'], 'reader_policy':data['rules']['pipeline'].get('reader_policy','legacy'),
        'universe':data['run']['universe'], 'coverage':cov, 'input_faults':inputs.record_faults(data['run']),
        'regime':data['breadth']['regime'], 'candidate_count':len(rows),
        'mechanical_grades':dict(Counter(r['mechanical_grade'] for r in rows)),
        'final_grades':dict(Counter(r['final_grade'] for r in rows)),
        'reviews':dict(Counter(r['review'] for r in rows)),
        'first_blockers':dict(Counter(r['recorded_first_blocker'] or 'not_recorded' for r in rows)),
        'overlapping_blockers':dict(Counter(v for r in rows for v in r['independent_blockers'])),
        'blocker_combinations':dict(Counter('|'.join(r['independent_blockers']) for r in rows)),
        'selected_infeasible':[r['ticker'] for r in rd if not r['structural_feasible']],
        'feasible_mechanical_A_unreviewed':feasible_unreviewed,
        'cutoff_tie':{'mechanical_grade':cutoff['grade_mechanical'] if cutoff else None,
                      'score':cutoff['score'] if cutoff else None,'members':tie,
                      'selected':[s for s in tie if s in selected]},
        'accepted_in_A_band':[r['ticker'] for r in rows if r['review']=='accepted' and r['final_grade'] in ('A+','A')],
        'structural_feasible':sum(r['structural_feasible'] is True for r in rows),
        'composite_with_RE_VOL_C_failure':sum(r['composite_with_RE_VOL_C_failure'] for r in rows),
        'oracle_errors':[{'ticker':r['ticker'],'errors':r['oracle_errors']} for r in rows if r['oracle_errors']],
        'tickets':data['trades'], 'anticipation':[
            {'ticker':w['ticker'],'eligible':(w.get('plan') or {}).get('eligible'),
             'action':(w.get('plan') or {}).get('action'), 'shares':(w.get('plan') or {}).get('shares')}
            for w in data.get('watchlist',{}).get('top',[])], 'counterfactuals':cf}
    return summary,rows


def inspect_frame(obj, session):
    """Independent scalar inspection of ALL retained source values and dates."""
    ds, cols = obj['dates'],dict(zip(obj['columns'],obj['values']))
    errors=[]
    if ds!=sorted(set(ds)): errors.append('duplicate_or_unordered_dates')
    expected=[str(d) for d in sessions.dates(date.fromisoformat(ds[0]), date.fromisoformat(ds[-1]))]
    missing=sorted(set(expected)-set(ds))
    non_sessions=sorted(set(ds)-set(expected))
    if non_sessions: errors.append('non_session')
    invalid=[]; fractional=[]; high_precision=0
    for i,day in enumerate(ds):
        values=[cols[k][i] for k in ('Open','High','Low','Close','Volume')]
        if not all(type(v) in (int,float) and math.isfinite(v) for v in values):
            invalid.append([day,'nonfinite']);continue
        o,h,l,c,v=values
        if min(o,h,l,c)<=0 or v<0 or not l<=min(o,c)<=max(o,c)<=h:
            invalid.append([day,'invalid_OHLCV'])
        if v!=int(v) or v>2**53: fractional.append(day)
        high_precision += any(abs(x*100-round(x*100))>1e-6 for x in (o,h,l,c))
    if invalid:errors.append('invalid_values')
    if fractional:errors.append('volume_not_exact_integer')
    if ds[-1]!=session:errors.append('wrong_decision_session')
    return {'rows':len(ds),'first':ds[0],'last':ds[-1], 'errors':errors,
        'missing_sessions':missing,'non_sessions':non_sessions,'invalid':invalid,
        'volume_noninteger_dates':fractional,'subcent_price_rows':high_precision,
        'warmup_rows':len(ds)-1,'full_110_session_quality_history':len(ds)>=111,
        'last_110_missing':[s for s in missing if s>=expected[max(0,len(expected)-111)]]}


def breadth_arithmetic(data):
    b=data['breadth'];history=b.get('history',[]);results={}
    for n in (5,10):
        tail=history[-n:];up=sum(x['up4'] for x in tail);down=sum(x['down4'] for x in tail)
        ratio=round(up/down,2) if down else (None if up==0 else None)
        results[str(n)]={'history_rows':len(tail),'up_sum':up,'down_sum':down,'ratio':ratio,
            'published_up':b.get(f'up4_{n}d'),'published_down':b.get(f'down4_{n}d'),
            'published_ratio':b.get(f'ratio_{n}d'),
            'status':'PASS' if len(tail)==n and up==b.get(f'up4_{n}d') and down==b.get(f'down4_{n}d')
                      and ratio==b.get(f'ratio_{n}d') else 'BLOCKED' if len(tail)<n else 'FAIL'}
    return {'aggregate_arithmetic':results,'underlying_events':'BLOCKED: full eligible frames not retained',
            'universe_basis':'current-session price-eligible/current frames; not point-in-time historical breadth'}


def source_inventory(publications):
    manifest=[];cache={};reader=[];future=[]
    for item,d in publications:
        for b in d['bursts']+d.get('watchlist',{}).get('top',[]):
            e=b.get('evidence') or {};src=e.get('source') or {};key=src.get('sha256')
            if not key:continue
            p=OBJECTS/(key+'.json.gz')
            if not p.exists():
                manifest.append({'publication':item['sha256'],'ticker':b['ticker'],'source':key,'status':'BLOCKED'});continue
            if key not in cache:
                obj=json.loads(gzip.decompress(p.read_bytes()));cache[key]=obj
            obj=cache[key]
            check=inspect_frame(obj,item['session'])
            manifest.append({'publication':item['sha256'],'capture_time':item['published_at'],
                'session':item['session'],'ticker':b['ticker'],'security_name':b.get('name'),
                'symbol_basis':'receipt-bound ticker; no retained permanent security ID or corporate-action master',
                'source':key,'path':p.relative_to(ROOT).as_posix(),'file_sha256':sha(p.read_bytes()),
                'content_hash_matches':provenance.digest(obj)==key,'basis':d['run'].get('input_basis'),
                'capture_class':'retained contemporaneous normalized candidate frame',
                'redistribution':'existing repository object; provider entitlement/licensing not established by retention',
                **check})
        for b in d['bursts']:
            cl=b.get('claude') or {};ri=(b.get('evidence') or {}).get('reader_input')
            if not cl:continue
            outcome={'publication':item['sha256'],'session':item['session'],'ticker':b['ticker'],
                'source':cl.get('source'),'grade':b['grade'],'mechanical':b['grade_mechanical'],
                'reader_input':ri,'attempts':cl.get('attempts',[]),'replay':[]}
            n=((b.get('evidence') or {}).get('source') or {}).get('rows')
            leg=b['quality'].get('leg') or {}
            outcome['original_chart_leg_complete'] = (leg.get('start',n) >= n-85) if n else None
            metrics={'quality_grade':b['grade_mechanical'],'reader_evidence':{'version':1,'checks':{
                c['letter']:{'status':c['status'],'values':c['values']} for c in b['quality']['checks']}}}
            for attempt in cl.get('attempts',[]):
                response=attempt.get('response') or {};text=response.get('text')
                result={'request_sha256':attempt.get('request_sha256'),'raw_text_sha256':response.get('text_sha256'),
                        'original_outcome':attempt.get('outcome')}
                if text is None:result.update(status='BLOCKED',reason='original raw reply not retained')
                else:
                    result['hash_matches']=sha(text.encode())==response['text_sha256']
                    try:
                        if response.get('stop_reason')=='max_tokens':raise grader.ScoreFormatError('truncated')
                        parsed=grader._validated(grader._extract_json(text))
                        reader_authority.validate(parsed,metrics,chart_seen=bool(ri and ri.get('chart_sha256')))
                        result.update(status='PASS',accepted=True,grade=parsed['grade'])
                    except (ValueError,TypeError,KeyError) as exc:
                        result.update(status='PASS' if attempt.get('outcome')=='rejected' else 'FAIL',accepted=False,
                                      reason=type(exc).__name__+': '+str(exc))
                outcome['replay'].append(result)
            reader.append(outcome)
    return manifest,cache,reader


def prefix_controls(publications,cache):
    import pandas as pd
    results=[]
    for item,d in publications:
        available=sorted([b for b in d['bursts'] if (b.get('evidence') or {}).get('source',{}).get('sha256') in cache],key=lambda b:b['ticker'])
        # An outcome-independent representative per publication, plus every
        # actually reviewed candidate with retained sources.
        selected={b['ticker']:b for b in available[:1]+[b for b in available if b.get('claude')]}
        for b in selected.values():
            obj=cache[b['evidence']['source']['sha256']];df=provenance.frame_of(obj);at=len(df)-1
            extra=df.iloc[[-1]].copy();extra.index=pd.DatetimeIndex([sessions.next_sessions(date.fromisoformat(item['session']),1)[0]])
            for c in ('Open','High','Low','Close'):extra[c]*=11
            extra['Volume']*=17
            added=pd.concat([df,extra]);altered=added.copy();altered.iloc[-1]*=3
            expected=(scans.scan_all(df),quality.assess(df).to_dict())
            good=all((scans.scan_all(frame,at=at),quality.assess(frame,at=at).to_dict())==expected for frame in (added,altered))
            # Production pipeline has no historical at parameter; the replay
            # boundary supplies ONLY a prefix to every downstream consumer.
            a=quality.assess(df);args={k:b[k] for k in ('scan','discovery','flags','gain_pct','volume_vs_prior','dollar_volume')}
            request=grader.user_text(quality.metrics_for_model(a,b['ticker'],b['close'],args))
            prefix=altered.loc[altered.index.date<=date.fromisoformat(item['session'])]
            req2=grader.user_text(quality.metrics_for_model(quality.assess(prefix),b['ticker'],b['close'],args))
            context_equal=charts.reader_context(df,a)==charts.reader_context(prefix,quality.assess(prefix)) if hasattr(charts,'reader_context') else True
            # Planner receives frozen signal values, never the held-out tail.
            plan_equal=preview(b,account(d))==preview({**b,'close':float(prefix.iloc[-1]['Close'])},account(d))
            results.append({'session':item['session'],'publication':item['sha256'],'ticker':b['ticker'],
                            'status':'PASS' if good and request==req2 and context_equal and plan_equal else 'FAIL'})
    return results


def exceptions():
    root=ROOT/'tests/fixtures/historical-validation';results=[]
    for path in sorted(root.glob('*/input-exceptions.json.gz')):
        raw=gzip.decompress(path.read_bytes());obj=json.loads(raw)
        directory=path.with_name('universe-directory.json.gz')
        try:
            input_diagnostics.validate(obj,expected_run=obj['run'],directory_bytes=directory.read_bytes())
            status='PASS';error=None
        except Exception as exc:status='FAIL';error=str(exc)
        members=obj['exceptions']['stale']['symbols'];observed=[]
        for sym in members:
            v=obj['observations'][sym];last=v['rows'][-1]
            observed.append({'ticker':sym,'last':last,'rows_retained':len(v['rows']),
                             'rows_total':v['rows_total'],'provider_cause':'UNKNOWN'})
        results.append({'run':obj['run'],'capture':obj['capture'],'status':status,'error':error,
            'record_sha256':sha(raw),'file_sha256':sha(path.read_bytes()),'directory_sha256':sha(directory.read_bytes()),
            'basis':{k:v for k,v in obj['basis'].items() if k!='fetch_arguments'},
            'counts':obj['input_counts'],'membership':{k:v['symbols'] for k,v in obj['exceptions'].items()},
            'observed':observed,'directory':obj['directory'],'limits':obj['limits'],
            'independent_stale_check':all(x['last']['timestamp']['session']<obj['capture']['evaluated_session'] for x in observed)})
    return {'packages':results,'recurring_stale':sorted(set(results[0]['membership']['stale']) & set(results[1]['membership']['stale'])) if len(results)==2 else [],
            'newly_stale':sorted(set(results[1]['membership']['stale'])-set(results[0]['membership']['stale'])) if len(results)==2 else []}


def original_replay(publications,cache_dir):
    results=[]
    for item,d in publications:
        source=cache_dir/item['commit'];result_file=source/'result.json'
        if result_file.exists():results.append(json.loads(result_file.read_bytes()));continue
        source.mkdir(parents=True,exist_ok=True)
        # Original publication tree contains its own implementation; execution
        # SHA from retained ledger is separately recorded where available.
        archive=git('archive',item['commit'],'src','knowledge','data')
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(source,filter='data')
        (source/'data.json').write_bytes(git('show',item['commit']+':docs/data.json'))
        (source/'picks.json').write_bytes(git('show',item['commit']+':docs/picks.json'))
        ran=subprocess.run([sys.executable,str(ROOT/'tools/verify_retained_publication.py'),str(source),str(source/'data.json'),str(OBJECTS)],capture_output=True,text=True)
        try:result=json.loads(ran.stdout)
        except ValueError:result={'source_replay':'BLOCKED','error':ran.stderr[-2000:]}
        result.update(publication=item['sha256'],commit=item['commit'],session=item['session'])
        save(result_file,result);results.append(result)
    return results


def event_study(publications, sources):
    """Selected-candidate next-session closes, NOT simulated entries or P&L.

    Earliest subsequent publication carrying a bar wins; revisions remain in
    manifest. No synthesized missing bars, no breadth reconstruction.
    """
    observations=defaultdict(dict);revisions=[];seen_variants=set()
    def put(sym, bars, item, source):
        for j,bar in enumerate(bars):
            value={'bar':bar,'capture':item['published_at'],'publication':item['sha256'],
                   'source':source,'prior_close':bars[j-1]['c'] if j else None}
            old=observations[sym].get(bar['date'])
            # Publication chart values are explicitly rounded to 4 decimals.
            # Don't call that display normalization a provider revision.
            normalized=tuple(round(bar[k],4) if k!='v' else bar[k] for k in ('o','h','l','c','v'))
            variant=(sym,bar['date'],normalized)
            if old and variant not in seen_variants and any(
                    (round(old['bar'][k],4) if k!='v' else old['bar'][k])!=normalized[j]
                    for j,k in enumerate(('o','h','l','c','v'))):
                revisions.append({'ticker':sym,'date':bar['date'],'original':old,'later':value,
                                  'classification':'changed observation; adjustment/revision cause unresolved'})
            seen_variants.add(variant)
            observations[sym].setdefault(bar['date'],value)
    for item,d in publications:
        for b in d['bursts']+d.get('watchlist',{}).get('top',[]):
            key=(b.get('evidence') or {}).get('source',{}).get('sha256')
            obj=sources.get(key)
            if obj:
                cols=dict(zip(obj['columns'],obj['values']))
                bars=[{'date':day,**{short:cols[long][j] for short,long in
                       [('o','Open'),('h','High'),('l','Low'),('c','Close'),('v','Volume')]}}
                      for j,day in enumerate(obj['dates'])]
                put(b['ticker'],bars,item,key)
            else:put(b['ticker'],b.get('series',[]),item,'publication series')
        for sym,v in (d.get('observations') or {}).get('symbols',{}).items():
            if isinstance(v,dict) and v.get('date'):
                put(sym,v.get('history') or [v],item,'publication observation')
    rows=[];seen=set()
    for item,d in publications:
        for b in sorted(d['bursts'],key=lambda b:b['ticker']):
            key=(item['session'],b['ticker'])
            if key in seen:continue
            seen.add(key)
            day=str(sessions.next_sessions(date.fromisoformat(item['session']),1)[0]);v=observations[b['ticker']].get(day)
            # The outcome bar's OWN predecessor must match, not a convenient
            # copy of the signal from a different (possibly pre-split) capture.
            match=bool(v and v['prior_close'] is not None and abs(v['prior_close']-b['close'])<.0001)
            result=None if not v or not match else round(100*(v['bar']['c']/b['close']-1),4)
            rows.append({'session':item['session'],'ticker':b['ticker'],'publication':item['sha256'],
                'next_session':day,'later_observation':v,'basis_overlap_match':match,
                'close_change_pct':result,'mechanical_A':b['grade_mechanical'] in ('A+','A'),
                'accepted_A':reader_coverage.accepted(b) and b['grade'] in ('A+','A')})
    def stat(group):
        xs=sorted(x['close_change_pct'] for x in group if x['close_change_pct'] is not None)
        n=len(xs)
        return {'population':len(group),'observed':n,'missing_or_basis_unknown':len(group)-n,
            'mean_close_change_pct':round(sum(xs)/n,4) if n else None,
            'median_close_change_pct':round((xs[(n-1)//2]+xs[n//2])/2,4) if n else None,
            'positive':sum(x>0 for x in xs),'negative':sum(x<0 for x in xs),
            'min':min(xs) if n else None,'max':max(xs) if n else None}
    return {'class':'COMPONENT/EVENT STUDY', 'horizon':'one subsequent XNYS close; not an entry-to-exit return',
        'limitations':['Selected source population; observation availability is also selected.',
            'Earliest candidate publication per symbol/session; revisions are not independent events.',
            'Overlapping dates and repeated symbols are dependent; no causal selection effect.',
            'Matching one overlapping close does not establish full corporate-action compatibility.',
            'No costs or execution attached to signal-close observations; not portfolio performance.'],
        'revised_bar_observations':len(revisions),'revisions':revisions,
        'groups':{'discovery':stat(rows),'mechanical_A':stat([x for x in rows if x['mechanical_A']]),
                  'accepted_A':stat([x for x in rows if x['accepted_A']])},'rows':rows}


def current_simulation(publications,cache):
    """Production scan + quality + planning over retained candidate prefixes.

    No breadth from this pool. No old response is attached to a new request.
    Recorded aggregate market permission is an explicit retained constraint.
    """
    out=[]
    for item,d in publications:
        prior={b['ticker']:b for b in d['bursts']}
        frames={s:provenance.frame_of(cache[b['evidence']['source']['sha256']])
                for s,b in prior.items() if (b.get('evidence') or {}).get('source',{}).get('sha256') in cache}
        for sym in frames:
            frames[sym]=frames[sym].loc[frames[sym].index.date<=date.fromisoformat(item['session'])]
        if not frames:
            out.append({'session':item['session'],'publication':item['sha256'],'status':'BLOCKED','reason':'No exact retained source frames'});continue
        uni=universe.Universe(sorted(frames),{s:prior[s].get('name','') for s in frames},
            {s:set(prior[s].get('flags',[])) for s in frames},'selected historical candidate pool',
            item['published_at'],{},'simulation only')
        rows,measured,errors=pipeline.scan_frames(frames,uni,pipeline.RunReport())
        changed=[]
        for b in rows:
            old=prior[b['ticker']]
            if (b['scan'],b['grade_mechanical'],b['score'])!=(old['scan'],old['grade_mechanical'],old['score']):
                changed.append({'ticker':b['ticker'],'old':[old['scan'],old['grade_mechanical'],old['score']],
                                'new':[b['scan'],b['grade_mechanical'],b['score']]})
            b['claude']=None;b['grade']=b['grade_mechanical']
        tickets,_,budget=pipeline._make_plans(rows,account(d),d['breadth']['regime'],0,
                            date.fromisoformat(item['session']),require_reader=True)
        out.append({'session':item['session'],'publication':item['sha256'],'status':'PASS' if not errors else 'FAIL',
            'scope':'CURRENT-POLICY HISTORICAL SIMULATION; retained candidate pool only',
            'measured':measured,'candidates':len(rows),'errors':errors,'mechanical_changes':changed,
            'reader':'UNKNOWN: prospective request v2 differs; zero authorized new reviews',
            'market':'recorded aggregate, underlying events unavailable','tickets':tickets})
    return out


def publication_revisions(publications):
    seen={};out=[]
    for item,d in publications:
        day=item['session']
        if day in seen:
            pi,pd=seen[day];before={b['ticker']:b for b in pd['bursts']};after={b['ticker']:b for b in d['bursts']}
            common=set(before)&set(after)
            changes={field:sorted(s for s in common if before[s].get(field)!=after[s].get(field))
                     for field in ('scan','grade_mechanical','grade','volume','prev_volume','plan')}
            out.append({'session':day,'original':pi['sha256'],'revision':item['sha256'],
                'added':sorted(set(after)-set(before)),'removed':sorted(set(before)-set(after)),
                'changes':changes,'breadth_changed':pd['breadth']!=d['breadth'],
                'tickets_changed':pd['trades']!=d['trades'],
                'structural_feasibility_changed':sorted(s for s in common if preview(before[s],account(pd))['eligible']!=preview(after[s],account(d))['eligible'])})
        seen[day]=(item,d)
    return out


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--ref',default=BASE);p.add_argument('--original-replay',action='store_true')
    p.add_argument('--simulate',action='store_true')
    p.add_argument('--cache',type=Path,default=ROOT/'scratchpad/poc-cache');args=p.parse_args(argv)
    out=args.output.resolve()
    if out == ROOT/'docs' or ROOT/'docs' in out.parents:
        raise ValueError('isolated output directory outside docs required')
    socket.socket.connect=socket.socket.connect_ex=socket.create_connection=offline
    start=time.monotonic();allpubs,excluded=inventory(args.ref)
    pubs=[(i,d) for i,d in allpubs if i['version']=='v2' and i['session']>='2026-09-11']
    summaries=[];traces=[]
    for item,d in pubs:
        s,t=trace(d,item);s['breadth_check']=breadth_arithmetic(d);summaries.append(s);traces.extend(t)
    manifests,objects,readers=source_inventory(pubs)
    prefixes=prefix_controls(pubs,objects)
    ev=event_study(pubs,objects)
    originals=original_replay(pubs,args.cache) if args.original_replay else []
    result={'version':VERSION,'baseline':BASE,'ref':args.ref,'clock':CLOCK,'spec_sha256':sha((ROOT/SPEC).read_bytes()),
        'implementation_tree':git('rev-parse','HEAD').decode().strip(),
        'implementation_files':{str(f.relative_to(ROOT)):sha(f.read_bytes()) for f in
            sorted((ROOT/'src').glob('*.py'))+sorted((ROOT/'knowledge').glob('*.md'))},
        'runner_sha256':sha(Path(__file__).read_bytes()),
        'publications':len(pubs),'unique_sessions':len({i['session'] for i,d in pubs}),
        'candidate_publications':len(traces),'unique_candidate_sessions':len({(r['session'],r['ticker']) for r in traces}),
        'sessions':summaries,'source_manifest':manifests,'source_objects_unique':len(objects),
        'original_replay':originals,'reader_replay':readers,'prefix_controls':prefixes,'exceptions':exceptions(),
        'current_policy_simulation':current_simulation(pubs,objects) if args.simulate else [],
        'same_session_revisions':publication_revisions(pubs),
        'performance':{'published_tickets':sum(len(d['trades']) for i,d in pubs),
            'retained_picks':len(json.loads(git('show',args.ref+':docs/picks.json'))['picks']),
            'settled':0,'expectancy':None,'portfolio_drawdown':None,'status':'BLOCKED',
            'reason':'No actual published plans; no execution or cost-adjusted expectancy sample.',
            'cost_scenarios_bps_per_side':[0,5,20],'cost_scenarios_status':'BLOCKED: no settled published plans',
            'intraday_data':'not retained','point_in_time_universe':'not retained'},
        'limits':['All eleven sessions are development/challenge observations, not a blind holdout.',
            'No full input universes or benchmark source series retained; candidate frames cannot validate underlying breadth events.',
            'Counterfactuals reuse recorded opinions as interventions, not responses to a changed request.',
            'Original early pre-provenance publications cannot be fully reconstructed from source frames.'],
        'runtime':{'python':sys.version.split()[0],**{x:importlib.metadata.version(x) for x in ['pandas','numpy','anthropic','exchange_calendars']}}}
    save(args.output/'results.json',result)
    for name,rows in [('candidate-traces',traces),('event-study',ev)]:
        buf=io.BytesIO()
        with gzip.GzipFile(filename='',mode='wb',fileobj=buf,mtime=0) as z:z.write(encode(rows))
        (args.output/(name+'.json.gz')).write_bytes(buf.getvalue())
    metrics={'elapsed_seconds':round(time.monotonic()-start,3),'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
             'artifact_bytes':sum(p.stat().st_size for p in args.output.glob('*') if p.is_file())}
    save(args.output/'runtime.json',metrics)
    print(json.dumps({'publications':len(pubs),'sessions':result['unique_sessions'],'candidates':len(traces),
        'source_objects':len(objects),'original_replay':Counter(x.get('source_replay') for x in originals),
        'oracle_failures':sum(bool(r['oracle_errors']) for r in traces),
        'prefix_failures':sum(r['status']!='PASS' for r in prefixes),'event_groups':ev['groups'],**metrics}))


if __name__=='__main__':main()
