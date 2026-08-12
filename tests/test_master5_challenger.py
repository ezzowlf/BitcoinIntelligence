from pathlib import Path
import json
import hashlib
import pandas as pd
import pytest

from bitcoin_cycle_analyzer.master5 import Master5ShadowLedger,build_master5_signal_book,summarize_signal_book,challenger_state_change
from bitcoin_cycle_analyzer.core.analyzer import analyze_intelligence
from bitcoin_cycle_analyzer.config import load_config

@pytest.fixture(scope="module")
def price_frame():
    import numpy as np
    rng=np.random.default_rng(9);idx=pd.date_range("2014-01-01",periods=1800,freq="D",tz="UTC");close=500*np.exp(np.cumsum(rng.normal(.001,.025,len(idx))));spread=close*.02
    return pd.DataFrame({"open":close,"high":close+spread,"low":close-spread,"close":close,"volume":1000},index=idx)

@pytest.fixture(scope="module")
def current_state(price_frame):return analyze_intelligence(price_frame,load_config("config.yaml"))

def test_challenger_is_separate_and_execution_locked(current_state):
    c=current_state["master5_challenger"]
    assert c["model"]=="MASTER_5_0_CHALLENGER" and c["champion_unchanged"] is True
    assert c["execution"]=="DISABLED" and c["openai"]=="NOT_USED_FOR_SIGNALS" and c["elliott"]=="CONTEXT_ONLY_NOT_COUNTED"

def test_rare_buy_and_sell_risk_are_separate(current_state):
    c=current_state["master5_challenger"]
    assert c["buy"]["state"] in {"NO_BUY","WATCH_BUY","BUY_ZONE","STRONG_BUY_CANDIDATE","HISTORICAL_EXTREME"}
    assert c["risk"]["sell_off_risk"] in {"LOW","MODERATE","HIGH","EXTREME"}
    assert c["buy"]["quality_is_probability"] is False

def test_zone_lifecycle_contract(current_state):
    z=current_state["master5_challenger"]["buy"]["zone_lifecycle"]
    assert z["state"] in {"UNAVAILABLE","APPROACHING","ENTERED","REJECTING","RECLAIMED","FAILED","DISTANT"}

def test_historical_book_is_causal_and_frequency_not_forced(price_frame):
    book=build_master5_signal_book(price_frame);summary=summarize_signal_book(book)
    assert not book.empty and (pd.to_datetime(book.timestamp)<=price_frame.index[-1]).all()
    assert summary["method"].startswith("causal features")

def test_shadow_ledger_is_append_only(tmp_path):
    start=pd.Timestamp("2026-08-10",tz="UTC");ledger=Master5ShadowLedger(tmp_path/"shadow.db",start)
    payload={"state":"WATCH_BUY","execution":"DISABLED"};first=ledger.append(start,payload);assert ledger.append(start,payload)==first and ledger.count()==1
    with pytest.raises(ValueError):ledger.append(start,{"state":"BUY_ZONE"})
    with pytest.raises(ValueError):ledger.append(start-pd.Timedelta(seconds=1),payload)

def test_alert_transition_and_dedup_fingerprint(current_state):
    current=json.loads(json.dumps(current_state["master5_challenger"],default=str));previous=json.loads(json.dumps(current));previous["buy"]["state"]="WATCH_BUY";current["buy"]["state"]="BUY_ZONE"
    one=challenger_state_change(previous,current);two=challenger_state_change(previous,current)
    assert one and one["fingerprint"]==two["fingerprint"] and one["execution"]=="DISABLED"

def test_non_alert_transition_is_silent(current_state):
    current=current_state["master5_challenger"]
    assert challenger_state_change(current,current) is None

def test_frozen_definition_exists_after_freeze():
    path=Path("frozen/master_5_0_challenger_frozen.json")
    if path.exists():
        payload=json.loads(path.read_text(encoding="utf-8"));assert payload["execution"]=="DISABLED" and payload["champion"]=="MASTER_3_0_FROZEN"
        for name,expected in payload["code_manifest_sha256"].items():assert hashlib.sha256((Path("src/bitcoin_cycle_analyzer/master5")/name).read_bytes()).hexdigest().upper()==expected
