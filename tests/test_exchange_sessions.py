"""Exchange-session regressions, first run against the weekday-only baseline."""
from datetime import date, datetime

import pytest

from src import clock, pipeline, plan, timing, universe


FRIDAY = date(2024, 8, 30)
HOLIDAY = date(2024, 9, 2)  # NYSE Labor Day
TUESDAY = date(2024, 9, 3)


def test_friday_signal_skips_the_monday_exchange_holiday():
    assert plan.next_sessions(FRIDAY, 2) == [TUESDAY, date(2024, 9, 4)]


def test_previous_session_after_holiday_is_friday():
    assert clock.previous_session(TUESDAY) == FRIDAY


def test_pinned_holiday_is_refused_before_provider_spending(monkeypatch):
    monkeypatch.setenv('SCAN_SESSION_DATE', HOLIDAY.isoformat())
    with pytest.raises(ValueError, match='not an XNYS trading session'):
        clock.pinned_session()


def test_shortened_session_serializes_its_actual_close():
    tm = timing.plan_timing(date(2024, 11, 27), date(2024, 11, 29),
                            window='first 30 minutes', window_minutes=30)
    assert tm['closes_at'] == '2024-11-29T13:00:00-05:00'


def test_holiday_evening_needs_no_directory_bars_or_model(
        fake_alpaca, fake_anthropic, monkeypatch, tmp_path):
    monkeypatch.delenv('SCAN_SESSION_DATE', raising=False)
    calls = []
    def directory(*a, **kw):
        calls.append('directory')
        return universe._explicit_universe(['AAA'])
    monkeypatch.setattr(universe, 'build', directory)
    rep = pipeline.run_evening(dry_run=True, docs=tmp_path,
        now=datetime(2024, 9, 2, 18, 30, tzinfo=clock.MARKET_TZ))
    assert calls == [], 'known holiday reached universe/provider work'
    assert fake_alpaca.bar_requests == [] and fake_anthropic.calls == []
    assert not rep.published and not rep.failed


def test_early_close_completion_uses_the_existing_fifteen_minute_buffer():
    assert clock.current_session(datetime(2024, 11, 29, 13, 15, tzinfo=clock.MARKET_TZ)) == date(2024, 11, 29)


def test_expected_open_missing_bars_is_an_outage_not_a_holiday():
    import pandas as pd
    frames = {'AAA': pd.DataFrame({'Close': [10], 'Volume': [100000]},
                                  index=pd.to_datetime(['2024-09-09']))}
    assert pipeline.session_state(frames, date(2024, 9, 10)) == ('outage', 0.0)


from src import sessions, market_data, report, record


@pytest.mark.parametrize('instant,expected', [
    ('2024-08-26T16:15:00-04:00', '2024-08-26'),
    ('2024-08-26T16:14:59-04:00', '2024-08-23'),
    ('2024-08-31T18:00:00-04:00', '2024-08-30'),
    ('2024-09-01T18:00:00-04:00', '2024-08-30'),
    ('2024-09-02T18:00:00-04:00', '2024-08-30'),
    ('2024-09-03T16:15:00-04:00', '2024-09-03'),
    ('2024-11-29T13:14:59-05:00', '2024-11-27'),
    ('2024-11-29T13:15:00-05:00', '2024-11-29'),
    ('2024-12-02T10:00:00-05:00', '2024-11-29'),
])
def test_completed_session_uses_real_sessions_and_dated_cutoffs(instant, expected):
    assert str(sessions.completed_session(datetime.fromisoformat(instant))) == expected


@pytest.mark.parametrize('day,opens,closes,shortened', [
    ('2024-03-08', '09:30:00-05:00', '16:00:00-05:00', False),
    ('2024-03-11', '09:30:00-04:00', '16:00:00-04:00', False),
    ('2024-11-01', '09:30:00-04:00', '16:00:00-04:00', False),
    ('2024-11-04', '09:30:00-05:00', '16:00:00-05:00', False),
    ('2024-11-29', '09:30:00-05:00', '13:00:00-05:00', True),
    ('1992-11-27', '09:30:00-05:00', '14:00:00-05:00', True),
])
def test_hours_come_from_versioned_xnys_including_dst_and_different_early_closes(day, opens, closes, shortened):
    row = sessions.session_info(date.fromisoformat(day))
    assert row['opens_at'] == day + 'T' + opens
    assert row['closes_at'] == day + 'T' + closes
    assert row['shortened'] is shortened


def test_holiday_pin_fails_pipeline_preflight_even_without_credentials(monkeypatch, tmp_path, fake_alpaca, fake_anthropic):
    monkeypatch.setenv('SCAN_SESSION_DATE', '2024-09-02')
    with pytest.raises(pipeline.PreflightError, match='2024-09-02 is not an XNYS trading session'):
        pipeline.run_evening(docs=tmp_path)
    assert fake_alpaca.bar_requests == [] and fake_anthropic.calls == []
    assert list(tmp_path.iterdir()) == []


def test_single_symbol_after_holiday_is_adjacent_without_closure_votes():
    import pandas as pd
    df = pd.DataFrame({'Open': [10, 11], 'High': [11, 12], 'Low': [9, 10], 'Close': [10, 11], 'Volume': [100000, 200000]}, index=pd.to_datetime(['2024-08-30', '2024-09-03']))
    stats = market_data.DownloadStats(requested=1, with_bars=1, session=TUESDAY, feed="sip")
    assert list(market_data.apply_session_rules({'X': df}, TUESDAY, stats)) == ['X']
    assert stats.previous_session == FRIDAY and not stats.previous_session_observed
    df.index = pd.to_datetime(['2024-08-29', '2024-09-03'])
    assert not market_data.apply_session_rules({'X': df}, TUESDAY, stats)
    assert stats.gapped == {'X': date(2024, 8, 29)}


def test_calendar_provenance_agrees_with_timing_and_rejects_forged_early_close():
    from copy import deepcopy
    measured = date(2024, 11, 27)
    run = {'session': str(measured), 'calendar': sessions.publication(measured), 'timing': pipeline.plan_timing(measured, measured, False)}
    assert sessions.record_faults(run) == []
    assert run['calendar']['applicable_session'] == '2024-11-29'
    bad = deepcopy(run); bad['timing']['closes_at'] = '2024-11-29T16:00:00-05:00'
    assert sessions.record_faults(bad)
    assert sessions.record_faults({'session': '2024-11-27'}) == []  # legacy is not rewritten


def test_plan_walk_does_not_renumber_a_missing_exchange_session():
    from tests.test_record import pick, LATER, frame
    bars = record.later_bars(frame(LATER), '2026-09-01')
    assert record.replay(pick(), bars)['status'] != record.UNREADABLE
    assert record.replay(pick(), bars[1:])['status'] == record.UNREADABLE
    assert record.replay(pick(), bars[:2] + bars[3:])['status'] == record.UNREADABLE


def test_calendar_bounds_and_naive_instants_fail_precisely():
    with pytest.raises(ValueError, match='outside supported'):
        sessions.is_session(date(2036, 1, 2))
    with pytest.raises(ValueError, match='offset-aware'):
        sessions.completed_session(datetime(2024, 9, 3, 18))


def test_holiday_intraday_also_avoids_provider_and_email(tmp_path, fake_alpaca, fake_resend):
    rep = pipeline.run_intraday(docs=tmp_path, now=datetime(2024, 9, 2, 10, tzinfo=clock.MARKET_TZ))
    assert rep.status == 'no_session' and not rep.published
    assert fake_alpaca.bar_requests == [] and fake_resend.sent == []


@pytest.mark.parametrize('outcome', ['no_session', 'session_incomplete', 'ok'])
def test_cli_exposes_whether_a_new_publication_exists(monkeypatch, tmp_path, outcome):
    output = tmp_path / 'actions-output'
    monkeypatch.setenv('GITHUB_OUTPUT', str(output))
    rep = pipeline.RunReport(published=outcome == 'ok', skipped=outcome if outcome != 'ok' else None)
    monkeypatch.setattr(pipeline, 'run_evening', lambda **kw: rep)
    assert pipeline.main(['evening', '--dry-run']) == 0
    assert output.read_text() == f"published={str(rep.published).lower()}\noutcome={outcome}\n"


def test_dated_schedule_and_email_agree_on_holiday_and_early_close():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent / 'fixtures' / 'page'
    for name, measured, applicable, close in [('closed', '2026-09-04', '2026-09-08', '16:00:00-04:00'),
                                                ('early', '2024-11-27', '2024-11-29', '13:00:00-05:00')]:
        data = json.loads((root / (name + '.json')).read_text())
        tm = data['run']['timing']
        assert tm['applicable_session'] == applicable
        assert tm['closes_at'] == applicable + 'T' + close
        for burst in data['bursts']:
            if burst.get('plan'):
                dated = plan.dated_schedule(burst['plan'], date.fromisoformat(measured))
                assert dated[0]['date'] == applicable
                days = [str(d) for d in sessions.next_sessions(date.fromisoformat(measured), plan.FINAL_EXIT_DAY)]
                assert all(row['date'] == days[row['day'] - 1] for row in dated)
        mail = report.digest_html(data)
        assert applicable in mail and tm['closes_at'] in mail and 'XNYS' in mail
        assert 'tomorrow' not in mail.lower()


def test_incomplete_session_skips_before_spending(monkeypatch, tmp_path, fake_alpaca, fake_anthropic):
    monkeypatch.delenv('SCAN_SESSION_DATE', raising=False)
    rep = pipeline.run_evening(docs=tmp_path, now=datetime.fromisoformat('2024-11-29T13:14:59-05:00'))
    assert rep.status == 'session_incomplete' and not rep.published
    assert fake_alpaca.bar_requests == [] and fake_anthropic.calls == []
