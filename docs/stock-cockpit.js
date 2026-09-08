/* The current-session starting point. Every figure is from the loaded record;
   this module changes presentation, never the scan, score, or return basis. */
(function () {
  'use strict';
  var focused = false;
  var reportIds = ['evidence-card', 'funnel-card', 'shortlist-card', 'scores-card',
    'gated-card', 'checks-card', 'predict-card', 'streak-card', 'trend-card',
    'outcome-card', 'returns-card', 'runs-card', 'ticker-card', 'next-callout'];
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function numeric(v) { return typeof v === 'number' && Number.isFinite(v) && v >= 0; }
  function count(v) { return numeric(v) ? v.toLocaleString('en-US') : '—'; }
  function link(label, href, cls) {
    var a = el('a', cls || 'cockpit-link', label); a.href = href; return a;
  }
  function applyFocus() {
    document.body.classList.toggle('stock-focus', focused);
    var b = document.getElementById('cockpit-focus');
    if (b) {
      b.setAttribute('aria-pressed', String(focused));
      b.textContent = focused ? 'Show full report' : 'Focus on my workspace';
    }
    var note = document.getElementById('cockpit-focus-note');
    if (note) note.textContent = focused
      ? 'Focus view: setups, risk planning, your journal, and research. Open any report link to restore the full report.'
      : 'Keep the full report open, or focus on setup research and trade planning.';
  }
  // Reveal report targets before their own handlers move keyboard focus.
  document.addEventListener('click', function (event) {
    var a = event.target.closest && event.target.closest('a[href^="#"]');
    if (!a || !focused) return;
    var target = document.getElementById(a.getAttribute('href').slice(1));
    if (target && target.closest('[data-stock-report]')) { focused = false; applyFocus(); }
  }, true);
  window.addEventListener('hashchange', function () {
    var target = document.getElementById(location.hash.slice(1));
    if (focused && target && target.closest('[data-stock-report]')) { focused = false; applyFocus(); }
  });
  function render(data) {
    var host = document.getElementById('session-cockpit');
    if (!host) return;
    reportIds.forEach(function (id) {
      var section = document.getElementById(id);
      if (section) section.setAttribute('data-stock-report', '');
    });
    var run = data.run || {}, candidates = Array.isArray(data.candidates) ? data.candidates : [];
    var errors = Array.isArray(run.errors) ? run.errors : [];
    var degraded = errors.length > 0 || (run.status && run.status !== 'ok');
    var claude = candidates.filter(function (c) { return c.provenance && c.provenance.source === 'claude'; }).length;
    var fallback = candidates.filter(function (c) { return c.provenance && c.provenance.source === 'fallback'; }).length;
    var unknown = candidates.length - claude - fallback;
    var heading = el('div', 'cockpit-heading');
    var intro = el('div');
    intro.append(el('p', 'sc-eyebrow sc-eyebrow--muted', 'SCORING PIPELINE / SECONDARY REVIEW'));
    var title = el('h2', '', run.fixture ? 'Explore this sample session.' : degraded ? 'Start with the run notes.' : candidates.length ? 'Build your view of the session.' : 'No scored candidates. A clear next step.');
    title.id = 'cockpit-title'; intro.append(title);
    var stamp = el('span', 'cockpit-session', 'RECORDED / ' + (run.date || 'DATE NOT RECORDED'));
    heading.append(intro, stamp);
    var grid = el('div', 'cockpit-grid');
    var review = el('article', 'cockpit-card cockpit-card--lead');
    review.append(el('p', 'cockpit-card-label', 'Your review queue'),
      el('p', 'cockpit-number', count(candidates.length)),
      el('h3', '', candidates.length ? 'Candidates to explore' : 'No scored candidates'));
    review.append(el('p', 'cockpit-copy', candidates.length
      ? count(run.shortlist_size) + ' on the recorded shortlist. Filter the signal lens, compare the details, and save the names you want to revisit.'
      : 'This snapshot has no ranked names. Review where the run narrowed, or revisit an earlier session.'));
    review.append(link(candidates.length ? 'Open the signal lens ↗' : 'See where the run narrowed ↗', candidates.length ? '#signal-workspace' : '#funnel-card', 'sc-btn sc-btn--primary cockpit-cta'));
    var trust = el('article', 'cockpit-card');
    trust.append(el('p', 'cockpit-card-label', 'Know the source'), el('h3', '', run.fixture ? 'Sample, clearly marked' : degraded ? 'Review the caveats' : 'Read the record first'));
    var details = el('dl', 'cockpit-source');
    [['Claude scores', claude], ['Checklist fallbacks', fallback], ['Other / unrecorded source', unknown]].forEach(function (row) {
      var pair = el('div'); pair.append(el('dt', '', row[0]), el('dd', '', count(row[1]))); details.append(pair);
    });
    trust.append(details, el('p', 'cockpit-copy', run.fixture ? 'Sample figures exercise the interface. They are not a real scan.'
      : degraded ? 'The run recorded a degraded status or errors. Read those notes alongside the ranking.'
      : 'Recorded daily measurements. Checking for updates reloads the published snapshot.'));
    trust.append(link(degraded && errors.length ? 'Read the run notes ↗' : 'Check snapshot status ↗', degraded && errors.length ? '#notice' : '#snapshot-panel'));
    var route = el('article', 'cockpit-card');
    route.append(el('p', 'cockpit-card-label', 'Make it yours'), el('h3', '', 'From a scan to a research habit.'));
    var steps = el('ol', 'cockpit-route');
    [['Compare the details', '#stock-desk', 'Keep up to three candidates side by side.'],
      ['Save your thinking', '#stock-desk', 'Pin a ticker and write a private browser note.'],
      ['Revisit the session', '#stock-replay', 'See previous runs and recorded outcomes.']].forEach(function (row) {
      var item = el('li'); item.append(link(row[0], row[1]), el('span', '', row[2])); steps.append(item);
    });
    route.append(steps); grid.append(review, trust, route);
    var trail = el('div', 'cockpit-trail'); trail.setAttribute('aria-label', 'The recorded selection stages');
    [['Universe', run.universe && run.universe.size], ['Bursts', run.bursts], ['Passed gate', run.passed_gate], ['Shortlist', run.shortlist_size]].forEach(function (row, index) {
      var cell = link('', '#funnel-card', 'cockpit-stage');
      cell.append(el('span', 'cockpit-stage-index', '0' + (index + 1)), el('span', 'cockpit-stage-name', row[0]), el('strong', '', count(row[1])));
      trail.append(cell);
    });
    var footer = el('div', 'cockpit-footer');
    var button = el('button', 'sc-btn sc-btn--secondary', 'Focus on my workspace'); button.id = 'cockpit-focus'; button.type = 'button';
    button.addEventListener('click', function () { focused = !focused; applyFocus(); });
    var note = el('p', 'sc-note'); note.id = 'cockpit-focus-note'; note.setAttribute('role', 'status');
    footer.append(button, note);
    var more = el('details', 'cockpit-details');
    more.append(el('summary', '', count(candidates.length) + ' scored reviews · sources and research tools'), grid);
    host.replaceChildren(heading, more, trail, footer); host.hidden = false; applyFocus();
  }
  window.SCStockCockpit = { render: render };
}());
