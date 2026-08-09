import numpy as np
import pandas as pd
from pathlib import Path

from bitcoin_cycle_analyzer.research.best_entries import add_outcomes, causal_feature_frame, cluster_entry_episodes


def frame(n=1800):
    idx=pd.date_range("2015-01-01",periods=n,tz="UTC")
    close=pd.Series(100*np.exp(np.linspace(0,2,n)+.25*np.sin(np.arange(n)/80)),index=idx)
    return pd.DataFrame({"open":close,"high":close*1.01,"low":close*.99,"close":close,"volume":1000},index=idx)


def test_causal_features_ignore_future_mutation():
    data=frame();cutoff=data.index[1000];a=causal_feature_frame(data.loc[:cutoff]).iloc[-1]
    changed=data.copy();changed.loc[changed.index>cutoff,["open","high","low","close"]]*=100
    b=causal_feature_frame(changed).loc[cutoff]
    pd.testing.assert_series_equal(a,b,check_names=False)


def test_future_is_used_only_for_outcome_labels():
    data=frame();features=causal_feature_frame(data);labelled=add_outcomes(features,data)
    assert labelled.loc[data.index[500],"return_365d"]==data.close.iloc[865]/data.close.iloc[500]-1
    assert "return_365d" not in features


def test_episode_clustering_is_independent_and_positive():
    labelled=add_outcomes(causal_feature_frame(frame()),frame());episodes=cluster_entry_episodes(labelled,90)
    dates=pd.DatetimeIndex(episodes.index).sort_values()
    assert all((dates[1:]-dates[:-1]).days>=90)
    assert (episodes.return_365d>0).all()


def test_research_does_not_change_frozen_or_execution():
    root=Path(__file__).parents[1]
    assert '"execution": "DISABLED"' in (root/"frozen"/"master_3_0_frozen.json").read_text(encoding="utf-8")
