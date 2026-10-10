/* Private, explicitly entered broker facts. The model owns storage, arithmetic
   and permission checks; rendering never interprets a click as execution. */
(function (w) {
  'use strict';
  const api = w.SCStock = w.SCStock || {}, d = w.document;
  const labels = {
    submitted_quantity: 'Total shares submitted', submitted_at: 'Submission time',
    filled_quantity: 'Cumulative entry shares filled', average_price: 'Average entry fill price ($)', filled_at: 'Latest entry fill time',
    cancelled_quantity: 'Unfilled entry shares cancelled', cancelled_at: 'Remainder cancellation time',
    exited_quantity: 'Cumulative filled shares sold / exited', exited_at: 'Latest exit time',
    protected_quantity: 'Current broker-confirmed protective shares', protection_confirmed_at: 'Protection checked by you at'
  };
  const groups = [
    ['Entry submission', ['submitted_quantity', 'submitted_at']],
    ['Entry fills', ['filled_quantity', 'average_price', 'filled_at']],
    ['Unfilled entry cancellation', ['cancelled_quantity', 'cancelled_at']],
    ['Exits after entry', ['exited_quantity', 'exited_at']],
    ['Protective order at the broker', ['protected_quantity', 'protection_confirmed_at']]
  ];
  const money = value => '$' + (BigInt(value) / 100n).toLocaleString('en-US') + '.' + String(BigInt(value) % 100n).padStart(2, '0');
  const clock = value => value ? new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', dateStyle: 'medium', timeStyle: 'long' }).format(new Date(value)) : 'Not reported';
  const amount = value => value === null || value === undefined ? 'Unknown' : String(value);
  let host = null, selected = null, editing = null, dirty = false, busy = false;
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
    editing = item; dirty = false;
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
    if (busy || !editing) return;
    const id = editing.id, revision = editing.revision;
    const fields = Object.fromEntries(api.handoff.FIELDS.map(key => [key, host.querySelector('[data-handoff-field="' + key + '"]').value]));
    busy = true; update();
    const result = await api.handoff.report(id, fields, revision);
    busy = false;
    if (result.ok) { selected = result.item.id; loadEditor(result.item); message('Your cumulative broker report was saved on this device. No order or protection was placed.'); }
    else message(result.error + ' Your unsaved entries remain below.');
    update();
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
  function mount(parent) {
    if (!api.handoff) return;
    host = node('details', { class: 'sc-disclosure ss-handoff', id: 'morning-handoffs' });
    host.append(node('summary', {}, 'Private broker handoffs'));
    const body = node('div', { class: 'sc-card__body' });
    body.append(node('p', { class: 'sc-hint' }, 'Saved only in this browser on this device. These are your manual records, separate from published tickets and daily-bar model outcomes. SpicyStock sends no broker orders, observes no executions and reserves no cash.'),
      node('p', { class: 'sc-hint', 'data-handoff-storage': '' }), node('p', { class: 'sc-hint', 'data-handoff-empty': '' }));
    const select = node('select', { class: 'sc-select', id: 'handoff-select' });
    select.addEventListener('change', () => {
      const id = select.value;
      if (dirty || busy) { select.value = selected; message('Save your correction or use Load saved report to discard it before switching handoffs.'); return; }
      choose(id);
    });
    body.append(node('label', { for: select.id }, 'Saved personal handoff'), select,
      node('p', { role: 'status', 'aria-live': 'polite', 'data-handoff-message': '', class: 'sc-hint' }));
    const panel = node('section', { 'data-handoff-selected': '', 'aria-labelledby': 'handoff-title' });
    panel.append(node('h3', { id: 'handoff-title', tabindex: '-1' }), node('p', { class: 'sc-hint', 'data-handoff-identity': '' }),
      node('dl', { class: 'sc-facts', 'data-handoff-summary': '' }), node('p', { class: 'sc-hint', 'data-handoff-protection': '' }),
      node('ul', { class: 'ss-notes', 'data-handoff-warnings': '' }));
    const readback = node('details', { class: 'sc-disclosure', 'data-handoff-readback': '' });
    readback.append(node('summary', {}, 'Saved draft readback and dated exit plan'),
      node('p', { class: 'sc-hint' }, 'Original personal draft, retained as history after broker facts are reported. A planned protective order is not confirmed protection.'),
      node('pre', { class: 'ss-handoff__readback', 'data-handoff-text': '' }), node('ul', { class: 'ss-notes', 'data-handoff-exits': '' }));
    const copy = button('Copy personal broker readback', { 'data-handoff-copy': '' }); copy.addEventListener('click', copyDraft);
    readback.append(copy, node('p', { class: 'sc-hint', 'data-handoff-copy-status': '' }));
    const report = node('details', { class: 'sc-disclosure', 'data-handoff-report': '' });
    report.append(node('summary', {}, 'Enter or correct broker facts'),
      node('p', { class: 'sc-hint' }, 'Enter cumulative totals from your broker, not an additional fill. Blank means unknown; 0 means you explicitly reported none. Corrections replace the previous report. Entry fills remain history after an exit.'),
      node('p', { class: 'sc-hint' }, 'Dates need an explicit offset, for example 2026-09-11T08:35:00-05:00. Use current time only enters this device’s time; it does not observe a broker event. Saved times below are displayed in Chicago.'));
    groups.forEach(([legend, keys]) => {
      const group = node('fieldset', { class: 'ss-handoff__fields' }); group.append(node('legend', {}, legend));
      if (legend === 'Exits after entry') group.append(node('p', { class: 'sc-hint' }, 'Explicit 0 exits is needed to calculate remaining reported holdings. Leave blank if you have not checked.'));
      if (legend === 'Protective order at the broker') group.append(node('p', { class: 'sc-hint' }, 'Check active protective sell quantity against remaining holdings after fills or exits. Draft instructions never confirm a live stop.'));
      keys.forEach(key => {
        const time = key.endsWith('_at'), id = 'handoff-' + key;
        const field = node('div', { class: 'ss-handoff__field' });
        const input = node('input', { id, class: 'sc-input', type: 'text', 'data-handoff-field': key, autocomplete: 'off', spellcheck: 'false', placeholder: time ? 'Unknown; include Z or ±HH:MM' : 'Unknown', ...(time ? {} : { inputmode: key === 'average_price' ? 'decimal' : 'numeric' }) });
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
    const actions = node('div', { class: 'ss-handoff__actions' }), save = button('Save broker report', { 'data-handoff-save': '' }), reload = button('Load saved report', { 'data-handoff-reload': '' });
    save.addEventListener('click', saveReport);
    reload.addEventListener('click', () => { const current = api.handoff.find(selected); if (current) { loadEditor(current); message('Saved report loaded; unsaved corrections discarded.'); update(); } else message('That saved handoff is no longer available. Your unsaved entries remain visible.'); });
    actions.append(save, reload); report.append(actions, node('p', { class: 'sc-hint', 'data-handoff-editor-status': '' }));
    const remove = node('details', { class: 'sc-disclosure' }); remove.append(node('summary', {}, 'Remove this private handoff'));
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
    const current = api.handoff.find(selected), status = api.handoff.status(), conflict = editing && (!current || current.revision !== editing.revision);
    host.querySelector('[data-handoff-editor-status]').textContent = busy ? 'Saving on this device…' : conflict ? 'The saved handoff changed in another view. Your edits were kept. Load its saved report before making a new correction.' : dirty ? 'Unsaved correction — changes are not yet in your private record.' : 'Blank fields remain unknown. Reports stay editable after the entry window or an event restriction.';
    host.querySelector('[data-handoff-save]').disabled = busy || !editing || !status.available;
    host.querySelector('[data-handoff-reload]').disabled = busy || !current;
    host.querySelector('[data-handoff-delete]').disabled = busy || !current || !status.available || !host.querySelector('[data-handoff-delete-confirm]').checked;
    host.querySelectorAll('[data-handoff-field], [data-handoff-now]').forEach(input => { input.disabled = busy; });
  }
  function update() {
    if (!host || !api.handoff) return;
    const items = api.handoff.list(), status = api.handoff.status(), select = host.querySelector('#handoff-select');
    host.querySelector('[data-handoff-storage]').textContent = status.error || 'Saved on this device only; clearing this site’s browser data removes these private records. There is no cloud backup.';
    host.querySelector('[data-handoff-empty]').textContent = !items.length ? status.error ? 'Saved records could not be read; this is not a claim that you hold no position.' : 'No personal handoff saved. Use a calculated cash preview to prepare one; no submitted order or holdings are inferred.' : '';
    const signature = JSON.stringify(items.map(item => [item.id, item.plan.ticker, item.draft.quantity, item.publication.session]));
    if (select.dataset.choices !== signature) {
      select.replaceChildren(...items.map(item => node('option', { value: item.id }, item.plan.ticker + ' · ' + item.draft.quantity + ' planned · scan ' + item.publication.session)));
      select.dataset.choices = signature;
    }
    if (!selected && items.length) { selected = items[items.length - 1].id; loadEditor(selectedItem(items)); }
    const current = selectedItem(items);
    if (current && (!editing || !dirty && !busy && current.revision !== editing.revision)) loadEditor(current);
    if (!current && !dirty && !busy && editing && status.available) { selected = items.length ? items[items.length - 1].id : null; loadEditor(selectedItem(items)); }
    select.value = selected || ''; select.disabled = !items.length || busy;
    host.querySelector('[data-handoff-selected]').hidden = !editing;
    host.querySelector('[data-handoff-recovery]').hidden = !status.error && !api.handoff.recovery().proposed;
    if (!editing) return;
    const item = current || editing, summary = api.handoff.summary(item);
    host.querySelector('#handoff-title').textContent = item.plan.ticker + ' · personal broker record';
    host.querySelector('[data-handoff-identity]').textContent = 'Scan ' + item.publication.session + ' · published ' + clock(item.publication.published_at) + ' · rules ' + item.publication.rules_version + ' · saved revision ' + item.revision + '. Original published terms are kept separately from your broker reports.';
    facts(host.querySelector('[data-handoff-summary]'), [
      ['Personal draft / published shares', item.draft.quantity + ' / ' + item.plan.order.quantity],
      ['Draft cash at limit including buffer', money(summary.calculation.commitmentCents)], ['Draft price-to-stop risk', money(summary.calculation.riskCents) + ' before fees, gaps and slippage'],
      ['Reported submitted', amount(item.report.submitted_quantity)], ['Cumulative entry filled', amount(item.report.filled_quantity)],
      ['Reported exited', amount(item.report.exited_quantity)], ['Remaining reported holdings', amount(summary.reported_held_quantity)],
      ['Entry shares not filled', amount(summary.unfilled_quantity)], ['Unfilled shares cancelled', amount(item.report.cancelled_quantity)],
      ['Entry remainder not reported cancelled', amount(summary.uncancelled_quantity)], ['Reported average entry fill', item.report.average_price === null ? 'Unknown' : '$' + item.report.average_price],
      ['Protective shares reported', amount(item.report.protected_quantity)], ['Protection checked by you', clock(item.report.protection_confirmed_at)],
      ['Submission / latest entry fill', clock(item.report.submitted_at) + ' / ' + clock(item.report.filled_at)],
      ['Cancellation / latest exit', clock(item.report.cancelled_at) + ' / ' + clock(item.report.exited_at)],
      ['Report saved on this device', clock(item.report_updated_at)]
    ]);
    const protection = { unknown: 'Protection is unknown. Check your remaining holdings and active protective orders at your broker.', matched: 'Reported protective quantity matches reported remaining holdings. SpicyStock does not verify an active stop.', under: 'Reported protective quantity is below remaining reported holdings. Reconcile protection at your broker.', over: 'Reported protective quantity exceeds remaining reported holdings. Reconcile the sell quantity at your broker.' };
    host.querySelector('[data-handoff-protection]').textContent = protection[summary.protection] || 'Protection needs reconciliation at your broker.';
    host.querySelector('[data-handoff-warnings]').replaceChildren(...summary.warnings.map(text => node('li', {}, text)));
    host.querySelector('[data-handoff-text]').textContent = api.handoff.readback(item);
    host.querySelector('[data-handoff-exits]').replaceChildren(...item.plan.exit_schedule.map(row => node('li', {}, row.date + ' · ' + row.instruction)));
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
        if (dirty || busy) {
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
    const previous = intent && api.handoff.list().find(item => item.publication.sha256 === intent.expectedPublication && item.plan.reference.id === intent.referenceId);
    const hasReport = previous && previous.report_updated_at !== null;
    prepare._intent = intent ? { key: intent.key, cash: intent.cash, fees: intent.fees, quantity: intent.quantity, expectedPublication: intent.expectedPublication, expectedRevision: previous ? previous.revision : null } : null;
    prepare.disabled = !!prepare._busy || !intent || !status.available || !!hasReport;
    prepare.textContent = previous ? hasReport ? 'Broker report already saved' : 'Replace private broker draft' : 'Prepare private broker draft';
    if (hasReport) section.querySelector('[data-handoff-prepare-status]').textContent = 'This exact plan already has a broker report. Open Private broker handoffs to correct it; preparing cannot overwrite it.';
  }
  api.handoffUI = { mount, update, preview };
})(window);
