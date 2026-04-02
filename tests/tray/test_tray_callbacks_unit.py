from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_on_effect_clicked_normalizes_and_refreshes() -> None:
    from src.tray.app.callbacks import on_effect_clicked

    tray = MagicMock()
    tray._refresh_ui = MagicMock()

    with (
        patch(
            "src.tray.app.callbacks.menu_mod.normalize_effect_label",
            return_value="Wave",
        ) as norm,
        patch("src.tray.app.callbacks.apply_effect_selection") as apply,
    ):
        on_effect_clicked(tray, item=object())

    norm.assert_called_once()
    apply.assert_called_once_with(tray, effect_name="Wave")
    tray._refresh_ui.assert_called_once()


def test_on_effect_key_clicked_normalizes_key_and_refreshes() -> None:
    from src.tray.app.callbacks import on_effect_key_clicked

    tray = MagicMock()
    tray._refresh_ui = MagicMock()

    with patch("src.tray.app.callbacks.apply_effect_selection") as apply:
        on_effect_key_clicked(tray, effect_name="  HW_Uniform  ")

    apply.assert_called_once_with(tray, effect_name="hw_uniform")
    tray._refresh_ui.assert_called_once()


def test_speed_and_brightness_callbacks_delegate() -> None:
    from src.tray.app.callbacks import on_brightness_clicked_cb, on_speed_clicked_cb

    tray = MagicMock()
    item = object()

    with (
        patch("src.tray.app.callbacks.on_speed_clicked") as sp,
        patch("src.tray.app.callbacks.on_brightness_clicked") as br,
    ):
        on_speed_clicked_cb(tray, item)
        on_brightness_clicked_cb(tray, item)

    sp.assert_called_once_with(tray, item)
    br.assert_called_once_with(tray, item)


def test_on_device_context_clicked_updates_selection_and_menu() -> None:
    from src.tray.app.callbacks import on_device_context_clicked

    tray = MagicMock()
    tray._update_menu = MagicMock()
    tray.selected_device_context = "keyboard"
    tray.config = MagicMock()

    on_device_context_clicked(tray, "lightbar:048d:7001")

    assert tray.selected_device_context == "lightbar:048d:7001"
    assert tray.config.tray_device_context == "lightbar:048d:7001"
    tray._update_menu.assert_called_once()


def test_on_device_context_clicked_returns_when_selection_is_read_only() -> None:
    from src.tray.app.callbacks import on_device_context_clicked

    class _Config:
        tray_device_context = "keyboard"

    class _Tray:
        def __init__(self) -> None:
            self._selected_device_context = "keyboard"
            self.config = _Config()
            self._update_menu = MagicMock()

        @property
        def selected_device_context(self) -> str:
            return self._selected_device_context

    tray = _Tray()

    on_device_context_clicked(tray, "lightbar:048d:7001")

    assert tray.selected_device_context == "keyboard"
    assert tray.config.tray_device_context == "keyboard"
    tray._update_menu.assert_not_called()


def test_on_device_context_clicked_ignores_read_only_config_and_updates_menu() -> None:
    from src.tray.app.callbacks import on_device_context_clicked

    class _Config:
        @property
        def tray_device_context(self) -> str:
            return "keyboard"

    class _Tray:
        def __init__(self) -> None:
            self.selected_device_context = "keyboard"
            self.config = _Config()
            self._update_menu = MagicMock()

    tray = _Tray()

    on_device_context_clicked(tray, "lightbar:048d:7001")

    assert tray.selected_device_context == "lightbar:048d:7001"
    assert tray.config.tray_device_context == "keyboard"
    tray._update_menu.assert_called_once()


def test_on_software_effect_target_clicked_updates_policy_and_menu() -> None:
    from src.tray.app.callbacks import on_software_effect_target_clicked

    tray = MagicMock()
    tray._update_menu = MagicMock()

    with patch("src.tray.app.callbacks.apply_software_effect_target_selection") as apply:
        on_software_effect_target_clicked(tray, "all_uniform_capable")

    apply.assert_called_once_with(tray, "all_uniform_capable")
    tray._update_menu.assert_called_once()


def test_on_off_and_on_turn_on_delegate() -> None:
    from src.tray.app.callbacks import on_off_clicked, on_turn_on_clicked

    tray = MagicMock()

    with patch("src.tray.app.callbacks.turn_off") as off, patch("src.tray.app.callbacks.turn_on") as on:
        on_off_clicked(tray)
        on_turn_on_clicked(tray)

    off.assert_called_once_with(tray)
    on.assert_called_once_with(tray)


def test_on_hardware_static_mode_clicked_applies_effect_and_refreshes() -> None:
    from src.tray.app.callbacks import on_hardware_static_mode_clicked

    tray = MagicMock()
    tray._refresh_ui = MagicMock()

    with patch("src.tray.app.callbacks.apply_effect_selection") as apply:
        on_hardware_static_mode_clicked(tray)

    apply.assert_called_once_with(tray, effect_name="hw_uniform")
    tray._refresh_ui.assert_called_once()


def test_on_hardware_color_clicked_applies_effect_refreshes_and_launches_gui() -> None:
    from src.tray.app.callbacks import on_hardware_color_clicked

    tray = MagicMock()
    tray._refresh_ui = MagicMock()

    with (
        patch("src.tray.app.callbacks.apply_effect_selection") as apply,
        patch("src.tray.app.callbacks.launch_uniform_gui") as launch,
    ):
        on_hardware_color_clicked(tray)

    apply.assert_called_once_with(tray, effect_name="hw_uniform")
    tray._refresh_ui.assert_called_once()
    launch.assert_called_once()


def test_on_selected_device_color_clicked_launches_targeted_uniform_gui_for_lightbar() -> None:
    from src.tray.app.callbacks import on_selected_device_color_clicked

    tray = MagicMock()
    tray.selected_device_context = "lightbar:048d:7001"

    with (
        patch(
            "src.tray.app.callbacks.selected_device_context_entry",
            return_value={"key": "lightbar:048d:7001", "device_type": "lightbar"},
        ),
        patch("src.tray.app.callbacks.selected_secondary_backend_name", return_value="ite8233"),
        patch("src.tray.app.callbacks.launch_uniform_gui") as launch,
    ):
        on_selected_device_color_clicked(tray)

    launch.assert_called_once_with(target_context="lightbar:048d:7001", backend_name="ite8233")


def test_on_selected_device_brightness_clicked_delegates_to_secondary_controller() -> None:
    from src.tray.app.callbacks import on_selected_device_brightness_clicked

    tray = MagicMock()
    item = object()

    with (
        patch(
            "src.tray.app.callbacks.selected_device_context_entry",
            return_value={"key": "lightbar:048d:7001", "device_type": "lightbar"},
        ),
        patch("src.tray.app.callbacks.apply_selected_secondary_brightness") as apply,
    ):
        on_selected_device_brightness_clicked(tray, item)

    apply.assert_called_once_with(tray, item)


def test_on_selected_device_turn_off_clicked_delegates_to_secondary_controller() -> None:
    from src.tray.app.callbacks import on_selected_device_turn_off_clicked

    tray = MagicMock()

    with (
        patch(
            "src.tray.app.callbacks.selected_device_context_entry",
            return_value={"key": "lightbar:048d:7001", "device_type": "lightbar"},
        ),
        patch("src.tray.app.callbacks.turn_off_selected_secondary_device") as turn_off_secondary,
    ):
        on_selected_device_turn_off_clicked(tray)

    turn_off_secondary.assert_called_once_with(tray)


def test_on_tcc_profile_clicked_updates_menu_on_success() -> None:
    from src.tray.app.callbacks import on_tcc_profile_clicked

    tray = MagicMock()
    tray._update_menu = MagicMock()

    with patch("src.tray.app.callbacks.tcc_power_profiles.set_temp_profile_by_id") as setp:
        on_tcc_profile_clicked(tray, profile_id="balanced")

    setp.assert_called_once_with("balanced")
    tray._update_menu.assert_called_once()


def test_on_tcc_profile_clicked_updates_menu_even_on_failure() -> None:
    from src.tray.app.callbacks import on_tcc_profile_clicked

    tray = MagicMock()
    tray._update_menu = MagicMock()

    with patch(
        "src.tray.app.callbacks.tcc_power_profiles.set_temp_profile_by_id",
        side_effect=RuntimeError("boom"),
    ) as setp:
        try:
            on_tcc_profile_clicked(tray, profile_id="balanced")
        except RuntimeError:
            pass

    setp.assert_called_once_with("balanced")
    tray._update_menu.assert_called_once()


def test_support_window_callbacks_launch_with_expected_focus() -> None:
    from src.tray.app.callbacks import on_backend_discovery_clicked, on_support_debug_clicked

    with patch("src.tray.app.callbacks.launch_support_gui") as launch:
        on_support_debug_clicked()
        on_backend_discovery_clicked()

    assert launch.call_args_list[0].kwargs == {"focus": "debug"}
    assert launch.call_args_list[1].kwargs == {"focus": "discovery"}
