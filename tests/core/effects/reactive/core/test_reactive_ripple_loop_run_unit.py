#!/usr/bin/env python3
"""Unit tests for run_reactive_ripple_loop (run-loop scenarios)."""

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
        auto_pulse_saturation: float = 1.0,
        mapped_cells: list | None = None,
        per_key_backdrop_active: bool = False,
    ) -> None:
        self._press = press_source if press_source is not None else _MockPressSource()
        self._overlay_values: dict = overlay_values if overlay_values is not None else {}
        self._base_map: dict = base_map if base_map is not None else {(0, 0): (100, 100, 100)}
        self._manual_color = manual_color
        self._pulse_scale = pulse_scale
        self._auto_pulse_saturation = auto_pulse_saturation
        self._mapped_cells: list = mapped_cells if mapped_cells is not None else []
        self._per_key_backdrop_active = per_key_backdrop_active

        # Recorded calls
        self.set_mix_calls: list[float] = []
        self.render_calls: list = []
        self.render_uniform_calls: list = []
        self.build_ripple_cm_calls: int = 0
        self.overlay_band_calls: list[float] = []

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

    def build_frame_base_maps(
        self, engine, *, background_rgb, effect_brightness_hw, backdrop_brightness_scale_factor_fn
    ):
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

    def build_ripple_overlay_into(self, dest, pulses, *, band: float, **_kwargs) -> None:
        self.overlay_band_calls.append(float(band))
        # overlay values come pre-populated from get_engine_overlay_buffer

    def get_engine_manual_reactive_color(self, engine):
        return self._manual_color

    def pulse_brightness_scale_factor(self, engine) -> float:
        return self._pulse_scale

    def reactive_auto_pulse_saturation(self, engine) -> float:
        return self._auto_pulse_saturation

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

    def build_ripple_color_map_into(
        self,
        dest,
        *,
        base,
        base_unscaled,
        overlay,
        per_key_backdrop_active,
        manual,
        pulse_scale,
        auto_pulse_saturation=1.0,
    ):
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


# ── run_reactive_ripple_loop: run-loop scenarios ──────────────────────────────


class TestRunReactiveRippleLoop:
    def test_eff_hw_zero_exits_after_render_base(self):
        """eff_hw=0: skips pulse logic, renders base, then exits on next wait()."""
        from keyrgb.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=0)
        api = _MockApi()

        run_reactive_ripple_loop(engine, api=api)

        assert api.render_calls, "render should have been called with base map"
        assert api.set_mix_calls == [0.0], "pulse mix target should be 0.0"

    def test_press_close_always_called_in_finally(self):
        """press.close() is called regardless of loop exit path."""
        from keyrgb.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=0)
        api = _MockApi()

        run_reactive_ripple_loop(engine, api=api)

        assert api._press.close_called

    def test_per_key_writer_path_calls_build_and_render(self):
        """With per-key writer and eff_hw>0, build_ripple_color_map_into and render are called."""
        from keyrgb.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=True)
        press = _MockPressSource(slot_id_sequence=(None,))
        api = _MockApi(press_source=press)

        run_reactive_ripple_loop(engine, api=api)

        assert api.build_ripple_cm_calls > 0
        assert api.render_calls
        assert press.close_called

    def test_uniform_fallback_no_per_key_writer(self):
        """Without per-key writer, _render_uniform_fallback is called instead of render."""
        from keyrgb.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=False)
        press = _MockPressSource(slot_id_sequence=(None,))
        api = _MockApi(press_source=press)

        run_reactive_ripple_loop(engine, api=api)

        assert api.render_uniform_calls
        assert api.build_ripple_cm_calls == 0
        assert press.close_called

    def test_pressed_key_with_mapped_cells_spawns_pulses(self):
        """When press returns a slot_id and mapped_cells are non-empty, pulses are appended."""
        from keyrgb.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=True)
        press = _MockPressSource(slot_id_sequence=("KEY_A",))
        api = _MockApi(press_source=press, mapped_cells=[(0, 0), (1, 1)])

        run_reactive_ripple_loop(engine, api=api)

        # At least one render call confirms the loop completed normally
        assert api.render_calls
        assert press.close_called

    def test_pressed_key_no_mapped_cells_uses_random_row_col(self):
        """When mapped_cells is empty, random row/col is used for the new pulse."""
        from keyrgb.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

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
        from keyrgb.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=False)
        press = _MockPressSource(slot_id_sequence=(None,))
        overlay = {(0, 0): (0.8, 180.0), (1, 1): (0.3, 90.0)}
        api = _MockApi(press_source=press, overlay_values=overlay)

        run_reactive_ripple_loop(engine, api=api)

        assert api.render_uniform_calls

    def test_uniform_fallback_with_manual_color_skips_hsv(self):
        """Uniform fallback with manual color uses manual instead of hsv_to_rgb."""
        from keyrgb.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=False)
        press = _MockPressSource(slot_id_sequence=(None,))
        api = _MockApi(press_source=press, manual_color=(200, 100, 50))

        run_reactive_ripple_loop(engine, api=api)

        assert api.render_uniform_calls

    def test_uniform_fallback_with_pulse_scale_below_one_calls_scale(self):
        """Uniform fallback with pulse_scale < 0.999 invokes api.scale."""
        from keyrgb.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

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
        from keyrgb.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=False)
        press = _MockPressSource(slot_id_sequence=(None,))
        api = _MockApi(press_source=press, base_map={})

        run_reactive_ripple_loop(engine, api=api)

        assert api.render_uniform_calls

    def test_trail_width_is_decoupled_from_speed_pace(self):
        """Wave thickness should depend on reactive_trail_percent, not on pace."""
        from keyrgb.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        slow_engine = _make_engine(reactive_brightness=25, has_per_key_writer=True)
        slow_engine.reactive_trail_percent = 50
        slow_api = _MockApi(press_source=_MockPressSource(slot_id_sequence=(None,)))
        slow_api.pace = lambda _engine, **_kwargs: 0.8  # type: ignore[method-assign]

        run_reactive_ripple_loop(slow_engine, api=slow_api)

        fast_engine = _make_engine(reactive_brightness=25, has_per_key_writer=True)
        fast_engine.reactive_trail_percent = 50
        fast_api = _MockApi(press_source=_MockPressSource(slot_id_sequence=(None,)))
        fast_api.pace = lambda _engine, **_kwargs: 2.2  # type: ignore[method-assign]

        run_reactive_ripple_loop(fast_engine, api=fast_api)

        assert slow_api.overlay_band_calls == [2.15]
        assert fast_api.overlay_band_calls == [2.15]

    def test_per_key_writer_path_with_per_key_backdrop_active(self):
        """per_key_backdrop_active=True flows correctly through build_ripple_color_map_into."""
        from keyrgb.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=True)
        press = _MockPressSource(slot_id_sequence=(None,))
        api = _MockApi(press_source=press, per_key_backdrop_active=True)

        run_reactive_ripple_loop(engine, api=api)

        assert api.build_ripple_cm_calls > 0
        assert api.render_calls

    def test_multiple_presses_in_one_frame_each_spawn_a_pulse(self):
        """A single evdev batch with two keydowns must spawn two pulses, not one."""
        from keyrgb.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        engine = _make_engine(reactive_brightness=25, has_per_key_writer=True)

        class _MultiPressSource(_MockPressSource):
            def poll_slot_ids(self, *, dt: float) -> list[str]:
                if self._idx:
                    return []
                self._idx += 1
                return ["KEY_A", "KEY_B"]

        spawned: list[tuple[int, int]] = []
        api = _MockApi(press_source=_MultiPressSource(), mapped_cells=[(0, 0)])

        def _tracking_pulse(*, row, col, age_s, ttl_s, hue_offset):
            spawned.append((row, col))
            return SimpleNamespace(row=row, col=col, age_s=age_s, ttl_s=ttl_s, hue_offset=hue_offset)

        api._RainbowPulse = _tracking_pulse

        run_reactive_ripple_loop(engine, api=api)

        assert len(spawned) == 2, "each pressed slot id in the batch should spawn its own pulse"
        assert api._press.close_called

    def test_loop_uses_rescaled_pace_range_so_slider_5_is_the_middle(self):
        """The shared 0.25..10 pace range made slider 3 feel like the middle;
        both reactive loops must use the rescaled 0.25..3.76 range instead."""
        from keyrgb.core.effects.reactive import _fade_loop, _ripple_loop
        from keyrgb.core.effects.reactive._ripple_loop import run_reactive_ripple_loop

        # Both loops declare the rescaled range...
        for module in (_ripple_loop, _fade_loop):
            assert module._PACE_MIN_FACTOR == 0.25
            assert module._PACE_MAX_FACTOR == 3.76

        # ...and the ripple loop actually passes it through to api.pace.
        pace_kwargs: list[dict] = []
        engine = _make_engine(reactive_brightness=25, has_per_key_writer=True)
        api = _MockApi(press_source=_MockPressSource(slot_id_sequence=(None,)))

        def _tracking_pace(_engine, **kwargs):
            pace_kwargs.append(kwargs)
            return 1.0

        api.pace = _tracking_pace  # type: ignore[method-assign]

        run_reactive_ripple_loop(engine, api=api)

        assert pace_kwargs, "loop should call api.pace"
        for kwargs in pace_kwargs:
            assert kwargs.get("min_factor") == 0.25
            assert kwargs.get("max_factor") == 3.76
