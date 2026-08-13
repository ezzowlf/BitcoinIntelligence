"""Master-Auftrag (Live-Daten, Mobile, Deutsch): feed-status semantics, execution-lock
labelling, and chart Y-axis clamping.

Protects the fix for the confusion between "data feed disabled" and "auto-trading
disabled" (both used to render as the bare word DISABLED), and the unclamped Y-axis
that could be stretched to millions by a single outlier target/zone/drawing.
"""
from pathlib import Path

SOURCE = Path("dashboard/app.py").read_text(encoding="utf-8")


def test_feed_badge_never_renders_bare_disabled_next_to_btcusd():
    idx = SOURCE.index("class='terminal-head'")
    head = SOURCE[idx:idx + 700]
    assert "DISABLED" not in head
    assert "feed_label" in head


def test_feed_status_labels_are_german_and_distinct_states():
    assert 'feed_label="LIVE-KURSDATEN: AKTIV"' in SOURCE
    assert "LIVE-KURSDATEN: VERZÖGERT" in SOURCE
    assert "LIVE-KURSDATEN: NICHT VERFÜGBAR" in SOURCE


def test_execution_lock_is_labelled_separately_from_feed_status():
    assert "AUTOMATISCHER HANDEL: DEAKTIVIERT" in SOURCE
    assert '"Automatischer Handel"' in SOURCE


def test_price_fallback_is_explicit_about_being_a_stale_daily_close():
    assert "Live-Kurs derzeit nicht verfügbar" in SOURCE
    assert "letzter bestätigter Tageskurs" in SOURCE


def test_news_events_distinguish_empty_from_unavailable():
    assert "Nachrichtendaten derzeit nicht verfügbar." in SOURCE
    assert "keine relevanten Ereignisse" in SOURCE


def test_yaxis_range_is_clamped_from_visible_price_bounds():
    assert "visible_lo=float(visible" in SOURCE
    assert "visible_hi=float(visible" in SOURCE
    assert 'yaxis_layout["range"]=' in SOURCE
    # the clamp must be applied to the layout actually used by the chart
    assert "yaxis=yaxis_layout" in SOURCE


def test_drawing_price_inputs_have_an_upper_bound():
    assert "draw_price_max=float(live_price)*10" in SOURCE
    assert SOURCE.count("max_value=draw_price_max") >= 4


def test_touch_action_css_present_and_scoped_not_blanket_disabled():
    assert "touch-action:pan-y" in SOURCE
    assert "touch-action:none" in SOURCE
    # must never blanket-disable touch on the whole page
    assert "html{touch-action:none}" not in SOURCE
    assert "body{touch-action:none}" not in SOURCE
