"""Alpaca broker adapter for paper and live trading.

The SAME code path serves paper and live: only the ``paper`` flag (from ``ALPACA_PAPER``)
changes the endpoint. Learn and validate on paper (fake money, real-time data), then flip
the flag for live -- but wrap this in a ``RiskGuard`` first.
"""

from __future__ import annotations

from trading_bot.broker.base import (
    Account,
    Broker,
    OrderResult,
    OrderSide,
    Position,
)
from trading_bot.config import Settings, get_settings


class AlpacaBroker(Broker):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.settings.require_alpaca()
        from alpaca.trading.client import TradingClient

        self._paper = self.settings.alpaca_paper
        self._client = TradingClient(
            self.settings.alpaca_api_key,
            self.settings.alpaca_secret_key,
            paper=self._paper,
        )

    @property
    def is_paper(self) -> bool:
        return self._paper

    def get_account(self) -> Account:
        a = self._client.get_account()
        return Account(
            cash=float(a.cash),
            equity=float(a.equity),
            buying_power=float(a.buying_power),
            is_paper=self._paper,
            pattern_day_trader=bool(getattr(a, "pattern_day_trader", False)),
            daytrade_count=int(getattr(a, "daytrade_count", 0) or 0),
        )

    def get_positions(self) -> list[Position]:
        out = []
        for p in self._client.get_all_positions():
            out.append(
                Position(
                    symbol=p.symbol,
                    qty=float(p.qty),
                    avg_entry_price=float(p.avg_entry_price),
                    market_value=float(p.market_value),
                    unrealized_pl=float(p.unrealized_pl),
                )
            )
        return out

    def submit_market_order(
        self, symbol: str, qty: float, side: OrderSide, reference_price: float | None = None
    ) -> OrderResult:
        from alpaca.trading.enums import OrderSide as AlpacaSide
        from alpaca.trading.enums import TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        req = MarketOrderRequest(
            symbol=symbol,
            qty=abs(qty),
            side=AlpacaSide.BUY if side == OrderSide.BUY else AlpacaSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        order = self._client.submit_order(req)
        return OrderResult(
            id=str(order.id),
            symbol=symbol,
            qty=abs(qty),
            side=side,
            status=str(order.status),
        )

    def close_position(self, symbol: str) -> None:
        self._client.close_position(symbol)

    def is_market_open(self) -> bool:
        return bool(self._client.get_clock().is_open)
