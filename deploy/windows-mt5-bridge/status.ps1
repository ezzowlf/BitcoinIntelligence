$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root "runtime\services"
foreach ($Name in @("collector", "dashboard")) {
    $PidFile = Join-Path $Runtime "$Name.pid"
    $Process = if (Test-Path $PidFile) { Get-Process -Id ([int](Get-Content $PidFile)) -ErrorAction SilentlyContinue } else { $null }
    [pscustomobject]@{ Service = $Name; Status = if ($Process) { "RUNNING" } else { "STOPPED" }; PID = $Process.Id }
}
 $Validation = Get-Content (Join-Path $Root "runtime\waverun_v5_3_fast_v2_forward\status.json") -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json
 $Tick = Get-Content (Join-Path $Root "runtime\waverun\vantage_ticks.jsonl") -Tail 1 -ErrorAction SilentlyContinue | ConvertFrom-Json
 Write-Output "dashboard PID: $((Get-Content (Join-Path $Runtime 'dashboard.pid') -ErrorAction SilentlyContinue))"
 Write-Output "collector PID: $((Get-Content (Join-Path $Runtime 'collector.pid') -ErrorAction SilentlyContinue))"
 Write-Output "MT5/Vantage: $($Validation.source_health.vantage)"
 Write-Output "Vantage tick freshness: $($Tick.timestamp)"
 Write-Output "Binance Spot: $($Validation.source_health.feeds.spot.state)"
 Write-Output "Binance Futures: $($Validation.source_health.feeds.futures.state)"
 Write-Output "L2: $($Validation.source_health.feeds.spot.state)"
 Write-Output "Forward-validation progress: $($Validation.progress_to_100)"
 Write-Output "Dashboard URL: http://127.0.0.1:8501"
try {
    $Health = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8501/_stcore/health" -TimeoutSec 3
    [pscustomobject]@{ Service = "dashboard-health"; Status = $Health.Content; PID = $null }
} catch {
    [pscustomobject]@{ Service = "dashboard-health"; Status = "OFFLINE"; PID = $null }
}
