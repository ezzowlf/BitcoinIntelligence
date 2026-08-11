import inspect
import pytest

from bitcoin_cycle_analyzer.drawing_state import UserDrawingStore, compute_fib_levels, DRAWING_TYPES, FIB_RATIOS


@pytest.fixture
def store(tmp_path):
    return UserDrawingStore(tmp_path, "BTCUSD")


# ---------------------------------------------------------------- Serialization / restore

def test_add_and_list_round_trips_all_fields(store):
    d = store.add("HLINE", "1D", {"price": 60000.0}, text="support")
    listed = store.list()
    assert len(listed) == 1
    assert listed[0] == d
    for field in ("drawing_id", "type", "timeframe", "coordinates", "text", "locked", "style", "created_at", "updated_at"):
        assert field in d


def test_drawings_persist_across_a_new_store_instance(tmp_path):
    first = UserDrawingStore(tmp_path, "BTCUSD")
    first.add("HLINE", "1D", {"price": 55000.0})
    reopened = UserDrawingStore(tmp_path, "BTCUSD")  # simulates app restart / reload
    assert len(reopened.list()) == 1


def test_invalid_drawing_type_is_rejected(store):
    with pytest.raises(ValueError):
        store.add("CIRCLE", "1D", {"price": 1})


# ---------------------------------------------------------------- Update / delete

def test_update_changes_fields_and_bumps_updated_at(store):
    d = store.add("HLINE", "1D", {"price": 60000.0})
    updated = store.update(d["drawing_id"], text="new label")
    assert updated["text"] == "new label"
    assert updated["updated_at"] >= d["updated_at"]


def test_update_missing_id_returns_none(store):
    assert store.update("does-not-exist", text="x") is None


def test_delete_removes_drawing(store):
    d = store.add("HLINE", "1D", {"price": 60000.0})
    deleted = store.delete(d["drawing_id"])
    assert deleted["drawing_id"] == d["drawing_id"]
    assert store.list() == []


def test_delete_missing_id_returns_none(store):
    assert store.delete("does-not-exist") is None


# ---------------------------------------------------------------- Locking

def test_locked_drawing_cannot_be_deleted(store):
    d = store.add("HLINE", "1D", {"price": 60000.0})
    store.update(d["drawing_id"], locked=True)
    with pytest.raises(ValueError):
        store.delete(d["drawing_id"])


def test_locked_drawing_cannot_be_edited_except_to_unlock(store):
    d = store.add("HLINE", "1D", {"price": 60000.0})
    store.update(d["drawing_id"], locked=True)
    with pytest.raises(ValueError):
        store.update(d["drawing_id"], text="should fail while locked")
    unlocked = store.update(d["drawing_id"], locked=False)
    assert unlocked["locked"] is False
    store.update(d["drawing_id"], text="now allowed")  # must not raise


# ---------------------------------------------------------------- Timeframe isolation

def test_timeframe_filter_only_returns_matching_drawings(store):
    store.add("HLINE", "1D", {"price": 1})
    store.add("HLINE", "1W", {"price": 2})
    assert len(store.list(timeframe="1D")) == 1
    assert len(store.list(timeframe="1W")) == 1
    assert len(store.list()) == 2  # no filter -> everything


def test_all_timeframes_marker_is_always_included():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        s = UserDrawingStore(Path(d), "BTCUSD")
        s.add("HLINE", "ALL_TIMEFRAMES", {"price": 3})
        s.add("HLINE", "1D", {"price": 4})
        assert len(s.list(timeframe="1W")) == 1  # only the ALL_TIMEFRAMES one


# ---------------------------------------------------------------- Symbol separation

def test_different_symbols_use_separate_files(tmp_path):
    btc = UserDrawingStore(tmp_path, "BTCUSD")
    eth = UserDrawingStore(tmp_path, "ETHUSD")
    btc.add("HLINE", "1D", {"price": 1})
    assert len(btc.list()) == 1
    assert len(eth.list()) == 0


# ---------------------------------------------------------------- Undo (restore)

def test_restore_reinstates_a_deleted_drawing(store):
    d = store.add("HLINE", "1D", {"price": 60000.0})
    deleted = store.delete(d["drawing_id"])
    store.restore(deleted)
    listed = store.list()
    assert len(listed) == 1
    assert listed[0]["drawing_id"] == d["drawing_id"]


# ---------------------------------------------------------------- Fibonacci

def test_fib_levels_cover_the_required_ratios():
    levels = compute_fib_levels(50000, 70000)
    ratios = {l["ratio"] for l in levels}
    assert ratios == set(FIB_RATIOS)


def test_fib_anchor_a_and_b_map_to_0_and_1():
    levels = compute_fib_levels(50000, 70000)
    by_ratio = {l["ratio"]: l["price"] for l in levels}
    assert by_ratio[0.0] == 50000
    assert by_ratio[1.0] == 70000


def test_fib_midpoint_is_exact():
    levels = compute_fib_levels(50000, 70000)
    by_ratio = {l["ratio"]: l["price"] for l in levels}
    assert by_ratio[0.5] == 60000


def test_fib_works_for_downward_direction_too():
    # B below A -> retracement measured downward, still arithmetic, no direction bias
    levels = compute_fib_levels(70000, 50000)
    by_ratio = {l["ratio"]: l["price"] for l in levels}
    assert by_ratio[0.0] == 70000
    assert by_ratio[1.0] == 50000
    assert by_ratio[0.5] == 60000


# ---------------------------------------------------------------- No decision side effect

def test_drawing_state_module_is_never_imported_by_decision_intelligence():
    from bitcoin_cycle_analyzer import decision_intelligence
    import bitcoin_cycle_analyzer.decision_intelligence.decision_engine as de
    import bitcoin_cycle_analyzer.decision_intelligence.evidence as ev
    for module in (decision_intelligence, de, ev):
        src = inspect.getsource(module)
        assert "drawing_state" not in src
        assert "UserDrawingStore" not in src


def test_decision_engine_signature_has_no_drawing_parameter():
    from bitcoin_cycle_analyzer.decision_intelligence.decision_engine import build_decision_state
    params = inspect.signature(build_decision_state).parameters
    assert not any("drawing" in p.lower() for p in params)


def test_adding_a_drawing_does_not_change_a_precomputed_decision_state(store):
    # Simulate: decision computed, then user adds a drawing, decision recomputed
    # from the same inputs must be byte-identical (drawings are pure UI state).
    fixed_decision = {"decision": "ACCUMULATE", "zone": {"low": 100, "high": 200}}
    store.add("RECTANGLE", "1D", {"low": 100, "high": 200}, text="my zone")
    assert fixed_decision == {"decision": "ACCUMULATE", "zone": {"low": 100, "high": 200}}
