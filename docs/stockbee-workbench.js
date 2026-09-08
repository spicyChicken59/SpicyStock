/* Stockbee's published scan and qualitative setup review, kept separate from
   SpicyStock's stricter scoring pipeline. Values come from the saved session. */
(function () {
  'use strict';
  var state = { date: '', tab: 'breakout', query: '', selected: '', data: null };
  var SOURCES = {
    scan: 'https://stockbee.blogspot.com/2015/11/how-to-use-4-breakout-scan-to-make-money.html',
    checklist: 'https://stockbee.blogspot.com/2020/12/how-to-make-money-using-setups-detailed.html',
    anticipation: 'https://stockbee.blogspot.com/2017/04/how-to-find-bullish-breakout.html'
  };
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function finite(value) { return typeof value === 'number' && Number.isFinite(value); }
  function number(value, places) {
    return finite(value) ? value.toLocaleString('en-US', { maximumFractionDigits: places === undefined ? 2 : places }) : 'Not measured';
  }
  function percent(value, signed) {
    return finite(value) ? (signed && value > 0 ? '+' : '') + value.toFixed(2) + '%' : 'Not measured';
  }
  function multiple(value) { return finite(value) ? value.toFixed(2) + '×' : 'Not measured'; }
  function price(value) { return finite(value) ? '$' + value.toFixed(2) : 'Not measured'; }
  function button(label, cls) { var node = el('button', cls || 'sb-button', label); node.type = 'button'; return node; }
  function link(label, href) { var node = el('a', 'sb-source-link', label); node.href = href; return node; }
  function list(value) { return Array.isArray(value) ? value : []; }
  function snapshot() {
    var value = state.data && state.data.run && state.data.run.stockbee;
    return value && value.version === 1 && typeof value === 'object'
      && value.date === state.data.run.date ? value : null;
  }
  function rowsFor(tab) {
    var data = snapshot();
    return data ? list(tab === 'anticipation' ? data.anticipation && data.anticipation.rows : data.scan && data.scan.rows)
      .filter(function (row) { return row && typeof row.ticker === 'string'; }) : [];
  }
  function scored(ticker) {
    return list(state.data && state.data.candidates).find(function (row) { return row.ticker === ticker; });
  }
  function metric(label, value, cls) {
    var item = el('div', cls || 'sb-metric'); item.append(el('dt', '', label), el('dd', '', value)); return item;
  }
  function sources() {
    var details = el('details', 'sb-method');
    details.append(el('summary', '', 'The published method, and what this app adds'));
    var content = el('div', 'sb-method-content');
    content.append(el('p', '', 'The published 4% scan is a starting list: close at least 4% above the previous close, more volume than the previous session, and at least 100,000 shares. It is followed by chart review, not an automatic buy verdict.'));
    content.append(link('Stockbee · the published 4% scan (2015)', SOURCES.scan));
    content.append(el('p', '', '2LYNCH is a qualitative setup lens. The 2020 explanation cautions about two prior up days, with room for a small up day; the older 2017 process uses three. The measurements here support visual judgment. They are not a six-point Stockbee score.'));
    content.append(link('Stockbee · the 2LYNCH setup explanation (2020)', SOURCES.checklist));
    content.append(el('p', '', 'Anticipation is a separate preparation list. Our transparent proxy looks for an established trend with a quiet, compressed session. It does not reproduce Stockbee’s proprietary scans or assert that a breakout will follow.'));
    content.append(link('Stockbee · preparing for bullish breakouts (2017)', SOURCES.anticipation));
    content.append(el('p', '', 'SpicyStock’s AI ranking is a separate, stricter path: a price floor, relative-volume and dollar-volume cuts, its own three-of-six proxy gate, and a scoring-call cap. A name can match the published scan without appearing in the scored list. Those additional cuts are app choices, not Stockbee’s scan formula.'));
    details.append(content); return details;
  }
  function pulse() {
    var data = snapshot(), run = state.data.run || {}, scope = data && data.scope || {};
    var panel = el('section', 'sb-pulse'); panel.setAttribute('aria-labelledby', 'stockbee-pulse-title');
    var heading = el('div', 'sb-section-heading');
    var intro = el('div'); intro.append(el('p', 'sb-kicker', '01 / THE BACKDROP'));
    var title = el('h3', '', 'The universe pulse.'); title.id = 'stockbee-pulse-title'; intro.append(title);
    heading.append(intro, el('span', 'sb-scope-pill', 'Curated subset · not the whole market')); panel.append(heading);
    var scopeLabel = scope.label || run.universe && run.universe.label || 'Recorded universe';
    var coverage = el('p', 'sb-caption'); coverage.id = 'stockbee-coverage';
    coverage.textContent = data ? scopeLabel + ' · ' + number(scope.measured, 0) + ' measured / ' + number(scope.requested, 0) + ' requested · ' + (data.date || run.date || 'Date not recorded')
      : scopeLabel + ' · this older snapshot does not include breadth measurements.';
    panel.append(coverage);
    var days = list(data && data.breadth && data.breadth.days).filter(function (day) {
      return day && finite(day.up4) && finite(day.down4) && finite(day.measured);
    }).slice(-10);
    var ratios = data && data.breadth && data.breadth.ratios || {};
    var stats = el('dl', 'sb-pulse-stats');
    stats.append(metric('5-session up / down ratio', multiple(ratios.d5)), metric('10-session up / down ratio', multiple(ratios.d10)));
    panel.append(stats);
    if (!days.length) {
      var empty = el('div', 'sb-empty sb-empty--compact');
      empty.append(el('strong', '', 'Breadth not yet recorded.'), el('p', '', 'A future saved scan will add daily 4% advances and declines for this universe. Missing history is not zero activity.'));
      panel.append(empty);
    } else {
      var legend = el('p', 'sb-pulse-legend'); legend.append(el('span', 'sb-up-label', '↑ 4% advances'), el('span', 'sb-down-label', '↓ 4% declines'));
      panel.append(legend);
      var bars = el('ol', 'sb-pulse-bars');
      var maximum = Math.max.apply(null, days.map(function (day) { return Math.max(day.up4, day.down4); }).concat([1]));
      days.forEach(function (day) {
        var row = el('li', 'sb-pulse-day');
        var date = el('time', '', String(day.date || 'Undated').slice(5)); date.dateTime = day.date || '';
        var tracks = el('div', 'sb-pulse-tracks');
        [['up', day.up4], ['down', day.down4]].forEach(function (pair) {
          var track = el('div', 'sb-pulse-track');
          var fill = el('span', 'sb-pulse-fill sb-pulse-fill--' + pair[0]); fill.style.width = Math.max(0, Math.min(100, pair[1] / maximum * 100)) + '%'; fill.setAttribute('aria-hidden', 'true');
          track.append(fill); tracks.append(track);
        });
        var values = el('span', 'sb-pulse-values', '↑ ' + number(day.up4, 0) + ' / ↓ ' + number(day.down4, 0));
        row.append(date, tracks, values);
        row.setAttribute('aria-label', day.date + ': ' + number(day.up4, 0) + ' advances of 4% or more, ' + number(day.down4, 0) + ' declines of 4% or more, ' + number(day.measured, 0) + ' stocks measured.');
        bars.append(row);
      });
      panel.append(bars);
    }
    panel.append(el('p', 'sb-footnote', 'Both breadth counts also require volume above the previous session and at least 100,000 shares. Ratios divide summed daily 4% advances by summed daily 4% declines. No ratio is shown without enough history or with a zero decline total. Coverage can vary by day. This subset cannot establish a whole-market regime.'));
    return panel;
  }
  function queueHeader(tab) {
    var data = snapshot(), group = data && (tab === 'anticipation' ? data.anticipation : data.scan);
    var header = el('div', 'sb-queue-heading');
    header.append(el('h3', '', tab === 'anticipation' ? 'Before the move.' : 'The move has printed.'));
    header.append(el('p', 'sb-caption', tab === 'anticipation'
      ? 'A quiet-day preparation list. These are not 4% breakout matches.'
      : 'Recorded matches to the published 4% price-and-volume scan. Review their charts before building a plan.'));
    var formula = el('p', 'sb-formula'); formula.id = 'stockbee-rules-' + tab;
    formula.textContent = tab === 'anticipation'
      ? 'App proxy · TI 7/65 ≥ 1.05× · 3-session minimum volume ≥ 100k · price ≥ $3 · move within ±1% · mean daily range: latest 7 / preceding 60 sessions ≤ 0.75×'
      : 'Close / previous close ≥ 1.04 · volume > previous volume · volume ≥ 100,000';
    header.append(formula);
    if (data) header.append(el('p', 'sb-footnote', number(group && group.matched, 0) + ' matches in the measured universe · ' + number(group && group.shown, 0) + ' setup records saved for review.'));
    return header;
  }
  function queueCard(row) {
    var card = button('', 'sb-setup-card');
    card.setAttribute('data-stockbee-select', row.ticker);
    card.setAttribute('aria-pressed', String(state.selected === row.ticker));
    card.setAttribute('aria-controls', 'stockbee-inspector');
    var heading = el('span', 'sb-setup-heading');
    heading.append(el('strong', 'sb-ticker', row.ticker), el('span', 'sb-gain', percent(row.gain_pct, true)));
    var value = el('span', 'sb-setup-metrics', price(row.close) + ' · ' + number(row.volume, 0) + ' shares');
    var volume = el('span', 'sb-setup-meta', multiple(row.volume_vs_previous) + ' vs previous volume');
    var status = el('span', 'sb-setup-status', scored(row.ticker) ? 'Also in the scored list' : 'Not in the scored list');
    card.append(heading, value, volume, status);
    card.addEventListener('click', function () {
      state.selected = row.ticker;
      document.querySelectorAll('#stockbee-workspace [data-stockbee-select]').forEach(function (node) {
        node.setAttribute('aria-pressed', String(node.getAttribute('data-stockbee-select') === state.selected));
      });
      renderInspector(row);
      if (window.matchMedia && window.matchMedia('(max-width: 900px)').matches) {
        var heading = document.getElementById('stockbee-selected-title');
        if (heading) { heading.focus({ preventScroll: true }); heading.scrollIntoView({ behavior: 'auto', block: 'start' }); }
      }
    });
    return card;
  }
  function renderQueue() {
    var host = document.getElementById('stockbee-workspace'); if (!host) return;
    var all = rowsFor(state.tab);
    var rows = all.filter(function (row) { return row.ticker.toLowerCase().indexOf(state.query.toLowerCase().trim()) !== -1; });
    if (!rows.some(function (row) { return row.ticker === state.selected; })) state.selected = rows.length ? rows[0].ticker : '';
    ['breakout', 'anticipation'].forEach(function (tab) {
      var node = document.getElementById('stockbee-tab-' + tab), panel = document.getElementById('stockbee-panel-' + tab);
      node.setAttribute('aria-selected', String(state.tab === tab)); node.tabIndex = state.tab === tab ? 0 : -1;
      panel.hidden = state.tab !== tab;
    });
    var panel = document.getElementById('stockbee-panel-' + state.tab);
    var listHost = el('div', 'sb-setup-list'); listHost.id = 'stockbee-queue-' + state.tab;
    if (rows.length) rows.forEach(function (row) { listHost.append(queueCard(row)); });
    else {
      var empty = el('div', 'sb-empty');
      empty.append(el('strong', '', !snapshot() ? 'This scan view starts with the next recorded run.' : state.query.trim() ? 'No saved setup matches that ticker.' : state.tab === 'anticipation' ? 'No anticipation setups recorded.' : 'No 4% scan matches recorded.'));
      empty.append(el('p', '', !snapshot()
        ? 'The current archive predates this strategy view. It contains no complete scan queue, so we cannot reconstruct one from only the scored names.'
        : state.query.trim() ? 'Search covers the saved setup records, not every ticker in the universe.' : 'An empty list is useful information. The next saved scan will refresh this dated record.'));
      if (state.query.trim()) {
        var clear = button('Clear search');
        clear.addEventListener('click', function () { state.query = ''; var input = document.getElementById('stockbee-search'); input.value = ''; renderQueue(); input.focus(); }); empty.append(clear);
      }
      listHost.append(empty);
    }
    panel.replaceChildren(queueHeader(state.tab), listHost);
    document.getElementById('stockbee-search-results').textContent = snapshot()
      ? rows.length + ' of ' + all.length + ' saved ' + (state.tab === 'anticipation' ? 'anticipation' : 'breakout') + ' setups shown.'
      : 'Strategy scan measurements are not yet recorded for this snapshot.';
    renderInspector(rows.find(function (row) { return row.ticker === state.selected; }));
  }
  function svgNode(tag, attributes) {
    var node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.keys(attributes || {}).forEach(function (key) { node.setAttribute(key, attributes[key]); }); return node;
  }
  function chart(row) {
    var figure = el('figure', 'sb-chart');
    var bars = list(row.series).filter(function (bar) {
      return bar && [bar.open, bar.high, bar.low, bar.close].every(finite) && bar.high >= bar.low && bar.low > 0;
    });
    if (!bars.length) { figure.append(el('p', 'sb-caption', 'No candle history was recorded for this setup.')); return figure; }
    var maximum = Math.max.apply(null, bars.map(function (bar) { return bar.high; }));
    var minimum = Math.min.apply(null, bars.map(function (bar) { return bar.low; }));
    var span = Math.max(maximum - minimum, maximum * 0.02, 0.01), ceiling = maximum + span * 0.06, floor = minimum - span * 0.06;
    var highestVolume = Math.max.apply(null, bars.map(function (bar) { return finite(bar.volume) ? bar.volume : 0; }).concat([1]));
    var svg = svgNode('svg', { viewBox: '0 0 640 310', role: 'img', 'aria-label': row.ticker + ': ' + bars.length + ' recorded daily candles from ' + bars[0].date + ' through ' + bars[bars.length - 1].date + '. Last close ' + price(bars[bars.length - 1].close) + '. Exact prices are in the candle data table below.' });
    var chartWidth = 616, unit = chartWidth / bars.length;
    function y(value) { return 12 + (ceiling - value) / (ceiling - floor) * 218; }
    for (var i = 0; i < 4; i += 1) svg.append(svgNode('line', { x1: 8, x2: 632, y1: 14 + i * 72, y2: 14 + i * 72, 'class': 'sb-chart-grid' }));
    svg.append(svgNode('line', { x1: 8, x2: 632, y1: 245, y2: 245, 'class': 'sb-chart-grid' }));
    bars.forEach(function (bar, index) {
      var x = 12 + unit * (index + 0.5), width = Math.min(13, unit * 0.62), cls = bar.close >= bar.open ? 'sb-candle-up' : 'sb-candle-down';
      var group = svgNode('g', { 'class': cls });
      var title = svgNode('title'); title.textContent = bar.date + ': open ' + price(bar.open) + ', high ' + price(bar.high) + ', low ' + price(bar.low) + ', close ' + price(bar.close) + ', volume ' + number(bar.volume, 0); group.append(title);
      group.append(svgNode('line', { x1: x, x2: x, y1: y(bar.high), y2: y(bar.low), 'class': 'sb-candle-wick' }));
      group.append(svgNode('rect', { x: x - width / 2, y: Math.min(y(bar.open), y(bar.close)), width: width, height: Math.max(1.5, Math.abs(y(bar.open) - y(bar.close))), 'class': 'sb-candle-body' }));
      if (finite(bar.volume) && bar.volume >= 0) {
        var height = bar.volume / highestVolume * 48;
        group.append(svgNode('rect', { x: x - width / 2, y: 305 - height, width: width, height: height, 'class': 'sb-candle-volume' }));
      }
      svg.append(group);
    });
    var extents = el('div', 'sb-chart-extents'); extents.append(el('span', '', 'Price range ' + price(minimum) + '–' + price(maximum)), el('span', '', 'Volume below'));
    var dates = el('div', 'sb-chart-dates'); dates.append(el('span', '', bars[0].date), el('span', '', bars[bars.length - 1].date));
    figure.append(extents, svg, dates);
    figure.append(el('figcaption', 'sb-footnote', 'Recorded daily bars · blue closes at or above its open; red closes below. This view is a saved session, not a live quote.'));
    var disclosure = el('details', 'sb-candle-data'); disclosure.append(el('summary', '', 'Read exact candle data (' + bars.length + ' sessions)'));
    var scroll = el('div', 'sc-table-wrap sb-bars-table'); scroll.tabIndex = 0; scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', row.ticker + ' daily candle data; scroll horizontally for all columns');
    var table = el('table');
    var caption = el('caption', '', row.ticker + ' recorded daily prices and share volume');
    var thead = el('thead'), header = el('tr');
    ['Session', 'Open', 'High', 'Low', 'Close', 'Volume'].forEach(function (label) { var th = el('th', '', label); th.scope = 'col'; header.append(th); }); thead.append(header);
    var tbody = el('tbody');
    bars.slice().reverse().forEach(function (bar) {
      var tr = el('tr'); var th = el('th', '', bar.date); th.scope = 'row'; tr.append(th);
      [price(bar.open), price(bar.high), price(bar.low), price(bar.close), number(bar.volume, 0)].forEach(function (value) { tr.append(el('td', '', value)); }); tbody.append(tr);
    });
    table.append(caption, thead, tbody); scroll.append(table); disclosure.append(scroll); figure.append(disclosure); return figure;
  }
  function lens(row) {
    var section = el('section', 'sb-lynch'); section.setAttribute('aria-labelledby', 'stockbee-lynch-title');
    var heading = el('h4', '', '2LYNCH · read the shape.'); heading.id = 'stockbee-lynch-title';
    section.append(heading, el('p', 'sb-caption', 'Six questions for visual review. Measured proxies support judgment; they do not produce a Stockbee pass score.'));
    var disclosure = el('details', 'sb-lynch-disclosure'); disclosure.id = 'stockbee-lynch-questions';
    disclosure.append(el('summary', '', 'Review the 2LYNCH setup questions'));
    var prompts = [
      ['2', 'Is it early enough?', 'Check prior up days. The 2020 explanation cautions about two, with discretion for a small up day.', row ? number(row.prior_up_days, 0) + ' consecutive prior up days' : 'Prior up days not measured'],
      ['L', 'Is the move linear?', 'Look for an orderly trend instead of a jagged, wide-swinging advance.', row ? 'Trend-intensity proxy (7/65): ' + multiple(row.trend_intensity) : 'Trend intensity not measured'],
      ['Y', 'Is this a young move?', 'Locate this burst in the wider trend. Earlier bursts and extension are context, not an age verdict.', row ? number(row.prior_bursts_20, 0) + ' prior 4% bursts / 20 sessions · ' + percent(row.extension_sma20_pct, true) + ' vs SMA20' : 'Prior bursts and extension not measured'],
      ['N', 'Was the prior day narrow or negative?', 'Inspect the session before the breakout for a quiet or negative day.', row ? 'Previous move ' + percent(row.prior_day_move_pct, true) + ' · daily range ' + percent(row.prior_day_range_pct) : 'Previous-day move and range not measured'],
      ['C', 'Is the base quiet and orderly?', 'Review a shallow, controlled base; the published explanation allows at most one 4% down day in it. The app uses the prior seven sessions as a base proxy.', row ? number(row.base_down4_count, 0) + ' down-4% days in prior 7 sessions · base range ' + percent(row.base_range_pct) : 'Base breakdowns and depth not measured'],
      ['H', 'Did it close near the high?', 'A close near the top of the daily range shows where the session finished; inspect the candle.', row ? 'Close position: ' + (finite(row.close_position) ? (row.close_position * 100).toFixed(1) + '% of the low-to-high range' : 'Not measured') : 'Close position not measured']
    ];
    var checklist = el('ol', 'sb-lynch-list');
    prompts.forEach(function (prompt) {
      var item = el('li', 'sb-lynch-item'), copy = el('div');
      copy.append(el('h5', '', prompt[1]), el('p', '', prompt[2]), el('p', 'sb-proxy', 'Measured context · ' + prompt[3]));
      item.append(el('span', 'sb-lynch-letter', prompt[0]), copy); checklist.append(item);
    });
    disclosure.append(checklist, link('Read Stockbee’s original explanation ↗', SOURCES.checklist));
    section.append(disclosure); return section;
  }
  function renderInspector(row) {
    var host = document.getElementById('stockbee-inspector'); if (!host) return;
    var content = el('div', 'sb-inspector-content');
    if (!row) {
      content.append(el('p', 'sb-kicker', '03 / KNOW THE SETUP'), el('h3', '', 'A chart before a score.'));
      content.append(el('p', 'sb-caption', 'Choose a saved setup to inspect its candles and volume. The 2LYNCH questions are available below.'));
      content.append(lens(null)); host.replaceChildren(content); return;
    }
    var heading = el('div', 'sb-inspector-heading');
    var names = el('div'), selectedTitle = el('h3', '', row.ticker); selectedTitle.id = 'stockbee-selected-title'; selectedTitle.tabIndex = -1;
    names.append(el('p', 'sb-kicker', '03 / KNOW THE SETUP'), selectedTitle);
    var quote = el('div', 'sb-inspector-quote'); quote.append(el('strong', '', price(row.close)), el('span', '', percent(row.gain_pct, true)));
    heading.append(names, quote); content.append(heading);
    content.append(el('p', 'sb-caption', (row.date || state.date || 'Date not recorded') + ' · ' + (state.tab === 'anticipation' ? 'Anticipation proxy match' : 'Published 4% scan match') + ' · ' + (scored(row.ticker) ? 'Also in the scored list' : 'Not in the scored list')));
    var facts = el('dl', 'sb-setup-facts');
    facts.append(metric('Previous close', price(row.prev_close)), metric('Share volume', number(row.volume, 0)), metric('Previous volume', number(row.prev_volume, 0)), metric('Volume / previous', multiple(row.volume_vs_previous)));
    facts.append(state.tab === 'anticipation'
      ? metric('Daily-range compression · 7 / 60', multiple(row.compression_ratio))
      : metric('Range / prior 7-session norm', multiple(row.range_expansion)));
    content.append(facts, chart(row));
    var actions = el('div', 'sb-inspector-actions');
    var plan = button('Plan this setup ↗', 'sb-button sb-button--primary'); plan.id = 'stockbee-plan-setup';
    plan.addEventListener('click', function () {
      window.dispatchEvent(new CustomEvent('stockbee:plan', { detail: row }));
    });
    actions.append(plan);
    if (window.SCStockDesk && typeof window.SCStockDesk.toggleSaved === 'function') {
      var save = button('', 'sb-button'); save.id = 'stockbee-save'; save.setAttribute('data-stockbee-save', row.ticker);
      var isSaved = typeof window.SCStockDesk.hasSaved === 'function' && window.SCStockDesk.hasSaved(row.ticker);
      save.textContent = isSaved ? 'Saved to research' : 'Save research'; save.setAttribute('aria-pressed', String(!!isSaved));
      save.addEventListener('click', function () { window.SCStockDesk.toggleSaved(row.ticker); }); actions.append(save);
    }
    content.append(actions, el('p', 'sb-footnote', 'A plan is your own price-and-risk worksheet. Matching a scan does not determine an entry, stop, position size, or trade decision.'), lens(row));
    host.replaceChildren(content);
  }
  function render(data) {
    var host = document.getElementById('stockbee-workspace'); if (!host) return;
    data = data || {};
    var date = data.run && data.run.date || '';
    if (state.date !== date) { state.date = date; state.selected = ''; state.query = ''; }
    state.data = data;
    var active = document.activeElement, activeId = active && host.contains(active) ? active.id : '';
    var selection = activeId === 'stockbee-search' ? [active.selectionStart, active.selectionEnd] : null;
    var intro = el('div', 'sb-heading');
    var text = el('div'); text.append(el('p', 'sb-kicker', 'THE 4% WORKBENCH'));
    var title = el('h2', '', 'Find the burst. Read the setup.'); title.id = 'stockbee-title'; text.append(title);
    text.append(el('p', 'sb-intro', 'Start with Stockbee’s published scan. Read the market subset, prepare tomorrow’s list, and inspect the chart before the AI ranking.'));
    intro.append(text, el('span', 'sb-edition', 'SAVED SESSION / ' + (date || 'NOT RECORDED')));
    var panel = el('section', 'sb-queues'); panel.setAttribute('aria-labelledby', 'stockbee-queue-title');
    var heading = el('div', 'sb-section-heading'), headingText = el('div');
    headingText.append(el('p', 'sb-kicker', '02 / THE TWO LISTS'));
    var h3 = el('h3', '', 'Breakout or build-up.'); h3.id = 'stockbee-queue-title'; headingText.append(h3); heading.append(headingText); panel.append(heading);
    var tabs = el('div', 'sb-tabs'); tabs.setAttribute('role', 'tablist'); tabs.setAttribute('aria-label', 'Stockbee setup lists');
    ['breakout', 'anticipation'].forEach(function (tab) {
      var source = snapshot(), group = source && (tab === 'anticipation' ? source.anticipation : source.scan);
      var control = button(tab === 'breakout' ? '4% breakouts' : 'Anticipation', 'sb-tab');
      control.id = 'stockbee-tab-' + tab; control.setAttribute('role', 'tab'); control.setAttribute('aria-controls', 'stockbee-panel-' + tab);
      var badge = el('span', 'sb-tab-count', source ? number(group && group.matched, 0) : '—'); control.append(badge);
      control.addEventListener('click', function () { state.tab = tab; state.selected = ''; renderQueue(); });
      control.addEventListener('keydown', function (event) {
        if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].indexOf(event.key) < 0) return;
        event.preventDefault();
        state.tab = event.key === 'Home' ? 'breakout' : event.key === 'End' ? 'anticipation' : state.tab === 'breakout' ? 'anticipation' : 'breakout';
        state.selected = ''; renderQueue(); document.getElementById('stockbee-tab-' + state.tab).focus();
      }); tabs.append(control);
    });
    panel.append(tabs);
    var searchField = el('div', 'sb-search');
    var label = el('label', '', 'Find a saved setup'); label.htmlFor = 'stockbee-search';
    var input = el('input'); input.id = 'stockbee-search'; input.type = 'search'; input.placeholder = 'Search ticker'; input.autocomplete = 'off'; input.spellcheck = false; input.value = state.query;
    input.addEventListener('input', function () { state.query = input.value; renderQueue(); });
    var status = el('p', 'sb-footnote'); status.id = 'stockbee-search-results'; status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
    input.setAttribute('aria-describedby', status.id); searchField.append(label, input, status); panel.append(searchField);
    ['breakout', 'anticipation'].forEach(function (tab) {
      var tabPanel = el('div', 'sb-tab-panel'); tabPanel.id = 'stockbee-panel-' + tab; tabPanel.setAttribute('role', 'tabpanel'); tabPanel.setAttribute('aria-labelledby', 'stockbee-tab-' + tab); panel.append(tabPanel);
    });
    var workspace = el('div', 'sb-workspace-grid');
    var inspector = el('section', 'sb-inspector'); inspector.id = 'stockbee-inspector'; inspector.setAttribute('aria-label', 'Selected setup chart and 2LYNCH context');
    workspace.append(panel, inspector);
    host.classList.add('stockbee-workbench'); host.replaceChildren(intro, pulse(), workspace, sources()); host.hidden = false;
    renderQueue();
    if (activeId) {
      var replacement = document.getElementById(activeId);
      if (replacement) { replacement.focus({ preventScroll: true }); if (selection && replacement.setSelectionRange) replacement.setSelectionRange(selection[0], selection[1]); }
    }
  }
  window.addEventListener('stock:desk-change', function () {
    var save = document.getElementById('stockbee-save');
    if (!save || !window.SCStockDesk || typeof window.SCStockDesk.hasSaved !== 'function') return;
    var saved = window.SCStockDesk.hasSaved(save.getAttribute('data-stockbee-save'));
    save.textContent = saved ? 'Saved to research' : 'Save research'; save.setAttribute('aria-pressed', String(saved));
  });
  window.SCStockbee = { render: render };
}());
