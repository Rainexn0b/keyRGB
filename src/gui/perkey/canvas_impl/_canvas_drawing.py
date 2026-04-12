from __future__ import annotations

import logging
from tkinter import TclError, font as tkfont
from typing import Any

from PIL import Image, ImageTk

from src.core.resources.layout import BASE_IMAGE_SIZE, get_layout_keys
from src.gui.reference.overlay_geometry import calc_centered_drawn_bbox, key_canvas_hit_rects, key_canvas_rect
from src.gui.utils.profile_backdrop_storage import load_backdrop_image
from src.gui.utils.key_draw_style import key_draw_style

from ..lightbar_layout import lightbar_rect_for_size
from ..profile_management import keymap_cells_for, representative_cell


logger = logging.getLogger(__name__)

_BACKDROP_RENDER_ERRORS = (AttributeError, OSError, RuntimeError, TclError, TypeError, ValueError)


def _visible_layout_keys_or_none(canvas: Any) -> list[object] | None:
    try:
        visible_keys_getter = canvas._visible_layout_keys
    except AttributeError:
        return None
    if not callable(visible_keys_getter):
        return None
    return list(visible_keys_getter())


def _resolved_layout_legend_pack_id_or_none(editor: Any) -> str | None:
    try:
        resolve_legend_pack = editor._resolved_layout_legend_pack_id
    except AttributeError:
        return None
    return resolve_legend_pack() if callable(resolve_legend_pack) else None


def _fit_key_label(label: str, *, font_name: str, font_size: int, max_text_w: int) -> tuple[str, int]:
    try:
        font = tkfont.Font(font=(font_name, font_size))
        while font_size > 6 and font.measure(label) > max_text_w:
            font_size -= 1
            font.configure(size=font_size)
        if font.measure(label) > max_text_w:
            ellipsis = "…"
            if font.measure(ellipsis) <= max_text_w:
                trimmed = label
                while trimmed and font.measure(trimmed + ellipsis) > max_text_w:
                    trimmed = trimmed[:-1]
                label = (trimmed + ellipsis) if trimmed else ellipsis
    except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
        logger.debug("Failed to measure key label %r; drawing without truncation.", label, exc_info=True)
    return label, font_size


def _coerce_backdrop_transparency(value: object) -> float:
    raw_value = value
    getter = getattr(raw_value, "get", None)
    if callable(getter):
        try:
            raw_value = getter()
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            logger.debug(
                "Failed to read backdrop transparency variable; falling back to default coercion.", exc_info=True
            )
    try:
        return max(0.0, min(100.0, float(raw_value or 0)))  # type: ignore[arg-type]
    except (AttributeError, TypeError, ValueError, OverflowError):
        logger.debug("Failed to coerce backdrop transparency %r; defaulting to 0.", raw_value, exc_info=True)
        return 0.0


def _shape_polygon_points(shape_rects: list[tuple[float, float, float, float]]) -> list[float]:
    if len(shape_rects) != 2:
        left = min(rect[0] for rect in shape_rects)
        top = min(rect[1] for rect in shape_rects)
        right = max(rect[2] for rect in shape_rects)
        bottom = max(rect[3] for rect in shape_rects)
        return [left, top, right, top, right, bottom, left, bottom]

    upper, lower = sorted(shape_rects, key=lambda rect: (rect[1], rect[0]))
    ux1, uy1, ux2, uy2 = upper
    lx1, _ly1, lx2, ly2 = lower
    return [ux1, uy1, ux2, uy1, ux2, uy2, lx2, uy2, lx2, ly2, lx1, ly2, lx1, uy2, ux1, uy2]


class _KeyboardCanvasDrawingMixin:
    # Attributes/methods provided by tk.Canvas and KeyboardCanvas
    editor: Any
    _canvas_transform: Any
    _deck_render_cache: Any
    _inset_pixels: Any
    create_image: Any
    create_polygon: Any
    create_rectangle: Any
    create_text: Any
    delete: Any
    itemconfig: Any
    tag_bind: Any
    winfo_height: Any
    winfo_width: Any

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
        visible_keys = _visible_layout_keys_or_none(self)
        if visible_keys is None:
            legend_pack_id = _resolved_layout_legend_pack_id_or_none(editor)
            visible_keys = list(
                get_layout_keys(
                    physical_layout,
                    legend_pack_id=legend_pack_id,
                    slot_overrides=getattr(self.editor, "layout_slot_overrides", None),
                )
            )
        else:
            visible_keys = list(visible_keys)

        for key in visible_keys:
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

            mapped_cells = keymap_cells_for(
                self.editor.keymap,
                key.key_id,
                slot_id=str(getattr(key, "slot_id", None) or key.key_id),
                physical_layout=physical_layout,
            )
            mapped = bool(mapped_cells)
            mapped_cell = representative_cell(mapped_cells, colors=self.editor.colors)
            color = self.editor.colors.get(mapped_cell) if mapped_cell is not None else None
            slot_id = str(getattr(key, "slot_id", None) or key.key_id)
            style = key_draw_style(
                mapped=mapped,
                selected=getattr(self.editor, "selected_slot_id", None) == slot_id,
                color=color,
            )

            shape_rects = list(
                key_canvas_hit_rects(
                    transform=t,
                    key=key,
                    layout_tweaks=self.editor.layout_tweaks,
                    per_key_layout_tweaks=self.editor.per_key_layout_tweaks,
                    image_size=BASE_IMAGE_SIZE,
                )
            )
            if len(shape_rects) == 1:
                sx1, sy1, sx2, sy2 = shape_rects[0]
                rect_id = self.create_rectangle(
                    sx1,
                    sy1,
                    sx2,
                    sy2,
                    fill=style.fill,
                    stipple=style.stipple,
                    outline=style.outline,
                    width=style.width,
                    dash=style.dash,
                    tags=(f"pslot_{slot_id}", f"pkey_{key.key_id}", "pkey"),
                )
            else:
                rect_id = self.create_polygon(
                    _shape_polygon_points(shape_rects),
                    fill=style.fill,
                    stipple=style.stipple,
                    outline=style.outline,
                    width=style.width,
                    dash=style.dash,
                    joinstyle="miter",
                    tags=(f"pslot_{slot_id}", f"pkey_{key.key_id}", "pkey"),
                )
            self.key_rects[key.key_id] = rect_id
            self.key_rects[slot_id] = rect_id

            key_w = max(1, int(x2 - x1))
            key_h = max(1, int(y2 - y1))
            font_name = "TkDefaultFont"
            font_size = max(7, min(11, int(min(key_w, key_h) * 0.30)))
            max_text_w = max(1, key_w - 6)

            label, font_size = _fit_key_label(
                key.label,
                font_name=font_name,
                font_size=font_size,
                max_text_w=max_text_w,
            )

            text_id = self.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=label,
                fill=style.text_fill,
                font=(font_name, font_size),
                tags=(f"pslot_{slot_id}", f"pkey_{key.key_id}", "pkey"),
            )
            self.key_texts[key.key_id] = text_id
            self.key_texts[slot_id] = text_id

            self.tag_bind(
                f"pslot_{slot_id}",
                "<Button-1>",
                lambda _e, sid=slot_id: self.editor.on_slot_clicked(sid),
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
