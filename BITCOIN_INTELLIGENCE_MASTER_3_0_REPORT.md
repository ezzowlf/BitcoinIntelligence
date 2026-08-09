# Bitcoin Intelligence MASTER 3.0 Report

## Versions

- Control model: `2.3-FROZEN`, commit `0c55061`.
- Decision/forward layer: `2.4-DECISION`, baseline commit `7ad58e2`.
- Primary analysis model: `2.5-RARE-SIGNAL`, commit `10fcb7c`.
- Master model: `MASTER_3_0_FROZEN`; working state on branch `codex/bitcoin-master-3`.
- Execution: `DISABLED`.

MASTER is a domain hierarchy, not a vote or universal factor score. Fibonacci and historical zones share one price-structure independence group; RSI and Bollinger share momentum. Research-only, risk-only, unavailable and rejected factors retain their limitations.

## Current Bitcoin Master State

Last confirmed BTC close: 2026-08-07 UTC at **$64,877.77**.

| Decision | Current |
|---|---|
| Long-Term | ACCUMULATE |
| New Entry | ACCUMULATE |
| Existing Position | HOLD |
| Risk | CAUTION |
| Production Signal | NO_PRODUCTION_SIGNAL |
| Buy Candidate | BUY_CANDIDATE, 50.0% complete |
| Sell Candidate | WATCH_DISTRIBUTION, 16.7% complete |
| Confidence | MODERATE |

Completion describes fulfilled conditions, not a probability.

## Market Structure

- Value: `HIGH_VALUE`, 70.3.
- Cycle: `TRANSITION`.
- Regime: `BEAR`, LOW stability, 40% model agreement.
- Timing: `WAIT`, score 0.
- Distribution: `DISTRIBUTION_CANDIDATE`, confirmation `NOT_YET`.
- Model comparison: 2.3 says ACCUMULATE; 2.5 has no Production signal and a 50% Buy Candidate; MASTER says ACCUMULATE/HOLD. This is classified as aligned at the action level, not majority voting.

The positive drivers are attractive value, a -47.98% drawdown and high-confidence historical support. Negative drivers are the bearish/unstable regime, missing timing confirmation and an unconfirmed distribution candidate. MASTER waits for lower-low rejection, structure reclaim and H4/D1 confirmation.

## Levels

- Buy Zone 1: $63,176.58-$64,752.82, HIGH.
- Buy Zone 2: $61,243.72-$62,493.90, MODERATE.
- Major historical support: $55,244.90-$60,864.85, HIGH.
- Major resistance/former ATH context: $67,696.10-$80,327.60, HIGH but exhausted.
- Distribution zone: no confirmed zone; resistance is context only.
- Breakdown/invalidation: below $61,243.72 for the current tactical setup.

## Long-Term Context

- Current drawdown: -47.98%.
- Historical severity percentile: 47.58.
- Maximum measured historical drawdown: -84.86%.
- Days below previous ATH: 305.
- Recovery from last major low: +10.85%, state `DEEP_DRAWDOWN`.
- Weekly RSI: 41.56.
- Monthly RSI: 44.33.
- RSI_365D: 48.51, `RESEARCH`.
- Daily/Weekly/Monthly Bollinger: INSIDE / INSIDE / INSIDE.

Drawdown, RSI or Bollinger alone cannot trigger BUY or SELL.

## External Data

- Price: AVAILABLE.
- On-chain: AVAILABLE/PARTIALLY_VALIDATED.
- Funding and OI/derivatives: AVAILABLE, direction role limited to `RISK_ONLY`/`RESEARCH`.
- Macro: UNAVAILABLE.
- ETF: UNAVAILABLE.
- News: UNAVAILABLE.

Missing providers are not converted to neutral numeric values and reduce coverage. News, war, Black Friday, funding, RSI or Bollinger alone cannot trigger STRONG_SELL.

## Evidence

- Evidence: 60.38, MODERATE.
- Directional redundancy-adjusted confluence: MODERATE, supported by long-term value and price structure.
- Data quality: 76, MODERATE; critical feeds healthy.
- Uncertainty: 57.1, HIGH.
- Historical SELL proxy: `REJECTED`, direction role `NONE`.

## Historical MASTER Research

All results are `RESEARCH_ONLY`.

- MASTER signal book: 40 episodes: 9 BUY and 31 REDUCE.
- Production SELL: 0; status `DISABLED_FOR_PRODUCTION`.
- STRONG BUY/SELL: 0.
- BUY median: -1.31% at 30D, -4.31% at 90D, +6.44% at 180D, +56.22% at 365D (7 mature).
- BUY median 90D MAE/MFE: -21.64% / +12.30%.
- REDUCE median: +3.56% at 30D, +4.76% at 90D and +41.81% at 365D. REDUCE is therefore not validated as a robust exit action.
- Rejected 2.5 SELL proxy: 3 observations; 2/3 were 30D false sells. Median missed upside was +207.41%.

The three rejected dates remain visible in the error taxonomy. MASTER converts them to HOLD rather than hiding them. Missed-buy and missed-sell classification remains incomplete because a robust objective definition of every major rally/drawdown has not yet been frozen; no thresholds were retrofitted after observing these errors.

Active-year historical counts are recorded in `data/reports/master_30_research.json`. Years without a signal remain zero.

## Telegram Dry Run

```text
₿ BITCOIN MASTER

BTC
$64,877.77

LONG TERM
ACCUMULATE

NEW ENTRY
ACCUMULATE

EXISTING POSITION
HOLD

RISK
CAUTION

PRODUCTION
NO_PRODUCTION_SIGNAL

BUY CANDIDATE
50.0% (completion, not probability)

SELL CANDIDATE
16.7% (completion, not probability)

Execution: DISABLED
```

Commands: `/master`, `/buy`, `/sell`, `/levels`, `/drawdown` plus existing views. Automatic candidate alerts default to false. Persistent alert dedup remains active.

## Forward Validation

- MASTER forward start: `2026-08-10T00:00:00Z`.
- MASTER snapshots: 0.
- Forward Production signals: 0.
- Forward Candidates: 0.

The start remains conservative because funding/OI through 8/9 August was previously visible, while no completed price candle after 7 August was used. Each future snapshot stores 2.3, 2.5 and MASTER versions and decisions in an append-only table.

## Limitations

- No mature MASTER forward evidence exists.
- Historical BUY timing is weak at 30/90 days despite positive long-horizon results.
- SELL and REDUCE are not historically robust and remain disabled/unvalidated for Production use.
- Macro, ETF and news are unavailable in the current state.
- Historical zones and RSI/Bollinger combinations remain research context.
- Pine cannot reproduce Python/on-chain/derivatives MASTER states and therefore exposes only locally verifiable alerts.
- Signal frequency is observed, never optimized to a target corridor.

## Verification

- Full suite: 132 passed.
- Python compile: passed.
- Git whitespace check: passed.
- Dashboard smoke: HTTP 200.
- MASTER CLI and all five new Telegram commands: passed in dry-run; no message sent.
- Historical MASTER replay and explicit false-sell review: completed.
- 2020 PIT zone replay: no formation timestamp after cutoff.
- 2.3 semantic config hash and MASTER source hash: exact matches.
- Pine artifact: v6 declaration, closed-candle lookahead controls and no fabricated Python Production states verified statically. Final compilation in TradingView remains external.
