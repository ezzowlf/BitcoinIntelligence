# WAVERUN V5.2 Opportunity Ranking Report

## BEST TOP-K CONFIGURATION

No production-worthy configuration. The highest Jul-2026 `$100/300s` top-k result was only **28.39%** (HistGradientBoosting, CORE, SHORT, Top-5), with 155 signals over 31 days. The best Apr-Jun result was **55.68%** (HistGradientBoosting, CORE_NO_MACD, LONG, Top-3), but it collapsed in Jul.

The ranker produced exactly 3/5/7/10 selections on every test day; zero-signal abstention was not triggered by this permissive research floor. That is itself a failure of the quality floor, not evidence for forcing signals.

Models compared: Regularized Logistic, HistGradientBoosting, ExtraTrees. Feature sets: PRICE_ONLY, CORE, CORE_NO_MACD. All were trained on Q1-2025 and scored unseen Apr-Jun-2025 and Jul-2026 days.

| Model / features | Direction | Period | Top-K | Target | Success | Net-positive |
|---|---|---|---:|---:|---:|---:|
| HistGradientBoosting / CORE_NO_MACD | LONG | Apr-Jun 2025 | 3/day | $100 | 55.68% | 53.85% |
| HistGradientBoosting / CORE | SHORT | Jul 2026 | 5/day | $100 | 28.39% | 46.45% |
| ExtraTrees / PRICE_ONLY | LONG | Jul 2026 | 3/day | $100 | 26.88% | 49.46% |

No result meets the 70% OOS requirement, and no V5.2 challenger is frozen.
