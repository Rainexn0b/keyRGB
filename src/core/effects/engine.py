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
from src.core.effects.engine_support import _EngineBrightness, _EngineCore, _EngineStart


class EffectsEngine(_EngineCore, _EngineBrightness, _EngineStart):
    """RGB effects engine with hardware and custom effects."""

    # Canonical effect lists are defined in src.core.effects.catalog.
    HW_EFFECTS = _HW_EFFECTS
    SW_EFFECTS = _SW_EFFECTS
    ALL_EFFECTS = _ALL_EFFECTS

    def __init__(self, *, backend=None):
        super().__init__(backend=backend)
