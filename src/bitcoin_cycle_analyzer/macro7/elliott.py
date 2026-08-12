from __future__ import annotations
import pandas as pd
from ..elliott_wave import analyze_elliott_intelligence

DEGREES=(("MACRO_CYCLE","ME"),("PRIMARY","W-MON"),("INTERMEDIATE","D"),("MINOR","4h"))

def _bars(frame,rule):
    if rule=="D":return frame
    bars=frame.resample(rule,label="right",closed="right").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    return bars[bars.index<=frame.index.max()]

class FullHistoryElliottEngine:
    """Structural multi-degree research counts; never a production driver."""
    def _macro_pivots(self,frame):
        monthly=_bars(frame,"ME");close=monthly.close;threshold=.35;pivots=[];direction=None;extreme_ts=close.index[0];extreme=float(close.iloc[0])
        for ts,value in close.iloc[1:].items():
            value=float(value)
            if direction in (None,"UP"):
                if value>=extreme:extreme_ts,extreme=ts,value
                elif value/extreme-1<=-threshold:pivots.append({"timestamp":extreme_ts,"price":extreme,"kind":"HIGH","confirmed_at":ts});direction="DOWN";extreme_ts,extreme=ts,value
            if direction=="DOWN":
                if value<=extreme:extreme_ts,extreme=ts,value
                elif value/extreme-1>=threshold:pivots.append({"timestamp":extreme_ts,"price":extreme,"kind":"LOW","confirmed_at":ts});direction="UP";extreme_ts,extreme=ts,value
        pivots.append({"timestamp":extreme_ts,"price":extreme,"kind":"HIGH" if direction=="UP" else "LOW","confirmed_at":close.index[-1]})
        labels=[];impulse=1
        for p in pivots:
            if p["kind"]=="HIGH":label=str(min(5,impulse));impulse+=2
            else:label=str(min(4,impulse));impulse+=2
            if impulse>6:impulse=1
            labels.append({**p,"algorithmic_label":label})
        return labels
    def analyze(self,frame,as_of=None,four_hour=None):
        data=frame.loc[:as_of] if as_of is not None else frame;hierarchy={}
        for degree,rule in DEGREES:
            bars=four_hour if degree=="MINOR" and four_hour is not None and not four_hour.empty else _bars(data,rule)
            hierarchy[degree]=analyze_elliott_intelligence(bars,as_of=bars.index[-1],timeframe={"MACRO_CYCLE":"1M","PRIMARY":"1W","INTERMEDIATE":"1D","MINOR":"4H"}[degree]);hierarchy[degree]["wave_degree"]=degree;hierarchy[degree]["primary"]["degree"]=degree
        pivots=self._macro_pivots(data);recent=pivots[-5:];last_low=next((x for x in reversed(recent) if x["kind"]=="LOW"),None);last_high=next((x for x in reversed(recent) if x["kind"]=="HIGH"),None)
        primary={"rank":1,"label":"PRIMARY","name":"Possible macro wave 4 completion / recovery watch" if last_low and recent[-1]["kind"]=="LOW" else "Possible macro corrective structure","degree":"MACRO_CYCLE","relative_support":None,"support_is_probability":False,"invalidation_level":None if last_low is None else last_low["price"],"invalidation_reason":"Confirmed monthly break below the latest structural low","confirmation_level":None if last_high is None else last_high["price"],"rules_passed":["alternating confirmed monthly pivots"],"guidelines_matched":["large-cycle correction structure"],"guidelines_missed":["next impulse not confirmed"],"status":"RESEARCH_ONLY"}
        alternatives=[{"rank":2,"label":"ALTERNATIVE_A","name":"Larger ABC / C-wave continuation","degree":"MACRO_CYCLE","relative_support":None,"support_is_probability":False,"invalidation_level":None if last_high is None else last_high["price"],"confirmation_level":None if last_low is None else last_low["price"],"status":"RESEARCH_ONLY","rules_passed":[],"guidelines_matched":["bear continuation remains possible below resistance"],"guidelines_missed":[]}]
        explanation={"wave_start":None if last_low is None else last_low["timestamp"],"wave_start_price":None if last_low is None else last_low["price"],"historical_pivots":recent,"why":"Confirmed monthly structural reversals and alternating pivots; labels remain revisable.","wave_5":"Only applicable after a confirmed corrective low and subsequent structural breakout.","invalidation":primary.get("invalidation_level"),"confirmation":primary.get("confirmation_level"),"abc_alternative":"A larger ABC correction remains plausible while recovery structure is unconfirmed."}
        return {"status":"RESEARCH_ONLY","production_role":"CONTEXT_ONLY","coverage":{"from":data.index.min(),"to":data.index.max()},"hierarchy":hierarchy,"macro_pivots":pivots,"primary":primary,"alternatives":alternatives,"explanation":explanation,"quality":{"structural_validity":"MODERATE" if len(pivots)>=5 else "LOW","count_stability":"LOW","historical_failure_rate":None,"fib_alignment":"RESEARCH_PENDING","regime_alignment":"CONTEXT_ONLY"},"single_candidate_note":None}

    def replay(self,frame,frequency="180D"):
        rows=[]
        for cutoff in pd.date_range(frame.index.min()+pd.Timedelta(days=730),frame.index.max(),freq=frequency,tz="UTC"):
            result=self.analyze(frame,as_of=cutoff);p=result["primary"];rows.append({"cutoff":cutoff,"name":p["name"],"invalidation":p.get("invalidation_level"),"pivot_count":len(result["macro_pivots"])})
        out=pd.DataFrame(rows);out["revised"]=out.name.ne(out.name.shift()) if not out.empty else pd.Series(dtype=bool);return out
