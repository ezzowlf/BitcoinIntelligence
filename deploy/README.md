# Windows VPS shadow deployment

Use 64-bit Python 3.13 in an elevated PowerShell terminal. The installer creates `C:\BitcoinIntelligence`, an isolated `.venv`, copies no `.env`, installs the pinned lock file and optionally registers four Task Scheduler jobs.

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\install_vps.ps1 -InstallRoot C:\BitcoinIntelligence -RegisterTasks
```

Create `C:\BitcoinIntelligence\app\.env` or set machine environment variables separately. Required for live Telegram are `TELEGRAM_ENABLED=true`, `TELEGRAM_DRY_RUN=false`, `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. If either credential is absent, the runtime automatically remains in dry-run. `EXECUTION` is always `DISABLED` and is not a configurable trading switch.

Jobs: H4 every four hours, Daily at 00:15 UTC/server time, Backup at 01:00, Startup after reboot. Provider refresh can be scheduled independently using `scripts\update_data.py` and `scripts\update_external_data.py`; provider errors remain isolated.
