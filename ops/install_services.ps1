# TAKEOFF Windows services via NSSM (reuses the NSSM binary already on this VPS).
# Idempotent. Touches ONLY TAKEOFF-* services. No WAVERUN / BitcoinElliot / POSTER / MeanPulse change.

$Nssm = "C:\Users\Administrator\Documents\POSTER\runtime\tools\nssm\nssm.exe"
$Root = "C:\TAKEOFF"
$Py   = "$Root\.venv\Scripts\python.exe"
$Logs = "$Root\logs"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

if (-not (Test-Path $Nssm)) { throw "NSSM not found at $Nssm" }
if (-not (Test-Path $Py))   { throw "TAKEOFF venv python not found at $Py" }

function Set-TakeoffService {
    param([string]$Name, [string]$App, [string]$Params, [string]$Dir)

    if (Get-Service -Name $Name -ErrorAction SilentlyContinue) {
        Write-Host "Removing existing service $Name"
        & $Nssm stop $Name confirm  | Out-Null
        Start-Sleep -Seconds 2
        & $Nssm remove $Name confirm | Out-Null
        Start-Sleep -Seconds 2
    }

    Write-Host "Installing $Name"
    & $Nssm install $Name $App $Params            | Out-Null
    & $Nssm set $Name AppDirectory $Dir           | Out-Null
    & $Nssm set $Name DisplayName "$Name (WAVERUN TAKEOFF)" | Out-Null
    & $Nssm set $Name Description "TAKEOFF analysis/signal system - EXECUTION DISABLED" | Out-Null
    & $Nssm set $Name Start SERVICE_AUTO_START     | Out-Null
    & $Nssm set $Name AppStdout "$Logs\$Name.out.log" | Out-Null
    & $Nssm set $Name AppStderr "$Logs\$Name.err.log" | Out-Null
    & $Nssm set $Name AppRotateFiles 1             | Out-Null
    & $Nssm set $Name AppRotateOnline 1            | Out-Null
    & $Nssm set $Name AppRotateBytes 10485760      | Out-Null
    & $Nssm set $Name AppExit Default Restart      | Out-Null
    & $Nssm set $Name AppRestartDelay 5000         | Out-Null
    & $Nssm set $Name AppThrottle 10000            | Out-Null
    & $Nssm set $Name AppStopMethodConsole 5000    | Out-Null
    & $Nssm set $Name AppEnvironmentExtra "EXECUTION=DISABLED" "BITCOIN_EXECUTION_ENABLED=false" "WAVERUN_ROOT=$Root" "PYTHONUNBUFFERED=1" | Out-Null
}

Set-TakeoffService -Name "TAKEOFF-Collector" -App $Py -Params "`"$Root\scripts\waverun_live.py`"" -Dir $Root
Set-TakeoffService -Name "TAKEOFF-API"       -App $Py -Params "`"$Root\scripts\waverun_web_api.py`" --host 127.0.0.1 --port 8877 --root `"$Root`"" -Dir $Root
Set-TakeoffService -Name "TAKEOFF-Web"       -App $Py -Params "-m http.server 8878 --bind 127.0.0.1 --directory `"$Root\frontend\dist`"" -Dir "$Root\frontend\dist"

Write-Host "`nStarting services..."
foreach ($s in "TAKEOFF-Collector","TAKEOFF-API","TAKEOFF-Web") { & $Nssm start $s | Out-Null; Start-Sleep -Seconds 3 }

Write-Host "`n--- Status ---"
foreach ($s in "TAKEOFF-Collector","TAKEOFF-API","TAKEOFF-Web") {
    $svc = Get-CimInstance Win32_Service -Filter "Name='$s'"
    "{0,-20} State={1,-9} StartMode={2,-10} PID={3}" -f $s, $svc.State, $svc.StartMode, $svc.ProcessId
}
