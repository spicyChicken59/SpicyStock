"""A metrics leg must actually fit inside the image sent to the reader."""
from types import SimpleNamespace
from src import charts
from tests.test_charts import _plot_spy


def test_full_claimed_leg_is_in_the_dated_image(ohlcv, monkeypatch, tmp_path):
    frame = ohlcv('burst')
    start = len(frame) - 95
    assessment = SimpleNamespace(leg={'start': start, 'end': len(frame)-20},
                                 base={'start': len(frame)-19, 'end': len(frame)-2})
    context = charts.reader_context(frame, assessment)
    seen = {}; _plot_spy(monkeypatch, seen)
    charts.render_chart('AAA', frame, str(tmp_path), context_start=context['start_index'])
    assert seen['frame'].index[0] == frame.index[start]
    assert context['regions']['leg']['from'] == frame.index[start].date().isoformat()
    assert context['through'] == frame.index[-1].date().isoformat()
    assert context['rows'] == len(seen['frame'])


def test_ordinary_chart_and_future_boundary_are_unchanged(ohlcv, monkeypatch, tmp_path):
    frame = ohlcv('burst'); seen = {}; _plot_spy(monkeypatch, seen)
    charts.render_chart('AAA', frame, str(tmp_path), through=len(frame)-3,
                        context_start=len(frame)-100)
    assert seen['frame'].index[-1] == frame.index[-3]
    charts.render_chart('AAA', frame, str(tmp_path))
    assert len(seen['frame']) == charts.SESSIONS
