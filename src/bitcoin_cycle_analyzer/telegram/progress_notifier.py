"""Orchestrates the Signal-Progress notifier: compute -> decide -> format ->
send -> persist. Telegram failures are always caught here and logged - they
must never propagate up into the analysis pipeline (see client.py, which
already never raises out of `.send()`; this module adds the same guarantee
around everything else: state-store I/O and message formatting).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from .client import TelegramClient
from .progress import ProgressConfig, compute_progress, evaluate_signal_progress
from .progress_state import SignalProgressStore

logger = logging.getLogger(__name__)


def config_from_env(values: dict) -> ProgressConfig:
    def flag(name, default):
        return str(values.get(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}

    def number(name, default):
        try:
            return float(values.get(name, default))
        except (TypeError, ValueError):
            return default

    return ProgressConfig(
        enabled=flag("TELEGRAM_PROGRESS_ENABLED", False),
        min_score_delta=number("TELEGRAM_MIN_SCORE_DELTA", 10.0),
        cooldown_hours=number("TELEGRAM_COOLDOWN_HOURS", 6.0),
        notify_weak_watch=flag("TELEGRAM_NOTIFY_EARLY", False),
        notify_invalidation=flag("TELEGRAM_NOTIFY_INVALIDATION", True),
    )


def _money(value):
    return "UNAVAILABLE" if value is None else f"${value:,.0f}"


FACTOR_LABELS = {
    "value": "Bewertung", "drawdown": "Rückgang", "major_support": "Wichtige Unterstützung",
    "momentum_extreme": "Momentum", "capitulation": "Kapitulation", "timing": "Timing",
    "valuation": "Bewertung", "distribution": "Distribution", "structure": "Struktur",
    "momentum": "Momentum", "derivatives": "Derivate", "etf": "ETF",
}


def format_progress_message(decision: dict, current, previous_score: float | None) -> str:
    direction_label = "BUY" if decision["direction"] == "BUY" else "SELL"
    zone_line = f"{_money(current.zone_low)} - {_money(current.zone_high)}" if current.zone_low else "UNAVAILABLE"
    invalidation_line = _money(current.invalidation_level)
    confirmed_new = sorted(FACTOR_LABELS.get(x, x) for x in decision.get("confirmed_new", []))

    if decision["type"] == "INVALIDATION":
        return (
            f"\U0001f534 BITCOIN SETUP INVALIDIERT\n\n"
            f"Das zuletzt gemeldete {direction_label}-Setup ist nicht mehr gueltig.\n\n"
            f"BTC: {_money(current.price)}\n"
            f"Invalidation: {invalidation_line}\n\n"
            f"Kein aktives {direction_label}-Signal mehr."
        )

    header = "\U0001f7e2 BITCOIN " + direction_label + " SIGNAL — " + ("A+" if current.level_name == "A+" else current.level_name) if current.level_index >= 4 else "\U0001f7e1 BITCOIN SETUP VERBESSERT"
    lines = [header, ""]
    lines.append(f"BTC: {_money(current.price)}")
    if current.level_index < 4:
        lines.append(f"Richtung: {direction_label}")
        lines.append(f"Status: {decision['previous_level']} → {decision['current_level']}")
        prev = "?" if previous_score is None else f"{previous_score:.0f}"
        lines.append(f"Qualitaet: {prev} → {current.score:.0f}")
    else:
        lines.append(f"Qualitaet: {current.score:.0f}/100")
    if confirmed_new:
        lines.append("")
        lines.append("Neu bestaetigt:")
        for name in confirmed_new:
            lines.append(f"• {name}")
    lines.append("")
    lines.append(("Kaufzone" if direction_label == "BUY" else "Verkaufszone") + f":\n{zone_line}")
    lines.append("")
    lines.append(f"Invalidation:\nunter {invalidation_line}" if direction_label == "BUY" else f"Invalidation:\nueber {invalidation_line}")
    lines.append("")
    lines.append("Noch kein finales Kaufsignal." if current.level_index < 6 else f"BitcoinElliot hat den Status auf {current.level_name} hochgestuft.")
    return "\n".join(lines)


def run_signal_progress_check(state: dict, config: ProgressConfig, client: TelegramClient, store: SignalProgressStore, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    results = []
    if not config.enabled:
        return [{"send": False, "type": "DISABLED", "direction": d, "reason": ["telegram_progress_disabled"]} for d in ("BUY", "SELL")]
    for direction in ("BUY", "SELL"):
        try:
            current = compute_progress(state, direction)
            previous_row = store.get(direction)
            previous_score = previous_row.get("last_score") if previous_row else None
            decision = evaluate_signal_progress(previous_row, current, config, now)
            logger.info("Telegram signal-progress %s: %s reason=%s previous=%s current=%s score=%.1f", direction, "SEND" if decision["send"] else "NO_SEND", ";".join(decision["reason"]), decision["previous_level"], decision["current_level"], current.score)
            if decision["send"]:
                message = format_progress_message(decision, current, previous_score)
                delivery = client.send(message)
                decision["delivery"] = delivery
            store.save(decision["new_row"])
            results.append(decision)
        except Exception:
            logger.exception("Telegram signal-progress check failed for direction=%s - continuing without notification", direction)
            results.append({"send": False, "type": "ERROR", "direction": direction, "reason": ["internal_error"]})
    return results


def send_test_message(client: TelegramClient) -> dict:
    return client.send("✅ BitcoinElliot Telegram verbunden\n\nSignal-Progress-Alerts sind aktiv.\nNur relevante Signalverbesserungen werden gemeldet.")
