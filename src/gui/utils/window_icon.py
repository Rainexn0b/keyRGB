from __future__ import annotations

from functools import lru_cache
from io import BytesIO
import importlib
import logging
from pathlib import Path

import tkinter as tk


logger = logging.getLogger(__name__)


_WINDOW_ICON_SIZE = (64, 64)
_SVG_RASTERIZER_FALLBACK_ERRORS = (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError)
_HOME_DISCOVERY_ERRORS = (OSError, RuntimeError)
_LOGO_PATH_PROBE_ERRORS = (OSError, RuntimeError)
_WINDOW_ICON_LOAD_ERRORS = (AttributeError, ImportError, OSError, RuntimeError, tk.TclError, TypeError, ValueError)
_WINDOW_ICON_APPLY_ERRORS = _WINDOW_ICON_LOAD_ERRORS + (LookupError,)


def _rasterize_svg_window_icon_with_cairosvg(path_str: str):
    from PIL import Image  # type: ignore

    cairosvg = importlib.import_module("cairosvg")
    svg2png = getattr(cairosvg, "svg2png")
    png_bytes = svg2png(url=path_str, output_width=_WINDOW_ICON_SIZE[0], output_height=_WINDOW_ICON_SIZE[1])
    with Image.open(BytesIO(png_bytes)) as image:
        return image.convert("RGBA")


def _rasterize_svg_window_icon_with_gdkpixbuf(path_str: str):
    from PIL import Image  # type: ignore

    gi = importlib.import_module("gi")
    require_version = getattr(gi, "require_version", None)
    if callable(require_version):
        require_version("GdkPixbuf", "2.0")

    from gi.repository import GdkPixbuf  # type: ignore

    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
        path_str,
        _WINDOW_ICON_SIZE[0],
        _WINDOW_ICON_SIZE[1],
        True,
    )
    ok, png_bytes = pixbuf.save_to_bufferv("png", [], [])
    if not ok:
        raise RuntimeError(f"Failed to rasterize SVG icon via GdkPixbuf: {path_str}")
    with Image.open(BytesIO(bytes(png_bytes))) as image:
        return image.convert("RGBA")


def _rasterize_svg_window_icon(path_str: str):
    last_exc: Exception | None = None
    for loader in (
        _rasterize_svg_window_icon_with_cairosvg,
        _rasterize_svg_window_icon_with_gdkpixbuf,
    ):
        try:
            return loader(path_str)
        except _SVG_RASTERIZER_FALLBACK_ERRORS as exc:
            last_exc = exc

    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"No SVG window icon rasterizer available for: {path_str}")


def _repo_candidate_logo_paths() -> list[Path]:
    paths: list[Path] = []

    # Repo checkouts and editable installs should prefer their local assets so
    # stale user-installed icons cannot override in-tree branding updates.
    start = Path(__file__).resolve()
    for parent in [start] + list(start.parents):
        for name in ("logo-keyrgb.svg", "logo-keyrgb.png", "legacy/logo-tray-squircle.png"):
            cand = parent / "assets" / name
            if cand not in paths:
                paths.append(cand)

    return paths


def _candidate_logo_paths() -> list[Path]:
    paths: list[Path] = []

    for path in _repo_candidate_logo_paths():
        if path not in paths:
            paths.append(path)

    # install.sh installs user icons here.
    try:
        home = Path.home()
        for candidate in (
            home / ".local/share/icons/hicolor/scalable/apps/keyrgb.svg",
            home / ".local/share/icons/hicolor/256x256/apps/keyrgb.png",
            home / ".local/share/icons/keyrgb.svg",
            home / ".local/share/icons/keyrgb.png",
        ):
            if candidate not in paths:
                paths.append(candidate)
    except _HOME_DISCOVERY_ERRORS:
        pass

    return paths


def find_keyrgb_logo_path() -> Path | None:
    for p in _candidate_logo_paths():
        try:
            if p.is_file():
                return p
        except _LOGO_PATH_PROBE_ERRORS:
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
            except _WINDOW_ICON_LOAD_ERRORS:
                continue
    except _WINDOW_ICON_APPLY_ERRORS as exc:
        logger.exception("Failed to apply KeyRGB window icon", exc_info=exc)
        return
