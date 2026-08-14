from datetime import datetime, timedelta, timezone

import pytest

from bitcoin_cycle_analyzer.telegram.progress import LEVELS, ProgressConfig, SignalProgress, evaluate_signal_progress
from bitcoin_cycle_analyzer.telegram.progress_state import SignalProgressStore
from bitcoin_cycle_analyzer.telegram.progress_notifier import format_progress_message, run_signal_progress_check
from bitcoin_cycle_analyzer.telegram.client import TelegramClient


def _progress(level_name, score=50.0, confirmed=(), missing=(), price=63000.0, zone=(61000.0, 62500.0), invalidation=59000.0, fp="fp1"):
    return SignalProgress("BUY", LEVELS.index(level_name), level_name, score, frozenset(confirmed), frozenset(missing), price, zone[0], zone[1], invalidation, fp)


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
CFG = ProgressConfig(enabled=True, min_score_delta=10.0, cooldown_hours=6.0, notify_weak_watch=False, notify_invalidation=True)


# --- Progress engine ---------------------------------------------------

def test_first_startup_is_no_send_baseline():
    decision = evaluate_signal_progress(None, _progress("WATCH"), CFG, NOW)
    assert decision["send"] is False
    assert decision["type"] == "BASELINE_INITIALIZED"


def test_same_state_is_no_send():
    prev = evaluate_signal_progress(None, _progress("B", score=50), CFG, NOW)["new_row"]
    prev["was_notified"] = True
    prev["last_sent_at"] = (NOW - timedelta(hours=10))
    decision = evaluate_signal_progress(prev, _progress("B", score=50, fp="fp1"), CFG, NOW)
    assert decision["send"] is False


def test_score_plus_one_is_no_send():
    prev = {"last_progress_level": "B", "last_score": 50.0, "last_fingerprint": "fp1", "was_notified": True, "last_sent_at": (NOW - timedelta(hours=10)), "last_confirmed": []}
    decision = evaluate_signal_progress(prev, _progress("B", score=51, fp="fp1"), CFG, NOW)
    assert decision["send"] is False
    assert "no_material_improvement" in decision["reason"] or decision["send"] is False


def test_score_plus_five_is_no_send():
    prev = {"last_progress_level": "B", "last_score": 50.0, "last_fingerprint": "fp1", "was_notified": True, "last_sent_at": (NOW - timedelta(hours=10)), "last_confirmed": []}
    decision = evaluate_signal_progress(prev, _progress("B", score=55, fp="fp1"), CFG, NOW)
    assert decision["send"] is False


def test_score_significant_jump_sends():
    prev = {"last_progress_level": "B", "last_score": 50.0, "last_fingerprint": "fp1", "was_notified": True, "last_sent_at": (NOW - timedelta(hours=10)), "last_confirmed": []}
    decision = evaluate_signal_progress(prev, _progress("B", score=65, fp="fp1"), CFG, NOW)
    assert decision["send"] is True


@pytest.mark.parametrize("prev_level,cur_level", [("WATCH", "EARLY"), ("EARLY", "B"), ("B", "A"), ("A", "A+")])
def test_level_up_transitions_send(prev_level, cur_level):
    prev = {"last_progress_level": prev_level, "last_score": 30.0, "last_fingerprint": "fp1", "was_notified": prev_level != "WATCH", "last_sent_at": (NOW - timedelta(hours=10)) if prev_level != "WATCH" else None, "last_confirmed": []}
    decision = evaluate_signal_progress(prev, _progress(cur_level, score=60, fp="fp1"), CFG, NOW)
    assert decision["send"] is True
    assert decision["current_level"] == cur_level


def test_downgrade_is_no_send():
    prev = {"last_progress_level": "A", "last_score": 80.0, "last_fingerprint": "fp1", "was_notified": True, "last_sent_at": (NOW - timedelta(hours=10)), "last_confirmed": []}
    decision = evaluate_signal_progress(prev, _progress("B", score=50, fp="fp1"), CFG, NOW)
    assert decision["send"] is False


def test_watch_level_suppressed_by_default_config():
    decision = evaluate_signal_progress({"last_progress_level": "NOTHING", "last_score": 0.0, "last_fingerprint": "fpX", "was_notified": False, "last_sent_at": None, "last_confirmed": [], "invalidated": False}, _progress("WATCH", score=20, fp="fp1"), CFG, NOW)
    assert decision["send"] is False


# --- Dedup ---------------------------------------------------------------

def test_same_setup_repeated_no_second_message(tmp_path):
    store = SignalProgressStore(tmp_path / "p.db")
    client = TelegramClient(None, None, enabled=False, dry_run=True)
    import bitcoin_cycle_analyzer.telegram.progress_notifier as pn

    state = {"rare_signal": _fake_rare_signal("BUY_CANDIDATE", "ACCUMULATE"), "master5_challenger": {"buy": {"quality": 60}}, "master": {"state": {"buy_zones": [{"low": 61000, "high": 62500}], "sell_zones": []}}, "decision": {"zones": {"current_price": 61500, "invalidation": {"below": 59000}}}, "precision": {"regime": {"current": "BEAR"}}}
    r1 = pn.run_signal_progress_check(state, ProgressConfig(enabled=True), client, store, now=NOW)
    r2 = pn.run_signal_progress_check(state, ProgressConfig(enabled=True), client, store, now=NOW + timedelta(minutes=5))
    assert all(not r["send"] for r in r1)  # baseline
    assert all(not r["send"] for r in r2)  # identical state again


def test_restart_with_same_persistent_state_no_second_message(tmp_path):
    db_path = tmp_path / "p.db"
    client = TelegramClient(None, None, enabled=False, dry_run=True)
    import bitcoin_cycle_analyzer.telegram.progress_notifier as pn

    state_watch = {"rare_signal": _fake_rare_signal("ACCUMULATION_CANDIDATE", "NO_BUY"), "master5_challenger": {"buy": {"quality": 20}}, "master": {"state": {"buy_zones": [], "sell_zones": []}}, "decision": {"zones": {"current_price": 61500, "invalidation": {}}}, "precision": {"regime": {"current": "BEAR"}}}
    state_b = {"rare_signal": _fake_rare_signal("BUY_CANDIDATE", "ACCUMULATE"), "master5_challenger": {"buy": {"quality": 55}}, "master": {"state": {"buy_zones": [{"low": 61000, "high": 62500}], "sell_zones": []}}, "decision": {"zones": {"current_price": 61500, "invalidation": {"below": 59000}}}, "precision": {"regime": {"current": "BEAR"}}}

    store = SignalProgressStore(db_path)
    pn.run_signal_progress_check(state_watch, ProgressConfig(enabled=True), client, store, now=NOW)  # baseline
    r_up = pn.run_signal_progress_check(state_b, ProgressConfig(enabled=True), client, store, now=NOW + timedelta(hours=1))
    assert any(r["send"] for r in r_up)

    # simulate restart: fresh store object pointing at the same file
    store2 = SignalProgressStore(db_path)
    r_restart = pn.run_signal_progress_check(state_b, ProgressConfig(enabled=True), client, store2, now=NOW + timedelta(hours=1, minutes=5))
    assert all(not r["send"] for r in r_restart)


def _fake_rare_signal(candidate, buy_state):
    return {
        "level_a": {"signal": "NO_PRODUCTION_SIGNAL", "direction": None, "strength": None},
        "level_b": {"buy": candidate, "sell": "NONE", "missing_buy": ["timing", "capitulation"], "missing_sell": []},
        "level_c": {"buy_factors": {"value": True, "drawdown": True, "major_support": False, "momentum_extreme": False, "capitulation": False, "timing": False}, "sell_factors": {"valuation": False, "distribution": False, "structure": False, "momentum": False, "derivatives": False, "etf": False}},
        "buy_state": buy_state,
        "sell": {"state": "NO_SELL", "distribution_score": 0, "factors": {"valuation": False, "distribution": False, "structure": False, "momentum": False, "derivatives": False, "etf": False}},
    }


# --- Cooldown --------------------------------------------------------------

def test_minor_improvement_inside_cooldown_no_send():
    prev = {"last_progress_level": "B", "last_score": 50.0, "last_fingerprint": "fp1", "was_notified": True, "last_sent_at": (NOW - timedelta(hours=1)), "last_confirmed": []}
    decision = evaluate_signal_progress(prev, _progress("B", score=61, fp="fp1"), CFG, NOW)
    assert decision["send"] is False
    assert "suppressed_by_cooldown" in decision["reason"]


def test_major_escalation_inside_cooldown_still_sends():
    prev = {"last_progress_level": "WATCH", "last_score": 20.0, "last_fingerprint": "fp1", "was_notified": True, "last_sent_at": (NOW - timedelta(hours=1)), "last_confirmed": []}
    decision = evaluate_signal_progress(prev, _progress("A", score=80, fp="fp1"), CFG, NOW)
    assert decision["send"] is True
    assert "cooldown_overridden_by_escalation" in decision["reason"]


# --- Invalidation ------------------------------------------------------

def test_notified_setup_invalidated_sends_once():
    prev = {"last_progress_level": "A", "last_score": 80.0, "last_fingerprint": "fp1", "was_notified": True, "invalidated": False, "last_sent_at": (NOW - timedelta(hours=2)), "last_confirmed": []}
    decision = evaluate_signal_progress(prev, _progress("NOTHING", score=0, fp="fp2"), CFG, NOW)
    assert decision["send"] is True
    assert decision["type"] == "INVALIDATION"


def test_same_invalidation_not_repeated():
    prev = {"last_progress_level": "NOTHING", "last_score": 0.0, "last_fingerprint": "fp2", "was_notified": False, "invalidated": True, "last_sent_at": (NOW - timedelta(hours=2)), "last_confirmed": []}
    decision = evaluate_signal_progress(prev, _progress("NOTHING", score=0, fp="fp2"), CFG, NOW)
    assert decision["send"] is False


def test_never_notified_weak_setup_invalidated_no_send():
    prev = {"last_progress_level": "WATCH", "last_score": 20.0, "last_fingerprint": "fp1", "was_notified": False, "invalidated": False, "last_sent_at": None, "last_confirmed": []}
    decision = evaluate_signal_progress(prev, _progress("NOTHING", score=0, fp="fp2"), CFG, NOW)
    assert decision["send"] is False


# --- Telegram client (mocked) ----------------------------------------------

def test_client_dry_run_no_http_request():
    client = TelegramClient("tok", "123", enabled=True, dry_run=True)
    result = client.send("hello")
    assert result["status"] == "DRY_RUN"
    assert result["delivered"] is False


def test_client_missing_token_disabled():
    client = TelegramClient(None, "123", enabled=True, dry_run=False)
    assert client.dry_run is True


def test_client_missing_chat_id_disabled():
    client = TelegramClient("tok", None, enabled=True, dry_run=False)
    assert client.dry_run is True


class _FakeSession:
    def __init__(self, response):
        self._response = response

    def post(self, *a, **k):
        return self._response


class _FakeResponse:
    def __init__(self, status=200, payload=None, raise_exc=None):
        self.status_code = status
        self._payload = payload or {}
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc:
            raise self._raise_exc

    def json(self):
        return self._payload


def test_client_valid_send_success():
    session = _FakeSession(_FakeResponse(200, {"ok": True, "result": {"message_id": 42}}))
    client = TelegramClient("tok", "123", enabled=True, dry_run=False, session=session)
    result = client.send("hi")
    assert result["status"] == "DELIVERED"
    assert result["message_id"] == 42


def test_client_timeout_graceful_failure():
    import requests

    class _TimeoutSession:
        def post(self, *a, **k):
            raise requests.Timeout("timed out")

    client = TelegramClient("tok", "123", enabled=True, dry_run=False, session=_TimeoutSession(), retries=1)
    result = client.send("hi")
    assert result["status"] == "FAILED"
    assert result["delivered"] is False


def test_client_http_error_graceful_failure():
    import requests

    session = _FakeSession(_FakeResponse(500, raise_exc=requests.HTTPError("boom")))
    client = TelegramClient("tok", "123", enabled=True, dry_run=False, session=session, retries=1)
    result = client.send("hi")
    assert result["status"] == "FAILED"


# --- Message formatting -----------------------------------------------------

def test_message_has_no_none_placeholders():
    decision = {"type": "SIGNAL_PROGRESS", "direction": "BUY", "previous_level": "EARLY", "current_level": "B", "confirmed_new": ["value"]}
    message = format_progress_message(decision, _progress("B", score=69, confirmed=["value"]), 58)
    assert "None" not in message
    assert "$None" not in message


def test_message_no_empty_bulletpoints():
    decision = {"type": "SIGNAL_PROGRESS", "direction": "BUY", "previous_level": "WATCH", "current_level": "EARLY", "confirmed_new": []}
    message = format_progress_message(decision, _progress("EARLY", score=40), 35)
    assert "•\n" not in message and not message.rstrip().endswith("•")


def test_message_direction_correct():
    decision = {"type": "SIGNAL_PROGRESS", "direction": "BUY", "previous_level": "B", "current_level": "A", "confirmed_new": []}
    message = format_progress_message(decision, _progress("A", score=80), 60)
    assert "BUY" in message


def test_invalidation_message_correct():
    decision = {"type": "INVALIDATION", "direction": "BUY", "previous_level": "A", "current_level": "NOTHING", "confirmed_new": []}
    message = format_progress_message(decision, _progress("NOTHING", score=0, price=60760, invalidation=60900), None)
    assert "INVALIDIERT" in message
    assert "60,760" in message or "60760" in message
