from __future__ import annotations

import logging
import time
from types import SimpleNamespace

import pytest

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


def test_pulse_brightness_uses_direct_slider_scale_when_reactive_exceeds_hw() -> None:
    eng = _DummyEngine(brightness=10, reactive_brightness=50)
    assert pulse_brightness_scale_factor(eng) == 1.0


def test_pulse_brightness_keeps_direct_slider_scale_on_very_dim_backdrops() -> None:
    eng = _DummyEngine(brightness=5, reactive_brightness=50)
    assert pulse_brightness_scale_factor(eng) == 1.0


def test_pulse_brightness_damps_very_dim_post_restore_bursts() -> None:
    eng = _DummyEngine(brightness=5, reactive_brightness=50)
    eng.per_key_colors = {(0, 0): (0, 0, 0)}
    eng.per_key_brightness = 5
    eng._reactive_post_restore_visual_damp_until = 102.0

    import src.core.effects.reactive.render as render_module

    original_monotonic = render_module.time.monotonic
    render_module.time.monotonic = lambda: 100.0
    try:
        assert pulse_brightness_scale_factor(eng) == pytest.approx(0.415)
    finally:
        render_module.time.monotonic = original_monotonic


def test_pulse_brightness_reseeds_restore_damp_on_first_post_restore_pulse() -> None:
    from src.core.effects.reactive import effects

    eng = _DummyEngine(brightness=5, reactive_brightness=50)
    eng.per_key_colors = {(0, 0): (0, 0, 0)}
    eng.per_key_brightness = 5
    eng._reactive_post_restore_visual_damp_until = 99.0
    eng._reactive_post_restore_visual_damp_pending = True

    import src.core.effects.reactive.render as render_module

    original_monotonic = render_module.time.monotonic
    render_module.time.monotonic = lambda: 100.0
    try:
        effects._set_reactive_active_pulse_mix(eng, target=1.0)
        assert pulse_brightness_scale_factor(eng) == pytest.approx(0.415)
    finally:
        render_module.time.monotonic = original_monotonic


def test_wake_path_reseeds_restore_damp_after_initial_window_expires(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.core.effects.reactive import _render_brightness_support as reactive_support
    from src.core.effects.reactive import effects
    from src.core.effects.reactive.render import _resolve_brightness
    from src.tray.pollers.idle_power._transition_actions import _seed_reactive_restore_windows

    class _Clock:
        def __init__(self, now: float) -> None:
            self.now = now

        def monotonic(self) -> float:
            return self.now

    clock = _Clock(100.0)
    monkeypatch.setattr("src.tray.pollers.idle_power._transition_actions.time.monotonic", clock.monotonic)
    monkeypatch.setattr("src.core.effects.reactive.effects.time.monotonic", clock.monotonic)
    monkeypatch.setattr("src.core.effects.reactive.render.time.monotonic", clock.monotonic)
    monkeypatch.setattr("src.core.effects.reactive._render_brightness.time.monotonic", clock.monotonic)
    monkeypatch.setattr("src.core.effects.reactive._render_brightness_support.time.monotonic", clock.monotonic)

    eng = _DummyEngine(brightness=5, reactive_brightness=50)
    eng.per_key_colors = {(0, 0): (0, 0, 0)}
    eng.per_key_brightness = 5
    eng._last_rendered_brightness = 5

    _seed_reactive_restore_windows(eng, fade_in_duration_s=1.0)
    state = reactive_support.ensure_reactive_state(eng)
    assert state._reactive_restore_phase is reactive_support.ReactiveRestorePhase.FIRST_PULSE_PENDING
    assert state._reactive_restore_damp_until == pytest.approx(104.0)

    clock.now = 105.0
    effects._set_reactive_active_pulse_mix(eng, target=1.0)

    state = reactive_support.ensure_reactive_state(eng)
    assert state._reactive_restore_phase is reactive_support.ReactiveRestorePhase.DAMPING
    assert state._reactive_restore_damp_until == pytest.approx(107.0)
    assert pulse_brightness_scale_factor(eng) == pytest.approx(0.415)

    _base, eff, hw = _resolve_brightness(eng)
    assert eff == 50
    assert hw == 5

    clock.now = 107.1
    assert pulse_brightness_scale_factor(eng) == 1.0
    state = reactive_support.ensure_reactive_state(eng)
    assert state._reactive_restore_phase is reactive_support.ReactiveRestorePhase.NORMAL

    reactive_support.set_engine_attr(eng, "_reactive_active_pulse_mix", 0.0)

    clock.now = 200.0
    _seed_reactive_restore_windows(eng, fade_in_duration_s=1.0)
    state = reactive_support.ensure_reactive_state(eng)
    assert state._reactive_restore_phase is reactive_support.ReactiveRestorePhase.FIRST_PULSE_PENDING
    assert state._reactive_restore_damp_until == pytest.approx(204.0)

    clock.now = 205.0
    effects._set_reactive_active_pulse_mix(eng, target=1.0)
    assert pulse_brightness_scale_factor(eng) == pytest.approx(0.415)
    state = reactive_support.ensure_reactive_state(eng)
    assert state._reactive_restore_phase is reactive_support.ReactiveRestorePhase.DAMPING
    assert state._reactive_restore_damp_until == pytest.approx(207.0)


def test_pulse_brightness_logs_visual_scale_under_debug(monkeypatch, caplog) -> None:
    eng = _DummyEngine(brightness=5, reactive_brightness=50)
    eng.per_key_colors = {(0, 0): (0, 0, 0)}
    eng.per_key_brightness = 5

    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")

    with caplog.at_level(logging.INFO, logger="src.core.effects.reactive.render"):
        pulse_brightness_scale_factor(eng)

    messages = [record.getMessage() for record in caplog.records if "reactive_pulse_visual:" in record.getMessage()]
    assert messages
    assert "visual_hw=5" in messages[-1]
    assert "pulse_scale=1.000" in messages[-1]
    assert "very_dim_curve=True" in messages[-1]
    assert "post_restore_damp=1.000" in messages[-1]


def test_pulse_brightness_logs_post_restore_damp_under_debug(monkeypatch, caplog) -> None:
    eng = _DummyEngine(brightness=5, reactive_brightness=50)
    eng.per_key_colors = {(0, 0): (0, 0, 0)}
    eng.per_key_brightness = 5
    eng._reactive_post_restore_visual_damp_until = 102.0

    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")
    monkeypatch.setattr("src.core.effects.reactive.render.time.monotonic", lambda: 100.0)

    with caplog.at_level(logging.INFO, logger="src.core.effects.reactive.render"):
        pulse_brightness_scale_factor(eng)

    messages = [record.getMessage() for record in caplog.records if "reactive_pulse_visual:" in record.getMessage()]
    assert messages
    assert "pulse_scale=0.415" in messages[-1]
    assert "holdoff_remaining_s=2.00" in messages[-1]
    assert "post_restore_damp=0.350" in messages[-1]


def test_pulse_brightness_does_not_damp_normal_first_activity_holdoff() -> None:
    eng = _DummyEngine(brightness=5, reactive_brightness=50)
    eng.per_key_colors = {(0, 0): (0, 0, 0)}
    eng.per_key_brightness = 5
    eng._reactive_disable_pulse_hw_lift_until = 102.0

    import src.core.effects.reactive.render as render_module

    original_monotonic = render_module.time.monotonic
    render_module.time.monotonic = lambda: 100.0
    try:
        assert pulse_brightness_scale_factor(eng) == 1.0
    finally:
        render_module.time.monotonic = original_monotonic


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


def test_follow_global_brightness_clamps_reactive_backdrop_during_soft_start() -> None:
    from src.core.effects.reactive.render import _resolve_brightness

    eng = _DummyEngine(brightness=2, reactive_brightness=50)
    eng._last_rendered_brightness = 2
    eng.per_key_colors = {(0, 0): (0, 0, 0)}
    eng.per_key_brightness = 5
    eng._reactive_follow_global_brightness = True

    base, eff, hw = _resolve_brightness(eng)

    assert base == 2
    assert eff == 2
    assert hw == 2


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


def test_resolve_brightness_logs_hw_lift_cooldown_reason_under_debug(monkeypatch, caplog) -> None:
    from src.core.effects.reactive.render import _resolve_brightness

    now = 100.0
    eng = _DummyEngine(brightness=10, reactive_brightness=50, has_per_key=False)
    eng._last_rendered_brightness = 10
    eng._reactive_active_pulse_mix = 1.0
    eng._reactive_uniform_hw_streak = 5
    eng._reactive_disable_pulse_hw_lift_until = now + 2.5

    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")
    monkeypatch.setattr("src.core.effects.reactive._render_brightness.time.monotonic", lambda: now)
    monkeypatch.setattr(
        "src.core.effects.reactive._render_brightness_support.time.monotonic",
        lambda: now,
    )

    with caplog.at_level(logging.INFO, logger="src.core.effects.reactive.render"):
        _resolve_brightness(eng)

    messages = [record.getMessage() for record in caplog.records if "reactive_hw_lift:" in record.getMessage()]
    assert messages
    assert "reason=cooldown" in messages[-1]
    assert "cooldown_remaining_s=2.50" in messages[-1]
