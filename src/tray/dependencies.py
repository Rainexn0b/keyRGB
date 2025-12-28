from __future__ import annotations

import sys
from contextlib import suppress
from pathlib import Path


def load_tray_dependencies():
    """Load runtime dependencies for the tray.

    Prefers imports that work when executed as a proper package, but includes a
    fallback for direct execution / alternate layouts.
    """

    try:
        from src.legacy.effects import EffectsEngine
        from src.legacy.config import Config
        from src.core.power import PowerManager

        return EffectsEngine, Config, PowerManager
    except Exception:
        with suppress(Exception):
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

        from src.legacy.effects import EffectsEngine
        from src.legacy.config import Config
        from src.core.power import PowerManager

        return EffectsEngine, Config, PowerManager
