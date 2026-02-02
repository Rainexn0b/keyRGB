from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal

from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS
from src.core.effects.perkey_animation import build_full_color_grid

from src.tray.ui.icon_draw import create_icon, create_icon_mosaic, create_icon_rainbow
from src.tray.ui.icon_color import representative_color


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


def _is_non_uniform_effect(config: Any) -> bool:
    effect = str(getattr(config, "effect", "none") or "none")

    if effect == "perkey":
        try:
            per_key = dict(getattr(config, "per_key_colors", {}) or {})
        except Exception:
            per_key = {}

        if not per_key:
            return False

        base_color = getattr(config, "color", (255, 0, 128)) or (255, 0, 128)
        try:
            full = build_full_color_grid(
                base_color=tuple(base_color),
                per_key_colors=per_key,
                num_rows=NUM_ROWS,
                num_cols=NUM_COLS,
            )
            # Detect true non-uniformity from the *final* grid.
            it = iter(full.values())
            first = next(it)
            for v in it:
                if v != first:
                    return True
            return False
        except Exception:
            # Fall back: treat multiple override values as non-uniform.
            try:
                return len({tuple(v) for v in per_key.values()}) >= 2
            except Exception:
                return True

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


def icon_visual(*, config: Any, is_off: bool, now: float | None = None) -> IconVisual:
    """Describe how the tray icon should look for the current state."""

    if now is None:
        now = time.time()

    effect = str(getattr(config, "effect", "none") or "none")

    if (not is_off) and getattr(config, "brightness", 0) != 0 and _is_non_uniform_effect(config):
        brightness = int(getattr(config, "brightness", 25) or 25)
        if effect == "perkey":
            try:
                brightness = int(getattr(config, "perkey_brightness", brightness) or brightness)
            except Exception:
                pass

            # For per-key, prefer showing a tiny grid preview in the K cutout.
            try:
                base_color = getattr(config, "color", (255, 0, 128)) or (255, 0, 128)
                per_key = dict(getattr(config, "per_key_colors", {}) or {})
                full = build_full_color_grid(
                    base_color=tuple(base_color),
                    per_key_colors=per_key,
                    num_rows=NUM_ROWS,
                    num_cols=NUM_COLS,
                )
                colors_flat = tuple(full[(r, c)] for r in range(NUM_ROWS) for c in range(NUM_COLS))
                return IconVisual(
                    mode="mosaic",
                    scale=_icon_scale_from_brightness(brightness),
                    colors_flat=colors_flat,
                    rows=NUM_ROWS,
                    cols=NUM_COLS,
                )
            except Exception:
                # Fall back to rainbow if we can't build the grid.
                pass

        # Non-uniform non-perkey: use a rainbow K.
        phase = (float(now) * 0.08) % 1.0
        return IconVisual(mode="rainbow", scale=_icon_scale_from_brightness(brightness), phase=phase)

    return IconVisual(mode="solid", color=representative_color(config=config, is_off=is_off))


__all__ = [
    "create_icon",
    "create_icon_mosaic",
    "create_icon_rainbow",
    "representative_color",
    "IconVisual",
    "icon_visual",
]
