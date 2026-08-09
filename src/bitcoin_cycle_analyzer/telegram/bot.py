from __future__ import annotations
import hashlib,json
from .formatter import command_message,decision_message

class TelegramDecisionBot:
    def __init__(self,dry_run=True,ledger=None):self.dry_run=dry_run;self.ledger=ledger;self._fingerprints=set()
    def command(self,command,state,health=None):return command_message(command,state,health)
    def alert(self,state,previous=None):
        decision=state["decision"]; current=(decision["long_term_decision"],decision["swing_decision"],decision["risk_action"],state["precision"]["regime"]["current"],state["precision"]["timing"]["state"])
        old=None if previous is None else (previous["decision"]["long_term_decision"],previous["decision"]["swing_decision"],previous["decision"]["risk_action"],previous["precision"]["regime"]["current"],previous["precision"]["timing"]["state"])
        if old is None or old==current:return None
        if state["precision"].get("candle_status","CONFIRMED")!="CONFIRMED":
            return {"alert_id":None,"message":"PREVIEW - unconfirmed candle\n"+decision_message(state),"dry_run":self.dry_run,"execution":"DISABLED","confirmed":False}
        fingerprint=hashlib.sha256(json.dumps(current).encode()).hexdigest()
        if fingerprint in self._fingerprints or (self.ledger is not None and self.ledger.alert_exists(fingerprint)):return None
        self._fingerprints.add(fingerprint)
        alert={"alert_id":fingerprint,"message":decision_message(state),"dry_run":self.dry_run,"execution":"DISABLED","confirmed":True}
        if self.ledger is not None:
            alert.update({"market_state":state["precision"]["market_state"],"btc_price":decision["zones"]["current_price"]})
            self.ledger.append_alert(fingerprint,state["precision"]["timestamp"],"STATE_CHANGE",decision["long_term_decision"],alert,"DRY_RUN" if self.dry_run else "PENDING")
        return alert
