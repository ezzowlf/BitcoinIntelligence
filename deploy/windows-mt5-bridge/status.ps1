$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runtime = Join-Path $Root "runtime\services"
foreach ($Name in @("collector", "dashboard")) {
    $PidFile = Join-Path $Runtime "$Name.pid"
    $Process = if (Test-Path $PidFile) { Get-Process -Id ([int](Get-Content $PidFile)) -ErrorAction SilentlyContinue } else { $null }
    [pscustomobject]@{ Service = $Name; Status = if ($Process) { "RUNNING" } else { "STOPPED" }; PID = $Process.Id }
}
try {
    $Health = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8501/_stcore/health" -TimeoutSec 3
    [pscustomobject]@{ Service = "dashboard-health"; Status = $Health.Content; PID = $null }
} catch {
    [pscustomobject]@{ Service = "dashboard-health"; Status = "OFFLINE"; PID = $null }
}
