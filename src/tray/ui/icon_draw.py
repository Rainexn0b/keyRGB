from __future__ import annotations

from collections import deque
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw

from src.gui.theme.detect import detect_system_prefers_dark


_ICON_SIZE = (64, 64)
_ICON_INNER_SIZE = (56, 56)


def _candidate_tray_logo_paths() -> list[Path]:
    paths: list[Path] = []

    # Repo checkout (and editable installs) typically keep assets/ alongside src/.
    # Adjust path resolution to be relative to this file's location in src/tray/ui/
    # original was src/tray/ui/icon.py, this is src/tray/ui/icon_draw.py, so same dir.
    start = Path(__file__).resolve()
    for parent in [start] + list(start.parents):
        cand = parent / "assets" / "logo-tray.png"
        if cand not in paths:
            paths.append(cand)

    # Working-directory fallback (useful for some launchers/tests).
    try:
        paths.append(Path.cwd() / "assets" / "logo-tray.png")
    except Exception:
        pass

    # Support common system install locations so packaged builds (Flatpak/RPM/AppImage)
    # can still find the asset when it's installed to a system directory.
    for sys_cand in (
        Path("/usr/share/keyrgb/assets/logo-tray.png"),
        Path("/usr/lib/keyrgb/assets/logo-tray.png"),
        Path("/usr/local/share/keyrgb/assets/logo-tray.png"),
        Path("/usr/local/lib/keyrgb/assets/logo-tray.png"),
    ):
        if sys_cand not in paths:
            paths.append(sys_cand)

    return paths


@lru_cache(maxsize=1)
def _load_tray_logo_alpha_64() -> Image.Image | None:
    for p in _candidate_tray_logo_paths():
        try:
            if not p.is_file():
                continue
        except Exception:
            continue

        try:
            img = Image.open(p).convert("RGBA")
            resampling = getattr(getattr(Image, "Resampling", None), "LANCZOS", getattr(Image, "LANCZOS", 1))

            # Keep a small transparent margin so the icon doesn't look like a
            # solid square in the tray (resizing a high-res asset directly to
            # 64×64 tends to eliminate edge transparency).
            inner = img.resize(_ICON_INNER_SIZE, resampling)  # type: ignore[arg-type]
            out = Image.new("RGBA", _ICON_SIZE, color=(0, 0, 0, 0))
            ox = (_ICON_SIZE[0] - _ICON_INNER_SIZE[0]) // 2
            oy = (_ICON_SIZE[1] - _ICON_INNER_SIZE[1]) // 2
            out.alpha_composite(inner, dest=(ox, oy))

            # Return only the alpha channel; we colorize at render time so we can
            # invert the outline color in light mode.
            return out.getchannel("A")
        except Exception:
            continue
    return None


def _outline_color_for_theme() -> tuple[int, int, int]:
    # Default stays as a light outline (optimized for dark trays), matching the
    # historical default of dark mode when detection is unknown.
    base = (235, 235, 235)
    try:
        prefers_dark = detect_system_prefers_dark()
    except Exception:
        prefers_dark = None

    # If the system prefers light, invert to a dark outline so it's visible.
    if prefers_dark is False:
        return (255 - base[0], 255 - base[1], 255 - base[2])
    return base


@lru_cache(maxsize=4)
def _tray_logo_outline(outline_color: tuple[int, int, int]) -> Image.Image | None:
    alpha64 = _load_tray_logo_alpha_64()
    if alpha64 is None:
        return None
    outline = Image.new("RGBA", _ICON_SIZE, color=(*outline_color, 0))
    outline.putalpha(alpha64)
    return outline


@lru_cache(maxsize=1)
def _tray_logo_masks() -> tuple[Image.Image, Image.Image] | None:
    """Return (silhouette_mask, cutout_mask) for the tray logo.

    - silhouette_mask keeps the full outer logo silhouette (including internal holes)
      so we can preserve non-square transparency when needed.
    - cutout_mask isolates internal transparent regions (the "K" cutout), so we can
      place dynamic color only behind the cutout and avoid color bleeding at the
      outer edges of the logo.
    """

    alpha = _load_tray_logo_alpha_64()
    if alpha is None:
        return None

    w, h = alpha.size
    a = list(alpha.getdata())

    def idx(x: int, y: int) -> int:
        return y * w + x

    transparent = [v == 0 for v in a]
    external = [False] * (w * h)
    q: deque[tuple[int, int]] = deque()

    # Seed border pixels.
    for x in range(w):
        for y in (0, h - 1):
            i = idx(x, y)
            if transparent[i] and not external[i]:
                external[i] = True
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            i = idx(x, y)
            if transparent[i] and not external[i]:
                external[i] = True
                q.append((x, y))

    # Flood-fill external transparency.
    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nx < 0 or ny < 0 or nx >= w or ny >= h:
                continue
            i = idx(nx, ny)
            if transparent[i] and not external[i]:
                external[i] = True
                q.append((nx, ny))

    # Silhouette = everything that's *not* external background.
    silhouette_data = [0 if external[i] else 255 for i in range(w * h)]
    silhouette = Image.new("L", (w, h), color=0)
    silhouette.putdata(silhouette_data)

    # Cutout = internal transparent pixels (transparent but not external background).
    cutout_data = [255 if (transparent[i] and not external[i]) else 0 for i in range(w * h)]
    cutout = Image.new("L", (w, h), color=0)
    cutout.putdata(cutout_data)

    return (silhouette, cutout)


def create_icon(color: tuple[int, int, int]) -> Image.Image:
    """Create tray icon image."""

    logo = _tray_logo_outline(_outline_color_for_theme())
    masks = _tray_logo_masks()
    if logo is not None and masks is not None:
        _silhouette_mask, cutout_mask = masks

        # Only show dynamic color through the internal cutout (the transparent "K").
        # This avoids tinted halos at the outer logo edges caused by anti-aliasing.
        underlay = Image.new("RGBA", _ICON_SIZE, color=(*color, 255))
        underlay.putalpha(cutout_mask)

        out = underlay.copy()
        out.alpha_composite(logo)
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
