$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runtime = Join-Path $Root "runtime\production8"
foreach ($name in "watcher.pid","dashboard.pid") {
    $path = Join-Path $Runtime $name
    if (-not (Test-Path -LiteralPath $path)) { continue }
    $processId = [int](Get-Content -LiteralPath $path)
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
    if ($process -and $process.CommandLine -and $process.CommandLine.Contains($Root)) {
        Stop-Process -Id $processId
    }
    Remove-Item -LiteralPath $path -ErrorAction SilentlyContinue
}
