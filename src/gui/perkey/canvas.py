from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional

from src.core.resources.layout import BASE_IMAGE_SIZE, REFERENCE_DEVICE_KEYS, KeyDef, get_layout_keys
from src.gui.utils.deck_render_cache import DeckRenderCache
from src.gui.reference.overlay_geometry import (
    CanvasTransform,
    apply_global_tweak,
    apply_per_key_tweak,
    inset_bbox,
    key_canvas_hit_rects,
    key_canvas_rect,
    transform_from_drawn_bbox,
)

from .canvas_impl._canvas_drawing import _KeyboardCanvasDrawingMixin
from .canvas_impl._canvas_events import _KeyboardCanvasEventMixin

from .canvas_impl.canvas_hit_testing import (
    cursor_for_edges,
    point_in_bbox,
    point_near_bbox,
    resize_edges_for_point_in_bbox,
)

from .overlay import OverlayDragController

if TYPE_CHECKING:
    from .editor import PerKeyEditor


KEYDEF_BY_ID: dict[str, KeyDef] = {k.key_id: k for k in REFERENCE_DEVICE_KEYS}
KEYDEF_BY_SLOT_ID: dict[str, KeyDef] = {str(getattr(k, "slot_id", None) or k.key_id): k for k in REFERENCE_DEVICE_KEYS}


def _visible_layout_keys_getter_or_none(editor: Any) -> Callable[[], object] | None:
    try:
        getter = editor._get_visible_layout_keys
    except AttributeError:
        return None
    return getter if callable(getter) else None


def _resolved_layout_legend_pack_id_or_none(editor: Any) -> str | None:
    try:
        resolve_legend_pack = editor._resolved_layout_legend_pack_id
    except AttributeError:
        return None
    if not callable(resolve_legend_pack):
        return None
    return resolve_legend_pack()


def _keydef_by_slot_id_or_none(canvas: Any, identity: str) -> KeyDef | None:
    try:
        slot_lookup = canvas._keydef_by_slot_id
    except AttributeError:
        return None
    return slot_lookup(identity) if callable(slot_lookup) else None


def _keydef_by_id_or_none(canvas: Any, identity: str) -> KeyDef | None:
    try:
        key_lookup = canvas._keydef_by_id
    except AttributeError:
        return None
    return key_lookup(identity) if callable(key_lookup) else None


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

    def _canvas_transform(self) -> CanvasTransform | None:
        if self._deck_drawn_bbox is None:
            return None
        x0, y0, dw, dh = self._deck_drawn_bbox
        return transform_from_drawn_bbox(x0=x0, y0=y0, draw_w=dw, draw_h=dh, image_size=BASE_IMAGE_SIZE)

    def _keydef_by_slot_id(self, slot_id: str) -> KeyDef | None:
        for key in KeyboardCanvas._visible_layout_keys(self):
            if str(getattr(key, "slot_id", None) or key.key_id) == str(slot_id):
                return key
        return KEYDEF_BY_SLOT_ID.get(str(slot_id))

    def _keydef_by_id(self, key_id: str) -> KeyDef | None:
        for key in KeyboardCanvas._visible_layout_keys(self):
            if key.key_id == key_id:
                return key
        return KEYDEF_BY_ID.get(key_id)

    def _visible_layout_keys(self) -> list[KeyDef]:
        getter = _visible_layout_keys_getter_or_none(self.editor)
        if callable(getter):
            return list(getter())

        try:
            physical_layout = self.editor._physical_layout or "auto"
        except AttributeError:
            physical_layout = "auto"
        legend_pack_id = _resolved_layout_legend_pack_id_or_none(self.editor)
        return list(
            get_layout_keys(
                physical_layout,
                legend_pack_id=legend_pack_id,
                slot_overrides=getattr(self.editor, "layout_slot_overrides", None),
            )
        )

    def _keydef_by_identity(self, identity: str) -> KeyDef | None:
        key = _keydef_by_slot_id_or_none(self, identity)
        if key is not None:
            return key
        return _keydef_by_id_or_none(self, identity)

    def _resize_edges_for_point(self, identity: str, cx: float, cy: float) -> str:
        kd = KeyboardCanvas._keydef_by_identity(self, identity)
        if kd is None:
            return ""
        bbox = self._key_bbox_canvas(kd)
        if bbox is None:
            return ""
        x1, y1, x2, y2 = bbox

        return resize_edges_for_point_in_bbox(x1=x1, y1=y1, x2=x2, y2=y2, cx=cx, cy=cy)

    def _cursor_for_edges(self, edges: str) -> str:
        return cursor_for_edges(edges)

    def _point_in_key_bbox(self, identity: str, cx: float, cy: float) -> bool:
        kd = KeyboardCanvas._keydef_by_identity(self, identity)
        if kd is None:
            return False
        bbox = self._key_bbox_canvas(kd)
        if bbox is None:
            return False
        x1, y1, x2, y2 = bbox
        return point_in_bbox(x1=x1, y1=y1, x2=x2, y2=y2, cx=cx, cy=cy)

    def _point_near_key_bbox(self, identity: str, cx: float, cy: float, *, pad: float) -> bool:
        kd = KeyboardCanvas._keydef_by_identity(self, identity)
        if kd is None:
            return False
        bbox = self._key_bbox_canvas(kd)
        if bbox is None:
            return False
        x1, y1, x2, y2 = bbox
        return point_near_bbox(x1=x1, y1=y1, x2=x2, y2=y2, cx=cx, cy=cy, pad=pad)

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
        t = self._canvas_transform()
        if t is None:
            return None
        visible_keys = KeyboardCanvas._visible_layout_keys(self)
        for kd in visible_keys:
            for x1, y1, x2, y2 in key_canvas_hit_rects(
                transform=t,
                key=kd,
                layout_tweaks=self.editor.layout_tweaks,
                per_key_layout_tweaks=self.editor.per_key_layout_tweaks,
                image_size=BASE_IMAGE_SIZE,
            ):
                if point_in_bbox(x1=x1, y1=y1, x2=x2, y2=y2, cx=cx, cy=cy):
                    return str(getattr(kd, "slot_id", None) or kd.key_id)
        return None

    def _hit_test_key_id(self, cx: float, cy: float) -> str | None:
        slot_id = KeyboardCanvas._hit_test_slot_id(self, cx, cy)
        if slot_id is None:
            return None
        key = KeyboardCanvas._keydef_by_slot_id(self, slot_id)
        return str(key.key_id) if key is not None else str(slot_id)

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

        selected_identity = str(selected_slot_id or "")
        if not selected_identity and selected_key_id:
            key = KeyboardCanvas._keydef_by_id(self, str(selected_key_id))
            if key is not None:
                selected_identity = str(getattr(key, "slot_id", None) or key.key_id)
            else:
                selected_identity = str(selected_key_id)
        if not selected_identity:
            return None

        edges = self._resize_edges_for_point(selected_identity, cx, cy)
        if edges:
            if not self._point_near_key_bbox(selected_identity, cx, cy, pad=float(pad)):
                return None
            return "resize", edges

        slot_id = self._hit_test_slot_id(cx, cy)
        if slot_id != selected_identity:
            return None
        return "move", ""

    # (event handlers and drawing methods live in mixins)
