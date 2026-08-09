from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from ..advanced.indicators import bollinger, rsi
from ..advanced.zones import HistoricalZoneEngine
from ..external_store import ExternalMetricStore
from ..rare_signals.signal_book import build_historical_signal_book
from ..master.replay import build_master_historical_signal_book

HORIZONS = (30, 90, 180, 365, 730)
MAE_HORIZONS = (7, 30, 90, 365)
HALVINGS = pd.to_datetime(["2012-11-28", "2016-07-09", "2020-05-11", "2024-04-20"], utc=True)


def _closed_period(series: pd.Series, rule: str) -> pd.Series:
    # Labels are period closes, so forward-fill never exposes an unfinished HTF candle.
    closed = series.resample(rule, label="right", closed="right").last().dropna()
    closed = closed[closed.index <= series.index.max()]
    return closed.reindex(series.index, method="ffill")


def _bucket_bb(percent_b: pd.Series) -> pd.Series:
    return pd.cut(percent_b, [-np.inf, 0, .25, .75, 1, np.inf], labels=["BELOW_LOWER", "LOWER_QUARTILE", "MIDDLE", "UPPER_QUARTILE", "ABOVE_UPPER"]).astype("string")


def causal_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Build features using observations at or before each row only."""
    close = frame.close.astype(float); out = pd.DataFrame(index=frame.index)
    ath = close.cummax(); dd = close / ath - 1
    out["entry_price"] = close; out["drawdown"] = dd
    out["drawdown_percentile"] = dd.expanding(365).rank(pct=True) * 100
    out["drawdown_velocity_7d"] = close.pct_change(7); out["drawdown_velocity_30d"] = close.pct_change(30)
    last_ath = pd.Series(np.where(close.eq(ath), np.arange(len(close)), np.nan), index=close.index).ffill()
    out["time_under_water_days"] = np.arange(len(close)) - last_ath
    ma200 = close.rolling(200).mean(); ma200w = close.rolling(1400).mean()
    out["distance_200d"] = close / ma200 - 1; out["distance_200w"] = close / ma200w - 1
    out["rsi_daily"] = rsi(close); out["rsi_weekly"] = rsi(_closed_period(close, "W-MON")).reindex(close.index)
    out["rsi_monthly"] = rsi(_closed_period(close, "ME")).reindex(close.index); out["rsi_365d"] = rsi(close, 365)
    for label, series in (("daily", close), ("weekly", _closed_period(close, "W-MON")), ("monthly", _closed_period(close, "ME"))):
        bb = bollinger(series)
        out[f"bollinger_{label}_position"] = _bucket_bb(bb.percent_b)
        out[f"bollinger_{label}_bandwidth"] = bb.bandwidth
    out["daily_structure"] = np.where(close > ma200, "BULL", "BEAR")
    out["weekly_structure"] = np.where(close > ma200w, "BULL", "BEAR")
    recovery = close / close.rolling(90, min_periods=30).min() - 1
    out["recovery_state"] = np.select([recovery >= .30, recovery >= .15, dd <= -.55], ["CONFIRMED", "EARLY", "CAPITULATION"], default="NONE")
    out["capitulation_state"] = np.where((close.pct_change(7) <= -.25) | ((dd <= -.55) & (close.pct_change(30) <= -.25)), "CAPITULATION", np.where((dd <= -.40) & (close.pct_change(30) < 0), "STRESS", "NONE"))
    out["regime"] = np.select([(dd <= -.4) & (recovery < .15), recovery >= .15, close > ma200], ["BEAR", "RECOVERY", "BULL"], default="ACCUMULATION")
    out["value_score"] = np.clip((-dd * 100) + np.clip(-out.distance_200d * 40, -20, 30), 0, 100)
    out["value_state"] = pd.cut(out.value_score, [-1, 35, 55, 75, 101], labels=["LOW", "FAIR", "HIGH", "EXTREME"]).astype("string")
    out["historical_value_percentile"] = out.value_score.expanding(365).rank(pct=True) * 100
    out["month"] = out.index.month; out["weekday"] = out.index.weekday
    out["black_friday_window"] = (out.index.month == 11) & (out.index.day >= 20)
    out["christmas_new_year_window"] = ((out.index.month == 12) & (out.index.day >= 20)) | ((out.index.month == 1) & (out.index.day <= 7))
    out["days_from_halving"] = [int((date - HALVINGS[np.argmin(abs(HALVINGS - date))]).days) for date in out.index]
    return out


def add_outcomes(features: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    out = features.copy(); close = frame.close; low = frame.low; high = frame.high
    for horizon in HORIZONS:
        out[f"return_{horizon}d"] = close.shift(-horizon) / close - 1
    for horizon in MAE_HORIZONS:
        out[f"MAE_{horizon}d"] = low.shift(-1)[::-1].rolling(horizon, min_periods=horizon).min()[::-1] / close - 1
    out["MFE_365d"] = high.shift(-1)[::-1].rolling(365, min_periods=365).max()[::-1] / close - 1
    local_low = low.shift(-90)[::-1].rolling(181, min_periods=181).min()[::-1]
    out["distance_from_local_low"] = close / local_low - 1
    # Outcome ranks are labels only and never fed back into causal features.
    r365 = out.return_365d.rank(pct=True); r730 = out.return_730d.rank(pct=True)
    out["long_term_score"] = 100 * (.55 * r365 + .45 * r730.fillna(r365))
    out["risk_adjusted_score"] = out.return_365d / out.MAE_365d.abs().clip(lower=.05)
    out["category_best_long_term"] = out.long_term_score >= out.long_term_score.quantile(.90)
    out["category_risk_adjusted"] = out.risk_adjusted_score >= out.risk_adjusted_score.quantile(.90)
    out["category_near_cycle_bottom"] = (out.distance_from_local_low <= .12) & (out.return_365d > 0)
    out["category_early_recovery"] = (out.recovery_state == "EARLY") & (out.return_365d > out.return_365d.median())
    out["category_capitulation"] = (out.capitulation_state == "CAPITULATION") & (out.return_365d > 0)
    return out


def cluster_entry_episodes(labelled: pd.DataFrame, min_gap_days: int = 90) -> pd.DataFrame:
    eligible = labelled[labelled[["category_best_long_term", "category_risk_adjusted", "category_near_cycle_bottom", "category_early_recovery", "category_capitulation"]].any(axis=1) & labelled.return_365d.notna()].copy()
    if eligible.empty: return eligible.assign(episode_id=pd.Series(dtype="int64"))
    groups=[]; current=[]; prior=None
    for date in eligible.index:
        if prior is not None and (date-prior).days >= min_gap_days:
            groups.append(current); current=[]
        current.append(date); prior=date
    groups.append(current); rows=[]
    for eid, dates in enumerate(groups, 1):
        group=eligible.loc[dates]; best=group.sort_values(["long_term_score", "risk_adjusted_score"], ascending=False).iloc[0].copy()
        best["episode_id"]=eid; best["start"]=dates[0]; best["end"]=dates[-1]; best["best_entry_window"]=f"{dates[0].date()}..{dates[-1].date()}"; best.name=group.sort_values(["long_term_score", "risk_adjusted_score"], ascending=False).index[0]; rows.append(best)
    return pd.DataFrame(rows).sort_values("long_term_score", ascending=False)


def _asof_metric(store: ExternalMetricStore, metric: str, dates: Iterable[pd.Timestamp]) -> list[float]:
    data=store.load(metric)
    if data.empty:return [np.nan for _ in dates]
    data=data.sort_values("available_at")
    return [np.nan if (visible:=data[data.available_at<=date]).empty else float(visible.iloc[-1].value) for date in dates]


def _cycle(date: pd.Timestamp) -> str:
    prior=HALVINGS[HALVINGS<=date]
    return "PRE_FIRST_HALVING" if prior.empty else f"POST_{prior[-1].year}_HALVING"


def _recognised(date, book, column):
    if book.empty:return False
    dates=pd.to_datetime(book[column], utc=True);return bool(((dates-date).abs()<=pd.Timedelta(days=30)).any())


def _zone_features(frame, date):
    zones=HistoricalZoneEngine().analyze(frame, date); price=float(frame.loc[date,"close"]); support=[z for z in zones if z["zone_type"] in {"MAJOR_SUPPORT","HISTORICAL_SUPPORT","PREVIOUS_ATH"} and z["upper_bound"]<=price*1.05]
    if not support:return {"major_support":False,"zone_strength":np.nan,"zone_distance":np.nan,"zone_flip":False,"support_exhaustion":np.nan,"fib_confluence":False}
    z=min(support,key=lambda x:abs(x["distance_percent"]));return {"major_support":z["confidence"] in {"MODERATE","HIGH"},"zone_strength":z["strength"],"zone_distance":abs(z["distance_percent"]),"zone_flip":bool(z["zone_flip"]),"support_exhaustion":z["support_exhaustion"],"fib_confluence":bool(z["fib_confluence"])}


def _archetype(row):
    if row.capitulation_state=="CAPITULATION":return "DEEP_CAPITULATION"
    if row.recovery_state in {"EARLY","CONFIRMED"}:return "EARLY_RECOVERY"
    if bool(row.major_support):return "HISTORICAL_SUPPORT_RETEST"
    return "DEEP_VALUE" if row.drawdown<=-.4 else "BULL_MARKET_CORRECTION"


FACTOR_DEFS = {
 "deep_drawdown": lambda x:x.drawdown<=-.4, "extreme_drawdown":lambda x:x.drawdown<=-.7,
 "weekly_rsi_extreme":lambda x:x.rsi_weekly<35, "daily_rsi_extreme":lambda x:x.rsi_daily<30,
 "below_weekly_bollinger":lambda x:x.bollinger_weekly_position=="BELOW_LOWER", "high_value":lambda x:x.value_score>=55,
 "major_support":lambda x:x.major_support==True, "fib_confluence":lambda x:x.fib_confluence==True,
 "capitulation":lambda x:x.capitulation_state=="CAPITULATION", "recovery_visible":lambda x:x.recovery_state in {"EARLY","CONFIRMED"},
 "below_200d":lambda x:x.distance_200d<0, "below_200w":lambda x:x.distance_200w<0,
 "negative_funding":lambda x:pd.notna(x.funding) and x.funding<0, "oi_available":lambda x:pd.notna(x.open_interest),
 "onchain_mvrv_below_1":lambda x:pd.notna(x.mvrv) and x.mvrv<1,
 "holiday_window":lambda x:bool(x.black_friday_window or x.christmas_new_year_window),
}


def _factor_matrix(samples: pd.DataFrame) -> pd.DataFrame:
    records=[]
    for name,fn in FACTOR_DEFS.items():
        top=samples[samples.sample_group=="TOP_ENTRY"]; control=samples[samples.sample_group=="CONTROL"]
        top_values=top.apply(fn,axis=1).fillna(False).astype(bool); ctl_values=control.apply(fn,axis=1).fillna(False).astype(bool)
        tf=float(top_values.mean()) if len(top) else np.nan; cf=float(ctl_values.mean()) if len(control) else np.nan
        lift=tf-cf if pd.notna(tf) and pd.notna(cf) else np.nan
        timing="LATE" if name=="recovery_visible" else "MID" if name in {"fib_confluence","major_support","below_weekly_bollinger"} else "EARLY"
        available = int(top.funding.notna().sum()) if name=="negative_funding" else int(top.open_interest.notna().sum()) if name=="oi_available" else len(top)
        status="INSUFFICIENT_DATA" if name in {"negative_funding","oi_available"} and available<5 else "PROMISING" if pd.notna(lift) and lift>=.15 else "LATE_CONFIRMATION" if timing=="LATE" else "CONTEXT_ONLY" if pd.notna(lift) and lift>0 else "NO_ROBUST_VALUE"
        present=samples.apply(fn,axis=1).fillna(False).astype(bool)
        records.append({"factor":name,"role":"TIMING" if timing!="EARLY" else "VALUE","top_entry_frequency":tf,"control_frequency":cf,"top_entry_lift":lift,"median_365d_when_present":samples[present].return_365d.median(),"MAE_365d_when_present":samples[present].MAE_365d.median(),"timing":timing,"sample_size":int(present.sum()),"confidence":"LOW" if len(top)<10 else "MODERATE","status":status})
    return pd.DataFrame(records).sort_values(["top_entry_lift","sample_size"],ascending=False)


def run_best_entry_study(frame: pd.DataFrame, external_store: ExternalMetricStore, four_hour: pd.DataFrame | None = None) -> tuple[pd.DataFrame,pd.DataFrame,dict]:
    labelled=add_outcomes(causal_feature_frame(frame),frame); episodes=cluster_entry_episodes(labelled)
    episodes=episodes.head(30).copy(); episodes.insert(0,"rank",range(1,len(episodes)+1)); episodes.insert(2,"date",episodes.index)
    for date in episodes.date:
        pass
    zones=pd.DataFrame([_zone_features(frame,d) for d in episodes.date],index=episodes.index); episodes=pd.concat([episodes,zones],axis=1)
    for metric,column in (("mvrv","mvrv"),("exchange_balance_btc","exchange_balance"),("exchange_inflows_usd","exchange_inflows"),("exchange_outflows_usd","exchange_outflows"),("hash_rate","hash_rate"),("active_addresses","network_activity"),("funding_rate_8h","funding"),("open_interest_usd","open_interest")):
        episodes[column]=_asof_metric(external_store,metric,episodes.date)
    if four_hour is not None and not four_hour.empty:
        h4rsi=rsi(four_hour.close);episodes["rsi_4h"]=[float(h4rsi.loc[:d].iloc[-1]) if not h4rsi.loc[:d].dropna().empty else np.nan for d in episodes.date]
        episodes["h4_structure"]=["BULL" if four_hour.loc[:d].close.iloc[-1]>four_hour.loc[:d].close.rolling(200).mean().iloc[-1] else "BEAR" for d in episodes.date]
    else: episodes["rsi_4h"]=np.nan;episodes["h4_structure"]="UNAVAILABLE"
    episodes["holder_state"]="UNAVAILABLE";episodes["macro_state"]="UNAVAILABLE";episodes["news_state"]="UNAVAILABLE"
    source=build_historical_signal_book(frame); master,_=build_master_historical_signal_book(frame)
    episodes["recognized_2_3"]=episodes.date.map(lambda d:_recognised(d,source[source.signal_type.isin(["BUY","ACCUMULATE"])],"date"))
    episodes["recognized_2_5"]=episodes.date.map(lambda d:_recognised(d,source[source.signal_type=="BUY"],"date")); episodes["recognized_master"]=episodes.date.map(lambda d:_recognised(d,master[master.master_signal=="BUY"],"date"))
    episodes["candidate_completion"]=[max([int(r.confluence)*25 for _,r in source[(pd.to_datetime(source.date,utc=True)-d).abs()<=pd.Timedelta(days=30)].iterrows() if r.signal_type in {"BUY","ACCUMULATE"}] or [0]) for d in episodes.date]
    episodes["master_decision"] = np.where(episodes.recognized_master,"BUY_RESEARCH_PROXY","NO_BUY_RESEARCH_PROXY")
    episodes["cycle"]=episodes.date.map(_cycle); episodes["entry_archetype"]=episodes.apply(_archetype,axis=1)
    episodes["days_to_local_low"]=[int((frame.loc[d-pd.Timedelta(days=90):d+pd.Timedelta(days=90)].low.idxmin()-d).days) for d in episodes.date]
    episodes["days_to_break_even"]=[next((i for i,v in enumerate(frame.loc[d:].close.iloc[1:366],1) if v>=p),np.nan) for d,p in zip(episodes.date,episodes.entry_price)]
    episodes["days_to_new_high"]=[next((i for i,v in enumerate(frame.loc[d:].close.iloc[1:731],1) if v>=frame.loc[:d].close.max()),np.nan) for d in episodes.date]
    top=episodes.copy(); top["sample_group"]="TOP_ENTRY"
    excluded=pd.DatetimeIndex(episodes.date)
    neutral=labelled[labelled.return_365d.notna() & (labelled.drawdown.between(-.25,-.05))].iloc[::90].head(max(10,len(top))).copy(); neutral["date"]=neutral.index; neutral["sample_group"]="CONTROL"
    neutral_z=pd.DataFrame([_zone_features(frame,d) for d in neutral.date],index=neutral.index);neutral=pd.concat([neutral,neutral_z],axis=1)
    for col in ("mvrv","funding","open_interest"): neutral[col]=np.nan
    samples=pd.concat([top,neutral],sort=False); matrix=_factor_matrix(samples)
    combos=[]
    for name, factors in (("Deep Drawdown + Major Support",("deep_drawdown","major_support")),("Deep Drawdown + Weekly RSI Extreme",("deep_drawdown","weekly_rsi_extreme")),("Major Support + Weekly RSI Extreme",("major_support","weekly_rsi_extreme")),("High Value + Recovery",("high_value","recovery_visible")),("Capitulation + Recovery",("capitulation","recovery_visible")),("Support + Fib Confluence",("major_support","fib_confluence")),("Deep Drawdown + MVRV<1",("deep_drawdown","onchain_mvrv_below_1"))):
        mask=pd.Series(True,index=samples.index)
        for factor in factors:mask &= samples.apply(FACTOR_DEFS[factor],axis=1).fillna(False).astype(bool)
        group=samples[mask];combos.append({"combination":name,"n":len(group),"median_365d":group.return_365d.median(),"median_MAE_365d":group.MAE_365d.median(),"top_share":float((group.sample_group=="TOP_ENTRY").mean()) if len(group) else np.nan})
    failed=labelled[(labelled.value_score>=55)&(labelled.return_365d<=0)].iloc[::60]
    exits=labelled[labelled.return_90d<=labelled.return_90d.quantile(.05)].sort_values("return_90d").iloc[::30].head(20)
    meta={"status":"RESEARCH_ONLY","method":"fixed objective labels; 90-day episode separation; no parameter search","multiple_testing":{"factors":len(FACTOR_DEFS),"predeclared_combinations":len(combos)},"combinations":combos,"failed_buy_candidates":len(failed),"exit_reduce_episodes":len(exits),"sell_conclusion":"Research-only downside episodes; rejected SELL proxy remains rejected.","execution":"DISABLED"}
    return episodes.reset_index(drop=True),matrix.reset_index(drop=True),meta

def staged_entry_research(frame:pd.DataFrame,episodes:pd.DataFrame)->pd.DataFrame:
    """Three fixed, outcome-only accumulation variants; never used by live decisions."""
    rows=[]
    for episode in episodes.itertuples():
        date=pd.Timestamp(episode.date);date=date.tz_localize("UTC") if date.tzinfo is None else date;window=frame.loc[date:date+pd.Timedelta(days=90)];end=frame.loc[:date+pd.Timedelta(days=365)]
        if window.empty:continue
        p0=float(frame.loc[date,"close"]);p30=float(window.iloc[:31].low.min());p90=float(window.low.min())
        recovery=window[window.close>=window.low.cummin()*1.15];recovery_price=float(recovery.close.iloc[0]) if not recovery.empty else np.nan;recovery_date=recovery.index[0] if not recovery.empty else None
        variants=(("single_entry",p0,0),("2_stage",(p0+p90)/2,50),("3_stage",(p0+p30+p90)/3,67),("recovery_confirmed",recovery_price,None))
        for name,avg,after in variants:
            future=frame.loc[date:date+pd.Timedelta(days=365)] if name!="recovery_confirmed" or recovery_date is None else frame.loc[recovery_date:recovery_date+pd.Timedelta(days=365)]
            rows.append({"episode_id":episode.episode_id,"date":date,"variant":name,"average_entry":avg,"delay_days":None if name!="recovery_confirmed" or recovery_date is None else (recovery_date-date).days,"MAE":np.nan if pd.isna(avg) or future.empty else float(future.low.min()/avg-1),"eventual_return_365d":np.nan if pd.isna(avg) or future.empty else float(future.close.iloc[-1]/avg-1),"capital_deployed_before_bottom_pct":100 if name=="single_entry" else 50 if name=="2_stage" else 33 if name=="3_stage" else 0,"capital_deployed_after_bottom_pct":0 if name=="single_entry" else 50 if name=="2_stage" else 67 if name=="3_stage" else 100,"status":"RESEARCH_ONLY"})
    return pd.DataFrame(rows)
