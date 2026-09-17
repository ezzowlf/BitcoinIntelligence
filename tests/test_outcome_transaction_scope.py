from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from bitcoin_cycle_analyzer.short_term.journal import Journal
from bitcoin_cycle_analyzer.short_term.outcome_engine import OutcomeEngine
import bitcoin_cycle_analyzer.short_term.outcome_engine as module


def test_outcome_calculation_does_not_hold_writer_transaction(tmp_path, monkeypatch):
    active = []

    class TrackedJournal(Journal):
        @contextmanager
        def connect(self):
            with super().connect() as db:
                active.append(db)
                try:
                    yield db
                finally:
                    active.remove(db)

    journal = TrackedJournal(tmp_path / 'journal.db')
    engine = OutcomeEngine(journal)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(60):
        engine.register(str(i), 'CANDIDATE', now, 'LONG', bid=10000, ask=10001,
                        horizons=(30,), payload={'calculation_probe': True})
    loads = module.json.loads
    checks = []

    def checked_loads(value, *args, **kwargs):
        if value == '{"calculation_probe": true}':
            checks.append(True)
            assert not any(db.in_transaction for db in active)
        return loads(value, *args, **kwargs)

    monkeypatch.setattr(module.json, 'loads', checked_loads)
    results = engine.resolve_due(now + timedelta(seconds=40))
    assert len(results) == len(checks) == 60
    assert all(r['status'] == 'INSUFFICIENT_FUTURE_DATA' for r in results)
    assert len(journal.rows('outcome')) == 60
