/* SpicyStock — the burst map: every burst the scan recorded, plotted by the
   session's gain against its volume relative to the previous session, with
   the page's one selection state. A presentation of the recorded
   measurements — no request, no storage, no scoring, no new market data;
   the existing ranking stays authoritative and every burst without a
   measurement stays listed and reachable. Restored from the first build's
   docs/signal-map.js (29e3205) against the current record.

     SCStock.map.render(host, {points, selectedId, session, onSelect, demo})
       -> { update(selectedId), dispose() }

   points: [{id, ticker, gain, volume, grade, score, rank, statusWords,
             statusTone, source: 'claude'|'checklist'|null, chartSeen}]
   gain   = bursts[].gain_pct, the session's close against the previous close
   volume = bursts[].volume_vs_prior, the session's volume over the previous
            session's (NOT a 50-day relative volume) */
(function (w) {
  'use strict';
  const SCStock = w.SCStock = w.SCStock || {};
  const el = (tag, attrs, kids) => w.SC.el(tag, attrs, kids);
  const svg = (tag, attrs, kids) => w.SC.svg(tag, attrs, kids);
  const isNum = (v) => typeof v === 'number' && isFinite(v);
  const pct = (v) => isNum(v) ? (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(1) + '%' : '—';
  const times = (v) => isNum(v) ? v.toFixed(1) + '×' : '—';
  const X_TITLE = 'Gain on the session vs previous close (%)';
  const Y_TITLE = 'Volume vs previous session (×)';
  const LABEL_ALL_UNDER = 9;     // this many points or fewer wear their ticker always; more label only the chosen and the focused
  const STACK_PX = 7;            // two points closer than this (px) share a spot and say so
  const LABEL_MIN_WIDTH = 480;   // a plot narrower than this (px) labels only the chosen, the focused and the hovered point
  const canPlot = (p) => isNum(p.gain) && isNum(p.volume) && p.volume >= 0;
  const sourceWords = (p) => p.source === 'claude' ? 'chart reader' : p.source === 'checklist' ? 'checklist alone' : 'source not recorded';
  const sourceGlyph = (p) => p.source === 'claude' ? '●' : p.source === 'checklist' ? '○' : '◌';
  function describe(p) {
    return p.ticker + ': ' + pct(p.gain) + ' on the session vs previous close, volume ' + times(p.volume) + ' the previous session'
      + (p.grade ? ', ' + p.grade + (isNum(p.score) ? ' ' + p.score.toFixed(1) : '') : '') + (isNum(p.rank) ? ', rank ' + p.rank : '') + ', ' + sourceWords(p)
      + (p.statusWords ? ', ' + p.statusWords : '') + '.';
  }

  function render(host, opts) {
    opts = opts || {};
    const points = (opts.points || []).filter((p) => p && p.id && p.ticker);
    const plotted = points.filter(canPlot), missing = points.filter((p) => !canPlot(p));
    let selectedId = opts.selectedId || null, observer = null;
    const markers = {};
    while (host.firstChild) host.removeChild(host.firstChild);
    host.classList.add('ss-map');
    host.setAttribute('data-plotted', String(plotted.length));
    host.setAttribute('data-missing', String(missing.length));

    const head = el('div', { 'class': 'ss-map__head' }, [
      el('div', null, [el('h3', { 'class': 'ss-map__title', text: 'Burst map' }), el('p', { 'class': 'ss-map__stamp', text: (opts.sessionWords ? 'session ' + opts.sessionWords : 'session not recorded') + (opts.demo ? ' · demo data' : '') })]),
      el('p', { 'class': 'ss-map__count', 'data-counts': '', text: points.length + ' burst' + (points.length === 1 ? '' : 's') + ' · ' + plotted.length + ' plotted' + (missing.length ? ' · ' + missing.length + ' without a measurement' : '') })
    ]);
    const surface = el('div', { 'class': 'ss-map__surface', role: 'group', 'aria-label': 'Bursts by the session’s gain and its volume relative to the previous session' });
    const legend = el('div', { 'class': 'ss-map__legend', 'aria-hidden': 'true' }, [
      el('span', { text: '● chart reader' }), el('span', { text: '○ checklist alone' }),
      points.some((p) => p.source !== 'claude' && p.source !== 'checklist') ? el('span', { text: '◌ source not recorded' }) : null
    ]);
    const selection = el('p', { 'class': 'ss-map__selection', role: 'status', 'aria-live': 'polite' });
    const note = el('p', { 'class': 'ss-map__note', text: 'Each point is a recorded burst. Position is a measurement on the recorded session — the close against the previous close, the volume against the previous session — not a predicted return.' + (missing.length ? ' ' + missing.length + ' burst' + (missing.length === 1 ? ' lacks' : 's lack') + ' a complete measurement and stay listed below.' : '') });
    host.appendChild(head); host.appendChild(surface); host.appendChild(legend); host.appendChild(selection); host.appendChild(note);

    // the bursts without a point, each a way into its card
    if (missing.length) {
      const list = el('div', { 'class': 'ss-map__missing' }, [el('span', { 'class': 'sc-eyebrow', text: 'not plotted' })]);
      missing.forEach((p) => {
        const b = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', 'data-id': p.id, 'aria-pressed': p.id === selectedId ? 'true' : 'false', text: p.ticker + ' · no ' + (isNum(p.gain) ? 'volume' : 'gain') + ' measurement' });
        b.addEventListener('click', () => choose(p.id));
        list.appendChild(b);
      });
      host.appendChild(list);
    }
    // the table twin: every burst, plotted or not, with a select button
    const details = el('details', { 'class': 'sc-details ss-map__table' }, [el('summary', { text: 'table view · every burst and its measurements' })]);
    const table = el('table', { 'class': 'sc-table sc-table--compact' });
    table.appendChild(el('caption', { 'class': 'sc-sr-only', text: 'Every recorded burst: gain on the session, volume vs previous session, grade, rank, source' }));
    table.appendChild(el('thead', null, el('tr', null, ['burst', 'gain', 'volume vs prev', 'grade', 'rank', 'source', 'plotted'].map((h, i) => el('th', { scope: 'col', 'class': i === 1 || i === 2 || i === 4 ? 'sc-num' : null, text: h })))));
    const tbody = el('tbody');
    points.forEach((p) => {
      const b = el('button', { 'class': 'sc-signal-matrix__name', type: 'button', 'data-id': p.id, 'aria-pressed': p.id === selectedId ? 'true' : 'false', text: p.ticker });
      b.addEventListener('click', () => choose(p.id));
      tbody.appendChild(el('tr', { 'data-id': p.id }, [
        el('th', { scope: 'row', 'class': 'sc-case' }, b), el('td', { 'class': 'sc-num', text: pct(p.gain) }), el('td', { 'class': 'sc-num', text: times(p.volume) }),
        el('td', { text: (p.grade || '—') + (isNum(p.score) ? ' · ' + p.score.toFixed(1) : '') }), el('td', { 'class': 'sc-num', text: isNum(p.rank) ? String(p.rank) : '—' }),
        el('td', { text: sourceWords(p) }), el('td', { text: canPlot(p) ? 'yes' : 'no' })
      ]));
    });
    table.appendChild(tbody);
    details.appendChild(el('div', { 'class': 'sc-table-scroll' }, table));
    host.appendChild(details);

    function choose(id) {
      selectedId = id;
      update(id);
      if (typeof opts.onSelect === 'function') opts.onSelect(id);
    }
    function update(id) {
      selectedId = id || null;
      let chosen = null;
      Object.keys(markers).forEach((k) => {
        const on = k === selectedId;
        markers[k].classList.toggle('is-selected', on);
        markers[k].setAttribute('aria-pressed', on ? 'true' : 'false');
        if (on) chosen = markers[k];
      });
      host.querySelectorAll('.ss-map__missing button, .ss-map__table button').forEach((b) => b.setAttribute('aria-pressed', b.getAttribute('data-id') === selectedId ? 'true' : 'false'));
      const p = points.find((x) => x.id === selectedId);
      selection.textContent = p ? describe(p) + (canPlot(p) ? (p.stackWith && p.stackWith.length ? ' Shares its spot with ' + p.stackWith.join(', ') + '.' : ' Highlighted on the map.') : ' Not plotted: the measurement is incomplete.') : (points.length ? 'Choose a burst to see its measurements.' : 'No bursts to map.');
      host.setAttribute('data-selected', selectedId || '');
      return chosen;
    }

    function draw() {
      while (surface.firstChild) surface.removeChild(surface.firstChild);
      Object.keys(markers).forEach((k) => { delete markers[k]; });
      if (!plotted.length) {
        surface.appendChild(el('div', { 'class': 'ss-map__empty' }, [el('strong', { text: points.length ? 'No complete measurements to plot.' : 'No bursts on this session.' }), el('span', { text: points.length ? 'Every burst remains in the table below and in the cards.' : 'The map fills when a run records bursts.' })]));
        return;
      }
      const width = Math.max(260, surface.clientWidth || 640), height = Math.max(280, Math.min(440, Math.round(width * 0.42)));
      surface.style.height = height + 'px';
      const left = 56, right = width - 22, top = 26, bottom = height - 54;
      const gains = plotted.map((p) => p.gain), volumes = plotted.map((p) => p.volume);
      const lowX = Math.min(0, Math.floor(Math.min.apply(null, gains))), highX = Math.max(1, Math.ceil(Math.max.apply(null, gains) * 1.08));
      const highY = Math.max(1, Math.ceil(Math.max.apply(null, volumes) * 1.08));
      const x = (v) => left + (v - lowX) / (highX - lowX) * (right - left), y = (v) => bottom - v / highY * (bottom - top);
      const s = svg('svg', { width: width, height: height, viewBox: '0 0 ' + width + ' ' + height, 'aria-hidden': 'true', focusable: 'false' });
      for (let i = 0; i <= 4; i++) {
        const gx = lowX + (highX - lowX) * i / 4, gy = highY * i / 4;
        s.appendChild(svg('line', { 'class': 'ss-map__grid', x1: x(gx), x2: x(gx), y1: top, y2: bottom }));
        s.appendChild(svg('line', { 'class': 'ss-map__grid', x1: left, x2: right, y1: y(gy), y2: y(gy) }));
        s.appendChild(svg('text', { 'class': 'ss-map__axis', x: x(gx), y: bottom + 18, 'text-anchor': 'middle' }, (gx > 0 ? '+' : '') + gx.toFixed(1) + '%'));
        s.appendChild(svg('text', { 'class': 'ss-map__axis', x: left - 8, y: y(gy) + 4, 'text-anchor': 'end' }, gy.toFixed(1) + '×'));
      }
      if (lowX < 0) s.appendChild(svg('line', { 'class': 'ss-map__zero', x1: x(0), x2: x(0), y1: top, y2: bottom }));
      s.appendChild(svg('text', { 'class': 'ss-map__axis-title', x: left, y: 14 }, Y_TITLE));
      s.appendChild(svg('text', { 'class': 'ss-map__axis-title', x: (left + right) / 2, y: height - 8, 'text-anchor': 'middle' }, X_TITLE));
      surface.appendChild(s);
      // stacks: points within STACK_PX share a spot; every one keeps its coordinates and its own button
      const placed = [];
      plotted.forEach((p) => { p.stackWith = []; });
      plotted.forEach((p) => {
        const px = x(p.gain), py = y(p.volume);
        placed.forEach((q) => { if (Math.abs(q.px - px) < STACK_PX && Math.abs(q.py - py) < STACK_PX) { p.stackWith.push(q.p.ticker); q.p.stackWith.push(p.ticker); } });
        placed.push({ p: p, px: px, py: py });
      });
      const labelAll = plotted.length <= LABEL_ALL_UNDER && width >= LABEL_MIN_WIDTH;
      placed.forEach((q) => {
        const p = q.p;
        const b = el('button', { 'class': 'ss-map__point' + (p.source === 'claude' ? '' : p.source === 'checklist' ? ' is-checklist' : ' is-unknown') + (labelAll ? ' is-labelled' : ''), type: 'button', 'data-id': p.id, 'data-ticker': p.ticker, 'data-gain': String(p.gain), 'data-volume': String(p.volume), 'aria-pressed': p.id === selectedId ? 'true' : 'false', 'aria-label': describe(p) + (p.stackWith.length ? ' Shares its spot with ' + p.stackWith.join(', ') + '.' : ''), title: describe(p) });
        b.style.left = q.px + 'px'; b.style.top = q.py + 'px';
        b.appendChild(el('span', { 'class': 'ss-map__dot', 'aria-hidden': 'true' }));
        b.appendChild(el('span', { 'class': 'ss-map__label', 'aria-hidden': 'true', text: p.ticker + (p.stackWith.length ? ' +' + p.stackWith.length : '') }));
        if (p.stackWith.length) b.appendChild(el('span', { 'class': 'ss-map__stack', 'aria-hidden': 'true', text: String(p.stackWith.length + 1) }));
        b.addEventListener('click', () => choose(p.id));
        surface.appendChild(b);
        markers[p.id] = b;
      });
      update(selectedId);
    }
    // the keyboard: arrows move between the points in rank order, Enter/Space chooses (a button)
    surface.addEventListener('keydown', (e) => {
      const list = Array.from(surface.querySelectorAll('.ss-map__point')), i = list.indexOf(w.document.activeElement);
      if (i < 0) return;
      let j;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') j = Math.min(list.length - 1, i + 1);
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') j = Math.max(0, i - 1);
      else if (e.key === 'Home') j = 0; else if (e.key === 'End') j = list.length - 1; else return;
      e.preventDefault(); list[j].focus();
    });
    draw();
    if (w.ResizeObserver) {
      let last = surface.clientWidth;
      observer = new w.ResizeObserver(() => { const now = surface.clientWidth; if (Math.abs(now - last) >= 4) { last = now; draw(); } });
      observer.observe(surface);
    }
    return {
      update: update,
      focusSelected: function () { const m = markers[selectedId]; if (m) m.focus(); },
      dispose: function () { if (observer) observer.disconnect(); observer = null; }
    };
  }
  SCStock.map = { render: render, describe: describe, X_TITLE: X_TITLE, Y_TITLE: Y_TITLE };
})(window);
