"""The scorecard read honestly (``scorecard_reading``), beside the record's own.

``record.scorecard()`` counts tickets and sums R, and its numbers do not move
here. This block says what those counts do not: how many distinct setups the
tickets are (a setup issued again on a later night is one setup), which model
account each ticket was sized against, what the stopped tickets read at the
session's close and at its low beside the stop they were booked at
(``model_record``), and which of the earlier sessions' breadth figures this
record computes differently from the publication before it. Real trades are
not public: what the owner's own fills say against the model is read on his
computer from a private copy of ``docs/positions-template.json``
(``tools/positions_compare.py``).

The page, the mail and ``orders.json`` print the block's own sentences.
``faults()`` holds its shape under rules that write it.
"""
from __future__ import annotations

from typing import Any

VERSION = 1
#: the breadth figures a later record can compute differently for an earlier session
REVISION_FIELDS = ("up4", "down4", "ratio_10d")
#: the revised sessions the block names; the rest are counted
MAX_REVISIONS = 10
COMPUTED, NOT_COMPUTED, UNRECONCILED = "computed", "not_computed", "unreconciled"
STATUSES = (COMPUTED, NOT_COMPUTED, UNRECONCILED)
REAL_VS_MODEL = ("Real trades are not public: an execution agent fills a private copy of "
                 "docs/positions-template.json, and tools/positions_compare.py reads it beside the published "
                 "record on the owner's computer, real R beside model R.")
STOP_NAMES = ("booked", "at_close", "at_low")


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _history(record: dict) -> dict:
    out = {}
    for row in _list(_dict(_dict(record).get("breadth")).get("history")):
        if isinstance(row, dict) and isinstance(row.get("date"), str):
            out[row["date"]] = {f: row.get(f) for f in REVISION_FIELDS}
    return out


def _r(value: float | None) -> str:
    return "not given" if value is None else f"{value:+.2f}R"


def breadth_revisions(previous: dict | None, data: dict) -> dict:
    """The sessions both records' breadth histories carry, and those whose
    figures this record computes differently from the one before it."""
    previous = _dict(previous)
    session = _dict(previous.get("run")).get("session")
    then, now = _history(previous), _history(data)
    shared = sorted(set(then) & set(now))
    differ = [{"session": d, "published": then[d], "revised": now[d]} for d in shared if then[d] != now[d]]
    if not previous or not then:
        sentence = "There is no earlier publication's breadth history to compare."
    elif not differ:
        sentence = (f"The {len(shared)} earlier sessions this record and the {session} publication both carry read "
                    "the same breadth figures in each.")
    else:
        named = "; ".join(
            f"{r['session']} " + ", ".join(f"{f} {r['published'][f]} to {r['revised'][f]}"
                                           for f in REVISION_FIELDS if r["published"][f] != r["revised"][f])
            for r in differ[:MAX_REVISIONS])
        sentence = (f"Of the {len(shared)} earlier sessions this record and the {session} publication both carry, "
                    f"{len(differ)} read differently tonight than when published: {named}"
                    + (f"; and {len(differ) - MAX_REVISIONS} more" if len(differ) > MAX_REVISIONS else "") + ".")
    return {"previous_session": session, "compared": len(shared), "differ_count": len(differ),
            "differ": differ[:MAX_REVISIONS], "sentence": sentence}


def model_summary(block: dict | None) -> dict:
    """The model-record block's own figures that the scorecard does not print."""
    block = _dict(block)
    status = block.get("status") if block.get("status") in STATUSES else NOT_COMPUTED
    if status != COMPUTED:
        return {"status": status, "reason": block.get("reason") or "the model record was not computed",
                "sentences": [s for s in _list(block.get("sentences")) if isinstance(s, str)][:3]}
    stops = _dict(block.get("stops"))
    return {
        "status": COMPUTED, "reason": None,
        "tickets": block.get("tickets"), "distinct_setups": block.get("distinct_setups"),
        "reissued_tickets": block.get("reissued_tickets"),
        "buckets": block.get("buckets"), "buckets_by_setup": block.get("buckets_by_setup"),
        "sum_r": block.get("sum_r"),
        "eras": [{k: e.get(k) for k in ("label", "issued_equity", "risk_pct", "from", "through", "tickets", "setups",
                                         "settled", "wins", "losses", "breakeven", "sum_r")}
                 for e in _list(block.get("eras")) if isinstance(e, dict)],
        "stops": {"count": stops.get("count"), "unexamined": stops.get("unexamined"),
                  "sum_r": {n: _dict(stops.get("sum_r")).get(n) for n in STOP_NAMES},
                  "settled_sum_r": {n: _dict(stops.get("settled_sum_r")).get(n) for n in STOP_NAMES}},
        "sentences": [s for s in _list(block.get("sentences")) if isinstance(s, str)],
    }


def stop_sentence(summary: dict) -> str | None:
    stops = _dict(summary.get("stops"))
    if summary.get("status") != COMPUTED or not stops.get("count"):
        return None
    sums = _dict(stops.get("sum_r"))
    return (f"The {stops['count']} stopped ticket{'' if stops['count'] == 1 else 's'} booked at the stop "
            f"{'sums' if stops['count'] == 1 else 'sum'} to {_r(sums.get('booked'))}; read at that session's close, "
            f"{_r(sums.get('at_close'))}; at its low, {_r(sums.get('at_low'))}.")


def build(model_block: dict | None, previous: dict | None, data: dict) -> dict:
    model = model_summary(model_block)
    revisions = breadth_revisions(previous, data)
    sentences = []
    if model["status"] == COMPUTED and _num(model.get("tickets")):
        sentences.append(f"{model['tickets']} ticket{'' if model['tickets'] == 1 else 's'} in the scorecard's window "
                         f"{'is' if model['tickets'] == 1 else 'are'} {model['distinct_setups']} distinct "
                         f"setup{'' if model['distinct_setups'] == 1 else 's'}.")
        eras = [e for e in model["eras"] if e.get("issued_equity") is not None]
        unknown = sum(e.get("tickets") or 0 for e in model["eras"] if e.get("issued_equity") is None)
        if eras:
            sentences.append("By model account: " + "; ".join(
                f"{e['label']}, {e['tickets']} ticket{'' if e['tickets'] == 1 else 's'} from {e['from']} through "
                f"{e['through']}, {e['settled']} settled, {_r(e['sum_r']) if e['settled'] else 'no R yet'}"
                for e in eras) + "."
                + (f" No model account is recorded for {unknown} more ticket{'' if unknown == 1 else 's'}."
                   if unknown else ""))
        elif unknown:
            sentences.append(f"No model account is recorded for the {unknown} ticket{'' if unknown == 1 else 's'}.")
        stop = stop_sentence(model)
        if stop:
            sentences.append(stop)
    else:
        sentences.append(f"The model record is {model['status'].replace('_', ' ')}: {model['reason']}.")
    sentences.append(revisions["sentence"])
    sentences.append(REAL_VS_MODEL)
    return {"version": VERSION, "status": model["status"], "model_record": model,
            "breadth_revisions": revisions, "real_vs_model": {"status": "private", "sentence": REAL_VS_MODEL},
            "sentences": sentences}


def faults(data: dict) -> list[str]:
    """The block's shape, one level in; asked for only under rules that write it."""
    archived = _dict(_dict(data.get("rules")).get("pipeline")).get("scorecard_reading_version")
    block = data.get("scorecard_reading")
    if archived is None:
        return [] if block is None else ["scorecard_reading present under rules that do not write it"]
    if archived != VERSION:
        return [f"scorecard_reading version {archived!r} is not one this code reads"]
    if not isinstance(block, dict):
        return ["scorecard_reading is missing or not an object"]
    out = []
    if block.get("version") != VERSION or block.get("status") not in STATUSES:
        out.append("scorecard_reading version or status is not this code's")
    if not isinstance(block.get("sentences"), list) or not all(isinstance(s, str) for s in block["sentences"]):
        out.append("scorecard_reading sentences are not a list of strings")
    revisions = block.get("breadth_revisions")
    if not isinstance(revisions, dict) or not isinstance(revisions.get("differ"), list) \
            or not isinstance(revisions.get("sentence"), str):
        out.append("scorecard_reading breadth_revisions is not readable")
    if not isinstance(block.get("model_record"), dict) or block["model_record"].get("status") != block.get("status"):
        out.append("scorecard_reading model_record does not carry the block's status")
    if _dict(block.get("real_vs_model")).get("sentence") != REAL_VS_MODEL:
        out.append("scorecard_reading real_vs_model is not this code's sentence")
    return out
