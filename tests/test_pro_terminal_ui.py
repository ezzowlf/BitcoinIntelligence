from pathlib import Path
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]

SOURCE=Path("dashboard/app.py").read_text(encoding="utf-8")

def test_terminal_has_compact_decision_and_live_confirmed_distinction():
    assert "terminal-head" in SOURCE and "decision" in SOURCE
    assert "MT5 LIVE" in SOURCE and "Confirmed H4" in SOURCE

def test_chart_is_dominant_and_has_required_overlays():
    assert "height=555" in SOURCE
    for layer in ("Zones","200D/200W","Bollinger","Elliott","Signals","Historical Entries"):assert layer in SOURCE
    assert "add_hrect" in SOURCE and "add_hline" in SOURCE

def test_raw_debug_is_not_exposed_in_production_terminal():
    assert 'DEBUG · raw state' not in SOURCE and 'st.json(state)' not in SOURCE

def test_terminal_apptest_renders_without_exception():
    at=AppTest.from_file(ROOT / "dashboard" / "app.py",default_timeout=40).run()
    top_level={"CHART","CYCLES","HISTORY","EVENTS","RESEARCH","SYSTEM"}
    assert not at.exception
    assert sum(1 for t in at.tabs if t.label in top_level)==6

def test_macro7_timeframes_layers_and_plain_language_surfaces():
    for token in ('"1Y"','"ALL"','"Macro Zones"','"Swing Zones"','"Fib"','"Events"','"CYCLES"'):assert token in SOURCE
    assert "Macro scenario map" in SOURCE and "Long-Swing BUY bleibt ohne validierten Edge gesperrt" in SOURCE

def test_navigation_is_simplified_to_six_top_level_sections():
    assert 'st.tabs(["CHART","CYCLES","HISTORY","EVENTS","RESEARCH","SYSTEM"])' in SOURCE

def test_indicator_state_and_rule_registry_are_exported_and_not_executed():
    assert "build_decision_state_v1" in SOURCE and "build_indicator_state_v1" in SOURCE and "rule_registry" in SOURCE
    assert "PINE_MQL_CAPABILITY_MATRIX" in SOURCE
    assert '"execution": "DISABLED"' in Path("src/bitcoin_cycle_analyzer/indicator_state.py").read_text(encoding="utf-8")

def test_layer_presets_and_drawing_tools_present():
    for preset in ("CLEAN","SWING","MACRO","RESEARCH"):assert f'"{preset}"' in SOURCE
    assert "drawline" in SOURCE and "drawrect" in SOURCE and "eraseshape" in SOURCE

def test_dormant_conditional_targets_are_labelled_not_predicted():
    assert "DORMANT — NOT AN ACTIVE TARGET" in SOURCE

def test_decision_card_is_wired_and_traceable():
    assert "BITCOIN DECISION" in SOURCE and "build_decision_intelligence" in SOURCE
    assert "Decision Rule Registry" in SOURCE and "DECISION_RULE_REGISTRY" in SOURCE
