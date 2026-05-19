from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


def _make_tray(*, power_forced_off: bool = False, transition_result: bool | None = None):
    tray = SimpleNamespace(
        config=SimpleNamespace(),
        is_off=True,
        _power_forced_off=power_forced_off,
        _start_current_effect=MagicMock(),
        _update_icon=MagicMock(),
        _update_menu=MagicMock(),
    )
    if transition_result is not None:
        tray._apply_power_source_perkey_profile_transition = MagicMock(return_value=transition_result)
    return tray


def test_activate_perkey_profile_runtime_uses_in_place_transition_without_power_marker() -> None:
    from src.core.profile.runtime_activation import activate_perkey_profile_runtime

    tray = _make_tray(transition_result=True)
    set_active_profile = MagicMock(return_value="battery")
    load_per_key_colors = MagicMock(return_value={(0, 0): (1, 2, 3)})
    apply_profile_to_config = MagicMock()

    name = activate_perkey_profile_runtime(
        tray,
        "battery",
        set_active_profile_fn=set_active_profile,
        load_per_key_colors_fn=load_per_key_colors,
        apply_profile_to_config_fn=apply_profile_to_config,
    )

    assert name == "battery"
    set_active_profile.assert_called_once_with("battery")
    load_per_key_colors.assert_called_once_with("battery")
    apply_profile_to_config.assert_called_once_with(tray.config, {(0, 0): (1, 2, 3)})
    tray._apply_power_source_perkey_profile_transition.assert_called_once_with()
    tray._start_current_effect.assert_not_called()
    tray._update_icon.assert_called_once_with()
    tray._update_menu.assert_called_once_with()
    assert tray.is_off is False
    assert not hasattr(tray, "_last_power_source_transition_at")


def test_activate_perkey_profile_runtime_marks_power_source_transition_and_restarts_on_decline() -> None:
    from src.core.profile.runtime_activation import activate_perkey_profile_runtime
    from src.tray.protocols import TrayIdlePowerState

    tray = _make_tray(transition_result=False)
    tray.tray_idle_power_state = TrayIdlePowerState()

    activate_perkey_profile_runtime(
        tray,
        "battery",
        set_active_profile_fn=lambda name: name,
        load_per_key_colors_fn=lambda _name: {(0, 0): (9, 9, 9)},
        apply_profile_to_config_fn=lambda config, colors: setattr(config, "per_key_colors", colors),
        mark_power_source_transition=True,
        monotonic_fn=lambda: 123.0,
    )

    tray._apply_power_source_perkey_profile_transition.assert_called_once_with()
    tray._start_current_effect.assert_called_once_with()
    assert tray._last_power_source_transition_at == 123.0
    assert tray._last_power_source_transition_profile_name == "battery"
    assert isinstance(tray.tray_idle_power_state, TrayIdlePowerState)
    assert tray.tray_idle_power_state.last_power_source_transition_at == 123.0
    assert tray.tray_idle_power_state.last_power_source_transition_profile_name == "battery"
    assert tray.config.per_key_colors == {(0, 0): (9, 9, 9)}


def test_activate_perkey_profile_runtime_skips_runtime_apply_while_power_forced_off() -> None:
    from src.core.profile.runtime_activation import activate_perkey_profile_runtime
    from src.tray.protocols import TrayIdlePowerState

    tray = _make_tray(power_forced_off=True, transition_result=True)
    tray.tray_idle_power_state = TrayIdlePowerState()
    apply_profile_to_config = MagicMock()

    activate_perkey_profile_runtime(
        tray,
        "default",
        set_active_profile_fn=lambda name: name,
        load_per_key_colors_fn=lambda _name: {(0, 0): (1, 2, 3)},
        apply_profile_to_config_fn=apply_profile_to_config,
        mark_power_source_transition=True,
        monotonic_fn=lambda: 42.0,
    )

    apply_profile_to_config.assert_called_once()
    tray._apply_power_source_perkey_profile_transition.assert_not_called()
    tray._start_current_effect.assert_not_called()
    tray._update_icon.assert_called_once_with()
    tray._update_menu.assert_called_once_with()
    assert tray.is_off is True
    assert tray._last_power_source_transition_at == 42.0
    assert isinstance(tray.tray_idle_power_state, TrayIdlePowerState)
    assert tray.tray_idle_power_state.last_power_source_transition_at == 42.0
