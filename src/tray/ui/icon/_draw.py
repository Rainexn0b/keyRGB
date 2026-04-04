from __future__ import annotations

import colorsys
from functools import lru_cache
from typing import cast
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw

from src.gui.theme.detect import detect_system_prefers_dark
from src.tray.ui.icon._mask import candidate_tray_mask_paths as _candidate_tray_mask_paths
from src.tray.ui.icon._mask import render_cairosvg_mask_alpha_64 as _render_cairosvg_mask_alpha_64
from src.tray.ui.icon._mask import render_simple_svg_mask_alpha_64 as _render_simple_svg_mask_alpha_64


_ICON_SIZE = (64, 64)
_TRAY_MASK_PATH_ERRORS = (OSError,)
_TRAY_MASK_RASTER_ERRORS = (
    AttributeError,
    ET.ParseError,
    ImportError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_TRAY_MASK_RENDER_ERRORS = (
    ET.ParseError,
    OSError,
    RuntimeError,
    TypeError,
    UnicodeError,
    ValueError,
)
_THEME_DETECTION_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _coerce_rgb_triplet(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None

    try:
        return (int(value[0]), int(value[1]), int(value[2]))
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def _load_tray_mask_alpha_64() -> Image.Image | None:
    for p in _candidate_tray_mask_paths():
        try:
            if not p.is_file():
                continue
        except _TRAY_MASK_PATH_ERRORS:
            continue

        try:
            return _render_cairosvg_mask_alpha_64(p)
        except _TRAY_MASK_RASTER_ERRORS:
            pass

        try:
            alpha = _render_simple_svg_mask_alpha_64(p)
            if alpha is not None:
                return alpha
        except _TRAY_MASK_RENDER_ERRORS:
            continue
    return None


def _outline_color_for_theme() -> tuple[int, int, int]:
    # Use a light grey outline instead of near-white so the logo remains legible
    # when the active keyboard/profile color is also white.
    base = (176, 176, 176)
    try:
        prefers_dark = detect_system_prefers_dark()
    except _THEME_DETECTION_ERRORS:
        prefers_dark = None

    # If the system prefers light, invert to a dark outline so it's visible.
    if prefers_dark is False:
        return (255 - base[0], 255 - base[1], 255 - base[2])
    return base


@lru_cache(maxsize=4)
def _tray_k_mask() -> Image.Image | None:
    return _load_tray_mask_alpha_64()


@lru_cache(maxsize=64)
def _create_cached_solid_icon(color: tuple[int, int, int], outline_color: tuple[int, int, int]) -> Image.Image:
    k_mask = _tray_k_mask()
    if k_mask is not None:
        fill = Image.new("RGBA", _ICON_SIZE, color=(*color, 255))
        fill.putalpha(k_mask)

        out = Image.new("RGBA", _ICON_SIZE, color=(0, 0, 0, 0))
        out.alpha_composite(fill)
        return out

    # Fallback: old placeholder keyboard icon.
    img = Image.new("RGBA", _ICON_SIZE, color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rectangle((8, 20, 56, 44), outline=(*color, 255), width=2)
    for row in range(2):
        for col in range(6):
            x = 12 + col * 7
            y = 24 + row * 8
            draw.rectangle(
                (x, y, x + 5, y + 5),
                fill=(*color, 255),
                outline=(*color, 255),
                width=1,
            )

    return img


def clear_cached_solid_icons() -> None:
    _create_cached_solid_icon.cache_clear()
    for cached in (_load_tray_mask_alpha_64, _tray_k_mask):
        clear_cache = getattr(cached, "cache_clear", None)
        if callable(clear_cache):
            clear_cache()


def _scale_cache_key(scale: float) -> int:
    return int(round(float(max(0.0, min(1.0, scale))) * 1000.0))


def create_icon(color: tuple[int, int, int]) -> Image.Image:
    """Create tray icon image."""

    return _create_cached_solid_icon(tuple(color), _outline_color_for_theme())


def _clamp_u8(v: float) -> int:
    return int(max(0, min(255, round(v))))


def _scale_rgb(color: tuple[int, int, int], scale: float) -> tuple[int, int, int]:
    s = float(max(0.0, min(1.0, scale)))
    r, g, b = color
    return (_clamp_u8(r * s), _clamp_u8(g * s), _clamp_u8(b * s))


@lru_cache(maxsize=64)
def _rainbow_gradient_64(phase_q: int) -> Image.Image:
    """Small cached rainbow gradient image (RGBA) used for the 'K' cutout."""

    phase_q = int(max(0, min(63, phase_q)))
    phase = float(phase_q) / 64.0

    w, h = _ICON_SIZE
    img = Image.new("RGBA", _ICON_SIZE, color=(0, 0, 0, 0))
    px = img.load()
    if px is None:
        return img
    for x in range(w):
        for y in range(h):
            progress = ((float(x) / float(max(1, w - 1))) + (float(y) / float(max(1, h - 1)))) / 2.0
            hue = (phase + progress) % 1.0
            rr, gg, bb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            r = int(rr * 255)
            g = int(gg * 255)
            b = int(bb * 255)
            px[x, y] = (r, g, b, 255)
    return img


@lru_cache(maxsize=256)
def _create_cached_rainbow_icon(
    phase_q: int,
    scale_key: int,
    outline_color: tuple[int, int, int],
) -> Image.Image:
    k_mask = _tray_k_mask()
    scale = float(scale_key) / 1000.0

    if k_mask is not None:
        underlay = _rainbow_gradient_64(phase_q).copy()
        if scale != 1.0:
            # Apply brightness scaling to the underlay.
            w, h = underlay.size
            px = underlay.load()
            if px is not None:
                for x in range(w):
                    for y in range(h):
                        r, g, b, a = cast(tuple[int, int, int, int], px[x, y])
                        rr, gg, bb = _scale_rgb((r, g, b), scale)
                        px[x, y] = (rr, gg, bb, a)

        underlay.putalpha(k_mask)
        out = Image.new("RGBA", _ICON_SIZE, color=(0, 0, 0, 0))
        out.alpha_composite(underlay)
        return out

    rr_f, gg_f, bb_f = colorsys.hsv_to_rgb(float(phase_q % 64) / 64.0, 1.0, 1.0)
    return create_icon(_scale_rgb((int(rr_f * 255), int(gg_f * 255), int(bb_f * 255)), scale))


def clear_cached_rainbow_icons() -> None:
    _create_cached_rainbow_icon.cache_clear()
    for cached in (_load_tray_mask_alpha_64, _tray_k_mask):
        clear_cache = getattr(cached, "cache_clear", None)
        if callable(clear_cache):
            clear_cache()


def create_icon_rainbow(*, scale: float = 1.0, phase: float = 0.0) -> Image.Image:
    """Create tray icon where the 'K' cutout is filled with a rainbow gradient."""

    phase_q = int(round((float(phase) % 1.0) * 63.0))
    return _create_cached_rainbow_icon(phase_q, _scale_cache_key(scale), _outline_color_for_theme())


def create_icon_mosaic(
    *,
    colors_flat: tuple[tuple[int, int, int], ...],
    rows: int,
    cols: int,
    scale: float = 1.0,
) -> Image.Image:
    """Create tray icon where the 'K' cutout shows a per-key color mosaic.

    colors_flat is expected to be row-major with length rows*cols.
    """

    k_mask = _tray_k_mask()
    if k_mask is not None:
        r_n = max(1, int(rows))
        c_n = max(1, int(cols))
        expected = r_n * c_n
        if len(colors_flat) != expected:
            # Fall back to a representative color if grid size mismatches.
            base = _coerce_rgb_triplet(colors_flat[0]) if colors_flat else None
            return create_icon(_scale_rgb(base or (255, 0, 128), scale))

        underlay = Image.new("RGBA", _ICON_SIZE, color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(underlay)

        w, h = _ICON_SIZE
        cell_w = float(w) / float(c_n)
        cell_h = float(h) / float(r_n)

        for r in range(r_n):
            y0 = int(round(r * cell_h))
            y1 = int(round((r + 1) * cell_h))
            for c in range(c_n):
                x0 = int(round(c * cell_w))
                x1 = int(round((c + 1) * cell_w))
                rr, gg, bb = colors_flat[(r * c_n) + c]
                cr, cg, cb = _scale_rgb((int(rr), int(gg), int(bb)), scale)
                draw.rectangle((x0, y0, max(x0, x1 - 1), max(y0, y1 - 1)), fill=(cr, cg, cb, 255))

            underlay.putalpha(k_mask)
            out = Image.new("RGBA", _ICON_SIZE, color=(0, 0, 0, 0))
            out.alpha_composite(underlay)
        return out

    # Fallback: pick first cell as representative.
    base = _coerce_rgb_triplet(colors_flat[0]) if colors_flat else None
    return create_icon(_scale_rgb(base or (255, 0, 128), scale))
