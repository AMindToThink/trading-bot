"""Yahoo Finance data source (via the ``yfinance`` package).

Use for FREE long-range DAILY history in backtests. Caveats, stated honestly:
  * It scrapes undocumented Yahoo endpoints and can break or rate-limit without notice.
  * Intraday history is severely limited (1-minute only ~7 days back).
  * Quotes are typically ~15 minutes delayed.
So: great for multi-year daily backtests, but NEVER on the live/real-money path. Use the
Alpaca source for anything real-time.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from trading_bot.data.base import DataSource, normalize_ohlcv

# yfinance interval strings keyed by our canonical timeframe names.
_INTERVALS = {
    "1Day": "1d",
    "1Hour": "1h",
    "1Min": "1m",
    "5Min": "5m",
    "15Min": "15m",
}


class YahooDataSource(DataSource):
    def get_bars(
        self,
        symbol: str,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        timeframe: str = "1Day",
        period: str = "2y",
    ) -> pd.DataFrame:
        import yfinance as yf

        interval = _INTERVALS.get(timeframe, "1d")
        ticker = yf.Ticker(symbol)
        df = ticker.history(
            start=start,
            end=end,
            period=None if start else period,
            interval=interval,
            auto_adjust=True,  # split/dividend-adjusted prices for honest backtests
        )
        if df.empty:
            raise ValueError(f"Yahoo returned no data for {symbol!r} ({timeframe}).")
        return normalize_ohlcv(df)
