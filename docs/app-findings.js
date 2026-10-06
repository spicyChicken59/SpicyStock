/* docs/app-findings.js -- the record, night by night.

   SCStock.findings mounts the historical-findings replay: the market the
   gate read on every session the records know, the scan's bursts on every
   published night, and what the counterfactual tickets of that night did
   over their hold, stepped one night at a time the way the Method
   walkthrough steps one burst. It reads no record, no clock and no
   storage: app.js hands it the committed docs/historical-findings.json,
   which tools/build_historical_findings.py built from the evidence files
   and tests/test_historical_findings.py holds to them. Every number this
   module prints is a field of that file, at the precision the file carries
   it; the only arithmetic here is drawing (a value to a pixel) and the
   distance of a press from a mark, never a figure the file does not carry.

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
  const VERDICTS = ['red', 'yellow', 'green'];
  const VERDICT_TONE = { green: 'good', yellow: 'warn', red: 'danger' };
  const CHAR = 6.5;         // px per glyph of the 10.5px mono the chart text wears
  const GOLDEN = 0.6180339887;
  const TAP_RADIUS = 22;    // half the 44px finger the sheet's touch targets are sized for
  const REPORT_PATH = /^docs\/input-truthfulness\/[\w.-]+\.md$/;
  let mounted = 0;

  // ---- words for numbers: every one a field of the file, at its precision --
  const isNum = (v) => typeof v === 'number' && isFinite(v);
  const thousands = (s) => String(s).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  const num = (v) => isNum(v) ? thousands(v) : '—';
  const fixed = (v, d) => isNum(v) ? v.toFixed(d) : '—';
  const sign = (v) => v > 0 ? '+' : v < 0 ? '−' : '';
  const signed = (v, d) => isNum(v) ? sign(v) + Math.abs(v).toFixed(d) : '—';
  // the study writes a sum and a median at two places and a mean at three, each rounded once;
  // the pasted backtest summary prints everything at two. The page prints each as written.
  const R2 = (v) => isNum(v) ? signed(v, 2) + 'R' : '—';
  const R3 = (v) => isNum(v) ? signed(v, 3) + 'R' : '—';
  const pct2 = (v) => isNum(v) ? signed(v, 2) + '%' : '—';
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
  const verdictCount = (v) => VERDICTS.filter((k) => v[k]).map((k) => num(v[k]) + ' ' + k).join(', ');
  const stratumOf = (nt, s) => s === 'all' ? nt.all : nt.strata[s];

  // ---- the shape the module indexes into, checked before anything is drawn --
  // A file of another shape is refused with a sentence one level in, never a
  // half-drawn replay or an engine's message (CLAUDE.md: a structure read off
  // disk is checked where it is first read).
  function shapeProblem(F) {
    const obj = (v) => v && typeof v === 'object' && !Array.isArray(v);
    const str = (v) => typeof v === 'string' && v.length > 0;
    const nums = (o, keys) => obj(o) && keys.every((k) => isNum(o[k]));
    const settled = (b) => obj(b) && obj(b.settled) && obj(b.buckets) && Array.isArray(b.r) && b.r.every(isNum) && isNum(b.rows) && isNum(b.tickets);
    if (!obj(F) || F.version !== VERSION) return 'Unknown findings version.';
    if (!obj(F.rules) || !nums(F.rules.breadth, ['ratio_long_sessions', 'burst_pct']) || !obj(F.rules.breadth.size_multiplier) ||
        !nums(F.rules.record, ['open_plan_sessions']) || !obj(F.rules.pipeline) || !Array.isArray(F.rules.pipeline.yellow_grades)) return 'The findings carry no rules.';
    if (!obj(F.market) || !Array.isArray(F.market.sessions) || !F.market.sessions.length || !nums(F.market.thresholds, ['ratio_10d_red', 'ratio_10d_yellow']) ||
        F.market.sessions.some((s) => !obj(s) || !str(s.date) || !(isNum(s.ratio_10d) || s.ratio_10d === null))) return 'The findings carry no market.';
    if (!Array.isArray(F.nights) || !F.nights.length) return 'The findings carry no nights.';
    const dates = {};
    F.market.sessions.forEach((s) => { dates[s.date] = true; });
    for (const nt of F.nights) {
      if (!obj(nt) || !dates[nt.session] || !obj(nt.regime) || !str(nt.regime.verdict) || !Array.isArray(nt.regime.reasons) ||
          !obj(nt.reads) || !nums(nt.a_quality, ['mechanical', 'final']) || !settled(nt.all) || !str(nt.commit) || !str(nt.phase) || !str(nt.status) ||
          ['bursts', 'vetoed', 'tickets_published'].some((k) => !isNum(nt[k]))) return 'A night of the findings is malformed.';
      if (!obj(nt.strata) || STRATA.slice(0, -1).some((s) => !settled(nt.strata[s]))) return 'A night of the findings has a malformed stratum.';
    }
    if (!nums(F.nights_summary, ['nights', 'tickets_published', 'bursts', 'admitted_positive_nights', 'inside_hold']) || !obj(F.nights_summary.verdicts)) return 'The findings carry no night summary.';
    const bt = F.backtest || {};
    for (const k of ['lookback_130', 'lookback_260']) {
      const b = bt[k];
      if (!obj(b) || !obj(b.gates) || !obj(b.gates.production) || !obj(b.gates.no_regime_gate) || !nums(b.evaluated, ['count']) || !obj(b.regimes) ||
          !obj(b.regimes.verdicts) || !obj(b.candidates) || !obj(b.lookback) || !obj(b.lookback.equivalence) || !obj(b.source) || !Array.isArray(b.limitations)) return 'The findings carry no backtest.';
    }
    const R = F.run6;
    if (!obj(R) || !obj(R.sessions) || !obj(R.download) || !Array.isArray(R.blocking_names) || !obj(R.public) || !obj(R.public.artifact) || !obj(R.source) ||
        Object.keys(R.sessions).some((d) => !obj(R.sessions[d].original) || !obj(R.sessions[d].policies) || !obj(R.sessions[d].policies.C) ||
          !Array.isArray(R.sessions[d].policies.C.ratio_10d_bounds) || !Array.isArray(R.sessions[d].policies.C.rules_fired))) return 'The findings carry no fresh-bar reading.';
    if (!obj(F.study) || !obj(F.study.summary) || !obj(F.study.summary.strata) || STRATA.slice(0, -1).some((s) => !obj((F.study.summary.strata[s] || {}).settled))) return 'The findings carry no study summary.';
    if (!Array.isArray(F.reports)) return 'The findings carry no reports.';
    return null;
  }

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
    const rLo = Math.min(0.5, (ratios.length ? Math.min.apply(null, ratios) : 1) - 0.1);
    const rHi = Math.max(model.thresholds.ratio_10d_yellow + 0.2, (ratios.length ? Math.max.apply(null, ratios) : 1) + 0.1);
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
             rLo, rHi, oLo, oHi, x, ya, yb, dateEvery, ticksB, axisY: H - axisBand + 14, bracketY: H - 4,
             dot: narrow ? 2.2 : 3 };
  }

  // ---- the model the chart draws: the file, re-keyed, nothing added ------
  function modelOf(F, stratum) {
    const index = {};
    F.market.sessions.forEach((s, i) => { index[s.date] = i; });
    const nights = F.nights.map((nt) => Object.assign({}, nt, { i: index[nt.session], block: stratumOf(nt, stratum) }));
    const outcomes = [];
    nights.forEach((nt) => { outcomes.push.apply(outcomes, nt.block.r); });
    return { sessions: F.market.sessions, thresholds: F.market.thresholds, nights, outcomes, stratum,
             window: F.backtest.lookback_260.evaluated, index };
  }

  // ---- the SVG ------------------------------------------------------------
  function buildSvg(SC, F, model, width, ids) {
    const G = geometry(width, model);
    const rules = F.rules.breadth, th = model.thresholds;
    const svg = SC.svg('svg', { 'class': 'ss-find__svg', viewBox: [0, 0, G.W, G.H].join(' '), width: G.W, height: G.H,
                                role: 'img', 'aria-labelledby': ids.title + ' ' + ids.desc });
    svg.appendChild(SC.svg('title', { id: ids.title }, 'The market the gate read, and what each night’s tickets did'));
    svg.appendChild(SC.svg('desc', { id: ids.desc }, 'Upper panel: the ' + plain(rules.ratio_long_sessions) + '-session ratio of stocks up ' +
      plain(rules.burst_pct) + '% to stocks down, every session from ' + words(model.sessions[0].date) + ' to ' +
      words(model.sessions[model.sessions.length - 1].date) + ', with dashed lines where the ratio rule changes its verdict, ' +
      fixed(th.ratio_10d_red, 1) + ' and ' + fixed(th.ratio_10d_yellow, 1) + '. Lower panel: for every published night, the settled R of its ' +
      STRATUM_WORDS[model.stratum] + ' tickets on a compressed axis, and their mean. The tables under the chart carry every value.'));
    const bands = SC.svg('g', { 'class': 'ss-find__bands' });
    const under = SC.svg('g'), marks = SC.svg('g'), over = SC.svg('g'), axis = SC.svg('g', { 'class': 'ss-find__axis' });
    svg.appendChild(bands); svg.appendChild(under); svg.appendChild(marks); svg.appendChild(over); svg.appendChild(axis);
    const plotRight = G.left + G.plotW;
    // the ratio rule's two thresholds: under the first it fires red, under the second
    // yellow; above the second it fires nothing, and green also needs every other rule
    // quiet, so no wash claims green. The lines are named at the axis, never over a mark.
    const red = G.ya(th.ratio_10d_red), yellow = G.ya(th.ratio_10d_yellow);
    bands.appendChild(SC.svg('rect', { 'class': 'ss-find__wash', x: G.left, y: red, width: G.plotW, height: Math.max(0, G.aBottom - red), style: tone('danger') }));
    bands.appendChild(SC.svg('rect', { 'class': 'ss-find__wash', x: G.left, y: yellow, width: G.plotW, height: Math.max(0, red - yellow), style: tone('warn') }));
    const refs = [[red, 'red', th.ratio_10d_red], [yellow, 'yellow', th.ratio_10d_yellow]];
    refs.forEach(([y, kind, value]) => {
      under.appendChild(SC.svg('line', { 'class': 'ss-find__ref', x1: G.left, x2: plotRight, y1: y, y2: y, 'data-ref': kind }));
      axis.appendChild(SC.svg('text', { 'class': 'ss-find__ref-text', x: G.left - 6, y: y + 3.5, 'text-anchor': 'end', 'data-ref-label': kind }, fixed(value, 1)));
    });
    // panel A: the ratio, one line broken where a session has none, markers on the published nights
    let d = '', pen = false;
    model.sessions.forEach((s, i) => {
      if (!isNum(s.ratio_10d)) { pen = false; return; }
      d += (pen ? 'L' : 'M') + G.x(i) + ',' + G.ya(s.ratio_10d);
      pen = true;
    });
    under.appendChild(SC.svg('path', { 'class': 'ss-find__line', d, style: tone('chart-emphasis') }));
    SC.ticks(G.rLo, G.rHi, G.narrow ? 3 : 4).ticks.forEach((t) => {
      if (t < G.rLo || t > G.rHi) return;
      const y = G.ya(t);
      under.appendChild(SC.svg('line', { 'class': 'ss-find__grid', x1: G.left, x2: plotRight, y1: y, y2: y }));
      if (refs.some((r) => Math.abs(r[0] - y) < 11)) return;   // the reference already names this height
      axis.appendChild(SC.svg('text', { 'class': 'ss-find__tick', x: G.left - 6, y: y + 3.5, 'text-anchor': 'end' }, fixed(t, 1)));
    });
    // the panel names, short on a phone so neither leaves the chart
    axis.appendChild(SC.svg('text', { 'class': 'ss-find__panel', x: G.left, y: G.aTop - 4 }, G.narrow
      ? plain(rules.ratio_long_sessions) + '-session ratio'
      : plain(rules.ratio_long_sessions) + '-session ratio, up ' + plain(rules.burst_pct) + '% against down'));
    // panel B: zero line, ticks, the compressed outcome axis
    const zero = G.yb(0);
    under.appendChild(SC.svg('line', { 'class': 'ss-find__zero', x1: G.left, x2: plotRight, y1: zero, y2: zero }));
    G.ticksB.forEach((t) => {
      const y = G.yb(t);
      if (t !== 0) under.appendChild(SC.svg('line', { 'class': 'ss-find__grid', x1: G.left, x2: plotRight, y1: y, y2: y }));
      axis.appendChild(SC.svg('text', { 'class': 'ss-find__tick', x: G.left - 6, y: y + 3.5, 'text-anchor': 'end', 'data-r-tick': t }, (t > 0 ? '+' : t < 0 ? '−' : '') + Math.abs(t) + 'R'));
    });
    axis.appendChild(SC.svg('text', { 'class': 'ss-find__panel', x: G.left, y: G.bTop - 6 }, G.narrow
      ? 'R per ticket, compressed axis'
      : 'what the night’s ' + (model.stratum === 'all' ? 'tickets, every burst,' : STRATUM_WORDS[model.stratum] + ' tickets') + ' did: R per ticket, compressed axis'));
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
      const cx = G.x(nt.i);
      const g = SC.svg('g', { 'class': 'ss-find__night', 'data-night': nt.session, 'data-k': k });
      if (isNum(nt.regime.ratio_10d)) {
        g.appendChild(SC.svg('circle', { 'class': 'ss-find__dot', cx, cy: G.ya(nt.regime.ratio_10d), r: 4.5, style: tone(VERDICT_TONE[nt.regime.verdict] || 'chart-context') }));
      }
      const b = nt.block;
      b.r.forEach((v, j) => {
        const off = ((j * GOLDEN) % 1 - 0.5) * G.slot * 0.8;
        g.appendChild(SC.svg('circle', { 'class': 'ss-find__r', cx: r1(cx + off), cy: G.yb(v), r: G.dot, style: tone('chart-context'), 'data-r': v }));
      });
      // a night with nothing settled has no mean and draws none: a mark on the zero line would read as a mean of zero
      if (isNum(b.settled.mean_r)) {
        g.appendChild(SC.svg('circle', { 'class': 'ss-find__mean', cx, cy: G.yb(b.settled.mean_r), r: 4.5, style: tone('chart-emphasis'), 'data-mean': b.settled.mean_r }));
      }
      marks.appendChild(g);
      nightMarks[nt.session] = g;
    });
    // the pill naming the current night's outcome, in the gap between the panels
    const pill = SC.svg('g', { 'class': 'ss-find__pill', 'data-pill': '' });
    const pillRect = SC.svg('rect', { rx: 4, ry: 4, height: 18 });
    const pillText = SC.svg('text', { 'class': 'ss-find__pill-text', 'text-anchor': 'middle' });
    pill.appendChild(pillRect); pill.appendChild(pillText); over.appendChild(pill);
    // dates along the floor, thinned to fit, and the backtest's own window
    // the last date ends at the plot's edge, never past the chart, and a thinned date
    // that would reach into it is dropped rather than drawn against it
    const lastAt = model.sessions.length - 1, lastLeft = plotRight - short(model.sessions[lastAt].date).length * CHAR;
    model.sessions.forEach((s, i) => {
      const last = i === lastAt, label = short(s.date);
      if (!last && (i % G.dateEvery !== 0 || G.x(i) + label.length * CHAR / 2 + 8 > lastLeft)) return;
      axis.appendChild(SC.svg('text', { 'class': 'ss-find__date', x: last ? plotRight : G.x(i), y: G.axisY, 'text-anchor': last ? 'end' : 'middle' }, label));
    });
    const wFrom = model.index[model.window.from], wTo = model.index[model.window.through];
    if (isNum(wFrom) && isNum(wTo)) {
      const x1 = r1(G.x(wFrom) - G.slot / 2), x2 = r1(G.x(wTo) + G.slot / 2), y = G.bracketY;
      over.appendChild(SC.svg('path', { 'class': 'ss-find__bracket', d: 'M' + x1 + ',' + (y - 5) + 'V' + y + 'H' + x2 + 'V' + (y - 5), 'data-bracket': 'backtest' }));
      // the label starts at the bracket's left end, or ends at its right end when it would run past the chart
      const label = (G.narrow ? 'exact lookback · ' : 'the backtest’s exact-lookback pass · ') + plural(model.window.count, 'session');
      const fits = x1 + 4 + label.length * CHAR <= G.W - 2;
      axis.appendChild(SC.svg('text', { 'class': 'ss-find__bracket-text', x: fits ? x1 + 4 : Math.min(x2, plotRight), y: y - 9, 'text-anchor': fits ? 'start' : 'end',
        'data-bracket-label': 'backtest' }, label));
    }
    // hit columns: one per session, over everything; a press is resolved by distance
    const hits = SC.svg('g', { 'class': 'ss-find__hits' });
    model.sessions.forEach((s, i) => {
      hits.appendChild(SC.svg('rect', { 'class': 'ss-find__hit', x: r1(G.x(i) - G.slot / 2), y: G.aTop, width: r1(G.slot), height: G.bBottom - G.aTop, 'data-hit': s.date, 'data-i': i }));
    });
    svg.appendChild(hits);
    function place(k) {
      const nt = model.nights[k];
      cursor.style.transform = 'translateX(' + r1(G.x(nt.i) - G.slot / 2) + 'px)';
      const text = pillText_(nt.block);
      const width = text.length * 6.4 + 14;
      const cx = Math.min(plotRight - width / 2 - 2, Math.max(G.left + width / 2 + 2, G.x(nt.i)));
      const yPill = G.aBottom + 6;
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
    // the published nights within a finger of a press, nearest first, in SVG units
    function near(clientX) {
      const box = svg.getBoundingClientRect(), scale = box.width ? G.W / box.width : 1;
      const xs = (clientX - box.left) * scale;
      return model.nights.map((nt, k) => ({ k, d: Math.abs(G.x(nt.i) - xs) / scale }))
        .filter((c) => c.d <= TAP_RADIUS).sort((a, b) => a.d - b.d);
    }
    return { svg, G, place, reveal, hits, nightMarks, near };
  }
  function pillText_(b) {
    if (isNum(b.settled.mean_r)) return R3(b.settled.mean_r) + ' · ' + num(b.settled.n) + ' settled';
    return b.buckets.pending ? plural(b.buckets.pending, 'ticket') + ' pending' : 'nothing settled';
  }

  // ---- captions: the night in words, every number the file's ---------------
  function factsOf(F, nt, stratum) {
    const rules = F.rules, b = stratumOf(nt, stratum);
    const reg = nt.regime, bk = b.buckets, st = b.settled;
    const hold = plain(rules.record.open_plan_sessions);
    const facts = [];
    facts.push({ chip: [reg.verdict, VERDICT_TONE[reg.verdict] || 'neutral'],
                 text: sizeWords(reg.size_multiplier) + ' · ' + num(reg.up4) + ' up ' + plain(rules.breadth.burst_pct) + '% against ' +
                       num(reg.down4) + ' down on the day · ' + num(reg.up4_10d) + ' against ' + num(reg.down4_10d) + ' over ' +
                       plain(rules.breadth.ratio_long_sessions) + ' sessions, ratio ' + fixed(reg.ratio_10d, 2) + '.' });
    // the study's rows are bursts; the file counts the tickets the production rules wrote for
    // them, the set-aside ones included, and says separately which of those were never walked
    let cf = 'Gate removed, reader not run: of ' + plural(b.rows, stratum === 'all' ? 'burst' : STRATUM_WORDS[stratum] + ' burst') +
             ' the rules wrote ' + plural(b.tickets, 'ticket') + ' at full size';
    if (bk.basis_mismatch) cf += ', ' + num(bk.basis_mismatch) + ' of them set aside unwalked because the later records do not carry the signal’s own bar as it was published';
    if (st.n) {
      cf += '; ' + num(st.n) + ' settled' + (nt.complete ? '' : ' so far') + ' · ' + num(st.wins) + ' won, ' + num(st.losses) + ' lost, ' +
            num(st.breakeven) + ' even · ' + R2(st.sum_r) + ' in all, ' + R3(st.mean_r) + ' per settled ticket, median ' + R2(st.median_r);
    } else {
      cf += nt.complete ? '; none settled' : '; none settled yet';
    }
    const rest = [];
    if (bk.uncertain) rest.push(num(bk.uncertain) + ' uncertain on daily bars');
    if (bk.not_filled) rest.push(num(bk.not_filled) + ' not filled');
    if (bk.open) rest.push(num(bk.open) + ' still open');
    if (bk.pending) rest.push(num(bk.pending) + ' pending');
    if (bk.unmeasured) rest.push(num(bk.unmeasured) + ' unmeasured');
    if (bk.unreadable) rest.push(num(bk.unreadable) + ' unreadable');
    if (bk.unscored) rest.push(num(bk.unscored) + ' unscored');
    facts.push(cf + (rest.length ? ' · ' + rest.join(', ') : '') + '.');
    const none = [];
    if (bk.no_ticket) none.push(num(bk.no_ticket) + ' the rules would not write a ticket for');
    if (bk.plan_error) none.push(num(bk.plan_error) + ' whose ticket could not be formed');
    if (none.length) facts.push('Without a ticket: ' + none.join('; ') + '.');
    const fr = nt.first_read && (stratum === 'admitted' ? nt.first_read.admitted : stratum === 'all' ? nt.first_read.all : null);
    if (fr && fr.n) {
      const then = R3(fr.mean_r) + ' per settled ticket over ' + num(fr.n);
      const now = R3(st.mean_r) + ' over ' + num(st.n);
      const same = fr.n === st.n && fr.mean_r === st.mean_r;
      facts.push('The first read, with records through ' + short(nt.first_read.as_of) +
        (nt.first_read.horizon_passed ? '' : ', before every ticket had had its ' + hold + ' sessions') + ': ' + then +
        (same ? '; unchanged since.' : '; read now, ' + now + '.'));
    }
    if (!nt.complete) facts.push('The ' + hold + '-session hold runs through ' + words(nt.horizon) + '; nothing here is final before then.');
    return facts;
  }

  function textOf(F, nt) {
    const reg = nt.regime, rd = nt.reads || {};
    const reader = rd.done
      ? 'The chart reader gave a usable read on ' + num(rd.done) + ' of ' + plural(rd.requested, 'requested name') + '; after it, ' + num(nt.a_quality.final) +
        ' stood at A-quality, every name without a usable read keeping the checklist’s grade.'
      : 'The chart reader gave no usable read on any of the ' + plural(rd.requested, 'requested name') + ' that night; every grade is the checklist’s.';
    return 'The scan found ' + plural(nt.bursts, 'burst') + '. The checklist graded ' + num(nt.a_quality.mechanical) + ' of them A-quality and vetoed ' +
      num(nt.vetoed) + '. ' + reader + ' The market gate said ' + reg.verdict + ': ' + sentence(reg.reasons) + ' It published ' +
      plural(nt.tickets_published, 'ticket') + '.';
  }

  // ---- the table twins: named, focusable scrollers, as every twin in the app ----
  function twin(SC, host, spec, key) {
    const table = SC.tableTwin(host, spec);
    const details = table.closest('details'), scroll = table.closest('.sc-table-scroll');
    if (details) details.setAttribute('data-find', key);
    if (scroll) { scroll.tabIndex = 0; scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', spec.summary); }
    return table;
  }
  function twins(SC, host, F, model) {
    const who = model.stratum === 'all' ? 'every burst' : 'the ' + STRATUM_WORDS[model.stratum] + ' bursts';
    twin(SC, host, {
      caption: 'Every published night: the market, the scan, and the counterfactual tickets of ' + who,
      summary: 'Nights as a table',
      head: ['night', 'verdict', 'ratio', 'bursts', 'A-quality, checklist', 'A-quality, after the reader', 'tickets published',
             'bursts in the stratum', 'tickets written', 'set aside unwalked', 'settled', 'won', 'lost', 'even', 'sum R', 'mean R', 'uncertain', 'not filled', 'open', 'pending'],
      rows: model.nights.map((nt) => {
        const b = nt.block, s = b.settled;
        return [words(nt.session), nt.regime.verdict, fixed(nt.regime.ratio_10d, 2), num(nt.bursts), num(nt.a_quality.mechanical), num(nt.a_quality.final),
                num(nt.tickets_published), num(b.rows), num(b.tickets), num(b.buckets.basis_mismatch), num(s.n), num(s.wins), num(s.losses), num(s.breakeven), signed(s.sum_r, 2), signed(s.mean_r, 3),
                num(b.buckets.uncertain), num(b.buckets.not_filled), num(b.buckets.open), num(b.buckets.pending)];
      }),
    }, 'table-nights');
    twin(SC, host, {
      caption: 'Every session the records know: the counts and the ratio the gate read, oldest first',
      summary: 'Market sessions as a table',
      head: ['session', 'up', 'down', 'ratio', 'verdict', 'read from'],
      rows: model.sessions.map((s) => [words(s.date), num(s.up4), num(s.down4), fixed(s.ratio_10d, 2), s.verdict || 'no publication',
        (s.basis === 'publication' ? 'its own publication ' + s.source : 'the history of ' + s.source) + (isNum(s.later_ratio_10d) ? ' (a later history reads ' + fixed(s.later_ratio_10d, 2) + ')' : '')]),
    }, 'table-market');
  }

  // ---- mount ---------------------------------------------------------------
  function mount(host, F, opts) {
    const SC = w.SC;
    opts = opts || {};
    if (!host || !SC || !SC.svg || shapeProblem(F)) return null;
    const id = ++mounted;
    const ids = { title: 'ss-find-title-' + id, desc: 'ss-find-desc-' + id, caption: 'ss-find-caption-' + id, filter: 'ss-find-filter-' + id,
                  head: 'ss-find-h-' + id, pick: 'ss-find-pick-' + id };
    const interval = Math.max(200, Number(opts.interval) || INTERVAL);
    const reduced = () => !!(w.matchMedia && w.matchMedia('(prefers-reduced-motion: reduce)').matches);
    let stratum = STRATA.indexOf(opts.stratum) >= 0 ? opts.stratum : 'admitted';
    let model = modelOf(F, stratum);
    let step = 0, timer = null, view = null, drawnWidth = 0, tip = null, pick = null;
    const el = SC.el;
    const hold = plain(F.rules.record.open_plan_sessions);

    // the stratum control: one captioned group, above everything it scopes
    const tabs = el('div', { 'class': 'sc-tabs', role: 'group', 'aria-labelledby': ids.filter });
    STRATA.forEach((s) => {
      tabs.appendChild(el('button', { type: 'button', 'class': 'sc-tab sc-tab--case', 'data-find-stratum': s, 'aria-pressed': s === stratum ? 'true' : 'false',
        text: STRATUM_WORDS[s], onclick: () => setStratum(s) }));
    });
    const filter = el('div', { 'class': 'sc-field sc-field--group ss-find__filter' }, [el('span', { 'class': 'sc-field__label', id: ids.filter, text: 'tickets' }), tabs]);

    const chart = el('div', { 'class': 'ss-find__chart' });
    // a label in the name: each control's visible word is the start of its accessible name
    const back = el('button', { type: 'button', 'class': 'sc-btn sc-btn--secondary sc-btn--sm', 'data-find': 'back', text: 'Back', 'aria-label': 'Back to the previous night' });
    const play = el('button', { type: 'button', 'class': 'sc-btn sc-btn--secondary sc-btn--sm', 'data-find': 'play', text: 'Play' });
    const next = el('button', { type: 'button', 'class': 'sc-btn sc-btn--secondary sc-btn--sm', 'data-find': 'next', text: 'Next', 'aria-label': 'Next night' });
    // the one live region: a line per step, short enough to be heard to its end
    const count = el('span', { 'class': 'ss-find__count', 'data-find': 'count', 'aria-live': 'polite' });
    const controls = el('div', { 'class': 'ss-find__controls' }, [back, play, next, count]);
    // the legend: the marks named in words beside them, a key per verdict the nights carry
    const present = VERDICTS.filter((v) => F.nights_summary.verdicts[v]);
    const legend = el('div', { 'class': 'sc-legend ss-find__legend', 'data-find': 'legend' }, [
      el('span', null, [el('i', { 'class': 'ss-find__key ss-find__key--line' }), plain(F.rules.breadth.ratio_long_sessions) + '-session ratio'])]
      .concat(present.map((v) => el('span', { 'data-find-key': v }, [el('i', { 'class': 'is-swatch ss-find__key ss-find__key--' + VERDICT_TONE[v] }), v + ' night'])))
      .concat([el('span', null, [el('i', { 'class': 'is-swatch ss-find__key ss-find__key--dot' }), 'one settled ticket']),
               el('span', null, [el('i', { 'class': 'is-swatch ss-find__key ss-find__key--mean' }), 'the night’s mean'])]));
    const th = F.market.thresholds, br = F.rules.breadth;
    const regimeKey = el('p', { 'class': 'sc-hint ss-find__regime-key', 'data-find': 'regime-key', text: 'Dashed lines, the ' + plain(br.ratio_long_sessions) +
      '-session ratio rule: under ' + fixed(th.ratio_10d_red, 1) + ' it says red, no new longs; under ' + fixed(th.ratio_10d_yellow, 1) +
      ' yellow, size × ' + plain(br.size_multiplier.yellow) + ', ' + F.rules.pipeline.yellow_grades.join(' and ') + ' only. Above ' +
      fixed(th.ratio_10d_yellow, 1) + ' it says nothing, and the night is green only when no other breadth rule fires either.' });
    const stage = el('div', { 'class': 'ss-find__stage', tabindex: 0, role: 'group', 'aria-roledescription': 'animated replay',
      'aria-label': 'The record night by night. Arrow keys move between nights, Home and End jump to the first and last, Space plays and pauses.',
      'aria-describedby': ids.caption }, [chart, legend, regimeKey, controls]);
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
    const caption = el('div', { 'class': 'ss-find__caption', id: ids.caption }, [eyebrow, title, text, facts, who]);
    const ns = F.nights_summary;
    host.appendChild(el('h3', { 'class': 'ss-find__h', id: ids.head, text: 'The record, night by night' }));
    host.appendChild(el('p', { 'class': 'sc-note', 'data-find': 'lead', text: 'Over the ' + plural(ns.nights, 'published night') + ' from ' + words(ns.from) + ' to ' + words(ns.through) +
      ' the gate said ' + verdictCount(ns.verdicts) + ' and published ' + plural(ns.tickets_published, 'ticket') + ' out of ' + plural(ns.bursts, 'burst') + ' scanned. ' +
      'The study then ran the production ticket rules over every burst, the gate removed and the reader not run, to see what the refusals were worth. Step through the nights or press Play; on a phone the list of nights is the precise way to one.' }));
    const root = el('div', { 'class': 'ss-find', 'data-find-root': '', 'data-stratum': stratum, 'aria-labelledby': ids.head, role: 'region' }, [filter, stage, side, caption]);
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
      count.textContent = 'Night ' + (step + 1) + ' of ' + model.nights.length + ' · ' + short(nt.session) + ' · ' + nt.regime.verdict + ' · ' + pillText_(nt.block);
      back.setAttribute('aria-disabled', step === 0 ? 'true' : 'false');
      next.setAttribute('aria-disabled', step === model.nights.length - 1 ? 'true' : 'false');
      root.setAttribute('data-night', nt.session);
      root.setAttribute('data-step', String(step + 1));
      root.classList.toggle('is-animated', !!animate && !reduced());
    }
    function go(n, animate) {
      closePick(false);
      step = Math.max(0, Math.min(model.nights.length - 1, n));
      paint(animate !== false);
      if (step === model.nights.length - 1) stopPlay();
    }
    // Play steps only while the replay is on screen: leaving the view, or hiding the tab, stops it
    let onScreen = true;
    if (w.IntersectionObserver) new w.IntersectionObserver((es) => { onScreen = es[es.length - 1].isIntersecting; if (!onScreen) stopPlay(); }).observe(stage);
    const shown = () => onScreen && stage.offsetParent !== null && !w.document.hidden;
    function startPlay() {
      if (timer) return;
      if (step === model.nights.length - 1) go(0);
      timer = w.setInterval(() => { if (!shown()) { stopPlay(); return; } go(step + 1); }, interval);
      play.textContent = 'Pause';
    }
    function stopPlay() {
      if (timer) w.clearInterval(timer);
      timer = null;
      play.textContent = 'Play';
    }
    play.addEventListener('click', () => { if (timer) stopPlay(); else startPlay(); });
    next.addEventListener('click', () => { stopPlay(); go(step + 1); });
    back.addEventListener('click', () => { stopPlay(); go(step - 1); });
    stage.addEventListener('keydown', (e) => {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      if (pick && pick.contains(e.target)) return;
      const keys = { ArrowRight: step + 1, ArrowLeft: step - 1, Home: 0, End: model.nights.length - 1 };
      if (e.key in keys) { e.preventDefault(); stopPlay(); go(keys[e.key]); return; }
      if (e.key === ' ' && e.target === e.currentTarget) { e.preventDefault(); if (timer) stopPlay(); else startPlay(); }
    });
    w.document.addEventListener('visibilitychange', () => { if (w.document.hidden) stopPlay(); });

    // a press that several published nights sit within a finger of asks which one
    // the reference is cleared BEFORE the node leaves the page: removing a focused
    // node fires its focusout, whose handler would otherwise remove it a second time.
    // A chooser closed while it held the focus (a choice, Escape, a redraw) hands it
    // back to the stage; one the reader left by Tab or a tap elsewhere leaves the
    // focus where the reader put it
    function closePick(refocus) {
      const node = pick;
      if (!node) return;
      pick = null;
      const held = node.contains(w.document.activeElement);
      node.remove();
      if (refocus || held) stage.focus({ preventScroll: true });
    }
    function openPick(cands) {
      closePick(false);
      const list = el('div', { 'class': 'sc-pick__list', role: 'group', 'aria-label': 'The nights within a finger of the press, nearest first' });
      cands.forEach((c) => {
        const nt = model.nights[c.k];
        list.appendChild(el('button', { type: 'button', 'class': 'sc-pick__item', 'data-pick-night': nt.session, 'aria-pressed': c.k === step ? 'true' : 'false',
          onclick: () => { stopPlay(); go(c.k); stage.focus(); } }, [
          el('span', { 'class': 'sc-pick__name', text: words(nt.session) }),
          el('span', { 'class': 'sc-pick__meta', text: nt.regime.verdict + ' · ' + pillText_(nt.block) })]));
      });
      const close = el('button', { type: 'button', 'class': 'sc-btn sc-btn--ghost sc-btn--sm', 'data-pick': 'close', text: 'Close', onclick: () => closePick(true) });
      pick = el('div', { 'class': 'sc-pick ss-find__pick', role: 'dialog', 'aria-labelledby': ids.pick, 'data-find': 'pick' }, [
        el('div', { 'class': 'sc-pick__head' }, [el('h4', { id: ids.pick, text: plural(cands.length, 'night') + ' within a finger' }), close]),
        el('p', { 'class': 'sc-pick__hint', text: 'Nearest first. The list of nights reaches each one exactly.' }), list]);
      pick.addEventListener('keydown', (e) => { if (e.key === 'Escape') { e.preventDefault(); closePick(true); } });
      pick.addEventListener('focusout', (e) => { if (pick && !pick.contains(e.relatedTarget)) closePick(false); });
      chart.appendChild(pick);
      const first = pick.querySelector('.sc-pick__item');
      if (first) first.focus();
    }

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
        rows.push({ value: num(b.tickets), label: 'tickets written, ' + STRATUM_WORDS[stratum] });
        rows.push({ value: R3(b.settled.mean_r), label: 'mean R, ' + num(b.settled.n) + ' settled' });
        meta += ' · ' + plural(nt.bursts, 'burst');
      }
      return { title: words(s.date), rows, meta };
    }
    function draw() {
      const width = chart.clientWidth;
      if (!width) return;
      if (view && Math.abs(width - drawnWidth) <= 1) return;
      drawnWidth = width;
      closePick(false);
      chart.textContent = '';
      if (tip) { tip.destroy(); tip = null; }
      view = buildSvg(SC, F, model, width, ids);
      chart.appendChild(view.svg);
      if (SC.tooltip) {
        tip = SC.tooltip(chart, { live: false, top: 6, flip: 0.55, offsetX: 14 });
        view.hits.addEventListener('pointermove', (e) => {
          const hit = e.target && e.target.getAttribute && e.target.getAttribute('data-i');
          if (hit === null || hit === undefined) return;
          tip.show(tooltipFor(Number(hit)), e);
        });
        view.hits.addEventListener('pointerleave', () => tip.hide());
      }
      view.hits.addEventListener('click', (e) => {
        // a mouse takes the nearest night; a finger that has more than one within reach is asked
        const cands = view.near(e.clientX);
        if (!cands.length) return;
        if (e.pointerType === 'touch' && cands.length > 1) { if (tip) tip.hide(); openPick(cands); return; }
        stopPlay(); go(cands[0].k);
      });
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
            num(p.uncertain), num(p.not_filled), s.readable ? pct2(s.spy_avg_pct) : '—'];
  }
  // a split row of the pasted summary carries plans, settled, wins, losses and sum R; no breakeven
  const splitRow = (label, b) => [label, num(b.plans), num(b.settled), num(b.wins) + ' / ' + num(b.losses) + ' / —', signed(b.sum_r, 2), '—', '—', '—', '—', '—', '—'];
  function renderBacktest(host, F) {
    const SC = w.SC, el = SC.el;
    const L = F.backtest.lookback_130, X = F.backtest.lookback_260;
    const prod = L.gates.production, cf = L.gates.no_regime_gate;
    const v = L.regimes.verdicts, green = v.green || 0;
    const sec = el('section', { 'class': 'ss-find__block', 'data-find-block': 'backtest', 'aria-labelledby': 'ss-find-backtest-h' });
    sec.appendChild(el('p', { 'class': 'sc-eyebrow', text: 'owner-run backtest · recorded as pasted · reader not run' }));
    sec.appendChild(el('h3', { id: 'ss-find-backtest-h', text: 'The policy over ' + plural(L.evaluated.count, 'session') + ' of the archive' }));
    sec.appendChild(el('p', { text: 'The same nightly decision replayed over the bars of the acquisition archive, session by session, from ' + words(L.evaluated.from) +
      ' to ' + words(L.evaluated.through) + ', on the owner’s computer. The chart reader was not run, so every ticket here is one it could still have refused. ' +
      'The gate said ' + verdictCount(v) + (green ? '.' : ', never green, so the full-size state has not been exercised on real bars.') }));
    const strip = el('dl', { 'class': 'sc-stat-strip sc-stat-strip--4 sc-stat-strip--instrument ss-find__stats', 'data-find': 'backtest-strip' }, [
      stat(el, 'sessions', num(L.evaluated.count), short(L.evaluated.from) + ' to ' + short(L.evaluated.through)),
      stat(el, 'yellow nights', num(v.yellow || 0), num(v.red || 0) + ' red · ' + num(green) + ' green'),
      stat(el, 'tickets', num(prod.tickets), green ? 'on yellow and green nights' : F.rules.pipeline.yellow_grades.join(' and ') + ' only, size × ' + plain(F.rules.breadth.size_multiplier.yellow)),
      stat(el, 'net result', R2(prod.settled.sum_r), plural(prod.settled.n, 'settled ticket') + ' · ' + num(prod.settled.wins) + ' won, ' + num(prod.settled.losses) + ' lost', true),
    ]);
    sec.appendChild(strip);
    const s = prod.settled;
    sec.appendChild(el('p', { 'class': 'sc-note', 'data-find': 'backtest-rates', text: 'Win rate ' + share(s.win_rate) + ' · mean ' + R2(s.avg_r) + ' · median ' + R2(s.median_r) +
      ' · ' + num(prod.plans.uncertain) + ' uncertain on daily bars · ' + num(prod.plans.not_filled) + ' not filled · SPY ' + pct2(s.spy_avg_pct) + ' over ' + plural(s.spy_pairs, 'matched pair') +
      ' · ' + plural(L.candidates.bursts, 'burst') + ' scanned · rules ' + L.rules_version + ' · lookback equivalence ' + L.lookback.equivalence.status + ' over ' +
      plural(L.lookback.equivalence.compared, 'shared session') + ' with ' + plural(L.lookback.equivalence.differences, 'difference') + '.' }));
    sec.appendChild(bars(el, [['yellow nights', v.yellow || 0, 'warn'], ['red nights', v.red || 0, 'danger'], ['green nights', green, 'good']], 'chart-context'));
    sec.appendChild(bars(el, [['won', s.wins], ['lost', s.losses], ['even', s.breakeven]], 'chart-emphasis'));
    const head = ['policy', 'tickets', 'settled', 'won / lost / even', 'sum R', 'mean R', 'median R', 'win rate', 'uncertain', 'not filled', 'SPY'];
    const rows = [['production'].concat(gateRows(prod)), ['gate removed'].concat(gateRows(cf))];
    Object.keys(cf.by_regime).sort().forEach((k) => rows.push(splitRow('gate removed, ' + k + ' nights', cf.by_regime[k])));
    Object.keys(cf.by_grade).sort().forEach((k) => rows.push(splitRow('gate removed, grade ' + k, cf.by_grade[k])));
    rows.push([plural(X.evaluated.count, 'session') + ': production'].concat(gateRows(X.gates.production)));
    rows.push([plural(X.evaluated.count, 'session') + ': gate removed'].concat(gateRows(X.gates.no_regime_gate)));
    const scroll = el('div', { 'class': 'sc-table-scroll ss-find__bt', 'data-find': 'backtest-table', tabindex: 0, role: 'region', 'aria-label': 'Backtest as a table' });
    SC.tableTwin(scroll, { caption: 'The backtest’s two blocks over ' + plural(L.evaluated.count, 'session') + ', the gate removed being a counterfactual and not a policy, and the exact-lookback pass over ' +
      plural(X.evaluated.count, 'session') + ' from ' + short(X.evaluated.from) + ', as pasted', head, rows, details: false });
    sec.appendChild(scroll);
    sec.appendChild(el('p', { 'class': 'sc-hint', 'data-find': 'backtest-source', text: '“Gate removed” is the counterfactual block, not a policy; the last two rows are the exact-lookback pass from ' +
      short(X.evaluated.from) + '. Rates print only where the pasted summary read them (' + plain(prod.settled.min_read) +
      ' settled or more); a dash is a number the summary did not carry. Two summaries, SHA-256 ' + L.source.sha256.slice(0, 12) + ' and ' + X.source.sha256.slice(0, 12) +
      ', parsed by the backtest tool’s own grammar; the per-ticket files stay on the owner’s machine.' }));
    const lim = el('details', { 'class': 'sc-disclosure', 'data-find': 'backtest-limits' }, [el('summary', { text: 'The backtest’s own limitations, as its summary prints them' }),
      el('ul', { 'class': 'ss-find__reading' }, L.limitations.map((t) => el('li', { text: t })))]);
    sec.appendChild(lim);
    host.appendChild(sec);
  }
  function renderRun6(host, F) {
    const SC = w.SC, el = SC.el, R = F.run6;
    const days = Object.keys(R.sessions).sort();
    const sec = el('section', { 'class': 'ss-find__block', 'data-find-block': 'run6', 'aria-labelledby': 'ss-find-run6-h' });
    sec.appendChild(el('p', { 'class': 'sc-eyebrow', text: 'run ' + num(R.public.run_number) + ' · fresh bars for every intended stock · owner-read' }));
    sec.appendChild(el('h3', { id: 'ss-find-run6-h', text: 'The red reading, checked on fresh bars' }));
    sec.appendChild(el('p', { text: 'A later retrieval of the bars for every stock the record intended, recomputing the gate’s own ratio for ' +
      days.map(words).join(' and ') + '. The verdict the gate published is compared with the one an independent calculator reads off the fresh bars.' }));
    const head = ['session', 'published ratio', 'fresh ratio', 'up / down over ten', 'could be anywhere in', 'counted', 'verdict', 'rules that fired'];
    const rows = days.map((day) => {
      const s = R.sessions[day], c = s.policies.C, o = s.original;
      return [words(day), fixed(o.ratio_10d, 2) + ' (' + num(o.up4_10d) + ' / ' + num(o.down4_10d) + ')', fixed(c.ratio_10d, 2), num(c.up4_10d) + ' / ' + num(c.down4_10d),
              fixed(c.ratio_10d_bounds[0], 2) + ' to ' + fixed(c.ratio_10d_bounds[1], 2) + ' over ' + plural(c.unknown_contributors, 'unknown'),
              num(o.universe) + ' published, ' + num(c.counted_universe) + ' fresh', o.verdict + ' published, ' + c.independent_verdict + ' fresh', c.rules_fired.map(underscores).join(', ')];
    });
    const scroll = el('div', { 'class': 'sc-table-scroll', 'data-find': 'run6-table', tabindex: 0, role: 'region', 'aria-label': 'Run ' + num(R.public.run_number) + ' as a table' });
    SC.tableTwin(scroll, { caption: 'The published and the freshly retrieved breadth reading, by session', head, rows, details: false });
    sec.appendChild(scroll);
    const partial = days.map((day) => num(R.sessions[day].partial) + ' on ' + short(day)).join(' and ');
    sec.appendChild(el('p', { 'class': 'sc-note', 'data-find': 'run6-facts', text: num(R.download.queries_completed) + ' of ' + num(R.download.queries_total) + ' queries completed; ' +
      'symbols returning a partial window: ' + partial + ', no cause assigned; strict establishment stays blocked by ' + plural(R.blocking_names.length, 'counted stock') +
      ' (' + R.blocking_names.join(', ') + ') whose month-long history the fresh bars do not reach. Artifact ' + String(R.public.artifact.id) + ', ' + num(R.public.artifact.size_in_bytes) +
      ' bytes, recovered and read on the owner’s machine; the summary’s SHA-256 is ' + R.source.sha256.slice(0, 12) + '.' }));
    host.appendChild(sec);
  }
  function renderReading(host, F) {
    const SC = w.SC, el = SC.el;
    const sec = el('section', { 'class': 'ss-find__block', 'data-find-block': 'reading', 'aria-labelledby': 'ss-find-reading-h' });
    sec.appendChild(el('h3', { id: 'ss-find-reading-h', text: 'Read it as' }));
    const strata = F.study.summary.strata, ns = F.nights_summary;
    const pooled = STRATA.slice(0, -1).map((s) => STRATUM_WORDS[s] + ' ' + R3(strata[s].settled.mean_r) + ' over ' + num(strata[s].settled.n)).join('; ');
    const onlyRed = VERDICTS.every((v) => v === 'red' || !ns.verdicts[v]);
    const positive = ns.admitted_positive_nights;
    const allUnder = STRATA.slice(0, -1).every((s) => isNum(strata[s].settled.mean_r) && strata[s].settled.mean_r < 0);
    const items = [
      'Pooled over the ' + plural(ns.nights, 'published night') + ' (' + verdictCount(ns.verdicts) + ') to ' + words(F.study.newest_session) +
        (ns.inside_hold ? ', ' + num(ns.inside_hold) + ' of them still inside their hold,' : '') + ' the mean R per settled counterfactual ticket by stratum: ' + pooled + '. ' +
        (allUnder ? 'Every stratum is under zero, so over these nights the refusals had value in sum' +
          (positive ? ', though ' + num(positive) + ' of the nights had a positive A-quality mean' : '') : 'Not every stratum is under zero, so the refusals did not have value in every grade') +
        (onlyRed ? '; what yellow or green nights would do is not in this record, which has carried none.' : '.'),
      'A night read before its tickets have had their hold leans toward losses, because a stop settles on its first bad day and a winner at its exit; the nights above are re-read as they complete, and the caption says when a night is still inside its hold.',
      'The chart reader is not run in either study; the mechanical grade is the ceiling of what it could have admitted, so the live policy would have written no more tickets than any counterfactual here.',
      'The study is exploratory where every next close was public before its spec was frozen, confirmatory only for nights published after it; nothing confirmatory is readable before its own minimum of settled tickets.',
    ];
    sec.appendChild(el('ul', { 'class': 'ss-find__reading', 'data-find': 'read-as' }, items.map((t) => el('li', { text: t }))));
    sec.appendChild(el('p', { 'class': 'sc-hint', text: 'The reports behind these numbers, served as the Markdown files they are:' }));
    // a report is linked only by the path the builder names; anything else is its title, unlinked
    sec.appendChild(el('ul', { 'class': 'ss-find__reports', 'data-find': 'reports' }, F.reports.map((r) => el('li', null,
      REPORT_PATH.test(String(r.path)) ? el('a', { 'class': 'sc-link--quiet', href: r.path.replace(/^docs\//, ''), text: r.title }) : el('span', { text: r.title })))));
    host.appendChild(sec);
  }

  S.findings = { VERSION, INTERVAL, STRATA, STRATUM_WORDS, TAP_RADIUS, shapeProblem, geometry, modelOf, factsOf, textOf, mount, renderBacktest, renderRun6, renderReading };
})(window);
