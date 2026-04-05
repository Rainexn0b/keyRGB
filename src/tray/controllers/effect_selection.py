"""Effect selection logic for the tray application.

This module implements a simplified HW/SW mode lockdown:
- Hardware mode: uniform color + hardware effects (no per-key)
- Software mode: per-key colors + software effects

When switching modes, the appropriate state is set up automatically.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Protocol, cast

from src.core.effects.catalog import SW_EFFECTS_SET as SW_EFFECTS
from src.core.effects.catalog import is_backend_hardware_effect
from src.core.effects.catalog import is_forced_hardware_effect
from src.core.effects.catalog import normalize_effect_name
from src.core.effects.catalog import strip_effect_namespace
from src.core.utils.exceptions import is_permission_denied
from src.core.utils.safe_attrs import safe_int_attr
from src.tray.protocols import LightingTrayProtocol
from src.tray.controllers.software_target_controller import restore_secondary_software_targets
from src.tray.controllers.software_target_controller import software_effect_target_routes_aux_devices

logger = logging.getLogger(__name__)

_PROFILE_LOAD_RECOVERABLE_EXCEPTIONS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


class _BackendCapsProtocol(Protocol):
    per_key: bool
    hardware_effects: bool


class _EffectSelectionTrayProtocol(LightingTrayProtocol, Protocol):
    backend: object | None
    backend_caps: _BackendCapsProtocol | None

    def _start_current_effect(self, **kwargs: object) -> None: ...


class _ProfilesApi(Protocol):
    def get_active_profile(self) -> str: ...

    def load_per_key_colors(self, profile_name: str): ...


profiles: object | None

try:
    # Module-level import so tests (and callers) can monkeypatch `profiles`.
    from src.core.profile import profiles as profiles
except ImportError:  # pragma: no cover
    profiles = None


def _set_attr_best_effort(obj: object, name: str, value: object) -> bool:
    try:
        setattr(obj, name, value)
    except (AttributeError, TypeError, ValueError):
        return False
    return True


def _load_per_key_colors_from_profile(config) -> dict:
    """Load per-key colors from the active profile.

    Returns the loaded colors dict, or empty dict on failure.
    """
    prof = profiles
    if prof is None:
        try:
            from src.core.profile import profiles as prof  # type: ignore[no-redef]
        except ImportError:
            logger.debug("Profile API unavailable while loading per-key colors", exc_info=True)
            return {}

    api = cast(_ProfilesApi, prof)
    get_active_profile = getattr(api, "get_active_profile", None)
    load_per_key_colors = getattr(api, "load_per_key_colors", None)
    if not callable(get_active_profile) or not callable(load_per_key_colors):
        logger.debug("Profile API unavailable while loading per-key colors")
        return {}

    try:
        active = get_active_profile()
        colors = load_per_key_colors(active)
        return dict(colors) if colors else {}
    except _PROFILE_LOAD_RECOVERABLE_EXCEPTIONS:
        logger.debug("Failed to load per-key colors from profile", exc_info=True)
        return {}


def _config_per_key_colors_ref(config) -> Mapping[object, object] | None:
    try:
        colors = getattr(config, "per_key_colors", None)
    except AttributeError:
        return None
    if isinstance(colors, Mapping) and colors:
        return colors
    return None


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
    existing = _config_per_key_colors_ref(config)

    # Sync to engine - may be None for uniform mode
    _set_attr_best_effort(tray.engine, "per_key_colors", existing)

    # Also sync a per-key base brightness when a per-key backdrop is active.
    # This allows reactive typing effects to keep the backdrop dim while
    # rendering pulses/highlights brighter.
    per_key_brightness = safe_int_attr(config, "perkey_brightness", default=0) if existing else None
    if not _set_attr_best_effort(tray.engine, "per_key_brightness", per_key_brightness):
        _set_attr_best_effort(tray.engine, "per_key_brightness", None)


def _ensure_hardware_mode(tray) -> None:
    """Ensure we're in hardware mode (clear per-key state).

    Hardware effects and uniform colors don't use per-key state.
    """
    _set_attr_best_effort(tray.engine, "per_key_colors", None)
    _set_attr_best_effort(tray.engine, "per_key_brightness", None)


def apply_effect_selection(tray: LightingTrayProtocol, *, effect_name: str) -> None:
    """Apply an effect selection coming from the tray menu.

    This is the main entry point for effect changes. It handles:
    - Mode detection (HW vs SW)
    - State setup (per-key colors for SW mode)
    - Effect activation
    """

    try:
        effect_tray = cast(_EffectSelectionTrayProtocol, tray)

        caps = getattr(effect_tray, "backend_caps", None)
        per_key_supported = bool(getattr(caps, "per_key", True)) if caps is not None else True
        hw_effects_supported = bool(getattr(caps, "hardware_effects", True)) if caps is not None else True

        try:
            effect_name = normalize_effect_name(effect_name)
        except (AttributeError, TypeError, ValueError):
            effect_name = "none"

        base_effect_name = strip_effect_namespace(effect_name)

        # === FORCE MODE SWITCHES ===

        # Force hardware uniform color mode (used by the tray's static-mode action
        # and the uniform color picker entry).
        if effect_name in {"hw_uniform", "hardware_uniform"}:
            tray.engine.stop()
            _set_attr_best_effort(tray.config, "per_key_colors", {})

            tray.config.effect = "none"
            _ensure_hardware_mode(tray)
            with tray.engine.kb_lock:
                tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
            if software_effect_target_routes_aux_devices(tray):
                restore_secondary_software_targets(tray)
            tray.is_off = False
            return

        # === HANDLE SPECIAL CASES ===

        # "none" or "stop" -> go to static color (respects current mode)
        if effect_name in {"none", "stop"}:
            tray.engine.stop()

            per_key = _config_per_key_colors_ref(tray.config)
            if per_key and per_key_supported:
                tray.config.effect = "perkey"
                _ensure_software_mode(tray)
                effect_tray._start_current_effect()
            else:
                tray.config.effect = "none"
                _ensure_hardware_mode(tray)
                with tray.engine.kb_lock:
                    tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
                if software_effect_target_routes_aux_devices(tray):
                    restore_secondary_software_targets(tray)

            tray.is_off = False
            return

        # "perkey" -> switch to software mode with static per-key colors
        if effect_name == "perkey":
            if not per_key_supported:
                tray.engine.stop()
                tray.config.effect = "none"
                _ensure_hardware_mode(tray)
                with tray.engine.kb_lock:
                    tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
                if software_effect_target_routes_aux_devices(tray):
                    restore_secondary_software_targets(tray)
                tray.is_off = False
                return

            colors = _load_per_key_colors_from_profile(tray.config)
            if colors:
                tray.config.per_key_colors = colors

            _ensure_software_mode(tray)
            tray.config.effect = "perkey"
            effect_tray._start_current_effect()
            tray.is_off = False
            return

        # === HARDWARE EFFECTS ===
        if is_backend_hardware_effect(effect_name, getattr(effect_tray, "backend", None)):
            if not hw_effects_supported:
                tray.engine.stop()
                tray.config.effect = "none"
                _ensure_hardware_mode(tray)
                with tray.engine.kb_lock:
                    tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
                if software_effect_target_routes_aux_devices(tray):
                    restore_secondary_software_targets(tray)
                tray.is_off = False
                return

            _set_attr_best_effort(tray.config, "per_key_colors", {})
            _ensure_hardware_mode(tray)
            tray.config.effect = effect_name if is_forced_hardware_effect(effect_name) else base_effect_name
            effect_tray._start_current_effect()
            tray.is_off = False
            return

        # === SOFTWARE EFFECTS ===
        if base_effect_name in SW_EFFECTS and not is_forced_hardware_effect(effect_name):
            _ensure_software_mode(tray)
            tray.config.effect = base_effect_name
            effect_tray._start_current_effect()
            tray.is_off = False
            return

        # Unknown effect -> treat as none
        logger.warning("Unknown effect: %s, treating as 'none'", effect_name)
        tray.engine.stop()
        tray.config.effect = "none"
        with tray.engine.kb_lock:
            tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
        tray.is_off = False
    except Exception as exc:  # @quality-exception exception-transparency: effect apply crosses device I/O and tray state; permission/disconnect are dispatched and remaining errors are logged with traceback
        if is_permission_denied(exc):
            try:
                tray._notify_permission_issue(exc)
            except Exception as notify_exc:  # @quality-exception exception-transparency: notification callback is a user-injected tray boundary and failures must not break the permission-issue handling path
                logger.exception("Failed to notify permission issue during effect selection: %s", notify_exc)
            return
        logger.exception("Error applying effect selection: %s", exc)
        return
