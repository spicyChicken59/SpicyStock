"""Independent historical boundaries, not tests of profitable outcomes."""
from copy import deepcopy
import pytest
from src import plan
from tools.historical_validation import independent_band, preview, plan_oracle, inspect_frame, event_study


@pytest.mark.parametrize('close,low,high', [(2,1.99,2.01),(17.82,17.11,17.88),
    (11.17,10.61,11.38),(100,96,100),(100,92,100),(1000,999,1001),(10000,9900,10001)])
def test_cent_band_and_shares_match_independent_equations(close,low,high):
    row={'ticker':'CONTROL','close':close,'low':low,'high':high,'open':low,
         'prev_close':low,'gain_pct':5,'scan':'burst'}
    p=preview(row,plan.Account());reference=independent_band(row)
    assert p['eligible']==reference['admitted']
    assert not plan_oracle(p)
    if p['eligible']:
        assert (p['stop'],p['limit'])==(reference['selected']['stop'],reference['selected']['limit'])


def source():
    return {'dates':['2026-09-23','2026-09-24','2026-09-25'],
            'columns':['Open','High','Low','Close','Volume'],
            'values':[[10]*3,[11]*3,[9]*3,[10]*3,[100001]*3]}


@pytest.mark.parametrize('kind', ['duplicate','wrong_session','bad_price','fractional_volume'])
def test_independent_value_inspector_refuses_corruption(kind):
    obj=source()
    if kind=='duplicate':obj['dates'][1]=obj['dates'][0]
    if kind=='wrong_session':obj['dates'][-1]='2026-09-28'
    if kind=='bad_price':obj['values'][1][0]=8
    if kind=='fractional_volume':obj['values'][4][0]=100000.5
    assert inspect_frame(obj,'2026-09-25')['errors']
    assert not inspect_frame(source(),'2026-09-25')['errors']


def test_outcome_cannot_borrow_signal_close_from_another_adjustment_basis():
    def pub(day,close,series):
        return ({'session':day,'published_at':day+'T22:00:00Z','sha256':day},
                {'bursts':[{'ticker':'AAA','close':close,'grade_mechanical':'A','series':series}]})
    bar=lambda day,c: {'date':day,'o':c,'h':c,'l':c,'c':c,'v':100000}
    old=pub('2026-09-24',10,[bar('2026-09-24',10)])
    revised=pub('2026-09-25',5.25,[bar('2026-09-24',5),bar('2026-09-25',5.25)])
    study=event_study([old,revised],{})
    assert study['rows'][0]['close_change_pct'] is None
    assert study['revised_bar_observations']==1


def test_missing_lookback_stays_visible_separately_from_invalid_values():
    checked=inspect_frame(source(),'2026-09-25')
    assert not checked['errors']
    assert checked['full_110_session_quality_history'] is False
