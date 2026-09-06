from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .resilience import CONFIG

# Canonical feed states (Phase 5 recovery state machine):
#   CONNECTING  -> first connect attempt in progress
#   CONNECTED   -> socket open and at least one valid frame seen (kept spelling
#                  for API/back-compat; equivalent to HEALTHY)
#   DEGRADED    -> a recoverable error occurred, retry pending
#   RECONNECTING-> actively backing off / re-establishing after a failure
#   STALE       -> socket may exist but no valid event for `feed_stale_after`
#   OFFLINE     -> no valid event for `feed_offline_after`, or too many
#                  consecutive failed connects
_ONLINE = {"CONNECTED", "HEALTHY", "LIVE", "ONLINE", "AVAILABLE", "RUNNING"}


@dataclass
class FeedHealth:
    name: str
    state: str = "OFFLINE"
    last_event_at: datetime | None = None
    reconnects: int = 0
    sequence_gaps: int = 0
    reason: str | None = None
    # --- B-2 additions -------------------------------------------------
    last_error: str | None = None
    consecutive_failures: int = 0
    recovery_level: int = 0
    connected_since: datetime | None = None
    total_events: int = 0
    last_state_change_at: datetime | None = None
    last_exchange_at: datetime | None = None

    # ------------------------------------------------------------- transitions

    def _set_state(self, state: str, reason: str | None = None) -> None:
        if state != self.state:
            self.last_state_change_at = datetime.now(UTC)
        self.state = state
        self.reason = reason

    def connecting(self) -> None:
        """A fresh connection attempt is starting."""
        if self.state != "CONNECTED":
            self._set_state("CONNECTING", "OPENING_CONNECTION")

    def event(self, received_at: datetime, max_age_seconds: float = 15.0, *, exchange_timestamp: datetime | None = None) -> None:
        """A valid frame arrived. `max_age_seconds` kept for call compatibility."""
        self.last_event_at = received_at
        self.last_exchange_at = exchange_timestamp or received_at
        self.total_events += 1
        self.consecutive_failures = 0
        self.recovery_level = 0
        if self.state != "CONNECTED":
            self.connected_since = received_at
        self._set_state("CONNECTED", None)
        if (received_at-self.last_exchange_at).total_seconds()>5:
            self._set_state('STALE','EXCHANGE_DATA_STALE')

    def disconnect(self, reason: str = "DISCONNECTED") -> None:
        """A recoverable error ended the current connection; retry pending."""
        self.state, self.reason = "DEGRADED", reason
        self.last_error = reason
        self.reconnects += 1
        self.consecutive_failures += 1
        self.connected_since = None
        self.last_state_change_at = datetime.now(UTC)
        if self.consecutive_failures >= CONFIG.feed_offline_after_failures:
            self._set_state("OFFLINE", f"{reason} (>= {CONFIG.feed_offline_after_failures} consecutive failures)")

    def reconnecting(self, attempt: int | None = None) -> None:
        """Backing off before the next connection attempt."""
        detail = f"RECONNECT_ATTEMPT_{attempt}" if attempt is not None else "RECONNECTING"
        if self.state != "OFFLINE":
            self._set_state("RECONNECTING", detail)
        else:
            self.reason = detail

    def gap(self) -> None:
        self.sequence_gaps += 1
        self.state, self.reason = "DEGRADED", "SEQUENCE_GAP_REQUIRES_RESYNC"
        self.last_error = "SEQUENCE_GAP_REQUIRES_RESYNC"
        self.last_state_change_at = datetime.now(UTC)

    def refresh(
        self,
        now: datetime | None = None,
        stale_after_seconds: float | None = None,
        offline_after_seconds: float | None = None,
    ) -> str:
        """Age-based freshness check. A 'CONNECTED' socket without recent events
        is downgraded to STALE and then OFFLINE purely by event age. Must be
        called periodically by an independent supervisor (Phase 7)."""
        stale_after = stale_after_seconds if stale_after_seconds is not None else CONFIG.feed_stale_after
        offline_after = offline_after_seconds if offline_after_seconds is not None else CONFIG.feed_offline_after
        if self.last_event_at is None:
            if self.state not in {"CONNECTING", "RECONNECTING", "OFFLINE"}:
                self._set_state("OFFLINE", "NO_EVENTS_YET")
            return self.state
        checked_at = now or datetime.now(UTC)
        age = (checked_at - self.last_event_at).total_seconds()
        if age > offline_after:
            self._set_state("OFFLINE", "NO_RECENT_EVENTS")
        elif age > stale_after and self.state in _ONLINE:
            self._set_state("STALE", "NO_RECENT_EVENTS")
        return self.state

    # --------------------------------------------------------------- read model

    def age_seconds(self, now: datetime | None = None) -> float | None:
        if self.last_event_at is None:
            return None
        checked_at = now or datetime.now(UTC)
        return max(0.0, (checked_at - self.last_event_at).total_seconds())

    def online(self) -> bool:
        return self.state in _ONLINE

    def to_dict(self, now: datetime | None = None) -> dict:
        return {
            "name": self.name,
            "state": self.state,
            "last_event_at": self.last_event_at.isoformat() if self.last_event_at else None,
            "age_seconds": self.age_seconds(now),
            "exchange_timestamp": self.last_exchange_at.isoformat() if self.last_exchange_at else None,
            "reconnects": self.reconnects,
            "reconnect_count": self.reconnects,
            "sequence_gaps": self.sequence_gaps,
            "reason": self.reason,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
            "recovery_level": self.recovery_level,
            "total_events": self.total_events,
        }
