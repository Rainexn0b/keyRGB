from __future__ import annotations

from typing import Optional

from PIL import Image

from src.core.profile import profiles
from src.core.profile._backdrop import BACKDROP_MODE_CUSTOM, BACKDROP_MODE_NONE, normalize_backdrop_mode
from src.gui.utils.backdrop_image_cache import backdrop_image_candidates, load_cached_backdrop_image


def load_reference_deck_image(*, profile_name: str | None) -> Optional[Image.Image]:
    """Load the reference deck image used as a backdrop for overlay-based UIs.

    Resolution order:
    1) Per-profile custom backdrop (if present)
    2) Repo checkout fallback: `assets/y15-pro-deck.png` (historical reference image)
    3) Working-directory fallback: `assets/y15-pro-deck.png`

    Returns a PIL Image, or None if no candidate is available/readable.
    """

    mode = profiles.load_backdrop_mode(profile_name) if profile_name else "builtin"
    mode = normalize_backdrop_mode(mode)
    if mode == BACKDROP_MODE_NONE:
        return None

    if mode == BACKDROP_MODE_CUSTOM and profile_name:
        custom_path = profiles.paths_for(profile_name).backdrop_image
        custom_image = load_cached_backdrop_image(candidates=(custom_path,))
        if custom_image is not None:
            return custom_image

    return load_cached_backdrop_image(
        candidates=backdrop_image_candidates(profile_name=None, include_cwd_fallback=True)
    )
