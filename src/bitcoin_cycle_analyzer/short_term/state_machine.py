from __future__ import annotations

from dataclasses import dataclass

from .contracts import SetupState


@dataclass
class StateMachine:
    state: SetupState = SetupState.NEUTRAL
    changed_at: object | None = None

    def update(self, quality: dict, fused: dict, timestamp) -> tuple[SetupState, SetupState]:
        previous = self.state
        edge = quality.get("status") == "EDGE"
        direction = max(float(fused.get("p_up", .5)), float(fused.get("p_down", .5)))
        if self.state in (SetupState.NEUTRAL, SetupState.WATCH_CANCELLED, SetupState.SIGNAL_INVALIDATED):
            self.state = SetupState.WATCH if direction >= .56 else SetupState.NEUTRAL
        elif self.state == SetupState.WATCH:
            self.state = SetupState.ARMED if direction >= .64 else SetupState.WATCH_CANCELLED if direction < .52 else SetupState.WATCH
        elif self.state == SetupState.ARMED:
            self.state = SetupState.SIGNAL if edge and direction >= .68 else SetupState.WATCH_CANCELLED if direction < .52 else SetupState.ARMED
        elif self.state == SetupState.SIGNAL:
            self.state = SetupState.SIGNAL_INVALIDATED if not edge else SetupState.SIGNAL
        if self.state != previous:
            self.changed_at = timestamp
        return previous, self.state
