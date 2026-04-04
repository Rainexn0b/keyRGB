from __future__ import annotations

import colorsys
import logging
import math
import time
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from src.core.effects.catalog import resolve_effect_name_for_backend
from src.core.effects.perkey_animation import build_full_color_grid
from src.core.resources.defaults import REFERENCE_MATRIX_COLS as NUM_COLS
from src.core.resources.defaults import REFERENCE_MATRIX_ROWS as NUM_ROWS
from src.core.utils.logging_utils import log_throttled


logger = logging.getLogger(__name__)

_DEFAULT_COLOR = (255, 0, 128)
_OFF_COLOR = (64, 64, 64)


def _log_config_read_failure(name: str, exc: Exception) -> None:
    log_throttled(
        logger,
        f"tray_icon.config.{name}",
        interval_s=120,
        level=logging.DEBUG,
        msg=f"Failed to read tray icon config attribute '{name}'",
        exc=exc,
    )


def _config_value(config: Any, name: str, default: Any) -> Any:
    try:
        value = getattr(config, name, default)
    except AttributeError:
        return default
    except Exception as exc:  # @quality-exception exception-transparency: tray icon color reads cross legacy config/property boundaries and must remain best-effort
        _log_config_read_failure(name, exc)
        return default
    return default if value is None else value


def _int_or_default(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError, OverflowError):
        return default


def _config_int(config: Any, name: str, default: int) -> int:
    return _int_or_default(_config_value(config, name, default), default)


def _normalized_rgb_or_none(value: object) -> tuple[int, int, int] | None:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 3:
        return None
    try:
        return (int(value[0]), int(value[1]), int(value[2]))
    except (TypeError, ValueError, OverflowError):
        return None


def _config_color(
    config: Any,
    name: str,
    default: tuple[int, int, int] = _DEFAULT_COLOR,
) -> tuple[int, int, int]:
    value = _config_value(config, name, default)
    return _normalized_rgb_or_none(value) or default


def _config_optional_color(config: Any, name: str) -> tuple[int, int, int] | None:
    value = _config_value(config, name, None)
    if value is None:
        return None
    return _normalized_rgb_or_none(value)


def _normalized_color_values(colors: Iterable[object]) -> tuple[tuple[int, int, int], ...]:
    normalized: list[tuple[int, int, int]] = []
    for color in colors:
        rgb = _normalized_rgb_or_none(color)
        if rgb is not None:
            normalized.append(rgb)
    return tuple(normalized)


def _pace_from_speed(speed: int) -> float:
    # Mirror src.core.effects.software.base.pace(engine) mapping.
    s = max(0, min(10, int(speed)))
    t = float(s) / 10.0
    t = t * t
    return float(0.25 + (10.0 - 0.25) * t)


def _per_key_color_mapping(config: Any) -> Mapping[tuple[int, int], tuple[int, int, int]]:
    per_key = _config_value(config, "per_key_colors", {})
    return per_key if isinstance(per_key, Mapping) else {}


def _weighted_hsv_mean(colors: Iterable[tuple[int, int, int]]) -> tuple[int, int, int]:
    # Avoid muddy greys when averaging multi-color maps by averaging hue on the
    # unit circle and weighting by saturation/value.
    total = 0.0
    x = 0.0
    y = 0.0
    s_acc = 0.0
    v_acc = 0.0
    count = 0
    r_sum = 0
    g_sum = 0
    b_sum = 0

    for r, g, b in colors:
        count += 1
        r_sum += int(r)
        g_sum += int(g)
        b_sum += int(b)
        rr = max(0, min(255, int(r))) / 255.0
        gg = max(0, min(255, int(g))) / 255.0
        bb = max(0, min(255, int(b))) / 255.0
        h, s, v = colorsys.rgb_to_hsv(rr, gg, bb)
        if v <= 0.0:
            continue
        w = max(1e-6, s * v)
        ang = 2.0 * math.pi * h
        x += math.cos(ang) * w
        y += math.sin(ang) * w
        s_acc += s * w
        v_acc += v * w
        total += w

    if total <= 1e-6 or (x == 0.0 and y == 0.0):
        if count == 0:
            return _DEFAULT_COLOR
        r = int(round(r_sum / count))
        g = int(round(g_sum / count))
        b = int(round(b_sum / count))
        return (r, g, b)

    mean_h = (math.atan2(y, x) / (2.0 * math.pi)) % 1.0
    mean_s = max(0.0, min(1.0, s_acc / total))
    mean_v = max(0.0, min(1.0, v_acc / total))
    rr, gg, bb = colorsys.hsv_to_rgb(mean_h, mean_s, mean_v)
    return (int(rr * 255), int(gg * 255), int(bb * 255))


def _representative_perkey_color(config: Any) -> tuple[int, int, int] | None:
    per_key = _per_key_color_mapping(config)
    if not per_key:
        return None

    normalized_per_key = _normalized_color_values(per_key.values())
    if not normalized_per_key:
        return None

    base_color = _config_color(config, "color")
    try:
        full = build_full_color_grid(
            base_color=base_color,
            per_key_colors=per_key,
            num_rows=NUM_ROWS,
            num_cols=NUM_COLS,
        )
    except (TypeError, ValueError, OverflowError):
        return _weighted_hsv_mean(normalized_per_key)

    full_colors = _normalized_color_values(full.values())
    return _weighted_hsv_mean(full_colors or normalized_per_key)


def _representative_saved_perkey_color(config: Any) -> tuple[int, int, int] | None:
    per_key = _per_key_color_mapping(config)
    if not per_key:
        return None

    normalized_per_key = _normalized_color_values(per_key.values())
    return _weighted_hsv_mean(normalized_per_key) if normalized_per_key else None


def representative_color(
    *,
    config: Any,
    is_off: bool,
    now: float | None = None,
    backend: object | None = None,
) -> tuple[int, int, int]:
    """Pick an RGB color representative of the currently applied state."""

    if now is None:
        now = time.time()

    # Off state
    if is_off or _config_value(config, "brightness", 0) == 0:
        return _OFF_COLOR

    effect = resolve_effect_name_for_backend(
        str(_config_value(config, "effect", "none") or "none"),
        backend,
    )
    brightness = _config_int(config, "brightness", 25)

    # Reactive typing effects can store a separate manual effect color.
    # Respect the "use manual color" toggle; when disabled, the icon should
    # mirror the configured base color rather than a stale stored reactive
    # color override.
    is_reactive = effect.startswith("reactive_")
    # NOTE: For the tray icon we intentionally follow the profile/policy
    # brightness (config.brightness). Reactive pulse intensity is tracked
    # separately via config.reactive_brightness.

    # Per-key: average of configured colors
    if effect == "perkey":
        brightness = _config_int(config, "perkey_brightness", brightness)
        base = _representative_perkey_color(config) or _config_color(config, "color")

    # Multi-color effects: cycle a hue so the icon changes.
    elif effect in {"rainbow_wave", "rainbow_swirl", "spectrum_cycle", "color_cycle"}:
        speed = _config_int(config, "speed", 5)
        p = _pace_from_speed(speed)

        if effect == "rainbow_wave":
            hue = (now * (0.165 * p)) % 1.0
            col_den = float(max(1, NUM_COLS - 1))
            row_den = float(max(1, NUM_ROWS - 1))
            r = NUM_ROWS // 2
            c = NUM_COLS // 2
            position = (float(c) / col_den) + (0.18 * (float(r) / row_den))
            h = (hue + position) % 1.0
            rr, gg, bb = colorsys.hsv_to_rgb(h, 1.0, 1.0)
            base = (int(rr * 255), int(gg * 255), int(bb * 255))

        elif effect == "rainbow_swirl":
            hue = (now * (0.115 * p)) % 1.0
            cr = (NUM_ROWS - 1) / 2.0
            cc = (NUM_COLS - 1) / 2.0
            r = NUM_ROWS // 2
            c = NUM_COLS // 2
            dy = float(r) - cr
            dx = float(c) - cc
            ang = (math.atan2(dy, dx) / (2.0 * math.pi)) % 1.0
            rad = math.hypot(dx, dy)
            max_r = math.hypot(max(cc, NUM_COLS - 1 - cc), max(cr, NUM_ROWS - 1 - cr))
            max_r = max(1e-6, max_r)
            h = (hue + ang + 0.25 * (rad / max_r)) % 1.0
            rr, gg, bb = colorsys.hsv_to_rgb(h, 1.0, 1.0)
            base = (int(rr * 255), int(gg * 255), int(bb * 255))

        elif effect == "color_cycle":
            phase = now * (1.8 * p)
            rf = (math.sin(phase) + 1.0) / 2.0
            gf = (math.sin(phase + (2.0 * math.pi / 3.0)) + 1.0) / 2.0
            bf = (math.sin(phase + (4.0 * math.pi / 3.0)) + 1.0) / 2.0
            base = (int(round(rf * 255)), int(round(gf * 255)), int(round(bf * 255)))

        else:  # spectrum_cycle
            hue = (now * (0.22 * p)) % 1.0
            rr, gg, bb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            base = (int(rr * 255), int(gg * 255), int(bb * 255))

    elif effect in {"rainbow", "random", "aurora", "fireworks", "wave", "marquee"}:
        # Hardware and mixed effects: keep a cheap animated approximation.
        speed = _config_int(config, "speed", 5)
        p = _pace_from_speed(speed)
        hue = (now * (0.18 * p)) % 1.0
        rr, gg, bb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        base = (int(rr * 255), int(gg * 255), int(bb * 255))

    else:
        if is_reactive:
            use_manual_reactive_color = bool(_config_value(config, "reactive_use_manual_color", False))
            if use_manual_reactive_color:
                base = _config_optional_color(config, "reactive_color") or _config_color(config, "color")
            else:
                brightness = _config_int(config, "perkey_brightness", brightness)
                base = _representative_saved_perkey_color(config) or _config_color(config, "color")

            if base == (0, 0, 0):
                base = _DEFAULT_COLOR
        else:
            base = _config_color(config, "color")

    # Scale by brightness (0..50), but bias brighter than the keyboard so the
    # tray icon stays readable in dark mode at low keyboard brightness.
    #
    # Ratio: approximately 1:3 (keyboard:icon), clamped to [0.25, 1.0].
    icon_brightness = max(0, min(50, int(round(float(brightness) * 3.0))))
    scale = max(0.25, min(1.0, icon_brightness / 50.0))
    return (
        int(max(0, min(255, base[0] * scale))),
        int(max(0, min(255, base[1] * scale))),
        int(max(0, min(255, base[2] * scale))),
    )
