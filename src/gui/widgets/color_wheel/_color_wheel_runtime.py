from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, TypeVar


ColorRGB = tuple[int, int, int]
_PhotoImageT = TypeVar("_PhotoImageT")


class _StyleProtocol(Protocol):
    def lookup(self, name: str, option: str) -> str: ...


class _ThemeBackgroundWidget(Protocol):
    def cget(self, option: str) -> object: ...


class _PhotoImageFactory(Protocol[_PhotoImageT]):
    def __call__(self, *, file: str) -> _PhotoImageT: ...


def resolve_theme_bg_hex(
    widget: _ThemeBackgroundWidget,
    *,
    style_factory: Callable[[], _StyleProtocol],
    style_errors: tuple[type[Exception], ...],
    widget_bg_errors: tuple[type[Exception], ...],
    default_hex: str = "#2b2b2b",
) -> str:
    """Best-effort resolve a background color that matches ttk theme."""

    try:
        style = style_factory()
        bg = style.lookup("TFrame", "background") or style.lookup(".", "background")
        if bg:
            return str(bg)
    except style_errors:
        pass

    try:
        bg = str(widget.cget("background"))
        if bg:
            return bg
    except widget_bg_errors:
        pass

    return default_hex


def load_wheel_photo_image(
    *,
    size: int,
    bg_rgb: ColorRGB,
    center_size: int,
    wheel_cache_path_fn: Callable[..., Path],
    build_wheel_ppm_bytes_fn: Callable[..., bytes],
    write_bytes_atomic_fn: Callable[[Path, bytes], None],
    photo_image_factory: _PhotoImageFactory[_PhotoImageT],
    unlink_fn: Callable[[str], None],
) -> _PhotoImageT:
    wheel_path = wheel_cache_path_fn(size=size, bg_rgb=bg_rgb, center_size=center_size)
    ppm_bytes: bytes | None = None

    try:
        cache_ready = wheel_path.exists() and wheel_path.stat().st_size >= 16
    except OSError:
        cache_ready = False

    if not cache_ready:
        ppm_bytes = build_wheel_ppm_bytes_fn(size=size, bg_rgb=bg_rgb, center_size=center_size)
        try:
            wheel_path.parent.mkdir(parents=True, exist_ok=True)
            write_bytes_atomic_fn(wheel_path, ppm_bytes)
            cache_ready = wheel_path.stat().st_size >= 16
        except OSError:
            cache_ready = False

    if cache_ready:
        return photo_image_factory(file=str(wheel_path))

    if ppm_bytes is None:
        ppm_bytes = build_wheel_ppm_bytes_fn(size=size, bg_rgb=bg_rgb, center_size=center_size)
    return _load_wheel_photo_image_from_temp(
        ppm_bytes,
        photo_image_factory=photo_image_factory,
        unlink_fn=unlink_fn,
    )


def _load_wheel_photo_image_from_temp(
    ppm_bytes: bytes,
    *,
    photo_image_factory: _PhotoImageFactory[_PhotoImageT],
    unlink_fn: Callable[[str], None],
) -> _PhotoImageT:
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="keyrgb_color_wheel_", suffix=".ppm", delete=False) as handle:
            handle.write(ppm_bytes)
            tmp_path = handle.name
        return photo_image_factory(file=tmp_path)
    finally:
        if tmp_path:
            try:
                unlink_fn(tmp_path)
            except OSError:
                pass
