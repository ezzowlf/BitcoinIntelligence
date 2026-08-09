from __future__ import annotations
from .models import BitcoinMasterState,BitcoinMasterDecision
from .registry import build_factor_registry

PRIMARY_ANALYSIS_MODEL="2.5-RARE-SIGNAL";CONTROL_MODEL="2.3-FROZEN";MASTER_MODEL="MASTER-3.0"


def _module_state(module):
    if module.get("status")!="AVAILABLE":return module.get("status","UNAVAILABLE")
    for key in ("state","regime","risk_state"):
        value=module.get(key)
        if isinstance(value,str):return value
    return "AVAILABLE"


class BitcoinMasterEngine:
    def build_state(self,state,technical):
        p=state["precision"];rare=state["rare_signal"];advanced=state["advanced"];zones=advanced["historical_zones"];price=float(technical["price"])
        support=next((z for z in zones if z["upper_bound"]<=price and ("SUPPORT" in z["zone_type"] or z["zone_type"]=="PREVIOUS_ATH")),rare.get("historical_support"));resistance=next((z for z in zones if z["lower_bound"]>=price and ("RESISTANCE" in z["zone_type"] or z["zone_type"]=="PREVIOUS_ATH")),rare.get("historical_resistance"))
        momentum=advanced["momentum"];draw=advanced["drawdown"];registry=build_factor_registry(state,technical)
        supportive=[]
        if p["value"]["state"] in {"HIGH_VALUE","EXTREME_VALUE"}:supportive.append("LONG_TERM_VALUE")
        if support is not None:supportive.append("PRICE_STRUCTURE")
        if p["timing"]["state"] in {"CONFIRMING","CONFIRMED"}:supportive.append("TIMING")
        if p["regime"]["current"] in {"RECOVERY","EARLY_BULL","BULL","ACCUMULATION"}:supportive.append("REGIME")
        if rare["sell"]["distribution"] in {"DISTRIBUTION","DISTRIBUTION_CONFIRMED"}:supportive.append("DISTRIBUTION_RISK")
        independent_groups=len(set(supportive));confluence={"level":"VERY_HIGH" if independent_groups>=5 else "HIGH" if independent_groups>=4 else "MODERATE" if independent_groups>=2 else "LOW","independent_groups":independent_groups,"supportive_groups":supportive,"method":"directional, redundancy-aware domain support; not a universal score"}
        h=state["historical_entry_quality"];mae=h.get("mae_context",{})
        return BitcoinMasterState(p["timestamp"],price,p["value"]["state"],p["value"]["score"],p["cycle"]["primary_regime"],p["regime"]["current"],p["regime"]["stability"],rare["buy_state"],rare["level_b"]["buy"],rare["level_b"]["buy_completion"],rare["sell"]["state"],rare["level_b"]["sell"],rare["level_b"]["sell_completion"],rare["sell"]["distribution"],p["timing"]["state"],p["timing"]["score"],state["decision"]["risk_action"],p["risk"]["horizons"]["7d"],p["risk"]["horizons"]["30d"],p["risk"]["horizons"]["90d"],draw["current_drawdown"],draw["historical_severity_percentile"],draw["state"],momentum["weekly"]["rsi"],momentum["monthly"]["rsi"],momentum["rsi_365d"]["value"],momentum["daily"]["bollinger"]["state"],momentum["weekly"]["bollinger"]["state"],momentum["monthly"]["bollinger"]["state"],support,resistance,[state["decision"]["zones"].get("buy_zone_1"),state["decision"]["zones"].get("buy_zone_2")],[resistance] if resistance else [],_module_state(state["modules"]["onchain"]),_module_state(state["modules"]["derivatives"]),_module_state(state["modules"]["macro"]),_module_state(state["modules"]["etf"]),_module_state(state["modules"]["news"]),p["evidence"],confluence,p["data_health"],p["uncertainty"],registry,h.get("score"),h["state"],h["entry_archetype"],h["matched_factors"],h["missing_factors"],h["contradicting_factors"],h["closest_historical_entries"],mae.get("median"),mae.get("best"),mae.get("worst"),h.get("price_vs_200d_pct"),h.get("price_vs_200w_pct"),h["research_status"])
    def decide(self,master,state):
        rare=state["rare_signal"];control=state["decision"];unreliable=not master.data_quality["critical_healthy"];production=rare["level_a"]["signal"]
        sell_valid=rare["sell"]["confirmation"]=="CONFIRMED" and rare["sell"]["independent_groups"]>=3
        if production in {"SELL","STRONG_SELL"} and not sell_valid:production="NO_PRODUCTION_SIGNAL"
        long_term="WAIT" if unreliable else "REDUCE" if production in {"SELL","STRONG_SELL"} else "STRONG_ACCUMULATE" if production=="STRONG_BUY" else "ACCUMULATE" if rare["buy_state"] in {"ACCUMULATE","BUY","STRONG_BUY"} else "HOLD"
        new_entry="DO_NOT_BUY" if unreliable or production in {"SELL","STRONG_SELL"} else production if production in {"BUY","STRONG_BUY"} else "ACCUMULATE" if rare["buy_state"]=="ACCUMULATE" else "WAIT"
        existing="SELL" if production in {"SELL","STRONG_SELL"} else "REDUCE" if rare["sell"]["state"]=="REDUCE" else "TAKE_PARTIAL_PROFIT" if rare["sell"]["distribution"] in {"DISTRIBUTION","DISTRIBUTION_CONFIRMED"} and master.risk in {"HIGH_RISK","REDUCE_RISK"} else "HOLD"
        confidence="LOW" if unreliable or master.uncertainty["state"]=="HIGH" and master.evidence["label"]=="LOW" else "HIGH" if master.evidence["label"]=="HIGH" and master.regime_stability=="HIGH" else "MODERATE"
        positives=[f"Value {master.value_state}",f"Drawdown {master.drawdown:.1%}"]+( [f"Support {master.nearest_support['confidence']}"] if master.nearest_support else [])
        negatives=[f"Regime {master.regime}",f"Timing {master.timing}"]+([f"Distribution {master.distribution}"] if master.distribution!="NONE" else [])
        uncertain=[f"Uncertainty {master.uncertainty['state']}"]+[f"{x['name']} unavailable" for x in master.factor_registry if x["availability"]!="AVAILABLE"]
        disagreement={"state":"MODEL_DISAGREEMENT" if control["long_term_decision"]!=long_term and not (control["long_term_decision"]=="ACCUMULATE" and long_term=="ACCUMULATE") else "ALIGNED","2.3":control["long_term_decision"],"2.5":rare["level_a"]["signal"],"MASTER":long_term}
        return BitcoinMasterDecision(long_term,new_entry,existing,master.risk,production,rare["level_b"]["buy"] if rare["level_b"]["buy"]!="NONE" else rare["level_b"]["sell"],confidence,positives[:5],negatives[:5],uncertain[:5],control["waiting_for"],control["next_upgrade_conditions"],control["next_downgrade_conditions"],control["invalidation_conditions"],disagreement)
    def analyze(self,state,technical):
        master=self.build_state(state,technical);decision=self.decide(master,state)
        return {"version":MASTER_MODEL,"primary_analysis_model":PRIMARY_ANALYSIS_MODEL,"control_model":CONTROL_MODEL,"state":master.to_dict(),"decision":decision.to_dict(),"execution":"DISABLED"}
