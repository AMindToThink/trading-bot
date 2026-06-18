"""Tests for the live runner's order translation, using a fake broker (no network)."""

from trading_bot.broker.base import Account, Broker, OrderResult, OrderSide, Position
from trading_bot.live.runner import LiveContext


class FakeBroker(Broker):
    def __init__(self, equity=10_000.0, positions=None):
        self._equity = equity
        self._positions = positions or []
        self.orders = []

    @property
    def is_paper(self):
        return True

    def get_account(self):
        return Account(cash=self._equity, equity=self._equity, buying_power=self._equity, is_paper=True)

    def get_positions(self):
        return list(self._positions)

    def submit_market_order(self, symbol, qty, side, reference_price=None):
        self.orders.append((symbol, qty, side, reference_price))
        return OrderResult(id="1", symbol=symbol, qty=qty, side=side, status="accepted")

    def close_position(self, symbol):
        self.orders.append((symbol, "close", None, None))

    def is_market_open(self):
        return True


def test_order_target_percent_sizes_from_equity_and_price():
    broker = FakeBroker(equity=10_000.0)
    ctx = LiveContext(broker, prices={"AAPL": 100.0})
    ctx.order_target_percent("AAPL", 0.5)  # $5000 / $100 = 50 shares
    assert broker.orders == [("AAPL", 50.0, OrderSide.BUY, 100.0)]


def test_order_target_shares_computes_delta_from_existing_position():
    broker = FakeBroker(positions=[Position("AAPL", 30, 100, 3000, 0)])
    ctx = LiveContext(broker, prices={"AAPL": 100.0})
    ctx.order_target_shares("AAPL", 50)  # already hold 30 -> buy 20 more
    assert broker.orders == [("AAPL", 20.0, OrderSide.BUY, 100.0)]


def test_sell_when_target_below_current():
    broker = FakeBroker(positions=[Position("AAPL", 50, 100, 5000, 0)])
    ctx = LiveContext(broker, prices={"AAPL": 100.0})
    ctx.order_target_shares("AAPL", 10)  # sell 40
    assert broker.orders == [("AAPL", 40.0, OrderSide.SELL, 100.0)]


def test_close_position_sells_all():
    broker = FakeBroker(positions=[Position("AAPL", 25, 100, 2500, 0)])
    ctx = LiveContext(broker, prices={"AAPL": 100.0})
    ctx.close_position("AAPL")
    assert broker.orders == [("AAPL", 25.0, OrderSide.SELL, 100.0)]


def test_whole_shares_rounds_toward_zero():
    broker = FakeBroker(equity=10_000.0)
    ctx = LiveContext(broker, prices={"AAPL": 300.0})  # 0.5*10000/300 = 16.67 -> 16
    ctx.order_target_percent("AAPL", 0.5)
    assert broker.orders == [("AAPL", 16.0, OrderSide.BUY, 300.0)]
