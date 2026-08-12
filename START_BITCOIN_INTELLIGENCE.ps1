$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) { throw "Missing project venv: $Python" }
$Runtime = Join-Path $Root "runtime\production8"
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

function Find-BitcoinProcess([string]$Needle) {
    Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($Root) -and $_.CommandLine.Contains($Needle) }
}

if (-not (Find-BitcoinProcess "production8_shadow.py")) {
    $watcher = Start-Process -FilePath $Python -ArgumentList (Join-Path $Root "scripts\production8_shadow.py"),"--watch","--interval","60" -WorkingDirectory $Root -WindowStyle Hidden -PassThru
    Set-Content -LiteralPath (Join-Path $Runtime "watcher.pid") -Value $watcher.Id -Encoding ascii
}
if (-not (Find-BitcoinProcess "streamlit run dashboard\app.py")) {
    $dashboard = Start-Process -FilePath $Python -ArgumentList "-m","streamlit","run","dashboard\app.py","--server.headless=true","--server.port=8501" -WorkingDirectory $Root -WindowStyle Hidden -PassThru
    Set-Content -LiteralPath (Join-Path $Runtime "dashboard.pid") -Value $dashboard.Id -Encoding ascii
}
& $Python -m bitcoin_cycle_analyzer health
Start-Process "http://localhost:8501"
