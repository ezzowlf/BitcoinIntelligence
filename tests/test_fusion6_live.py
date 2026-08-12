import json,sqlite3
import pandas as pd
import pytest
from bitcoin_cycle_analyzer.fusion_live import Fusion6ForwardLedger
from bitcoin_cycle_analyzer.event_evidence import PointInTimeEventDatabase
from bitcoin_cycle_analyzer.calendar_research import complete_calendar_study,black_friday_finding
from bitcoin_cycle_analyzer.fusion_alerts import FusionAlertLedger,relevant_changes
from bitcoin_cycle_analyzer.telegram.client import TelegramClient
from bitcoin_cycle_analyzer.telegram.setup import discover_chats,masked_token,save_allowlist,load_allowlist

def state(**kw):
    base={"timing":"WAIT","rare_buy":"BUY_ZONE","distribution":"WATCH","risk":"CAUTION","new_entry":"WAIT","active_historical_patterns":[]};base.update(kw);return base

def test_first_true_forward_snapshot_is_strict_and_append_only(tmp_path):
    ledger=Fusion6ForwardLedger(tmp_path/"live.db","2026-08-09T21:31:09Z");payload={"fusion_6":state(),"execution":"DISABLED"}
    with pytest.raises(ValueError):ledger.append_snapshot("2026-08-09T21:31:09Z",100,payload)
    first=ledger.append_snapshot("2026-08-10T01:00:00Z",101,payload);assert first["first_true"] and first["marker"]=="FIRST_TRUE_FUSION6_FORWARD_SNAPSHOT"
    assert not ledger.append_snapshot("2026-08-10T01:00:00Z",101,payload)["inserted"]
    with pytest.raises(ValueError):ledger.append_snapshot("2026-08-10T01:00:00Z",101,{"changed":True})

def test_outcome_maturation_never_changes_snapshot(tmp_path):
    ledger=Fusion6ForwardLedger(tmp_path/"live.db","2026-01-01T00:00Z");snap=ledger.append_snapshot("2026-01-02T00:00Z",100,{"fusion_6":state()})
    idx=pd.date_range("2026-01-02",periods=100,freq="4h",tz="UTC");prices=pd.DataFrame({"close":range(100,200)},index=idx)
    assert ledger.mature_outcomes(prices,idx[20])>=3;assert ledger.mature_outcomes(prices,idx[20])==0
    with sqlite3.connect(ledger.path) as db:assert db.execute("SELECT price FROM fusion_snapshots WHERE id=?",(snap["id"],)).fetchone()[0]==100

def test_watched_state_transitions_are_separate_rows(tmp_path):
    ledger=Fusion6ForwardLedger(tmp_path/"live.db","2026-01-01T00:00Z");snap=ledger.append_snapshot("2026-01-02T00:00Z",100,{"fusion_6":state()})
    rows=ledger.append_transitions(snap["id"],"2026-01-02T00:00Z",state(),state(timing="CONFIRMING",rare_buy="STRONG_BUY",risk="HIGH_RISK"));assert {x["field"] for x in rows}=={"timing","rare_buy","risk"}

class Response:
    def __init__(self,payload):self.payload=payload
    def raise_for_status(self):pass
    def json(self):return self.payload
class Session:
    def get(self,url,**kwargs):
        return Response({"ok":True,"result":{"id":7,"username":"bot"}} if url.endswith("getMe") else {"ok":True,"result":[{"message":{"text":"/start","chat":{"id":42,"first_name":"A"}}},{"message":{"text":"hello","chat":{"id":99}}}]})

def test_telegram_setup_masks_token_and_builds_allowlist(tmp_path):
    me,chats=discover_chats("123456:SECRET",Session());assert me["id"]==7 and [x["chat_id"] for x in chats]==["42"] and "SECRET" not in masked_token("123456:SECRET")
    path=tmp_path/"allow.json";saved=save_allowlist(path,["42"],me);assert saved["token"]=="NOT_STORED" and load_allowlist(path)=={"42"}
    assert TelegramClient.allowlisted_command({"message":{"text":"/fusion","chat":{"id":42}}},{"42"})=="/fusion"
    assert TelegramClient.allowlisted_command({"message":{"text":"/fusion","chat":{"id":99}}},{"42"}) is None

def test_alert_dedup_and_relevant_changes(tmp_path):
    events=relevant_changes(state(),state(timing="CONFIRMING",rare_buy="STRONG_BUY"));assert events==["BUY_TIMING_CONFIRMING","RARE_BUY_UPGRADE"]
    ledger=FusionAlertLedger(tmp_path/"alerts.db");assert ledger.append("t",events[0],{})["inserted"] and not ledger.append("t",events[0],{})["inserted"]

def test_event_pit_provenance_and_reaction(tmp_path):
    db=PointInTimeEventDatabase(tmp_path/"events.db");event={"event_time":"2020-01-01T00:00Z","first_known_at":"2020-01-01T01:00Z","available_at":"2020-01-01T01:05Z","source_url":"https://example.com/a","source_name":"Primary","source_quality":"PRIMARY","category":"FED","headline":"Release"};db.append(event)
    assert db.as_of("2020-01-01T01:04Z").empty and len(db.as_of("2020-01-01T01:05Z"))==1
    bad={**event,"headline":"Bad","available_at":"2020-01-01T00:30Z"}
    with pytest.raises(ValueError):db.append(bad)
    idx=pd.date_range("2019-12-30",periods=900,freq="h",tz="UTC");assert db.compute_reactions(pd.DataFrame({"close":range(100,1000)},index=idx))>0

def test_calendar_and_black_friday_are_deterministic():
    idx=pd.date_range("2011-01-01","2025-12-31",freq="D",tz="UTC");frame=pd.DataFrame({"close":100*(1+pd.Series(range(len(idx)),index=idx)/10000),"low":99},index=idx)
    study=complete_calendar_study(frame);finding=black_friday_finding(frame)
    assert len(study["months"])==12 and set(study["boundaries"])=={"month_start","month_end","quarter_start","quarter_end","year_start","year_end"}
    assert finding["samples"]>=10 and finding["conclusion"] in {"SUPPORTED","NOT_SUPPORTED"}

def test_research_next_is_isolated_from_snapshots(tmp_path):
    ledger=Fusion6ForwardLedger(tmp_path/"live.db","2026-01-01T00:00Z");ledger.add_research_next("2026-01-02T00:00Z","candidate",{"x":1})
    assert ledger.health()["research_next_candidates"]==1 and ledger.health()["fusion_snapshots"]==0
