/* SpicyStock — the burst map: every burst the scan recorded, plotted by the
   session's gain against its volume relative to the previous session, with
   the page's one selection state. A presentation of the recorded
   measurements — no request, no storage, no scoring, no new market data;
   the existing ranking stays authoritative and every burst without a
   measurement stays listed and reachable. Restored from the first build's
   docs/signal-map.js (29e3205) against the current record.

     SCStock.map.render(host, {points, selectedId, session, onSelect, demo, subset})
       -> { update(selectedId), dispose() }

   points is whatever the page's one visible-candidate selector handed over --
   the map plots that list and nothing else. `subset: {total, words}` names the
   stage's own total and the lens that narrowed it, so the count line says
   "4 bursts of 401 · A-quality lens" rather than passing a subset off as the
   whole night; without it the count reads as every burst, as it always did.

   points: [{id, ticker, gain, volume, grade, score, rank, statusWords,
             statusTone, source: 'claude'|'checklist'|null, chartSeen}]
   gain   = bursts[].gain_pct, the session's close against the previous close
   volume = bursts[].volume_vs_prior, the session's volume over the previous
            session's (NOT a 50-day relative volume), as docs/app.js
            volumeRatio() reads it: the row's own field, else the checklist's
            two-place copy in a record from before the dollar scan carried
            it, else null -- and a null point is listed, never invented */
(function (w) {
  'use strict';
  const SCStock = w.SCStock = w.SCStock || {};
  const el = (tag, attrs, kids) => w.SC.el(tag, attrs, kids);
  const svg = (tag, attrs, kids) => w.SC.svg(tag, attrs, kids);
  const isNum = (v) => typeof v === 'number' && isFinite(v);
  const pct = (v) => isNum(v) ? (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(1) + '%' : '—';
  const times = (v) => isNum(v) ? v.toFixed(1) + '×' : '—';
  const X_TITLE = 'Gain on the session vs previous close (%)';
  const Y_TITLE = 'Volume vs previous session (×, compressed)';
  const LABEL_ALL_UNDER = 9;     // this many points or fewer wear their ticker always; more label only the chosen and the focused
  const LABEL_MIN_WIDTH = 480;   // a plot narrower than this (px) labels only the chosen, the focused and the hovered point
  // The gain axis is linear: a percentage move is read as a percentage move.
  // Volume relative to the previous session is a RATIO with no upper bound,
  // and a linear axis over it is unreadable the moment one name runs away.
  // On the published record of 2026-09-11 one burst printed 168.8x while the
  // median printed 1.1x, and the pane put 391 of 401 points within five
  // pixels of its floor, across twelve distinct pixel rows. So the volume
  // axis is compressed:
  //     y(v) = log1p(v / VOLUME_KNEE) / log1p(top / VOLUME_KNEE)
  // and the compression is a POSITION only. log1p is defined at zero and
  // returns zero there, so a session that printed no volume against a
  // previous session that did sits ON the floor -- a value, told apart from a
  // burst with no measurement at all, which is not plotted and is listed by
  // name below. Under VOLUME_KNEE the curve is effectively linear. The top of
  // the axis is still the largest recorded ratio with the same headroom a
  // linear axis had, so no outlier is clipped, binned or winsorised, and
  // every tick is labelled with the ratio it actually stands for.
  const VOLUME_KNEE = 0.25;      // the ratio under which the volume axis is effectively linear
  const VOLUME_TICKS = [0, 0.25, 0.5, 1, 1.5, 2, 3, 5, 10, 25, 50, 100, 250, 500, 1000];
  const TICK_MIN_GAP = 20;       // px between two volume labels before the upper one is dropped
  const X_TICKS = 4;             // the linear gain axis keeps its even divisions
  // A tap is a finger, not a pixel: every point whose centre is this close to
  // the tap is a candidate for it, the dot's own radius is far smaller, and
  // the topmost button is never taken on its own when another is in reach.
  // Half .ss-map__point's 44px box, which is what the browser hit-tests.
  const TAP_RADIUS = 22;
  const NEARBY_SHOWN = 10;       // the chooser lists this many, then offers the rest
  const canPlot = (p) => isNum(p.gain) && isNum(p.volume) && p.volume >= 0;
  const tickWords = (v) => String(+Number(v).toFixed(2)) + '×';

  /** The volume axis: a position for a ratio, and the ticks that name it.
      `at(v)` is 0 at zero and 1 at the top; `ticks` are real ratios. */
  function volumeScale(top, px) {
    const span = Math.log1p(top / VOLUME_KNEE) || 1;
    const at = (v) => (v > 0 ? Math.log1p(v / VOLUME_KNEE) / span : 0);
    const wanted = VOLUME_TICKS.filter((t) => t < top).concat([top]);
    const ticks = [];
    wanted.forEach((t) => {
      const y = at(t) * px;
      if (!ticks.length || y - at(ticks[ticks.length - 1]) * px >= TICK_MIN_GAP) ticks.push(t);
    });
    // the top is the largest recorded ratio and always keeps its label
    if (ticks[ticks.length - 1] !== top) {
      while (ticks.length > 1 && (at(top) - at(ticks[ticks.length - 1])) * px < TICK_MIN_GAP) ticks.pop();
      ticks.push(top);
    }
    return { at: at, top: top, ticks: ticks };
  }
  const SCALE_WORDS = 'The volume axis is compressed: the ratio has no upper bound, so one runaway name would otherwise flatten every other point onto the floor. Each label is the ratio it stands for, every burst sits at its own recorded ratio, the largest is never clipped, and 0× is on the axis line. The gain axis is linear.';
  const sourceWords = (p) => p.source === 'claude' ? 'chart reader' : p.source === 'checklist' ? 'checklist alone' : 'source not recorded';
  const sourceGlyph = (p) => p.source === 'claude' ? '●' : p.source === 'checklist' ? '○' : '◌';
  const nearWords = (n) => n + ' other' + (n === 1 ? '' : 's') + ' within a finger of this point';
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
    const markers = {}, placed = [];   // placed: one entry per plotted point, its pane coordinates
    while (host.firstChild) host.removeChild(host.firstChild);
    host.classList.add('ss-map');
    host.setAttribute('data-plotted', String(plotted.length));
    host.setAttribute('data-missing', String(missing.length));
    host.setAttribute('data-nearby', 'closed');

    const head = el('div', { 'class': 'ss-map__head' }, [
      el('div', null, [el('h3', { 'class': 'ss-map__title', text: 'Burst map' }), el('p', { 'class': 'ss-map__stamp', text: (opts.sessionWords ? 'session ' + opts.sessionWords : 'session not recorded') + (opts.demo ? ' · demo data' : '') })]),
      // the subset the page handed it, reconciled with the stage's own total,
      // so a narrowed map never reads as the whole night
      el('p', { 'class': 'ss-map__count', 'data-counts': '', text: points.length + ' burst' + (points.length === 1 ? '' : 's')
        + (opts.subset && isNum(opts.subset.total) ? ' of ' + opts.subset.total + (opts.subset.words ? ' · ' + opts.subset.words : '') : '')
        + ' · ' + plotted.length + ' plotted' + (missing.length ? ' · ' + missing.length + ' without a measurement' : '') })
    ]);
    const surface = el('div', { 'class': 'ss-map__surface', role: 'group', 'aria-label': 'Bursts by the session’s gain and its volume relative to the previous session' });
    const legend = el('div', { 'class': 'ss-map__legend', 'aria-hidden': 'true' }, [
      el('span', { text: '● chart reader' }), el('span', { text: '○ checklist alone' }),
      points.some((p) => p.source !== 'claude' && p.source !== 'checklist') ? el('span', { text: '◌ source not recorded' }) : null
    ]);
    const selection = el('p', { 'class': 'ss-map__selection', role: 'status', 'aria-live': 'polite' });
    // the selected point's way into the nearby chooser, for a reader who
    // arrived by the keyboard, by search or from a card rather than by a tap
    const nearbyBtn = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm ss-map__nearby-open', type: 'button', hidden: true });
    const selectionRow = el('div', { 'class': 'ss-map__selection-row' }, [selection, nearbyBtn]);
    const note = el('p', { 'class': 'ss-map__note', text: 'Each point is a recorded burst. Position is a measurement on the recorded session — the close against the previous close, the volume against the previous session — not a predicted return. ' + SCALE_WORDS + (missing.length ? ' ' + missing.length + ' burst' + (missing.length === 1 ? ' lacks' : 's lack') + ' a complete measurement and stay listed below.' : '') });
    host.appendChild(head); host.appendChild(surface); host.appendChild(legend); host.appendChild(selectionRow); host.appendChild(note);

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
      // the panel describes one tap; a selection made from the table, a card,
      // the search or the route is a different answer, so the panel goes
      closeNearby(false);
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
      const near = p && p.near ? p.near.length : 0;
      selection.textContent = p ? describe(p) + (canPlot(p) ? (near ? ' ' + cap(nearWords(near)) + '.' : ' Highlighted on the map.') : ' Not plotted: the measurement is incomplete.') : (points.length ? 'Choose a burst to see its measurements.' : 'No bursts to map.');
      nearbyBtn.hidden = !near;
      nearbyBtn.textContent = near ? 'Nearby stocks (' + (near + 1) + ')' : '';
      nearbyBtn.setAttribute('aria-label', near ? 'Choose among the ' + (near + 1) + ' stocks within a finger of this point, including ' + p.ticker : '');
      host.setAttribute('data-selected', selectedId || '');
      host.setAttribute('data-near', String(near));
      return chosen;
    }
    const cap = (s) => s ? s.charAt(0).toUpperCase() + s.slice(1) : s;

    // ---- the nearby chooser -------------------------------------------
    // Points overlap: on the published record of 2026-09-11 a phone put 393
    // of 401 markers under another marker's 44px hit box, so a tap at RVTY's
    // own centre selected PDS -- whichever button was appended last. A tap is
    // therefore resolved by DISTANCE from the tap, not by stacking order, and
    // when more than one point is in reach the page asks instead of guessing.
    // Nothing is hidden: the list is nearest-first, it counts what it has not
    // shown yet, and one button reveals the rest without leaving the panel.
    let panel = null, panelOpener = null;
    // `refocus` asks for the focus back; holding it is reason enough. A panel
    // removed with the focus inside drops it on <body>, and the map's arrow
    // keys then do nothing until a point is focused again.
    function closeNearby(refocus) {
      if (!panel) return;
      const held = panel.contains(w.document.activeElement);
      if (panel.parentNode) panel.parentNode.removeChild(panel);
      panel = null;
      if ((refocus || held) && panelOpener && panelOpener.focus && w.document.contains(panelOpener)) panelOpener.focus();
      panelOpener = null;
      host.setAttribute('data-nearby', 'closed');
    }
    // `back` is where Escape and Close hand the focus: NEVER the button the
    // browser hit-tested, which is the one the chooser exists to refuse. A
    // reader who taps LMAT, cancels and presses Enter must not land on the
    // marker that happened to be drawn last over it.
    function openNearby(list, at, back) {
      closeNearby(false);
      panelOpener = back || w.document.activeElement;
      let shown = Math.min(NEARBY_SHOWN, list.length);
      const head = el('div', { 'class': 'ss-map__nearby-head' }, [
        el('h4', { id: 'ss-map-nearby-h', text: list.length + ' stocks within a finger of this tap' }),
        el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', text: 'Close', 'data-nearby': 'close' })
      ]);
      const hint = el('p', { 'class': 'ss-map__nearby-hint' });
      const items = el('div', { 'class': 'ss-map__nearby-list', role: 'group', 'aria-label': 'The stocks within a finger of the tap, nearest first' });
      // a labelled popover, not a modal: the page behind it stays live, so
      // claiming aria-modal would tell a screen reader in browse mode that the
      // rest of the page does not exist while it is up
      panel = el('div', { 'class': 'ss-map__nearby', role: 'dialog', 'aria-labelledby': 'ss-map-nearby-h' }, [head, hint, items]);
      function fill() {
        while (items.firstChild) items.removeChild(items.firstChild);
        list.slice(0, shown).forEach((q) => {
          const p = q.p;
          const b = el('button', { 'class': 'ss-map__nearby-item', type: 'button', 'data-id': p.id, 'data-ticker': p.ticker, 'aria-pressed': p.id === selectedId ? 'true' : 'false' }, [
            el('b', { 'class': 'sc-case', text: p.ticker }),
            el('span', { 'class': 'ss-map__nearby-measures', text: pct(p.gain) + ' · ' + times(p.volume) + ' volume' }),
            el('span', { 'class': 'ss-map__nearby-grade', text: (p.grade || '—') + (isNum(p.rank) ? ' · rank ' + p.rank : '') })
          ]);
          b.addEventListener('click', () => { const id = p.id; closeNearby(false); choose(id); const m = markers[id]; if (m) m.focus(); });
          items.appendChild(b);
        });
        if (shown < list.length) {
          const more = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm ss-map__nearby-more', type: 'button', 'data-nearby': 'more', text: 'Show the other ' + (list.length - shown) });
          more.addEventListener('click', () => { shown = list.length; fill(); const first = items.querySelector('.ss-map__nearby-item'); if (first) first.focus(); });
          items.appendChild(more);
        }
        hint.textContent = 'The ' + Math.min(shown, list.length) + ' nearest the tap, of ' + list.length + '. None is chosen until you choose one; Escape closes this, and every burst is also in the cards and the table below.';
      }
      fill();
      head.querySelector('[data-nearby="close"]').addEventListener('click', () => closeNearby(true));
      panel.addEventListener('keydown', (e) => {
        const buttons = Array.from(panel.querySelectorAll('button'));
        const i = buttons.indexOf(w.document.activeElement);
        if (e.key === 'Escape') { e.preventDefault(); closeNearby(true); return; }
        if (i < 0) return;
        let j;
        // the arrows walk the list; Tab is left alone, because a popover that
        // holds the focus in against Tab is a trap whatever its role says
        if (e.key === 'ArrowDown' || e.key === 'ArrowRight') j = (i + 1) % buttons.length;
        else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') j = (i - 1 + buttons.length) % buttons.length;
        else if (e.key === 'Home') j = 0; else if (e.key === 'End') j = buttons.length - 1;
        else return;
        e.preventDefault(); buttons[j].focus();
      });
      // Tab out and the panel has been left: it described one tap, and the
      // reader has moved on. Closing here must not take the focus back.
      panel.addEventListener('focusout', (e) => {
        if (!panel || (e.relatedTarget && panel.contains(e.relatedTarget))) return;
        if (e.relatedTarget) closeNearby(false);
      });
      surface.appendChild(panel);
      // inside the pane, clamped to it, so a tap near an edge stays readable
      const box = panel.getBoundingClientRect(), pane = surface.getBoundingClientRect();
      panel.style.left = Math.max(6, Math.min(at.x - box.width / 2, pane.width - box.width - 6)) + 'px';
      panel.style.top = Math.max(6, Math.min(at.y + 14, pane.height - box.height - 6)) + 'px';
      host.setAttribute('data-nearby', 'open');
      const first = items.querySelector('.ss-map__nearby-item');
      if (first) first.focus();
    }
    // every plotted point within a finger of (x, y), nearest first
    function nearbyAt(x, y) {
      return placed
        .map((q) => ({ p: q.p, d: Math.sqrt((q.px - x) * (q.px - x) + (q.py - y) * (q.py - y)) }))
        .filter((q) => q.d <= TAP_RADIUS)
        .sort((a, b) => a.d - b.d);
    }
    function tapped(p, e) {
      // A keyboard Enter or Space on a focused point names that point and no
      // other, so it is taken as chosen; only a pointer needs disambiguating.
      // Measured in Chromium: a mouse click reports detail 1 and pointerType
      // 'mouse', a touch tap detail 1 and 'touch', and Enter or Space on a
      // focused button detail 0, pointerType '' and clientX/Y at the origin.
      const fromPointer = !!e && (e.detail > 0 || (typeof e.pointerType === 'string' && e.pointerType !== ''));
      if (!fromPointer) { choose(p.id); return; }
      const pane = surface.getBoundingClientRect();
      const x = e.clientX - pane.left, y = e.clientY - pane.top;
      const list = nearbyAt(x, y);
      if (list.length > 1) { openNearby(list, { x: x, y: y }, markers[selectedId] || markers[list[0].p.id]); return; }
      choose(list.length === 1 ? list[0].p.id : p.id);
    }
    nearbyBtn.addEventListener('click', () => {
      const q = placed.find((x) => x.p.id === selectedId);
      if (q) openNearby(nearbyAt(q.px, q.py), { x: q.px, y: q.py }, nearbyBtn);
    });

    function draw() {
      // a redraw destroys every marker, so the focus cannot be handed back
      // until they exist again
      const hadFocus = !!panel && panel.contains(w.document.activeElement);
      closeNearby(false);
      while (surface.firstChild) surface.removeChild(surface.firstChild);
      Object.keys(markers).forEach((k) => { delete markers[k]; });
      placed.length = 0;
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
      const vol = volumeScale(highY, bottom - top);
      const x = (v) => left + (v - lowX) / (highX - lowX) * (right - left), y = (v) => bottom - vol.at(v) * (bottom - top);
      const s = svg('svg', { width: width, height: height, viewBox: '0 0 ' + width + ' ' + height, 'aria-hidden': 'true', focusable: 'false' });
      for (let i = 0; i <= X_TICKS; i++) {
        const gx = lowX + (highX - lowX) * i / X_TICKS;
        s.appendChild(svg('line', { 'class': 'ss-map__grid', x1: x(gx), x2: x(gx), y1: top, y2: bottom }));
        s.appendChild(svg('text', { 'class': 'ss-map__axis', x: x(gx), y: bottom + 18, 'text-anchor': 'middle' }, (gx > 0 ? '+' : '') + gx.toFixed(1) + '%'));
      }
      vol.ticks.forEach((gy) => {
        s.appendChild(svg('line', { 'class': 'ss-map__grid', x1: left, x2: right, y1: y(gy), y2: y(gy) }));
        s.appendChild(svg('text', { 'class': 'ss-map__axis', 'data-tick': String(gy), x: left - 8, y: y(gy) + 4, 'text-anchor': 'end' }, tickWords(gy)));
      });
      if (lowX < 0) s.appendChild(svg('line', { 'class': 'ss-map__zero', x1: x(0), x2: x(0), y1: top, y2: bottom }));
      s.appendChild(svg('text', { 'class': 'ss-map__axis-title', x: left, y: 14 }, Y_TITLE));
      s.appendChild(svg('text', { 'class': 'ss-map__axis-title', x: (left + right) / 2, y: height - 8, 'text-anchor': 'middle' }, X_TITLE));
      surface.appendChild(s);
      // every point keeps its own coordinates and its own button; the crowd
      // is counted by the same radius a tap is resolved by, so the badge, the
      // spoken label and the chooser are one rule with one number
      plotted.forEach((p) => {
        placed.push({ p: p, px: x(p.gain), py: y(p.volume) });
      });
      placed.forEach((q) => { q.p.near = []; });
      for (let i = 0; i < placed.length; i++) {
        for (let j = i + 1; j < placed.length; j++) {
          const dx = placed[i].px - placed[j].px, dy = placed[i].py - placed[j].py;
          if (dx * dx + dy * dy <= TAP_RADIUS * TAP_RADIUS) { placed[i].p.near.push(placed[j].p.ticker); placed[j].p.near.push(placed[i].p.ticker); }
        }
      }
      const labelAll = plotted.length <= LABEL_ALL_UNDER && width >= LABEL_MIN_WIDTH;
      placed.forEach((q) => {
        const p = q.p;
        const b = el('button', { 'class': 'ss-map__point' + (p.source === 'claude' ? '' : p.source === 'checklist' ? ' is-checklist' : ' is-unknown') + (labelAll ? ' is-labelled' : ''), type: 'button', 'data-id': p.id, 'data-ticker': p.ticker, 'data-gain': String(p.gain), 'data-volume': String(p.volume), 'data-near': String(p.near.length), 'aria-pressed': p.id === selectedId ? 'true' : 'false', 'aria-label': describe(p) + (p.near.length ? ' ' + cap(nearWords(p.near.length)) + '; choosing it takes this one, and the Nearby stocks button beside the selection lists the rest.' : ''), title: describe(p) });
        b.style.left = q.px + 'px'; b.style.top = q.py + 'px';
        b.appendChild(el('span', { 'class': 'ss-map__dot', 'aria-hidden': 'true' }));
        b.appendChild(el('span', { 'class': 'ss-map__label', 'aria-hidden': 'true', text: p.ticker + (p.near.length ? ' +' + p.near.length : '') }));
        if (p.near.length) b.appendChild(el('span', { 'class': 'ss-map__stack', 'aria-hidden': 'true', text: String(p.near.length + 1) }));
        b.addEventListener('click', (e) => tapped(p, e));
        surface.appendChild(b);
        markers[p.id] = b;
      });
      update(selectedId);
      if (hadFocus && markers[selectedId]) markers[selectedId].focus();
    }
    // the keyboard: arrows move between the points in rank order, Enter/Space
    // chooses the focused point itself (it names one point, so nothing is
    // ambiguous); the nearby list is a button beside the selection line
    surface.addEventListener('keydown', (e) => {
      if (panel) return;   // the open chooser owns the keyboard
      const list = Array.from(surface.querySelectorAll('.ss-map__point')), i = list.indexOf(w.document.activeElement);
      if (i < 0) return;
      let j;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') j = Math.min(list.length - 1, i + 1);
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') j = Math.max(0, i - 1);
      else if (e.key === 'Home') j = 0; else if (e.key === 'End') j = list.length - 1; else return;
      e.preventDefault(); list[j].focus();
    });
    // a tap on bare pane closes the chooser; the pane's own points handle
    // their own taps, so this never swallows a selection
    surface.addEventListener('pointerdown', (e) => {
      // the default action of a press on bare pane blurs whatever had the
      // focus, and it runs AFTER this handler, so the focus has to be kept
      // here rather than handed back and then dropped on <body>
      if (panel && !panel.contains(e.target) && !e.target.closest('.ss-map__point')) { e.preventDefault(); closeNearby(true); }
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
      dispose: function () { closeNearby(false); if (observer) observer.disconnect(); observer = null; }
    };
  }
  SCStock.map = { render: render, describe: describe, X_TITLE: X_TITLE, Y_TITLE: Y_TITLE,
    VOLUME_KNEE: VOLUME_KNEE, VOLUME_TICKS: VOLUME_TICKS, TAP_RADIUS: TAP_RADIUS,
    NEARBY_SHOWN: NEARBY_SHOWN, SCALE_WORDS: SCALE_WORDS, volumeScale: volumeScale };
})(window);
