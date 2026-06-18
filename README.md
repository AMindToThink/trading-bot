# 📈 TradingLab — An Educational Day-Trading Bot

> A hands-on, **math-first** introduction to algorithmic day trading of US stocks — built
> for people who've taken intro statistics and know the basics of the market.

TradingLab is equal parts **software** and **lesson**. It implements four classic trading
strategies, backtests them *honestly* on real historical data, streams live market data,
and (carefully, eventually) places real trades — while a beautiful web page explains the
statistics behind every decision.

> ⚠️ **Not financial advice.** Day trading is risky and the large majority of retail day
> traders lose money (Taiwan: >80% lose; Brazil: 97% of those who persist lose). This is a
> tool for *understanding*, not a get-rich scheme. Learn on paper money. See the
> **Reality check** and **Pitfalls** sections of the web app before risking a cent.

---

## What's inside

| Layer | What it does |
|-------|--------------|
| **`indicators.py`** | SMA, EMA, Bollinger/z-score, Wilder RSI — pure, causal, unit-tested functions |
| **`backtest/`** | Event-driven engine (look-ahead-safe), portfolio with costs/slippage, full metrics |
| **`strategies/`** | MA crossover, mean reversion, RSI, pairs trading — extensible via a registry |
| **`data/`** | Yahoo (free daily history) + Alpaca (real-time IEX bars & stream) |
| **`broker/`** | Pluggable broker interface, Alpaca paper/live, risk guards, Schwab migration path |
| **`live/`** | Live runner that reuses the *exact same* strategy code as the backtester |
| **`web/`** | FastAPI backend + a single-page educational site with KaTeX math & live charts |

### The four strategies

1. **Moving-average crossover** — trend following. \(\mathrm{EMA}_t = \alpha P_t + (1-\alpha)\mathrm{EMA}_{t-1}\), golden/death cross.
2. **Mean reversion (Bollinger / z-score)** — fade extremes. \(z_t = (P_t-\mu_t)/\sigma_t\).
3. **RSI momentum** — Wilder's oscillator, buy oversold / exit at the midline.
4. **Pairs trading (cointegration)** — stat-arb on a mean-reverting spread (OLS hedge ratio + ADF test).

---

## Quickstart

This project uses [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync                       # install dependencies

# Launch the educational web app (then open http://127.0.0.1:8000)
uv run python -m trading_bot.cli serve
#   ...or directly:
uv run python -m uvicorn trading_bot.web.app:app --reload

# Backtest from the terminal
uv run python -m trading_bot.cli list
uv run python -m trading_bot.cli backtest --strategy rsi --symbols AAPL \
    --start 2022-01-01 --end 2024-12-31 --set window=14

# Pairs trade
uv run python -m trading_bot.cli backtest --strategy pairs --symbols KO PEP

# Run the tests
uv run pytest
```

No API keys are needed for backtesting or the web app — they use free Yahoo daily data.

---

## How look-ahead bias is prevented

The single most common way a backtest *lies* is by peeking at the future. The engine
structurally prevents it:

```
for each bar t:
    1. fill orders decided on bar t-1, at THIS bar's OPEN
    2. let the strategy decide using data only up to THIS bar's CLOSE
    3. mark the portfolio to market at the close
```

A decision made on the close of bar `t` is queued and filled at the **open of bar `t+1`** —
so the bot can never trade on information it wouldn't have had. Indicators are causal by
construction (the value at `t` depends only on prices `≤ t`).

---

## Adding your own strategy

The registry makes strategies plug-and-play — no other file needs to change:

```python
from trading_bot.strategies.base import Strategy, Param, register

@register("my_strategy")
class MyStrategy(Strategy):
    name = "My Strategy"
    blurb = "One-line description shown in the UI."

    @classmethod
    def param_spec(cls):
        return [Param("threshold", 1.5, "float", "Threshold", "What it does.")]

    def __init__(self, symbol, threshold=1.5):
        self.symbol, self.threshold = symbol, threshold

    def required_symbols(self):
        return [self.symbol]

    def prepare(self, data):
        ...  # precompute causal indicators over data[self.symbol]

    def on_bar(self, t, ctx):
        ...  # ctx.order_target_percent(self.symbol, 0.95), etc.
```

Import it in `trading_bot/strategies/__init__.py` and it appears in the CLI, the API, and
the web form automatically.

---

## From paper trading to real money

The bot talks to brokers only through a `Broker` abstraction, so the path is a swap, not a
rewrite. **Validate everything on Alpaca paper trading first** — it's free, instant, uses
real-time data, and shares the exact same code path as live.

1. Get free **Alpaca** paper-trading keys at <https://alpaca.markets/>, copy `.env.example`
   to `.env`, and fill them in (`.env` is gitignored — never commit secrets).
2. Run and validate the strategy on paper for a meaningful period.
3. Only then consider real money. **Schwab** (the documented `SchwabBroker` stub) supports
   real equity orders but has **no usable paper sandbox** — every order is live money — and
   a multi-day app approval. Start tiny.
4. Always wrap a live broker in a `RiskGuard` (kill switch, per-order notional cap, max
   positions, day-trade limit) and set `allow_live_trading=True` explicitly.

**Know the rules** (surfaced in the app's "Real money" section): the Pattern Day Trader
$25k rule (being replaced by FINRA's intraday-margin framework, effective June 4 2026 with
an 18-month phase-in), cash-account settlement violations (T+1), and the wash-sale rule for
taxes. Verify your broker's current policy in writing.

---

## Project layout

```
trading_bot/
  indicators.py            # SMA / EMA / Bollinger / RSI (causal, tested)
  config.py                # env-based secrets (fail-loud)
  cli.py                   # `python -m trading_bot.cli ...`
  backtest/{engine,portfolio,metrics}.py
  strategies/{base,ma_crossover,mean_reversion,rsi,pairs}.py
  data/{base,yahoo,alpaca}.py
  broker/{base,alpaca_broker,schwab_broker}.py
  live/runner.py
  web/{app.py, page_template.html, lessons.json, static/}
scripts/build_page.py      # injects lessons.json -> static/index.html
tests/                     # 57 unit/integration tests
```

The educational prose lives in `web/lessons.json`; after editing it (or the template) run
`uv run python scripts/build_page.py` to rebuild the served page.

## License

MIT — see [LICENSE](LICENSE). **Not financial advice. Use at your own risk.**
