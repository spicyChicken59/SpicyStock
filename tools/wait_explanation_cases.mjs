/* Frozen publication acceptance shared by the normal page gate and isolated
   source controls. Scenario projections are synthetic, never new market data. */
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import path from 'node:path';
const ROOT = path.resolve(import.meta.dirname, '..');
const FIXTURE = 'tests/fixtures/wait-explanations/';
export async function retainedWaitPublication() {
  const source = JSON.parse(await readFile(path.join(ROOT, FIXTURE, 'source.json'), 'utf8'));
  const bytes = gunzipSync(await readFile(path.join(ROOT, FIXTURE, '2026-09-25.json.gz')));
  if (createHash('sha256').update(bytes).digest('hex') !== source.uncompressed_sha256) throw Error('Frozen September 25 publication changed');
  return JSON.parse(bytes);
}
const clone = x => structuredClone(x);
const nextText = p => p.locator('#decision-gates .sc-hint').textContent();
const blockers = p => p.locator('#detail [data-all-blockers]').textContent();
const sha = b => createHash('sha256').update(b).digest('hex');

export async function checkWaitExplanations({browser, base, open, check, eq, shotsDir}) {
  console.log('-- wait explanations: frozen September 25 / September 24 and labelled synthetic controls');
  const retained = await retainedWaitPublication(), original = JSON.stringify(retained);
  const prior = JSON.parse(gunzipSync(await readFile(path.join(ROOT, 'tests/fixtures/chart-keyboard/2026-09-24.json.gz'))));
  const full = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/page/full.json'), 'utf8'));
  const geometry = [];
  const shot = async (p, name) => {
    if (!shotsDir) return;
    await mkdir(shotsDir, {recursive:true});
    await p.screenshot({path:path.join(shotsDir, `wait-${name}.png`)});
  };
  const render = async (p, data, now, ticker = 'MSFT') => {
    // Narrow only the candidate list for repeated scenario renders. Run, calendar,
    // policy and the selected candidate are untouched copies of frozen evidence.
    data=clone(data);
    if (data.bursts.length > 10) data.bursts=data.bursts.filter(b=>b.ticker===ticker);
    data.observations={}; // no saved observations participate in these stage/clock projections
    await p.evaluate(({data,now,ticker}) => { SCStock.render(data,new Date(now)); SCStock.navigate('#/explore/bursts/'+ticker); },{data,now,ticker});
  };
  const noOrders = async (p,label) => {
    eq(label+' no copy controls',await p.locator('#detail [data-copy], #order-sheet [data-copy]').count(),0);
    eq(label+' no actionable order rows',await p.locator('#order-sheet tbody tr[data-ticker]').count(),0);
  };
  const measure = async (p,selector,label) => {
    const g = await p.locator(selector).evaluate(e => {
      const r=e.getBoundingClientRect();
      return {width:r.width,height:r.height,left:r.left,right:r.right,client:e.clientWidth,scroll:e.scrollWidth,viewport:innerWidth,document:document.documentElement.scrollWidth};
    });
    geometry.push({label,...g});
    check(label+' readable rendered geometry',g.width>180&&g.height>20&&g.left>=-1&&g.right<=g.viewport+1&&g.scroll<=g.client+1&&g.document<=g.viewport+1,g);
  };
  function projection(mutator) {
    const d=clone(retained), b=d.bursts.find(b=>b.ticker==='MSFT');
    d.fixture='synthetic planning-stage explanation control';
    d.breadth.regime={...d.breadth.regime,verdict:'green',size_multiplier:1};
    d.bursts=[b]; d.trades=[]; d.watchlist.top=[];
    d.cash_budget={...d.cash_budget,within:[],beyond:[],cut:[],skipped:[]};
    b.grade='A'; b.vetoes=[]; b.reader_coverage='accepted';
    b.claude={source:'claude',grade:'A',score:8,reason:'Synthetic accepted review control'};
    b.evidence={...b.evidence,version:1,planning:{inputs:null,error:null},gate:{reason:null,detail:null,ticket:false}};
    mutator(d,b); return d;
  }
  const error=projection((d,b)=>{
    b.evidence.planning={inputs:{ticker:b.ticker,close:b.close},error:'synthetic invalid planner input'};
    b.evidence.gate={reason:'plan_error',detail:'synthetic invalid planner input',ticket:false};
  });
  const legacy=projection((d,b)=>{delete b.evidence;delete d.rules.pipeline.reader_policy;});
  const attempted=projection((d,b)=>{b.evidence.planning={inputs:{ticker:b.ticker}};b.evidence.gate={};});
  const gateOnly=projection((d,b)=>{delete b.evidence.planning;b.evidence.gate={reason:'plan_error',detail:'synthetic recorded planner error'};});
  const gateWithoutDetail=projection((d,b)=>{delete b.evidence.planning;b.evidence.gate={reason:'plan_error'};});
  const readerSkip=projection((d,b)=>{
    b.reader_coverage='not_selected_budget';b.claude={source:'not_graded'};b.evidence.gate={reason:'reader_coverage'};
  });
  const unknownPolicy=clone(readerSkip);unknownPolicy.rules.pipeline.reader_policy='unknown_future_policy';
  const oldPolicy=clone(readerSkip);delete oldPolicy.rules.pipeline.reader_policy;
  const absentInputs=clone(retained);delete absentInputs.bursts.find(b=>b.ticker==='MSFT').evidence.planning.inputs;
  const cases=[
    ['planner-error',error,['Planning failed','synthetic invalid planner input'],['not evaluated','skipped']],
    ['legacy-unknown',legacy,['Planning evidence unavailable'],['not evaluated','Planning skipped','Planning failed']],
    ['attempted-unknown',attempted,['Planning was attempted','outcome is unavailable'],['not evaluated','Planning skipped','Planning failed']],
    ['gate-error',gateOnly,['Planning failed','synthetic recorded planner error'],['not evaluated','skipped']],
    ['gate-error-without-detail',gateWithoutDetail,['Planning failed','recorded a planner error without further detail'],['not evaluated','skipped']],
    ['reader-skip',readerSkip,['Planning skipped','accepted reader review'],['Planning failed']],
    ['unknown-policy',unknownPolicy,['Planning evidence unavailable'],['Planning skipped']],
    ['legacy-policy',oldPolicy,['Planning evidence unavailable'],['Planning skipped']],
    ['missing-stage-inputs',absentInputs,['Planning evidence unavailable','Market permission: RED','Review:'],['Planning skipped']],
  ];
  for(const width of [390,320,1280]) for(const theme of ['dark','light']) {
    const label=`${width}/${theme}`;
    const {page:p,context,errors}=await open(browser,base,'/wait-frozen.json','2026-09-28T21:00:00Z',width,{
      height:844,theme,touch:width<500,lens:'all',hash:'#/explore/bursts/MSFT',reducedMotion:'reduce',
      beforeLoad:async p=>{
        await p.route('**/*',r=>r.request().url().startsWith(base)?r.continue():r.abort());
        await p.route('**/wait-frozen.json*',r=>r.fulfill({json:retained}));
      }
    });
    try {
      // An unchanged market/reader control must pass even on the reviewed source.
      const fullPending=await nextText(p);
      check(label+' full genuine record does not skip pending Monday',fullPending.includes('2026-09-28')&&!fullPending.includes('2026-09-29'),fullPending);
      const initial=await blockers(p);
      check(label+' independent RED and rejected review retained',initial.includes('Market permission: RED')&&initial.includes('outside the permitted criterion'));
      check(label+' known early-gate skip is recorded',initial.includes('Planning skipped')&&initial.includes('market gate')&&!initial.includes('Planning failed'),initial);
      const timing=[
        ['pre-close','2026-09-28T13:15:00Z',['next market session','2026-09-28']],
        ['in-session','2026-09-28T19:59:59Z',['2026-09-28','still in progress']],
        ['close-buffer','2026-09-28T20:14:59Z',['2026-09-28','market-data buffer']],
        ['completion-boundary','2026-09-28T20:15:00Z',['2026-09-28','awaiting its evening evaluation']],
        ['after-buffer','2026-09-28T20:15:01Z',['2026-09-28','awaiting its evening evaluation']],
        ['pre-primary','2026-09-28T21:00:00Z',['2026-09-28','awaiting its evening evaluation']],
        ['delayed','2026-09-29T01:00:00Z',['2026-09-28','delayed, missing or failed']],
        ['missing-next-morning','2026-09-29T13:15:00Z',['2026-09-28','delayed, missing or failed']],
        ['multiple-missing','2026-09-29T21:00:00Z',['2026-09-29','delayed, missing or failed']],
        ['weekend','2026-09-27T16:00:00Z',['next market session','2026-09-28']],
        ['outside-calendar','2026-12-25T21:00:00Z',['calendar','cannot establish']],
      ];
      for(const [name,now,need] of timing) {
        await render(p,retained,now);
        const t=await nextText(p);
        check(label+' '+name+' evaluation explanation',need.every(s=>t.includes(s)),t);
        if(['completion-boundary','after-buffer','pre-primary','delayed','missing-next-morning'].includes(name))
          check(label+' '+name+' does not jump to Tuesday',!t.includes('2026-09-29'),t);
        await noOrders(p,label+' '+name);
        if(['pre-primary','delayed'].includes(name)) {
          await p.locator('#decision-gates details').evaluate(e=>e.open=true);
          await p.locator('#decision-gates').scrollIntoViewIfNeeded();
          await measure(p,'#decision-gates .sc-hint',label+' '+name);
          await shot(p,`${width}-${theme}-${name}`);
        }
      }
      const failed=clone(retained);failed.run.status='failed';
      await render(p,failed,'2026-09-28T21:00:00Z');
      check(label+' explicit failed run distinguished',(await nextText(p)).includes('loaded run failed'));
      for(const key of ['calendar','published_at']) {
        const missing=clone(retained);delete missing.run[key];
        await render(p,missing,'2026-09-28T21:00:00Z');
        check(label+' missing '+key+' evidence is unknown',(await nextText(p)).includes('cannot establish'));
      }
      const invalid=clone(retained);invalid.run.calendar.schedule.sessions[0].closes_at='invalid';
      await render(p,invalid,'2026-09-28T21:00:00Z');
      check(label+' malformed calendar not bypassed',(await nextText(p)).includes('cannot establish'));
      // Only the date/publication state is projected. The XNYS schedule itself
      // is byte-for-byte archived evidence: September 7 is absent, September 8 exists.
      const holiday=clone(retained);holiday.fixture='synthetic publication date over retained XNYS holiday schedule';
      holiday.run.session=holiday.run.expected_session='2026-09-04';holiday.run.published_at='2026-09-04T23:00:00Z';
      for(const now of ['2026-09-05T16:00:00Z','2026-09-07T21:00:00Z','2026-09-08T13:15:00Z']) {
        await render(p,holiday,now);
        const t=await nextText(p);
        check(label+' holiday/weekend '+now+' uses archived session',t.includes('next market session')&&t.includes('2026-09-08')&&!t.includes('2026-09-07'),t);
      }
      for(const [name,data,need,absent] of cases) {
        await render(p,data,'2026-09-28T13:15:00Z');
        const t=await blockers(p);
        check(label+' '+name+' stage evidence',need.every(s=>t.includes(s))&&absent.every(s=>!t.includes(s)),t);
        await noOrders(p,label+' '+name);
        eq(label+' '+name+' no plan/levels fabricated',await p.evaluate(()=>SCStock.model.byId['bursts:MSFT'].plan),null);
        if(['planner-error','legacy-unknown'].includes(name)) {
          await p.locator('[data-all-blockers]').scrollIntoViewIfNeeded();
          await measure(p,'[data-all-blockers]',label+' '+name);
          await shot(p,`${width}-${theme}-${name}`);
        }
      }
      const overlap=clone(error);overlap.breadth.regime.verdict='red';overlap.bursts[0].grade='C';overlap.bursts[0].claude={source:'fallback'};
      await render(p,overlap,'2026-09-28T13:15:00Z');
      const overlapText=await blockers(p);
      check(label+' planner failure does not erase independent blockers',['Planning failed','Market permission: RED','Final quality: C','Review:'].every(s=>overlapText.includes(s)),overlapText);
      // Producer-generated synthetic controls, already frozen by make_fixture --check.
      for(const [ticker,need] of [['TSLA',['Plan produced but ineligible', '4%']],['AMD',['Whole-share size: 4','Allocation:','4-slot']]]) {
        await render(p,full,'2026-09-10T22:31:00Z',ticker);
        const t=await blockers(p);
        check(label+' '+ticker+' recorded refusal',need.every(s=>t.includes(s))&&!t.includes('Planning skipped'),t);
        eq(label+' '+ticker+' no copy on refused detail',await p.locator('#detail [data-copy]').count(),0);
        eq(label+' '+ticker+' plan unchanged',await p.evaluate(t=>SCStock.model.byId['bursts:'+t].plan,ticker),full.bursts.find(b=>b.ticker===ticker).plan);
      }
      const zero=clone(full),zeroRow=zero.bursts.find(b=>b.ticker==='AMD');zeroRow.plan.shares=0;
      zero.cash_budget.cut=zero.cash_budget.cut.filter(c=>c.ticker!=='AMD');zeroRow.evidence.gate={reason:'no_shares',detail:'synthetic zero whole shares'};
      await render(p,zero,'2026-09-10T22:31:00Z','AMD');
      check(label+' explicit zero-size outcome',(await blockers(p)).includes('Whole-share size: 0'));
      eq(label+' zero size no copy',await p.locator('#detail [data-copy]').count(),0);
      await render(p,full,'2026-09-10T22:31:00Z','AAPL');
      eq(label+' ordinary eligible plan no invented blocker',await p.locator('#detail [data-all-blockers]').count(),0);
      eq(label+' eligible plan levels unchanged',await p.evaluate(()=>SCStock.model.byId['bursts:AAPL'].plan),full.bursts.find(b=>b.ticker==='AAPL').plan);
      await p.locator('#disc-plan').evaluate(e=>e.open=true);
      eq(label+' ordinary eligible plan retains its published copy',await p.locator('#disc-plan [data-copy]').count(),1);
      eq(label+' browser errors',errors,[]);
    } finally {await context.close();}

    // Unpinned native page clock: the same DOM survives close, buffer, focus,
    // visibility/pageshow and the existing bounded tick. No application hook
    // bypasses the event handlers under test.
    let served=retained;
    const live=await open(browser,base,'/wait-live.json',null,width,{height:844,theme,lens:'all',hash:'#/explore/bursts/MSFT',reducedMotion:'reduce',
      beforeLoad:async p=>{
        await p.clock.install({time:new Date('2026-09-28T19:59:59Z')});
        await p.clock.pauseAt(new Date('2026-09-28T19:59:59Z'));
        await p.route('**/*',r=>r.request().url().startsWith(base)?r.continue():r.abort());
        await p.route('**/wait-live.json*',r=>r.fulfill({json:served}));
      }});
    try {
      const q=live.page;
      await q.locator('#decision-gates details').evaluate(e=>e.open=true);
      await q.locator('#disc-provenance').evaluate(e=>e.open=true);
      await q.locator('#decision-gates summary').focus();
      await q.evaluate(()=>{window.__held={chart:document.querySelector('#chart'),gates:document.querySelector('#decision-gates details'),focus:document.activeElement,hash:location.hash,y:scrollY,charts:SCStock.liveCharts()};});
      for(const [now,event,need] of [
        ['2026-09-28T20:00:01Z','focus','market-data buffer'],
        ['2026-09-28T20:15:00Z','visibilitychange','awaiting its evening evaluation'],
        ['2026-09-28T21:00:00Z','pageshow','awaiting its evening evaluation'],
        ['2026-09-29T01:00:00Z','tick','delayed, missing or failed']
      ]) {
        await q.clock.setSystemTime(new Date(now));
        if(event==='tick') await q.clock.runFor(30000);
        else await q.evaluate(event=>(event==='visibilitychange'?document:window).dispatchEvent(new Event(event)),event);
        check(label+' '+event+' updates evaluation',(await nextText(q)).includes(need),await nextText(q));
        const kept=await q.evaluate(()=>({chart:__held.chart===document.querySelector('#chart'),gates:__held.gates===document.querySelector('#decision-gates details'),focus:__held.focus===document.activeElement,hash:__held.hash===location.hash,scroll:Math.abs(scrollY-__held.y)<2,charts:SCStock.liveCharts()===__held.charts,open:document.querySelector('#decision-gates details').open&&document.querySelector('#disc-provenance').open}));
        check(label+' '+event+' keeps charts selection focus disclosures and scroll',Object.values(kept).every(Boolean),kept);
      }
      // A same-bytes refresh must not reset the page either.
      await q.evaluate(()=>SCStock.checkUpdates());
      await q.waitForFunction(()=>document.querySelector('#refresh-said').dataset.outcome==='unchanged');
      check(label+' unchanged refresh keeps evaluation',(await nextText(q)).includes('delayed, missing or failed'));
      check(label+' unchanged refresh keeps chart and focus',await q.evaluate(()=>__held.chart===document.querySelector('#chart')&&__held.focus===document.activeElement));
      // Arrival uses two real retained records, not an invented future run.
      served=prior;
      await q.clock.setSystemTime(new Date('2026-09-25T21:00:00Z'));
      await q.evaluate(data=>SCStock.render(data),prior);
      await q.locator('#decision-gates details').evaluate(e=>e.open=true);
      check(label+' genuine September 25 evaluation pending',(await nextText(q)).includes('2026-09-25')&&(await nextText(q)).includes('awaiting its evening evaluation'));
      await q.clock.setSystemTime(new Date('2026-09-26T00:40:00Z'));
      served=retained;
      await q.locator('#check-updates').focus();
      await q.evaluate(()=>SCStock.checkUpdates());
      await q.waitForFunction(()=>document.querySelector('#refresh-said').dataset.outcome==='newer');
      const arrived=await nextText(q);
      check(label+' newly arrived genuine record acknowledged',arrived.includes('Loaded publication: 2026-09-25')&&arrived.includes('next market session')&&arrived.includes('2026-09-28')&&!arrived.includes('awaiting its evening evaluation'),arrived);
      eq(label+' newer refresh preserves wait disclosure',await q.locator('#decision-gates details').evaluate(e=>e.open),true);
      eq(label+' newer refresh focus preserved',await q.evaluate(()=>document.activeElement.id),'check-updates');
      eq(label+' newer refresh keeps selected stock',await q.evaluate(()=>location.hash),'#/explore/bursts/MSFT');
      await noOrders(q,label+' genuine arrival');
      eq(label+' real arrival record unchanged',await q.evaluate(()=>JSON.stringify(SCStock.data)),original);
      eq(label+' clock/refresh browser errors',live.errors,[]);
    } finally {await live.context.close();}
  }
  eq('frozen wait publication unchanged in harness',JSON.stringify(retained),original);
  if(shotsDir) await writeFile(path.join(shotsDir,'wait-geometry.json'),JSON.stringify({source:JSON.parse(await readFile(path.join(ROOT,FIXTURE,'source.json'))),application_sha256:sha(await readFile(process.env.SCSTOCK_APP||path.join(ROOT,'docs/app.js'))),geometry},null,2)+'\n');
}
