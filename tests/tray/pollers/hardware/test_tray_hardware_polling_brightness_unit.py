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


def test_hardware_polling_does_not_mark_off_from_zero_brightness_without_off_state() -> None:
    tray = _DummyTray(brightness=25, is_off=False)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=25,
        last_off_state=False,
    )

    assert last_brightness == 0
    assert last_off is False

    # Config brightness is user intent / last chosen brightness and should not
    # be overwritten by transient hardware reads of 0.
    assert tray.config.brightness == 25
    assert tray.is_off is False
    assert tray.refresh_count == 0


def test_fresh_zero_transition_arms_pending_zero_confirm() -> None:
    tray = _DummyTray(brightness=25, is_off=False)

    _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=25,
        last_off_state=False,
    )

    assert tray.tray_idle_power_state.pending_zero_confirm_at > 0


def test_fresh_zero_transition_with_forced_off_does_not_arm_pending_zero_confirm() -> None:
    from tests.tray.fakes import attach_idle_power_owner, make_idle_power_owner

    tray = _DummyTray(brightness=25, is_off=True)
    attach_idle_power_owner(
        tray,
        make_idle_power_owner(user_forced_off=True, last_brightness=25),
    )

    _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=25,
        last_off_state=False,
    )

    assert tray.tray_idle_power_state.pending_zero_confirm_at == 0


def test_stable_zero_confirm_poll_clears_pending_zero_confirm() -> None:
    tray = _DummyTray(brightness=25, is_off=False)
    tray.tray_idle_power_state.pending_zero_confirm_at = 100.0

    _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=0,
        last_off_state=False,
    )

    assert tray.tray_idle_power_state.pending_zero_confirm_at == 0


def test_nonzero_read_clears_pending_zero_confirm() -> None:
    tray = _DummyTray(brightness=25, is_off=False)
    tray.tray_idle_power_state.pending_zero_confirm_at = 100.0

    _apply_polled_hardware_state(
        tray,
        current_brightness=15,
        current_off=False,
        last_brightness=15,
        last_off_state=False,
    )

    assert tray.tray_idle_power_state.pending_zero_confirm_at == 0


def test_hardware_polling_marks_off_when_zero_brightness_matches_off_state() -> None:
    tray = _DummyTray(brightness=25, is_off=False)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=True,
        last_brightness=25,
        last_off_state=False,
    )

    assert last_brightness == 0
    assert last_off is True
    assert tray.config.brightness == 25
    assert tray.is_off is True
    assert tray.refresh_count == 1
    assert tray.last_animate_icon is False


def test_hardware_polling_does_not_persist_nonzero_brightness_and_clears_off() -> None:
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
    # Brightness reads from hardware should not overwrite the user's persisted
    # tray selection.
    assert tray.config.brightness == 25
    assert tray.is_off is False
    assert tray.refresh_count == 1
    assert tray.last_animate_icon is False


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


def test_hardware_polling_does_not_convert_small_brightness_values() -> None:
    tray = _DummyTray(brightness=25, is_off=False)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=7,
        current_off=False,
        last_brightness=25,
        last_off_state=False,
    )

    # No scale conversion; value is used as-is (within 0..50 range).
    assert last_brightness == 7
    assert last_off is False
    # But do not persist into config.
    assert tray.config.brightness == 25
    assert tray.refresh_count == 1
    assert tray.last_animate_icon is False


def test_hardware_polling_clamps_over_50_brightness_values() -> None:
    tray = _DummyTray(brightness=25, is_off=False)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=80,
        current_off=False,
        last_brightness=25,
        last_off_state=False,
    )

    # No scale conversion; clamp into 0..50.
    assert last_brightness == 50
    assert last_off is False


def test_hardware_polling_does_not_scale_up_when_config_expects_low_value() -> None:
    """Regression: values 1..10 can be valid on the 0..50 scale.

    If the backend reports 10 and the config is already 10, we must not treat it
    as a 0..10 scale value and rewrite it to 50.
    """

    tray = _DummyTray(brightness=10, is_off=False)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=10,
        current_off=False,
        last_brightness=15,
        last_off_state=False,
    )

    assert tray.config.brightness == 10
    assert last_brightness == 10
    assert last_off is False
    assert tray.refresh_count == 1
    assert tray.last_animate_icon is False


def test_hardware_polling_recovers_recent_power_source_blank_without_marking_off(monkeypatch) -> None:
    tray = _DummyTray(brightness=25, is_off=False)
    tray._last_power_source_transition_at = 100.0
    tray._apply_power_source_perkey_profile_transition = MagicMock(return_value=True)

    monkeypatch.setattr("keyrgb.tray.pollers.hardware_polling.time.monotonic", lambda: 101.0)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=25,
        last_off_state=False,
    )

    tray._apply_power_source_perkey_profile_transition.assert_called_once_with()
    assert last_brightness == 0
    assert last_off is False
    assert tray.is_off is False
    assert tray.refresh_count == 1
    assert tray.last_animate_icon is False
    assert tray.tray_idle_power_state.hidden_perkey_restore_brightness_hint is None
    assert tray.tray_idle_power_state.hidden_perkey_restore_device_off_hint is None
    assert tray.tray_idle_power_state.last_power_source_blank_recovery_at == 101.0


def test_hardware_polling_recovers_stable_zero_without_off_state(monkeypatch) -> None:
    tray = _DummyTray(brightness=25, is_off=False)
    tray._start_current_effect = MagicMock()

    monkeypatch.setattr("keyrgb.tray.pollers.hardware_polling.time.monotonic", lambda: 200.0)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=0,
        last_off_state=False,
    )

    tray._start_current_effect.assert_called_once_with()
    assert last_brightness == 0
    assert last_off is False
    assert tray.is_off is False
    assert tray.refresh_count == 1
    assert tray.last_animate_icon is False
    assert tray.tray_idle_power_state.hidden_perkey_restore_brightness_hint is None
    assert tray.tray_idle_power_state.hidden_perkey_restore_device_off_hint is None
    assert tray.tray_idle_power_state.last_hardware_blank_recovery_at == 200.0


def test_hardware_polling_does_not_recover_stable_zero_when_forced_off(monkeypatch) -> None:
    tray = _DummyTray(brightness=25, is_off=True, power_forced_off=True)
    tray._start_current_effect = MagicMock()

    monkeypatch.setattr("keyrgb.tray.pollers.hardware_polling.time.monotonic", lambda: 200.0)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=0,
        last_off_state=False,
    )

    tray._start_current_effect.assert_not_called()
    assert last_brightness == 0
    assert last_off is True
    assert tray.is_off is True
    assert tray.refresh_count == 0


def test_hardware_polling_stable_zero_recovery_obeys_cooldown(monkeypatch) -> None:
    tray = _DummyTray(brightness=25, is_off=False)
    tray._last_hardware_blank_recovery_at = 198.0
    tray._start_current_effect = MagicMock()

    monkeypatch.setattr("keyrgb.tray.pollers.hardware_polling.time.monotonic", lambda: 200.0)

    _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=0,
        last_off_state=False,
    )

    tray._start_current_effect.assert_not_called()
    assert tray.refresh_count == 0
    assert tray.tray_idle_power_state.last_hardware_blank_recovery_at == 198.0


def test_hardware_polling_keeps_recent_power_source_blank_in_recovery_window(monkeypatch) -> None:
    tray = _DummyTray(brightness=25, is_off=False)
    tray._last_power_source_transition_at = 100.0

    monkeypatch.setattr("keyrgb.tray.pollers.hardware_polling.time.monotonic", lambda: 101.0)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=True,
        last_brightness=0,
        last_off_state=False,
    )

    assert last_brightness == 0
    assert last_off is False
    assert tray.is_off is False
    assert tray.refresh_count == 0


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


def test_controller_sleep_off_suppressed_immediately_after_idle_restore(monkeypatch) -> None:
    """A post-restore firmware zero must not stick the deck dark again.

    Journaled failure: idle_power:restore lit the board, then ~8s later a
    transient brightness=0 re-entered controller_sleep_off and only a manual
    tray Turn On recovered it.
    """

    import time

    from keyrgb.tray.idle_power_state import set_idle_power_state_field
    from keyrgb.tray.pollers.idle_power._constants import POST_RESUME_IDLE_ACTION_SUPPRESSION_S

    tray = _DummyTray(brightness=25, is_off=False)
    tray.config.controller_sleep_respect = True
    set_idle_power_state_field(
        tray,
        attr_name="_last_resume_at",
        state_name="last_resume_at",
        value=time.monotonic() - (POST_RESUME_IDLE_ACTION_SUPPRESSION_S / 2.0),
    )

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
    assert owner.controller_sleep_off is False
    assert tray.is_off is False
    assert recovery_calls == [0]
    assert (last_brightness, last_off) == (0, False)


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


def test_nonzero_read_while_controller_sleep_off_restarts_stopped_effect(monkeypatch) -> None:
    tray = _DummyTray(brightness=25, is_off=True)
    tray.config.controller_sleep_respect = True
    owner = tray.tray_idle_power_state
    owner.controller_sleep_off = True
    owner.controller_sleep_off_at = 100.0
    start_calls: list[str] = []
    tray._start_current_effect = lambda: start_calls.append("start") or True
    monkeypatch.setattr("keyrgb.tray.pollers.hardware_polling.time.monotonic", lambda: 101.0)

    last_brightness, _last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=25,
        current_off=False,
        last_brightness=0,
        last_off_state=True,
    )

    assert owner.controller_sleep_off is False
    assert tray.is_off is False
    assert last_brightness == 25
    assert owner.last_resume_at == 101.0
    assert start_calls == ["start"]


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
