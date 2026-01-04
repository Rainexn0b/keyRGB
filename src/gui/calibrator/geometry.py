from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

from src.core.resources.layout import BASE_IMAGE_SIZE, REFERENCE_DEVICE_KEYS, KeyDef
from src.gui.reference_overlay_geometry import CanvasTransform, hit_test as _hit_test, key_canvas_bbox_inset


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
    # Calibrator expects inset to be fractional and clamped.
    return _hit_test(
        transform=transform,
        x=x,
        y=y,
        layout_tweaks=layout_tweaks,
        per_key_layout_tweaks=per_key_layout_tweaks,
        keys=keys,
        image_size=image_size,
        inset_value_cap=0.20,
    )
