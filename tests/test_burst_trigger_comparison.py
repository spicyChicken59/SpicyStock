"""The dated reading of the burst trigger rule, held to its file and its tool.

``tools/burst_trigger_comparison.py`` is the frozen signal-outcome study run
twice, once per ``plan.BURST_TRIGGER_RULES``; these tests hold the dated
report's figures to the committed ``comparison.json`` and the tool's two
pieces of its own (the ticket under a named rule, the first day's place
against a ticket's lines) to the code they stand on.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from src import plan
from tools import burst_trigger_comparison as cmp
from tools import signal_outcomes as so

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "docs" / "input-truthfulness" / "2026-11-19-burst-trigger-comparison" / "comparison.json"
REPORT = ROOT / "docs" / "input-truthfulness" / "2026-11-19-burst-trigger-comparison.md"
DATA = json.loads(FILE.read_text())
TEXT = re.sub(r"\s+", " ", REPORT.read_text())


def n(v: int) -> str:
    return f"{v:,}"


def test_the_file_is_the_tools_encoding_and_names_its_population():
    assert FILE.read_text() == cmp.encoded(DATA)
    assert DATA["version"] == cmp.VERSION and set(DATA["rules"]) == set(plan.BURST_TRIGGER_RULES)
    assert DATA["base_spec"] == cmp.BASE_SPEC.relative_to(ROOT).as_posix()
    assert DATA["base_spec_sha256"] == hashlib.sha256(cmp.BASE_SPEC.read_bytes()).hexdigest()
    assert DATA["cushion"] == {"cents": plan.TRIGGER_CENTS, "fraction": plan.TRIGGER_FRACTION}
    assert re.fullmatch(r"[0-9a-f]{40}", DATA["ref"])
    assert f"--ref {DATA['ref'][:8]}" in TEXT
    assert (f"{DATA['publications']} publications, the first of each of {DATA['nights']} sessions ticketed "
            f"(11 September to 18 November 2026)") in TEXT
    assert (DATA["first_session"], DATA["newest_session"]) == ("2026-09-11", "2026-11-18")
    assert f"The 7 November extension's {len(json.loads(cmp.BASE_SPEC.read_text())['publications'])} publications" in TEXT


def test_every_figure_the_report_prints_is_the_files():
    rows = []
    for rule in ("close", "close_plus_cushion"):
        r = DATA["rules"][rule]
        o = r["first_day_open"]
        with_day = sum(v for k, v in o.items() if k != "no_first_day")
        at_over = o["at_buy_stop"] + o["in_band"] + o["over_limit_to_day2"] + o["over_day2"]
        a = r["admitted"]
        rows.append({"tickets": sum(o.values()), "withheld": r["withheld_by_the_stop_rule"], "under": o["under_buy_stop"],
                     "at_over": f"{n(at_over)} of {n(with_day)} ({100 * at_over / with_day:.1f}%)",
                     "settled": a["settled"]["n"], "mean": a["settled"]["mean_r"], "median": a["settled"]["median_r"],
                     "ci": a["night_bootstrap"]["ci95"], "uncertain": a["buckets"]["uncertain"], "not_filled": a["buckets"]["not_filled"]})
    old, new = rows
    sign = lambda v: f"{v:g}".replace("-", "−")
    for label, key in (("tickets written (every stratum)", "tickets"), ("withheld by the 4% stop rule", "withheld"),
                       ("first day opened under the buy stop", "under"), ("admitted (A+/A, no veto): settled", "settled"),
                       ("admitted: uncertain on daily bars", "uncertain"), ("admitted: not filled", "not_filled")):
        assert f"| {label} | {n(old[key])} | {n(new[key])} |" in TEXT, label
    assert f"| first day opened at or over the buy stop | {old['at_over']} | {new['at_over']} |" in TEXT
    assert f"| admitted: mean R / median R | {sign(old['mean'])} / {sign(old['median'])} | {sign(new['mean'])} / {sign(new['median'])} |" in TEXT
    ci = lambda c: f"[{sign(c[0])}, {sign(c[1])}]"
    assert f"| {ci(old['ci'])} | {ci(new['ci'])} |" in TEXT
    assert f"so {new['withheld'] - old['withheld']} more setups have no limit above their buy stop" in TEXT
    # the reading's own claims: the cushion moves opens under the buy stop, and no interval clears zero
    assert new["under"] > old["under"] and new["settled"] < old["settled"]
    assert all(c[0] < 0 < c[1] for c in (old["ci"], new["ci"]))
    assert "includes zero under both rules" in TEXT


def test_the_ticket_under_close_is_the_studys_own():
    row = {"ticker": "XMPL", "close": 100.0, "low": 97.0, "high": 100.5, "open": 97.5, "prev_close": 95.0,
           "gain_pct": 5.26, "scan": "4pct", "extension_pct": None}
    account = plan.Account(equity=30_000, risk_pct=0.5, max_position_pct=25, max_open_positions=4)
    assert cmp.ticket_under(plan.LEGACY_BURST_TRIGGER_RULE)(row, account) == so.ticket(row, account)
    new, bucket, _ = cmp.ticket_under(plan.BURST_TRIGGER_RULE)(row, account)
    assert bucket is None and new["entry_ref"] == plan.burst_trigger(100.0, plan.BURST_TRIGGER_RULE)


@pytest.mark.parametrize("open_, where", [(97.0, "at_or_under_stop"), (97.5, "under_skip_line"), (99.0, "under_buy_stop"),
                                          (100.10, "at_buy_stop"), (100.2, "in_band"), (103.0, "over_limit_to_day2"),
                                          (105.0, "over_day2")])
def test_the_first_day_is_placed_against_the_tickets_own_lines(open_, where):
    ticket = {"stop": 97.0, "entry_low": 98.0, "entry_ref": 100.10, "limit": 101.0, "day2_spent_above": 104.0}
    assert cmp.open_position(ticket, {"o": open_}) == where
    assert cmp.open_position(ticket, None) == "no_first_day"
    assert where in cmp.POSITIONS
