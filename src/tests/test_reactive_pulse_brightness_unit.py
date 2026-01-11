from __future__ import annotations


from src.core.effects.reactive.render import pulse_brightness_scale_factor


class _DummyEngine:
    def __init__(self, *, brightness: int, reactive_brightness: int):
        self.brightness = brightness
        self.reactive_brightness = reactive_brightness
        self.per_key_colors = None
        self.per_key_brightness = None


def test_pulse_brightness_uses_reactive_brightness_when_lower_than_hw() -> None:
    eng = _DummyEngine(brightness=40, reactive_brightness=20)
    # Pulse scale should dim pulses to match reactive_brightness target.
    assert pulse_brightness_scale_factor(eng) == 0.5


def test_pulse_brightness_caps_when_reactive_exceeds_hw() -> None:
    eng = _DummyEngine(brightness=10, reactive_brightness=50)
    # Can't exceed hardware brightness; scale factor should cap to 1.
    assert pulse_brightness_scale_factor(eng) == 1.0
