"""Unit tests for the event-driven backtest engine, including look-ahead safety."""

import pytest

from conftest import make_ohlcv
from trading_bot.backtest.engine import BacktestConfig, run_backtest
from trading_bot.strategies.base import Strategy


class BuyAndHoldOnce(Strategy):
    """Test strategy: invest 100% of equity on the very first bar, then hold."""

    name = "Buy and Hold (test)"

    def __init__(self, symbol="X"):
        self.symbol = symbol
        self._done = False

    def required_symbols(self):
        return [self.symbol]

    def on_bar(self, t, ctx):
        if not self._done:
            ctx.order_target_percent(self.symbol, 1.0)
            self._done = True


def _zero_cost_config():
    return BacktestConfig(
        starting_cash=10_000.0, commission_pct=0.0, slippage_pct=0.0, periods_per_year=252
    )


def test_order_fills_next_bar_not_same_bar():
    # open == close == 100 for the first two bars, then 110.
    data = {"X": make_ohlcv([100.0, 100.0, 110.0, 110.0])}
    res = run_backtest(BuyAndHoldOnce(), data, _zero_cost_config())
    eq = res.equity_curve
    # Decision at t=0 (close 100) must NOT be filled until t=1's open -> still all cash at t=0.
    assert eq.iloc[0] == pytest.approx(10_000.0)
    # Filled at t=1 open (100): 100 shares. Marked at close 100 -> still 10000.
    assert eq.iloc[1] == pytest.approx(10_000.0)
    assert res.positions["X"].iloc[1] == pytest.approx(100.0)
    # t=2 close 110 -> 100 * 110 = 11000.
    assert eq.iloc[2] == pytest.approx(11_000.0)
    assert res.report.total_return == pytest.approx(0.10)


def test_constant_price_zero_cost_preserves_equity():
    data = {"X": make_ohlcv([100.0] * 10)}
    res = run_backtest(BuyAndHoldOnce(), data, _zero_cost_config())
    assert res.equity_curve.iloc[-1] == pytest.approx(10_000.0)
    assert res.report.max_drawdown == pytest.approx(0.0)


def test_costs_reduce_equity():
    data = {"X": make_ohlcv([100.0] * 10)}
    costly = BacktestConfig(starting_cash=10_000.0, commission_pct=0.001, slippage_pct=0.001)
    res = run_backtest(BuyAndHoldOnce(), data, costly)
    # A single buy with costs must leave us below the starting equity on flat prices.
    assert res.equity_curve.iloc[-1] < 10_000.0


def test_missing_symbol_raises():
    data = {"Y": make_ohlcv([100.0] * 5)}
    with pytest.raises(ValueError):
        run_backtest(BuyAndHoldOnce("X"), data, _zero_cost_config())


def test_alignment_intersects_indices():
    a = make_ohlcv([1.0, 2.0, 3.0, 4.0], start="2020-01-01")
    b = make_ohlcv([1.0, 2.0, 3.0], start="2020-01-02")  # starts one day later
    from trading_bot.backtest.engine import _align

    aligned = _align({"A": a, "B": b})
    assert len(aligned["A"]) == len(aligned["B"]) == 3
    assert (aligned["A"].index == aligned["B"].index).all()
