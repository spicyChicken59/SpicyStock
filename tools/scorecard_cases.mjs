export async function checkScorecard({browser, base, data, open, check, eq, shotsDir}) {
  console.log('-- public model scorecard');
  const app = await open(browser, base, '/tests/fixtures/page/full.json', '2026-09-10T22:31:00Z', 1280, {hash:'#/record'});
  const {page} = app;
  const card = page.locator('#record-card');
  const render = async d => {await page.evaluate(r => SCStock.render(r, new Date('2026-09-10T22:31:00Z')), d); await page.waitForTimeout(120);};
  check('current pipeline publishes complete population accounting', data.scorecard.contract_version === 2);
  check('model and personal outcomes are visibly distinct', /not your trading results/.test(await card.innerText()));
  const sc = data.scorecard;
  eq('all outcome buckets reconcile', ['settled','open','pending','uncertain','not_filled','unmeasured','unreadable','unscored'].reduce((n,k)=>n+sc[k],0), sc.plans);
  for (const [label,value] of [['published plans',sc.plans],['resolved',sc.settled],['open',sc.open],['uncertain',sc.uncertain]]) {
    check('printed recorded ' + label, (await card.innerText()).includes(label + '\n' + value));
  }
  check('rate denominator names resolved plans', (await card.locator('[data-scorecard-rates]').innerText()).includes(sc.settled + ' resolved plans'));
  await card.locator('summary').focus(); await page.keyboard.press('Enter');
  eq('method disclosure works by keyboard', await card.locator('details').evaluate(el=>el.open), true);
  check('benchmark coverage count shown', (await card.innerText()).includes(sc.benchmark_pairs + ' matched resolved plans'));
  check('price basis and replay version disclosed', (await card.innerText()).includes(sc.replay_rules_version) && (await card.innerText()).includes('split-adjusted'));
  const small = structuredClone(data);
  Object.assign(small.scorecard, {plans:9,settled:3,wins:1,losses:1,breakeven:1,open:1,pending:1,uncertain:1,not_filled:1,unmeasured:1,unreadable:1,unscored:0,uncertain_reasons:[{...sc.uncertain_reasons[0],count:1}],readable:false,win_rate:.99,avg_r:99,median_r:99});
  // Deliberately retained numeric values must not bypass the publication's
  // unreadable flag. The page does not recompute a trading statistic.
  await render(small);
  check('small sample warning is immediate', /Small sample: 3 settled/.test(await card.locator('[data-scorecard-sample]').innerText()));
  check('small sample never prints stale rate values', !(await card.locator('[data-scorecard-rates]').innerText()).includes('99'));
  check('missing and pending remain visible', /1 awaiting first session.*1 missing or stale/.test(await card.locator('[data-scorecard-accounting]').innerText()));
  const before = await card.innerText();
  await page.evaluate(async () => {const b=SCStock.data.bursts.find(b=>SCStock.data.trades.includes(b.ticker));SCStock.navigate('#/explore/bursts/'+b.ticker);});
  await page.waitForTimeout(100); await page.locator('#detail [data-select-plan]').click();
  await page.waitForFunction(()=>SCStock.follow.list().some(x=>x.plan_selection));
  await page.evaluate(()=>SCStock.navigate('#/record')); await page.waitForTimeout(100);
  eq('personal selection never changes public scorecard', await card.innerText(), before);
  const legacy = structuredClone(data); delete legacy.scorecard.contract_version;
  await render(legacy);
  check('legacy summary admits incomplete denominator', /total may be incomplete/.test(await card.locator('[data-scorecard-legacy]').innerText()));
  const limited = structuredClone(data); limited.scorecard.population.at_capacity=true; limited.scorecard.population.problem='one malformed pick dropped';
  await render(limited);
  check('retention and invalid-record limits disclosed', /at capacity.*malformed/.test(await card.locator('[data-scorecard-limit]').textContent()));
  await render(small);
  for (const width of [1280,390,320]) for (const theme of ['dark','light']) {
    await page.setViewportSize({width,height:900}); await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
    await page.waitForTimeout(60);
    check('scorecard fits '+width+' '+theme, await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    if (shotsDir) await card.screenshot({path:shotsDir+'/scorecard-'+width+'-'+theme+'.png'});
  }
  await render(data);
  if (shotsDir) {await page.setViewportSize({width:1280,height:900});await card.screenshot({path:shotsDir+'/scorecard-readable.png'});}
  eq('scorecard page errors', app.errors, []);
  await app.context.close();
}
