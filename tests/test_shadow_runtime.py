import json,sqlite3
from pathlib import Path
from bitcoin_cycle_analyzer.forward import ForwardLedger
from bitcoin_cycle_analyzer.runtime import RuntimeSettings
from bitcoin_cycle_analyzer.telegram import TelegramClient,TelegramDecisionBot
from bitcoin_cycle_analyzer.telegram.events import detect_events,event_message
from test_decision_24 import decide


def test_missing_telegram_credentials_forces_dry_run(monkeypatch,tmp_path):
    monkeypatch.setenv("BITCOIN_HOME",str(tmp_path));monkeypatch.setenv("TELEGRAM_ENABLED","true");monkeypatch.setenv("TELEGRAM_DRY_RUN","false");monkeypatch.delenv("TELEGRAM_BOT_TOKEN",raising=False);monkeypatch.delenv("TELEGRAM_CHAT_ID",raising=False)
    cfg=RuntimeSettings.from_env(tmp_path);assert cfg.telegram_dry_run is True and cfg.execution=="DISABLED"

def test_execution_enable_attempt_is_hard_blocked(monkeypatch,tmp_path):
    monkeypatch.setenv("BITCOIN_EXECUTION_ENABLED","true")
    import pytest
    with pytest.raises(RuntimeError,match="must remain DISABLED"):RuntimeSettings.from_env(tmp_path)

def test_vps_env_file_is_loaded_without_dotenv(monkeypatch,tmp_path):
    monkeypatch.delenv("TELEGRAM_CHAT_ID",raising=False);monkeypatch.delenv("BITCOIN_EXECUTION_ENABLED",raising=False)
    (tmp_path/".env").write_text("TELEGRAM_CHAT_ID=42\nTELEGRAM_DRY_RUN=true\n",encoding="utf-8")
    assert RuntimeSettings.from_env(tmp_path).telegram_chat_id=="42"


def test_telegram_client_dry_run_never_calls_network():
    class NoNetwork:
        def post(self,*args,**kwargs):raise AssertionError("network called")
    assert TelegramClient(None,None,enabled=True,dry_run=False,session=NoNetwork()).send("x")["status"]=="DRY_RUN"


def test_persistent_alert_dedup_survives_restart(tmp_path):
    db=tmp_path/"forward.db";previous=decide();current=decide(timing="CONFIRMED",regime="RECOVERY")
    assert TelegramDecisionBot(ledger=ForwardLedger(db)).alert(current,previous)
    assert TelegramDecisionBot(ledger=ForwardLedger(db)).alert(current,previous) is None


def test_alert_schema_contains_delivery_audit_fields(tmp_path):
    ledger=ForwardLedger(tmp_path/"forward.db")
    with sqlite3.connect(ledger.path) as con:columns={row[1] for row in con.execute("PRAGMA table_info(decision_alerts)")}
    assert {"message_hash","market_state","btc_price","telegram_delivery_status"}<=columns


def test_unauthorized_telegram_chat_is_ignored():
    client=TelegramClient("token","42",enabled=True,dry_run=False)
    assert client.authorized_command({"message":{"chat":{"id":7},"text":"/decision"}}) is None
    assert client.authorized_command({"message":{"chat":{"id":42},"text":"/decision"}})=="/decision"


def test_zone_and_invalidation_are_events_not_sell():
    previous=decide();current=decide();zone=current["decision"]["zones"]["buy_zone_1"]
    previous["decision"]["zones"]["current_price"]=zone["high"]+100
    current["decision"]["zones"]["current_price"]=(zone["low"]+zone["high"])/2
    assert "BUY_ZONE_1_REACHED" in detect_events(current,previous)
    level=current["decision"]["zones"]["invalidation"]["below"]
    previous["decision"]["zones"]["current_price"]=level+1;current["decision"]["zones"]["current_price"]=level-1
    assert "INVALIDATION" in detect_events(current,previous)
    assert "not automatically a SELL" in event_message("INVALIDATION",current)


def test_all_required_dry_run_message_types_render():
    current=decide()
    for event in ("BUY_ZONE_1_REACHED","INVALIDATION","REGIME_CHANGE","CAPITULATION","DATA_WARNING"):
        message=event_message(event,current);assert "2.3-FROZEN" in message and "DISABLED" in message
