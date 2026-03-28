from __future__ import annotations

from typing import Optional

from PIL import Image

from src.gui.utils.backdrop_image_cache import backdrop_image_candidates, load_cached_backdrop_image


def load_reference_deck_image(*, profile_name: str | None) -> Optional[Image.Image]:
    """Load the reference deck image used as a backdrop for overlay-based UIs.

    Resolution order:
    1) Per-profile custom backdrop (if present)
    2) Repo checkout fallback: `assets/y15-pro-deck.png` (historical reference image)
    3) Working-directory fallback: `assets/y15-pro-deck.png`

    Returns a PIL Image, or None if no candidate is available/readable.
    """

    return load_cached_backdrop_image(
        candidates=backdrop_image_candidates(profile_name=profile_name, include_cwd_fallback=True)
    )
