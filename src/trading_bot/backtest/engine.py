"""Event-driven backtester.

The loop is deliberately simple and explicit so the mechanics are easy to learn:

    for t in range(N):
        1. fill orders that were decided on the PREVIOUS bar, at THIS bar's open
        2. ask the strategy to decide, using data only up to THIS bar's close
        3. mark the portfolio to market at this bar's close and record equity

Because a decision made at the close of bar ``t`` is queued and only filled at the open of
bar ``t+1``, the backtester cannot "trade on information it would not yet have." That is
the structural guarantee against look-ahead bias -- the most common way backtests lie.

The engine is multi-asset (positions are a dict keyed by symbol), which is what lets the
pairs-trading strategy hold two legs at once.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from trading_bot.backtest.metrics import PerformanceReport, performance_report
from trading_bot.backtest.portfolio import Portfolio
from trading_bot.strategies.base import Strategy


@dataclass
class BacktestConfig:
    starting_cash: float = 100_000.0
    commission_per_share: float = 0.0
    commission_pct: float = 0.0005  # 5 bps per trade, a reasonable retail-ish default
    slippage_pct: float = 0.0005  # 5 bps adverse fill
    periods_per_year: int = 252  # set to 252*bars_per_session for intraday bars
    risk_free_rate: float = 0.0  # per-period


@dataclass
class Context:
    """Handed to ``Strategy.on_bar``. Lets a strategy read the present and queue orders.

    Orders queued here are market orders filled at the NEXT bar's open. Position sizing
    helpers use the current bar's close as the best available price estimate (you do not
    yet know the next open when you decide)."""

    t: int
    timestamp: pd.Timestamp
    portfolio: Portfolio
    config: BacktestConfig
    _closes: dict[str, float]
    _pending: dict[str, float] = field(default_factory=dict)

    def price(self, symbol: str) -> float:
        """Latest known price (this bar's close)."""
        return self._closes[symbol]

    def position(self, symbol: str) -> float:
        return self.portfolio.position(symbol)

    def equity(self) -> float:
        return self.portfolio.equity(self._closes)

    def order(self, symbol: str, qty: float) -> None:
        """Queue a market order for ``qty`` signed shares (filled next bar's open)."""
        self._pending[symbol] = self._pending.get(symbol, 0.0) + qty

    def order_target_shares(self, symbol: str, target: float) -> None:
        """Queue an order to reach ``target`` total shares for ``symbol``."""
        self.order(symbol, target - self.position(symbol))

    def order_target_percent(self, symbol: str, pct: float) -> None:
        """Queue an order so the position becomes ``pct`` of current equity.

        ``pct`` may be negative (short). Sized using the current close.
        """
        price = self._closes[symbol]
        if price <= 0:
            return
        target_shares = pct * self.equity() / price
        self.order_target_shares(symbol, target_shares)

    def close_position(self, symbol: str) -> None:
        self.order_target_shares(symbol, 0.0)


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    report: PerformanceReport
    positions: pd.DataFrame  # shares held per symbol over time
    config: BacktestConfig
    strategy_name: str


def _align(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Restrict all symbols to their common timestamps so bars line up across assets."""
    if not data:
        raise ValueError("no data provided")
    common = None
    for df in data.values():
        idx = df.index
        common = idx if common is None else common.intersection(idx)
    if common is None or len(common) == 0:
        raise ValueError("symbols share no common timestamps")
    common = common.sort_values()
    return {sym: df.loc[common] for sym, df in data.items()}


def run_backtest(
    strategy: Strategy,
    data: dict[str, pd.DataFrame],
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Run ``strategy`` over ``data`` (symbol -> OHLCV DataFrame) and report performance."""
    config = config or BacktestConfig()

    missing = [s for s in strategy.required_symbols() if s not in data]
    if missing:
        raise ValueError(f"strategy {strategy.name!r} needs missing symbols: {missing}")

    aligned = _align(data)
    symbols = list(aligned.keys())
    index = next(iter(aligned.values())).index
    n = len(index)
    if n < 2:
        raise ValueError("need at least 2 bars to backtest")

    opens = {s: aligned[s]["open"].to_numpy() for s in symbols}
    closes = {s: aligned[s]["close"].to_numpy() for s in symbols}

    strategy.prepare(aligned)

    pf = Portfolio(
        starting_cash=config.starting_cash,
        commission_per_share=config.commission_per_share,
        commission_pct=config.commission_pct,
        slippage_pct=config.slippage_pct,
    )

    pending: dict[str, float] = {}
    equity_values: list[float] = []
    position_rows: list[dict[str, float]] = []

    for t in range(n):
        # 1. Fill orders decided on the previous bar, at this bar's open.
        if pending:
            for sym, qty in pending.items():
                if qty != 0:
                    pf.fill(sym, qty, float(opens[sym][t]))
            pending = {}

        # 2. Strategy decides using data up to this bar's close.
        cur_closes = {s: float(closes[s][t]) for s in symbols}
        ctx = Context(
            t=t,
            timestamp=index[t],
            portfolio=pf,
            config=config,
            _closes=cur_closes,
        )
        strategy.on_bar(t, ctx)
        pending = ctx._pending

        # 3. Mark to market at this bar's close.
        equity_values.append(pf.equity(cur_closes))
        position_rows.append({s: pf.position(s) for s in symbols})

    equity_curve = pd.Series(equity_values, index=index, name="equity")
    positions = pd.DataFrame(position_rows, index=index)
    report = performance_report(
        equity_curve,
        trade_pnls=pf.realized_trade_pnls,
        risk_free_rate=config.risk_free_rate,
        periods_per_year=config.periods_per_year,
    )

    return BacktestResult(
        equity_curve=equity_curve,
        report=report,
        positions=positions,
        config=config,
        strategy_name=strategy.name,
    )
