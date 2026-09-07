from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from keyrgb.tray.controllers._power._transition_constants import DEFAULT_IDLE_FADE_DURATION_S
from keyrgb.tray.pollers.idle_power.polling import _apply_idle_action


def _mk_tray(*, effect: str = "rainbow_wave", brightness: int = 25) -> MagicMock:
    from tests.tray.fakes import make_owner_backed_mock_tray

    tray = make_owner_backed_mock_tray(
        is_off=False,
        idle_forced_off=False,
        user_forced_off=False,
        power_forced_off=False,
        dim_temp_active=False,
        dim_temp_target_brightness=None,
    )
    tray.config = SimpleNamespace(effect=effect, brightness=brightness)
    return tray


def test_turn_off_stops_engine_turns_off_and_sets_idle_forced_flag() -> None:
    tray = _mk_tray(effect="wave", brightness=25)

    _apply_idle_action(tray, action="turn_off", dim_temp_brightness=5)

    tray.engine.stop.assert_called_once()
    tray.engine.turn_off.assert_called_once_with(fade=True, fade_duration_s=DEFAULT_IDLE_FADE_DURATION_S)
    assert tray.is_off is True
    assert tray._idle_forced_off is True
    assert tray._dim_temp_active is False
    assert tray._dim_temp_target_brightness is None
    tray._refresh_ui.assert_called_once()
    assert float(tray._last_idle_turn_off_at) > 0.0


def test_turn_off_uses_soft_fade_for_reactive_per_key_effects() -> None:
    tray = _mk_tray(effect="reactive_ripple", brightness=25)
    tray.engine.kb = SimpleNamespace(set_key_colors=MagicMock())

    _apply_idle_action(tray, action="turn_off", dim_temp_brightness=5)

    tray.engine.stop.assert_called_once()
    tray.engine.turn_off.assert_called_once_with(fade=True, fade_duration_s=DEFAULT_IDLE_FADE_DURATION_S)
    assert tray.is_off is True
    assert tray._idle_forced_off is True


def test_turn_off_records_idle_turn_off_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    tray = _mk_tray(effect="wave", brightness=25)

    monkeypatch.setattr("keyrgb.tray.pollers.idle_power._action_execution.time.monotonic", lambda: 123.0)

    _apply_idle_action(tray, action="turn_off", dim_temp_brightness=5)

    assert tray._last_idle_turn_off_at == pytest.approx(123.0)


def test_turn_off_keeps_soft_fade_for_reactive_uniform_backend() -> None:
    tray = _mk_tray(effect="reactive_ripple", brightness=25)
    tray.engine.kb = SimpleNamespace()

    _apply_idle_action(tray, action="turn_off", dim_temp_brightness=5)

    tray.engine.stop.assert_called_once()
    tray.engine.turn_off.assert_called_once_with(fade=True, fade_duration_s=DEFAULT_IDLE_FADE_DURATION_S)
    assert tray.is_off is True
    assert tray._idle_forced_off is True


def test_turn_off_logs_recoverable_stop_failure_and_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    import keyrgb.tray.pollers.idle_power._actions as actions_module

    logs: list[tuple[str, str, BaseException | None]] = []

    def fake_log_throttled(_logger, key, *, interval_s, level, msg, exc=None):
        logs.append((key, msg, exc))
        return True

    tray = _mk_tray(effect="wave", brightness=25)
    tray.engine.stop.side_effect = RuntimeError("stop failed")
    monkeypatch.setattr(actions_module, "log_throttled", fake_log_throttled)

    _apply_idle_action(tray, action="turn_off", dim_temp_brightness=5)

    tray.engine.stop.assert_called_once()
    tray.engine.turn_off.assert_called_once_with(fade=True, fade_duration_s=DEFAULT_IDLE_FADE_DURATION_S)
    assert logs == [
        (
            "idle_power.turn_off.stop_engine",
            "Idle-power turn-off failed while stopping engine",
            tray.engine.stop.side_effect,
        )
    ]


def test_turn_off_propagates_unexpected_stop_failure() -> None:
    tray = _mk_tray(effect="wave", brightness=25)
    tray.engine.stop.side_effect = AssertionError("unexpected stop bug")

    with pytest.raises(AssertionError, match="unexpected stop bug"):
        _apply_idle_action(tray, action="turn_off", dim_temp_brightness=5)

    tray.engine.turn_off.assert_not_called()
    tray._refresh_ui.assert_not_called()


def test_dim_to_temp_does_nothing_if_tray_is_off() -> None:
    tray = _mk_tray(effect="wave", brightness=25)
    tray.is_off = True

    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=5)

    tray.engine.set_brightness.assert_not_called()
    assert tray._dim_temp_active is False
    assert tray._dim_temp_target_brightness is None


@pytest.mark.parametrize(
    "effect,expected_apply_to_hardware",
    [
        ("rainbow_wave", False),
        ("perkey", True),
        ("wave", True),
    ],
)
def test_dim_to_temp_uses_hw_write_only_for_non_software_effects(effect: str, expected_apply_to_hardware: bool) -> None:
    tray = _mk_tray(effect=effect, brightness=25)

    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=7)

    assert tray._dim_temp_active is True
    assert tray._dim_temp_target_brightness == 7
    tray.engine.set_brightness.assert_called_once_with(
        7,
        apply_to_hardware=expected_apply_to_hardware,
        fade=True,
        fade_duration_s=0.25,
    )


def test_dim_to_temp_uses_legacy_brightness_signature_without_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    import keyrgb.tray.pollers.idle_power._actions as actions_module

    logs: list[tuple[str, str, BaseException | None]] = []

    def fake_log_throttled(_logger, key, *, interval_s, level, msg, exc=None):
        logs.append((key, msg, exc))
        return True

    class LegacyBrightnessEngine:
        def __init__(self) -> None:
            self.calls: list[tuple[int, bool]] = []

        def set_brightness(self, brightness: int, *, apply_to_hardware: bool) -> None:
            self.calls.append((int(brightness), bool(apply_to_hardware)))

    tray = _mk_tray(effect="wave", brightness=25)
    tray.engine = LegacyBrightnessEngine()
    monkeypatch.setattr(actions_module, "log_throttled", fake_log_throttled)

    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=7)

    assert tray.engine.calls == [(7, True)]
    assert logs == []


def test_dim_to_temp_logs_recoverable_brightness_write_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import keyrgb.tray.pollers.idle_power._actions as actions_module

    logs: list[tuple[str, str, BaseException | None]] = []

    def fake_log_throttled(_logger, key, *, interval_s, level, msg, exc=None):
        logs.append((key, msg, exc))
        return True

    tray = _mk_tray(effect="wave", brightness=25)
    tray.engine.set_brightness.side_effect = RuntimeError("brightness failed")
    monkeypatch.setattr(actions_module, "log_throttled", fake_log_throttled)

    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=7)

    tray.engine.set_brightness.assert_called_once_with(
        7,
        apply_to_hardware=True,
        fade=True,
        fade_duration_s=0.25,
    )
    assert tray._dim_temp_active is True
    assert tray._dim_temp_target_brightness == 7
    assert len(logs) == 1
    assert logs[0][0] == "idle_power.set_brightness_best_effort"
    assert logs[0][1] == "Idle-power brightness update failed"
    assert isinstance(logs[0][2], RuntimeError)


def test_dim_to_temp_logs_effect_name_failure_and_falls_back_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    import keyrgb.tray.pollers.idle_power._actions as actions_module

    logs: list[tuple[str, str, BaseException | None]] = []

    def fake_log_throttled(_logger, key, *, interval_s, level, msg, exc=None):
        logs.append((key, msg, exc))
        return True

    class BadEffect:
        def __str__(self) -> str:
            raise RuntimeError("bad effect")

    tray = _mk_tray(effect=BadEffect(), brightness=25)
    monkeypatch.setattr(actions_module, "log_throttled", fake_log_throttled)

    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=7)

    tray.engine.set_brightness.assert_called_once_with(
        7,
        apply_to_hardware=True,
        fade=True,
        fade_duration_s=0.25,
    )
    assert len(logs) == 1
    assert logs[0][0] == "idle_power.dim_to_temp.effect_name"
    assert logs[0][1] == "Idle-power dim-to-temp could not read effect name; falling back to none"
    assert isinstance(logs[0][2], RuntimeError)


def test_dim_to_temp_for_reactive_effect_also_updates_perkey_brightness() -> None:
    tray = _mk_tray(effect="reactive_fade", brightness=25)
    tray.config.perkey_brightness = 50

    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=7)

    assert tray._dim_temp_active is True
    assert tray._dim_temp_target_brightness == 7
    # Reactive dim-sync uses instant (no-fade) updates to avoid blocking the
    # render loop under the RLock.  The stability guard in
    # _resolve_brightness() handles smooth visual transitions.
    tray.engine.set_brightness.assert_called_once_with(7, apply_to_hardware=False, fade=False, fade_duration_s=0.0)
    assert tray.engine.per_key_brightness == 7


def test_dim_to_temp_skips_when_owner_state_matches_and_legacy_values_are_invalid() -> None:
    from keyrgb.tray.idle_power_state import TrayIdlePowerState

    tray = SimpleNamespace(
        engine=MagicMock(),
        config=SimpleNamespace(effect="wave", brightness=25),
        is_off=False,
        _idle_forced_off=False,
        _user_forced_off=False,
        _power_forced_off=False,
        _dim_temp_active=object(),
        _dim_temp_target_brightness=object(),
        tray_idle_power_state=TrayIdlePowerState(
            dim_temp_active=True,
            dim_temp_target_brightness=7,
        ),
        _refresh_ui=MagicMock(),
        _start_current_effect=MagicMock(),
    )

    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=7)

    tray.engine.set_brightness.assert_not_called()
    assert tray.tray_idle_power_state.dim_temp_active is True
    assert tray.tray_idle_power_state.dim_temp_target_brightness == 7
