from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from operator import attrgetter
from typing import TYPE_CHECKING, Protocol

from src.core.backends.base import supports_per_key_output
from src.core.effects.matrix_layout import geometry_for_engine

from .input import EvdevKeyboardDevices
from .utils import frame_elapsed_dt_s, log_frame_overrun_if_slow, remaining_frame_delay_s

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine

logger = logging.getLogger(__name__)

Color = tuple[int, int, int]
Key = tuple[int, int]
ColorMap = dict[Key, Color]
SlotKeyMap = Mapping[str, Sequence[Key]]
FadeOverlay = dict[Key, float]
_INT_COERCION_ERRORS = (TypeError, ValueError)

# Base pulse lifetime at pace=1.0. Raised from 0.48s when the loop switched to
# real-dt aging: the old constant was tuned against frames that really ran
# ~1.6x slower than nominal, so 0.48s of true wall-clock life felt abrupt.
_BASE_PULSE_TTL_S: float = 0.75

# Reactive pace range. The shared quadratic pace mapping (0.25..10) made
# slider 3 feel like the perceptual middle; capping the max factor at 3.76
# rescales the curve so slider 5 delivers the old slider-3 pace (1.13x) and
# slider 10 tops out at the old slider-6 pace. Scoped to the reactive loops
# so other software effects keep the shared mapping.
_PACE_MIN_FACTOR: float = 0.25
_PACE_MAX_FACTOR: float = 3.76


def _engine_int_attr_or_default(engine: EffectsEngine, attr_name: str, *, missing_default: int) -> int:
    try:
        raw_value = attrgetter(attr_name)(engine)
    except AttributeError:
        raw_value = missing_default
    return int(raw_value or 0)


def _engine_int_attr_or_fallback(
    engine: EffectsEngine,
    attr_name: str,
    *,
    missing_default: int,
    error_default: int,
) -> int:
    try:
        return _engine_int_attr_or_default(engine, attr_name, missing_default=missing_default)
    except _INT_COERCION_ERRORS:
        return error_default


def _has_per_key_writer(engine: EffectsEngine) -> bool:
    return supports_per_key_output(getattr(engine, "backend_caps", None), getattr(engine, "kb", None))


class _PressSourceProtocol(Protocol):
    spawn_interval_s: float

    def poll_slot_ids(self, *, dt: float) -> list[str]: ...

    def close(self) -> None: ...


class _PressSourceFactoryProtocol(Protocol):
    def __call__(
        self,
        *,
        devices: EvdevKeyboardDevices,
        synthetic: bool,
        spawn_interval_s: float,
        allow_synthetic: bool,
    ) -> _PressSourceProtocol: ...


class _PulseProtocol(Protocol):
    row: int
    col: int
    age_s: float
    ttl_s: float


class _PulseFactoryProtocol(Protocol):
    def __call__(self, *, row: int, col: int, age_s: float, ttl_s: float) -> _PulseProtocol: ...


class _RandomProtocol(Protocol):
    def randrange(self, stop: int) -> int: ...


class _BackdropBrightnessScaleFactorProtocol(Protocol):
    def __call__(self, engine: EffectsEngine, *, effect_brightness_hw: int) -> float: ...


class _ReactiveFadeApiProtocol(Protocol):
    @property
    def _PressSource(self) -> _PressSourceFactoryProtocol: ...

    @property
    def _Pulse(self) -> _PulseFactoryProtocol: ...

    @property
    def random(self) -> _RandomProtocol: ...

    @property
    def NUM_ROWS(self) -> int: ...

    @property
    def NUM_COLS(self) -> int: ...

    def frame_dt_s(self) -> float: ...

    def create_press_source(
        self,
        engine: EffectsEngine,
        *,
        press_source_cls: _PressSourceFactoryProtocol,
        open_keyboards: Callable[[], EvdevKeyboardDevices | None],
        synthetic_fallback_enabled: Callable[[], bool],
    ) -> _PressSourceProtocol: ...

    def try_open_evdev_keyboards(self) -> EvdevKeyboardDevices | None: ...

    def reactive_synthetic_fallback_enabled(self) -> bool: ...

    def load_slot_keymap(self, *, loader: Callable[[], SlotKeyMap]) -> SlotKeyMap: ...

    def load_active_profile_slot_keymap(self) -> SlotKeyMap: ...

    def pace(self, engine: EffectsEngine, *, min_factor: float = 0.8, max_factor: float = 2.2) -> float: ...

    def get_engine_reactive_color(self, engine: EffectsEngine) -> Color: ...

    def get_engine_manual_reactive_color(self, engine: EffectsEngine) -> Color | None: ...

    def mapped_slot_cells(self, slot_keymap: SlotKeyMap, pressed_slot_id: object) -> Sequence[Key]: ...

    def _age_pulses_in_place(self, pulses: list[_PulseProtocol], *, dt: float) -> list[_PulseProtocol]: ...

    def get_engine_overlay_buffer(self, engine: EffectsEngine, attr_name: str) -> FadeOverlay: ...

    def build_fade_overlay_into(self, dest: FadeOverlay, pulses: Sequence[_PulseProtocol]) -> FadeOverlay: ...

    def _set_reactive_active_pulse_mix(self, engine: EffectsEngine, *, target: float) -> None: ...

    def build_frame_base_maps(
        self,
        engine: EffectsEngine,
        *,
        background_rgb: Color,
        effect_brightness_hw: int,
        backdrop_brightness_scale_factor_fn: _BackdropBrightnessScaleFactorProtocol,
    ) -> tuple[bool, ColorMap, ColorMap]: ...

    def backdrop_brightness_scale_factor(self, engine: EffectsEngine, *, effect_brightness_hw: int) -> float: ...

    def pulse_brightness_scale_factor(self, engine: EffectsEngine) -> float: ...

    def scale(self, rgb: Color, s: float) -> Color: ...

    def _brightness_boost_pulse(self, *, base_rgb: Color) -> Color: ...

    def _pick_contrasting_highlight(self, *, base_rgb: Color, preferred_rgb: Color) -> Color: ...

    def mix(self, a: Color, b: Color, t: float) -> Color: ...

    def _render_uniform_fallback(self, engine: EffectsEngine, *, rgb: Color) -> None: ...

    def get_engine_color_map_buffer(self, engine: EffectsEngine, attr_name: str) -> ColorMap: ...

    def render(self, engine: EffectsEngine, *, color_map: ColorMap) -> None: ...


def run_reactive_fade_loop(engine: EffectsEngine, *, api: _ReactiveFadeApiProtocol) -> None:
    nominal_dt = api.frame_dt_s()
    if engine.stop_event.is_set():
        return

    press = api.create_press_source(
        engine,
        press_source_cls=api._PressSource,
        open_keyboards=api.try_open_evdev_keyboards,
        synthetic_fallback_enabled=api.reactive_synthetic_fallback_enabled,
    )
    slot_keymap = api.load_slot_keymap(loader=api.load_active_profile_slot_keymap)

    pulses: list[_PulseProtocol] = []
    last_frame_s: float | None = None
    try:
        if engine.stop_event.is_set():
            return
        while engine.running and not engine.stop_event.is_set():
            # Age pulses by the real elapsed frame time (not the nominal dt) so
            # animation speed stays constant in wall-clock time; sleep only the
            # remaining frame budget so render work doesn't stretch the period.
            frame_start_s = time.monotonic()
            real_dt = frame_elapsed_dt_s(
                now_s=frame_start_s,
                last_frame_s=last_frame_s,
                nominal_dt_s=nominal_dt,
            )
            last_frame_s = frame_start_s

            p = api.pace(engine, min_factor=_PACE_MIN_FACTOR, max_factor=_PACE_MAX_FACTOR)
            press.spawn_interval_s = max(0.10, 0.45 / max(0.1, p))
            eff_hw = _engine_int_attr_or_fallback(
                engine,
                "reactive_brightness",
                missing_default=0,
                error_default=0,
            )

            react_color = api.get_engine_reactive_color(engine)
            manual = api.get_engine_manual_reactive_color(engine)

            pressed_slot_ids = press.poll_slot_ids(dt=real_dt)
            if pressed_slot_ids:
                trail_pct = _engine_int_attr_or_fallback(
                    engine, "reactive_trail_percent", missing_default=40, error_default=40
                )
                trail_scale = max(0.02, min(8.0, ((int(trail_pct) or 40) / 50.0) ** 2))
                ttl = (_BASE_PULSE_TTL_S / p) * trail_scale
                for pressed_slot_id in pressed_slot_ids:
                    mapped_cells = api.mapped_slot_cells(slot_keymap, pressed_slot_id)
                    if mapped_cells:
                        for row, col in mapped_cells:
                            pulses.append(api._Pulse(row=int(row), col=int(col), age_s=0.0, ttl_s=ttl))
                    else:
                        geometry = geometry_for_engine(engine)
                        row = api.random.randrange(int(geometry.rows))
                        col = api.random.randrange(int(geometry.cols))
                        pulses.append(api._Pulse(row=row, col=col, age_s=0.0, ttl_s=ttl))

            pulses = api._age_pulses_in_place(pulses, dt=real_dt)

            overlay = api.get_engine_overlay_buffer(engine, "_reactive_fade_overlay")
            api.build_fade_overlay_into(overlay, pulses)

            try:
                target_mix = max((float(value) for value in overlay.values()), default=0.0)
            except (TypeError, ValueError):
                target_mix = 0.0
            api._set_reactive_active_pulse_mix(engine, target=target_mix)

            per_key_backdrop_active, base_unscaled, base = api.build_frame_base_maps(
                engine,
                background_rgb=api.scale(react_color, 0.06),
                effect_brightness_hw=_engine_int_attr_or_default(engine, "brightness", missing_default=25),
                backdrop_brightness_scale_factor_fn=api.backdrop_brightness_scale_factor,
            )

            if eff_hw <= 0:
                api._set_reactive_active_pulse_mix(engine, target=0.0)
                api.render(engine, color_map=base)
                log_frame_overrun_if_slow(
                    logger=logger, frame_start_s=frame_start_s, nominal_dt_s=nominal_dt, effect_name="fade"
                )
                engine.stop_event.wait(remaining_frame_delay_s(frame_start_s=frame_start_s, nominal_dt_s=nominal_dt))
                continue

            pulse_scale = api.pulse_brightness_scale_factor(engine)

            if not _has_per_key_writer(engine):
                w_global = 0.0
                if overlay:
                    try:
                        w_global = max(float(value) for value in overlay.values())
                    except (TypeError, ValueError):
                        w_global = 0.0

                try:
                    base_rgb = next(iter(base.values()))
                except StopIteration:
                    base_rgb = (0, 0, 0)
                try:
                    base_rgb_unscaled = next(iter(base_unscaled.values()))
                except StopIteration:
                    base_rgb_unscaled = base_rgb

                if manual is not None:
                    pulse_rgb = react_color
                elif per_key_backdrop_active:
                    pulse_rgb = api._brightness_boost_pulse(base_rgb=base_rgb_unscaled)
                else:
                    pulse_rgb = api._pick_contrasting_highlight(
                        base_rgb=base_rgb_unscaled,
                        preferred_rgb=react_color,
                    )

                if pulse_scale < 0.999:
                    pulse_rgb = api.scale(pulse_rgb, pulse_scale)

                rgb = api.mix(base_rgb, pulse_rgb, t=min(1.0, w_global))
                api._render_uniform_fallback(engine, rgb=rgb)
                log_frame_overrun_if_slow(
                    logger=logger, frame_start_s=frame_start_s, nominal_dt_s=nominal_dt, effect_name="fade"
                )
                engine.stop_event.wait(remaining_frame_delay_s(frame_start_s=frame_start_s, nominal_dt_s=nominal_dt))
                continue

            color_map = api.get_engine_color_map_buffer(engine, "_reactive_fade_frame_map")
            color_map.clear()
            for key, base_rgb in base.items():
                base_rgb_unscaled = base_unscaled.get(key, base_rgb)
                weight = overlay.get(key, 0.0)
                if manual is not None:
                    pulse_rgb = react_color
                    if pulse_scale < 0.999:
                        pulse_rgb = api.scale(pulse_rgb, pulse_scale)
                    color_map[key] = api.mix(base_rgb, pulse_rgb, t=min(1.0, weight))
                elif per_key_backdrop_active:
                    # Apply pulse_scale to the mix weight so the brightness slider
                    # remains effective regardless of the auto-contrast highlight color.
                    pulse_rgb = api._brightness_boost_pulse(base_rgb=base_rgb_unscaled)
                    color_map[key] = api.mix(base_rgb, pulse_rgb, t=min(1.0, weight * pulse_scale))
                else:
                    pulse_rgb = api._pick_contrasting_highlight(
                        base_rgb=base_rgb_unscaled,
                        preferred_rgb=react_color,
                    )
                    if pulse_scale < 0.999:
                        pulse_rgb = api.scale(pulse_rgb, pulse_scale)
                    color_map[key] = api.mix(base_rgb, pulse_rgb, t=min(1.0, weight))

            api.render(engine, color_map=color_map)
            log_frame_overrun_if_slow(
                logger=logger, frame_start_s=frame_start_s, nominal_dt_s=nominal_dt, effect_name="fade"
            )
            engine.stop_event.wait(remaining_frame_delay_s(frame_start_s=frame_start_s, nominal_dt_s=nominal_dt))
    finally:
        press.close()
