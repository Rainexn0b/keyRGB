from __future__ import annotations

from collections.abc import Iterable

from keyrgb.core.resources.layout import BASE_IMAGE_SIZE, REFERENCE_DEVICE_KEYS, KeyDef
from keyrgb.gui.reference.overlay_geometry import (
    CanvasTransform,
    hit_test as _hit_test,
    key_canvas_bbox_inset,
)


def key_canvas_bbox(
    *,
    transform: CanvasTransform,
    key: KeyDef,
    layout_tweaks: dict[str, float],
    per_key_layout_tweaks: dict[str, dict[str, float]],
    image_size: tuple[int, int] = BASE_IMAGE_SIZE,
) -> tuple[float, float, float, float]:
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
    layout_tweaks: dict[str, float],
    per_key_layout_tweaks: dict[str, dict[str, float]],
    keys: Iterable[KeyDef] = REFERENCE_DEVICE_KEYS,
    image_size: tuple[int, int] = BASE_IMAGE_SIZE,
) -> KeyDef | None:
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
