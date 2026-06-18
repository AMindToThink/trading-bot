"""Alpaca data source: historical bars + real-time IEX stream.

This is the PRIMARY source for the bot: it is an official, documented, ToS-clean API that
gives both historical 1-minute bars (for backtesting) and a real-time websocket stream,
tied to the same account you (paper-)trade with. On the free plan, quotes/bars come from
the IEX venue only -- a single exchange, not the full consolidated SIP tape. That is an
honest limitation we surface to users rather than hide.
"""

from __future__ import annotations

from datetime import datetime
from typing import Awaitable, Callable

import pandas as pd

from trading_bot.config import Settings, get_settings
from trading_bot.data.base import DataSource, normalize_ohlcv


def _timeframe(name: str):
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    mapping = {
        "1Day": TimeFrame.Day,
        "1Hour": TimeFrame.Hour,
        "1Min": TimeFrame.Minute,
        "5Min": TimeFrame(5, TimeFrameUnit.Minute),
        "15Min": TimeFrame(15, TimeFrameUnit.Minute),
    }
    if name not in mapping:
        raise ValueError(f"unsupported timeframe {name!r}; choose from {list(mapping)}")
    return mapping[name]


class AlpacaDataSource(DataSource):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.settings.require_alpaca()
        self._feed = self.settings.alpaca_data_feed

    def _client(self):
        from alpaca.data.historical import StockHistoricalDataClient

        return StockHistoricalDataClient(
            self.settings.alpaca_api_key, self.settings.alpaca_secret_key
        )

    def get_bars(
        self,
        symbol: str,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        timeframe: str = "1Day",
    ) -> pd.DataFrame:
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockBarsRequest

        feed = DataFeed.SIP if self._feed == "sip" else DataFeed.IEX
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=_timeframe(timeframe),
            start=start,
            end=end,
            feed=feed,
        )
        bars = self._client().get_stock_bars(request)
        df = bars.df
        if df.empty:
            raise ValueError(f"Alpaca returned no {timeframe} bars for {symbol!r}.")
        # bars.df is a (symbol, timestamp) MultiIndex; drop the symbol level.
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol, level="symbol")
        return normalize_ohlcv(df)


class AlpacaStream:
    """Thin wrapper over Alpaca's real-time IEX websocket.

    Example::

        stream = AlpacaStream()
        stream.on_bar(my_async_handler, "AAPL", "MSFT")
        stream.run()   # blocks; runs the asyncio event loop
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.settings.require_alpaca()
        from alpaca.data.enums import DataFeed
        from alpaca.data.live import StockDataStream

        feed = DataFeed.SIP if self.settings.alpaca_data_feed == "sip" else DataFeed.IEX
        self._stream = StockDataStream(
            self.settings.alpaca_api_key, self.settings.alpaca_secret_key, feed=feed
        )

    def on_bar(self, handler: Callable[[object], Awaitable[None]], *symbols: str) -> None:
        self._stream.subscribe_bars(handler, *symbols)

    def on_quote(self, handler: Callable[[object], Awaitable[None]], *symbols: str) -> None:
        self._stream.subscribe_quotes(handler, *symbols)

    def run(self) -> None:
        self._stream.run()

    async def stop(self) -> None:
        await self._stream.stop_ws()
