from __future__ import annotations

import logging
from tkinter import font as tkfont

from PIL import Image, ImageTk

from src.core.resources.layout import BASE_IMAGE_SIZE, REFERENCE_DEVICE_KEYS
from src.gui.reference.deck_image import load_reference_deck_image
from src.gui.reference.overlay_geometry import calc_centered_drawn_bbox, key_canvas_rect
from src.gui.utils.key_draw_style import key_draw_style


logger = logging.getLogger(__name__)


class _KeyboardCanvasDrawingMixin:
    def _load_deck_image(self) -> None:
        prof = getattr(self.editor, "profile_name", None)
        self._deck_img = load_reference_deck_image(profile_name=str(prof) if isinstance(prof, str) else None)

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
            style = key_draw_style(
                mapped=mapped,
                selected=self.editor.selected_key_id == key.key_id,
                color=color,
            )

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
            font_name = "TkDefaultFont"
            font_size = max(7, min(11, int(min(key_w, key_h) * 0.30)))
            max_text_w = max(1, key_w - 6)

            label = key.label
            try:
                f = tkfont.Font(font=(font_name, font_size))
                while font_size > 6 and f.measure(label) > max_text_w:
                    font_size -= 1
                    f.configure(size=font_size)
                if f.measure(label) > max_text_w:
                    ell = "…"
                    if f.measure(ell) <= max_text_w:
                        trimmed = label
                        while trimmed and f.measure(trimmed + ell) > max_text_w:
                            trimmed = trimmed[:-1]
                        label = (trimmed + ell) if trimmed else ell
            except Exception:
                pass

            text_id = self.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=label,
                fill=style.text_fill,
                font=(font_name, font_size),
                tags=(f"pkey_{key.key_id}", "pkey"),
            )
            self.key_texts[key.key_id] = text_id

            self.tag_bind(
                f"pkey_{key.key_id}",
                "<Button-1>",
                lambda _e, kid=key.key_id: self.editor.on_key_clicked(kid),
            )

    def _draw_deck_background(self) -> None:
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
