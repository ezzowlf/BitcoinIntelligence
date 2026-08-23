# WAVERUN PRODUCT DEPLOYMENT STATUS

## Current usable profile

Windows all-in-one, loopback-only dashboard at `http://127.0.0.1:8501`.

- Live Vantage BTCUSD Bid/Ask: available
- Binance Spot/Futures/L2: connected
- Forward validator: running, provisional and unverified
- Manual paper LONG/SHORT and manual exit: available
- Browser console: clean in live acceptance
- Mobile 390x844: no horizontal overflow
- Execution: disabled

## Security boundary

Loopback uses explicit `WAVERUN_LOCAL_TRUSTED=true`. Any non-loopback deployment is locked unless `WAVERUN_DASHBOARD_PASSWORD_SHA256` is supplied. The Linux template terminates HTTPS with Caddy and does not expose Streamlit directly.

## External blockers

Remote secure access, HTTPS certificate issuance, remote-device acceptance, Linux benchmark, and reboot recovery cannot be proven without a configured hostname/Linux host and permission for a host reboot. They remain **NOT VERIFIED**, not silently treated as passed.
