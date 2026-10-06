"""tools.backtest_timeline: the owner's private ``backtest.json`` reduced to
one price-free, ticker-free row per night per gate. The private file here
is built by hand in the shape ``historical_backtest.run()`` writes -- two
gates, three nights, walked rows with a settled win, a loss, a breakeven,
an uncertain fill, a plan never filled and one still pending, tickers and
prices wherever the real file carries them -- and written through the
backtest's own encoder, so the reader is exercised over the bytes it will
meet. Every held number is computed by hand beside its assertion, and
every refusal and every held number is shown to fail on a mutated copy."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from src import plan, record
from tools import backtest_timeline as tl
from tools import historical_backtest as backtest

S1, S2, S3 = "2026-03-02", "2026-03-03", "2026-03-04"
#: the names the private file carries; none may reach the output
TICKERS = ("QQZ", "WXV", "KLM", "PRT", "ZZT", "RDN", "LST", "NMO")
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
                          candidate("ZZT", "A", True, buy)]),
        night(S2, *MEASURED[S2], gate=True, eligible=0, trades=[], cut={"no_new_longs": 1}, slots_held=2,
              candidates=[candidate("RDN", "A", False, None)]),
        night(S3, *MEASURED[S3], gate=True, eligible=3, trades=["QQZ", "KLM", "PRT"], cut={}, slots_held=1,
              candidates=[candidate(t, "A+", True, buy) for t in ("QQZ", "KLM", "PRT", "LST")]),
    ]
    ungated_nights = [
        night(S1, *MEASURED[S1], gate=False, eligible=3, trades=["QQZ", "WXV", "ZZT"], cut={}, slots_held=0,
              candidates=production_nights[0]["candidates"]),
        night(S2, *MEASURED[S2], gate=False, eligible=1, trades=["RDN"], cut={}, slots_held=3,
              candidates=[candidate("RDN", "A", True, buy)]),
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
                       row("RDN", S2, "A", "red", "uncertain", status="uncertain", uncertainty="trigger_timing")]
                    + copy.deepcopy(production_rows[2:])
                    + [row("LST", S3, "A+", "yellow", "pending"),
                       row("NMO", S3, "A", "yellow", "settled", r=0.26, status="exit")])
    nights = {PRODUCTION: production_nights, UNGATED: ungated_nights}
    rows = {PRODUCTION: production_rows, UNGATED: ungated_rows}
    outcomes = {}
    for gate in backtest.GATES:
        picks = [pick(r["ticker"], r["picked"], r["grade"], r["regime"]) for r in rows[gate]]
        outcomes[gate] = {"tickets_issued": len(picks), "summary": record.summarize_scorecard(rows[gate]),
                          "rows": rows[gate],
                          "by_grade": backtest._partition(rows[gate], lambda r: r.get("grade")),
                          "by_regime": backtest._partition(rows[gate], lambda r: r.get("regime")),
                          "by_month": backtest._partition(rows[gate], lambda r: r["picked"][:7]),
                          "picks": picks}
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


def write(tmp_path, private: dict):
    """The private file as the backtest writes it, through its own encoder."""
    path = tmp_path / "private" / "backtest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(backtest._encode(private), encoding="utf-8")
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


# ------------------------------------------------------------- the rows ----
def test_every_night_row_copies_the_regime_and_the_counts_and_counts_its_tickets(timeline, private):
    for gate in backtest.GATES:
        got, nights = timeline["gates"][gate], private["nights"][gate]
        assert [r["session"] for r in got] == [n["session"] for n in nights] == [S1, S2, S3]
        for out, src in zip(got, nights):
            for key in tl.REGIME_FIELDS:
                assert out[key] == src["regime"][key], (gate, out["session"], key)
            for key in tl.COPIED:
                assert out[key] == src[key], (gate, out["session"], key)
            assert out["tickets"] == len(src["trades"])
            assert "trades" not in out and "candidates" not in out and out["reason"] is None
    assert [r["tickets"] for r in timeline["gates"][PRODUCTION]] == [2, 0, 3]
    assert [r["tickets"] for r in timeline["gates"][UNGATED]] == [3, 1, 5]
    assert rows_of(timeline, PRODUCTION)[S2]["verdict"] == "red" and rows_of(timeline, PRODUCTION)[S2]["ratio_10d"] == 0.86


@pytest.mark.parametrize("key", tl.REGIME_FIELDS + tl.COPIED)
def test_each_copied_field_is_read_off_the_night_not_assumed(private, tmp_path, key):
    """Prove the copy is live: move the night's value and the row follows."""
    mutated = copy.deepcopy(private)
    in_regime = key in tl.REGIME_FIELDS
    for gate in backtest.GATES:
        holder = mutated["nights"][gate][0]["regime"] if in_regime else mutated["nights"][gate][0]
        before = holder[key]
        holder[key] = {"Z": 1} if isinstance(before, dict) else "moved" if isinstance(before, str) else before + 1
    moved = mutated["nights"][PRODUCTION][0]["regime"] if in_regime else mutated["nights"][PRODUCTION][0]
    original = private["nights"][PRODUCTION][0]["regime"] if in_regime else private["nights"][PRODUCTION][0]
    out = rows_of(tl.read(write(tmp_path, mutated)), PRODUCTION)[S1]
    assert out[key] == moved[key] != original[key]


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
    # the ungated third night settles three: KLM 0.0, PRT -1.0, NMO +0.26.
    #   sum = 0.0 + (-1.0) + 0.26 = -0.74; mean = -0.74 / 3 = -0.24666... -> -0.247 at three places
    #   (-0.25 at two, which is why the mean keeps one place more than the sum); median of three = 0.0
    last = rows_of(timeline, UNGATED)[S3]
    assert last["r"] == [-1.0, 0.0, 0.26]
    assert last["settled"] == {"n": 3, "wins": 1, "losses": 1, "breakeven": 1,
                               "sum_r": -0.74, "mean_r": -0.247, "median_r": 0.0}


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
    red = rows_of(timeline, UNGATED)[S2]
    assert red["tickets"] == 1 and red["buckets"]["uncertain"] == 1 and red["uncertainty"] == {"trigger_timing": 1}
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
    out = rows_of(tl.read(write(tmp_path, mutated)), UNGATED)[S2]
    assert out["verdict"] is None and out["ratio_10d"] is None and out["universe"] is None
    assert out["reason"] == "no name printed on the session" and out["tickets"] == 0 and out["settled"]["n"] == 0


# ------------------------------------------------------------ the source ----
def test_the_source_names_the_file_by_basename_and_digest_and_copies_the_runs_context(timeline, path, private):
    text = tl.encode(timeline)
    assert timeline["version"] == tl.VERSION
    assert timeline["source"]["path"] == "backtest.json" and str(path.parent) not in text
    assert timeline["source"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert timeline["source"]["backtest_version"] == backtest.VERSION
    assert timeline["source"]["rules_version"] == "abc123def456"
    for key in tl.SOURCE_FIELDS:
        assert timeline["source"][key] == private[key], key
    assert timeline["source"]["lookback"]["equivalence"] == {"required": True, "compared": 28, "differences": 0,
                                                             "status": "PASS"}
    assert timeline["reader"] == backtest.READER and timeline["limitations"] == list(backtest.LIMITATIONS)


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


# ------------------------------------------------------------- privacy ----
def test_the_serialised_timeline_carries_no_private_key_no_ticker_and_no_price(timeline, private):
    text = tl.encode(timeline)
    for key in tl.PRIVATE_KEYS:
        assert f'"{key}"' not in text, key
    for ticker in TICKERS:
        assert ticker in json.dumps(private) and ticker not in text, ticker
    for price in PRICES:
        assert price in json.dumps(private) and price not in text, price
    assert "$" not in text
    assert tl.private_leaks(timeline, tl.tickers_of(private)) == []
    assert tl.tickers_of(private) == frozenset(TICKERS)


def test_the_key_sweep_is_what_keeps_a_price_out(private, tmp_path, monkeypatch):
    """Inject the candidates block, which carries the plan's prices, into the
    row: the sweep refuses it by key; with the key list emptied the same
    build passes and the prices are in the text."""
    nameless = copy.deepcopy(private)
    for gate in backtest.GATES:
        for n in nameless["nights"][gate]:
            for c in n["candidates"]:
                del c["ticker"]
    p = write(tmp_path, nameless)
    monkeypatch.setattr(tl, "COPIED", tl.COPIED + ("candidates",))
    with pytest.raises(tl.TimelineError) as refused:
        tl.read(p)
    message = str(refused.value)
    assert "candidates (private key)" in message and "plan.limit (private key)" in message \
        and "plan.stop (private key)" in message and "plan.entry_ref (private key)" in message
    monkeypatch.setattr(tl, "PRIVATE_KEYS", frozenset())
    text = tl.encode(tl.read(p))
    assert '"candidates"' in text and "124.21" in text and "126.47" in text and "121.42" in text and "505.88" in text


def test_the_value_sweep_catches_a_ticker_under_a_key_the_list_does_not_name(private, tmp_path, monkeypatch):
    p = write(tmp_path, private)
    monkeypatch.setattr(tl, "COPIED", tl.COPIED + ("trades",))
    monkeypatch.setattr(tl, "PRIVATE_KEYS", frozenset())
    with pytest.raises(tl.TimelineError, match=r"trades\[0\] \(a ticker\)"):
        tl.read(p)
    # and the intact candidates block is refused for its ticker values even with the key list emptied
    monkeypatch.setattr(tl, "COPIED", tl.COPIED[:-1] + ("candidates",))
    with pytest.raises(tl.TimelineError, match=r"candidates\[0\]\.ticker \(a ticker\)"):
        tl.read(p)


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


def test_a_file_that_is_not_json_or_lacks_a_field_is_a_sentence_not_a_traceback(tmp_path, private, capsys):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert tl.main(["--backtest", str(broken)]) == 2
    assert capsys.readouterr().err.startswith("refused: ")
    mutated = copy.deepcopy(private)
    del mutated["nights"][PRODUCTION][0]["counted"]
    assert tl.main(["--backtest", str(write(tmp_path, mutated))]) == 2
    assert capsys.readouterr().err == "refused: 'counted'\n"
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
                       f"no_regime_gate: 3 sessions, 9 tickets, 5 settled; written {out}\n")
    assert tl.main(["--backtest", str(path)]) == 0
    assert capsys.readouterr().out == expected
    assert path.read_text(encoding="utf-8") == backtest._encode(build_private()), "the private file is read, never rewritten"
