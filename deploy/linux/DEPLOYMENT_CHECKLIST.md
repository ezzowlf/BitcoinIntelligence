# WAVERUN later Linux deployment checklist

Do not run this checklist until a real Linux host, hostname, and TLS owner are supplied.

Required environment variables (environment/secret manager only):

```text
DOMAIN=waverun.example.com
WAVERUN_HOSTNAME=${DOMAIN}
WAVERUN_DASHBOARD_PASSWORD_SHA256=<sha256-of-login-password>
WAVERUN_API_AUTH_TOKEN=<random-bridge-token>
WAVERUN_MT5_BRIDGE_TOKEN=<random-bridge-token>
WAVERUN_SERVER_URL=https://${DOMAIN}
WAVERUN_DATABASE_PATH=/var/lib/waverun/database/waverun_product.db
WAVERUN_STORAGE_PATH=/var/lib/waverun/runtime
```

Checklist:

- Create the Linux service account and private storage paths.
- Provision DNS for `DOMAIN` and Caddy certificates.
- Start API/dashboard behind Caddy; never expose Streamlit port 8501 directly.
- Configure bridge token in the Windows bridge and server environment.
- Verify idempotent tick ingestion, heartbeat freshness, and replay after outage.
- Verify database backups and compressed raw-storage retention.
- Verify login from a separate device.
- Verify Binance, L2, Vantage, and forward-validator health.
- Only then mark HYBRID remote deployment accepted.

No values in this file are credentials.
