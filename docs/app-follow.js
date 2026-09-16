/* SpicyStock — Following: the setups the reader chose to keep in view, saved
   in this browser only. A saved plan, not a trade, a fill or a position:
   the store holds the setup's own snapshot (its levels, its suggested whole-
   share quantity, its sentences), a frozen copy of the evidence the record
   carried for that signal, a bounded history of the later closes the page has
   been shown since, plus one optional reference size of the reader's — and
   never a purchase price, an execution or a P&L. Nothing here reaches the
   record, the repository, the email or the model's scorecard.

   v4 adds an explicit choice of a published plan, independently of saving or
   legacy personal notes. Its timestamp proves only browser-local selection.
   One dated public model outcome may be cached by exact plan receipt; it is
   never a personal fill, position or result, and never changes the original.

     Mutators below return Promises and acquire the same origin-wide Web Lock.
     SCStock.follow.setDemo(bool)      -> demo follows live under their own key
     SCStock.follow.status()           -> {available, error, count, migration, notes}
     SCStock.follow.list()             -> [item]  (validated; a corrupt store is set aside)
     SCStock.follow.find(id)           -> item | null
     SCStock.follow.add(setup)         -> {ok, item, existed, evidenceDropped, error}
     SCStock.follow.remove(id)         -> {ok, error}
     SCStock.follow.setShares(id, n)   -> {ok, item, error}   (n = null clears the override)
     SCStock.follow.observe(updates)   -> {ok, changed, added, revised, ignored, error}
     SCStock.follow.attachEvidence(id, ev) -> {ok, attached}  (once, never over an original)
     SCStock.follow.commit('selectPlan', setup, expectedSaved) -> atomically save/select
     SCStock.follow.commit('observePlans', updates) -> retain exact public outcomes
     SCStock.follow.identity(setup)    -> the id: kind, ticker, session, rules identity
     SCStock.follow.onChange(fn)       -> another tab wrote; fn() to re-read

   An item: {v, id, ticker, kind, stage, session, rules_version, saved_at,
             suggested_shares, reference_shares, demo, snapshot: {...},
             evidence: {series, anchors, recovered, from} | null, observations: [obs]}
   An observation: {date, c, o, h, l, v, from_session, from_rules, source,
                    basis, revised, revised_from}

   THE RULES THE MERGE KEEPS, because a saved setup outlives the record it
   came from:
     * the original is immutable — snapshot, evidence, levels, grade, reason,
       rules identity and signal close are written once, by add(), and no
       later record touches them;
     * one observation per market DATE, so a re-render, a reload or a theme
       change adds nothing;
     * an OLDER record never replaces a newer observation;
     * a different close on a date already observed is a REVISION of that
       trading day, carrying what it replaced — never a new day;
     * a session nothing was seen for stays missing: nothing is forward-filled
       and no price is invented;
     * the newest OBSERVATION_MAX dates are kept, and the original baseline is
       not one of them and is never dropped. */
(function (w) {
  'use strict';
  const SCStock = w.SCStock = w.SCStock || {};
  const VERSION = 4;
  const KEY = 'spicystock:following:v1';
  const DEMO_KEY = 'spicystock:following:demo:v1';
  //: the migrated-from payload, kept beside the store and never read back into it
  const BACKUP = '.previous';
  //: the unreadable payload, set aside rather than over
  const CORRUPT = '.corrupt';
  //: entries that could not be repaired, kept out of the list and named
  const REJECTED = '.rejected';
  const SHARES_MAX = 1000000;
  //: distinct market sessions kept per saved setup: a display and storage
  //: bound, and not a statement about how long a setup is held
  const OBSERVATION_MAX = 20;
  //: bars of the original chart one follow may freeze -- the record's own
  //: per-name cap (pipeline.SERIES_BARS), so a copy is never larger than the
  //: thing it copies
  const EVIDENCE_BARS = 120;
  const ISO = /^\d{4}-\d{2}-\d{2}$/;
  let demo = false;
  const keyFor = () => (demo ? DEMO_KEY : KEY);
  const isInt = (v) => typeof v === 'number' && isFinite(v) && Math.floor(v) === v;
  const isNum = (v) => typeof v === 'number' && isFinite(v);
  const text = (v) => (typeof v === 'string' ? v : '');
  const isDate = (v) => typeof v === 'string' && ISO.test(v);
  const num = (v) => (isNum(v) ? v : null);
  const REF_FIELDS = ['id', 'context_sha256', 'plan_sha256', 'pick_sha256'];
  function planReference(snapshot) {
    const ref = (snapshot || {}).evidence_ref;
    return ref && ref.version === 1 && REF_FIELDS.every(k => /^[a-f0-9]{64}$/.test(ref[k]))
      ? Object.fromEntries(['version', ...REF_FIELDS].map(k => [k, ref[k]])) : null;
  }
  function sameReference(a, b) {
    return !!(a && b && a.version === 1 && b.version === 1 && REF_FIELDS.every(k => a[k] === b[k]));
  }
  function selectedPlan(item) {
    const s = item && item.plan_selection;
    if (!s || s.version !== 1 || !Number.isFinite(Date.parse(s.selected_at)) || (item.snapshot || {}).status !== 'ticket') return null;
    const ref = planReference(item.snapshot);
    if (s.basis === 'published-receipt' ? !sameReference(s.reference, ref) : s.basis !== 'legacy-snapshot' || s.reference !== null) return null;
    return s;
  }
  function matchesPlan(item, row) {
    const s = selectedPlan(item);
    return !!(s && s.reference && row && row.ticker === item.ticker && row.kind === item.kind && row.picked === item.session &&
      sameReference(s.reference, row.evidence_ref));
  }

  function storage() {
    try { return w.localStorage || null; } catch (e) { return null; }
  }
  // is the store usable at all: a write that reads back
  function available() {
    const s = storage();
    if (!s) return false;
    try { s.setItem(KEY + '.probe', '1'); const ok = s.getItem(KEY + '.probe') === '1'; s.removeItem(KEY + '.probe'); return ok; } catch (e) { return false; }
  }

  // ------------------------------------------------------------ shapes, one level in
  // Every structure that comes off disk is read through one of these before a
  // consumer indexes into it: a bar with no date or no finite close is not a
  // bar, and an entry that cannot be repaired is set aside by name rather than
  // dropped in silence.
  function cleanBar(b) {
    if (!b || typeof b !== 'object' || !isDate(b.date) || !isNum(b.c)) return null;
    return { date: b.date, o: num(b.o), h: num(b.h), l: num(b.l), c: b.c, v: num(b.v) };
  }
  function cleanObs(o) {
    const bar = cleanBar(o);
    if (!bar) return null;
    const out = Object.assign({}, o, bar, {
      from_session: isDate(o.from_session) ? o.from_session : null,
      from_rules: text(o.from_rules), source: text(o.source) || 'record',
      basis: ['match', 'adjusted', 'unknown'].indexOf(o.basis) >= 0 ? o.basis : 'unknown'
    });
    if (o.revised) {
      const was = o.revised_from && typeof o.revised_from === 'object' ? o.revised_from : null;
      out.revised = true;
      out.revised_from = was && isNum(was.c) ? { c: was.c, from_session: isDate(was.from_session) ? was.from_session : null } : null;
    }
    return out;
  }
  // the newest OBSERVATION_MAX dates, oldest first, one entry per date
  function boundObs(list) {
    const byDate = {};
    (Array.isArray(list) ? list : []).forEach((o) => { const c = cleanObs(o); if (c) byDate[c.date] = c; });
    return Object.keys(byDate).sort().slice(-OBSERVATION_MAX).map((d) => byDate[d]);
  }
  function cleanEvidence(e, session) {
    if (!e || typeof e !== 'object') return null;
    // only bars at or before the signal's own session: the original view is
    // what was on the screen that night, never a candle printed since
    const series = (Array.isArray(e.series) ? e.series : []).map(cleanBar)
      .filter((b) => b && (!isDate(session) || b.date <= session)).slice(-EVIDENCE_BARS);
    const anchors = (Array.isArray(e.anchors) ? e.anchors : []).filter((a) => a && typeof a === 'object' && text(a.key) && isDate(a.from) && isDate(a.to) && a.to <= session)
      .slice(0, 8).map((a) => ({ key: text(a.key), label: text(a.label), from: a.from, to: a.to, low: num(a.low), high: num(a.high) }));
    if (!series.length) return null;
    return Object.assign({}, e, { series: series, anchors: anchors, recovered: !!e.recovered,
      from: Object.assign({}, e.from || {}, { session: isDate(e.from && e.from.session) ? e.from.session : null, rules_version: text(e.from && e.from.rules_version) }) });
  }
  // An entry off disk, repaired rather than discarded: what can be read is
  // kept and what cannot is named. Identity is the one thing that cannot be
  // repaired -- an entry with no symbol, session or id is not a saved setup.
  function coerceItem(it, problems) {
    if (!it || typeof it !== 'object' || !text(it.id) || !text(it.ticker) || !isDate(it.session) || !text(it.kind)
        || !it.snapshot || typeof it.snapshot !== 'object') return null;
    const shares = (v) => (isInt(v) && v > 0 && v <= SHARES_MAX ? v : null);
    const raw = Array.isArray(it.observations) ? it.observations : [];
    const before = { bad: raw.filter((o) => !cleanObs(o)).length, ev: !!(it.evidence && Array.isArray(it.evidence.series) && it.evidence.series.length) };
    const out = Object.assign({}, it, {
      v: VERSION, id: it.id, ticker: it.ticker, kind: it.kind, stage: text(it.stage), session: it.session,
      rules_version: text(it.rules_version), saved_at: text(it.saved_at), demo: !!it.demo,
      suggested_shares: shares(it.suggested_shares), reference_shares: shares(it.reference_shares),
      snapshot: it.snapshot, evidence: cleanEvidence(it.evidence, it.session), observations: boundObs(it.observations)
    });
    if (before.ev && !out.evidence) problems.push(out.ticker + ': the saved chart could not be read and was left out; the setup itself is unchanged.');
    if (before.bad) problems.push(out.ticker + ': ' + before.bad + (before.bad === 1 ? ' saved observation had no date or no price' : ' saved observations had no date or no price') + ' and was left out; the setup itself is unchanged.');
    return out;
  }

  // A store set aside and a store upgraded are one-time events: they are
  // remembered for as long as the page is open rather than left in lastError,
  // which the NEXT read clears -- the first reader of the store would
  // otherwise be the only one ever told.
  let lastError = null, lastNotes = [], migration = null, frozen = null, aside = null;
  let inTransaction = false, migrationQueued = false, writeBlocked = null;
  let envelope = {};
  // A store this page does not understand is LEFT ALONE: it is read as empty
  // for display and every write is refused, because overwriting a newer
  // schema with this one's idea of a list would throw away the reader's data.
  function readRaw(s) {
    let raw;
    try { raw = s.getItem(keyFor()); } catch (e) { return { blocked: true }; }
    if (!raw) return { empty: true };
    let parsed = null;
    try { parsed = JSON.parse(raw); } catch (e) { parsed = null; }
    return { raw: raw, parsed: parsed };
  }
  function read() {
    lastNotes = [];
    const s = storage();
    if (!s) { lastError = 'This browser offers no storage, so nothing can be followed here.'; return []; }
    const got = readRaw(s);
    if (got.blocked) { writeBlocked = 'Storage could not be read; nothing was overwritten.'; lastError = 'Storage is blocked in this browser; nothing can be followed here.'; return []; }
    if (got.empty) { lastError = null; frozen = null; envelope = {}; return []; }
    const parsed = got.parsed;
    envelope = parsed && typeof parsed === 'object' ? parsed : {};
    writeBlocked = null;
    if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.items) || !isInt(parsed.version)) {
      // set the unreadable list aside, never over it
      try { s.setItem(keyFor() + CORRUPT, got.raw); if (s.getItem(keyFor() + CORRUPT) !== got.raw) throw new Error('backup'); s.removeItem(keyFor()); } catch (e) { writeBlocked = 'The unreadable saved list could not be backed up; it was left untouched.'; }
      aside = 'The saved list in this browser could not be read and was set aside; it starts empty.';
      lastError = aside;
      frozen = null;
      return [];
    }
    if (parsed.version > VERSION) {
      frozen = parsed.version;
      lastError = 'This browser holds a saved list from a newer version of this page (' + parsed.version + '); it has been left untouched, and nothing can be saved here until that page is used again.';
      return [];
    }
    frozen = null;
    const problems = [], rejected = [];
    const items = [];
    parsed.items.forEach((it) => { const c = coerceItem(it, problems); if (c) items.push(c); else rejected.push(it); });
    if (rejected.length) {
      // an entry with no identity is kept OUT of the list and beside it, named
      try { const backup = JSON.stringify({ version: parsed.version, items: rejected }); s.setItem(keyFor() + REJECTED, backup); if (s.getItem(keyFor() + REJECTED) !== backup) throw new Error('backup'); } catch (e) { writeBlocked = 'Unreadable entries could not be backed up; nothing was overwritten.'; }
      problems.push(rejected.length === 1 ? 'One saved entry had no symbol or session to identify it; it was set aside rather than shown.'
        : rejected.length + ' saved entries had no symbol or session to identify them; they were set aside rather than shown.');
    }
    if (parsed.version < VERSION) {
      if (inTransaction) migrate(s, got.raw, items, problems);
      else if (!migrationQueued) {
        migrationQueued = true;
        Promise.resolve().then(() => commit('migrate')).then(() => {
          // This tab receives no storage event for its own asynchronous upgrade.
          // Report success or failure while the guard prevents a failed backup
          // from immediately queuing another migration during the UI refresh.
          listeners.forEach((fn) => { try { fn(); } catch (err) { /* keep other listeners */ } });
        }).finally(() => { migrationQueued = false; });
      }
    }
    lastNotes = problems;
    lastError = problems.length ? problems[0] : null;
    return items;
  }
  // The old payload is preserved BEFORE the new one is written and the new one
  // is read back before the migration is called done; a write that does not
  // read back leaves the old list exactly where it was.
  function migrate(s, raw, items, problems) {
    migration = { from: envelope.version, to: VERSION, kept: items.length, ok: false };
    let backupKey;
    try {
      backupKey = s.getItem(keyFor() + BACKUP) ? keyFor() + BACKUP + '.v' + envelope.version : keyFor() + BACKUP;
      if (!s.getItem(backupKey)) s.setItem(backupKey, raw);
      if (s.getItem(backupKey) !== raw) throw new Error('the copy did not read back');
    } catch (e) {
      migration.error = 'The saved list could not be copied before upgrading it, so it was left as it was; it still reads here.';
      problems.push(migration.error);
      writeBlocked = migration.error;
      return;
    }
    const payload = JSON.stringify(Object.assign({}, envelope, { version: VERSION, items: items }));
    try {
      s.setItem(keyFor(), payload);
      if (s.getItem(keyFor()) !== payload) throw new Error('the upgrade did not read back');
    } catch (e) {
      try { s.setItem(keyFor(), raw); } catch (e2) { /* the old payload is still under BACKUP */ }
      migration.error = 'The saved list could not be upgraded in this browser; it was left as it was.';
      problems.push(migration.error);
      writeBlocked = migration.error;
      return;
    }
    migration.ok = true;
    // the sentence lives on `migration` rather than in the notes, because the
    // notes are re-read off a store that is no longer the old one: a reader
    // who upgraded should still be told, on the render that follows
    migration.note = problems.concat(items.length + ' saved setups were carried over with original evidence and reference shares unchanged. Existing notes and reference amounts keep their original meaning; no plan selection was inferred.').join(' ');
    problems.push(migration.note);
  }
  function write(items) {
    const s = storage();
    if (!s || frozen || writeBlocked) return { ok: false, error: writeBlocked || 'Storage is blocked or from a newer version; nothing was written over it.' };
    const payload = JSON.stringify(Object.assign({}, envelope, { version: VERSION, items: items }));
    let before;
    try {
      before = s.getItem(keyFor());
      s.setItem(keyFor(), payload);
      if (s.getItem(keyFor()) !== payload) throw new Error('readback');
      lastError = null;
      return { ok: true };
    } catch (e) {
      // Restore the prior valid payload after a write/readback failure. Keep
      // the proposed input in memory; the UI also retains its editable draft.
      pendingWrite = { prior: before === undefined ? null : before, proposed: payload };
      try { if (before !== undefined) { if (before === null) s.removeItem(keyFor()); else s.setItem(keyFor(), before); } } catch (ignored) { /* backup/draft remain recoverable */ }
      return { ok: false, error: 'Could not confirm the save. Prior data was retained where storage allowed; your input remains available to retry. Keep this tab open to download a recovery copy.' };
    }
  }
  let pendingWrite = null;
  // All page writes use an origin-wide Web Lock, including observation
  // ingestion and migration. Read again INSIDE the lock: no stale list can
  // replace another tab's save. Conflicting edits use lock acquisition order;
  // editing an item removed by another tab fails rather than resurrecting it.
  async function commit(action, ...args) {
    const locks = w.navigator && w.navigator.locks;
    if (!locks) return { ok: false, error: 'Safe saving needs browser Web Locks (HTTPS). Your existing setups are still readable.' };
    const key = keyFor();
    try { return await locks.request(key, () => {
      if (key !== keyFor()) return { ok: false, error: 'The record changed before saving. Please retry.' };
      inTransaction = true;
      try {
        if (action === 'migrate') { read(); return { ok: !writeBlocked && !frozen }; }
        const operations = { add, remove, setShares, setAnnotation, observe, attachEvidence, selectPlan, clearPlan, observePlans };
        if (!operations[action]) return { ok: false, error: 'Unknown saved setup action.' };
        return operations[action](...args);
      } finally { inTransaction = false; }
    }); } catch (error) { return { ok: false, error: 'Storage could not complete the save. Your input remains available to retry.' }; }
  }
  function parseAmount(raw) {
    if (raw === '' || raw === null) return null;
    if (typeof raw !== 'string' || !/^\d+(?:\.\d{1,2})?$/.test(raw)) return undefined;
    const [whole, fraction = ''] = raw.split('.');
    const cents = BigInt(whole) * 100n + BigInt((fraction + '00').slice(0, 2));
    return cents > 0n && cents <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(cents) : undefined;
  }
  function setAnnotation(id, field, value) {
    const amount = field === 'amount' ? parseAmount(value) : null;
    if (field === 'amount' && amount === undefined) return { ok: false, error: 'Enter a positive USD amount with at most two decimal places, or clear it.' };
    if (field !== 'amount' && (field !== 'taken' || typeof value !== 'boolean')) return { ok: false, error: 'Invalid annotation.' };
    const items = read(), item = items.find(it => it.id === id);
    if (!item) return { ok: false, error: 'That setup was removed. Your input has not been saved.' };
    const a = Object.assign({}, item.annotation || {}), now = new Date().toISOString();
    if (field === 'amount') { a.reference_amount = amount === null ? null : { currency: 'USD', minor_units: amount }; a.amount_marked_at = now; }
    else { a.taken = value; a.taken_marked_at = now; }
    item.annotation = a;
    const res = write(items);
    return res.ok ? { ok: true, item } : res;
  }
  function identity(setup) {
    const base = [text(setup.kind) || 'setup', text(setup.ticker), text(setup.session), text(setup.rules_version) || 'rules'].join(':');
    return setup.revision_id ? base + ':' + text(setup.revision_id) : base;
  }
  // A follow keeps the setup's own evidence. When the write will not fit, the
  // setup is saved WITHOUT its chart and says so: a follow that reports
  // success having saved nothing is the one thing this must never do.
  function add(setup) {
    if (!setup || !text(setup.ticker) || !isDate(setup.session)) return { ok: false, error: 'Nothing to follow: the setup has no symbol or a session this page can read.' };
    const items = read(), id = identity(setup);
    const existing = items.find((it) => it.id === id);
    if (existing) return { ok: true, item: existing, existed: true };
    const item = newItem(setup);
    if (!item) return { ok: false, error: 'Nothing to follow: the setup has no symbol or a session this page can read.' };
    return writeAdded(items, item);
  }
  function newItem(setup) {
    return coerceItem({
      id: identity(setup), ticker: text(setup.ticker), kind: text(setup.kind) || 'setup', stage: text(setup.stage), session: setup.session,
      rules_version: text(setup.rules_version), provenance: setup.provenance || null, saved_at: new Date().toISOString(),
      suggested_shares: setup.suggested_shares, reference_shares: null,
      snapshot: setup.snapshot && typeof setup.snapshot === 'object' ? setup.snapshot : {},
      evidence: setup.evidence || null, observations: setup.observations || [], demo: demo
    }, []);
  }
  function writeAdded(items, item) {
    let res = write(items.concat([item]));
    if (!res.ok && item.evidence) {
      // the chart is the large part; the setup is the point
      const lean = Object.assign({}, item, { evidence: null, evidence_dropped: true });
      const retry = write(items.concat([lean]));
      if (retry.ok) return { ok: true, item: lean, existed: false, evidenceDropped: true };
    }
    return res.ok ? { ok: true, item: item, existed: false } : { ok: false, error: res.error };
  }
  // One locked write saves and selects a published plan. A stale control for
  // an existing item cannot resurrect an item removed by another tab.
  function selectPlan(setup, expectedSaved) {
    if (!setup || !text(setup.ticker) || !isDate(setup.session)) return {ok:false, error:'No recorded setup to select.'};
    const items = read(), existing = items.find(it => it.id === (expectedSaved && setup.id ? setup.id : identity(setup)));
    if (expectedSaved && !existing) return {ok:false, error:'That setup was removed. Reopen it before selecting a plan.'};
    if (existing && !setup.id) {
      const incoming = planReference(setup.snapshot), original = planReference(existing.snapshot);
      const same = incoming || original ? sameReference(incoming, original)
        : JSON.stringify((setup.snapshot || {}).published_plan || {}) === JSON.stringify(existing.snapshot.published_plan || {}) &&
          text((setup.provenance || {}).published_at) === text((existing.provenance || {}).published_at);
      if (!same) return {ok:false, error:'A different publication was saved in another tab. Open the saved original before selecting its plan.'};
    }
    const item = existing || newItem(setup), snap = item && item.snapshot;
    if (!snap || snap.status !== 'ticket' || !((snap.published_plan || {}).order_json || text(snap.order_line) || text(snap.instruction)))
      return {ok:false, error:'This setup has no published ticket to follow.'};
    if (selectedPlan(item)) return {ok:true, item, existed:!!existing};
    const reference = planReference(snap);
    item.plan_selection = {version:1, selected_at:new Date().toISOString(),
      basis:reference ? 'published-receipt' : 'legacy-snapshot', reference};
    if (!existing) return writeAdded(items, item);
    const res = write(items); return res.ok ? {ok:true, item, existed:true} : res;
  }
  function clearPlan(id) {
    const items = read(), item = items.find(it => it.id === id);
    if (!item) return {ok:false, error:'That setup was removed.'};
    delete item.plan_selection; delete item.model_observation;
    const res = write(items); return res.ok ? {ok:true, item} : res;
  }
  function observePlans(updates) {
    const items = read(); let changed = false;
    (Array.isArray(updates) ? updates : []).forEach(update => {
      const item = items.find(it => it.id === update.id);
      if (!item || !matchesPlan(item, update.row) || !isDate(update.from_session) || update.from_session < item.session ||
          update.row.last_date != null && (!isDate(update.row.last_date) || update.row.last_date > update.from_session) || typeof update.row.status !== 'string') return;
      const old = item.model_observation;
      if (old && (old.from_session > update.from_session || old.from_session === update.from_session && text(old.published_at) > text(update.published_at))) return;
      const next = {row:update.row, from_session:update.from_session, published_at:text(update.published_at), rules_version:text(update.rules_version)};
      if (JSON.stringify(old) !== JSON.stringify(next)) {item.model_observation = next; changed = true;}
    });
    if (!changed) return {ok:true, changed:false};
    const res = write(items); return res.ok ? {ok:true, changed:true} : res;
  }
  // A setup saved before this page saved charts carries none, because none
  // was saved then. One may be RECOVERED, and only from a record that IS this
  // signal -- the same kind, symbol, session and rules identity -- never from
  // a newer setup for the same ticker, which is a different signal with its
  // own bars. It is written once: an item that already has evidence is left
  // exactly as it is, so nothing a later record carries can rewrite an
  // original.
  function attachEvidence(id, evidence) {
    const items = read(), item = items.find((it) => it.id === id);
    if (!item || item.evidence) return { ok: true, attached: false };
    const clean = cleanEvidence(Object.assign({}, evidence, { recovered: true }), item.session);
    if (!clean) return { ok: true, attached: false };
    item.evidence = clean;
    const res = write(items);
    return res.ok ? { ok: true, attached: true, item: item } : { ok: false, attached: false, error: res.error };
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

  // ------------------------------------------------------------ the observation merge
  // One incoming bar against what is already saved for that date. The verdict
  // is the whole rule set in one place, so the shelf, the saved detail and the
  // tests all read the same answer.
  function mergeOne(existing, inc) {
    if (!existing) return { action: 'added', obs: inc };
    if (existing.c === inc.c) {
      // the same close from a fuller source: the bar is completed, which is
      // not a revision -- the price never moved
      const richer = existing.o === null && inc.o !== null;
      return { action: 'duplicate', obs: richer ? Object.assign({}, inc, { revised: existing.revised, revised_from: existing.revised_from }) : existing };
    }
    // an older record cannot replace what a newer one already said
    if (existing.from_session && inc.from_session && inc.from_session < existing.from_session) return { action: 'ignored', obs: existing };
    return { action: 'revised', obs: Object.assign({}, inc, { revised: true, revised_from: { c: existing.c, from_session: existing.from_session } }) };
  }
  // `updates` is [{id, bars: [bar], from_session, from_rules, source, basis}].
  // One read and at most one write for the whole shelf, so a record that
  // observes twenty setups cannot race itself; a merge that changes nothing
  // writes nothing, which is what makes a re-render, a reload and a theme
  // change cost no observation.
  function observe(updates) {
    if (!Array.isArray(updates) || !updates.length) return { ok: true, changed: false, added: 0, revised: 0, ignored: 0 };
    const items = read();
    if (!items.length) return { ok: true, changed: false, added: 0, revised: 0, ignored: 0 };
    const before = JSON.stringify(items.map((it) => it.observations));
    let added = 0, revised = 0, ignored = 0;
    updates.forEach((u) => {
      const item = items.find((it) => it.id === (u && u.id));
      if (!item) return;
      const byDate = {};
      item.observations.forEach((o) => { byDate[o.date] = o; });
      (Array.isArray(u.bars) ? u.bars : []).forEach((raw) => {
        const bar = cleanBar(raw);
        // the signal's own session is the baseline the snapshot froze; a later
        // record's copy of it is evidence about the basis, never an observation
        if (!bar || bar.date <= item.session) return;
        const inc = cleanObs(Object.assign({}, bar, { from_session: raw.from_session || u.from_session, from_rules: raw.from_rules || u.from_rules, revised: raw.revised, revised_from: raw.revised_from,
          source: text(raw.source) || u.source, basis: u.basis }));
        if (!inc) return;
        const got = mergeOne(byDate[bar.date], inc);
        if (got.action === 'added') added++;
        else if (got.action === 'revised') revised++;
        else if (got.action === 'ignored') ignored++;
        byDate[bar.date] = got.obs;
      });
      item.observations = boundObs(Object.keys(byDate).map((d) => byDate[d]));
    });
    const after = JSON.stringify(items.map((it) => it.observations));
    if (after === before) return { ok: true, changed: false, added: 0, revised: 0, ignored: ignored };
    const res = write(items);
    return res.ok ? { ok: true, changed: true, added: added, revised: revised, ignored: ignored }
      : { ok: false, changed: false, added: 0, revised: 0, ignored: ignored, error: res.error };
  }

  // another tab writing this origin's storage: the shelf is re-read, never merged from memory
  const listeners = [];
  try {
    w.addEventListener('storage', (e) => {
      if (!e || (e.key !== KEY && e.key !== DEMO_KEY)) return;
      listeners.forEach((fn) => { try { fn(); } catch (err) { /* one listener cannot stop the rest */ } });
    });
  } catch (e) { /* no window events here; the page still reads on render */ }

  SCStock.follow = {
    VERSION: VERSION, KEY: KEY, DEMO_KEY: DEMO_KEY, SHARES_MAX: SHARES_MAX,
    OBSERVATION_MAX: OBSERVATION_MAX, EVIDENCE_BARS: EVIDENCE_BARS,
    setDemo: function (v) { demo = !!v; },
    status: function () {
      const ok = available();
      const items = read();
      return { available: ok, error: ok ? (lastError || aside) : (lastError || 'Storage is blocked in this browser; nothing can be followed here.'),
        count: items.length, notes: lastNotes.slice(), migration: migration, aside: aside, frozen: frozen };
    },
    list: function () { return read(); },
    find: function (id) { return read().find((it) => it.id === id) || null; },
    commit: commit, parseAmount: parseAmount, setAnnotation: (...a) => commit('setAnnotation', ...a), pending: () => pendingWrite,
    selectedPlan, matchesPlan, planReference,
    add: (...a) => commit('add', ...a), remove: (...a) => commit('remove', ...a), setShares: (...a) => commit('setShares', ...a), observe: (...a) => commit('observe', ...a), attachEvidence: (...a) => commit('attachEvidence', ...a), identity: identity,
    onChange: function (fn) { if (typeof fn === 'function') listeners.push(fn); }
  };
})(window);
