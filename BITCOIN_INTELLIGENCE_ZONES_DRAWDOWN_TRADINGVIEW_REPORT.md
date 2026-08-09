# Bitcoin Intelligence 2.5 Zones, Drawdown and TradingView Report

## Current analysis

- Algorithmic historical zones: 27 total; 15 support, 1 resistance and 11 previous-ATH clusters.
- Nearest historical support: $55,244.90-$60,864.85, strength 82.8/HIGH, three independent reactions.
- Nearest former-ATH area: $47,220.35-$66,635.64, strength 100/HIGH; exhaustion is high, so its touch count is not treated as automatically bullish.
- Nearest historical resistance: $95,195.96-$100,983.04, strength 70.5/MODERATE.
- Existing tactical buy zone 1: $63,176.58-$64,752.82.
- Existing tactical buy zone 2: $61,243.72-$62,493.90.
- Challenger sell/distribution zone: none confirmed. Former ATH $67,696.10-$80,327.60 is context, not an active SELL target.

## Drawdown and recovery

- Current ATH drawdown: -47.98%.
- Historical severity percentile: 47.58.
- Maximum automatically measured historical drawdown: -84.86%.
- Days below previous ATH: 305.
- Last major low: 2026-06-30.
- Recovery from that low: +10.85%.
- State: DEEP_DRAWDOWN.
- Detected peak-to-trough cycles: 16.

## Momentum and Bollinger

| Metric | Current |
|---|---:|
| 4H RSI | 52.53 |
| Daily RSI | 54.48 |
| Weekly RSI | 41.56 |
| Monthly RSI | 44.33 |
| RSI_365D | 48.51 / RESEARCH |
| Daily Bollinger | INSIDE |
| Weekly Bollinger | INSIDE |
| Monthly Bollinger | INSIDE |

No current RSI or Bollinger extreme supports a rare Production BUY or SELL.

## Validation conclusions

1. Historical zones add interpretable location context, but forward evidence is zero; BUY-timing improvement is not validated.
2. Historical resistance did not rescue the historical SELL proxy; SELL timing remains rejected.
3. Weekly RSI is useful as `TIMING_ONLY/RESEARCH`, not a standalone signal.
4. RSI_365D remains `RESEARCH` because it is non-standard and era-sensitive.
5. Weekly Bollinger is `TIMING_ONLY/RESEARCH`; current state is not extreme.
6. Drawdown percentile distinguishes depth but does not confirm a bottom; status `PARTIALLY_VALIDATED` as context.
7. Recovery state adds regime context, with forward value not yet established.
8. No combination is robust enough for promotion without forward data. Ablations are presently `NOT_IDENTIFIABLE_WITHOUT_FORWARD_SAMPLE`.

## TradingView

`tradingview/bitcoin_intelligence_indicator.pine` uses Pine Script v6 and implements local RSI, Bollinger, ATR-width support/resistance, swing Fibonacci, ATH drawdown, time under ATH and recovery. It provides alerts for support/resistance entry, Weekly RSI/Bollinger extremes and confirmed local breaks.

It does not fabricate on-chain, derivatives, evidence, regime or Rare Signal states. Pine-local signals are analytical labels only. Python reference formulas are covered by tests, but final TradingView compilation remains to be confirmed in Pine Editor because no local Pine compiler is available.

Known limitations: historical-zone clusters are based on price/ATR rather than full volume-profile data; ETF/news/geopolitical PIT history is incomplete; early Bitcoin has limited indicator warm-up; all historical signal conclusions remain research-only.
