# WAVERUN HOST BENCHMARK

Measured 2026-08-24 on the active Windows all-in-one host under live WAVERUN load.

## Windows host

- CPU load snapshot: **17%**
- RAM: **31.18 GB total / 14.14 GB free**
- Dashboard health latency: **64.49 ms** loopback
- Binance API RTT: **386.80 ms**
- Vantage recorder throughput: **143.8 bytes/s**
- Binance/L2 raw event throughput sample: **314,345.6 bytes/s**
- Decision-record throughput sample: **2,632.6 bytes/s**
- Uncompressed aggregate estimate: **25.518 GB/day**, **178.626 GB/week**, **765.54 GB/30 days** at the sampled burst rate

The raw event stream must remain in partitioned/compressed retention storage; it must not be moved into the operational SQLite database. The estimate is a short burst sample and must be remeasured over 24 hours before capacity procurement.

## Linux comparison

**NOT RUN — no Linux host, hostname, SSH target, or service credentials were available.**

## Deployment decision

**WINDOWS ALL-IN-ONE for the currently verified usable deployment.**

The preferred future architecture remains hybrid Linux + Windows MT5 bridge, but it cannot be selected or called remotely accepted until the actual Linux host is benchmarked and its authenticated HTTPS ingestion path is exercised.
