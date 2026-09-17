"""Storage-growth fix: rotated audit jsonl files (decision_records.*, pre_gate_candidates.*)
duplicate what journal.db already retains durably (14-day prune) and were never cleaned up -
measured 2026-09-17: 78+58 rotated files, ~1.09GB, unbounded. _append now caps how many
rotated files accumulate per stem, but only ever deletes files THIS process rotated itself -
a pre-existing backlog on disk when the process starts must never be touched automatically."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / 'src'), str(REPO / 'scripts')]
import waverun_live


def test_append_rotates_at_size_threshold(tmp_path):
    path = tmp_path / 'decision_records.jsonl'
    big = {'pad': 'x' * (9 * 1024 * 1024)}
    waverun_live.LiveSession._append(path, big)
    waverun_live.LiveSession._append(path, {'small': 1})
    rotated = list(tmp_path.glob('decision_records.*.jsonl'))
    assert len(rotated) == 1
    assert path.exists()
    assert json.loads(path.read_text().strip()) == {'small': 1}


def test_append_only_caps_files_rotated_by_this_process(tmp_path, monkeypatch):
    monkeypatch.setattr(waverun_live.LiveSession, '_rotated_since_start', set())
    monkeypatch.setattr(waverun_live.LiveSession, '_ROTATED_KEEP', 2)
    path = tmp_path / 'decision_records.jsonl'
    # Pre-existing backlog on disk before this process ever touches the file -
    # must never be auto-deleted, no matter how many rotations happen afterward.
    preexisting = [tmp_path / f'decision_records.pre{i}.jsonl' for i in range(5)]
    for p in preexisting:
        p.write_text('{}\n')
    big = {'pad': 'x' * (9 * 1024 * 1024)}
    for _ in range(4):
        waverun_live.LiveSession._append(path, big)
    for p in preexisting:
        assert p.exists(), f'pre-existing rotated file {p} must never be auto-deleted'
    own_rotated = [p for p in tmp_path.glob('decision_records.*.jsonl') if p not in preexisting]
    assert len(own_rotated) == waverun_live.LiveSession._ROTATED_KEEP
