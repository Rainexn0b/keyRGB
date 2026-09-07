from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from keyrgb.tray.controllers._power._transition_constants import (
    DEFAULT_IDLE_FADE_DURATION_S,
    SOFT_ON_START_BRIGHTNESS,
    idle_fade_duration_s,
)


def _lock_mock() -> MagicMock:
    return MagicMock(__enter__=lambda s: None, __exit__=lambda s, *args: None)


class TestTurnOffOn:
    def test_turn_off_sets_flags_and_calls_engine(self):
        from keyrgb.tray.controllers.lighting_controller import turn_off
        from tests.tray.fakes import make_owner_backed_mock_tray

        mock_tray = make_owner_backed_mock_tray(is_off=False)

        turn_off(mock_tray)

        assert mock_tray._user_forced_off is True
        assert mock_tray._idle_forced_off is False
        assert mock_tray.tray_idle_power_state.user_forced_off is True
        assert mock_tray.tray_idle_power_state.idle_forced_off is False
        assert mock_tray.is_off is True
        mock_tray.engine.turn_off.assert_called_once()
        mock_tray._refresh_ui.assert_called_once()

    def test_turn_on_clears_flags_and_restores_brightness(self):
        from keyrgb.tray.controllers.lighting_controller import turn_on
        from tests.tray.fakes import make_owner_backed_mock_tray

        mock_tray = make_owner_backed_mock_tray(is_off=True, last_brightness=75)
        mock_tray.config.brightness = 0
        mock_tray.config.effect = "breathe"
        mock_tray.tray_idle_power_state.last_resume_at = 0.0

        with patch("keyrgb.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            turn_on(mock_tray)

        assert mock_tray._user_forced_off is False
        assert mock_tray._idle_forced_off is False
        assert mock_tray.tray_idle_power_state.user_forced_off is False
        assert mock_tray.is_off is False
        assert mock_tray.config.brightness == 75
        assert float(mock_tray.tray_idle_power_state.last_resume_at) > 0.0
        mock_start.assert_called_once_with(
            mock_tray,
            brightness_override=SOFT_ON_START_BRIGHTNESS,
            fade_in=True,
            fade_in_duration_s=DEFAULT_IDLE_FADE_DURATION_S,
        )

    def test_turn_on_uses_default_25_if_no_last_brightness(self):
        from keyrgb.tray.controllers.lighting_controller import turn_on
        from tests.tray.fakes import make_owner_backed_mock_tray

        mock_tray = make_owner_backed_mock_tray(is_off=True, last_brightness=0)
        mock_tray.config.brightness = 0
        mock_tray.config.effect = "none"
        mock_tray.config.color = (255, 255, 255)
        mock_tray.engine.kb_lock = _lock_mock()

        with patch("keyrgb.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            turn_on(mock_tray)

        assert mock_tray.config.brightness == 25
        mock_start.assert_called_once_with(
            mock_tray,
            brightness_override=SOFT_ON_START_BRIGHTNESS,
            fade_in=True,
            fade_in_duration_s=DEFAULT_IDLE_FADE_DURATION_S,
        )


class TestIdleFadeDuration:
    def test_defaults_when_config_lacks_setting(self):
        assert idle_fade_duration_s(SimpleNamespace()) == DEFAULT_IDLE_FADE_DURATION_S

    def test_reads_configured_value(self):
        assert idle_fade_duration_s(SimpleNamespace(idle_fade_duration_s=1.2)) == 1.2

    def test_clamps_to_supported_range(self):
        assert idle_fade_duration_s(SimpleNamespace(idle_fade_duration_s=0.0)) == 0.1
        assert idle_fade_duration_s(SimpleNamespace(idle_fade_duration_s=99.0)) == 3.0

    def test_falls_back_on_uncoercible_value(self):
        assert idle_fade_duration_s(SimpleNamespace(idle_fade_duration_s="fast")) == DEFAULT_IDLE_FADE_DURATION_S

    def test_power_turn_off_uses_configured_fade_duration(self):
        from keyrgb.tray.controllers.lighting_controller import power_turn_off
        from tests.tray.fakes import make_owner_backed_mock_tray

        mock_tray = make_owner_backed_mock_tray(is_off=False)
        mock_tray.config.idle_fade_duration_s = 1.2

        power_turn_off(mock_tray)

        mock_tray.engine.turn_off.assert_called_once_with(fade=True, fade_duration_s=1.2)
