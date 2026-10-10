/* Optional, bounded SEC source inspection. Public files only; this reader never
   changes a published plan, an event exclusion, a cash preview or an order. */
(function (w) {
  'use strict';
  const api = w.SCStock = w.SCStock || {}, d = w.document;
  const RECEIPT_BYTES = 64 * 1024, BUNDLE_BYTES = 2 * 1024 * 1024, TIMEOUT_MS = 15000;
  const HEX = /^[a-f0-9]{64}$/, TICKER = /^[A-Z0-9][A-Z0-9.-]{0,31}$/, ACCESSION = /^\d{10}-\d{2}-\d{6}$/;
  const POLICY = { version: 1, max_issuers: 8, lookback_days: 365, max_reports: 3, max_exhibits_per_report: 2,
    max_history_files: 1, max_metadata_rows: 2000, max_listed_filings: 12, max_excerpt_bytes: 16384,
    receipt_ttl_seconds: 86400, max_future_skew_seconds: 5, max_requests: 96, max_response_bytes: 2097152,
    max_download_bytes: 33554432, max_collection_seconds: 240, min_request_interval_seconds: 1 };
  const ERRORS = ['rate_limit', 'http_error', 'timeout', 'network_error', 'redirect_refused', 'size_limit', 'request_budget', 'time_budget', 'invalid_response', 'identity_unverified', 'metadata_invalid', 'document_invalid', 'history_incomplete'];
  const object = x => !!x && typeof x === 'object' && !Array.isArray(x);
  const require = (ok, why) => { if (!ok) throw Error(why); };
  const canonical = x => Array.isArray(x) ? x.map(canonical) : object(x) ? Object.fromEntries(Object.keys(x).sort().map(k => [k, canonical(x[k])])) : x;
  const equal = (a, b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
  const keys = (x, names) => object(x) && equal(Object.keys(x).sort(), names.split(' ').sort());
  const text = (x, max = 4096) => typeof x === 'string' && x.length <= max;
  const integer = (x, max = Number.MAX_SAFE_INTEGER) => Number.isSafeInteger(x) && x >= 0 && x <= max;
  const day = x => typeof x === 'string' && /^\d{4}-\d\d-\d\d$/.test(x) && Number.isFinite(Date.parse(x)) && new Date(x).toISOString().slice(0, 10) === x;
  const instant = x => {
    const match = typeof x === 'string' && /^(\d{4}-\d\d-\d\d)T(\d\d):(\d\d):(\d\d)(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)$/.exec(x);
    return match && day(match[1]) && Number(match[2]) < 24 && Number(match[3]) < 60 && Number(match[4]) < 60 ? Date.parse(x) : NaN;
  };
  const clock = () => api.now ? new Date(api.now).getTime() : Date.now();
  const stamp = x => Number.isFinite(instant(x)) ? new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(x)) + ' CT' : 'Unavailable';
  const fingerprint = () => api.observations.facts();
  const id = c => c.kind + ':' + c.ticker;
  let mounted = null, record = null, identity = '', choices = [], receipt = null, bundle = null;
  let state = 'deferred', issue = '', epoch = 0, controller = null, pending = null;

  function node(tag, attrs, value) {
    const el = d.createElement(tag);
    Object.entries(attrs || {}).forEach(([key, val]) => el.setAttribute(key, val));
    if (value !== undefined) el.textContent = value;
    return el;
  }
  function safeUrl(value, secOnly = true) {
    try {
      const url = new URL(value);
      return text(value, 2048) && url.protocol === 'https:' && !url.username && !url.password && !url.port && !url.search && !url.hash &&
        (!secOnly || ['www.sec.gov', 'data.sec.gov'].includes(url.hostname)) ? url : null;
    } catch (_) { return null; }
  }
  function link(label, url, secOnly = true) {
    return safeUrl(url, secOnly) ? node('a', { href: url, target: '_blank', rel: 'noopener noreferrer', referrerpolicy: 'no-referrer' }, label) : node('span', {}, label + ' (link unavailable)');
  }
  function paragraph(host, label, value) {
    const p = node('p', { class: 'sc-hint' }); p.append(node('strong', {}, label + ' '), d.createTextNode(value)); host.append(p);
  }
  function relevant(data) {
    const rows = (data.bursts || []).map(row => ['burst', row]).concat(((data.watchlist || {}).top || []).map(row => ['anticipation', row]));
    const admitted = [], excluded = [];
    rows.forEach(([kind, row]) => {
      const plan = row.plan || {}, evidence = row.evidence || {}, event = plan.event_risk || {};
      const admission = event.blocked === true ? 'known_event_excluded' : (evidence.gate || {}).ticket === true ? 'admitted' : null;
      if (!admission) return;
      const item = { ticker: row.ticker, kind, evidence_id: evidence.id, plan_sha256: (plan.evidence_ref || {}).plan_sha256,
        admission, anchors: event.matches || [] };
      (admission === 'admitted' ? admitted : excluded).push(item);
    });
    return admitted.concat(excluded);
  }
  function binding(value) {
    const hashes = fingerprint(), run = record.run || {};
    require(keys(value, 'data_sha256 context_sha256 run_id rules_version measured_session applicable_session published_at reader_projection_version reader_sha256') &&
      HEX.test(value.data_sha256) && HEX.test(value.reader_sha256) && value.reader_projection_version === 1 &&
      hashes.canonicalHash && value.data_sha256 === hashes.canonicalHash && (!hashes.projected || value.reader_sha256 === hashes.recordHash) &&
      value.context_sha256 === (run.evidence || {}).context_sha256 && value.rules_version === (record.app || {}).rules_version &&
      String(value.run_id) === String(run.run_id) && value.measured_session === run.session &&
      value.applicable_session === (run.timing || {}).applicable_session && value.published_at === run.published_at,
    'This issuer evidence belongs to another publication.');
  }
  function validateReceipt(value) {
    require(keys(value, 'schema_version status dry_run collection_run_id collection_started_at generated_at expires_at publication previous_receipt_sha256 policy selection bundle coverage') &&
      value.schema_version === 1 && value.dry_run === false && ['collected', 'partial', 'unavailable', 'no_candidates', 'inapplicable'].includes(value.status) &&
      text(value.collection_run_id, 256) && value.collection_run_id.length > 0 && (value.previous_receipt_sha256 === null || HEX.test(value.previous_receipt_sha256)), 'Issuer receipt is invalid or a rehearsal.');
    binding(value.publication);
    const start = instant(value.collection_started_at), end = instant(value.generated_at), expiry = instant(value.expires_at);
    require([start, end, expiry].every(Number.isFinite) && start <= end && end - start <= 240000 && end <= clock() + 5000 && expiry - end === 86400000, 'Issuer receipt timestamps are invalid.');
    const ref = value.bundle, selection = value.selection;
    require(keys(ref, 'sha256 bytes path') && HEX.test(ref.sha256) && integer(ref.bytes, BUNDLE_BYTES) && ref.bytes > 0 && ref.path === 'issuer-evidence/' + ref.sha256 + '.json', 'Issuer bundle reference is invalid.');
    require(keys(selection, 'candidate_count issuer_count selected_issuer_count omitted_issuer_count selected_tickers') &&
      integer(selection.candidate_count, 128) && integer(selection.issuer_count, 128) && integer(selection.selected_issuer_count, 8) &&
      integer(selection.omitted_issuer_count, 128) && selection.selected_issuer_count + selection.omitted_issuer_count === selection.issuer_count &&
      Array.isArray(selection.selected_tickers) && selection.selected_tickers.length === selection.selected_issuer_count &&
      selection.selected_tickers.every(t => TICKER.test(t)) && new Set(selection.selected_tickers).size === selection.selected_tickers.length,
    'Issuer selection is invalid.');
    require(keys(value.coverage, 'issuer_news earnings') && keys(value.coverage.issuer_news, 'status reason') && value.coverage.issuer_news.status === 'not_cleared' && text(value.coverage.issuer_news.reason) &&
      keys(value.coverage.earnings, 'status reason') && value.coverage.earnings.status === 'not_checked' && text(value.coverage.earnings.reason) && equal(value.policy, POLICY), 'Issuer coverage claims or collection policy are invalid.');
    return value;
  }
  function source(value, end, asOf) {
    require(keys(value, 'url raw_sha256 bytes fetched_at checked_at cache_status') && safeUrl(value.url) && HEX.test(value.raw_sha256) && integer(value.bytes, BUNDLE_BYTES) && value.bytes > 0 &&
      ['network', 'verified_cache'].includes(value.cache_status) && Number.isFinite(instant(value.fetched_at)) && instant(value.fetched_at) === instant(value.checked_at) && instant(value.checked_at) <= end + 5000,
    'Issuer source metadata is invalid.');
    if (value.cache_status === 'verified_cache') {
      const ttl = value.url === 'https://www.sec.gov/files/company_tickers_exchange.json' ? 7 * 86400000 : value.url.startsWith('https://www.sec.gov/Archives/edgar/data/') ? 86400000 : 0;
      require(ttl > 0 && asOf - instant(value.fetched_at) <= ttl, 'Issuer cached source exceeds its retrieval age limit.');
    }
  }
  function filing(row, end) {
    require(keys(row, 'accession form filing_date report_date accepted_at primary_document items') && ACCESSION.test(row.accession) && text(row.form, 40) && day(row.filing_date) &&
      (row.report_date === null || day(row.report_date)) && Number.isFinite(instant(row.accepted_at)) && instant(row.accepted_at) <= end + 5000 &&
      text(row.primary_document, 256) && /^[A-Za-z0-9_.-]+$/.test(row.primary_document) && !row.primary_document.includes('..') && text(row.items, 1024), 'Filing metadata is invalid.');
  }
  async function sha(raw) {
    require(w.crypto && w.crypto.subtle && w.TextEncoder, 'Exact source verification is unavailable in this browser.');
    const hash = await w.crypto.subtle.digest('SHA-256', typeof raw === 'string' ? new TextEncoder().encode(raw) : raw);
    return Array.from(new Uint8Array(hash), n => n.toString(16).padStart(2, '0')).join('');
  }
  async function validateBundle(value, r) {
    require(keys(value, 'schema_version publication collection_started_at generated_at as_of window_start candidates issuers stats') && value.schema_version === 1 &&
      equal(value.publication, r.publication) && value.collection_started_at === r.collection_started_at && value.generated_at === r.generated_at && value.as_of === r.collection_started_at && day(value.window_start), 'Issuer bundle metadata differs from its receipt.');
    const end = instant(value.generated_at), asOf = instant(value.as_of), selected = r.selection.selected_tickers;
    require(value.window_start === new Date(instant(value.as_of) - 365 * 86400000).toISOString().slice(0, 10), 'Issuer index window is invalid.');
    require(Array.isArray(value.candidates) && value.candidates.length === choices.length && value.candidates.length === r.selection.candidate_count && choices.length <= 128, 'Issuer candidate coverage differs from this publication.');
    value.candidates.forEach((c, i) => {
      require(keys(c, 'ticker kind evidence_id plan_sha256 admission selected anchors') && typeof c.selected === 'boolean' && c.selected === selected.includes(c.ticker) &&
        equal(Object.fromEntries(Object.entries(c).filter(([key]) => key !== 'selected')), choices[i]), 'Issuer candidate or archived anchor differs from this publication.');
    });
    const tickers = [...new Set(choices.map(c => c.ticker))];
    require(r.selection.issuer_count === tickers.length && equal(selected, r.status === 'inapplicable' ? [] : tickers.slice(0, 8)), 'Issuer fetch selection differs from this publication.');
    require(Array.isArray(value.issuers) && value.issuers.length === selected.length && equal(value.issuers.map(x => x.ticker), selected), 'Issuer membership differs from its receipt.');
    for (const row of value.issuers) {
      require(keys(row, 'ticker status reason identity index documents errors') && ['collected', 'partial', 'unavailable', 'identity_unverified'].includes(row.status) && (row.reason === null || text(row.reason)), 'Issuer status is invalid.');
      const ident = row.identity, index = row.index;
      require(keys(ident, 'status cik name mapping_source submissions_source') && ['verified', 'unverified'].includes(ident.status), 'Issuer identity is invalid.');
      for (const item of [ident.mapping_source, ident.submissions_source]) if (item !== null) source(item, end, asOf);
      require(ident.status === 'verified' ? integer(ident.cik, 9999999999) && ident.cik > 0 && text(ident.name, 512) && ident.name.length > 0 && ident.mapping_source && ident.submissions_source :
        (ident.cik === null || integer(ident.cik, 9999999999)) && (ident.name === null || text(ident.name, 512)), 'Issuer identity could not be verified.');
      if (ident.status === 'verified') require(ident.mapping_source.url === 'https://www.sec.gov/files/company_tickers_exchange.json' && ident.submissions_source.url === 'https://data.sec.gov/submissions/CIK' + String(ident.cik).padStart(10, '0') + '.json', 'SEC submissions CIK or mapping source differs from the issuer.');
      require(keys(index, 'window_start window_end coverage_status reason range_start range_end metadata_count eligible_current_report_count not_selected_count history_files_advertised history_files_fetched history_sources selected_accessions listed_filings exhibit_links_observed exhibit_links_not_fetched') &&
        index.window_start === value.window_start && index.window_end === new Date(asOf).toISOString().slice(0, 10) && ['observed_window', 'partial', 'unknown'].includes(index.coverage_status) &&
        (index.reason === null || text(index.reason)) && [index.range_start, index.range_end].every(x => x === null || day(x)) &&
        (index.range_start === null) === (index.range_end === null) && (index.range_start === null || index.range_start <= index.range_end) &&
        ['metadata_count', 'eligible_current_report_count', 'not_selected_count', 'history_files_advertised', 'history_files_fetched', 'exhibit_links_observed', 'exhibit_links_not_fetched'].every(key => integer(index[key], 4000)) &&
        index.exhibit_links_not_fetched <= index.exhibit_links_observed &&
        index.history_files_fetched <= 1 && index.history_files_fetched <= index.history_files_advertised &&
        Array.isArray(index.selected_accessions) && index.selected_accessions.length <= 3 && index.selected_accessions.every(x => ACCESSION.test(x)) && new Set(index.selected_accessions).size === index.selected_accessions.length &&
        index.eligible_current_report_count <= index.metadata_count && index.not_selected_count === index.eligible_current_report_count - index.selected_accessions.length &&
        Array.isArray(index.listed_filings) && index.listed_filings.length <= 12 && index.listed_filings.length <= index.metadata_count,
      'Issuer index coverage is invalid.');
      require(Array.isArray(index.history_sources) && index.history_sources.length === index.history_files_fetched, 'Historical index source count is invalid.');
      for (const item of index.history_sources) {
        source(item, end, asOf);
        require(ident.status === 'verified' && new RegExp('^https://data\\.sec\\.gov/submissions/CIK' + String(ident.cik).padStart(10, '0') + '-submissions-[0-9]{3}\\.json$').test(item.url), 'Historical index CIK differs from the issuer.');
      }
      index.listed_filings.forEach(item => {
        filing(item, asOf);
        require(['8-K', '8-K/A', '6-K', '6-K/A'].includes(item.form) && item.filing_date >= index.window_start && item.filing_date <= index.window_end, 'Listed report falls outside this collection.');
      });
      const ordered = index.listed_filings.slice().sort((a, b) => a.accepted_at === b.accepted_at ? (a.accession < b.accession ? 1 : a.accession > b.accession ? -1 : 0) : a.accepted_at < b.accepted_at ? 1 : -1);
      require(equal(ordered, index.listed_filings) && index.listed_filings.length <= index.eligible_current_report_count && equal(index.selected_accessions, ordered.slice(0, 3).map(x => x.accession)), 'Latest report selection differs from the listed metadata.');
      require(new Set(index.listed_filings.map(x => x.accession)).size === index.listed_filings.length && Array.isArray(row.documents) && row.documents.length <= 9 && (ident.status === 'verified' || row.documents.length === 0), 'Issuer documents lack verified identity.');
      const urls = new Set();
      for (const doc of row.documents) {
        require(keys(doc, 'accession form role source filing_date report_date accepted_at release_date excerpt') && index.selected_accessions.includes(doc.accession) &&
          ['8-K', '8-K/A', '6-K', '6-K/A'].includes(doc.form) && ['primary', 'exhibit'].includes(doc.role) && day(doc.filing_date) && (doc.report_date === null || day(doc.report_date)) &&
          Number.isFinite(instant(doc.accepted_at)) && instant(doc.accepted_at) <= asOf + 5000 && doc.release_date === null, 'Issuer document metadata is invalid.');
        source(doc.source, end, asOf);
        const url = safeUrl(doc.source.url), prefix = '/Archives/edgar/data/' + ident.cik + '/' + doc.accession.replaceAll('-', '') + '/';
        require(url.hostname === 'www.sec.gov' && url.pathname.startsWith(prefix) && /^[A-Za-z0-9_.-]+\.(?:htm|html)$/i.test(url.pathname.slice(prefix.length)) && !url.pathname.slice(prefix.length).includes('..') && !urls.has(url.href), 'Document path differs from its issuer and accession.');
        urls.add(url.href);
        const listed = index.listed_filings.find(x => x.accession === doc.accession);
        require(listed && ['form', 'filing_date', 'report_date', 'accepted_at'].every(key => listed[key] === doc[key]) && (doc.role !== 'primary' || url.pathname === prefix + listed.primary_document), 'Document differs from its index metadata.');
        const excerpt = doc.excerpt;
        require(keys(excerpt, 'text normalization start characters normalized_characters truncated sha256') && text(excerpt.text, 16384) && new TextEncoder().encode(excerpt.text).byteLength <= 16384 &&
          excerpt.normalization === 'html_text_v1' && excerpt.start === 0 && excerpt.characters === Array.from(excerpt.text).length && integer(excerpt.normalized_characters, BUNDLE_BYTES) && excerpt.normalized_characters >= excerpt.characters &&
          excerpt.truncated === (excerpt.normalized_characters > excerpt.characters) && HEX.test(excerpt.sha256) && await sha(excerpt.text) === excerpt.sha256, 'Issuer excerpt is invalid.');
      }
      for (const accession of index.selected_accessions) {
        require(row.documents.filter(x => x.accession === accession && x.role === 'primary').length <= 1 && row.documents.filter(x => x.accession === accession && x.role === 'exhibit').length <= 2, 'Issuer document count exceeds the collection boundary.');
        require(!row.documents.some(x => x.accession === accession && x.role === 'exhibit') || row.documents.some(x => x.accession === accession && x.role === 'primary'), 'Issuer exhibit lacks its primary document.');
      }
      require(index.exhibit_links_observed - index.exhibit_links_not_fetched === row.documents.filter(x => x.role === 'exhibit').length, 'Issuer exhibit remainder differs from retrieved content.');
      require(Array.isArray(row.errors) && row.errors.length <= 96 && row.errors.every(x => keys(x, 'code source_url') && ERRORS.includes(x.code) && (x.source_url === null || safeUrl(x.source_url))), 'Issuer error metadata is invalid.');
    }
    require(keys(value.stats, 'request_count downloaded_bytes capture_bytes budget_stop') && integer(value.stats.request_count, 96) && integer(value.stats.downloaded_bytes, 34 * 1024 * 1024) &&
      integer(value.stats.capture_bytes, 32 * 1024 * 1024) && (value.stats.budget_stop === null || ERRORS.includes(value.stats.budget_stop)) &&
      (value.stats.downloaded_bytes <= 32 * 1024 * 1024 || value.stats.budget_stop === 'size_limit'), 'Issuer collection bounds are invalid.');
    require(!['no_candidates', 'inapplicable'].includes(r.status) || !value.issuers.length && value.stats.request_count === 0 && value.stats.downloaded_bytes === 0 && value.stats.capture_bytes === 0, 'Issuer no-fetch receipt contradicts collection.');
    require(r.status !== 'no_candidates' || !choices.length, 'Issuer no-candidate status contradicts this publication.');
    return value;
  }
  async function read(response, max, expected) {
    require(response.ok && !response.redirected, 'Published issuer evidence is unavailable.');
    const length = Number(response.headers.get('content-length'));
    require(!Number.isFinite(length) || length <= max, 'Published issuer evidence exceeds its size limit.');
    require(response.body && response.body.getReader, 'Bounded source reading is unavailable in this browser.');
    const reader = response.body.getReader(), decoder = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true });
    const chunks = [];
    let size = 0, raw = '';
    try {
      while (true) {
        const next = await reader.read(); if (next.done) break;
        size += next.value.byteLength;
        if (size > max || expected !== undefined && size > expected) { await reader.cancel(); throw Error('Published issuer evidence exceeds its declared size.'); }
        chunks.push(next.value);
        raw += decoder.decode(next.value, { stream: true });
      }
      require(expected === undefined || size === expected, 'Issuer evidence length differs from its receipt.');
      const bytes = new Uint8Array(size);
      let offset = 0; for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
      return { raw: raw + decoder.decode(), bytes };
    } finally { reader.releaseLock(); }
  }
  async function load() {
    if (pending) return pending;
    if (!fingerprint().recordHash) { issue = 'Waiting for exact publication verification.'; paint(); return false; }
    const token = epoch, target = record;
    state = 'loading'; issue = ''; paint();
    pending = Promise.resolve().then(async () => {
      const active = new AbortController(); controller = active;
      const timer = w.setTimeout(() => active.abort(), TIMEOUT_MS);
      try {
        require(w.crypto && w.crypto.subtle && w.TextEncoder, 'Exact source verification is unavailable in this browser.');
        const base = new URL('issuer-evidence.json', w.location.href);
        require(['http:', 'https:'].includes(base.protocol) && base.origin === w.location.origin && !base.search && !base.hash, 'Issuer evidence must use this public origin.');
        const options = { cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer', mode: 'same-origin', redirect: 'error', signal: active.signal };
        const nextReceipt = validateReceipt(JSON.parse((await read(await w.fetch(base.href, options), RECEIPT_BYTES)).raw));
        if (token !== epoch || target !== record) return false;
        const nextRaw = await read(await w.fetch(new URL(nextReceipt.bundle.path, base).href, options), BUNDLE_BYTES, nextReceipt.bundle.bytes);
        require(await sha(nextRaw.bytes) === nextReceipt.bundle.sha256, 'Issuer evidence digest differs from its receipt.');
        const nextBundle = await validateBundle(JSON.parse(nextRaw.raw), nextReceipt);
        if (token !== epoch || target !== record) return false;
        binding(nextReceipt.publication);
        receipt = nextReceipt; bundle = nextBundle; state = 'loaded'; issue = ''; paint(); return true;
      } catch (error) {
        if (token !== epoch || target !== record) return false;
        receipt = null; bundle = null; state = 'unavailable'; issue = error && error.name === 'AbortError' ? 'Published issuer evidence timed out.' : error && error.message || 'Published issuer evidence is unavailable.'; paint(); return false;
      } finally { w.clearTimeout(timer); if (token === epoch) { controller = null; pending = null; } }
    });
    return pending;
  }
  function anchors(host, candidate) {
    const section = node('section', { 'data-issuer-anchors': '' }); section.append(node('h4', {}, 'Known event evidence from this publication'));
    if (!candidate || !candidate.anchors.length) paragraph(section, 'No archived match.', 'This is not event clearance. Check current issuer news and earnings independently.');
    else for (const event of candidate.anchors) {
      paragraph(section, event.issuer || candidate.ticker, event.reason || 'A reviewed event excludes this candidate.');
      paragraph(section, 'Reviewed', (event.reviewed_on || 'unavailable') + ' · evidence as of ' + (event.evidence_as_of || 'unavailable') + ' · review due ' + (event.review_due || 'unavailable') + '. An overdue review does not end this exclusion.');
      for (const item of event.sources || []) {
        const p = node('p', { class: 'sc-hint' }); p.append(link(item.title || 'Reviewed event source', item.url, false), d.createTextNode(' · source date ' + (item.published_on || 'unavailable'))); section.append(p);
        if (item.quote) section.append(node('blockquote', {}, item.quote));
      }
    }
    host.append(section);
  }
  function ageLabel() {
    const now = clock(), generated = instant(receipt.generated_at);
    return 'Collected ' + stamp(receipt.generated_at) + (!Number.isFinite(now) || generated > now + 5000 ? ' · browser clock cannot verify this receipt’s age' : now > instant(receipt.expires_at) ? ' · aged receipt (over 24 hours)' : ' · receipt within 24 hours') + '. This is source inspection, not news clearance.';
  }
  function paintAge() {
    if (mounted && receipt && state === 'loaded') mounted.querySelector('[data-issuer-status]').textContent = ageLabel();
  }
  function paint() {
    if (!mounted) return;
    mounted.setAttribute('data-issuer-state', state);
    const status = mounted.querySelector('[data-issuer-status]'), body = mounted.querySelector('[data-issuer-body]'), button = mounted.querySelector('[data-issuer-reload]');
    button.disabled = state === 'loading' || !fingerprint().recordHash;
    status.textContent = state === 'deferred' ? 'Source files load only when you open this section.' : state === 'loading' ? 'Reading the published source bundle…' : state === 'unavailable' ? issue :
      ageLabel();
    const selected = choices.find(c => id(c) === mounted.querySelector('[data-issuer-choice]').value);
    body.replaceChildren();
    if (!selected) { paragraph(body, 'No relevant candidates.', 'This publication has no admitted ticket or known-event-excluded candidate to inspect.'); return; }
    body.append(node('h3', {}, selected.ticker + ' · ' + (selected.admission === 'admitted' ? 'published conditional ticket' : 'excluded research — no entry ticket')));
    anchors(body, selected);
    if (!bundle) { paragraph(body, 'Recent SEC filings:', issue || 'Not loaded. Known event evidence above remains in force.'); return; }
    if (receipt.status === 'inapplicable') {
      paragraph(body, 'Collection skipped:', 'This publication’s scan session was not current at collection time. No SEC collection ran; issuer filings and news remain unreviewed.');
      return;
    }
    paragraph(body, 'Collection scope:', receipt.selection.selected_issuer_count + ' issuers selected; ' + receipt.selection.omitted_issuer_count + ' omitted by the collection cap. Trailing-year filing metadata is not a year of reviewed content.');
    const row = bundle.issuers.find(x => x.ticker === selected.ticker);
    if (!row) { paragraph(body, 'Not collected:', 'This issuer exceeded the fetch cap. Its filings and news remain unreviewed.'); return; }
    const ident = row.identity, index = row.index, primaries = row.documents.filter(x => x.role === 'primary').length;
    paragraph(body, 'Issuer identity:', ident.status === 'verified' ? ident.name + ' · CIK ' + String(ident.cik).padStart(10, '0') + ' · matched SEC mapping and submissions' : 'Unverified — no issuer content may be treated as matched.');
    paragraph(body, 'Index window:', index.window_start + '–' + index.window_end + ' · ' + index.coverage_status.replaceAll('_', ' ') + (index.reason ? ' · ' + index.reason : '') + '. Observed range: ' + (index.range_start || 'unknown') + '–' + (index.range_end || 'unknown') + '.');
    paragraph(body, 'Content boundary:', index.metadata_count + ' metadata rows observed; ' + index.eligible_current_report_count + ' current reports; ' + index.selected_accessions.length + ' selected; ' + primaries + ' primary documents retrieved. ' + index.not_selected_count + ' eligible reports not selected; ' + (index.selected_accessions.length - primaries) + ' selected primary documents missing. All remaining content is unreviewed.');
    paragraph(body, 'Historical index:', index.history_files_fetched + ' of ' + index.history_files_advertised + ' advertised history files fetched. ' + (index.metadata_count - index.listed_filings.length) + ' observed metadata rows not listed here.');
    paragraph(body, 'Exhibit boundary:', index.exhibit_links_observed + ' eligible exhibit links observed; ' + index.exhibit_links_not_fetched + ' not retrieved. Unfetched linked material remains unreviewed.');
    for (const [label, src] of [['SEC ticker mapping', ident.mapping_source], ['SEC submissions index', ident.submissions_source], ...index.history_sources.map(src => ['Older SEC submissions index', src])]) if (src) {
      const p = node('p', { class: 'sc-hint' }); p.append(link(label, src.url)); body.append(p);
      paragraph(body, 'Retrieved / checked:', stamp(src.fetched_at) + ' / ' + stamp(src.checked_at) + ' · ' + src.cache_status.replaceAll('_', ' '));
    }
    if (row.reason || row.errors.length) paragraph(body, 'Missing coverage:', [row.reason, ...row.errors.map(x => x.code.replaceAll('_', ' '))].filter(Boolean).join(' · '));
    const metadata = node('details', { class: 'sc-disclosure' }); metadata.append(node('summary', {}, 'Listed filing metadata (' + index.listed_filings.length + ')'));
    for (const item of index.listed_filings) paragraph(metadata, item.form + ' · ' + item.filing_date, 'SEC accepted ' + stamp(item.accepted_at) + ' · report date ' + (item.report_date || 'not supplied') + ' · accession ' + item.accession);
    body.append(metadata);
    if (!row.documents.length) paragraph(body, 'No document excerpts retrieved.', 'Missing filings or content do not establish that no event exists.');
    for (const doc of row.documents) {
      const article = node('details', { class: 'sc-disclosure', 'data-issuer-document': '' });
      article.append(node('summary', {}, doc.form + ' · filed ' + doc.filing_date + ' · ' + doc.role));
      const content = node('div', { class: 'sc-disclosure__body' });
      content.append(link('Read complete SEC document', doc.source.url));
      paragraph(content, 'SEC acceptance:', stamp(doc.accepted_at) + '. This is availability metadata, not the event date.');
      paragraph(content, 'Report date:', (doc.report_date || 'not supplied') + ' · issuer release date not extracted.');
      paragraph(content, 'Retrieved / checked:', stamp(doc.source.fetched_at) + ' / ' + stamp(doc.source.checked_at) + ' · ' + doc.source.cache_status.replaceAll('_', ' '));
      paragraph(content, 'Excerpt only:', doc.excerpt.characters + ' of ' + doc.excerpt.normalized_characters + ' normalized characters shown' + (doc.excerpt.truncated ? ' · truncated' : '') + '. Remaining filing content and linked material are unreviewed.');
      content.append(node('blockquote', { 'data-issuer-excerpt': '' }, doc.excerpt.text));
      article.append(content); body.append(article);
    }
  }
  function mount() {
    const host = node('details', { class: 'sc-disclosure ss-issuer', 'data-issuer-evidence': '' });
    host.append(node('summary', {}, 'Issuer evidence · SEC source reader'));
    const content = node('div', { class: 'sc-disclosure__body' });
    content.append(node('p', { class: 'sc-hint' }, 'Read dated sources before a decision. This bounded collection does not clear issuer news, check earnings or authorize an entry. Missing or newer filings never remove a known exclusion.'));
    content.append(node('label', { for: 'issuer-evidence-choice' }, 'Published candidate'), node('select', { id: 'issuer-evidence-choice', class: 'sc-select', 'data-issuer-choice': '' }),
      node('p', { class: 'sc-hint', role: 'status', 'data-issuer-status': '' }), node('div', { 'data-issuer-body': '' }));
    const button = node('button', { class: 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', 'data-issuer-reload': '' }, 'Reload published issuer evidence');
    button.addEventListener('click', load);
    content.append(button, node('p', { class: 'sc-hint' }, 'Reload reads public files only; it does not run a new SEC collection. Your cash inputs and saved symbols are never part of these requests.'));
    host.append(content); mounted = host;
    host.querySelector('[data-issuer-choice]').addEventListener('change', paint);
    host.addEventListener('toggle', () => { if (host.open && state === 'deferred') load(); else paintAge(); });
    return host;
  }
  function update(data) {
    const facts = fingerprint(), key = [facts.recordHash, facts.canonicalHash, facts.projected].join('|');
    if (record !== data || key !== identity) {
      epoch++; if (controller) controller.abort(); controller = null; pending = null;
      record = data; identity = key; choices = relevant(data); receipt = null; bundle = null; state = 'deferred'; issue = '';
      if (mounted) {
        const select = mounted.querySelector('[data-issuer-choice]'), previous = select.value;
        select.replaceChildren(...(choices.length ? choices.map(c => [id(c), c.ticker + ' · ' + c.kind + ' · ' + (c.admission === 'admitted' ? 'published ticket' : 'excluded research')]) : [['', 'No relevant candidates']]).map(([value, label]) => node('option', { value }, label)));
        if (choices.some(c => id(c) === previous)) select.value = previous;
      }
      paint(); if (mounted && mounted.open && facts.recordHash) load();
    } else if (receipt) {
      // Age changes only the dated source label; it cannot repaint private inputs.
      paintAge();
    }
  }
  w.setInterval(() => { if (mounted && mounted.open && !d.hidden) paintAge(); }, 60000);
  w.addEventListener('focus', paintAge);
  d.addEventListener('visibilitychange', paintAge);
  api.issuerEvidence = { mount, update, reload: load, status: () => ({ state, issue, publication: receipt && receipt.publication, candidates: choices.length }) };
})(window);
