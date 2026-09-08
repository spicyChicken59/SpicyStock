/* Same-origin broker client. No tokens, keys, or trading state are persisted here. */
(function (root) {
  'use strict';
  function createClient(options) {
    options = options || {};
    var fetcher = options.fetch || function (url, init) { return root.fetch(url, init); };
    var location = options.location || root.location;
    var timeout = options.timeout || 10000;
    var config = null, statusData = null, csrf = null, loading = null;
    function failure(code, message) { return { ok: false, error: { code: code, message: message } }; }
    function object(v) { return v !== null && typeof v === 'object' && !Array.isArray(v); }
    function endpoint(path) { return new URL(path, location.href).href; }
    async function request(path, method, body) {
      var controller = new AbortController(), timer = setTimeout(function () { controller.abort(); }, timeout);
      var submitting = path === '/api/orders';
      try {
        var headers = { Accept: 'application/json' };
        if (method === 'POST') {
          if (!csrf) return failure('SESSION_REQUIRED', 'Reconnect your account before continuing.');
          headers['Content-Type'] = 'application/json';
          headers['X-CSRF-Token'] = csrf;
        }
        var response = await fetcher(endpoint(path), {
          method: method || 'GET', credentials: 'same-origin', cache: 'no-store',
          redirect: 'error', headers: headers, signal: controller.signal,
          body: method === 'POST' ? JSON.stringify(body || {}) : undefined
        });
        if (!/application\/json/i.test(response.headers.get('content-type') || '')) {
          return failure(submitting ? 'UNKNOWN_ORDER_STATE' : 'INVALID_RESPONSE', submitting
            ? 'The order result is unknown. Refresh account activity to reconcile it before trying another order.'
            : 'The account service returned an unreadable response. Try refreshing its status.');
        }
        var data = await response.json();
        if (!object(data)) throw new Error('Invalid response');
        if (!response.ok) {
          if (response.status === 401) { csrf = null; statusData = null; }
          if (submitting && response.status >= 500) return failure('UNKNOWN_ORDER_STATE', 'The order result is unknown. Refresh account activity to reconcile it before trying another order.');
          return object(data.error) && typeof data.error.code === 'string' && typeof data.error.message === 'string'
            ? { ok: false, error: { code: data.error.code, message: data.error.message } }
            : failure('SERVICE_ERROR', 'The account service could not complete this request.');
        }
        return { ok: true, data: data };
      } catch (_) {
        return failure(submitting ? 'UNKNOWN_ORDER_STATE' : 'CONNECTION_FAILED', submitting
          ? 'The order result is unknown. Refresh account activity to reconcile it before trying another order.'
          : 'The account service could not be reached. Your last account view may be out of date.');
      } finally { clearTimeout(timer); }
    }
    async function load(force) {
      if (config && !force) return { ok: true, data: config };
      if (loading) return loading;
      loading = (async function () {
        var path = new URL('trading-config.json', location.href).pathname;
        var result = await request(path, 'GET');
        if (!result.ok) { config = null; csrf = null; statusData = null; return result; }
        var v = result.data;
        if (v.version !== 1 || typeof v.enabled !== 'boolean' || v.broker !== 'alpaca' ||
            (v.enabled ? v.api_base !== '/api' : v.api_base !== null)) {
          config = null; csrf = null; statusData = null;
          return failure('INVALID_CONFIG', 'Trading configuration could not be verified. Planning and confirmed fill entry remain available.');
        }
        config = { version: 1, enabled: v.enabled, api_base: v.api_base, broker: v.broker };
        if (!config.enabled) { csrf = null; statusData = null; }
        return { ok: true, data: config };
      }());
      try { return await loading; } finally { loading = null; }
    }
    async function ready() {
      var result = await load();
      if (!result.ok) return result;
      return config.enabled ? { ok: true } : failure('TRADING_UNAVAILABLE', 'Broker connection is not enabled on this copy of SpicyStock. You can plan trades and record confirmed fills.');
    }
    async function call(path, method, body) {
      var result = await ready();
      return result.ok ? request(path, method, body) : result;
    }
    async function status() {
      var result = await call('/api/status', 'GET');
      if (result.ok) {
        var v = result.data;
        if (v.version !== 1 || typeof v.connected !== 'boolean' ||
            ['unconfigured', 'not_connected', 'paper', 'live', 'reconciliation_needed'].indexOf(v.state) < 0 ||
            (v.connected && (['paper', 'live'].indexOf(v.mode) < 0 || typeof v.csrf_token !== 'string' || !v.csrf_token))) {
          csrf = null; statusData = null;
          return failure('INVALID_RESPONSE', 'The account connection could not be verified. Reconnect before continuing.');
        }
        csrf = v.connected ? v.csrf_token : null;
        statusData = Object.assign({}, v); delete statusData.csrf_token;
        result = { ok: true, data: Object.assign({}, statusData) };
      } else { csrf = null; statusData = null; }
      return result;
    }
    return {
      load: load, status: status,
      getState: function () { return { config: config && Object.assign({}, config), status: statusData && Object.assign({}, statusData), connected: !!(statusData && statusData.connected) }; },
      portfolio: function () { return call('/api/portfolio', 'GET'); },
      quote: function (symbol) {
        if (typeof symbol !== 'string' || !/^[A-Z][A-Z0-9.-]{0,14}$/.test(symbol)) return Promise.resolve(failure('INVALID_SYMBOL', 'Choose a valid stock symbol.'));
        return call('/api/quote?symbol=' + encodeURIComponent(symbol), 'GET');
      },
      preview: function (values) { return call('/api/preview', 'POST', values); },
      submit: function (previewId) {
        if (typeof previewId !== 'string' || !previewId || previewId.length > 128) return Promise.resolve(failure('INVALID_PREVIEW', 'Review a current trade plan before submitting.'));
        return call('/api/orders', 'POST', { preview_id: previewId, confirmation: 'submit' });
      },
      disconnect: async function () {
        var result = await call('/api/disconnect', 'POST', {});
        if (result.ok) { csrf = null; statusData = null; }
        return result;
      },
      connect: async function (mode) {
        mode = mode || 'paper';
        if (mode !== 'paper' && mode !== 'live') return failure('INVALID_MODE', 'Choose paper or live trading.');
        var result = await ready();
        if (!result.ok) return result;
        location.assign(endpoint('/api/connect?mode=' + mode));
        return { ok: true, data: { navigating: true } };
      }
    };
  }
  if (typeof module === 'object' && module.exports) module.exports = { createClient: createClient };
  else root.SCTradeBridge = createClient();
}(typeof window !== 'undefined' ? window : globalThis));
