"""Measure the TAKEOFF performance gate: consumer capacity vs producer rate.

The gate (SS13-14) is not "the queue is currently empty" - a queue can look
empty while the consumer is only barely keeping up. What has to hold is that
sustainable consumer capacity exceeds the producer rate with reserve, queues
recover after a burst, and event age does not creep.

Rates come from the collector's own counters in runtime/waverun/backpressure.json:

    producer rate     = d(produced)  / d(wall)
    consumer rate     = d(consumed)  / d(wall)
    consumer capacity = d(consumed)  / d(processing_seconds)   <- throughput ceiling
    utilisation       = d(processing_seconds) / d(wall)         <- fraction of time busy

    python ops/perf_gate.py --seconds 300 --interval 10
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKPRESSURE = ROOT / 'runtime' / 'waverun' / 'backpressure.json'


def read() -> dict:
    return json.loads(BACKPRESSURE.read_text(encoding='utf-8'))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=float, default=300)
    parser.add_argument('--interval', type=float, default=10)
    args = parser.parse_args()

    first = read()
    t0 = time.time()
    peak_queue: dict[str, int] = {}
    peak_age: dict[str, float] = {}
    samples = 0
    deadline = t0 + args.seconds
    while time.time() < deadline:
        time.sleep(args.interval)
        current = read()
        samples += 1
        for lane, q in current.get('queues', {}).items():
            peak_queue[lane] = max(peak_queue.get(lane, 0), q.get('size', 0))
        for lane, m in current.get('metrics', {}).items():
            peak_age[lane] = max(peak_age.get(lane, 0.0), float(m.get('last_event_age_seconds') or 0))

    last = read()
    wall = time.time() - t0
    print(f'window {wall:.0f}s over {samples} samples   {datetime.now(UTC).isoformat()}')
    print(f'{"lane":<8}{"prod/s":>9}{"cons/s":>9}{"capacity/s":>12}{"util %":>9}'
          f'{"headroom":>10}{"qpeak":>7}{"qcap":>8}{"agepeak":>9}{"drops":>7}')
    verdicts = []
    for lane in sorted(last.get('metrics', {})):
        a, b = first['metrics'].get(lane, {}), last['metrics'][lane]
        produced = b.get('produced', 0) - a.get('produced', 0)
        consumed = b.get('consumed', 0) - a.get('consumed', 0)
        busy = b.get('processing_seconds', 0) - a.get('processing_seconds', 0)
        failed = b.get('failed', 0) - a.get('failed', 0)
        prod_rate = produced / wall
        cons_rate = consumed / wall
        capacity = (consumed / busy) if busy > 0 else float('inf')
        util = (busy / wall) * 100
        headroom = (capacity / prod_rate) if prod_rate > 0 else float('inf')
        qcap = last.get('queues', {}).get(lane, {}).get('capacity', 0)
        drops = sum(v for k, v in (last.get('dropped') or {}).items() if k.startswith(lane))
        print(f'{lane:<8}{prod_rate:>9.1f}{cons_rate:>9.1f}{capacity:>12.1f}{util:>9.1f}'
              f'{headroom:>9.1f}x{peak_queue.get(lane, 0):>7}{qcap:>8}'
              f'{peak_age.get(lane, 0):>9.2f}{drops:>7}')
        verdicts.append((lane, capacity > prod_rate, headroom, drops, failed))

    print()
    ok = True
    for lane, faster, headroom, drops, failed in verdicts:
        problems = []
        if not faster:
            problems.append('consumer capacity <= producer rate')
        if headroom < 2:
            problems.append(f'headroom only {headroom:.1f}x')
        if drops:
            problems.append(f'{drops} drops')
        if failed:
            problems.append(f'{failed} failed')
        if problems:
            ok = False
            print(f'  FAIL {lane}: ' + '; '.join(problems))
        else:
            print(f'  PASS {lane}: capacity {headroom:.0f}x the producer rate, no drops')
    print(f'\nPerformance gate: {"PASS" if ok else "FAIL"}')
    return 0 if ok else 2


if __name__ == '__main__':
    raise SystemExit(main())
