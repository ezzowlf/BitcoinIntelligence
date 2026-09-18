"""High-frequency burst/capacity monitor for the final 24h soak.

The ten-minute soak sampler cannot see a burst: the previous production
failure peaked around 1250 events/s and a two-minute episode would fall
entirely between two samples. This samples backpressure.json at 1Hz, keeps
running maxima and tracks backpressure EPISODES, so the final report can
answer the burst/capacity gate from measured peaks rather than averages.

Read-only. Never touches the collector, never writes runtime state.

Storage is bounded by design: one compact summary line per run (288/day) plus
an episode line only when something notable actually happens.

    python ops/soak/burst_monitor.py --seconds 295

Intended to be driven every 5 minutes by a scheduled task, so a crashed run
self-heals on the next tick instead of needing a daemon.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / 'runtime' / 'waverun'
OUT = ROOT / 'ops' / 'soak'
SUMMARIES = OUT / 'burst_summaries.jsonl'
EPISODES = OUT / 'burst_episodes.jsonl'

LANES = ('book', 'futures', 'spot', 'l2')
# Causally required lanes. bookTicker is replaceable and is coalesced on
# purpose, so its shed events are NOT drops and must never be mixed in.
REQUIRED = ('spot', 'futures')
IDLE_QUEUE = 10          # a queue at or below this counts as recovered
IDLE_AGE = 2.0           # seconds; event age at or below this counts as recovered


def _read(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=float, default=295)
    parser.add_argument('--interval', type=float, default=1.0)
    args = parser.parse_args()

    started = datetime.now(UTC)
    deadline = time.time() + args.seconds
    prev = None
    prev_t = None
    samples = 0

    peak_prod = {lane: 0.0 for lane in LANES}
    peak_cons = {lane: 0.0 for lane in LANES}
    peak_queue = {lane: 0 for lane in LANES}
    peak_util = {lane: 0.0 for lane in LANES}
    peak_age = {lane: 0.0 for lane in LANES}
    capacity = {lane: 0 for lane in LANES}
    # The decisive congestion-collapse test. The old failure mode was
    # "backlog up -> per-event cost up -> throughput DOWN -> backlog up".
    # So compare consumer throughput while the lane is backlogged against
    # while it is idle. Healthy: backlogged >= idle (the consumer works at
    # least as hard when there is work queued). Collapsed: backlogged well
    # below idle, which is what 18/s vs 150/s looked like.
    backlogged = {lane: [] for lane in LANES}
    idle = {lane: [] for lane in LANES}
    drops_start, drops_end = None, None
    coalesced_start, coalesced_end = None, None
    severe_samples = 0
    critical_samples = 0
    states = {}
    # A backpressure episode: queue above idle on any lane, or severe.
    episode = None
    longest_episode = 0.0
    episodes = []

    while time.time() < deadline:
        bp = _read(RUNTIME / 'backpressure.json')
        health = _read(RUNTIME / 'health.json') or {}
        now = time.time()
        if bp:
            samples += 1
            metrics = bp.get('metrics') or {}
            queues = bp.get('queues') or {}
            state = health.get('operating_state')
            states[state] = states.get(state, 0) + 1
            if state == 'CRITICAL':
                critical_samples += 1
            if bp.get('severe'):
                severe_samples += 1

            drops = sum(v for k, v in (bp.get('dropped') or {}).items() if k in REQUIRED)
            coalesced = sum((bp.get('coalesced') or {}).values())
            if drops_start is None:
                drops_start, coalesced_start = drops, coalesced
            drops_end, coalesced_end = drops, coalesced

            busy = False
            for lane in LANES:
                m = metrics.get(lane) or {}
                q = queues.get(lane) or {}
                size = q.get('size') or 0
                cap = q.get('capacity') or 0
                capacity[lane] = cap or capacity[lane]
                age = float(m.get('last_event_age_seconds') or 0)
                peak_queue[lane] = max(peak_queue[lane], size)
                peak_age[lane] = max(peak_age[lane], age)
                if cap:
                    peak_util[lane] = max(peak_util[lane], 100.0 * size / cap)
                if size > IDLE_QUEUE or age > IDLE_AGE:
                    busy = True
                if prev and prev_t and now > prev_t:
                    pm = (prev.get('metrics') or {}).get(lane) or {}
                    dt = now - prev_t
                    dp = (m.get('produced') or 0) - (pm.get('produced') or 0)
                    dc = (m.get('consumed') or 0) - (pm.get('consumed') or 0)
                    if dp >= 0:
                        peak_prod[lane] = max(peak_prod[lane], dp / dt)
                    if dc >= 0:
                        rate = dc / dt
                        peak_cons[lane] = max(peak_cons[lane], rate)
                        # Only count windows where there was work to do, so an
                        # idle-but-quiet market does not look like a collapse.
                        if rate > 0:
                            (backlogged if size > 500 else idle)[lane].append(rate)

            if busy and episode is None:
                episode = {'start': datetime.now(UTC).isoformat(), 'start_t': now,
                           'peak_queue': 0, 'peak_age': 0.0, 'drops_at_start': drops}
            if episode:
                episode['peak_queue'] = max(episode['peak_queue'], max(
                    (queues.get(l) or {}).get('size') or 0 for l in LANES))
                episode['peak_age'] = max(episode['peak_age'], max(
                    float((metrics.get(l) or {}).get('last_event_age_seconds') or 0) for l in LANES))
                if not busy:
                    episode['end'] = datetime.now(UTC).isoformat()
                    episode['recovery_seconds'] = round(now - episode['start_t'], 1)
                    episode['required_drops'] = drops - episode['drops_at_start']
                    longest_episode = max(longest_episode, episode['recovery_seconds'])
                    episode.pop('start_t'); episode.pop('drops_at_start')
                    episodes.append(episode)
                    episode = None
            prev, prev_t = bp, now
        time.sleep(args.interval)

    if episode:  # still in an episode when the run ended
        episode['end'] = None
        episode['recovery_seconds'] = round(time.time() - episode['start_t'], 1)
        episode['required_drops'] = (drops_end or 0) - episode['drops_at_start']
        episode['ongoing'] = True
        longest_episode = max(longest_episode, episode['recovery_seconds'])
        episode.pop('start_t'); episode.pop('drops_at_start')
        episodes.append(episode)

    summary = {
        'start': started.isoformat(),
        'end': datetime.now(UTC).isoformat(),
        'samples': samples,
        'peak_producer_per_s': {k: round(v, 1) for k, v in peak_prod.items()},
        'peak_consumer_per_s': {k: round(v, 1) for k, v in peak_cons.items()},
        'peak_queue': peak_queue,
        'queue_capacity': capacity,
        'peak_queue_util_pct': {k: round(v, 1) for k, v in peak_util.items()},
        'peak_event_age_s': {k: round(v, 2) for k, v in peak_age.items()},
        'required_drops_delta': (drops_end or 0) - (drops_start or 0),
        'coalesced_delta': (coalesced_end or 0) - (coalesced_start or 0),
        'severe_samples': severe_samples,
        'critical_samples': critical_samples,
        'operating_states': states,
        'episodes': len(episodes),
        'longest_backpressure_seconds': longest_episode,
        # Congestion-collapse evidence: median consumer throughput while
        # backlogged vs while idle, per lane. Healthy is backlogged >= idle.
        'consumer_backlogged_median': {
            lane: (round(sorted(v)[len(v) // 2], 1) if v else None) for lane, v in backlogged.items()},
        'consumer_idle_median': {
            lane: (round(sorted(v)[len(v) // 2], 1) if v else None) for lane, v in idle.items()},
        'backlogged_windows': {lane: len(v) for lane, v in backlogged.items()},
        'execution': 'DISABLED',
    }
    OUT.mkdir(parents=True, exist_ok=True)
    with SUMMARIES.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(summary, sort_keys=True) + '\n')
    if episodes:
        with EPISODES.open('a', encoding='utf-8') as handle:
            for row in episodes:
                handle.write(json.dumps(row, sort_keys=True) + '\n')
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
