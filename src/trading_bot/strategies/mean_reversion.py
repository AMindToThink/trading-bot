"""Mean reversion using the Bollinger-band z-score."""

from __future__ import annotations

import math

import pandas as pd

from trading_bot.indicators import zscore
from trading_bot.strategies.base import Strategy, register


@register("mean_reversion")
class MeanReversion(Strategy):
    r"""Fade extremes: buy when price is unusually low, sell when unusually high.

    Using the rolling z-score :math:`z_t = (P_t - \mu_t)/\sigma_t` over a window:

    * Enter **long** when :math:`z_t \le -z_{\text{entry}}` (oversold, below the lower band).
    * Enter **short** when :math:`z_t \ge +z_{\text{entry}}` (overbought) if shorting is on.
    * **Exit** when price reverts to the mean: a long closes once :math:`z_t \ge -z_{\text{exit}}`
      and a short closes once :math:`z_t \le +z_{\text{exit}}` (with ``exit_z = 0`` that is a
      return to the mean).
    """

    name = "Mean Reversion (Bollinger z-score)"

    def __init__(
        self,
        symbol: str,
        window: int = 20,
        entry_z: float = 2.0,
        exit_z: float = 0.0,
        position_size: float = 0.95,
        allow_short: bool = True,
    ) -> None:
        self.symbol = symbol
        self.window = window
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.position_size = position_size
        self.allow_short = allow_short

    def required_symbols(self) -> list[str]:
        return [self.symbol]

    def prepare(self, data: dict[str, pd.DataFrame]) -> None:
        self.z = zscore(data[self.symbol]["close"], self.window, population=True).to_numpy()

    def on_bar(self, t: int, ctx) -> None:
        z = self.z[t]
        if math.isnan(z):
            return
        pos = ctx.position(self.symbol)
        if pos == 0:
            if z <= -self.entry_z:
                ctx.order_target_percent(self.symbol, self.position_size)
            elif self.allow_short and z >= self.entry_z:
                ctx.order_target_percent(self.symbol, -self.position_size)
        elif pos > 0:
            if z >= -self.exit_z:
                ctx.close_position(self.symbol)
        else:  # short
            if z <= self.exit_z:
                ctx.close_position(self.symbol)
