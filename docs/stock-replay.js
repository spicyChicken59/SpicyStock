/* Session Replay reads saved observations only; it never starts a scan. */
(function () {
  'use strict';

  var state = { data: null, sessions: [], selected: null, stamp: null, book: null,
    loading: false, error: '', controller: null, request: 0, requested: new Set() };
  var dateFormat = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
  var shortDateFormat = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });

  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function finite(value) { return typeof value === 'number' && Number.isFinite(value); }
  function count(value) { return finite(value) && value >= 0 && Number.isInteger(value); }
  function number(value) { return count(value) ? value.toLocaleString('en-US') : 'Not recorded'; }
  function date(value, short) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
    var parsed = new Date(value + 'T00:00:00Z');
    if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) return null;
    return (short ? shortDateFormat : dateFormat).format(parsed);
  }
  function key(run) { return run.date + '|' + (run.type || ''); }
  function selected() { return state.sessions.find(function (run) { return key(run) === state.selected; }); }
  function basis() {
    var active = document.querySelector('#basis-tabs [aria-pressed="true"]');
    return active && active.dataset.basis === 'open' ? 'open' : 'close';
  }
  function basisLabel() { return basis() === 'open' ? "from the next session’s open" : 'from the burst-day close'; }
  function percentage(value) { return finite(value) ? (value > 0 ? '+' : '') + value.toFixed(1) + '%' : 'Not recorded'; }
  function source(row) {
    if (row.source === 'claude') return 'Claude';
    if (row.source === 'fallback') return 'Fallback';
    return typeof row.source === 'string' && row.source.trim() ? 'Source: ' + row.source : 'Scorer not recorded';
  }
  function button(text, id, handler) {
    var node = element('button', 'stock-replay__button', text);
    node.type = 'button';
    node.id = id;
    node.addEventListener('click', handler);
    return node;
  }
  function summaryNote(run) {
    if (run.status && run.status !== 'ok') return 'Recorded status: ' + run.status + '. Review this session’s recorded counts and scoring sources below.';
    if (run.scored === 0 && run.bursts === 0) return 'A quiet session is still a record. No 4% bursts were recorded in this scan.';
    if (run.scored === 0) return 'No candidates were scored in this scan. The recorded counts show how many names reached each stage.';
    return number(run.scored) + ' candidates scored; ' + number(run.shortlist_size) + ' made the shortlist.';
  }
  function metric(label, value) {
    var item = element('div', 'stock-replay__metric');
    item.append(element('dt', '', label), element('dd', '', value));
    return item;
  }
  function changeSelection(value) {
    state.selected = value;
    paint(true);
  }

  function controls(host) {
    var index = state.sessions.findIndex(function (run) { return key(run) === state.selected; });
    var nav = element('div', 'stock-replay__controls');
    var previous = button('← Previous', 'stock-replay-previous', function () {
      if (index > 0) changeSelection(key(state.sessions[index - 1]));
    });
    previous.disabled = index <= 0;
    previous.setAttribute('aria-label', 'Previous recorded session');
    var choice = element('div', 'stock-replay__choice');
    var label = element('label', '', 'Recorded session');
    label.htmlFor = 'stock-replay-date';
    var select = element('select', 'stock-replay__select');
    select.id = 'stock-replay-date';
    state.sessions.forEach(function (run) {
      var option = element('option', '', date(run.date) + (run.type ? ' · ' + run.type : ''));
      option.value = key(run);
      select.appendChild(option);
    });
    select.value = state.selected;
    select.addEventListener('change', function () { changeSelection(select.value); });
    choice.append(label, select);
    var next = button('Next →', 'stock-replay-next', function () {
      if (index < state.sessions.length - 1) changeSelection(key(state.sessions[index + 1]));
    });
    next.disabled = index >= state.sessions.length - 1;
    next.setAttribute('aria-label', 'Next recorded session');
    nav.append(previous, choice, next);
    host.appendChild(nav);

    var caption = element('p', 'stock-replay__rail-caption', 'Scored candidates per recorded session · oldest to newest');
    caption.id = 'stock-replay-rail-caption';
    host.appendChild(caption);
    var rail = element('div', 'stock-replay__rail');
    rail.setAttribute('role', 'group');
    rail.setAttribute('aria-labelledby', caption.id);
    var maximum = Math.max.apply(null, [1].concat(state.sessions.map(function (run) { return count(run.scored) ? run.scored : 0; })));
    state.sessions.forEach(function (run, runIndex) {
      var item = button('', 'stock-replay-session-' + runIndex, function () { changeSelection(key(run)); });
      item.className = 'stock-replay__session';
      item.setAttribute('aria-pressed', key(run) === state.selected ? 'true' : 'false');
      item.setAttribute('aria-label', date(run.date) + (run.type ? ', ' + run.type : '') + ': ' + number(run.scored) + ' scored candidates');
      var plot = element('span', 'stock-replay__bar-track');
      plot.setAttribute('aria-hidden', 'true');
      var bar = element('span', 'stock-replay__bar');
      bar.style.height = (count(run.scored) ? run.scored / maximum * 100 : 0) + '%';
      plot.appendChild(bar);
      item.append(element('span', 'stock-replay__bar-number', count(run.scored) ? number(run.scored) : '—'), plot,
        element('span', 'stock-replay__bar-date', date(run.date, true)));
      rail.appendChild(item);
    });
    host.appendChild(rail);
  }

  function coherentRun() {
    if (!state.book) return null;
    var run = selected();
    var saved = state.book.runs.find(function (item) { return item && key(item) === key(run); });
    if (!saved) throw new Error('This session is missing from the detailed record. Refresh the page, then try again.');
    ['scored', 'bursts', 'passed_gate', 'shortlist_size', 'fallbacks', 'top_score'].forEach(function (field) {
      if (run[field] !== undefined && saved[field] !== undefined && run[field] !== saved[field]) {
        throw new Error('The page and detailed record contain different session counts. Refresh the page, then try again.');
      }
    });
    if (!Array.isArray(saved.candidates)) throw new Error('This session’s candidate list is unavailable in the saved record.');
    if (saved.candidates.some(function (row) {
      return !row || typeof row !== 'object' || typeof row.ticker !== 'string' || !row.ticker.trim() ||
        row.date !== saved.date || (row.forward_returns != null && (typeof row.forward_returns !== 'object' || Array.isArray(row.forward_returns)));
    })) throw new Error('The saved candidate details are incomplete or have an unsupported format.');
    if (count(run.scored) && saved.candidates.length !== run.scored) throw new Error('The candidate list does not match this session’s scored count. Refresh the page, then try again.');
    return saved;
  }

  function candidateCard(row) {
    var card = element('article', 'stock-replay__candidate');
    var header = element('div', 'stock-replay__candidate-head');
    header.append(element('h4', '', row.ticker), element('span', 'stock-replay__source', source(row)));
    var score = element('p', 'stock-replay__candidate-score');
    score.append(element('strong', '', finite(row.score) ? row.score.toFixed(1) : '—'), document.createTextNode(' / 10 recorded score'));
    var facts = element('dl', 'stock-replay__candidate-facts');
    facts.append(metric('Session gain', percentage(row.gain_pct)), metric('Relative volume', finite(row.volume_ratio) ? row.volume_ratio.toFixed(1) + '×' : 'Not recorded'),
      metric('Checks passed', count(row.lynch_passes) ? number(row.lynch_passes) + (count(row.lynch_total) ? ' / ' + number(row.lynch_total) : '') : 'Not recorded'));
    var returns = element('dl', 'stock-replay__returns');
    var record = row.forward_returns || {};
    if (basis() === 'open') record = record.from_open && typeof record.from_open === 'object' ? record.from_open : {};
    [1, 3, 5].forEach(function (horizon) { returns.appendChild(metric('+' + horizon + ' session' + (horizon === 1 ? '' : 's'), percentage(record['d' + horizon]))); });
    card.append(header, score, facts, element('p', 'stock-replay__returns-label', 'Subsequent returns · ' + basisLabel()), returns);
    return card;
  }

  function archiveDetails(host, run) {
    var details = element('div', 'stock-replay__details');
    details.id = 'stock-replay-details';
    var requested = state.requested.has(state.selected);
    var saved = null;
    var error = state.error;
    if (requested && state.book) {
      try { saved = coherentRun(); } catch (failure) { error = failure.message; }
    }
    if (state.book && (state.book.fixture === true || (saved && saved.fixture === true))) {
      details.appendChild(element('p', 'stock-replay__warning', 'Demo record: these archived candidate details are synthetic fixture data.'));
    }
    if (run.scored === 0) {
      details.appendChild(element('p', 'stock-replay__quiet', 'No scored candidates to replay for this session. The next recorded scan will appear here when it is published.'));
    } else if (saved) {
      var rows = saved.candidates.slice().sort(function (a, b) {
        var ar = count(a.rank) ? a.rank : Infinity;
        var br = count(b.rank) ? b.rank : Infinity;
        return ar - br || (finite(b.score) ? b.score : -Infinity) - (finite(a.score) ? a.score : -Infinity) || a.ticker.localeCompare(b.ticker);
      });
      var claude = rows.filter(function (row) { return row.source === 'claude'; }).length;
      var fallback = rows.filter(function (row) { return row.source === 'fallback'; }).length;
      var other = rows.length - claude - fallback;
      details.appendChild(element('p', 'stock-replay__provenance', claude + ' Claude · ' + fallback + ' fallback' + (other ? ' · ' + other + ' other / unspecified source' : '') + ' · saved candidate record'));
      details.appendChild(element('h3', 'stock-replay__details-title', 'Top recorded candidates'));
      var order = rows.every(function (row) { return count(row.rank); }) ? 'recorded rank order' : 'recorded score order where rank is unavailable';
      details.appendChild(element('p', 'stock-replay__note', 'Showing ' + Math.min(5, rows.length) + ' of ' + rows.length + ' scored candidates, in ' + order + '. Returns can fill in after a session; these are the latest saved observations, not an original historical page snapshot.'));
      var cards = element('div', 'stock-replay__candidates');
      rows.slice(0, 5).forEach(function (row) { cards.appendChild(candidateCard(row)); });
      details.appendChild(cards);
      if (!rows.length) details.appendChild(element('p', 'stock-replay__quiet', 'No candidate details were recorded for this session.'));
      details.appendChild(element('p', 'stock-replay__footnote', 'Candidate source: ledger.json · session ' + run.date + (state.book.generated ? ' · record generated ' + state.book.generated : '')));
    } else {
      if (requested && error) {
        var failure = element('p', 'stock-replay__warning', error);
        failure.setAttribute('role', 'status');
        details.appendChild(failure);
      } else {
        details.appendChild(element('p', 'stock-replay__note', 'Open the saved candidate record to see this session’s leaders, scoring sources and subsequent returns.'));
      }
      var load = button(state.loading ? 'Loading session record…' : (requested && error ? 'Retry session record' : 'Read session candidates'), 'stock-replay-load', loadBook);
      load.disabled = state.loading;
      load.setAttribute('aria-controls', details.id);
      details.setAttribute('aria-busy', state.loading ? 'true' : 'false');
      details.appendChild(load);
    }
    host.appendChild(details);
  }

  function paint(scroll) {
    var host = document.getElementById('stock-replay');
    if (!host) return;
    var focused = host.contains(document.activeElement) ? document.activeElement.id : null;
    host.replaceChildren();
    host.hidden = false;
    host.classList.add('stock-replay');
    host.setAttribute('aria-labelledby', 'stock-replay-title');
    var heading = element('div', 'stock-replay__heading');
    var titleGroup = element('div', '');
    titleGroup.append(element('p', 'sc-eyebrow sc-eyebrow--muted', 'The session archive'));
    var title = element('h2', '', 'Replay the tape.');
    title.id = 'stock-replay-title';
    titleGroup.appendChild(title);
    heading.append(titleGroup, element('p', 'stock-replay__count', state.sessions.length + ' recorded session' + (state.sessions.length === 1 ? '' : 's')));
    host.append(heading, element('p', 'stock-replay__intro', 'Travel through the saved scans. See what surfaced, what made the cut and what the record knows now.'));
    if (state.data && state.data.run && state.data.run.fixture === true) host.appendChild(element('p', 'stock-replay__warning', 'Demo snapshot: this session archive contains synthetic fixture data.'));
    if (!state.sessions.length) {
      host.appendChild(element('p', 'stock-replay__quiet', 'No recorded sessions yet. The archive begins when a scan is saved and published.'));
      return;
    }
    controls(host);
    var run = selected();
    var current = state.data.run && run.date === state.data.run.date && (!run.type || run.type === state.data.run.type);
    var summary = element('div', 'stock-replay__summary');
    var label = element('p', 'stock-replay__context', (current ? 'Current published session' : 'Archived session') + ' · ' + date(run.date));
    label.setAttribute('role', 'status');
    var sessionTitle = run.scored === 0 && run.status === 'ok' ? (run.bursts === 0 ? 'Quiet, on the record.' : 'No scored candidates.') : 'The session, in numbers.';
    summary.append(label, element('h3', 'stock-replay__session-title', sessionTitle),
      element('p', 'stock-replay__note', summaryNote(run)));
    if (run.dry_run === true) summary.appendChild(element('p', 'stock-replay__warning', 'This session was recorded as a dry run.'));
    var metrics = element('dl', 'stock-replay__metrics');
    metrics.append(metric('Universe scanned', number(run.universe && run.universe.size)), metric('4% bursts', number(run.bursts)),
      metric('Passed the gate', number(run.passed_gate)), metric('Scored', number(run.scored)), metric('Shortlist', number(run.shortlist_size)),
      metric('Top score', finite(run.top_score) ? run.top_score.toFixed(1) + ' / 10' : 'Not recorded'));
    summary.appendChild(metrics);
    var scoring = run.scored === 0 ? '0 Claude · 0 fallback' : count(run.fallbacks) ? number(run.fallbacks) + ' fallback score' + (run.fallbacks === 1 ? '' : 's') : 'Fallback count not recorded';
    summary.appendChild(element('p', 'stock-replay__footnote', 'Status: ' + (typeof run.status === 'string' ? run.status : 'not recorded') + ' · ' + scoring + ' · summary source: data.json · ' + run.date));
    host.appendChild(summary);
    archiveDetails(host, run);
    if (focused) {
      var replacement = document.getElementById(focused);
      if (replacement && !replacement.disabled) replacement.focus({ preventScroll: true });
      else if (replacement && replacement.disabled && focused !== 'stock-replay-load') document.getElementById('stock-replay-date').focus({ preventScroll: true });
    }
    if (scroll || !focused || focused === 'stock-replay-date') {
      var rail = host.querySelector('.stock-replay__rail');
      var active = rail.querySelector('[aria-pressed="true"]');
      if (active) rail.scrollLeft = active.offsetLeft - rail.offsetLeft - (rail.clientWidth - active.offsetWidth) / 2;
    }
  }

  function loadBook() {
    if (state.loading) return;
    state.requested.add(state.selected);
    state.error = '';
    if (state.book) {
      try { coherentRun(); paint(false); return; } catch (_) { state.book = null; }
    }
    state.loading = true;
    var request = ++state.request;
    var controller = new AbortController();
    state.controller = controller;
    var timedOut = false;
    var timeout = setTimeout(function () { timedOut = true; controller.abort(); }, 12000);
    paint(false);
    var url = new URL('ledger.json', window.location.href);
    fetch(url.href, { signal: controller.signal, cache: 'no-cache', credentials: 'same-origin' })
      .then(function (response) {
        if (!response.ok) throw new Error(response.status === 404 ? 'The detailed session record has not been published yet.' : 'The session record could not be loaded. Please try again.');
        return response.json();
      })
      .then(function (book) {
        if (request !== state.request) return;
        if (!book || book.schema_version !== 1 || book.app !== 'SpicyStock' || !Array.isArray(book.runs)) throw new Error('The session record uses an unsupported format. Refresh the page and try again.');
        // The ledger and dashboard stamp their writes independently. A newer
        // ledger can also contain newly observed returns for the same session.
        // coherentRun checks the session identity, counts and candidate dates;
        // generation timestamps are provenance, not snapshot identity.
        state.book = book;
      })
      .catch(function (error) {
        if (request !== state.request) return;
        state.error = timedOut ? 'The session record took too long to respond. Please try again.' : (error.message || 'The session record could not be loaded. Please try again.');
      })
      .finally(function () {
        clearTimeout(timeout);
        if (request !== state.request) return;
        state.loading = false;
        state.controller = null;
        paint(false);
      });
  }

  function render(data) {
    if (!data || typeof data !== 'object') return;
    var sessions = Array.isArray(data.runs) ? data.runs.filter(function (run) { return run && typeof run === 'object' && date(run.date); }) : [];
    var unique = new Map();
    sessions.forEach(function (run) { if (!unique.has(key(run))) unique.set(key(run), run); });
    sessions = Array.from(unique.values()).sort(function (a, b) { return key(a).localeCompare(key(b)); });
    var stamp = (data.generated || '') + '|' + JSON.stringify(data.run && [data.run.date, data.run.type, data.run.fixture]) + '|' + JSON.stringify(sessions);
    if (stamp !== state.stamp) {
      state.request += 1;
      if (state.controller) state.controller.abort();
      state.book = null;
      state.loading = false;
      state.error = '';
      state.requested.clear();
      state.stamp = stamp;
    }
    state.data = data;
    state.sessions = sessions;
    if (!sessions.some(function (run) { return key(run) === state.selected; })) {
      var current = data.run && sessions.find(function (run) { return key(run) === key(data.run); });
      state.selected = current ? key(current) : sessions.length ? key(sessions[sessions.length - 1]) : null;
    }
    paint(false);
  }

  window.SCStockReplay = { render: render };
}());
