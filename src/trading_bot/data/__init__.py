"""Market-data sources."""

from trading_bot.data.base import DataSource, OHLCV_COLUMNS, normalize_ohlcv
from trading_bot.data.yahoo import YahooDataSource

__all__ = [
    "DataSource",
    "OHLCV_COLUMNS",
    "normalize_ohlcv",
    "YahooDataSource",
    "get_data_source",
]


def get_data_source(name: str = "yahoo") -> DataSource:
    """Factory: ``"yahoo"`` (free daily, no key) or ``"alpaca"`` (IEX, needs keys)."""
    if name == "yahoo":
        return YahooDataSource()
    if name == "alpaca":
        from trading_bot.data.alpaca import AlpacaDataSource

        return AlpacaDataSource()
    raise ValueError(f"unknown data source {name!r}; choose 'yahoo' or 'alpaca'")
