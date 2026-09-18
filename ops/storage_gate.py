"""Measure real TAKEOFF persistent-growth against the <=100MB/24h storage gate.

Takes byte-accurate samples of every persistent TAKEOFF location (not just one
directory) and reports the delta between the first and last sample as MB/h plus
the projected MB/24h. No theoretical claims - only measured deltas.

    python ops/storage_gate.py --baseline            # write a baseline sample
    python ops/storage_gate.py --sample              # append a sample
    python ops/storage_gate.py --report              # delta vs baseline

Sample history lives in ops/storage_gate_samples.jsonl so a long measurement
survives restarts of whatever drives it.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / 'ops' / 'storage_gate_samples.jsonl'

# Every location TAKEOFF grows persistently, by category (§10).
GROUPS: dict[str, list[Path]] = {
    'database': [ROOT / 'database'],
    'raw': [ROOT / 'runtime' / 'waverun' / 'raw'],
    'runtime': [ROOT / 'runtime'],           # minus raw, subtracted below
    'logs': [ROOT / 'logs'],
    'diagnostics': [ROOT / 'ops' / 'soak'],
    'exports': [ROOT / 'exports'],
}


def _size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for entry in path.rglob('*'):
        try:
            if entry.is_file():
                total += entry.stat().st_size
        except OSError:
            continue  # vanished mid-scan (rotation/GC) - not part of the delta
    return total


def sample() -> dict:
    sizes = {name: sum(_size(p) for p in paths) for name, paths in GROUPS.items()}
    # runtime is measured whole then reduced by raw so the categories sum cleanly.
    sizes['runtime'] = max(0, sizes['runtime'] - sizes['raw'])
    return {
        'timestamp': datetime.now(UTC).isoformat(),
        'monotonic': time.time(),
        'sizes': sizes,
        'total': sum(sizes.values()),
    }


def _load() -> list[dict]:
    if not SAMPLES.exists():
        return []
    return [json.loads(line) for line in SAMPLES.read_text(encoding='utf-8').splitlines() if line.strip()]


def _append(row: dict) -> None:
    SAMPLES.parent.mkdir(parents=True, exist_ok=True)
    with SAMPLES.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(row, sort_keys=True) + '\n')


def report() -> int:
    rows = _load()
    if len(rows) < 2:
        print(f'need at least 2 samples, have {len(rows)}')
        return 1
    first, last = rows[0], rows[-1]
    hours = (last['monotonic'] - first['monotonic']) / 3600
    if hours <= 0:
        print('samples are not separated in time')
        return 1
    print(f'window: {first["timestamp"]} -> {last["timestamp"]}  ({hours:.3f} h, {len(rows)} samples)')
    print(f'{"category":<14}{"delta MB":>12}{"MB/h":>12}{"MB/24h":>12}')
    total_per_h = 0.0
    for name in GROUPS:
        delta = (last['sizes'].get(name, 0) - first['sizes'].get(name, 0)) / 1e6
        per_h = delta / hours
        total_per_h += per_h
        print(f'{name:<14}{delta:>12.2f}{per_h:>12.2f}{per_h * 24:>12.2f}')
    total_delta = (last['total'] - first['total']) / 1e6
    print(f'{"TOTAL":<14}{total_delta:>12.2f}{total_per_h:>12.2f}{total_per_h * 24:>12.2f}')
    projected = total_per_h * 24
    verdict = 'PASS' if projected <= 100 else 'FAIL'
    print(f'\nProjected TOTAL: {projected:.2f} MB/24h   gate <=100 MB/24h   {verdict}')
    return 0 if projected <= 100 else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true', help='reset history and write the first sample')
    parser.add_argument('--sample', action='store_true')
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args()
    if args.baseline:
        SAMPLES.unlink(missing_ok=True)
        row = sample()
        _append(row)
        print(f'baseline {row["total"] / 1e6:.2f} MB at {row["timestamp"]}')
        return 0
    if args.sample:
        row = sample()
        _append(row)
        print(f'sample   {row["total"] / 1e6:.2f} MB at {row["timestamp"]}')
        return 0
    if args.report:
        return report()
    parser.error('choose --baseline, --sample or --report')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
