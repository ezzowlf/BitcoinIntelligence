# WAVERUN V5.1 Strategy Research

## Result

**NO ROBUST STRATEGY FOUND.** This bounded research used 3,663,360 rows from 212 existing derived daily Parquets, 9 predeclared mechanism families, 6 targets ($100/$150/$200/$300/$400/$500), 6 horizons (3m/5m/10m/15m/30m/60m), LONG/SHORT and 3 chronological folds. It produced 1,944 result cells. No locked 2026-08-16 or 2026-08-17 data was opened.

The historical tier contains Spot/Futures flow, CVD, pressure, acceleration, lead/lag, expansion, regime and MACD features. It does not contain historical Vantage Bid/Ask ticks. Results therefore use an explicit $17 round-trip cost proxy and are not Vantage-execution proof. The live Vantage tier is kept separate.

## Folds

- `train_q1`: Q1 2025
- `walk_forward_blind_2025`: Apr-Jun 2025
- `walk_forward_jul_2026`: Jul 2026

The strongest nominal cell was LONG absorption reversal, `$100`, 60m, blind-2025: N=35,730, precision=69.56%, signals/day=392.64, net terminal EV proxy=$5.71, median MAE=-$190.17. It is not a product result: the Jul-2026 fold fell to 50.86%, and the frequency is far above 3-10 independent opportunities/day.

The best low-frequency family was mean-reversion confirmed, but it still produced about 186-198 signals/day at `$100/60m` and did not provide stable precision or EV. All families were rejected for product use.

## Data limitations

No historical Vantage path, L2 depth history, liquidation/OI history or Coinbase path was present in this compatible tier. Those feature families were not silently imputed. Execution remains `DISABLED`.
