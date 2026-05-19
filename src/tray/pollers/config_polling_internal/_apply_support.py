from __future__ import annotations

from typing import SupportsIndex
from typing import SupportsInt
from typing import cast

from src.core.effects.device import Color
from src.core.effects.device import PerKeyColorMap
from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
from src.core.effects.software_targets import normalize_software_effect_target
from src.core.utils.safe_attrs import safe_int_attr


_INT_COERCION_EXCEPTIONS = (TypeError, ValueError, OverflowError)


def _coerce_int(value: object, *, default: int) -> int:
    candidate = default if not value else value
    try:
        return int(cast(str | bytes | bytearray | SupportsInt | SupportsIndex, candidate))
    except _INT_COERCION_EXCEPTIONS:
        return default


def current_software_effect_target(current: object) -> str:
    return normalize_software_effect_target(getattr(current, "software_effect_target", "keyboard"))


def has_all_uniform_capable_target(current: object) -> bool:
    return (
        str(getattr(current, "software_effect_target", "keyboard") or "keyboard")
        == SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
    )


def reactive_sync_values(current: object, config: object) -> tuple[int, int]:
    default_brightness = safe_int_attr(
        config,
        "reactive_brightness",
        default=safe_int_attr(config, "brightness", default=0),
    )
    reactive_brightness = getattr(current, "reactive_brightness", default_brightness)
    reactive_trail_percent = getattr(current, "reactive_trail_percent", None)
    if reactive_trail_percent is None:
        reactive_trail_percent = safe_int_attr(config, "reactive_trail_percent", default=40)

    return (
        _coerce_int(reactive_brightness, default=0),
        _coerce_int(reactive_trail_percent, default=40),
    )


def reactive_visual_mode_value(current: object, config: object) -> str:
    try:
        raw_value = getattr(current, "reactive_visual_mode", None)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        raw_value = None
    if raw_value is None:
        try:
            raw_value = getattr(config, "reactive_visual_mode", "subtle")
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            raw_value = "subtle"
    normalized = str(raw_value or "subtle").strip().lower()
    return normalized if normalized in {"subtle", "vivid"} else "subtle"


def build_perkey_color_map(
    config: object,
    *,
    ite_num_rows: int,
    ite_num_cols: int,
    base_color: Color,
) -> PerKeyColorMap:
    configured_map = cast(PerKeyColorMap | None, getattr(config, "per_key_colors", None))
    if configured_map is None:
        return {}

    if 0 < len(configured_map) < (ite_num_rows * ite_num_cols):
        color_map = dict(configured_map)
        for row in range(ite_num_rows):
            for col in range(ite_num_cols):
                color_map.setdefault((row, col), base_color)
        return color_map

    return configured_map
