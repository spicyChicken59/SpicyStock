/* Agent-operated Chromium acceptance over frozen retained data. No external calls.
   node tools/historical_journeys.mjs --output /tmp/historical-journeys
   --baseline serves untouched base HTML/JS to demonstrate the missing journey.
   --mutant removes the new gate summary; the same assertions must fail. */
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { chromium } from 'playwright';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2), output = args.includes('--output') ? args[args.indexOf('--output')+1] : '/tmp/historical-journeys';
const base = '8be007f68deaa417b85a512d2e16a37899d27011', baseline=args.includes('--baseline'), mutant=args.includes('--mutant');
const imageMutant=args.includes('--image-mutant'), readerMutant=args.includes('--reader-mutant');
const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.gz':'application/gzip'};
const server=createServer(async(req,res)=>{
  try {
    const name=decodeURIComponent(new URL(req.url,'http://localhost').pathname), file=path.resolve(root,'.'+name);
    if(!file.startsWith(root+path.sep)) throw Error('path');
    let bytes=await readFile(file);
    if(baseline && ['/docs/app.js','/docs/index.html'].includes(name)) bytes=execFileSync('git',['show',base+':'+name.slice(1)],{cwd:root});
    if(mutant && name==='/docs/app.js') bytes=Buffer.from(bytes.toString().replace('    renderDecisionGates(data);','    // isolated restored omission'));
    if(imageMutant && name==='/docs/app.js') bytes=Buffer.from(bytes.toString().replace("chart: /^[a-f0-9]{64}$/.test(imageSha) ? 'evidence/' + imageSha + '.png' : null",'chart: c.row.chart'));
    if(readerMutant && name==='/docs/app.js') bytes=Buffer.from(bytes.toString().replace("includes('ReaderAuthorityError: evidence outside criterion authority')","includes('__isolated_unmatched_error__')"));
    res.setHeader('Content-Type',mime[path.extname(file)]||'application/octet-stream');res.end(bytes);
  } catch {res.statusCode=404;res.end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const url='http://127.0.0.1:'+server.address().port, browser=await chromium.launch();
const results=[],errors=[],clock='2026-09-28T13:15:00Z';await mkdir(output,{recursive:true});
const check=(name,ok,detail)=>{results.push({name,status:ok?'PASS':'FAIL',detail});if(!ok) console.error('FAIL',name,detail||'');};
try {
  for(const width of [390,320,1280]) for(const theme of ['dark','light']) {
    const context=await browser.newContext({viewport:{width,height:844},hasTouch:width<500,isMobile:width<500});
    const page=await context.newPage();
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',r=>r.request().url().startsWith(url)?r.continue():r.abort());
    await page.addInitScript(({clock,theme})=>{window.SCStock={now:clock};localStorage.setItem('sc-theme',theme);},{clock,theme});
    await page.goto(url+'/docs/index.html#/explore/bursts/MSFT');
    await page.waitForFunction(()=>document.documentElement.hasAttribute('data-ss-rendered'));
    const gates=await page.locator('#decision-gates').textContent().catch(()=> '');
    check(`${width}/${theme} independent wait gates`,gates.includes('4,758')&&gates.includes('4,780')&&gates.includes('incomplete')&&gates.includes('11 accepted')&&gates.includes('0 accepted, non-vetoed'));
    check(`${width}/${theme} rejected review visible`,await page.locator('[data-all-blockers]').count()>0);
    check(`${width}/${theme} exact retained reader rejection`,(await page.locator('[data-all-blockers]').textContent().catch(()=>'' )).includes('outside the permitted criterion'));
    const savedBefore=await page.evaluate(()=>JSON.stringify(Object.fromEntries(Object.entries(localStorage).filter(([k])=>k.includes('following')))));
    const original=await page.evaluate(()=>JSON.stringify(SCStock.data));
    if(baseline||mutant) {await page.screenshot({path:path.join(output,`${width}-${theme}-before.png`)});await context.close();break;}
    await page.screenshot({path:path.join(output,`${width}-${theme}-wait.png`)});
    await page.locator('#decision-gates').evaluate(e=>e.scrollIntoView({block:'start'}));
    await page.locator('#decision-gates summary').click();
    await page.screenshot({path:path.join(output,`${width}-${theme}-gates.png`)});
    await page.locator('#decision-gates summary').click();
    await page.locator('[data-all-blockers]').evaluate(e=>e.scrollIntoView({block:'center'}));
    await page.mouse.move(1,1); await page.keyboard.press('Escape'); await page.waitForTimeout(160);
    await page.screenshot({path:path.join(output,`${width}-${theme}-reader-wait.png`)});
    await page.evaluate(()=>{location.hash='#/record';});
    await page.waitForSelector('[data-study-inspect="CRL"]');
    await page.locator('[data-study-inspect="CRL"]').click();
    await page.waitForSelector('[data-study-original="CRL"]');
    check(`${width}/${theme} historical reader image identity`,await page.locator('[data-study-original="CRL"] a[href="evidence/b32a2e0d0b7b81387cbdc39e55e68a78c7a93e5ed7284b71470659a4d373ce18.png"]').count()===1);
    check(`${width}/${theme} frozen case has no order copy`,await page.locator('[data-study-original="CRL"] button').filter({hasText:'Copy order'}).count()===0);
    const before=await page.locator('[data-study-original="CRL"] [data-panel]').textContent();
    await page.locator('[data-study-original="CRL"]').evaluate(e=>e.scrollIntoView({block:'start'}));
    await page.screenshot({path:path.join(output,`${width}-${theme}-frozen.png`)});
    await page.locator('[data-study-outcome="CRL"] summary').click();
    check(`${width}/${theme} outcome reveal keeps earlier chart`,before===await page.locator('[data-study-original="CRL"] [data-panel]').textContent());
    await page.locator('[data-study-original="CRL"]').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(output,`${width}-${theme}-historical.png`)});
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
    await page.screenshot({path:path.join(output,`${width}-${theme}-saved.png`)});
    await page.goBack(); await page.waitForSelector('#saved[open]',{state:'hidden'}); await page.waitForSelector('#view-record:not([hidden])');
    await page.locator('[data-study-outcome="CRL"] summary').click();
    await page.locator('[data-study-outcome="CRL"] summary').click();
    check(`${width}/${theme} outcome toggle preserves saved original`,savedOriginal===await page.evaluate(()=>JSON.stringify(Object.fromEntries(Object.entries(localStorage).filter(([k])=>k.includes('following'))))));
    await page.goBack();await page.waitForTimeout(150);
    check(`${width}/${theme} Back restores current view`,await page.locator('#view-explore').isVisible());
    await page.reload();await page.waitForFunction(()=>document.documentElement.hasAttribute('data-ss-rendered'));
    check(`${width}/${theme} refresh keeps current identity`,original===await page.evaluate(()=>JSON.stringify(SCStock.data)));
    await context.close();
  }
  check('no browser exceptions',errors.length===0,errors);
} finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
const sha=b=>createHash('sha256').update(b).digest('hex');
const report={application_revision:baseline?base:execFileSync('git',['rev-parse','HEAD'],{cwd:root}).toString().trim(),
  application_files:Object.fromEntries(await Promise.all(['docs/app.js','docs/app.css','docs/index.html','docs/historical-validation.json'].map(async p=>[p,sha(await readFile(path.join(root,p)))]))),
  publication_sha256:sha(await readFile(path.join(root,'docs/data.json'))),clock,browser:'Chromium 141.0.7390.37 / Playwright 1.56.1',
  rules_version:JSON.parse(await readFile(path.join(root,'docs/data.json'),'utf8')).app.rules_version,
  routes:['/docs/index.html#/explore/bursts/MSFT','/docs/index.html#/record','/docs/index.html#/followed/<saved-CRL-identity>'],
  viewports:[390,320,1280].map(width=>({width,height:844,touch_emulation:width<500})),themes:['dark','light'],
  mode:baseline?'baseline':mutant?'isolated omission mutant':imageMutant?'isolated historical image mutant':readerMutant?'isolated reader reason mutant':'repaired',
  physical_device:'NOT RUN',assistive_technology:'NOT RUN',human_usability:'NOT RUN',
  journey_A:'BLOCKED: no real qualifying historical ticket in the declared sample',results};
await writeFile(path.join(output,'results.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({checks:results.length,failures:results.filter(r=>r.status==='FAIL').length,output}));
if(results.some(r=>r.status==='FAIL')) process.exitCode=1;
