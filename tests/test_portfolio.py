"""Unit tests for portfolio accounting, fills, costs, and realized P&L."""

import pytest

from trading_bot.backtest.portfolio import Portfolio


def test_buy_then_sell_realizes_pnl_no_costs():
    pf = Portfolio(10_000.0)
    pf.fill("X", 10, 100.0)
    assert pf.cash == pytest.approx(9_000.0)
    assert pf.position("X") == 10
    assert pf.avg_cost["X"] == pytest.approx(100.0)

    pf.fill("X", -10, 110.0)
    assert pf.position("X") == 0
    assert pf.cash == pytest.approx(10_100.0)
    assert pf.realized_trade_pnls == [pytest.approx(100.0)]  # (110-100)*10


def test_commission_and_slippage_reduce_pnl():
    pf = Portfolio(10_000.0, commission_pct=0.001, slippage_pct=0.01)
    pf.fill("X", 10, 100.0)  # buy: exec 101, commission 0.001*1010 = 1.01
    # cash = 10000 - 10*101 - 1.01
    assert pf.cash == pytest.approx(10_000.0 - 1010.0 - 1.01)
    assert pf.avg_cost["X"] == pytest.approx(101.0)

    pf.fill("X", -10, 110.0)  # sell: exec 108.9, commission 0.001*1089 = 1.089
    # realized = (108.9 - 101)*10 - 1.089
    assert pf.realized_trade_pnls[0] == pytest.approx((108.9 - 101.0) * 10 - 1.089)


def test_short_then_cover_realizes_pnl():
    pf = Portfolio(10_000.0)
    pf.fill("X", -10, 100.0)  # short at 100
    assert pf.position("X") == -10
    pf.fill("X", 10, 90.0)  # cover at 90 -> profit
    assert pf.realized_trade_pnls == [pytest.approx(100.0)]  # (90-100)*10*sign(-1) = +100


def test_average_cost_on_scaling_in():
    pf = Portfolio(10_000.0)
    pf.fill("X", 10, 100.0)
    pf.fill("X", 10, 120.0)
    assert pf.avg_cost["X"] == pytest.approx(110.0)  # (1000 + 1200)/20


def test_equity_marks_to_market():
    pf = Portfolio(10_000.0)
    pf.fill("X", 10, 100.0)  # cash 9000, 10 shares
    assert pf.equity({"X": 130.0}) == pytest.approx(9_000.0 + 10 * 130.0)
