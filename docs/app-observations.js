/* Public morning observations are a separately dated, exact-record-bound
   receipt. They cannot create a ticket or relax publication/strategy rules. */
(function (w) {
  'use strict';
  const api = w.SCStock = w.SCStock || {}, d = w.document;
  const MAX_BYTES = 512 * 1024, QUOTE_AGE = 60, RECEIPT_AGE = 300, FUTURE_SKEW = 5;
  const HEX = /^[a-f0-9]{64}$/;
  const HALT_URL = 'https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts', CACHE_KEY = 'spicystock:morning-receipt:v1';
  const HALT_CODES = new Set('T1 T2 T3 T5 T6 T7 T8 T12 H4 H9 H10 H11 O1 IPO1 IPOQ IPOE M1 M2 LUDP LUDS MWC1 MWC2 MWC3 MWC0 MWCQ R4 R9 C3 C4 C9 C11 R1 R2 M D'.split(' '));
  const finite = n => typeof n === 'number' && Number.isFinite(n);
  const dateMs = value => typeof value === 'string' && /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? Date.parse(value) : NaN;
  const words = value => typeof value === 'string' ? value.replace(/_/g, ' ') : 'unknown';
  const money = value => finite(value) ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 4 }).format(value) : 'unavailable';
  const atCT = value => Number.isFinite(dateMs(value)) ? new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit' }).format(new Date(value)) + ' CT' : 'time unavailable';
  const ageWords = (stamp, now) => {
    const seconds = (now - dateMs(stamp)) / 1000;
    return !Number.isFinite(seconds) ? 'age unavailable' : seconds < -FUTURE_SKEW ? 'timestamp is in the future' : seconds < 60 ? Math.max(0, Math.floor(seconds)) + ' seconds old' : Math.floor(seconds / 60) + ' minutes old';
  };
  const node = (tag, attrs, text) => {
    const element = d.createElement(tag);
    Object.entries(attrs || {}).forEach(([key, value]) => element.setAttribute(key, value));
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const sourceURL = value => {
    try {
      const url = new URL(value);
      return url.protocol === 'https:' && !url.username && !url.password && url.hostname ? url.href : null;
    } catch (e) { return null; }
  };
  const rowKey = c => (c.stage === 'bursts' ? 'burst' : 'anticipation') + ':' + c.ticker;
  let record = null, recordHash = null, epoch = 0, sequence = 0, controller = null, state = 'unbound', receipt = null, issue = '', now = Date.now();
  let readerBinding = null;
  let halted = new Map(), corporate = new Map(), onChange = null, storageIssue = '', cachedHalt = false, pinned = false;
  const sourceMemory = { halts: {}, corporate: {} };
  const hosts = new Map();
  const candidates = () => Object.values((api.model || {}).stages || {}).flat().filter(c => c.status === 'ticket');
  const findCandidate = (kind, ticker) => candidates().find(c => rowKey(c) === kind + ':' + ticker);
  const freshStamp = (stamp, maxAge) => Number.isFinite(dateMs(stamp)) && now - dateMs(stamp) >= -FUTURE_SKEW * 1000 && now - dateMs(stamp) <= maxAge * 1000;
  const receiptFresh = () => !!receipt && freshStamp(receipt.generated_at, RECEIPT_AGE) && now <= dateMs(receipt.expires_at);
  const rowFor = c => receipt && receipt.rows.find(row => row.kind + ':' + row.ticker === rowKey(c));
  const quotesCurrent = row => receiptFresh() && ['quote', 'trade'].every(key => row[key] && row[key].status === 'recent' && freshStamp(row[key].timestamp, QUOTE_AGE));
  const require = (condition, message) => { if (!condition) throw Error(message); };
  const easternParts = stamp => Object.fromEntries(new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).formatToParts(new Date(stamp)).map(part => [part.type, part.value]));
  const sessionAt = stamp => { const p = easternParts(stamp); return p.year + '-' + p.month + '-' + p.day; };
  const sourceTimeMatches = (stamp, day, clock) => {
    if (!Number.isFinite(dateMs(stamp)) || typeof day !== 'string' || typeof clock !== 'string' || !/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(day) || !/^\d{1,2}:\d{2}:\d{2}(?:\.\d{1,6})?$/.test(clock)) return false;
    const p = easternParts(stamp);
    const fraction = value => ((value.match(/\.(\d+)/) || [])[1] || '').padEnd(6, '0');
    return day.split('/').map(Number).join('/') === [p.month, p.day, p.year].map(Number).join('/') && clock.split('.')[0].split(':').map(Number).join(':') === [p.hour, p.minute, p.second].map(Number).join(':') && fraction(clock) === fraction(stamp);
  };
  function validateHaltSource(source, generated) {
    require(source && source.source_url === HALT_URL && source.provider === 'Nasdaq Trader current trade halts RSS' && typeof source.scope === 'string', 'Halt source identity is invalid.');
    const checked = dateMs(source.checked_at);
    require(Number.isFinite(checked) && checked <= generated + FUTURE_SKEW * 1000, 'Halt check time is invalid.');
    if (['unavailable', 'not_requested'].includes(source.status)) {
      require(['fetched_at', 'source_published_at', 'expires_at', 'source_sha256', 'item_count', 'source_age_seconds', 'receipt_age_seconds'].every(key => source[key] === null), 'Unavailable halt source claims evidence.');
      return;
    }
    const fetched = dateMs(source.fetched_at), published = dateMs(source.source_published_at);
    require(['fresh', 'stale'].includes(source.status) && HEX.test(source.source_sha256) && Number.isInteger(source.item_count) && source.item_count >= 0 && source.item_count <= 2000, 'Halt source evidence is incomplete.');
    require([fetched, published].every(Number.isFinite) && checked - fetched >= -5000 && checked - published >= -5000 && published <= fetched + 5000, 'Halt source clocks are invalid.');
    const fresh = checked - published <= 180000 && checked - fetched <= 300000;
    require(source.status === (fresh ? 'fresh' : 'stale') && Math.abs(source.source_age_seconds - (checked - published) / 1000) < .002 && Math.abs(source.receipt_age_seconds - (checked - fetched) / 1000) < .002 && dateMs(source.expires_at) === Math.min(published + 180000, fetched + 300000), 'Halt freshness disagrees with source clocks.');
  }
  function validateHalt(halt, coverage, row, generated) {
    require(halt && halt.source_url === HALT_URL && Array.isArray(halt.events) && halt.events.length <= 1 && (halt.blocks_entry === true || halt.blocks_entry === null), 'Halt row is invalid.');
    const source = halt.retained_source || coverage;
    validateHaltSource(source, generated);
    require(!halt.retained_source || halt.blocks_entry === true, 'Retained evidence cannot establish resumption.');
    require(Number.isInteger(halt.event_count) && halt.event_count >= halt.events.length && halt.event_count <= (source.item_count || 0), 'Halt event count is invalid.');
    if (!halt.events.length) {
      require(halt.event_count === 0 && halt.blocks_entry === null && halt.status === (coverage.status === 'fresh' ? 'not_listed' : 'unknown'), 'Empty halt evidence cannot establish a restriction or clearance.');
      return;
    }
    const event = halt.events[0], fields = event && event.source_fields;
    require(event && event.symbol === row.ticker && fields && fields.IssueSymbol === row.ticker && fields.Market === event.market && fields.ReasonCode === event.reason_code && fields.IssueName === event.issue_name, 'Halt identity differs from source evidence.');
    require(sourceTimeMatches(event.halted_at, fields.HaltDate, fields.HaltTime), 'Halt time differs from source evidence.');
    const haltedAt = dateMs(event.halted_at), published = dateMs(source.source_published_at), checked = dateMs(coverage.checked_at);
    require(Number.isFinite(published) && haltedAt <= published + 5000 && haltedAt <= checked + 5000, 'Halt was not observed by its source.');
    for (const [key, field] of [['quote_resumption_at', 'ResumptionQuoteTime'], ['trade_resumption_at', 'ResumptionTradeTime']]) {
      require(fields[field] ? sourceTimeMatches(event[key], fields.ResumptionDate, fields[field]) : event[key] === null, 'Resumption time differs from source evidence.');
    }
    const trade = dateMs(event.trade_resumption_at), code = event.reason_code;
    require(event.trade_resumption_at === null || Number.isFinite(trade) && trade >= haltedAt, 'Trading resumption precedes its halt.');
    const status = code === 'D' ? 'security_deleted' : event.trade_resumption_at === null ? 'halt_reported' : !HALT_CODES.has(code) ? 'unknown' : trade > checked || trade > published ? 'resumption_scheduled' : halt.retained_source || coverage.status !== 'fresh' ? 'unknown' : 'resumption_reported';
    require(halt.status === status && halt.blocks_entry === (['halt_reported', 'resumption_scheduled', 'security_deleted'].includes(status) ? true : null), 'Halt classification disagrees with source evidence.');
  }
  function validatePrices(row, value) {
    const generated = dateMs(value.generated_at), observed = dateMs(value.sources.iex.checked_at), session = value.publication.applicable_session;
    for (const [key, fields] of [['trade', ['price']], ['quote', ['bid', 'ask', 'bid_size', 'ask_size']]]) {
      const datum = row[key];
      require(datum && ['recent', 'stale', 'missing', 'invalid', 'unavailable'].includes(datum.status), 'Unknown quote or trade status.');
      fields.forEach(field => require(datum[field] === null || finite(datum[field]) && datum[field] > 0 && datum[field] <= 1e15, 'Invalid quote or trade value.'));
      if (['missing', 'unavailable'].includes(datum.status)) require(datum.timestamp === null && fields.every(field => datum[field] === null), 'Missing quote claims observed values.');
      if (['recent', 'stale'].includes(datum.status)) {
        const stamp = dateMs(datum.timestamp);
        require(Number.isFinite(stamp) && fields.every(field => finite(datum[field])) && stamp <= observed + 5000, 'Quote timestamp or values are invalid.');
        require(datum.status === (generated - stamp <= QUOTE_AGE * 1000 && sessionAt(stamp) === session ? 'recent' : 'stale'), 'Quote freshness differs from its timestamp.');
        if (key === 'quote') require(datum.ask >= datum.bid && finite(datum.spread_usd) && Math.abs(datum.spread_usd - (datum.ask - datum.bid)) < 1e-6, 'Quote spread is invalid.');
      }
    }
    require(row.price_checks && ['trade', 'ask'].every(key => ['below_stop', 'below_entry_floor', 'below_trigger', 'within_published_band', 'above_limit', 'above_day2_extension', 'unknown'].includes(row.price_checks[key])), 'Unknown recorded price comparison.');
  }
  function validateCorporate(action, row, session) {
    require(action && action.version === 1 && action.coverage === 'manual_known_events_only' && action.symbol === row.ticker && action.session === session && HEX.test(action.registry_sha256) && typeof action.blocked === 'boolean' && Array.isArray(action.matches), 'Corporate-event evidence is invalid.');
    require(action.blocked === (action.matches.length > 0) && (action.blocked ? ['known_event', 'review_required'].includes(action.status) : action.status === 'not_in_registry'), 'Corporate-event status contradicts its sources.');
    action.matches.forEach(match => {
      require(match && typeof match.id === 'string' && match.id.length > 0 && match.symbol === row.ticker && match.kind === 'cash_acquisition' && /^\d{4}-\d\d-\d\d$/.test(match.active_from) && match.active_from <= session && (!match.active_until || match.active_until > session) && typeof match.reason === 'string' && Array.isArray(match.sources) && match.sources.length > 0 && match.sources.length <= 8, 'Corporate-event interval or sources are invalid.');
      match.sources.forEach(source => require(sourceURL(source.url) && HEX.test(source.sha256) && typeof source.title === 'string' && typeof source.quote === 'string' && /^\d{4}-\d\d-\d\d$/.test(source.published_on) && source.published_on <= session, 'Corporate-event source is invalid.'));
    });
  }
  function retainedAction(facts, ticker, session, generated) {
    require(Array.isArray(facts) && facts.length <= 128, 'Retained corporate-event list is invalid.');
    facts.forEach(fact => {
      require(fact && HEX.test(fact.registry_sha256) && Number.isFinite(dateMs(fact.observed_at)) && dateMs(fact.observed_at) <= generated + 5000, 'Retained corporate-event reference is invalid.');
      validateCorporate({ version: 1, coverage: 'manual_known_events_only', symbol: ticker, session, registry_sha256: fact.registry_sha256, blocked: true, status: 'known_event', matches: [fact.event] }, { ticker }, session);
    });
    return { matches: facts.map(fact => fact.event), reason: facts.map(fact => fact.event.reason).join(' ') };
  }
  function positiveFacts(value) {
    require(value && value.schema_version === 1 && value.dry_run === false && value.publication && HEX.test(value.publication.data_sha256) && /^\d{4}-\d\d-\d\d$/.test(value.publication.applicable_session), 'Public source-fact envelope is invalid.');
    const generated = dateMs(value.generated_at);
    require(Number.isFinite(generated) && generated <= now + 5000 && value.halt_memory && value.corporate_memory && typeof value.halt_memory === 'object' && !Array.isArray(value.halt_memory) && typeof value.corporate_memory === 'object' && !Array.isArray(value.corporate_memory), 'Public source-fact clock or memory is invalid.');
    require(Object.keys(value.halt_memory).length <= 100 && Object.values(value.corporate_memory).reduce((n, facts) => n + (Array.isArray(facts) ? facts.length : 129), 0) <= 128, 'Public source-fact limit exceeded.');
    Object.entries(value.halt_memory).forEach(([ticker, fact]) => {
      require(/^[A-Z0-9][A-Z0-9.\-/$]*$/.test(ticker) && fact && fact.halt && fact.halt.blocks_entry === true, 'Remembered source fact is not an exclusion.');
      validateHalt(fact.halt, fact.source, { ticker }, generated);
    });
    Object.entries(value.corporate_memory).forEach(([ticker, facts]) => retainedAction(facts, ticker, value.publication.applicable_session, generated));
    return value;
  }
  function applySourceMemory() {
    candidates().forEach(c => {
      const fact = sourceMemory.halts[c.ticker], events = sourceMemory.corporate[c.ticker];
      if (fact) rememberHalt(rowKey(c), fact.halt, fact.source, fact.source.checked_at);
      if (events && events.length) corporate.set(rowKey(c), { action: { matches: events.map(fact => fact.event), reason: events.map(fact => fact.event.reason).join(' ') }, at: events[0].observed_at });
    });
  }
  function ingestPositive(value) {
    positiveFacts(value);
    Object.entries(value.halt_memory).forEach(([ticker, fact]) => {
      const old = sourceMemory.halts[ticker];
      if (old && (old.halt.status === 'security_deleted' || dateMs(fact.source.source_published_at) < dateMs(old.source.source_published_at) || dateMs(fact.halt.events[0].halted_at) < dateMs(old.halt.events[0].halted_at))) return;
      if (old || Object.keys(sourceMemory.halts).length < 100) sourceMemory.halts[ticker] = fact;
    });
    Object.entries(value.corporate_memory).forEach(([ticker, facts]) => {
      const prior = sourceMemory.corporate[ticker] || (sourceMemory.corporate[ticker] = []);
      facts.forEach(fact => {
        const index = prior.findIndex(old => old.event.id === fact.event.id && old.event.active_from === fact.event.active_from);
        if (index >= 0) { if (dateMs(fact.observed_at) >= dateMs(prior[index].observed_at)) prior[index] = fact; }
        else if (Object.values(sourceMemory.corporate).reduce((n, list) => n + list.length, 0) < 128) prior.push(fact);
      });
      if (prior.length) sourceMemory.corporate[ticker] = prior;
    });
    applySourceMemory();
  }
  function resolutionFor(fact, value) {
    if (!freshStamp(value.generated_at, RECEIPT_AGE) || dateMs(value.expires_at) < now) return false;
    return (value.corporate_resolutions || []).some(proof => proof.event_id === fact.event.id && proof.symbol === fact.event.symbol && proof.active_from === fact.event.active_from && dateMs(proof.observed_at) >= dateMs(fact.observed_at));
  }
  function validateResolutions(value) {
    const proofs = value.corporate_resolutions;
    require(Array.isArray(proofs) && proofs.length <= 128, 'Corporate resolution list is invalid.');
    proofs.forEach(proof => {
      require(proof && typeof proof.event_id === 'string' && /^[A-Z][A-Z0-9.\-]*$/.test(proof.symbol) && HEX.test(proof.registry_sha256) && /^\d{4}-\d\d-\d\d$/.test(proof.registry_reviewed_on), 'Corporate resolution identity is invalid.');
      require(/^\d{4}-\d\d-\d\d$/.test(proof.active_from) && /^\d{4}-\d\d-\d\d$/.test(proof.active_until) && proof.active_from < proof.active_until && proof.active_until <= value.publication.applicable_session && proof.active_until <= proof.registry_reviewed_on, 'Corporate resolution interval is invalid.');
      const source = proof.resolution;
      require(source && sourceURL(source.url) && HEX.test(source.sha256) && typeof source.title === 'string' && typeof source.quote === 'string' && /^\d{4}-\d\d-\d\d$/.test(source.published_on) && source.published_on <= proof.active_until, 'Corporate resolution lacks a dated source.');
      require(Number.isFinite(dateMs(proof.observed_at)) && dateMs(proof.observed_at) <= dateMs(value.generated_at), 'Corporate resolution observation clock is invalid.');
    });
  }
  function resolveSourceMemory(value) {
    Object.entries(sourceMemory.halts).forEach(([ticker, fact]) => {
      const row = value.rows.find(row => row.ticker === ticker), old = { status: fact.halt.status, at: fact.source.checked_at, haltedAt: fact.halt.events[0].halted_at, sourcePublished: fact.source.source_published_at };
      if (row && resumes(old, row.events.halt, value)) delete sourceMemory.halts[ticker];
    });
    Object.entries(sourceMemory.corporate).forEach(([ticker, facts]) => {
      const incoming = value.corporate_memory[ticker] || [];
      const remaining = facts.filter(fact => incoming.some(next => next.event.id === fact.event.id && next.event.active_from === fact.event.active_from) || !resolutionFor(fact, value));
      if (remaining.length) sourceMemory.corporate[ticker] = remaining; else delete sourceMemory.corporate[ticker];
    });
    halted = new Map(); corporate = new Map(); applySourceMemory();
  }
  function savePublicFacts(value) {
    // Save only received public bytes with independently validated source facts
    // that retain every unresolved fact. Cached prices never become quote state.
    const keeps = Object.entries(sourceMemory.halts).every(([ticker, fact]) => value.halt_memory[ticker] && dateMs(value.halt_memory[ticker].source.source_published_at) >= dateMs(fact.source.source_published_at)) &&
      Object.entries(sourceMemory.corporate).every(([ticker, facts]) => facts.every(fact => (value.corporate_memory[ticker] || []).some(next => next.event.id === fact.event.id && next.event.active_from === fact.event.active_from)));
    if (!keeps) { storageIssue = 'The latest file omits earlier source evidence; this tab retains its earlier public receipt for reloads.'; return; }
    try {
      const saved = JSON.stringify(value);
      if (new TextEncoder().encode(saved).byteLength <= MAX_BYTES) w.sessionStorage.setItem(CACHE_KEY, saved);
    } catch (e) { storageIssue = 'This tab could not retain public halt/event evidence for reloads; coverage must be checked again at your broker.'; }
  }

  function validate(value) {
    if (!value || value.schema_version !== 1 || value.dry_run !== false || !value.publication || !Array.isArray(value.rows) || value.rows.length > 64) throw Error('Unsupported observation document or rehearsal receipt.');
    const p = value.publication, run = record.run || {}, timing = run.timing || {};
    if (!HEX.test(p.data_sha256) || p.data_sha256 !== (readerBinding ? readerBinding.canonicalSha : recordHash) ||
        readerBinding && (p.reader_projection_version !== 1 || p.reader_sha256 !== recordHash) ||
        p.context_sha256 !== (run.evidence || {}).context_sha256 || p.rules_version !== (record.app || {}).rules_version ||
        String(p.run_id) !== String(run.run_id) || p.measured_session !== run.session ||
        p.applicable_session !== timing.applicable_session || p.published_at !== run.published_at) throw Error('These observations belong to another publication.');
    if (!['observed', 'partial', 'provider_unavailable', 'no_tickets', 'inapplicable', 'invalid_publication'].includes(value.status)) throw Error('Unknown observation status.');
    const started = dateMs(value.collection_started_at), generated = dateMs(value.generated_at), expires = dateMs(value.expires_at);
    if (![started, generated, expires].every(Number.isFinite) || started > generated || generated > now + FUTURE_SKEW * 1000 || expires <= generated || expires - generated > RECEIPT_AGE * 1000) throw Error('Observation timestamps are invalid.');
    const policy = value.policy || {};
    if (policy.quote_max_age_seconds !== QUOTE_AGE || policy.trade_max_age_seconds !== QUOTE_AGE || policy.snapshot_max_age_seconds !== RECEIPT_AGE || policy.max_future_skew_seconds !== FUTURE_SKEW || policy.delayed_sip_min_delay_seconds !== 900 || policy.market_timezone !== 'America/New_York') throw Error('Observation freshness policy is unavailable.');
    require(value.status === 'inapplicable' ? value.rows.length === 0 && typeof value.reason === 'string' : value.rows.length === candidates().length && value.reason === null, 'Observation membership is incomplete.');
    require((value.status === 'no_tickets') === (!candidates().length && value.status !== 'inapplicable'), 'No-ticket status contradicts the publication.');
    for (const feed of ['iex', 'delayed_sip']) {
      const source = (value.sources || {})[feed];
      require(source && source.feed === feed && source.scope === (feed === 'iex' ? 'single_venue' : 'consolidated_delayed') && source.minimum_delay_seconds === (feed === 'iex' ? 0 : 900), 'Feed source or scope is invalid.');
      require(value.rows.length ? ['ok', 'unavailable'].includes(source.status) && source.entitlement === (source.status === 'ok' ? 'request_succeeded' : 'unavailable') && dateMs(source.checked_at) >= started && dateMs(source.checked_at) <= generated : source.status === 'not_requested' && source.entitlement === 'not_requested', 'Feed entitlement observation is invalid.');
    }
    const coverage = value.coverage || {};
    require(coverage.issuer_news && coverage.issuer_news.status === 'not_checked' && coverage.earnings && coverage.earnings.status === 'not_checked', 'Unsupported event coverage claim.');
    validateHaltSource(coverage.halts, generated);
    validateResolutions(value);
    require(value.halt_memory && typeof value.halt_memory === 'object' && !Array.isArray(value.halt_memory) && Object.keys(value.halt_memory).length <= 100 && value.corporate_memory && typeof value.corporate_memory === 'object' && !Array.isArray(value.corporate_memory), 'Retained event memory is invalid.');
    Object.entries(value.halt_memory).forEach(([ticker, fact]) => {
      require(fact && fact.halt && fact.halt.blocks_entry === true, 'Retained halt cannot claim clearance.');
      validateHalt(fact.halt, fact.source, { ticker }, generated);
    });
    require(Object.values(value.corporate_memory).reduce((n, facts) => n + (Array.isArray(facts) ? facts.length : 129), 0) <= 128, 'Retained corporate-event limit exceeded.');
    Object.entries(value.corporate_memory).forEach(([ticker, facts]) => retainedAction(facts, ticker, p.applicable_session, generated));
    const seen = new Set();
    value.rows.forEach(row => {
      if (!row || !['burst', 'anticipation'].includes(row.kind) || typeof row.ticker !== 'string') throw Error('Invalid observation row.');
      const key = row.kind + ':' + row.ticker, c = findCandidate(row.kind, row.ticker);
      if (!c || seen.has(key) || row.evidence_id !== (c.row.evidence || {}).id || !HEX.test(row.evidence_id) ||
          !HEX.test(row.plan_sha256) || row.plan_sha256 !== ((c.plan || {}).evidence_ref || {}).plan_sha256) throw Error('Observation row does not match an admitted published plan.');
      seen.add(key);
      const order = (c.plan || {}).order_json || {}, levels = row.levels || {};
      if (levels.trigger !== order.stop_price || levels.limit !== order.limit_price || levels.stop !== (order.then || {}).stop_price) throw Error('Observation price levels do not match the published order.');
      require(levels.entry_low === (row.kind === 'burst' ? c.plan.entry_low : c.plan.trigger) && levels.day2_spent_above === (row.kind === 'burst' ? c.plan.day2_spent_above || null : null), 'Observation entry-band levels differ.');
      validatePrices(row, value);
      validateHalt((row.events || {}).halt, coverage.halts, row, generated);
      validateCorporate((row.events || {}).corporate_action, row, p.applicable_session);
      retainedAction(row.events.retained_corporate_actions, row.ticker, p.applicable_session, generated);
      require(row.events.halt.blocks_entry !== true || value.halt_memory[row.ticker], 'A positive halt is missing its retained source fact.');
      require(row.events.corporate_action.matches.every(match => (value.corporate_memory[row.ticker] || []).some(fact => fact.event.id === match.id && fact.event.active_from === match.active_from)), 'A corporate exclusion is missing its retained source fact.');
    });
    return value;
  }
  function rememberHalts(value) {
    const before = JSON.stringify([Array.from(halted), Array.from(corporate)]);
    value.rows.forEach(row => {
      const halt = (row.events || {}).halt || {}, key = row.kind + ':' + row.ticker;
      const action = (row.events || {}).corporate_action || {};
      if (action.blocked === true) corporate.set(key, { action, at: value.generated_at });
      if (row.events.retained_corporate_actions.length) corporate.set(key, { action: retainedAction(row.events.retained_corporate_actions, row.ticker, value.publication.applicable_session, dateMs(value.generated_at)), at: row.events.retained_corporate_actions[0].observed_at });
      const events = Array.isArray(halt.events) ? halt.events : [];
      if (halt.blocks_entry === true && ['halt_reported', 'resumption_scheduled', 'security_deleted'].includes(halt.status) && events.length && sourceURL(halt.source_url)) {
        rememberHalt(key, halt, halt.retained_source || value.coverage.halts, value.generated_at);
      } else if (halt.status === 'resumption_reported' && events.length && sourceURL(halt.source_url)) {
        // A later quote or an omitted feed item is never a resumption event.
        const old = halted.get(key);
        if (old && resumes(old, halt, value)) halted.delete(key);
      }
    });
    candidates().forEach(c => {
      const memory = value.halt_memory[c.ticker], events = value.corporate_memory[c.ticker];
      if (memory) rememberHalt(rowKey(c), memory.halt, memory.source, memory.source.checked_at);
      if (events && events.length) corporate.set(rowKey(c), { action: retainedAction(events, c.ticker, value.publication.applicable_session, dateMs(value.generated_at)), at: events[0].observed_at });
    });
    return before !== JSON.stringify([Array.from(halted), Array.from(corporate)]);
  }
  function rememberHalt(key, halt, source, at) {
    const old = halted.get(key), event = halt.events[0];
    if (old && (old.status === 'security_deleted' || dateMs(source.source_published_at) < dateMs(old.sourcePublished) || dateMs(event.halted_at) < dateMs(old.haltedAt))) return;
    halted.set(key, { status: halt.status, reason: halt.reason, at, haltedAt: event.halted_at, sourcePublished: source.source_published_at, sourceSha: source.source_sha256, url: halt.source_url });
  }
  function resumes(old, halt, value) {
    const source = value.coverage.halts;
    return old.status !== 'security_deleted' && halt.status === 'resumption_reported' && freshStamp(value.generated_at, RECEIPT_AGE) && source.status === 'fresh' && dateMs(source.expires_at) >= now && dateMs(source.source_published_at) > dateMs(old.sourcePublished) && dateMs(value.generated_at) > dateMs(old.at) && dateMs(halt.events[0].halted_at) >= dateMs(old.haltedAt);
  }
  function preservesRestrictions(value) {
    for (const [key, old] of halted) {
      const row = value.rows.find(row => row.kind + ':' + row.ticker === key), halt = row && row.events.halt, ticker = key.slice(key.indexOf(':') + 1);
      if (value.halt_memory[ticker] || halt && halt.blocks_entry === true) continue;
      if (halt && resumes(old, halt, value)) continue;
      return false;
    }
    for (const [key] of corporate) {
      const row = value.rows.find(row => row.kind + ':' + row.ticker === key), ticker = key.slice(key.indexOf(':') + 1);
      const remembered = sourceMemory.corporate[ticker] || [];
      const incoming = [...(value.corporate_memory[ticker] || []), ...(row ? row.events.retained_corporate_actions : [])];
      if (!remembered.every(fact => incoming.some(next => next.event.id === fact.event.id && next.event.active_from === fact.event.active_from) || resolutionFor(fact, value))) return false;
    }
    return true;
  }
  function refusal(c) {
    if (!c || c.status !== 'ticket') return null;
    const halt = halted.get(rowKey(c));
    const event = corporate.get(rowKey(c));
    if (event) return 'Morning corporate-event exclusion, last checked ' + atCT(event.at) + '. ' + event.action.reason + ' Entry copying remains withheld; verify the sourced event and broker restrictions.';
    return halt ? 'Morning check: ' + words(halt.status) + ', last reported ' + atCT(halt.at) + '. ' + halt.reason + ' Entry copying is withheld until a sourced resumption is recorded; check your broker.'
      : !receipt && ['unbound', 'loading'].includes(state) ? 'Checking published morning halt evidence; entry copying is briefly paused while this record is matched.' : null;
  }
  async function readBounded(response) {
    if (!response.ok) throw Error('The published morning file could not be read.');
    const length = Number(response.headers.get('content-length'));
    if (Number.isFinite(length) && length > MAX_BYTES) throw Error('Observation document exceeds the size limit.');
    if (!response.body || !response.body.getReader) throw Error('Bounded observation reading is unavailable.');
    const reader = response.body.getReader(), decoder = new TextDecoder('utf-8', { fatal: true });
    let bytes = 0, text = '';
    try {
      while (true) {
        const part = await reader.read();
        if (part.done) break;
        bytes += part.value.byteLength;
        if (bytes > MAX_BYTES) { await reader.cancel(); throw Error('Observation document exceeds the size limit.'); }
        text += decoder.decode(part.value, { stream: true });
      }
      return text + decoder.decode();
    } finally { reader.releaseLock(); }
  }
  async function reload() {
    if (!recordHash || state === 'practice') return;
    const token = epoch, request = ++sequence;
    if (controller) controller.abort();
    controller = new AbortController();
    const active = controller, timeout = w.setTimeout(() => active.abort(), 15000);
    state = 'loading'; issue = ''; paintAll();
    try {
      const url = new URL('morning.json', w.location.href);
      if (url.origin !== w.location.origin || !['http:', 'https:'].includes(url.protocol)) throw Error('Same-origin observations are unavailable.');
      url.hash = ''; url.search = '';
      const response = await w.fetch(url.href, { cache: 'no-store', credentials: 'omit', mode: 'same-origin', redirect: 'error', signal: active.signal });
      const raw = await readBounded(response);
      if (token !== epoch || request !== sequence) return;
      if (!pinned) now = Date.now();
      const parsed = JSON.parse(raw);
      ingestPositive(parsed);
      savePublicFacts(parsed);
      const next = validate(parsed);
      if (receipt && dateMs(next.generated_at) < dateMs(receipt.generated_at)) throw Error('An older observation file was not loaded.');
      require(preservesRestrictions(next), 'A previous event exclusion was omitted without a sourced resolution; it remains withheld.');
      receipt = next; state = 'loaded'; issue = '';
      rememberHalts(next);
      resolveSourceMemory(next); savePublicFacts(next);
      paintAll(); if (onChange) onChange();
    } catch (e) {
      if (token !== epoch || request !== sequence) return;
      state = 'unavailable'; issue = e && e.message || 'Observation file unavailable.'; paintAll(); if (onChange) onChange();
    } finally { w.clearTimeout(timeout); }
  }
  function reset(data, at, clockPinned) {
    epoch++; sequence++;
    if (controller) controller.abort();
    record = data; recordHash = null; readerBinding = null; receipt = null; halted = new Map(); corporate = new Map(); issue = ''; storageIssue = ''; cachedHalt = false; pinned = !!clockPinned;
    state = data && data.fixture ? 'practice' : 'unbound'; now = at ? new Date(at).getTime() : Date.now();
    if (state !== 'practice') applySourceMemory();
    paintAll();
  }
  async function bind(data, raw, projection) {
    if (record !== data || state === 'practice') return;
    const token = epoch;
    readerBinding = projection || null;
      try {
        const saved = w.sessionStorage.getItem(CACHE_KEY);
        if (saved) {
          require(saved.length <= MAX_BYTES && new TextEncoder().encode(saved).byteLength <= MAX_BYTES, 'Cached evidence exceeds its limit.');
          ingestPositive(JSON.parse(saved)); cachedHalt = halted.size > 0 || corporate.size > 0;
        }
      } catch (e) {
        storageIssue = 'Earlier tab source evidence could not be verified and was ignored; this does not establish event clearance.';
        try { w.sessionStorage.removeItem(CACHE_KEY); } catch (ignored) { /* storage remains optional */ }
      }
    if (!w.crypto || !w.crypto.subtle || !w.TextEncoder || typeof raw !== 'string') { state = 'unavailable'; issue = 'Exact publication verification is unavailable in this browser.'; paintAll(); if (onChange) onChange(); return; }
    try {
      const digest = await w.crypto.subtle.digest('SHA-256', new TextEncoder().encode(raw));
      if (token !== epoch || record !== data) return;
      recordHash = Array.from(new Uint8Array(digest), n => n.toString(16).padStart(2, '0')).join('');
      await reload();
    } catch (e) {
      if (token !== epoch) return;
      state = 'unavailable'; issue = 'Exact publication verification failed.'; paintAll(); if (onChange) onChange();
    }
  }

  function headline() {
    if (state === 'practice') return 'Practice record — no market observations requested';
    if (state === 'unbound') return 'Morning observations not yet verified';
    if (state === 'loading') return 'Reading the published morning file…';
    if (state === 'unavailable') return 'Morning observations unavailable';
    if (halted.size || corporate.size) return 'Entry copying withheld by a sourced event check';
    if (!receiptFresh()) return 'Morning observations are stale';
    if (receipt.rows.length && !receipt.rows.every(quotesCurrent)) return 'Quote observations are stale or incomplete';
    return ({ observed: 'Morning snapshot available', partial: 'Morning check is incomplete', provider_unavailable: 'Market provider unavailable', no_tickets: 'No admitted tickets to check', inapplicable: 'Morning check is outside its session', invalid_publication: 'Publication could not be checked' })[receipt.status] || 'Morning check unavailable';
  }
  function line(host, label, value, attrs) {
    const p = node('p', Object.assign({ class: 'sc-hint' }, attrs));
    p.append(node('strong', {}, label + ' '), d.createTextNode(value)); host.append(p);
  }
  function source(host, label, value) {
    const url = sourceURL(value);
    if (url) host.append(node('a', { href: url, target: '_blank', rel: 'noopener noreferrer', 'data-observation-link': url }, label));
  }
  function paintHost(host, descriptor) {
    const body = host.querySelector('[data-observation-body]'), title = host.querySelector('[data-observation-heading]');
    const active = body.contains(d.activeElement) && d.activeElement.getAttribute('data-observation-link');
    body.replaceChildren();
    const c = descriptor.candidate, row = c && rowFor(c), blocked = c && refusal(c);
    title.textContent = descriptor.kind === 'summary' ? headline() : 'Morning quote check · ' + (c.status !== 'ticket' ? 'not requested' : blocked ? 'entry restricted' : !row ? 'unavailable' : !quotesCurrent(row) ? 'stale or incomplete' : 'dated snapshot');
    host.setAttribute('data-observation-state', state === 'loaded' && (!receiptFresh() || row && !quotesCurrent(row)) ? 'stale' : state);
    if (issue) line(body, 'File status:', issue);
    if (storageIssue) line(body, 'Reload coverage:', storageIssue);
    if (cachedHalt) line(body, 'Earlier public evidence:', 'A sourced halt or event exclusion was retained in this tab. Cached evidence is not a new quote check.');
    if (!c) candidates().forEach(candidate => {
      if (halted.has(rowKey(candidate)) || corporate.has(rowKey(candidate))) line(body, candidate.ticker + ' — entry withheld:', refusal(candidate), { class: 'sc-note', 'data-observation-refusal': '' });
    });
    if (receipt) line(body, state === 'unavailable' ? 'Last available receipt:' : 'Checked:', atCT(receipt.generated_at) + ' · ' + ageWords(receipt.generated_at, now) + (receiptFresh() ? '' : ' · receipt expired'), { 'data-observation-time': '' });
    if (c && c.status !== 'ticket') {
      line(body, 'No quote check requested.', 'This setup has no admitted published order. A quote cannot change that refusal.');
    } else if (c && !row) {
      line(body, 'No matching quote check.', 'Verify current quote, spread and trading status at your broker.');
    } else if (row) {
      const q = row.quote || {}, t = row.trade || {}, quoteFresh = receiptFresh() && freshStamp(q.timestamp, QUOTE_AGE), tradeFresh = receiptFresh() && freshStamp(t.timestamp, QUOTE_AGE);
      line(body, 'IEX quote:', 'bid ' + money(q.bid) + ' · ask ' + money(q.ask) + ' · spread ' + money(q.spread_usd) + (finite(q.spread_pct) ? ' (' + q.spread_pct.toFixed(3) + '%)' : ''), { 'data-observation-quote': '' });
      line(body, 'Quote time:', atCT(q.timestamp) + ' · ' + ageWords(q.timestamp, now) + ' · ' + (quoteFresh ? words(q.status) : 'stale or unavailable'), { 'data-observation-quote-age': '' });
      line(body, 'Quoted size:', (finite(q.bid_size) ? q.bid_size : 'unknown') + ' bid · ' + (finite(q.ask_size) ? q.ask_size : 'unknown') + ' ask, as supplied by IEX. This does not establish executable liquidity.');
      line(body, 'Last IEX trade:', money(t.price) + ' · ' + atCT(t.timestamp) + ' · ' + (tradeFresh ? words(t.status) : 'stale or unavailable'));
      const checks = row.price_checks || {};
      line(body, 'Against published levels:', 'last trade ' + words(checks.trade) + '; ask ' + words(checks.ask) + '. These dated comparisons are not an entry or cancellation instruction.', { 'data-observation-comparison': '' });
      const volume = row.delayed_volume || {};
      line(body, 'Delayed SIP volume:', words(volume.status) + ' · ' + (finite(volume.partial_volume) ? volume.partial_volume.toLocaleString('en-US') + ' partial shares' : 'partial volume unavailable') + ' · ' + words(volume.comparison) + '. Consolidated data is delayed at least 15 minutes.');
      line(body, 'Bar timestamps:', atCT(volume.daily_timestamp) + ' · prior ' + atCT(volume.previous_timestamp) + '. These label sessions; the volume data-through time is unavailable.');
      const halt = (row.events || {}).halt || {};
      line(body, 'Halt check:', words(halt.status) + '. ' + (halt.reason || 'Halt coverage is unknown; verify with your broker.'), { 'data-observation-halt': '' });
      source(body, 'Halt source', halt.source_url);
      const action = (row.events || {}).corporate_action || {};
      line(body, 'Corporate actions:', action.blocked ? action.reason : 'Bounded manual registry only; absence is not event clearance.');
      (action.matches || []).forEach(match => (match.sources || []).forEach(link => source(body, link.title, link.url)));
    }
    if (blocked) {
      line(body, 'Entry copying withheld:', blocked, { class: 'sc-note', 'data-observation-refusal': '' });
      const event = corporate.get(rowKey(c)), halt = halted.get(rowKey(c));
      if (halt) source(body, 'Retained halt source', halt.url);
      if (event) (event.action.matches || []).forEach(match => (match.sources || []).forEach(link => source(body, link.title, link.url)));
    }
    if (!c && receipt) {
      line(body, 'Coverage:', receipt.rows.length + ' admitted published plans in this receipt. ' + (receipt.reason || ''));
      const coverage = receipt.coverage || {}, halt = coverage.halts || {};
      line(body, 'Trading halts:', words(halt.status === 'fresh' && dateMs(halt.expires_at) < now ? 'stale' : halt.status) + ' · ' + (halt.scope || 'coverage unknown') + ' · ' + atCT(halt.checked_at));
      source(body, 'Halt source', halt.source_url);
    }
    if (receipt) for (const feed of ['iex', 'delayed_sip']) {
      const observed = receipt.sources[feed];
      line(body, feed === 'iex' ? 'IEX access:' : 'Delayed SIP access:', words(observed.entitlement) + ' · ' + atCT(observed.checked_at) + (observed.error_kind ? ' · ' + words(observed.error_kind) : '') + '. This describes that request, not a future entitlement guarantee.');
    }
    line(body, 'Feed limits:', 'IEX is a single venue, not the consolidated market. Delayed SIP is at least 15 minutes behind. Quote/trade observations expire after 60 seconds; a receipt expires after 5 minutes.');
    line(body, 'Still to verify:', 'Current broker quote, spread and trading status; issuer news, earnings and corporate actions. A morning snapshot is not comprehensive event clearance or permission to trade.');
    if (active) {
      const replacement = Array.from(body.querySelectorAll('[data-observation-link]')).find(n => n.getAttribute('data-observation-link') === active);
      if (replacement) replacement.focus({ preventScroll: true });
    }
    const reloadButton = host.querySelector('[data-observation-reload]');
    if (reloadButton) reloadButton.disabled = !recordHash || state === 'loading';
  }
  function paintAll() {
    hosts.forEach((descriptor, host) => { if (!host.isConnected) hosts.delete(host); else paintHost(host, descriptor); });
  }
  function mount(kind, candidate) {
    const host = node(kind === 'summary' ? 'section' : 'details', { class: kind === 'summary' ? 'ss-observations' : 'sc-disclosure ss-observations', 'data-observations': kind });
    const title = node(kind === 'summary' ? 'h3' : 'summary', { 'data-observation-heading': '' });
    host.append(title, node('div', { 'data-observation-body': '' }));
    if (kind === 'summary') {
      const button = node('button', { class: 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', 'data-observation-reload': '' }, 'Reload published observations');
      button.addEventListener('click', reload); host.append(button);
      host.append(node('p', { class: 'sc-hint' }, 'Reload reads the latest static morning file. It does not request a new market quote or start a provider refresh.'));
    } else host.id = 'disc-observations';
    const descriptor = { kind, candidate }; hosts.set(host, descriptor); paintHost(host, descriptor); return host;
  }
  api.observations = {
    reset, bind, reload, refusal, summary: () => mount('summary'), detail: c => mount('detail', c),
    validateHaltEvidence: (halt, coverage, ticker, at) => validateHalt(halt, coverage, { ticker }, dateMs(at)),
    clock: at => { now = new Date(at).getTime(); paintAll(); },
    onChange: handler => { onChange = handler; },
    facts: () => ({ state, recordHash, canonicalHash: readerBinding ? readerBinding.canonicalSha : recordHash, projected: !!readerBinding, headline: headline(), generatedAt: receipt && receipt.generated_at, fresh: receiptFresh(), pending: !receipt && ['unbound', 'loading'].includes(state), restricted: [...new Set([...halted.keys(), ...corporate.keys()])] })
  };
})(window);
