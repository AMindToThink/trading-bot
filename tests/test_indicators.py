"""Unit tests for indicators, checked against hand-computed values."""

import numpy as np
import pandas as pd
import pytest

from trading_bot.indicators import (
    bollinger_bands,
    ema,
    rolling_std,
    rsi,
    sma,
    zscore,
)


def test_sma_basic():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = sma(s, 3)
    # first two are NaN, then means of consecutive triples
    assert np.isnan(out.iloc[0]) and np.isnan(out.iloc[1])
    assert out.iloc[2] == pytest.approx(2.0)
    assert out.iloc[3] == pytest.approx(3.0)
    assert out.iloc[4] == pytest.approx(4.0)


def test_ema_recursion_alpha_2_over_n_plus_1():
    # N=2 -> alpha = 2/3, seeded at EMA_0 = P_0
    s = pd.Series([1.0, 2.0, 3.0])
    out = ema(s, 2)
    assert out.iloc[0] == pytest.approx(1.0)
    assert out.iloc[1] == pytest.approx(5.0 / 3.0)       # 2/3*2 + 1/3*1
    assert out.iloc[2] == pytest.approx(23.0 / 9.0)      # 2/3*3 + 1/3*(5/3)


def test_rolling_std_population_vs_sample():
    s = pd.Series([1.0, 2.0, 3.0])
    pop = rolling_std(s, 3, population=True).iloc[-1]
    samp = rolling_std(s, 3, population=False).iloc[-1]
    assert pop == pytest.approx(np.sqrt(2.0 / 3.0))      # divisor N=3
    assert samp == pytest.approx(1.0)                    # divisor N-1=2


def test_bollinger_bands_and_zscore():
    s = pd.Series([1.0, 2.0, 3.0])
    bb = bollinger_bands(s, window=3, num_std=2.0, population=True)
    sd = np.sqrt(2.0 / 3.0)
    assert bb["mid"].iloc[-1] == pytest.approx(2.0)
    assert bb["upper"].iloc[-1] == pytest.approx(2.0 + 2.0 * sd)
    assert bb["lower"].iloc[-1] == pytest.approx(2.0 - 2.0 * sd)
    # touching neither band yet; z = (3 - 2)/sd
    assert bb["zscore"].iloc[-1] == pytest.approx(1.0 / sd)
    # standalone zscore agrees with the bollinger column
    z = zscore(s, 3, population=True)
    assert z.iloc[-1] == pytest.approx(bb["zscore"].iloc[-1])


def test_zscore_at_band_equals_k():
    # When price sits exactly k std above the mean, z == +k by construction.
    s = pd.Series([10.0, 10.0, 16.0])  # mean of last 3 = 12, pop std = 2.8284
    z = zscore(s, 3, population=True).iloc[-1]
    sd = np.sqrt(((10 - 12) ** 2 + (10 - 12) ** 2 + (16 - 12) ** 2) / 3)
    assert z == pytest.approx((16 - 12) / sd)


def test_rsi_window2_handcomputed():
    s = pd.Series([10.0, 11.0, 10.0, 11.0, 12.0])
    out = rsi(s, window=2)
    assert np.isnan(out.iloc[0]) and np.isnan(out.iloc[1])
    assert out.iloc[2] == pytest.approx(50.0)
    assert out.iloc[3] == pytest.approx(75.0)
    assert out.iloc[4] == pytest.approx(87.5)


def test_rsi_all_gains_is_100():
    s = pd.Series(np.arange(1.0, 30.0))  # strictly increasing
    out = rsi(s, window=14)
    assert out.dropna().iloc[-1] == pytest.approx(100.0)


def test_rsi_all_losses_is_0():
    s = pd.Series(np.arange(30.0, 1.0, -1.0))  # strictly decreasing
    out = rsi(s, window=14)
    assert out.dropna().iloc[-1] == pytest.approx(0.0)


def test_rsi_bounded_0_100():
    rng = np.random.default_rng(0)
    s = pd.Series(100 + np.cumsum(rng.normal(0, 1, 500)))
    out = rsi(s, window=14).dropna()
    assert (out >= 0).all() and (out <= 100).all()


def test_indicators_no_lookahead():
    # The value at t must not change when future data is appended.
    s = pd.Series(100 + np.cumsum(np.random.default_rng(1).normal(0, 1, 100)))
    full = rsi(s, 14)
    truncated = rsi(s.iloc[:60], 14)
    pd.testing.assert_series_equal(full.iloc[:60], truncated, check_names=False)
