from __future__ import annotations

import logging
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


def test_post_fade_reactive_release_removes_effect_target_step(monkeypatch) -> None:
    from keyrgb.core.effects.reactive import _render_brightness_transition
    from keyrgb.core.effects.reactive._render_brightness_support import (
        ReactiveRestorePhase,
        ensure_reactive_state,
    )

    eng = _DummyEngine(brightness=10, reactive_brightness=50)
    eng.per_key_colors = {(0, 0): (0, 0, 0)}
    eng.per_key_brightness = 10
    eng._last_rendered_brightness = 10
    state = ensure_reactive_state(eng)
    state._reactive_restore_damp_until = 204.0
    state._reactive_restore_phase = ReactiveRestorePhase.DAMPING
    state._reactive_transition_from_brightness = 10
    state._reactive_transition_to_brightness = 50
    state._reactive_transition_started_at = 200.0
    state._reactive_transition_duration_s = 0.42
    clock = SimpleNamespace(now=200.0)
    monkeypatch.setattr("keyrgb.core.effects.reactive.render.time.monotonic", lambda: clock.now)
    monkeypatch.setattr(_render_brightness_transition.time, "monotonic", lambda: clock.now)

    scales = [pulse_brightness_scale_factor(eng)]
    clock.now = 200.01
    scales.append(pulse_brightness_scale_factor(eng))
    clock.now = 200.21
    scales.append(pulse_brightness_scale_factor(eng))
    clock.now = 200.42
    scales.append(pulse_brightness_scale_factor(eng))

    assert scales[0] == pytest.approx(0.07)
    assert scales[1] < 0.09
    assert 0.27 <= scales[2] <= 0.30
    assert scales[3] == pytest.approx(0.48)
    assert scales == sorted(scales)


def test_post_fade_release_matches_lower_effect_target_over_brighter_base(monkeypatch) -> None:
    from keyrgb.core.effects.reactive import _render_brightness_transition
    from keyrgb.core.effects.reactive._render_brightness_support import (
        ReactiveRestorePhase,
        ensure_reactive_state,
    )

    eng = _DummyEngine(brightness=10, reactive_brightness=20)
    eng.per_key_colors = {(0, 0): (0, 0, 0)}
    eng.per_key_brightness = 50
    eng._last_rendered_brightness = 10
    state = ensure_reactive_state(eng)
    state._reactive_restore_damp_until = 204.0
    state._reactive_restore_phase = ReactiveRestorePhase.DAMPING
    state._reactive_transition_from_brightness = 10
    state._reactive_transition_to_brightness = 50
    state._reactive_transition_started_at = 200.0
    state._reactive_transition_duration_s = 0.42
    clock = SimpleNamespace(now=200.0)
    monkeypatch.setattr("keyrgb.core.effects.reactive.render.time.monotonic", lambda: clock.now)
    monkeypatch.setattr(_render_brightness_transition.time, "monotonic", lambda: clock.now)

    scales = [pulse_brightness_scale_factor(eng)]
    clock.now = 200.21
    scales.append(pulse_brightness_scale_factor(eng))
    clock.now = 200.42
    scales.append(pulse_brightness_scale_factor(eng))

    assert scales == pytest.approx([0.07, 0.105, 0.14])
    assert scales == sorted(scales)


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

    eng._reactive_state = ReactiveRenderState()
    assert apply_queued_reactive_restore_seed(eng) is True
    state = ensure_reactive_state(eng)
    assert state._reactive_restore_phase is ReactiveRestorePhase.FIRST_PULSE_PENDING
    assert state._reactive_restore_damp_until == pytest.approx(104.0)
    assert state._reactive_disable_pulse_hw_lift_until == pytest.approx(102.0)
    assert state._reactive_restore_frame_started_at == pytest.approx(100.0)
    assert state._reactive_restore_frame_duration_s == pytest.approx(0.42)
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
    seed_reactive_restore_windows(eng, fade_in_duration_s=0.42, now=100.0)
    state = ensure_reactive_state(eng)
    assert state._reactive_restore_phase is ReactiveRestorePhase.FIRST_PULSE_PENDING

    import keyrgb.core.effects.reactive.render as render_module

    original_monotonic = render_module.time.monotonic
    render_module.time.monotonic = lambda: 100.0
    try:
        assert _post_restore_frame_scale(eng) == pytest.approx(0.62)
        assert _resolve_transition_visual_scale(eng) == pytest.approx(0.62)
        state._reactive_restore_phase = ReactiveRestorePhase.DAMPING
        assert _post_restore_frame_scale(eng) == pytest.approx(0.62)
        assert _resolve_transition_visual_scale(eng) == pytest.approx(0.62)
        render_module.time.monotonic = lambda: 100.5
        assert _post_restore_frame_scale(eng) == pytest.approx(1.0)
        assert _resolve_transition_visual_scale(eng) == pytest.approx(1.0)
        state._reactive_restore_phase = ReactiveRestorePhase.NORMAL
        state._reactive_restore_damp_until = None
        state._reactive_restore_frame_started_at = None
        state._reactive_restore_frame_duration_s = None
        assert _post_restore_frame_scale(eng) == pytest.approx(1.0)
        assert _resolve_transition_visual_scale(eng) == pytest.approx(1.0)
    finally:
        render_module.time.monotonic = original_monotonic


def test_pulse_brightness_damps_normal_base_post_restore_bursts() -> None:
    """Typing-wake flash regression: damp must apply at base>=10 (e.g. 20)."""
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


def test_wake_path_reseeds_restore_damp_after_initial_window_expires(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_post_restore_frame_scale_is_monotonic_and_phase_independent_across_fade() -> None:
    """Whole-frame restore scale must be monotonic and reach 1.0 by fade duration."""
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
        render_module.time.monotonic = lambda: 100.0
        v0 = _post_restore_frame_scale(eng)
        assert v0 == pytest.approx(0.62)
        state._reactive_restore_phase = ReactiveRestorePhase.DAMPING
        assert _post_restore_frame_scale(eng) == pytest.approx(v0)
        state._reactive_restore_phase = ReactiveRestorePhase.FIRST_PULSE_PENDING
        assert _post_restore_frame_scale(eng) == pytest.approx(v0)

        render_module.time.monotonic = lambda: 100.21
        v_mid = _post_restore_frame_scale(eng)
        assert v_mid > v0
        assert v_mid == pytest.approx(0.62 + (1.0 - 0.62) * (0.21 / 0.42))

        render_module.time.monotonic = lambda: 100.42
        assert _post_restore_frame_scale(eng) == pytest.approx(1.0)
        render_module.time.monotonic = lambda: 101.0
        assert _post_restore_frame_scale(eng) == pytest.approx(1.0)
        assert state._reactive_restore_damp_until == pytest.approx(104.0)

        seq = []
        for t in [100.0, 100.1, 100.2, 100.3, 100.42, 100.5]:
            render_module.time.monotonic = lambda t=t: t  # type: ignore[misc]
            seq.append(_post_restore_frame_scale(eng))
        assert seq == sorted(seq)
        assert seq[0] == pytest.approx(0.62)
        assert seq[-1] == pytest.approx(1.0)
    finally:
        render_module.time.monotonic = original
