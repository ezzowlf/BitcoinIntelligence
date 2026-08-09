from __future__ import annotations

import hashlib,json
from dataclasses import asdict,dataclass
from pathlib import Path
import numpy as np
import pandas as pd

REFERENCE_VERSION="BEST_ENTRY_REFERENCE_SET_V1"
FACTOR_GROUPS={
 "VALUE":("DEEP_DRAWDOWN","EXTREME_DRAWDOWN","HIGH_VALUE","BELOW_200D","BELOW_200W"),
 "LOCATION":("MAJOR_HISTORICAL_SUPPORT",),
 "MOMENTUM_EXTREME":("DAILY_RSI_WEAK","WEEKLY_RSI_WEAK"),
 "STRESS":("CAPITULATION_STRESS",),
}
PROVENANCE={
 "DEEP_DRAWDOWN":"existing DrawdownCycleEngine threshold <= -40%; historically tested",
 "EXTREME_DRAWDOWN":"existing DrawdownCycleEngine threshold <= -70%; historically tested",
 "MAJOR_HISTORICAL_SUPPORT":"existing PIT HistoricalZoneEngine support; historically tested; not duplicated with Fib",
 "HIGH_VALUE":"existing Precision value state HIGH_VALUE or EXTREME_VALUE",
 "BELOW_200D":"research feature: closed daily price below trailing 200D mean",
 "BELOW_200W":"research feature: closed daily price below trailing 1400D proxy used in frozen study",
 "DAILY_RSI_WEAK":"historical study threshold RSI < 30",
 "WEEKLY_RSI_WEAK":"historical study threshold closed-week RSI < 35",
 "CAPITULATION_STRESS":"existing capitulation state CAPITULATION/STRESS",
}

@dataclass(frozen=True)
class HistoricalEntryQuality:
    score:float|None;state:str;matched_factors:list;missing_factors:list;contradicting_factors:list;factor_status:dict;factor_groups:dict;closest_historical_entries:list;sample_size:int;research_status:str;research_evidence:str;entry_archetype:str;mae_context:dict;control_comparison:dict;price_vs_200d_pct:float|None;price_vs_200w_pct:float|None;current_drawdown:float|None;drawdown_percentile:float|None;accumulation_context:str;reference_set:str;threshold_provenance:dict
    def to_dict(self):return asdict(self)

def _canonical_bytes(path):return path.read_bytes().replace(b"\r\n",b"\n")
def _hash(path):return hashlib.sha256(_canonical_bytes(path)).hexdigest()

def load_reference_set(root:Path|None=None):
    root=root or Path(__file__).resolve().parents[3];meta_path=root/"frozen"/"best_entry_reference_set_v1.json";episode_path=root/"BITCOIN_ENTRY_EPISODES.csv";factor_path=root/"BITCOIN_ENTRY_FACTOR_MATRIX.csv"
    if not all(p.exists() for p in (meta_path,episode_path,factor_path)):return None,None,"REFERENCE_ARTIFACT_MISSING"
    meta=json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("reference_set")!=REFERENCE_VERSION or _hash(episode_path)!=meta["episodes_sha256"] or _hash(factor_path)!=meta["factor_matrix_sha256"]:return None,None,"REFERENCE_HASH_MISMATCH"
    episodes=pd.read_csv(episode_path);episodes=episodes[episodes.episode_id.isin(meta["episode_ids"])]
    if len(episodes)!=meta["episode_count"]:return None,None,"REFERENCE_EPISODE_MISMATCH"
    return episodes,pd.read_csv(factor_path),"AVAILABLE"

def _current(frame,state,technical):
    p=state["precision"];advanced=state["advanced"];price=float(technical["price"]);close=frame.loc[:p["timestamp"],"close"]
    ma200=close.rolling(200).mean().iloc[-1];ma200w=close.rolling(1400).mean().iloc[-1];draw=float(advanced["drawdown"]["current_drawdown"]);daily=advanced["momentum"]["daily"]["rsi"];weekly=advanced["momentum"]["weekly"]["rsi"]
    support=next((z for z in advanced["historical_zones"] if z["upper_bound"]<=price*1.05 and z["zone_type"] in {"MAJOR_SUPPORT","HISTORICAL_SUPPORT","PREVIOUS_ATH"} and z["confidence"] in {"MODERATE","HIGH"}),None)
    cap=p["risk"]["capitulation"]
    status={"DEEP_DRAWDOWN":draw<=-.4,"EXTREME_DRAWDOWN":draw<=-.7,"MAJOR_HISTORICAL_SUPPORT":support is not None,"HIGH_VALUE":p["value"]["state"] in {"HIGH_VALUE","EXTREME_VALUE"},"BELOW_200D":bool(price<ma200) if pd.notna(ma200) else None,"BELOW_200W":bool(price<ma200w) if pd.notna(ma200w) else None,"DAILY_RSI_WEAK":bool(daily<30) if daily is not None else None,"WEEKLY_RSI_WEAK":bool(weekly<35) if weekly is not None else None,"CAPITULATION_STRESS":cap in {"CAPITULATION","CAPITULATION_CANDIDATE","STRESS"} if cap is not None else None}
    values={"drawdown":draw,"distance_200d":price/ma200-1 if pd.notna(ma200) else np.nan,"distance_200w":price/ma200w-1 if pd.notna(ma200w) else np.nan,"rsi_daily":daily,"rsi_weekly":weekly,"value_score":p["value"]["score"],"major_support":support is not None,"capitulation_state":cap}
    return status,values,support

def _similarity(row,status):
    historical={"DEEP_DRAWDOWN":row.drawdown<=-.4,"EXTREME_DRAWDOWN":row.drawdown<=-.7,"MAJOR_HISTORICAL_SUPPORT":bool(row.major_support),"HIGH_VALUE":row.value_score>=55,"BELOW_200D":row.distance_200d<0,"BELOW_200W":pd.notna(row.distance_200w) and row.distance_200w<0,"DAILY_RSI_WEAK":row.rsi_daily<30,"WEEKLY_RSI_WEAK":row.rsi_weekly<35,"CAPITULATION_STRESS":row.capitulation_state in {"CAPITULATION","STRESS"}}
    available=[k for k,v in status.items() if v is not None];matches=[k for k in available if status[k]==historical[k]]
    return round(100*len(matches)/max(1,len(available)),1),matches,[k for k in available if k not in matches]

def evaluate_historical_entry_quality(frame,state,technical,root:Path|None=None):
    episodes,matrix,availability=load_reference_set(root);status,values,support=_current(frame,state,technical)
    if availability!="AVAILABLE":return HistoricalEntryQuality(None,"HISTORICAL_ENTRY_QUALITY_UNAVAILABLE",[],[],[],status,{},[],0,availability,"LOW","NO_MATCH",{}, {},values["distance_200d"],values["distance_200w"],values["drawdown"],state["advanced"]["drawdown"]["historical_severity_percentile"],"NONE",REFERENCE_VERSION,PROVENANCE).to_dict()
    groups={};weights={"VALUE":.4,"LOCATION":.25,"MOMENTUM_EXTREME":.2,"STRESS":.15}
    for group,names in FACTOR_GROUPS.items():
        vals=[status[n] for n in names if status[n] is not None];ratio=sum(vals)/len(vals) if vals else None;groups[group]={"matched":sum(vals),"available":len(vals),"strength":"UNAVAILABLE" if ratio is None else "STRONG" if ratio>=.67 else "MODERATE" if ratio>=.34 else "ABSENT"}
    score=100*sum(weights[g]*(groups[g]["matched"]/groups[g]["available"] if groups[g]["available"] else 0) for g in groups);state_name="EXTREME" if score>=85 else "VERY_HIGH" if score>=70 else "HIGH" if score>=55 else "MODERATE" if score>=30 else "LOW"
    closest=[]
    for row in episodes.itertuples():
        sim,matched,contradictions=_similarity(row,status);closest.append({"episode_id":int(row.episode_id),"date":row.date,"similarity":sim,"archetype":row.entry_archetype,"historical_return_365d":float(row.return_365d),"historical_MAE_365d":float(row.MAE_365d),"matched_features":matched,"contradictions":contradictions,"label":"Historical outcome, not forecast."})
    closest=sorted(closest,key=lambda x:x["similarity"],reverse=True)[:3];maes=[x["historical_MAE_365d"] for x in closest]
    archetype=closest[0]["archetype"] if closest and closest[0]["similarity"]>=55 else "NO_MATCH"
    matched=[k for k,v in status.items() if v is True];missing=[k for k,v in status.items() if v is False];unavailable=[k for k,v in status.items() if v is None]
    control={"successful_entry_similarity":round(float(np.mean([x["similarity"] for x in closest])),1),"failed_buy_reference_n":5,"neutral_control_note":"aggregate factor matrix control frequencies","distinguishing_success_factors":matrix[matrix.top_entry_lift>=.15].factor.tolist(),"resembles_failed_entries":missing}
    timing=state["precision"]["timing"]["state"];acc="ACCUMULATION_CONTEXT" if state_name in {"HIGH","VERY_HIGH","EXTREME"} and timing not in {"CONFIRMING","CONFIRMED"} else "NONE"
    return HistoricalEntryQuality(round(score,1),state_name,matched,missing,unavailable,status,groups,closest,len(episodes),"LIVE_RESEARCH_CONTEXT","MODERATE",archetype,{"median":float(np.median(maes)),"best":float(max(maes)),"worst":float(min(maes)),"warning":bool(min(maes)<=-.2)},control,values["distance_200d"],values["distance_200w"],values["drawdown"],state["advanced"]["drawdown"]["historical_severity_percentile"],acc,REFERENCE_VERSION,PROVENANCE).to_dict()
