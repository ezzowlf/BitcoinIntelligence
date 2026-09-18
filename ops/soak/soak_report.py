"""Evaluate the 24h production soak against the release gates.

Reads ops/soak/samples.jsonl (written every ~10 min by the independent
scheduled task) and reports measured values only - no estimates. Cumulative
counters are reported as deltas over the soak window, so a fault that occurred
between two samples is still visible.

    python ops/soak/soak_report.py [--hours 24]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / 'ops' / 'soak' / 'samples.jsonl'
RECONNECTS = ROOT / 'ops' / 'soak' / 'reconnect_events.jsonl'
LANES_ORDER = ('book', 'futures', 'spot', 'l2')


def _ts(row):
    return datetime.fromisoformat(row['timestamp'])


def _get(row, *path, default=None):
    node = row
    for key in path:
        if not isinstance(node, dict):
            return default
        node = node.get(key)
    return default if node is None else node


def _series(rows, *path):
    out = []
    for row in rows:
        value = _get(row, *path)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out.append(value)
    return out


def _delta(rows, *path):
    """First->last change of a cumulative counter, tolerating a restart (the
    counter dropping) by summing the segments."""
    values = _series(rows, *path)
    if len(values) < 2:
        return 0
    total = 0
    for a, b in zip(values, values[1:]):
        total += (b - a) if b >= a else b
    return total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--hours', type=float, default=24.0)
    args = parser.parse_args()

    rows = [json.loads(line) for line in SAMPLES.read_text(encoding='utf-8').splitlines() if line.strip()]
    if len(rows) < 2:
        print(f'need at least 2 samples, have {len(rows)}')
        return 1
    first, last = rows[0], rows[-1]
    hours = (_ts(last) - _ts(first)).total_seconds() / 3600

    print('=' * 72)
    print('TAKEOFF 24H PRODUCTION SOAK')
    print('=' * 72)
    print(f'window   : {first["timestamp"]}  ->  {last["timestamp"]}')
    print(f'duration : {hours:.2f} h over {len(rows)} samples')
    gates = {}

    # ---- availability -----------------------------------------------------
    states = [r.get('operating_state') for r in rows]
    full = sum(1 for s in states if s == 'FULL_LIVE')
    print(f'\n-- AVAILABILITY --')
    print(f'FULL_LIVE      : {full}/{len(states)} samples ({100 * full / len(states):.1f}%)')
    other = {}
    for s in states:
        if s != 'FULL_LIVE':
            other[s] = other.get(s, 0) + 1
    print(f'other states   : {other or "none"}')

    # ---- feeds / vantage --------------------------------------------------
    print(f'\n-- FEEDS / VANTAGE --')
    starts = _series(rows, 'vantage', 'starts')
    fails = _series(rows, 'vantage', 'failures')
    ages = _series(rows, 'vantage', 'age_seconds')
    if starts:
        print(f'MT5 starts     : {starts[0]} -> {starts[-1]}  (restart loop guard: delta {starts[-1] - starts[0]})')
    if fails:
        print(f'MT5 failures   : max {max(fails)}')
    if ages:
        a = sorted(ages)
        print(f'quote age      : min {min(ages):.2f}s  p50 {a[len(a) // 2]:.2f}s  max {max(ages):.2f}s')
        print(f'  age<=3s      : {100 * sum(1 for x in ages if x <= 3) / len(ages):.1f}% of samples')
    fresh = _series(rows, 'feed_freshness_seconds', 'feed_spot')
    if fresh:
        print(f'spot freshness : max {max(fresh):.2f}s')

    # ---- performance ------------------------------------------------------
    print(f'\n-- PERFORMANCE --')
    # The replaceable bookTicker lane is deliberately coalesced (drop-oldest)
    # under load, so produced-consumed grows by design there and is NOT
    # consumer lag. The gate that matters is: no dropped causally-required
    # events, and the queue and event age RECOVER after a burst.
    lanes = sorted((_get(last, 'pipeline', 'lanes') or {}).keys())
    drops_total = _delta(rows, 'pipeline', 'dropped', 'spot') + _delta(rows, 'pipeline', 'dropped', 'futures')
    coalesced_total = sum((_get(last, 'pipeline', 'coalesced') or {}).values())
    queue_ok = True
    for lane in lanes:
        produced = _delta(rows, 'pipeline', 'lanes', lane, 'produced')
        consumed = _delta(rows, 'pipeline', 'lanes', lane, 'consumed')
        qsize = _series(rows, 'pipeline', 'lanes', lane, 'queue_size')
        age = _series(rows, 'pipeline', 'lanes', lane, 'last_event_age_seconds')
        failed = _delta(rows, 'pipeline', 'lanes', lane, 'failed')
        drops_total += failed
        qpeak, qlast = (max(qsize), qsize[-1]) if qsize else (0, 0)
        agepeak, agelast = (max(age), age[-1]) if age else (0, 0)
        qcap = _get(last, 'pipeline', 'lanes', lane, 'queue_capacity', default=1) or 1
        # Recovery, not absence of bursts, is the requirement.
        recovered = qlast <= max(10, qpeak * 0.1) and agelast <= 5
        if not recovered:
            queue_ok = False
        print(f'{lane:<8} prod {produced / (hours * 3600):7.1f}/s  cons {consumed / (hours * 3600):7.1f}/s  '
              f'qpeak {qpeak:>5}/{qcap:<6} qend {qlast:<5} agepeak {agepeak:6.2f}s agend {agelast:5.2f}s  '
              f'failed {failed}  {"recovered" if recovered else "NOT RECOVERED"}')
    print(f'dropped causally-required events : {drops_total}')
    print(f'coalesced replaceable book events: {coalesced_total} (by design, not loss)')
    gates['no_drops'] = drops_total == 0
    gates['queue_recovery'] = queue_ok

    # ---- burst / capacity gate (1Hz monitor, not the 10-min sampler) ------
    bursts = ROOT / 'ops' / 'soak' / 'burst_summaries.jsonl'
    if bursts.exists():
        runs = [json.loads(line) for line in bursts.read_text(encoding='utf-8').splitlines() if line.strip()]
        runs = [r for r in runs if r.get('start', '') >= first['timestamp']]
        if runs:
            print(f'\n-- BURST / CAPACITY (1Hz over {len(runs)} monitor runs) --')
            print(f'{"lane":<8}{"prod peak/s":>12}{"cons peak/s":>12}{"q max":>8}{"q util%":>9}'
                  f'{"age max":>9}{"cons@backlog":>14}{"cons@idle":>11}')
            collapse_ok = True
            for lane in LANES_ORDER:
                pp = max((r['peak_producer_per_s'].get(lane) or 0) for r in runs)
                pc = max((r['peak_consumer_per_s'].get(lane) or 0) for r in runs)
                qm = max((r['peak_queue'].get(lane) or 0) for r in runs)
                qu = max((r['peak_queue_util_pct'].get(lane) or 0) for r in runs)
                am = max((r['peak_event_age_s'].get(lane) or 0) for r in runs)
                bl = [r['consumer_backlogged_median'].get(lane) for r in runs
                      if r.get('consumer_backlogged_median', {}).get(lane)]
                idl = [r['consumer_idle_median'].get(lane) for r in runs
                       if r.get('consumer_idle_median', {}).get(lane)]
                bl_med = sorted(bl)[len(bl) // 2] if bl else None
                idl_med = sorted(idl)[len(idl) // 2] if idl else None
                # Collapse signature: throughput markedly LOWER while backlogged.
                if bl_med is not None and idl_med is not None and bl_med < idl_med * 0.5:
                    collapse_ok = False
                print(f'{lane:<8}{pp:>12.1f}{pc:>12.1f}{qm:>8}{qu:>9.1f}{am:>9.2f}'
                      f'{(f"{bl_med:.1f}" if bl_med else "-"):>14}{(f"{idl_med:.1f}" if idl_med else "-"):>11}')
            required_drops = sum(r.get('required_drops_delta') or 0 for r in runs)
            coalesced = sum(r.get('coalesced_delta') or 0 for r in runs)
            severe = sum(r.get('severe_samples') or 0 for r in runs)
            critical = sum(r.get('critical_samples') or 0 for r in runs)
            longest = max((r.get('longest_backpressure_seconds') or 0) for r in runs)
            episodes = sum(r.get('episodes') or 0 for r in runs)
            print(f'\ncausally-required drops (spot+futures) : {required_drops}   <- gate: 0')
            print(f'coalesced replaceable book events      : {coalesced} (by design, not loss)')
            print(f'severe=True samples                    : {severe}')
            print(f'CRITICAL samples                       : {critical}')
            print(f'backpressure episodes / longest        : {episodes} / {longest:.1f}s')
            print(f'congestion collapse (backlog->slower)  : {"NOT OBSERVED" if collapse_ok else "OBSERVED"}')
            gates['required_drops_zero'] = required_drops == 0
            gates['no_congestion_collapse'] = collapse_ok
            gates['no_critical_state'] = critical == 0

    # ---- resources --------------------------------------------------------
    print(f'\n-- RESOURCES --')
    rss = _series(rows, 'collector_usage', 'rss_mb')
    if rss:
        drift = rss[-1] - rss[0]
        print(f'collector RSS  : {rss[0]:.0f} -> {rss[-1]:.0f} MB  (max {max(rss):.0f}, drift {drift:+.0f} MB)')
        gates['no_ram_creep'] = drift < 150
    uptime = _series(rows, 'collector', 'uptime_seconds')
    restarts = sum(1 for a, b in zip(uptime, uptime[1:]) if b < a) if len(uptime) > 1 else 0
    print(f'collector restarts during soak : {restarts}')
    free = _series(rows, 'disk_free_gb')
    if free:
        print(f'disk free      : {free[0]:.1f} -> {free[-1]:.1f} GB')

    # ---- storage ----------------------------------------------------------
    print(f'\n-- STORAGE --')
    mb = _series(rows, 'persistent_mb')
    if mb and hours > 0:
        growth = (mb[-1] - mb[0]) / hours * 24
        print(f'persistent     : {mb[0]:.1f} -> {mb[-1]:.1f} MB   projected {growth:.1f} MB/24h   gate <=100')
        gates['storage'] = growth <= 100
    raw = _series(rows, 'raw_dir_gb')
    if raw:
        print(f'raw dir        : {raw[-1]:.3f} GB (must stay ~0 - wire stream is not archived)')

    # ---- signals ----------------------------------------------------------
    print(f'\n-- SIGNAL FUNNEL (delta over window) --')
    first_sig = next((r for r in rows if _get(r, 'signals', 'by_state')), None)
    if first_sig:
        a = _get(first_sig, 'signals', 'by_state') or {}
        b = _get(last, 'signals', 'by_state') or {}
        for state in sorted(set(a) | set(b)):
            print(f'  {str(state):<12} {b.get(state, 0) - a.get(state, 0):>5}   (total {b.get(state, 0)})')
        da = _get(first_sig, 'signals', 'by_direction') or {}
        dbb = _get(last, 'signals', 'by_direction') or {}
        print(f'  LONG {dbb.get("LONG", 0) - da.get("LONG", 0)}   SHORT {dbb.get("SHORT", 0) - da.get("SHORT", 0)}')
        print(f'\n  rejection reasons (cumulative):')
        for reason, n in sorted((_get(last, 'signals', 'rejection_reasons') or {}).items(), key=lambda kv: -kv[1]):
            print(f'    {n:>5}  {reason}')

    # ---- regression counters (the three fixes) ----------------------------
    print(f'\n-- REGRESSION GUARDS (delta must be 0) --')
    if first_sig:
        checks = {
            'lost entry quotes (NULL entry observations)': 'null_entry_observations',
            'outcomes-evidence failures (scheduler backlog)': 'outcomes_evidence_failures',
            'INVALID_DATA outcomes': 'invalid_data_outcomes',
        }
        for label, key in checks.items():
            delta = (_get(last, 'signals', key) or 0) - (_get(first_sig, 'signals', key) or 0)
            flag = 'OK' if delta == 0 else 'CHECK'
            print(f'  {label:<46} {delta:>5}  {flag}')
            if key in ('null_entry_observations', 'outcomes_evidence_failures'):
                gates[key] = delta == 0
        pins = _get(last, 'signals', 'raw_event_pins') or {}
        bad = {k: v for k, v in pins.items() if k in ('candidate', 'decision')}
        print(f'  candidate/decision raw pins (must be absent)   {bad or "none":>5}')
        gates['no_pin_regrowth'] = not bad
        obs = (_get(last, 'signals', 'observations_total') or 0) - (_get(first_sig, 'signals', 'observations_total') or 0)
        print(f'  observations registered in window              {obs:>5}')
        sched = _series(rows, 'signals', 'outcome_scheduler_age_s')
        if sched:
            print(f'  outcome_scheduler marker age max              {max(sched):>5.2f}s  (cancels setups above 10s)')

    # ---- errors -----------------------------------------------------------
    print(f'\n-- ERRORS --')
    inc = _series(rows, 'incident_count_cumulative')
    if inc:
        print(f'incidents      : {inc[0]} -> {inc[-1]}  (delta {inc[-1] - inc[0]})')
    if RECONNECTS.exists():
        events = [line for line in RECONNECTS.read_text(encoding='utf-8').splitlines() if line.strip()]
        print(f'feed state changes logged : {len(events)}')

    # ---- verdict ----------------------------------------------------------
    print(f'\n-- GATES --')
    gates['soak_duration'] = hours >= args.hours
    for name, ok in gates.items():
        print(f'  {"PASS" if ok else "FAIL"}  {name}')
    print(f'\nSOAK VERDICT: {"PASS" if all(gates.values()) else "FAIL"}')
    return 0 if all(gates.values()) else 2


if __name__ == '__main__':
    raise SystemExit(main())
