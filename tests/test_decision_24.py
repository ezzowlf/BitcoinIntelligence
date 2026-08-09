from __future__ import annotations
import sqlite3
import pandas as pd
import pytest
from bitcoin_cycle_analyzer.decision.engine import build_decision
from bitcoin_cycle_analyzer.decision.zones import build_zones
from bitcoin_cycle_analyzer.forward.ledger import ForwardLedger
from bitcoin_cycle_analyzer.forward.frozen import FrozenChampion
from bitcoin_cycle_analyzer.telegram import TelegramDecisionBot
from bitcoin_cycle_analyzer.telegram.formatter import command_message


def state(value="HIGH_VALUE",timing="WAIT",regime="BEAR",tail="NORMAL",quality=True,no_edge=False):
    precision={"timestamp":pd.Timestamp("2026-08-10",tz="UTC"),"value":{"state":value,"score":70,"historical_percentile":60,"inputs":{"ath_drawdown":-.4}},
      "regime":{"current":regime,"model_agreement":.4,"relative_support":{"BEAR":40},"stability":"LOW","transition_status":"CONFIRMING"},
      "timing":{"state":timing,"score":0,"missing_conditions":["structure_reclaim"]},"risk":{"tail_state":tail,"horizons":{"7d":30,"30d":40,"90d":50},"volatility_percentile":20,"capitulation":"NONE"},
      "data_health":{"critical_healthy":quality,"score":76},"confluence":{"independent_groups":5,"unavailable":["macro"]},"evidence":{"score":60,"label":"MODERATE"},
      "uncertainty":{"state":"HIGH"},"no_edge":no_edge,"market_state":"VALUE_WITHOUT_CONFIRMATION","system_conclusion":"ATTRACTIVE_VALUE_BUT_NO_CONFIRMED_ENTRY_EDGE",
      "cycle":{"primary_regime":"TRANSITION"},"analogues":{"independent_episodes":12},"config_hash":"x"}
    return {"precision":precision,"modules":{"onchain":{},"derivatives":{}},"decision":None}
def technical(trend="bearish"):
    return {"price":65000,"structure":{"trend":trend},"confluence_zones":[{"low":62000,"high":63000,"center":62500,"count":7},{"low":59000,"high":60500,"center":60000,"count":5},{"low":68000,"high":69000,"center":68500,"count":4}]}


def decide(**kwargs):
    s=state(**kwargs);s["decision"]=build_decision(s,technical());return s


def test_long_term_and_swing_are_separate_accumulate_wait():
    result=decide()["decision"];assert result["long_term_decision"]=="ACCUMULATE" and result["swing_decision"]=="WAIT"
    assert result["accumulation_mode"]=="SMALL_ACCUMULATION"


def test_buy_requires_confirmation_and_non_bear_regime():
    assert decide(timing="CONFIRMED",regime="RECOVERY")["decision"]["long_term_decision"]=="BUY"
    assert decide(timing="WAIT",regime="RECOVERY")["decision"]["long_term_decision"]!="BUY"


def test_sell_has_own_evidence_and_is_not_inverse_buy():
    ordinary=decide(value="EXPENSIVE",timing="WAIT",regime="DISTRIBUTION")["decision"]
    assert ordinary["swing_decision"]=="REDUCE" and ordinary["swing_decision"]!="SELL"


def test_no_edge_and_data_unreliable():
    assert decide(value="FAIR",no_edge=True)["decision"]["swing_decision"]=="NO_EDGE"
    unreliable=decide(quality=False)["decision"];assert unreliable["long_term_decision"]=="DATA_UNRELIABLE" and unreliable["swing_decision"]=="DATA_UNRELIABLE"


def test_confidence_upgrade_downgrade_and_execution():
    result=decide()["decision"];assert result["confidence"]=="MODERATE"
    assert "structure_reclaim" in result["next_upgrade_conditions"] and "weekly_support_break" in result["next_downgrade_conditions"]
    assert result["execution"]=="DISABLED"


def test_zone_generation_is_existing_confluence_only():
    zones=build_zones(65000,technical());assert zones["buy_zone_1"]["low"]==62000 and zones["buy_zone_1"]["confidence"]=="HIGH"
    assert zones["resistance"]["low"]==68000 and zones["invalidation"]["below"]==59000


def test_telegram_commands_and_research_labels():
    current=decide();bot=TelegramDecisionBot(dry_run=True)
    for command in ("/btc","/decision","/value","/timing","/risk","/cycle","/zones","/why","/health"):
        assert bot.command(command,current)
    assert "RESEARCH" in bot.command("/risk",current) and "DISABLED" in bot.command("/decision",current)


def test_telegram_dedup_only_state_changes():
    bot=TelegramDecisionBot();previous=decide();assert bot.alert(previous,previous) is None
    current=decide(timing="CONFIRMED",regime="RECOVERY");alert=bot.alert(current,previous);assert alert and alert["dry_run"] is True
    assert bot.alert(current,previous) is None


def test_telegram_alert_is_persisted_in_forward_ledger(tmp_path):
    ledger=ForwardLedger(tmp_path/"forward.db");bot=TelegramDecisionBot(ledger=ledger)
    previous=decide();current=decide(timing="CONFIRMED",regime="RECOVERY")
    assert bot.alert(current,previous) and ledger.health()["alerts"]==1


def test_intrabar_alert_is_preview_and_not_persisted(tmp_path):
    ledger=ForwardLedger(tmp_path/"forward.db");bot=TelegramDecisionBot(ledger=ledger)
    previous=decide();current=decide(timing="CONFIRMED",regime="RECOVERY")
    current["precision"]["candle_status"]="PREVIEW"
    alert=bot.alert(current,previous)
    assert alert["confirmed"] is False and alert["message"].startswith("PREVIEW")
    assert ledger.health()["alerts"]==0


def test_forward_cutoff_append_only_and_alert_ledger(tmp_path):
    ledger=ForwardLedger(tmp_path/"forward.db");current=decide();current["decision"]["zones"]["current_price"]=65000
    payload=ledger.append_snapshot(current,"commit","hash");assert payload["engine_version"]=="2.3-FROZEN"
    with pytest.raises(sqlite3.IntegrityError):ledger.append_snapshot(current,"commit","hash")
    ledger.append_alert("a1",current["precision"]["timestamp"],"ACCUMULATE","ACCUMULATE",{"x":1});assert ledger.health()["alerts"]==1
    too_early=decide();too_early["precision"]["timestamp"]=pd.Timestamp("2026-08-09",tz="UTC")
    with pytest.raises(ValueError):ledger.append_snapshot(too_early,"commit","hash")


def test_database_triggers_reject_snapshot_mutation(tmp_path):
    ledger=ForwardLedger(tmp_path/"forward.db");current=decide();current["decision"]["zones"]["current_price"]=65000;ledger.append_snapshot(current,"c","h")
    with sqlite3.connect(ledger.path) as con:
        with pytest.raises(sqlite3.IntegrityError):con.execute("UPDATE frozen_snapshots SET btc_price=1")


def test_frozen_model_detects_mutation(tmp_path):
    path=tmp_path/"frozen.json";path.write_text('{"model_id":"2.3-FROZEN","execution":"DISABLED"}',encoding="utf-8");frozen=FrozenChampion(path);assert frozen.assert_immutable()
    frozen.payload["execution"]="ENABLED"
    with pytest.raises(RuntimeError):frozen.assert_immutable()
