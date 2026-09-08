/* Personal research state. Market facts are always read from the active snapshot. */
(function () {
  'use strict';
  var KEY = 'spicystock.research.v1';
  var LIMIT = 100, NOTE_LIMIT = 4000, COMPARE_LIMIT = 3;
  var saved = new Map(), drafts = new Map(), compared = [];
  var candidates = new Map(), snapshot = null, activeTab = 'compare', addDraft = '';
  var host, comparePanel, savedPanel, message, storageStatus, tabButtons;
  var storageOK = true, storageReason = '';
  var tray, traySummary, trayNoticeNode, trayObserver, trayNotice = '', trayReturnFocus;

  function node(tag, attrs, children) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      if (key === 'text') n.textContent = attrs[key];
      else n.setAttribute(key, attrs[key]);
    });
    (children || []).forEach(function (child) { if (child) n.appendChild(child); });
    return n;
  }
  function ticker(value) {
    if (typeof value !== 'string') return null;
    var result = value.trim().toUpperCase();
    return /^[A-Z][A-Z0-9.-]{0,14}$/.test(result) ? result : null;
  }
  function ownObject(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value) &&
      (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
  }
  function decode(raw) {
    if (raw === null) return new Map();
    var data = JSON.parse(raw);
    if (!ownObject(data) || data.version !== 1 || !Array.isArray(data.saved) || data.saved.length > LIMIT) {
      throw new Error('Invalid notebook');
    }
    var result = new Map();
    data.saved.forEach(function (entry) {
      if (!ownObject(entry) || !Object.prototype.hasOwnProperty.call(entry, 'ticker') ||
          !Object.prototype.hasOwnProperty.call(entry, 'note') || ticker(entry.ticker) !== entry.ticker ||
          typeof entry.note !== 'string' || entry.note.length > NOTE_LIMIT || result.has(entry.ticker)) {
        throw new Error('Invalid saved research');
      }
      result.set(entry.ticker, { ticker: entry.ticker, note: entry.note });
    });
    return result;
  }
  try { saved = decode(window.localStorage.getItem(KEY)); }
  catch (_) { storageOK = false; storageReason = 'Browser storage is unavailable or the saved notebook could not be read.'; }

  function persist() {
    if (!storageOK) return;
    try {
      window.localStorage.setItem(KEY, JSON.stringify({ version: 1, saved: Array.from(saved.values()) }));
    } catch (_) {
      storageOK = false;
      storageReason = 'Browser storage is unavailable or full.';
    }
  }
  function announce(text) {
    if (message) message.textContent = text;
  }
  function notify(text) {
    repaint();
    announce(text);
    window.dispatchEvent(new CustomEvent('stock:desk-change', {
      detail: { saved: Array.from(saved.keys()), compared: compared.slice() }
    }));
  }
  function source(c) {
    var p = c && c.provenance;
    return p && p.source === 'claude' ? 'Claude review' : p && p.source === 'fallback' ? 'Checklist fallback' : 'Source not recorded';
  }
  function number(value, digits, suffix, signed) {
    if (typeof value !== 'number' || !isFinite(value)) return 'Not recorded';
    return (signed && value > 0 ? '+' : '') + value.toFixed(digits) + (suffix || '');
  }
  function checks(c) {
    return Number.isInteger(c.lynch_passes) && Number.isInteger(c.lynch_total) && c.lynch_total > 0
      ? c.lynch_passes + ' / ' + c.lynch_total + ' passed' : 'Not recorded';
  }
  function button(label, focusKey, handler, extra) {
    var attrs = Object.assign({ type: 'button', 'class': 'desk-button', 'data-desk-focus': focusKey, text: label }, extra || {});
    var b = node('button', attrs);
    b.addEventListener('click', handler);
    return b;
  }
  function facts(c) {
    var dl = node('dl', { 'class': 'desk-facts' });
    [
      ['Recorded score', number(c.score, 1, ' / 10')],
      ['Score source', source(c)],
      ['Session gain', number(c.gain_pct, 2, '%', true)],
      ['Relative volume', number(c.volume_ratio, 2, '× average')],
      ['2LYNCH checks', checks(c)]
    ].forEach(function (pair) {
      dl.appendChild(node('div', {}, [node('dt', { text: pair[0] }), node('dd', { text: pair[1] })]));
    });
    return dl;
  }
  function recordLink(t) {
    var match = candidates.get(t);
    return match ? node('a', { 'class': 'desk-link', href: '#signal-record-' + match.index, text: 'Open recorded detail', 'aria-label': 'Open recorded detail for ' + t }) : null;
  }
  function empty(title, text) {
    return node('div', { 'class': 'desk-empty' }, [
      node('p', { 'class': 'desk-empty-title', text: title }), node('p', { text: text }),
      node('a', { 'class': 'desk-link', href: '#signal-workspace', text: 'Explore this session’s candidates' })
    ]);
  }
  function renderComparison() {
    comparePanel.replaceChildren();
    var heading = node('div', { 'class': 'desk-panel-heading' }, [
      node('div', {}, [node('h3', { text: 'A closer look, side by side' }),
        node('p', { text: 'Choose up to three candidates from the signal cards. These are recorded observations from the current snapshot.' })]),
      node('span', { 'class': 'desk-count', id: 'desk-compare-count', text: compared.length + ' / ' + COMPARE_LIMIT + ' selected' })
    ]);
    comparePanel.appendChild(heading);
    if (!compared.length) {
      comparePanel.appendChild(empty('Build your comparison.', 'Tap “Compare” on a candidate to bring its score, momentum, checklist and recorded risk into one place.'));
      return;
    }
    var grid = node('div', { 'class': 'desk-compare-grid' });
    compared.forEach(function (t) {
      var c = candidates.get(t).row;
      var card = node('article', { 'class': 'desk-compare-card', 'data-desk-ticker': t, 'aria-label': t + ' comparison' }, [
        node('div', { 'class': 'desk-card-heading' }, [
          node('h4', { text: t }),
          button('Remove', 'compare-remove-' + t, function () { toggleCompare(t); }, { 'aria-label': 'Remove ' + t + ' from comparison' })
        ]),
        node('p', { 'class': 'desk-stamp', text: 'Session ' + (c.date || snapshot.run.date || 'not recorded') }),
        facts(c),
        node('div', { 'class': 'desk-risk' }, [node('span', { text: 'Recorded key risk' }), node('p', { text: typeof c.key_risk === 'string' && c.key_risk.trim() ? c.key_risk : 'No key risk was recorded.' })]),
        node('div', { 'class': 'desk-card-actions' }, [
          button(saved.has(t) ? 'Saved to research' : 'Save to research', 'compare-save-' + t, function () { toggleSaved(t); }, { 'aria-pressed': String(saved.has(t)), 'aria-label': (saved.has(t) ? 'Unsave ' : 'Save ') + t + ' research' }),
          recordLink(t)
        ])
      ]);
      grid.appendChild(card);
    });
    comparePanel.appendChild(grid);
    comparePanel.appendChild(node('p', { 'class': 'desk-footnote', text: 'Claude reviews and checklist fallbacks use different scoring sources. Compare the source and the risk alongside the number.' }));
  }
  function renderSaved() {
    savedPanel.replaceChildren();
    var currentCount = Array.from(saved.keys()).filter(function (t) { return candidates.has(t); }).length;
    savedPanel.appendChild(node('div', { 'class': 'desk-panel-heading' }, [node('div', {}, [
      node('h3', { text: 'Your research, between sessions' }),
      node('p', { id: 'desk-saved-summary', text: saved.size + ' saved · ' + currentCount + ' in this snapshot. Notes belong to you; saving a ticker does not add it to the scanner.' })
    ])]));
    var add = node('form', { 'class': 'desk-add-form' });
    var input = node('input', { id: 'desk-add-ticker', name: 'ticker', type: 'text', maxlength: '15', autocomplete: 'off', autocapitalize: 'characters', spellcheck: 'false', placeholder: 'TICKER', 'data-desk-focus': 'add-ticker', 'aria-describedby': 'desk-add-help' });
    input.value = addDraft;
    add.appendChild(node('div', { 'class': 'desk-add-field' }, [node('label', { for: 'desk-add-ticker', text: 'Add a research ticker' }), input]));
    add.appendChild(node('button', { type: 'submit', 'class': 'desk-button desk-button-primary', 'data-desk-focus': 'add-submit', text: 'Add ticker' }));
    add.addEventListener('submit', function (event) {
      event.preventDefault();
      var t = ticker(input.value);
      if (!t) { input.setCustomValidity('Use a ticker of 1–15 letters, numbers, dots or hyphens, starting with a letter.'); input.reportValidity(); return; }
      input.setCustomValidity('');
      if (saved.has(t)) { announce(t + ' is already in saved research.'); return; }
      if (saved.size < LIMIT) addDraft = '';
      if (addSaved(t)) {
        var note = document.getElementById('desk-note-' + t);
        if (note) note.focus({ preventScroll: true });
      }
    });
    input.addEventListener('input', function () { addDraft = input.value; input.setCustomValidity(''); });
    savedPanel.appendChild(add);
    savedPanel.appendChild(node('p', { 'class': 'desk-footnote', id: 'desk-add-help', text: 'Add a ticker for personal notes, or save one from the signal cards. Metrics appear only when it is a candidate in the current snapshot.' }));
    if (!saved.size) {
      savedPanel.appendChild(empty('Keep the thread of your research.', 'Save a candidate or add a ticker above, then write what you want to revisit. Your notebook stays in this browser.'));
      return;
    }
    var list = node('div', { 'class': 'desk-saved-grid' });
    saved.forEach(function (entry, t) {
      var match = candidates.get(t), c = match && match.row;
      var card = node('article', { 'class': 'desk-saved-card', 'data-desk-saved': t, 'aria-label': t + ' saved research' }, [
        node('div', { 'class': 'desk-card-heading' }, [node('h4', { text: t }),
          button('Remove', 'saved-remove-' + t, function () { toggleSaved(t); }, { 'aria-label': 'Remove ' + t + ' and its note from saved research' })]),
        node('p', { 'class': 'desk-availability' + (c ? ' is-current' : ''), text: c ? 'In this snapshot · ' + (c.date || snapshot.run.date || 'session not recorded') : 'Not a candidate in this snapshot' })
      ]);
      if (c) {
        card.appendChild(node('p', { 'class': 'desk-saved-metrics', text: number(c.score, 1, ' / 10') + ' · ' + source(c) + ' · ' + number(c.gain_pct, 2, '%', true) + ' session gain' }));
      } else {
        card.appendChild(node('p', { 'class': 'desk-footnote', text: 'Personal notes only. No earlier market metrics are carried forward here.' }));
      }
      var value = drafts.has(t) ? drafts.get(t) : entry.note;
      var noteId = 'desk-note-' + t, countId = 'desk-note-count-' + t;
      var area = node('textarea', { id: noteId, rows: '4', maxlength: String(NOTE_LIMIT), 'data-desk-focus': 'note-' + t, 'aria-describedby': countId, placeholder: 'What caught your eye? What would you revisit?' });
      area.value = value;
      var count = node('span', { id: countId, 'class': 'desk-note-count', text: value.length + ' / ' + NOTE_LIMIT + (value !== entry.note ? ' · unsaved edits' : '') });
      var save = button('Save note', 'note-save-' + t, function () {
        var text = area.value.slice(0, NOTE_LIMIT);
        saved.set(t, { ticker: t, note: text });
        drafts.delete(t);
        persist();
        notify(t + (storageOK ? ' note saved in this browser.' : ' note kept only for this visit.'));
      }, { 'class': 'desk-button desk-button-primary', 'aria-label': 'Save note for ' + t });
      save.disabled = value === entry.note;
      area.addEventListener('input', function () {
        drafts.set(t, area.value);
        var changed = area.value !== saved.get(t).note;
        count.textContent = area.value.length + ' / ' + NOTE_LIMIT + (changed ? ' · unsaved edits' : '');
        save.disabled = !changed;
      });
      card.appendChild(node('label', { 'class': 'desk-note-label', for: noteId, text: 'Your note on ' + t }));
      card.appendChild(area);
      card.appendChild(count);
      card.appendChild(node('div', { 'class': 'desk-card-actions' }, [save,
        c ? button(compared.indexOf(t) >= 0 ? 'In comparison' : 'Compare', 'saved-compare-' + t, function () { toggleCompare(t); }, { 'aria-pressed': String(compared.indexOf(t) >= 0), 'aria-label': 'Compare ' + t }) : null,
        recordLink(t)]));
      list.appendChild(card);
    });
    savedPanel.appendChild(list);
  }
  function setTab(tab, focus) {
    activeTab = tab;
    Object.keys(tabButtons).forEach(function (name) {
      tabButtons[name].setAttribute('aria-selected', String(name === tab));
      tabButtons[name].tabIndex = name === tab ? 0 : -1;
    });
    comparePanel.hidden = tab !== 'compare';
    savedPanel.hidden = tab !== 'saved';
    if (focus) tabButtons[tab].focus();
  }
  function syncTraySpace() {
    if (!tray) return;
    var visible = !tray.hidden && host && !host.hidden && tray.getBoundingClientRect().height > 0;
    document.body.classList.toggle('desk-has-tray', visible);
    if (visible) {
      var box = tray.getBoundingClientRect();
      var space = Math.ceil(box.height + Math.max(0, window.innerHeight - box.bottom) + 12) + 'px';
      if (document.documentElement.style.getPropertyValue('--desk-tray-space') !== space) {
        document.documentElement.style.setProperty('--desk-tray-space', space);
      }
    } else {
      document.documentElement.style.removeProperty('--desk-tray-space');
    }
  }
  function syncTrayVisibility() {
    if (!tray) return;
    var focused = document.activeElement;
    var editing = focused && (focused.matches('input, textarea, select') || focused.isContentEditable);
    tray.hidden = !compared.length || !!editing;
    syncTraySpace();
  }
  function renderTray() {
    if (!tray) return;
    traySummary.textContent = compared.length + ' / ' + COMPARE_LIMIT + ' selected · ' + compared.join(' · ');
    trayNoticeNode.textContent = trayNotice;
    trayNoticeNode.hidden = !trayNotice;
    syncTrayVisibility();
  }
  function mountTray() {
    if (trayObserver) trayObserver.disconnect();
    traySummary = node('p', { id: 'desk-tray-summary', 'class': 'desk-tray-summary' });
    trayNoticeNode = node('p', { id: 'desk-tray-notice', 'class': 'desk-tray-notice', hidden: '' });
    var open = button('Open comparison', 'tray-open', function () {
      setTab('compare', false);
      comparePanel.focus({ preventScroll: true });
      host.scrollIntoView({ block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    }, { id: 'desk-tray-open', 'class': 'desk-button desk-button-primary', 'aria-controls': 'desk-panel-compare' });
    var clear = button('Clear comparison', 'tray-clear', function () {
      compared = [];
      trayNotice = '';
      notify('Comparison cleared.');
      var target = trayReturnFocus && trayReturnFocus.isConnected ? trayReturnFocus : tabButtons[activeTab];
      target.focus({ preventScroll: true });
    }, { id: 'desk-tray-clear' });
    tray = node('aside', { id: 'desk-comparison-tray', 'class': 'desk-tray', 'aria-label': 'Selected candidate comparison', hidden: '' }, [
      node('div', { 'class': 'desk-tray-copy' }, [traySummary, trayNoticeNode]),
      node('div', { 'class': 'desk-tray-actions' }, [open, clear])
    ]);
    host.appendChild(tray);
    if (typeof ResizeObserver !== 'undefined') {
      trayObserver = new ResizeObserver(syncTraySpace);
      trayObserver.observe(tray);
    }
  }
  function mount() {
    host = document.getElementById('stock-desk');
    if (!host) return false;
    host.classList.add('desk-workspace');
    host.setAttribute('aria-labelledby', 'desk-title');
    host.replaceChildren();
    host.appendChild(node('div', { 'class': 'desk-heading' }, [node('p', { 'class': 'sc-eyebrow', text: 'Your research desk' }),
      node('h2', { id: 'desk-title', text: 'A little less noise. A closer look.' }),
      node('p', { 'class': 'desk-description', text: 'Put candidates beside each other, keep your own notes, and pick up the thread next session.' })]));
    var tabs = node('div', { 'class': 'desk-tabs', role: 'tablist', 'aria-label': 'Research desk' });
    tabButtons = {};
    ['compare', 'saved'].forEach(function (name) {
      var b = button('', 'tab-' + name, function () { setTab(name, false); }, { id: 'desk-tab-' + name, 'class': 'desk-tab', role: 'tab', 'aria-controls': 'desk-panel-' + name });
      b.addEventListener('keydown', function (event) {
        if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].indexOf(event.key) < 0) return;
        event.preventDefault();
        setTab(event.key === 'Home' ? 'compare' : event.key === 'End' ? 'saved' : name === 'compare' ? 'saved' : 'compare', true);
      });
      tabButtons[name] = b;
      tabs.appendChild(b);
    });
    host.appendChild(tabs);
    message = node('p', { id: 'desk-message', 'class': 'desk-message', role: 'status', 'aria-live': 'polite', 'aria-atomic': 'true' });
    storageStatus = node('p', { id: 'desk-storage-status', 'class': 'desk-storage-status' });
    host.appendChild(message);
    comparePanel = node('div', { id: 'desk-panel-compare', 'class': 'desk-panel', role: 'tabpanel', 'aria-labelledby': 'desk-tab-compare', tabindex: '0' });
    savedPanel = node('div', { id: 'desk-panel-saved', 'class': 'desk-panel', role: 'tabpanel', 'aria-labelledby': 'desk-tab-saved', tabindex: '0' });
    host.appendChild(comparePanel);
    host.appendChild(savedPanel);
    host.appendChild(storageStatus);
    mountTray();
    return true;
  }
  function repaint() {
    if (!host || !host.isConnected) { if (!mount()) return; }
    var focused = document.activeElement, inside = focused && host.contains(focused);
    var focusKey = inside && focused.getAttribute('data-desk-focus');
    var selection = inside && focused.tagName === 'TEXTAREA' ? [focused.selectionStart, focused.selectionEnd] : null;
    tabButtons.compare.textContent = 'Comparison (' + compared.length + ')';
    tabButtons.saved.textContent = 'Saved research (' + saved.size + ')';
    renderComparison();
    renderSaved();
    setTab(activeTab, false);
    storageStatus.textContent = storageOK
      ? 'Private to this browser · notes are saved only when you press Save note. Browser data clearing removes your notebook; it does not sync between devices.'
      : 'Only this visit: ' + storageReason + ' Keep a separate copy of any notes you want to retain.';
    storageStatus.classList.toggle('is-temporary', !storageOK);
    host.hidden = false;
    renderTray();
    if (inside && focusKey) {
      var replacement = Array.from(host.querySelectorAll('[data-desk-focus]')).find(function (n) { return n.getAttribute('data-desk-focus') === focusKey; });
      if (replacement && !replacement.disabled) {
        replacement.focus({ preventScroll: true });
        if (selection && replacement.tagName === 'TEXTAREA') replacement.setSelectionRange(selection[0], selection[1]);
      } else {
        var noteTarget = focusKey.indexOf('note-save-') === 0 && document.getElementById('desk-note-' + focusKey.slice(10));
        (noteTarget || tabButtons[activeTab]).focus({ preventScroll: true });
      }
    }
    syncTrayVisibility();
  }
  function addSaved(t) {
    if (saved.size >= LIMIT) { announce('Your notebook holds up to ' + LIMIT + ' tickers. Remove one before adding another.'); return false; }
    saved.set(t, { ticker: t, note: '' });
    persist();
    notify(t + (storageOK ? ' saved to research.' : ' saved only for this visit.'));
    return true;
  }
  function toggleSaved(value) {
    var t = ticker(value);
    if (!t) return false;
    if (!saved.has(t)) return addSaved(t);
    saved.delete(t);
    drafts.delete(t);
    persist();
    notify(t + ' and its note removed from saved research.');
    return false;
  }
  function toggleCompare(value) {
    var t = ticker(value), index = compared.indexOf(t);
    var focused = document.activeElement;
    if (focused && focused !== document.body && (!tray || !tray.contains(focused))) trayReturnFocus = focused;
    if (index >= 0) {
      compared.splice(index, 1);
      trayNotice = '';
      notify(t + ' removed from comparison.');
      return false;
    }
    if (!t || !candidates.has(t)) { announce('Only candidates in this snapshot can be compared.'); return false; }
    if (compared.length >= COMPARE_LIMIT) {
      trayNotice = 'Three selected. Open comparison to remove one before adding ' + t + '.';
      renderTray();
      announce('Three candidates are already selected. Remove one from comparison to add ' + t + '.');
      return false;
    }
    compared.push(t);
    trayNotice = '';
    notify(t + ' added to comparison. ' + compared.length + ' of ' + COMPARE_LIMIT + ' selected.');
    return true;
  }
  function render(data) {
    snapshot = data && typeof data === 'object' ? data : {};
    if (!snapshot.run) snapshot = Object.assign({}, snapshot, { run: {} });
    candidates = new Map();
    (Array.isArray(snapshot.candidates) ? snapshot.candidates : []).forEach(function (c, index) {
      var t = c && ticker(c.ticker);
      if (t && !candidates.has(t)) candidates.set(t, { row: c, index: index });
    });
    compared = compared.filter(function (t) { return candidates.has(t); });
    trayNotice = '';
    repaint();
    window.dispatchEvent(new CustomEvent('stock:desk-change', {
      detail: { saved: Array.from(saved.keys()), compared: compared.slice() }
    }));
  }
  window.addEventListener('storage', function (event) {
    if (event.key !== KEY && event.key !== null) return;
    try {
      saved = decode(event.key === null ? null : event.newValue);
      storageOK = true;
      storageReason = '';
      Array.from(drafts.keys()).forEach(function (t) { if (!saved.has(t)) drafts.delete(t); });
      notify('Saved research updated from another tab.');
    } catch (_) {
      storageOK = false;
      storageReason = 'The notebook changed in another tab but could not be read.';
      repaint();
    }
  });
  document.addEventListener('focusin', syncTrayVisibility);
  document.addEventListener('focusout', function () { window.requestAnimationFrame(syncTrayVisibility); });
  window.addEventListener('resize', syncTraySpace);
  window.SCStockDesk = {
    render: render,
    toggleSaved: toggleSaved,
    toggleCompare: toggleCompare,
    hasSaved: function (value) { return saved.has(ticker(value)); },
    hasCompared: function (value) { return compared.indexOf(ticker(value)) >= 0; }
  };
}());
