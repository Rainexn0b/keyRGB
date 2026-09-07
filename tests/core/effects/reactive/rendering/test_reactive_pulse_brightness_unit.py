from __future__ import annotations

from types import SimpleNamespace

from keyrgb.core.effects.reactive.render import pulse_brightness_scale_factor


class _DummyEngine:
    def __init__(
        self,
        *,
        brightness: int,
        reactive_brightness: int,
        has_per_key: bool = True,
        reactive_visual_mode: str | None = None,
    ):
        self.brightness = brightness
        self.reactive_brightness = reactive_brightness
        self.per_key_colors = None
        self.per_key_brightness = None
        self.backend_caps = SimpleNamespace(per_key=has_per_key)
        self.kb = SimpleNamespace(set_key_colors=lambda *_args, **_kwargs: None) if has_per_key else SimpleNamespace()
        if reactive_visual_mode is not None:
            self.reactive_visual_mode = reactive_visual_mode
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


def test_pulse_brightness_uses_direct_slider_scale_when_reactive_exceeds_hw() -> None:
    eng = _DummyEngine(brightness=10, reactive_brightness=50)
    assert pulse_brightness_scale_factor(eng) == 1.0


def test_pulse_brightness_keeps_direct_slider_scale_on_very_dim_backdrops() -> None:
    eng = _DummyEngine(brightness=5, reactive_brightness=50)
    assert pulse_brightness_scale_factor(eng) == 1.0


def test_pulse_brightness_keeps_full_scale_when_reactive_matches_hw() -> None:
    eng = _DummyEngine(brightness=50, reactive_brightness=50)
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


def test_subtle_visual_mode_softens_midrange_per_key_pulse_scale() -> None:
    eng_vivid = _DummyEngine(brightness=40, reactive_brightness=20, reactive_visual_mode="vivid")
    eng_subtle = _DummyEngine(brightness=40, reactive_brightness=20, reactive_visual_mode="subtle")

    assert pulse_brightness_scale_factor(eng_subtle) < pulse_brightness_scale_factor(eng_vivid)


def test_idle_without_active_pulse_keeps_hw_at_profile_brightness() -> None:
    from keyrgb.core.effects.reactive.render import _resolve_brightness

    eng = _DummyEngine(brightness=10, reactive_brightness=50)
    eng._last_rendered_brightness = 10
    eng._reactive_active_pulse_mix = 0.0

    _base, eff, hw = _resolve_brightness(eng)

    assert eff == 50
    assert hw == 10


def test_follow_global_brightness_clamps_reactive_backdrop_during_soft_start() -> None:
    from keyrgb.core.effects.reactive.render import _resolve_brightness

    eng = _DummyEngine(brightness=2, reactive_brightness=50)
    eng._last_rendered_brightness = 2
    eng.per_key_colors = {(0, 0): (0, 0, 0)}
    eng.per_key_brightness = 5
    eng._reactive_follow_global_brightness = True

    base, eff, hw = _resolve_brightness(eng)

    assert base == 2
    assert eff == 2
    assert hw == 2
