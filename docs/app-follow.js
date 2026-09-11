/* SpicyStock — Following: the setups the reader chose to keep in view, saved
   in this browser only. A saved plan, not a trade, a fill or a position:
   the store holds the setup's own snapshot (its levels, its suggested whole-
   share quantity, its sentences) plus one optional reference size of the
   reader's, and never a purchase price, an execution or a P&L. Nothing here
   reaches the record, the repository, the email or the model's scorecard.

     SCStock.follow.setDemo(bool)      -> demo follows live under their own key
     SCStock.follow.status()           -> {available, error}
     SCStock.follow.list()             -> [item]  (validated; a corrupt store is set aside)
     SCStock.follow.add(setup)         -> {ok, item, existed, error}
     SCStock.follow.remove(id)         -> {ok, error}
     SCStock.follow.setShares(id, n)   -> {ok, item, error}   (n = null clears the override)
     SCStock.follow.identity(setup)    -> the id: kind, ticker, session, rules identity

   An item: {id, ticker, kind, stage, session, rules_version, saved_at,
             suggested_shares, reference_shares, snapshot: {...}, demo} */
(function (w) {
  'use strict';
  const SCStock = w.SCStock = w.SCStock || {};
  const VERSION = 1;
  const KEY = 'spicystock:following:v1';
  const DEMO_KEY = 'spicystock:following:demo:v1';
  const SHARES_MAX = 1000000;
  let demo = false;
  const keyFor = () => (demo ? DEMO_KEY : KEY);
  const isInt = (v) => typeof v === 'number' && isFinite(v) && Math.floor(v) === v;
  const text = (v) => (typeof v === 'string' ? v : '');

  function storage() {
    try { return w.localStorage || null; } catch (e) { return null; }
  }
  // is the store usable at all: a write that reads back
  function available() {
    const s = storage();
    if (!s) return false;
    try { s.setItem(KEY + '.probe', '1'); const ok = s.getItem(KEY + '.probe') === '1'; s.removeItem(KEY + '.probe'); return ok; } catch (e) { return false; }
  }
  function validItem(it) {
    return !!it && typeof it === 'object' && text(it.id) && text(it.ticker) && text(it.session) && text(it.kind)
      && (it.suggested_shares === null || isInt(it.suggested_shares)) && (it.reference_shares === null || isInt(it.reference_shares))
      && it.snapshot && typeof it.snapshot === 'object';
  }
  let lastError = null;
  function read() {
    const s = storage();
    if (!s) { lastError = 'This browser offers no storage, so nothing can be followed here.'; return []; }
    let raw;
    try { raw = s.getItem(keyFor()); } catch (e) { lastError = 'Storage is blocked in this browser; nothing can be followed here.'; return []; }
    if (!raw) { lastError = null; return []; }
    let parsed = null;
    try { parsed = JSON.parse(raw); } catch (e) { parsed = null; }
    if (!parsed || parsed.version !== VERSION || !Array.isArray(parsed.items)) {
      // set the unreadable list aside, never over it
      try { s.setItem(keyFor() + '.corrupt', raw); s.removeItem(keyFor()); } catch (e) { /* nothing more to do */ }
      lastError = 'The saved list in this browser could not be read and was set aside; it starts empty.';
      return [];
    }
    lastError = null;
    return parsed.items.filter(validItem);
  }
  function write(items) {
    const s = storage();
    if (!s) return { ok: false, error: 'This browser offers no storage, so nothing was saved.' };
    const payload = JSON.stringify({ version: VERSION, items: items });
    try {
      s.setItem(keyFor(), payload);
      if (s.getItem(keyFor()) !== payload) return { ok: false, error: 'The save did not read back; nothing is saved.' };
      lastError = null;
      return { ok: true };
    } catch (e) {
      return { ok: false, error: 'Could not save in this browser (storage is blocked or full); nothing is saved.' };
    }
  }
  function identity(setup) {
    return [text(setup.kind) || 'setup', text(setup.ticker), text(setup.session), text(setup.rules_version) || 'rules'].join(':');
  }
  function add(setup) {
    if (!setup || !text(setup.ticker) || !text(setup.session)) return { ok: false, error: 'Nothing to follow: the setup has no symbol or session.' };
    const items = read(), id = identity(setup);
    const existing = items.find((it) => it.id === id);
    if (existing) return { ok: true, item: existing, existed: true };
    const item = {
      id: id, ticker: text(setup.ticker), kind: text(setup.kind) || 'setup', stage: text(setup.stage), session: text(setup.session),
      rules_version: text(setup.rules_version), saved_at: new Date().toISOString(),
      suggested_shares: isInt(setup.suggested_shares) && setup.suggested_shares > 0 ? setup.suggested_shares : null,
      reference_shares: null, snapshot: setup.snapshot && typeof setup.snapshot === 'object' ? setup.snapshot : {}, demo: demo
    };
    items.push(item);
    const res = write(items);
    return res.ok ? { ok: true, item: item, existed: false } : { ok: false, error: res.error };
  }
  function remove(id) {
    const items = read(), kept = items.filter((it) => it.id !== id);
    if (kept.length === items.length) return { ok: true, removed: false };
    const res = write(kept);
    return res.ok ? { ok: true, removed: true } : { ok: false, error: res.error };
  }
  function setShares(id, n) {
    if (n !== null && !(isInt(n) && n >= 1 && n <= SHARES_MAX)) return { ok: false, error: 'A reference size is a whole number of shares from 1 to ' + SHARES_MAX.toLocaleString('en-US') + '.' };
    const items = read(), item = items.find((it) => it.id === id);
    if (!item) return { ok: false, error: 'That setup is no longer followed.' };
    item.reference_shares = n;
    const res = write(items);
    return res.ok ? { ok: true, item: item } : { ok: false, error: res.error };
  }
  SCStock.follow = {
    VERSION: VERSION, KEY: KEY, DEMO_KEY: DEMO_KEY, SHARES_MAX: SHARES_MAX,
    setDemo: function (v) { demo = !!v; },
    status: function () { const ok = available(); const items = ok ? read() : []; return { available: ok, error: ok ? lastError : (lastError || 'Storage is blocked in this browser; nothing can be followed here.'), count: items.length }; },
    list: function () { return read(); },
    find: function (id) { return read().find((it) => it.id === id) || null; },
    add: add, remove: remove, setShares: setShares, identity: identity
  };
})(window);
