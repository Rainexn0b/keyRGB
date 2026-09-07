from __future__ import annotations

import logging
import time
from types import SimpleNamespace

import pytest


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
    for _ in range(12):
        _base, eff, hw = _resolve_brightness(eng)
        eng._last_rendered_brightness = hw

    assert eff == 50
    assert hw == 50


def test_pulse_return_to_idle_skips_guard_tail() -> None:
    from keyrgb.core.effects.reactive.render import _resolve_brightness

    eng = _DummyEngine(brightness=10, reactive_brightness=50, has_per_key=False)
    eng._last_rendered_brightness = 50
    eng._reactive_active_pulse_mix = 0.0

    _base, eff, hw = _resolve_brightness(eng)

    assert eff == 50
    assert hw == 10


def test_controller_handoff_forces_uniform_pulse_return_step_guard() -> None:
    from keyrgb.core.effects.reactive._render_brightness_support import ensure_reactive_state
    from keyrgb.core.effects.reactive.render import _resolve_brightness

    eng = _DummyEngine(brightness=10, reactive_brightness=50, has_per_key=False)
    eng._last_rendered_brightness = 50
    eng._reactive_active_pulse_mix = 1.0
    eng._reactive_controller_brightness_handoff_active = True

    _base, eff, hw = _resolve_brightness(eng)

    assert eff == 50
    assert hw == 42
    assert ensure_reactive_state(eng)._reactive_controller_brightness_handoff_active is True


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
    monkeypatch.setattr("keyrgb.core.effects.reactive._render_brightness_support.time.monotonic", lambda: now)

    with caplog.at_level(logging.INFO, logger="keyrgb.core.effects.reactive.render"):
        _resolve_brightness(eng)

    messages = [record.getMessage() for record in caplog.records if "reactive_hw_lift:" in record.getMessage()]
    assert messages
    assert "reason=cooldown" in messages[-1]
    assert "cooldown_remaining_s=2.50" in messages[-1]


def test_start_current_effect_for_idle_restore_does_not_reset_damping_to_first_pulse_pending(
    monkeypatch,
) -> None:
    """Seed queued before start must survive stop but post-start must not reseed DAMPING."""
    from keyrgb.core.effects.reactive import effects
    from keyrgb.core.effects.reactive._render_brightness_support import (
        ReactiveRenderState,
        ReactiveRestorePhase,
        ensure_reactive_state,
    )
    from keyrgb.tray.pollers.idle_power._transition_actions import start_current_effect_for_idle_restore

    class _Clock:
        def __init__(self) -> None:
            self.now = 100.0

        def monotonic(self) -> float:
            return self.now

    clock = _Clock()
    monkeypatch.setattr("keyrgb.tray.pollers.idle_power._transition_actions.time.monotonic", clock.monotonic)
    monkeypatch.setattr("keyrgb.core.effects.reactive._reactive_restore_seed.time.monotonic", clock.monotonic)
    monkeypatch.setattr("keyrgb.core.effects.reactive.render.time.monotonic", clock.monotonic)

    eng = SimpleNamespace()
    eng._reactive_state = ReactiveRenderState()

    def _fake_start_current_effect(*_args, **_kwargs):
        eng._reactive_state = ReactiveRenderState()
        from keyrgb.core.effects.reactive._reactive_restore_seed import apply_queued_reactive_restore_seed

        apply_queued_reactive_restore_seed(eng)
        state = ensure_reactive_state(eng)
        assert state._reactive_restore_phase is ReactiveRestorePhase.FIRST_PULSE_PENDING
        effects._set_reactive_active_pulse_mix(eng, target=1.0)
        clock.now = 100.3
        return True

    tray = SimpleNamespace(
        config=SimpleNamespace(effect="reactive_ripple", brightness=20),
        engine=eng,
        is_off=False,
    )
    tray._start_current_effect = _fake_start_current_effect  # type: ignore[attr-defined]
    tray.tray_idle_power_state = SimpleNamespace(idle_restore_loop_effect_ramp=False)

    start_current_effect_for_idle_restore(
        tray,  # type: ignore[arg-type]
        brightness_override=1,
        fade_in=True,
        fade_in_duration_s=0.42,
    )

    state = ensure_reactive_state(eng)
    assert state._reactive_restore_phase is ReactiveRestorePhase.DAMPING
    assert state._reactive_restore_frame_started_at == pytest.approx(100.0)
    assert state._reactive_restore_frame_duration_s == pytest.approx(0.42)
    assert state._reactive_restore_damp_until == pytest.approx(104.0)
