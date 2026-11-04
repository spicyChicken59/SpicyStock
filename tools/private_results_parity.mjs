/* The page's own verdicts on a corpus of private backups, for
   tools/private_results.py to be held to (tests/test_private_results.py).

   Each case is the first-trade rehearsal's backup (or an independent research
   report built from the stop-research fixture) with one change, written as the
   bytes a file would hold. The page's real app-cash-preview.js and
   app-handoff.js run in a vm over each: whether the page's parseStore()
   accepts the bytes, and for an accepted store every record's completed result
   and beyond-stop figures from summary(). No page, network, clock or storage
   beyond a stub localStorage is involved; summary() and the store parser read
   no clock.

   node tools/private_results_parity.mjs           writes tests/fixtures/first-trade/parity.json.gz
   node tools/private_results_parity.mjs --check   fails when the file is not what the page says now

   Every broker fact here is synthetic. */
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import { gzipSync, gunzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';

const ROOT = path.resolve(import.meta.dirname, '..');
// Gzipped: the cases share most of their bytes. --check compares the text, so
// a platform's gzip header cannot fail it.
const OUT = path.join(ROOT, 'tests/fixtures/first-trade/parity.json.gz');
const KEY = 'spicystock:handoff:v1';
const scripts = await Promise.all(['docs/app-cash-preview.js', process.env.SCSTOCK_HANDOFF || 'docs/app-handoff.js'].map(file => readFile(path.resolve(ROOT, file), 'utf8')));
const base = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/first-trade/backup.json'), 'utf8'));
const receipt = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/stop-research/current-receipt.json'), 'utf8'));
const bundle = JSON.parse(await readFile(path.join(ROOT, 'tests/fixtures/stop-research/current-bundle.json'), 'utf8'));
const publicationBytes = await readFile(path.join(ROOT, 'tests/fixtures/cash-preview/publication-multiple.json'));
const publication = JSON.parse(publicationBytes.toString('utf8'));
const publicationSha = createHash('sha256').update(publicationBytes).digest('hex');

function page(raw) {
  const store = new Map([[KEY, raw]]);
  const window = { SCStock: {}, TextEncoder, navigator: { locks: { request: async (key, fn) => fn() } },
    localStorage: { getItem: key => store.get(key) ?? null, setItem: (key, value) => store.set(key, value), removeItem: key => store.delete(key) },
    addEventListener: () => {} };
  const context = vm.createContext({ window });
  scripts.forEach(script => vm.runInContext(script, context));
  const handoff = window.SCStock.handoff;
  const status = handoff.status();
  if (status.error) return { accepted: false, records: [] };
  return { accepted: true, records: handoff.list().map(item => {
    const summary = handoff.summary(item), result = summary.completed_result, beyond = summary.beyond_stop, reference = summary.reference_exits;
    return { id: item.id, kind: item.kind, state: result.state, missing: [...result.missing].sort(),
      gross_microusd: result.gross_microusd, fees_microusd: result.fees_microusd, net_microusd: result.net_microusd,
      gross_display: result.gross_display, fees_display: result.fees_display, net_display: result.net_display, outcome: result.outcome,
      beyond_stop: beyond && { per_share_microusd: beyond.per_share_microusd, total_microusd: beyond.total_microusd, quantity: beyond.quantity,
        per_share_display: beyond.per_share_display, total_display: beyond.total_display },
      // An owner trade's reference arithmetic (the sell-half level, the record's
      // placed sessions, the fill's New York date); never a decision.
      reference_exits: reference && { sell_half_pct: reference.sell_half_pct, sell_half_day: reference.sell_half_day, final_exit_day: reference.final_exit_day, entry_day: reference.entry_day,
        level: reference.level, fill_session: reference.fill_session, fill_on_entry_session: reference.fill_on_entry_session, entry_session: reference.entry_session,
        sell_half_session: reference.sell_half_session, final_session: reference.final_session, stop_price: reference.stop_price } };
  }) };
}

const copy = value => JSON.parse(JSON.stringify(value));
const coil = store => store.items.find(item => item.plan && item.plan.ticker === 'COIL');
const aapl = store => store.items.find(item => item.plan && item.plan.ticker === 'AAPL');
// A literal the page never writes itself (2.0, NaN, a long integer) is spelled
// in place of a marker string after JSON.stringify.
const literal = (store, spelled) => JSON.stringify(store).replace(/"__LITERAL__"/, spelled);
const report = patch => store => { Object.assign(coil(store).report, patch); };
function independent() {
  const row = bundle.rows.find(row => row.ticker === 'KE');
  const source = { ticker: 'KE', stage: 'setting-up', publication: copy(receipt.publication),
    cohort: { sha256: receipt.bundle.sha256, bytes: receipt.bundle.bytes, generated_at: receipt.timing.generated_at, policy_id: receipt.policy.id },
    evidence: copy(row.evidence), baseline_admitted: row.baseline.admitted };
  const empty = Object.fromEntries(Object.keys(base.items[0].report).map(key => [key, null]));
  return { version: 3, items: [{ version: 3, kind: 'independent_research', id: source.publication.data_sha256 + ':' + source.evidence.id, revision: 1,
    created_at: '2026-10-12T15:00:00.000Z', updated_at: '2026-10-12T15:00:00.000Z', source,
    report: { ...empty, submitted_quantity: 3, filled_quantity: 3, cancelled_quantity: 0, exited_quantity: 3, average_price: '29.4', average_exit_price: '31.05',
      filled_at: '2026-10-12T13:35:00.000Z', exited_at: '2026-10-12T14:55:00.000Z', entry_fees: '0.00', exit_fees: '0.02' },
    report_updated_at: '2026-10-12T15:00:00.000Z' }] };
}
const indep = mutate => () => { const store = independent(); mutate(store); return JSON.stringify(store); };
// An owner's own trade on a listed name without a ticket (NVDA: an A+ burst the
// fixture's allocation left without an order), as the page's reportOwner()
// freezes it: the publication, the row as read, the archived exit rules and the
// day-3 / day-5 sessions the record's calendar places after its applicable one.
function ownerTrade() {
  const row = publication.bursts.find(row => row.ticker === 'NVDA'), rules = publication.rules.plan, timing = publication.run.timing;
  const sessions = publication.run.calendar.schedule.sessions.map(s => s.session), at = sessions.indexOf(timing.applicable_session);
  const source = { ticker: 'NVDA', stage: 'bursts', publication: { sha256: publicationSha, session: publication.run.session, published_at: publication.run.published_at, rules_version: publication.app.rules_version },
    row: { rank: publication.bursts.indexOf(row) + 1, grade: row.grade, score: row.score, scan: typeof row.scan === 'string' ? row.scan : null, admitted: null, status: 'no_order', reason: '' },
    evidence_id: row.evidence && row.evidence.id ? row.evidence.id : null,
    rules: { sell_half_pct: rules.sell_half_pct, sell_half_day: rules.sell_half_day, final_exit_day: rules.final_exit_day, entry_day: rules.entry_day },
    schedule: { entry_session: sessions[at], sell_half_session: sessions[at + rules.sell_half_day - rules.entry_day], final_session: sessions[at + rules.final_exit_day - rules.entry_day] } };
  const empty = Object.fromEntries(Object.keys(base.items[0].report).map(key => [key, null]));
  return { version: 4, items: [{ version: 4, kind: 'owner_trade', id: source.publication.sha256 + ':owner:' + source.stage + ':' + source.ticker, revision: 1,
    created_at: '2026-09-11T14:05:00.000Z', updated_at: '2026-09-11T14:05:00.000Z', source,
    report: { ...empty, submitted_quantity: 102, filled_quantity: 102, cancelled_quantity: 0, average_price: '70.345', filled_at: '2026-09-11T13:41:00.000Z',
      protected_quantity: 102, protection_confirmed_at: '2026-09-11T13:42:00.000Z', account_label: 'Rollover IRA', stop_price: '67.85' },
    report_updated_at: '2026-09-11T14:05:00.000Z' }] };
}
const own = mutate => () => { const store = ownerTrade(); mutate(store); return JSON.stringify(store); };
const ownRaw = build => () => build(ownerTrade());
const ownerRow = store => store.items[0];
const on = mutate => () => { const store = copy(base); mutate(store); return JSON.stringify(store); };
const raw = build => () => build(copy(base));

// name -> the bytes. Accept and refuse are whatever the page says; the names say why each is here.
const CASES = [
  ['the rehearsal backup', () => JSON.stringify(base)],
  ['an empty store', () => JSON.stringify({ version: 4, items: [] })],
  ['a version 3 empty store', () => JSON.stringify({ version: 3, items: [] })],
  ['a version 3 store', on(store => { store.version = 3; for (const item of store.items) { item.version = 3; for (const key of ['account_label', 'stop_price']) delete item.report[key]; } })],
  ['a draft with no report', on(store => { const item = coil(store); for (const key of Object.keys(item.report)) item.report[key] = null; item.report_updated_at = null; })],
  ['version 2', on(store => { store.version = 2; for (const item of store.items) { item.version = 2; delete item.kind; } })],
  ['version 1', on(store => { store.version = 1; for (const item of store.items) { item.version = 1; delete item.kind; for (const key of ['average_exit_price', 'entry_fees', 'exit_fees']) delete item.report[key]; } })],
  // figures
  ['break-even', on(report({ average_exit_price: '111.06', exit_fees: '0.02' }))],
  ['a sub-cent gain', on(report({ average_exit_price: '111.050006', exit_fees: '0.00' }))],
  ['a sub-cent loss', on(report({ average_exit_price: '111.049994', exit_fees: '0.00' }))],
  ['an exit exactly at the stop', on(report({ average_exit_price: '109.5' }))],
  ['a gap on both shares', on(report({ average_exit_price: '108.75' }))],
  ['an average under the stop from one high and one low exit', on(report({ average_exit_price: '107.5' }))],
  ['one micro-dollar under the stop', on(report({ average_exit_price: '109.499999' }))],
  ['the largest quantities and prices', on(store => Object.assign(coil(store).report, { submitted_quantity: 1000000, filled_quantity: 1000000, cancelled_quantity: 0, cancelled_at: null, exited_quantity: 1000000, average_price: '0.000001', average_exit_price: '9999999999.999999', entry_fees: '90071992547409.91', exit_fees: '0.02' }))],
  ['a partial exit', on(report({ exited_quantity: 1, average_exit_price: '113.2' }))],
  ['unknown fees', on(report({ exit_fees: null }))],
  // spellings the page reads but never writes
  ['an integral float quantity', raw(store => { coil(store).report.filled_quantity = '__LITERAL__'; return literal(store, '2.0'); })],
  ['an integral float revision', raw(store => { coil(store).revision = '__LITERAL__'; return literal(store, '5.0'); })],
  ['an exponent for cash cents', raw(store => { coil(store).draft.cash_cents = '__LITERAL__'; return literal(store, '2.0e5'); })],
  ['an integral float published quantity', raw(store => { coil(store).plan.order.quantity = '__LITERAL__'; return literal(store, '4.0'); })],
  ['an integral float schedule day', raw(store => { coil(store).plan.exit_schedule[0].day = '__LITERAL__'; return literal(store, '1.0'); })],
  ['a record clock without milliseconds', on(store => { coil(store).created_at = '2026-09-11T13:35:00Z'; })],
  ['a record clock with an offset', on(store => { coil(store).created_at = '2026-09-11T08:35:00-05:00'; })],
  ['a report clock with an offset', on(store => { coil(store).report_updated_at = '2026-09-15T15:10:00-05:00'; })],
  ['a record clock without seconds', on(store => { coil(store).created_at = '2026-09-11T13:35Z'; })],
  ['a publication session in year 0000', on(store => { coil(store).publication.session = '0000-01-01'; })],
  ['an entry window clock with milliseconds', on(store => { coil(store).plan.timing.opens_at = '2026-09-11T09:30:00.000-04:00'; })],
  ['a schedule instruction of 2000 UTF-16 units', on(store => { coil(store).plan.exit_schedule[0].instruction = 'x'.repeat(2000); })],
  ['an escaped lone surrogate in an instruction', raw(store => { coil(store).plan.exit_schedule[0].instruction = '__LITERAL__'; return literal(store, '"\\ud800 then buy"'); })],
  // the envelope
  ['a byte-order mark', () => '﻿' + JSON.stringify(base)],
  ['a NaN literal', raw(store => { coil(store).revision = '__LITERAL__'; return literal(store, 'NaN'); })],
  ['store version 5', on(store => { store.version = 5; for (const item of store.items) item.version = 5; })],
  ['version 3 records under a version 4 envelope', on(store => { store.version = 4; for (const item of store.items) { item.version = 3; for (const key of ['account_label', 'stop_price']) delete item.report[key]; } })],
  ['a version 3 store whose records carry version 4 fields', on(store => { store.version = 3; for (const item of store.items) item.version = 3; })],
  ['store version true', on(store => { store.version = true; for (const item of store.items) { item.version = true; delete item.kind; for (const key of ['average_exit_price', 'entry_fees', 'exit_fees']) delete item.report[key]; } })],
  ['items not a list', () => JSON.stringify({ version: 4, items: {} })],
  ['an extra envelope field', on(store => { store.note = 'x'; })],
  ['two records with one identity', on(store => { store.items.push(copy(store.items[0])); })],
  ['101 records', on(store => { const first = store.items[0]; store.items = Array.from({ length: 101 }, (_, i) => ({ ...copy(first), id: first.id.slice(0, 65) + i.toString(16).padStart(64, '0') })); })],
  // the record
  ['an unknown kind', on(store => { coil(store).kind = 'broker_import'; })],
  ['an extra record field', on(store => { coil(store).note = 'x'; })],
  ['item version true', on(store => { coil(store).version = true; })],
  ['revision zero', on(store => { coil(store).revision = 0; })],
  ['revision past a safe integer', raw(store => { coil(store).revision = '__LITERAL__'; return literal(store, '1152921504606846976'); })],
  ['a planned identity that is not its publication and reference', on(store => { coil(store).id = '0'.repeat(64) + ':' + '1'.repeat(64); })],
  ['created after it was updated', on(store => { coil(store).created_at = '2026-09-16T00:00:00.000Z'; })],
  ['a report saved after the record was updated', on(store => { coil(store).report_updated_at = '2026-09-16T00:00:00.000Z'; })],
  ['reported facts without a report clock', on(store => { coil(store).report_updated_at = null; })],
  ['a record clock that is not a date', on(store => { coil(store).created_at = '2026-02-30T00:00:00.000Z'; })],
  // the report
  ['filled plus cancelled over submitted', on(report({ cancelled_quantity: 2 }))],
  ['filled over submitted', on(report({ filled_quantity: 4 }))],
  ['exited over filled', on(report({ exited_quantity: 3 }))],
  ['fills without a submitted quantity', on(report({ submitted_quantity: null, submitted_at: null }))],
  ['an exit price without an exit', on(report({ exited_quantity: 0, exited_at: null }))],
  ['a cancellation time without a cancellation', on(report({ cancelled_quantity: 0 }))],
  ['a fill price without a fill', on(store => Object.assign(coil(store).report, { filled_quantity: 0, exited_quantity: 0, average_exit_price: null, exited_at: null, protected_quantity: null, protection_confirmed_at: null, cancelled_quantity: 3 }))],
  ['a protection time without a protected quantity', on(report({ protected_quantity: null }))],
  ['a fill before the submission', on(report({ filled_at: '2026-09-11T13:30:00.000Z' }))],
  ['a cancellation before the latest fill', on(report({ cancelled_at: '2026-09-11T13:33:00.000Z' }))],
  ['a complete exit before the latest fill', on(report({ exited_at: '2026-09-11T13:33:00.000Z' }))],
  ['a quantity over the share bound', on(report({ protected_quantity: 1000001 }))],
  ['a quantity true', on(report({ protected_quantity: true }))],
  ['a non-canonical price', on(report({ average_price: '111.050' }))],
  ['a price with seven places', on(report({ average_price: '111.0500001' }))],
  ['a zero price', on(report({ average_price: '0' }))],
  ['a fee with one place', on(report({ entry_fees: '0.1' }))],
  ['a fee as a number', on(report({ entry_fees: 0 }))],
  ['a report time that is not the stored spelling', on(report({ filled_at: '2026-09-11T13:33:40Z' }))],
  ['a missing report field', on(store => { delete coil(store).report.exit_fees; })],
  // the plan, the order, the timing, the schedule, the draft
  ['reference version true', on(store => { coil(store).plan.reference.version = true; })],
  ['an unknown stage', on(store => { coil(store).plan.stage = 'watchlist'; })],
  ['a ticker that is not the order symbol', on(store => { coil(store).plan.ticker = 'COIN'; })],
  ['a then-quantity true on a one-share order', on(store => { aapl(store).plan.order.then.quantity = true; })],
  ['a then-quantity not the order quantity', on(store => { coil(store).plan.order.then.quantity = 3; })],
  ['a day protective stop', on(store => { coil(store).plan.order.then.time_in_force = 'day'; })],
  ['a stop at the trigger', on(store => { coil(store).plan.order.then.stop_price = 110.61; })],
  ['a limit under the trigger', on(store => { coil(store).plan.order.limit_price = 110.6; })],
  ['an order price with three places', on(store => { coil(store).plan.order.limit_price = 111.725; })],
  ['an entry window clock with microseconds', on(store => { coil(store).plan.timing.opens_at = '2026-09-11T09:30:00.000000-04:00'; })],
  ['an entry window that cuts off before it opens', on(store => { coil(store).plan.timing.cutoff_at = '2026-09-11T09:00:00-04:00'; })],
  ['a schedule row dated before the session', on(store => { coil(store).plan.exit_schedule[0].date = '2026-09-10'; })],
  ['a schedule day 31', on(store => { coil(store).plan.exit_schedule[0].day = 31; })],
  ['a schedule key with capitals', on(store => { coil(store).plan.exit_schedule[0].key = 'Entry'; })],
  ['21 schedule rows', on(store => { const rows = coil(store).plan.exit_schedule; while (rows.length < 21) rows.push(copy(rows[0])); })],
  ['no schedule rows', on(store => { coil(store).plan.exit_schedule = []; })],
  ['a schedule instruction of 2001 UTF-16 units', on(store => { coil(store).plan.exit_schedule[0].instruction = 'x'.repeat(2001); })],
  ['a schedule instruction of 1500 astral characters', on(store => { coil(store).plan.exit_schedule[0].instruction = '\u{1F4C8}'.repeat(1500); })],
  ['a draft over the published quantity', on(store => { coil(store).draft.quantity = 5; })],
  ['a draft of zero shares', on(store => { coil(store).draft.quantity = 0; })],
  // three COIL at the $111.72 limit is $335.16; the draft's fee buffer is $1.00
  ['a draft its cash cannot fund', on(store => { coil(store).draft.cash_cents = 33515; })],
  ['a draft its cash funds only without the fee buffer', on(store => { coil(store).draft.cash_cents = 33615; })],
  ['a draft its cash funds with the fee buffer exactly', on(store => { coil(store).draft.cash_cents = 33616; })],
  ['a publication hash that is not hex', on(store => { coil(store).publication.sha256 = 'X'.repeat(64); })],
  ['a rules version of eleven characters', on(store => { coil(store).publication.rules_version = 'a'.repeat(11); })],
  // an independent research report
  ['an independent report', indep(() => {})],
  ['an independent report with integral float cohort bytes', () => { const store = independent(); store.items[0].source.cohort.bytes = '__LITERAL__'; return literal(store, '8911.0'); }],
  ['an independent report with a microsecond publication clock', indep(store => { store.items[0].source.publication.published_at = '2026-10-10T07:30:15.553690+00:00'; })],
  ['an independent report with reader projection version true', indep(store => { store.items[0].source.publication.reader_projection_version = true; })],
  ['an independent report under another policy', indep(store => { store.items[0].source.cohort.policy_id = 'anticipation_stop_width_4_to_6_v1'; })],
  ['an independent report whose identity is not its source', indep(store => { store.items[0].id = '0'.repeat(64) + ':' + '1'.repeat(64); })],
  ['an independent report with no report clock', indep(store => { const item = store.items[0]; for (const key of Object.keys(item.report)) item.report[key] = null; item.report_updated_at = null; })],
  ['an independent report of zero cohort bytes', indep(store => { store.items[0].source.cohort.bytes = 0; })],
  ['an independent report from the anticipation stage only', indep(store => { store.items[0].source.stage = 'bursts'; })],
  ['an independent report with a baseline that is not a boolean', indep(store => { store.items[0].source.baseline_admitted = 1; })],
  // A one-string array passes RegExp.test() by coercion; the page tests the type first.
  ['a reference id wrapped in an array', on(store => { const ref = aapl(store).plan.reference; ref.id = [ref.id]; })],
  ['a reference context digest wrapped in an array', on(store => { const ref = aapl(store).plan.reference; ref.context_sha256 = [ref.context_sha256]; })],
  ['a publication digest wrapped in an array', on(store => { const pub = aapl(store).publication; pub.sha256 = [pub.sha256]; })],
  ['a publication rules version wrapped in an array', on(store => { const pub = aapl(store).publication; pub.rules_version = [pub.rules_version]; })],
  ['an independent report ticker wrapped in an array', indep(store => { store.items[0].source.ticker = [store.items[0].source.ticker]; })],
  ['an independent report cohort digest wrapped in an array', indep(store => { const cohort = store.items[0].source.cohort; cohort.sha256 = [cohort.sha256]; })],
  ['an independent report rules version wrapped in an array', indep(store => { const pub = store.items[0].source.publication; pub.rules_version = [pub.rules_version]; })],
  ['an independent report run id wrapped in an array', indep(store => { const pub = store.items[0].source.publication; pub.run_id = [pub.run_id]; })],
  // an owner's own trade (version 4)
  ['an owner trade', own(() => {})],
  ['an owner trade with no fill reported yet', own(store => { Object.assign(ownerRow(store).report, { filled_quantity: null, average_price: null, filled_at: null, protected_quantity: null, protection_confirmed_at: null }); })],
  ['an owner trade without a stop or a label', own(store => { Object.assign(ownerRow(store).report, { account_label: null, stop_price: null }); })],
  ['an owner trade filled on another session than the record counts from', own(store => { ownerRow(store).report.filled_at = '2026-09-14T13:41:00.000Z'; })],
  ['an owner trade filled before the New York day the clock names', own(store => { ownerRow(store).report.filled_at = '2026-09-12T03:30:00.000Z'; })],
  ['an owner trade exited under its reported stop', own(store => { Object.assign(ownerRow(store).report, { exited_quantity: 102, exited_at: '2026-09-14T13:35:00.000Z', average_exit_price: '67.1', entry_fees: '0.00', exit_fees: '0.01' }); })],
  ['an owner trade exited at a sub-cent gain', own(store => { Object.assign(ownerRow(store).report, { exited_quantity: 102, exited_at: '2026-09-15T19:55:00.000Z', average_exit_price: '70.345004', entry_fees: '0.00', exit_fees: '0.00' }); })],
  ['an owner trade with a cent-rounding sell-half level', own(store => { ownerRow(store).report.average_price = '61.72'; })],
  ['an owner trade whose record places no sessions', own(store => { ownerRow(store).source.schedule = null; })],
  ['an owner trade on the anticipation stage', own(store => { const item = ownerRow(store); item.source.stage = 'setting-up'; item.source.row = { rank: 1, grade: null, score: null, scan: null, admitted: null, status: 'no_order', reason: 'coil without a ticket' }; item.id = item.source.publication.sha256 + ':owner:setting-up:NVDA'; })],
  ['an owner trade with an integral float stop level', ownRaw(store => { ownerRow(store).source.rules.sell_half_pct = '__LITERAL__'; return literal(store, '8.0'); })],
  ['an owner trade with a label of forty characters', own(store => { ownerRow(store).report.account_label = 'R'.repeat(40); })],
  ['an owner trade with a label of forty-one characters', own(store => { ownerRow(store).report.account_label = 'R'.repeat(41); })],
  ['an owner trade with a control character in its label', own(store => { ownerRow(store).report.account_label = 'Roth\u0007IRA'; })],
  ['an owner trade with an untrimmed label', own(store => { ownerRow(store).report.account_label = ' Roth IRA '; })],
  ['an owner trade with a label that is not a string', own(store => { ownerRow(store).report.account_label = 7; })],
  ['an owner trade with a zero stop price', own(store => { ownerRow(store).report.stop_price = '0'; })],
  ['an owner trade with a seven-decimal stop price', own(store => { ownerRow(store).report.stop_price = '67.8500001'; })],
  ['an owner trade under a version 3 envelope', own(store => { store.version = 3; const item = ownerRow(store); item.version = 3; for (const key of ['account_label', 'stop_price']) delete item.report[key]; })],
  ['an owner trade with no report clock', own(store => { const item = ownerRow(store); for (const key of Object.keys(item.report)) item.report[key] = null; item.report_updated_at = null; })],
  ['an owner trade whose identity is not its source', own(store => { ownerRow(store).id = ownerRow(store).source.publication.sha256 + ':owner:bursts:AAPL'; })],
  ['an owner trade carrying a draft', own(store => { ownerRow(store).draft = { quantity: 1, cash_cents: 200000, fee_cents: 0 }; })],
  ['an owner trade carrying a plan', own(store => { ownerRow(store).plan = copy(base.items[0].plan); })],
  ['an owner trade on an unknown stage', own(store => { ownerRow(store).source.stage = 'coil'; })],
  ['an owner trade with a lower-case ticker', own(store => { ownerRow(store).source.ticker = 'nvda'; })],
  ['an owner trade with an extra source field', own(store => { ownerRow(store).source.note = 'x'; })],
  ['an owner trade with a rank of zero', own(store => { ownerRow(store).source.row.rank = 0; })],
  ['an owner trade with an integral float rank', ownRaw(store => { ownerRow(store).source.row.rank = '__LITERAL__'; return literal(store, '3.0'); })],
  ['an owner trade with a boolean rank', own(store => { ownerRow(store).source.row.rank = true; })],
  ['an owner trade with a boolean score', own(store => { ownerRow(store).source.row.score = true; })],
  ['an owner trade with a negative score', own(store => { ownerRow(store).source.row.score = -1; })],
  ['an owner trade with a grade of nine letters', own(store => { ownerRow(store).source.row.grade = 'A'.repeat(9); })],
  ['an owner trade with a scan route in capitals', own(store => { ownerRow(store).source.row.scan = 'Both'; })],
  ['an owner trade with an admission that is not a boolean', own(store => { ownerRow(store).source.row.admitted = 1; })],
  ['an owner trade with a status in capitals', own(store => { ownerRow(store).source.row.status = 'No_order'; })],
  ['an owner trade with a reason of 2001 UTF-16 units', own(store => { ownerRow(store).source.row.reason = 'x'.repeat(2001); })],
  ['an owner trade with a reason of 2000 UTF-16 units', own(store => { ownerRow(store).source.row.reason = 'x'.repeat(2000); })],
  ['an owner trade with a reason of 1001 astral characters', own(store => { ownerRow(store).source.row.reason = '\u{1F600}'.repeat(1001); })],
  ['an owner trade with an evidence id that is not hex', own(store => { ownerRow(store).source.evidence_id = 'g'.repeat(64); })],
  ['an owner trade with a three-decimal sell-half percentage', own(store => { ownerRow(store).source.rules.sell_half_pct = 8.001; })],
  ['an owner trade with a zero sell-half percentage', own(store => { ownerRow(store).source.rules.sell_half_pct = 0; })],
  ['an owner trade whose exit day precedes its sell-half day', own(store => { const rules = ownerRow(store).source.rules; rules.sell_half_day = 5; rules.final_exit_day = 3; })],
  ['an owner trade whose entry day is its sell-half day', own(store => { ownerRow(store).source.rules.sell_half_day = 1; })],
  ['an owner trade with a day past thirty', own(store => { ownerRow(store).source.rules.final_exit_day = 31; })],
  ['an owner trade with an integral float day', ownRaw(store => { ownerRow(store).source.rules.final_exit_day = '__LITERAL__'; return literal(store, '5.0'); })],
  ['an owner trade whose placed sessions are out of order', own(store => { const schedule = ownerRow(store).source.schedule; [schedule.sell_half_session, schedule.final_session] = [schedule.final_session, schedule.sell_half_session]; })],
  ['an owner trade whose placed session is not a date', own(store => { ownerRow(store).source.schedule.final_session = '2026-13-01'; })],
  ['an owner trade with an extra placed session', own(store => { ownerRow(store).source.schedule.extra = '2026-09-18'; })],
  ['an owner trade with a publication clock without seconds', own(store => { ownerRow(store).source.publication.published_at = '2026-09-10T22:30+00:00'; })],
  ['an owner trade with a microsecond publication clock', own(store => { ownerRow(store).source.publication.published_at = '2026-09-10T22:30:00.553690+00:00'; })],
  ['an owner trade with a rules digest of eleven characters', own(store => { ownerRow(store).source.publication.rules_version = 'abcdef01234'; })],
  ['an owner trade ticker wrapped in an array', own(store => { ownerRow(store).source.ticker = [ownerRow(store).source.ticker]; })],
  ['an owner trade publication digest wrapped in an array', own(store => { const pub = ownerRow(store).source.publication; pub.sha256 = [pub.sha256]; })],
  ['an owner trade beside the rehearsal records', () => { const store = copy(base); store.items.push(ownerTrade().items[0]); return JSON.stringify(store); }],
  // JavaScript's \d is ASCII; a date or clock spelled in other digits is refused
  ['an owner trade with a placed session in fullwidth digits', own(store => { ownerRow(store).source.schedule.final_session = '\uff12\uff10\uff12\uff16-09-17'; })],
  ['an owner trade with a record clock in fullwidth digits', own(store => { ownerRow(store).created_at = '\uff12\uff10\uff12\uff16-09-11T14:05:00.000Z'; })],
  ['a fill clock in fullwidth digits', on(report({ filled_at: '\uff12\uff10\uff12\uff16-09-11T13:41:00.000Z' }))],
  ['a publication session in fullwidth digits', on(store => { coil(store).publication.session = '\uff12\uff10\uff12\uff16-09-10'; })],
];

const corpus = { version: 1, generated_by: 'tools/private_results_parity.mjs',
  note: 'Synthetic private backups and the page\'s own verdicts on each (app-handoff.js parseStore and summary). Not a real trade.',
  cases: CASES.map(([name, build]) => { const text = build(); return { name, raw: text, page: page(text) }; }) };
const names = corpus.cases.map(item => item.name);
if (new Set(names).size !== names.length) throw new Error('duplicate case names');
const written = JSON.stringify(corpus, null, 1) + '\n';
if (process.argv.includes('--check')) {
  let committed = null;
  try { committed = gunzipSync(await readFile(OUT)).toString('utf8'); } catch (error) { /* reported below */ }
  if (committed !== written) {
    console.error('tests/fixtures/first-trade/parity.json.gz is not what the page says now: node tools/private_results_parity.mjs');
    process.exit(1);
  }
  console.log(`parity corpus current: ${corpus.cases.length} cases, ${corpus.cases.filter(c => c.page.accepted).length} accepted by the page`);
} else {
  await writeFile(OUT, gzipSync(Buffer.from(written, 'utf8'), { level: 9 }));
  console.log(`wrote ${path.relative(ROOT, OUT)}: ${corpus.cases.length} cases, ${corpus.cases.filter(c => c.page.accepted).length} accepted by the page`);
}
