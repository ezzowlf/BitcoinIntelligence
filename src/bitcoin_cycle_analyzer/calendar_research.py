from __future__ import annotations

import pandas as pd

from .seasonality.event_windows import event_window_statistics, holiday_dates


def complete_calendar_study(frame: pd.DataFrame, regimes: pd.Series | None = None) -> dict:
    returns = frame.close.pct_change()
    monthly = []
    for month, group in returns.groupby(returns.index.month):
        monthly.append({"month": int(month), "sample_size": int(group.notna().sum()), "median": float(group.median()), "win_rate": float((group > 0).mean())})
    flags = {
        "month_start": frame.index.is_month_start, "month_end": frame.index.is_month_end,
        "quarter_start": frame.index.is_quarter_start, "quarter_end": frame.index.is_quarter_end,
        "year_start": frame.index.is_year_start, "year_end": frame.index.is_year_end,
    }
    boundaries = {name: {"sample_size": int(mask.sum()), "median": float(returns[mask].median()), "win_rate": float((returns[mask] > 0).mean())} for name, mask in flags.items()}
    holidays = {name: event_window_statistics(frame, name, before=7, after=7, regimes=regimes) for name in holiday_dates(frame.index.max().year)}
    return {"months": monthly, "boundaries": boundaries, "holidays": holidays, "coverage": {"from": frame.index.min().isoformat(), "to": frame.index.max().isoformat()}}


def black_friday_finding(frame: pd.DataFrame, regimes: pd.Series | None = None) -> dict:
    study = event_window_statistics(frame, "black_friday", before=7, after=7, regimes=regimes)
    obs = study["observations"]
    returns = pd.Series([x["return"] for x in obs], dtype=float)
    conclusion = "INSUFFICIENT_SAMPLE" if len(returns) < 8 else "SUPPORTED" if float(returns.median()) < 0 and float((returns < 0).mean()) >= .6 else "NOT_SUPPORTED"
    return {**study, "median": None if returns.empty else float(returns.median()), "win_rate": None if returns.empty else float((returns > 0).mean()), "outliers": [] if returns.empty else [obs[i] for i in range(len(obs)) if abs(returns.iloc[i]-returns.median()) > 2*returns.std()], "conclusion": conclusion, "interpretation": "A calendar association is research context, never an isolated signal."}
