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
