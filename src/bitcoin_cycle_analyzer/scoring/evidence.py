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


def factor_evidence(sample_size: int, historical_coverage: float, data_quality: float, regime_coverage: float, provider_reliability: float, ablation_value: float, oos_quality: float) -> dict:
    raw={"sample_size":min(1,sample_size/100),"historical_coverage":historical_coverage,"data_quality":data_quality,"regime_coverage":regime_coverage,"provider_reliability":provider_reliability,"ablation_value":ablation_value,"oos_quality":oos_quality}
    weights={"sample_size":.1,"historical_coverage":.15,"data_quality":.15,"regime_coverage":.1,"provider_reliability":.15,"ablation_value":.2,"oos_quality":.15}
    components={k:round(max(0,min(1,float(raw[k])))*w*100,2) for k,w in weights.items()}; score=round(sum(components.values()),2)
    status="VALIDATED" if score>=70 and ablation_value>.5 and oos_quality>.5 else "REJECTED" if sample_size>=100 and ablation_value<.4 else "RESEARCH"
    return {"score":score,"status":status,"components":components,"note":"Factor evidence is horizon-specific and not directional."}
