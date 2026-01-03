"""Legacy import path for the historical Y15 Pro naming.

Internal code now uses `src.gui.reference_overlay_geometry`.
"""

from __future__ import annotations

from src.gui.reference_overlay_geometry import (
    CanvasTransform,
    apply_global_tweak,
    apply_per_key_tweak,
    calc_centered_transform,
    hit_test,
    inset_bbox,
    key_canvas_bbox_inset,
    key_canvas_rect,
    transform_from_drawn_bbox,
)

__all__ = [
    "CanvasTransform",
    "calc_centered_transform",
    "transform_from_drawn_bbox",
    "apply_global_tweak",
    "apply_per_key_tweak",
    "key_canvas_rect",
    "inset_bbox",
    "key_canvas_bbox_inset",
    "hit_test",
]
