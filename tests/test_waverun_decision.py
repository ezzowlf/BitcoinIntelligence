from bitcoin_cycle_analyzer.waverun_decision import (
    DecisionInput,
    DecisionSignal,
    fast_decision,
)


def signal(group, name, direction, strength, explanation, available=True):
    return DecisionSignal(group, name, direction, strength, explanation, available)


def test_approved_requires_multiple_groups_cost_edge_and_calibration():
    result = fast_decision(DecisionInput(
        "BTCUSDT", "2026-08-21T12:00:00Z",
        (signal("L2", "imbalance", "BULLISH", .8, "persistent positive 10-level imbalance"),
         signal("FLOW", "signed_volume", "BULLISH", .7, "aggressive buy flow increasing"),
         signal("CROSS_EXCHANGE", "coinbase", "BULLISH", .6, "Coinbase confirms"),
         signal("DERIVATIVES", "oi", "BULLISH", .6, "OI rising with price")),
        .98, 1, "EARLY", "high-volatility trend", 1.0, True))
    assert result.decision == "APPROVED"
    assert result.direction == "LONG"
    assert result.execution == "DISABLED"
    assert "Coinbase confirms" in result.supporting_factors


def test_contradiction_fails_closed():
    result = fast_decision(DecisionInput(
        "BTCUSDT", "now",
        (signal("L2", "book", "BULLISH", .9, "book bullish"),
         signal("FLOW", "trades", "BEARISH", .9, "aggressive trades bearish"),
         signal("DERIVATIVES", "oi", "BULLISH", .7, "OI rising")),
        .99, 1, "EARLY", "trend", 1.0, True))
    assert result.decision == "BLOCKED"
    assert result.state == "CONFLICTED"
    assert result.confidence < 1


def test_missing_data_never_becomes_approval():
    result = fast_decision(DecisionInput(
        "BTCUSDT", "now",
        (signal("L2", "book", "BULLISH", .9, "book bullish"),),
        .99, 1, "EARLY", "trend", 1.0, True))
    assert result.decision in {"BLOCKED", "WATCH"}


def test_unknown_timing_is_unverified_not_a_hard_blocker():
    result = fast_decision(DecisionInput(
        "BTCUSDT", "now",
        (signal("L2", "book", "BULLISH", .9, "book bullish"),
         signal("FLOW", "trades", "BULLISH", .8, "flow bullish"),
         signal("DERIVATIVES", "oi", "BULLISH", .7, "OI confirms")),
        .99, 1, "UNKNOWN", "trend", None, False))
    assert result.decision == "ARMED"
    assert result.state == "BULLISH"
    assert result.invalidation_reason.startswith("LIVE SIGNAL UNVERIFIED:")
    assert result.execution == "DISABLED"


def test_unavailable_optional_groups_cap_at_unverified_instead_of_blocking():
    result = fast_decision(DecisionInput(
        "BTCUSDT", "now",
        (signal("L2", "book", "BEARISH", .9, "book bearish"),
         signal("FLOW", "trades", "BEARISH", .8, "flow bearish")),
        .99, 1, "EARLY", "trend", None, False))
    assert result.decision == "ARMED"
    assert result.state == "BEARISH"
    assert "sources unavailable" in result.invalidation_reason
    assert "CROSS_EXCHANGE" in result.invalidation_reason
    assert "DERIVATIVES" in result.invalidation_reason


def test_late_timing_remains_a_hard_counterindication():
    result = fast_decision(DecisionInput(
        "BTCUSDT", "now",
        (signal("L2", "book", "BULLISH", .9, "book bullish"),
         signal("FLOW", "trades", "BULLISH", .8, "flow bullish"),
         signal("DERIVATIVES", "oi", "BULLISH", .7, "OI confirms")),
        .99, 1, "LATE", "trend", 1.0, True))
    assert result.decision == "BLOCKED"
    assert result.invalidation_reason == "late timing is an explicit counterindication"
