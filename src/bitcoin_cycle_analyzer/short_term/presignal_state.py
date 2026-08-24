"""Deterministic pre-signal state machine for the WAVERUN web UI.

This is a *presentation* layer. It reads structured evidence that the engine and
the frozen V5.3 Fast V2 forward collector already produce and folds it into one
calm, slow-moving state label:

    RUHIG -> BEOBACHTEN -> SETUP_ENTSTEHT -> SIGNAL_NAHE -> TESTSIGNAL

with a separate ``INVALIDIERT`` transition out of the three build-up states when
the build-up collapses before a test signal is reached.

Hard boundaries (see the module guardrails in ``web_api.py``):

* It never computes a signal, never selects a V5.3 candidate, never vetoes one
  and never touches forward-validation statistics. ``TESTSIGNAL`` only mirrors a
  candidate the frozen collector has *already* written.
* Execution stays DISABLED. No order code path exists here.

Evidence groups
---------------
Five independent build-up groups are derived from fields the API already reads:

``richtung``   direction_bias is LONG/SHORT *and* the matching pressure score is
               at least ``PRESSURE_MIN`` (35 of 100). A bias without pressure is
               noise, so both halves are required.
``momentum``   |60s return| >= ``RETURN_MIN`` (0.03 %) in the biased direction,
               or range_expansion >= ``RANGE_EXPANSION_MIN`` (1.3). Either is an
               independent sign that the move has physical size.
``futures``    flow_agreement == CONFIRMED (spot and futures order flow point the
               same way).
``orderbuch``  the L2 imbalance is aligned with the direction bias.
``zustand``    the engine's own setup state machine is at WATCH/ARMED/SIGNAL.

Two further conditions are gates on the way into SIGNAL_NAHE only, deliberately
*not* build-up groups:

``scharf``          the engine's setup state is ARMED or SIGNAL. WATCH alone is a
                    build-up, never "one condition away from a trigger".
``datenqualitaet``  all sources online *and* the Vantage tick is LIVE. This is
                    true in a dead-calm market, so counting it as a build-up
                    group would permanently lift the UI off RUHIG; as a gate it
                    stops stale data from being presented as "nearly triggering".

Raw classification per evaluation
---------------------------------
* fresh accepted V5.3 candidate (age <= ``TESTSIGNAL_MAX_AGE_S``) -> TESTSIGNAL
* at most one of the seven required conditions missing      -> SIGNAL_NAHE
* three or more build-up groups satisfied                   -> SETUP_ENTSTEHT
* one or two build-up groups satisfied                      -> BEOBACHTEN
* none                                                      -> RUHIG

Hysteresis
----------
Evaluations arrive at roughly 1 Hz. A raw classification is only promoted to the
*confirmed* state once it has held for ``UPGRADE_TICKS`` consecutive evaluations
and ``UPGRADE_SECONDS``; a downgrade needs the much longer ``DOWNGRADE_TICKS`` /
``DOWNGRADE_SECONDS``. Upgrades are kept short so a real build-up is not shown
too late, downgrades long so a single missing tick cannot erase a build-up.
``INVALIDIERT`` is held for ``INVALIDATED_HOLD_S`` and then decays to RUHIG.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

# --------------------------------------------------------------------- tuning

PRESSURE_MIN = 35.0
RETURN_MIN = 0.0003
RANGE_EXPANSION_MIN = 1.3
TESTSIGNAL_MAX_AGE_S = 300.0

UPGRADE_TICKS = 3
UPGRADE_SECONDS = 2.0
DOWNGRADE_TICKS = 8
DOWNGRADE_SECONDS = 7.0
INVALIDATED_HOLD_S = 30.0

TIMELINE_SIZE = 20
ALERT_BUFFER_SIZE = 20

STATES = ("RUHIG", "BEOBACHTEN", "SETUP_ENTSTEHT", "SIGNAL_NAHE", "TESTSIGNAL", "INVALIDIERT")
BUILD_UP_STATES = ("BEOBACHTEN", "SETUP_ENTSTEHT", "SIGNAL_NAHE")
_RANK = {"RUHIG": 0, "INVALIDIERT": 0, "BEOBACHTEN": 1, "SETUP_ENTSTEHT": 2, "SIGNAL_NAHE": 3, "TESTSIGNAL": 4}

BUILD_UP_GROUPS = ("richtung", "momentum", "futures", "orderbuch", "zustand")
REQUIRED_CONDITIONS = (*BUILD_UP_GROUPS, "scharf", "datenqualitaet")

CONDITION_LABELS = {
    "richtung": "Eindeutige Richtung mit Druck",
    "momentum": "Bewegung hat Größe",
    "futures": "Futures bestätigen den Spot",
    "orderbuch": "Orderbuch stützt die Richtung",
    "zustand": "Engine-Zustand mindestens BEOBACHTUNG",
    "scharf": "Engine-Zustand SCHARF (ARMED/SIGNAL)",
    "datenqualitaet": "Datenqualität ausreichend",
}

# What the user is told is still missing, in the order we blame it.
MISSING_TEXT = {
    "richtung": "die eindeutige Richtung",
    "momentum": "die Größe der Bewegung",
    "futures": "die Futures-Bestätigung",
    "orderbuch": "die Orderbuch-Bestätigung",
    "zustand": "die Freigabe der Engine",
    "scharf": "die Scharfschaltung der Engine",
    "datenqualitaet": "eine saubere Datenlage",
}

ALERT_SEVERITY = {
    "RUHIG": "NONE",
    "BEOBACHTEN": "QUIET",
    "SETUP_ENTSTEHT": "NORMAL",
    "SIGNAL_NAHE": "STRONG",
    "TESTSIGNAL": "CRITICAL",
    "INVALIDIERT": "QUIET",
}
ALERT_SOUND = {"SIGNAL_NAHE", "TESTSIGNAL"}

STATE_LABELS = {
    "RUHIG": "RUHIG",
    "BEOBACHTEN": "BEOBACHTEN",
    "SETUP_ENTSTEHT": "SETUP ENTSTEHT",
    "SIGNAL_NAHE": "SIGNAL NAHE",
    "TESTSIGNAL": "TESTSIGNAL",
    "INVALIDIERT": "INVALIDIERT",
}

_DIRECTION_WORD = {"LONG": "Kaufdruck", "SHORT": "Verkaufsdruck"}
_SIDE_WORD = {"LONG": "LONG", "SHORT": "SHORT"}


# -------------------------------------------------------------------- evidence


@dataclass(frozen=True)
class Evidence:
    """One evaluation's worth of already-computed engine facts."""

    setup_state: str = "NEUTRAL"
    direction: str = "NEUTRAL"
    pressure: float = 0.0
    flow_agreement: str = "NEUTRAL"
    l2_aligned: bool | None = None
    return_60s: float | None = None
    range_expansion: float | None = None
    sources_online: bool = True
    price_live: bool = True
    contradictions: tuple[str, ...] = ()
    v5_3_candidate_age_s: float | None = None
    v5_3_candidate_accepted: bool = False

    def conditions(self) -> dict[str, bool]:
        directional = self.direction in {"LONG", "SHORT"}
        richtung = directional and self.pressure >= PRESSURE_MIN

        momentum = False
        if directional and isinstance(self.return_60s, (int, float)):
            signed = self.return_60s if self.direction == "LONG" else -self.return_60s
            momentum = signed >= RETURN_MIN
        if isinstance(self.range_expansion, (int, float)) and self.range_expansion >= RANGE_EXPANSION_MIN:
            momentum = momentum or directional

        return {
            "richtung": richtung,
            "momentum": momentum,
            "futures": self.flow_agreement == "CONFIRMED",
            "orderbuch": bool(self.l2_aligned),
            "zustand": self.setup_state in {"WATCH", "ARMED", "SIGNAL"},
            "scharf": self.setup_state in {"ARMED", "SIGNAL"},
            "datenqualitaet": bool(self.sources_online and self.price_live),
        }

    def is_test_signal(self) -> bool:
        age = self.v5_3_candidate_age_s
        return (
            self.v5_3_candidate_accepted
            and isinstance(age, (int, float))
            and 0 <= age <= TESTSIGNAL_MAX_AGE_S
        )

    def is_hard_invalidation(self) -> bool:
        return self.setup_state in {"WATCH_CANCELLED", "SIGNAL_INVALIDATED"}


def classify(evidence: Evidence) -> tuple[str, dict[str, bool]]:
    """Raw (unsmoothed) state for a single evaluation."""
    conditions = evidence.conditions()
    if evidence.is_test_signal():
        return "TESTSIGNAL", conditions
    missing = [key for key in REQUIRED_CONDITIONS if not conditions[key]]
    if len(missing) <= 1:
        return "SIGNAL_NAHE", conditions
    satisfied_build = sum(1 for key in BUILD_UP_GROUPS if conditions[key])
    if satisfied_build >= 3:
        return "SETUP_ENTSTEHT", conditions
    if satisfied_build >= 1:
        return "BEOBACHTEN", conditions
    return "RUHIG", conditions


# ------------------------------------------------------------------- narration


def _missing_keys(conditions: dict[str, bool]) -> list[str]:
    return [key for key in REQUIRED_CONDITIONS if not conditions.get(key)]


def missing_trigger(conditions: dict[str, bool]) -> str | None:
    """The single identifiable condition still blocking a trigger, if there is one."""
    missing = _missing_keys(conditions)
    if len(missing) == 1:
        return missing[0]
    if not missing:
        return "v5_3_ausloeser"
    return None


def headline(state: str, evidence: Evidence, conditions: dict[str, bool]) -> str:
    """One calm German line. Deterministic, no model, no free text."""
    direction = evidence.direction
    pressure_word = _DIRECTION_WORD.get(direction, "Druck")
    side = _SIDE_WORD.get(direction, "")

    if state == "RUHIG":
        return "Der Markt zeigt aktuell keine klare kurzfristige Gelegenheit."
    if state == "INVALIDIERT":
        return "Der Aufbau ist zerfallen. Es liegt keine Gelegenheit mehr vor."
    if state == "TESTSIGNAL":
        return (
            f"{side or 'SHORT'}-Testsignal der eingefrorenen V5.3-Hypothese. "
            "Nur Beobachtung — die Ausführung ist deaktiviert."
        )
    if state == "SIGNAL_NAHE":
        key = missing_trigger(conditions)
        if key == "v5_3_ausloeser":
            return f"{side}-Signal nahe. Alle Bedingungen sind erfüllt, nur der V5.3-Auslöser fehlt noch."
        return f"{side}-Signal nahe. Nur {MISSING_TEXT.get(key, 'eine Bedingung')} fehlt noch."

    confirmed = [CONDITION_LABELS[k] for k in BUILD_UP_GROUPS if conditions.get(k)]
    missing = [MISSING_TEXT[k] for k in BUILD_UP_GROUPS if not conditions.get(k)]
    if state == "SETUP_ENTSTEHT":
        parts = [f"{pressure_word} nimmt zu."]
        if confirmed:
            parts.append(f"Bestätigt: {', '.join(confirmed)}.")
        if missing:
            parts.append(f"Es fehlt noch {', '.join(missing)}.")
        return " ".join(parts)
    # BEOBACHTEN
    if confirmed:
        return f"Erste Auffälligkeit: {', '.join(confirmed)}. Noch kein Setup."
    return "Erste Auffälligkeit im Markt. Noch kein Setup."


def transition_reason(previous: str, state: str, conditions: dict[str, bool]) -> str:
    if state == "RUHIG":
        return "Keine gerichtete Auffälligkeit mehr."
    if state == "INVALIDIERT":
        return "Aufbau zerfallen, bevor ein Testsignal erreicht wurde."
    if state == "TESTSIGNAL":
        return "Eingefrorenes V5.3-Kandidatensignal wurde erfasst."
    satisfied = [CONDITION_LABELS[k] for k in BUILD_UP_GROUPS if conditions.get(k)]
    joined = ", ".join(satisfied) if satisfied else "keine"
    if state == "SIGNAL_NAHE":
        key = missing_trigger(conditions)
        rest = "nur der V5.3-Auslöser" if key == "v5_3_ausloeser" else f"nur noch {MISSING_TEXT.get(key, 'eine Bedingung')}"
        return f"Fast alle Bedingungen erfüllt, es fehlt {rest}."
    if _RANK[state] > _RANK.get(previous, 0):
        return f"Belege bauen sich auf: {joined}."
    return f"Belege gehen zurück, bestätigt bleibt: {joined}."


# --------------------------------------------------------------- state machine


@dataclass
class _Pending:
    state: str = "RUHIG"
    ticks: int = 0
    since: float = 0.0


class PreSignalStateMachine:
    """Hysteresis-smoothed state machine with an in-memory event/alert history.

    Thread-safe: ``/api/state`` and ``/api/stream`` both drive it from the same
    process. History lives for the lifetime of the process only.
    """

    def __init__(self, clock: Callable[[], float] | None = None):
        self._clock = clock or (lambda: datetime.now(UTC).timestamp())
        self._lock = threading.Lock()
        now = self._clock()
        self.state = "RUHIG"
        self.entered_at = now
        self._pending = _Pending("RUHIG", 0, now)
        self._conditions: dict[str, bool] = {key: False for key in REQUIRED_CONDITIONS}
        self._evidence = Evidence()
        self._peak = "RUHIG"
        self._timeline: deque[dict[str, Any]] = deque(maxlen=TIMELINE_SIZE)
        self._alerts: deque[dict[str, Any]] = deque(maxlen=ALERT_BUFFER_SIZE)
        self._alert_ids: set[str] = set()

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _iso(stamp: float) -> str:
        return datetime.fromtimestamp(stamp, tz=UTC).isoformat()

    def _enter(self, state: str, now: float, conditions: dict[str, bool]) -> None:
        previous = self.state
        if state == previous:
            return
        reason = transition_reason(previous, state, conditions)
        self.state = state
        self.entered_at = now
        if state in BUILD_UP_STATES or state == "TESTSIGNAL":
            self._peak = state if _RANK[state] > _RANK.get(self._peak, 0) else self._peak
        else:
            self._peak = "RUHIG"
        event = {
            "timestamp": self._iso(now),
            "from": previous,
            "to": state,
            "label": STATE_LABELS[state],
            "reason": reason,
            "severity": ALERT_SEVERITY[state],
        }
        self._timeline.appendleft(event)
        self._emit_alert(state, now, reason)

    def _emit_alert(self, state: str, now: float, reason: str) -> None:
        severity = ALERT_SEVERITY[state]
        if severity == "NONE":
            return
        # One alert per (state, entered_at) -- never repeated while the state holds.
        alert_id = f"{state}@{self._iso(now)}"
        if alert_id in self._alert_ids:
            return
        self._alert_ids.add(alert_id)
        self._alerts.appendleft({
            "id": alert_id,
            "state": state,
            "severity": severity,
            "sound": state in ALERT_SOUND,
            "title": f"WAVERUN — {STATE_LABELS[state]}",
            "body": reason,
            "timestamp": self._iso(now),
        })

    # ------------------------------------------------------------------- step

    def update(self, evidence: Evidence) -> dict[str, Any]:
        with self._lock:
            now = self._clock()
            raw, conditions = classify(evidence)
            self._conditions = conditions
            self._evidence = evidence

            # A hard engine invalidation short-circuits the build-up immediately.
            if evidence.is_hard_invalidation() and self.state in BUILD_UP_STATES:
                self._enter("INVALIDIERT", now, conditions)
                self._pending = _Pending("INVALIDIERT", 0, now)
                return self._snapshot(now)

            # INVALIDIERT is a transient notice; it decays back to RUHIG.
            if self.state == "INVALIDIERT" and now - self.entered_at >= INVALIDATED_HOLD_S:
                self._enter("RUHIG", now, conditions)

            target = raw
            # A collapse out of a build-up is reported as INVALIDIERT, not as a
            # silent slide back to RUHIG.
            if raw == "RUHIG" and self.state in BUILD_UP_STATES:
                target = "INVALIDIERT"

            if target != self._pending.state:
                self._pending = _Pending(target, 1, now)
            else:
                self._pending.ticks += 1

            if target != self.state:
                upgrade = _RANK[target] > _RANK.get(self.state, 0)
                need_ticks = UPGRADE_TICKS if upgrade else DOWNGRADE_TICKS
                need_seconds = UPGRADE_SECONDS if upgrade else DOWNGRADE_SECONDS
                held = now - self._pending.since
                if self._pending.ticks >= need_ticks and held >= need_seconds:
                    self._enter(target, now, conditions)

            return self._snapshot(now)

    # -------------------------------------------------------------- read model

    def _snapshot(self, now: float) -> dict[str, Any]:
        conditions = self._conditions
        rows = [
            {
                "key": key,
                "label": CONDITION_LABELS[key],
                "status": "MET" if conditions.get(key) else "MISSING",
            }
            for key in REQUIRED_CONDITIONS
        ]
        trigger = missing_trigger(conditions) if self.state in {"SIGNAL_NAHE", "TESTSIGNAL"} else None
        return {
            "state": self.state,
            "label": STATE_LABELS[self.state],
            "direction": self._evidence.direction,
            "entered_at": self._iso(self.entered_at),
            "seconds_in_state": round(max(0.0, now - self.entered_at), 1),
            "headline": headline(self.state, self._evidence, conditions),
            "severity": ALERT_SEVERITY[self.state],
            "missing_trigger": trigger,
            "missing_trigger_label": None
            if trigger is None
            else ("V5.3-Auslöser" if trigger == "v5_3_ausloeser" else CONDITION_LABELS[trigger]),
            "conditions": rows,
            "satisfied": [key for key in REQUIRED_CONDITIONS if conditions.get(key)],
            "missing": _missing_keys(conditions),
            "pending_state": self._pending.state,
            "pending_ticks": self._pending.ticks,
            "show_checklist": self.state in {"SIGNAL_NAHE", "TESTSIGNAL"},
            "timeline": list(self._timeline),
            "execution": "DISABLED",
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._snapshot(self._clock())

    def alerts(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._alerts)
