/* The original 85 historical/save/isolation checks, shared by normal CI
   and the standalone entry point. Publications are frozen, never docs/data.json. */
import {mkdir,readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {retainedWaitPublication} from './wait_explanation_cases.mjs';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
// The study's cases are read from docs/historical-validation/, byte copies the
// archive's 21-day window never prunes. The archive directories the cases came
// from are served 404 here on purpose -- the 24 September record left the live
// archive with the 16 October publication -- so a page that still asked the
// archive for a case would fail by name rather than pass on today's checkout.
async function studyCases() {
  const study=JSON.parse(await readFile(path.join(ROOT,'docs','historical-validation.json'),'utf8'));
  const crl=study.cases.find(c=>c.ticker==='CRL');
  return {records:[...new Set(study.cases.map(c=>c.entry.source))],crl,
    evidence:await readFile(path.join(ROOT,'docs','historical-validation',crl.entry.path))};
}
export async function checkHistoricalJourneys({browser,base,open,check,shotsDir}) {
  console.log('-- historical journeys: frozen September 25 publication');
  const retained=await retainedWaitPublication(),errors=[],clock='2026-09-28T13:15:00Z';
  const cases=await studyCases(),archived=new RegExp('/history/('+cases.records.join('|')+')/');
  const output=shotsDir||'';
  if(shotsDir) await mkdir(output,{recursive:true});
  const capture=async(page,options)=>{if(shotsDir) await page.screenshot(options);};
  for(const width of [390,320,1280]) for(const theme of ['dark','light']) {
    const archiveRequests=[],studyRequests=[];
    const {context,page,errors:pageErrors}=await open(browser,base,'/historical-frozen.json',clock,width,{
      height:844,theme,touch:width<500,hash:'#/explore/bursts/MSFT',
      beforeLoad:async page=>{
        await page.route('**/*',r=>r.request().url().startsWith(base)?r.continue():r.abort());
        await page.route('**/historical-frozen.json*',r=>r.fulfill({json:retained}));
        await page.route(u=>archived.test(u.pathname),r=>r.fulfill({status:404,body:'gone from the rolling archive'}));
        page.on('request',r=>{const u=r.url();if(/\/history\/[a-f0-9]{40}\//.test(u)) archiveRequests.push(u);if(u.includes('/historical-validation/')) studyRequests.push(u);});
      }
    });
    const gates=await page.locator('#decision-gates').textContent().catch(()=> '');
    check(`${width}/${theme} independent wait gates`,gates.includes('4,758')&&gates.includes('4,780')&&gates.includes('incomplete')&&gates.includes('11 accepted')&&gates.includes('0 accepted, non-vetoed'));
    check(`${width}/${theme} rejected review visible`,await page.locator('[data-all-blockers]').count()>0);
    check(`${width}/${theme} exact retained reader rejection`,(await page.locator('[data-all-blockers]').textContent().catch(()=>'' )).includes('outside the permitted criterion'));
    const savedBefore=await page.evaluate(()=>JSON.stringify(Object.fromEntries(Object.entries(localStorage).filter(([k])=>k.includes('following')))));
    const original=await page.evaluate(()=>JSON.stringify(SCStock.data));
    if(['baseline','omission'].includes(process.env.SCSTOCK_HISTORICAL_CONTROL)) {await capture(page, {path:path.join(output,`${width}-${theme}-before.png`)});await context.close();break;}
    await capture(page, {path:path.join(output,`${width}-${theme}-wait.png`)});
    await page.locator('#decision-gates').evaluate(e=>e.scrollIntoView({block:'start'}));
    await page.locator('#decision-gates summary').click();
    await capture(page, {path:path.join(output,`${width}-${theme}-gates.png`)});
    await page.locator('#decision-gates summary').click();
    await page.locator('[data-all-blockers]').evaluate(e=>e.scrollIntoView({block:'center'}));
    await page.mouse.move(1,1); await page.keyboard.press('Escape'); await page.waitForTimeout(160);
    await capture(page, {path:path.join(output,`${width}-${theme}-reader-wait.png`)});
    await page.evaluate(()=>{location.hash='#/record';});
    await page.waitForSelector('[data-study-inspect="CRL"]');
    await page.locator('[data-study-inspect="CRL"]').click();
    await page.waitForSelector('[data-study-case="CRL"] [data-study-original="CRL"], [data-study-case="CRL"] [role="alert"]');
    const inspected=await page.locator('[data-study-original="CRL"]').count()===1;
    check(`${width}/${theme} frozen case inspected from the study files`,inspected,await page.locator('[data-study-case="CRL"] [role="alert"]').allTextContents());
    check(`${width}/${theme} no request to the rolling archive for a case`,archiveRequests.length===0,archiveRequests);
    check(`${width}/${theme} the case's context and evidence were read from historical-validation/`,
      studyRequests.some(u=>u.endsWith('/historical-validation/'+cases.crl.entry.source+'/record.json'))&&studyRequests.some(u=>u.endsWith('/historical-validation/'+cases.crl.entry.path)),studyRequests);
    if(!inspected){errors.push(...pageErrors);await context.close();continue;}
    check(`${width}/${theme} historical reader image identity`,await page.locator('[data-study-original="CRL"] a[href="evidence/b32a2e0d0b7b81387cbdc39e55e68a78c7a93e5ed7284b71470659a4d373ce18.png"]').count()===1);
    check(`${width}/${theme} frozen case has no order copy`,await page.locator('[data-study-original="CRL"] button').filter({hasText:'Copy order'}).count()===0);
    // The initial drawing uses a detached width. Compare outcome toggling only
    // after the chart's first attached layout has selected its date-axis ticks.
    await page.waitForFunction(()=>{
      const chart=document.querySelector('[data-study-original="CRL"] .sc-chart--stock');
      return chart && chart.clientWidth>0 && chart.geometry().width===chart.clientWidth;
    });
    const before=await page.locator('[data-study-original="CRL"] [data-panel]').textContent();
    await page.locator('[data-study-original="CRL"]').evaluate(e=>e.scrollIntoView({block:'start'}));
    await capture(page, {path:path.join(output,`${width}-${theme}-frozen.png`)});
    await page.locator('[data-study-outcome="CRL"] summary').click();
    check(`${width}/${theme} outcome reveal keeps earlier chart`,before===await page.locator('[data-study-original="CRL"] [data-panel]').textContent());
    await page.locator('[data-study-original="CRL"]').scrollIntoViewIfNeeded();
    await capture(page, {path:path.join(output,`${width}-${theme}-historical.png`)});
    const geometry=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth,
      charts:[...document.querySelectorAll('#historical-evidence svg')].map(e=>({width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height})).filter(x=>x.width)}));
    check(`${width}/${theme} page geometry`,geometry.document<=geometry.viewport+1,geometry);
    check(`${width}/${theme} rendered historical chart geometry`,geometry.charts.some(x=>x.width>200&&x.height>100),geometry.charts);
    check(`${width}/${theme} current record unchanged`,original===await page.evaluate(()=>JSON.stringify(SCStock.data)));
    check(`${width}/${theme} reveal leaves saved originals untouched`,savedBefore===await page.evaluate(()=>JSON.stringify(Object.fromEntries(Object.entries(localStorage).filter(([k])=>k.includes('following'))))));
    await page.locator('[data-study-save="CRL"]').click();
    try { await page.waitForSelector('#saved[open]',{timeout:5000}); }
    catch(error) { console.error('historical save failure',await page.locator('[data-study-save="CRL"]').textContent(),errors);throw error; }
    const savedOriginal=await page.evaluate(()=>JSON.stringify(Object.fromEntries(Object.entries(localStorage).filter(([k])=>k.includes('following')))));
    check(`${width}/${theme} historical original saved for research`,savedOriginal.includes('CRL')&&savedOriginal.includes('2026-09-24'));
    await capture(page, {path:path.join(output,`${width}-${theme}-saved.png`)});
    await page.goBack(); await page.waitForSelector('#saved[open]',{state:'hidden'}); await page.waitForSelector('#view-record:not([hidden])');
    await page.locator('[data-study-outcome="CRL"] summary').click();
    await page.locator('[data-study-outcome="CRL"] summary').click();
    check(`${width}/${theme} outcome toggle preserves saved original`,savedOriginal===await page.evaluate(()=>JSON.stringify(Object.fromEntries(Object.entries(localStorage).filter(([k])=>k.includes('following'))))));
    await page.goBack();await page.waitForTimeout(150);
    check(`${width}/${theme} Back restores current view`,await page.locator('#view-explore').isVisible());
    await page.reload();await page.waitForFunction(()=>document.documentElement.hasAttribute('data-ss-rendered'));
    check(`${width}/${theme} refresh keeps current identity`,original===await page.evaluate(()=>JSON.stringify(SCStock.data)));
    errors.push(...pageErrors);
    await context.close();
  }
  // A frozen case file that is not the study's bytes, or is missing, ends in
  // its own sentence and shows nothing: the page verifies the digest over the
  // served bytes and never falls back to the archive.
  for(const [name,respond,expected] of [
    ['tampered',r=>r.fulfill({status:200,contentType:'application/json',body:Buffer.concat([cases.evidence,Buffer.from(' ')])}),'integrity check'],
    // past the 256 KiB bound the archive's own files are held to: refused
    // before it is hashed, in the bound's own words rather than the digest's
    ['oversize',r=>r.fulfill({status:200,contentType:'application/json',body:Buffer.concat([cases.evidence,Buffer.alloc(256*1024,' ')])}),'exceeds the supported bound'],
    ['missing',r=>r.fulfill({status:404,body:'not found'}),'unavailable in the published study files']]) {
    const archiveRequests=[];
    const {context,page,errors:pageErrors}=await open(browser,base,'/historical-frozen.json',clock,1280,{
      height:844,theme:'dark',hash:'#/record',
      beforeLoad:async page=>{
        await page.route('**/*',r=>r.request().url().startsWith(base)?r.continue():r.abort());
        await page.route('**/historical-frozen.json*',r=>r.fulfill({json:retained}));
        await page.route(u=>archived.test(u.pathname),r=>r.fulfill({status:404,body:'gone from the rolling archive'}));
        await page.route(u=>u.pathname.endsWith('/historical-validation/'+cases.crl.entry.path),respond);
        page.on('request',r=>{if(/\/history\/[a-f0-9]{40}\//.test(r.url())) archiveRequests.push(r.url());});
      }
    });
    await page.waitForSelector('[data-study-inspect="CRL"]');
    // Chromium reports the deliberate 404 on the console after the page has
    // handled the response, so the one expected report is awaited, bounded,
    // rather than read off the list at an instant of the driver's choosing.
    const expected404=name==='missing'?page.waitForEvent('console',{predicate:m=>m.type()==='error'&&/status of 404/.test(m.text()),timeout:5000}).then(()=>true,()=>false):Promise.resolve(false);
    await page.locator('[data-study-inspect="CRL"]').click();
    await page.waitForSelector('[data-study-case="CRL"] [data-study-original="CRL"], [data-study-case="CRL"] [role="alert"]');
    const alerts=await page.locator('[data-study-case="CRL"] [role="alert"]').allTextContents();
    check(`${name} frozen evidence is refused in its own sentence`,alerts.length===1&&alerts[0].includes(expected),alerts);
    check(`${name} frozen evidence shows no original`,await page.locator('[data-study-original="CRL"]').count()===0);
    check(`${name} frozen evidence asks the rolling archive for nothing`,archiveRequests.length===0,archiveRequests);
    check(`${name} frozen evidence leaves Inspect available again`,await page.locator('[data-study-inspect="CRL"]').isEnabled());
    // The missing case is served 404 on purpose, which Chromium reports on
    // the console once; that one report is the route doing its job and is
    // not a page exception. Any other console error still fails below.
    const reported=await expected404;
    const notFound=pageErrors.map((e,i)=>/status of 404/.test(String(e))?i:-1).filter(i=>i>=0);
    check(`${name} frozen evidence produced ${name==='missing'?'exactly one':'no'} console 404`,name==='missing'?reported&&notFound.length===1:notFound.length===0,pageErrors);
    errors.push(...pageErrors.filter((_,i)=>!(name==='missing'&&i===notFound[0])));
    await context.close();
  }
  check('no browser exceptions',errors.length===0,errors);
}
