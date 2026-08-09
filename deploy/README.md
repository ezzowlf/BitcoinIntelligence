# Windows VPS shadow deployment without GitHub

The authorized local source is `C:\Users\djaez\Documents\ChatGPT\Bitcoin`. No Git remote is required or configured. The package keeps Bitcoin Intelligence separate from MeanPulse.

## 1. Build the immutable package locally

The builder requires a clean committed worktree, uses `git archive HEAD`, adds only the public canonical BTC/on-chain/derivatives databases needed for the first smoke, writes `DEPLOYED_VERSION.json`, and excludes `.env`, `.git`, virtual environments, forward state, logs and caches.

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\build_package.ps1 -OutputZip C:\path\bitcoin-intelligence-master-3.zip
```

Record the printed SHA-256 before transfer.

## 2. Transfer by the actually available administration path

Use the VPS's confirmed RDP drive mapping, SFTP/SCP, or other established transfer. Do not invent a host or reuse MeanPulse directories. Copy only the ZIP to a temporary user-controlled location and verify its SHA-256 on the VPS.

## 3. Inventory the VPS without writes

Extract the ZIP to a temporary staging directory, then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\preflight_vps.ps1
```

Review Windows, Python, disk, RAM, processes, scheduled tasks and especially the reported state of `C:\BitcoinIntelligence`. If the target exists without `.bitcoin-intelligence-owned`, stop. Never overwrite or merge it.

## 4. Install only after inventory approval

Use 64-bit CPython. The project-root architecture is preserved under `C:\BitcoinIntelligence\app`; runtime state is stored beside it.

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\install_vps.ps1 `
  -SourceRoot C:\path\to\staging `
  -InstallRoot C:\BitcoinIntelligence `
  -InventoryConfirmed
```

Create `C:\BitcoinIntelligence\app\.env` from `.env.example`. Keep `TELEGRAM_DRY_RUN=true`, `TELEGRAM_CANDIDATE_ALERTS=false`, `EXECUTION=DISABLED`, and `BITCOIN_EXECUTION_ENABLED=false`. A true execution flag hard-stops the runtime; there is no order adapter.

Run price/provider refresh, MASTER, health and Telegram command dry-runs before task registration. Do not send a real Telegram message until credentials and the configured chat ID are independently confirmed.

Register tasks only in a second explicit invocation:

```powershell
powershell -ExecutionPolicy Bypass -File C:\BitcoinIntelligence\app\deploy\install_vps.ps1 `
  -SourceRoot C:\BitcoinIntelligence\app `
  -InstallRoot C:\BitcoinIntelligence `
  -InventoryConfirmed `
  -RegisterTasks
```

The installer refuses to overwrite existing Bitcoin Intelligence task names. Dashboard binds to `127.0.0.1:8501`; no public port is opened.

## 5. Required VPS verification

Use `C:\BitcoinIntelligence\.venv\Scripts\python.exe` for all commands:

```powershell
& C:\BitcoinIntelligence\.venv\Scripts\python.exe C:\BitcoinIntelligence\app\scripts\shadow_service.py startup
& C:\BitcoinIntelligence\.venv\Scripts\python.exe C:\BitcoinIntelligence\app\scripts\shadow_service.py health
& C:\BitcoinIntelligence\.venv\Scripts\python.exe C:\BitcoinIntelligence\app\scripts\shadow_service.py command --command /master
& C:\BitcoinIntelligence\.venv\Scripts\python.exe C:\BitcoinIntelligence\app\scripts\shadow_service.py command --command /history
```

Verify all task definitions, logs, hashes, dashboard HTTP 200 on localhost, backup output and restart behavior. The first current close must be at or after the frozen `2026-08-10T00:00:00Z` cutoff before `daily` may create a forward snapshot.

Only after every dry-run check passes may `TELEGRAM_DRY_RUN=false` be set and exactly one neutral connection/status message be sent. No BUY/SELL startup event is allowed.
