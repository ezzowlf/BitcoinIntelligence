from __future__ import annotations
from pathlib import Path
import pandas as pd
from .fred_provider import FredVintageProvider, FRED_SERIES
from .store import MacroReleaseStore
from .engine import MACRO_METRICS


def load_macro_series(api_key: str | None, db_path: Path, as_of) -> dict[str, pd.DataFrame]:
    """Fetch (if a FRED_API_KEY is configured) and read cached macro releases,
    returning the {metric: DataFrame} shape analyze_macro() expects.

    Provider/network errors are caught per-series so one failing series never
    breaks the others or crashes the app - whatever was already cached for
    that series from a previous successful run is used instead. A metric with
    no cache and no successful fetch is simply absent from the result;
    analyze_macro() already treats a missing metric as UNAVAILABLE, so no
    availability is faked here.
    """
    store = MacroReleaseStore(db_path)
    if api_key:
        provider = FredVintageProvider(api_key)
        for metric, series_id in FRED_SERIES.items():
            if metric not in MACRO_METRICS:
                continue
            try:
                store.upsert(provider.fetch_macro_initial(series_id, metric))
            except Exception:
                pass
    series = {}
    for metric in MACRO_METRICS:
        frame = store.as_of(metric, as_of)
        if not frame.empty:
            series[metric] = frame
    return series
