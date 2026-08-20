# WAVERUN V3 Data Gap Priority

| Rank | Missing data | Expected value | Cost/difficulty | Availability | Leakage risk |
|---:|---|---|---|---|---|
| 1 | Historical L2/order book | Very high | High | Exchange/vendor dependent | Low with timestamp discipline |
| 2 | Liquidations + open interest | High | Medium | Often purchasable | Medium |
| 3 | Cross-exchange order flow | High | High | Vendor dependent | Low |
| 4 | Funding + basis | Medium-high | Medium | Usually historical | Low |
| 5 | Options IV/skew | Medium-high | High | Limited intraday history | Medium |
| 6 | Point-in-time news/events | Medium | High | Fragmented | High |
| 7 | Vantage historical Bid/Ask metadata | Execution-critical | Medium | Broker dependent | Low |
| 8 | ETF flow timing | Medium | Medium | Coarse/delayed | High |
