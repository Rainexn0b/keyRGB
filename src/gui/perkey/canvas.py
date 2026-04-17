from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Optional

from src.core.resources.layout import BASE_IMAGE_SIZE, KeyDef, get_layout_keys
from src.gui.reference import overlay_geometry as _overlay_geometry
from src.gui.utils.deck_render_cache import DeckRenderCache

from .canvas_impl import _canvas_services
from .canvas_impl import canvas_hit_testing as _canvas_hit_testing
from .canvas_impl._canvas_drawing import _KeyboardCanvasDrawingMixin
from .canvas_impl._canvas_events import _KeyboardCanvasEventMixin

from .overlay import OverlayDragController

if TYPE_CHECKING:
    from .editor import PerKeyEditor


# Preserve module-level monkeypatch seams while keeping the import block compact.
apply_global_tweak = _overlay_geometry.apply_global_tweak
apply_per_key_tweak = _overlay_geometry.apply_per_key_tweak
inset_bbox = _overlay_geometry.inset_bbox
key_canvas_hit_rects = _overlay_geometry.key_canvas_hit_rects
key_canvas_rect = _overlay_geometry.key_canvas_rect
transform_from_drawn_bbox = _overlay_geometry.transform_from_drawn_bbox

cursor_for_edges = _canvas_hit_testing.cursor_for_edges
point_in_bbox = _canvas_hit_testing.point_in_bbox
point_near_bbox = _canvas_hit_testing.point_near_bbox
resize_edges_for_point_in_bbox = _canvas_hit_testing.resize_edges_for_point_in_bbox


KEYDEF_BY_ID: dict[str, KeyDef] = _canvas_services.KEYDEF_BY_ID
KEYDEF_BY_SLOT_ID: dict[str, KeyDef] = _canvas_services.KEYDEF_BY_SLOT_ID


class KeyboardCanvas(_KeyboardCanvasEventMixin, _KeyboardCanvasDrawingMixin, tk.Canvas):
    def __init__(self, parent, editor: PerKeyEditor, **kwargs):
        super().__init__(parent, **kwargs)
        self.editor = editor
        self._deck_img: Optional[object] = None
        self._deck_img_tk: Optional[object] = None
        self._deck_render_cache: DeckRenderCache[object] = DeckRenderCache()
        self._deck_drawn_bbox: Optional[tuple[int, int, int, int]] = None
        self._overlay_drag = OverlayDragController(self)
        self._resize_job: Optional[str] = None

        self.key_rects: dict[str, int] = {}
        self.key_texts: dict[str, int] = {}

        self.bind("<Configure>", self._on_resize)
        self.bind("<Button-1>", self._on_click)
        self.bind("<ButtonPress-1>", self._overlay_drag.on_press)
        self.bind("<B1-Motion>", self._overlay_drag.on_drag)
        self.bind("<ButtonRelease-1>", self._overlay_drag.on_release)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", self._on_leave)

        self._load_deck_image()

    def _inset_pixels(self, w_px: float, h_px: float, inset_value: float) -> float:
        x1, y1, x2, y2 = inset_bbox(
            x1=0.0,
            y1=0.0,
            x2=float(w_px),
            y2=float(h_px),
            inset_value=float(inset_value),
        )
        return float(x1)

    def _apply_global_tweak(self, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        return apply_global_tweak(
            rect=(float(x), float(y), float(w), float(h)),
            layout_tweaks=self.editor.layout_tweaks,
            image_size=BASE_IMAGE_SIZE,
        )

    def _apply_per_key_tweak(
        self, key_id: str, x: float, y: float, w: float, h: float, *, slot_id: str | None = None
    ) -> tuple[float, float, float, float, float]:
        inset_default = float(self.editor.layout_tweaks.get("inset", 0.06))
        return apply_per_key_tweak(
            key_id=str(key_id),
            slot_id=str(slot_id or "") or None,
            rect=(float(x), float(y), float(w), float(h)),
            per_key_layout_tweaks=self.editor.per_key_layout_tweaks,
            inset_default=inset_default,
        )

    def _key_rect_canvas(self, key: KeyDef) -> tuple[float, float, float, float, float] | None:
        t = self._canvas_transform()
        if t is None:
            return None
        x1, y1, x2, y2, inset_value = key_canvas_rect(
            transform=t,
            key=key,
            layout_tweaks=self.editor.layout_tweaks,
            per_key_layout_tweaks=self.editor.per_key_layout_tweaks,
            image_size=BASE_IMAGE_SIZE,
        )
        return x1, y1, x2, y2, inset_value

    def _canvas_transform(self) -> _overlay_geometry.CanvasTransform | None:
        if self._deck_drawn_bbox is None:
            return None
        x0, y0, dw, dh = self._deck_drawn_bbox
        return transform_from_drawn_bbox(x0=x0, y0=y0, draw_w=dw, draw_h=dh, image_size=BASE_IMAGE_SIZE)

    def _keydef_by_slot_id(self, slot_id: str) -> KeyDef | None:
        return _canvas_services.keydef_by_slot_id(
            self,
            slot_id,
            get_layout_keys=get_layout_keys,
            fallback_by_slot_id=KEYDEF_BY_SLOT_ID,
        )

    def _keydef_by_id(self, key_id: str) -> KeyDef | None:
        return _canvas_services.keydef_by_id(
            self,
            key_id,
            get_layout_keys=get_layout_keys,
            fallback_by_id=KEYDEF_BY_ID,
        )

    def _visible_layout_keys(self) -> list[KeyDef]:
        return _canvas_services.visible_layout_keys(self.editor, get_layout_keys=get_layout_keys)

    def _keydef_by_identity(self, identity: str) -> KeyDef | None:
        return _canvas_services.keydef_by_identity(self, identity)

    def _resize_edges_for_point(self, identity: str, cx: float, cy: float) -> str:
        return _canvas_services.resize_edges_for_point(
            self,
            identity,
            cx,
            cy,
            keydef_by_identity=lambda value: KeyboardCanvas._keydef_by_identity(self, value),
            resize_edges_for_point_in_bbox=resize_edges_for_point_in_bbox,
        )

    def _cursor_for_edges(self, edges: str) -> str:
        return cursor_for_edges(edges)

    def _point_in_key_bbox(self, identity: str, cx: float, cy: float) -> bool:
        return _canvas_services.point_in_key_bbox(
            self,
            identity,
            cx,
            cy,
            keydef_by_identity=lambda value: KeyboardCanvas._keydef_by_identity(self, value),
            point_in_bbox=point_in_bbox,
        )

    def _point_near_key_bbox(self, identity: str, cx: float, cy: float, *, pad: float) -> bool:
        return _canvas_services.point_near_key_bbox(
            self,
            identity,
            cx,
            cy,
            keydef_by_identity=lambda value: KeyboardCanvas._keydef_by_identity(self, value),
            point_near_bbox=point_near_bbox,
            pad=pad,
        )

    def _key_rect_base_after_global(self, identity: str) -> tuple[float, float, float, float] | None:
        kd = KeyboardCanvas._keydef_by_identity(self, identity)
        if kd is None:
            return None
        x, y, w, h = (float(v) for v in kd.rect)
        return self._apply_global_tweak(x, y, w, h)

    def _key_bbox_canvas(self, key: KeyDef) -> tuple[float, float, float, float] | None:
        rect = self._key_rect_canvas(key)
        if rect is None:
            return None
        x1, y1, x2, y2, inset_value = rect
        inset = self._inset_pixels(x2 - x1, y2 - y1, inset_value)
        return (x1 + inset, y1 + inset, x2 - inset, y2 - inset)

    def _overlay_drag_geometry(
        self, identity: str
    ) -> tuple[float, float, float, float, float, float, float, float] | None:
        """Return (gx, gy, gw, gh, l0, r0, t0, b0) for the selected key overlay.

        gx/gy/gw/gh is the base rect after global tweak. l0/r0/t0/b0 is the per-key
        tweaked rect bounds in base-image coordinates.
        """

        base_rect = self._key_rect_base_after_global(identity)
        if base_rect is None:
            return None
        gx, gy, gw, gh = base_rect

        key = KeyboardCanvas._keydef_by_identity(self, identity)
        if key is None:
            return None
        x2, y2, w2, h2, _inset = self._apply_per_key_tweak(
            str(key.key_id),
            gx,
            gy,
            gw,
            gh,
            slot_id=str(getattr(key, "slot_id", None) or "") or None,
        )
        l0, r0 = x2, x2 + w2
        t0, b0 = y2, y2 + h2
        return (
            float(gx),
            float(gy),
            float(gw),
            float(gh),
            float(l0),
            float(r0),
            float(t0),
            float(b0),
        )

    def _hit_test_slot_id(self, cx: float, cy: float) -> str | None:
        return _canvas_services.hit_test_slot_id(
            self,
            cx,
            cy,
            get_layout_keys=get_layout_keys,
            key_canvas_hit_rects=key_canvas_hit_rects,
            image_size=BASE_IMAGE_SIZE,
            point_in_bbox=point_in_bbox,
        )

    def _hit_test_key_id(self, cx: float, cy: float) -> str | None:
        return _canvas_services.hit_test_key_id(
            cx,
            cy,
            hit_test_slot_id=lambda x, y: KeyboardCanvas._hit_test_slot_id(self, x, y),
            keydef_by_slot_id=lambda value: KeyboardCanvas._keydef_by_slot_id(self, value),
        )

    def _overlay_press_mode(
        self,
        *,
        selected_slot_id: str | None = None,
        selected_key_id: str | None = None,
        cx: float,
        cy: float,
        pad: float = 6.0,
    ) -> tuple[str, str] | None:
        """Return (mode, edges) for an overlay press, or None if not applicable.

        Mode is either "move" or "resize". Edges is a subset of "lrtb".
        """
        return _canvas_services.overlay_press_mode(
            selected_slot_id=selected_slot_id,
            selected_key_id=selected_key_id,
            cx=cx,
            cy=cy,
            pad=float(pad),
            keydef_by_id=lambda value: KeyboardCanvas._keydef_by_id(self, value),
            resize_edges_for_point=self._resize_edges_for_point,
            point_near_key_bbox=self._point_near_key_bbox,
            hit_test_slot_id=self._hit_test_slot_id,
        )

    # (event handlers and drawing methods live in mixins)
