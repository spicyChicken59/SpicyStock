/* A presentation of the recorded candidates. No requests, storage, scoring,
   sector inference, or new market data. The existing ranking stays authoritative. */
(function () {
  'use strict';
  var selected = null;
  var observer;
  var resize;
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
    root.replaceChildren();
    var candidates = Array.isArray(data.candidates) ? data.candidates : [];
    var run = data.run || {};
    var points = candidates.map(function (c, index) { return { c: c, index: index }; }).filter(function (p) { return canPlot(p.c); });
    document.getElementById('signal-workspace').hidden = false;
    document.getElementById('signal-count').textContent = candidates.length + ' scored · ' + points.length + ' plotted';

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
    root.append(layout);
    var cardNodes = [], buttons = [], markerNodes = [];
    var selectedIndex = candidates.findIndex(function (c) { return c.ticker === selected; });
    if (selectedIndex < 0 && candidates.length) selectedIndex = 0;

    function select(index, reveal, announce) {
      var c = candidates[index];
      if (!c) return;
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
      card.append(link);
      cards.append(card);
      cardNodes.push(card); buttons.push(button);
    });

    if (!candidates.length) {
      cards.append(node('div', 'signal-empty', 'No candidates were scored in this session.'), node('p', 'signal-empty-note', 'Review the run status and evidence before interpreting an empty result. The map only displays recorded candidates.'));
      selection.textContent = 'No scored candidates to select.';
      legend.hidden = true;
    }

    function draw() {
      surface.replaceChildren();
      markerNodes = [];
      if (!points.length) {
        var empty = node('div', 'signal-map-empty');
        empty.append(node('span', 'signal-empty-symbol', '—'), node('strong', '', candidates.length ? 'No complete measurements to plot.' : 'No scored signals.'), node('span', '', candidates.length ? 'Every scored candidate remains in the notes.' : 'The map fills when a run records scored candidates.'));
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
      points.forEach(function (p) {
        var marker = node('button', 'signal-point' + (fallback(p.c) ? ' is-fallback' : unknown(p.c) ? ' is-unknown' : ''));
        marker.type = 'button';
        marker.style.left = x(p.c.gain_pct) + 'px';
        marker.style.top = y(p.c.volume_ratio) + 'px';
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
    draw();
    select(selectedIndex, false, false);
    if (points.length !== candidates.length) mapNote.textContent += ' ' + (candidates.length - points.length) + ' candidate(s) lack complete gain/volume measurements and remain listed.';
    if (window.ResizeObserver) { observer = new ResizeObserver(draw); observer.observe(surface); }
    else { resize = draw; window.addEventListener('resize', resize); }
  }
  window.SCStockSignals = { render: render };
}());
