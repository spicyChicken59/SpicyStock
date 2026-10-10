/* Private broker readback and manually reported cumulative entry facts. Nothing
   in this store submits an order, reserves cash, observes fills or edits a
   published plan. New preparation/copy uses current page guards; correcting
   reported facts deliberately does not require a still-open entry window. */
(function (w) {
  'use strict';
  const api = w.SCStock = w.SCStock || {};
  const VERSION = 3, KEY = 'spicystock:handoff:v1', MAX_ITEMS = 100, MAX_BYTES = 1048576, MAX_SHARES = 1000000;
  const HEX = /^[a-f0-9]{64}$/, DATE = /^\d{4}-\d{2}-\d{2}$/;
  const REF = ['id', 'context_sha256', 'plan_sha256', 'pick_sha256'];
  const LEGACY_FIELDS = ['submitted_quantity', 'submitted_at', 'filled_quantity', 'average_price', 'filled_at', 'cancelled_quantity', 'cancelled_at', 'exited_quantity', 'exited_at', 'protected_quantity', 'protection_confirmed_at'];
  const RESULT_FIELDS = ['average_exit_price', 'entry_fees', 'exit_fees'];
  const FIELDS = [...LEGACY_FIELDS, ...RESULT_FIELDS];
  const QUANTITIES = ['submitted_quantity', 'filled_quantity', 'cancelled_quantity', 'exited_quantity', 'protected_quantity'];
  const TIMES = ['submitted_at', 'filled_at', 'cancelled_at', 'exited_at', 'protection_confirmed_at'];
  const listeners = [];
  const backupPreviews = new WeakMap();
  let lastError = '', pending = null;
  const clone = value => JSON.parse(JSON.stringify(value));
  const fail = error => ({ ok: false, error });
  const object = value => value && typeof value === 'object' && !Array.isArray(value);
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const emptyReport = (version = VERSION) => Object.fromEntries((version === 1 ? LEGACY_FIELDS : FIELDS).map(key => [key, null]));
  // Clearing cumulative fields means unknown, never "no order was submitted".
  // Once reporting begins, corrections cannot revive a fresh entry draft.
  const reported = item => item.report_updated_at !== null || Object.values(item.report).some(value => value !== null);
  const independent = item => item.kind === 'independent_research';
  const keyOf = candidate => candidate.stage + ':' + candidate.ticker;
  const cents = value => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
  const dollars = value => '$' + (BigInt(value) / 100n).toLocaleString('en-US') + '.' + String(BigInt(value) % 100n).padStart(2, '0');
  const cashText = value => String(BigInt(value) / 100n) + '.' + String(BigInt(value) % 100n).padStart(2, '0');
  function exactKeys(value, keys) { return object(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key)); }
  function validDate(value) {
    if (typeof value !== 'string' || !DATE.test(value)) return false;
    const date = new Date(value + 'T00:00:00Z');
    return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
  }
  function timestamp(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d{1,3})?)?(?:Z|[+-](?:0\d|1[0-4]):[0-5]\d)$/.test(value) || !validDate(value.slice(0, 10))) return null;
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? date.toISOString() : null;
  }
  function quantity(value) {
    if (value === null || value === '') return null;
    const raw = typeof value === 'number' ? String(value) : value;
    if (typeof raw !== 'string' || !/^\d{1,7}$/.test(raw.trim())) return undefined;
    const number = Number(raw.trim());
    return Number.isSafeInteger(number) && number <= MAX_SHARES ? number : undefined;
  }
  function average(value) {
    if (value === null || value === '') return null;
    if (typeof value !== 'string' || !/^\d{1,10}(?:\.\d{1,6})?$/.test(value.trim())) return undefined;
    const [whole, part = ''] = value.trim().split('.');
    if (BigInt(whole) * 1000000n + BigInt(part.padEnd(6, '0')) <= 0n) return undefined;
    return String(BigInt(whole)) + (part.replace(/0+$/, '') ? '.' + part.replace(/0+$/, '') : '');
  }
  function normalizeReport(fields, at, version = VERSION) {
    if (!exactKeys(fields, version === 1 ? LEGACY_FIELDS : FIELDS)) return fail('Enter the complete set of manual report fields; blank means unknown.');
    const out = emptyReport(version);
    for (const key of QUANTITIES) {
      out[key] = quantity(fields[key]);
      if (out[key] === undefined) return fail('Quantities must be whole shares between 0 and ' + MAX_SHARES + ', or blank for unknown.');
    }
    out.average_price = average(fields.average_price);
    if (out.average_price === undefined) return fail('Average fill price must be positive, with at most six decimal places, or blank for unknown.');
    if (version >= 2) {
      out.average_exit_price = average(fields.average_exit_price);
      if (out.average_exit_price === undefined) return fail('Average exit price must be positive, with at most six decimal places, or blank for unknown.');
      for (const key of ['entry_fees', 'exit_fees']) {
        const value = fields[key] === null ? null : api.cashPreview.cents(fields[key]);
        if (value === undefined) return fail('Actual fees must be non-negative dollar amounts with at most two decimals, or blank for unknown.');
        out[key] = value === null ? null : cashText(value);
      }
    }
    for (const key of TIMES) {
      const raw = fields[key];
      out[key] = raw === null || raw === '' ? null : timestamp(raw);
      if (raw !== null && raw !== '' && !out[key]) return fail('Use a valid date and time with an explicit time-zone offset.');
      if (out[key] && at && Date.parse(out[key]) > Date.parse(at) + 5000) return fail('A reported broker event cannot be in the future. Check its time zone.');
    }
    const submitted = out.submitted_quantity, filled = out.filled_quantity, cancelled = out.cancelled_quantity, exited = out.exited_quantity;
    if (submitted === null && (filled !== null || cancelled !== null)) return fail('Enter the quantity actually submitted before reporting fills or cancellations.');
    if (submitted !== null && ((filled !== null && filled > submitted) || (cancelled !== null && cancelled > submitted) || (filled !== null && cancelled !== null && filled + cancelled > submitted))) return fail('Filled plus cancelled shares cannot exceed the quantity reported submitted. Correct the cumulative quantities together.');
    if (exited !== null && (filled === null || exited > filled)) return fail('Exited shares cannot exceed reported entry fills. Enter or correct both cumulative quantities together.');
    if (version >= 2 && out.average_exit_price !== null && !exited) return fail('An average exit price needs a positive reported exit quantity.');
    if ((out.submitted_at && !submitted) || ((out.average_price !== null || out.filled_at) && !filled) || (out.cancelled_at && !cancelled) || (out.exited_at && !exited) || (out.protection_confirmed_at && out.protected_quantity === null)) return fail('Prices and event times need their corresponding reported quantity; zero fills have no fill price or fill time.');
    for (const key of ['filled_at', 'cancelled_at', 'exited_at']) if (out[key] && out.submitted_at && out[key] < out.submitted_at) return fail('A fill, cancellation or exit cannot precede the reported submission. Correct the times together.');
    if (out.cancelled_at && out.filled_at && out.cancelled_at < out.filled_at) return fail('The remainder cancellation cannot precede the latest reported fill.');
    // A partial exit may precede a later partial entry fill. Only a reported
    // complete exit must be at/after the latest entry fill.
    if (exited > 0 && exited === filled && out.exited_at && out.filled_at && out.exited_at < out.filled_at) return fail('A complete exit cannot precede the latest reported entry fill.');
    return { ok: true, report: out };
  }
  function validReference(ref) { return exactKeys(ref, ['version', ...REF]) && ref.version === 1 && REF.every(key => HEX.test(ref[key])); }
  function orderValid(order) {
    if (!exactKeys(order, ['symbol', 'action', 'quantity', 'order_type', 'stop_price', 'limit_price', 'time_in_force', 'conditional', 'then']) || !/^[A-Z][A-Z0-9.-]{0,14}$/.test(order.symbol) ||
        !exactKeys(order.then, ['action', 'quantity', 'order_type', 'stop_price', 'time_in_force'])) return false;
    return api.cashPreview.calculate({ cash: '90071992547409.91', fees: '0', quantity: '1', order }).state === 'calculated';
  }
  function planValid(plan) {
    if (!exactKeys(plan, ['reference', 'ticker', 'stage', 'order', 'timing', 'exit_schedule']) || !validReference(plan.reference) || !['bursts', 'setting-up'].includes(plan.stage) || !orderValid(plan.order) || plan.ticker !== plan.order.symbol) return false;
    const timing = plan.timing;
    if (!exactKeys(timing, ['applicable_session', 'opens_at', 'cutoff_at', 'closes_at']) || !validDate(timing.applicable_session) || !['opens_at', 'cutoff_at', 'closes_at'].every(key => timestamp(timing[key])) ||
        !(Date.parse(timing.opens_at) < Date.parse(timing.cutoff_at) && Date.parse(timing.cutoff_at) <= Date.parse(timing.closes_at))) return false;
    return Array.isArray(plan.exit_schedule) && plan.exit_schedule.length > 0 && plan.exit_schedule.length <= 20 && plan.exit_schedule.every(row =>
      exactKeys(row, ['day', 'date', 'key', 'instruction']) && Number.isInteger(row.day) && row.day > 0 && row.day <= 30 && validDate(row.date) && row.date >= timing.applicable_session &&
      typeof row.key === 'string' && /^[a-z0-9_]{1,80}$/.test(row.key) && typeof row.instruction === 'string' && row.instruction.length > 0 && row.instruction.length <= 2000);
  }
  function calculation(item) {
    if (independent(item)) return null;
    return api.cashPreview.calculate({ cash: cashText(item.draft.cash_cents), fees: cashText(item.draft.fee_cents), quantity: String(item.draft.quantity), order: item.plan.order });
  }
  // Source clocks retain upstream microseconds and spelling. Manual broker
  // times use the separate timestamp() normalizer above.
  function sourceTime(value) {
    if (typeof value !== 'string') return false;
    return !!timestamp(value.replace(/(\.\d{3})\d{1,3}(?=Z|[+-])/, '$1'));
  }
  function researchPublicationValid(pub) {
    return exactKeys(pub, ['data_sha256', 'context_sha256', 'run_id', 'rules_version', 'measured_session', 'applicable_session', 'published_at', 'reader_projection_version', 'reader_sha256']) &&
      ['data_sha256', 'context_sha256', 'reader_sha256'].every(key => typeof pub[key] === 'string' && HEX.test(pub[key])) &&
      typeof pub.run_id === 'string' && /^[A-Za-z0-9_-]{1,100}$/.test(pub.run_id) && /^[a-f0-9]{12}$/.test(pub.rules_version) &&
      validDate(pub.measured_session) && validDate(pub.applicable_session) && sourceTime(pub.published_at) && pub.reader_projection_version === 1;
  }
  function researchValid(source) {
    if (!exactKeys(source, ['ticker', 'stage', 'publication', 'cohort', 'evidence', 'baseline_admitted']) || !/^[A-Z][A-Z0-9.-]{0,14}$/.test(source.ticker) || source.stage !== 'setting-up' || typeof source.baseline_admitted !== 'boolean') return false;
    const cohort = source.cohort, evidence = source.evidence;
    return researchPublicationValid(source.publication) &&
      exactKeys(cohort, ['sha256', 'bytes', 'generated_at', 'policy_id']) && HEX.test(cohort.sha256) && Number.isSafeInteger(cohort.bytes) && cohort.bytes > 0 && cohort.bytes <= 128 * 1024 &&
      sourceTime(cohort.generated_at) && cohort.policy_id === 'anticipation_stop_width_4_to_5_v1' &&
      exactKeys(evidence, ['id', 'plan_sha256', 'source_sha256', 'inputs_sha256']) && Object.values(evidence).every(value => typeof value === 'string' && HEX.test(value));
  }
  function validItem(item, version = VERSION) {
    if (!object(item)) return false;
    const isIndependent = version === VERSION && independent(item);
    const fields = ['version', 'id', 'revision', 'created_at', 'updated_at', 'report', 'report_updated_at', ...(isIndependent ? ['source'] : ['publication', 'plan', 'draft']), ...(version === VERSION ? ['kind'] : [])];
    if (!exactKeys(item, fields) || item.version !== version || (version === VERSION && !['planned_handoff', 'independent_research'].includes(item.kind)) || !Number.isSafeInteger(item.revision) || item.revision < 1 ||
        !timestamp(item.created_at) || !timestamp(item.updated_at) || Date.parse(item.created_at) > Date.parse(item.updated_at)) return false;
    if (isIndependent) {
      if (!researchValid(item.source) || item.id !== item.source.publication.data_sha256 + ':' + item.source.evidence.id || item.report_updated_at === null) return false;
    } else {
      if (!planValid(item.plan)) return false;
      const pub = item.publication, draft = item.draft;
      if (!exactKeys(pub, ['sha256', 'session', 'published_at', 'rules_version']) || !HEX.test(pub.sha256) || !validDate(pub.session) || !sourceTime(pub.published_at) || !/^[a-f0-9]{12}$/.test(pub.rules_version) ||
          item.id !== pub.sha256 + ':' + item.plan.reference.id || !exactKeys(draft, ['quantity', 'cash_cents', 'fee_cents']) || !Number.isInteger(draft.quantity) || draft.quantity < 1 || draft.quantity > MAX_SHARES || !cents(draft.cash_cents) || !cents(draft.fee_cents) || calculation(item).state !== 'calculated') return false;
    }
    const report = normalizeReport(item.report, null, version);
    return report.ok && same(report.report, item.report) && (item.report_updated_at === null ? !reported(item) : !!timestamp(item.report_updated_at) && Date.parse(item.report_updated_at) <= Date.parse(item.updated_at));
  }
  // Parse files and storage through the same complete rules. This is pure:
  // an invalid selected file must not poison a healthy destination's status.
  function parseStore(raw) {
    if (typeof raw !== 'string' || /[\uD800-\uDFFF]/u.test(raw) || new w.TextEncoder().encode(raw).length > MAX_BYTES) throw new Error('size or encoding');
    const store = JSON.parse(raw);
    if (!exactKeys(store, ['version', 'items']) || ![1, 2, VERSION].includes(store.version) || !Array.isArray(store.items) || store.items.length > MAX_ITEMS || !store.items.every(item => validItem(item, store.version)) || new Set(store.items.map(item => item.id)).size !== store.items.length) throw new Error('shape');
    // The normalized view is not an export or restore serialization.
    const items = store.version < VERSION ? store.items.map(item => ({ ...item, version: VERSION, kind: 'planned_handoff',
      report: store.version === 1 ? { ...item.report, ...Object.fromEntries(RESULT_FIELDS.map(key => [key, null])) } : item.report })) : store.items;
    return { items, raw, version: store.version };
  }
  function load() {
    let raw;
    try {
      raw = w.localStorage.getItem(KEY);
      if (raw === null) { lastError = ''; return { ok: true, items: [], raw }; }
      // Reading an old record never writes or invents prices, fees or times.
      // The original raw bytes remain available for a failed explicit save.
      const parsed = parseStore(raw);
      lastError = ''; return { ok: true, ...parsed };
    } catch (error) {
      lastError = 'Private handoff storage is unavailable, unreadable or from another version. It was left untouched; no reported positions were removed.';
      return { ok: false, items: [], raw, error: lastError };
    }
  }
  function notify() { listeners.forEach(fn => { try { fn(); } catch (error) { /* other listeners still receive the change */ } }); }
  function save(loaded, items) {
    if (!items.every(item => validItem(item))) return fail('The corrected record is inconsistent, including its update clock. Nothing was overwritten.');
    if (items.length > MAX_ITEMS) return fail('Private storage has reached ' + MAX_ITEMS + ' handoffs. Explicitly remove an old record before preparing another; nothing was evicted.');
    const raw = JSON.stringify({ version: VERSION, items });
    if (new w.TextEncoder().encode(raw).length > MAX_BYTES) return fail('Private handoff storage is full. Nothing was removed or overwritten.');
    return writeRaw(loaded, raw);
  }
  function writeRaw(loaded, raw) {
    // All app writers share the lock. Also refuse an out-of-band raw change
    // before writing; equal item counts are not an unchanged destination.
    try {
      if (w.localStorage.getItem(KEY) !== loaded.raw) return fail('Private storage changed in another view. Review it again before saving; nothing was overwritten.');
    } catch (error) { return fail('Private storage could not be checked before saving. Nothing was overwritten.'); }
    try {
      w.localStorage.setItem(KEY, raw);
      if (w.localStorage.getItem(KEY) !== raw) throw new Error('readback');
      pending = null; lastError = ''; return { ok: true };
    } catch (error) {
      pending = { prior: loaded.raw, proposed: raw };
      try { if (loaded.raw === null) w.localStorage.removeItem(KEY); else w.localStorage.setItem(KEY, loaded.raw); } catch (ignored) { /* keep both payloads available for recovery */ }
      return fail('The save could not be confirmed. Keep your input and this tab open to retry or recover the private record.');
    }
  }
  async function transaction(operation) {
    if (!w.navigator || !w.navigator.locks) return fail('Private saving isn’t available in this browser. Open the secure site in a current browser; saved records remain readable.');
    try {
      const result = await w.navigator.locks.request(KEY, () => { const loaded = load(); return loaded.ok ? operation(loaded) : fail(loaded.error); });
      if (result.ok) notify();
      return result;
    } catch (error) { return fail('The private save could not complete. Your entered values remain available to retry.'); }
  }
  function currentPlan(key, expectedPublication) {
    const data = api.data, model = api.model, av = api.avail;
    if (!data || !av || !model || !api.morning || !api.observations) return fail('No current publication is ready for a personal draft.');
    const facts = api.morning.facts(data, av, model), observation = api.observations.facts();
    if (!facts.allowed || !facts.matched) return fail(!facts.allowed ? facts.reason : 'Published sizing does not match the cash-account reference.');
    if (!HEX.test(expectedPublication || '') || observation.canonicalHash !== expectedPublication) return fail('This draft belongs to another or unverified publication. Review the current plan first.');
    const candidate = facts.tickets.find(candidate => keyOf(candidate) === key);
    if (!candidate) return fail('This plan is no longer an admitted ticket in the current record.');
    const refusal = api.observations.refusal(candidate);
    if (refusal) return fail(refusal);
    const plan = candidate.plan || {}, order = plan.order_json;
    if (!orderValid(order) || order.symbol !== candidate.ticker || plan.shares !== order.quantity || (candidate.stage === 'bursts' ? plan.entry_ref : plan.trigger) !== order.stop_price || plan.limit !== order.limit_price || plan.stop !== order.then.stop_price || !validReference(plan.evidence_ref)) return fail('Published order details do not match the plan. No personal draft can be prepared.');
    const timing = data.run.timing || {};
    const snapshot = { reference: clone(plan.evidence_ref), ticker: candidate.ticker, stage: candidate.stage, order: clone(order),
      timing: Object.fromEntries(['applicable_session', 'opens_at', 'cutoff_at', 'closes_at'].map(key => [key, timing[key]])), exit_schedule: clone(plan.exit_schedule || []) };
    if (!planValid(snapshot)) return fail('The published plan lacks usable dated entry or exit terms.');
    return { ok: true, snapshot, publication: { sha256: expectedPublication, session: data.run.session, published_at: data.run.published_at, rules_version: data.app.rules_version } };
  }
  function availability(item) {
    if (!validItem(item)) return fail('This private draft is unreadable.');
    if (independent(item)) return fail('This is an independently reported trade. It has no entry draft or order to copy.');
    const current = currentPlan(keyOf(item.plan), item.publication.sha256);
    if (!current.ok) return current;
    if (!same(current.snapshot, item.plan) || !same(current.publication, item.publication)) return fail('The published plan changed. This saved readback remains history; prepare from the current publication.');
    if (reported(item)) return fail('Broker facts have been reported for this draft. Its recorded instructions remain readable; it is not a new entry to copy.');
    return { ok: true };
  }
  async function prepare(input) {
    return transaction(loaded => {
      if (api.reclock) api.reclock();
      const source = currentPlan(input && input.key, input && input.expectedPublication);
      if (!source.ok) return source;
      const calc = api.cashPreview.calculate({ cash: input.cash, fees: input.fees, quantity: input.quantity, order: source.snapshot.order });
      if (calc.state !== 'calculated') return fail(calc.reason);
      const id = source.publication.sha256 + ':' + source.snapshot.reference.id, previous = loaded.items.find(item => item.id === id);
      if ((previous ? previous.revision : null) !== input.expectedRevision) return fail('This private draft changed in another view. Reopen it before replacing it.');
      if (previous && (!same(previous.plan, source.snapshot) || !same(previous.publication, source.publication))) return fail('The published source changed under this draft. Its original evidence cannot be overwritten.');
      if (previous && reported(previous)) return fail('This draft has reported broker facts. Correct those facts explicitly; preparing a draft cannot overwrite them.');
      const at = new Date().toISOString();
      const item = { version: VERSION, kind: 'planned_handoff', id, revision: previous ? previous.revision + 1 : 1, created_at: previous ? previous.created_at : at, updated_at: at,
        publication: source.publication, plan: source.snapshot, draft: { quantity: calc.quantity, cash_cents: api.cashPreview.cents(input.cash), fee_cents: calc.feeCents }, report: emptyReport(), report_updated_at: null };
      if (!validItem(item)) return fail('The exact published source cannot be stored as a private draft.');
      const items = loaded.items.filter(row => row.id !== id); items.push(item);
      const saved = save(loaded, items); return saved.ok ? { ok: true, item: clone(item) } : saved;
    });
  }
  function inspectResearch(request) {
    const journal = object(request) && Object.hasOwn(request, 'origin');
    if (journal && request.origin !== 'retained_journal') return fail('This research reference has an unsupported origin. Open its verified source before recording a trade.');
    const verifier = journal ? api.researchOutcomes : api.stopResearch;
    if (!verifier || typeof verifier.reportReference !== 'function') return fail(journal ? 'Open the verified research journal before recording a trade.' : 'Open the verified research comparison before recording a trade.');
    const verified = verifier.reportReference(request);
    if (!verified || !verified.ok) return fail(verified && verified.error || 'The research source changed. Open its current reference before recording a trade.');
    const source = verified.source, hashes = api.observations && api.observations.facts();
    // A retained original remains historical. Only the journal verifier's
    // separately bound active publication authorizes this source lookup.
    const publication = journal ? verified.publication : source && source.publication;
    if (!researchValid(source) || !researchPublicationValid(publication) || !hashes || hashes.canonicalHash !== publication.data_sha256) return fail('The research source does not match the verified publication.');
    return { ok: true, source: clone(source) };
  }
  async function reportResearch(request, fields, expectedRevision = null) {
    return transaction(loaded => {
      const inspected = inspectResearch(request);
      if (!inspected.ok) return inspected;
      const source = inspected.source, id = source.publication.data_sha256 + ':' + source.evidence.id;
      if (loaded.items.some(item => item.id === id)) return { ...fail('A private record already exists for this original idea. Open and correct that record instead of creating another.'), existingId: id };
      if (expectedRevision !== null) return fail('A new independent report has no prior revision. Open the saved record to correct it.');
      const at = new Date().toISOString(), normalized = normalizeReport(fields, at);
      if (!normalized.ok) return normalized;
      if (!(normalized.report.filled_quantity > 0)) return fail('Record a positive quantity actually filled at your broker before saving an independent trade. Blank or zero is not an executed trade.');
      const item = { version: VERSION, kind: 'independent_research', id, revision: 1, created_at: at, updated_at: at, source, report: normalized.report, report_updated_at: at };
      const saved = save(loaded, [...loaded.items, item]);
      return saved.ok ? { ok: true, item: clone(item) } : saved;
    });
  }
  async function report(id, fields, expectedRevision) {
    return transaction(loaded => {
      const item = loaded.items.find(row => row.id === id);
      if (!item || item.revision !== expectedRevision) return fail('This handoff was removed or changed in another view. Reopen its current report before correcting it.');
      const at = new Date().toISOString(), normalized = normalizeReport(fields, at);
      if (!normalized.ok) return normalized;
      item.report = normalized.report; item.report_updated_at = at; item.updated_at = at; item.revision += 1;
      const saved = save(loaded, loaded.items); return saved.ok ? { ok: true, item: clone(item) } : saved;
    });
  }
  async function remove(id, expectedRevision) {
    return transaction(loaded => {
      const item = loaded.items.find(row => row.id === id);
      if (!item || item.revision !== expectedRevision) return fail('This handoff changed. Review its current contents before explicitly deleting it.');
      const saved = save(loaded, loaded.items.filter(row => row.id !== id)); return saved.ok ? { ok: true } : saved;
    });
  }
  function backupSummary(parsed) {
    return { version: parsed.version, count: parsed.items.length,
      planned_count: parsed.items.filter(item => !independent(item)).length,
      independent_count: parsed.items.filter(independent).length,
      records: parsed.items.map(item => {
        const source = independent(item) ? item.source : item, pub = source.publication;
        return { id: item.id, ticker: independent(item) ? source.ticker : item.plan.ticker, kind: item.kind,
          session: independent(item) ? pub.measured_session : pub.session, published_at: pub.published_at,
          created_at: item.created_at, updated_at: item.updated_at };
      }) };
  }
  function exportBackup() {
    const loaded = load();
    if (!loaded.ok) return fail(loaded.error);
    if (loaded.raw === null) return fail('There are no saved private records to download. Unsaved inputs are not a backup.');
    return { ok: true, raw: loaded.raw, summary: backupSummary(loaded) };
  }
  function previewBackup(raw) {
    let parsed;
    try { parsed = parseStore(raw); } catch (error) { return fail('This file is not a supported private backup, is inconsistent, or exceeds the 100-record / 1 MiB limit. Nothing was changed.'); }
    const loaded = load();
    if (!loaded.ok) return fail(loaded.error);
    if (loaded.items.length) return fail('Restore requires empty private storage. Existing records will not be merged or overwritten.');
    const preview = { raw, expectedRaw: loaded.raw, summary: backupSummary(parsed) };
    backupPreviews.set(preview, { raw, expectedRaw: loaded.raw });
    return { ok: true, preview };
  }
  async function restoreBackup(preview) {
    return transaction(loaded => {
      if (!exactKeys(preview, ['raw', 'expectedRaw', 'summary']) || !(preview.expectedRaw === null || typeof preview.expectedRaw === 'string')) return fail('Preview a supported private backup before confirming restore.');
      const issued = backupPreviews.get(preview);
      if (!issued || issued.raw !== preview.raw || issued.expectedRaw !== preview.expectedRaw) return fail('The backup differs from its preview. Preview the file again before restoring.');
      if (loaded.items.length || loaded.raw !== preview.expectedRaw) return fail('Private storage is occupied or changed since preview. Nothing was overwritten; preview again in an empty destination.');
      let parsed;
      try { parsed = parseStore(preview.raw); } catch (error) { return fail('The backup changed or is not supported. Nothing was restored.'); }
      const summary = backupSummary(parsed);
      if (!same(summary, preview.summary)) return fail('The backup differs from its preview. Preview the file again before restoring.');
      const saved = writeRaw(loaded, preview.raw);
      if (saved.ok) backupPreviews.delete(preview);
      return saved.ok ? { ok: true, summary } : saved;
    });
  }
  function priceMicros(value) {
    const [whole, part = ''] = value.split('.');
    return BigInt(whole) * 1000000n + BigInt(part.padEnd(6, '0'));
  }
  function displayMicros(value) {
    const negative = value < 0n, magnitude = negative ? -value : value;
    const rounded = (magnitude + 5000n) / 10000n;
    if (value !== 0n && rounded === 0n) return (negative ? '-' : '') + '<$0.01';
    return (negative ? '-' : '') + dollars(rounded);
  }
  function completedResult(report) {
    const missing = [], reasons = [];
    const absent = (field, reason) => { missing.push(field); reasons.push(reason); };
    if (report.filled_quantity === null || report.filled_quantity === 0) absent('filled_quantity', 'Report a positive number of actual entry fills.');
    if (report.exited_quantity === null) absent('exited_quantity', 'Report how many filled shares were exited.');
    else if (report.exited_quantity !== report.filled_quantity) reasons.push('The reported position is not fully exited. Partial exits have no calculated result here because their cost basis is not established.');
    if (report.submitted_quantity === null) absent('submitted_quantity', 'Report the quantity actually submitted.');
    if (report.cancelled_quantity === null) absent('cancelled_quantity', 'Report cancelled entry shares, including explicit 0 when none were cancelled.');
    else if (report.filled_quantity !== null && report.submitted_quantity !== null && report.filled_quantity + report.cancelled_quantity !== report.submitted_quantity) reasons.push('Reconcile the remaining submitted entry shares before completing this result.');
    for (const [field, label] of [['average_price', 'average entry price'], ['average_exit_price', 'average exit price'], ['entry_fees', 'actual entry fees'], ['exit_fees', 'actual exit fees'], ['filled_at', 'latest entry fill time'], ['exited_at', 'latest exit time']]) {
      if (report[field] === null) absent(field, 'Report the ' + label + (field.endsWith('_fees') ? '; enter 0 only when you have confirmed no fees.' : '.'));
    }
    const empty = { state: 'incomplete', reasons, missing, quantity: null, gross_microusd: null, fees_microusd: null, net_microusd: null,
      gross_display: null, fees_display: null, net_display: null, outcome: null };
    if (reasons.length) return empty;
    const gross = (priceMicros(report.average_exit_price) - priceMicros(report.average_price)) * BigInt(report.filled_quantity);
    // Fees were explicitly reported in cents. Never borrow the draft's buffer.
    const fees = priceMicros(report.entry_fees) + priceMicros(report.exit_fees), net = gross - fees;
    return { ...empty, state: 'complete', quantity: report.filled_quantity, gross_microusd: String(gross), fees_microusd: String(fees), net_microusd: String(net),
      gross_display: displayMicros(gross), fees_display: displayMicros(fees), net_display: displayMicros(net), outcome: net > 0n ? 'gain' : net < 0n ? 'loss' : 'breakeven' };
  }
  function exitReview(item) {
    const report = item.report, hasReport = reported(item);
    const held = report.filled_quantity === null || report.exited_quantity === null ? null : report.filled_quantity - report.exited_quantity;
    if (independent(item)) return { basis: held === null ? 'reported_unknown' : 'reported_remaining', quantity: held, model_half_quantity: null, model_remaining_quantity: null, needs_review: held === null,
      message: 'This independent trade has no personal entry draft or archived exit instructions. Remaining holdings are ' + (held === null ? 'unknown; report actual entry fills and exits.' : held + ' reported whole ' + (held === 1 ? 'share.' : 'shares.')) + ' Check holdings and protection at your broker; no exit has been inferred or placed.' };
    const quantity = hasReport ? held : item.draft.quantity;
    const basis = hasReport ? (quantity === null ? 'reported_unknown' : 'reported_remaining') : 'personal_draft';
    if (quantity === null) return { basis, quantity, model_half_quantity: null, model_remaining_quantity: null, needs_review: true,
      message: 'Remaining holdings are unknown. Check entry fills and exits at your broker before applying the archived partial-exit schedule. Your draft quantity is not a report of remaining holdings.' };
    if (quantity === 0) return { basis, quantity, model_half_quantity: null, model_remaining_quantity: null, needs_review: false,
      message: 'You reported no remaining shares. The archived exit schedule remains history; SpicyStock has not verified your broker holdings.' };
    // The existing model takes at least half in whole shares (plan.follow).
    // This reference never decides whether an exit is due or repeats a prior exit.
    const half = quantity - Math.floor(quantity / 2), remaining = quantity - half;
    const source = hasReport ? 'Your reported remaining holdings are ' : 'Your personal draft is ';
    const units = quantity === 1 ? ' whole share. ' : ' whole shares. ';
    return { basis, quantity, model_half_quantity: half, model_remaining_quantity: remaining, needs_review: quantity % 2 !== 0,
      message: source + quantity + units + "The model's at-least-half convention rounds up to " + half + (half === 1 ? ' whole share' : ' whole shares') + ', leaving ' + remaining + '. ' +
        (quantity === 1 ? 'A one-share position cannot be partly exited in whole shares. ' : '') +
        'This is reference arithmetic and does not determine whether another exit is due. Review prior exits and choose feasible quantities at your broker before acting; fractional-share support is unknown.' };
  }
  function summary(item) {
    if (!validItem(item)) return null;
    const report = item.report, filled = report.filled_quantity, submitted = report.submitted_quantity, cancelled = report.cancelled_quantity, exited = report.exited_quantity, protectedQty = report.protected_quantity;
    const held = filled === null || exited === null ? null : filled - exited;
    const warnings = [];
    if (!independent(item)) {
      if (submitted !== null && submitted !== item.draft.quantity) warnings.push('Reported submitted quantity differs from your personal draft; this is a broker fact, not a revised plan.');
      if (filled && report.average_price !== null && (Number(report.average_price) < item.plan.order.stop_price || Number(report.average_price) > item.plan.order.limit_price)) warnings.push('Reported average fill price is outside the published trigger-to-limit range.');
      if (report.filled_at && (Date.parse(report.filled_at) < Date.parse(item.plan.timing.opens_at) || Date.parse(report.filled_at) >= Date.parse(item.plan.timing.cutoff_at))) warnings.push('Reported fill time is outside the published entry window.');
    }
    const protection = held === null || protectedQty === null ? 'unknown' : protectedQty === held ? 'matched' : protectedQty < held ? 'under' : 'over';
    if (protection === 'under') warnings.push('Broker-confirmed protective quantity is below reported remaining holdings. Reconcile protection at your broker.');
    if (protection === 'over') warnings.push('Broker-confirmed protective quantity exceeds reported remaining holdings. Reconcile the sell quantity at your broker.');
    return { state: !reported(item) ? 'draft' : filled === null ? 'reported_unknown_fill' : filled === 0 ? 'reported_no_fill' : held === 0 ? 'reported_closed' : submitted !== null && filled < submitted ? 'reported_partial_fill' : 'reported_filled',
      planned_quantity: independent(item) ? null : item.draft.quantity, submitted_quantity: submitted, filled_quantity: filled, exited_quantity: exited, reported_held_quantity: held,
      unfilled_quantity: submitted === null || filled === null ? null : submitted - filled,
      uncancelled_quantity: submitted === null || filled === null || cancelled === null ? null : submitted - filled - cancelled,
      cancelled_quantity: cancelled, protected_quantity: protectedQty, protection, warnings, exit_review: exitReview(item), calculation: calculation(item), completed_result: completedResult(report) };
  }
  function readback(item) {
    if (!validItem(item) || independent(item)) return '';
    const order = item.plan.order, qty = item.draft.quantity;
    return 'PERSONAL BROKER READBACK — ' + item.plan.ticker + '\n' +
      'BUY ' + qty + ' ' + item.plan.ticker + ' · STOP LIMIT · trigger ' + dollars(api.cashPreview.cents(String(order.stop_price))) + ' · limit ' + dollars(api.cashPreview.cents(String(order.limit_price))) + ' · DAY\n' +
      'Planned protective SELL ' + qty + ' ' + item.plan.ticker + ' · STOP ' + dollars(api.cashPreview.cents(String(order.then.stop_price))) + ' · GTC; confirm support, activation and actual filled quantity at your broker.\n' +
      'Published quantity: ' + order.quantity + '. This personal readback places no order or protective stop.\n' +
      'Entry window: ' + item.plan.timing.opens_at + ' to ' + item.plan.timing.cutoff_at + '. Cancel any unfilled entry at the cutoff yourself.\n' +
      'Whole-share exit reference: ' + exitReview(item).message;
  }
  function copy(id) {
    if (api.reclock) api.reclock();
    const loaded = load(), item = loaded.items.find(row => row.id === id);
    if (!loaded.ok || !item) return fail(loaded.error || 'This private draft is no longer saved.');
    const allowed = availability(item);
    return allowed.ok ? { ok: true, text: readback(item) } : allowed;
  }
  try { w.addEventListener('storage', event => { if (event.key === KEY || event.key === null) notify(); }); } catch (error) { /* reads still validate each time */ }
  api.handoff = {
    VERSION, KEY, MAX_ITEMS, MAX_BYTES, FIELDS: FIELDS.slice(), prepare, inspectResearch, reportResearch, report, remove, summary, availability, readback, copy, exportBackup, previewBackup, restoreBackup,
    list: () => clone(load().items), find: id => clone(load().items.find(item => item.id === id) || null),
    status: () => { const result = load(); return { available: result.ok && !!(w.navigator && w.navigator.locks), error: result.error || (!(w.navigator && w.navigator.locks) ? 'Private saving isn’t available in this browser. Open the secure site in a current browser; saved records remain readable.' : ''), count: result.items.length }; },
    recovery: () => pending ? clone(pending) : { prior: load().raw, proposed: null },
    onChange: fn => { if (typeof fn === 'function') listeners.push(fn); }
  };
})(window);
