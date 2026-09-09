/* Recorded daily OHLCV only. Interaction changes the inspection date, never a trade. */
(function () {
  'use strict';
  var SVG = 'http://www.w3.org/2000/svg', serial = 0;
  function element(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function shape(tag, attrs, text) {
    var node = document.createElementNS(SVG, tag);
    Object.keys(attrs || {}).forEach(function (key) { node.setAttribute(key, attrs[key]); });
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function finite(value) { return typeof value === 'number' && Number.isFinite(value); }
  function price(value) { return finite(value) ? '$' + value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : 'Unavailable'; }
  function compact(value) { return finite(value) ? value.toLocaleString('en-US', { notation: 'compact', maximumFractionDigits: 1 }) : '—'; }
  function dateLabel(value, short) {
    return new Date(value + 'T12:00:00Z').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: short ? undefined : 'numeric', timeZone: 'UTC' });
  }
  function validDate(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    var date = new Date(value + 'T12:00:00Z');
    return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
  }
  function normalise(row) {
    var dates = new Map();
    (Array.isArray(row && row.series) ? row.series : []).forEach(function (bar) {
      if (!bar || !validDate(bar.date) || !finite(bar.close) || bar.close <= 0) return;
      var candle = finite(bar.open) && finite(bar.high) && finite(bar.low) && bar.open > 0 && bar.low > 0 && bar.low <= Math.min(bar.open, bar.close) && bar.high >= Math.max(bar.open, bar.close);
      dates.set(bar.date, { date: bar.date, close: bar.close, open: candle ? bar.open : null, high: candle ? bar.high : bar.close, low: candle ? bar.low : bar.close, volume: finite(bar.volume) && bar.volume >= 0 ? bar.volume : null, candle: candle });
    });
    return Array.from(dates.values()).sort(function (a, b) { return a.date.localeCompare(b.date); });
  }
  function render(row, options) {
    options = options || {};
    var id = 'tc-' + (++serial), all = normalise(row), bars = [], offset = 0, selected = 0;
    var count = all.length, period = count > 21 ? '1M' : 'All', view = 'candles', width = 640;
    var entry = finite(options.entry) && options.entry > 0 ? options.entry : null;
    var stop = finite(options.stop) && options.stop > 0 ? options.stop : null;
    var root = element('section', 'tc-chart');
    root.destroy = function () {};
    var symbol = row && typeof row.ticker === 'string' ? row.ticker : 'Stock';
    root.setAttribute('aria-label', symbol + ' recorded price and volume');
    root.dataset.symbol = symbol;
    root.updateLevels = function (nextEntry, nextStop) {
      entry = finite(nextEntry) && nextEntry > 0 ? nextEntry : null;
      stop = finite(nextStop) && nextStop > 0 ? nextStop : null;
      if (all.length) { paintLevels(); draw(); }
      return root;
    };
    if (!all.length) {
      root.classList.add('tc-chart--empty');
      root.append(element('p', 'tc-empty-title', 'The chart needs recorded history.'), element('p', 'tc-caption', 'No valid daily prices were saved for ' + symbol + '. Your plan can still use prices you verify with your broker.'));
      return root;
    }
    if (!all.some(function (bar) { return bar.candle; })) view = 'line';
    function button(label, cls, action) {
      var node = element('button', 'tc-button' + (cls ? ' ' + cls : ''), label);
      node.type = 'button'; node.addEventListener('click', action); return node;
    }
    var header = element('div', 'tc-header');
    var quote = element('div', 'tc-quote');
    var quoteLabel = element('p', 'tc-eyebrow', 'Recorded close');
    var quoteValue = element('strong', 'tc-price');
    var change = element('span', 'tc-change');
    var quoteLine = element('div', 'tc-price-line'); quoteLine.append(quoteValue, change); quote.append(quoteLabel, quoteLine);
    var stamp = element('div', 'tc-stamp');
    var date = element('strong', 'tc-date');
    var kind = element('span', 'tc-stamp-label'); stamp.append(date, kind); header.append(quote, stamp);
    var controls = element('div', 'tc-controls');
    var ranges = element('div', 'tc-segment'); ranges.setAttribute('role', 'group'); ranges.setAttribute('aria-label', 'Recorded chart period');
    var periods = [];
    if (count > 21) periods.push({ label: '1M', length: 21 });
    if (count > 63) periods.push({ label: '3M', length: 63 });
    if (count > 252) periods.push({ label: '1Y', length: 252 });
    periods.push({ label: 'All', length: count });
    periods.forEach(function (item) {
      var node = button(item.label, '', function () { period = item.label; setPeriod(); });
      node.dataset.period = item.label;
      node.title = item.label === 'All' ? 'All ' + count + ' recorded sessions' : 'Last ' + item.length + ' recorded sessions';
      ranges.append(node);
    });
    var views = element('div', 'tc-segment'); views.setAttribute('role', 'group'); views.setAttribute('aria-label', 'Chart display');
    [['candles', 'Candles'], ['line', 'Line']].forEach(function (item) {
      var node = button(item[1], '', function () { view = item[0]; paintControls(); draw(); });
      node.dataset.view = item[0];
      if (item[0] === 'candles' && !all.some(function (bar) { return bar.candle; })) node.disabled = true;
      views.append(node);
    });
    controls.append(ranges, views);
    var levels = element('div', 'tc-levels'); levels.setAttribute('aria-label', 'Your plan levels');
    var canvas = element('div', 'tc-canvas');
    var svg = shape('svg', { 'class': 'tc-svg', viewBox: '0 0 640 294', 'aria-hidden': 'true', focusable: 'false' });
    canvas.append(svg);
    var stats = element('dl', 'tc-inspector');
    var statNodes = {};
    [['open', 'Open'], ['high', 'High'], ['low', 'Low'], ['volume', 'Shares traded']].forEach(function (item) {
      var stat = element('div'); statNodes[item[0]] = element('dd'); stat.append(element('dt', '', item[1]), statNodes[item[0]]); stats.append(stat);
    });
    var scrub = element('div', 'tc-scrub');
    var prev = button('←', 'tc-step', function () { inspect(selected - 1, true); }); prev.setAttribute('aria-label', 'Inspect previous session');
    var next = button('→', 'tc-step', function () { inspect(selected + 1, true); }); next.setAttribute('aria-label', 'Inspect next session');
    var range = element('input', 'tc-range'); range.type = 'range'; range.min = '0'; range.step = '1'; range.id = id + '-session'; range.setAttribute('aria-label', 'Inspect a recorded trading session');
    range.addEventListener('input', function () { inspect(Number(range.value), false); });
    var latest = button('Latest', 'tc-latest', function () { inspect(bars.length - 1, true); });
    scrub.append(prev, range, next, latest);
    var caption = element('p', 'tc-caption');
    var hint = element('p', 'tc-hint', count > 1 ? 'Drag across the chart, or use the arrows to inspect a day.' : 'One recorded session is available. More history will appear when saved.');
    var live = element('span', 'tc-sr-only'); live.setAttribute('role', 'status'); live.setAttribute('aria-live', 'polite'); live.setAttribute('aria-atomic', 'true');
    root.append(header, controls, levels, canvas, stats, scrub, caption, hint, live);
    var geometry = null;
    var overlay = null;
    function paintControls() {
      ranges.querySelectorAll('button').forEach(function (node) { node.setAttribute('aria-pressed', String(node.dataset.period === period)); });
      views.querySelectorAll('button').forEach(function (node) { node.setAttribute('aria-pressed', String(node.dataset.view === view)); });
    }
    function paintLevels() {
      levels.replaceChildren();
      if (entry !== null) levels.append(element('span', 'tc-level tc-level--entry', 'Your entry ' + price(entry)));
      if (stop !== null) levels.append(element('span', 'tc-level tc-level--stop', 'Your stop ' + price(stop)));
      levels.hidden = entry === null && stop === null;
    }
    function setPeriod() {
      var item = periods.find(function (candidate) { return candidate.label === period; });
      bars = all.slice(-item.length); offset = all.length - bars.length; selected = bars.length - 1;
      range.max = String(bars.length - 1); range.disabled = bars.length < 2;
      caption.textContent = dateLabel(bars[0].date) + ' – ' + dateLabel(bars[bars.length - 1].date) + ' · ' + bars.length + ' recorded session' + (bars.length === 1 ? '' : 's') + ' · Daily prices, not live';
      paintControls(); draw(); inspect(selected, false);
    }
    function draw() {
      svg.replaceChildren();
      var height = width < 420 ? 266 : 294;
      var left = 10, right = 61, top = 20, bottom = height - 79, volumeTop = height - 58, volumeBottom = height - 18;
      var plotWidth = Math.max(100, width - left - right), step = plotWidth / bars.length;
      var lows = bars.map(function (bar) { return view === 'candles' ? bar.low : bar.close; });
      var highs = bars.map(function (bar) { return view === 'candles' ? bar.high : bar.close; });
      var low = Math.min.apply(null, lows), high = Math.max.apply(null, highs);
      // Far-away or partially typed levels stay labelled at the edge; they must not flatten the price history.
      var dataSpan = high - low || high * .02;
      [entry, stop].forEach(function (value) { if (value !== null && value >= low - dataSpan * .5 && value <= high + dataSpan * .5) { low = Math.min(low, value); high = Math.max(high, value); } });
      var padding = Math.max((high - low) * .13, high * .003);
      low = Math.max(0, low - padding); high += padding;
      var y = function (value) { return bottom - (value - low) / (high - low) * (bottom - top); };
      var x = function (index) { return left + step * (index + .5); };
      geometry = { x: x, y: y, left: left, top: top, bottom: bottom, volumeTop: volumeTop, volumeBottom: volumeBottom, step: step, plotWidth: plotWidth, low: low, high: high };
      svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
      var defs = shape('defs');
      var gradient = shape('linearGradient', { id: id + '-area', x1: 0, x2: 0, y1: 0, y2: 1 });
      gradient.append(shape('stop', { offset: '0%', 'class': 'tc-area-top' }), shape('stop', { offset: '100%', 'class': 'tc-area-bottom' })); defs.append(gradient); svg.append(defs);
      for (var tick = 0; tick < 4; tick += 1) {
        var value = low + (high - low) * tick / 3, yy = y(value);
        svg.append(shape('line', { x1: left, x2: left + plotWidth, y1: yy, y2: yy, 'class': 'tc-grid' }));
        svg.append(shape('text', { x: width - right + 9, y: yy + 4, 'class': 'tc-axis' }, value >= 10000 ? compact(value) : value.toFixed(value < 10 ? 2 : 1)));
      }
      if (entry !== null && stop !== null && stop < entry) {
        var bandTop = Math.max(top, Math.min(bottom, y(entry))), bandBottom = Math.max(top, Math.min(bottom, y(stop)));
        if (bandBottom > bandTop) svg.append(shape('rect', { x: left, y: bandTop, width: plotWidth, height: bandBottom - bandTop, 'class': 'tc-risk-band' }));
      }
      var closePath = bars.map(function (bar, index) { return (index ? 'L' : 'M') + x(index).toFixed(2) + ' ' + y(bar.close).toFixed(2); }).join(' ');
      if (bars.length > 1) svg.append(shape('path', { d: closePath + ' L' + x(bars.length - 1) + ' ' + bottom + ' L' + x(0) + ' ' + bottom + ' Z', fill: 'url(#' + id + '-area)', 'class': view === 'line' ? 'tc-area' : 'tc-area tc-area--quiet' }));
      var maximumVolume = Math.max.apply(null, bars.map(function (bar) { return bar.volume === null ? 0 : bar.volume; }));
      svg.append(shape('line', { x1: left, x2: left + plotWidth, y1: volumeBottom, y2: volumeBottom, 'class': 'tc-grid' }));
      bars.forEach(function (bar, index) {
        var xx = x(index), up = bar.candle ? bar.close >= bar.open : index > 0 ? bar.close >= bars[index - 1].close : true;
        var tone = up ? 'tc-up' : 'tc-down';
        if (view === 'candles' && bar.candle) {
          var candleWidth = Math.min(10, Math.max(.7, step * .54));
          svg.append(shape('line', { x1: xx, x2: xx, y1: y(bar.high), y2: y(bar.low), 'class': 'tc-wick ' + tone }));
          svg.append(shape('rect', { x: xx - candleWidth / 2, y: Math.min(y(bar.open), y(bar.close)), width: candleWidth, height: Math.max(1.5, Math.abs(y(bar.close) - y(bar.open))), rx: .7, 'class': 'tc-candle ' + tone }));
        } else if (view === 'candles' || bars.length === 1) {
          svg.append(shape('circle', { cx: xx, cy: y(bar.close), r: 3, 'class': 'tc-point' }));
        }
        if (bar.volume !== null && maximumVolume > 0) {
          var barHeight = bar.volume / maximumVolume * (volumeBottom - volumeTop);
          svg.append(shape('rect', { x: xx - step * .33, y: volumeBottom - barHeight, width: Math.max(.5, step * .66), height: barHeight, rx: 1, 'class': 'tc-volume ' + tone }));
        }
      });
      svg.append(shape('path', { d: closePath, 'class': view === 'line' ? 'tc-line' : 'tc-line tc-line--quiet' }));
      var finalClose = bars[bars.length - 1].close;
      svg.append(shape('line', { x1: x(bars.length - 1), x2: left + plotWidth, y1: y(finalClose), y2: y(finalClose), 'class': 'tc-close-guide' }));
      [['entry', entry], ['stop', stop]].forEach(function (level) {
        if (level[1] === null) return;
        var inRange = level[1] >= low && level[1] <= high;
        var position = Math.max(top + 2, Math.min(bottom - 2, y(level[1])));
        svg.append(shape('line', { x1: left, x2: left + plotWidth, y1: position, y2: position, 'class': 'tc-plan-line tc-plan-line--' + level[0] + (inRange ? '' : ' tc-plan-line--outside') }));
        if (!inRange) svg.append(shape('text', { x: left + 4, y: position + (level[1] > high ? 12 : -6), 'class': 'tc-level-axis' }, (level[0] === 'entry' ? 'Entry' : 'Stop') + (level[1] > high ? ' above chart ↑' : ' below chart ↓')));
      });
      svg.append(shape('text', { x: width - right + 9, y: volumeTop + 12, 'class': 'tc-axis' }, 'Vol'));
      svg.append(shape('text', { x: width - right + 9, y: volumeTop + 27, 'class': 'tc-axis tc-axis--small' }, maximumVolume > 0 ? compact(maximumVolume) : '—'));
      overlay = shape('g', { 'class': 'tc-crosshair' }); svg.append(overlay);
      paintInspection();
    }
    function paintInspection() {
      if (!geometry || !overlay) return;
      var bar = bars[selected], xx = geometry.x(selected), yy = geometry.y(bar.close);
      overlay.replaceChildren();
      overlay.append(shape('rect', { x: xx - geometry.step * .47, y: geometry.top, width: geometry.step * .94, height: geometry.volumeBottom - geometry.top, 'class': 'tc-selected-column' }));
      overlay.append(shape('line', { x1: xx, x2: xx, y1: geometry.top, y2: geometry.volumeBottom, 'class': 'tc-crosshair-line' }));
      overlay.append(shape('line', { x1: geometry.left, x2: geometry.left + geometry.plotWidth, y1: yy, y2: yy, 'class': 'tc-crosshair-price' }));
      overlay.append(shape('circle', { cx: xx, cy: yy, r: 8, 'class': 'tc-halo' }), shape('circle', { cx: xx, cy: yy, r: 3.5, 'class': 'tc-dot' }));
      var pillY = Math.max(geometry.top - 10, Math.min(geometry.bottom - 9, yy - 9));
      overlay.append(shape('rect', { x: width - 58, y: pillY, width: 57, height: 19, rx: 4, 'class': 'tc-price-pill' }));
      overlay.append(shape('text', { x: width - 30, y: pillY + 13, 'class': 'tc-price-pill-label', 'text-anchor': 'middle' }, bar.close >= 10000 ? compact(bar.close) : bar.close.toFixed(2)));
    }
    function inspect(index, announce) {
      selected = Math.max(0, Math.min(bars.length - 1, index));
      var bar = bars[selected], globalIndex = offset + selected, previous = globalIndex > 0 ? all[globalIndex - 1].close : null;
      if (previous === null && row && row.date === bar.date && finite(row.prev_close) && row.prev_close > 0) previous = row.prev_close;
      var move = previous === null ? null : (bar.close / previous - 1) * 100;
      quoteValue.textContent = price(bar.close);
      change.textContent = move === null ? 'No prior close' : (move >= 0 ? '+' : '') + move.toFixed(2) + '% session';
      change.dataset.direction = move === null ? 'unknown' : move >= 0 ? 'up' : 'down';
      date.textContent = dateLabel(bar.date); kind.textContent = selected === bars.length - 1 ? 'Latest recorded session' : 'Inspecting history';
      statNodes.open.textContent = price(bar.open); statNodes.high.textContent = bar.candle ? price(bar.high) : 'Unavailable'; statNodes.low.textContent = bar.candle ? price(bar.low) : 'Unavailable';
      statNodes.volume.textContent = bar.volume === null ? 'Unavailable' : compact(bar.volume); statNodes.volume.title = bar.volume === null ? 'Volume not recorded' : bar.volume.toLocaleString('en-US', { maximumFractionDigits: 0 }) + ' shares';
      range.value = String(selected);
      var summary = dateLabel(bar.date) + ', close ' + price(bar.close) + (move === null ? '' : ', ' + (move >= 0 ? 'up ' : 'down ') + Math.abs(move).toFixed(2) + ' percent versus the previous recorded close') + ', volume ' + (bar.volume === null ? 'unavailable' : bar.volume.toLocaleString('en-US') + ' shares');
      range.setAttribute('aria-valuetext', summary);
      prev.disabled = selected === 0; next.disabled = selected === bars.length - 1; latest.disabled = selected === bars.length - 1;
      if (announce) live.textContent = summary;
      paintInspection();
    }
    function point(event) {
      if (!geometry) return;
      var rect = svg.getBoundingClientRect();
      if (!rect.width) return;
      var position = (event.clientX - rect.left) / rect.width * width;
      inspect(Math.floor((position - geometry.left) / geometry.step), false);
    }
    var dragging = false;
    svg.addEventListener('pointerdown', function (event) {
      if (event.pointerType === 'mouse' && event.button !== 0) return;
      dragging = true; point(event);
      if (svg.setPointerCapture) svg.setPointerCapture(event.pointerId);
    });
    svg.addEventListener('pointermove', function (event) { if (dragging || event.pointerType === 'mouse') point(event); });
    svg.addEventListener('pointerup', function () { dragging = false; });
    svg.addEventListener('pointercancel', function () { dragging = false; });
    svg.addEventListener('lostpointercapture', function () { dragging = false; });
    paintLevels(); setPeriod();
    if (typeof ResizeObserver !== 'undefined') {
      var wasConnected = false;
      var observer = new ResizeObserver(function (entries) {
        if (wasConnected && !root.isConnected) { observer.disconnect(); return; }
        if (root.isConnected) wasConnected = true;
        var nextWidth = Math.round(entries[0].contentRect.width);
        if (nextWidth > 0 && nextWidth !== width) { width = Math.max(180, nextWidth); draw(); }
      });
      observer.observe(canvas);
      root.destroy = function () { observer.disconnect(); };
    } else {
      // The chart remains responsive without observation; the inspector contains full-size equivalent values.
      root.destroy = function () {};
    }
    return root;
  }
  window.SCTradeChart = Object.freeze({ render: render });
}());
