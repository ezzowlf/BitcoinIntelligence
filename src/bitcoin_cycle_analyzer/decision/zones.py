from __future__ import annotations


def build_zones(price:float,technical:dict)->dict:
    candidates=sorted(technical.get("confluence_zones",[]),key=lambda zone:abs(zone["center"]-price))
    below=[zone for zone in candidates if zone["center"]<price]; above=[zone for zone in candidates if zone["center"]>=price]
    def output(zone,label):
        if zone is None:return {"label":label,"status":"UNAVAILABLE","low":None,"high":None,"confidence":"LOW"}
        confidence="HIGH" if zone.get("count",0)>=7 else "MODERATE" if zone.get("count",0)>=4 else "LOW"
        return {"label":label,"status":"AVAILABLE","low":round(float(zone["low"]),2),"high":round(float(zone["high"]),2),"center":round(float(zone["center"]),2),"confidence":confidence,"confluence_count":int(zone.get("count",0))}
    buy1=below[0] if below else None; buy2=below[1] if len(below)>1 else None; resistance=above[0] if above else None
    invalidation=None if buy2 is None else {"label":"INVALIDATION","status":"AVAILABLE","below":round(float(buy2["low"]),2),"confidence":"MODERATE"}
    return {"current_price":round(price,2),"buy_zone_1":output(buy1,"BUY ZONE 1"),"buy_zone_2":output(buy2,"BUY ZONE 2"),
            "major_support":output(buy1,"MAJOR SUPPORT"),"invalidation":invalidation or {"status":"UNAVAILABLE"},"resistance":output(resistance,"RESISTANCE"),
            "note":"Zones are derived from existing technical confluence, not price targets."}
