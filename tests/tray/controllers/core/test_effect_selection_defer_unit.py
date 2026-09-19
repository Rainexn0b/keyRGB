"""Unit tests for _effect_selection_defer.py persist-only effect selection."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestDeferEffectSelection:
    def test_zoned_perkey_defer_persists_map_and_synced_color_without_deck_writes(self, monkeypatch):
        """Zoned perkey choices persist the map plus the averaged color, no deck writes."""
        from keyrgb.tray.controllers import effect_selection as facade
        from keyrgb.tray.controllers._effect_selection_defer import defer_effect_selection

        expected_colors = {(0, 0): (10, 20, 30), (0, 1): (30, 40, 50)}
        monkeypatch.setattr(facade, "_load_per_key_colors_from_profile", lambda _config: expected_colors)

        mock_tray = MagicMock()
        mock_tray.config.per_key_colors = {}

        defer_effect_selection(
            mock_tray,
            effect_name="perkey",
            per_key_supported=False,
            hw_effects_supported=False,
            zoned_supported=True,
        )

        assert mock_tray.config.effect == "none"
        assert mock_tray.config.per_key_colors == expected_colors
        assert mock_tray.config.color == (20, 30, 40)
        assert mock_tray.engine.per_key_colors is expected_colors
        mock_tray.engine.stop.assert_not_called()
        mock_tray.engine.kb.set_color.assert_not_called()
        mock_tray.engine.kb.set_key_colors.assert_not_called()

    def test_zoned_none_defer_syncs_color_with_saved_map(self):
        """Zoned 'none' with a saved map persists the software path and synced color."""
        from keyrgb.tray.controllers._effect_selection_defer import defer_effect_selection

        mock_tray = MagicMock()
        mock_tray.config.per_key_colors = {(0, 0): (10, 20, 30), (0, 1): (30, 40, 50)}
        mock_tray.config.color = (255, 0, 0)

        defer_effect_selection(
            mock_tray,
            effect_name="none",
            per_key_supported=False,
            hw_effects_supported=False,
            zoned_supported=True,
        )

        assert mock_tray.config.effect == "none"
        assert mock_tray.config.color == (20, 30, 40)
        assert mock_tray.engine.per_key_colors is mock_tray.config.per_key_colors
        mock_tray.engine.kb.set_color.assert_not_called()

    def test_non_zoned_non_perkey_perkey_defer_keeps_hardware_mode(self):
        """Brightness-only backends keep the hardware-mode defer for 'perkey'."""
        from keyrgb.tray.controllers._effect_selection_defer import defer_effect_selection

        mock_tray = MagicMock()

        result = defer_effect_selection(
            mock_tray,
            effect_name="perkey",
            per_key_supported=False,
            hw_effects_supported=True,
            zoned_supported=False,
        )

        assert result is True
        assert mock_tray.config.effect == "none"
        assert mock_tray.engine.per_key_colors is None
        assert mock_tray.engine.per_key_brightness is None
