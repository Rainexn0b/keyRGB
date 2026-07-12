from __future__ import annotations

from typing import Any

from src.core.backends.policy import experimental_backends_enabled
from src.core.secondary_device_routes import (
    SecondaryDeviceRoute,
    iter_virtual_routes,
)


_READ_ERRORS = (AttributeError, ImportError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _load_config() -> object | None:
    try:
        from src.core.config import Config

        return Config()
    except _READ_ERRORS:
        return None


def _config_value(config: object | None, attr: str, default: object = None) -> object:
    if config is None:
        return default
    try:
        return getattr(config, attr, default)
    except _READ_ERRORS:
        return default


def _parent_probe(route: SecondaryDeviceRoute) -> tuple[bool, str]:
    """Read-only availability probe of a virtual route's parent backend.

    Uses the backend ``probe()`` (hidraw scan + policy gate) rather than opening
    the device, so discovery stays read-only.
    """
    try:
        backend = route.get_backend()
    except _READ_ERRORS as exc:
        return False, f"parent backend unavailable ({exc})"

    probe = getattr(backend, "probe", None)
    if not callable(probe):
        return False, "parent backend has no probe()"

    try:
        result = probe()
    except _READ_ERRORS as exc:
        return False, f"parent probe failed ({exc})"

    available = bool(getattr(result, "available", False))
    reason = str(getattr(result, "reason", "") or "")
    return available, reason


def _virtual_route_entry(route: SecondaryDeviceRoute) -> dict[str, Any]:
    available, reason = _parent_probe(route)
    return {
        "backend_name": route.backend_name,
        "device_type": route.device_type,
        "display_name": route.display_name,
        "parent_backend": route.parent_backend_name,
        "zone_key": route.zone_key,
        "parent_available": available,
        "parent_reason": reason,
        "supports_uniform_color": bool(route.supports_uniform_color),
        "supports_software_target": bool(route.supports_software_target),
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
    virtual_routes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Summarize the device-context rows the tray header would render.

    This mirrors the gating in ``src/tray/ui/_menu_status_devices.py``:
    a keyboard row, one row per non-keyboard discovery candidate, and one row
    per virtual zone route whose parent backend is currently available.
    """
    contexts: list[dict[str, Any]] = [
        {"key": "keyboard", "device_type": "keyboard", "source": "primary", "controls_available": True}
    ]
    for candidate in aux_candidates:
        key = str(candidate.get("context_key") or "").strip() or str(candidate.get("device_type") or "")
        contexts.append(
            {
                "key": key,
                "device_type": candidate.get("device_type"),
                "source": "discovery",
                "controls_available": bool(candidate.get("controls_available")),
            }
        )
    for route in virtual_routes:
        if not route.get("parent_available"):
            continue
        contexts.append(
            {
                "key": route.get("backend_name"),
                "device_type": route.get("device_type"),
                "source": "virtual_route",
                "controls_available": True,
            }
        )
    return contexts


def _secondary_device_state(config: object | None) -> dict[str, Any]:
    """Report persisted brightness/color for each registered secondary route."""
    state: dict[str, Any] = {}
    if config is None:
        return state
    get_brightness = getattr(config, "get_secondary_device_brightness", None)
    get_color = getattr(config, "get_secondary_device_color", None)

    routes = list(iter_virtual_routes())
    for route in routes:
        brightness: object = None
        color: object = None
        if callable(get_brightness):
            try:
                brightness = get_brightness(
                    route.state_key,
                    fallback_keys=(route.config_brightness_attr,) if route.config_brightness_attr else (),
                    default=0,
                )
            except _READ_ERRORS:
                brightness = None
        if callable(get_color):
            try:
                color_value = get_color(
                    route.state_key,
                    fallback_keys=(route.config_color_attr,) if route.config_color_attr else (),
                )
                if isinstance(color_value, (list, tuple)):
                    color = [int(channel) for channel in color_value]
            except _READ_ERRORS:
                color = None
        state[route.state_key] = {"brightness": brightness, "color": color}
    return state


def secondary_devices_snapshot(candidates: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Build a read-only snapshot of secondary/auxiliary device state.

    Captures everything needed to confirm, from a support bundle, whether
    auxiliary lighting devices (e.g. Legion Gen10 logo/neon/vent chassis zones)
    are detected, whether the tray would surface controls for them, and why not
    if a zone's parent backend is unavailable. No devices are opened.
    """
    config = _load_config()

    virtual_routes = [_virtual_route_entry(route) for route in iter_virtual_routes()]
    aux_candidates = _auxiliary_candidates(candidates or [])
    expected_contexts = _expected_tray_contexts(aux_candidates, virtual_routes)

    all_compatible_enabled = any(
        bool(context.get("controls_available")) and context.get("device_type") != "keyboard"
        for context in expected_contexts
    )

    return {
        "experimental_backends_enabled": bool(experimental_backends_enabled()),
        "selected_device_context": str(_config_value(config, "tray_device_context", "keyboard") or "keyboard"),
        "software_effect_target": {
            "current": str(_config_value(config, "software_effect_target", "keyboard") or "keyboard"),
            "all_compatible_devices_enabled": all_compatible_enabled,
        },
        "virtual_routes": virtual_routes,
        "auxiliary_candidates": aux_candidates,
        "expected_tray_contexts": expected_contexts,
        "secondary_device_state": _secondary_device_state(config),
    }


__all__ = ["secondary_devices_snapshot"]
