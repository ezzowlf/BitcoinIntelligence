"""Causal replay of recorded production features, in a separate journal.

This diagnoses SignalEngine; it does not claim lossless raw-feed replay.
"""
import json
import sqlite3
import sys
import tempfile
from collections import Counter
from datetime import datetime,UTC
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from bitcoin_cycle_analyzer.short_term.journal import Journal
from bitcoin_cycle_analyzer.short_term.outcome_engine import OutcomeEngine
from bitcoin_cycle_analyzer.short_term.signal_engine import SignalEngine

source=sqlite3.connect((ROOT/'runtime/waverun/journal.db').as_uri()+'?mode=ro',uri=True,timeout=2)
end=source.execute("SELECT max(timestamp) FROM events WHERE kind='features'").fetchone()[0]
start=end-3600
rows=source.execute("SELECT timestamp,payload FROM events WHERE kind='features' AND timestamp>=? AND timestamp<=? ORDER BY timestamp",(start,end)).fetchall()
directory=Path(tempfile.mkdtemp(prefix='mission-replay-',dir=ROOT/'ops'))
journal=Journal(directory/'journal.db');outcomes=OutcomeEngine(journal);engine=SignalEngine(journal,outcomes)
for stamp,raw in rows:
    feature=json.loads(raw)
    t=datetime.fromtimestamp(stamp,UTC)
    engine.tick(t)
    engine.evaluate(t,feature)
transitions=[row['payload'] for row in journal.rows('signal_transition',limit=100000)]
summary={'kind':'RECORDED_FEATURE_REPLAY_NOT_RAW_REPLAY','start':datetime.fromtimestamp(start,UTC).isoformat(),
    'end':datetime.fromtimestamp(end,UTC).isoformat(),'feature_rows':len(rows),
    'states':dict(Counter(row['state_to'] for row in transitions)),
    'reject_reasons':dict(Counter(reason for row in transitions for reason in row['reasons'])),
    'missing_evidence':dict(Counter(reason for row in transitions for reason in row['missing_evidence'])),
    'directions':{direction:dict(Counter(row['state_to'] for row in transitions if row['direction']==direction)) for direction in ('LONG','SHORT')},
    'limitation':'Historical feature records include the original degraded feed/storage/outcome gates. They cannot establish signal quality on a lossless pipeline.',
    'execution':'DISABLED'}
(directory/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
print(directory,flush=True);print(json.dumps(summary,indent=2),flush=True)
source.close()
