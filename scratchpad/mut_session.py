"""Mutants over the rules this milestone added to the page, judged by the two
new smoke suites. Each deletes or inverts ONE rule and must turn a suite red;
a survivor is a hole in the checks, not a passing mutant."""
import pathlib, subprocess, sys, time

APP = pathlib.Path('docs/app.js')

MUTANTS = [
 # --- the phase rule itself
 ("the window stays open AT its cutoff",
  "    return t < tm.cutoff.getTime() ? 'open' : 'ended';",
  "    return t <= tm.cutoff.getTime() ? 'open' : 'ended';", "session"),
 ("the window opens a minute early",
  "    if (t < tm.opens.getTime()) return 'upcoming';",
  "    if (t < tm.opens.getTime() - 60000) return 'upcoming';", "session"),
 ("an ended window still offers the order",
  "    const timingBlocked = ph === 'ended' || ph === 'unknown';",
  "    const timingBlocked = ph === 'unknown';", "session"),
 ("an unknown window is treated as permission",
  "    const timingBlocked = ph === 'ended' || ph === 'unknown';",
  "    const timingBlocked = ph === 'ended';", "session"),
 ("timing WIDENS: a stale page becomes actionable in an open window",
  "      offered: !pubBlocked && !timingBlocked, reason: '', lead: '', word: PHASE_WORDS[ph], tone: PHASE_TONE[ph] };",
  "      offered: ph === 'open' || (!pubBlocked && !timingBlocked), reason: '', lead: '', word: PHASE_WORDS[ph], tone: PHASE_TONE[ph] };", "session"),
 ("the clock refuses nothing before a copy",
  "    return nowAv.offered ? null : nowAv.reason;",
  "    return null;", "session"),
 ("the copy guard reads the answer the surface was drawn with",
  "    const nowAv = clockPinned ? av : availability(current, new Date());",
  "    const nowAv = av;", "session"),
 ("a half-written window is compared against anyway",
  "    out.known = !out.faults.length;",
  "    out.known = !!(out.session && out.opens && out.cutoff);", "session"),
 ("an instant with no offset is accepted",
  "    if (!/[+-]\\d\\d:?\\d\\d$|Z$/.test(value)) return null;",
  "    if (false) return null;", "session"),
 ("the next action names the preparation reminder whatever the clock",
  "    if (ph === 'ended') {",
  "    if (false) {", "session"),
 ("the ticket sheet keeps its rows past the window",
  "    const rows = offered ? withOrders : [];",
  "    const rows = !pubBlockedSheet ? withOrders : [];", "session"),
 ("the recorded ticket is hidden rather than kept readable",
  "    if (c.status === 'ticket' && av.timingBlocked && plan.order_json) kids.push(recordedTicket(plan, av));",
  "    if (false) kids.push(recordedTicket(plan, av));", "session"),
 ("the clock is never re-read while the tab sits open",
  "    clockTimer = w.setInterval(() => { if (!d.hidden) reclock(); }, CLOCK_TICK_MS);",
  "    clockTimer = null;", "session"),
 ("a re-reading tears the chart down",
  "    reclockDetail();",
  "    state.detailKey = null; renderDetail();", "session"),
 ("a repaint drops the reader's focus on the body",
  "    const back = (key && next.querySelector(key)) ||\n      next.querySelector('summary, button, [href], input') || next;",
  "    const back = key && next.querySelector(key);\n    if (!back) return next;", "session"),
 ("the two clocks share one chip",
  "      'plan', chip(tm.known ? 'entry window ' + PHASE_WORDS[av.phase] : 'entry timing unavailable', tm.known ? PHASE_TONE[av.phase] : 'warn'));",
  "      'plan');", "session"),
 # --- the update check
 ("an older record is applied backwards",
  "    if (there < here) { saidUpdate('older'); return; }",
  "    if (false) { saidUpdate('older'); return; }", "refresh"),
 ("a re-publish of the same session reads as unchanged",
  "    if (sameBytes(raw)) { saidUpdate('unchanged'); return; }",
  "    if (current && current.run && JSON.parse(raw).run.session === current.run.session && JSON.parse(raw).run.published_at === current.run.published_at) { saidUpdate('unchanged'); return; }", "refresh"),
 ("a stale answer lands over a newer one",
  "      .then((raw) => { if (seq === updateSeq) applyUpdate(raw); })",
  "      .then((raw) => { applyUpdate(raw); })", "refresh"),
 ("a record the page cannot read is loaded anyway",
  "    if (timingFaults(next).length) { saidUpdate('invalid'); return; }",
  "    if (false) { saidUpdate('invalid'); return; }", "refresh"),
 ("a load forgets where the reader was",
  "      if (keep.stage) state.stage = keep.stage;",
  "      if (false) state.stage = keep.stage;", "refresh"),
 ("a lost comparison is not explained",
  "    if (keep.pins.length) lost.push(keep.pins.length === 2 && keep.comparing",
  "    if (false) lost.push(keep.pins.length === 2 && keep.comparing", "refresh"),
 ("a half-typed reference size is thrown away",
  "    if (keep) { restoreSizeForm(keep.sizeForm); if (keep.scroll) w.scrollTo(0, keep.scroll); }",
  "    if (keep) { if (keep.scroll) w.scrollTo(0, keep.scroll); }", "refresh"),
 # --- a CONTROL: a rule neither suite names
 ("CONTROL: the footer's own separator",
  " · paper prices, one venue’s prints, no slippage · not investment advice",
  " | paper prices, one venue’s prints, no slippage | not investment advice", "session"),
]

def run(suite):
    r = subprocess.run(['node', 'tools/page_smoke.mjs', '--only', suite],
                       capture_output=True, text=True, timeout=900)
    tail = [l for l in r.stdout.strip().splitlines() if 'passed' in l]
    return (tail[-1] if tail else r.stdout.strip()[-160:]), r.returncode

which = sys.argv[1] if len(sys.argv) > 1 else None
src = APP.read_text()
for label, old, new, suite in MUTANTS:
    if which and which not in label:
        continue
    if src.count(old) != 1:
        print(f"  SKIP  [{suite}] {label}: pattern appears {src.count(old)}x"); continue
    APP.write_text(src.replace(old, new))
    t0 = time.time()
    try:
        line, code = run(suite)
    finally:
        APP.write_text(src)
    print(f"  {'DEAD ' if code else 'ALIVE'} [{suite}] {label}\n        {line}  ({time.time()-t0:.0f}s)")
