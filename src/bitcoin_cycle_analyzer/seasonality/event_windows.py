from __future__ import annotations
from datetime import date, timedelta
import pandas as pd
from .statistics import _summary


def _thanksgiving(year: int) -> date:
    current = date(year, 11, 1)
    first_thursday = current + timedelta(days=(3 - current.weekday()) % 7)
    return first_thursday + timedelta(weeks=3)


def holiday_dates(year: int) -> dict[str, date]:
    thanksgiving = _thanksgiving(year)
    return {"thanksgiving": thanksgiving, "black_friday": thanksgiving + timedelta(days=1), "christmas": date(year, 12, 25), "new_year": date(year, 1, 1)}


def event_window_statistics(frame: pd.DataFrame, event: str, before: int = 14, after: int = 14, as_of=None, regimes: pd.Series | None = None) -> dict:
    visible = frame.loc[:as_of] if as_of is not None else frame
    cutoff = visible.index.max()
    records = []
    for year in range(visible.index.min().year, cutoff.year + 1):
        event_date = pd.Timestamp(holiday_dates(year)[event], tz="UTC")
        start, end = event_date - pd.Timedelta(days=before), event_date + pd.Timedelta(days=after)
        if start < visible.index.min() or end > cutoff:
            continue
        window = visible.loc[start:end]
        if window.empty:
            continue
        entry, exit_price = float(window.close.iloc[0]), float(window.close.iloc[-1])
        records.append({"year": year, "event_date": event_date, "return": exit_price / entry - 1, "max_drawdown": float(window.low.min() / entry - 1), "regime": None if regimes is None else regimes.reindex([event_date], method="ffill").iloc[0]})
    samples = pd.DataFrame(records)
    result = _summary(samples["return"] if not samples.empty else pd.Series(dtype=float), samples["max_drawdown"] if not samples.empty else None)
    result["event"] = event
    result["window"] = {"before_days": before, "after_days": after}
    result["positive"] = 0 if samples.empty else int((samples["return"] > 0).sum())
    result["observations"] = records
    if regimes is not None and not samples.empty:
        result["by_regime"] = {str(name): _summary(group["return"], group["max_drawdown"]) for name, group in samples.dropna(subset=["regime"]).groupby("regime")}
    return result

