param([string]$InstallRoot="C:\BitcoinIntelligence",[switch]$RegisterTasks)
$ErrorActionPreference="Stop"
$source=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$app=Join-Path $InstallRoot "app"
foreach($name in @("app","data","logs","snapshots","forward","config","backups")){New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot $name)|Out-Null}
robocopy $source $app /MIR /XD .git .venv .runtime database data logs backups /XF .env "python-*-amd64.exe" | Out-Null
if($LASTEXITCODE -gt 7){throw "Application copy failed with robocopy exit $LASTEXITCODE"}
$python=(Get-Command python -ErrorAction Stop).Source
& $python -m venv (Join-Path $InstallRoot ".venv")
$venvPython=Join-Path $InstallRoot ".venv\Scripts\python.exe"
& $venvPython -m pip install --disable-pip-version-check -r (Join-Path $app "requirements-vps.lock")
if($RegisterTasks){
  $runner="`"$venvPython`" `"$app\scripts\shadow_service.py`""
  schtasks /Create /F /TN "BitcoinIntelligence-H4" /SC HOURLY /MO 4 /TR "$runner h4" /RU SYSTEM
  schtasks /Create /F /TN "BitcoinIntelligence-Daily" /SC DAILY /ST 00:15 /TR "$runner daily" /RU SYSTEM
  schtasks /Create /F /TN "BitcoinIntelligence-Backup" /SC DAILY /ST 01:00 /TR "$runner backup" /RU SYSTEM
  schtasks /Create /F /TN "BitcoinIntelligence-Startup" /SC ONSTART /DELAY 0001:00 /TR "$runner startup --send" /RU SYSTEM
  schtasks /Create /F /TN "BitcoinIntelligence-Telegram" /SC MINUTE /MO 1 /TR "$runner poll" /RU SYSTEM
  schtasks /Create /F /TN "BitcoinIntelligence-Price" /SC HOURLY /MO 1 /TR "$runner refresh-price" /RU SYSTEM
  schtasks /Create /F /TN "BitcoinIntelligence-Providers" /SC HOURLY /MO 6 /TR "$runner refresh-providers" /RU SYSTEM
}
Write-Output "Installed Bitcoin Intelligence SHADOW LIVE at $InstallRoot"
