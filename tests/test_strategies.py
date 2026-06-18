"""Tests that each strategy registers, runs through the engine, and trades when it should."""

import numpy as np
import pytest

from conftest import make_ohlcv
from trading_bot.backtest.engine import BacktestConfig, run_backtest
from trading_bot.strategies import available_strategies, get_strategy
from trading_bot.strategies.ma_crossover import MovingAverageCrossover
from trading_bot.strategies.mean_reversion import MeanReversion
from trading_bot.strategies.pairs import PairsTrading
from trading_bot.strategies.rsi import RSIStrategy

CONFIG = BacktestConfig(starting_cash=10_000.0, commission_pct=0.0, slippage_pct=0.0)


def test_registry_has_all_four():
    assert set(available_strategies()) == {"ma_crossover", "mean_reversion", "rsi", "pairs"}
    assert get_strategy("rsi") is RSIStrategy


def test_ma_crossover_enters_on_golden_cross():
    # Decline then sustained rise -> short EMA crosses above long EMA -> a long entry.
    prices = [20, 18, 16, 14, 12, 10, 12, 15, 18, 21, 24, 27, 30, 33]
    data = {"X": make_ohlcv(prices)}
    strat = MovingAverageCrossover("X", short_window=2, long_window=4, ma_type="ema")
    res = run_backtest(strat, data, CONFIG)
    assert (res.positions["X"] > 0).any()  # went long at some point


def test_mean_reversion_trades_on_dip():
    prices = [100.0] * 20 + [90.0] + [100.0] * 10
    data = {"X": make_ohlcv(prices)}
    strat = MeanReversion("X", window=5, entry_z=2.0, exit_z=0.0, allow_short=False)
    res = run_backtest(strat, data, CONFIG)
    assert res.report.trades.num_trades >= 1


def test_rsi_trades_on_oversold_then_recovery():
    prices = [100, 100, 100, 95, 90, 85, 80, 78, 85, 92, 98, 104, 110]
    data = {"X": make_ohlcv(prices)}
    strat = RSIStrategy("X", window=3, oversold=30, exit_level=50, allow_short=False)
    res = run_backtest(strat, data, CONFIG)
    assert res.report.trades.num_trades >= 1


def test_pairs_runs_and_computes_adf():
    rng = np.random.default_rng(7)
    a = 100 + np.cumsum(rng.normal(0, 1, 250))
    noise = rng.normal(0, 0.5, 250)
    b = 50 + 0.5 * (a - 100) + noise  # cointegrated with A (beta ~ 0.5)
    data = {"A": make_ohlcv(a), "B": make_ohlcv(b)}
    strat = PairsTrading("A", "B", lookback=30, z_window=30, entry_z=1.5, exit_z=0.3)
    res = run_backtest(strat, data, CONFIG)
    assert len(res.equity_curve) == 250
    # ADF descriptive stat was computed for the lesson display.
    assert strat.adf_stat is not None and strat.adf_pvalue is not None
    # A genuinely cointegrated pair should look stationary (low ADF p-value).
    assert strat.adf_pvalue < 0.1


def test_pairs_holds_both_legs():
    # Construct a clean divergence so we know the strategy must open a spread position.
    rng = np.random.default_rng(1)
    a = 100 + np.cumsum(rng.normal(0, 0.5, 200))
    b = a.copy()
    b[120:140] += 8.0  # B diverges sharply -> spread blows out -> a trade must open
    data = {"A": make_ohlcv(a), "B": make_ohlcv(b)}
    strat = PairsTrading("A", "B", lookback=30, z_window=30, entry_z=1.5, exit_z=0.3)
    res = run_backtest(strat, data, CONFIG)
    assert (res.positions["A"] != 0).any() and (res.positions["B"] != 0).any()
