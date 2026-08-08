from __future__ import annotations
import math
import pandas as pd
from ..indicators import add_indicators

HALVINGS = (
    pd.Timestamp("2012-11-28", tz="UTC"),
    pd.Timestamp("2016-07-09", tz="UTC"),
    pd.Timestamp("2020-05-11", tz="UTC"),
    pd.Timestamp("2024-04-20", tz="UTC"),
)


def halving_context(as_of: pd.Timestamp) -> dict:
    as_of = pd.Timestamp(as_of)
    if as_of.tzinfo is None:
        as_of = as_of.tz_localize("UTC")
    known = [date for date in HALVINGS if date <= as_of]
    last = known[-1] if known else None
    if last is None:
        return {"last_halving": None, "days_since": None, "months_since": None, "cycle_number": 0}
    days = (as_of - last).days
    return {"last_halving": last, "days_since": days, "months_since": round(days / 30.4375, 2), "cycle_number": len(known)}


def ath_context(frame: pd.DataFrame) -> dict:
    close = frame.close
    ath = float(close.cummax().iloc[-1])
    ath_date = close[close == ath].index[0]
    drawdown = float(close.iloc[-1] / ath - 1)
    underwater = close < close.cummax()
    duration = 0
    for value in underwater.iloc[::-1]:
        if not value:
            break
        duration += 1
    return {"ath": ath, "ath_date": ath_date, "drawdown": drawdown, "days_since_ath": int((frame.index[-1] - ath_date).days), "drawdown_duration_bars": duration}


def _soft_regimes(row: pd.Series) -> dict[str, float]:
    dd = float(row.drawdown)
    r30 = float(row.return_30) if pd.notna(row.return_30) else 0
    above_200 = pd.notna(row.ema_200) and row.close > row.ema_200
    rsi = float(row.rsi_14) if pd.notna(row.rsi_14) else 50
    raw = {
        "ACCUMULATION": max(0, -dd - .35) * 2 + max(0, 45 - rsi) / 50,
        "EARLY_BULL": (1 if above_200 else 0) * max(0, .25 - r30) + max(0, r30),
        "BULL_EXPANSION": (1 if above_200 else 0) * max(0, r30) * 3 + max(0, rsi - 55) / 40,
        "LATE_BULL": max(0, rsi - 70) / 20 + max(0, r30 - .2) * 2,
        "DISTRIBUTION": max(0, rsi - 60) / 40 + max(0, -r30),
        "EARLY_BEAR": (0 if above_200 else 1) * max(0, -r30) * 3 + max(0, -dd - .15),
        "BEAR": (0 if above_200 else 1) * max(0, -dd - .25) * 2 + max(0, 45 - rsi) / 50,
        "CAPITULATION": max(0, -dd - .55) * 3 + max(0, 30 - rsi) / 20,
        "RECOVERY": max(0, r30) * 2 + (1 if above_200 and dd < -.1 else 0) * .5,
        "TRANSITION": .25 + (0 if abs(r30) > .15 else .4),
    }
    exp = {key: math.exp(min(value, 8)) for key, value in raw.items()}
    total = sum(exp.values())
    return {key: round(value / total * 100, 1) for key, value in exp.items()}


def analyze_cycle(frame: pd.DataFrame, as_of=None) -> dict:
    visible = frame.loc[:as_of].copy() if as_of is not None else frame.copy()
    if visible.empty:
        raise ValueError("cycle analysis requires data")
    enriched = add_indicators(visible)
    confidence = _soft_regimes(enriched.iloc[-1])
    ranked = sorted(confidence.items(), key=lambda item: item[1], reverse=True)
    return {"as_of": visible.index[-1], "halving": halving_context(visible.index[-1]), "ath": ath_context(visible), "primary_regime": ranked[0][0], "primary_confidence": ranked[0][1], "alternatives": [{"regime": name, "confidence": score} for name, score in ranked[1:4]], "all_regimes": confidence, "confidence_note": "rule-based relative confidence, not calibrated probability"}


def market_regime_series(frame: pd.DataFrame) -> pd.Series:
    enriched = add_indicators(frame)
    values = []
    for _, row in enriched.iterrows():
        ranked = sorted(_soft_regimes(row).items(), key=lambda item: item[1], reverse=True)
        values.append(ranked[0][0])
    return pd.Series(values, index=frame.index, name="market_regime")
