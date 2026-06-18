"""Portfolio accounting for the backtester: cash, positions, costs, and realized P&L.

Cost model (all configurable, all applied at fill time):
  * slippage: the fill price is pushed against you by ``slippage_pct`` (buys pay more,
    sells receive less) -- a simple stand-in for crossing the bid/ask spread and market
    impact.
  * commission: ``commission_per_share * |qty| + commission_pct * notional``.

Realized P&L is tracked with an average-cost basis. When a fill reduces or flips a
position, we realize P&L on the closed portion and record it as one "trade" for
trade-level statistics (win rate, profit factor, expectancy). Commission on the closing
fill is subtracted from that trade's P&L so the statistics reflect costs.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def _sign(x: float) -> int:
    return int(x > 0) - int(x < 0)


@dataclass
class Portfolio:
    starting_cash: float
    commission_per_share: float = 0.0
    commission_pct: float = 0.0
    slippage_pct: float = 0.0

    cash: float = field(init=False)
    positions: dict[str, float] = field(default_factory=dict)
    avg_cost: dict[str, float] = field(default_factory=dict)
    realized_trade_pnls: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cash = float(self.starting_cash)

    def position(self, symbol: str) -> float:
        return self.positions.get(symbol, 0.0)

    def _commission(self, qty: float, exec_price: float) -> float:
        return abs(qty) * self.commission_per_share + abs(qty * exec_price) * self.commission_pct

    def fill(self, symbol: str, qty: float, raw_price: float) -> None:
        """Execute a market order for ``qty`` signed shares at a raw price.

        ``qty > 0`` buys, ``qty < 0`` sells/shorts. Slippage and commission are applied
        here. Realized P&L is booked when the trade reduces or flips the position.
        """
        if qty == 0:
            return

        # Slippage pushes the fill price against the trader.
        exec_price = raw_price * (1.0 + self.slippage_pct) if qty > 0 else raw_price * (
            1.0 - self.slippage_pct
        )
        commission = self._commission(qty, exec_price)

        cur = self.positions.get(symbol, 0.0)
        new = cur + qty

        if cur == 0 or _sign(cur) == _sign(qty):
            # Opening or adding in the same direction -> update weighted-average cost.
            total = self.avg_cost.get(symbol, 0.0) * abs(cur) + exec_price * abs(qty)
            self.avg_cost[symbol] = total / abs(new) if new != 0 else 0.0
        else:
            # Reducing or flipping -> realize P&L on the closed portion.
            closed = min(abs(qty), abs(cur))
            entry = self.avg_cost.get(symbol, exec_price)
            pnl = (exec_price - entry) * closed * _sign(cur) - commission
            self.realized_trade_pnls.append(pnl)
            if abs(qty) > abs(cur):
                # Position flipped through zero; the remainder opens a new position.
                self.avg_cost[symbol] = exec_price
            elif new == 0:
                self.avg_cost.pop(symbol, None)
            # (if merely reduced, avg cost of the remaining shares is unchanged)

        # Cash: buying spends cash, selling raises it; commission always costs cash.
        self.cash -= qty * exec_price
        self.cash -= commission
        if new == 0:
            self.positions.pop(symbol, None)
        else:
            self.positions[symbol] = new

    def market_value(self, prices: dict[str, float]) -> float:
        """Total value of open positions marked at the given prices."""
        return sum(shares * prices[sym] for sym, shares in self.positions.items())

    def equity(self, prices: dict[str, float]) -> float:
        """Total account equity = cash + marked-to-market positions."""
        return self.cash + self.market_value(prices)
