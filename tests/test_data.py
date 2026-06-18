"""Tests for data normalization and credential guarding (no network calls)."""

import pandas as pd
import pytest

from trading_bot.config import Settings
from trading_bot.data.base import normalize_ohlcv


def test_normalize_lowercases_and_selects_columns():
    raw = pd.DataFrame(
        {
            "Open": [1.0, 2.0],
            "High": [2.0, 3.0],
            "Low": [0.5, 1.5],
            "Close": [1.5, 2.5],
            "Volume": [100, 200],
            "Dividends": [0.0, 0.0],  # extraneous yfinance column, dropped
        },
        index=pd.to_datetime(["2020-01-02", "2020-01-01"]),  # out of order
    )
    out = normalize_ohlcv(raw)
    assert list(out.columns) == ["open", "high", "low", "close", "volume"]
    assert out.index.is_monotonic_increasing  # sorted ascending
    assert out["close"].dtype == float


def test_normalize_raises_on_missing_columns():
    raw = pd.DataFrame({"Open": [1.0], "Close": [1.0]})
    with pytest.raises(ValueError, match="missing required columns"):
        normalize_ohlcv(raw)


def test_normalize_drops_duplicate_timestamps():
    idx = pd.to_datetime(["2020-01-01", "2020-01-01"])
    raw = pd.DataFrame(
        {"open": [1, 9], "high": [1, 9], "low": [1, 9], "close": [1, 9], "volume": [1, 9]},
        index=idx,
    )
    out = normalize_ohlcv(raw)
    assert len(out) == 1
    assert out["close"].iloc[0] == 9  # keeps last


def test_alpaca_source_requires_credentials():
    from trading_bot.data.alpaca import AlpacaDataSource

    empty = Settings(None, None, alpaca_paper=True, alpaca_data_feed="iex")
    with pytest.raises(RuntimeError, match="Alpaca credentials missing"):
        AlpacaDataSource(empty)
