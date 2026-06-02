from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Callable, Tuple

from src.core.effects.perkey_animation import enable_user_mode_once, per_key_mode_requires_frame_reassert
from src.core.effects.software_targets import average_color_map as average_color_map_impl
from src.core.effects.software_targets import render_secondary_uniform_rgb
from src.core.effects.transitions import avoid_full_black
from src.core.utils.exceptions import is_device_disconnected
from src.core.utils.logging_utils import log_throttled

from . import _render_brightness_support as _brightness_support

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine

logger = logging.getLogger(__name__)

Color = Tuple[int, int, int]
Key = Tuple[int, int]
FrameEntry = tuple[int, int, int, int, int]
FrameSignature = tuple[int, tuple[tuple[int, int, int, int, int], ...]]

_RECOVERABLE_BRIGHTNESS_WRITE_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_REACTIVE_RENDER_RUNTIME_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_REACTIVE_RENDER_CLEANUP_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _last_hw_mode_brightness_or_none(engine: "EffectsEngine") -> int | None:
    try:
        return engine._last_hw_mode_brightness
    except AttributeError:
        return None


def _last_reactive_per_key_frame_signature_or_none(engine: "EffectsEngine") -> object | None:
    try:
        return engine._last_reactive_per_key_frame_signature
    except AttributeError:
        return None


def _per_key_frame_signature(color_map: Mapping[Key, Color], *, brightness_hw: int) -> FrameSignature:
    entries: list[tuple[int, int, int, int, int]] = []
    for (row, col), (red, green, blue) in color_map.items():
        entries.append((int(row), int(col), int(red), int(green), int(blue)))
    return (int(brightness_hw), tuple(sorted(entries)))


def _frame_signature_or_none(signature: object) -> FrameSignature | None:
    if not isinstance(signature, tuple) or len(signature) != 2:
        return None

    brightness_hw, raw_entries = signature
    if not isinstance(raw_entries, tuple):
        return None

    try:
        normalized_entries = tuple(
            (int(row), int(col), int(red), int(green), int(blue))
            for row, col, red, green, blue in raw_entries
        )
    except (TypeError, ValueError):
        return None

    try:
        normalized_brightness = int(brightness_hw)
    except (TypeError, ValueError):
        return None

    return (normalized_brightness, normalized_entries)


def _reactive_deck_change_threshold(total_keys: int) -> int:
    return max(1, (int(total_keys) * 3) // 4)


def _log_reactive_frame_deck_change_if_needed(
    *,
    logger: logging.Logger,
    previous_signature: object | None,
    frame_signature: FrameSignature,
) -> None:
    if not _brightness_support.debug_brightness_enabled():
        return

    previous = _frame_signature_or_none(previous_signature)
    current = _frame_signature_or_none(frame_signature)
    if previous is None or current is None:
        return

    previous_brightness_hw, previous_entries = previous
    brightness_hw, current_entries = current
    total_keys = len(current_entries)
    if total_keys <= 0:
        return

    previous_by_key = {(row, col): (red, green, blue) for row, col, red, green, blue in previous_entries}

    changed_keys = 0
    lit_keys = 0
    total_red = 0
    total_green = 0
    total_blue = 0
    changed_samples: list[tuple[int, int, int, int, int, int, int, int]] = []
    for row, col, red, green, blue in current_entries:
        total_red += int(red)
        total_green += int(green)
        total_blue += int(blue)
        if red or green or blue:
            lit_keys += 1

        previous_rgb = previous_by_key.get((row, col), (0, 0, 0))
        current_rgb = (int(red), int(green), int(blue))
        if previous_rgb != current_rgb:
            changed_keys += 1
            if len(changed_samples) < 4:
                changed_samples.append(
                    (
                        int(row),
                        int(col),
                        int(previous_rgb[0]),
                        int(previous_rgb[1]),
                        int(previous_rgb[2]),
                        int(current_rgb[0]),
                        int(current_rgb[1]),
                        int(current_rgb[2]),
                    )
                )

    if changed_keys < _reactive_deck_change_threshold(total_keys):
        return

    logger.info(
        "reactive_frame_deck_change changed_keys=%s total_keys=%s lit_keys=%s brightness_hw=%s previous_brightness_hw=%s avg_rgb=(%s,%s,%s) samples=%s",
        int(changed_keys),
        int(total_keys),
        int(lit_keys),
        int(brightness_hw),
        int(previous_brightness_hw),
        int(round(total_red / total_keys)),
        int(round(total_green / total_keys)),
        int(round(total_blue / total_keys)),
        tuple(changed_samples),
    )


def apply_hw_brightness(engine: "EffectsEngine", brightness_hw: int, *, force_reinit: bool = False) -> None:
    """Set hardware brightness, avoiding a full mode reinit when possible."""

    prev = _last_hw_mode_brightness_or_none(engine)
    if force_reinit or prev is None:
        if _brightness_support.debug_brightness_enabled():
            logger.info(
                "apply_hw_brightness: force_reinit=%s prev=%s brightness_hw=%s",
                force_reinit,
                prev,
                brightness_hw,
            )
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

    if _brightness_support.debug_brightness_enabled():
        logger.info(
            "apply_hw_brightness: set_brightness prev=%s brightness_hw=%s",
            prev,
            brightness_hw,
        )
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
    color_map: Mapping[Key, Color],
    resolve_brightness: Callable[["EffectsEngine"], tuple[int, int, int]],
    resolve_transition_visual_scale: Callable[["EffectsEngine"], float],
    logger: logging.Logger,
) -> bool:
    try:
        brightness_hw = 0
        rendered_color_map: Mapping[Key, Color] = color_map
        with engine.kb_lock:
            _, _, brightness_hw = resolve_brightness(engine)
            transition_visual_scale = resolve_transition_visual_scale(engine)
            _brightness_support.log_render_visual_scale_change(
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
            previous_signature = _last_reactive_per_key_frame_signature_or_none(engine)
            if (
                not reassert_every_frame
                and not mode_uninitialized
                and frame_signature == previous_signature
            ):
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
            _log_reactive_frame_deck_change_if_needed(
                logger=logger,
                previous_signature=previous_signature,
                frame_signature=frame_signature,
            )
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
    engine: "EffectsEngine",
    *,
    color_map: Mapping[Key, Color],
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
            int(round(rgb[0] * f)),
            int(round(rgb[1] * f)),
            int(round(rgb[2] * f)),
        )
        for key, rgb in color_map.items()
    }
