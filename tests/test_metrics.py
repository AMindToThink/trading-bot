"""Unit tests for performance metrics, checked against hand-computed values."""

import numpy as np
import pandas as pd
import pytest

from trading_bot.backtest.metrics import (
    annualized_volatility,
    cagr,
    drawdown_series,
    max_drawdown,
    performance_report,
    sharpe_ratio,
    sortino_ratio,
    total_return,
    trade_stats,
)


def test_total_return():
    eq = pd.Series([100.0, 105.0, 110.0])
    assert total_return(eq) == pytest.approx(0.10)


def test_cagr_geometric():
    # 100 -> 121 over 2 periods at 1 period/year -> 2 years -> sqrt(1.21)-1 = 0.10
    eq = pd.Series([100.0, 110.0, 121.0])
    assert cagr(eq, periods_per_year=1) == pytest.approx(0.10)


def test_max_drawdown():
    eq = pd.Series([100.0, 120.0, 90.0, 110.0])
    # running peak 120; trough 90 -> 90/120 - 1 = -0.25
    assert max_drawdown(eq) == pytest.approx(-0.25)
    dd = drawdown_series(eq)
    assert dd.iloc[1] == pytest.approx(0.0)
    assert dd.iloc[2] == pytest.approx(-0.25)


def test_sharpe_annualization_scaling():
    # Annualized Sharpe must equal per-period Sharpe * sqrt(P).
    rets = pd.Series([0.01, -0.005, 0.02, 0.0, 0.015, -0.01])
    per_period = sharpe_ratio(rets, risk_free_rate=0.0, periods_per_year=1)
    annual = sharpe_ratio(rets, risk_free_rate=0.0, periods_per_year=252)
    assert annual == pytest.approx(per_period * np.sqrt(252))


def test_sharpe_zero_vol_is_nan():
    rets = pd.Series([0.01, 0.01, 0.01])
    assert np.isnan(sharpe_ratio(rets))


def test_sortino_handcomputed():
    rets = pd.Series([0.1, -0.05, 0.1, -0.05])
    # mean = 0.025; downside dev = sqrt((0.05^2 + 0.05^2)/4) = sqrt(0.00125)
    dd = np.sqrt((0.05**2 + 0.05**2) / 4)
    expected = 0.025 / dd  # periods_per_year=1
    assert sortino_ratio(rets, mar=0.0, periods_per_year=1) == pytest.approx(expected)


def test_sortino_divides_by_full_n_not_loss_count():
    # Two losers, two winners. Downside denominator must use N=4, not 2.
    rets = pd.Series([0.1, -0.05, 0.1, -0.05])
    full_n = np.sqrt((0.05**2 + 0.05**2) / 4)
    loss_only = np.sqrt((0.05**2 + 0.05**2) / 2)
    got = sortino_ratio(rets, mar=0.0, periods_per_year=1)
    assert got == pytest.approx(0.025 / full_n)
    assert got != pytest.approx(0.025 / loss_only)


def test_annualized_volatility_scaling():
    rets = pd.Series([0.01, -0.02, 0.015, 0.0])
    assert annualized_volatility(rets, 252) == pytest.approx(rets.std(ddof=1) * np.sqrt(252))


def test_trade_stats_handcomputed():
    pnls = [100.0, -50.0, 200.0, -50.0, -25.0]
    ts = trade_stats(pnls)
    assert ts.num_trades == 5
    assert ts.win_rate == pytest.approx(0.4)
    assert ts.avg_win == pytest.approx(150.0)
    assert ts.avg_loss == pytest.approx(125.0 / 3)
    assert ts.profit_factor == pytest.approx(300.0 / 125.0)
    # expectancy equals the mean P&L per trade
    assert ts.expectancy == pytest.approx(np.mean(pnls))


def test_trade_stats_all_wins_infinite_profit_factor():
    ts = trade_stats([10.0, 20.0, 30.0])
    assert ts.profit_factor == float("inf")
    assert ts.win_rate == 1.0


def test_performance_report_bundles_everything():
    eq = pd.Series(100 * np.cumprod(1 + np.random.default_rng(0).normal(0.0005, 0.01, 300)))
    rep = performance_report(eq, trade_pnls=[10.0, -5.0, 8.0], periods_per_year=252)
    d = rep.to_dict()
    for key in ("total_return", "cagr", "sharpe_ratio", "sortino_ratio", "max_drawdown"):
        assert key in d
    assert d["trades"]["num_trades"] == 3
