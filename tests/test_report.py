"""src.report: the data.json contract, the cover and summary sentences, the
problem words, and the email digest through the Resend double.

Every test is offline. The delivery tests are the old emailer's, ported with
the transport: the test-mode respelling happens once, on one refusal, and
the log names counts and domains and never an address.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import math
from html.parser import HTMLParser
from pathlib import Path

import pytest

from src import report
from src.report import (
    GRADES, PROBLEM_KINDS, PROBLEM_SENTENCES, RUN_STATUSES, build, closed_market_digest,
    contract_paths, cover, deliver, digest_html, digest_subject, problem, redact_addresses,
    send_digest, send_failure_notice, summary, write,
)

# --- builders -------------------------------------------------------------------

SESSION = "2026-09-10"
ORDER_LINE = "Buy 69 XYZ stop-limit 12.34/12.71 day; OTO sell stop 11.62 GTC"


def _plan(**over) -> dict:
    plan = {"entry_low": 12.34, "entry_high": 12.71, "stop": 11.62, "shares": 69, "position_usd": 852,
            "entry_window_minutes": 30, "target_low": 13.33, "target_high": 14.81, "horizon_sessions": 5,
            "order_line": ORDER_LINE}
    plan.update(over)
    return plan


def _burst(ticker: str = "XYZ", **over) -> dict:
    burst = {
        "ticker": ticker, "name": f"{ticker} Corp", "scan": "4pct", "close": 12.34, "gain_pct": 6.1,
        "volume": 1_234_567, "volume_vs_prior": 1.9, "dollar_volume": 15_234_567.0,
        "quality": {"grade_mechanical": "A+", "score": 8.6, "passes": 8, "of": 9,
                    "base_sessions": 14, "base_depth_pct": 6.2, "checks": [], "vetoes": []},
        "claude": {"agree": True, "grade": "A+", "reason": "Tight base, clean expansion", "key_risk": "a gap",
                   "entry_note": "", "source": "claude", "chart_seen": True, "error": None},
        "grade": "A+", "score": 8.6, "rank": 1, "plan": _plan(), "chart": f"charts/{ticker}.png",
        "series": [{"date": SESSION, "o": 11.7, "h": 12.4, "l": 11.6, "c": 12.34, "v": 1_234_567}],
    }
    burst.update(over)
    return burst


def _miss(ticker: str = "ABC") -> dict:
    return _burst(ticker, gain_pct=4.2, grade="B", score=7.8, claude=None, plan=None, chart=None, series=None,
                  quality={"grade_mechanical": "B", "score": 7.8, "passes": 6, "of": 9,
                           "base_sessions": 23, "base_depth_pct": 11.0, "checks": [], "vetoes": ["up_days"]})


def _breadth(verdict: str = "green", **over) -> dict:
    regime = {"green": (1.0, ["10-day ratio 2.9 >= 2"]),
              "yellow": (0.5, ["10-day ratio 1.6 < 2"]),
              "red": (0.0, ["5-day ratio 0.4 < 0.5 with 412 down vs 96 up today: a fast selling phase"])}[verdict]
    breadth = {"date": SESSION, "up4": 412, "down4": 96, "ratio_5d": 2.4, "ratio_10d": 2.9, "history": [],
               "regime": {"verdict": verdict, "size_multiplier": regime[0], "reasons": regime[1]}}
    breadth.update(over)
    return breadth


def _run(**over) -> dict:
    run = {"session": SESSION, "session_state": "open", "expected_session": SESSION, "status": "ok",
           "problems": [], "dry_run": False, "model": "claude-sonnet-4-6", "feed": "sip",
           "universe": {"label": "nasdaq directory", "size": 6231}, "bursts": 2}
    run.update(over)
    return run


def _night(**over) -> dict:
    """The keyword arguments build() takes, for one ordinary green night."""
    night = {
        "run": _run(), "account": {"equity": 10000, "risk_pct": 0.5, "max_position_pct": 25,
                                   "max_open_positions": 4, "notes": []},
        "rules": {"scans": {"BURST_RATIO": 1.04}, "plan": {"RISK_PCT": 0.5}},
        "breadth": _breadth(), "bursts": [_burst(), _miss()], "trades": ["XYZ"], "beyond_cap": [],
        "cash_budget": {"committed_usd": 852, "slots_used": 1, "slots_max": 4, "cut": []},
        "watchlist": {"top": [{"ticker": "WCH", "setups": ["TI65"], "trigger": 20.05, "stop": 18.9, "shares": 40,
                               "plan": {"order_line": "Buy 40 WCH stop 20.05 limit 20.30; OTO sell stop 18.90"}}],
                      "also_quiet": [], "counts": {"top": 1, "also_quiet": 0}},
        "open_plans": [{"ticker": "OLD", "picked": "2026-09-08", "day": 2, "of": 5, "status": "sell_half",
                        "instruction": "Sell half at the open; raise the stop to 9.40."}],
        "scorecard": None,
        "nights": [{"session": SESSION, "status": "ok", "published_at": "2026-09-10T22:31:00Z"}],
        "generated": dt.datetime(2026, 9, 10, 22, 31, tzinfo=dt.timezone.utc),
    }
    night.update(over)
    return night


class _Text(HTMLParser):
    """What a mail client shows: the text nodes, with the tags parsed away."""

    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def _rendered(markup: str) -> str:
    parser = _Text()
    parser.feed(markup)
    return " ".join(parser.text)


# --- the cover ---------------------------------------------------------------------

@pytest.mark.parametrize("label, run, breadth, trades, expected", [
    ("green with trades", _run(), _breadth("green"), ["XYZ", "ABC"], "Trade tomorrow. 2 A-quality bursts."),
    ("yellow with trades", _run(), _breadth("yellow"), ["XYZ"], "Trade small. 1 A+ burst."),
    ("red", _run(), _breadth("red"), [], "Stand aside."),
    ("open, nothing qualifies", _run(), _breadth("green"), [], "Nothing qualifies. Keep cash."),
    ("closed", _run(session="2026-09-09", session_state="closed", status="closed"), _breadth("green"), [],
     "Market closed. Plans unchanged."),
    ("failed", _run(status="failed"), None, [], "No verdict for 2026-09-10."),
])
def test_the_cover_h1_takes_each_of_its_six_forms(label, run, breadth, trades, expected):
    assert cover(run, breadth, trades, [_burst(), _miss()], None)["h1"] == expected, label


def test_the_singular_form_is_used_for_one_trade_and_the_plural_for_more():
    one = cover(_run(), _breadth("green"), ["XYZ"], [_burst()], None)["h1"]
    two = cover(_run(), _breadth("yellow"), ["XYZ", "ABC"], [_burst(), _burst("ABC")], None)["h1"]
    assert one == "Trade tomorrow. 1 A-quality burst."
    assert two == "Trade small. 2 A+ bursts."


def test_the_dek_carries_the_breadth_numbers_and_the_size_rule():
    dek = cover(_run(), _breadth("green"), ["XYZ"], [_burst()], None)["dek"]
    assert dek == "Breadth is green: 412 up 4% vs 96 down, 10-day ratio 2.9. Full size."


@pytest.mark.parametrize("verdict, size, reason", [
    ("yellow", "Half size.", "10-day ratio 1.6 < 2."),
    ("red", "No new positions.", "5-day ratio 0.4 < 0.5 with 412 down vs 96 up today: a fast selling phase."),
])
def test_the_regimes_reasons_follow_the_dek_when_the_verb_changed(verdict, size, reason):
    dek = cover(_run(), _breadth(verdict), ["XYZ"], [_burst()], None)["dek"]
    assert dek == f"Breadth is {verdict}: 412 up 4% vs 96 down, 10-day ratio 2.9. {size} {reason}"


def test_the_size_rule_is_read_off_the_multiplier_and_not_off_the_verdict():
    breadth = _breadth("green")
    breadth["regime"]["size_multiplier"] = 0.5
    assert "Half size." in cover(_run(), breadth, ["XYZ"], [_burst()], None)["dek"]


def test_the_no_trade_dek_counts_the_bursts_and_points_at_the_closest_miss():
    bursts = [_burst(grade="B", plan=None), _miss()]
    with_miss = cover(_run(), _breadth("green"), [], bursts, {"ticker": "ABC"})["dek"]
    without = cover(_run(), _breadth("green"), [], [], None)["dek"]
    assert with_miss == "2 bursts found, none A-quality. The closest miss is below."
    assert without == "No bursts found."


def test_the_no_trade_dek_says_when_a_setup_qualified_and_its_ticket_did_not():
    """A burst that carries a plan qualified; without a ticket it is withheld
    or cut, and the dek must not call it 'none A-quality'."""
    withheld = _burst(plan=_plan(action="refused", eligible=False, order_line=None))
    dek = cover(_run(), _breadth("green"), [], [withheld, _miss()], None)["dek"]
    assert dek == ("2 bursts found, 1 with a qualifying setup and no ticket (withheld by the stop rule at the "
                   "limit, or cut); each card says why.")
    assert cover(_run(), _breadth("green"), [], [withheld], None)["dek"].startswith("1 burst found, 1 with")


@pytest.mark.parametrize("trades, label, target", [
    (["XYZ"], "Tomorrow's orders", "#orders"),
    ([], "Open model plans", "#hold"),
])
def test_the_primary_action_points_at_the_orders_when_there_are_any(trades, label, target):
    result = cover(_run(), _breadth("green"), trades, [_burst()], None)
    assert (result["action_label"], result["action_target"]) == (label, target)


def test_a_red_regime_points_at_what_you_hold_whatever_the_list_says():
    result = cover(_run(), _breadth("red"), ["XYZ"], [_burst()], None)
    assert result["h1"] == "Stand aside." and result["action_target"] == "#hold"


def test_the_failed_cover_carries_the_first_problems_fixed_sentence():
    run = _run(status="failed", problems=[problem("bars", "coverage_thin", "budget spent")])
    assert PROBLEM_SENTENCES["coverage_thin"] in cover(run, None, [], [], None)["dek"]


def test_every_cover_verb_is_one_the_vocabulary_names():
    cases = [(_run(), _breadth("green"), ["XYZ"]), (_run(), _breadth("yellow"), ["XYZ"]),
             (_run(), _breadth("red"), []), (_run(), _breadth("green"), []),
             (_run(session_state="closed", status="closed"), _breadth("green"), []),
             (_run(status="failed"), None, [])]
    verbs = [cover(run, breadth, trades, [_burst()], None)["verb"] for run, breadth, trades in cases]
    assert set(verbs) == set(report.VERBS) and len(set(verbs)) == 6


# --- the summary sentence ---------------------------------------------------------------

def test_the_summary_is_one_sentence_from_the_published_numbers():
    assert summary(_burst()) == (
        "XYZ: +6.1% on 1.9× volume out of a 14-session base 6.2% deep. "
        "Buy 12.34–12.71 tomorrow in the first 30 minutes, stop 11.62, aim 13.33–14.81 by day 5. "
        "A+ 8.6, 8 of 9 criteria."
    )


def test_the_summary_reads_the_shapes_the_plan_and_the_checklist_publish():
    """src.plan publishes entry_window as words and targets as a block, and
    src.quality publishes the base as {start, end, length, high, low}: the
    sentence reads those and not a shape of this module's own invention."""
    burst = _burst()
    burst["quality"] = {"grade": "A+", "score": 8.6, "passes": 8, "of": 9, "checks": [], "vetoes": [],
                        "base": {"start": 40, "end": 53, "length": 14, "high": 12.90, "low": 12.10}}
    burst["plan"] = {"entry_low": 12.34, "entry_high": 12.71, "stop": 11.62, "entry_window": "first 30 minutes",
                     "targets": {"low": 13.33, "high": 14.81, "low_pct": 8.0, "high_pct": 20.0},
                     "final_exit_day": 5, "order_line": ORDER_LINE}
    assert summary(burst) == (
        "XYZ: +6.1% on 1.9× volume out of a 14-session base 6.2% deep. "
        "Buy 12.34–12.71 tomorrow in the first 30 minutes, stop 11.62, aim 13.33–14.81 by day 5. "
        "A+ 8.6, 8 of 9 criteria."
    )
    del burst["plan"]["final_exit_day"]
    assert "aim 13.33–14.81." in summary(burst), "no published horizon, no day clause"


def test_a_burst_with_no_plan_loses_the_plan_clause_and_nothing_else():
    assert summary(_burst(plan=None)) == (
        "XYZ: +6.1% on 1.9× volume out of a 14-session base 6.2% deep. A+ 8.6, 8 of 9 criteria."
    )


def test_a_burst_the_model_never_read_is_summarised_off_the_checklists_grade():
    burst = _burst(claude=None, grade="A", score=7.9)
    burst["quality"]["grade_mechanical"] = "A"
    burst["quality"]["score"] = 7.9
    assert summary(burst).endswith("A 7.9, 8 of 9 criteria.")


@pytest.mark.parametrize("field", ["gain_pct", "volume_vs_prior", "quality", "grade", "score", "ticker"])
def test_a_missing_field_drops_its_clause_and_never_prints_none(field):
    burst = _burst()
    burst[field] = None
    sentence = summary(burst)
    assert "None" not in sentence and "nan" not in sentence.lower() and sentence.endswith(".")


def test_a_plan_with_only_a_stop_still_reads_as_a_sentence():
    burst = _burst(plan={"stop": 11.62})
    assert "Stop 11.62." in summary(burst)


# --- the problem words ----------------------------------------------------------------------

def test_every_problem_kind_has_exactly_one_fixed_sentence():
    assert set(PROBLEM_SENTENCES) == set(PROBLEM_KINDS) and len(PROBLEM_KINDS) == 7
    assert all(s.endswith(".") for s in PROBLEM_SENTENCES.values())


def test_an_unknown_problem_kind_is_refused():
    with pytest.raises(ValueError, match="unknown problem kind"):
        problem("email", "smtp_down", "x")


def test_a_problem_names_its_stage():
    with pytest.raises(ValueError):
        problem("", "email_failed", "x")


def test_a_problem_message_is_held_to_two_hundred_characters():
    made = problem("bars", "coverage_thin", "x" * 500)
    assert len(made["message"]) == report.MESSAGE_MAX_CHARS == 200
    assert made["message"].endswith("…")


def test_a_problem_message_loses_its_tags_and_keeps_its_words():
    made = problem("claude", "claude_unavailable", "<html><b>502 Bad Gateway</b><br>cloudflare</html>")
    assert made["message"] == "502 Bad Gateway cloudflare"
    assert made == {"stage": "claude", "kind": "claude_unavailable", "message": "502 Bad Gateway cloudflare"}


def test_a_problem_message_masks_an_address_to_its_domain():
    made = problem("email", "email_failed",
                   "You can only send testing emails to your own email address (owner@example.invalid).")
    assert "owner@" not in made["message"]
    assert "(…@example.invalid)" in made["message"]


@pytest.mark.parametrize("text, expected", [
    ("You can only send testing emails to your own email address (owner@example.invalid). Verify",
     "You can only send testing emails to your own email address (…@example.invalid). Verify"),
    ("first.last+tag@mail.example.co.uk and Second_One@Example.ORG refused",
     "…@mail.example.co.uk and …@Example.ORG refused"),
    ("no address here, only 4% and an @ sign alone", "no address here, only 4% and an @ sign alone"),
])
def test_redaction_keeps_the_domain_and_drops_the_local_part(text, expected):
    assert redact_addresses(text) == expected


# --- build() and the contract ----------------------------------------------------------------

def test_a_full_night_builds_with_the_schema_and_the_app_block():
    data = build(**_night())
    assert data["schema_version"] == 2
    assert data["app"]["name"] == "SpicyStock" and data["app"]["version"] == "2.0"
    assert len(data["app"]["rules_version"]) == 12 and int(data["app"]["rules_version"], 16) >= 0
    assert data["generated"] == "2026-09-10T22:31:00Z"
    assert data["trades"] == ["XYZ"] and data["cover"]["h1"] == "Trade tomorrow. 1 A-quality burst."


def test_the_rules_version_moves_with_a_constant_and_not_with_key_order():
    night = _night()
    a = build(**night)["app"]["rules_version"]
    reordered = {"plan": {"RISK_PCT": 0.5}, "scans": {"BURST_RATIO": 1.04}}
    b = build(**_night(rules=reordered))["app"]["rules_version"]
    c = build(**_night(rules={"scans": {"BURST_RATIO": 1.05}, "plan": {"RISK_PCT": 0.5}}))["app"]["rules_version"]
    assert a == b != c


def test_the_contract_names_exactly_the_top_level_keys():
    data = build(**_night())
    assert set(data["_contract"]) == set(data)
    assert all(isinstance(p, str) and p for p in data["_contract"].values())


def test_a_top_level_key_the_contract_does_not_name_is_refused():
    """PRECONDITION: build() always agrees with its own contract, so the
    mismatch has to be planted; a subset check would pass the extra key."""
    data = build(**_night())
    data["extra"] = 1
    with pytest.raises(ValueError, match="_contract does not name exactly"):
        report.validate(data)
    del data["extra"]
    data["_contract"]["ghost"] = "a paragraph for a key that is not there"
    with pytest.raises(ValueError, match="_contract does not name exactly"):
        report.validate(data)


def test_a_nan_anywhere_becomes_null_and_is_counted():
    bursts = [_burst(volume_vs_prior=float("nan")), _miss()]
    bursts[0]["quality"]["base_depth_pct"] = math.inf
    data = build(**_night(bursts=bursts))
    assert data["bursts"][0]["volume_vs_prior"] is None
    assert data["bursts"][0]["quality"]["base_depth_pct"] is None
    assert data["run"]["sanitised"]["replaced"] == 2
    assert set(data["run"]["sanitised"]["paths"]) == {"bursts[].volume_vs_prior", "bursts[].quality.base_depth_pct"}
    assert "nan" not in json.dumps(data).lower().replace("financ", "")
    assert "NaN" not in json.dumps(data, allow_nan=False)


def test_a_grade_outside_the_vocabulary_is_refused():
    with pytest.raises(ValueError, match="bursts\\[0\\].grade 'A-'"):
        build(**_night(bursts=[_burst(grade="A-"), _miss()]))


def test_the_models_grade_is_held_to_the_same_vocabulary():
    burst = _burst()
    burst["claude"]["grade"] = "A++"
    with pytest.raises(ValueError, match="claude.grade"):
        build(**_night(bursts=[burst, _miss()]))


def test_a_status_outside_the_four_words_is_refused():
    with pytest.raises(ValueError, match="run.status 'crashed'"):
        build(**_night(run=_run(status="crashed")))


def test_a_problem_of_an_unknown_kind_is_refused_at_build():
    run = _run(problems=[{"stage": "email", "kind": "smtp_down", "message": "x"}])
    with pytest.raises(ValueError, match="seven words"):
        build(**_night(run=run))


def test_a_series_bar_missing_a_key_is_refused():
    burst = _burst(series=[{"date": SESSION, "o": 1, "h": 2, "l": 0.5, "c": 1.5}])
    with pytest.raises(ValueError, match="series\\[0\\]"):
        build(**_night(bursts=[burst, _miss()]))


def test_a_trade_that_is_not_a_burst_is_refused():
    with pytest.raises(ValueError, match="trades names 'QQQ'"):
        build(**_night(trades=["QQQ"]))


def test_every_burst_leaves_build_with_a_summary_sentence():
    data = build(**_night())
    assert all(b["summary"] == summary(b) for b in data["bursts"])
    assert data["bursts"][1]["summary"].startswith("ABC: +4.2%")


def test_the_closest_miss_is_the_best_burst_not_traded_and_says_why():
    data = build(**_night())
    assert data["closest_miss"] == {"ticker": "ABC", "grade": "B", "score": 7.8, "why": "vetoed: up_days",
                                    "sentence": "ABC came closest at B 7.8: vetoed: up_days."}
    assert build(**_night(trades=["XYZ", "ABC"]))["closest_miss"] is None


def test_the_closest_miss_is_the_highest_score_and_ties_break_by_ticker():
    """PRECONDITION: two non-trade bursts with different scores, or a flipped
    sort would pick the same one."""
    lower = _miss("DEF")
    lower["score"] = lower["quality"]["score"] = 5.0
    tied = _miss("AAA")
    assert build(**_night(bursts=[_burst(), lower, _miss()]))["closest_miss"]["ticker"] == "ABC"
    assert build(**_night(bursts=[_burst(), _miss(), tied]))["closest_miss"]["ticker"] == "AAA"


def test_the_vocabularies_are_the_contracts():
    assert GRADES == ("A+", "A", "B", "C", "skip")
    assert RUN_STATUSES == ("ok", "degraded", "closed", "failed")
    assert PROBLEM_KINDS == ("universe_cached", "coverage_thin", "claude_unavailable", "claude_partial",
                             "chart_missing", "email_failed", "push_retried")


# --- write() and contract_paths() ---------------------------------------------------------------

def test_write_is_atomic_and_reads_back_equal(tmp_path):
    data = build(**_night())
    target = tmp_path / "docs" / "data.json"
    target.parent.mkdir()
    target.write_text("{stale}")
    write(data, target)
    assert json.loads(target.read_text(encoding="utf-8")) == data
    assert [p.name for p in target.parent.iterdir()] == ["data.json"], "no temp file is left beside it"
    text = target.read_text(encoding="utf-8")
    assert text.startswith('{\n "schema_version": 2,') and "×" in text, "indent 1, key order kept, unicode kept"


def test_write_refuses_a_nan_rather_than_writing_an_invalid_file(tmp_path):
    target = tmp_path / "data.json"
    target.write_text("previous")
    with pytest.raises(ValueError):
        write({"x": float("nan")}, target)
    assert target.read_text() == "previous" and list(tmp_path.iterdir()) == [target]


def test_contract_paths_names_every_path_with_arrays_as_brackets():
    paths = contract_paths(build(**_night()))
    for expected in ("bursts[].plan.stop", "run.problems", "bursts[].series[].c", "cover.h1",
                     "watchlist.top[].plan.order_line", "open_plans[].instruction", "_contract.bursts"):
        assert expected in paths, expected
    assert "bursts[].plan.nonsense" not in paths


# --- the digest ---------------------------------------------------------------------------------

def test_the_subject_is_the_h1_and_the_session():
    assert digest_subject(build(**_night())) == "Trade tomorrow. 1 A-quality burst. · 2026-09-10"


def test_the_digest_carries_the_order_line_the_plans_and_the_alerts():
    data = build(**_night())
    markup = digest_html(data)
    text = _rendered(markup)
    assert ORDER_LINE in text
    assert "Buy zone 12.34–12.71" in text and "Stop 11.62" in text and "Shares 69" in text
    assert summary(data["bursts"][0]) in text
    assert "SELL HALF" in text and "Sell half at the open; raise the stop to 9.40." in text
    assert "WCH" in text and "Trigger 20.05" in text and "Stop 18.90" in text and "Shares 40" in text
    assert report.PAGE_URL in markup and 'href="https://spicychicken59.github.io/SpicyStock/"' in markup
    assert "<link" not in markup and "<style" not in markup, "inline styles only"


def test_a_ticker_that_looks_like_a_tag_reaches_the_reader_as_text():
    burst = _burst("<X>")
    burst["claude"]["reason"] = "Breakout above <resistance> on 3x volume"
    data = build(**_night(bursts=[burst, _miss()], trades=["<X>"]))
    markup = digest_html(data)
    assert "<X>" not in markup and "<resistance>" not in markup
    text = _rendered(markup)
    assert "<X>" in text and "Breakout above <resistance> on 3x volume" in text


def test_the_digest_never_prints_none_or_undefined():
    thin = _burst(plan=None, claude=None, score=None, chart=None, series=None)
    thin["quality"] = {"grade_mechanical": "A"}
    thin["grade"] = "A"
    night = _night(bursts=[thin, _miss()], trades=["XYZ"], watchlist={"top": [{"ticker": "WCH"}], "also_quiet": [], "counts": {}},
                   open_plans=[{"ticker": "OLD", "status": None}], cash_budget={}, run=_run(model=None, feed=None))
    for data in (build(**night), build(**_night(trades=[], open_plans=[], watchlist={"top": [], "also_quiet": [], "counts": {}}))):
        markup = digest_html(data)
        assert "None" not in markup and "undefined" not in markup and "nan" not in _rendered(markup).lower()


def test_the_digest_prints_the_fixed_sentence_for_each_problem():
    run = _run(status="degraded", problems=[problem("charts", "chart_missing", "<b>PIL</b> raised"),
                                           problem("email", "email_failed", "refused owner@example.invalid")])
    text = _rendered(digest_html(build(**_night(run=run))))
    assert PROBLEM_SENTENCES["chart_missing"] in text and PROBLEM_SENTENCES["email_failed"] in text
    assert "owner@" not in text and "<b>" not in text


def test_the_open_plan_chip_words_are_the_six_the_page_uses_and_an_unknown_one_is_itself():
    assert {"HOLD", "SELL HALF", "SELL INTO STRENGTH", "SELL", "STOPPED", "EXPIRED"} <= set(
        report.PLAN_STATUS_WORDS.values())
    assert report.PLAN_STATUS_WORDS["sell_into_strength"] == "SELL INTO STRENGTH"
    data = build(**_night(open_plans=[{"ticker": "OLD", "status": "half_out", "instruction": "x"}]))
    text = _rendered(digest_html(data))
    assert "HALF OUT" in text and "SELL" not in text, "an unknown word is printed as itself, never mapped"


def test_the_digest_says_what_a_night_with_nothing_to_do_holds():
    data = build(**_night(trades=[], open_plans=[], watchlist={"top": [], "also_quiet": [], "counts": {}}))
    text = _rendered(digest_html(data))
    assert "No orders for tomorrow." in text and "No open model plans." in text and "No anticipation names tonight." in text
    assert "SpicyStock does not know what you hold" in text and "What you hold" not in text


# --- delivery: the ported transport ---------------------------------------------------------

_TEST_MODE_REFUSAL = (
    "You can only send testing emails to your own email address (owner@example.invalid). "
    "To send emails to other recipients, please verify a domain at resend.com/domains, "
    "and change the `from` address to an email using this domain."
)


def test_send_digest_goes_through_the_mocked_transport_and_logs_a_count(fake_resend, caplog):
    import resend

    data = build(**_night())
    with caplog.at_level(logging.INFO, logger="src.report"):
        response = send_digest(data)

    assert response == {"id": "fake-email-id"}
    assert len(fake_resend.sent) == 1
    params = fake_resend.sent[0]
    assert params["to"] == ["one@example.invalid", "two@example.invalid"]
    assert params["from"] == "tests@example.invalid"
    assert params["subject"] == digest_subject(data) and params["attachments"] == []
    assert ORDER_LINE in params["html"]
    assert resend.api_key == "test-not-a-real-key"
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "to 2 recipient(s)" in said and "example.invalid" not in said, "the count, never the addresses"


@pytest.mark.parametrize("var", ["RESEND_API_KEY", "EMAIL_TO"])
def test_an_empty_delivery_variable_is_missing_not_present(monkeypatch, fake_resend, var):
    monkeypatch.setenv(var, "   ")
    with pytest.raises(KeyError, match=var):
        deliver("subject", "<p>body</p>")
    assert fake_resend.sent == []
    assert var in report.REQUIRED_ENV


def test_an_empty_sender_falls_back_to_resends_sandbox_address(monkeypatch, fake_resend):
    monkeypatch.setenv("RESEND_FROM", "")
    deliver("subject", "<p>body</p>")
    assert fake_resend.sent[0]["from"] == "onboarding@resend.dev"


def test_a_case_only_mismatch_is_resent_in_resends_own_spelling(fake_resend, monkeypatch, caplog):
    """EMAIL_TO was the account's address with a capital letter, Resend's
    test-mode check is an exact string match, and three dispatches drew the
    same refusal. Sent again as Resend spells it -- once, on this refusal
    only, and said out loud."""
    import resend

    monkeypatch.setenv("EMAIL_TO", "Owner@Example.invalid")
    calls: list[list[str]] = []

    def send(params, options=None):
        calls.append(list(params["to"]))
        if len(calls) == 1:
            raise RuntimeError(_TEST_MODE_REFUSAL)
        return {"id": "resent-id"}
    monkeypatch.setattr(resend.Emails, "send", send)

    with caplog.at_level(logging.WARNING, logger="src.report"):
        response = deliver("subject", "<p>body</p>")

    assert response == {"id": "resent-id"}
    assert calls == [["Owner@Example.invalid"], ["owner@example.invalid"]], calls
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "as Resend spells it" in said and "Re-save EMAIL_TO" in said
    assert "recipient(s):" not in said, "the diagnosis is for the refusals a retry cannot fix"


def test_a_second_refusal_after_the_respelling_is_raised_like_any_other(fake_resend, monkeypatch, caplog):
    import resend

    monkeypatch.setenv("EMAIL_TO", "Owner@Example.invalid")
    calls: list[list[str]] = []

    def send(params, options=None):
        calls.append(list(params["to"]))
        raise RuntimeError(_TEST_MODE_REFUSAL)
    monkeypatch.setattr(resend.Emails, "send", send)

    with caplog.at_level(logging.ERROR, logger="src.report"), pytest.raises(RuntimeError):
        deliver("subject", "<p>body</p>")
    assert len(calls) == 2, "one respelling, then no third attempt"
    assert "1 recipient(s): the address Resend named, at example.invalid" in \
        " ".join(r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("email_to, expected", [
    ("someone.else@example.test", "1 recipient(s): a different address, at example.test"),
    ("Owner@Example.invalid, someone.else@example.test",
     "2 recipient(s): the address Resend named in different capitalisation, at example.invalid; "
     "a different address, at example.test"),
    ("owner@example.invalid", "1 recipient(s): the address Resend named, at example.invalid"),
])
def test_only_a_case_only_mismatch_earns_the_second_send(fake_resend, monkeypatch, caplog, email_to, expected):
    """A different address is refused once and diagnosed by domain, never
    sent twice; the diagnosis never prints a recipient."""
    import resend

    monkeypatch.setenv("EMAIL_TO", email_to)
    calls: list[list[str]] = []

    def send(params, options=None):
        calls.append(list(params["to"]))
        raise RuntimeError(_TEST_MODE_REFUSAL)
    monkeypatch.setattr(resend.Emails, "send", send)

    with caplog.at_level(logging.ERROR, logger="src.report"), pytest.raises(RuntimeError):
        deliver("subject", "<p>body</p>")

    assert len(calls) == 1, calls
    said = " ".join(r.getMessage() for r in caplog.records)
    assert expected in said and "REPOSITORY secret" in said
    assert "someone.else@" not in said and "owner@" not in said.replace("Owner@", "owner@"), said


def test_any_other_resend_refusal_is_left_to_speak_for_itself(fake_resend, monkeypatch, caplog):
    import resend

    def refuse(params, options=None):
        raise RuntimeError("The example.invalid domain is not verified.")
    monkeypatch.setattr(resend.Emails, "send", refuse)

    with caplog.at_level(logging.ERROR, logger="src.report"), pytest.raises(RuntimeError):
        deliver("subject", "<p>body</p>")
    assert "recipient(s)" not in " ".join(r.getMessage() for r in caplog.records)


# --- the notices ----------------------------------------------------------------------------------

def test_the_failure_notice_names_the_session_it_has_no_plan_for(fake_resend):
    problems = [problem("bars", "coverage_thin", "only 40% answered")]
    send_failure_notice("evening", problems, None, expected_session="2026-09-11")
    params = fake_resend.sent[0]
    assert params["subject"] == "FAILED — no plan for 2026-09-11"
    text = _rendered(params["html"])
    assert "No verdict for 2026-09-11." in text and PROBLEM_SENTENCES["coverage_thin"] in text
    assert "None" not in params["html"] and params["attachments"] == []


def test_after_a_publish_the_digest_itself_is_the_notice_with_the_problems_it_now_carries(fake_resend):
    data = build(**_night())
    extra = problem("email", "email_failed", "refused")
    send_failure_notice("evening", [extra], data)
    params = fake_resend.sent[0]
    assert params["subject"] == digest_subject(data)
    assert ORDER_LINE in params["html"] and PROBLEM_SENTENCES["email_failed"] in _rendered(params["html"])


def test_a_closed_market_goes_out_under_its_own_subject(fake_resend):
    run = _run(session="2026-09-09", session_state="closed", status="closed", expected_session="2026-09-10")
    data = build(**_night(run=run, trades=[]))
    closed_market_digest(data)
    send_digest(data)
    assert [p["subject"] for p in fake_resend.sent] == ["Market closed — plans unchanged"] * 2
    assert "Market closed. Plans unchanged." in _rendered(fake_resend.sent[1]["html"])


def test_the_closest_miss_is_never_a_plan_the_budget_cut():
    """A name with an order the slots could not take is beyond the cap, not
    a miss; the miss is the best burst that did not qualify."""
    data = build(**_night(trades=["XYZ"], bursts=[_burst(), _burst("BIG", score=9.9), _miss()], beyond_cap=["BIG"]))
    assert data["closest_miss"]["ticker"] == "ABC"
    assert build(**_night(trades=["XYZ"], bursts=[_burst(), _burst("BIG", score=9.9)], beyond_cap=["BIG"]))["closest_miss"] is None


def test_the_hold_action_points_at_an_element_the_page_has():
    page = (Path(__file__).resolve().parent.parent / "docs" / "index.html").read_text()
    for label, target in (report.HOLD_ACTION, report.ORDERS_ACTION):
        assert f'id="{target[1:]}"' in page, target
    assert report.HOLD_ACTION == ("Open model plans", "#hold")


def test_the_problems_block_prints_the_fixed_sentence_and_never_the_recorded_message():
    html = report._problems_block([problem("grade", "claude_unavailable", "no reply for any of 5 names (502 Bad Gateway)")])
    assert PROBLEM_SENTENCES["claude_unavailable"] in _rendered(html)
    assert "502" not in html and "no reply for any" not in html


def test_an_alert_with_no_ticket_says_why_in_the_pages_words():
    row = {"ticker": "COIL", "setups": ["TI65"], "plan": {"trigger": 110.61, "stop": 109.5, "shares": 0,
                                                          "order_line": None, "action": "no_new_longs"}}
    text = _rendered(report._alert_row(row))
    assert "No order" in text and "breadth sizes new positions at zero tonight" in text
    row["plan"]["action"] = "no_order"
    row["plan"]["reason"] = None
    assert "No order · no order tonight" in _rendered(report._alert_row(row))


def test_the_open_plan_row_names_the_hold_length_off_the_rules():
    data = build(**_night(rules={"plan": {"final_exit_day": 5}, "scans": {}}))
    assert "day 2 of 5" in _rendered(digest_html(data))


def test_the_digest_prints_an_uncertain_plan_and_a_withheld_ticket_in_the_pages_words():
    uncertain = {"ticker": "UNC", "picked": "2026-09-09", "day": 1, "status": "uncertain", "uncertainty": "trigger_timing",
                 "instruction": "Day 1 (2026-09-10): opened under the trigger; the day reached it at a time the bar cannot give. The model books no fill."}
    withheld = _burst("WHD", plan=_plan(action="refused", eligible=False, order_line=None, order_json=None,
                                        reason="ticket withheld: at the $12.71 limit the stop is 8.6% away"))
    night = _night(bursts=[_burst(), withheld, _miss()], trades=["XYZ"], beyond_cap=["WHD"], open_plans=[uncertain],
                   cash_budget={"committed_usd": 852, "slots_used": 2, "slots_max": 4,
                                "sentence": "Model allocation: tomorrow's tickets would commit $852.00 of the configured $10,000.00; 2 of 4 slots (1 open model plan)",
                                "cut": [{"ticker": "WHD", "kind": "withheld", "reason": withheld["plan"]["reason"]}]})
    text = _rendered(digest_html(build(**night)))
    assert "UNCERTAIN" in text and uncertain["instruction"] in text
    assert "No ticket for WHD: ticket withheld: at the $12.71 limit the stop is 8.6% away." in text
    assert "Beyond the slot cap" not in text
    assert "Model allocation: tomorrow's tickets would commit $852.00 of the configured $10,000.00; 2 of 4 slots (1 open model plan). Not a balance or buying power." in text
    assert "Open model plans" in text and "What you hold" not in text


def test_the_trade_block_carries_the_sizing_note_and_the_day_order_term():
    burst = _burst(plan=_plan(sizing_note="sized at the $12.71 limit, the highest fill the ticket permits: 69 shares put $75.21 between that fill and the $11.62 stop, planned price-to-stop risk, not a maximum loss",
                              order_terms=["A day order rests until the close unless you cancel it.", "second term"]))
    text = _rendered(report._trade_block(burst, None))
    assert "sized at the $12.71 limit" in text and "not a maximum loss" in text
    assert "A day order rests until the close unless you cancel it." in text and "second term" not in text
    assert "fallback" not in text.lower()


def test_the_breadth_line_prints_the_ratio_to_two_places_like_the_page():
    breadth = _breadth()
    breadth["ratio_10d"] = 0.88
    assert "10-day ratio 0.88" in _rendered(report._breadth_line(breadth))
