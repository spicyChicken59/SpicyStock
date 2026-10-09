/* The original 85 historical/save/isolation checks, shared by normal CI
   and the standalone entry point. Publications are frozen, never docs/data.json. */
import {mkdir} from 'node:fs/promises';
import path from 'node:path';
import {retainedWaitPublication} from './wait_explanation_cases.mjs';
export async function checkHistoricalJourneys({browser,base,open,check,shotsDir}) {
  console.log('-- historical journeys: frozen September 25 publication');
  const retained=await retainedWaitPublication(),errors=[],clock='2026-09-28T13:15:00Z';
  const output=shotsDir||'';
  if(shotsDir) await mkdir(output,{recursive:true});
  const capture=async(page,options)=>{if(shotsDir) await page.screenshot(options);};
  for(const width of [390,320,1280]) for(const theme of ['dark','light']) {
    const {context,page,errors:pageErrors}=await open(browser,base,'/historical-frozen.json',clock,width,{
      height:844,theme,touch:width<500,hash:'#/explore/bursts/MSFT',
      beforeLoad:async page=>{
        await page.route('**/*',r=>r.request().url().startsWith(base)?r.continue():r.abort());
        await page.route('**/historical-frozen.json*',r=>r.fulfill({json:retained}));
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
    await page.waitForSelector('[data-study-original="CRL"]');
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
  check('no browser exceptions',errors.length===0,errors);
}
