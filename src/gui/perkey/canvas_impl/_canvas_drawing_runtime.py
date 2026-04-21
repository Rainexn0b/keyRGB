from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from PIL import Image

from src.core.resources.layout import BASE_IMAGE_SIZE, KeyDef, get_layout_keys
from src.gui.reference.overlay_geometry import (
    CanvasTransform,
    calc_centered_drawn_bbox,
    key_canvas_hit_rects,
    key_canvas_rect,
)
from src.gui.utils.key_draw_style import KeyDrawStyle, key_draw_style
from src.gui.utils.profile_backdrop_storage import load_backdrop_image

from ..lightbar_layout import lightbar_rect_for_size
from ..profile_management import keymap_cells_for, representative_cell


KeyCell = tuple[int, int]
KeyCells = tuple[KeyCell, ...]
LayoutTweaks = dict[str, float]
PerKeyLayoutTweaks = dict[str, dict[str, float]]
LayoutSlotOverrides = dict[str, dict[str, object]]
ShapeRect = tuple[float, float, float, float]


class _CalcCenteredDrawnBboxProtocol(Protocol):
    def __call__(
        self,
        *,
        canvas_w: int,
        canvas_h: int,
        image_size: tuple[int, int] = BASE_IMAGE_SIZE,
    ) -> tuple[int, int, int, int, float]: ...


class _GetLayoutKeysProtocol(Protocol):
    def __call__(
        self,
        physical_layout: str = "auto",
        *,
        legend_pack_id: str | None,
        slot_overrides: LayoutSlotOverrides | None,
    ) -> Sequence[KeyDef]: ...


class _KeyCanvasHitRectsProtocol(Protocol):
    def __call__(
        self,
        *,
        transform: CanvasTransform,
        key: KeyDef,
        layout_tweaks: LayoutTweaks,
        per_key_layout_tweaks: PerKeyLayoutTweaks,
        image_size: tuple[int, int] = BASE_IMAGE_SIZE,
    ) -> Sequence[ShapeRect]: ...


class _KeyCanvasRectProtocol(Protocol):
    def __call__(
        self,
        *,
        transform: CanvasTransform,
        key: KeyDef,
        layout_tweaks: LayoutTweaks,
        per_key_layout_tweaks: PerKeyLayoutTweaks,
        image_size: tuple[int, int] = BASE_IMAGE_SIZE,
    ) -> tuple[float, float, float, float, float]: ...


class _KeyDrawStyleFactoryProtocol(Protocol):
    def __call__(
        self,
        *,
        mapped: bool,
        selected: bool,
        color: tuple[int, int, int] | None = None,
    ) -> KeyDrawStyle: ...


class _KeymapCellsForProtocol(Protocol):
    def __call__(
        self,
        keymap: Mapping[str, object],
        key_id: str | None,
        *,
        slot_id: str | None = None,
        physical_layout: str | None = None,
    ) -> KeyCells: ...


class _RepresentativeCellProtocol(Protocol):
    def __call__(
        self,
        cells: object,
        colors: Mapping[KeyCell, object] | None = None,
    ) -> KeyCell | None: ...


class _LightbarRectForSizeProtocol(Protocol):
    def __call__(
        self,
        *,
        width: float,
        height: float,
        overlay: dict[str, object] | None,
    ) -> tuple[float, float, float, float] | None: ...


class _LoadBackdropImageProtocol(Protocol):
    def __call__(
        self,
        profile_name: str,
        *,
        backdrop_mode: str | None = None,
    ) -> Image.Image | None: ...


@dataclass(frozen=True)
class CanvasDrawingRuntime:
    base_image_size: tuple[int, int]
    calc_centered_drawn_bbox: _CalcCenteredDrawnBboxProtocol
    get_layout_keys: _GetLayoutKeysProtocol
    key_canvas_hit_rects: _KeyCanvasHitRectsProtocol
    key_canvas_rect: _KeyCanvasRectProtocol
    key_draw_style: _KeyDrawStyleFactoryProtocol
    keymap_cells_for: _KeymapCellsForProtocol
    representative_cell: _RepresentativeCellProtocol
    lightbar_rect_for_size: _LightbarRectForSizeProtocol
    load_backdrop_image: _LoadBackdropImageProtocol


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