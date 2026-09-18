"""Read-only production capacity evidence; never constructs a writer engine."""
import json
import sqlite3
import time
from datetime import datetime, UTC
from pathlib import Path

root = Path(__file__).resolve().parents[1]
db = sqlite3.connect((root / 'runtime/waverun/journal.db').as_uri() + '?mode=ro', uri=True, timeout=2)
print('UTC', datetime.now(UTC).isoformat(), flush=True)
queries = {
    'observations_status': 'SELECT status,count(*) FROM observations GROUP BY status',
    'observations_kind': 'SELECT kind,count(*) FROM observations GROUP BY kind',
    'pending_due': "SELECT count(*),min(due_at),max(due_at) FROM observations WHERE status='PENDING'",
    'outbox': 'SELECT count(*) FROM outcome_outbox',
    'progress': 'SELECT stage,seq,event_at,committed_at FROM progress',
    'cursor_query_plan': "EXPLAIN QUERY PLAN SELECT seq,id,timestamp,payload FROM events WHERE kind='outcome' AND seq>2400000 ORDER BY seq LIMIT 1000",
    'recent_incidents': "SELECT timestamp,payload FROM events WHERE kind='incident' ORDER BY timestamp DESC LIMIT 10",
}
for label, query in queries.items():
    started = time.monotonic()
    db.set_progress_handler(lambda: int(time.monotonic() - started > 120), 10000)
    try:
        print(json.dumps({'query': label, 'rows': db.execute(query).fetchall(), 'seconds': time.monotonic()-started}), flush=True)
    except sqlite3.Error as error:
        print(label, type(error).__name__, str(error), flush=True)
db.close()
