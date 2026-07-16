from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TypeAlias

from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
from src.core.effects.software_targets import normalize_software_effect_target
from src.core import secondary_lighting_state
from src.core.secondary_device_runtime import iter_effective_secondary_routes
from src.core.secondary_device_runtime import secondary_device_simulation_enabled
from src.core.utils.exceptions import is_permission_denied
from src.tray.secondary_device_routes import route_for_context_entry
from src.tray.ui.menu_status import DeviceContextEntry, device_context_controls_available, device_context_entries

from . import _software_target_auxiliary as software_target_auxiliary
from . import _software_target_boundaries as boundaries
from . import _software_target_profile as software_target_profile
from ._lighting_controller_helpers import is_software_effect

# Public re-exports for tests and monkeypatch seams.
_SoftwareTargetTrayProtocol = boundaries._SoftwareTargetTrayProtocol
_PermissionIssueTrayProtocol = boundaries._PermissionIssueTrayProtocol
_run_recoverable_boundary = boundaries.run_recoverable_boundary
_try_log_event = boundaries.try_log_event
_call_tray_callback_best_effort = boundaries.call_tray_callback_best_effort
_notify_permission_issue_or_none = boundaries.notify_permission_issue_or_none
_set_engine_attr_best_effort = boundaries.set_engine_attr_best_effort
_set_config_attr_best_effort = boundaries.set_config_attr_best_effort
_log_boundary_exception = boundaries.log_boundary_exception
_restore_target_from_config = software_target_profile.restore_target_from_config
logger = boundaries.logger

_SecondarySoftwareTargetProtocol: TypeAlias = software_target_auxiliary._SecondarySoftwareTargetProtocol
_CachedSecondarySoftwareTarget = software_target_auxiliary._CachedSecondarySoftwareTarget
_SECONDARY_TARGET_RUNTIME_EXCEPTIONS = software_target_auxiliary._SECONDARY_TARGET_RUNTIME_EXCEPTIONS


def _handle_secondary_target_error(tray: _SoftwareTargetTrayProtocol, exc: Exception, *, action: str) -> None:
    # Keep permission classification on this module so tests can patch
    # ``is_permission_denied`` / logger seams on the public controller path.
    if is_permission_denied(exc):
        notify_permission_issue = _notify_permission_issue_or_none(tray)
        if notify_permission_issue is None:
            _log_boundary_exception(tray, f"Error during {action}: %s", exc)
            return
        if _call_tray_callback_best_effort(
            lambda: notify_permission_issue(exc),
            on_recoverable=lambda notify_exc: _log_boundary_exception(
                tray,
                "Failed to notify permission issue for secondary software target: %s",
                notify_exc,
            ),
        ):
            return

    _log_boundary_exception(tray, f"Error during {action}: %s", exc)


def _software_effect_is_running(tray: object, current: object) -> bool:
    return bool(
        getattr(getattr(tray, "engine", None), "running", False)
        and is_software_effect(str(getattr(current, "effect", "none")))
    )


def configure_engine_software_targets(tray: _SoftwareTargetTrayProtocol) -> None:
    engine = getattr(tray, "engine", None)
    if engine is None:
        return

    target = normalize_software_effect_target(getattr(getattr(tray, "config", None), "software_effect_target", None))
    _set_engine_attr_best_effort(
        tray,
        "software_effect_target",
        target,
        error_msg="Failed to sync engine software target: %s",
    )
    _set_engine_attr_best_effort(
        tray,
        "secondary_software_targets_provider",
        lambda tray_ref=tray: secondary_software_render_targets(tray_ref),
        error_msg="Failed to install secondary software target provider: %s",
    )


def apply_software_effect_target_selection(tray: _SoftwareTargetTrayProtocol, target: str) -> str:
    normalized = normalize_software_effect_target(target)
    previous = normalize_software_effect_target(getattr(getattr(tray, "config", None), "software_effect_target", None))

    _set_config_attr_best_effort(
        tray,
        "software_effect_target",
        normalized,
        error_msg="Failed to persist software effect target selection: %s",
    )

    configure_engine_software_targets(tray)
    _try_log_event(tray, "menu", "set_software_effect_target", old=previous, new=normalized)

    if normalized != SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE and not bool(getattr(tray, "is_off", False)):
        restore_secondary_software_targets(tray)

    return normalized


def software_effect_target_has_auxiliary_devices(tray: object) -> bool:
    return software_target_auxiliary.software_effect_target_has_auxiliary_devices(
        tray,
        secondary_target_entries_fn=_secondary_target_entries,
    )


def software_effect_target_has_compatible_devices(tray: object) -> bool:
    """Return whether compatible secondary routes exist, enabled or disabled."""
    return bool(_compatible_secondary_target_entries(tray))


def software_effect_target_routes_aux_devices(tray: _SoftwareTargetTrayProtocol) -> bool:
    return software_target_auxiliary.software_effect_target_routes_aux_devices(
        tray,
        has_auxiliary_devices_fn=software_effect_target_has_auxiliary_devices,
    )


def secondary_software_render_targets(tray: _SoftwareTargetTrayProtocol) -> list[_SecondarySoftwareTargetProtocol]:
    return software_target_auxiliary.secondary_software_render_targets(
        tray,
        secondary_target_entries_fn=_secondary_target_entries,
        proxy_cache_fn=_proxy_cache,
        cached_secondary_target_cls=_CachedSecondarySoftwareTarget,
    )


def restore_secondary_software_targets(tray: _SoftwareTargetTrayProtocol) -> None:
    # Keep the loop here so tests can monkeypatch `_iter_secondary_targets` /
    # `_restore_target_from_config` on this module.
    for entry, target in _iter_secondary_targets(tray):
        try:
            _restore_target_from_config(tray, entry=entry, target=target)
        except _SECONDARY_TARGET_RUNTIME_EXCEPTIONS as exc:
            _handle_secondary_target_error(tray, exc, action="restore_secondary_software_target")


def reconcile_secondary_profile_state(
    tray: _SoftwareTargetTrayProtocol,
    payload: object,
    *,
    animated: bool,
) -> None:
    mapping_payload: Mapping[str, object] | None
    if payload is None or isinstance(payload, Mapping):
        mapping_payload = payload  # type: ignore[assignment]
    else:
        mapping_payload = None
    software_target_profile.reconcile_secondary_profile_state(
        tray,
        mapping_payload,
        animated=animated,
        proxy_cache_fn=_proxy_cache,
        handle_secondary_target_error_fn=_handle_secondary_target_error,
    )


def turn_off_secondary_software_targets(tray: _SoftwareTargetTrayProtocol) -> None:
    for _entry, target in _iter_secondary_targets(tray):
        try:
            target.turn_off()
        except _SECONDARY_TARGET_RUNTIME_EXCEPTIONS as exc:
            _handle_secondary_target_error(tray, exc, action="turn_off_secondary_software_target")


def software_effect_target_options(tray: object) -> list[dict[str, object]]:
    return software_target_auxiliary.software_effect_target_options(
        tray,
        has_auxiliary_devices_fn=software_effect_target_has_auxiliary_devices,
    )


def _compatible_secondary_target_entries(tray: object) -> list[DeviceContextEntry]:
    if secondary_device_simulation_enabled():
        return [
            {
                "key": effective.backend_name,
                "backend_name": effective.backend_name,
                "device_type": effective.device_type,
                "status": "supported",
                "text": f"{effective.display_name} (simulated)",
            }
            for effective in iter_effective_secondary_routes()
            if effective.available
            and effective.route.supports_uniform_color
            and effective.route.supports_software_target
        ]
    return software_target_auxiliary._secondary_target_entries(
        tray,
        device_context_entries_fn=device_context_entries,
        device_context_controls_available_fn=device_context_controls_available,
    )


def _secondary_target_entries(tray: object) -> list[DeviceContextEntry]:
    entries = _compatible_secondary_target_entries(tray)
    if "_active_secondary_lighting" not in vars(tray):
        return entries
    return [
        entry
        for entry in entries
        if (
            (route := route_for_context_entry(entry)) is None or _route_enabled_by_active_profile(tray, route.state_key)
        )
    ]


def _route_enabled_by_active_profile(tray: object, state_key: str) -> bool:
    """Gate animated fan-out on the active profile when activation supplied it."""
    if "_active_secondary_lighting" not in vars(tray):
        return True
    missing = object()
    payload = vars(tray).get("_active_secondary_lighting", missing)
    if payload is missing:
        return True
    entry = secondary_lighting_state.area_entry(payload, state_key)
    if entry is None:
        return False
    return secondary_lighting_state.entry_enabled(entry)


def _proxy_cache(tray: _SoftwareTargetTrayProtocol) -> dict[str, _SecondarySoftwareTargetProtocol]:
    return software_target_auxiliary._proxy_cache(
        tray,
        on_store_cache_failure=lambda exc: _log_boundary_exception(
            tray,
            "Failed to store software target proxy cache: %s",
            exc,
        ),
    )


def close_secondary_software_target_cache(tray: _SoftwareTargetTrayProtocol) -> None:
    """Close and clear all cached secondary target handles for the tray."""
    software_target_auxiliary.close_secondary_software_target_cache(_proxy_cache(tray))


def _iter_secondary_targets(
    tray: _SoftwareTargetTrayProtocol,
) -> Iterator[tuple[DeviceContextEntry, _SecondarySoftwareTargetProtocol]]:
    return software_target_auxiliary._iter_secondary_targets(
        tray,
        secondary_target_entries_fn=_secondary_target_entries,
        secondary_software_render_targets_fn=secondary_software_render_targets,
    )


__all__ = [
    "apply_software_effect_target_selection",
    "close_secondary_software_target_cache",
    "configure_engine_software_targets",
    "reconcile_secondary_profile_state",
    "restore_secondary_software_targets",
    "secondary_software_render_targets",
    "software_effect_target_has_auxiliary_devices",
    "software_effect_target_has_compatible_devices",
    "software_effect_target_options",
    "software_effect_target_routes_aux_devices",
    "turn_off_secondary_software_targets",
]
