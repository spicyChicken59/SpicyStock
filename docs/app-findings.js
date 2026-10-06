/* docs/app-findings.js -- the record, night by night.

   SCStock.findings mounts the historical-findings replay: the market the
   gate read on every session the records know, the scan's bursts on every
   published night, and what the counterfactual tickets of that night did
   over their hold, stepped one night at a time the way the Method
   walkthrough steps one burst. It reads no record, no clock and no
   storage: app.js hands it the committed docs/historical-findings.json,
   which tools/build_historical_findings.py built from the evidence files
   and tests/test_historical_findings.py holds to them. Every number this
   module prints is a field of that file; the only arithmetic here is
   drawing (a value to a pixel), never a figure the file does not carry.

   Colours are tone SLOTS through the --sc-tone channel; app.css declares
   every fill and stroke as var(--sc-tone, fallback), so a theme flip
   re-resolves with no script. The outcome axis is COMPRESSED (a signed
   log1p, like the map's volume axis): it is a position and never a value,
   its ticks are real multiples, nothing is clipped, and every R stays in
   the table twin. */
(function (w) {
  'use strict';
  const S = w.SCStock = w.SCStock || {};
  const VERSION = 'historical-findings-v1';
  const INTERVAL = 5000;    // ms per Play step; tests inject SCStock.findingsInterval
  const STRATA = ['admitted', 'B', 'C', 'skip', 'vetoed', 'all'];
  const STRATUM_WORDS = { admitted: 'A-quality', B: 'graded B', C: 'graded C', skip: 'graded skip', vetoed: 'vetoed', all: 'every burst' };
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const VERDICT_TONE = { green: 'good', yellow: 'warn', red: 'danger' };
  const CHAR = 6.5;         // px per glyph of the 10.5px mono the chart text wears
  const GOLDEN = 0.6180339887;
  let mounted = 0;

  // ---- words for numbers: every one a field of the file ------------------
  const isNum = (v) => typeof v === 'number' && isFinite(v);
  const thousands = (s) => String(s).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  const num = (v) => isNum(v) ? thousands(v) : '—';
  const fixed = (v, d) => isNum(v) ? v.toFixed(d) : '—';
  const sign = (v) => v > 0 ? '+' : v < 0 ? '−' : '';
  const signed = (v, d) => isNum(v) ? sign(v) + Math.abs(v).toFixed(d) : '—';
  const rr = (v) => isNum(v) ? signed(v, 2) + 'R' : '—';
  const pct1 = (v) => isNum(v) ? sign(v) + Math.abs(v).toFixed(1) + '%' : '—';
  const share = (v) => isNum(v) ? Math.round(v * 100) + '%' : '—';
  const plain = (v) => isNum(v) ? String(v).replace(/\.0$/, '') : '—';
  const dateOf = (iso) => new Date(iso + 'T12:00:00Z');
  const short = (iso) => iso ? dateOf(iso).getUTCDate() + ' ' + MONTHS[dateOf(iso).getUTCMonth()] : '—';
  const words = (iso) => iso ? DAYS[dateOf(iso).getUTCDay()] + ' ' + short(iso) : '—';
  const plural = (n, noun) => num(n) + ' ' + noun + (n === 1 ? '' : 's');
  const r1 = (v) => Math.round(v * 10) / 10;
  const tone = (slot) => '--sc-tone:var(--sc-' + slot + ')';
  const comp = (v) => Math.sign(v) * Math.log1p(Math.abs(v));   // the compressed outcome axis
  const sizeWords = (m) => m === 0 ? 'no new longs' : m === 1 ? 'full size' : 'size × ' + plain(m);
  const sentence = (parts) => parts.map((t) => /[.!?]$/.test(t) ? t : t + '.').join(' ');
  const underscores = (s) => String(s).replace(/_/g, ' ');

  // ---- geometry: pure, exported, drawn at the chart's OWN column ----------
  function geometry(width, model) {
    const W = Math.max(240, Math.round(width)), narrow = W < 560;
    const left = narrow ? 34 : 42, right = narrow ? 10 : 16, top = 14;
    const axisBand = narrow ? 48 : 44, gap = 44;   // the dates on one row, the backtest bracket on its own
    const H = narrow ? 360 : 410;
    const n = model.sessions.length;
    const plotW = W - left - right, slot = plotW / n;
    const span = H - top - axisBand - gap;
    const aTop = top, aBottom = r1(top + span * 0.52);
    const bTop = aBottom + gap, bBottom = H - axisBand;
    const ratios = model.sessions.map((s) => s.ratio_10d).filter(isNum);
    const rLo = Math.min(0.5, Math.min.apply(null, ratios) - 0.1);
    const rHi = Math.max(model.thresholds.ratio_10d_yellow + 0.2, Math.max.apply(null, ratios) + 0.1);
    const outcomes = model.outcomes;      // every settled R of every night, the chosen stratum
    const oLo = comp(Math.min(-1, outcomes.length ? Math.min.apply(null, outcomes) : -1));
    const oHi = comp(Math.max(1, outcomes.length ? Math.max.apply(null, outcomes) : 1));
    const x = (i) => r1(left + (i + 0.5) * slot);
    const ya = (v) => r1(aBottom - (v - rLo) / (rHi - rLo) * (aBottom - aTop));
    const yb = (v) => r1(bBottom - (comp(v) - oLo) / (oHi - oLo) * (bBottom - bTop));
    const dateEvery = Math.max(1, Math.ceil((6 * CHAR + 10) / slot));
    // real multiples on the compressed axis, zero first, thinned so no two labels touch
    const ticksB = [];
    [0, 1, -1, 2, -2, 5, -5, 10, -10].forEach((t) => {
      if (comp(t) < oLo - 1e-9 || comp(t) > oHi + 1e-9) return;
      if (ticksB.every((k) => Math.abs(yb(k) - yb(t)) >= 12)) ticksB.push(t);
    });
    ticksB.sort((a, b) => a - b);
    return { W, H, narrow, left, right, top, axisBand, gap, n, slot, plotW, aTop, aBottom, bTop, bBottom,
             rLo, rHi, oLo, oHi, x, ya, yb, dateEvery, ticksB, axisY: H - axisBand + 14, bracketY: H - 4 };
  }

  // ---- the model the chart draws: the file, re-keyed, nothing added ------
  function modelOf(F, stratum) {
    const index = {};
    F.market.sessions.forEach((s, i) => { index[s.date] = i; });
    const nights = F.nights.map((nt) => Object.assign({}, nt, {
      i: index[nt.session],
      block: stratum === 'all' ? nt.all : nt.strata[stratum],
    }));
    const outcomes = [];
    nights.forEach((nt) => { outcomes.push.apply(outcomes, nt.block.r); });
    return { sessions: F.market.sessions, thresholds: F.market.thresholds, nights, outcomes, stratum,
             window: F.backtest.lookback_260.evaluated, index };
  }

  // ---- the SVG ------------------------------------------------------------
  function buildSvg(SC, F, model, width, ids) {
    const G = geometry(width, model);
    const rules = F.rules.breadth;
    const svg = SC.svg('svg', { 'class': 'ss-find__svg', viewBox: [0, 0, G.W, G.H].join(' '), width: G.W, height: G.H,
                                role: 'img', 'aria-labelledby': ids.title + ' ' + ids.desc });
    svg.appendChild(SC.svg('title', { id: ids.title }, 'The market the gate read, and what each night’s tickets did'));
    svg.appendChild(SC.svg('desc', { id: ids.desc }, 'Upper panel: the ' + plain(rules.ratio_long_sessions) + '-session ratio of stocks up ' +
      plain(rules.burst_pct) + '% to stocks down, every session from ' + words(model.sessions[0].date) + ' to ' +
      words(model.sessions[model.sessions.length - 1].date) + ', with the red line at ' + fixed(rules.red_ratio_10d, 1) +
      ' and the green line at ' + fixed(rules.yellow_ratio_10d, 1) + '. Lower panel: for every published night, the settled R of its ' +
      STRATUM_WORDS[model.stratum] + ' tickets on a compressed axis, and their mean. The tables under the chart carry every value.'));
    const bands = SC.svg('g', { 'class': 'ss-find__bands' });
    const under = SC.svg('g'), marks = SC.svg('g'), over = SC.svg('g'), axis = SC.svg('g', { 'class': 'ss-find__axis' });
    svg.appendChild(bands); svg.appendChild(under); svg.appendChild(marks); svg.appendChild(over); svg.appendChild(axis);
    const plotRight = G.left + G.plotW;
    // regime washes and the two reference lines of panel A
    const red = G.ya(model.thresholds.ratio_10d_red), yellow = G.ya(model.thresholds.ratio_10d_yellow);
    bands.appendChild(SC.svg('rect', { 'class': 'ss-find__wash', x: G.left, y: red, width: G.plotW, height: G.aBottom - red, style: tone('danger') }));
    bands.appendChild(SC.svg('rect', { 'class': 'ss-find__wash', x: G.left, y: yellow, width: G.plotW, height: red - yellow, style: tone('warn') }));
    bands.appendChild(SC.svg('rect', { 'class': 'ss-find__wash', x: G.left, y: G.aTop, width: G.plotW, height: Math.max(0, yellow - G.aTop), style: tone('good') }));
    // the two lines the regime rule draws, named at the right edge; a phone keeps the short names
    [[red, 'red', G.narrow ? 'red below ' + fixed(model.thresholds.ratio_10d_red, 1) : 'red, no new longs, below ' + fixed(model.thresholds.ratio_10d_red, 1)],
     [yellow, 'green', G.narrow ? 'green above ' + fixed(model.thresholds.ratio_10d_yellow, 1) : 'green, full size, above ' + fixed(model.thresholds.ratio_10d_yellow, 1)]].forEach(([y, kind, text]) => {
      under.appendChild(SC.svg('line', { 'class': 'ss-find__ref', x1: G.left, x2: plotRight, y1: y, y2: y, 'data-ref': kind }));
      axis.appendChild(SC.svg('text', { 'class': 'ss-find__ref-text', x: plotRight - 4, y: y - 4, 'text-anchor': 'end', 'data-ref-label': kind }, text));
    });
    if (!G.narrow) axis.appendChild(SC.svg('text', { 'class': 'ss-find__ref-text', x: plotRight - 4, y: r1((red + yellow) / 2) + 4, 'text-anchor': 'end', 'data-ref-label': 'yellow' },
      'yellow between: size × ' + plain(rules.size_multiplier.yellow) + ', ' + F.rules.pipeline.yellow_grades.join(' and ') + ' only'));
    // panel A: the ratio, one line, markers on the published nights
    const pts = model.sessions.map((s, i) => G.x(i) + ',' + G.ya(s.ratio_10d));
    under.appendChild(SC.svg('path', { 'class': 'ss-find__line', d: 'M' + pts.join('L'), style: tone('chart-emphasis') }));
    SC.ticks(G.rLo, G.rHi, G.narrow ? 3 : 4).ticks.forEach((t) => {
      if (t < G.rLo || t > G.rHi) return;
      const y = G.ya(t);
      under.appendChild(SC.svg('line', { 'class': 'ss-find__grid', x1: G.left, x2: plotRight, y1: y, y2: y }));
      axis.appendChild(SC.svg('text', { 'class': 'ss-find__tick', x: G.left - 6, y: y + 3.5, 'text-anchor': 'end' }, fixed(t, 1)));
    });
    axis.appendChild(SC.svg('text', { 'class': 'ss-find__panel', x: G.left, y: G.aTop - 4 }, plain(rules.ratio_long_sessions) + '-session ratio, up ' + plain(rules.burst_pct) + '% against down'));
    // panel B: zero line, ticks, the compressed outcome axis
    const zero = G.yb(0);
    under.appendChild(SC.svg('line', { 'class': 'ss-find__zero', x1: G.left, x2: plotRight, y1: zero, y2: zero }));
    G.ticksB.forEach((t) => {
      const y = G.yb(t);
      if (t !== 0) under.appendChild(SC.svg('line', { 'class': 'ss-find__grid', x1: G.left, x2: plotRight, y1: y, y2: y }));
      axis.appendChild(SC.svg('text', { 'class': 'ss-find__tick', x: G.left - 6, y: y + 3.5, 'text-anchor': 'end', 'data-r-tick': t }, (t > 0 ? '+' : t < 0 ? '−' : '') + Math.abs(t) + 'R'));
    });
    axis.appendChild(SC.svg('text', { 'class': 'ss-find__panel', x: G.left, y: G.bTop - 6 },
      'what the night’s ' + (model.stratum === 'all' ? 'tickets, every burst,' : STRATUM_WORDS[model.stratum] + ' tickets') + ' did: R per ticket, compressed axis'));
    if (model.nights.length && model.nights[0].i > 0) {
      axis.appendChild(SC.svg('text', { 'class': 'ss-find__note', x: G.left + 4, y: G.bTop + 12, 'data-note': 'before' },
        G.narrow ? 'no published scan yet' : 'no published scan before ' + short(model.nights[0].session)));
    }
    // the cursor: one band through both panels, moved with the step
    const cursor = SC.svg('g', { 'class': 'ss-find__cursor', 'data-cursor': '' });
    cursor.appendChild(SC.svg('rect', { x: 0, y: G.aTop, width: r1(G.slot), height: G.bBottom - G.aTop, style: tone('chart-emphasis') }));
    under.insertBefore(cursor, under.firstChild);
    // markers: every published night in A; every settled R and the mean in B
    const nightMarks = {};
    model.nights.forEach((nt, k) => {
      const cx = G.x(nt.i), cy = G.ya(nt.regime.ratio_10d);
      const g = SC.svg('g', { 'class': 'ss-find__night', 'data-night': nt.session, 'data-k': k });
      g.appendChild(SC.svg('circle', { 'class': 'ss-find__dot', cx, cy, r: 4.5, style: tone(VERDICT_TONE[nt.regime.verdict] || 'chart-context') }));
      const b = nt.block, rs = b.r;
      rs.forEach((v, j) => {
        const off = ((j * GOLDEN) % 1 - 0.5) * G.slot * 0.8;
        g.appendChild(SC.svg('circle', { 'class': 'ss-find__r', cx: r1(cx + off), cy: G.yb(v), r: G.narrow ? 1.8 : 2.4, style: tone('chart-context'), 'data-r': v }));
      });
      if (isNum(b.settled.mean_r)) {
        g.appendChild(SC.svg('circle', { 'class': 'ss-find__mean', cx, cy: G.yb(b.settled.mean_r), r: 4.5, style: tone('chart-emphasis'), 'data-mean': b.settled.mean_r }));
      } else {
        g.appendChild(SC.svg('circle', { 'class': 'ss-find__mean ss-find__mean--none', cx, cy: zero, r: 4.5, style: tone('chart-context'), 'data-mean': 'none' }));
      }
      marks.appendChild(g);
      nightMarks[nt.session] = g;
    });
    // the pill naming the current night's outcome, clamped inside panel B
    const pill = SC.svg('g', { 'class': 'ss-find__pill', 'data-pill': '' });
    const pillRect = SC.svg('rect', { rx: 4, ry: 4, height: 18 });
    const pillText = SC.svg('text', { 'class': 'ss-find__pill-text', 'text-anchor': 'middle' });
    pill.appendChild(pillRect); pill.appendChild(pillText); over.appendChild(pill);
    // dates along the floor, thinned to fit, and the backtest's own window
    model.sessions.forEach((s, i) => {
      if (i % G.dateEvery !== 0 && i !== model.sessions.length - 1) return;
      if (i !== model.sessions.length - 1 && (model.sessions.length - 1 - i) * G.slot < 5 * CHAR + 6) return;
      axis.appendChild(SC.svg('text', { 'class': 'ss-find__date', x: G.x(i), y: G.axisY, 'text-anchor': 'middle' }, short(s.date)));
    });
    const wFrom = model.index[model.window.from], wTo = model.index[model.window.through];
    if (isNum(wFrom) && isNum(wTo)) {
      const x1 = r1(G.x(wFrom) - G.slot / 2), x2 = r1(G.x(wTo) + G.slot / 2), y = G.bracketY;
      over.appendChild(SC.svg('path', { 'class': 'ss-find__bracket', d: 'M' + x1 + ',' + (y - 5) + 'V' + y + 'H' + x2 + 'V' + (y - 5), 'data-bracket': 'backtest' }));
      axis.appendChild(SC.svg('text', { 'class': 'ss-find__bracket-text', x: x1 + 4, y: y - 9, 'data-bracket-label': 'backtest' },
        'backtest window · ' + plural(model.window.count, 'session')));
    }
    // hit columns: one per session, over everything
    const hits = SC.svg('g', { 'class': 'ss-find__hits' });
    model.sessions.forEach((s, i) => {
      hits.appendChild(SC.svg('rect', { 'class': 'ss-find__hit', x: r1(G.x(i) - G.slot / 2), y: G.aTop, width: r1(G.slot), height: G.bBottom - G.aTop, 'data-hit': s.date, 'data-i': i }));
    });
    svg.appendChild(hits);
    function place(k) {
      const nt = model.nights[k];
      cursor.style.transform = 'translateX(' + r1(G.x(nt.i) - G.slot / 2) + 'px)';
      const text = isNum(nt.block.settled.mean_r)
        ? rr(nt.block.settled.mean_r) + ' · ' + num(nt.block.settled.n) + ' settled'
        : (nt.block.buckets.pending ? plural(nt.block.buckets.pending, 'ticket') + ' pending' : 'nothing settled');
      const width = text.length * 6.4 + 14;
      const cx = Math.min(plotRight - width / 2 - 2, Math.max(G.left + width / 2 + 2, G.x(nt.i)));
      const yPill = G.aBottom + 6;   // in the gap between the panels, never over a dot
      pillRect.setAttribute('x', r1(cx - width / 2)); pillRect.setAttribute('y', yPill); pillRect.setAttribute('width', r1(width));
      pillText.setAttribute('x', r1(cx)); pillText.setAttribute('y', yPill + 13); pillText.textContent = text;
      pill.setAttribute('data-pill', nt.session);
    }
    function reveal(k) {
      model.nights.forEach((nt, j) => {
        const g = nightMarks[nt.session];
        g.classList.toggle('is-ghost', j > k);
        g.classList.toggle('is-current', j === k);
      });
    }
    return { svg, G, place, reveal, hits, nightMarks };
  }

  // ---- captions: the night in words, every number the file's ---------------
  function factsOf(F, nt, stratum) {
    const rules = F.rules, b = stratum === 'all' ? nt.all : nt.strata[stratum];
    const reg = nt.regime, bk = b.buckets, st = b.settled;
    const hold = plain(rules.record.open_plan_sessions);
    const facts = [];
    facts.push({ chip: [reg.verdict, VERDICT_TONE[reg.verdict] || 'neutral'],
                 text: sizeWords(reg.size_multiplier) + ' · ' + num(reg.up4) + ' up ' + plain(rules.breadth.burst_pct) + '% against ' +
                       num(reg.down4) + ' down on the day · ' + num(reg.up4_10d) + ' against ' + num(reg.down4_10d) + ' over ' +
                       plain(rules.breadth.ratio_long_sessions) + ' sessions, ratio ' + fixed(reg.ratio_10d, 2) + '.' });
    let cf = (stratum === 'all' ? 'Had every burst been ticketed' : 'Had every ' + STRATUM_WORDS[stratum] + ' burst been ticketed') +
             ' at full size, reader not run: ' + plural(b.rows, 'ticket');
    if (st.n) {
      cf += '; ' + num(st.n) + ' settled after their ' + hold + '-session hold · ' + num(st.wins) + ' won, ' + num(st.losses) + ' lost, ' +
            num(st.breakeven) + ' even · ' + rr(st.sum_r) + ' in all, ' + rr(st.mean_r) + ' per ticket, median ' + rr(st.median_r);
    } else {
      cf += '; none settled yet';
    }
    const rest = [];
    if (bk.uncertain) rest.push(num(bk.uncertain) + ' uncertain on daily bars');
    if (bk.not_filled) rest.push(num(bk.not_filled) + ' not filled');
    if (bk.open) rest.push(num(bk.open) + ' still open');
    if (bk.pending) rest.push(num(bk.pending) + ' pending');
    if (bk.no_ticket) rest.push(num(bk.no_ticket) + ' with no ticket the rules would write');
    if (bk.basis_mismatch) rest.push(num(bk.basis_mismatch) + ' set aside, the night’s own bars being in no later history');
    if (bk.unmeasured) rest.push(num(bk.unmeasured) + ' unmeasured');
    facts.push(cf + (rest.length ? ' · ' + rest.join(', ') : '') + '.');
    const fr = nt.first_read && (stratum === 'admitted' ? nt.first_read.admitted : stratum === 'all' ? nt.first_read.all : null);
    if (fr && fr.n) {
      facts.push('Read on ' + short(nt.first_read.as_of) + ', before every ticket had its ' + hold + ' sessions: ' + rr(fr.mean_r) + ' per ticket over ' +
                 plural(fr.n, 'settled ticket') + '; read now, ' + rr(st.mean_r) + ' over ' + num(st.n) + '.');
    }
    if (!nt.complete) facts.push('The ' + hold + '-session hold runs through ' + words(nt.horizon) + '; nothing here is final before then.');
    return facts;
  }

  function textOf(F, nt) {
    const gm = nt.grades_mechanical, gf = nt.grades_final;
    const a = (g) => (g['A+'] || 0) + (g.A || 0);
    const reg = nt.regime;
    return 'The scan found ' + plural(nt.bursts, 'burst') + '. The checklist graded ' + num(a(gm)) + ' of them A-quality and vetoed ' +
      num(nt.vetoed) + '; after the chart reader ' + num(a(gf)) + ' stayed A-quality. The market gate said ' + reg.verdict + ': ' +
      sentence(reg.reasons) + ' It published ' + plural(nt.tickets_published, 'ticket') + '.';
  }

  // ---- the table twins -----------------------------------------------------
  function twins(SC, host, F, model) {
    const nights = SC.tableTwin(host, {
      caption: 'Every published night: the market, the scan and the counterfactual tickets of the ' + STRATUM_WORDS[model.stratum] + ' stratum',
      summary: 'Nights as a table',
      head: ['night', 'verdict', 'ratio', 'bursts', 'A-quality', 'tickets published', 'counterfactual tickets', 'settled', 'won', 'lost', 'even', 'sum R', 'mean R', 'uncertain', 'not filled', 'open or pending'],
      rows: model.nights.map((nt) => {
        const b = nt.block, s = b.settled, g = nt.grades_mechanical;
        return [words(nt.session), nt.regime.verdict, fixed(nt.regime.ratio_10d, 2), num(nt.bursts), num((g['A+'] || 0) + (g.A || 0)), num(nt.tickets_published),
                num(b.rows), num(s.n), num(s.wins), num(s.losses), num(s.breakeven), signed(s.sum_r, 2), signed(s.mean_r, 3), num(b.buckets.uncertain), num(b.buckets.not_filled),
                num((b.buckets.open || 0) + (b.buckets.pending || 0))];
      }),
    });
    const nd = nights.closest('details'); if (nd) nd.setAttribute('data-find', 'table-nights');
    const market = SC.tableTwin(host, {
      caption: 'Every session the records know: the counts and the ratio the gate read, oldest first',
      summary: 'Market sessions as a table',
      head: ['session', 'up', 'down', 'ratio', 'verdict', 'read from'],
      rows: model.sessions.map((s) => [words(s.date), num(s.up4), num(s.down4), fixed(s.ratio_10d, 2), s.verdict || 'no publication',
        (s.basis === 'publication' ? 'its own publication ' + s.source : 'the history of ' + s.source) + (isNum(s.later_ratio_10d) ? ' (a later history reads ' + fixed(s.later_ratio_10d, 2) + ')' : '')]),
    });
    const md = market.closest('details'); if (md) md.setAttribute('data-find', 'table-market');
  }

  // ---- mount ---------------------------------------------------------------
  function mount(host, F, opts) {
    const SC = w.SC;
    opts = opts || {};
    if (!host || !SC || !SC.svg || !F || F.version !== VERSION) return null;
    const id = ++mounted;
    const ids = { title: 'ss-find-title-' + id, desc: 'ss-find-desc-' + id, caption: 'ss-find-caption-' + id, filter: 'ss-find-filter-' + id };
    const interval = Math.max(200, Number(opts.interval) || INTERVAL);
    const reduced = () => !!(w.matchMedia && w.matchMedia('(prefers-reduced-motion: reduce)').matches);
    let stratum = STRATA.indexOf(opts.stratum) >= 0 ? opts.stratum : 'admitted';
    let model = modelOf(F, stratum);
    let step = 0, timer = null, view = null, drawnWidth = 0, tip = null;
    const el = SC.el;
    const hold = plain(F.rules.record.open_plan_sessions);

    // the stratum control: one captioned group, above everything it scopes
    const tabs = el('div', { 'class': 'sc-tabs', role: 'group', 'aria-labelledby': ids.filter });
    STRATA.forEach((s) => {
      tabs.appendChild(el('button', { type: 'button', 'class': 'sc-tab', 'data-find-stratum': s, 'aria-pressed': s === stratum ? 'true' : 'false',
        text: STRATUM_WORDS[s], onclick: () => setStratum(s) }));
    });
    const filter = el('div', { 'class': 'sc-field sc-field--group ss-find__filter' }, [el('span', { 'class': 'sc-field__label', id: ids.filter, text: 'tickets' }), tabs]);

    const chart = el('div', { 'class': 'ss-find__chart' });
    const back = el('button', { type: 'button', 'class': 'sc-btn sc-btn--secondary sc-btn--sm', 'data-find': 'back', text: 'Back', 'aria-label': 'Previous night' });
    const play = el('button', { type: 'button', 'class': 'sc-btn sc-btn--secondary sc-btn--sm', 'data-find': 'play', text: 'Play', 'aria-pressed': 'false' });
    const next = el('button', { type: 'button', 'class': 'sc-btn sc-btn--secondary sc-btn--sm', 'data-find': 'next', text: 'Next', 'aria-label': 'Next night' });
    const count = el('span', { 'class': 'ss-find__count', 'data-find': 'count', 'aria-live': 'polite' });
    const controls = el('div', { 'class': 'ss-find__controls' }, [back, play, next, count]);
    const stage = el('div', { 'class': 'ss-find__stage', tabindex: 0, role: 'group', 'aria-roledescription': 'animated replay',
      'aria-label': 'The record night by night. Arrow keys move between nights, Home and End jump to the first and last, Space plays and pauses.',
      'aria-describedby': ids.caption }, [chart, controls]);
    const index = el('ol', { 'class': 'ss-find__index', 'aria-label': 'Nights' });
    model.nights.forEach((nt, k) => {
      index.appendChild(el('li', null, el('button', { type: 'button', 'class': 'sc-tab sc-tab--case', 'data-find-night': nt.session, 'aria-current': 'false',
        onclick: () => { stopPlay(); go(k); } }, [el('span', { 'class': 'ss-find__n', text: String(k + 1) }), el('span', { text: short(nt.session) + ' · ' + nt.regime.verdict })])));
    });
    const side = el('div', { 'class': 'ss-find__side' }, index);
    const eyebrow = el('p', { 'class': 'sc-eyebrow', 'data-find': 'eyebrow' });
    const title = el('h4', { 'data-find': 'title' });
    const text = el('p', { 'data-find': 'text' });
    const facts = el('ul', { 'class': 'ss-find__facts', 'data-find': 'facts' });
    const who = el('p', { 'class': 'sc-note ss-find__who', 'data-find': 'who' });
    const caption = el('div', { 'class': 'ss-find__caption', id: ids.caption, 'aria-live': 'polite' }, [eyebrow, title, text, facts, who]);
    const ns = F.nights_summary, verdicts = ['red', 'yellow', 'green'].filter((v) => ns.verdicts[v]).map((v) => num(ns.verdicts[v]) + ' ' + v);
    host.appendChild(el('p', { 'class': 'sc-note', 'data-find': 'lead', text: 'Over the ' + plural(ns.nights, 'published night') + ' from ' + words(ns.from) + ' to ' + words(ns.through) +
      ' the gate said ' + verdicts.join(', ') + ' and published ' + plural(ns.tickets_published, 'ticket') + ' out of ' + plural(ns.bursts, 'burst') + ' scanned. ' +
      'The study ticketed every burst anyway, reader not run, to see what the refusals were worth; step through the nights, or press Play.' }));
    const root = el('div', { 'class': 'ss-find', 'data-find-root': '', 'data-stratum': stratum }, [filter, stage, side, caption]);
    host.appendChild(root);
    const tables = el('div', { 'class': 'ss-find__tables', 'data-find': 'tables' });
    host.appendChild(tables);

    function paint(animate) {
      const nt = model.nights[step];
      if (view) { view.reveal(step); view.place(step); }
      index.querySelectorAll('[data-find-night]').forEach((b) => b.setAttribute('aria-current', b.getAttribute('data-find-night') === nt.session ? 'step' : 'false'));
      eyebrow.textContent = 'night ' + (step + 1) + ' of ' + model.nights.length + ' · ' + nt.phase + ' · ' +
        (nt.complete ? hold + ' sessions complete' : 'inside its hold');
      title.textContent = words(nt.session) + ' · ' + nt.regime.verdict + ' · ratio ' + fixed(nt.regime.ratio_10d, 2);
      text.textContent = textOf(F, nt);
      facts.textContent = '';
      factsOf(F, nt, stratum).forEach((f) => {
        if (typeof f === 'string') facts.appendChild(el('li', { text: f }));
        else facts.appendChild(el('li', null, [el('span', { 'class': 'sc-chip sc-chip--' + f.chip[1], text: f.chip[0] }), ' ' + f.text]));
      });
      who.textContent = 'Source: publication ' + nt.commit.slice(0, 8) + ' (' + nt.status + '); the study’s rows over the records’ own bars.';
      count.textContent = 'Night ' + (step + 1) + ' of ' + model.nights.length;
      back.setAttribute('aria-disabled', step === 0 ? 'true' : 'false');
      next.setAttribute('aria-disabled', step === model.nights.length - 1 ? 'true' : 'false');
      root.setAttribute('data-night', nt.session);
      root.setAttribute('data-step', String(step + 1));
      root.classList.toggle('is-animated', !!animate && !reduced());
    }
    function go(n, animate) {
      step = Math.max(0, Math.min(model.nights.length - 1, n));
      paint(animate !== false);
      if (step === model.nights.length - 1) stopPlay();
    }
    function startPlay() {
      if (timer) return;
      if (step === model.nights.length - 1) go(0);
      timer = w.setInterval(() => go(step + 1), interval);
      play.textContent = 'Pause'; play.setAttribute('aria-pressed', 'true');
    }
    function stopPlay() {
      if (timer) w.clearInterval(timer);
      timer = null;
      play.textContent = 'Play'; play.setAttribute('aria-pressed', 'false');
    }
    play.addEventListener('click', () => { if (timer) stopPlay(); else startPlay(); });
    next.addEventListener('click', () => { stopPlay(); go(step + 1); });
    back.addEventListener('click', () => { stopPlay(); go(step - 1); });
    stage.addEventListener('keydown', (e) => {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      const keys = { ArrowRight: step + 1, ArrowLeft: step - 1, Home: 0, End: model.nights.length - 1 };
      if (e.key in keys) { e.preventDefault(); stopPlay(); go(keys[e.key]); return; }
      if (e.key === ' ' && e.target === e.currentTarget) { e.preventDefault(); if (timer) stopPlay(); else startPlay(); }
    });
    w.document.addEventListener('visibilitychange', () => { if (w.document.hidden) stopPlay(); });

    function setStratum(s) {
      if (STRATA.indexOf(s) < 0 || s === stratum) return;
      stratum = s;
      model = modelOf(F, stratum);
      root.setAttribute('data-stratum', stratum);
      tabs.querySelectorAll('[data-find-stratum]').forEach((b) => b.setAttribute('aria-pressed', b.getAttribute('data-find-stratum') === stratum ? 'true' : 'false'));
      drawnWidth = 0;
      draw();
      retable();
    }
    function retable() {
      tables.textContent = '';
      twins(SC, tables, F, model);
    }
    function tooltipFor(i) {
      const s = model.sessions[i];
      const rows = [{ value: fixed(s.ratio_10d, 2), label: 'ratio' }, { value: num(s.up4) + ' / ' + num(s.down4), label: 'up / down' }];
      const nt = model.nights.find((x) => x.i === i);
      let meta = s.verdict ? 'verdict ' + s.verdict : 'no publication; from the history of ' + s.source;
      if (nt) {
        const b = nt.block;
        rows.push({ value: num(b.rows), label: STRATUM_WORDS[stratum] + ' tickets' });
        rows.push({ value: isNum(b.settled.mean_r) ? rr(b.settled.mean_r) : '—', label: 'mean R, ' + plural(b.settled.n, 'settled') });
        meta += ' · ' + plural(nt.bursts, 'burst');
      }
      return { title: words(s.date), rows, meta };
    }
    function draw() {
      const width = chart.clientWidth;
      if (!width) return;
      if (view && Math.abs(width - drawnWidth) <= 1) return;
      drawnWidth = width;
      chart.textContent = '';
      if (tip) { tip.destroy(); tip = null; }
      view = buildSvg(SC, F, model, width, ids);
      chart.appendChild(view.svg);
      if (SC.tooltip) {
        tip = SC.tooltip(chart, { live: true, top: 6, flip: 0.55, offsetX: 14 });
        view.hits.addEventListener('pointermove', (e) => {
          const hit = e.target && e.target.getAttribute && e.target.getAttribute('data-i');
          if (hit === null || hit === undefined) return;
          tip.show(tooltipFor(Number(hit)), e);
        });
        view.hits.addEventListener('pointerleave', () => tip.hide());
        view.hits.addEventListener('click', (e) => {
          const hit = e.target && e.target.getAttribute && e.target.getAttribute('data-i');
          if (hit === null || hit === undefined) return;
          const k = model.nights.findIndex((x) => x.i === Number(hit));
          if (k >= 0) { stopPlay(); go(k); }
        });
      }
      paint(false);
    }
    let raf = 0;
    const redraw = () => { if (raf) return; raf = w.requestAnimationFrame(() => { raf = 0; draw(); }); };
    if (w.ResizeObserver) new w.ResizeObserver(redraw).observe(chart); else w.addEventListener('resize', redraw);
    draw();
    retable();
    paint(false);
    const handle = { go: (n) => go(n, false), step: () => step, play: startPlay, pause: stopPlay, playing: () => !!timer, root,
                     stratum: () => stratum, setStratum, redraw: () => { drawnWidth = 0; draw(); } };
    S.findingsHandle = handle;
    return handle;
  }

  // ---- the blocks under the replay: the backtest, run 6, the reports ------
  function stat(el, label, value, note, lead) {
    return el('div', { 'class': 'sc-stat' + (lead ? ' sc-stat--lead' : '') }, [
      el('dt', { 'class': 'sc-stat__label', text: label }), el('dd', { 'class': 'sc-stat__value', text: value }),
      note ? el('dd', { 'class': 'sc-stat__note', text: note }) : null]);
  }
  function bars(el, rows, slot) {
    const max = Math.max.apply(null, rows.map((r) => r[1]).concat([1]));
    return el('div', { 'class': 'sc-bars' }, rows.map((r) => el('div', { 'class': 'sc-bars__row' }, [
      el('span', { 'class': 'sc-bars__label', text: r[0] }),
      el('div', { 'class': 'sc-bars__measure' }, [
        el('span', { 'class': 'sc-bars__track' }, el('span', { 'class': 'sc-bars__fill', style: '--sc-bar-size:' + (100 * r[1] / max).toFixed(1) + '%;' + tone(r[2] || slot) })),
        el('span', { 'class': 'sc-bars__value', text: num(r[1]) })])])));
  }
  function gateRows(g) {
    const s = g.settled, p = g.plans;
    return [num(g.tickets), num(s.n), num(s.wins) + ' / ' + num(s.losses) + ' / ' + num(s.breakeven), signed(s.sum_r, 2),
            s.readable ? signed(s.avg_r, 2) : '—', s.readable ? signed(s.median_r, 2) : '—', s.readable ? share(s.win_rate) : '—',
            num(p.uncertain), num(p.not_filled), s.readable ? pct1(s.spy_avg_pct) : '—'];
  }
  function renderBacktest(host, F) {
    const SC = w.SC, el = SC.el;
    const L = F.backtest.lookback_130, X = F.backtest.lookback_260;
    const prod = L.gates.production, cf = L.gates.no_regime_gate;
    const sec = el('section', { 'class': 'ss-find__block', 'data-find-block': 'backtest', 'aria-labelledby': 'ss-find-backtest-h' });
    sec.appendChild(el('p', { 'class': 'sc-eyebrow', text: 'owner-run backtest · recorded as pasted · reader not run' }));
    sec.appendChild(el('h3', { id: 'ss-find-backtest-h', text: 'The policy over ' + plural(L.evaluated.count, 'session') + ' of the archive' }));
    sec.appendChild(el('p', { text: 'The same nightly decision replayed over the bars of the acquisition archive, session by session, from ' + words(L.evaluated.from) +
      ' to ' + words(L.evaluated.through) + ', on the owner’s computer. The chart reader was not run, so every ticket here is one it could still have refused; ' +
      'the market was never green in the window, so the full-size state has never been exercised on real bars.' }));
    const v = L.regimes.verdicts;
    const strip = el('dl', { 'class': 'sc-stat-strip sc-stat-strip--4 sc-stat-strip--instrument ss-find__stats', 'data-find': 'backtest-strip' }, [
      stat(el, 'sessions', num(L.evaluated.count), short(L.evaluated.from) + ' to ' + short(L.evaluated.through)),
      stat(el, 'nights by regime', num(v.yellow || 0) + ' yellow · ' + num(v.red || 0) + ' red', num(v.green || 0) + ' green'),
      stat(el, 'tickets', num(prod.tickets), F.rules.pipeline.yellow_grades.join(' and ') + ' only, size × ' + plain(F.rules.breadth.size_multiplier.yellow)),
      stat(el, 'net result', rr(prod.settled.sum_r), plural(prod.settled.n, 'settled ticket') + ' · ' + num(prod.settled.wins) + ' won, ' + num(prod.settled.losses) + ' lost', true),
    ]);
    sec.appendChild(strip);
    const s = prod.settled;
    sec.appendChild(el('p', { 'class': 'sc-note', 'data-find': 'backtest-rates', text: 'Win rate ' + share(s.win_rate) + ' · mean ' + rr(s.avg_r) + ' · median ' + rr(s.median_r) +
      ' · ' + num(prod.plans.uncertain) + ' uncertain on daily bars · ' + num(prod.plans.not_filled) + ' not filled · SPY ' + pct1(s.spy_avg_pct) + ' over ' + plural(s.spy_pairs, 'matched pair') +
      ' · ' + plural(L.candidates.bursts, 'burst') + ' scanned · rules ' + L.rules_version + ' · lookback equivalence ' + L.lookback.equivalence.status + ' over ' +
      plural(L.lookback.equivalence.compared, 'shared session') + ' with ' + plural(L.lookback.equivalence.differences, 'difference') + '.' }));
    sec.appendChild(bars(el, [['yellow nights', v.yellow || 0, 'warn'], ['red nights', v.red || 0, 'danger'], ['green nights', v.green || 0, 'good']], 'chart-context'));
    sec.appendChild(bars(el, [['won', s.wins], ['lost', s.losses], ['even', s.breakeven]], 'chart-emphasis'));
    const head = ['policy', 'tickets', 'settled', 'won / lost / even', 'sum R', 'mean R', 'median R', 'win rate', 'uncertain', 'not filled', 'SPY'];
    const rows = [['production: the gate as published'].concat(gateRows(prod)), ['counterfactual: gate removed (not a policy)'].concat(gateRows(cf))];
    Object.keys(cf.by_regime).sort().forEach((k) => {
      const b = cf.by_regime[k];
      rows.push([' counterfactual on ' + k + ' nights', num(b.plans), num(b.settled), num(b.wins) + ' / ' + num(b.losses) + ' / ' + num(b.settled - b.wins - b.losses), signed(b.sum_r, 2), '—', '—', '—', '—', '—', '—']);
    });
    Object.keys(cf.by_grade).sort().forEach((k) => {
      const b = cf.by_grade[k];
      rows.push([' counterfactual, grade ' + k, num(b.plans), num(b.settled), num(b.wins) + ' / ' + num(b.losses) + ' / ' + num(b.settled - b.wins - b.losses), signed(b.sum_r, 2), '—', '—', '—', '—', '—', '—']);
    });
    rows.push(['exact lookback, ' + plural(X.evaluated.count, 'session') + ' from ' + short(X.evaluated.from) + ': production'].concat(gateRows(X.gates.production)));
    rows.push(['exact lookback: counterfactual'].concat(gateRows(X.gates.no_regime_gate)));
    const scroll = el('div', { 'class': 'sc-table-scroll', 'data-find': 'backtest-table', tabindex: 0, role: 'region', 'aria-label': 'Backtest as a table' });
    SC.tableTwin(scroll, { caption: 'The backtest’s two blocks and the exact-lookback pass, as pasted', head, rows, details: false });
    sec.appendChild(scroll);
    sec.appendChild(el('p', { 'class': 'sc-hint', 'data-find': 'backtest-source', text: 'Rates print only where the pasted summary read them (' + plain(prod.settled.min_read) +
      ' settled or more); a dash is a number the summary did not carry. Two summaries, SHA-256 ' + L.source.sha256.slice(0, 12) + ' and ' + X.source.sha256.slice(0, 12) +
      ', parsed by the backtest tool’s own grammar; the per-ticket files stay on the owner’s machine.' }));
    host.appendChild(sec);
  }
  function renderRun6(host, F) {
    const SC = w.SC, el = SC.el, R = F.run6;
    const sec = el('section', { 'class': 'ss-find__block', 'data-find-block': 'run6', 'aria-labelledby': 'ss-find-run6-h' });
    sec.appendChild(el('p', { 'class': 'sc-eyebrow', text: 'run ' + num(R.public.run_number) + ' · fresh bars for every intended stock · owner-read' }));
    sec.appendChild(el('h3', { id: 'ss-find-run6-h', text: 'The red reading, checked on fresh bars' }));
    sec.appendChild(el('p', { text: 'A later retrieval of the bars for every stock the record intended, recomputing the gate’s own ratio for ' +
      Object.keys(R.sessions).map(words).join(' and ') + '. The verdict the gate published is compared with the one an independent calculator reads off the fresh bars.' }));
    const head = ['session', 'published ratio', 'fresh ratio', 'up / down over ten', 'could be anywhere in', 'counted', 'verdict', 'rules that fired'];
    const rows = Object.keys(R.sessions).sort().map((day) => {
      const s = R.sessions[day], c = s.policies.C, o = s.original;
      return [words(day), fixed(o.ratio_10d, 2) + ' (' + num(o.up4_10d) + ' / ' + num(o.down4_10d) + ')', fixed(c.ratio_10d, 2), num(c.up4_10d) + ' / ' + num(c.down4_10d),
              fixed(c.ratio_10d_bounds[0], 2) + ' to ' + fixed(c.ratio_10d_bounds[1], 2) + ' over ' + plural(c.unknown_contributors, 'unknown'),
              num(o.universe) + ' published, ' + num(c.counted_universe) + ' fresh', o.verdict + ' published, ' + c.independent_verdict + ' fresh', c.rules_fired.map(underscores).join(', ')];
    });
    const scroll = el('div', { 'class': 'sc-table-scroll', 'data-find': 'run6-table', tabindex: 0, role: 'region', 'aria-label': 'Run ' + num(R.public.run_number) + ' as a table' });
    SC.tableTwin(scroll, { caption: 'The published and the freshly retrieved breadth reading, by session', head, rows, details: false });
    sec.appendChild(scroll);
    const first = R.sessions[Object.keys(R.sessions).sort()[0]];
    sec.appendChild(el('p', { 'class': 'sc-note', 'data-find': 'run6-facts', text: num(R.download.queries_completed) + ' of ' + num(R.download.queries_total) + ' queries completed; ' +
      num(first.partial) + ' symbols per session returned a partial window, no cause assigned; strict establishment stays blocked by ' + plural(R.blocking_names.length, 'counted stock') +
      ' (' + R.blocking_names.join(', ') + ') whose month-long history the fresh bars do not reach. Artifact ' + String(R.public.artifact.id) + ', ' + num(R.public.artifact.size_in_bytes) +
      ' bytes, recovered and read on the owner’s machine; the summary’s SHA-256 is ' + R.source.sha256.slice(0, 12) + '.' }));
    host.appendChild(sec);
  }
  function renderReading(host, F) {
    const SC = w.SC, el = SC.el;
    const sec = el('section', { 'class': 'ss-find__block', 'data-find-block': 'reading', 'aria-labelledby': 'ss-find-reading-h' });
    sec.appendChild(el('h3', { id: 'ss-find-reading-h', text: 'Read it as' }));
    const strata = F.study.summary.strata;
    const pooled = ['admitted', 'B', 'C', 'skip', 'vetoed'].map((s) => STRATUM_WORDS[s] + ' ' + rr(strata[s].settled.mean_r) + ' over ' + num(strata[s].settled.n)).join('; ');
    const items = [
      'Pooled over the red nights to ' + words(F.study.newest_session) + ', the mean R per settled counterfactual ticket by stratum: ' + pooled +
        '. Where every stratum is under zero, the refusals had value in sum; single nights above can still be positive, and a reading of what green or yellow nights would do is not in this record, which has never carried one.',
      'A night read before its tickets have had their hold leans toward losses, because a stop settles on its first bad day and a winner at its exit; the nights above are re-read as they complete, and the caption says when a night is still inside its hold.',
      'The chart reader is not run in either study; the mechanical grade is the ceiling of what it could have admitted, so the live policy would have written fewer tickets than any counterfactual here.',
      'The study is exploratory where every next close was public before its spec was frozen, confirmatory only for nights published after it; nothing confirmatory is readable before its own minimum of settled tickets.',
    ].concat(F.read_as || []);
    sec.appendChild(el('ul', { 'class': 'ss-find__reading', 'data-find': 'read-as' }, items.map((t) => el('li', { text: t }))));
    sec.appendChild(el('p', { 'class': 'sc-hint', text: 'The reports behind these numbers, served as the Markdown files they are:' }));
    sec.appendChild(el('ul', { 'class': 'ss-find__reports', 'data-find': 'reports' }, F.reports.map((r) => el('li', null, el('a', { 'class': 'sc-link--quiet', href: r.path.replace(/^docs\//, ''), text: r.title })))));
    host.appendChild(sec);
  }

  S.findings = { VERSION, INTERVAL, STRATA, STRATUM_WORDS, geometry, modelOf, factsOf, textOf, mount, renderBacktest, renderRun6, renderReading };
})(window);
