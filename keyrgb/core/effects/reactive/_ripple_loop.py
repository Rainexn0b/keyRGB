from __future__ import annotations

# @quality-exception file-size-analysis: single reactive ripple render loop; size is the frame pipeline and pulse scheduling, not mixed ownership
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from operator import attrgetter
from typing import TYPE_CHECKING, Protocol

from keyrgb.core.backends.base import supports_per_key_output
from keyrgb.core.effects.matrix_layout import geometry_for_engine

from .input import EvdevKeyboardDevices
from .utils import frame_elapsed_dt_s, log_frame_overrun_if_slow, remaining_frame_delay_s

if TYPE_CHECKING:
    from keyrgb.core.effects.engine import EffectsEngine

logger = logging.getLogger(__name__)

Color = tuple[int, int, int]
Key = tuple[int, int]
ColorMap = dict[Key, Color]
SlotKeyMap = Mapping[str, Sequence[Key]]
RippleOverlay = dict[Key, tuple[float, float]]
_INT_COERCION_ERRORS = (TypeError, ValueError)

# Rainbow hue advance rate in degrees per second. Matches the historical
# 2.0 deg/frame at the nominal 60 fps frame_dt_s(), expressed per-second so
# the cycle speed no longer depends on the achieved frame rate.
_HUE_ADVANCE_DEG_PER_S: float = 120.0

# Base pulse lifetime at pace=1.0. The expanding ring crosses the deck from
# the pressed key to its farthest corner in this time (radius is normalized
# per pulse). 0.65s was tuned against frames that really ran ~1.6x slower
# than nominal; at true 60 fps it produced a barely perceptible ~38 keys/s
# wavefront. 1.32s lands the wave visibly at the far edge.
_BASE_PULSE_TTL_S: float = 1.32

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


class _RainbowPulseProtocol(Protocol):
    row: int
    col: int
    age_s: float
    ttl_s: float
    hue_offset: float


class _RainbowPulseFactoryProtocol(Protocol):
    def __call__(
        self,
        *,
        row: int,
        col: int,
        age_s: float,
        ttl_s: float,
        hue_offset: float,
    ) -> _RainbowPulseProtocol: ...


class _RandomProtocol(Protocol):
    def randrange(self, stop: int) -> int: ...


class _BackdropBrightnessScaleFactorProtocol(Protocol):
    def __call__(self, engine: EffectsEngine, *, effect_brightness_hw: int) -> float: ...


class _ReactiveRippleApiProtocol(Protocol):
    @property
    def _PressSource(self) -> _PressSourceFactoryProtocol: ...

    @property
    def _RainbowPulse(self) -> _RainbowPulseFactoryProtocol: ...

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

    def build_frame_base_maps(
        self,
        engine: EffectsEngine,
        *,
        background_rgb: Color,
        effect_brightness_hw: int,
        backdrop_brightness_scale_factor_fn: _BackdropBrightnessScaleFactorProtocol,
    ) -> tuple[bool, ColorMap, ColorMap]: ...

    def backdrop_brightness_scale_factor(self, engine: EffectsEngine, *, effect_brightness_hw: int) -> float: ...

    def _set_reactive_active_pulse_mix(self, engine: EffectsEngine, *, target: float) -> None: ...

    def mapped_slot_cells(self, slot_keymap: SlotKeyMap, pressed_slot_id: object) -> Sequence[Key]: ...

    def _age_pulses_in_place(
        self,
        pulses: list[_RainbowPulseProtocol],
        *,
        dt: float,
    ) -> list[_RainbowPulseProtocol]: ...

    def get_engine_overlay_buffer(self, engine: EffectsEngine, attr_name: str) -> RippleOverlay: ...

    def build_ripple_overlay_into(
        self,
        dest: RippleOverlay,
        pulses: list[_RainbowPulseProtocol],
        *,
        band: float,
        engine: EffectsEngine | None = None,
        geometry: object | None = None,
    ) -> RippleOverlay: ...

    def get_engine_manual_reactive_color(self, engine: EffectsEngine) -> Color | None: ...

    def pulse_brightness_scale_factor(self, engine: EffectsEngine) -> float: ...

    def reactive_auto_pulse_saturation(self, engine: EffectsEngine) -> float: ...

    def hsv_to_rgb(self, h: float, s: float, v: float) -> Color: ...

    def scale(self, rgb: Color, s: float) -> Color: ...

    def mix(self, a: Color, b: Color, t: float) -> Color: ...

    def _render_uniform_fallback(self, engine: EffectsEngine, *, rgb: Color) -> None: ...

    def get_engine_color_map_buffer(self, engine: EffectsEngine, attr_name: str) -> ColorMap: ...

    def build_ripple_color_map_into(
        self,
        dest: ColorMap,
        *,
        base: ColorMap,
        base_unscaled: ColorMap,
        overlay: RippleOverlay,
        per_key_backdrop_active: bool,
        manual: Color | None,
        pulse_scale: float,
        auto_pulse_saturation: float = 1.0,
    ) -> ColorMap: ...

    def render(self, engine: EffectsEngine, *, color_map: ColorMap) -> None: ...


def run_reactive_ripple_loop(engine: EffectsEngine, *, api: _ReactiveRippleApiProtocol) -> None:
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

    pulses: list[_RainbowPulseProtocol] = []
    global_hue = 0.0
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

            per_key_backdrop_active, base_unscaled, base = api.build_frame_base_maps(
                engine,
                background_rgb=(5, 5, 5),
                effect_brightness_hw=_engine_int_attr_or_default(engine, "brightness", missing_default=25),
                backdrop_brightness_scale_factor_fn=api.backdrop_brightness_scale_factor,
            )

            if eff_hw <= 0:
                api._set_reactive_active_pulse_mix(engine, target=0.0)
                api.render(engine, color_map=base)
                log_frame_overrun_if_slow(
                    logger=logger, frame_start_s=frame_start_s, nominal_dt_s=nominal_dt, effect_name="ripple"
                )
                engine.stop_event.wait(remaining_frame_delay_s(frame_start_s=frame_start_s, nominal_dt_s=nominal_dt))
                continue

            pressed_slot_ids = press.poll_slot_ids(dt=real_dt)
            if pressed_slot_ids:
                ttl = _BASE_PULSE_TTL_S / p
                for pressed_slot_id in pressed_slot_ids:
                    mapped_cells = api.mapped_slot_cells(slot_keymap, pressed_slot_id)
                    if mapped_cells:
                        for row, col in mapped_cells:
                            pulses.append(
                                api._RainbowPulse(
                                    row=int(row),
                                    col=int(col),
                                    age_s=0.0,
                                    ttl_s=ttl,
                                    hue_offset=global_hue,
                                )
                            )
                    else:
                        geometry = geometry_for_engine(engine)
                        row = api.random.randrange(int(geometry.rows))
                        col = api.random.randrange(int(geometry.cols))
                        pulses.append(api._RainbowPulse(row=row, col=col, age_s=0.0, ttl_s=ttl, hue_offset=global_hue))

            pulses = api._age_pulses_in_place(pulses, dt=real_dt)

            # Trail length scales the ring width (band), not TTL, so wave speed stays
            # constant and the user perceives a wider/narrower illuminated ring rather
            # than a faster/slower expanding wavefront.
            trail_pct = _engine_int_attr_or_fallback(
                engine, "reactive_trail_percent", missing_default=40, error_default=40
            )
            trail_scale = max(0.1, min(4.0, ((int(trail_pct) or 40) / 50.0) ** 2))
            band = 2.15 * trail_scale
            overlay = api.get_engine_overlay_buffer(engine, "_reactive_ripple_overlay")
            api.build_ripple_overlay_into(overlay, pulses, band=band, engine=engine)

            try:
                target_mix = max((float(weight) for (weight, _hue) in overlay.values()), default=0.0)
            except (TypeError, ValueError):
                target_mix = 0.0
            api._set_reactive_active_pulse_mix(engine, target=target_mix)

            manual = api.get_engine_manual_reactive_color(engine)
            pulse_scale = api.pulse_brightness_scale_factor(engine)
            auto_pulse_saturation = api.reactive_auto_pulse_saturation(engine)

            if not _has_per_key_writer(engine):
                best_weight = 0.0
                best_hue = 0.0
                for weight, hue in overlay.values():
                    if float(weight) > float(best_weight):
                        best_weight = float(weight)
                        best_hue = float(hue)

                if base:
                    red = sum(color[0] for color in base.values())
                    green = sum(color[1] for color in base.values())
                    blue = sum(color[2] for color in base.values())
                    count = max(1, len(base))
                    base_rgb = (int(red / count), int(green / count), int(blue / count))
                else:
                    base_rgb = (0, 0, 0)

                if manual is not None:
                    pulse_rgb = manual
                else:
                    pulse_rgb = api.hsv_to_rgb(best_hue / 360.0, auto_pulse_saturation, 1.0)

                # RGB scaling is safe here: hsv_to_rgb(h, 1.0, 1.0) always returns a
                # fully-bright colour, avoiding the black edge-case that requires
                # mix-weight scaling in the per-key contrast-highlight path.
                if pulse_scale < 0.999:
                    pulse_rgb = api.scale(pulse_rgb, pulse_scale)

                rgb = api.mix(base_rgb, pulse_rgb, t=min(1.0, best_weight))
                api._render_uniform_fallback(engine, rgb=rgb)
                # Advance hue at a fixed rate so the rainbow cycles consistently
                # regardless of typing speed (not pace-coupled). Time-based so the
                # cycle speed is independent of the achieved frame rate.
                global_hue = (global_hue + _HUE_ADVANCE_DEG_PER_S * real_dt) % 360.0
                log_frame_overrun_if_slow(
                    logger=logger, frame_start_s=frame_start_s, nominal_dt_s=nominal_dt, effect_name="ripple"
                )
                engine.stop_event.wait(remaining_frame_delay_s(frame_start_s=frame_start_s, nominal_dt_s=nominal_dt))
                continue

            color_map = api.get_engine_color_map_buffer(engine, "_reactive_ripple_frame_map")
            api.build_ripple_color_map_into(
                color_map,
                base=base,
                base_unscaled=base_unscaled,
                overlay=overlay,
                per_key_backdrop_active=per_key_backdrop_active,
                manual=manual,
                pulse_scale=pulse_scale,
                auto_pulse_saturation=auto_pulse_saturation,
            )

            api.render(engine, color_map=color_map)
            global_hue = (global_hue + _HUE_ADVANCE_DEG_PER_S * real_dt) % 360.0
            log_frame_overrun_if_slow(
                logger=logger, frame_start_s=frame_start_s, nominal_dt_s=nominal_dt, effect_name="ripple"
            )
            engine.stop_event.wait(remaining_frame_delay_s(frame_start_s=frame_start_s, nominal_dt_s=nominal_dt))
    finally:
        press.close()
