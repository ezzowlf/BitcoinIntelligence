from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ScoreResult:
    total: float
    classification: str
    components: dict[str, float]
    explanations: dict[str, str]


LABELS = [(40, "keine attraktive Kaufchance"), (60, "beobachten"), (75, "interessante Kaufzone"), (90, "starke historische Kaufzone"), (101, "außergewöhnliche historische Konstellation")]


def calculate_score(signals: dict[str, float], weights: dict[str, float], explanations: dict[str, str] | None = None) -> ScoreResult:
    if set(signals) != set(weights):
        raise ValueError("signals and weights must contain identical components")
    if sum(weights.values()) != 100:
        raise ValueError("weights must sum to 100")
    components = {name: round(max(0, min(1, signals[name])) * weight, 2) for name, weight in weights.items()}
    total = round(sum(components.values()), 2)
    classification = next(label for ceiling, label in LABELS if total < ceiling)
    return ScoreResult(total, classification, components, explanations or {})


def states(score: ScoreResult, confirmation: float, risk: float) -> dict:
    return {"value_zone": "HIGH" if score.total >= 75 else "MEDIUM" if score.total >= 60 else "LOW", "confirmation": "HIGH" if confirmation >= .7 else "MEDIUM" if confirmation >= .4 else "LOW", "risk": "HIGH" if risk >= .7 else "MEDIUM" if risk >= .4 else "LOW"}
