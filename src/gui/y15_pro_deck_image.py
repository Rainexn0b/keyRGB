from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PIL import Image

from src.core import profiles


def load_y15_pro_deck_image(*, profile_name: str | None) -> Optional[Image.Image]:
    """Load the Y15 Pro deck image used as a backdrop for overlay-based UIs.

    Resolution order:
    1) Per-profile custom backdrop (if present)
    2) Repo checkout fallback: `assets/y15-pro-deck.png`
    3) Working-directory fallback: `assets/y15-pro-deck.png`

    Returns a PIL Image, or None if no candidate is available/readable.
    """

    candidates: list[str] = []

    try:
        prof = (profile_name or "").strip()
        if prof:
            p = profiles.paths_for(prof).backdrop_image
            candidates.append(str(p))
    except Exception:
        pass

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    candidates.append(os.path.join(repo_root, "assets", "y15-pro-deck.png"))

    candidates.append(os.path.join(os.getcwd(), "assets", "y15-pro-deck.png"))

    for path in candidates:
        try:
            if os.path.exists(path):
                return Image.open(path)
        except Exception:
            continue

    return None
