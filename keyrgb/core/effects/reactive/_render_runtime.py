from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from keyrgb.core.backends.policies.per_key_mode import per_key_mode_requires_frame_reassert
from keyrgb.core.effects.perkey_animation import enable_user_mode_once
from keyrgb.core.effects.software_targets import (
    average_color_map as average_color_map_impl,
    render_secondary_uniform_rgb,
)
from keyrgb.core.effects.transitions import avoid_full_black
from keyrgb.core.utils.exceptions import is_device_disconnected
from keyrgb.core.utils.logging_utils import log_throttled

from ._render_brightness_debug import log_render_visual_scale_change

if TYPE_CHECKING:
    from keyrgb.core.effects.engine import EffectsEngine

logger = logging.getLogger(__name__)

Color = tuple[int, int, int]
Key = tuple[int, int]
FrameSignature = tuple[int, tuple[tuple[int, int, int, int, int], ...]]

_RECOVERABLE_BRIGHTNESS_WRITE_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_REACTIVE_RENDER_RUNTIME_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_REACTIVE_RENDER_CLEANUP_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _reactive_hardware_writes_allowed(engine: EffectsEngine) -> bool:
    """Skip in-flight frames once the engine is stopping or mode-off.

    Controller-sleep honor stops the effect after a firmware zero. A frame
    already past the loop check can still acquire ``kb_lock`` and write a
    brightness-guard ramp (0→8) into the sleeping controller. Treat an
    explicit ``running is False`` or ``_device_mode_off`` latch as a hard
    stop on hardware commits. Engines that omit those attrs still write.
    """

    if getattr(engine, "running", True) is False:
        return False
    try:
        return engine._device_mode_off is not True
    except AttributeError:
        return True


def _last_hw_mode_brightness_or_none(engine: EffectsEngine) -> int | None:
    try:
        return engine._last_hw_mode_brightness
    except AttributeError:
        return None


def _last_reactive_per_key_frame_signature_or_none(engine: EffectsEngine) -> object | None:
    try:
        return engine._last_reactive_per_key_frame_signature
    except AttributeError:
        return None


def _per_key_frame_signature(color_map: Mapping[Key, Color], *, brightness_hw: int) -> FrameSignature:
    entries: list[tuple[int, int, int, int, int]] = []
    for (row, col), (red, green, blue) in color_map.items():
        entries.append((int(row), int(col), int(red), int(green), int(blue)))
    return (int(brightness_hw), tuple(sorted(entries)))


def apply_hw_brightness(engine: EffectsEngine, brightness_hw: int, *, force_reinit: bool = False) -> None:
    """Set hardware brightness, avoiding a full mode reinit when possible."""

    prev = _last_hw_mode_brightness_or_none(engine)
    if force_reinit or prev is None:
        enable_user_mode_once(
            kb=engine.kb,
            kb_lock=engine.kb_lock,
            brightness=int(brightness_hw),
            save=prev is None,
        )
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
    engine: EffectsEngine,
    *,
    color_map: Mapping[Key, Color],
    resolve_brightness: Callable[[EffectsEngine], tuple[int, int, int]],
    resolve_transition_visual_scale: Callable[[EffectsEngine], float],
    logger: logging.Logger,
) -> bool:
    try:
        brightness_hw = 0
        rendered_color_map: Mapping[Key, Color] = color_map
        with engine.kb_lock:
            if not _reactive_hardware_writes_allowed(engine):
                return True
            _, _, brightness_hw = resolve_brightness(engine)
            transition_visual_scale = resolve_transition_visual_scale(engine)
            log_render_visual_scale_change(
                engine,
                logger=logger,
                brightness_hw=brightness_hw,
                transition_visual_scale=transition_visual_scale,
            )
            if transition_visual_scale < 0.999:
                rendered_color_map = _scale_color_map(color_map, factor=transition_visual_scale)
            engine._last_rendered_brightness = brightness_hw

            reassert_every_frame = per_key_mode_requires_frame_reassert(engine.kb)
            mode_uninitialized = _last_hw_mode_brightness_or_none(engine) is None
            frame_signature = _per_key_frame_signature(rendered_color_map, brightness_hw=brightness_hw)
            if not mode_uninitialized and frame_signature == _last_reactive_per_key_frame_signature_or_none(engine):
                return True
            if not _reactive_hardware_writes_allowed(engine):
                return True

            need_mode_init = reassert_every_frame or mode_uninitialized
            if need_mode_init:
                apply_hw_brightness(engine, brightness_hw, force_reinit=reassert_every_frame)

            try:
                engine.kb.set_key_colors(rendered_color_map, brightness=int(brightness_hw), enable_user_mode=False)
            except _REACTIVE_RENDER_RUNTIME_ERRORS as exc:
                if is_device_disconnected(exc):
                    try:
                        engine.mark_device_unavailable()
                    except _REACTIVE_RENDER_CLEANUP_ERRORS as mark_exc:  # @quality-exception exception-transparency: disconnect cleanup must stay best-effort and still suppress further reactive hardware writes even if invalidation fails
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
            engine._last_reactive_per_key_frame_signature = frame_signature
        render_secondary_uniform_rgb(
            engine,
            rgb=average_color_map(rendered_color_map),
            brightness_hw=brightness_hw,
            logger=logger,
            log_key="effects.reactive.secondary",
        )
        return True
    except _REACTIVE_RENDER_RUNTIME_ERRORS as exc:
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
    engine: EffectsEngine,
    *,
    color_map: Mapping[Key, Color],
    resolve_brightness: Callable[[EffectsEngine], tuple[int, int, int]],
) -> None:
    rgb = average_color_map(color_map)
    final_rgb = rgb
    brightness_hw = 0

    with engine.kb_lock:
        if not _reactive_hardware_writes_allowed(engine):
            return
        _, _, brightness_hw = resolve_brightness(engine)
        engine._last_rendered_brightness = brightness_hw
        r, g, b = avoid_full_black(rgb=rgb, target_rgb=rgb, brightness=int(brightness_hw))
        final_rgb = (r, g, b)

        need_mode_init = _last_hw_mode_brightness_or_none(engine) is None
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


def average_color_map(color_map: Mapping[Key, Color]) -> Color:
    return average_color_map_impl(color_map)


def _scale_color_map(color_map: Mapping[Key, Color], *, factor: float) -> Mapping[Key, Color]:
    f = max(0.0, min(1.0, float(factor)))
    if f >= 0.999:
        return color_map
    if f <= 0.0:
        return {key: (0, 0, 0) for key in color_map}
    return {
        key: (
            round(rgb[0] * f),
            round(rgb[1] * f),
            round(rgb[2] * f),
        )
        for key, rgb in color_map.items()
    }
