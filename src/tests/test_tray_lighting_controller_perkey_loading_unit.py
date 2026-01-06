from __future__ import annotations
from unittest.mock import MagicMock
from src.tray.controllers.lighting_controller import start_current_effect


class MockEngine:
    def __init__(self):
        self.stop = MagicMock()
        self.turn_off = MagicMock()
        self.start_effect = MagicMock()
        self.per_key_colors = None
        self.per_key_brightness = None
        self.running = False
        self.kb_lock = MagicMock()
        self.kb_lock.__enter__ = MagicMock()
        self.kb_lock.__exit__ = MagicMock()


class MockConfig:
    def __init__(self):
        self.effect = "rainbow_wave"
        self.speed = 5
        self.brightness = 25
        self.color = (255, 0, 0)
        self.per_key_colors = {(0, 0): (255, 255, 255)}
        self.perkey_brightness = 10
        self.reactive_color = None


class MockTray:
    def __init__(self):
        self.config = MockConfig()
        self.engine = MockEngine()
        self.is_off = False


def test_start_current_effect_loads_perkey_for_software_effect() -> None:
    tray = MockTray()
    tray.config.effect = "reactive_ripple"  # Known SW effect (if in set)

    # We need to ensure SW_EFFECTS contains it. The controller imports it.
    # Assuming runtime env has it.

    start_current_effect(tray)

    # Check if per_key_colors/brightness were loaded
    assert tray.engine.per_key_colors == {(0, 0): (255, 255, 255)}
    assert tray.engine.per_key_brightness == 10

    tray.engine.start_effect.assert_called_once()


def test_start_current_effect_clears_perkey_for_hardware_effect() -> None:
    tray = MockTray()
    tray.config.effect = "breathing"  # Assuming HW effect
    # Pre-set engine state to ensure it gets cleared
    tray.engine.per_key_colors = {(0, 0): (255, 255, 255)}
    tray.engine.per_key_brightness = 10

    start_current_effect(tray)

    assert tray.engine.per_key_colors is None
    assert tray.engine.per_key_brightness is None

    tray.engine.start_effect.assert_called_once()
