def news_risk(events) -> dict:
    if not events:
        return {"status": "UNAVAILABLE", "risk": None}
    weighted = sum(event.severity * event.confidence for event in events) / len(events)
    return {"status": "AVAILABLE", "risk": "HIGH" if weighted >= .7 else "MEDIUM" if weighted >= .4 else "LOW", "score": weighted * 100, "events": len(events)}

