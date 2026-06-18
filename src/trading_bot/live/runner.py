"""Live / paper trading runner.

Reuses the EXACT same ``Strategy`` objects as the backtester. The trick is ``LiveContext``:
it exposes the same methods a strategy calls in a backtest (``position``, ``price``,
``equity``, ``order_target_percent``, ...), but instead of queuing fills for a simulated
next bar, it sends market orders to a real broker.

Decision cycle (``run_once``): pull recent bars -> ``strategy.prepare(...)`` -> call
``strategy.on_bar(last_index, ctx)``. Orders go out immediately as market orders, sized
from live account equity and the latest price, and pass through the broker's ``RiskGuard``.

This runner intentionally trades on the last CLOSED bar to avoid acting on a partial,
still-forming bar -- the live analogue of the backtester's look-ahead guard.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from trading_bot.broker.base import Broker, OrderSide
from trading_bot.data.base import DataSource
from trading_bot.strategies.base import Strategy


class LiveContext:
    """Strategy-facing context that routes orders to a live broker."""

    def __init__(self, broker: Broker, prices: dict[str, float], whole_shares: bool = True) -> None:
        self._broker = broker
        self._prices = prices
        self._whole_shares = whole_shares
        account = broker.get_account()
        self._equity = account.equity
        self._positions = {p.symbol: p.qty for p in broker.get_positions()}

    # --- read side ---------------------------------------------------------------------
    def price(self, symbol: str) -> float:
        return self._prices[symbol]

    def position(self, symbol: str) -> float:
        return self._positions.get(symbol, 0.0)

    def equity(self) -> float:
        return self._equity

    # --- order side --------------------------------------------------------------------
    def order(self, symbol: str, qty: float) -> None:
        if self._whole_shares:
            qty = float(int(qty))
        if qty == 0:
            return
        side = OrderSide.BUY if qty > 0 else OrderSide.SELL
        price = self._prices.get(symbol)
        self._broker.submit_market_order(symbol, abs(qty), side, reference_price=price)
        self._positions[symbol] = self._positions.get(symbol, 0.0) + qty

    def order_target_shares(self, symbol: str, target: float) -> None:
        self.order(symbol, target - self.position(symbol))

    def order_target_percent(self, symbol: str, pct: float) -> None:
        price = self._prices.get(symbol)
        if not price or price <= 0:
            return
        self.order_target_shares(symbol, pct * self._equity / price)

    def close_position(self, symbol: str) -> None:
        self.order_target_shares(symbol, 0.0)


class LiveTrader:
    def __init__(self, strategy: Strategy, broker: Broker, data: DataSource) -> None:
        self.strategy = strategy
        self.broker = broker
        self.data = data

    def _recent_bars(self, lookback_days: int, timeframe: str) -> dict[str, "object"]:
        start = datetime.utcnow() - timedelta(days=lookback_days)
        return {
            sym: self.data.get_bars(sym, start=start, timeframe=timeframe)
            for sym in self.strategy.required_symbols()
        }

    def run_once(self, lookback_days: int = 120, timeframe: str = "1Day") -> None:
        """Run a single decision cycle on the most recent closed bar."""
        bars = self._recent_bars(lookback_days, timeframe)
        # Align to common timestamps (mirrors the backtester).
        common = None
        for df in bars.values():
            common = df.index if common is None else common.intersection(df.index)
        bars = {s: df.loc[common] for s, df in bars.items()}

        self.strategy.prepare(bars)
        last = len(common) - 1
        prices = {s: float(df["close"].iloc[-1]) for s, df in bars.items()}
        ctx = LiveContext(self.broker, prices)
        self.strategy.on_bar(last, ctx)

    def run_forever(
        self, poll_seconds: int = 60, lookback_days: int = 120, timeframe: str = "1Day"
    ) -> None:  # pragma: no cover - long-running loop
        """Poll on an interval, trading only while the market is open."""
        while True:
            if self.broker.is_market_open():
                try:
                    self.run_once(lookback_days, timeframe)
                except Exception as exc:  # log and keep the loop alive
                    print(f"[live] decision cycle error: {exc!r}")
            time.sleep(poll_seconds)
