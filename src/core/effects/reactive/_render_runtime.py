from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Dict, Tuple

from src.core.effects.perkey_animation import enable_user_mode_once, per_key_mode_requires_frame_reassert
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

_RECOVERABLE_BRIGHTNESS_WRITE_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


def apply_hw_brightness(engine: "EffectsEngine", brightness_hw: int, *, force_reinit: bool = False) -> None:
    """Set hardware brightness, avoiding a full mode reinit when possible."""

    prev = getattr(engine, "_last_hw_mode_brightness", None)
    if force_reinit or prev is None:
        enable_user_mode_once(kb=engine.kb, kb_lock=engine.kb_lock, brightness=int(brightness_hw))
        engine._last_hw_mode_brightness = int(brightness_hw)
        return

    if int(prev) == int(brightness_hw):
        return

    try:
        engine.kb.set_brightness(int(brightness_hw))
    except _RECOVERABLE_BRIGHTNESS_WRITE_EXCEPTIONS as exc:
        log_throttled(
            logger,
            "effects.reactive.set_brightness_failed",
            interval_s=120,
            level=logging.DEBUG,
            msg="Reactive per-key brightness update failed; reinitializing user mode",
            exc=exc,
        )
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

            reassert_every_frame = per_key_mode_requires_frame_reassert(engine.kb)
            need_mode_init = reassert_every_frame or getattr(engine, "_last_hw_mode_brightness", None) is None
            if need_mode_init:
                apply_hw_brightness(engine, brightness_hw, force_reinit=reassert_every_frame)

            try:
                engine.kb.set_key_colors(color_map, brightness=int(brightness_hw), enable_user_mode=False)
            except Exception as exc:  # @quality-exception exception-transparency: reactive per-key writes cross backend-specific runtime I/O boundaries and disconnect handling must suppress further hardware writes
                if is_device_disconnected(exc):
                    try:
                        engine.mark_device_unavailable()
                    except Exception as mark_exc:  # @quality-exception exception-transparency: disconnect cleanup must stay best-effort and still suppress further reactive hardware writes even if invalidation fails
                        log_throttled(
                            logger,
                            "effects.reactive.mark_device_unavailable_failed",
                            interval_s=120,
                            level=logging.DEBUG,
                            msg="Failed to mark disconnected reactive device unavailable",
                            exc=mark_exc,
                        )
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
    except Exception as exc:  # @quality-exception exception-transparency: reactive per-key rendering crosses backend I/O and effect runtime policy boundaries and must degrade to uniform output instead of killing the effect loop
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
