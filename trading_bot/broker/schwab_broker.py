"""Schwab broker adapter -- the REAL-MONEY migration path (intentionally a guided stub).

Why this is a stub: per the project research, the Charles Schwab Trader API has **no
usable paper-trading environment** (its "Sandbox" only returns canned data; the schwab-py
library states plainly that "Paper trading is not supported"). So every Schwab order is
live money. We therefore do NOT auto-wire Schwab. Instead, this file documents exactly
what to implement, so going live is a deliberate, reviewed step -- not an accident.

Migration checklist (do these in order):
  1. Prove the strategy first on Alpaca PAPER (see AlpacaBroker). Do not skip this.
  2. Register a developer app at https://developer.schwab.com/ -> "Trader API - Individual".
     Approval takes a few business days. Set an HTTPS callback (e.g. https://127.0.0.1:8182).
  3. ``uv sync --extra schwab`` to install schwab-py.
  4. Implement the methods below using schwab-py's client. Note the OAuth tokens expire:
     access token after 30 min (auto-refreshed), refresh token after 7 days (forces a
     manual re-login) -- plan for periodic re-auth on an always-on bot.
  5. ALWAYS wrap this broker in a RiskGuard with allow_live_trading=True, a small
     max_position_notional, and start with tiny share counts (there is no sandbox to
     catch mistakes).
"""

from __future__ import annotations

from trading_bot.broker.base import Account, Broker, OrderResult, Position

_NOT_IMPLEMENTED = (
    "SchwabBroker is a documented stub. Schwab has no paper sandbox, so it is not wired "
    "by default. Follow the migration checklist in schwab_broker.py before enabling real "
    "money, and validate on Alpaca paper trading first."
)


class SchwabBroker(Broker):
    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    @property
    def is_paper(self) -> bool:
        return False  # Schwab is ALWAYS live money.

    def get_account(self) -> Account:  # pragma: no cover - stub
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def get_positions(self) -> list[Position]:  # pragma: no cover - stub
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def submit_market_order(self, symbol, qty, side, reference_price=None) -> OrderResult:  # pragma: no cover
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def close_position(self, symbol: str) -> None:  # pragma: no cover - stub
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def is_market_open(self) -> bool:  # pragma: no cover - stub
        raise NotImplementedError(_NOT_IMPLEMENTED)
