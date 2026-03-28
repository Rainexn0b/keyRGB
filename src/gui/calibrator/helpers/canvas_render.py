from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from typing import Optional

from PIL import Image, ImageTk

from src.core.resources.layout import BASE_IMAGE_SIZE, REFERENCE_DEVICE_KEYS
from src.gui.reference.overlay_geometry import (
    CanvasTransform,
    calc_centered_drawn_bbox,
    transform_from_drawn_bbox,
)
from src.gui.utils.deck_render_cache import DeckRenderCache
from src.gui.utils.key_draw_style import key_draw_style

from .geometry import key_canvas_bbox


def redraw_calibration_canvas(
    *,
    canvas: tk.Canvas,
    deck_pil: Optional[Image.Image],
    deck_render_cache: DeckRenderCache[ImageTk.PhotoImage],
    layout_tweaks: object,
    per_key_layout_tweaks: object,
    keymap: dict[str, tuple[int, int]],
    selected_key_id: str | None,
) -> tuple[CanvasTransform, Optional[ImageTk.PhotoImage]]:
    canvas.delete("all")

    cw = max(1, int(canvas.winfo_width()))
    ch = max(1, int(canvas.winfo_height()))
    x0, y0, dw, dh, _scale = calc_centered_drawn_bbox(canvas_w=cw, canvas_h=ch, image_size=BASE_IMAGE_SIZE)
    transform = transform_from_drawn_bbox(x0=x0, y0=y0, draw_w=dw, draw_h=dh, image_size=BASE_IMAGE_SIZE)

    deck_tk: Optional[ImageTk.PhotoImage] = None
    if deck_pil is not None:
        deck_tk = deck_render_cache.get_or_create(
            deck_image=deck_pil,
            draw_size=(dw, dh),
            transparency_pct=0.0,
            photo_factory=ImageTk.PhotoImage,
        )
        if deck_tk is not None:
            canvas.create_image(x0, y0, anchor="nw", image=deck_tk)

    for key in REFERENCE_DEVICE_KEYS:
        x1, y1, x2, y2 = key_canvas_bbox(
            transform=transform,
            key=key,
            layout_tweaks=layout_tweaks,
            per_key_layout_tweaks=per_key_layout_tweaks,
            image_size=BASE_IMAGE_SIZE,
        )
        mapped = keymap.get(key.key_id)
        style = key_draw_style(mapped=mapped is not None, selected=selected_key_id == key.key_id)

        canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            outline=style.outline,
            width=style.width,
            fill=style.fill,
            stipple=style.stipple,
            dash=style.dash,
            tags=(f"pkey_{key.key_id}", "pkey"),
        )

        label, font_size = _fit_key_label(key.label, key_w=max(1, int(x2 - x1)), key_h=max(1, int(y2 - y1)))
        canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=label,
            fill=style.text_fill,
            font=("TkDefaultFont", font_size),
            tags=(f"pkey_{key.key_id}", "pkey"),
        )

    return transform, deck_tk


def _fit_key_label(label: str, *, key_w: int, key_h: int) -> tuple[str, int]:
    font_size = max(7, min(11, int(min(key_w, key_h) * 0.30)))
    max_text_w = max(1, key_w - 6)
    fitted_label = label

    try:
        font_obj = tkfont.Font(font=("TkDefaultFont", font_size))
        while font_size > 6 and font_obj.measure(fitted_label) > max_text_w:
            font_size -= 1
            font_obj.configure(size=font_size)
        if font_obj.measure(fitted_label) > max_text_w:
            ellipsis = "…"
            if font_obj.measure(ellipsis) <= max_text_w:
                trimmed = fitted_label
                while trimmed and font_obj.measure(trimmed + ellipsis) > max_text_w:
                    trimmed = trimmed[:-1]
                fitted_label = (trimmed + ellipsis) if trimmed else ellipsis
    except Exception:
        pass

    return fitted_label, font_size