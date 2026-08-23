# WAVERUN hybrid Linux profile

This profile provides the authenticated dashboard behind automatic Caddy HTTPS. Configure environment-only `WAVERUN_HOSTNAME` and `WAVERUN_DASHBOARD_PASSWORD_SHA256`; no secret belongs in Git.

The Windows Vantage bridge/server ingestion service still requires a reachable Linux host and service token before this profile can be accepted remotely. Until then use the verified Windows all-in-one profile. Do not expose port 8501 directly.
