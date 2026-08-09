from __future__ import annotations
import json
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.external_store import ExternalMetricStore
from bitcoin_cycle_analyzer.validation.matrix import empty_validation_matrix, ablation_plan


def correlation(feature,target):
    joined=pd.concat([feature,target],axis=1).dropna()
    return None if len(joined)<100 else float(joined.rank().corr().iloc[0,1])


def main():
    root=Path(__file__).resolve().parents[1]; config=load_config(root/"config.yaml")
    price=OHLCVStore(root/config["data"]["database"]).load("1d"); price.index=pd.to_datetime(price.index,utc=True)
    store=ExternalMetricStore(root/config["data"]["external_database"])
    oi=store.load("open_interest_usd"); oi=oi[oi.provider=="binance-vision-public-archive"]
    daily=oi.set_index("available_at").value.resample("1D").last().dropna(); feature=daily.pct_change(7)
    joined=pd.DataFrame({"close":price.close,"oi_change_7d":feature}).dropna(); split=joined.index[int(len(joined)*.7)]
    horizons={}
    for days in (7,30,90,180,365):
        target=joined.close.shift(-days)/joined.close-1
        horizons[str(days)]={"all_rank_correlation":correlation(joined.oi_change_7d,target),
                             "oos_rank_correlation":correlation(joined.loc[split:,"oi_change_7d"],target.loc[split:]),
                             "observations":int(pd.concat([joined.oi_change_7d,target],axis=1).dropna().shape[0])}
    funding=store.load("funding_rate_8h").set_index("available_at").value.resample("1D").mean()
    risk_frame=pd.DataFrame({"close":price.close,"oi":daily,"funding":funding}).dropna()
    risk_frame["oi_pct"]=risk_frame.oi.rolling(365,min_periods=90).rank(pct=True)
    risk_frame["funding_pct"]=risk_frame.funding.rolling(365,min_periods=90).rank(pct=True)
    future_returns=pd.concat([risk_frame.close.shift(-i)/risk_frame.close-1 for i in range(1,31)],axis=1)
    risk_frame["mae_30d"]=future_returns.min(axis=1); risk_frame["vol_30d"]=future_returns.std(axis=1)
    extreme=risk_frame[(risk_frame.oi_pct>=.9)|(risk_frame.funding_pct>=.95)]
    normal=risk_frame[(risk_frame.oi_pct.between(.25,.75))&(risk_frame.funding_pct.between(.25,.75))]
    risk_comparison={"extreme_raw_observations":int(len(extreme)),"normal_raw_observations":int(len(normal)),
                     "extreme_mae_median":float(extreme.mae_30d.median()),"normal_mae_median":float(normal.mae_30d.median()),
                     "extreme_volatility_median":float(extreme.vol_30d.median()),"normal_volatility_median":float(normal.vol_30d.median()),
                     "conclusion":"NO_ROBUST_OI_RISK_UPLIFT"}
    matrix=empty_validation_matrix(); matrix["CORE"]={"status":"BASELINE","horizons":{},"independent_episodes":None}
    matrix["CORE + DERIVATIVES"]={"status":"TESTED","horizons":horizons,"independent_episodes":None,
                                   "conclusion":"RESEARCH/RISK_ONLY; unstable OOS direction"}
    report={"split":{"method":"chronological 70/30; final OOS untouched","oos_start":str(split)},
            "oi":{"provider":"binance-vision-public-archive","start":str(oi.event_timestamp.min()),"end":str(oi.event_timestamp.max()),
                  "observations":len(oi),"hourly":True,"validation":horizons,"risk_comparison":risk_comparison},"validation_matrix":matrix,
            "ablation_plan":ablation_plan({"DERIVATIVES","ONCHAIN"}),
            "provider_status":{"macro":"UNAVAILABLE_NO_FRED_API_KEY","etf":"UNAVAILABLE_NO_LICENSED_PIT_SOURCE",
                               "news":"UNAVAILABLE_NO_MEANPULSE_ENDPOINT","onchain":"RESEARCH","funding":"RISK_ONLY","oi":"RESEARCH"}}
    path=root/"data"/"reports"/"intelligence_22_validation.json"; path.write_text(json.dumps(report,indent=2,default=str),encoding="utf-8")
    return report


if __name__=="__main__": print(json.dumps(main(),indent=2,default=str))
