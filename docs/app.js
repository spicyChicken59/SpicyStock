/* SpicyStock — the page. Renders docs/data.json (schema_version 2) on the
   SpicyChicken system as one small application: Explore (the market in a
   line, then the stocks Setting up and the Bursts, one chosen stock at a
   time with its annotated chart, its conditions and its conditional
   ticket), Record (what the published model plans did), Market (Bonde's
   Market Monitor in full) and Method (the run and its assumptions).

   It computes exactly one thing of its own: the status chip, from
   run.session / run.session_state / run.expected_session / generated and
   the browser clock in ET — because a run that failed cannot write its own
   obituary. Every other number is printed, never derived from a rule:
   thresholds come out of the archived `rules` and `breadth.regime` blocks,
   sizes out of `plan`, sentences out of `cover`, `open_plans[]` and
   `breadth.regime.reasons[]`, verbatim. Selection, stage and view are page
   state, kept in the hash (#/explore/bursts/AAPL) so a link reloads and the
   Back button works; choosing a stock fetches nothing and grades nothing.

     SCStock.status(data, now)  -> {state, chip, tone, sentence, expected, behind}
     SCStock.render(data, now)  -> paints the page
     SCStock.navigate(hash)     -> routes inside the page
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
  const METHOD_URL = 'https://github.com/' + REPO + '/blob/main/knowledge/method.md';
  const RULEBOOK_URL = 'https://github.com/' + REPO + '/blob/main/knowledge/strategy.md';

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
  // One word per plan status, the same eleven src/report.py mails (tests/test_docs.py holds the two equal).
  const PLAN_STATUS = {
    hold: ['HOLD', 'good'], sell_half: ['SELL HALF', 'brand'], sell_into_strength: ['SELL INTO STRENGTH', 'brand'],
    exit: ['SELL', 'brand'], stopped: ['STOPPED', 'danger'], expired: ['EXPIRED', 'neutral'], pending: ['PENDING', 'neutral'],
    not_filled: ['NOT FILLED', 'neutral'], uncertain: ['UNCERTAIN', 'warn'], unreadable: ['UNREADABLE', 'warn'], unmeasured: ['UNMEASURED', 'warn']
  };
  // the statuses the model actually walked from a known fill; the others carry no position to draw
  const WALKED = ['hold', 'sell_half', 'sell_into_strength', 'exit', 'stopped', 'expired'];
  // why an A-quality plan has no ticket, as the budget's cut kinds spell it (src/plan.py CUT_KINDS)
  const CUT_WORDS = { withheld: 'ticket withheld', slot_cap: 'beyond the slot cap', equity: 'beyond the configured equity', no_shares: 'no whole share', no_new_longs: 'no new longs' };
  const CUT_TONE = { withheld: 'warn', slot_cap: 'neutral', equity: 'neutral', no_shares: 'neutral', no_new_longs: 'neutral' };
  const REGIME_TONE = { green: 'good', yellow: 'warn', red: 'danger' };
  const FLAG_WORDS = { gain_over_15: 'gain over 15%', wide_stop: 'stop past the line at the limit', position_capped: 'position capped', biotech: 'biotech', foreign: 'foreign', dollar_breakout: '$ breakout', refused: 'ticket withheld', risk_halved: 'risk halved', extended: 'extended' };
  // The checklist's own keys (src/quality.py): 2 L Y N C H, then RE and VOL.
  const CRITERIA_SHORT = {
    two_days: 'up days', linearity: 'linear', young_trend: 'young', narrow_or_negative: 'quiet',
    consolidation: 'tight', close_near_high: 'close', range_expansion: 'range', volume: 'volume'
  };
  const VETO_WORDS = { up_days: 'three up days in a row', not_linear: 'the prior leg is not linear' };
  const STOP_BASIS = { burst_low: 'the burst day’s low', half_range: 'the burst bar’s midpoint' };
  const STAGES = ['bursts', 'setting-up'];
  const STAGE_NAME = { bursts: 'Bursts', 'setting-up': 'Setting up' };
  const VIEWS = ['explore', 'record', 'market', 'method'];
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
  const text = (v) => typeof v === 'string' && v.trim() ? v.trim() : '';
  const sentence = (s) => { s = text(s); return s ? (/[.!?]$/.test(s) ? s : s + '.') : ''; };
  const firstSentence = (s) => { s = text(s); const m = /^(.+?[.!?])(\s|$)/.exec(s); return m ? m[1] : s; };
  const plural = (n, noun) => n + ' ' + noun + (n === 1 ? '' : 's');
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
  function clear(node) { while (node && node.firstChild) node.removeChild(node.firstChild); return node; }
  const $ = (id) => d.getElementById(id);
  const by = (list, key) => { const m = {}; (list || []).forEach((x) => { if (x && x.ticker) m[x.ticker] = x; }); return m; };
  const narrow = () => !!(w.matchMedia && w.matchMedia('(max-width: 720px)').matches);

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
  // a page in one of these states offers no order: the tickets are withheld from the reader's hand
  const BLOCKED = ['stale1', 'stale2', 'pending', 'failed'];
  const blocked = (st) => BLOCKED.indexOf(st.state) >= 0;

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

  // ---------------------------------------------------------------- the market, in a line
  function renderMarketBar(data, st) {
    const run = data.run || {}, cover = data.cover || {}, b = data.breadth || {}, reg = b.regime || {};
    $('cover-eyebrow').textContent = 'spicystock · ' + (run.session || '—') + ' · evening run';
    $('cover-h1').textContent = cover.h1 || 'No verdict.';
    $('cover-dek').textContent = cover.dek || '';
    const facts = clear($('market-facts'));
    const fact = (dt, kids) => facts.appendChild(el('div', { 'data-fact': dt }, [el('dt', { text: dt }), el('dd', null, kids)]));
    fact('session', [el('span', { text: dateWords(run.session) + (run.session_state === 'closed' ? ' · closed on ' + dateWords(run.expected_session) : '') })]);
    const size = reg.size_multiplier;
    const sizeWords = size === 1 ? 'full size' : size === 0 ? 'no new longs' : isNum(size) ? 'size at ' + (size * 100).toFixed(0) + '%' : '';
    fact('regime', [chip((reg.verdict || 'unknown').toUpperCase(), REGIME_TONE[reg.verdict] || 'neutral', true), el('span', { text: sizeWords + (isNum(b.ratio_10d) ? ' · 10-day ratio ' + plain(b.ratio_10d) : '') })]);
    fact('published', [el('span', { text: timeET(run.published_at) + ' · run ' + (run.status || '—') + ' · email ' + (run.email || '—') })]);
    const notice = $('demo-notice');
    if (notice) {
      clear(notice);
      if (demo) notice.appendChild(el('div', { 'class': 'sc-notice ss-demo', role: 'note' }, [el('span', { 'class': 'sc-eyebrow', text: 'sample data · fixture ' + String(data.fixture) }), el('p', { text: 'Do not trade sample data: this record is a pipeline-written fixture over a synthetic market; its bursts, coils, plans and chart-reader replies are test doubles.' })]));
      notice.hidden = !demo;
    }
    // the record's own call to action (Tomorrow's orders / Open model plans),
    // falling back to the model plans on a page that offers no order
    const links = clear($('market-links'));
    const offered = !blocked(st), label = offered ? (cover.action_label || 'Open model plans') : 'Open model plans', target = offered ? (cover.action_target || '#hold') : '#hold';
    links.appendChild(el('a', { 'class': 'sc-link--quiet', id: 'cover-action', href: target, text: label }));
    links.appendChild(el('a', { 'class': 'sc-link--quiet', href: '#/market', text: 'market detail' }));
    links.appendChild(el('a', { 'class': 'sc-link--quiet', href: '#/method', text: 'run details' }));
  }

  // ---------------------------------------------------------------- run strip (the method view)
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
  function renderMethod(data) {
    renderStrip(data);
    const run = data.run || {}, uni = run.universe || {}, app = data.app || {}, acct = data.account || {};
    const meta = clear($('run-meta'));
    const line = (t) => meta.appendChild(el('li', { text: t }));
    line('Bars: Alpaca ' + String(run.feed || '').toUpperCase() + ', daily, the request window sixteen minutes behind the clock; ' + num(uni.size) + ' common stocks from ' + (uni.source || '—') + (uni.label ? ' (' + uni.label + ')' : '') + '.');
    line('Graded by ' + (run.model || '—') + ' from the chart and the numbers; the model may only lower a grade, never raise it.');
    line('Rules ' + (app.rules_version || '—') + ': a digest of every strategy constant in this record, so two nights under different numbers never read as one. Universe identity ' + (uni.identity || '—') + '.');
    line('Timing: ' + num(run.elapsed_seconds) + ' s for the run, ' + num(run.fetch_seconds) + ' s of it fetching; generated ' + (run.published_at || '—') + '.');
    (run.problems || []).forEach((p) => { if (p && PROBLEMS[p.kind]) line('Problem recorded (' + words(p.kind) + '): ' + PROBLEMS[p.kind]); });
    if (run.run_id) {
      const li = el('li', null, [el('a', { href: 'https://github.com/' + REPO + '/actions/runs/' + run.run_id, target: '_blank', rel: 'noopener', text: 'The run log for this record' }), d.createTextNode(' · '), el('a', { href: RUNS_URL, target: '_blank', rel: 'noopener', text: 'every evening run' })]);
      meta.appendChild(li);
    } else meta.appendChild(el('li', null, [el('a', { href: RUNS_URL, target: '_blank', rel: 'noopener', text: 'The evening runs on GitHub' })]));
    const body = clear($('method-body'));
    body.appendChild(el('p', { text: 'SpicyStock is an implementation of Pradeep Bonde’s momentum burst method with explicit assumptions: a 4% range-expansion day out of a quiet base, bought the next morning inside a narrow zone with the stop under the burst bar, sold into strength over three to five days, and only when breadth allows it. It is not a proven edge and it knows nothing about what you hold.' }));
    body.appendChild(el('p', { text: 'Setting up is the anticipation list: quiet, coiled names inside established momentum, with a buy stop a few cents over the box. Bursts are the range-expansion days the scan found on the session, graded on Bonde’s checklist; a grade, a plan and a ticket are three different things, and the page says which a stock has. Every ticket is sized at its limit, the highest fill it permits, so the fixed quantity keeps the risk budget, the position cap and his 4% stop line at every fill it can take; a stop past that line at the limit withholds the ticket and keeps the setup.' }));
    body.appendChild(el('p', { text: 'The Record is a model: a fill is booked only at the next open inside the ticket, the published stop is one R, sales are whole shares, and a fill the daily bars cannot establish is uncertain and scored nowhere. Paper prices, one venue’s prints, no slippage. Not investment advice.' }));
    body.appendChild(el('p', null, [el('a', { href: METHOD_URL, target: '_blank', rel: 'noopener', text: 'Whose number each rule is (knowledge/method.md)' }), d.createTextNode(' · '), el('a', { href: RULEBOOK_URL, target: '_blank', rel: 'noopener', text: 'the rulebook the chart reader follows (knowledge/strategy.md)' })]));
    const notes = clear($('account-notes'));
    (acct.notes || []).forEach((n) => notes.appendChild(el('li', { text: n })));
    if (!(acct.notes || []).length) notes.appendChild(el('li', { text: 'No sizing notes were recorded.' }));
  }

  // ---------------------------------------------------------------- breadth (the market view)
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

  // ---------------------------------------------------------------- the ticket
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
  // the order, as written by the run: shown only when the plan carries one
  // and the page is not stale, pending or without a verdict
  function orderBlock(plan, extraHint, withheld) {
    const lines = withheld ? null : ticket(plan.order_json);
    const wrap = el('div', { 'class': 'ss-order' });
    if (!lines) { wrap.appendChild(el('p', { 'class': 'sc-hint', text: extraHint || 'No order.' })); return wrap; }
    const pre = el('pre', { 'class': 'ss-order__pre', 'data-order': '', 'data-ticker': plan.ticker || '' });
    lines.forEach((line, i) => { if (i) pre.appendChild(d.createTextNode('\n')); pre.appendChild(el('span', { text: line })); });
    wrap.appendChild(el('div', { 'class': 'ss-order__head' }, [el('span', { 'class': 'sc-eyebrow', style: 'margin:0', text: 'the order, in Fidelity’s field order' }), copyButton(() => pre.textContent, pre)]));
    wrap.appendChild(pre);
    if (plan.order_line) wrap.appendChild(el('p', { 'class': 'ss-order__readback', text: 'Read it back: ' + plan.order_line }));
    const terms = (plan.order_terms || []).filter((t) => typeof t === 'string' && t);
    if (terms.length) {
      wrap.appendChild(el('div', { 'class': 'sc-eyebrow', style: 'margin-top:10px', text: 'what the ticket enforces, and what it leaves to you' }));
      wrap.appendChild(el('ul', { 'class': 'ss-notes ss-order__terms' }, terms.map((t) => el('li', { text: t }))));
    }
    return wrap;
  }
  function stopWords(plan) {
    const basis = STOP_BASIS[plan.stop_basis] || (plan.stop_basis === 'max_stop' ? plain(plan.stop_pct) + '% under the limit (the bar does not support it)' : words(plan.stop_basis));
    return usd(plan.stop) + ' · ' + basis;
  }

  // ---------------------------------------------------------------- the chart panel: modes, ranges, preferences
  // One geometry, three drawings (app-chart.js `mode`) and three ranges. The
  // mode, the range and the close-line toggle are the reader's preferences,
  // kept in this browser and applied to every stock; a blocked store keeps
  // the defaults and still applies a choice for the session.
  const CHART_PREFS_KEY = 'spicystock:chart:v1';
  const CHART_MODES = ['setup', 'candles', 'line'];
  const MODE_WORDS = { setup: 'Setup', candles: 'Candles', line: 'Line' };
  const CHART_RANGES = ['setup', '60', '120'];
  const RANGE_WORDS = { setup: 'Setup range', '60': '60 sessions', '120': '120 sessions' };
  const SETUP_PAD_MIN = 8;          // sessions of context before the base in the Setup range (presentation)
  const SETUP_PAD_FRACTION = 0.6;   // or this share of the base's length, whichever is more (presentation)
  const prefs = { mode: 'setup', range: 'setup', closeLine: false };
  function loadPrefs() {
    try {
      const raw = w.localStorage && w.localStorage.getItem(CHART_PREFS_KEY), saved = raw ? JSON.parse(raw) : null;
      if (saved && CHART_MODES.indexOf(saved.mode) >= 0) prefs.mode = saved.mode;
      if (saved && CHART_RANGES.indexOf(String(saved.range)) >= 0) prefs.range = String(saved.range);
      if (saved && typeof saved.closeLine === 'boolean') prefs.closeLine = saved.closeLine;
    } catch (e) { /* a blocked or corrupt store keeps the defaults */ }
  }
  function savePrefs() { try { w.localStorage.setItem(CHART_PREFS_KEY, JSON.stringify(prefs)); } catch (e) { /* not remembered; still applied */ } }
  const idxOf = (series, date) => series.findIndex((x) => x && x.date === date);
  // the bars a range shows, with the words that disclose it. The Setup range
  // frames the base (the burst's base, the coil's box) with a short run of
  // context before it; without base dates it says so and shows 60 sessions.
  function rangeSlice(c, range) {
    const all = c.series, dates = c.stage === 'bursts' ? ((c.row.quality || {}).base || {}) : (c.row.box || {});
    if (range === 'setup') {
      const bs = dates.start ? idxOf(all, dates.start) : -1, be = dates.end ? idxOf(all, dates.end) : -1;
      if (bs >= 0 && be >= bs) {
        const pad = Math.max(SETUP_PAD_MIN, Math.round((be - bs + 1) * SETUP_PAD_FRACTION)), from = Math.max(0, bs - pad);
        return { series: all.slice(from), range: 'setup', note: 'the base and ' + plural(bs - from, 'session') + ' before it', fallback: false };
      }
      const series = all.slice(-60);
      return { series: series, range: 'setup', note: 'Setup range unavailable, no base dates recorded: the last ' + series.length + ' sessions', fallback: true };
    }
    const series = all.slice(-(+range));
    return { series: series, range: range, note: 'the last ' + series.length + ' sessions', fallback: false };
  }
  function chartOptionsFor(c, series, height) {
    const o = c.stage === 'bursts' ? burstChartOptions(c.row, series, height) : coilChartOptions(c.row, series, height);
    o.mode = prefs.mode; o.closeLine = prefs.closeLine; o.gutterLabels = true; o.head = false;
    return o;
  }
  function burstChartOptions(b, series, height) {
    const plan = b.plan || {}, q = b.quality || {}, base = q.base || {};
    const check = {}; (q.checks || []).forEach((c) => { if (c && c.key) check[c.key] = c; });
    let box = null;
    if (base.start && base.end && isNum(base.low) && isNum(base.high)) {
      let bs = idxOf(series, base.start), be = idxOf(series, base.end);
      if (be >= 0) { if (bs < 0) bs = 0; box = { start: bs, end: be, low: base.low, high: base.high, depthPct: base.depth_pct }; }
    }
    const up = check.two_days && check.two_days.values ? check.two_days.values.up_run : null;
    const rng = check.range_expansion ? check.range_expansion.value : null;
    return {
      ticker: b.ticker,
      card: true, compact: false, futureSlots: 6, targetRuler: true, ma: [], volumeAvg: 20,
      burstIndex: series.length - 1, box: box,
      // the buy stop is the trigger; the zone's top is the limit, its floor the skip line
      stop: plan.stop, trigger: plan.entry_ref, entryLow: plan.entry_low, entryHigh: plan.entry_high,
      targetLow: plan.targets ? plan.targets.low : null, targetHigh: plan.targets ? plan.targets.high : null, targetRef: plan.planned_entry,
      upDays: isNum(up) ? up : 0, breakdownIndexes: (base.breakdown_dates || []).map((d) => idxOf(series, d)).filter((i) => i >= 0),
      burstVolumeRatio: b.volume_vs_prior, rangeExpansion: isNum(rng) ? rng : null,
      ariaLabel: b.summary || null, height: height
    };
  }
  function coilChartOptions(c, series, height) {
    const plan = c.plan || {}, box = c.box || {};
    let bx = null;
    if (box.start && box.end && isNum(box.low) && isNum(box.high)) {
      let bs = idxOf(series, box.start), be = idxOf(series, box.end);
      if (be >= 0) { if (bs < 0) bs = 0; bx = { start: bs, end: be, low: box.low, high: box.high }; }
    }
    const t = plan.targets || {};
    return {
      ticker: c.ticker,
      card: true, compact: false, futureSlots: 6, targetRuler: true, ma: [], volumeAvg: 20,
      burstIndex: null, box: bx,
      stop: plan.stop, trigger: plan.trigger, entryLow: plan.trigger, entryHigh: plan.limit,
      targetLow: isNum(t.low) ? t.low : null, targetHigh: isNum(t.high) ? t.high : null, targetRef: plan.limit,
      ariaLabel: c.ticker + ' daily chart: a coil of ' + plain(box.sessions) + ' sessions between ' + usd(box.low) + ' and ' + usd(box.high) + (isNum(plan.trigger) ? ', buy stop at ' + usd(plan.trigger) + ' with the limit ' + usd(plan.limit) + ' and the stop ' + usd(plan.stop) : ', no ticket') + '. Use the arrow keys to step through the sessions; the table view below lists the same numbers.',
      height: height
    };
  }
  SCStock.chartOptions = burstChartOptions;

  // ---------------------------------------------------------------- the view model
  // A small adapter over the record, and the only place the page decides
  // which words describe a stock. Every status is read off a field the run
  // wrote (trades[], cash_budget.cut[].kind, plan.eligible, plan.action,
  // plan.shares, quality.vetoes, the grade against the archived
  // rules.pipeline.trade_grades); every sentence beside it is the record's
  // own. Nothing here scans, grades, sizes or fetches.
  const STATUS_WORDS = {
    ticket: ['ticket', 'good'], vetoed: ['vetoed', 'danger'], below_grade: ['no ticket', 'neutral'], not_admitted: ['no ticket', 'neutral'],
    no_plan: ['no ticket', 'neutral'], no_order: ['no order', 'neutral'], watch: ['watch', 'neutral']
  };
  function statusWords(status) {
    if (CUT_WORDS[status]) return [CUT_WORDS[status], CUT_TONE[status] || 'neutral'];
    return STATUS_WORDS[status] || [words(status || 'no ticket'), 'neutral'];
  }
  const listRule = (data, key, fallback) => { const r = ((data.rules || {}).pipeline || {})[key]; return Array.isArray(r) && r.length ? r : fallback; };
  function buildModel(data) {
    const trades = data.trades || [], cb = data.cash_budget || {}, cuts = {};
    (cb.cut || []).forEach((c) => { if (c && c.ticker && !cuts[c.ticker]) cuts[c.ticker] = c; });
    const reg = (data.breadth || {}).regime || {}, verdict = reg.verdict;
    const tradeGrades = listRule(data, 'trade_grades', ['A+', 'A']), yellowGrades = listRule(data, 'yellow_grades', ['A+']);
    const bursts = (data.bursts || []).filter((b) => b && b.ticker).map((b, i) => {
      const plan = b.plan || null, q = b.quality || {}, vetoes = q.vetoes || b.vetoes || [], cut = cuts[b.ticker] || null;
      let status, reason;
      if (trades.indexOf(b.ticker) >= 0 && plan && plan.order_json) { status = 'ticket'; reason = plan.order_line || ''; }
      else if (cut && cut.kind) { status = cut.kind; reason = cut.reason || ''; }
      else if (plan && plan.eligible === false) { status = 'withheld'; reason = plan.reason || ''; }
      else if (plan && plan.action === 'no_new_longs') { status = 'no_new_longs'; reason = plan.reason || 'breadth sizes new positions at zero tonight'; }
      else if (plan && plan.shares === 0) { status = 'no_shares'; reason = plan.reason || 'the size came to zero whole shares'; }
      else if (vetoes.length) { status = 'vetoed'; reason = 'veto: ' + vetoes.map((v) => VETO_WORDS[v] || words(v)).join(', '); }
      else if (tradeGrades.indexOf(b.grade) < 0) {
        const miss = (q.checks || []).find((c) => c && !c.pass);
        status = 'below_grade';
        reason = 'graded ' + (b.grade || '—') + ', under the ' + tradeGrades.join('/') + ' line' + (miss ? ' · misses ‘' + (miss.label || words(miss.key) || 'a check') + '’' : '');
      }
      else if (verdict === 'yellow' && yellowGrades.indexOf(b.grade) < 0) { status = 'not_admitted'; reason = 'a yellow night admits ' + yellowGrades.join('/') + ' only'; }
      else if (reg.size_multiplier === 0 || verdict === 'red') { status = 'no_new_longs'; reason = 'no new longs: breadth is ' + (verdict || 'red'); }
      else if (!plan) { status = 'no_plan'; reason = 'the run wrote no plan for this burst'; }
      else { status = 'no_order'; reason = plan.reason || 'no order was written for this plan'; }
      const flags = (b.flags || []).slice();
      (plan && plan.flags || []).forEach((f) => { if (flags.indexOf(f) < 0) flags.push(f); });
      return { id: 'bursts:' + b.ticker, stage: 'bursts', ticker: b.ticker, name: text(b.name), rank: isNum(b.rank) ? b.rank : i + 1,
        grade: b.grade || null, score: b.score, status: status, reason: reason, cut: cut, plan: plan, row: b, quiet: false, flags: flags,
        series: Array.isArray(b.series) ? b.series.filter((x) => x && x.date) : [],
        measures: [['gain', pct(b.gain_pct)], ['vol', isNum(b.volume_vs_prior) ? b.volume_vs_prior.toFixed(1) + '×' : '—'], ['close', usd(b.close)]] };
    });
    const wl = data.watchlist || {};
    const coil = (r, i, quiet) => {
      const plan = quiet ? null : (r.plan || null), box = r.box || {};
      let status, reason;
      if (quiet) { status = 'watch'; reason = 'also quiet: on no list tonight, no plan and no ticket'; }
      else if (plan && plan.eligible === false) { status = 'withheld'; reason = plan.reason || ''; }
      else if (plan && plan.action === 'no_new_longs') { status = 'no_new_longs'; reason = plan.reason || 'breadth sizes new positions at zero tonight; keep the alert, place nothing'; }
      else if (plan && plan.order_json) { status = 'ticket'; reason = plan.order_line || ''; }
      else if (plan && plan.shares === 0) { status = 'no_shares'; reason = plan.reason || 'the size came to zero whole shares'; }
      else if (plan) { status = 'no_order'; reason = plan.reason || 'no order was written for this plan'; }
      else { status = 'watch'; reason = 'on the list; the run wrote no plan for it'; }
      return { id: 'setting-up:' + r.ticker, stage: 'setting-up', ticker: r.ticker, name: text(r.name), rank: i + 1, grade: null, score: null,
        status: status, reason: reason, cut: null, plan: plan, row: r, quiet: !!quiet, flags: plan && plan.flags ? plan.flags.slice() : [],
        series: Array.isArray(r.series) ? r.series.filter((x) => x && x.date) : [],
        measures: [['quiet', plain(r.quiet_days) + ' d'], ['range', plain(r.range_pct) + '%'], quiet ? ['close', usd(r.close)] : ['box', plain(box.sessions) + ' s']] };
    };
    const top = (wl.top || []).filter((r) => r && r.ticker), seen = {};
    top.forEach((r) => { seen[r.ticker] = true; });
    const settingUp = top.map((r, i) => coil(r, i, false))
      .concat((wl.also_quiet || []).filter((r) => r && r.ticker && !seen[r.ticker]).map((r, i) => coil(r, top.length + i, true)));
    const stages = { bursts: bursts, 'setting-up': settingUp }, byId = {};
    STAGES.forEach((s) => stages[s].forEach((c) => { byId[c.id] = c; }));
    const count = (list, f) => list.filter(f).length;
    return { stages: stages, byId: byId, defaultStage: bursts.length ? 'bursts' : settingUp.length ? 'setting-up' : 'bursts',
      tickets: { bursts: count(bursts, (c) => c.status === 'ticket'), 'setting-up': count(settingUp, (c) => c.status === 'ticket') },
      counts: wl.counts || {}, tradeGrades: tradeGrades };
  }
  function pickReason(c) {
    if (c.stage === 'bursts') {
      const s = firstSentence(text(c.row.summary).replace(/^[A-Z0-9.\-]+:\s*/, ''));
      return s || sentence(c.reason) || 'No summary recorded.';
    }
    const r = c.row, box = r.box || {};
    return (r.setups && r.setups.length ? r.setups.join(', ') + ' · ' : '') + (c.quiet ? 'also quiet · ' : '') + plain(r.quiet_days) + ' quiet days' + (isNum(box.low) && isNum(box.high) ? ' · box ' + usd(box.low) + '–' + usd(box.high) : '');
  }

  // ---------------------------------------------------------------- state and routes
  // The page's state is the hash: #/explore/<stage>/<TICKER>, #/record,
  // #/market, #/method. The selection is remembered per stage for the
  // session; a route without a symbol resolves to it, else to the stage's
  // first name, and the hash is rewritten to the resolved route (no new
  // history entry) so what is bookmarked is what is shown. The old
  // one-page anchors (#hold, #orders, #trade-X, #burst-X, #closest-miss,
  // #scan-details, #also-quiet) still land where they used to.
  const state = { view: 'explore', stage: null, selected: { bursts: null, 'setting-up': null }, query: '', range: 60, notice: '', picksKey: null, detailKey: null, gesture: false };
  let current = null, model = null, st = null, pendingNotice = '', pendingFocus = '', chooserOpener = null;
  let demo = false;   // the record is a pipeline-written fixture over a synthetic market
  const LEGACY = {
    hold: { view: 'record', anchor: 'hold' }, record: { view: 'record', anchor: 'record-card' }, breadth: { view: 'market' }, method: { view: 'method' },
    orders: { view: 'explore', open: 'orders' }, scan: { view: 'explore', open: 'scan' }, 'scan-details': { view: 'explore', open: 'scan' },
    'closest-miss': { view: 'explore', open: 'scan', anchor: 'closest-miss' }, tomorrow: { view: 'explore', stage: 'bursts' }, trades: { view: 'explore', stage: 'bursts' },
    alerts: { view: 'explore', stage: 'setting-up' }, 'also-quiet': { view: 'explore', stage: 'setting-up' }, cover: { view: 'explore' }, main: { view: 'explore' }, next: { view: 'explore', anchor: 'next' },
    following: { view: 'explore', anchor: 'following' }
  };
  function parseHash(hash) {
    hash = String(hash || '').replace(/^#/, '');
    if (!hash || hash === '/') return { view: 'explore' };
    if (hash.charAt(0) === '/') {
      const parts = hash.split('/').filter(Boolean).map((p) => { try { return decodeURIComponent(p); } catch (e) { return p; } });
      if (VIEWS.indexOf(parts[0]) < 0) return { view: 'explore', unknown: '#' + hash };
      if (parts[0] !== 'explore') return parts.length > 1 ? { view: parts[0], unknown: '#' + hash } : { view: parts[0] };
      const out = { view: 'explore' };
      if (parts.length > 1) { if (STAGES.indexOf(parts[1]) < 0) return { view: 'explore', unknown: '#' + hash }; out.stage = parts[1]; }
      if (parts.length > 2) out.ticker = parts[2].toUpperCase();
      if (parts.length > 3) out.unknown = '#' + hash;
      return out;
    }
    if (LEGACY[hash]) return Object.assign({ legacy: true }, LEGACY[hash]);
    let m = /^(?:trade|burst)-([A-Za-z0-9.\-]+)$/.exec(hash);
    if (m) return { view: 'explore', stage: 'bursts', ticker: m[1].toUpperCase(), legacy: true };
    m = /^alert-([A-Za-z0-9.\-]+)$/.exec(hash);
    if (m) return { view: 'explore', stage: 'setting-up', ticker: m[1].toUpperCase(), legacy: true };
    return { view: 'explore', unknown: '#' + hash };
  }
  SCStock.parseHash = parseHash;
  function routeHash(stage, id) {
    const c = id && model && model.byId[id];
    return '#/explore/' + stage + (c ? '/' + encodeURIComponent(c.ticker) : '');
  }
  function navigate(hash) {
    if (w.location.hash === hash) applyRoute(parseHash(hash));
    else w.location.hash = hash;
  }
  SCStock.navigate = navigate;
  const reducedMotion = () => !!(w.matchMedia && w.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const scrollTo = (node) => { if (node && node.scrollIntoView) node.scrollIntoView({ block: 'start', behavior: reducedMotion() ? 'auto' : 'smooth' }); };
  function applyRoute(route, first) {
    const previousView = state.view;
    state.view = VIEWS.indexOf(route.view) >= 0 ? route.view : 'explore';
    if (!model) { showView(false); return; }
    state.notice = route.unknown ? 'There is no ' + route.unknown + ' on this page; showing ' + (route.view === 'explore' ? 'Explore' : cap(route.view)) + '.' : pendingNotice;
    pendingNotice = '';
    let canon = '#/' + state.view;
    if (state.view === 'explore') {
      let stage = route.stage || state.stage || model.defaultStage;
      if (route.ticker) {
        const here = stage + ':' + route.ticker;
        if (model.byId[here]) state.selected[stage] = here;
        else {
          const other = STAGES.filter((s) => s !== stage).find((s) => model.byId[s + ':' + route.ticker]);
          if (other) {
            state.notice = route.ticker + ' is not in ' + STAGE_NAME[stage] + ' tonight; it is in ' + STAGE_NAME[other] + ', shown instead.';
            stage = other; state.selected[other] = other + ':' + route.ticker;
          } else state.notice = 'No stock ' + route.ticker + ' in tonight’s record' + (model.stages[stage].length ? '; showing ' + STAGE_NAME[stage] + ' instead.' : '.');
        }
      }
      state.stage = stage;
      const list = model.stages[stage];
      if (!state.selected[stage] || !model.byId[state.selected[stage]]) state.selected[stage] = list.length ? list[0].id : null;
      canon = routeHash(stage, state.selected[stage]);
    }
    showView(!first && previousView !== state.view);
    if (state.view === 'explore') renderExplore();
    if (w.location.hash !== canon && w.history && w.history.replaceState) { try { w.history.replaceState(null, '', canon); } catch (e) { /* a file: URL may refuse */ } }
    if (route.open) { const det = $(route.open); if (det) det.open = true; }
    if (route.open || route.anchor) { const target = $(route.anchor || route.open); if (target) scrollTo(target); }
  }
  function showView(scrollTop) {
    d.querySelectorAll('.ss-view').forEach((sec) => { sec.hidden = sec.getAttribute('data-view') !== state.view; });
    d.querySelectorAll('#nav a').forEach((a) => { if (a.getAttribute('data-view') === state.view) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
    d.documentElement.setAttribute('data-ss-view', state.view);
    if (scrollTop) w.scrollTo(0, 0);
  }

  // ---------------------------------------------------------------- Explore: the stages
  function buildStages() {
    const box = clear($('stages'));
    STAGES.forEach((s) => {
      const list = model.stages[s], n = list.length, tickets = model.tickets[s];
      const sub = s === 'bursts'
        ? (n ? tickets + ' with a ticket · ' + (n - tickets) + ' without' : 'range-expansion days, graded')
        : (n ? tickets + ' with a ticket · ' + (n - tickets) + ' to watch' : 'quiet, coiled names inside momentum');
      const btn = el('button', { 'class': 'ss-stage', type: 'button', 'data-stage': s, 'data-count': String(n), 'aria-pressed': 'false', 'aria-controls': 'workspace' }, [
        el('span', null, [el('span', { 'class': 'ss-stage__name', text: STAGE_NAME[s] }), el('span', { 'class': 'ss-stage__sub', text: sub })]),
        el('span', { 'class': 'ss-stage__count' }, [d.createTextNode(String(n)), el('small', { text: n === 1 ? 'stock' : 'stocks' })])
      ]);
      btn.addEventListener('click', () => { state.gesture = true; navigate(routeHash(s, state.selected[s])); });
      box.appendChild(btn);
    });
  }
  function syncStages() {
    d.querySelectorAll('#stages .ss-stage').forEach((b) => b.setAttribute('aria-pressed', b.getAttribute('data-stage') === state.stage ? 'true' : 'false'));
  }
  function buildDatalist() {
    const list = clear($('ticker-options')), seen = {};
    STAGES.forEach((s) => model.stages[s].forEach((c) => { if (!seen[c.ticker]) { seen[c.ticker] = true; list.appendChild(el('option', { value: c.ticker, label: STAGE_NAME[s] })); } }));
  }
  function renderExplore() {
    syncStages();
    renderPicks();
    renderDetail();
  }

  // ---------------------------------------------------------------- Explore: the stocks in a stage
  const matches = (c, q) => !q || c.ticker.indexOf(q) >= 0 || (c.name && c.name.toUpperCase().indexOf(q) >= 0);
  function setQuery(q) { state.query = q; $('search').value = q; if (model && state.view === 'explore') renderPicks(); }
  function pickItem(c) {
    const sw = statusWords(c.status);
    const btn = el('button', { 'class': 'ss-pick', type: 'button', 'data-id': c.id, 'data-ticker': c.ticker, 'data-status': c.status, 'aria-pressed': 'false', 'aria-controls': 'detail', tabindex: '-1' }, [
      el('span', { 'class': 'ss-pick__row' }, [
        el('span', { 'class': 'ss-pick__ticker sc-case', text: c.ticker }),
        c.grade ? chip(c.grade + (isNum(c.score) ? ' · ' + c.score.toFixed(1) : ''), 'brand', true) : null,
        chip(sw[0], sw[1])
      ]),
      el('span', { 'class': 'ss-pick__reason', text: pickReason(c) }),
      el('span', { 'class': 'ss-pick__measures' }, c.measures.map((m) => el('span', null, [m[0] + ' ', el('b', { text: m[1] })])))
    ]);
    btn.addEventListener('click', () => { state.gesture = true; navigate(routeHash(c.stage, c.id)); });
    btn.addEventListener('focus', () => { d.querySelectorAll('#pick-list .ss-pick').forEach((p) => { p.tabIndex = p === btn ? 0 : -1; }); });
    return el('div', { 'class': 'ss-pick-item', role: 'listitem' }, btn);
  }
  function emptyStage(stage) {
    const box = el('div', { 'class': 'ss-picks__empty', 'data-empty': stage }), run = current.run || {}, counts = model.counts;
    const other = STAGES.find((s) => s !== stage), otherN = model.stages[other].length;
    let why;
    if (stage === 'bursts') {
      why = run.session_state === 'closed' ? 'The market was closed on ' + dateWords(run.expected_session || run.session) + '; no burst was scanned.'
        : isNum(run.bursts) && run.bursts > 0 ? 'The scan found ' + num(run.bursts) + ' bursts; none was archived with its checks.'
        : 'No burst tonight: the scan found no 4% range-expansion day on ' + dateWords(run.session) + '.';
    } else {
      why = 'Nothing setting up tonight.' + (isNum(counts.coiled) ? ' The anticipation scans found ' + num(counts.coiled) + ' quiet ' + (counts.coiled === 1 ? 'stock' : 'stocks') + ' inside momentum' + (isNum(counts.admitted) ? ', ' + num(counts.admitted) + ' admitted' : '') + '.' : '');
    }
    box.appendChild(el('p', { text: why }));
    if (otherN) {
      const b = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', text: 'See ' + STAGE_NAME[other] + ' · ' + otherN });
      b.addEventListener('click', () => { state.gesture = true; navigate(routeHash(other, state.selected[other])); });
      box.appendChild(b);
    }
    return box;
  }
  function noMatch(stage, q) {
    const box = el('div', { 'class': 'ss-picks__empty', 'data-empty': 'search' });
    const other = STAGES.find((s) => s !== stage), elsewhere = model.stages[other].filter((c) => matches(c, q));
    box.appendChild(el('p', { text: 'No stock matching ‘' + q + '’ in ' + STAGE_NAME[stage] + (elsewhere.length ? '; ' + elsewhere.slice(0, 3).map((c) => c.ticker).join(', ') + (elsewhere.length === 1 ? ' matches' : ' match') + ' in ' + STAGE_NAME[other] + '.' : ', or anywhere in tonight’s record.') }));
    if (elsewhere.length) {
      const b = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', text: 'Show ' + elsewhere[0].ticker + ' in ' + STAGE_NAME[other] });
      b.addEventListener('click', () => { pendingNotice = elsewhere[0].ticker + ' is in ' + STAGE_NAME[other] + ' tonight; switched from ' + STAGE_NAME[stage] + '.'; setQuery(''); state.gesture = true; navigate(routeHash(other, elsewhere[0].id)); });
      box.appendChild(b);
    }
    const clearBtn = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', text: 'Clear search' });
    clearBtn.addEventListener('click', () => { setQuery(''); $('search').focus(); });
    box.appendChild(clearBtn);
    return box;
  }
  function renderPicks() {
    const stage = state.stage, list = model.stages[stage], q = state.query, host = $('pick-list');
    renderDiscover(stage);
    const shown = list.filter((c) => matches(c, q)), key = stage + '|' + q;
    $('picks-h2').textContent = STAGE_NAME[stage].toLowerCase() + ' · ' + list.length;
    if (state.picksKey !== key) {
      clear(host);
      if (!list.length) host.appendChild(emptyStage(stage));
      else if (!shown.length) host.appendChild(noMatch(stage, q));
      else shown.forEach((c) => host.appendChild(pickItem(c)));
      state.picksKey = key;
    }
    const sel = model.byId[state.selected[stage]];
    let seenSelected = false;
    host.querySelectorAll('.ss-pick').forEach((b) => { const on = !!sel && b.getAttribute('data-id') === sel.id; b.setAttribute('aria-pressed', on ? 'true' : 'false'); b.tabIndex = on ? 0 : -1; if (on) seenSelected = true; });
    if (!seenSelected) { const firstPick = host.querySelector('.ss-pick'); if (firstPick) firstPick.tabIndex = 0; }
    if (sel && state.gesture && narrow()) { const b = host.querySelector('.ss-pick[aria-pressed="true"]'); if (b && b.scrollIntoView) b.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: reducedMotion() ? 'auto' : 'smooth' }); }
    let status;
    if (!list.length) status = 'Nothing in ' + STAGE_NAME[stage] + ' tonight.';
    else if (q) status = shown.length + ' of ' + list.length + ' match ‘' + q + '’' + (shown.length ? '; Enter chooses the first.' : '.');
    else if (sel) status = sel.ticker + ' · ' + (list.indexOf(sel) + 1) + ' of ' + list.length + ' in ' + STAGE_NAME[stage] + '.';
    else status = '';
    $('picks-status').textContent = (state.notice ? state.notice + ' ' : '') + status;
  }
  function resolveSearch(q) {
    const stage = state.stage, here = model.stages[stage], hereMatch = here.filter((c) => matches(c, q));
    const exact = here.find((c) => c.ticker === q) || (hereMatch.length === 1 ? hereMatch[0] : null);
    if (exact) { setQuery(''); state.gesture = true; navigate(routeHash(stage, exact.id)); return; }
    const other = STAGES.find((s) => s !== stage), there = model.stages[other].filter((c) => matches(c, q));
    const found = model.stages[other].find((c) => c.ticker === q) || (there.length === 1 ? there[0] : null);
    if (found) { pendingNotice = found.ticker + ' is in ' + STAGE_NAME[other] + ' tonight; switched from ' + STAGE_NAME[stage] + '.'; setQuery(''); state.gesture = true; navigate(routeHash(other, found.id)); return; }
    state.query = q; renderPicks();
  }

  // ---------------------------------------------------------------- Explore: the chosen stock
  function detailEmpty(stage) {
    const box = el('div', { 'class': 'ss-chart-empty', 'data-detail': 'empty' });
    const cover = current.cover || {};
    box.appendChild(el('strong', { text: model.stages[stage].length ? 'Choose a stock. ' : 'Nothing to show for ' + STAGE_NAME[stage] + ' tonight. ' }));
    box.appendChild(d.createTextNode(model.stages[stage].length ? 'Its chart, its conditions and its conditional plan appear here.' : (cover.dek ? cover.dek + ' ' : '') + 'The market view has the breadth in full; the record view has the open model plans.'));
    return box;
  }
  function detailHead(c) {
    const b = c.row, run = current.run || {}, sw = statusWords(c.status), chips = [];
    if (c.grade) chips.push(chip(c.grade + (isNum(c.score) ? ' · ' + c.score.toFixed(1) : ''), 'brand', true));
    chips.push(chip(sw[0], sw[1]));
    if (c.stage === 'setting-up') (b.setups || []).forEach((s) => chips.push(chip(String(s), 'neutral', true)));
    c.flags.forEach((f) => chips.push(chip(FLAG_WORDS[f] || words(f), 'warn')));
    const last = c.series.length ? c.series[c.series.length - 1].date : run.session;
    const sub = c.stage === 'bursts'
      ? (c.name ? c.name + ' · ' : '') + usd(b.close) + ' · ' + pct(b.gain_pct) + ' on ' + (isNum(b.volume_vs_prior) ? b.volume_vs_prior.toFixed(1) : '—') + '× volume' + (b.scan && b.scan !== 'burst' ? ' · ' + words(b.scan) + ' scan' : '') + ' · rank ' + plain(c.rank)
      : (c.name ? c.name + ' · ' : '') + usd(b.close) + ' · ' + plain(b.quiet_days) + ' quiet days · ' + plain(b.range_pct) + '% range' + (c.quiet ? ' · also quiet' : ' · rank ' + plain(c.rank));
    const back = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm ss-detail__back', type: 'button', text: '↑ all stocks' });
    back.addEventListener('click', () => { scrollTo($('stages')); const sel = $('pick-list').querySelector('.ss-pick[aria-pressed="true"]'); if (sel) sel.focus({ preventScroll: true }); else $('search').focus({ preventScroll: true }); });
    return el('header', { 'class': 'ss-detail__head' }, [
      el('div', null, [
        el('div', { 'class': 'sc-eyebrow', text: STAGE_NAME[c.stage].toLowerCase() + ' · ' + (c.stage === 'bursts' ? 'burst on ' + dateWords(last) : 'coiled through ' + dateWords(last)) }),
        el('h2', { 'class': 'ss-detail__h2 sc-case', id: 'detail-h2', text: c.ticker }),
        el('p', { 'class': 'sc-hint ss-detail__sub', text: sub })
      ]),
      el('div', { 'class': 'ss-detail__chips' }, chips.concat([back]))
    ]);
  }
  // the one live chart: disposed (observers, tooltip, listeners) before another is drawn
  let chartHost = null;
  function disposeChart() { if (chartHost && chartHost.dispose) chartHost.dispose(); chartHost = null; }
  const chartHeight = () => (narrow() ? 300 : 400);
  // the plan's levels in one line beside the chart, the aim named even when it sits outside the visible range
  function referenceLine(c, g) {
    const plan = c.plan || {}, parts = [], burst = c.stage === 'bursts';
    const trig = burst ? plan.entry_ref : plan.trigger, lim = burst ? plan.entry_high : plan.limit;
    if (isNum(plan.stop)) parts.push('stop ' + usd(plan.stop));
    if (isNum(trig)) parts.push('trigger ' + usd(trig));
    if (isNum(lim)) parts.push('limit ' + usd(lim));
    if (burst && isNum(plan.entry_low) && isNum(trig) && Math.abs(plan.entry_low - trig) / trig > 0.005) parts.push('zone low ' + usd(plan.entry_low));
    const t = plan.targets || {};
    if (isNum(t.low) && isNum(t.high)) parts.push('aim +' + plain(t.low_pct) + '% ' + usd(t.low) + ' / +' + plain(t.high_pct) + '% ' + usd(t.high) + (g && g.target && g.target.offscale ? ' (outside the visible range)' : ''));
    return parts.length ? 'Levels: ' + parts.join(' · ') : 'No plan levels for this name.';
  }
  function mountChart(mount, c) {
    disposeChart();
    clear(mount);
    if (!c.series.length) {
      mount.style.minHeight = '';
      mount.appendChild(el('div', { 'class': 'ss-chart-empty', 'data-chart': 'unavailable' }, [
        el('strong', { text: 'Chart unavailable. ' }),
        'No daily bars are archived for ' + c.ticker + ' in tonight’s record' + (c.quiet ? ': it is on no list, so the run kept only its measures' : '') + '. The grade stands on the numbers; the conditions below carry them.'
      ]));
      return null;
    }
    const slice = rangeSlice(c, prefs.range), height = chartHeight();
    mount.style.minHeight = height + 'px';
    const host = SCStock.chart(slice.series, chartOptionsFor(c, slice.series, height));
    host.setAttribute('data-sessions', String(slice.series.length));
    host.setAttribute('data-ticker', c.ticker);
    host.setAttribute('data-stage', c.stage);
    host.setAttribute('data-range', slice.range);
    mount.appendChild(host);
    chartHost = host;
    return { host: host, slice: slice };
  }
  function detailChart(c) {
    const run = current.run || {}, all = c.series, last = all.length ? all[all.length - 1] : null;
    const panel = el('figure', { 'class': 'ss-chart-panel', 'data-mode': prefs.mode, 'data-range': prefs.range });
    // one header strip: the symbol, its last close and session; the mode and the range controls together; the legend for the mode
    const legendBox = el('div', { 'class': 'ss-chart-panel__legend' });
    const modeTabs = el('div', { 'class': 'sc-tabs', role: 'group', 'aria-label': 'Chart mode' });
    const rangeTabs = el('div', { 'class': 'sc-tabs', role: 'group', 'aria-label': 'Sessions shown' });
    const toggleInput = el('input', { type: 'checkbox', checked: prefs.closeLine ? '' : null });
    const toggle = el('label', { 'class': 'ss-chart-panel__toggle', hidden: prefs.mode === 'candles' ? null : '' }, [toggleInput, 'close line']);
    panel.appendChild(el('div', { 'class': 'ss-chart-panel__head' }, [
      el('div', { 'class': 'ss-chart-panel__id' }, [
        el('span', { 'class': 'sc-figure', text: c.ticker }),
        last && isNum(last.c) ? el('span', { 'class': 'ss-chart-panel__price', text: usd(last.c) }) : null,
        el('span', { 'class': 'sc-hint', text: last ? 'close ' + dateWords(last.date) : 'no bars archived' }),
        demo ? chip('demo data', 'warn') : null
      ]),
      el('div', { 'class': 'ss-chart-panel__tools' }, [modeTabs, el('div', { 'class': 'ss-chart-panel__group' }, [el('span', { 'class': 'ss-chart-panel__caption', 'aria-hidden': 'true', text: 'range' }), rangeTabs]), toggle])
    ]));
    const mount = el('div', { 'class': 'ss-chart-mount', id: 'chart-mount' });
    panel.appendChild(mount);
    const rangeLine = el('p', { 'class': 'ss-chart-panel__range' }), refLine = el('p', { 'class': 'ss-chart-panel__refs', 'data-refs': '' });
    panel.appendChild(el('figcaption', { 'class': 'sc-chart-caption' }, [
      legendBox, rangeLine, refLine,
      el('p', { text: (all.length ? 'Alpaca ' + String(run.feed || '').toUpperCase() + ' daily bars, drawn from the same numbers as the plan' : 'No bars archived for ' + c.ticker) + (c.row.chart ? ' · ' : '.') }, c.row.chart ? [el('a', { 'class': 'sc-link--quiet', href: c.row.chart, text: 'the chart the grader saw' })] : null)
    ]));
    let live = mountChart(mount, c);
    function disclose() {
      const g = chartHost && chartHost.geometry ? chartHost.geometry() : null, series = live ? live.slice.series : [];
      rangeLine.textContent = series.length ? 'Showing ' + plural(series.length, 'session') + ', ' + dateShort(series[0].date) + ' – ' + dateShort(series[series.length - 1].date) + ' ' + String(series[series.length - 1].date).slice(0, 4) + ' · ' + live.slice.note + '.' : '';
      refLine.textContent = referenceLine(c, g);
      clear(legendBox); if (chartHost && chartHost.legend) legendBox.appendChild(chartHost.legend());
      panel.setAttribute('data-mode', prefs.mode); panel.setAttribute('data-range', prefs.range);
      toggle.hidden = prefs.mode !== 'candles';
      modeTabs.querySelectorAll('.sc-tab').forEach((t) => t.setAttribute('aria-pressed', t.getAttribute('data-mode') === prefs.mode ? 'true' : 'false'));
      rangeTabs.querySelectorAll('.sc-tab').forEach((t) => t.setAttribute('aria-pressed', t.getAttribute('data-range') === prefs.range ? 'true' : 'false'));
    }
    CHART_MODES.forEach((m) => {
      const t = el('button', { 'class': 'sc-tab', type: 'button', 'data-mode': m, 'aria-pressed': m === prefs.mode ? 'true' : 'false', text: MODE_WORDS[m], disabled: all.length ? null : '' });
      t.addEventListener('click', () => { prefs.mode = m; savePrefs(); if (chartHost) chartHost.update({ mode: m, closeLine: prefs.closeLine }); disclose(); });
      modeTabs.appendChild(t);
    });
    CHART_RANGES.forEach((r) => {
      const t = el('button', { 'class': 'sc-tab', type: 'button', 'data-range': r, 'aria-pressed': r === prefs.range ? 'true' : 'false', 'aria-label': RANGE_WORDS[r], title: RANGE_WORDS[r], disabled: all.length ? null : '', text: r === 'setup' ? 'setup' : r });
      t.addEventListener('click', () => {
        prefs.range = r; savePrefs();
        if (!chartHost) return;
        const slice = rangeSlice(c, r);
        chartHost.update(Object.assign({ series: slice.series }, chartOptionsFor(c, slice.series, chartHeight())));
        chartHost.setAttribute('data-sessions', String(slice.series.length)); chartHost.setAttribute('data-range', slice.range);
        live = { host: chartHost, slice: slice };
        disclose();
      });
      rangeTabs.appendChild(t);
    });
    toggleInput.addEventListener('change', () => { prefs.closeLine = !!toggleInput.checked; savePrefs(); if (chartHost) chartHost.update({ closeLine: prefs.closeLine }); });
    disclose();
    return panel;
  }
  // ---------------------------------------------------------------- discovery: Cards | Map (Bursts only)
  // The map is an overview of the stage's bursts by the recorded session's
  // gain and volume ratio, on the page's one selection state; the cards and
  // the map are two views of the same list, and the choice is a preference
  // kept in this browser. Setting up is never mapped: its names have not burst.
  const DISCOVER_KEY = 'spicystock:discover:v1';
  let discover = 'cards', mapView = null;
  function loadDiscover() { try { const v = w.localStorage && w.localStorage.getItem(DISCOVER_KEY); if (v === 'map' || v === 'cards') discover = v; } catch (e) { /* the default stands */ } }
  function saveDiscover() { try { w.localStorage.setItem(DISCOVER_KEY, discover); } catch (e) { /* not remembered */ } }
  function mapPoints() {
    return model.stages.bursts.map((c) => ({
      id: c.id, ticker: c.ticker, gain: isNum(c.row.gain_pct) ? c.row.gain_pct : null, volume: isNum(c.row.volume_vs_prior) ? c.row.volume_vs_prior : null,
      grade: c.grade, score: c.score, rank: c.rank, statusWords: statusWords(c.status)[0], statusTone: statusWords(c.status)[1],
      source: c.row.claude && c.row.claude.source === 'claude' ? 'claude' : (c.row.quality && c.row.quality.checks ? 'checklist' : null),
      chartSeen: c.row.claude ? c.row.claude.chart_seen : null
    }));
  }
  function unmountMap() {
    if (mapView) { mapView.dispose(); mapView = null; }
    const host = $('burst-map'); if (host) host.parentNode.removeChild(host);
  }
  function mountMap() {
    const ws = $('workspace'), run = current.run || {};
    let host = $('burst-map');
    if (host && mapView) { mapView.update(state.selected.bursts); return; }
    unmountMap();
    host = el('div', { id: 'burst-map' });
    const picks = $('picks'), head = picks ? picks.querySelector('.ss-picks__head') : null;
    if (head) picks.insertBefore(host, head.nextSibling); else ws.insertBefore(host, ws.firstChild);
    mapView = SCStock.map.render(host, { points: mapPoints(), selectedId: state.selected.bursts, sessionWords: dateWords(run.session), demo: demo,
      onSelect: (id) => { state.gesture = true; navigate(routeHash('bursts', id)); } });
  }
  function renderDiscover(stage) {
    const ctl = $('discover'), ws = $('workspace');
    if (!ctl || !ws) return;
    ctl.hidden = stage !== 'bursts';
    if (!ctl.childElementCount) {
      [['cards', 'Cards'], ['map', 'Map']].forEach((pair) => {
        const t = el('button', { 'class': 'sc-tab', type: 'button', 'data-discover': pair[0], 'aria-pressed': 'false', text: pair[1] });
        t.addEventListener('click', () => { discover = pair[0]; saveDiscover(); renderDiscover(state.stage); if (discover === 'map' && mapView) mapView.focusSelected(); });
        ctl.appendChild(t);
      });
    }
    ctl.querySelectorAll('.sc-tab').forEach((t) => t.setAttribute('aria-pressed', t.getAttribute('data-discover') === discover ? 'true' : 'false'));
    const mapMode = stage === 'bursts' && discover === 'map';
    ws.setAttribute('data-discover', mapMode ? 'map' : 'cards');
    if (mapMode) mountMap(); else unmountMap();
  }

  // ---------------------------------------------------------------- Following: a saved setup, in this browser
  // The button saves the setup's own snapshot with its suggested whole-share
  // quantity; one optional reference size is the reader's and changes
  // nothing else. The shelf shows each saved setup against the newest bar the
  // record carries for it (observations, else the record's own rows), and
  // never says bought, filled, held, sold or stopped out.
  function followSetupOf(c) {
    const run = current.run || {}, app = current.app || {}, plan = c.plan || {}, t = plan.targets || {}, b = c.row;
    const burst = c.stage === 'bursts';
    const hasTicket = c.status === 'ticket' && isNum(plan.shares) && plan.shares > 0;
    return {
      ticker: c.ticker, kind: burst ? 'burst' : 'anticipation', stage: c.stage, session: run.session || '', rules_version: app.rules_version || '',
      suggested_shares: hasTicket ? plan.shares : null,
      snapshot: {
        name: c.name || '', close: isNum(b.close) ? b.close : null, close_date: run.session || '', grade: c.grade || null, score: isNum(c.score) ? c.score : null,
        status: c.status, status_words: statusWords(c.status)[0],
        levels: { entry_low: burst ? plan.entry_low : plan.trigger, entry_high: burst ? plan.entry_high : plan.limit, trigger: burst ? plan.entry_ref : plan.trigger,
          limit: burst ? plan.entry_high : plan.limit, stop: plan.stop, stop_basis: plan.stop_basis || null,
          target_low: t.low, target_high: t.high, target_low_pct: t.low_pct, target_high_pct: t.high_pct },
        order_line: text(plan.order_line), instruction: entryInstruction(plan), summary: burst ? sentence(firstSentence(text(b.summary).replace(/^[A-Z0-9.\-]+:\s*/, ''))) : pickReason(c),
        withheld_reason: c.status !== 'ticket' ? text(c.reason) : ''
      }
    };
  }
  // the newest bar the record carries for a symbol: the observation block, else the record's own rows
  function latestObservation(ticker) {
    const obs = ((current.observations || {}).symbols || {})[ticker];
    if (obs && text(obs.date) && isNum(obs.c)) return { date: obs.date, close: obs.c, source: 'observations' };
    const run = current.run || {};
    const b = (current.bursts || []).find((x) => x && x.ticker === ticker);
    if (b && isNum(b.close) && run.session) return { date: run.session, close: b.close, source: 'burst' };
    const r = ((current.watchlist || {}).top || []).concat((current.watchlist || {}).also_quiet || []).find((x) => x && x.ticker === ticker);
    if (r && isNum(r.close) && run.session) return { date: run.session, close: r.close, source: 'watchlist' };
    const o = (current.open_plans || []).find((x) => x && x.ticker === ticker);
    if (o && isNum(o.last_close) && text(o.last_date)) return { date: o.last_date, close: o.last_close, source: 'open plan' };
    return null;
  }
  const modelUpdateOf = (item) => (current.open_plans || []).find((o) => o && o.ticker === item.ticker && o.picked === item.session) || null;
  let followStatus = null;
  function followJump() {
    const link = $('following-jump'); if (!link) return;
    const n = SCStock.follow.list().length;
    link.textContent = 'Following · ' + n;
    link.hidden = false;
  }
  function followBlock(c) {
    const setup = followSetupOf(c), id = SCStock.follow.identity(setup), st0 = SCStock.follow.status();
    const item = st0.available ? SCStock.follow.find(id) : null;
    const box = el('div', { 'class': 'ss-follow', 'data-follow': item ? 'following' : 'not-following', 'data-follow-id': id });
    const redraw = () => { const next = followBlock(c); box.parentNode.replaceChild(next, box); return next; };
    const warn = (msg) => { box.querySelectorAll('.ss-follow__warn').forEach((x) => x.remove()); box.appendChild(el('p', { 'class': 'ss-follow__warn', role: 'alert', text: msg })); };
    if (!st0.available) {
      box.appendChild(chip('not saved', 'neutral'));
      warn(st0.error || 'Storage is blocked in this browser; nothing can be followed here.');
      return box;
    }
    if (!item) {
      const btn = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', text: 'Follow this setup', 'data-follow-action': 'add' });
      btn.addEventListener('click', () => {
        const res = SCStock.follow.add(setup);
        if (!res.ok) { warn(res.error); return; }
        redraw(); renderFollowing(); followJump();
      });
      box.appendChild(btn);
      box.appendChild(el('p', { 'class': 'ss-follow__hint', text: setup.suggested_shares ? plural(setup.suggested_shares, 'share') + ' suggested by the plan · saved in this browser only' : (c.status === 'ticket' ? 'for observation, no size suggested' : 'for observation, no ticket: ' + (statusWords(c.status)[0]) + ' · saved in this browser only') }));
      return box;
    }
    box.appendChild(chip('following', 'good'));
    const size = isNum(item.reference_shares) ? 'your reference size ' + plural(item.reference_shares, 'share') + (isNum(item.suggested_shares) ? ' (plan suggested ' + item.suggested_shares + ')' : '') : (isNum(item.suggested_shares) ? plural(item.suggested_shares, 'share') + ' suggested by the plan' : 'for observation, no size');
    box.appendChild(el('p', { 'class': 'ss-follow__hint', text: size + ' · saved in this browser, not a broker fill' }));
    const edit = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', text: 'Edit size', 'data-follow-action': 'edit' });
    const undo = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', text: 'Undo', 'data-follow-action': 'remove' });
    const link = el('a', { 'class': 'sc-link--quiet', href: '#following', text: 'Following shelf' });
    edit.addEventListener('click', () => {
      const form = el('form', { 'class': 'ss-follow__form', novalidate: '' });
      const input = el('input', { 'class': 'sc-input', type: 'number', min: '1', max: String(SCStock.follow.SHARES_MAX), step: '1', inputmode: 'numeric', value: String(isNum(item.reference_shares) ? item.reference_shares : (item.suggested_shares || 1)), 'aria-label': 'Your reference size in whole shares' });
      const save = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'submit', text: 'Save size' });
      const cancel = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', text: 'Cancel' });
      const clearBtn = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', text: 'Use the suggested size', hidden: isNum(item.reference_shares) ? null : '' });
      form.appendChild(input); form.appendChild(save); form.appendChild(clearBtn); form.appendChild(cancel);
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const n = input.value.trim() === '' ? NaN : Number(input.value);
        const res = SCStock.follow.setShares(id, Number.isInteger(n) ? n : NaN);
        if (!res.ok) { warn(res.error); return; }
        redraw(); renderFollowing();
      });
      clearBtn.addEventListener('click', () => { const res = SCStock.follow.setShares(id, null); if (!res.ok) { warn(res.error); return; } redraw(); renderFollowing(); });
      cancel.addEventListener('click', () => { redraw(); });
      edit.replaceWith(form); input.focus();
    });
    undo.addEventListener('click', () => { const res = SCStock.follow.remove(id); if (!res.ok) { warn(res.error); return; } redraw(); renderFollowing(); followJump(); });
    box.appendChild(edit); box.appendChild(undo); box.appendChild(link);
    return box;
  }
  function followedCard(item) {
    const snap = item.snapshot || {}, lv = snap.levels || {}, obs = latestObservation(item.ticker), upd = modelUpdateOf(item);
    const card = el('article', { 'class': 'ss-followed', 'data-follow-id': item.id, 'data-ticker': item.ticker });
    const open = el('button', { 'class': 'ss-followed__ticker sc-case', type: 'button', text: item.ticker, 'data-open': routeHash(item.stage === 'setting-up' ? 'setting-up' : 'bursts', item.stage + ':' + item.ticker) });
    open.addEventListener('click', () => { pendingFocus = 'detail'; state.gesture = true; navigate(open.getAttribute('data-open')); });
    card.appendChild(el('div', { 'class': 'ss-followed__row' }, [open, el('span', { 'class': 'ss-followed__meta', text: (item.kind === 'anticipation' ? 'setting up' : 'burst') + ' · signal ' + dateWords(item.session) }), snap.status_words ? chip(snap.status_words, snap.status === 'ticket' ? 'good' : 'neutral') : null, item.demo ? chip('demo', 'warn') : null]));
    const dl = el('dl');
    const row = (dt, dd) => { if (dd) dl.appendChild(el('div', null, [el('dt', { text: dt }), el('dd', { text: dd })])); };
    row('size', isNum(item.reference_shares) ? 'your reference size ' + plural(item.reference_shares, 'share') + (isNum(item.suggested_shares) ? ' · plan suggested ' + item.suggested_shares : '') : (isNum(item.suggested_shares) ? plural(item.suggested_shares, 'share') + ' suggested' : 'observation only, no size'));
    const newer = obs && obs.date > (snap.close_date || '');
    if (obs) row('latest close', usd(obs.close) + ' · ' + dateWords(obs.date) + (newer ? '' : ' · no newer observation available'));
    else row('latest close', 'no observation in this record · last seen ' + dateWords(snap.close_date) + (isNum(snap.close) ? ' at ' + usd(snap.close) : ''));
    if (newer && isNum(snap.close) && snap.close > 0) row('since the signal', pct((obs.close / snap.close - 1) * 100) + ' from the ' + usd(snap.close) + ' close on ' + dateShort(snap.close_date) + ' · price movement on the record’s bars, not your result');
    const levels = [];
    if (isNum(lv.trigger)) levels.push('trigger ' + usd(lv.trigger));
    if (isNum(lv.limit)) levels.push('limit ' + usd(lv.limit));
    if (isNum(lv.stop)) levels.push('stop ' + usd(lv.stop));
    if (isNum(lv.target_low) && isNum(lv.target_high)) levels.push('aim ' + usd(lv.target_low) + '–' + usd(lv.target_high));
    row('saved plan', levels.length ? levels.join(' · ') : 'no plan levels');
    if (upd) row('model update', 'day ' + plain(upd.day) + ' · ' + (PLAN_STATUS[upd.status] ? PLAN_STATUS[upd.status][0] : words(upd.status)) + (isNum(upd.current_stop) ? ' · stop now ' + usd(upd.current_stop) : '') + ' (the model plan, separate from your saved plan)');
    card.appendChild(dl);
    const note = upd && text(upd.instruction) ? upd.instruction : (snap.instruction || snap.summary || snap.withheld_reason || '');
    if (note) card.appendChild(el('p', { 'class': 'ss-followed__note' }, [el('span', { 'class': 'ss-followed__note-label', text: upd && text(upd.instruction) ? 'the model plan says' : 'the record says' }), ' “' + note + '”']));
    const actions = el('div', { 'class': 'ss-followed__actions' });
    const openBtn = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', text: 'Open chart' });
    openBtn.addEventListener('click', () => open.click());
    const remove = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', text: 'Remove' });
    remove.addEventListener('click', () => { const res = SCStock.follow.remove(item.id); if (!res.ok) { setFollowStatus(res.error); return; } renderFollowing(); followJump(); if (state.view === 'explore') renderDetailFollow(); });
    actions.appendChild(openBtn); actions.appendChild(remove);
    card.appendChild(actions);
    return card;
  }
  function setFollowStatus(msg) { const p = $('following-status'); if (!p) return; p.textContent = msg || ''; p.hidden = !msg; }
  function renderFollowing() {
    const list = $('following-list'), count = $('following-count');
    if (!list) return;
    clear(list);
    const st0 = SCStock.follow.status(), items = st0.available ? SCStock.follow.list() : [];
    if (count) count.textContent = items.length ? plural(items.length, 'setup') + ' · saved in this browser' : 'saved in this browser';
    setFollowStatus(st0.error || '');
    if (!items.length) { list.appendChild(el('div', { 'class': 'ss-following__empty', text: st0.available ? 'Nothing followed yet. Follow a setup from its action area to keep it in view here; it is saved in this browser only, and a saved plan is never a trade.' : 'Nothing can be followed in this browser.' })); return; }
    items.slice().reverse().forEach((it) => list.appendChild(followedCard(it)));
  }
  // the chosen stock's follow block, redrawn after a change made from the shelf
  function renderDetailFollow() {
    const box = d.querySelector('#detail .ss-follow'), c = model && model.byId[state.selected[state.stage]];
    if (box && c) box.parentNode.replaceChild(followBlock(c), box);
  }

  function entryInstruction(plan) {
    const s = ((plan || {}).exit_schedule || []).find((x) => x && (x.key === 'entry' || x.day === 1));
    return s && text(s.instruction) ? cap(sentence(s.instruction)) : '';
  }
  function firstText() { for (let i = 0; i < arguments.length; i++) { const v = arguments[i]; if (typeof v === 'string' && v.trim()) return v; if (Array.isArray(v) && v.length && typeof v[0] === 'string' && v[0].trim()) return v[0]; } return ''; }
  function burstDecision(c) {
    const b = c.row, plan = c.plan || {}, q = b.quality || {}, cl = b.claude || {}, checks = q.checks || [];
    const passes = checks.filter((x) => x && x.pass).length, miss = checks.find((x) => x && !x.pass);
    const summary = sentence(firstSentence(text(b.summary).replace(/^[A-Z0-9.\-]+:\s*/, '')));
    const why = [summary || 'No summary was recorded for this burst.',
      checks.length ? passes + ' of ' + checks.length + ' checks pass (' + plain(q.passes) + ' of the ' + plain(q.of) + ' letters)' + (miss ? '; the miss is ‘' + (miss.label || words(miss.key) || 'a check') + '’ (' + (miss.display || '—') + ').' : '; nothing missed.') : '',
      cl.source === 'claude' && text(cl.reason) ? 'The chart reader: ' + sentence(cl.reason) : ''];
    const entry = entryInstruction(plan);
    const need = c.status === 'ticket'
      ? [entry || (text(plan.order_line) ? sentence(plan.order_line) : 'The plan carries no entry instruction.')]
      : [c.plan ? 'No ticket tonight (' + statusWords(c.status)[0] + '). The setup would need: ' + (entry || 'an entry the plan does not spell out.') : 'Nothing: ' + sentence(c.reason)];
    const wait = c.plan
      ? [text(plan.pre_open_check) ? cap(sentence(plan.pre_open_check)) : '', isNum(plan.stop) ? 'Stop ' + stopWords(plan) + (plan.stop_basis !== 'max_stop' && isNum(plan.stop_pct) && isNum(plan.sizing_price) ? ' · ' + plain(plan.stop_pct) + '% under the ' + usd(plan.sizing_price) + ' limit' : '') + '.' : '']
      : [cap(sentence(c.reason))];
    const riskText = firstText(cl.key_risk, plan.stop_risk_reason, plan.hazards, plan.notes);
    const risk = [riskText ? cap(sentence(riskText)) : (c.flags.length ? cap(c.flags.map((f) => FLAG_WORDS[f] || words(f)).join(', ')) + '.' : 'None recorded beyond the method’s own: paper prices, one venue’s prints, no slippage.'),
      c.series.length ? '' : 'No bars are archived for this name, so there is no chart to read.'];
    return [['why', 'Why this stock?', why], ['need', 'What would need to happen?', need], ['wait', 'What invalidates it, or makes me wait?', wait], ['risk', 'Principal risk or limitation', risk]];
  }
  function coilDecision(c) {
    const r = c.row, plan = c.plan || {}, box = r.box || {}, wl = current.watchlist || {};
    const why = [(r.setups && r.setups.length ? r.setups.join(', ') + ': ' : '') + plain(r.quiet_days) + ' quiet days, ' + plain(r.range_pct) + '% range' + (isNum(box.sessions) ? ', a box of ' + plain(box.sessions) + ' sessions between ' + usd(box.low) + ' and ' + usd(box.high) : '') + (r.vol_dry ? ', volume dry' : '') + '.',
      c.quiet ? 'Also quiet: quiet inside momentum, on no list tonight.' : ''];
    const entry = entryInstruction(plan);
    const need = c.status === 'ticket'
      ? [entry || (text(plan.order_line) ? sentence(plan.order_line) : 'The plan carries no entry instruction.')]
      : [c.plan ? 'No ticket tonight (' + statusWords(c.status)[0] + '). The setup would need: ' + (entry || sentence(wl.instruction) || 'an entry the plan does not spell out.') : (text(wl.instruction) ? sentence(wl.instruction) : 'The run wrote no plan for it.')];
    const wait = c.plan
      ? [text(plan.gap_rule) ? cap(sentence(plan.gap_rule)) : '', isNum(plan.stop) ? 'Stop ' + usd(plan.stop) + (text(plan.stop_basis) ? ' · ' + plan.stop_basis : '') + (isNum(plan.stop_pct) && isNum(plan.limit) ? ' · ' + plain(plan.stop_pct) + '% under the ' + usd(plan.limit) + ' limit' : '') + '.' : '']
      : [cap(sentence(c.reason))];
    const riskText = firstText(plan.stop_risk_reason, plan.hazards, plan.notes);
    const risk = [riskText ? cap(sentence(riskText)) : (c.flags.length ? cap(c.flags.map((f) => FLAG_WORDS[f] || words(f)).join(', ')) + '.' : 'None recorded beyond the method’s own: paper prices, one venue’s prints, no slippage.'),
      c.series.length ? '' : 'No bars are archived for this name, so there is no chart to read.'];
    return [['why', 'Why this stock?', why], ['need', 'What would need to happen?', need], ['wait', 'What invalidates it, or makes me wait?', wait], ['risk', 'Principal risk or limitation', risk]];
  }
  function decisionSummary(c) {
    const items = c.stage === 'bursts' ? burstDecision(c) : coilDecision(c);
    return el('section', { 'class': 'ss-decision', 'aria-label': 'Decision summary' }, items.map((it) =>
      el('div', { 'class': 'ss-decision__item', 'data-item': it[0] }, [el('h3', { 'class': 'sc-eyebrow', text: it[1] })].concat(it[2].filter(Boolean).map((p) => el('p', { text: p }))))));
  }
  const stateWords = (s) => s.state === 'pending' ? 'waiting for tonight’s run' : s.state === 'failed' ? 'without a verdict' : 'stale';
  function openDisclosure(id) {
    const det = $(id); if (!det) return;
    det.open = true; scrollTo(det);
    const s = det.querySelector('summary'); if (s) { s.tabIndex = 0; s.focus({ preventScroll: true }); }
  }
  function actionArea(c) {
    const sw = statusWords(c.status), blockedNow = !!(st && blocked(st)), plan = c.plan || {};
    const box = el('div', { 'class': 'ss-action', 'data-ticket': c.status === 'ticket' ? (blockedNow ? 'blocked' : 'order') : c.status });
    let line, btn;
    if (c.status === 'ticket' && !blockedNow) {
      line = 'Conditional ticket: ' + (text(plan.order_line) ? plan.order_line : 'see the plan') + '. It fills only on its own terms tomorrow; nothing here is placed for you.';
      btn = el('button', { 'class': 'sc-btn sc-btn--secondary', type: 'button', text: 'View conditional plan', 'data-open': 'disc-plan' });
      box.appendChild(chip(sw[0], sw[1]));
    } else if (c.status === 'ticket') {
      line = 'The ticket is not offered from a page that is ' + stateWords(st) + '. ' + sentence(st.sentence);
      btn = el('button', { 'class': 'sc-btn sc-btn--secondary', type: 'button', text: 'Inspect conditions', 'data-open': 'disc-checklist' });
      box.appendChild(chip('not offered', 'warn'));
    } else {
      line = (c.reason ? cap(sentence(c.reason)) : 'No ticket tonight.') + (c.plan ? ' The setup is kept here for inspection.' : '');
      btn = el('button', { 'class': 'sc-btn sc-btn--secondary', type: 'button', text: 'Inspect conditions', 'data-open': 'disc-checklist' });
      box.appendChild(chip(sw[0], sw[1]));
    }
    box.appendChild(el('p', { text: line }));
    btn.addEventListener('click', () => openDisclosure(btn.getAttribute('data-open')));
    box.appendChild(btn);
    box.appendChild(followBlock(c));
    return box;
  }
  function disclosure(id, title, hint, kids) {
    return el('details', { 'class': 'sc-disclosure', id: id }, [
      el('summary', null, [d.createTextNode(title), hint ? el('span', { 'class': 'sc-muted', text: ' · ' + hint }) : null]),
      el('div', { 'class': 'sc-disclosure__body' }, kids)
    ]);
  }
  function factList(pairs) {
    const dl = el('dl', { 'class': 'sc-facts' });
    pairs.forEach((p) => { if (!p) return; dl.appendChild(el('div', { 'class': p[3] ? 'is-wide' : null }, [el('dt', { text: p[0] }), el('dd', null, [p[1], p[2] ? el('small', { text: p[2] }) : null])])); });
    return dl;
  }
  function checkTile(c, vetoed) {
    const tone = vetoed ? 'blocked' : !c ? null : c.pass ? (c.marginal ? 'caution' : 'good') : 'blocked';
    const glyph = vetoed ? '✕' : !c ? '—' : c.pass ? (c.marginal ? '~' : '✓') : '✕';
    const word = vetoed ? 'veto' : !c ? 'not measured' : c.pass ? (c.marginal ? 'partial' : 'pass') : (c.status === 'unmeasured' ? 'not measured' : 'fail');
    const display = c ? String(c.display || '') : '', threshold = c ? String(c.threshold || '') : '';
    return el('div', { 'class': 'sc-signal' + (tone ? ' sc-signal--' + tone : ''), 'data-check': c ? c.key : null, 'data-verdict': word, title: c ? [display, threshold ? 'threshold: ' + threshold : '', c.note].filter(Boolean).join('\n') : null }, [
      el('span', { 'class': 'ss-check__label', text: c ? (c.label || words(c.key)) : '—' }),
      el('span', { 'class': 'sc-signal__glyph', 'aria-hidden': 'true', text: glyph }),
      el('span', { 'class': 'sc-signal__label', text: word + (display ? ' · ' + display.split(' ')[0] : '') }),
      c ? el('span', { 'class': 'sc-signal__note', text: threshold.length > 64 ? threshold.slice(0, 62).replace(/\s+\S*$/, '') + '…' : threshold }) : null
    ]);
  }
  function discChecklist(c) {
    const kids = [];
    if (c.stage === 'bursts') {
      const b = c.row, q = b.quality || {}, base = q.base || {}, checks = q.checks || [], vetoes = q.vetoes || [];
      const passes = checks.filter((x) => x && x.pass).length;
      kids.push(el('p', { 'class': 'sc-hint', text: checks.length ? 'Bonde’s ' + checks.length + ' A-quality criteria: the verdict in words, the measured value, his threshold. ' + passes + ' of ' + checks.length + ' pass (' + plain(q.passes) + ' of the ' + plain(q.of) + ' letters).' : 'No checklist was archived for this burst.' }));
      if (checks.length) kids.push(el('div', { 'class': 'ss-checks' }, checks.map((x) => checkTile(x, (x.key === 'two_days' && vetoes.indexOf('up_days') >= 0) || (x.key === 'linearity' && vetoes.indexOf('not_linear') >= 0)))));
      if (vetoes.length) kids.push(el('p', { 'class': 'sc-note', text: 'Veto: ' + vetoes.map((v) => VETO_WORDS[v] || words(v)).join(', ') + '.' }));
      kids.push(el('div', { 'class': 'sc-eyebrow', text: 'the measurements' }));
      kids.push(factList([
        ['the burst', pct(b.gain_pct) + ' · ' + (isNum(b.volume_vs_prior) ? b.volume_vs_prior.toFixed(1) : '—') + '× volume', 'open ' + usd(b.open) + ' · high ' + usd(b.high) + ' · low ' + usd(b.low) + ' · close ' + usd(b.close) + ' · prior close ' + usd(b.prev_close)],
        ['the base', isNum(base.sessions) ? plain(base.sessions) + ' sessions · ' + plain(base.depth_pct) + '% deep' : '—', base.start && base.end ? dateShort(base.start) + ' to ' + dateShort(base.end) + ' · ' + usd(base.low) + '–' + usd(base.high) + ((base.breakdown_dates || []).length ? ' · ' + plural(base.breakdown_dates.length, 'breakdown') : '') : ''],
        ['dollar volume', isNum(b.dollar_volume) ? usd(b.dollar_volume, 0) : '—', b.scan ? words(b.scan) + ' scan' : ''],
        ['extension', isNum(b.extension_pct) ? pct(b.extension_pct) : '—', 'close against its 20-session average'],
        ['grade', (b.grade || '—') + (isNum(b.score) ? ' · ' + b.score.toFixed(1) : ''), (b.grade_mechanical && b.grade_mechanical !== b.grade ? 'the checklist said ' + b.grade_mechanical : 'the checklist’s own grade') + (q.reclass ? ' · reclassified: ' + words(q.reclass) : '')]
      ]));
      if (q.notes && q.notes.length) kids.push(el('ul', { 'class': 'ss-notes' }, q.notes.map((n) => el('li', { text: n }))));
    } else {
      const r = c.row, box = r.box || {}, wl = current.watchlist || {};
      kids.push(el('p', { 'class': 'sc-hint', text: c.quiet ? 'Quiet inside momentum, on no list tonight: the measures the scan kept.' : 'The anticipation scans’ measures for this coil; the plan reads the box.' }));
      kids.push(factList([
        ['setups', (r.setups || []).length ? r.setups.join(', ') : '—', (r.reasons_failed || []).length ? 'not: ' + r.reasons_failed.join(', ') : ''],
        ['quiet', plain(r.quiet_days) + ' days', isNum(r.narrow_range_days) ? plain(r.narrow_range_days) + ' narrow-range days' + (r.tight_today ? ' · tight today' : '') : ''],
        ['range', plain(r.range_pct) + '%', (isNum(r.range_recent_pct) ? 'recent ' + plain(r.range_recent_pct) + '%' : '') + (isNum(r.range_base_pct) ? ' · base ' + plain(r.range_base_pct) + '%' : '') + (isNum(r.adr20_pct) ? ' · 20-day ADR ' + plain(r.adr20_pct) + '%' : '')],
        ['the box', isNum(box.sessions) ? plain(box.sessions) + ' sessions · ' + usd(box.low) + '–' + usd(box.high) : '—', box.start && box.end ? dateShort(box.start) + ' to ' + dateShort(box.end) + (isNum(box.spread) ? ' · spread ' + plain(box.spread) + '%' : '') : ''],
        ['volume', isNum(r.volume_ratio) ? r.volume_ratio.toFixed(2) + '× its average' : '—', r.vol_dry ? 'dry' : ''],
        ['momentum', isNum(r.ti65) ? 'TI65 ' + r.ti65.toFixed(3) : (isNum(r.extension) ? 'extension ' + r.extension.toFixed(2) : '—'), (isNum(r.up_run) ? plain(r.up_run) + ' up days in a row' : '') + (isNum(r.breakdowns) ? ' · ' + plural(r.breakdowns, 'breakdown') : '')],
        ['close', usd(r.close), isNum(r.pct_change_today) ? pct(r.pct_change_today) + ' today' : '']
      ]));
      if (text(wl.instruction)) kids.push(el('p', { 'class': 'sc-note', text: 'The list’s rule: ' + sentence(wl.instruction) }));
    }
    return disclosure('disc-checklist', 'Conditions and measurements', c.stage === 'bursts' ? 'the checklist' : 'the coil', kids);
  }
  function discPlan(c) {
    const plan = c.plan, acct = current.account || {}, rules = (current.rules || {}).plan || {}, kids = [];
    if (!plan) {
      kids.push(el('p', { 'class': 'sc-hint', text: 'No plan: ' + sentence(c.reason) + (c.stage === 'bursts' ? ' A grade, a plan and a ticket are three different things; this burst has the first.' : '') }));
      return disclosure('disc-plan', 'Conditional plan, sizing and order', 'none', kids);
    }
    const blockedNow = !!(st && blocked(st)), withheld = c.status !== 'ticket' || blockedNow, t = plan.targets || {};
    if (c.stage === 'bursts') {
      kids.push(factList([
        ['buy', usd(plan.entry_low) + ' – ' + usd(plan.entry_high), (plan.entry_window || '') + ' · a buy stop at ' + usd(plan.entry_ref) + ', limit ' + usd(plan.entry_high), true],
        ['skip if it opens above', usd(plan.skip_if_open_above), 'day 2 is spent; a resting order could still fill on a pullback, so cancel it'],
        ['skip if it opens below', usd(plan.skip_if_open_below), 'the burst is failing; do not place it'],
        ['stop', stopWords(plan), 'judged at the ' + usd(plan.sizing_price) + ' limit · move it to your entry day’s low once filled', true],
        ['sized at', usd(plan.sizing_price), 'the limit, the highest fill the ticket permits · indicative entry ' + usd(plan.planned_entry) + ' (not a fill)', true],
        ['risk per share', usd(plan.risk_per_share), 'limit − stop'],
        ['shares', num(plan.shares), plan.capped_by === 'position_cap' ? 'cut by the position cap' : 'from ' + usd(plan.risk_usd) + ' ÷ ' + usd(plan.risk_per_share)],
        ['position', usd(plan.position_usd), (isNum(plan.position_pct) ? plan.position_pct.toFixed(1) : '—') + '% of the configured ' + usd(acct.equity, 0)],
        ['planned risk', usd(plan.risk_usd), 'price-to-stop at the limit, not a maximum loss · budget ' + plain(acct.risk_pct) + '% of configured equity'],
        ['aim', '+' + plain(t.low_pct) + '% to +' + plain(t.high_pct) + '% by day ' + plain(rules.final_exit_day), usd(t.low) + ' – ' + usd(t.high) + ' from the indicative entry' + (t.note ? ' · ' + t.note : ''), true]
      ]));
    } else {
      kids.push(factList([
        ['trigger', usd(plan.trigger), 'a buy stop ' + (isNum(plan.trigger_cushion) ? usd(plan.trigger_cushion) + ' ' : '') + 'over the box high ' + usd(plan.box_high), true],
        ['limit', usd(plan.limit), 'the highest fill the ticket permits'],
        ['stop', usd(plan.stop), (text(plan.stop_basis) ? plan.stop_basis + ' · ' : '') + plain(plan.stop_pct) + '% under the limit'],
        ['sized at', usd(plan.sizing_price || plan.limit), text(plan.planned_entry_note) ? plan.planned_entry_note : 'the limit', true],
        ['risk per share', usd(plan.risk_per_share), 'limit − stop'],
        ['shares', plan.eligible === false ? '—' : num(plan.shares), plan.capped_by === 'position_cap' ? 'cut by the position cap' : 'from ' + usd(plan.risk_usd) + ' ÷ ' + usd(plan.risk_per_share)],
        ['position', usd(plan.position_usd), (isNum(plan.position_pct) ? plan.position_pct.toFixed(1) : '—') + '% of the configured ' + usd(acct.equity, 0)],
        ['planned risk', usd(plan.risk_usd), 'price-to-stop at the limit, not a maximum loss'],
        ['aim', '+' + plain(t.low_pct) + '% to +' + plain(t.high_pct) + '% by day ' + plain(rules.final_exit_day), usd(t.low) + ' – ' + usd(t.high) + ' from the trigger' + (t.note ? ' · ' + t.note : ''), true],
        text(plan.gap_rule) ? ['gap rule', cap(plan.gap_rule), text(plan.open_entry) ? plan.open_entry : '', true] : null
      ]));
    }
    if ((plan.flags && plan.flags.length) || (plan.notes && plan.notes.length) || (plan.hazards && plan.hazards.length)) {
      kids.push(el('div', { 'class': 'sc-eyebrow', text: 'hazards and notes' }));
      if (plan.flags && plan.flags.length) kids.push(el('div', { 'class': 'ss-hazards' }, plan.flags.map((f) => chip(FLAG_WORDS[f] || words(f), 'warn'))));
      const notes = (plan.hazards || []).concat(plan.notes || []);
      if (notes.length) kids.push(el('ul', { 'class': 'ss-notes' }, notes.map((n) => el('li', { text: n }))));
    }
    if (text(plan.sizing_note)) kids.push(el('p', { 'class': 'sc-note', text: cap(sentence(plan.sizing_note)) }));
    if (text(plan.resize_rule)) kids.push(el('p', { 'class': 'sc-note', text: cap(sentence(plan.resize_rule)) }));
    const hint = blockedNow && c.status === 'ticket' ? 'No order is offered from a page that is ' + stateWords(st) + '.'
      : c.status === 'ticket' ? 'No order line was written for this plan.'
      : 'No ticket tonight: ' + (c.reason || statusWords(c.status)[0]) + '. The setup is kept here for inspection.';
    kids.push(orderBlock(plan, hint, withheld));
    return disclosure('disc-plan', 'Conditional plan, sizing and order', withheld ? (blockedNow && c.status === 'ticket' ? 'not offered' : statusWords(c.status)[0]) : 'sized at the limit', kids);
  }
  function discExits(c) {
    const plan = c.plan, kids = [];
    if (!plan) kids.push(el('p', { 'class': 'sc-hint', text: 'No plan, so no model exits.' }));
    else {
      const sched = plan.exit_schedule || [];
      if (sched.length) kids.push(el('ol', { 'class': 'sc-timeline' }, sched.map((s) => el('li', { 'class': 'sc-timeline__item' }, [
        el('div', { 'class': 'sc-timeline__stamp', text: dateWords(s.date) + ' · day ' + plain(s.day) }),
        el('div', { 'class': 'sc-timeline__body' }, [el('p', { text: cap(s.instruction || '') })])
      ]))));
      else kids.push(el('p', { 'class': 'sc-hint', text: 'The plan carries no dated schedule.' }));
      const exits = (plan.exits || []).filter((x) => x && (x.when || x.rule));
      if (exits.length) {
        kids.push(el('div', { 'class': 'sc-eyebrow', text: 'the rules the schedule follows' }));
        kids.push(el('ul', { 'class': 'ss-notes' }, exits.map((x) => el('li', { text: (x.when ? cap(x.when) + ': ' : '') + (x.rule || '') + (x.source ? ' (' + x.source + ')' : '') }))));
      }
    }
    kids.push(el('p', { 'class': 'sc-hint', text: 'Model guidance on daily bars: what the published ticket’s own rules would say on each day, not a record of a position.' }));
    return disclosure('disc-exits', 'Model exit guidance', plan && (plan.exit_schedule || []).length ? plural(plan.exit_schedule.length, 'dated step') : 'none', kids);
  }
  function discProvenance(c) {
    const b = c.row, run = current.run || {}, app = current.app || {}, cl = b.claude || null, kids = [];
    if (c.stage === 'bursts') {
      if (cl && cl.source === 'claude') {
        kids.push(el('div', { 'class': 'sc-insight' }, [
          el('div', { 'class': 'sc-eyebrow', text: (demo ? 'simulated chart-reader reply (fixture)' : 'claude read the chart') + (cl.agree === false ? ' · lowered the grade' : cl.agree === true ? ' · agreed' : '') }),
          demo ? el('p', { 'class': 'sc-hint', text: 'Sample data: this reply is scripted by the test doubles, not a live analysis of a real chart.' }) : null,
          el('p', { text: cl.reason || '' }),
          text(cl.key_risk) ? el('p', null, [el('strong', { text: 'Key risk: ' }), cl.key_risk]) : null,
          text(cl.entry_note) ? el('p', null, [el('strong', { text: 'At the open: ' }), cl.entry_note]) : null,
          el('p', { 'class': 'sc-hint', text: 'Model grade ' + (cl.grade || '—') + (isNum(cl.score) ? ' · ' + cl.score.toFixed(1) : '') + (cl.chart_seen === false ? ' · read from the numbers alone, no chart' : '') })
        ]));
      } else kids.push(el('p', { 'class': 'sc-hint ss-nomodel', text: 'Graded by the checklist alone; the model did not answer' + (cl && text(cl.error) ? ' (' + cl.error + ')' : '') + '.' }));
    } else kids.push(el('p', { 'class': 'sc-hint', text: 'Anticipation names are measured, not graded: no chart reader, no letters.' }));
    kids.push(factList([
      ['bars', 'Alpaca ' + String(run.feed || '').toUpperCase() + ', daily', c.series.length ? plural(c.series.length, 'session') + ' archived through ' + dateWords(c.series[c.series.length - 1].date) : 'none archived for this name'],
      ['rules', app.rules_version || '—', 'the digest of every strategy constant in this record'],
      ['run', (run.status || '—') + ' · ' + dateWords(run.session), 'published ' + timeET(run.published_at)],
      b.chart ? ['chart file', b.chart, 'the PNG the grader was shown, when the run rendered it'] : null
    ]));
    if (b.chart) kids.push(el('p', null, [el('a', { 'class': 'sc-link--quiet', href: b.chart, text: 'open the chart the grader saw' })]));
    return disclosure('disc-provenance', 'Provenance and the chart reader', c.stage === 'bursts' ? (cl && cl.source === 'claude' ? 'model read' : 'checklist alone') : 'measured', kids);
  }
  function renderDetail() {
    const stage = state.stage, c = model.byId[state.selected[stage]], box = $('detail');
    const key = c ? c.id : 'none:' + stage;
    if (state.detailKey !== key) {
      state.detailKey = key;
      disposeChart();
      clear(box);
      box.setAttribute('data-selected', c ? c.id : '');
      if (!c) box.appendChild(detailEmpty(stage));
      else {
        box.appendChild(detailHead(c));
        box.appendChild(detailChart(c));
        box.appendChild(decisionSummary(c));
        box.appendChild(actionArea(c));
        box.appendChild(discChecklist(c));
        box.appendChild(discPlan(c));
        box.appendChild(discExits(c));
        box.appendChild(discProvenance(c));
      }
      box.classList.remove('is-fresh');
      void box.offsetWidth;
      box.classList.add('is-fresh');
    }
    if (pendingFocus === 'detail') { pendingFocus = ''; box.focus({ preventScroll: true }); scrollTo(box); }
    else if (state.gesture && narrow() && c) scrollTo(box);
    state.gesture = false;
  }

  // ---------------------------------------------------------------- the tickets, as a disclosure
  function renderTickets(data) {
    const bursts = by(data.bursts || []), trades = (data.trades || []).map((t) => bursts[t]).filter(Boolean);
    const withOrders = trades.filter((b) => b.plan && b.plan.order_json), blockedNow = !!(st && blocked(st));
    const regime = ((data.breadth || {}).regime || {}).verdict;
    $('orders-summary').textContent = 'Tomorrow’s tickets · ' + (withOrders.length ? plural(withOrders.length, 'order') + (blockedNow ? ', not offered' : '') : 'none');
    const cb = data.cash_budget || {}, acct = data.account || {};
    const budget = clear($('budget'));
    budget.appendChild(el('strong', { text: cb.sentence || ('Model allocation: tomorrow’s tickets would commit ' + usd(cb.committed_usd, 0) + ' of the configured ' + usd(acct.equity, 0) + ' · ' + plain(cb.slots_used) + ' of ' + plain(cb.slots_max) + ' slots') }));
    if (isNum(cb.at_risk_usd)) budget.appendChild(d.createTextNode(' · ' + usd(cb.at_risk_usd, 0) + ' planned price-to-stop risk'));
    budget.appendChild(d.createTextNode(' · over the configured sizing assumptions, not a balance, settled cash or buying power'));
    (cb.cut || []).forEach((c) => budget.appendChild(el('span', { 'class': 'sc-note', text: 'No ticket: ' + c.ticker + ' — ' + c.reason })));
    const sheet = clear($('orders-table'));
    const table = el('table', { 'class': 'sc-table sc-table--compact ss-orders', id: 'order-sheet' });
    table.appendChild(el('caption', { 'class': 'sc-sr-only', text: 'Tomorrow’s orders in Fidelity’s field order' }));
    table.appendChild(el('thead', null, el('tr', null, ['symbol', 'action', 'shares', 'type', 'stop (trigger)', 'limit', 'tif', 'then OTO sell stop', 'skip above', 'planned risk'].map((h, i) => el('th', { scope: 'col', 'class': i >= 2 && i !== 3 && i !== 6 ? 'sc-num' : null, text: h })))));
    const body = el('tbody');
    const rows = blockedNow ? [] : withOrders;
    rows.forEach((b) => {
      const o = b.plan.order_json, t = o.then || {};
      const name = el('button', { 'class': 'sc-signal-matrix__name', type: 'button', text: b.ticker, 'data-go': routeHash('bursts', 'bursts:' + b.ticker) });
      name.addEventListener('click', () => { pendingFocus = 'detail'; state.gesture = true; navigate(name.getAttribute('data-go')); });
      body.appendChild(el('tr', { 'data-ticker': b.ticker }, [
        el('th', { scope: 'row', 'class': 'sc-case' }, name), el('td', { text: String(o.action || '').toUpperCase() }),
        el('td', { 'class': 'sc-num', text: num(o.quantity) }), el('td', { text: words(o.order_type || '').toUpperCase() }),
        el('td', { 'class': 'sc-num', text: usd(o.stop_price) }), el('td', { 'class': 'sc-num', text: usd(o.limit_price) }),
        el('td', { text: String(o.time_in_force || '').toUpperCase() }), el('td', { 'class': 'sc-num', text: usd(t.stop_price) + ' ' + String(t.time_in_force || '').toUpperCase() }),
        el('td', { 'class': 'sc-num', text: usd(b.plan.skip_if_open_above) }), el('td', { 'class': 'sc-num', text: usd(b.plan.risk_usd) })
      ]));
    });
    if (!rows.length) body.appendChild(el('tr', { 'class': 'sc-empty' }, el('td', { colspan: '10', text: blockedNow && withOrders.length ? 'No orders offered: the page is ' + stateWords(st) + '.' : st && st.state === 'closed' ? 'No orders: the market was closed and the plans stand.' : regime === 'red' ? 'No orders: breadth is red.' : 'No orders tomorrow.' })));
    table.appendChild(body);
    const committed = rows.reduce((a, b) => a + (b.plan.position_usd || 0), 0), risk = rows.reduce((a, b) => a + (b.plan.risk_usd || 0), 0);
    table.appendChild(el('tfoot', null, el('tr', null, el('td', { colspan: '10', text: plural(rows.length, 'order') + ' · ' + usd(committed, 0) + ' would be committed at the limits · ' + usd(risk, 0) + ' planned price-to-stop risk · ' + (isNum(acct.equity) && acct.equity ? (100 * committed / acct.equity).toFixed(1) : '—') + '% of the configured equity' }))));
    sheet.appendChild(table);
    const notes = acct.notes || [];
    if (notes.length) sheet.appendChild(el('details', { 'class': 'sc-details' }, [el('summary', { text: 'the configured sizing assumptions this sheet follows' }), el('ul', { 'class': 'ss-notes' }, notes.map((n) => el('li', { text: n })))]));
  }

  // ---------------------------------------------------------------- the scan, as a disclosure
  function signalCell(c, vetoed) {
    const tone = vetoed ? 'blocked' : !c ? null : c.pass ? (c.marginal ? 'caution' : 'good') : 'blocked';
    const glyph = vetoed ? '✕' : !c ? '—' : c.pass ? (c.marginal ? '~' : '✓') : '✕';
    const word = vetoed ? 'veto' : !c ? 'not measured' : c.pass ? (c.marginal ? 'partial' : 'pass') : (c.status === 'unmeasured' ? 'not measured' : c.marginal ? 'partial' : 'fail');
    const primary = c ? String(c.display || '').split(' ')[0] : '', threshold = c ? String(c.threshold || '') : '';
    const cell = el('span', { 'class': 'sc-signal' + (tone ? ' sc-signal--' + tone : ''), title: c ? [c.display, threshold ? 'threshold: ' + threshold : '', c.note].filter(Boolean).join('\n') : null }, [
      el('span', { 'class': 'sc-signal__glyph', 'aria-hidden': 'true', text: glyph }),
      el('span', { 'class': 'sc-signal__label', text: word + (primary ? ' · ' + primary : '') }),
      c ? el('span', { 'class': 'sc-signal__note', text: threshold.length > 42 ? threshold.slice(0, 40).replace(/\s+\S*$/, '') + '…' : threshold }) : null
    ]);
    return el('td', null, cell);
  }
  function renderScan(data) {
    const bursts = (data.bursts || []).filter((b) => b && b.ticker), trades = data.trades || [], body = clear($('scan-body')), run = data.run || {};
    const nCriteria = bursts.length && bursts[0].quality && bursts[0].quality.checks ? bursts[0].quality.checks.length : Object.keys(CRITERIA_SHORT).length;
    $('scan-summary').textContent = 'Everything the scan found · ' + (bursts.length ? plural(bursts.length, 'burst') : 'no burst');
    $('scan-lede').textContent = 'Every burst against Bonde’s ' + nCriteria + ' A-quality criteria: the measured value, his threshold, and the verdict in words. A name opens its card above.' + (isNum(run.bursts) && run.bursts > bursts.length ? ' ' + bursts.length + ' of the ' + num(run.bursts) + ' bursts found are archived with their checks.' : '');
    const cm = data.closest_miss;
    if (cm && cm.sentence && !trades.length) body.appendChild(el('aside', { 'class': 'sc-callout sc-callout--core', id: 'closest-miss' }, [el('div', { 'class': 'sc-callout__label', text: 'closest miss' }), el('p', { 'class': 'sc-callout__figure', text: cm.sentence })]));
    if (!bursts.length) { body.appendChild(empty('The scan found no burst.')); return; }
    const keys = Object.keys(CRITERIA_SHORT);
    const labels = {}; bursts.forEach((b) => ((b.quality || {}).checks || []).forEach((c) => { if (c && c.key && !labels[c.key]) labels[c.key] = c.label; }));
    body.appendChild(el('p', { 'class': 'sc-hint', id: 'scan-help', text: 'Jump to a criterion or swipe across. Keyboard: focus the table and use the arrow keys. Hover a tile for every measurement, his full threshold and the note.' }));
    const scroll = el('div', { 'class': 'sc-table-scroll', 'data-sc-matrix-nav': '', tabindex: '0', role: 'region', 'aria-label': 'Every burst against the ' + nCriteria + ' criteria', 'aria-describedby': 'scan-help' });
    const table = el('table', { 'class': 'sc-table sc-signal-matrix', id: 'scan-table' });
    table.appendChild(el('caption', { 'class': 'sc-sr-only', text: 'Bursts found on ' + (run.session || '') + ' compared on Bonde’s ' + nCriteria + ' A-quality criteria. Green passes, amber is marginal, red fails or is vetoed, neutral was not measured.' }));
    const sortBtn = el('button', { 'class': 'sc-table__sort', type: 'button', text: 'grade · score' });
    const sortTh = el('th', { scope: 'col', 'class': 'is-sortable', 'aria-sort': 'descending' }, sortBtn);
    table.appendChild(el('thead', null, el('tr', null, [el('th', { scope: 'col', text: 'burst' })].concat(keys.map((k) => el('th', { scope: 'col', 'data-sc-label': CRITERIA_SHORT[k], text: labels[k] || words(k) }))).concat([sortTh]))));
    const tbody = el('tbody');
    bursts.forEach((b) => {
      const q = b.quality || {}, checks = {}; (q.checks || []).forEach((c) => { if (c && c.key) checks[c.key] = c; });
      const vetoes = q.vetoes || [];
      const tr = el('tr', { id: 'burst-' + b.ticker, 'data-ticker': b.ticker, 'data-score': isNum(b.score) ? String(b.score) : '' });
      const isTrade = trades.indexOf(b.ticker) >= 0;
      const name = el('button', { 'class': 'sc-signal-matrix__name', type: 'button', text: b.ticker, 'data-go': routeHash('bursts', 'bursts:' + b.ticker) });
      name.addEventListener('click', () => { pendingFocus = 'detail'; state.gesture = true; navigate(name.getAttribute('data-go')); });
      tr.appendChild(el('th', { scope: 'row' }, [name,
        el('span', { 'class': 'sc-signal-matrix__note', text: pct(b.gain_pct) + ' · ' + (isNum(b.volume_vs_prior) ? b.volume_vs_prior.toFixed(1) : '—') + '× vol · ' + usd(b.close) + (b.scan === 'dollar' ? ' · $ scan' : '') })
      ]));
      keys.forEach((k) => tr.appendChild(signalCell(checks[k], (k === 'two_days' && vetoes.indexOf('up_days') >= 0) || (k === 'linearity' && vetoes.indexOf('not_linear') >= 0))));
      const miss = (q.checks || []).find((c) => c && !c.pass);
      const gradeNote = vetoes.length ? 'veto · ' + vetoes.map((v) => VETO_WORDS[v] || words(v)).join(', ') : q.reclass ? 'reclassified · ' + words(q.reclass) : miss ? 'first miss · ' + (miss.label || words(miss.key) || 'a check') : 'nothing missed';
      const gradeTone = b.grade === 'A+' || b.grade === 'A' ? 'brand' : 'neutral';
      tr.appendChild(el('td', { 'class': 'sc-signal-matrix__value' }, [chip((b.grade || '—') + (isNum(b.score) ? ' · ' + b.score.toFixed(1) : ''), gradeTone, true),
        el('span', { 'class': 'ss-grade-note', text: gradeNote + (b.claude && b.claude.source === 'claude' && b.claude.agree === false ? ' · Claude lowered it' : '') + (isTrade ? ' · trade' : '') })]));
      tbody.appendChild(tr);
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
    body.appendChild(scroll);
    body.appendChild(el('p', { 'class': 'sc-hint', text: 'Green = passes his threshold. Amber = partial. Red = fails, or vetoed outright. A+ and A need the close near the high and no two up days in a row; the grade word is the verdict, the score its rank.' }));
  }

  // ---------------------------------------------------------------- the record view
  function planRow(p, holdDays) {
    const words_ = PLAN_STATUS[p.status] || [words(String(p.status || '—')).toUpperCase(), 'neutral'];
    const row = el('article', { 'class': 'ss-plan', 'data-ticker': p.ticker, 'data-status': p.status || '' });
    row.appendChild(el('div', { 'class': 'ss-plan__row' }, [
      el('strong', { 'class': 'sc-case', text: p.ticker }), chip(words_[0], words_[1], true),
      el('span', { 'class': 'ss-plan__meta', text: 'day ' + plain(p.day) + (isNum(holdDays) ? ' of ' + plain(holdDays) : '') + ' · picked ' + dateMD(p.picked) + ' · ' + num(p.shares) + ' sh' })
    ]));
    const t = p.targets || {}, stop = isNum(p.current_stop) ? p.current_stop : p.stop, aim = isNum(t.high) ? t.high : null;
    // the bar runs from the stop to the aim; the entry marker is drawn only
    // while the entry still sits above the stop (a trailed stop can pass it),
    // and only for a plan the model walked from a known fill
    if (WALKED.indexOf(p.status) >= 0 && isNum(p.last_close) && isNum(stop) && aim !== null && aim > stop && isNum(t.low) && isNum(p.entry_ref)) {
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
    if (p.status === 'uncertain') row.appendChild(el('p', { 'class': 'sc-hint', text: 'Uncertain: the bars cannot establish this fill, so the model holds no position here and scores none; it keeps its slot in the model allocation.' }));
    return row;
  }
  function tile(label, value, sub) {
    return el('div', { 'class': 'sc-tile' }, [el('div', { 'class': 'sc-tile__label', text: label }), el('div', { 'class': 'sc-tile__value sc-tile__value--sm', text: value }), el('div', { 'class': 'sc-tile__sub', text: sub })]);
  }
  function renderRecord(data) {
    const sc = data.scorecard || {}, card = clear($('record-card'));
    const settled = isNum(sc.settled) ? sc.settled : 0, minRead = sc.min_read, readable = sc.readable === true;
    card.appendChild(el('div', { 'class': 'sc-card__head' }, [
      el('div', null, [el('h3', { text: 'The scorecard' }), el('p', { 'class': 'sc-hint', text: 'a model of the published plans’ fills, the rules’ record and not yours: rates from ' + plain(minRead) + ' settled plans, an uncertain fill in no rate' + (readable ? '' : ' · ' + settled + ' settled so far, so nothing below is a rate yet') })]),
      chip(readable ? 'readable' : 'not yet readable', readable ? 'good' : 'neutral')
    ]));
    const uncertain = isNum(sc.uncertain) ? sc.uncertain : 0;
    card.appendChild(el('div', { 'class': 'sc-grid sc-grid--4' }, [
      tile('plans', num(sc.plans), num(sc.settled) + ' settled · ' + num(uncertain) + ' uncertain · reads at ' + plain(minRead)),
      tile('filled', num(sc.filled), 'at the next open, at or over the trigger and at or under the limit'),
      tile('win rate', isNum(sc.win_rate) ? (100 * sc.win_rate).toFixed(0) + '%' : '—', num(sc.wins) + ' wins · ' + num(sc.losses) + ' losses, settled plans only'),
      tile('avg R', isNum(sc.avg_r) ? (sc.avg_r > 0 ? '+' : '') + sc.avg_r.toFixed(2) : '—', 'sum R ' + (isNum(sc.sum_r) ? (sc.sum_r > 0 ? '+' : '') + sc.sum_r.toFixed(1) : '—') + ' · sales weighted by whole shares')
    ]));
    const reasons = (sc.uncertain_reasons || []).filter((r) => r && isNum(r.count) && r.words);
    if (uncertain || reasons.length) card.appendChild(el('p', { 'class': 'sc-note', id: 'scorecard-uncertain', text: num(uncertain) + ' uncertain, in no rate: ' + (reasons.length ? reasons.map((r) => num(r.count) + ' ' + r.words).join('; ') : 'the bars could not establish the fill') + '.' }));
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
  function renderRecordView(data) {
    const rules = data.rules || {}, holdDays = (rules.plan || {}).final_exit_day, window = (rules.record || {}).open_plan_sessions;
    const hold = clear($('hold-rows')), plans = data.open_plans || [], hint = $('hold-hint');
    if (hint) hint.textContent = 'Model plans from the last ' + (isNum(window) ? plain(window) : 'five') + ' sessions, walked from daily bars by the published ticket’s own rules. SpicyStock does not know what you hold: if you took a plan, this is what its rules say next; if you did not, ignore its row. UNCERTAIN means the bars cannot say whether it filled.';
    if (!plans.length) hold.appendChild(empty('No open model plans. Nothing was picked in the last ' + (isNum(window) ? plain(window) : 'five') + ' sessions.'));
    plans.forEach((p) => { if (p && p.ticker) hold.appendChild(planRow(p, holdDays)); });
    renderRecord(data);
  }

  // ---------------------------------------------------------------- next
  function nextAction(data, s) {
    const bursts = by(data.bursts || []);
    const orders = (data.trades || []).map((t) => bursts[t]).filter((b) => b && b.plan && b.plan.order_json).length;
    const open = (data.open_plans || []).length, red = ((data.breadth || {}).regime || {}).verdict === 'red';
    if (blocked(s)) return ['Do not place these orders.', 'Wait for tonight’s run to publish, or check the run log. Nothing on this page is tomorrow’s plan.', 'stale'];
    const window = ((data.rules || {}).plan || {}).entry_window || 'entry window';
    if (s.state === 'closed') return ['Plans unchanged. Check the open model plans before ' + ORDERS_BY + '.', 'The market was closed; there is nothing new to place.', 'closed'];
    if (red) return ['No new longs. Work the exits in the record before ' + ORDERS_BY + '.', 'Breadth is red: tighten the stops and sell into strength.', 'red'];
    if (orders) return ['Place the ' + plural(orders, 'order') + ' from tomorrow’s tickets in Fidelity before ' + ORDERS_BY + '. Exits first.', 'Attach each sell stop the moment its buy fills, and cancel any order that has not filled by the end of the ' + window + '.', 'orders'];
    if (open) return ['Nothing new to place. Work the exits in the record before ' + ORDERS_BY + '.', 'No burst qualified with a ticket tonight; the open model plans still carry their instructions.', 'quiet'];
    return ['Nothing to place. Keep cash.', 'No burst qualified and nothing is held. Come back after the next run.', 'quiet'];
  }
  function renderNext(data, s) {
    const n = nextAction(data, s);
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

  // ---------------------------------------------------------------- the chooser
  function fillChooser(q) {
    const list = clear($('chooser-list')); let n = 0, first = null;
    STAGES.forEach((s) => {
      const items = model.stages[s].filter((c) => matches(c, q));
      if (!items.length) return;
      list.appendChild(el('div', { 'class': 'sc-eyebrow ss-chooser__group', text: STAGE_NAME[s].toLowerCase() + ' · ' + items.length }));
      items.forEach((c) => {
        n++;
        const sw = statusWords(c.status);
        const b = el('button', { 'class': 'ss-chooser__item', type: 'button', 'data-id': c.id, 'aria-pressed': state.selected[s] === c.id ? 'true' : 'false' }, [
          el('b', { 'class': 'sc-case', text: c.ticker }), el('span', { text: pickReason(c) }), chip(sw[0], sw[1])
        ]);
        b.addEventListener('click', (e) => { e.preventDefault(); choose(c); });
        if (!first) first = b;
        list.appendChild(b);
      });
    });
    $('chooser-status').textContent = n ? n + ' stock' + (n === 1 ? '' : 's') + (q ? ' match ‘' + q + '’' : ' in tonight’s record') + '; Enter chooses the first.' : 'No stock matching ‘' + q + '’ in tonight’s record.';
    return first;
  }
  function openChooser() {
    const dlg = $('chooser');
    if (!dlg || !model) return;
    chooserOpener = d.activeElement;
    dlg.returnValue = '';
    $('chooser-search').value = '';
    fillChooser('');
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', '');
    $('chooser-search').focus();
  }
  function choose(c) {
    const dlg = $('chooser');
    if (dlg.close) dlg.close('chosen'); else dlg.removeAttribute('open');
    pendingFocus = 'detail'; state.gesture = true;
    navigate(routeHash(c.stage, c.id));
  }

  // ---------------------------------------------------------------- wiring (once)
  function wire() {
    const input = $('search');
    input.addEventListener('input', () => { state.query = input.value.trim().toUpperCase(); if (model && state.view === 'explore') renderPicks(); });
    $('search-form').addEventListener('submit', (e) => { e.preventDefault(); if (!model) return; const q = input.value.trim().toUpperCase(); if (q) resolveSearch(q); });
    $('pick-list').addEventListener('keydown', (e) => {
      const picks = Array.from($('pick-list').querySelectorAll('.ss-pick')), i = picks.indexOf(d.activeElement);
      if (i < 0) return;
      let j;
      if (e.key === 'ArrowDown' || e.key === 'ArrowRight') j = Math.min(picks.length - 1, i + 1);
      else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') j = Math.max(0, i - 1);
      else if (e.key === 'Home') j = 0;
      else if (e.key === 'End') j = picks.length - 1;
      else return;
      e.preventDefault();
      picks[j].focus();
    });
    $('choose-open').addEventListener('click', openChooser);
    const dlg = $('chooser'), cs = $('chooser-search');
    cs.addEventListener('input', () => { fillChooser(cs.value.trim().toUpperCase()); });
    cs.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); const first = $('chooser-list').querySelector('.ss-chooser__item'); if (first) first.click(); } });
    dlg.addEventListener('close', () => { if (dlg.returnValue !== 'chosen') { const back = chooserOpener && chooserOpener.focus ? chooserOpener : $('choose-open'); back.focus(); } chooserOpener = null; });
    dlg.addEventListener('click', (e) => { if (e.target === dlg && dlg.close) dlg.close('backdrop'); });
    w.addEventListener('hashchange', () => applyRoute(parseHash(w.location.hash)));
  }

  // ---------------------------------------------------------------- render
  function render(data, now) {
    current = data; SCStock.data = data;
    demo = !!data.fixture;
    d.documentElement.setAttribute('data-ss-demo', demo ? 'true' : 'false');
    st = status(data, now); SCStock.state = st;
    model = buildModel(data); SCStock.model = model;
    SCStock.follow.setDemo(demo);
    unmountMap();
    state.stage = null; state.selected = { bursts: null, 'setting-up': null }; state.query = ''; state.picksKey = null; state.detailKey = null; state.notice = '';
    $('search').value = '';
    renderStatus(data, st);
    renderMarketBar(data, st);
    renderMethod(data);
    renderBreadth(data);
    buildStages();
    buildDatalist();
    renderTickets(data);
    renderScan(data);
    renderRecordView(data);
    renderNext(data, st);
    renderFooter(data);
    renderFollowing();
    followJump();
    applyRoute(parseHash(w.location.hash), true);
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
    clear($('stages')).appendChild(el('div', { 'class': 'ss-picks__empty', 'data-empty': 'record', text: 'No record loaded: there are no stages to choose from.' }));
    clear($('pick-list')).appendChild(el('div', { 'class': 'ss-picks__empty', 'data-empty': 'record', text: 'No record, no stocks.' }));
    clear($('detail')).appendChild(el('div', { 'class': 'ss-chart-empty', 'data-detail': 'error' }, [el('strong', { text: 'No record. ' }), 'The page could not read docs/data.json, so there is nothing to explore. Check the run log; do not place any order from this page.']));
    $('picks-status').textContent = 'No record loaded.';
    $('orders-summary').textContent = 'Tomorrow’s tickets · none';
    $('scan-summary').textContent = 'Everything the scan found · no record';
    clear($('hold-rows')).appendChild(empty('No record loaded.'));
    const fl = $('following-list'); if (fl) { clear(fl).appendChild(el('div', { 'class': 'ss-following__empty', text: 'No record loaded, so nothing to observe.' })); }
    clear($('record-card')).appendChild(empty('No record loaded.'));
    applyRoute(parseHash(w.location.hash), true);
    d.documentElement.setAttribute('data-ss-rendered', 'error');
  }
  function boot() {
    loadPrefs();
    loadDiscover();
    wire();
    const src = (w.SCStock && w.SCStock.dataUrl) || 'data.json';
    w.fetch(src, { cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error('data.json answered ' + r.status); return r.json(); })
      .then((data) => { if (!data || data.schema_version !== 2 || !data.run) throw new Error('not a schema_version 2 record'); render(data, w.SCStock.now ? new Date(w.SCStock.now) : new Date()); })
      .catch((e) => failed(String(e && e.message || e)));
  }
  if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', boot); else boot();
})(window);
