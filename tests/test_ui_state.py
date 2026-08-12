from bitcoin_cycle_analyzer.ui_state import default_chart_view_state, get_chart_view_state, LAYER_PRESETS, VIEW_MODES


def test_default_chart_view_state_has_all_required_fields():
    state = default_chart_view_state()
    for field in ("timeframe", "scale", "preset", "layers", "mode"):
        assert field in state


def test_layer_presets_cover_clean_to_research_depth():
    assert LAYER_PRESETS["CLEAN"] == []  # CLEAN must mean candles only, no exceptions
    assert set(LAYER_PRESETS["SWING"]) <= set(LAYER_PRESETS["RESEARCH"])
    assert set(LAYER_PRESETS["MACRO"]) <= set(LAYER_PRESETS["RESEARCH"])


def test_get_chart_view_state_is_idempotent_within_a_session():
    session_state = {}
    query_params = {}
    first = get_chart_view_state(session_state, query_params)
    first["timeframe"] = "1W"
    second = get_chart_view_state(session_state, query_params)
    assert second is first  # same object returned, not rebuilt from scratch on the next rerun
    assert second["timeframe"] == "1W"


def test_query_params_seed_mode_and_preset_on_first_load():
    session_state = {}
    query_params = {"preset": "MACRO", "mode": "SIMPLE"}
    state = get_chart_view_state(session_state, query_params)
    assert state["preset"] == "MACRO"
    assert state["mode"] == "SIMPLE"
    assert state["layers"] == LAYER_PRESETS["MACRO"]


def test_invalid_mode_in_query_params_falls_back_to_simple():
    session_state = {}
    query_params = {"mode": "NOT_A_REAL_MODE"}
    state = get_chart_view_state(session_state, query_params)
    assert state["mode"] == "SIMPLE"


def test_view_modes_are_exactly_simple_and_research():
    assert set(VIEW_MODES) == {"SIMPLE", "RESEARCH"}
