from __future__ import annotations

from types import SimpleNamespace

from src.tray.idle_power_state import (
    TrayIdlePowerState,
    any_forced_off,
    dim_temp_target_brightness,
    is_dim_temp_active,
    is_system_forced_off,
    is_user_forced_off,
    read_forced_off_flags,
    read_last_brightness,
    read_last_resume_at,
    set_last_brightness,
)


def test_read_forced_off_flags_from_legacy_attrs() -> None:
    tray = SimpleNamespace(
        _user_forced_off=True,
        _power_forced_off=False,
        _idle_forced_off=True,
        tray_idle_power_state=TrayIdlePowerState(),
    )
    assert read_forced_off_flags(tray) == (True, False, True)
    assert any_forced_off(tray) is True
    assert is_user_forced_off(tray) is True
    assert is_system_forced_off(tray) is True


def test_read_forced_off_flags_from_owner_when_legacy_missing() -> None:
    tray = SimpleNamespace(
        tray_idle_power_state=TrayIdlePowerState(
            user_forced_off=False,
            power_forced_off=True,
            idle_forced_off=False,
        )
    )
    assert read_forced_off_flags(tray) == (False, True, False)
    assert any_forced_off(tray) is True
    assert is_user_forced_off(tray) is False
    assert is_system_forced_off(tray) is True


def test_any_forced_off_false_when_clear() -> None:
    tray = SimpleNamespace(
        _user_forced_off=False,
        _power_forced_off=False,
        _idle_forced_off=False,
        tray_idle_power_state=TrayIdlePowerState(),
    )
    assert any_forced_off(tray) is False
    assert is_system_forced_off(tray) is False


def test_dim_temp_and_resume_helpers() -> None:
    tray = SimpleNamespace(
        _dim_temp_active=True,
        _dim_temp_target_brightness=7,
        _last_resume_at=12.5,
        tray_idle_power_state=TrayIdlePowerState(),
    )
    assert is_dim_temp_active(tray) is True
    assert dim_temp_target_brightness(tray) == 7
    assert read_last_resume_at(tray) == 12.5


def test_last_brightness_helpers_ignore_non_positive() -> None:
    tray = SimpleNamespace(
        _last_brightness=40,
        tray_idle_power_state=TrayIdlePowerState(last_brightness=10),
    )
    assert read_last_brightness(tray, default=25) == 40
    set_last_brightness(tray, 0)
    assert tray._last_brightness == 40
    set_last_brightness(tray, 55)
    assert tray._last_brightness == 55
    assert tray.tray_idle_power_state.last_brightness == 55
    tray2 = SimpleNamespace(tray_idle_power_state=TrayIdlePowerState(last_brightness=0))
    assert read_last_brightness(tray2, default=25) == 25


def test_keyrgb_tray_idle_power_properties_are_owner_backed() -> None:
    from src.tray.app.application import KeyRGBTray
    from src.tray.idle_power_state import TrayIdlePowerState, set_idle_power_state_field

    tray = object.__new__(KeyRGBTray)
    owner = TrayIdlePowerState()
    tray.tray_idle_power_state = owner

    tray._power_forced_off = True
    tray._user_forced_off = True
    tray._idle_forced_off = False
    tray._dim_temp_active = True
    tray._dim_temp_target_brightness = 9
    tray._last_brightness = 33
    tray._last_resume_at = 1.25

    assert owner.power_forced_off is True
    assert owner.user_forced_off is True
    assert owner.idle_forced_off is False
    assert owner.dim_temp_active is True
    assert owner.dim_temp_target_brightness == 9
    assert owner.last_brightness == 33
    assert owner.last_resume_at == 1.25
    assert "_power_forced_off" not in vars(tray)
    assert tray._power_forced_off is True
    assert read_forced_off_flags(tray) == (True, True, False)
    assert read_last_brightness(tray, default=25) == 33

    # set helper writes owner only when the tray type uses properties.
    set_idle_power_state_field(
        tray, attr_name="_power_forced_off", state_name="power_forced_off", value=False
    )
    assert owner.power_forced_off is False
    assert "_power_forced_off" not in vars(tray)
    assert tray._power_forced_off is False
