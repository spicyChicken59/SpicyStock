/* Manual Chicago wall times through the real private-report editor. The cash
   preview and observations are run_evening-produced fixtures; every broker
   fact below is synthetic. Expected UTC instants are fixed examples, not
   answers obtained from the helper or a second copy of its conversion code. */
import { readFile, mkdir } from 'node:fs/promises';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const SOURCE = 'tests/fixtures/cash-preview';
const KEY = 'spicystock:handoff:v1';
const NOW = '2026-09-11T13:35:00.000Z';
const TIMES = [
  ['submitted_at', 'Submission time', '08:31', '2026-09-11T13:31:00.000Z'],
  ['filled_at', 'Latest entry fill time', '08:32:03.123', '2026-09-11T13:32:03.123Z'],
  ['cancelled_at', 'Remainder cancellation time', '08:33', '2026-09-11T13:33:00.000Z'],
  ['exited_at', 'Latest exit time', '08:34', '2026-09-11T13:34:00.000Z'],
  ['protection_confirmed_at', 'Protection checked by you at', '08:34:30', '2026-09-11T13:34:30.000Z']
];
const field = (page, name) => page.locator('[data-handoff-field="' + name + '"]');
const opener = (page, name) => page.locator('[data-handoff-chicago="' + name + '"]');
const helper = page => page.locator('[data-handoff-time-helper]');
const apply = page => page.locator('[data-handoff-time-apply]');
const preview = page => page.locator('[data-handoff-time-preview]');
const raw = page => page.evaluate(key => localStorage.getItem(key), KEY);
const fields = page => page.locator('[data-handoff-field]').evaluateAll(nodes => Object.fromEntries(nodes.map(node => [node.dataset.handoffField, node.value])));
const set = async (page, values) => { for (const [name, value] of Object.entries(values)) await field(page, name).fill(value); };
const fillClock = async (page, date, time) => { await page.locator('#handoff-time-date').fill(date); await page.locator('#handoff-time-clock').fill(time); };
const cancel = async page => page.locator('[data-handoff-time-cancel]').click();
async function save(page) {
  await page.locator('[data-handoff-save]').click();
  await page.waitForFunction(() => !document.querySelector('[data-handoff-save]').disabled || /storage|saving/i.test(document.querySelector('[data-handoff-storage]').textContent));
}

export async function checkBrokerTime({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- Chicago broker times: explicit local conversion, DST choice, unsaved continuity and unchanged report guards');
  const sidecar = await readFile(path.join(ROOT, SOURCE, 'observed.json'), 'utf8');
  for (const [width, theme, browserZone] of [[390, 'light', 'Asia/Tokyo'], [1280, 'dark', 'America/Los_Angeles']]) {
    const requests = [];
    const tab = await open(browser, base, '/' + SOURCE + '/publication.json', null, width, {
      theme, hash: '#/explore/setting-up/COIL', reducedMotion: 'reduce',
      beforeLoad: async (page, context) => {
        // The existing driver has no timezone option. Chromium's public
        // emulation command changes this page before any application script.
        const session = await context.newCDPSession(page);
        await session.send('Emulation.setTimezoneOverride', { timezoneId: browserZone });
        await context.addInitScript(start => {
          const Native = Date; window.__brokerTimeClock = Native.parse(start);
          window.Date = class extends Native {
            constructor(...args) { super(...(args.length ? args : [window.__brokerTimeClock])); }
            static now() { return window.__brokerTimeClock; }
          };
        }, NOW);
        page.on('request', request => requests.push([request.url(), request.method(), request.postData()]));
        await page.route('**/morning.json', route => route.fulfill({ contentType: 'application/json', body: sidecar }));
      }
    });
    const { page, context, errors } = tab;
    const name = width + '/' + theme + '/' + browserZone;
    const isInstant = async (label, key, utc, offset) => {
      const value = await field(page, key).inputValue();
      check(name + ': ' + label + ' carries the explicit Chicago offset', value.endsWith(offset), value);
      eq(name + ': ' + label + ' resolves to its independently fixed instant', Number.isFinite(Date.parse(value)) ? new Date(value).toISOString() : null, utc);
    };
    const screenshot = async suffix => {
      if (!shotsDir) return;
      await mkdir(shotsDir, { recursive: true });
      await helper(page).scrollIntoViewIfNeeded();
      await page.screenshot({ path: path.join(shotsDir, 'broker-time-' + suffix + '-' + width + '-' + theme + '.png') });
    };
    try {
      eq(name + ': the browser actually uses the deliberately different timezone', await page.evaluate(() => Intl.DateTimeFormat().resolvedOptions().timeZone), browserZone);
      await page.waitForFunction(() => SCStock.observations.facts().state === 'loaded');
      await page.locator('#morning-open').click();
      await page.locator('.ss-morning__prep > summary').click();
      await page.locator('#morning-cash').fill('2000');
      await page.locator('#morning-preview-fees').fill('1');
      await page.locator('#morning-preview-quantity').fill('2');
      await page.locator('[data-handoff-prepare]').click();
      await page.waitForFunction(() => SCStock.handoff.list().length === 1);
      await page.locator('[data-handoff-report] > summary').click();
      let initialRaw = await raw(page);
      const requestCount = requests.length;
      const original = await page.evaluate(() => ({ record: JSON.stringify(SCStock.data), following: localStorage.getItem('spicystock:following:v1') }));
      eq(name + ': every broker time remains unknown until entered', await page.evaluate(times => times.map(([key]) => SCStock.handoff.list()[0].report[key]), TIMES), TIMES.map(() => null));
      eq(name + ': there is one reusable helper', await helper(page).count(), 1);
      eq(name + ': the helper is initially closed', await helper(page).isVisible(), false);
      eq(name + ': exactly the five time fields offer Chicago entry', await page.locator('[data-handoff-chicago]').evaluateAll(nodes => nodes.map(node => node.dataset.handoffChicago)), TIMES.map(([key]) => key));

      // Delay an actual replacement behind the same real Web Lock the
      // unchanged model uses. The helper opens after the operation is queued;
      // no raw field is edited, so ordinary dirty-field protection cannot
      // accidentally hide a missing post-await helper guard.
      const beforeReplacementFields = await fields(page);
      const beforeReplacementRevision = await page.evaluate(() => SCStock.handoff.list()[0].revision);
      await page.evaluate(key => {
        window.__brokerTimeReplacementHeld = false;
        navigator.locks.request(key, () => new Promise(resolve => {
          window.__brokerTimeReplacementHeld = true;
          window.__brokerTimeReplacementRelease = resolve;
        }));
      }, KEY);
      try {
        await page.waitForFunction(() => window.__brokerTimeReplacementHeld, null, { timeout: 5000 });
        await page.locator('[data-handoff-prepare]').click();
        await page.waitForFunction(async key => (await navigator.locks.query()).pending.some(lock => lock.name === key), KEY, { timeout: 5000 });
        eq(name + ': pending replacement has not committed while the real lock is held', await raw(page), initialRaw);
        await opener(page, 'submitted_at').click(); await fillClock(page, '2026-01-02', '08:12:00.123');
        await page.locator('#handoff-time-clock').focus();
        await page.evaluate(() => {
          window.__brokerTimeReplacementDate = document.querySelector('#handoff-time-date');
          window.__brokerTimeReplacementClock = document.querySelector('#handoff-time-clock');
          window.__brokerTimeReplacementRelease();
        });
        await page.waitForFunction(() => !document.querySelector('[data-handoff-prepare]')._busy, null, { timeout: 5000 });
        eq(name + ': pending replacement actually commits its next revision', await page.evaluate(() => SCStock.handoff.list()[0].revision), beforeReplacementRevision + 1);
        eq(name + ': pending replacement keeps the helper visible', await helper(page).isVisible(), true);
        eq(name + ': pending replacement keeps exact helper nodes, values and focus', await page.evaluate(() => {
          const date = document.querySelector('#handoff-time-date'), clock = document.querySelector('#handoff-time-clock');
          return [date === window.__brokerTimeReplacementDate, date.value, clock === window.__brokerTimeReplacementClock, clock.value, document.activeElement === clock];
        }), [true, '2026-01-02', true, '08:12:00.123', true]);
        eq(name + ': pending replacement keeps every raw report field', await fields(page), beforeReplacementFields);
        check(name + ': pending replacement announces the stale editor revision', /another view/.test(await page.locator('[data-handoff-editor-status]').textContent()));
        eq(name + ': pending replacement leaves report saving disabled until the helper is resolved', await page.locator('[data-handoff-save]').isDisabled(), true);
        await screenshot('pending-replacement');
        const replacedRaw = await raw(page);
        await page.locator('[data-handoff-reload]').click();
        eq(name + ': pending replacement resolves through explicit saved reload', await helper(page).isVisible(), false);
        eq(name + ': pending replacement explicit reload restores known saved fields', await fields(page), beforeReplacementFields);
        check(name + ': pending replacement explicit reload clears the revision warning', !/another view/.test(await page.locator('[data-handoff-editor-status]').textContent()));
        eq(name + ': pending replacement explicit reload preserves the new private bytes', await raw(page), replacedRaw);
        initialRaw = replacedRaw;
      } finally {
        await page.evaluate(() => { if (window.__brokerTimeReplacementRelease) window.__brokerTimeReplacementRelease(); });
      }

      for (const [key, label, wall, utc] of TIMES) {
        const before = await fields(page);
        await opener(page, key).focus(); await page.keyboard.press('Enter');
        check(name + ': ' + label + ' opens a labelled Chicago helper', await helper(page).isVisible() && (await helper(page).textContent()).includes(label) && /America\/Chicago/.test(await helper(page).textContent()));
        eq(name + ': ' + label + ' starts with no guessed date or time', [await page.locator('#handoff-time-date').inputValue(), await page.locator('#handoff-time-clock').inputValue()], ['', '']);
        eq(name + ': ' + label + ' opening preserves all raw report inputs', await fields(page), before);
        eq(name + ': opening focuses the date input', await page.evaluate(() => document.activeElement.id), 'handoff-time-date');
        eq(name + ': an unfinished helper cannot apply', await apply(page).isDisabled(), true);
        eq(name + ': an unfinished helper prevents accidental report saving', await page.locator('[data-handoff-save]').isDisabled(), true);
        check(name + ': the disabled save has an apply/cancel explanation', /apply|cancel/i.test(await page.locator('[data-handoff-editor-status]').textContent()));
        await fillClock(page, '2026-09-11', wall);
        eq(name + ': ' + label + ' valid wall time can be applied', await apply(page).isDisabled(), false);
        check(name + ': ' + label + ' preview exposes both offset and UTC', /-05:00/.test(await preview(page).textContent()) && /UTC|Z/.test(await preview(page).textContent()));
        if (key === 'submitted_at') {
          const draft = [await page.locator('#handoff-time-date').inputValue(), await page.locator('#handoff-time-clock').inputValue()];
          await opener(page, key).click();
          eq(name + ': reopening the active helper preserves its draft', [await page.locator('#handoff-time-date').inputValue(), await page.locator('#handoff-time-clock').inputValue()], draft);
          await opener(page, 'filled_at').click();
          eq(name + ': another target cannot silently discard the active helper draft', [await page.locator('#handoff-time-date').inputValue(), await page.locator('#handoff-time-clock').inputValue()], draft);
          check(name + ': refused target switch still names submission', (await helper(page).textContent()).includes(label));
          eq(name + ': target switch keeps all raw inputs', await fields(page), before);
          await screenshot('preview');
        }
        await apply(page).focus(); await page.keyboard.press('Enter');
        await isInstant(label, key, utc, '-05:00');
        const after = await fields(page), applied = after[key];
        eq(name + ': ' + label + ' application changes only its selected raw field', after, { ...before, [key]: applied });
        eq(name + ': ' + label + ' application closes the helper', await helper(page).isVisible(), false);
        eq(name + ': ' + label + ' application returns keyboard focus to raw input', await field(page, key).evaluate(node => document.activeElement === node), true);
        eq(name + ': ' + label + ' application does not save private bytes', await raw(page), initialRaw);
      }
      check(name + ': entry milliseconds survive conversion', /\.123-05:00$/.test(await field(page, 'filled_at').inputValue()));
      await save(page);
      eq(name + ': time conversion cannot bypass missing corresponding quantities', await raw(page), initialRaw);
      check(name + ': the existing quantity guard explains its refusal', /corresponding reported quantity/.test(await page.locator('[data-handoff-message]').textContent()));
      await set(page, { submitted_quantity: '2', filled_quantity: '1', average_price: '111.23', cancelled_quantity: '1', exited_quantity: '1', average_exit_price: '115', entry_fees: '0.05', exit_fees: '0.07', protected_quantity: '0' });
      await save(page);
      eq(name + ': explicit save uses the unchanged UTC storage format', await page.evaluate(times => times.map(([key]) => SCStock.handoff.list()[0].report[key]), TIMES), TIMES.map(([, , , utc]) => utc));
      const savedRaw = await raw(page);
      check(name + ': the report changes only after explicit save', savedRaw !== initialRaw);
      const knownFields = await fields(page);

      // Cancellation and invalid inputs never manufacture a value or erase a
      // pre-existing raw timestamp, including an unsaved manual correction.
      await field(page, 'average_price').fill('111.2345');
      const unsaved = await fields(page);
      await opener(page, 'submitted_at').click();
      await page.locator('#handoff-time-date').fill('2026-01-15');
      eq(name + ': a date without a clock remains incomplete', await apply(page).isDisabled(), true);
      await page.locator('#handoff-time-clock').fill('08:31');
      const clockDraft = [await page.locator('#handoff-time-date').inputValue(), await page.locator('#handoff-time-clock').inputValue()];
      await page.locator('#handoff-time-clock').focus();
      await page.evaluate(() => { window.__brokerTimeInput = document.querySelector('#handoff-time-clock'); SCStock.reclock(); });
      eq(name + ': clock refresh preserves the helper node, value and focus', await page.locator('#handoff-time-clock').evaluate(node => [node === window.__brokerTimeInput, node.value, document.activeElement === node]), [true, clockDraft[1], true]);
      eq(name + ': clock refresh keeps unrelated unsaved report inputs', await fields(page), unsaved);
      await cancel(page);
      eq(name + ': cancelling restores opener focus', await opener(page, 'submitted_at').evaluate(node => document.activeElement === node), true);
      eq(name + ': cancelling preserves raw and unrelated unsaved fields', await fields(page), unsaved);
      eq(name + ': cancelling preserves saved bytes', await raw(page), savedRaw);

      await opener(page, 'submitted_at').click();
      await fillClock(page, '2026-03-08', '02:30');
      eq(name + ': nonexistent spring-forward Chicago time is refused', await apply(page).isDisabled(), true);
      eq(name + ': nonexistent Chicago time offers no selectable instant', await page.locator('#handoff-time-occurrence option').evaluateAll(nodes => nodes.filter(node => node.value).map(node => node.value)), []);
      eq(name + ': nonexistent Chicago time cannot masquerade as a repeated hour', await page.locator('[data-handoff-time-fold]').isVisible(), false);
      check(name + ': spring-forward refusal explains the missing local time', /does not exist|does not occur|nonexistent|skipped/i.test(await preview(page).textContent()));
      eq(name + ': spring gap leaves the original timestamp untouched', await field(page, 'submitted_at').inputValue(), unsaved.submitted_at);
      await fillClock(page, '2026-03-08', '01:59:59.999');
      await apply(page).click();
      await isInstant('last millisecond before spring jump', 'submitted_at', '2026-03-08T07:59:59.999Z', '-06:00');
      await opener(page, 'submitted_at').click(); await fillClock(page, '2026-03-08', '03:00'); await apply(page).click();
      await isInstant('first time after spring jump', 'submitted_at', '2026-03-08T08:00:00.000Z', '-05:00');
      await opener(page, 'submitted_at').click(); await fillClock(page, '2026-01-15', '08:31'); await apply(page).click();
      await isInstant('winter Chicago time', 'submitted_at', '2026-01-15T14:31:00.000Z', '-06:00');

      for (const [offset, utc] of [['-05:00', '2026-11-01T06:30:00.000Z'], ['-06:00', '2026-11-01T07:30:00.000Z']]) {
        await opener(page, 'submitted_at').click(); await fillClock(page, '2026-11-01', '01:30');
        const occurrence = page.locator('#handoff-time-occurrence');
        check(name + ': fall-back time offers an explicit occurrence choice', await occurrence.isVisible());
        eq(name + ': no ambiguous occurrence is guessed', await occurrence.inputValue(), '');
        eq(name + ': ambiguous time cannot apply until the owner chooses', await apply(page).isDisabled(), true);
        const options = await occurrence.locator('option').evaluateAll(nodes => nodes.filter(node => node.value).map(node => node.value));
        eq(name + ': fall-back choices represent the two distinct known instants', options.map(value => new Date(value).toISOString()), ['2026-11-01T06:30:00.000Z', '2026-11-01T07:30:00.000Z']);
        check(name + ': both fall-back offsets are visible to the owner', /-05:00/.test(await occurrence.textContent()) && /-06:00/.test(await occurrence.textContent()));
        const choice = options.find(value => value.endsWith(offset));
        check(name + ': expected occurrence ' + offset + ' exists', !!choice);
        if (choice) await occurrence.selectOption(choice);
        eq(name + ': an explicit fold choice allows applying', await apply(page).isDisabled(), false);
        if (offset === '-06:00') await screenshot('fall-choice');
        await apply(page).click(); await isInstant('selected fall-back occurrence ' + offset, 'submitted_at', utc, offset);
      }
      await opener(page, 'submitted_at').click(); await fillClock(page, '2026-11-01', '01:30');
      const occurrence = page.locator('#handoff-time-occurrence');
      const first = await occurrence.locator('option').evaluateAll(nodes => nodes.find(node => node.value)?.value || '');
      if (first) await occurrence.selectOption(first);
      await page.locator('#handoff-time-clock').fill('01:31');
      eq(name + ': editing an ambiguous wall time requires a fresh occurrence choice', await occurrence.inputValue(), '');
      eq(name + ': stale occurrence cannot apply after a clock edit', await apply(page).isDisabled(), true);
      // Native date inputs sanitize impossible calendar dates to an empty
      // value. Send their ordinary input event after that native sanitation.
      await page.locator('#handoff-time-date').evaluate(node => { node.value = '2026-02-30'; node.dispatchEvent(new Event('input', { bubbles: true })); });
      eq(name + ': impossible native calendar input is empty', await page.locator('#handoff-time-date').inputValue(), '');
      eq(name + ': an invalid calendar input cannot use a previous resolved choice', await apply(page).isDisabled(), true);
      await cancel(page);
      eq(name + ': all DST and invalid-input exercises remain unsaved', await raw(page), savedRaw);

      // The helper only edits a timestamp. The model still rejects event
      // facts whose actual report violates time and quantity relationships.
      await page.locator('[data-handoff-reload]').click();
      eq(name + ': explicit saved reload restores all known fields', await fields(page), knownFields);
      await opener(page, 'filled_at').click(); await fillClock(page, '2026-09-12', '08:32'); await apply(page).click();
      await save(page);
      eq(name + ': converted future event cannot overwrite saved facts', await raw(page), savedRaw);
      check(name + ': future event keeps the existing model refusal', /cannot be in the future/.test(await page.locator('[data-handoff-message]').textContent()));
      await page.locator('[data-handoff-reload]').click();
      await opener(page, 'filled_at').click(); await fillClock(page, '2026-09-11', '08:30'); await apply(page).click();
      await save(page);
      eq(name + ': converted fill before submission cannot overwrite saved facts', await raw(page), savedRaw);
      check(name + ': chronology keeps the existing model refusal', /cannot precede the reported submission/.test(await page.locator('[data-handoff-message]').textContent()));
      await page.locator('[data-handoff-reload]').click();
      await opener(page, 'cancelled_at').click(); await fillClock(page, '2026-09-11', '08:32'); await apply(page).click();
      await save(page);
      eq(name + ': converted cancellation before the latest fill cannot overwrite', await raw(page), savedRaw);
      check(name + ': cancellation chronology remains enforced', /cancellation cannot precede/.test(await page.locator('[data-handoff-message]').textContent()));
      await page.locator('[data-handoff-reload]').click();
      await opener(page, 'exited_at').click(); await fillClock(page, '2026-09-11', '08:32'); await apply(page).click();
      await save(page);
      eq(name + ': converted complete exit before the latest fill cannot overwrite', await raw(page), savedRaw);
      check(name + ': complete-exit chronology remains enforced', /complete exit cannot precede/.test(await page.locator('[data-handoff-message]').textContent()));
      await page.locator('[data-handoff-reload]').click();
      await opener(page, 'submitted_at').click(); await fillClock(page, '2026-01-15', '08:31');
      await page.locator('[data-handoff-reload]').click();
      eq(name + ': explicit saved reload may discard an open helper', await helper(page).isVisible(), false);
      eq(name + ': saved reload with a helper restores all raw fields', await fields(page), knownFields);

      // The old exact-offset path stays available, and "current time" still
      // means the device clock, not a Chicago broker-event inference.
      await field(page, 'submitted_at').fill('2026-09-11T22:31:00+09:00');
      await save(page);
      eq(name + ': manually supplied non-Chicago offset keeps the same instant', await page.evaluate(() => SCStock.handoff.list()[0].report.submitted_at), '2026-09-11T13:31:00.000Z');
      const fallbackRaw = await raw(page);
      await page.locator('[data-handoff-now="protection_confirmed_at"]').click();
      eq(name + ': current time still enters the actual fixed device instant', await field(page, 'protection_confirmed_at').inputValue(), NOW);
      eq(name + ': current time remains unsaved', await raw(page), fallbackRaw);
      await field(page, 'protection_confirmed_at').fill(''); await save(page);
      eq(name + ': explicit blank still saves unknown rather than invented time', await page.evaluate(() => SCStock.handoff.list()[0].report.protection_confirmed_at), null);

      // A genuine same-origin second tab changes the saved revision while
      // this tab is composing a time. Its public startup requests are tracked
      // separately; the original page must make none for private editing.
      const beforeConflict = await raw(page), beforeConflictFields = await fields(page);
      await opener(page, 'submitted_at').click(); await fillClock(page, '2026-09-11', '08:30:30.456');
      await page.locator('#handoff-time-clock').focus();
      await page.evaluate(key => {
        window.__brokerTimeConflictInput = document.querySelector('#handoff-time-clock');
        window.__brokerTimeConflictDate = document.querySelector('#handoff-time-date');
        window.__brokerTimeStorageEvents = [];
        addEventListener('storage', event => {
          if (event.key === key) window.__brokerTimeStorageEvents.push({ key: event.key, oldValue: event.oldValue, newValue: event.newValue, trusted: event.isTrusted, local: event.storageArea === localStorage });
        });
      }, KEY);
      const other = await context.newPage(), otherRequests = [];
      try {
        other.on('request', request => otherRequests.push([request.url(), request.method(), request.postData()]));
        await other.addInitScript(dataUrl => { window.SCStock = { dataUrl }; }, '/' + SOURCE + '/publication.json');
        await other.route('**/morning.json', route => route.fulfill({ contentType: 'application/json', body: sidecar }));
        await other.goto(base + '/docs/index.html', { waitUntil: 'load' });
        await other.waitForFunction(() => document.documentElement.getAttribute('data-ss-rendered'));
        const changed = await other.evaluate(async key => {
          const item = SCStock.handoff.list()[0];
          const result = await SCStock.handoff.report(item.id, { ...item.report, average_price: '111.24' }, item.revision);
          return { ok: result.ok, error: result.error || null, previousRevision: item.revision, item: result.item || null, raw: localStorage.getItem(key) };
        }, KEY);
        eq(name + ': second tab explicitly saves a different valid report', [changed.ok, changed.error, changed.item?.report.average_price, changed.item?.revision], [true, null, '111.24', changed.previousRevision + 1]);
        check(name + ': second-tab write changes actual saved bytes', changed.raw !== beforeConflict);
        await page.waitForFunction(() => window.__brokerTimeStorageEvents.length > 0 && /another view/.test(document.querySelector('[data-handoff-editor-status]').textContent), null, { timeout: 5000 });
        eq(name + ': the original receives a real trusted local-storage event', await page.evaluate(() => window.__brokerTimeStorageEvents), [{ key: KEY, oldValue: beforeConflict, newValue: changed.raw, trusted: true, local: true }]);
        eq(name + ': second-tab conflict retains exact helper nodes, values and focus', await page.evaluate(() => {
          const date = document.querySelector('#handoff-time-date'), clock = document.querySelector('#handoff-time-clock');
          return [date === window.__brokerTimeConflictDate, date.value, clock === window.__brokerTimeConflictInput, clock.value, document.activeElement === clock];
        }), [true, '2026-09-11', true, '08:30:30.456', true]);
        eq(name + ': second-tab conflict retains every original raw report input', await fields(page), beforeConflictFields);
        check(name + ': the conflict is announced while the helper remains open', /another view/.test(await page.locator('[data-handoff-editor-status]').textContent()) && await helper(page).isVisible());
        eq(name + ': open conflicted helper still blocks report save', await page.locator('[data-handoff-save]').isDisabled(), true);
        await apply(page).click();
        await isInstant('applied time on the stale editor', 'submitted_at', '2026-09-11T13:30:30.456Z', '-05:00');
        eq(name + ': applying during a conflict keeps all other stale inputs', await fields(page), { ...beforeConflictFields, submitted_at: await field(page, 'submitted_at').inputValue() });
        eq(name + ': applying does not overwrite the other tab', await raw(page), changed.raw);
        await save(page);
        eq(name + ': stale explicit save cannot overwrite the second tab', await raw(page), changed.raw);
        check(name + ': stale save names the revision conflict', /changed in another view|Reopen its current report/.test(await page.locator('[data-handoff-message]').textContent()));
        await page.locator('[data-handoff-reload]').click();
        eq(name + ': explicit reload adopts all facts from the newer revision', await fields(page), Object.fromEntries(Object.keys(beforeConflictFields).map(key => [key, changed.item.report[key] === null ? '' : String(changed.item.report[key])])));
        eq(name + ': explicit reload leaves the helper closed', await helper(page).isVisible(), false);
        eq(name + ': explicit reload preserves the newer saved bytes', await raw(page), changed.raw);
        check(name + ': explicit reload resolves the editor conflict', !/another view/.test(await page.locator('[data-handoff-editor-status]').textContent()));
        check(name + ': second tab made its separate public startup reads', otherRequests.length > 0 && otherRequests.every(([, method, body]) => method === 'GET' && body === null));
      } finally { await other.close(); }
      eq(name + ': original-page private editing sends no additional request', requests.slice(requestCount), []);
      eq(name + ': published record and Following remain unchanged', await page.evaluate(() => ({ record: JSON.stringify(SCStock.data), following: localStorage.getItem('spicystock:following:v1') })), original);
      check(name + ': all report controls fit the viewport', await page.locator('#morning-desk').evaluate(node => node.scrollWidth <= node.clientWidth + 1 && document.documentElement.scrollWidth <= innerWidth));
      eq(name + ': no browser errors', [...errors], []);
    } catch (error) {
      check(name + ': broker-time journey completes', false, error.stack);
    } finally { await context.close(); }
  }
}
