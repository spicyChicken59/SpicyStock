/* SpicyStock — the page. Renders docs/data.json (schema_version 2) on the
   SpicyChicken system and computes exactly one thing of its own: the status
   chip, from run.session / run.session_state / run.expected_session /
   generated and the browser clock in ET — because a run that failed cannot
   write its own obituary. Every other number is printed, never derived from
   a rule: thresholds come out of the archived `rules` and `breadth.regime`
   blocks, sizes out of `plan`, sentences out of `cover`, `open_plans[]` and
   `breadth.regime.reasons[]`, verbatim.

     SCStock.status(data, now)  -> {state, chip, tone, sentence, expected, behind}
     SCStock.render(data, now)  -> paints the page
     SCStock.data               -> the record the page last rendered

   Needs sc-charts.js (SC.el, SC.svg, SC.ticks, SC.tooltip, SC.tableTwin)
   and app-chart.js (SCStock.chart, SCStock.chartGeometry). */
(function (w) {
  'use strict';
  const SCStock = w.SCStock = w.SCStock || {};
  const d = w.document;

  // Facts, not thresholds. Bonde's own 4% scan finds a median 239 names a
  // night over his ~6,500-stock universe (his Market Monitor sheet, 2026);
  // the order deadline is the desk's own clock, not a strategy number.
  const BONDE_MEDIAN_NIGHT = 239;
  const ORDERS_BY = '9:28 AM';
  const PENDING_UNTIL_HOUR = 21;   // ET; evening.yml's retry fires at 8:16 PM and a full-market run takes minutes
  const ET = 'America/New_York';
  const REPO = 'spicyChicken59/SpicyStock';
  const RUNS_API = 'https://api.github.com/repos/' + REPO + '/actions/workflows/evening.yml/runs?per_page=1';
  const RUNS_URL = 'https://github.com/' + REPO + '/actions/workflows/evening.yml';

  // One fixed sentence per problem kind, the same seven src/report.py mails
  // (tests/test_docs.py holds the two lists equal); the message the run
  // recorded never reaches the page.
  const PROBLEMS = {
    universe_cached: "The stock directory could not be refreshed; tonight's universe is the cached one.",
    coverage_thin: "Part of the universe was not read: the bars fetch ran out of time or names answered late.",
    claude_unavailable: "The model did not answer; every grade tonight is the checklist's alone.",
    claude_partial: "The model answered for some names and not others; the rest are graded by the checklist alone.",
    chart_missing: "A chart did not render; the grade stands on the numbers.",
    email_failed: "The digest could not be delivered; the page is the record.",
    push_retried: "Committing the record took more than one push."
  };
  // One word per plan status, the same ten src/report.py mails (tests/test_docs.py holds the two equal).
  const PLAN_STATUS = {
    hold: ['HOLD', 'good'], sell_half: ['SELL HALF', 'brand'], sell_into_strength: ['SELL INTO STRENGTH', 'brand'],
    exit: ['SELL', 'brand'], stopped: ['STOPPED', 'danger'], expired: ['EXPIRED', 'neutral'], pending: ['PENDING', 'neutral'],
    not_filled: ['NOT FILLED', 'neutral'], unreadable: ['UNREADABLE', 'warn'], unmeasured: ['UNMEASURED', 'warn']
  };
  const REGIME_TONE = { green: 'good', yellow: 'warn', red: 'danger' };
  const FLAG_WORDS = { gain_over_15: 'gain over 15%', wide_stop: 'wide stop', position_capped: 'position capped', biotech: 'biotech', foreign: 'foreign', dollar_breakout: '$ breakout', refused: 'refused' };
  // The checklist's own keys (src/quality.py): 2 L Y N C H, then RE and VOL.
  const CRITERIA_SHORT = {
    two_days: 'up days', linearity: 'linear', young_trend: 'young', narrow_or_negative: 'quiet',
    consolidation: 'tight', close_near_high: 'close', range_expansion: 'range', volume: 'volume'
  };
  const VETO_WORDS = { up_days: 'three up days in a row', not_linear: 'the prior leg is not linear' };
  const STOP_BASIS = { burst_low: 'the burst day’s low', half_range: 'the burst bar’s midpoint' };
  const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  // ---------------------------------------------------------------- helpers
  const SC = () => w.SC;
  const el = (tag, attrs, kids) => SC().el(tag, attrs, kids);
  const svg = (tag, attrs, kids) => SC().svg(tag, attrs, kids);
  const isNum = (v) => typeof v === 'number' && isFinite(v);
  const thousands = (s) => s.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  const num = (v, dec) => isNum(v) ? thousands(v.toFixed(dec === undefined ? 0 : dec)) : '—';
  const usd = (v, dec) => isNum(v) ? (v < 0 ? '−' : '') + '$' + thousands(Math.abs(v).toFixed(dec === undefined ? 2 : dec)) : '—';
  const pct = (v, dec) => isNum(v) ? (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(dec === undefined ? 1 : dec) + '%' : '—';
  const plain = (v) => isNum(v) ? String(v).replace(/\.0$/, '') : '—';
  const words = (s) => (s || '').replace(/_/g, ' ');
  const cap = (s) => s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
  function parseISO(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
    return m ? new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], 12)) : null;
  }
  const toISO = (dt) => dt.toISOString().slice(0, 10);
  const dateWords = (iso) => { const dt = parseISO(iso); return dt ? WD[dt.getUTCDay()] + ' ' + dt.getUTCDate() + ' ' + MON[dt.getUTCMonth()] : (iso || '—'); };
  const dateShort = (iso) => { const dt = parseISO(iso); return dt ? dt.getUTCDate() + ' ' + MON[dt.getUTCMonth()] : (iso || '—'); };
  const dateMD = (iso) => (iso || '').slice(5, 10);
  function timeET(iso) {
    const dt = iso ? new Date(iso) : null;
    if (!dt || isNaN(dt.getTime())) return '—';
    return new Intl.DateTimeFormat('en-US', { timeZone: ET, hour: 'numeric', minute: '2-digit' }).format(dt) + ' ET';
  }
  function chip(text, tone, keepCase) {
    return el('span', { 'class': 'sc-chip sc-chip--' + (tone || 'neutral') + (keepCase ? ' sc-chip--case' : ''), text: text });
  }
  const empty = (text) => el('p', { 'class': 'sc-empty', text: text });
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); return node; }
  const $ = (id) => d.getElementById(id);
  const by = (list, key) => { const m = {}; (list || []).forEach((x) => { if (x && x.ticker) m[x.ticker] = x; }); return m; };

  // ---------------------------------------------------------------- ET clock
  function etParts(now) {
    const f = new Intl.DateTimeFormat('en-US', { timeZone: ET, weekday: 'short', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
    const p = {}; f.formatToParts(now).forEach((x) => { p[x.type] = x.value; });
    return { date: p.year + '-' + p.month + '-' + p.day, weekday: WD.indexOf(p.weekday), hour: (+p.hour) % 24, minute: +p.minute };
  }
  const isWeekday = (dt) => dt.getUTCDay() !== 0 && dt.getUTCDay() !== 6;
  function prevWeekday(iso) {
    const dt = parseISO(iso);
    do { dt.setUTCDate(dt.getUTCDate() - 1); } while (!isWeekday(dt));
    return toISO(dt);
  }
  // weekdays x with a < x <= b (0 when b <= a)
  function weekdaysBetween(a, b) {
    const da = parseISO(a), db = parseISO(b);
    if (!da || !db || db <= da) return 0;
    let n = 0; const dt = new Date(da.getTime());
    while (dt < db) { dt.setUTCDate(dt.getUTCDate() + 1); if (isWeekday(dt)) n++; }
    return n;
  }
  function weekdaysEnding(iso, n) {
    const out = []; const dt = parseISO(iso);
    while (out.length < n) { if (isWeekday(dt)) out.unshift(toISO(dt)); dt.setUTCDate(dt.getUTCDate() - 1); }
    return out;
  }

  // ---------------------------------------------------------------- status
  // The one rule the page computes. `expected` is the last session that has
  // CLOSED at `now` in ET: today's date on a weekday from 4:00 PM, otherwise
  // the previous weekday. `behind` counts the weekdays between the session
  // the record was published FOR and that. No holiday calendar: one session
  // behind is ambiguous (closed or failed) and says so; two is never a
  // closure, because no two US market holidays are adjacent.
  function status(data, now) {
    const run = (data && data.run) || {};
    const et = etParts(now || new Date());
    const weekday = et.weekday >= 1 && et.weekday <= 5;
    const expected = weekday && et.hour >= 16 ? et.date : prevWeekday(et.date);
    const recordFor = run.expected_session || run.session || null;
    const behind = recordFor ? weekdaysBetween(recordFor, expected) : 99;
    // pending from the close until the 8:16 PM ET retry has had time to run
    const pending = weekday && et.hour >= 16 && et.hour < PENDING_UNTIL_HOUR;
    const session = run.session || null, sessionWords = session ? dateWords(session) : 'no session';
    const base = { expected: expected, behind: behind, session: session };
    if (!recordFor || run.status === 'failed') {
      return Object.assign(base, { state: 'failed', chip: 'no verdict', tone: 'danger', sentence: 'The run did not finish; nothing below is a verdict. Check the run log.' });
    }
    if (behind >= 2) {
      return Object.assign(base, { state: 'stale2', chip: 'STALE · ' + behind + ' sessions behind', tone: 'danger', keepCase: true,
        sentence: 'The run has not published for ' + behind + ' sessions. Something is broken — check the run log; nothing below is tomorrow’s plan.' });
    }
    if (behind === 1 && pending) {
      return Object.assign(base, { state: 'pending', chip: 'tonight’s run pending', tone: 'info',
        sentence: 'Tonight’s run has not published yet. What is below is ' + sessionWords + '’s plan — do not act on it as tomorrow’s.' });
    }
    if (behind === 1) {
      return Object.assign(base, { state: 'stale1', chip: 'STALE · 1 session behind', tone: 'warn', keepCase: true,
        sentence: 'No run published for ' + dateWords(expected) + '. Either the market was closed or the run failed — check the run log. Do not place these orders.' });
    }
    if (run.session_state === 'closed') {
      return Object.assign(base, { state: 'closed', chip: 'market closed', tone: 'neutral',
        sentence: sessionWords + '’s plans stand; the market was closed on ' + dateWords(recordFor) + '.' });
    }
    if (run.status === 'degraded' || (run.problems && run.problems.length)) {
      const kinds = (run.problems || []).map((p) => p && p.kind).filter((k) => PROBLEMS[k]);
      return Object.assign(base, { state: 'degraded', chip: 'degraded · ' + dateShort(session), tone: 'warn',
        sentence: kinds.length ? kinds.map((k) => PROBLEMS[k]).join(' ') : 'The run published with a problem it did not name.', problems: kinds });
    }
    return Object.assign(base, { state: 'fresh', chip: 'fresh · ' + dateShort(session), tone: 'good', sentence: '' });
  }
  SCStock.status = status;
  SCStock.PROBLEM_SENTENCES = PROBLEMS;

  // ---------------------------------------------------------------- masthead
  function renderStatus(data, st) {
    const slot = clear($('status-slot'));
    slot.appendChild(chip(st.chip, st.tone, st.keepCase));
    const line = clear($('status-line'));
    if (!st.sentence) { line.hidden = true; return; }
    const alarm = st.state !== 'closed';
    const block = el('div', { 'class': (alarm ? 'sc-notice' : 'sc-callout sc-callout--core') + ' ss-notice', role: alarm ? 'alert' : null });
    block.appendChild(el('div', { 'class': alarm ? 'sc-eyebrow' : 'sc-callout__label', text: st.state === 'degraded' ? 'degraded' : st.state === 'closed' ? 'market closed' : st.state === 'pending' ? 'pending' : st.state === 'failed' ? 'no verdict' : 'stale' }));
    if (st.state === 'degraded') {
      (st.problems && st.problems.length ? st.problems : [null]).forEach((k) => block.appendChild(el('p', { text: k ? PROBLEMS[k] : st.sentence })));
    } else {
      const p = el('p');
      const parts = st.sentence.split('check the run log');
      p.appendChild(d.createTextNode(parts[0]));
      if (parts.length > 1) {
        p.appendChild(el('a', { href: RUNS_URL, target: '_blank', rel: 'noopener', text: 'check the run log' }));
        p.appendChild(d.createTextNode(parts[1]));
      }
      block.appendChild(p);
      if (parts.length > 1) block.appendChild(el('p', { 'class': 'ss-runlog', id: 'runlog', hidden: '' }));
    }
    line.appendChild(block);
    line.hidden = false;
  }

  // ---------------------------------------------------------------- cover
  function renderCover(data, st) {
    const run = data.run || {}, cover = data.cover || {}, app = data.app || {};
    $('cover-eyebrow').textContent = 'spicystock · ' + (run.session || '—') + ' · evening run';
    $('cover-h1').textContent = cover.h1 || 'No verdict.';
    $('cover-dek').textContent = cover.dek || '';
    const meta = clear($('cover-meta'));
    const uni = run.universe || {};
    meta.appendChild(el('span', { text: num(uni.size) + ' common stocks read' }));
    meta.appendChild(el('span', { text: num(run.bursts) + ' bursts · Bonde’s median night is ' + BONDE_MEDIAN_NIGHT }));
    meta.appendChild(el('span', { text: 'Alpaca ' + String(run.feed || '').toUpperCase() + ' daily bars' }));
    meta.appendChild(el('span', { text: 'graded by ' + (run.model || '—') }));
    meta.appendChild(el('span', { text: 'rules ' + (app.rules_version || '—') }));
    const actions = clear($('cover-actions'));
    const stale = st.state === 'stale1' || st.state === 'stale2' || st.state === 'pending' || st.state === 'failed';
    const label = stale ? 'What you hold' : (cover.action_label || 'What you hold');
    const target = stale ? '#hold' : (cover.action_target || '#hold');
    actions.appendChild(el('a', { 'class': 'sc-btn sc-btn--primary', id: 'cover-action', href: target, text: label }));
    actions.appendChild(el('button', { 'class': 'sc-btn sc-btn--secondary', type: 'button', text: 'Print', onclick: () => w.print() }));
  }

  // ---------------------------------------------------------------- run strip
  function stat(label, value, note, lead) {
    return el('div', { 'class': 'sc-stat' + (lead ? ' sc-stat--lead' : '') }, [
      el('dt', { 'class': 'sc-stat__label', text: label }),
      el('dd', { 'class': 'sc-stat__value', text: value }),
      el('dd', { 'class': 'sc-stat__note', text: note })
    ]);
  }
  function renderStrip(data) {
    const run = data.run || {}, cov = run.coverage || {}, g = run.graded || {}, reads = run.reads || {};
    const strip = clear($('run-strip'));
    strip.appendChild(stat('session', dateWords(run.session), run.session_state === 'closed' ? 'closed on ' + dateWords(run.expected_session) : 'evening run · ' + (run.status || '—')));
    strip.appendChild(stat('covered', num(cov.with_bars) + ' of ' + num(cov.requested), num(cov.measured) + ' measured · ' + num(cov.stale) + ' stale · ' + num(cov.no_bars) + ' no bar'));
    strip.appendChild(stat('bursts', num(run.bursts), 'Bonde’s median night is ' + BONDE_MEDIAN_NIGHT));
    strip.appendChild(stat('graded', num(g.a) + ' A · ' + num(g.a_plus) + ' A+', num(g.b) + ' B · ' + num(g.c) + ' C · ' + num(g.skip) + ' skip'));
    strip.appendChild(stat('claude', num(reads.done) + ' of ' + num(reads.requested) + ' read', reads.unavailable_reason ? 'unavailable: ' + words(reads.unavailable_reason) : 'chart + numbers, may only lower a grade'));
    strip.appendChild(stat('published', timeET(run.published_at), 'email ' + (run.email || '—')));
  }

  // ---------------------------------------------------------------- breadth
  function delta(now, before, unit) {
    if (!isNum(now) || !isNum(before)) return 'vs yesterday not recorded';
    const diff = now - before;
    return (diff > 0 ? '▲ ' : diff < 0 ? '▼ ' : '· ') + num(Math.abs(diff)) + ' vs yesterday' + (unit || '');
  }
  function renderBreadth(data) {
    const b = data.breadth || {}, reg = b.regime || {}, th = reg.thresholds || {}, hist = b.history || [];
    const prev = hist.length >= 2 ? hist[hist.length - 2] : {};
    const line = th.ratio_10d_yellow;
    const deck = clear($('breadth-deck'));
    deck.appendChild(stat('up 4% today', num(b.up4), delta(b.up4, prev.up4) + (isNum(b.universe) && b.universe && isNum(b.up4) ? ' · ' + (100 * b.up4 / b.universe).toFixed(1) + '% of ' + num(b.universe) : '')));
    deck.appendChild(stat('down 4% today', num(b.down4), delta(b.down4, prev.down4)));
    deck.appendChild(stat('5-day ratio', plain(b.ratio_5d), num(b.up4_5d) + ' up ÷ ' + num(b.down4_5d) + ' down, last 5 sessions'));
    deck.appendChild(stat('10-day ratio', plain(b.ratio_10d), 'Bonde’s line is ' + plain(line) + '. ' + (isNum(b.ratio_10d) && isNum(line) ? (b.ratio_10d >= line ? 'Above it.' : 'Below it.') : ''), true));

    const regime = clear($('regime'));
    const verdict = reg.verdict || 'unknown';
    const size = reg.size_multiplier;
    const sizeWords = size === 1 ? 'Full size.' : size === 0 ? 'No new longs.' : isNum(size) ? 'Size at ' + (size * 100).toFixed(0) + '%.' : '';
    regime.appendChild(el('div', { 'class': 'sc-callout__label', text: 'regime' }));
    regime.appendChild(el('div', { 'class': 'sc-callout__figure' }, [chip(verdict.toUpperCase(), REGIME_TONE[verdict] || 'neutral', true), el('span', { text: sizeWords })]));
    regime.appendChild(el('ul', null, (reg.reasons || []).map((r) => el('li', { text: r }))));

    renderRatioChart(data);

    const facts = clear($('breadth-facts'));
    const notes = {}; (b.notes || []).forEach((n) => { if (n && n.key) notes[n.key] = n.text; });
    const rules = b.rules || {};
    function factCard(title, hint, pairs, noteKey, extra) {
      const card = el('div', { 'class': 'sc-card' });
      card.appendChild(el('div', { 'class': 'sc-eyebrow', text: title }));
      card.appendChild(el('p', { 'class': 'sc-hint', text: hint }));
      card.appendChild(el('dl', { 'class': 'sc-facts' }, pairs.map((p) => el('div', null, [el('dt', { text: p[0] }), el('dd', { text: p[1] })]))));
      if (extra) card.appendChild(extra);
      if (notes[noteKey]) card.appendChild(el('p', { 'class': 'sc-note', text: 'Bonde: ' + notes[noteKey] }));
      return card;
    }
    facts.appendChild(factCard('the quarter', num(rules.quarter_sessions) + ' sessions, names moving ' + plain(rules.quarter_move_pct) + '%',
      [['up 25%', num(b.up25_quarter)], ['down 25%', num(b.down25_quarter)]], 'down25_quarter',
      reg.oversold_extreme ? el('p', { 'class': 'sc-hint' }, [chip('oversold extreme', 'info'), ' down-25% count under the scaled ' + plain(th.down25_quarter_oversold)]) : null));
    facts.appendChild(factCard('the month', num(rules.month_sessions) + ' sessions, names moving ' + plain(rules.month_move_pct) + '% and ' + plain(rules.month_big_move_pct) + '%',
      [['up 25%', num(b.up25_month)], ['down 25%', num(b.down25_month)], ['up 50%', num(b.up50_month)], ['down 50%', num(b.down50_month)]], 'up50_month'));
    facts.appendChild(factCard('above the ' + plain(rules.ma_sessions) + '-day average', 'T2108, the share of stocks above it',
      [['above', isNum(b.pct_above_40ma) ? b.pct_above_40ma.toFixed(1) + '%' : '—'], ['measured over', num(b.universe) + ' stocks']], 'pct_above_40ma'));
  }

  // The 10-day ratio over the last 30 sessions: one series in the emphasis
  // tone, a dashed reference at the archived yellow line, a tooltip, and a
  // table twin. The viewBox is the measured width so text stays 10.5px.
  function renderRatioChart(data) {
    const b = data.breadth || {}, hist = (b.history || []).filter((h) => h && isNum(h.ratio_10d)), th = (b.regime || {}).thresholds || {};
    const line = th.ratio_10d_yellow, redLine = th.ratio_10d_red;
    const fig = clear($('ratio-chart'));
    const above = isNum(line) ? hist.filter((h) => h.ratio_10d >= line).length : null;
    const lo = hist.length ? Math.min.apply(null, hist.map((h) => h.ratio_10d)) : 0, hi = hist.length ? Math.max.apply(null, hist.map((h) => h.ratio_10d)) : 1;
    fig.appendChild(el('div', { 'class': 'sc-card__head' }, [
      el('div', null, [el('h3', { text: '10-day ratio, last ' + hist.length + ' sessions' }),
        el('p', { 'class': 'sc-hint', text: 'up 4% ÷ down 4% over ten sessions; ' + (above === null ? '' : 'above ' + plain(line) + ' on ' + above + ' of ' + hist.length + '.') })]),
      chip('one series', 'neutral')
    ]));
    const label = hist.length ? '10-day ratio over the last ' + hist.length + ' sessions, ' + lo.toFixed(2) + ' to ' + hi.toFixed(2) + (above === null ? '' : ', above ' + plain(line) + ' on ' + above + ' of ' + hist.length) + '. Arrow keys step the sessions; the table below lists the same numbers.' : 'No breadth history in this record.';
    const host = el('div', { 'class': 'sc-chart', role: 'group', tabindex: '0', 'aria-label': label });
    const stage = el('div', { 'class': 'sc-chart__stage', style: 'position:relative' });
    host.appendChild(stage);
    fig.appendChild(host);
    if (!hist.length) { stage.appendChild(empty((b.history || []).length ? 'No 10-day ratio yet: no name broke down 4% in the last ten sessions, so the ratio has no denominator.' : 'No breadth history in this record.')); return; }
    const tip = SC().tooltip(stage, { live: true, top: 6, flip: 0.55, offsetX: 14 });
    const state = { node: null, index: null, g: null };
    function geometry(W) {
      const H = 200, plot = { left: 40, right: W - 12, top: 14, bottom: H - 26 };
      let dlo = Math.min(lo, isNum(line) ? line : lo, isNum(redLine) ? redLine : lo), dhi = Math.max(hi, isNum(line) ? line : hi);
      const span = dhi - dlo || 1; dlo = Math.max(0, dlo - span * 0.15); dhi = dhi + span * 0.15;
      const tk = SC().ticks(dlo, dhi, 4);
      const x = (i) => Math.round((plot.left + (hist.length === 1 ? (plot.right - plot.left) / 2 : i / (hist.length - 1) * (plot.right - plot.left))) * 10) / 10;
      const y = (v) => Math.round((plot.bottom - (v - dlo) / (dhi - dlo) * (plot.bottom - plot.top)) * 10) / 10;
      return { W, H, plot, x, y, ticks: tk.ticks.filter((t) => t >= dlo && t <= dhi) };
    }
    function draw() {
      const W = Math.max(280, host.clientWidth || 640), g = geometry(W);
      state.g = g;
      const s = svg('svg', { viewBox: '0 0 ' + g.W + ' ' + g.H, width: g.W, height: g.H, 'aria-hidden': 'true', focusable: 'false' });
      g.ticks.forEach((t) => {
        s.appendChild(svg('line', { 'class': 'sc-chart__grid', x1: g.plot.left, x2: g.plot.right, y1: g.y(t), y2: g.y(t) }));
        s.appendChild(svg('text', { x: g.plot.left - 6, y: g.y(t) + 4, 'text-anchor': 'end' }, plain(t)));
      });
      if (isNum(line)) {
        s.appendChild(svg('line', { 'class': 'ss-ref', 'data-ref': 'yellow', x1: g.plot.left, x2: g.plot.right, y1: g.y(line), y2: g.y(line) }));
        s.appendChild(svg('text', { 'class': 'ss-ref-label', x: g.plot.right - 2, y: g.y(line) - 5, 'text-anchor': 'end' }, plain(line) + ' · Bonde’s line'));
      }
      let path = '';
      hist.forEach((h, i) => { path += (i ? 'L' : 'M') + g.x(i) + ',' + g.y(h.ratio_10d); });
      s.appendChild(svg('path', { 'class': 'sc-chart__series sc-chart__series--emphasis', d: path }));
      const marks = svg('g', { 'class': 'sc-chart__marker', style: '--sc-tone:var(--sc-chart-emphasis)' });
      hist.forEach((h, i) => marks.appendChild(svg('circle', { cx: g.x(i), cy: g.y(h.ratio_10d), r: i === hist.length - 1 ? 5 : 3.5 })));
      s.appendChild(marks);
      // x axis: first, middle, last session
      [0, Math.floor((hist.length - 1) / 2), hist.length - 1].forEach((i, k) => {
        s.appendChild(svg('text', { x: g.x(i), y: g.H - 8, 'text-anchor': k === 0 ? 'start' : k === 1 ? 'middle' : 'end' }, dateShort(hist[i].date)));
      });
      const cross = svg('g', { 'class': 'sc-chart__cross', visibility: 'hidden' }, [
        svg('line', { 'class': 'sc-chart__crosshair', x1: 0, x2: 0, y1: g.plot.top, y2: g.plot.bottom }),
        svg('circle', { 'class': 'sc-chart__marker', style: '--sc-tone:var(--sc-chart-emphasis)', r: 5, cx: 0, cy: 0 })
      ]);
      s.appendChild(cross);
      const hit = svg('rect', { 'class': 'sc-chart__hit', x: g.plot.left, y: g.plot.top, width: g.plot.right - g.plot.left, height: g.plot.bottom - g.plot.top });
      s.appendChild(hit);
      hit.addEventListener('pointermove', (e) => { const r = s.getBoundingClientRect(); const px = (e.clientX - r.left) * (g.W / (r.width || g.W)); focus(Math.round((px - g.plot.left) / ((g.plot.right - g.plot.left) / Math.max(1, hist.length - 1)))); });
      hit.addEventListener('pointerleave', () => clearFocus());
      if (state.node) stage.replaceChild(s, state.node); else stage.insertBefore(s, tip.node);
      state.node = s;
      if (state.index !== null) focus(state.index);
    }
    function focus(i) {
      i = Math.max(0, Math.min(hist.length - 1, i)); state.index = i;
      const h = hist[i], g = state.g, cross = state.node.querySelector('.sc-chart__cross');
      const cx = g.x(i), cy = g.y(h.ratio_10d), l = cross.querySelector('line'), c = cross.querySelector('circle');
      l.setAttribute('x1', cx); l.setAttribute('x2', cx); c.setAttribute('cx', cx); c.setAttribute('cy', cy);
      cross.setAttribute('visibility', 'visible');
      tip.show({ title: dateWords(h.date) + ' ' + h.date, rows: [
        { value: plain(h.ratio_10d), label: '10-day ratio', tone: 'chart-emphasis' },
        { value: num(h.up4), label: 'up 4%', tone: 'chart-context' },
        { value: num(h.down4), label: 'down 4%', tone: 'chart-context' }
      ], meta: isNum(line) ? (h.ratio_10d >= line ? 'at or above Bonde’s line' : 'below Bonde’s line') : '' }, { px: cx, py: 0 });
    }
    function clearFocus() { state.index = null; const cross = state.node && state.node.querySelector('.sc-chart__cross'); if (cross) cross.setAttribute('visibility', 'hidden'); tip.hide(); }
    host.addEventListener('keydown', (e) => {
      const start = state.index === null ? hist.length - 1 : state.index;
      if (e.key === 'ArrowLeft') focus(state.index === null ? start : start - 1);
      else if (e.key === 'ArrowRight') focus(state.index === null ? start : start + 1);
      else if (e.key === 'Home') focus(0); else if (e.key === 'End') focus(hist.length - 1);
      else if (e.key === 'Escape') clearFocus(); else return;
      e.preventDefault();
    });
    host.addEventListener('blur', clearFocus);
    draw();
    if (w.ResizeObserver) new w.ResizeObserver(() => { const W = Math.max(280, host.clientWidth || 640); if (state.g && Math.abs(W - state.g.W) >= 4) draw(); }).observe(host);
    const twin = el('div');
    SC().tableTwin(twin, { caption: '10-day ratio by session, oldest first', summary: 'table view · ' + hist.length + ' sessions',
      head: ['session', 'up 4%', 'down 4%', '10-day ratio'], rows: hist.map((h) => [h.date, num(h.up4), num(h.down4), plain(h.ratio_10d)]) });
    fig.appendChild(twin.firstChild);
    const ratioNote = (b.notes || []).find((n) => n && n.key === 'ratio_10d');
    fig.appendChild(el('figcaption', { 'class': 'sc-chart-caption' }, [
      el('p', { text: 'Counts over ' + num(b.universe) + ' common stocks with a bar on ' + dateWords(b.date) + '; ratio = Σ up 4% ÷ Σ down 4% over ' + plain((b.rules || {}).ratio_long_sessions) + ' sessions. The dashed line is the archived yellow threshold.' + (ratioNote ? ' Bonde: ' + ratioNote.text + '.' : '') })
    ]));
  }

  // ---------------------------------------------------------------- tomorrow
  function ticket(o) {
    // Fidelity's field order: Action · Quantity · Symbol · Order type · Stop
    // price · Limit price · Time in force; then the conditional leg.
    if (!o) return null;
    const type = words(o.order_type || '').toUpperCase(), tif = String(o.time_in_force || '').toUpperCase();
    const parts = [type];
    if (isNum(o.stop_price)) parts.push('stop ' + usd(o.stop_price));
    if (isNum(o.limit_price)) parts.push('limit ' + usd(o.limit_price));
    parts.push(tif);
    const lines = [String(o.action || '').toUpperCase() + ' ' + num(o.quantity) + ' ' + (o.symbol || ''), parts.join(' · ')];
    if (o.then) {
      const t = o.then, cond = o.conditional === 'one_triggers_the_other' ? 'OTO' : words(o.conditional || '').toUpperCase();
      const tp = [words(t.order_type || '').toUpperCase()];
      if (isNum(t.stop_price)) tp.push('stop ' + usd(t.stop_price));
      if (isNum(t.limit_price)) tp.push('limit ' + usd(t.limit_price));
      tp.push(String(t.time_in_force || '').toUpperCase());
      lines.push('then ' + cond + ' → ' + String(t.action || '').toUpperCase() + ' ' + num(t.quantity) + ' ' + (o.symbol || '') + ' · ' + tp.join(' · '));
    }
    return lines;
  }
  function copyButton(getText, pre) {
    const btn = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', text: 'Copy', 'data-copy': '' });
    btn.addEventListener('click', () => {
      const text = getText();
      const done = () => { btn.textContent = 'Copied'; setTimeout(() => { btn.textContent = 'Copy'; }, 1600); };
      const fallback = () => {
        try { const range = d.createRange(); range.selectNodeContents(pre); const sel = w.getSelection(); sel.removeAllRanges(); sel.addRange(range); btn.textContent = 'Selected — press Ctrl/Cmd+C'; setTimeout(() => { btn.textContent = 'Copy'; }, 2400); } catch (e) { /* nothing to do */ }
      };
      if (w.navigator && w.navigator.clipboard && w.navigator.clipboard.writeText) w.navigator.clipboard.writeText(text).then(done, fallback);
      else fallback();
    });
    return btn;
  }
  function orderBlock(plan, extraHint, withheld) {
    const lines = withheld ? null : ticket(plan.order_json);
    const wrap = el('div', { 'class': 'ss-order' });
    if (!lines) { wrap.appendChild(el('p', { 'class': 'sc-hint', text: extraHint || 'No order.' })); return wrap; }
    const pre = el('pre', { 'class': 'ss-order__pre', 'data-order': '' });
    lines.forEach((line, i) => { if (i) pre.appendChild(d.createTextNode('\n')); pre.appendChild(el('span', { text: line })); });
    wrap.appendChild(el('div', { 'class': 'ss-order__head' }, [el('span', { 'class': 'sc-eyebrow', style: 'margin:0', text: 'the order, in Fidelity’s field order' }), copyButton(() => pre.textContent, pre)]));
    wrap.appendChild(pre);
    if (plan.order_line) wrap.appendChild(el('p', { 'class': 'ss-order__readback', text: 'Read it back: ' + plan.order_line }));
    if (plan.fallback_line) wrap.appendChild(el('p', { 'class': 'sc-hint', text: plan.fallback_line }));
    return wrap;
  }
  function stopWords(plan) {
    const basis = STOP_BASIS[plan.stop_basis] || (plan.stop_basis === 'max_stop' ? plain(plan.stop_pct) + '% under the close (the bar does not support it)' : words(plan.stop_basis));
    return usd(plan.stop) + ' · ' + basis;
  }
  function chartOptions(b, series, account) {
    const plan = b.plan || {}, q = b.quality || {}, base = q.base || {}, checks = by(q.checks || [], 'key');
    const check = {}; (q.checks || []).forEach((c) => { if (c && c.key) check[c.key] = c; });
    const idx = (date) => series.findIndex((x) => x && x.date === date);
    let box = null;
    if (base.start && base.end && isNum(base.low) && isNum(base.high)) {
      let bs = idx(base.start), be = idx(base.end);
      if (be >= 0) { if (bs < 0) bs = 0; box = { start: bs, end: be, low: base.low, high: base.high, depthPct: base.depth_pct }; }
    }
    const up = check.two_days && check.two_days.values ? check.two_days.values.up_run : null;
    const rng = check.range_expansion ? check.range_expansion.value : null;
    return {
      ticker: b.ticker, card: true, compact: true, futureSlots: 6, targetRuler: true, ma: [], volumeAvg: 20,
      burstIndex: series.length - 1, box: box,
      stop: plan.stop, entryLow: plan.entry_low, entryHigh: plan.entry_high,
      targetLow: plan.targets ? plan.targets.low : null, targetHigh: plan.targets ? plan.targets.high : null, targetRef: plan.planned_entry,
      upDays: isNum(up) ? up : 0, breakdownIndexes: (base.breakdown_dates || []).map(idx).filter((i) => i >= 0),
      burstVolumeRatio: b.volume_vs_prior, rangeExpansion: isNum(rng) ? rng : null,
      ariaLabel: b.summary || null, height: (w.innerWidth || 1280) < 480 ? 250 : 300
    };
  }
  SCStock.chartOptions = chartOptions;
  function mountChart(mount, b, n, account) {
    const series = (b.series || []).slice(-n);
    clear(mount);
    if (!series.length) { mount.appendChild(el('div', { 'class': 'sc-empty sc-empty--inline', text: 'No bars archived for this name; the grade stands on the numbers beside it.' })); return; }
    const host = SCStock.chart(series, chartOptions(b, series, account));
    host.setAttribute('data-sessions', String(series.length));
    host.setAttribute('data-ticker', b.ticker);
    mount.appendChild(host);
  }
  function tradeCard(b, data, state) {
    const plan = b.plan || {}, q = b.quality || {}, acct = data.account || {}, rules = (data.rules || {}).plan || {};
    const beyond = (data.beyond_cap || []).indexOf(b.ticker) >= 0 || !plan.order_json;
    const card = el('article', { 'class': 'sc-card ss-trade', id: 'trade-' + b.ticker, 'data-ticker': b.ticker });
    const grade = el('div', { 'class': 'ss-trade__grade' }, [chip((b.grade || '—') + (isNum(b.score) ? ' · ' + b.score.toFixed(1) : ''), 'brand', true)]);
    if (beyond) grade.appendChild(chip('beyond the slot cap', 'neutral'));
    (b.flags || []).forEach((f) => grade.appendChild(chip(FLAG_WORDS[f] || words(f), 'warn')));
    card.appendChild(el('div', { 'class': 'sc-card__head' }, [
      el('div', null, [el('h3', { 'class': 'sc-case', text: b.ticker }),
        el('p', { 'class': 'sc-hint', text: (b.name || b.ticker) + ' · ' + usd(b.close) + ' · ' + pct(b.gain_pct) + ' on ' + (isNum(b.volume_vs_prior) ? b.volume_vs_prior.toFixed(1) : '—') + '× volume' + (b.scan && b.scan !== 'burst' ? ' · ' + words(b.scan) + ' scan' : '') })]),
      grade
    ]));
    // the chart, 60 sessions on the card, 120 on request
    const chartWrap = el('div', { 'class': 'ss-trade__chart' });
    const mount = el('div', { 'class': 'ss-trade__chart-mount' });
    chartWrap.appendChild(mount);
    const tabs = el('div', { 'class': 'sc-tabs', role: 'group', 'aria-label': 'Sessions shown' });
    [60, 120].forEach((n) => {
      const t = el('button', { 'class': 'sc-tab', type: 'button', 'aria-pressed': n === 60 ? 'true' : 'false', text: n + ' sessions', 'data-sessions': String(n) });
      t.addEventListener('click', () => { tabs.querySelectorAll('.sc-tab').forEach((x) => x.setAttribute('aria-pressed', x === t ? 'true' : 'false')); mountChart(mount, b, n, acct); });
      tabs.appendChild(t);
    });
    const captionKids = [el('p', { text: 'Alpaca SIP daily bars through ' + dateWords(b.series && b.series.length ? b.series[b.series.length - 1].date : data.run.session) + ' · drawn from the same numbers as the plan below.' + (b.chart ? ' ' : '') }, b.chart ? [el('a', { 'class': 'sc-link--quiet', href: b.chart, text: 'the chart the grader saw' })] : null), tabs];
    chartWrap.appendChild(el('figcaption', { 'class': 'sc-chart-caption' }, captionKids));
    card.appendChild(chartWrap);
    mountChart(mount, b, 60, acct);

    // the plan facts and the order, beside the exits and the read
    const facts = el('dl', { 'class': 'sc-facts' });
    const fact = (dt, dd, sub, wide) => facts.appendChild(el('div', { 'class': wide ? 'is-wide' : null }, [el('dt', { text: dt }), el('dd', null, [dd, sub ? el('small', { text: sub }) : null])]));
    if (plan.entry_low !== undefined) {
      fact('buy', usd(plan.entry_low) + ' – ' + usd(plan.entry_high), plan.entry_window || '', true);
      fact('skip if it opens above', usd(plan.skip_if_open_above), 'the gap ate the trade', false);
      fact('skip if it opens below', usd(plan.skip_if_open_below), 'the burst is failing', false);
      fact('stop', stopWords(plan), 'move it to your entry day’s low once filled', true);
      fact('risk per share', usd(plan.risk_per_share), null, false);
      fact('shares', num(plan.shares), plan.capped_by === 'position_cap' ? 'cut by the position cap' : 'from ' + usd(plan.risk_usd) + ' ÷ ' + usd(plan.risk_per_share), false);
      fact('position', usd(plan.position_usd), (isNum(plan.position_pct) ? plan.position_pct.toFixed(1) : '—') + '% of ' + usd(acct.equity, 0), false);
      fact('at risk', usd(plan.risk_usd), plain(acct.risk_pct) + '% of equity', false);
      const t = plan.targets || {};
      fact('aim', '+' + plain(t.low_pct) + '% to +' + plain(t.high_pct) + '% by day ' + plain(rules.final_exit_day), usd(t.low) + ' – ' + usd(t.high) + (t.note ? ' · ' + t.note : ''), true);
    }
    if ((plan.flags && plan.flags.length) || (plan.notes && plan.notes.length)) {
      const hz = el('div', { 'class': 'is-wide' }, [el('dt', { text: 'hazards' })]);
      const dd = el('dd');
      if (plan.flags && plan.flags.length) dd.appendChild(el('div', { 'class': 'ss-hazards' }, plan.flags.map((f) => chip(FLAG_WORDS[f] || words(f), 'warn'))));
      if (plan.notes && plan.notes.length) dd.appendChild(el('ul', { 'class': 'ss-notes' }, plan.notes.map((n) => el('li', { text: n }))));
      hz.appendChild(dd); facts.appendChild(hz);
    }
    const left = el('div', null, [facts]);
    const cut = (data.cash_budget && data.cash_budget.cut || []).filter((c) => c && c.ticker === b.ticker).map((c) => c.reason).join(' ');
    left.appendChild(orderBlock(plan, beyond ? 'No order tonight: ' + (cut || 'beyond the slot cap.') : 'No order line was written for this plan.', beyond));
    const right = el('div');
    const sched = plan.exit_schedule || [];
    if (sched.length) {
      right.appendChild(el('div', { 'class': 'sc-eyebrow', text: 'the exits, dated' }));
      right.appendChild(el('ol', { 'class': 'sc-timeline' }, sched.map((s) => el('li', { 'class': 'sc-timeline__item' }, [
        el('div', { 'class': 'sc-timeline__stamp', text: dateWords(s.date) + ' · day ' + plain(s.day) }),
        el('div', { 'class': 'sc-timeline__body' }, [el('p', { text: cap(s.instruction || '') })])
      ]))));
    }
    const c = b.claude;
    if (c && c.source === 'claude') {
      right.appendChild(el('div', { 'class': 'sc-insight' }, [
        el('div', { 'class': 'sc-eyebrow', text: 'claude read the chart' + (c.agree === false ? ' · lowered the grade' : '') }),
        el('p', { text: c.reason || '' }),
        c.key_risk ? el('p', null, [el('strong', { text: 'Key risk: ' }), c.key_risk]) : null,
        c.entry_note ? el('p', null, [el('strong', { text: 'At the open: ' }), c.entry_note]) : null
      ]));
    } else {
      right.appendChild(el('p', { 'class': 'sc-hint ss-trade__nomodel', text: 'Graded by the checklist alone; the model did not answer.' }));
    }
    card.appendChild(el('div', { 'class': 'sc-split ss-trade__body' }, [left, right]));
    const checks = q.checks || [], passes = checks.filter((x) => x && x.pass).length, miss = checks.find((x) => x && !x.pass);
    const footText = passes + ' of ' + checks.length + ' checks pass (' + plain(q.passes) + ' of the ' + plain(q.of) + ' letters)' + (miss ? ' · the miss is ‘' + (miss.label || words(miss.key) || 'a check') + '’ (' + (miss.display || '—') + ')' : ' · nothing missed') + (q.vetoes && q.vetoes.length ? ' · veto: ' + q.vetoes.map((v) => VETO_WORDS[v] || words(v)).join(', ') : '');
    card.appendChild(el('div', { 'class': 'ss-trade__foot' }, [el('span', { 'class': 'sc-hint', text: footText }), el('a', { 'class': 'sc-link--quiet', href: '#burst-' + b.ticker, 'data-matrix-link': '', text: 'row in the matrix ↓' })]));
    return card;
  }
  function planRow(p, red, holdDays) {
    const st = PLAN_STATUS[p.status] || [words(String(p.status || '—')).toUpperCase(), 'neutral'];
    const row = el('article', { 'class': 'ss-plan', 'data-ticker': p.ticker, 'data-status': p.status || '' });
    row.appendChild(el('div', { 'class': 'ss-plan__row' }, [
      el('strong', { 'class': 'sc-case', text: p.ticker }), chip(st[0], st[1], true),
      el('span', { 'class': 'ss-plan__meta', text: 'day ' + plain(p.day) + (isNum(holdDays) ? ' of ' + plain(holdDays) : '') + ' · picked ' + dateMD(p.picked) + ' · ' + num(p.shares) + ' sh' })
    ]));
    const t = p.targets || {}, stop = isNum(p.current_stop) ? p.current_stop : p.stop, aim = isNum(t.high) ? t.high : null;
    // the bar runs from the stop to the aim; the entry marker is drawn only
    // while the entry still sits above the stop (a trailed stop can pass it)
    if (isNum(p.last_close) && isNum(stop) && aim !== null && aim > stop && isNum(t.low) && isNum(p.entry_ref)) {
      const pos = (v) => Math.max(0, Math.min(100, 100 * (v - stop) / (aim - stop)));
      const entryAbove = p.entry_ref > stop;
      const fig = el('figure', { 'class': 'sc-benchmark', style: '--sc-benchmark-position:' + pos(p.last_close).toFixed(1) + '%;' + (entryAbove ? '--sc-benchmark-reference:' + pos(p.entry_ref).toFixed(1) + '%;' : '') + '--sc-benchmark-band-start:' + pos(t.low).toFixed(1) + '%;--sc-benchmark-band-end:' + pos(t.high).toFixed(1) + '%' });
      fig.appendChild(el('figcaption', { 'class': 'sc-benchmark__head' }, [el('span', { 'class': 'sc-benchmark__label', text: 'last close · ' + dateShort(p.last_date) }), el('strong', { 'class': 'sc-benchmark__value', text: usd(p.last_close) })]));
      fig.appendChild(el('div', { 'class': 'sc-benchmark__track', 'aria-hidden': 'true' }, [el('span', { 'class': 'sc-benchmark__band' }), entryAbove ? el('span', { 'class': 'sc-benchmark__reference' }) : null, el('span', { 'class': 'sc-benchmark__point' })]));
      const scale = [['stop', stop], ['entry', p.entry_ref], ['aim', aim]].sort((a, b) => a[1] - b[1]);
      fig.appendChild(el('div', { 'class': 'sc-benchmark__scale', 'aria-hidden': 'true' }, scale.map((s) => el('span', { text: s[0] + ' ' + usd(s[1]) }))));
      fig.appendChild(el('p', { 'class': 'sc-benchmark__note', text: pct(p.unrealised_pct, 2) + ' from the ' + usd(p.entry_ref) + ' entry · band ' + usd(t.low) + '–' + usd(t.high) + ' · stop ' + usd(stop) + (entryAbove ? '' : ' (the stop has been trailed above the entry)') }));
      row.appendChild(fig);
    }
    row.appendChild(el('p', { 'class': 'sc-note ss-plan__instruction', text: p.instruction || '' }));
    return row;
  }
  function renderTomorrow(data, st) {
    const bursts = by(data.bursts || [], 'ticker'), trades = (data.trades || []).map((t) => bursts[t]).filter(Boolean);
    const beyond = (data.beyond_cap || []).map((t) => bursts[t]).filter((b) => b && b.plan);
    const main = clear($('trades'));
    const regime = ((data.breadth || {}).regime || {}).verdict;
    const rules = data.rules || {}, holdDays = (rules.plan || {}).final_exit_day, window = (rules.record || {}).open_plan_sessions;
    const lede = $('tomorrow-lede');
    const more = beyond.length ? ' ' + beyond.length + ' more A-quality burst' + (beyond.length === 1 ? ' is' : 's are') + ' cut by the slots or the equity and follow' + (beyond.length === 1 ? 's' : '') + ' with no order.' : '';
    if (st.state === 'closed') lede.textContent = 'The market was closed; nothing new was planned. What you hold is on the right, unchanged.';
    else if (regime === 'red') lede.textContent = 'Breadth is red: no new longs. What you hold is the only work.';
    else if (!trades.length) lede.textContent = 'No burst reached A-quality with an order tonight. What you hold is the only work; the closest miss is under the scan.' + more;
    else lede.textContent = trades.length + ' A-quality burst' + (trades.length === 1 ? '' : 's') + ' with ' + (trades.length === 1 ? 'its' : 'their') + ' plans, ranked. Read the chart first; the order block is in Fidelity’s field order.' + more;
    if (!trades.length && !beyond.length) main.appendChild(el('div', { 'class': 'sc-card' }, [empty(st.state === 'closed' ? 'Market closed. Plans unchanged; nothing new to place.' : regime === 'red' ? 'Stand aside. Breadth is red and no new long is offered.' : 'Nothing qualifies. Keep cash; every burst the scan found is in the table below.')]));
    trades.concat(beyond).forEach((b) => main.appendChild(tradeCard(b, data, st)));

    const hold = clear($('hold-rows'));
    const plans = data.open_plans || [];
    const hint = $('hold-hint');
    if (hint) hint.textContent = 'Every pick from the last ' + (isNum(window) ? plain(window) : 'five') + ' sessions, judged from bars alone. If you never bought it, ignore its row.';
    if (!plans.length) hold.appendChild(empty('No open plans. Nothing was picked in the last ' + (isNum(window) ? plain(window) : 'five') + ' sessions.'));
    plans.forEach((p) => hold.appendChild(planRow(p, regime === 'red', holdDays)));

    const cb = data.cash_budget || {}, acct = data.account || {};
    const budget = clear($('budget'));
    budget.appendChild(el('strong', { text: 'Tomorrow’s orders commit ' + usd(cb.committed_usd, 0) + ' of ' + usd(acct.equity, 0) + ' · ' + plain(cb.slots_used) + ' of ' + plain(cb.slots_max) + ' slots' }));
    if (isNum(cb.at_risk_usd)) budget.appendChild(d.createTextNode(' · ' + usd(cb.at_risk_usd, 0) + ' at risk'));
    (cb.cut || []).forEach((c) => budget.appendChild(el('span', { 'class': 'sc-note', text: 'Cut: ' + c.ticker + ' — ' + c.reason })));

    const sheet = clear($('orders-table'));
    const withOrders = trades.filter((b) => b.plan && b.plan.order_json);
    const table = el('table', { 'class': 'sc-table sc-table--compact', id: 'order-sheet' });
    table.appendChild(el('caption', { 'class': 'sc-sr-only', text: 'Tomorrow’s orders in Fidelity’s field order' }));
    table.appendChild(el('thead', null, el('tr', null, ['symbol', 'action', 'shares', 'type', 'stop (trigger)', 'limit', 'tif', 'then OTO sell stop', 'skip above', 'at risk'].map((h, i) => el('th', { scope: 'col', 'class': i >= 2 && i !== 3 && i !== 6 ? 'sc-num' : null, text: h })))));
    const body = el('tbody');
    withOrders.forEach((b) => {
      const o = b.plan.order_json, t = o.then || {};
      body.appendChild(el('tr', { 'data-ticker': b.ticker }, [
        el('th', { scope: 'row', 'class': 'sc-case', text: b.ticker }), el('td', { text: String(o.action || '').toUpperCase() }),
        el('td', { 'class': 'sc-num', text: num(o.quantity) }), el('td', { text: words(o.order_type || '').toUpperCase() }),
        el('td', { 'class': 'sc-num', text: usd(o.stop_price) }), el('td', { 'class': 'sc-num', text: usd(o.limit_price) }),
        el('td', { text: String(o.time_in_force || '').toUpperCase() }), el('td', { 'class': 'sc-num', text: usd(t.stop_price) + ' ' + String(t.time_in_force || '').toUpperCase() }),
        el('td', { 'class': 'sc-num', text: usd(b.plan.skip_if_open_above) }), el('td', { 'class': 'sc-num', text: usd(b.plan.risk_usd) })
      ]));
    });
    if (!withOrders.length) body.appendChild(el('tr', { 'class': 'sc-empty' }, el('td', { colspan: '10', text: st.state === 'closed' ? 'No orders: the market was closed and the plans stand.' : regime === 'red' ? 'No orders: breadth is red.' : 'No orders tomorrow.' })));
    table.appendChild(body);
    const committed = withOrders.reduce((a, b) => a + (b.plan.position_usd || 0), 0), risk = withOrders.reduce((a, b) => a + (b.plan.risk_usd || 0), 0);
    table.appendChild(el('tfoot', null, el('tr', null, el('td', { colspan: '10', text: withOrders.length + ' order' + (withOrders.length === 1 ? '' : 's') + ' · ' + usd(committed, 0) + ' committed · ' + usd(risk, 0) + ' at risk · ' + (isNum(acct.equity) && acct.equity ? (100 * committed / acct.equity).toFixed(1) : '—') + '% of equity' }))));
    sheet.appendChild(table);
    const notes = acct.notes || [];
    if (notes.length) sheet.appendChild(el('details', { 'class': 'sc-details' }, [el('summary', { text: 'the sizing rules this sheet follows' }), el('ul', { 'class': 'ss-notes' }, notes.map((n) => el('li', { text: n })))]));
  }

  // ---------------------------------------------------------------- alerts
  function renderAlerts(data) {
    const wl = data.watchlist || {}, top = wl.top || [], also = wl.also_quiet || [];
    $('alerts-lede').textContent = wl.instruction || 'Quiet, coiled names inside established momentum.';
    const body = clear($('alerts-body'));
    if (!top.length) { body.appendChild(empty('No coiled names tonight.' + (isNum((wl.counts || {}).coiled) ? ' The anticipation scans found ' + num(wl.counts.coiled) + ' quiet stocks inside momentum.' : ''))); }
    else {
      const table = el('table', { 'class': 'sc-table sc-table--compact', id: 'alerts-table' });
      table.appendChild(el('caption', { 'class': 'sc-sr-only', text: 'Anticipation watchlist with a buy-stop plan per name' }));
      table.appendChild(el('thead', null, el('tr', null, ['ticker', 'setups', 'box', 'close', 'trigger', 'limit', 'stop', 'shares', 'risk', 'the ticket'].map((h, i) => el('th', { scope: 'col', 'class': i >= 3 && i <= 8 ? 'sc-num' : null, text: h })))));
      const tb = el('tbody');
      top.forEach((r) => {
        const p = r.plan || {}, box = r.box || {};
        tb.appendChild(el('tr', { 'data-ticker': r.ticker }, [
          el('th', { scope: 'row' }, [el('span', { 'class': 'sc-figure', text: r.ticker }), el('span', { 'class': 'sc-note', text: (r.name || '') + ' · ' + plain(r.quiet_days) + ' quiet days · ' + plain(r.range_pct) + '% range' })]),
          el('td', null, (r.setups || []).map((s) => chip(s, 'neutral', true))),
          el('td', { text: plain(box.sessions) + ' sessions · ' + usd(box.low) + '–' + usd(box.high) }),
          el('td', { 'class': 'sc-num', text: usd(r.close) }), el('td', { 'class': 'sc-num', text: usd(p.trigger) }), el('td', { 'class': 'sc-num', text: usd(p.limit) }),
          el('td', { 'class': 'sc-num', text: usd(p.stop) }), el('td', { 'class': 'sc-num', text: p.eligible === false ? '—' : num(p.shares) }),
          el('td', { 'class': 'sc-num', text: plain(p.stop_pct) + '%' + (isNum(p.risk_usd) && p.eligible !== false ? ' · ' + usd(p.risk_usd, 0) : '') }),
          el('td', { 'class': 'ss-ticket' }, p.eligible === false ? [chip('refused', 'danger'), ' ', el('span', { 'class': 'sc-note', text: p.reason || '' })] : p.order_line ? [el('span', { text: p.order_line })] : [chip('no order', 'neutral'), ' ', el('span', { 'class': 'sc-note', text: p.action === 'no_new_longs' ? 'breadth sizes new positions at zero tonight; keep the alert, place nothing' : (p.reason || 'the size came to zero shares') })])
        ]));
      });
      table.appendChild(tb);
      body.appendChild(el('div', { 'class': 'sc-table-scroll' }, table));
      const gap = top.map((r) => r.plan && r.plan.gap_rule).find(Boolean);
      if (gap) body.appendChild(el('p', { 'class': 'sc-hint', text: 'Gap rule, from the plan: ' + gap }));
    }
    if (also.length) {
      const det = el('details', { 'class': 'sc-details', id: 'also-quiet' });
      det.appendChild(el('summary', { text: 'also quiet · ' + also.length + ' more, no ticket' }));
      const t = el('table', { 'class': 'sc-table sc-table--compact' });
      t.appendChild(el('thead', null, el('tr', null, ['ticker', 'setups', 'close', 'quiet days', 'range'].map((h, i) => el('th', { scope: 'col', 'class': i >= 2 ? 'sc-num' : null, text: h })))));
      t.appendChild(el('tbody', null, also.map((r) => el('tr', null, [el('th', { scope: 'row', text: r.ticker }), el('td', null, (r.setups || []).map((s) => chip(s, 'neutral', true))), el('td', { 'class': 'sc-num', text: usd(r.close) }), el('td', { 'class': 'sc-num', text: plain(r.quiet_days) }), el('td', { 'class': 'sc-num', text: plain(r.range_pct) + '%' })]))));
      det.appendChild(el('div', { 'class': 'sc-table-scroll' }, t));
      body.appendChild(det);
    }
  }

  // ---------------------------------------------------------------- the scan
  function signalCell(c, vetoed) {
    const tone = vetoed ? 'blocked' : !c ? null : c.pass ? (c.marginal ? 'caution' : 'good') : 'blocked';
    const glyph = vetoed ? '✕' : !c ? '—' : c.pass ? (c.marginal ? '~' : '✓') : '✕';
    const word = vetoed ? 'veto' : !c ? 'not measured' : c.pass ? (c.marginal ? 'partial' : 'pass') : 'fail';
    // the tile carries the verdict and the primary measurement; the full
    // display, his threshold and the note sit on the tile's title
    const primary = c ? String(c.display || '').split(' ')[0] : '';
    const threshold = c ? String(c.threshold || '') : '';
    const cell = el('span', { 'class': 'sc-signal' + (tone ? ' sc-signal--' + tone : ''), title: c ? [c.display, threshold ? 'threshold: ' + threshold : '', c.note].filter(Boolean).join('\n') : null }, [
      el('span', { 'class': 'sc-signal__glyph', 'aria-hidden': 'true', text: glyph }),
      el('span', { 'class': 'sc-signal__label', text: word + (primary ? ' · ' + primary : '') }),
      c ? el('span', { 'class': 'sc-signal__note', text: threshold.length > 42 ? threshold.slice(0, 40).replace(/\s+\S*$/, '') + '…' : threshold }) : null
    ]);
    return el('td', null, cell);
  }
  function renderScan(data) {
    const bursts = (data.bursts || []).slice(), trades = data.trades || [], body = clear($('scan-body'));
    const run = data.run || {};
    const nCriteria = bursts.length && bursts[0].quality && bursts[0].quality.checks ? bursts[0].quality.checks.length : Object.keys(CRITERIA_SHORT).length;
    $('scan-lede').textContent = 'Every burst against Bonde’s ' + nCriteria + ' A-quality criteria: the measured value, his threshold, and the verdict in words.' + (isNum(run.bursts) && run.bursts > bursts.length ? ' ' + bursts.length + ' of the ' + num(run.bursts) + ' bursts found are archived with their checks.' : '');
    const cm = data.closest_miss;
    if (cm && cm.sentence && !trades.length) body.appendChild(el('aside', { 'class': 'sc-callout sc-callout--core', id: 'closest-miss' }, [el('div', { 'class': 'sc-callout__label', text: 'closest miss' }), el('p', { 'class': 'sc-callout__figure', text: cm.sentence })]));
    if (!bursts.length) { body.appendChild(empty('The scan found no burst.')); return; }
    const keys = Object.keys(CRITERIA_SHORT);
    const labels = {}; bursts.forEach((b) => ((b.quality || {}).checks || []).forEach((c) => { if (c && c.key && !labels[c.key]) labels[c.key] = c.label; }));
    const det = el('details', { 'class': 'sc-details sc-disclosure', id: 'scan-details' });
    det.appendChild(el('summary', { text: 'show all ' + bursts.length + ' bursts · sortable by score' }));
    det.appendChild(el('p', { 'class': 'sc-hint', id: 'scan-help', text: 'Jump to a criterion or swipe across. Keyboard: focus the table and use the arrow keys. Hover a tile for every measurement, his full threshold and the note.' }));
    const scroll = el('div', { 'class': 'sc-table-scroll', 'data-sc-matrix-nav': '', tabindex: '0', role: 'region', 'aria-label': 'Every burst against the ' + nCriteria + ' criteria', 'aria-describedby': 'scan-help' });
    const table = el('table', { 'class': 'sc-table sc-signal-matrix', id: 'scan-table' });
    table.appendChild(el('caption', { 'class': 'sc-sr-only', text: 'Bursts found on ' + (run.session || '') + ' compared on Bonde’s ' + nCriteria + ' A-quality criteria. Green passes, amber is marginal, red fails or is vetoed, neutral was not measured.' }));
    const sortBtn = el('button', { 'class': 'sc-table__sort', type: 'button', text: 'grade · score' });
    const sortTh = el('th', { scope: 'col', 'class': 'is-sortable', 'aria-sort': 'descending' }, sortBtn);
    table.appendChild(el('thead', null, el('tr', null, [el('th', { scope: 'col', text: 'burst' })].concat(keys.map((k) => el('th', { scope: 'col', 'data-sc-label': CRITERIA_SHORT[k], text: labels[k] || words(k) }))).concat([sortTh]))));
    const tbody = el('tbody');
    const rowOf = {};
    bursts.forEach((b) => {
      const q = b.quality || {}, checks = {}; (q.checks || []).forEach((c) => { if (c && c.key) checks[c.key] = c; });
      const vetoes = q.vetoes || [];
      const tr = el('tr', { id: 'burst-' + b.ticker, 'data-ticker': b.ticker, 'data-score': isNum(b.score) ? String(b.score) : '' });
      const isTrade = trades.indexOf(b.ticker) >= 0;
      tr.appendChild(el('th', { scope: 'row' }, [
        isTrade ? el('a', { 'class': 'sc-signal-matrix__name', href: '#trade-' + b.ticker, text: b.ticker }) : el('span', { 'class': 'sc-signal-matrix__name', text: b.ticker }),
        el('span', { 'class': 'sc-signal-matrix__note', text: pct(b.gain_pct) + ' · ' + (isNum(b.volume_vs_prior) ? b.volume_vs_prior.toFixed(1) : '—') + '× vol · ' + usd(b.close) + (b.scan === 'dollar' ? ' · $ scan' : '') })
      ]));
      keys.forEach((k) => tr.appendChild(signalCell(checks[k], (k === 'two_days' && vetoes.indexOf('up_days') >= 0) || (k === 'linearity' && vetoes.indexOf('not_linear') >= 0))));
      const miss = (q.checks || []).find((c) => c && !c.pass);
      const gradeNote = vetoes.length ? 'veto · ' + vetoes.map((v) => VETO_WORDS[v] || words(v)).join(', ') : q.reclass ? 'reclassified · ' + words(q.reclass) : miss ? 'first miss · ' + (miss.label || words(miss.key) || 'a check') : 'nothing missed';
      const gradeTone = b.grade === 'A+' || b.grade === 'A' ? 'brand' : 'neutral';
      tr.appendChild(el('td', { 'class': 'sc-signal-matrix__value' }, [chip((b.grade || '—') + (isNum(b.score) ? ' · ' + b.score.toFixed(1) : ''), gradeTone, true),
        el('span', { 'class': 'ss-grade-note', text: gradeNote + (b.claude && b.claude.source === 'claude' && b.claude.agree === false ? ' · Claude lowered it' : '') + (isTrade ? ' · trade' : '') })]));
      tbody.appendChild(tr); rowOf[b.ticker] = tr;
    });
    table.appendChild(tbody);
    let dir = 'descending';
    function sort() {
      const rows = Array.from(tbody.children);
      rows.sort((a, b) => {
        const sa = a.dataset.score === '' ? -Infinity : +a.dataset.score, sb = b.dataset.score === '' ? -Infinity : +b.dataset.score;
        return dir === 'descending' ? sb - sa : sa - sb;
      });
      rows.forEach((r) => tbody.appendChild(r));
      sortTh.setAttribute('aria-sort', dir);
    }
    sortBtn.addEventListener('click', () => { dir = dir === 'descending' ? 'ascending' : 'descending'; sort(); });
    sort();
    scroll.appendChild(table);
    det.appendChild(scroll);
    det.appendChild(el('p', { 'class': 'sc-hint', text: 'Green = passes his threshold. Amber = partial. Red = fails, or vetoed outright. A+ and A need the close near the high and no two up days in a row; the grade word is the verdict, the score its rank.' }));
    body.appendChild(det);
    // a link into the matrix opens the disclosure first
    d.addEventListener('click', (e) => {
      const a = e.target.closest && e.target.closest('a[data-matrix-link]');
      if (a) det.open = true;
    });
    if (w.location.hash && /^#burst-/.test(w.location.hash) && rowOf[w.location.hash.slice(7)]) det.open = true;
  }

  // ---------------------------------------------------------------- record
  function tile(label, value, sub) {
    return el('div', { 'class': 'sc-tile' }, [el('div', { 'class': 'sc-tile__label', text: label }), el('div', { 'class': 'sc-tile__value sc-tile__value--sm', text: value }), el('div', { 'class': 'sc-tile__sub', text: sub })]);
  }
  function renderRecord(data) {
    const sc = data.scorecard || {}, card = clear($('record-card'));
    const settled = isNum(sc.settled) ? sc.settled : 0, minRead = sc.min_read, readable = sc.readable === true;
    card.appendChild(el('div', { 'class': 'sc-card__head' }, [
      el('div', null, [el('h3', { text: 'The scorecard' }), el('p', { 'class': 'sc-hint', text: 'read from ' + plain(minRead) + ' settled plans: the rules’ record, not yours' + (readable ? '' : ' · ' + settled + ' settled so far, so nothing below is a rate yet') })]),
      chip(readable ? 'readable' : 'not yet readable', readable ? 'good' : 'neutral')
    ]));
    card.appendChild(el('div', { 'class': 'sc-grid sc-grid--4' }, [
      tile('plans', num(sc.plans), num(sc.settled) + ' settled · reads at ' + plain(minRead)),
      tile('filled', num(sc.filled), 'at the next open, inside the zone'),
      tile('win rate', isNum(sc.win_rate) ? (100 * sc.win_rate).toFixed(0) + '%' : '—', num(sc.wins) + ' wins · ' + num(sc.losses) + ' losses'),
      tile('avg R', isNum(sc.avg_r) ? (sc.avg_r > 0 ? '+' : '') + sc.avg_r.toFixed(2) : '—', 'sum R ' + (isNum(sc.sum_r) ? (sc.sum_r > 0 ? '+' : '') + sc.sum_r.toFixed(1) : '—'))
    ]));
    card.appendChild(el('p', { 'class': 'sc-note', text: 'SPY over the same days: ' + pct(sc.spy_avg_pct, 2) + ' — one comparison line, not a benchmark. ' + (sc.note || '') }));
    // fourteen nights of reliability, from nights[]: ok, degraded, closed, missing
    const nights = {}; (data.nights || []).forEach((x) => { if (x && x.session) nights[x.session] = x; });
    const end = (data.run || {}).expected_session || (data.run || {}).session;
    const days = end ? weekdaysEnding(end, 14) : [];
    const counts = { ok: 0, degraded: 0, closed: 0, failed: 0, missing: 0 };
    const list = el('ol', { 'class': 'ss-nights', id: 'nights', 'aria-label': 'The last fourteen evenings' }, days.map((iso) => {
      const nt = nights[iso], s = nt ? (counts[nt.status] !== undefined ? nt.status : 'ok') : 'missing';
      counts[s]++;
      return el('li', { 'class': 'ss-night is-' + s, 'data-session': iso, 'data-status': s, title: dateWords(iso) + ' · ' + s }, el('span', { 'class': 'sc-sr-only', text: dateWords(iso) + ' ' + s }));
    }));
    card.appendChild(el('div', { 'class': 'sc-eyebrow', style: 'margin-top:16px', text: 'the last fourteen evenings' }));
    card.appendChild(list);
    card.appendChild(el('div', { 'class': 'ss-nights-key' }, [
      el('span', null, [el('i', { 'class': 'ss-night is-ok' }), counts.ok + ' ok']),
      el('span', null, [el('i', { 'class': 'ss-night is-degraded' }), counts.degraded + ' degraded']),
      el('span', null, [el('i', { 'class': 'ss-night is-closed' }), counts.closed + ' closed']),
      el('span', null, [el('i', { 'class': 'ss-night is-missing' }), (counts.missing + counts.failed) + ' missing'])
    ]));
  }

  // ---------------------------------------------------------------- next
  function nextAction(data, st) {
    const bursts = by(data.bursts || [], 'ticker');
    const orders = (data.trades || []).map((t) => bursts[t]).filter((b) => b && b.plan && b.plan.order_json).length;
    const open = (data.open_plans || []).length, red = ((data.breadth || {}).regime || {}).verdict === 'red';
    if (st.state === 'stale1' || st.state === 'stale2' || st.state === 'pending' || st.state === 'failed') {
      return ['Do not place these orders.', 'Wait for tonight’s run to publish, or check the run log. Nothing on this page is tomorrow’s plan.', 'stale'];
    }
    if (st.state === 'closed') return ['Plans unchanged. Check what you hold before ' + ORDERS_BY + '.', 'The market was closed; there is nothing new to place.', 'closed'];
    if (red) return ['No new longs. Work the exits above before ' + ORDERS_BY + '.', 'Breadth is red: tighten the stops and sell into strength.', 'red'];
    if (orders) return ['Place the ' + orders + ' order' + (orders === 1 ? '' : 's') + ' above in Fidelity before ' + ORDERS_BY + '. Exits first.', 'Attach each sell stop the moment its buy fills.', 'orders'];
    if (open) return ['Nothing new to place. Work the exits above before ' + ORDERS_BY + '.', 'No burst qualified tonight; the open plans still carry their instructions.', 'quiet'];
    return ['Nothing to place. Keep cash.', 'No burst qualified and nothing is held. Come back after the next run.', 'quiet'];
  }
  function renderNext(data, st) {
    const n = nextAction(data, st);
    $('next-h3').textContent = n[0]; $('next-p').textContent = n[1];
    $('next').setAttribute('data-variant', n[2]);
  }

  // ---------------------------------------------------------------- footer
  function renderFooter(data) {
    const run = data.run || {}, uni = run.universe || {}, app = data.app || {};
    const foot = clear($('foot-line'));
    foot.appendChild(d.createTextNode('bars: Alpaca ' + String(run.feed || '').toUpperCase() + ', daily, 16-minute holdback · universe: ' + (uni.source || '—') + ', ' + num(uni.size) + ' common stocks · graded by ' + (run.model || '—') + ' · rules ' + (app.rules_version || '—') + ' · run ' + (run.status || '—') + ' · '));
    if (run.run_id) { foot.appendChild(el('a', { href: 'https://github.com/' + REPO + '/actions/runs/' + run.run_id, target: '_blank', rel: 'noopener', text: 'run ' + run.run_id })); foot.appendChild(d.createTextNode(' · ')); }
    foot.appendChild(el('a', { href: RUNS_URL, target: '_blank', rel: 'noopener', text: 'dispatch' }));
    foot.appendChild(d.createTextNode(' · generated ' + (run.published_at ? timeET(run.published_at) : '—') + ' · paper prices, one venue’s prints, no slippage · not investment advice'));
  }

  // ---------------------------------------------------------------- live run log (optional; silent on failure)
  function liveRunLog() {
    const slot = $('runlog');
    if (!slot || !w.fetch) return;
    w.fetch(RUNS_API, { headers: { accept: 'application/vnd.github+json' } })
      .then((r) => (r && r.ok ? r.json() : null))
      .then((j) => {
        const run = j && j.workflow_runs && j.workflow_runs[0];
        if (!run || !run.status) return;
        const when = run.status === 'completed' ? run.updated_at : run.run_started_at || run.created_at;
        const word = run.status === 'completed' ? (run.conclusion === 'success' ? 'completed' : 'failed') : run.status.replace(/_/g, ' ');
        clear(slot);
        slot.appendChild(d.createTextNode('tonight’s run: ' + word + (when ? ' at ' + timeET(when) : '') + ' — '));
        slot.appendChild(el('a', { href: run.html_url || RUNS_URL, target: '_blank', rel: 'noopener', text: 'open log' }));
        slot.hidden = false;
      })
      .catch(() => { /* the static link stands */ });
  }

  // Under 720px the open-plans rail comes FIRST in the DOM, not just on
  // screen: a phone reader (and a screen reader) meets "what do I do with
  // what I hold" before "what do I buy". Desktop puts it back beside the cards.
  const NARROW = '(max-width: 720px)';
  function placeRail() {
    const bento = d.querySelector('.ss-bento'); if (!bento) return;
    const main = bento.querySelector('.sc-bento__main'), aside = bento.querySelector('.sc-bento__aside');
    if (!main || !aside) return;
    const narrow = w.matchMedia && w.matchMedia(NARROW).matches;
    if (narrow && aside.nextElementSibling !== main) bento.insertBefore(aside, main);
    else if (!narrow && main.nextElementSibling !== aside) bento.appendChild(aside);
  }
  if (w.matchMedia) { const mq = w.matchMedia(NARROW); if (mq.addEventListener) mq.addEventListener('change', placeRail); else if (mq.addListener) mq.addListener(placeRail); }

  // ---------------------------------------------------------------- render
  function render(data, now) {
    SCStock.data = data;
    const st = status(data, now);
    SCStock.state = st;
    renderStatus(data, st);
    renderCover(data, st);
    renderStrip(data);
    renderBreadth(data);
    renderTomorrow(data, st);
    renderAlerts(data);
    renderScan(data);
    renderRecord(data);
    renderNext(data, st);
    renderFooter(data);
    d.title = 'SpicyStock · ' + ((data.cover || {}).h1 || 'no verdict');
    if (w.SC && w.SC.reading && w.SC.reading.refresh) { try { w.SC.reading.refresh(); } catch (e) { /* optional */ } }
    d.documentElement.setAttribute('data-ss-rendered', st.state);
    liveRunLog();
    return st;
  }
  SCStock.render = render;

  function failed(message) {
    $('cover-h1').textContent = 'The record could not be read.';
    $('cover-dek').textContent = message;
    clear($('status-slot')).appendChild(chip('no record', 'danger'));
    $('next-h3').textContent = 'Do not place any order from this page.';
    $('next-p').textContent = 'docs/data.json did not load; check the run log.';
    d.documentElement.setAttribute('data-ss-rendered', 'error');
  }
  function boot() {
    const src = (w.SCStock && w.SCStock.dataUrl) || 'data.json';
    w.fetch(src, { cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error('data.json answered ' + r.status); return r.json(); })
      .then((data) => { if (!data || data.schema_version !== 2 || !data.run) throw new Error('not a schema_version 2 record'); render(data, w.SCStock.now ? new Date(w.SCStock.now) : new Date()); })
      .catch((e) => failed(String(e && e.message || e)));
  }
  if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', boot); else boot();
})(window);
