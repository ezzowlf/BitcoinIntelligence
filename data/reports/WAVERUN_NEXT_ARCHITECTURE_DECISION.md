# Next architecture decision

Do not build V7 yet. Preserve a future point-in-time `MarketLocationState` contract conceptually, but first collect enough historical OHLC/L2/Vantage-aligned data to evaluate FVG, zones, sweeps, VWAP and profile against matched bases. Current answer: old directional edge may contain information; location may add information; neither is sufficiently proven for a challenger.
