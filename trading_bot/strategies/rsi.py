"""RSI momentum / oscillator strategy."""

from __future__ import annotations

import math

import pandas as pd

from trading_bot.indicators import rsi
from trading_bot.strategies.base import Param, Strategy, _clean, register


@register("rsi")
class RSIStrategy(Strategy):
    r"""Trade RSI extremes with a midline exit.

    With Wilder's RSI bounded in :math:`[0, 100]`:

    * Enter **long** when :math:`\mathrm{RSI}_t <` ``oversold`` (default 30).
    * Enter **short** when :math:`\mathrm{RSI}_t >` ``overbought`` (default 70), if enabled.
    * **Exit** when RSI crosses back through the midline ``exit_level`` (default 50): a long
      closes once RSI rises above 50, a short closes once RSI falls below 50.
    """

    name = "RSI Momentum"
    num_symbols = 1
    blurb = "Oscillator: buy oversold (RSI<30), exit at the midline (RSI 50)."
    signal_katex = r"\mathrm{RSI}_t = 100 - \frac{100}{1+\mathrm{RS}_t};\ \text{buy if } \mathrm{RSI}_t < 30"
    default_symbols = ("TSLA",)

    @classmethod
    def param_spec(cls):
        return [
            Param("window", 14, "int", "Window (N)", "Wilder smoothing length."),
            Param("oversold", 30.0, "float", "Oversold", "Buy below this RSI."),
            Param("overbought", 70.0, "float", "Overbought", "Short above this RSI."),
            Param("exit_level", 50.0, "float", "Exit (midline)", "Close when RSI crosses this."),
            Param("allow_short", False, "bool", "Allow shorting", "Short when overbought."),
        ]

    def __init__(
        self,
        symbol: str,
        window: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        exit_level: float = 50.0,
        position_size: float = 0.95,
        allow_short: bool = False,
    ) -> None:
        self.symbol = symbol
        self.window = window
        self.oversold = oversold
        self.overbought = overbought
        self.exit_level = exit_level
        self.position_size = position_size
        self.allow_short = allow_short

    def required_symbols(self) -> list[str]:
        return [self.symbol]

    def prepare(self, data: dict[str, pd.DataFrame]) -> None:
        self.rsi = rsi(data[self.symbol]["close"], self.window).to_numpy()

    def on_bar(self, t: int, ctx) -> None:
        r = self.rsi[t]
        if math.isnan(r):
            return
        pos = ctx.position(self.symbol)
        if pos == 0:
            if r < self.oversold:
                ctx.order_target_percent(self.symbol, self.position_size)
            elif self.allow_short and r > self.overbought:
                ctx.order_target_percent(self.symbol, -self.position_size)
        elif pos > 0:
            if r > self.exit_level:
                ctx.close_position(self.symbol)
        else:  # short
            if r < self.exit_level:
                ctx.close_position(self.symbol)

    def signal_panel(self):
        return {
            "name": f"RSI({self.window})",
            "values": _clean(self.rsi),
            "thresholds": [
                {"y": self.overbought, "label": "Overbought"},
                {"y": self.exit_level, "label": "Midline"},
                {"y": self.oversold, "label": "Oversold"},
            ],
        }
