"""tools/service_watch.py -- a watch on the service, not a reading of it.

GitHub starts this repository's scheduled runs hours after their slots (the
13 October 2026 schedule reading, and every night since), and until now
nothing said so when a night had not arrived: a publication that never came
looked exactly like one that was late. This asks two questions of the files
on disk and a clock, and answers each in one word and one sentence:

``evening``
    Has the session after the one ``docs/data.json`` covers been published?
    The answer is ``src/freshness.py``'s -- the five steps the page's own
    status chip walks, read off the record's calendar and delivery policy --
    and the watch adds one judgement to it: a publication that is still
    absent ``ALERT_WITHIN_HOURS`` before its recovery limit (the next
    session's open), or absent after it, is worth a person's attention, and
    so is a record more than one completed session behind. Late alone is
    not: every first publication from 22 September to 6 November 2026
    landed after both slots (the 7 November service reading).

``morning``
    Once the entry window the record names has closed: did a morning check
    for THIS record land inside its collection window? Read off
    ``docs/morning.json``: its binding to the record's bytes, its own
    generation instant and status, and how many of its ticket rows carried
    a recent price. A check that landed before the entry window opened and
    quoted nothing is said in those words and is not an alert: it is what a
    dispatch at 8:21 AM CT gives every morning. A record that published no
    ticket has nothing to quote, so its missing check is reported and never
    alerted.

It reads two files and decides nothing about them. It calls no provider, and
it mails only with ``--mail``, through the evening's own transport
(``report.deliver``), only when a judgement above says alert or the record
cannot be read at all. It keeps no memory, so every run that finds an alert
mails it: a late night can mail twice. A watch that
runs on GitHub's scheduler is itself late by hours, so the same two answers
are printed for anything else with a clock to run it: ``python
tools/service_watch.py --docs docs``.

Exit codes: 0 nothing to flag, 1 an alert, 2 the record could not answer.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import freshness  # noqa: E402  (standard library only; the mail transport is imported when asked for)

VERSION = 1
DATA_FILE = "data.json"
MORNING_FILE = "morning.json"
#: The files this reads are the publication's own; a larger one is not read at all.
MAX_RECORD_BYTES = 48 * 1024 * 1024        # reader.MAX_PUBLICATION_BYTES; tests hold the two equal
MAX_MORNING_BYTES = 512 * 1024             # morning.MAX_OBSERVATION_BYTES; tests hold the two equal

#: A publication still absent this many hours before its recovery limit is flagged.
#: Read off the landing commits on 19 November 2026: every first publication from
#: 19 October to 18 November landed more than nine hours before the next open, so
#: no night of that month would have been flagged.
ALERT_WITHIN_HOURS = 6
#: A missing publication is flagged for this long after its limit, then left: the
#: next evening's run replaces the record, and a watch that repeated itself until
#: then would say nothing new.
MISSING_ALERT_HOURS = 12
#: The same bound for a morning check that did not land.
MORNING_ALERT_HOURS = 12

# evening judgements
OK, LATE_NEAR_LIMIT, MISSING, UNKNOWN = "ok", "late_near_limit", "missing", "unknown"
# morning judgements
NOT_DUE, LANDED, NOT_LANDED = "not_due", "landed", "not_landed"

EXIT_OK, EXIT_ALERT, EXIT_UNKNOWN = 0, 1, 2

DISPATCH_HINT = ("Start it by hand: GitHub, Actions, Evening scan, Run workflow, branch main, with only_if_unpublished "
                 "ticked. From the session's primary slot (6:16 PM ET) on, it publishes the newest completed session "
                 "if it is still unpublished, and it does nothing otherwise.")
MISSING_HINT = ("The scheduled slots and a dispatch with only_if_unpublished ticked will not publish that session now. "
                "A plain dispatch of the Evening scan with the session box filled still can, and the tickets it writes "
                "would be for an entry window that may have ended. Read the evening workflow's runs for that evening, "
                "and treat every ticket in the record on the site as expired.")
BEHIND_HINT = ("More than one session has completed since the record on main. Read the Evening scan's runs: this is "
               "an outage, not a late night.")
UNREADABLE_SUBJECT = "SpicyStock watch: the record on main could not be read"
#: What a morning receipt's status must be for the check to count as one that ran for the record's tickets.
#: ``provider_unavailable`` and ``inapplicable`` (``src/morning.STATUSES``) quoted nothing and say so themselves.
RAN_STATUSES = ("observed", "partial", "no_tickets")
RECENT = "recent"
MORNING_HINT = ("The morning check is started from outside GitHub's scheduler (the owner's own dispatch of morning.yml). "
                "Look at that trigger's last run.")
LATE_ITSELF = ("This watch runs on GitHub's scheduler, which starts scheduled runs hours late, so it may itself have "
               "run late: read the clock it names.")
SUBJECT_EVENING = "SpicyStock watch: {session} is not published"
SUBJECT_MORNING = "SpicyStock watch: no morning check landed for {session}"


class Unreadable(ValueError):
    """A file the watch needs is absent, too large or not the JSON object it should be."""


def _instant(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def _hours(delta: timedelta) -> float:
    return round(delta.total_seconds() / 3600, 2)


def read_bytes(path: Path, maximum: int) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise Unreadable(f"{path.name} is not a regular file")
        size = path.stat().st_size
        if size > maximum:
            raise Unreadable(f"{path.name} is {size} bytes, over the {maximum} this watch reads")
        return path.read_bytes()
    except OSError as exc:
        raise Unreadable(f"{path.name} could not be read ({type(exc).__name__})") from exc


def decode(raw: bytes, name: str) -> dict:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise Unreadable(f"{name} is not JSON ({type(exc).__name__})") from exc
    if not isinstance(value, dict):
        raise Unreadable(f"{name} is not a JSON object")
    return value


def ticket_count(record: dict) -> int | None:
    """How many model tickets the record published, off its own funnel block
    (``src/funnel.py``); None when the record carries no readable count."""
    funnel = record.get("funnel")
    if not isinstance(funnel, dict):
        return None
    total = 0
    for family in ("reaction", "anticipation"):
        block = funnel.get(family)
        stages = block.get("stages") if isinstance(block, dict) else None
        count = stages.get("ticket") if isinstance(stages, dict) else None
        if type(count) is not int or count < 0:
            return None
        total += count
    return total


def sessions_behind(record: dict, covers_through, now: datetime) -> dict | None:
    """The sessions after the one the record covers that have completed by ``now``, read off the record's own
    calendar (``run.calendar.schedule.sessions``, each with its ``completion_at``): how many, the newest of them,
    and that one's own recovery limit (the open of the session after it). None when the record does not carry a
    schedule this can be read from."""
    run = record.get("run") if isinstance(record.get("run"), dict) else {}
    calendar = run.get("calendar") if isinstance(run.get("calendar"), dict) else {}
    schedule = calendar.get("schedule") if isinstance(calendar.get("schedule"), dict) else {}
    rows = schedule.get("sessions")
    if not isinstance(rows, list) or not isinstance(covers_through, str):
        return None
    later = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("session"), str):
            return None
        done, opens = _instant(row.get("completion_at")), _instant(row.get("opens_at"))
        if done is None or opens is None:
            return None
        if row["session"] > covers_through:
            later.append((row["session"], done, opens))
    later.sort()
    completed = [index for index, (_, done, _) in enumerate(later) if done <= now]
    if not completed:
        return {"count": 0, "newest": None, "newest_limit": None}
    newest = completed[-1]
    limit = later[newest + 1][2] if newest + 1 < len(later) else None
    return {"count": len(completed), "newest": later[newest][0],
            "newest_limit": limit.isoformat() if limit is not None else None}


def evening(record: dict, now: datetime) -> dict:
    """The freshness answer for the session after the one the record covers,
    and whether its absence is worth an alert."""
    expected = freshness.expected(record)
    answer = freshness.state(expected, now)
    session = expected.get("next_session")
    limit = _instant(expected.get("recovery_until"))
    hours = _hours(limit - now) if limit is not None else None
    behind = sessions_behind(record, expected.get("covers_through"), now)
    out = {"covers_through": expected.get("covers_through"), "next_session": session,
           "state": answer["state"], "state_sentence": answer["sentence"],
           "recovery_until": expected.get("recovery_until"), "hours_to_limit": hours,
           "sessions_behind": behind,
           "judgement": OK, "sentence": answer["sentence"], "alert": False, "action": None}
    if answer["state"] == freshness.UNKNOWN:
        out["judgement"] = UNKNOWN
    elif answer["state"] == freshness.MISSING:
        out["judgement"] = MISSING
        out["sentence"] = (f"The {session} session was not published before the session after it opened "
                           f"({expected.get('recovery_until')}), and the service will not publish it now. The record "
                           f"on main still covers {out['covers_through']}.")
        # the limit is known here: state() answers missing only past it
        out["alert"] = limit is not None and now - limit < timedelta(hours=MISSING_ALERT_HOURS)
        out["action"] = MISSING_HINT
        if behind is not None and behind["count"] > 1:
            # A second night in a row never gets its own "missing": the record still names the first one. The
            # newest completed session is judged by the first night's own rule: near its limit, or just past it.
            out["sentence"] += (f" {behind['count']} sessions have completed since {out['covers_through']} and none "
                                f"of them is published; the newest is {behind['newest']}.")
            newest_limit = _instant(behind["newest_limit"])
            if newest_limit is not None and newest_limit - now <= timedelta(hours=ALERT_WITHIN_HOURS) \
                    and now - newest_limit < timedelta(hours=MISSING_ALERT_HOURS):
                out["alert"] = True
            # MISSING_HINT is about the first missed session; the newest can still be published until its limit
            if newest_limit is not None and now < newest_limit:
                out["action"] = (f"{BEHIND_HINT} The newest, {behind['newest']}, can still be published: "
                                 f"{DISPATCH_HINT} The first, {session}: {MISSING_HINT}")
            else:
                out["action"] = f"{BEHIND_HINT} The first, {session}: {MISSING_HINT}"
    elif (answer["state"] in (freshness.PENDING, freshness.LATE) and limit is not None
          and limit - now <= timedelta(hours=ALERT_WITHIN_HOURS)):
        # the limit decides, not the state word: a record with no readable delivery policy stays `pending` until
        # its limit, and is as unpublished as a late one
        out["judgement"] = LATE_NEAR_LIMIT
        slots = ("Both scheduled slots have passed" if answer["state"] == freshness.LATE
                 else "It completed and its publication is still pending")
        out["sentence"] = (f"The {session} session is not published yet. {slots} and the "
                           f"session after it opens at {expected.get('recovery_until')}, {hours:g} hours after this "
                           "watch's clock; after that the scheduled service will not publish it.")
        out["alert"] = True
        out["action"] = DISPATCH_HINT
    return out


def _measured(record: dict):
    run = record.get("run") if isinstance(record.get("run"), dict) else {}
    return run.get("session")


def morning(record: dict, record_raw: bytes, receipt: dict | None, receipt_problem: str | None, now: datetime) -> dict:
    """Whether a morning check for this record landed inside its collection
    window, once that window has closed."""
    window = freshness.morning_window(record)
    session = window.get("applicable_session")
    tickets = ticket_count(record)
    out = {"applicable_session": session, "collection_starts_at": window.get("collection_starts_at"),
           "window_cutoff_at": window.get("window_cutoff_at"), "tickets": tickets,
           "judgement": UNKNOWN, "sentence": None, "alert": False, "action": None, "receipt": None}
    start, cutoff = _instant(window.get("collection_starts_at")), _instant(window.get("window_cutoff_at"))
    if window.get("unknown") or start is None or cutoff is None:
        out["sentence"] = f"The morning check cannot be judged: {window.get('unknown') or 'the record gives no entry window'}."
        return out
    if now < cutoff:
        out["judgement"] = NOT_DUE
        out["sentence"] = (f"The entry window for {session} closes at {window['window_cutoff_at']}; a morning check is "
                           "judged after that.")
        return out
    wanted = hashlib.sha256(record_raw).hexdigest()
    problem = receipt_problem
    generated = None
    if receipt is not None:
        publication = receipt.get("publication")
        bound = publication.get("data_sha256") if isinstance(publication, dict) else None
        generated = _instant(receipt.get("generated_at"))
        status = receipt.get("status") if isinstance(receipt.get("status"), str) else None
        rows = [r for r in receipt.get("rows", []) if isinstance(r, dict)] if isinstance(receipt.get("rows"), list) else []
        recent = sum(1 for r in rows if any(isinstance(r.get(side), dict) and r[side].get("status") == RECENT
                                            for side in ("trade", "quote")))
        opens = _instant(window.get("window_opens_at"))
        same_session = (isinstance(publication, dict)
                        and publication.get("measured_session") == _measured(record)
                        and publication.get("applicable_session") == session)
        out["receipt"] = {"generated_at": receipt.get("generated_at") if generated else None,
                          "status": status, "bound_to_this_record": bound == wanted,
                          "same_session_other_publication": bound != wanted and bool(same_session),
                          "before_window_opened": bool(generated and opens and generated < opens),
                          "ticket_rows": len(rows), "rows_with_recent_price": recent}
        if bound != wanted and same_session and generated is not None and start <= generated <= cutoff \
                and receipt.get("dry_run") is False and status in RAN_STATUSES:
            # the session was published again after the morning: the check that landed was for the earlier
            # publication of the same session, and saying none landed would be false
            out["judgement"] = LANDED
            out["sentence"] = (f"A morning check for {session} landed inside its collection window, generated "
                               f"{receipt['generated_at']} (status {status}), for an earlier publication of this "
                               "session: the record on main was published again after it.")
            return out
        if bound != wanted:
            problem = "the morning file on disk is bound to another publication"
        elif generated is None:
            problem = "the morning file names no generation instant"
        elif generated < start:
            problem = f"the morning file was generated at {receipt['generated_at']}, before the collection window opened"
        elif generated > cutoff:
            problem = f"the morning file was generated at {receipt['generated_at']}, after the entry window closed"
        elif receipt.get("dry_run") is not False:
            problem = "the morning file is a rehearsal"
        elif status not in RAN_STATUSES:
            problem = f"the morning file says status {status!r}: it quoted nothing"
    if problem is None:
        seen = out["receipt"]
        out["judgement"] = LANDED
        out["sentence"] = (f"A morning check for {session} landed inside its collection window, generated "
                           f"{receipt['generated_at']} (status {seen['status']})")
        if tickets:
            out["sentence"] += (f"; it was generated {'before' if seen['before_window_opened'] else 'after'} the entry "
                                f"window opened, and {seen['rows_with_recent_price']} of its {seen['ticket_rows']} ticket "
                                f"row{'' if seen['ticket_rows'] == 1 else 's'} carried a recent price")
        out["sentence"] += "."
        return out
    out["judgement"] = NOT_LANDED
    counted = ("the record does not say how many tickets it published" if tickets is None
               else f"the record published {tickets} ticket{'' if tickets == 1 else 's'}")
    out["sentence"] = f"No morning check for {session} landed inside its collection window: {problem}; {counted}."
    # a record with no ticket has nothing to quote: reported, never alerted
    out["alert"] = bool(tickets) and now - cutoff < timedelta(hours=MORNING_ALERT_HOURS)
    out["action"] = MORNING_HINT if out["alert"] else None
    return out


def watch(docs: Path, now: datetime) -> dict:
    """Both answers for the files under ``docs`` at ``now`` (an aware instant)."""
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("the watch needs its clock as an instant with an offset")
    record_raw = read_bytes(docs / DATA_FILE, MAX_RECORD_BYTES)
    record = decode(record_raw, DATA_FILE)
    receipt, receipt_problem = None, None
    try:
        receipt = decode(read_bytes(docs / MORNING_FILE, MAX_MORNING_BYTES), MORNING_FILE)
    except Unreadable as exc:
        receipt_problem = str(exc)
    first = evening(record, now)
    second = morning(record, record_raw, receipt, receipt_problem, now)
    return {"version": VERSION, "clock": now.astimezone(timezone.utc).isoformat(),
            "record_sha256": hashlib.sha256(record_raw).hexdigest(),
            "evening": first, "morning": second,
            "alert": first["alert"] or second["alert"],
            "exit_code": (EXIT_ALERT if first["alert"] or second["alert"]
                          else EXIT_UNKNOWN if first["judgement"] == UNKNOWN else EXIT_OK)}


def lines(result: dict) -> list[str]:
    """The result as the run log prints it."""
    first, second = result["evening"], result["morning"]
    out = [f"Service watch at {result['clock']}.",
           f"Evening: {first['judgement']} ({first['state']}). {first['sentence']}"]
    if first["action"]:
        out.append(f"  {first['action']}")
    out.append(f"Morning: {second['judgement']}. {second['sentence']}")
    if second["action"]:
        out.append(f"  {second['action']}")
    out.append("Alert." if result["alert"] else "Nothing to flag.")
    return out


def messages(result: dict) -> list[tuple[str, str]]:
    """(subject, HTML body) for each alert the result carries; none otherwise."""
    out = []
    for block, subject, session in ((result["evening"], SUBJECT_EVENING, result["evening"]["next_session"]),
                                    (result["morning"], SUBJECT_MORNING, result["morning"]["applicable_session"])):
        if not block["alert"]:
            continue
        paragraphs = [block["sentence"], block["action"], f"Watch clock: {result['clock']}. {LATE_ITSELF}"]
        body = "".join(f"<p>{html.escape(text)}</p>" for text in paragraphs if text)
        out.append((subject.format(session=session or "the next session"), body))
    return out


def mail(result: dict) -> int:
    """Send each alert through the evening's own transport. Returns how many went."""
    pending = messages(result)
    if not pending:
        return 0
    from src import report  # the one send path; imported only when a message is owed
    for subject, body in pending:
        report.deliver(subject, body)
    return len(pending)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Is the evening publication late or missing, and did the morning check land?")
    parser.add_argument("--docs", type=Path, default=ROOT / "docs")
    parser.add_argument("--now", help="the clock to judge by, ISO-8601 with an offset (default: this machine's clock)")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    parser.add_argument("--mail", action="store_true", help="mail each alert through the evening's transport")
    args = parser.parse_args(argv)
    now = _instant(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        print("--now is not an instant with an offset", file=sys.stderr)
        return EXIT_UNKNOWN
    try:
        result = watch(args.docs, now)
    except Unreadable as exc:
        print(f"Service watch: {exc}.", file=sys.stderr)
        if args.mail:
            # the state in which the site itself can show no record: a person should hear of it
            from src import report
            report.deliver(UNREADABLE_SUBJECT,
                           "".join(f"<p>{html.escape(text)}</p>" for text in (
                               f"The record on main could not be read: {exc}.",
                               f"Watch clock: {now.astimezone(timezone.utc).isoformat()}. {LATE_ITSELF}")))
            print("Mailed 1 alert.", file=sys.stderr)
        return EXIT_UNKNOWN
    print(json.dumps(result, indent=1, sort_keys=True) if args.json else "\n".join(lines(result)))
    if args.mail and result["alert"]:
        sent = mail(result)
        print(f"Mailed {sent} alert{'' if sent == 1 else 's'}.", file=sys.stderr)
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
