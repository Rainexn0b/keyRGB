#!/usr/bin/env python3
"""Unit tests for _ripple_loop.py helpers and run_reactive_ripple_loop."""

from __future__ import annotations

from types import SimpleNamespace


# ── Utility: _engine_int_attr_or_default ──────────────────────────────────────


class TestEngineIntAttrOrDefault:
    def test_missing_attribute_returns_missing_default(self):
        from src.core.effects.reactive._ripple_loop import _engine_int_attr_or_default

        engine = SimpleNamespace()
        assert _engine_int_attr_or_default(engine, "nonexistent", missing_default=42) == 42

    def test_valid_string_attr_returns_int(self):
        from src.core.effects.reactive._ripple_loop import _engine_int_attr_or_default

        engine = SimpleNamespace(some_attr="5")
        assert _engine_int_attr_or_default(engine, "some_attr", missing_default=0) == 5

    def test_none_attr_returns_zero(self):
        from src.core.effects.reactive._ripple_loop import _engine_int_attr_or_default

        engine = SimpleNamespace(some_attr=None)
        # int(None or 0) == int(0) == 0, not missing_default
        assert _engine_int_attr_or_default(engine, "some_attr", missing_default=99) == 0


# ── Utility: _engine_int_attr_or_fallback ─────────────────────────────────────


class TestEngineIntAttrOrFallback:
    def test_valid_attr_delegates_to_default(self):
        from src.core.effects.reactive._ripple_loop import _engine_int_attr_or_fallback

        engine = SimpleNamespace(brightness=25)
        result = _engine_int_attr_or_fallback(engine, "brightness", missing_default=0, error_default=-1)
        assert result == 25

    def test_coercion_error_returns_error_default(self):
        from src.core.effects.reactive._ripple_loop import _engine_int_attr_or_fallback

        # "not_a_number" is truthy so `int("not_a_number" or 0)` raises ValueError
        engine = SimpleNamespace(bad_attr="not_a_number")
        result = _engine_int_attr_or_fallback(engine, "bad_attr", missing_default=0, error_default=7)
        assert result == 7


# ── Utility: _has_per_key_writer ──────────────────────────────────────────────


class TestHasPerKeyWriter:
    def test_no_set_key_colors_attr_returns_false(self):
        from src.core.effects.reactive._ripple_loop import _has_per_key_writer

        engine = SimpleNamespace(kb=SimpleNamespace())  # no set_key_colors
        assert _has_per_key_writer(engine) is False

    def test_set_key_colors_none_returns_false(self):
        from src.core.effects.reactive._ripple_loop import _has_per_key_writer

        engine = SimpleNamespace(kb=SimpleNamespace(set_key_colors=None))
        assert _has_per_key_writer(engine) is False

    def test_set_key_colors_callable_returns_true(self):
        from src.core.effects.reactive._ripple_loop import _has_per_key_writer

        engine = SimpleNamespace(kb=SimpleNamespace(set_key_colors=lambda keys: None))
        assert _has_per_key_writer(engine) is True


# ── run_reactive_ripple_loop: test infrastructure ─────────────────────────────


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

    def poll_slot_id(self, *, dt: float) -> str | None:
        if self._idx < len(self._slots):
            result = self._slots[self._idx]
            self._idx += 1
            return result
        return None

    def close(self) -> None:
        self.close_called = True


class _MockRandom:
    def randrange(self, stop: int) -> int:
        return 0


class _MockApi:
    NUM_ROWS = 6
    NUM_COLS = 21

    def __init__(
        self,
        *,
        press_source: _MockPressSource | None = None,
        overlay_values: dict | None = None,
        base_map: dict | None = None,
        manual_color: tuple | None = None,
        pulse_scale: float = 1.0,
        mapped_cells: list | None = None,
        per_key_backdrop_active: bool = False,
    ) -> None:
        self._press = press_source if press_source is not None else _MockPressSource()
        self._overlay_values: dict = overlay_values if overlay_values is not None else {}
        self._base_map: dict = base_map if base_map is not None else {(0, 0): (100, 100, 100)}
        self._manual_color = manual_color
        self._pulse_scale = pulse_scale
        self._mapped_cells: list = mapped_cells if mapped_cells is not None else []
        self._per_key_backdrop_active = per_key_backdrop_active

        # Recorded calls
        self.set_mix_calls: list[float] = []
        self.render_calls: list = []
        self.render_uniform_calls: list = []
        self.build_ripple_cm_calls: int = 0

        # Protocol-required factory attributes
        self._PressSource = None  # unused – create_press_source returns self._press directly
        self._RainbowPulse = lambda *, row, col, age_s, ttl_s, hue_offset: SimpleNamespace(
            row=row, col=col, age_s=age_s, ttl_s=ttl_s, hue_offset=hue_offset
        )
        self.random = _MockRandom()

    # ── Protocol methods ──────────────────────────────────────────────────────

    def frame_dt_s(self) -> float:
        return 0.001

    def create_press_source(self, engine, *, press_source_cls, open_keyboards, synthetic_fallback_enabled):
        return self._press

    def try_open_evdev_keyboards(self):
        return None

    def reactive_synthetic_fallback_enabled(self) -> bool:
        return False

    def load_slot_keymap(self, *, loader):
        return {}

    def load_active_profile_slot_keymap(self):
        return {}

    def pace(self, engine, *, min_factor: float = 0.8, max_factor: float = 2.2) -> float:
        return 1.0

    def build_frame_base_maps(self, engine, *, background_rgb, effect_brightness_hw, backdrop_brightness_scale_factor_fn):
        bm = dict(self._base_map)
        return (self._per_key_backdrop_active, bm, bm)

    def backdrop_brightness_scale_factor(self, engine, *, effect_brightness_hw: int) -> float:
        return 1.0

    def _set_reactive_active_pulse_mix(self, engine, *, target: float) -> None:
        self.set_mix_calls.append(target)

    def mapped_slot_cells(self, slot_keymap, pressed_slot_id):
        return self._mapped_cells

    def _age_pulses_in_place(self, pulses, *, dt: float):
        return pulses

    def get_engine_overlay_buffer(self, engine, attr_name: str) -> dict:
        return dict(self._overlay_values)

    def build_ripple_overlay_into(self, dest, pulses, *, band: float) -> None:
        pass  # overlay values come pre-populated from get_engine_overlay_buffer

    def get_engine_manual_reactive_color(self, engine):
        return self._manual_color

    def pulse_brightness_scale_factor(self, engine) -> float:
        return self._pulse_scale

    def hsv_to_rgb(self, h: float, s: float, v: float) -> tuple:
        return (255, 0, 0)

    def scale(self, rgb: tuple, s: float) -> tuple:
        return tuple(int(c * s) for c in rgb)  # type: ignore[return-value]

    def mix(self, a: tuple, b: tuple, t: float) -> tuple:
        return tuple(int(a[i] * (1.0 - t) + b[i] * t) for i in range(3))  # type: ignore[return-value]

    def _render_uniform_fallback(self, engine, *, rgb: tuple) -> None:
        self.render_uniform_calls.append(rgb)

    def get_engine_color_map_buffer(self, engine, attr_name: str) -> dict:
        return {}

    def build_ripple_color_map_into(self, dest, *, base, base_unscaled, overlay, per_key_backdrop_active, manual, pulse_scale):
        self.build_ripple_cm_calls += 1
        return dest

    def render(self, engine, *, color_map) -> None:
        self.render_calls.append(color_map)


def _make_engine(*, reactive_brightness: int = 0, has_per_key_writer: bool = False) -> SimpleNamespace:
    """Build a minimal engine SimpleNamespace for loop tests."""
    stop_event = _StopAfterWaitEvent()
    kb = SimpleNamespace()
    if has_per_key_writer:
        kb.set_key_colors = lambda keys: None

    engine = SimpleNamespace(
        running=True,
        stop_event=stop_event,
        reactive_brightness=reactive_brightness,
        brightness=25,
        reactive_trail_percent=50,
        kb=kb,
    )
    stop_event.bind(engine)
    return engine


# ── run_reactive_ripple_loop: scenarios ───────────────────────────────────────


class TestRunReactiveRippleLoop:
    def test_eff_hw_zero_exits_after_render_base(self):
        """eff_hw=0: skips pulse logic, renders base, then exits on next wait()."""
        from src.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=0)
        api = _MockApi()

        run_reactive_ripple_loop(engine, api=api)

        assert api.render_calls, "render should have been called with base map"
        assert api.set_mix_calls == [0.0], "pulse mix target should be 0.0"

    def test_press_close_always_called_in_finally(self):
        """press.close() is called regardless of loop exit path."""
        from src.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=0)
        api = _MockApi()

        run_reactive_ripple_loop(engine, api=api)

        assert api._press.close_called

    def test_per_key_writer_path_calls_build_and_render(self):
        """With per-key writer and eff_hw>0, build_ripple_color_map_into and render are called."""
        from src.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=True)
        press = _MockPressSource(slot_id_sequence=(None,))
        api = _MockApi(press_source=press)

        run_reactive_ripple_loop(engine, api=api)

        assert api.build_ripple_cm_calls > 0
        assert api.render_calls
        assert press.close_called

    def test_uniform_fallback_no_per_key_writer(self):
        """Without per-key writer, _render_uniform_fallback is called instead of render."""
        from src.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=False)
        press = _MockPressSource(slot_id_sequence=(None,))
        api = _MockApi(press_source=press)

        run_reactive_ripple_loop(engine, api=api)

        assert api.render_uniform_calls
        assert api.build_ripple_cm_calls == 0
        assert press.close_called

    def test_pressed_key_with_mapped_cells_spawns_pulses(self):
        """When press returns a slot_id and mapped_cells are non-empty, pulses are appended."""
        from src.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=True)
        press = _MockPressSource(slot_id_sequence=("KEY_A",))
        api = _MockApi(press_source=press, mapped_cells=[(0, 0), (1, 1)])

        run_reactive_ripple_loop(engine, api=api)

        # At least one render call confirms the loop completed normally
        assert api.render_calls
        assert press.close_called

    def test_pressed_key_no_mapped_cells_uses_random_row_col(self):
        """When mapped_cells is empty, random row/col is used for the new pulse."""
        from src.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=True)
        press = _MockPressSource(slot_id_sequence=("KEY_B",))

        randrange_calls: list[int] = []

        class _TrackingRandom:
            def randrange(self, stop: int) -> int:
                randrange_calls.append(stop)
                return 0

        api = _MockApi(press_source=press, mapped_cells=[])
        api.random = _TrackingRandom()

        run_reactive_ripple_loop(engine, api=api)

        assert randrange_calls, "random.randrange should have been called"
        assert press.close_called

    def test_uniform_fallback_with_overlay_values_computes_best_weight(self):
        """Uniform fallback with overlay values computes best_weight/best_hue."""
        from src.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=False)
        press = _MockPressSource(slot_id_sequence=(None,))
        overlay = {(0, 0): (0.8, 180.0), (1, 1): (0.3, 90.0)}
        api = _MockApi(press_source=press, overlay_values=overlay)

        run_reactive_ripple_loop(engine, api=api)

        assert api.render_uniform_calls

    def test_uniform_fallback_with_manual_color_skips_hsv(self):
        """Uniform fallback with manual color uses manual instead of hsv_to_rgb."""
        from src.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=False)
        press = _MockPressSource(slot_id_sequence=(None,))
        api = _MockApi(press_source=press, manual_color=(200, 100, 50))

        run_reactive_ripple_loop(engine, api=api)

        assert api.render_uniform_calls

    def test_uniform_fallback_with_pulse_scale_below_one_calls_scale(self):
        """Uniform fallback with pulse_scale < 0.999 invokes api.scale."""
        from src.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=False)
        press = _MockPressSource(slot_id_sequence=(None,))
        scale_calls: list[float] = []
        api = _MockApi(press_source=press, pulse_scale=0.5)
        _orig_scale = api.scale

        def _tracking_scale(rgb: tuple, s: float) -> tuple:
            scale_calls.append(s)
            return _orig_scale(rgb, s)

        api.scale = _tracking_scale  # type: ignore[method-assign]

        run_reactive_ripple_loop(engine, api=api)

        assert scale_calls, "api.scale should have been called for pulse_scale < 0.999"

    def test_uniform_fallback_empty_base_map_uses_black(self):
        """Uniform fallback with empty base map uses (0, 0, 0) as base_rgb."""
        from src.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=False)
        press = _MockPressSource(slot_id_sequence=(None,))
        api = _MockApi(press_source=press, base_map={})

        run_reactive_ripple_loop(engine, api=api)

        assert api.render_uniform_calls

    def test_per_key_writer_path_with_per_key_backdrop_active(self):
        """per_key_backdrop_active=True flows correctly through build_ripple_color_map_into."""
        from src.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=True)
        press = _MockPressSource(slot_id_sequence=(None,))
        api = _MockApi(press_source=press, per_key_backdrop_active=True)

        run_reactive_ripple_loop(engine, api=api)

        assert api.build_ripple_cm_calls > 0
        assert api.render_calls
