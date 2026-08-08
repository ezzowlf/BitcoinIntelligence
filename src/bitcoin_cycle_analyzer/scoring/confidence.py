def normalize_confidences(values: dict[str, float]) -> dict[str, float]:
    positive = {key: max(0, float(value)) for key, value in values.items()}
    total = sum(positive.values())
    return {key: (round(value / total * 100, 1) if total else 0.0) for key, value in positive.items()}
