import json, datetime as dt

rows = [json.loads(l) for l in open('ops/soak/samples.jsonl') if l.strip()]
f, l = rows[0], rows[-1]
t0 = dt.datetime.fromisoformat(f['t'].replace('Z', '+00:00'))
tN = dt.datetime.fromisoformat(l['t'].replace('Z', '+00:00'))

def at(h):
    return min(rows, key=lambda r: abs((dt.datetime.fromisoformat(r['t'].replace('Z','+00:00')) - t0).total_seconds() - h*3600))

S = {h: at(h) for h in (0, 6, 12, 18, 24)}
dur = (tN - t0).total_seconds() / 3600

def uniq(path):
    def get(r):
        x = r
        for k in path.split('.'):
            x = (x or {}).get(k) if isinstance(x, dict) else None
        return x
    return sorted(set(str(get(r)) for r in rows))

print("SAMPLES", len(rows))
print("SOAK START :", f['t'])
print("SOAK END   :", l['t'])
print("DURATION   : %.2f h" % dur)
print()
print("== SERVICES ==")
print(" collector state set:", uniq('svc.collector'))
print(" api  state set     :", uniq('svc.api'))
print(" web  state set     :", uniq('svc.web'))
print(" startmodes         :", uniq('svc.collector_start'), uniq('svc.api_start'), uniq('svc.web_start'))
print(" collector pid set  :", uniq('proc.collector_pid'))
print(" api pid set        :", uniq('proc.api_pid'))
print(" web pid set        :", uniq('proc.web_pid'))
print(" collector_instances:", uniq('proc.collector_instances'))
print()
print("== HEALTH ==")
print(" api health set:", uniq('api.health'))
print(" ts  health set:", uniq('api.ts_health'))
print(" web health set:", uniq('api.web'))
print(" samples with api!=200:", sum(1 for r in rows if str(r['api']['health']) != '200'))
print(" samples with ts !=200:", sum(1 for r in rows if str(r['api']['ts_health']) != '200'))
print(" samples with web!=200:", sum(1 for r in rows if str(r['api']['web']) != '200'))
print()
print("== FEEDS / RECONNECTS ==")
print(" spot rc 0/6/12/18/24:", [S[h]['feeds']['spot_reconnects'] for h in (0,6,12,18,24)])
print(" fut  rc 0/6/12/18/24:", [S[h]['feeds']['fut_reconnects'] for h in (0,6,12,18,24)])
print(" spot state set:", uniq('feeds.spot_state'))
print(" fut  state set:", uniq('feeds.fut_state'))
prev = None
for r in rows:
    if r['feeds']['spot_state'] != prev:
        print("   spot_state ->", r['feeds']['spot_state'], "at", r['t']); prev = r['feeds']['spot_state']
prev = None
for r in rows:
    if r['feeds']['fut_state'] != prev:
        print("   fut_state  ->", r['feeds']['fut_state'], "at", r['t'], "rc", r['feeds']['fut_reconnects']); prev = r['feeds']['fut_state']
# count sample windows where spot rc increased, and total delta
inc_windows = sum(1 for i in range(1, len(rows)) if rows[i]['feeds']['spot_reconnects'] > rows[i-1]['feeds']['spot_reconnects'])
print(" spot rc TOTAL:", l['feeds']['spot_reconnects'], " | sample-windows with an increase:", inc_windows)
print(" fut  rc TOTAL:", l['feeds']['fut_reconnects'])
fdeg = [r for r in rows if r['feeds']['fut_state'] == 'DEGRADED']
if fdeg:
    a = dt.datetime.fromisoformat(fdeg[0]['t'].replace('Z', '+00:00'))
    print(" fut DEGRADED from", fdeg[0]['t'], "to end; span %.2f h" % ((tN - a).total_seconds()/3600))
print()
print("== RESOURCES ==")
for h in (0, 6, 12, 18, 24):
    r = S[h]
    print("  %2dh RAMfree=%sMB colRSS=%sMB apiRSS=%sMB cpu=%s%% disk=%sGB thr(col)=%s" % (
        h, r['host']['ram_free_mb'], r['proc']['collector_rss_mb'], r['proc']['api_rss_mb'],
        r['host']['cpu_pct'], r['host']['disk_free_gb'], r['proc']['collector_threads']))
print("  RAMfree min/max:", min(r['host']['ram_free_mb'] for r in rows), max(r['host']['ram_free_mb'] for r in rows))
print("  colRSS  min/max:", min(r['proc']['collector_rss_mb'] for r in rows), max(r['proc']['collector_rss_mb'] for r in rows))
print("  cpu     min/max:", min(r['host']['cpu_pct'] for r in rows), max(r['host']['cpu_pct'] for r in rows))
print("  col threads first/last/max:", f['proc']['collector_threads'], l['proc']['collector_threads'], max(r['proc']['collector_threads'] for r in rows))
print("  api threads first/last:", f['proc']['api_threads'], l['proc']['api_threads'])
print("  col conns first/last:", f['net']['collector_conns'], l['net']['collector_conns'])
print("  binance spot/fut flag last:", l['net']['binance_spot'], l['net']['binance_futures'])
print()
print("== FILES / GROWTH ==")
for h in (0, 6, 12, 18, 24):
    r = S[h]
    print("  %2dh market_events=%d pre_gate=%d db=%.0fMB log=%dB" % (
        h, r['files']['market_events'], r['files']['pre_gate_candidates'],
        r['files']['db_bytes']/1e6, r['files']['log_bytes']))
me = l['files']['market_events'] - f['files']['market_events']
pg = l['files']['pre_gate_candidates'] - f['files']['pre_gate_candidates']
dbd = l['files']['db_bytes'] - f['files']['db_bytes']
print("  market_events delta:", me)
print("  pre_gate delta     :", pg)
print("  db bytes  first/last: %d / %d  (delta %d, %.0f MB)" % (f['files']['db_bytes'], l['files']['db_bytes'], dbd, dbd/1e6))
print("  log bytes first/last:", f['files']['log_bytes'], l['files']['log_bytes'])
print("  disk GB   first/last:", f['host']['disk_free_gb'], l['host']['disk_free_gb'])
per_day_db = dbd / dur * 24 / 1e6
print("  db growth/day: %.0f MB  -> 7d %.1f GB  30d %.1f GB" % (per_day_db, per_day_db*7/1000, per_day_db*30/1000))
print()
print("== ENGINE ==")
print(" last:", json.dumps(l.get('engine') or {}, default=str))
print(" accepted set:", uniq('engine.accepted_signals'))
print(" veto set    :", uniq('engine.veto_blocked_signals'))
print(" resolved set:", uniq('engine.resolved_signals'))
print(" recorder_health set:", uniq('engine.recorder_health'))
print(" vantage set :", uniq('engine.vantage'))
print(" setup_state set:", uniq('feeds.setup_state'))
print(" exec feeds set :", uniq('feeds.execution'))
print(" exec engine set:", uniq('engine.execution'))
print()
print("== ISOLATION ==")
print(" BE mtime set:", uniq('isolation.bitcoinelliot_mtime'))
print(" BE 8502 set :", uniq('isolation.bitcoinelliot_8502_listen'))
print(" ts443 set   :", uniq('isolation.tailscale_443_route'))
