"""A price-free, ticker-free timeline read off the owner's private backtest.

``tools/historical_backtest.py`` writes two things: ``backtest.json``, every
night and every walked plan with its prices and its tickers, which stays on
the owner's computer, and ``summary.txt``, the totals, which is what has
been pasted and committed. This tool is the row between the two: the owner
runs it over the private file and gets one row per night per gate carrying
the night's breadth -- the Market Monitor's verdict, its two ratios and its
counts, as the night row recorded them -- what the policy did with it --
the scan's counts, the grade and cut tallies, the slots held, how many
tickets -- and how that gate's tickets came out: counted by scorecard
bucket and by kind of uncertainty, the settled R listed, summed, averaged
and its median. Nothing in it can name a stock or quote a price.

It is a READER. It changes no number of the backtest's: every value is
copied off the night row ``historical_backtest.measure()`` and ``decide()``
wrote, or counted and summed over the rows ``record.scorecard_rows()``
walked for that night, joined on the session the plan was picked on. Its
only arithmetic is a night's wins, losses, breakeven, the ``math.fsum`` of
its settled R, their mean and their median, rounded once.

What it writes is an allowlist, not a filter. Every field of the output is
named in this module and copied by type: a count is a whole number, a ratio
or R a finite number, a verdict, grade, cut kind, bucket, uncertainty kind
or equivalence status a word of its own vocabulary, a session an ISO date.
The run's context (``account``, ``lookback``, ``evaluated``, ``regimes``)
is copied field by field from the lists below, so a field the private file
grows is left behind, never published; a lookback's equivalence
``differences``, fingerprints of candidates and plans, are reduced to how
many there were.

Then, before a byte is written, the whole output is swept:

* no key in ``PRIVATE_KEYS`` anywhere, under any parent;
* no ticker the private file names -- in a night's ``trades`` or
  ``candidates``, a walked row or a pick (``TICKER_FIELDS``) -- as a whole
  word, in any case, in any key or string value, unless that key or string
  is one of the tool's own words (``VOCABULARY``: its field names, the
  vocabularies above and the backtest's own sentences), because the grade
  ``A`` is not the ticker ``A`` and the field ``path`` is not the ticker
  ``PATH``. The free text it copies -- the reader's and the limitations'
  sentences and the private file's basename -- is swept the same way.

A leak is a refusal, not a warning. So is any file the timeline could not
describe honestly, each with one sentence and exit code 2: a file that is
not a JSON object, whose ``version`` is not the backtest's own, that misses
either gate's nights or outcomes, or carries a field of the wrong type or
outside its vocabulary; a walked plan picked on a session no night row
evaluated; a night session written twice; a gate whose nights are not the
``evaluated`` count; a night whose walked plans are not its tickets, whose
scorecard buckets do not add up to them, whose uncertain plans are not all
of a kind the scorecard names, or whose settled R is not a finite number; a
gate whose tickets are not the ``tickets_issued`` the outcomes carry; a
lookback with no equivalence block, or whose status contradicts its
differences; and an ``--output`` that names the private file itself.

    python tools/backtest_timeline.py --backtest <private backtest.json> --output <file>

writes the timeline and prints one line of counts; without ``--output``
the timeline goes to stdout. The output may go anywhere but over the
private file -- it is public by construction -- and the private file is
read where it is and never copied.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import dataclasses
from datetime import date
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import breadth, grader, plan, record  # noqa: E402
from tools.historical_backtest import (GATES, LIMITATIONS, READER,  # noqa: E402
                                       VERSION as BACKTEST_VERSION)

VERSION = "backtest-timeline-v1"
#: the keys of the private file that carry a price, a name or the block that
#: carries both; none may appear anywhere in the output, under any parent
PRIVATE_KEYS = frozenset({"ticker", "entry_ref", "entry_low", "entry_high", "limit", "stop", "trigger",
                          "position_usd", "order_json", "targets", "day2_spent_above", "evidence_ref", "candidates"})
#: where the private file names a ticker, and what each list holds: a name
#: itself, or an object whose ``ticker`` is one. A night carries the first
#: two, a gate's outcomes the last two; ``tickers_of()`` reads all four off both.
TICKER_FIELDS = {"trades": str, "candidates": dict, "rows": dict, "picks": dict}

#: the Market Monitor's reading of the night, copied off the night's regime:
#: its verdict, its two ratios and its counts
VERDICT = "verdict"
RATIO_FIELDS = ("ratio_10d", "ratio_5d")
BREADTH_COUNTS = ("up4", "down4", "up4_10d", "down4_10d", "universe")
REGIME_FIELDS = (VERDICT, *RATIO_FIELDS, *BREADTH_COUNTS)
#: the one reason ``historical_backtest.measure()`` writes, on a session no name printed on
NO_SESSION_REASON = "no name printed on the session"
#: the night's counts, copied off the night row as the backtest wrote them
COUNT_FIELDS = ("counted", "measured", "bursts", "eligible_plans", "slots_held")
#: the night's tallies, each keyed by its own vocabulary: the mechanical
#: grade and the cash budget's cut kind
TALLIES = {"grades": grader.GRADES, "cut": plan.CUT_KINDS}
COPIED = COUNT_FIELDS + tuple(TALLIES)

#: the run's context, copied into ``source`` field by field
ACCOUNT_FIELDS = tuple(f.name for f in dataclasses.fields(plan.Account))
EVALUATED_FIELDS = ("from", "through", "count", "seconds")
LOOKBACK_FIELDS = ("sessions", "production", "equivalence")
EQUIVALENCE_FIELDS = ("required", "compared", "differences", "status")
EQUIVALENCE_FAIL, EQUIVALENCE_NOT_REQUIRED = "FAIL", "not required"
#: every status ``historical_backtest.run()`` writes
EQUIVALENCE_STATUSES = (EQUIVALENCE_NOT_REQUIRED, EQUIVALENCE_FAIL, "PASS",
                        "BLOCKED: no session carries the full lookback")
REGIMES_FIELDS = ("verdicts", "ratio_10d")
RATIO_SUMMARY = ("min", "max", "median")
#: ``regimes.verdicts`` counts the production nights by verdict; a night
#: with none is the key JSON spells "null"
VERDICT_KEYS = (*breadth.VERDICTS, "null")
SOURCE_FIELDS = ("path", "sha256", "backtest_version", "rules_version", "lookback", "evaluated", "regimes", "account")
TOP_FIELDS = ("version", "reader", "limitations", "source", "gates")

#: decimals of a night's summed and median R, as ``record.summarize_scorecard`` rounds them
R_DECIMALS = 2
#: decimals of a night's mean R: a night holds a handful of plans, so the
#: mean is kept one place finer than the sum it is read from
MEAN_DECIMALS = 3
SETTLED = "settled"
SETTLED_FIELDS = ("n", "wins", "losses", "breakeven", "sum_r", "mean_r", "median_r")
ROW_FIELDS = ("session", *REGIME_FIELDS, "reason", *COPIED, "tickets", "buckets", "settled", "r", "uncertainty")

#: every word the timeline writes of its own: its field names, the
#: vocabularies its values are read against and the backtest's own
#: sentences. A key or string that IS one of these is the tool's word, never
#: a stock's, and the ticker sweep passes it; anything else is swept.
VOCABULARY = frozenset({
    *TOP_FIELDS, *SOURCE_FIELDS, *LOOKBACK_FIELDS, *EQUIVALENCE_FIELDS, *EVALUATED_FIELDS, *REGIMES_FIELDS,
    *RATIO_SUMMARY, "defined", *ACCOUNT_FIELDS, *GATES, *ROW_FIELDS, *SETTLED_FIELDS,
    *grader.GRADES, *plan.CUT_KINDS, *VERDICT_KEYS, *record.SCORECARD_BUCKETS, *record.UNCERTAIN_REASONS,
    *EQUIVALENCE_STATUSES, NO_SESSION_REASON, VERSION, BACKTEST_VERSION, READER, *LIMITATIONS})


class TimelineError(RuntimeError):
    """A refusal, named; never a guess."""


# ------------------------------------------------------------- the types ----


def _what(value) -> str:
    """A value's JSON type, never the value itself (a refusal is printed)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, (int, float)):
        return "a number" if math.isfinite(value) else repr(value)
    return {str: "a string", list: "an array", dict: "an object"}.get(type(value), type(value).__name__)


def _get(holder: dict, key: str, where: str):
    if key not in holder:
        raise TimelineError(f"{where} has no {key}")
    return holder[key]


def _object(value, where: str) -> dict:
    if not isinstance(value, dict):
        raise TimelineError(f"{where} is {_what(value)}, not an object")
    return value


def _list(value, where: str) -> list:
    if not isinstance(value, list):
        raise TimelineError(f"{where} is {_what(value)}, not an array")
    return value


def _text(value, where: str) -> str:
    if not isinstance(value, str):
        raise TimelineError(f"{where} is {_what(value)}, not a string")
    return value


def _count(value, where: str, *, optional: bool = False) -> int | None:
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TimelineError(f"{where} is {_what(value)}, not a count")
    return value


def _number(value, where: str, *, optional: bool = False) -> float | int | None:
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise TimelineError(f"{where} is {_what(value)}, not a finite number")
    return value


def _word(value, vocabulary, where: str):
    if value not in vocabulary:
        raise TimelineError(f"{where} is not one of {', '.join(map(str, vocabulary))}")
    return value


def _date(value, where: str) -> str:
    try:
        if date.fromisoformat(_text(value, where)).isoformat() == value:
            return value
    except ValueError:
        pass
    raise TimelineError(f"{where} is not an ISO date")


def _tally(value, vocabulary, where: str) -> dict:
    """A count per word of ``vocabulary``; a key outside it is refused, so
    a name can never ride in as a key."""
    out = {}
    for key, n in _object(value, where).items():
        out[_word(key, vocabulary, f"{where} key")] = _count(n, f"{where}.{key}")
    return out


# ------------------------------------------------------------- the rows ----


def settled_block(rs: list[float]) -> dict:
    """Wins, losses, breakeven and the three R figures over one night's
    settled R values; the sums are None on a night that settled nothing."""
    n = len(rs)
    return {"n": n, "wins": sum(r > 0 for r in rs), "losses": sum(r < 0 for r in rs),
            "breakeven": sum(r == 0 for r in rs),
            "sum_r": round(math.fsum(rs), R_DECIMALS) if rs else None,
            "mean_r": round(math.fsum(rs) / n, MEAN_DECIMALS) if rs else None,
            "median_r": round(statistics.median(rs), R_DECIMALS) if rs else None}


def night_row(night: dict, rows: list[dict], where: str) -> dict:
    """One timeline row: the night's regime and counts copied by type, the
    number of its tickets (never their names), and its walked plans counted
    by bucket and by the kind of uncertainty, its settled R listed sorted
    and summed. Every walked plan is in exactly one bucket and every
    uncertain plan of one named kind, or the night is refused."""
    session = night["session"]
    regime = _object(_get(night, "regime", where), f"{where}.regime")
    reason = regime.get("reason")
    if reason not in (None, NO_SESSION_REASON):
        raise TimelineError(f"{where}.regime.reason is not the backtest's own sentence")
    out = {"session": session,
           VERDICT: _word(regime.get(VERDICT), (*breadth.VERDICTS, None), f"{where}.regime.{VERDICT}"),
           **{k: _number(regime.get(k), f"{where}.regime.{k}", optional=True) for k in RATIO_FIELDS},
           **{k: _count(regime.get(k), f"{where}.regime.{k}", optional=True) for k in BREADTH_COUNTS},
           "reason": reason,
           **{k: _count(_get(night, k, where), f"{where}.{k}") for k in COUNT_FIELDS},
           **{k: _tally(_get(night, k, where), vocabulary, f"{where}.{k}") for k, vocabulary in TALLIES.items()},
           "tickets": len(_list(_get(night, "trades", where), f"{where}.trades"))}
    tickets = out["tickets"]
    if len(rows) != tickets:
        raise TimelineError(f"{session}: {tickets} tickets but {len(rows)} walked plans; "
                            "the timeline refuses to describe a population the night did not issue")
    buckets = {bucket: sum(r["bucket"] == bucket for r in rows) for bucket in record.SCORECARD_BUCKETS}
    if sum(buckets.values()) != tickets:
        unknown = sorted({r["bucket"] for r in rows} - set(record.SCORECARD_BUCKETS))
        raise TimelineError(f"{session}: {tickets} walked plans but {sum(buckets.values())} in the scorecard's "
                            f"buckets; {', '.join(map(repr, unknown))} is not a bucket the scorecard counts")
    rs = []
    for r in rows:
        if r["bucket"] == SETTLED:
            value = r.get("r")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise TimelineError(f"{session}: a settled plan's R is {_what(value)}, not a finite number")
            rs.append(value)
    rs.sort()
    kinds = [r.get("uncertainty") for r in rows if r["bucket"] == record.UNCERTAIN]
    uncertainty = {kind: kinds.count(kind) for kind in record.UNCERTAIN_REASONS if kind in kinds}
    if sum(uncertainty.values()) != buckets[record.UNCERTAIN]:
        unknown = sorted({repr(k) for k in kinds if k not in record.UNCERTAIN_REASONS})
        raise TimelineError(f"{session}: {buckets[record.UNCERTAIN]} uncertain plans but "
                            f"{sum(uncertainty.values())} of a kind the scorecard names; "
                            f"{', '.join(unknown)} is not one")
    out["buckets"] = buckets
    out["settled"] = settled_block(rs)
    out["r"] = rs
    out["uncertainty"] = uncertainty
    return out


def gate_rows(private: dict, gate: str) -> list[dict]:
    """Every night of one gate in the file's own order, each joined to the
    walked plans picked on its session; a plan on a session no night
    evaluated, and a session written twice, are refused by name, and so is
    a gate whose tickets are not the ``tickets_issued`` its outcomes carry."""
    nights = _list(private["nights"][gate], f"nights.{gate}")
    outcome = _object(private["outcomes"][gate], f"outcomes.{gate}")
    sessions = [_date(_get(_object(n, f"nights.{gate}[{i}]"), "session", f"nights.{gate}[{i}]"),
                      f"nights.{gate}[{i}].session") for i, n in enumerate(nights)]
    repeated = sorted(s for s, n in Counter(sessions).items() if n > 1)
    if repeated:
        raise TimelineError(f"{gate}: the night of {', '.join(repeated)} is written more than once; "
                            "its walked plans could not be told apart")
    by_session: dict[str, list[dict]] = defaultdict(list)
    for j, row in enumerate(_list(_get(outcome, "rows", f"outcomes.{gate}"), f"outcomes.{gate}.rows")):
        here = f"outcomes.{gate}.rows[{j}]"
        _object(row, here)
        _text(_get(row, "picked", here), f"{here}.picked")
        _text(_get(row, "bucket", here), f"{here}.bucket")
        by_session[row["picked"]].append(row)
    unknown = sorted(set(by_session) - set(sessions))
    if unknown:
        raise TimelineError(f"{gate}: walked plans picked on {', '.join(unknown)}, sessions no night row evaluated")
    out = [night_row(n, by_session.get(s, []), f"nights.{gate}[{i}]")
           for i, (n, s) in enumerate(zip(nights, sessions))]
    if "tickets_issued" in outcome:
        issued = _count(outcome["tickets_issued"], f"outcomes.{gate}.tickets_issued")
        total = sum(r["tickets"] for r in out)
        if issued != total:
            raise TimelineError(f"{gate}: the nights issued {total} tickets but the outcomes say {issued}")
    return out


# ----------------------------------------------------------- the source ----


def lookback_of(private: dict) -> dict:
    """The lookback block field by field, its equivalence differences, which
    are fingerprints of candidates and plans, reduced to how many there
    were. A lookback with no equivalence block, or whose status says FAIL
    over no difference or passes over one, is refused."""
    lookback = _object(_get(private, "lookback", "the file"), "lookback")
    equivalence = _object(_get(lookback, "equivalence", "lookback"), "lookback.equivalence")
    differences = _list(_get(equivalence, "differences", "lookback.equivalence"), "lookback.equivalence.differences")
    status = _word(_get(equivalence, "status", "lookback.equivalence"), EQUIVALENCE_STATUSES,
                   "lookback.equivalence.status")
    required = _get(equivalence, "required", "lookback.equivalence")
    if not isinstance(required, bool):
        raise TimelineError(f"lookback.equivalence.required is {_what(required)}, not a boolean")
    if (status == EQUIVALENCE_FAIL) != bool(differences) or (status == EQUIVALENCE_NOT_REQUIRED) == required:
        raise TimelineError(f"lookback.equivalence says {status!r} (required {required}) over "
                            f"{len(differences)} differences")
    return {"sessions": _count(_get(lookback, "sessions", "lookback"), "lookback.sessions"),
            "production": _count(_get(lookback, "production", "lookback"), "lookback.production"),
            "equivalence": {"required": required,
                            "compared": _count(_get(equivalence, "compared", "lookback.equivalence"),
                                               "lookback.equivalence.compared"),
                            "differences": len(differences), "status": status}}


def evaluated_of(private: dict) -> dict:
    evaluated = _object(_get(private, "evaluated", "the file"), "evaluated")
    return {"from": _date(_get(evaluated, "from", "evaluated"), "evaluated.from"),
            "through": _date(_get(evaluated, "through", "evaluated"), "evaluated.through"),
            "count": _count(_get(evaluated, "count", "evaluated"), "evaluated.count"),
            "seconds": _number(_get(evaluated, "seconds", "evaluated"), "evaluated.seconds")}


def regimes_of(private: dict) -> dict:
    regimes = _object(_get(private, "regimes", "the file"), "regimes")
    ratio = _object(_get(regimes, "ratio_10d", "regimes"), "regimes.ratio_10d")
    return {"verdicts": _tally(_get(regimes, "verdicts", "regimes"), VERDICT_KEYS, "regimes.verdicts"),
            "ratio_10d": {**{k: _number(_get(ratio, k, "regimes.ratio_10d"), f"regimes.ratio_10d.{k}", optional=True)
                             for k in RATIO_SUMMARY},
                          "defined": _count(_get(ratio, "defined", "regimes.ratio_10d"), "regimes.ratio_10d.defined")}}


def account_of(private: dict) -> dict:
    account = _object(_get(private, "account", "the file"), "account")
    return {k: _number(_get(account, k, "account"), f"account.{k}") for k in ACCOUNT_FIELDS}


# ------------------------------------------------------------ the sweep ----


def tickers_of(private: dict) -> frozenset[str]:
    """Every name the private file carries, in capitals, wherever it carries
    one: each of ``TICKER_FIELDS`` on every night and on every gate's outcomes."""
    names: set[str] = set()
    for gate in GATES:
        holders = [(f"nights.{gate}[{i}]", n) for i, n in enumerate(_list(private["nights"][gate], f"nights.{gate}"))]
        holders.append((f"outcomes.{gate}", private["outcomes"][gate]))
        for where, holder in holders:
            _object(holder, where)
            for field, kind in TICKER_FIELDS.items():
                for i, item in enumerate(_list(holder.get(field, []), f"{where}.{field}")):
                    here = f"{where}.{field}[{i}]"
                    if not isinstance(item, kind):
                        raise TimelineError(f"{here} is {_what(item)}, not {'a name' if kind is str else 'an object'}")
                    name = item if kind is str else item.get("ticker")
                    if name is not None:
                        names.add(_text(name, here if kind is str else f"{here}.ticker").upper())
    names.discard("")
    return frozenset(names)


def _words(text: str) -> set[str]:
    return {w.upper() for w in re.split(r"[^0-9A-Za-z]+", text) if w}


def private_leaks(value, tickers: frozenset[str], path: str = "timeline") -> list[str]:
    """Every place a private key sits in ``value``, and every key or string
    that is not one of the tool's own words and carries a ticker as a whole
    word in any case, by path."""
    plain = {t.upper() for t in tickers if t.isalnum()}
    marked = [re.compile(rf"(?<![0-9A-Za-z]){re.escape(t)}(?![0-9A-Za-z])", re.IGNORECASE)
              for t in tickers if t and not t.isalnum()]

    def named(text: str) -> bool:
        if text in VOCABULARY:
            return False
        return bool(_words(text) & plain) or any(p.search(text) for p in marked)

    def sweep(inner, here: str) -> list[str]:
        leaks = []
        if isinstance(inner, dict):
            for key, item in inner.items():
                there = f"{here}.{key}"
                if key in PRIVATE_KEYS:
                    leaks.append(f"{there} (private key)")
                elif isinstance(key, str) and named(key):
                    leaks.append(f"{there} (a ticker in its key)")
                leaks += sweep(item, there)
        elif isinstance(inner, list):
            for i, item in enumerate(inner):
                leaks += sweep(item, f"{here}[{i}]")
        elif isinstance(inner, str) and named(inner):
            leaks.append(f"{here} (a ticker)")
        return leaks

    return sweep(value, path)


# ------------------------------------------------------------ the output ----


def validate(private) -> None:
    if not isinstance(private, dict):
        raise TimelineError(f"the file is {_what(private)}, not a JSON object")
    if private.get("version") != BACKTEST_VERSION:
        raise TimelineError(f"not a {BACKTEST_VERSION} file: version {private.get('version')!r}")
    for block in ("nights", "outcomes"):
        held = _object(private.get(block) or {}, block)
        missing = [gate for gate in GATES if gate not in held]
        if missing:
            raise TimelineError(f"{block} missing the {', '.join(missing)} gate")


def build(private, *, path: Path, digest: str) -> dict:
    """The timeline over one private file, field by field, swept for a
    private key or a ticker before it is returned; a leak is a refusal."""
    validate(private)
    out = {"version": VERSION, "reader": _text(_get(private, "reader", "the file"), "reader"),
           "limitations": [_text(t, f"limitations[{i}]") for i, t in
                           enumerate(_list(_get(private, "limitations", "the file"), "limitations"))],
           "source": {"path": Path(path).name, "sha256": digest, "backtest_version": private["version"],
                      "rules_version": _text(_get(private, "rules_version", "the file"), "rules_version"),
                      "lookback": lookback_of(private), "evaluated": evaluated_of(private),
                      "regimes": regimes_of(private), "account": account_of(private)},
           "gates": {gate: gate_rows(private, gate) for gate in GATES}}
    count = out["source"]["evaluated"]["count"]
    for gate in GATES:
        if len(out["gates"][gate]) != count:
            raise TimelineError(f"{gate}: {len(out['gates'][gate])} nights but {count} sessions evaluated")
    leaks = private_leaks(out, tickers_of(private))
    if leaks:
        raise TimelineError("the timeline would carry what the private file keeps private: " + "; ".join(leaks))
    return out


def read(path: Path) -> dict:
    """The timeline of the private file at ``path``, read where it is."""
    data = Path(path).read_bytes()
    return build(json.loads(data), path=path, digest=hashlib.sha256(data).hexdigest())


def encode(timeline: dict) -> str:
    return json.dumps(timeline, indent=1, sort_keys=True, allow_nan=False) + "\n"


def same_file(a: Path, b: Path) -> bool:
    """Whether two paths name one file: the same resolved path, or (when
    both exist) the same file by another name, such as a hard link."""
    a, b = Path(a), Path(b)
    if a.resolve() == b.resolve():
        return True
    try:
        return a.exists() and b.exists() and os.path.samefile(a, b)
    except OSError:
        return False


def counts_line(timeline: dict, written: Path | None) -> str:
    parts = []
    for gate in GATES:
        rows = timeline["gates"][gate]
        parts.append(f"{gate}: {len(rows)} sessions, {sum(r['tickets'] for r in rows)} tickets, "
                     f"{sum(r['settled']['n'] for r in rows)} settled")
    where = f"; written {written}" if written else ""
    return f"timeline {timeline['version']} over {timeline['source']['path']}: " + "; ".join(parts) + where


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backtest", type=Path, required=True, help="the private backtest.json, read where it is")
    parser.add_argument("--output", type=Path, default=None,
                        help="where to write the timeline (anywhere but over the private file: it carries no "
                             "price and no ticker); stdout if omitted")
    args = parser.parse_args(argv)
    try:
        if args.output is not None and same_file(args.output, args.backtest):
            raise TimelineError(f"--output {args.output} is the private file itself; the timeline is never "
                                "written over it")
        timeline = read(args.backtest)
        text = encode(timeline)
        if args.output is None:
            print(text, end="")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
            print(counts_line(timeline, args.output))
        return 0
    except (TimelineError, ValueError, KeyError, TypeError, AttributeError, IndexError, OSError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
