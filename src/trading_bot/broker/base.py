"""Broker interface and risk guards.

The bot talks to brokers ONLY through the ``Broker`` abstraction. That is what lets you
learn and validate on Alpaca paper trading today and swap in a Schwab adapter for real
money later without rewriting strategy or execution logic.

``RiskGuard`` wraps any broker and blocks dangerous orders *before* they reach the wire:
a kill switch, per-order notional caps, a max number of open positions, and a rolling
day-trade counter (relevant to the Pattern Day Trader rule). Failing loudly here is much
safer than relying on the broker to reject a bad order after the fact.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from datetime import date
from enum import Enum


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class Account:
    cash: float
    equity: float
    buying_power: float
    is_paper: bool
    pattern_day_trader: bool = False
    daytrade_count: int = 0


@dataclass
class Position:
    symbol: str
    qty: float
    avg_entry_price: float
    market_value: float
    unrealized_pl: float


@dataclass
class OrderResult:
    id: str
    symbol: str
    qty: float
    side: OrderSide
    status: str


class Broker(ABC):
    """Abstract brokerage. Implementations: Alpaca (now), Schwab (real money, later)."""

    @abstractmethod
    def get_account(self) -> Account: ...

    @abstractmethod
    def get_positions(self) -> list[Position]: ...

    def get_position(self, symbol: str) -> Position | None:
        return next((p for p in self.get_positions() if p.symbol == symbol), None)

    @abstractmethod
    def submit_market_order(
        self,
        symbol: str,
        qty: float,
        side: OrderSide,
        reference_price: float | None = None,
    ) -> OrderResult:
        """Submit a market order. ``reference_price`` (latest known price) is advisory --
        used by risk guards for notional checks; plain adapters may ignore it."""

    @abstractmethod
    def close_position(self, symbol: str) -> None: ...

    @abstractmethod
    def is_market_open(self) -> bool: ...

    @property
    @abstractmethod
    def is_paper(self) -> bool: ...


class RiskError(RuntimeError):
    """Raised when an order violates a configured risk limit."""


@dataclass
class RiskLimits:
    kill_switch: bool = False  # if True, block ALL orders
    max_position_notional: float = 10_000.0  # max $ per single order
    max_open_positions: int = 10
    max_day_trades_per_5d: int = 3  # stay under the PDT 4-in-5 trigger by default
    allow_live_trading: bool = False  # must be explicitly enabled for real money


class RiskGuard(Broker):
    """Decorator that enforces ``RiskLimits`` around any underlying broker."""

    def __init__(self, broker: Broker, limits: RiskLimits | None = None) -> None:
        self._broker = broker
        self.limits = limits or RiskLimits()
        self._day_trades: deque[date] = deque()

        if not broker.is_paper and not self.limits.allow_live_trading:
            raise RiskError(
                "Refusing to wrap a LIVE broker without limits.allow_live_trading=True. "
                "Real money requires an explicit opt-in."
            )

    # --- pass-throughs -----------------------------------------------------------------
    def get_account(self) -> Account:
        return self._broker.get_account()

    def get_positions(self) -> list[Position]:
        return self._broker.get_positions()

    def is_market_open(self) -> bool:
        return self._broker.is_market_open()

    @property
    def is_paper(self) -> bool:
        return self._broker.is_paper

    # --- guarded actions ---------------------------------------------------------------
    def submit_market_order(
        self,
        symbol: str,
        qty: float,
        side: OrderSide,
        reference_price: float | None = None,
    ) -> OrderResult:
        if self.limits.kill_switch:
            raise RiskError("Kill switch is ON: all orders are blocked.")

        account = self._broker.get_account()
        price = reference_price if reference_price is not None else self._reference_price(symbol)
        notional = abs(qty) * price
        if notional > self.limits.max_position_notional:
            raise RiskError(
                f"Order notional ${notional:,.0f} exceeds cap "
                f"${self.limits.max_position_notional:,.0f} for {symbol}."
            )

        positions = self._broker.get_positions()
        held = {p.symbol for p in positions if p.qty != 0}
        if symbol not in held and len(held) >= self.limits.max_open_positions:
            raise RiskError(
                f"Already holding {len(held)} positions (max {self.limits.max_open_positions})."
            )

        if account.daytrade_count >= self.limits.max_day_trades_per_5d:
            raise RiskError(
                f"Broker day-trade count {account.daytrade_count} is at/over the limit "
                f"{self.limits.max_day_trades_per_5d}; refusing to risk a PDT flag."
            )

        return self._broker.submit_market_order(symbol, qty, side)

    def close_position(self, symbol: str) -> None:
        if self.limits.kill_switch:
            raise RiskError("Kill switch is ON: all orders are blocked.")
        self._broker.close_position(symbol)

    def _reference_price(self, symbol: str) -> float:
        pos = self._broker.get_position(symbol)
        if pos is not None and pos.qty != 0:
            return abs(pos.market_value / pos.qty)
        return 0.0  # unknown price -> notional check treats as 0 (caller should pass sized qty)
