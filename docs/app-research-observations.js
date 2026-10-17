/* Dated IEX observations of the current research cohort's allocation-fit rows.
   A supplement to the stop-width research panel: it binds the exact publication,
   the exact cohort receipt and bundle and each row's original evidence, prints
   a single-venue snapshot beside the row, and creates no ready label, size,
   order or entry permission. Halts, volume, issuer news and earnings are not
   checked by this file, and it says so. */
(function (w) {
  'use strict';
  const api = w.SCStock = w.SCStock || {}, d = w.document;
  const MAX_BYTES = 64 * 1024, TIMEOUT_MS = 15000, QUOTE_AGE_MS = 60000, RECEIPT_AGE_MS = 300000, SKEW_MS = 5000, MAX_COLLECTION_MS = 180000;
  const HEX = /^[a-f0-9]{64}$/;
  const POLICY = { version: 1, feed: 'iex', max_requests_per_run: 1, selection: 'allocation_fit_rows_of_the_bound_registered_cohort',
    cohort_policy_id: 'anticipation_stop_width_4_to_5_v1', cohort_schema_version: 1, quote_max_age_seconds: 60, trade_max_age_seconds: 60,
    snapshot_max_age_seconds: 300, max_future_skew_seconds: 5, preopen_minutes: 30, max_collection_seconds: 180, market_timezone: 'America/New_York' };
  const LIMITS = ['dated_best_effort_snapshot', 'iex_single_venue_not_consolidated', 'no_delayed_volume_request', 'halts_news_earnings_not_checked',
    'research_rows_are_not_tickets', 'no_ready_label_or_entry_authority', 'no_personal_sizing_or_cash', 'broker_verification_required'];
  const COVERAGE = { halts: 'not_checked', delayed_volume: 'not_requested', issuer_news: 'not_checked', earnings: 'not_checked', corporate_action: 'archived_cohort_registry_only' };
  const STATUSES = ['observed', 'partial', 'provider_unavailable', 'no_research_rows', 'inapplicable'];
  const REASONS = [null, 'wrong_session', 'entry_window_ended', 'before_collection_window', 'stale_publication', 'future_publication', 'cohort_missing', 'cohort_not_current'];
  const SOURCE_ERRORS = [null, 'missing_credentials', 'authentication', 'entitlement', 'rate_limit', 'timeout', 'provider_error'];
  const QUOTE_STATES = ['recent', 'stale', 'missing', 'invalid', 'unavailable'];
  const PRICE_STATES = ['below_stop', 'below_entry_floor', 'below_trigger', 'within_published_band', 'above_limit', 'above_day2_extension', 'unknown'];
  const ENVELOPE = 'schema_version collection_started_at generated_at expires_at observation_run_id previous_observation_sha256 dry_run publication cohort policy status reason entry_phase source coverage rows limits';
  const object = x => !!x && typeof x === 'object' && !Array.isArray(x);
  const require = (ok, why) => { if (!ok) throw Error(why); };
  const canonical = x => Array.isArray(x) ? x.map(canonical) : object(x) ? Object.fromEntries(Object.keys(x).sort().map(k => [k, canonical(x[k])])) : x;
  const equal = (a, b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
  const keys = (x, names) => object(x) && equal(Object.keys(x).sort(), names.split(' ').sort());
  const finite = x => typeof x === 'number' && Number.isFinite(x);
  const price = x => finite(x) && x > 0 && x <= 1e15;
  const day = x => typeof x === 'string' && /^\d{4}-\d\d-\d\d$/.test(x) && Number.isFinite(Date.parse(x)) && new Date(x).toISOString().slice(0, 10) === x;
  // The producer retains microseconds. Date.parse truncates them, which would
  // move a print across the exact 60-second age or five-second future boundary.
  const micros = x => {
    const match = typeof x === 'string' && /^(\d{4}-\d\d-\d\d)T(\d\d):(\d\d):(\d\d)(?:\.(\d{1,6}))?(Z|[+-](\d\d):(\d\d))$/.exec(x);
    if (!match || !day(match[1]) || Number(match[2]) >= 24 || Number(match[3]) >= 60 || Number(match[4]) >= 60 ||
      match[6] !== 'Z' && (Number(match[7]) >= 24 || Number(match[8]) >= 60)) return null;
    const whole = Date.parse(match[1] + 'T' + match[2] + ':' + match[3] + ':' + match[4] + match[6]);
    return Number.isFinite(whole) ? BigInt(whole) * 1000n + BigInt((match[5] || '').padEnd(6, '0')) : null;
  };
  const instant = x => { const value = micros(x); return value === null ? NaN : Number(value) / 1000; };
  const clockMicros = () => api.now ? micros(api.now instanceof Date ? api.now.toISOString() : api.now) : BigInt(Date.now()) * 1000n;
  const clock = () => api.now ? new Date(api.now).getTime() : Date.now();
  const atCT = x => Number.isFinite(instant(x)) ? new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit' }).format(new Date(x)) + ' CT' : 'time unavailable';
  const money = x => finite(x) ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 4 }).format(x) : 'unavailable';
  const ageWords = (stamp, now) => {
    const seconds = (now - instant(stamp)) / 1000;
    const plural = (n, unit) => n + ' ' + unit + (n === 1 ? '' : 's') + ' old';
    return !Number.isFinite(seconds) ? 'age unavailable' : seconds < -5 ? 'timestamp is in the future' : seconds < 60 ? plural(Math.max(0, Math.floor(seconds)), 'second') : seconds < 3600 ? plural(Math.floor(seconds / 60), 'minute') : plural(Math.floor(seconds / 3600), 'hour');
  };
  const sessionAt = stamp => {
    const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(stamp)).map(part => [part.type, part.value]));
    return parts.year + '-' + parts.month + '-' + parts.day;
  };
  const fingerprint = () => api.observations ? api.observations.facts() : {};
  const STATE_WORDS = { below_stop: 'at or below the published stop', below_entry_floor: 'below the published trigger', below_trigger: 'below the published trigger',
    within_published_band: 'between the published trigger and limit (a position, not a signal)', above_limit: 'above the published limit',
    above_day2_extension: 'above the published extension line', unknown: 'unknown — no recent observation' };
  const REASON_WORDS = { wrong_session: 'collected on a day other than the applicable session', entry_window_ended: 'collected after the entry window ended',
    before_collection_window: 'collected before the half-hour collection window', stale_publication: 'the publication was not the newest completed session',
    future_publication: 'the publication clock was in the future', cohort_missing: 'no research cohort was published at collection time',
    cohort_not_current: 'the published cohort belonged to another publication' };
  const SOURCE_WORDS = { missing_credentials: 'no provider credentials were configured', authentication: 'the provider refused the credentials', entitlement: 'the feed was not entitled',
    rate_limit: 'the provider rate limit was reached', timeout: 'the provider request timed out', provider_error: 'the provider returned an error' };

  let record = null, identity = '', cohort = null, receipt = null, observation = null, hosts = new Map(), summaryHost = null;
  let state = 'deferred', issue = '', epoch = 0, controller = null, pending = null;

  function node(tag, attrs, value) {
    const el = d.createElement(tag);
    Object.entries(attrs || {}).forEach(([key, val]) => el.setAttribute(key, val));
    if (value !== undefined) el.textContent = value;
    return el;
  }
  function paragraph(host, label, value, attrs) {
    const p = node('p', Object.assign({ class: 'sc-hint' }, attrs || {}));
    if (label) p.append(node('strong', {}, label + ' '));
    p.append(d.createTextNode(value)); host.append(p);
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
    'This dated observation belongs to another publication.');
  }
  function priceState(value, levels, status) {
    if (status !== 'recent' || !price(value)) return 'unknown';
    if (value <= levels.stop) return 'below_stop';
    if (value < levels.entry_low) return 'below_entry_floor';
    if (levels.day2_spent_above !== null && value > levels.day2_spent_above) return 'above_day2_extension';
    if (value > levels.limit) return 'above_limit';
    if (value < levels.trigger) return 'below_trigger';
    return 'within_published_band';
  }
  function validateDatum(datum, fields, generated, observed, session) {
    require(object(datum) && QUOTE_STATES.includes(datum.status), 'Unknown quote or trade state.');
    fields.forEach(field => require(datum[field] === null || price(datum[field]), 'Invalid quote or trade value.'));
    require(datum.timestamp === null || Number.isFinite(instant(datum.timestamp)), 'Invalid quote or trade time.');
    require(datum.conditions === null || Array.isArray(datum.conditions) && datum.conditions.length <= 32 && datum.conditions.every(x => typeof x === 'string' && x.length > 0 && x.length <= 16), 'Invalid quote conditions.');
    if (['missing', 'unavailable'].includes(datum.status)) {
      require(datum.timestamp === null && fields.every(field => datum[field] === null), 'A missing observation claims values.');
      return;
    }
    if (['recent', 'stale'].includes(datum.status)) {
      const stamp = micros(datum.timestamp);
      const exchanges = 'ask' in datum ? ['bid_exchange', 'ask_exchange'] : ['exchange'];
      require(fields.every(field => price(datum[field])) && datum.conditions !== null &&
        exchanges.every(field => typeof datum[field] === 'string' && datum[field].length > 0 && datum[field].length <= 32) &&
        stamp !== null && observed !== null && stamp <= observed + BigInt(SKEW_MS) * 1000n, 'Observed values or time are invalid.');
      require(datum.status === (generated - stamp <= BigInt(QUOTE_AGE_MS) * 1000n && sessionAt(Number(stamp / 1000n)) === session ? 'recent' : 'stale'), 'Freshness differs from the provider timestamp.');
      if ('ask' in datum) {
        const delta = datum.ask - datum.bid, midpoint = datum.bid / 2 + datum.ask / 2;
        const percentage = delta / midpoint * 100;
        // The producer rounds both spread fields to eight decimal places. Allow
        // that half-unit plus binary floating-point representation at a tie.
        // At 2**26 and above float spacing exceeds 1e-8, so rounding to eight
        // decimals preserves the original float and needs exact equality.
        const roundedMatch = (given, derived) => finite(given) && finite(derived) &&
          (Math.abs(derived) >= 2 ** 26 ? given === derived :
            Math.abs(given - derived) <= 5e-9 + Number.EPSILON * Math.max(1, Math.abs(derived)));
        require(delta >= 0 && finite(midpoint) && midpoint > 0 &&
          roundedMatch(datum.spread_usd, delta) && roundedMatch(datum.spread_pct, percentage), 'Quote spread is invalid.');
      }
    }
  }
  function validate(value) {
    require(keys(value, ENVELOPE) && value.schema_version === 1 && typeof value.dry_run === 'boolean' && (value.dry_run === false || record.fixture === true), 'Dated observation envelope is unsupported.');
    binding(value.publication);
    require(equal(value.publication, receipt.publication), 'The dated observation is bound to a publication other than this cohort’s.');
    require(equal(value.policy, POLICY) && equal(value.limits, LIMITS) && equal(value.coverage, COVERAGE), 'Dated observation policy or coverage differs.');
    require(typeof value.observation_run_id === 'string' && value.observation_run_id.length > 0 && value.observation_run_id.length <= 128, 'Observation run identity is invalid.');
    require(value.previous_observation_sha256 === null || HEX.test(value.previous_observation_sha256), 'Prior observation binding is invalid.');
    const c = value.cohort;
    require(keys(c, 'receipt_sha256 bundle_sha256 bundle_path bundle_bytes policy_id generated_at status applicable_session bound') &&
      c.receipt_sha256 === cohort.receiptSha && c.bundle_sha256 === receipt.bundle.sha256 && c.bundle_path === receipt.bundle.path && c.bundle_bytes === receipt.bundle.bytes &&
      c.policy_id === receipt.policy.id && c.generated_at === receipt.timing.generated_at && c.status === receipt.status && c.applicable_session === receipt.publication.applicable_session && c.bound === true,
    'The dated observation describes another research cohort.');
    const started = micros(value.collection_started_at), generated = micros(value.generated_at), expires = micros(value.expires_at), now = clockMicros();
    require([started, generated, expires, now].every(value => value !== null) && started <= generated && expires === generated + BigInt(RECEIPT_AGE_MS) * 1000n && generated - started <= BigInt(MAX_COLLECTION_MS) * 1000n && generated <= now + BigInt(SKEW_MS) * 1000n, 'Observation clocks are invalid.');
    require(REASONS.includes(value.reason) && STATUSES.includes(value.status) && ['upcoming', 'open', 'ended', 'unknown'].includes(value.entry_phase), 'Observation outcome is unknown.');
    const timing = record.run.timing || {}, opens = micros(timing.opens_at), cutoff = micros(timing.cutoff_at);
    if (value.reason === null) require(opens !== null && cutoff !== null && started >= opens - BigInt(POLICY.preopen_minutes * 60000) * 1000n && started < cutoff && sessionAt(Number(started / 1000n)) === receipt.publication.applicable_session, 'An applicable observation sits outside its collection window.');
    const expected = value.reason === null && receipt.status === 'recorded' ? cohort.bundle.rows.filter(row => row.research.allocation_fit) : [];
    require(Array.isArray(value.rows) && value.rows.length === expected.length, 'Observation rows differ from the cohort’s allocation fits.');
    const source = value.source;
    require(keys(source, 'status feed scope entitlement checked_at error_kind minimum_delay_seconds requests') && source.feed === 'iex' && source.scope === 'single_venue' && source.minimum_delay_seconds === 0 &&
      SOURCE_ERRORS.includes(source.error_kind) && Number.isInteger(source.requests) && source.requests >= 0 && source.requests <= POLICY.max_requests_per_run, 'Source metadata is invalid.');
    if (!expected.length) {
      require(source.status === 'not_requested' && source.entitlement === 'not_requested' && source.checked_at === null && source.error_kind === null && source.requests === 0, 'An inapplicable observation requested a provider.');
    } else {
      const checked = micros(source.checked_at);
      require(checked !== null && started <= checked && checked <= generated, 'Provider check time is invalid.');
      require((source.status === 'ok' && source.entitlement === 'request_succeeded' && source.error_kind === null) || (source.status === 'unavailable' && source.entitlement === 'unavailable' && source.error_kind !== null), 'Source status contradicts its error.');
      require(source.requests === (source.error_kind === 'missing_credentials' ? 0 : 1), 'Request count differs from the budget.');
    }
    const observed = micros(source.checked_at), session = receipt.publication.applicable_session;
    let allRecent = true;
    value.rows.forEach((row, index) => {
      const original = expected[index], levels = original.levels;
      require(keys(row, 'rank ticker kind evidence projection_sha256 levels event trade quote price_checks') && row.rank === original.rank && row.ticker === original.ticker && row.kind === 'anticipation' &&
        equal(row.evidence, original.evidence) && row.projection_sha256 === original.research.projection_sha256 && equal(row.event, original.event) &&
        equal(row.levels, { trigger: levels.trigger, limit: levels.limit, stop: levels.stop, entry_low: levels.trigger, day2_spent_above: null }), 'A row’s identity, evidence or levels differ from the cohort.');
      validateDatum(row.trade, ['price'], generated, observed, session);
      validateDatum(row.quote, ['bid', 'ask', 'bid_size', 'ask_size'], generated, observed, session);
      if (source.status !== 'ok') require(row.trade.status === 'unavailable' && row.quote.status === 'unavailable', 'A failed source claims a price.');
      require(keys(row.price_checks, 'trade ask') && PRICE_STATES.includes(row.price_checks.trade) && PRICE_STATES.includes(row.price_checks.ask) &&
        row.price_checks.trade === priceState(row.trade.price, row.levels, row.trade.status) && row.price_checks.ask === priceState(row.quote.ask, row.levels, row.quote.status), 'A price comparison differs from its levels.');
      if (row.trade.status !== 'recent' || row.quote.status !== 'recent') allRecent = false;
    });
    const status = value.reason ? 'inapplicable' : !value.rows.length ? 'no_research_rows' : source.status === 'unavailable' ? 'provider_unavailable' : allRecent ? 'observed' : 'partial';
    require(value.status === status, 'Observation status contradicts its measurements.');
    return value;
  }
  async function read(response) {
    if (!response.ok || response.redirected) {
      if (response.body && !response.body.locked) await response.body.cancel().catch(() => {});
      throw Error(response.status === 404 ? 'No dated observation has been published for this cohort.' : 'The published dated observation is unavailable.');
    }
    const length = Number(response.headers.get('content-length'));
    if (Number.isFinite(length) && length > MAX_BYTES) {
      if (response.body && !response.body.locked) await response.body.cancel().catch(() => {});
      throw Error('The published dated observation exceeds its size limit.');
    }
    require(response.body && response.body.getReader, 'Bounded reading is unavailable in this browser.');
    const reader = response.clone().body.getReader();
    let size = 0;
    try {
      while (true) {
        const next = await reader.read(); if (next.done) break;
        size += next.value.byteLength;
        require(size <= MAX_BYTES, 'The published dated observation exceeds its size limit.');
      }
      const bytes = new Uint8Array(await response.arrayBuffer());
      require(bytes.byteLength === size, 'The dated observation changed during reading.');
      return bytes;
    } catch (error) {
      await Promise.allSettled([reader.cancel(), response.body.cancel()]); throw error;
    } finally { reader.releaseLock(); }
  }
  const decode = bytes => new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);

  // keep: a pressed reload holds the verified observation until a newer file
  // validates, and a failed read leaves it on screen with the failure named.
  async function load(keep) {
    if (pending) return pending;
    if (!record || !cohort || !fingerprint().recordHash) { state = 'deferred'; paint(); return false; }
    const kept = keep && state === 'loaded' && observation ? observation : null;
    const token = epoch, target = record, mine = cohort, active = new AbortController(); controller = active;
    state = 'loading'; issue = ''; paint();
    let timer, timedOut = false;
    const deadline = new Promise((resolve, reject) => { timer = w.setTimeout(() => {
      timedOut = true; active.abort(); reject(Error('The dated observation timed out after 15 seconds.'));
    }, TIMEOUT_MS); });
    const reading = Promise.resolve().then(async () => {
      const base = new URL('research-observations.json', w.location.href);
      require(['http:', 'https:'].includes(base.protocol) && base.origin === w.location.origin && !base.search && !base.hash, 'Dated observations must use this public origin.');
      const options = { cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer', mode: 'same-origin', redirect: 'error', signal: active.signal };
      const bytes = await read(await w.fetch(base.href, options));
      require(token === epoch && target === record && mine === cohort && !active.signal.aborted, 'The cohort changed during observation loading.');
      return validate(JSON.parse(decode(bytes)));
    });
    pending = Promise.race([reading, deadline]).then(result => {
      if (token !== epoch || target !== record || mine !== cohort || active.signal.aborted) return false;
      observation = result; state = 'loaded'; issue = ''; paint(); return true;
    }, error => {
      if (token !== epoch || target !== record || mine !== cohort) return false;
      const why = timedOut ? 'The dated observation timed out after 15 seconds.' : error && error.message || 'The published dated observation is unavailable.';
      if (kept) { observation = kept; state = 'loaded'; issue = 'A re-read failed (' + why + ') This is the last verified observation.'; }
      else { state = 'unavailable'; issue = why; }
      paint(); return false;
    }).finally(() => { w.clearTimeout(timer); if (token === epoch) { controller = null; pending = null; } });
    return pending;
  }
  function summaryWords(now) {
    if (state === 'loading') return 'Checking for a dated IEX observation of these research rows…';
    if (state === 'unavailable') return issue;
    if (state !== 'loaded' || !observation) return 'A dated IEX observation of these research rows loads with the comparison. None is a ready signal.';
    const fits = observation.rows.length, when = atCT(observation.generated_at), expired = now > instant(observation.expires_at);
    if (observation.reason) return 'No dated observation applies to this cohort: ' + REASON_WORDS[observation.reason] + ' (' + when + '). Zero provider requests were made.';
    if (observation.status === 'no_research_rows') return 'This cohort has no allocation-fit research row, so no price was observed (' + when + '). Zero provider requests were made.';
    const failed = issue ? ' ' + issue : '';
    const lead = (expired ? 'Expired dated observation' : 'Dated observation') + ' · ' + when + ' · ' + ageWords(observation.generated_at, now) + ' · ' + fits + (fits === 1 ? ' research row' : ' research rows') + ' · ' + (observation.source.requests === 0 ? 'zero IEX snapshot requests' : 'one IEX snapshot request');
    if (observation.status === 'provider_unavailable') return lead + ' · IEX unavailable: ' + (SOURCE_WORDS[observation.source.error_kind] || 'the source failed') + '. No price was observed.' + failed;
    return lead + (observation.status === 'partial' ? ' · some prices were stale, invalid or missing' : '') + '. Single venue, not consolidated; halts, volume pace, issuer news and earnings were not checked.' + failed;
  }
  function renderRow(host, row, now) {
    host.replaceChildren();
    const expired = now > instant(observation.expires_at);
    const section = node('section', { class: 'ss-research-observation', 'data-research-observation': row.ticker, 'data-observation-state': expired ? 'expired' : observation.status });
    section.append(node('h5', {}, (expired ? 'Expired dated' : 'Dated') + ' IEX observation · ' + atCT(observation.generated_at)));
    const list = node('dl', { class: 'sc-facts' });
    const fact = (key, label, value) => { const item = node('div'); item.append(node('dt', {}, label), node('dd', { 'data-observation-value': key }, value)); list.append(item); };
    const quote = row.quote, trade = row.trade;
    if (['recent', 'stale'].includes(quote.status)) {
      fact('bid-ask', 'Bid × size / ask × size', money(quote.bid) + ' × ' + quote.bid_size + ' / ' + money(quote.ask) + ' × ' + quote.ask_size + (quote.status === 'stale' ? ' (stale)' : ''));
      fact('spread', 'Spread', money(quote.spread_usd) + ' (' + quote.spread_pct.toFixed(2) + '%)');
      fact('quote-time', 'Quote time', atCT(quote.timestamp) + ' · ' + ageWords(quote.timestamp, now));
    } else fact('bid-ask', 'Bid / ask', quote.status === 'unavailable' ? 'unavailable — ' + (SOURCE_WORDS[observation.source.error_kind] || 'the source failed') : quote.status === 'invalid' ? 'invalid provider quote (not shown)' : 'missing from the provider snapshot');
    if (['recent', 'stale'].includes(trade.status)) fact('trade', 'Last trade', money(trade.price) + ' at ' + atCT(trade.timestamp) + (trade.status === 'stale' ? ' (stale)' : '') + ' · a print, not a current quote');
    else fact('trade', 'Last trade', trade.status === 'unavailable' ? 'unavailable' : trade.status === 'invalid' ? 'invalid provider print (not shown)' : 'missing from the provider snapshot');
    fact('ask-state', 'Ask at collection against the published levels', STATE_WORDS[row.price_checks.ask]);
    fact('trade-state', 'Last trade at collection against the published levels', STATE_WORDS[row.price_checks.trade]);
    fact('levels', 'Published levels', 'trigger ' + money(row.levels.trigger) + ' · limit ' + money(row.levels.limit) + ' · stop ' + money(row.levels.stop));
    section.append(list);
    paragraph(section, 'Not checked here:', 'trading halts, delayed volume pace, issuer news and earnings. The archived known-event registry had ' + (row.event.blocked ? 'a match' : 'no match') + ' for ' + row.ticker + ', which is not news clearance.');
    paragraph(section, 'Research context only.', 'Recent/stale labels and level positions describe collection time. A dated single-venue snapshot of a hypothetical research row: not a ready signal, not a quantity, not an order and not an entry permission. Check current prices, spread and trading status at your broker.');
    host.append(section);
  }
  function paint() {
    const now = clock();
    if (summaryHost && summaryHost.isConnected) { summaryHost.textContent = summaryWords(now); summaryHost.setAttribute('data-research-observations-state', state); }
    hosts.forEach((host, ticker) => {
      if (!host.isConnected) return;
      host.setAttribute('data-research-observations-state', state);
      const row = state === 'loaded' && observation ? observation.rows.find(r => r.ticker === ticker) : null;
      if (row) { renderRow(host, row, now); return; }
      host.replaceChildren();
      const note = state === 'loading' ? 'Checking for a dated observation…' : state === 'unavailable' ? 'No dated observation for this row: ' + issue
        : state === 'loaded' && observation && observation.reason ? 'No dated observation applies to this row: ' + REASON_WORDS[observation.reason] + '. Zero provider requests were made.'
        : state === 'loaded' ? 'No dated observation was recorded for this row.' : 'No dated observation has loaded for this row.';
      paragraph(host, null, note, { 'data-research-observation-note': ticker });
    });
  }
  // Rendered sections belong to the cohort they describe: when that cohort or
  // its publication goes, the words go with it rather than outliving them.
  function clearRendered() {
    hosts.forEach(host => { if (host.isConnected) host.replaceChildren(); });
    if (summaryHost && summaryHost.isConnected) { summaryHost.textContent = ''; summaryHost.removeAttribute('data-research-observations-state'); }
  }
  // The research panel calls this after it has rendered its rows: the cohort it
  // shows is the one an observation must be bound to, and the hosts are where
  // each row's observation belongs. The same cohort re-attached renders from
  // the kept result without another request.
  function attach(input) {
    const next = input && object(input) && input.receipt && input.bundle && HEX.test(input.receiptSha || '') ? input : null;
    if (!next) clearRendered();
    hosts = new Map(next && next.hosts instanceof Map ? next.hosts : []);
    summaryHost = next ? next.summary || null : null;
    const nextIdentity = next ? [next.receiptSha, fingerprint().recordHash, fingerprint().canonicalHash].join('|') : '';
    if (!next || nextIdentity !== identity) {
      epoch++; if (controller) controller.abort(); controller = null; pending = null;
      if (!next) clearRendered();
      if (next && next.record !== record) { record = next.record; }
      cohort = next ? { receipt: next.receipt, receiptSha: next.receiptSha, bundle: next.bundle } : null;
      identity = nextIdentity; receipt = cohort ? cohort.receipt : null; observation = null; state = 'deferred'; issue = '';
      if (cohort && record && fingerprint().recordHash) load(); else paint();
      // The morning summary's offer counts these rows, so it is told.
      if (api.observations && typeof api.observations.repaint === 'function') api.observations.repaint();
    } else paint();
  }
  function update(data) {
    if (record !== data) {
      epoch++; if (controller) controller.abort(); controller = null; pending = null;
      clearRendered();
      record = data || null; identity = ''; cohort = null; receipt = null; observation = null; hosts = new Map(); summaryHost = null; state = 'deferred'; issue = '';
    }
    paint();
  }
  api.researchObservations = { attach, update, reload: () => { epoch++; if (controller) controller.abort(); controller = null; pending = null; observation = null; state = 'deferred'; return load(); },
    refresh: () => { epoch++; if (controller) controller.abort(); controller = null; pending = null; return load(true); },
    status: () => ({ state, issue, settled: state !== 'loading', rows: observation ? observation.rows.length : 0, status: observation ? observation.status : null, reason: observation ? observation.reason : null,
      // The rows a morning run would quote for the attached cohort: its
      // allocation fits when recorded (src/research_observations.research_rows),
      // unknown (null) until a comparison has loaded.
      fit: cohort ? (cohort.receipt.status === 'recorded' ? cohort.bundle.rows.filter(row => row.research && row.research.allocation_fit).length : 0) : null }) };
})(window);
