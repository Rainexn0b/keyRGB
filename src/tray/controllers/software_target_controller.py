from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from typing import Protocol, TypeAlias, TypeVar, cast

from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
from src.core.effects.software_targets import normalize_software_effect_target
from src.core.utils.exceptions import is_permission_denied
from src.tray.secondary_device_routes import route_for_context_entry
from src.tray.ui.menu_status import DeviceContextEntry, device_context_controls_available, device_context_entries

from . import _software_target_auxiliary as software_target_auxiliary


logger = logging.getLogger(__name__)
_ResultT = TypeVar("_ResultT")

_SecondarySoftwareTargetProtocol: TypeAlias = software_target_auxiliary._SecondarySoftwareTargetProtocol
_CachedSecondarySoftwareTarget = software_target_auxiliary._CachedSecondarySoftwareTarget
_SECONDARY_TARGET_RUNTIME_EXCEPTIONS = software_target_auxiliary._SECONDARY_TARGET_RUNTIME_EXCEPTIONS

_ENGINE_ATTR_WRITE_EXCEPTIONS = (OSError, OverflowError, RuntimeError, TypeError, ValueError)
_CONFIG_ATTR_WRITE_EXCEPTIONS = (OSError, RuntimeError, TypeError, ValueError)
_TRAY_CALLBACK_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


class _SoftwareTargetTrayProtocol(Protocol):
    @property
    def config(self) -> object: ...

    @property
    def engine(self) -> object: ...

    @property
    def is_off(self) -> bool: ...

    def _log_exception(self, msg: str, exc: Exception) -> None: ...

    def _log_event(self, source: str, action: str, **fields: object) -> None: ...


class _PermissionIssueTrayProtocol(Protocol):
    def _notify_permission_issue(self, exc: Exception) -> None: ...


def _run_recoverable_boundary(
    action: Callable[[], _ResultT],
    *,
    runtime_exceptions: tuple[type[Exception], ...],
    on_recoverable: Callable[[Exception], None],
    fallback: _ResultT,
    reraise_recoverable: bool = False,
) -> _ResultT:
    try:
        return action()
    except runtime_exceptions as exc:  # @quality-exception exception-transparency: shared secondary-target device and tray callback runtime seams must either invalidate cached state or degrade to fallback logging while unexpected defects still propagate
        on_recoverable(exc)
        if reraise_recoverable:
            raise
        return fallback


def _try_log_event(tray: _SoftwareTargetTrayProtocol, source: str, action: str, **fields: object) -> None:
    _call_tray_callback_best_effort(
        lambda: tray._log_event(source, action, **fields),
        on_recoverable=lambda exc: logger.exception("Tray event logging failed: %s", exc),
    )


def _call_tray_callback_best_effort(
    action: Callable[[], None],
    *,
    on_recoverable: Callable[[Exception], None],
) -> bool:
    def _call_action() -> bool:
        action()
        return True

    return _run_recoverable_boundary(
        _call_action,
        runtime_exceptions=_TRAY_CALLBACK_RUNTIME_EXCEPTIONS,
        on_recoverable=on_recoverable,
        fallback=False,
    )


def _notify_permission_issue_or_none(tray: _SoftwareTargetTrayProtocol) -> Callable[[Exception], None] | None:
    try:
        notify_permission_issue = cast(_PermissionIssueTrayProtocol, tray)._notify_permission_issue
    except AttributeError:
        return None
    if not callable(notify_permission_issue):
        return None
    return notify_permission_issue


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
    for entry, target in _iter_secondary_targets(tray):
        try:
            _restore_target_from_config(tray, entry=entry, target=target)
        except _SECONDARY_TARGET_RUNTIME_EXCEPTIONS as exc:
            _handle_secondary_target_error(tray, exc, action="restore_secondary_software_target")


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


def _secondary_target_entries(tray: object) -> list[DeviceContextEntry]:
    return software_target_auxiliary._secondary_target_entries(
        tray,
        device_context_entries_fn=device_context_entries,
        device_context_controls_available_fn=device_context_controls_available,
    )


def _proxy_cache(tray: _SoftwareTargetTrayProtocol) -> dict[str, _SecondarySoftwareTargetProtocol]:
    return software_target_auxiliary._proxy_cache(
        tray,
        on_store_cache_failure=lambda exc: _log_boundary_exception(
            tray,
            "Failed to store software target proxy cache: %s",
            exc,
        ),
    )


def _iter_secondary_targets(
    tray: _SoftwareTargetTrayProtocol,
) -> Iterator[tuple[DeviceContextEntry, _SecondarySoftwareTargetProtocol]]:
    return software_target_auxiliary._iter_secondary_targets(
        tray,
        secondary_target_entries_fn=_secondary_target_entries,
        secondary_software_render_targets_fn=secondary_software_render_targets,
    )


def _restore_target_from_config(
    tray: _SoftwareTargetTrayProtocol,
    *,
    entry: DeviceContextEntry,
    target: _SecondarySoftwareTargetProtocol,
) -> None:
    route = route_for_context_entry(entry)
    if route is None:
        return

    config = getattr(tray, "config", None)
    if config is None:
        return

    brightness_getter = getattr(config, "get_secondary_device_brightness", None)
    color_getter = getattr(config, "get_secondary_device_color", None)
    if callable(brightness_getter):
        brightness = int(
            brightness_getter(
                str(route.state_key), fallback_keys=tuple(filter(None, (route.config_brightness_attr,))), default=0
            )
            or 0
        )
    else:
        brightness_attr = str(route.config_brightness_attr or "").strip()
        if not brightness_attr:
            return
        raw_brightness = getattr(config, brightness_attr, 0)
        brightness = 0 if not raw_brightness else int(raw_brightness)
    if brightness <= 0:
        target.turn_off()
        return

    if callable(color_getter):
        raw_color = color_getter(
            str(route.state_key), fallback_keys=tuple(filter(None, (route.config_color_attr,))), default=(255, 0, 0)
        )
    else:
        color_attr = str(route.config_color_attr or "").strip()
        if not color_attr:
            return
        raw_color = getattr(config, color_attr, (255, 0, 0))
    color = tuple(raw_color or (255, 0, 0))
    target.set_color(color, brightness=brightness)


def _handle_secondary_target_error(tray: _SoftwareTargetTrayProtocol, exc: Exception, *, action: str) -> None:
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


def _set_engine_attr_best_effort(
    tray: _SoftwareTargetTrayProtocol, attr: str, value: object, *, error_msg: str
) -> None:
    engine = getattr(tray, "engine", None)
    if engine is None:
        return

    try:
        setattr(engine, attr, value)
    except AttributeError:
        return
    except _ENGINE_ATTR_WRITE_EXCEPTIONS as exc:
        _log_boundary_exception(tray, error_msg, exc)


def _set_config_attr_best_effort(
    tray: _SoftwareTargetTrayProtocol, attr: str, value: object, *, error_msg: str
) -> None:
    config = getattr(tray, "config", None)
    if config is None:
        return

    try:
        setattr(config, attr, value)
    except AttributeError:
        return
    except _CONFIG_ATTR_WRITE_EXCEPTIONS as exc:
        _log_boundary_exception(tray, error_msg, exc)


def _log_boundary_exception(tray: _SoftwareTargetTrayProtocol, msg: str, exc: Exception) -> None:
    if _call_tray_callback_best_effort(
        lambda: tray._log_exception(msg, exc),
        on_recoverable=lambda log_exc: logger.exception(
            "Tray exception logger failed while logging boundary: %s", log_exc
        ),
    ):
        return

    logger.error(msg, exc, exc_info=(type(exc), exc, exc.__traceback__))


__all__ = [
    "apply_software_effect_target_selection",
    "configure_engine_software_targets",
    "restore_secondary_software_targets",
    "secondary_software_render_targets",
    "software_effect_target_has_auxiliary_devices",
    "software_effect_target_options",
    "software_effect_target_routes_aux_devices",
    "turn_off_secondary_software_targets",
]
