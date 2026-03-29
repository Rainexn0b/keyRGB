from __future__ import annotations

import colorsys
from io import BytesIO
from functools import lru_cache
from pathlib import Path
import re
from typing import cast
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw

from src.gui.theme.detect import detect_system_prefers_dark

_ICON_SIZE = (64, 64)
_ICON_INNER_SIZE = (48, 48)
_SVG_PATH_TOKEN_RE = re.compile(r"[MLZmlz]|-?\d+(?:\.\d+)?")


def _candidate_tray_mask_paths() -> list[Path]:
    paths: list[Path] = []

    # Repo checkout (and editable installs) typically keep assets/ alongside src/.
    start = Path(__file__).resolve()
    for parent in [start] + list(start.parents):
        cand = parent / "assets" / "tray-mask.svg"
        if cand not in paths:
            paths.append(cand)

    # Working-directory fallback (useful for some launchers/tests).
    try:
        paths.append(Path.cwd() / "assets" / "tray-mask.svg")
    except Exception:
        pass

    # Support common system install locations so packaged builds (Flatpak/RPM/AppImage)
    # can still find the asset when it's installed to a system directory.
    for sys_cand in (
        Path("/usr/share/keyrgb/assets/tray-mask.svg"),
        Path("/usr/lib/keyrgb/assets/tray-mask.svg"),
        Path("/usr/local/share/keyrgb/assets/tray-mask.svg"),
        Path("/usr/local/lib/keyrgb/assets/tray-mask.svg"),
    ):
        if sys_cand not in paths:
            paths.append(sys_cand)

    return paths


@lru_cache(maxsize=1)
def _load_tray_mask_alpha_64() -> Image.Image | None:
    for p in _candidate_tray_mask_paths():
        try:
            if not p.is_file():
                continue
        except Exception:
            continue

        try:
            from cairosvg import svg2png  # type: ignore

            png_bytes = svg2png(url=str(p), output_width=_ICON_INNER_SIZE[0], output_height=_ICON_INNER_SIZE[1])
            img = Image.open(BytesIO(png_bytes)).convert("RGBA")
            return _center_alpha_mask(img.getchannel("A"))
        except Exception:
            pass

        try:
            alpha = _render_simple_svg_mask_alpha_64(p)
            if alpha is not None:
                return alpha
        except Exception:
            continue
    return None


def _resampling_lanczos() -> int:
    return getattr(getattr(Image, "Resampling", None), "LANCZOS", getattr(Image, "LANCZOS", 1))


def _center_alpha_mask(alpha: Image.Image) -> Image.Image:
    bbox = alpha.getbbox()
    if bbox is None:
        return Image.new("L", _ICON_SIZE, color=0)

    cropped = alpha.crop(bbox)
    src_w, src_h = cropped.size
    if src_w <= 0 or src_h <= 0:
        return Image.new("L", _ICON_SIZE, color=0)

    scale = min(
        float(_ICON_INNER_SIZE[0]) / float(src_w),
        float(_ICON_INNER_SIZE[1]) / float(src_h),
    )
    dst_w = max(1, int(round(src_w * scale)))
    dst_h = max(1, int(round(src_h * scale)))
    inner = cropped.resize((dst_w, dst_h), _resampling_lanczos())  # type: ignore[arg-type]

    out = Image.new("L", _ICON_SIZE, color=0)
    ox = (_ICON_SIZE[0] - dst_w) // 2
    oy = (_ICON_SIZE[1] - dst_h) // 2
    out.paste(inner, (ox, oy))
    return out


def _parse_simple_svg_subpaths(path_data: str) -> list[list[tuple[float, float]]]:
    tokens = _SVG_PATH_TOKEN_RE.findall(path_data)
    subpaths: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    cursor = (0.0, 0.0)
    command: str | None = None
    idx = 0

    while idx < len(tokens):
        token = tokens[idx]
        if token.isalpha():
            next_command = token
            idx += 1
            if next_command in {"Z", "z"}:
                if current:
                    subpaths.append(current)
                    current = []
                command = None
                continue
            if next_command in {"M", "m"} and current:
                subpaths.append(current)
                current = []
            command = next_command
            continue

        if command not in {"M", "L", "m", "l"} or (idx + 1) >= len(tokens):
            return []

        x = float(token)
        y = float(tokens[idx + 1])
        idx += 2

        if command in {"m", "l"}:
            x += cursor[0]
            y += cursor[1]

        cursor = (x, y)
        current.append(cursor)

        if command == "M":
            command = "L"
        elif command == "m":
            command = "l"

    if current:
        subpaths.append(current)

    return [subpath for subpath in subpaths if len(subpath) >= 3]


def _render_simple_svg_mask_alpha_64(path: Path) -> Image.Image | None:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    view_box = str(root.attrib.get("viewBox", "")).strip().split()
    if len(view_box) != 4:
        return None

    vb_x, vb_y, vb_w, vb_h = (float(part) for part in view_box)
    if vb_w <= 0 or vb_h <= 0:
        return None

    path_nodes = root.findall("{http://www.w3.org/2000/svg}path")
    if not path_nodes:
        return None

    render_size = (_ICON_INNER_SIZE[0] * 4, _ICON_INNER_SIZE[1] * 4)
    mask = Image.new("L", render_size, color=0)
    draw = ImageDraw.Draw(mask)
    scale_x = float(render_size[0]) / vb_w
    scale_y = float(render_size[1]) / vb_h

    drew_any = False
    for node in path_nodes:
        path_data = str(node.attrib.get("d", ""))
        for subpath in _parse_simple_svg_subpaths(path_data):
            points = [((x - vb_x) * scale_x, (y - vb_y) * scale_y) for x, y in subpath]
            if len(points) >= 3:
                draw.polygon(points, fill=255)
                drew_any = True

    if not drew_any:
        return None

    return _center_alpha_mask(mask)


def _outline_color_for_theme() -> tuple[int, int, int]:
    # Use a light grey outline instead of near-white so the logo remains legible
    # when the active keyboard/profile color is also white.
    base = (176, 176, 176)
    try:
        prefers_dark = detect_system_prefers_dark()
    except Exception:
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
        hue = (phase + (float(x) / float(max(1, w - 1)))) % 1.0
        rr, gg, bb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        r = int(rr * 255)
        g = int(gg * 255)
        b = int(bb * 255)
        for y in range(h):
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
            base = (255, 0, 128)
            if colors_flat:
                try:
                    base = (colors_flat[0][0], colors_flat[0][1], colors_flat[0][2])
                except Exception:
                    base = (255, 0, 128)
            return create_icon(_scale_rgb(base, scale))

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
    base = (255, 0, 128)
    if colors_flat:
        try:
            base = (colors_flat[0][0], colors_flat[0][1], colors_flat[0][2])
        except Exception:
            base = (255, 0, 128)
    return create_icon(_scale_rgb(base, scale))
