from __future__ import annotations

import logging

from src.core.backends.registry import select_backend


def load_ite_dimensions() -> tuple[int, int]:
    """Load keyboard matrix dimensions.

    Historically this was ITE-specific. It now routes through the backend
    registry so future vendors/controllers can provide their own dimensions.

    Falls back to a common default if anything goes wrong.
    """

    logger = logging.getLogger(__name__)

    try:
        backend = select_backend()
        if backend is None:
            return 6, 21
        r, c = backend.dimensions()
        return int(r), int(c)
    except Exception as exc:
        logger.debug("Falling back to default keyboard dimensions: %s", exc)
        return 6, 21
