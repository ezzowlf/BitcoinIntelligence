from __future__ import annotations

STATUSES={"VALIDATED","PARTIALLY_VALIDATED","TIMING_ONLY","RISK_ONLY","RESEARCH","RESEARCH_ONLY","REJECTED","UNAVAILABLE"}


def _entry(name,group,status,role,availability="AVAILABLE",freshness="CURRENT",confidence="MODERATE",independence=None):
    assert status in STATUSES
    return {"name":name,"group":group,"status":status,"direction_role":role,"confidence":confidence,"freshness":freshness,"availability":availability,"independence_group":independence or group,"research_status":status}


def build_factor_registry(state,technical):
    p=state["precision"];data=state["data_status"]
    def provider(name,group,status,role):
        item=data.get(name,{"status":"UNAVAILABLE"});available=item.get("status")=="AVAILABLE"
        # Availability is data health; the registry status remains the
        # domain role. Derivatives are risk-only even when the feed is absent.
        return _entry(name,group,status,role,item.get("status","UNAVAILABLE"),"CURRENT" if available else "UNKNOWN",independence=group)
    factors=[
      _entry("price","PRICE","VALIDATED","CONTEXT",confidence="HIGH"),_entry("structure","STRUCTURE","PARTIALLY_VALIDATED","TIMING",confidence="HIGH"),
      _entry("fibonacci","ZONES","RESEARCH_ONLY","CONTEXT",independence="PRICE_STRUCTURE"),_entry("historical_zones","ZONES","RESEARCH","CONTEXT",independence="PRICE_STRUCTURE"),
      _entry("rsi","MOMENTUM","TIMING_ONLY","TIMING",independence="MOMENTUM"),_entry("bollinger","MOMENTUM","TIMING_ONLY","TIMING",independence="MOMENTUM"),
      _entry("drawdown","VALUE","PARTIALLY_VALIDATED","CONTEXT",independence="LONG_TERM_VALUE"),_entry("recovery","REGIME","RESEARCH","CONTEXT",independence="RECOVERY"),
      _entry("cycle","REGIME","RESEARCH","CONTEXT",independence="CYCLE"),_entry("regime","REGIME","RESEARCH","CONTEXT",independence="REGIME"),
      _entry("value","VALUE",p["value"].get("status","PARTIALLY_VALIDATED"),"DIRECTION",independence="LONG_TERM_VALUE"),_entry("timing","TIMING","RESEARCH","TIMING",independence="TIMING"),
      _entry("risk","RISK","RESEARCH","RISK",independence="RISK"),_entry("capitulation","RISK","RESEARCH","CONTEXT",independence="CAPITULATION"),
      _entry("distribution","DISTRIBUTION","RESEARCH","RISK",independence="DISTRIBUTION"),_entry("historical_sell_proxy","DISTRIBUTION","REJECTED","NONE",confidence="HIGH",independence="REJECTED_SELL"),
      provider("onchain","ONCHAIN","PARTIALLY_VALIDATED","CONTEXT"),provider("derivatives","DERIVATIVES","RISK_ONLY","RISK"),provider("macro","MACRO","RESEARCH","CONTEXT"),provider("etf","ETF","RESEARCH","CONTEXT"),provider("news","NEWS","RESEARCH","RISK"),
      _entry("seasonality","SEASONALITY","RESEARCH_ONLY","CONTEXT"),_entry("similarity","SIMILARITY","RESEARCH_ONLY","CONTEXT"),_entry("elliott","ELLIOTT","RESEARCH_ONLY","CONTEXT")]
    return factors
