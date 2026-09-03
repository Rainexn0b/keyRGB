from __future__ import annotations

import logging
import time
from types import SimpleNamespace

import pytest

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


def test_pulse_brightness_damps_very_dim_post_restore_bursts() -> None:
    from keyrgb.core.effects.reactive._render_brightness_support import (
        ReactiveRestorePhase,
        ensure_reactive_state,
    )

    eng = _DummyEngine(brightness=5, reactive_brightness=50)
    eng.per_key_colors = {(0, 0): (0, 0, 0)}
    eng.per_key_brightness = 5
    state = ensure_reactive_state(eng)
    state._reactive_restore_damp_until = 102.0
    state._reactive_restore_phase = ReactiveRestorePhase.DAMPING

    import keyrgb.core.effects.reactive.render as render_module

    original_monotonic = render_module.time.monotonic
    render_module.time.monotonic = lambda: 100.0
    try:
        assert pulse_brightness_scale_factor(eng) == pytest.approx(0.415)
    finally:
        render_module.time.monotonic = original_monotonic


def test_queued_restore_seed_survives_engine_state_reset() -> None:
    """Pre-start queue must re-apply after stop()-style ReactiveRenderState()."""
    from keyrgb.core.effects.reactive._reactive_restore_seed import (
        apply_queued_reactive_restore_seed,
        seed_reactive_restore_windows,
    )
    from keyrgb.core.effects.reactive._render_brightness_support import (
        ReactiveRenderState,
        ReactiveRestorePhase,
        ensure_reactive_state,
    )

    eng = _DummyEngine(brightness=20, reactive_brightness=50)
    assert seed_reactive_restore_windows(eng, fade_in_duration_s=0.42, now=100.0)
    state = ensure_reactive_state(eng)
    assert state._reactive_restore_phase is ReactiveRestorePhase.FIRST_PULSE_PENDING
    assert state._reactive_restore_damp_until == pytest.approx(104.0)
    assert state._reactive_restore_frame_started_at == pytest.approx(100.0)
    assert state._reactive_restore_frame_duration_s == pytest.approx(0.42)

    # Simulate engine.stop() rebuild.
    eng._reactive_state = ReactiveRenderState()
    assert apply_queued_reactive_restore_seed(eng) is True
    state = ensure_reactive_state(eng)
    assert state._reactive_restore_phase is ReactiveRestorePhase.FIRST_PULSE_PENDING
    assert state._reactive_restore_damp_until == pytest.approx(104.0)
    assert state._reactive_disable_pulse_hw_lift_until == pytest.approx(102.0)
    assert state._reactive_restore_frame_started_at == pytest.approx(100.0)
    assert state._reactive_restore_frame_duration_s == pytest.approx(0.42)
    # Queue is single-shot.
    eng._reactive_state = ReactiveRenderState()
    assert apply_queued_reactive_restore_seed(eng) is False


def test_post_restore_frame_scale_softens_soft_on_matrix_steps() -> None:
    """Whole-frame scale during restore damp covers pulse_mix=0 soft-on pops."""
    from keyrgb.core.effects.reactive._reactive_restore_seed import seed_reactive_restore_windows
    from keyrgb.core.effects.reactive._render_brightness_support import (
        ReactiveRestorePhase,
        ensure_reactive_state,
    )
    from keyrgb.core.effects.reactive.render import _post_restore_frame_scale, _resolve_transition_visual_scale

    eng = _DummyEngine(brightness=20, reactive_brightness=50)
    eng.per_key_colors = {(0, 0): (0, 0, 0)}
    eng.per_key_brightness = 20
    # Seed via the canonical helper so frame envelope is populated (fade 0.42).
    seed_reactive_restore_windows(eng, fade_in_duration_s=0.42, now=100.0)
    state = ensure_reactive_state(eng)
    assert state._reactive_restore_phase is ReactiveRestorePhase.FIRST_PULSE_PENDING

    import keyrgb.core.effects.reactive.render as render_module

    original_monotonic = render_module.time.monotonic
    render_module.time.monotonic = lambda: 100.0
    try:
        # At envelope start → frame floor 0.62, independent of pulse phase.
        assert _post_restore_frame_scale(eng) == pytest.approx(0.62)
        assert _resolve_transition_visual_scale(eng) == pytest.approx(0.62)
        # First key flips phase to DAMPING but frame envelope stays monotonic;
        # whole-frame must NOT jump back to 1.0 (the OP-1 discontinuity).
        state._reactive_restore_phase = ReactiveRestorePhase.DAMPING
        assert _post_restore_frame_scale(eng) == pytest.approx(0.62)
        assert _resolve_transition_visual_scale(eng) == pytest.approx(0.62)
        # Outside restore window (envelope elapsed), full scale.
        render_module.time.monotonic = lambda: 100.5
        assert _post_restore_frame_scale(eng) == pytest.approx(1.0)
        assert _resolve_transition_visual_scale(eng) == pytest.approx(1.0)
        # Clearing frame envelope also yields full scale.
        state._reactive_restore_phase = ReactiveRestorePhase.NORMAL
        state._reactive_restore_damp_until = None
        state._reactive_restore_frame_started_at = None
        state._reactive_restore_frame_duration_s = None
        assert _post_restore_frame_scale(eng) == pytest.approx(1.0)
        assert _resolve_transition_visual_scale(eng) == pytest.approx(1.0)
    finally:
        render_module.time.monotonic = original_monotonic


def test_pulse_brightness_damps_normal_base_post_restore_bursts() -> None:
    """Typing-wake flash regression: damp must apply at base>=10 (e.g. 20).

    Previously post-restore damp was nested under very_dim_curve (visual_hw < 10),
    so a normal base like 20 kept pulse_scale=1.0 on the first rapid burst after
    long idle off — a brief deck-wide flash with reactive_ripple.
    """
    from keyrgb.core.effects.reactive._render_brightness_support import (
        ReactiveRestorePhase,
        ensure_reactive_state,
    )

    eng = _DummyEngine(brightness=20, reactive_brightness=50)
    eng.per_key_colors = {(0, 0): (0, 0, 0)}
    eng.per_key_brightness = 20
    state = ensure_reactive_state(eng)
    state._reactive_restore_damp_until = 102.0
    state._reactive_restore_phase = ReactiveRestorePhase.DAMPING

    import keyrgb.core.effects.reactive.render as render_module

    original_monotonic = render_module.time.monotonic
    render_module.time.monotonic = lambda: 100.0
    try:
        # baseline=20/50=0.4, pulse=1.0, damp@start=0.35
        # final = 0.4 + (1.0 - 0.4) * 0.35 = 0.61
        assert pulse_brightness_scale_factor(eng) == pytest.approx(0.61)
        undamped = _DummyEngine(brightness=20, reactive_brightness=50)
        undamped.per_key_colors = {(0, 0): (0, 0, 0)}
        undamped.per_key_brightness = 20
        assert pulse_brightness_scale_factor(undamped) == pytest.approx(1.0)
    finally:
        render_module.time.monotonic = original_monotonic


def test_pulse_brightness_damps_eff_le_hw_path_during_restore() -> None:
    """Restore damp also applies when reactive slider is not above backdrop hw."""
    from keyrgb.core.effects.reactive._render_brightness_support import (
        ReactiveRestorePhase,
        ensure_reactive_state,
    )

    eng = _DummyEngine(brightness=20, reactive_brightness=20)
    eng.per_key_colors = {(0, 0): (0, 0, 0)}
    eng.per_key_brightness = 20
    state = ensure_reactive_state(eng)
    state._reactive_restore_damp_until = 102.0
    state._reactive_restore_phase = ReactiveRestorePhase.DAMPING

    import keyrgb.core.effects.reactive.render as render_module

    original_monotonic = render_module.time.monotonic
    render_module.time.monotonic = lambda: 100.0
    try:
        undamped = pulse_brightness_scale_factor(_DummyEngine(brightness=20, reactive_brightness=20))
        damped = pulse_brightness_scale_factor(eng)
        assert undamped == pytest.approx(0.4)
        assert damped == pytest.approx(undamped * 0.35)
    finally:
        render_module.time.monotonic = original_monotonic


def test_pulse_brightness_reseeds_restore_damp_on_first_post_restore_pulse() -> None:
    from keyrgb.core.effects.reactive import effects
    from keyrgb.core.effects.reactive._render_brightness_support import (
        ReactiveRestorePhase,
        ensure_reactive_state,
    )

    eng = _DummyEngine(brightness=5, reactive_brightness=50)
    eng.per_key_colors = {(0, 0): (0, 0, 0)}
    eng.per_key_brightness = 5
    state = ensure_reactive_state(eng)
    state._reactive_restore_damp_until = 99.0
    state._reactive_restore_phase = ReactiveRestorePhase.FIRST_PULSE_PENDING

    import keyrgb.core.effects.reactive.render as render_module

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
    from keyrgb.core.effects.reactive import _render_brightness_support as reactive_support, effects
    from keyrgb.core.effects.reactive.render import _resolve_brightness
    from keyrgb.tray.pollers.idle_power._transition_actions import _seed_reactive_restore_windows

    class _Clock:
        def __init__(self, now: float) -> None:
            self.now = now

        def monotonic(self) -> float:
            return self.now

    clock = _Clock(100.0)
    monkeypatch.setattr("keyrgb.tray.pollers.idle_power._transition_actions.time.monotonic", clock.monotonic)
    monkeypatch.setattr("keyrgb.core.effects.reactive.effects.time.monotonic", clock.monotonic)
    monkeypatch.setattr("keyrgb.core.effects.reactive.render.time.monotonic", clock.monotonic)
    monkeypatch.setattr("keyrgb.core.effects.reactive._render_brightness.time.monotonic", clock.monotonic)
    monkeypatch.setattr("keyrgb.core.effects.reactive._render_brightness_support.time.monotonic", clock.monotonic)

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

    with caplog.at_level(logging.INFO, logger="keyrgb.core.effects.reactive.render"):
        pulse_brightness_scale_factor(eng)

    messages = [record.getMessage() for record in caplog.records if "reactive_pulse_visual:" in record.getMessage()]
    assert messages
    assert "visual_hw=5" in messages[-1]
    assert "pulse_scale=1.000" in messages[-1]
    assert "very_dim_curve=True" in messages[-1]
    assert "post_restore_damp=1.000" in messages[-1]


def test_pulse_brightness_logs_post_restore_damp_under_debug(monkeypatch, caplog) -> None:
    from keyrgb.core.effects.reactive._render_brightness_support import (
        ReactiveRestorePhase,
        ensure_reactive_state,
    )

    eng = _DummyEngine(brightness=5, reactive_brightness=50)
    eng.per_key_colors = {(0, 0): (0, 0, 0)}
    eng.per_key_brightness = 5
    state = ensure_reactive_state(eng)
    state._reactive_restore_damp_until = 102.0
    state._reactive_restore_phase = ReactiveRestorePhase.DAMPING

    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")
    monkeypatch.setattr("keyrgb.core.effects.reactive.render.time.monotonic", lambda: 100.0)

    with caplog.at_level(logging.INFO, logger="keyrgb.core.effects.reactive.render"):
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

    import keyrgb.core.effects.reactive.render as render_module

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


def test_subtle_visual_mode_softens_midrange_per_key_pulse_scale() -> None:
    eng_vivid = _DummyEngine(brightness=40, reactive_brightness=20, reactive_visual_mode="vivid")
    eng_subtle = _DummyEngine(brightness=40, reactive_brightness=20, reactive_visual_mode="subtle")

    assert pulse_brightness_scale_factor(eng_subtle) < pulse_brightness_scale_factor(eng_vivid)


def test_active_pulse_mix_does_not_lift_hw_on_per_key_backends() -> None:
    from keyrgb.core.effects.reactive.render import _resolve_brightness

    eng = _DummyEngine(brightness=10, reactive_brightness=50)
    eng._last_rendered_brightness = 10
    eng._reactive_active_pulse_mix = 1.0

    _base, eff, hw = _resolve_brightness(eng)

    assert eff == 50
    assert hw == 10


def test_active_pulse_mix_can_lift_hw_on_uniform_backends() -> None:
    from keyrgb.core.effects.reactive.render import _resolve_brightness

    eng = _DummyEngine(brightness=10, reactive_brightness=50, has_per_key=False)
    eng._last_rendered_brightness = 10
    eng._reactive_active_pulse_mix = 1.0

    _base, eff, hw = _resolve_brightness(eng)

    assert eff == 50
    assert hw == 10


def test_active_pulse_mix_can_lift_after_uniform_backend_streak() -> None:
    from keyrgb.core.effects.reactive.render import _resolve_brightness

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


def test_pulse_return_to_idle_skips_guard_tail() -> None:
    from keyrgb.core.effects.reactive.render import _resolve_brightness

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
    from keyrgb.core.effects.reactive.render import _resolve_brightness

    eng = _DummyEngine(brightness=10, reactive_brightness=50, has_per_key=False)
    eng._last_rendered_brightness = 10
    eng._reactive_active_pulse_mix = 1.0
    eng._reactive_disable_pulse_hw_lift_until = time.monotonic() + 5.0

    _base, eff, hw = _resolve_brightness(eng)

    assert eff == 50
    assert hw == 10


def test_resolve_brightness_logs_hw_lift_cooldown_reason_under_debug(monkeypatch, caplog) -> None:
    from keyrgb.core.effects.reactive.render import _resolve_brightness

    now = 100.0
    eng = _DummyEngine(brightness=10, reactive_brightness=50, has_per_key=False)
    eng._last_rendered_brightness = 10
    eng._reactive_active_pulse_mix = 1.0
    eng._reactive_uniform_hw_streak = 5
    eng._reactive_disable_pulse_hw_lift_until = now + 2.5

    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")
    monkeypatch.setattr("keyrgb.core.effects.reactive._render_brightness.time.monotonic", lambda: now)
    monkeypatch.setattr(
        "keyrgb.core.effects.reactive._render_brightness_support.time.monotonic",
        lambda: now,
    )

    with caplog.at_level(logging.INFO, logger="keyrgb.core.effects.reactive.render"):
        _resolve_brightness(eng)

    messages = [record.getMessage() for record in caplog.records if "reactive_hw_lift:" in record.getMessage()]
    assert messages
    assert "reason=cooldown" in messages[-1]
    assert "cooldown_remaining_s=2.50" in messages[-1]


def test_post_restore_frame_scale_is_monotonic_and_phase_independent_across_fade() -> None:
    """Whole-frame restore scale must be monotonic and reach 1.0 by fade duration.

    Independent of FIRST_PULSE_PENDING→DAMPING flip; pulse damp may continue
    after the frame envelope ends.
    """
    from keyrgb.core.effects.reactive._reactive_restore_seed import seed_reactive_restore_windows
    from keyrgb.core.effects.reactive._render_brightness_support import (
        ReactiveRestorePhase,
        ensure_reactive_state,
    )
    from keyrgb.core.effects.reactive.render import _post_restore_frame_scale

    eng = _DummyEngine(brightness=20, reactive_brightness=50)
    eng.per_key_colors = {(0, 0): (0, 0, 0)}
    eng.per_key_brightness = 20

    import keyrgb.core.effects.reactive.render as render_module

    seed_reactive_restore_windows(eng, fade_in_duration_s=0.42, now=100.0)
    state = ensure_reactive_state(eng)
    assert state._reactive_restore_phase is ReactiveRestorePhase.FIRST_PULSE_PENDING
    assert state._reactive_restore_frame_duration_s == pytest.approx(0.42)

    original = render_module.time.monotonic
    try:
        # At envelope start → FRAME_MIN
        render_module.time.monotonic = lambda: 100.0
        v0 = _post_restore_frame_scale(eng)
        assert v0 == pytest.approx(0.62)
        # Phase flip must not cause discontinuity.
        state._reactive_restore_phase = ReactiveRestorePhase.DAMPING
        assert _post_restore_frame_scale(eng) == pytest.approx(v0)
        # Flip back also stable.
        state._reactive_restore_phase = ReactiveRestorePhase.FIRST_PULSE_PENDING
        assert _post_restore_frame_scale(eng) == pytest.approx(v0)

        # Monotonic rise through fade duration.
        render_module.time.monotonic = lambda: 100.21
        v_mid = _post_restore_frame_scale(eng)
        assert v_mid > v0
        assert v_mid == pytest.approx(0.62 + (1.0 - 0.62) * (0.21 / 0.42))

        render_module.time.monotonic = lambda: 100.42
        assert _post_restore_frame_scale(eng) == pytest.approx(1.0)

        # After envelope, still 1.0 even though pulse damp continues (until ~104).
        render_module.time.monotonic = lambda: 101.0
        assert _post_restore_frame_scale(eng) == pytest.approx(1.0)
        assert state._reactive_restore_damp_until == pytest.approx(104.0)

        # Strict monotonic sequence.
        seq = []
        for t in [100.0, 100.1, 100.2, 100.3, 100.42, 100.5]:
            render_module.time.monotonic = lambda t=t: t  # type: ignore[misc]
            seq.append(_post_restore_frame_scale(eng))
        assert seq == sorted(seq)
        assert seq[0] == pytest.approx(0.62)
        assert seq[-1] == pytest.approx(1.0)
    finally:
        render_module.time.monotonic = original


def test_start_current_effect_for_idle_restore_does_not_reset_damping_to_first_pulse_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seed queued before start must survive stop but post-start must not reseed DAMPING."""
    from keyrgb.core.effects.reactive import effects
    from keyrgb.core.effects.reactive._render_brightness_support import (
        ReactiveRenderState,
        ReactiveRestorePhase,
        ensure_reactive_state,
    )
    from keyrgb.tray.pollers.idle_power._transition_actions import start_current_effect_for_idle_restore

    # Shared monotonic clock so seed and frame envelope are deterministic.
    class _Clock:
        def __init__(self) -> None:
            self.now = 100.0

        def monotonic(self) -> float:
            return self.now

    clock = _Clock()
    monkeypatch.setattr("keyrgb.tray.pollers.idle_power._transition_actions.time.monotonic", clock.monotonic)
    monkeypatch.setattr("keyrgb.core.effects.reactive._reactive_restore_seed.time.monotonic", clock.monotonic)
    monkeypatch.setattr("keyrgb.core.effects.reactive.render.time.monotonic", clock.monotonic)

    # Minimal engine with real ReactiveRenderState semantics and queued-seed support.
    eng = SimpleNamespace()
    eng._reactive_state = ReactiveRenderState()

    # Fake tray; start_current_effect simulates engine.stop() plus first-key DAMPING flip.
    def _fake_start_current_effect(*_args, **_kwargs):
        # Simulate engine.stop(): fresh state + apply queued seed.
        eng._reactive_state = ReactiveRenderState()
        from keyrgb.core.effects.reactive._reactive_restore_seed import apply_queued_reactive_restore_seed

        apply_queued_reactive_restore_seed(eng)
        # Now first reactive key arrives during the blocking fade: FIRST_PULSE_PENDING→DAMPING
        state = ensure_reactive_state(eng)
        assert state._reactive_restore_phase is ReactiveRestorePhase.FIRST_PULSE_PENDING
        # Use the real first-pulse state transition while the start fade owns
        # the caller. The original 4 s seed remains later than the 2 s pulse
        # extension; only the phase changes to DAMPING.
        effects._set_reactive_active_pulse_mix(eng, target=1.0)
        # Advance clock to simulate blocking start returning later.
        clock.now = 100.3
        return True

    tray = SimpleNamespace(
        config=SimpleNamespace(effect="reactive_ripple", brightness=20),
        engine=eng,
        is_off=False,
    )
    tray._start_current_effect = _fake_start_current_effect  # type: ignore[attr-defined]
    # Provide idle_power_state owner for loop-effect-ramp flag writes.
    tray.tray_idle_power_state = SimpleNamespace(idle_restore_loop_effect_ramp=False)

    start_current_effect_for_idle_restore(
        tray,  # type: ignore[arg-type]
        brightness_override=1,
        fade_in=True,
        fade_in_duration_s=0.42,
    )

    state = ensure_reactive_state(eng)
    # Post-start must NOT have reset DAMPING to FIRST_PULSE_PENDING nor reseeded frame start.
    assert state._reactive_restore_phase is ReactiveRestorePhase.DAMPING
    assert state._reactive_restore_frame_started_at == pytest.approx(100.0)
    assert state._reactive_restore_frame_duration_s == pytest.approx(0.42)
    # The original deadline survives. A fresh post-start seed would move it to
    # 104.3 and reset the phase to FIRST_PULSE_PENDING.
    assert state._reactive_restore_damp_until == pytest.approx(104.0)
