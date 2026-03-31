from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class BatterySaverPolicy:
    """State machine for dim-on-battery and restore-on-AC.

    This is designed to be unit-testable (no threads, no IO).
    """

    enabled: bool = False
    target_brightness: int = 25
    debounce_seconds: float = 3.0

    _last_state: Optional[bool] = None
    _last_change_ts: float = 0.0
    _saved_ac_brightness: Optional[int] = None
    _applied_battery_brightness: Optional[int] = None
    _manual_override_on_battery: bool = False

    def configure(self, *, enabled: bool, target_brightness: int) -> None:
        self.enabled = bool(enabled)
        self.target_brightness = int(target_brightness)

    def update(self, *, on_ac: bool, current_brightness: int, is_off: bool, now: float) -> Optional[int]:
        """Process current inputs and return a brightness to apply, if any."""

        on_ac = bool(on_ac)
        current_brightness = int(current_brightness)

        # Track manual overrides while on battery (user brightness differs from what we set).
        if self._last_state is False and self._applied_battery_brightness is not None:
            if current_brightness != int(self._applied_battery_brightness):
                self._manual_override_on_battery = True

        if self._last_state is None:
            self._last_state = on_ac
            self._last_change_ts = float(now)
            return None

        if on_ac == self._last_state:
            return None

        # Debounce flapping.
        if float(now) - float(self._last_change_ts) < float(self.debounce_seconds):
            return None

        self._last_state = on_ac
        self._last_change_ts = float(now)

        if not self.enabled:
            # Clear any pending restore state to avoid surprise restores later.
            self._saved_ac_brightness = None
            self._applied_battery_brightness = None
            self._manual_override_on_battery = False
            return None

        if is_off:
            # User explicitly turned the keyboard off; do not fight it.
            return None

        if not on_ac:
            # AC -> Battery: dim.
            target = max(0, int(self.target_brightness))
            if current_brightness <= 0:
                return None

            # Only act if we would actually reduce brightness.
            if 0 < target < current_brightness:
                self._saved_ac_brightness = current_brightness
                self._applied_battery_brightness = target
                self._manual_override_on_battery = False
                return target
            return None

        # Battery -> AC: restore.
        restore = self._saved_ac_brightness
        self._saved_ac_brightness = None
        self._applied_battery_brightness = None
        self._manual_override_on_battery = False
        if restore is None:
            return None
        return int(restore)
