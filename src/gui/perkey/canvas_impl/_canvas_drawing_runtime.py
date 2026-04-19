from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core.resources.layout import BASE_IMAGE_SIZE, get_layout_keys
from src.gui.reference.overlay_geometry import (
    calc_centered_drawn_bbox,
    key_canvas_hit_rects,
    key_canvas_rect,
)
from src.gui.utils.key_draw_style import key_draw_style
from src.gui.utils.profile_backdrop_storage import load_backdrop_image

from ..lightbar_layout import lightbar_rect_for_size
from ..profile_management import keymap_cells_for, representative_cell


@dataclass(frozen=True)
class CanvasDrawingRuntime:
    base_image_size: tuple[int, int]
    calc_centered_drawn_bbox: Any
    get_layout_keys: Any
    key_canvas_hit_rects: Any
    key_canvas_rect: Any
    key_draw_style: Any
    keymap_cells_for: Any
    representative_cell: Any
    lightbar_rect_for_size: Any
    load_backdrop_image: Any


DEFAULT_CANVAS_DRAWING_RUNTIME = CanvasDrawingRuntime(
    base_image_size=BASE_IMAGE_SIZE,
    calc_centered_drawn_bbox=calc_centered_drawn_bbox,
    get_layout_keys=get_layout_keys,
    key_canvas_hit_rects=key_canvas_hit_rects,
    key_canvas_rect=key_canvas_rect,
    key_draw_style=key_draw_style,
    keymap_cells_for=keymap_cells_for,
    representative_cell=representative_cell,
    lightbar_rect_for_size=lightbar_rect_for_size,
    load_backdrop_image=load_backdrop_image,
)