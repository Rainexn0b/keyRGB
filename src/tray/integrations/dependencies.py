from __future__ import annotations

import sys
from contextlib import suppress
from pathlib import Path

from src.core.runtime.imports import ensure_repo_root_on_sys_path


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
    except ImportError:
        # Fallback for alternate layouts / direct execution.
        with suppress(Exception):
            ensure_repo_root_on_sys_path(Path(__file__))

        from src.legacy.effects import EffectsEngine
        from src.legacy.config import Config
        from src.core.power import PowerManager

        return EffectsEngine, Config, PowerManager
