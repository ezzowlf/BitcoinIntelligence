from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"scripts"))
import bitcoin_intelligence
from bitcoin_cycle_analyzer.telegram.formatter import decision_message
from bitcoin_cycle_analyzer.telegram.events import event_message


def main():
    state,_=bitcoin_intelligence.state();messages={}
    for decision in ("ACCUMULATE","BUY","STRONG_BUY","WAIT","REDUCE","SELL"):
        variant=copy.deepcopy(state);variant["decision"]["long_term_decision"]=decision
        messages[decision]=decision_message(variant)
    for event in ("BUY_ZONE_1_REACHED","INVALIDATION","REGIME_CHANGE","CAPITULATION","DATA_WARNING"):
        messages[event]=event_message(event,state)
    result={name:{"dry_run":True,"length":len(message),"sha256":hashlib.sha256(message.encode()).hexdigest(),"execution":"DISABLED"} for name,message in messages.items()}
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
