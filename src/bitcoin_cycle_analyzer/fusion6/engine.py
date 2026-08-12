from __future__ import annotations
from dataclasses import dataclass

@dataclass
class BitcoinFusionEngine:
    version:str="FUSION_6_RESEARCH_CHALLENGER"
    def evaluate(self,state:dict,discovery:dict|None=None)->dict:
        m3=state["master"];m5=state["master5_challenger"];regime=state["precision"]["regime"]["current"];timing=m3["state"]["timing"]
        # Domain routing, never arithmetic averaging.
        long_term=m3["decision"]["long_term_action"]
        rare=m5["buy"]["state"]
        new_entry="WAIT" if timing=="WAIT" else "ACCUMULATE_CONFIRMED" if long_term=="ACCUMULATE" else m3["decision"]["new_entry_action"]
        risk=m3["decision"]["risk_action"] if m5["risk"]["sell_off_risk"] in {"LOW","MODERATE"} else m5["risk"]["existing_position_action"]
        existing="HOLD" if risk in {"NORMAL","CAUTION","WATCH_RISK"} else risk
        disagreement=[]
        if m3["decision"]["new_entry_action"]!=new_entry:disagreement.append({"domain":"NEW_ENTRY","control_3":m3["decision"]["new_entry_action"],"fusion_6":new_entry,"reason":"confirmed timing owns entry"})
        agreement="HIGH" if not disagreement else "MODERATE" if len(disagreement)==1 else "LOW"
        patterns=[] if discovery is None else discovery.get("active_patterns",[])
        return {"model":self.version,"status":"RESEARCH_CHALLENGER","domain_ownership":{"long_term":"CONTROL_3 + historical context","rare_buy":"SPECIALIST_5","timing":"CONTROL_3 + MT5 confirmed candles","historical_location":"SPECIALIST_5","regime":"CONTROL_3","distribution":"SPECIALIST_5_RESEARCH","risk":"CONTROL_3 with SPECIALIST_5 escalation","final_decision":"FUSION_6 domain routing"},"long_term":long_term,"new_entry":new_entry,"existing_position":existing,"risk":risk,"rare_buy":rare,"rare_sell":"REJECTED_LEGACY_NOT_USED","distribution":m5["risk"]["distribution"],"historical_entry_quality":state["historical_entry_quality"],"regime":regime,"timing":timing,"zones":m5["buy"]["zone"],"drawdown":m3["state"]["drawdown"],"recovery":m3["state"]["recovery_state"],"macro":state["modules"]["macro"],"news":state["modules"]["news"],"derivatives":state["modules"]["derivatives"],"onchain":state["modules"]["onchain"],"evidence":m3["state"]["evidence"],"uncertainty":m3["state"]["uncertainty"],"data_quality":m3["state"]["data_quality"],"control_3_state":m3["decision"],"specialist_5_state":m5,"agreement":agreement,"disagreement":disagreement,"active_historical_patterns":patterns[:5],"pattern_completion":None if not patterns else {"matched":len(patterns[0]["factors"]),"total":len(patterns[0]["factors"]),"probability":False},"openai":"EXPLANATION_ONLY","execution":"DISABLED"}
