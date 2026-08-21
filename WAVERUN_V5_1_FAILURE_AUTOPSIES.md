# WAVERUN V5.1 failure autopsies

Observed operational failure: the recorder persisted the decision-time MT5 quote but not the future Vantage Bid/Ask path required for outcome resolution.

Consequence: 21,468 candidates are real and causal at decision time, but none can be classified as target-first or adverse-first using the mandated execution truth. No model, calibration, product frontier, or gate-value claim was produced from unlabeled candidates.
