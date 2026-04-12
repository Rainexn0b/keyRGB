from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, Tuple

from src.core.effects.matrix_layout import NUM_COLS, NUM_ROWS
from src.core.utils.logging_utils import log_throttled

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine

Color = Tuple[int, int, int]
Key = Tuple[int, int]

logger = logging.getLogger(__name__)

_PER_KEY_BACKDROP_ITERATION_LOG_KEY = "effects.reactive.per_key_backdrop.iteration_failed"
_PER_KEY_BACKDROP_ITERATION_LOG_INTERVAL_S = 30.0
_PER_KEY_BACKDROP_ITERATION_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)

_ALL_KEYS: tuple[Key, ...] = tuple((r, c) for r in range(NUM_ROWS) for c in range(NUM_COLS))


def get_engine_color_map_buffer(engine: "EffectsEngine", attr_name: str) -> Dict[Key, Color]:
    try:
        engine_state = object.__getattribute__(engine, "__dict__")
    except (AttributeError, TypeError):
        engine_state = None

    if isinstance(engine_state, dict):
        existing = engine_state.get(attr_name)
        if isinstance(existing, dict):
            return existing

        created: Dict[Key, Color] = {}
        engine_state[attr_name] = created
        return created

    created: Dict[Key, Color] = {}  # type: ignore[no-redef]
    try:
        setattr(engine, attr_name, created)
    except (AttributeError, TypeError):
        pass
    return created


def fill_uniform_color_map(dest: Dict[Key, Color], *, color: Color) -> Dict[Key, Color]:
    dest.clear()
    for key in _ALL_KEYS:
        dest[key] = color
    return dest


def fill_per_key_backdrop_map(
    dest: Dict[Key, Color],
    *,
    base_color: Color,
    per_key_colors: object,
) -> Dict[Key, Color]:
    fill_uniform_color_map(dest, color=base_color)

    items = getattr(per_key_colors, "items", None)
    if not callable(items):
        return dest

    try:
        for entry_key, rgb in items():
            try:
                row, col = entry_key
                rr, gg, bb = rgb
                dest[(int(row), int(col))] = (int(rr), int(gg), int(bb))
            except (TypeError, ValueError):
                continue
    except _PER_KEY_BACKDROP_ITERATION_ERRORS as exc:  # @quality-exception exception-transparency: reactive per-key backdrops may come from malformed runtime config objects and rendering must degrade to the uniform base color
        log_throttled(
            logger,
            _PER_KEY_BACKDROP_ITERATION_LOG_KEY,
            interval_s=_PER_KEY_BACKDROP_ITERATION_LOG_INTERVAL_S,
            level=logging.ERROR,
            msg="Failed to iterate reactive per-key backdrop colors",
            exc=exc,
        )
        return dest

    return dest


def scale_color_map_into(dest: Dict[Key, Color], *, source: Dict[Key, Color], factor: float) -> Dict[Key, Color]:
    f = float(factor)
    dest.clear()

    if f <= 0.0:
        for key in source.keys():
            dest[key] = (0, 0, 0)
        return dest

    for key, rgb in source.items():
        dest[key] = (
            int(round(rgb[0] * f)),
            int(round(rgb[1] * f)),
            int(round(rgb[2] * f)),
        )
    return dest


def build_frame_base_maps(
    engine: "EffectsEngine",
    *,
    background_rgb: Color,
    effect_brightness_hw: int,
    backdrop_brightness_scale_factor_fn,
) -> tuple[bool, Dict[Key, Color], Dict[Key, Color]]:
    base_unscaled = get_engine_color_map_buffer(engine, "_reactive_base_unscaled_map")
    per_key_backdrop_active = bool(getattr(engine, "per_key_colors", None) or None)
    if per_key_backdrop_active:
        base_color_src = getattr(engine, "current_color", None) or (255, 0, 0)
        base_color = (
            int(base_color_src[0]),
            int(base_color_src[1]),
            int(base_color_src[2]),
        )
        fill_per_key_backdrop_map(
            base_unscaled,
            base_color=base_color,
            per_key_colors=getattr(engine, "per_key_colors", None),
        )
        factor = backdrop_brightness_scale_factor_fn(engine, effect_brightness_hw=int(effect_brightness_hw))
        if factor >= 0.999:
            return True, base_unscaled, base_unscaled

        base = get_engine_color_map_buffer(engine, "_reactive_base_scaled_map")
        scale_color_map_into(base, source=base_unscaled, factor=factor)
        return True, base_unscaled, base

    fill_uniform_color_map(base_unscaled, color=background_rgb)
    return False, base_unscaled, base_unscaled
