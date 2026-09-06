"""Deduplicated, escalating production alerting (Phases 11-13).

Delivery uses the project's existing safe notification infrastructure
(:class:`bitcoin_cycle_analyzer.telegram.client.TelegramClient`), which falls
back to a no-op DRY_RUN automatically when a token / chat id is not configured.
Regardless of Telegram, every alert is also appended to ``alerts.jsonl`` and the
incident log, so a stale pipeline can never go unrecorded.

Secrets are never logged or returned. Only ``CONFIGURED`` / ``MISSING`` is
exposed for the Telegram configuration state. Execution stays DISABLED.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .resilience import CONFIG
from .journal import atomic_json

EXECUTION = "DISABLED"

# Severity ladder (Phase 13).
INFO = "INFO"
WARNING = "WARNING"
HIGH = "HIGH"
CRITICAL = "CRITICAL"
_RANK = {INFO: 0, WARNING: 1, HIGH: 2, CRITICAL: 3}

# Alert kinds (Phase 11).
DEGRADED = "DEGRADED"
RECOVERY_WARNING = "RECOVERY_WARNING"
CRITICAL_ALERT = "CRITICAL"
RECOVERED = "RECOVERED"


def telegram_config_state() -> str:
    """`CONFIGURED` iff enabled with a token and chat id; never reveals values."""
    enabled = os.environ.get("TELEGRAM_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    has_token = bool(os.environ.get("TELEGRAM_BOT_TOKEN", "").strip())
    has_chat = bool(os.environ.get("TELEGRAM_CHAT_ID", os.environ.get("BITCOIN_TELEGRAM_CHAT_ID", "")).strip())
    return "CONFIGURED" if (enabled and has_token and has_chat) else "MISSING"


def _default_telegram_sink() -> Callable[[str], dict[str, Any]] | None:
    try:
        from bitcoin_cycle_analyzer.telegram.client import TelegramClient
    except Exception:  # noqa: BLE001
        return None
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or None
    chat = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("BITCOIN_TELEGRAM_CHAT_ID") or None
    enabled = os.environ.get("TELEGRAM_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    dry_run = os.environ.get("TELEGRAM_DRY_RUN", "true").strip().lower() in {"1", "true", "yes", "on"}
    client = TelegramClient(token, chat, enabled=enabled, dry_run=dry_run)

    def _send(text: str) -> dict[str, Any]:
        result = client.send(text)
        # Never surface token/chat; keep only the delivery verdict.
        return {"status": result.get("status"), "delivered": bool(result.get("delivered"))}

    return _send


@dataclass
class _AlertState:
    kind: str
    severity: str
    first_seen: datetime
    last_sent: datetime
    open: bool = True


@dataclass
class AlertManager:
    alerts_path: Path
    incident_log: Any | None = None
    telegram_sink: Callable[[str], dict[str, Any]] | None = None
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _states: dict[str, _AlertState] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self.alerts_path = Path(self.alerts_path)
        self.alerts_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path=self.alerts_path.with_suffix('.state.json')
        try:
            saved=json.loads(self._state_path.read_text(encoding='utf8'))
            self._states={k:_AlertState(v['kind'],v['severity'],datetime.fromisoformat(v['first_seen']),datetime.fromisoformat(v['last_sent']),v['open']) for k,v in saved.items()}
        except FileNotFoundError:pass
        if self.telegram_sink is None:
            self.telegram_sink = _default_telegram_sink()

    # ------------------------------------------------------------------ public

    def notify(
        self,
        *,
        component: str,
        kind: str,
        severity: str,
        message: str,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Deduplicated dispatch. Returns the emitted record, or None if suppressed."""
        now = self.clock()
        key = f"{component}:{kind}"
        with self._lock:
            state = self._states.get(key)
            reminder_due = (
                state is not None
                and state.open
                and (now - state.last_sent).total_seconds() >= CONFIG.alert_reminder_interval
            )
            escalated = state is not None and state.open and _RANK[severity] > _RANK[state.severity]
            is_new = state is None or not state.open

            if not (is_new or reminder_due or escalated):
                return None  # same state, within reminder window -> suppress

            if is_new:
                self._states[key] = _AlertState(kind, severity, now, now, open=True)
            else:
                state.last_sent = now
                state.severity = max(state.severity, severity, key=lambda s: _RANK[s])

            self._persist()
            return self._emit(component, kind, severity, message, detail, now, reminder=reminder_due and not escalated)

    def resolve(
        self,
        *,
        component: str,
        kind: str,
        message: str,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Close an open alert and emit exactly one RECOVERED (Phase 12)."""
        now = self.clock()
        key = f"{component}:{kind}"
        with self._lock:
            state = self._states.get(key)
            if state is None or not state.open:
                return None
            downtime = (now - state.first_seen).total_seconds()
            state.open = False
            self._persist()
            rec = self._emit(
                component, RECOVERED, INFO,
                message, {**(detail or {}), "downtime_seconds": round(downtime, 1)}, now,
            )
            if rec is not None:
                rec["downtime_seconds"] = round(downtime, 1)
            return rec

    # ----------------------------------------------------------------- internal

    def _persist(self):
        atomic_json(self._state_path,{k:dict(kind=v.kind,severity=v.severity,first_seen=v.first_seen.isoformat(),last_sent=v.last_sent.isoformat(),open=v.open) for k,v in self._states.items()})

    def _emit(self, component, kind, severity, message, detail, now, reminder=False) -> dict[str, Any]:
        record = {
            "timestamp": now.isoformat(),
            "component": component,
            "kind": kind,
            "severity": severity,
            "reminder": bool(reminder),
            "message": message,
            "detail": detail or {},
            "execution": EXECUTION,
        }
        try:
            with self.alerts_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        except OSError:
            pass
        delivery = {"status": "NO_SINK", "delivered": False}
        if self.telegram_sink is not None:
            try:
                delivery = self.telegram_sink(self._format(record))
            except Exception as exc:  # noqa: BLE001 - alert delivery must never crash the caller
                delivery = {"status": f"SINK_ERROR:{type(exc).__name__}", "delivered": False}
        record["delivery"] = delivery
        if self.incident_log is not None:
            try:
                self.incident_log.record(
                    component=component,
                    previous_state="-",
                    new_state=f"ALERT:{kind}",
                    reason=message,
                    recovery_action=(detail or {}).get("recovery_action"),
                    recovery_result=delivery.get("status"),
                    extra={"severity": severity, "reminder": reminder},
                )
            except Exception:  # noqa: BLE001
                pass
        return record

    @staticmethod
    def _format(record: dict[str, Any]) -> str:
        icons = {DEGRADED: "⚠", RECOVERY_WARNING: "\U0001f6a8", CRITICAL_ALERT: "\U0001f6a8", RECOVERED: "✅"}
        head = f"{icons.get(record['kind'], '')} WAVERUN {record['kind']}".strip()
        lines = [head, record["message"]]
        for k, v in (record.get("detail") or {}).items():
            lines.append(f"{k}: {v}")
        lines.append("execution: DISABLED")
        return "\n".join(str(x) for x in lines)
