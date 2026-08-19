from __future__ import annotations

from .contracts import ModelOutput


def _output(name: str, horizon: int, score: float, confidence: float, reason: str) -> ModelOutput:
    score = max(-1.0, min(1.0, score))
    p_up = 0.5 + score * 0.25
    p_down = 0.5 - score * 0.25
    p_no_move = max(0.0, 1.0 - abs(score) * 0.5)
    total = p_up + p_down + p_no_move
    return ModelOutput(name, horizon, p_up / total, p_down / total, p_no_move / total, score * 0.001, confidence, (reason,))


def price_action(features, horizon: int) -> ModelOutput:
    momentum = float(features.get("momentum", 0.0))
    return _output("price_action_baseline", horizon, momentum / 0.01, min(1.0, features["sample_size"] / 30), "short momentum and range")


def order_flow(features, horizon: int) -> ModelOutput:
    imbalance = float(features.get("volume_imbalance", 0.0))
    return _output("order_flow_baseline", horizon, imbalance, min(1.0, features["sample_size"] / 20), "buy/sell volume imbalance")


def orderbook(features, horizon: int) -> ModelOutput:
    imbalance = features.get("orderbook_imbalance")
    if imbalance is None:
        return ModelOutput("orderbook_baseline", horizon, .5, .5, 0.0, 0.0, 0.0, ("order book unavailable",), False)
    return _output("orderbook_baseline", horizon, float(imbalance), .6, "order book imbalance")
