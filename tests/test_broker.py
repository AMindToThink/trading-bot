"""Tests for the broker risk guards, using a fake in-memory broker (no network)."""

import pytest

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


class FakeBroker(Broker):
    def __init__(self, *, paper=True, positions=None, daytrade_count=0):
        self._paper = paper
        self._positions = positions or []
        self._daytrade_count = daytrade_count
        self.submitted = []

    @property
    def is_paper(self):
        return self._paper

    def get_account(self):
        return Account(
            cash=100_000, equity=100_000, buying_power=200_000,
            is_paper=self._paper, daytrade_count=self._daytrade_count,
        )

    def get_positions(self):
        return list(self._positions)

    def submit_market_order(self, symbol, qty, side, reference_price=None):
        self.submitted.append((symbol, qty, side))
        return OrderResult(id="1", symbol=symbol, qty=qty, side=side, status="accepted")

    def close_position(self, symbol):
        self.submitted.append((symbol, "close", None))

    def is_market_open(self):
        return True


def test_order_passes_within_limits():
    guard = RiskGuard(FakeBroker(), RiskLimits(max_position_notional=10_000))
    res = guard.submit_market_order("AAPL", 10, OrderSide.BUY, reference_price=100.0)
    assert res.status == "accepted"


def test_kill_switch_blocks_orders():
    guard = RiskGuard(FakeBroker(), RiskLimits(kill_switch=True))
    with pytest.raises(RiskError, match="Kill switch"):
        guard.submit_market_order("AAPL", 1, OrderSide.BUY, reference_price=100.0)


def test_notional_cap_blocks_large_orders():
    guard = RiskGuard(FakeBroker(), RiskLimits(max_position_notional=1_000))
    with pytest.raises(RiskError, match="exceeds cap"):
        guard.submit_market_order("AAPL", 100, OrderSide.BUY, reference_price=100.0)  # $10k


def test_max_open_positions_blocks_new_symbol():
    held = [Position("MSFT", 1, 100, 100, 0), Position("GOOG", 1, 100, 100, 0)]
    guard = RiskGuard(FakeBroker(positions=held), RiskLimits(max_open_positions=2))
    with pytest.raises(RiskError, match="positions"):
        guard.submit_market_order("AAPL", 1, OrderSide.BUY, reference_price=100.0)
    # but adding to an existing position is allowed
    guard.submit_market_order("MSFT", 1, OrderSide.BUY, reference_price=100.0)


def test_daytrade_count_blocks_pdt_risk():
    guard = RiskGuard(FakeBroker(daytrade_count=3), RiskLimits(max_day_trades_per_5d=3))
    with pytest.raises(RiskError, match="day-trade count"):
        guard.submit_market_order("AAPL", 1, OrderSide.BUY, reference_price=100.0)


def test_live_broker_requires_explicit_optin():
    with pytest.raises(RiskError, match="allow_live_trading"):
        RiskGuard(FakeBroker(paper=False), RiskLimits(allow_live_trading=False))
    # explicit opt-in is accepted
    guard = RiskGuard(FakeBroker(paper=False), RiskLimits(allow_live_trading=True))
    assert guard.is_paper is False
