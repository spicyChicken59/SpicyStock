/* Optional source-bound strategy research. This module owns only its disclosure;
   it never creates orders, changes model eligibility or reads private inputs. */
(function (w) {
  'use strict';
  const api = w.SCStock = w.SCStock || {}, d = w.document;
  const RECEIPT_BYTES = 16 * 1024, BUNDLE_BYTES = 128 * 1024, TIMEOUT_MS = 15000;
  const HEX = /^[a-f0-9]{64}$/;
  const POLICY = { version: 1, id: 'anticipation_stop_width_4_to_5_v1', applicable_start: '2026-10-12', applicable_end: '2026-11-06',
    baseline_stop_pct: 4, research_stop_pct: 5, account: { equity: 2000, risk_pct: 0.5, max_position_pct: 25, max_open_positions: 4 },
    allocation: 'baseline_first_then_original_watchlist_rank', geometry: 'unchanged_anticipation_trigger_limit_structural_stop',
    review: 'existing_anticipation_policy_no_new_chart_review' };
  const BLOCKERS = ['outside_band', 'watchlist_ineligible', 'market_gate', 'known_event', 'invalid_inputs', 'no_whole_share', 'occupied_model_symbol', 'baseline_symbol_reserved', 'slot_cap', 'equity', 'duplicate'];
  const LIMITS = ['research_only_no_orders', 'manual_known_events_not_news_clearance', 'no_new_chart_review', 'no_live_quote_or_earnings_check',
    'principal_excludes_actual_fees', 'price_to_stop_risk_excludes_gaps_slippage', 'model_reservations_not_broker_cash', 'no_returns_or_strategy_edge_established'];
  const COMMON = 'schema_version policy publication timing status reason counts';
  const object = x => !!x && typeof x === 'object' && !Array.isArray(x);
  const require = (ok, why) => { if (!ok) throw Error(why); };
  const canonical = x => Array.isArray(x) ? x.map(canonical) : object(x) ? Object.fromEntries(Object.keys(x).sort().map(k => [k, canonical(x[k])])) : x;
  const equal = (a, b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
  const keys = (x, names) => object(x) && equal(Object.keys(x).sort(), names.split(' ').sort());
  const integer = (x, max = Number.MAX_SAFE_INTEGER) => Number.isSafeInteger(x) && x >= 0 && x <= max;
  const finite = x => typeof x === 'number' && Number.isFinite(x);
  const text = (x, max = 4096) => typeof x === 'string' && x.length <= max;
  const day = x => typeof x === 'string' && /^\d{4}-\d\d-\d\d$/.test(x) && Number.isFinite(Date.parse(x)) && new Date(x).toISOString().slice(0, 10) === x;
  const instant = x => {
    const match = typeof x === 'string' && /^(\d{4}-\d\d-\d\d)T(\d\d):(\d\d):(\d\d)(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)$/.exec(x);
    return match && day(match[1]) && Number(match[2]) < 24 && Number(match[3]) < 60 && Number(match[4]) < 60 ? Date.parse(x) : NaN;
  };
  const clock = () => api.now ? new Date(api.now).getTime() : Date.now();
  const stamp = x => Number.isFinite(instant(x)) ? new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', dateStyle: 'medium', timeStyle: 'short' }).format(new Date(x)) + ' CT' : 'Unavailable';
  const money = x => finite(x) ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(x) : 'Unavailable';
  const fingerprint = () => api.observations ? api.observations.facts() : {};
  let mounted = null, record = null, identity = '', receipt = null, bundle = null;
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
  function binding(value) {
    const hashes = fingerprint(), run = record && record.run || {};
    require(keys(value, 'data_sha256 context_sha256 run_id rules_version measured_session applicable_session published_at reader_projection_version reader_sha256') &&
      HEX.test(value.data_sha256) && HEX.test(value.reader_sha256) && HEX.test(value.context_sha256) && /^[a-f0-9]{12}$/.test(value.rules_version) &&
      day(value.measured_session) && day(value.applicable_session) && Number.isFinite(instant(value.published_at)) && value.reader_projection_version === 1 &&
      hashes.recordHash && value.data_sha256 === hashes.canonicalHash && (!hashes.projected || value.reader_sha256 === hashes.recordHash) &&
      value.context_sha256 === (run.evidence || {}).context_sha256 && value.rules_version === (record.app || {}).rules_version &&
      String(value.run_id) === String(run.run_id) && value.measured_session === run.session &&
      value.applicable_session === (run.timing || {}).applicable_session && value.published_at === run.published_at,
    'This research belongs to another publication. No comparison has been loaded.');
  }
  function cents(value) {
    const result = Math.round(value * 100);
    require(finite(value) && value >= 0 && Number.isSafeInteger(result) && Math.abs(result - value * 100) < 0.00001, 'Research contains an invalid money amount.');
    return result;
  }
  function validateReceipt(value) {
    require(keys(value, COMMON + ' bundle') && value.schema_version === 1 && equal(value.policy, POLICY), 'The research policy is unsupported.');
    binding(value.publication);
    require(Object.entries(POLICY.account).every(([key, expected]) => (record.account || {})[key] === expected), 'Research account differs from the publication.');
    const timing = value.timing, sourceTiming = record.run.timing || {};
    require(keys(timing, 'generated_at entry_opens_at entry_cutoff_at classification'), 'Research timing is missing.');
    const generated = instant(timing.generated_at), opens = instant(timing.entry_opens_at), cutoff = instant(timing.entry_cutoff_at);
    require([generated, opens, cutoff].every(Number.isFinite) && opens < cutoff && generated <= clock() + 5000 && instant(value.publication.published_at) <= generated + 5000 &&
      opens === instant(sourceTiming.opens_at) && cutoff === instant(sourceTiming.cutoff_at) &&
      timing.classification === (generated < opens ? 'before_entry' : generated < cutoff ? 'during_entry' : 'after_entry'), 'Research timing differs from its recorded entry window.');
    const inPeriod = value.publication.applicable_session >= POLICY.applicable_start && value.publication.applicable_session <= POLICY.applicable_end;
    require(value.status === (inPeriod ? 'recorded' : 'outside_period') && value.reason === (inPeriod ? null : 'The applicable session is outside the registered experiment period.'), 'Research registration status is invalid.');
    const counts = value.counts, top = (record.watchlist || {}).top;
    require(Array.isArray(top) && top.length <= 5 && keys(counts, 'top_count considered in_band mechanical_fit allocation_fit by_blocker') &&
      ['top_count', 'considered', 'in_band', 'mechanical_fit', 'allocation_fit'].every(k => integer(counts[k], 5)) &&
      counts.top_count === top.length && counts.considered === (inPeriod ? top.length : 0) &&
      keys(counts.by_blocker, BLOCKERS.join(' ')) && Object.values(counts.by_blocker).every(n => integer(n, 5)), 'Research cohort counts are invalid.');
    const ref = value.bundle;
    require(keys(ref, 'sha256 bytes path') && HEX.test(ref.sha256) && integer(ref.bytes, BUNDLE_BYTES) && ref.bytes > 0 && ref.path === 'stop-research/' + ref.sha256 + '.json', 'Research bundle identity is invalid.');
    return value;
  }
  async function validateBundle(value, r) {
    require(keys(value, COMMON + ' reservations rows limits') && COMMON.split(' ').every(k => equal(value[k], r[k])) && equal(value.limits, LIMITS), 'Research metadata or coverage limits differ from the receipt.');
    const top = r.status === 'recorded' ? record.watchlist.top : [], cash = record.cash_budget || {}, account = record.account || {};
    const all = (record.bursts || []).concat(record.watchlist.top), baseline = all.filter(x => ((x.evidence || {}).gate || {}).ticket === true);
    const baselineSymbols = [...new Set(baseline.map(x => x.ticker))].sort(), reserves = value.reservations;
    require(keys(reserves, 'equity_usd position_cap_usd max_slots open_model_principal_usd open_model_slots open_symbols baseline_principal_usd baseline_risk_usd baseline_slots baseline_symbols available_principal_usd_before_research research_principal_usd research_risk_usd research_slots slots_used remaining_model_principal_usd'), 'Research reservations are invalid.');
    Object.entries(reserves).forEach(([key, n]) => { if (!['open_symbols', 'baseline_symbols'].includes(key)) cents(n); });
    require(reserves.equity_usd === account.equity && reserves.position_cap_usd === account.equity * account.max_position_pct / 100 && reserves.max_slots === account.max_open_positions &&
      reserves.open_model_principal_usd === cash.reserved_usd && reserves.open_model_slots === cash.open_positions && equal(reserves.open_symbols, cash.open_symbols) &&
      reserves.baseline_principal_usd === cash.committed_usd && reserves.baseline_risk_usd === cash.at_risk_usd && reserves.baseline_slots === baseline.length &&
      equal(reserves.baseline_symbols, baselineSymbols) && ['open_model_slots', 'baseline_slots', 'research_slots', 'slots_used'].every(k => integer(reserves[k])) &&
      Array.isArray(reserves.open_symbols) && reserves.open_symbols.every(x => typeof x === 'string'), 'Research changed an existing model reservation or baseline ticket.');
    const before = Math.max(0, cents(cash.available_usd) - cents(cash.committed_usd));
    require(cents(reserves.available_principal_usd_before_research) === before, 'Research available principal differs from baseline allocation.');
    require(Array.isArray(value.rows) && value.rows.length === top.length && new Set(value.rows.map(x => x.ticker)).size === top.length, 'Research omitted or duplicated a published top row.');
    const registry = ((record.rules || {}).event_risk || {}), regime = ((record.breadth || {}).regime || {}), rules = (record.rules || {}).plan || {};
    require(rules.max_stop_pct === POLICY.baseline_stop_pct && rules.ideal_stop_pct === 2 && rules.stop_risk_multiplier === 0.5 && registry.coverage === 'manual_known_events_only', 'Research planner or event policy is unsupported.');
    let remaining = before, slots = reserves.open_model_slots + baseline.length, researchPrincipal = 0, researchRisk = 0, researchSlots = 0;
    for (let index = 0; index < top.length; index++) {
      const row = value.rows[index], original = top[index], originalPlan = original.plan || {}, evidence = original.evidence || {}, source = evidence.source || {}, planning = evidence.planning || {};
      require(keys(row, 'rank ticker evidence in_band baseline levels research event quality') && row.rank === index + 1 && row.ticker === original.ticker && /^[A-Z][A-Z0-9.-]{0,14}$/.test(row.ticker), 'Research membership or rank differs from the publication.');
      require(keys(row.evidence, 'id plan_sha256 source_sha256 inputs_sha256') && Object.values(row.evidence).every(x => typeof x === 'string' && HEX.test(x)) &&
        row.evidence.id === evidence.id && row.evidence.plan_sha256 === planning.output_sha256 && row.evidence.source_sha256 === source.sha256, 'Research source or plan identity differs from the publication.');
      require(equal(row.baseline, { admitted: ((evidence.gate || {}).ticket === true), eligible: originalPlan.eligible ?? null, action: originalPlan.action ?? null,
        reason: originalPlan.reason ?? planning.error ?? null, shares: originalPlan.shares ?? null }), 'Research baseline differs from the published plan.');
      require(keys(row.quality, 'watchlist_eligible source_session review') && row.quality.watchlist_eligible === (original.eligible === true) &&
        row.quality.source_session === record.run.session && row.quality.review === 'not_required_by_anticipation', 'Research source quality differs from the publication.');
      const event = row.event, archivedEvent = originalPlan.event_risk;
      const matches = archivedEvent ? (archivedEvent.matches || []).map(x => x.id) : ((registry.registry || {}).events || []).filter(x => x.symbol === row.ticker && x.active_from <= record.run.session && (!x.active_until || x.active_until > record.run.session)).map(x => x.id);
      require(keys(event, 'blocked status registry_sha256 event_ids') && event.registry_sha256 === registry.registry_sha256 &&
        equal(event.event_ids, matches) && event.blocked === (matches.length > 0) &&
        (archivedEvent ? event.status === archivedEvent.status : ['known_event', 'review_required', 'not_in_registry'].includes(event.status)), 'Research event exclusions differ from the archived registry.');
      const research = row.research, levels = row.levels;
      require(keys(research, 'mechanical_fit allocation_fit shares principal_usd risk_usd risk_per_share effective_risk_budget_usd multipliers blockers projection_sha256') &&
        typeof research.mechanical_fit === 'boolean' && typeof research.allocation_fit === 'boolean' && HEX.test(research.projection_sha256) &&
        Array.isArray(research.blockers) && research.blockers.length === new Set(research.blockers).size && research.blockers.every(x => BLOCKERS.includes(x)), 'Research projection or refusal reasons are invalid.');
      const expectedBlockers = [];
      if (levels === null) {
        require((!original.plan || planning.error) && ['shares', 'principal_usd', 'risk_usd', 'risk_per_share', 'effective_risk_budget_usd', 'multipliers'].every(k => research[k] === null), 'Missing inputs acquired a research size.');
        expectedBlockers.push('invalid_inputs');
      } else {
        require(keys(levels, 'trigger limit stop stop_pct') && Object.values(levels).every(x => finite(x) && x > 0) &&
          ['trigger', 'limit', 'stop', 'stop_pct'].every(k => levels[k] === originalPlan[k]) && levels.stop < levels.trigger && levels.trigger <= levels.limit, 'Research changed the original structural levels.');
        const multipliers = research.multipliers, stopMultiplier = levels.stop_pct > rules.ideal_stop_pct && levels.stop_pct <= POLICY.research_stop_pct ? rules.stop_risk_multiplier : 1;
        const marketMultiplier = (planning.inputs || {}).size_multiplier;
        require(keys(multipliers, 'regime hazard stop_risk total') && Object.values(multipliers).every(x => finite(x) && x >= 0 && x <= 1) &&
          multipliers.regime === marketMultiplier && multipliers.hazard === 1 && multipliers.stop_risk === stopMultiplier && multipliers.total === marketMultiplier * stopMultiplier, 'Research changed the recorded risk multipliers.');
        const risk = cents(levels.limit) - cents(levels.stop), budget = Math.round(account.equity * account.risk_pct * multipliers.total), cap = cents(reserves.position_cap_usd);
        require(risk > 0 && cents(research.risk_per_share) === risk && cents(research.effective_risk_budget_usd) === budget && integer(research.shares, 1000000) &&
          research.shares === Math.min(Math.floor(budget / risk), Math.floor(cap / cents(levels.limit))) &&
          cents(research.principal_usd) === research.shares * cents(levels.limit) && cents(research.risk_usd) === research.shares * risk, 'Research whole-share cost or planned risk does not reconcile.');
      }
      require(row.in_band === (levels !== null && levels.stop_pct > POLICY.baseline_stop_pct && levels.stop_pct <= POLICY.research_stop_pct), 'Research band membership differs from recorded stop width.');
      if (!row.in_band) expectedBlockers.push('outside_band');
      if (!row.quality.watchlist_eligible) expectedBlockers.push('watchlist_ineligible');
      if (regime.size_multiplier <= 0 || regime.verdict === 'red') expectedBlockers.push('market_gate');
      if (event.blocked) expectedBlockers.push('known_event');
      if (levels && research.shares <= 0) expectedBlockers.push('no_whole_share');
      require(research.mechanical_fit === (expectedBlockers.length === 0), 'Research mechanical fit contradicts its source refusals.');
      const occupied = reserves.open_symbols.includes(row.ticker), reserved = baselineSymbols.includes(row.ticker);
      if (occupied) expectedBlockers.push('occupied_model_symbol');
      if (reserved) expectedBlockers.push('baseline_symbol_reserved');
      let allocationFit = false;
      if (research.mechanical_fit && !occupied && !reserved) {
        if (slots >= reserves.max_slots) expectedBlockers.push('slot_cap');
        else if (cents(research.principal_usd) > remaining) expectedBlockers.push('equity');
        else { allocationFit = true; slots++; researchSlots++; remaining -= cents(research.principal_usd); researchPrincipal += cents(research.principal_usd); researchRisk += cents(research.risk_usd); }
      }
      if (research.mechanical_fit && reserved && !occupied) expectedBlockers.push('duplicate');
      require(equal(research.blockers.slice().sort(), expectedBlockers.sort()) && research.allocation_fit === allocationFit, 'Research changed baseline priority or shared allocation.');
    }
    const count = predicate => value.rows.filter(predicate).length;
    const expectedCounts = { top_count: record.watchlist.top.length, considered: value.rows.length, in_band: count(x => x.in_band), mechanical_fit: count(x => x.research.mechanical_fit), allocation_fit: count(x => x.research.allocation_fit),
      by_blocker: Object.fromEntries(BLOCKERS.map(key => [key, count(x => x.research.blockers.includes(key))])) };
    require(equal(value.counts, expectedCounts), 'Research totals do not reconcile with all rows.');
    require(cents(reserves.research_principal_usd) === researchPrincipal && cents(reserves.research_risk_usd) === researchRisk && reserves.research_slots === researchSlots &&
      reserves.slots_used === slots && cents(reserves.remaining_model_principal_usd) === remaining, 'Research allocation totals do not reconcile.');
    return value;
  }
  async function read(response, max, expected) {
    if (!response.ok || response.redirected) {
      if (response.body && !response.body.locked) await response.body.cancel().catch(() => {});
      throw Error('Published stop-width research is unavailable.');
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

  function datedLabel() {
    const timing = receipt.timing, av = api.avail || {}, pub = av.pub || {};
    const archived = clock() >= instant(timing.entry_cutoff_at) || av.pubBlocked || av.phase === 'ended' || !['fresh', 'degraded', 'closed'].includes(pub.state);
    const phase = { before_entry: 'recorded before entry opened', during_entry: 'recorded during the entry window — not a pre-entry snapshot', after_entry: 'recorded after the entry window — retrospective comparison' }[timing.classification];
    return (archived ? 'Archived comparison. ' : 'Dated comparison. ') + 'Applicable session ' + receipt.publication.applicable_session + ' · ' + stamp(timing.generated_at) + ' · ' + phase + '. No live quote or trade outcome is inferred.';
  }
  function facts(host, values) {
    const list = node('dl', { class: 'sc-facts' });
    for (const [key, label, value] of values) {
      const item = node('div'); item.append(node('dt', {}, label), node('dd', { 'data-stop-value': key }, value)); list.append(item);
    }
    host.append(list);
  }
  const BLOCKER_WORDS = {
    outside_band: 'Outside the experimental band (over 4%, at most 5%).', watchlist_ineligible: 'The original watchlist quality gate is not met.',
    market_gate: 'The recorded market regime refuses new long entries.', known_event: 'The archived known-event exclusion remains in force.',
    invalid_inputs: 'Required planning inputs are unavailable or invalid.', no_whole_share: 'The effective risk budget and position cap cannot fit one whole share.',
    occupied_model_symbol: 'An unfinished model plan already occupies this symbol.', baseline_symbol_reserved: 'An unchanged production ticket reserves this symbol first.',
    slot_cap: 'No model position slot remains after existing reservations and earlier-ranked fits.', equity: 'Insufficient model principal remains after existing reservations and earlier-ranked fits.',
    duplicate: 'This symbol already has a reserved allocation.'
  };
  function renderComparison(host) {
    const counts = bundle.counts, reserves = bundle.reservations, policy = receipt.policy;
    paragraph(host, 'Registered window:', policy.applicable_start + ' through ' + policy.applicable_end + ' applicable sessions. Empty and refused cohorts are retained. User-reported trades and results remain separate.');
    paragraph(host, 'Source record:', 'Measured ' + receipt.publication.measured_session + '; published ' + stamp(receipt.publication.published_at) + '. This comparison was recorded separately at ' + stamp(receipt.timing.generated_at) + '.');
    if (receipt.status === 'outside_period') {
      paragraph(host, 'Outside the registered period.', receipt.reason + ' ' + counts.top_count + ' top anticipation rows were present; no rows were included in this registered experiment.');
      return;
    }
    paragraph(host, 'One change:', 'The maximum anticipation stop width rises from 4% to 5%. Trigger, limit and structural stop stay fixed. Existing market, input, event and whole-share safeguards still apply; anticipation does not add a chart review.');
    facts(host, [['top-count', 'Published top rows', String(counts.top_count)], ['in-band', 'Within the 4–5% band', String(counts.in_band)],
      ['mechanical-fit', 'Individual research fits', String(counts.mechanical_fit)], ['allocation-fit', 'Fits after model allocation', String(counts.allocation_fit)]]);
    paragraph(host, 'Account reference:', money(policy.account.equity) + ' · ' + policy.account.risk_pct + '% base risk (' + money(policy.account.equity * policy.account.risk_pct / 100) + ') · ' + money(reserves.position_cap_usd) + ' per-name cap · ' + reserves.max_slots + ' model slots. Risk reductions still apply.');
    paragraph(host, 'Baseline first:', reserves.baseline_slots + ' unchanged production tickets reserve ' + money(reserves.baseline_principal_usd) + '. ' + reserves.open_model_slots + ' unfinished model plans reserve ' + money(reserves.open_model_principal_usd) + (reserves.open_symbols.length ? ' (' + reserves.open_symbols.join(', ') + ')' : '') + '. Research cannot displace either.');
    facts(host, [['research-principal', 'Additional research principal', money(reserves.research_principal_usd)], ['research-risk', 'Research price-to-stop risk', money(reserves.research_risk_usd)],
      ['slots-used', 'Model slots used', reserves.slots_used + ' of ' + reserves.max_slots], ['remaining-principal', 'Remaining model principal', money(reserves.remaining_model_principal_usd)]]);
    paragraph(host, 'Model figures only.', 'Principal excludes actual fees. Planned price-to-stop risk is not a maximum loss; gaps and slippage can increase losses. These reservations do not read or reserve your broker settled cash.');
    if (!bundle.rows.length) paragraph(host, 'Zero-row cohort.', 'This exact publication had no top anticipation rows. The empty comparison remains part of the registered observation period.');
    for (const row of bundle.rows) {
      const article = node('article', { class: 'ss-stop-research__row', 'data-stop-row': row.ticker });
      article.append(node('h4', {}, row.rank + ' · ' + row.ticker));
      paragraph(article, row.research.allocation_fit ? 'Hypothetical allocation fits.' : 'Research withheld.', row.in_band ? 'The unchanged stop is inside the experimental 4–5% band.' : 'This original top row remains visible outside the experimental band.');
      if (row.levels) facts(article, [['trigger', 'Unchanged trigger', money(row.levels.trigger)], ['limit', 'Unchanged limit', money(row.levels.limit)],
        ['stop', 'Unchanged structural stop', money(row.levels.stop)], ['stop-width', 'Stop width at limit', row.levels.stop_pct.toFixed(2) + '%']]);
      const columns = node('div', { class: 'ss-stop-research__comparison' }), baseline = node('section'), research = node('section');
      baseline.append(node('h5', {}, '4% production baseline'));
      paragraph(baseline, row.baseline.admitted ? 'Production ticket retained.' : 'No production ticket.', row.baseline.reason || (row.baseline.admitted ? 'Its original conditions and quantity remain unchanged.' : 'This original plan was not admitted.'));
      facts(baseline, [['baseline-shares', row.baseline.admitted ? 'Published whole shares' : 'Recorded size — withheld', row.baseline.shares === null ? 'Unavailable' : String(row.baseline.shares)]]);
      research.append(node('h5', {}, '5% research comparison'));
      facts(research, [['research-shares', 'Hypothetical whole shares', row.research.shares === null ? 'Unavailable' : String(row.research.shares)],
        ['research-row-principal', 'Hypothetical principal', money(row.research.principal_usd)], ['research-row-risk', 'Planned price-to-stop risk', money(row.research.risk_usd)],
        ['risk-budget', 'Effective risk budget', money(row.research.effective_risk_budget_usd)], ['allocated-shares', 'Research shares after allocation', String(row.research.allocation_fit ? row.research.shares : 0)]]);
      if (row.research.multipliers) {
        const multipliers = row.research.multipliers;
        paragraph(research, 'Risk reductions:', money(policy.account.equity * policy.account.risk_pct / 100) + ' × ' + multipliers.regime + ' market × ' + multipliers.hazard + ' hazard × ' + multipliers.stop_risk + ' stop width = ' + money(row.research.effective_risk_budget_usd) + '. Refused baseline sizing is not reused.');
      }
      columns.append(baseline, research); article.append(columns);
      if (row.research.blockers.length) {
        const list = node('ul', { class: 'ss-stop-research__limits', 'data-stop-blockers': '' });
        row.research.blockers.forEach(key => list.append(node('li', {}, BLOCKER_WORDS[key]))); article.append(list);
      }
      paragraph(article, row.event.blocked ? 'Known event exclusion.' : 'Limited event coverage.', row.event.blocked ? row.event.event_ids.join(', ') + (row.event.status === 'review_required' ? ' · source review is overdue; exclusion remains.' : ' · retained in both policies.') : 'No match in the archived manual registry is not issuer-news or earnings clearance.');
      host.append(article);
    }
    paragraph(host, 'Still unverified:', 'Current broker quotes, spread, trading status, issuer news and earnings. This comparison supplies no new live check, executable order, confirmed fill, return or established strategy edge.');
    const source = node('details', { class: 'sc-disclosure' }); source.append(node('summary', {}, 'Publication and experiment references'));
    const detail = node('div', { class: 'sc-disclosure__body' });
    paragraph(detail, 'Policy:', policy.id); paragraph(detail, 'Rules:', receipt.publication.rules_version);
    paragraph(detail, 'Canonical source SHA-256:', receipt.publication.data_sha256); paragraph(detail, 'Reader SHA-256:', receipt.publication.reader_sha256);
    paragraph(detail, 'Comparison SHA-256:', receipt.bundle.sha256); source.append(detail); host.append(source);
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
      const base = new URL('stop-research.json', w.location.href);
      require(['http:', 'https:'].includes(base.protocol) && base.origin === w.location.origin && !base.search && !base.hash, 'Research must use this public origin.');
      const options = { cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer', mode: 'same-origin', redirect: 'error', signal: active.signal };
      const nextReceipt = validateReceipt(JSON.parse(decode(await read(await w.fetch(base.href, options), RECEIPT_BYTES))));
      require(token === epoch && target === record && !active.signal.aborted, 'The publication changed during research loading.');
      const bytes = await read(await w.fetch(new URL(nextReceipt.bundle.path, base).href, options), BUNDLE_BYTES, nextReceipt.bundle.bytes);
      require(await sha(bytes) === nextReceipt.bundle.sha256, 'Research digest differs from its receipt.');
      const nextBundle = await validateBundle(JSON.parse(decode(bytes)), nextReceipt);
      binding(nextReceipt.publication);
      return { receipt: nextReceipt, bundle: nextBundle };
    });
    pending = Promise.race([reading, deadline]).then(result => {
      if (token !== epoch || target !== record || active.signal.aborted) return false;
      receipt = result.receipt; bundle = result.bundle; state = 'loaded'; issue = ''; paint(); return true;
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
    mounted.setAttribute('data-stop-research-state', state);
    mounted.querySelector('[data-stop-reload]').disabled = state === 'loading' || !record || !fingerprint().recordHash;
    mounted.querySelector('[data-stop-status]').textContent = state === 'loading' ? 'Verifying the published comparison…' : state === 'unavailable' ? issue :
      state === 'deferred' ? issue || (!record ? 'No publication is loaded. Its research cannot be requested yet.' : !fingerprint().recordHash ? 'Waiting for exact publication verification.' : 'Comparison files load only when you open this section.') : datedLabel();
  }
  function paint() {
    if (!mounted) return;
    paintStatus();
    const host = mounted.querySelector('[data-stop-body]'); host.replaceChildren();
    if (bundle) renderComparison(host);
  }
  function mount() {
    if (mounted) return mounted;
    const host = node('details', { class: 'sc-disclosure ss-stop-research', 'data-stop-research': '' });
    host.append(node('summary', {}, 'Wider-stop anticipation research'));
    const content = node('div', { class: 'sc-disclosure__body' });
    content.append(node('p', { class: 'sc-hint' }, 'An optional 4% versus 5% stop-width comparison. Production tickets keep their original policy. Research quantities are not broker drafts, reported fills or evidence of a profitable strategy.'),
      node('p', { class: 'sc-hint', role: 'status', 'aria-live': 'polite', 'data-stop-status': '' }), node('div', { 'data-stop-body': '' }));
    const button = node('button', { class: 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', 'data-stop-reload': '' }, 'Reload published comparison');
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
  api.stopResearch = { mount, update, reload: load, status: () => ({ state, issue, publication: receipt && receipt.publication, rows: bundle ? bundle.rows.length : 0 }) };
})(window);
