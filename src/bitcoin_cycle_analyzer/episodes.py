from __future__ import annotations
import pandas as pd


def cluster_episodes(signals: pd.DataFrame, min_gap_days: int = 60, hysteresis_exit: float = 10.0) -> pd.DataFrame:
    if signals.empty: return signals.assign(episode_id=pd.Series(dtype=int))
    ordered = signals.copy()
    if "timestamp" in ordered.columns:
        ordered = ordered.set_index(pd.to_datetime(ordered.pop("timestamp"), utc=True))
    ordered = ordered.sort_index(); episode_ids=[]; episode=0; last_date=None; last_regime=None
    for date, row in ordered.iterrows():
        regime = row.get("market_phase")
        new = last_date is None or (date-last_date).days >= min_gap_days or (last_regime is not None and regime != last_regime)
        if new: episode += 1
        episode_ids.append(episode); last_date=date; last_regime=regime
    ordered["episode_id"] = episode_ids
    return ordered


def episode_summary(signals: pd.DataFrame, **kwargs) -> dict:
    clustered = cluster_episodes(signals, **kwargs)
    return {"threshold_crossings": len(signals), "independent_episodes": 0 if clustered.empty else int(clustered.episode_id.nunique()), "episodes": [] if clustered.empty else [{"episode_id":int(eid),"start":str(group.index.min()),"end":str(group.index.max()),"crossings":len(group)} for eid,group in clustered.groupby("episode_id")]}
