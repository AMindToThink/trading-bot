"""API tests for the FastAPI backend, with the data source patched (no network)."""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from trading_bot.data.base import DataSource
from trading_bot.web import app as webapp


class FakeSource(DataSource):
    def get_bars(self, symbol, start=None, end=None, timeframe="1Day", **kw):
        seed = sum(ord(c) for c in symbol)
        rng = np.random.default_rng(seed)
        n = 250
        close = 100 + np.cumsum(rng.normal(0, 1, n))
        idx = pd.date_range("2022-01-01", periods=n, freq="B")
        return pd.DataFrame(
            {"open": close, "high": close * 1.01, "low": close * 0.99,
             "close": close, "volume": np.full(n, 1e6)},
            index=idx,
        )


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(webapp, "get_data_source", lambda name="yahoo": FakeSource())
    return TestClient(webapp.app)


def test_list_strategies(client):
    r = client.get("/api/strategies")
    assert r.status_code == 200
    keys = {s["key"] for s in r.json()["strategies"]}
    assert keys == {"ma_crossover", "mean_reversion", "rsi", "pairs"}
    # each strategy exposes a params schema for the UI
    for s in r.json()["strategies"]:
        assert isinstance(s["params"], list)


def test_backtest_single_asset(client):
    r = client.post("/api/backtest", json={
        "strategy": "ma_crossover", "symbols": ["AAPL"],
        "params": {"short_window": 10, "long_window": 30},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["equity"]) == 250
    assert len(body["buy_hold_equity"]) == 250
    assert "sharpe_ratio" in body["metrics"]
    assert "MA(10)" in body["overlays"]


def test_backtest_pairs_reports_adf(client):
    r = client.post("/api/backtest", json={"strategy": "pairs", "symbols": ["KO", "PEP"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["extra"]["adf_pvalue"] is not None
    assert body["signal_panel"]["name"] == "Spread z-score"


def test_backtest_wrong_symbol_count(client):
    r = client.post("/api/backtest", json={"strategy": "pairs", "symbols": ["KO"]})
    assert r.status_code == 400


def test_unknown_strategy(client):
    r = client.post("/api/backtest", json={"strategy": "nope", "symbols": ["AAPL"]})
    assert r.status_code == 404
