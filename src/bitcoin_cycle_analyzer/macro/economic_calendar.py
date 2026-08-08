from __future__ import annotations
import pandas as pd


def released_events(events: pd.DataFrame, as_of) -> pd.DataFrame:
    if "release_timestamp" not in events:
        raise ValueError("release_timestamp required")
    timestamps = pd.to_datetime(events.release_timestamp, utc=True)
    return events[timestamps <= pd.Timestamp(as_of)].copy()

