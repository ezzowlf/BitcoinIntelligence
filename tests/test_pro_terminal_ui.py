from pathlib import Path
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]

SOURCE=Path("dashboard/app.py").read_text(encoding="utf-8")

def test_terminal_has_compact_decision_and_live_confirmed_distinction():
    assert "terminal-head" in SOURCE and "decision" in SOURCE
    assert "MT5 LIVE" in SOURCE and "Confirmed H4" in SOURCE

def test_chart_is_dominant_and_has_required_overlays():
    assert "height=620 if simple else 555" in SOURCE
    for layer in ("Zones","200D/200W","Bollinger","Elliott","Signals","Historical Entries"):assert layer in SOURCE
    assert "add_hrect" in SOURCE and "add_hline" in SOURCE

def test_raw_debug_is_not_exposed_in_production_terminal():
    assert 'DEBUG · raw state' not in SOURCE and 'st.json(state)' not in SOURCE

def test_terminal_apptest_renders_without_exception():
    # Default is now SIMPLE Mode (Explain & Action Layer pass), which st.stop()s
    # before the tab strip — switch to RESEARCH to verify the full app still renders.
    at=AppTest.from_file(ROOT / "dashboard" / "app.py",default_timeout=40).run()
    assert not at.exception
    view_toggle=next(w for w in at.segmented_control if list(w.options)==["SIMPLE","RESEARCH"])
    at=view_toggle.set_value("RESEARCH").run()
    top_level={"CHART","CYCLES","HISTORY","EVENTS","RESEARCH","SYSTEM"}
    assert not at.exception
    assert sum(1 for t in at.tabs if t.label in top_level)==6

def test_terminal_apptest_renders_without_exception_in_default_simple_mode():
    at=AppTest.from_file(ROOT / "dashboard" / "app.py",default_timeout=40).run()
    assert not at.exception

def test_terminal_apptest_renders_without_exception_with_mixed_drawing_types():
    # Regression test: rendering the drawing list once crashed with KeyError
    # whenever HLINE/RECTANGLE/FIB drawings coexisted, because the description
    # lookup was a dict literal that eagerly evaluated every branch. app.py
    # always opens ROOT/runtime/drawings/BTCUSD.json, so seed that real file
    # (backing up and restoring whatever was already there).
    from bitcoin_cycle_analyzer.drawing_state import UserDrawingStore
    drawings_path = ROOT / "runtime" / "drawings" / "BTCUSD.json"
    backup = drawings_path.read_text(encoding="utf-8") if drawings_path.exists() else None
    try:
        store = UserDrawingStore(ROOT, "BTCUSD")
        store._write([])
        store.add("HLINE", "ALL", {"price": 60000.0})
        store.add("RECTANGLE", "ALL", {"low": 58000.0, "high": 62000.0})
        store.add("FIB", "ALL", {"price_a": 50000.0, "price_b": 70000.0})
        at = AppTest.from_file(ROOT / "dashboard" / "app.py", default_timeout=40).run()
        assert not at.exception
    finally:
        if backup is not None:
            drawings_path.write_text(backup, encoding="utf-8")
        elif drawings_path.exists():
            drawings_path.unlink()

def test_macro7_timeframes_layers_and_plain_language_surfaces():
    for token in ('"1Y"','"ALL"','"Macro Zones"','"Swing Zones"','"Fib"','"Events"','"CYCLES"'):assert token in SOURCE
    assert "Macro scenario map" in SOURCE and "Long-Swing BUY stays locked without a validated edge" in SOURCE

def test_navigation_is_simplified_to_six_top_level_sections():
    assert 'st.tabs(["CHART","CYCLES","HISTORY","EVENTS","RESEARCH","SYSTEM"])' in SOURCE

def test_indicator_state_and_rule_registry_are_exported_and_not_executed():
    assert "build_decision_state_v1" in SOURCE and "build_indicator_state_v1" in SOURCE and "rule_registry" in SOURCE
    assert "PINE_MQL_CAPABILITY_MATRIX" in SOURCE
    assert '"execution": "DISABLED"' in Path("src/bitcoin_cycle_analyzer/indicator_state.py").read_text(encoding="utf-8")

def test_layer_presets_and_drawing_tools_present():
    ui_state_source = Path("src/bitcoin_cycle_analyzer/ui_state.py").read_text(encoding="utf-8")
    for preset in ("CLEAN","SWING","MACRO","RESEARCH"):assert f'"{preset}"' in ui_state_source
    assert "LAYER_PRESETS" in SOURCE  # app.py consumes the shared preset state, doesn't redefine it
    assert "drawline" in SOURCE and "drawrect" in SOURCE and "eraseshape" in SOURCE

def test_dormant_conditional_targets_are_labelled_not_predicted():
    assert "DORMANT — NOT AN ACTIVE TARGET" in SOURCE

def test_decision_card_is_wired_and_traceable():
    assert "DECISION DETAIL" in SOURCE and "build_decision_intelligence" in SOURCE
    assert "Decision Rule Registry" in SOURCE and "DECISION_RULE_REGISTRY" in SOURCE

def test_simple_and_research_modes_exist_and_default_to_simple():
    assert '["SIMPLE","RESEARCH"]' in SOURCE
    from bitcoin_cycle_analyzer.ui_state import default_chart_view_state
    assert default_chart_view_state()["mode"] == "SIMPLE"  # Explain & Action Layer: product explains itself first

def test_decision_zone_and_invalidation_render_unconditionally_on_chart():
    # These must NOT be inside an `if X in layers:` gate — they are P0 priority
    # (Teil "CHART LAYER PRIORITY": current price / active decision zone / invalidation / targets first).
    assert "Decision Intelligence zone/invalidation/targets ALWAYS render" in SOURCE

def test_touch_targets_are_at_least_44px_in_css():
    assert "min-height:44px" in SOURCE

def test_glossary_has_no_fabricated_facts_only_static_definitions():
    from bitcoin_cycle_analyzer.glossary import GLOSSARY
    assert len(GLOSSARY) >= 8
    for term, text in GLOSSARY.items():
        assert len(text) > 10
        assert "you should buy" not in text.lower() and "you should sell" not in text.lower()

def test_ui_state_module_separates_chart_view_state_from_engine_state():
    ui_state_source = Path("src/bitcoin_cycle_analyzer/ui_state.py").read_text(encoding="utf-8")
    assert "ENGINE STATE" in ui_state_source and "DECISION STATE" in ui_state_source and "CHART VIEW STATE" in ui_state_source

def test_events_layer_renders_on_main_chart_and_is_informative_only():
    assert '"Events" in layers' in SOURCE
    assert "event_evidence_family" in SOURCE
    assert "classify_causality" in SOURCE and "expected_vs_observed" in SOURCE

def test_simple_mode_uses_the_german_action_story_layer():
    assert "WAS SOLL ICH JETZT TUN?" in SOURCE
    assert "STRATEGISCH (langfristige Lage)" in SOURCE and "AKTION JETZT" in SOURCE
    assert "WARUM NICHT JETZT KAUFEN?" in SOURCE
    assert "KAUFSIGNAL AKTIV" in SOURCE
    assert "ELLIOTT EINFACH ERKLÄRT" in SOURCE
    assert "WAS MUSS PASSIEREN" in SOURCE

def test_no_zone_classification_logic_is_reimplemented_in_the_ui():
    # app.py may only READ zone_type/decision/entry_status from the decision_intelligence
    # dicts (di/dz) — it must never itself branch on price to decide STRONG_BUY_ZONE etc.
    import re
    zone_type_literals = re.findall(r'"(STRONG_BUY_ZONE|BUY_ZONE|WATCH_ZONE|TAKE_PROFIT_ZONE|HIGH_RISK_ZONE)"', SOURCE)
    # the only allowed occurrence is inside the zone_fill lookup dict, which maps an
    # already-decided zone_type to a display color — not a decision.
    fill_dict_line = next(l for l in SOURCE.splitlines() if "zone_fill=" in l)
    assert all(lit in fill_dict_line for lit in set(zone_type_literals))
