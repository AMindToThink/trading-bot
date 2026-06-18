"""Data-source interface.

Every data source returns a *normalized* OHLCV DataFrame: a sorted ``DatetimeIndex`` and
exactly the columns ``open, high, low, close, volume`` (lowercase, float). The backtester
and strategies depend only on this shape, so sources are interchangeable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce an arbitrary OHLCV frame to the canonical shape, failing loudly if columns
    are missing."""
    rename = {c: c.lower() for c in df.columns}
    out = df.rename(columns=rename)
    missing = [c for c in OHLCV_COLUMNS if c not in out.columns]
    if missing:
        raise ValueError(f"data missing required columns {missing}; got {list(out.columns)}")
    out = out[OHLCV_COLUMNS].astype(float)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out.dropna(how="any")


class DataSource(ABC):
    """Abstract source of historical OHLCV bars."""

    @abstractmethod
    def get_bars(
        self,
        symbol: str,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        timeframe: str = "1Day",
    ) -> pd.DataFrame:
        """Return a normalized OHLCV DataFrame for ``symbol``."""

    def get_bars_multi(
        self,
        symbols: list[str],
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        timeframe: str = "1Day",
    ) -> dict[str, pd.DataFrame]:
        """Fetch several symbols, returning ``symbol -> DataFrame``."""
        return {s: self.get_bars(s, start, end, timeframe) for s in symbols}
