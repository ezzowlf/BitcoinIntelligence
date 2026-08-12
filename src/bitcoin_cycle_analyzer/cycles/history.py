from __future__ import annotations

import pandas as pd

HALVINGS=pd.to_datetime(["2012-11-28","2016-07-09","2020-05-11","2024-04-20"],utc=True)

def _normalized(close,anchor,window_before=0,window_after=1500):
    segment=close.loc[anchor-pd.Timedelta(days=window_before):anchor+pd.Timedelta(days=window_after)]
    if segment.empty:return []
    nearest=segment.index[(segment.index-anchor).to_series().abs().argmin()];base=float(segment.loc[nearest])
    return [{"day":(ts-anchor).days,"normalized":float(value/base)} for ts,value in segment.resample("7D").last().dropna().items()]


def _point(ts, price, kind):
    return {"timestamp": pd.Timestamp(ts), "price": float(price), "kind": kind}


def analyze_cycle_history(frame: pd.DataFrame, as_of=None) -> dict:
    data = frame.loc[:as_of].dropna(subset=["close"]).copy() if as_of is not None else frame.dropna(subset=["close"]).copy()
    close = data.close.astype(float)
    if close.empty:
        return {"status":"UNAVAILABLE","cycles":[],"ath_normalized":[],"current":{},"provenance":{"price_source":"BITSTAMP historical dataset","pit_status":"NO_DATA"}}
    candidates = close[close == close.rolling(365, center=True, min_periods=min(120,len(close))).max()]
    peaks = candidates.groupby(candidates.index.year).idxmax() if not candidates.empty else pd.Series(dtype="datetime64[ns]")
    points = []
    for peak_ts in peaks.sort_values():
        peak = close.loc[peak_ts]
        after = close.loc[peak_ts:]
        if after.empty: continue
        trough_ts = after.iloc[: min(800, len(after))].idxmin(); trough = close.loc[trough_ts]
        points.append((_point(peak_ts, peak, "MAJOR_HIGH"), _point(trough_ts, trough, "MAJOR_LOW")))
    dedup=[]
    for high,low in points:
        if dedup and high["timestamp"] <= dedup[-1][1]["timestamp"]: continue
        dedup.append((high,low))
    rows=[]; overlays=[];bottom_overlays=[]
    for number,(high,low) in enumerate(dedup,1):
        segment=close.loc[high["timestamp"]:low["timestamp"]]
        rows.append({"cycle":number,"major_high":high["timestamp"],"major_low":low["timestamp"],"peak_price":high["price"],"trough_price":low["price"],
                     "drawdown_high_to_low":low["price"]/high["price"]-1,"days_high_to_low":(low["timestamp"]-high["timestamp"]).days})
        overlays.append({"cycle":number,"basis":"ATH","points":[{"day":(ts-high["timestamp"]).days,"normalized":float(v/high["price"])} for ts,v in segment.resample("7D").last().dropna().items()]})
        bottom_overlays.append({"cycle":number,"basis":"MAJOR_LOW","points":_normalized(close,low["timestamp"])})
    ath=float(close.cummax().iloc[-1]); current=float(close.iloc[-1]); ath_ts=close.loc[:close.idxmax()].idxmax()
    halvings=[{"halving":h,"points":_normalized(close,h,365,1500)} for h in HALVINGS if close.index[0]<=h<=close.index[-1]];last_halving=max((h for h in HALVINGS if h<=close.index[-1]),default=None)
    return {"status":"RESEARCH_ONLY","cycles":rows,"ath_normalized":overlays,"bottom_recovery_normalized":bottom_overlays,"halving_normalized":halvings,
            "current":{"timestamp":close.index[-1],"price":current,"ath":ath,"drawdown":current/ath-1,"days_since_ath":(close.index[-1]-ath_ts).days},
            "days_since_halving":None if last_halving is None else (close.index[-1]-last_halving).days,
            "provenance":{"price_source":"BITSTAMP historical dataset","coverage_start":close.index[0],"coverage_end":close.index[-1],"pit_status":"PIT_CAUSAL_INPUT; cycle labels research-only","method":"365D extrema; research labels require later confirmation"}}
