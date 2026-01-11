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
    # No backdrop => hw is profile brightness (40). Scale is eff/hw.
    assert pulse_brightness_scale_factor(eng) == 0.5


def test_pulse_brightness_caps_when_reactive_exceeds_hw() -> None:
    eng = _DummyEngine(brightness=10, reactive_brightness=50)
    # 50/50 -> full intensity.
    assert pulse_brightness_scale_factor(eng) == 1.0


def test_pulse_brightness_scale_changes_across_range() -> None:
    # Fixed hw (backdrop active at 50) => scale tracks eff/hw.
    eng_low = _DummyEngine(brightness=50, reactive_brightness=5)
    eng_low.per_key_colors = {(0, 0): (0, 0, 0)}
    eng_low.per_key_brightness = 50

    eng_high = _DummyEngine(brightness=50, reactive_brightness=25)
    eng_high.per_key_colors = {(0, 0): (0, 0, 0)}
    eng_high.per_key_brightness = 50

    assert pulse_brightness_scale_factor(eng_low) < pulse_brightness_scale_factor(eng_high)
