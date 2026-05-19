from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def test_activate_perkey_profile_uses_shared_in_place_transition_path() -> None:
    from src.tray.controllers import menu_adapters

    tray = SimpleNamespace(
        config=SimpleNamespace(),
        is_off=True,
        _power_forced_off=False,
        _apply_power_source_perkey_profile_transition=MagicMock(return_value=True),
        _start_current_effect=MagicMock(),
        _update_icon=MagicMock(),
        _update_menu=MagicMock(),
    )

    with (
        patch.object(menu_adapters.core_profiles, "set_active_profile", return_value="gaming") as set_active,
        patch.object(menu_adapters.core_profiles, "load_per_key_colors", return_value={(0, 0): (3, 4, 5)}) as load_colors,
        patch.object(menu_adapters.core_profiles, "apply_profile_to_config") as apply_profile,
    ):
        menu_adapters.activate_perkey_profile(tray, "gaming")

    set_active.assert_called_once_with("gaming")
    load_colors.assert_called_once_with("gaming")
    apply_profile.assert_called_once_with(tray.config, {(0, 0): (3, 4, 5)})
    tray._apply_power_source_perkey_profile_transition.assert_called_once_with()
    tray._start_current_effect.assert_not_called()
    tray._update_icon.assert_called_once_with()
    tray._update_menu.assert_called_once_with()
    assert tray.is_off is False
    assert not hasattr(tray, "_last_power_source_transition_at")
