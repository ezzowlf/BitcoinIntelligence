"""Signal-Progress notifier - pure decision logic.

This module never computes a signal itself. It only observes fields the
existing engine already produces (`state["rare_signal"]`, `state["master5_challenger"]`)
and decides whether a *change* in those fields is significant enough to be
worth a Telegram message. It never lowers thresholds, invents candidates, or
feeds anything back into the analysis engine - purely a read-only observer
layered on top.

Progress ladder (per direction, BUY or SELL), derived entirely from existing
`rare_signal` fields - no new state names invented:

    0 NOTHING     level_b.<dir> == "NONE" and <dir>_state == "NO_BUY"/"NO_SELL"
    1 WATCH       level_b.<dir> == "ACCUMULATION_CANDIDATE" / "WATCH_DISTRIBUTION"
    2 EARLY       level_b.<dir> == "BUY_CANDIDATE" (>=3 independent factor groups)
    3 B           <dir>_state == "ACCUMULATE" / "REDUCE"
    4 A           <dir>_state == "BUY" / "SELL"            (level_a.strength VERY_HIGH)
    5 A+          <dir>_state == "STRONG_BUY" / "STRONG_SELL" (strength EXCEPTIONAL)
    6 PRODUCTION  level_a.signal == <dir>_state and level_a.direction == <dir>
                  (the production gate actually fired for this direction, i.e.
                  no competing direction pre-empted it)
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

LEVELS = ("NOTHING", "WATCH", "EARLY", "B", "A", "A+", "PRODUCTION")


def _buy_level(rare_signal: dict) -> int:
    candidate = rare_signal["level_b"]["buy"]
    buy_state = rare_signal["buy_state"]
    strength = rare_signal["level_a"]["strength"]
    if rare_signal["level_a"]["signal"] == buy_state and rare_signal["level_a"]["direction"] == "BUY" and buy_state in {"BUY", "STRONG_BUY"}:
        return 6
    if buy_state == "STRONG_BUY" or strength == "EXCEPTIONAL":
        return 5
    if buy_state == "BUY" or strength == "VERY_HIGH":
        return 4
    if buy_state == "ACCUMULATE":
        return 3
    if candidate == "BUY_CANDIDATE":
        return 2
    if candidate == "ACCUMULATION_CANDIDATE":
        return 1
    return 0


def _sell_level(rare_signal: dict) -> int:
    sell = rare_signal["sell"]
    candidate = rare_signal["level_b"]["sell"]
    sell_state = sell["state"]
    if rare_signal["level_a"]["signal"] == sell_state and rare_signal["level_a"]["direction"] == "SELL" and sell_state in {"SELL", "STRONG_SELL"}:
        return 6
    if sell_state == "STRONG_SELL":
        return 5
    if sell_state == "SELL":
        return 4
    if sell_state == "REDUCE":
        return 3
    if candidate == "WATCH_DISTRIBUTION":
        return 1
    return 0


@dataclass(frozen=True)
class SignalProgress:
    direction: str
    level_index: int
    level_name: str
    score: float
    confirmed: frozenset
    missing: frozenset
    price: float
    zone_low: float | None
    zone_high: float | None
    invalidation_level: float | None
    fingerprint: str


def _fingerprint(direction: str, level_name: str, cycle_regime: str, zone_low: float | None, zone_high: float | None, invalidation_level: float | None) -> str:
    # Deliberately excludes the live BTC price - only the *structural* identity
    # of the setup, so the same setup is recognized across ordinary price
    # movement between two runs (per the brief: 63,450 -> 63,600 must not
    # register as a "new" setup).
    zone_key = f"{round(zone_low, -2) if zone_low else None}-{round(zone_high, -2) if zone_high else None}"
    invalidation_key = round(invalidation_level, -2) if invalidation_level else None
    payload = f"{direction}|{level_name}|{cycle_regime}|{zone_key}|{invalidation_key}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def compute_progress(state: dict, direction: str) -> SignalProgress:
    rare = state["rare_signal"]
    m5 = state["master5_challenger"]
    ms = state["master"]["state"]
    if direction == "BUY":
        level_index = _buy_level(rare)
        score = float(m5["buy"]["quality"])
        missing = frozenset(rare["level_b"]["missing_buy"])
        confirmed = frozenset(rare["level_c"]["buy_factors"].keys()) - missing
        zone = ms["buy_zones"][0] if ms.get("buy_zones") else None
        invalidation_level = state["decision"]["zones"]["invalidation"].get("below")
    else:
        level_index = _sell_level(rare)
        score = float(rare["sell"]["distribution_score"])
        missing = frozenset(k for k, v in rare["level_c"]["sell_factors"].items() if not v)
        confirmed = frozenset(rare["level_c"]["sell_factors"].keys()) - missing
        zone = ms["sell_zones"][0] if ms.get("sell_zones") else None
        invalidation_level = state["decision"]["zones"]["invalidation"].get("above")
    zone_low = zone.get("low") if zone else None
    zone_high = zone.get("high") if zone else None
    cycle_regime = state["precision"]["regime"]["current"]
    price = state["decision"]["zones"]["current_price"]
    level_name = LEVELS[level_index]
    fp = _fingerprint(direction, level_name, cycle_regime, zone_low, zone_high, invalidation_level)
    return SignalProgress(direction, level_index, level_name, score, confirmed, missing, price, zone_low, zone_high, invalidation_level, fp)


@dataclass(frozen=True)
class ProgressConfig:
    enabled: bool = False
    min_score_delta: float = 10.0
    cooldown_hours: float = 6.0
    notify_weak_watch: bool = False
    notify_invalidation: bool = True
    escalation_levels: int = 2  # a jump of >= this many levels overrides cooldown


def evaluate_signal_progress(previous_row: dict | None, current: SignalProgress, config: ProgressConfig, now) -> dict:
    """Pure decision function - no I/O, no side effects, fully testable.

    `previous_row` is whatever the persistent store last saved for this
    direction (or None on a genuinely first run for this direction).
    Returns a machine-readable decision; the caller is responsible for
    actually sending the message and persisting the new row.
    """
    reason: list[str] = []
    new_row = {
        "direction": current.direction,
        "last_progress_level": current.level_name,
        "last_signal_state": current.level_name,
        "last_score": current.score,
        "last_fingerprint": current.fingerprint,
        "updated_at": str(now),
    }

    if previous_row is None:
        new_row.update({"was_notified": False, "invalidated": False, "last_sent_at": None, "last_message_type": None})
        return {"send": False, "type": "BASELINE_INITIALIZED", "direction": current.direction, "previous_level": None, "current_level": current.level_name, "reason": ["first_run_baseline"], "new_row": new_row, "confirmed_new": frozenset(), "confirmed": current.confirmed}

    previous_level = previous_row.get("last_progress_level", "NOTHING")
    previous_index = LEVELS.index(previous_level) if previous_level in LEVELS else 0
    previous_score = float(previous_row.get("last_score") or 0.0)
    was_notified = bool(previous_row.get("was_notified"))
    invalidated_already = bool(previous_row.get("invalidated"))
    same_fingerprint = previous_row.get("last_fingerprint") == current.fingerprint

    new_row.update({"was_notified": was_notified, "invalidated": invalidated_already, "last_sent_at": previous_row.get("last_sent_at"), "last_message_type": previous_row.get("last_message_type")})

    # Invalidation: a previously notified setup collapsed back to NOTHING.
    if was_notified and not invalidated_already and current.level_index == 0 and previous_index > 0:
        if config.notify_invalidation:
            new_row.update({"invalidated": True, "was_notified": False, "last_sent_at": str(now), "last_message_type": "INVALIDATION"})
            return {"send": True, "type": "INVALIDATION", "direction": current.direction, "previous_level": previous_level, "current_level": current.level_name, "reason": ["previous_setup_invalidated"], "new_row": new_row, "confirmed_new": frozenset(), "confirmed": current.confirmed}
        new_row.update({"invalidated": True, "was_notified": False})
        return {"send": False, "type": "NO_SEND", "direction": current.direction, "previous_level": previous_level, "current_level": current.level_name, "reason": ["invalidation_notifications_disabled"], "new_row": new_row, "confirmed_new": frozenset(), "confirmed": current.confirmed}

    if current.level_index == 0:
        # Nothing was ever notified for this direction, or it's already been
        # invalidated once - either way, a flat NOTHING state stays silent.
        new_row["invalidated"] = False
        return {"send": False, "type": "NO_SEND", "direction": current.direction, "previous_level": previous_level, "current_level": current.level_name, "reason": ["no_active_candidate"], "new_row": new_row, "confirmed_new": frozenset(), "confirmed": current.confirmed}

    level_up = current.level_index > previous_index
    level_jump = current.level_index - previous_index
    score_delta = current.score - previous_score
    new_confirmed = current.confirmed - set(previous_row.get("last_confirmed", []) or [])
    new_row["last_confirmed"] = sorted(current.confirmed)

    escalation = level_jump >= config.escalation_levels or current.level_index >= 4  # reaching A/A+/PRODUCTION always escalates

    within_cooldown = False
    if was_notified and previous_row.get("last_sent_at"):
        try:
            elapsed_hours = (now - previous_row["last_sent_at"]).total_seconds() / 3600.0
            within_cooldown = elapsed_hours < config.cooldown_hours
        except TypeError:
            within_cooldown = False

    if not level_up and not same_fingerprint:
        # Different setup at the same or lower level than before - not a
        # progression of the setup we already know about; treat like a fresh
        # candidate only if it clears the "new serious setup" bar.
        if current.level_index >= 2 or (config.notify_weak_watch and current.level_index >= 1):
            reason.append("new_setup_replacing_previous")
        else:
            new_row["last_progress_level"] = current.level_name
            return {"send": False, "type": "NO_SEND", "direction": current.direction, "previous_level": previous_level, "current_level": current.level_name, "reason": ["new_setup_too_weak"], "new_row": new_row, "confirmed_new": new_confirmed, "confirmed": current.confirmed}

    should_send = False
    msg_type = "NO_SEND"

    if level_up:
        if current.level_index == 1 and not config.notify_weak_watch:
            reason.append("watch_level_suppressed_by_config")
        else:
            should_send = True
            msg_type = "SIGNAL_PROGRESS" if current.level_index < 6 else "PRODUCTION_SIGNAL"
            reason.append(f"level_up_{previous_level}_to_{current.level_name}")
    elif current.level_index == previous_index and score_delta >= config.min_score_delta:
        should_send = True
        msg_type = "SIGNAL_PROGRESS"
        reason.append(f"score_delta_{score_delta:.1f}_gte_{config.min_score_delta}")
        if new_confirmed:
            reason.append("new_confirmation:" + ",".join(sorted(new_confirmed)))
    elif not level_up:
        reason.append("no_material_improvement")

    if should_send and within_cooldown and not escalation:
        should_send = False
        msg_type = "NO_SEND"
        reason.append("suppressed_by_cooldown")
    elif should_send and within_cooldown and escalation:
        reason.append("cooldown_overridden_by_escalation")

    new_row["last_progress_level"] = current.level_name
    if should_send:
        new_row.update({"was_notified": True, "last_sent_at": str(now), "last_message_type": msg_type, "invalidated": False})

    return {"send": should_send, "type": msg_type, "direction": current.direction, "previous_level": previous_level, "current_level": current.level_name, "reason": reason, "new_row": new_row, "confirmed_new": new_confirmed, "confirmed": current.confirmed}
