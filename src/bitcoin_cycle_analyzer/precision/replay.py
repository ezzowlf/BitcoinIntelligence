from __future__ import annotations
import pandas as pd


def replay_frame(frame:pd.DataFrame,as_of):
    cutoff=pd.Timestamp(as_of); result=frame.loc[:cutoff].copy()
    if result.empty: raise ValueError("no data available as of replay date")
    return result


def navigate(date,action):
    offsets={"previous_day":-1,"next_day":1,"plus_7_days":7,"plus_30_days":30}
    if action not in offsets: raise ValueError("unsupported replay action")
    return pd.Timestamp(date)+pd.Timedelta(days=offsets[action])
