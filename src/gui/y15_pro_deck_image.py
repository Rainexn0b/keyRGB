"""Legacy import path for the historical Y15 Pro naming.

Internal code now uses `src.gui.reference_deck_image`.
"""

from __future__ import annotations

from typing import Optional

from PIL import Image

from src.gui.reference_deck_image import load_reference_deck_image


def load_y15_pro_deck_image(*, profile_name: str | None) -> Optional[Image.Image]:
    return load_reference_deck_image(profile_name=profile_name)
