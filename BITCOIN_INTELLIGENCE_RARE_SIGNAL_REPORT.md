# Bitcoin Intelligence 2.5 Rare Signal Report

## Model boundary

- Champion remains `2.3-FROZEN`; semantic config hash unchanged.
- New model: `RARE_SIGNAL_CHALLENGER_1`, status `CHALLENGER`.
- All historical results are `RESEARCH_ONLY`; no OOS claim.
- Forward start remains `2026-08-10T00:00:00Z`.
- Execution remains `DISABLED`.

Production, candidate and diagnostic layers are stored and displayed separately. Signal frequency was measured only after economically motivated rules were fixed; no threshold was tuned to reach a target count.

## Current real state (2026-08-07 close)

| Field | Result |
|---|---|
| BTC | $64,877.77 |
| Production | NO_PRODUCTION_SIGNAL |
| Rare buy state | ACCUMULATE |
| Buy candidate | BUY_CANDIDATE, 50.0% complete |
| Sell state | WATCH_DISTRIBUTION |
| Sell candidate | 16.7% complete |
| Distribution | DISTRIBUTION_CANDIDATE, not confirmed |

The buy candidate has value, deep drawdown and historical support, but lacks momentum extreme, capitulation and timing confirmation. The sell watch has only one group; valuation, weekly structure break, momentum breakdown, derivatives and ETF confirmation are missing. This is not a SELL.

## Historical signal book

The causal research proxy produced 82 independent episodes: 12 Production proxies and 70 Candidate episodes. Production contains 9 BUY and 3 SELL observations; no STRONG_BUY or STRONG_SELL occurred. Calendar years with no Production signal remain zero.

| Type | Episodes | Median 30D | Median 90D | Median 365D | Median 90D MAE | Median 90D MFE |
|---|---:|---:|---:|---:|---:|---:|
| BUY | 9 | -1.31% | -4.31% | +56.22% (n=7 mature) | -21.64% | +12.30% |
| ACCUMULATE | 39 | +1.59% | +2.46% | +38.54% (n=33 mature) | -15.59% | +26.56% |
| REDUCE | 31 | +3.56% | +4.76% | +41.81% (n=28 mature) | -24.14% | +23.52% |
| SELL | 3 | +21.37% | +156.31% | +547.73% | -8.05% | +207.41% |

The result is deliberately unfavorable to the current SELL proxy: two of three SELL observations meet the documented 30D false-sell definition, and median missed upside across all three was +207.41%. Therefore the historical SELL rule is `REJECTED` for promotion. It remains research evidence for making the production SellOpportunityEngine stricter. REDUCE is not a full sell and is kept separate.

Observed per-active-year ranges were BUY 1-3, SELL 1-2, ACCUMULATE 1-8 and REDUCE 1-7. Years omitted from a state-specific range had zero signals.

## Major bottoms and tops

- 2014/15: 9 ACCUMULATE, 2 BUY.
- 2018: 9 ACCUMULATE, 1 BUY, 1 REDUCE.
- March 2020 window: 1 ACCUMULATE, 1 BUY.
- 2021/22 through mid-2023: 6 ACCUMULATE, 3 BUY, 2 REDUCE.
- 2013 top window: 4 REDUCE, 1 SELL, plus 2 accumulation observations.
- 2017 top window: 8 REDUCE, 2 SELL, plus 3 later accumulation observations.
- 2021 top window: 6 REDUCE but no validated SELL.

2011 cannot be evaluated by this proxy because the required 365-day warm-up is unavailable. The top review confirms that early warning is easier than a reliable SELL; those SELL observations failed outcome validation.

## Holiday research

All samples use algorithmically calculated dates.

| Event (±14D) | Samples | Median return | Win rate | Worst window drawdown |
|---|---:|---:|---:|---:|
| Thanksgiving | 15 | +7.33% | 53.3% | -46.68% |
| Black Friday | 15 | +7.42% | 60.0% | -49.25% |
| Christmas | 15 | +0.16% | 53.3% | -56.52% |
| New Year | 15 | +4.21% | 60.0% | -51.26% |

Black Friday is not a standalone sell factor: its median was positive and dispersion was very high. Status remains `RESEARCH/RISK_ONLY`; it may alert only with actual distribution, leverage and weakening structure.

No PIT geopolitical event library is available. No war, severity or reaction history was invented; geopolitical/news conclusions remain `UNAVAILABLE`. News alone cannot produce STRONG_SELL.

## Interfaces and forward evidence

Telegram automatic state flow remains Production-only. `/candidates` exposes completion and missing conditions; `/signals` exposes the current Production state and zero-start forward evidence. Candidate and Production events can be appended separately to the immutable rare-signal ledger only at or after Forward Start.

Forward Production BUY episodes: 0. Forward Production SELL episodes: 0.

Main weaknesses: small and era-dependent Production samples, rejected historical SELL timing, incomplete ETF/news/macro history, no intraday event-reaction history, and no mature forward observations.
