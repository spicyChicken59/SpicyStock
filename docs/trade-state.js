/* Private, broker-independent plans and confirmed executions. Never sends orders. */
(function (root, factory) {
  'use strict';
  var api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.SCTradeState = api;
}(typeof window === 'object' ? window : null, function (root) {
  'use strict';
  var KEY = 'spicystock.trades.v2', LEGACY_KEY = 'spicystock.trade-journal.v1';
  var MAX_FILLS = 5000, MAX_PLANS = 1000, MAX_BYTES = 8000000;
  var CSV_COLUMNS = ['execution_id', 'symbol', 'side', 'qty', 'price', 'executed_at', 'fees', 'initial_stop', 'source', 'environment', 'account_id', 'plan_id', 'order_id'];
  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function obj(v) { return v !== null && typeof v === 'object' && !Array.isArray(v); }
  function num(v) { return typeof v === 'number' ? v : typeof v === 'string' && v.trim() ? Number(v) : NaN; }
  function finite(v) { return typeof v === 'number' && Number.isFinite(v); }
  function optional(v) { return v === undefined || v === null || v === ''; }
  function text(v, max) { return typeof v === 'string' && v.length > 0 && v.length <= max && !/[\u0000-\u001f\u007f]/.test(v); }
  function identity(v, max) { return text(v, max) && /^[A-Za-z0-9]/.test(v) && v.indexOf('|') < 0; }
  function symbol(v) { var s = typeof v === 'string' ? v.trim().toUpperCase() : ''; return /^[A-Z][A-Z0-9.-]{0,14}$/.test(s) ? s : null; }
  function date(v) { return typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && Number.isFinite(Date.parse(v + 'T12:00:00Z')) && new Date(v + 'T12:00:00Z').toISOString().slice(0, 10) === v; }
  function timestamp(v) {
    if (typeof v !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$/.test(v) || !date(v.slice(0, 10))) return null;
    var t = Date.parse(v), h = Number(v.slice(11, 13)), m = Number(v.slice(14, 16)), s = Number(v.slice(17, 19));
    return Number.isFinite(t) && h < 24 && m < 60 && s < 60 ? new Date(t).toISOString() : null;
  }
  function digest(str) { var a = 2166136261, b = 2246822507; for (var i = 0; i < str.length; i++) { a = Math.imul(a ^ str.charCodeAt(i), 16777619); b = Math.imul(b ^ str.charCodeAt(i), 3266489909); } return (a >>> 0).toString(16).padStart(8, '0') + (b >>> 0).toString(16).padStart(8, '0'); }
  function equal(a, b) { return JSON.stringify(a) === JSON.stringify(b); }
  function empty() { return { version: 2, revision: 0, profile: { capital: null, risk_percent: null, cash_cap: null, max_positions: null }, plans: [], fills: [], voids: [], links: [], broker_snapshots: [] }; }
  function validateProfile(p) {
    if (!obj(p)) throw Error('Profile must be an object.');
    var out = {};
    ['capital', 'risk_percent', 'cash_cap', 'max_positions'].forEach(function (k) { out[k] = optional(p[k]) ? null : num(p[k]); if (out[k] !== null && !finite(out[k])) throw Error('Profile values must be numbers.'); });
    if (out.capital !== null && (out.capital <= 0 || out.capital > 1e12)) throw Error('Enter capital greater than zero and no more than one trillion.');
    if (out.risk_percent !== null && (out.risk_percent < 0 || out.risk_percent > 100)) throw Error('Risk must be between 0% and 100%.');
    if (out.cash_cap !== null && (out.cash_cap < 0 || out.cash_cap > 1e12 || out.capital !== null && out.cash_cap > out.capital)) throw Error('Cash cap must be between zero and capital.');
    if (out.max_positions !== null && (!Number.isInteger(out.max_positions) || out.max_positions < 1 || out.max_positions > 1000)) throw Error('Maximum positions must be a whole number from 1 to 1000.');
    return out;
  }
  function wholeShares(value) { return Math.floor(value + Number.EPSILON * Math.max(1, Math.abs(value)) * 4); }
  function calculate(p) {
    p = p || {};
    try {
      var profile = validateProfile(p), entry = num(p.entry), stop = num(p.stop);
      if (profile.capital === null || profile.risk_percent === null || !finite(entry) || !finite(stop)) throw Error('Enter capital, risk %, entry and initial stop.');
      if (entry <= 0 || stop <= 0 || stop >= entry || entry > 1e9) throw Error('Entry must be positive and the initial stop must be below it.');
      var cash = profile.cash_cap === null ? profile.capital : profile.cash_cap;
      var budget = profile.capital * profile.risk_percent / 100;
      var qty = Math.min(wholeShares(budget / (entry - stop)), wholeShares(cash / entry));
      if (!Number.isSafeInteger(qty) || qty < 0) throw Error('Position size exceeds the supported range.');
      return { ok: true, qty: qty, planned_risk: qty * (entry - stop), position_cost: qty * entry, risk_budget: budget, cash_cap: cash, entry: entry, stop: stop };
    } catch (e) { return { ok: false, error: e.message }; }
  }
  function fillIdentity(f) { return [f.source, f.environment, f.account_id, f.execution_id].join('|'); }
  function bucketKey(f) { return [f.source, f.environment, f.account_id, f.symbol].join('|'); }
  function normalFill(f, now, allowFuture) {
    if (!obj(f)) throw Error('An execution must be an object.');
    var s = symbol(f.symbol), side = f.side, qty = num(f.qty), price = num(f.price);
    var executed = timestamp(f.executed_at);
    if (!s || (side !== 'buy' && side !== 'sell')) throw Error('Every execution needs a valid symbol and buy or sell side.');
    if (!finite(qty) || qty <= 0 || qty > 1e12 || !finite(price) || price <= 0 || price > 1e9 || !finite(qty * price)) throw Error('Quantity and execution price must be positive, finite numbers.');
    if (!executed || !allowFuture && Date.parse(executed) > now + 300000) throw Error('Execution time must be a valid, completed date and time with a timezone.');
    if (['manual', 'alpaca'].indexOf(f.source) < 0 || ['paper', 'live'].indexOf(f.environment) < 0) throw Error('Every execution needs its manual/Alpaca source and paper/live environment.');
    if (!identity(f.account_id, 100) || !identity(f.execution_id, 160)) throw Error('Every execution needs a valid account and unique execution ID.');
    var fees = optional(f.fees) ? null : num(f.fees), stop = optional(f.initial_stop) ? null : num(f.initial_stop);
    if (fees !== null && (!finite(fees) || fees < 0 || fees > 1e12)) throw Error('Fees must be zero or positive; leave blank if unknown.');
    if (stop !== null && (!finite(stop) || stop <= 0 || side === 'buy' && stop >= price)) throw Error('Initial stop must be positive and below the actual buy price.');
    if (!optional(f.plan_id) && !identity(f.plan_id, 100)) throw Error('Invalid plan ID.');
    if (!optional(f.order_id) && !identity(f.order_id, 160)) throw Error('Invalid order ID.');
    var out = { id: '', execution_id: f.execution_id, symbol: s, side: side, qty: qty, price: price, executed_at: executed, fees: fees, initial_stop: side === 'buy' ? stop : null, source: f.source, environment: f.environment, account_id: f.account_id, plan_id: optional(f.plan_id) ? null : f.plan_id, order_id: optional(f.order_id) ? null : f.order_id };
    out.id = 'fill-' + digest(fillIdentity(out));
    if (f.id !== undefined && f.id !== out.id) throw Error('Execution identity does not match its stored ID.');
    return out;
  }
  function normalPlan(p, now, id) {
    if (!obj(p) || !symbol(p.symbol) || !date(p.snapshot_date) || p.snapshot_date > new Date(now).toISOString().slice(0, 10)) throw Error('A plan needs a symbol and valid setup snapshot date.');
    var size = calculate(p); if (!size.ok) throw Error(size.error);
    var qty = optional(p.qty) ? size.qty : num(p.qty);
    if (!Number.isSafeInteger(qty) || qty < 0 || qty > size.qty) throw Error('Plan quantity cannot exceed its risk and cash limits.');
    var status = p.status || 'draft';
    if (['draft', 'prepared', 'submitted', 'canceled'].indexOf(status) < 0) throw Error('Unknown plan status.');
    if ((status === 'prepared' || status === 'submitted') && qty < 1) throw Error('A prepared plan needs at least one share.');
    if (!identity(id, 100)) throw Error('Invalid plan ID.');
    if (!optional(p.order_id) && !identity(p.order_id, 160)) throw Error('Invalid broker order ID.');
    if (!optional(p.account_id) && !identity(p.account_id, 100)) throw Error('Invalid plan account ID.');
    if (!optional(p.environment) && ['paper', 'live'].indexOf(p.environment) < 0) throw Error('Invalid plan environment.');
    if (status === 'submitted' && (optional(p.order_id) || optional(p.account_id) || optional(p.environment))) throw Error('A submitted plan needs the broker’s order, account and environment identifiers.');
    var profile = validateProfile(p);
    return { id: id, symbol: symbol(p.symbol), snapshot_date: p.snapshot_date, entry: size.entry, stop: size.stop, risk_percent: profile.risk_percent, capital: profile.capital, cash_cap: size.cash_cap, qty: qty, planned_risk: qty * (size.entry - size.stop), status: status, created_at: timestamp(p.created_at) || new Date(now).toISOString(), order_id: optional(p.order_id) ? null : p.order_id, account_id: optional(p.account_id) ? null : p.account_id, environment: optional(p.environment) ? null : p.environment };
  }
  function parseCSV(textValue) {
    if (typeof textValue !== 'string' || textValue.length > MAX_BYTES) throw Error('CSV is too large.');
    var input = textValue.replace(/^\uFEFF/, ''), rows = [], row = [], value = '', quoted = false, afterQuote = false, cellStart = true;
    for (var i = 0; i < input.length; i++) {
      var c = input[i];
      if (quoted) { if (c === '"') { if (input[i + 1] === '"') { value += '"'; i++; } else { quoted = false; afterQuote = true; } } else value += c; continue; }
      if (c === '"') { if (!cellStart || afterQuote) throw Error('CSV contains a quote inside an unquoted field.'); quoted = true; cellStart = false; continue; }
      if (c === ',' || c === '\n' || c === '\r') {
        row.push(value); value = ''; cellStart = true; afterQuote = false;
        if (c !== ',') { if (c === '\r' && input[i + 1] === '\n') i++; if (row.some(function (v) { return v !== ''; })) rows.push(row); row = []; }
        continue;
      }
      if (afterQuote) throw Error('CSV contains characters after a closing quote.');
      value += c; cellStart = false;
    }
    if (quoted) throw Error('CSV contains an unclosed quoted field.');
    if (row.length || value !== '' || afterQuote) { row.push(value); rows.push(row); }
    return rows;
  }
  function csvCell(v) { if (v === null || v === undefined) return ''; var s = String(v); return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; }
  function normalSnapshot(p, now) {
    if (!obj(p) || typeof p.incomplete !== 'boolean' || !identity(p.account_id, 100) || p.source !== 'alpaca' || ['paper', 'live'].indexOf(p.environment) < 0 || !timestamp(p.as_of)) throw Error('Broker snapshot identity or timestamp is invalid.');
    var fields = ['cash', 'equity', 'buying_power'], out = { source: 'alpaca', account_id: p.account_id, environment: p.environment, as_of: timestamp(p.as_of), incomplete: p.incomplete === true, unresolved: [], positions: [] };
    if (Date.parse(out.as_of) > now + 300000) throw Error('Broker snapshot time is in the future.');
    fields.forEach(function (k) { out[k] = optional(p[k]) ? null : num(p[k]); if (out[k] !== null && !finite(out[k])) throw Error('Invalid broker account balance.'); });
    if (!Array.isArray(p.positions) || p.positions.length > 2000 || !Array.isArray(p.unresolved) || p.unresolved.length > 5000) throw Error('Invalid broker snapshot positions.');
    out.unresolved = p.unresolved.map(function (v) { return typeof v === 'string' ? v.slice(0, 1000) : JSON.stringify(v).slice(0, 1000); });
    out.positions = p.positions.map(function (r) {
      var qty = num(r.qty), average = num(r.avg_entry_price), market = optional(r.market_value) ? null : num(r.market_value), price = optional(r.current_price) ? null : num(r.current_price);
      if (!symbol(r.symbol) || !finite(qty) || !finite(average) || average <= 0 || market !== null && !finite(market) || price !== null && (!finite(price) || price <= 0)) throw Error('Invalid broker position values.');
      return { symbol: symbol(r.symbol), qty: qty, avg_entry_price: average, market_value: market, current_price: price };
    });
    return out;
  }
  function deriveState(state) {
    var linked = new Map((state.links || []).map(function (l) { return [l.fill_id, l]; }));
    var buckets = new Map(), closed = [], reconciliation = [], ignored = new Set(state.voids.map(function (v) { return v.fill_id; }));
    state.fills.map(function (f, i) { return { f: f, i: i }; }).filter(function (x) { return !ignored.has(x.f.id); }).sort(function (a, b) { return a.f.executed_at.localeCompare(b.f.executed_at) || a.i - b.i; }).forEach(function (x) {
      var f = x.f, key = bucketKey(f), b = buckets.get(key), link = linked.get(f.id);
      if (!b) { b = { key: key, symbol: f.symbol, source: f.source, environment: f.environment, account_id: f.account_id, lots: [], uncertain: false }; buckets.set(key, b); }
      if (f.side === 'buy') { b.lots.push({ fill_id: f.id, qty: f.qty, original_qty: f.qty, price: f.price, initial_stop: f.initial_stop === null && link ? link.initial_stop : f.initial_stop, fees: f.fees, executed_at: f.executed_at, plan_id: f.plan_id || (link ? link.plan_id : null) }); return; }
      var remaining = f.qty;
      while (remaining > 1e-9 && b.lots.length) {
        var lot = b.lots[0], used = Math.min(remaining, lot.qty), gross = (f.price - lot.price) * used;
        var risk = lot.initial_stop === null ? null : (lot.price - lot.initial_stop) * used;
        var fees = lot.fees === null || f.fees === null ? null : lot.fees * used / lot.original_qty + f.fees * used / f.qty;
        closed.push({ key: key, symbol: f.symbol, qty: used, entry: lot.price, exit: f.price, profit: gross, net_profit: fees === null ? null : gross - fees, fees: fees, initial_risk: risk, r: risk === null || risk <= 0 ? null : gross / risk, net_r: risk === null || risk <= 0 || fees === null ? null : (gross - fees) / risk, entered_at: lot.executed_at, exited_at: f.executed_at, buy_fill_id: lot.fill_id, sell_fill_id: f.id, plan_id: lot.plan_id, source: f.source, environment: f.environment, account_id: f.account_id, reconciled: true });
        lot.qty -= used; remaining -= used; if (lot.qty < 1e-9) b.lots.shift();
      }
      if (remaining > 1e-9) { b.uncertain = true; reconciliation.push({ key: key, symbol: f.symbol, source: f.source, environment: f.environment, account_id: f.account_id, qty: remaining, fill_id: f.id, reason: 'Sell exceeds recorded earlier buys. Import missing history or reconcile transfers/splits before using performance.' }); }
    });
    var brokerPositions = [];
    state.broker_snapshots.forEach(function (s) {
      var prefix = [s.source, s.environment, s.account_id].join('|') + '|';
      if (s.incomplete || s.unresolved.length) {
        reconciliation.push({ key: prefix, symbol: null, source: s.source, environment: s.environment, account_id: s.account_id, qty: null, reason: 'Broker execution history is incomplete or has unresolved activity. Broker holdings are shown separately; performance needs reconciliation.' });
        buckets.forEach(function (b) { if (b.key.indexOf(prefix) === 0) b.uncertain = true; });
      }
      var brokerSymbols = new Set();
      s.positions.forEach(function (p) {
        brokerSymbols.add(p.symbol); var b = buckets.get(prefix + p.symbol), qty = b ? b.lots.reduce(function (a, l) { return a + l.qty; }, 0) : 0;
        brokerPositions.push(Object.assign({ source: s.source, environment: s.environment, account_id: s.account_id, as_of: s.as_of }, p));
        if (Math.abs(qty - p.qty) > 1e-7) { if (b) b.uncertain = true; reconciliation.push({ key: prefix + p.symbol, symbol: p.symbol, source: s.source, environment: s.environment, account_id: s.account_id, qty: p.qty - qty, reason: 'Broker holding differs from recorded executions. Missing history, a transfer or a split needs reconciliation.' }); }
      });
      buckets.forEach(function (b) { if (b.key.indexOf(prefix) !== 0 || brokerSymbols.has(b.symbol)) return; var qty = b.lots.reduce(function (a, l) { return a + l.qty; }, 0); if (qty > 1e-9) { b.uncertain = true; reconciliation.push({ key: b.key, symbol: b.symbol, source: b.source, environment: b.environment, account_id: b.account_id, qty: -qty, reason: 'Recorded executions show a holding absent from this broker snapshot. Refresh and reconcile before using performance.' }); } });
    });
    // Manual confirmations can describe an execution later returned by the broker.
    // Keep both provenance records, but require the manual copy to be corrected
    // before treating a likely duplicate as additional exposure or performance.
    var activeFills = state.fills.filter(function (f) { return !ignored.has(f.id); });
    var brokerMatches = new Map();
    activeFills.filter(function (f) { return f.source === 'alpaca'; }).forEach(function (f) { var k = [f.environment, f.symbol, f.side, f.qty, f.price].join('|'); if (!brokerMatches.has(k)) brokerMatches.set(k, []); brokerMatches.get(k).push(f); });
    activeFills.filter(function (f) { return f.source === 'manual'; }).forEach(function (f) {
      var matches = brokerMatches.get([f.environment, f.symbol, f.side, f.qty, f.price].join('|')) || [];
      var match = matches.find(function (v) { return Math.abs(Date.parse(v.executed_at) - Date.parse(f.executed_at)) <= 60000; });
      if (match) { buckets.get(bucketKey(f)).uncertain = true; buckets.get(bucketKey(match)).uncertain = true; reconciliation.push({ key: bucketKey(f), symbol: f.symbol, source: f.source, environment: f.environment, account_id: f.account_id, qty: f.qty, fill_id: f.id, reason: 'A manual execution resembles a synced broker execution. Check both records and correct the manual duplicate if they describe the same fill.' }); }
    });
    closed.forEach(function (c) { if (buckets.get(c.key).uncertain) { c.reconciled = false; c.profit = null; c.net_profit = null; c.r = null; c.net_r = null; } });
    var positions = [];
    buckets.forEach(function (b) { var qty = 0, cost = 0, risk = 0, known = true; b.lots.forEach(function (l) { qty += l.qty; cost += l.qty * l.price; if (l.initial_stop === null) known = false; else risk += l.qty * (l.price - l.initial_stop); }); if (qty > 1e-9) positions.push(Object.assign({}, b, { qty: qty, cost_basis: cost, average_entry: cost / qty, initial_risk: known ? risk : null, opened_at: b.lots[0].executed_at, lots: clone(b.lots) })); });
    var totals = {};
    ['live', 'paper'].forEach(function (env) {
      var ps = positions.filter(function (p) { return p.environment === env; }), cs = closed.filter(function (c) { return c.environment === env; });
      var unresolved = reconciliation.some(function (r) { return r.environment === env; });
      totals[env] = { open_cost: unresolved ? null : ps.reduce(function (a, p) { return a + p.cost_basis; }, 0), open_positions: ps.length, initial_risk: unresolved || ps.some(function (p) { return p.initial_risk === null || p.uncertain; }) ? null : ps.reduce(function (a, p) { return a + p.initial_risk; }, 0), realized_gross: unresolved ? null : cs.reduce(function (a, c) { return a + c.profit; }, 0), realized_net: unresolved || cs.some(function (c) { return c.net_profit === null; }) ? null : cs.reduce(function (a, c) { return a + c.net_profit; }, 0), reconciliation_required: unresolved, valuation: 'recorded_entry_cost' };
    });
    return { positions: positions, closed: closed, reconciliation: reconciliation, totals: totals, broker_positions: brokerPositions, broker_snapshots: clone(state.broker_snapshots) };
  }
  function createStore(options) {
    options = options || {}; var storage = options.storage, clock = options.clock || Date.now, state = empty(), loaded = false, persistent = true, reason = '', lastRaw = null, subscribers = [], previews = new Map(), seq = 0;
    if (storage === undefined) { try { storage = root && root.localStorage; } catch (_) { storage = null; } }
    function uid(prefix) { seq++; return prefix + '-' + clock().toString(36) + '-' + seq.toString(36) + '-' + Math.random().toString(36).slice(2, 10); }
    function notify() { var snapshot = clone(state); subscribers.forEach(function (fn) { try { fn(snapshot, getStorageStatus()); } catch (_) {} }); }
    function getStorageStatus() { return { persistent: persistent, temporary: !persistent, reason: reason }; }
    function validateState(value) {
      if (!obj(value) || value.version !== 2 || !Number.isSafeInteger(value.revision) || value.revision < 0 || !Array.isArray(value.plans) || value.plans.length > MAX_PLANS || !Array.isArray(value.fills) || value.fills.length > MAX_FILLS || !Array.isArray(value.voids) || value.voids.length > MAX_FILLS || !Array.isArray(value.broker_snapshots) || value.broker_snapshots.length > 20) throw Error('Backup is not a supported version 2 trade ledger.');
      var out = empty(); out.revision = value.revision; out.profile = validateProfile(value.profile);
      var ids = new Set(); out.plans = value.plans.map(function (p) { if (!obj(p) || !timestamp(p.created_at) || Date.parse(p.created_at) > clock() + 300000) throw Error('Invalid plan creation time.'); var n = normalPlan(p, clock(), p.id); if (ids.has(n.id)) throw Error('Duplicate plan ID.'); ids.add(n.id); return n; });
      ids = new Set(); out.fills = value.fills.map(function (f) { var n = normalFill(f, clock(), false); if (ids.has(n.id)) throw Error('Duplicate execution ID.'); ids.add(n.id); return n; });
      var fillMap = new Map(out.fills.map(function (f) { return [f.id, f]; })); var voided = new Set();
      out.voids = value.voids.map(function (v) { if (!obj(v) || !text(v.id, 100) || !text(v.reason, 500) || !timestamp(v.voided_at) || Date.parse(v.voided_at) > clock() + 300000 || !fillMap.has(v.fill_id) || fillMap.get(v.fill_id).source !== 'manual' || voided.has(v.fill_id)) throw Error('Invalid execution correction.'); voided.add(v.fill_id); return { id: v.id, fill_id: v.fill_id, reason: v.reason, voided_at: timestamp(v.voided_at) }; });
      if (value.links !== undefined && (!Array.isArray(value.links) || value.links.length > MAX_FILLS)) throw Error('Invalid execution links.');
      var planMap = new Map(out.plans.map(function (p) { return [p.id, p]; })); ids = new Set();
      out.links = (value.links || []).map(function (l) {
        var f = obj(l) && fillMap.get(l.fill_id), p = obj(l) && planMap.get(l.plan_id);
        if (!f || !p || f.side !== 'buy' || f.symbol !== p.symbol || f.initial_stop !== null || !finite(l.initial_stop) || l.initial_stop !== p.stop || l.initial_stop >= f.price || !timestamp(l.linked_at) || Date.parse(l.linked_at) > clock() + 300000 || ids.has(l.fill_id) || p.environment && p.environment !== f.environment || p.account_id && p.account_id !== f.account_id) throw Error('Invalid execution-to-plan link.');
        ids.add(l.fill_id); return { fill_id: l.fill_id, plan_id: l.plan_id, initial_stop: l.initial_stop, linked_at: timestamp(l.linked_at) };
      });
      ids = new Set(); out.broker_snapshots = value.broker_snapshots.map(function (s) { var n = normalSnapshot(s, clock()), k = n.source + '|' + n.environment + '|' + n.account_id; if (ids.has(k)) throw Error('Duplicate broker snapshot.'); ids.add(k); return n; });
      return out;
    }
    function load() {
      if (loaded) return clone(state); loaded = true;
      try { if (!storage) throw Error('Browser storage is unavailable.'); lastRaw = storage.getItem(KEY); if (lastRaw !== null) { if (lastRaw.length > MAX_BYTES) throw Error('Saved ledger exceeds the supported size.'); state = validateState(JSON.parse(lastRaw)); } }
      catch (_) { persistent = false; reason = 'Temporary mode: saved trade data could not be read or storage is blocked. The stored copy will not be overwritten. Export this visit’s changes.'; }
      return clone(state);
    }
    function getState() { if (!loaded) load(); return clone(state); }
    function result(extra) { return Object.assign({ ok: true, state: clone(state), temporary: !persistent, warning: persistent ? null : reason }, extra || {}); }
    function failure(e) { return { ok: false, error: e && e.message || String(e), temporary: !persistent, warning: persistent ? null : reason }; }
    function commit(next, extra) {
      next.revision = state.revision + 1; var raw = JSON.stringify(next);
      if (raw.length > MAX_BYTES) return failure(Error('Trade data is too large. Export a backup before adding more.'));
      if (persistent) { try { if (!storage || storage.getItem(KEY) !== lastRaw) throw Error('Another tab changed saved data.'); storage.setItem(KEY, raw); lastRaw = raw; } catch (_) { persistent = false; reason = 'Temporary mode: storage is full, blocked, or changed in another tab. This visit’s edits are kept in memory; the stored copy is preserved. Export before closing.'; } }
      state = next; previews.clear(); notify(); return result(extra);
    }
    function mutate(fn) { getState(); try { var next = clone(state), extra = fn(next); return commit(next, extra); } catch (e) { return failure(e); } }
    function mergeFills(next, rows) {
      var existing = new Map(next.fills.map(function (f) { return [f.id, f]; })), added = 0, duplicates = 0;
      rows.forEach(function (f) { if (existing.has(f.id)) { if (!equal(existing.get(f.id), f)) throw Error('Execution ID collision: ' + f.execution_id + ' has different values. Nothing was imported.'); duplicates++; } else { existing.set(f.id, f); next.fills.push(f); added++; } });
      if (next.fills.length > MAX_FILLS) throw Error('Ledger limit is 5,000 executions. Export your records before importing more.');
      return { added: added, duplicates: duplicates };
    }
    function savePlan(plan) {
      return mutate(function (next) { var id = plan && plan.id || uid('plan'), previous = next.plans.find(function (p) { return p.id === id; }); var p = normalPlan(Object.assign({}, plan, previous ? { created_at: previous.created_at } : {}), clock(), id);
        if (previous && (previous.status === 'submitted' || next.links.some(function (l) { return l.plan_id === id; }) || next.fills.some(function (f) { return f.plan_id === id; }))) { var a = Object.assign({}, previous, { status: p.status }), b = Object.assign({}, p); if (!equal(a, b) || ['submitted', 'canceled'].indexOf(p.status) < 0) throw Error('Submitted plan values are frozen. Create a new plan to change the trade.'); }
        if (previous && previous.status === 'canceled' && p.status !== 'canceled') throw Error('A canceled plan cannot be reopened. Create a new plan.');
        if (previous) next.plans[next.plans.indexOf(previous)] = p; else { if (next.plans.length >= MAX_PLANS) throw Error('Plan limit reached. Export a backup.'); next.plans.push(p); } return { plan: clone(p) }; });
    }
    function recordFill(fill) {
      return mutate(function (next) { if (!fill || fill.confirmed !== true) throw Error('Confirm the symbol, side, quantity, actual price and execution time before recording.'); if (fill.source && fill.source !== 'manual') throw Error('Broker executions must come through broker sync or a reviewed import.');
        var f = normalFill(Object.assign({ source: 'manual', account_id: 'local', execution_id: uid('manual') }, fill), clock(), false);
        var old = deriveState(next), info = mergeFills(next, [f]);
        var derived = deriveState(next), oldUnmatched = old.reconciliation.filter(function (r) { return r.fill_id && r.reason.indexOf('Sell exceeds') === 0; }).map(function (r) { return r.fill_id + ':' + r.qty; });
        if (derived.reconciliation.some(function (r) { return r.fill_id === f.id && r.reason.indexOf('A manual execution resembles') === 0; })) throw Error('This resembles an execution already synced from the broker. Check that record before adding a manual duplicate.');
        if (derived.reconciliation.some(function (r) { return r.fill_id && r.reason.indexOf('Sell exceeds') === 0 && oldUnmatched.indexOf(r.fill_id + ':' + r.qty) < 0; })) throw Error('This sell exceeds recorded earlier buys. Import or reconcile the missing history first.');
        return Object.assign({ fill: clone(f) }, info); });
    }
    function voidFill(id, confirmation) { return mutate(function (next) { var f = next.fills.find(function (v) { return v.id === id; }); if (!f || f.source !== 'manual') throw Error('Only a manually recorded execution can be corrected here.'); if (!confirmation || confirmation.confirmed !== true || !text(confirmation.reason, 500)) throw Error('Confirm the correction and provide its reason.'); if (next.voids.some(function (v) { return v.fill_id === id; })) throw Error('This execution was already marked as corrected.'); next.voids.push({ id: uid('void'), fill_id: id, reason: confirmation.reason, voided_at: new Date(clock()).toISOString() }); return { voided: id }; }); }
    function previewImport(input, format) {
      getState(); previews.clear(); var errors = [], warnings = [], rows = [], plans = [], voids = [], links = [], snapshots = [];
      try {
        if (typeof input !== 'string' || input.length > MAX_BYTES) throw Error('Import must be text smaller than 8 MB.');
        if (format === 'csv') {
          var parsed = parseCSV(input); if (!parsed.length || !equal(parsed[0], CSV_COLUMNS)) throw Error('CSV header must be exactly: ' + CSV_COLUMNS.join(','));
          if (parsed.length > MAX_FILLS + 1) throw Error('CSV exceeds 5,000 executions.');
          parsed.slice(1).forEach(function (values, i) { try { if (values.length !== CSV_COLUMNS.length) throw Error('Wrong number of columns.'); var f = {}; CSV_COLUMNS.forEach(function (k, j) { f[k] = values[j]; }); rows.push(normalFill(f, clock(), false)); } catch (e) { errors.push('Row ' + (i + 2) + ': ' + e.message); } });
        } else if (format === 'json') { var imported = validateState(JSON.parse(input)); rows = imported.fills; plans = imported.plans; voids = imported.voids; links = imported.links; snapshots = imported.broker_snapshots; warnings.push('Backups merge executions and plans by ID. Conflicting IDs stop the entire import. Current profile settings and newer broker snapshots are retained. Missing broker snapshots are restored with their original timestamps.'); }
        else if (format === 'legacy') {
          var legacy = JSON.parse(input); if (!obj(legacy) || legacy.version !== 1 || !Array.isArray(legacy.records) || legacy.records.length > 100) throw Error('Not a supported legacy journal.');
          legacy.records.forEach(function (r, i) {
            if (!obj(r) || !text(r.id, 80) || !symbol(r.ticker) || !date(r.date) || ['paper', 'open', 'closed'].indexOf(r.status) < 0 || !finite(r.entry) || !finite(r.stop) || !Number.isSafeInteger(r.shares) || r.shares < 1 || r.entry <= r.stop || r.stop <= 0) throw Error('Legacy record ' + (i + 1) + ' is invalid.');
            var planId = 'legacy-plan-' + digest(r.id);
            var p = normalPlan({ symbol: r.ticker, snapshot_date: r.date, entry: r.entry, stop: r.stop, capital: r.entry * r.shares, risk_percent: (r.entry - r.stop) / r.entry * 100, cash_cap: r.entry * r.shares, qty: r.shares, status: 'draft' }, clock(), planId);
            plans.push(p);
          });
          warnings.push('Legacy journal records contain dates, not confirmed execution timestamps. They import as draft plans only. No purchases or profits are invented; confirm actual fills separately.');
        } else throw Error('Choose csv, json or legacy format.');
        var next = clone(state), counts = mergeFills(next, rows);
        var existingPlans = new Map(next.plans.map(function (p) { return [p.id, p]; }));
        plans.forEach(function (p) { if (existingPlans.has(p.id) && !equal(existingPlans.get(p.id), p)) throw Error('Plan ID collision: ' + p.id + '. Nothing was imported.'); existingPlans.set(p.id, p); });
        if (existingPlans.size > MAX_PLANS) throw Error('Plan limit exceeded.'); next.plans = Array.from(existingPlans.values());
        var existingVoids = new Map(next.voids.map(function (v) { return [v.fill_id, v]; }));
        voids.forEach(function (v) { if (existingVoids.has(v.fill_id) && !equal(existingVoids.get(v.fill_id), v)) throw Error('Correction collision. Nothing was imported.'); existingVoids.set(v.fill_id, v); }); next.voids = Array.from(existingVoids.values());
        var existingLinks = new Map(next.links.map(function (l) { return [l.fill_id, l]; }));
        links.forEach(function (l) { if (existingLinks.has(l.fill_id) && !equal(existingLinks.get(l.fill_id), l)) throw Error('Execution-to-plan link collision. Nothing was imported.'); existingLinks.set(l.fill_id, l); }); next.links = Array.from(existingLinks.values());
        // Restored observations keep their original age and incomplete-history flags.
        snapshots.forEach(function (s) { if (!next.broker_snapshots.some(function (v) { return v.account_id === s.account_id && v.environment === s.environment && v.source === s.source; })) next.broker_snapshots.push(s); });
        validateState(next);
        var after = deriveState(next); if (after.reconciliation.length) warnings.push('Reconciliation required: ' + after.reconciliation.length + ' history or broker holding issue(s). Affected performance stays unavailable.');
        if (rows.some(function (r) { return r.fees === null; })) warnings.push('Some fees are unknown. Gross results exclude fees; net results remain unavailable for those trades.');
        if (rows.some(function (r) { return r.source === 'alpaca'; })) warnings.push('CSV/backup broker provenance is supplied by the file. Only a connected broker refresh verifies current holdings.');
        var id = uid('preview'), preview = { ok: errors.length === 0, id: id, format: format, errors: errors, warnings: warnings, rows: clone(rows), counts: { fills: counts.added, plans: next.plans.length - state.plans.length, duplicates: counts.duplicates } };
        if (preview.ok) previews.set(id, { revision: state.revision, next: next, digest: digest(JSON.stringify(preview)), counts: preview.counts });
        return preview;
      } catch (e) { errors.push(e.message); return { ok: false, id: null, format: format, errors: errors, warnings: warnings, rows: clone(rows), counts: { fills: 0, plans: 0, duplicates: 0 } }; }
    }
    function commitImport(preview) {
      getState(); try { var pending = preview && previews.get(preview.id); if (!pending || pending.revision !== state.revision || digest(JSON.stringify(preview)) !== pending.digest) throw Error('Import preview expired or changed. Preview the file again before importing.'); return commit(pending.next, { added: pending.counts.fills, plans_added: pending.counts.plans, duplicates: pending.counts.duplicates }); } catch (e) { return failure(e); }
    }
    function ingestBroker(portfolio) {
      return mutate(function (next) {
        if (!obj(portfolio) || !obj(portfolio.account) || !identity(portfolio.account.id, 100) || ['paper', 'live'].indexOf(portfolio.mode) < 0 || !Array.isArray(portfolio.fills) || !Array.isArray(portfolio.positions) || portfolio.fills.length > MAX_FILLS) throw Error('Broker portfolio is missing its account, environment or execution list.');
        var account = portfolio.account.id, env = portfolio.mode;
        var fills = portfolio.fills.map(function (f) {
          if (f.source !== 'alpaca' || f.mode && f.mode !== env || f.account_id && f.account_id !== account) throw Error('Broker execution account or environment does not match this portfolio.');
          var mapped = { execution_id: f.id, symbol: f.symbol, side: f.side, qty: f.qty, price: f.price, executed_at: f.transaction_time, fees: f.fees, initial_stop: null, source: 'alpaca', environment: env, account_id: account, order_id: f.order_id };
          var old = next.fills.find(function (r) { return fillIdentity(r) === fillIdentity(mapped); }); if (old) { mapped.initial_stop = old.initial_stop; mapped.plan_id = old.plan_id; }
          return normalFill(mapped, clock(), false);
        });
        var info = mergeFills(next, fills);
        fills.forEach(function (f) {
          if (f.side !== 'buy' || f.initial_stop !== null || next.links.some(function (l) { return l.fill_id === f.id; })) return;
          var plan = next.plans.find(function (p) { return p.order_id && p.order_id === f.order_id && p.symbol === f.symbol && p.account_id === account && p.environment === env && p.stop < f.price; });
          if (plan) next.links.push({ fill_id: f.id, plan_id: plan.id, initial_stop: plan.stop, linked_at: new Date(clock()).toISOString() });
        });
        var snapshot = normalSnapshot({ source: 'alpaca', account_id: account, environment: env, as_of: portfolio.as_of || portfolio.fetched_at || portfolio.synced_at, cash: portfolio.account.cash, equity: portfolio.account.equity, buying_power: portfolio.account.buying_power, positions: portfolio.positions, incomplete: portfolio.fills_truncated === true || portfolio.fills_complete_since === null, unresolved: portfolio.unresolved || [] }, clock());
        var at = next.broker_snapshots.findIndex(function (s) { return s.source === 'alpaca' && s.environment === env && s.account_id === account; });
        if (at >= 0) { if (next.broker_snapshots[at].as_of > snapshot.as_of) throw Error('This broker response is older than the last saved snapshot. Refresh again.'); next.broker_snapshots[at] = snapshot; } else { if (next.broker_snapshots.length >= 20) throw Error('Broker account limit reached.'); next.broker_snapshots.push(snapshot); }
        return info;
      });
    }
    function linkFillToPlan(fillId, planId, confirmation) {
      return mutate(function (next) {
        var f = next.fills.find(function (v) { return v.id === fillId; }), p = next.plans.find(function (v) { return v.id === planId; });
        if (!confirmation || confirmation.confirmed !== true) throw Error('Confirm that this plan’s original stop belongs to the actual execution.');
        if (!f || !p || f.side !== 'buy' || f.symbol !== p.symbol || f.initial_stop !== null || next.links.some(function (l) { return l.fill_id === fillId; }) || p.stop >= f.price || p.environment && p.environment !== f.environment || p.account_id && p.account_id !== f.account_id) throw Error('This execution cannot be linked to that plan. Check symbol, account, environment and original stop.');
        next.links.push({ fill_id: fillId, plan_id: planId, initial_stop: p.stop, linked_at: new Date(clock()).toISOString() });
        return { linked: fillId };
      });
    }
    function exportJSON() { return JSON.stringify(getState(), null, 2); }
    function exportCSV() { getState(); var active = new Set(state.voids.map(function (v) { return v.fill_id; })); return [CSV_COLUMNS.join(',')].concat(state.fills.filter(function (f) { return !active.has(f.id); }).map(function (f) { return CSV_COLUMNS.map(function (k) { return csvCell(f[k]); }).join(','); })).join('\r\n') + '\r\n'; }
    function previewLegacy() { try { if (!storage) throw Error('Browser storage is unavailable.'); var raw = storage.getItem(LEGACY_KEY); if (!raw) throw Error('No legacy journal was found in this browser.'); return previewImport(raw, 'legacy'); } catch (e) { return { ok: false, errors: [e.message], warnings: [], rows: [], counts: { fills: 0, plans: 0, duplicates: 0 } }; } }
    function externalChange(event) { if (event && event.key === KEY && loaded && event.newValue !== lastRaw) { persistent = false; reason = 'Temporary mode: another tab changed the saved trade ledger. Your current view is preserved. Export unsaved work and reload to use the newer copy.'; previews.clear(); notify(); } }
    if (root && root.addEventListener && options.listen !== false) root.addEventListener('storage', externalChange);
    return { key: KEY, csvColumns: CSV_COLUMNS.slice(), load: load, getState: getState, getStorageStatus: getStorageStatus, subscribe: function (fn) { if (typeof fn !== 'function') return function () {}; subscribers.push(fn); return function () { subscribers = subscribers.filter(function (f) { return f !== fn; }); }; }, setProfile: function (p) { return mutate(function (next) { next.profile = validateProfile(p); }); }, savePlan: savePlan, recordFill: recordFill, voidFill: voidFill, linkFillToPlan: linkFillToPlan, previewImport: previewImport, commitImport: commitImport, previewLegacy: previewLegacy, ingestBroker: ingestBroker, derive: function () { getState(); return deriveState(state); }, calculate: calculate, exportJSON: exportJSON, exportCSV: exportCSV, parseCSV: parseCSV, dispose: function () { if (root && root.removeEventListener) root.removeEventListener('storage', externalChange); subscribers = []; } };
  }
  var api = createStore(); api.createStore = createStore; return api;
}));
