from __future__ import annotations

from functools import lru_cache
from io import BytesIO
import importlib
from pathlib import Path

import tkinter as tk


_WINDOW_ICON_SIZE = (64, 64)


def _rasterize_svg_window_icon(path_str: str):
    from PIL import Image  # type: ignore

    cairosvg = importlib.import_module("cairosvg")
    svg2png = getattr(cairosvg, "svg2png")
    png_bytes = svg2png(url=path_str, output_width=_WINDOW_ICON_SIZE[0], output_height=_WINDOW_ICON_SIZE[1])
    with Image.open(BytesIO(png_bytes)) as image:
        return image.convert("RGBA")


def _candidate_logo_paths() -> list[Path]:
    paths: list[Path] = []

    # install.sh installs user icons here.
    try:
        home = Path.home()
        paths.append(home / ".local/share/icons/hicolor/scalable/apps/keyrgb.svg")
        paths.append(home / ".local/share/icons/hicolor/256x256/apps/keyrgb.png")
        paths.append(home / ".local/share/icons/keyrgb.svg")
        paths.append(home / ".local/share/icons/keyrgb.png")
    except Exception:
        pass

    # Repo checkout (and editable installs) typically keep assets/ alongside src/.
    start = Path(__file__).resolve()
    for parent in [start] + list(start.parents):
        for name in ("logo-keyrgb.svg", "logo-keyrgb.png", "legacy/logo-tray-squircle.png"):
            cand = parent / "assets" / name
            if cand not in paths:
                paths.append(cand)

    return paths


def find_keyrgb_logo_path() -> Path | None:
    for p in _candidate_logo_paths():
        try:
            if p.is_file():
                return p
        except Exception:
            continue
    return None


@lru_cache(maxsize=4)
def _load_cached_window_icon_image(path_str: str, mtime_ns: int):
    from PIL import Image  # type: ignore

    if path_str.lower().endswith(".svg"):
        icon = _rasterize_svg_window_icon(path_str)
    else:
        with Image.open(path_str) as image:
            icon = image.convert("RGBA")
    return icon.resize(_WINDOW_ICON_SIZE)


def load_window_icon_image(path: Path):
    stat = path.stat()
    return _load_cached_window_icon_image(str(path), int(stat.st_mtime_ns))


def clear_cached_window_icon_images() -> None:
    _load_cached_window_icon_image.cache_clear()


def apply_keyrgb_window_icon(window: tk.Misc) -> None:
    """Best-effort: set KeyRGB icon for a Tk window.

    Uses the installed SVG/PNG icon or the repo asset fallback.
    Safe to call on any Tk root/toplevel; does nothing on failure.
    """

    try:
        from PIL import ImageTk  # type: ignore

        candidate_paths: list[Path] = []
        preferred_path = find_keyrgb_logo_path()
        if preferred_path is not None:
            candidate_paths.append(preferred_path)
        for candidate_path in _candidate_logo_paths():
            if candidate_path not in candidate_paths:
                candidate_paths.append(candidate_path)

        for logo_path in candidate_paths:
            try:
                img = load_window_icon_image(logo_path)
                photo = ImageTk.PhotoImage(img)

                # Prevent garbage collection.
                setattr(window, "keyrgb_icon_image", photo)

                iconphoto = getattr(window, "iconphoto", None)
                if callable(iconphoto):
                    iconphoto(True, photo)
                return
            except Exception:
                continue
    except Exception:
        return
