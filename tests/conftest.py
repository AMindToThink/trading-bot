"""Shared test helpers."""

import numpy as np
import pandas as pd


def make_ohlcv(close, *, open_=None, start="2020-01-01", freq="D") -> pd.DataFrame:
    """Build an OHLCV DataFrame from a close-price array.

    By default open == close (handy for deterministic fill tests). High/low bracket the
    bar and volume is constant; the engine only reads open and close.
    """
    close = np.asarray(close, dtype=float)
    open_ = close if open_ is None else np.asarray(open_, dtype=float)
    idx = pd.date_range(start=start, periods=len(close), freq=freq)
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) * 1.001,
            "low": np.minimum(open_, close) * 0.999,
            "close": close,
            "volume": np.full(len(close), 1_000_000.0),
        },
        index=idx,
    )
