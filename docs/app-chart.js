/* SpicyStock — annotated daily candlestick + volume chart on the SpicyChicken
   design system. Needs sc.css and sc-charts.js (SC.el/svg, SC.ticks,
   SC.spreadLabels, SC.tooltip, SC.tableTwin).

     SCStock.chart(series, options)                      -> .sc-chart host element
     SCStock.chartGeometry(series, options, width, height) -> pure scales and positions
     SCStock.sma(closes, n)                              -> simple moving average

   series: [{date:'YYYY-MM-DD', o, h, l, c, v}] oldest first. A bar whose o/h/l
   is null is a GAP: no candle, the averages step over it, nothing is spliced.
   Colour arrives through the --sc-tone channel only; no mark names a colour. */
(function (w) {
  'use strict';
  var SCStock = w.SCStock = w.SCStock || {};
  var CHAR = 6.6;     /* px per glyph of 11px mono — sizes label plates without a DOM */
  var LABEL_H = 14;
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var DAYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
  var styled = false;

  function sc() {
    if (!w.SC || !w.SC.ticks || !w.SC.spreadLabels) throw new Error('app-chart.js needs sc-charts.js loaded first');
    return w.SC;
  }
  function num(v) { return typeof v === 'number' && isFinite(v) ? v : null; }
  function r1(v) { return Math.round(v * 10) / 10; }
  function thousands(s) { return s.replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
  function fmtPrice(v, decimals) {
    if (num(v) === null) return '—';
    var d = decimals === undefined ? 2 : decimals, s = Math.abs(v).toFixed(d);
    return (v < 0 ? '-' : '') + '$' + thousands(s);
  }
  function fmtPct(v) { return num(v) === null ? '—' : (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(1) + '%'; }
  function fmtVol(v) {
    if (num(v) === null) return '—';
    if (v >= 1e9) return (v / 1e9).toFixed(2) + 'B';
    if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
    if (v >= 1e3) return Math.round(v / 1e3) + 'K';
    return String(Math.round(v));
  }
  function weekday(date) {
    var p = date.split('-');
    if (p.length !== 3) return '';
    var t = Date.UTC(+p[0], +p[1] - 1, +p[2]);
    return isFinite(t) ? DAYS[new Date(t).getUTCDay()] : '';
  }
  function shortDate(date) {
    var p = date.split('-');
    return p.length === 3 ? (+p[2]) + ' ' + MONTHS[+p[1] - 1] : date;
  }

  /* ---------- simple moving average ------------------------------------- */
  function sma(closes, n) {
    var out = [], i, j, sum, ok;
    closes = closes || [];
    n = Math.max(1, Math.floor(n || 1));
    for (i = 0; i < closes.length; i++) {
      if (i < n - 1) { out.push(null); continue; }
      sum = 0; ok = true;
      for (j = i - n + 1; j <= i; j++) {
        if (num(closes[j]) === null) { ok = false; break; }
        sum += closes[j];
      }
      out.push(ok ? sum / n : null);
    }
    return out;
  }

  /* ---------- bars ----------------------------------------------------- */
  function normalise(series) {
    var out = [], prev = null, i, r, o, h, l, c, v, candle;
    series = Object.prototype.toString.call(series) === '[object Array]' ? series : [];
    for (i = 0; i < series.length; i++) {
      r = series[i] || {};
      o = num(r.o); h = num(r.h); l = num(r.l); c = num(r.c); v = num(r.v);
      candle = o !== null && h !== null && l !== null && c !== null && o > 0 && l > 0
        && l <= Math.min(o, c) && h >= Math.max(o, c);
      out.push({
        index: i, date: typeof r.date === 'string' ? r.date : '',
        o: o, h: h, l: l, c: c, v: v !== null && v >= 0 ? v : null, candle: candle,
        pct: c !== null && prev !== null && prev > 0 ? (c / prev - 1) * 100 : null
      });
      if (c !== null) prev = c;
    }
    return out;
  }

  /* ---------- geometry (pure) -------------------------------------------
     Price scale: the domain is every candle's low and high (a gap bar's
     close) AND every annotation level, padded 5% below and 7% above so the
     stop, the target and the burst label all sit inside the pane. Volume is
     its own pane under the price pane, scaled 0..max, with no second axis on
     the price pane. The right gutter is sized from the widest label it has
     to hold, so a $1,234.56 name and a $4.20 name each get the room they
     need at 360px. */
  function chartGeometry(series, options, width, height) {
    var SC = sc();
    options = options || {};
    var compact = !!options.compact;
    var W = Math.max(200, Math.round(width || options.width || 640));
    var H = Math.max(160, Math.round(height || options.height || (compact ? 200 : 320)));
    var bars = normalise(series), n = bars.length, i, b;
    var stop = num(options.stop), entryLow = num(options.entryLow), entryHigh = num(options.entryHigh);
    var trigger = num(options.trigger), targetLow = num(options.targetLow), targetHigh = num(options.targetHigh);
    var box = options.box && num(options.box.start) !== null && num(options.box.end) !== null ? options.box : null;
    if (box) {
      var bs = Math.max(0, Math.min(n - 1, Math.floor(box.start))), be = Math.max(0, Math.min(n - 1, Math.floor(box.end)));
      box = n && bs <= be && num(box.low) !== null && num(box.high) !== null && box.low < box.high
        ? { start: bs, end: be, low: box.low, high: box.high } : null;
    }
    if (entryLow !== null && entryHigh !== null && entryLow > entryHigh) { var t = entryLow; entryLow = entryHigh; entryHigh = t; }
    if (targetLow !== null && targetHigh !== null && targetLow > targetHigh) { var t2 = targetLow; targetLow = targetHigh; targetHigh = t2; }
    var burstIndex = num(options.burstIndex);
    burstIndex = burstIndex !== null && burstIndex >= 0 && burstIndex < n && bars[burstIndex].candle ? Math.floor(burstIndex) : null;

    /* domain */
    var lo = Infinity, hi = -Infinity;
    function widen(v) { if (v !== null && isFinite(v)) { if (v < lo) lo = v; if (v > hi) hi = v; } }
    for (i = 0; i < n; i++) { b = bars[i]; if (b.candle) { widen(b.l); widen(b.h); } else widen(b.c); }
    widen(stop); widen(entryLow); widen(entryHigh); widen(trigger); widen(targetLow); widen(targetHigh);
    if (box) { widen(box.low); widen(box.high); }
    if (!isFinite(lo)) { lo = 0; hi = 1; }
    if (hi === lo) { var e = Math.max(1, Math.abs(lo) * 0.02); lo -= e; hi += e; }
    var span = hi - lo;
    lo -= span * 0.05; hi += span * 0.07;
    var lastClose = null;
    for (i = n - 1; i >= 0 && lastClose === null; i--) lastClose = bars[i].c;

    /* gridline values and the right-gutter texts, which size the gutter */
    var tk = SC.ticks(lo, hi, compact ? 3 : 5), gridValues = [], decimals = 2;
    if (tk.ticks.length > 1) decimals = tk.ticks[1] - tk.ticks[0] >= 1 ? 0 : 2;
    for (i = 0; i < tk.ticks.length; i++) if (tk.ticks[i] > lo && tk.ticks[i] < hi) gridValues.push(tk.ticks[i]);
    /* the target band is read off the entry reference: the top of the buy
       zone (the worst fill), else the trigger, else the last close */
    var ref = num(options.targetRef) !== null ? options.targetRef
      : entryHigh !== null ? entryHigh : entryLow !== null ? entryLow : trigger !== null ? trigger : lastClose;
    var target = null;
    if (targetLow !== null && targetHigh !== null) {
      target = { low: targetLow, high: targetHigh, ref: ref };
      if (ref !== null && ref > 0) {
        target.pctLow = Math.round((targetLow / ref - 1) * 100);
        target.pctHigh = Math.round((targetHigh / ref - 1) * 100);
        target.text = typeof options.targetLabel === 'string' ? options.targetLabel
          : fmtPct(target.pctLow).replace('.0', '') + ' … ' + fmtPct(target.pctHigh).replace('.0', '');
      } else target.text = typeof options.targetLabel === 'string' ? options.targetLabel : 'target';
    }
    var maList = options.ma === undefined ? [10, 20, 50] : (options.ma || []);
    var closes = [], mas = [], k;
    for (i = 0; i < n; i++) closes.push(bars[i].c);
    for (k = 0; k < maList.length; k++) {
      var len = num(maList[k]);
      if (len === null || len < 1) continue;
      mas.push({ n: Math.floor(len), weight: Math.floor(len) === 20 ? 1.8 : 1.1, values: sma(closes, Math.floor(len)) });
    }
    var widest = 0;
    function span1(s) { if (s.length > widest) widest = s.length; }
    if (lastClose !== null) span1(fmtPrice(lastClose));
    for (i = 0; i < gridValues.length; i++) span1(fmtPrice(gridValues[i], decimals));
    if (target) span1(target.text);
    for (k = 0; k < mas.length; k++) span1(mas[k].n + 'd');
    var gutter = Math.max(compact ? 40 : 48, Math.round(widest * CHAR) + 16);

    /* panes */
    var top = compact ? 14 : 18, axisH = 18, gap = 8;
    var volH = Math.round((H - top - axisH - gap) * (compact ? 0.18 : 0.22));
    var plot = { left: 6, right: W - gutter, top: top, bottom: H - axisH - volH - gap };
    plot.width = plot.right - plot.left; plot.height = plot.bottom - plot.top;
    var vol = { top: plot.bottom + gap, bottom: H - axisH };
    vol.height = vol.bottom - vol.top;
    var slot = n ? plot.width / n : plot.width;
    var bodyW = Math.max(1, Math.min(12, Math.round(slot * 0.62)));
    function x(i) { return r1(plot.left + (i + 0.5) * slot); }
    function y(p) { return r1(plot.bottom - (p - lo) / (hi - lo) * plot.height); }
    var vmax = 0;
    for (i = 0; i < n; i++) if (bars[i].v !== null && bars[i].v > vmax) vmax = bars[i].v;
    function vy(v) { return r1(vol.bottom - (vmax ? v / vmax : 0) * vol.height); }

    /* candles and volume bars */
    var out = [], burst = null;
    for (i = 0; i < n; i++) {
      b = bars[i];
      var cx = x(i), bx = r1(cx - bodyW / 2), candle = null, volume = null;
      if (b.candle) {
        var up = b.c >= b.o, yTop = y(Math.max(b.o, b.c)), yBot = y(Math.min(b.o, b.c));
        candle = { x: bx, cx: cx, y: yTop, w: bodyW, h: Math.max(1, r1(yBot - yTop)),
                   wickTop: y(b.h), wickBottom: y(b.l), up: up, filled: !up, burst: i === burstIndex };
      }
      if (b.v !== null) {
        var vTop = vy(b.v);
        volume = { x: bx, y: vTop, w: bodyW, h: Math.max(b.v > 0 ? 1 : 0, r1(vol.bottom - vTop)), burst: i === burstIndex };
      }
      out.push({ index: i, date: b.date, x: cx, o: b.o, h: b.h, l: b.l, c: b.c, v: b.v, pct: b.pct, candle: candle, volume: volume });
    }
    if (burstIndex !== null) {
      b = bars[burstIndex];
      var bpct = b.pct !== null ? b.pct : (b.c / b.o - 1) * 100;
      var text = 'burst ' + fmtPct(bpct), tw = text.length * CHAR + 8, lx = x(burstIndex), anchor = 'middle';
      if (lx - tw / 2 < plot.left) { anchor = 'start'; lx = plot.left + 2; }
      else if (lx + tw / 2 > plot.right) { anchor = 'end'; lx = plot.right - 2; }
      burst = { index: burstIndex, x: x(burstIndex), yHigh: y(b.h), yLow: y(b.l), pct: bpct, close: b.c, volume: b.v, date: b.date,
                column: { x: r1(plot.left + burstIndex * slot), w: r1(slot), y: plot.top, h: r1(vol.bottom - plot.top) },
                marker: { x: x(burstIndex), y: r1(y(b.l) + 4), size: 5 },
                label: { x: lx, y: Math.max(top - 4, r1(y(b.h) - 9)), text: text, anchor: anchor } };
    }

    /* base box */
    var boxG = null;
    if (box) {
      var x1 = r1(plot.left + box.start * slot), x2 = r1(plot.left + (box.end + 1) * slot);
      var by1 = y(box.high), by2 = y(box.low), sessions = box.end - box.start + 1;
      var btext = 'base · ' + sessions + ' session' + (sessions === 1 ? '' : 's');
      var above = by1 - LABEL_H - 2 >= plot.top - 6;
      var blx = x1 + 2, banchor = 'start';
      if (x1 + btext.length * CHAR + 8 > plot.right) { blx = x2 - 2; banchor = 'end'; }
      boxG = { x: x1, y: by1, w: r1(x2 - x1), h: r1(by2 - by1), start: box.start, end: box.end, low: box.low, high: box.high, sessions: sessions,
               label: { x: blx, y: above ? r1(by1 - 4) : r1(by2 + 12), text: btext, anchor: banchor } };
    }

    /* moving averages */
    var maPaths = [];
    for (k = 0; k < mas.length; k++) {
      var pts = [], last = null;
      for (i = 0; i < n; i++) {
        var mv = mas[k].values[i];
        pts.push(mv === null ? null : { x: x(i), y: y(mv) });
        if (mv !== null) last = { x: x(i), y: y(mv), value: mv };
      }
      maPaths.push({ n: mas[k].n, weight: mas[k].weight, points: pts, last: last });
    }

    /* levels — labelled at the left edge. The stop reads under its line, the
       trigger over its line (under it when the buy zone starts there), the
       buy zone inside its band when the band is tall enough and over it
       otherwise; then one collision pass, and a label the pass moved gets a
       leader back to the level it names. The base label joins the pass when
       its box starts under these. */
    var left = [], stopG = null, entryG = null, triggerG = null, targetG = null;
    function leftLabel(y0, text, kind, tone) {
      var it = { y: y0, yTrue: y0, x: plot.left + 4, text: text, kind: kind, tone: tone, leader: null };
      left.push(it); return it;
    }
    var ey1 = null, ey2 = null;
    if (entryLow !== null && entryHigh !== null) { ey1 = y(entryHigh); ey2 = y(entryLow); }
    if (stop !== null) stopG = { y: y(stop), price: stop, label: leftLabel(r1(y(stop) + 11), 'stop ' + fmtPrice(stop), 'stop', 'danger') };
    if (trigger !== null) {
      var tyy = y(trigger), under = ey2 !== null && ey2 >= tyy - LABEL_H - 2 && ey2 <= tyy + 2;
      triggerG = { y: tyy, price: trigger, label: leftLabel(r1(under ? tyy + 11 : tyy - 4), 'trigger ' + fmtPrice(trigger), 'trigger', 'warn') };
    }
    if (ey1 !== null) {
      var inside = ey2 - ey1 >= 2 * LABEL_H;
      entryG = { y1: ey1, y2: ey2, h: Math.max(1, r1(ey2 - ey1)), low: entryLow, high: entryHigh,
                 label: leftLabel(inside ? r1(ey1 + 11) : r1(ey1 - 4), 'buy zone ' + fmtPrice(entryLow) + '\u2013' + fmtPrice(entryHigh), 'entry', 'chart-emphasis') };
    }
    var leftWidth = 0;
    for (i = 0; i < left.length; i++) leftWidth = Math.max(leftWidth, left[i].text.length * CHAR + 8);
    var boxJoined = boxG && boxG.label.anchor === 'start' && boxG.label.x < plot.left + leftWidth;
    if (boxJoined) { boxG.label.yTrue = boxG.label.y; left.push(boxG.label); }
    SC.spreadLabels(left, { gap: LABEL_H + 1, min: plot.top + 9, max: plot.bottom - 3 });
    for (i = 0; i < left.length; i++) {
      left[i].y = r1(left[i].y);
      if (left[i].kind && Math.abs(left[i].y - left[i].yTrue) > 2) {
        var levelY = left[i].kind === 'stop' ? stopG.y : left[i].kind === 'trigger' ? triggerG.y : entryG.y1;
        left[i].leader = { x: plot.left + 1, y1: levelY, y2: r1(left[i].y - 5) };
      }
    }
    if (boxJoined) left.pop();

    /* right gutter — last close, the target band, gridline values, MA ends */
    var right = [];
    function near(list, y0, d) { for (var j = 0; j < list.length; j++) if (Math.abs(list[j].yTrue - y0) < d) return true; return false; }
    function rightLabel(y0, text, kind) { var it = { y: y0, yTrue: y0, text: text, kind: kind }; right.push(it); return it; }
    if (lastClose !== null) rightLabel(y(lastClose), fmtPrice(lastClose), 'close');
    if (target) {
      var ty1 = y(targetHigh), ty2 = y(targetLow);
      targetG = { y1: ty1, y2: ty2, h: Math.max(1, r1(ty2 - ty1)), low: targetLow, high: targetHigh, ref: ref,
                  pctLow: target.pctLow, pctHigh: target.pctHigh, text: target.text,
                  strip: { x: plot.right + 1, w: 4 }, label: rightLabel(r1((ty1 + ty2) / 2 + 4), target.text, 'target') };
    }
    var grid = [];
    for (i = 0; i < gridValues.length; i++) {
      var gy = y(gridValues[i]);
      grid.push({ value: gridValues[i], y: gy });
      if (!near(right, gy, LABEL_H)) rightLabel(gy, fmtPrice(gridValues[i], decimals), 'tick');
    }
    for (k = 0; k < maPaths.length; k++) {
      if (maPaths[k].last && !near(right, maPaths[k].last.y, LABEL_H - 2)) rightLabel(maPaths[k].last.y, maPaths[k].n + 'd', 'ma');
    }
    SC.spreadLabels(right, { gap: LABEL_H - 1, min: plot.top + 5, max: plot.bottom - 2 });
    for (i = 0; i < right.length; i++) { right[i].y = r1(right[i].y); right[i].x = plot.right + 9; }

    /* date axis: month boundaries; a series too short for two of them is
       ticked every n/5 bars instead */
    var dateTicks = [], prevX = -Infinity, m, pm, d;
    for (i = 1; i < n; i++) {
      d = bars[i].date; m = d.slice(5, 7); pm = bars[i - 1].date.slice(5, 7);
      if (m && pm && m !== pm) dateTicks.push({ index: i, label: MONTHS[+m - 1] + (m === '01' ? " '" + d.slice(2, 4) : '') });
    }
    if (dateTicks.length < 2 && n) {
      var step = Math.max(1, Math.ceil(n / 5));
      dateTicks = [];
      for (i = 0; i < n; i += step) dateTicks.push({ index: i, label: shortDate(bars[i].date) });
    }
    var kept = [];
    for (i = 0; i < dateTicks.length; i++) {
      var tx = r1(plot.left + dateTicks[i].index * slot);
      if (tx - prevX < 30) continue;
      dateTicks[i].x = tx; kept.push(dateTicks[i]); prevX = tx;
    }

    return {
      width: W, height: H, n: n, compact: compact, gutter: gutter,
      plot: plot, vol: vol, axisY: H - 5, slot: slot, bodyWidth: bodyW,
      domain: { lo: lo, hi: hi }, volMax: vmax, lastClose: lastClose, decimals: decimals,
      x: x, y: y, vy: vy,
      grid: grid, dateTicks: kept, bars: out, ma: maPaths,
      box: boxG, burst: burst, stop: stopG, entry: entryG, trigger: triggerG, target: targetG,
      leftLabels: left, rightLabels: right
    };
  }

  /* ---------- styles (tokens only; the sheet keeps every declaration) ---- */
  function ensureStyle() {
    if (styled || !w.document) return;
    styled = true;
    var css = [
      '.sc-chart--stock{touch-action:pan-y}',
      '.sc-chart--stock .sc-chart__stage{position:relative}',
      '.sc-chart--stock text{font-size:11px}',
      '.sc-chart--stock .sc-chart__note{font:600 11px var(--sc-font-mono);fill:var(--sc-heading)}',
      '.sc-chart--stock .sc-chart__note--strong{font-weight:700}',
      '.sc-chart--stock .sc-chart__faint{fill:var(--sc-text-3)}',
      '.sc-chart__plate{fill:var(--sc-surface);fill-opacity:.9;stroke:none}',
      '.sc-chart__wick{stroke:var(--sc-tone,var(--sc-chart-context));stroke-width:1}',
      '.sc-chart__candle{stroke:var(--sc-tone,var(--sc-chart-context));stroke-width:1.2;fill:none}',
      '.sc-chart__candle.is-filled{fill:var(--sc-tone,var(--sc-chart-context))}',
      '.sc-chart__candle--burst{stroke-width:1.8}',
      '.sc-chart__vol{fill:var(--sc-tone,var(--sc-chart-context));fill-opacity:.5}',
      '.sc-chart__vol.is-emphasis{fill-opacity:1}',
      '.sc-chart__band{fill:var(--sc-tone,var(--sc-chart-context));fill-opacity:.14;stroke:none}',
      '.sc-chart__band--faint{fill-opacity:.07}',
      '.sc-chart__strip{fill:var(--sc-tone,var(--sc-chart-context));fill-opacity:.9}',
      '.sc-chart__box{fill:var(--sc-tone,var(--sc-chart-context));fill-opacity:.2;stroke:var(--sc-tone,var(--sc-chart-context));stroke-width:1.3;stroke-dasharray:4 3}',
      '.sc-chart__level{fill:none;stroke:var(--sc-tone,var(--sc-chart-context));stroke-width:1.3}',
      '.sc-chart__level--dashed{stroke-dasharray:6 4}',
      '.sc-chart__level--dotted{stroke-dasharray:2 3}',
      '.sc-chart__flag{fill:var(--sc-tone,var(--sc-accent))}',
      '.sc-chart__leader{stroke:var(--sc-border-strong);stroke-width:1;fill:none}',
      '.sc-chart--stock .sc-chart__hit{fill:transparent;cursor:crosshair}',
      '.sc-chart--stock .sc-chart__crosshair{stroke-dasharray:3 3;pointer-events:none}',
      '.sc-chart__head{display:flex;align-items:baseline;gap:6px 14px;flex-wrap:wrap;margin:0 0 6px}',
      '.sc-chart__head .sc-legend{margin:0;margin-left:auto}',
      '.sc-chart__key{display:inline-block;overflow:visible}',
      '.sc-chart--stock .sc-details{margin-top:10px}',
      '.sc-chart--stock .sc-details .sc-table+.sc-table{margin-top:10px}'
    ].join('\n');
    var node = w.document.createElement('style');
    node.setAttribute('data-sc-stock-chart', '');
    node.textContent = css;
    w.document.head.appendChild(node);
  }

  /* ---------- SVG ------------------------------------------------------- */
  function toneStyle(slot) { return '--sc-tone:var(--sc-' + slot + ')'; }
  function plate(parent, SC, lab, cls) {
    var wdt = r1(lab.text.length * CHAR + 6), x0 = lab.anchor === 'end' ? lab.x - wdt + 3 : lab.anchor === 'middle' ? lab.x - wdt / 2 : lab.x - 3;
    parent.appendChild(SC.svg('rect', { 'class': 'sc-chart__plate', x: r1(x0), y: r1(lab.y - 11), width: wdt, height: LABEL_H, rx: 2 }));
    parent.appendChild(SC.svg('text', { 'class': 'sc-chart__note' + (cls ? ' ' + cls : ''), x: lab.x, y: lab.y, 'text-anchor': lab.anchor || 'start' }, lab.text));
  }
  function pathOf(points) {
    var d = '', pen = false, i, p;
    for (i = 0; i < points.length; i++) {
      p = points[i];
      if (!p) { pen = false; continue; }
      d += (pen ? 'L' : 'M') + p.x + ',' + p.y; pen = true;
    }
    return d;
  }
  function buildSvg(g, SC) {
    var svg = SC.svg('svg', { viewBox: '0 0 ' + g.width + ' ' + g.height, width: g.width, height: g.height, 'aria-hidden': 'true', focusable: 'false' });
    var plot = g.plot, i, b;
    /* gridlines */
    var grid = SC.svg('g');
    for (i = 0; i < g.grid.length; i++) grid.appendChild(SC.svg('line', { 'class': 'sc-chart__grid', x1: plot.left, x2: plot.right, y1: g.grid[i].y, y2: g.grid[i].y }));
    grid.appendChild(SC.svg('line', { 'class': 'sc-chart__grid', x1: plot.left, x2: plot.right, y1: g.vol.bottom, y2: g.vol.bottom }));
    svg.appendChild(grid);
    /* the burst column under everything but the grid, then the bands: target (faint, full width + gutter strip), buy zone, base box */
    if (g.burst) svg.appendChild(SC.svg('rect', { 'class': 'sc-chart__band sc-chart__band--faint', style: toneStyle('accent'), x: g.burst.column.x, y: g.burst.column.y, width: g.burst.column.w, height: g.burst.column.h }));
    if (g.target) {
      var tg = SC.svg('g', { style: toneStyle('good') });
      tg.appendChild(SC.svg('rect', { 'class': 'sc-chart__band sc-chart__band--faint', x: plot.left, y: g.target.y1, width: plot.width, height: g.target.h }));
      tg.appendChild(SC.svg('rect', { 'class': 'sc-chart__strip', x: g.target.strip.x, y: g.target.y1, width: g.target.strip.w, height: g.target.h }));
      svg.appendChild(tg);
    }
    if (g.entry) {
      svg.appendChild(SC.svg('rect', { 'class': 'sc-chart__band', style: toneStyle('chart-emphasis'), x: plot.left, y: g.entry.y1, width: plot.width, height: g.entry.h }));
    }
    if (g.box) {
      svg.appendChild(SC.svg('rect', { 'class': 'sc-chart__box', style: toneStyle('chart-context'), x: g.box.x, y: g.box.y, width: g.box.w, height: g.box.h }));
    }
    /* volume */
    var vg = SC.svg('g', { style: toneStyle('chart-context') }), vb = SC.svg('g', { style: toneStyle('accent') });
    for (i = 0; i < g.bars.length; i++) {
      b = g.bars[i].volume;
      if (!b || !b.h) continue;
      (b.burst ? vb : vg).appendChild(SC.svg('rect', { 'class': 'sc-chart__vol' + (b.burst ? ' is-emphasis' : ''), x: b.x, y: b.y, width: b.w, height: b.h }));
    }
    svg.appendChild(vg); svg.appendChild(vb);
    /* moving averages: context tone, the 20 a touch heavier */
    for (i = 0; i < g.ma.length; i++) {
      var d = pathOf(g.ma[i].points);
      if (d) svg.appendChild(SC.svg('path', { 'class': 'sc-chart__series sc-chart__series--context', style: '--sc-weight:' + g.ma[i].weight, d: d }));
    }
    /* candles: up hollow in emphasis, down filled in context, the burst in the accent */
    var up = SC.svg('g', { style: toneStyle('chart-emphasis') }), down = SC.svg('g', { style: toneStyle('chart-context') }), burstG = SC.svg('g', { style: toneStyle('accent') });
    for (i = 0; i < g.bars.length; i++) {
      var c = g.bars[i].candle;
      if (!c) continue;
      var parent = c.burst ? burstG : c.up ? up : down, cls = 'sc-chart__candle' + (c.filled ? ' is-filled' : '') + (c.burst ? ' sc-chart__candle--burst' : '');
      /* the wick in two pieces so it never crosses a hollow body */
      if (c.wickTop < c.y) parent.appendChild(SC.svg('line', { 'class': 'sc-chart__wick', x1: c.cx, x2: c.cx, y1: c.wickTop, y2: c.y }));
      if (c.wickBottom > c.y + c.h) parent.appendChild(SC.svg('line', { 'class': 'sc-chart__wick', x1: c.cx, x2: c.cx, y1: c.y + c.h, y2: c.wickBottom }));
      if (c.w <= 2) parent.appendChild(SC.svg('line', { 'class': cls, x1: c.cx, x2: c.cx, y1: c.y, y2: c.y + c.h, 'stroke-width': c.filled ? 2 : 1 }));
      else parent.appendChild(SC.svg('rect', { 'class': cls, x: c.x, y: c.y, width: c.w, height: c.h }));
    }
    svg.appendChild(up); svg.appendChild(down); svg.appendChild(burstG);
    /* levels */
    if (g.stop) svg.appendChild(SC.svg('line', { 'class': 'sc-chart__level sc-chart__level--dashed', style: toneStyle('danger'), x1: plot.left, x2: plot.right, y1: g.stop.y, y2: g.stop.y }));
    if (g.trigger) svg.appendChild(SC.svg('line', { 'class': 'sc-chart__level sc-chart__level--dotted', style: toneStyle('warn'), x1: plot.left, x2: plot.right, y1: g.trigger.y, y2: g.trigger.y }));
    if (g.entry) {
      svg.appendChild(SC.svg('line', { 'class': 'sc-chart__level', style: toneStyle('chart-emphasis') + ';stroke-opacity:.5', x1: plot.left, x2: plot.right, y1: g.entry.y1, y2: g.entry.y1, 'stroke-width': 1 }));
      svg.appendChild(SC.svg('line', { 'class': 'sc-chart__level', style: toneStyle('chart-emphasis') + ';stroke-opacity:.5', x1: plot.left, x2: plot.right, y1: g.entry.y2, y2: g.entry.y2, 'stroke-width': 1 }));
    }
    /* burst marker: a small triangle under the low, in the accent */
    if (g.burst) {
      var m = g.burst.marker, s = m.size;
      svg.appendChild(SC.svg('path', { 'class': 'sc-chart__flag', style: toneStyle('accent'), d: 'M' + m.x + ',' + m.y + 'l' + s + ',' + (s + 2) + 'h' + (-2 * s) + 'z' }));
    }
    /* labels, on surface plates so they read over candles */
    var labels = SC.svg('g');
    if (g.box) plate(labels, SC, g.box.label);
    for (i = 0; i < g.leftLabels.length; i++) {
      var ld = g.leftLabels[i].leader;
      if (ld) labels.appendChild(SC.svg('line', { 'class': 'sc-chart__leader', x1: ld.x, x2: ld.x, y1: ld.y1, y2: ld.y2 }));
      plate(labels, SC, g.leftLabels[i]);
    }
    if (g.burst) plate(labels, SC, g.burst.label, 'sc-chart__note--strong');
    svg.appendChild(labels);
    /* right gutter: leaders then texts */
    var gutter = SC.svg('g');
    for (i = 0; i < g.rightLabels.length; i++) {
      var L = g.rightLabels[i];
      gutter.appendChild(SC.svg('line', { 'class': 'sc-chart__leader', x1: plot.right, y1: L.yTrue, x2: plot.right + 6, y2: L.y }));
      var cls2 = L.kind === 'close' ? 'sc-chart__note sc-chart__note--strong' : L.kind === 'target' ? 'sc-chart__note' : L.kind === 'ma' ? 'sc-chart__faint' : null;
      gutter.appendChild(SC.svg('text', { 'class': cls2, x: L.x, y: L.y + 4, 'text-anchor': 'start' }, L.text));
    }
    svg.appendChild(gutter);
    /* volume pane caption and the date axis */
    svg.appendChild(SC.svg('text', { 'class': 'sc-chart__faint', x: plot.left + 2, y: g.vol.top + 9 }, 'vol'));
    if (g.volMax) svg.appendChild(SC.svg('text', { 'class': 'sc-chart__faint', x: plot.right + 9, y: g.vol.top + 9 }, fmtVol(g.volMax)));
    var axis = SC.svg('g');
    for (i = 0; i < g.dateTicks.length; i++) {
      var tkx = g.dateTicks[i].x;
      axis.appendChild(SC.svg('line', { 'class': 'sc-chart__grid', x1: tkx, x2: tkx, y1: g.vol.bottom, y2: g.vol.bottom + 4 }));
      axis.appendChild(SC.svg('text', { x: tkx + 3, y: g.axisY, 'text-anchor': 'start' }, g.dateTicks[i].label));
    }
    svg.appendChild(axis);
    /* crosshair (hidden until a bar is focused) and the hit area */
    var cross = SC.svg('g', { 'class': 'sc-chart__cross', visibility: 'hidden' }, [
      SC.svg('line', { 'class': 'sc-chart__crosshair', x1: 0, x2: 0, y1: plot.top, y2: g.vol.bottom }),
      SC.svg('line', { 'class': 'sc-chart__crosshair', x1: plot.left, x2: plot.right, y1: 0, y2: 0 }),
      SC.svg('circle', { 'class': 'sc-chart__marker', r: 4, cx: 0, cy: 0 })
    ]);
    svg.appendChild(cross);
    svg.appendChild(SC.svg('rect', { 'class': 'sc-chart__hit', x: plot.left, y: plot.top, width: plot.width, height: g.vol.bottom - plot.top }));
    return svg;
  }

  /* ---------- table twin ------------------------------------------------ */
  function levelRows(g, ticker) {
    var rows = [], lc = g.lastClose;
    function vs(p) { return lc ? fmtPct((p / lc - 1) * 100) + ' from last close' : ''; }
    if (g.burst) rows.push(['burst', fmtPrice(g.burst.close), g.burst.date + ' · ' + fmtPct(g.burst.pct) + ' on the day · vol ' + fmtVol(g.burst.volume)]);
    if (g.box) rows.push(['base', fmtPrice(g.box.low) + ' – ' + fmtPrice(g.box.high), g.bars[g.box.start].date + ' → ' + g.bars[g.box.end].date + ' · ' + g.box.sessions + ' sessions']);
    if (g.trigger) rows.push(['trigger', fmtPrice(g.trigger.price), vs(g.trigger.price)]);
    if (g.entry) rows.push(['buy zone', fmtPrice(g.entry.low) + ' – ' + fmtPrice(g.entry.high), 'width ' + fmtPct((g.entry.high / g.entry.low - 1) * 100).replace('+', '')]);
    if (g.stop) rows.push(['stop', fmtPrice(g.stop.price), vs(g.stop.price)]);
    if (g.target) rows.push(['target', fmtPrice(g.target.low) + ' – ' + fmtPrice(g.target.high), g.target.text + (g.target.ref !== null ? ' vs ' + fmtPrice(g.target.ref) : '')]);
    if (lc !== null) rows.push(['last close', fmtPrice(lc), g.bars.length ? g.bars[g.bars.length - 1].date : '']);
    return rows;
  }
  function barRows(g) {
    var rows = [], i, b;
    for (i = g.bars.length - 1; i >= 0 && rows.length < 10; i--) {
      b = g.bars[i];
      rows.push([b.date + (g.burst && g.burst.index === i ? ' ▲ burst' : ''), fmtPrice(b.o), fmtPrice(b.h), fmtPrice(b.l), fmtPrice(b.c), fmtPct(b.pct), fmtVol(b.v)]);
    }
    return rows;
  }
  function buildTwin(SC, g, options) {
    var name = options.ticker || 'the series';
    var details = SC.el('details', { 'class': 'sc-details' }, SC.el('summary', { text: 'table view · last 10 sessions and levels' }));
    var scroll = SC.el('div', { 'class': 'sc-table-scroll' });
    details.appendChild(scroll);
    var bars = SC.tableTwin(scroll, { details: false, caption: name + ': last 10 sessions, newest first',
      head: ['session', 'open', 'high', 'low', 'close', 'chg', 'volume'], rows: barRows(g) });
    bars.setAttribute('data-sc-twin', 'bars');
    var levels = SC.tableTwin(scroll, { details: false, caption: name + ': chart levels', numeric: function (i) { return i === 1; },
      head: ['level', 'price', 'note'], rows: levelRows(g, name) });
    levels.setAttribute('data-sc-twin', 'levels');
    return details;
  }

  /* ---------- legend ---------------------------------------------------- */
  function keyCandle(SC, tone, filled) {
    return SC.svg('svg', { 'class': 'sc-chart__key', width: 8, height: 14, viewBox: '0 0 8 14', 'aria-hidden': 'true', style: toneStyle(tone) }, [
      SC.svg('line', { 'class': 'sc-chart__wick', x1: 4, x2: 4, y1: 1, y2: 3 }),
      SC.svg('rect', { 'class': 'sc-chart__candle' + (filled ? ' is-filled' : ''), x: 1.5, y: 3, width: 5, height: 8 }),
      SC.svg('line', { 'class': 'sc-chart__wick', x1: 4, x2: 4, y1: 11, y2: 13 })
    ]);
  }
  function buildHead(SC, options, g) {
    var head = SC.el('div', { 'class': 'sc-chart__head' });
    if (options.ticker) head.appendChild(SC.el('span', { 'class': 'sc-figure', text: options.ticker }));
    if (options.title) head.appendChild(SC.el('span', { 'class': 'sc-muted', text: options.title }));
    var legend = SC.el('div', { 'class': 'sc-legend' }, [
      SC.el('span', null, [keyCandle(SC, 'chart-emphasis', false), 'up']),
      SC.el('span', null, [keyCandle(SC, 'chart-context', true), 'down'])
    ]);
    if (g.burst) legend.appendChild(SC.el('span', null, [keyCandle(SC, 'accent', false), 'burst']));
    if (g.ma.length) {
      var names = [], i;
      for (i = 0; i < g.ma.length; i++) names.push(g.ma[i].n);
      legend.appendChild(SC.el('span', null, [SC.el('i', { style: 'background:' + SC.toneRef('chart-context') }), names.join('/') + '-day avg']));
    }
    head.appendChild(legend);
    return head;
  }

  /* ---------- the chart ------------------------------------------------- */
  function ariaLabel(g, options) {
    var s = (options.ticker || 'Price') + ' daily candlestick chart';
    if (g.n) s += ', ' + g.n + ' sessions from ' + g.bars[0].date + ' to ' + g.bars[g.n - 1].date;
    if (g.lastClose !== null) s += ', last close ' + fmtPrice(g.lastClose);
    if (g.burst) s += '. Burst ' + fmtPct(g.burst.pct) + ' on ' + g.burst.date;
    if (g.box) s += '. Base of ' + g.box.sessions + ' sessions between ' + fmtPrice(g.box.low) + ' and ' + fmtPrice(g.box.high);
    if (g.entry) s += '. Buy zone ' + fmtPrice(g.entry.low) + ' to ' + fmtPrice(g.entry.high);
    if (g.trigger) s += '. Trigger ' + fmtPrice(g.trigger.price);
    if (g.stop) s += '. Stop ' + fmtPrice(g.stop.price);
    if (g.target) s += '. Target ' + fmtPrice(g.target.low) + ' to ' + fmtPrice(g.target.high);
    return s + '. Use the arrow keys to step through the sessions; the table view below lists the same numbers.';
  }
  function chart(series, options) {
    options = options || {};
    var SC = sc();
    ensureStyle();
    var host = SC.el('div', { 'class': 'sc-chart sc-chart--stock', role: 'group', tabindex: '0' });
    var stage = SC.el('div', { 'class': 'sc-chart__stage' });
    var state = { g: null, svg: null, index: null, pinned: false, width: 0 };
    var tip = SC.tooltip(stage, { live: true, top: 6, flip: 0.55, offsetX: 14 });

    function measure() {
      var wdt = host.clientWidth || (host.parentNode && host.parentNode.clientWidth) || 0;
      return wdt > 0 ? wdt : (options.width || 640);
    }
    function describe(i) {
      var g = state.g, b = g.bars[i], tone = b.candle ? (b.candle.burst ? 'accent' : b.candle.up ? 'chart-emphasis' : 'chart-context') : 'chart-context';
      var rows = [
        { value: fmtPrice(b.o), label: 'open', tone: tone },
        { value: fmtPrice(b.h), label: 'high', tone: tone },
        { value: fmtPrice(b.l), label: 'low', tone: tone },
        { value: fmtPrice(b.c), label: 'close', tone: tone },
        { value: fmtPct(b.pct), label: 'vs prior close', tone: tone },
        { value: fmtVol(b.v), label: 'volume', tone: 'chart-context' }
      ];
      var meta = b.candle ? 'session ' + (i + 1) + ' of ' + g.n : 'no bar recorded (gap)';
      if (b.candle && b.candle.burst) meta = 'burst day · ' + fmtPct(b.pct);
      else if (g.box && i >= g.box.start && i <= g.box.end) meta = 'inside the base · ' + meta;
      return { title: weekday(b.date) + ' ' + b.date, rows: rows, meta: meta };
    }
    function focus(i) {
      var g = state.g;
      if (!g || !g.n) return;
      i = Math.max(0, Math.min(g.n - 1, i));
      state.index = i;
      var b = g.bars[i], cross = state.svg.querySelector('.sc-chart__cross'), lines = cross.querySelectorAll('line'), dot = cross.querySelector('circle');
      var cx = g.x(i), cy = b.c !== null ? g.y(b.c) : null;
      lines[0].setAttribute('x1', cx); lines[0].setAttribute('x2', cx);
      lines[1].setAttribute('visibility', cy === null ? 'hidden' : 'visible');
      if (cy !== null) { lines[1].setAttribute('y1', cy); lines[1].setAttribute('y2', cy); dot.setAttribute('cx', cx); dot.setAttribute('cy', cy); }
      dot.setAttribute('visibility', cy === null ? 'hidden' : 'visible');
      dot.setAttribute('style', toneStyle(b.candle ? (b.candle.burst ? 'accent' : b.candle.up ? 'chart-emphasis' : 'chart-context') : 'chart-context'));
      cross.setAttribute('visibility', 'visible');
      tip.show(describe(i), { px: cx, py: 0 });
    }
    function clear() {
      state.index = null; state.pinned = false;
      if (state.svg) { var cross = state.svg.querySelector('.sc-chart__cross'); if (cross) cross.setAttribute('visibility', 'hidden'); }
      tip.hide();
    }
    function indexAt(e) {
      var g = state.g, rect = state.svg.getBoundingClientRect();
      var px = (e.clientX - rect.left) * (g.width / (rect.width || g.width));
      return Math.floor((px - g.plot.left) / g.slot);
    }
    function wire(svg) {
      var hit = svg.querySelector('.sc-chart__hit');
      hit.addEventListener('pointermove', function (e) { if (e.pointerType === 'touch') return; if (!state.pinned) focus(indexAt(e)); });
      hit.addEventListener('pointerdown', function (e) {
        if (e.pointerType === 'mouse') return;
        var i = indexAt(e);
        if (state.pinned && i === state.index) { clear(); return; }
        state.pinned = true; focus(i); tip.tap(true);
      });
      hit.addEventListener('pointerleave', function (e) { if (e.pointerType !== 'touch' && !state.pinned) clear(); });
    }
    function draw() {
      var wdt = measure(), g = chartGeometry(series, options, wdt, options.height);
      state.g = g; state.width = wdt;
      var svg = buildSvg(g, SC);
      wire(svg);
      if (state.svg) stage.replaceChild(svg, state.svg); else stage.insertBefore(svg, tip.node);
      state.svg = svg;
      host.setAttribute('aria-label', ariaLabel(g, options));
      if (state.index !== null) focus(state.index);
    }
    draw();
    if (!options.compact) host.insertBefore(buildHead(SC, options, state.g), host.firstChild);
    host.appendChild(stage);
    host.appendChild(buildTwin(SC, state.g, options));

    host.addEventListener('keydown', function (e) {
      var g = state.g, key = e.key, start = state.index !== null ? state.index : (g.burst ? g.burst.index : g.n - 1);
      if (key === 'ArrowLeft') focus(state.index === null ? start : start - 1);
      else if (key === 'ArrowRight') focus(state.index === null ? start : start + 1);
      else if (key === 'Home') focus(0);
      else if (key === 'End') focus(g.n - 1);
      else if (key === 'Escape') clear();
      else return;
      e.preventDefault();
    });
    host.addEventListener('blur', function () { if (!state.pinned) clear(); });
    stage.addEventListener('pointerdown', function (e) {
      if (e.pointerType !== 'mouse' && state.pinned && !(e.target && e.target.classList && e.target.classList.contains('sc-chart__hit'))) clear();
    });
    /* the viewBox is the measured width, so text stays 11px at every size;
       re-measure when the host is resized (or first attached) */
    var pending = false;
    function onResize() {
      if (pending) return;
      pending = true;
      (w.requestAnimationFrame || function (f) { setTimeout(f, 16); })(function () {
        pending = false;
        var wdt = measure();
        if (Math.abs(wdt - state.width) >= 4) draw();
      });
    }
    if (w.ResizeObserver) new w.ResizeObserver(onResize).observe(host);
    else w.addEventListener('resize', onResize);
    host.redraw = draw;
    return host;
  }

  SCStock.chart = chart;
  SCStock.chartGeometry = chartGeometry;
  SCStock.sma = sma;
  SCStock.format = { price: fmtPrice, pct: fmtPct, volume: fmtVol };
})(window);
