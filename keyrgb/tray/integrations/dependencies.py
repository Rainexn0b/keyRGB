from __future__ import annotations

from keyrgb.core.config import Config
from keyrgb.core.effects.engine import EffectsEngine
from keyrgb.core.power.management import PowerManager


def load_tray_dependencies():
    """Load runtime dependencies for the tray."""

    return EffectsEngine, Config, PowerManager
