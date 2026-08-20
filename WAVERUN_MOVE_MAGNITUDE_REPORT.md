# WAVERUN Move Magnitude Report

Every precision below means: **predicted endpoint direction correct AND maximum favorable excursion reached the stated magnitude**. It is not one-tick directional precision.

Prices are Binance research proxies at 5-second resolution. Movement is normalized to USD, basis points, and percent. Vantage broker points/pips, real spread, and real slippage remain unavailable.

Cell format: `precision; N; signals/day; proxy net endpoint EV; median MFE; median MAE`. N and frequency describe the independent V1 decisions evaluated in that cell; they are not the number of successful threshold hits.

| Minimum MFE | 30s | 60s | 90s | 180s | 300s |
|---:|---:|---:|---:|---:|---:|
| >=1bp | 54.09%; N159; 1.15/d; EV-0.84bp; MFE8.80; MAE5.10bp | 57.86%; N159; 1.15/d; EV+2.31bp; MFE12.15; MAE8.43bp | 57.86%; N159; 1.15/d; EV+4.58bp; MFE14.12; MAE10.79bp | 63.52%; N159; 1.15/d; EV+6.59bp; MFE24.18; MAE15.96bp | 63.52%; N159; 1.15/d; EV+7.98bp; MFE28.07; MAE17.76bp |
| >=2bp | 54.09%; N159; 1.15/d; EV-0.84bp; MFE8.80; MAE5.10bp | 57.86%; N159; 1.15/d; EV+2.31bp; MFE12.15; MAE8.43bp | 57.86%; N159; 1.15/d; EV+4.58bp; MFE14.12; MAE10.79bp | 63.52%; N159; 1.15/d; EV+6.59bp; MFE24.18; MAE15.96bp | 62.89%; N159; 1.15/d; EV+7.98bp; MFE28.07; MAE17.76bp |
| >=5bp | 51.57%; N159; 1.15/d; EV-0.84bp; MFE8.80; MAE5.10bp | 54.72%; N159; 1.15/d; EV+2.31bp; MFE12.15; MAE8.43bp | 57.86%; N159; 1.15/d; EV+4.58bp; MFE14.12; MAE10.79bp | 62.89%; N159; 1.15/d; EV+6.59bp; MFE24.18; MAE15.96bp | 62.89%; N159; 1.15/d; EV+7.98bp; MFE28.07; MAE17.76bp |
| >=10bp | 40.88%; N159; 1.15/d; EV-0.84bp; MFE8.80; MAE5.10bp | 49.69%; N159; 1.15/d; EV+2.31bp; MFE12.15; MAE8.43bp | 52.20%; N159; 1.15/d; EV+4.58bp; MFE14.12; MAE10.79bp | 59.75%; N159; 1.15/d; EV+6.59bp; MFE24.18; MAE15.96bp | 61.64%; N159; 1.15/d; EV+7.98bp; MFE28.07; MAE17.76bp |
| >=15bp | 28.93%; N159; 1.15/d; EV-0.84bp; MFE8.80; MAE5.10bp | 41.51%; N159; 1.15/d; EV+2.31bp; MFE12.15; MAE8.43bp | 43.40%; N159; 1.15/d; EV+4.58bp; MFE14.12; MAE10.79bp | 55.35%; N159; 1.15/d; EV+6.59bp; MFE24.18; MAE15.96bp | 57.23%; N159; 1.15/d; EV+7.98bp; MFE28.07; MAE17.76bp |
| >=20bp | 19.50%; N159; 1.15/d; EV-0.84bp; MFE8.80; MAE5.10bp | 34.59%; N159; 1.15/d; EV+2.31bp; MFE12.15; MAE8.43bp | 41.51%; N159; 1.15/d; EV+4.58bp; MFE14.12; MAE10.79bp | 47.17%; N159; 1.15/d; EV+6.59bp; MFE24.18; MAE15.96bp | 52.20%; N159; 1.15/d; EV+7.98bp; MFE28.07; MAE17.76bp |
| >=30bp | 10.06%; N159; 1.15/d; EV-0.84bp; MFE8.80; MAE5.10bp | 22.01%; N159; 1.15/d; EV+2.31bp; MFE12.15; MAE8.43bp | 29.56%; N159; 1.15/d; EV+4.58bp; MFE14.12; MAE10.79bp | 39.62%; N159; 1.15/d; EV+6.59bp; MFE24.18; MAE15.96bp | 42.14%; N159; 1.15/d; EV+7.98bp; MFE28.07; MAE17.76bp |
| >=50bp | 3.14%; N159; 1.15/d; EV-0.84bp; MFE8.80; MAE5.10bp | 7.55%; N159; 1.15/d; EV+2.31bp; MFE12.15; MAE8.43bp | 10.69%; N159; 1.15/d; EV+4.58bp; MFE14.12; MAE10.79bp | 18.87%; N159; 1.15/d; EV+6.59bp; MFE24.18; MAE15.96bp | 26.42%; N159; 1.15/d; EV+7.98bp; MFE28.07; MAE17.76bp |

## Existing 101 directional winners at 180s

- Median MFE: 37.65 bp / $301.38
- MFE P25/P75: 19.95 / 58.24 bp
- Median MAE: 6.24 bp / $51.30
- Median endpoint: 25.03 bp / $197.83
- Median time to MFE: 145s
- Tradeable under the 3bp proxy cost + 2bp safety definition: 100/101

## Core answer

No tested magnitude/horizon cell reaches 3-10 independent V1 signals/day with >=70% combined direction-and-magnitude precision and positive proxy net EV. No reliable 80-90% magnitude class exists. V1 produces only 1.15 signals/day before any magnitude requirement.

Execution remains `DISABLED`. V1 remains immutable and `FAILED`.
