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

    with patch("src.tray.app.callbacks.on_speed_clicked") as sp, patch("src.tray.app.callbacks.on_brightness_clicked") as br:
        on_speed_clicked_cb(tray, item)
        on_brightness_clicked_cb(tray, item)

    sp.assert_called_once_with(tray, item)
    br.assert_called_once_with(tray, item)


def test_on_off_and_on_turn_on_delegate() -> None:
    from src.tray.app.callbacks import on_off_clicked, on_turn_on_clicked

    tray = MagicMock()

    with patch("src.tray.app.callbacks.turn_off") as off, patch("src.tray.app.callbacks.turn_on") as on:
        on_off_clicked(tray)
        on_turn_on_clicked(tray)

    off.assert_called_once_with(tray)
    on.assert_called_once_with(tray)


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
