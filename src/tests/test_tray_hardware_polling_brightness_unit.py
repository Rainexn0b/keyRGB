from __future__ import annotations

from dataclasses import dataclass

from src.tray.hardware_polling import _apply_polled_hardware_state


@dataclass
class _DummyConfig:
    brightness: int


class _DummyTray:
    def __init__(self, *, brightness: int, is_off: bool, power_forced_off: bool = False):
        self.config = _DummyConfig(brightness=brightness)
        self.is_off = is_off
        self._power_forced_off = power_forced_off
        self._last_brightness = brightness
        self.refresh_count = 0

    def _refresh_ui(self) -> None:
        self.refresh_count += 1


def test_hardware_polling_does_not_persist_zero_brightness() -> None:
    tray = _DummyTray(brightness=25, is_off=False)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=25,
        last_off_state=False,
    )

    assert last_brightness == 0
    assert last_off is True

    # Config brightness is user intent / last chosen brightness and should not
    # be overwritten by transient hardware reads of 0.
    assert tray.config.brightness == 25
    assert tray.is_off is True
    assert tray.refresh_count == 1


def test_hardware_polling_persists_nonzero_brightness_and_clears_off() -> None:
    tray = _DummyTray(brightness=25, is_off=True)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=15,
        current_off=False,
        last_brightness=0,
        last_off_state=True,
    )

    assert last_brightness == 15
    assert last_off is False
    assert tray.config.brightness == 15
    assert tray.is_off is False
    assert tray.refresh_count == 1


def test_hardware_polling_ignores_forced_off_zero_changes() -> None:
    tray = _DummyTray(brightness=25, is_off=True, power_forced_off=True)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=True,
        last_brightness=25,
        last_off_state=False,
    )

    assert last_brightness == 0
    assert last_off is True

    # Don't fight forced-off state; also do not refresh.
    assert tray.config.brightness == 25
    assert tray.refresh_count == 0
