from __future__ import annotations


def entry_timing_state(structure: str, confirmation: str, rsi: float | None, derivatives: dict | None = None, reclaim: bool | None = None) -> dict:
    points = 0
    points += 35 if structure == "bullish" else 15 if structure == "corrective" else 0
    points += 30 if confirmation == "HIGH" else 15 if confirmation == "MEDIUM" else 0
    points += 15 if rsi is not None and 40 <= rsi <= 65 else 5 if rsi is not None and rsi < 40 else 0
    if reclaim is True: points += 20
    if derivatives and derivatives.get("timing_adjustment") is not None: points += derivatives["timing_adjustment"]
    points = max(0,min(100,points))
    state = "EXTENDED" if rsi is not None and rsi > 75 else "CONFIRMED" if points>=75 else "CONFIRMING" if points>=55 else "EARLY" if points>=35 else "WAIT"
    return {"state":state,"score":points,"execution":"DISABLED"}
