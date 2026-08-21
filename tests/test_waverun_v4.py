import pytest

from bitcoin_cycle_analyzer.short_term.waverun_v4 import (
    ADVERSE_USD,
    HORIZONS_SECONDS,
    MAGNITUDES_USD,
    BookSnapshot,
    book_change,
    book_features,
    information_gain,
    source_health,
    v4_gate,
)


def test_v4_ladders_are_bounded():
    assert MAGNITUDES_USD == (100, 150, 200, 300, 400, 500, 600, 800)
    assert ADVERSE_USD == (25, 50, 75, 100, 150, 200)
    assert HORIZONS_SECONDS == (30, 60, 90, 120, 180, 300, 600)


def test_book_features_and_sequence_changes():
    left = BookSnapshot("t", ((99, 2),), ((101, 2),), 1, "x")
    right = BookSnapshot("t2", ((99, 1),), ((101, 3),), 2, "x")
    assert book_features(left)["depth_imbalance"] == 0
    change = book_change(left, right)
    assert change["bid_pull"] == 1 and change["ask_stack"] == 1


def test_book_sequence_integrity_blocks_reordering():
    book = BookSnapshot("t", ((99, 1),), ((101, 1),), 1, "x")
    try:
        book_change(book, book)
    except ValueError:
        pass
    else:
        raise AssertionError("sequence must increase")


def test_source_health_and_information_gain():
    assert source_health(0, 0, 0, 0, 0)["status"] == "UNAVAILABLE"
    assert source_health(10, 0, 0, 0, 0)["status"] == "GOOD"
    assert information_gain(0.25, 0.20) == pytest.approx(0.05)


def test_v4_gate_fails_without_new_evidence():
    assert v4_gate({})["passed"] is False
