from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable

from PIL import Image

from src.core.profile import profiles
from src.core.runtime.imports import repo_root_from


_BACKDROP_CANDIDATE_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


def backdrop_image_candidates(*, profile_name: str | None, include_cwd_fallback: bool = False) -> tuple[Path, ...]:
    paths: list[Path] = []

    try:
        prof = (profile_name or "").strip()
        if prof:
            paths.append(profiles.paths_for(prof).backdrop_image)
    except _BACKDROP_CANDIDATE_ERRORS:
        pass

    repo_root = repo_root_from(__file__)
    paths.append(repo_root / "assets" / "y15-pro-deck.png")

    if include_cwd_fallback:
        try:
            paths.append(Path.cwd() / "assets" / "y15-pro-deck.png")
        except OSError:
            pass

    unique_paths: list[Path] = []
    for path in paths:
        if path not in unique_paths:
            unique_paths.append(path)
    return tuple(unique_paths)


@lru_cache(maxsize=8)
def _load_cached_rgba_image(path_str: str, mtime_ns: int) -> Image.Image:
    with Image.open(path_str) as image:
        return image.convert("RGBA")


def load_cached_backdrop_image(*, candidates: Iterable[Path]) -> Image.Image | None:
    for path in candidates:
        try:
            if not path.is_file():
                continue
            stat = path.stat()
            return _load_cached_rgba_image(str(path), int(stat.st_mtime_ns))
        except OSError:
            continue
    return None


def clear_cached_backdrop_images() -> None:
    _load_cached_rgba_image.cache_clear()
