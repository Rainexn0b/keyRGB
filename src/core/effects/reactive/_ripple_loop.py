from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from operator import attrgetter
from typing import TYPE_CHECKING, Protocol

from .input import EvdevKeyboardDevices

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine

Color = tuple[int, int, int]
Key = tuple[int, int]
ColorMap = dict[Key, Color]
SlotKeyMap = Mapping[str, Sequence[Key]]
RippleOverlay = dict[Key, tuple[float, float]]
_INT_COERCION_ERRORS = (TypeError, ValueError)


def _engine_int_attr_or_default(engine: "EffectsEngine", attr_name: str, *, missing_default: int) -> int:
    try:
        raw_value = attrgetter(attr_name)(engine)
    except AttributeError:
        raw_value = missing_default
    return int(raw_value or 0)


def _engine_int_attr_or_fallback(
    engine: "EffectsEngine",
    attr_name: str,
    *,
    missing_default: int,
    error_default: int,
) -> int:
    try:
        return _engine_int_attr_or_default(engine, attr_name, missing_default=missing_default)
    except _INT_COERCION_ERRORS:
        return error_default


def _has_per_key_writer(engine: "EffectsEngine") -> bool:
    kb = engine.kb
    try:
        set_key_colors = attrgetter("set_key_colors")(kb)
    except AttributeError:
        return False
    return bool(set_key_colors)


class _PressSourceProtocol(Protocol):
    spawn_interval_s: float

    def poll_slot_id(self, *, dt: float) -> str | None: ...

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
    def __call__(self, engine: "EffectsEngine", *, effect_brightness_hw: int) -> float: ...


class _ReactiveRippleApiProtocol(Protocol):
    _PressSource: _PressSourceFactoryProtocol
    _RainbowPulse: _RainbowPulseFactoryProtocol
    random: _RandomProtocol
    NUM_ROWS: int
    NUM_COLS: int

    def frame_dt_s(self) -> float: ...

    def create_press_source(
        self,
        engine: "EffectsEngine",
        *,
        press_source_cls: _PressSourceFactoryProtocol,
        open_keyboards: Callable[[], EvdevKeyboardDevices | None],
        synthetic_fallback_enabled: Callable[[], bool],
    ) -> _PressSourceProtocol: ...

    def try_open_evdev_keyboards(self) -> EvdevKeyboardDevices | None: ...

    def reactive_synthetic_fallback_enabled(self) -> bool: ...

    def load_slot_keymap(self, *, loader: Callable[[], SlotKeyMap]) -> SlotKeyMap: ...

    def load_active_profile_slot_keymap(self) -> SlotKeyMap: ...

    def pace(self, engine: "EffectsEngine", *, min_factor: float = 0.8, max_factor: float = 2.2) -> float: ...

    def build_frame_base_maps(
        self,
        engine: "EffectsEngine",
        *,
        background_rgb: Color,
        effect_brightness_hw: int,
        backdrop_brightness_scale_factor_fn: _BackdropBrightnessScaleFactorProtocol,
    ) -> tuple[bool, ColorMap, ColorMap]: ...

    def backdrop_brightness_scale_factor(self, engine: "EffectsEngine", *, effect_brightness_hw: int) -> float: ...

    def _set_reactive_active_pulse_mix(self, engine: "EffectsEngine", *, target: float) -> None: ...

    def mapped_slot_cells(self, slot_keymap: SlotKeyMap, pressed_slot_id: object) -> Sequence[Key]: ...

    def _age_pulses_in_place(
        self,
        pulses: list[_RainbowPulseProtocol],
        *,
        dt: float,
    ) -> list[_RainbowPulseProtocol]: ...

    def get_engine_overlay_buffer(self, engine: "EffectsEngine", attr_name: str) -> RippleOverlay: ...

    def build_ripple_overlay_into(
        self,
        dest: RippleOverlay,
        pulses: list[_RainbowPulseProtocol],
        *,
        band: float,
    ) -> RippleOverlay: ...

    def get_engine_manual_reactive_color(self, engine: "EffectsEngine") -> Color | None: ...

    def pulse_brightness_scale_factor(self, engine: "EffectsEngine") -> float: ...

    def hsv_to_rgb(self, h: float, s: float, v: float) -> Color: ...

    def scale(self, rgb: Color, s: float) -> Color: ...

    def mix(self, a: Color, b: Color, t: float) -> Color: ...

    def _render_uniform_fallback(self, engine: "EffectsEngine", *, rgb: Color) -> None: ...

    def get_engine_color_map_buffer(self, engine: "EffectsEngine", attr_name: str) -> ColorMap: ...

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
    ) -> ColorMap: ...

    def render(self, engine: "EffectsEngine", *, color_map: ColorMap) -> None: ...


def run_reactive_ripple_loop(engine: "EffectsEngine", *, api: _ReactiveRippleApiProtocol) -> None:
    dt = api.frame_dt_s()

    press = api.create_press_source(
        engine,
        press_source_cls=api._PressSource,
        open_keyboards=api.try_open_evdev_keyboards,
        synthetic_fallback_enabled=api.reactive_synthetic_fallback_enabled,
    )
    slot_keymap = api.load_slot_keymap(loader=api.load_active_profile_slot_keymap)

    pulses: list[_RainbowPulseProtocol] = []
    global_hue = 0.0

    try:
        while engine.running and not engine.stop_event.is_set():
            p = api.pace(engine)
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
                engine.stop_event.wait(dt)
                continue

            pressed_slot_id = press.poll_slot_id(dt=dt)
            if pressed_slot_id is not None:
                mapped_cells = api.mapped_slot_cells(slot_keymap, pressed_slot_id)

                ttl = 0.65 / p
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
                    row = api.random.randrange(api.NUM_ROWS)
                    col = api.random.randrange(api.NUM_COLS)
                    pulses.append(api._RainbowPulse(row=row, col=col, age_s=0.0, ttl_s=ttl, hue_offset=global_hue))

            pulses = api._age_pulses_in_place(pulses, dt=dt)

            # Trail length scales the ring width (band), not TTL, so wave speed stays
            # constant and the user perceives a wider/narrower illuminated ring rather
            # than a faster/slower expanding wavefront.
            trail_pct = _engine_int_attr_or_fallback(engine, "reactive_trail_percent", missing_default=50, error_default=50)
            trail_scale = max(0.1, min(4.0, ((int(trail_pct) or 50) / 50.0) ** 2))
            band = 2.15 * trail_scale
            overlay = api.get_engine_overlay_buffer(engine, "_reactive_ripple_overlay")
            api.build_ripple_overlay_into(overlay, pulses, band=band)

            try:
                target_mix = max((float(weight) for (weight, _hue) in overlay.values()), default=0.0)
            except (TypeError, ValueError):
                target_mix = 0.0
            api._set_reactive_active_pulse_mix(engine, target=target_mix)

            manual = api.get_engine_manual_reactive_color(engine)
            pulse_scale = api.pulse_brightness_scale_factor(engine)

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
                    pulse_rgb = api.hsv_to_rgb(best_hue / 360.0, 1.0, 1.0)

                # RGB scaling is safe here: hsv_to_rgb(h, 1.0, 1.0) always returns a
                # fully-bright colour, avoiding the black edge-case that requires
                # mix-weight scaling in the per-key contrast-highlight path.
                if pulse_scale < 0.999:
                    pulse_rgb = api.scale(pulse_rgb, pulse_scale)

                rgb = api.mix(base_rgb, pulse_rgb, t=min(1.0, best_weight))
                api._render_uniform_fallback(engine, rgb=rgb)
                # Advance hue at a fixed rate so the rainbow cycles consistently
                # regardless of typing speed (not pace-coupled).
                global_hue = (global_hue + 2.0) % 360.0
                engine.stop_event.wait(dt)
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
            )

            api.render(engine, color_map=color_map)
            global_hue = (global_hue + 2.0) % 360.0
            engine.stop_event.wait(dt)
    finally:
        press.close()
