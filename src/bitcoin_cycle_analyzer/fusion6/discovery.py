from __future__ import annotations
from dataclasses import dataclass
import hashlib,itertools
import numpy as np
import pandas as pd
from ..research.best_entries import causal_feature_frame,add_outcomes

FEATURE_GROUPS={"deep_drawdown":"VALUE","below_200d":"TREND","below_200w":"TREND","weekly_rsi_weak":"MOMENTUM","daily_rsi_weak":"MOMENTUM","high_value":"VALUE","capitulation":"STRESS","recovery":"STRUCTURE","ath_proximity":"LOCATION","weekly_rsi_high":"MOMENTUM","monthly_rsi_high":"MOMENTUM","volatility_expansion":"VOLATILITY","lower_high":"STRUCTURE"}
PREDECLARED=(
 ("deep_drawdown","below_200d"),("deep_drawdown","below_200w"),("deep_drawdown","weekly_rsi_weak"),("deep_drawdown","capitulation"),
 ("below_200w","weekly_rsi_weak"),("high_value","recovery"),("ath_proximity","weekly_rsi_high"),("ath_proximity","lower_high"),
 ("weekly_rsi_high","volatility_expansion"),("lower_high","volatility_expansion"),("deep_drawdown","below_200d","weekly_rsi_weak"),("deep_drawdown","below_200w","capitulation"))

def _feature_frame(frame):
    f=add_outcomes(causal_feature_frame(frame),frame);close=frame.close;weekly=close.resample("W-MON",label="right",closed="right").last().dropna();lower=(weekly.rolling(8).max()<weekly.shift(8).rolling(8).max()).reindex(close.index,method="ffill").fillna(False)
    x=pd.DataFrame(index=frame.index);x["deep_drawdown"]=f.drawdown<=-.4;x["below_200d"]=f.distance_200d<0;x["below_200w"]=f.distance_200w<0;x["weekly_rsi_weak"]=f.rsi_weekly<35;x["daily_rsi_weak"]=f.rsi_daily<30;x["high_value"]=f.value_score>=55;x["capitulation"]=f.capitulation_state=="CAPITULATION";x["recovery"]=f.recovery_state.isin(["EARLY","CONFIRMED"]);x["ath_proximity"]=close>=close.cummax()*.95;x["weekly_rsi_high"]=f.rsi_weekly>75;x["monthly_rsi_high"]=f.rsi_monthly>80;x["volatility_expansion"]=close.pct_change().rolling(14).std()>close.pct_change().rolling(365,min_periods=100).std();x["lower_high"]=lower
    return x.fillna(False),f

def _era(frame):
    vol=frame.close.pct_change().rolling(180).std();volume=frame.volume.rolling(180).median();score=(vol.rank(pct=True)+volume.rank(pct=True)).fillna(0);breaks=[frame.index[int(len(frame)*q)] for q in (.25,.5,.75)];return pd.cut(pd.Series(np.arange(len(frame)),index=frame.index),[-1,int(len(frame)*.25),int(len(frame)*.5),int(len(frame)*.75),len(frame)],labels=["STATISTICAL_ERA_1","STATISTICAL_ERA_2","STATISTICAL_ERA_3","STATISTICAL_ERA_4"]).astype(str),breaks,score

@dataclass
class HistoricalPatternDiscoveryEngine:
    minimum_sample:int=8
    def discover(self,frame:pd.DataFrame,as_of=None)->dict:
        visible=frame.loc[:as_of] if as_of is not None else frame;features,outcomes=_feature_frame(visible);eras,breaks,_=_era(visible);regimes=outcomes.regime
        targets={"STRONG_30D_RECOVERY":outcomes.return_30d>=.20,"STRONG_90D_RECOVERY":outcomes.return_90d>=.50,"STRONG_365D_RECOVERY":outcomes.return_365d>=1.0,"LOW_MAE_ENTRY":outcomes.MAE_365d>=-.10,"SELL_OFF_30D":outcomes.MAE_30d<=-.20,"SELL_OFF_90D":outcomes.MAE_90d<=-.30}
        registry=[]
        for factors in PREDECLARED:
            if len({FEATURE_GROUPS[x] for x in factors})<2:status="REDUNDANT"
            else:status=None
            mask=features[list(factors)].all(axis=1);n=int(mask.sum())
            for target_name,target in targets.items():
                valid=target.notna();base=float(target[valid].mean()) if valid.any() else np.nan;hit=float(target[mask&valid].mean()) if (mask&valid).any() else np.nan;lift=hit-base if pd.notna(hit) else np.nan
                sample=int((mask&valid).sum());failure=1-hit if pd.notna(hit) else None
                fold_results=[]
                for split in (.5,.65,.8):
                    cut=int(len(visible)*split);train=(mask.iloc[:cut]&valid.iloc[:cut]);test=(mask.iloc[cut:]&valid.iloc[cut:]);fold_results.append(None if train.sum()<self.minimum_sample or test.sum()<3 else float(target.iloc[cut:][test].mean()-target.iloc[:cut][valid.iloc[:cut]].mean()))
                survived=sum(x is not None and x>0 for x in fold_results);longevity="STABLE" if survived>=2 else "MULTI_ERA" if survived==1 else "ONE_ERA" if sample>=self.minimum_sample else "INSUFFICIENT_DATA"
                final=status or ("INSUFFICIENT_DATA" if sample<self.minimum_sample else "PROMISING" if lift>=.15 and survived>=1 else "DISCOVERED" if lift>=.08 else "WEAK" if lift>0 else "REJECTED")
                by_regime={str(r):{"n":int(m.sum()),"hit_rate":None if m.sum()==0 else round(float(target[m].mean()),4)} for r in regimes.dropna().unique() if (m:=(mask&valid&(regimes==r))).sum()>0}
                pid=hashlib.sha256(f"{factors}|{target_name}".encode()).hexdigest()[:16]
                registry.append({"pattern_id":pid,"discovered_at":visible.index[-1],"factors":list(factors),"independence_groups":sorted({FEATURE_GROUPS[x] for x in factors}),"hypothesis":f"{'+'.join(factors)} precedes {target_name}","target":target_name,"sample_size":sample,"effect_lift":None if pd.isna(lift) else round(lift,4),"median_90d":None if sample==0 else outcomes.loc[mask,"return_90d"].median(),"MAE":None if sample==0 else outcomes.loc[mask,"MAE_90d"].median(),"failure_rate":failure,"regimes":by_regime,"era_coverage":int(eras[mask].nunique()),"walk_forward":fold_results,"longevity":longevity,"status":final,"multiple_testing_family_size":len(PREDECLARED)*len(targets)})
        current=[p for p in registry if p["status"] in {"PROMISING","DISCOVERED"} and features.iloc[-1][p["factors"]].all()]
        rejected=[p for p in registry if p["status"] in {"REJECTED","REDUNDANT"}]
        reverse=self._reverse_windows(visible,features,outcomes)
        return {"status":"RESEARCH_ONLY","coverage":{"price_start":visible.index[0],"price_end":visible.index[-1],"daily_rows":len(visible),"volume_non_null":int(visible.volume.notna().sum())},"hypotheses_tested":len(registry),"patterns":registry,"active_patterns":current,"rejected_registry":rejected,"structural_breaks":breaks,"reverse_studies":reverse,"multiple_testing":{"predeclared_hypotheses":len(PREDECLARED),"target_labels":len(targets),"total_tests":len(registry),"risk":"HIGH; exploratory research","production_promotion":False},"execution":"DISABLED"}

    def _reverse_windows(self,frame,features,outcomes):
        labels={"major_rally_90d":outcomes.return_90d>=.5,"major_selloff_90d":outcomes.MAE_90d<=-.3}
        result={}
        for name,label in labels.items():
            dates=[]
            for ts in label[label.fillna(False)].index:
                if not dates or (ts-dates[-1]).days>=90:dates.append(ts)
            windows=[]
            for ts in dates:
                row={"event_time":ts}
                for offset in (90,60,30,14,7,3,1,0):
                    visible=features.loc[:ts-pd.Timedelta(days=offset)];row[f"T-{offset}"]=[] if visible.empty else [k for k,v in visible.iloc[-1].items() if bool(v)]
                windows.append(row)
            result[name]={"events":len(dates),"windows":windows}
        return result
