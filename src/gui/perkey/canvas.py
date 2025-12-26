from __future__ import annotations

import os
import tkinter as tk
from PIL import Image, ImageTk
from typing import TYPE_CHECKING, Optional

from src.core.layout import BASE_IMAGE_SIZE, Y15_PRO_KEYS, KeyDef

if TYPE_CHECKING:
    from .editor import PerKeyEditor

class KeyboardCanvas(tk.Canvas):
    def __init__(self, parent, editor: PerKeyEditor, **kwargs):
        super().__init__(parent, **kwargs)
        self.editor = editor
        self._deck_img: Optional[Image.Image] = None
        self._deck_img_tk: Optional[ImageTk.PhotoImage] = None
        self._deck_drawn_bbox: Optional[tuple[int, int, int, int]] = None
        self._drag_ctx: Optional[dict] = None
        self._resize_job: Optional[str] = None
        
        self.key_rects: dict[str, int] = {}
        self.key_texts: dict[str, int] = {}

        self.bind("<Configure>", self._on_resize)
        self.bind("<Button-1>", self._on_click)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

        self._load_deck_image()

    def _load_deck_image(self):
        try:
            # Assuming we are in src/gui/perkey/canvas.py
            # Repo root is ../../../
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
            path = os.path.join(repo_root, 'assets', 'y15-pro-deck.png')
            self._deck_img = Image.open(path)
        except Exception:
            self._deck_img = None

    def redraw(self):
        self.delete("all")
        self._draw_deck_background()
        self.key_rects = {}
        self.key_texts = {}

        if self._deck_drawn_bbox is None:
            return

        for key in Y15_PRO_KEYS:
            rect = self._key_rect_canvas(key)
            if rect is None:
                return
            x1, y1, x2, y2, inset_value = rect

            inset = self._inset_pixels(x2 - x1, y2 - y1, inset_value)
            x1 += inset
            y1 += inset
            x2 -= inset
            y2 -= inset

            mapped = self.editor.keymap.get(key.key_id)
            color = self.editor.colors.get(mapped) if mapped else None
            if color is None:
                fill = "" if mapped is None else "#000000"
                stipple = "" if mapped is None else "gray75"
                text_fill = "#cfcfcf" if mapped is None else "#e0e0e0"
            else:
                r, g, b = color
                fill = f"#{r:02x}{g:02x}{b:02x}"
                brightness = (r * 299 + g * 587 + b * 114) / 1000
                text_fill = "#000000" if brightness > 128 else "#ffffff"
                stipple = "gray50"

            outline = "#00ffff" if self.editor.selected_key_id == key.key_id else ("#777777" if mapped else "#8a8a8a")
            width = 3 if self.editor.selected_key_id == key.key_id else 2
            dash = () if mapped else (3,)

            rect_id = self.create_rectangle(
                x1, y1, x2, y2,
                fill=fill, stipple=stipple, outline=outline, width=width, dash=dash,
                tags=(f"pkey_{key.key_id}", "pkey"),
            )
            self.key_rects[key.key_id] = rect_id

            key_w = max(1, int(x2 - x1))
            key_h = max(1, int(y2 - y1))
            font_size = max(7, min(11, int(min(key_w, key_h) * 0.30)))
            text_id = self.create_text(
                (x1 + x2) / 2, (y1 + y2) / 2,
                text=key.label, fill=text_fill, font=("TkDefaultFont", font_size),
                tags=(f"pkey_{key.key_id}", "pkey"),
            )
            self.key_texts[key.key_id] = text_id

            self.tag_bind(
                f"pkey_{key.key_id}",
                "<Button-1>",
                lambda _e, kid=key.key_id: self.editor.select_key_id(kid),
            )

    def _draw_deck_background(self):
        if self._deck_img is None:
            self._deck_drawn_bbox = None
            return

        cw = max(1, int(self.winfo_width()))
        ch = max(1, int(self.winfo_height()))

        iw, ih = self._deck_img.size
        scale = min(cw / iw, ch / ih)
        dw = max(1, int(iw * scale))
        dh = max(1, int(ih * scale))

        x0 = (cw - dw) // 2
        y0 = (ch - dh) // 2

        resized = self._deck_img.resize((dw, dh), Image.Resampling.LANCZOS)
        self._deck_img_tk = ImageTk.PhotoImage(resized)
        self.create_image(x0, y0, image=self._deck_img_tk, anchor='nw')
        self._deck_drawn_bbox = (x0, y0, dw, dh)

    def _on_resize(self, _event):
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(40, self._redraw_callback)

    def _redraw_callback(self):
        self._resize_job = None
        self.redraw()

    def _inset_pixels(self, w_px: float, h_px: float, inset_value: float) -> float:
        min_dim = max(1.0, min(w_px, h_px))
        if inset_value <= 0.5:
            inset = min_dim * max(0.0, inset_value)
        else:
            inset = max(0.0, inset_value)
        inset = min(inset, (min_dim / 2.0) - 1.0)
        return max(0.0, inset)

    def _apply_global_tweak(self, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        iw, ih = BASE_IMAGE_SIZE
        px = iw / 2.0
        py = ih / 2.0

        g_dx = float(self.editor.layout_tweaks.get("dx", 0.0))
        g_dy = float(self.editor.layout_tweaks.get("dy", 0.0))
        g_sx = float(self.editor.layout_tweaks.get("sx", 1.0))
        g_sy = float(self.editor.layout_tweaks.get("sy", 1.0))

        x = (x - px) * g_sx + px + g_dx
        y = (y - py) * g_sy + py + g_dy
        w = w * g_sx
        h = h * g_sy
        return x, y, w, h

    def _apply_per_key_tweak(self, key_id: str, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float, float]:
        g_inset = float(self.editor.layout_tweaks.get("inset", 0.06))
        kt = self.editor.per_key_layout_tweaks.get(key_id, {})
        k_dx = float(kt.get("dx", 0.0))
        k_dy = float(kt.get("dy", 0.0))
        k_sx = float(kt.get("sx", 1.0))
        k_sy = float(kt.get("sy", 1.0))
        k_inset = float(kt.get("inset", g_inset))

        cx = x + (w / 2.0)
        cy = y + (h / 2.0)
        w2 = w * k_sx
        h2 = h * k_sy
        x2 = cx - (w2 / 2.0) + k_dx
        y2 = cy - (h2 / 2.0) + k_dy
        return x2, y2, w2, h2, k_inset

    def _key_rect_canvas(self, key: KeyDef) -> tuple[float, float, float, float, float] | None:
        if self._deck_drawn_bbox is None:
            return None

        x0, y0, dw, dh = self._deck_drawn_bbox
        iw, ih = BASE_IMAGE_SIZE
        csx = dw / max(1, iw)
        csy = dh / max(1, ih)

        x, y, w, h = (float(v) for v in key.rect)
        x, y, w, h = self._apply_global_tweak(x, y, w, h)
        x, y, w, h, inset_value = self._apply_per_key_tweak(key.key_id, x, y, w, h)

        x1 = x0 + x * csx
        y1 = y0 + y * csy
        x2 = x0 + (x + w) * csx
        y2 = y0 + (y + h) * csy
        return x1, y1, x2, y2, inset_value

    def _on_press(self, event):
        if self.editor.overlay_scope.get() != "key":
            self._drag_ctx = None
            return
        if not self.editor.selected_key_id or self._deck_drawn_bbox is None:
            self._drag_ctx = None
            return

        kid = self._hit_test_key_id(float(event.x), float(event.y))
        if kid != self.editor.selected_key_id:
            self._drag_ctx = None
            return

        kt = self.editor.per_key_layout_tweaks.get(self.editor.selected_key_id, {})
        self._drag_ctx = {
            "kid": self.editor.selected_key_id,
            "x": float(event.x),
            "y": float(event.y),
            "dx": float(kt.get("dx", 0.0)),
            "dy": float(kt.get("dy", 0.0)),
        }

    def _on_drag(self, event):
        if not self._drag_ctx or self._deck_drawn_bbox is None:
            return
        kid = self._drag_ctx.get("kid")
        if not kid:
            return

        x0, y0, dw, dh = self._deck_drawn_bbox
        iw, ih = BASE_IMAGE_SIZE
        csx = dw / max(1, iw)
        csy = dh / max(1, ih)
        if csx <= 0 or csy <= 0:
            return

        dx_canvas = float(event.x) - float(self._drag_ctx["x"])
        dy_canvas = float(event.y) - float(self._drag_ctx["y"])

        dx_base = dx_canvas / csx
        dy_base = dy_canvas / csy

        new_dx = float(self._drag_ctx["dx"]) + dx_base
        new_dy = float(self._drag_ctx["dy"]) + dy_base

        kt = dict(self.editor.per_key_layout_tweaks.get(kid, {}))
        kt["dx"] = new_dx
        kt["dy"] = new_dy
        self.editor.per_key_layout_tweaks[kid] = kt

        self.editor.sync_overlay_vars()
        self.redraw()

    def _on_release(self, _event):
        self._drag_ctx = None

    def _key_bbox_canvas(self, key: KeyDef) -> tuple[float, float, float, float] | None:
        rect = self._key_rect_canvas(key)
        if rect is None:
            return None
        x1, y1, x2, y2, inset_value = rect
        inset = self._inset_pixels(x2 - x1, y2 - y1, inset_value)
        return (x1 + inset, y1 + inset, x2 - inset, y2 - inset)

    def _hit_test_key_id(self, cx: float, cy: float) -> str | None:
        for kd in Y15_PRO_KEYS:
            bbox = self._key_bbox_canvas(kd)
            if bbox is None:
                return None
            x1, y1, x2, y2 = bbox
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                return kd.key_id
        return None

    def _on_click(self, event):
        try:
            current = self.find_withtag("current")
            if current:
                tags = self.gettags(current[0])
                for t in tags:
                    if t.startswith("pkey_"):
                        self.editor.select_key_id(t.removeprefix("pkey_"))
                        return
        except Exception:
            pass

        kid = self._hit_test_key_id(float(event.x), float(event.y))
        if kid is not None:
            self.editor.select_key_id(kid)

    def update_key_visual(self, key_id: str, color: tuple[int, int, int]):
        r, g, b = color
        fill = f"#{r:02x}{g:02x}{b:02x}"
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        text_fill = "#000000" if brightness > 128 else "#ffffff"

        rect_id = self.key_rects.get(key_id)
        if rect_id is not None:
            self.itemconfig(rect_id, fill=fill)
        text_id = self.key_texts.get(key_id)
        if text_id is not None:
            self.itemconfig(text_id, fill=text_fill)
