# WAVERUN V5.1 Vantage tick-path acceptance

Acceptance folder: `runtime/waverun_v5_1/vantage_acceptance_20260821` (git-ignored).

- Real MT5/Vantage connection: `ONLINE`, symbol `BTCUSD`, terminal connected and logged in.
- The 12-minute run persisted 1,578 append-only Vantage records from `2026-08-21T19:37:31.405000Z` through `2026-08-21T19:49:36.774000Z` (725.369 seconds).
- Each record contains `time_msc`, UTC `timestamp`, `bid`, `ask`, `last`, `flags`, and `spread`.
- `time_msc` was unique and monotonic: 0 backwards timestamps, 0 duplicate ticks, 0 missing bids, 0 missing asks, 0 crossed quotes.
- Quote gaps: 150 gaps greater than one second; median gap 0.252 seconds; maximum gap 5.365 seconds. These are measured gaps, not filled values.
- 708 pre-gate candidates were produced. Candidate and decision timestamps are UTC and the resolver uses the persisted future Vantage path, not Binance prices.
- For `$100 target / $25 adverse / 60s`, 652 candidates had complete horizons: 27 target-first, 472 adverse-first, 153 neither; 56 were correctly marked `INSUFFICIENT_DATA` because the horizon extended beyond capture end.
- For `$150 / $50 / 60s`, 652 complete: 0 target-first, 234 adverse-first, 418 neither.
- For `$500 / $150 / 60s`, 652 complete: 0 target-first, 5 adverse-first, 647 neither.
- Resolver uses executable prices: LONG enters at ask and exits at bid; SHORT enters at bid and exits at ask. MFE/MAE and time-to-target/adverse are calculated from that same path.
- Restart test: same recorder/output restarted for 8 seconds; tick file grew from 1,578 to 1,621 records, proving append-only restartability.
- `execution` remains `DISABLED`; no 6-hour run was started.
