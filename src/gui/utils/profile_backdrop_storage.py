from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image

from src.core.profile import profiles
from src.core.profile._backdrop import BACKDROP_MODE_CUSTOM, BACKDROP_MODE_NONE, normalize_backdrop_mode
from src.core.resources.layout import BASE_IMAGE_SIZE
from src.gui.utils.backdrop_image_cache import backdrop_image_candidates, load_cached_backdrop_image


def load_backdrop_image(profile_name: str, *, backdrop_mode: str | None = None) -> Optional[Image.Image]:
    """Load backdrop image (RGBA) for a profile, or return None."""

    mode = normalize_backdrop_mode(
        profiles.load_backdrop_mode(profile_name) if backdrop_mode is None else backdrop_mode
    )
    if mode == BACKDROP_MODE_NONE:
        return None

    if mode == BACKDROP_MODE_CUSTOM:
        custom_path = profiles.paths_for(profile_name).backdrop_image
        custom_image = load_cached_backdrop_image(candidates=(custom_path,))
        if custom_image is not None:
            return custom_image
        return None

    return load_cached_backdrop_image(candidates=backdrop_image_candidates(profile_name=None))


def save_backdrop_image(*, profile_name: str, source_path: str | Path) -> None:
    """Save a user-selected image as the profile backdrop (canonical size)."""

    img = Image.open(source_path).convert("RGBA")
    img = img.resize(BASE_IMAGE_SIZE, Image.Resampling.LANCZOS)

    dst = profiles.paths_for(profile_name).backdrop_image
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, format="PNG")


def reset_backdrop_image(profile_name: str) -> None:
    """Delete the per-profile backdrop image if it exists."""

    path = profiles.paths_for(profile_name).backdrop_image
    if path.exists():
        path.unlink()
