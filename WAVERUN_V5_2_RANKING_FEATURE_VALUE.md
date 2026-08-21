# WAVERUN V5.2 Ranking Feature Value

The ablation was evaluated with identical chronological folds and daily Top-3/5/7/10 selection.

- PRICE_ONLY was the strongest of the tested feature sets in several Apr-Jun cells, indicating that adding flow/cross-market features did not reliably reorder winners.
- CORE (price + flow + cross-market + MACD + regime) did not improve Jul ranking; the best Jul result remained below 29%.
- CORE_NO_MACD did not improve Jul and therefore MACD has no demonstrated ranking value.
- L2, depletion, replenishment, microprice, resilience, derivatives and Coinbase had no coverage in the historical core tier; their ranking value is `NOT ESTIMABLE`, not zero.
- No booster or blocker passed the requirement of improving later-period ranking while preserving chronological stability.

The result rejects the current ranker rather than assigning unsupported feature importance.
