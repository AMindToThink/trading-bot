"""Technical indicators, implemented to match the math shown on the web page exactly.

Every function here is a *pure* function of a price series. They never look into the
future: the value at index ``t`` depends only on prices at indices ``<= t``. This is the
first and most important defense against look-ahead bias (see ``backtest/engine.py``).

Conventions deliberately pinned (and unit-tested), because libraries disagree:
  * EMA smoothing factor      alpha = 2 / (N + 1)        (standard EMA)
  * Wilder/RSI smoothing       alpha = 1 / N             (NOT 2/(N+1) -- a classic bug)
  * Bollinger standard dev     population (ddof=0)       (Bollinger's own convention)

References for the formulas are in ``web/templates`` (the lesson text) and the project
research notes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "sma",
    "ema",
    "rolling_std",
    "zscore",
    "bollinger_bands",
    "rsi",
]


def sma(prices: pd.Series, window: int) -> pd.Series:
    r"""Simple Moving Average.

    .. math:: \mathrm{SMA}_t^{(N)} = \frac{1}{N}\sum_{i=0}^{N-1} P_{t-i}

    Returns NaN for the first ``window - 1`` rows (not enough history yet).
    """
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")
    return prices.rolling(window=window, min_periods=window).mean()


def ema(prices: pd.Series, window: int) -> pd.Series:
    r"""Exponential Moving Average with the standard smoothing factor.

    .. math:: \alpha = \frac{2}{N+1}, \qquad
              \mathrm{EMA}_t = \alpha P_t + (1-\alpha)\,\mathrm{EMA}_{t-1}

    Uses pandas' recursive ``ewm(adjust=False)``, which seeds ``EMA_0 = P_0``. (The
    infinite weighted-sum identity holds only in the steady-state limit; with a finite
    seed there is a vanishing ``(1-alpha)^t`` transient. This is fine pedagogically and
    is what real implementations compute.)
    """
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")
    return prices.ewm(span=window, adjust=False).mean()


def rolling_std(prices: pd.Series, window: int, *, population: bool = True) -> pd.Series:
    r"""Rolling standard deviation.

    ``population=True`` uses the divisor ``1/N`` (ddof=0), matching Bollinger Bands'
    original convention. Set ``population=False`` for the sample std ``1/(N-1)`` (ddof=1),
    which is pandas'/numpy's default.
    """
    ddof = 0 if population else 1
    return prices.rolling(window=window, min_periods=window).std(ddof=ddof)


def zscore(prices: pd.Series, window: int, *, population: bool = True) -> pd.Series:
    r"""Rolling z-score of price relative to its own moving average.

    .. math:: z_t = \frac{P_t - \mu_t}{\sigma_t}

    where :math:`\mu_t` and :math:`\sigma_t` are the rolling mean and std over ``window``.
    """
    mu = sma(prices, window)
    sd = rolling_std(prices, window, population=population)
    return (prices - mu) / sd


def bollinger_bands(
    prices: pd.Series, window: int = 20, num_std: float = 2.0, *, population: bool = True
) -> pd.DataFrame:
    r"""Bollinger Bands.

    .. math:: \text{Mid}_t = \mu_t, \quad
              \text{Upper}_t = \mu_t + k\sigma_t, \quad
              \text{Lower}_t = \mu_t - k\sigma_t

    Returns a DataFrame with columns ``mid``, ``upper``, ``lower``, ``zscore``.
    Note that touching the upper band is exactly ``zscore == +k`` and the lower band
    is ``zscore == -k``.
    """
    mu = sma(prices, window)
    sd = rolling_std(prices, window, population=population)
    return pd.DataFrame(
        {
            "mid": mu,
            "upper": mu + num_std * sd,
            "lower": mu - num_std * sd,
            "zscore": (prices - mu) / sd,
        }
    )


def rsi(prices: pd.Series, window: int = 14) -> pd.Series:
    r"""Relative Strength Index using Wilder's smoothing.

    Per-period change :math:`\Delta_t = P_t - P_{t-1}`, split into gains and losses
    (losses stored as positive magnitudes):

    .. math:: U_t = \max(\Delta_t, 0), \qquad D_t = \max(-\Delta_t, 0)

    Seed at ``t = N`` with simple averages, then Wilder-smooth (an EMA with
    :math:`\alpha = 1/N`):

    .. math:: \overline{U}_t = \frac{(N-1)\overline{U}_{t-1} + U_t}{N}, \qquad
              \mathrm{RS}_t = \frac{\overline{U}_t}{\overline{D}_t}, \qquad
              \mathrm{RSI}_t = 100 - \frac{100}{1 + \mathrm{RS}_t}

    Edge cases are defined directly to avoid division by zero:
    ``avg_loss == 0 -> RSI = 100`` and ``avg_gain == 0 -> RSI = 0``.

    Implemented as an explicit recursion (rather than ``ewm``) so it matches the
    textbook Wilder seed exactly and is easy to verify against the displayed formula.
    """
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")

    delta = prices.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    n = len(prices)
    avg_gain = np.full(n, np.nan)
    avg_loss = np.full(n, np.nan)

    if n <= window:
        return pd.Series(np.full(n, np.nan), index=prices.index, name="rsi")

    # Seed: simple average of the first `window` changes (indices 1..window).
    g = gain.to_numpy()
    losses = loss.to_numpy()
    avg_gain[window] = np.mean(g[1 : window + 1])
    avg_loss[window] = np.mean(losses[1 : window + 1])

    # Wilder recursion for t > window.
    for t in range(window + 1, n):
        avg_gain[t] = (avg_gain[t - 1] * (window - 1) + g[t]) / window
        avg_loss[t] = (avg_loss[t - 1] * (window - 1) + losses[t]) / window

    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        out = 100.0 - 100.0 / (1.0 + rs)

    # Edge cases: avg_loss == 0 -> RSI 100; avg_gain == 0 -> RSI 0.
    out = np.where((avg_loss == 0) & (~np.isnan(avg_loss)), 100.0, out)
    out = np.where((avg_gain == 0) & (~np.isnan(avg_gain)), 0.0, out)

    return pd.Series(out, index=prices.index, name="rsi")
