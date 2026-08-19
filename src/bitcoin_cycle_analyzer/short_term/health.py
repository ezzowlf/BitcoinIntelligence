from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class FeedHealth:
    name: str
    state: str = "OFFLINE"
    last_event_at: datetime | None = None
    reconnects: int = 0
    sequence_gaps: int = 0
    reason: str | None = None

    def event(self, received_at: datetime, max_age_seconds: float = 15.0) -> None:
        self.last_event_at = received_at
        self.state = "CONNECTED"
        self.reason = None

    def disconnect(self, reason: str = "DISCONNECTED") -> None:
        self.state, self.reason = "DEGRADED", reason
        self.reconnects += 1

    def gap(self) -> None:
        self.sequence_gaps += 1
        self.state, self.reason = "DEGRADED", "SEQUENCE_GAP_REQUIRES_RESYNC"

    def refresh(self, now: datetime | None = None, stale_after_seconds: float = 15.0) -> str:
        if self.last_event_at is None:
            return self.state
        checked_at = now or datetime.now(UTC)
        age = (checked_at - self.last_event_at).total_seconds()
        if age > stale_after_seconds:
            self.state, self.reason = "STALE", "NO_RECENT_EVENTS"
        return self.state

    def to_dict(self) -> dict:
        return {"name": self.name, "state": self.state, "last_event_at": self.last_event_at.isoformat() if self.last_event_at else None, "reconnects": self.reconnects, "sequence_gaps": self.sequence_gaps, "reason": self.reason}
