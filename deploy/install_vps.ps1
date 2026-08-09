param(
  [string]$InstallRoot="C:\BitcoinIntelligence",
  [string]$SourceRoot=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
  [switch]$InventoryConfirmed,
  [switch]$RegisterTasks
)
$ErrorActionPreference="Stop"
if(-not $InventoryConfirmed){throw "Run deploy\preflight_vps.ps1 on the VPS first, review it, then pass -InventoryConfirmed."}
$source=(Resolve-Path -LiteralPath $SourceRoot).Path
$marker=Join-Path $InstallRoot ".bitcoin-intelligence-owned"
if(Test-Path -LiteralPath $InstallRoot){
  $items=@(Get-ChildItem -LiteralPath $InstallRoot -Force -ErrorAction Stop)
  if($items.Count -gt 0 -and -not (Test-Path -LiteralPath $marker)){throw "Target exists and is not marked as Bitcoin Intelligence owned: $InstallRoot"}
}
$taskNames=@("BitcoinIntelligence-H4","BitcoinIntelligence-Daily","BitcoinIntelligence-Backup","BitcoinIntelligence-Startup","BitcoinIntelligence-Telegram","BitcoinIntelligence-Price","BitcoinIntelligence-Providers","BitcoinIntelligence-Health","BitcoinIntelligence-Dashboard")
if($RegisterTasks){foreach($task in $taskNames){schtasks /Query /TN $task 2>$null | Out-Null;if($LASTEXITCODE -eq 0){throw "Scheduled task already exists; no overwrite performed: $task"}}}
foreach($name in @("app","data","database","forward","snapshots","alerts","logs","backups","config","runtime")){New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot $name)|Out-Null}
$app=Join-Path $InstallRoot "app"
robocopy $source $app /E /XD .git .venv .runtime logs backups forward snapshots alerts /XF .env "python-*-amd64.exe" forward_validation.db | Out-Null
if($LASTEXITCODE -gt 7){throw "Application copy failed with robocopy exit $LASTEXITCODE"}
$python=(Get-Command python -ErrorAction Stop).Source
if(-not (Test-Path -LiteralPath (Join-Path $InstallRoot ".venv\Scripts\python.exe"))){& $python -m venv (Join-Path $InstallRoot ".venv")}
$venvPython=Join-Path $InstallRoot ".venv\Scripts\python.exe"
& $venvPython -m pip install --disable-pip-version-check -r (Join-Path $app "requirements-vps.lock")
if($LASTEXITCODE -ne 0){throw "Dependency installation failed"}
Set-Content -LiteralPath $marker -Value (Get-Date).ToUniversalTime().ToString("o") -Encoding ascii
if($RegisterTasks){
  $runner="`"$venvPython`" `"$app\scripts\shadow_service.py`""
  schtasks /Create /TN "BitcoinIntelligence-H4" /SC HOURLY /MO 4 /TR "$runner h4" /RU SYSTEM
  schtasks /Create /TN "BitcoinIntelligence-Daily" /SC DAILY /ST 00:15 /TR "$runner daily" /RU SYSTEM
  schtasks /Create /TN "BitcoinIntelligence-Backup" /SC DAILY /ST 01:00 /TR "$runner backup" /RU SYSTEM
  schtasks /Create /TN "BitcoinIntelligence-Startup" /SC ONSTART /DELAY 0001:00 /TR "$runner startup" /RU SYSTEM
  schtasks /Create /TN "BitcoinIntelligence-Telegram" /SC MINUTE /MO 1 /TR "$runner poll" /RU SYSTEM
  schtasks /Create /TN "BitcoinIntelligence-Price" /SC HOURLY /MO 1 /TR "$runner refresh-price" /RU SYSTEM
  schtasks /Create /TN "BitcoinIntelligence-Providers" /SC HOURLY /MO 6 /TR "$runner refresh-providers" /RU SYSTEM
  schtasks /Create /TN "BitcoinIntelligence-Health" /SC MINUTE /MO 15 /TR "$runner health" /RU SYSTEM
  $dashboard="`"$venvPython`" -m streamlit run `"$app\dashboard\app.py`" --server.address 127.0.0.1 --server.port 8501 --server.headless true"
  schtasks /Create /TN "BitcoinIntelligence-Dashboard" /SC ONSTART /DELAY 0001:30 /TR "$dashboard" /RU SYSTEM
  if($LASTEXITCODE -ne 0){throw "Task registration failed"}
}
Write-Output "Installed Bitcoin Intelligence SHADOW LIVE at $InstallRoot; Telegram remains dry-run until VPS .env is explicitly configured."
