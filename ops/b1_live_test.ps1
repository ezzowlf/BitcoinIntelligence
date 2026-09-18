# B-1 live disconnect/reconnect test for the TAKEOFF collector.
# Controlled: one outbound firewall rule blocking Binance stream endpoints only.
# Fully reversed at the end (and on Ctrl-C the rule name is fixed so it can be removed).
$ErrorActionPreference = "Stop"
$Root   = "C:\TAKEOFF"
$Py     = "$Root\.venv\Scripts\python.exe"
$Latest = "$Root\runtime\waverun\latest.json"
$Events = "$Root\runtime\waverun\market_events.jsonl"
$RuleName = "TAKEOFF-B1-TEST-BLOCK"
$Cycles = 3
$BlockSeconds = 20
$RecoverSeconds = 30

function Get-CollectorPid {
    (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'waverun_live' } |
        Sort-Object CreationDate | Select-Object -Last 1).ProcessId
}
function LineCount($p) { if (Test-Path $p) { (& $Py -c "import sys;print(sum(1 for _ in open(sys.argv[1],encoding='utf-8',errors='replace')))" $p) } else { 0 } }
function Feeds {
    try { $d = Get-Content $Latest -Raw | ConvertFrom-Json; return $d.feeds } catch { return $null }
}
function ApiHealth {
    try { (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8877/api/health" -TimeoutSec 5).StatusCode } catch { "ERR" }
}
function Resolve-BinanceIPs {
    $names = "stream.binance.com","fstream.binance.com"
    $ips = foreach ($n in $names) {
        try { (Resolve-DnsName -Name $n -Type A -ErrorAction Stop | Where-Object {$_.IPAddress}).IPAddress } catch {}
    }
    $ips | Sort-Object -Unique
}

if (Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue) {
    Remove-NetFirewallRule -DisplayName $RuleName
}

$startPid = Get-CollectorPid
"START collector PID = $startPid   API health = $(ApiHealth)"
$f = Feeds
"START feeds: spot state=$($f.spot.state) reconnects=$($f.spot.reconnects) | futures state=$($f.futures.state) reconnects=$($f.futures.reconnects)"
""

for ($c = 1; $c -le $Cycles; $c++) {
    "===== CYCLE $c / $Cycles ====="
    $ips = Resolve-BinanceIPs
    "  blocking IPs: $($ips -join ', ')  + remote port 9443"
    $preEvents = LineCount $Events
    $prePid = Get-CollectorPid
    $pf = Feeds
    $preSpotRc = [int]$pf.spot.reconnects ; $preFutRc = [int]$pf.futures.reconnects

    New-NetFirewallRule -DisplayName $RuleName -Direction Outbound -Action Block `
        -RemoteAddress $ips -Protocol TCP -ErrorAction Stop | Out-Null
    New-NetFirewallRule -DisplayName $RuleName -Direction Outbound -Action Block `
        -RemotePort 9443 -Protocol TCP -ErrorAction Stop | Out-Null
    $tBlock = Get-Date
    "  [$(Get-Date -Format HH:mm:ss)] BLOCK applied"

    Start-Sleep -Seconds $BlockSeconds
    $midEvents = LineCount $Events
    $midPid = Get-CollectorPid
    $health = ApiHealth
    "  [$(Get-Date -Format HH:mm:ss)] during block: events $preEvents -> $midEvents (delta $($midEvents-$preEvents)) | collector PID $midPid | API $health"

    Remove-NetFirewallRule -DisplayName $RuleName
    "  [$(Get-Date -Format HH:mm:ss)] BLOCK removed; waiting ${RecoverSeconds}s to recover"
    Start-Sleep -Seconds $RecoverSeconds

    $postEvents = LineCount $Events
    $postPid = Get-CollectorPid
    $qf = Feeds
    "  RESULT cycle ${c}:"
    "    collector PID: start=$prePid now=$postPid  (survived: $([bool]($postPid -eq $prePid -and $postPid)))"
    "    events: during-block delta=$($midEvents-$preEvents)  post-recover delta=$($postEvents-$midEvents)"
    "    spot:    state=$($qf.spot.state)    reconnects $preSpotRc -> $($qf.spot.reconnects)   last_event_at=$($qf.spot.last_event_at)"
    "    futures: state=$($qf.futures.state) reconnects $preFutRc -> $($qf.futures.reconnects)  last_event_at=$($qf.futures.last_event_at)"
    "    API health = $(ApiHealth)"
    ""
}

if (Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue) { Remove-NetFirewallRule -DisplayName $RuleName }
$endPid = Get-CollectorPid
"END collector PID = $endPid  (unchanged from start: $([bool]($endPid -eq $startPid)))"
"END API health = $(ApiHealth)"
$ef = Feeds
"END feeds: spot state=$($ef.spot.state) reconnects=$($ef.spot.reconnects) | futures state=$($ef.futures.state) reconnects=$($ef.futures.reconnects)"
"Firewall rule present at exit: $([bool](Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue))"
