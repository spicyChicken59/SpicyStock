/* A deliberate find → plan → confirm → track workflow. Orders require the private bridge. */
(function () {
  'use strict';
  var host, data, activeTab = 'today', queueTab = 'breakout', query = '', selected = null;
  var panel, statusPanel, notice, profileOpen = false, manualOpen = false, importOpen = false;
  var draft = { symbol: '', entry: '', stop: '', note: '' }, fillDraft = {}, editingPlan = null;
  var preview = null, importPreview = null, broker = { state: 'unconfigured', connected: false };
  var portfolio = null, brokerError = '', busy = false, refreshSerial = 0, timer, initialized = false;
  var bridgeReady = false, bridgeLoading = false, planVisible = false, message = '';
  var SOURCE = 'https://stockbee.blogspot.com/2015/11/how-to-use-4-breakout-scan-to-make-money.html';

  function node(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; }
  function list(v) { return Array.isArray(v) ? v : []; }
  function finite(v) { return typeof v === 'number' && Number.isFinite(v); }
  function number(v, digits) { return finite(v) ? v.toLocaleString('en-US', { maximumFractionDigits: digits === undefined ? 2 : digits }) : 'Not available'; }
  function money(v) { return finite(v) ? '$' + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : 'Not available'; }
  function pct(v) { return finite(v) ? (v > 0 ? '+' : '') + v.toFixed(2) + '%' : 'Not measured'; }
  function safeDate(v) { return typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && Number.isFinite(Date.parse(v + 'T12:00:00Z')); }
  function time(v) { var d = new Date(v); return v && Number.isFinite(d.getTime()) ? d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : 'Time not available'; }
  function elId(n, id) { n.id = id; return n; }
  function button(label, id, fn, primary) { var b = node('button', 'tw-button' + (primary ? ' tw-button--primary' : ''), label); b.type = 'button'; if (id) b.id = id; b.addEventListener('click', fn); return b; }
  function small(text) { return node('p', 'tw-small', text); }
  function metric(label, value) { var n = node('div', 'tw-metric'); n.append(node('dt', '', label), node('dd', '', value)); return n; }
  function announce(text) { message = text; if (notice) notice.textContent = text; }
  function focus(id) { var n = host && host.querySelector('#' + id); if (n) { n.scrollIntoView({ block: 'nearest', behavior: 'auto' }); n.focus({ preventScroll: true }); } }
  function engine() { if (!window.SCTradeState) throw new Error('Trade records could not load. Reload to restore the trading workspace.'); return window.SCTradeState; }
  function state() { return engine().getState(); }
  function derived() { return engine().derive(); }
  function profile() { return state().profile || {}; }
  function profileReady() { var p = profile(); return finite(p.capital) && p.capital > 0 && finite(p.risk_percent) && p.risk_percent > 0; }
  function measured() { var s = data && data.run && data.run.stockbee; return s && s.version === 1 && s.date === data.run.date ? s : null; }
  function oldSnapshot() { var stamp = data && data.generated; var age = Date.now() - Date.parse(stamp); return !Number.isFinite(age) || age < -300000 || age > 36 * 60 * 60 * 1000; }
  function scored(symbol) { return list(data && data.candidates).find(function (r) { return r.ticker === symbol; }); }
  function rows() {
    var s = measured(), group = s && (queueTab === 'anticipation' ? s.anticipation : s.scan);
    return list(group && group.rows).filter(function (r) { return r && typeof r.ticker === 'string' && /^[A-Z][A-Z0-9.-]{0,14}$/.test(r.ticker); })
      .slice().sort(function (a, b) { var ac = scored(a.ticker), bc = scored(b.ticker); var av = ac && finite(ac.score) ? ac.score : -1, bv = bc && finite(bc.score) ? bc.score : -1; return bv - av || (finite(b.close_position) ? b.close_position : -1) - (finite(a.close_position) ? a.close_position : -1) || a.ticker.localeCompare(b.ticker); });
  }
  function calc() { var p = profile(); return engine().calculate({ capital: p.capital, risk_percent: p.risk_percent, cash_cap: p.cash_cap, entry: draft.entry, stop: draft.stop }); }
  function mutate(result, success) { if (!result || !result.ok) { announce(result && result.error || 'This change could not be saved.'); return false; } announce(success + (result.temporary ? ' This visit only; export a backup before leaving.' : '')); return true; }
  function showTab(tab, keyboard) { activeTab = tab; paintTabs(); paintBody(); if (keyboard) focus('trade-tab-' + tab); }
  function tabButton(name, label) { var b = button(label, 'trade-tab-' + name, function () { showTab(name, false); }); b.className = 'tw-tab'; b.setAttribute('role', 'tab'); b.dataset.tradeTab = name; b.setAttribute('aria-controls', 'trade-panel'); return b; }
  function paintTabs() { host.querySelectorAll('[data-trade-tab]').forEach(function (b) { var yes = b.dataset.tradeTab === activeTab; b.setAttribute('aria-selected', String(yes)); b.tabIndex = yes ? 0 : -1; }); }

  function nextAction() {
    var d = derived(), s = measured();
    if (list(d.reconciliation).length || broker.state === 'reconciliation_needed' || list(portfolio && portfolio.unresolved).length) return { label: 'A record needs your attention.', text: 'Resolve unmatched fills or an uncertain order before preparing another trade.', button: 'Review positions', action: function () { showTab('positions'); }, tone: 'attention' };
    if (!profileReady()) return { label: 'Make this your trading desk.', text: 'Set your capital and the amount you choose to risk. We will do the share math for each plan.', button: 'Set my limits', action: function () { profileOpen = true; paintBody(); focus('trade-capital'); }, tone: 'ready' };
    if (list(portfolio && portfolio.pending_orders).length) return { label: 'An order is still in progress.', text: 'Submitted is not filled. Keep its actual fill and stop status in view.', button: 'Track the order', action: function () { showTab('positions'); }, tone: 'attention' };
    if (list(d.positions).length || list(d.broker_positions).length) return { label: 'Start with what you own.', text: 'Review your recorded positions, pending orders and planned risk before adding another setup.', button: 'Review positions', action: function () { showTab('positions'); }, tone: 'ready' };
    if (!s || oldSnapshot()) return { label: 'Your next move: prepare, then verify.', text: !s ? 'The saved scan predates the new 4% queue. Set up your plan while the next recorded scan arrives.' : 'These setups come from an older snapshot. Review the date and verify current market prices before acting.', button: 'Prepare a plan', action: openBlankPlan, tone: 'quiet' };
    if (broker.connected && portfolio && portfolio.clock && portfolio.clock.is_open === false) return { label: 'Market closed. Plan with a clear head.', text: 'Build a plan now. Order previews stay unavailable until the broker reports an open market.', button: rows().length ? 'Review the first setup' : 'Prepare a plan', action: function () { if (rows().length) choose(rows()[0]); else openBlankPlan(); }, tone: 'quiet' };
    if (!list(s.scan && s.scan.rows).length) return { label: 'No 4% matches in this scan.', text: 'A quiet list is useful information. Review the anticipation watchlist without treating it as a breakout signal.', button: 'See what is setting up', action: function () { queueTab = 'anticipation'; activeTab = 'today'; paintTabs(); paintBody(); focus('trade-watch-tab'); }, tone: 'quiet' };
    return { label: 'A short list. A deliberate next move.', text: 'Review why a stock matched, define your entry and stop, then choose whether to place an order.', button: 'Review the first setup', action: function () { queueTab = 'breakout'; choose(rows()[0]); }, tone: 'ready' };
  }
  function paintStatus() {
    if (!statusPanel) return;
    var next = nextAction(); statusPanel.replaceChildren(); statusPanel.dataset.tone = next.tone;
    var top = node('div', 'tw-status-line'); var mode = broker.connected ? (broker.mode === 'live' ? 'LIVE ACCOUNT' : 'PAPER ACCOUNT') : 'YOUR PRIVATE RECORD';
    top.append(node('span', 'tw-eyebrow', 'TODAY / ' + mode), node('span', 'tw-status-dot', navigator.onLine === false ? 'Offline · last saved view' : brokerError ? 'Broker refresh unavailable' : broker.connected ? 'Broker connected' : 'Broker not connected'));
    var text = node('div', 'tw-status-copy'); text.append(node('h1', 'tw-title', next.label), node('p', 'tw-intro', next.text));
    var actions = node('div', 'tw-actions'); actions.append(button(next.button, 'trade-next-action', next.action, true));
    var stamp = node('div', 'tw-data-stamp'); stamp.id = 'trade-data-status';
    var run = data && data.run || {}; stamp.append(node('span', '', 'Scan session ' + (run.date || 'not recorded')), node('span', '', 'Published ' + time(data && data.generated)), node('span', 'tw-data-quality', (run.fixture || run.dry_run ? 'Demonstration / rehearsal data' : oldSnapshot() ? 'Older snapshot · not a live quote' : 'Daily snapshot · not a live quote')));
    statusPanel.append(top, text, actions, stamp);
    var badge = host.querySelector('#trade-account-status'); if (badge) badge.textContent = broker.connected ? (broker.mode === 'live' ? 'Live' : 'Paper') + ' connected' : 'Not connected';
  }
  function storageLine() {
    var st = engine().getStorageStatus(); var p = node('p', 'tw-storage'); p.id = 'trade-storage-status';
    p.textContent = st.persistent ? 'Your plans and recorded fills stay in this browser. Export a backup to move devices.' : 'This visit only. ' + (st.reason || 'Browser storage is unavailable.') + ' Export a backup before leaving.';
    if (!st.persistent) p.classList.add('tw-warning'); return p;
  }
  function paintBody() {
    if (!panel) return; panel.replaceChildren(); panel.setAttribute('aria-labelledby', 'trade-tab-' + activeTab);
    if (activeTab === 'today') paintToday(); else if (activeTab === 'positions') paintPositions(); else paintActivity();
    panel.append(storageLine());
    if (notice) notice.textContent = message;
  }
  function sectionHeading(kicker, heading, text) { var h = node('div', 'tw-section-heading'); if (kicker) h.append(node('p', 'tw-eyebrow', kicker)); h.append(node('h3', '', heading)); if (text) h.append(node('p', 'tw-copy', text)); return h; }
  function empty(title, text) { var box = node('div', 'tw-empty'); box.append(node('h4', '', title), node('p', 'tw-copy', text)); return box; }
  function showProfile() { profileOpen = true; activeTab = 'today'; paintTabs(); paintBody(); focus('trade-capital'); }
  function paintToday() {
    var rail = node('div', 'tw-routine'); ['Find a setup', 'Define your risk', 'Confirm & track'].forEach(function (label, i) { var item = node('span', 'tw-routine-step'); item.append(node('b', '', '0' + (i + 1)), document.createTextNode(label)); rail.append(item); }); panel.append(rail);
    if (profileOpen) panel.append(profileForm());
    var grid = node('div', 'tw-desk-grid' + (planVisible ? ' tw-desk-grid--planning' : ''));
    var queue = node('section', 'tw-queue'); queue.id = 'trade-queue'; queue.append(sectionHeading('01 / FIND', 'Setups worth a closer look.', 'The published price-and-volume scan, before the stricter scoring filters.'));
    var tabs = node('div', 'tw-queue-switch'); tabs.setAttribute('role', 'group'); tabs.setAttribute('aria-label', 'Setup list');
    [['breakout', '4% breakouts', 'trade-breakout-tab'], ['anticipation', 'Setting up', 'trade-watch-tab']].forEach(function (item) { var b = button(item[1], item[2], function () { queueTab = item[0]; query = ''; paintBody(); focus(item[2]); }); b.setAttribute('aria-pressed', String(queueTab === item[0])); tabs.append(b); }); queue.append(tabs);
    var search = node('div', 'tw-search'); var label = node('label', '', 'Find a symbol'); label.htmlFor = 'trade-search'; var input = node('input'); input.id = 'trade-search'; input.type = 'search'; input.placeholder = 'Search this scan'; input.value = query; input.autocomplete = 'off'; input.addEventListener('input', function () { query = input.value; paintCards(queue.querySelector('#trade-setup-list')); }); search.append(label, input); queue.append(search);
    var cards = node('div', 'tw-setup-list'); cards.id = 'trade-setup-list'; paintCards(cards); queue.append(cards);
    var methods = node('details', 'tw-details'); methods.append(node('summary', '', 'Why these stocks?')); var s = measured();
    methods.append(small(queueTab === 'anticipation' ? 'This separate watchlist uses SpicyStock’s disclosed trend-and-compression proxy. These stocks have not necessarily broken out.' : 'A match has risen at least 4%, traded more shares than the previous session, and traded at least 100,000 shares. It still needs chart review.'));
    methods.append(small('Order: recorded model score first when available, then how near the high the session closed, then symbol. This is a review order, not a win probability. Model scores are a SpicyStock overlay.'));
    methods.append(small('Coverage: ' + (s && s.scope ? number(s.scope.measured, 0) + ' of ' + number(s.scope.requested, 0) + ' requested names' : 'not yet recorded') + '. A curated subset, not the entire stock market.'));
    var source = node('a', 'tw-source', 'Read Stockbee’s published scan'); source.href = SOURCE; source.target = '_blank'; source.rel = 'noopener noreferrer'; methods.append(source); queue.append(methods);
    var own = node('div', 'tw-actions'); own.append(button('Plan a different symbol', 'trade-plan-manual', openBlankPlan)); queue.append(own); grid.append(queue);
    if (planVisible) grid.append(planForm()); panel.append(grid);
    var footer = node('div', 'tw-support-grid'); footer.append(accountCard(), learningCard()); panel.append(footer);
  }
  function paintCards(box) {
    if (!box) return; box.replaceChildren(); var s = measured(), all = rows(), filtered = all.filter(function (r) { return r.ticker.indexOf(query.trim().toUpperCase()) >= 0; });
    if (!s) { box.append(empty('The next scan starts here.', 'This saved session has no canonical 4% measurements yet. We will show recorded matches when the next scan publishes.')); return; }
    if (!filtered.length) { box.append(empty(query ? 'No matching symbol.' : queueTab === 'anticipation' ? 'No anticipation matches recorded.' : 'No 4% matches recorded.', query ? 'Try another symbol from this list.' : 'You do not need a trade every session. The next scan may bring a different list.')); return; }
    filtered.forEach(function (row, i) {
      var b = button('', null, function () { choose(row); }); b.className = 'tw-setup-card'; b.dataset.tradeSelect = row.ticker; b.setAttribute('aria-label', 'Review ' + row.ticker + ' setup'); b.setAttribute('aria-pressed', String(selected && selected.ticker === row.ticker));
      var h = node('div', 'tw-card-top'); h.append(node('span', 'tw-card-rank', String(i + 1).padStart(2, '0')), node('strong', 'tw-symbol', row.ticker), node('span', 'tw-change', pct(row.gain_pct))); b.append(h);
      var reasons = []; if (finite(row.volume_vs_previous)) reasons.push(row.volume_vs_previous.toFixed(2) + '× yesterday’s volume'); if (finite(row.close_position)) reasons.push('closed at ' + Math.round(row.close_position * 100) + '% of its range'); b.append(node('span', 'tw-card-reason', reasons.join(' · ') || 'Open the recorded measurements to review this setup.'));
      var c = scored(row.ticker), provenance = c && c.provenance && c.provenance.source;
      var tag = c && finite(c.score) ? 'Score ' + number(c.score) + '/10 · ' + (provenance === 'claude' ? 'AI review' : provenance === 'fallback' ? 'offline fallback' : 'source not recorded') : 'Scan match · no model score';
      b.append(node('span', 'tw-card-meta', tag), node('span', 'tw-card-bottom', money(row.close) + ' recorded close · ' + (row.date || s.date))); box.append(b);
    });
    var group = queueTab === 'anticipation' ? s.anticipation : s.scan;
    if (group && finite(group.matched) && group.matched > all.length) box.append(small(number(all.length, 0) + ' saved for review of ' + number(group.matched, 0) + ' measured matches.'));
  }
  function choose(row) {
    if (!row || typeof row.ticker !== 'string') return;
    selected = row; draft = { symbol: row.ticker, entry: '', stop: '', note: '' }; editingPlan = null; preview = null; planVisible = true; activeTab = 'today'; paintTabs(); paintBody(); focus('trade-entry'); announce('Reviewing ' + row.ticker + '. Enter intended prices, or explicitly load the dated reference.');
  }
  function openBlankPlan() { selected = null; draft = { symbol: '', entry: '', stop: '', note: '' }; editingPlan = null; preview = null; planVisible = true; activeTab = 'today'; paintTabs(); paintBody(); focus('trade-symbol'); }
  function field(label, id, attrs, value, change) {
    var wrap = node('div', 'tw-field'); var lab = node('label', '', label); lab.htmlFor = id;
    var input = node(attrs && attrs.type === 'textarea' ? 'textarea' : 'input'); input.id = id;
    Object.keys(attrs || {}).forEach(function (key) { if (!(key === 'type' && attrs[key] === 'textarea')) input.setAttribute(key, attrs[key]); });
    input.value = value === null || value === undefined ? '' : value; if (change) input.addEventListener('input', function () { change(input.value); }); wrap.append(lab, input); return wrap;
  }
  function selectField(label, id, options, value, change) {
    var wrap = node('div', 'tw-field'), lab = node('label', '', label), select = node('select'); lab.htmlFor = id; select.id = id;
    options.forEach(function (o) { var n = node('option', '', o[1]); n.value = o[0]; select.append(n); }); select.value = value || ''; select.addEventListener('change', function () { change(select.value); }); wrap.append(lab, select); return wrap;
  }
  function profileForm() {
    var form = node('form', 'tw-profile tw-surface'); form.id = 'trade-profile-form'; form.append(sectionHeading('YOUR LIMITS / SET ONCE, CHANGE ANY TIME', 'Your money. Your boundaries.', 'Choose the capital and risk budget you want this planner to use.'));
    var p = profile(), values = Object.assign({}, p), fields = node('div', 'tw-fields');
    [['Capital ($)', 'capital', 'trade-capital'], ['Risk per trade (%)', 'risk_percent', 'trade-risk'], ['Cash cap per position ($, optional)', 'cash_cap', 'trade-cash-cap'], ['Maximum open positions (optional)', 'max_positions', 'trade-max-positions']].forEach(function (v) { fields.append(field(v[0], v[2], { type: 'number', min: '0', step: v[1] === 'max_positions' ? '1' : 'any', inputmode: 'decimal' }, p[v[1]], function (text) { values[v[1]] = text.trim() === '' ? null : Number(text); })); }); form.append(fields);
    form.append(small('No risk percentage is preselected. Position sizing uses your limit and rounds down to whole shares. A stop is a plan; gaps and slippage can produce a larger loss.'));
    var actions = node('div', 'tw-actions'), save = node('button', 'tw-button tw-button--primary', 'Save my limits'); save.type = 'submit'; save.id = 'trade-save-profile'; actions.append(save); if (profileReady()) actions.append(button('Close', null, function () { profileOpen = false; paintBody(); })); form.append(actions);
    form.addEventListener('submit', function (e) { e.preventDefault(); if (mutate(engine().setProfile(values), 'Trading limits saved.')) { profileOpen = false; preview = null; paintStatus(); paintBody(); } }); return form;
  }
  function spark(row) {
    var bars = list(row && row.series).filter(function (b) { return b && finite(b.open) && finite(b.close) && finite(b.high) && finite(b.low) && b.low > 0 && b.high >= Math.max(b.open, b.close) && b.low <= Math.min(b.open, b.close); }).slice(-24);
    if (bars.length < 2) return small('Chart history was not saved for this setup.');
    var box = node('figure', 'tw-chart'), svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('viewBox', '0 0 480 160'); svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', row.ticker + ' recorded daily candles, ' + bars[0].date + ' through ' + bars[bars.length - 1].date + '. Historical prices, not a live quote.');
    var low = Math.min.apply(null, bars.map(function (b) { return b.low; })), high = Math.max.apply(null, bars.map(function (b) { return b.high; })), span = high - low || 1;
    var y = function (price) { return 144 - (price - low) / span * 128; }, width = 456 / bars.length;
    function shape(tag, attrs) { var n = document.createElementNS(svg.namespaceURI, tag); Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); }); svg.append(n); }
    [16, 80, 144].forEach(function (v) { shape('line', { x1: 0, x2: 480, y1: v, y2: v, 'class': 'tw-chart-grid' }); });
    bars.forEach(function (b, i) { var x = 12 + width * (i + .5), cls = b.close >= b.open ? 'tw-candle-up' : 'tw-candle-down'; shape('line', { x1: x, x2: x, y1: y(b.high), y2: y(b.low), 'class': cls + ' tw-candle-wick' }); shape('rect', { x: x - width * .28, y: Math.min(y(b.open), y(b.close)), width: width * .56, height: Math.max(1.4, Math.abs(y(b.close) - y(b.open))), 'class': cls + ' tw-candle-body' }); });
    box.append(svg, node('figcaption', '', bars[0].date + ' — ' + bars[bars.length - 1].date + ' · ' + money(low) + '–' + money(high))); return box;
  }
  function planForm() {
    var form = node('section', 'tw-plan tw-surface'); form.id = 'trade-plan'; form.setAttribute('aria-labelledby', 'trade-plan-title');
    var title = sectionHeading('02 / PLAN', draft.symbol ? 'Make ' + draft.symbol + ' a plan.' : 'Put a price on your risk.', 'A saved plan is not an order.'); title.querySelector('h3').id = 'trade-plan-title'; form.append(title);
    if (selected) {
      form.append(spark(selected)); var ref = node('div', 'tw-reference'); ref.id = 'trade-reference'; ref.append(small('Recorded ' + (selected.date || 'date unavailable') + ' · close ' + money(selected.close) + ' · low ' + money(selected.low)));
      if (safeDate(selected.date) && finite(selected.close) && finite(selected.low) && selected.low > 0 && selected.low < selected.close) ref.append(button('Use recorded close & low', 'trade-use-reference', function () { draft.entry = String(selected.close); draft.stop = String(selected.low); preview = null; paintBody(); focus('trade-entry'); announce('Historical reference loaded from ' + selected.date + '. Verify both prices before making a trade.'); }));
      form.append(ref);
      var explain = node('details', 'tw-details'); explain.append(node('summary', '', 'What to check on the chart')); explain.append(small('Look for a young, orderly move out of a compact base; a quiet preceding day; and a close near the high. Review consecutive up days and prior failed breaks. The numeric scan alone cannot confirm this pattern.'));
      var c = scored(selected.ticker); if (c && typeof c.reason === 'string') explain.append(small('Recorded model review: ' + c.reason)); form.append(explain);
    }
    if (!profileReady()) { form.append(empty('Set your limits first.', 'Your position size comes from your chosen capital and risk budget.')); form.append(button('Set my limits', 'trade-plan-profile', showProfile, true)); }
    else { var p = profile(); var limits = node('div', 'tw-plan-limits'); limits.append(small(money(p.capital) + ' capital · ' + number(p.risk_percent) + '% risk per trade'), button('Edit limits', 'trade-edit-profile', showProfile)); form.append(limits); }
    var fields = node('div', 'tw-fields'); [['Symbol', 'symbol', 'trade-symbol', { type: 'text', maxlength: '15', autocomplete: 'off', autocapitalize: 'characters' }], ['Intended entry limit ($)', 'entry', 'trade-entry', { type: 'number', min: '0', step: 'any', inputmode: 'decimal' }], ['Initial stop ($)', 'stop', 'trade-stop', { type: 'number', min: '0', step: 'any', inputmode: 'decimal' }]].forEach(function (v) { fields.append(field(v[0], v[2], v[3], draft[v[1]], function (value) { draft[v[1]] = v[1] === 'symbol' ? value.toUpperCase() : value; preview = null; paintCalculation(); })); }); form.append(fields);
    var result = node('div', 'tw-calculation'); result.id = 'trade-calculation'; result.setAttribute('aria-live', 'polite'); form.append(result);
    var actions = node('div', 'tw-actions'); actions.append(button(editingPlan ? 'Update saved plan' : 'Save plan', 'trade-save-plan', savePlan, true));
    if (broker.connected) { var pb = button('Preview broker order', 'trade-preview-order', previewOrder); pb.disabled = busy || broker.state === 'reconciliation_needed' || !!(portfolio && portfolio.clock && portfolio.clock.is_open === false); actions.append(pb); }
    form.append(actions); var previewBox = node('div'); previewBox.id = 'trade-order-preview'; form.append(previewBox);
    var alternatives = node('details', 'tw-details'); alternatives.append(node('summary', '', 'Already bought this stock?')); alternatives.append(small('Record the actual execution from your stock account. The intended entry and share count are kept separate.')); alternatives.append(button('Record actual fill', 'trade-plan-record-fill', function () { openFill(draft.symbol, 'buy', editingPlan); })); form.append(alternatives);
    window.setTimeout(function () { if (form.isConnected) { paintCalculation(); paintPreview(); } }, 0); return form;
  }
  function paintCalculation() {
    var target = host.querySelector('#trade-calculation'); if (!target) return; target.replaceChildren(); var c = calc();
    if (!profileReady()) { target.append(small('Choose your limits to calculate shares.')); } else if (!c.ok) target.append(small(c.error || 'Enter your intended entry and initial stop.')); else {
      var count = node('p', 'tw-share-count'); count.id = 'trade-plan-qty'; count.append(node('strong', '', number(c.qty, 0)), document.createTextNode(' shares')); target.append(count);
      var metrics = node('dl', 'tw-result-metrics'); metrics.append(metric('Planned loss at stop', money(c.planned_risk)), metric('Position cost', money(c.position_cost))); target.append(metrics); if (c.qty === 0) target.append(small('Your limits do not allow a whole share.'));
      var max = profile().max_positions, d = derived(); if (finite(max) && max > 0 && list(d.positions).length >= max) target.append(node('p', 'tw-warning', 'Your recorded position count has reached your chosen maximum. Review positions before adding another.'));
    }
    var save = host.querySelector('#trade-save-plan'), pb = host.querySelector('#trade-preview-order'); if (save) save.disabled = !c.ok || !c.qty || !/^[A-Z][A-Z0-9.-]{0,14}$/.test(draft.symbol); if (pb) pb.disabled = busy || !c.ok || !c.qty || !/^[A-Z][A-Z0-9.-]{0,14}$/.test(draft.symbol) || broker.state === 'reconciliation_needed' || !!(portfolio && portfolio.clock && portfolio.clock.is_open === false);
    paintPreview();
  }
  function savePlan() {
    var c = calc(); if (!c.ok || !c.qty) { announce(c.error || 'A plan needs at least one whole share.'); return; }
    var p = profile(), snapshotDate = selected && selected.date || data && data.run && data.run.date;
    if (!safeDate(snapshotDate)) { announce('A dated scan is required to link this plan to its evidence.'); return; }
    var result = engine().savePlan({ id: editingPlan || undefined, symbol: draft.symbol, snapshot_date: snapshotDate, entry: Number(draft.entry), stop: Number(draft.stop), risk_percent: p.risk_percent, capital: p.capital, cash_cap: p.cash_cap, qty: c.qty, status: 'prepared' });
    if (mutate(result, 'Plan saved. No order has been placed.')) { editingPlan = result.plan && result.plan.id || result.id || (result.state && list(result.state.plans).find(function (r) { return r.symbol === draft.symbol && r.entry === Number(draft.entry) && r.stop === Number(draft.stop); }) || {}).id || editingPlan; paintStatus(); paintBody(); }
  }
  function accountCard() {
    var box = node('section', 'tw-account tw-surface'); box.append(sectionHeading('ACCOUNT', broker.connected ? (broker.mode === 'live' ? 'Live account connected.' : 'Practice with paper money.') : 'Keep the whole journey here.', broker.connected ? 'New entries require a current quote and a fresh, explicit order confirmation.' : 'Prepare a plan, place the trade in your stock account, then record or import the actual fill here.'));
    var badge = node('p', 'tw-account-badge', broker.connected ? (broker.mode === 'live' ? 'Live' : 'Paper') + ' connected' : 'Not connected'); badge.id = 'trade-account-status'; box.append(badge);
    if (brokerError) box.append(node('p', 'tw-warning', brokerError));
    if (broker.connected && portfolio) { var dl = node('dl', 'tw-account-metrics'); dl.append(metric('Broker cash', money(portfolio.account && portfolio.account.cash)), metric('Account equity', money(portfolio.account && portfolio.account.equity))); box.append(dl, small('Broker snapshot ' + time(portfolio.as_of))); }
    var actions = node('div', 'tw-actions');
    if (broker.connected) actions.append(button('Refresh account', 'trade-refresh-account', function () { refreshBroker(true); }));
    else if (broker.configured && window.SCTradeBridge) actions.append(button('Connect paper account', 'trade-connect-paper', function () { connect('paper'); }));
    else box.append(small('Broker connection setup is required for orders in this page. You can prepare plans and track fills here now.'));
    if (broker.configured && broker.live_enabled && !broker.connected) { var live = node('details', 'tw-details'); live.append(node('summary', '', 'Use a live account')); live.append(small('Live orders use real money. Every order still needs your explicit review and submission.')); live.append(button('Connect live account', 'trade-connect-live', function () { connect('live'); })); box.append(live); }
    if (actions.childNodes.length) box.append(actions);
    var settings = node('details', 'tw-details'); settings.append(node('summary', '', 'Limits & connection')); settings.append(button(profileReady() ? 'Edit my trading limits' : 'Set my trading limits', 'trade-account-profile', showProfile));
    if (broker.connected) settings.append(button('Disconnect account', 'trade-disconnect', disconnect)); box.append(settings); return box;
  }
  function learningCard() {
    var learning = data && (data.learning || data.run && data.run.learning), box = node('section', 'tw-learning tw-surface');
    box.append(sectionHeading('THE FEEDBACK LOOP', 'Learn from the record.', 'Every completed setup adds evidence. Changes earn their place through later, unseen sessions.'));
    var title = 'Collecting completed setups'; var version = learning && learning.model && learning.model.version;
    if (learning && typeof learning.status === 'string') title = learning.status === 'collecting' || learning.status === 'insufficient_data' ? 'Collecting completed setups' : learning.status === 'shadow' || learning.status === 'shadow_evaluation' ? 'Comparing a challenger in shadow' : learning.status === 'qualified' ? 'Challenger passed the research gate · still in shadow' : 'Reviewing recorded evidence';
    box.append(node('p', 'tw-learning-state', title)); if (version) box.append(small('Recorded model: ' + String(version)));
    if (learning && learning.counts && finite(learning.counts.matured)) box.append(small(number(learning.counts.matured, 0) + ' completed setups · ' + number(learning.counts.validation, 0) + ' validation observations'));
    box.append(small('No automatic strategy promotion. Paper setup returns and your actual account fills remain separate.'));
    var details = node('details', 'tw-details'); details.append(node('summary', '', 'How improvement stays accountable')); details.append(small('Versioned rules, dated predictions and forward outcomes make changes reviewable. A model score is a research ranking, not a probability of profit.'));
    if (learning && typeof learning.reason === 'string') details.append(small(learning.reason));
    if (learning && learning.requirements) { var needs = learning.requirements; details.append(small('Research gate: ' + number(needs.train_setups, 0) + ' training setups, ' + number(needs.validation_setups, 0) + ' validation setups and ' + number(needs.validation_dates, 0) + ' validation dates. Labels must have been available before the model was fitted.')); }
    if (learning && learning.validation && finite(learning.validation.mae_improvement_pct)) details.append(small('Validation error improvement vs baseline: ' + pct(learning.validation.mae_improvement_pct) + '. Hypothetical next-open to fifth-session-close outcomes; the recorded cost proxy is ' + number(learning.target && learning.target.round_trip_cost_bps, 0) + ' basis points round trip.'));
    box.append(details); return box;
  }
  function paintPositions() {
    panel.append(sectionHeading('03 / TRACK', 'Know what you actually own.', 'Filled executions create positions. Saved plans and accepted orders do not.'));
    var actions = node('div', 'tw-actions'); actions.append(button('Record actual fill', 'trade-record-fill', function () { openFill('', 'buy'); }, true), button('Import fills', 'trade-import-open', function () { importOpen = !importOpen; manualOpen = false; paintBody(); })); panel.append(actions);
    if (manualOpen) panel.append(fillForm()); if (importOpen) panel.append(importForm());
    var d = derived(), s = state(), brokerPositions = list(d.broker_positions);
    if (list(d.reconciliation).length) { var warnings = node('section', 'tw-reconciliation'); warnings.id = 'trade-reconciliation'; warnings.append(node('h4', '', 'Reconcile before relying on totals.')); list(d.reconciliation).forEach(function (r) { warnings.append(small((r.symbol ? r.symbol + ' · ' : '') + (r.environment === 'paper' ? 'Paper · ' : 'Live · ') + r.reason)); }); panel.append(warnings); }
    if (brokerError) panel.append(node('p', 'tw-warning', brokerError + ' Broker values below are the last saved snapshot.'));
    var pending = list(portfolio && portfolio.pending_orders); if (pending.length || list(portfolio && portfolio.unresolved).length || broker.state === 'reconciliation_needed') {
      var orderBox = node('section', 'tw-order-list tw-surface'); orderBox.id = 'trade-pending-orders'; orderBox.append(node('h4', '', 'Orders in progress'));
      pending.forEach(function (o) { var item = node('div', 'tw-pending-order'); item.append(node('strong', '', (o.symbol || 'Order') + ' · ' + String(o.status || 'status unknown').replace(/_/g, ' ')), small(number(Number(o.filled_qty || 0)) + ' filled of ' + number(Number(o.qty)) + ' shares'));
        if (o.status === 'partially_filled') item.append(node('p', 'tw-warning', 'Partial fill. The attached stop may not activate until the entry fills completely.'));
        var legs = list(o.legs); if (legs.length) legs.forEach(function (leg) { item.append(small('Attached ' + (leg.type || 'exit') + ' · ' + String(leg.status || 'status unknown').replace(/_/g, ' '))); }); else item.append(small('Attached stop status is not confirmed in this order response.'));
        orderBox.append(item);
      });
      if (broker.state === 'reconciliation_needed' || list(portfolio && portfolio.unresolved).length) orderBox.append(node('p', 'tw-warning', 'An order result needs reconciliation. Refresh account activity before attempting another order.'));
      if (broker.connected) orderBox.append(button('Reconcile account', 'trade-reconcile-account', function () { refreshBroker(true); })); panel.append(orderBox);
    }
    var positions = node('div', 'tw-position-list'); positions.id = 'trade-positions-list';
    brokerPositions.forEach(function (p) {
      var card = node('article', 'tw-position-card'); card.dataset.tradePosition = p.symbol; card.append(node('p', 'tw-eyebrow', (p.environment === 'paper' ? 'PAPER' : 'LIVE') + ' / BROKER HOLDING'), node('h4', '', p.symbol));
      var dl = node('dl', 'tw-position-metrics'); dl.append(metric('Broker shares', number(p.qty)), metric('Average entry', money(p.avg_entry_price)), metric('Broker market value', money(p.market_value)), metric('Snapshot price', money(p.current_price))); card.append(dl, small('Account ' + accountLabel(p.account_id) + ' · snapshot ' + time(p.as_of)));
      card.append(small('Review active exit orders at your broker. A recorded stop price does not confirm a working stop order.')); positions.append(card);
    });
    list(d.positions).filter(function (p) { return p.source !== 'alpaca' || !brokerPositions.some(function (b) { return b.symbol === p.symbol && b.account_id === p.account_id && b.environment === p.environment; }); }).forEach(function (p) {
      var card = node('article', 'tw-position-card'); card.dataset.tradePosition = p.symbol; card.append(node('p', 'tw-eyebrow', (p.environment === 'paper' ? 'PAPER' : 'LIVE') + ' / ' + (p.source === 'manual' ? 'CONFIRMED BY YOU' : 'RECORDED EXECUTIONS')), node('h4', '', p.symbol));
      var dl = node('dl', 'tw-position-metrics'); dl.append(metric('Recorded shares', number(p.qty)), metric('Average entry', money(p.average_entry)), metric('Original planned risk', p.uncertain ? 'Needs reconciliation' : money(p.initial_risk))); card.append(dl);
      card.append(small('Opened ' + time(p.opened_at) + ' · ' + recordedSessions(p.opened_at) + ' recorded sessions since entry.'));
      if (p.uncertain) card.append(node('p', 'tw-warning', 'This record needs reconciliation before you rely on its exposure or return.'));
      else card.append(small('Entry cost only. No current market price or working stop is implied.'));
      if (p.source === 'manual') card.append(button('Record a sell fill', null, function () { openFill(p.symbol, 'sell', null, p.environment); })); positions.append(card);
    });
    if (!positions.childNodes.length) positions.append(empty('Your first fill belongs here.', 'After a trade executes, record the actual shares, price and time, or import its execution record. Paper trading stays separate from live money.'));
    panel.append(positions);
    var plans = node('details', 'tw-saved-plans tw-details'); plans.open = !positions.querySelector('[data-trade-position]'); plans.id = 'trade-saved-plans'; plans.append(node('summary', '', 'Saved plans · ' + list(s.plans).filter(function (p) { return p.status !== 'canceled'; }).length));
    list(s.plans).slice().reverse().forEach(function (p) { var card = node('div', 'tw-saved-plan'); card.dataset.tradePlanId = p.id; card.append(node('strong', '', p.symbol + ' · ' + p.status), small(number(p.qty, 0) + ' intended shares · entry ' + money(p.entry) + ' · stop ' + money(p.stop)), small('Evidence session ' + p.snapshot_date + '. ' + (p.status === 'submitted' ? 'Check actual fills above.' : 'This is not a position.')));
      var a = node('div', 'tw-actions'); if (['draft', 'prepared'].indexOf(p.status) >= 0) { a.append(button('Open plan', null, function () { editPlan(p); }), button('Record actual fill', null, function () { openFill(p.symbol, 'buy', p.id); }));
        var cancel = node('details', 'tw-inline-confirm'); cancel.append(node('summary', '', 'Cancel plan')); cancel.append(small('Keep the record and mark this unsubmitted plan as canceled?')); cancel.append(button('Confirm cancel plan', null, function () { if (mutate(engine().savePlan(Object.assign({}, p, { status: 'canceled' })), 'Plan canceled. Its record is retained.')) paintBody(); })); card.append(cancel); }
      if (a.childNodes.length) card.append(a); plans.append(card);
    });
    if (!s.plans.length) plans.append(small('Plans you explicitly save will appear here.')); panel.append(plans);
  }
  function accountLabel(id) { return typeof id === 'string' && id !== 'local' ? '…' + id.slice(-6) : 'manual record'; }
  function recordedSessions(stamp) { var day = typeof stamp === 'string' ? stamp.slice(0, 10) : ''; var dates = list(data && data.runs).filter(function (r) { return r && r.type === 'evening' && r.dry_run !== true && r.fixture !== true && safeDate(r.date) && r.date > day; }).map(function (r) { return r.date; }); var run = data && data.run; if (run && run.type === 'evening' && run.dry_run !== true && run.fixture !== true && safeDate(run.date) && run.date > day) dates.push(run.date); return new Set(dates).size; }
  function editPlan(p) { selected = null; editingPlan = p.id; draft = { symbol: p.symbol, entry: String(p.entry), stop: String(p.stop), note: '' }; planVisible = true; preview = null; activeTab = 'today'; paintTabs(); paintBody(); focus('trade-entry'); }
  function openFill(symbol, side, planId, environment) { fillDraft = { symbol: symbol || '', side: side || 'buy', environment: environment || '', qty: '', price: '', executed_at: '', fees: '', initial_stop: '', execution_id: '', plan_id: planId || null, confirmed: false }; manualOpen = true; importOpen = false; activeTab = 'positions'; paintTabs(); paintBody(); focus(symbol ? 'trade-fill-qty' : 'trade-fill-symbol'); }
  function fillForm() {
    var form = node('form', 'tw-fill-form tw-surface'); form.id = 'trade-fill-form'; form.append(sectionHeading('ACTUAL EXECUTION', 'What filled in your account?', 'Enter the broker’s completed execution. Keep intended prices in the plan.'));
    if (fillDraft.plan_id) { var p = list(state().plans).find(function (r) { return r.id === fillDraft.plan_id; }); if (p) form.append(small('Linked plan: ' + number(p.qty, 0) + ' intended shares at ' + money(p.entry) + ', initial planned stop ' + money(p.stop) + '. Confirm the actual values below.')); }
    var fields = node('div', 'tw-fields'); fields.append(field('Symbol', 'trade-fill-symbol', { type: 'text', maxlength: '15', autocomplete: 'off', required: '' }, fillDraft.symbol, function (v) { fillDraft.symbol = v.toUpperCase(); }));
    fields.append(selectField('Execution side', 'trade-fill-side', [['buy', 'Buy'], ['sell', 'Sell']], fillDraft.side, function (v) { fillDraft.side = v; }));
    fields.append(selectField('Account environment', 'trade-fill-environment', [['', 'Choose your account'], ['live', 'Live · real money'], ['paper', 'Paper · simulated money']], fillDraft.environment, function (v) { fillDraft.environment = v; }));
    [['Actual shares', 'qty', 'trade-fill-qty'], ['Actual fill price ($)', 'price', 'trade-fill-price'], ['Fees ($, leave blank if unknown)', 'fees', 'trade-fill-fees'], ['Original stop ($, optional for buy)', 'initial_stop', 'trade-fill-stop']].forEach(function (v) { fields.append(field(v[0], v[2], { type: 'number', min: '0', step: 'any', inputmode: 'decimal' }, fillDraft[v[1]], function (x) { fillDraft[v[1]] = x; })); });
    fields.append(field('Execution time (your local time)', 'trade-fill-time', { type: 'datetime-local', required: '', step: '1' }, fillDraft.executed_at, function (v) { fillDraft.executed_at = v; }));
    fields.append(field('Execution ID (optional)', 'trade-fill-execution', { type: 'text', maxlength: '180', autocomplete: 'off' }, fillDraft.execution_id, function (v) { fillDraft.execution_id = v; })); form.append(fields);
    var confirmation = node('label', 'tw-checkbox'); var check = node('input'); check.type = 'checkbox'; check.id = 'trade-fill-confirm'; check.checked = fillDraft.confirmed; check.required = true; check.addEventListener('change', function () { fillDraft.confirmed = check.checked; }); confirmation.append(check, node('span', '', 'I checked the actual symbol, side, shares, fill price, execution time and account environment.')); form.append(confirmation);
    var actions = node('div', 'tw-actions'), save = node('button', 'tw-button tw-button--primary', 'Record confirmed fill'); save.type = 'submit'; save.id = 'trade-save-fill'; actions.append(save, button('Cancel', 'trade-cancel-fill', function () { manualOpen = false; paintBody(); })); form.append(actions);
    form.addEventListener('submit', function (e) {
      e.preventDefault(); var stamp = new Date(fillDraft.executed_at); if (!Number.isFinite(stamp.getTime())) { announce('Enter the actual execution date and local time.'); return; }
      var values = { symbol: fillDraft.symbol, side: fillDraft.side, qty: fillDraft.qty, price: fillDraft.price, executed_at: stamp.toISOString(), initial_stop: fillDraft.initial_stop === '' ? null : Number(fillDraft.initial_stop), fees: fillDraft.fees === '' ? null : Number(fillDraft.fees), source: 'manual', environment: fillDraft.environment, account_id: 'local', plan_id: fillDraft.plan_id, confirmed: fillDraft.confirmed };
      if (fillDraft.execution_id.trim()) values.execution_id = fillDraft.execution_id.trim();
      if (mutate(engine().recordFill(values), 'Actual fill recorded. Positions now reflect the execution.')) { manualOpen = false; fillDraft = {}; paintStatus(); paintBody(); focus('trade-tab-positions'); }
    }); return form;
  }
  function download(name, contents, mime) { var url = URL.createObjectURL(new Blob([contents], { type: mime })); var a = node('a'); a.href = url; a.download = name; document.body.append(a); a.click(); a.remove(); window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000); }
  function importForm() {
    var box = node('section', 'tw-import tw-surface'); box.id = 'trade-import'; box.append(sectionHeading('BRING YOUR FILLS', 'Review first. Import once.', 'Use the execution CSV template or a SpicyStock JSON backup. Duplicate execution IDs are checked before anything changes.'));
    var wrap = node('div', 'tw-field'), label = node('label', '', 'Choose a CSV or JSON file'), file = node('input'); file.id = 'trade-import-file'; file.type = 'file'; file.accept = '.csv,.json,text/csv,application/json'; label.htmlFor = file.id; wrap.append(label, file); box.append(wrap);
    file.addEventListener('change', async function () { var selectedFile = file.files && file.files[0]; if (!selectedFile) return; if (selectedFile.size > 8000000) { announce('Choose a file smaller than 8 MB.'); return; } try { var text = await selectedFile.text(); importPreview = engine().previewImport(text, /\.csv$/i.test(selectedFile.name) ? 'csv' : 'json'); paintImportPreview(); } catch (_) { announce('This file could not be read.'); } });
    var actions = node('div', 'tw-actions'); actions.append(button('Download CSV template', 'trade-import-template', function () { download('spicystock-executions-template.csv', engine().csvColumns.join(',') + '\r\n', 'text/csv'); }), button('Preview previous journal', 'trade-import-legacy', function () { importPreview = engine().previewLegacy(); paintImportPreview(); })); box.append(actions);
    var previewBox = node('div'); previewBox.id = 'trade-import-preview'; previewBox.setAttribute('aria-live', 'polite'); box.append(previewBox); window.setTimeout(function () { if (box.isConnected) paintImportPreview(); }, 0); return box;
  }
  function paintImportPreview() {
    var box = host.querySelector('#trade-import-preview'); if (!box) return; box.replaceChildren(); if (!importPreview) return;
    var p = importPreview, counts = p.counts || {}; box.append(node('h4', '', p.ok ? 'Ready for your confirmation.' : 'Resolve these rows first.'), small(number(counts.fills || 0, 0) + ' new fills · ' + number(counts.plans || 0, 0) + ' plans · ' + number(counts.duplicates || 0, 0) + ' duplicate executions skipped.'));
    list(p.errors).forEach(function (e) { box.append(node('p', 'tw-warning', e)); }); list(p.warnings).forEach(function (e) { box.append(small(e)); });
    var items = node('ul', 'tw-import-rows'); list(p.rows).slice(0, 8).forEach(function (r) { items.append(node('li', '', (r.environment === 'paper' ? 'Paper' : 'Live') + ' · ' + r.symbol + ' · ' + r.side + ' ' + number(r.qty) + ' at ' + money(r.price) + ' · ' + time(r.executed_at))); }); box.append(items);
    if (list(p.rows).length > 8) box.append(small('Showing the first 8 of ' + p.rows.length + ' execution rows.'));
    if (p.ok) box.append(button('Confirm import', 'trade-import-confirm', function () { var result = engine().commitImport(importPreview); if (mutate(result, 'Import complete. ' + (result.added || 0) + ' fills added; ' + (result.duplicates || 0) + ' duplicates skipped.')) { importPreview = null; importOpen = false; paintStatus(); paintBody(); } }, true));
  }
  function paintActivity() {
    var d = derived(), s = state(); panel.append(sectionHeading('THE RECORD', 'A receipt for every decision.', 'Plans, executions and corrections retain their provenance. Performance uses matched actual fills.'));
    var actions = node('div', 'tw-actions'); actions.append(button('Export full backup', 'trade-export-json', function () { download('spicystock-trade-record.json', engine().exportJSON(), 'application/json'); }), button('Export execution CSV', 'trade-export-csv', function () { download('spicystock-executions.csv', engine().exportCSV(), 'text/csv'); })); panel.append(actions);
    var totals = node('div', 'tw-outcomes'); totals.id = 'trade-performance'; ['live', 'paper'].forEach(function (env) { var values = d.totals[env], count = list(d.closed).filter(function (r) { return r.environment === env; }).length; var box = node('section', 'tw-outcome tw-surface'); box.append(node('p', 'tw-eyebrow', env === 'live' ? 'LIVE MONEY / MATCHED EXITS' : 'PAPER MONEY / MATCHED EXITS')); var stats = node('dl', 'tw-result-metrics'); stats.append(metric('Realized P/L before fees', count ? money(values.realized_gross) : 'No matched exits'), metric('Realized P/L after fees', count ? money(values.realized_net) : 'No matched exits')); box.append(stats, small(count + ' matched exit lots · partial exits match earlier buys first. Unknown fees or missing history keep affected totals unavailable.')); totals.append(box); }); panel.append(totals);
    var exits = node('div', 'tw-exits'); exits.id = 'trade-closed-exits'; list(d.closed).slice().reverse().slice(0, 40).forEach(function (r) { var row = node('article', 'tw-exit'); row.append(node('strong', '', r.symbol + ' · ' + (r.environment === 'paper' ? 'Paper' : 'Live') + ' matched exit'), small(number(r.qty) + ' shares · ' + money(r.entry) + ' → ' + money(r.exit)), node('p', 'tw-exit-result', money(r.profit) + ' gross · ' + (finite(r.r) ? r.r.toFixed(2) + 'R on original risk' : 'R unavailable')), small(time(r.exited_at))); exits.append(row); }); panel.append(exits);
    var ledger = node('div', 'tw-execution-list'); ledger.id = 'trade-execution-list'; ledger.append(node('h4', '', 'Execution history'));
    var voids = new Set(list(s.voids).map(function (v) { return v.fill_id; }));
    list(s.fills).slice().sort(function (a, b) { return String(b.executed_at).localeCompare(String(a.executed_at)); }).slice(0, 100).forEach(function (f) {
      var row = node('article', 'tw-execution'); row.dataset.tradeExecution = f.execution_id; var corrected = voids.has(f.id); row.append(node('p', 'tw-eyebrow', (f.environment === 'paper' ? 'PAPER' : 'LIVE') + ' / ' + (f.source === 'manual' ? 'CONFIRMED BY YOU' : 'BROKER EXECUTION') + (corrected ? ' / CORRECTED' : '')));
      row.append(node('strong', '', f.symbol + ' · ' + f.side + ' ' + number(f.qty) + ' at ' + money(f.price)), small(time(f.executed_at) + ' · execution ' + f.execution_id));
      if (f.source === 'manual' && !corrected) { var details = node('details', 'tw-inline-confirm'); details.append(node('summary', '', 'Correct this record')); details.append(small('The original stays in your history and is excluded from totals. Record a replacement afterward if needed.')); var reason = field('Why is this execution incorrect?', 'trade-correct-' + f.id.replace(/[^a-zA-Z0-9-]/g, '').slice(-60), { type: 'text', maxlength: '500' }, '', null); details.append(reason); details.append(button('Confirm correction', null, function () { if (mutate(engine().voidFill(f.id, { confirmed: true, reason: reason.querySelector('input').value }), 'Execution marked as corrected. The original record is retained.')) { paintStatus(); paintBody(); } })); row.append(details); }
      ledger.append(row);
    });
    if (!s.fills.length) ledger.append(empty('An empty record is an honest start.', 'Confirmed fills will appear here with their account environment, source and execution time. No hypothetical gains are added to your results.'));
    if (s.fills.length > 100) ledger.append(small('Showing the latest 100 executions. Export your full backup for the complete record.')); panel.append(ledger);
  }
  function bridgeFailure(result) { return result && result.error && result.error.message || 'The broker service could not complete this request.'; }
  async function connect(mode) { if (!window.SCTradeBridge || busy) return; busy = true; try { var r = await window.SCTradeBridge.connect(mode); if (!r.ok) announce(bridgeFailure(r)); } finally { busy = false; } }
  async function disconnect() { if (!window.SCTradeBridge || busy) return; busy = true; try { var r = await window.SCTradeBridge.disconnect(); if (!r.ok) { announce(bridgeFailure(r)); return; } refreshSerial++; broker = { state: 'not_connected', configured: true, connected: false }; portfolio = null; preview = null; clearTimeout(timer); announce('Broker disconnected. Recorded executions remain in this browser.'); paintStatus(); paintBody(); } finally { busy = false; } }
  async function startBridge() {
    if (bridgeReady || bridgeLoading || !window.SCTradeBridge) return; bridgeLoading = true;
    try { var config = await window.SCTradeBridge.load(); if (!config.ok) { brokerError = bridgeFailure(config); return; } bridgeReady = true; if (!config.data.enabled) return; await refreshBroker(false); }
    finally { bridgeLoading = false; paintStatus(); if (activeTab === 'today' && !planVisible && !profileOpen) paintBody(); }
  }
  async function refreshBroker(explicit) {
    if (!window.SCTradeBridge || navigator.onLine === false || document.hidden || busy) return;
    var serial = ++refreshSerial; clearTimeout(timer);
    try {
      var status = await window.SCTradeBridge.status(); if (serial !== refreshSerial) return;
      if (!status.ok) { brokerError = bridgeFailure(status); preview = null; if (explicit) announce(brokerError); return; }
      broker = status.data; if (!broker.connected) { portfolio = null; brokerError = ''; preview = null; return; }
      var result = await window.SCTradeBridge.portfolio(); if (serial !== refreshSerial) return;
      if (!result.ok) { brokerError = bridgeFailure(result); preview = null; if (explicit) announce(brokerError); return; }
      var ingested = engine().ingestBroker(result.data); if (!ingested.ok) { brokerError = ingested.error; preview = null; if (explicit) announce(brokerError); return; }
      portfolio = result.data; brokerError = ''; if (portfolio.state === 'reconciliation_needed') broker.state = 'reconciliation_needed';
      if (explicit) { announce('Account refreshed. Only confirmed executions were added to the record.'); paintBody(); }
    } catch (_) { brokerError = 'Account refresh failed. Your last view may be out of date.'; preview = null; }
    finally { if (serial === refreshSerial) { paintStatus(); if (activeTab === 'positions' && !manualOpen && !importOpen) paintBody(); paintCalculation(); if (broker.connected && !document.hidden) timer = window.setTimeout(function () { refreshBroker(false); }, 30000); } }
  }
  async function previewOrder() {
    if (busy || !broker.connected || brokerError || navigator.onLine === false) { announce(brokerError || 'Connect and refresh your broker account before previewing an order.'); return; }
    var c = calc(), p = profile(); if (!c.ok || !c.qty) { announce(c.error || 'Enter a valid plan first.'); return; }
    var fingerprint = JSON.stringify([draft.symbol, draft.entry, draft.stop, p.capital, p.risk_percent, p.cash_cap]);
    busy = true; preview = null; paintCalculation(); announce('Checking the current quote, account cash and order limits…');
    try { var r = await window.SCTradeBridge.preview({ symbol: draft.symbol, limit_price: Number(draft.entry), stop_price: Number(draft.stop), risk_percent: p.risk_percent, cash_cap: p.cash_cap === null ? undefined : p.cash_cap, max_positions: p.max_positions === null ? undefined : p.max_positions });
      if (!r.ok) { announce(bridgeFailure(r)); return; }
      var v = r.data, currentProfile = profile();
      if (fingerprint !== JSON.stringify([draft.symbol, draft.entry, draft.stop, currentProfile.capital, currentProfile.risk_percent, currentProfile.cash_cap])) { announce('The plan changed while the preview was loading. Request a new preview.'); return; }
      if (!v || typeof v.preview_id !== 'string' || v.mode !== broker.mode || v.symbol !== draft.symbol || v.account_id && (!portfolio || !portfolio.account || v.account_id !== portfolio.account.id) || !Number.isSafeInteger(v.qty) || v.qty <= 0 || !finite(v.limit_price) || v.limit_price <= 0 || !finite(v.stop_price) || v.stop_price <= 0 || v.stop_price >= v.limit_price || !Number.isFinite(Date.parse(v.expires_at)) || Date.parse(v.expires_at) <= Date.now() || !v.quote || v.quote.fresh !== true) { announce('This order preview could not be verified. Refresh the account and request a new preview.'); return; }
      preview = { data: v, submitted: false, receipt: null, fingerprint: fingerprint }; announce('Order preview ready. Check the account, prices and share count before submitting.');
    } catch (_) { announce('Order preview failed. No order was submitted.'); }
    finally { busy = false; paintCalculation(); focus('trade-submit-order'); }
  }
  function paintPreview() {
    var box = host.querySelector('#trade-order-preview'); if (!box) return; box.replaceChildren(); if (!preview) return; var v = preview.data;
    var p = profile(), fingerprint = JSON.stringify([draft.symbol, draft.entry, draft.stop, p.capital, p.risk_percent, p.cash_cap]);
    if (!preview.submitted && fingerprint !== preview.fingerprint) { preview = null; return; }
    var card = node('section', 'tw-order-confirm'); card.append(node('p', 'tw-eyebrow', v.mode === 'live' ? 'REAL MONEY / FINAL CONFIRMATION' : 'PAPER MONEY / FINAL CONFIRMATION'), node('h4', '', 'Buy ' + number(v.qty, 0) + ' ' + v.symbol));
    var metrics = node('dl', 'tw-result-metrics'); metrics.append(metric('Entry limit', money(v.limit_price)), metric('Initial stop', money(v.stop_price)), metric('Planned dollar risk', money(v.risk_dollars)), metric('Position amount', money(v.position_dollars))); card.append(metrics);
    card.append(small('Account ' + String(v.account_label || 'label unavailable') + ' · ' + String(v.order_type || 'Order type unavailable')), small('Broker sizing uses current account equity and available cash. Review this final share count against your saved plan.'), small('Quote ' + time(v.quote.timestamp) + ' · ' + String(v.quote.feed || 'feed unavailable')), small('Preview expires ' + time(v.expires_at)));
    card.append(node('p', 'tw-warning', v.protection_note || 'The attached stop may activate only after the entry fills completely. Partial fills can remain unprotected.'));
    if (preview.receipt) { var receipt = preview.receipt; var receiptText = receipt.state === 'accepted' ? 'Order accepted. Waiting for confirmed fills.' : receipt.state === 'rejected' ? 'Order rejected. No fill has been recorded.' : receipt.state === 'filled' ? 'Broker reports filled. Syncing execution receipts for your record.' : receipt.state === 'partially_filled' ? 'Broker reports a partial fill. Check confirmed executions and the attached stop.' : receipt.state === 'canceled' || receipt.state === 'expired' ? 'Order ' + receipt.state + '. Reconcile any executions before another order.' : 'Order result unknown. Reconcile before another order.'; card.append(node('p', 'tw-order-receipt', receiptText)); if (receipt.message) card.append(small(receipt.message)); card.append(button('Track account activity', 'trade-track-submitted', function () { showTab('positions'); refreshBroker(true); }, true)); }
    else if (preview.submitted) card.append(node('p', 'tw-order-receipt', 'Submitting once. Waiting for the broker’s response…'));
    else { var submit = button(v.mode === 'live' ? 'Submit live order · real money' : 'Submit paper order', 'trade-submit-order', submitOrder, true); submit.disabled = busy || Date.parse(v.expires_at) <= Date.now(); card.append(submit); if (Date.parse(v.expires_at) <= Date.now()) card.append(small('This preview expired. Request a new preview before submitting.')); }
    box.append(card);
  }
  async function submitOrder() {
    if (busy || !preview || preview.submitted) return; if (Date.parse(preview.data.expires_at) <= Date.now()) { announce('The order preview expired. Request a new one.'); paintPreview(); return; }
    var current = preview, v = current.data; current.submitted = true; busy = true; paintCalculation();
    try { var r = await window.SCTradeBridge.submit(v.preview_id); if (!r.ok) { current.receipt = { state: r.error && r.error.code === 'UNKNOWN_ORDER_STATE' ? 'reconciliation_needed' : 'rejected', message: bridgeFailure(r) }; }
      else current.receipt = r.data;
      if (['accepted', 'filled', 'partially_filled'].indexOf(current.receipt.state) >= 0 && current.receipt.order && current.receipt.order.id && portfolio && portfolio.account) {
        var p = profile(); var saved = engine().savePlan({ symbol: v.symbol, snapshot_date: v.source_session, entry: v.limit_price, stop: v.stop_price, risk_percent: p.risk_percent, capital: finite(v.risk_budget) && p.risk_percent > 0 ? v.risk_budget * 100 / p.risk_percent : p.capital, cash_cap: finite(v.position_dollars) ? v.position_dollars : p.cash_cap, qty: v.qty, status: 'submitted', order_id: current.receipt.order.id, account_id: portfolio.account.id, environment: v.mode });
        if (!saved.ok) announce('Order accepted; its plan could not be linked locally. Refresh executions to reconcile the record.');
        else announce('Order accepted. A position appears only when executions confirm the fill.');
      } else announce(current.receipt.message || (current.receipt.state === 'accepted' ? 'Order accepted. Waiting for confirmed executions.' : 'Check the order result before continuing.'));
      if (current.receipt.state === 'reconciliation_needed') broker.state = 'reconciliation_needed';
    } catch (_) { current.receipt = { state: 'reconciliation_needed', message: 'The response was lost. Do not submit another order until account activity is reconciled.' }; broker.state = 'reconciliation_needed'; announce(current.receipt.message); }
    finally { busy = false; paintStatus(); paintCalculation(); if (broker.connected) timer = window.setTimeout(function () { refreshBroker(false); }, 15000); }
  }
  function render(d) {
    host = document.getElementById('trade-workspace'); if (!host) return; data = d || {}; engine().load(); host.hidden = false; host.classList.add('trade-workspace'); host.replaceChildren();
    statusPanel = node('section', 'tw-today-status'); statusPanel.id = 'trade-today-status'; host.append(statusPanel);
    var tabs = node('div', 'tw-tabs'); tabs.setAttribute('role', 'tablist'); tabs.setAttribute('aria-label', 'Your trading desk'); tabs.append(tabButton('today', 'Today'), tabButton('positions', 'Positions'), tabButton('activity', 'Activity'));
    tabs.addEventListener('keydown', function (event) { if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return; event.preventDefault(); var names = ['today', 'positions', 'activity'], at = names.indexOf(activeTab); var next = event.key === 'Home' ? 0 : event.key === 'End' ? 2 : (at + (event.key === 'ArrowRight' ? 1 : -1) + 3) % 3; showTab(names[next], true); }); host.append(tabs);
    notice = node('p', 'tw-notice', message); notice.id = 'trade-notice'; notice.setAttribute('role', 'status'); notice.setAttribute('aria-live', 'polite'); host.append(notice);
    panel = node('div', 'tw-panel'); panel.id = 'trade-panel'; panel.setAttribute('role', 'tabpanel'); host.append(panel); paintTabs(); paintStatus(); paintBody();
    if (!initialized) { initialized = true; engine().subscribe(function () { if (host && host.isConnected) { paintStatus(); var line = host.querySelector('#trade-storage-status'); if (line) line.replaceWith(storageLine()); } });
      window.addEventListener('stockbee:plan', function (event) { if (host && host.isConnected) choose(event.detail); });
      document.addEventListener('visibilitychange', function () { clearTimeout(timer); if (!document.hidden && broker.connected) refreshBroker(false); });
      window.addEventListener('offline', function () { refreshSerial++; clearTimeout(timer); preview = null; brokerError = 'You are offline. Account information is the last saved view.'; paintStatus(); paintCalculation(); });
      window.addEventListener('online', function () { if (broker.connected) refreshBroker(false); else { brokerError = ''; paintStatus(); } });
    }
    startBridge();
  }
  window.SCTradeWorkspace = { render: render, openPlan: choose };
}());
