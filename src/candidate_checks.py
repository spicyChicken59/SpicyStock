"""SEC, earnings and second-source checks on the night's candidates (``candidate_checks``).

The tickets' own checks (``run.earnings``, ``run.sec_flags``, ``run.cross_check``)
read the names the record publishes an order or a listed setup for. This block
reads the same three things for up to ``MAX_NAMES`` names, taken in ``ROLES``
order and unique by stage and ticker: every ticket, every listed setup, every
burst the review selected, every burst whose mechanical grade is in the
archived trade band with no quality veto that the discovery admission admits
(each in the record's rank order), then the also-quiet coils. Names past the
bound are counted by role and get no row.

Each row is built by the modules' own pure functions over the night's ONE SEC
reader (``SecReader``: every URL asked once and its answer kept, the tickets
read first, a deadline from its first request and the issuer transport's
request budget over the whole night) and one iex batch of its own
(``read_iex()`` over ``cross_symbols()``, retried once as every bars request
is; the tickets' cross-check keeps its own request): the earnings estimate and
the recent current reports
(``earnings_risk.read_row()``), the merger, tender and deal filings
(``sec_flags.read_name()``) and the signal-day bar read again
(``cross_check.compare()``). A name with a row in ``run.earnings``,
``run.sec_flags`` or ``run.cross_check`` carries that row's reading, so the
two never disagree; the validator holds them equal.

Policy ``flag_only``: it changes no plan, ticket, funnel stage, cash budget or
``orders.json`` field, it is collected after every plan and the allocation are
final, and it never fails a night. A name it could not read is unknown, and
unknown is never clear. It reads what a filing is and an estimate of a report
date, never company news; only the manual event registry withholds a ticket.
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from src import cross_check, earnings_risk, issuer_evidence, sec_flags

VERSION = 1
VERSIONS = (1,)              # the versions a record can archive and this module can read
POLICY = "flag_only"
#: (P) the names one night reads, the tickets first so they always have a row
MAX_NAMES = 80
#: the roles a name is taken under, in the order they are taken
ROLES = ("ticket", "listed", "reviewed", "candidate", "also_quiet")
#: (P) seconds from the night's first SEC request in which the shared reader begins requests
DEADLINE_SECONDS = 150
#: the issuer transport's own request budget, over the whole night's SEC reads
MAX_REQUESTS = issuer_evidence.MAX_REQUESTS
#: (P) the block's compact bytes; past it, rows no run.* row stands behind are shed to not checked, from the end
MAX_BLOCK_BYTES = 256 * 1024
#: (P) the newest flagged SEC filings a row keeps, with the count beside them
MAX_FILINGS = 4
#: (P) the material 8-K items a row keeps, with the count beside them
MAX_MATERIAL = 4
#: (P) names the block's sentence lists for each kind of flag, with the count beside them
SENTENCE_NAMES = 3
#: the earnings verdicts that put a report near a next-session hold: the ones a reader is warned of
EARNINGS_FLAGS = ("reported_after_signal", "estimate_inside", "estimate_near", "overdue")
STATUSES = ("not_applicable", "checked", "partial", "unavailable")
RULES = {"candidate_checks.version": VERSION, "candidate_checks.policy": POLICY,
         "candidate_checks.max_names": MAX_NAMES, "candidate_checks.roles": list(ROLES),
         "candidate_checks.deadline_seconds": DEADLINE_SECONDS, "candidate_checks.max_requests": MAX_REQUESTS,
         "candidate_checks.max_block_bytes": MAX_BLOCK_BYTES, "candidate_checks.max_filings": MAX_FILINGS,
         "candidate_checks.max_material": MAX_MATERIAL, "candidate_checks.sentence_names": SENTENCE_NAMES,
         "candidate_checks.unknown_policy": "never_clearance"}

ROLE_WORDS = {"ticket": ("ticket", "tickets"), "listed": ("listed setup", "listed setups"),
              "reviewed": ("reviewed burst", "reviewed bursts"),
              "candidate": ("discovery-admitted {band} burst", "discovery-admitted {band} bursts"),
              "also_quiet": ("also-quiet coil", "also-quiet coils")}
BLOCK_KEYS = {"version", "policy", "session", "since", "max_names", "names", "unchecked", "rows", "shed",
              "requests", "status", "sentence"}
ROW_KEYS = {"stage", "ticker", "role", "rank", "cik", "source", "sec", "earnings", "items", "cross_check"}
SEC_KEYS = {"state", "reason", "filings", "filings_count"}
EARNINGS_KEYS = {"verdict", "reason", "error", "placement", "projection", "observed", "sentence"}
ITEMS_KEYS = {"status", "reason", "material", "material_count", "codes", "count", "unread", "after_hold",
              "unretained_material"}
CROSS_KEYS = {"result", "reason", "differences"}
SOURCE_KEYS = {"sha256", "bytes", "retrieved_at"}
REQUEST_KEYS = {"sec", "sec_reused", "iex"}
NOT_CHECKED = "not_checked"


class IexBatchFailed(RuntimeError):
    """The night's iex batch failed twice and the bars endpoint dropped it."""


# ------------------------------------------------------------ the names ---
def _rank(row) -> int | None:
    value = row.get("rank") if isinstance(row, dict) else None
    return value if type(value) is int else None


def names_of(bursts, trades, watchlist, trade_grades) -> list[dict]:
    """Every name the night checks, in ``ROLES`` order, unique by stage and
    ticker: the tickets (``earnings_risk.tickets_of()``), the listed setups, the
    bursts the review selected, the admitted bursts in the trade band without
    a veto, then the also-quiet coils. A burst's rank is the record's; a setup's
    is its place in its list. Never raises over a shape a record should not carry."""
    from src import admission
    rows = [b for b in bursts if isinstance(b, dict) and isinstance(b.get("ticker"), str)] \
        if isinstance(bursts, list) else []
    watch = watchlist if isinstance(watchlist, dict) else {}
    lists = {k: [r for r in (watch.get(k) if isinstance(watch.get(k), list) else [])
                 if isinstance(r, dict) and isinstance(r.get("ticker"), str)] for k in ("top", "also_quiet")}
    grades = tuple(g for g in trade_grades if isinstance(g, str)) if isinstance(trade_grades, list) else ()
    by_ticker: dict = {}
    for b in rows:
        by_ticker.setdefault(b["ticker"], b)
    places: dict = {}
    for i, r in enumerate(lists["top"], 1):
        places.setdefault(r["ticker"], i)
    out: list[dict] = []
    seen: set = set()

    def add(stage, ticker, role, rank):
        if (stage, ticker) not in seen:
            seen.add((stage, ticker))
            out.append({"stage": stage, "ticker": ticker, "role": role, "rank": rank})

    for t in earnings_risk.tickets_of(rows, trades, lists["top"]):
        add(t["stage"], t["ticker"], "ticket",
            _rank(by_ticker.get(t["ticker"])) if t["stage"] == "burst" else places.get(t["ticker"]))
    for i, r in enumerate(lists["top"], 1):
        add("anticipation", r["ticker"], "listed", i)
    ordered = [b for _, b in sorted(enumerate(rows), key=lambda ib: (_rank(ib[1]) is None, _rank(ib[1]) or 0, ib[0]))]
    for b in ordered:
        if isinstance(b.get("review_selection"), dict) and b["review_selection"].get("selected") is True:
            add("burst", b["ticker"], "reviewed", _rank(b))
    for b in ordered:
        if b.get("grade_mechanical") in grades and not b.get("vetoes") and admission.admitted(b):
            add("burst", b["ticker"], "candidate", _rank(b))
    for i, r in enumerate(lists["also_quiet"], 1):
        add("anticipation", r["ticker"], "also_quiet", i)
    return out


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def record_names(data: dict) -> list[dict]:
    """``names_of()`` over a record, with the trade band its rules archived."""
    pipeline = _dict(_dict(data.get("rules")).get("pipeline"))
    return names_of(data.get("bursts"), data.get("trades"), data.get("watchlist"), pipeline.get("trade_grades"))


def symbols(names: list[dict], max_names: int = MAX_NAMES) -> list[str]:
    """The distinct tickers of the names that get a row."""
    return sorted({n["ticker"] for n in names[:max_names]})


# ------------------------------------------------------- the SEC reader ---
class SecReader:
    """The night's one SEC reader, passed as ``fetch`` to the earnings warning,
    the SEC flags and the candidate checks. Each URL is asked once and its
    answer -- the bytes, or the source error SEC's side gave -- is kept, so the
    three read the same filing list and a ticket's two rows cannot disagree.
    ``made()`` is the requests it actually began (``earnings_risk.counted()``
    reads it): an answer it already held is not a request. A request is not
    begun past ``deadline_seconds`` from the reader's first request, past
    ``max_requests``, or once the transport has downloaded its
    ``issuer_evidence.MAX_DOWNLOAD_BYTES`` for the night (an answer past that
    could not be read); each is a named source error, never kept, so a later
    name reads it as unknown, never clear. The clock starts at the first
    request, so work the evening does before it (the plans, the record) never
    spends the SEC reads' time."""

    def __init__(self, fetch=None, *, now=None, deadline_seconds: float = DEADLINE_SECONDS,
                 max_requests: int = MAX_REQUESTS, monotonic=time.monotonic):
        self._fetch = fetch
        self._now = now
        self.deadline_seconds = deadline_seconds
        self.max_requests = max_requests
        self._monotonic = monotonic
        self.started = None
        self.requests = 0
        self.reused = 0
        self._kept: dict[str, tuple] = {}
        self.last_at = None

    def _base(self):
        if self._fetch is None:
            self._fetch = earnings_risk.FETCH or earnings_risk._default_fetch(self.deadline_seconds)
        return self._fetch

    def clock(self) -> datetime:
        return self._now or datetime.now(timezone.utc)

    def made(self) -> int:
        return self.requests

    def __call__(self, url: str) -> bytes:
        if url in self._kept:
            self.reused += 1
            body, code, at = self._kept[url]
            self.last_at = at
            if code is not None:
                raise earnings_risk.SourceError(code)
            return body
        if self.started is None:
            self.started = self._monotonic()
        elif self._monotonic() - self.started >= self.deadline_seconds:
            raise earnings_risk.SourceError("time_budget")
        if self.requests >= self.max_requests:
            raise earnings_risk.SourceError("request_budget")
        base = self._base()
        budget = getattr(base, "budget", None)
        downloaded = getattr(budget, "bytes", None)
        if type(downloaded) is int and downloaded >= issuer_evidence.MAX_DOWNLOAD_BYTES:
            raise earnings_risk.SourceError("size_limit")
        before = budget.requests if budget is not None else None
        try:
            body = base(url)
        except earnings_risk.SourceError as exc:
            began = (budget.requests - before) if budget is not None else 1
            self.requests += began
            if began:   # SEC's answer for the night; a refusal before the request went out is not kept
                self._kept[url] = (None, exc.code, self.clock())
                self.last_at = self._kept[url][2]
            raise
        except Exception:
            self.requests += (budget.requests - before) if budget is not None else 1
            raise
        self.requests += (budget.requests - before) if budget is not None else 1
        self._kept[url] = (body, None, self.clock())
        self.last_at = self._kept[url][2]
        return body


# ------------------------------------------------------- the iex batch ---
def cross_symbols(data: dict) -> list[str]:
    """The tickers the candidate checks ask the iex feed for: each name within
    the bound that no ``run.cross_check`` row stands behind. A ticket's own
    cross-check reads its own request, as it did before these checks, so a
    candidate's ticker the provider refuses can never change a ticket's row."""
    runs = _run_rows(data)
    return sorted({n["ticker"] for n in record_names(data)[:MAX_NAMES]
                   if (n["stage"], n["ticker"]) not in runs["cross_check"]})


def read_iex(client, tickers, session: date) -> dict:
    """The candidate checks' one iex batch for every distinct ticker, through
    ``market_data.download_bars()`` (one SDK call below its batch size,
    retried once). A batch that failed twice is dropped there, and its
    tickers are named here so they read ``iex_unavailable``, not ``no_iex_bar``;
    a refusal or any other raise is every ticker's."""
    out: dict[str, Any] = {"requested": sorted(set(tickers)), "frames": {}, "dropped": set(), "exception": None,
                           "attempts": 0}
    if not out["requested"]:
        return out
    from alpaca.data.enums import DataFeed
    from src import market_data
    try:
        frames, stats = market_data.download_bars(client, out["requested"], session, cross_check.LOOKBACK_DAYS,
                                                  DataFeed.IEX)
        out["frames"] = frames if isinstance(frames, dict) else {}
        out["dropped"] = set(getattr(stats, "dropped_symbols", None) or ())
        out["attempts"] = getattr(stats, "batch_attempts", None) or 1
    except Exception as exc:  # noqa: BLE001 -- the provider's failure is every row unknown, never the night's
        out["exception"] = exc
        out["attempts"] = getattr(getattr(exc, "download_stats", None), "batch_attempts", None) or 1
    return out


def _cross(name: dict, iex, frames, session: date) -> dict:
    ticker = name["ticker"]
    if not isinstance(iex, dict) or ticker not in iex.get("requested", ()):
        return {"result": cross_check.UNKNOWN, "reason": NOT_CHECKED, "differences": None}
    if iex["exception"] is not None:
        return {"result": cross_check.UNKNOWN, "reason": f"iex_unavailable ({type(iex['exception']).__name__})",
                "differences": None}
    if ticker in iex["dropped"]:
        return {"result": cross_check.UNKNOWN, "reason": f"iex_unavailable ({IexBatchFailed.__name__})",
                "differences": None}
    return cross_check.compare((frames or {}).get(ticker), iex["frames"].get(ticker), session)


# ------------------------------------------------------------ the rows ---
def _hold(role: str) -> str:
    return earnings_risk.TICKET_HOLD if role == "ticket" else earnings_risk.CANDIDATE_HOLD


def _unread_earnings(name: dict, session: str, days, at) -> dict:
    return earnings_risk._row(name, session, days, at, reason=NOT_CHECKED)


def _earnings_part(er: dict, role: str) -> dict:
    return {"verdict": er["verdict"], "reason": er["reason"], "error": er["error"], "placement": er["placement"],
            "projection": er["projection"], "observed": er["observed"],
            "sentence": er["sentence"] if role == "ticket" else earnings_risk.sentence(er, hold=_hold(role))}


def _items_part(er: dict) -> dict:
    items = er["items"]
    material = items["material"] if isinstance(items.get("material"), list) else []
    return {"status": items["status"], "reason": items["reason"], "material": material[:MAX_MATERIAL],
            "material_count": len(material), "codes": list(items["codes"]), "count": items["count"],
            "unread": items["unread"], "after_hold": items["after_hold"],
            "unretained_material": items["unretained_material"]}


def _source_part(er: dict):
    source = er["sources"][0] if er.get("sources") else None
    return {k: source[k] for k in sorted(SOURCE_KEYS)} if source else None


def _sec_part(sr: dict) -> dict:
    filings = sr["filings"] if isinstance(sr.get("filings"), list) else []
    return {"state": sr["state"], "reason": sr["reason"], "filings": filings[-MAX_FILINGS:],
            "filings_count": len(filings)}


def _cross_part(cross: dict) -> dict:
    return {"result": cross["result"], "reason": cross["reason"], "differences": cross["differences"]}


def _lean(name: dict, er: dict, sr: dict, cross: dict) -> dict:
    """One name's row from its full earnings row, its SEC flags row and its
    cross-check reading: the fields a reader acts on, each list bounded with
    its count beside it."""
    return {"stage": name["stage"], "ticker": name["ticker"], "role": name["role"], "rank": name["rank"],
            "cik": er["cik"] if er.get("cik") is not None else sr.get("cik"),
            "source": _source_part(er), "sec": _sec_part(sr), "earnings": _earnings_part(er, name["role"]),
            "items": _items_part(er), "cross_check": _cross_part(cross)}


def _readable(key: str, row: dict) -> bool:
    """Whether a run.* row can be read into a candidate row; one that cannot is
    not stood behind, and its own block's validator names it."""
    try:
        if key == "earnings":
            _earnings_part(row, "ticket"), _items_part(row), _source_part(row)
        elif key == "sec_flags":
            _sec_part(row)
        else:
            _cross_part(row)
        return isinstance(row.get("ticker"), str)
    except (KeyError, TypeError, AttributeError, IndexError, ValueError):
        return False


def _run_rows(data: dict) -> dict:
    """The rows the tickets' own blocks carry, by stage and ticker: the first of
    each that can be read (``_readable()``)."""
    run = _dict(data.get("run"))
    out = {}
    for key in ("earnings", "sec_flags", "cross_check"):
        rows = _dict(run.get(key)).get("rows")
        found: dict = {}
        for r in rows if isinstance(rows, list) else []:
            if isinstance(r, dict) and _readable(key, r):
                found.setdefault((r.get("stage"), r.get("ticker")), r)
        out[key] = found
    return out


def _unread_sec(name: dict) -> dict:
    return {"stage": name["stage"], "ticker": name["ticker"], "state": sec_flags.UNKNOWN, "reason": NOT_CHECKED,
            "cik": None, "filings": []}


def _unread_cross() -> dict:
    return {"result": cross_check.UNKNOWN, "reason": NOT_CHECKED, "differences": None}


def _row_of(name: dict, runs: dict, session: str, days, at, *, er=None, sr=None, cross=None) -> dict:
    key = (name["stage"], name["ticker"])
    return _lean(name, runs["earnings"].get(key) or er or _unread_earnings(name, session, days, at),
                 runs["sec_flags"].get(key) or sr or _unread_sec(name),
                 runs["cross_check"].get(key) or cross or _unread_cross())


def _counts(names: list[dict]) -> dict:
    return {role: n for role in ROLES if (n := sum(1 for x in names if x["role"] == role))}


def _since(session: str, window_days: int = sec_flags.WINDOW_DAYS) -> str:
    return (earnings_risk._day(session) - timedelta(days=window_days)).isoformat()


def _compact(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _block(data: dict, names: list[dict], rows: list[dict], requests: dict, shed: int = 0) -> dict:
    session = _dict(data.get("run")).get("session")
    block = {"version": VERSION, "policy": POLICY, "session": session, "since": _since(session),
             "max_names": MAX_NAMES, "names": _counts(names), "unchecked": _counts(names[MAX_NAMES:]),
             "rows": rows, "shed": shed, "requests": requests}
    block["status"] = status_of(rows)
    block["sentence"] = sentence(block, data)
    return block


def _bounded(data: dict, names: list[dict], rows: list[dict], requests: dict) -> dict:
    """The block within ``MAX_BLOCK_BYTES``: rows no run.* row stands behind
    are shed to not checked from the end, one at a time, so a ticket's row is
    never one of them."""
    runs = _run_rows(data)
    session = data["run"]["session"]
    days = earnings_risk.window(session)
    at = datetime.now(timezone.utc)
    shed = 0
    block = _block(data, names, rows, requests, shed)
    sheddable = [i for i, n in enumerate(names[:len(rows)])
                 if not any((n["stage"], n["ticker"]) in runs[k] for k in runs)]
    while len(_compact(block)) > MAX_BLOCK_BYTES and sheddable:
        i = sheddable.pop()
        rows[i] = _row_of(names[i], runs, session, days, at)
        shed += 1
        block = _block(data, names, rows, requests, shed)
    return block


def unread(data: dict, requests: dict | None = None) -> dict:
    """The block when nothing was read for it: each name a run.* row stands
    behind carries that row's reading, and every other row is not checked.
    ``report.build()`` writes it until the evening replaces it, and the
    evening falls back to it when its own collection fails."""
    session = data["run"]["session"]
    names = record_names(data)
    runs = _run_rows(data)
    days = earnings_risk.window(session)
    at = datetime.now(timezone.utc)
    rows = [_row_of(n, runs, session, days, at) for n in names[:MAX_NAMES]]
    return _bounded(data, names, rows, dict(requests or {"sec": 0, "sec_reused": 0, "iex": 0}))


def collect(data: dict, *, reader: SecReader | None = None, iex: dict | None = None, frames=None) -> dict:
    """The night's block over a record whose plans and allocation are final:
    each name a run.* row stands behind carries that row, and every other
    name is read through the shared ``reader`` and ``iex`` batch."""
    session = data["run"]["session"]
    names = record_names(data)
    runs = _run_rows(data)
    days = earnings_risk.window(session)
    since = _since(session)
    reader = reader if reader is not None else SecReader()
    before, reused = reader.requests, reader.reused
    clock_now = lambda: reader.last_at or reader.clock()   # noqa: E731 -- the instant SEC answered the URL last read
    mapping, mapping_error, read = None, None, {}
    asked = False
    rows = []
    for name in names[:MAX_NAMES]:
        key = (name["stage"], name["ticker"])
        er = sr = cross = None
        if key not in runs["earnings"] or key not in runs["sec_flags"]:
            if not asked:
                asked = True
                try:
                    mapping = earnings_risk.parse_mapping(reader(issuer_evidence.MAPPING_URL))
                except earnings_risk.SourceError as exc:
                    mapping_error = exc.code
            if key not in runs["earnings"]:
                er = earnings_risk.read_row(reader, mapping, mapping_error, name, session, days, clock_now, read)
            if key not in runs["sec_flags"]:
                sr = sec_flags.read_name(reader, mapping, mapping_error, name, since)
        if key not in runs["cross_check"]:
            cross = _cross(name, iex, frames, earnings_risk._day(session))
        rows.append(_row_of(name, runs, session, days, clock_now(), er=er, sr=sr, cross=cross))
    requests = {"sec": reader.requests - before, "sec_reused": reader.reused - reused,
                "iex": (iex or {}).get("attempts", 0) or 0}
    return _bounded(data, names, rows, requests)


def safe_collect(data: dict, **kwargs) -> dict:
    """The evening's call: a check never fails a night. A collection that
    raised, or wrote a block its validator refuses, is the block with nothing
    read for it, the requests it had made counted."""
    reader = kwargs.get("reader")
    made = (reader.requests, reader.reused) if isinstance(reader, SecReader) else (0, 0)
    try:
        block = collect(data, **kwargs)
        problems = faults({**data, "candidate_checks": block})
        if problems:
            raise ValueError(problems[0])
        return block
    except Exception:  # noqa: BLE001 -- a flag must never stop a publication
        requests = {"sec": (reader.requests - made[0]) if isinstance(reader, SecReader) else 0,
                    "sec_reused": (reader.reused - made[1]) if isinstance(reader, SecReader) else 0,
                    "iex": (kwargs.get("iex") or {}).get("attempts", 0) or 0}
        return unread(data, requests)


def carried(previous_block, data: dict):
    """A closed night re-presents the previous session's names, and their checks
    as that publication read them: the previous block when it holds under
    tonight's record -- its names, its session, the tickets' own rows -- else None."""
    if isinstance(previous_block, dict) and not faults({**data, "candidate_checks": previous_block}):
        return previous_block
    return None


def night(data: dict, *, reader=None, iex=None, frames=None, previous=None, client=None) -> dict:
    """The evening's block: the previous one on a closed night when it still
    holds, else the night's own collection; never a raise. Given ``client``
    and no ``iex``, it reads the batch itself (``cross_symbols()``), and only
    when it collects."""
    try:
        kept = carried(previous, data) if previous is not None else None
        if kept is not None:
            return kept
        if iex is None and client is not None:
            iex = read_iex(client, cross_symbols(data), earnings_risk._day(data["run"]["session"]))
        return safe_collect(data, reader=reader, iex=iex, frames=frames)
    except Exception:  # noqa: BLE001 -- a flag must never stop a publication
        return unread(data)


# ------------------------------------------------------------ the words ---
def _read(row: dict) -> dict:
    """Which of a row's three readings were made."""
    # the earnings date is read only when its verdict says something: a filing list read in full that
    # gives no date (a foreign issuer, a short history) leaves the date unknown, and unknown is never clear
    return {"sec": row["sec"]["state"] != sec_flags.UNKNOWN,
            "earnings": row["earnings"]["verdict"] != "unknown",
            "cross_check": row["cross_check"]["result"] != cross_check.UNKNOWN}


def status_of(rows: list[dict]) -> str:
    if not rows:
        return "not_applicable"
    reads = [_read(r) for r in rows]
    if all(all(x.values()) for x in reads):
        return "checked"
    return "unavailable" if not any(any(x.values()) for x in reads) else "partial"


def _band(data: dict) -> str:
    grades = _dict(_dict(data.get("rules")).get("pipeline")).get("trade_grades")
    grades = [g for g in grades if isinstance(g, str)] if isinstance(grades, list) else []
    return "/".join(grades) or "trade-band"


def _role_words(counts: dict, band: str) -> str:
    parts = []
    for role in ROLES:
        n = counts.get(role)
        if n:
            one, many = ROLE_WORDS[role]
            parts.append(f"{n} {(one if n == 1 else many).format(band=band)}")
    return ", ".join(parts)


def _named(rows: list[dict]) -> str:
    names = [r["ticker"] for r in rows[:SENTENCE_NAMES]]
    more = len(rows) - len(names)
    return ", ".join(names) + (f" and {more} more" if more else "")


def sentence(block: dict, data: dict) -> str:
    """What the page's Method line and the mail print, verbatim: counts, and at
    most ``SENTENCE_NAMES`` names for each kind of flag."""
    rows = block["rows"]
    band = _band(data)
    if not rows:
        return "Candidate checks: no ticket, listed setup or admitted candidate to check."
    total = sum(block["names"].values())
    words = (f"Candidate checks (flags only) for {len(rows)} of {total} "
             f"name{'' if total == 1 else 's'}: {_role_words(_counts_of(rows), band)}.")
    if block["unchecked"]:
        words += f" Not checked past the bound of {block['max_names']}: {_role_words(block['unchecked'], band)}."
    if block["shed"]:
        words += f" {block['shed']} shed to stay within the block's byte bound, not checked."
    flags = [("SEC merger, tender or deal filings flagged for", [r for r in rows if r["sec"]["state"] == sec_flags.FLAGGED]),
             ("a material 8-K item for", [r for r in rows if r["items"]["status"] == "material"]),
             ("earnings reported after the signal, estimated in or near the hold window, or overdue for",
              [r for r in rows if r["earnings"]["verdict"] in EARNINGS_FLAGS]),
             ("the iex feed's signal-day bar differs for", [r for r in rows if r["cross_check"]["result"] == cross_check.FAIL])]
    found = "; ".join(f"{what} {len(hit)} ({_named(hit)})" for what, hit in flags if hit)
    if found:
        words += f" {found[0].upper()}{found[1:]}."
    elif status_of(rows) == "unavailable":
        words += " Nothing could be read for these names, so none is flagged and none is clear."
    else:
        words += " None flagged among the readings made."
    unknown = [(what, sum(1 for r in rows if not _read(r)[key])) for what, key in
               (("SEC filings", "sec"), ("the earnings date", "earnings"), ("the iex bar", "cross_check"))]
    unknown = [f"{what} of {n}" for what, n in unknown if n]
    if unknown:
        words += " Unknown, and unknown is never clear: " + "; ".join(unknown) + "."
    return words + (" A flag is for a reader: it changes no plan, ticket or order, and only the manual event "
                    "registry withholds a ticket.")


def _counts_of(rows: list[dict]) -> dict:
    return {role: n for role in ROLES if (n := sum(1 for r in rows if r.get("role") == role))}


# ------------------------------------------------------------ validation ---
def faults(data: dict) -> list[str]:
    """The block one level in, under rules that archive it; a record whose
    rules archive none is asked for none. Its names are re-derived from the
    record, each row's earnings sentence and cross-check result from its own
    fields, each flagged filing held to the SEC flags' archived window, forms
    and items (``rules.sec_flags``), and a
    name a run.* row stands behind is held to that row's reading. Names
    faults; never raises."""
    try:
        return _faults(data)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, ArithmeticError, RecursionError) as exc:
        return [f"candidate_checks is malformed ({type(exc).__name__})"]


def _int(value) -> bool:
    return type(value) is int and value >= 0


def _faults(data: dict) -> list[str]:
    if not isinstance(data, dict):
        return []
    rules = data.get("rules")
    archived = rules.get("candidate_checks") if isinstance(rules, dict) else None
    block = data.get("candidate_checks")
    if archived is None:
        return [] if block is None else ["candidate_checks present under rules that do not write it"]
    if not isinstance(archived, dict):
        return ["rules.candidate_checks is not an object"]
    version = archived.get("version")
    if type(version) is not int or version not in VERSIONS:
        return ["candidate_checks rules version is unknown"]
    if not isinstance(block, dict) or set(block) != BLOCK_KEYS:
        return ["candidate_checks is missing or its keys are not this version's"]
    if block["version"] != version or type(block["version"]) is not int or block["policy"] != POLICY:
        return ["candidate_checks version or policy is not the rules it archived"]
    run = data.get("run") if isinstance(data.get("run"), dict) else {}
    session = run.get("session")
    if block["session"] != session or not isinstance(session, str):
        return ["candidate_checks session differs from the run's"]
    max_names = archived.get("max_names")
    if not _int(max_names) or block["max_names"] != max_names:
        return ["candidate_checks bound is not the rules it archived"]
    rows = block["rows"]
    if not isinstance(rows, list) or not all(isinstance(r, dict) and set(r) == ROW_KEYS for r in rows):
        return ["candidate_checks rows are not this version's"]
    out = []
    names = record_names(data)
    if [(r["stage"], r["ticker"], r["role"], r["rank"]) for r in rows] != \
            [(n["stage"], n["ticker"], n["role"], n["rank"]) for n in names[:max_names]]:
        out.append("candidate_checks rows are not the record's names")
    if block["names"] != _counts(names) or block["unchecked"] != _counts(names[max_names:]):
        out.append("candidate_checks counts by role are not the record's names")
    if not (_int(block["shed"]) and isinstance(block["requests"], dict) and set(block["requests"]) == REQUEST_KEYS
            and all(_int(v) for v in block["requests"].values())):
        out.append("candidate_checks shed or request counts")
    flags_rules = _dict(_dict(rules).get("sec_flags"))
    window_days = flags_rules.get("window_days")
    if not _int(window_days) or block["since"] != _since(session, window_days):
        out.append("candidate_checks window is not the SEC flags' archived window")
    days = earnings_risk.window(session)
    cross_rules = _dict(_dict(rules).get("cross_check"))
    runs = _run_rows(data)
    for r in rows:
        fault = _row_faults(r, archived, days, block["since"], flags_rules, cross_rules, runs)
        if fault:
            out.append(fault)
    if len(_compact(block)) > (archived.get("max_block_bytes") if _int(archived.get("max_block_bytes")) else -1):
        out.append("candidate_checks is over its archived byte bound")
    if out:
        return out
    if block["status"] != status_of(rows):
        out.append("candidate_checks status is not its rows'")
    elif block["sentence"] != sentence(block, data):
        out.append("candidate_checks sentence is not its rows'")
    return out


def _row_faults(r, archived, days, since, flags_rules, cross_rules, runs) -> str | None:
    name = r["ticker"]
    if r["role"] not in ROLES or r["stage"] not in earnings_risk.STAGES or not isinstance(name, str):
        return "candidate_checks row identity"
    if not (r["cik"] is None or (type(r["cik"]) is int and 0 < r["cik"] < 10**10)):
        return f"candidate_checks cik for {name}"
    src = r["source"]
    if not (src is None or (isinstance(src, dict) and set(src) == SOURCE_KEYS
                            and isinstance(src["sha256"], str) and earnings_risk.SHA256.fullmatch(src["sha256"])
                            and type(src["bytes"]) is int and src["bytes"] > 0
                            and earnings_risk._instant(src["retrieved_at"]))):
        return f"candidate_checks source for {name}"
    sec, earn, items, cross = r["sec"], r["earnings"], r["items"], r["cross_check"]
    if not (isinstance(sec, dict) and set(sec) == SEC_KEYS and isinstance(earn, dict) and set(earn) == EARNINGS_KEYS
            and isinstance(items, dict) and set(items) == ITEMS_KEYS and isinstance(cross, dict)
            and set(cross) == CROSS_KEYS):
        return f"candidate_checks parts for {name}"
    # the SEC flags reading, held to the archived window, forms and items
    max_filings = archived.get("max_filings")
    if (sec["state"] not in sec_flags.STATES or not _int(sec["filings_count"]) or not isinstance(sec["filings"], list)
            or not _int(max_filings) or len(sec["filings"]) != min(sec["filings_count"], max_filings)
            or (sec["state"] == sec_flags.FLAGGED) != (sec["filings_count"] > 0)
            or (sec["state"] == sec_flags.UNKNOWN) != (sec["reason"] is not None)
            or not (sec["reason"] is None or isinstance(sec["reason"], str))):
        return f"candidate_checks SEC reading for {name}"
    for f in sec["filings"]:
        if (not isinstance(f, dict) or not isinstance(f.get("filing_date"), str) or f["filing_date"] < since
                or not (f.get("form") in (flags_rules.get("forms") or ())
                        or (isinstance(f.get("items"), list) and f["items"]
                            and all(isinstance(i, str) for i in f["items"])
                            and set(f["items"]) <= set(flags_rules.get("items") or ())))):
            return f"candidate_checks a flagged filing for {name} is outside the window or of no listed form or item"
    # the earnings reading, its sentence re-derived from its own fields
    if (earn["verdict"] not in earnings_risk.VERDICTS
            or earn["reason"] not in earnings_risk.UNKNOWN_REASONS + (None,)
            or (earn["verdict"] == "unknown") != (earn["reason"] is not None)
            or not (earn["error"] is None or earn["error"] in earnings_risk.ERRORS)
            or not (earn["placement"] is None or earn["placement"] in earnings_risk.PLACEMENTS)):
        return f"candidate_checks earnings reading for {name}"
    if earn["sentence"] != earnings_risk.sentence({**earn, "window": days}, hold=_hold(r["role"])):
        return f"candidate_checks earnings sentence for {name}"
    # the current reports' items
    max_material = archived.get("max_material")
    if (items["status"] not in earnings_risk.ITEMS_STATUSES or not isinstance(items["material"], list)
            or not _int(items["material_count"]) or not _int(max_material)
            or len(items["material"]) != min(items["material_count"], max_material)
            or (items["status"] == "material") != (items["material_count"] > 0)
            or not isinstance(items["codes"], list) or not all(isinstance(c, str) for c in items["codes"])
            or not all(isinstance(m, dict) and m.get("item") in earnings_risk.MATERIAL_ITEMS for m in items["material"])):
        return f"candidate_checks current-report items for {name}"
    if (earn["reason"] in earnings_risk.ASSESSED_REASONS) == (items["status"] == "not_checked"):
        return f"candidate_checks current-report items for {name} are not its earnings reading's"
    # a reading SEC gave names the issuer it was read for, and a filing list read names its source
    if sec["state"] != sec_flags.UNKNOWN and r["cik"] is None:
        return f"candidate_checks SEC reading for {name} names no issuer"
    if earn["reason"] in earnings_risk.ASSESSED_REASONS and (r["cik"] is None or src is None):
        return f"candidate_checks earnings reading for {name} names no issuer or no source"
    # the cross-check reading, its result and reason re-derived from its differences
    if cross["result"] not in cross_check.RESULTS or (cross["result"] == cross_check.UNKNOWN) != (cross["differences"] is None):
        return f"candidate_checks cross-check for {name}"
    if cross["result"] != cross_check.UNKNOWN:
        diffs = cross["differences"]
        if not isinstance(diffs, dict) or not all(cross_check._finite(diffs.get(k)) for k in ("open", "high", "low", "close", "volume")):
            return f"candidate_checks cross-check for {name} carries no finite differences"
        if not (cross_check._finite(cross_rules.get("price_pct")) and cross_check._finite(cross_rules.get("volume_pct"))):
            return "candidate_checks cross-check tolerances are not numbers"
        over = cross_check.judge(diffs, cross_rules["price_pct"], cross_rules["volume_pct"])
        if (cross_check.FAIL if over else cross_check.PASS) != cross["result"] or \
                cross["reason"] != (("differ: " + ", ".join(over)) if over else None):
            return f"candidate_checks cross-check for {name} is not what its differences give"
    elif not isinstance(cross["reason"], str):
        return f"candidate_checks cross-check for {name} names no reason"
    # a name a run.* row stands behind carries that row's reading
    key = (r["stage"], name)
    er, sr, cr = runs["earnings"].get(key), runs["sec_flags"].get(key), runs["cross_check"].get(key)
    try:
        if er is not None:
            for part, expected in (("earnings", _earnings_part(er, r["role"])), ("items", _items_part(er)),
                                   ("source", _source_part(er))):
                if r[part] != expected:
                    return f"candidate_checks {part} for {name} is not its run.* row's"
            if er.get("cik") is not None and r["cik"] != er["cik"]:
                return f"candidate_checks cik for {name} is not its run.* row's"
        if sr is not None and r["sec"] != _sec_part(sr):
            return f"candidate_checks sec for {name} is not its run.* row's"
        if cr is not None and r["cross_check"] != _cross_part(cr):
            return f"candidate_checks cross_check for {name} is not its run.* row's"
    except (KeyError, TypeError, AttributeError, IndexError, ValueError):
        return f"candidate_checks the run.* rows behind {name} cannot be read"
    return None
