from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

from src.core.resources.layout import BASE_IMAGE_SIZE, REFERENCE_DEVICE_KEYS, KeyDef
from src.gui.reference_overlay_geometry import CanvasTransform, calc_centered_transform, key_canvas_bbox_inset
from src.gui import reference_overlay_geometry


def calc_transform(
    *,
    canvas_w: int,
    canvas_h: int,
    image_size: tuple[int, int] = BASE_IMAGE_SIZE,
) -> CanvasTransform:
    return calc_centered_transform(canvas_w=canvas_w, canvas_h=canvas_h, image_size=image_size)


def key_canvas_bbox(
    *,
    transform: CanvasTransform,
    key: KeyDef,
    layout_tweaks: Dict[str, float],
    per_key_layout_tweaks: Dict[str, Dict[str, float]],
    image_size: tuple[int, int] = BASE_IMAGE_SIZE,
) -> Tuple[float, float, float, float]:
    # Calibrator expects inset to be fractional and clamped.
    return key_canvas_bbox_inset(
        transform=transform,
        key=key,
        layout_tweaks=layout_tweaks,
        per_key_layout_tweaks=per_key_layout_tweaks,
        image_size=image_size,
        inset_value_cap=0.20,
    )


def hit_test(
    *,
    transform: CanvasTransform,
    x: int,
    y: int,
    layout_tweaks: Dict[str, float],
    per_key_layout_tweaks: Dict[str, Dict[str, float]],
    keys: Iterable[KeyDef] = REFERENCE_DEVICE_KEYS,
    image_size: tuple[int, int] = BASE_IMAGE_SIZE,
) -> Optional[KeyDef]:
    return reference_overlay_geometry.hit_test(
        transform=transform,
        x=x,
        y=y,
        layout_tweaks=layout_tweaks,
        per_key_layout_tweaks=per_key_layout_tweaks,
        keys=keys,
        image_size=image_size,
        inset_value_cap=0.20,
    )
