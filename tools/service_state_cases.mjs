/* The service state on the page: pending against stale is decided by the
   record's own calendar (the next session's open, the instant past which the
   evening guard refuses to publish a missed session) and the slot words come
   from the record's archived schedule policy (`run.delivery`, src/delivery.py).
   No fixed hour on the page. Every clock below is pinned; the record is the
   generator's `full` night (session Thu 10 Sep 2026, published 6:30 PM ET) and
   two routed copies of it -- one from before the block existed, one whose
   block is half written -- so a shape the generator never writes is put in
   front of the page. Lane B: writes no scratch record, reads no clipboard. */
import { mkdir, readFile } from 'node:fs/promises';
import path from 'node:path';

const FIXTURES = path.resolve('tests/fixtures/page');
const FRESH = '2026-09-10T22:31:00Z';
// the night Friday 11 Sep's run is due, read in ET: the session completed at 4:15 PM
const CLOCKS = {
  beforePrimary: ['2026-09-11T20:30:00Z', 'Fri 4:30 PM ET, the session complete, the primary slot ahead'],
  atPrimary: ['2026-09-11T22:16:00Z', 'Fri 6:16 PM ET, the primary slot itself'],
  betweenSlots: ['2026-09-11T23:00:00Z', 'Fri 7:00 PM ET, between the slots'],
  atRetry: ['2026-09-12T00:16:00Z', 'Fri 8:16 PM ET, the retry slot itself'],
  saturday: ['2026-09-12T14:00:00Z', 'Sat 10:00 AM ET, past both slots, the next open ahead'],
  sunday: ['2026-09-13T23:00:00Z', 'Sun 7:00 PM ET, the window still running'],
  lastSecond: ['2026-09-14T13:29:59Z', 'Mon 9:29:59 AM ET, the last second of the recovery window'],
  nextOpen: ['2026-09-14T13:30:00Z', 'Mon 9:30 AM ET, the next open: the window has ended'],
  mondayNoon: ['2026-09-14T16:00:00Z', 'Mon noon ET, the session in progress'],
  wednesday: ['2026-09-16T14:00:00Z', 'Wed 10:00 AM ET, three sessions behind'],
};
const clone = (d) => JSON.parse(JSON.stringify(d));

function routed(name, record) {
  const body = JSON.stringify(record);
  return { url: `/service-${name}.json`, beforeLoad: (p) => p.route(`**/service-${name}.json`, (route) => route.fulfill({ contentType: 'application/json', body })) };
}
const statusAt = (page, data, at) => page.evaluate(([d, a]) => {
  const s = window.SCStock.status(d, new Date(a));
  return { state: s.state, chip: s.chip, slot: s.slot === undefined ? null : s.slot, sentence: s.sentence, recoverUntil: s.recoverUntil || null, nextSession: s.nextSession || null };
}, [data, at]);
const renderAt = async (page, data, at) => { await page.evaluate(([d, a]) => { window.SCStock.render(d, new Date(a)); }, [data, at]); await page.waitForTimeout(300); };
const noOverflow = (page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);

export async function checkServiceState({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- service state: pending against stale off the record, the slots in its words');
  const full = JSON.parse(await readFile(path.join(FIXTURES, 'full.json'), 'utf8'));
  const dv = full.run.delivery;
  check('the fixture carries the delivery block this suite reads', dv && dv.version === 1 && dv.policy && dv.policy.primary_et === '18:16' && dv.policy.retry_et === '20:16', JSON.stringify(dv && dv.policy));
  eq('the fixture published between the slots, 135 minutes after completion', [dv.slot, dv.latency_minutes, dv.before_next_open], ['after_primary', 135, true]);
  // a record from before the block: no block, no rule that writes it
  const legacy = clone(full); delete legacy.run.delivery;
  for (const k of ['delivery_version', 'delivery_primary_et', 'delivery_retry_et', 'delivery_recovery_until']) delete legacy.rules.pipeline[k];
  // a half-written block: the rule is archived, the words are not readable
  const half = clone(full); half.run.delivery.policy.primary_et = 'six';

  for (const [width, theme] of [[1280, 'dark'], [390, 'light'], [320, 'dark']]) {
    const where = `${width} ${theme}`;
    const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH, width, { height: width < 400 ? 844 : 900, theme, reducedMotion: 'reduce', lens: 'all', hash: '#/method' });
    try {
      // ---- fresh: the Method view prints the record's own delivery sentence and schedule
      eq(`${where}: fresh`, await page.getAttribute('html', 'data-ss-rendered'), 'fresh');
      const meta = await page.locator('#run-meta').innerText();
      check(`${where}: Method prints the delivery sentence verbatim`, meta.includes('Delivery: ' + dv.sentence), meta.slice(meta.indexOf('Delivery'), meta.indexOf('Delivery') + 120));
      check(`${where}: Method names the archived schedule`, meta.includes('Service schedule, as this record archived it: evening runs are scheduled at 6:16 PM ET with a retry at 8:16 PM ET.'), meta);
      check(`${where}: and the recovery window in the page's one sentence for the archived policy`, meta.includes(await page.evaluate(() => window.SCStock.RECOVERY_WORDS.next_session_open)), meta);
      check(`${where}: Method says the state is read from the window, not a fixed hour`, meta.includes('not from a fixed hour'), meta);
      const strip = await page.locator('#run-strip').innerText();
      check(`${where}: the run strip carries the latency the record wrote`, strip.includes('135 min after completion'), strip);
      if (shotsDir) { await mkdir(shotsDir, { recursive: true }); await page.locator('#run-details').screenshot({ path: path.join(shotsDir, `service-method-${width}-${theme}.png`) }); }

      // ---- the night the next run is due, slot by slot
      const want = {
        beforePrimary: ['pending', 'before_primary', 'tonight’s run pending', 'its first scheduled slot is 6:16 PM ET'],
        atPrimary: ['pending', 'after_primary', 'tonight’s run pending', 'Its 6:16 PM ET slot has passed without a publication; the retry slot is 8:16 PM ET'],
        betweenSlots: ['pending', 'after_primary', 'tonight’s run pending', 'the retry slot is 8:16 PM ET'],
        atRetry: ['pending', 'after_retry', 'run pending · past both slots', 'Both scheduled slots (6:16 PM ET, 8:16 PM ET) have passed; a delayed run can still publish it until Mon 14 Sep opens (9:30 AM ET), after which it will not — check the run log.'],
        saturday: ['pending', 'after_retry', 'run pending · past both slots', 'No publication yet for Fri 11 Sep.'],
        sunday: ['pending', 'after_retry', 'run pending · past both slots', 'until Mon 14 Sep opens (9:30 AM ET)'],
        lastSecond: ['pending', 'after_retry', 'run pending · past both slots', 'a delayed run can still publish it'],
        nextOpen: ['stale1', null, 'STALE · 1 session behind', 'No run published for Fri 11 Sep, and the service’s recovery window for it ended when Mon 14 Sep opened (9:30 AM ET): it will not be published now. The calendar expected a session; check the run log. Do not place these orders.'],
        mondayNoon: ['stale1', null, 'STALE · 1 session behind', 'it will not be published now'],
        wednesday: ['stale2', null, 'STALE · 3 sessions behind', 'Something is broken'],
      };
      for (const key of Object.keys(want)) {
        const [state, slot, chip, words] = want[key], got = await statusAt(page, full, CLOCKS[key][0]);
        eq(`${where}: ${CLOCKS[key][1]} -> ${state}`, [got.state, got.slot, got.chip], [state, slot, chip]);
        check(`  and the sentence says so: ${words.slice(0, 48)}`, got.sentence.includes(words), got.sentence);
        if (state === 'pending') {
          eq('  pending names the open that ends the window, off the calendar', [got.recoverUntil, got.nextSession], ['2026-09-14T09:30:00-04:00', '2026-09-14']);
          check('  and what is below is named as the loaded session’s plan', got.sentence.includes('What is below is Thu 10 Sep’s plan — do not treat it as a new signal.'), got.sentence);
        }
      }
      // ---- the words every surface prints for those states, rendered
      for (const [key, chipRe, linked, word] of [['betweenSlots', /pending/, false, 'waiting for the evening run'], ['saturday', /pending/, true, 'waiting for the evening run'], ['nextOpen', /STALE/, true, 'stale']]) {
        await renderAt(page, full, CLOCKS[key][0]);
        await page.evaluate(() => { location.hash = '#/explore/bursts/' + window.SCStock.data.trades[0]; }); await page.waitForTimeout(250);
        const chip = await page.locator('#status-slot .sc-chip').innerText();
        check(`${where} ${key}: the masthead chip`, chipRe.test(chip), chip);
        eq(`${where} ${key}: the status line links the run log only where the sentence sends the reader there`, (await page.locator('#status-line a[href*="actions/workflows/evening.yml"]').count()) === 1, linked);
        check(`${where} ${key}: the next action withholds the orders`, (await page.locator('#next-h3').innerText()).startsWith('Do not place these orders'), await page.locator('#next-h3').innerText());
        eq(`${where} ${key}: the trade's action area withholds its order`, await page.locator('#detail .ss-action').getAttribute('data-ticket'), 'blocked');
        await page.evaluate(() => { document.getElementById('disc-plan').open = true; }); await page.waitForTimeout(100);
        check(`${where} ${key}: the plan says why, in the state's own word`, (await page.locator('#disc-plan').innerText()).includes(word), (await page.locator('#disc-plan').innerText()).slice(0, 160));
        check(`${where} ${key}: nothing scrolls sideways`, await noOverflow(page));
        if (shotsDir) await page.locator('#status-line').screenshot({ path: path.join(shotsDir, `service-${key}-${width}-${theme}.png`) });
      }
      eq(`${where}: page errors`, [...errors], []);
    } finally { await context.close(); }
  }

  // ---- a record from before the block, and one whose block is half written: the
  // boundary is still the calendar's next open; the slots are not named, and the
  // Method view says which of the two it is reading
  for (const [name, record, methodWords, sentenceWords] of [
    ['legacy', legacy, 'Delivery: this record predates the delivery block; when it landed against the service’s schedule is not recorded.', 'This record does not carry the service’s schedule, so no slot is named.'],
    ['half', half, 'Delivery: this record carries a delivery block in a shape this page cannot read, so nothing is said of when it landed.', 'This record does not carry the service’s schedule, so no slot is named.'],
  ]) {
    const r = routed(name, record);
    const { page, context, errors } = await open(browser, base, r.url, CLOCKS.saturday[0], 1280, { reducedMotion: 'reduce', lens: 'all', hash: '#/method', beforeLoad: r.beforeLoad });
    try {
      const got = await statusAt(page, record, CLOCKS.saturday[0]);
      eq(`${name}: Saturday is still pending, off the calendar's next open`, [got.state, got.slot, got.chip, got.recoverUntil], ['pending', null, 'tonight’s run pending', '2026-09-14T09:30:00-04:00']);
      check(`${name}: the sentence names the window and no slot`, got.sentence.includes('until Mon 14 Sep opens (9:30 AM ET)') && got.sentence.includes(sentenceWords) && !got.sentence.includes('6:16'), got.sentence);
      eq(`${name}: Monday's open ends it`, (await statusAt(page, record, CLOCKS.nextOpen[0])).state, 'stale1');
      const meta = await page.locator('#run-meta').innerText();
      check(`${name}: Method says what it is reading`, meta.includes(methodWords), meta.slice(meta.indexOf('Delivery'), meta.indexOf('Delivery') + 160));
      check(`${name}: the run strip carries no latency`, !(await page.locator('#run-strip').innerText()).includes('after completion'));
      const read = await page.evaluate((d) => { const x = window.SCStock.deliveryOf(d); return [x.present, x.known, x.faults.length > 0]; }, record);
      eq(`${name}: deliveryOf reads it as ${name === 'legacy' ? 'absent' : 'present and refused whole'}`, read, name === 'legacy' ? [false, false, false] : [true, false, true]);
      const body = await page.locator('body').innerText();
      check(`${name}: nothing prints undefined or NaN`, !/\bundefined\b|\bNaN\b/.test(body), (body.match(/.{0,40}(undefined|NaN).{0,40}/) || [''])[0]);
      eq(`${name}: page errors`, [...errors], []);
    } finally { await context.close(); }
  }

  // ---- every clause of the shape check refuses the block whole, one at a time
  const { page, context, errors } = await open(browser, base, '/tests/fixtures/page/full.json', FRESH, 1280, { reducedMotion: 'reduce', lens: 'all' });
  try {
    const shapes = {
      'policy missing': (b) => { delete b.policy; },
      'policy not an object': (b) => { b.policy = 'nightly'; },
      'primary_et not HH:MM': (b) => { b.policy.primary_et = '6pm'; },
      'retry_et not HH:MM': (b) => { b.policy.retry_et = 2016; },
      'policy timezone not ET': (b) => { b.policy.timezone = 'America/Chicago'; },
      'recovery policy unknown': (b) => { b.policy.recovery_until = 'never'; },
      'completion_at without an offset': (b) => { b.completion_at = '2026-09-10T16:15:00'; },
      'published_at missing': (b) => { delete b.published_at; },
      'primary_slot_at not an instant': (b) => { b.primary_slot_at = 'six'; },
      'retry_slot_at null': (b) => { b.retry_slot_at = null; },
      'next_open_at a date only': (b) => { b.next_open_at = '2026-09-11'; },
      'latency not a number': (b) => { b.latency_minutes = '135'; },
      'before_next_open not a boolean': (b) => { b.before_next_open = 'yes'; },
      'slot outside the three': (b) => { b.slot = 'late'; },
      'sentence empty': (b) => { b.sentence = ''; },
      'block an array': (b, run) => { run.delivery = [b]; },
    };
    for (const [name, mutate] of Object.entries(shapes)) {
      const copy = clone(full); mutate(copy.run.delivery, copy.run);
      const read = await page.evaluate((d) => { const x = window.SCStock.deliveryOf(d); return [x.present, x.known, x.faults.length, x.sentence, x.slot]; }, copy);
      eq(`shape: ${name} -> present, not known, named, nothing read`, [read[0], read[1], read[2] > 0, read[3], read[4]], [true, false, true, null, null]);
      const got = await statusAt(page, copy, CLOCKS.betweenSlots[0]);
      eq(`shape: ${name} -> still pending on the calendar, no slot named`, [got.state, got.slot, got.sentence.includes('6:16')], ['pending', null, false]);
    }
    const whole = await page.evaluate((d) => { const x = window.SCStock.deliveryOf(d); return [x.present, x.known, x.faults, x.slot, x.latency, x.policy]; }, full);
    eq('the generator’s own block is read whole', whole, [true, true, [], 'after_primary', 135, { primaryEt: '18:16', retryEt: '20:16', recoveryUntil: 'next_session_open' }]);
    eq('shape checks: page errors', [...errors], []);
  } finally { await context.close(); }
}
