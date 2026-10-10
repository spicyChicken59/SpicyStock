/* A compact public reader, plus one content-addressed research sidecar.
   Transport identity never changes the canonical strategy or saved originals. */
(function (w) {
  'use strict';
  const api = w.SCStock = w.SCStock || {};
  const MAX_BYTES = 32 * 1024 * 1024, TIMEOUT_MS = 15000, HEX = /^[a-f0-9]{64}$/;
  const object = value => !!value && typeof value === 'object' && !Array.isArray(value);
  const date = value => typeof value === 'string' && /^\d{4}-\d\d-\d\d$/.test(value) && Number.isFinite(Date.parse(value));
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const require = (test, reason) => { if (!test) throw Error(reason); };
  const metadata = value => Object.fromEntries(Object.entries(value).filter(([key]) => !['symbols', 'signals'].includes(key)));
  const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  let current = null, projection = null, epoch = 0, controller = null, pending = null, state = 'complete', reason = '', onChange = null;
  let cached = null;
  function parse(raw, sourceUrl) {
    require(typeof raw === 'string' && new TextEncoder().encode(raw).byteLength <= MAX_BYTES, 'The published reader exceeds its size limit.');
    const value = JSON.parse(raw);
    if (value && value.schema_version === 2) return { data: value, projection: null };
    require(object(value) && value.schema_version === 1 && value.projection_version === 1 && object(value.data) && value.data.schema_version === 2 && value.data.run, 'Unsupported reader projection.');
    const canonical = value.canonical, sidecar = value.retained_observations, observations = value.data.observations;
    require(object(canonical) && HEX.test(canonical.sha256) && Number.isSafeInteger(canonical.bytes) && canonical.bytes > 0 && canonical.bytes <= MAX_BYTES, 'Canonical publication identity is invalid.');
    require(object(sidecar) && HEX.test(sidecar.sha256) && Number.isSafeInteger(sidecar.bytes) && sidecar.bytes > 0 && sidecar.bytes <= MAX_BYTES && sidecar.path === 'reader-observations/' + sidecar.sha256 + '.json', 'Research sidecar identity is invalid.');
    require(object(observations) && object(observations.symbols) && !Object.keys(observations.symbols).length && (!('signals' in observations) || object(observations.signals) && !Object.keys(observations.signals).length), 'Projected observations must be deferred.');
    const base = new URL(sourceUrl || 'reader.json', w.location.href), url = new URL(sidecar.path, base);
    require(['http:', 'https:'].includes(base.protocol) && base.origin === w.location.origin && !base.username && !base.password && url.origin === base.origin && !url.search && !url.hash, 'Research must use the same public origin.');
    return { data: value.data, projection: Object.freeze({ version: 1, canonicalSha: canonical.sha256, canonicalBytes: canonical.bytes,
      sidecar: Object.freeze({ sha256: sidecar.sha256, bytes: sidecar.bytes, path: sidecar.path, url: url.href }),
      metadata: JSON.stringify(metadata(observations)), hasSignals: 'signals' in observations }) };
  }
  function attach(data, descriptor) {
    epoch++;
    if (controller) controller.abort();
    current = data; projection = descriptor || null; controller = null; pending = null;
    state = projection ? 'deferred' : 'complete'; reason = '';
  }
  const status = () => ({ projected: !!projection, state, reason, canonicalSha: projection && projection.canonicalSha, sidecarSha: projection && projection.sidecar.sha256 });
  function changed() { if (onChange) onChange({ data: current, ...status() }); }
  async function refuse(response, reason) {
    if (response.body && !response.body.locked && typeof response.body.cancel === 'function')
      await response.body.cancel().catch(() => {});
    throw Error(reason);
  }
  // Preserve the response bytes through digest verification. Decoding first
  // can strip a UTF-8 BOM and turn a different file into the expected string.
  async function read(response, expected = null) {
    if (!response.ok || response.redirected) return refuse(response, 'The public JSON file could not be read.');
    const contentLength = Number(response.headers.get('content-length'));
    if (Number.isFinite(contentLength) && contentLength > MAX_BYTES) return refuse(response, 'Public JSON exceeds its size limit.');
    if (!response.body || !response.body.getReader) return refuse(response, 'Bounded public JSON reading is unavailable.');
    // Count a clone before native consumption. Directly draining the network
    // response can emit Chromium ERR_ABORTED after a complete successful read.
    // The original tee queue is bounded by this counter; retain no extra chunks.
    const reader = response.clone().body.getReader();
    let length = 0;
    try {
      while (true) {
        const next = await reader.read(); if (next.done) break;
        length += next.value.byteLength;
        if (length > MAX_BYTES || expected !== null && length > expected) throw Error('Public JSON exceeds its byte limit.');
      }
      require(expected === null || length === expected, 'Research length differs from its publication.');
      // Native buffering starts only after actual EOF and the byte checks.
      const bytes = new Uint8Array(await response.arrayBuffer());
      require(bytes.byteLength === length, 'Public JSON length changed during reading.');
      return bytes;
    } catch (error) {
      // A tee cancellation waits for both branches: start both before awaiting.
      await Promise.allSettled([reader.cancel(), response.body.cancel()]);
      throw error;
    } finally { reader.releaseLock(); }
  }
  // JSON does not permit a leading BOM. Preserve it so JSON.parse rejects it,
  // and refuse malformed UTF-8 instead of silently replacing source bytes.
  const decode = bytes => new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
  function validate(value, descriptor) {
    require(object(value) && object(value.symbols) && equal(metadata(value), JSON.parse(descriptor.metadata)) && ('signals' in value) === descriptor.hasSignals && (!descriptor.hasSignals || object(value.signals)), 'Research metadata differs from its publication.');
    const bar = row => object(row) && date(row.date) && finite(row.c) && row.c > 0 && ['o', 'h', 'l', 'v'].every(key => row[key] === undefined || row[key] === null || finite(row[key]) && row[key] >= 0);
    Object.entries(value.symbols).forEach(([ticker, row]) => {
      require(/^[A-Z0-9][A-Z0-9.-]{0,15}$/.test(ticker) && bar(row) && (row.history === undefined || Array.isArray(row.history) && row.history.length <= (Number.isInteger(value.history_max) ? value.history_max : 20) && row.history.every(bar)), 'Research contains an invalid observation bar.');
    });
    Object.entries(value.signals || {}).forEach(([id, signal]) => {
      require(object(signal) && /^[A-Z0-9][A-Z0-9.-]{0,15}$/.test(signal.ticker) && date(signal.session) && ['burst', 'anticipation'].includes(signal.kind) && typeof signal.rules_version === 'string' && id === [signal.kind, signal.ticker, signal.session, signal.rules_version].join(':'), 'Research contains an invalid signal identity.');
    });
    return value;
  }
  async function ensure() {
    if (!projection || state === 'complete') return true;
    if (pending) return pending;
    const token = epoch, target = current, descriptor = projection;
    state = 'loading'; reason = ''; changed();
    pending = Promise.resolve().then(async () => {
      if (token !== epoch || target !== current) return false;
      const active = new AbortController(); controller = active;
      const timer = w.setTimeout(() => active.abort(), TIMEOUT_MS);
      try {
        let value;
        if (cached && cached.sha === descriptor.sidecar.sha256) {
          require(cached.bytes === descriptor.sidecar.bytes, 'Research length differs from its publication.');
          value = validate(cached.value, descriptor);
        }
        else {
          require(w.crypto && w.crypto.subtle && w.TextEncoder, 'Research digest verification is unavailable in this browser.');
          const response = await w.fetch(descriptor.sidecar.url, { cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer', mode: 'same-origin', redirect: 'error', signal: active.signal });
          const bytes = await read(response, descriptor.sidecar.bytes);
          const digest = await w.crypto.subtle.digest('SHA-256', bytes);
          require(Array.from(new Uint8Array(digest), n => n.toString(16).padStart(2, '0')).join('') === descriptor.sidecar.sha256, 'Research digest differs from its publication.');
          value = validate(JSON.parse(decode(bytes)), descriptor);
        }
        if (token !== epoch || target !== current) return false;
        cached = { sha: descriptor.sidecar.sha256, bytes: descriptor.sidecar.bytes, value };
        current.observations = value; state = 'complete'; reason = ''; changed();
        return true;
      } catch (error) {
        if (token !== epoch || target !== current) return false;
        state = 'unavailable'; reason = error && error.message || 'Public research coverage is unavailable.'; changed();
        return false;
      } finally { w.clearTimeout(timer); if (token === epoch) { pending = null; controller = null; } }
    });
    return pending;
  }
  api.reader = { parse, read, decode, attach, ensure, status, mergeAllowed: () => !projection || state === 'complete', onChange: fn => { onChange = fn; }, MAX_BYTES };
})(window);
