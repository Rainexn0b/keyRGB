#!/usr/bin/env python3
"""Unit tests for run_reactive_ripple_loop startup/stop-event paths."""

from __future__ import annotations

from types import SimpleNamespace


class _StopAfterWaitEvent:
    """stop_event stub that sets engine.running=False on the first wait() call."""

    def __init__(self) -> None:
        self._engine: object = None
        self.wait_count = 0

    def bind(self, engine: object) -> None:
        self._engine = engine

    def is_set(self) -> bool:
        return False

    def wait(self, dt: float) -> None:
        self.wait_count += 1
        if self._engine is not None:
            self._engine.running = False  # type: ignore[union-attr]


class _MockPressSource:
    def __init__(self, *, slot_id_sequence: tuple = (None,)) -> None:
        self.spawn_interval_s: float = 0.45
        self._slots = list(slot_id_sequence)
        self._idx = 0
        self.close_called = False

    def poll_slot_ids(self, *, dt: float) -> list[str]:
        if self._idx < len(self._slots):
            result = self._slots[self._idx]
            self._idx += 1
            return [] if result is None else [result]
        return []

    def close(self) -> None:
        self.close_called = True


class _AlreadySetEvent:
    def is_set(self) -> bool:
        return True

    def wait(self, _dt: float) -> None:
        return


class _SetAfterFirstCheckEvent:
    def __init__(self) -> None:
        self.check_count = 0

    def is_set(self) -> bool:
        self.check_count += 1
        return self.check_count > 1

    def wait(self, _dt: float) -> None:
        return


class _TrackingStartupApi:
    _PressSource = None

    def __init__(self, press: _MockPressSource) -> None:
        self.press = press
        self.create_press_calls = 0
        self.load_keymap_calls = 0
        self.render_calls = 0

    def frame_dt_s(self) -> float:
        return 0.001

    def try_open_evdev_keyboards(self):
        return None

    def reactive_synthetic_fallback_enabled(self) -> bool:
        return False

    def load_active_profile_slot_keymap(self):
        return {}

    def create_press_source(self, _engine, **_kwargs):
        self.create_press_calls += 1
        return self.press

    def load_slot_keymap(self, **_kwargs):
        self.load_keymap_calls += 1
        return {}

    def render(self, _engine, **_kwargs) -> None:
        self.render_calls += 1


def _make_engine(*, reactive_brightness: int = 0, has_per_key_writer: bool = False) -> SimpleNamespace:
    """Build a minimal engine SimpleNamespace for loop tests."""
    stop_event = _StopAfterWaitEvent()
    kb = SimpleNamespace()
    if has_per_key_writer:
        kb.set_key_colors = lambda keys: None

    engine = SimpleNamespace(
        backend_caps=SimpleNamespace(per_key=has_per_key_writer),
        running=True,
        stop_event=stop_event,
        reactive_brightness=reactive_brightness,
        brightness=25,
        reactive_trail_percent=40,
        kb=kb,
    )
    stop_event.bind(engine)
    return engine


# ── run_reactive_ripple_loop: startup scenarios ───────────────────────────────


class TestRunReactiveRippleLoopStartup:
    def test_stopped_replacement_worker_does_not_open_input(self):
        from keyrgb.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=True)
        engine.stop_event = _AlreadySetEvent()
        api = _TrackingStartupApi(_MockPressSource())

        run_reactive_ripple_loop(engine, api=api)

        assert api.create_press_calls == 0
        assert api.load_keymap_calls == 0
        assert api.render_calls == 0
        assert not api.press.close_called

    def test_worker_stopped_during_input_open_closes_without_rendering(self):
        from keyrgb.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=True)
        engine.stop_event = _SetAfterFirstCheckEvent()
        api = _TrackingStartupApi(_MockPressSource())

        run_reactive_ripple_loop(engine, api=api)

        assert api.create_press_calls == 1
        assert api.load_keymap_calls == 1
        assert api.render_calls == 0
        assert api.press.close_called

    def test_stopped_fade_replacement_worker_does_not_open_input(self):
        from keyrgb.core.effects.reactive._fade_loop import run_reactive_fade_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=True)
        engine.stop_event = _AlreadySetEvent()
        api = _TrackingStartupApi(_MockPressSource())

        run_reactive_fade_loop(engine, api=api)

        assert api.create_press_calls == 0
        assert api.load_keymap_calls == 0
        assert api.render_calls == 0
        assert not api.press.close_called

    def test_fade_worker_stopped_during_input_open_closes_without_rendering(self):
        from keyrgb.core.effects.reactive._fade_loop import run_reactive_fade_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=True)
        engine.stop_event = _SetAfterFirstCheckEvent()
        api = _TrackingStartupApi(_MockPressSource())

        run_reactive_fade_loop(engine, api=api)

        assert api.create_press_calls == 1
        assert api.load_keymap_calls == 1
        assert api.render_calls == 0
        assert api.press.close_called
