from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from keyrgb.tray.controllers import effect_selection
from keyrgb.tray.controllers.effect_selection import apply_effect_selection


def _backend(*effect_names: str):
    backend = MagicMock()
    backend.effects.return_value = {name: object() for name in effect_names}
    return backend


def test_software_effect_remembers_last_software_effect() -> None:
    mock_tray = MagicMock()
    mock_tray.is_off = False
    mock_tray.backend_caps = MagicMock(hardware_effects=True, per_key=True, zoned=False)
    mock_tray.backend = _backend("wave")

    apply_effect_selection(mock_tray, effect_name="rainbow_wave")

    assert mock_tray.config.effect == "rainbow_wave"
    assert mock_tray.config.last_software_effect == "rainbow_wave"


def test_lighting_profile_toggle_applies_profile_then_restores_last_software_effect(monkeypatch) -> None:
    expected_colors = {(0, 0): (9, 8, 7)}
    monkeypatch.setattr(effect_selection, "_load_per_key_colors_from_profile", lambda _config: expected_colors)

    mock_tray = MagicMock()
    mock_tray.is_off = False
    mock_tray.backend_caps = SimpleNamespace(per_key=True, hardware_effects=False, zoned=False)
    mock_tray.config.effect = "rainbow_wave"
    mock_tray.config.last_software_effect = None
    mock_tray.config.per_key_colors = {}

    apply_effect_selection(mock_tray, effect_name="lighting_profile")

    assert mock_tray.config.effect == "none"
    assert mock_tray.config.last_software_effect == "rainbow_wave"
    assert mock_tray.config.per_key_colors == expected_colors
    mock_tray._start_current_effect.assert_called()

    mock_tray._start_current_effect.reset_mock()
    apply_effect_selection(mock_tray, effect_name="lighting_profile")

    assert mock_tray.config.effect == "rainbow_wave"
    mock_tray._start_current_effect.assert_called()
