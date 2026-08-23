$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Runtime = Join-Path $Root "runtime\services"
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
$env:WAVERUN_LOCAL_TRUSTED = "true"

if (-not (Test-Path $Python)) { throw "WAVERUN Python environment not found: $Python" }

function Start-WaverunProcess {
    param([string]$Name, [string]$Arguments)
    $PidFile = Join-Path $Runtime "$Name.pid"
    if (Test-Path $PidFile) {
        $ExistingPid = [int](Get-Content $PidFile)
        if (Get-Process -Id $ExistingPid -ErrorAction SilentlyContinue) { return }
    }
    $Process = Start-Process -FilePath $Python -ArgumentList $Arguments -WorkingDirectory $Root -WindowStyle Hidden -PassThru
    Set-Content -LiteralPath $PidFile -Value $Process.Id -Encoding ascii
}

Start-WaverunProcess "collector" 'scripts\waverun_live.py --output runtime\waverun\latest.json --mt5-enabled --mt5-terminal-path "C:\Program Files\MetaTrader 5\terminal64.exe"'
Start-WaverunProcess "dashboard" '-m streamlit run dashboard\app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false'
