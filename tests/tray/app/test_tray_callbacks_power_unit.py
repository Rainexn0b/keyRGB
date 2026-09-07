from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_on_selected_device_color_clicked_launches_targeted_uniform_gui_for_lightbar() -> None:
    from keyrgb.tray.app.callbacks import on_selected_device_color_clicked

    tray = MagicMock()
    tray.selected_device_context = "lightbar:048d:7001"

    with (
        patch(
            "keyrgb.tray.app.callbacks.selected_device_context_entry",
            return_value={"key": "lightbar:048d:7001", "device_type": "lightbar"},
        ),
        patch(
            "keyrgb.tray.app.callbacks.selected_secondary_backend_name",
            return_value="ite8233_none_chassis_lightbar_clevo",
        ),
        patch("keyrgb.tray.app.callbacks.launch_uniform_gui") as launch,
    ):
        on_selected_device_color_clicked(tray)

    launch.assert_called_once_with(
        target_context="lightbar:048d:7001", backend_name="ite8233_none_chassis_lightbar_clevo"
    )


def test_on_selected_device_color_clicked_launches_targeted_uniform_gui_for_mouse() -> None:
    from keyrgb.tray.app.callbacks import on_selected_device_color_clicked

    tray = MagicMock()
    tray.selected_device_context = "mouse:sysfs:usbmouse__rgb"

    with (
        patch(
            "keyrgb.tray.app.callbacks.selected_device_context_entry",
            return_value={"key": "mouse:sysfs:usbmouse__rgb", "device_type": "mouse"},
        ),
        patch("keyrgb.tray.app.callbacks.selected_secondary_backend_name", return_value="sysfs-mouse"),
        patch("keyrgb.tray.app.callbacks.launch_uniform_gui") as launch,
    ):
        on_selected_device_color_clicked(tray)

    launch.assert_called_once_with(target_context="mouse:sysfs:usbmouse__rgb", backend_name="sysfs-mouse")


def test_on_selected_device_brightness_clicked_delegates_to_secondary_controller() -> None:
    from keyrgb.tray.app.callbacks import on_selected_device_brightness_clicked

    tray = MagicMock()
    item = object()

    with (
        patch(
            "keyrgb.tray.app.callbacks.selected_device_context_entry",
            return_value={"key": "lightbar:048d:7001", "device_type": "lightbar"},
        ),
        patch("keyrgb.tray.app.callbacks.apply_selected_secondary_brightness") as apply,
    ):
        on_selected_device_brightness_clicked(tray, item)

    apply.assert_called_once_with(tray, item)


def test_on_selected_device_turn_off_clicked_delegates_to_secondary_controller() -> None:
    from keyrgb.tray.app.callbacks import on_selected_device_turn_off_clicked

    tray = MagicMock()

    with (
        patch(
            "keyrgb.tray.app.callbacks.selected_device_context_entry",
            return_value={"key": "lightbar:048d:7001", "device_type": "lightbar"},
        ),
        patch("keyrgb.tray.app.callbacks.turn_off_selected_secondary_device") as turn_off_secondary,
    ):
        on_selected_device_turn_off_clicked(tray)

    turn_off_secondary.assert_called_once_with(tray)


def test_on_selected_device_turn_on_clicked_delegates_to_secondary_controller() -> None:
    from keyrgb.tray.app.callbacks import on_selected_device_turn_on_clicked

    tray = MagicMock()

    with (
        patch(
            "keyrgb.tray.app.callbacks.selected_device_context_entry",
            return_value={"key": "lightbar:048d:7001", "device_type": "lightbar"},
        ),
        patch("keyrgb.tray.app.callbacks.turn_on_selected_secondary_device") as turn_on_secondary,
    ):
        on_selected_device_turn_on_clicked(tray)

    turn_on_secondary.assert_called_once_with(tray)


def test_support_window_callbacks_launch_with_expected_focus() -> None:
    from keyrgb.tray.app.callbacks import on_backend_discovery_clicked, on_support_debug_clicked

    with patch("keyrgb.tray.app.callbacks.launch_support_gui") as launch:
        on_support_debug_clicked()
        on_backend_discovery_clicked()

    assert launch.call_args_list[0].kwargs == {"focus": "debug"}
    assert launch.call_args_list[1].kwargs == {"focus": "discovery"}


def test_on_power_mode_settings_clicked_launches_power_mode_settings_gui() -> None:
    from keyrgb.tray.app.callbacks import on_power_mode_settings_clicked

    with patch("keyrgb.tray.app.callbacks.launch_power_mode_settings_gui") as launch:
        on_power_mode_settings_clicked()

    launch.assert_called_once_with()
