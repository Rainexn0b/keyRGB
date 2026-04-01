from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Dict, Tuple

from src.core.effects.perkey_animation import enable_user_mode_once
from src.core.effects.software_targets import average_color_map as average_color_map_impl
from src.core.effects.software_targets import render_secondary_uniform_rgb
from src.core.effects.transitions import avoid_full_black
from src.core.utils.exceptions import is_device_disconnected
from src.core.utils.logging_utils import log_throttled

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine

logger = logging.getLogger(__name__)

Color = Tuple[int, int, int]
Key = Tuple[int, int]


def apply_hw_brightness(engine: "EffectsEngine", brightness_hw: int) -> None:
    """Set hardware brightness, avoiding a full mode reinit when possible."""

    prev = getattr(engine, "_last_hw_mode_brightness", None)
    if prev is None:
        enable_user_mode_once(kb=engine.kb, kb_lock=engine.kb_lock, brightness=int(brightness_hw))
        engine._last_hw_mode_brightness = int(brightness_hw)
        return

    if int(prev) == int(brightness_hw):
        return

    try:
        engine.kb.set_brightness(int(brightness_hw))
    except Exception:
        enable_user_mode_once(kb=engine.kb, kb_lock=engine.kb_lock, brightness=int(brightness_hw))
    engine._last_hw_mode_brightness = int(brightness_hw)


def render_per_key_frame(
    engine: "EffectsEngine",
    *,
    color_map: Dict[Key, Color],
    resolve_brightness: Callable[["EffectsEngine"], tuple[int, int, int]],
    logger: logging.Logger,
) -> bool:
    try:
        brightness_hw = 0
        with engine.kb_lock:
            _, _, brightness_hw = resolve_brightness(engine)
            engine._last_rendered_brightness = brightness_hw

            need_mode_init = getattr(engine, "_last_hw_mode_brightness", None) is None
            if need_mode_init:
                apply_hw_brightness(engine, brightness_hw)

            try:
                engine.kb.set_key_colors(color_map, brightness=int(brightness_hw), enable_user_mode=False)
            except Exception as exc:
                if is_device_disconnected(exc):
                    try:
                        engine.mark_device_unavailable()
                    except Exception:
                        pass
                    return True
                raise

            if not need_mode_init:
                apply_hw_brightness(engine, brightness_hw)
        render_secondary_uniform_rgb(
            engine,
            rgb=average_color_map(color_map),
            brightness_hw=brightness_hw,
            logger=logger,
            log_key="effects.reactive.secondary",
        )
        return True
    except Exception as exc:
        log_throttled(
            logger,
            "effects.render.per_key_failed",
            interval_s=30,
            level=logging.WARNING,
            msg="Per-key render failed; falling back to uniform",
            exc=exc,
        )
        return False


def render_uniform_frame(
    engine: "EffectsEngine",
    *,
    color_map: Dict[Key, Color],
    resolve_brightness: Callable[["EffectsEngine"], tuple[int, int, int]],
) -> None:
    rgb = average_color_map(color_map)
    final_rgb = rgb
    brightness_hw = 0

    with engine.kb_lock:
        _, _, brightness_hw = resolve_brightness(engine)
        engine._last_rendered_brightness = brightness_hw
        r, g, b = avoid_full_black(rgb=rgb, target_rgb=rgb, brightness=int(brightness_hw))
        final_rgb = (r, g, b)

        need_mode_init = getattr(engine, "_last_hw_mode_brightness", None) is None
        if need_mode_init:
            apply_hw_brightness(engine, brightness_hw)

        engine.kb.set_color((r, g, b), brightness=int(brightness_hw))

        if not need_mode_init:
            apply_hw_brightness(engine, brightness_hw)
    render_secondary_uniform_rgb(
        engine,
        rgb=final_rgb,
        brightness_hw=brightness_hw,
        logger=logger,
        log_key="effects.reactive.secondary",
    )


def average_color_map(color_map: Dict[Key, Color]) -> Color:
    return average_color_map_impl(color_map)
