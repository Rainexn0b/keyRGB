from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Dict, Tuple

from src.core.effects.matrix_layout import NUM_COLS, NUM_ROWS
from src.core.effects.software_targets import average_color_map, render_secondary_uniform_rgb
from src.core.effects.perkey_animation import (
    build_full_color_grid,
    enable_user_mode_once,
    per_key_mode_requires_frame_reassert,
)
from src.core.effects.transitions import avoid_full_black
from src.core.utils.logging_utils import log_throttled
from src.core.utils.exceptions import is_device_disconnected

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine

Color = Tuple[int, int, int]
Key = Tuple[int, int]


def clamp01(x: float) -> float:
    return 0.0 if x <= 0.0 else (1.0 if x >= 1.0 else x)


def pace(engine: "EffectsEngine", *, min_factor: float = 0.8, max_factor: float = 2.2) -> float:
    """Map UI speed (0..10) to an effect pace multiplier.

    Uses a quadratic curve so the top end (speed=10) is significantly faster.
    """

    try:
        speed_raw = getattr(engine, "speed")
    except AttributeError:
        speed_raw = 4

    if speed_raw is None:
        s = 0
    else:
        try:
            s = int(speed_raw)
        except (TypeError, ValueError, OverflowError):
            s = 4

    s = max(0, min(10, s))
    t = float(s) / 10.0
    t = t * t

    min_factor = float(min_factor)
    max_factor = float(max_factor)
    if min_factor == 0.8 and max_factor == 2.2:
        min_factor = 0.25
        max_factor = 10.0

    return float(min_factor + (max_factor - min_factor) * t)


def frame_dt_s() -> float:
    return 1.0 / 60.0


def animation_step_s(
    engine: "EffectsEngine",
    attr_name: str,
    *,
    nominal_s: float | None = None,
    max_step_multiple: float = 1.25,
    now_s: float | None = None,
) -> float:
    step_s = frame_dt_s() if nominal_s is None else max(1e-6, float(nominal_s))
    max_step_s = step_s * max(1.0, float(max_step_multiple))
    current_s = time.monotonic() if now_s is None else float(now_s)

    try:
        previous_raw = getattr(engine, attr_name)
    except AttributeError:
        previous_s = None
    else:
        try:
            previous_s = float(previous_raw)
        except (TypeError, ValueError, OverflowError):
            previous_s = None

    try:
        setattr(engine, attr_name, current_s)
    except (AttributeError, TypeError, ValueError):
        pass

    if previous_s is None:
        return step_s

    elapsed_s = current_s - previous_s
    if elapsed_s <= 0.0:
        return step_s
    return min(max_step_s, elapsed_s)


def has_per_key(engine: "EffectsEngine") -> bool:
    return bool(getattr(engine.kb, "set_key_colors", None))


def base_color_map(engine: "EffectsEngine") -> Dict[Key, Color]:
    base_color_src = getattr(engine, "current_color", None) or (255, 0, 0)
    base_color = (
        int(base_color_src[0]),
        int(base_color_src[1]),
        int(base_color_src[2]),
    )

    per_key = getattr(engine, "per_key_colors", None) or None
    if not per_key:
        return {(r, c): base_color for r in range(NUM_ROWS) for c in range(NUM_COLS)}

    full = build_full_color_grid(
        base_color=base_color,
        per_key_colors=per_key,
        num_rows=NUM_ROWS,
        num_cols=NUM_COLS,
    )

    out: Dict[Key, Color] = {}
    for (r, c), rgb in full.items():
        out[(r, c)] = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
    return out


def mix(a: Color, b: Color, t: float) -> Color:
    tt = clamp01(t)
    return (
        int(round(a[0] + (b[0] - a[0]) * tt)),
        int(round(a[1] + (b[1] - a[1]) * tt)),
        int(round(a[2] + (b[2] - a[2]) * tt)),
    )


def scale(rgb: Color, s: float) -> Color:
    ss = clamp01(s)
    return (int(round(rgb[0] * ss)), int(round(rgb[1] * ss)), int(round(rgb[2] * ss)))


def render(engine: "EffectsEngine", *, color_map: Dict[Key, Color]) -> None:
    """Render per-key when available, otherwise fall back to uniform."""

    if has_per_key(engine):
        try:
            with engine.kb_lock:
                brightness_hw = int(engine.brightness)
                reassert_every_frame = per_key_mode_requires_frame_reassert(engine.kb)
                last_hw_brightness = getattr(engine, "_last_hw_mode_brightness", None)
                need_mode_init = reassert_every_frame or last_hw_brightness is None

                if need_mode_init:
                    enable_user_mode_once(
                        kb=engine.kb,
                        kb_lock=engine.kb_lock,
                        brightness=brightness_hw,
                    )
                    engine._last_hw_mode_brightness = brightness_hw

                try:
                    engine.kb.set_key_colors(
                        color_map,
                        brightness=brightness_hw,
                        enable_user_mode=False,
                    )
                except Exception as exc:  # @quality-exception exception-transparency: disconnect detection spans backend-specific runtime I/O failures and must avoid unsafe uniform fallback writes on device disappearance
                    # On USB disconnect, attempting a fallback uniform write can trigger
                    # a libusb crash on some systems. Mark the device unavailable and
                    # stop issuing I/O until the engine re-acquires it.
                    if is_device_disconnected(exc):
                        try:
                            engine.mark_device_unavailable()
                        except Exception as mark_exc:  # @quality-exception exception-transparency: disconnect cleanup must stay best-effort and still suppress further hardware writes even if device invalidation fails
                            log_throttled(
                                logger,
                                "effects.render.mark_device_unavailable_failed",
                                interval_s=120,
                                level=logging.DEBUG,
                                msg="Failed to mark disconnected device unavailable",
                                exc=mark_exc,
                            )
                        return
                    raise

                if not need_mode_init and int(last_hw_brightness) != brightness_hw:  # type: ignore[arg-type]
                    try:
                        engine.kb.set_brightness(int(brightness_hw))
                    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
                        enable_user_mode_once(
                            kb=engine.kb,
                            kb_lock=engine.kb_lock,
                            brightness=brightness_hw,
                        )
                    engine._last_hw_mode_brightness = brightness_hw

                render_secondary_uniform_rgb(
                    engine,
                    rgb=average_color_map(color_map),
                    brightness_hw=brightness_hw,
                    logger=logger,
                    log_key="effects.render.secondary",
                )
                return
        except Exception as exc:  # @quality-exception exception-transparency: per-key rendering crosses backend I/O and effect runtime policy boundaries and must degrade to uniform output instead of killing the effect loop
            log_throttled(
                logger,
                "effects.render.per_key_failed",
                interval_s=30,
                level=logging.WARNING,
                msg="Per-key render failed; falling back to uniform",
                exc=exc,
            )

    if not color_map:
        rgb = (0, 0, 0)
    else:
        rgb = average_color_map(color_map)

    r, g, b = avoid_full_black(rgb=rgb, target_rgb=rgb, brightness=int(engine.brightness))
    with engine.kb_lock:
        enable_user_mode_once(kb=engine.kb, kb_lock=engine.kb_lock, brightness=int(engine.brightness))
        engine.kb.set_color((r, g, b), brightness=int(engine.brightness))
    render_secondary_uniform_rgb(
        engine,
        rgb=(r, g, b),
        brightness_hw=int(engine.brightness),
        logger=logger,
        log_key="effects.render.secondary",
    )
