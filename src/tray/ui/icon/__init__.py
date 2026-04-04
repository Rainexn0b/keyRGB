from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from src.core.effects.catalog import resolve_effect_name_for_backend
from src.core.effects.perkey_animation import build_full_color_grid
from src.core.resources.defaults import REFERENCE_MATRIX_COLS as NUM_COLS
from src.core.resources.defaults import REFERENCE_MATRIX_ROWS as NUM_ROWS

from src.tray.ui.icon._draw import create_icon, create_icon_mosaic, create_icon_rainbow
from src.tray.ui.icon._color import _per_key_color_mapping, representative_color


_ANIMATED_ICON_PHASE_RATE = 0.008
_ANIMATED_ICON_SCALE_FLOOR = 0.85
_CONFIG_READ_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_INT_COERCION_ERRORS = (TypeError, ValueError, OverflowError)


@dataclass(frozen=True)
class IconVisual:
    mode: Literal["solid", "rainbow", "mosaic"]
    color: tuple[int, int, int] | None = None
    # For rainbow mode we scale the gradient brightness (0..1).
    scale: float = 1.0
    # Phase shifts the gradient hue (0..1).
    phase: float = 0.0
    # For mosaic mode we store the per-key grid (row-major) and dimensions.
    colors_flat: tuple[tuple[int, int, int], ...] | None = None
    rows: int = 0
    cols: int = 0


def _icon_scale_from_brightness(brightness: int) -> float:
    # Mirror representative_color's icon-visibility scaling.
    icon_brightness = max(0, min(50, int(round(float(brightness) * 3.0))))
    return max(0.25, min(1.0, icon_brightness / 50.0))


def _animated_icon_scale_from_brightness(brightness: int) -> float:
    return max(_ANIMATED_ICON_SCALE_FLOOR, _icon_scale_from_brightness(brightness))


def _animated_icon_phase(now: float) -> float:
    return (float(now) * _ANIMATED_ICON_PHASE_RATE) % 1.0


def _config_value_or_default(config: Any, name: str, default: object) -> object:
    try:
        value = getattr(config, name, default)
    except _CONFIG_READ_ERRORS:
        return default
    return default if value is None else value


def _config_int_or_default(config: Any, name: str, default: int) -> int:
    value = _config_value_or_default(config, name, default)
    try:
        return int(value)  # type: ignore[call-overload]
    except _INT_COERCION_ERRORS:
        return default


def _normalized_rgb_or_none(value: object) -> tuple[int, int, int] | None:
    try:
        if not isinstance(value, (tuple, list)) or len(value) != 3:
            return None
        return (int(value[0]), int(value[1]), int(value[2]))
    except _INT_COERCION_ERRORS:
        return None


def _has_non_uniform_perkey_base(
    *,
    base_color: tuple[int, int, int],
    per_key_colors: Mapping[tuple[int, int], tuple[int, int, int]],
) -> bool:
    for color in per_key_colors.values():
        normalized = _normalized_rgb_or_none(color)
        if normalized is None or normalized != base_color:
            return True
    return False


def _is_non_uniform_effect(config: Any, *, backend: object | None = None) -> bool:
    effect = resolve_effect_name_for_backend(
        str(_config_value_or_default(config, "effect", "none") or "none"),
        backend,
    )

    if effect == "perkey":
        per_key = _per_key_color_mapping(config)
        if not per_key:
            return False

        base_color = _normalized_rgb_or_none(_config_value_or_default(config, "color", (255, 0, 128)) or (255, 0, 128))
        if base_color is None:
            return True
        return _has_non_uniform_perkey_base(base_color=base_color, per_key_colors=per_key)

    # Known multi-color / non-uniform effects.
    if effect in {
        "rainbow",
        "rainbow_wave",
        "rainbow_swirl",
        "spectrum_cycle",
        "color_cycle",
        "random",
        "aurora",
        "fireworks",
        "wave",
        "marquee",
    }:
        return True

    # Heuristic: effect names that imply cycling/multi-color.
    lowered = effect.lower()
    if "rainbow" in lowered or "cycle" in lowered or "spectrum" in lowered or "aurora" in lowered:
        return True

    return False


def _build_perkey_mosaic_visual(*, config: Any, brightness: int) -> IconVisual | None:
    """Build a mosaic visual from the configured base per-key map.

    Returns ``None`` if there is no usable non-uniform per-key base map.
    """

    per_key = _per_key_color_mapping(config)
    if not per_key:
        return None

    base_color = _normalized_rgb_or_none(_config_value_or_default(config, "color", (255, 0, 128)) or (255, 0, 128))
    if base_color is None:
        return None

    try:
        full = build_full_color_grid(
            base_color=base_color,
            per_key_colors=per_key,
            num_rows=NUM_ROWS,
            num_cols=NUM_COLS,
        )
        it = iter(full.values())
        first = next(it)
        for v in it:
            if v != first:
                colors_flat = tuple(full[(r, c)] for r in range(NUM_ROWS) for c in range(NUM_COLS))
                return IconVisual(
                    mode="mosaic",
                    scale=_icon_scale_from_brightness(brightness),
                    colors_flat=colors_flat,
                    rows=NUM_ROWS,
                    cols=NUM_COLS,
                )
    except _INT_COERCION_ERRORS:
        return None

    return None


def render_icon_visual(visual: IconVisual):
    """Render an ``IconVisual`` into a concrete tray icon image."""

    if visual.mode == "rainbow":
        return create_icon_rainbow(scale=visual.scale, phase=visual.phase)
    if visual.mode == "mosaic":
        return create_icon_mosaic(
            colors_flat=tuple(visual.colors_flat or ()),
            rows=int(visual.rows or 0),
            cols=int(visual.cols or 0),
            scale=visual.scale,
        )
    return create_icon(visual.color or (255, 0, 128))


def create_icon_for_state(*, config: Any, is_off: bool, now: float | None = None, backend: object | None = None):
    """Create the tray icon image for the current state."""

    return render_icon_visual(icon_visual(config=config, is_off=is_off, now=now, backend=backend))


def icon_visual(*, config: Any, is_off: bool, now: float | None = None, backend: object | None = None) -> IconVisual:
    """Describe how the tray icon should look for the current state."""

    if now is None:
        now = time.time()

    effect = resolve_effect_name_for_backend(str(_config_value_or_default(config, "effect", "none") or "none"), backend)
    is_reactive = effect.startswith("reactive_")
    base_brightness = _config_int_or_default(config, "brightness", 0)

    if (not is_off) and base_brightness != 0 and is_reactive:
        brightness = _config_int_or_default(
            config, "perkey_brightness", _config_int_or_default(config, "brightness", 25)
        )

        use_manual_reactive_color = bool(_config_value_or_default(config, "reactive_use_manual_color", False))
        if not use_manual_reactive_color:
            if effect == "reactive_ripple":
                return IconVisual(
                    mode="rainbow",
                    scale=_animated_icon_scale_from_brightness(brightness),
                    phase=_animated_icon_phase(float(now)),
                )

            # When the effect-specific reactive color override is disabled,
            # show the configured base lighting instead of a stale stored
            # reactive color.
            mosaic = _build_perkey_mosaic_visual(config=config, brightness=brightness)
            if mosaic is not None:
                return mosaic

        return IconVisual(
            mode="solid",
            color=representative_color(config=config, is_off=is_off, now=now, backend=backend),
        )

    if (not is_off) and base_brightness != 0 and _is_non_uniform_effect(config, backend=backend):
        brightness = _config_int_or_default(config, "brightness", 25)
        if effect == "perkey":
            brightness = _config_int_or_default(config, "perkey_brightness", brightness)

            mosaic = _build_perkey_mosaic_visual(config=config, brightness=brightness)
            if mosaic is not None:
                return mosaic
            return IconVisual(
                mode="solid",
                color=representative_color(config=config, is_off=is_off, now=now, backend=backend),
            )

        # Non-uniform non-perkey: use a rainbow K.
        return IconVisual(
            mode="rainbow",
            scale=_animated_icon_scale_from_brightness(brightness),
            phase=_animated_icon_phase(float(now)),
        )

    return IconVisual(mode="solid", color=representative_color(config=config, is_off=is_off, backend=backend))


__all__ = [
    "create_icon",
    "create_icon_for_state",
    "create_icon_mosaic",
    "create_icon_rainbow",
    "representative_color",
    "IconVisual",
    "icon_visual",
    "render_icon_visual",
]
