from types import SimpleNamespace
import pandas as pd
import requests
import sqlite3
import pytest

from bitcoin_cycle_analyzer.ai import BitcoinAIRouter
from bitcoin_cycle_analyzer.elliott_wave import analyze_elliott_intelligence
from bitcoin_cycle_analyzer.live import MT5MarketDataProvider
from bitcoin_cycle_analyzer.cycles import analyze_cycle_history
from bitcoin_cycle_analyzer.elliott_validation import replay_elliott


def _frame(n=900):
    idx=pd.date_range("2020-01-01",periods=n,tz="UTC")
    close=pd.Series([100+i*.1+20*((i%120)/120) for i in range(n)],index=idx)
    return pd.DataFrame({"open":close,"high":close+2,"low":close-2,"close":close,"volume":1},index=idx)


def _state():
    return {"master":{"decision":{"long_term_action":"ACCUMULATE","new_entry_action":"WAIT","risk_action":"CAUTION","production_signal":"NO_PRODUCTION_SIGNAL"},"state":{"btc_price":100.0}}}


def test_ai_disabled_is_deterministic_fallback(tmp_path):
    result=BitcoinAIRouter(values={"OPENAI_ENABLED":"false"},cache_dir=tmp_path).explain("NANO",_state())
    assert result.status=="FALLBACK" and "MASTER" in result.text


def test_model_discovery_without_key_is_honest(tmp_path):
    result=BitcoinAIRouter(values={},cache_dir=tmp_path).discover_models()
    assert result["status"]=="UNAVAILABLE_NO_API_KEY" and result["nano"]==[]


def test_contradiction_and_hallucinated_price_guard(tmp_path):
    router=BitcoinAIRouter(values={},cache_dir=tmp_path)
    assert router._guard("Jetzt kaufen",_state())[0] is False
    assert router._guard("BTC steht bei $999",_state())[1]=="HALLUCINATED_PRICE"
    assert router._guard("Die Wahrscheinlichkeit steigt.",_state())[1]=="UNSUPPORTED_PROBABILITY"
    assert router._guard("Elliott Invalidation 12345",_state())[1]=="ELLIOTT_LEVEL_NOT_GROUNDED"


def test_raw_responses_output_and_real_model_defaults(tmp_path):
    router=BitcoinAIRouter(values={},cache_dir=tmp_path)
    payload={"output":[{"content":[{"type":"output_text","text":"Grounded result"}]}]}
    assert router._output_text(payload)=="Grounded result"
    assert router.models["NANO"]=="gpt-4.1-nano"
    assert router.models["ANALYSIS"]=="gpt-5.1"


def test_grounding_keeps_wait_and_dormant_scenarios(tmp_path):
    state=_state();state["macro7"]={"actions":{"long_swing":"WAIT"},"scenarios":[{"name":"DEEP BEAR","status":"DORMANT"}]}
    grounded=BitcoinAIRouter(values={},cache_dir=tmp_path).grounded_state(state)
    assert grounded["macro7"]["actions"]["long_swing"]=="WAIT"
    assert grounded["macro7"]["scenarios"][0]["status"]=="DORMANT"
    assert grounded["execution"]=="DISABLED"


class FakeMT5:
    TIMEFRAME_H4=4;TIMEFRAME_D1=1;TIMEFRAME_W1=7;TIMEFRAME_MN1=30
    def initialize(self,**kwargs):return True
    def symbols_get(self):return [SimpleNamespace(name="BTCUSD")]
    def symbol_select(self,*args):return True
    def symbol_info_tick(self,symbol):return SimpleNamespace(bid=99,ask=101,time=1_700_000_000)
    def copy_rates_from_pos(self,symbol,timeframe,start,count):
        return [{"time":1_700_000_000,"open":1,"high":2,"low":.5,"close":1.5,"tick_volume":5}]
    def account_info(self):return SimpleNamespace(server="private-server")
    def shutdown(self):pass
    def terminal_info(self):return SimpleNamespace(connected=True)
    def version(self):return (500,6090,"date")


def test_mt5_read_only_confirmed_candles_and_provenance():
    provider=MT5MarketDataProvider(FakeMT5(),{"MT5_ENABLED":"true"})
    assert provider.connect().status=="ONLINE"
    assert provider.tick()["mid"]==100
    assert len(provider.confirmed_candles("4h"))==1
    assert provider.provenance()["execution"]=="DISABLED"
    assert not hasattr(provider,"order_send")
    preview=provider.intrabar_preview("4h")
    assert preview["status"]=="PREVIEW" and preview["confirmed"] is False


def test_mt5_disconnect_and_stale_tick_never_confirm_intrabar():
    disabled=MT5MarketDataProvider(FakeMT5(),{"MT5_ENABLED":"false"})
    assert disabled.connect().status=="DISABLED" and disabled.confirmed_candles("1d").empty
    connected=MT5MarketDataProvider(FakeMT5(),{"MT5_ENABLED":"true"});connected.connect()
    assert connected.tick()["freshness"]=="STALE"
    assert connected.intrabar_preview("1d")["confirmed"] is False


def test_elliott_is_pit_research_and_support_not_probability():
    result=analyze_elliott_intelligence(_frame())
    assert result["status"]=="RESEARCH_ONLY"
    assert result["scenario_support_is_probability"] is False
    assert all(x["confirmed_at"] <= result["evidence"]["cutoff"] for x in result["evidence"]["confirmed_swings"])


def test_cycle_history_has_provenance():
    result=analyze_cycle_history(_frame())
    assert result["status"]=="RESEARCH_ONLY"
    assert result["provenance"]["price_source"].startswith("BITSTAMP")
    assert "halving_normalized" in result and "bottom_recovery_normalized" in result

def test_tick_freshness_and_disagreement_states():
    assert MT5MarketDataProvider.divergence(100,100)["status"]=="NORMAL"
    assert MT5MarketDataProvider.divergence(110,100)["status"]=="CRITICAL"

def test_usage_ledger_cache_and_missing_data_guard(tmp_path):
    router=BitcoinAIRouter(values={},cache_dir=tmp_path);router._record("test",10,5,False,"NANO",.01)
    assert router.usage_today()["input_tokens"]==10
    state=_state();state["modules"]={"etf":{"status":"UNAVAILABLE"}}
    assert router._guard("ETF inflows are positive",state)[1]=="CLAIM_FROM_MISSING_DATA"
    with sqlite3.connect(router.ledger_path) as db:
        assert {"state_hash","api_status","guard_status","fallback"}<={row[1] for row in db.execute("PRAGMA table_info(usage)")}


class RetryResponse:
    def __init__(self,status):self.status_code=status


class RetrySession:
    def __init__(self,items):self.items=list(items);self.calls=0
    def get(self,*args,**kwargs):
        self.calls+=1;item=self.items.pop(0)
        if isinstance(item,Exception):raise item
        return RetryResponse(item)


@pytest.mark.parametrize("items,expected_calls,expected_status",[
    ([429,429,200],3,200),([520,200],2,200),([401],1,401),
])
def test_api_retry_taxonomy(tmp_path,items,expected_calls,expected_status):
    session=RetrySession(items);router=BitcoinAIRouter(values={},session=session,cache_dir=tmp_path)
    response=router._request("get","https://example.invalid",timeout=1)
    assert response.status_code==expected_status and session.calls==expected_calls


def test_api_timeout_is_bounded(tmp_path):
    session=RetrySession([requests.Timeout(),requests.Timeout(),requests.Timeout()]);router=BitcoinAIRouter(values={},session=session,cache_dir=tmp_path)
    with pytest.raises(requests.Timeout):router._request("get","https://example.invalid",timeout=1)
    assert session.calls==3


class ExplainResponse:
    def __init__(self,status,payload):self.status_code=status;self.ok=status<400;self.payload=payload
    def json(self):return self.payload


class ExplainSession:
    def __init__(self,response):self.response=response;self.calls=0
    def post(self,*args,**kwargs):self.calls+=1;return self.response


def _ai_state():
    state=_state();state["macro7"]={"actions":{"long_swing":"WAIT"},"scenarios":[],"elliott":{},"zones":{}}
    return state


def test_model_unavailable_and_invalid_response_fall_back(tmp_path):
    values={"OPENAI_ENABLED":"true","OPENAI_API_KEY":"test","OPENAI_NANO_MODEL":"gpt-4.1-nano"}
    missing=BitcoinAIRouter(values=values,session=ExplainSession(ExplainResponse(404,{"error":{"code":"model_not_found"}})),cache_dir=tmp_path/"missing").explain("NANO",_ai_state(),bypass_cache=True)
    assert missing.status=="FALLBACK" and missing.reason=="HTTP_404:model_not_found"
    invalid=BitcoinAIRouter(values=values,session=ExplainSession(ExplainResponse(200,{"id":"x","output":[],"usage":{}})),cache_dir=tmp_path/"invalid").explain("NANO",_ai_state(),bypass_cache=True)
    assert invalid.status=="REJECTED_FALLBACK" and invalid.reason=="EMPTY_RESPONSE"


def test_daily_cost_limit_blocks_model_but_not_engine(tmp_path):
    values={"OPENAI_ENABLED":"true","OPENAI_API_KEY":"test","OPENAI_MAX_DAILY_COST":"0.001"}
    router=BitcoinAIRouter(values=values,cache_dir=tmp_path);router._record("gpt-5.1",100,100,False,"ANALYSIS",.01)
    result=router.explain("ANALYSIS",_ai_state(),deep=True)
    assert result.status=="FALLBACK" and result.reason=="DAILY_COST_LIMIT_REACHED"
    assert "MASTER" in result.text

def test_elliott_replay_is_pit_and_reports_revisions():
    ledger,stats=replay_elliott(_frame(1200),frequency="90D")
    assert stats["pit_violations"]==0 and stats["status"]=="RESEARCH_ONLY"
    assert (ledger.max_confirmed_at.dropna()<=ledger.loc[ledger.max_confirmed_at.notna(),"timestamp"]).all()
