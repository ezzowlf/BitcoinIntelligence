$ErrorActionPreference = "SilentlyContinue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runtime = Join-Path $Root "runtime\waverun"
foreach ($name in @("engine.pid", "dashboard.pid")) {
    $path = Join-Path $Runtime $name
    if (Test-Path -LiteralPath $path) {
        $pidValue = [int](Get-Content -LiteralPath $path -Raw)
        Stop-Process -Id $pidValue -Force
        Remove-Item -LiteralPath $path -Force
    }
}
Write-Host "WAVERUN STOPPED; execution remains DISABLED"
