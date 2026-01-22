#!/usr/bin/env python3
"""KeyRGB Effects Engine.

This module intentionally stays small and composes the engine from mixins.
"""

from __future__ import annotations

from src.core.effects.catalog import (
    ALL_EFFECTS as _ALL_EFFECTS,
    HW_EFFECTS as _HW_EFFECTS,
    SW_EFFECTS as _SW_EFFECTS,
)
from src.core.effects.engine_brightness import _EngineBrightness
from src.core.effects.engine_core import _EngineCore
from src.core.effects.engine_start import _EngineStart


class EffectsEngine(_EngineCore, _EngineBrightness, _EngineStart):
    """RGB effects engine with hardware and custom effects."""

    # Canonical effect lists are defined in src.core.effects.catalog.
    HW_EFFECTS = _HW_EFFECTS
    SW_EFFECTS = _SW_EFFECTS
    ALL_EFFECTS = _ALL_EFFECTS

    def __init__(self):
        super().__init__()
