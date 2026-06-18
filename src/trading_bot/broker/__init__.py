"""Broker abstraction and adapters."""

from trading_bot.broker.base import (
    Account,
    Broker,
    OrderResult,
    OrderSide,
    Position,
    RiskError,
    RiskGuard,
    RiskLimits,
)

__all__ = [
    "Account",
    "Broker",
    "OrderResult",
    "OrderSide",
    "Position",
    "RiskError",
    "RiskGuard",
    "RiskLimits",
    "get_broker",
]


def get_broker(name: str = "alpaca"):
    """Factory: ``"alpaca"`` (paper/live) or ``"schwab"`` (real-money stub)."""
    if name == "alpaca":
        from trading_bot.broker.alpaca_broker import AlpacaBroker

        return AlpacaBroker()
    if name == "schwab":
        from trading_bot.broker.schwab_broker import SchwabBroker

        return SchwabBroker()
    raise ValueError(f"unknown broker {name!r}; choose 'alpaca' or 'schwab'")
