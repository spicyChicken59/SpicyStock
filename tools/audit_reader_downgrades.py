"""Reproduce a bounded, manually adjudicated reader/source audit from Git.

No model, provider, pipeline execution, outcomes or historical writes. Claim
labels are review judgements below; only extraction, arithmetic, source identity
and quoted-measurement checks are automated. This is not an NLP grader.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter
import gzip
import hashlib
import json
import re
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = '2d790e1f95a8df746d9e7cb7870d16444462725d'
EXECUTIONS = [
 '74bff884dcc1ee4d9c835d4e1560b1dc0ddeff87', '7380a97605c7f16eb902421486c491a95b957cd7',
 '3d60ae15b9f615f6364358affb944a67e869e566', '0233b309a43d3c3f64d30ee974d2be15d1fcea28',
 '7859ae081a1cbb12ef4c2f949ee0e699df893bc8', 'bd34b8b65cbeb0951a659f4002734170e43c26a5',
 'ebcdea34464b9090e7734ca543be8733d39fc20a', '89d31535fe1684711fb6c15e8541b573b1963f03',
 '25eb5b2688a3ba1ceecc01083a7cb6046cc62aea']
FILES = ['src/grader.py', 'src/pipeline.py', 'src/quality.py', 'src/discovery.py',
         'src/provenance.py', 'knowledge/strategy.md', 'knowledge/method.md', 'knowledge/reaction-discovery.md']
# Reviewed claim incidence. Indices are validated against the frozen publication
# order and reader identities, not used by production. Repeated revisions stay.
CHECK_CLAIMS = {
 'N': [61],
 'Y': [0,6,7,8,9,10,11,12,13,19,20,21,22,23,24,25,26,33,34,35,36,38,42,45,47,51,52,54,62,63,64,88,89,90,91,100,101,102,106],
 'RE': [1,2,3,4,5,7,9,10,12,15,16,17,18,20,22,25,27,29,30,31,33,34,35,37,46,47,51,52,54,56,57,58,59,60,62,64,65,66,67,68,70,72,74,75,76,77,78,80,81,82,83,84,85,88,89,93,94,95,97,98,100,101,104,105,107],
 'VOL': [1,2,5,6,7,8,9,10,11,12,15,18,19,20,21,22,34,43,46,47,52,53,57,58,59,66,67,69,70,77,79,83,84,85,86,88,89,90,91,92,93,94,97,98,99,100,101,102,103,104,105,106],
 'C': [39,48,49,53,55,56,57,58,59,65,66,67,68,69,70,71,75,77,78,79,80,81,82,83,92,93,95,103,104,107],
}
PERCENT_GATE = [1,2,8,14,15,19,21,24,32,40,41,44,46]
PRIOR_NOTE_VOTE = [10,12,22,26,29,33,34,37,48,49,50,51,54,55,56,57,60,62,65,66,77,78,79,84,85,91,92,94,97,98,100,103,105]
RISK_ONLY_NOTES = [37,48,57,66,79,84,91,100]
BASE_VISUAL = [1,2,3,4,5,6,7,8,9,10,11,12,14,15,16,17,18,19,20,22,23,24,26,27,28,29,30,31,32,33,34,35,37,38,39,40,41,42,43,44,46,47,48,49,50,51,52,53,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,86,87,92,93,94,95,99,103,104,105,106,107]
CLEAR_DECLINE = [55,56,59,68,69,71,77,78,79,80,81,82,83,93,95,104,107]
VOLUME_QUALITATIVE = [3,4,13,16,17,23,26,29,30,32,37,38,39,40,44,61,63]


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], stderr=subprocess.DEVNULL)


def optional(rev, path):
    try: return git('show', rev + ':' + path)
    except subprocess.CalledProcessError: return None


def digest(raw): return hashlib.sha256(raw).hexdigest()


def base_tripwire():
    """Run only the base's pure text guard, not a reader or today's prompt."""
    module = ast.parse(git('show', BASE + ':src/discovery.py'))
    fn = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'conflicting_fields')
    namespace = {'re': re}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<pinned-base-tripwire>', 'exec'), namespace)
    return namespace['conflicting_fields']


def raw_comparisons(index, row):
    """Verify the consequential superlatives against original, dated frames.

    Only signal/prior bars are read. This never reads later price performance.
    """
    if index not in (72,73,75,81,85,86,87,96,98,99,101,104):
        return None
    sha = row['evidence']['source']['sha256']
    raw = gzip.decompress(git('show', BASE + ':docs/evidence/' + sha + '.json.gz'))
    obj = json.loads(raw)
    cols = obj['columns']
    bars = [dict(zip(cols, values, strict=True)) for values in zip(*obj['values'], strict=True)]
    assert obj['dates'][-1] == row['evidence']['session']
    ranges = [round(b['High']-b['Low'], 6) for b in bars[-6:]]
    result = dict(source_sha256=sha, object_bytes_sha256=digest(raw), signal_range=ranges[-1], prior_five_ranges=ranges[:-1],
                  signal_is_narrowest=ranges[-1] < min(ranges[:-1]))
    if index in (72,85,98,101):
        assert not result['signal_is_narrowest']
    if index in (75,81):
        assert result['signal_is_narrowest']
    if index == 73:
        result['preceding_30_session_low'] = min(b['Low'] for b in bars[-31:-1])
        assert result['preceding_30_session_low'] < 68
    if index == 86:
        base = row['quality']['base']
        selected = bars[base['start_index']:base['end_index']+1]
        result['base_extrema'] = [min(b['Low'] for b in selected), max(b['High'] for b in selected)]
        assert result['base_extrema'][0] >= base['low'] and result['base_extrema'][1] <= base['high']
    if index in (87,96):
        result['signal_ohlc'] = {k: bars[-1][k] for k in ('Open','High','Low','Close')}
        result['prior_close'] = bars[-2]['Close']
    if index == 99:
        result['prior_volume'] = bars[-2]['Volume']
        assert result['prior_volume'] == 31158866
    if index == 104:
        result['signal_volume'] = bars[-1]['Volume']
        result['preceding_15_volume_min'] = min(b['Volume'] for b in bars[-16:-1])
        assert result['signal_volume'] > result['preceding_15_volume_min']
    return result


def claims(index, row):
    result = []
    cs = {c['letter']: c for c in row['quality']['checks']}
    def add(category, claim, status, basis, authority, field='reason'):
        result.append(dict(category=category, claim=claim, status=status, basis=basis,
                           authority=authority, reader_field=field))
    for letter, ids in CHECK_CLAIMS.items():
        if index in ids:
            check = cs[letter]
            assert check['status'] == 'FAIL', (index, letter, check['status'])
            add('measured_' + letter, f'{letter} fails its recorded quality test.', 'SUPPORTED',
                {'status': check['status'], 'values': check['values'], 'threshold': check['threshold']},
                'PRIMARY qualitative concept; DERIVED historical quality proxy. A failure is not a new veto.')
    if index in PERCENT_GATE:
        assert row['scan'] == 'dollar'
        add('universal_percent_gate', 'A Dollar-only candidate must meet the separate 4% discovery minimum (or its gain alone is disqualifying).',
            'CONTRADICTED', 'Historical strategy opening imposed 4% universally, but historical method/scans admitted Dollar separately. Conflict is recorded, not silently reconciled. #68 removed the stale prompt; #72 later verified primary Dollar authorship.',
            'HISTORICAL MODEL follows stale prompt; contradicted by same-revision DERIVED discovery contract. Current PRIMARY mapping also forbids it.')
    if index in PRIOR_NOTE_VOTE:
        add('no_vote_note_reference' if index in RISK_ONLY_NOTES else 'no_vote_note',
            'Prior-breakout history appears in risk commentary; its influence on the grade is unknown.' if index in RISK_ONLY_NOTES else
            'Prior-breakout success/failure is used as a quality strike or evidence of poor future odds.',
            'UNVERIFIABLE' if index in RISK_ONLY_NOTES else 'CONTRADICTED',
            'Every audited strategy prompt calls the prior-breakout note a measurement with no vote. A risk-only mention does not prove a grade vote. Only its use as authority is audited; no prior or subsequent return is recomputed or used to decide this finding.',
            'HISTORICAL MODEL; no authorized strategy vote', 'reason/key_risk')
    if index in BASE_VISUAL:
        add('base_visual', 'The described base has adverse shape (overlap, chop, decline or distribution).',
            'UNVERIFIABLE' if index < 48 else 'SUPPORTED' if index in CLEAR_DECLINE else 'PARTIALLY SUPPORTED',
            'Pre-provenance chart/source frame unavailable; C proxy is not proof of visual shape.' if index < 48 else
            'Retained chart inspected: the described decline is visible. Actual shareholder distribution is not established.' if index in CLEAR_DECLINE else
            'Retained chart inspected; the source permits shape review, but loose/orderly is qualitative and the reader does not identify exact bars. No invented numerical tightness gate is endorsed.',
            'Repository/field-guide attribution to PRIMARY quiet-base concept; DERIVED chart-reader discretion, not a verified new numerical rule')
    if index in VOLUME_QUALITATIVE:
        add('volume_strength', 'Measured volume rank/average context is too weak for a convincing burst.', 'PARTIALLY SUPPORTED',
            {'measurements': cs['VOL']['values'], 'limit': 'Source supports volume context, but no extra hard cutoff at this observed rank/average and no direct institutional-identity evidence.'},
            'PRIMARY volume concept; DERIVED rank/lookback; HISTORICAL MODEL strength judgement')
    # Every record includes risk/entry commentary. Only factual/rule assertions
    # that materially alter authority are adjudicated, not hypothetical tomorrow.
    extras = EXTRA.get(index, [])
    for category, claim, status, basis in extras:
        field = 'entry_note' if category == 'entry_authority' else 'reason'
        if (index,category) in ((9,'trend_count'),(10,'trend_count'),(15,'volume_fact'),
                (64,'trend_count'),(73,'chart_context'),(86,'institutional_fact')):
            field = 'key_risk'
        if (index,category) in ((11,'extra_veto'),(99,'base_fact')):
            field = 'entry_note'
        add(category, claim, status, basis, 'Historical prompt + retained measurements / chart, unless stated otherwise', field)
    assert result, index
    return result

# Manual claim splits supplement the common incidence above. Each status applies
# to the normalized single claim, never to an entire response or final grade.
EXTRA = {
 0:[('trend_duration','The move started 54 sessions ago.','CONTRADICTED','Y records 57; 54 is the leg length. Trend-age failure itself is supported.')],
 9:[('trend_count','There were three prior breakouts.','CONTRADICTED','Y records two prior; today is the third.')],
 10:[('trend_count','There were three prior breakouts in this move.','CONTRADICTED','Y records two prior.')],
 11:[('extra_veto','Y is a mechanical veto.','CONTRADICTED','Historical quality has only up_days and not_linear vetoes; Y is a weighted check.')],
 12:[('range_order','The current range is smaller than all five prior bars.','UNVERIFIABLE','RE vs maximum <1 proves only smaller than the largest, not every bar; exact old frames unavailable.')],
 13:[('entry_authority','Any open above today close is over the entry ceiling.','CONTRADICTED','Close and entry ceiling are different plan concepts; no plan exists in this red publication.')],
 15:[('volume_fact','Signal volume is below average.','CONTRADICTED','VOL volume_vs_avg50=1.04; below prior=0.92 is a different fact.')],
 28:[('gap_math','The intraday high-low range is explained by an overnight gap.','CONTRADICTED','High-low excludes the prior-close-to-open gap. A gap-down recovery is not the gap-and-fade described in the prompt.')],
 35:[('entry_authority','Opening above the signal close needs a tight first five minutes.','UNSUPPORTED','The prompt/plan uses the first 30 minutes and a computed ceiling, not this additional condition.')],
 37:[('entry_authority','A gap above close by 0.5% imposes an extra entry restriction.','UNSUPPORTED','No such 0.5% entry cutoff exists in the applicable source contract.')],
 39:[('extra_veto','C is a mechanical veto.','CONTRADICTED','C is weighted and can lower quality; it is not either named veto.')],
 40:[('range_order','The 3.0% signal range is the smallest in the visible consolidation.','CONTRADICTED','RE vs_prior_5=1.0 and status PASS; vs_prior_10=0.91. It is not smaller than the prior five maximum on the decision grid.')],
 41:[('signal_fact','The signal is a red open-to-close bar closing near its low.','CONTRADICTED','H passes with close above open and close near high; the recorded Dollar body is positive.')],
 43:[('discovery_conflation','A negative close-to-close gain cannot be a Dollar burst.','CONTRADICTED','Dollar measures close-open. Prior-close sign is not admission authority; source-specific down-close remains context.')],
 46:[('signal_fact','A negative prior-close change makes the candlestick red.','CONTRADICTED','Dollar admission and H establish close>open; prior close is a different reference.')],
 47:[('check_count','Y, RE and VOL are three of the six scoring letters.','CONTRADICTED','RE and VOL are extra checks, not the six weighted letters.')],
 49:[('linearity_gate','R2=0.34 by itself establishes failed linearity.','PARTIALLY SUPPORTED','R2 is correctly quoted; L passes via ER. Qualitative chop is allowed, but an AND gate cannot replace the recorded OR.')],
 50:[('threshold_fact','0.34 is the A+ giveback ceiling.','CONTRADICTED','C A+ giveback is 0.25; 0.34 is ordinary pass.'),('threshold_fact','Tightness 0.62 is borderline.','UNSUPPORTED','No cutoff at 0.62; it is below the 0.70 A+ tightness boundary.')],
 53:[('source_attribution','20 sessions is a universal Bonde ceiling.','PARTIALLY SUPPORTED','Historical quality deliberately reconciles 3–20, 3–10 and 5–40 source variants with partial status; 20 is the selected pass band, not a timeless universal ceiling.')],
 61:[('threshold_fact','Tightness 0.69 barely passes.','UNSUPPORTED','Ordinary pass <=1.0; 0.69 also passes the tighter 0.70 component. No extra cutoff supplied.'),('linearity_gate','ER=0.25 establishes deficient linearity despite R2.','PARTIALLY SUPPORTED','ER quoted accurately, but OR rule passes via R2. Visual concern may remain; deterministic L is not FAIL.')],
 64:[('trend_count','There were four prior breakouts.','CONTRADICTED','Three prior are recorded; today is the fourth.')],
 65:[('route_penalty','Only a thin Dollar admission holds the setup together.','CONTRADICTED','The applicable strategy expressly says Dollar-only is neither weaker nor stronger merely for its route.')],
 67:[('source_attribution','20 sessions is a universal Bonde ceiling.','PARTIALLY SUPPORTED','Selected pass window differs from later 5–40 source variant; historical code carries partial, not universal exclusion.')],
 71:[('no_vote_note','Low price / high signal gain / an event-study cell disqualifies the candidate.','CONTRADICTED','The prompt calls these measurements with no vote. No study outcomes are used or evaluated in this audit.')],
 72:[('range_order','The signal is the smallest-range day of the last five.','CONTRADICTED','Retained ranges: signal 3.965; prior include 1.687, 2.0, 3.36, 3.57 and 4.275. RE fail does not mean minimum.')],
 73:[('measured_C','The selected base has two sessions and C is PARTIAL.','SUPPORTED','Recorded C base_sessions=2, status PARTIAL; the 3-session pass minimum is the actual contract.'),('base_duration','Two bars are categorically no consolidation under any reading.','PARTIALLY SUPPORTED','Short-base concern is authorized; historical code explicitly gives two bars partial credit, not a veto.'),('chart_context','The stock was range-bound at 68–72 for six weeks.','CONTRADICTED','Retained chart/source show the advance from lower prices during that interval; the last six weeks were not confined to that band.'),('entry_authority','72.12 is the entry ceiling.','UNSUPPORTED','72.12 is the measured base high; no plan/ticket/ceiling was computed in red regime.')],
 74:[('discovery_conflation','A negative close-to-close signal means no valid Dollar burst.','CONTRADICTED','Dollar body is positive and independent of the prior-close change; RE failure is a separate legitimate quality concern.')],
 75:[('range_order','Signal range is narrowest of the prior-five window.','SUPPORTED','Retained signal range 1.98 is below each prior range: 7.245, 2.46, 4.9, 3.99, 2.04.')],
 81:[('range_order','Signal range is weakest of the prior-five window.','SUPPORTED','Retained signal range 2.99 is below each prior range: 4.75, 3.22, 3.82, 4.78, 3.64.')],
 85:[('range_order','0.47x the prior maximum makes the signal narrowest.','CONTRADICTED','Signal 13.937; prior include 10.87, 11.49, 12.483 and 13.738, all narrower.')],
 86:[('base_bounds','Multiple base wicks pierce both measured box boundaries.','CONTRADICTED','The measured box high/low bound the retained base bars; no lower-bound breach in the base.'),('linearity_fact','ER=0.42 and R2=0.63 are borderline.','PARTIALLY SUPPORTED','Both values are accurately quoted and both pass; borderline is qualitative, not another threshold.'),('institutional_fact','Institutional participation is absent.','UNVERIFIABLE','Lower relative volume does not identify participant types or prove their absence.')],
 87:[('gap_fact','Most close-to-close gain occurred in the overnight gap.','SUPPORTED','gap_pct=7.1 vs gain_pct=10.79; source/chart retain open=29.76, prior close=27.80, close=30.80.'),('gap_math','The actionable high-low range expansion happened before the session.','CONTRADICTED','The overnight gap is not part of high-low range. The quoted 3.7 percentage-point contribution is on the prior-close denominator; actual intraday high-low range is 4.1% of close.'),('setup_identity','A gap proves an EP/news catalyst.','UNVERIFIABLE','The prompt permits flagging an apparent catalyst; no news/catalyst source is retained.'),('threshold_fact','10.79% is disqualifying because near 15%.','CONTRADICTED','10.79<15, and the high-gain note has no grade vote.'),('threshold_fact','0.33 is at the A+ giveback limit.','CONTRADICTED','A+ giveback limit is 0.25; normal pass limit 0.34.'),('plan_fact','The published stop/entry plan is structurally wrong.','UNVERIFIABLE','Red regime contains no plan, stop, or ticket to validate; chart-review concern is not evidence of a published plan defect.')],
 91:[('route_penalty','Dollar is weaker because it lacks the burst route volume requirement.','CONTRADICTED','Applicable prompt forbids route-based penalty. A VOL quality failure is distinct and permitted.')],
 94:[('volume_fact','There is no volume confirmation of any kind.','PARTIALLY SUPPORTED','Below-prior 0.45 is true, but average ratio=1.46 and rank=9 provide mixed context; no participation-absence proof.')],
 96:[('gap_fact','Most close-to-close gain occurred overnight.','SUPPORTED','Same retained signal facts as earlier Sep 21 WBD revision.'),('gap_math','3.7% is actual intraday range.','CONTRADICTED','High-low range is recorded 4.1%; open-to-close body is about 3.49%, a different measurement.'),('setup_identity','Gap appearance proves EP/news identity.','UNVERIFIABLE','No retained catalyst source; only an apparent visual possibility is authorized.'),('overhead_fact','August highs near 29 form overhead above the signal.','CONTRADICTED','Signal open=29.76 and close=30.80, above base high=28.99.'),('entry_authority','31.50 is the entry ceiling.','UNSUPPORTED','No plan exists and no rule/source establishes that level as the ceiling.')],
 98:[('range_order','0.47x the maximum makes the signal narrowest.','CONTRADICTED','Same retained range ordering as earlier MEDP revision.')],
 99:[('base_fact','The base high is near 147.','CONTRADICTED','Recorded base high=156.92; no alternate base or plan level is identified.'),('volume_fact','The prior volume was already modest.','CONTRADICTED','Prior=31,158,866; signal/average=.79 and signal/prior=.26 imply prior about 3x the signal-relative average; chart shows a large spike.')],
 101:[('range_order','Signal range did not exceed any of the prior five.','CONTRADICTED','Raw frame ordering checked; the signal exceeds some prior ranges despite failing against their maximum.')],
 104:[('volume_fact','The signal is the quietest volume bar in weeks.','CONTRADICTED','Raw frame ordering checked; prior bars in the preceding weeks have lower volume.')],
}


def build():
    tripwire = base_tripwire()
    inventory = json.loads(git('show', BASE + ':docs/input-truthfulness/2026-09-22-quality-audit.json'))
    pubs = [p for p in inventory['publications'] if p['version'] == 'v2']
    assert len(pubs) == len(EXECUTIONS) == 9
    contracts, records = [], []
    for pub, execution in zip(pubs, EXECUTIONS, strict=True):
        raw = git('show', pub['commit'] + ':docs/data.json')
        assert digest(raw) == pub['sha256']
        data = json.loads(raw)
        source = {}
        for path in FILES:
            original = optional(execution, path)
            at_publication = optional(pub['commit'], path)
            assert original == at_publication, (pub['commit'], path)
            source[path] = None if original is None else {
                'git_blob': git('rev-parse', execution + ':' + path).decode().strip(), 'sha256': digest(original)}
        old = source['knowledge/strategy.md']['git_blob'] == 'b4c7ccb60da18c3f196dfb74178e7e6a344d5c9d'
        contract = dict(publication=pub['commit'], blob=pub['blob'], sha256=pub['sha256'],
            session=pub['session'], published_at=pub['published_at'], run_id=pub['run_id'], execution_revision=execution,
            sources=source, prompt_generation='universal-percent opening' if old else 'discovery-specific opening',
            rules_version=pub['rules_version'], max_reads=12, attempts_per_candidate=2,
            grade_bands=[[9,'A+'],[8,'A'],[6.5,'B'],[5,'C']], authority='confirm or lower; never raise; independent chart/measurement defect',
            fields='ticker,close,quality_grade,quality_score,quality_passes,quality_a_plus_checks,checklist,vetoes,notes,reclass,unreadable,base,leg,burst,scan,flags,gain_pct,volume_vs_prior,dollar_volume' + ('' if old else ',discovery'),
            not_yet_landed=['#68 scan-specific prompt and tripwire', '#72 primary Dollar attribution', '#73 source/request retention'] if old else [],
            source_limit='Chart not retained; pre-provenance facts cannot certify full frame/request' if old else 'Content-addressed frame/chart/system/request evidence retained')
        contracts.append(contract)
        for b in data['bursts']:
            cl=b.get('claude') or {}
            if cl.get('source') != 'claude': continue
            i=len(records); q=b['quality']; e=b.get('evidence') or {}
            routes = ['burst','dollar'] if b['scan']=='both' else [b['scan']]
            block = {'inapplicable_rules': {family: data['rules'][family]
                     for family in ('burst','dollar') if family not in routes}}
            records.append(dict(index=i, session=pub['session'], publication=pub['commit'], ticker=b['ticker'], family=b['scan'],
                mechanical_score=q['score'], a_plus_tally=q['a_plus_count'], mechanical_grade=b['grade_mechanical'],
                checks={c['letter']:{k:c[k] for k in ['status','a_plus','values','threshold']} for c in q['checks']}, vetoes=q['vetoes'],
                reader={k:cl.get(k) for k in ['score','grade','returned_grade','reason','key_risk','entry_note','source','model','chart_seen']},
                final_grade=b['grade'], regime=data['breadth']['regime']['verdict'], plan=b.get('plan'), ticket=b['ticker'] in data['trades'],
                provenance={'evidence_id':e.get('id'), 'source':e.get('source'), 'reader_input':e.get('reader_input'),
                    'reader_sha256':e.get('reader_sha256'), 'raw_reader_sha256':digest(json.dumps(cl,sort_keys=True).encode())},
                prompt_blob=source['knowledge/strategy.md']['git_blob'], rules_version=pub['rules_version'],
                raw_comparisons=raw_comparisons(i,b),
                base_current_comparison={'tripwire_conflicting_fields': tripwire(block,cl),
                    'scope': 'Historical words through pinned-main pure discovery text guard only; no current model score or final grade inferred.'},
                claims=claims(i,b)))
    assert len(records)==108 and sum(r['mechanical_grade']=='A+' for r in records)==14
    assert all(r['regime']=='red' and r['plan'] is None and not r['ticket'] for r in records)
    def count(rs):
        flat=[c for r in rs for c in r['claims']]
        return {'candidates':len(rs), 'transitions':dict(Counter(r['mechanical_grade']+'->'+r['final_grade'] for r in rs)),
            'reader_scores':dict(sorted(Counter(r['reader']['score'] for r in rs).items())),
            'grade_steps':dict(Counter(['A+','A','B','C','skip'].index(r['final_grade'])-['A+','A','B','C','skip'].index(r['mechanical_grade']) for r in rs)),
            'mechanical_score_minus_reader_score':dict(sorted(Counter(round(r['mechanical_score']-r['reader']['score'],1) for r in rs).items())),
            'claim_statuses':dict(Counter(c['status'] for c in flat)),
            'claim_categories':dict(Counter(c['category'] for c in flat)),
            'candidates_with_unsupported':sum(any(c['status']=='UNSUPPORTED' for c in r['claims']) for r in rs),
            'candidates_with_contradicted':sum(any(c['status']=='CONTRADICTED' for c in r['claims']) for r in rs),
            'no_fully_supported_adverse_claim_in_audited_set':[r['ticker'] for r in rs if not any(c['status']=='SUPPORTED' for c in r['claims'])]}
    return {'audit_version':1,'base':BASE,'population':'All retained real v2 reader-completed candidates; repeated publications distinct',
        'method':'Manually reviewed material factual/rule claims; counts are of this explicit claim inventory, not all sentences or an overall reader score. Prospective entry scenarios and future-risk rhetoric are not certified facts. No outcomes used.',
        'contracts':contracts, 'summary':count(records),'by_publication':{p['publication']:count([r for r in records if r['publication']==p['publication']]) for p in contracts},'decisions':records}


def a_plus_markdown(result):
    lines = ['# Fourteen retained mechanical A+ assessments — 22 September 2026', '',
        'Generated from the [claim inventory](2026-09-22-reader-downgrade-audit.json) by',
        '`tools/audit_reader_downgrades.py`. See the [audit](2026-09-22-reader-downgrade-audit.md)',
        'for source hierarchy, historical contracts, limitations and verification.', '',
        'Each revision is distinct. Check statuses and A+ flags below are recorded mechanical',
        'evidence, not new grades. Reader text is quoted historical model assertion, not source',
        'authority. All fourteen have no veto, red regime, no plan and no ticket.',
        'The JSON retains exact threshold strings, rule identities and provenance hashes.', '']
    for r in result['decisions']:
        if r['mechanical_grade'] != 'A+': continue
        lines += [f"## {r['session']} · {r['ticker']} · {r['publication'][:7]}", '',
            f"Publication `{r['publication']}`; inventory index {r['index']}; discovery **{r['family']}**.",
            f"Mechanical **{r['mechanical_score']}/10, A+ tally {r['a_plus_tally']}** → recorded reader **{r['reader']['score']} / {r['reader']['grade']}** → final **{r['final_grade']}**.",
            f"Rules `{r['rules_version']}`; prompt blob `{r['prompt_blob']}`.",
            ('Source frame/chart/request identity retained; original source replay available.' if r['provenance']['source'] else
             'Pre-provenance: checklist and reply retained; exact chart, frame and request unavailable.'), '',
            '| Check | Recorded status | A+ flag | Measurements |', '|---|---|---|---|']
        for letter,c in r['checks'].items():
            values = '; '.join(f'{k}={json.dumps(v)}' for k,v in c['values'].items())
            lines.append(f"| {letter} | {c['status']} | {str(c['a_plus']).lower()} | {values} |")
        lines += ['', '**Exact recorded reader text**', '']
        for field in ('reason','key_risk','entry_note'):
            lines += [f"{field}:", '', '> ' + str(r['reader'][field]).replace('\n','\n> '), '']
        lines += ['| Individual claim | Evidence status | Basis |', '|---|---|---|']
        for c in r['claims']:
            basis = c['basis'] if isinstance(c['basis'],str) else json.dumps(c['basis'],sort_keys=True)
            lines.append('| ' + ' | '.join(str(v).replace('|','/').replace('\n',' ') for v in (c['claim'],c['status'],basis)) + ' |')
        blocked = r['base_current_comparison']['tripwire_conflicting_fields']
        lines += ['', '**Offline comparison with verified main:** ' + (
            'its existing discovery tripwire rejects these historical fields: ' + ', '.join(blocked) + '.' if blocked else
            'its discovery tripwire does not reject this historical response.'),
            'Contradicted/unsupported authority claims above remain impermissible under the current source hierarchy;',
            'supported independent quality concerns remain eligible. No current model response, score or final grade is inferred.', '']
    return '\n'.join(lines)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--a-plus-output',type=Path);args=parser.parse_args()
    result=build();args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    if args.a_plus_output: args.a_plus_output.write_text(a_plus_markdown(result).rstrip()+'\n')
    print(json.dumps(result['summary'],indent=2))
