# Bitcoin Intelligence TradingView Indicator

The indicator uses Pine Script v6 and deliberately implements only chart-local calculations. TradingView's official documentation identifies v6 as the current language version. Paste `tradingview/bitcoin_intelligence_indicator.pine` into Pine Editor, save it and add it to a BTC chart.

Default display shows dynamic ATR-width support/resistance areas, the 0.618 swing Fibonacci level, RSI/drawdown tables and six local alerts. Bollinger overlays and less important layers are optional to avoid chart overload.

## Modes and limitations

`PURE PINE` calculates RSI, moving statistics, Bollinger bands, ATH drawdown, rolling major low/recovery, swing levels and local support/resistance. `ENGINE ASSISTED` is only a visible placeholder for later manual state display; the script does not bypass TradingView restrictions or claim an API synchronization.

On-chain, funding, open interest, the Python regime ensemble, evidence and Rare Signal Challenger are never fabricated in Pine. Consequently the indicator labels only local conditions and never emits `STRONG_BUY` or `STRONG_SELL`.

Available alerts: major support entered, major resistance entered, Weekly RSI extreme, Weekly Bollinger extreme, support breakdown and resistance breakout. They are analytical events, not orders. Execution remains disabled.

Python and Pine use Wilder RSI, population-standard-deviation Bollinger bands, cumulative ATH drawdown and closed higher-timeframe candles. Small feed/session differences may remain. TradingView compilation must be confirmed in Pine Editor because no local Pine compiler is included.
