"""src.delivery -- when the evening publication landed, against the service's own schedule.

The record already says WHICH session it measured and WHEN its plans apply
(`run.timing`, `run.calendar`). It did not say how the publication itself
fared against the service that produces it: how long after the session's
completion it landed, whether before or after the evening workflow's two
scheduled slots, and whether before the next session's open -- the instant
past which the workflow's own guard refuses to publish a missed session at
all. The page used to answer the last question with a hard-coded hour; it
reads this block and the calendar now, and the service-health reading reads
the same slot rule, so the three cannot disagree.

Facts, not verdicts: this block says where a publication fell. Whether that
is "late" is the reader's word, and the page's state words carry it.
"""

from __future__ import annotations

from datetime import date, datetime, time as time_of_day
from typing import Any, Mapping

from src import sessions
from src.sessions import MARKET_TZ, MARKET_TZ_NAME

VERSION = 1

#: The evening workflow's nominal slots as wall clock in the exchange's zone.
#: `evening.yml` spells each as a PAIR of crons, one per UTC offset, and
#: `tests/test_workflows.py` holds the four crons to these two times, so the
#: workflow and the record describe one schedule. Not strategy numbers: the
#: service's own (P).
EVENING_PRIMARY_ET = time_of_day(18, 16)
EVENING_RETRY_ET = time_of_day(20, 16)

#: The guard's own recovery window, named: a delayed or retried run may
#: publish a missed session until the next session opens, and never after
#: (`evening.yml`'s guard; rehearsed in `tools/recovery_rehearsal.py`). The
#: page keeps one sentence per key here, held equal by tests/test_docs.py.
RECOVERY_NEXT_OPEN = "next_session_open"
RECOVERY_POLICIES: tuple[str, ...] = (RECOVERY_NEXT_OPEN,)

#: Where a publication fell against the two slots.
SLOT_BEFORE_PRIMARY = "before_primary"
SLOT_AFTER_PRIMARY = "after_primary"
SLOT_AFTER_RETRY = "after_retry"
SLOTS: tuple[str, ...] = (SLOT_BEFORE_PRIMARY, SLOT_AFTER_PRIMARY, SLOT_AFTER_RETRY)

FIELDS = frozenset({"version", "session", "completion_at", "published_at", "latency_minutes", "primary_slot_at",
                    "retry_slot_at", "after_primary_minutes", "slot", "next_session", "next_open_at",
                    "before_next_open", "policy", "sentence"})
POLICY_FIELDS = frozenset({"timezone", "primary_et", "retry_et", "recovery_until"})

#: Archived beside the pipeline's rules (`pipeline.RULES`), so a record made
#: under another schedule cannot be read as one made under this one, and the
#: validator holds a record's block to the slots IT archived.
RULES: dict[str, Any] = {
    "pipeline.delivery_version": VERSION,
    "pipeline.delivery_primary_et": EVENING_PRIMARY_ET.isoformat(timespec="minutes"),
    "pipeline.delivery_retry_et": EVENING_RETRY_ET.isoformat(timespec="minutes"),
    "pipeline.delivery_recovery_until": RECOVERY_NEXT_OPEN,
}


def slots(session: date, primary_et: time_of_day = EVENING_PRIMARY_ET,
          retry_et: time_of_day = EVENING_RETRY_ET) -> tuple[datetime, datetime]:
    """The two slots on ``session`` as aware instants in the exchange's zone,
    so the November change is the tz database's answer and no UTC hour is
    written anywhere: 6:16 PM ET is 22:16 UTC on EDT and 23:16 UTC on EST,
    the two crons the workflow carries for one slot."""
    return (datetime.combine(session, primary_et, tzinfo=MARKET_TZ),
            datetime.combine(session, retry_et, tzinfo=MARKET_TZ))


def minutes_between(later: datetime, earlier: datetime) -> float:
    """Signed minutes, rounded once to a tenth."""
    return round((later - earlier).total_seconds() / 60, 1)


def block(session: date, published_at: str, *, primary_et: time_of_day = EVENING_PRIMARY_ET,
          retry_et: time_of_day = EVENING_RETRY_ET) -> dict[str, Any]:
    """The serialized block for a publication of ``session`` generated at
    ``published_at`` (the run's own clock, an ISO-8601 instant WITH an offset;
    it is copied in verbatim so the block and ``run.published_at`` cannot
    differ by a spelling). Instants the block adds are in the exchange's zone
    with their offsets, as ``run.timing``'s are."""
    sessions.require_session(session)
    published = _aware(published_at)
    if published is None:
        raise ValueError(f"published_at {published_at!r} is not an ISO-8601 instant with an offset")
    completion = sessions.completion_at(session)
    primary, retry = slots(session, primary_et, retry_et)
    following = sessions.next_sessions(session, 1)[0]
    next_open = sessions.hours(following)[0]
    slot = (SLOT_BEFORE_PRIMARY if published < primary else
            SLOT_AFTER_PRIMARY if published < retry else SLOT_AFTER_RETRY)
    out = {
        "version": VERSION,
        "session": session.isoformat(),
        "completion_at": completion.isoformat(),
        "published_at": published_at,
        "latency_minutes": minutes_between(published, completion),
        "primary_slot_at": primary.isoformat(),
        "retry_slot_at": retry.isoformat(),
        "after_primary_minutes": minutes_between(published, primary),
        "slot": slot,
        "next_session": following.isoformat(),
        "next_open_at": next_open.isoformat(),
        "before_next_open": published < next_open,
        "policy": {"timezone": MARKET_TZ_NAME,
                   "primary_et": primary_et.isoformat(timespec="minutes"),
                   "retry_et": retry_et.isoformat(timespec="minutes"),
                   "recovery_until": RECOVERY_NEXT_OPEN},
    }
    out["sentence"] = sentence(out)
    return out


def sentence(b: Mapping[str, Any]) -> str:
    """Where the publication fell, in words a reader can check against the
    block's own instants. Facts only: no "late", no promise about the next one."""
    published = _aware(b["published_at"])
    completion, primary, retry, next_open = (_aware(b[k]) for k in ("completion_at", "primary_slot_at", "retry_slot_at", "next_open_at"))
    if None in (published, completion, primary, retry, next_open):
        raise ValueError("delivery block carries an instant without an offset")
    latency = b["latency_minutes"]
    when = (f"{_minutes(latency)} after the measured session's completion ({_clock(completion)})" if latency >= 0
            else f"{_minutes(-latency)} before the measured session's completion ({_clock(completion)})")
    slot = {SLOT_BEFORE_PRIMARY: f"before the primary slot ({_clock(primary)})",
            SLOT_AFTER_PRIMARY: f"after the primary slot ({_clock(primary)}) and before the retry slot ({_clock(retry)})",
            SLOT_AFTER_RETRY: f"after both scheduled slots ({_clock(primary, zone=False)} and {_clock(retry)})"}[b["slot"]]
    where = "before" if b["before_next_open"] else "after"
    return (f"Published {_clock(published)} on {_day(published)}, {when}; {slot}; "
            f"{where} the next session's open ({_day(next_open)}, {_clock(next_open)}).")


def faults(run: Mapping[str, Any], pipeline_rules: Any) -> list[str]:
    """``run.delivery`` held to the record it sits in: present under rules that
    write it, and equal to what the archived slots re-derive from the run's own
    session and publication instant. A record made under older rules is not
    asked for one, and a version this code does not know is named, not guessed."""
    if not isinstance(pipeline_rules, Mapping) or "delivery_version" not in pipeline_rules:
        return []
    b = run.get("delivery") if isinstance(run, Mapping) else None
    if b is None:
        return ["run.delivery is missing"]
    try:
        if pipeline_rules["delivery_version"] != VERSION:
            return [f"run.delivery archived version {pipeline_rules['delivery_version']!r} is not one this code re-derives"]
        if not isinstance(b, Mapping) or set(b) != FIELDS or not isinstance(b.get("policy"), Mapping) \
                or set(b["policy"]) != POLICY_FIELDS:
            return ["run.delivery is malformed"]
        again = block(date.fromisoformat(run["session"]), run["published_at"],
                      primary_et=time_of_day.fromisoformat(pipeline_rules["delivery_primary_et"]),
                      retry_et=time_of_day.fromisoformat(pipeline_rules["delivery_retry_et"]))
        if pipeline_rules.get("delivery_recovery_until") != b["policy"]["recovery_until"] \
                or b["policy"]["recovery_until"] not in RECOVERY_POLICIES:
            return ["run.delivery recovery policy is not the archived one"]
        differing = sorted(k for k in FIELDS if b[k] != again[k])
        if differing:
            return ["run.delivery does not re-derive from the run's session, publication instant and archived slots: "
                    + ", ".join(differing)]
    except (KeyError, TypeError, ValueError, AttributeError):
        return ["run.delivery is malformed"]
    return []


def _aware(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _clock(dt: datetime, *, zone: bool = True) -> str:
    et = dt.astimezone(MARKET_TZ)
    hour = et.hour % 12 or 12
    return f"{hour}:{et.minute:02d} {'AM' if et.hour < 12 else 'PM'}" + (" ET" if zone else "")


def _day(dt: datetime) -> str:
    et = dt.astimezone(MARKET_TZ)
    return f"{et.strftime('%a')} {et.day} {et.strftime('%b')}"


def _minutes(m: float) -> str:
    whole = int(m) if float(m).is_integer() else m
    return f"{whole:,} minute{'' if whole == 1 else 's'}"
