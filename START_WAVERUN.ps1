$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) { throw "Missing project venv: $Python. Install with: $Python -m pip install -e '.[dev,live,dashboard]'" }
$Runtime = Join-Path $Root "runtime\waverun"
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
Write-Host "WAVERUN ENGINE STARTING"
Write-Host "DATA FEEDS CONNECTING"
$engine = Start-Process -FilePath $Python -ArgumentList (Join-Path $Root "scripts\waverun_live.py") -WorkingDirectory $Root -WindowStyle Hidden -PassThru
Set-Content -LiteralPath (Join-Path $Runtime "engine.pid") -Value $engine.Id -Encoding ascii
Write-Host "PREDICTION ENGINE READY"
if (-not (Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue)) {
    $dashboard = Start-Process -FilePath $Python -ArgumentList "-m","streamlit","run","dashboard\app.py","--server.headless=true","--server.port=8501" -WorkingDirectory $Root -WindowStyle Hidden -PassThru
    Set-Content -LiteralPath (Join-Path $Runtime "dashboard.pid") -Value $dashboard.Id -Encoding ascii
}
Write-Host "DASHBOARD READY"
Write-Host "Execution remains DISABLED"
