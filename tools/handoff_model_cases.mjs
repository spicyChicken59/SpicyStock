/* Private model controls over the committed run_evening-produced cash fixture.
   No HTTP, provider calls, fabricated production record or browser UI stubs.
   The page's actual morning facts/cash arithmetic are loaded; availability and
   observation authority are explicit injected boundaries, covered again in
   the real browser suite. SCSTOCK_HANDOFF permits isolated source mutations. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import { createHash } from 'node:crypto';
import { gunzipSync } from 'node:zlib';

const ROOT = path.resolve(import.meta.dirname, '..');
const raw = await readFile(path.join(ROOT, 'tests/fixtures/cash-preview/publication.json'), 'utf8');
const HASH = createHash('sha256').update(raw).digest('hex');
const scripts = await Promise.all(['docs/app-cash-preview.js', 'docs/app-morning.js', process.env.SCSTOCK_HANDOFF || 'docs/app-handoff.js'].map(file => readFile(path.resolve(ROOT, file), 'utf8')));
const NOW = '2026-09-11T13:35:00.000Z';
// Exact private-store bytes produced by the original v1 module at 067e792a
// over the committed cash publication, with explicitly synthetic manual facts.
// Kept inline because this runner owns its source controls, not public fixtures.
const LEGACY_RAW = "{\"version\":1,\"items\":[{\"version\":1,\"id\":\"8555facbab2445dcd98240696a5adf5c953769168507336ddc2418cfd8893399:4df6056f0f8d938f9a82186ecfec2ceef6c5f502bfc79f475a80f9d791193e9b\",\"revision\":2,\"created_at\":\"2026-09-11T13:35:00.000Z\",\"updated_at\":\"2026-09-11T13:35:00.000Z\",\"publication\":{\"sha256\":\"8555facbab2445dcd98240696a5adf5c953769168507336ddc2418cfd8893399\",\"session\":\"2026-09-10\",\"published_at\":\"2026-09-10T22:30:00+00:00\",\"rules_version\":\"e87cdf5b1bbe\"},\"plan\":{\"reference\":{\"version\":1,\"id\":\"4df6056f0f8d938f9a82186ecfec2ceef6c5f502bfc79f475a80f9d791193e9b\",\"context_sha256\":\"e7549e1ab149e27a3b207aa7a1bc801475732f4fb28af06994395d75e64d9cb4\",\"plan_sha256\":\"7ff63ac52be72aeb9b4e8d2b72516f692c57de3435f1b4c1153f51c479a4dab7\",\"pick_sha256\":\"52e839012fd40c9391900ff3bcb7465eaea23772e2a7c8e995d14ec8967ae98a\"},\"ticker\":\"COIL\",\"stage\":\"setting-up\",\"order\":{\"symbol\":\"COIL\",\"action\":\"buy\",\"quantity\":4,\"order_type\":\"stop_limit\",\"stop_price\":110.61,\"limit_price\":111.72,\"time_in_force\":\"day\",\"conditional\":\"one_triggers_the_other\",\"then\":{\"action\":\"sell\",\"quantity\":4,\"order_type\":\"stop\",\"stop_price\":109.5,\"time_in_force\":\"gtc\"}},\"timing\":{\"applicable_session\":\"2026-09-11\",\"opens_at\":\"2026-09-11T09:30:00-04:00\",\"cutoff_at\":\"2026-09-11T10:00:00-04:00\",\"closes_at\":\"2026-09-11T16:00:00-04:00\"},\"exit_schedule\":[{\"day\":1,\"date\":\"2026-09-11\",\"key\":\"entry\",\"instruction\":\"buy only if it trades through $110.61 (limit $111.72) in the first 30 minutes; the sell stop at $109.50 is live from the fill; cancel the day order yourself if it has not filled by the end of the first 30 minutes.\"},{\"day\":1,\"date\":\"2026-09-11\",\"key\":\"sell_half_8pct\",\"instruction\":\"if same or next day, the price reaches $119.46 (+8% from $110.61): sell half and move the stop to 25-50 cents under that day's high.\"},{\"day\":1,\"date\":\"2026-09-11\",\"key\":\"entry_day_low\",\"instruction\":\"at the close of day 1: the stop rises to the entry day's low if that is above $109.50.\"},{\"day\":2,\"date\":\"2026-09-14\",\"key\":\"no_breakeven\",\"instruction\":\"if day 2 is green: do not move the stop to break-even before day 5 just because it is green.\"},{\"day\":3,\"date\":\"2026-09-15\",\"key\":\"day3\",\"instruction\":\"at the day 3 close: sell at least half at the close. If day 3 closes at or below $110.61: exit: no follow-through.\"},{\"day\":4,\"date\":\"2026-09-16\",\"key\":\"trail\",\"instruction\":\"raise the stop to each day's low (it never moves down); sell the rest into strength.\"},{\"day\":5,\"date\":\"2026-09-17\",\"key\":\"day5_exit\",\"instruction\":\"at the day 5 close: exit the remainder into strength.\"}]},\"draft\":{\"quantity\":2,\"cash_cents\":200000,\"fee_cents\":100},\"report\":{\"submitted_quantity\":2,\"submitted_at\":null,\"filled_quantity\":1,\"average_price\":\"111.23\",\"filled_at\":\"2026-09-11T13:34:00.000Z\",\"cancelled_quantity\":1,\"cancelled_at\":\"2026-09-11T13:35:00.000Z\",\"exited_quantity\":1,\"exited_at\":\"2026-09-11T13:35:00.000Z\",\"protected_quantity\":0,\"protection_confirmed_at\":null},\"report_updated_at\":\"2026-09-11T13:35:00.000Z\"}]}";

// Exact v2 bytes captured by the original committed model at 703032b9;
// synthetic reported execution over the unchanged cash producer fixture.
const LEGACY_V2_RAW = "{\"version\":2,\"items\":[{\"version\":2,\"id\":\"8555facbab2445dcd98240696a5adf5c953769168507336ddc2418cfd8893399:4df6056f0f8d938f9a82186ecfec2ceef6c5f502bfc79f475a80f9d791193e9b\",\"revision\":2,\"created_at\":\"2026-09-11T13:35:00.000Z\",\"updated_at\":\"2026-09-11T15:45:00.000Z\",\"publication\":{\"sha256\":\"8555facbab2445dcd98240696a5adf5c953769168507336ddc2418cfd8893399\",\"session\":\"2026-09-10\",\"published_at\":\"2026-09-10T22:30:00+00:00\",\"rules_version\":\"e87cdf5b1bbe\"},\"plan\":{\"reference\":{\"version\":1,\"id\":\"4df6056f0f8d938f9a82186ecfec2ceef6c5f502bfc79f475a80f9d791193e9b\",\"context_sha256\":\"e7549e1ab149e27a3b207aa7a1bc801475732f4fb28af06994395d75e64d9cb4\",\"plan_sha256\":\"7ff63ac52be72aeb9b4e8d2b72516f692c57de3435f1b4c1153f51c479a4dab7\",\"pick_sha256\":\"52e839012fd40c9391900ff3bcb7465eaea23772e2a7c8e995d14ec8967ae98a\"},\"ticker\":\"COIL\",\"stage\":\"setting-up\",\"order\":{\"symbol\":\"COIL\",\"action\":\"buy\",\"quantity\":4,\"order_type\":\"stop_limit\",\"stop_price\":110.61,\"limit_price\":111.72,\"time_in_force\":\"day\",\"conditional\":\"one_triggers_the_other\",\"then\":{\"action\":\"sell\",\"quantity\":4,\"order_type\":\"stop\",\"stop_price\":109.5,\"time_in_force\":\"gtc\"}},\"timing\":{\"applicable_session\":\"2026-09-11\",\"opens_at\":\"2026-09-11T09:30:00-04:00\",\"cutoff_at\":\"2026-09-11T10:00:00-04:00\",\"closes_at\":\"2026-09-11T16:00:00-04:00\"},\"exit_schedule\":[{\"day\":1,\"date\":\"2026-09-11\",\"key\":\"entry\",\"instruction\":\"buy only if it trades through $110.61 (limit $111.72) in the first 30 minutes; the sell stop at $109.50 is live from the fill; cancel the day order yourself if it has not filled by the end of the first 30 minutes.\"},{\"day\":1,\"date\":\"2026-09-11\",\"key\":\"sell_half_8pct\",\"instruction\":\"if same or next day, the price reaches $119.46 (+8% from $110.61): sell half and move the stop to 25-50 cents under that day's high.\"},{\"day\":1,\"date\":\"2026-09-11\",\"key\":\"entry_day_low\",\"instruction\":\"at the close of day 1: the stop rises to the entry day's low if that is above $109.50.\"},{\"day\":2,\"date\":\"2026-09-14\",\"key\":\"no_breakeven\",\"instruction\":\"if day 2 is green: do not move the stop to break-even before day 5 just because it is green.\"},{\"day\":3,\"date\":\"2026-09-15\",\"key\":\"day3\",\"instruction\":\"at the day 3 close: sell at least half at the close. If day 3 closes at or below $110.61: exit: no follow-through.\"},{\"day\":4,\"date\":\"2026-09-16\",\"key\":\"trail\",\"instruction\":\"raise the stop to each day's low (it never moves down); sell the rest into strength.\"},{\"day\":5,\"date\":\"2026-09-17\",\"key\":\"day5_exit\",\"instruction\":\"at the day 5 close: exit the remainder into strength.\"}]},\"draft\":{\"quantity\":2,\"cash_cents\":200000,\"fee_cents\":100},\"report\":{\"submitted_quantity\":37,\"submitted_at\":\"2026-09-11T13:31:00.000Z\",\"filled_quantity\":37,\"average_price\":\"111.000001\",\"filled_at\":\"2026-09-11T13:34:00.000Z\",\"cancelled_quantity\":0,\"cancelled_at\":null,\"exited_quantity\":37,\"exited_at\":\"2026-09-11T15:40:00.000Z\",\"protected_quantity\":0,\"protection_confirmed_at\":null,\"average_exit_price\":\"112.000006\",\"entry_fees\":\"1.23\",\"exit_fees\":\"2.34\"},\"report_updated_at\":\"2026-09-11T15:45:00.000Z\"}]}";

const researchFixtures = Object.fromEntries(await Promise.all(['current', 'priority'].map(async name => {
  const folder = path.join(ROOT, 'tests/fixtures/stop-research');
  const publication = gunzipSync(await readFile(path.join(folder, name + '-publication.json.gz')));
  const receipt = JSON.parse(await readFile(path.join(folder, name + '-receipt.json'), 'utf8'));
  const bundleRaw = await readFile(path.join(folder, name + '-bundle.json'));
  assert.equal(createHash('sha256').update(publication).digest('hex'), receipt.publication.data_sha256);
  assert.equal(createHash('sha256').update(bundleRaw).digest('hex'), receipt.bundle.sha256);
  assert.equal(bundleRaw.length, receipt.bundle.bytes);
  return [name, { data: JSON.parse(publication), receipt, bundle: JSON.parse(bundleRaw) }];
})));
const journalFixtures = Object.fromEntries(await Promise.all(['observed', 'cohort-revisions', 'pending', 'basis-conflict', 'not-filled'].map(async name => {
  const folder = path.join(ROOT, 'tests/fixtures/research-outcomes');
  const publication = gunzipSync(await readFile(path.join(folder, name + '-publication.json.gz')));
  const receipt = JSON.parse(await readFile(path.join(folder, name + '-receipt.json'), 'utf8'));
  const bundleRaw = await readFile(path.join(folder, name + '-bundle.json'));
  assert.equal(createHash('sha256').update(publication).digest('hex'), receipt.publication.data_sha256);
  assert.equal(createHash('sha256').update(bundleRaw).digest('hex'), receipt.bundle.sha256);
  assert.equal(bundleRaw.length, receipt.bundle.bytes);
  const bundle = JSON.parse(bundleRaw);
  for (const entry of bundle.cohorts) {
    assert.equal(createHash('sha256').update(entry.source.raw).digest('hex'), entry.source.sha256);
    assert.equal(Buffer.byteLength(entry.source.raw), entry.source.bytes);
  }
  return [name, { data: JSON.parse(publication), receipt, bundle }];
})));

const plain = value => JSON.parse(JSON.stringify(value));
const reportFields = patch => ({ submitted_quantity: '', submitted_at: '', filled_quantity: '', average_price: '', filled_at: '', cancelled_quantity: '', cancelled_at: '', exited_quantity: '', exited_at: '', protected_quantity: '', protection_confirmed_at: '', average_exit_price: '', entry_fees: '', exit_fees: '', ...patch });

function environment(options = {}) {
  const state = { now: NOW, hash: HASH, restriction: null, readFails: false, writeFails: false, writes: 0, badReadback: false, blockLock: null, ...options };
  const store = options.store || new Map(), events = new Map();
  const data = options.data ? plain(options.data) : JSON.parse(raw);
  const makeCandidate = (row, stage) => ({ ticker: row.ticker, stage, status: row.plan?.eligible ? 'ticket' : 'withheld', plan: row.plan, row });
  const api = { data, avail: { offered: true, reason: '', pub: { state: 'fresh' }, timing: {}, phase: 'open' },
    model: { stages: { bursts: data.trades.map(row => makeCandidate(row, 'bursts')), 'setting-up': data.watchlist.top.map(row => makeCandidate(row, 'setting-up')) } },
    observations: { facts: () => ({ canonicalHash: state.hash }), refusal: () => state.restriction } };
  api.reclock = () => { api.avail.offered = Date.parse(state.now) < Date.parse(data.run.timing.cutoff_at); api.avail.reason = api.avail.offered ? '' : 'Entry window ended.'; };
  let queue = Promise.resolve();
  const locks = { request: async (key, fn) => {
    if (state.blockLock) { const waiting = state.blockLock; state.blockLock = null; await waiting; }
    const result = queue.then(fn); queue = result.catch(() => {}); return result;
  } };
  const storage = { getItem: key => { if (state.beforeGet) state.beforeGet(); if (state.readFails) throw Error('read blocked'); const got = store.get(key) ?? null; if (state.readbackFaultPending) { state.readbackFaultPending = false; return got + ' '; } return state.badReadback && got !== null ? got + ' ' : got; },
    setItem: (key, value) => { state.writes++; if (state.writeFails) throw Error('quota'); store.set(key, value); if (state.failNextReadback) { state.failNextReadback = false; state.readbackFaultPending = true; } }, removeItem: key => store.delete(key) };
  const window = { SCStock: api, localStorage: storage, navigator: state.noLocks ? {} : { locks }, TextEncoder, addEventListener: (type, fn) => events.set(type, fn) };
  class Clock extends Date { constructor(...args) { super(...(args.length ? args : [state.now])); } static now() { return Date.parse(state.now); } }
  const context = vm.createContext({ window, Date: Clock });
  scripts.forEach(script => vm.runInContext(script, context));
  const handoff = api.handoff;
  return { api, handoff, state, store, events,
    prepare: patch => handoff.prepare({ key: 'setting-up:COIL', cash: '2000', fees: '1', quantity: '2', expectedPublication: HASH, expectedRevision: null, ...patch }) };
}

// The source verifier is an explicit injected boundary here. It returns exact
// descriptors from genuine retained producer bundles, never invented stock
// cards. Browser controls exercise the real verifier and its byte binding.
function researchEnvironment(name = 'current', ticker = 'KE', options = {}) {
  const fixture = researchFixtures[name], { receipt, bundle } = fixture;
  const row = bundle.rows.find(row => row.ticker === ticker); assert.ok(row);
  const source = { ticker, stage: 'setting-up', publication: plain(receipt.publication),
    cohort: { sha256: receipt.bundle.sha256, bytes: receipt.bundle.bytes, generated_at: receipt.timing.generated_at, policy_id: receipt.policy.id },
    evidence: plain(row.evidence), baseline_admitted: row.baseline.admitted };
  const request = { recordHash: receipt.publication.reader_sha256, projected: true, publication: plain(source.publication), cohort: plain(source.cohort), ticker, evidence: plain(source.evidence) };
  const env = environment({ data: fixture.data, hash: receipt.publication.data_sha256, now: '2026-10-12T14:05:00Z', ...options });
  env.state.source = source; env.state.request = request; env.state.verifierCalls = 0;
  env.api.stopResearch = { reportReference: input => {
    env.state.verifierCalls++;
    return !env.state.sourceUnavailable && JSON.stringify(input) === JSON.stringify(env.state.request)
      ? { ok: true, source: plain(env.state.source) } : { ok: false, error: 'Research reference changed.' };
  } };
  return { ...env, request, source, create: fields => env.handoff.reportResearch(request, reportFields(fields), null) };
}

// Only the verifier boundary is injected. Active and original publications,
// raw cohort identities and row evidence come from genuine producer fixtures.
function journalEnvironment(name = 'observed', ticker = 'COIL', options = {}) {
  const fixture = journalFixtures[name], { receipt, bundle } = fixture, entry = bundle.cohorts[options.cohortIndex || 0];
  const original = JSON.parse(entry.source.raw), row = original.rows.find(row => row.ticker === ticker); assert.ok(row);
  const source = { ticker, stage: 'setting-up', publication: plain(original.publication),
    cohort: { sha256: entry.source.sha256, bytes: entry.source.bytes, generated_at: original.timing.generated_at, policy_id: original.policy.id },
    evidence: plain(row.evidence), baseline_admitted: row.baseline.admitted };
  const request = { origin: 'retained_journal', recordHash: receipt.publication.reader_sha256, projected: true, publication: plain(receipt.publication),
    journal: { sha256: receipt.bundle.sha256, bytes: receipt.bundle.bytes, generated_at: receipt.generated_at, cohort_set_sha256: receipt.cohort_set_sha256 },
    cohort: plain(source.cohort), ticker, evidence: plain(source.evidence) };
  const env = environment({ data: fixture.data, hash: receipt.publication.data_sha256, now: '2026-11-07T20:00:00Z', ...options });
  Object.assign(env.state, { source, request: plain(request), activePublication: plain(receipt.publication), verifierCalls: 0, comparisonCalls: 0 });
  env.api.researchOutcomes = { reportReference: input => {
    env.state.verifierCalls++;
    return !env.state.sourceUnavailable && JSON.stringify(input) === JSON.stringify(env.state.request)
      ? { ok: true, source: plain(env.state.source), publication: plain(env.state.activePublication) } : { ok: false, error: 'Journal reference changed.' };
  } };
  env.api.stopResearch = { reportReference: () => { env.state.comparisonCalls++; return { ok: true, source: plain(env.state.source) }; } };
  return { ...env, request, source, create: fields => env.handoff.reportResearch(request, reportFields(fields), null) };
}

test('retained journal inspection binds the active publication while preserving the older original source without writes', () => {
  const env = journalEnvironment(), before = JSON.stringify(env.api.data);
  assert.notEqual(env.source.publication.data_sha256, env.state.hash);
  const inspected = env.handoff.inspectResearch(env.request); assert.equal(inspected.ok, true, inspected.error);
  assert.deepEqual(plain(inspected.source), env.source); assert.equal(Object.keys(inspected).sort().join(','), 'ok,source');
  inspected.source.cohort.sha256 = 'f'.repeat(64); assert.notEqual(env.source.cohort.sha256, inspected.source.cohort.sha256);
  assert.equal(env.state.comparisonCalls, 0); assert.equal(env.state.writes, 0); assert.equal(env.store.size, 0); assert.equal(JSON.stringify(env.api.data), before);
});

test('retained journal dispatch refuses every present unsupported origin without comparison fallback', () => {
  for (const origin of [null, undefined, '', 'current', false, 'retained_journal_v2']) {
    const env = researchEnvironment(), request = { ...env.request, origin }; env.state.request = request;
    const result = env.handoff.inspectResearch(request); assert.equal(result.ok, false); assert.match(result.error, /unsupported origin/);
    assert.equal(env.state.verifierCalls, 0); assert.equal(env.state.writes, 0);
  }
  for (const absent of [true, false]) {
    const env = journalEnvironment(); if (absent) delete env.api.researchOutcomes; else env.state.sourceUnavailable = true;
    assert.equal(env.handoff.inspectResearch(env.request).ok, false); assert.equal(env.state.comparisonCalls, 0);
  }
});

test('retained journal support never relaxes the current comparison original publication hash guard', () => {
  const env = journalEnvironment(), current = plain(env.request); delete current.origin;
  assert.equal(env.handoff.inspectResearch(current).ok, false); assert.equal(env.state.comparisonCalls, 1); assert.equal(env.state.verifierCalls, 0);
  env.state.hash = env.source.publication.data_sha256;
  assert.equal(env.handoff.inspectResearch(current).ok, true);
  assert.equal(env.handoff.inspectResearch(env.request).ok, false); assert.equal(env.state.writes, 0);
});

test('retained journal active publication and original source are separately strict rather than caller authority', async () => {
  for (const change of [pub => { pub.data_sha256 = 'f'.repeat(64); }, pub => { pub.run_id = null; }, pub => { delete pub.context_sha256; }, pub => { pub.reader_projection_version = 2; }, pub => { pub.published_at = '2026-10-12T20:00:00.1234567Z'; }, pub => { pub.extra = true; }]) {
    const env = journalEnvironment(); change(env.state.activePublication);
    const result = await env.create({ submitted_quantity: '1', filled_quantity: '1' }); assert.equal(result.ok, false); assert.match(result.error, /verified publication/); assert.equal(env.state.writes, 0);
  }
  for (const change of [source => { source.publication.run_id = null; }, source => { source.cohort.bytes = 131073; }, source => { source.evidence.id = null; }, source => { source.baseline_admitted = 'false'; }, source => { source.order = {}; }]) {
    const env = journalEnvironment(); change(env.state.source); assert.equal(env.handoff.inspectResearch(env.request).ok, false);
    assert.equal((await env.create({ submitted_quantity: '1', filled_quantity: '1' })).ok, false); assert.equal(env.state.writes, 0);
  }
});

test('retained journal reference and canonical authority are reverified after waiting for the save lock', async () => {
  for (const change of [env => { env.state.sourceUnavailable = true; }, env => { env.state.request.journal.sha256 = 'a'.repeat(64); }, env => { env.state.hash = 'b'.repeat(64); }]) {
    const env = journalEnvironment(); assert.equal(env.handoff.inspectResearch(env.request).ok, true);
    let unlock; env.state.blockLock = new Promise(resolve => { unlock = resolve; });
    const waiting = env.create({ submitted_quantity: '2', filled_quantity: '1' }); change(env); unlock();
    assert.equal((await waiting).ok, false); assert.equal(env.state.verifierCalls, 2); assert.equal(env.state.writes, 0); assert.equal(env.store.size, 0);
  }
});

test('retained journal first save still requires explicit positive reconciled fills and carries no hypothetical outcome facts', async () => {
  const env = journalEnvironment();
  for (const fields of [{}, { submitted_quantity: '1', filled_quantity: '0' }, { filled_quantity: '1' }, { submitted_quantity: '1', filled_quantity: '2' }, { submitted_quantity: '2', filled_quantity: '1', cancelled_quantity: '2' }]) {
    assert.equal((await env.create(fields)).ok, false); assert.equal(env.state.writes, 0);
  }
  for (const [name, ticker] of [['observed', 'COIL'], ['observed', 'RONE'], ['observed', 'RTHR'], ['observed', 'RTWO'], ['observed', 'ZBASE'], ['basis-conflict', 'COIL'], ['not-filled', 'COIL'], ['pending', 'KE']]) {
    const row = journalEnvironment(name, ticker), saved = await row.create({ submitted_quantity: '9', filled_quantity: '7' }); assert.equal(saved.ok, true, saved.error);
    assert.deepEqual(plain(saved.item.source), row.source); assert.equal(saved.item.id, row.source.publication.data_sha256 + ':' + row.source.evidence.id);
    for (const [key, value] of Object.entries(saved.item.report)) assert.equal(value, key === 'submitted_quantity' ? 9 : key === 'filled_quantity' ? 7 : null, key);
    assert.equal(saved.item.version, 3); assert.equal(saved.item.kind, 'independent_research'); assert.equal('draft' in saved.item, false); assert.equal('plan' in saved.item, false);
    assert.equal(row.handoff.summary(saved.item).completed_result.state, 'incomplete'); assert.equal(row.handoff.summary(saved.item).reported_held_quantity, null);
    assert.equal(row.handoff.readback(saved.item), ''); assert.equal(row.handoff.copy(saved.item.id).ok, false);
  }
});

test('retained journal cohort revisions share original identity and never replace a saved source', async () => {
  const first = journalEnvironment('cohort-revisions'), saved = await first.create({ submitted_quantity: '2', filled_quantity: '1' }); assert.equal(saved.ok, true, saved.error);
  const next = journalEnvironment('cohort-revisions', 'COIL', { cohortIndex: 1, store: first.store }); assert.notEqual(next.source.cohort.sha256, first.source.cohort.sha256);
  assert.equal(next.source.publication.data_sha256, first.source.publication.data_sha256); assert.equal(next.source.evidence.id, first.source.evidence.id);
  const before = first.store.get(first.handoff.KEY), duplicate = await next.create({ submitted_quantity: '4', filled_quantity: '4' });
  assert.equal(duplicate.ok, false); assert.equal(duplicate.existingId, saved.item.id); assert.equal(first.store.get(first.handoff.KEY), before);
  assert.deepEqual(plain(next.handoff.find(saved.item.id).source), first.source);
});

test('retained journal and current comparison or planned handoffs use one duplicate namespace in both directions', async () => {
  for (const planned of [false, true]) {
    const first = researchEnvironment('priority', 'ZBASE', { now: '2026-10-12T13:35:00Z' });
    const saved = planned ? await first.prepare({ key: 'setting-up:ZBASE', expectedPublication: first.state.hash, quantity: '1', fees: '0' }) : await first.create({ submitted_quantity: '1', filled_quantity: '1' });
    assert.equal(saved.ok, true, saved.error);
    const journal = journalEnvironment('observed', 'ZBASE', { store: first.store }), before = first.store.get(first.handoff.KEY), duplicate = await journal.create({ submitted_quantity: '3', filled_quantity: '2' });
    assert.equal(duplicate.ok, false); assert.equal(duplicate.existingId, saved.item.id); assert.equal(first.store.get(first.handoff.KEY), before);
  }
  const journal = journalEnvironment('observed', 'ZBASE'), saved = await journal.create({ submitted_quantity: '3', filled_quantity: '2' }); assert.equal(saved.ok, true, saved.error);
  const current = researchEnvironment('priority', 'ZBASE', { now: '2026-10-12T13:35:00Z', store: journal.store }), before = journal.store.get(journal.handoff.KEY);
  const duplicate = await current.create({ submitted_quantity: '1', filled_quantity: '1' }); assert.equal(duplicate.ok, false); assert.equal(duplicate.existingId, saved.item.id);
  assert.equal((await current.prepare({ key: 'setting-up:ZBASE', expectedPublication: current.state.hash, quantity: '1', fees: '0', expectedRevision: 1 })).ok, false);
  assert.equal(journal.store.get(journal.handoff.KEY), before);
});

test('retained journal saved corrections and exact backup survive disappearance while failed writes preserve recovery', async () => {
  const env = journalEnvironment('observed', 'COIL', { store: new Map([['spicystock:handoff:v1', LEGACY_V2_RAW]]) }); env.state.writeFails = true;
  assert.equal((await env.create({ submitted_quantity: '2', filled_quantity: '1' })).ok, false);
  assert.equal(env.handoff.recovery().prior, LEGACY_V2_RAW); assert.equal(env.store.get(env.handoff.KEY), LEGACY_V2_RAW);
  const proposed = JSON.parse(env.handoff.recovery().proposed); assert.deepEqual(proposed.items[1].source, env.source);
  env.state.writeFails = false; const saved = await env.create({ submitted_quantity: '2', filled_quantity: '1' }); assert.equal(saved.ok, true, saved.error);
  env.state.sourceUnavailable = true; env.state.hash = 'e'.repeat(64);
  const corrected = await env.handoff.report(saved.item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1', exited_quantity: '0' }), 1); assert.equal(corrected.ok, true, corrected.error);
  assert.deepEqual(plain(corrected.item.source), env.source); assert.equal(env.handoff.summary(corrected.item).reported_held_quantity, 1);
  assert.equal((await env.handoff.report(saved.item.id, reportFields({ submitted_quantity: '2', filled_quantity: '2' }), 1)).ok, false);
  const backup = env.handoff.exportBackup(); assert.equal(backup.ok, true); assert.equal(backup.raw, env.store.get(env.handoff.KEY));
  const fresh = environment(), preview = fresh.handoff.previewBackup(backup.raw); assert.equal(preview.ok, true, preview.error);
  assert.equal((await fresh.handoff.restoreBackup(preview.preview)).ok, true); assert.equal(fresh.store.get(fresh.handoff.KEY), backup.raw);
  assert.deepEqual(plain(fresh.handoff.find(saved.item.id).source), env.source); assert.equal(fresh.handoff.copy(saved.item.id).ok, false);
});

test('verified research inspection is read-only with no defaults and preserves exact microsecond source clocks', () => {
  const env = researchEnvironment(), before = JSON.stringify(env.api.data);
  const inspected = env.handoff.inspectResearch(env.request); assert.equal(inspected.ok, true, inspected.error);
  assert.deepEqual(plain(inspected.source), env.source);
  assert.equal(inspected.source.publication.published_at, '2026-10-10T07:30:15.553690+00:00');
  assert.equal(inspected.source.baseline_admitted, false);
  assert.equal(env.state.writes, 0); assert.equal(env.store.size, 0); assert.equal(env.handoff.list().length, 0);
  assert.equal(JSON.stringify(env.api.data), before); assert.equal('report' in inspected, false);
  inspected.source.ticker = 'CHANGED'; assert.equal(env.state.source.ticker, 'KE');
});

test('independent creation requires a positive actual fill and reconciled submitted quantity', async () => {
  const env = researchEnvironment();
  for (const fields of [{}, { submitted_quantity: '2', filled_quantity: '0' }, { filled_quantity: '1' }, { submitted_quantity: '1', filled_quantity: '2' }, { submitted_quantity: '2', filled_quantity: '1', cancelled_quantity: '2' }]) {
    const result = await env.create(fields); assert.equal(result.ok, false, JSON.stringify(fields));
    assert.equal(env.state.writes, 0); assert.equal(env.store.size, 0);
  }
  const saved = await env.create({ submitted_quantity: '9', filled_quantity: '7' }); assert.equal(saved.ok, true, saved.error);
  assert.equal(saved.item.kind, 'independent_research'); assert.equal(saved.item.version, 3);
  for (const key of ['draft', 'plan', 'order', 'publication', 'cash']) assert.equal(key in saved.item, false, key);
  assert.equal(saved.item.report.submitted_quantity, 9); assert.equal(saved.item.report.filled_quantity, 7);
  for (const [key, value] of Object.entries(saved.item.report)) if (!['submitted_quantity', 'filled_quantity'].includes(key)) assert.equal(value, null, key);
  const summary = env.handoff.summary(saved.item);
  assert.equal(summary.reported_held_quantity, null); assert.equal(summary.protection, 'unknown'); assert.equal(summary.calculation, null); assert.equal(summary.planned_quantity, null);
  assert.equal(summary.completed_result.state, 'incomplete'); assert.equal(summary.exit_review.model_half_quantity, null);
});

test('independent reports reconcile actual partial exits and exact results without model sizing or cash assumptions', async () => {
  const env = researchEnvironment(), original = JSON.stringify(env.api.data);
  const fields = { submitted_quantity: '9', filled_quantity: '7', cancelled_quantity: '2', exited_quantity: '3', protected_quantity: '5', average_price: '31.234567', filled_at: '2026-10-09T13:40:00Z', exited_at: '2026-10-09T14:01:00Z', average_exit_price: '32.345678', entry_fees: '0.11', exit_fees: '0.22' };
  let result = await env.create(fields); assert.equal(result.ok, true, result.error);
  let summary = env.handoff.summary(result.item);
  assert.equal(summary.reported_held_quantity, 4); assert.equal(summary.protection, 'over'); assert.equal(summary.unfilled_quantity, 2); assert.equal(summary.uncancelled_quantity, 0);
  assert.equal(summary.completed_result.state, 'incomplete'); assert.equal(summary.completed_result.net_display, null);
  result = await env.handoff.report(result.item.id, reportFields({ ...fields, exited_quantity: '7', protected_quantity: '0' }), 1); assert.equal(result.ok, true, result.error);
  summary = env.handoff.summary(result.item);
  assert.equal(summary.completed_result.gross_microusd, '7777777'); assert.equal(summary.completed_result.fees_microusd, '330000'); assert.equal(summary.completed_result.net_microusd, '7447777'); assert.equal(summary.completed_result.net_display, '$7.45');
  assert.equal(summary.reported_held_quantity, 0); assert.equal(summary.protection, 'matched'); assert.equal(summary.exit_review.model_half_quantity, null);
  assert.equal(JSON.stringify(env.api.data), original); assert.equal(env.store.size, 1);
});

test('independent missing costs times and remainder facts stay unknown while exact zero and subcent results remain valid', async () => {
  const fields = { submitted_quantity: '1', filled_quantity: '1', cancelled_quantity: '0', exited_quantity: '1', average_price: '30', average_exit_price: '30.000001', filled_at: '2026-10-12T13:35:00Z', exited_at: '2026-10-12T13:40:00Z', entry_fees: '0', exit_fees: '0' };
  for (const key of ['cancelled_quantity', 'average_price', 'average_exit_price', 'filled_at', 'exited_at', 'entry_fees', 'exit_fees']) {
    const env = researchEnvironment(), saved = await env.create({ ...fields, [key]: '' }); assert.equal(saved.ok, true, saved.error);
    const summary = env.handoff.summary(saved.item).completed_result; assert.equal(summary.state, 'incomplete', key); assert.equal(summary.net_microusd, null, key);
  }
  const env = researchEnvironment(), saved = await env.create(fields); assert.equal(saved.ok, true, saved.error);
  const result = env.handoff.summary(saved.item).completed_result; assert.equal(result.net_microusd, '1'); assert.equal(result.net_display, '<$0.01'); assert.equal(result.outcome, 'gain');
});

test('independent records can never become an entry readback even after facts are corrected to unknown', async () => {
  const env = researchEnvironment(), saved = await env.create({ submitted_quantity: '1', filled_quantity: '1' }); assert.equal(saved.ok, true, saved.error);
  assert.equal(env.handoff.copy(saved.item.id).ok, false); assert.equal(env.handoff.availability(saved.item).ok, false); assert.equal(env.handoff.readback(saved.item), '');
  const corrected = await env.handoff.report(saved.item.id, reportFields({}), 1); assert.equal(corrected.ok, true, corrected.error);
  assert.equal(env.handoff.summary(corrected.item).state, 'reported_unknown_fill'); assert.equal(env.handoff.copy(saved.item.id).ok, false); assert.equal(env.handoff.readback(corrected.item), '');
  assert.equal(env.handoff.summary(corrected.item).exit_review.model_remaining_quantity, null);
});

test('admitted research origin is retained exactly but does not grant independent reports order authority', async () => {
  const env = researchEnvironment('priority', 'ZBASE'); assert.equal(env.source.baseline_admitted, true);
  const saved = await env.create({ submitted_quantity: '30', filled_quantity: '20' }); assert.equal(saved.ok, true, saved.error);
  assert.equal(saved.item.source.baseline_admitted, true); assert.equal(env.handoff.readback(saved.item), ''); assert.equal(env.handoff.copy(saved.item.id).ok, false);
  env.state.now = '2026-10-12T13:35:00Z';
  const preparation = await env.prepare({ key: 'setting-up:ZBASE', expectedPublication: env.state.hash, expectedRevision: 1, quantity: '1', fees: '0' });
  assert.equal(preparation.ok, false); assert.deepEqual(plain(env.handoff.find(saved.item.id).source), env.source);
});

test('one original idea has one private record across planned and independently reported origins', async () => {
  const env = researchEnvironment('priority', 'ZBASE', { now: '2026-10-12T13:35:00Z' });
  const prepared = await env.prepare({ key: 'setting-up:ZBASE', expectedPublication: env.state.hash, quantity: '1', fees: '0' }); assert.equal(prepared.ok, true, prepared.error);
  const before = env.store.get(env.handoff.KEY), duplicate = await env.create({ submitted_quantity: '1', filled_quantity: '1' });
  assert.equal(duplicate.ok, false); assert.equal(duplicate.existingId, prepared.item.id); assert.equal(env.store.get(env.handoff.KEY), before);
  const other = researchEnvironment(), saved = await other.create({ submitted_quantity: '1', filled_quantity: '1' }); assert.equal(saved.ok, true, saved.error);
  const same = await other.create({ submitted_quantity: '2', filled_quantity: '2' }); assert.equal(same.ok, false); assert.equal(same.existingId, saved.item.id); assert.equal(other.handoff.list().length, 1);
});

test('creation rejects detached source identity and rechecks publication after the storage lock', async () => {
  const env = researchEnvironment();
  const detached = plain(env.request); detached.cohort.sha256 = 'f'.repeat(64);
  assert.equal(env.handoff.inspectResearch(detached).ok, false);
  assert.equal((await env.handoff.reportResearch(detached, reportFields({ submitted_quantity: '1', filled_quantity: '1' }), null)).ok, false);
  let unlock; env.state.blockLock = new Promise(resolve => { unlock = resolve; });
  const waiting = env.create({ submitted_quantity: '1', filled_quantity: '1' });
  env.state.hash = 'a'.repeat(64); unlock(); const result = await waiting;
  assert.equal(result.ok, false); assert.match(result.error, /verified publication/); assert.equal(env.state.writes, 0);
});

test('research reference is verified twice and malformed descriptors cannot enter private storage', async () => {
  for (const change of [source => { source.baseline_admitted = 'false'; }, source => { source.order = {}; }, source => { source.cohort.bytes = 131073; }, source => { source.publication.published_at = '2026-10-10T12:00:00'; }, source => { source.cohort.generated_at = '2026-10-10T12:00:00.1234567Z'; }, source => { source.evidence.inputs_sha256 = null; }]) {
    const env = researchEnvironment(); change(env.state.source);
    assert.equal((await env.create({ submitted_quantity: '1', filled_quantity: '1' })).ok, false); assert.equal(env.state.writes, 0);
  }
  const env = researchEnvironment(); assert.equal(env.handoff.inspectResearch(env.request).ok, true); env.state.sourceUnavailable = true;
  assert.equal((await env.create({ submitted_quantity: '1', filled_quantity: '1' })).ok, false); assert.equal(env.state.verifierCalls, 2); assert.equal(env.state.writes, 0);
});

test('independent corrections preserve original source after expiry replacement and exclusion with revision conflicts refused', async () => {
  const env = researchEnvironment(), saved = await env.create({ submitted_quantity: '2', filled_quantity: '1' }); assert.equal(saved.ok, true, saved.error);
  const source = plain(saved.item.source); env.state.now = '2026-12-01T16:00:00Z'; env.state.hash = 'a'.repeat(64); env.state.restriction = 'Known event'; env.state.sourceUnavailable = true;
  const revised = await env.handoff.report(saved.item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1', exited_quantity: '0', protected_quantity: '0' }), 1);
  assert.equal(revised.ok, true, revised.error); assert.deepEqual(plain(revised.item.source), source); assert.equal(env.handoff.summary(revised.item).protection, 'under');
  const stale = await env.handoff.report(saved.item.id, reportFields({ submitted_quantity: '2', filled_quantity: '2' }), 1); assert.equal(stale.ok, false); assert.equal(env.handoff.find(saved.item.id).report.filled_quantity, 1);
  assert.equal(env.handoff.copy(saved.item.id).ok, false); assert.equal((await env.create({ submitted_quantity: '2', filled_quantity: '1' })).ok, false);
});

test('independent schema rejects authority payloads and future records without losing original bytes', async () => {
  const source = researchEnvironment(), saved = await source.create({ submitted_quantity: '1', filled_quantity: '1' }); assert.equal(saved.ok, true, saved.error);
  const raw = source.store.get(source.handoff.KEY);
  for (const change of [store => { store.items[0].draft = {}; }, store => { store.items[0].plan = {}; }, store => { store.items[0].kind = 'planned_handoff'; }, store => { store.version = 99; }, store => { store.items[0].source.publication.data_sha256 = 'a'.repeat(64); }, store => { store.items[0].report_updated_at = null; }]) {
    const value = JSON.parse(raw); change(value); const corrupt = JSON.stringify(value), env = researchEnvironment('current', 'KE', { store: new Map([[source.handoff.KEY, corrupt]]) });
    assert.equal(env.handoff.status().available, false); assert.equal((await env.create({ submitted_quantity: '1', filled_quantity: '1' })).ok, false);
    assert.equal(env.store.get(env.handoff.KEY), corrupt); assert.equal(env.state.writes, 0); assert.equal(env.handoff.recovery().prior, corrupt);
  }
});

test('independent save failures retain exact prior and proposed reports and lock failures do not write', async () => {
  const env = researchEnvironment('current', 'KE', { store: new Map([['spicystock:handoff:v1', LEGACY_V2_RAW]]) }); env.state.writeFails = true;
  const failed = await env.create({ submitted_quantity: '1', filled_quantity: '1' }); assert.equal(failed.ok, false);
  assert.equal(env.store.get(env.handoff.KEY), LEGACY_V2_RAW); assert.equal(env.handoff.recovery().prior, LEGACY_V2_RAW);
  const proposed = JSON.parse(env.handoff.recovery().proposed); assert.equal(proposed.version, 3); assert.equal(proposed.items.length, 2); assert.equal(proposed.items[1].kind, 'independent_research');
  env.state.writeFails = false; const saved = await env.create({ submitted_quantity: '1', filled_quantity: '1' }); assert.equal(saved.ok, true, saved.error);
  assert.equal(env.handoff.list()[0].report.entry_fees, '1.23');
  const blocked = researchEnvironment('current', 'KE', { noLocks: true }); assert.equal((await blocked.create({ submitted_quantity: '1', filled_quantity: '1' })).ok, false); assert.equal(blocked.state.writes, 0);
});

test('genuine v2 costs and all semantic fields survive read-only migration then explicit v3 save', async () => {
  const old = JSON.parse(LEGACY_V2_RAW).items[0], env = environment({ now: '2030-01-02T16:00:00Z', store: new Map([['spicystock:handoff:v1', LEGACY_V2_RAW]]) });
  assert.equal(env.handoff.status().available, true); const item = env.handoff.list()[0];
  assert.deepEqual(plain(item), { ...old, version: 3, kind: 'planned_handoff' }); assert.equal(env.state.writes, 0); assert.equal(env.store.get(env.handoff.KEY), LEGACY_V2_RAW);
  assert.equal(env.handoff.summary(item).completed_result.net_microusd, '33430185');
  const saved = await env.handoff.report(item.id, item.report, item.revision); assert.equal(saved.ok, true, saved.error);
  assert.equal(JSON.parse(env.store.get(env.handoff.KEY)).version, 3); assert.deepEqual(plain(saved.item.report), old.report);
  for (const key of ['id', 'publication', 'plan', 'draft', 'created_at']) assert.deepEqual(plain(saved.item[key]), old[key]);
});

test('legacy v2 costs and exit-price guards still reject invalid old records before migration', () => {
  for (const change of [item => { item.report.entry_fees = '-1'; }, item => { item.report.exit_fees = '0.001'; }, item => { item.report.average_exit_price = '0'; }, item => { item.report.exited_quantity = 0; item.report.exited_at = null; }, item => { item.kind = 'planned_handoff'; }]) {
    const value = JSON.parse(LEGACY_V2_RAW); change(value.items[0]); const raw = JSON.stringify(value), env = environment({ store: new Map([['spicystock:handoff:v1', raw]]) });
    assert.equal(env.handoff.status().available, false); assert.equal(env.state.writes, 0); assert.equal(env.store.get(env.handoff.KEY), raw);
  }
});

test('planned source clocks preserve upstream microseconds while manual event clocks remain strict', async () => {
  // A narrow source-clock unit variation of the real producer record, not a
  // new provenance fixture or claim of another production publication.
  const env = environment(); env.api.data.run.published_at = '2026-09-10T22:30:00.123456+00:00';
  env.state.hash = createHash('sha256').update(JSON.stringify(env.api.data)).digest('hex');
  const saved = await env.prepare({ expectedPublication: env.state.hash }); assert.equal(saved.ok, true, saved.error);
  assert.equal(saved.item.publication.published_at, env.api.data.run.published_at);
  const raw = env.store.get(env.handoff.KEY), reload = environment({ store: env.store });
  assert.equal(reload.handoff.status().available, true); assert.equal(reload.state.writes, 0); assert.equal(reload.store.get(env.handoff.KEY), raw);
  const manual = await env.handoff.report(saved.item.id, reportFields({ submitted_quantity: '1', filled_quantity: '1', filled_at: '2026-09-11T13:34:00.123456Z' }), 1);
  assert.equal(manual.ok, false); assert.match(manual.error, /valid date and time/);
  env.api.data.run.published_at = '2026-09-10T22:30:00.1234567+00:00'; env.state.hash = createHash('sha256').update(JSON.stringify(env.api.data)).digest('hex');
  assert.equal((await env.prepare({ expectedPublication: env.state.hash })).ok, false);
});

test('backup exports and restores exact original legacy bytes including whitespace without migration', async () => {
  for (const original of [LEGACY_RAW, LEGACY_V2_RAW]) {
    const raw = ' \n' + original + '\t\n', saved = JSON.parse(raw), source = environment({ store: new Map([['spicystock:handoff:v1', raw]]) });
    const backup = source.handoff.exportBackup(); assert.equal(backup.ok, true, backup.error); assert.equal(backup.raw, raw);
    assert.equal(backup.summary.version, saved.version); assert.equal(backup.summary.count, 1); assert.equal(backup.summary.planned_count, 1); assert.equal(backup.summary.independent_count, 0);
    assert.equal(backup.summary.records[0].published_at, saved.items[0].publication.published_at); assert.equal(backup.summary.records[0].updated_at, saved.items[0].updated_at);
    assert.equal(source.state.writes, 0); assert.equal(source.store.get(source.handoff.KEY), raw);
    const destination = environment(), preview = destination.handoff.previewBackup(raw); assert.equal(preview.ok, true, preview.error);
    assert.equal(preview.preview.expectedRaw, null); assert.equal(destination.state.writes, 0); assert.equal(destination.handoff.list().length, 0);
    const restored = await destination.handoff.restoreBackup(preview.preview); assert.equal(restored.ok, true, restored.error);
    assert.equal(destination.store.get(destination.handoff.KEY), raw); assert.equal(destination.state.writes, 1); assert.equal(destination.handoff.exportBackup().raw, raw);
    assert.equal(JSON.parse(destination.handoff.exportBackup().raw).version, saved.version);
    const view = destination.handoff.list()[0]; assert.deepEqual(plain(view.report), plain(source.handoff.list()[0].report));
    assert.equal(destination.handoff.copy(view.id).ok, false); assert.equal(destination.handoff.recovery().proposed, null);
  }
});

test('mixed planned and independent backups preserve unknown corrections source identity and authority', async () => {
  const source = researchEnvironment('current', 'KE', { store: new Map([['spicystock:handoff:v1', LEGACY_V2_RAW]]) });
  const created = await source.create({ submitted_quantity: '9', filled_quantity: '7' }); assert.equal(created.ok, true, created.error);
  const corrected = await source.handoff.report(created.item.id, reportFields({}), 1); assert.equal(corrected.ok, true, corrected.error);
  const original = source.store.get(source.handoff.KEY), backup = source.handoff.exportBackup();
  assert.equal(backup.ok, true, backup.error); assert.equal(backup.summary.version, 3); assert.equal(backup.summary.count, 2); assert.equal(backup.summary.planned_count, 1); assert.equal(backup.summary.independent_count, 1);
  assert.equal(backup.summary.records[1].ticker, 'KE'); assert.equal(backup.summary.records[1].session, '2026-10-09'); assert.equal(backup.summary.records[1].published_at, source.source.publication.published_at);
  const dest = environment({ now: '2030-01-02T16:00:00Z', hash: null }); dest.api.data = null; dest.api.model = null;
  const preview = dest.handoff.previewBackup(backup.raw); assert.equal(preview.ok, true, preview.error);
  const restored = await dest.handoff.restoreBackup(preview.preview); assert.equal(restored.ok, true, restored.error); assert.equal(dest.store.get(dest.handoff.KEY), original);
  const independent = dest.handoff.find(created.item.id); assert.deepEqual(plain(independent), plain(corrected.item)); assert.equal(dest.handoff.readback(independent), ''); assert.equal(dest.handoff.copy(independent.id).ok, false);
  assert.equal(dest.handoff.summary(independent).state, 'reported_unknown_fill'); assert.equal(dest.handoff.summary(independent).calculation, null);
  assert.equal(dest.handoff.summary(dest.handoff.list()[0]).completed_result.net_microusd, '33430185');
});

test('restored unreported planned draft still needs exact current publication time and event guards', async () => {
  const source = environment(), saved = await source.prepare(); assert.equal(saved.ok, true, saved.error);
  const raw = source.handoff.exportBackup().raw, dest = environment(), preview = dest.handoff.previewBackup(raw);
  assert.equal((await dest.handoff.restoreBackup(preview.preview)).ok, true); assert.equal(dest.handoff.copy(saved.item.id).ok, true);
  dest.state.hash = 'a'.repeat(64); assert.equal(dest.handoff.copy(saved.item.id).ok, false);
  dest.state.hash = HASH; dest.state.restriction = 'Reported halt'; assert.equal(dest.handoff.copy(saved.item.id).ok, false);
  dest.state.restriction = null; dest.state.now = '2026-09-11T16:00:00Z'; assert.equal(dest.handoff.copy(saved.item.id).ok, false);
  assert.equal(dest.store.get(dest.handoff.KEY), raw);
});

test('empty supported envelopes retain exact raw distinction while absent export refuses', async () => {
  const absent = environment(); assert.equal(absent.handoff.exportBackup().ok, false); assert.equal(absent.state.writes, 0);
  for (const version of [1, 2, 3]) {
    const prior = '{ "version": ' + version + ', "items": [] }\n', env = environment({ store: new Map([['spicystock:handoff:v1', prior]]) });
    const backup = env.handoff.exportBackup(); assert.equal(backup.ok, true, backup.error); assert.equal(backup.raw, prior); assert.equal(backup.summary.count, 0);
    const incoming = '\n{"items":[],"version":1}\n', preview = env.handoff.previewBackup(incoming); assert.equal(preview.ok, true, preview.error); assert.equal(preview.preview.expectedRaw, prior);
    assert.equal((await env.handoff.restoreBackup(preview.preview)).ok, true); assert.equal(env.store.get(env.handoff.KEY), incoming); assert.equal(env.handoff.exportBackup().summary.version, 1);
  }
});

test('bad selected backups do not poison healthy destination records errors or recovery', () => {
  const env = environment({ store: new Map([['spicystock:handoff:v1', LEGACY_V2_RAW]]) }), before = plain(env.handoff.status()), recovery = plain(env.handoff.recovery());
  for (const raw of ['{', '\uFEFF' + LEGACY_RAW, '{"version":99,"items":[]}', JSON.stringify({ prior: LEGACY_RAW, proposed: LEGACY_V2_RAW }), '[]', null]) {
    const preview = env.handoff.previewBackup(raw); assert.equal(preview.ok, false); assert.match(preview.error, /not a supported private backup/);
    assert.deepEqual(plain(env.handoff.status()), before); assert.deepEqual(plain(env.handoff.recovery()), recovery); assert.equal(env.handoff.list().length, 1); assert.equal(env.state.writes, 0);
  }
});

test('backup rejects duplicate inconsistent mixed-version and unknown fields with no destination writes', () => {
  const env = environment();
  for (const change of [store => store.items.push(store.items[0]), store => { store.items[0].report.filled_quantity = 99; }, store => { store.items[0].version = 3; }, store => { store.items[0].report.entry_fees = '-1'; }, store => { store.items[0].new_field = true; }, store => { store.extra = 0; }]) {
    const data = JSON.parse(LEGACY_V2_RAW); change(data); assert.equal(env.handoff.previewBackup(JSON.stringify(data)).ok, false);
  }
  assert.equal(env.state.writes, 0); assert.equal(env.store.size, 0);
});

test('occupied unreadable or inaccessible destinations cannot be previewed or overwritten', async () => {
  for (const prior of [LEGACY_RAW, '{bad', '{"version":99,"items":[]}']) {
    const env = environment({ store: new Map([['spicystock:handoff:v1', prior]]) }), preview = env.handoff.previewBackup(LEGACY_RAW);
    assert.equal(preview.ok, false); assert.equal(env.store.get(env.handoff.KEY), prior); assert.equal(env.state.writes, 0);
    const forged = { raw: LEGACY_RAW, expectedRaw: prior, summary: environment({ store: new Map([['spicystock:handoff:v1', LEGACY_RAW]]) }).handoff.exportBackup().summary };
    assert.equal((await env.handoff.restoreBackup(forged)).ok, false); assert.equal(env.store.get(env.handoff.KEY), prior); assert.equal(env.state.writes, 0);
  }
  const inaccessible = environment({ readFails: true }); assert.equal(inaccessible.handoff.previewBackup(LEGACY_RAW).ok, false); assert.equal(inaccessible.handoff.exportBackup().ok, false); assert.equal(inaccessible.state.writes, 0);
});

test('restore compares exact empty destination bytes after lock wait including null versus empty envelope', async () => {
  for (const prior of [null, '{"version":1,"items":[]}']) {
    const env = environment({ store: new Map(prior === null ? [] : [['spicystock:handoff:v1', prior]]) }), preview = env.handoff.previewBackup(LEGACY_RAW); assert.equal(preview.ok, true, preview.error);
    let unlock; env.state.blockLock = new Promise(resolve => { unlock = resolve; }); const pending = env.handoff.restoreBackup(preview.preview);
    const changed = prior === null ? '{"version":1,"items":[]}' : prior + ' '; env.store.set(env.handoff.KEY, changed); unlock();
    const result = await pending; assert.equal(result.ok, false); assert.match(result.error, /changed since preview/); assert.equal(env.store.get(env.handoff.KEY), changed); assert.equal(env.state.writes, 0);
  }
});

test('the shared raw writer rechecks storage immediately before restore and never writes after a failed check', async () => {
  for (const mode of ['changed', 'unavailable']) {
    const env = environment(), preview = env.handoff.previewBackup(LEGACY_RAW); assert.equal(preview.ok, true);
    const changed = '{"version":2,"items":[]}'; let reads = 0;
    env.state.beforeGet = () => { if (++reads === 2) { if (mode === 'changed') env.store.set(env.handoff.KEY, changed); else env.state.readFails = true; } };
    const result = await env.handoff.restoreBackup(preview.preview); assert.equal(result.ok, false);
    assert.match(result.error, mode === 'changed' ? /changed in another view/ : /could not be checked/);
    assert.equal(env.state.writes, 0); assert.equal(env.store.get(env.handoff.KEY) ?? null, mode === 'changed' ? changed : null);
  }
});

test('a concurrent saved report wins over an earlier empty-destination preview', async () => {
  const env = environment(), preview = env.handoff.previewBackup(LEGACY_RAW); assert.equal(preview.ok, true);
  const created = await env.prepare(); assert.equal(created.ok, true, created.error); const saved = env.store.get(env.handoff.KEY), writes = env.state.writes;
  const result = await env.handoff.restoreBackup(preview.preview); assert.equal(result.ok, false); assert.equal(env.store.get(env.handoff.KEY), saved); assert.equal(env.state.writes, writes);
});

test('restore revalidates selected raw and displayed summary rather than trusting a mutable preview', async () => {
  for (const alter of [p => { p.raw = '{"version":99,"items":[]}'; }, p => { p.summary.count = 2; }, p => { p.extra = true; }, p => { delete p.expectedRaw; }]) {
    const env = environment(), preview = env.handoff.previewBackup(LEGACY_RAW); assert.equal(preview.ok, true); alter(preview.preview);
    assert.equal((await env.handoff.restoreBackup(preview.preview)).ok, false); assert.equal(env.state.writes, 0); assert.equal(env.store.size, 0);
  }
});

test('restore quota and readback failures preserve exact prior and proposed bytes for recovery', async () => {
  for (const mode of ['quota', 'readback']) for (const prior of [null, ' {"version":1,"items":[]}\n']) {
    const env = environment({ store: new Map(prior === null ? [] : [['spicystock:handoff:v1', prior]]) }), raw = '\n' + LEGACY_V2_RAW + ' ', preview = env.handoff.previewBackup(raw);
    assert.equal(preview.ok, true, preview.error); if (mode === 'quota') env.state.writeFails = true; else env.state.failNextReadback = true;
    const failed = await env.handoff.restoreBackup(preview.preview); assert.equal(failed.ok, false); assert.match(failed.error, /could not be confirmed/);
    assert.equal(env.store.get(env.handoff.KEY) ?? null, prior); assert.deepEqual(plain(env.handoff.recovery()), { prior, proposed: raw });
    env.state.writeFails = false; const saved = await env.handoff.restoreBackup(preview.preview); assert.equal(saved.ok, true, saved.error); assert.equal(env.store.get(env.handoff.KEY), raw); assert.equal(env.handoff.recovery().proposed, null);
  }
});

test('restore binds the exact issued bytes even when changed actual fees keep the same preview summary', async () => {
  const env = environment(), preview = env.handoff.previewBackup(LEGACY_V2_RAW); assert.equal(preview.ok, true);
  const changed = JSON.parse(LEGACY_V2_RAW); changed.items[0].report.entry_fees = '9.99'; const raw = JSON.stringify(changed);
  assert.notEqual(raw, LEGACY_V2_RAW); const other = env.handoff.previewBackup(raw); assert.equal(other.ok, true);
  assert.deepEqual(plain(other.preview.summary), plain(preview.preview.summary));
  let unlock; env.state.blockLock = new Promise(resolve => { unlock = resolve; }); const pending = env.handoff.restoreBackup(preview.preview);
  preview.preview.raw = raw; unlock(); const refused = await pending;
  assert.equal(refused.ok, false); assert.match(refused.error, /differs from its preview/); assert.equal(env.state.writes, 0); assert.equal(env.store.size, 0);
  preview.preview.raw = LEGACY_V2_RAW; assert.equal((await env.handoff.restoreBackup(preview.preview)).ok, true); assert.equal(env.store.get(env.handoff.KEY), LEGACY_V2_RAW);
});

test('restore refuses copied preview objects and changed expected destination while preserving issued previews', async () => {
  const env = environment(), preview = env.handoff.previewBackup(LEGACY_RAW); assert.equal(preview.ok, true);
  const copy = plain(preview.preview); assert.equal((await env.handoff.restoreBackup(copy)).ok, false); assert.equal(env.state.writes, 0);
  const changed = '{"version":1,"items":[]}'; env.store.set(env.handoff.KEY, changed); preview.preview.expectedRaw = changed;
  const refused = await env.handoff.restoreBackup(preview.preview); assert.equal(refused.ok, false); assert.match(refused.error, /differs from its preview/); assert.equal(env.state.writes, 0);
  env.store.delete(env.handoff.KEY); preview.preview.expectedRaw = null; assert.equal((await env.handoff.restoreBackup(preview.preview)).ok, true);
});

test('a successful empty backup restore consumes its confirmation but another explicit preview works', async () => {
  const raw = '{"version":1,"items":[]}', env = environment({ store: new Map([['spicystock:handoff:v1', raw]]) }), preview = env.handoff.previewBackup(raw);
  assert.equal((await env.handoff.restoreBackup(preview.preview)).ok, true); const writes = env.state.writes;
  assert.equal((await env.handoff.restoreBackup(preview.preview)).ok, false); assert.equal(env.state.writes, writes);
  const fresh = env.handoff.previewBackup(raw); assert.equal((await env.handoff.restoreBackup(fresh.preview)).ok, true);
});

test('normal export needs no saving permission but restore never bypasses the lock requirement', async () => {
  const source = environment({ noLocks: true, store: new Map([['spicystock:handoff:v1', LEGACY_RAW]]) }); assert.equal(source.handoff.exportBackup().ok, true); assert.equal(source.state.writes, 0);
  const dest = environment({ noLocks: true }), preview = dest.handoff.previewBackup(LEGACY_RAW); assert.equal(preview.ok, true); assert.equal((await dest.handoff.restoreBackup(preview.preview)).ok, false); assert.equal(dest.state.writes, 0);
});

test('backup UTF8 and record bounds are shared with storage and never truncate records', async () => {
  const env = environment(), max = env.handoff.MAX_BYTES;
  const data = JSON.parse(LEGACY_RAW); data.items[0].plan.exit_schedule[0].instruction = 'Price reference café 🐔';
  const prefix = JSON.stringify(data), exact = prefix + ' '.repeat(max - Buffer.byteLength(prefix)); assert.equal(Buffer.byteLength(exact), max);
  const preview = env.handoff.previewBackup(exact); assert.equal(preview.ok, true, preview.error); assert.equal(env.handoff.previewBackup(exact + ' ').ok, false);
  assert.equal((await env.handoff.restoreBackup(preview.preview)).ok, true); assert.equal(env.handoff.exportBackup().raw, exact);
  const item = JSON.parse(LEGACY_RAW).items[0], items = Array.from({ length: 100 }, (_, i) => { const copy = plain(item); copy.publication.sha256 = i.toString(16).padStart(64, '0'); copy.id = copy.publication.sha256 + ':' + copy.plan.reference.id; return copy; });
  const dest = environment(), valid = JSON.stringify({ version: 1, items }); assert.equal(dest.handoff.previewBackup(valid).ok, true);
  const extra = plain(items[0]); extra.publication.sha256 = 'f'.repeat(64); extra.id = extra.publication.sha256 + ':' + extra.plan.reference.id;
  assert.equal(dest.handoff.previewBackup(JSON.stringify({ version: 1, items: [...items, extra] })).ok, false); assert.equal(dest.state.writes, 0);
});

test('raw lone surrogate cannot silently change exported bytes while escaped JSON remains exact', async () => {
  const data = JSON.parse(LEGACY_RAW); data.items[0].plan.exit_schedule[0].instruction = '\uD800';
  const escaped = JSON.stringify(data), literal = escaped.replace('\\ud800', '\uD800'), env = environment(); assert.notEqual(literal, escaped);
  assert.equal(env.handoff.previewBackup(literal).ok, false);
  const invalidStore = environment({ store: new Map([['spicystock:handoff:v1', literal]]) }); assert.equal(invalidStore.handoff.exportBackup().ok, false); assert.equal(invalidStore.store.get(invalidStore.handoff.KEY), literal); assert.equal(invalidStore.state.writes, 0);
  const preview = env.handoff.previewBackup(escaped); assert.equal(preview.ok, true, preview.error); assert.equal((await env.handoff.restoreBackup(preview.preview)).ok, true); assert.equal(env.handoff.exportBackup().raw, escaped);
});

test('real producer draft keeps published four and personally reads back two without inferred execution', async () => {
  const env = environment(), original = JSON.stringify(env.api.data);
  const result = await env.prepare(); assert.equal(result.ok, true, result.error);
  const item = plain(result.item), summary = plain(env.handoff.summary(result.item));
  assert.equal(item.publication.sha256, HASH);
  assert.equal(item.plan.order.quantity, 4); assert.equal(item.plan.order.then.quantity, 4);
  assert.deepEqual(item.draft, { quantity: 2, cash_cents: 200000, fee_cents: 100 });
  assert.equal(summary.calculation.commitmentCents, 22444); assert.equal(summary.calculation.riskCents, 444);
  assert.equal(summary.reported_held_quantity, null); assert.equal(summary.unfilled_quantity, null); assert.equal(summary.protection, 'unknown');
  assert.ok(Object.values(item.report).every(value => value === null));
  const copy = env.handoff.copy(item.id); assert.equal(copy.ok, true);
  assert.match(copy.text, /BUY 2 COIL/); assert.match(copy.text, /protective SELL 2 COIL/); assert.match(copy.text, /Published quantity: 4/);
  assert.match(copy.text, /places no order or protective stop/);
  assert.equal(JSON.stringify(env.api.data), original); assert.equal(env.handoff.find(item.id).revision, 1);
  assert.equal(env.store.size, 1); assert.equal(env.store.has('spicystock:following:v1'), false);
});

test('one of two filled means one reported held, one unfilled, cancellation and protection still unknown', async () => {
  const env = environment(), { item } = await env.prepare();
  const result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1', exited_quantity: '0', average_price: '111.234500', filled_at: '2026-09-11T08:34:30-05:00' }), item.revision);
  assert.equal(result.ok, true, result.error);
  const summary = env.handoff.summary(result.item);
  assert.equal(summary.state, 'reported_partial_fill'); assert.equal(summary.reported_held_quantity, 1); assert.equal(summary.unfilled_quantity, 1);
  assert.equal(summary.uncancelled_quantity, null); assert.equal(summary.protection, 'unknown');
  assert.equal(result.item.report.average_price, '111.2345'); assert.equal(result.item.report.filled_at, '2026-09-11T13:34:30.000Z');
  assert.equal(env.handoff.copy(item.id).ok, false); // readback is retained, never a second entry instruction
  assert.match(env.handoff.readback(result.item), /BUY 2 COIL/);
});

test('explicit zero fills differ from unknown, with no implied price or broker protection', async () => {
  const env = environment(), { item } = await env.prepare();
  const result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '0', exited_quantity: '0', cancelled_quantity: '0' }), 1);
  assert.equal(result.ok, true, result.error);
  const summary = env.handoff.summary(result.item);
  assert.equal(summary.reported_held_quantity, 0); assert.equal(summary.unfilled_quantity, 2); assert.equal(summary.uncancelled_quantity, 2);
  assert.equal(result.item.report.average_price, null); assert.equal(summary.protection, 'unknown');
});

test('unknown exits never mean still held; explicit exits reconcile holdings and stale protection after expiry', async () => {
  const env = environment(), { item } = await env.prepare();
  let result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1', protected_quantity: '1' }), 1);
  assert.equal(result.ok, true, result.error);
  let summary = env.handoff.summary(result.item);
  assert.equal(summary.filled_quantity, 1); assert.equal(summary.exited_quantity, null); assert.equal(summary.reported_held_quantity, null); assert.equal(summary.protection, 'unknown');
  env.state.now = '2026-09-11T16:00:00Z'; env.state.restriction = 'Known halt';
  result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1', filled_at: NOW, cancelled_quantity: '1', exited_quantity: '1', exited_at: '2026-09-11T15:00:00Z', protected_quantity: '1' }), result.item.revision);
  assert.equal(result.ok, true, result.error);
  summary = env.handoff.summary(result.item);
  assert.equal(summary.filled_quantity, 1); assert.equal(summary.exited_quantity, 1); assert.equal(summary.reported_held_quantity, 0); assert.equal(summary.state, 'reported_closed');
  assert.equal(summary.protection, 'over'); assert.match(summary.warnings.join(' '), /remaining holdings/);
  result = await env.handoff.report(item.id, { ...result.item.report, protected_quantity: '0', protection_confirmed_at: env.state.now }, result.item.revision);
  assert.equal(result.ok, true, result.error); assert.equal(env.handoff.summary(result.item).protection, 'matched');
  assert.equal(result.item.plan.order.quantity, 4); assert.equal(env.handoff.copy(item.id).ok, false);
});

test('exit conservation and chronology reject impossible reports without confusing partial-entry timing', async () => {
  const env = environment(), { item } = await env.prepare();
  const base = { submitted_quantity: '2', submitted_at: '2026-09-11T13:30:00Z', filled_quantity: '2', filled_at: '2026-09-11T13:34:00Z' };
  for (const patch of [
    { exited_quantity: '3' }, { filled_quantity: '', filled_at: '', exited_quantity: '1' },
    { exited_quantity: '0', exited_at: NOW }, { exited_quantity: '1', exited_at: '2026-09-11T13:29:00Z' },
    { exited_quantity: '2', exited_at: '2026-09-11T13:33:00Z' }, { exited_quantity: '1', exited_at: '2026-09-11T13:35:06Z' }
  ]) assert.equal((await env.handoff.report(item.id, reportFields({ ...base, ...patch }), 1)).ok, false, JSON.stringify(patch));
  // One earlier fill may have exited before the latest partial entry filled.
  const result = await env.handoff.report(item.id, reportFields({ ...base, exited_quantity: '1', exited_at: '2026-09-11T13:33:00Z' }), 1);
  assert.equal(result.ok, true, result.error); assert.equal(env.handoff.summary(result.item).reported_held_quantity, 1);
});

test('protective mismatch is a retained fact, including overprotection, and corrections reconcile it', async () => {
  const env = environment(), { item } = await env.prepare();
  let latest = item;
  for (const [quantity, expected] of [['0', 'under'], ['2', 'over'], ['1', 'matched']]) {
    const result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1', exited_quantity: '0', protected_quantity: quantity, protection_confirmed_at: NOW }), latest.revision);
    assert.equal(result.ok, true, result.error); latest = result.item;
    assert.equal(latest.report.protected_quantity, Number(quantity));
    const summary = env.handoff.summary(latest); assert.equal(summary.protection, expected);
    assert.equal(summary.warnings.some(value => /protective quantity/.test(value)), expected !== 'matched');
  }
  assert.equal(latest.revision, 4); assert.equal(latest.plan.order.quantity, 4);
});

test('reported quantities, prices and times outside the plan remain factual deviations after expiry', async () => {
  const env = environment(), { item } = await env.prepare();
  env.state.now = '2026-09-11T15:00:00.000Z'; env.state.restriction = 'Source-backed halt'; env.state.hash = 'c'.repeat(64);
  const result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '5', submitted_at: '2026-09-11T14:00:00Z', filled_quantity: '3', exited_quantity: '0', average_price: '115', filled_at: '2026-09-11T14:01:00Z' }), 1);
  assert.equal(result.ok, true, result.error);
  const summary = env.handoff.summary(result.item);
  assert.equal(summary.reported_held_quantity, 3); assert.equal(summary.unfilled_quantity, 2); assert.equal(summary.warnings.length, 3);
  assert.equal(env.handoff.copy(item.id).ok, false);
  const reread = environment({ store: env.store, now: env.state.now });
  assert.equal(reread.handoff.find(item.id).report.filled_quantity, 3);
  assert.equal(reread.handoff.find(item.id).plan.order.quantity, 4);
});

test('cumulative fill and cancellation conservation rejects impossible totals without overwriting', async () => {
  const env = environment(), { item } = await env.prepare();
  const before = env.store.get(env.handoff.KEY);
  for (const [submitted, filled, cancelled] of [['2', '3', ''], ['2', '1', '2'], ['2', '', '3'], ['', '1', ''], ['', '', '1']]) {
    const result = await env.handoff.report(item.id, reportFields({ submitted_quantity: submitted, filled_quantity: filled, cancelled_quantity: cancelled }), 1);
    assert.equal(result.ok, false, [submitted, filled, cancelled].join('/')); assert.equal(env.store.get(env.handoff.KEY), before);
  }
  const result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1', exited_quantity: '0', cancelled_quantity: '1', cancelled_at: NOW }), 1);
  assert.equal(result.ok, true, result.error); assert.equal(env.handoff.summary(result.item).uncancelled_quantity, 0);
  assert.equal(env.handoff.summary(result.item).reported_held_quantity, 1);
});

test('numeric and clock errors reject only malformed reports, preserving positive out-of-plan facts', async () => {
  const env = environment(), { item } = await env.prepare();
  const base = { submitted_quantity: '2', submitted_at: '2026-09-11T13:33:00Z', filled_quantity: '1', average_price: '111.2', filled_at: '2026-09-11T13:34:00Z' };
  for (const patch of [
    { filled_quantity: '1.5' }, { filled_quantity: '-1' }, { submitted_quantity: '1000001' }, { average_price: '0' }, { average_price: 'NaN' }, { average_price: '1e2' }, { average_price: '111.1234567' },
    { filled_at: '2026-09-11T13:34:00' }, { filled_at: '2026-02-30T13:34:00Z' }, { filled_at: '2026-09-11T25:00:00Z' }, { filled_at: '2026-09-11T13:35:06Z' },
    { filled_at: '2026-09-11T13:32:59Z' }, { cancelled_quantity: '1', cancelled_at: '2026-09-11T13:33:59Z' }, { filled_quantity: '0' }, { submitted_quantity: '0', filled_quantity: '', average_price: '', filled_at: '' }
  ]) {
    const result = await env.handoff.report(item.id, reportFields({ ...base, ...patch }), 1);
    assert.equal(result.ok, false, JSON.stringify(patch)); assert.equal(env.handoff.find(item.id).revision, 1);
  }
  const valid = await env.handoff.report(item.id, reportFields({ ...base, average_price: '99.000001' }), 1);
  assert.equal(valid.ok, true, valid.error); assert.equal(valid.item.report.average_price, '99.000001');
});

test('draft cap, cash and explicit fees remain separate from manually reported actual quantities', async () => {
  for (const patch of [{ quantity: '5' }, { cash: '224.43' }, { fees: '' }, { cash: '' }, { quantity: '0' }, { quantity: '1.2' }]) {
    const env = environment(), result = await env.prepare(patch); assert.equal(result.ok, false, JSON.stringify(patch)); assert.equal(env.store.size, 0);
  }
  const env = environment(), result = await env.prepare({ cash: '224.44' });
  assert.equal(result.ok, true, result.error); assert.equal(env.handoff.summary(result.item).calculation.remainingCents, 0);
});

test('new preparation and detached copy recheck expiry, events, exact publication and plan identity', async () => {
  const controls = [
    ['expiry', env => { env.state.now = '2026-09-11T14:00:00Z'; }],
    ['halt', env => { env.state.restriction = 'Known active halt'; }],
    ['corporate', env => { env.state.restriction = 'Known merger exclusion'; }],
    ['binding pending', env => { env.state.hash = null; }],
    ['new publication', env => { env.state.hash = 'b'.repeat(64); }],
    ['withheld', env => { env.api.model.stages['setting-up'][0].status = 'withheld'; }],
    ['account mismatch', env => { env.api.data.account.equity = 10000; }],
    ['practice', env => { env.api.data.fixture = { label: 'explicit refusal control' }; }],
    ['order mismatch', env => { env.api.model.stages['setting-up'][0].plan.order_json.then.quantity = 3; }],
    ['level mismatch', env => { env.api.model.stages['setting-up'][0].plan.stop += .01; }],
    ['reference mismatch', env => { env.api.model.stages['setting-up'][0].plan.evidence_ref.plan_sha256 = 'c'.repeat(64); }]
  ];
  for (const [label, change] of controls) {
    const env = environment(), { item } = await env.prepare(); change(env);
    assert.equal(env.handoff.copy(item.id).ok, false, label + ' copy');
    const result = await env.prepare({ expectedRevision: 1 });
    // A different valid reference still creates a different-source draft only
    // if explicitly reviewed; an existing identity must never silently change.
    assert.equal(result.ok, false, label + ' preparation');
    assert.equal(env.handoff.find(item.id).draft.quantity, 2); assert.equal(env.handoff.find(item.id).plan.order.quantity, 4);
  }
});

test('guard is evaluated after waiting for the storage lock', async () => {
  let unlock; const waiting = new Promise(resolve => { unlock = resolve; });
  const env = environment({ blockLock: waiting });
  const pending = env.prepare(); env.state.now = '2026-09-11T14:00:00Z'; unlock();
  assert.equal((await pending).ok, false); assert.equal(env.store.size, 0);
});

test('optimistic revisions reject stale corrections and removed records without resurrection', async () => {
  const env = environment(), { item } = await env.prepare();
  const results = await Promise.all([
    env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1' }), 1),
    env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '2' }), 1)
  ]);
  assert.deepEqual(results.map(result => result.ok), [true, false]);
  assert.equal(env.handoff.find(item.id).report.filled_quantity, 1);
  assert.equal((await env.prepare({ expectedRevision: 2 })).ok, false);
  assert.equal((await env.handoff.remove(item.id, 1)).ok, false);
  assert.equal((await env.handoff.remove(item.id, 2)).ok, true);
  assert.equal((await env.handoff.report(item.id, reportFields(), 2)).ok, false);
  assert.equal(env.handoff.list().length, 0);
});

test('an explicit correction replaces cumulative totals and never adds a second fill', async () => {
  const env = environment(), { item } = await env.prepare();
  let result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '2', average_price: '111' }), 1);
  result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1', exited_quantity: '0', average_price: '110.8', cancelled_quantity: '1' }), result.item.revision);
  assert.equal(result.ok, true, result.error); assert.equal(env.handoff.summary(result.item).reported_held_quantity, 1); assert.equal(result.item.report.average_price, '110.8');
  result = await env.handoff.report(item.id, reportFields(), result.item.revision);
  assert.equal(result.ok, true, result.error); assert.equal(env.handoff.summary(result.item).reported_held_quantity, null);
  assert.equal(env.handoff.summary(result.item).state, 'reported_unknown_fill');
  assert.equal(env.handoff.copy(item.id).ok, false);
  assert.equal((await env.prepare({ expectedRevision: result.item.revision })).ok, false);
  assert.ok(result.item.report_updated_at); assert.equal(result.item.plan.order.quantity, 4);
});

test('malformed or future stores remain untouched rather than losing reported holdings', async () => {
  const source = environment(), { item } = await source.prepare();
  await source.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1' }), 1);
  const valid = source.store.get(source.handoff.KEY);
  for (const alter of [() => '{', value => { value.version = 99; return JSON.stringify(value); }, value => { value.items[0].report.filled_quantity = 3; return JSON.stringify(value); }, value => { value.items.push(value.items[0]); return JSON.stringify(value); }, value => { value.items[0].plan.order.quantity = 1; return JSON.stringify(value); }]) {
    const raw = alter(JSON.parse(valid)), env = environment({ store: new Map([[source.handoff.KEY, raw]]) });
    assert.equal(env.handoff.status().available, false); assert.match(env.handoff.status().error, /left untouched/);
    assert.equal((await env.prepare()).ok, false); assert.equal(env.store.get(env.handoff.KEY), raw);
    assert.equal(env.handoff.recovery().prior, raw);
  }
});

test('write failures retain confirmed state and proposed recovery without claiming success', async () => {
  const env = environment(), { item } = await env.prepare(), before = env.store.get(env.handoff.KEY);
  env.state.writeFails = true;
  const result = await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1' }), 1);
  assert.equal(result.ok, false); assert.equal(env.store.get(env.handoff.KEY), before);
  assert.equal(env.handoff.find(item.id).report.filled_quantity, null);
  assert.equal(JSON.parse(env.handoff.recovery().proposed).items[0].report.filled_quantity, 1);
  env.state.writeFails = false;
  assert.equal((await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1' }), 1)).ok, true);
  assert.equal(env.handoff.recovery().proposed, null);
});

test('unavailable locks and storage fail readably; a normal reload preserves manual facts', async () => {
  const noLocks = environment({ noLocks: true }); assert.equal((await noLocks.prepare()).ok, false);
  const blocked = environment({ readFails: true }); assert.equal((await blocked.prepare()).ok, false); assert.equal(blocked.handoff.status().available, false);
  const env = environment(), { item } = await env.prepare();
  await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1' }), 1);
  const reload = environment({ store: env.store, noLocks: true });
  assert.equal(reload.handoff.find(item.id).report.filled_quantity, 1); assert.equal(reload.handoff.status().available, false);
});

test('explicit deletion alone removes reported records; notifications include cross-tab clears', async () => {
  const env = environment(); let changes = 0; env.handoff.onChange(() => { changes += 1; });
  const { item } = await env.prepare(); await env.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1' }), 1);
  assert.equal(changes, 2); env.events.get('storage')({ key: null }); assert.equal(changes, 3);
  assert.equal((await env.handoff.remove(item.id, 2)).ok, true); assert.equal(changes, 4); assert.equal(env.handoff.list().length, 0);
});

test('bounded private history refuses a new draft without silently evicting reported positions', async () => {
  const source = environment(), { item } = await source.prepare();
  const result = await source.handoff.report(item.id, reportFields({ submitted_quantity: '2', filled_quantity: '1', exited_quantity: '0' }), 1);
  // Explicit synthetic local-store controls, not new production publications.
  const items = Array.from({ length: source.handoff.MAX_ITEMS }, (_, index) => {
    const saved = plain(result.item); saved.publication.sha256 = index.toString(16).padStart(64, '0'); saved.id = saved.publication.sha256 + ':' + saved.plan.reference.id; return saved;
  });
  const raw = JSON.stringify({ version: source.handoff.VERSION, items }), env = environment({ store: new Map([[source.handoff.KEY, raw]]) });
  assert.equal(env.handoff.status().count, 100);
  const refused = await env.prepare(); assert.equal(refused.ok, false); assert.match(refused.error, /nothing was evicted/);
  assert.equal(env.store.get(env.handoff.KEY), raw); assert.equal(env.handoff.list().every(saved => env.handoff.summary(saved).reported_held_quantity === 1), true);
});

const completedFields = patch => reportFields({ submitted_quantity: '2', filled_quantity: '2', average_price: '111.23', filled_at: '2026-09-11T13:34:00Z',
  cancelled_quantity: '0', exited_quantity: '2', exited_at: NOW, average_exit_price: '115', entry_fees: '0.05', exit_fees: '0.07', ...patch });

test('completed reported result uses actual quantities and fees, preserving the original draft buffer', async () => {
  const cases = [
    [{}, ['$7.54', '$0.12', '$7.42', 'gain', '7420000']],
    [{ filled_quantity: '1', exited_quantity: '1', cancelled_quantity: '1' }, ['$3.77', '$0.12', '$3.65', 'gain', '3650000']],
    [{ average_exit_price: '109.50' }, ['-$3.46', '$0.12', '-$3.58', 'loss', '-3580000']],
    // Two actual partial entry fills averaged 111.25; two exits averaged114.50.
    [{ average_price: '111.25', average_exit_price: '114.5', entry_fees: '0.06', exit_fees: '0.08' }, ['$6.50', '$0.14', '$6.36', 'gain', '6360000']]
  ];
  for (const [patch, expected] of cases) {
    const env = environment(), before = JSON.stringify(env.api.data), { item } = await env.prepare();
    const saved = await env.handoff.report(item.id, completedFields(patch), 1);
    assert.equal(saved.ok, true, saved.error);
    const result = env.handoff.summary(saved.item).completed_result;
    assert.equal(result.state, 'complete'); assert.deepEqual(plain(result.reasons), []);
    assert.deepEqual([result.gross_display, result.fees_display, result.net_display, result.outcome, result.net_microusd], expected);
    assert.equal(saved.item.draft.fee_cents, 100); assert.equal(saved.item.plan.order.quantity, 4); assert.equal(saved.item.draft.quantity, 2);
    assert.equal(JSON.stringify(env.api.data), before); assert.equal(env.handoff.copy(item.id).ok, false);
  }
});

test('every missing result input remains unknown and exposes no numerical result', async () => {
  for (const field of ['filled_quantity', 'exited_quantity', 'submitted_quantity', 'cancelled_quantity', 'average_price', 'average_exit_price', 'entry_fees', 'exit_fees', 'filled_at', 'exited_at']) {
    const env = environment(), { item } = await env.prepare(), input = completedFields({ [field]: '' });
    // Remove dependent facts only when the existing report schema requires it.
    // The particular missing field must still be identified in result.missing.
    if (field === 'submitted_quantity' || field === 'filled_quantity') Object.assign(input, { filled_quantity: '', average_price: '', filled_at: '', cancelled_quantity: '', exited_quantity: '', exited_at: '', average_exit_price: '' });
    if (field === 'exited_quantity') Object.assign(input, { exited_at: '', average_exit_price: '' });
    const saved = await env.handoff.report(item.id, input, 1); assert.equal(saved.ok, true, field + ': ' + saved.error);
    const result = env.handoff.summary(saved.item).completed_result;
    assert.equal(result.state, 'incomplete', field); assert.ok(result.missing.includes(field), field);
    assert.ok(['gross_microusd', 'fees_microusd', 'net_microusd', 'gross_display', 'fees_display', 'net_display', 'outcome'].every(key => result[key] === null), field);
  }
});

test('partial exits and unreconciled entry remainders never invent a completed cost basis', async () => {
  for (const patch of [
    { exited_quantity: '1' }, { filled_quantity: '1', exited_quantity: '1', cancelled_quantity: '0' },
    { filled_quantity: '0', exited_quantity: '0', cancelled_quantity: '2', average_price: '', filled_at: '', average_exit_price: '', exited_at: '' }
  ]) {
    const env = environment(), { item } = await env.prepare();
    const saved = await env.handoff.report(item.id, completedFields(patch), 1); assert.equal(saved.ok, true, saved.error);
    const result = env.handoff.summary(saved.item).completed_result; assert.equal(result.state, 'incomplete'); assert.equal(result.net_microusd, null);
  }
  // buy1@100 -> sell1@110 -> buy1@120: latest avg entry110 cannot establish
  // the first sale's gross10. The aggregate report must not invent gross0.
  const env = environment(), { item } = await env.prepare();
  const saved = await env.handoff.report(item.id, completedFields({ average_price: '110', average_exit_price: '110', exited_quantity: '1' }), 1);
  assert.equal(saved.ok, true, saved.error);
  const result = env.handoff.summary(saved.item).completed_result;
  assert.equal(result.gross_display, null); assert.match(result.reasons.join(' '), /cost basis/);
});

test('explicit zero costs and exact sign survive cent rounding without false breakeven', async () => {
  const controls = [
    [{ average_exit_price: '111.23', entry_fees: '0', exit_fees: '0' }, ['0', '$0.00', 'breakeven']],
    [{ average_exit_price: '111.2325', entry_fees: '0', exit_fees: '0' }, ['5000', '$0.01', 'gain']],
    [{ average_exit_price: '111.2275', entry_fees: '0', exit_fees: '0' }, ['-5000', '-$0.01', 'loss']],
    // Rounding gross first would incorrectly turn .005-.01 into zero.
    [{ average_exit_price: '111.2325', entry_fees: '0.01', exit_fees: '0' }, ['-5000', '-$0.01', 'loss']],
    [{ filled_quantity: '1', exited_quantity: '1', cancelled_quantity: '1', average_exit_price: '111.230001', entry_fees: '0', exit_fees: '0' }, ['1', '<$0.01', 'gain']],
    [{ filled_quantity: '1', exited_quantity: '1', cancelled_quantity: '1', average_exit_price: '111.229999', entry_fees: '0', exit_fees: '0' }, ['-1', '-<$0.01', 'loss']]
  ];
  for (const [patch, expected] of controls) {
    const env = environment(), { item } = await env.prepare();
    const saved = await env.handoff.report(item.id, completedFields(patch), 1); assert.equal(saved.ok, true, saved.error);
    assert.equal(saved.item.report.exit_fees, '0.00');
    const result = env.handoff.summary(saved.item).completed_result;
    assert.deepEqual([result.net_microusd, result.net_display, result.outcome], expected);
  }
});

test('result arithmetic stays exact beyond safe floating-point integers', async () => {
  const env = environment(), { item } = await env.prepare();
  const saved = await env.handoff.report(item.id, completedFields({ submitted_quantity: '1000000', filled_quantity: '1000000', exited_quantity: '1000000', average_price: '0.000001', average_exit_price: '9999999999.999999', entry_fees: '0.01', exit_fees: '0.02' }), 1);
  assert.equal(saved.ok, true, saved.error);
  const result = env.handoff.summary(saved.item).completed_result;
  assert.equal(result.gross_microusd, '9999999999999998000000');
  assert.equal(result.net_microusd, '9999999999999997970000');
  assert.equal(result.net_display, '$9,999,999,999,999,997.97');
});

test('result fields reject impossible prices and non-cent costs without changing saved facts', async () => {
  const env = environment(), { item } = await env.prepare(), before = env.store.get(env.handoff.KEY);
  for (const patch of [{ average_exit_price: '0' }, { average_exit_price: '-1' }, { average_exit_price: '111.1234567' }, { average_exit_price: '1e3' },
    { entry_fees: '-0.01' }, { entry_fees: '0.001' }, { exit_fees: '90071992547409.92' }, { exit_fees: 0 }, { exited_quantity: '0', exited_at: '' }]) {
    const saved = await env.handoff.report(item.id, completedFields(patch), 1); assert.equal(saved.ok, false, JSON.stringify(patch));
    assert.equal(env.store.get(env.handoff.KEY), before);
  }
});

test('corrections recompute results after expiry and events without restoring entry authority', async () => {
  const env = environment(), { item } = await env.prepare();
  let saved = await env.handoff.report(item.id, completedFields(), 1); assert.equal(saved.ok, true, saved.error);
  env.state.now = '2026-09-12T13:35:00Z'; env.state.restriction = 'Known event exclusion'; env.state.hash = 'b'.repeat(64);
  saved = await env.handoff.report(item.id, { ...saved.item.report, average_exit_price: '109.5' }, saved.item.revision);
  assert.equal(saved.ok, true, saved.error); assert.equal(env.handoff.summary(saved.item).completed_result.net_display, '-$3.58');
  const revision = saved.item.revision;
  assert.equal((await env.handoff.report(item.id, completedFields(), revision - 1)).ok, false);
  saved = await env.handoff.report(item.id, { ...saved.item.report, exit_fees: '' }, revision);
  assert.equal(saved.ok, true, saved.error); assert.equal(env.handoff.summary(saved.item).completed_result.state, 'incomplete');
  assert.equal(env.handoff.summary(saved.item).completed_result.net_display, null); assert.equal(env.handoff.copy(item.id).ok, false);
  const reloaded = environment({ store: env.store }); assert.equal(reloaded.handoff.find(item.id).report.exit_fees, null);
});

test('a genuine v1 record reads as unknown new fields without a single storage write', async () => {
  const original = JSON.parse(LEGACY_RAW), old = original.items[0], env = environment({ store: new Map([['spicystock:handoff:v1', LEGACY_RAW]]) });
  assert.equal(env.handoff.status().available, true);
  const item = env.handoff.list()[0]; assert.equal(item.version, 3); assert.equal(item.kind, 'planned_handoff');
  const expected = { ...old, version: 3, kind: 'planned_handoff', report: { ...old.report, average_exit_price: null, entry_fees: null, exit_fees: null } };
  assert.deepEqual(plain(item), expected); assert.equal(env.handoff.find(item.id).revision, old.revision);
  assert.equal(env.handoff.summary(item).completed_result.state, 'incomplete'); assert.equal(env.handoff.summary(item).completed_result.net_display, null);
  assert.equal(env.handoff.copy(item.id).ok, false); assert.equal(env.store.get(env.handoff.KEY), LEGACY_RAW); assert.equal(env.state.writes, 0);
  assert.equal(env.handoff.recovery().prior, LEGACY_RAW);
});

test('an explicit valid save upgrades v1 once while preserving original semantics and timestamps', async () => {
  const old = JSON.parse(LEGACY_RAW).items[0], env = environment({ store: new Map([['spicystock:handoff:v1', LEGACY_RAW]]) });
  const item = env.handoff.list()[0];
  const bad = await env.handoff.report(item.id, { ...item.report, average_exit_price: 'bad' }, item.revision);
  assert.equal(bad.ok, false); assert.equal(env.store.get(env.handoff.KEY), LEGACY_RAW); assert.equal(env.state.writes, 0);
  const saved = await env.handoff.report(item.id, { ...item.report, average_exit_price: '115', entry_fees: '0.05', exit_fees: '0.07' }, item.revision);
  assert.equal(saved.ok, true, saved.error); assert.equal(env.state.writes, 1);
  const raw = env.store.get(env.handoff.KEY), store = JSON.parse(raw); assert.equal(store.version, 3); assert.equal(store.items[0].version, 3);
  assert.equal(saved.item.revision, old.revision + 1); assert.equal(saved.item.created_at, old.created_at);
  for (const key of ['id', 'publication', 'plan', 'draft']) assert.deepEqual(plain(saved.item[key]), old[key]);
  for (const key of Object.keys(old.report)) assert.deepEqual(saved.item.report[key], old.report[key], key);
  assert.equal(env.handoff.summary(saved.item).completed_result.net_display, '$3.65');
  env.handoff.list(); env.handoff.status(); assert.equal(env.store.get(env.handoff.KEY), raw); assert.equal(env.state.writes, 1);
});

test('failed v1 upgrades retain exact old bytes plus proposed v3 recovery and reject stale retries', async () => {
  const env = environment({ store: new Map([['spicystock:handoff:v1', LEGACY_RAW]]) }), item = env.handoff.list()[0]; env.state.writeFails = true;
  const fields = { ...item.report, average_exit_price: '115', entry_fees: '0', exit_fees: '0' };
  assert.equal((await env.handoff.report(item.id, fields, item.revision)).ok, false);
  assert.equal(env.store.get(env.handoff.KEY), LEGACY_RAW); assert.equal(env.handoff.recovery().prior, LEGACY_RAW);
  const proposed = JSON.parse(env.handoff.recovery().proposed); assert.equal(proposed.version, 3); assert.equal(proposed.items[0].report.entry_fees, '0.00');
  assert.equal(env.handoff.find(item.id).report.entry_fees, null);
  env.state.writeFails = false;
  const saved = await env.handoff.report(item.id, fields, item.revision); assert.equal(saved.ok, true, saved.error);
  assert.equal((await env.handoff.report(item.id, { ...fields, exit_fees: '1' }, item.revision)).ok, false);
  assert.equal(env.handoff.find(item.id).report.exit_fees, '0.00');
});

test('legacy unknown fields and mixed or future versions remain untouched and recoverable', async () => {
  for (const alter of [value => { value.items[0].report.unrecognized = null; }, value => { value.items[0].unexpected = 1; },
    value => { value.items[0].report.entry_fees = '0.00'; }, value => { value.version = 2; }, value => { value.version = 3; }]) {
    const value = JSON.parse(LEGACY_RAW); alter(value); const raw = JSON.stringify(value), env = environment({ store: new Map([['spicystock:handoff:v1', raw]]) });
    assert.equal(env.handoff.status().available, false); assert.equal((await env.prepare()).ok, false);
    assert.equal(env.store.get(env.handoff.KEY), raw); assert.equal(env.state.writes, 0); assert.equal(env.handoff.recovery().prior, raw);
  }
});

test('legacy expansion cannot write past the byte cap or evict another reported position', async () => {
  const source = JSON.parse(LEGACY_RAW).items[0], items = Array.from({ length: 30 }, (_, index) => {
    // Explicit synthetic private-store capacity controls, not public records.
    const item = plain(source); item.publication.sha256 = index.toString(16).padStart(64, '0'); item.id = item.publication.sha256 + ':' + item.plan.reference.id;
    item.plan.exit_schedule = Array.from({ length: 20 }, () => ({ ...item.plan.exit_schedule[0], instruction: 'x' })); return item;
  });
  const cap = environment().handoff.MAX_BYTES, serialize = () => JSON.stringify({ version: 1, items });
  let needed = cap - 8 - Buffer.byteLength(serialize());
  for (const item of items) for (const row of item.plan.exit_schedule) { const add = Math.min(1999, needed); row.instruction += 'x'.repeat(add); needed -= add; }
  assert.equal(needed, 0); const raw = serialize(); assert.equal(Buffer.byteLength(raw), cap - 8);
  const env = environment({ store: new Map([['spicystock:handoff:v1', raw]]) }); assert.equal(env.handoff.status().count, 30); assert.equal(env.state.writes, 0);
  const item = env.handoff.list()[0], saved = await env.handoff.report(item.id, { ...item.report, average_exit_price: '115', entry_fees: '0', exit_fees: '0' }, item.revision);
  assert.equal(saved.ok, false); assert.match(saved.error, /storage is full/);
  assert.equal(env.store.get(env.handoff.KEY), raw); assert.equal(env.state.writes, 0); assert.equal(env.handoff.status().count, 30);
});

test('whole-share exit reference uses personal draft and existing round-up convention without revising the model', async () => {
  for (const [quantity, half, left] of [[1, 1, 0], [2, 1, 1], [3, 2, 1], [4, 2, 2]]) {
    const env = environment(), before = JSON.stringify(env.api.data);
    const result = await env.prepare({ quantity: String(quantity), fees: '0' });
    assert.equal(result.ok, true, result.error);
    const stored = env.store.get(env.handoff.KEY), writes = env.state.writes;
    const review = plain(env.handoff.summary(result.item).exit_review);
    assert.equal(review.basis, 'personal_draft'); assert.equal(review.quantity, quantity);
    assert.equal(review.model_half_quantity, half); assert.equal(review.model_remaining_quantity, left);
    assert.equal(review.needs_review, quantity % 2 !== 0);
    assert.match(review.message, /reference arithmetic/i);
    if (quantity === 1) assert.match(review.message, /one-share position cannot be partly exited/i);
    if (quantity === 3) assert.match(review.message, /rounds up to 2 whole shares/);
    assert.match(env.handoff.readback(result.item), /Whole-share exit reference/);
    assert.equal(result.item.plan.order.quantity, 4);
    assert.equal(JSON.stringify(env.api.data), before); assert.equal(env.store.get(env.handoff.KEY), stored); assert.equal(env.state.writes, writes);
  }
});

test('whole-share exit reference uses reported remaining holdings and never assumes an unknown fill or exit', async () => {
  const env = environment(), { item } = await env.prepare({ quantity: '3' });
  for (const [fields, basis, quantity, half, left] of [
    [{ submitted_quantity: '3' }, 'reported_unknown', null, null, null],
    [{ submitted_quantity: '3', filled_quantity: '3' }, 'reported_unknown', null, null, null],
    [{ submitted_quantity: '3', filled_quantity: '3', exited_quantity: '0' }, 'reported_remaining', 3, 2, 1],
    [{ submitted_quantity: '3', filled_quantity: '3', exited_quantity: '1' }, 'reported_remaining', 2, 1, 1],
    [{ submitted_quantity: '3', filled_quantity: '3', exited_quantity: '2' }, 'reported_remaining', 1, 1, 0],
    [{ submitted_quantity: '3', filled_quantity: '3', exited_quantity: '3' }, 'reported_remaining', 0, null, null]
  ]) {
    const current = env.handoff.find(item.id);
    const result = await env.handoff.report(item.id, reportFields(fields), current.revision);
    assert.equal(result.ok, true, result.error);
    const review = plain(env.handoff.summary(result.item).exit_review);
    assert.equal(review.basis, basis); assert.equal(review.quantity, quantity);
    assert.equal(review.model_half_quantity, half); assert.equal(review.model_remaining_quantity, left);
    if (quantity === null) assert.match(review.message, /holdings are unknown/i);
    else if (quantity === 0) assert.match(review.message, /reported no remaining shares/i);
    else assert.match(review.message, /does not determine whether another exit is due/i);
    assert.equal(env.handoff.find(item.id).draft.quantity, 3);
  }
});

test('whole-share exit reference reads legacy storage without migration or extra writes', () => {
  const store = new Map([['spicystock:handoff:v1', LEGACY_RAW]]), env = environment({ store });
  const item = env.handoff.list()[0], review = env.handoff.summary(item).exit_review;
  assert.equal(review.basis, 'reported_remaining'); assert.equal(review.quantity, 0);
  assert.equal(review.model_half_quantity, null); assert.equal(review.model_remaining_quantity, null);
  assert.equal(store.get(env.handoff.KEY), LEGACY_RAW); assert.equal(env.state.writes, 0);
});
