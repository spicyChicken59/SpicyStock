/* Private, explicitly entered broker facts. The model owns storage, arithmetic
   and permission checks; rendering never interprets a click as execution. */
(function (w) {
  'use strict';
  const api = w.SCStock = w.SCStock || {}, d = w.document;
  const labels = {
    submitted_quantity: 'Total shares submitted', submitted_at: 'Submission time',
    filled_quantity: 'Cumulative entry shares filled', average_price: 'Average entry fill price ($)', filled_at: 'Latest entry fill time',
    cancelled_quantity: 'Unfilled entry shares cancelled', cancelled_at: 'Remainder cancellation time',
    exited_quantity: 'Cumulative filled shares sold / exited', average_exit_price: 'Average exit fill price ($)', exited_at: 'Latest exit time',
    entry_fees: 'Actual total entry fees ($)', exit_fees: 'Actual total exit fees ($)',
    protected_quantity: 'Current broker-confirmed protective shares', protection_confirmed_at: 'Protection checked by you at'
  };
  const groups = [
    ['Entry submission', ['submitted_quantity', 'submitted_at']],
    ['Entry fills', ['filled_quantity', 'average_price', 'filled_at']],
    ['Unfilled entry cancellation', ['cancelled_quantity', 'cancelled_at']],
    ['Exits after entry', ['exited_quantity', 'average_exit_price', 'exited_at']],
    ['Actual transaction costs', ['entry_fees', 'exit_fees']],
    ['Protective order at the broker', ['protected_quantity', 'protection_confirmed_at']]
  ];
  const money = value => '$' + (BigInt(value) / 100n).toLocaleString('en-US') + '.' + String(BigInt(value) % 100n).padStart(2, '0');
  const clock = value => value ? new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', dateStyle: 'medium', timeStyle: 'long' }).format(new Date(value)) : 'Not reported';
  const amount = value => value === null || value === undefined ? 'Unknown' : String(value);
  let host = null, selected = null, editing = null, research = null, dirty = false, busy = false;
  let backupPreview = null, backupReading = false, backupGeneration = 0;
  const independent = item => item && item.kind === 'independent_research';
  const ticker = item => independent(item) ? item.source.ticker : item.plan.ticker;
  const publication = item => independent(item) ? item.source.publication : item.publication;
  const session = item => independent(item) ? item.source.publication.measured_session : item.publication.session;
  function node(tag, attrs, text) {
    const item = d.createElement(tag);
    Object.entries(attrs || {}).forEach(([key, value]) => item.setAttribute(key, value));
    if (text !== undefined) item.textContent = text;
    return item;
  }
  function button(text, attrs) { return node('button', { type: 'button', class: 'sc-btn sc-btn--secondary sc-btn--sm', ...attrs }, text); }
  function message(text) { if (host) host.querySelector('[data-handoff-message]').textContent = text; }
  function facts(target, rows) {
    target.replaceChildren(...rows.map(([label, value]) => { const row = node('div'); row.append(node('dt', {}, label), node('dd', {}, String(value))); return row; }));
  }
  function loadEditor(item) {
    editing = item; research = null; dirty = false;
    api.handoff.FIELDS.forEach(key => { host.querySelector('[data-handoff-field="' + key + '"]').value = item && item.report[key] !== null ? String(item.report[key]) : ''; });
    host.querySelector('[data-handoff-delete-confirm]').checked = false;
  }
  function selectedItem(items) { return items.find(item => item.id === selected) || null; }
  function choose(id) {
    const item = api.handoff.find(id);
    if (!item) return;
    selected = id; loadEditor(item); message(''); update();
  }
  async function saveReport() {
    if (busy || !editing && !research) return;
    const id = editing && editing.id, revision = editing && editing.revision, pending = research;
    const fields = Object.fromEntries(api.handoff.FIELDS.map(key => [key, host.querySelector('[data-handoff-field="' + key + '"]').value]));
    busy = true; update();
    const result = pending ? await api.handoff.reportResearch(pending.request, fields, null) : await api.handoff.report(id, fields, revision);
    busy = false;
    if (result.ok) { selected = result.item.id; loadEditor(result.item); message('Your cumulative broker report was saved on this device. No order or protection was placed.'); }
    else {
      if (pending && result.existingId) pending.existingId = result.existingId;
      message(result.error + ' Your unsaved entries remain below.' + (result.existingId ? ' Use Load saved report to discard these entries and open that existing record.' : ''));
    }
    update();
  }
  function revealEditor() {
    host.open = true;
    host.querySelector('[data-handoff-report]').open = true;
    const title = host.querySelector('#handoff-title');
    title.scrollIntoView({ block: 'start' }); title.focus({ preventScroll: true });
  }
  function openResearch(request) {
    const fail = error => ({ ok: false, error });
    if (!host || !api.handoff.inspectResearch) return fail('Private research reporting is unavailable in this page.');
    if (busy) return fail('A private save is in progress. Your current report and its original reference have been kept; wait before reopening a report.');
    const checked = api.handoff.inspectResearch(request);
    if (!checked.ok) return checked;
    if (research && JSON.stringify(research.source) === JSON.stringify(checked.source)) {
      // Only an explicit, verified reopen renews the transient lookup. Its
      // original source and the mounted broker-fact inputs stay untouched.
      research.request = JSON.parse(JSON.stringify(request));
      revealEditor(); return { ok: true };
    }
    if (dirty || busy) return fail('Your current broker report has unsaved entries. Save or explicitly discard them before opening another report; those entries have been kept.');
    const id = checked.source.publication.data_sha256 + ':' + checked.source.evidence.id;
    const existing = api.handoff.find(id);
    if (existing) { choose(id); message('This source already has a private record. Correct its broker facts here; nothing was replaced.'); revealEditor(); return { ok: true }; }
    const previousSelection = research ? research.previousSelection : selected;
    loadEditor(null); selected = null;
    research = { request: JSON.parse(JSON.stringify(request)), source: JSON.parse(JSON.stringify(checked.source)), previousSelection };
    message('Not saved. Enter the positive fill and quantity actually submitted, then save explicitly. All other blank facts remain unknown.');
    update(); revealEditor(); return { ok: true };
  }
  function cancelResearch() {
    if (!research || busy) return;
    const prior = research.previousSelection, item = prior && api.handoff.find(prior);
    selected = item ? item.id : null; loadEditor(item || null);
    message('Unsaved research report discarded. No private record or broker order was created.'); update();
    host.querySelector('summary').focus();
  }
  async function copyDraft() {
    if (!editing) return;
    const result = api.handoff.copy(editing.id);
    if (!result.ok) { message(result.error); update(); return; }
    try { await w.navigator.clipboard.writeText(result.text); message('Personal readback copied. Nothing was submitted; verify every term at your broker.'); }
    catch (error) { message('Clipboard unavailable. The saved readback remains visible below.'); }
    update();
  }
  async function removeSelected() {
    if (busy || !editing || !host.querySelector('[data-handoff-delete-confirm]').checked) return;
    busy = true; update();
    const result = await api.handoff.remove(editing.id, editing.revision);
    busy = false;
    if (result.ok) { selected = null; loadEditor(null); message('Private handoff removed from this device. This did not cancel an order or close a position at your broker.'); }
    else message(result.error + ' Your unsaved entries remain below.');
    update();
  }
  function downloadRecovery() {
    const recovery = api.handoff.recovery();
    const blob = new w.Blob([JSON.stringify(recovery, null, 2)], { type: 'application/json' });
    const url = w.URL.createObjectURL(blob), link = node('a', { href: url, download: 'spicystock-private-handoff-recovery.json' });
    link.click(); w.setTimeout(() => w.URL.revokeObjectURL(url), 1000);
    message('Private recovery copy downloaded to this device. It contains broker facts you entered; keep it private. Nothing was uploaded.');
  }
  function backupMessage(text, state) {
    host.querySelector('[data-handoff-backup-status]').textContent = text;
    host.querySelector('[data-handoff-backup]').setAttribute('data-handoff-backup-state', state);
  }
  function refreshBackup() {
    if (!host) return;
    host.querySelector('[data-handoff-backup-download]').disabled = busy;
    host.querySelector('[data-handoff-backup-file]').disabled = busy;
    host.querySelector('[data-handoff-backup-confirm]').disabled = busy || backupReading || !backupPreview;
    host.querySelector('[data-handoff-backup-cancel]').disabled = busy;
    host.querySelector('[data-handoff-backup-preview]').hidden = !backupPreview;
    host.querySelector('[data-handoff-backup-warning]').textContent = backupPreview && (dirty || research)
      ? 'Your report has unsaved entries. Save or explicitly discard that report before restoring; selecting this file has kept those entries.' : '';
  }
  function clearBackupPreview() {
    backupPreview = null;
    host.querySelector('[data-handoff-backup-facts]').replaceChildren();
    host.querySelector('[data-handoff-backup-records]').replaceChildren();
  }
  function downloadBackup() {
    if (busy) return;
    const result = api.handoff.exportBackup();
    if (!result.ok) { backupMessage(result.error, 'unavailable'); return; }
    const blob = new w.Blob([result.raw], { type: 'application/json' });
    const url = w.URL.createObjectURL(blob), link = node('a', { href: url, download: 'spicystock-private-backup.json' });
    link.click(); w.setTimeout(() => w.URL.revokeObjectURL(url), 1000);
    backupMessage('Private backup downloaded: ' + result.summary.count + ' saved ' + (result.summary.count === 1 ? 'record' : 'records') + '. Unsaved editor changes are excluded. Keep this file private; nothing was uploaded.', 'downloaded');
  }
  function renderBackupPreview(summary) {
    facts(host.querySelector('[data-handoff-backup-facts]'), [
      ['Saved records', summary.count], ['Planned handoffs', summary.planned_count],
      ['Independent execution reports', summary.independent_count], ['Original file version', summary.version]
    ]);
    host.querySelector('[data-handoff-backup-records]').replaceChildren(...summary.records.map(record =>
      node('li', {}, record.ticker + ' · ' + (record.kind === 'independent_research' ? 'independent execution report' : 'planned handoff') +
        ' · original scan ' + record.session + ' · published ' + clock(record.published_at) +
        ' · first saved ' + clock(record.created_at) + ' · last saved ' + clock(record.updated_at))));
  }
  async function selectBackup() {
    if (busy) return;
    const generation = ++backupGeneration, file = host.querySelector('[data-handoff-backup-file]').files[0];
    clearBackupPreview(); backupReading = false;
    if (!file) { backupMessage('No backup selected. Nothing was changed.', 'idle'); refreshBackup(); return; }
    backupReading = true; backupMessage('Reading the selected file on this device… Nothing has been restored.', 'reading'); refreshBackup();
    try {
      if (!Number.isSafeInteger(file.size) || file.size > api.handoff.MAX_BYTES) throw new Error('size');
      const bytes = new Uint8Array(await file.slice(0, api.handoff.MAX_BYTES + 1).arrayBuffer());
      if (generation !== backupGeneration) return;
      if (bytes.byteLength > api.handoff.MAX_BYTES || bytes.byteLength !== file.size) throw new Error('size');
      // Preserve a BOM for the JSON validator to refuse; never trim or repair bytes.
      const raw = new w.TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
      const result = api.handoff.previewBackup(raw);
      if (!result.ok) { backupMessage(result.error, 'unavailable'); return; }
      backupPreview = result.preview; renderBackupPreview(backupPreview.summary);
      backupMessage('Backup validated on this device. Review the original records below, then choose Restore to save them. No records have been written.', 'preview');
    } catch (error) {
      if (generation === backupGeneration) backupMessage('This file could not be read as a private backup within the 1 MiB limit. Use an unchanged UTF-8 backup file; nothing was written.', 'unavailable');
    } finally {
      if (generation === backupGeneration) { backupReading = false; refreshBackup(); }
    }
  }
  function cancelBackup() {
    if (busy) return;
    ++backupGeneration; backupReading = false; clearBackupPreview();
    host.querySelector('[data-handoff-backup-file]').value = '';
    backupMessage('Backup selection cancelled. Saved records and unsaved report entries were kept.', 'idle'); refreshBackup();
    host.querySelector('[data-handoff-backup-file]').focus();
  }
  async function restoreBackup() {
    if (busy || backupReading || !backupPreview) return;
    if (dirty || research) {
      backupMessage('Restore refused: your report has unsaved entries. Save or explicitly discard that report first; your entries were kept.', 'blocked');
      return;
    }
    const preview = backupPreview, confirm = host.querySelector('[data-handoff-backup-confirm]'), hadFocus = d.activeElement === confirm;
    let restored = false;
    busy = true; backupMessage('Restoring the reviewed backup on this device…', 'restoring'); update();
    try {
      const result = await api.handoff.restoreBackup(preview);
      if (!result.ok) { backupMessage(result.error + ' Your report editor was kept. Check the storage notice and any separate recovery copy before retrying.', 'unavailable'); return; }
      restored = true;
      ++backupGeneration; clearBackupPreview(); host.querySelector('[data-handoff-backup-file]').value = '';
      backupMessage('Restored ' + result.summary.count + ' saved ' + (result.summary.count === 1 ? 'record' : 'records') + ' exactly as backed up. Original dates and unknown facts were kept. No broker order or cash reservation was created.', 'restored');
    } catch (error) {
      backupMessage('Restore could not complete. Your saved records and recovery status remain visible; retry only after checking them.', 'unavailable');
    } finally {
      busy = false; update();
      const status = host.querySelector('[data-handoff-backup-status]');
      if (restored && hadFocus && (d.activeElement === d.body || d.activeElement === confirm) && status.getClientRects().length) status.focus({ preventScroll: true });
    }
  }
  function mountBackup(parent) {
    const section = node('details', { class: 'sc-disclosure', 'data-handoff-backup': '', 'data-handoff-backup-state': 'idle' });
    section.append(node('summary', {}, 'Private backup and restore'));
    const body = node('div', { class: 'sc-card__body' });
    const download = button('Download private backup', { 'data-handoff-backup-download': '' }); download.addEventListener('click', downloadBackup);
    body.append(node('p', { class: 'sc-hint' }, 'Keep a local copy of your saved broker records. The file contains private facts you entered; it has no cloud backup and is never uploaded here. Unsaved editor changes are not included.'), download);
    const file = node('input', { id: 'handoff-backup-file', type: 'file', accept: '.json,application/json', class: 'sc-input', 'data-handoff-backup-file': '', 'aria-describedby': 'handoff-backup-help' });
    file.addEventListener('change', selectBackup);
    const field = node('div', { class: 'ss-handoff__field' }); field.append(node('label', { for: file.id }, 'Restore private backup'), file);
    body.append(node('p', { id: 'handoff-backup-help', class: 'sc-hint' }, 'Choose a saved backup up to 1 MiB and 100 records. Restore is available only when this browser’s private store is readable and empty. Existing records are never merged or replaced. Emergency recovery files with prior/proposed copies are separate and cannot be restored here.'), field,
      node('p', { role: 'status', 'aria-live': 'polite', tabindex: '-1', class: 'sc-hint', 'data-handoff-backup-status': '' }, 'Choose a file to preview it. Nothing is saved until you confirm Restore.'));
    const preview = node('section', { hidden: '', 'data-handoff-backup-preview': '', 'aria-label': 'Private backup preview' });
    preview.append(node('dl', { class: 'sc-facts', 'data-handoff-backup-facts': '' }), node('ul', { class: 'ss-notes', 'data-handoff-backup-records': '' }),
      node('p', { class: 'sc-hint', 'data-handoff-backup-warning': '' }));
    const actions = node('div', { class: 'ss-handoff__actions' }), confirm = button('Restore reviewed backup', { 'data-handoff-backup-confirm': '' }), cancel = button('Cancel backup selection', { 'data-handoff-backup-cancel': '' });
    confirm.addEventListener('click', restoreBackup); cancel.addEventListener('click', cancelBackup);
    preview.append(confirm); actions.append(cancel); body.append(preview, actions); section.append(body); parent.append(section);
  }
  function mount(parent) {
    if (!api.handoff) return;
    host = node('details', { class: 'sc-disclosure ss-handoff', id: 'morning-handoffs' });
    host.append(node('summary', {}, 'Private broker handoffs and reports'));
    const body = node('div', { class: 'sc-card__body' });
    body.append(node('p', { class: 'sc-hint' }, 'Saved only in this browser on this device. These are your manual records, separate from published tickets and daily-bar model outcomes. SpicyStock sends no broker orders, observes no executions and reserves no cash.'),
      node('p', { class: 'sc-hint', 'data-handoff-storage': '' }), node('p', { class: 'sc-hint', 'data-handoff-empty': '' }));
    mountBackup(body);
    const select = node('select', { class: 'sc-select', id: 'handoff-select' });
    select.addEventListener('change', () => {
      const id = select.value;
      if (dirty || busy) { select.value = selected; message('Save your correction or use Load saved report to discard it before switching handoffs.'); return; }
      choose(id);
    });
    body.append(node('label', { for: select.id }, 'Saved personal handoff'), select,
      node('p', { role: 'status', 'aria-live': 'polite', 'data-handoff-message': '', class: 'sc-hint' }));
    const panel = node('section', { 'data-handoff-selected': '', 'aria-labelledby': 'handoff-title' });
    const references = node('details', { class: 'sc-disclosure', 'data-handoff-research-references': '' });
    references.append(node('summary', {}, 'Original research references'), node('p', { class: 'sc-hint', 'data-handoff-research-digests': '' }));
    panel.append(node('h3', { id: 'handoff-title', tabindex: '-1' }), node('p', { class: 'sc-hint', 'data-handoff-identity': '' }),
      node('p', { class: 'sc-hint', 'data-handoff-research-source': '' }), references,
      node('dl', { class: 'sc-facts', 'data-handoff-summary': '' }), node('p', { class: 'sc-hint', 'data-handoff-protection': '' }),
      node('ul', { class: 'ss-notes', 'data-handoff-warnings': '' }));
    const exitReview = node('section', { 'data-handoff-exit-section': '' });
    exitReview.append(node('h4', {}, 'Whole-share exit check'), node('p', { class: 'sc-hint', 'data-handoff-exit-review': '' }));
    panel.append(exitReview);
    const completed = node('section', { 'data-handoff-completed': '', 'aria-labelledby': 'handoff-result-title' });
    completed.append(node('h4', { id: 'handoff-result-title' }, 'Reported completed result'),
      node('p', { class: 'sc-hint', 'data-handoff-result-status': '', role: 'status' }),
      node('dl', { class: 'sc-facts', 'data-handoff-result-amounts': '' }),
      node('p', { class: 'sc-hint' }, 'Calculated only from your reported entry, exit and actual fees after all filled shares are exited and the entry remainder is reconciled. Partial exits have no completed result here. Broker records are not verified; published model outcomes stay separate.'));
    panel.append(completed);
    const readback = node('details', { class: 'sc-disclosure', 'data-handoff-readback': '' });
    readback.append(node('summary', {}, 'Saved draft readback and dated exit plan'),
      node('p', { class: 'sc-hint' }, 'Original personal draft, retained as history after broker facts are reported. A planned protective order is not confirmed protection.'),
      node('pre', { class: 'ss-handoff__readback', 'data-handoff-text': '' }),
      node('h4', {}, 'Archived model exit schedule'),
      node('p', { class: 'sc-hint' }, 'Original published dates and wording. This schedule is not resized to your personal draft or reported holdings; review the whole-share exit check and your prior exits before acting.'),
      node('ul', { class: 'ss-notes', 'data-handoff-exits': '' }));
    const copy = button('Copy personal broker readback', { 'data-handoff-copy': '' }); copy.addEventListener('click', copyDraft);
    readback.append(copy, node('p', { class: 'sc-hint', 'data-handoff-copy-status': '' }));
    const report = node('details', { class: 'sc-disclosure', 'data-handoff-report': '' });
    report.append(node('summary', {}, 'Enter or correct broker facts'),
      node('p', { class: 'sc-hint' }, 'Enter cumulative totals from your broker, not an additional fill. Blank means unknown; 0 means you explicitly reported none. Corrections replace the previous report. Entry fills remain history after an exit.'),
      node('p', { class: 'sc-hint' }, 'Dates need an explicit offset, for example 2026-09-11T08:35:00-05:00. Use current time only enters this device’s time; it does not observe a broker event. Saved times below are displayed in Chicago.'));
    groups.forEach(([legend, keys]) => {
      const group = node('fieldset', { class: 'ss-handoff__fields' }); group.append(node('legend', {}, legend));
      if (legend === 'Exits after entry') group.append(node('p', { class: 'sc-hint' }, 'Explicit 0 exits is needed to calculate remaining reported holdings. Leave blank if you have not checked.'));
      if (legend === 'Actual transaction costs') group.append(node('p', { class: 'sc-hint' }, 'Enter actual total fees from your broker for entry and exit separately. Blank is unknown; enter 0 only for confirmed zero fees. The draft fee buffer is an estimate and is never used as an actual cost.'));
      if (legend === 'Protective order at the broker') group.append(node('p', { class: 'sc-hint' }, 'Check active protective sell quantity against remaining holdings after fills or exits. Draft instructions never confirm a live stop.'));
      keys.forEach(key => {
        const time = key.endsWith('_at'), id = 'handoff-' + key;
        const field = node('div', { class: 'ss-handoff__field' });
        const input = node('input', { id, class: 'sc-input', type: 'text', 'data-handoff-field': key, autocomplete: 'off', spellcheck: 'false', placeholder: time ? 'Unknown; include Z or ±HH:MM' : 'Unknown', ...(time ? {} : { inputmode: ['average_price', 'average_exit_price', 'entry_fees', 'exit_fees'].includes(key) ? 'decimal' : 'numeric' }) });
        input.addEventListener('input', () => { dirty = true; refreshEditorStatus(); });
        field.append(node('label', { for: id }, labels[key]), input);
        if (time) {
          const now = button('Use current time', { 'data-handoff-now': key });
          now.addEventListener('click', () => { input.value = new Date().toISOString(); dirty = true; refreshEditorStatus(); input.focus(); });
          field.append(now);
        }
        group.append(field);
      });
      report.append(group);
    });
    const actions = node('div', { class: 'ss-handoff__actions' }), save = button('Save broker report', { 'data-handoff-save': '' }), reload = button('Load saved report', { 'data-handoff-reload': '' }), cancel = button('Cancel unsaved report', { 'data-handoff-cancel': '', hidden: '' });
    save.addEventListener('click', saveReport);
    reload.addEventListener('click', () => { const current = api.handoff.find(selected || research && research.existingId); if (current) { selected = current.id; loadEditor(current); message('Saved report loaded; unsaved corrections discarded.'); update(); } else message('That saved handoff is no longer available. Your unsaved entries remain visible.'); });
    cancel.addEventListener('click', cancelResearch);
    actions.append(save, reload, cancel); report.append(actions, node('p', { class: 'sc-hint', 'data-handoff-editor-status': '' }));
    const remove = node('details', { class: 'sc-disclosure', 'data-handoff-remove-section': '' }); remove.append(node('summary', {}, 'Remove this private handoff'));
    const consent = node('label', { class: 'sc-check' }); consent.append(node('input', { type: 'checkbox', 'data-handoff-delete-confirm': '' }), node('span', {}, 'Delete this draft and its reported broker facts from this device. This does not cancel broker orders, remove protective orders or close positions.'));
    consent.querySelector('input').addEventListener('change', refreshEditorStatus);
    const removeButton = button('Delete private handoff', { 'data-handoff-delete': '' }); removeButton.addEventListener('click', removeSelected);
    remove.append(consent, removeButton);
    panel.append(readback, report, remove); body.append(panel);
    const recover = button('Download private recovery copy', { 'data-handoff-recovery': '' }); recover.addEventListener('click', downloadRecovery);
    body.append(recover); host.append(body); parent.append(host); update();
  }
  function refreshEditorStatus() {
    if (!host) return;
    refreshBackup();
    const current = api.handoff.find(selected || research && research.existingId), status = api.handoff.status(), conflict = editing && (!current || current.revision !== editing.revision);
    host.querySelector('[data-handoff-editor-status]').textContent = busy ? 'Saving on this device…' : conflict ? 'The saved handoff changed in another view. Your edits were kept. Load its saved report before making a new correction.' : research
      ? 'Unsaved independent trade report. Saving requires a positive actual fill and the corresponding submitted quantity. Blank costs, prices, times and exits remain unknown; research values are never filled in for you.'
      : dirty ? 'Unsaved correction — changes are not yet in your private record.' : 'Blank fields remain unknown. Reports stay editable after the entry window or an event restriction.';
    host.querySelector('[data-handoff-save]').disabled = busy || !editing && !research || !status.available;
    host.querySelector('[data-handoff-reload]').disabled = busy || !current;
    host.querySelector('[data-handoff-delete]').disabled = busy || !current || !status.available || !host.querySelector('[data-handoff-delete-confirm]').checked;
    host.querySelector('[data-handoff-cancel]').hidden = !research;
    host.querySelector('[data-handoff-cancel]').disabled = busy;
    host.querySelectorAll('[data-handoff-field], [data-handoff-now]').forEach(input => { input.disabled = busy; });
  }
  function renderResearchIdentity(source) {
    host.querySelector('[data-handoff-research-source]').textContent = 'Independent execution report only. Original production baseline: ' +
      (source.baseline_admitted ? 'admitted' : 'not admitted') + '. Recording broker facts grants no entry permission. ' +
      'Research captured ' + clock(source.cohort.generated_at) + '.';
    host.querySelector('[data-handoff-research-digests]').textContent = 'Research policy ' + source.cohort.policy_id + ' · cohort SHA-256 ' + source.cohort.sha256 +
      ' · publication SHA-256 ' + source.publication.data_sha256 + ' · original evidence ' + source.evidence.id + '.';
  }
  function update() {
    if (!host || !api.handoff) return;
    const items = api.handoff.list(), status = api.handoff.status(), select = host.querySelector('#handoff-select');
    host.querySelector('[data-handoff-storage]').textContent = status.error || 'Saved on this device only; clearing this site’s browser data removes these private records. There is no cloud backup.';
    host.querySelector('[data-handoff-empty]').textContent = !items.length ? status.error ? 'Saved records could not be read; this is not a claim that you hold no position.' : 'No personal handoff or trade report saved. Use a calculated cash preview for a draft, or a verified research row to record an already executed trade. No submitted order or holdings are inferred.' : '';
    const signature = JSON.stringify(items.map(item => [item.id, ticker(item), independent(item) ? 'independent' : item.draft.quantity, session(item)]));
    if (select.dataset.choices !== signature) {
      select.replaceChildren(...items.map(item => node('option', { value: item.id }, ticker(item) + ' · ' + (independent(item) ? 'independent execution report' : item.draft.quantity + ' planned') + ' · scan ' + session(item))));
      select.dataset.choices = signature;
    }
    host.querySelector('[data-handoff-recovery]').hidden = !status.error && !api.handoff.recovery().proposed;
    refreshBackup();
    host.querySelector('[data-handoff-selected]').hidden = !editing && !research;
    host.setAttribute('data-handoff-mode', research ? 'independent-unsaved' : editing && independent(editing) ? 'independent_research' : 'planned_handoff');
    host.querySelector('[data-handoff-readback]').hidden = !!research || independent(editing);
    host.querySelector('[data-handoff-remove-section]').hidden = !!research;
    host.querySelector('[data-handoff-research-source]').hidden = !research && !independent(editing);
    host.querySelector('[data-handoff-research-references]').hidden = !research && !independent(editing);
    for (const selector of ['[data-handoff-summary]', '[data-handoff-protection]', '[data-handoff-warnings]', '[data-handoff-exit-section]', '[data-handoff-completed]']) host.querySelector(selector).hidden = !!research;
    if (research) {
      select.value = ''; select.disabled = true;
      host.querySelector('#handoff-title').textContent = research.source.ticker + ' · unsaved independent trade report';
      host.querySelector('[data-handoff-identity]').textContent = 'Original scan ' + research.source.publication.measured_session + ' · applicable ' + research.source.publication.applicable_session + ' · published ' + clock(research.source.publication.published_at) + '. No private record has been saved.';
      renderResearchIdentity(research.source);
      host.querySelector('[data-handoff-completed]').setAttribute('data-result-state', 'incomplete');
      host.querySelector('[data-handoff-completed]').setAttribute('data-result-outcome', 'unknown');
      host.querySelector('[data-handoff-copy]').disabled = true;
      host.querySelector('[data-handoff-text]').textContent = '';
      host.querySelector('[data-handoff-exits]').replaceChildren();
      refreshEditorStatus(); return;
    }
    if (!selected && items.length) { selected = items[items.length - 1].id; loadEditor(selectedItem(items)); }
    const current = selectedItem(items);
    if (current && (!editing || !dirty && !busy && current.revision !== editing.revision)) loadEditor(current);
    if (!current && !dirty && !busy && editing && status.available) { selected = items.length ? items[items.length - 1].id : null; loadEditor(selectedItem(items)); }
    select.value = selected || ''; select.disabled = !items.length || busy;
    host.querySelector('[data-handoff-selected]').hidden = !editing;
    if (!editing) return;
    const item = current || editing, summary = api.handoff.summary(item);
    const reportOnly = independent(item), pub = publication(item);
    host.setAttribute('data-handoff-mode', reportOnly ? 'independent_research' : 'planned_handoff');
    host.querySelector('[data-handoff-readback]').hidden = reportOnly;
    host.querySelector('[data-handoff-research-source]').hidden = !reportOnly;
    host.querySelector('[data-handoff-research-references]').hidden = !reportOnly;
    host.querySelector('#handoff-title').textContent = ticker(item) + (reportOnly ? ' · independent execution report' : ' · personal broker record');
    host.querySelector('[data-handoff-identity]').textContent = 'Scan ' + session(item) + ' · published ' + clock(pub.published_at) + ' · rules ' + pub.rules_version + ' · saved revision ' + item.revision + '. ' + (reportOnly ? 'Original research evidence is retained; this is your execution report, not a production ticket or model fill.' : 'Original published terms are kept separately from your broker reports.');
    if (reportOnly) renderResearchIdentity(item.source);
    facts(host.querySelector('[data-handoff-summary]'), [...(reportOnly ? [] : [
      ['Personal draft / published shares', item.draft.quantity + ' / ' + item.plan.order.quantity],
      ['Draft cash at limit including buffer', money(summary.calculation.commitmentCents)], ['Draft price-to-stop risk', money(summary.calculation.riskCents) + ' before fees, gaps and slippage'],
      ['Draft fee buffer (estimate)', money(item.draft.fee_cents)]]),
      ['Reported submitted', amount(item.report.submitted_quantity)], ['Cumulative entry filled', amount(item.report.filled_quantity)],
      ['Reported exited', amount(item.report.exited_quantity)], ['Remaining reported holdings', amount(summary.reported_held_quantity)],
      ['Entry shares not filled', amount(summary.unfilled_quantity)], ['Unfilled shares cancelled', amount(item.report.cancelled_quantity)],
      ['Entry remainder not reported cancelled', amount(summary.uncancelled_quantity)], ['Reported average entry fill', item.report.average_price === null ? 'Unknown' : '$' + item.report.average_price],
      ['Reported average exit fill', item.report.average_exit_price == null ? 'Unknown' : '$' + item.report.average_exit_price],
      ['Protective shares reported', amount(item.report.protected_quantity)], ['Protection checked by you', clock(item.report.protection_confirmed_at)],
      ['Submission / latest entry fill', clock(item.report.submitted_at) + ' / ' + clock(item.report.filled_at)],
      ['Cancellation / latest exit', clock(item.report.cancelled_at) + ' / ' + clock(item.report.exited_at)],
      ['Report saved on this device', clock(item.report_updated_at)]
    ]);
    const result = summary.completed_result, complete = result && result.state === 'complete';
    host.querySelector('[data-handoff-completed]').setAttribute('data-result-state', complete ? 'complete' : 'incomplete');
    host.querySelector('[data-handoff-completed]').setAttribute('data-result-outcome', complete ? result.outcome : 'unknown');
    const outcomes = { gain: 'User-reported net gain', loss: 'User-reported net loss', breakeven: 'User-reported break-even' };
    host.querySelector('[data-handoff-result-status]').textContent = complete
      ? outcomes[result.outcome] + ' · ' + result.quantity + ' reported ' + (result.quantity === 1 ? 'share' : 'shares') + ' fully exited. Amounts are rounded for display; gain or loss uses the exact reported values.'
      : 'Completed result unavailable. ' + (result ? result.reasons.join(' ') : 'Entry, exit and actual costs are not yet available.');
    facts(host.querySelector('[data-handoff-result-amounts]'), complete ? [
      ['Reported gross result', result.gross_display],
      ['Reported actual costs', result.fees_display + ' (entry $' + item.report.entry_fees + ' + exit $' + item.report.exit_fees + ')'],
      ['Reported net result', result.net_display]
    ] : []);
    const protection = { unknown: 'Protection is unknown. Check your remaining holdings and active protective orders at your broker.', matched: 'Reported protective quantity matches reported remaining holdings. SpicyStock does not verify an active stop.', under: 'Reported protective quantity is below remaining reported holdings. Reconcile protection at your broker.', over: 'Reported protective quantity exceeds remaining reported holdings. Reconcile the sell quantity at your broker.' };
    host.querySelector('[data-handoff-protection]').textContent = protection[summary.protection] || 'Protection needs reconciliation at your broker.';
    host.querySelector('[data-handoff-warnings]').replaceChildren(...summary.warnings.map(text => node('li', {}, text)));
    host.querySelector('[data-handoff-exit-review]').textContent = summary.exit_review.message;
    host.querySelector('[data-handoff-text]').textContent = api.handoff.readback(item);
    host.querySelector('[data-handoff-exits]').replaceChildren(...(reportOnly ? [] : item.plan.exit_schedule.map(row => node('li', {}, row.date + ' · ' + row.instruction))));
    const available = current ? api.handoff.availability(current) : { ok: false, error: 'This handoff is no longer available in saved storage.' };
    host.querySelector('[data-handoff-copy]').disabled = !available.ok;
    host.querySelector('[data-handoff-copy-status]').textContent = available.ok ? 'Copying only places text on your clipboard. Check cash, live quote, activation and protection at your broker.' : available.error;
    refreshEditorStatus();
  }
  function preview(parent, intent) {
    if (!api.handoff) return;
    let section = parent.querySelector('[data-handoff-prepare-section]');
    if (!section) {
      section = node('div', { 'data-handoff-prepare-section': '' });
      const prepare = button('Prepare private broker draft', { 'data-handoff-prepare': '' });
      prepare.addEventListener('click', async () => {
        const input = prepare._intent;
        if (!input || prepare._busy) return;
        if (dirty || busy || research) {
          section.querySelector('[data-handoff-prepare-status]').textContent = 'Save your current broker report or use Load saved report to discard its edits before preparing a draft.';
          return;
        }
        const priorSelection = selected;
        prepare._busy = true; prepare.disabled = true;
        const result = await api.handoff.prepare(input);
        prepare._busy = false;
        section.querySelector('[data-handoff-prepare-status]').textContent = result.ok ? 'Private draft saved. It creates no broker order or confirmed protective stop.' : result.error;
        if (result.ok && host) {
          if (!dirty && !busy && (selected === priorSelection || selected === result.item.id)) { choose(result.item.id); host.open = true; host.querySelector('#handoff-title').focus(); }
          else message('Private draft saved. Your current report and unsaved entries were kept; save or discard them before choosing another handoff.');
        }
        if (api.morning.refreshPersonal) api.morning.refreshPersonal();
      });
      section.append(prepare, node('p', { class: 'sc-hint', 'data-handoff-prepare-status': '', role: 'status' }),
        node('p', { class: 'sc-hint' }, 'Preparing explicitly saves this preview, including entered cash and fees, as a private draft on this device. It reserves no cash, places no order and does not confirm a protective stop.'));
      parent.append(section);
    }
    const prepare = section.querySelector('[data-handoff-prepare]'), status = api.handoff.status();
    const previous = intent && api.handoff.list().find(item => independent(item)
      ? item.source.publication.data_sha256 === intent.expectedPublication && item.source.evidence.id === intent.referenceId
      : item.publication.sha256 === intent.expectedPublication && item.plan.reference.id === intent.referenceId);
    const hasReport = previous && previous.report_updated_at !== null;
    prepare._intent = intent ? { key: intent.key, cash: intent.cash, fees: intent.fees, quantity: intent.quantity, expectedPublication: intent.expectedPublication, expectedRevision: previous ? previous.revision : null } : null;
    prepare.disabled = !!prepare._busy || !intent || !status.available || !!hasReport;
    prepare.textContent = previous ? hasReport ? 'Broker report already saved' : 'Replace private broker draft' : 'Prepare private broker draft';
    if (hasReport) section.querySelector('[data-handoff-prepare-status]').textContent = 'This exact plan already has a broker report. Open Private broker handoffs to correct it; preparing cannot overwrite it.';
  }
  api.handoffUI = { mount, update, preview, openResearch };
})(window);
