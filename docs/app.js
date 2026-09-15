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
  // The lenses: four ways to narrow a stage, each a question asked of a field
  // the run wrote. `a` reads the archived grade against the record's own
  // trade grades; `ticket` reads the status the record gives the stock, which
  // is a fact ABOUT THE RECORD and never a permission -- a stale, failed,
  // pending or sample page still refuses every order, because the order is
  // offered by blocked(st) and the run's own fields, not by this list.
  // `following` reads this browser's shelf. Nothing here scans or grades.
  const LENSES = {
    bursts: [['a', 'A-quality', 'the A and A+ grades this record archived'], ['all', 'All bursts', 'every burst the scan archived'],
      ['ticket', 'With ticket', 'a ticket written into the published record'], ['following', 'Saved in this scan', 'tonight’s candidates you already saved in this browser']],
    'setting-up': [['all', 'All setups', 'every coil the anticipation scans admitted'],
      ['ticket', 'With ticket', 'a ticket written into the published record'], ['following', 'Saved in this scan', 'tonight’s candidates you already saved in this browser']]
  };
  const LENS_WORDS = { a: 'A-quality', all: 'all', ticket: 'with a ticket', following: 'following' };
  // Sorting is presentation. It is offered where the record measures the key
  // for every row (the bursts' own session), never invented for the coils.
  const SORTS = [['rank', 'rank', 'the run’s own order'], ['gain', 'gain', 'the session’s gain, largest first'], ['volume', 'volume', 'volume against the previous session, largest first']];
  const SORT_WORDS = { rank: 'the run’s rank', gain: 'the session’s gain', volume: 'volume vs the previous session' };
  // Which recorded check is anchored to which stretch of chart. A check whose
  // evidence the record carries no dates for -- linearity, the trend's age,
  // the run of up days -- is NOT here: its words are shown and the anchor is
  // said to be unavailable, rather than a convincing region being invented.
  const CHECK_ANCHOR = { consolidation: 'base', close_near_high: 'burst', range_expansion: 'burst', volume: 'burst', narrow_or_negative: 'prior' };
  const ANCHOR_WORDS = { base: 'Base', burst: 'Burst day', prior: 'Prior day', box: 'Box' };
  const VIEWS = ['explore', 'setups', 'record', 'market', 'method'];
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
  // How a printed number was arrived at (design system v2.13.0, §4h). Recorded
  // is the default and wears no class; these two are the other two answers, and
  // both are applied from what the RECORD says about a figure, never from a
  // computation this page has just done. Each wraps the VALUE and never the row
  // or the cell -- a slot styled by a descendant rule (`.sc-facts dd`, a `td`
  // under its table's own class) wins on specificity otherwise -- and the words
  // stay in the markup either way, because the mark is reinforcement and the
  // word is the meaning.
  // `unreported`: the source never supplied it. Mono, lowercase, its own size,
  // never tabular, so an absence cannot align or weigh like a measurement.
  const unreported = (words) => el('span', { 'class': 'sc-unreported', text: words });
  // `estimate`: derived from the run's stated assumptions. The ticket's own
  // terms -- the trigger, the limit, the stop, the day-2 line -- are exact and
  // are NEVER marked with it.
  const estimate = (figure) => el('span', { 'class': 'sc-estimate', text: figure });
  // The session's volume over the previous session's, read one way for every
  // consumer (the card, the detail line, the measurements, the map, the scan
  // table, the chart's burst label). The row's own field is the scan's
  // measurement and the canonical value; a record written before the dollar
  // scan carried it (run 46 and earlier) holds the same measurement at two
  // places in the checklist's burst block, and that stands in when the field
  // is null. A ratio is a finite number of zero or more -- zero is a value --
  // and anything else is missing, said to be missing, never invented.
  const RATIO_ROUNDING = 0.005 + 1e-9;   // a two-place copy of a four-place value sits within this of it
  function volumeRatio(b) {
    const own = b ? b.volume_vs_prior : null, q = b && b.quality && b.quality.burst ? b.quality.burst.volume_vs_prior : null;
    if (isNum(own) && own >= 0) return { value: own, source: 'scan', disagrees: isNum(q) && q >= 0 && Math.abs(own - q) > RATIO_ROUNDING ? q : null };
    if (isNum(q) && q >= 0) return { value: q, source: 'checklist', disagrees: null };
    return { value: null, source: null, disagrees: null };
  }
  const volumeTimes = (b) => { const v = volumeRatio(b).value; return isNum(v) ? v.toFixed(1) : '—'; };
  SCStock.volumeRatio = volumeRatio;
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

  // ---------------------------------------------------------------- the two clocks
  // A record carries two different facts about time, and `status()` above is
  // only the first of them: is this the newest record, and did the run
  // finish? PUBLICATION. The second is which session the published plans are
  // FOR and whether that session's entry window is still ahead, running or
  // over: ACTION TIMING, and nothing above knows it. A record can be
  // perfectly fresh and its window three hours gone; the page used to print
  // the first as though it settled the second, and told a reader at eleven
  // o'clock to place orders "before 9:28 AM".
  //
  // The run serializes the window (`run.timing`, src/timing.py) so the page
  // never reads a deadline out of an English instruction and never writes a
  // UTC offset of its own: the instants arrive with their offsets, and where
  // only a DATE is available the comparison is made in ET wall-clock terms
  // through `etParts()`, which asks the browser's own tz database.
  const PHASE_WORDS = { upcoming: 'upcoming', open: 'in progress', ended: 'ended', unknown: 'unavailable' };
  const PHASE_TONE = { upcoming: 'brand', open: 'good', ended: 'neutral', unknown: 'warn' };
  // one sentence per src/timing.py LIMITS key (tests/test_docs.py holds the two lists equal)
  const TIMING_LIMITS = {
    no_holiday_calendar: 'SpicyStock carries no market-holiday calendar, so the applicable session is the next weekday: a holiday moves it, and the date is printed so the mistake is visible.',
    regular_hours_assumed: 'The window is the regular session’s: a shortened session closes early and still opens at 9:30 AM ET.'
  };

  function instant(value) {
    if (typeof value !== 'string' || !value) return null;
    // an instant without an offset would be a different moment on every desk
    if (!/[+-]\d\d:?\d\d$|Z$/.test(value)) return null;
    const t = Date.parse(value);
    return isFinite(t) ? new Date(t) : null;
  }
  // The record's own timing block, read once and never inferred, and held to
  // its shape one level in -- the class this repository produces most often is
  // a structure read off disk whose shape nothing checked until a consumer
  // broke. A HALF-written window is worse than none: the page would compare
  // against it and get an answer. `faults` names what is wrong (empty for a
  // record that simply has no block, which is every record published before
  // the field existed), and `known` is false either way.
  function timingOf(data) {
    const t = (data && data.run && data.run.timing);
    const out = { known: false, present: false, faults: [], session: null, opens: null, cutoff: null,
      prepareBy: null, closes: null,
      window: ((((data || {}).rules || {}).plan || {}).entry_window) || 'entry window',
      windowMinutes: null, closedSession: null, basis: null, limits: [], et: {} };
    if (t === null || t === undefined) return out;
    out.present = true;
    if (typeof t !== 'object' || Array.isArray(t)) { out.faults.push('run.timing is neither absent nor an object'); return out; }
    out.session = text(t.applicable_session) ? t.applicable_session : null;
    out.opens = instant(t.opens_at); out.cutoff = instant(t.cutoff_at);
    out.prepareBy = instant(t.prepare_by); out.closes = instant(t.closes_at);
    out.closedSession = text(t.closed_session) ? t.closed_session : null;
    out.basis = text(t.basis) ? t.basis : null;
    out.limits = (t.limits || []).filter((k) => TIMING_LIMITS[k]);
    out.et = { opens: text(t.opens_et) ? t.opens_et : null, cutoff: text(t.cutoff_et) ? t.cutoff_et : null,
      prepareBy: text(t.prepare_by_et) ? t.prepare_by_et : null };
    if (text(t.window)) out.window = t.window;
    if (isNum(t.window_minutes)) out.windowMinutes = t.window_minutes;
    const day = (iso) => /^\d{4}-\d\d-\d\d$/.test(String(iso || ''));
    if (!day(out.session)) out.faults.push('run.timing.applicable_session is not a YYYY-MM-DD date');
    if (!day(t.measured_session)) out.faults.push('run.timing.measured_session is not a YYYY-MM-DD date');
    else if (day(out.session) && out.session <= t.measured_session) out.faults.push('run.timing.applicable_session is not after its measured_session');
    ['opens_at', 'cutoff_at', 'prepare_by', 'closes_at'].forEach((k) => {
      if (!instant(t[k])) out.faults.push('run.timing.' + k + ' is not an ISO-8601 instant with an offset');
    });
    if (out.opens && out.cutoff && out.cutoff <= out.opens) out.faults.push('run.timing.cutoff_at is not after its opens_at, so the window has no width');
    // the instant is serialized in market time, so its own date prefix is the
    // session it belongs to -- no zone arithmetic to get this wrong
    if (out.opens && day(out.session) && String(t.opens_at).slice(0, 10) !== out.session) out.faults.push('run.timing.opens_at is not on its own applicable_session');
    if (!clockET(t.opens_et) || !clockET(t.cutoff_et)) out.faults.push('run.timing needs opens_et and cutoff_et as HH:MM');
    if (!text(t.window) || !isNum(t.window_minutes)) out.faults.push('run.timing needs the window’s words and its whole number of minutes');
    if (!text(t.basis)) out.faults.push('run.timing.basis is missing');
    if (!Array.isArray(t.limits)) out.faults.push('run.timing.limits is not a list');
    out.known = !out.faults.length;
    return out;
  }
  // the shape check on its own, for a record offered to the page by an update
  // check: a block that IS there and is broken refuses the whole load, because
  // a run that wrote it wrong wrote something else wrong too
  const timingFaults = (data) => timingOf(data).faults;
  SCStock.timingFaults = timingFaults;
  // the same rule src/timing.py `phase()` pins: open from the bell up to but
  // NOT including the cutoff, because the window is the first N minutes and
  // at the cutoff the last of them is over
  function phaseOf(tm, now) {
    if (!tm || !tm.known) return 'unknown';
    const t = (now || new Date()).getTime();
    if (t < tm.opens.getTime()) return 'upcoming';
    return t < tm.cutoff.getTime() ? 'open' : 'ended';
  }
  // a session's phase from its DATE alone, for a saved setup whose own night
  // is not the record on screen. No offset arithmetic: `now` is read in ET
  // and compared as wall clock against the policy times the run serialized.
  function phaseOfSession(iso, tm, now) {
    if (!text(iso) || !tm || !tm.et || !tm.et.opens || !tm.et.cutoff) return 'unknown';
    const et = etParts(now || new Date());
    if (iso > et.date) return 'upcoming';
    if (iso < et.date) return 'ended';
    const mins = et.hour * 60 + et.minute, hm = (s) => (+s.slice(0, 2)) * 60 + (+s.slice(3, 5));
    if (mins < hm(tm.et.opens)) return 'upcoming';
    return mins < hm(tm.et.cutoff) ? 'open' : 'ended';
  }
  const clockET = (hhmm, suffix) => { const m = /^(\d\d):(\d\d)$/.exec(String(hhmm || '')); if (!m) return null;
    const h = +m[1]; return ((h % 12) || 12) + ':' + m[2] + (suffix === false ? '' : (h < 12 ? ' AM' : ' PM') + ' ET'); };
  // "9:30-10:00 AM ET", the meridiem and the zone said once when both share them
  function windowWords(tm) {
    const a = tm.et.opens, b = tm.et.cutoff;
    if (!a || !b) return '—';
    const half = (s) => (+s.slice(0, 2)) < 12;
    return half(a) === half(b) ? clockET(a, false) + '\u2013' + clockET(b) : clockET(a) + '\u2013' + clockET(b);
  }

  // THE one answer to "may the reader act on tonight's tickets now?", and the
  // only place any surface asks it. Three different things can refuse, and
  // each keeps its own voice so the page never gives the wrong reason:
  //
  //   publication — stale, pending, failed: there is no current record
  //   timing      — the window is over, or the record does not say when it is
  //   the record  — red breadth, a withheld ticket, no whole share
  //
  // Timing NARROWS and never widens. `offered` is false whenever publication
  // says so, whatever the clock; a window that is open cannot make a stale
  // page actionable, and `unknown` is research only, never permission.
  function availability(data, now) {
    const at = now || new Date();
    const pub = status(data, now), tm = timingOf(data), ph = phaseOf(tm, at);
    const pubBlocked = blocked(pub);
    const timingBlocked = ph === 'ended' || ph === 'unknown';
    const av = { at: at, pub: pub, timing: tm, phase: ph, pubBlocked: pubBlocked, timingBlocked: timingBlocked,
      offered: !pubBlocked && !timingBlocked, reason: '', lead: '', word: PHASE_WORDS[ph], tone: PHASE_TONE[ph] };
    if (pubBlocked) {
      av.reason = 'The page is ' + stateWords(pub) + '. ' + sentence(pub.sentence);
      av.lead = 'not offered';
    } else if (ph === 'ended') {
      av.reason = 'The entry window for ' + dateWords(tm.session) + ' ended at ' + timeET(tm.cutoff.toISOString()) +
        '. The setup, its evidence and the ticket the record published stay readable; this is history now, not an order to place.';
      av.lead = 'window ended';
    } else if (ph === 'unknown') {
      av.reason = 'Entry timing unavailable — research only. This record does not say which session its plans are for, so the page will not name a deadline for them.';
      av.lead = 'timing unavailable';
    }
    return av;
  }
  SCStock.availability = availability;
  SCStock.timingOf = timingOf;

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
    // The verdict is the record's own sentence, printed verbatim -- and its
    // "Trade tomorrow." was written on the evening of its session, when
    // tomorrow was the session it names. Once that session's window is behind
    // the reader, the eyebrow says the sentence is the archived one rather
    // than rewriting it: the page does not edit the record's words, and does
    // not leave a headline in 30px type reading as today's instruction.
    const asPublished = av.phase === 'ended' || av.pubBlocked;
    $('cover-eyebrow').textContent = 'spicystock · ' + (run.session || '—') + ' · evening run' +
      (asPublished ? ' · the verdict as published' : '');
    $('cover-h1').textContent = cover.h1 || 'No verdict.';
    $('cover-dek').textContent = cover.dek || '';
    const facts = clear($('market-facts'));
    // the chip sits beside the LABEL, not after the value: it qualifies that
    // fact and says so by where it is, and the fact is two rows rather than
    // three -- which is what keeps the workspace on the first screen at 390 px
    const fact = (dt, kids, key, tag) => facts.appendChild(el('div', { 'data-fact': key || dt }, [
      el('dt', null, [el('span', { text: dt }), tag || null]), el('dd', null, kids)]));
    // The regime belongs to the VERDICT, which is what the h1 and the dek are:
    // the two facts beside them are about time, and a third about the market
    // both read as one list and cost the workspace its place on a phone.
    const size = reg.size_multiplier;
    const sizeWords = size === 1 ? 'full size' : size === 0 ? 'no new longs' : isNum(size) ? 'size at ' + (size * 100).toFixed(0) + '%' : '';
    const regimeLine = clear($('cover-regime'));
    regimeLine.appendChild(chip((reg.verdict || 'unknown').toUpperCase(), REGIME_TONE[reg.verdict] || 'neutral', true));
    regimeLine.appendChild(el('span', { text: sizeWords + (isNum(b.ratio_10d) ? ' · 10-day ratio ' + plain(b.ratio_10d) : '') }));
    // The two facts, apart. "data through" is what was measured and when it
    // was published; the publication chip belongs HERE and covers this line
    // alone. "plan for" is the session the plans are for and where its entry
    // window stands, which no freshness chip can answer.
    fact('data through', [el('span', { text: dateWords(run.session) + (run.session_state === 'closed' ? ' · closed on ' + dateWords(run.expected_session) : '') + ' · published ' + timeET(run.published_at) })],
      'data', chip(st.chip, st.tone, st.keepCase));
    const tm = av.timing;
    fact('plan for', [el('span', { text: tm.known ? dateWords(tm.session) + ' · window ' + windowWords(tm) : 'not recorded' })],
      'plan', chip(tm.known ? 'entry window ' + PHASE_WORDS[av.phase] : 'entry timing unavailable', tm.known ? PHASE_TONE[av.phase] : 'warn'));
    renderRefresh();
    const notice = $('demo-notice');
    if (notice) {
      clear(notice);
      if (demo) notice.appendChild(el('div', { 'class': 'sc-notice ss-demo', role: 'note' }, [el('span', { 'class': 'sc-eyebrow', text: 'sample data · fixture ' + String(data.fixture) }), el('p', { text: 'Do not trade sample data: this record is a pipeline-written fixture over a synthetic market; its bursts, coils, plans and chart-reader replies are test doubles.' })]));
      notice.hidden = !demo;
    }
    // the record's own call to action (Tomorrow's orders / Open model plans),
    // falling back to the model plans on a page that offers no order
    const links = clear($('market-links'));
    const offered = !!(av && av.offered), label = offered ? (cover.action_label || 'Open model plans') : 'Open model plans', target = offered ? (cover.action_target || '#hold') : '#hold';
    links.appendChild(el('a', { 'class': 'sc-link--quiet', id: 'cover-action', href: target, text: label }));
    // the two views these reach, spelled as the nav spells them: one line at
    // 390 px, which is what leaves room for the update control beside them
    links.appendChild(el('a', { 'class': 'sc-link--quiet', href: '#/market', text: 'market' }));
    links.appendChild(el('a', { 'class': 'sc-link--quiet', href: '#/method', text: 'method' }));
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
    // what the record says about WHEN its plans apply, and what its calendar
    // could not read. Printed here rather than argued: the run wrote it.
    const tm = av.timing;
    if (tm.known) {
      line('The plans are for ' + dateWords(tm.session) + ', whose scheduled entry window is ' + windowWords(tm) +
        ' (' + tm.window + '), have the orders ready by ' + clockET(tm.et.prepareBy) + '. Times are ' +
        ((run.timing || {}).timezone || 'America/New_York') + ', carried with their offsets so no clock here guesses one.' +
        (tm.closedSession ? ' The market was closed on ' + dateWords(tm.closedSession) + ', so the plans dated for it apply to this session instead.' : ''));
      tm.limits.forEach((k) => line('Entry-timing limitation: ' + TIMING_LIMITS[k]));
    } else {
      line('This record does not say which session its plans are for' + (tm.present ? ' in a shape this page can read' : '') +
        ', so the page names no entry deadline for them: research only.');
    }
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
  // The guard every current-ticket action asks immediately before it acts:
  // null to go ahead, else the reason it is refused NOW. It re-reads the clock
  // rather than trusting the answer the surface was drawn with.
  //: the last refusal a copy control gave, so the reader is told it did not
  //: copy even though the surface it was on is rebuilt in the same breath
  let copyRefused = null;
  function copyGuard() {
    if (!current || !current.run) return 'No record is loaded, so there is no ticket to copy.';
    const nowAv = clockPinned ? av : availability(current, new Date());
    return nowAv.offered ? null : nowAv.reason;
  }
  // A copy is an ACTION, and the clock may have moved since the button was
  // drawn: a reader who opened the disclosure at 9:55 and copied at 10:02
  // would otherwise carry a ticket out of a window that closed in between. So
  // the guard is asked again here, immediately before the write, and a refusal
  // replaces the button with its reason rather than copying anyway.
  function copyButton(getText, pre, guard) {
    const btn = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', text: 'Copy', 'data-copy': '' });
    btn.addEventListener('click', () => {
      const refusal = guard ? guard() : null;
      if (refusal) {
        btn.disabled = true;
        btn.textContent = 'No longer offered';
        // recorded as page state first: catching the page up rebuilds the very
        // surface this button is in, so a note appended here would not survive
        copyRefused = { ticker: pre && pre.getAttribute('data-ticker'), text: 'Nothing was copied: ' + refusal };
        reclock();
        return;
      }
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
  // What the record published for a ticket the clock has withdrawn: the same
  // lines, printed and dated, with no copy control. A window that ended is
  // not a reason to hide what was published for it -- the reader may need to
  // read back an order already sitting in a broker -- but it is every reason
  // not to hand it over as something to place now.
  function recordedTicket(plan, avail) {
    const lines = ticket(plan.order_json) || [];
    const wrap = el('div', { 'class': 'ss-order ss-order--history', 'data-recorded-ticket': plan.ticker || '' });
    wrap.appendChild(el('div', { 'class': 'ss-order__head' }, [
      el('span', { 'class': 'sc-eyebrow', style: 'margin:0', text: 'what the record published for ' + dateWords(avail.timing.session) }),
      chip(avail.lead, PHASE_TONE[avail.phase])]));
    const pre = el('pre', { 'class': 'ss-order__pre', 'data-recorded': '', 'data-ticker': plan.ticker || '' });
    lines.forEach((line, i) => { if (i) pre.appendChild(d.createTextNode('\n')); pre.appendChild(el('span', { text: line })); });
    wrap.appendChild(pre);
    wrap.appendChild(el('p', { 'class': 'ss-order__readback', text: 'History, not an order to place. ' + cancelLine() }));
    return wrap;
  }
  // the order, as written by the run: shown only when the plan carries one,
  // the page is not stale, pending or without a verdict, AND the session its
  // entry window belongs to has not had that window close
  function orderBlock(plan, extraHint, withheld) {
    const lines = withheld ? null : ticket(plan.order_json);
    const wrap = el('div', { 'class': 'ss-order' });
    if (!lines) { wrap.appendChild(el('p', { 'class': 'sc-hint', text: extraHint || 'No order.' })); return wrap; }
    const pre = el('pre', { 'class': 'ss-order__pre', 'data-order': '', 'data-ticker': plan.ticker || '' });
    lines.forEach((line, i) => { if (i) pre.appendChild(d.createTextNode('\n')); pre.appendChild(el('span', { text: line })); });
    wrap.appendChild(el('div', { 'class': 'ss-order__head' }, [el('span', { 'class': 'sc-eyebrow', style: 'margin:0', text: 'the order, in Fidelity’s field order' }), copyButton(() => pre.textContent, pre, copyGuard)]));
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
    // "tomorrow" is only true of a chart drawn from tonight's record; a saved
    // setup's chart is of a night that has already had its next session
    if (text(c.signalSession)) o.futureLabel = 'the session after →';
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
      burstVolumeRatio: volumeRatio(b).value, rangeExpansion: isNum(rng) ? rng : null,
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
  // Saying there is no ticket, once. STATUS_WORDS already answers "no ticket"
  // for below_grade, not_admitted and no_plan and CUT_WORDS answers "ticket
  // withheld", so a sentence that leads with those words must not close with
  // them too: the page printed "for observation, no ticket: no ticket" on
  // thirteen fixture stock pages, and "No ticket tonight (no ticket)".
  const NO_TICKET = 'no ticket';
  // a reason that already opens with the words for "there is no ticket"
  const saysNoTicket = (s) => { s = text(s).toLowerCase(); return s.indexOf(NO_TICKET) === 0 || s.indexOf(CUT_WORDS.withheld) === 0; };
  // the record's own reason, else the status words -- but never the bare
  // words "no ticket", which every caller here has already said
  function noTicketWhy(c) {
    const own = text(c && c.reason);
    if (own) return own.replace(/[.]$/, '');
    const w = statusWords(c && c.status)[0];
    return w && w !== NO_TICKET ? w : '';
  }
  // `lead`, then the record's own reason -- or the reason alone when it
  // already leads with those words, so neither is said twice.
  function noTicketPhrase(lead, c) {
    const why = noTicketWhy(c);
    if (!why) return lead;
    return saysNoTicket(why) ? why : lead + ': ' + why;
  }
  // the long form, for the plan disclosure: the reason in full, once
  const noTicketLine = (c) => cap(sentence(noTicketPhrase('No ticket tonight', c)));
  // the short form, for the decision summary, which is a summary: the words
  // the card's chip already wears, with no parenthesis when they are the lead
  // itself. The reason in full belongs to the action area and the disclosure,
  // and the Following hint takes these same short words because it sits
  // directly under the action area that has just printed the reason.
  const noTicketLead = (c) => {
    const w = statusWords(c && c.status)[0];
    return 'No ticket tonight' + (w && w !== NO_TICKET ? ' (' + w + ')' : '') + '.';
  };
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
        measures: [['gain', pct(b.gain_pct)], ['vol', isNum(volumeRatio(b).value) ? volumeTimes(b) + '×' : '—'], ['close', usd(b.close)]] };
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
  // ------------------------------------------------- the one visible-candidate selector
  // The cards, the map, the counts, the previous/next stepper, the chooser's
  // stage groups and the search all read `visible(stage)`. One list, so the
  // map can never show a population the cards do not.
  const LENS_KEY = 'spicystock:lens:v1';
  const stored = { bursts: null, 'setting-up': null, sort: null };
  function loadLens() {
    try {
      const raw = w.localStorage && w.localStorage.getItem(LENS_KEY), saved = raw ? JSON.parse(raw) : null;
      if (!saved || typeof saved !== 'object') return;
      STAGES.forEach((s) => { if (LENSES[s].some((l) => l[0] === saved[s])) stored[s] = saved[s]; });
      if (SORTS.some((x) => x[0] === saved.sort)) stored.sort = saved.sort;
    } catch (e) { /* a blocked or corrupt store keeps the record's own default */ }
  }
  function saveLens() {
    try { w.localStorage.setItem(LENS_KEY, JSON.stringify({ bursts: stored.bursts, 'setting-up': stored['setting-up'], sort: stored.sort })); } catch (e) { /* not remembered; still applied */ }
  }
  // the lens a first visit opens on: A-quality when this record archived an
  // A or A+ burst, else every burst -- never an empty first screen
  function defaultLens(stage) {
    if (stage !== 'bursts') return 'all';
    return model && model.stages.bursts.some((c) => model.tradeGrades.indexOf(c.grade) >= 0) ? 'a' : 'all';
  }
  const lensOf = (stage) => state.lens[stage] || defaultLens(stage);
  // the ids this browser's shelf holds for tonight's record, rebuilt only when
  // the shelf changes (a 400-burst stage asks this once per render, not 400 times)
  let followIndex = null;
  function followedIds() {
    if (followIndex) return followIndex;
    followIndex = {};
    try { SCStock.follow.list().forEach((it) => { if (it && it.id) followIndex[it.id] = true; }); } catch (e) { /* an unreadable shelf follows nothing */ }
    return followIndex;
  }
  const invalidateFollow = () => { followIndex = null; };
  function isFollowed(c) {
    const run = current.run || {}, app = current.app || {};
    // the identity is four fields, and this asks for them through the same
    // SCStock.follow.identity() the Follow button uses, so the two cannot drift
    try {
      return !!followedIds()[SCStock.follow.identity({ kind: c.stage === 'bursts' ? 'burst' : 'anticipation',
        ticker: c.ticker, session: run.session || '', rules_version: app.rules_version || '' })];
    } catch (e) { return false; }
  }
  function lensPass(c, lens) {
    if (lens === 'a') return model.tradeGrades.indexOf(c.grade) >= 0;
    if (lens === 'ticket') return c.status === 'ticket';
    if (lens === 'following') return isFollowed(c);
    return true;
  }
  const sortable = (stage) => stage === 'bursts';   // the coils record no session gain or volume ratio of their own
  const sortOf = (stage) => (sortable(stage) ? (stored.sort || state.sort || 'rank') : 'rank');
  // a missing measurement sorts last in either direction; it is never a zero
  function sorted(list, key) {
    if (key === 'rank') return list;
    const value = (c) => (key === 'gain' ? (isNum(c.row.gain_pct) ? c.row.gain_pct : null) : volumeRatio(c.row).value);
    return list.slice().sort((a, b) => {
      const va = value(a), vb = value(b);
      if (!isNum(va) && !isNum(vb)) return a.rank - b.rank;
      if (!isNum(va)) return 1;
      if (!isNum(vb)) return -1;
      return vb - va || a.rank - b.rank;
    });
  }
  const lensed = (stage) => (model.stages[stage] || []).filter((c) => lensPass(c, lensOf(stage)));
  function visible(stage) {
    return sorted(lensed(stage).filter((c) => matches(c, state.query)), sortOf(stage));
  }
  const lensCount = (stage, lens) => (model.stages[stage] || []).filter((c) => lensPass(c, lens)).length;
  // the state that decides which cards exist and in what order; the picks, the
  // map and the stepper are all rebuilt together when it changes
  const picksKey = () => state.stage + '|' + lensOf(state.stage) + '|' + sortOf(state.stage) + '|' + state.query;
  function setLens(stage, lens, remember) {
    state.lens[stage] = lens;
    if (remember) { stored[stage] = lens; saveLens(); }
  }
  const lensIsDefault = (stage) => lensOf(stage) === defaultLens(stage);
  const filtersActive = () => !lensIsDefault(state.stage) || !!state.query || sortOf(state.stage) !== 'rank';

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
  const state = { view: 'explore', stage: null, selected: { bursts: null, 'setting-up': null }, query: '', range: 60, notice: '', picksKey: null, detailKey: null, gesture: false,
    lens: { bursts: null, 'setting-up': null }, sort: 'rank', pins: [], pinAsk: null };
  let current = null, model = null, st = null, pendingNotice = '', pendingFocus = '', chooserOpener = null;
  //: the shared action-availability answer, recomputed on every render and on
  //: every clock re-reading. `st` is its publication half and stays what it
  //: was; every surface that offers an action asks this and nothing else.
  let av = null;
  //: whether a RECORD is on screen. `failed()` leaves `current` a stub so the
  //: Following shelf and a saved setup still read, and that stub has a `run`
  //: object -- so "is there a record" cannot be asked of `current` alone, and
  //: a clock re-reading over the no-record page would repaint the market bar
  //: with "No verdict." over the sentence saying the record could not be read.
  let loaded = false;
  //: the clock the page is reading. Injected (SCStock.now, or a Date handed to
  //: render) so a test pins an instant; when it is injected, the page does not
  //: move it on its own -- a pinned clock that ticked would be no pin at all.
  let clockAt = null, clockPinned = false;
  const nowAt = () => clockPinned ? new Date(clockAt.getTime()) : new Date();
  //: the route the reader was on before a saved setup was opened over it
  let lastHash = '';
  let demo = false;   // the record is a pipeline-written fixture over a synthetic market
  const LEGACY = {
    hold: { view: 'record', anchor: 'hold' }, record: { view: 'record', anchor: 'record-card' }, breadth: { view: 'market' }, method: { view: 'method' },
    orders: { view: 'explore', open: 'orders' }, scan: { view: 'explore', open: 'scan' }, 'scan-details': { view: 'explore', open: 'scan' },
    'closest-miss': { view: 'explore', open: 'scan', anchor: 'closest-miss' }, tomorrow: { view: 'explore', stage: 'bursts' }, trades: { view: 'explore', stage: 'bursts' },
    alerts: { view: 'explore', stage: 'setting-up' }, 'also-quiet': { view: 'explore', stage: 'setting-up' }, cover: { view: 'explore' }, main: { view: 'explore' }, next: { view: 'explore', anchor: 'next' },
    following: { view: 'setups', anchor: 'following' }
  };
  function parseHash(hash) {
    hash = String(hash || '').replace(/^#/, '');
    if (!hash || hash === '/') return { view: 'explore' };
    if (hash.charAt(0) === '/') {
      const parts = hash.split('/').filter(Boolean).map((p) => { try { return decodeURIComponent(p); } catch (e) { return p; } });
      // A SAVED setup is named by its own identity, not by a stage and a
      // ticker: the symbol may be in another stage tonight, under a newer
      // signal, or in no list at all. `keepView` leaves the reader's view,
      // lens and selection exactly where they were -- the sheet opens over
      // them and closing it puts them back.
      if (parts[0] === 'followed') return parts.length === 2 ? { followed: parts[1], keepView: true } : { view: 'explore', unknown: '#' + hash };
      if (parts[0] === 'following') return { view: 'setups' };
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
  const savedHash = (id) => '#/followed/' + encodeURIComponent(id);
  function applyRoute(route, first) {
    const previousView = state.view;
    state.view = route.keepView && VIEWS.indexOf(state.view) >= 0 ? state.view : (VIEWS.indexOf(route.view) >= 0 ? route.view : 'explore');
    if (!model) { showView(false); if (route.followed) openSaved(route.followed, true); return; }
    state.notice = route.unknown ? 'There is no ' + route.unknown + ' on this page; showing ' + (route.view === 'explore' ? 'Explore' : cap(route.view)) + '.' : pendingNotice;
    pendingNotice = '';
    let canon = '#/' + state.view;
    if (state.view === 'explore') {
      let stage = route.stage || state.stage || model.defaultStage;
      const wasOn = state.selected[stage];   // before the route moves it: what the reader was already looking at
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
      // A route that NAMES A STOCK THE READER IS NOT ALREADY ON is a request to
      // inspect that stock: when the lens hides it the lens widens, says so, and
      // is not written to storage -- so the next fresh visit still opens on the
      // reader's own choice. A route over the stock already chosen is a
      // re-render (a lens change, an unfollow) and must widen nothing: the page
      // jumped out of the Following lens the moment the last setup left it.
      const named = route.ticker ? model.byId[stage + ':' + route.ticker] : null;
      const asked = named && named.id !== wasOn ? named : null;
      if (asked && !lensPass(asked, lensOf(stage))) {
        const was = lensOf(stage);
        setLens(stage, 'all', false);
        state.notice = (state.notice ? state.notice + ' ' : '') + asked.ticker + ' is outside the ' + LENS_WORDS[was] + ' lens; showing every ' + (stage === 'bursts' ? 'burst' : 'setup') + ' so it can be inspected.';
      }
      // The selection belongs to the LENS, not to the search box: a find-as-you-
      // type with no match narrows the cards and leaves the chosen stock alone,
      // while a lens that no longer holds it moves to the first it does hold.
      const inLens = sorted(lensed(stage), sortOf(stage));
      const sel = state.selected[stage] ? model.byId[state.selected[stage]] : null;
      if (!sel || inLens.indexOf(sel) < 0) state.selected[stage] = inLens.length ? inLens[0].id : null;
      canon = routeHash(stage, state.selected[stage]);
    }
    showView(!first && previousView !== state.view);
    if (state.view === 'explore') renderExplore();
    // Keep the opener node through a saved sheet's open/close route changes.
    // Store changes and record loads already refresh this destination.
    if (state.view === 'setups' && previousView !== 'setups') renderFollowing();
    // the saved setup keeps its own hash, so a bookmark reopens it; every
    // other route is rewritten to the one it resolved to
    if (route.followed) canon = savedHash(route.followed);
    if (w.location.hash !== canon && w.history && w.history.replaceState) { try { w.history.replaceState(null, '', canon); } catch (e) { /* a file: URL may refuse */ } }
    if (!route.followed) lastHash = canon;
    if (route.followed) openSaved(route.followed, first); else closeSaved();
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
      // name, count and the sub are laid out by grid area, so the phone can put
      // the count beside the name and give the sub -- which is where the ticket
      // count is said -- the card's full width instead of dropping it
      const btn = el('button', { 'class': 'ss-stage', type: 'button', 'data-stage': s, 'data-count': String(n), 'aria-pressed': 'false', 'aria-controls': 'workspace' }, [
        el('span', { 'class': 'ss-stage__name', text: STAGE_NAME[s] }),
        el('span', { 'class': 'ss-stage__count' }, [d.createTextNode(String(n)), el('small', { text: n === 1 ? 'stock' : 'stocks' })]),
        el('span', { 'class': 'ss-stage__sub', text: sub })
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
    const btn = el('button', { 'class': 'ss-pick', type: 'button', 'data-id': c.id, 'data-ticker': c.ticker, 'data-status': c.status, 'data-rank': String(c.rank), 'aria-pressed': 'false', 'aria-controls': 'detail', tabindex: '-1' }, [
      el('span', { 'class': 'ss-pick__row' }, [
        el('span', { 'class': 'ss-pick__ticker sc-case', text: c.ticker }),
        c.grade ? chip(c.grade + (isNum(c.score) ? ' · ' + c.score.toFixed(1) : ''), 'brand', true) : null,
        chip(sw[0], sw[1])
      ]),
      el('span', { 'class': 'ss-pick__reason', text: pickReason(c) }),
      el('span', { 'class': 'ss-pick__measures' }, c.measures.map((m) => el('span', null, [m[0] + ' ', el('b', { text: m[1] })]))
        // the published rank stays a label of its own, whatever the cards are sorted by
        .concat([el('span', { 'class': 'ss-pick__rank', text: 'rank ' + plain(c.rank) })]))
    ]);
    btn.addEventListener('click', () => { state.gesture = true; navigate(routeHash(c.stage, c.id)); });
    btn.addEventListener('focus', () => { d.querySelectorAll('#pick-list .ss-pick').forEach((p) => { p.tabIndex = p === btn ? 0 : -1; }); });
    // the Compare toggle is a SIBLING of the selection button, never inside it:
    // pinning must not choose the stock, and choosing must not pin it
    return el('div', { 'class': 'ss-pick-item', role: 'listitem' }, [btn, el('div', { 'class': 'ss-pick__tools' }, [saveButton(c), pinButton(c, 'card')])]);
  }
  // ---- the lens row: four ways to narrow a stage, the counts, the reset
  function lensTabs(stage) {
    const box = el('div', { 'class': 'sc-tabs ss-lens__tabs', role: 'group', 'aria-labelledby': 'lens-label' });
    const now = lensOf(stage);
    LENSES[stage].forEach((l) => {
      const n = lensCount(stage, l[0]);
      const t = el('button', { 'class': 'sc-tab ss-lens__tab', type: 'button', 'data-lens': l[0], 'data-count': String(n),
        'aria-pressed': l[0] === now ? 'true' : 'false', title: l[2] }, [d.createTextNode(l[1]), el('small', { text: String(n) })]);
      t.addEventListener('click', () => {
        if (lensOf(stage) === l[0]) return;
        setLens(stage, l[0], true);
        state.notice = '';
        state.gesture = true;
        applyRoute(parseHash(w.location.hash));
      });
      box.appendChild(t);
    });
    return box;
  }
  function sortTabs(stage) {
    const box = el('div', { 'class': 'sc-tabs ss-lens__tabs', role: 'group', 'aria-labelledby': 'sort-label' });
    const now = sortOf(stage);
    SORTS.forEach((s) => {
      const t = el('button', { 'class': 'sc-tab', type: 'button', 'data-sort': s[0], 'aria-pressed': s[0] === now ? 'true' : 'false', title: s[2], text: s[1] });
      t.addEventListener('click', () => {
        if (sortOf(stage) === s[0]) return;
        state.sort = s[0]; stored.sort = s[0]; saveLens();
        state.gesture = true;
        applyRoute(parseHash(w.location.hash));
      });
      box.appendChild(t);
    });
    return box;
  }
  // Where the lens row lives. On a desktop it rides in the stage band, in the
  // space beside the two cards, so narrowing a stage costs the chart nothing
  // of the first screen. On a phone that band is already two stacked cards
  // and the one thing that must stay above the fold is the search, so the
  // lens goes under it, with the list it narrows.
  const lensHome = () => (narrow() ? (($('picks') || {}).querySelector ? $('picks').querySelector('.ss-picks__head') : null) : $('stage-band'));
  function renderLens(stage) {
    const host = $('lens');
    if (!host) return;
    const home = lensHome();
    if (home && host.parentNode !== home) {
      if (narrow()) home.insertBefore(host, $('picks-status'));
      else home.appendChild(host);
    }
    clear(host);
    host.appendChild(el('div', { 'class': 'sc-field sc-field--group ss-lens__field' }, [
      el('span', { 'class': 'sc-field__label', id: 'lens-label', text: 'show' }), lensTabs(stage)]));
    if (sortable(stage)) host.appendChild(el('div', { 'class': 'sc-field sc-field--group ss-lens__field' }, [
      el('span', { 'class': 'sc-field__label', id: 'sort-label', text: 'sort' }), sortTabs(stage)]));
    if (filtersActive()) {
      const reset = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm ss-lens__reset', type: 'button', 'data-reset': '', text: 'Reset' });
      reset.addEventListener('click', () => {
        setLens(stage, defaultLens(stage), true);
        state.sort = 'rank'; stored.sort = 'rank'; saveLens();
        state.query = ''; $('search').value = '';
        state.notice = '';
        state.gesture = true;
        applyRoute(parseHash(w.location.hash));
      });
      host.appendChild(reset);
    }
  }
  // a lens with nothing in it says which lens, why, and offers one way out
  function emptyLens(stage, lens) {
    const box = el('div', { 'class': 'ss-picks__empty', 'data-empty': 'lens', 'data-lens': lens });
    const total = model.stages[stage].length, noun = stage === 'bursts' ? 'burst' : 'setup';
    const reg = ((current.breadth || {}).regime || {}).verdict;
    let why;
    if (lens === 'a') why = 'No ' + noun + ' in tonight’s record is graded ' + model.tradeGrades.join(' or ') + '. All ' + plural(total, noun) + ' are still here to inspect.';
    else if (lens === 'ticket') why = 'No ' + noun + ' carries a ticket in tonight’s record' + (reg === 'red' ? ': breadth is red, so the run wrote no order' : '') + '. All ' + plural(total, noun) + ' are still here to inspect.';
    else why = 'No saved setup matches this scan. My setups contains all your saved signals, including those absent or hidden here.';
    box.appendChild(el('p', { text: why }));
    const out = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', 'data-lens-out': 'all', text: 'Show all · ' + total });
    out.addEventListener('click', () => { setLens(stage, 'all', true); state.gesture = true; applyRoute(parseHash(w.location.hash)); });
    box.appendChild(out);
    return box;
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
    // a stock the LENS is hiding exists: say so and offer it, never "no such stock"
    const hidden = model.stages[stage].filter((c) => matches(c, q));
    if (hidden.length) {
      const one = hidden.find((c) => c.ticker === q) || hidden[0];
      box.setAttribute('data-empty', 'lens-hidden');
      box.appendChild(el('p', { text: (hidden.length === 1 ? one.ticker + ' is' : hidden.slice(0, 3).map((c) => c.ticker).join(', ') + (hidden.length > 3 ? ' and ' + (hidden.length - 3) + ' more are' : ' are')) + ' in ' + STAGE_NAME[stage] + ' tonight, hidden by the ' + LENS_WORDS[lensOf(stage)] + ' lens' + (one.grade ? ' (' + one.ticker + ' is graded ' + one.grade + ')' : '') + '.' }));
      const show = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', 'data-lens-out': 'all', text: 'Inspect ' + one.ticker + ' anyway' });
      show.addEventListener('click', () => {
        pendingNotice = one.ticker + ' is outside the ' + LENS_WORDS[lensOf(stage)] + ' lens; showing every ' + (stage === 'bursts' ? 'burst' : 'setup') + ' so it can be inspected.';
        setLens(stage, 'all', false); setQuery(''); state.gesture = true; navigate(routeHash(stage, one.id));
      });
      box.appendChild(show);
      const clearOnly = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', text: 'Clear search' });
      clearOnly.addEventListener('click', () => { setQuery(''); $('search').focus(); });
      box.appendChild(clearOnly);
      return box;
    }
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
    const lens = lensOf(stage), inLens = lensed(stage), shown = visible(stage), key = picksKey();
    renderLens(stage);
    renderDiscover(stage);
    // the stage's own total stays beside the subset, always
    $('picks-h2').textContent = STAGE_NAME[stage].toLowerCase() + ' · ' + shown.length + ' of ' + list.length;
    if (state.picksKey !== key) {
      clear(host);
      if (!list.length) host.appendChild(emptyStage(stage));
      else if (!inLens.length) host.appendChild(emptyLens(stage, lens));
      else if (!shown.length) host.appendChild(noMatch(stage, q));
      else shown.forEach((c) => host.appendChild(pickItem(c)));
      state.picksKey = key;
    }
    const sel = model.byId[state.selected[stage]];
    let seenSelected = false;
    host.querySelectorAll('.ss-pick').forEach((b) => { const on = !!sel && b.getAttribute('data-id') === sel.id; b.setAttribute('aria-pressed', on ? 'true' : 'false'); b.tabIndex = on ? 0 : -1; if (on) seenSelected = true; });
    if (!seenSelected) { const firstPick = host.querySelector('.ss-pick'); if (firstPick) firstPick.tabIndex = 0; }
    if (sel && state.gesture && narrow()) { const b = host.querySelector('.ss-pick[aria-pressed="true"]'); if (b && b.scrollIntoView) b.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: reducedMotion() ? 'auto' : 'smooth' }); }
    // Which pins the lens hides is a reading of the CURRENT lens, so the tray
    // cannot be left behind by a change to it. It is redrawn only when what it
    // SHOWS has changed, because this runs on every search keystroke and a
    // rebuild under the reader would take the open replace-prompt with it.
    if (trayKey !== trayState()) renderTray();
    syncPins();
    // the lens, the subset and the stage total in one sentence; on a page that
    // offers no order, a recorded ticket is named as the record's, not as one
    const lensLine = lens === 'all' ? '' : ' · ' + LENS_WORDS[lens] + ' lens' + (lens === 'ticket' && av && !av.offered ? ', as the record wrote them — ' + av.lead + ', so no order is offered' : '');
    let status;
    if (!list.length) status = 'Nothing in ' + STAGE_NAME[stage] + ' tonight.';
    else if (!inLens.length) status = 'No ' + (stage === 'bursts' ? 'burst' : 'setup') + ' matches the ' + LENS_WORDS[lens] + ' lens; ' + plural(list.length, 'stock') + ' in ' + STAGE_NAME[stage] + '.';
    else if (q) status = shown.length + ' of ' + inLens.length + ' match ‘' + q + '’' + (shown.length ? '; Enter chooses the first.' : '.') + lensLine;
    else if (sel) status = sel.ticker + ' · ' + (shown.indexOf(sel) + 1) + ' of ' + shown.length + ' shown, ' + list.length + ' in ' + STAGE_NAME[stage] + lensLine + (sortOf(stage) === 'rank' ? '' : ' · sorted by ' + SORT_WORDS[sortOf(stage)]) + '.';
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
    const cover = current.cover || {}, total = model.stages[stage].length, lens = lensOf(stage);
    if (total && !lensed(stage).length) {
      box.setAttribute('data-detail', 'lens');
      box.appendChild(el('strong', { text: 'Nothing matches the ' + LENS_WORDS[lens] + ' lens. ' }));
      box.appendChild(d.createTextNode('All ' + plural(total, 'stock') + ' in ' + STAGE_NAME[stage] + ' are still in the record; widen the lens beside the list to inspect them.'));
      return box;
    }
    box.appendChild(el('strong', { text: total ? 'Choose a stock. ' : 'Nothing to show for ' + STAGE_NAME[stage] + ' tonight. ' }));
    box.appendChild(d.createTextNode(total ? 'Its chart, its conditions and its conditional plan appear here.' : (cover.dek ? cover.dek + ' ' : '') + 'The market view has the breadth in full; the record view has the open model plans.'));
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
      ? (c.name ? c.name + ' · ' : '') + usd(b.close) + ' · ' + pct(b.gain_pct) + ' on ' + volumeTimes(b) + '× volume' + (b.scan && b.scan !== 'burst' ? ' · ' + words(b.scan) + ' scan' : '') + ' · rank ' + plain(c.rank)
      : (c.name ? c.name + ' · ' : '') + usd(b.close) + ' · ' + plain(b.quiet_days) + ' quiet days · ' + plain(b.range_pct) + '% range' + (c.quiet ? ' · also quiet' : ' · rank ' + plain(c.rank));
    const back = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm ss-detail__back', type: 'button', text: '↑ all stocks' });
    back.addEventListener('click', () => { scrollTo($('stages')); const sel = $('pick-list').querySelector('.ss-pick[aria-pressed="true"]'); if (sel) sel.focus({ preventScroll: true }); else $('search').focus({ preventScroll: true }); });
    return el('header', { 'class': 'ss-detail__head' }, [
      el('div', null, [
        el('div', { 'class': 'sc-eyebrow', text: STAGE_NAME[c.stage].toLowerCase() + ' · ' + (c.stage === 'bursts' ? 'burst on ' + dateWords(last) : 'coiled through ' + dateWords(last)) }),
        el('h2', { 'class': 'ss-detail__h2 sc-case', id: 'detail-h2', text: c.ticker }),
        el('p', { 'class': 'sc-hint ss-detail__sub', text: sub })
      ]),
      el('div', { 'class': 'ss-detail__chips' }, chips.concat([back])),
      detailTools(c)
    ]);
  }
  // the stepper walks the SAME visible candidates the cards and the map show,
  // so "next" never lands on a stock the lens is hiding; the Compare toggle
  // stands beside it, independent of the card that chose this stock
  function detailTools(c) {
    const shown = visible(c.stage), at = shown.indexOf(c);
    const box = el('div', { 'class': 'ss-detail__tools' });
    const step = (delta, label, aria) => {
      const b = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm ss-step', type: 'button', 'data-step': delta > 0 ? 'next' : 'prev', 'aria-label': aria, text: label,
        disabled: at < 0 || at + delta < 0 || at + delta >= shown.length ? '' : null });
      b.addEventListener('click', () => { const n = shown[at + delta]; if (n) { state.gesture = true; navigate(routeHash(n.stage, n.id)); } });
      return b;
    };
    box.appendChild(step(-1, '‹', 'Previous stock in this list'));
    box.appendChild(el('span', { 'class': 'ss-step__where', 'data-where': '', text: at < 0 ? 'not in these matches' : (at + 1) + ' of ' + shown.length }));
    box.appendChild(step(1, '›', 'Next stock in this list'));
    box.appendChild(pinButton(c, 'detail'));
    return box;
  }
  // ------------------------------------------------- the recorded evidence, and where it sits
  // Every anchor below is a DATE the run archived, resolved against the bars
  // the record carries. Nothing is derived: a check with no recorded date
  // range -- linearity, the trend's age, the run of up days -- gets no anchor
  // and says so, rather than a convincing region being drawn for it.
  const checksOf = (c) => { const m = {}; (((c.row || {}).quality || {}).checks || []).forEach((x) => { if (x && x.key) m[x.key] = x; }); return m; };
  const vetoedCheck = (key, vetoes) => (key === 'two_days' && vetoes.indexOf('up_days') >= 0) || (key === 'linearity' && vetoes.indexOf('not_linear') >= 0);
  // the four words the checklist's own fields spell, plus the veto: one place,
  // read by the tiles, the scan cells and the evidence panel alike
  function checkVerdict(chk, vetoed) {
    if (vetoed) return 'veto';
    if (!chk) return 'not measured';
    if (chk.pass) return chk.marginal ? 'partial' : 'pass';
    return chk.status === 'unmeasured' ? 'not measured' : 'fail';
  }
  const VERDICT_TONE = { pass: 'good', partial: 'warn', fail: 'danger', veto: 'danger', 'not measured': 'neutral' };
  // the signal session: the session the record was PUBLISHED FOR, never the
  // last bar in the frame -- a later observation appended to the series would
  // otherwise move the burst day onto a candle that never burst
  // A SAVED setup carries its own session (`signalSession`), because the night
  // it was archived is not tonight; a candidate of the loaded record has none
  // and reads the run's.
  function signalDate(c) {
    const run = current.run || {};
    const s = text(c.signalSession) || text(run.session);
    return s && idxOf(c.series, s) >= 0 ? s : null;
  }
  function evidenceItems(c) {
    const items = [], series = c.series;
    if (c.stage === 'bursts') {
      const b = c.row, q = b.quality || {}, base = q.base || {}, chk = checksOf(c), vetoes = q.vetoes || [];
      if (text(base.start) && text(base.end)) {
        const bd = (base.breakdown_dates || []).length;
        items.push({ key: 'base', label: ANCHOR_WORDS.base, from: base.start, to: base.end, low: base.low, high: base.high,
          lede: 'The quiet range the burst came out of, as the run recorded it.',
          measured: (isNum(base.sessions) ? plain(base.sessions) + ' sessions' : 'sessions not recorded') + ' · ' + plain(base.depth_pct) + '% deep · ' + usd(base.low) + '–' + usd(base.high) + (bd ? ' · ' + plural(bd, 'breakdown') : ''),
          checks: ['consolidation'] });
      }
      const sig = signalDate(c);
      if (sig) {
        items.push({ key: 'burst', label: ANCHOR_WORDS.burst, from: sig, to: sig, low: b.low, high: b.high,
          lede: 'The range-expansion session the scan found — the signal itself.',
          measured: pct(b.gain_pct) + ' on ' + volumeTimes(b) + '× volume · open ' + usd(b.open) + ' · high ' + usd(b.high) + ' · low ' + usd(b.low) + ' · close ' + usd(b.close),
          checks: ['close_near_high', 'range_expansion', 'volume'] });
        // the previous trading OBSERVATION, one archived bar back, never the previous date
        const i = idxOf(series, sig);
        if (i > 0) {
          const p = series[i - 1];
          items.push({ key: 'prior', label: ANCHOR_WORDS.prior, from: p.date, to: p.date, low: p.l, high: p.h,
            lede: 'The session before the signal — the last bar that printed before it, not the previous calendar day.',
            measured: 'open ' + usd(p.o) + ' · high ' + usd(p.h) + ' · low ' + usd(p.l) + ' · close ' + usd(p.c),
            checks: ['narrow_or_negative'] });
        }
      }
      return items.map((it) => Object.assign(it, { rows: it.checks.map((k) => ({ key: k, check: chk[k], verdict: checkVerdict(chk[k], vetoedCheck(k, vetoes)) })) }));
    }
    const r = c.row, box = r.box || {};
    if (text(box.start) && text(box.end)) {
      items.push({ key: 'box', label: ANCHOR_WORDS.box, from: box.start, to: box.end, low: box.low, high: box.high,
        lede: 'The coil the buy stop sits over, as the anticipation scans measured it.',
        measured: (isNum(box.sessions) ? plain(box.sessions) + ' sessions' : 'sessions not recorded') + ' · ' + usd(box.low) + '–' + usd(box.high) + (isNum(box.spread) ? ' · spread ' + plain(box.spread) + '%' : ''),
        note: 'Anticipation names are measured, not graded: the record carries no pass or fail for a coil.', rows: [] });
    }
    return items;
  }
  // the first range that holds the whole anchor, so "show the recorded range"
  // names a range that works rather than moving the reader somewhere blind
  function rangeHolding(c, item) {
    return CHART_RANGES.find((r) => { const s = rangeSlice(c, r).series; return idxOf(s, item.from) >= 0 && idxOf(s, item.to) >= 0; }) || null;
  }

  const chartHeight = () => (narrow() ? 300 : 400);
  // the plan's levels in one line beside the chart, the aim named even when it sits outside the visible range
  function referenceLine(c, g) {
    const plan = c.plan || {}, parts = [], burst = c.stage === 'bursts';
    const trig = burst ? plan.entry_ref : plan.trigger, lim = burst ? plan.entry_high : plan.limit;
    if (isNum(plan.stop)) parts.push('stop ' + usd(plan.stop));
    if (isNum(trig)) parts.push('trigger ' + usd(trig));
    if (isNum(lim)) parts.push('limit ' + usd(lim));
    if (burst && isNum(plan.day2_spent_above) && plan.day2_spent_above !== lim) parts.push('too extended over ' + usd(plan.day2_spent_above));
    if (burst && isNum(plan.entry_low) && isNum(trig) && Math.abs(plan.entry_low - trig) / trig > 0.005) parts.push('zone low ' + usd(plan.entry_low));
    const t = plan.targets || {};
    if (isNum(t.low) && isNum(t.high)) parts.push('aim +' + plain(t.low_pct) + '% ' + usd(t.low) + ' / +' + plain(t.high_pct) + '% ' + usd(t.high) + (g && g.target && g.target.offscale ? ' (outside the visible range)' : ''));
    return parts.length ? 'Levels: ' + parts.join(' · ') : 'No plan levels for this name.';
  }
  // One chart, owned by whoever built it. The host, its observers and its
  // tooltip belong to the returned handle, never to a page-wide variable, so
  // mounting a second chart cannot dispose the first.
  function mountChart(mount, c, height) {
    clear(mount);
    if (!c.series.length) {
      mount.style.minHeight = '';
      mount.appendChild(el('div', { 'class': 'ss-chart-empty', 'data-chart': 'unavailable' }, [
        el('strong', { text: 'Chart unavailable. ' }),
        'No daily bars are archived for ' + c.ticker + ' in tonight’s record' + (c.quiet ? ': it is on no list, so the run kept only its measures' : '') + '. The grade stands on the numbers; the conditions below carry them.'
      ]));
      return null;
    }
    const slice = rangeSlice(c, prefs.range);
    mount.style.minHeight = height + 'px';
    const host = SCStock.chart(slice.series, chartOptionsFor(c, slice.series, height));
    host.setAttribute('data-sessions', String(slice.series.length));
    host.setAttribute('data-ticker', c.ticker);
    host.setAttribute('data-stage', c.stage);
    host.setAttribute('data-range', slice.range);
    mount.appendChild(host);
    return { host: host, slice: slice };
  }
  // ------------------------------------------------- the chart panel, one instance at a time
  // Every id it writes is namespaced by `idPrefix`, and the host it mounts is
  // this handle's own: two panels can stand side by side and neither disposes
  // the other. `onPrefs` lets an owner that drives several panels from one set
  // of controls (the comparison) hide the per-panel strip and redraw the rest.
  function chartPanel(c, opts) {
    opts = opts || {};
    const idp = opts.idPrefix || 'chart';
    const run = current.run || {}, all = c.series, last = all.length ? all[all.length - 1] : null;
    // a saved setup brings the evidence the record carried the night it was
    // archived; a candidate of the loaded record has the run's own
    const evid = c.evidence && c.evidence.length ? c.evidence : evidenceItems(c);
    let live = null, host = null, chosen = null;
    const panelHeight = () => opts.height || chartHeight();
    const panel = el('figure', { 'class': 'ss-chart-panel', 'data-panel': idp, 'data-ticker': c.ticker, 'data-mode': prefs.mode, 'data-range': prefs.range });
    const legendBox = el('div', { 'class': 'ss-chart-panel__legend' });
    const modeTabs = el('div', { 'class': 'sc-tabs', role: 'group', 'aria-labelledby': idp + '-view-label' });
    const rangeTabs = el('div', { 'class': 'sc-tabs', role: 'group', 'aria-labelledby': idp + '-range-label' });
    const toggleInput = el('input', { type: 'checkbox', checked: prefs.closeLine ? '' : null });
    const toggle = el('label', { 'class': 'ss-chart-panel__toggle', hidden: prefs.mode === 'candles' ? null : '' }, [toggleInput, 'close line']);
    // one header strip: the symbol, its last close and session; the mode and the range controls together; the legend for the mode
    const tools = el('div', { 'class': 'ss-chart-panel__tools' }, [
      // two segmented groups in one strip: each is captioned, and the caption is
      // the group's own name (aria-labelledby), because "setup" is a mode AND a
      // range and neither row could be told from the other without it
      el('div', { 'class': 'sc-field sc-field--group' }, [el('span', { 'class': 'sc-field__label', id: idp + '-view-label', text: 'view' }), modeTabs]),
      el('div', { 'class': 'sc-field sc-field--group' }, [el('span', { 'class': 'sc-field__label', id: idp + '-range-label', text: 'range' }), rangeTabs]),
      toggle]);
    if (opts.tools === false) tools.hidden = true;
    panel.appendChild(el('div', { 'class': 'ss-chart-panel__head' }, [
      el('div', { 'class': 'ss-chart-panel__id' }, [
        el('span', { 'class': 'sc-figure', text: c.ticker }),
        last && isNum(last.c) ? el('span', { 'class': 'ss-chart-panel__price', text: usd(last.c) }) : null,
        el('span', { 'class': 'sc-hint', text: last ? 'close ' + dateWords(last.date) : 'no bars archived' }),
        demo ? chip('demo data', 'warn') : null
      ]), tools
    ]));
    const mount = el('div', { 'class': 'ss-chart-mount', id: idp + '-mount' });
    panel.appendChild(mount);
    // the chart's own key sits with the chart; the evidence controls and the
    // one explanation come directly under it, and the disclosure sentences last
    panel.appendChild(legendBox);
    const evidenceRow = el('div', { 'class': 'ss-evidence', 'data-evidence-row': idp });
    const explain = el('div', { 'class': 'ss-evidence__explain', id: idp + '-evidence', role: 'status', 'aria-live': 'polite' });
    panel.appendChild(evidenceRow); panel.appendChild(explain);
    const rangeLine = el('p', { 'class': 'ss-chart-panel__range' }), refLine = el('p', { 'class': 'ss-chart-panel__refs', 'data-refs': '' });
    panel.appendChild(el('figcaption', { 'class': 'sc-chart-caption' }, [
      rangeLine, refLine,
      // a saved setup says where ITS bars came from; a candidate of the loaded record says where tonight's did
      el('p', { text: (text(c.barsNote) || (all.length ? 'Alpaca ' + String(run.feed || '').toUpperCase() + ' daily bars, drawn from the same numbers as the plan' : 'No bars archived for ' + c.ticker)) + (c.row.chart ? ' · ' : '.') }, c.row.chart ? [el('a', { 'class': 'sc-link--quiet', href: c.row.chart, text: 'the chart the grader saw' })] : null)
    ]));

    // the marker in the CURRENT slice: the anchor is dates, so a range change
    // rebinds it and a range that does not hold it draws nothing at all
    function markOf() {
      if (!chosen || !live) return null;
      const s = live.slice.series, from = idxOf(s, chosen.from), to = idxOf(s, chosen.to);
      if (from < 0 || to < 0) return null;
      return { from: from, to: to, low: chosen.low, high: chosen.high, label: chosen.label.toLowerCase() };
    }
    function paint() {
      if (!host) return;
      host.update({ highlight: markOf() });
    }
    function drawExplain() {
      clear(explain);
      evidenceRow.querySelectorAll('[data-anchor]').forEach((b) => b.setAttribute('aria-pressed', chosen && b.getAttribute('data-anchor') === chosen.key ? 'true' : 'false'));
      panel.setAttribute('data-evidence', chosen ? chosen.key : '');
      explain.hidden = !chosen;
      if (!chosen) return;
      const s = live ? live.slice.series : [], inRange = !!live && idxOf(s, chosen.from) >= 0 && idxOf(s, chosen.to) >= 0;
      const span = chosen.from === chosen.to ? dateWords(chosen.from) : dateWords(chosen.from) + ' – ' + dateWords(chosen.to);
      const head = el('div', { 'class': 'ss-evidence__head' }, [
        el('h4', { text: chosen.label }), el('span', { 'class': 'ss-evidence__dates', text: span }),
        el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', 'data-evidence-clear': '', text: 'Clear' })
      ]);
      head.querySelector('[data-evidence-clear]').addEventListener('click', () => { select(null); });
      explain.appendChild(head);
      explain.appendChild(el('p', { 'class': 'ss-evidence__lede', text: chosen.lede }));
      explain.appendChild(el('p', { 'class': 'ss-evidence__measured' }, [el('span', { 'class': 'sc-eyebrow', text: 'measured' }), el('span', { text: chosen.measured })]));
      (chosen.rows || []).forEach((r) => {
        const tone = VERDICT_TONE[r.verdict] || 'neutral';
        explain.appendChild(el('div', { 'class': 'ss-evidence__check', 'data-check': r.key, 'data-verdict': r.verdict }, [
          el('div', { 'class': 'ss-evidence__check-head' }, [
            el('strong', { text: r.check ? (r.check.label || words(r.key)) : words(r.key) }), chip(r.verdict, tone)]),
          r.check && text(r.check.display)
            ? el('p', { 'class': 'ss-evidence__value', text: r.check.display })
            : el('p', { 'class': 'ss-evidence__value' }, [unreported('not measured in this record')]),
          r.check && text(r.check.threshold)
            ? el('p', { 'class': 'ss-evidence__threshold', text: 'his threshold: ' + r.check.threshold })
            : el('p', { 'class': 'ss-evidence__threshold' }, [unreported('no threshold archived')]),
          r.check && text(r.check.note) ? el('p', { 'class': 'ss-evidence__note', text: r.check.note }) : null
        ]));
      });
      if (chosen.note) explain.appendChild(el('p', { 'class': 'sc-hint', text: chosen.note }));
      if (!all.length) explain.appendChild(el('p', { 'class': 'sc-hint', 'data-anchor-state': 'no-bars', text: 'No bars are archived for ' + c.ticker + ' in tonight’s record, so this evidence has no chart to sit on. The numbers above are the record’s own.' }));
      else if (!inRange) {
        const r = rangeHolding(c, chosen);
        const p = el('p', { 'class': 'sc-hint', 'data-anchor-state': r ? 'out-of-range' : 'unanchored' }, [
          d.createTextNode(r ? 'These sessions are outside the range on screen. ' : 'These sessions are outside every range this chart offers, so they cannot be marked here. ')]);
        if (r) {
          const b = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', 'data-show-range': r, text: 'Show recorded range' });
          b.addEventListener('click', () => setRange(r));
          p.appendChild(b);
        }
        explain.appendChild(p);
      }
    }
    function select(key) {
      const next = key ? evid.find((x) => x.key === key) || null : null;
      chosen = next && chosen && chosen.key === next.key ? null : next;   // pressing the pressed one clears it
      paint();
      drawExplain();
    }
    function buildEvidence() {
      clear(evidenceRow);
      if (!evid.length) { evidenceRow.hidden = true; return; }
      evidenceRow.hidden = false;
      evidenceRow.appendChild(el('span', { 'class': 'sc-field__label', id: idp + '-evidence-label', text: 'show on chart' }));
      const group = el('div', { 'class': 'sc-tabs ss-evidence__tabs', role: 'group', 'aria-labelledby': idp + '-evidence-label' });
      evid.forEach((it) => {
        const b = el('button', { 'class': 'sc-tab', type: 'button', 'data-anchor': it.key, 'aria-pressed': 'false', 'aria-controls': idp + '-evidence', title: it.lede, text: it.label });
        b.addEventListener('click', () => select(it.key));
        group.appendChild(b);
      });
      evidenceRow.appendChild(group);
    }
    function disclose() {
      const g = host && host.geometry ? host.geometry() : null, series = live ? live.slice.series : [];
      rangeLine.textContent = series.length ? 'Showing ' + plural(series.length, 'session') + ', ' + dateShort(series[0].date) + ' – ' + dateShort(series[series.length - 1].date) + ' ' + String(series[series.length - 1].date).slice(0, 4) + ' · ' + live.slice.note + '.' : '';
      refLine.textContent = referenceLine(c, g);
      clear(legendBox); if (host && host.legend) legendBox.appendChild(host.legend());
      panel.setAttribute('data-mode', prefs.mode); panel.setAttribute('data-range', prefs.range);
      toggle.hidden = prefs.mode !== 'candles';
      modeTabs.querySelectorAll('.sc-tab').forEach((t) => t.setAttribute('aria-pressed', t.getAttribute('data-mode') === prefs.mode ? 'true' : 'false'));
      rangeTabs.querySelectorAll('.sc-tab').forEach((t) => t.setAttribute('aria-pressed', t.getAttribute('data-range') === prefs.range ? 'true' : 'false'));
      if (toggleInput.checked !== prefs.closeLine) toggleInput.checked = prefs.closeLine;
    }
    function setMode(m) {
      prefs.mode = m; savePrefs();
      if (host) host.update({ mode: m, closeLine: prefs.closeLine, highlight: markOf() });
      disclose(); drawExplain();
      if (typeof opts.onPrefs === 'function') opts.onPrefs('mode', m, handle);
    }
    function setRange(r) {
      prefs.range = r; savePrefs();
      if (host) {
        const slice = rangeSlice(c, r);
        live = { host: host, slice: slice };
        host.update(Object.assign({ series: slice.series }, chartOptionsFor(c, slice.series, panelHeight()), { highlight: markOf() }));
        host.setAttribute('data-sessions', String(slice.series.length)); host.setAttribute('data-range', slice.range);
      }
      disclose(); drawExplain();
      if (typeof opts.onPrefs === 'function') opts.onPrefs('range', r, handle);
    }
    function setCloseLine(on) {
      prefs.closeLine = !!on; savePrefs();
      if (host) host.update({ closeLine: prefs.closeLine });
      disclose();
      if (typeof opts.onPrefs === 'function') opts.onPrefs('closeLine', prefs.closeLine, handle);
    }
    CHART_MODES.forEach((m) => {
      const t = el('button', { 'class': 'sc-tab', type: 'button', 'data-mode': m, 'aria-pressed': m === prefs.mode ? 'true' : 'false', text: MODE_WORDS[m], disabled: all.length ? null : '' });
      t.addEventListener('click', () => setMode(m));
      modeTabs.appendChild(t);
    });
    CHART_RANGES.forEach((r) => {
      const t = el('button', { 'class': 'sc-tab', type: 'button', 'data-range': r, 'aria-pressed': r === prefs.range ? 'true' : 'false', 'aria-label': RANGE_WORDS[r], title: RANGE_WORDS[r], disabled: all.length ? null : '', text: r === 'setup' ? 'setup' : r });
      t.addEventListener('click', () => setRange(r));
      rangeTabs.appendChild(t);
    });
    toggleInput.addEventListener('change', () => setCloseLine(toggleInput.checked));
    live = mountChart(mount, c, panelHeight());
    host = live ? live.host : null;
    buildEvidence();
    disclose();
    drawExplain();
    const handle = {
      node: panel, ticker: c.ticker, candidate: c,
      // an owner driving several panels: apply the shared choice without
      // re-emitting it, so two panels cannot chase each other round
      applyPrefs: function () {
        if (!host) { disclose(); return; }
        const slice = rangeSlice(c, prefs.range);
        live = { host: host, slice: slice };
        host.update(Object.assign({ series: slice.series }, chartOptionsFor(c, slice.series, panelHeight()), { highlight: markOf() }));
        host.setAttribute('data-sessions', String(slice.series.length)); host.setAttribute('data-range', slice.range);
        disclose(); drawExplain();
      },
      showEvidence: function (key) { if (evid.some((x) => x.key === key) && (!chosen || chosen.key !== key)) select(key); },
      anchors: function () { return evid.map((x) => x.key); },
      dispose: function () { if (host && host.dispose) host.dispose(); host = null; live = null; }
    };
    return handle;
  }
  // the detail's own panel: the page-wide one, kept so renderDetail can drop it
  let detailPanel = null;
  function disposeChart() { if (detailPanel) { detailPanel.dispose(); detailPanel = null; } }
  function detailChart(c) {
    disposeChart();
    detailPanel = chartPanel(c, { idPrefix: 'chart' });
    return detailPanel.node;
  }
  // a checklist tile and its evidence control are the same mechanism: one
  // anchor, selected in one place, drawn on one chart
  function showEvidenceFromCheck(key) {
    const anchor = CHECK_ANCHOR[key];
    if (!detailPanel || !anchor) return;
    detailPanel.showEvidence(anchor);
    scrollTo(detailPanel.node);
    const btn = detailPanel.node.querySelector('[data-anchor="' + anchor + '"]');
    if (btn) btn.focus({ preventScroll: true });
  }
  // ---------------------------------------------------------------- Compare: exactly two setups
  // Pinning is not selecting and not following: it navigates nowhere, saves
  // nothing and writes nothing. Two candidates of the SAME stage and the same
  // published record can be compared; a third asks which to replace rather
  // than dropping one silently, and a pin from the other stage is explained.
  const PIN_MAX = 2;
  const pinned = () => state.pins.filter((id) => model && model.byId[id]);
  const isPinned = (c) => state.pins.indexOf(c.id) >= 0;
  function pinButton(c, where) {
    const on = isPinned(c);
    const b = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm ss-pin', type: 'button', 'data-pin': c.id, 'data-ticker': c.ticker, 'data-pin-where': where,
      'aria-pressed': on ? 'true' : 'false', 'aria-label': (on ? 'Unpin ' : 'Pin ') + c.ticker + ' for comparison', text: on ? 'Pinned' : 'Compare' });
    b.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); togglePin(c); });
    return b;
  }
  function togglePin(c) {
    state.pinAsk = null;
    const at = state.pins.indexOf(c.id);
    if (at >= 0) state.pins.splice(at, 1);
    else {
      const held = pinned().map((id) => model.byId[id]);
      if (held.length && held[0].stage !== c.stage) state.pinAsk = { kind: 'stage', id: c.id };
      else if (held.length >= PIN_MAX) state.pinAsk = { kind: 'replace', id: c.id };
      else state.pins.push(c.id);
    }
    renderTray(); syncPins();
  }
  function unpin(id) {
    const at = state.pins.indexOf(id);
    if (at >= 0) state.pins.splice(at, 1);
    state.pinAsk = null;
    renderTray(); syncPins();
  }
  function syncPins() {
    d.querySelectorAll('.ss-pin').forEach((b) => {
      const on = state.pins.indexOf(b.getAttribute('data-pin')) >= 0;
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.textContent = on ? 'Pinned' : 'Compare';
      b.setAttribute('aria-label', (on ? 'Unpin ' : 'Pin ') + b.getAttribute('data-ticker') + ' for comparison');
    });
  }
  // everything the tray draws: the pins, whether each is inside its stage's
  // own lens, and the question it may be asking
  let trayKey = null;
  function trayState() {
    if (!model) return '';
    return pinned().map((id) => { const c = model.byId[id]; return c.id + (lensPass(c, lensOf(c.stage)) ? '+' : '-') + lensOf(c.stage); }).join(',')
      + '|' + (state.pinAsk ? state.pinAsk.kind + ':' + state.pinAsk.id : '');
  }
  function renderTray() {
    const tray = $('compare-tray');
    if (!tray || !model) return;
    trayKey = trayState();
    const held = pinned().map((id) => model.byId[id]);
    clear(tray);
    tray.hidden = !held.length && !state.pinAsk;
    tray.setAttribute('data-pins', String(held.length));
    if (tray.hidden) return;
    tray.appendChild(el('span', { 'class': 'sc-eyebrow ss-tray__label', text: 'compare' }));
    const chips = el('div', { 'class': 'ss-tray__pins' });
    held.forEach((c) => {
      // a pin the reader's own lens no longer shows: kept, and SAID -- a stock
      // in the comparison that is not in the list behind it is otherwise a
      // stock from nowhere
      const hiddenBy = lensPass(c, lensOf(c.stage)) ? null : lensOf(c.stage);
      const item = el('span', { 'class': 'ss-tray__pin', 'data-ticker': c.ticker, 'data-hidden-by': hiddenBy }, [
        el('b', { 'class': 'sc-case', text: c.ticker }),
        el('small', { text: STAGE_NAME[c.stage].toLowerCase() + ' · ' + statusWords(c.status)[0] + (hiddenBy ? ' · outside the ' + LENS_WORDS[hiddenBy] + ' lens' : '') })
      ]);
      const x = el('button', { 'class': 'ss-tray__drop', type: 'button', 'aria-label': 'Remove ' + c.ticker + ' from the comparison', text: '✕' });
      x.addEventListener('click', () => unpin(c.id));
      item.appendChild(x);
      chips.appendChild(item);
    });
    if (held.length < PIN_MAX) chips.appendChild(el('span', { 'class': 'ss-tray__slot', text: 'pin one more' }));
    tray.appendChild(chips);
    const go = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', id: 'compare-open', text: 'Compare 2', disabled: held.length === PIN_MAX ? null : '' });
    go.addEventListener('click', () => openCompare());
    tray.appendChild(go);
    const clr = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', 'data-tray-clear': '', text: 'Clear' });
    clr.addEventListener('click', () => { state.pins = []; state.pinAsk = null; renderTray(); syncPins(); });
    tray.appendChild(clr);
    // the pins the lens is hiding, named once, each with one click to it: the
    // pin is never dropped and never silently outside the list behind it
    const away = held.filter((c) => !lensPass(c, lensOf(c.stage)));
    if (away.length) {
      const note = el('div', { 'class': 'ss-tray__away', 'data-away': String(away.length) });
      note.appendChild(el('p', { text: away.map((c) => c.ticker).join(' and ') + (away.length === 1 ? ' is' : ' are') + ' pinned but outside the ' + LENS_WORDS[lensOf(away[0].stage)] + ' lens, so ' + (away.length === 1 ? 'it is' : 'they are') + ' not in the list behind this. ' + (away.length === 1 ? 'It stays' : 'They stay') + ' pinned; the comparison reads the record, not the lens.' }));
      away.forEach((c) => {
        const b = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', 'data-tray-show': c.ticker, text: 'Show ' + c.ticker });
        b.addEventListener('click', () => { state.gesture = true; navigate(routeHash(c.stage, c.id)); });
        note.appendChild(b);
      });
      tray.appendChild(note);
    }
    if (!state.pinAsk) return;
    // the third pin, and the cross-stage pin: explained, decided by the reader
    const asked = model.byId[state.pinAsk.id];
    const ask = el('div', { 'class': 'ss-tray__ask', role: 'group', 'data-ask': state.pinAsk.kind });
    if (state.pinAsk.kind === 'stage') {
      ask.appendChild(el('p', { text: 'A comparison holds two stocks from one stage and one published session. ' + asked.ticker + ' is in ' + STAGE_NAME[asked.stage] + '; the pair pinned is in ' + STAGE_NAME[held[0].stage] + '. Their fields are not the same measurements, so they are not put side by side.' }));
      const fresh = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', 'data-ask-action': 'restart', text: 'Start a new comparison with ' + asked.ticker });
      fresh.addEventListener('click', () => { state.pins = [asked.id]; state.pinAsk = null; renderTray(); syncPins(); });
      ask.appendChild(fresh);
    } else {
      ask.appendChild(el('p', { text: 'Two are already pinned. Which does ' + asked.ticker + ' replace?' }));
      held.forEach((c) => {
        const b = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', 'data-ask-action': 'replace', 'data-ticker': c.ticker, text: 'Replace ' + c.ticker });
        b.addEventListener('click', () => { state.pins = state.pins.map((id) => (id === c.id ? asked.id : id)); state.pinAsk = null; renderTray(); syncPins(); });
        ask.appendChild(b);
      });
    }
    const cancel = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', 'data-ask-action': 'cancel', text: 'Keep the pair' });
    cancel.addEventListener('click', () => { state.pinAsk = null; renderTray(); syncPins(); });
    ask.appendChild(cancel);
    tray.appendChild(ask);
  }

  // the aligned evidence: every value read off the same fields the card and
  // the detail read, so a number here can never differ from the one there
  function cmpFacts(c) {
    const burst = c.stage === 'bursts', b = c.row, plan = c.plan || {}, q = b.quality || {}, cl = b.claude || {};
    const base = burst ? (q.base || {}) : (b.box || {});
    const vr = burst ? volumeRatio(b) : null;
    const trig = burst ? plan.entry_ref : plan.trigger, lim = burst ? plan.entry_high : plan.limit;
    const why = burst ? sentence(firstSentence(text(b.summary).replace(/^[A-Z0-9.\-]+:\s*/, ''))) : pickReason(c);
    const concern = firstText(burst ? cl.key_risk : '', plan.stop_risk_reason, plan.hazards, plan.notes);
    return {
      grade: c.grade ? c.grade + (isNum(c.score) ? ' · ' + c.score.toFixed(1) : '') : null,
      provenance: burst ? (cl.source === 'claude' ? 'chart reader' + (cl.agree === false ? ', lowered the grade' : cl.agree === true ? ', agreed' : '') + (cl.chart_seen === false ? ' · numbers only, no chart' : '') : 'checklist alone') : 'measured, not graded',
      gain: burst ? (isNum(b.gain_pct) ? pct(b.gain_pct) : null) : (isNum(b.pct_change_today) ? pct(b.pct_change_today) : null),
      volume: burst ? (vr.value === null ? null : vr.value.toFixed(1) + '×' + (vr.source === 'checklist' ? ' (the checklist’s copy)' : '')) : (isNum(b.volume_ratio) ? b.volume_ratio.toFixed(2) + '×' : null),
      base: text(base.start) && text(base.end) ? (isNum(base.sessions) ? plain(base.sessions) + ' sessions' : 'sessions not recorded') + ' · ' + usd(base.low) + '–' + usd(base.high) + (burst && isNum(base.depth_pct) ? ' · ' + plain(base.depth_pct) + '% deep' : '') + ' · ' + dateShort(base.start) + '–' + dateShort(base.end) : null,
      trigger: isNum(trig) ? usd(trig) : null,
      limit: isNum(lim) ? usd(lim) : null,
      stop: isNum(plan.stop) ? stopWords(plan) : null,
      stopPct: isNum(plan.stop_pct) ? plain(plan.stop_pct) + '% under the ' + usd(plan.sizing_price || lim) + ' limit' : null,
      why: why || null,
      concern: concern ? cap(sentence(concern)) : (c.flags.length ? cap(c.flags.map((f) => FLAG_WORDS[f] || words(f)).join(', ')) + '.' : null),
      ticket: c.status === 'ticket'
        ? (av && !av.offered ? 'recorded for ' + dateWords(av.timing.session) + ', ' + av.lead + ' — ' + (text(plan.order_line) || 'a ticket in the record')
          : (text(plan.order_line) || 'a ticket in the record'))
        : cap(sentence(noTicketPhrase('No ticket', c)))
    };
  }
  function compareTable(a, b) {
    const fa = cmpFacts(a), fb = cmpFacts(b), burst = a.stage === 'bursts';
    const rows = [
      ['grade', 'grade'], ['provenance', 'graded by'],
      ['gain', burst ? 'session gain' : 'change today'],
      ['volume', burst ? 'volume vs previous session' : 'volume vs its average'],
      ['base', burst ? 'base' : 'box'],
      ['trigger', 'trigger (buy stop)'], ['limit', 'ticket limit'], ['stop', 'stop'], ['stopPct', 'published stop distance'],
      ['why', 'main qualifying reason'], ['concern', 'principal concern'], ['ticket', 'ticket']
    ].filter((r) => fa[r[0]] !== null || fb[r[0]] !== null);
    const table = el('table', { 'class': 'sc-table sc-table--compact ss-compare__table', id: 'compare-table' });
    table.appendChild(el('caption', { 'class': 'sc-sr-only', text: 'What the record says about ' + a.ticker + ' and ' + b.ticker + '. A marked row is one where the two differ; it does not say which is better.' }));
    table.appendChild(el('thead', null, el('tr', null, [el('th', { scope: 'col', text: '' }), el('th', { scope: 'col', 'class': 'sc-case', text: a.ticker }), el('th', { scope: 'col', 'class': 'sc-case', text: b.ticker })])));
    const body = el('tbody');
    rows.forEach((r) => {
      const va = fa[r[0]], vb = fb[r[0]];
      body.appendChild(el('tr', { 'data-fact': r[0], 'data-differs': va !== null && vb !== null && va !== vb ? 'true' : 'false' }, [
        el('th', { scope: 'row', text: r[1] }),
        el('td', { 'data-missing': va === null ? '' : null }, [va === null ? unreported('not recorded') : va]),
        el('td', { 'data-missing': vb === null ? '' : null }, [vb === null ? unreported('not recorded') : vb])
      ]));
    });
    table.appendChild(body);
    return table;
  }
  let comparePanels = [], compareReturn = null;
  function disposeCompare() {
    comparePanels.forEach((p) => p.dispose());
    comparePanels = [];
  }
  // one identity builder, used inside each side on a desktop and in the phone's
  // shared strip, so both symbols and both statuses stay on screen either way
  function compareId(c, side, tag) {
    const sw = statusWords(c.status);
    // the symbol and its chips on one line, the company name on a second that
    // never wraps: the two panels then start their charts at the same height,
    // whatever the record calls the company
    return el('div', { 'class': 'ss-compare__id', 'data-side': side, 'data-id-of': c.ticker }, [
      el('div', { 'class': 'ss-compare__id-row' }, [
        el('span', { 'class': 'ss-compare__tag', 'aria-hidden': 'true', text: tag || side.toUpperCase() }),
        el('h3', { 'class': 'sc-case', text: c.ticker }),
        c.grade ? chip(c.grade + (isNum(c.score) ? ' · ' + c.score.toFixed(1) : ''), 'brand', true) : null,
        chip(sw[0], sw[1])
      ]),
      el('p', { 'class': 'sc-hint ss-compare__name', text: c.name || '—' })
    ]);
  }
  function compareSide(c, side, idp, height) {
    const panel = chartPanel(c, { idPrefix: idp, tools: false, height: height });
    comparePanels.push(panel);
    const box = el('section', { 'class': 'ss-compare__side', 'data-side': side, 'data-ticker': c.ticker, 'aria-label': c.ticker });
    box.appendChild(compareId(c, side));
    box.appendChild(panel.node);
    const actions = el('div', { 'class': 'ss-compare__actions' });
    const open = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', 'data-open-setup': c.ticker, text: 'Open setup' });
    open.addEventListener('click', () => { closeCompare(); pendingFocus = 'detail'; state.gesture = true; navigate(routeHash(c.stage, c.id)); });
    actions.appendChild(open);
    actions.appendChild(followBlock(c));
    box.appendChild(actions);
    return box;
  }
  function buildCompare(dlg, a, b) {
    disposeCompare();
    clear(dlg);
    const run = current.run || {};
    const wrap = el('div', { 'class': 'ss-compare__wrap' });
    const close = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', id: 'compare-close', text: 'Close' });
    close.addEventListener('click', () => closeCompare());
    wrap.appendChild(el('header', { 'class': 'ss-compare__head' }, [
      el('div', null, [
        el('div', { 'class': 'sc-eyebrow', text: STAGE_NAME[a.stage].toLowerCase() + ' · ' + dateWords(run.session) + (demo ? ' · demo data' : '') }),
        el('h2', { id: 'compare-h2' }, [el('span', { 'class': 'sc-case', text: a.ticker }), d.createTextNode(' and '), el('span', { 'class': 'sc-case', text: b.ticker })])
      ]), close]));
    // the common controls: one choice, both charts; each chart keeps its own
    // price scale and its own dates, because they are two different stocks
    const modeTabs = el('div', { 'class': 'sc-tabs', role: 'group', 'aria-labelledby': 'compare-view-label' });
    const rangeTabs = el('div', { 'class': 'sc-tabs', role: 'group', 'aria-labelledby': 'compare-range-label' });
    const abTabs = el('div', { 'class': 'sc-tabs ss-compare__ab', role: 'group', 'aria-labelledby': 'compare-ab-label' });
    const tools = el('div', { 'class': 'ss-compare__tools' }, [
      el('div', { 'class': 'sc-field sc-field--group' }, [el('span', { 'class': 'sc-field__label', id: 'compare-view-label', text: 'view' }), modeTabs]),
      el('div', { 'class': 'sc-field sc-field--group' }, [el('span', { 'class': 'sc-field__label', id: 'compare-range-label', text: 'range' }), rangeTabs]),
      el('div', { 'class': 'sc-field sc-field--group ss-compare__ab-field' }, [el('span', { 'class': 'sc-field__label', id: 'compare-ab-label', text: 'chart' }), abTabs])
    ]);
    wrap.appendChild(tools);
    const height = narrow() ? 280 : 340;
    // the phone shows one chart at a time, so both identities ride above it
    const both = el('div', { 'class': 'ss-compare__both', 'data-active': 'a' }, [compareId(a, 'a'), compareId(b, 'b')]);
    wrap.appendChild(both);
    const panels = el('div', { 'class': 'ss-compare__panels', 'data-active': 'a' });
    panels.appendChild(compareSide(a, 'a', 'cmp-a', height));
    panels.appendChild(compareSide(b, 'b', 'cmp-b', height));
    wrap.appendChild(panels);
    wrap.appendChild(el('div', { 'class': 'sc-table-scroll ss-compare__facts' }, compareTable(a, b)));
    wrap.appendChild(el('p', { 'class': 'sc-hint', text: 'Every value is the published record’s own, for ' + dateWords(run.session) + '. A marked row is one the two records differ on — it is not a verdict, and nothing here says which setup is better. Each chart keeps its own price scale and its own dates; the two are never drawn on one axis.' }));
    dlg.appendChild(wrap);
    function sync() {
      modeTabs.querySelectorAll('.sc-tab').forEach((t) => t.setAttribute('aria-pressed', t.getAttribute('data-mode') === prefs.mode ? 'true' : 'false'));
      rangeTabs.querySelectorAll('.sc-tab').forEach((t) => t.setAttribute('aria-pressed', t.getAttribute('data-range') === prefs.range ? 'true' : 'false'));
    }
    CHART_MODES.forEach((m) => {
      const t = el('button', { 'class': 'sc-tab', type: 'button', 'data-mode': m, 'aria-pressed': m === prefs.mode ? 'true' : 'false', text: MODE_WORDS[m] });
      t.addEventListener('click', () => { prefs.mode = m; savePrefs(); comparePanels.forEach((p) => p.applyPrefs()); sync(); });
      modeTabs.appendChild(t);
    });
    CHART_RANGES.forEach((r) => {
      const t = el('button', { 'class': 'sc-tab', type: 'button', 'data-range': r, 'aria-pressed': r === prefs.range ? 'true' : 'false', 'aria-label': RANGE_WORDS[r], title: RANGE_WORDS[r], text: r === 'setup' ? 'setup' : r });
      t.addEventListener('click', () => { prefs.range = r; savePrefs(); comparePanels.forEach((p) => p.applyPrefs()); sync(); });
      rangeTabs.appendChild(t);
    });
    // the phone shows one chart at a time; both symbols and both statuses stay
    [['a', a.ticker], ['b', b.ticker]].forEach((pair) => {
      const t = el('button', { 'class': 'sc-tab sc-tab--case', type: 'button', 'data-ab': pair[0], 'aria-pressed': pair[0] === 'a' ? 'true' : 'false', text: pair[1] });
      t.addEventListener('click', () => {
        panels.setAttribute('data-active', pair[0]);
        both.setAttribute('data-active', pair[0]);
        abTabs.querySelectorAll('.sc-tab').forEach((x) => x.setAttribute('aria-pressed', x.getAttribute('data-ab') === pair[0] ? 'true' : 'false'));
        comparePanels.forEach((p) => p.applyPrefs());   // a chart revealed at zero width re-measures
      });
      abTabs.appendChild(t);
    });
    sync();
    return close;
  }
  function openCompare() {
    const ids = pinned();
    const dlg = $('compare');
    if (!dlg || ids.length !== PIN_MAX) return;
    const a = model.byId[ids[0]], b = model.byId[ids[1]];
    compareReturn = { focus: d.activeElement, scroll: w.pageYOffset || w.scrollY || 0, mode: prefs.mode, range: prefs.range };
    const close = buildCompare(dlg, a, b);
    dlg.returnValue = '';
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', '');
    close.focus();
  }
  function closeCompare() {
    const dlg = $('compare');
    if (!dlg) return;
    if (dlg.open && dlg.close) dlg.close('closed'); else dlg.removeAttribute('open');
  }
  // one teardown, whichever way the sheet was dismissed (button, Escape, backdrop)
  function afterCompareClose() {
    const dlg = $('compare'), back = compareReturn;
    disposeCompare();
    clear(dlg);
    compareReturn = null;
    if (!back) return;
    // the reader's earlier place: the same stock, the same lens, the same
    // scroll, the same focus -- and a mode or range changed in the sheet
    // applied to the detail's chart, because that choice is theirs everywhere
    if (model && state.view === 'explore' && (back.mode !== prefs.mode || back.range !== prefs.range)) { state.detailKey = null; renderDetail(); }
    if (back.focus && back.focus.isConnected && back.focus.focus) back.focus.focus({ preventScroll: true });
    w.scrollTo(0, back.scroll);
  }

  // ---------------------------------------------------------------- discovery: Cards | Map (Bursts only)
  // The map is an overview of the stage's bursts by the recorded session's
  // gain and volume ratio, on the page's one selection state; the cards and
  // the map are two views of the same list, and the choice is a preference
  // kept in this browser. Setting up is never mapped: its names have not burst.
  const DISCOVER_KEY = 'spicystock:discover:v1';
  let discover = 'cards', mapView = null, mapKey = null;
  function loadDiscover() { try { const v = w.localStorage && w.localStorage.getItem(DISCOVER_KEY); if (v === 'map' || v === 'cards') discover = v; } catch (e) { /* the default stands */ } }
  function saveDiscover() { try { w.localStorage.setItem(DISCOVER_KEY, discover); } catch (e) { /* not remembered */ } }
  function mapPoints() {
    // the same list the cards draw, in the same order: the map is the cards'
    // twin and can never plot a population the cards do not show
    return visible('bursts').map((c) => ({
      id: c.id, ticker: c.ticker, gain: isNum(c.row.gain_pct) ? c.row.gain_pct : null, volume: volumeRatio(c.row).value,
      grade: c.grade, score: c.score, rank: c.rank, statusWords: statusWords(c.status)[0], statusTone: statusWords(c.status)[1],
      source: c.row.claude && c.row.claude.source === 'claude' ? 'claude' : (c.row.quality && c.row.quality.checks ? 'checklist' : null),
      chartSeen: c.row.claude ? c.row.claude.chart_seen : null
    }));
  }
  function unmountMap() {
    if (mapView) { mapView.dispose(); mapView = null; }
    mapKey = null;
    const host = $('burst-map'); if (host) host.parentNode.removeChild(host);
  }
  function mountMap() {
    const ws = $('workspace'), run = current.run || {};
    let host = $('burst-map');
    // the map is redrawn whenever the visible set changes, and only then:
    // a cached map over a stale lens is the cards and the map disagreeing
    const key = picksKey();
    if (host && mapView && mapKey === key) { mapView.update(state.selected.bursts); return; }
    unmountMap();
    host = el('div', { id: 'burst-map' });
    const picks = $('picks'), head = picks ? picks.querySelector('.ss-picks__head') : null;
    if (head) picks.insertBefore(host, head.nextSibling); else ws.insertBefore(host, ws.firstChild);
    const lens = lensOf('bursts'), total = model.stages.bursts.length;
    mapView = SCStock.map.render(host, { points: mapPoints(), selectedId: state.selected.bursts, sessionWords: dateWords(run.session), demo: demo,
      subset: lens === 'all' && !state.query ? null : { total: total, words: LENS_WORDS[lens] + ' lens' + (state.query ? ' · ‘' + state.query + '’' : '') },
      onSelect: (id) => { state.gesture = true; navigate(routeHash('bursts', id)); },
      // the map's Compare toggle is the cards' own button, placed there: two
      // candidates can be pinned from the map the reader is already reading
      // without a detour through the cards to find them again
      control: (p, where) => { const c = model.byId[p.id]; return c ? pinButton(c, where) : null; } });
    mapKey = key;
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
  // The button freezes the setup's own snapshot with its suggested whole-share
  // quantity AND the evidence the record carried for that signal -- the bars
  // up to the signal session and the dated anchors drawn on them -- so the
  // setup stays readable long after its record is gone. One optional
  // reference size is the reader's and changes nothing else. Every record
  // loaded afterwards contributes at most one observation per market date;
  // the original is never rewritten, and no sentence here says bought,
  // filled, held, sold or stopped out.
  function followEvidenceOf(c, record) {
    record = record || current;
    const run = record.run || {}, app = record.app || {}, sig = text(c.signalSession) || text(run.session);
    // only bars at or before the signal's own session: what was on the screen
    // that night, never a candle that printed after it
    const series = (c.series || []).filter((b) => b && text(b.date) && (!sig || b.date <= sig));
    if (!series.length) return null;
    return {
      series: series.slice(-SCStock.follow.EVIDENCE_BARS),
      anchors: evidenceItems(c).map((it) => ({ key: it.key, label: it.label, from: it.from, to: it.to, low: it.low, high: it.high, lede: it.lede, measured: it.measured })),
      from: { session: text(run.session), rules_version: text(app.rules_version) }
    };
  }
  function followSetupOf(c, record) {
    record = record || current;
    const run = record.run || {}, app = record.app || {}, plan = c.plan || {}, t = plan.targets || {}, b = c.row;
    const burst = c.stage === 'bursts';
    const hasTicket = c.status === 'ticket' && isNum(plan.shares) && plan.shares > 0;
    return {
      ticker: c.ticker, kind: burst ? 'burst' : 'anticipation', stage: c.stage, session: run.session || '', rules_version: app.rules_version || '',
      suggested_shares: hasTicket ? plan.shares : null,
      evidence: followEvidenceOf(c, record),
      provenance: record.provenance || { session: run.session, published_at: run.published_at, run_id: run.run_id, rules_version: app.rules_version },
      snapshot: {
        name: c.name || '', close: isNum(b.close) ? b.close : null, close_date: run.session || '', grade: c.grade || null, score: isNum(c.score) ? c.score : null,
        status: c.status, status_words: statusWords(c.status)[0], scan: b.scan || null, reader_reason: text((b.claude || {}).reason),
        levels: { entry_low: burst ? plan.entry_low : plan.trigger, entry_high: burst ? plan.entry_high : plan.limit, trigger: burst ? plan.entry_ref : plan.trigger,
          limit: burst ? plan.entry_high : plan.limit, day2_spent_above: burst && isNum(plan.day2_spent_above) ? plan.day2_spent_above : null,
          stop: plan.stop, stop_basis: plan.stop_basis || null,
          target_low: t.low, target_high: t.high, target_low_pct: t.low_pct, target_high_pct: t.high_pct },
        order_line: text(plan.order_line), instruction: entryInstruction(plan), summary: burst ? sentence(firstSentence(text(b.summary).replace(/^[A-Z0-9.\-]+:\s*/, ''))) : pickReason(c),
        withheld_reason: c.status !== 'ticket' ? text(c.reason) : '',
        limitations: savedLimitations(c)
      }
    };
  }
  // what the record itself said this setup could NOT show, frozen with it: a
  // grade the checklist alone gave, a chart the reader never saw, a veto
  function savedLimitations(c) {
    const out = [], b = c.row || {}, cl = b.claude || {}, q = b.quality || {};
    if (c.stage === 'bursts') {
      if (cl.source !== 'claude') out.push('graded by the checklist alone; the chart reader did not answer for this name');
      else if (cl.chart_seen === false) out.push('the chart reader answered without a chart');
      (q.vetoes || []).forEach((v) => out.push('veto: ' + (VETO_WORDS[v] || words(v))));
    } else out.push('anticipation names are measured, not graded: the record carries no pass or fail for a coil');
    if (!(c.series || []).length) out.push('no daily bars were archived for it, so no chart was saved');
    return out;
  }

  // ------------------------------------------------- what the loaded record can say about a saved symbol
  // Every dated bar the record carries for one ticker, in increasing order of
  // how much of the bar it holds, so the fullest source wins its date. Nothing
  // is fetched and nothing is derived: each entry is a number the run wrote.
  function recordBarsFor(ticker) {
    const run = current.run || {}, session = text(run.session), out = {};
    const put = (date, o, h, l, c, v, source, origin) => {
      if (!text(date) || !isNum(c)) return;
      out[date] = { date: date, o: isNum(o) ? o : null, h: isNum(h) ? h : null, l: isNum(l) ? l : null, c: c, v: isNum(v) ? v : null, source: source, from_session: origin || session };
    };
    const p = (current.open_plans || []).find((x) => x && x.ticker === ticker);
    if (p) put(text(p.last_date), null, null, null, p.last_close, null, 'the open model plan');
    const wl = current.watchlist || {}, r = (wl.top || []).concat(wl.also_quiet || []).find((x) => x && x.ticker === ticker);
    if (r) put(session, null, null, null, r.close, null, 'the record’s watchlist row');
    const b = (current.bursts || []).find((x) => x && x.ticker === ticker);
    if (b) put(session, b.open, b.high, b.low, b.close, b.volume, 'the record’s burst row');
    const ob = ((current.observations || {}).symbols || {})[ticker];
    if (ob) {
      (ob.history || []).forEach(b => put(text(b.date), b.o, b.h, b.l, b.c, b.v, 'public observation history', b.from_session));
      if (!(ob.history || []).length) put(text(ob.date), ob.o, ob.h, ob.l, ob.c, ob.v, 'the record’s observation block', ob.date < session ? ob.date : session);
    }
    STAGES.forEach((s) => {
      const cand = model ? model.byId[s + ':' + ticker] : null;
      (cand ? cand.series : []).forEach((x) => put(text(x.date), x.o, x.h, x.l, x.c, x.v, 'the record’s archived bars'));
    });
    return Object.keys(out).sort().map((k) => out[k]);
  }
  // Are the record's prices on the same footing as the ones this setup was
  // saved under? The bars are asked, not assumed: a session BOTH already hold
  // answers it. Same close, same basis. A different close on a session
  // EARLIER than the one being published means every earlier bar has been
  // re-priced since (a split does exactly that), and no comparison across it
  // would be honest. Nothing in common, and the answer is that we do not know.
  const BASIS_CENTS = 0.005;
  function basisOf(item, bars, session) {
    const known = {}, snap = item.snapshot || {};
    ((item.evidence || {}).series || []).forEach((b) => { known[b.date] = b.c; });
    (item.observations || []).forEach((o) => { known[o.date] = o.c; });
    if (text(snap.close_date) && isNum(snap.close)) known[snap.close_date] = snap.close;
    let seen = false;
    for (let i = 0; i < bars.length; i++) {
      const b = bars[i];
      if (!(b.date in known)) continue;
      if (Math.abs(known[b.date] - b.c) > BASIS_CENTS) { if (b.date < session) return 'adjusted'; }
      else seen = true;
    }
    return seen ? 'match' : 'unknown';
  }
  // A setup saved before this page saved charts can have its ORIGINAL chart
  // back -- but only from a record that IS that signal. `currentSetupFor().same`
  // compares the whole identity (kind, symbol, session and rules), so a newer
  // signal for the same ticker can never supply one, and an original already
  // saved is never replaced.
  async function recoverEvidence() {
    if (!model) return 0;
    let items = [];
    try { items = SCStock.follow.list(); } catch (e) { return 0; }
    let n = 0;
    for (const it of items) {
      if (it.evidence) continue;
      const cur = currentSetupFor(it);
      if (!cur || !cur.same) continue;
      const ev = followEvidenceOf(cur.candidate);
      if (ev && (await SCStock.follow.commit('attachEvidence', it.id, ev)).attached) n++;
    }
    if (n) invalidateFollow();
    return n;
  }
  // One pass per loaded record, over the whole shelf: a merge that changes
  // nothing writes nothing, which is what makes a re-render, a reload and a
  // theme change cost no observation.
  async function recordObservations() {
    const run = current.run || {}, app = current.app || {}, session = text(run.session);
    if (!session) return null;
    let items = [];
    try { items = SCStock.follow.list(); } catch (e) { return null; }
    const updates = [];
    items.forEach((it) => {
      const bars = recordBarsFor(it.ticker);
      if (bars.length) updates.push({ id: it.id, bars: bars, from_session: session, from_rules: text(app.rules_version), basis: basisOf(it, bars, session) });
    });
    if (!updates.length) return null;
    const res = await SCStock.follow.commit('observe', updates);
    if (res && res.changed) invalidateFollow();
    return res;
  }

  // ------------------------------------------------- reading one saved setup
  // What is known about whether the two records priced this symbol the same
  // way, said in full where there is room (the saved detail) and in a few
  // words where there is not (the card), so neither place invents certainty.
  const BASIS_WORDS = {
    match: '',
    unknown: 'No session is recorded in both, so nothing confirms the two were priced the same way.',
    adjusted: 'A session recorded for this symbol now prints a different close, so the archive has been re-priced since the signal; the two prices are not comparable and no change is shown.'
  };
  const BASIS_SHORT = { match: '', unknown: 'basis not confirmed', adjusted: 'prices re-adjusted since; no change shown' };
  // Where the newest observation stands against the record ON SCREEN: it came
  // from it, from a record NEWER than it (the page is showing an older one
  // than this browser has already read), or from an earlier one and nothing
  // since. The reader is told which, because "latest" alone would be a claim
  // about the market rather than about what has been loaded here.
  const STAND_WORDS = { current: ['tonight’s record', 'neutral'], ahead: ['newer than this record', 'warn'],
    older: ['older than tonight', 'warn'], unknown: ['no record loaded', 'neutral'] };
  function observationState(item) {
    const snap = item.snapshot || {}, run = current.run || {}, session = text(run.session);
    const obs = item.observations || [], latest = obs.length ? obs[obs.length - 1] : null;
    const base = isNum(snap.close) && snap.close > 0 ? snap.close : null;
    const out = { latest: latest, count: obs.length, base: base, baseDate: text(snap.close_date) || item.session,
      stand: 'unknown', current: false, change: null, basis: latest ? latest.basis : null, limitation: '', coverage: '', brief: '' };
    if (!latest) {
      out.coverage = 'No later session has been observed for ' + item.ticker + ' in any record this page has loaded'
        + (session ? ', tonight’s included' : '') + '; the setup is shown as it was saved.';
      return out;   // the one line above already says it; a second would repeat it
    }
    const from = text(latest.from_session) || latest.date;
    out.stand = !session ? 'unknown' : latest.date === session ? 'current' : latest.date > session ? 'ahead' : 'older';
    out.current = out.stand === 'current';
    if (latest.basis === 'adjusted') out.limitation = BASIS_WORDS.adjusted;
    else if (base) out.change = (latest.c / base - 1) * 100;
    if (latest.basis === 'unknown') out.limitation = BASIS_WORDS.unknown;
    let short = '';
    if (out.stand === 'older') {
      out.coverage = 'Nothing newer: tonight’s record (' + dateWords(session) + ') carries no session for ' + item.ticker + ' after this one.';
      short = 'nothing newer in tonight’s record';
    } else if (out.stand === 'ahead') {
      out.coverage = 'This close came from the ' + dateWords(from) + ' record, which is newer than the one on screen (' + dateWords(session) + '); the page is showing an older record than this browser has already read.';
      short = 'from the ' + dateShort(from) + ' record; this page shows ' + dateShort(session);
    } else if (out.stand === 'unknown') {
      out.coverage = 'No record is loaded, so this is the newest observation this browser holds.';
      short = 'no record loaded';
    }
    // the card's one line: the caveat that must never be dropped, then what
    // is limited about this reading -- never the three paragraphs the saved
    // detail has room for
    out.brief = ['recorded closes, not your result', short, BASIS_SHORT[out.basis] || ''].filter(Boolean).join(' · ');
    return out;
  }
  // The open model plan the record keeps for THIS signal. A ticker alone is
  // not a signal: the plan must be for the same session and the same family,
  // and it must have been written under the rules this setup was saved under.
  // Anything else is named as another signal's and shown apart, never folded
  // into the saved plan.
  function modelUpdateOf(item) {
    const app = current.app || {};
    const same = (current.open_plans || []).filter((o) => o && o.ticker === item.ticker);
    if (!same.length) return { plan: null, matched: false, why: '' };
    const exact = same.find((o) => text(o.picked) === item.session && text(o.kind) === item.kind);
    if (!exact) {
      const other = same[0];
      return { plan: null, matched: false, other: other,
        why: 'The record keeps an open model plan for ' + item.ticker + ', but it was picked ' + dateWords(text(other.picked)) + ' — a different signal from this one, so it is not this setup’s.' };
    }
    if (text(app.rules_version) && text(item.rules_version) && app.rules_version !== item.rules_version) {
      return { plan: null, matched: false, other: exact,
        why: 'The record’s model plan for this signal was written under different rules (' + app.rules_version.slice(0, 8) + ' against the saved ' + item.rules_version.slice(0, 8) + '), so it is shown apart from the saved plan rather than as an update to it.' };
    }
    return { plan: exact, matched: true, why: '' };
  }
  // is this symbol in the loaded record at all, and is it THIS signal?
  function currentSetupFor(item) {
    if (!model) return null;
    const c = model.byId[item.stage + ':' + item.ticker] || STAGES.map((s) => model.byId[s + ':' + item.ticker]).filter(Boolean)[0] || null;
    if (!c) return null;
    const run = current.run || {}, app = current.app || {};
    const id = SCStock.follow.identity({ kind: c.stage === 'bursts' ? 'burst' : 'anticipation', ticker: c.ticker,
      session: text(run.session), rules_version: text(app.rules_version) });
    const samePublication = !(item.provenance || {}).published_at || item.provenance.published_at === run.published_at;
    return { candidate: c, same: (id === item.id || item.id.startsWith(id + ':')) && samePublication, movedStage: c.stage !== item.stage };
  }
  // the archived status, said as the record's and dated, so it can never be
  // read as a ticket available now
  const archivedWords = (item) => (text((item.snapshot || {}).status_words) || 'no ticket') + ' · ' + dateShort(item.session) + ' record';
  let followStatus = null;
  // A count of prices, not of alerts. It says what the number is counted
  // against -- tonight's session -- because "3 updates" beside a stock list
  // would read as three new trades, which is the one thing it is not.
  function updatesSummary(items) {
    const session = text((current.run || {}).session);
    let fresh = 0, older = 0, ahead = 0, none = 0;
    items.forEach((it) => {
      const o = observationState(it);
      if (!o.latest) none++; else if (o.stand === 'current') fresh++; else if (o.stand === 'ahead') ahead++; else older++;
    });
    if (!items.length) return '';
    const parts = [];
    if (fresh) parts.push(fresh + (session ? ' with a close from ' + dateShort(session) : ' current'));
    if (ahead) parts.push(ahead + ' from a newer record');
    if (older) parts.push(older + ' older');
    if (none) parts.push(none + ' not seen since the signal');
    return parts.join(' · ');
  }
  function followJump() {
    const link = $('following-jump'), box = $('following-jump-box'), sum = $('following-updates');
    if (!link) return;
    let items = [];
    try { items = SCStock.follow.list(); } catch (e) { items = []; }
    link.textContent = 'My setups · ' + items.length;
    link.hidden = false;
    if (box) box.hidden = false;
    if (sum) {
      const words = updatesSummary(items);
      sum.textContent = words ? 'Latest: ' + words : '';
      sum.hidden = !words;
      sum.title = words ? 'Observed closes, counted against tonight’s record. Not alerts, not new trades and not buy signals.' : '';
    }
  }
  function setupForSave(c) {
    const setup = followSetupOf(c), existing = SCStock.follow.find(SCStock.follow.identity(setup));
    const pub = setup.provenance && setup.provenance.published_at;
    if (existing && pub && (existing.provenance || {}).published_at && existing.provenance.published_at !== pub) setup.revision_id = 'publication-' + pub;
    return setup;
  }
  function saveButton(c) {
    const setup = setupForSave(c), id = SCStock.follow.identity(setup), saved = SCStock.follow.find(id);
    const b = el('button', { type: 'button', 'class': 'sc-btn sc-btn--secondary sc-btn--sm', 'data-save-setup': c.ticker, text: saved ? 'Saved · open' : 'Save setup' });
    b.addEventListener('click', async () => {
      if (SCStock.follow.find(id)) { navigate(savedHash(id)); return; }
      b.disabled = true;
      const result = await SCStock.follow.commit('add', setup);
      b.disabled = false;
      if (!result.ok) { b.insertAdjacentElement('afterend', el('p', { role: 'alert', text: result.error })); return; }
      afterFollowChange(); renderDetailFollow();
      if (result.evidenceDropped) setFollowStatus('Setup saved, but its chart did not fit in browser storage. Original chart was not saved.');
      const replacement = [...d.querySelectorAll('[data-save-setup]')].find(x => x.dataset.saveSetup === c.ticker);
      if (replacement) replacement.focus();
    });
    return b;
  }
  const annotationDrafts = new Map();
  function amountText(amount) {
    const cents = amount && amount.currency === 'USD' && Number.isSafeInteger(amount.minor_units) ? amount.minor_units : null;
    return cents === null ? '' : String(Math.floor(cents / 100)) + '.' + String(cents % 100).padStart(2, '0');
  }
  function annotationForm(item) {
    const a = item.annotation || {}, form = el('form', { 'class': 'ss-annotation', novalidate: '' });
    const taken = el('input', { type: 'checkbox', id: 'setup-taken', checked: a.taken ? '' : null });
    const amount = el('input', { id: 'setup-amount', 'class': 'sc-input', type: 'text', inputmode: 'decimal', autocomplete: 'off', placeholder: 'Optional', value: annotationDrafts.has(item.id) ? annotationDrafts.get(item.id) : amountText(a.reference_amount) });
    const message = el('p', { 'class': 'sc-hint', role: 'status', 'data-annotation-status': '', text: annotationDrafts.has(item.id) ? 'Unsaved amount: save to keep this edit.' : '' });
    const submit = el('button', { type: 'submit', 'class': 'sc-btn sc-btn--secondary sc-btn--sm', text: 'Save amount' });
    const clearAmount = el('button', { type: 'button', 'class': 'sc-btn sc-btn--ghost sc-btn--sm', text: 'Clear amount' });
    form.appendChild(el('label', { 'class': 'ss-annotation__taken', for: 'setup-taken' }, [taken, ' I took this setup']));
    form.appendChild(el('label', { for: 'setup-amount', text: 'Reference amount (USD)' }));
    form.appendChild(el('div', { 'class': 'ss-annotation__amount' }, [amount, submit, clearAmount]));
    form.appendChild(el('p', { 'class': 'sc-hint', text: 'Optional, browser-local notes. A marking time is not a purchase date. Unmarked means unmarked. Amounts do not imply shares, fills or personal P&L.' }));
    form.appendChild(message);
    if (a.taken_marked_at) form.appendChild(el('p', { 'class': 'sc-hint', text: 'Indication marked at ' + a.taken_marked_at + ' (not a purchase date).' }));
    amount.addEventListener('input', () => annotationDrafts.set(item.id, amount.value));
    taken.addEventListener('change', async () => {
      const want = taken.checked;
      const res = await SCStock.follow.commit('setAnnotation', item.id, 'taken', want);
      message.textContent = res.ok ? 'Indication saved in this browser.' : res.error;
      if (!res.ok) taken.checked = !want;
      afterFollowChange();
    });
    const save = async () => {
      const draft = amount.value.trim(); annotationDrafts.set(item.id, draft);
      submit.disabled = true;
      const res = await SCStock.follow.commit('setAnnotation', item.id, 'amount', draft);
      submit.disabled = false;
      message.textContent = res.ok ? (draft ? 'Reference amount saved in this browser.' : 'Amount cleared; reference amount is unknown.') : res.error;
      if (!res.ok) recoveryDownload(form);
      if (res.ok) { annotationDrafts.delete(item.id); afterFollowChange(); }
    };
    form.addEventListener('submit', e => { e.preventDefault(); save(); });
    clearAmount.addEventListener('click', () => { amount.value = ''; save(); });
    return form;
  }

  // Public recovery is loaded only on request. No annotation, amount, saved
  // identity, or private selection is sent: index search happens in memory.
  let recoveryIndex = null, recoveryRequest = 0, recoveryPanel = null;
  async function publicJSON(path, digest) {
    if (!/^(?:index\.json|[a-f0-9]{40}\/(?:record|(?:burst|anticipation)-[A-Z0-9][A-Z0-9.-]{0,15})\.json)$/.test(path)) throw new Error('Invalid archive path.');
    const response = await fetch('history/' + path, { credentials: 'omit', referrerPolicy: 'no-referrer' });
    if (!response.ok) throw new Error('This original is unavailable in the retained public archive.');
    const bytes = await response.arrayBuffer();
    if (bytes.byteLength > (path === 'index.json' ? 8 * 1024 * 1024 : 256 * 1024)) throw new Error('Archive exceeds the supported bound.');
    if (digest) {
      const actual = [...new Uint8Array(await w.crypto.subtle.digest('SHA-256', bytes))].map(x => x.toString(16).padStart(2, '0')).join('');
      if (actual !== digest) throw new Error('Archived source failed its integrity check. Nothing was saved.');
    }
    return JSON.parse(new TextDecoder().decode(bytes));
  }
  async function findEarlier(event) {
    event.preventDefault();
    const request = ++recoveryRequest, ticker = $('history-ticker').value.trim().toUpperCase();
    const status = $('history-status'), host = clear($('history-results'));
    if (recoveryPanel) { recoveryPanel.dispose(); recoveryPanel = null; }
    if (!/^[A-Z0-9][A-Z0-9.-]{0,15}$/.test(ticker)) { status.textContent = 'Enter a ticker such as ATEC or VICR.'; return; }
    status.textContent = 'Reading the public archive…';
    try {
      if (!recoveryIndex) recoveryIndex = await publicJSON('index.json');
      const index = recoveryIndex;
      if (index.version !== 1 || !Array.isArray(index.entries) || !Array.isArray(index.dates) || !index.records) throw new Error('This public archive version is unavailable.');
      if (request !== recoveryRequest) return;
      status.textContent = 'Available signal dates: ' + index.dates.join(', ') + '. Public window: ' + index.days + ' calendar days through ' + index.as_of + '. Local saves do not expire.';
      const cutoff = new Date(nowAt()); cutoff.setUTCDate(cutoff.getUTCDate() - index.days);
      const hits = index.entries.filter(e => e.ticker === ticker && index.records[e.source] && index.records[e.source].session >= cutoff.toISOString().slice(0, 10));
      if (!hits.length) { host.appendChild(el('p', { text: 'No retained published original found for ' + ticker + '. It may be unavailable or outside the public window; no recommendation was reconstructed.' })); return; }
      hits.forEach(entry => {
        const source = index.records[entry.source];
        const card = el('article', { 'class': 'ss-history__result', 'data-history-source': entry.source });
        card.appendChild(el('h3', { text: ticker + ' · ' + source.session + ' · ' + entry.kind }));
        card.appendChild(el('p', { 'class': 'sc-hint', text: 'Published grade: ' + (entry.grade || 'not graded') + (entry.scan ? ' · scan ' + entry.scan : '') + ' · ' + (entry.chart ? 'original chart available' : 'Original chart unavailable in this archived record') }));
        card.appendChild(el('p', { 'class': 'sc-hint ss-history__source', text: 'Published ' + source.published_at + ' · source ' + entry.source }));
        const inspect = el('button', { type: 'button', 'class': 'sc-btn sc-btn--secondary sc-btn--sm', text: 'Inspect original', 'data-history-inspect': entry.source });
        inspect.addEventListener('click', async () => {
          inspect.disabled = true;
          try {
            const [context, evidence] = await Promise.all([publicJSON(entry.source + '/record.json', source.context_sha256), publicJSON(entry.path, entry.sha256)]);
            if (request !== recoveryRequest) return;
            if (evidence.source !== entry.source || evidence.row.ticker !== ticker || evidence.kind !== entry.kind || context.run.session !== source.session || context.app.rules_version !== source.rules_version) throw new Error('Archive identity does not match the selected original.');
            const record = Object.assign({}, context, { bursts: evidence.kind === 'burst' ? [evidence.row] : [], watchlist: { top: evidence.kind === 'anticipation' && !evidence.quiet ? [evidence.row] : [], also_quiet: evidence.kind === 'anticipation' && evidence.quiet ? [evidence.row] : [] } });
            const c = buildModel(record).byId[(entry.kind === 'burst' ? 'bursts:' : 'setting-up:') + ticker];
            c.signalSession = source.session;
            const setup = followSetupOf(c, record);
            setup.provenance = source;
            if (setup.evidence) setup.evidence.recovered = true;
            const previous = SCStock.follow.find(SCStock.follow.identity(setup));
            if (previous && ((previous.provenance || {}).record_id !== source.record_id) && ((previous.provenance || {}).published_at !== source.published_at)) setup.revision_id = source.record_id;
            const preview = el('div', { 'class': 'ss-history__preview' });
            preview.appendChild(el('p', { text: 'Original status: ' + statusWords(c.status)[0] + '. ' + c.reason + '. Signal close ' + usd(c.row.close) + ' on ' + source.session + '. Historical research only.' }));
            preview.appendChild(el('p', { text: setup.snapshot.summary }));
            if (setup.snapshot.reader_reason) preview.appendChild(el('p', { 'class': 'sc-hint', text: 'Original chart reader: ' + setup.snapshot.reader_reason }));
            if (recoveryPanel) recoveryPanel.dispose();
            if (c.series.length) { recoveryPanel = chartPanel(c, { idPrefix: 'recovery', height: 280 }); preview.appendChild(recoveryPanel.node); }
            else preview.appendChild(el('p', { text: 'Original chart unavailable in this archived record. No later chart is substituted.' }));
            const save = el('button', { type: 'button', 'class': 'sc-btn sc-btn--secondary', text: 'Save this original', 'data-history-save': ticker });
            save.addEventListener('click', async () => {
              const result = await SCStock.follow.commit('add', setup);
              if (!result.ok) { status.textContent = result.error; return; }
              await recordObservations(); afterFollowChange();
              if (result.evidenceDropped) status.textContent = 'Setup saved, but chart evidence did not fit; the chart was not saved.';
              navigate(savedHash(result.item.id));
            });
            preview.appendChild(save); card.querySelector('.ss-history__preview')?.remove(); card.appendChild(preview); save.focus();
          } catch (error) { status.textContent = error.message; } finally { inspect.disabled = false; }
        });
        card.appendChild(inspect); host.appendChild(card);
      });
    } catch (error) { status.textContent = error.message; }
  }
  $('history-search').addEventListener('submit', findEarlier);

  function followBlock(c) {
    const setup = setupForSave(c), id = SCStock.follow.identity(setup), st0 = SCStock.follow.status();
    const item = SCStock.follow.find(id);
    const box = el('div', { 'class': 'sc-actionbar__more ss-follow', 'data-follow': item ? 'following' : 'not-following', 'data-follow-id': id });
    const redraw = () => { const next = followBlock(c); box.parentNode.replaceChild(next, box); return next; };
    const warn = (msg) => { box.querySelectorAll('.ss-follow__warn').forEach((x) => x.remove()); box.appendChild(el('p', { 'class': 'ss-follow__warn', role: 'alert', text: msg })); recoveryDownload(box); };
    if (!st0.available) {
      box.appendChild(chip('not saved', 'neutral'));
      warn(st0.error || 'Storage is blocked in this browser; nothing can be followed here.');
      return box;
    }
    if (!item) {
      const btn = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', text: 'Save setup', 'data-follow-action': 'add' });
      btn.addEventListener('click', async () => {
        const res = await SCStock.follow.commit('add', setup);
        if (!res.ok) { warn(res.error); return; }
        const next = redraw(); afterFollowChange();
        if (res.evidenceDropped) { next.appendChild(el('p', { role: 'alert', text: 'Setup saved, but chart evidence did not fit. Original chart was not saved.' })); }
        const focus = next.querySelector('a,button'); if (focus) focus.focus();
      });
      box.appendChild(btn);
      box.appendChild(el('p', { 'class': 'ss-follow__hint', text: setup.suggested_shares ? plural(setup.suggested_shares, 'share') + ' suggested by the plan · saved in this browser only' : (c.status === 'ticket' ? 'for observation, no size suggested' : 'for observation, ' + statusWords(c.status)[0] + ' · saved in this browser only') }));
      return box;
    }
    box.appendChild(chip('saved', 'good'));
    if (item.evidence_dropped) box.appendChild(el('p', { role: 'alert', text: 'Setup saved without chart evidence: browser storage was full.' }));
    const size = isNum(item.reference_shares) ? 'your reference size ' + plural(item.reference_shares, 'share') + (isNum(item.suggested_shares) ? ' (plan suggested ' + item.suggested_shares + ')' : '') : (isNum(item.suggested_shares) ? plural(item.suggested_shares, 'share') + ' suggested by the plan' : 'for observation, no size');
    box.appendChild(el('p', { 'class': 'ss-follow__hint', text: size + ' · saved in this browser, not a broker fill' }));
    const edit = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', text: 'Edit size', 'data-follow-action': 'edit' });
    const undo = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', text: 'Remove', 'data-follow-action': 'remove' });
    const link = el('a', { 'class': 'sc-link--quiet', href: '#following', text: 'Open My setups' });
    edit.addEventListener('click', () => {
      const form = el('form', { 'class': 'ss-follow__form', novalidate: '' });
      const input = el('input', { 'class': 'sc-input', type: 'number', min: '1', max: String(SCStock.follow.SHARES_MAX), step: '1', inputmode: 'numeric', value: String(isNum(item.reference_shares) ? item.reference_shares : (item.suggested_shares || 1)), 'aria-label': 'Your reference size in whole shares' });
      const save = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'submit', text: 'Save size' });
      const cancel = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', text: 'Cancel' });
      const clearBtn = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', text: 'Use the suggested size', hidden: isNum(item.reference_shares) ? null : '' });
      form.appendChild(input); form.appendChild(save); form.appendChild(clearBtn); form.appendChild(cancel);
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const n = input.value.trim() === '' ? NaN : Number(input.value);
        const res = await SCStock.follow.commit('setShares', id, Number.isInteger(n) ? n : NaN);
        if (!res.ok) { warn(res.error); return; }
        redraw(); afterFollowChange();
      });
      clearBtn.addEventListener('click', async () => { const res = await SCStock.follow.commit('setShares', id, null); if (!res.ok) { warn(res.error); return; } redraw(); afterFollowChange(); });
      cancel.addEventListener('click', () => { redraw(); });
      edit.replaceWith(form); input.focus();
    });
    undo.addEventListener('click', async () => { const res = await SCStock.follow.commit('remove', id); if (!res.ok) { warn(res.error); return; } redraw(); afterFollowChange(); });
    box.appendChild(edit); box.appendChild(undo); box.appendChild(link);
    const open = el('button', { type: 'button', 'class': 'sc-btn sc-btn--secondary sc-btn--sm', text: 'Open saved setup' });
    open.addEventListener('click', () => { closeCompare(); navigate(savedHash(id)); }); box.appendChild(open);
    return box;
  }
  // business days between two dates: the trail's own x axis, so a gap in the
  // dots is a session nothing was observed for and adjacent dots are adjacent
  // sessions. A market holiday reads as a gap, which overstates what is
  // missing rather than hiding it.
  function bdaysBetween(from, to) {
    const a = parseISO(from), b = parseISO(to);
    if (!a || !b || b < a) return 0;
    let n = 0;
    const cur = new Date(a.getTime());
    while (cur < b) { cur.setUTCDate(cur.getUTCDate() + 1); if (isWeekday(cur)) n++; }
    return n;
  }
  const TRAIL_W = 240, TRAIL_H = 46;
  // The observed closes as dots at their own dates, with the signal close as
  // the baseline. Dots are NEVER joined: a line between two observations would
  // claim the sessions between them, which this page has not seen. One
  // observation draws one dot and says its value.
  function observedTrail(item, o) {
    const obs = item.observations || [];
    if (!obs.length || !isNum(o.base)) return null;
    const first = o.baseDate, last = obs[obs.length - 1].date;
    const span = Math.max(1, bdaysBetween(first, last));
    const values = [o.base].concat(obs.map((x) => x.c));
    let lo = Math.min.apply(null, values), hi = Math.max.apply(null, values);
    const pad = (hi - lo) * 0.18 || Math.max(0.01, hi * 0.01);
    lo -= pad; hi += pad;
    const x = (date) => 10 + bdaysBetween(first, date) / span * (TRAIL_W - 20);
    const y = (v) => Math.round((TRAIL_H - 9 - (v - lo) / (hi - lo) * (TRAIL_H - 18)) * 10) / 10;
    const kids = [
      svg('line', { 'class': 'ss-trail__base', x1: 2, x2: TRAIL_W - 2, y1: y(o.base), y2: y(o.base) }),
      svg('circle', { 'class': 'ss-trail__signal', cx: x(first), cy: y(o.base), r: 3 })
    ];
    obs.forEach((p) => {
      const dir = p.c > o.base ? 'up' : p.c < o.base ? 'down' : 'flat';
      kids.push(svg('circle', { 'class': 'ss-trail__dot', 'data-dir': dir, 'data-date': p.date, cx: x(p.date), cy: y(p.c), r: 3.2 }));
    });
    // the spoken label carries the prices, because a screen reader cannot see
    // the dots; the caption explains the drawing, and never repeats the number
    // printed directly above it
    const spoken = obs.length === 1
      ? 'One observed close, ' + usd(obs[0].c) + ' on ' + dateWords(obs[0].date) + ', against the ' + usd(o.base) + ' signal close.'
      : plural(obs.length, 'observed close') + ' from ' + usd(obs[0].c) + ' on ' + dateWords(obs[0].date) + ' to ' + usd(obs[obs.length - 1].c) + ' on ' + dateWords(last) + ', against the ' + usd(o.base) + ' signal close.';
    const caption = obs.length === 1
      ? 'One observed close against the ' + usd(o.base) + ' signal close (dashed).'
      : plural(obs.length, 'observed close') + ', ' + dateShort(obs[0].date) + ' to ' + dateShort(last) + ', against the ' + usd(o.base) + ' signal close (dashed). Sessions with no observation are left empty and the dots are not joined.';
    return el('figure', { 'class': 'ss-trail', 'data-points': String(obs.length) }, [
      svg('svg', { viewBox: '0 0 ' + TRAIL_W + ' ' + TRAIL_H, 'class': 'ss-trail__svg', role: 'img', 'aria-label': spoken, focusable: 'false' }, kids),
      el('figcaption', { 'class': 'sc-hint', text: caption })
    ]);
  }
  function followedCard(item) {
    const snap = item.snapshot || {}, lv = snap.levels || {}, o = observationState(item);
    const card = el('article', { 'class': 'ss-followed', 'data-follow-id': item.id, 'data-ticker': item.ticker,
      'data-observed': o.latest ? o.stand : 'none' });
    const open = el('button', { 'class': 'ss-followed__ticker sc-case', type: 'button', text: item.ticker, 'data-open-followed': item.id });
    open.addEventListener('click', () => { state.gesture = true; navigate(savedHash(item.id)); });
    // what was followed, and when its signal was
    card.appendChild(el('div', { 'class': 'ss-followed__row' }, [open,
      el('span', { 'class': 'ss-followed__meta', text: (item.kind === 'anticipation' ? 'setting up' : 'burst') + ' · signal ' + dateWords(item.session) }),
      el('div', { 'class': 'ss-followed__chips' }, [snap.grade ? chip('original ' + snap.grade, 'brand') : null, chip(archivedWords(item), snap.status === 'ticket' ? 'good' : 'neutral', true), item.demo ? chip('demo', 'warn') : null])]));
    // group one: the original, frozen
    const at = el('div', { 'class': 'ss-followed__group', 'data-group': 'signal' }, [el('span', { 'class': 'sc-eyebrow', text: 'at the signal' })]);
    const levels = [];
    if (isNum(snap.close)) levels.push('close ' + usd(snap.close));
    if (isNum(lv.trigger)) levels.push('trigger ' + usd(lv.trigger));
    if (isNum(lv.limit)) levels.push('limit ' + usd(lv.limit));
    // four prices, four rules: the limit is the executable one and the day-2
    // line is the outer extension threshold, so a card that saved both says both
    if (isNum(lv.day2_spent_above) && lv.day2_spent_above !== lv.limit) levels.push('too extended over ' + usd(lv.day2_spent_above));
    if (isNum(lv.stop)) levels.push('stop ' + usd(lv.stop));
    at.appendChild(el('p', { 'class': 'ss-followed__levels', text: levels.length ? levels.join(' · ') : 'no plan levels were recorded' }));
    at.appendChild(el('p', { 'class': 'ss-followed__size', text: isNum(item.reference_shares)
      ? 'your reference size ' + plural(item.reference_shares, 'share') + (isNum(item.suggested_shares) ? ' · plan suggested ' + item.suggested_shares : '')
      : (isNum(item.suggested_shares) ? plural(item.suggested_shares, 'share') + ' suggested by the plan' : 'observation only, no size') }));
    const annotation = item.annotation || {};
    if (annotation.taken) at.appendChild(el('p', { 'class': 'sc-hint', text: 'You marked: I took this setup' }));
    if (annotation.reference_amount) at.appendChild(el('p', { 'class': 'sc-hint', text: 'Reference amount: USD ' + amountText(annotation.reference_amount) }));
    card.appendChild(at);
    // group two: what has been seen since
    const since = el('div', { 'class': 'ss-followed__group', 'data-group': 'since' }, [el('span', { 'class': 'sc-eyebrow', text: 'since the signal' })]);
    if (o.latest) {
      since.appendChild(el('p', { 'class': 'ss-followed__latest' }, [
        el('strong', { text: usd(o.latest.c) }),
        el('span', { 'class': 'ss-followed__when', text: dateWords(o.latest.date) }),
        isNum(o.change) ? el('span', { 'class': 'ss-followed__move', 'data-dir': o.change > 0 ? 'up' : o.change < 0 ? 'down' : 'flat', text: pct(o.change) }) : null,
        chip(STAND_WORDS[o.stand][0], STAND_WORDS[o.stand][1]),
        o.latest.revised ? chip('revised', 'warn') : null
      ]));
      const trail = observedTrail(item, o);
      if (trail) since.appendChild(trail);
    } else {
      since.appendChild(el('p', { 'class': 'ss-followed__latest ss-followed__latest--none', text: 'No later close has been observed.' }));
    }
    // one line, not three paragraphs: the whole of it is said in the saved detail
    if (o.brief) since.appendChild(el('p', { 'class': 'sc-hint ss-followed__caveat', title: [o.limitation, o.coverage].filter(Boolean).join(' '), text: o.brief }));
    card.appendChild(since);
    if (text(snap.summary)) card.appendChild(el('p', { 'class': 'ss-followed__note' }, [el('span', { 'class': 'ss-followed__note-label', text: 'the record says' }), ' “' + snap.summary + '”']));
    const actions = el('div', { 'class': 'ss-followed__actions' });
    const openBtn = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', text: 'Open saved setup', 'data-open-saved': item.id });
    openBtn.addEventListener('click', () => open.click());
    const remove = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', text: 'Remove' });
    remove.addEventListener('click', async () => { const res = await SCStock.follow.commit('remove', item.id); if (!res.ok) { setFollowStatus(res.error); return; } if (state.view === 'explore') renderDetailFollow(); afterFollowChange(); });
    actions.appendChild(openBtn); actions.appendChild(remove);
    card.appendChild(actions);
    return card;
  }
  function recoveryDownload(host) {
    if (!SCStock.follow.pending() || host.querySelector('[data-storage-recovery]')) return;
    const button = el('button', { type: 'button', 'class': 'sc-btn sc-btn--secondary sc-btn--sm', 'data-storage-recovery': '', text: 'Download recovery copy' });
    button.addEventListener('click', () => {
      const pending = SCStock.follow.pending();
      const url = URL.createObjectURL(new Blob([JSON.stringify(pending, null, 2)], { type: 'application/json' }));
      const link = el('a', { href: url, download: 'spicystock-local-recovery.json' }); link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    host.appendChild(button);
  }
  function setFollowStatus(msg) { const p = $('following-status'); if (!p) return; p.textContent = msg || ''; p.hidden = !msg; }
  function renderFollowing() {
    const list = $('following-list'), count = $('following-count');
    if (!list) return;
    clear(list);
    recoveryDownload($('following'));
    const st0 = SCStock.follow.status(), items = SCStock.follow.list();
    if (count) count.textContent = items.length ? plural(items.length, 'setup') + ' · saved in this browser' : 'saved in this browser';
    // a migration is reported for as long as the page is open, because the
    // store it happened to no longer says it did
    const mig = st0.migration && st0.migration.ok ? st0.migration.note : (st0.migration && st0.migration.error) || '';
    // EVERY problem the store reported, not the first: an entry set aside, an
    // observation dropped and an upgrade are three different things to have
    // been told about, and a list read twice must not lose any of them
    const notes = (st0.notes || []).filter((n) => n && n !== mig);
    const rest = notes.length ? notes : [st0.error && st0.error !== mig ? st0.error : ''];
    setFollowStatus([mig, st0.aside && rest.indexOf(st0.aside) < 0 ? st0.aside : ''].concat(rest).filter(Boolean).join(' '));
    if (!items.length) { list.appendChild(el('div', { 'class': 'ss-following__empty', text: st0.available ? 'No saved setups yet. Save a setup from Today’s scan, or find an earlier published signal above. No amount or purchase information is needed.' : 'Nothing can be followed in this browser.' })); return; }
    items.slice().reverse().forEach((it) => list.appendChild(followedCard(it)));
  }
  // One refresh after any change to the shelf: the shelf itself, the jump
  // link, the lens counts (Following is a lens) and, when that lens is the one
  // in force, the list and the selection, since a stock just unfollowed leaves it.
  function afterFollowChange() {
    invalidateFollow();
    renderFollowing(); followJump();
    if (!model || state.view !== 'explore') return;
    state.picksKey = null;
    if (lensOf(state.stage) === 'following') applyRoute(parseHash(w.location.hash));
    else renderPicks();
  }
  // another tab followed, unfollowed or resized something: this one re-reads
  // the store rather than writing its own idea of the list over it
  SCStock.follow.onChange(() => { if (current) { invalidateFollow(); renderFollowing(); followJump(); if (savedOpen) openSaved(savedOpen, false); renderDetailFollow(); if (model && state.view === 'explore') { state.picksKey = null; renderPicks(); } } });
  // the chosen stock's follow block, redrawn after a change made from the shelf
  function renderDetailFollow() {
    const box = d.querySelector('#detail .ss-follow'), c = model && model.byId[state.selected[state.stage]];
    if (box && c) box.parentNode.replaceChild(followBlock(c), box);
  }

  // ------------------------------------------------- the saved setup's own detail
  // Keyed by the saved identity -- kind, ticker, signal session, rules -- and
  // never by tonight's stage and ticker, because the symbol may be in another
  // stage tonight, under a newer signal, or in no list at all. What it shows
  // is the record of the night it was saved: a ticket there is a ticket THERE,
  // and the only way to an order that could be placed is the current record's
  // own card, behind the freshness, regime and eligibility guards that offer it.
  let savedOpen = null, savedPanel = null, savedReturn = null;
  function savedCandidate(item) {
    const snap = item.snapshot || {}, lv = snap.levels || {}, ev = item.evidence;
    if (!ev || !(ev.series || []).length) return null;
    const plan = { stop: lv.stop, stop_basis: lv.stop_basis, entry_ref: lv.trigger, entry_low: lv.entry_low, entry_high: lv.limit,
      day2_spent_above: lv.day2_spent_above, planned_entry: null,
      targets: { low: lv.target_low, high: lv.target_high, low_pct: lv.target_low_pct, high_pct: lv.target_high_pct } };
    const anchors = ev.anchors || [], base = anchors.find((a) => a.key === 'base'), box = anchors.find((a) => a.key === 'box');
    const row = { ticker: item.ticker, close: snap.close, summary: snap.summary, plan: plan, chart: null,
      quality: { base: base ? { start: base.from, end: base.to, low: base.low, high: base.high, breakdown_dates: [] } : {}, checks: [], vetoes: [] },
      box: box ? { start: box.from, end: box.to, low: box.low, high: box.high } : {} };
    return { id: 'saved:' + item.id, stage: item.stage === 'setting-up' ? 'setting-up' : 'bursts', ticker: item.ticker, name: text(snap.name),
      grade: snap.grade || null, score: isNum(snap.score) ? snap.score : null, status: snap.status, reason: text(snap.withheld_reason),
      plan: plan, row: row, quiet: false, flags: [], series: ev.series, signalSession: item.session,
      barsNote: (ev.recovered
        ? 'The daily bars this browser recovered from the ' + dateWords(item.session) + ' record — the same signal this setup was saved from, matched on symbol, session and rules identity'
        : 'The daily bars this browser saved from the ' + dateWords(item.session) + ' record') + ', up to the signal session',
      evidence: anchors.map((a) => ({ key: a.key, label: text(a.label) || ANCHOR_WORDS[a.key] || a.key, from: a.from, to: a.to, low: a.low, high: a.high,
        lede: text(a.lede), measured: text(a.measured), rows: [] })) };
  }
  function savedFacts(item) {
    const snap = item.snapshot || {}, lv = snap.levels || {}, rows = [];
    const put = (k, v) => { if (v) rows.push([k, v]); };
    put('stage', (item.kind === 'anticipation' ? 'setting up' : 'burst') + ' · ' + dateWords(item.session));
    put('published', (item.provenance || {}).published_at || 'publication time not retained in this older save');
    put('source record', (item.provenance || {}).record_id || ((item.provenance || {}).run_id ? 'workflow run ' + item.provenance.run_id : 'source identifier not retained in this older save'));
    put('scan', snap.scan);
    put('grade', snap.grade ? snap.grade + (isNum(snap.score) ? ' · ' + snap.score.toFixed(1) : '') + ' in that record' : 'no grade was archived');
    put('signal close', isNum(snap.close) ? usd(snap.close) + ' on ' + dateWords(text(snap.close_date) || item.session) : '');
    put('trigger', isNum(lv.trigger) ? usd(lv.trigger) : '');
    put('limit', isNum(lv.limit) ? usd(lv.limit) : '');
    put('too extended over', isNum(lv.day2_spent_above) && lv.day2_spent_above !== lv.limit ? usd(lv.day2_spent_above) : '');
    put('stop', isNum(lv.stop) ? usd(lv.stop) + (STOP_BASIS[lv.stop_basis] ? ' · ' + STOP_BASIS[lv.stop_basis] : '') : '');
    put('aim', isNum(lv.target_low) && isNum(lv.target_high)
      ? [estimate(usd(lv.target_low) + '–' + usd(lv.target_high)), ' · estimated from the indicative entry']
      : '');
    put('size', isNum(item.reference_shares)
      ? 'your reference size ' + plural(item.reference_shares, 'share') + (isNum(item.suggested_shares) ? ' · the plan suggested ' + item.suggested_shares : '')
      : (isNum(item.suggested_shares) ? plural(item.suggested_shares, 'share') + ' suggested by that plan' : 'observation only, no size'));
    put('saved', text(item.saved_at) ? dateWords(item.saved_at.slice(0, 10)) + ' in this browser' : 'in this browser');
    return rows;
  }
  function savedSignalSection(item) {
    const snap = item.snapshot || {}, box = el('section', { 'class': 'ss-saved__section', 'data-saved': 'signal' });
    box.appendChild(el('h3', { 'class': 'sc-eyebrow', text: 'at the signal' }));
    box.appendChild(el('p', { 'class': 'ss-saved__lede', text: 'The ' + dateWords(item.session) + ' record as it stood, saved in this browser and never rewritten by a later one.' }));
    const c = savedCandidate(item);
    if (c) {
      savedPanel = chartPanel(c, { idPrefix: 'saved', height: narrow() ? 280 : 340 });
      box.appendChild(savedPanel.node);
    } else {
      box.appendChild(el('div', { 'class': 'ss-chart-empty', 'data-chart': 'unsaved' }, [
        el('strong', { text: item.evidence_dropped ? 'Original chart was not saved because browser storage was full. ' : item.provenance && item.provenance.record_id ? 'Original chart unavailable in this archived record. ' : 'Original chart was not saved. ' }),
        'This setup was kept before this page saved chart evidence, or the record carried no daily bars for ' + item.ticker + ' that night. The levels and the reasons below are the ones saved with it; no chart is reconstructed from a later record, because a later record is a different signal.'
      ]));
    }
    const dl = el('dl', { 'class': 'ss-saved__facts' });
    savedFacts(item).forEach((r) => dl.appendChild(el('div', null, [el('dt', { text: r[0] }),
      typeof r[1] === 'string' ? el('dd', { text: r[1] }) : el('dd', null, r[1])])));
    box.appendChild(dl);
    if (snap.reader_reason) box.appendChild(el('p', { 'class': 'sc-hint', text: 'Original chart reader: ' + snap.reader_reason }));
    if (text(snap.summary)) box.appendChild(el('p', { 'class': 'ss-saved__quote' }, [el('span', { 'class': 'sc-eyebrow', text: 'the record said' }), ' “' + snap.summary + '”']));
    if (text(snap.withheld_reason)) box.appendChild(el('p', { 'class': 'ss-saved__quote', 'data-saved-reason': '' }, [el('span', { 'class': 'sc-eyebrow', text: 'no ticket, because' }), ' ' + cap(sentence(snap.withheld_reason))]));
    const lim = (snap.limitations || []).slice();
    if (lim.length) {
      box.appendChild(el('p', { 'class': 'sc-eyebrow', text: 'what that record could not show' }));
      box.appendChild(el('ul', { 'class': 'ss-saved__limits' }, lim.map((x) => el('li', { text: cap(x) }))));
    }
    if (text(snap.instruction) || text(snap.order_line)) {
      box.appendChild(el('div', { 'class': 'ss-saved__archived', 'data-archived-order': '' }, [
        el('span', { 'class': 'sc-eyebrow', text: 'the instruction in that record' }),
        el('p', { 'class': 'ss-saved__order', text: '“' + (text(snap.instruction) || text(snap.order_line)) + '”' }),
        el('p', { 'class': 'sc-hint', text: 'Recorded for ' + dateWords(item.session) + ' and shown as history. It is not an instruction for today, and no order can be placed from it here.' })
      ]));
    }
    return box;
  }
  function savedSinceSection(item) {
    const o = observationState(item), box = el('section', { 'class': 'ss-saved__section', 'data-saved': 'since' });
    box.appendChild(el('h3', { 'class': 'sc-eyebrow', text: 'since the signal' }));
    if (o.latest) {
      box.appendChild(el('p', { 'class': 'ss-saved__latest' }, [
        el('strong', { text: usd(o.latest.c) }), el('span', { 'class': 'ss-followed__when', text: dateWords(o.latest.date) }),
        isNum(o.change) ? el('span', { 'class': 'ss-followed__move', 'data-dir': o.change > 0 ? 'up' : o.change < 0 ? 'down' : 'flat', text: pct(o.change) + ' from the signal close' }) : null,
        chip(STAND_WORDS[o.stand][0], STAND_WORDS[o.stand][1])
      ]));
      const trail = observedTrail(item, o);
      if (trail) box.appendChild(trail);
    } else box.appendChild(el('p', { 'class': 'ss-saved__latest ss-saved__latest--none', text: 'No later close has been observed for ' + item.ticker + '.' }));
    if (o.limitation) box.appendChild(el('p', { 'class': 'sc-hint ss-saved__limit', text: o.limitation }));
    const horizon = (current.observations || {}).days || 21;
    const daysSince = (parseISO(text((current.run || {}).session)) - parseISO(item.session)) / 86400000;
    const coverage = daysSince > horizon ? 'The public observation window has ended. Your saved setup and last actual observation remain here.' : !recordBarsFor(item.ticker).length ? 'Not observed in the loaded record. This does not establish a delisting.' : '';
    if (coverage) box.appendChild(el('p', { 'class': 'sc-hint', text: coverage }));
    if (o.coverage) box.appendChild(el('p', { 'class': 'sc-hint ss-saved__limit', text: o.coverage }));
    if (o.count) {
      const head = ['session', 'close', 'against the signal', 'where it came from'];
      const rows = (item.observations || []).slice().reverse().map((ob) => [
        dateWords(ob.date) + (ob.revised ? ' · revised' : ''), usd(ob.c),
        o.basis === 'adjusted' || !isNum(o.base) ? 'not comparable' : pct((ob.c / o.base - 1) * 100),
        text(ob.source) + (text(ob.from_session) ? ' · ' + dateShort(ob.from_session) + ' record' : '')
      ]);
      box.appendChild(el('div', { 'class': 'sc-table-scroll ss-saved__obs' }, [
        el('table', { 'class': 'sc-table' }, [
          el('thead', null, [el('tr', null, head.map((h) => el('th', { text: h })))]),
          el('tbody', null, rows.map((r, i) => el('tr', { 'data-obs-row': String(i) }, r.map((v) => el('td', { text: v })))))
        ])
      ]));
      const revised = (item.observations || []).filter((ob) => ob.revised);
      if (revised.length) box.appendChild(el('p', { 'class': 'sc-hint', text: revised.length === 1
        ? 'One session was re-published with a different close and is marked revised: the same trading day read again on later bars, not a second day.'
        : revised.length + ' sessions were re-published with different closes and are marked revised: the same trading days read again on later bars, not further days.' }));
      box.appendChild(el('p', { 'class': 'sc-hint', text: 'At most ' + SCStock.follow.OBSERVATION_MAX + ' observed sessions are kept per setup, which is a limit on this list and not on how long a setup is held. Sessions no record here carried are simply missing; no price is filled in for them.' }));
    }
    const upd = modelUpdateOf(item);
    if (upd.plan && upd.matched) {
      const p = upd.plan;
      box.appendChild(el('div', { 'class': 'ss-saved__model', 'data-model-update': 'matched' }, [
        el('span', { 'class': 'sc-eyebrow', text: 'the model plan for this signal' }),
        el('p', null, [d.createTextNode('Day ' + plain(p.day) + ' · '), chip(PLAN_STATUS[p.status] ? PLAN_STATUS[p.status][0] : words(p.status), PLAN_STATUS[p.status] ? PLAN_STATUS[p.status][1] : 'neutral'),
          d.createTextNode(isNum(p.current_stop) ? ' · stop now ' + usd(p.current_stop) : '')]),
        text(p.instruction) ? el('p', { 'class': 'ss-saved__quote', text: '“' + p.instruction + '”' }) : null,
        el('p', { 'class': 'sc-hint', text: 'The model’s own plan over configured sizing assumptions, matched to this signal by its session and its rules. It is not your position and not a record of anything you did.' })
      ]));
    } else if (upd.why) {
      box.appendChild(el('div', { 'class': 'ss-saved__model', 'data-model-update': 'apart' }, [
        el('span', { 'class': 'sc-eyebrow', text: 'a model plan, but not this signal’s' }),
        el('p', { 'class': 'sc-hint', text: upd.why })
      ]));
    }
    return box;
  }
  function buildSaved(dlg, item, id) {
    disposeSaved();
    clear(dlg);
    // the identity on the sheet itself: a reader (and a check) can see WHICH
    // saved setup is open, which is the whole point of a sheet keyed by one
    const wrap = el('div', { 'class': 'ss-saved__wrap', 'data-saved-id': id });
    const close = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', id: 'saved-close', text: 'Close' });
    close.addEventListener('click', () => closeSaved());
    if (!item) {
      wrap.appendChild(el('header', { 'class': 'ss-saved__head' }, [
        el('div', null, [el('div', { 'class': 'sc-eyebrow', text: 'saved setup' }), el('h2', { id: 'saved-h2', text: 'Not saved in this browser' })]), close]));
      wrap.appendChild(el('p', { 'class': 'ss-saved__lede', 'data-saved-missing': '', text: 'This link names a setup saved in a browser, and this browser does not hold it. A followed setup lives in local storage and travels nowhere: not to the record, not to the repository, not to another device. Nothing is missing from the record — there is simply no local copy here.' }));
      wrap.appendChild(el('p', { 'class': 'sc-hint', text: 'The identity in the link is ' + id + '.' }));
      if (annotationDrafts.has(id)) wrap.appendChild(el('label', { text: 'Your unsaved reference amount (USD)' }, el('input', { 'class': 'sc-input', value: annotationDrafts.get(id), 'aria-label': 'Unsaved reference amount, available to copy' })));
      dlg.appendChild(wrap);
      return close;
    }
    const snap = item.snapshot || {};
    wrap.appendChild(el('header', { 'class': 'ss-saved__head' }, [
      el('div', null, [
        el('div', { 'class': 'sc-eyebrow', text: 'saved setup · ' + (item.kind === 'anticipation' ? 'setting up' : 'burst') + ' · signal ' + dateWords(item.session) }),
        el('h2', { id: 'saved-h2' }, [el('span', { 'class': 'sc-case', text: item.ticker }), text(snap.name) ? el('small', { 'class': 'ss-saved__name', text: snap.name }) : null])
      ]),
      el('div', { 'class': 'ss-saved__chips' }, [chip(archivedWords(item), snap.status === 'ticket' ? 'good' : 'neutral', true), item.demo ? chip('demo', 'warn') : null]),
      close]));
    wrap.appendChild(el('p', { 'class': 'ss-saved__note', text: cap((text(snap.status_words) || 'no ticket')) + ' in the ' + dateWords(item.session) + ' record — a fact about that record, not a ticket available now.' }));
    wrap.appendChild(annotationForm(item));
    wrap.appendChild(savedSignalSection(item));
    wrap.appendChild(savedSinceSection(item));
    const foot = el('div', { 'class': 'ss-saved__foot' });
    const cur = currentSetupFor(item);
    if (cur && cur.same) {
      const b = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', 'data-current-setup': cur.candidate.ticker, text: 'Open it in tonight’s record' });
      b.addEventListener('click', () => { pendingFocus = 'detail'; state.gesture = true; navigate(routeHash(cur.candidate.stage, cur.candidate.id)); });
      foot.appendChild(b);
      foot.appendChild(el('p', { 'class': 'sc-hint', text: 'This is the same signal tonight’s record carries, so the card there is this setup, live.' }));
    } else if (cur) {
      const b = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', 'data-current-setup': cur.candidate.ticker, text: 'Current setup for ' + cur.candidate.ticker });
      b.addEventListener('click', () => { pendingFocus = 'detail'; state.gesture = true; navigate(routeHash(cur.candidate.stage, cur.candidate.id)); });
      foot.appendChild(b);
      foot.appendChild(el('p', { 'class': 'sc-hint', text: 'Tonight’s record carries a ' + (cur.movedStage ? STAGE_NAME[cur.candidate.stage].toLowerCase() + ' ' : '') + 'signal for ' + cur.candidate.ticker + ' from ' + dateWords(text((current.run || {}).session)) + '. It is a different signal with its own grade, its own levels and its own status; any ticket it carries is offered there, under tonight’s guards.' }));
    } else {
      foot.appendChild(el('p', { 'class': 'sc-hint', 'data-current-setup': 'none', text: model
        ? item.ticker + ' is on no list in tonight’s record, so there is no current setup to open. The saved one above is unaffected.'
        : 'No record is loaded, so there is no current setup to compare this with. The saved one above is unaffected: it lives in this browser.' }));
    }
    const remove = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', 'data-saved-remove': '', text: 'Remove from My setups' });
    remove.addEventListener('click', async () => {
      const res = await SCStock.follow.commit('remove', item.id);
      if (!res.ok) { foot.appendChild(el('p', { 'class': 'ss-follow__warn', role: 'alert', text: res.error })); return; }
      closeSaved(); if (state.view === 'explore') renderDetailFollow(); afterFollowChange();
    });
    foot.appendChild(remove);
    wrap.appendChild(foot);
    dlg.appendChild(wrap);
    return close;
  }
  function disposeSaved() { if (savedPanel) { savedPanel.dispose(); savedPanel = null; } }
  function openSaved(id, first) {
    const dlg = $('saved');
    if (!dlg) return;
    let item = null;
    try { item = SCStock.follow.find(id); } catch (e) { item = null; }
    // where the reader was: kept on the FIRST open, so re-reading the sheet
    // over a newer record does not overwrite it with the sheet's own route
    if (savedOpen !== id || !dlg.open) savedReturn = { focus: d.activeElement, scroll: w.pageYOffset || w.scrollY || 0, hash: first ? '' : lastHash };
    savedOpen = id;
    const active = d.activeElement, focused = active && dlg.contains(active) ? active.id : null;
    const selection = focused === 'setup-amount' ? [active.selectionStart, active.selectionEnd] : null;
    const close = buildSaved(dlg, item, id);
    if (focused && $(focused)) { $(focused).focus(); if (selection) $(focused).setSelectionRange(...selection); }
    if (!dlg.open) { if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', ''); close.focus(); }
  }
  function closeSaved() {
    const dlg = $('saved');
    if (!dlg) return;
    if (dlg.open && dlg.close) dlg.close('closed');
    else if (dlg.hasAttribute('open')) { dlg.removeAttribute('open'); afterSavedClose(); }
    else savedOpen = null;
  }
  // One teardown, whichever way the sheet was dismissed. Dismissed IN PLACE
  // (Close, Escape, the backdrop) the hash still names the sheet, so it is
  // taken back to the route the reader came from and their focus and scroll
  // with it; dismissed BY a route they asked for (tonight's card, another
  // saved setup) the new route owns both and nothing is restored over it.
  function afterSavedClose() {
    const dlg = $('saved'), b = savedReturn, wasOpen = savedOpen;
    savedOpen = null; savedReturn = null;
    disposeSaved();
    clear(dlg);
    if (!wasOpen || String(w.location.hash).indexOf('#/followed/') !== 0) return;
    const to = b && b.hash && b.hash.indexOf('#/followed/') !== 0 ? b.hash : '#/setups';
    if (w.location.hash !== to) w.location.hash = to;
    if (!b) return;
    if (b.focus && b.focus.isConnected && b.focus.focus) b.focus.focus({ preventScroll: true });
    w.scrollTo(0, b.scroll);
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
      : [c.plan ? noTicketLead(c) + ' The setup would need: ' + (entry || 'an entry the plan does not spell out.') : 'Nothing: ' + sentence(c.reason)];
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
      : [c.plan ? noTicketLead(c) + ' The setup would need: ' + (entry || sentence(wl.instruction) || 'an entry the plan does not spell out.') : (text(wl.instruction) ? sentence(wl.instruction) : 'The run wrote no plan for it.')];
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
    const sw = statusWords(c.status), offered = !!(av && av.offered), plan = c.plan || {};
    const tm = (av || {}).timing || {}, ph = (av || {}).phase || 'unknown';
    const box = el('div', { 'class': 'sc-actionbar ss-action', 'data-ticket': c.status === 'ticket' ? (offered ? 'order' : 'blocked') : c.status,
      'data-window': ph });
    let line, btn;
    if (c.status === 'ticket' && offered) {
      // the day the ticket is for, named: "tomorrow" is true for one evening
      // and wrong from the next midnight, on the very session it means
      const when = ph === 'open' ? 'inside ' + dateWords(tm.session) + '’s entry window, which runs to ' + timeET(tm.cutoff.toISOString())
        : 'on its own terms in ' + dateWords(tm.session) + '’s entry window';
      line = 'Conditional ticket: ' + (text(plan.order_line) ? plan.order_line : 'see the plan') + '. It fills only ' + when + '; nothing here is placed for you.';
      btn = el('button', { 'class': 'sc-btn sc-btn--secondary', type: 'button', text: 'View conditional plan', 'data-open': 'disc-plan' });
      box.appendChild(chip(sw[0], sw[1]));
    } else if (c.status === 'ticket') {
      // the recorded ticket stays inspectable; only placing it is withdrawn
      line = av.reason;
      btn = el('button', { 'class': 'sc-btn sc-btn--secondary', type: 'button',
        text: av.timingBlocked ? 'Inspect the recorded ticket' : 'Inspect conditions',
        'data-open': av.timingBlocked ? 'disc-plan' : 'disc-checklist' });
      box.appendChild(chip(av.lead, av.pubBlocked ? 'warn' : PHASE_TONE[ph]));
    } else {
      line = (c.reason ? cap(sentence(c.reason)) : 'No ticket tonight.') + (c.plan ? ' The setup is kept here for inspection.' : '');
      btn = el('button', { 'class': 'sc-btn sc-btn--secondary', type: 'button', text: 'Inspect conditions', 'data-open': 'disc-checklist' });
      box.appendChild(chip(sw[0], sw[1]));
    }
    box.appendChild(el('p', { text: line }));
    if (copyRefused && copyRefused.ticker === c.ticker)
      box.appendChild(el('p', { 'class': 'ss-action__refused', 'data-copy-refused': '', role: 'alert', text: copyRefused.text }));
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
  const VERDICT_GLYPH = { pass: '✓', partial: '~', fail: '✕', veto: '✕', 'not measured': '—' };
  const VERDICT_SIGNAL = { pass: 'good', partial: 'caution', fail: 'blocked', veto: 'blocked', 'not measured': null };
  // A check the record dated is a way ONTO the chart: the tile and the evidence
  // row are one mechanism, so "inspect the base" has a single implementation.
  // A check with no recorded dates stays a tile and is never made clickable --
  // and `offered` is THIS stock's own anchors, because a class of check the
  // record usually dates is not a promise that this record dated this one.
  function checkTile(chk, vetoed, offered) {
    const word = checkVerdict(chk, vetoed), tone = VERDICT_SIGNAL[word], glyph = VERDICT_GLYPH[word];
    const display = chk ? String(chk.display || '') : '', threshold = chk ? String(chk.threshold || '') : '';
    const key = chk && CHECK_ANCHOR[chk.key] ? CHECK_ANCHOR[chk.key] : null;
    const anchor = key && offered && offered[key] ? key : null;
    const attrs = { 'class': 'sc-signal' + (tone ? ' sc-signal--' + tone : '') + (anchor ? ' ss-check--anchored' : ''),
      'data-check': chk ? chk.key : null, 'data-verdict': word, 'data-anchor': anchor,
      title: chk ? [display, threshold ? 'threshold: ' + threshold : '', chk.note].filter(Boolean).join('\n') : null };
    const kids = [
      el('span', { 'class': 'ss-check__label', text: chk ? (chk.label || words(chk.key)) : '—' }),
      el('span', { 'class': 'sc-signal__glyph', 'aria-hidden': 'true', text: glyph }),
      el('span', { 'class': 'sc-signal__label', text: word + (display ? ' · ' + display.split(' ')[0] : '') }),
      chk ? el('span', { 'class': 'sc-signal__note', text: threshold.length > 64 ? threshold.slice(0, 62).replace(/\s+\S*$/, '') + '…' : threshold }) : null,
      anchor ? el('span', { 'class': 'ss-check__show', text: 'show the ' + ANCHOR_WORDS[anchor].toLowerCase() + ' on the chart' }) : null
    ];
    if (!anchor) return el('div', attrs, kids);
    attrs.type = 'button';
    const btn = el('button', attrs, kids);
    btn.addEventListener('click', () => showEvidenceFromCheck(chk.key));
    return btn;
  }
  // the coil's own dated evidence, on the same one mechanism as the tiles
  function boxValue(box) {
    const words_ = isNum(box.sessions) ? plain(box.sessions) + ' sessions · ' + usd(box.low) + '–' + usd(box.high) : '—';
    if (!(text(box.start) && text(box.end))) return words_;
    const btn = el('button', { 'class': 'ss-fact__show', type: 'button', 'data-anchor': 'box', text: 'show on chart' });
    btn.addEventListener('click', () => {
      if (!detailPanel) return;
      detailPanel.showEvidence('box');
      scrollTo(detailPanel.node);
      const b = detailPanel.node.querySelector('[data-anchor="box"]');
      if (b) b.focus({ preventScroll: true });
    });
    return el('span', { 'class': 'ss-fact__with-show' }, [el('span', { text: words_ }), btn]);
  }
  function discChecklist(c) {
    const kids = [];
    if (c.stage === 'bursts') {
      const b = c.row, q = b.quality || {}, base = q.base || {}, checks = q.checks || [], vetoes = q.vetoes || [];
      const passes = checks.filter((x) => x && x.pass).length;
      kids.push(el('p', { 'class': 'sc-hint', text: checks.length ? 'Bonde’s ' + checks.length + ' A-quality criteria: the verdict in words, the measured value, his threshold. ' + passes + ' of ' + checks.length + ' pass (' + plain(q.passes) + ' of the ' + plain(q.of) + ' letters).' : 'No checklist was archived for this burst.' }));
      // the anchors THIS stock's record actually carries, so a tile is a way
      // onto the chart only where there is something for it to mark
      const offered = {}; evidenceItems(c).forEach((it) => { offered[it.key] = true; });
      if (checks.length) kids.push(el('div', { 'class': 'ss-checks' }, checks.map((x) => checkTile(x, vetoedCheck(x.key, vetoes), offered))));
      if (vetoes.length) kids.push(el('p', { 'class': 'sc-note', text: 'Veto: ' + vetoes.map((v) => VETO_WORDS[v] || words(v)).join(', ') + '.' }));
      kids.push(el('div', { 'class': 'sc-eyebrow', text: 'the measurements' }));
      const vr = volumeRatio(b);
      const volumeNote = vr.source === 'checklist' ? ' · volume ratio read from the checklist’s block, the scan’s own field being empty in this record'
        : vr.source === null ? ' · volume ratio not recorded'
        : isNum(vr.disagrees) ? ' · the checklist’s block says ' + vr.disagrees.toFixed(2) + '× volume' : '';
      kids.push(factList([
        ['the burst', pct(b.gain_pct) + ' · ' + volumeTimes(b) + '× volume', 'open ' + usd(b.open) + ' · high ' + usd(b.high) + ' · low ' + usd(b.low) + ' · close ' + usd(b.close) + ' · prior close ' + usd(b.prev_close) + volumeNote],
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
        ['the box', boxValue(box), box.start && box.end ? dateShort(box.start) + ' to ' + dateShort(box.end) + (isNum(box.spread) ? ' · spread ' + plain(box.spread) + '%' : '') : ''],
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
    const offered = !!(av && av.offered), withheld = c.status !== 'ticket' || !offered, t = plan.targets || {};
    if (c.stage === 'bursts') {
      kids.push(factList([
        ['buy', usd(plan.entry_low) + ' – ' + usd(plan.entry_high), (plan.entry_window || '') + ' · a buy stop at ' + usd(plan.entry_ref) + ', limit ' + usd(plan.entry_high) + (text(plan.limit_note) ? ' · ' + plan.limit_note : ''), true],
        ['skip if it opens above', usd(plan.skip_if_open_above), 'day 2 is spent' + (isNum(plan.limit) && isNum(plan.skip_if_open_above) && plan.limit !== plan.skip_if_open_above ? ', the outer threshold and not the ' + usd(plan.limit) + ' ticket limit' : '') + '; a resting order could still fill on a pullback, so cancel it'],
        ['skip if it opens below', usd(plan.skip_if_open_below), 'the burst is failing; do not place it'],
        ['stop', stopWords(plan), 'judged at the ' + usd(plan.sizing_price) + ' limit · move it to your entry day’s low once filled', true],
        ['sized at', usd(plan.sizing_price), 'the limit, the highest fill the ticket permits · indicative entry ' + usd(plan.planned_entry) + (plan.planned_entry_capped ? ' (not a fill; the close +1% would sit over the limit, so it is the limit)' : ' (not a fill)'), true],
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
    const hint = c.status === 'ticket' && !offered ? av.reason + (av.timingBlocked ? ' ' + cancelLine() : '')
      : c.status === 'ticket' ? 'No order line was written for this plan.'
      : noTicketLine(c) + ' The setup is kept here for inspection.';
    // the ticket the record published stays printed as history even when it is
    // no longer offered: withdrawing the COPY is not erasing the evidence
    if (c.status === 'ticket' && av.timingBlocked && plan.order_json) kids.push(recordedTicket(plan, av));
    kids.push(orderBlock(plan, hint, withheld));
    return disclosure('disc-plan', 'Conditional plan, sizing and order', withheld ? (c.status === 'ticket' ? av.lead : statusWords(c.status)[0]) : 'sized at the limit', kids);
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
    // the stepper counts the CURRENT visible list, so a lens or a search that
    // changed without changing the stock still says where this stock sits
    const tools = box.querySelector('.ss-detail__tools');
    if (tools && c) tools.parentNode.replaceChild(detailTools(c), tools);
    syncPins();
    if (pendingFocus === 'detail') { pendingFocus = ''; box.focus({ preventScroll: true }); scrollTo(box); }
    else if (state.gesture && narrow() && c) scrollTo(box);
    state.gesture = false;
  }

  // ---------------------------------------------------------------- the tickets, as a disclosure
  function renderTickets(data) {
    const bursts = by(data.bursts || []), trades = (data.trades || []).map((t) => bursts[t]).filter(Boolean);
    const withOrders = trades.filter((b) => b.plan && b.plan.order_json), offered = !!(av && av.offered);
    const tm = av.timing, regime = ((data.breadth || {}).regime || {}).verdict;
    // the session, not "tomorrow": the sheet is read on the day it is for
    const forDay = tm.known ? dateWords(tm.session) + '’s tickets' : 'Tickets, session undated';
    $('orders-summary').textContent = forDay + ' · ' + (withOrders.length ? plural(withOrders.length, 'order') + (offered ? '' : ', ' + av.lead) : 'none');
    const cb = data.cash_budget || {}, acct = data.account || {};
    const budget = clear($('budget'));
    budget.appendChild(el('strong', { text: cb.sentence || ('Model allocation: tomorrow’s tickets would commit ' + usd(cb.committed_usd, 0) + ' of the configured ' + usd(acct.equity, 0) + ' · ' + plain(cb.slots_used) + ' of ' + plain(cb.slots_max) + ' slots') }));
    if (isNum(cb.at_risk_usd)) budget.appendChild(d.createTextNode(' · ' + usd(cb.at_risk_usd, 0) + ' planned price-to-stop risk'));
    budget.appendChild(d.createTextNode(' · over the configured sizing assumptions, not a balance, settled cash or buying power'));
    // the cut's own reason already opens with "ticket withheld" when the stop
    // rule refused it, so the lead is dropped rather than said twice
    (cb.cut || []).forEach((c) => budget.appendChild(el('span', { 'class': 'sc-note',
      text: saysNoTicket(c.reason) ? c.ticker + ' — ' + c.reason : 'No ticket: ' + c.ticker + ' — ' + c.reason })));
    const sheet = clear($('orders-table'));
    const table = el('table', { 'class': 'sc-table sc-table--compact ss-orders', id: 'order-sheet' });
    table.appendChild(el('caption', { 'class': 'sc-sr-only', text: (tm.known ? dateWords(tm.session) + '’s orders' : 'The orders') + ' in Fidelity’s field order' }));
    table.appendChild(el('thead', null, el('tr', null, ['symbol', 'action', 'shares', 'type', 'stop (trigger)', 'limit', 'tif', 'then OTO sell stop', 'too extended over', 'planned risk'].map((h, i) => el('th', { scope: 'col', 'class': i >= 2 && i !== 3 && i !== 6 ? 'sc-num' : null, text: h })))));
    const body = el('tbody');
    const rows = offered ? withOrders : [];
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
    if (!rows.length) body.appendChild(el('tr', { 'class': 'sc-empty' }, el('td', { colspan: '10', text: !offered && withOrders.length ? 'No orders offered: ' + av.reason : st && st.state === 'closed' ? 'No orders: the market was closed and the plans stand.' : regime === 'red' ? 'No orders: breadth is red.' : 'No orders for ' + (tm.known ? dateWords(tm.session) : 'the next session') + '.' })));
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
        el('span', { 'class': 'sc-signal-matrix__note', text: pct(b.gain_pct) + ' · ' + volumeTimes(b) + '× vol · ' + usd(b.close) + (b.scan === 'dollar' ? ' · $ scan' : '') })
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
  // The one next action, and the surface the session-aware pass exists for:
  // it used to name the desk's 9:28 AM reminder at every hour of every day,
  // so a reader at eleven o'clock was told to act before a deadline ninety
  // minutes gone, on "tomorrow's" tickets, on the very day they were for.
  //
  // The order of refusal is publication, then the record's own safeguards,
  // then the clock -- timing narrows and never overrides, so a red night's
  // headline stays "no new longs" and the window's state is said beside it.
  function timingLine(tm, ph) {
    if (ph === 'unknown') return 'This record does not say which session its plans are for, so the page will not name a deadline for them.';
    const day = dateWords(tm.session), ends = timeET(tm.cutoff.toISOString());
    if (ph === 'ended') return 'The entry window for ' + day + ' ended at ' + ends + '; nothing here is an order to place now.';
    if (ph === 'open') return 'The scheduled entry window for ' + day + ' runs to ' + ends + '. This page reads the published record, not live prices: whether a trigger or a fill condition has been met is not verified here.';
    return 'The entry window for ' + day + ' opens at ' + timeET(tm.opens.toISOString()) + ' and runs to ' + ends + '.';
  }
  function cancelLine() {
    return 'If you submitted an order that did not fill, check or cancel it in your broker: SpicyStock places nothing and cancels nothing.';
  }
  function nextAction(data, s) {
    const bursts = by(data.bursts || []);
    const orders = (data.trades || []).map((t) => bursts[t]).filter((b) => b && b.plan && b.plan.order_json).length;
    const open = (data.open_plans || []).length, red = ((data.breadth || {}).regime || {}).verdict === 'red';
    if (blocked(s)) return ['Do not place these orders.', 'Wait for tonight’s run to publish, or check the run log. Nothing on this page is the next session’s plan.', 'stale'];
    const tm = av.timing, ph = av.phase, window = tm.window;
    const line = timingLine(tm, ph);
    const day = tm.known ? dateWords(tm.session) : null;
    const by_ = tm.prepareBy ? timeET(tm.prepareBy.toISOString()) : ORDERS_BY;
    // the record's own safeguards first, with the window's state beside them
    if (s.state === 'closed') return ['Plans unchanged. Check the open model plans.', 'The market was closed on ' + dateWords(tm.closedSession || s.expected) + ', so the plans dated for it had no session. ' + line, 'closed'];
    if (red) return ['No new longs. Work the exits in the open model plans.', 'Breadth is red: tighten the stops and sell into strength. ' + line, 'red'];
    if (ph === 'unknown') return ['Entry timing unavailable — research only.', line + ' Read the setups and the evidence; do not place an order from a page that cannot date it.', 'stale'];
    if (ph === 'ended') {
      return orders
        ? ['The entry window for ' + day + ' has ended.', 'The ' + plural(orders, 'ticket') + ' the record published for it ' + (orders === 1 ? 'stays' : 'stay') + ' readable as history, and ' + (orders === 1 ? 'is' : 'are') + ' no longer offered to place. ' + cancelLine(), 'ended']
        : ['The entry window for ' + day + ' has ended.', 'Nothing new was offered for it. Work the exits in the open model plans and wait for the next run.', 'ended'];
    }
    if (ph === 'open') {
      return orders
        ? ['The entry window for ' + day + ' is in progress.', 'Place the ' + plural(orders, 'order') + ' on their own terms, exits first, and cancel any that has not filled by the end of the ' + window + '. ' + line, 'orders']
        : ['Nothing new to place in ' + day + '’s window.', 'No burst qualified with a ticket. ' + line, 'quiet'];
    }
    if (orders) return ['Plan for ' + day + ': place the ' + plural(orders, 'order') + ' in Fidelity before ' + by_ + '. Exits first.', 'Attach each sell stop the moment its buy fills, and cancel any order that has not filled by the end of the ' + window + '. ' + line, 'orders'];
    if (open) return ['Nothing new to place for ' + day + '. Work the exits in the open model plans.', 'No burst qualified with a ticket tonight; the open model plans still carry their instructions. ' + line, 'quiet'];
    return ['Nothing to place for ' + day + '. Keep cash.', 'No burst qualified and nothing is held. Come back after the next run. ' + line, 'quiet'];
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
  // The chooser reaches EVERY stock in the record, which is what it is for --
  // so it is the one door that must say where the reader is going. A name the
  // stage's own lens hides is listed under its own heading, marked on the item
  // and ordered after the ones in the lens, because choosing it widens the
  // lens for that stock: saying so afterwards, once the page has already
  // moved, is telling the reader what happened rather than what will.
  function fillChooser(q) {
    const list = clear($('chooser-list')); let n = 0, away = 0, first = null;
    STAGES.forEach((s) => {
      const items = model.stages[s].filter((c) => matches(c, q));
      if (!items.length) return;
      const lens = lensOf(s), inLens = items.filter((c) => lensPass(c, lens)), outside = items.filter((c) => !lensPass(c, lens));
      const group = (label, rows, out) => {
        if (!rows.length) return;
        list.appendChild(el('div', { 'class': 'sc-eyebrow ss-chooser__group', 'data-group': out ? 'outside' : 'in', text: label }));
        if (out) list.appendChild(el('p', { 'class': 'sc-hint ss-chooser__why', text: 'Choosing one of these shows every ' + (s === 'bursts' ? 'burst' : 'setup') + ' so it can be inspected; your ' + LENS_WORDS[lens] + ' lens is not changed for next time.' }));
        rows.forEach((c) => {
          n++; if (out) away++;
          const sw = statusWords(c.status);
          const b = el('button', { 'class': 'ss-chooser__item', type: 'button', 'data-id': c.id, 'data-in-lens': out ? 'false' : 'true',
            'aria-pressed': state.selected[s] === c.id ? 'true' : 'false' }, [
            el('b', { 'class': 'sc-case', text: c.ticker }),
            out ? el('em', { 'class': 'ss-chooser__away', text: 'outside the lens' }) : null,
            el('span', { text: pickReason(c) }), chip(sw[0], sw[1])
          ]);
          b.addEventListener('click', (e) => { e.preventDefault(); choose(c); });
          if (!first) first = b;
          list.appendChild(b);
        });
      };
      const name = STAGE_NAME[s].toLowerCase();
      if (!outside.length) group(name + ' · ' + items.length, items, false);
      else {
        group(name + ' · ' + inLens.length + ' in the ' + LENS_WORDS[lens] + ' lens', inLens, false);
        group(name + ' · ' + outside.length + ' outside it', outside, true);
      }
    });
    $('chooser-status').textContent = n ? n + ' stock' + (n === 1 ? '' : 's') + (q ? ' match ‘' + q + '’' : ' in tonight’s record')
      + (away ? ', ' + away + ' of them outside the lens you are reading' : '') + '; Enter chooses the first.'
      : 'No stock matching ‘' + q + '’ in tonight’s record.';
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
    // The clock, re-read where a page that was left alone comes back: a tab
    // brought forward, a window given focus, and a page the browser restored
    // from its back/forward cache -- which is served from a snapshot and would
    // otherwise show the words of whatever hour it was put away at.
    d.addEventListener('visibilitychange', () => { if (!d.hidden) reclock(); });
    w.addEventListener('focus', () => reclock());
    w.addEventListener('pageshow', () => reclock());
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
    // the lens row changes home at the phone breakpoint; nothing else moves
    if (w.matchMedia) {
      const mq = w.matchMedia('(max-width: 720px)');
      const onBreak = () => { if (model && state.view === 'explore') renderLens(state.stage); };
      if (mq.addEventListener) mq.addEventListener('change', onBreak);
      else if (mq.addListener) mq.addListener(onBreak);
    }
    // the comparison sheet: one teardown whichever way it was dismissed --
    // the Close button, Escape, or a press on the backdrop
    const cmp = $('compare');
    if (cmp) {
      cmp.addEventListener('close', afterCompareClose);
      cmp.addEventListener('click', (e) => { if (e.target === cmp) closeCompare(); });
    }
    // the saved setup's own sheet, dismissed the same three ways
    const sv = $('saved');
    if (sv) {
      sv.addEventListener('close', afterSavedClose);
      sv.addEventListener('click', (e) => { if (e.target === sv) closeSaved(); });
    }
    w.addEventListener('hashchange', () => applyRoute(parseHash(w.location.hash)));
  }

  // ---------------------------------------------------------------- the clock, re-read
  // A page left open crosses the deadline it is describing, so the answer is
  // re-read: on every render, when the tab becomes visible again, when the
  // window takes focus, when the browser restores the page from its back /
  // forward cache, and on a bounded tick while the tab is visible.
  //
  // What it does NOT do: re-render. The charts, the map, the lens, the
  // comparison, the saved sheet, the search box and the focus are all left
  // exactly where they are; only the surfaces whose words depend on the clock
  // are repainted, and only when the ANSWER changed. There is no countdown
  // and no cue that appears at the bell: a reader watching the page is told
  // the same thing a reader arriving is told.
  const CLOCK_TICK_MS = 30000;   // a bounded re-read while visible, not a countdown
  let clockTimer = null;
  function watchClock() {
    if (clockTimer) { w.clearInterval(clockTimer); clockTimer = null; }
    if (clockPinned) return;     // a pinned clock does not tick
    clockTimer = w.setInterval(() => { if (!d.hidden) reclock(); }, CLOCK_TICK_MS);
  }
  // the one re-reading. Returns true when something on the page changed.
  function reclock() {
    if (!loaded || !current || !current.run || clockPinned) return false;
    const next = availability(current, new Date());
    const same = av && next.phase === av.phase && next.pub.state === av.pub.state &&
      next.pub.chip === av.pub.chip && next.offered === av.offered;
    clockAt = next.at;
    av = next; st = av.pub; SCStock.state = st; SCStock.avail = av;
    if (same) return false;
    // the clock-dependent surfaces, and nothing else: no chart is disposed, no
    // lens re-read, no comparison closed, no saved sheet dismissed, and the
    // detail's chart instance is left standing while the words beside it change
    renderStatus(current, st);
    renderMarketBar(current, st);
    renderTickets(current);
    renderNext(current, st);
    reclockDetail();
    renderFollowing();
    renderTray();
    if (comparePanels.length && state.pins.length === 2) reclockCompare();
    d.documentElement.setAttribute('data-ss-rendered', st.state);
    d.documentElement.setAttribute('data-ss-window', av.phase);
    return true;
  }
  SCStock.reclock = reclock;

  // The chosen stock's clock-dependent parts, in place. `renderDetail()` would
  // rebuild the whole panel and dispose the chart, which is exactly what a
  // reader mid-reading must not have happen; these two children carry every
  // word the clock touches.
  function reclockDetail() {
    const box = $('detail'), c = model && state.stage ? model.byId[state.selected[state.stage]] : null;
    if (!box || !c) return;
    repaint(box.querySelector('.ss-action'), () => actionArea(c));
    repaint($('disc-plan'), () => discPlan(c));
  }
  // the comparison's fact table, whose ticket row says whether an order stands
  function reclockCompare() {
    const t = $('compare-table');
    if (!t) return;
    const a = model.byId[state.pins[0]], b = model.byId[state.pins[1]];
    if (a && b) repaint(t.parentNode, () => el('div', { 'class': 'sc-table-scroll ss-compare__facts' }, compareTable(a, b)));
  }
  // Swap a subtree for a freshly built one without taking the reader's place
  // with it: a disclosure that was open stays open, and whatever had focus is
  // found again by the attribute that identifies it.
  function repaint(node, build) {
    if (!node || !node.parentNode) return null;
    const held = node.contains(d.activeElement);
    const key = held ? focusKey(d.activeElement) : null;
    const wasOpen = node.tagName === 'DETAILS' ? node.open : null;
    const next = build();
    node.parentNode.replaceChild(next, node);
    if (wasOpen !== null && 'open' in next) next.open = wasOpen;
    if (!held) return next;
    // The control the reader was on may be the very one the clock withdrew --
    // a copy button on a window that closed is exactly that. Focus falls back
    // to the replacement itself rather than to the body, so the reader stays
    // where they were reading instead of at the top of the document.
    const back = (key && next.querySelector(key)) ||
      next.querySelector('summary, button, [href], input') || next;
    if (back.focus) {
      if (back === next && !next.hasAttribute('tabindex')) next.setAttribute('tabindex', '-1');
      back.focus({ preventScroll: true });
    }
    return next;
  }
  const FOCUS_KEYS = ['data-open', 'data-copy', 'data-follow', 'data-open-saved', 'data-pin', 'data-go'];
  function focusKey(node) {
    if (!node || !node.getAttribute) return null;
    for (let i = 0; i < FOCUS_KEYS.length; i++) {
      const a = FOCUS_KEYS[i];
      if (node.hasAttribute(a)) return '[' + a + '="' + String(node.getAttribute(a)).replace(/"/g, '\\"') + '"]';
    }
    return null;
  }

  // ---------------------------------------------------------------- check for updates
  // One control, beside the publication line it is about, that re-reads the
  // SAME static file the page booted from. It rescans nothing, grades nothing,
  // asks no provider, dispatches no workflow, sends no notification and polls
  // on no timer: a reader presses it, or it does not happen.
  //
  // The load is transactional. The bytes are parsed, held to the schema, the
  // run and the timing shape, and COMPARED against what is on screen before
  // anything is replaced; a record that is older than the one in front of the
  // reader is refused rather than applied backwards. Only the newest press
  // counts: an answer whose sequence is not the current one is dropped, so a
  // slow first response cannot land over a fast second.
  const UPDATE_SAID = {
    checking: 'Re-reading the published record…',
    unchanged: 'No newer record: this is still the published one.',
    older: 'The published file is for an earlier session than the one on screen, so it was not loaded. Nothing here changed.',
    failed: 'The published record could not be re-read. Nothing here changed.',
    invalid: 'The published file is not a record this page can read, so it was not loaded. Nothing here changed.'
  };
  let updateSeq = 0, updateBusy = false, updateSaid = '', updateOutcome = '';
  //: the bytes the page was last loaded from, so "unchanged" means the served
  //: file is identical and not merely stamped alike. A re-publish of the same
  //: session on later bars keeps its session, its published_at AND its rules
  //: digest, and moves only its numbers -- which is exactly the case a stamp of
  //: those fields cannot see, and one string comparison can.
  let rawRecord = null;
  // true when the served bytes are the record already on screen. Falls back to
  // re-serializing what is in memory for a page handed a record directly (a
  // test, a fixture), so the answer is exact either way.
  //
  // The cost of reading bytes rather than meaning: a re-publish that changed
  // only whitespace reads as a revision and is loaded. `report.write()` writes
  // one shape every time, so that is a re-run whose numbers came out the same
  // -- a re-render nobody is hurt by, and the price of never missing a
  // re-publish that DID move a number under an unchanged publish stamp.
  function sameBytes(raw) {
    if (rawRecord !== null) return raw === rawRecord;
    try { return !!current && raw === JSON.stringify(current); } catch (e) { return false; }
  }
  function renderRefresh() {
    const host = $('market-refresh');
    if (!host) return;
    // a clock re-reading repaints the bar around this control; a reader whose
    // finger is on the button keeps it
    const hadFocus = host.contains(d.activeElement);
    clear(host);
    // the control stays pressable while a check is in flight: a reader whose
    // first press is hanging must be able to try again, and the sequence number
    // below is what makes the newest answer the only one that can land
    const btn = el('button', { 'class': 'sc-btn sc-btn--ghost sc-btn--sm', type: 'button', id: 'check-updates',
      text: updateBusy ? 'Checking…' : 'Check for updates', 'data-check': updateBusy ? 'busy' : '' });
    btn.addEventListener('click', checkUpdates);
    host.appendChild(btn);
    // at rest the control says what it does and nothing more; the outcome line
    // appears only once a check has actually answered
    btn.title = 'Re-reads the published record. Nothing is scanned or graded.';
    const line = el('p', { 'class': 'ss-refresh__said', id: 'refresh-said', role: 'status', 'aria-live': 'polite',
      'data-outcome': updateOutcome || null, text: updateSaid });
    if (!updateSaid) line.hidden = true;
    host.appendChild(line);
    if (hadFocus && !btn.disabled) btn.focus({ preventScroll: true });
  }
  function saidUpdate(outcome, message) {
    updateOutcome = outcome; updateSaid = message || UPDATE_SAID[outcome] || '';
    updateBusy = outcome === 'checking';
    renderRefresh();
  }
  function checkUpdates() {
    // a second press SUPERSEDES the one in flight rather than being refused;
    // every answer carries the sequence it was asked under and a stale one is
    // dropped, so a slow first response cannot land over a fast second
    const seq = ++updateSeq;
    saidUpdate('checking');
    const src = ((w.SCStock && w.SCStock.dataUrl) || 'data.json');
    const bust = src + (src.indexOf('?') >= 0 ? '&' : '?') + 'at=' + Date.now();
    w.fetch(bust, { cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error('answered ' + r.status); return r.text(); })
      .then((raw) => { if (seq === updateSeq) applyUpdate(raw); })
      .catch(() => { if (seq === updateSeq) saidUpdate('failed'); });
  }
  // the decision, with nothing replaced until every question is answered
  function applyUpdate(raw) {
    // identical bytes: nothing is parsed, nothing is rendered, and the
    // Following shelf is not asked to observe a session it already has
    if (sameBytes(raw)) { saidUpdate('unchanged'); return; }
    let next = null;
    try { next = JSON.parse(raw); } catch (e) { saidUpdate('failed'); return; }
    if (!next || typeof next !== 'object' || next.schema_version !== 2 || !next.run ||
        !Array.isArray(next.bursts) || !next.run.session) { saidUpdate('invalid'); return; }
    if (timingFaults(next).length) { saidUpdate('invalid'); return; }
    const here = current && current.run ? current.run.session : null;
    const there = next.run.session;
    if (!here) { loadUpdate(raw, next, 'newer', 'A record loaded: ' + dateWords(there) + '.'); return; }
    if (there < here) { saidUpdate('older'); return; }
    // the same trading day, re-measured on later bars: a REVISION, not a new
    // session, and the word matters -- the reader's saved observations of that
    // date are revisions of it too, not a second day
    if (there === here) { loadUpdate(raw, next, 'revised', dateWords(there) + ' was re-published, so it was re-read: the same session on later bars, not a new one.'); return; }
    loadUpdate(raw, next, 'newer', 'A newer record loaded: ' + dateWords(there) + ' replaces ' + dateWords(here) + '.');
  }
  // What a reader keeps across a load, and what they are TOLD they lost. The
  // record changes; the reader's own place in it, their private saves and
  // their preferences do not. A comparison pair is the one thing that cannot
  // survive: it was pinned from one published record and two names remapped
  // onto a different one would be a comparison nobody made.
  function loadUpdate(raw, next, outcome, message) {
    const keep = {
      view: state.view, stage: state.stage, selected: Object.assign({}, state.selected),
      query: $('search') ? $('search').value : '', hash: String(w.location.hash || ''),
      pins: state.pins.slice(), scroll: w.pageYOffset || 0, sizeForm: openSizeForm(),
      savedOpen: savedOpen, comparing: !!(state.pins.length === 2 && $('compare') && $('compare').open)
    };
    render(next, clockPinned ? clockAt : null, keep);
    rawRecord = raw;
    const lost = [];
    if (keep.pins.length) lost.push(keep.pins.length === 2 && keep.comparing
      ? 'The comparison was closed: a pinned pair belongs to the record it was pinned from.'
      : 'The pins were cleared: a pin belongs to the record it was made in.');
    if (keep.stage && keep.selected[keep.stage] && !(model.byId[keep.selected[keep.stage]]))
      lost.push('The stock you were on is not in this record.');
    saidUpdate(outcome, [message].concat(lost).join(' '));
  }
  // an open reference-size form, so a half-typed number survives the load
  function openSizeForm() {
    const form = d.querySelector('.ss-follow__form');
    if (!form) return null;
    const host = form.closest('[data-follow-id]'), input = form.querySelector('input');
    return host && input ? { id: host.getAttribute('data-follow-id'), value: input.value,
      focused: form.contains(d.activeElement) } : null;
  }
  function restoreSizeForm(want) {
    if (!want) return;
    const host = d.querySelector('[data-follow-id="' + String(want.id).replace(/"/g, '\\"') + '"]');
    const edit = host ? host.querySelector('[data-follow-action="edit"]') : null;
    if (!edit) return;
    edit.click();
    const input = host.querySelector('.ss-follow__form input');
    if (!input) return;
    input.value = want.value;
    if (want.focused) input.focus();
  }
  SCStock.checkUpdates = checkUpdates;

  // ---------------------------------------------------------------- render
  function render(data, now, keep) {
    current = data; SCStock.data = data;
    demo = !!data.fixture;
    d.documentElement.setAttribute('data-ss-demo', demo ? 'true' : 'false');
    clockAt = now ? new Date(now) : new Date();
    clockPinned = !!now;
    copyRefused = null;
    loaded = true;
    // the bytes belong to the loader that read them; a record handed straight to
    // render() (a test, a fixture) has none, and `sameBytes()` says so
    rawRecord = null;
    av = availability(data, clockAt); st = av.pub; SCStock.state = st; SCStock.avail = av;
    model = buildModel(data); SCStock.model = model;
    SCStock.follow.setDemo(demo);
    invalidateFollow();
    unmountMap();
    closeCompare();
    disposeCompare();
    state.stage = null; state.selected = { bursts: null, 'setting-up': null }; state.query = ''; state.picksKey = null; state.detailKey = null; state.notice = '';
    // a comparison belongs to one published record: a new one clears it, and
    // the lens the reader chose is re-read against the record now on screen
    state.pins = []; state.pinAsk = null;
    STAGES.forEach((s) => { state.lens[s] = stored[s]; });
    state.sort = stored.sort || 'rank';
    $('search').value = '';
    // An update check hands back the reader's place: the stage they were on,
    // the stock if the new record still carries it, and the ticker they had
    // typed. The lens and the chart's mode and range come out of this
    // browser's own store and were never the record's to reset. The pins are
    // NOT restored -- `loadUpdate()` says so out loud instead.
    if (keep) {
      if (keep.stage) state.stage = keep.stage;
      STAGES.forEach((s) => { const id = keep.selected && keep.selected[s]; if (id && model.byId[id]) state.selected[s] = id; });
      if (keep.query) { $('search').value = keep.query; state.query = keep.query.trim().toUpperCase(); }
    }
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
    // one observation pass per loaded record, BEFORE the shelf is drawn, so
    // the card and the saved detail read the same saved history rather than
    // each re-deriving one from the record
    recoverEvidence().then(recordObservations).then(() => { renderFollowing(); followJump(); if (savedOpen) openSaved(savedOpen, false); });
    renderFollowing();
    followJump();
    renderTray();
    applyRoute(parseHash(keep && keep.hash ? keep.hash : w.location.hash), true);
    d.title = 'SpicyStock · ' + ((data.cover || {}).h1 || 'no verdict');
    if (w.SC && w.SC.reading && w.SC.reading.refresh) { try { w.SC.reading.refresh(); } catch (e) { /* optional */ } }
    d.documentElement.setAttribute('data-ss-rendered', st.state);
    d.documentElement.setAttribute('data-ss-window', av.phase);
    if (keep) { restoreSizeForm(keep.sizeForm); if (keep.scroll) w.scrollTo(0, keep.scroll); }
    watchClock();
    liveRunLog();
    return st;
  }
  SCStock.render = render;

  function failed(message) {
    // A record that would not load erases nothing of the reader's own: the
    // saved setups are in this browser, not in the record, so the shelf still
    // reads and a bookmark into one still opens. `current` is a stub rather
    // than null so every reader of it -- the shelf, the saved sheet, its
    // chart -- has the shape it indexes into.
    current = { run: {}, app: {} };
    loaded = false;
    if (clockTimer) { w.clearInterval(clockTimer); clockTimer = null; }
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
    renderFollowing(); followJump();
    const fl = $('following-list');
    if (fl && !fl.childElementCount) clear(fl).appendChild(el('div', { 'class': 'ss-following__empty', text: 'No record loaded, so nothing to observe.' }));
    clear($('record-card')).appendChild(empty('No record loaded.'));
    applyRoute(parseHash(w.location.hash), true);
    d.documentElement.setAttribute('data-ss-rendered', 'error');
  }
  function boot() {
    loadPrefs();
    loadLens();
    loadDiscover();
    wire();
    const src = (w.SCStock && w.SCStock.dataUrl) || 'data.json';
    w.fetch(src, { cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error('data.json answered ' + r.status); return r.text(); })
      // an injected clock is a PIN and the page does not move it; without one
      // the page reads the real clock and re-reads it as the day goes on
      .then((raw) => {
        const data = JSON.parse(raw);
        if (!data || data.schema_version !== 2 || !data.run) throw new Error('not a schema_version 2 record');
        render(data, w.SCStock.now ? new Date(w.SCStock.now) : null);
        rawRecord = raw;
      })
      .catch((e) => failed(String(e && e.message || e)));
  }
  if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', boot); else boot();
})(window);
