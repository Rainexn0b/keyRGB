from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from tkinter import TclError, font as tkfont
from typing import TYPE_CHECKING, Protocol, TypeAlias

from PIL import Image, ImageTk

from . import _canvas_drawing_helpers as drawing_helpers
from . import _canvas_drawing_render as drawing_render
from ._canvas_drawing_runtime import DEFAULT_CANVAS_DRAWING_RUNTIME

if TYPE_CHECKING:
    from src.core.resources.layout import KeyDef
    from src.gui.reference.overlay_geometry import CanvasTransform

    from ._canvas_drawing_helpers import ShapeRect


BASE_IMAGE_SIZE = DEFAULT_CANVAS_DRAWING_RUNTIME.base_image_size
calc_centered_drawn_bbox = DEFAULT_CANVAS_DRAWING_RUNTIME.calc_centered_drawn_bbox
get_layout_keys = DEFAULT_CANVAS_DRAWING_RUNTIME.get_layout_keys
key_canvas_hit_rects = DEFAULT_CANVAS_DRAWING_RUNTIME.key_canvas_hit_rects
key_canvas_rect = DEFAULT_CANVAS_DRAWING_RUNTIME.key_canvas_rect
key_draw_style = DEFAULT_CANVAS_DRAWING_RUNTIME.key_draw_style
keymap_cells_for = DEFAULT_CANVAS_DRAWING_RUNTIME.keymap_cells_for
lightbar_rect_for_size = DEFAULT_CANVAS_DRAWING_RUNTIME.lightbar_rect_for_size
load_backdrop_image = DEFAULT_CANVAS_DRAWING_RUNTIME.load_backdrop_image
representative_cell = DEFAULT_CANVAS_DRAWING_RUNTIME.representative_cell


logger = logging.getLogger(__name__)

_BACKDROP_RENDER_ERRORS = (AttributeError, OSError, RuntimeError, TclError, TypeError, ValueError)


CanvasItemId: TypeAlias = int
KeyCell: TypeAlias = tuple[int, int]
RGBColor: TypeAlias = tuple[int, int, int]
LayoutTweaks: TypeAlias = dict[str, float]
PerKeyLayoutTweaks: TypeAlias = dict[str, dict[str, float]]
LayoutSlotOverrides: TypeAlias = dict[str, dict[str, object]]
DrawnDeckBBox: TypeAlias = tuple[int, int, int, int]


class _DeckRenderCacheProtocol(Protocol):
    def clear(self) -> None: ...

    def get_or_create(
        self,
        *,
        deck_image: Image.Image | None,
        draw_size: tuple[int, int],
        transparency_pct: float,
        photo_factory: Callable[[Image.Image], object],
    ) -> object | None: ...


class _InsetPixelsProtocol(Protocol):
    def __call__(self, width_px: float, height_px: float, inset_value: float) -> float: ...


class _CanvasCreateImageProtocol(Protocol):
    def __call__(self, x: float, y: float, **kwargs: object) -> CanvasItemId: ...


class _CanvasCreatePolygonProtocol(Protocol):
    def __call__(self, points: Sequence[float], **kwargs: object) -> CanvasItemId: ...


class _CanvasCreateRectangleProtocol(Protocol):
    def __call__(self, x1: float, y1: float, x2: float, y2: float, **kwargs: object) -> CanvasItemId: ...


class _CanvasCreateTextProtocol(Protocol):
    def __call__(self, x: float, y: float, **kwargs: object) -> CanvasItemId: ...


class _CanvasDeleteProtocol(Protocol):
    def __call__(self, tag_or_id: str) -> None: ...


class _CanvasItemConfigProtocol(Protocol):
    def __call__(self, item_id: CanvasItemId, **kwargs: object) -> None: ...


class _CanvasTagBindProtocol(Protocol):
    def __call__(self, tag_or_id: str, event: str, callback: Callable[[object], None]) -> None: ...


class _CanvasSizeGetterProtocol(Protocol):
    def __call__(self) -> int: ...


class _PerKeyCanvasEditorProtocol(Protocol):
    profile_name: object
    _physical_layout: str | None
    layout_slot_overrides: LayoutSlotOverrides | None
    layout_tweaks: LayoutTweaks
    per_key_layout_tweaks: PerKeyLayoutTweaks
    keymap: Mapping[str, object]
    colors: Mapping[KeyCell, RGBColor]
    selected_slot_id: str | None
    has_lightbar_device: bool
    lightbar_overlay: dict[str, object] | None
    backdrop_transparency: object

    def on_slot_clicked(self, slot_id: str) -> None: ...

    def _resolved_layout_legend_pack_id(self) -> str | None: ...


def _visible_layout_keys_or_none(canvas: object) -> list[KeyDef] | None:
    return drawing_helpers._visible_layout_keys_or_none(canvas)


def _resolved_layout_legend_pack_id_or_none(editor: object) -> str | None:
    return drawing_helpers._resolved_layout_legend_pack_id_or_none(editor)


def _fit_key_label(label: str, *, font_name: str, font_size: int, max_text_w: int) -> tuple[str, int]:
    return drawing_helpers._fit_key_label(
        label,
        font_name=font_name,
        font_size=font_size,
        max_text_w=max_text_w,
        font_factory=tkfont.Font,
        logger=logger,
    )


def _coerce_backdrop_transparency(value: object) -> float:
    return drawing_helpers._coerce_backdrop_transparency(value, logger=logger)


def _shape_polygon_points(shape_rects: Sequence[ShapeRect]) -> list[float]:
    return drawing_helpers._shape_polygon_points(shape_rects)


class _KeyboardCanvasDrawingMixin:
    # Attributes/methods provided by tk.Canvas and KeyboardCanvas
    editor: _PerKeyCanvasEditorProtocol
    _canvas_transform: Callable[[], CanvasTransform | None]
    _deck_render_cache: _DeckRenderCacheProtocol
    _inset_pixels: _InsetPixelsProtocol
    create_image: _CanvasCreateImageProtocol
    create_polygon: _CanvasCreatePolygonProtocol
    create_rectangle: _CanvasCreateRectangleProtocol
    create_text: _CanvasCreateTextProtocol
    delete: _CanvasDeleteProtocol
    itemconfig: _CanvasItemConfigProtocol
    tag_bind: _CanvasTagBindProtocol
    winfo_height: _CanvasSizeGetterProtocol
    winfo_width: _CanvasSizeGetterProtocol
    _deck_img: Image.Image | None
    _deck_img_tk: object | None
    _deck_drawn_bbox: DrawnDeckBBox | None
    key_rects: dict[str, CanvasItemId]
    key_texts: dict[str, CanvasItemId]

    def _load_deck_image(self) -> None:
        prof = getattr(self.editor, "profile_name", None)
        self._deck_img = load_backdrop_image(str(prof)) if isinstance(prof, str) else None
        self._deck_render_cache.clear()

    def reload_backdrop_image(self) -> None:
        """Reload the backdrop image for the current profile and redraw."""

        self._load_deck_image()
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        self._draw_deck_background()
        self.key_rects = {}
        self.key_texts = {}

        t = self._canvas_transform()
        if t is None:
            return

        self._draw_lightbar_overlay()

        editor = self.editor
        physical_layout = editor._physical_layout or "auto"
        visible_keys = drawing_render.resolve_visible_keys(
            canvas=self,
            editor=editor,
            physical_layout=physical_layout,
            visible_layout_keys_or_none=_visible_layout_keys_or_none,
            resolved_layout_legend_pack_id_or_none=_resolved_layout_legend_pack_id_or_none,
            get_layout_keys=get_layout_keys,
        )
        drawing_render.render_visible_keys(
            canvas=self,
            transform=t,
            visible_keys=visible_keys,
            physical_layout=physical_layout,
            key_canvas_rect=key_canvas_rect,
            key_canvas_hit_rects=key_canvas_hit_rects,
            key_draw_style=key_draw_style,
            keymap_cells_for=keymap_cells_for,
            representative_cell=representative_cell,
            shape_polygon_points=_shape_polygon_points,
            fit_key_label=_fit_key_label,
        )

    def _draw_deck_background(self) -> None:
        cw = max(1, int(self.winfo_width()))
        ch = max(1, int(self.winfo_height()))

        deck_image = self._deck_img if isinstance(self._deck_img, Image.Image) else None
        image_size = deck_image.size if deck_image is not None else BASE_IMAGE_SIZE

        x0, y0, dw, dh, _scale = calc_centered_drawn_bbox(
            canvas_w=cw,
            canvas_h=ch,
            image_size=image_size,
        )

        self._deck_drawn_bbox = (x0, y0, dw, dh)
        if deck_image is None:
            self._deck_img_tk = None
            return

        # Backdrop transparency is a user-facing percentage:
        # 0 = opaque, 100 = fully transparent.
        t = _coerce_backdrop_transparency(getattr(self.editor, "backdrop_transparency", 0))
        try:
            self._deck_img_tk = self._deck_render_cache.get_or_create(
                deck_image=deck_image,
                draw_size=(dw, dh),
                transparency_pct=t,
                photo_factory=ImageTk.PhotoImage,
            )
        except _BACKDROP_RENDER_ERRORS:
            logger.exception("Deck backdrop render failed; clearing cache and skipping the background image.")
            self._deck_render_cache.clear()
            self._deck_img_tk = None
        if self._deck_img_tk is not None:
            self.create_image(x0, y0, image=self._deck_img_tk, anchor="nw")

    def _draw_lightbar_overlay(self) -> None:
        if not bool(getattr(self.editor, "has_lightbar_device", False)):
            return

        transform = self._canvas_transform()
        if transform is None:
            return

        rect = lightbar_rect_for_size(
            width=float(BASE_IMAGE_SIZE[0]),
            height=float(BASE_IMAGE_SIZE[1]),
            overlay=getattr(self.editor, "lightbar_overlay", None),
        )
        if rect is None:
            return

        x1, y1, x2, y2 = rect
        cx1, cy1, cx2, cy2 = transform.to_canvas((x1, y1, x2 - x1, y2 - y1))
        self.create_rectangle(
            cx1,
            cy1,
            cx2,
            cy2,
            fill="#f28c28",
            stipple="gray50",
            outline="#f7c56f",
            width=2,
            tags=("lightbar_overlay",),
        )

    def update_key_visual(self, key_id: str, color: tuple[int, int, int]) -> None:
        if not key_id:
            return
        r, g, b = color
        fill = f"#{r:02x}{g:02x}{b:02x}"
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        text_fill = "#000000" if brightness > 128 else "#ffffff"

        rect_id = self.key_rects.get(key_id)
        if rect_id is not None:
            # Ensure the new fill is visible even if the key previously had the
            # 'uncolored' stipple.
            self.itemconfig(rect_id, fill=fill, stipple="gray50")
        text_id = self.key_texts.get(key_id)
        if text_id is not None:
            self.itemconfig(text_id, fill=text_fill)


# These imports are only for type checkers.
# They keep the mixin self-contained without causing runtime import cycles.
if False:  # pragma: no cover
    from ..canvas import KeyboardCanvas  # noqa: F401
