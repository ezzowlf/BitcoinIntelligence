from __future__ import annotations


def evidence_score(sample_size: int, data_quality: float, module_agreement: float, oos_quality: float, provider_coverage: float) -> dict:
    sample = min(1, sample_size / 20)
    inputs = {"sample_size": sample, "data_quality": data_quality, "module_agreement": module_agreement, "oos_quality": oos_quality, "provider_coverage": provider_coverage}
    bounded = {key: max(0, min(1, float(value))) for key, value in inputs.items()}
    weights = {"sample_size": .25, "data_quality": .25, "module_agreement": .2, "oos_quality": .2, "provider_coverage": .1}
    components = {key: round(bounded[key] * weight * 100, 2) for key, weight in weights.items()}
    total = round(sum(components.values()), 2)
    label = "HIGH" if total >= 75 else "MODERATE" if total >= 50 else "LOW" if total >= 25 else "VERY LOW"
    return {"score": total, "label": label, "components": components, "note": "Evidence measures support quality, not market direction."}

