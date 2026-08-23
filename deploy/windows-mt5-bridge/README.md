# WAVERUN Windows all-in-one

Market-data and research-only profile. No order route exists and execution remains disabled.

- `install.ps1`: register per-user logon autostart.
- `start.ps1`, `stop.ps1`, `status.ps1`: lifecycle.
- Runtime data and PID files remain below ignored `runtime/`.
- Set `WAVERUN_LOCAL_TRUSTED=true` only for loopback-only access. For any remote binding, set `WAVERUN_DASHBOARD_PASSWORD_SHA256` and terminate TLS at a trusted reverse proxy.
- MT5 must be installed and logged in; the adapter retries temporary disconnects.
