# WAVERUN V5.2 Ranking Failures

The ranker failed in three ways:

1. It learned Q1/Apr-Jun ordering that did not transfer to Jul-2026.
2. Daily Top-K selection did not create a meaningful winner/loser separation; the Jul top-k success rate was 11.6–28.4% across the tested models and directions.
3. The historical core lacks Vantage Bid/Ask and L2, so MAE/cost and microstructure ranking could not be proven with broker execution truth.

The logistic, HistGradientBoosting and ExtraTrees comparisons all failed the later-period and >=70% gates. No score monotonicity claim is made, no 90% elite class exists, and no automatic online learning or production retraining was added.

Final status: `NO ROBUST STRATEGY FOUND`; `WAVERUN_V5_2_RANKING_CHALLENGER_V1` is **NOT FROZEN**; execution remains `DISABLED`.
