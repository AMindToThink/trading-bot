r"""Performance & risk metrics, with the period-vs-annualized distinction made explicit.

The single most common bug in this area is annualizing with a hardcoded ``sqrt(252)``
regardless of bar size. We instead take ``periods_per_year`` as an explicit parameter
everywhere. For daily bars that is 252; for hourly bars on a 6.5-hour US session it is
``252 * 6.5 ~= 1638``; for minute bars ``252 * 390 = 98280``.

The ``sqrt`` annualization rule (mean scales with P, std with sqrt(P), so the Sharpe
ratio scales with sqrt(P)) is exact only if per-period returns are i.i.d. Real returns
are autocorrelated and fat-tailed, so annualized figures are optimistic. We surface this
caveat in the lesson text rather than hiding it.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def total_return(equity: pd.Series) -> float:
    r""":math:`R_{\text{total}} = V_{\text{end}} / V_{\text{start}} - 1`."""
    equity = equity.dropna()
    if len(equity) < 2 or equity.iloc[0] == 0:
        return float("nan")
    return float(equity.iloc[-1] / equity.iloc[0] - 1.0)


def cagr(equity: pd.Series, periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    r"""Compound Annual Growth Rate.

    .. math:: \mathrm{CAGR} = \left(\frac{V_{\text{end}}}{V_{\text{start}}}\right)^{1/Y} - 1

    where ``Y`` is the number of years, inferred from the number of periods and
    ``periods_per_year``. This is a geometric mean and is always <= the arithmetic mean
    of periodic returns (Jensen's inequality).
    """
    equity = equity.dropna()
    n = len(equity)
    if n < 2 or equity.iloc[0] <= 0:
        return float("nan")
    years = (n - 1) / periods_per_year
    if years <= 0:
        return float("nan")
    growth = equity.iloc[-1] / equity.iloc[0]
    if growth <= 0:
        return float("nan")
    return float(growth ** (1.0 / years) - 1.0)


def _periodic_returns(equity: pd.Series) -> pd.Series:
    return equity.dropna().pct_change().dropna()


def sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    r"""Annualized Sharpe ratio.

    Per-period: :math:`\mathrm{SR} = \dfrac{\mathbb{E}[r_t - r_f]}{\mathrm{std}(r_t)}`,
    annualized by :math:`\sqrt{P}`.

    ``risk_free_rate`` is the *per-period* risk-free rate (use 0 for a quick read).
    Uses the sample standard deviation (ddof=1).
    """
    returns = returns.dropna()
    if len(returns) < 2:
        return float("nan")
    excess = returns - risk_free_rate
    sd = returns.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return float("nan")
    return float(excess.mean() / sd * np.sqrt(periods_per_year))


def sortino_ratio(
    returns: pd.Series,
    mar: float = 0.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    r"""Annualized Sortino ratio.

    .. math:: \mathrm{Sortino} = \frac{\mathbb{E}[r_t] - \mathrm{MAR}}{\mathrm{DD}},
              \qquad
              \mathrm{DD} = \sqrt{\frac{1}{N}\sum_{t=1}^{N}\big[\min(r_t - \mathrm{MAR}, 0)\big]^2}

    Critical subtlety: returns above the minimum acceptable return (MAR) contribute 0 to
    the sum but are NOT dropped, and we divide by the FULL count ``N`` (not the number of
    losing periods). Annualized by ``sqrt(P)``.
    """
    returns = returns.dropna()
    n = len(returns)
    if n < 2:
        return float("nan")
    downside = np.minimum(returns - mar, 0.0)
    dd = np.sqrt(np.sum(downside**2) / n)
    if dd == 0 or np.isnan(dd):
        return float("nan")
    return float((returns.mean() - mar) / dd * np.sqrt(periods_per_year))


def annualized_volatility(
    returns: pd.Series, periods_per_year: int = TRADING_DAYS_PER_YEAR
) -> float:
    r""":math:`\sigma_{\text{annual}} = \mathrm{std}(r_t)\,\sqrt{P}` (sample std, ddof=1)."""
    returns = returns.dropna()
    if len(returns) < 2:
        return float("nan")
    return float(returns.std(ddof=1) * np.sqrt(periods_per_year))


def drawdown_series(equity: pd.Series) -> pd.Series:
    r"""Drawdown at each point: :math:`DD_t = V_t / \max(V_0,\dots,V_t) - 1 \le 0`."""
    equity = equity.dropna()
    running_peak = equity.cummax()
    return equity / running_peak - 1.0


def max_drawdown(equity: pd.Series) -> float:
    r"""Maximum drawdown: the most negative value of the drawdown series.

    Recovery is asymmetric: a drawdown of ``d`` needs a gain of ``1/(1+d) - 1`` to
    recover (a -50% drawdown needs +100%).
    """
    equity = equity.dropna()
    if len(equity) < 2:
        return float("nan")
    return float(drawdown_series(equity).min())


@dataclass
class TradeStats:
    """Trade-level statistics. Losses are reported as positive magnitudes."""

    num_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    expectancy: float


def trade_stats(trade_pnls: list[float] | np.ndarray | pd.Series) -> TradeStats:
    r"""Compute win rate, profit factor, and expectancy from per-trade P&L.

    * Win rate = winners / total.
    * Profit factor = gross profit / |gross loss| (>1 profitable, <1 loses money).
    * Expectancy = WinRate * AvgWin - LossRate * AvgLoss (expected $ per trade).

    Win rate alone is misleading -- a 90% win rate still loses money if the rare losses
    are huge -- so we always report profit factor and expectancy alongside it.
    """
    pnls = np.asarray(list(trade_pnls), dtype=float)
    n = len(pnls)
    if n == 0:
        return TradeStats(0, float("nan"), float("nan"), float("nan"), float("nan"), float("nan"))

    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_profit = wins.sum()
    gross_loss = -losses.sum()  # positive magnitude

    win_rate = len(wins) / n
    loss_rate = len(losses) / n
    avg_win = wins.mean() if len(wins) else 0.0
    avg_loss = (-losses.mean()) if len(losses) else 0.0  # positive magnitude

    if gross_loss == 0:
        profit_factor = float("inf") if gross_profit > 0 else float("nan")
    else:
        profit_factor = gross_profit / gross_loss

    expectancy = win_rate * avg_win - loss_rate * avg_loss

    return TradeStats(
        num_trades=n,
        win_rate=win_rate,
        avg_win=float(avg_win),
        avg_loss=float(avg_loss),
        profit_factor=float(profit_factor),
        expectancy=float(expectancy),
    )


@dataclass
class PerformanceReport:
    """Full performance summary for an equity curve (+ optional trade P&Ls)."""

    total_return: float
    cagr: float
    annualized_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    periods_per_year: int
    trades: TradeStats | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def performance_report(
    equity: pd.Series,
    trade_pnls: list[float] | None = None,
    risk_free_rate: float = 0.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> PerformanceReport:
    """Bundle the headline metrics for an equity curve into one report."""
    rets = _periodic_returns(equity)
    return PerformanceReport(
        total_return=total_return(equity),
        cagr=cagr(equity, periods_per_year),
        annualized_volatility=annualized_volatility(rets, periods_per_year),
        sharpe_ratio=sharpe_ratio(rets, risk_free_rate, periods_per_year),
        sortino_ratio=sortino_ratio(rets, risk_free_rate, periods_per_year),
        max_drawdown=max_drawdown(equity),
        periods_per_year=periods_per_year,
        trades=trade_stats(trade_pnls) if trade_pnls is not None else None,
    )
