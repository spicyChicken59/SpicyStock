"""tools.backtest_timeline: the owner's private ``backtest.json`` reduced to
one price-free, ticker-free row per night per gate. The private file here
is built by hand in the shape ``historical_backtest.run()`` writes -- two
gates, three nights, walked rows with a settled win, a loss, a breakeven,
uncertain fills (two of one kind on one night), a plan never filled and one
still pending, tickers and prices wherever the real file carries them --
and written through the backtest's own encoder, so the reader is exercised
over the bytes it will meet. Four names sit in exactly one of the four
places the private file names a stock, so the sweep is shown to read each
place on its own. Every held number is computed by hand beside its
assertion, every list of fields is written here rather than read off the
module, and every refusal and every held number is shown to fail on a
mutated copy."""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import re
from datetime import date

import pytest

from src import plan, record
from tools import backtest_timeline as tl
from tools import historical_backtest as backtest

S1, S2, S3 = "2026-03-02", "2026-03-03", "2026-03-04"
#: one name in each place the private file names a stock, and in no other
TRADE_ONLY, CANDIDATE_ONLY, ROW_ONLY, PICK_ONLY = "TRO", "CDO", "RWO", "PKO"
SOLE_SOURCE = [("trades", TRADE_ONLY), ("candidates", CANDIDATE_ONLY), ("rows", ROW_ONLY), ("picks", PICK_ONLY)]
#: the names the private file carries; none may reach the output
TICKERS = ("QQZ", "WXV", "KLM", "PRT", "ZZT", "RDN", "LST", "NMO", "UQV",
           TRADE_ONLY, CANDIDATE_ONLY, ROW_ONLY, PICK_ONLY)
#: the prices the private file carries, as the JSON text spells them
PRICES = ("124.21", "126.47", "121.42", "505.88", "134.15", "149.05", "129.18", "99.99")
PRODUCTION, UNGATED = backtest.PRODUCTION, backtest.NO_GATE


def regime(verdict, ratio_10d, ratio_5d, up4, down4, up4_10d, down4_10d, up50_month) -> dict:
    return {"verdict": verdict, "ratio_10d": ratio_10d, "ratio_5d": ratio_5d, "up4_10d": up4_10d,
            "down4_10d": down4_10d, "up4": up4, "down4": down4, "up50_month": up50_month, "universe": 4000,
            "reasons": [f"the 10-day ratio reads {ratio_10d}"]}


def candidate(ticker: str, grade: str, eligible: bool, action: str | None) -> dict:
    """``historical_backtest._slim()``'s shape: a ticker and a plan with prices."""
    return {"ticker": ticker, "scan": "burst", "grade": grade, "score": 9.5, "vetoes": [], "gain_pct": 5.12,
            "plan": {"eligible": eligible, "action": action, "entry_ref": 124.21, "limit": 126.47, "stop": 121.42,
                     "shares": 4, "position_usd": 505.88, "reason": None if eligible else "no_new_longs"}}


def pick(ticker: str, session: str, grade: str, verdict: str) -> dict:
    """``pipeline.pick_of()``'s shape plus the record's date and regime."""
    return {"evidence_ref": "sha256:" + "ab" * 32, "ticker": ticker, "date": session, "kind": "burst",
            "grade": grade, "score": 9.5, "regime": verdict, "entry_ref": 124.21, "entry_low": 121.42,
            "entry_high": 126.47, "day2_spent_above": 129.18, "limit_basis": "stop_line", "trigger": 124.21,
            "limit": 126.47, "stop": 121.42, "shares": 4, "targets": {"low": 134.15, "high": 149.05},
            "order_json": {"symbol": ticker, "limit": 126.47, "stop": 121.42, "price": 99.99}}


def row(ticker: str, session: str, grade: str, verdict: str, bucket: str, r=None, status=None,
        uncertainty=None) -> dict:
    """``record.scorecard_rows()``'s shape."""
    return {"ticker": ticker, "picked": session, "kind": "burst", "grade": grade, "regime": verdict,
            "evidence_ref": "sha256:" + "ab" * 32, "through": S3, "horizon": "2026-03-11", "r": r,
            "spy_pct": 0.3 if r is not None else None, "filled": bucket in ("settled", "open"),
            "uncertainty": uncertainty, "status": status, "bucket": bucket}


def night(session: str, reg: dict, counts: dict, *, gate: bool, eligible: int, trades: list[str],
          cut: dict, slots_held: int, candidates: list[dict]) -> dict:
    """``measure()``'s row with ``decide()``'s fields on top."""
    return {"session": session, "with_bars": 4001, "stale": 3, "gapped": 1, "unreadable": 0, "price_excluded": 7,
            "regime": copy.deepcopy(reg), "scan_errors": 0, **copy.deepcopy(counts), "gate": gate,
            "eligible_plans": eligible, "trades": list(trades), "cut": dict(cut), "slots_held": slots_held,
            "candidates": copy.deepcopy(candidates)}


#: the three nights' measurements: the same market read for both gates
MEASURED = {
    S1: (regime("yellow", 1.12, 1.05, 180, 160, 1900, 1700, 12),
         {"counted": 3990, "measured": 3985, "bursts": 7, "grades": {"A+": 1, "A": 2, "B": 4}}),
    S2: (regime("red", 0.86, 0.70, 90, 210, 1500, 1750, 8),
         {"counted": 3988, "measured": 3980, "bursts": 3, "grades": {"A": 1, "B": 2}}),
    S3: (regime("yellow", 1.03, 1.20, 220, 140, 1800, 1740, 15),
         {"counted": 3991, "measured": 3989, "bursts": 9, "grades": {"A+": 2, "A": 1, "B": 3, "C": 3}}),
}


def build_private() -> dict:
    buy = plan.ORDER_ACTIONS[-1]
    production_nights = [
        night(S1, *MEASURED[S1], gate=True, eligible=2, trades=["QQZ", "WXV"], cut={"slot_cap": 1}, slots_held=0,
              candidates=[candidate("QQZ", "A+", True, buy), candidate("WXV", "A", True, buy),
                          candidate("ZZT", "A", True, buy), candidate(CANDIDATE_ONLY, "B", False, None)]),
        night(S2, *MEASURED[S2], gate=True, eligible=0, trades=[], cut={"no_new_longs": 1}, slots_held=2,
              candidates=[candidate("RDN", "A", False, None)]),
        night(S3, *MEASURED[S3], gate=True, eligible=3, trades=["QQZ", "KLM", "PRT"], cut={}, slots_held=1,
              candidates=[candidate(t, "A+", True, buy) for t in ("QQZ", "KLM", "PRT", "LST")]),
    ]
    ungated_nights = [
        night(S1, *MEASURED[S1], gate=False, eligible=3, trades=["QQZ", "WXV", "ZZT"], cut={}, slots_held=0,
              candidates=production_nights[0]["candidates"]),
        night(S2, *MEASURED[S2], gate=False, eligible=2, trades=[TRADE_ONLY, "UQV"], cut={}, slots_held=3,
              candidates=[candidate("RDN", "A", True, buy), candidate("UQV", "A", True, buy)]),
        night(S3, *MEASURED[S3], gate=False, eligible=5, trades=["QQZ", "KLM", "PRT", "LST", "NMO"], cut={},
              slots_held=2, candidates=production_nights[2]["candidates"] + [candidate("NMO", "A", True, buy)]),
    ]
    production_rows = [row("QQZ", S1, "A+", "yellow", "settled", r=1.68, status="exit"),
                       row("WXV", S1, "A", "yellow", "settled", r=-0.80, status="stopped"),
                       row("QQZ", S3, "A+", "yellow", "uncertain", status="uncertain", uncertainty="stop_sequence"),
                       row("KLM", S3, "A+", "yellow", "settled", r=0.0, status="expired"),
                       row("PRT", S3, "A+", "yellow", "settled", r=-1.0, status="stopped")]
    # the two gates are two records: the same walk, but no row shared between them
    ungated_rows = (copy.deepcopy(production_rows[:2])
                    + [row("ZZT", S1, "A", "yellow", "not_filled", status="not_filled"),
                       row("RDN", S2, "A", "red", "uncertain", status="uncertain", uncertainty="trigger_timing"),
                       row("UQV", S2, "A", "red", "uncertain", status="uncertain", uncertainty="trigger_timing")]
                    + copy.deepcopy(production_rows[2:])
                    + [row("LST", S3, "A+", "yellow", "pending"),
                       row("NMO", S3, "A", "yellow", "settled", r=0.26, status="exit")])
    nights = {PRODUCTION: production_nights, UNGATED: ungated_nights}
    rows = {PRODUCTION: production_rows, UNGATED: ungated_rows}
    # the timeline counts a night's tickets and walked plans and never matches
    # their names, which is what lets one name sit in one place only: the
    # ungated LST plan is picked as PICK_ONLY, and NMO is walked as ROW_ONLY
    renamed_picks = {UNGATED: {"LST": PICK_ONLY}}
    outcomes = {}
    for gate in backtest.GATES:
        picks = [pick(renamed_picks.get(gate, {}).get(r["ticker"], r["ticker"]), r["picked"], r["grade"], r["regime"])
                 for r in rows[gate]]
        outcomes[gate] = {"tickets_issued": len(picks), "summary": record.summarize_scorecard(rows[gate]),
                          "rows": rows[gate],
                          "by_grade": backtest._partition(rows[gate], lambda r: r.get("grade")),
                          "by_regime": backtest._partition(rows[gate], lambda r: r.get("regime")),
                          "by_month": backtest._partition(rows[gate], lambda r: r["picked"][:7]),
                          "picks": picks}
    ungated_rows[-1]["ticker"] = ROW_ONLY
    return {
        "version": backtest.VERSION, "reader": backtest.READER, "limitations": list(backtest.LIMITATIONS),
        "archive": {"manifest_sha256": "f" * 64, "symbols": 4001, "intended": 4780, "price_exempt": 1,
                    "statuses": {"complete": 4001}, "queries": ["q-2026-09-25"], "non_terminal_queries": [],
                    "sessions": {"from": "2025-08-04", "through": "2026-09-25", "count": 288}},
        "lookback": {"sessions": 130, "production": backtest.PRODUCTION_LOOKBACK,
                     "equivalence": {"required": True, "compared": 28, "differences": [], "status": "PASS"}},
        "account": plan.Account().to_dict(), "rules_version": "abc123def456",
        "evaluated": {"from": S1, "through": S3, "count": 3, "seconds": 91.4},
        "regimes": {"verdicts": {"yellow": 2, "red": 1},
                    "ratio_10d": {"min": 0.86, "max": 1.12, "median": 1.03, "defined": 3}},
        "nights": nights, "outcomes": outcomes,
    }


def write(tmp_path, private) -> os.PathLike:
    """The private file as the backtest writes it, through its own encoder."""
    path = tmp_path / "private" / "backtest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(backtest._encode(private), encoding="utf-8")
    return path


def write_raw(tmp_path, private):
    """The private file through plain ``json.dumps``, which spells NaN and
    Infinity where the backtest's own encoder refuses them: a file the
    reader must still meet, because ``json.loads`` accepts them."""
    path = tmp_path / "raw" / "backtest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(private, allow_nan=True), encoding="utf-8")
    return path


@pytest.fixture
def private() -> dict:
    return build_private()


@pytest.fixture
def path(tmp_path, private):
    return write(tmp_path, private)


@pytest.fixture
def timeline(path) -> dict:
    return tl.read(path)


def rows_of(timeline: dict, gate: str) -> dict:
    return {r["session"]: r for r in timeline["gates"][gate]}


def refused(capsys, tmp_path, private, *, raw: bool = False) -> str:
    """What the CLI prints over a file it must refuse; the exit is 2 and
    nothing is written."""
    out = tmp_path / "out" / "timeline.json"
    capsys.readouterr()
    p = (write_raw if raw else write)(tmp_path, private)
    assert tl.main(["--backtest", str(p), "--output", str(out)]) == 2
    assert not out.exists()
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("refused: ") and captured.err.count("\n") == 1
    return captured.err[len("refused: "):-1]


# ------------------------------------------------------------- the rows ----
#: every field a night row carries, written here rather than read off the module
ROW_KEYS = {"session", "verdict", "ratio_10d", "ratio_5d", "up4", "down4", "up4_10d", "down4_10d", "universe",
            "reason", "counted", "measured", "bursts", "grades", "eligible_plans", "cut", "slots_held",
            "tickets", "buckets", "settled", "r", "uncertainty"}
#: each field copied off a night, where the night holds it, and a value to move it to
COPIED_FIELDS = [("verdict", "regime", "green"), ("ratio_10d", "regime", 1.5), ("ratio_5d", "regime", 1.4),
                 ("up4", "regime", 181), ("down4", "regime", 161), ("up4_10d", "regime", 1901),
                 ("down4_10d", "regime", 1701), ("universe", "regime", 4001),
                 ("counted", "night", 3991), ("measured", "night", 3986), ("bursts", "night", 8),
                 ("grades", "night", {"C": 7}), ("eligible_plans", "night", 4), ("cut", "night", {"equity": 1}),
                 ("slots_held", "night", 1)]


def test_every_night_row_copies_the_regime_and_the_counts_and_counts_its_tickets(timeline, private):
    for gate in backtest.GATES:
        got, nights = timeline["gates"][gate], private["nights"][gate]
        assert [r["session"] for r in got] == [n["session"] for n in nights] == [S1, S2, S3]
        for out, src in zip(got, nights):
            assert set(out) == ROW_KEYS, (gate, out["session"])
            for key, where, _ in COPIED_FIELDS:
                holder = src["regime"] if where == "regime" else src
                assert out[key] == holder[key], (gate, out["session"], key)
            assert out["tickets"] == len(src["trades"])
            assert out["reason"] is None
    assert [r["tickets"] for r in timeline["gates"][PRODUCTION]] == [2, 0, 3]
    assert [r["tickets"] for r in timeline["gates"][UNGATED]] == [3, 2, 5]
    assert rows_of(timeline, PRODUCTION)[S2]["verdict"] == "red" and rows_of(timeline, PRODUCTION)[S2]["ratio_10d"] == 0.86


@pytest.mark.parametrize("key, where, moved", COPIED_FIELDS)
def test_each_copied_field_is_read_off_the_night_not_assumed(private, tmp_path, key, where, moved):
    """Prove the copy is live: move the night's value and the row follows."""
    mutated = copy.deepcopy(private)
    for gate in backtest.GATES:
        holder = mutated["nights"][gate][0]["regime"] if where == "regime" else mutated["nights"][gate][0]
        holder[key] = copy.deepcopy(moved)
    original = private["nights"][PRODUCTION][0]["regime"] if where == "regime" else private["nights"][PRODUCTION][0]
    out = rows_of(tl.read(write(tmp_path, mutated)), PRODUCTION)[S1]
    assert out[key] == moved != original[key]


def test_the_settled_block_is_the_hand_arithmetic_over_the_nights_own_rows(timeline):
    # production, first night: QQZ +1.68 and WXV -0.80 settled.
    #   sum  = 1.68 + (-0.80) = 0.88; mean = 0.88 / 2 = 0.44; median of two = 0.44
    first = rows_of(timeline, PRODUCTION)[S1]
    assert first["r"] == [-0.80, 1.68] == sorted(first["r"])
    assert first["settled"] == {"n": 2, "wins": 1, "losses": 1, "breakeven": 0,
                                "sum_r": 0.88, "mean_r": 0.44, "median_r": 0.44}
    assert first["buckets"] == {**{b: 0 for b in record.SCORECARD_BUCKETS}, "settled": 2}
    # production, third night: KLM 0.0 (breakeven) and PRT -1.0 settled; QQZ uncertain, scored nowhere.
    #   sum = 0.0 + (-1.0) = -1.0; mean = -1.0 / 2 = -0.5; median = -0.5
    third = rows_of(timeline, PRODUCTION)[S3]
    assert third["r"] == [-1.0, 0.0]
    assert third["settled"] == {"n": 2, "wins": 0, "losses": 1, "breakeven": 1,
                                "sum_r": -1.0, "mean_r": -0.5, "median_r": -0.5}
    # the ungated first night settles the same two and adds a plan never filled
    ungated = rows_of(timeline, UNGATED)[S1]
    assert ungated["settled"] == first["settled"] and ungated["tickets"] == 3
    assert ungated["buckets"]["not_filled"] == 1 and ungated["buckets"]["settled"] == 2
    # the ungated third night settles three: KLM 0.0, PRT -1.0, and +0.26.
    #   sum = 0.0 + (-1.0) + 0.26 = -0.74; mean = -0.74 / 3 = -0.24666... -> -0.247 at three places
    #   (-0.25 at two, which is why the mean keeps one place more than the sum); median of three = 0.0
    last = rows_of(timeline, UNGATED)[S3]
    assert last["r"] == [-1.0, 0.0, 0.26]
    assert last["settled"] == {"n": 3, "wins": 1, "losses": 1, "breakeven": 1,
                               "sum_r": -0.74, "mean_r": -0.247, "median_r": 0.0}


def settled_on(private: dict, gate: str, session: str) -> list[dict]:
    return [r for r in private["outcomes"][gate]["rows"] if r["picked"] == session and r["bucket"] == "settled"]


def test_the_sum_and_the_median_are_rounded_to_two_places_and_the_mean_to_three(private, tmp_path):
    """R as the walk writes it has two places, so on the fixture's nights no
    rounding shows; these three carry a third, so each figure's own does."""
    mutated = copy.deepcopy(private)
    settled = settled_on(mutated, UNGATED, S3)
    assert [r["r"] for r in settled] == [0.0, -1.0, 0.26]
    for r, value in zip(settled, (0.333, -0.801, 1.687)):
        r["r"] = value
    last = rows_of(tl.read(write(tmp_path, mutated)), UNGATED)[S3]
    # sorted: -0.801, 0.333, 1.687
    #   sum    = -0.801 + 0.333 + 1.687 = 1.219      -> 1.22 at two places (1.219 at three)
    #   mean   = 1.219 / 3 = 0.406333...              -> 0.406 at three places (0.41 at two)
    #   median = the middle of three = 0.333          -> 0.33 at two places (0.333 at three)
    assert last["r"] == [-0.801, 0.333, 1.687]
    assert last["settled"] == {"n": 3, "wins": 2, "losses": 1, "breakeven": 0,
                               "sum_r": 1.22, "mean_r": 0.406, "median_r": 0.33}


def test_the_sum_and_the_mean_are_math_fsum_not_a_running_sum(private, tmp_path):
    """No R a plan prints tells the two apart -- on Python 3.12 ``sum()`` is
    itself compensated -- so this night carries three values that do. Their
    exact sum is 2**53 + 1 + 2**-60, past the midpoint 2**53 + 1 between the
    doubles 2**53 and 2**53 + 2, so the correctly rounded sum is 2**53 + 2;
    a running sum loses 2**-60 into 1.0, lands on the midpoint and ties to
    the even 2**53."""
    mutated = copy.deepcopy(private)
    for r, value in zip(settled_on(mutated, UNGATED, S3), (2.0 ** 53, 1.0, 2.0 ** -60)):
        r["r"] = value
    rs = sorted([2.0 ** 53, 1.0, 2.0 ** -60])
    assert sum(rs) == 2.0 ** 53 != 2.0 ** 53 + 2, "the case must separate the two on this interpreter"
    last = rows_of(tl.read(write(tmp_path, mutated)), UNGATED)[S3]
    assert last["r"] == rs
    # sum  = 2**53 + 2 = 9007199254740994.0
    # mean = (2**53 + 2) / 3 = 3002399751580331.33..., whose nearest double is 3002399751580331.5
    #        (a running sum's 2**53 / 3 would be 3002399751580330.5)
    # median of three = 1.0
    assert last["settled"] == {"n": 3, "wins": 3, "losses": 0, "breakeven": 0,
                               "sum_r": 9007199254740994.0, "mean_r": 3002399751580331.5, "median_r": 1.0}


def test_a_changed_r_moves_the_nights_block_and_nothing_else(private, tmp_path, timeline):
    mutated = copy.deepcopy(private)
    assert mutated["outcomes"][PRODUCTION]["rows"][0]["r"] == 1.68
    mutated["outcomes"][PRODUCTION]["rows"][0]["r"] = 2.68
    moved = tl.read(write(tmp_path, mutated))
    first = rows_of(moved, PRODUCTION)[S1]
    # 2.68 + (-0.80) = 1.88; 1.88 / 2 = 0.94; median of two = 0.94
    assert first["r"] == [-0.80, 2.68]
    assert first["settled"] == {"n": 2, "wins": 1, "losses": 1, "breakeven": 0,
                                "sum_r": 1.88, "mean_r": 0.94, "median_r": 0.94}
    for t in (moved, timeline):
        rows_of(t, PRODUCTION)[S1].pop("settled")
        rows_of(t, PRODUCTION)[S1].pop("r")
        t["source"].pop("sha256")
    assert moved == timeline


def test_an_uncertain_row_is_counted_by_bucket_and_by_kind_and_scored_nowhere(timeline):
    third = rows_of(timeline, PRODUCTION)[S3]
    assert third["buckets"] == {**{b: 0 for b in record.SCORECARD_BUCKETS}, "settled": 2, "uncertain": 1}
    assert third["uncertainty"] == {"stop_sequence": 1} and None not in third["r"]
    # the ungated red night: two tickets, both uncertain, both for the trigger's timing
    red = rows_of(timeline, UNGATED)[S2]
    assert red["tickets"] == 2 and red["buckets"]["uncertain"] == 2 and red["uncertainty"] == {"trigger_timing": 2}
    assert red["settled"] == {"n": 0, "wins": 0, "losses": 0, "breakeven": 0,
                              "sum_r": None, "mean_r": None, "median_r": None}
    last = rows_of(timeline, UNGATED)[S3]
    assert last["buckets"]["pending"] == 1 and last["tickets"] == 5 and sum(last["buckets"].values()) == 5


def test_a_night_with_no_plan_has_an_empty_settled_block_and_zero_buckets(timeline):
    empty = rows_of(timeline, PRODUCTION)[S2]
    assert empty["tickets"] == 0 and empty["r"] == [] and empty["uncertainty"] == {}
    assert empty["settled"] == {"n": 0, "wins": 0, "losses": 0, "breakeven": 0,
                                "sum_r": None, "mean_r": None, "median_r": None}
    assert empty["buckets"] == {b: 0 for b in record.SCORECARD_BUCKETS}
    assert empty["verdict"] == "red" and empty["cut"] == {"no_new_longs": 1} and empty["slots_held"] == 2


def test_a_session_no_name_printed_on_keeps_its_reason_and_no_ratio(private, tmp_path):
    mutated = copy.deepcopy(private)
    for gate in backtest.GATES:
        mutated["nights"][gate][1]["regime"] = {"verdict": None, "reason": "no name printed on the session"}
        mutated["nights"][gate][1].update(trades=[], candidates=[], counted=0, measured=0, bursts=0, grades={})
        mutated["outcomes"][gate]["rows"] = [r for r in mutated["outcomes"][gate]["rows"] if r["picked"] != S2]
        mutated["outcomes"][gate]["tickets_issued"] = len(mutated["outcomes"][gate]["rows"])
    out = rows_of(tl.read(write(tmp_path, mutated)), UNGATED)[S2]
    assert out["verdict"] is None and out["ratio_10d"] is None and out["universe"] is None
    assert out["reason"] == "no name printed on the session" and out["tickets"] == 0 and out["settled"]["n"] == 0


def test_the_one_reason_admitted_is_the_one_measure_writes():
    """The sentence is held to the backtest's own ``measure()`` over a
    session no name printed on, not to the name it is kept under."""
    archive = backtest.Archive(frames={}, intended=[], price_exempt=(), statuses={}, manifest_sha256="f" * 64,
                               queries=[], non_terminal=[])
    written = backtest.measure({}, date.fromisoformat(S1), backtest._universe(archive)).row["regime"]
    assert written == {"verdict": None, "reason": tl.NO_SESSION_REASON}


def test_a_reason_that_is_not_the_backtests_own_is_refused(private, tmp_path, capsys):
    mutated = copy.deepcopy(private)
    mutated["nights"][PRODUCTION][1]["regime"]["reason"] = "QQZ halted at 124.21"
    assert refused(capsys, tmp_path, mutated) == "nights.production[1].regime.reason is not the backtest's own sentence"


# ------------------------------------------------------------ the source ----
def test_the_source_names_the_file_by_basename_and_digest_and_copies_the_runs_context(timeline, path, private):
    text = tl.encode(timeline)
    assert set(timeline) == {"version", "reader", "limitations", "source", "gates"}
    assert set(timeline["source"]) == {"path", "sha256", "backtest_version", "rules_version", "lookback",
                                       "evaluated", "regimes", "account"}
    assert timeline["version"] == tl.VERSION
    assert timeline["source"]["path"] == "backtest.json" and str(path.parent) not in text
    assert timeline["source"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert timeline["source"]["backtest_version"] == backtest.VERSION
    assert timeline["source"]["rules_version"] == "abc123def456"
    for key in ("evaluated", "regimes", "account"):
        assert timeline["source"][key] == private[key], key
    assert tl.ACCOUNT_FIELDS == ("equity", "risk_pct", "max_position_pct", "max_open_positions")
    assert timeline["source"]["lookback"] == {"sessions": 130, "production": backtest.PRODUCTION_LOOKBACK,
                                              "equivalence": {"required": True, "compared": 28, "differences": 0,
                                                              "status": "PASS"}}
    assert timeline["reader"] == backtest.READER and timeline["limitations"] == list(backtest.LIMITATIONS)


#: blocks the timeline copies field by field: a field the private file grows
#: in any of them -- here a name as its key and a price as its value, and a
#: sentence carrying both -- is left behind, never published
PLANTED = [("account",), ("lookback",), ("lookback", "equivalence"), ("evaluated",), ("regimes",),
           ("regimes", "ratio_10d"), ("nights", PRODUCTION, 0), ("nights", PRODUCTION, 0, "regime"),
           ("outcomes", PRODUCTION)]


@pytest.mark.parametrize("trail", PLANTED, ids=lambda t: ".".join(map(str, t)))
def test_a_field_the_private_file_grows_is_left_behind(private, tmp_path, timeline, trail):
    mutated = copy.deepcopy(private)
    holder = mutated
    for step in trail:
        holder = holder[step]
    holder.update({"QQZ": 124.21, "note": "QQZ bought at 126.47"})
    moved = tl.read(write(tmp_path, mutated))
    text = tl.encode(moved)
    assert "QQZ" not in text and "124.21" not in text and "126.47" not in text and '"note"' not in text
    for t in (moved, timeline):
        t["source"].pop("sha256")
    assert moved == timeline


def test_a_failed_equivalence_is_reduced_to_a_count_because_its_fingerprints_carry_prices(private, tmp_path,
                                                                                        monkeypatch):
    mutated = copy.deepcopy(private)
    fp = backtest.fingerprint(private["nights"][PRODUCTION][0])
    assert any("QQZ" in str(c) for c in fp["candidates"]) and any(124.21 in p for p in fp["plans"])
    mutated["lookback"]["equivalence"].update(status="FAIL", differences=[{"session": S1, "shortened": fp,
                                                                          "production": fp}])
    p = write(tmp_path, mutated)
    out = tl.read(p)
    assert out["source"]["lookback"]["equivalence"]["differences"] == 1
    assert out["source"]["lookback"]["equivalence"]["status"] == "FAIL"
    text = tl.encode(out)
    assert not any(t in text for t in TICKERS) and not any(price in text for price in PRICES)
    # without the reduction the sweep is what stands between the fingerprints and the output
    monkeypatch.setattr(tl, "lookback_of", lambda private: dict(private["lookback"]))
    with pytest.raises(tl.TimelineError, match=r"differences\[0\]\.shortened\.candidates \(private key\)"):
        tl.read(p)


def test_an_unrelated_change_moves_only_the_copied_text_and_the_digest(private, tmp_path, timeline):
    mutated = copy.deepcopy(private)
    mutated["limitations"][0] = "The reader is not run; this sentence was changed for the test."
    moved = tl.read(write(tmp_path, mutated))
    assert moved["limitations"][0] == mutated["limitations"][0] != timeline["limitations"][0]
    assert moved["source"]["sha256"] != timeline["source"]["sha256"]
    for t in (moved, timeline):
        t.pop("limitations")
        t["source"].pop("sha256")
    assert moved == timeline


def test_the_vocabularies_are_the_ones_the_backtest_writes():
    """Each list the timeline reads a word against, written out here; the
    equivalence statuses also held to ``run()``'s own text."""
    assert set(tl.TALLIES) == {"grades", "cut"}
    assert tl.TALLIES["grades"] == ("A+", "A", "B", "C", "skip")
    assert tl.TALLIES["cut"] == ("slot_cap", "equity", "no_new_longs", "no_shares", "withheld")
    assert tl.VERDICT_KEYS == ("green", "yellow", "red", "null")
    assert tl.EQUIVALENCE_STATUSES == ("not required", "FAIL", "PASS", "BLOCKED: no session carries the full lookback")
    source = inspect.getsource(backtest.run)
    for status in tl.EQUIVALENCE_STATUSES:
        assert f'"{status}"' in source, status


# ------------------------------------------------------------- privacy ----
def sources_naming(private: dict, ticker: str) -> set[str]:
    """Which of the four lists name ``ticker``, read off the fixture here and
    not through the module."""
    found = set()
    for gate in backtest.GATES:
        for n in private["nights"][gate]:
            if ticker in n["trades"]:
                found.add("trades")
            if any(c.get("ticker") == ticker for c in n["candidates"]):
                found.add("candidates")
        if any(r["ticker"] == ticker for r in private["outcomes"][gate]["rows"]):
            found.add("rows")
        if any(p["ticker"] == ticker for p in private["outcomes"][gate]["picks"]):
            found.add("picks")
    return found


def test_the_serialised_timeline_carries_no_private_key_no_ticker_and_no_price(timeline, private):
    assert tl.PRIVATE_KEYS == frozenset({"ticker", "entry_ref", "entry_low", "entry_high", "limit", "stop",
                                         "trigger", "position_usd", "order_json", "targets", "day2_spent_above",
                                         "evidence_ref", "candidates"})
    text = tl.encode(timeline)
    for key in tl.PRIVATE_KEYS:
        assert f'"{key}"' not in text, key
    for ticker in TICKERS:
        assert ticker in json.dumps(private) and ticker not in text.upper(), ticker
    for price in PRICES:
        assert price in json.dumps(private) and price not in text, price
    assert "$" not in text
    assert tl.private_leaks(timeline, tl.tickers_of(private)) == []
    assert tl.tickers_of(private) == frozenset(TICKERS)


@pytest.mark.parametrize("source, ticker", SOLE_SOURCE)
def test_each_place_the_private_file_names_a_stock_is_read_on_its_own(private, tmp_path, source, ticker):
    """A name in one place only -- not also a trade, a candidate, a row or a
    pick -- is still a name the output may not carry."""
    assert sources_naming(private, ticker) == {source}
    assert ticker in tl.tickers_of(private)
    mutated = copy.deepcopy(private)
    mutated["limitations"][0] = f"A sentence that names {ticker.lower()} in passing."
    with pytest.raises(tl.TimelineError, match=r"timeline\.limitations\[0\] \(a ticker\)"):
        tl.read(write(tmp_path, mutated))


def test_a_ticker_is_a_whole_word_in_any_case_in_a_value_or_a_key_and_never_part_of_another(private):
    names = tl.tickers_of(private)
    assert tl.private_leaks({"note": "bought qqz at the open"}, names) == ["timeline.note (a ticker)"]
    assert tl.private_leaks({"note": "Bought Qqz."}, names) == ["timeline.note (a ticker)"]
    assert tl.private_leaks({"note": ["fine", "(WXV)"]}, names) == ["timeline.note[1] (a ticker)"]
    assert tl.private_leaks({"x": {"qqz": 1}}, names) == ["timeline.x.qqz (a ticker in its key)"]
    assert tl.private_leaks({"x": {"wxv_seen": 1}}, names) == ["timeline.x.wxv_seen (a ticker in its key)"]
    # inside another word it is not the name
    assert tl.private_leaks({"note": "QQZX and xqqz and qqz9 are other words", "qqzwxv": 1}, names) == []
    # a name with a dot is matched whole, in any case, too
    assert tl.private_leaks({"note": "brk.b rose"}, frozenset({"BRK.B"})) == ["timeline.note (a ticker)"]
    assert tl.private_leaks({"note": "brk.bx and xbrk.b rose"}, frozenset({"BRK.B"})) == []


def words_written(value, key=None) -> set[str]:
    """Every word of every key and string the timeline writes, but the
    free values -- the basename, the digests, the dates -- split here."""
    if isinstance(value, dict):
        found = set()
        for k, v in value.items():
            found |= {w.upper() for w in re.split(r"[^0-9A-Za-z]+", k) if w}
            found |= words_written(v, k)
        return found
    if isinstance(value, list):
        return set().union(*(words_written(v, key) for v in value)) if value else set()
    if isinstance(value, str) and key not in {"path", "sha256", "rules_version", "session", "from", "through"}:
        return {w.upper() for w in re.split(r"[^0-9A-Za-z]+", value) if w}
    return set()


def test_the_tools_own_words_pass_the_sweep_even_where_a_ticker_spells_one(timeline, path, monkeypatch):
    """A real universe has tickers that are words: A is a grade here, PATH
    and R field names. Make every word the timeline writes of its own a
    ticker: the realistic file still passes, because each key and string is
    one of the tool's words, and the same words in a string of another's
    are still caught. The basename is the owner's text, not the tool's: it
    is swept like any other, so its own words are left out of this universe
    (``test_a_private_file_named_after_a_stock_is_refused`` sweeps it)."""
    universe = words_written(timeline) - {"BACKTEST", "JSON"}
    assert {"A", "PATH", "R", "N", "CUT", "BREAKEVEN", "READER", "THE"} <= universe
    assert tl.private_leaks(timeline, frozenset(universe)) == []
    monkeypatch.setattr(tl, "tickers_of", lambda private: frozenset(universe))
    assert tl.read(path) == timeline
    assert tl.private_leaks({"note": "a path"}, frozenset(universe)) == ["timeline.note (a ticker)"]


def test_a_private_file_named_after_a_stock_is_refused(private, tmp_path):
    named = tmp_path / "qqz-run.json"
    named.write_text(backtest._encode(private), encoding="utf-8")
    with pytest.raises(tl.TimelineError, match=r"timeline\.source\.path \(a ticker\)"):
        tl.read(named)


def test_the_key_sweep_is_what_keeps_a_price_out(private, tmp_path, monkeypatch):
    """Copy the night's candidates block, which carries the plan's prices,
    into its row: the sweep refuses it by key; with the key list emptied the
    same build passes and the prices are in the text."""
    nameless = copy.deepcopy(private)
    for gate in backtest.GATES:
        for n in nameless["nights"][gate]:
            for c in n["candidates"]:
                del c["ticker"]
    p = write(tmp_path, nameless)
    row_of = tl.night_row
    monkeypatch.setattr(tl, "night_row", lambda n, rows, where: {**row_of(n, rows, where), "candidates": n["candidates"]})
    with pytest.raises(tl.TimelineError) as refusal:
        tl.read(p)
    message = str(refusal.value)
    assert "candidates (private key)" in message and "plan.limit (private key)" in message \
        and "plan.stop (private key)" in message and "plan.entry_ref (private key)" in message
    monkeypatch.setattr(tl, "PRIVATE_KEYS", frozenset())
    text = tl.encode(tl.read(p))
    assert '"candidates"' in text and "124.21" in text and "126.47" in text and "121.42" in text and "505.88" in text


def test_the_value_sweep_catches_a_ticker_under_a_key_the_list_does_not_name(private, tmp_path, monkeypatch):
    p = write(tmp_path, private)
    row_of = tl.night_row
    monkeypatch.setattr(tl, "PRIVATE_KEYS", frozenset())
    monkeypatch.setattr(tl, "night_row", lambda n, rows, where: {**row_of(n, rows, where), "trades": n["trades"]})
    with pytest.raises(tl.TimelineError, match=r"production\[0\]\.trades\[0\] \(a ticker\)"):
        tl.read(p)
    # and the intact candidates block is refused for its ticker values even with the key list emptied
    monkeypatch.setattr(tl, "night_row", lambda n, rows, where: {**row_of(n, rows, where), "candidates": n["candidates"]})
    with pytest.raises(tl.TimelineError, match=r"candidates\[0\]\.ticker \(a ticker\)"):
        tl.read(p)


def test_the_encoder_refuses_a_number_json_cannot_spell():
    with pytest.raises(ValueError):
        tl.encode({"r": [float("nan")]})
    with pytest.raises(ValueError):
        tl.encode({"r": [float("inf")]})


# ------------------------------------------------------------ refusals ----
def test_a_file_of_another_version_is_refused(private, tmp_path, capsys):
    good = write(tmp_path / "good", private)
    assert tl.main(["--backtest", str(good), "--output", str(tmp_path / "out" / "timeline.json")]) == 0
    mutated = copy.deepcopy(private)
    mutated["version"] = "historical-backtest-v2"
    bad = write(tmp_path / "bad", mutated)
    with pytest.raises(tl.TimelineError, match="not a historical-backtest-v1 file: version 'historical-backtest-v2'"):
        tl.read(bad)
    capsys.readouterr()
    assert tl.main(["--backtest", str(bad), "--output", str(tmp_path / "out" / "refused.json")]) == 2
    err = capsys.readouterr().err
    assert err.startswith("refused: not a historical-backtest-v1 file") and not (tmp_path / "out" / "refused.json").exists()


@pytest.mark.parametrize("block", ["nights", "outcomes"])
@pytest.mark.parametrize("gate", backtest.GATES)
def test_a_file_missing_a_gate_is_refused(private, tmp_path, block, gate):
    mutated = copy.deepcopy(private)
    del mutated[block][gate]
    with pytest.raises(tl.TimelineError, match=f"{block} missing the {gate} gate"):
        tl.read(write(tmp_path, mutated))


def test_a_walked_plan_on_a_session_no_night_evaluated_is_refused(private, tmp_path):
    mutated = copy.deepcopy(private)
    mutated["outcomes"][UNGATED]["rows"][3]["picked"] = "2026-03-05"
    with pytest.raises(tl.TimelineError, match="no_regime_gate: walked plans picked on 2026-03-05, sessions no night"):
        tl.read(write(tmp_path, mutated))


def test_a_night_whose_tickets_and_walked_plans_disagree_is_refused(private, tmp_path):
    dropped = copy.deepcopy(private)
    dropped["outcomes"][PRODUCTION]["rows"].pop()
    with pytest.raises(tl.TimelineError, match="2026-03-04: 3 tickets but 2 walked plans"):
        tl.read(write(tmp_path, dropped))
    added = copy.deepcopy(private)
    added["nights"][PRODUCTION][1]["trades"].append("ZZT")
    with pytest.raises(tl.TimelineError, match="2026-03-03: 1 tickets but 0 walked plans"):
        tl.read(write(tmp_path, added))


def test_a_walked_plan_in_no_bucket_the_scorecard_counts_is_refused(private, tmp_path, capsys):
    mutated = copy.deepcopy(private)
    mutated["outcomes"][PRODUCTION]["rows"][0]["bucket"] = "won"
    assert refused(capsys, tmp_path, mutated) == ("2026-03-02: 2 walked plans but 1 in the scorecard's buckets; "
                                                  "'won' is not a bucket the scorecard counts")


@pytest.mark.parametrize("kind, named", [(None, "None"), ("gap_down", "'gap_down'")])
def test_an_uncertain_plan_of_no_kind_the_scorecard_names_is_refused(private, tmp_path, capsys, kind, named):
    mutated = copy.deepcopy(private)
    qqz = mutated["outcomes"][PRODUCTION]["rows"][2]
    assert (qqz["picked"], qqz["bucket"], qqz["uncertainty"]) == (S3, "uncertain", "stop_sequence")
    qqz["uncertainty"] = kind
    assert refused(capsys, tmp_path, mutated) == ("2026-03-04: 1 uncertain plans but 0 of a kind the scorecard "
                                                  f"names; {named} is not one")


def test_a_night_written_twice_is_refused(private, tmp_path, capsys):
    mutated = copy.deepcopy(private)
    mutated["nights"][UNGATED].insert(2, copy.deepcopy(mutated["nights"][UNGATED][1]))
    assert refused(capsys, tmp_path, mutated) == ("no_regime_gate: the night of 2026-03-03 is written more than "
                                                  "once; its walked plans could not be told apart")


def test_a_gate_whose_nights_are_not_the_evaluated_count_is_refused(private, tmp_path, capsys):
    mutated = copy.deepcopy(private)
    mutated["evaluated"]["count"] = 4
    assert refused(capsys, tmp_path, mutated) == "production: 3 nights but 4 sessions evaluated"


@pytest.mark.parametrize("r, shown", [(float("nan"), "nan"), (float("inf"), "inf"), (None, "null"),
                                      ("1.68", "a string"), (True, "a boolean")])
def test_a_settled_plan_whose_r_is_not_a_finite_number_is_refused(private, tmp_path, capsys, r, shown):
    mutated = copy.deepcopy(private)
    mutated["outcomes"][PRODUCTION]["rows"][0]["r"] = r
    assert refused(capsys, tmp_path, mutated, raw=True) == \
        f"2026-03-02: a settled plan's R is {shown}, not a finite number"


def test_a_gate_whose_tickets_are_not_the_tickets_issued_is_refused_and_one_without_it_is_read(private, tmp_path,
                                                                                              capsys, timeline):
    mutated = copy.deepcopy(private)
    assert mutated["outcomes"][UNGATED]["tickets_issued"] == 10
    mutated["outcomes"][UNGATED]["tickets_issued"] = 11
    assert refused(capsys, tmp_path, mutated) == "no_regime_gate: the nights issued 10 tickets but the outcomes say 11"
    for gate in backtest.GATES:
        del mutated["outcomes"][gate]["tickets_issued"]
    moved = tl.read(write(tmp_path, mutated))
    for t in (moved, timeline):
        t["source"].pop("sha256")
    assert moved == timeline


@pytest.mark.parametrize("equivalence, message", [
    (None, "lookback.equivalence is null, not an object"),
    ("absent", "lookback has no equivalence"),
    ({"required": True, "compared": 28, "differences": [{"session": S1}], "status": "PASS"},
     "lookback.equivalence says 'PASS' (required True) over 1 differences"),
    ({"required": True, "compared": 28, "differences": [], "status": "FAIL"},
     "lookback.equivalence says 'FAIL' (required True) over 0 differences"),
    ({"required": True, "compared": 0, "differences": [], "status": "not required"},
     "lookback.equivalence says 'not required' (required True) over 0 differences"),
    ({"required": True, "compared": 28, "differences": [], "status": "PASSED"},
     "lookback.equivalence.status is not one of not required, FAIL, PASS, BLOCKED: no session carries the full "
     "lookback"),
], ids=["null", "absent", "pass-over-a-difference", "fail-over-none", "not-required-but-required", "unknown"])
def test_a_lookback_without_its_equivalence_or_contradicting_it_is_refused(private, tmp_path, capsys, equivalence,
                                                                          message):
    mutated = copy.deepcopy(private)
    if equivalence == "absent":
        del mutated["lookback"]["equivalence"]
    else:
        mutated["lookback"]["equivalence"] = equivalence
    assert refused(capsys, tmp_path, mutated) == message


def test_the_full_lookback_with_no_check_required_is_read(private, tmp_path):
    mutated = copy.deepcopy(private)
    mutated["lookback"] = {"sessions": backtest.PRODUCTION_LOOKBACK, "production": backtest.PRODUCTION_LOOKBACK,
                           "equivalence": {"required": False, "compared": 0, "differences": [],
                                           "status": "not required"}}
    assert tl.read(write(tmp_path, mutated))["source"]["lookback"]["equivalence"] == \
        {"required": False, "compared": 0, "differences": 0, "status": "not required"}


def _night0(p):
    return p["nights"][PRODUCTION][0]


#: a name where a word of a vocabulary belongs, or a price or a sentence
#: where a count or a ratio does: each refused by its path
MISPLACED = [
    ("ticker-as-grade", lambda p: _night0(p)["grades"].update(QQZ=1),
     "nights.production[0].grades key is not one of A+, A, B, C, skip"),
    ("ticker-as-cut", lambda p: _night0(p)["cut"].update(qqz=1),
     "nights.production[0].cut key is not one of slot_cap, equity, no_new_longs, no_shares, withheld"),
    ("ticker-as-verdict-tally", lambda p: p["regimes"]["verdicts"].update(QQZ=1),
     "regimes.verdicts key is not one of green, yellow, red, null"),
    ("ticker-as-verdict", lambda p: _night0(p)["regime"].update(verdict="QQZ"),
     "nights.production[0].regime.verdict is not one of green, yellow, red, None"),
    ("fractional-count", lambda p: _night0(p)["grades"].update({"A": 1.5}),
     "nights.production[0].grades.A is a number, not a count"),
    ("count-as-string", lambda p: _night0(p).update(counted="3990"),
     "nights.production[0].counted is a string, not a count"),
    ("negative-count", lambda p: _night0(p).update(slots_held=-1),
     "nights.production[0].slots_held is a number, not a count"),
    ("boolean-count", lambda p: _night0(p)["regime"].update(up4=True),
     "nights.production[0].regime.up4 is a boolean, not a count"),
    ("price-as-ratio-string", lambda p: _night0(p)["regime"].update(ratio_10d="124.21"),
     "nights.production[0].regime.ratio_10d is a string, not a finite number"),
    ("price-as-account-string", lambda p: p["account"].update(equity="124.21"),
     "account.equity is a string, not a finite number"),
    ("ticker-as-session", lambda p: _night0(p).update(session="QQZ"),
     "nights.production[0].session is not an ISO date"),
    ("sentence-as-evaluated-date", lambda p: p["evaluated"].update(through="QQZ on 2026-03-04"),
     "evaluated.through is not an ISO date"),
    ("ticker-as-rules-version", lambda p: p.update(rules_version=["QQZ"]),
     "rules_version is an array, not a string"),
]


@pytest.mark.parametrize("case, mutate, message", MISPLACED, ids=[m[0] for m in MISPLACED])
def test_a_value_outside_its_type_or_its_vocabulary_is_refused(private, tmp_path, capsys, case, mutate, message):
    mutated = copy.deepcopy(private)
    mutate(mutated)
    assert refused(capsys, tmp_path, mutated) == message


def _replace(p, trail, value):
    holder = p
    for step in trail[:-1]:
        holder = holder[step]
    holder[trail[-1]] = value
    return p


#: shapes that are not the backtest's file, each a sentence and never a traceback
MALFORMED = [
    ("top-level-array", lambda p: [p], "the file is an array, not a JSON object"),
    ("top-level-null", lambda p: None, "the file is null, not a JSON object"),
    ("top-level-string", lambda p: "backtest", "the file is a string, not a JSON object"),
    ("top-level-number", lambda p: 3, "the file is a number, not a JSON object"),
    ("nights-array", lambda p: _replace(p, ("nights",), [1]), "nights is an array, not an object"),
    ("gate-nights-object", lambda p: _replace(p, ("nights", PRODUCTION), {}),
     "nights.production is an object, not an array"),
    ("night-string", lambda p: _replace(p, ("nights", PRODUCTION, 0), "QQZ"),
     "nights.production[0] is a string, not an object"),
    ("regime-string", lambda p: _replace(p, ("nights", PRODUCTION, 0, "regime"), "red"),
     "nights.production[0].regime is a string, not an object"),
    ("regime-null", lambda p: _replace(p, ("nights", PRODUCTION, 0, "regime"), None),
     "nights.production[0].regime is null, not an object"),
    ("trades-object", lambda p: _replace(p, ("nights", PRODUCTION, 0, "trades"), {"QQZ": 1}),
     "nights.production[0].trades is an object, not an array"),
    ("candidate-string", lambda p: _replace(p, ("nights", PRODUCTION, 0, "candidates", 0), "QQZ"),
     "nights.production[0].candidates[0] is a string, not an object"),
    ("candidate-ticker-number", lambda p: _replace(p, ("nights", PRODUCTION, 0, "candidates", 0, "ticker"), 7),
     "nights.production[0].candidates[0].ticker is a number, not a string"),
    ("trade-number", lambda p: _replace(p, ("nights", PRODUCTION, 0, "trades", 0), 7),
     "nights.production[0].trades[0] is a number, not a name"),
    ("outcomes-array", lambda p: _replace(p, ("outcomes", PRODUCTION), []),
     "outcomes.production is an array, not an object"),
    ("row-string", lambda p: _replace(p, ("outcomes", PRODUCTION, "rows", 0), "QQZ"),
     "outcomes.production.rows[0] is a string, not an object"),
    ("row-picked-number", lambda p: _replace(p, ("outcomes", PRODUCTION, "rows", 0, "picked"), 20260302),
     "outcomes.production.rows[0].picked is a number, not a string"),
    ("pick-number", lambda p: _replace(p, ("outcomes", PRODUCTION, "picks", 0), 1),
     "outcomes.production.picks[0] is a number, not an object"),
    ("limitations-string", lambda p: _replace(p, ("limitations",), "none"),
     "limitations is a string, not an array"),
    ("account-array", lambda p: _replace(p, ("account",), []), "account is an array, not an object"),
]


@pytest.mark.parametrize("case, mutate, message", MALFORMED, ids=[m[0] for m in MALFORMED])
def test_a_file_of_another_shape_is_a_sentence_not_a_traceback(private, tmp_path, capsys, case, mutate, message):
    assert refused(capsys, tmp_path, mutate(copy.deepcopy(private))) == message


def test_a_file_that_is_not_json_or_lacks_a_field_is_a_sentence_not_a_traceback(tmp_path, private, capsys):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert tl.main(["--backtest", str(broken)]) == 2
    assert capsys.readouterr().err.startswith("refused: ")
    mutated = copy.deepcopy(private)
    del mutated["nights"][PRODUCTION][0]["counted"]
    assert tl.main(["--backtest", str(write(tmp_path, mutated))]) == 2
    assert capsys.readouterr().err == "refused: nights.production[0] has no counted\n"
    assert tl.main(["--backtest", str(tmp_path / "absent.json")]) == 2


# ----------------------------------------------------------------- CLI ----
def test_the_cli_writes_the_file_and_prints_the_counts(path, tmp_path, capsys):
    out = tmp_path / "public" / "nested" / "timeline.json"
    assert tl.main(["--backtest", str(path), "--output", str(out)]) == 0
    expected = tl.encode(tl.read(path))
    assert out.read_text(encoding="utf-8") == expected
    assert expected == json.dumps(tl.read(path), indent=1, sort_keys=True) + "\n"
    printed = capsys.readouterr().out
    assert printed.count("\n") == 1
    assert printed == ("timeline backtest-timeline-v1 over backtest.json: production: 3 sessions, 5 tickets, 4 settled; "
                       f"no_regime_gate: 3 sessions, 10 tickets, 5 settled; written {out}\n")
    assert tl.main(["--backtest", str(path)]) == 0
    assert capsys.readouterr().out == expected
    assert path.read_text(encoding="utf-8") == backtest._encode(build_private()), "the private file is read, never rewritten"


def test_an_output_naming_the_private_file_is_refused_and_the_file_is_untouched(path, tmp_path, capsys):
    before = path.read_bytes()
    linked = tmp_path / "linked.json"
    os.link(path, linked)
    for output in (path, path.parent / ".." / path.parent.name / path.name, linked):
        capsys.readouterr()
        assert tl.main(["--backtest", str(path), "--output", str(output)]) == 2, output
        assert capsys.readouterr().err == (f"refused: --output {output} is the private file itself; "
                                           "the timeline is never written over it\n")
        assert path.read_bytes() == before
    # the same read written anywhere else is fine
    assert tl.main(["--backtest", str(path), "--output", str(tmp_path / "elsewhere.json")]) == 0
    assert path.read_bytes() == before
