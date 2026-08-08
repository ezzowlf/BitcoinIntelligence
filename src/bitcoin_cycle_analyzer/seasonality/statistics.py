from __future__ import annotations
import numpy as np
import pandas as pd


def _summary(values: pd.Series, drawdowns: pd.Series | None = None) -> dict:
    values = values.dropna()
    return {"samples": len(values), "mean_return": None if values.empty else float(values.mean()), "median_return": None if values.empty else float(values.median()), "win_rate": None if values.empty else float((values > 0).mean()), "volatility": None if values.empty else float(values.std()), "max_drawdown": None if drawdowns is None or drawdowns.dropna().empty else float(drawdowns.min())}


def monthly_statistics(frame: pd.DataFrame, as_of=None, regimes: pd.Series | None = None) -> dict:
    visible = frame.loc[:as_of] if as_of is not None else frame
    monthly = visible.resample("ME", label="right", closed="right").agg({"open":"first", "high":"max", "low":"min", "close":"last"}).dropna()
    monthly = monthly[monthly.index <= visible.index.max()]
    monthly["return"] = monthly.close / monthly.open - 1
    monthly["drawdown"] = monthly.low / monthly.open - 1
    result = {str(month): _summary(group["return"], group["drawdown"]) for month, group in monthly.groupby(monthly.index.month)}
    if regimes is not None:
        aligned = regimes.reindex(monthly.index, method="ffill")
        result["by_regime"] = {}
        for regime in aligned.dropna().unique():
            subset = monthly[aligned == regime]
            result["by_regime"][str(regime)] = {str(month): _summary(group["return"], group["drawdown"]) for month, group in subset.groupby(subset.index.month)}
    return result


def weekday_statistics(frame: pd.DataFrame, as_of=None) -> dict:
    visible = frame.loc[:as_of] if as_of is not None else frame
    returns = visible.close.pct_change()
    names = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
    return {names[day]: _summary(returns[returns.index.dayofweek == day]) for day in range(7)}


def monthly_heatmap(frame: pd.DataFrame, as_of=None) -> pd.DataFrame:
    visible = frame.loc[:as_of] if as_of is not None else frame
    monthly = visible.close.resample("ME").last().pct_change()
    monthly = monthly[monthly.index <= visible.index.max()]
    table = pd.DataFrame({"year": monthly.index.year, "month": monthly.index.month, "return": monthly.values})
    return table.pivot(index="year", columns="month", values="return")

