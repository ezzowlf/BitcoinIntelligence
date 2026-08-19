from __future__ import annotations

from statistics import mean

from .contracts import ModelOutput


def fuse(outputs: list[ModelOutput], horizon: int) -> dict:
    usable = [x for x in outputs if x.available and x.horizon_seconds == horizon]
    if not usable:
        return {"available": False, "p_up": .5, "p_down": .5, "p_no_move": 0.0, "expected_return": 0.0, "confidence": 0.0, "uncertainty": 1.0, "agreement": 0.0, "reasons": ()}
    probs = [(x.p_up, x.p_down, x.p_no_move) for x in usable]
    p_up, p_down, p_none = (mean(x[i] for x in probs) for i in range(3))
    directions = [1 if x.p_up > x.p_down else -1 if x.p_down > x.p_up else 0 for x in usable]
    agreement = sum(x == (1 if p_up > p_down else -1 if p_down > p_up else 0) for x in directions) / len(directions)
    return {"available": True, "p_up": p_up, "p_down": p_down, "p_no_move": p_none, "expected_return": mean(x.expected_return for x in usable), "confidence": mean(x.confidence for x in usable) * agreement, "uncertainty": 1 - agreement, "agreement": agreement, "reasons": tuple(r for x in usable for r in x.reasons)[:5]}
