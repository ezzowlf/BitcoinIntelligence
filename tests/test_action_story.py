import pandas as pd
import pytest

from bitcoin_cycle_analyzer.action_story import (
    translate_decision, translate_macro_action, translate_entry_status,
    zone_message_de, what_must_happen_de, why_text_de, why_not_now_de,
    buy_playbook_de, elliott_roadmap_de, event_relevance_de,
    ELLIOTT_BASICS_DE, DECISION_LABELS_DE, _ROADMAP_AFTER_DE,
)
from bitcoin_cycle_analyzer.decision_intelligence.decision_engine import DECISION_STATES
from bitcoin_cycle_analyzer.decision_intelligence.cycle_elliott_context import CYCLE_BUCKETS


# ---------------------------------------------------------------- German labels (Section 1)

def test_every_canonical_decision_state_has_a_german_label():
    for state in DECISION_STATES:
        assert state in DECISION_LABELS_DE
        assert DECISION_LABELS_DE[state] != state  # actually translated, not a passthrough


def test_translate_decision_falls_back_gracefully_for_unknown_state():
    assert translate_decision("SOMETHING_NEW") == "SOMETHING_NEW"


def test_translate_macro_action_covers_the_three_macro7_actions():
    for action in ("ACCUMULATE", "REDUCE", "HOLD"):
        assert translate_macro_action(action) != action or action == "HOLD"  # HOLD->HALTEN below
    assert translate_macro_action("HOLD") == "HALTEN"


def test_translate_entry_status_is_german_not_a_raw_enum():
    assert translate_entry_status("WAITING_FOR_CONFIRMATION") == "Noch kein Einstieg bestätigt"
    assert "_" not in translate_entry_status("WAITING_FOR_CONFIRMATION")


# ---------------------------------------------------------------- Zone missing message (explicit, never silent)

def test_zone_message_when_no_zone_is_explicit_not_silent():
    msg = zone_message_de(None)
    assert msg == "Aktuell keine gültige Kaufzone."


def test_zone_message_when_zone_active_shows_concrete_numbers():
    zone = {"lower": 62500.0, "upper": 64800.0, "zone_type": "BUY_ZONE"}
    msg = zone_message_de(zone)
    assert "62.500" in msg.replace(",", ".") or "62,500" in msg
    assert "64.800" in msg.replace(",", ".") or "64,800" in msg


# ---------------------------------------------------------------- Golden UI scenarios (Section 3/25)

def _fake_decision_intel(decision, zone=None, entry_status="NOT_CONFIRMED", invalidation=55000.0, targets=None, elliott_bucket="LATE_BEAR"):
    return {
        "decision": decision,
        "cycle_bucket": "LATE_BEAR",
        "active_zone": zone,
        "entry_status": entry_status,
        "invalidation_level": invalidation,
        "targets": targets or [{"id": "T1", "price": 68000.0, "why": "resistance"}],
        "evidence_agreement": {"supporting_count": 3, "contradicting_count": 0, "supporting_families": ["CYCLE", "STRUCTURE", "VALUATION"], "contradicting_families": []},
        "confirmation": {"triggers": {"weekly_reclaim": {"met": False, "description": "x"}, "higher_low": {"met": True, "description": "y"}}},
        "playbooks_matched": [{"name": "RECOVERY_ENTRY"}],
        "risk_state": "LOW",
        "elliott_structure": {"cycle_bucket": elliott_bucket, "engine_primary": "Possible macro wave 4 completion", "consistency": "CONSISTENT"},
    }


@pytest.mark.parametrize("decision", list(DECISION_STATES))
def test_golden_scenario_translates_without_raising_for_every_decision_state(decision):
    zone = {"lower": 62500.0, "upper": 64800.0, "zone_type": "BUY_ZONE"}
    di = _fake_decision_intel(decision, zone=zone, entry_status="CONFIRMED" if decision in ("BUY", "STRONG_BUY") else "NOT_CONFIRMED")
    label = translate_decision(di["decision"])
    assert label and label != ""
    zmsg = zone_message_de(di["active_zone"])
    assert zmsg
    must_happen = what_must_happen_de(di["confirmation"])
    assert "missing" in must_happen
    fake_explanation = {"conclusion": "test"}
    why = why_text_de(di, fake_explanation)
    assert translate_decision(decision) in why  # the decision itself is always named in the story


def test_wait_scenario_has_a_why_not_now_explanation():
    di = _fake_decision_intel("WAIT", zone={"lower": 60000.0, "upper": 62000.0, "zone_type": "WATCH_ZONE"})
    text = why_not_now_de(di)
    assert "interessant" in text.lower() or "keine" in text.lower()


def test_wait_scenario_without_any_zone_still_gets_a_reason():
    di = _fake_decision_intel("WAIT", zone=None)
    text = why_not_now_de(di)
    assert len(text) > 20


def test_buy_scenario_has_full_playbook_fields():
    zone = {"lower": 62500.0, "upper": 64800.0, "zone_type": "BUY_ZONE"}
    di = _fake_decision_intel("BUY", zone=zone, entry_status="CONFIRMED")
    pb = buy_playbook_de(di)
    for field in ("entry_type", "entry_zone", "why", "invalidation", "first_target", "risk", "dont_chase_above"):
        assert field in pb
    assert pb["invalidation"] == "$55,000"
    assert pb["first_target"] == "$68,000"


def test_strong_buy_scenario_also_produces_a_playbook():
    zone = {"lower": 62500.0, "upper": 64800.0, "zone_type": "STRONG_BUY_ZONE"}
    di = _fake_decision_intel("STRONG_BUY", zone=zone, entry_status="CONFIRMED")
    pb = buy_playbook_de(di)
    assert pb["entry_zone"] != "—"


def test_take_profit_and_high_risk_and_sell_scenarios_do_not_crash():
    for decision in ("TAKE_PROFIT", "HIGH_RISK", "SELL"):
        di = _fake_decision_intel(decision, zone=None, entry_status="NOT_APPLICABLE")
        translate_decision(di["decision"])
        why_not_now_de(di)  # must not raise even for non-WAIT states


# ---------------------------------------------------------------- No invented Elliott wave (Section 10/23)

def test_elliott_roadmap_only_uses_the_engines_own_hypothesis_text():
    ctx = {"cycle_bucket": "DEEP_BEAR_BOTTOM_SEARCH", "engine_primary": "Possible macro wave 4 completion / recovery watch", "consistency": "CONSISTENT"}
    roadmap = elliott_roadmap_de(ctx)
    assert roadmap["current_hypothesis"] == ctx["engine_primary"]  # never replaced with an invented label


def test_elliott_roadmap_covers_every_known_cycle_bucket():
    for bucket in CYCLE_BUCKETS:
        assert bucket in _ROADMAP_AFTER_DE


def test_elliott_roadmap_carries_the_known_limitation_disclaimer():
    ctx = {"cycle_bucket": "LATE_BEAR", "engine_primary": "x", "consistency": "CONSISTENT"}
    roadmap = elliott_roadmap_de(ctx)
    assert "nicht möglich" in roadmap["limitation"].lower() or "hinweis" in roadmap["limitation"].lower()


def test_elliott_roadmap_flags_conflict_when_engine_says_conflict():
    ctx = {"cycle_bucket": "LATE_BEAR", "engine_primary": "x", "consistency": "CONFLICT"}
    roadmap = elliott_roadmap_de(ctx)
    assert "NICHT" in roadmap["consistency_note"]


def test_elliott_basics_mentions_only_the_five_wave_impulse_and_abc_correction():
    assert "1" in ELLIOTT_BASICS_DE and "5" in ELLIOTT_BASICS_DE
    assert "A" in ELLIOTT_BASICS_DE and "C" in ELLIOTT_BASICS_DE
    assert "Hypothese" in ELLIOTT_BASICS_DE or "hypothese" in ELLIOTT_BASICS_DE.lower()


# ---------------------------------------------------------------- Strategic vs tactical separation (Section 22/23)

def test_strategic_and_tactical_labels_can_legitimately_differ_without_being_a_bug():
    # ACCUMULATE (strategic, macro7) + WAIT (tactical, decision_intelligence) is a valid,
    # intentional combination -- the translation layer must render both, not force agreement.
    strategic = translate_macro_action("ACCUMULATE")
    tactical = translate_decision("WAIT")
    assert strategic == "AKKUMULATION INTERESSANT"
    assert tactical == "WARTEN"
    assert strategic != tactical


# ---------------------------------------------------------------- Event relevance / AI fallback (Section 29, 17)

def test_event_relevance_with_no_events_is_explicit():
    text = event_relevance_de(pd.DataFrame())
    assert "keine relevanten" in text.lower()


def test_event_relevance_with_events_states_it_does_not_change_decision_by_default():
    df = pd.DataFrame({"headline": ["x"], "event_time": ["2024-01-01"]})
    text = event_relevance_de(df, decision_changes=False)
    assert "nicht" in text.lower()


def test_action_story_module_never_imports_ai():
    import inspect
    from bitcoin_cycle_analyzer import action_story
    src = inspect.getsource(action_story)
    assert "openai" not in src.lower() and "BitcoinAIRouter" not in src


# ---------------------------------------------------------------- No decision side effect (consistent with drawing/event passes)

def test_action_story_module_never_imported_by_decision_intelligence():
    import inspect
    from bitcoin_cycle_analyzer import decision_intelligence
    import bitcoin_cycle_analyzer.decision_intelligence.decision_engine as de
    for module in (decision_intelligence, de):
        src = inspect.getsource(module)
        assert "action_story" not in src
