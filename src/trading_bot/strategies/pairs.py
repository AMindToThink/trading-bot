"""Pairs trading via cointegration -- a statistical-arbitrage strategy on two stocks."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from trading_bot.strategies.base import Strategy, register


@register("pairs")
class PairsTrading(Strategy):
    r"""Trade the *spread* between two correlated stocks, betting it mean-reverts.

    Estimate a hedge ratio :math:`\beta` by regressing A on B over a trailing window
    (:math:`\hat\beta_t = \mathrm{Cov}(A,B)/\mathrm{Var}(B)`), form the spread
    :math:`s_t = A_t - \hat\beta_t B_t`, and standardize it:
    :math:`z_t = (s_t - \mu_t)/\sigma_t`.

    * **Short the spread** (sell A, buy :math:`\beta` B) when :math:`z_t \ge +z_{\text{entry}}`.
    * **Long the spread** (buy A, sell :math:`\beta` B) when :math:`z_t \le -z_{\text{entry}}`.
    * **Exit** when it reverts (:math:`|z_t| \le z_{\text{exit}}`) or a stop trips
      (:math:`|z_t| \ge z_{\text{stop}}`), which guards against the relationship breaking down.

    All of :math:`\beta`, :math:`\mu`, and :math:`\sigma` are computed on trailing windows
    (causal), so no future information leaks into a trading decision. An Augmented
    Dickey-Fuller test on the full-sample spread is computed once for the lesson display
    (a descriptive cointegration check, not a trading signal).
    """

    name = "Pairs Trading (cointegration)"

    def __init__(
        self,
        symbol_a: str,
        symbol_b: str,
        lookback: int = 60,
        z_window: int = 60,
        entry_z: float = 2.0,
        exit_z: float = 0.5,
        stop_z: float = 4.0,
        capital_fraction: float = 0.5,
    ) -> None:
        self.symbol_a = symbol_a
        self.symbol_b = symbol_b
        self.lookback = lookback
        self.z_window = z_window
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.stop_z = stop_z
        self.capital_fraction = capital_fraction
        self.adf_stat: float | None = None
        self.adf_pvalue: float | None = None

    def required_symbols(self) -> list[str]:
        return [self.symbol_a, self.symbol_b]

    def prepare(self, data: dict[str, pd.DataFrame]) -> None:
        a = data[self.symbol_a]["close"]
        b = data[self.symbol_b]["close"]

        # Causal rolling hedge ratio beta = Cov(A,B)/Var(B) over the lookback window.
        cov = a.rolling(self.lookback).cov(b)
        var = b.rolling(self.lookback).var()
        beta = cov / var
        spread = a - beta * b
        mu = spread.rolling(self.z_window).mean()
        sd = spread.rolling(self.z_window).std(ddof=0)
        z = (spread - mu) / sd

        self.beta = beta.to_numpy()
        self.z = z.to_numpy()

        # Full-sample ADF on a static-beta spread, for the educational display only.
        try:
            from statsmodels.tsa.stattools import adfuller

            static_beta = np.cov(a, b)[0, 1] / np.var(b)
            static_spread = (a - static_beta * b).dropna()
            if len(static_spread) > 20:
                result = adfuller(static_spread, autolag="AIC")
                self.adf_stat = float(result[0])
                self.adf_pvalue = float(result[1])
        except Exception:  # pragma: no cover - display-only, never blocks a backtest
            self.adf_stat = None
            self.adf_pvalue = None

    def on_bar(self, t: int, ctx) -> None:
        beta = self.beta[t]
        z = self.z[t]
        if math.isnan(beta) or math.isnan(z):
            return

        pos_a = ctx.position(self.symbol_a)
        in_position = pos_a != 0

        if not in_position:
            price_a = ctx.price(self.symbol_a)
            if price_a <= 0:
                return
            notional = self.capital_fraction * ctx.equity()
            qa = notional / price_a
            if z >= self.entry_z:  # short the spread: sell A, buy beta*B
                ctx.order_target_shares(self.symbol_a, -qa)
                ctx.order_target_shares(self.symbol_b, beta * qa)
            elif z <= -self.entry_z:  # long the spread: buy A, sell beta*B
                ctx.order_target_shares(self.symbol_a, qa)
                ctx.order_target_shares(self.symbol_b, -beta * qa)
        else:
            if abs(z) <= self.exit_z or abs(z) >= self.stop_z:
                ctx.close_position(self.symbol_a)
                ctx.close_position(self.symbol_b)
