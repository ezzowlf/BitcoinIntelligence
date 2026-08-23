$Runtime = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path "runtime\services"
foreach ($Name in @("collector", "dashboard")) {
    $PidFile = Join-Path $Runtime "$Name.pid"
    if (Test-Path $PidFile) {
        $ProcessId = [int](Get-Content $PidFile)
        Stop-Process -Id $ProcessId -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $PidFile -Force
    }
}
