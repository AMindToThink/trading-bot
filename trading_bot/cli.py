"""Command-line interface for the trading bot.

Examples::

    # Backtest the RSI strategy on Apple over a date range
    uv run python -m trading_bot.cli backtest --strategy rsi --symbols AAPL \\
        --start 2022-01-01 --end 2024-12-31 --set window=14 --set oversold=25

    # Pairs trade Coke vs Pepsi
    uv run python -m trading_bot.cli backtest --strategy pairs --symbols KO PEP

    # List strategies and their parameters
    uv run python -m trading_bot.cli list

    # Launch the educational web app
    uv run python -m trading_bot.cli serve
"""

from __future__ import annotations

import argparse
import sys

from trading_bot.backtest.engine import BacktestConfig, run_backtest
from trading_bot.data import get_data_source
from trading_bot.strategies import available_strategies, get_strategy


def _parse_sets(pairs: list[str], strategy_key: str) -> dict:
    """Turn ['window=14', 'allow_short=true'] into a typed param dict."""
    spec = {p.name: p.kind for p in get_strategy(strategy_key).param_spec()}
    out: dict = {}
    for item in pairs:
        if "=" not in item:
            raise SystemExit(f"--set expects key=value, got {item!r}")
        key, _, val = item.partition("=")
        kind = spec.get(key)
        if kind == "int":
            out[key] = int(val)
        elif kind == "float":
            out[key] = float(val)
        elif kind == "bool":
            out[key] = val.strip().lower() in {"1", "true", "yes", "on"}
        else:  # unknown param -> best-effort numeric, else string
            try:
                out[key] = float(val)
            except ValueError:
                out[key] = val
    return out


def cmd_list(_: argparse.Namespace) -> int:
    for key in available_strategies():
        cls = get_strategy(key)
        params = ", ".join(f"{p.name}={p.default}" for p in cls.param_spec()) or "(none)"
        print(f"\n  {key}  —  {cls.name}")
        print(f"      {cls.blurb}")
        print(f"      symbols: {cls.num_symbols}   params: {params}")
    print()
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    if args.strategy not in available_strategies():
        raise SystemExit(f"unknown strategy {args.strategy!r}; try `list`")
    cls = get_strategy(args.strategy)
    symbols = [s.upper() for s in args.symbols]
    if len(symbols) != cls.num_symbols:
        raise SystemExit(f"{args.strategy} needs {cls.num_symbols} symbol(s), got {len(symbols)}")

    strat = cls.from_config(symbols, **_parse_sets(args.set, args.strategy))
    data = get_data_source(args.source).get_bars_multi(
        symbols, start=args.start, end=args.end, timeframe=args.timeframe
    )
    config = BacktestConfig(
        starting_cash=args.cash,
        commission_pct=args.cost_bps / 10_000,
        slippage_pct=args.cost_bps / 10_000,
    )
    result = run_backtest(strat, data, config)
    r = result.report

    bps = lambda x: "—" if x != x else f"{x * 100:6.2f}%"  # noqa: E731
    num = lambda x: "—" if x != x else f"{x:6.2f}"  # noqa: E731
    print(f"\n  {result.strategy_name}  ·  {', '.join(symbols)}  ·  {len(result.equity_curve)} bars")
    print("  " + "-" * 48)
    print(f"  Total return     {bps(r.total_return)}")
    print(f"  CAGR             {bps(r.cagr)}")
    print(f"  Sharpe (annual)  {num(r.sharpe_ratio)}")
    print(f"  Sortino (annual) {num(r.sortino_ratio)}")
    print(f"  Volatility       {bps(r.annualized_volatility)}")
    print(f"  Max drawdown     {bps(r.max_drawdown)}")
    if r.trades:
        t = r.trades
        print(f"  Trades           {t.num_trades}")
        print(f"  Win rate         {bps(t.win_rate)}")
        print(f"  Profit factor    {num(t.profit_factor)}")
        print(f"  Expectancy/trade ${t.expectancy:,.2f}")
    if getattr(strat, "adf_pvalue", None) is not None:
        print(f"  ADF p-value      {num(strat.adf_pvalue)}  (cointegration: <0.05 is good)")
    final = float(result.equity_curve.iloc[-1])
    print(f"  Final equity     ${final:,.0f}  (from ${config.starting_cash:,.0f})")
    print("\n  Reminder: a backtest is a hypothesis, not a promise. See the web app's")
    print("  'pitfalls' section before trusting any number above.\n")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("trading_bot.web.app:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trading_bot", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list available strategies").set_defaults(func=cmd_list)

    bt = sub.add_parser("backtest", help="run a backtest")
    bt.add_argument("--strategy", required=True)
    bt.add_argument("--symbols", nargs="+", required=True)
    bt.add_argument("--start", default=None)
    bt.add_argument("--end", default=None)
    bt.add_argument("--source", default="yahoo", choices=["yahoo", "alpaca"])
    bt.add_argument("--timeframe", default="1Day")
    bt.add_argument("--cash", type=float, default=100_000.0)
    bt.add_argument("--cost-bps", type=float, default=5.0, help="commission+slippage, basis points")
    bt.add_argument("--set", action="append", default=[], help="strategy param, e.g. window=14")
    bt.set_defaults(func=cmd_backtest)

    sv = sub.add_parser("serve", help="launch the educational web app")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.add_argument("--reload", action="store_true")
    sv.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
