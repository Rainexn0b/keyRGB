from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image

from src.core.resources.layout import BASE_IMAGE_SIZE
from src.core import profiles


def _default_backdrop_candidates(profile_name: str) -> list[Path]:
    return [
        profiles.paths_for(profile_name).backdrop_image,
        # Repo / dev-run fallback.
        Path.cwd() / "assets" / "y15-pro-deck.png",
    ]


def load_backdrop_image(profile_name: str) -> Optional[Image.Image]:
    """Load backdrop image (RGBA) for a profile, or return None."""

    for path in _default_backdrop_candidates(profile_name):
        if path.exists():
            return Image.open(path).convert("RGBA")
    return None


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
