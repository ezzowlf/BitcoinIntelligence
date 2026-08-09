# Bitcoin Best Historical Entries Study

> RESEARCH_ONLY. Outcome labels use future prices; every factor input obeys `available_at <= entry_timestamp`. No production score or rule was created.

## Method
- Independent episodes: **8**, minimum separation 90 days.
- Objective categories: long-term 365/730D, risk-adjusted, near local bottom, early recovery, capitulation.
- Controls: deterministic neutral observations and failed high-value candidates.
- Multiple testing: 16 declared factors and 7 economically predeclared combinations; no brute-force search.
- Weekly/monthly features use only closed higher-timeframe candles. Future prices are labels only.

## Real data coverage
- 1d: 5469 rows, 2011-08-18 00:00:00+00:00 to 2026-08-07 00:00:00+00:00
- 4h: 32812 rows, 2011-08-18 12:00:00+00:00 to 2026-08-08 00:00:00+00:00
- 1w: 781 rows, 2011-08-22 00:00:00+00:00 to 2026-08-03 00:00:00+00:00
- 1M: 180 rows, 2011-08-31 00:00:00+00:00 to 2026-07-31 00:00:00+00:00
- External coverage: see source rows below; missing history remains unavailable.

| metric | provider | min_time | max_time | rows |
| --- | --- | --- | --- | --- |
| active_addresses | coinmetrics-community-v4 | 2011-08-18 00:00:00+00:00 | 2026-08-08 00:00:00+00:00 | 5470 |
| exchange_balance_btc | coinmetrics-community-v4 | 2011-08-18 00:00:00+00:00 | 2026-08-08 00:00:00+00:00 | 5470 |
| exchange_inflows_usd | coinmetrics-community-v4 | 2011-08-18 00:00:00+00:00 | 2026-08-08 00:00:00+00:00 | 5470 |
| exchange_outflows_usd | coinmetrics-community-v4 | 2011-08-18 00:00:00+00:00 | 2026-08-08 00:00:00+00:00 | 5470 |
| fees_btc | coinmetrics-community-v4 | 2011-08-18 00:00:00+00:00 | 2026-08-08 00:00:00+00:00 | 5470 |
| funding_rate_8h | binance-usdm-public | 2019-09-10 08:00:00+00:00 | 2026-08-09 08:00:00.005000+00:00 | 7576 |
| hash_rate | coinmetrics-community-v4 | 2011-08-18 00:00:00+00:00 | 2026-08-08 00:00:00+00:00 | 5470 |
| issuance_btc | coinmetrics-community-v4 | 2011-08-18 00:00:00+00:00 | 2026-08-08 00:00:00+00:00 | 5470 |
| mvrv | coinmetrics-community-v4 | 2011-08-18 00:00:00+00:00 | 2026-08-08 00:00:00+00:00 | 5470 |
| open_interest_usd | binance-usdm-public | 2026-07-19 04:00:00+00:00 | 2026-08-09 08:00:00+00:00 | 509 |
| open_interest_usd | binance-vision-public-archive | 2020-09-01 00:00:00+00:00 | 2026-08-08 23:00:00+00:00 | 52010 |
| transaction_count | coinmetrics-community-v4 | 2011-08-18 00:00:00+00:00 | 2026-08-08 00:00:00+00:00 | 5470 |
| transfer_count | coinmetrics-community-v4 | 2011-08-18 00:00:00+00:00 | 2026-08-08 00:00:00+00:00 | 5470 |

## Top historical entry episodes

| rank | date | entry_price | return_30d | return_90d | return_365d | return_730d | MAE_365d | MFE_365d | days_to_local_low | entry_archetype | recognized_master |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2012-06-03 00:00:00+00:00 | 5.19 | 0.24084778420038533 | 0.909441233140655 | 22.741811175337183 | 128.12138728323697 | -0.009633911368015502 | 48.96917148362234 | -70 | HISTORICAL_SUPPORT_RETEST | False |
| 2 | 2016-09-01 00:00:00+00:00 | 571.05 | 0.0734261448209439 | 0.29946589615620356 | 7.618684878732161 | 11.582103143332459 | -0.007039663777252403 | 7.641975308641976 | -30 | HISTORICAL_SUPPORT_RETEST | False |
| 3 | 2020-03-16 00:00:00+00:00 | 5033.42 | 0.3150104700183971 | 0.8536084809135736 | 10.306098040695987 | 7.173917535194759 | -0.019354633628824947 | 11.274324415606088 | -3 | DEEP_CAPITULATION | True |
| 4 | 2019-02-14 00:00:00+00:00 | 3560.46 | 0.12064171483459996 | 1.3055138942720887 | 1.9108710672216516 | 12.264712986524215 | -0.0043758390769731426 | 2.898372682181516 | -61 | HISTORICAL_SUPPORT_RETEST | False |
| 5 | 2023-01-08 00:00:00+00:00 | 17119.0 | 0.35825690752964534 | 0.6337987031952801 | 1.7451953969273908 | 4.663064431333606 | -0.0006425608972486785 | 1.761901980255856 | -48 | HISTORICAL_SUPPORT_RETEST | False |
| 6 | 2024-09-07 00:00:00+00:00 | 54147.0 | 0.1489463866880898 | 0.8449406245960072 | 1.0526344949858717 |  | -0.009437272609747582 | 1.2996103200546658 | -33 | HISTORICAL_SUPPORT_RETEST | False |
| 7 | 2022-07-03 00:00:00+00:00 | 19294.46 | 0.19213079816693512 | 0.000909069235417892 | 0.6148676874087173 | 2.215067952147922 | -0.19774899116119338 | 0.6304161920053737 | -15 | DEEP_CAPITULATION | True |
| 8 | 2018-06-13 00:00:00+00:00 | 6307.4 | -0.014555918445001037 | -0.004345689190474622 | 0.3060849161302597 | 0.5003123315470717 | -0.5049814503598946 | 0.44224085994229023 | 16 | DEEP_CAPITULATION | False |

## Factor ranking

| factor | role | top_entry_frequency | control_frequency | top_entry_lift | median_365d_when_present | MAE_365d_when_present | timing | sample_size | confidence | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deep_drawdown | VALUE | 0.875 | 0.0 | 0.875 | 1.9108710672216516 | -0.009633911368015502 | EARLY | 7 | LOW | PROMISING |
| below_200d | VALUE | 0.75 | 0.1 | 0.65 | 1.0526344949858717 | -0.019354633628824947 | EARLY | 7 | LOW | PROMISING |
| high_value | VALUE | 0.625 | 0.0 | 0.625 | 1.7451953969273908 | -0.019354633628824947 | EARLY | 5 | LOW | PROMISING |
| extreme_drawdown | VALUE | 0.5 | 0.0 | 0.5 | 1.8280332320745212 | -0.011865236352899045 | EARLY | 4 | LOW | PROMISING |
| daily_rsi_extreme | VALUE | 0.375 | 0.0 | 0.375 | 0.6148676874087173 | -0.19774899116119338 | EARLY | 3 | LOW | PROMISING |
| capitulation | VALUE | 0.375 | 0.0 | 0.375 | 0.6148676874087173 | -0.19774899116119338 | EARLY | 3 | LOW | PROMISING |
| below_200w | VALUE | 0.375 | 0.0 | 0.375 | 1.7451953969273908 | -0.019354633628824947 | EARLY | 3 | LOW | PROMISING |
| oi_available | VALUE | 0.375 | 0.0 | 0.375 | 1.0526344949858717 | -0.009437272609747582 | EARLY | 3 | LOW | INSUFFICIENT_DATA |
| weekly_rsi_extreme | VALUE | 0.5 | 0.3 | 0.2 | 7.618684878732161 | -0.059879248115321415 | EARLY | 7 | LOW | PROMISING |
| major_support | TIMING | 1.0 | 0.8 | 0.19999999999999996 | 1.2905680679548033 | -0.08438533097848083 | MID | 16 | LOW | PROMISING |

## Predeclared combinations

| combination | n | median_365d | median_MAE_365d | top_share |
| --- | --- | --- | --- | --- |
| Deep Drawdown + Weekly RSI Extreme | 4 | 4.116776283070439 | -0.10855181239500916 | 1.0 |
| Deep Drawdown + Major Support | 7 | 1.9108710672216516 | -0.009633911368015502 | 1.0 |
| Major Support + Weekly RSI Extreme | 7 | 7.618684878732161 | -0.059879248115321415 | 0.5714285714285714 |
| High Value + Recovery | 0 |  |  |  |
| Capitulation + Recovery | 0 |  |  |  |
| Support + Fib Confluence | 0 |  |  |  |
| Deep Drawdown + MVRV<1 | 0 |  |  |  |

## Archetype performance

| entry_archetype | n | median_30d | median_90d | median_365d | median_MAE | median_delay |
| --- | --- | --- | --- | --- | --- | --- |
| DEEP_CAPITULATION | 3 | 0.19213079816693512 | 0.000909069235417892 | 0.6148676874087173 | -0.19774899116119338 | -3.0 |
| HISTORICAL_SUPPORT_RETEST | 5 | 0.1489463866880898 | 0.8449406245960072 | 1.9108710672216516 | -0.007039663777252403 | -48.0 |

## Fixed staged accumulation versus recovery confirmation

| variant | n | average_entry_ratio | median_MAE | median_365d | median_delay | capital_before_bottom | capital_after_bottom |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2_stage | 8 | 5387.8575 | -0.00541713852459258 | 1.8423048351132207 |  | 50.0 | 50.0 |
| 3_stage | 8 | 5293.673333333333 | -0.0036180330297977403 | 1.8470951691760438 |  | 33.0 | 67.0 |
| recovery_confirmed | 8 | 6042.49 | -0.09187157565262277 | 1.2860553149150462 | 10.0 | 0.0 | 100.0 |
| single_entry | 8 | 5670.41 | -0.010775247640313623 | 1.8280332320745212 |  | 100.0 | 0.0 |
These are exactly four predeclared research variants, not optimized strategies or production recommendations.

## Early versus late trade-off

| timing | factors | median_lift | median_MAE |
| --- | --- | --- | --- |
| EARLY | 12 | 0.375 | -0.019354633628824947 |
| LATE | 1 | -0.8 | -0.29840765521209683 |
| MID | 3 | 0.024999999999999994 | -0.05976280537792816 |
Recovery is classified as late confirmation. It was absent at the selected entry day in this sample; waiting for it necessarily changes the entry and cannot be presented as free risk reduction.

## Drawdown depth study

| bucket | n | median_365d | median_MAE |
| --- | --- | --- | --- |
| 80%+ | 1 | 1.9108710672216516 | -0.0043758390769731426 |
| 70-80% | 3 | 1.7451953969273908 | -0.019354633628824947 |
| 60-70% | 1 | 0.3060849161302597 | -0.5049814503598946 |
| 40-60% | 2 | 15.180248027034672 | -0.008336787572633952 |
| 20-40% | 1 | 1.0526344949858717 | -0.009437272609747582 |

## Weekly RSI buckets

| bucket | n | median_365d | median_MAE |
| --- | --- | --- | --- |
| <20 | 3 | 0.6148676874087173 | -0.19774899116119338 |
| 20-30 | 1 | 7.618684878732161 | -0.007039663777252403 |
| 30-40 | 1 | 1.0526344949858717 | -0.009437272609747582 |
| 40-50 | 1 | 1.7451953969273908 | -0.0006425608972486785 |
| 60-70 | 2 | 12.326341121279418 | -0.007004875222494322 |

## 2.3 / 2.5 / MASTER recognition and candidate completion

| rank | date | recognized_2_3 | recognized_2_5 | recognized_master | candidate_completion |
| --- | --- | --- | --- | --- | --- |
| 1 | 2012-06-03 00:00:00+00:00 | False | False | False | 0 |
| 2 | 2016-09-01 00:00:00+00:00 | False | False | False | 0 |
| 3 | 2020-03-16 00:00:00+00:00 | True | True | True | 100 |
| 4 | 2019-02-14 00:00:00+00:00 | True | False | False | 75 |
| 5 | 2023-01-08 00:00:00+00:00 | False | False | False | 0 |
| 6 | 2024-09-07 00:00:00+00:00 | False | False | False | 0 |
| 7 | 2022-07-03 00:00:00+00:00 | True | True | True | 100 |
| 8 | 2018-06-13 00:00:00+00:00 | True | False | False | 75 |

## Major-bottom timelines
For each selected episode the PIT sequence is: T-30/T-7 drawdown and momentum deterioration; T0 support/capitulation if present; T+7 early reclaim; T+30 recovery confirmation. T+7/T+30 states are explanatory outcomes, never entry inputs.

## Failed buys and controls
High-value candidates with non-positive 365D outcome: **5**. Neutral controls are deterministic 90-day samples, not random shuffles.

## Exit / reduce research
Objective worst-5% 90D downside sampling produced **9** independent research observations. No rejected SELL rule was revived.

## Major-bottom interpretation
The objective episode list includes cycle lows only when the labels select them. For each selected low, deep drawdown/value were knowable first; capitulation and support contact were contemporaneous; recovery was later confirmation and paid for reduced uncertainty with a higher entry price.

## BUY conclusion
Repeated deep drawdown/value context provides the earliest information. Historical support and depressed weekly momentum add discrimination. Recovery improves confirmation but is later; none of these findings is promoted to production.

## SELL / REDUCE conclusion
Research-only downside episodes; rejected SELL proxy remains rejected.

## Unchanged
MASTER 3.0 hierarchy, 2.5 Primary, 2.3 Control, frozen hashes, forward cutoff, Telegram production behavior, and execution `DISABLED` are unchanged.