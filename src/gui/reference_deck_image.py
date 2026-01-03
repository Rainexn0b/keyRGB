from __future__ import annotations

import logging
import os
from typing import Optional

from PIL import Image

from src.core.logging_utils import log_throttled
from src.core.profile import profiles

logger = logging.getLogger(__name__)


def load_reference_deck_image(*, profile_name: str | None) -> Optional[Image.Image]:
    """Load the reference deck image used as a backdrop for overlay-based UIs.

    Resolution order:
    1) Per-profile custom backdrop (if present)
    2) Repo checkout fallback: `assets/y15-pro-deck.png` (historical reference image)
    3) Working-directory fallback: `assets/y15-pro-deck.png`

    Returns a PIL Image, or None if no candidate is available/readable.
    """

    candidates: list[str] = []

    try:
        prof = (profile_name or "").strip()
        if prof:
            p = profiles.paths_for(prof).backdrop_image
            candidates.append(str(p))
    except Exception as exc:
        log_throttled(
            logger,
            "gui.reference_deck_image.profile_backdrop",
            interval_s=120,
            level=logging.DEBUG,
            msg="Failed to resolve per-profile backdrop image",
            exc=exc,
        )

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    candidates.append(os.path.join(repo_root, "assets", "y15-pro-deck.png"))

    candidates.append(os.path.join(os.getcwd(), "assets", "y15-pro-deck.png"))

    for path in candidates:
        try:
            if os.path.exists(path):
                return Image.open(path)
        except OSError as exc:
            log_throttled(
                logger,
                "gui.reference_deck_image.open_failed",
                interval_s=120,
                level=logging.DEBUG,
                msg=f"Failed to open deck image: {path}",
                exc=exc,
            )
            continue

    return None
