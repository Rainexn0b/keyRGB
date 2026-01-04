from __future__ import annotations

import logging
import tkinter as tk
from PIL import Image, ImageTk
from typing import TYPE_CHECKING, Optional

from src.core.logging_utils import log_throttled

from src.core.resources.layout import BASE_IMAGE_SIZE, REFERENCE_DEVICE_KEYS, KeyDef
from src.gui.reference_deck_image import load_reference_deck_image
from src.gui.reference_overlay_geometry import (
    CanvasTransform,
    apply_global_tweak,
    apply_per_key_tweak,
    calc_centered_drawn_bbox,
    inset_bbox,
    key_canvas_rect,
    transform_from_drawn_bbox,
)
from src.gui.key_draw_style import key_draw_style

from .canvas_hit_testing import (
    cursor_for_edges,
    point_in_bbox,
    point_near_bbox,
    resize_edges_for_point_in_bbox,
)

from .overlay import OverlayDragController

if TYPE_CHECKING:
    from .editor import PerKeyEditor


logger = logging.getLogger(__name__)


KEYDEF_BY_ID: dict[str, KeyDef] = {k.key_id: k for k in REFERENCE_DEVICE_KEYS}


class KeyboardCanvas(tk.Canvas):
    def __init__(self, parent, editor: PerKeyEditor, **kwargs):
        super().__init__(parent, **kwargs)
        self.editor = editor
        self._deck_img: Optional[Image.Image] = None
        self._deck_img_tk: Optional[ImageTk.PhotoImage] = None
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

    def _load_deck_image(self):
        prof = getattr(self.editor, "profile_name", None)
        self._deck_img = load_reference_deck_image(profile_name=str(prof) if isinstance(prof, str) else None)

    def reload_backdrop_image(self) -> None:
        """Reload the backdrop image for the current profile and redraw."""

        self._load_deck_image()
        self.redraw()

    def redraw(self):
        self.delete("all")
        self._draw_deck_background()
        self.key_rects = {}
        self.key_texts = {}

        t = self._canvas_transform()
        if t is None:
            return

        for key in REFERENCE_DEVICE_KEYS:
            x1, y1, x2, y2, inset_value = key_canvas_rect(
                transform=t,
                key=key,
                layout_tweaks=self.editor.layout_tweaks,
                per_key_layout_tweaks=self.editor.per_key_layout_tweaks,
                image_size=BASE_IMAGE_SIZE,
            )

            inset = self._inset_pixels(x2 - x1, y2 - y1, inset_value)
            x1 += inset
            y1 += inset
            x2 -= inset
            y2 -= inset

            mapped_cell = self.editor.keymap.get(key.key_id)
            mapped = mapped_cell is not None
            color = self.editor.colors.get(mapped_cell) if mapped_cell is not None else None
            style = key_draw_style(mapped=mapped, selected=self.editor.selected_key_id == key.key_id, color=color)

            rect_id = self.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill=style.fill,
                stipple=style.stipple,
                outline=style.outline,
                width=style.width,
                dash=style.dash,
                tags=(f"pkey_{key.key_id}", "pkey"),
            )
            self.key_rects[key.key_id] = rect_id

            key_w = max(1, int(x2 - x1))
            key_h = max(1, int(y2 - y1))
            font_size = max(7, min(11, int(min(key_w, key_h) * 0.30)))
            text_id = self.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=key.label,
                fill=style.text_fill,
                font=("TkDefaultFont", font_size),
                tags=(f"pkey_{key.key_id}", "pkey"),
            )
            self.key_texts[key.key_id] = text_id

            self.tag_bind(
                f"pkey_{key.key_id}",
                "<Button-1>",
                lambda _e, kid=key.key_id: self.editor.on_key_clicked(kid),
            )

    def _draw_deck_background(self):
        if self._deck_img is None:
            self._deck_drawn_bbox = None
            return

        cw = max(1, int(self.winfo_width()))
        ch = max(1, int(self.winfo_height()))

        x0, y0, dw, dh, _scale = calc_centered_drawn_bbox(
            canvas_w=cw,
            canvas_h=ch,
            image_size=self._deck_img.size,
        )

        resized = self._deck_img.resize((dw, dh), Image.Resampling.LANCZOS)

        # Backdrop transparency is a user-facing percentage:
        # 0 = opaque, 100 = fully transparent.
        try:
            t = float(getattr(self.editor, "backdrop_transparency", 0).get())
        except Exception:
            try:
                t = float(getattr(self.editor, "backdrop_transparency", 0) or 0)
            except Exception:
                t = 0.0
        t = max(0.0, min(100.0, float(t)))
        if t > 0.0:
            alpha_mul = max(0.0, min(1.0, (100.0 - t) / 100.0))
            try:
                a = resized.getchannel("A")
                a = a.point(lambda px: int(px * alpha_mul))
                resized.putalpha(a)
            except Exception:
                # Best-effort: if alpha manipulation fails, keep original.
                pass

        self._deck_img_tk = ImageTk.PhotoImage(resized)
        self.create_image(x0, y0, image=self._deck_img_tk, anchor="nw")
        self._deck_drawn_bbox = (x0, y0, dw, dh)

    def _on_resize(self, _event):
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except Exception as exc:
                log_throttled(
                    logger,
                    "perkey.canvas.after_cancel",
                    interval_s=60,
                    level=logging.DEBUG,
                    msg="after_cancel failed",
                    exc=exc,
                )
        self._resize_job = self.after(40, self._redraw_callback)

    def _redraw_callback(self):
        self._resize_job = None
        self.redraw()

    def _inset_pixels(self, w_px: float, h_px: float, inset_value: float) -> float:
        x1, y1, x2, y2 = inset_bbox(x1=0.0, y1=0.0, x2=float(w_px), y2=float(h_px), inset_value=float(inset_value))
        return float(x1)

    def _apply_global_tweak(self, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        return apply_global_tweak(
            rect=(float(x), float(y), float(w), float(h)),
            layout_tweaks=self.editor.layout_tweaks,
            image_size=BASE_IMAGE_SIZE,
        )

    def _apply_per_key_tweak(
        self, key_id: str, x: float, y: float, w: float, h: float
    ) -> tuple[float, float, float, float, float]:
        inset_default = float(self.editor.layout_tweaks.get("inset", 0.06))
        return apply_per_key_tweak(
            key_id=str(key_id),
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

    def _on_motion(self, event):
        # Cursor affordances for overlay move/resize.
        try:
            if self.editor.overlay_scope.get() != "key" or not self.editor.selected_key_id:
                self.configure(cursor="")
                return

            cx = float(event.x)
            cy = float(event.y)
            edges = self._resize_edges_for_point(self.editor.selected_key_id, cx, cy)
            if edges:
                self.configure(cursor=self._cursor_for_edges(edges))
                return

            # Inside selected key: show move cursor.
            if self._point_in_key_bbox(self.editor.selected_key_id, cx, cy):
                self.configure(cursor="fleur")
            else:
                self.configure(cursor="")
        except Exception:
            log_throttled(
                logger,
                "perkey.canvas.on_motion",
                interval_s=60,
                level=logging.DEBUG,
                msg="Error in perkey hover handling",
            )

    def _on_leave(self, _event):
        try:
            self.configure(cursor="")
        except Exception as exc:
            log_throttled(
                logger,
                "perkey.canvas.on_leave",
                interval_s=60,
                level=logging.DEBUG,
                msg="Error resetting cursor",
                exc=exc,
            )

    def _keydef_by_id(self, key_id: str) -> KeyDef | None:
        return KEYDEF_BY_ID.get(key_id)

    def _resize_edges_for_point(self, key_id: str, cx: float, cy: float) -> str:
        kd = self._keydef_by_id(key_id)
        if kd is None:
            return ""
        bbox = self._key_bbox_canvas(kd)
        if bbox is None:
            return ""
        x1, y1, x2, y2 = bbox

        return resize_edges_for_point_in_bbox(x1=x1, y1=y1, x2=x2, y2=y2, cx=cx, cy=cy)

    def _cursor_for_edges(self, edges: str) -> str:
        return cursor_for_edges(edges)

    def _point_in_key_bbox(self, key_id: str, cx: float, cy: float) -> bool:
        kd = self._keydef_by_id(key_id)
        if kd is None:
            return False
        bbox = self._key_bbox_canvas(kd)
        if bbox is None:
            return False
        x1, y1, x2, y2 = bbox
        return point_in_bbox(x1=x1, y1=y1, x2=x2, y2=y2, cx=cx, cy=cy)

    def _point_near_key_bbox(self, key_id: str, cx: float, cy: float, *, pad: float) -> bool:
        kd = self._keydef_by_id(key_id)
        if kd is None:
            return False
        bbox = self._key_bbox_canvas(kd)
        if bbox is None:
            return False
        x1, y1, x2, y2 = bbox
        return point_near_bbox(x1=x1, y1=y1, x2=x2, y2=y2, cx=cx, cy=cy, pad=pad)

    def _key_rect_base_after_global(self, key_id: str) -> tuple[float, float, float, float] | None:
        kd = self._keydef_by_id(key_id)
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

    def _overlay_drag_geometry(self, key_id: str) -> tuple[float, float, float, float, float, float, float, float] | None:
        """Return (gx, gy, gw, gh, l0, r0, t0, b0) for the selected key overlay.

        gx/gy/gw/gh is the base rect after global tweak. l0/r0/t0/b0 is the per-key
        tweaked rect bounds in base-image coordinates.
        """

        base_rect = self._key_rect_base_after_global(key_id)
        if base_rect is None:
            return None
        gx, gy, gw, gh = base_rect

        x2, y2, w2, h2, _inset = self._apply_per_key_tweak(key_id, gx, gy, gw, gh)
        l0, r0 = x2, x2 + w2
        t0, b0 = y2, y2 + h2
        return float(gx), float(gy), float(gw), float(gh), float(l0), float(r0), float(t0), float(b0)

    def _hit_test_key_id(self, cx: float, cy: float) -> str | None:
        t = self._canvas_transform()
        if t is None:
            return None
        for kd in REFERENCE_DEVICE_KEYS:
            x1, y1, x2, y2, inset_value = key_canvas_rect(
                transform=t,
                key=kd,
                layout_tweaks=self.editor.layout_tweaks,
                per_key_layout_tweaks=self.editor.per_key_layout_tweaks,
                image_size=BASE_IMAGE_SIZE,
            )
            inset = self._inset_pixels(x2 - x1, y2 - y1, inset_value)
            x1, y1, x2, y2 = (x1 + inset, y1 + inset, x2 - inset, y2 - inset)
            if point_in_bbox(x1=x1, y1=y1, x2=x2, y2=y2, cx=cx, cy=cy):
                return kd.key_id
        return None

    def _overlay_press_mode(self, *, selected_key_id: str, cx: float, cy: float, pad: float = 6.0) -> tuple[str, str] | None:
        """Return (mode, edges) for an overlay press, or None if not applicable.

        Mode is either "move" or "resize". Edges is a subset of "lrtb".
        """

        if not selected_key_id:
            return None

        edges = self._resize_edges_for_point(selected_key_id, cx, cy)
        if edges:
            if not self._point_near_key_bbox(selected_key_id, cx, cy, pad=float(pad)):
                return None
            return "resize", edges

        kid = self._hit_test_key_id(cx, cy)
        if kid != selected_key_id:
            return None
        return "move", ""

    def _on_click(self, event):
        try:
            current = self.find_withtag("current")
            if current:
                tags = self.gettags(current[0])
                for t in tags:
                    if t.startswith("pkey_"):
                        self.editor.on_key_clicked(t.removeprefix("pkey_"))
                        return
        except Exception as exc:
            log_throttled(
                logger,
                "perkey.canvas.on_click",
                interval_s=60,
                level=logging.DEBUG,
                msg="Error handling click",
                exc=exc,
            )

        kid = self._hit_test_key_id(float(event.x), float(event.y))
        if kid is not None:
            self.editor.on_key_clicked(kid)

    def update_key_visual(self, key_id: str, color: tuple[int, int, int]):
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
