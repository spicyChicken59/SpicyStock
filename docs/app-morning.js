/* Personal morning preparation over the published record. No provider requests
   or broker order creation. Publication/timing permission comes from
   app.js availability(); candidate ticket status comes from its existing model.
   Cash and checklist entries live only in this tab, never in the publication. */
(function (w) {
  'use strict';
  const api = w.SCStock = w.SCStock || {}, d = w.document;
  const PROFILE = Object.freeze({ equity: 2000, riskPct: 0.5, positionPct: 25, maxOpenPositions: 4, zone: 'America/Chicago' });
  const money = value => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value);
  const centMoney = value => '$' + (BigInt(value) / 100n).toLocaleString('en-US') + '.' + String(BigInt(value) % 100n).padStart(2, '0');
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const clock = value => new Intl.DateTimeFormat('en-US', { timeZone: PROFILE.zone, hour: 'numeric', minute: '2-digit' }).format(value);
  const date = value => new Intl.DateTimeFormat('en-US', { timeZone: PROFILE.zone, weekday: 'short', month: 'short', day: 'numeric' }).format(value);
  const count = (n, singular, plural) => n + ' ' + (n === 1 ? singular : plural || singular + 's');
  const CHECKS = [
    ['quote', 'Check a current broker quote and spread; confirm the entry trigger and limit still apply.'],
    ['cash', 'Confirm settled cash at the broker covers the whole order plus any fees.'],
    ['stop', 'Confirm your broker supports the order and protective stop; check quantity and exit plan.'],
    ['events', 'Check company news, earnings and takeover/corporate-action risk before entry.']
  ];
  let mounted = null, sessionKey = null, publicationKey = null, latest = null, previewKey = null;

  function facts(data, av, model) {
    const account = data.account || {}, run = data.run || {}, regime = (data.breadth || {}).regime || {};
    const stages = (model || {}).stages || {};
    const bursts = (stages.bursts || []).filter(c => c.status === 'ticket');
    const setups = (stages['setting-up'] || []).filter(c => c.status === 'ticket');
    const tickets = bursts.concat(setups), tm = av.timing || {};
    const marketKnown = regime.verdict === 'green' || regime.verdict === 'yellow';
    const allowed = !!av.offered && marketKnown && !data.fixture;
    const matched = account.equity === PROFILE.equity && account.risk_pct === PROFILE.riskPct && account.max_position_pct === PROFILE.positionPct && account.max_open_positions === PROFILE.maxOpenPositions;
    let headline, reason;
    if (data.fixture) {
      headline = 'Practice record — no live entries';
      reason = 'These are simulated setups. Use them to learn the morning workflow.';
    } else if (!av.offered) {
      headline = 'No entries to place from this record';
      reason = av.reason || 'Publication or entry timing is unavailable. Inspect the record for context.';
    } else if (!marketKnown) {
      headline = regime.verdict === 'red' ? 'Stand aside for new longs' : 'Market permission is unavailable';
      reason = regime.verdict === 'red' ? 'The published market gate is RED. A stock on the scan is not a new-entry instruction.' : 'Wait for a record with an established market verdict.';
    } else if (!tickets.length) {
      headline = 'No qualifying entry plans';
      reason = (data.cover || {}).h1 || 'The run published no conditional entry tickets. Inspect the scan gates to see what held them back.';
    } else if (!matched) {
      headline = 'Account sizing needs an update';
      reason = count(tickets.length, 'conditional plan') + ' recorded. Published quantities do not match your $2,000 cash-account reference.';
    } else if (av.pub.state === 'degraded') {
      headline = 'Review run issues before trading';
      reason = count(tickets.length, 'conditional plan') + ' recorded; the run reports incomplete or degraded evidence. Inspect each plan and its conditions.';
    } else {
      headline = av.phase === 'open' ? count(tickets.length, 'conditional plan') + ' to inspect' : 'Prepare ' + count(tickets.length, 'conditional plan');
      reason = 'Confirm live prices, settled cash and the plan’s conditions at your broker before submitting anything.';
    }
    return {
      headline, reason, matched, allowed, tickets, fixture: !!data.fixture, bursts: bursts.length, setups: setups.length,
      window: tm.known ? date(tm.opens) + ' · ' + clock(tm.opens) + '–' + clock(tm.cutoff) + ' CT' : 'Entry session/window unavailable',
      prepare: tm.known && tm.prepareBy ? 'Prepare by ' + clock(tm.prepareBy) + ' CT' : '',
      phase: av.phase === 'open' ? 'window open' : av.phase === 'upcoming' ? 'window upcoming' : av.phase === 'ended' ? 'window ended' : 'timing unknown',
      publication: av.pub.chip || 'publication unknown',
      market: (regime.verdict || 'unknown').toUpperCase() + (finite(regime.size_multiplier) ? ' · size ' + (100 * regime.size_multiplier) + '%' : ''),
      sizing: matched ? 'Published sizing matches the reference; balances and holdings are still unverified.'
        : 'Published sizing: ' + (finite(account.equity) ? money(account.equity) : 'equity unknown') +
          ' / ' + (finite(account.risk_pct) ? account.risk_pct + '% risk' : 'risk unknown') +
          ' / ' + (finite(account.max_position_pct) ? account.max_position_pct + '% position cap' : 'cap unknown') +
          ' / ' + (Number.isInteger(account.max_open_positions) ? account.max_open_positions + ' model slots' : 'model slot cap unknown') +
          '. Do not copy these quantities for the $2,000 account. Wait for matching sizing or verify a smaller quantity independently.',
      session: tm.known ? tm.session : null,
      summary: data.fixture ? 'Practice record' : !allowed ? 'Inspect only' : !tickets.length ? 'No qualifying plans' : !matched ? 'Check sizing' : av.pub.state === 'degraded' ? 'Review run issues' : 'Prepare at broker',
      identity: [run.session, run.published_at, (data.app || {}).rules_version].join('|')
    };
  }

  function node(tag, attrs, text) {
    const n = d.createElement(tag);
    Object.entries(attrs || {}).forEach(([key, value]) => n.setAttribute(key, value));
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function field(host, key, text) {
    const n = host.querySelector('[data-morning="' + key + '"]');
    if (n && n.textContent !== text) n.textContent = text;
  }
  function cashValue(raw) {
    const value = api.cashPreview.cents(raw);
    return { value: value == null ? null : value / 100, error: value === undefined };
  }
  function refreshCash(host) {
    const input = host.querySelector('#morning-cash'), cash = cashValue(input.value);
    input.setAttribute('aria-invalid', cash.error ? 'true' : 'false');
    const label = cash.error ? 'Enter a non-negative dollar amount with up to two decimals.'
      : cash.value === null ? 'Settled cash unknown — check your broker.'
      : cash.value === 0 ? '$0 settled cash entered — no new cash purchase is funded.'
      : centMoney(api.cashPreview.cents(input.value)) + ' settled cash entered by you; not verified by SpicyStock.';
    field(host, 'cash', label);
    field(host, 'cash-status', label);
    refreshPreview(host);
  }
  const planKey = candidate => candidate.stage + ':' + candidate.ticker;
  function refreshPreview(host) {
    const select = host.querySelector('#morning-preview-plan'), result = host.querySelector('[data-cash-preview-result]');
    if (!select || !latest) return;
    const choices = latest.tickets.map(candidate => [planKey(candidate), candidate.ticker + ' · ' + (candidate.stage === 'bursts' ? 'burst' : 'setting up')]);
    const signature = JSON.stringify(choices);
    if (select.dataset.choices !== signature) {
      const previous = select.value;
      select.replaceChildren(...(choices.length ? choices : [['', 'No published ticket']]).map(([value, label]) => node('option', { value }, label)));
      if (choices.some(([value]) => value === previous)) select.value = previous;
      select.dataset.choices = signature;
    }
    const candidate = latest.tickets.find(item => planKey(item) === select.value), plan = candidate && candidate.plan || {}, order = plan.order_json;
    const identity = candidate ? [planKey(candidate), (plan.evidence_ref || {}).plan_sha256, JSON.stringify(order)].join('|') : null;
    if (previewKey !== identity) {
      host.querySelector('#morning-preview-fees').value = '';
      host.querySelector('#morning-preview-quantity').value = '';
      previewKey = identity;
    }
    result.replaceChildren();
    let why = latest.fixture ? 'Practice record: no current personal order preview.'
      : !latest.allowed ? latest.reason
      : !latest.matched ? 'Published account sizing differs from the $2,000 reference. Inspect the recorded plan; this preview is unavailable.'
      : !candidate ? 'No admitted published ticket is available for this calculation.'
      : order && order.symbol !== candidate.ticker ? 'The published order symbol does not match this candidate. This preview is unavailable.'
      : order && (plan.shares !== order.quantity || (candidate.stage === 'bursts' ? plan.entry_ref : plan.trigger) !== order.stop_price || plan.limit !== order.limit_price || !order.then || plan.stop !== order.then.stop_price)
        ? 'Published plan quantities or prices do not match its order. This preview is unavailable.'
      : api.observations.refusal(candidate);
    let calculation = null;
    if (!why) {
      calculation = api.cashPreview.calculate({ cash: host.querySelector('#morning-cash').value,
        fees: host.querySelector('#morning-preview-fees').value, quantity: host.querySelector('#morning-preview-quantity').value, order });
      why = calculation.reason;
    }
    host.querySelector('[data-cash-preview]').setAttribute('data-preview-state', calculation ? calculation.state : 'unavailable');
    const status = host.querySelector('[data-cash-preview-status]'); status.textContent = why || '';
    if (calculation && calculation.state === 'calculated') {
      const amounts = [
        ['Published shares', calculation.publishedQuantity], ['Your preview shares', calculation.quantity],
        ['Buy trigger / limit', centMoney(calculation.triggerCents) + ' / ' + centMoney(calculation.limitCents)],
        ['Protective stop', centMoney(calculation.stopCents)],
        ['Principal at the limit', centMoney(calculation.principalCents)], ['Fees buffer', centMoney(calculation.feeCents)],
        ['Total cash for this preview', centMoney(calculation.commitmentCents)],
        ['Planned price-to-stop risk', centMoney(calculation.riskCents)],
        ['Cash left after this preview only', centMoney(calculation.remainingCents)]
      ];
      amounts.forEach(([label, value]) => { const item = node('div'); item.append(node('dt', {}, label), node('dd', {}, String(value))); result.append(item); });
    }
    const copy = host.querySelector('[data-cash-preview-copy-note]');
    copy.textContent = order ? 'Copy order elsewhere still uses the published ' + order.quantity + ' shares. This preview does not change, copy or submit that order.' : 'This preview creates no order.';
    if (api.handoffUI) {
      const binding = api.observations.facts();
      const intent = calculation && calculation.state === 'calculated' && /^[a-f0-9]{64}$/.test(binding.canonicalHash || '') ? {
        key: planKey(candidate), referenceId: (plan.evidence_ref || {}).id, expectedPublication: binding.canonicalHash,
        cash: host.querySelector('#morning-cash').value, fees: host.querySelector('#morning-preview-fees').value, quantity: String(calculation.quantity)
      } : null;
      api.handoffUI.preview(host.querySelector('[data-cash-preview]'), intent);
    }
  }
  function previewControl() {
    const section = node('section', { 'data-cash-preview': '', 'aria-labelledby': 'morning-preview-title' });
    section.append(node('h3', { id: 'morning-preview-title' }, 'Cash-aware quantity preview'),
      node('p', { class: 'sc-hint' }, 'One plan at a time. Each calculation uses the cash you entered independently; it reserves nothing. Account for other open orders and holds at your broker before entering available cash.'));
    const controls = node('div', { class: 'ss-morning__cash' });
    const select = node('select', { id: 'morning-preview-plan', class: 'sc-select' });
    const fees = node('input', { id: 'morning-preview-fees', class: 'sc-input', type: 'text', inputmode: 'decimal', autocomplete: 'off', placeholder: 'Unknown; 0 allowed' });
    const quantity = node('input', { id: 'morning-preview-quantity', class: 'sc-input', type: 'text', inputmode: 'numeric', autocomplete: 'off', placeholder: 'Affordable maximum' });
    [['Published plan', select], ['Fees buffer for this order ($)', fees], ['Preview shares (optional)', quantity]].forEach(([label, input]) => {
      controls.append(node('label', { for: input.id }, label), input);
    });
    const update = () => { api.reclock(); refreshPreview(mounted); };
    select.addEventListener('change', update);
    fees.addEventListener('input', update);
    quantity.addEventListener('input', update);
    section.append(controls, node('p', { class: 'sc-hint', role: 'status', 'data-cash-preview-status': '' }),
      node('dl', { class: 'sc-facts', 'data-cash-preview-result': '' }),
      node('p', { class: 'sc-hint', 'data-cash-preview-copy-note': '' }),
      node('p', { class: 'sc-hint' }, 'Planned risk excludes fees, gaps and slippage; actual losses can be larger. A calculation is not broker verification or an entry instruction.'));
    return section;
  }
  function mount(host) {
    host.classList.add('sc-card', 'ss-morning');
    host.setAttribute('aria-labelledby', 'morning-title');
    const close = node('button', { type: 'button', class: 'sc-btn sc-btn--ghost sc-btn--sm', id: 'morning-close' }, 'Close');
    close.addEventListener('click', () => host.close());
    let returnToOpener = true;
    const opener = d.getElementById('morning-open');
    if (opener) {
      opener.disabled = false;
      opener.addEventListener('click', () => { host.showModal(); close.focus(); });
      host.addEventListener('close', () => { if (returnToOpener) opener.focus({ preventScroll: true }); returnToOpener = true; });
    }
    const content = node('div', { class: 'ss-morning__content' });
    const head = node('div', { class: 'ss-morning__head' });
    const lead = node('div');
    lead.append(node('div', { class: 'sc-eyebrow' }, 'morning desk · Chicago'), node('h2', { id: 'morning-title', 'data-morning': 'headline' }));
    const window = node('div', { class: 'ss-morning__window' });
    window.append(node('strong', { 'data-morning': 'window' }), node('span', { 'data-morning': 'phase' }));
    const top = node('div', { class: 'ss-morning__top' }); top.append(window, close);
    head.append(lead, top);
    const factsRow = node('dl', { class: 'ss-morning__facts' });
    [['publication', 'record'], ['market', 'market'], ['plans', 'conditional plans'], ['cash', 'settled cash']].forEach(([key, label]) => {
      const block = node('div'); block.append(node('dt', {}, label), node('dd', { 'data-morning': key })); factsRow.append(block);
    });
    const reason = node('p', { class: 'ss-morning__reason', 'data-morning': 'reason' });
    const account = node('p', { class: 'ss-morning__reference' }, '$2,000 cash-account reference · $10 planned risk (0.5%) · $500 position cap (25%).');
    const sizing = node('p', { class: 'ss-morning__sizing', 'data-morning': 'sizing' });
    const details = node('details', { class: 'ss-morning__prep' });
    details.append(node('summary', {}, 'Before you trade · cash and broker checks'));
    const body = node('div', { class: 'ss-morning__body' });
    const form = node('div', { class: 'ss-morning__cash' });
    form.append(node('label', { for: 'morning-cash' }, 'Settled cash shown by your broker ($)'));
    const input = node('input', { id: 'morning-cash', class: 'sc-input', type: 'text', inputmode: 'decimal', autocomplete: 'off', placeholder: 'Unknown', 'aria-describedby': 'morning-cash-status morning-local-note' });
    input.addEventListener('input', () => { api.reclock(); refreshCash(host); });
    form.append(input, node('p', { id: 'morning-cash-status', class: 'sc-hint', role: 'status', 'data-morning': 'cash-status' }));
    body.append(form, previewControl());
    const checklist = node('fieldset', { class: 'ss-morning__checks' });
    checklist.append(node('legend', { class: 'sc-eyebrow' }, 'Manual checks — repeat for each order'));
    CHECKS.forEach(([key, text]) => {
      const label = node('label', { class: 'sc-check' });
      label.append(node('input', { type: 'checkbox', 'data-morning-check': key }), node('span', {}, text));
      checklist.append(label);
    });
    body.append(checklist, node('p', { id: 'morning-local-note', class: 'sc-hint' }, 'Entries stay in this tab and clear on reload or a new session. Checkboxes are reminders, never permission to trade. SpicyStock does not verify balances, live quotes, news or broker order support.'),
      node('p', { class: 'sc-hint' }, 'Use settled cash only; ask your broker when sale proceeds settle. The $10 reference is price-to-stop risk, not a maximum loss: gaps and slippage can lose more.'));
    details.append(body);
    const next = node('button', { type: 'button', class: 'sc-btn sc-btn--secondary sc-btn--sm', 'data-morning': 'next' });
    next.addEventListener('click', () => {
      // Open the current record's research; this control places/copies nothing.
      const current = api.morning.facts(api.data, api.avail, api.model);
      returnToOpener = false;
      host.close();
      const reveal = (route, action) => {
        if (w.location.hash === route) { api.navigate(route); action(); }
        else { w.addEventListener('hashchange', action, { once: true }); api.navigate(route); }
      };
      if (current.tickets.length) {
        const candidate = current.tickets[0];
        reveal('#/explore/' + candidate.stage + '/' + encodeURIComponent(candidate.ticker), () => {
          const detail = d.getElementById('detail');
          if (detail) { detail.scrollIntoView({ block: 'start' }); detail.focus({ preventScroll: true }); }
        });
      } else {
        reveal('#/explore', () => {
          const gates = d.getElementById('decision-gates'), disclosure = gates && gates.querySelector('details');
          if (disclosure) { disclosure.open = true; gates.scrollIntoView({ block: 'start' }); disclosure.querySelector('summary').focus({ preventScroll: true }); }
        });
      }
    });
    const foot = node('div', { class: 'ss-morning__foot' });
    foot.append(details, next);
    const issuer = api.issuerEvidence && typeof api.issuerEvidence.mount === 'function' && typeof api.issuerEvidence.update === 'function'
      ? api.issuerEvidence.mount() : node('p', { class: 'sc-hint', 'data-issuer-unavailable': '' }, 'Issuer source reader unavailable. Check company filings, news and earnings independently; this does not clear any known event.');
    const research = api.stopResearch && typeof api.stopResearch.mount === 'function'
      ? api.stopResearch.mount() : node('p', { class: 'sc-hint' }, 'Optional stop-width research is unavailable in this page. Production plans keep their recorded policy.');
    content.append(head, factsRow, reason, account, sizing, api.observations.summary(), issuer, research, foot);
    if (api.handoffUI && api.handoff) api.handoffUI.mount(content);
    else content.append(node('p', { class: 'sc-hint' }, 'Private broker handoffs are unavailable in this page. Cash preview and published research remain available.'));
    host.append(content);
    mounted = host;
  }
  function render(host, data, av, model) {
    if (!host) return;
    if (mounted !== host) mount(host);
    latest = facts(data, av, model);
    if (sessionKey !== latest.session) { host.querySelector('#morning-cash').value = ''; previewKey = null; }
    if (publicationKey !== latest.identity || sessionKey !== latest.session) host.querySelectorAll('[data-morning-check]').forEach(input => { input.checked = false; });
    sessionKey = latest.session; publicationKey = latest.identity;
    ['headline', 'window', 'publication', 'market', 'reason', 'sizing'].forEach(key => field(host, key, latest[key]));
    const opener = d.getElementById('morning-open');
    if (opener) opener.setAttribute('title', 'Morning desk · Chicago · ' + latest.window + ' · ' + latest.summary + ' · $2,000 cash reference');
    field(host, 'phase', latest.phase + (latest.prepare ? ' · ' + latest.prepare : ''));
    field(host, 'plans', latest.bursts + ' burst · ' + latest.setups + ' setting up' + (latest.allowed ? '' : ' · inspect only'));
    field(host, 'next', latest.tickets.length ? 'Inspect first recorded plan' : 'See why we’re waiting');
    const restrictions = new Set(api.observations.facts().restricted);
    const blocked = latest.tickets.filter(candidate => restrictions.has((candidate.stage === 'bursts' ? 'burst:' : 'anticipation:') + candidate.ticker));
    if (blocked.length) {
      field(host, 'headline', 'Entry withheld by a morning event check');
      field(host, 'reason', blocked.map(candidate => candidate.ticker).join(', ') + ': ' + api.observations.refusal(blocked[0]));
      if (opener) opener.setAttribute('title', 'Morning desk · Chicago · ' + latest.window + ' · Event restriction — inspect the sources');
    }
    host.setAttribute('data-sizing-match', String(latest.matched));
    host.setAttribute('data-morning-offered', String(latest.allowed));
    refreshCash(host);
    if (api.handoffUI) api.handoffUI.update();
    if (api.issuerEvidence && typeof api.issuerEvidence.update === 'function') api.issuerEvidence.update(data);
    if (api.stopResearch && typeof api.stopResearch.update === 'function') api.stopResearch.update(data);
  }
  api.morning = { render, facts, cashValue, profile: PROFILE, refreshPersonal: () => { if (mounted) refreshPreview(mounted); } };
})(window);
