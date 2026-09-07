from __future__ import annotations

import threading
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock

from keyrgb.tray.pollers.hardware_polling import _apply_polled_hardware_state


@dataclass
class _DummyConfig:
    brightness: int


class _DummyTray:
    def __init__(self, *, brightness: int, is_off: bool, power_forced_off: bool = False):
        from tests.tray.fakes import attach_idle_power_owner, make_idle_power_owner

        self.config = _DummyConfig(brightness=brightness)
        self.is_off = is_off
        self.refresh_count = 0
        self.last_animate_icon = None
        attach_idle_power_owner(
            self,
            make_idle_power_owner(
                power_forced_off=power_forced_off,
                last_brightness=brightness if brightness > 0 else 25,
            ),
        )

    def _refresh_ui(self, *, animate_icon: bool = True) -> None:
        self.refresh_count += 1
        self.last_animate_icon = bool(animate_icon)


def test_stable_zero_confirm_enters_controller_sleep_off_when_respected() -> None:
    tray = _DummyTray(brightness=25, is_off=False)
    tray.config.controller_sleep_respect = True
    stop_calls: list[str] = []
    engine = SimpleNamespace(
        stop=lambda: stop_calls.append("stop"),
        _device_mode_off=False,
        running=False,
    )
    tray.engine = engine

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=0,
        last_off_state=False,
    )

    owner = tray.tray_idle_power_state
    assert owner.controller_sleep_off is True
    assert owner.controller_sleep_off_at > 0
    assert tray.is_off is True
    assert stop_calls == ["stop"]
    # Firmware sleep must mark the engine so soft-on reasserts user mode.
    assert engine._device_mode_off is True
    assert (last_brightness, last_off) == (0, True)


def test_controller_sleep_off_is_honored_while_effect_engine_running(monkeypatch) -> None:
    """Respect-enabled controller sleep must stay dark even mid-render."""

    tray = _DummyTray(brightness=25, is_off=False)
    tray.config.controller_sleep_respect = True
    stop_calls: list[str] = []
    kb = MagicMock()
    kb.get_brightness.return_value = 8
    engine = SimpleNamespace(
        running=True,
        stop=lambda: stop_calls.append("stop"),
        _device_mode_off=False,
        kb=kb,
        kb_lock=threading.RLock(),
    )
    tray.engine = engine

    recovery_calls: list[int] = []

    def _fake_recover(_tray, *, current_brightness: int) -> bool:
        recovery_calls.append(int(current_brightness))
        return True

    monkeypatch.setattr(
        "keyrgb.tray.pollers.hardware_polling._recover_stable_zero_brightness_best_effort",
        _fake_recover,
    )

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=0,
        last_off_state=False,
    )

    owner = tray.tray_idle_power_state
    assert owner.controller_sleep_off is True
    assert tray.is_off is True
    assert stop_calls == ["stop"]
    assert engine._device_mode_off is True
    kb.turn_off.assert_called_once_with()
    assert recovery_calls == []
    assert (last_brightness, last_off) == (0, True)


def test_controller_sleep_off_keeps_native_zero_without_redundant_turn_off(monkeypatch) -> None:
    """Do not replace an intact firmware sleep with an explicit off command."""

    tray = _DummyTray(brightness=25, is_off=False)
    tray.config.controller_sleep_respect = True
    kb = MagicMock()
    kb.get_brightness.return_value = 0
    tray.engine = SimpleNamespace(
        running=True,
        stop=lambda: None,
        _device_mode_off=False,
        kb=kb,
        kb_lock=threading.RLock(),
    )
    monkeypatch.setattr(
        "keyrgb.tray.pollers.hardware_polling._recover_stable_zero_brightness_best_effort",
        lambda *_args, **_kwargs: True,
    )

    result = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=0,
        last_off_state=False,
    )

    assert result == (0, True)
    kb.turn_off.assert_not_called()


def test_controller_sleep_off_state_stays_quiet_on_zero_reads() -> None:
    tray = _DummyTray(brightness=25, is_off=True)
    tray.config.controller_sleep_respect = True
    owner = tray.tray_idle_power_state
    owner.controller_sleep_off = True
    owner.controller_sleep_off_at = 100.0

    result = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=0,
        last_off_state=True,
    )

    assert result == (0, True)
    assert owner.controller_sleep_off is True
    assert tray.refresh_count == 0


def test_nonzero_fade_sample_does_not_wake_controller_sleep_during_power_forced_off(monkeypatch) -> None:
    """Suspend turn-off must beat a poll sampled while its fade is in flight."""

    tray = _DummyTray(brightness=25, is_off=True, power_forced_off=True)
    tray.config.controller_sleep_respect = True
    owner = tray.tray_idle_power_state
    owner.controller_sleep_off = True
    owner.controller_sleep_off_at = 100.0
    start_calls: list[str] = []
    tray._start_current_effect = lambda: start_calls.append("start") or True
    monkeypatch.setattr("keyrgb.tray.pollers.hardware_polling.time.monotonic", lambda: 101.0)

    result = _apply_polled_hardware_state(
        tray,
        current_brightness=3,
        current_off=False,
        last_brightness=0,
        last_off_state=True,
    )

    assert result == (3, True)
    assert owner.controller_sleep_off is True
    assert owner.controller_sleep_off_at == 100.0
    assert tray.is_off is True
    assert start_calls == []


def test_nonzero_brightness_register_stays_asleep_when_hardware_is_off() -> None:
    """Corrective turn_off may retain brightness but must remain logically dark."""

    tray = _DummyTray(brightness=25, is_off=True)
    tray.config.controller_sleep_respect = True
    owner = tray.tray_idle_power_state
    owner.controller_sleep_off = True
    owner.controller_sleep_off_at = 100.0

    result = _apply_polled_hardware_state(
        tray,
        current_brightness=8,
        current_off=True,
        last_brightness=0,
        last_off_state=True,
    )

    assert result == (8, True)
    assert owner.controller_sleep_off is True
    assert tray.is_off is True
