/* Private broker readback and manually reported cumulative entry facts. Nothing
   in this store submits an order, reserves cash, observes fills or edits a
   published plan. New preparation/copy uses current page guards; correcting
   reported facts deliberately does not require a still-open entry window. */
(function (w) {
  'use strict';
  const api = w.SCStock = w.SCStock || {};
  const VERSION = 1, KEY = 'spicystock:handoff:v1', MAX_ITEMS = 100, MAX_BYTES = 1048576, MAX_SHARES = 1000000;
  const HEX = /^[a-f0-9]{64}$/, DATE = /^\d{4}-\d{2}-\d{2}$/;
  const REF = ['id', 'context_sha256', 'plan_sha256', 'pick_sha256'];
  const FIELDS = ['submitted_quantity', 'submitted_at', 'filled_quantity', 'average_price', 'filled_at', 'cancelled_quantity', 'cancelled_at', 'exited_quantity', 'exited_at', 'protected_quantity', 'protection_confirmed_at'];
  const QUANTITIES = ['submitted_quantity', 'filled_quantity', 'cancelled_quantity', 'exited_quantity', 'protected_quantity'];
  const TIMES = ['submitted_at', 'filled_at', 'cancelled_at', 'exited_at', 'protection_confirmed_at'];
  const listeners = [];
  let lastError = '', pending = null;
  const clone = value => JSON.parse(JSON.stringify(value));
  const fail = error => ({ ok: false, error });
  const object = value => value && typeof value === 'object' && !Array.isArray(value);
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const emptyReport = () => Object.fromEntries(FIELDS.map(key => [key, null]));
  const reported = item => FIELDS.some(key => item.report[key] !== null);
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
  function normalizeReport(fields, at) {
    if (!exactKeys(fields, FIELDS)) return fail('Enter the complete set of manual report fields; blank means unknown.');
    const out = emptyReport();
    for (const key of QUANTITIES) {
      out[key] = quantity(fields[key]);
      if (out[key] === undefined) return fail('Quantities must be whole shares between 0 and ' + MAX_SHARES + ', or blank for unknown.');
    }
    out.average_price = average(fields.average_price);
    if (out.average_price === undefined) return fail('Average fill price must be positive, with at most six decimal places, or blank for unknown.');
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
    return api.cashPreview.calculate({ cash: cashText(item.draft.cash_cents), fees: cashText(item.draft.fee_cents), quantity: String(item.draft.quantity), order: item.plan.order });
  }
  function validItem(item) {
    if (!exactKeys(item, ['version', 'id', 'revision', 'created_at', 'updated_at', 'publication', 'plan', 'draft', 'report', 'report_updated_at']) || item.version !== VERSION || !Number.isSafeInteger(item.revision) || item.revision < 1 ||
        !timestamp(item.created_at) || !timestamp(item.updated_at) || Date.parse(item.created_at) > Date.parse(item.updated_at) || !planValid(item.plan)) return false;
    const pub = item.publication, draft = item.draft;
    if (!exactKeys(pub, ['sha256', 'session', 'published_at', 'rules_version']) || !HEX.test(pub.sha256) || !validDate(pub.session) || !timestamp(pub.published_at) || !/^[a-f0-9]{12}$/.test(pub.rules_version) ||
        item.id !== pub.sha256 + ':' + item.plan.reference.id || !exactKeys(draft, ['quantity', 'cash_cents', 'fee_cents']) || !Number.isInteger(draft.quantity) || draft.quantity < 1 || draft.quantity > MAX_SHARES || !cents(draft.cash_cents) || !cents(draft.fee_cents) || calculation(item).state !== 'calculated') return false;
    const report = normalizeReport(item.report);
    return report.ok && same(report.report, item.report) && (item.report_updated_at === null ? !reported(item) : !!timestamp(item.report_updated_at) && Date.parse(item.report_updated_at) <= Date.parse(item.updated_at));
  }
  function load() {
    let raw;
    try {
      raw = w.localStorage.getItem(KEY);
      if (raw === null) { lastError = ''; return { ok: true, items: [], raw }; }
      if (new w.TextEncoder().encode(raw).length > MAX_BYTES) throw new Error('size');
      const store = JSON.parse(raw);
      if (!exactKeys(store, ['version', 'items']) || store.version !== VERSION || !Array.isArray(store.items) || store.items.length > MAX_ITEMS || !store.items.every(validItem) || new Set(store.items.map(item => item.id)).size !== store.items.length) throw new Error('shape');
      lastError = ''; return { ok: true, items: store.items, raw };
    } catch (error) {
      lastError = 'Private handoff storage is unavailable, unreadable or from another version. It was left untouched; no reported positions were removed.';
      return { ok: false, items: [], raw, error: lastError };
    }
  }
  function notify() { listeners.forEach(fn => { try { fn(); } catch (error) { /* other listeners still receive the change */ } }); }
  function save(loaded, items) {
    if (!items.every(validItem)) return fail('The corrected record is inconsistent, including its update clock. Nothing was overwritten.');
    if (items.length > MAX_ITEMS) return fail('Private storage has reached ' + MAX_ITEMS + ' handoffs. Explicitly remove an old record before preparing another; nothing was evicted.');
    const raw = JSON.stringify({ version: VERSION, items });
    if (new w.TextEncoder().encode(raw).length > MAX_BYTES) return fail('Private handoff storage is full. Nothing was removed or overwritten.');
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
      const item = { version: VERSION, id, revision: previous ? previous.revision + 1 : 1, created_at: previous ? previous.created_at : at, updated_at: at,
        publication: source.publication, plan: source.snapshot, draft: { quantity: calc.quantity, cash_cents: api.cashPreview.cents(input.cash), fee_cents: calc.feeCents }, report: emptyReport(), report_updated_at: null };
      if (!validItem(item)) return fail('The exact published source cannot be stored as a private draft.');
      const items = loaded.items.filter(row => row.id !== id); items.push(item);
      const saved = save(loaded, items); return saved.ok ? { ok: true, item: clone(item) } : saved;
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
  function summary(item) {
    if (!validItem(item)) return null;
    const report = item.report, filled = report.filled_quantity, submitted = report.submitted_quantity, cancelled = report.cancelled_quantity, exited = report.exited_quantity, protectedQty = report.protected_quantity;
    const held = filled === null || exited === null ? null : filled - exited;
    const warnings = [];
    if (submitted !== null && submitted !== item.draft.quantity) warnings.push('Reported submitted quantity differs from your personal draft; this is a broker fact, not a revised plan.');
    if (filled && report.average_price !== null && (Number(report.average_price) < item.plan.order.stop_price || Number(report.average_price) > item.plan.order.limit_price)) warnings.push('Reported average fill price is outside the published trigger-to-limit range.');
    if (report.filled_at && (Date.parse(report.filled_at) < Date.parse(item.plan.timing.opens_at) || Date.parse(report.filled_at) >= Date.parse(item.plan.timing.cutoff_at))) warnings.push('Reported fill time is outside the published entry window.');
    const protection = held === null || protectedQty === null ? 'unknown' : protectedQty === held ? 'matched' : protectedQty < held ? 'under' : 'over';
    if (protection === 'under') warnings.push('Broker-confirmed protective quantity is below reported remaining holdings. Reconcile protection at your broker.');
    if (protection === 'over') warnings.push('Broker-confirmed protective quantity exceeds reported remaining holdings. Reconcile the sell quantity at your broker.');
    return { state: !reported(item) ? 'draft' : filled === null ? 'reported_unknown_fill' : filled === 0 ? 'reported_no_fill' : held === 0 ? 'reported_closed' : submitted !== null && filled < submitted ? 'reported_partial_fill' : 'reported_filled',
      planned_quantity: item.draft.quantity, submitted_quantity: submitted, filled_quantity: filled, exited_quantity: exited, reported_held_quantity: held,
      unfilled_quantity: submitted === null || filled === null ? null : submitted - filled,
      uncancelled_quantity: submitted === null || filled === null || cancelled === null ? null : submitted - filled - cancelled,
      cancelled_quantity: cancelled, protected_quantity: protectedQty, protection, warnings, calculation: calculation(item) };
  }
  function readback(item) {
    if (!validItem(item)) return '';
    const order = item.plan.order, qty = item.draft.quantity;
    return 'PERSONAL BROKER READBACK — ' + item.plan.ticker + '\n' +
      'BUY ' + qty + ' ' + item.plan.ticker + ' · STOP LIMIT · trigger ' + dollars(api.cashPreview.cents(String(order.stop_price))) + ' · limit ' + dollars(api.cashPreview.cents(String(order.limit_price))) + ' · DAY\n' +
      'Planned protective SELL ' + qty + ' ' + item.plan.ticker + ' · STOP ' + dollars(api.cashPreview.cents(String(order.then.stop_price))) + ' · GTC; confirm support, activation and actual filled quantity at your broker.\n' +
      'Published quantity: ' + order.quantity + '. This personal readback places no order or protective stop.\n' +
      'Entry window: ' + item.plan.timing.opens_at + ' to ' + item.plan.timing.cutoff_at + '. Cancel any unfilled entry at the cutoff yourself.';
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
    VERSION, KEY, MAX_ITEMS, MAX_BYTES, FIELDS: FIELDS.slice(), prepare, report, remove, summary, availability, readback, copy,
    list: () => clone(load().items), find: id => clone(load().items.find(item => item.id === id) || null),
    status: () => { const result = load(); return { available: result.ok && !!(w.navigator && w.navigator.locks), error: result.error || (!(w.navigator && w.navigator.locks) ? 'Private saving isn’t available in this browser. Open the secure site in a current browser; saved records remain readable.' : ''), count: result.items.length }; },
    recovery: () => pending ? clone(pending) : { prior: load().raw, proposed: null },
    onChange: fn => { if (typeof fn === 'function') listeners.push(fn); }
  };
})(window);
