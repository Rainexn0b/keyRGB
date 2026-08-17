from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from src.core import secondary_lighting_state
from src.core.backends.policies.backend_selection import experimental_backends_enabled
from src.core.diagnostics.model import freeze_snapshot
from src.core.secondary_device_routes import iter_secondary_routes
from src.core.secondary_device_runtime import EffectiveSecondaryRoute, iter_effective_secondary_routes

_READ_ERRORS = (AttributeError, ImportError, LookupError, OSError, RuntimeError, TypeError, ValueError)
logger = logging.getLogger(__name__)


class ReadonlyDiagnosticsConfig:
    """Detached read-only config view for diagnostics. Never persists."""

    def __init__(self, settings: Mapping[str, object]) -> None:
        self._settings = dict(settings)
        self.tray_device_context = str(self._settings.get("tray_device_context") or "keyboard")
        self.software_effect_target = str(self._settings.get("software_effect_target") or "keyboard")
        self.brightness = self._settings.get("brightness", 0)

    def _state_entry(self, state_key: object) -> Mapping[str, object]:
        raw_state = self._settings.get("secondary_device_state")
        if not isinstance(raw_state, Mapping):
            return {}
        entry = raw_state.get(str(state_key or "").strip().lower())
        return entry if isinstance(entry, Mapping) else {}

    def _fallback_value(self, fallback_keys: tuple[str, ...], default: object) -> object:
        for key in fallback_keys:
            if key in self._settings:
                return self._settings[key]
        return default

    def get_secondary_device_brightness(
        self,
        state_key: object,
        *,
        fallback_keys: tuple[str, ...] = (),
        default: object = 0,
    ) -> object:
        entry = self._state_entry(state_key)
        if "brightness" in entry:
            return entry["brightness"]
        return self._fallback_value(fallback_keys, default)

    def get_secondary_device_enabled(
        self,
        state_key: object,
        *,
        fallback_keys: tuple[str, ...] = (),
        default: object = False,
    ) -> object:
        entry = self._state_entry(state_key)
        if "enabled" in entry:
            return entry["enabled"]
        return self._fallback_value(fallback_keys, default)

    def get_secondary_device_color(
        self,
        state_key: object,
        *,
        fallback_keys: tuple[str, ...] = (),
        default: object = (255, 0, 0),
    ) -> object:
        entry = self._state_entry(state_key)
        if "color" in entry:
            return entry["color"]
        return self._fallback_value(fallback_keys, default)


def _load_config() -> object | None:
    try:
        from src.core.config.defaults import DEFAULTS
        from src.core.config.file_storage import load_config_settings
        from src.core.config.paths import config_file_path

        loaded = load_config_settings(
            config_file=config_file_path(),
            defaults=DEFAULTS,
            retries=1,
            retry_delay=0.0,
            logger=logger,
        )
    except _READ_ERRORS:
        return None
    if not isinstance(loaded, Mapping):
        return None
    return ReadonlyDiagnosticsConfig(loaded)


def _config_value(config: object | None, attr: str, default: object = None) -> object:
    if config is None:
        return default
    try:
        return getattr(config, attr, default)
    except _READ_ERRORS:
        return default


def _effective_route_entry(effective: EffectiveSecondaryRoute) -> dict[str, Any]:
    route = effective.route
    return {
        "backend_name": route.backend_name,
        "device_type": route.device_type,
        "display_name": route.display_name,
        "parent_backend": route.parent_backend_name,
        "zone_key": route.zone_key,
        "state_key": route.state_key,
        "available": effective.available,
        "parent_available": effective.available,
        "parent_reason": effective.availability_reason,
        "availability_source": effective.availability_source,
        "simulated": effective.simulated,
        "supports_uniform_color": bool(route.supports_uniform_color),
        "supports_software_target": bool(route.supports_software_target),
        "supports_profile_state": bool(route.supports_profile_state),
        "brightness_policy": route.brightness_policy,
    }


def _auxiliary_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aux: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        device_type = str(candidate.get("device_type") or "").strip().lower()
        if not device_type or device_type == "keyboard":
            continue
        status = str(candidate.get("status") or "").strip()
        aux.append(
            {
                "device_type": device_type,
                "status": status,
                "usb_vid": str(candidate.get("usb_vid") or "").strip(),
                "usb_pid": str(candidate.get("usb_pid") or "").strip(),
                "product": str(candidate.get("product") or "").strip(),
                "context_key": str(candidate.get("context_key") or "").strip(),
                # Mirrors tray device_context_controls_available(): a non-keyboard
                # discovery candidate only gets live controls when its status is
                # "supported".
                "controls_available": status == "supported",
            }
        )
    return aux


def _expected_tray_contexts(
    aux_candidates: list[dict[str, Any]],
    effective_routes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Summarize the selectable live-control contexts the tray should render."""
    contexts: list[dict[str, Any]] = [
        {"key": "keyboard", "device_type": "keyboard", "source": "primary", "controls_available": True}
    ]
    seen_device_types: set[str] = set()
    for candidate in aux_candidates:
        device_type = str(candidate.get("device_type") or "").strip().lower()
        if not device_type or device_type in seen_device_types:
            continue
        contexts.append(
            {
                "key": str(candidate.get("context_key") or device_type),
                "device_type": device_type,
                "source": "discovery",
                "controls_available": bool(candidate.get("controls_available")),
            }
        )
        seen_device_types.add(device_type)

    for route in effective_routes:
        device_type = str(route.get("device_type") or "").strip().lower()
        if not bool(route.get("available")) or not device_type or device_type in seen_device_types:
            continue
        contexts.append(
            {
                "key": str(route.get("backend_name") or device_type),
                "device_type": device_type,
                "source": "simulation" if bool(route.get("simulated")) else "effective_route",
                "controls_available": True,
            }
        )
        seen_device_types.add(device_type)
    return contexts


def _expected_profile_editor_rows(effective_routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Report the secondary rows the Lighting Profile Editor should render."""
    return [
        {
            "state_key": route.get("state_key"),
            "device_type": route.get("device_type"),
            "display_name": route.get("display_name"),
            "simulated": bool(route.get("simulated")),
            "availability_source": route.get("availability_source"),
        }
        for route in effective_routes
        if route.get("available") and route.get("supports_profile_state")
    ]


def _secondary_device_state(config: object | None) -> dict[str, Any]:
    """Report persisted enabled/brightness/color for each registered route."""
    state: dict[str, Any] = {}
    if config is None:
        return state
    routes = list(iter_secondary_routes())
    for route in routes:
        state[route.state_key] = {
            "enabled": secondary_lighting_state.config_enabled(config, route),
            "brightness": secondary_lighting_state.config_brightness(config, route, default=0),
            "color": list(secondary_lighting_state.config_color(config, route)),
        }
    return state


def secondary_devices_snapshot(candidates: list[dict[str, Any]] | None) -> Mapping[str, Any]:
    """Build a read-only snapshot of secondary/auxiliary device state.

    Captures everything needed to confirm, from a support bundle, whether
    auxiliary lighting devices (e.g. Legion Gen10 logo/neon/vent chassis zones)
    are detected, whether the tray would surface controls for them, and why not
    if a zone's parent backend is unavailable. No devices are opened and no
    mutable ``Config`` instance is constructed.
    """
    config = _load_config()

    effective = list(iter_effective_secondary_routes(include_unavailable=True))
    effective_routes = [_effective_route_entry(entry) for entry in effective]
    virtual_routes = [entry for entry in effective_routes if entry.get("parent_backend")]
    aux_candidates = _auxiliary_candidates(candidates or [])
    expected_contexts = _expected_tray_contexts(aux_candidates, effective_routes)
    expected_editor_rows = _expected_profile_editor_rows(effective_routes)

    all_compatible_enabled = any(
        bool(route.get("available")) and bool(route.get("supports_software_target")) for route in effective_routes
    )

    snapshot = {
        "experimental_backends_enabled": bool(experimental_backends_enabled()),
        "selected_device_context": str(_config_value(config, "tray_device_context", "keyboard") or "keyboard"),
        "software_effect_target": {
            "current": str(_config_value(config, "software_effect_target", "keyboard") or "keyboard"),
            "all_compatible_devices_enabled": all_compatible_enabled,
        },
        "virtual_routes": virtual_routes,
        "effective_routes": effective_routes,
        "auxiliary_candidates": aux_candidates,
        "expected_tray_contexts": expected_contexts,
        "expected_profile_editor_rows": expected_editor_rows,
        "secondary_device_state": _secondary_device_state(config),
    }
    frozen = freeze_snapshot(snapshot)
    return frozen if isinstance(frozen, Mapping) else snapshot


__all__ = ["ReadonlyDiagnosticsConfig", "secondary_devices_snapshot"]
