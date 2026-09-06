"""Central resilience configuration and the WAVERUN operating-state model.

Every timeout / freshness threshold used by the live collector, the feed
watchdogs, the health supervisor and the API health model lives here so there
are no magic numbers scattered across modules. Values may be overridden from the
environment with the ``WAVERUN_RES_`` prefix (e.g. ``WAVERUN_RES_WS_IDLE_TIMEOUT``).

Nothing in this module touches signal maths, thresholds or V5.3 rules. It only
describes *when a data source or an internal pipeline counts as fresh / stale /
offline* and how those component states roll up into one operating state.

Execution stays DISABLED: this module has no order or broker code path.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from enum import Enum
from typing import Any

EXECUTION = "DISABLED"


# --------------------------------------------------------------------------- config


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(float(raw))
    except ValueError:
        return default


@dataclass
class ResilienceConfig:
    """All resilience timing knobs. Seconds unless noted.

    Treat the module-level :data:`CONFIG` singleton as read-only in production
    code; it is intentionally mutable only so tests can override individual
    thresholds deterministically.
    """

    # --- websocket connect / read watchdogs (Phase 6) -----------------------
    ws_open_timeout: float = 15.0          # opening handshake hard cap
    ws_connect_timeout: float = 30.0       # outer cap around one full connect attempt
    ws_idle_timeout: float = 45.0          # no valid frame for this long -> controlled disconnect
    ws_ping_interval: float = 20.0
    ws_ping_timeout: float = 20.0

    # --- reconnect backoff (Phase 5) --------------------------------------
    reconnect_base_delay: float = 1.0
    reconnect_max_delay: float = 30.0
    feed_offline_after_failures: int = 10  # consecutive failed attempts -> feed state OFFLINE

    # --- data freshness (Phase 6) ---------------------------------------
    feed_stale_after: float = 30.0         # now - last_valid_event -> STALE
    feed_offline_after: float = 180.0      # now - last_valid_event -> OFFLINE

    # --- independent health supervisor (Phase 7) -----------------------
    supervisor_interval: float = 5.0
    startup_grace: float = 45.0            # collector counts as STARTING for this long

    # --- decision / prediction pipeline watchdog (Phase 8) ------------
    # A quiet market can legitimately produce no *qualified* signals, but the
    # per-second decision/candidate/prediction writes must keep advancing while
    # spot events are fresh. These bounds are only evaluated when the driving
    # feed (spot) is itself fresh.
    decision_stale_after: float = 180.0
    decision_offline_after: float = 600.0
    prediction_stale_after: float = 300.0
    prediction_offline_after: float = 900.0

    # --- alert escalation (Phase 11-13) ------------------------------
    alert_degraded_after: float = 120.0    # component STALE this long -> DEGRADED alert
    alert_reminder_interval: float = 1800.0  # re-alert cadence while unchanged
    alert_recovery_warning_failures: int = 3  # failed recovery attempts -> RECOVERY WARNING
    alert_critical_after: float = 300.0    # min-data-basis gone this long -> CRITICAL

    # --- auto-repair levels (Phase 9) -------------------------------
    repair_level1_max: int = 6            # internal reconnect attempts before Level 2
    repair_level2_max: int = 3            # task re-create attempts before Level 3
    repair_level3_max: int = 2            # subcomponent re-init before Level 4
    repair_cooldown: float = 120.0        # between escalations
    restart_budget: int = 3               # Level-4 collector restarts allowed per window
    restart_budget_window: float = 3600.0

    # --- disk (Phase 7) -------------------------------------------
    disk_min_free_gb: float = 5.0

    @classmethod
    def from_env(cls) -> "ResilienceConfig":
        kwargs: dict[str, Any] = {}
        for f in fields(cls):
            env_name = "WAVERUN_RES_" + f.name.upper()
            if f.type == "int" or f.name.endswith(("_failures", "_max", "_budget")):
                kwargs[f.name] = _env_int(env_name, getattr(cls, f.name))
            else:
                kwargs[f.name] = _env_float(env_name, getattr(cls, f.name))
        return cls(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CONFIG = ResilienceConfig.from_env()


# ------------------------------------------------------------------- component health


# Canonical component states. HEALTHY is the fresh/live state; the API keeps
# emitting "LIVE"/"CONNECTED" spellings for backwards compatibility via
# ``online_state`` below.
HEALTHY = "HEALTHY"
CONNECTING = "CONNECTING"
RECONNECTING = "RECONNECTING"
DEGRADED = "DEGRADED"
STALE = "STALE"
OFFLINE = "OFFLINE"
UNKNOWN = "UNKNOWN"

_ONLINE_STATES = {HEALTHY, "LIVE", "CONNECTED", "ONLINE", "AVAILABLE", "RUNNING"}
_RECOVERING_STATES = {CONNECTING, RECONNECTING, "RECOVERING"}


def is_online(state: str) -> bool:
    return str(state).upper() in _ONLINE_STATES


def is_recovering(state: str) -> bool:
    return str(state).upper() in _RECOVERING_STATES


@dataclass
class ComponentHealth:
    """One monitored component's state for the API health model (Phase 14)."""

    key: str
    state: str = UNKNOWN
    last_event_at: str | None = None
    age_seconds: float | None = None
    reconnect_count: int = 0
    last_error: str | None = None
    recovery_level: int = 0
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------- operating state


class OperatingState(str, Enum):
    STARTING = "STARTING"
    FULL_LIVE = "FULL_LIVE"
    DEGRADED_LIVE = "DEGRADED_LIVE"
    RECOVERING = "RECOVERING"
    CRITICAL = "CRITICAL"


# Which components must be HEALTHY for FULL_LIVE, and which — when not healthy —
# only degrade rather than make the system CRITICAL. Derived from the Phase 1
# feed-independence audit:
#   * binance_spot        REQUIRED  (feature/flow/L2/V5.3 data basis)
#   * decision_pipeline   REQUIRED  (the intelligence pipeline itself)
#   * prediction_persist  REQUIRED  (multi-horizon prediction store)
#   * vantage             REQUIRED  (price reference + V5.3 outcome resolution)
#   * binance_futures     OPTIONAL  (confirmation flow only)
#   * l2                  OPTIONAL  (orderbook predictor degrades cleanly)
REQUIRED_FOR_FULL_LIVE = ("binance_spot", "vantage", "feature_pipeline", "candidate_pipeline", "decision_pipeline", "prediction_persistence", "outcome_scheduler", "storage", "disk", "consumer_backpressure")
# Loss of any of these means new *decisions/signals* can no longer be produced
# on their defined data basis -> CRITICAL (never silently "LIVE").
MIN_DATA_BASIS = ("binance_spot", "decision_pipeline")


def compute_operating_state(
    components: dict[str, ComponentHealth],
    *,
    starting: bool = False,
) -> tuple[OperatingState, list[str]]:
    """Pure roll-up from component freshness. A socket object is never proof."""
    reasons: list[str] = []

    if starting:
        return OperatingState.STARTING, ["collector within startup grace window"]

    def st(key: str) -> str:
        c = components.get(key)
        return (c.state if c else UNKNOWN).upper()

    # CRITICAL: the minimum data basis for new decisions is gone / frozen.
    critical_hits = [k for k in MIN_DATA_BASIS if st(k) in {OFFLINE, DEGRADED} or (st(k) == STALE and k == "decision_pipeline")]
    if critical_hits:
        reasons += [f"{k}={st(k)}" for k in critical_hits]
        return OperatingState.CRITICAL, reasons

    # RECOVERING: something is actively being reconnected / re-initialised.
    recovering_hits = [k for k, c in components.items() if is_recovering(c.state) or c.recovery_level > 0]
    degraded_hits = [
        k for k in REQUIRED_FOR_FULL_LIVE
        if not is_online(st(k))
    ]
    optional_hits = [
        k for k in ("binance_futures", "l2")
        if st(k) in {STALE, OFFLINE, DEGRADED}
    ]

    if recovering_hits and (degraded_hits or optional_hits):
        reasons += [f"{k} recovering" for k in recovering_hits]
        reasons += [f"{k}={st(k)}" for k in degraded_hits + optional_hits]
        return OperatingState.RECOVERING, reasons

    if degraded_hits or optional_hits:
        reasons += [f"{k}={st(k)}" for k in degraded_hits + optional_hits]
        if recovering_hits:
            reasons += [f"{k} recovering" for k in recovering_hits]
        return OperatingState.DEGRADED_LIVE, reasons

    if recovering_hits:
        reasons += [f"{k} recovering" for k in recovering_hits]
        return OperatingState.RECOVERING, reasons

    return OperatingState.FULL_LIVE, ["all required components fresh"]


def api_overall_label(state: OperatingState) -> str:
    """Compatibility label for the existing ``connection`` field / dashboard."""
    return {
        OperatingState.STARTING: "STARTING",
        OperatingState.FULL_LIVE: "LIVE",
        OperatingState.DEGRADED_LIVE: "DEGRADED",
        OperatingState.RECOVERING: "RECOVERING",
        OperatingState.CRITICAL: "CRITICAL",
    }[state]


def age_seconds(last_event_at: datetime | str | None, now: datetime | None = None) -> float | None:
    if last_event_at is None:
        return None
    now = now or datetime.now(UTC)
    if isinstance(last_event_at, str):
        try:
            parsed = datetime.fromisoformat(last_event_at)
        except ValueError:
            return None
    else:
        parsed = last_event_at
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return max(0.0, (now - parsed).total_seconds())
