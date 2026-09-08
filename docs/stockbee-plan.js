/* User-entered long-only plans and a browser-local trade journal. No orders. */
(function () {
  'use strict';
  var KEY = 'spicystock.trade-journal.v1', LIMIT = 100, NOTE_LIMIT = 4000;
  var records = [], storageOK = true, storageReason = '', lastStored = null;
  var host, planPanel, journalPanel, resultNode, notice, storageNode, journalList;
  var inputs = {}, journalInputs = {}, tabs = [], activeTab = 'plan', editingId = null;
  var reference = null, referenceNode, recordedDates = [];
  var RISK_SOURCE = 'https://stockbee.blogspot.com/2014/08/how-i-control-my-risk.html';
  var PROCESS_SOURCE = 'https://stockbee.blogspot.com/2017/07/my-process-loop-to-trade-4-bo-and-bo.html';

  function number(value) {
    if (typeof value !== 'number' && typeof value !== 'string') return NaN;
    if (typeof value === 'string' && !value.trim()) return NaN;
    return Number(value);
  }
  function finite(value) { return typeof value === 'number' && isFinite(value); }
  function ticker(value) {
    var text = typeof value === 'string' ? value.trim().toUpperCase() : '';
    return /^[A-Z][A-Z0-9.-]{0,14}$/.test(text) ? text : null;
  }
  function date(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    var time = new Date(value + 'T12:00:00Z');
    return isFinite(time.getTime()) && time.toISOString().slice(0, 10) === value;
  }
  function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
  function calculate(values) {
    values = values || {};
    var capital = number(values.capital), riskPercent = number(values.riskPercent);
    var entry = number(values.entry), stop = number(values.stop);
    var cap = values.cashCap === '' || values.cashCap === undefined || values.cashCap === null ? capital : number(values.cashCap);
    if (![capital, riskPercent, entry, stop, cap].every(finite)) return { valid: false, error: 'Enter capital, risk %, entry and stop as numbers.' };
    if (capital <= 0 || entry <= 0 || stop <= 0) return { valid: false, error: 'Capital, entry and stop must be greater than zero.' };
    if (riskPercent < 0 || riskPercent > 100) return { valid: false, error: 'Risk must be between 0% and 100% of capital.' };
    if (stop >= entry) return { valid: false, error: 'For a long position, the initial stop must be below the entry.' };
    if (cap < 0 || cap > capital) return { valid: false, error: 'The cash cap must be between zero and your capital. This planner does not use margin.' };
    var perShare = entry - stop, riskBudget = capital * (riskPercent / 100);
    var riskShares = Math.floor(riskBudget / perShare), cashShares = Math.floor(cap / entry);
    var shares = Math.min(riskShares, cashShares);
    var riskDollars = shares * perShare, positionDollars = shares * entry;
    var oneR = entry + perShare, twoR = entry + perShare * 2;
    if (![perShare, riskBudget, riskShares, cashShares, riskDollars, positionDollars, oneR, twoR].every(finite) ||
        !Number.isSafeInteger(shares) || shares < 0) return { valid: false, error: 'These values exceed the calculator’s numeric range. Use smaller amounts.' };
    return { valid: true, shares: shares, riskShares: riskShares, cashShares: cashShares,
      riskBudget: riskBudget, riskDollars: riskDollars, positionDollars: positionDollars,
      perShare: perShare, stopDistancePercent: perShare / entry * 100,
      concentrationPercent: positionDollars / capital * 100, oneR: oneR, twoR: twoR,
      limitedBy: cashShares < riskShares ? 'cash' : 'risk' };
  }
  function outcome(record) {
    if (!record || record.status !== 'closed') return null;
    var initialRisk = (record.entry - record.stop) * record.shares;
    var profit = (record.exit - record.entry) * record.shares;
    return { profit: profit, initialRisk: initialRisk, r: profit / initialRisk };
  }
  function validateRecord(r) {
    return object(r) && typeof r.id === 'string' && /^[a-zA-Z0-9-]{1,80}$/.test(r.id) &&
      ticker(r.ticker) === r.ticker && ['paper', 'open', 'closed'].indexOf(r.status) >= 0 && date(r.date) &&
      finite(r.entry) && r.entry > 0 && finite(r.stop) && r.stop > 0 && r.stop < r.entry &&
      Number.isSafeInteger(r.shares) && r.shares > 0 && finite(r.entry * r.shares) &&
      typeof r.note === 'string' && r.note.length <= NOTE_LIMIT &&
      typeof r.marketNote === 'string' && r.marketNote.length <= NOTE_LIMIT &&
      (r.status === 'closed' ? finite(r.exit) && r.exit >= 0 && date(r.exitDate) && r.exitDate >= r.date &&
        finite((r.exit - r.entry) * r.shares) && finite((r.exit - r.entry) / (r.entry - r.stop)) : r.exit === null && r.exitDate === null);
  }
  function decode(raw) {
    if (raw === null) return [];
    if (typeof raw !== 'string' || raw.length > 1000000) throw new Error('Invalid journal');
    var data = JSON.parse(raw), ids = new Set();
    if (!object(data) || data.version !== 1 || !Array.isArray(data.records) || data.records.length > LIMIT) throw new Error('Invalid journal');
    data.records.forEach(function (r) {
      if (!validateRecord(r) || ids.has(r.id)) throw new Error('Invalid record');
      ids.add(r.id);
    });
    return data.records;
  }
  try { lastStored = window.localStorage.getItem(KEY); records = decode(lastStored); }
  catch (_) { storageOK = false; storageReason = 'Saved journal could not be read, or browser storage is blocked. Its stored copy will not be overwritten.'; }
  function persist() {
    if (storageOK) {
      try {
        if (window.localStorage.getItem(KEY) !== lastStored) throw new Error('Journal changed in another tab');
        var raw = JSON.stringify({ version: 1, records: records });
        window.localStorage.setItem(KEY, raw); lastStored = raw;
      } catch (_) { storageOK = false; storageReason = 'Storage is full, unavailable, or changed in another tab. This visit’s edits are in memory; the stored copy is preserved.'; }
    }
    storageMessage();
  }
  function node(tag, attrs, children) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      if (key === 'text') n.textContent = attrs[key]; else n.setAttribute(key, attrs[key]);
    });
    (children || []).forEach(function (child) { if (child) n.appendChild(child); });
    return n;
  }
  function button(label, id, fn, extra) {
    var b = node('button', Object.assign({ type: 'button', 'class': 'bee-plan-button', text: label }, id ? { id: id } : {}, extra || {}));
    b.addEventListener('click', fn); return b;
  }
  function paragraph(text, css) { return node('p', { 'class': css || 'bee-plan-copy', text: text }); }
  function field(label, id, attrs, map, key) {
    var control = node(attrs && attrs.type === 'textarea' ? 'textarea' : 'input', Object.assign({ id: id, name: key }, attrs || {}));
    if (attrs && attrs.type === 'textarea') control.removeAttribute('type');
    map[key] = control;
    return node('div', { 'class': 'bee-plan-field' }, [node('label', { for: id, text: label }), control]);
  }
  function dollars(value) { return finite(value) ? '$' + value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : 'Not available'; }
  function sourceLink(url, title) { return node('a', { href: url, target: '_blank', rel: 'noopener noreferrer', text: title }); }
  function announce(text) { if (notice) notice.textContent = text; }
  function storageMessage() {
    if (!storageNode) return;
    storageNode.textContent = storageOK ? 'Saved on this browser only. Up to 100 records; this journal is separate from your saved research notes. Export a copy to keep a backup.' : 'Only this visit. ' + storageReason + ' Export a copy before leaving.';
    storageNode.classList.toggle('is-temporary', !storageOK);
  }
  function selectTab(name, focus) {
    activeTab = name;
    planPanel.hidden = name !== 'plan'; journalPanel.hidden = name !== 'journal';
    tabs.forEach(function (b) { var selected = b.dataset.planTab === name; b.setAttribute('aria-selected', String(selected)); b.tabIndex = selected ? 0 : -1; if (selected && focus) b.focus(); });
  }
  function values(map) {
    var result = {}; Object.keys(map).forEach(function (key) { result[key] = map[key].value; }); return result;
  }
  function updateCalculation() {
    var result = calculate(values(inputs)); resultNode.replaceChildren();
    if (!result.valid) { resultNode.appendChild(paragraph(result.error)); return result; }
    resultNode.appendChild(node('p', { 'class': 'bee-plan-share-count', id: 'bee-plan-shares', text: result.shares.toLocaleString('en-US') + ' shares' }));
    resultNode.appendChild(paragraph(result.shares ? 'Within your ' + (result.limitedBy === 'cash' ? 'cash cap' : 'risk budget') + ', rounded down to whole shares.' : 'Your limits do not allow a whole share.', 'bee-plan-result-caption'));
    var dl = node('dl', { 'class': 'bee-plan-metrics' });
    [['Planned loss at stop', dollars(result.riskDollars)], ['Position cost', dollars(result.positionDollars)],
      ['Risk budget', dollars(result.riskBudget)], ['Stop distance', result.stopDistancePercent.toFixed(2) + '%'],
      ['Capital in position', result.concentrationPercent.toFixed(2) + '%'], ['Risk per share', dollars(result.perShare)],
      ['+1R price', dollars(result.oneR)], ['+2R price', dollars(result.twoR)]].forEach(function (pair) {
      dl.appendChild(node('div', {}, [node('dt', { text: pair[0] }), node('dd', { text: pair[1] })]));
    });
    resultNode.appendChild(dl);
    resultNode.appendChild(paragraph('+1R and +2R are distance landmarks, not predicted returns or exit targets. Fees are excluded; gaps and slippage can make the loss exceed the planned amount.', 'bee-plan-small'));
    return result;
  }
  function renderReference() {
    referenceNode.replaceChildren(); referenceNode.hidden = !reference;
    if (!reference) return;
    referenceNode.appendChild(paragraph(reference.ticker + ' · recorded ' + (date(reference.date) ? reference.date : 'date unavailable') +
      ' · close ' + dollars(reference.close) + ' · high ' + dollars(reference.high) + ' · low ' + dollars(reference.low)));
    referenceNode.appendChild(paragraph('Historical reference only. Check current prices and your intended stop before using this plan.', 'bee-plan-small'));
    if (date(reference.date) && finite(reference.close) && finite(reference.low) && reference.close > reference.low && reference.low > 0) {
      referenceNode.appendChild(button('Use recorded close and low', 'bee-plan-use-reference', function () {
        inputs.entry.value = reference.close; inputs.stop.value = reference.low; updateCalculation();
        announce('Loaded historical close and low from ' + reference.date + '. Review both prices before use.'); inputs.entry.focus();
      }));
    }
  }
  function seed(row) {
    if (!object(row) || !ticker(row.ticker) || !host) return;
    reference = { ticker: ticker(row.ticker), date: row.date, close: row.close, high: row.high, low: row.low };
    inputs.ticker.value = reference.ticker;
    inputs.entry.value = ''; inputs.stop.value = '';
    renderReference(); updateCalculation(); selectTab('plan', false);
    host.scrollIntoView({ behavior: 'auto', block: 'start' }); inputs.entry.focus({ preventScroll: true });
    announce('Planning ' + reference.ticker + '. Enter your intended prices or explicitly use the dated reference.');
  }
  function copyPlan() {
    var result = updateCalculation(), t = ticker(inputs.ticker.value);
    if (!result.valid || !result.shares || !t) { announce(!t ? 'Enter a valid ticker before copying a plan.' : !result.valid ? result.error : 'A journal plan needs at least one whole share.'); return; }
    resetEditor();
    journalInputs.ticker.value = t; journalInputs.entry.value = inputs.entry.value;
    journalInputs.stop.value = inputs.stop.value; journalInputs.shares.value = result.shares;
    journalInputs.status.value = 'paper'; updateStatus(); selectTab('journal', false);
    host.querySelector('.bee-journal-editor').open = true;
    journalInputs.date.focus(); announce('Copied to a Paper plan draft. Enter its date, add your reasoning, then save. Nothing has been logged yet.');
  }
  function updateStatus() {
    var closed = journalInputs.status.value === 'closed', paper = journalInputs.status.value === 'paper';
    host.querySelector('#bee-journal-exit-fields').hidden = !closed;
    journalInputs.exit.required = closed; journalInputs.exitDate.required = closed;
    host.querySelector('label[for="bee-journal-entry"]').textContent = paper ? 'Planned entry ($)' : 'Actual entry ($)';
    host.querySelector('label[for="bee-journal-date"]').textContent = paper ? 'Plan date' : 'Actual entry date';
    host.querySelector('label[for="bee-journal-shares"]').textContent = paper ? 'Planned whole shares' : 'Actual whole shares';
    host.querySelector('#bee-journal-save').textContent = editingId ? 'Save changes' : paper ? 'Save paper plan' : closed ? 'Log closed trade' : 'Log open trade';
  }
  function resetEditor() {
    editingId = null;
    Object.keys(journalInputs).forEach(function (key) { journalInputs[key].value = key === 'status' ? 'paper' : ''; });
    if (host) { host.querySelector('#bee-journal-editor-title').textContent = 'Write a record'; updateStatus(); }
  }
  function editorRecord() {
    var v = values(journalInputs), status = v.status;
    return { id: editingId || Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 12),
      ticker: ticker(v.ticker), status: status, date: v.date, entry: number(v.entry), stop: number(v.stop), shares: number(v.shares),
      exit: status === 'closed' ? number(v.exit) : null, exitDate: status === 'closed' ? v.exitDate : null,
      note: v.note, marketNote: v.marketNote };
  }
  function saveRecord(event) {
    event.preventDefault();
    var record = editorRecord();
    if (!validateRecord(record)) { announce('Check the ticker, dates, positive entry and stop, and whole shares. Stop must be below entry. A closed trade needs an exit price (zero allowed) and an exit date on or after entry.'); return; }
    if (!editingId && records.length >= LIMIT) { announce('This journal holds 100 records. Export it and remove a record before adding another.'); return; }
    var index = records.findIndex(function (r) { return r.id === editingId; });
    if (editingId && index < 0) { announce('That record no longer exists. Start a new record.'); return; }
    if (index >= 0) records[index] = record; else records.unshift(record);
    persist(); resetEditor(); renderJournal();
    announce((record.status === 'paper' ? 'Paper plan saved' : 'Trade logged') + ' for ' + record.ticker + (storageOK ? ' on this browser.' : ' for this visit only.'));
    host.querySelector('#bee-journal-summary').focus();
  }
  function edit(record) {
    editingId = record.id;
    Object.keys(journalInputs).forEach(function (key) { journalInputs[key].value = record[key] === null ? '' : record[key]; });
    host.querySelector('#bee-journal-editor-title').textContent = 'Edit ' + record.ticker + ' record'; updateStatus();
    host.querySelector('.bee-journal-editor').open = true;
    journalInputs.status.focus();
  }
  function holding(record) {
    if (record.status === 'paper') return 'Paper plan · no holding clock or realized result.';
    if (!recordedDates.length) return 'No saved evening sessions available for a holding review.';
    var asOf = recordedDates[recordedDates.length - 1], end = record.status === 'closed' && record.exitDate < asOf ? record.exitDate : asOf;
    var count = recordedDates.filter(function (d) { return d > record.date && d <= end; }).length;
    var text = count + ' recorded sessions since entry · through ' + end + '.';
    if (record.date > asOf) return 'Entry is after the latest recorded session (' + asOf + '). No holding observations yet.';
    if (record.status === 'open' && count >= 5) text += ' Five-session review: revisit your exit plan and whether momentum remains.';
    else if (record.status === 'open' && count >= 3) text += ' Three-session review: did the move follow through? Review your stop and exit plan.';
    else if (record.status === 'open') text += ' Review follow-through around the third and fifth sessions.';
    return text;
  }
  function renderJournal() {
    if (!journalList) return;
    journalList.replaceChildren();
    var paper = records.filter(function (r) { return r.status === 'paper'; }).length;
    var open = records.filter(function (r) { return r.status === 'open'; }).length;
    var closed = records.filter(function (r) { return r.status === 'closed'; });
    var summary = host.querySelector('#bee-journal-summary');
    summary.textContent = paper + ' paper plans · ' + open + ' open trades · ' + closed.length + ' closed trades';
    if (!records.length) { journalList.appendChild(paragraph('Your first record starts with your decision. Copy a risk plan or enter a trade you actually made.')); return; }
    records.forEach(function (r) {
      var label = r.status === 'paper' ? 'Paper plan' : r.status === 'open' ? 'Open trade' : 'Closed trade';
      var card = node('article', { 'class': 'bee-journal-card', 'data-journal-id': r.id }, [
        node('div', { 'class': 'bee-journal-card-head' }, [node('h4', { text: r.ticker }), node('span', { 'class': 'bee-journal-status', text: label })]),
        paragraph(r.date + ' · ' + r.shares.toLocaleString('en-US') + ' shares · entry ' + dollars(r.entry) + ' · initial stop ' + dollars(r.stop)),
        paragraph(holding(r), 'bee-journal-clock')
      ]);
      var pnl = outcome(r);
      if (pnl) card.appendChild(paragraph('Exited ' + r.exitDate + ' at ' + dollars(r.exit) + ' · P/L ' + dollars(pnl.profit) + ' · ' + (pnl.r > 0 ? '+' : '') + pnl.r.toFixed(2) + 'R before fees.', 'bee-journal-outcome'));
      if (r.marketNote) card.appendChild(node('div', { 'class': 'bee-journal-note' }, [node('strong', { text: 'Market context' }), paragraph(r.marketNote)]));
      if (r.note) card.appendChild(node('div', { 'class': 'bee-journal-note' }, [node('strong', { text: 'Setup / follow-through / lesson' }), paragraph(r.note)]));
      var actions = node('div', { 'class': 'bee-plan-actions' });
      actions.appendChild(button(r.status === 'open' ? 'Edit / record exit' : 'Edit record', null, function () { edit(r); }, { 'aria-label': 'Edit ' + r.ticker + ' ' + label.toLowerCase() }));
      actions.appendChild(button('Delete', null, function () {
        actions.replaceChildren(paragraph('Delete this ' + r.ticker + ' record?'), button('Delete record', null, function () {
          records = records.filter(function (entry) { return entry.id !== r.id; });
          if (editingId === r.id) resetEditor(); persist(); renderJournal();
          announce('Deleted ' + r.ticker + ' record.'); summary.focus();
        }), button('Keep record', null, function () { renderJournal(); summary.focus(); }));
        actions.querySelector('button').focus();
      }, { 'aria-label': 'Delete ' + r.ticker + ' ' + label.toLowerCase() }));
      card.appendChild(actions); journalList.appendChild(card);
    });
  }
  function exportJournal() {
    var blob = new Blob([JSON.stringify({ version: 1, records: records }, null, 2)], { type: 'application/json' });
    var url = URL.createObjectURL(blob), link = node('a', { href: url, download: 'spicystock-trade-journal.json' });
    document.body.appendChild(link); link.click(); link.remove();
    window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    announce('Journal export requested. Keep the downloaded file private; it includes your notes and trade records.');
  }
  function mount() {
    host.classList.add('bee-plan-workspace'); host.hidden = false; host.replaceChildren();
    host.appendChild(node('header', { 'class': 'bee-plan-heading' }, [node('p', { 'class': 'sc-eyebrow', text: '03 / plan & learn' }),
      node('h2', { id: 'bee-plan-heading', text: 'Define the risk. Keep the lesson.' }),
      paragraph('Turn a setup into a deliberate plan, then record what happened. The calculator is long-only and uses your own inputs; this page places no orders.') ]));
    host.setAttribute('aria-labelledby', 'bee-plan-heading');
    var tablist = node('div', { 'class': 'bee-plan-tabs', role: 'tablist', 'aria-label': 'Risk plan and trade journal' });
    ['plan', 'journal'].forEach(function (name, index) {
      var b = button(name === 'plan' ? 'Risk plan' : 'Trade journal', 'bee-tab-' + name, function () { selectTab(name, true); },
        { role: 'tab', 'data-plan-tab': name, 'aria-controls': 'bee-panel-' + name, 'aria-selected': String(index === 0), tabindex: index === 0 ? '0' : '-1' });
      b.addEventListener('keydown', function (event) {
        if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].indexOf(event.key) < 0) return;
        event.preventDefault(); selectTab(event.key === 'Home' ? 'plan' : event.key === 'End' ? 'journal' : activeTab === 'plan' ? 'journal' : 'plan', true);
      });
      tabs.push(b); tablist.appendChild(b);
    });
    host.appendChild(tablist);
    notice = node('p', { 'class': 'bee-plan-notice', id: 'bee-plan-notice', role: 'status', 'aria-live': 'polite' }); host.appendChild(notice);
    planPanel = node('div', { id: 'bee-panel-plan', role: 'tabpanel', 'aria-labelledby': 'bee-tab-plan' });
    journalPanel = node('div', { id: 'bee-panel-journal', role: 'tabpanel', 'aria-labelledby': 'bee-tab-journal', hidden: '' });
    host.appendChild(planPanel); host.appendChild(journalPanel);
    referenceNode = node('aside', { 'class': 'bee-plan-reference', id: 'bee-plan-reference', hidden: '' }); planPanel.appendChild(referenceNode);
    var layout = node('div', { 'class': 'bee-plan-layout' }), form = node('form', { id: 'bee-plan-form', 'class': 'bee-plan-form' });
    form.addEventListener('submit', function (event) { event.preventDefault(); updateCalculation(); });
    var grid = node('div', { 'class': 'bee-plan-inputs' });
    [['Ticker', 'ticker', { type: 'text', maxlength: '15', autocapitalize: 'characters', autocomplete: 'off', spellcheck: 'false' }],
      ['Capital ($)', 'capital', { type: 'number', min: '0', step: 'any', inputmode: 'decimal', required: '' }],
      ['Your risk budget (%)', 'riskPercent', { type: 'number', min: '0', max: '100', step: 'any', inputmode: 'decimal', required: '' }],
      ['Planned entry ($)', 'entry', { type: 'number', min: '0', step: 'any', inputmode: 'decimal', required: '' }],
      ['Initial stop ($)', 'stop', { type: 'number', min: '0', step: 'any', inputmode: 'decimal', required: '' }],
      ['Position cash cap ($, optional)', 'cashCap', { type: 'number', min: '0', step: 'any', inputmode: 'decimal' }]].forEach(function (spec) {
      grid.appendChild(field(spec[0], 'bee-plan-' + spec[1], spec[2], inputs, spec[1]));
    });
    form.appendChild(grid);
    form.appendChild(paragraph('Choose the risk percentage yourself. A blank cash cap uses your capital; it does not account for other positions or cash already committed.', 'bee-plan-small'));
    form.addEventListener('input', function () {
      if (reference && ticker(inputs.ticker.value) !== reference.ticker) { reference = null; renderReference(); }
      updateCalculation();
    });
    form.appendChild(button('Copy to journal draft', 'bee-plan-copy', copyPlan));
    resultNode = node('div', { 'class': 'bee-plan-result', id: 'bee-plan-result', role: 'region', 'aria-label': 'Position size calculation' });
    layout.appendChild(form); layout.appendChild(resultNode); planPanel.appendChild(layout);
    var source = paragraph('Method: risk dollars ÷ (entry − stop), then capped by available cash. Inspired by ', 'bee-plan-small');
    source.appendChild(sourceLink(RISK_SOURCE, 'Stockbee’s risk model')); source.appendChild(document.createTextNode('.')); planPanel.appendChild(source);
    buildJournal();
    storageNode = paragraph('', 'bee-plan-storage'); storageNode.id = 'bee-journal-storage'; host.appendChild(storageNode);
    storageMessage(); updateCalculation(); selectTab(activeTab, false);
  }
  function buildJournal() {
    var top = node('div', { 'class': 'bee-journal-heading' }, [
      paragraph('Paper plans stay separate from actual trades. Enter actual fills yourself; this journal does not infer positions from scanner results.'),
      button('Export journal', 'bee-journal-export', exportJournal)
    ]); journalPanel.appendChild(top);
    var editor = node('details', { 'class': 'bee-journal-editor', open: '' });
    editor.appendChild(node('summary', { id: 'bee-journal-editor-title', text: 'Write a record' }));
    var form = node('form', { id: 'bee-journal-form' }), grid = node('div', { 'class': 'bee-plan-inputs' });
    var status = node('select', { id: 'bee-journal-status' }, ['paper', 'open', 'closed'].map(function (value) {
      return node('option', { value: value, text: value === 'paper' ? 'Paper plan' : value === 'open' ? 'Open trade' : 'Closed trade' });
    })); journalInputs.status = status; status.addEventListener('change', updateStatus);
    grid.appendChild(node('div', { 'class': 'bee-plan-field' }, [node('label', { for: 'bee-journal-status', text: 'Record type' }), status]));
    [['Ticker', 'ticker', { type: 'text', maxlength: '15', required: '', autocapitalize: 'characters', autocomplete: 'off', spellcheck: 'false' }],
      ['Plan date', 'date', { type: 'date', required: '' }],
      ['Planned entry ($)', 'entry', { type: 'number', min: '0', step: 'any', inputmode: 'decimal', required: '' }],
      ['Initial stop ($)', 'stop', { type: 'number', min: '0', step: 'any', inputmode: 'decimal', required: '' }],
      ['Planned whole shares', 'shares', { type: 'number', min: '1', step: '1', inputmode: 'numeric', required: '' }]].forEach(function (spec) {
      grid.appendChild(field(spec[0], 'bee-journal-' + spec[1], spec[2], journalInputs, spec[1]));
    }); form.appendChild(grid);
    var exit = node('div', { id: 'bee-journal-exit-fields', 'class': 'bee-plan-inputs', hidden: '' });
    exit.appendChild(field('Actual exit ($)', 'bee-journal-exit', { type: 'number', min: '0', step: 'any', inputmode: 'decimal' }, journalInputs, 'exit'));
    exit.appendChild(field('Actual exit date', 'bee-journal-exitDate', { type: 'date' }, journalInputs, 'exitDate')); form.appendChild(exit);
    form.appendChild(field('Market context on entry (optional)', 'bee-journal-marketNote', { type: 'textarea', rows: '2', maxlength: String(NOTE_LIMIT), placeholder: 'What were market conditions, and why did you choose to act or sit out?' }, journalInputs, 'marketNote'));
    form.appendChild(field('Setup, follow-through and lesson (optional)', 'bee-journal-note', { type: 'textarea', rows: '3', maxlength: String(NOTE_LIMIT), placeholder: 'What was the setup? What would invalidate it? What happened next?' }, journalInputs, 'note'));
    form.appendChild(paragraph('Initial stop is the original risk reference for R. Closed records represent the entire position at one exit price; for several fills, enter your share-weighted average prices. P/L excludes fees.', 'bee-plan-small'));
    form.appendChild(node('div', { 'class': 'bee-plan-actions' }, [node('button', { type: 'submit', 'class': 'bee-plan-button', id: 'bee-journal-save', text: 'Save paper plan' }),
      button('New blank record', 'bee-journal-new', function () { resetEditor(); announce('Started a blank draft. Saved records are unchanged.'); journalInputs.ticker.focus(); })]));
    form.addEventListener('submit', saveRecord); editor.appendChild(form); journalPanel.appendChild(editor);
    journalPanel.appendChild(node('p', { id: 'bee-journal-summary', 'class': 'bee-journal-summary', tabindex: '-1' }));
    var clockNote = paragraph('Review prompts count unique saved evening sessions after entry, excluding dry runs. Missing scans mean missing sessions; this is not an exchange calendar or a live holding clock. See ', 'bee-plan-small');
    clockNote.appendChild(sourceLink(PROCESS_SOURCE, 'Stockbee’s 3–5 day process')); clockNote.appendChild(document.createTextNode(' for the original guidelines. Prompts are reminders to review, not automatic exit instructions.'));
    journalPanel.appendChild(clockNote);
    journalList = node('div', { 'class': 'bee-journal-list', id: 'bee-journal-list' }); journalPanel.appendChild(journalList);
    updateStatus(); renderJournal();
  }
  function render(d) {
    recordedDates = Array.from(new Set((d && Array.isArray(d.runs) ? d.runs : []).filter(function (r) {
      return object(r) && r.type === 'evening' && !r.dry_run && date(r.date);
    }).map(function (r) { return r.date; }))).sort();
    var target = document.getElementById('stockbee-plan');
    if (!target) return;
    if (host !== target || !target.querySelector('#bee-plan-form')) { host = target; inputs = {}; journalInputs = {}; tabs = []; mount(); }
    else { host.hidden = false; renderJournal(); }
  }
  window.addEventListener('stockbee:plan', function (event) { seed(event.detail && (event.detail.setupRow || event.detail)); });
  window.addEventListener('storage', function (event) {
    if (event.key !== KEY && event.key !== null) return;
    if (!storageOK) return;
    try {
      var raw = window.localStorage.getItem(KEY), updated = decode(raw);
      records = updated; lastStored = raw; renderJournal();
      announce('Journal updated from another tab. Your unsaved form remains in place.');
    } catch (_) { storageOK = false; storageReason = 'A journal update from another tab could not be read. The stored copy will not be overwritten.'; storageMessage(); }
  });
  window.SCStockPlan = { render: render, calculate: calculate, outcome: outcome };
}());
