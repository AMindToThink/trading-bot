"""Moving-average crossover: a classic trend-following strategy."""

from __future__ import annotations

import pandas as pd

from trading_bot.indicators import ema, sma
from trading_bot.strategies.base import Strategy, register


@register("ma_crossover")
class MovingAverageCrossover(Strategy):
    r"""Go long on a golden cross, exit (or short) on a death cross.

    With a short window :math:`N_s` and long window :math:`N_l` (:math:`N_s < N_l`), let
    :math:`D_t = \mathrm{MA}^{(N_s)}_t - \mathrm{MA}^{(N_l)}_t`. A *golden cross* is
    :math:`D_{t-1} \le 0 < D_t` (bullish); a *death cross* is :math:`D_{t-1} \ge 0 > D_t`
    (bearish). Signals fire on the crossing, not while the condition merely persists.
    """

    name = "Moving-Average Crossover"

    def __init__(
        self,
        symbol: str,
        short_window: int = 20,
        long_window: int = 50,
        ma_type: str = "ema",
        position_size: float = 0.95,
        allow_short: bool = False,
    ) -> None:
        if short_window >= long_window:
            raise ValueError("short_window must be < long_window")
        self.symbol = symbol
        self.short_window = short_window
        self.long_window = long_window
        self.ma_type = ma_type
        self.position_size = position_size
        self.allow_short = allow_short

    def required_symbols(self) -> list[str]:
        return [self.symbol]

    def prepare(self, data: dict[str, pd.DataFrame]) -> None:
        close = data[self.symbol]["close"]
        f = ema if self.ma_type == "ema" else sma
        self.ma_short = f(close, self.short_window).to_numpy()
        self.ma_long = f(close, self.long_window).to_numpy()

    def on_bar(self, t: int, ctx) -> None:
        if t < 1:
            return
        s0, l0 = self.ma_short[t - 1], self.ma_long[t - 1]
        s1, l1 = self.ma_short[t], self.ma_long[t]
        if any(x != x for x in (s0, l0, s1, l1)):  # NaN guard (NaN != NaN)
            return
        d_prev, d_now = s0 - l0, s1 - l1
        if d_prev <= 0 < d_now:  # golden cross
            ctx.order_target_percent(self.symbol, self.position_size)
        elif d_prev >= 0 > d_now:  # death cross
            ctx.order_target_percent(self.symbol, -self.position_size if self.allow_short else 0.0)
