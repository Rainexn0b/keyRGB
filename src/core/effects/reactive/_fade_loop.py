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
FadeOverlay = dict[Key, float]
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
    def __call__(self, engine: "EffectsEngine", *, effect_brightness_hw: int) -> float: ...


class _ReactiveFadeApiProtocol(Protocol):
    _PressSource: _PressSourceFactoryProtocol
    _Pulse: _PulseFactoryProtocol
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

    def get_engine_reactive_color(self, engine: "EffectsEngine") -> Color: ...

    def get_engine_manual_reactive_color(self, engine: "EffectsEngine") -> Color | None: ...

    def mapped_slot_cells(self, slot_keymap: SlotKeyMap, pressed_slot_id: object) -> Sequence[Key]: ...

    def _age_pulses_in_place(self, pulses: list[_PulseProtocol], *, dt: float) -> list[_PulseProtocol]: ...

    def get_engine_overlay_buffer(self, engine: "EffectsEngine", attr_name: str) -> FadeOverlay: ...

    def build_fade_overlay_into(self, dest: FadeOverlay, pulses: Sequence[_PulseProtocol]) -> FadeOverlay: ...

    def _set_reactive_active_pulse_mix(self, engine: "EffectsEngine", *, target: float) -> None: ...

    def build_frame_base_maps(
        self,
        engine: "EffectsEngine",
        *,
        background_rgb: Color,
        effect_brightness_hw: int,
        backdrop_brightness_scale_factor_fn: _BackdropBrightnessScaleFactorProtocol,
    ) -> tuple[bool, ColorMap, ColorMap]: ...

    def backdrop_brightness_scale_factor(self, engine: "EffectsEngine", *, effect_brightness_hw: int) -> float: ...

    def pulse_brightness_scale_factor(self, engine: "EffectsEngine") -> float: ...

    def scale(self, rgb: Color, s: float) -> Color: ...

    def _brightness_boost_pulse(self, *, base_rgb: Color) -> Color: ...

    def _pick_contrasting_highlight(self, *, base_rgb: Color, preferred_rgb: Color) -> Color: ...

    def mix(self, a: Color, b: Color, t: float) -> Color: ...

    def _render_uniform_fallback(self, engine: "EffectsEngine", *, rgb: Color) -> None: ...

    def get_engine_color_map_buffer(self, engine: "EffectsEngine", attr_name: str) -> ColorMap: ...

    def render(self, engine: "EffectsEngine", *, color_map: ColorMap) -> None: ...


def run_reactive_fade_loop(engine: "EffectsEngine", *, api: _ReactiveFadeApiProtocol) -> None:
    dt = api.frame_dt_s()

    press = api.create_press_source(
        engine,
        press_source_cls=api._PressSource,
        open_keyboards=api.try_open_evdev_keyboards,
        synthetic_fallback_enabled=api.reactive_synthetic_fallback_enabled,
    )
    slot_keymap = api.load_slot_keymap(loader=api.load_active_profile_slot_keymap)

    pulses: list[_PulseProtocol] = []
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

            react_color = api.get_engine_reactive_color(engine)
            manual = api.get_engine_manual_reactive_color(engine)

            pressed_slot_id = press.poll_slot_id(dt=dt)
            if pressed_slot_id is not None:
                mapped_cells = api.mapped_slot_cells(slot_keymap, pressed_slot_id)

                ttl = 0.48 / p
                if mapped_cells:
                    for row, col in mapped_cells:
                        pulses.append(api._Pulse(row=int(row), col=int(col), age_s=0.0, ttl_s=ttl))
                else:
                    row = api.random.randrange(api.NUM_ROWS)
                    col = api.random.randrange(api.NUM_COLS)
                    pulses.append(api._Pulse(row=row, col=col, age_s=0.0, ttl_s=ttl))

            pulses = api._age_pulses_in_place(pulses, dt=dt)

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
                engine.stop_event.wait(dt)
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
                engine.stop_event.wait(dt)
                continue

            color_map = api.get_engine_color_map_buffer(engine, "_reactive_fade_frame_map")
            color_map.clear()
            for key, base_rgb in base.items():
                base_rgb_unscaled = base_unscaled.get(key, base_rgb)
                weight = overlay.get(key, 0.0)
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

                color_map[key] = api.mix(base_rgb, pulse_rgb, t=min(1.0, weight))

            api.render(engine, color_map=color_map)
            engine.stop_event.wait(dt)
    finally:
        press.close()
