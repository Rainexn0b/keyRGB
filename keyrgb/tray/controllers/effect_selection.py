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

from keyrgb.core.backends.base import normalize_backend_capabilities
from keyrgb.core.effects import catalog as effects_catalog
from keyrgb.core.lighting_layers import has_nonempty_per_key_base
from keyrgb.core.utils.exceptions import is_permission_denied
from keyrgb.core.utils.safe_attrs import safe_int_attr
from keyrgb.tray.controllers._effect_selection_defer import defer_effect_selection as _defer_effect_selection
from keyrgb.tray.controllers.secondary_static_scene import apply_secondary_static_fallback
from keyrgb.tray.protocols import LightingTrayProtocol

logger = logging.getLogger(__name__)

_PROFILE_LOAD_RECOVERABLE_EXCEPTIONS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_EFFECT_SELECTION_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
# Permission-notify tray callback boundary; no map/key LookupError expected.
_NOTIFY_CALLBACK_RUNTIME_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


class _BackendCapsProtocol(Protocol):
    per_key: bool
    hardware_effects: bool


class _EffectSelectionTrayProtocol(LightingTrayProtocol, Protocol):
    backend: object | None
    backend_caps: _BackendCapsProtocol | None

    def _start_current_effect(self, **kwargs: object) -> bool | None: ...


class _ProfilesApi(Protocol):
    def get_active_profile(self) -> str: ...

    def load_per_key_colors(self, profile_name: str): ...


profiles: object | None

try:
    # Module-level import so tests (and callers) can monkeypatch `profiles`.
    from keyrgb.core.profile import profiles
except ImportError:  # pragma: no cover
    profiles = None


def _set_attr_best_effort(obj: object, name: str, value: object) -> bool:
    try:
        setattr(obj, name, value)
    except (AttributeError, TypeError, ValueError):
        return False
    return True


def _notify_permission_issue_best_effort(tray: LightingTrayProtocol, exc: Exception) -> None:
    try:
        tray._notify_permission_issue(exc)
    except _NOTIFY_CALLBACK_RUNTIME_EXCEPTIONS as notify_exc:
        logger.exception("Failed to notify permission issue during effect selection: %s", notify_exc)  # noqa: TRY401


def _load_per_key_colors_from_profile(config) -> dict:
    """Load per-key colors from the active profile.

    Returns the loaded colors dict, or empty dict on failure.
    """
    prof = profiles
    if prof is None:
        try:
            from keyrgb.core.profile import profiles as prof
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

        caps = normalize_backend_capabilities(getattr(effect_tray, "backend_caps", None))
        per_key_supported = caps.per_key
        hw_effects_supported = caps.hardware_effects

        try:
            effect_name = effects_catalog.normalize_effect_name(effect_name)
        except (AttributeError, TypeError, ValueError):
            effect_name = "none"

        base_effect_name = effects_catalog.strip_effect_namespace(effect_name)

        from keyrgb.tray.deck_pipeline import hardware_apply_deferred

        if hardware_apply_deferred(tray):
            _defer_effect_selection(
                effect_tray,
                effect_name=effect_name,
                per_key_supported=per_key_supported,
                hw_effects_supported=hw_effects_supported,
            )
            return

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
            apply_secondary_static_fallback(tray)
            tray.is_off = False
            return

        # === HANDLE SPECIAL CASES ===

        # "none" or "stop" -> go to static color (respects current mode)
        if effect_name in {"none", "stop"}:
            tray.engine.stop()

            per_key = _config_per_key_colors_ref(tray.config)
            tray.config.effect = "none"
            if has_nonempty_per_key_base(per_key) and per_key_supported:
                _ensure_software_mode(tray)
                effect_tray._start_current_effect()
            else:
                _ensure_hardware_mode(tray)
                with tray.engine.kb_lock:
                    tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
                apply_secondary_static_fallback(tray)

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
                apply_secondary_static_fallback(tray)
                tray.is_off = False
                return

            colors = _load_per_key_colors_from_profile(tray.config)
            if colors:
                tray.config.per_key_colors = colors

            _ensure_software_mode(tray)
            tray.config.effect = "none"
            effect_tray._start_current_effect()
            tray.is_off = False
            return

        # === HARDWARE EFFECTS ===
        if effects_catalog.is_backend_hardware_effect(effect_name, getattr(effect_tray, "backend", None)):
            if not hw_effects_supported:
                tray.engine.stop()
                tray.config.effect = "none"
                _ensure_hardware_mode(tray)
                with tray.engine.kb_lock:
                    tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
                apply_secondary_static_fallback(tray)
                tray.is_off = False
                return

            _set_attr_best_effort(tray.config, "per_key_colors", {})
            _ensure_hardware_mode(tray)
            tray.config.effect = (
                effect_name if effects_catalog.is_forced_hardware_effect(effect_name) else base_effect_name
            )
            effect_tray._start_current_effect()
            tray.is_off = False
            return

        # === SOFTWARE EFFECTS ===
        if base_effect_name in effects_catalog.SW_EFFECTS_SET and not effects_catalog.is_forced_hardware_effect(
            effect_name
        ):
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
        apply_secondary_static_fallback(tray)
        tray.is_off = False
    except _EFFECT_SELECTION_RUNTIME_EXCEPTIONS as exc:  # @quality-exception exception-transparency: effect apply crosses device I/O and tray state; permission/disconnect are dispatched and remaining recoverable runtime errors are logged with traceback
        if is_permission_denied(exc):
            _notify_permission_issue_best_effort(tray, exc)
            return
        logger.exception("Error applying effect selection: %s", exc)  # noqa: TRY401
        return
