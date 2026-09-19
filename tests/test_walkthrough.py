"""The Method view's walkthrough (docs/app-method.js) prints what the code
writes. Its RULES block names every number a caption quotes for the constant
it came from, and EXAMPLE is what the modules write for its synthetic BARS:
both are re-derived here, so the page can fall behind Python only by turning
this suite red. The browser half -- that each step reveals, labels and prints
what it says -- is tools/walkthrough_cases.mjs."""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src import breadth, grader, pipeline, plan, quality, record, scans, sessions, universe

ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / "docs" / "app-method.js").read_text()
MODULES = {"universe": universe, "scans": scans, "quality": quality, "breadth": breadth, "plan": plan, "record": record}
SIGNAL = date(2026, 8, 20)   # any session: the walkthrough carries no date, the replay needs one


def block(name: str):
    """A `const NAME = {...};` or `[...]` the module declares, read as the
    JSON it is written as."""
    found = re.search(rf"const {name} = (\{{.*?\}}|\[.*?\]);\n", SOURCE, re.S)
    assert found, f"docs/app-method.js declares no {name}"
    return json.loads(found.group(1))


RULES, BANDS, BARS, EXAMPLE = block("RULES"), block("BANDS"), block("BARS"), block("EXAMPLE")
BURST = int(re.search(r"const BURST = (\d+);", SOURCE).group(1))


def frame() -> tuple[pd.DataFrame, list[str]]:
    """The synthetic bars as the pipeline's frame, dated so the signal falls
    on SIGNAL and every other bar on an exchange session."""
    earlier: list[str] = []
    day = SIGNAL
    while len(earlier) < BURST:
        day -= timedelta(days=1)
        if sessions.is_session(day):
            earlier.insert(0, str(day))
    dates = earlier + [str(SIGNAL)] + [str(d) for d in plan.next_sessions(SIGNAL, len(BARS) - BURST - 1)]
    rows = [{"Open": o, "High": h, "Low": lo, "Close": c, "Volume": v} for o, h, lo, c, v in BARS]
    return pd.DataFrame(rows, index=pd.to_datetime(dates)), dates


# ------------------------------------------------------- the numbers quoted ----
def test_every_rule_the_walkthrough_quotes_is_the_modules_own():
    assert len(RULES) >= 50, "the walkthrough quotes fewer rules than it did"
    for key, value in RULES.items():
        module, name = key.split(".", 1)
        assert module in MODULES, key
        assert hasattr(MODULES[module], name.upper()), f"{key}: src/{module}.py names no {name.upper()}"
        assert getattr(MODULES[module], name.upper()) == value, (key, value, getattr(MODULES[module], name.upper()))


def test_the_walkthrough_quotes_the_graders_bands_and_the_regimes_words():
    floors = {grade: floor for floor, grade in grader.GRADE_BANDS}
    for grade, floor in BANDS.items():
        assert floors[grade] == floor, (grade, floor, floors)
    # the words the breadth step prints for yellow are the pipeline's own rule
    assert "half size, A+ only" in SOURCE
    assert breadth.SIZE_MULTIPLIER == {"green": 1.0, "yellow": 0.5, "red": 0.0}
    assert pipeline.YELLOW_GRADES == ("A+",)
    # and the gate the signal step names is the checklist's
    assert "2 and H to pass outright" in SOURCE and quality.GRADE_GATE_LETTERS == ("2", "H")
    assert "no new longs, no plans" in SOURCE and breadth.SIZE_MULTIPLIER["red"] == 0.0


def test_the_walkthrough_quotes_no_number_it_does_not_name():
    """A bare strategy number in a caption would escape the test above. The
    captions are built from N('...'), EXAMPLE and BANDS; the digits that may
    appear as literals are the ones that are not rules: a year, 2LYNCH and
    the checklist's letter 2, the ten points the six weights sum to, the
    plan's own day2_spent_above field, and one quoted "3rd"."""
    captions = SOURCE.split("const STEPS = [", 1)[1].split("// the stop in force", 1)[0]
    literal = re.findall(r"'[^']*'", captions)
    rule_key = re.compile(r"^'(universe|scans|quality|breadth|plan|record)\.[a-z0-9_]+'$")
    allowed = re.compile(r"of 10|2LYNCH|20(09|11|14|16|18)|2015|2017|3rd|R²|\b2 (and|B|·)|day 2 already spent")
    stray = [chunk for chunk in literal if not rule_key.match(chunk) and re.search(r"\d", allowed.sub("", chunk))]
    assert not stray, stray
    # the guard can fail: the source line that once read "the 15% hazard E"
    # is what it caught, and this is that line with its number spelled again
    assert re.search(r"\d", allowed.sub("", "'the hold B; the 15% hazard E'"))


# ------------------------------------------------------- the example written ----
def test_the_example_is_what_the_code_writes_for_the_bars():
    df, dates = frame()
    upto = df.iloc[: BURST + 1]
    scan = scans.burst_4pct(upto)
    assert scan and scan["gain_pct"] == EXAMPLE["gain_pct"] and scan["volume_vs_prior"] == EXAMPLE["volume_vs_prior"]
    assert scans.dollar_breakout(upto) is None, "the example is a 4% burst, not a Dollar day"

    a = quality.assess(upto)
    assert (a.grade, a.score, a.a_plus_count, a.vetoes) == (EXAMPLE["grade"], EXAMPLE["score"], EXAMPLE["a_plus_letters"], [])
    by = {c.letter: c for c in a.checks}
    assert all(by[letter].passed for letter in quality.LETTERS + quality.EXTRA_CHECKS), {k: c.passed for k, c in by.items()}
    assert (a.leg["length"], a.leg["gain_pct"], a.leg["er"], a.leg["r2"]) == (
        EXAMPLE["leg_sessions"], EXAMPLE["leg_gain_pct"], EXAMPLE["er"], EXAMPLE["r2"])
    assert by["Y"].value["breakouts_in_move"] == EXAMPLE["breakouts_in_move"]
    assert (a.base["start"], a.base["end"], a.base["length"], a.base["high"], a.base["low"]) == (
        EXAMPLE["base_start"], EXAMPLE["base_end"], EXAMPLE["base_sessions"], EXAMPLE["base_high"], EXAMPLE["base_low"])
    c = by["C"].value
    assert (c["breakdowns"], c["bursts_in_base"], c["giveback"], c["tightness"], c["base_volume_vs_leg"]) == (
        EXAMPLE["breakdowns"], EXAMPLE["bursts_in_base"], EXAMPLE["giveback"], EXAMPLE["tightness"], EXAMPLE["base_volume_vs_leg"])
    two, n = by["2"].value, by["N"].value
    assert (two["up_run"], two["up_closes"], n["prior_day_pct"], n["prior_range_pct"]) == (
        EXAMPLE["up_run"], EXAMPLE["up_closes"], EXAMPLE["prior_day_pct"], EXAMPLE["prior_range_pct"])
    assert (by["H"].value["close_pos"], by["RE"].value["vs_prior_5"], by["VOL"].value["volume_rank_60"]) == (
        EXAMPLE["close_pos"], EXAMPLE["vs_prior_5"], EXAMPLE["volume_rank_60"])

    bar = BARS[BURST]
    p = plan.burst_plan(ticker="XMPL", close=bar[3], low=bar[2], high=bar[1], open_=bar[0], prev_close=BARS[BURST - 1][3],
                        gain_pct=scan["gain_pct"], account=plan.Account.from_env({}), extension_pct=pipeline.extension_pct(upto))
    assert p["action"] == "buy_at_open" and p["eligible"] and p["flags"] == ["limit_narrowed", "risk_halved"]
    for key, field in (("trigger", "entry_ref"), ("limit", "limit"), ("limit_basis", "limit_basis"), ("day2_spent_above", "day2_spent_above"),
                       ("skip_below", "entry_low"), ("stop", "stop"), ("stop_basis", "stop_basis"), ("stop_pct", "stop_pct"),
                       ("shares", "shares"), ("position_usd", "position_usd"), ("risk_usd", "risk_usd")):
        assert p[field] == EXAMPLE[key], (key, p[field], EXAMPLE[key])
    assert p["sizing"]["budget_usd"] == EXAMPLE["budget_usd"]
    assert p["limit"] == p["entry_high"] < p["day2_spent_above"]

    pick = pipeline.pick_of(p, "burst", a.grade, a.score)
    pick["date"] = str(SIGNAL)
    later = [{"date": dates[BURST + 1 + i], "o": b[0], "h": b[1], "l": b[2], "c": b[3]} for i, b in enumerate(BARS[BURST + 1:])]
    row = record.replay(pick, later)
    assert (row["status"], row["day"], row["fill"]) == ("exit", EXAMPLE["settled_day"], f"filled at the open, ${EXAMPLE['fill']:.2f}")
    events = [(e["day"], e["event"], e["price"], e.get("shares")) for e in row["events"]]
    assert events == [
        (1, "sell_half", EXAMPLE["sell_half_price"], EXAMPLE["sell_half_shares"]),
        (1, "stop_raised", EXAMPLE["stop_after_day1"], None),
        (3, "stop_trailed", EXAMPLE["stop_day3"], None),
        (4, "stop_trailed", EXAMPLE["stop_day4"], None),
        (5, "stop_trailed", EXAMPLE["stop_day5"], None),
        (5, "day5_exit", EXAMPLE["exit_price"], EXAMPLE["exit_shares"]),
    ], events
    assert BARS[BURST + 1][1] == EXAMPLE["day1_high"]
    assert row["result_pct"] == EXAMPLE["result_pct"]
    assert record.r_multiple(row, pick["stop"]) == EXAMPLE["r"]
    assert round(EXAMPLE["fill"] - EXAMPLE["stop"], 2) == EXAMPLE["one_r"]
    # the day-by-day statuses the captions narrate: half sold on day 1, then held into strength to day 5
    walked = [record.replay(pick, later[:n])["status"] for n in range(1, 6)]
    assert walked == ["sell_half", "sell_into_strength", "sell_into_strength", "sell_into_strength", "exit"], walked


def test_the_example_would_not_survive_a_bar_out_of_place():
    """The test above can fail: a low a cent under the stop on the fill day
    makes the fill uncertain, and the walkthrough's R would no longer be
    the replay's."""
    df, dates = frame()
    upto = df.iloc[: BURST + 1]
    bar = BARS[BURST]
    p = plan.burst_plan(ticker="XMPL", close=bar[3], low=bar[2], high=bar[1], open_=bar[0], prev_close=BARS[BURST - 1][3],
                        gain_pct=scans.burst_4pct(upto)["gain_pct"], account=plan.Account.from_env({}))
    pick = pipeline.pick_of(p, "burst", "A+", 10.0)
    pick["date"] = str(SIGNAL)
    later = [{"date": dates[BURST + 1 + i], "o": b[0], "h": b[1], "l": b[2], "c": b[3]} for i, b in enumerate(BARS[BURST + 1:])]
    later[0] = {**later[0], "o": EXAMPLE["trigger"] - 0.01, "l": EXAMPLE["stop"] - 0.01}
    row = record.replay(pick, later)
    assert row["status"] == record.UNCERTAIN and record.r_multiple(row, pick["stop"]) is None


# ------------------------------------------------------------- the page ----
def test_the_page_loads_the_walkthrough_before_the_app_and_the_docs_name_it():
    page = (ROOT / "docs" / "index.html").read_text()
    assert page.index('src="app-method.js"') < page.index('src="app.js"'), "the module must load before app.js mounts it"
    assert 'id="walkthrough-mount"' in page and 'id="walkthrough"' in page
    app = (ROOT / "docs" / "app.js").read_text()
    assert "SCStock.walkthrough.mount($('walkthrough-mount')" in app
    assert "parts[1] === 'walkthrough'" in app, "the #/method/walkthrough route"
    readme = re.sub(r"\s+", " ", (ROOT / "README.md").read_text())   # a phrase may wrap
    assert "app-method.js" in readme and "one burst at a time" in readme
    for harness in ("tools/continuity_check.mjs", "tools/evidence_focus_cases.mjs"):
        assert "docs/app-method.js" in (ROOT / harness).read_text(), f"{harness} loads the page's modules by name"
    assert "checkWalkthrough" in (ROOT / "tools" / "page_smoke.mjs").read_text()


def test_the_walkthrough_reads_nothing_of_the_record():
    """The walkthrough explains; the run decides. Nothing in the module
    fetches, reads SCStock.data or model, or names a ticker the record could
    carry."""
    body = SOURCE.split("(function (w) {", 1)[1]
    for forbidden in ("fetch(", "SCStock.data", "S.data", "SCStock.model", "S.model", "localStorage", "picks.json", "data.json"):
        assert forbidden not in body, forbidden
