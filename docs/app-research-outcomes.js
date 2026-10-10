/* Optional frozen-cohort follow-through. Public evidence only; no order or private result authority. */
(function (w) {
  'use strict';
  const api = w.SCStock = w.SCStock || {}, d = w.document;
  const RECEIPT_BYTES = 16 * 1024, BUNDLE_BYTES = 2 * 1024 * 1024, TIMEOUT_MS = 15000;
  const HEX = /^[a-f0-9]{64}$/;
  const POLICY = {"version":1,"id":"anticipation_stop_width_follow_through_v1","cohort_policy_id":"anticipation_stop_width_4_to_5_v1","horizon_sessions":5,"observation_price_decimals":4,"population":"frozen_allocation_fit_only","primary":"first_actual_before_entry_per_applicable_session","basis":"same_provider_feed_adjustment_daily_and_fresh_matching_anchor","replay_rules":{"version":1,"fill":"open_inside_zone","same_bar":"stop_first","whole_shares":"ceil_half","r":"original_stop_weighted_complete_sales_v1","plan":{"sell_half_pct":8.0,"abnormal_day_pct":10.0,"gap_exit_pct":20.0,"trail_cents":0.25,"sell_half_day":3,"no_progress_day":3,"trail_from_day":3,"final_exit_day":5,"entry_day":1,"precision.cents":2,"precision.pct_decimals":2},"record":{"open_plan_sessions":5,"known_fill":"open_inside_zone"},"calendar":{"version":1,"exchange":"XNYS","library":"exchange_calendars","library_version":"4.13.2","timezone":"America/New_York","completion_buffer_minutes":15}},"costs":"unspecified_actual_fees_and_slippage_excluded","aggregation":"counts_only_no_portfolio_performance"};
  const LIMITS = ["conditional_daily_bar_model_not_actual_execution","no_orders_or_personal_results","no_new_provider_or_model_calls","first_30_minutes_and_intraday_order_unknown","known_open_fill_uses_stop_first_daily_bar_convention","whole_share_model_exits","actual_fees_and_slippage_unspecified","no_cross_cohort_portfolio_reservations","retained_observation_coverage_may_be_missing","revisions_do_not_rewrite_prior_snapshots"];
  const STATUSES = ["pending","missing","uncertain","not_filled","open","resolved","excluded","origin_unavailable","basis_conflict","unsupported","unreadable"];
  const EVENTS = ["abnormal_day","day5_exit","gap_exit","no_progress","not_filled","sell_half","stop_raised","stop_raised_to_entry_low","stop_trailed","stopped","stopped_at_open","uncertain"];
  const SOURCE_POLICY = {"version":1,"id":"anticipation_stop_width_4_to_5_v1","applicable_start":"2026-10-12","applicable_end":"2026-11-06","baseline_stop_pct":4.0,"research_stop_pct":5.0,"account":{"equity":2000,"risk_pct":0.5,"max_position_pct":25,"max_open_positions":4},"allocation":"baseline_first_then_original_watchlist_rank","geometry":"unchanged_anticipation_trigger_limit_structural_stop","review":"existing_anticipation_policy_no_new_chart_review"};
  const SOURCE_LIMITS = ["research_only_no_orders","manual_known_events_not_news_clearance","no_new_chart_review","no_live_quote_or_earnings_check","principal_excludes_actual_fees","price_to_stop_risk_excludes_gaps_slippage","model_reservations_not_broker_cash","no_returns_or_strategy_edge_established"];
  const COMMON = 'schema_version policy publication generated_at cohort_set_sha256 counts';
  const object = x => !!x && typeof x === 'object' && !Array.isArray(x);
  const require = (ok, why) => { if (!ok) throw Error(why); };
  const canonical = x => Array.isArray(x) ? x.map(canonical) : object(x) ? Object.fromEntries(Object.keys(x).sort().map(k => [k, canonical(x[k])])) : x;
  const equal = (a, b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
  const keys = (x, names) => object(x) && equal(Object.keys(x).sort(), names.split(' ').sort());
  const integer = (x, max = Number.MAX_SAFE_INTEGER) => Number.isSafeInteger(x) && x >= 0 && x <= max;
  const finite = x => typeof x === 'number' && Number.isFinite(x);
  const text = (x, max = 4096) => typeof x === 'string' && x.length > 0 && x.length <= max;
  const day = x => typeof x === 'string' && /^\d{4}-\d\d-\d\d$/.test(x) && Number.isFinite(Date.parse(x)) && new Date(x).toISOString().slice(0, 10) === x;
  const instant = x => {
    const match = typeof x === 'string' && /^(\d{4}-\d\d-\d\d)T(\d\d):(\d\d):(\d\d)(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)$/.exec(x);
    return match && day(match[1]) && Number(match[2]) < 24 && Number(match[3]) < 60 && Number(match[4]) < 60 ? Date.parse(x) : NaN;
  };
  const clock = () => api.now ? new Date(api.now).getTime() : Date.now();
  const stamp = x => Number.isFinite(instant(x)) ? new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', dateStyle: 'medium', timeStyle: 'short' }).format(new Date(x)) + ' CT' : 'Unavailable';
  const money = x => finite(x) ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: POLICY.observation_price_decimals }).format(x) : 'Unavailable';
  const fingerprint = () => api.observations ? api.observations.facts() : {};
  let mounted = null, record = null, identity = '', receipt = null, bundle = null;
  let sources = [];
  let state = 'deferred', issue = '', epoch = 0, controller = null, pending = null;

  function node(tag, attrs, value) {
    const el = d.createElement(tag);
    Object.entries(attrs || {}).forEach(([key, val]) => el.setAttribute(key, val));
    if (value !== undefined) el.textContent = value;
    return el;
  }
  function paragraph(host, label, value) {
    const p = node('p', { class: 'sc-hint' });
    p.append(node('strong', {}, label + ' '), d.createTextNode(value)); host.append(p);
  }
  async function sha(bytes) {
    require(w.crypto && w.crypto.subtle && w.TextEncoder, 'Exact publication verification is unavailable in this browser.');
    const hash = await w.crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(hash), n => n.toString(16).padStart(2, '0')).join('');
  }

  function publication(value) {
    require(keys(value, 'data_sha256 context_sha256 run_id rules_version measured_session applicable_session published_at reader_projection_version reader_sha256') &&
      ['data_sha256', 'context_sha256', 'reader_sha256'].every(k => typeof value[k] === 'string' && HEX.test(value[k])) &&
      typeof value.rules_version === 'string' && /^[a-f0-9]{12}$/.test(value.rules_version) && value.reader_projection_version === 1 &&
      (value.run_id === null || text(value.run_id, 128)) && day(value.measured_session) && day(value.applicable_session) && Number.isFinite(instant(value.published_at)),
    'A research publication reference is invalid.');
  }
  function binding(value) {
    publication(value);
    const hashes = fingerprint(), run = record && record.run || {};
    require(hashes.recordHash && value.data_sha256 === hashes.canonicalHash && (!hashes.projected || value.reader_sha256 === hashes.recordHash) &&
      value.context_sha256 === (run.evidence || {}).context_sha256 && value.rules_version === (record.app || {}).rules_version &&
      String(value.run_id) === String(run.run_id) && value.measured_session === run.session &&
      value.applicable_session === (run.timing || {}).applicable_session && value.published_at === run.published_at,
    'These observations belong to another publication. No journal has been loaded.');
  }
  const dates = value => Array.isArray(value) && value.length <= 5 && value.every(day) && equal(value, [...new Set(value)].sort());
  const basis = value => keys(value, 'provider feed adjustment timeframe') && Object.values(value).every(x => text(x, 64) && x.length) && value.timeframe === '1Day';
  function validateReceipt(value) {
    require(keys(value, COMMON + ' bundle') && value.schema_version === 1 && equal(value.policy, POLICY), 'The follow-through policy is unsupported.');
    binding(value.publication);
    require(Number.isFinite(instant(value.generated_at)) && instant(value.generated_at) <= clock() + 5000 &&
      instant(value.publication.published_at) <= instant(value.generated_at) + 5000 && typeof value.cohort_set_sha256 === 'string' && HEX.test(value.cohort_set_sha256), 'The observation snapshot identity or date is invalid.');
    const c = value.counts, ref = value.bundle;
    require(keys(c, 'cohorts primary_cohorts rows eligible by_status') && ['cohorts', 'primary_cohorts', 'rows', 'eligible'].every(k => integer(c[k], 640)) &&
      c.cohorts <= 128 && c.primary_cohorts <= c.cohorts && keys(c.by_status, STATUSES.join(' ')) && Object.values(c.by_status).every(n => integer(n, 640)) &&
      Object.values(c.by_status).reduce((a, b) => a + b, 0) === c.rows && c.eligible === c.rows - c.by_status.excluded, 'Research observation counts do not reconcile.');
    require(keys(ref, 'path sha256 bytes') && typeof ref.sha256 === 'string' && HEX.test(ref.sha256) && integer(ref.bytes, BUNDLE_BYTES) && ref.bytes > 0 &&
      ref.path === 'research-outcomes/' + ref.sha256 + '.json', 'The observation bundle path or size is invalid.');
    return value;
  }
  function validateSource(source, generated) {
    require(keys(source, 'schema_version policy publication timing status reason counts reservations rows limits') && source.schema_version === 1 &&
      equal(source.policy, SOURCE_POLICY) && equal(source.limits, SOURCE_LIMITS), 'The original cohort policy is unsupported.');
    publication(source.publication);
    const t = source.timing, p = source.publication;
    require(keys(t, 'generated_at entry_opens_at entry_cutoff_at classification') && [t.generated_at, t.entry_opens_at, t.entry_cutoff_at].every(x => Number.isFinite(instant(x))) &&
      instant(t.entry_opens_at) < instant(t.entry_cutoff_at) && instant(t.generated_at) <= generated + 5000 && instant(p.published_at) <= instant(t.generated_at) + 5000 &&
      t.classification === (instant(t.generated_at) < instant(t.entry_opens_at) ? 'before_entry' : instant(t.generated_at) < instant(t.entry_cutoff_at) ? 'during_entry' : 'after_entry'), 'The original cohort timing is invalid.');
    const inPeriod = p.applicable_session >= SOURCE_POLICY.applicable_start && p.applicable_session <= SOURCE_POLICY.applicable_end;
    require(source.status === (inPeriod ? 'recorded' : 'outside_period') && (source.reason === null || text(source.reason, 600)) &&
      Array.isArray(source.rows) && source.rows.length <= 5 && (inPeriod || !source.rows.length) && new Set(source.rows.map(row => row.ticker)).size === source.rows.length, 'The original cohort population is invalid.');
    for (const [index, row] of source.rows.entries()) {
      require(keys(row, 'rank ticker evidence in_band baseline levels research event quality') && row.rank === index + 1 && typeof row.ticker === 'string' && /^[A-Z][A-Z0-9.-]{0,14}$/.test(row.ticker) &&
        keys(row.evidence, 'id plan_sha256 source_sha256 inputs_sha256') && Object.values(row.evidence).every(x => typeof x === 'string' && HEX.test(x)) &&
        keys(row.quality, 'watchlist_eligible source_session review') && row.quality.source_session === p.measured_session && row.quality.review === 'not_required_by_anticipation', 'An original row lost its source identity.');
      const r = row.research, e = row.event;
      require(keys(r, 'mechanical_fit allocation_fit shares principal_usd risk_usd risk_per_share effective_risk_budget_usd multipliers blockers projection_sha256') &&
        typeof r.mechanical_fit === 'boolean' && typeof r.allocation_fit === 'boolean' && (r.shares === null || integer(r.shares, 1000000)) &&
        typeof r.projection_sha256 === 'string' && HEX.test(r.projection_sha256) && Array.isArray(r.blockers) && r.blockers.length <= 12 && r.blockers.every(x => text(x, 64)) &&
        keys(e, 'blocked status registry_sha256 event_ids') && typeof e.blocked === 'boolean' && typeof e.registry_sha256 === 'string' && HEX.test(e.registry_sha256) &&
        Array.isArray(e.event_ids) && e.event_ids.length <= 128 && e.event_ids.every(x => text(x, 128)), 'The original research eligibility is invalid.');
      require(!r.allocation_fit || (r.mechanical_fit && r.shares > 0 && !r.blockers.length && !e.blocked && row.quality.watchlist_eligible === true && row.in_band === true), 'A refused original row cannot acquire an outcome.');
      require(!e.blocked || r.blockers.includes('known_event'), 'An original event exclusion was removed.');
      if (row.levels !== null) {
        const l = row.levels;
        require(keys(l, 'trigger limit stop stop_pct') && Object.values(l).every(x => finite(x) && x > 0) && l.stop < l.trigger && l.trigger <= l.limit, 'The frozen research levels are invalid.');
      }
      require(!r.allocation_fit || row.levels !== null, 'An eligible original row lacks frozen levels.');
    }
    const counts = source.counts;
    require(keys(counts, 'top_count considered in_band mechanical_fit allocation_fit by_blocker') && counts.considered === source.rows.length &&
      integer(counts.top_count, 5) && counts.top_count >= source.rows.length && counts.in_band === source.rows.filter(x => x.in_band).length &&
      counts.mechanical_fit === source.rows.filter(x => x.research.mechanical_fit).length && counts.allocation_fit === source.rows.filter(x => x.research.allocation_fit).length,
    'The original cohort counts differ from its retained rows.');
  }
  function validateRow(row, original, source, origin, value) {
    require(keys(row, 'rank ticker evidence_id observation model') && row.rank === original.rank && row.ticker === original.ticker && row.evidence_id === original.evidence.id, 'An outcome omitted or changed its original row.');
    const obs = row.observation, m = row.model;
    if (obs !== null) {
      require(origin && keys(obs, 'publication basis anchor bars bars_sha256 carried revision_of changed_dates'), 'Observation evidence fields are invalid.');
      publication(obs.publication);
      require(equal(obs.basis, origin.basis) && equal(obs.anchor, origin.anchors[row.evidence_id]) &&
        instant(obs.publication.published_at) <= instant(value.generated_at) + 5000 && obs.publication.measured_session <= value.publication.measured_session &&
        instant(obs.publication.published_at) <= instant(value.publication.published_at) &&
        typeof obs.carried === 'boolean' && (obs.carried || equal(obs.publication, value.publication)), 'Observation basis or publication attribution changed.');
      require(Array.isArray(obs.bars) && obs.bars.length <= 5 && typeof obs.bars_sha256 === 'string' && HEX.test(obs.bars_sha256), 'The observation clip is invalid.');
      for (const bar of obs.bars) require(keys(bar, 'date o h l c v from_session') && day(bar.date) && bar.from_session === obs.publication.measured_session &&
        source.publication.measured_session < bar.date && bar.date <= obs.publication.measured_session && ['o', 'h', 'l', 'c'].every(k => finite(bar[k]) && bar[k] > 0) &&
        (bar.v === null || finite(bar.v) && bar.v >= 0) && bar.l <= Math.min(bar.o, bar.c) && Math.max(bar.o, bar.c) <= bar.h, 'Daily bars are inconsistent or attributed to another session.');
      require(dates(obs.bars.map(b => b.date)) && (obs.revision_of === null || typeof obs.revision_of === 'string' && HEX.test(obs.revision_of)) && dates(obs.changed_dates) &&
        obs.changed_dates.every(date => obs.bars.some(bar => bar.date === date)) && Boolean(obs.revision_of) === Boolean(obs.changed_dates.length), 'Observation revision evidence is invalid.');
    }
    require(keys(m, 'status reason day sessions entry original_shares sold_shares remaining_shares current_stop events r uncertainty expected_sessions missing_sessions') &&
      STATUSES.includes(m.status) && text(m.reason, 600) && m.reason.length && integer(m.day, 5) && integer(m.sessions, 5) && m.day <= m.sessions &&
      m.original_shares === original.research.shares, 'The model state or frozen share count is invalid.');
    require(dates(m.expected_sessions) && dates(m.missing_sessions) && m.expected_sessions.every(date => date > source.publication.measured_session && date <= value.publication.measured_session) &&
      m.missing_sessions.every(date => m.expected_sessions.includes(date)), 'Expected or missing session dates are invalid.');
    require(m.sessions <= (obs ? obs.bars.length : 0) && equal(m.missing_sessions, m.expected_sessions.filter(date => !obs || !obs.bars.some(bar => bar.date === date))),
    'Model sessions differ from the attached daily evidence.');
    require(['entry', 'current_stop', 'r'].every(k => m[k] === null || finite(m[k]) && (k === 'r' || m[k] > 0)) &&
      ['sold_shares', 'remaining_shares'].every(k => m[k] === null || integer(m[k], 1000000)) &&
      (m.uncertainty === null || ['trigger_timing', 'stop_sequence', 'open_above_limit'].includes(m.uncertainty)) &&
      (m.status === 'uncertain') === (m.uncertainty !== null), 'The model numbers or uncertainty are invalid.');
    require(Array.isArray(m.events) && m.events.length <= 20, 'Too many model events.');
    let sold = 0, profit = 0, lastDay = 0;
    for (const event of m.events) {
      require((keys(event, 'day date event price') || keys(event, 'day date event price shares remaining')) && integer(event.day, 5) && event.day > 0 && event.day >= lastDay &&
        EVENTS.includes(event.event) && (event.price === null || finite(event.price) && event.price > 0) && day(event.date) && obs && obs.bars.some(bar => bar.date === event.date), 'A model event lacks valid dated evidence.');
      lastDay = event.day;
      if ('shares' in event) {
        require(integer(event.shares, 1000000) && event.shares > 0 && integer(event.remaining, 1000000) && finite(event.price), 'A model sale is not a whole-share sale.');
        sold += event.shares; profit += event.shares * (event.price - m.entry);
        require(event.remaining === m.original_shares - sold, 'Whole-share model sales do not reconcile.');
      }
    }
    const known = m.entry !== null;
    if (known) require(obs && obs.bars.length && original.levels && m.entry >= original.levels.trigger && m.entry <= original.levels.limit && m.entry === obs.bars[0].o &&
      m.sold_shares === sold && integer(m.remaining_shares, 1000000) && sold + m.remaining_shares === m.original_shares &&
      ['open', 'resolved', 'missing'].includes(m.status) && finite(m.current_stop), 'The conditional model fill or remaining shares do not reconcile.');
    else require(m.sold_shares === null && m.remaining_shares === null && m.current_stop === null && sold === 0, 'An unknown fill acquired model holdings.');
    require((m.status === 'resolved') === (m.r !== null) && (m.status !== 'resolved' || known && m.remaining_shares === 0 && m.original_shares > 0 &&
      Math.abs(m.r - profit / (m.original_shares * (m.entry - original.levels.stop))) <= 0.00500001), 'R requires reconciled complete whole-share sales.');
    require(m.status !== 'open' || known && m.remaining_shares > 0, 'An open model requires hypothetical shares remaining.');
    if (['uncertain', 'not_filled'].includes(m.status)) require(obs && obs.bars.length > 0 && m.day > 0 && !known, 'A fill classification requires an entry-session observation.');
    require((m.status === 'excluded') === !original.research.allocation_fit, 'Frozen research eligibility changed.');
    if (['pending', 'missing', 'uncertain', 'not_filled', 'open', 'resolved'].includes(m.status)) require(origin && equal(origin.replay_rules, POLICY.replay_rules), 'The model lacks supported original replay rules.');
    if (m.status === 'pending') require(!m.expected_sessions.length && m.day === 0 && !m.events.length && !known, 'Pending research acquired nonexistent observations.');
  }
  async function validateBundle(value, r) {
    require(keys(value, COMMON + ' cohorts limits') && COMMON.split(' ').every(k => equal(value[k], r[k])) && equal(value.limits, LIMITS) &&
      Array.isArray(value.cohorts) && value.cohorts.length <= 128, 'The journal metadata or limits differ from its receipt.');
    const decoded = [], seen = new Set(), primary = new Set(), revisions = new Map(), order = [];
    for (const entry of value.cohorts) {
      require(keys(entry, 'source primary revision origin rows') && keys(entry.source, 'sha256 bytes raw') && typeof entry.source.raw === 'string' &&
        typeof entry.source.sha256 === 'string' && HEX.test(entry.source.sha256) && integer(entry.source.bytes, 128 * 1024) && entry.source.bytes > 0 && !seen.has(entry.source.sha256), 'An original cohort is missing, duplicated or oversized.');
      const bytes = new TextEncoder().encode(entry.source.raw);
      require(bytes.byteLength === entry.source.bytes && await sha(bytes) === entry.source.sha256, 'The original frozen cohort bytes differ from their reference.');
      const source = JSON.parse(entry.source.raw); validateSource(source, instant(value.generated_at)); decoded.push(source); seen.add(entry.source.sha256);
      const applicable = source.publication.applicable_session, expectedPrimary = source.timing.classification === 'before_entry' && !primary.has(applicable);
      if (expectedPrimary) primary.add(applicable);
      const revision = (revisions.get(applicable) || 0) + 1; revisions.set(applicable, revision);
      order.push([applicable, instant(source.timing.generated_at), entry.source.sha256]);
      require(entry.primary === expectedPrimary && entry.revision === revision && integer(entry.revision, 128), 'The first pre-entry cohort or revision order changed.');
      const origin = entry.origin, eligible = source.rows.filter(row => row.research.allocation_fit);
      if (origin !== null) {
        require(keys(origin, 'basis replay_rules anchors') && basis(origin.basis) && (origin.replay_rules === null || equal(origin.replay_rules, POLICY.replay_rules)) &&
          object(origin.anchors) && equal(Object.keys(origin.anchors).sort(), eligible.map(row => row.evidence.id).sort()), 'Original basis, rules or anchor membership is invalid.');
        for (const row of eligible) {
          const a = origin.anchors[row.evidence.id];
          require(keys(a, 'date close source_sha256') && a.date === source.publication.measured_session && a.source_sha256 === row.evidence.source_sha256 && finite(a.close) && a.close > 0, 'An original close anchor changed.');
        }
      }
      require(Array.isArray(entry.rows) && entry.rows.length === source.rows.length, 'The journal omitted an original research row.');
      entry.rows.forEach((row, index) => validateRow(row, source.rows[index], source, origin, value));
    }
    const sorted = order.slice().sort((a, b) => a[0].localeCompare(b[0]) || a[1] - b[1] || a[2].localeCompare(b[2]));
    require(equal(order, sorted) && await sha(new TextEncoder().encode(JSON.stringify(value.cohorts.map(entry => entry.source.sha256)))) === value.cohort_set_sha256, 'The cohort set or chronology changed.');
    const rows = value.cohorts.flatMap(entry => entry.rows);
    require(rows.length <= 640 && equal(value.counts, { cohorts: value.cohorts.length, primary_cohorts: value.cohorts.filter(x => x.primary).length,
      rows: rows.length, eligible: rows.filter(x => x.model.status !== 'excluded').length, by_status: Object.fromEntries(STATUSES.map(status => [status, rows.filter(x => x.model.status === status).length])) }), 'The journal totals omit or misclassify original rows.');
    return { value, sources: decoded };
  }
  async function read(response, max, expected) {
    if (!response.ok || response.redirected) {
      if (response.body && !response.body.locked) await response.body.cancel().catch(() => {});
      throw Error('Published research observations are unavailable.');
    }
    const length = Number(response.headers.get('content-length'));
    if (Number.isFinite(length) && length > max) {
      if (response.body && !response.body.locked) await response.body.cancel().catch(() => {});
      throw Error('Published research exceeds its size limit.');
    }
    require(response.body && response.body.getReader, 'Bounded research reading is unavailable in this browser.');
    // Keep network completion and actual-byte identity, as the main reader does.
    const reader = response.clone().body.getReader();
    let size = 0;
    try {
      while (true) {
        const next = await reader.read(); if (next.done) break;
        size += next.value.byteLength;
        require(size <= max && (expected === undefined || size <= expected), 'Published research exceeds its declared size.');
      }
      require(expected === undefined || size === expected, 'Research length differs from its receipt.');
      const bytes = new Uint8Array(await response.arrayBuffer());
      require(bytes.byteLength === size, 'Research length changed during reading.');
      return bytes;
    } catch (error) {
      await Promise.allSettled([reader.cancel(), response.body.cancel()]); throw error;
    } finally { reader.releaseLock(); }
  }
  const decode = bytes => new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);


  const STATUS_WORDS = { pending: 'Awaiting observations', missing: 'Missing session evidence', uncertain: 'Fill uncertain', not_filled: 'No model fill',
    open: 'Conditional model open', resolved: 'Conditional model resolved', excluded: 'Originally excluded', origin_unavailable: 'Original source unavailable',
    basis_conflict: 'Observation basis conflict', unsupported: 'Replay rules unsupported', unreadable: 'Daily bars unreadable' };
  const EVENT_WORDS = { not_filled: 'No model fill', uncertain: 'Fill remains uncertain', stopped_at_open: 'Model stop at open', gap_exit: 'Model gap exit',
    stopped: 'Model stop', sell_half: 'Model whole-share exit', stop_raised: 'Model stop raised', abnormal_day: 'Model abnormal-day condition',
    no_progress: 'Model no-progress exit', stop_raised_to_entry_low: 'Model stop raised to entry-day low', stop_trailed: 'Model stop trailed', day5_exit: 'Model day-five exit' };
  function datedLabel() {
    return 'Dated observation snapshot · ' + stamp(receipt.generated_at) + '. Retained coverage through the ' + receipt.publication.measured_session +
      ' publication; individual rows may have older or missing evidence. This is not a current price check.';
  }
  function facts(host, values) {
    const list = node('dl', { class: 'sc-facts' });
    for (const [key, label, value] of values) {
      const item = node('div'); item.append(node('dt', {}, label), node('dd', { 'data-outcome-field': key }, value)); list.append(item);
    }
    host.append(list);
  }
  function references(host, label, values) {
    const details = node('details', { class: 'sc-disclosure' }); details.append(node('summary', {}, label));
    const body = node('div', { class: 'sc-disclosure__body' });
    values.forEach(([key, value]) => paragraph(body, key, value)); details.append(body); host.append(details);
    return body;
  }
  function renderRow(host, row, original, source, entry) {
    const article = node('article', { class: 'ss-research-outcomes__row', 'data-outcome-row': row.ticker }), m = row.model, obs = row.observation;
    article.append(node('h5', {}, row.rank + ' · ' + row.ticker));
    facts(article, [['status', 'Dated model state', STATUS_WORDS[m.status]], ['day', 'Observed model day', String(m.day) + ' of 5'],
      ['original-shares', m.status === 'excluded' ? 'Frozen research size — withheld' : 'Original hypothetical whole shares', m.original_shares === null ? 'Unknown' : String(m.original_shares)]]);
    paragraph(article, '', m.reason);
    if (m.status === 'excluded') paragraph(article, 'Original refusal:', original.research.blockers.join(', ').replaceAll('_', ' ') + '. This row stays in the cohort; no model entry is inferred.');
    if (original.event.blocked) paragraph(article, 'Known-event exclusion:', original.event.event_ids.join(', ') + '. The archived exclusion remains visible.');
    else paragraph(article, 'Limited event coverage:', 'The original manual registry is not issuer-news or earnings clearance. These observations add no current event check.');
    if (original.levels) facts(article, [['trigger', 'Frozen hypothetical trigger', money(original.levels.trigger)], ['limit', 'Frozen hypothetical limit', money(original.levels.limit)], ['original-stop', 'Frozen structural stop', money(original.levels.stop)]]);
    facts(article, [['entry', 'Conditional model entry', m.entry === null ? 'Not established' : money(m.entry)],
      ['sold-shares', 'Whole shares exited in model', m.sold_shares === null ? 'Not established' : String(m.sold_shares)],
      ['remaining-shares', 'Whole shares remaining in model', m.remaining_shares === null ? 'Not established' : String(m.remaining_shares)],
      ['r', 'Resolved conditional model R', m.r === null ? 'Not established' : m.r.toFixed(2) + ' R']]);
    if (m.r !== null) paragraph(article, 'R denominator:', 'The model entry-to-original-stop risk, weighted by all whole-share model exits. Actual fees and slippage are unspecified; this is not your return.');
    if (m.missing_sessions.length) paragraph(article, 'Missing completed sessions:', m.missing_sessions.join(', ') + '. A later clock does not supply missing market bars.');
    if (obs) {
      paragraph(article, obs.carried ? 'Older evidence retained:' : 'Dated observation evidence:', 'Publication measured ' + obs.publication.measured_session + ', published ' + stamp(obs.publication.published_at) +
        '. ' + (obs.bars.length ? 'Daily bars ' + obs.bars[0].date + ' through ' + obs.bars[obs.bars.length - 1].date + '.' : 'No entry-session bars yet.') +
        (obs.carried ? ' This clip was carried from its earlier publication, not refreshed.' : ''));
      paragraph(article, 'Observation basis:', [obs.basis.provider, obs.basis.feed, obs.basis.adjustment, obs.basis.timeframe].join(' · ') + '. Original close anchor ' + obs.anchor.date + ': ' + money(obs.anchor.close) + '.');
      if (obs.changed_dates.length) paragraph(article, 'Revised daily observations:', obs.changed_dates.join(', ') + '. This dated snapshot records the revision; it does not rewrite earlier snapshots.');
    } else paragraph(article, 'Observation evidence:', 'No readable, matching daily-bar clip is attached to this row.');
    if (m.events.length) {
      const timeline = node('ol', { class: 'ss-research-outcomes__events', 'data-outcome-events': '' });
      m.events.forEach(event => timeline.append(node('li', {}, event.date + ' · day ' + event.day + ' · ' + EVENT_WORDS[event.event] +
        (event.price === null ? '' : ' at ' + money(event.price)) + ('shares' in event ? ' · ' + event.shares + ' whole shares exited, ' + event.remaining + ' remain in model' : ''))));
      article.append(timeline);
    }
    const evidence = references(article, 'Original and observation references', [['Original measured session:', source.publication.measured_session],
      ['Original cohort SHA-256:', entry.source.sha256], ['Original evidence ID:', row.evidence_id], ['Original source-frame SHA-256:', original.evidence.source_sha256],
      ['Original plan SHA-256:', original.evidence.plan_sha256], ['Observation canonical SHA-256:', obs ? obs.publication.data_sha256 : 'Unavailable'],
      ['Observation bar digest:', obs ? obs.bars_sha256 : 'Unavailable'], ['Prior revised bar digest:', obs && obs.revision_of || 'None recorded']]);
    if (obs && obs.bars.length) {
      const list = node('ul', { class: 'ss-research-outcomes__events' });
      obs.bars.forEach(bar => list.append(node('li', {}, bar.date + ' · O ' + money(bar.o) + ' · H ' + money(bar.h) + ' · L ' + money(bar.l) + ' · C ' + money(bar.c) +
        ' · volume ' + (bar.v === null ? 'unknown' : new Intl.NumberFormat('en-US').format(bar.v)) + ' · from ' + bar.from_session)));
      evidence.append(list);
    }
    host.append(article);
  }
  function renderJournal(host) {
    paragraph(host, 'Conditional daily-bar model.', 'A known model fill requires the entry-session open inside the frozen trigger and limit. Later intraday crossings cannot establish the first thirty minutes. When daily events conflict, the model uses the stop-first convention and whole-share exits over at most five sessions.');
    paragraph(host, 'Separate from your trades.', 'No broker execution, personal result, portfolio return or strategy edge is inferred. Different nightly cohorts do not reserve positions against one another. Actual fees and slippage are unspecified.');
    facts(host, [['cohorts', 'Retained original cohorts', String(bundle.counts.cohorts)], ['primary-cohorts', 'First pre-entry cohorts', String(bundle.counts.primary_cohorts)],
      ['rows', 'All original rows', String(bundle.counts.rows)], ['eligible', 'Frozen eligible research rows', String(bundle.counts.eligible)]]);
    if (!bundle.cohorts.length) paragraph(host, 'No original cohorts recorded.', 'The dated journal is empty. No fill or result is inferred.');
    let session = null, group;
    bundle.cohorts.forEach((entry, index) => {
      const source = sources[index], applicable = source.publication.applicable_session;
      if (session !== applicable) {
        session = applicable; group = node('section', { class: 'ss-research-outcomes__session' }); group.append(node('h3', {}, 'Applicable session ' + applicable));
        if (!bundle.cohorts.some((c, i) => c.primary && sources[i].publication.applicable_session === applicable)) paragraph(group, 'No pre-entry primary.', 'Every retained capture for this session was recorded during or after its entry window. Treat it as retrospective evidence.');
        host.append(group);
      }
      const cohort = node('section', { class: 'ss-research-outcomes__cohort', 'data-outcome-cohort': entry.source.sha256 });
      cohort.append(node('h4', {}, (entry.primary ? 'Primary · first pre-entry capture' : 'Revision ' + entry.revision + ' · retained separately')));
      paragraph(cohort, 'Original capture:', stamp(source.timing.generated_at) + ' · ' + ({ before_entry: 'before entry opened', during_entry: 'during entry — not pre-entry evidence', after_entry: 'after entry — retrospective evidence' }[source.timing.classification]) + '. Original source measured ' + source.publication.measured_session + '.');
      if (!entry.rows.length) paragraph(cohort, 'Zero-row cohort retained.', source.status === 'outside_period' ? 'This original publication was outside the registered experiment period.' : 'This original comparison contained no top anticipation rows.');
      entry.rows.forEach((row, i) => renderRow(cohort, row, source.rows[i], source, entry)); group.append(cohort);
    });
    references(host, 'Journal publication references', [['Policy:', receipt.policy.id], ['Snapshot generated:', stamp(receipt.generated_at)],
      ['Observation canonical SHA-256:', receipt.publication.data_sha256], ['Observation reader SHA-256:', receipt.publication.reader_sha256],
      ['Ordered cohort set SHA-256:', receipt.cohort_set_sha256], ['Journal bundle SHA-256:', receipt.bundle.sha256]]);
  }
  async function load() {
    if (pending) return pending;
    if (!record || !fingerprint().recordHash) { issue = 'No exact publication is available. Load a publication before requesting its research.'; paint(); return false; }
    const token = epoch, target = record, active = new AbortController(); controller = active;
    state = 'loading'; issue = ''; paint();
    let timer, timedOut = false;
    const deadline = new Promise((resolve, reject) => { timer = w.setTimeout(() => {
      timedOut = true; active.abort(); reject(Error('Published research timed out after 15 seconds. Retry when ready.'));
    }, TIMEOUT_MS); });
    const reading = Promise.resolve().then(async () => {
      require(w.crypto && w.crypto.subtle && w.TextEncoder, 'Exact publication verification is unavailable in this browser.');
      const base = new URL('research-outcomes.json', w.location.href);
      require(['http:', 'https:'].includes(base.protocol) && base.origin === w.location.origin && !base.search && !base.hash, 'Research must use this public origin.');
      const options = { cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer', mode: 'same-origin', redirect: 'error', signal: active.signal };
      const nextReceipt = validateReceipt(JSON.parse(decode(await read(await w.fetch(base.href, options), RECEIPT_BYTES))));
      require(token === epoch && target === record && !active.signal.aborted, 'The publication changed during research loading.');
      const bytes = await read(await w.fetch(new URL(nextReceipt.bundle.path, base).href, options), BUNDLE_BYTES, nextReceipt.bundle.bytes);
      require(await sha(bytes) === nextReceipt.bundle.sha256, 'Research digest differs from its receipt.');
      const nextBundle = await validateBundle(JSON.parse(decode(bytes)), nextReceipt);
      binding(nextReceipt.publication);
      return { receipt: nextReceipt, bundle: nextBundle.value, sources: nextBundle.sources };
    });
    pending = Promise.race([reading, deadline]).then(result => {
      if (token !== epoch || target !== record || active.signal.aborted) return false;
      receipt = result.receipt; bundle = result.bundle; sources = result.sources; state = 'loaded'; issue = ''; paint(); return true;
    }).catch(error => {
      if (token !== epoch || target !== record) return false;
      receipt = null; bundle = null; state = 'unavailable';
      issue = timedOut ? 'Published research timed out after 15 seconds. Retry when ready.' : error && error.message || 'Published research is unavailable.';
      paint(); return false;
    }).finally(() => { w.clearTimeout(timer); if (token === epoch) { controller = null; pending = null; } });
    return pending;
  }
  function paintStatus() {
    if (!mounted) return;
    mounted.setAttribute('data-research-outcomes-state', state);
    mounted.querySelector('[data-outcome-reload]').disabled = state === 'loading' || !record || !fingerprint().recordHash;
    mounted.querySelector('[data-outcome-status]').textContent = state === 'loading' ? 'Verifying the dated research observations…' : state === 'unavailable' ? issue :
      state === 'deferred' ? issue || (!record ? 'No publication is loaded. Its research cannot be requested yet.' : !fingerprint().recordHash ? 'Waiting for exact publication verification.' : 'Observation files load only when you open this section.') : datedLabel();
  }
  function paint() {
    if (!mounted) return;
    paintStatus();
    const host = mounted.querySelector('[data-outcome-body]'); host.replaceChildren();
    if (bundle) renderJournal(host);
  }
  function mount() {
    if (mounted) return mounted;
    const host = node('details', { class: 'sc-disclosure ss-research-outcomes', 'data-research-outcomes': '' });
    host.append(node('summary', {}, 'Research follow-through · dated model observations'));
    const content = node('div', { class: 'sc-disclosure__body' });
    content.append(node('p', { class: 'sc-hint' }, 'What happened to each frozen research idea, using retained daily bars. These conditional model observations are separate from your broker fills and reported results.'),
      node('p', { class: 'sc-hint', role: 'status', 'aria-live': 'polite', 'data-outcome-status': '' }), node('div', { 'data-outcome-body': '' }));
    const button = node('button', { class: 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', 'data-outcome-reload': '' }, 'Reload published observations');
    button.addEventListener('click', load);
    content.append(button, node('p', { class: 'sc-hint' }, 'Reload reads the same public research files. It does not run a scan, request provider data or send your cash inputs, saved symbols or broker reports.'));
    host.append(content); mounted = host;
    host.addEventListener('toggle', () => { if (host.open && state === 'deferred') load(); else paintStatus(); });
    paint(); return host;
  }
  function update(data) {
    const hashes = fingerprint(), key = [hashes.recordHash, hashes.canonicalHash, hashes.projected].join('|');
    if (record !== data || key !== identity) {
      epoch++; if (controller) controller.abort(); controller = null; pending = null;
      record = data || null; identity = key; receipt = null; bundle = null; state = 'deferred'; issue = '';
      paint(); if (mounted && mounted.open && record && hashes.recordHash) load();
    } else paintStatus();
  }
  api.researchOutcomes = { mount, update, reload: load, status: () => ({ state, issue, publication: receipt && receipt.publication, rows: bundle ? bundle.counts.rows : 0, cohorts: bundle ? bundle.counts.cohorts : 0 }) };
})(window);
