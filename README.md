# 📈 Trading Bot — An Educational Day-Trading Lab

> A hands-on, math-first introduction to algorithmic day trading of US stocks.
> Built for people who've taken intro statistics and know the basics of the stock market.

This project is **equal parts software and lesson**. It implements real trading
strategies, backtests them honestly on historical data, streams live market data,
and (eventually, carefully) places real trades — while a beautiful web page explains
the statistics behind every decision.

> ⚠️ **Not financial advice.** This is an educational tool. Day trading is risky and
> the large majority of retail day traders lose money. See the
> [Risks & Honest Caveats](#) section of the web app before risking real capital.

## Status

🚧 Under active construction. Architecture and content are being finalized from a
research pass (broker choice, free data APIs, backtesting approach, strategy math).

## Planned features

- **Four strategies, built to extend**: moving-average crossover, mean reversion
  (Bollinger / z-score), RSI momentum, and pairs trading (cointegration).
- **Honest backtester**: realistic transaction costs & slippage, look-ahead-bias
  guards, in-sample vs out-of-sample splits.
- **Live data** from free APIs.
- **Paper trading first**, with a clear path to real money.
- **Educational web page** with KaTeX-rendered math explaining every concept.
- **Full statistical treatment**: Sharpe, Sortino, max drawdown, plus the pitfalls
  (overfitting, multiple testing, survivorship bias).

## License

MIT — see [LICENSE](LICENSE).
