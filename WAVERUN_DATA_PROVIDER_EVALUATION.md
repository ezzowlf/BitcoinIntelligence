# WAVERUN data-provider evaluation

Status: research-only evaluation. No account was created, no paid API was
called, and no historical count is inferred from provider documentation.

| Provider | Relevant coverage | Fit for WAVERUN | Limitation |
| --- | --- | --- | --- |
| Tardis.dev | Tick trades, quotes, L2 updates/snapshots, derivative tick data and liquidations; exchange-native timestamps plus local capture timestamps | Best fit for a reproducible multi-venue raw event lake and replay/import adapter | Commercial access for unrestricted history; Binance Spot book data is documented as 100 ms aggregated, so it is not equivalent to full L3 |
| Kaiko | Institutional multi-venue market-data product; evaluate only after confirming the exact BTC venue/channel entitlement and timestamp semantics | Potential enterprise alternative | No purchase or entitlement validation was performed in this build |
| Amberdata | Historical trades, order-book events/snapshots, derivatives and liquidation coverage are documented across Binance, Bybit and Coinbase-related venues | Useful for cross-checks and analytics; weaker fit as the sole raw replay source where one-minute snapshots are all that is available | Endpoint granularity differs by product; analytics endpoints must not be mistaken for tick-level raw history |
| CoinAPI | Broad exchange market-data API candidate | Adapter can be added after exact venue/channel contract is selected | Coverage, retention and cost were not validated with credentials |

## Recommendation

Use direct public exchange WebSockets for the live auxiliary feeds and the
read-only MT5 bridge for Vantage primary truth. For a paid historical source,
Tardis is the strongest first candidate because its documented model exposes
raw/tick-level trades, book updates, quotes, derivatives and liquidations in a
replayable format. This is a recommendation for a future procurement decision,
not evidence that WAVERUN has purchased or accessed the data.

Amberdata is a sensible secondary validation source for coverage and
cross-exchange analytics. Kaiko and CoinAPI remain procurement candidates until
their exact BTCUSDT/BTCUSD venue coverage, L2 semantics, retention and pricing
are confirmed for the required horizons.

## Evidence and constraints

The provider descriptions were checked against their current public
documentation on 2026-08-19. Tardis documents normalized tick-level trades,
incremental L2, snapshots, quotes, derivative tickers and liquidations, plus
local capture timestamps. It also documents venue-specific limitations such as
Binance Spot book updates aggregated at 100 ms. Amberdata documents historical
coverage tables and separate order-book/liquidation endpoints with venue- and
granularity-specific limits.

This repository report intentionally does not claim Vantage history,
Binance/Bybit/Coinbase historical counts, lead/lag, or a proven edge. Those
require actual data acquisition, timestamp audits, realistic bid/ask execution
simulation, and chronological out-of-sample validation.
