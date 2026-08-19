from __future__ import annotations

from dataclasses import dataclass

from .contracts import SetupState


@dataclass
class AudioSettings:
    enabled: bool = True
    volume: float = 1.0
    watch: bool = True
    armed: bool = True
    signal: bool = True
    cancelled: bool = True
    exit: bool = True


class TransitionAlert:
    """One local alert per state transition; backend is injectable for tests."""

    def __init__(self, settings: AudioSettings | None = None, backend=None):
        self.settings = settings or AudioSettings()
        self.backend = backend or self._windows_backend
        self.last_state = SetupState.NEUTRAL

    def transition(self, new_state: SetupState) -> bool:
        old = self.last_state
        self.last_state = new_state
        enabled = {SetupState.WATCH: self.settings.watch, SetupState.ARMED: self.settings.armed, SetupState.SIGNAL: self.settings.signal, SetupState.WATCH_CANCELLED: self.settings.cancelled, SetupState.SIGNAL_INVALIDATED: self.settings.cancelled, SetupState.EXIT: self.settings.exit}.get(new_state, False)
        if new_state == old or not self.settings.enabled or not enabled:
            return False
        self.backend(new_state, self.settings.volume)
        return True

    @staticmethod
    def _windows_backend(state: SetupState, volume: float) -> None:
        try:
            import winsound
            frequencies = {SetupState.WATCH: 660, SetupState.ARMED: 880, SetupState.SIGNAL: 1200, SetupState.WATCH_CANCELLED: 440, SetupState.SIGNAL_INVALIDATED: 440, SetupState.EXIT: 520}
            winsound.Beep(frequencies.get(state, 440), 180 if state != SetupState.SIGNAL else 350)
        except (ImportError, RuntimeError):
            # Headless/non-Windows environments remain non-fatal and visible in logs/UI.
            return
