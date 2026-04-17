from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar, cast, overload


_STARTUP_MIGRATION_ERRORS = (AttributeError, ImportError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_STARTUP_CALLBACK_INSTALL_ERRORS = (AttributeError, RuntimeError)
_STARTUP_ENGINE_SET_BACKEND_ERRORS = (TypeError, RuntimeError, ValueError)
_ResultT = TypeVar("_ResultT")
_EngineT = TypeVar("_EngineT", covariant=True)
_PermissionErrorCallback = Callable[[Exception | None], None]


class _EffectsEngineFactory(Protocol[_EngineT]):
    @overload
    def __call__(self, *, backend: object) -> _EngineT: ...

    @overload
    def __call__(self) -> _EngineT: ...


class _NotificationDrainTray(Protocol):
    def _notify(self, title: str, message: str) -> None: ...


class _PermissionErrorCallbackSink(Protocol):
    @property
    def _permission_error_cb(self) -> _PermissionErrorCallback | None: ...

    @_permission_error_cb.setter
    def _permission_error_cb(self, callback: _PermissionErrorCallback | None) -> None: ...


def _run_best_effort(
    operation: Callable[[], _ResultT],
    *,
    fallback: _ResultT,
    recoverable_errors: tuple[type[Exception], ...],
    on_recoverable: Callable[[Exception], None] | None = None,
) -> _ResultT:
    try:
        return operation()
    except recoverable_errors as exc:  # @quality-exception exception-transparency: shared tray startup helper centralizes recoverable migration, backend introspection, and callback-install boundaries so startup degrades cleanly while unexpected defects still propagate
        if on_recoverable is not None:
            on_recoverable(exc)
        return fallback


def migrate_builtin_profile_brightness_best_effort(config: object) -> None:
    def _migrate() -> None:
        from src.core.profile import profiles as core_profiles

        core_profiles.migrate_builtin_profile_brightness(config)

    _run_best_effort(
        _migrate,
        fallback=None,
        recoverable_errors=_STARTUP_MIGRATION_ERRORS,
    )


def _set_engine_backend_best_effort(engine: object, backend: object) -> None:
    set_backend = getattr(engine, "set_backend", None)
    if not callable(set_backend):
        return

    _run_best_effort(
        lambda: set_backend(backend),
        fallback=None,
        recoverable_errors=_STARTUP_ENGINE_SET_BACKEND_ERRORS,
    )


def create_effects_engine(EffectsEngine: _EffectsEngineFactory[_EngineT], *, backend: object) -> _EngineT:
    try:
        return EffectsEngine(backend=backend)
    except TypeError:
        engine = EffectsEngine()
        _set_engine_backend_best_effort(engine, backend)
        return engine


def install_permission_error_callback_best_effort(engine: object, callback: _PermissionErrorCallback) -> None:
    _run_best_effort(
        lambda: _install_permission_error_callback(cast(_PermissionErrorCallbackSink, engine), callback),
        fallback=None,
        recoverable_errors=_STARTUP_CALLBACK_INSTALL_ERRORS,
    )


def _install_permission_error_callback(
    engine: _PermissionErrorCallbackSink, callback: _PermissionErrorCallback
) -> None:
    engine._permission_error_cb = callback


def build_permission_denied_message(backend_name: str) -> str:
    repo_url = "https://github.com/Rainexn0b/keyRGB"
    msg_lines = [
        "KeyRGB was blocked by missing permissions while updating keyboard lighting.",
        "",
        "Fix:",
        "  • Re-run KeyRGB's installer (installs udev rules / helpers)",
        "  • Reload udev rules: sudo udevadm control --reload-rules && sudo udevadm trigger",
        "  • Replug the device or reboot",
    ]
    if backend_name == "ite8291r3":
        msg_lines.append("  • ITE USB devices usually need /etc/udev/rules.d/99-ite8291-wootbook.rules")
    elif backend_name == "sysfs-leds":
        msg_lines.append(
            "  • Sysfs LED nodes may require /etc/udev/rules.d/99-keyrgb-sysfs-leds.rules or a polkit helper"
        )
    msg_lines.append("")
    msg_lines.append(repo_url)
    return "\n".join(msg_lines)


def flush_pending_notifications(tray: _NotificationDrainTray) -> None:
    pending_store = vars(tray).get("_pending_notifications")
    pending = list(pending_store) if isinstance(pending_store, list) else []
    if isinstance(pending_store, list):
        pending_store.clear()
    for title, message in pending:
        tray._notify(title, message)
