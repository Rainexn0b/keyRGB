from __future__ import annotations

from dataclasses import dataclass
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


def test_hardware_polling_always_dispatches_raw_invalid_high_to_render_heal(monkeypatch) -> None:
    import keyrgb.tray.pollers.hardware_polling as hp

    observed: list[int] = []

    def recover(_tray, *, current_brightness: int) -> bool:
        observed.append(int(current_brightness))
        return True

    monkeypatch.setattr(hp, "_recover_invalid_high_brightness_best_effort", recover)
    tray = _DummyTray(brightness=10, is_off=False)

    for last_brightness in (None, 10, 50):
        result = hp._apply_polled_hardware_state(
            tray,
            raw_brightness=60,
            current_brightness=50,
            current_off=False,
            last_brightness=last_brightness,
            last_off_state=False,
        )
        assert result == (50, False)

    assert observed == [60, 60, 60]
    assert tray.config.brightness == 10


def test_hardware_polling_does_not_heal_invalid_high_when_device_is_off(monkeypatch) -> None:
    import keyrgb.tray.pollers.hardware_polling as hp

    recover = MagicMock(return_value=True)
    monkeypatch.setattr(hp, "_recover_invalid_high_brightness_best_effort", recover)
    tray = _DummyTray(brightness=10, is_off=True)

    result = hp._apply_polled_hardware_state(
        tray,
        raw_brightness=60,
        current_brightness=50,
        current_off=True,
        last_brightness=50,
        last_off_state=True,
    )

    assert result == (50, True)
    recover.assert_not_called()


def test_failed_invalid_high_does_not_fall_through_to_power_blank_recovery(monkeypatch) -> None:
    import keyrgb.tray.pollers.hardware_polling as hp

    power_recover = MagicMock(return_value=True)
    monkeypatch.setattr(hp, "_recover_invalid_high_brightness_best_effort", lambda *_a, **_kw: False)
    monkeypatch.setattr(hp, "_recover_recent_power_source_blank_best_effort", power_recover)
    tray = _DummyTray(brightness=10, is_off=False)

    hp._apply_polled_hardware_state(
        tray,
        raw_brightness=60,
        current_brightness=50,
        current_off=False,
        last_brightness=50,
        last_off_state=False,
    )

    power_recover.assert_not_called()


def test_valid_hardware_read_rearms_invalid_high_recovery() -> None:
    tray = _DummyTray(brightness=10, is_off=False)
    tray.tray_idle_power_state.invalid_high_brightness_recovery_attempt_count = 3

    _apply_polled_hardware_state(
        tray,
        raw_brightness=10,
        current_brightness=10,
        current_off=False,
        last_brightness=10,
        last_off_state=False,
    )

    assert tray.tray_idle_power_state.invalid_high_brightness_recovery_attempt_count == 0
    assert tray.tray_idle_power_state.last_invalid_high_brightness_recovery_at == 0.0
    assert tray.tray_idle_power_state.invalid_high_brightness_recovery_generation is None


def test_invalid_high_heal_clears_stale_logical_off_state(monkeypatch) -> None:
    import keyrgb.tray.pollers.hardware_polling as hp
    from keyrgb.tray.deck_state import DeckState

    monkeypatch.setattr(hp, "_recover_invalid_high_brightness_best_effort", lambda *_a, **_kw: True)
    tray = _DummyTray(brightness=10, is_off=True)
    tray.tray_idle_power_state.deck_state = DeckState.RESTORING
    refreshed_states: list[tuple[bool, DeckState]] = []
    tray._refresh_ui = lambda **_kw: refreshed_states.append((bool(tray.is_off), tray.tray_idle_power_state.deck_state))

    result = hp._apply_polled_hardware_state(
        tray,
        raw_brightness=60,
        current_brightness=50,
        current_off=False,
        last_brightness=50,
        last_off_state=False,
    )

    assert result == (50, False)
    assert tray.is_off is False
    assert tray.tray_idle_power_state.deck_state is DeckState.LIT
    assert refreshed_states == [(False, DeckState.LIT)]


def test_invalid_high_heal_contains_post_state_refresh_error(monkeypatch) -> None:
    import keyrgb.tray.pollers.hardware_polling as hp

    errors: list[str] = []
    monkeypatch.setattr(hp, "_recover_invalid_high_brightness_best_effort", lambda *_a, **_kw: True)
    tray = _DummyTray(brightness=10, is_off=True)
    tray._refresh_ui = lambda **_kw: (_ for _ in ()).throw(OSError("refresh failed"))
    tray._log_exception = lambda message, exc: errors.append(message % exc)

    result = hp._apply_polled_hardware_state(
        tray,
        raw_brightness=60,
        current_brightness=50,
        current_off=False,
        last_brightness=50,
        last_off_state=False,
    )

    assert result == (50, False)
    assert tray.is_off is False
    assert errors == ["Hardware polling error: refresh failed"]


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
