"""Audit what the signal engine actually decided on live data, and why (SS18).

Separates the two explanations for "no LIVE signal":
  MARKET   - the rules were evaluated and not met. Correct behaviour.
  BLOCKER  - a technical condition stopped the evaluation from being able to
             qualify at all (stale feed, missing feature, unavailable quote,
             disk gate, degraded data quality). That is a bug.

Reads only what the collector already persists, so it can run against a live
system without touching it.

    python ops/signal_audit.py [--hours 1]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOURNAL = ROOT / 'runtime' / 'waverun' / 'journal.db'

# Conditions that mean the pipeline could not fairly evaluate the rules.
BLOCKER_MARKERS = (
    'STALE', 'UNAVAILABLE', 'OFFLINE', 'MISSING', 'DISK', 'STORAGE',
    'QUEUE', 'BACKPRESSURE', 'NOT_READY', 'INSUFFICIENT_CONTEXT',
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--hours', type=float, default=1.0)
    args = parser.parse_args()
    cutoff = time.time() - args.hours * 3600

    db = sqlite3.connect(f'file:{JOURNAL.as_posix()}?mode=ro', uri=True)
    db.execute('PRAGMA busy_timeout=4000')

    def rows(kind):
        return [json.loads(p) for (p,) in db.execute(
            'SELECT payload FROM events WHERE kind=? AND timestamp>=? ORDER BY timestamp', (kind, cutoff))]

    decisions = rows('decision')
    transitions = rows('signal_transition')
    incidents = rows('incident')
    outcomes = rows('outcome')

    print(f'=== signal audit, last {args.hours}h ===')
    print(f'persisted decision samples : {len(decisions)}')

    verdicts = Counter()
    directions = Counter()
    for row in decisions:
        legacy = row.get('legacy') or {}
        verdicts[str(legacy.get('decision', 'UNKNOWN'))] += 1
        directions[str(legacy.get('direction', 'NONE'))] += 1
    print('  decision verdicts :', dict(verdicts))
    print('  direction bias    :', dict(directions))

    states = Counter(str(t.get('state_to')) for t in transitions)
    print(f'\nsignal transitions : {len(transitions)}  {dict(states)}')
    for t in transitions[-12:]:
        print(f"    {t.get('timestamp','')[11:19]}  {str(t.get('state_from')):<11}-> "
              f"{str(t.get('state_to')):<11} {str(t.get('direction')):<6} "
              f"{','.join(t.get('reasons') or [])[:52]}")

    print(f'\nLONG transitions   : {sum(1 for t in transitions if t.get("direction") == "LONG")}')
    print(f'SHORT transitions  : {sum(1 for t in transitions if t.get("direction") == "SHORT")}')
    print(f'reached LIVE       : {states.get("LIVE", 0)}')

    # Why did setups not progress? Aggregate the engine's own stated reasons.
    reasons = Counter()
    missing = Counter()
    conflicts = Counter()
    for t in transitions:
        for r in t.get('reasons') or []:
            reasons[str(r)] += 1
        for m in t.get('missing_evidence') or []:
            missing[str(m)] += 1
        for c in t.get('conflicts') or []:
            conflicts[str(c)] += 1
    print('\nreasons          :', dict(reasons))
    print('missing evidence :', dict(missing) or '(none)')
    print('conflicts        :', dict(conflicts) or '(none)')

    # Technical blockers vs market decisions.
    blockers = Counter()
    for label, bucket in (('missing_evidence', missing), ('conflict', conflicts)):
        for key, n in bucket.items():
            if any(marker in key.upper() for marker in BLOCKER_MARKERS):
                blockers[f'{label}:{key}'] += n
    for inc in incidents:
        blockers[f"incident:{inc.get('reason', 'UNKNOWN')}"] += 1
    print('\n--- technical blockers (bugs, not market) ---')
    print('  ', dict(blockers) or 'NONE - every non-signal was a market decision')

    resolved = Counter(str(o.get('status')) for o in outcomes)
    print(f'\noutcomes resolved  : {len(outcomes)}  {dict(resolved)}')
    hits = sum(1 for o in outcomes if (o.get('targets') or {}) and
               any(t.get('hit') for t in (o.get('targets') or {}).values()))
    print(f'  with a target hit: {hits}')
    db.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
