"""Strategy interface and registry.

A strategy implements two methods:

  * ``prepare(data)`` -- precompute causal indicators over the full (aligned) history.
    Because our indicators only ever look backward, computing them over the whole series
    up front introduces no look-ahead: the value at bar ``t`` still depends only on prices
    at ``<= t``.
  * ``on_bar(t, ctx)`` -- called once per bar in time order. Read indicator/price values
    at index ``t`` and place orders through ``ctx``. Orders are *market* orders that fill
    at the NEXT bar's open, so a decision made on the close of bar ``t`` can never be
    executed at that same close. This is the structural defense against look-ahead bias.

To add a new strategy, subclass ``Strategy``, implement the two methods, and decorate the
class with ``@register("my-name")``. It then becomes available everywhere (CLI, web app)
without touching any other file.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from trading_bot.backtest.engine import Context


@dataclass
class Param:
    """One tunable strategy parameter, used to auto-build the web UI form."""

    name: str
    default: float | int | bool
    kind: str  # "int" | "float" | "bool"
    label: str
    help: str = ""


class Strategy(ABC):
    """Base class for all trading strategies."""

    #: Human-readable name, set by subclasses.
    name: str = "unnamed"
    #: 1 for single-asset strategies, 2 for pairs.
    num_symbols: int = 1
    #: One-line description shown in the UI.
    blurb: str = ""
    #: A KaTeX string summarizing the entry/exit rule (shown on the web page).
    signal_katex: str = ""
    #: Suggested default tickers for the demo UI.
    default_symbols: tuple[str, ...] = ("AAPL",)

    @classmethod
    def param_spec(cls) -> list[Param]:
        """Tunable parameters. Override to expose knobs in the UI; default is none."""
        return []

    @classmethod
    def from_config(cls, symbols: list[str], **params) -> "Strategy":
        """Build an instance from a list of symbols and keyword params."""
        if cls.num_symbols == 1:
            return cls(symbols[0], **params)
        return cls(symbols[0], symbols[1], **params)

    @abstractmethod
    def required_symbols(self) -> list[str]:
        """Symbols this strategy needs. One for single-asset, two for pairs trading."""

    def prepare(self, data: dict[str, pd.DataFrame]) -> None:
        """Precompute indicators. ``data`` maps symbol -> OHLCV DataFrame, all sharing the
        same DatetimeIndex (the engine aligns them before calling this)."""

    @abstractmethod
    def on_bar(self, t: int, ctx: "Context") -> None:
        """Decide and place orders at integer bar index ``t``."""

    def plot_series(self) -> dict[str, list[float | None]]:
        """Named indicator overlays drawn on the PRICE axis, valid after ``prepare``.
        Override to return e.g. {"SMA(20)": [...], ...}. NaNs become None for JSON."""
        return {}

    def signal_panel(self) -> dict | None:
        """An oscillator drawn in a SEPARATE lower panel (RSI, z-score, spread), or None.

        Shape: ``{"name": str, "values": [...], "thresholds": [{"y": float, "label": str}]}``.
        """
        return None


def _clean(arr) -> list[float | None]:
    """Convert a numpy array to a JSON-safe list (NaN/inf -> None)."""
    return [None if (v is None or not np.isfinite(v)) else float(v) for v in np.asarray(arr)]


# --------------------------------------------------------------------------- registry
_REGISTRY: dict[str, type[Strategy]] = {}


def register(key: str) -> Callable[[type[Strategy]], type[Strategy]]:
    """Class decorator that registers a strategy under ``key``."""

    def deco(cls: type[Strategy]) -> type[Strategy]:
        if key in _REGISTRY:
            raise ValueError(f"strategy key {key!r} already registered")
        _REGISTRY[key] = cls
        cls.registry_key = key  # type: ignore[attr-defined]
        return cls

    return deco


def get_strategy(key: str) -> type[Strategy]:
    if key not in _REGISTRY:
        raise KeyError(f"unknown strategy {key!r}; available: {sorted(_REGISTRY)}")
    return _REGISTRY[key]


def available_strategies() -> list[str]:
    return sorted(_REGISTRY)
