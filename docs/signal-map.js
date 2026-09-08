/* A presentation of recorded candidates. Filters never change the source ranking
   or measurements; saved choices are delegated to the device's research desk. */
(function () {
  'use strict';
  var selected = null;
  var observer;
  var resize;
  var refreshDesk;
  var lensState = { session: null, search: '', filter: 'all', order: 'rank' };
  var ns = 'http://www.w3.org/2000/svg';
  function node(tag, className, text) {
    var n = document.createElement(tag);
    if (className) n.className = className;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function svgNode(tag, attrs, text) {
    var n = document.createElementNS(ns, tag);
    Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function finite(v) { return typeof v === 'number' && Number.isFinite(v); }
  function amount(v, suffix, signed) {
    return finite(v) ? (signed && v > 0 ? '+' : '') + v.toFixed(2) + suffix : 'Not recorded';
  }
  function fallback(c) { return !!c.provenance && c.provenance.source === 'fallback'; }
  function unknown(c) { return !c.provenance || (c.provenance.source !== 'claude' && c.provenance.source !== 'fallback'); }
  function sourceLabel(c) { return fallback(c) ? 'Checklist fallback' : unknown(c) ? (c.provenance && c.provenance.source ? 'Unrecognized score source' : 'Source not recorded') : 'Claude'; }
  function canPlot(c) { return finite(c.gain_pct) && finite(c.volume_ratio) && c.volume_ratio >= 0; }
  function render(data) {
    var root = document.getElementById('signal-content');
    if (!root) return;
    if (observer) observer.disconnect();
    if (resize) window.removeEventListener('resize', resize);
    if (refreshDesk) window.removeEventListener('stock:desk-change', refreshDesk);
    root.replaceChildren();
    var candidates = Array.isArray(data.candidates) ? data.candidates : [];
    var run = data.run || {};
    var points = candidates.map(function (c, index) { return { c: c, index: index }; }).filter(function (p) { return canPlot(p.c); });
    document.getElementById('signal-workspace').hidden = false;
    document.getElementById('signal-count').textContent = candidates.length + ' scored · ' + points.length + ' plotted';
    // Changing the return basis re-renders the same session; keep its research lens.
    var sessionKey = JSON.stringify([run.date || null, run.type || null]);
    if (lensState.session !== sessionKey) lensState = { session: sessionKey, search: '', filter: 'all', order: 'rank' };
    var query = lensState.search.trim().toLowerCase(), activeFilter = lensState.filter, order = lensState.order;
    var visibleIndexes = candidates.map(function (_, index) { return index; });
    var shortlistSize = finite(run.shortlist_size) ? Math.max(0, run.shortlist_size) : 0;

    var lens = node('div', 'signal-lens');
    var lensFields = node('div', 'signal-lens-fields');
    var searchLabel = node('label', 'signal-search');
    searchLabel.append(node('span', 'signal-field-label', 'Find a signal'));
    var search = node('input', 'signal-search-input');
    search.type = 'search';
    search.id = 'signal-search';
    search.placeholder = 'Ticker or scoring note';
    search.autocomplete = 'off';
    search.spellcheck = false;
    search.value = lensState.search;
    searchLabel.append(search);
    var sortLabel = node('label', 'signal-sort');
    sortLabel.append(node('span', 'signal-field-label', 'Arrange by'));
    var sort = node('select', 'signal-sort-input');
    sort.id = 'signal-sort';
    [['rank', 'Recorded rank'], ['gain', 'Highest daily gain'], ['volume', 'Highest relative volume']].forEach(function (entry) {
      var option = node('option', '', entry[1]); option.value = entry[0]; sort.append(option);
    });
    sort.value = order;
    sortLabel.append(sort);
    lensFields.append(searchLabel, sortLabel);
    var filters = node('div', 'signal-filters');
    filters.setAttribute('role', 'group');
    filters.setAttribute('aria-label', 'Filter recorded signals');
    var filterButtons = [];
    [['all', 'All'], ['shortlist', 'Shortlist'], ['claude', 'Claude'], ['fallback', 'Fallback'], ['volume', 'Volume ≥ 3×']].forEach(function (entry) {
      var chip = node('button', 'signal-filter', entry[1]);
      chip.type = 'button';
      chip.dataset.signalFilter = entry[0];
      chip.setAttribute('aria-pressed', String(entry[0] === 'all'));
      chip.addEventListener('click', function () { activeFilter = entry[0]; applyLens(); });
      filters.append(chip); filterButtons.push(chip);
    });
    var lensFooter = node('div', 'signal-lens-footer');
    var resultCount = node('p', 'signal-result-count');
    resultCount.id = 'signal-results';
    resultCount.setAttribute('role', 'status');
    resultCount.setAttribute('aria-live', 'polite');
    var clearFilters = node('button', 'signal-clear', 'Clear filters');
    clearFilters.type = 'button';
    clearFilters.addEventListener('click', function () {
      query = ''; activeFilter = 'all'; order = 'rank'; search.value = ''; sort.value = 'rank';
      applyLens(); search.focus();
    });
    lensFooter.append(resultCount, clearFilters);
    lens.append(lensFields, filters, lensFooter);
    search.addEventListener('input', function () { query = search.value.trim().toLowerCase(); applyLens(); });
    sort.addEventListener('change', function () { order = sort.value; applyLens(); });

    var layout = node('div', 'signal-layout');
    var panel = node('div', 'signal-panel');
    var heading = node('div', 'signal-panel-heading');
    heading.append(node('h3', '', 'Signal map'), node('span', 'signal-stamp', String(run.date || 'Date not recorded')));
    var surface = node('div', 'signal-surface');
    surface.setAttribute('role', 'group');
    surface.setAttribute('aria-label', 'Scored candidates by daily gain and relative volume');
    var mapNote = node('p', 'signal-map-note', 'Each point is a scored candidate. Position shows measurements, not a predicted return.');
    var legend = node('div', 'signal-map-legend');
    legend.append(node('span', 'signal-key', '● Claude'), node('span', 'signal-key', '○ Checklist fallback'));
    if (candidates.some(unknown)) legend.append(node('span', 'signal-key', '◌ Source unknown'));
    var selection = node('p', 'signal-selection', 'Choose a candidate to inspect its recorded measurements.');
    selection.setAttribute('role', 'status');
    selection.setAttribute('aria-live', 'polite');
    panel.append(heading, surface, legend, selection, mapNote);
    var cards = node('div', 'signal-cards');
    cards.setAttribute('role', 'region');
    cards.setAttribute('aria-label', 'Scored candidate notes');
    // A keyboard reader can scroll this region even when no point has focus.
    cards.tabIndex = 0;
    layout.append(panel, cards);
    root.append(lens, layout);
    var cardNodes = [], buttons = [], markerNodes = [], deskButtons = [];
    var noMatches = node('div', 'signal-no-matches');
    noMatches.append(node('h3', '', 'No signals match this lens.'), node('p', '', 'Try a different ticker, search the scoring notes, or clear your filters to see every recorded candidate.'));
    noMatches.hidden = true;
    var selectedIndex = candidates.findIndex(function (c) { return c.ticker === selected; });
    if (selectedIndex < 0 && candidates.length) selectedIndex = 0;

    function select(index, reveal, announce) {
      var c = candidates[index];
      if (!c || visibleIndexes.indexOf(index) < 0) return;
      selectedIndex = index;
      selected = c.ticker;
      cardNodes.forEach(function (card, i) { card.classList.toggle('is-selected', i === index); });
      buttons.forEach(function (button, i) { button.setAttribute('aria-pressed', String(i === index)); });
      markerNodes.forEach(function (marker) {
        var active = Number(marker.dataset.signalIndex) === index;
        marker.classList.toggle('is-selected', active);
        marker.setAttribute('aria-pressed', String(active));
      });
      if (announce) selection.textContent = String(c.ticker) + ': daily gain ' + amount(c.gain_pct, '%', true) + ', relative volume ' + amount(c.volume_ratio, '×') + '. ' + (canPlot(c) ? 'Highlighted on the map.' : 'Measurements are incomplete; this candidate is listed without a point.');
      if (reveal) cardNodes[index].scrollIntoView({ block: 'nearest', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    }

    candidates.forEach(function (c, index) {
      var card = node('article', 'signal-card');
      card.id = 'signal-candidate-' + index;
      var top = node('div', 'signal-card-top');
      top.append(node('span', 'signal-rank', 'RANK ' + (c.rank === undefined ? '—' : c.rank)), node('span', 'signal-provenance' + (fallback(c) ? ' is-fallback' : unknown(c) ? ' is-unknown' : ''), sourceLabel(c)));
      var h3 = node('h3');
      var button = node('button', 'signal-card-select', String(c.ticker));
      button.type = 'button';
      button.setAttribute('aria-label', 'Highlight ' + String(c.ticker) + ' on the signal map');
      button.addEventListener('click', function () { select(index, false, true); });
      h3.append(button);
      var score = node('p', 'signal-score');
      score.append(node('strong', '', amount(c.score, '')), node('span', '', ' / 10 · ' + (c.verdict || 'No verdict')));
      var facts = node('dl', 'signal-facts');
      [['Daily gain', amount(c.gain_pct, '%', true)], ['Relative volume', amount(c.volume_ratio, '×')]].forEach(function (f) {
        var pair = node('div'); pair.append(node('dt', '', f[0]), node('dd', '', f[1])); facts.append(pair);
      });
      var note = node('p', 'signal-card-note', c.reason || 'No scoring note was recorded.');
      card.append(top, h3, score, facts, note);
      if (!canPlot(c)) card.append(node('p', 'signal-missing', 'Not plotted · gain or volume measurement missing'));
      if (!unknown(c) && !fallback(c) && c.provenance.chart_seen === false) card.append(node('p', 'signal-missing', 'Scored without the chart'));
      if (!unknown(c) && !fallback(c) && typeof c.provenance.chart_seen !== 'boolean') card.append(node('p', 'signal-missing', 'Chart review not recorded'));
      var link = node('a', 'signal-record-link', 'Read scored record ↗');
      link.href = '#signal-record-' + index;
      link.addEventListener('click', function () {
        var row = document.getElementById('signal-record-' + index);
        if (row) row.focus({ preventScroll: true });
      });
      var actions = node('div', 'signal-card-actions');
      ['save', 'compare'].forEach(function (kind) {
        var action = node('button', 'signal-desk-action', kind === 'save' ? 'Save' : 'Compare');
        action.type = 'button';
        action.setAttribute('data-stock-' + kind, String(c.ticker));
        action.addEventListener('click', function () {
          var desk = window.SCStockDesk;
          var method = kind === 'save' ? 'toggleSaved' : 'toggleCompare';
          if (desk && typeof desk[method] === 'function') desk[method](c.ticker);
          refreshDesk();
        });
        actions.append(action); deskButtons.push({ node: action, c: c, kind: kind });
      });
      card.append(actions, link);
      cards.append(card);
      cardNodes.push(card); buttons.push(button);
    });

    cards.append(noMatches);
    refreshDesk = function () {
      var desk = window.SCStockDesk;
      deskButtons.forEach(function (entry) {
        var check = entry.kind === 'save' ? 'hasSaved' : 'hasCompared';
        var method = entry.kind === 'save' ? 'toggleSaved' : 'toggleCompare';
        var available = desk && typeof desk[check] === 'function' && typeof desk[method] === 'function';
        var pressed = !!(available && desk[check](entry.c.ticker));
        entry.node.disabled = !available;
        entry.node.setAttribute('aria-pressed', String(pressed));
        entry.node.textContent = entry.kind === 'save' ? (pressed ? 'Saved' : 'Save') : (pressed ? 'In compare' : 'Compare');
        entry.node.setAttribute('aria-label', (entry.kind === 'save' ? (pressed ? 'Remove ' : 'Save ') : (pressed ? 'Remove ' : 'Compare ')) + String(entry.c.ticker) + (pressed ? (entry.kind === 'save' ? ' from saved signals' : ' from comparison') : ''));
      });
    };
    window.addEventListener('stock:desk-change', refreshDesk);
    refreshDesk();

    if (!candidates.length) {
      cards.append(node('div', 'signal-empty', 'No candidates were scored in this session.'), node('p', 'signal-empty-note', 'Review the run status and evidence before interpreting an empty result. The map only displays recorded candidates.'));
      selection.textContent = 'No scored candidates to select.';
      legend.hidden = true;
    }

    function draw() {
      surface.replaceChildren();
      markerNodes = [];
      var shownPoints = points.filter(function (p) { return visibleIndexes.indexOf(p.index) >= 0; });
      if (!shownPoints.length) {
        var empty = node('div', 'signal-map-empty');
        empty.append(node('span', 'signal-empty-symbol', '—'), node('strong', '', candidates.length ? (visibleIndexes.length ? 'No complete measurements to plot.' : 'No signals in this view.') : 'No scored signals.'), node('span', '', candidates.length ? (visibleIndexes.length ? 'The matching candidates remain in the notes.' : 'Change or clear your filters to explore the recorded session.') : 'The map fills when a run records scored candidates.'));
        surface.append(empty);
        return;
      }
      var width = Math.max(240, surface.clientWidth), height = surface.clientHeight || 340;
      var left = 52, right = width - 24, top = 36, bottom = height - 62;
      var gains = points.map(function (p) { return p.c.gain_pct; });
      var volumes = points.map(function (p) { return p.c.volume_ratio; });
      var lowX = Math.min(0, Math.floor(Math.min.apply(null, gains)));
      var highX = Math.max(1, Math.ceil(Math.max.apply(null, gains) * 1.08));
      var highY = Math.max(1, Math.ceil(Math.max.apply(null, volumes) * 1.08));
      function x(v) { return left + (v - lowX) / (highX - lowX) * (right - left); }
      function y(v) { return bottom - v / highY * (bottom - top); }
      var svg = svgNode('svg', { width: width, height: height, viewBox: '0 0 ' + width + ' ' + height, 'aria-hidden': 'true' });
      for (var i = 0; i <= 4; i++) {
        var gx = lowX + (highX - lowX) * i / 4, gy = highY * i / 4;
        svg.append(svgNode('line', { x1: x(gx), y1: top, x2: x(gx), y2: bottom, 'class': 'signal-grid' }), svgNode('line', { x1: left, y1: y(gy), x2: right, y2: y(gy), 'class': 'signal-grid' }));
        svg.append(svgNode('text', { x: x(gx), y: bottom + 23, 'text-anchor': 'middle', 'class': 'signal-axis' }, gx.toFixed(1) + '%'), svgNode('text', { x: left - 9, y: y(gy) + 4, 'text-anchor': 'end', 'class': 'signal-axis' }, gy.toFixed(1) + '×'));
      }
      svg.append(svgNode('text', { x: left, y: 19, 'class': 'signal-axis-title' }, 'Relative volume'), svgNode('text', { x: (left + right) / 2, y: height - 13, 'text-anchor': 'middle', 'class': 'signal-axis-title' }, 'Daily gain'));
      surface.append(svg);
      shownPoints.forEach(function (p) {
        var marker = node('button', 'signal-point' + (fallback(p.c) ? ' is-fallback' : unknown(p.c) ? ' is-unknown' : ''));
        marker.type = 'button';
        marker.style.left = x(p.c.gain_pct) + 'px';
        marker.style.top = y(p.c.volume_ratio) + 'px';
        // Keep the selected ticker label inside the plot at either horizontal edge.
        if (x(p.c.gain_pct) > width - 82) marker.classList.add('is-near-right');
        if (x(p.c.gain_pct) < 82) marker.classList.add('is-near-left');
        marker.dataset.signalIndex = p.index;
        var label = String(p.c.ticker) + ', daily gain ' + amount(p.c.gain_pct, '%', true) + ', relative volume ' + amount(p.c.volume_ratio, '×') + ', ' + sourceLabel(p.c);
        marker.setAttribute('aria-label', label);
        marker.title = label;
        marker.append(node('span', 'signal-point-dot'), node('span', 'signal-point-label', String(p.c.ticker)));
        marker.addEventListener('click', function () { select(p.index, true, true); });
        surface.append(marker); markerNodes.push(marker);
      });
      select(selectedIndex, false, false);
    }
    function applyLens() {
      lensState.search = search.value;
      lensState.filter = activeFilter;
      lensState.order = order;
      visibleIndexes = candidates.map(function (_, index) { return index; }).filter(function (index) {
        var c = candidates[index];
        var matchesQuery = !query || (String(c.ticker) + ' ' + String(c.reason || '')).toLowerCase().indexOf(query) >= 0;
        var matchesFilter = activeFilter === 'all' ||
          (activeFilter === 'shortlist' && finite(c.rank) && c.rank > 0 && c.rank <= shortlistSize) ||
          (activeFilter === 'claude' && !unknown(c) && !fallback(c)) ||
          (activeFilter === 'fallback' && fallback(c)) ||
          (activeFilter === 'volume' && finite(c.volume_ratio) && c.volume_ratio >= 3);
        return matchesQuery && matchesFilter;
      });
      if (order !== 'rank') visibleIndexes.sort(function (a, b) {
        var key = order === 'gain' ? 'gain_pct' : 'volume_ratio';
        var av = candidates[a][key], bv = candidates[b][key];
        var validA = finite(av) && (key !== 'volume_ratio' || av >= 0);
        var validB = finite(bv) && (key !== 'volume_ratio' || bv >= 0);
        if (validA !== validB) return validA ? -1 : 1;
        return validA && av !== bv ? bv - av : a - b;
      });
      cardNodes.forEach(function (card, index) { card.hidden = visibleIndexes.indexOf(index) < 0; });
      visibleIndexes.forEach(function (index) { cards.append(cardNodes[index]); });
      cards.append(noMatches);
      noMatches.hidden = !candidates.length || !!visibleIndexes.length;
      filterButtons.forEach(function (button) { button.setAttribute('aria-pressed', String(button.dataset.signalFilter === activeFilter)); });
      clearFilters.hidden = !query && activeFilter === 'all' && order === 'rank';
      var plotted = points.filter(function (p) { return visibleIndexes.indexOf(p.index) >= 0; }).length;
      resultCount.textContent = visibleIndexes.length + ' of ' + candidates.length + ' signals · ' + plotted + ' plotted' + (order === 'rank' ? '' : ' · original ranks kept');
      if (visibleIndexes.indexOf(selectedIndex) < 0) selectedIndex = visibleIndexes.length ? visibleIndexes[0] : -1;
      if (selectedIndex < 0) {
        selection.textContent = candidates.length ? 'No candidates match the current filters.' : 'No scored candidates to select.';
        cardNodes.forEach(function (card) { card.classList.remove('is-selected'); });
        buttons.forEach(function (button) { button.setAttribute('aria-pressed', 'false'); });
      } else select(selectedIndex, false, true);
      draw();
    }
    applyLens();
    if (points.length) mapNote.textContent += ' Axes stay fixed while you filter.';
    if (points.length !== candidates.length) mapNote.textContent += ' ' + (candidates.length - points.length) + ' candidate(s) lack complete gain/volume measurements and remain listed.';
    if (window.ResizeObserver) { observer = new ResizeObserver(draw); observer.observe(surface); }
    else { resize = draw; window.addEventListener('resize', resize); }
  }
  window.SCStockSignals = { render: render };
}());
