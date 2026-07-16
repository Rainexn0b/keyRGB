"""Profile-owned secondary software-target reconcile and restore helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol, TypeAlias

from src.core import secondary_lighting_state
from src.tray.idle_power_state import any_forced_off
from src.tray.secondary_device_routes import route_for_context_entry
from src.tray.ui.menu_status import DeviceContextEntry

from . import _software_target_auxiliary as software_target_auxiliary
from . import secondary_static_scene

_SecondarySoftwareTargetProtocol: TypeAlias = software_target_auxiliary._SecondarySoftwareTargetProtocol
_SECONDARY_TARGET_RUNTIME_EXCEPTIONS = software_target_auxiliary._SECONDARY_TARGET_RUNTIME_EXCEPTIONS


class _SoftwareTargetTrayProtocol(Protocol):
    @property
    def config(self) -> object: ...

    @property
    def engine(self) -> object: ...

    @property
    def is_off(self) -> bool: ...

    def _log_exception(self, msg: str, exc: Exception) -> None: ...

    def _log_event(self, source: str, action: str, **fields: object) -> None: ...


def restore_target_from_config(
    tray: _SoftwareTargetTrayProtocol,
    *,
    entry: DeviceContextEntry,
    target: _SecondarySoftwareTargetProtocol,
) -> None:
    route = route_for_context_entry(entry)
    if route is None:
        return

    config = getattr(tray, "config", None)
    payload = vars(tray).get("_active_secondary_lighting")
    if payload is None:
        payload = secondary_lighting_state.legacy_snapshot_from_config(config, (route,))
    state = secondary_lighting_state.area_entry(payload, route.state_key)
    if state is None:
        return
    if not secondary_lighting_state.entry_enabled(state):
        target.turn_off()
        return
    target.set_color(
        secondary_lighting_state.route_color(config, route, state),
        brightness=secondary_lighting_state.route_brightness(config, route, state),
    )


def reconcile_secondary_profile_state(
    tray: _SoftwareTargetTrayProtocol,
    payload: Mapping[str, object] | None,
    *,
    animated: bool,
    proxy_cache_fn: Callable[[_SoftwareTargetTrayProtocol], dict[str, _SecondarySoftwareTargetProtocol]],
    handle_secondary_target_error_fn: Callable[..., None],
) -> None:
    """Refresh profile-owned secondary state without restarting the keyboard effect."""
    if payload is None:
        if not animated:
            secondary_static_scene.apply_secondary_static_scene(tray)
        return

    old_payload = vars(tray).get("_active_secondary_lighting")
    new_enabled = secondary_lighting_state.enabled_state_keys(payload)
    old_enabled = secondary_lighting_state.enabled_state_keys(old_payload)
    cache = proxy_cache_fn(tray)
    if not old_enabled:
        old_enabled = {str(getattr(target, "state_key", "")).strip().lower() for target in cache.values()}
    if animated and not any_forced_off(tray):
        for target in tuple(cache.values()):
            state_key = str(getattr(target, "state_key", "")).strip().lower()
            if state_key not in old_enabled or state_key in new_enabled:
                continue
            try:
                target.turn_off()
            except _SECONDARY_TARGET_RUNTIME_EXCEPTIONS as exc:
                handle_secondary_target_error_fn(tray, exc, action="disable_secondary_software_target")

    try:
        vars(tray)["_active_secondary_lighting"] = payload
    except (AttributeError, TypeError, RuntimeError):
        pass

    if not animated:
        secondary_static_scene.apply_secondary_static_scene(tray, payload=payload)
