/* A deliberate find → plan → confirm → track workflow. Orders require the private bridge. */
(function () {
  'use strict';
  var host, data, activeTab = 'today', queueTab = 'breakout', query = '', selected = null;
  var tracker, trackerMount, homePanel, returnFocus, allSetups = false, mapView = 'map', activeChart = null;
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
  function showTab(tab, keyboard) {
    activeTab = tab;
    if (tab === 'today') {
      if (tracker && tracker.open) tracker.close();
      panel = homePanel;
    } else {
      if (!tracker.open) { returnFocus = document.activeElement; tracker.showModal(); document.documentElement.classList.add('tw-modal-open'); }
      panel = trackerMount;
    }
    paintTabs(); paintBody();
    if (tab !== 'today') trackerMount.scrollTop = 0;
    if (keyboard) focus('trade-tab-' + tab);
  }

  function tabButton(name, label) { var b = button(label, 'trade-tab-' + name, function () { showTab(name, false); }); b.className = 'tw-tab'; b.setAttribute('role', 'tab'); b.dataset.tradeTab = name; b.setAttribute('aria-controls', 'trade-tracker-panel'); return b; }

  function paintTabs() { host.querySelectorAll('[data-trade-tab]').forEach(function (b) { var yes = b.dataset.tradeTab === activeTab; b.setAttribute('aria-selected', String(yes)); b.tabIndex = yes ? 0 : -1; }); }

  function nextAction() {
    var d = derived(), s = measured();
    if (list(d.reconciliation).length || broker.state === 'reconciliation_needed' || list(portfolio && portfolio.unresolved).length) return { label: 'Check one thing first.', text: 'A fill or order needs your review. Open the tracker to resolve it.', button: 'Review tracker', action: function () { showTab('positions'); }, tone: 'attention' };
    if (list(portfolio && portfolio.pending_orders).length) return { label: 'Your order is in progress.', text: 'Open the tracker to check what has actually filled.', button: 'Open tracker', action: function () { showTab('positions'); }, tone: 'attention' };
    if (list(d.positions).length || list(d.broker_positions).length) return { label: 'Check your trades. Then look ahead.', text: 'Your positions are in the tracker. Fresh ideas are below when you need them.', button: 'Open tracker', action: function () { showTab('positions'); }, tone: 'ready' };
    if (!s) return { label: 'A clear place to start.', text: 'The latest 4% scan will appear here when it is published.', button: 'Plan a stock', action: openBlankPlan, tone: 'quiet' };
    if (oldSnapshot()) return { label: 'Review now. Verify before trading.', text: 'This is an older daily scan. Check current prices before using a plan.', button: 'Review a setup', action: function () { if (rows().length) choose(rows()[0]); else openBlankPlan(); }, tone: 'quiet' };
    if (!list(s.scan && s.scan.rows).length) return { label: 'No rush. No forced trades.', text: 'No breakout matches this session. See which stocks are still setting up.', button: 'See what’s setting up', action: function () { queueTab = 'anticipation'; allSetups = false; showTab('today'); focus('trade-watch-tab'); }, tone: 'quiet' };
    return { label: 'See the move. Make your plan.', text: 'Explore the scan. Read the chart. Turn one idea into a trade you can follow.', button: 'Review the first setup', action: function () { queueTab = 'breakout'; choose(rows()[0]); }, tone: 'ready' };
  }

  function paintStatus() {
    if (!statusPanel) return;
    var next = nextAction(), s = measured(), d = derived(); statusPanel.replaceChildren(); statusPanel.dataset.tone = next.tone;
    var top = node('div', 'tw-status-line'); top.append(node('span', 'tw-eyebrow', 'SPICYSTOCK / THE TRADING DESK'), node('span', 'tw-status-dot', navigator.onLine === false ? 'Offline · saved scan' : brokerError ? 'Account refresh unavailable' : broker.connected ? (broker.mode === 'live' ? 'Live account connected' : 'Paper account connected') : 'Trade in your broker · track here'));
    var copy = node('div', 'tw-status-copy'); copy.append(node('h1', 'tw-title', next.label), node('p', 'tw-intro', next.text));
    var actions = node('div', 'tw-actions'); actions.append(button(next.button, 'trade-next-action', next.action, true));
    if (next.button !== 'Open tracker' && next.button !== 'Review tracker') actions.append(button('My tracker', 'trade-open-tracker', function () { showTab('positions'); }));
    var stats = node('dl', 'tw-session-summary');
    stats.append(metric('Breakout matches', s ? number(s.scan && s.scan.matched, 0) : '—'), metric('Setting up', s ? number(s.anticipation && s.anticipation.matched, 0) : '—'), metric('My open positions', String(list(d.broker_positions).length + list(d.positions).filter(function (p) { return p.source !== 'alpaca' || !list(d.broker_positions).some(function (b) { return b.symbol === p.symbol && b.account_id === p.account_id && b.environment === p.environment; }); }).length)));
    var body = node('div', 'tw-hero-body'); var left = node('div'); left.append(copy, actions); body.append(left, stats);
    var run = data && data.run || {}, stamp = node('div', 'tw-data-stamp'); stamp.id = 'trade-data-status';
    stamp.append(node('span', '', 'Session ' + (run.date || 'unavailable')), node('span', '', s && s.scope ? number(s.scope.measured, 0) + ' / ' + number(s.scope.requested, 0) + ' tracked stocks measured' : 'Coverage unavailable'), node('span', 'tw-data-quality', run.fixture || run.dry_run ? 'Sample data · no real signals' : oldSnapshot() ? 'Older snapshot · not live' : 'Daily prices · not live'));
    if (run.fixture || run.dry_run || list(run.errors).length) stamp.append(node('span', 'tw-warning', run.fixture || run.dry_run ? 'This session is a demonstration.' : 'Scan has missing or degraded data. Open scan details below.'));
    statusPanel.append(top, body, stamp);
    var badge = host.querySelector('#trade-account-status'); if (badge) badge.textContent = broker.connected ? (broker.mode === 'live' ? 'Live' : 'Paper') + ' connected' : 'Not connected';
  }

  function storageLine() {
    var st = engine().getStorageStatus(); var p = node('p', 'tw-storage'); p.id = 'trade-storage-status';
    p.textContent = st.persistent ? 'Your plans and recorded fills stay in this browser. Export a backup to move devices.' : 'This visit only. ' + (st.reason || 'Browser storage is unavailable.') + ' Export a backup before leaving.';
    if (!st.persistent) p.classList.add('tw-warning'); return p;
  }
  function paintBody() {
    if (!panel) return; if (activeChart && panel.contains(activeChart)) { if (activeChart.destroy) activeChart.destroy(); activeChart = null; } panel.replaceChildren();
    if (activeTab === 'today') { panel.removeAttribute('aria-labelledby'); paintToday(); }
    else { panel.setAttribute('aria-labelledby', 'trade-tab-' + activeTab); if (activeTab === 'positions') paintPositions(); else if (activeTab === 'plans') paintPlans(); else paintActivity(); panel.append(storageLine()); }
    if (notice) { (activeTab === 'today' ? host : tracker).insertBefore(notice, activeTab === 'today' ? homePanel : trackerMount); notice.textContent = message; }
  }

  function sectionHeading(kicker, heading, text) { var h = node('div', 'tw-section-heading'); if (kicker) h.append(node('p', 'tw-eyebrow', kicker)); h.append(node('h3', '', heading)); if (text) h.append(node('p', 'tw-copy', text)); return h; }
  function empty(title, text) { var box = node('div', 'tw-empty'); box.append(node('h4', '', title), node('p', 'tw-copy', text)); return box; }
  function showProfile() { profileOpen = true; showTab('today'); focus('trade-capital'); }

  function openResearch(id) {
    var report = document.getElementById('research-report'), target = document.getElementById(id || 'research-report');
    if (report) report.open = true;
    if (target) { for (var p = target; p; p = p.parentElement) if (p.tagName === 'DETAILS') p.open = true; target.scrollIntoView({ block: 'start', behavior: 'auto' }); var title = target.querySelector('summary, h2, h3') || target; title.tabIndex = -1; title.focus({ preventScroll: true }); }
    window.dispatchEvent(new Event('resize'));
  }
  function paintToday() {
    activeChart = null;
    if (profileOpen && !planVisible) panel.append(profileForm());
    var market = node('section', 'tw-market'); market.id = 'trade-queue';
    var heading = node('div', 'tw-market-heading'), title = sectionHeading('01 / EXPLORE', 'Where the action is.', 'Tap a stock. Its chart, setup and trade plan stay together.');
    title.querySelector('h3').id = 'trade-market-title'; title.querySelector('h3').tabIndex = -1;
    var modes = node('div', 'tw-view-switch'); modes.setAttribute('role', 'group'); modes.setAttribute('aria-label', 'Explore stocks as');
    [['map', 'Map'], ['cards', 'Cards']].forEach(function (v) { var b = button(v[1], 'trade-view-' + v[0], function () { mapView = v[0]; paintBody(); focus('trade-view-' + v[0]); }); b.setAttribute('aria-pressed', String(mapView === v[0])); modes.append(b); }); heading.append(title, modes); market.append(heading);
    var toolbar = node('div', 'tw-market-toolbar'), switches = node('div', 'tw-queue-switch'), s = measured(); switches.setAttribute('role', 'group'); switches.setAttribute('aria-label', 'Setup list');
    [['breakout', '4% breakouts', 'trade-breakout-tab', s && s.scan], ['anticipation', 'Setting up', 'trade-watch-tab', s && s.anticipation]].forEach(function (v) {
      var b = button(v[1] + ' · ' + (v[3] ? number(v[3].matched, 0) : '—'), v[2], function () { queueTab = v[0]; query = ''; selected = null; planVisible = false; preview = null; allSetups = false; paintBody(); focus(v[2]); }); b.setAttribute('aria-pressed', String(queueTab === v[0])); switches.append(b);
    });
    var search = node('div', 'tw-search'), label = node('label', '', 'Find a stock'), input = node('input'); label.htmlFor = 'trade-search'; input.id = 'trade-search'; input.type = 'search'; input.placeholder = 'Search symbol'; input.value = query; input.autocomplete = 'off';
    input.addEventListener('input', function () { query = input.value; var target = host.querySelector('#trade-market-content'); if (target) renderMarket(target); }); search.append(label, input); toolbar.append(switches, search); market.append(toolbar);
    var content = node('div'); content.id = 'trade-market-content'; renderMarket(content); market.append(content);
    var footer = node('div', 'tw-market-footer'); footer.append(small('Review order: recorded score, then close strength. A scan match is not a buy signal.'), button('Plan another stock', 'trade-plan-manual', openBlankPlan)); market.append(footer); panel.append(market);
    var row = selected || (!planVisible ? rows()[0] : null), desk = node('div', 'tw-visual-desk' + (planVisible && selected ? ' tw-visual-desk--planning' : '')); desk.id = 'trade-selected-desk';
    if (row) desk.append(setupPreview(row));
    if (planVisible) desk.append(planForm());
    else if (!row) desk.append(empty('Nothing to force.', 'Switch lists, or plan a stock you already follow. Your saved trades are in My tracker.'));
    panel.append(desk, universeCard());
    var support = node('div', 'tw-support-compact');
    var settings = node('details', 'tw-settings'); settings.append(node('summary', '', 'My limits & account')); settings.append(accountCard()); support.append(settings);
    var learning = node('details', 'tw-settings'); learning.append(node('summary', '', 'Strategy results & learning'), learningCard()); support.append(learning); panel.append(support);
  }
  function renderMarket(box) {
    box.replaceChildren(); var all = rows().filter(function (r) { return r.ticker.indexOf(query.trim().toUpperCase()) >= 0; });
    if (!all.length) { box.append(empty(query ? 'No matching symbol.' : 'No matches on this list.', query ? 'Try another symbol or plan a stock you follow.' : 'Try the other list. The next scan may find something new.')); return; }
    if (mapView === 'cards') { var cards = node('div', 'tw-setup-list tw-visual-cards'); cards.id = 'trade-setup-list'; paintCards(cards); box.append(cards); return; }
    var displayed = all.slice(0, 12), valid = displayed.filter(function (r) { return finite(r.gain_pct) && finite(r.volume_vs_average); });
    if (!valid.length) { box.append(small('Map measurements are unavailable. Use Cards to review the saved stocks.')); return; }
    var figure = node('figure', 'tw-opportunity-map'), chart = node('div', 'tw-map-plot'); chart.setAttribute('aria-label', 'Stock map: session move vertically, volume versus its average horizontally.');
    var xs = valid.map(function (r) { return r.volume_vs_average; }), ys = valid.map(function (r) { return r.gain_pct; });
    var xlo = Math.min.apply(null, xs), xhi = Math.max.apply(null, xs), ylo = Math.min(0, Math.min.apply(null, ys)), yhi = Math.max(4, Math.max.apply(null, ys));
    var xpad = Math.max(.12, (xhi - xlo) * .15), ypad = Math.max(.5, (yhi - ylo) * .12); xlo = Math.max(0, xlo - xpad); xhi += xpad; ylo -= ypad; yhi += ypad;
    var area = node('div', 'tw-map-area');
    [0, .5, 1].forEach(function (t) { var line = node('div', 'tw-map-gridline'); line.style.bottom = t * 100 + '%'; line.append(node('span', '', pct(ylo + (yhi - ylo) * t))); area.append(line); });
    if (ylo < 4 && yhi > 4) { var trigger = node('div', 'tw-map-trigger'); trigger.style.bottom = (4 - ylo) / (yhi - ylo) * 100 + '%'; trigger.append(node('span', '', '+4% scan level')); area.append(trigger); }
    valid.forEach(function (r, i) {
      var point = button('', 'trade-map-' + r.ticker, function () { choose(r); }); point.className = 'tw-map-point'; point.dataset.tradeSelect = r.ticker;
      point.setAttribute('aria-label', 'Review ' + r.ticker + ', ' + pct(r.gain_pct) + ', ' + number(r.volume_vs_average) + ' times average volume'); point.setAttribute('aria-pressed', String((selected || rows()[0]).ticker === r.ticker));
      point.style.left = ((r.volume_vs_average - xlo) / (xhi - xlo) * 100) + '%'; point.style.bottom = ((r.gain_pct - ylo) / (yhi - ylo) * 100) + '%'; point.style.setProperty('--point-delay', i * 35 + 'ms');
      point.append(node('span', 'tw-map-dot'), node('strong', '', r.ticker)); area.append(point);
    });
    chart.append(node('span', 'tw-map-y-title', 'SESSION MOVE'), area);
    var axis = node('div', 'tw-map-x-axis'); axis.append(node('span', '', number(xlo) + '×'), node('span', '', 'VOLUME VS 20-DAY AVERAGE'), node('span', '', number(xhi) + '×')); chart.append(axis); figure.append(chart);
    var legend = node('figcaption', 'tw-map-caption'); legend.append(node('span', '', 'More participation →'), node('span', '', 'Higher on the map = larger session move. Not a return forecast.')); figure.append(legend); box.append(figure);
    var strip = node('div', 'tw-symbol-strip'); strip.setAttribute('role', 'group'); strip.setAttribute('aria-label', 'Select any stock on the map');
    displayed.forEach(function (r) { var b = button('', null, function () { choose(r); }); b.setAttribute('aria-pressed', String((selected || rows()[0]).ticker === r.ticker)); b.append(node('strong', '', r.ticker), node('span', r.gain_pct >= 0 ? 'tw-positive' : 'tw-negative', pct(r.gain_pct))); strip.append(b); }); box.append(strip);
    if (all.length > displayed.length) box.append(button('See all ' + all.length + ' stocks as cards', 'trade-map-show-all', function () { mapView = 'cards'; allSetups = true; paintBody(); focus('trade-view-cards'); }));
  }
  function setupPreview(row) {
    var box = node('section', 'tw-inspector tw-surface'); box.id = 'trade-inspector';
    if (!row) return box;
    var head = node('div', 'tw-inspector-head'), identity = node('div'); identity.append(node('p', 'tw-eyebrow', '02 / UNDERSTAND THE SETUP'), node('h3', 'tw-inspector-symbol', row.ticker));
    identity.querySelector('h3').id = 'trade-inspector-title'; identity.querySelector('h3').tabIndex = -1;
    var price = node('div', 'tw-inspector-price'); price.append(node('strong', '', money(row.close)), node('span', row.gain_pct >= 0 ? 'tw-positive' : 'tw-negative', pct(row.gain_pct) + ' session')); head.append(identity, price); box.append(head);
    var c = scored(row.ticker), provenance = c && c.provenance && c.provenance.source;
    var meta = node('div', 'tw-inspector-meta'); meta.append(node('span', '', 'Daily bars · ' + (row.date || 'unknown session')), node('span', '', c && finite(c.score) ? number(c.score) + '/10 · ' + (provenance === 'claude' ? 'AI reviewed' : 'Recorded score') : 'Scan match · no AI score')); box.append(meta, spark(row));
    var evidence = node('section', 'tw-setup-evidence'); evidence.append(node('div', 'tw-evidence-heading', 'The setup, explained.'));
    var gauges = node('div', 'tw-evidence-grid');
    [
      ['Close strength', finite(row.close_position) ? Math.round(row.close_position * 100) + '%' : '—', finite(row.close_position) ? row.close_position : null, 'Where the close sits between the session low and high. 100% means it closed at the high. This is a measurement, not a win probability.'],
      ['Volume lift', finite(row.volume_vs_previous) ? number(row.volume_vs_previous) + '×' : '—', finite(row.volume_vs_previous) ? Math.min(row.volume_vs_previous / 3, 1) : null, 'Shares traded versus the prior session. The 4% scan asks for more volume than yesterday, plus at least 100,000 shares.'],
      ['Base compression', finite(row.compression_ratio) ? number(row.compression_ratio) + '×' : '—', finite(row.compression_ratio) ? Math.min(row.compression_ratio, 1) : null, 'Recent range versus its longer baseline. A lower ratio means the recent price action is tighter. It does not confirm a breakout by itself.'],
      ['Above 20-day average', finite(row.extension_sma20_pct) ? pct(row.extension_sma20_pct) : '—', null, 'Distance from the 20-session moving average. A large extension means the price has already travelled; inspect your entry and stop distance.'],
      ['Prior up days', number(row.prior_up_days, 0), null, 'Consecutive up sessions immediately before the signal. This helps distinguish a fresh move from one already running.'],
      ['Earlier 4% bursts', number(row.prior_bursts_20, 0), null, 'Number of earlier 4% bursts in 20 sessions. Repeated bursts can help you spot an extended or choppy move on the chart.']
    ].forEach(function (v) { var cell = node('details', 'tw-evidence-cell'), summary = node('summary'); summary.append(node('span', 'tw-evidence-label', v[0]), node('strong', '', v[1]), node('span', 'tw-evidence-info', 'ⓘ')); if (v[2] !== null) { var meter = node('span', 'tw-evidence-meter'); meter.style.setProperty('--meter', Math.max(0, Math.min(v[2], 1)) * 100 + '%'); summary.append(meter); } cell.append(summary, small(v[3])); gauges.append(cell); }); evidence.append(gauges); box.append(evidence);
    if (c && typeof c.reason === 'string') box.append(node('p', 'tw-recorded-review', 'Recorded review · ' + c.reason));
    var actions = node('div', 'tw-inspector-actions');
    if (!planVisible) actions.append(button('Build a plan for ' + row.ticker + ' →', 'trade-review-featured', function () { choose(row); }, true));
    else actions.append(button('Jump to trade ticket ↓', 'trade-jump-ticket', function () { focus('trade-entry'); }));
    actions.append(button('See the strategy record ↗', 'trade-inspector-research', function () { openResearch('evidence-card'); })); box.append(actions); return box;
  }
  function universeCard() {
    var run = data && data.run || {}, s = measured(), u = run.universe || {}, selection = u.selection;
    var box = node('section', 'tw-universe'); box.id = 'trade-universe';
    var coverage = 'This session used the 228-name curated starter list. It is a subset of US stocks.';
    if (selection) {
      coverage = 'Discovery used a fallback. The scope below is the one actually scanned.';
      if (selection.mode === 'adaptive') {
        var captured = typeof selection.directory_fetched_at === 'string' ? selection.directory_fetched_at.slice(0, 10) : '';
        coverage = selection.directory_status === 'cached'
          ? 'Listings captured ' + (safeDate(captured) ? captured : 'on an unavailable date') + '. Prices and selection refreshed for ' + run.date + '.'
          : 'Refreshed from current listings and recorded market activity.';
      }
    }
    var heading = sectionHeading('THE SEARCH BEHIND THE SIGNALS', selection && selection.mode === 'adaptive' ? 'A universe that moves with the market.' : 'Know what the scan actually covers.', coverage); box.append(heading);
    var steps = node('div', 'tw-universe-flow');
    [['Discovered', selection ? number(selection.discovered, 0) : '—'], ['Deeply scanned', s ? number(s.scope && s.scope.measured, 0) : '—'], ['4% breakouts', s ? number(s.scan && s.scan.matched, 0) : '—'], ['Setting up', s ? number(s.anticipation && s.anticipation.matched, 0) : '—']].forEach(function (v, i) { var part = node('div', 'tw-universe-stage'); part.append(node('span', 'tw-universe-step', '0' + (i + 1)), node('strong', '', v[1]), node('span', '', v[0])); steps.append(part); }); box.append(steps);
    if (selection) { box.append(small('Selected ' + number(selection.selected, 0) + ' of ' + number(selection.eligible, 0) + ' eligible · ' + list(selection.added).length + ' added · ' + list(selection.removed).length + ' rotated out · ' + (selection.source || 'Source unavailable'))); if (selection.warning) box.append(node('p', 'tw-warning', selection.warning)); }
    else box.append(small('The starter list was hand-picked for fast scans, not ranked as the best 228 stocks. New scan selection is shown here when a refreshed run publishes.'));
    box.append(button('Inspect the scan record ↗', 'trade-universe-record', function () { openResearch('funnel-card'); })); return box;
  }

  function paintCards(box) {
    if (!box) return; box.replaceChildren(); var s = measured(), all = rows(), filtered = all.filter(function (r) { return r.ticker.indexOf(query.trim().toUpperCase()) >= 0; });
    if (!s) { box.append(empty('Waiting for the next scan.', 'Your saved trades are still in My tracker.')); return; }
    if (!filtered.length) { box.append(empty(query ? 'No matching stock.' : 'Nothing on this list today.', query ? 'Try another symbol.' : 'Try the other list. There is no need to force a trade.')); return; }
    (allSetups || query ? filtered : filtered.slice(0, 5)).forEach(function (row, i) {
      var b = button('', null, function () { choose(row); }); b.className = 'tw-setup-card'; b.dataset.tradeSelect = row.ticker; b.setAttribute('aria-label', 'Review ' + row.ticker + ' setup'); b.setAttribute('aria-pressed', String(selected && selected.ticker === row.ticker));
      var h = node('div', 'tw-card-top'); h.append(node('span', 'tw-card-rank', String(i + 1).padStart(2, '0')), node('strong', 'tw-symbol', row.ticker), node('span', 'tw-change', pct(row.gain_pct))); b.append(h);
      var c = scored(row.ticker), provenance = c && c.provenance && c.provenance.source;
      var tag = c && finite(c.score) ? number(c.score) + '/10 · ' + (provenance === 'claude' ? 'AI review' : provenance === 'fallback' ? 'Checklist fallback' : 'Unknown score source') : 'Scan match · unscored';
      b.append(node('span', 'tw-card-reason', money(row.close) + ' close · ' + (finite(row.volume_vs_previous) ? number(row.volume_vs_previous) + '× volume vs yesterday' : 'Volume unavailable')));
      var bottom = node('span', 'tw-card-bottom'); bottom.append(node('span', 'tw-card-meta', tag), node('span', 'tw-card-cta', 'Review →')); b.append(bottom); box.append(b);
    });
    if (!query && filtered.length > 5) box.append(button(allSetups ? 'Show fewer' : 'Show all ' + filtered.length + ' stocks', 'trade-show-all', function () { allSetups = !allSetups; paintCards(box); focus('trade-show-all'); }));
    var group = queueTab === 'anticipation' ? s.anticipation : s.scan; if (group && finite(group.matched) && group.matched > all.length) box.append(small(number(all.length, 0) + ' saved of ' + number(group.matched, 0) + ' measured matches.'));
  }

  function choose(row) {
    if (!row || typeof row.ticker !== 'string') return;
    selected = row; draft = { symbol: row.ticker, entry: '', stop: '', note: '' }; editingPlan = null; preview = null; planVisible = true; profileOpen = false; showTab('today'); focus('trade-inspector-title'); announce('Reviewing ' + row.ticker + '. Check the chart, then enter your prices.');
  }

  function openBlankPlan() { selected = null; draft = { symbol: '', entry: '', stop: '', note: '' }; editingPlan = null; preview = null; planVisible = true; showTab('today'); focus('trade-symbol'); }

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
    var form = node('form', 'tw-profile tw-surface'); form.id = 'trade-profile-form'; form.append(sectionHeading('SET ONCE', 'Start with your limits.', 'We’ll calculate the shares. You choose how much to risk.'));
    var p = profile(), values = Object.assign({}, p), fields = node('div', 'tw-fields'), extra = node('details', 'tw-details'); extra.append(node('summary', '', 'Optional position limits'));
    [['Trading capital ($)', 'capital', 'trade-capital'], ['Risk per trade (%)', 'risk_percent', 'trade-risk'], ['Cash cap per stock ($)', 'cash_cap', 'trade-cash-cap'], ['Maximum open positions', 'max_positions', 'trade-max-positions']].forEach(function (v, i) { var f = field(v[0], v[2], { type: 'number', min: '0', step: v[1] === 'max_positions' ? '1' : 'any', inputmode: 'decimal' }, p[v[1]], function (text) { values[v[1]] = text.trim() === '' ? null : Number(text); }); (i < 2 ? fields : extra).append(f); }); form.append(fields, extra);
    form.append(small('Risk means the planned loss if your stop is reached. Gaps and slippage can make the actual loss larger.'));
    var actions = node('div', 'tw-actions'), save = node('button', 'tw-button tw-button--primary', 'Save my limits'); save.type = 'submit'; save.id = 'trade-save-profile'; actions.append(save, button('Close', null, function () { profileOpen = false; paintBody(); })); form.append(actions);
    form.addEventListener('submit', function (e) { e.preventDefault(); if (mutate(engine().setProfile(values), 'Trading limits saved.')) { profileOpen = false; preview = null; paintStatus(); paintBody(); if (planVisible) focus('trade-entry'); } }); return form;
  }

  function spark(row) {
    if (window.SCTradeChart) { activeChart = window.SCTradeChart.render(row, { entry: planVisible && draft.symbol === row.ticker ? Number(draft.entry) || null : null, stop: planVisible && draft.symbol === row.ticker ? Number(draft.stop) || null : null }); return activeChart; }
    return fallbackSpark(row);
  }
  function fallbackSpark(row) {
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
    var title = sectionHeading('YOUR TRADE TICKET', draft.symbol ? draft.symbol + ' · the plan' : 'Plan a stock.', 'Set two prices. We’ll calculate the shares.'); title.querySelector('h3').id = 'trade-plan-title'; title.querySelector('h3').tabIndex = -1; form.append(title); form.append(button('Back to overview', 'trade-close-plan', function () { planVisible = false; profileOpen = false; paintBody(); focus('trade-review-featured'); }));
    if (selected) {
      var ref = node('div', 'tw-reference'); ref.id = 'trade-reference';
      ref.append(small('Reference · ' + selected.date + ': close ' + money(selected.close) + ' / low ' + money(selected.low)));
      if (safeDate(selected.date) && finite(selected.close) && finite(selected.low) && selected.low > 0 && selected.low < selected.close) ref.append(button('Start with recorded close & low', 'trade-use-reference', function () { draft.entry = String(selected.close); draft.stop = String(selected.low); preview = null; paintBody(); focus('trade-entry'); announce('Historical reference loaded from ' + selected.date + '. Verify both prices before making a trade.'); }));
      form.append(ref);
    }
    if (!profileReady() || profileOpen) { if (profileOpen) form.append(profileForm()); else { form.append(small('One quick setup lets us calculate your shares.')); form.append(button('Set my limits', 'trade-plan-profile', showProfile, true)); } }
    else { var p = profile(); var limits = node('div', 'tw-plan-limits'); limits.append(small(money(p.capital) + ' capital · ' + number(p.risk_percent) + '% risk per trade'), button('Edit limits', 'trade-edit-profile', showProfile)); form.append(limits); }
    var fields = node('div', 'tw-fields'); [['Symbol', 'symbol', 'trade-symbol', { type: 'text', maxlength: '15', autocomplete: 'off', autocapitalize: 'characters' }], ['Buy limit ($)', 'entry', 'trade-entry', { type: 'number', min: '0', step: 'any', inputmode: 'decimal' }], ['Exit if it falls to ($)', 'stop', 'trade-stop', { type: 'number', min: '0', step: 'any', inputmode: 'decimal' }]].forEach(function (v) { fields.append(field(v[0], v[2], v[3], draft[v[1]], function (value) { draft[v[1]] = v[1] === 'symbol' ? value.toUpperCase() : value; preview = null; paintCalculation(); })); }); if (selected) { var symbolField = fields.querySelector('#trade-symbol'); if (symbolField) symbolField.closest('.tw-field').hidden = true; } form.append(fields);
    var result = node('div', 'tw-calculation'); result.id = 'trade-calculation'; result.setAttribute('aria-live', 'polite'); form.append(result);
    var actions = node('div', 'tw-actions'); actions.append(button(editingPlan ? 'Update saved plan' : 'Save plan', 'trade-save-plan', savePlan, true));
    if (broker.connected) { var pb = button('Preview broker order', 'trade-preview-order', previewOrder); pb.disabled = busy || broker.state === 'reconciliation_needed' || !!(portfolio && portfolio.clock && portfolio.clock.is_open === false); actions.append(pb); }
    if (editingPlan) { actions.append(button('Log my purchase', 'trade-log-purchase', function () { openFill(draft.symbol, 'buy', editingPlan); }, true), button('View saved plans', 'trade-view-plans', function () { showTab('plans'); })); } form.append(actions); if (editingPlan) form.append(small('Saved in My tracker. Place the trade with your broker, then log the actual fill.')); var previewBox = node('div'); previewBox.id = 'trade-order-preview'; form.append(previewBox);
    var handoff = node('div', 'tw-broker-handoff'); handoff.append(node('p', 'tw-eyebrow', broker.connected ? 'CONNECTED ACCOUNT' : 'PLACE THE TRADE'));
    handoff.append(node('strong', '', broker.connected ? 'Preview here. Confirm once.' : 'Buy in your broker. Track it here.'));
    handoff.append(small(broker.connected ? 'A preview checks the current quote, account and order limits.' : 'Direct orders are not connected. Copy this ticket, review current prices in your broker, then log only what actually filled.'));
    var transfer = node('div', 'tw-actions'); transfer.append(button('Copy trade details', 'trade-copy-ticket', copyTicket), button('I bought it · record fill', 'trade-plan-record-fill', function () { openFill(draft.symbol, 'buy', editingPlan); })); handoff.append(transfer); form.append(handoff);
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
    if (activeChart && activeChart.isConnected && activeChart.updateLevels) activeChart.updateLevels(Number(draft.entry) || null, Number(draft.stop) || null);
    var copy = host.querySelector('#trade-copy-ticket'); if (copy) copy.disabled = !c.ok || !c.qty || !/^[A-Z][A-Z0-9.-]{0,14}$/.test(draft.symbol);
    var rail = host.querySelector('#trade-risk-ruler'); if (rail) rail.remove();
    if (c.ok && c.qty) { var ruler = node('div', 'tw-risk-ruler'); ruler.id = 'trade-risk-ruler'; ruler.append(node('span', '', 'Stop ' + money(Number(draft.stop))), node('span', 'tw-risk-distance', number((Number(draft.entry) - Number(draft.stop)) / Number(draft.entry) * 100) + '% room'), node('span', '', 'Entry ' + money(Number(draft.entry)))); target.append(ruler); }
    paintPreview();
  }
  function copyTicket() {
    var c = calc(); if (!c.ok || !c.qty || !/^[A-Z][A-Z0-9.-]{0,14}$/.test(draft.symbol)) { announce('Enter a valid symbol, prices and trading limits first.'); return; }
    var original = editingPlan && list(state().plans).find(function (p) { return p.id === editingPlan; });
    var ticketSession = original && original.snapshot_date || selected && selected.date || data.run && data.run.date || 'unknown';
    var text = draft.symbol + ' · BUY PLAN (not an order)\n' + c.qty + ' shares · buy limit ' + money(Number(draft.entry)) + '\nInitial stop reference ' + money(Number(draft.stop)) + '\nPosition cost ' + money(c.position_cost) + ' · planned loss at stop ' + money(c.planned_risk) + '\nRecorded session ' + ticketSession + '\nVerify current prices, order type and protection in your broker. Gaps can exceed planned loss.';
    function manualCopy() { var old = host.querySelector('#trade-ticket-text'); if (old) old.remove(); var area = node('textarea', 'tw-ticket-copy'); area.id = 'trade-ticket-text'; area.readOnly = true; area.setAttribute('aria-label', 'Trade details to copy'); area.value = text; host.querySelector('.tw-broker-handoff').append(area); area.focus(); area.select(); announce('Select and copy your trade details below.'); }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(function () { announce('Trade details copied. No order has been placed.'); }, manualCopy); else manualCopy();
  }
  function savePlan() {
    var c = calc(); if (!c.ok || !c.qty) { announce(c.error || 'A plan needs at least one whole share.'); return; }
    var savedPlan = editingPlan && list(state().plans).find(function (r) { return r.id === editingPlan; });
    var p = profile(), snapshotDate = savedPlan && savedPlan.snapshot_date || selected && selected.date || data && data.run && data.run.date;
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
  var trackerExpanded = '';
  function trackerRow(key, title, subtitle, value, valueLabel) {
    var row = node('details', 'tw-tracker-row'); row.dataset.trackerKey = key; row.name = 'trade-tracker-record';
    var summary = node('summary', 'tw-tracker-summary'), identity = node('span', 'tw-tracker-identity');
    identity.append(node('strong', 'tw-tracker-symbol', title), node('span', 'tw-tracker-meta', subtitle));
    var amount = node('span', 'tw-tracker-amount'); amount.append(node('strong', '', value), node('span', '', valueLabel));
    summary.append(identity, amount, node('span', 'tw-tracker-chevron', '⌄')); row.append(summary);
    var body = node('div', 'tw-tracker-detail'); row.append(body); row.open = trackerExpanded === key;
    row.addEventListener('toggle', function () {
      if (row.open) { trackerExpanded = key; panel.querySelectorAll('.tw-tracker-row[open]').forEach(function (other) { if (other !== row) other.open = false; }); }
      else if (trackerExpanded === key) trackerExpanded = '';
    });
    return { row: row, body: body };
  }
  function paintPlans() {
    var plans = list(state().plans), current = plans.filter(function (p) { return p.status !== 'canceled'; });
    panel.append(sectionHeading('', 'Your saved plans', 'Review a plan. Buy in your account. Record what actually filled.'));
    var container = node('div', 'tw-tracker-list'); container.id = 'trade-saved-plans';
    if (!current.length) container.append(empty('Nothing saved yet.', 'Choose a stock, set your entry and stop, and save the plan here.'));
    current.slice().reverse().forEach(function (p) { container.append(savedPlanRow(p)); }); panel.append(container);
    var old = plans.filter(function (p) { return p.status === 'canceled'; });
    if (old.length) { var archive = node('details', 'tw-details'); archive.append(node('summary', '', 'Canceled plans · ' + old.length)); old.slice().reverse().forEach(function (p) { archive.append(savedPlanRow(p)); }); panel.append(archive); }
    var actions = node('div', 'tw-actions'); actions.append(button('Find a setup', 'trade-plans-find', function () { showTab('today'); }, !current.length)); panel.append(actions);
  }
  function savedPlanRow(p) {
    var labels = { draft: 'Draft', prepared: 'Ready to review', submitted: 'Order submitted · check fills', canceled: 'Canceled' };
    var item = trackerRow('plan:' + p.id, p.symbol, labels[p.status] || p.status, number(p.qty, 0), 'planned shares'); item.row.dataset.tradePlanId = p.id;
    var dl = node('dl', 'tw-tracker-metrics'); dl.append(metric('Planned entry', money(p.entry)), metric('Planned stop', money(p.stop)), metric('Planned risk', money(p.qty * (p.entry - p.stop)))); item.body.append(dl);
    item.body.append(small('Evidence: ' + p.snapshot_date + '. A saved plan is not a holding.'));
    if (p.status === 'submitted') item.body.append(small('Confirm the execution in Holdings. An accepted order may still be unfilled.'));
    if (['draft', 'prepared'].indexOf(p.status) >= 0) {
      var actions = node('div', 'tw-actions'); actions.append(button('Review plan', null, function () { editPlan(p); }, true), button('Record actual fill', null, function () { openFill(p.symbol, 'buy', p.id); })); item.body.append(actions);
      var cancel = node('details', 'tw-inline-confirm'); cancel.append(node('summary', '', 'Cancel plan'), small('Keep the record and mark this unsubmitted plan as canceled?'));
      cancel.append(button('Confirm cancel plan', null, function () { if (mutate(engine().savePlan(Object.assign({}, p, { status: 'canceled' })), 'Plan canceled. Its record is retained.')) { paintStatus(); paintBody(); } })); item.body.append(cancel);
    }
    return item.row;
  }
  function paintPositions() {
    var d = derived(), brokerPositions = list(d.broker_positions);
    panel.append(sectionHeading('', 'What you own', 'Only actual fills count. Tap a holding to see its details.'));
    if (list(d.reconciliation).length) { var warnings = node('section', 'tw-reconciliation'); warnings.id = 'trade-reconciliation'; warnings.append(node('h4', '', 'Check these records first')); list(d.reconciliation).forEach(function (r) { warnings.append(small((r.symbol ? r.symbol + ' · ' : '') + (r.environment === 'paper' ? 'Paper · ' : 'Live · ') + r.reason)); }); panel.append(warnings); }
    if (brokerError) panel.append(node('p', 'tw-warning', brokerError + ' Broker values below are the last saved snapshot.'));
    if (manualOpen) { panel.append(fillForm()); return; }
    if (importOpen) { panel.append(importForm()); return; }
    var actions = node('div', 'tw-actions tw-tracker-actions'); actions.append(button('Record a trade', 'trade-record-fill', function () { openFill('', 'buy'); }, true), button('Import fills', 'trade-import-open', function () { importOpen = true; manualOpen = false; paintBody(); focus('trade-import-file'); }));
    if (broker.connected) actions.append(button('Refresh account', 'trade-refresh-holdings', function () { refreshBroker(true); })); panel.append(actions);
    var pending = list(portfolio && portfolio.pending_orders); if (pending.length || list(portfolio && portfolio.unresolved).length || broker.state === 'reconciliation_needed') {
      var orderBox = node('section', 'tw-order-list tw-tracker-pending'); orderBox.id = 'trade-pending-orders'; orderBox.append(node('h4', '', 'Orders still in progress'));
      pending.forEach(function (o, i) {
        var item = trackerRow('order:' + (o.id || i), o.symbol || 'Order', String(o.status || 'status unknown').replace(/_/g, ' '), number(Number(o.filled_qty || 0)) + ' / ' + number(Number(o.qty)), 'shares filled');
        if (o.status === 'partially_filled') { item.row.dataset.attention = 'true'; orderBox.append(node('p', 'tw-warning', (o.symbol || 'Order') + ': partial fill. The attached stop may not activate until the entry fills completely.')); }
        var legs = list(o.legs); if (legs.length) legs.forEach(function (leg) { item.body.append(small('Attached ' + (leg.type || 'exit') + ' · ' + String(leg.status || 'status unknown').replace(/_/g, ' '))); }); else item.body.append(small('A working attached stop is not confirmed by this response.')); orderBox.append(item.row);
      });
      if (broker.state === 'reconciliation_needed' || list(portfolio && portfolio.unresolved).length) orderBox.append(node('p', 'tw-warning', 'An order result is uncertain. Refresh account activity before another order.'));
      if (broker.connected) orderBox.append(button('Reconcile account', 'trade-reconcile-account', function () { refreshBroker(true); })); panel.append(orderBox);
    }
    var positions = node('div', 'tw-tracker-list'); positions.id = 'trade-positions-list';
    brokerPositions.forEach(function (p) {
      var item = trackerRow('broker:' + p.environment + ':' + p.account_id + ':' + p.symbol, p.symbol, (p.environment === 'paper' ? 'Paper' : 'Live') + ' · broker holding', number(p.qty), 'shares'); item.row.dataset.tradePosition = p.symbol;
      var dl = node('dl', 'tw-tracker-metrics'); dl.append(metric('Average entry', money(p.avg_entry_price)), metric('Snapshot value', money(p.market_value)), metric('Snapshot price', money(p.current_price))); item.body.append(dl, small('Account ' + accountLabel(p.account_id) + ' · snapshot ' + time(p.as_of)), small('Check active exit orders at your broker. A recorded stop does not confirm a working stop order.')); positions.append(item.row);
    });
    list(d.positions).filter(function (p) { return p.source !== 'alpaca' || !brokerPositions.some(function (b) { return b.symbol === p.symbol && b.account_id === p.account_id && b.environment === p.environment; }); }).forEach(function (p) {
      var item = trackerRow('holding:' + p.source + ':' + p.environment + ':' + p.account_id + ':' + p.symbol, p.symbol, (p.environment === 'paper' ? 'Paper' : 'Live') + ' · ' + (p.uncertain ? 'Check record' : p.source === 'manual' ? 'Confirmed by you' : 'Recorded executions'), number(p.qty), 'recorded shares'); item.row.dataset.tradePosition = p.symbol;
      var dl = node('dl', 'tw-tracker-metrics'); dl.append(metric('Average entry', money(p.average_entry)), metric('Original planned risk', p.uncertain ? 'Needs reconciliation' : money(p.initial_risk))); item.body.append(dl, small('Opened ' + time(p.opened_at) + ' · ' + recordedSessions(p.opened_at) + ' recorded sessions since entry.'));
      if (p.uncertain) { item.row.dataset.attention = 'true'; item.body.append(node('p', 'tw-warning', 'Reconcile this record before relying on its exposure or return.')); }
      else item.body.append(small('Recorded entry cost. No live price or working stop is implied.'));
      if (p.source === 'manual') item.body.append(button('Record a sell fill', null, function () { openFill(p.symbol, 'sell', null, p.environment); })); positions.append(item.row);
    });
    if (!positions.childNodes.length) positions.append(empty('Your first trade goes here.', 'After your broker fills a trade, record its shares, price and time. Live and paper money stay separate.')); panel.append(positions);
  }
  function accountLabel(id) { return typeof id === 'string' && id !== 'local' ? '…' + id.slice(-6) : 'manual record'; }
  function recordedSessions(stamp) { var day = typeof stamp === 'string' ? stamp.slice(0, 10) : ''; var dates = list(data && data.runs).filter(function (r) { return r && r.type === 'evening' && r.dry_run !== true && r.fixture !== true && safeDate(r.date) && r.date > day; }).map(function (r) { return r.date; }); var run = data && data.run; if (run && run.type === 'evening' && run.dry_run !== true && run.fixture !== true && safeDate(run.date) && run.date > day) dates.push(run.date); return new Set(dates).size; }
  function editPlan(p) { var s = measured(); selected = list(s && s.scan && s.scan.rows).concat(list(s && s.anticipation && s.anticipation.rows)).find(function (r) { return r.ticker === p.symbol && r.date === p.snapshot_date; }) || null; editingPlan = p.id; draft = { symbol: p.symbol, entry: String(p.entry), stop: String(p.stop), note: '' }; planVisible = true; preview = null; showTab('today'); focus('trade-entry'); }

  function openFill(symbol, side, planId, environment) { fillDraft = { symbol: symbol || '', side: side || 'buy', environment: environment || '', qty: '', price: '', executed_at: '', fees: '', initial_stop: '', execution_id: '', plan_id: planId || null, confirmed: false }; manualOpen = true; importOpen = false; showTab('positions'); focus(symbol ? 'trade-fill-qty' : 'trade-fill-symbol'); }

  function fillForm() {
    var form = node('form', 'tw-fill-form tw-tracker-form'); form.id = 'trade-fill-form'; form.append(sectionHeading('', 'Record a completed trade', 'Copy the actual execution from your broker.'));
    if (fillDraft.plan_id) { var p = list(state().plans).find(function (r) { return r.id === fillDraft.plan_id; }); if (p) form.append(small('Linked plan: ' + number(p.qty, 0) + ' shares at ' + money(p.entry) + ', stop ' + money(p.stop) + '. Enter the actual fill below.')); }
    var fields = node('div', 'tw-fields');
    fields.append(field('Symbol', 'trade-fill-symbol', { type: 'text', maxlength: '15', autocomplete: 'off', required: '' }, fillDraft.symbol, function (v) { fillDraft.symbol = v.toUpperCase(); }));
    fields.append(selectField('Bought or sold?', 'trade-fill-side', [['buy', 'Bought'], ['sell', 'Sold']], fillDraft.side, function (v) { fillDraft.side = v; }));
    fields.append(selectField('Which account?', 'trade-fill-environment', [['', 'Choose account'], ['live', 'Live · real money'], ['paper', 'Paper · practice']], fillDraft.environment, function (v) { fillDraft.environment = v; })); fields.querySelector('#trade-fill-environment').required = true;
    [['Shares filled', 'qty', 'trade-fill-qty'], ['Fill price ($)', 'price', 'trade-fill-price']].forEach(function (v) { fields.append(field(v[0], v[2], { type: 'number', min: '0', step: 'any', inputmode: 'decimal', required: '' }, fillDraft[v[1]], function (x) { fillDraft[v[1]] = x; })); });
    fields.append(field('When did it fill? (local time)', 'trade-fill-time', { type: 'datetime-local', required: '', step: '1' }, fillDraft.executed_at, function (v) { fillDraft.executed_at = v; })); form.append(fields);
    var extra = node('details', 'tw-details'); extra.append(node('summary', '', 'Fees, original stop & execution ID (optional)'));
    var optional = node('div', 'tw-fields'); [['Fees ($, blank if unknown)', 'fees', 'trade-fill-fees'], ['Original stop ($, for buys)', 'initial_stop', 'trade-fill-stop']].forEach(function (v) { optional.append(field(v[0], v[2], { type: 'number', min: '0', step: 'any', inputmode: 'decimal' }, fillDraft[v[1]], function (x) { fillDraft[v[1]] = x; })); });
    optional.append(field('Execution ID', 'trade-fill-execution', { type: 'text', maxlength: '180', autocomplete: 'off' }, fillDraft.execution_id, function (v) { fillDraft.execution_id = v; })); extra.append(optional, small('Known fees make after-fee results available. The original stop enables results measured against planned risk.')); form.append(extra);
    var confirmation = node('label', 'tw-checkbox'); var check = node('input'); check.type = 'checkbox'; check.id = 'trade-fill-confirm'; check.checked = fillDraft.confirmed; check.required = true; check.addEventListener('change', function () { fillDraft.confirmed = check.checked; }); confirmation.append(check, node('span', '', 'I checked the symbol, side, shares, price, time and account against the actual fill.')); form.append(confirmation);
    var actions = node('div', 'tw-actions'), save = node('button', 'tw-button tw-button--primary', 'Save actual fill'); save.type = 'submit'; save.id = 'trade-save-fill'; actions.append(save, button('Cancel', 'trade-cancel-fill', function () { manualOpen = false; paintBody(); focus('trade-record-fill'); })); form.append(actions);
    form.addEventListener('submit', function (e) {
      e.preventDefault(); var stamp = new Date(fillDraft.executed_at); if (!Number.isFinite(stamp.getTime())) { announce('Enter the actual execution date and local time.'); return; }
      var values = { symbol: fillDraft.symbol, side: fillDraft.side, qty: fillDraft.qty, price: fillDraft.price, executed_at: stamp.toISOString(), initial_stop: fillDraft.initial_stop === '' ? null : Number(fillDraft.initial_stop), fees: fillDraft.fees === '' ? null : Number(fillDraft.fees), source: 'manual', environment: fillDraft.environment, account_id: 'local', plan_id: fillDraft.plan_id, confirmed: fillDraft.confirmed };
      if (fillDraft.execution_id.trim()) values.execution_id = fillDraft.execution_id.trim();
      if (mutate(engine().recordFill(values), 'Fill saved. Your holdings are updated.')) { manualOpen = false; fillDraft = {}; paintStatus(); paintBody(); focus('trade-tab-positions'); }
    }); return form;
  }
  function download(name, contents, mime) { var url = URL.createObjectURL(new Blob([contents], { type: mime })); var a = node('a'); a.href = url; a.download = name; document.body.append(a); a.click(); a.remove(); window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000); }
  function importForm() {
    var box = node('section', 'tw-import tw-tracker-form'); box.id = 'trade-import'; box.append(sectionHeading('', 'Bring in your trades', 'Choose an execution CSV or SpicyStock backup. Review it before saving.'));
    var wrap = node('div', 'tw-field'), label = node('label', '', 'CSV or JSON file'), file = node('input'); file.id = 'trade-import-file'; file.type = 'file'; file.accept = '.csv,.json,text/csv,application/json'; label.htmlFor = file.id; wrap.append(label, file); box.append(wrap);
    file.addEventListener('change', async function () { var selectedFile = file.files && file.files[0]; if (!selectedFile) return; importPreview = null; paintImportPreview(); if (selectedFile.size > 8000000) { announce('Choose a file smaller than 8 MB.'); return; } try { var text = await selectedFile.text(); importPreview = engine().previewImport(text, /\.csv$/i.test(selectedFile.name) ? 'csv' : 'json'); paintImportPreview(); } catch (_) { announce('This file could not be read.'); } });
    var help = node('details', 'tw-details'); help.append(node('summary', '', 'Need a template or your old journal?')); var actions = node('div', 'tw-actions'); actions.append(button('CSV template', 'trade-import-template', function () { download('spicystock-executions-template.csv', engine().csvColumns.join(',') + '\r\n', 'text/csv'); }), button('Preview previous journal', 'trade-import-legacy', function () { importPreview = engine().previewLegacy(); paintImportPreview(); })); help.append(actions); box.append(help);
    var previewBox = node('div'); previewBox.id = 'trade-import-preview'; previewBox.setAttribute('aria-live', 'polite'); box.append(previewBox);
    box.append(button('Back to holdings', 'trade-import-cancel', function () { importOpen = false; importPreview = null; paintBody(); focus('trade-import-open'); })); window.setTimeout(function () { if (box.isConnected) paintImportPreview(); }, 0); return box;
  }
  function paintImportPreview() {
    var box = host.querySelector('#trade-import-preview'); if (!box) return; box.replaceChildren(); if (!importPreview) return;
    var p = importPreview, counts = p.counts || {}; box.append(node('h4', '', p.ok ? 'Ready to save?' : 'A few rows need fixing'), small(number(counts.fills || 0, 0) + ' new fills · ' + number(counts.plans || 0, 0) + ' plans · ' + number(counts.duplicates || 0, 0) + ' duplicate executions skipped.'));
    list(p.errors).forEach(function (e) { box.append(node('p', 'tw-warning', e)); }); list(p.warnings).forEach(function (e) { box.append(small(e)); });
    var items = node('ul', 'tw-import-rows'); list(p.rows).slice(0, 8).forEach(function (r) { items.append(node('li', '', (r.environment === 'paper' ? 'Paper' : 'Live') + ' · ' + r.symbol + ' · ' + r.side + ' ' + number(r.qty) + ' at ' + money(r.price) + ' · ' + time(r.executed_at))); }); box.append(items);
    if (list(p.rows).length > 8) box.append(small('Showing the first 8 of ' + p.rows.length + ' execution rows.'));
    if (p.ok) box.append(button('Confirm import', 'trade-import-confirm', function () { var result = engine().commitImport(importPreview); if (mutate(result, 'Import complete. ' + (result.added || 0) + ' fills added; ' + (result.duplicates || 0) + ' duplicates skipped.')) { importPreview = null; importOpen = false; paintStatus(); paintBody(); } }, true));
  }
  function paintActivity() {
    var d = derived(), s = state(); panel.append(sectionHeading('', 'Your trade history', 'Real results from matched fills. Live and paper money stay separate.'));
    var totals = node('div', 'tw-tracker-totals'); totals.id = 'trade-performance'; ['live', 'paper'].forEach(function (env) {
      var values = d.totals[env], count = list(d.closed).filter(function (r) { return r.environment === env; }).length;
      var box = node('section', 'tw-tracker-total'); box.append(node('p', 'tw-eyebrow', env === 'live' ? 'Live money' : 'Paper money'), node('strong', 'tw-tracker-total-value', count ? money(values.realized_net) : '—'), small(count ? 'Realized P/L after fees' : 'No completed exits'));
      var detail = node('details', 'tw-details'); detail.append(node('summary', '', 'How this is measured')); detail.append(small('Before fees: ' + (count ? money(values.realized_gross) : 'No matched exits') + '. ' + count + ' matched exit lots. Earlier buys match first. Missing fees or history keep affected totals unavailable.')); box.append(detail); totals.append(box);
    }); panel.append(totals);
    var exits = node('details', 'tw-details tw-tracker-exits'); exits.append(node('summary', '', 'Completed exits · ' + list(d.closed).length)); var exitList = node('div', 'tw-tracker-list'); exitList.id = 'trade-closed-exits';
    list(d.closed).slice().reverse().slice(0, 40).forEach(function (r, i) { var item = trackerRow('exit:' + i + ':' + r.symbol + ':' + r.exited_at, r.symbol, (r.environment === 'paper' ? 'Paper' : 'Live') + ' · ' + number(r.qty) + ' shares', money(r.profit), 'before fees'); var dl = node('dl', 'tw-tracker-metrics'); dl.append(metric('Entry', money(r.entry)), metric('Exit', money(r.exit)), metric('Return on original risk', finite(r.r) ? r.r.toFixed(2) + 'R' : 'Not available')); item.body.append(dl, small(time(r.exited_at))); exitList.append(item.row); });
    if (!list(d.closed).length) exitList.append(small('Completed exits will appear after a sell fill matches an earlier buy.')); if (list(d.closed).length > 40) exitList.append(small('Showing the latest 40 matched exits. Your backup contains the complete execution record.')); exits.append(exitList); panel.append(exits);
    var ledger = node('div', 'tw-tracker-list'); ledger.id = 'trade-execution-list'; ledger.append(node('h4', 'tw-tracker-label', 'Recorded fills'));
    var voids = new Set(list(s.voids).map(function (v) { return v.fill_id; }));
    list(s.fills).slice().sort(function (a, b) { return String(b.executed_at).localeCompare(String(a.executed_at)); }).slice(0, 100).forEach(function (f) {
      var corrected = voids.has(f.id), item = trackerRow('fill:' + f.id, f.symbol, (f.environment === 'paper' ? 'Paper' : 'Live') + ' · ' + (f.side === 'buy' ? 'Bought ' : 'Sold ') + number(f.qty) + (corrected ? ' · Corrected' : ''), money(f.price), 'fill price'); item.row.dataset.tradeExecution = f.execution_id;
      item.body.append(small((f.source === 'manual' ? 'Confirmed by you' : 'Broker execution') + ' · ' + time(f.executed_at)), small('Execution ' + f.execution_id + ' · account ' + accountLabel(f.account_id)));
      if (corrected) item.body.append(small('Corrected record. Retained in history and excluded from totals.'));
      if (f.source === 'manual' && !corrected) { var details = node('details', 'tw-inline-confirm'); details.append(node('summary', '', 'Correct this record'), small('The original stays in history and is excluded from totals. Record a replacement afterward if needed.')); var reason = field('What is incorrect?', 'trade-correct-' + f.id.replace(/[^a-zA-Z0-9-]/g, '').slice(-60), { type: 'text', maxlength: '500' }, '', null); details.append(reason); details.append(button('Confirm correction', null, function () { if (mutate(engine().voidFill(f.id, { confirmed: true, reason: reason.querySelector('input').value }), 'Execution marked as corrected. The original record is retained.')) { paintStatus(); paintBody(); } })); item.body.append(details); } ledger.append(item.row);
    });
    if (!s.fills.length) ledger.append(empty('A clean start.', 'Your confirmed trades will appear here. Record your first fill in Holdings.'));
    if (s.fills.length > 100) ledger.append(small('Showing the latest 100 executions. Export a backup for the full record.')); panel.append(ledger);
    var tools = node('details', 'tw-details'); tools.append(node('summary', '', 'Export & backup')); var actions = node('div', 'tw-actions'); actions.append(button('Full backup (JSON)', 'trade-export-json', function () { download('spicystock-trade-record.json', engine().exportJSON(), 'application/json'); }), button('Execution CSV', 'trade-export-csv', function () { download('spicystock-executions.csv', engine().exportCSV(), 'text/csv'); })); tools.append(actions, small('Use a full backup to move this record to another browser or device.')); panel.append(tools);
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
    if (tracker && tracker.open) tracker.close(); document.documentElement.classList.remove('tw-modal-open'); activeTab = 'today';
    var navigation = node('nav', 'tw-desk-nav'); navigation.setAttribute('aria-label', 'Trading workspace');
    navigation.append(button('Trading desk', 'trade-nav-desk', function () { showTab('today'); focus('trade-market-title'); }), button('Research studio ↗', 'trade-nav-research', function () { openResearch('research-report'); }), button('My tracker', 'trade-nav-tracker', function () { showTab('positions'); }), button('My limits', 'trade-nav-limits', showProfile)); host.append(navigation);
    statusPanel = node('section', 'tw-today-status'); statusPanel.id = 'trade-today-status'; host.append(statusPanel);
    notice = node('p', 'tw-notice', message); notice.id = 'trade-notice'; notice.setAttribute('role', 'status'); notice.setAttribute('aria-live', 'polite'); host.append(notice);
    homePanel = node('div', 'tw-panel'); homePanel.id = 'trade-panel'; host.append(homePanel); panel = homePanel;
    tracker = node('dialog', 'tw-tracker'); tracker.id = 'trade-tracker'; tracker.setAttribute('aria-labelledby', 'trade-tracker-title');
    var heading = node('div', 'tw-tracker-heading'); var titles = node('div'); titles.append(node('p', 'tw-eyebrow', '03 / LOG & TRACK'), elId(node('h2', '', 'My tracker'), 'trade-tracker-title')); heading.append(titles, button('Close', 'trade-close-tracker', function () { tracker.close(); })); tracker.append(heading);
    var tabs = node('div', 'tw-tabs'); tabs.setAttribute('role', 'tablist'); tabs.setAttribute('aria-label', 'My tracker'); tabs.append(tabButton('positions', 'Holdings'), tabButton('plans', 'Plans'), tabButton('activity', 'History'));
    tabs.addEventListener('keydown', function (event) { if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return; event.preventDefault(); var names = ['positions', 'plans', 'activity'], at = names.indexOf(activeTab); var next = event.key === 'Home' ? 0 : event.key === 'End' ? 2 : (at + (event.key === 'ArrowRight' ? 1 : -1) + 3) % 3; showTab(names[next], true); }); tracker.append(tabs);
    trackerMount = node('div', 'tw-panel tw-tracker-panel'); trackerMount.id = 'trade-tracker-panel'; trackerMount.setAttribute('role', 'tabpanel'); tracker.append(trackerMount); host.append(tracker);
    tracker.addEventListener('close', function () { if (tracker.open) return; document.documentElement.classList.remove('tw-modal-open'); if (activeTab !== 'today') { activeTab = 'today'; panel = homePanel; host.insertBefore(notice, homePanel); paintStatus(); if (returnFocus && returnFocus.isConnected) returnFocus.focus({ preventScroll: true }); else { var opener = host.querySelector('#trade-open-tracker') || host.querySelector('#trade-next-action'); if (opener) opener.focus({ preventScroll: true }); } } });
    tracker.addEventListener('click', function (e) { if (e.target === tracker) { var r = tracker.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) tracker.close(); } });
    paintTabs(); paintStatus(); paintBody();
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
