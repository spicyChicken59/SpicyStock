/* The method, one burst at a time: Bonde's momentum burst as SpicyStock runs
   it, walked over ONE SYNTHETIC series -- no ticker, no date, no record.

   Every number a caption prints is this build's. RULES names each for the
   constant it quotes and tests/test_walkthrough.py holds every value to
   src/<module>.py, so a rule that moves in Python turns this page red rather
   than leaving it stale. EXAMPLE is what the code writes for BARS -- the
   checklist's readings, the ticket and its five-session replay -- and the same
   test re-derives every one of them through scans.py, quality.py, plan.py and
   record.py, so the walkthrough prints what the code writes and nothing it
   argued. Nothing here reads the record, scans, grades or sizes: the
   walkthrough explains, the run decides. Whose number each rule is:
   knowledge/method.md (B Bonde's own words or formula, V his 2018 video, P
   this repo's provisional proxy, E third-party evidence). */
(function (w) {
  'use strict';
  const S = w.SCStock = w.SCStock || {};

  // ---- the numbers the captions quote, each named for its constant ----------
  // JSON on purpose: the test parses this block as it stands.
  const RULES = {
    "universe.min_price": 3.0,
    "scans.burst_ratio": 1.04, "scans.min_volume": 100000, "scans.dollar_move": 0.90,
    "quality.min_er": 0.40, "quality.min_r2": 0.55, "quality.max_prior_breakouts": 1,
    "quality.base_min": 3, "quality.base_max": 20, "quality.max_breakdowns": 1,
    "quality.max_giveback": 0.34, "quality.a_plus_max_giveback": 0.25,
    "quality.max_tightness": 1.0, "quality.a_plus_max_tightness": 0.70, "quality.volume_avg_sessions": 50,
    "quality.up_day_pct": 1.0, "quality.max_up_run": 1, "quality.veto_up_days": 3,
    "quality.narrow_range_pct": 2.0, "quality.narrow_norm_sessions": 20,
    "quality.min_close_pos": 0.80, "quality.a_plus_close_pos": 0.90,
    "quality.re_window": 5, "quality.re_window_long": 10,
    "quality.a_plus_max_volume_rank": 3, "quality.volume_rank_sessions": 60, "quality.min_a_plus_letters": 4,
    "breadth.yellow_ratio_10d": 2.0, "breadth.red_ratio_10d": 1.0, "breadth.red_ratio_5d": 0.5,
    "breadth.down4_alarm": 700, "breadth.reference_universe": 6500, "breadth.up50_month_hot": 20,
    "plan.default_equity": 10000, "plan.default_risk_pct": 0.5,
    "plan.default_max_position_pct": 25, "plan.default_max_open_positions": 4,
    "plan.max_stop_pct": 4.0, "plan.ideal_stop_pct": 2.0, "plan.stop_risk_multiplier": 0.5,
    "plan.entry_below_pct": 2.0, "plan.entry_above_pct": 4.0, "plan.entry_window_minutes": 30,
    "plan.sell_half_pct": 8.0, "plan.abnormal_day_pct": 10.0, "plan.gap_exit_pct": 20.0,
    "plan.trail_cents": 0.25, "plan.trail_cents_max": 0.50,
    "plan.sell_half_day": 3, "plan.no_progress_day": 3, "plan.trail_from_day": 3,
    "plan.final_exit_day": 5, "plan.no_breakeven_before_day": 5,
    "plan.gain_ceiling_pct": 15.0, "plan.extension_hazard_pct": 20.0, "plan.extension_sessions": 20,
    "plan.target_low_pct": 8.0, "plan.target_high_pct": 20.0,
    "plan.low_price_band_usd": 5.0, "plan.low_price_target_high_pct": 40.0,
    "plan.high_price_band_usd": 40.0, "plan.high_price_target_low_usd": 5.0, "plan.high_price_target_high_usd": 25.0,
    "record.scorecard_min_plans": 20
  };
  // the grader's floors for the two grades that get an order (grader.GRADE_BANDS)
  const BANDS = { "A+": 9.0, "A": 8.0 };

  // ---- one synthetic series: open, high, low, close, volume -----------------
  // Thirteen sessions of leg, eight of base, the signal, then five sessions.
  // Not a stock and not a date: drawn so the checklist reads each part as what
  // the caption calls it, which the test asserts rather than assumes.
  const BARS = [
    [13.90, 14.20, 13.75, 14.05, 1000000], [14.05, 14.55, 13.95, 14.45, 1200000],
    [14.50, 15.05, 14.40, 14.90, 1300000], [14.90, 15.00, 14.55, 14.70, 900000],
    [14.75, 15.30, 14.70, 15.20, 1400000], [15.25, 15.75, 15.15, 15.65, 1300000],
    [15.70, 16.10, 15.55, 15.95, 1100000], [15.95, 16.55, 15.90, 16.45, 1500000],
    [16.45, 16.60, 16.15, 16.30, 900000], [16.35, 16.90, 16.30, 16.80, 1400000],
    [16.85, 17.40, 16.75, 17.30, 1600000], [17.35, 17.90, 17.25, 17.80, 1500000],
    [17.85, 18.45, 17.75, 18.30, 1400000],
    [18.30, 18.40, 18.05, 18.20, 700000], [18.20, 18.35, 17.95, 18.10, 600000],
    [18.10, 18.40, 18.00, 18.30, 700000], [18.30, 18.40, 18.00, 18.05, 600000],
    [18.05, 18.25, 17.85, 18.15, 500000], [18.15, 18.40, 18.05, 18.35, 600000],
    [18.35, 18.40, 18.10, 18.20, 500000], [18.20, 18.30, 18.00, 18.10, 400000],
    [18.85, 19.38, 18.79, 19.28, 1900000],
    [19.35, 21.00, 19.30, 20.85, 2200000], [20.95, 21.25, 20.80, 21.15, 1600000],
    [21.10, 21.40, 21.00, 21.20, 1200000], [21.15, 21.45, 21.05, 21.25, 1100000],
    [21.20, 21.50, 21.10, 21.20, 1000000]
  ];
  const BURST = 21;   // the signal session's index; the five after it are the hold
  const LEG = { start: 0, end: 12 };

  // ---- what the code writes for BARS ------------------------------------------
  // Copied from the run of scans.py, quality.py, plan.py and record.py over
  // the bars above, and re-derived by the test; never edited by hand.
  const EXAMPLE = {
    "gain_pct": 6.52, "volume_vs_prior": 4.75, "grade": "A+", "score": 10.0, "a_plus_letters": 6,
    "leg_sessions": 13, "leg_gain_pct": 30.2, "er": 0.86, "r2": 0.98, "breakouts_in_move": 0,
    "base_start": 13, "base_end": 20, "base_sessions": 8, "base_high": 18.45, "base_low": 17.85,
    "breakdowns": 0, "bursts_in_base": 0, "giveback": 0.13, "tightness": 0.54, "base_volume_vs_leg": 0.45,
    "up_run": 0, "up_closes": 0, "prior_day_pct": -0.55, "prior_range_pct": 1.7,
    "close_pos": 0.83, "vs_prior_5": 1.41, "volume_rank_60": 1,
    "trigger": 19.28, "limit": 19.57, "limit_basis": "stop_line", "day2_spent_above": 20.05, "skip_below": 18.89,
    "stop": 18.79, "stop_basis": "burst_low", "stop_pct": 3.99,
    "budget_usd": 25.0, "shares": 32, "position_usd": 626.24, "risk_usd": 24.96,
    "fill": 19.35, "day1_high": 21.00, "sell_half_price": 20.90, "sell_half_shares": 16, "stop_after_day1": 20.75,
    "stop_day3": 21.00, "stop_day4": 21.05, "stop_day5": 21.10,
    "exit_price": 21.20, "exit_shares": 16, "result_pct": 9.56, "one_r": 0.56, "r": 3.04, "settled_day": 5
  };

  const INTERVAL = 6000;   // ms per step under Play; SCStock.walkthroughInterval overrides it (tests)
  const STAGGER = 60;      // ms between one revealed bar and the next (the system's --sc-motion-stagger)

  // ---- words for numbers -------------------------------------------------------
  const N = (k) => { if (!(k in RULES)) throw new Error('walkthrough quotes no rule ' + k); return RULES[k]; };
  const X = EXAMPLE;
  const thousands = (s) => s.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  const num = (v) => thousands(String(v));
  const usd = (v) => '$' + thousands(v.toFixed(2));
  const pct = (v, dec) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(dec === undefined ? 2 : dec) + '%';
  const share = (v) => String(Math.round(v * 10000) / 100) + '%';   // 0.34 -> 34%, 1 - 0.8 -> 20%
  const g = (v) => String(v);                                        // 4.0 -> 4, 0.40 -> 0.4, 1.04 -> 1.04
  const cents = (v) => String(Math.round(v * 100));
  const riskUsd = N('plan.default_equity') * N('plan.default_risk_pct') / 100;

  // ---- the steps -----------------------------------------------------------------
  // reveal: bars drawn live (the rest are ghosts) · marks: annotations on ·
  // days: sessions after the signal the stop's path is drawn through ·
  // module: the src module that owns the rule · who: whose number it is.
  const MODULES = ['universe', 'scans', 'quality', 'breadth', 'plan', 'record'];
  const STEPS = [
    { id: 'thesis', label: 'the thesis', module: 'universe', reveal: 0, marks: [], days: 0,
      title: 'The thesis',
      text: 'Stocks move in momentum bursts of ' + N('plan.sell_half_day') + '–' + N('plan.final_exit_day') + ' days of '
        + g(N('plan.target_low_pct')) + '–' + g(N('plan.target_high_pct')) + '%. A burst starts with a range-expansion day '
        + 'out of a quiet consolidation. Enter the next morning, stop under the burst, exit into strength, gate everything '
        + 'by breadth, and repeat hundreds of times a year.',
      facts: ['universe: US-listed common stocks with a session close of at least ' + usd(N('universe.min_price'))
        + '; biotech and foreign names are flagged, never excluded',
      'under ' + usd(N('plan.low_price_band_usd')) + ' a burst runs up to ' + g(N('plan.low_price_target_high_pct'))
        + '%; over ' + usd(N('plan.high_price_band_usd')) + ' he measures it in dollars, '
        + usd(N('plan.high_price_target_low_usd')) + '–' + usd(N('plan.high_price_target_high_usd'))],
      who: 'the thesis B; the price floor and the flags P' },
    { id: 'leg', label: 'L and Y · the leg', module: 'quality', reveal: LEG.end + 1, marks: ['leg'], days: 0,
      title: 'L and Y · the leg before the base',
      text: 'The move into the base went in a line: an efficiency ratio of at least ' + g(N('quality.min_er'))
        + ' or an R² of at least ' + g(N('quality.min_r2')) + ' (both for A+). A choppy leg is a veto, not a deduction. '
        + 'And the burst must be the move’s first or second breakout: at most ' + N('quality.max_prior_breakouts')
        + ' earlier 4% day since the move began (none for A+).',
      facts: ['here: ER ' + X.er + ', R² ' + X.r2 + ', over ' + X.leg_sessions + ' sessions gaining ' + pct(X.leg_gain_pct, 1),
        'earlier 4% days in this move: ' + X.breakouts_in_move],
      who: 'the ER formula B (2009), the veto B (2011), the thresholds P; Y B (2LYNCH), where the move starts P' },
    { id: 'base', label: 'C · the base', module: 'quality', reveal: BURST, marks: ['leg', 'base'], days: 0,
      title: 'C · the base',
      text: N('quality.base_min') + '–' + N('quality.base_max') + ' sessions, at most ' + N('quality.max_breakdowns')
        + ' 4% breakdown, giving back no more than ' + share(N('quality.max_giveback')) + ' of the leg, its daily ranges no wider than '
        + g(N('quality.max_tightness')) + '× the norm before it. A+ needs no breakdown, no burst inside it, giveback under '
        + share(N('quality.a_plus_max_giveback')) + ', ranges under ' + g(N('quality.a_plus_max_tightness'))
        + '×, and volume under both the leg’s and the ' + N('quality.volume_avg_sessions')
        + '-session average: a base that dried up.',
      facts: ['here: ' + X.base_sessions + ' sessions, ' + X.breakdowns + ' breakdowns, ' + X.bursts_in_base + ' bursts inside, giveback '
        + share(X.giveback) + ', ranges ' + X.tightness + '× the norm, volume ' + X.base_volume_vs_leg + '× the leg’s'],
      who: N('quality.base_min') + '–' + N('quality.base_max') + ' B (2014); ≤ ' + N('quality.max_breakdowns')
        + ' B (2LYNCH); the third P (one webinar port); tightness P; dry volume B (2016)' },
    { id: 'quiet', label: '2 and N · the day before', module: 'quality', reveal: BURST, marks: ['base', 'quiet'], days: 0,
      title: '2 and N · the day before',
      text: 'Not up two days in a row before the burst: at most ' + N('quality.max_up_run') + ' day over +' + g(N('quality.up_day_pct'))
        + '% since the last negative close (a smaller up day is flat), and ' + N('quality.veto_up_days')
        + ' rising closes in a row of any size is a veto. The day before is negative, or its range is under '
        + g(N('quality.narrow_range_pct')) + '% of its close; A+ wants both, with the range under its '
        + N('quality.narrow_norm_sessions') + '-session median.',
      facts: ['here: ' + X.up_run + ' counted up days, ' + X.up_closes + ' rising closes; the day before ' + pct(X.prior_day_pct)
        + ' with a ' + X.prior_range_pct + '% range'],
      who: '2 B (2LYNCH); the three-up veto B and V; ' + g(N('quality.narrow_range_pct')) + '% V; the median P' },
    { id: 'signal', label: 'the signal', module: 'scans', reveal: BURST + 1, marks: ['burst'], days: 0,
      title: 'The signal · the scan fires',
      text: 'The 4% burst scan: a close at least ' + g(N('scans.burst_ratio')) + '× the previous close, on more volume than the '
        + 'previous session and at least ' + num(N('scans.min_volume')) + ' shares. The Dollar scan is a second door: a close at least '
        + usd(N('scans.dollar_move')) + ' over the same day’s open on more than ' + num(N('scans.min_volume'))
        + ' shares, which can admit a day under +4%. On the bar itself: H, the close in the top '
        + share(1 - N('quality.min_close_pos')) + ' of the range and above the open (A+: the top '
        + share(1 - N('quality.a_plus_close_pos')) + '); RE, a range wider than any of the prior ' + N('quality.re_window')
        + ' sessions (A+: ' + N('quality.re_window_long') + '); VOL, above yesterday’s (A+: one of the top '
        + N('quality.a_plus_max_volume_rank') + ' of the last ' + N('quality.volume_rank_sessions')
        + '). A or A+ needs 2 and H to pass outright.',
      facts: ['here: ' + pct(X.gain_pct) + ' on ' + X.volume_vs_prior + '× yesterday’s volume; closed ' + share(X.close_pos)
        + ' of the way up its range; ' + X.vs_prior_5 + '× the widest of the prior ' + N('quality.re_window')
        + '; volume rank ' + X.volume_rank_60 + ' of ' + N('quality.volume_rank_sessions'),
      'score ' + X.score.toFixed(1) + ' of 10 with ' + X.a_plus_letters + ' checks at their A+ standard: ' + X.grade
        + ' (A+ from ' + BANDS['A+'].toFixed(1) + ' with at least ' + N('quality.min_a_plus_letters')
        + ', A from ' + BANDS.A.toFixed(1) + '; the chart reader may only lower a grade)'],
      who: 'both scans PRIMARY (4% May 2015, Dollar July 2017); H and RE V; the outright rule and the weights P' },
    { id: 'breadth', label: 'Market Monitor', module: 'breadth', reveal: BURST + 1, marks: ['burst'], days: 0,
      title: 'Market Monitor · the gate',
      text: 'Before any plan is written the market is read from Bonde’s Telechart counts over the measured universe: '
        + 'names up and down 4% on the day, up 25% in a quarter, up 25% and 50% in a month. The 10-day ratio of 4% ups '
        + 'to 4% downs sets the regime, and the regime sets the size or refuses the night.',
      facts: [{ chip: ['green', 'good'], text: '10-day ratio at or over ' + g(N('breadth.yellow_ratio_10d')) + ': full size' },
        { chip: ['yellow', 'warn'], text: 'under ' + g(N('breadth.yellow_ratio_10d')) + ', or more than ' + N('breadth.up50_month_hot')
          + ' names up 50% in a month: half size, A+ only' },
        { chip: ['red', 'danger'], text: '10-day ratio under ' + g(N('breadth.red_ratio_10d')) + ', ' + num(N('breadth.down4_alarm'))
          + '+ names down 4% today, or a 5-day ratio under ' + g(N('breadth.red_ratio_5d'))
          + ' with more down than up: no new longs, no plans' },
        'counts are scaled to the measured universe against his ' + num(N('breadth.reference_universe'))],
      who: 'the formulas B; the thresholds B, scaled to this universe P' },
    { id: 'plan', label: 'the plan', module: 'plan', reveal: BURST + 1, marks: ['plan'], days: 0,
      title: 'The plan · written before the open',
      text: 'A buy stop-limit for the next open: the buy stop at the burst close, ' + usd(X.trigger) + ', and its limit the lower of '
        + 'the close +' + g(N('plan.entry_above_pct')) + '% and the highest price at which the stop is still inside his '
        + g(N('plan.max_stop_pct')) + '% line — here ' + usd(X.limit) + '. The stop is the burst day’s low, else the bar’s '
        + 'midpoint, attached the moment the buy fills; a burst whose stop no limit above the trigger can keep inside '
        + g(N('plan.max_stop_pct')) + '% is withheld, the setup kept. Risk ' + g(N('plan.default_risk_pct'))
        + '% of equity: shares = risk ÷ (limit − stop), never more than ' + g(N('plan.default_max_position_pct'))
        + '% of equity, at most ' + N('plan.default_max_open_positions') + ' open plans.',
      facts: ['here: stop ' + usd(X.stop) + ', ' + X.stop_pct + '% under the limit — wider than his ideal '
        + g(N('plan.ideal_stop_pct')) + '%, so the ' + usd(riskUsd) + ' risk is halved to ' + usd(X.budget_usd) + ': '
        + X.shares + ' shares at the limit, ' + usd(X.position_usd),
      'skip an open under ' + usd(X.skip_below) + ' (−' + g(N('plan.entry_below_pct')) + '%, the burst failing) or over '
        + usd(X.day2_spent_above) + ' (+' + g(N('plan.entry_above_pct')) + '%, day 2 already spent); the entry is the first '
        + N('plan.entry_window_minutes') + ' minutes'],
      who: 'the stop and the sizing B; the ' + g(N('plan.max_stop_pct')) + '% line B; the limit rule, the halving and the zone P' },
    { id: 'fill', label: 'day 1', module: 'record', reveal: BURST + 2, marks: ['plan', 'fill', 'half', 'stop'], days: 1,
      title: 'Day 1 · filled at the open',
      text: 'An open at or over the buy stop and at or under the limit fills at the open: the one fill a daily bar can establish. '
        + 'If the price reaches +' + g(N('plan.sell_half_pct')) + '% on the entry day or the next, sell half and raise the stop to '
        + cents(N('plan.trail_cents')) + '–' + cents(N('plan.trail_cents_max')) + ' cents under that day’s high. A close '
        + g(N('plan.abnormal_day_pct')) + '% or more over the entry is an abnormal day: take partial profit and hold the stop '
        + 'under its high. A gap of ' + g(N('plan.gap_exit_pct')) + '% or more at an open after entry: sell at the open.',
      facts: ['here: filled at the open, ' + usd(X.fill) + '; the high ' + usd(X.day1_high) + ' reached +' + g(N('plan.sell_half_pct'))
        + '% (' + usd(X.sell_half_price) + '): ' + X.sell_half_shares + ' of ' + X.shares + ' sold, the stop raised to '
        + usd(X.stop_after_day1)],
      who: 'the exits B (2018); the fill rule P' },
    { id: 'third', label: 'day 3', module: 'plan', reveal: BURST + 4, marks: ['half', 'stop'], days: 3,
      title: 'Day 3 · the close',
      text: 'If half is still held at day ' + N('plan.sell_half_day') + '’s close, sell at least half then, in whole shares. A close '
        + 'at or under the entry on day ' + N('plan.no_progress_day') + ' is no follow-through: out entirely. From day '
        + N('plan.trail_from_day') + ' the stop trails each day’s low and never moves down. There is no break-even move before day '
        + N('plan.no_breakeven_before_day') + '.',
      facts: ['here: half was sold on day 1, so day 3 sells nothing; the stop trails to ' + usd(X.stop_day3)],
      who: 'the exits B; the trail P (a reading of “after 3rd day keep moving stop to low of day”); no break-even E' },
    { id: 'trail', label: 'days 4–5', module: 'plan', reveal: BARS.length, marks: ['half', 'stop', 'exit'], days: 5,
      title: 'Days 4–5 · trail, then out',
      text: 'The stop follows each day’s low. Day ' + N('plan.final_exit_day') + ' is the exit, at the close, whatever the price is '
        + 'doing. Two hazards halve the size and never veto: a burst day of ' + g(N('plan.gain_ceiling_pct'))
        + '% or more, and a close ' + g(N('plan.extension_hazard_pct')) + '% over its ' + N('plan.extension_sessions')
        + '-session average.',
      facts: ['here: the stop trails to ' + usd(X.stop_day4) + ', then ' + usd(X.stop_day5) + '; the remaining ' + X.exit_shares
        + ' sold at the day-' + X.settled_day + ' close, ' + usd(X.exit_price)],
      who: 'the hold B; the ' + g(N('plan.gain_ceiling_pct')) + '% hazard E (the one event study’s worst cell); the extension hazard P' },
    { id: 'record', label: 'the record', module: 'record', reveal: BARS.length, marks: ['fill', 'sale', 'exit', 'stop', 'r'], days: 5,
      title: 'The record',
      text: 'Every published plan is replayed from daily bars alone, as a model: a fill is booked only at the next open, inside '
        + 'the ticket. A trigger crossed after the open, an open past the limit or under the skip line that could still have '
        + 'filled, or a fill-day low under the stop is uncertain — no fill, no R, counted by reason. One R is the fill minus '
        + 'the published stop, on the whole position; every sale is weighted by the shares it sold; everything settles by day '
        + N('plan.final_exit_day') + '. Rates are printed only from ' + N('record.scorecard_min_plans') + ' settled plans.',
      facts: ['here: one R = ' + usd(X.fill) + ' − ' + usd(X.stop) + ' = ' + usd(X.one_r) + ' on ' + X.shares + ' shares; '
        + X.sell_half_shares + ' sold at ' + usd(X.sell_half_price) + ' and ' + X.exit_shares + ' at ' + usd(X.exit_price) + ': '
        + (X.r > 0 ? '+' : '') + X.r.toFixed(2) + 'R, settled on day ' + X.settled_day],
      who: 'the replay P; the hold B' }
  ];

  // the stop in force at the close of day k (k = 0: the published stop)
  const STOP_AFTER = [X.stop, X.stop_after_day1, X.stop_after_day1, X.stop_day3, X.stop_day4, X.stop_day5];
  // the level labels a step puts in the gutter, pure: the geometry adds the y
  function labelTexts(step, narrow) {
    const out = [], days = step.days, on = (id) => step.marks.indexOf(id) >= 0;
    const add = (kind, price, text) => out.push({ kind, price, text });
    if (on('plan') && !days) {
      add('day2', X.day2_spent_above, narrow ? 'skip > ' + usd(X.day2_spent_above) : 'too extended over ' + usd(X.day2_spent_above));
      add('limit', X.limit, 'limit ' + usd(X.limit));
      add('trigger', X.trigger, narrow ? 'buy ' + usd(X.trigger) : 'buy stop ' + usd(X.trigger));
      add('skip', X.skip_below, narrow ? 'skip < ' + usd(X.skip_below) : 'burst failing under ' + usd(X.skip_below));
      add('stop', X.stop, 'stop ' + usd(X.stop));
    }
    if (days) {
      if (on('fill')) add('fill', X.fill, narrow ? 'fill ' + usd(X.fill) : 'filled at the open ' + usd(X.fill));
      if (on('half')) add('half', X.sell_half_price, '+' + g(N('plan.sell_half_pct')) + '% ' + (narrow ? '' : '· sell half ') + usd(X.sell_half_price));
      if (on('sale')) add('sale', X.sell_half_price, narrow ? X.sell_half_shares + ' @ ' + usd(X.sell_half_price) : 'sold ' + X.sell_half_shares + ' at ' + usd(X.sell_half_price));
      if (on('exit')) add('exit', X.exit_price, step.id === 'record' ? (narrow ? X.exit_shares + ' @ ' + usd(X.exit_price) : 'sold ' + X.exit_shares + ' at ' + usd(X.exit_price)) : (narrow ? 'out ' + usd(X.exit_price) : 'day ' + X.settled_day + ' · out ' + usd(X.exit_price)));
      if (on('stop')) {
        if (step.id === 'record') add('stop', X.stop, narrow ? 'stop ' + usd(X.stop) : 'one R from ' + usd(X.stop));
        else add('stop', STOP_AFTER[days], (narrow ? 'stop ' : days === 1 ? 'stop raised ' : 'stop trails ') + usd(STOP_AFTER[days]));
      }
    }
    return out;
  }
  // the gutter is as wide as its widest label, so no label leaves the chart at any width
  const CHAR = 6.5;   // the widest a mono glyph gets at the chart's 10.5px, fallback stack included
  const longest = (narrow) => STEPS.reduce((m, s) => labelTexts(s, narrow).reduce((mm, l) => Math.max(mm, l.text.length), m), 0);

  // ---- geometry (pure) ------------------------------------------------------------
  function geometry(width) {
    const W = Math.max(300, Math.round(width)), narrow = W < 560;
    const gutter = Math.ceil(longest(narrow) * CHAR) + 16, H = narrow ? 292 : 320;
    // a phone's slots are too narrow for four words in one row: the axis takes two
    const axisRows = narrow ? 2 : 1, axisBand = 20 + 14 * (axisRows - 1);
    const plot = { left: 6, right: W - gutter, top: 16, bottom: H - 50 - axisBand };
    const vol = { top: H - 36 - axisBand, bottom: H - axisBand - 10 };
    plot.width = plot.right - plot.left; plot.height = plot.bottom - plot.top;
    let lo = Infinity, hi = -Infinity, vmax = 0;
    BARS.forEach((b) => { lo = Math.min(lo, b[2]); hi = Math.max(hi, b[1]); vmax = Math.max(vmax, b[4]); });
    const pad = (hi - lo) * 0.05;
    lo -= pad; hi += pad;
    const slot = plot.width / BARS.length;
    const x = (i) => plot.left + (i + 0.5) * slot;
    const y = (p) => plot.top + (hi - p) / (hi - lo) * plot.height;
    const vy = (v) => vol.bottom - v / vmax * (vol.bottom - vol.top);
    return { W, H, narrow, gutter, plot, vol, slot, body: Math.max(3, Math.min(12, slot * 0.62)), domain: { lo, hi }, x, y, vy, axisY: H - 10, axisRows };
  }
  const r1 = (v) => Math.round(v * 10) / 10;

  // ---- the chart --------------------------------------------------------------------
  // Every mark carries a tone SLOT through --sc-tone; the sheet (app.css) keeps
  // every colour declaration, so a theme flip re-resolves it with no script.
  const tone = (slot) => '--sc-tone:var(--sc-' + slot + ')';
  const LEVEL_TONE = { stop: 'danger', trigger: 'warn', limit: 'chart-emphasis', skip: 'chart-context', day2: 'chart-context', half: 'good', fill: 'accent', sale: 'good', exit: 'good' };
  const LEVEL_DASH = { stop: 'dashed', trigger: 'dotted', skip: 'dashed', day2: 'dashed', half: 'dashed', exit: 'dashed' };

  function buildSvg(SC, width, ids) {
    const G = geometry(width), plot = G.plot;
    const svg = SC.svg('svg', { 'class': 'ss-walk__svg', viewBox: '0 0 ' + G.W + ' ' + G.H, width: G.W, height: G.H,
      role: 'img', 'aria-labelledby': ids.title + ' ' + ids.desc });
    svg.appendChild(SC.svg('title', { id: ids.title }, ['Synthetic daily candles of one momentum burst']));
    svg.appendChild(SC.svg('desc', { id: ids.desc }, ['A linear leg up, a tight base, a quiet day, a burst day up ' + pct(X.gain_pct)
      + ' on ' + X.volume_vs_prior + ' times the previous volume, then five sessions with the exits the rules decide.']));
    const grid = SC.svg('g');
    for (let k = 1; k <= 3; k++) { const gy = r1(plot.top + plot.height * k / 4); grid.appendChild(SC.svg('line', { 'class': 'ss-walk__grid', x1: plot.left, x2: plot.right, y1: gy, y2: gy })); }
    grid.appendChild(SC.svg('line', { 'class': 'ss-walk__grid', x1: plot.left, x2: plot.right, y1: G.vol.bottom, y2: G.vol.bottom }));
    svg.appendChild(grid);
    const under = SC.svg('g'); svg.appendChild(under);       // bands and boxes, under the candles
    const bars = [];
    const barsG = SC.svg('g'); svg.appendChild(barsG);
    BARS.forEach((b, i) => {
      const cx = r1(G.x(i)), up = b[3] >= b[0];
      const top = r1(G.y(Math.max(b[0], b[3]))), h = Math.max(1.5, r1(G.y(Math.min(b[0], b[3])) - top));
      const node = SC.svg('g', { 'class': 'ss-walk__bar is-ghost', 'data-index': i, 'data-dir': up ? 'up' : 'down', style: tone('chart-context') }, [
        SC.svg('line', { 'class': 'ss-walk__wick', x1: cx, x2: cx, y1: r1(G.y(b[1])), y2: r1(G.y(b[2])) }),
        SC.svg('rect', { 'class': 'ss-walk__candle' + (up ? '' : ' is-filled'), x: r1(cx - G.body / 2), y: top, width: r1(G.body), height: h, rx: 1 }),
        SC.svg('rect', { 'class': 'ss-walk__vol', x: r1(cx - G.body / 2), y: r1(G.vy(b[4])), width: r1(G.body), height: r1(G.vol.bottom - G.vy(b[4])) })
      ]);
      barsG.appendChild(node); bars.push({ node, up, burst: i === BURST });
    });
    const over = SC.svg('g'); svg.appendChild(over);         // lines, rings, flags, dots, pills
    const gutter = SC.svg('g', { 'class': 'ss-walk__gutter' }); svg.appendChild(gutter);
    // the axis words under the volume pane
    // row 0 is the lower row; a phone puts the leg and the burst on the upper one
    const ax = (i, text, anchor, dx, row) => svg.appendChild(SC.svg('text', { 'class': 'ss-walk__axis', x: r1(G.x(i) + (dx || 0)), y: G.axisY - 14 * (row || 0), 'text-anchor': anchor || 'middle' }, [text]));
    const hold = N('plan.final_exit_day');
    ax((LEG.start + LEG.end) / 2, G.narrow ? 'leg' : 'the leg', null, 0, G.narrow ? 1 : 0); ax((X.base_start + X.base_end) / 2, G.narrow ? 'base' : 'the base');
    // on a phone the words alternate rows so none touches; on a desktop the
    // burst's word ends at its bar's edge so D1 has its own
    if (G.narrow) { ax(BURST, 'burst', null, 0, 1); ax(BURST + (hold + 1) / 2, 'hold'); }
    else { ax(BURST, 'burst', 'end', G.slot / 2 - 3); for (let dday = 1; dday <= hold; dday++) ax(BURST + dday, 'D' + dday); }
    svg.appendChild(SC.svg('text', { 'class': 'ss-walk__axis', x: plot.left, y: G.vol.top - 3, 'text-anchor': 'start' }, ['volume']));

    // -- the annotations, built once and switched on per step -------------------
    const marks = {};
    const mark = (id, node) => { node.setAttribute('class', 'ss-walk__mark'); node.setAttribute('data-mark', id); marks[id] = node; return node; };
    const pill = (cx, cy, text) => {
      const wd = text.length * 6.4 + 14, x0 = Math.max(plot.left + 2, Math.min(plot.right - wd - 2, cx - wd / 2));
      return SC.svg('g', null, [
        SC.svg('rect', { 'class': 'ss-walk__pill', x: r1(x0), y: r1(cy - 9), width: r1(wd), height: 18, rx: 9 }),
        SC.svg('text', { 'class': 'ss-walk__pill-text', x: r1(x0 + wd / 2), y: r1(cy + 3.5), 'text-anchor': 'middle' }, [text])
      ]);
    };
    const half = G.slot / 2, burstLeft = r1(G.x(BURST) - half), burstRight = r1(G.x(BURST) + half);
    // L: the leg, a dashed line from its first low to its high
    over.appendChild(mark('leg', SC.svg('g', { style: tone('chart-emphasis') }, [
      SC.svg('line', { 'class': 'ss-walk__line ss-walk__line--dashed', x1: r1(G.x(LEG.start)), y1: r1(G.y(BARS[LEG.start][2])), x2: r1(G.x(LEG.end)), y2: r1(G.y(BARS[LEG.end][1])) }),
      pill(G.x(4), G.y(BARS[9][1]) - 14, G.narrow ? 'L · the leg' : 'L · a linear leg')
    ])));
    // C: the base, the box the checklist measured
    under.appendChild(mark('base', SC.svg('g', { style: tone('chart-context') }, [
      SC.svg('rect', { 'class': 'ss-walk__box', x: r1(G.x(X.base_start) - half), y: r1(G.y(X.base_high)), width: r1(G.x(X.base_end) - G.x(X.base_start) + G.slot), height: r1(G.y(X.base_low) - G.y(X.base_high)), rx: 3 }),
      pill(G.x((X.base_start + X.base_end) / 2), G.y(X.base_high) - 14, G.narrow ? 'C · the base' : 'C · a tight base, dry volume')
    ])));
    // 2 and N: the day before
    over.appendChild(mark('quiet', SC.svg('g', { style: tone('chart-emphasis') }, [
      SC.svg('circle', { 'class': 'ss-walk__ring', cx: r1(G.x(BURST - 1)), cy: r1(G.y(BARS[BURST - 1][3])), r: 11 }),
      pill(G.x(BURST - 1), G.y(X.base_low) + 20, '2 · N')
    ])));
    // the signal session
    under.appendChild(mark('burst', SC.svg('g', { style: tone('accent') }, [
      SC.svg('rect', { 'class': 'ss-walk__band', x: burstLeft, y: plot.top, width: r1(G.slot), height: r1(G.vol.bottom - plot.top) }),
      pill(G.x(BURST), G.y(BARS[BURST][1]) - 16, pct(X.gain_pct) + ' · ' + X.volume_vs_prior + '× vol')
    ])));
    // the ticket's levels, from the signal bar to the right edge
    const level = (kind, price, x1) => SC.svg('line', { 'class': 'ss-walk__line' + (LEVEL_DASH[kind] ? ' ss-walk__line--' + LEVEL_DASH[kind] : ''), 'data-level': kind,
      style: tone(LEVEL_TONE[kind]), x1: x1 === undefined ? burstLeft : x1, x2: plot.right, y1: r1(G.y(price)), y2: r1(G.y(price)) });
    over.appendChild(mark('plan', SC.svg('g', null, [
      SC.svg('rect', { 'class': 'ss-walk__band', style: tone('chart-emphasis'), x: burstRight, y: r1(G.y(X.limit)), width: r1(plot.right - burstRight), height: Math.max(2, r1(G.y(X.trigger) - G.y(X.limit))) }),
      level('day2', X.day2_spent_above), level('skip', X.skip_below), level('limit', X.limit), level('trigger', X.trigger), level('stop', X.stop)
    ])));
    // day 1: the fill at the open, the +8% level
    const fillX = r1(G.x(BURST + 1)), fillY = r1(G.y(X.fill));
    over.appendChild(mark('fill', SC.svg('g', { style: tone('accent') }, [
      SC.svg('path', { 'class': 'ss-walk__flag', d: 'M' + (fillX - 8) + ',' + (fillY - 5) + 'L' + fillX + ',' + fillY + 'L' + (fillX - 8) + ',' + (fillY + 5) + 'Z' })
    ])));
    over.appendChild(mark('half', SC.svg('g', null, [level('half', X.sell_half_price, r1(G.x(BURST + 1) - half))])));
    // the stop's path: one polyline whose reach depends on the step
    const stopPath = SC.svg('path', { 'class': 'ss-walk__path', style: tone('danger'), d: '' });
    over.appendChild(mark('stop', SC.svg('g', null, [stopPath])));
    const sale = (i, price) => SC.svg('g', { style: tone('good') }, [SC.svg('circle', { 'class': 'ss-walk__dot', cx: r1(G.x(i)), cy: r1(G.y(price)), r: 4.5 })]);
    over.appendChild(mark('sale', sale(BURST + 1, X.sell_half_price)));
    over.appendChild(mark('exit', sale(BURST + N('plan.final_exit_day'), X.exit_price)));
    over.appendChild(mark('r', pill(plot.left + 80, plot.top + 14, (X.r > 0 ? '+' : '') + X.r.toFixed(2) + 'R · settled day ' + X.settled_day)));

    // the stop through `days` sessions after the signal: the published stop until
    // day 1's close, the raised stop from there, the trail from day 3
    function reach(days) {
      if (!days) { stopPath.setAttribute('d', ''); return; }
      let px = burstLeft, py = r1(G.y(X.stop)), dd = 'M' + px + ',' + py;
      for (let k = 1; k <= days; k++) {
        const right = r1(G.x(BURST + k) + half), yk = r1(G.y(STOP_AFTER[k]));
        dd += 'H' + right;
        if (yk !== py) { dd += 'V' + yk; py = yk; }
      }
      stopPath.setAttribute('d', dd);
    }
    // the gutter: one label per level in force, spread apart, each with a leader
    function relabel(step) {
      while (gutter.firstChild) gutter.removeChild(gutter.firstChild);
      const items = labelTexts(step, G.narrow).map((l) => Object.assign({ y: r1(G.y(l.price)) }, l));
      if (!items.length) return;
      const spread = SC.spreadLabels(items.map((it) => ({ y: it.y, it })), { gap: 14, min: plot.top + 7, max: G.vol.bottom - 4 });
      spread.forEach((s) => {
        const it = s.it, lx = plot.right + 8;
        gutter.appendChild(SC.svg('path', { 'class': 'ss-walk__leader', style: tone(LEVEL_TONE[it.kind]), d: 'M' + plot.right + ',' + it.y + 'L' + (plot.right + 5) + ',' + it.y + 'L' + (lx - 2) + ',' + r1(s.y) }));
        gutter.appendChild(SC.svg('text', { 'class': 'ss-walk__gutter-text', 'data-label': it.kind, x: lx, y: r1(s.y + 3.5), 'text-anchor': 'start' }, [it.text]));
      });
    }
    return { svg, bars, marks, reach, relabel, G };
  }

  // ---- the walkthrough ------------------------------------------------------------------
  let mounted = 0;
  function mount(host, opts) {
    opts = opts || {};
    const SC = w.SC, d = w.document;
    if (!host || !SC || !SC.svg) return null;
    const el = SC.el, seq = ++mounted, ids = { title: 'ss-walk-title-' + seq, desc: 'ss-walk-desc-' + seq, caption: 'ss-walk-caption-' + seq };
    const interval = Math.max(200, Number(opts.interval) || INTERVAL);
    const reduced = () => !!(w.matchMedia && w.matchMedia('(prefers-reduced-motion: reduce)').matches);
    let step = 0, shown = 0, timer = null, view = null, drawnWidth = 0;

    // -- the DOM ------------------------------------------------------------------------
    const chips = MODULES.map((m) => el('li', null, el('span', { 'class': 'sc-chip sc-chip--neutral', 'data-module': m, title: 'src/' + m + '.py', text: m })));
    const chart = el('div', { 'class': 'ss-walk__chart' });
    const back = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', 'data-walk': 'back', 'aria-label': 'Previous step', text: 'Back' });
    const play = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', 'data-walk': 'play', text: 'Play' });
    const next = el('button', { 'class': 'sc-btn sc-btn--secondary sc-btn--sm', type: 'button', 'data-walk': 'next', 'aria-label': 'Next step', text: 'Next' });
    const count = el('span', { 'class': 'ss-walk__count', 'data-walk': 'count', 'aria-live': 'polite' });
    const stage = el('div', { 'class': 'ss-walk__stage', tabindex: '0', role: 'group', 'aria-roledescription': 'animated walkthrough',
      'aria-label': 'One momentum burst, step by step: arrow keys move between steps, space plays and pauses', 'aria-describedby': ids.caption }, [
      el('ul', { 'class': 'ss-walk__modules', 'aria-label': 'Which module owns this step' }, chips),
      chart,
      el('div', { 'class': 'ss-walk__controls' }, [back, play, next, count])
    ]);
    const index = STEPS.map((s, i) => el('li', null, el('button', { 'class': 'sc-tab sc-tab--case', type: 'button', 'data-walk-step': s.id, 'aria-current': 'false' }, [
      el('span', { 'class': 'ss-walk__n', text: String(i + 1) }), el('span', { text: s.label })
    ])));
    const capEyebrow = el('p', { 'class': 'sc-eyebrow', 'data-walk': 'eyebrow' });
    const capTitle = el('h4', { 'data-walk': 'title' });
    const capText = el('p', { 'data-walk': 'text' });
    const facts = el('ul', { 'class': 'ss-walk__facts', 'data-walk': 'facts' });
    const who = el('p', { 'class': 'sc-note ss-walk__who', 'data-walk': 'who' });
    const caption = el('div', { 'class': 'ss-walk__caption', id: ids.caption, 'aria-live': 'polite' }, [capEyebrow, capTitle, capText, facts, who]);
    const side = el('div', { 'class': 'ss-walk__side' }, [el('ol', { 'class': 'ss-walk__index', 'aria-label': 'Steps' }, index)]);
    const root = el('div', { 'class': 'ss-walk', 'data-walk-root': '' }, [stage, side, caption]);
    host.appendChild(root);
    // every chart owes a table twin: the bars, readable without the picture
    SC.tableTwin(host, {
      caption: 'The synthetic bars the walkthrough is drawn over',
      summary: 'The synthetic bars as a table',
      head: ['session', 'open', 'high', 'low', 'close', 'volume'],
      rows: BARS.map((b, i) => [i === BURST ? 'burst' : i > BURST ? 'D' + (i - BURST) : i <= LEG.end ? 'leg ' + (i + 1) : 'base ' + (i - LEG.end),
        b[0].toFixed(2), b[1].toFixed(2), b[2].toFixed(2), b[3].toFixed(2), num(b[4])])
    });
    const twin = host.querySelector('.sc-details');
    if (twin) { twin.setAttribute('data-walk', 'table'); const rows = twin.querySelectorAll('tbody tr'); if (rows[BURST]) rows[BURST].setAttribute('data-burst', 'true'); }

    // -- painting -------------------------------------------------------------------------
    function reveal(n, animate) {
      const stagger = animate && !reduced();
      view.bars.forEach((b, i) => {
        const live = i < n;
        b.node.classList.toggle('is-ghost', !live);
        b.node.setAttribute('style', tone(live ? (b.up ? 'good' : 'danger') : 'chart-context'));
        b.node.style.transitionDelay = (stagger && live && i >= shown) ? ((i - shown) * STAGGER) + 'ms' : '0ms';
      });
      shown = n;
    }
    function paint(animate) {
      const s = STEPS[step];
      if (view) {
        reveal(s.reveal, animate);
        Object.keys(view.marks).forEach((id) => view.marks[id].classList.toggle('is-on', s.marks.indexOf(id) >= 0));
        view.reach(s.days);
        view.relabel(s);
        view.svg.setAttribute('data-step', s.id);
      }
      chips.forEach((li) => { const c = li.firstChild; const on = c.getAttribute('data-module') === s.module; c.className = 'sc-chip ' + (on ? 'sc-chip--brand' : 'sc-chip--neutral'); c.setAttribute('aria-current', on ? 'true' : 'false'); });
      index.forEach((li, i) => li.firstChild.setAttribute('aria-current', i === step ? 'step' : 'false'));
      capEyebrow.textContent = 'step ' + (step + 1) + ' of ' + STEPS.length + ' · ' + s.module;
      capTitle.textContent = s.title;
      capText.textContent = s.text;
      while (facts.firstChild) facts.removeChild(facts.firstChild);
      s.facts.forEach((f) => {
        if (typeof f === 'string') facts.appendChild(el('li', { text: f }));
        else facts.appendChild(el('li', null, [el('span', { 'class': 'sc-chip sc-chip--' + f.chip[1], text: f.chip[0] }), d.createTextNode(f.text)]));
      });
      who.textContent = 'Source: ' + s.who;
      count.textContent = 'Step ' + (step + 1) + ' of ' + STEPS.length;
      back.setAttribute('aria-disabled', step === 0 ? 'true' : 'false');
      next.setAttribute('aria-disabled', step === STEPS.length - 1 ? 'true' : 'false');
      root.setAttribute('data-step', String(step + 1));
    }
    function draw() {
      const width = chart.clientWidth || 0;
      if (!width) return;          // hidden: the observer redraws when the view shows
      drawnWidth = width;
      view = buildSvg(SC, width, ids);
      while (chart.firstChild) chart.removeChild(chart.firstChild);
      chart.appendChild(view.svg);
      shown = 0;
      paint(false);
    }
    function go(n, animate) {
      step = Math.max(0, Math.min(STEPS.length - 1, n));
      paint(animate !== false);
      if (step === STEPS.length - 1) stopPlay();
    }
    function stopPlay() { if (timer) { w.clearInterval(timer); timer = null; } play.textContent = 'Play'; play.setAttribute('aria-pressed', 'false'); }
    function startPlay() {
      if (step === STEPS.length - 1) go(0);
      timer = w.setInterval(() => go(step + 1), interval);
      play.textContent = 'Pause'; play.setAttribute('aria-pressed', 'true');
    }
    play.addEventListener('click', () => { if (timer) stopPlay(); else startPlay(); });
    next.addEventListener('click', () => { stopPlay(); go(step + 1); });
    back.addEventListener('click', () => { stopPlay(); go(step - 1); });
    index.forEach((li, i) => li.firstChild.addEventListener('click', () => { stopPlay(); go(i); }));
    stage.addEventListener('keydown', (e) => {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      if (e.key === 'ArrowRight') { stopPlay(); go(step + 1); e.preventDefault(); }
      else if (e.key === 'ArrowLeft') { stopPlay(); go(step - 1); e.preventDefault(); }
      else if (e.key === 'Home') { stopPlay(); go(0); e.preventDefault(); }
      else if (e.key === 'End') { stopPlay(); go(STEPS.length - 1); e.preventDefault(); }
      else if (e.key === ' ' && e.target === e.currentTarget) { if (timer) stopPlay(); else startPlay(); e.preventDefault(); }
    });
    // a tab put away stops playing; the reader resumes it
    d.addEventListener('visibilitychange', () => { if (d.hidden) stopPlay(); });
    // the width the chart is drawn at is the host's, re-read when it changes --
    // including from nothing, when the Method view is first shown
    let pending = null;
    const redraw = () => {
      if (pending) return;
      const later = w.requestAnimationFrame ? w.requestAnimationFrame.bind(w) : (fn) => w.setTimeout(fn, 16);
      pending = later(() => { pending = null; const width = chart.clientWidth; if (width && Math.abs(width - drawnWidth) > 1) draw(); });
    };
    if (w.ResizeObserver) { const ro = new w.ResizeObserver(redraw); ro.observe(chart); }
    else w.addEventListener('resize', redraw);
    draw();
    paint(false);
    const handle = { go: (n) => go(n), step: () => step, play: startPlay, pause: stopPlay, playing: () => !!timer, root };
    S.walkthroughHandle = handle;
    return handle;
  }

  S.walkthrough = { RULES, BANDS, BARS, BURST, LEG, EXAMPLE, STEPS, MODULES, INTERVAL, geometry, mount };
})(window);
