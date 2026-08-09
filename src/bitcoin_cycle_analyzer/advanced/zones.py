from __future__ import annotations
from dataclasses import dataclass
import hashlib
import numpy as np
import pandas as pd


@dataclass
class HistoricalZoneEngine:
    pivot_window:int=3
    min_touches:int=2

    def _atr(self,frame):
        prev=frame.close.shift();tr=pd.concat([frame.high-frame.low,(frame.high-prev).abs(),(frame.low-prev).abs()],axis=1).max(axis=1);return tr.rolling(14,min_periods=5).median()
    def _pivots(self,frame):
        atr=self._atr(frame);rows=[];w=self.pivot_window
        for i in range(w,len(frame)-w):
            segment=frame.iloc[i-w:i+w+1];ts=frame.index[i];confirmed=frame.index[i+w]
            if frame.high.iloc[i]>=segment.high.max():rows.append((float(frame.high.iloc[i]),"RESISTANCE",ts,confirmed,float(atr.iloc[i])))
            if frame.low.iloc[i]<=segment.low.min():rows.append((float(frame.low.iloc[i]),"SUPPORT",ts,confirmed,float(atr.iloc[i])))
        return rows
    def analyze(self,frame,as_of=None,fib_levels=None):
        visible=frame.loc[:as_of].copy() if as_of is not None else frame.copy();cutoff=visible.index[-1];points=[]
        for timeframe,rule,weight in (("WEEKLY","W-MON",1.0),("MONTHLY","ME",1.35)):
            bars=visible.resample(rule,label="right",closed="right").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
            running_ath=bars.high.cummax()
            for price,kind,event,confirmed,atr in self._pivots(bars):
                if confirmed<=cutoff:points.append({"price":price,"kind":kind,"event":event,"confirmed":confirmed,"atr":atr,"timeframe":timeframe,"weight":weight,"previous_ath":kind=="RESISTANCE" and price>=float(running_ath.loc[event])})
        points.sort(key=lambda x:x["price"]);clusters=[]
        for point in points:
            tolerance=max(point["atr"]*.6,point["price"]*.005)
            target=next((c for c in clusters if abs(c["center"]-point["price"])<=max(tolerance,c["tolerance"])),None)
            if target is None:clusters.append({"points":[point],"center":point["price"],"tolerance":tolerance})
            else:
                target["points"].append(point);weights=[p["weight"] for p in target["points"]];target["center"]=float(np.average([p["price"] for p in target["points"]],weights=weights));target["tolerance"]=max(target["tolerance"],tolerance)
        current=float(visible.close.iloc[-1]);zones=[]
        for cluster in clusters:
            pts=cluster["points"];independent=[]
            for p in sorted(pts,key=lambda x:x["confirmed"]):
                if not independent or (p["confirmed"]-independent[-1]["confirmed"]).days>=21:independent.append(p)
            if len(independent)<self.min_touches:continue
            prices=np.array([p["price"] for p in pts]);width=max(float(np.std(prices))*1.5,float(np.median([p["atr"] for p in pts]))*.35);low=max(0,cluster["center"]-width);high=cluster["center"]+width
            reactions=[];returns7=[];returns30=[];maes=[];mfes=[]
            for p in independent:
                future=visible.loc[p["confirmed"]:].head(31)
                if len(future)>1:
                    reactions.append(float(future.close.max()/p["price"]-1) if p["kind"]=="SUPPORT" else float(p["price"]/future.close.min()-1));returns7.append(float(future.close.iloc[min(7,len(future)-1)]/p["price"]-1));returns30.append(float(future.close.iloc[-1]/p["price"]-1));maes.append(float(future.low.min()/p["price"]-1));mfes.append(float(future.high.max()/p["price"]-1))
            failures=sum(1 for x in reactions if x<0.03);touches=len(independent);age=max(0,(cutoff-max(p["confirmed"] for p in pts)).days);strength=min(100,25+touches*11+min(25,max(0,np.median(reactions) if reactions else 0)*100)-min(20,age/365*3))
            kinds=[p["kind"] for p in pts];base="HISTORICAL_SUPPORT" if current>=cluster["center"] else "HISTORICAL_RESISTANCE";major=touches>=4 or any(p["timeframe"]=="MONTHLY" for p in pts)
            if major:base="MAJOR_SUPPORT" if current>=cluster["center"] else "MAJOR_RESISTANCE"
            if any(p["previous_ath"] for p in pts):base="PREVIOUS_ATH"
            fib_confluence=any(low<=float(level)<=high for level in (fib_levels or []))
            if fib_confluence:strength=min(100,strength+5)
            flip="RESISTANCE_TO_SUPPORT" if "RESISTANCE" in kinds and current>high else "SUPPORT_TO_RESISTANCE" if "SUPPORT" in kinds and current<low else None
            first=min(p["confirmed"] for p in pts);last=max(p["confirmed"] for p in pts);zone_id=hashlib.sha256(f"{first}|{round(cluster['center'],2)}".encode()).hexdigest()[:16]
            zones.append({"zone_id":zone_id,"lower_bound":round(low,2),"upper_bound":round(high,2),"zone_type":base,"strength":round(strength,1),"confidence":"HIGH" if strength>=75 else "MODERATE" if strength>=55 else "LOW","timeframe":"MONTHLY" if any(p["timeframe"]=="MONTHLY" for p in pts) else "WEEKLY","first_seen":first,"last_confirmed":last,"touch_count":touches,"successful_reactions":touches-failures,"failed_reactions":failures,"failure_rate":round(failures/touches,3),"median_reaction":None if not reactions else round(float(np.median(reactions)),4),"median_7d_reaction":None if not returns7 else round(float(np.median(returns7)),4),"median_30d_reaction":None if not returns30 else round(float(np.median(returns30)),4),"MAE":None if not maes else round(float(np.median(maes)),4),"MFE":None if not mfes else round(float(np.median(mfes)),4),"support_exhaustion":round(min(1,max(0,(touches-3)/6+failures/max(1,touches))),3),"zone_flip":flip,"fib_confluence":fib_confluence,"distance_usd":round(cluster["center"]-current,2),"distance_percent":round(cluster["center"]/current-1,4),"formation_cutoff":last,"version":touches})
        return sorted(zones,key=lambda z:abs(z["distance_percent"]))
