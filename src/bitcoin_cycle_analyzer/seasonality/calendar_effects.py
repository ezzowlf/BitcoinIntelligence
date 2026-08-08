from __future__ import annotations
import pandas as pd


def turn_of_month_statistics(frame: pd.DataFrame, as_of=None, days: int = 5) -> dict:
    visible = frame.loc[:as_of] if as_of is not None else frame
    daily = visible.close.pct_change()
    last = daily.index.days_in_month - daily.index.day < days
    first = daily.index.day <= days
    def summary(values):
        values = values.dropna()
        return {"samples": len(values), "mean": float(values.mean()), "median": float(values.median()), "win_rate": float((values > 0).mean())}
    return {"last_days": summary(daily[last]), "first_days": summary(daily[first])}


def quarter_statistics(frame: pd.DataFrame, as_of=None) -> dict:
    visible = frame.loc[:as_of] if as_of is not None else frame
    quarterly = visible.close.resample("QE").last().pct_change().dropna()
    return {f"Q{q}": {"samples": len(values), "median": float(values.median()), "mean": float(values.mean()), "win_rate": float((values > 0).mean())} for q, values in quarterly.groupby(quarterly.index.quarter)}
