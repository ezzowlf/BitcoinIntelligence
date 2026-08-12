from __future__ import annotations
import hashlib,json

ALERT_TRANSITIONS={
    ("WATCH_BUY","BUY_ZONE"),("BUY_ZONE","STRONG_BUY_CANDIDATE"),("STRONG_BUY_CANDIDATE","HISTORICAL_EXTREME"),
    ("WATCH","DISTRIBUTION_CANDIDATE"),("DISTRIBUTION_CANDIDATE","DISTRIBUTION_CONFIRMED"),("DISTRIBUTION_CONFIRMED","HIGH_RISK_DISTRIBUTION")}

def challenger_state_change(previous:dict|None,current:dict)->dict|None:
    if previous is None:return None
    changes=[]
    for path in (("buy","state"),("risk","distribution")):
        old=previous[path[0]][path[1]];new=current[path[0]][path[1]]
        if (old,new) in ALERT_TRANSITIONS:changes.append({"engine":path[0],"old":old,"new":new})
    if not changes:return None
    payload={"changes":changes,"model":current["model"],"buy_quality":current["buy"]["quality"],"buy_zone":current["buy"]["zone"],"factors":{"buy":[k for k,v in current["buy"]["factors"].items() if v],"risk":[k for k,v in current["risk"]["factors"].items() if v]},"invalidation":current["levels"].get("support"),"status":"SHADOW_RESEARCH","execution":"DISABLED"}
    payload["fingerprint"]=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest();return payload
