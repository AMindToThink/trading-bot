"""FastAPI backend for the educational web app.

Endpoints
  GET  /                      -> the educational single-page app
  GET  /api/strategies        -> registry-driven strategy metadata (drives the UI form)
  POST /api/backtest          -> run a backtest, return prices/indicators/equity/metrics
  GET  /api/recent/{symbol}   -> recent daily bars (Yahoo, no key) for a quick live-ish view

The frontend is intentionally dependency-light (vanilla JS + KaTeX + a tiny canvas chart),
so the whole thing is readable and easy to learn from.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from trading_bot.backtest.engine import BacktestConfig, run_backtest
from trading_bot.data import get_data_source
from trading_bot.strategies import available_strategies, get_strategy

# Import the package so all strategies register.
import trading_bot.strategies  # noqa: F401

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Trading Bot — Educational Day-Trading Lab")

# Annualization factor by bar size (periods per year).
_PERIODS_PER_YEAR = {
    "1Day": 252,
    "1Hour": 252 * 7,  # ~6.5h session, rounded
    "15Min": 252 * 26,
    "5Min": 252 * 78,
    "1Min": 252 * 390,
}


class BacktestRequest(BaseModel):
    strategy: str
    symbols: list[str] = Field(..., min_length=1, max_length=2)
    start: str | None = None
    end: str | None = None
    source: str = "yahoo"
    timeframe: str = "1Day"
    starting_cash: float = 100_000.0
    commission_pct: float = 0.0005
    slippage_pct: float = 0.0005
    params: dict = Field(default_factory=dict)


def _strategy_meta(key: str) -> dict:
    cls = get_strategy(key)
    return {
        "key": key,
        "name": cls.name,
        "blurb": cls.blurb,
        "num_symbols": cls.num_symbols,
        "signal_katex": cls.signal_katex,
        "default_symbols": list(cls.default_symbols),
        "params": [
            {"name": p.name, "default": p.default, "kind": p.kind, "label": p.label, "help": p.help}
            for p in cls.param_spec()
        ],
    }


def _coerce_params(key: str, raw: dict) -> dict:
    """Cast incoming JSON params to the types declared in the strategy's param_spec."""
    spec = {p.name: p.kind for p in get_strategy(key).param_spec()}
    out = {}
    for name, value in raw.items():
        kind = spec.get(name)
        if kind == "int":
            out[name] = int(value)
        elif kind == "float":
            out[name] = float(value)
        elif kind == "bool":
            out[name] = bool(value)
        else:
            out[name] = value
    return out


@app.get("/api/strategies")
def list_strategies() -> dict:
    return {"strategies": [_strategy_meta(k) for k in available_strategies()]}


@app.post("/api/backtest")
def backtest(req: BacktestRequest) -> dict:
    if req.strategy not in available_strategies():
        raise HTTPException(404, f"unknown strategy {req.strategy!r}")
    cls = get_strategy(req.strategy)
    if len(req.symbols) != cls.num_symbols:
        raise HTTPException(400, f"{req.strategy} needs exactly {cls.num_symbols} symbol(s)")

    symbols = [s.upper().strip() for s in req.symbols]
    try:
        strat = cls.from_config(symbols, **_coerce_params(req.strategy, req.params))
        source = get_data_source(req.source)
        data = source.get_bars_multi(symbols, start=req.start, end=req.end, timeframe=req.timeframe)
    except Exception as exc:  # surface a clean error to the UI
        raise HTTPException(400, str(exc)) from exc

    config = BacktestConfig(
        starting_cash=req.starting_cash,
        commission_pct=req.commission_pct,
        slippage_pct=req.slippage_pct,
        periods_per_year=_PERIODS_PER_YEAR.get(req.timeframe, 252),
    )
    try:
        result = run_backtest(strat, data, config)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc

    return _serialize(result, strat, symbols, config)


@app.get("/api/recent/{symbol}")
def recent(symbol: str, days: int = 180) -> dict:
    try:
        df = get_data_source("yahoo").get_bars(symbol.upper(), period=f"{max(days, 5)}d")
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        "symbol": symbol.upper(),
        "dates": [d.isoformat() for d in df.index],
        "close": [float(x) for x in df["close"]],
        "last": float(df["close"].iloc[-1]),
    }


def _markers(positions: pd.Series, prices: pd.Series, dates: list[str]) -> list[dict]:
    """Derive buy/sell markers from sign changes in the position."""
    out = []
    prev = 0.0
    for i, (pos, price) in enumerate(zip(positions.to_numpy(), prices.to_numpy())):
        if (pos > 0) and (prev <= 0):
            out.append({"i": i, "date": dates[i], "type": "buy", "price": float(price)})
        elif (pos < 0) and (prev >= 0):
            out.append({"i": i, "date": dates[i], "type": "short", "price": float(price)})
        elif (pos == 0) and (prev != 0):
            out.append({"i": i, "date": dates[i], "type": "exit", "price": float(price)})
        prev = pos
    return out


def _serialize(result, strat, symbols: list[str], config: BacktestConfig) -> dict:
    from trading_bot.backtest.metrics import drawdown_series

    dates = [d.isoformat() for d in result.equity_curve.index]
    primary = symbols[0]
    primary_close = result.prices[primary]

    # Buy & hold benchmark on the primary symbol: invest all starting cash at bar 0.
    buy_hold = config.starting_cash * (primary_close / primary_close.iloc[0])

    return {
        "strategy": result.strategy_name,
        "symbols": symbols,
        "primary": primary,
        "dates": dates,
        "prices": {s: [float(x) for x in result.prices[s]] for s in symbols},
        "overlays": strat.plot_series(),
        "signal_panel": strat.signal_panel(),
        "equity": [float(x) for x in result.equity_curve],
        "buy_hold_equity": [float(x) for x in buy_hold],
        "drawdown": [float(x) for x in drawdown_series(result.equity_curve)],
        "metrics": result.report.to_dict(),
        "markers": _markers(result.positions[primary], primary_close, dates),
        "extra": {
            "adf_stat": getattr(strat, "adf_stat", None),
            "adf_pvalue": getattr(strat, "adf_pvalue", None),
            "starting_cash": config.starting_cash,
        },
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


if (STATIC_DIR).exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
