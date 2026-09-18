# TAKEOFF 24h soak sampler - READ ONLY. Appends one JSON line per run.
# Never modifies TAKEOFF, never restarts anything. Safe to run on a schedule.
$ErrorActionPreference = "SilentlyContinue"
$Root   = "C:\TAKEOFF"
$Out    = "$Root\ops\soak\samples.jsonl"
$RecOut = "$Root\ops\soak\reconnect_events.jsonl"
$Prev   = "$Root\ops\soak\_prev.json"
$Py     = "$Root\.venv\Scripts\python.exe"
New-Item -ItemType Directory -Force -Path "$Root\ops\soak" | Out-Null

function LC($p) { if (Test-Path $p) { try { (& $Py -c "import sys;print(sum(1 for _ in open(sys.argv[1],'rb')))" $p) -as [int] } catch { -1 } } else { 0 } }
function Worker($rx) { (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match $rx } | Sort-Object CreationDate | Select-Object -Last 1) }
function Svc($n) { Get-CimInstance Win32_Service -Filter "Name='$n'" }
function HttpCode($u) { try { (Invoke-WebRequest -UseBasicParsing $u -TimeoutSec 6).StatusCode } catch { if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { "ERR" } } }

$now = (Get-Date).ToUniversalTime().ToString("o")
$os  = Get-CimInstance Win32_OperatingSystem
$cpu = (Get-CimInstance Win32_Processor | Measure-Object LoadPercentage -Average).Average

$colW = Worker 'waverun_live'
$apiW = Worker 'waverun_web_api'
$webW = Worker 'http\.server 8878'
$colProc = if ($colW) { Get-Process -Id $colW.ProcessId } else { $null }
$apiProc = if ($apiW) { Get-Process -Id $apiW.ProcessId } else { $null }

$colCount = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'waverun_live' -and $_.CommandLine -match '\.venv' }).Count
$conns = if ($colW) { @(Get-NetTCPConnection -State Established -OwningProcess $colW.ProcessId).Count } else { 0 }
$binSpot = if ($colW) { [bool](Get-NetTCPConnection -State Established -OwningProcess $colW.ProcessId -RemotePort 9443) } else { $false }
$binFut  = if ($colW) { @(Get-NetTCPConnection -State Established -OwningProcess $colW.ProcessId -RemotePort 443).Count -gt 0 } else { $false }

function ReadJson($p) {
  for ($i=0; $i -lt 4; $i++) {
    try { return (Get-Content $p -Raw -ErrorAction Stop | ConvertFrom-Json) } catch { Start-Sleep -Milliseconds 250 }
  }
  return $null
}
$latest = ReadJson "$Root\runtime\waverun\latest.json"
$status = ReadJson "$Root\runtime\waverun_v5_3_fast_v2_forward\status.json"

$logBytes = (Get-ChildItem "$Root\logs\*.log" | Measure-Object Length -Sum).Sum
$dbBytes  = (Get-Item "$Root\database\waverun_predictions.db").Length
$diskFree = (Get-PSDrive C).Free

# isolation invariants
$beMtime = (Get-Item "C:\BitcoinElliot").LastWriteTime.ToString("o")
$be8502  = [bool](Get-NetTCPConnection -LocalPort 8502 -State Listen)
$ts443   = try { ((& "C:\Program Files\Tailscale\tailscale.exe" serve status --json | ConvertFrom-Json).Web.'vmi3427793-2.tail795fcf.ts.net:443'.Handlers.'/'.Proxy) } catch { "?" }

$sample = [ordered]@{
  t = $now
  svc = [ordered]@{
    collector = (Svc 'TAKEOFF-Collector').State
    api       = (Svc 'TAKEOFF-API').State
    web       = (Svc 'TAKEOFF-Web').State
    collector_start = (Svc 'TAKEOFF-Collector').StartMode
    api_start       = (Svc 'TAKEOFF-API').StartMode
    web_start       = (Svc 'TAKEOFF-Web').StartMode
  }
  proc = [ordered]@{
    collector_pid = $colW.ProcessId
    api_pid       = $apiW.ProcessId
    web_pid       = $webW.ProcessId
    collector_rss_mb = if ($colProc) { [math]::Round($colProc.WorkingSet64/1MB,1) } else { $null }
    api_rss_mb       = if ($apiProc) { [math]::Round($apiProc.WorkingSet64/1MB,1) } else { $null }
    collector_threads = if ($colProc) { $colProc.Threads.Count } else { $null }
    api_threads       = if ($apiProc) { $apiProc.Threads.Count } else { $null }
    collector_handles = if ($colProc) { $colProc.HandleCount } else { $null }
    collector_cpu_s   = if ($colProc) { [math]::Round($colProc.CPU,1) } else { $null }
    collector_instances = $colCount
  }
  host = [ordered]@{
    ram_free_mb = [math]::Round($os.FreePhysicalMemory/1KB,0)
    ram_total_mb = [math]::Round($os.TotalVisibleMemorySize/1KB,0)
    cpu_pct = $cpu
    disk_free_gb = [math]::Round($diskFree/1GB,2)
  }
  net = [ordered]@{ collector_conns = $conns; binance_spot = $binSpot; binance_futures = $binFut }
  feeds = if ($latest) { [ordered]@{
    spot_state = $latest.feeds.spot.state
    spot_reconnects = $latest.feeds.spot.reconnects
    spot_last_event = $latest.feeds.spot.last_event_at
    fut_state = $latest.feeds.futures.state
    fut_reconnects = $latest.feeds.futures.reconnects
    fut_last_event = $latest.feeds.futures.last_event_at
    price = $(if ($latest.price -is [double] -or $latest.price -is [int] -or $latest.price -is [decimal]) { $latest.price } else { $latest.price.mid })
    setup_state = $latest.state
    execution = $latest.execution
  } } else { $null }
  engine = if ($status) { [ordered]@{
    recorder_health = $status.recorder_health
    accepted_signals = $status.accepted_signals
    veto_blocked_signals = $status.veto_blocked_signals
    resolved_signals = $status.resolved_signals
    successes_100_5m = $status.successes_100_5m
    progress_to_100 = $status.progress_to_100
    last_candidate_ts = $status.last_candidate_timestamp
    vantage = $status.source_health.vantage
    execution = $status.execution
  } } else { $null }
  files = [ordered]@{
    market_events = LC "$Root\runtime\waverun\market_events.jsonl"
    pre_gate_candidates = LC "$Root\runtime\waverun\pre_gate_candidates.jsonl"
    decision_records = LC "$Root\runtime\waverun\decision_records.jsonl"
    vantage_ticks = LC "$Root\runtime\waverun\vantage_ticks.jsonl"
    log_bytes = $logBytes
    db_bytes = $dbBytes
  }
  api = [ordered]@{
    health = HttpCode "http://127.0.0.1:8877/api/health"
    ts_health = HttpCode "https://vmi3427793-2.tail795fcf.ts.net:8443/api/health"
    web = HttpCode "http://127.0.0.1:8878/"
  }
  isolation = [ordered]@{
    bitcoinelliot_mtime = $beMtime
    bitcoinelliot_8502_listen = $be8502
    tailscale_443_route = $ts443
  }
}

# reconnect / restart event detection vs previous sample
$prev = try { Get-Content $Prev -Raw | ConvertFrom-Json } catch { $null }
if ($prev -and $latest) {
  foreach ($f in "spot","fut") {
    $pr = [int]$prev.feeds."${f}_reconnects"; $cur = [int]$sample.feeds."${f}_reconnects"
    if ($cur -gt $pr) {
      ([ordered]@{ t=$now; feed=$f; kind="RECONNECT"; from=$pr; to=$cur;
        prev_sample_t=$prev.t; collector_pid=$sample.proc.collector_pid;
        events_now=$sample.files.market_events } | ConvertTo-Json -Compress) | Add-Content $RecOut
    }
  }
  if ($prev.proc.collector_pid -and $sample.proc.collector_pid -and $prev.proc.collector_pid -ne $sample.proc.collector_pid) {
    ([ordered]@{ t=$now; kind="COLLECTOR_PID_CHANGE"; from=$prev.proc.collector_pid; to=$sample.proc.collector_pid; prev_sample_t=$prev.t } | ConvertTo-Json -Compress) | Add-Content $RecOut
  }
  if ($prev.api.health -eq 200 -and $sample.api.health -ne 200) {
    ([ordered]@{ t=$now; kind="API_DOWN"; code=$sample.api.health; prev_sample_t=$prev.t } | ConvertTo-Json -Compress) | Add-Content $RecOut
  }
}

($sample | ConvertTo-Json -Depth 6 -Compress) | Add-Content $Out
($sample | ConvertTo-Json -Depth 6 -Compress) | Set-Content $Prev
