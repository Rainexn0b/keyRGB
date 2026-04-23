from __future__ import annotations

import time
from types import SimpleNamespace


from src.core.effects.reactive.render import pulse_brightness_scale_factor


class _DummyEngine:
    def __init__(self, *, brightness: int, reactive_brightness: int, has_per_key: bool = True):
        self.brightness = brightness
        self.reactive_brightness = reactive_brightness
        self.per_key_colors = None
        self.per_key_brightness = None
        self.kb = SimpleNamespace(set_key_colors=object()) if has_per_key else SimpleNamespace()
        self._reactive_active_pulse_mix = 0.0
        # Set to 50 (steady-state) so the stability guard does not interfere
        # with tests that verify raw brightness scaling formulas.
        self._last_rendered_brightness = 50


def test_pulse_brightness_uses_reactive_brightness_when_lower_than_hw() -> None:
    eng = _DummyEngine(brightness=40, reactive_brightness=20)
    # Per-key hardware uses the reactive slider as a direct 0..50 pulse-intensity
    # control, independent of the steady-state hardware brightness.
    assert pulse_brightness_scale_factor(eng) == 0.4


def test_pulse_brightness_uniform_backend_still_uses_eff_over_hw_ratio() -> None:
    eng = _DummyEngine(brightness=40, reactive_brightness=20, has_per_key=False)
    eng._last_rendered_brightness = 40
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


def test_active_pulse_mix_does_not_lift_hw_on_per_key_backends() -> None:
    from src.core.effects.reactive.render import _resolve_brightness

    eng = _DummyEngine(brightness=10, reactive_brightness=50)
    eng._last_rendered_brightness = 10
    eng._reactive_active_pulse_mix = 1.0

    _base, eff, hw = _resolve_brightness(eng)

    assert eff == 50
    assert hw == 10


def test_active_pulse_mix_can_lift_hw_on_uniform_backends() -> None:
    from src.core.effects.reactive.render import _resolve_brightness

    eng = _DummyEngine(brightness=10, reactive_brightness=50, has_per_key=False)
    eng._last_rendered_brightness = 10
    eng._reactive_active_pulse_mix = 1.0

    _base, eff, hw = _resolve_brightness(eng)

    assert eff == 50
    assert hw == 10


def test_active_pulse_mix_can_lift_after_uniform_backend_streak() -> None:
    from src.core.effects.reactive.render import _resolve_brightness

    eng = _DummyEngine(brightness=10, reactive_brightness=50, has_per_key=False)
    eng._last_rendered_brightness = 10
    eng._reactive_active_pulse_mix = 1.0

    hw = 10
    # Lift starts only after the uniform-backend streak gate, then ramps through
    # the per-frame brightness guard.
    for _ in range(12):
        _base, eff, hw = _resolve_brightness(eng)
        eng._last_rendered_brightness = hw

    assert eff == 50
    assert hw == 50


def test_idle_without_active_pulse_keeps_hw_at_profile_brightness() -> None:
    from src.core.effects.reactive.render import _resolve_brightness

    eng = _DummyEngine(brightness=10, reactive_brightness=50)
    eng._last_rendered_brightness = 10
    eng._reactive_active_pulse_mix = 0.0

    _base, eff, hw = _resolve_brightness(eng)

    assert eff == 50
    assert hw == 10


def test_pulse_return_to_idle_skips_guard_tail() -> None:
    from src.core.effects.reactive.render import _resolve_brightness

    eng = _DummyEngine(brightness=10, reactive_brightness=50, has_per_key=False)
    # Previous frame was a fully lifted pulse.
    eng._last_rendered_brightness = 50
    eng._reactive_active_pulse_mix = 0.0

    _base, eff, hw = _resolve_brightness(eng)

    assert eff == 50
    # When a pulse has finished, return directly to the idle baseline instead
    # of stepping down through a bright tail frame.
    assert hw == 10


def test_active_pulse_mix_lift_is_suppressed_during_post_transition_cooldown() -> None:
    from src.core.effects.reactive.render import _resolve_brightness

    eng = _DummyEngine(brightness=10, reactive_brightness=50, has_per_key=False)
    eng._last_rendered_brightness = 10
    eng._reactive_active_pulse_mix = 1.0
    eng._reactive_disable_pulse_hw_lift_until = time.monotonic() + 5.0

    _base, eff, hw = _resolve_brightness(eng)

    assert eff == 50
    assert hw == 10
