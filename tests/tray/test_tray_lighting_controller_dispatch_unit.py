from __future__ import annotations

from unittest.mock import MagicMock


def _lock_mock() -> MagicMock:
    return MagicMock(__enter__=lambda s: None, __exit__=lambda s, *args: None)


class TestParseMenuInt:
    def test_parse_menu_int_strips_radio_markers(self):
        from src.tray.controllers._lighting_controller_helpers import parse_menu_int

        assert parse_menu_int("🔘 50") == 50
        assert parse_menu_int("⚪ 75") == 75
        assert parse_menu_int("100") == 100

    def test_parse_menu_int_returns_none_on_invalid(self):
        from src.tray.controllers._lighting_controller_helpers import parse_menu_int

        assert parse_menu_int("not a number") is None
        assert parse_menu_int("🔘 abc") is None


class TestStartCurrentEffect:
    def test_perkey_effect_calls_set_key_colors(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "perkey"
        mock_tray.config.brightness = 50
        mock_tray.config.per_key_colors = {(0, 0): (255, 0, 0)}
        mock_tray.engine.kb.enable_user_mode = MagicMock()
        mock_tray.engine.kb.set_key_colors = MagicMock()
        mock_tray.engine.kb_lock = _lock_mock()

        start_current_effect(mock_tray)

        mock_tray.engine.stop.assert_called_once()
        mock_tray.engine.kb.set_key_colors.assert_called_once()
        assert mock_tray.is_off is False

    def test_perkey_turns_off_if_brightness_zero(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "perkey"
        mock_tray.config.brightness = 0

        start_current_effect(mock_tray)

        mock_tray.engine.stop.assert_called_once()
        mock_tray.engine.turn_off.assert_called_once()
        assert mock_tray.is_off is True

    def test_none_effect_calls_set_color(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "none"
        mock_tray.config.brightness = 75
        mock_tray.config.color = (255, 0, 0)
        mock_tray.engine.kb_lock = _lock_mock()

        start_current_effect(mock_tray)

        mock_tray.engine.stop.assert_called_once()
        mock_tray.engine.kb.set_color.assert_called_once_with((255, 0, 0), brightness=75)
        assert mock_tray.is_off is False

    def test_animated_effect_starts_engine(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "breathe"
        mock_tray.config.brightness = 100
        mock_tray.config.speed = 3
        mock_tray.config.color = (0, 255, 0)
        mock_tray.config.reactive_color = None
        mock_tray.config.reactive_use_manual_color = False

        start_current_effect(mock_tray)

        mock_tray.engine.start_effect.assert_called_once_with(
            "breathe",
            speed=3,
            brightness=100,
            color=(0, 255, 0),
            reactive_color=None,
            reactive_use_manual_color=False,
            direction=mock_tray.config.direction,
        )
        assert mock_tray.is_off is False

    def test_start_current_effect_handles_exception_gracefully(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "wave"
        mock_tray.engine.start_effect = MagicMock(side_effect=RuntimeError("hardware error"))

        start_current_effect(mock_tray)

    def test_start_current_effect_resolves_prefixed_hardware_name_before_engine_start(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        backend = MagicMock()
        backend.effects.return_value = {"rainbow_wave": object()}

        mock_tray = MagicMock()
        mock_tray.backend = backend
        mock_tray.config.effect = "hw:rainbow_wave"
        mock_tray.config.brightness = 40
        mock_tray.config.speed = 3
        mock_tray.config.color = (1, 2, 3)
        mock_tray.config.reactive_color = None
        mock_tray.config.reactive_use_manual_color = False

        start_current_effect(mock_tray)

        assert mock_tray.config.effect == "rainbow_wave"
        mock_tray.engine.start_effect.assert_called_once_with(
            "rainbow_wave",
            speed=3,
            brightness=40,
            color=(1, 2, 3),
            reactive_color=None,
            reactive_use_manual_color=False,
            direction=mock_tray.config.direction,
        )
