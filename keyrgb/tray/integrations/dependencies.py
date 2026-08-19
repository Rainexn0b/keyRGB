from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from keyrgb.core.runtime.imports import ensure_repo_root_on_sys_path


def load_tray_dependencies():
    """Load runtime dependencies for the tray.

    Prefers imports that work when executed as a proper package, but includes a
    fallback for direct execution / alternate layouts.
    """

    try:
        from keyrgb.core.config import Config
        from keyrgb.core.effects.engine import EffectsEngine
        from keyrgb.core.power.management import PowerManager

        return EffectsEngine, Config, PowerManager
    except ImportError:
        # Fallback for alternate layouts / direct execution.
        with suppress(OSError):
            ensure_repo_root_on_sys_path(Path(__file__))

        from keyrgb.core.config import Config
        from keyrgb.core.effects.engine import EffectsEngine
        from keyrgb.core.power.management import PowerManager

        return EffectsEngine, Config, PowerManager
