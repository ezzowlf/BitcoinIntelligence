"""Append-only production incident log (Phase 16).

Every operating-state / component-state transition and every recovery action is
written here so that after the fact it is possible to reconstruct exactly:
what failed, when it was detected, what WAVERUN did about it, and when real data
flow was restored.

No secrets are ever written. Execution stays DISABLED.
"""

from __future__ import annotations

import json
import threading
import re
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXECUTION = "DISABLED"

_SECRET_HINTS = ("token", "secret", "password", "authorization", "bearer", "api_key", "apikey", "chat_id", "cookie")


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("<redacted>" if any(h in str(k).lower() for h in _SECRET_HINTS) else _scrub(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in value]
    if isinstance(value,str):
        return re.sub(r'(?i)((?:token|secret|password|authorization|bearer|api_key|apikey|chat_id|cookie)\s*[=: ]\s*)[^\s,;&]+',r'\1<redacted>',value)
    return value


class IncidentLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record(
        self,
        *,
        component: str,
        previous_state: str,
        new_state: str,
        reason: str,
        last_event_age: float | None = None,
        recovery_action: str | None = None,
        recovery_result: str | None = None,
        operating_state: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "component": component,
            "previous_state": previous_state,
            "new_state": new_state,
            "reason": reason,
            "last_event_age": None if last_event_age is None else round(float(last_event_age), 1),
            "recovery_action": recovery_action,
            "recovery_result": recovery_result,
            "operating_state": operating_state,
            "execution": EXECUTION,
        }
        if extra:
            row["extra"] = _scrub(extra)
        row=_scrub(row)
        line = json.dumps(row, sort_keys=True, default=str)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return row

    def tail(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as handle:
            lines = list(deque(handle,maxlen=limit))
        out: list[dict[str, Any]] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out
