"""Master-Auftrag 4 — product integration/quality guards.

These tests protect the fixes made during the full user-journey audit:
removed duplicate zone cards, English-only UI copy, a single canonical
DecisionState feeding both the chart and the card, honest data-availability
wording, and a default view that isn't "whatever the last commit left".
"""
import re
from pathlib import Path

SOURCE = Path("dashboard/app.py").read_text(encoding="utf-8")

FORBIDDEN_GERMAN_STRINGS = (
    "bleibt ohne validierten Edge gesperrt",
    "Kein neues bestätigtes tieferes Tief",
    "Struktur zurückerobern",
    "keine Wahrscheinlichkeit",
)


# ---------------------------------------------------------------- Terminology (Sections 1, 5, 24)

def test_no_leftover_german_strings_in_primary_ui():
    for forbidden in FORBIDDEN_GERMAN_STRINGS:
        assert forbidden not in SOURCE, f"German string leaked into the UI: {forbidden!r}"


def test_wait_labels_are_plain_english():
    match = re.search(r'wait_labels=\{([^}]+)\}', SOURCE)
    assert match, "wait_labels dict not found"
    body = match.group(1)
    # crude but effective: German uses these characters, English display copy must not
    assert not any(ch in body for ch in "äöüß")


# ---------------------------------------------------------------- One primary answer / no duplication (Sections 2, 3)

def test_next_buy_zone_duplicate_card_was_removed():
    assert "NEXT BUY ZONE" not in SOURCE  # fully duplicated the DECISION DETAIL zone line


def test_decision_detail_card_replaces_the_old_competing_bitcoin_decision_label():
    assert "DECISION DETAIL" in SOURCE
    assert "explains the champion signal above" in SOURCE  # explicit bridge, not a second verdict
    assert "research synthesis" not in SOURCE  # old, ambiguous framing removed


def test_champion_signal_is_explicitly_labelled_as_such():
    assert "CHAMPION SIGNAL (CONTROL 3 / MACRO 7)" in SOURCE


# ---------------------------------------------------------------- Decision Story chain (Section 4)

def test_decision_detail_card_shows_full_story_chain():
    # ZONE (where), ENTRY (interesting vs confirmed), INVALIDATION (wrong-if), CONFIDENCE
    card_start = SOURCE.index("DECISION DETAIL <span")
    card_region = SOURCE[card_start:card_start + 1200]
    for field in ("ZONE</span>", "ENTRY</span>", "INVALIDATION</span>", "CONFIDENCE</span>"):
        assert field in card_region


def test_decision_detail_uses_the_full_explanation_summary_not_just_a_one_liner():
    assert "decision_explanation['summary']" in SOURCE or 'decision_explanation["summary"]' in SOURCE


# ---------------------------------------------------------------- Canonical state reuse (Section 19)

def test_decision_intelligence_is_computed_exactly_once():
    assert SOURCE.count("build_decision_intelligence(") == 1


def test_explanation_facts_are_computed_exactly_once():
    assert SOURCE.count("build_explanation_facts(") == 1


def test_chart_and_card_read_the_same_di_object():
    # the chart-drawing code and the DECISION DETAIL card must both reference `di[`,
    # never a second independently-fetched decision value
    chart_region = SOURCE[SOURCE.index("Decision Intelligence zone/invalidation/targets ALWAYS render"):SOURCE.index("Decision Intelligence zone/invalidation/targets ALWAYS render") + 800]
    assert 'di["invalidation_level"]' in chart_region or "di.get(\"invalidation_level\")" in chart_region
    card_region = SOURCE[SOURCE.index("DECISION DETAIL <span"):SOURCE.index("DECISION DETAIL <span") + 1200]
    assert "di['invalidation_level']" in card_region or 'di["invalidation_level"]' in card_region


# ---------------------------------------------------------------- No contradictory decision labels (Section 18)

def test_dec_color_mapping_covers_every_canonical_decision_state():
    from bitcoin_cycle_analyzer.decision_intelligence.decision_engine import DECISION_STATES
    color_line = next(l for l in SOURCE.splitlines() if "dec_color=" in l)
    for state in DECISION_STATES:
        assert f'"{state}"' in color_line, f"decision state {state} has no display color mapped — would fall back silently"


# ---------------------------------------------------------------- Event display (Section 8)

def test_event_relevance_card_only_shows_high_or_critical_importance():
    assert 'recent_important=event_rows[event_rows.importance.isin(["HIGH","CRITICAL"])]' in SOURCE


# ---------------------------------------------------------------- Data availability wording (Section 20)

def test_data_unavailable_is_never_relabelled_as_neutral():
    assert '"UNAVAILABLE"' in SOURCE
    # the historical family / macro family modules must not silently say NEUTRAL when data is missing
    evidence_source = Path("src/bitcoin_cycle_analyzer/decision_intelligence/evidence.py").read_text(encoding="utf-8")
    macro_family_fn = evidence_source[evidence_source.index("def _macro_family"):evidence_source.index("def _positioning_family")]
    assert '"UNAVAILABLE"' in macro_family_fn
    assert 'direction, strength = "NEUTRAL"' not in macro_family_fn.split("if macro_status")[0]


# ---------------------------------------------------------------- Responsive primary-content order (Section 14)

def test_chart_renders_before_the_tab_strip_in_script_order():
    assert SOURCE.index('st.plotly_chart(fig,width="stretch"') < SOURCE.index('tabs=st.tabs(')


# ---------------------------------------------------------------- Default preset / default view (Section 11)

def test_default_view_state_is_well_defined_not_implicit():
    from bitcoin_cycle_analyzer.ui_state import default_chart_view_state
    state = default_chart_view_state()
    assert state["preset"] == "SWING"  # deliberate default, not CLEAN or RESEARCH
    assert state["mode"] == "SIMPLE"  # Explain & Action Layer: product explains itself first


# ---------------------------------------------------------------- Explanation fallback (Section 17)

def test_explanation_facts_do_not_require_ai():
    import inspect
    from bitcoin_cycle_analyzer.decision_intelligence import explanation
    source = inspect.getsource(explanation)
    assert "openai" not in source.lower() and "BitcoinAIRouter" not in source


# ---------------------------------------------------------------- Technical cleanup (Section 27)

def test_no_unused_zone_low_high_variables_left_behind():
    # the removed NEXT BUY ZONE card used to compute zl/zh from m5["buy"]["zone"] —
    # confirm that dead computation was actually removed, not just the display
    assert "zl=zone.get(\"low\")" not in SOURCE
