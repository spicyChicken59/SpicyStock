/* Reading aids only. Never scores a stock or changes a recorded verdict.
   Measurement definitions: src/quality.py and src/watchlist.py.
   Rationale and authorship: knowledge/method.md, knowledge/strategy.md,
   knowledge/reaction-discovery.md. Rules always belong to the loaded record. */
(function (w) {
  'use strict';
  const S = w.SCStock = w.SCStock || {};
  const terms = {
    journey: ['Start with the market, then a stock', 'SpicyStock is a published research report on short-term momentum setups. Check its session and market filter, choose a candidate, inspect its evidence, then read the conditional plan or waiting reason. Compare and save are optional. It does not place trades, read live prices or know your holdings.'],
    discovery: ['Why a stock is shown', 'Discovery finds candidates using this record’s scan rules. A 4% breakout compares the close with the previous close; a Dollar breakout compares the close with the same session’s open. Either can admit a candidate. Discovery is separate from its grade and from permission to offer a ticket.'],
    momentum: ['Momentum burst', 'The method looks for a short price move emerging from a quieter base. “Bursts” is the discovery list, including Dollar candidates; being listed does not establish that the range-expansion checklist item passed or that a trade is available.'],
    anticipation: ['Setting up / anticipation', 'A watch list of quieter stocks within an established upward move. The recorded box and conditional trigger describe what would need to happen. These stocks are measured rather than given the burst checklist’s grade; a quiet day alone is not an entry.'],
    grade: ['A-quality and grade', 'A / A+ are categories from the recorded weighted checklist and any permitted chart-reader downgrade. A grade is not a probability, expected return or order. An A-grade need not pass every item. Market, evidence, budget and entry timing can still prevent a ticket.'],
    checklist: ['Read one criterion at a time', 'Pass means this item met its recorded criterion. Fail names a weakness; only an explicit veto is an outright method refusal. Partial is intermediate evidence. Not measured means unknown, not zero or failure. The stored verdict remains authoritative even when displayed measurements were rounded.'],
    market: ['Market breadth and regime', 'Breadth counts participation across the measured stock population. The up/down ratio compares counts of qualifying rises and falls over the named sessions. GREEN permits normal model sizing, YELLOW reduces it, RED refuses new longs. These are market filters; a favourable filter cannot create a ticket or reopen an expired window.'],
    data: ['Publication, session and coverage', '“Data through” names the measured session; “published” names when the report was written. This is a recorded snapshot, not live prices. Coverage says which intended stocks had usable inputs. Missing or stale inputs are unknowns, not measured non-matches. Publication status and the separate entry-window status answer different questions.'],
    base: ['Base / consolidation', 'The recorded pause after an earlier advance, called the prior leg. Its dated box shows the measured range. Giveback compares the base’s high-to-low depth with the rise from the prior leg’s low to the base high. Tightness compares average daily range percentages with the preceding reference period.'],
    prior: ['Prior session', 'The preceding trading observation, not the previous calendar day. A negative prior day means its close fell versus the close before it. That can satisfy a pause criterion even though the day is shown as a falling price.'],
    volume: ['Volume ratio', 'A burst’s headline and map ratio compare its session volume with the preceding session. Checklist average-volume and rank comparisons use their own recorded periods. Setting up compares two volume averages. A chart’s moving average is a visual reference, not a substitute for any of these criteria.'],
    range: ['Range expansion', 'Daily range percentage is (high − low) ÷ that session’s close × 100. The checklist compares the burst’s range percentage with the largest in a recorded prior window. Ordinary and A+ use different windows. This describes measured expansion, not the size of a future move.'],
    ticket: ['Ticket versus conditional plan', 'A plan records conditions and levels. A ticket adds the published order terms and model quantity. “Ticket” on a card means one was published, not that it is currently offered, submitted or filled. Read the selected stock’s entry status and dated window before interpreting it. SpicyStock sends no orders.'],
    trigger: ['Trigger, limit and protective stop', 'The buy-stop trigger activates a conditional entry; its limit is the highest price that order permits. The protective stop is a separate exit condition after a fill. Crossing a trigger does not prove a fill, and a stop-market exit can fill beyond its stop price. Read the record’s exact terms.'],
    size: ['Model size', 'Suggested shares come from the report’s configured sizing assumptions, evaluated at the ticket’s limit. They are not based on your balance, holdings, buying power or actual fill. Saving or following a plan does not submit this quantity anywhere.'],
    window: ['Entry window', 'The dated session and time interval in which this record permits a new entry. A published ticket remains inspectable after the window ends, but is no longer offered. Publication problems and the market filter may block entry even while the scheduled window is open.'],
    r: ['R: a unit of model risk', 'One R is the public model’s initial per-share risk from its recorded fill to the published protective stop. Outcomes expressed in R compare model gains or losses with that starting risk. They are not personal P&L, a promise, or a live account measurement.'],
    provenance: ['Provenance / where the evidence came from', 'The record’s identity, source bars, rules version and original chart-reader response make its evidence inspectable. Chart-reader commentary is unverified interpretation; recorded checklist fields govern criteria and the published plan defines order terms. Source detail lets you check a claim, not certify future performance.'],
    saved: ['Saved setup', 'A browser-local bookmark of the exact published setup. A saved confirmation means the save worked; it is not a positive assessment of the stock. “I followed this plan” records your choice, not an order, a fill or your quantity. Later published observations are research, not account returns.'],
    outcomes: ['Public-model outcomes', 'HOLD means the recorded model plan remains open under its rules. STOPPED means its model stop was reached under the bar-based assumptions. Other outcomes likewise describe this public model. They do not say what you own or tell you what happened in your account; an uncertain fill stays uncertain.'],
    chart: ['Read the chart marks', 'The horizontal axis is recorded sessions; the price axis is dollars and volume bars show shares. Candles have an open-to-close body and low-to-high wick: hollow when close ≥ open, filled when close < open. Candle direction differs from a headline gain versus the previous close. Setup uses blue up/gray down, with its signal candle and volume bar blue regardless of direction; Candles uses green/red; Line joins closes. Evidence highlights and plan levels are not forecasts.'],
    map: ['Read the discovery map', 'Horizontal position is the session’s close-to-previous-close gain. Vertical position is volume divided by the prior session’s volume, on a compressed scale: equal pixel distances are not equal ratio differences. Filled circles mean chart-reader provenance, hollow circles checklist alone, dashed circles unknown source. The selected point uses an accent fill and outline regardless of provenance; check its source label. No position predicts returns.'],
    compare: ['What Compare helps you inspect', 'Compare aligns two stocks from the same stage and published session. Marked rows show recorded differences, not which stock is better. Each chart has its own price scale and dates. Use the differences to choose evidence to inspect, then open a setup for its entry status and complete conditions.']
  };
  const number = x => typeof x === 'number' && Number.isFinite(x);
  const val = (x, unit = '') => number(x) ? String(x) + unit : 'not measured';
  const pc = x => number(x) ? String(Number((x * 100).toPrecision(15))) + '%' : 'not measured';
  const bool = (x, yes, no) => x === true ? yes : x === false ? no : 'not measured';
  const clean = s => String(s || '').replace(/(\d+)\.0+(?!\d)/g, '$1').replace(/\s+/g, ' ').trim();
  const titles = {
    two_days: 'Was the prior run-up short enough?', linearity: 'Was the prior advance orderly?',
    young_trend: 'Is this an early breakout in the move?', narrow_or_negative: 'Did the prior session pause or fall?',
    consolidation: 'Was the base controlled and tight?', close_near_high: 'Did the session close near its high?',
    range_expansion: 'Did the trading range expand?', volume: 'Did trading volume increase?'
  };
  function verdict(check, vetoed) {
    if (vetoed) return 'veto';
    if (!check) return 'not measured';
    const recorded = String(check.status || '').toLowerCase();
    if (recorded === 'unmeasured' || recorded === 'not measured') return 'not measured';
    if (recorded === 'pass' || recorded === 'fail' || recorded === 'partial') return recorded;
    if (recorded) return 'not measured';
    if (check.partial === true || check.marginal === true) return 'partial';
    return check.pass === true ? 'pass' : check.pass === false ? 'fail' : 'not measured';
  }
  function explain(check, rules) {
    const c = check || {}, v = c.values || {}, q = rules || {};
    const out = { title: titles[c.key] || c.label || 'Recorded criterion', observed: c.display || 'not measured in this record',
      rule: c.threshold || 'not recorded', plus: '', why: 'The recorded material is preserved below. This rule format or its comparison basis is not recognised, so no interpretation is inferred.', known: false };
    let expected, observed, rule, plus, why;
    const n = k => val(q[k]), p = k => pc(q[k]);
    switch (c.key) {
      case 'two_days':
        expected = `up_run <= ${n('max_up_run')}, counting days above +${n('up_day_pct_exclusive')}%; veto at ${n('veto_up_days')}+ up closes of any size`;
        observed = `${val(v.up_run)} sessions above +${n('up_day_pct_exclusive')}% since the last negative close; ${val(v.up_closes)} consecutive rising closes of any size. Prior session: ${val(v.prior_day_pct, '%')} vs its previous close.`;
        rule = `At most ${n('max_up_run')} counted up sessions; ${n('veto_up_days')} or more consecutive rising closes is a veto. Small non-negative days do not add to or break the first count.`;
        plus = 'No counted up sessions (up_run = 0).';
        why = 'The method checks for an already extended run before a new entry.';
        break;
      case 'linearity':
        expected = `ER >= ${n('min_er')} or R2 >= ${n('min_r2')} (both for A+); failing is a veto`;
        observed = `Efficiency ratio (ER) ${val(v.er)}; trend fit (R²) ${val(v.r2)}, over a ${val(v.leg_sessions)}-session prior leg gaining ${val(v.leg_gain_pct, '%')}.`;
        rule = `ER ≥ ${n('min_er')} OR R² ≥ ${n('min_r2')}. Failure is a veto.`;
        plus = 'Both ordinary thresholds must be met. ER = absolute net close change ÷ sum of absolute daily close changes. R² measures the straight-line fit of log closes; these cutoffs are implementation proxies.';
        why = 'The method prefers an orderly prior advance rather than a jagged path.';
        break;
      case 'young_trend':
        expected = `prior breakouts since the move started <= ${n('max_prior_breakouts')} (0 for A+)`;
        observed = `${val(v.breakouts_in_move)} prior breakouts; ${val(v.sessions_since_move_start)} sessions since the implementation’s move start, gaining ${val(v.gain_since_move_start_pct, '%')}.`;
        rule = `At most ${n('max_prior_breakouts')} prior breakouts since that move start.`;
        plus = 'No prior breakouts. Move-start detection is an implementation choice; its raw fields remain below.';
        why = 'The method looks for an early breakout, before repeated attempts have aged the move.';
        break;
      case 'narrow_or_negative':
        expected = `prior day negative or range < ${n('narrow_range_pct_exclusive')}% (A+: negative and under its ${n('narrow_norm_sessions')}-session median range)`;
        observed = `Prior close change ${val(v.prior_day_pct, '%')}; high-to-low range ${val(v.prior_range_pct, '%')} of that session’s close. Preceding ${n('narrow_norm_sessions')}-session median range: ${val(v.median_range_pct, '%')}.`;
        rule = `Prior close below its previous close OR range < ${n('narrow_range_pct_exclusive')}% of its close.`;
        plus = `Negative close change AND range below its preceding ${n('narrow_norm_sessions')}-session median (the prior day itself is excluded).`;
        why = 'The method seeks a pause before the burst. A falling prior day can pass this criterion.';
        break;
      case 'consolidation':
        expected = `base ${n('base_min')}-${n('base_max')} sessions, breakdowns <= ${n('max_breakdowns')}, giveback <= ${n('max_giveback')}, tightness <= ${n('max_tightness')} (A+: 0 breakdowns, 0 bursts inside, giveback <= ${n('a_plus_max_giveback')}, tightness <= ${n('a_plus_max_tightness')}, base volume under the leg's and the ${n('volume_avg_sessions')}-session average)`;
        observed = `Base ${val(v.base_sessions)} sessions; ${val(v.breakdowns)} breakdowns; giveback ${pc(v.giveback)} of the rise from prior-leg low to base high; mean daily range as a percentage of close ${val(v.tightness, '×')} the preceding ${n('tightness_norm_sessions')}-session average.`;
        rule = `${n('base_min')}–${n('base_max')} sessions; breakdowns ≤ ${n('max_breakdowns')}; giveback ≤ ${p('max_giveback')}; range ratio ≤ ${n('max_tightness')}×.`;
        plus = `No breakdowns or bursts inside; giveback ≤ ${p('a_plus_max_giveback')}; range ratio ≤ ${n('a_plus_max_tightness')}×; base volume below both the leg’s and prior ${n('volume_avg_sessions')}-session averages. Observed: ${val(v.bursts_in_base)} bursts, volume ${val(v.base_volume_vs_leg, '×')} the leg and ${val(v.base_volume_vs_avg, '×')} the prior average. Giveback = (base high − base low) ÷ (base high − prior leg low). Tightness compares mean (high − low) ÷ close percentages.`;
        why = 'The method checks whether the pause retained the prior advance and traded in narrower ranges.';
        break;
      case 'close_near_high':
        expected = `close_pos >= ${n('min_close_pos')} and close > open (A+ >= ${n('a_plus_close_pos')}; partial from ${n('partial_close_pos')})`;
        observed = `Close ${pc(v.close_pos)} of the way from the session low to high; ${bool(v.close_above_open, 'above its open', 'at or below its open')}.`;
        rule = `At least ${p('min_close_pos')} of that low-to-high range AND close above open.`;
        plus = `At least ${p('a_plus_close_pos')} and above open. Partial begins at ${p('partial_close_pos')} when above open. Close position = (close − low) ÷ (high − low).`;
        why = 'The method checks how much of the session’s rise remained at the close.';
        break;
      case 'range_expansion':
        expected = `today's range over the largest of the prior ${n('re_window')} >= ${n('min_range_expansion')} (A+: also over the prior ${n('re_window_long')})`;
        observed = `Range ${val(v.bar_range_pct, '%')} of the session close; ${val(v.vs_prior_5, '×')} the largest range percentage in the prior ${n('re_window')} sessions.`;
        rule = `Range ratio ≥ ${n('min_range_expansion')}× versus the largest of the prior ${n('re_window')} sessions.`;
        plus = `Also ≥ ${n('min_range_expansion')}× versus the prior ${n('re_window_long')} sessions; observed ${val(v.vs_prior_10, '×')}. Each daily range percentage = (high − low) ÷ that day’s close × 100.`;
        why = 'The method seeks a wider trading range as the stock emerges from a pause.';
        break;
      case 'volume':
        expected = `volume > prior session (A+: rank <= ${n('a_plus_max_volume_rank')} of the last ${n('volume_rank_sessions')}); a base over ${n('cv_base_sessions_exclusive')} sessions also needs >= ${n('cv_min_volume')}x the ${n('volume_avg_sessions')}-session average`;
        observed = `${val(v.volume_vs_prior, '×')} the prior session’s volume; ${val(v.volume_vs_avg50, '×')} the prior ${n('volume_avg_sessions')}-session average. Long-base condition: ${bool(v.cv_required, 'applies', 'does not apply')}.`;
        rule = `More volume than the prior session. A base over ${n('cv_base_sessions_exclusive')} sessions also requires ≥ ${n('cv_min_volume')}× the prior ${n('volume_avg_sessions')}-session average (burst excluded).`;
        plus = `Volume rank ≤ ${n('a_plus_max_volume_rank')} of the last ${n('volume_rank_sessions')} sessions including the burst; observed rank ${val(v.volume_rank_60)} (1 is highest). The long-base volume addition comes from secondary sources.`;
        why = 'The method checks whether the price move had greater trading participation; volume alone does not prove demand will continue.';
        break;
    }
    // Do not apply today's defaults to an older or unfamiliar record. Matching
    // the archived expression and required bases recognises a format, not a score.
    const bases = { consolidation: ['tightness_norm_sessions'], volume: [], linearity: [], young_trend: [], two_days: [], narrow_or_negative: [], close_near_high: [], range_expansion: [] };
    if (expected && !expected.includes('not measured') && (bases[c.key] || []).every(k => number(q[k])) && clean(expected) === clean(c.threshold)) {
      Object.assign(out, { observed, rule, plus, why, known: true });
    }
    return out;
  }
  function helpSystem(onRead) {
    const d = w.document;
    let trigger = null, popup = null, explicit = false, timer = null, returning = null;
    const make = (tag, text, cls) => { const e = d.createElement(tag); if (text) e.textContent = text; if (cls) e.className = cls; return e; };
    function dismiss(back) {
      w.clearTimeout(timer);
      const old = trigger;
      if (old) old.setAttribute('aria-expanded', 'false');
      if (popup) { if (popup.hidePopover && popup.matches(':popover-open')) popup.hidePopover(); popup.remove(); }
      trigger = popup = null; explicit = false;
      if (back && old && old.isConnected) { returning = old; old.focus({ preventScroll: true }); w.setTimeout(() => { returning = null; }, 0); }
    }
    function position() {
      if (!trigger || !popup) return;
      const r = trigger.getBoundingClientRect();
      if (!trigger.isConnected || r.bottom < 0 || r.top > w.innerHeight) { dismiss(false); return; }
      for (let parent = trigger.parentElement; parent && parent !== d.body; parent = parent.parentElement) {
        if (/auto|scroll|hidden|clip/.test(w.getComputedStyle(parent).overflowY)) {
          const clip = parent.getBoundingClientRect();
          if (r.bottom <= clip.top || r.top >= clip.bottom) { dismiss(false); return; }
        }
      }
      const edge = 12, gap = 8;
      // CSS text enlargement scales top-layer coordinates as well as content.
      const scale = popup.getBoundingClientRect().width / popup.offsetWidth || 1;
      popup.style.maxWidth = (w.innerWidth - 2 * edge) / scale + 'px';
      popup.style.maxHeight = (w.innerHeight - 2 * edge) / scale + 'px';
      const p = popup.getBoundingClientRect();
      const top = r.bottom + gap + p.height <= w.innerHeight - edge ? r.bottom + gap : Math.max(edge, r.top - p.height - gap);
      popup.style.top = Math.round(top / scale) + 'px';
      popup.style.left = Math.round(Math.max(edge, Math.min(r.left, w.innerWidth - p.width - edge)) / scale) + 'px';
    }
    function deferClose() {
      w.clearTimeout(timer);
      if (!explicit) timer = w.setTimeout(() => {
        if (popup && !popup.matches(':hover') && !popup.contains(d.activeElement) && trigger && !trigger.matches(':hover') && d.activeElement !== trigger) dismiss(false);
      }, 250);
    }
    function open(button, deliberate) {
      w.clearTimeout(timer);
      if (returning === button) return;
      if (trigger === button && popup) { if (deliberate) { explicit = true; popup.querySelector('button').focus(); } return; }
      dismiss(false); trigger = button; explicit = !!deliberate;
      const topic = button.dataset.helpTopic, term = terms[topic];
      popup = make('aside', '', 'ss-help-popover'); popup.id = 'ss-reading-help';
      popup.setAttribute('role', 'region'); popup.setAttribute('aria-labelledby', 'ss-help-heading'); popup.setAttribute('popover', 'manual');
      const title = make('strong', term[0]); title.id = 'ss-help-heading';
      const close = make('button', 'Close', 'sc-btn sc-btn--ghost sc-btn--sm'); close.type = 'button'; close.setAttribute('aria-label', 'Close help'); close.addEventListener('click', () => dismiss(true));
      const head = make('div', '', 'ss-help-popover__head'); head.append(title, close);
      const more = make('a', 'Read more in Method'); more.href = '#/method/' + topic;
      more.addEventListener('click', e => { e.preventDefault(); const from = trigger; dismiss(false); onRead(topic, from); });
      popup.append(head, make('p', term[1]), more);
      popup.addEventListener('pointerenter', () => w.clearTimeout(timer)); popup.addEventListener('pointerleave', deferClose);
      popup.addEventListener('focusin', () => w.clearTimeout(timer)); popup.addEventListener('focusout', deferClose);
      (button.closest('dialog[open]') || d.body).appendChild(popup);
      if (popup.showPopover) popup.showPopover();
      button.setAttribute('aria-expanded', 'true'); position();
      if (deliberate) close.focus();
    }
    function button(topic, label) {
      const b = make('button', (label || terms[topic][0]) + ' ?', 'ss-help'); b.type = 'button';
      b.dataset.helpTopic = topic; b.setAttribute('aria-label', 'Help: ' + (label || terms[topic][0]));
      b.setAttribute('aria-expanded', 'false'); b.setAttribute('aria-controls', 'ss-reading-help');
      b.addEventListener('pointerenter', e => { if (e.pointerType !== 'touch') open(b, false); });
      b.addEventListener('pointerleave', deferClose); b.addEventListener('focus', () => open(b, false)); b.addEventListener('blur', deferClose);
      b.addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); if (trigger === b && explicit) dismiss(true); else open(b, true); });
      return b;
    }
    d.addEventListener('keydown', e => { if (e.key === 'Escape' && popup) { e.preventDefault(); e.stopImmediatePropagation(); dismiss(true); } }, true);
    d.addEventListener('pointerdown', e => { if (popup && !popup.contains(e.target) && trigger !== e.target && !trigger.contains(e.target)) dismiss(false); }, true);
    d.addEventListener('scroll', position, true); w.addEventListener('resize', position);
    return { button, dismiss };
  }
  S.reading = { terms, verdict, explain, helpSystem };
})(window);
