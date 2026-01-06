"""Effect selection logic for the tray application.

This module implements a simplified HW/SW mode lockdown:
- Hardware mode: uniform color + hardware effects (no per-key)
- Software mode: per-key colors + software effects

When switching modes, the appropriate state is set up automatically.
"""

from __future__ import annotations

import logging
from typing import Any

from src.core.effects.catalog import HW_EFFECTS_SET as HW_EFFECTS
from src.core.effects.catalog import SW_EFFECTS_SET as SW_EFFECTS
from src.core.effects.catalog import normalize_effect_name

logger = logging.getLogger(__name__)

profiles: Any

try:
    # Module-level import so tests (and callers) can monkeypatch `profiles`.
    from src.core.profile import profiles as profiles
except Exception:  # pragma: no cover
    profiles = None


def _load_per_key_colors_from_profile(config) -> dict:
    """Load per-key colors from the active profile.

    Returns the loaded colors dict, or empty dict on failure.
    """
    try:
        prof = profiles
        if prof is None:
            from src.core.profile import profiles as prof  # type: ignore[no-redef]

        active = prof.get_active_profile()
        colors = prof.load_per_key_colors(active)
        return dict(colors) if colors else {}
    except Exception as exc:
        logger.debug("Failed to load per-key colors from profile: %s", exc)
        return {}


def _ensure_config_per_key_colors_loaded(config) -> None:
    """Ensure config.per_key_colors has a value, if possible.

    Used when switching into per-key effects so the keyboard isn't left blank.
    This is a compatibility shim for existing code that calls this function.
    """
    try:
        existing = dict(getattr(config, "per_key_colors", {}) or {})
    except Exception:
        existing = {}

    if existing:
        return

    colors = _load_per_key_colors_from_profile(config)
    if colors:
        config.per_key_colors = colors


def _ensure_software_mode(tray) -> None:
    """Ensure we're in software mode.

    Software mode can work with either:
    1. Per-key colors from a profile (if per_key_colors exist)
    2. Uniform color (loose state - no profile needed)

    This allows software effects like reactive typing to work with
    the current uniform color without requiring a profile.
    """
    config = tray.config

    # Get existing per-key colors (if any)
    existing = dict(getattr(config, "per_key_colors", {}) or {})

    # Sync to engine - may be None for uniform mode
    try:
        tray.engine.per_key_colors = dict(existing) if existing else None
    except Exception:
        pass

    # Also sync a per-key base brightness when a per-key backdrop is active.
    # This allows reactive typing effects to keep the backdrop dim while
    # rendering pulses/highlights brighter.
    try:
        tray.engine.per_key_brightness = int(getattr(config, "perkey_brightness", None) or 0) if existing else None
    except Exception:
        try:
            tray.engine.per_key_brightness = None
        except Exception:
            pass


def _ensure_hardware_mode(tray) -> None:
    """Ensure we're in hardware mode (clear per-key state).

    Hardware effects and uniform colors don't use per-key state.
    """
    try:
        tray.engine.per_key_colors = None
    except Exception:
        pass
    try:
        tray.engine.per_key_brightness = None
    except Exception:
        pass


def apply_effect_selection(tray, *, effect_name: str) -> None:
    """Apply an effect selection coming from the tray menu.

    This is the main entry point for effect changes. It handles:
    - Mode detection (HW vs SW)
    - State setup (per-key colors for SW mode)
    - Effect activation
    """

    caps = getattr(tray, "backend_caps", None)
    per_key_supported = bool(getattr(caps, "per_key", True)) if caps is not None else True
    hw_effects_supported = bool(getattr(caps, "hardware_effects", True)) if caps is not None else True

    try:
        effect_name = normalize_effect_name(effect_name)
    except Exception:
        effect_name = "none"

    # === FORCE MODE SWITCHES ===

    # Force hardware uniform color mode (used by the tray's "Hardware Color" entry
    # and "None (use uniform color)" under Hardware Effects). This must override
    # any existing per-key state so HW effects unlock and SW effects lock.
    if effect_name in {"hw_uniform", "hardware_uniform"}:
        tray.engine.stop()
        try:
            tray.config.per_key_colors = {}
        except Exception:
            pass

        tray.config.effect = "none"
        _ensure_hardware_mode(tray)
        with tray.engine.kb_lock:
            tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
        tray.is_off = False
        return

    # === HANDLE SPECIAL CASES ===

    # "none" or "stop" -> go to static color (respects current mode)
    if effect_name in {"none", "stop"}:
        tray.engine.stop()

        # Check if we have per-key colors (software mode)
        per_key = dict(getattr(tray.config, "per_key_colors", {}) or {})
        if per_key and per_key_supported:
            # Stay in software mode with static per-key
            tray.config.effect = "perkey"
            _ensure_software_mode(tray)
            tray._start_current_effect()
        else:
            # Hardware mode with uniform color
            tray.config.effect = "none"
            _ensure_hardware_mode(tray)
            with tray.engine.kb_lock:
                tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)

        tray.is_off = False
        return

    # "perkey" -> switch to software mode with static per-key colors
    if effect_name == "perkey":
        if not per_key_supported:
            # Fall back to hardware uniform
            tray.engine.stop()
            tray.config.effect = "none"
            _ensure_hardware_mode(tray)
            with tray.engine.kb_lock:
                tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
            tray.is_off = False
            return

        # Load per-key colors from profile for static per-key mode
        colors = _load_per_key_colors_from_profile(tray.config)
        if colors:
            tray.config.per_key_colors = colors

        _ensure_software_mode(tray)
        tray.config.effect = "perkey"
        tray._start_current_effect()
        tray.is_off = False
        return

    # === HARDWARE EFFECTS ===
    if effect_name in HW_EFFECTS:
        if not hw_effects_supported:
            # Fall back to uniform color
            tray.engine.stop()
            tray.config.effect = "none"
            _ensure_hardware_mode(tray)
            with tray.engine.kb_lock:
                tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
            tray.is_off = False
            return

        # Switch to hardware mode
        try:
            tray.config.per_key_colors = {}
        except Exception:
            pass
        _ensure_hardware_mode(tray)
        tray.config.effect = effect_name
        tray._start_current_effect()
        tray.is_off = False
        return

    # === SOFTWARE EFFECTS ===
    if effect_name in SW_EFFECTS:
        # Software effects work with both per-key colors (from profile)
        # and uniform colors (loose mode). Don't force profile loading.
        _ensure_software_mode(tray)
        tray.config.effect = effect_name
        tray._start_current_effect()
        tray.is_off = False
        return

    # Unknown effect -> treat as none
    logger.warning("Unknown effect: %s, treating as 'none'", effect_name)
    tray.engine.stop()
    tray.config.effect = "none"
    with tray.engine.kb_lock:
        tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
    tray.is_off = False
