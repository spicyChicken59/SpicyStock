"""tools/live_check.py, driven through the same doubles the pipeline tests use.

The tool exists because every boundary that needs a socket is untested, and
the sandbox has no socket. So the tool itself is what gets tested here: every
verdict it can print, produced by the failure that earns it, with the doubles
standing in for the real Alpaca, Claude and Resend the way they do for the
pipeline. A tool that checks the first run, and has not itself been checked,
is one more thing to find out about on the first night.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
from datetime import datetime, timezone

import pytest
import requests
from alpaca.common.exceptions import APIError
from requests.exceptions import HTTPError

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load():
    import sys

    spec = importlib.util.spec_from_file_location("live_check", ROOT / "tools" / "live_check.py")
    module = importlib.util.module_from_spec(spec)
    # Registered before execution: @dataclass looks its class's module up in
    # sys.modules, and a module loaded by path is not there until someone
    # puts it there.
    sys.modules["live_check"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def live():
    return _load()


@pytest.fixture
def boundaries(fake_alpaca, fake_anthropic, fake_resend, ohlcv):
    """All three doubles, with AAPL registered so the default symbol answers."""
    fake_alpaca.add_history("AAPL", ohlcv("burst", variant=3))
    return {"alpaca": fake_alpaca, "anthropic": fake_anthropic, "resend": fake_resend}


def _alpaca_error(status: int | None, message: str) -> APIError:
    body = json.dumps({"message": message})
    if status is None:
        return APIError(body)
    response = requests.Response()
    response.status_code = status
    return APIError(body, HTTPError(response=response))


def by_name(checks):
    return {c.name: c for c in checks}


# The clock the checks are told, so the Alpaca double's bars land on the
# session the tool expects: a Thursday evening after the close.
NOW = datetime(2026, 9, 3, 22, 30, tzinfo=timezone.utc)


@pytest.fixture
def pinned_clock(live, monkeypatch):
    """current_session() answers for NOW, not for the hour the test runs at."""
    real = live.scanner.current_session
    monkeypatch.setattr(live.scanner, "current_session", lambda now=None: real(NOW))


# ------------------------------------------------------------ all clear ----
def test_every_boundary_answers_and_the_verdict_is_ready(live, pinned_clock, boundaries, monkeypatch):
    checks = live.run_checks(now=NOW)

    assert [c.name for c in checks] == list(live.ALL_CHECKS)
    assert all(c.ok for c in checks), [(c.name, c.status, c.detail) for c in checks if not c.ok]
    out = live.render(checks)
    assert "READY for the first scheduled run" in out
    assert "Persist the run" in out, "the one thing it cannot try is named, not implied"


def test_it_drives_the_pipelines_own_calls_not_copies_of_them(live, pinned_clock, boundaries, monkeypatch):
    """A pass has to mean the nightly run's calls work. So the bars request is
    the scan's own (the double records the SDK's wire fields), the scoring call
    carries the cached system prompt the run sends, and the mail goes through
    the run's only send path."""
    live.run_checks(now=NOW)

    fields = boundaries["alpaca"].request_fields[-1]
    assert fields.get("adjustment") == "split" and fields.get("feed"), fields
    calls = boundaries["anthropic"].calls
    assert len(calls) == 2, "one scoring call and one cache-hit call"
    assert calls[0]["system"][0].get("cache_control") == {"type": "ephemeral"}
    sent = boundaries["resend"].sent
    assert len(sent) == 1 and sent[0]["subject"] == live.TEST_SUBJECT
    assert sent[0]["from"] == "tests@example.invalid", "RESEND_FROM, via the run's own sender rule"


def test_the_sender_rule_has_one_copy_and_the_tool_reads_it(live, boundaries, monkeypatch):
    """A check that carried its OWN four lines of sender fallback would pass
    every test above, because the copy is correct today. It is a second copy
    of a rule this project has already watched drift once, so the test is:
    change the rule in src.emailer and see the tool follow. Found by
    mutation -- the copy survived everything else in this file."""
    monkeypatch.setattr(live.emailer, "sender_address", lambda: "sentinel@example.invalid")
    live.run_checks(only=("resend",), now=NOW)
    assert boundaries["resend"].sent[0]["from"] == "sentinel@example.invalid"


def test_the_resend_check_follows_the_senders_one_rule_rather_than_carrying_a_copy(
    live, boundaries, monkeypatch
):
    """A copy of the sender-fallback rule that is correct today passes every
    test that only checks the address. This changes the rule in the one place
    it lives and asks whether the tool followed -- a tool with its own copy
    would go on sending from the old address, and that is the mutant that
    survived until this test existed."""
    monkeypatch.setattr(live.emailer, "sender_address", lambda: "sentinel@rule.moved")

    checks = by_name(live.run_checks(only=("resend",), now=NOW))

    assert boundaries["resend"].sent[0]["from"] == "sentinel@rule.moved"
    assert "sentinel@rule.moved" in checks["resend"].detail


def test_a_real_chart_is_scored_when_alpaca_supplied_one_and_a_synthetic_one_otherwise(
    live, pinned_clock, boundaries
):
    with_bars = by_name(live.run_checks(now=NOW))["claude"]
    assert "a real chart of AAPL" in with_bars.detail

    boundaries["anthropic"].calls.clear()
    boundaries["alpaca"].history.clear()          # nothing to draw
    without = by_name(live.run_checks(now=NOW))
    assert without["alpaca"].status == "FAIL" and "returned no bars" in without["alpaca"].detail
    assert without["claude"].ok and "a synthetic chart" in without["claude"].detail, (
        "the model boundary is checked even when the data boundary failed")


# ------------------------------------------------------------- no spend ----
def test_no_spend_skips_exactly_the_checks_that_cost_something(live, boundaries):
    checks = by_name(live.run_checks(spend=False, now=NOW))
    for name in live.SPENDING:
        assert checks[name].status == "skip", name
    assert boundaries["anthropic"].calls == [] and boundaries["resend"].sent == []
    out = live.render(list(checks.values()))
    assert "paid boundaries were not tried" in out
    assert "READY" not in out, "no READY verdict on a run that did not try the paid boundaries"


def test_only_runs_the_named_checks_and_names_an_unknown_one(live, boundaries):
    checks = live.run_checks(only=("clock", "alpaca", "nosuch"), now=NOW)
    assert [c.name for c in checks] == ["clock", "alpaca", "nosuch"]
    assert checks[-1].status == "skip" and "no such check" in checks[-1].detail
    assert boundaries["anthropic"].calls == []


# ------------------------------------------------------------------ env ----
def test_a_missing_key_fails_env_and_skips_the_layer_that_needs_it(live, boundaries, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    checks = by_name(live.run_checks(now=NOW))

    assert checks["env"].status == "FAIL" and "ANTHROPIC_API_KEY" in checks["env"].detail
    assert "the morning run has what it needs" in checks["env"].detail
    assert checks["claude"].status == "skip" and "ANTHROPIC_API_KEY" in checks["claude"].detail
    assert checks["cache"].status == "skip"
    assert checks["alpaca"].ok and checks["resend"].ok, "the other layers are still tried"
    assert boundaries["anthropic"].calls == [], "nothing is sent to a boundary with no key"


def test_an_empty_key_counts_as_missing_the_way_actions_passes_one(live, boundaries, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "")
    checks = by_name(live.run_checks(now=NOW))
    assert checks["env"].status == "FAIL" and "RESEND_API_KEY" in checks["env"].detail
    assert checks["resend"].status == "skip"


def test_an_unset_sender_is_reported_as_the_sandbox_fallback_not_as_missing(live, boundaries, monkeypatch):
    monkeypatch.delenv("RESEND_FROM")
    checks = by_name(live.run_checks(now=NOW))
    assert checks["env"].ok and "sandbox sender" in checks["env"].detail
    assert boundaries["resend"].sent[0]["from"] == "onboarding@resend.dev"


# --------------------------------------------------------------- alpaca ----
def test_a_401_is_reported_as_a_credential_problem_not_a_plan_problem(live, boundaries):
    boundaries["alpaca"].raise_on_bars = _alpaca_error(401, "request is not authorized")
    c = by_name(live.run_checks(only=("alpaca",), now=NOW))["alpaca"]
    assert c.status == "FAIL"
    assert "ALPACA_API_KEY" in c.detail and "401" in c.detail
    assert not c.detail.startswith("Alpaca refused the"), "that is the 403 message"


def test_a_403_is_reported_as_a_feed_problem_naming_scan_feed(live, boundaries):
    boundaries["alpaca"].raise_on_bars = _alpaca_error(
        403, "subscription does not permit querying recent SIP data")
    c = by_name(live.run_checks(only=("alpaca",), now=NOW))["alpaca"]
    assert c.status == "FAIL" and "SCAN_FEED" in c.detail and "subscribe" in c.detail


def test_a_transport_error_is_a_failure_that_names_the_feed(live, boundaries):
    boundaries["alpaca"].raise_on_bars = RuntimeError("connection reset by peer")
    c = by_name(live.run_checks(only=("alpaca",), now=NOW))["alpaca"]
    assert c.status == "FAIL" and "connection reset" in c.detail and "feed" in c.detail


def test_a_feed_behind_the_session_passes_but_says_so(live, pinned_clock, boundaries, ohlcv, monkeypatch):
    boundaries["alpaca"].add_history("AAPL", ohlcv("burst", variant=3), stale_sessions=2)
    c = by_name(live.run_checks(only=("alpaca",), now=NOW))["alpaca"]
    assert c.ok and "BEHIND the session" in c.detail
    assert c.data["fresh"] is False


def test_the_live_check_says_when_the_feed_repeated_a_bar_and_stays_quiet_when_it_did_not(
    live, boundaries, ohlcv
):
    """The third caller of the scan's downloader, and the one that touches the
    LIVE feed from a machine with the keys -- so it is the likeliest place the
    first real duplicate is met, and it reported "200 bars for AAPL" for a
    202-bar response with nothing saying which copies it had dropped. The
    count is the same out-parameter the scan and the forward-returns fetch
    pass; here it is one clause on the OK detail."""
    quiet = by_name(live.run_checks(only=("alpaca",), now=NOW))["alpaca"]
    assert quiet.ok and "sent twice" not in quiet.detail and "duplicate" not in quiet.detail

    boundaries["alpaca"].send_session_bar_twice("AAPL", copies=2)
    c = by_name(live.run_checks(only=("alpaca",), now=NOW))["alpaca"]

    assert c.ok, c.detail
    assert "2 extra bar(s) dropped as duplicates, keeping the copy that arrived last" in c.detail
    assert f"{len(quiet.data['frame'])} bars for AAPL" in c.detail, (
        "and the bar count is still the de-duplicated frame's, which is what the rules read")


# --------------------------------------------------------------- claude ----
def test_the_stand_in_candidate_carries_the_scans_own_volume_arithmetic(live, ohlcv):
    """The one tool that reaches the real API builds its own Candidate, and
    the pair it puts in the request is `avg_volume` beside a `volume_ratio`
    knowledge/strategy.md tells the model to divide back out.

    It retyped the scan's 50-session window as `iloc[-51:-1]`, so nothing tied
    the two numbers together and an off-by-one here would have sent a ratio
    over a baseline the payload did not name -- the exact sentence
    src.scorer.volume_ratio_basis() exists to avoid printing. It calls
    trailing_volume_mean() now, and this reads the result back through the
    scorer's own derivation.
    """
    from src.scanner import ScanConfig, trailing_volume_mean
    from src.scorer import volume_ratio_basis

    frame = ohlcv("burst")
    cand = live._candidate("AAA", frame)
    # ROUNDED, the way detect_setup() archives it, not truncated. The pair
    # this sends is read back by volume_ratio_basis(), whose one step of
    # slack is reasoned from round() -- so a tool that truncates is a tool
    # whose request is rounded differently from every real candidate's.
    assert cand.avg_volume == round(trailing_volume_mean(frame, ScanConfig()))
    assert "trailing average" in volume_ratio_basis(cand)


def test_a_frame_with_no_measurable_volume_average_is_not_sent_as_one_share(live, boundaries, ohlcv):
    """`trailing_volume_mean() or 1.0` made 1 a denominator.

    The two are not the same function on a frame with holes: the scan's mean
    dropna()s its window and returns None below `min_rvol_sessions`, and `or
    1.0` then told the live model "a trailing average of 1 shares" beside a
    volume_ratio of three million. Reproduced on a frame whose last sixty
    volumes are NaN: avg_volume 1, volume_ratio 3000000.0. This is the one
    request in the repo that reaches the real endpoint, and the round that
    wrote the line pinned it on a clean synthetic frame only.

    A frame the scan could not have measured is a frame this tool cannot
    build the pair from, so it falls back to the synthetic one the way
    check_claude already does below 85 bars -- and says which of the two
    reasons it was, rather than sending a number nothing produced.
    """
    from src.scanner import ScanConfig, trailing_volume_mean

    frame = ohlcv("burst").copy()
    frame.iloc[-60:, frame.columns.get_loc("Volume")] = float("nan")
    assert len(frame) >= 85, "precondition: long enough that the bar count is not the reason"
    assert trailing_volume_mean(frame, ScanConfig()) is None, (
        "precondition: the scan itself would refuse to measure an average here")

    check = live.check_claude(frame=frame, ticker="AAA")

    assert check.ok, check.detail
    assert "synthetic chart" in check.detail and "trailing" in check.detail, check.detail
    cand = check.data["inputs"][0]
    assert cand.avg_volume > 1, "a baseline of one share is not a baseline"


def test_a_rejected_anthropic_key_fails_claude_and_skips_the_cache_check(live, boundaries):
    boundaries["anthropic"].set_error(RuntimeError("Error code: 401 - invalid x-api-key"))
    checks = by_name(live.run_checks(now=NOW))
    assert checks["claude"].status == "FAIL" and "fell back" in checks["claude"].detail
    assert "401" in checks["claude"].detail
    assert checks["cache"].status == "skip"


def test_a_reply_the_parser_cannot_read_is_a_failure_here_even_though_the_run_survives_it(
    live, boundaries
):
    boundaries["anthropic"].set_raw("Looks like a decent setup, maybe a 7.")
    c = by_name(live.run_checks(now=NOW))["claude"]
    assert c.status == "FAIL" and "fell back" in c.detail and "ScoreFormatError" in c.detail


def test_a_request_without_cache_control_is_caught_before_the_first_night_pays_for_it(
    live, boundaries, monkeypatch
):
    real = live.scorer.request_kwargs

    def uncached(system, content, model=None):
        kwargs = real(system, content, model)
        kwargs["system"] = system
        return kwargs

    monkeypatch.setattr(live.scorer, "request_kwargs", uncached)
    c = by_name(live.run_checks(now=NOW))["claude"]
    assert c.status == "FAIL" and "NO cached prefix" in c.detail


def test_a_cache_that_never_hits_is_a_failure_on_the_second_call(live, boundaries, monkeypatch):
    import tests.fakes as fakes

    real = fakes.billed_usage

    def never_reads(kwargs, calls, uncached=1109):
        usage = real(kwargs, calls, uncached)
        usage.cache_creation_input_tokens += usage.cache_read_input_tokens
        usage.cache_read_input_tokens = 0
        return usage

    monkeypatch.setattr(fakes, "billed_usage", never_reads)
    checks = by_name(live.run_checks(now=NOW))
    assert checks["claude"].ok, "the first call is fine: it wrote the prefix"
    assert checks["cache"].status == "FAIL" and "read nothing from cache" in checks["cache"].detail


# --------------------------------------------------------------- resend ----
def test_a_refused_sender_domain_fails_resend_and_says_what_the_run_would_do(live, boundaries, monkeypatch):
    import resend

    def refuse(params, options=None):
        raise RuntimeError("The example.invalid domain is not verified")

    monkeypatch.setattr(resend.Emails, "send", refuse)
    c = by_name(live.run_checks(only=("resend",), now=NOW))["resend"]
    assert c.status == "FAIL"
    assert "not verified" in c.detail and "exit 3" in c.detail


# ----------------------------------------------------------------- main ----
def test_main_exits_nonzero_on_any_failure_and_zero_otherwise(live, pinned_clock, boundaries, capsys, monkeypatch):
    assert live.main(["--no-spend"]) == 0
    assert "paid boundaries were not tried" in capsys.readouterr().out

    boundaries["alpaca"].raise_on_bars = _alpaca_error(401, "not authorized")
    assert live.main(["--only", "alpaca"]) == 1
    assert "NOT READY: 1 check(s) failed -- alpaca" in capsys.readouterr().out


def test_the_symbol_flag_is_upper_cased_and_reaches_the_request(live, boundaries, ohlcv, capsys):
    boundaries["alpaca"].add_history("MSFT", ohlcv("burst", variant=4))
    live.main(["--only", "alpaca", "--symbol", "msft"])
    assert boundaries["alpaca"].request_fields[-1]["symbols"] == "MSFT"
