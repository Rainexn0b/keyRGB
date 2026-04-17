"""Private bootstrap and run bindings for the tray application facade."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast, overload

from .lifecycle import _AutostartEffectTray, _LifecyclePollingTray, _MonitoringPowerManager


if TYPE_CHECKING:
    from src.core.config import Config


class _EffectsEngineFactory(Protocol):
    @overload
    def __call__(self, *, backend: object) -> object: ...

    @overload
    def __call__(self) -> object: ...


class _ConfigFactory(Protocol):
    def __call__(self) -> Config: ...


class _PowerManagerFactory(Protocol):
    def __call__(
        self,
        tray: _LifecyclePollingTray,
        *,
        config: Config | None = None,
    ) -> _MonitoringPowerManager: ...


class _LoadTrayDependencies(Protocol):
    def __call__(self) -> tuple[_EffectsEngineFactory, _ConfigFactory, _PowerManagerFactory]: ...


class _CreateEffectsEngine(Protocol):
    def __call__(self, EffectsEngine: _EffectsEngineFactory, *, backend: object) -> object: ...


class _PermissionIssueCallback(Protocol):
    def __call__(self, exc: Exception | None = None) -> None: ...


class _InstallPermissionCallback(Protocol):
    def __call__(self, engine: object, callback: _PermissionIssueCallback) -> None: ...


class _SelectBackend(Protocol):
    def __call__(self) -> tuple[object | None, object | None, object | None]: ...


class _SelectDiscoverySnapshot(Protocol):
    def __call__(self) -> object | None: ...


class _LoadIteDimensions(Protocol):
    def __call__(self) -> tuple[int, int]: ...


class _StartPowerMonitoring(Protocol):
    def __call__(
        self,
        tray: _LifecyclePollingTray,
        *,
        power_manager_cls: _PowerManagerFactory,
        config: Config | None,
    ) -> _MonitoringPowerManager: ...


class _StartAllPolling(Protocol):
    def __call__(self, tray: _LifecyclePollingTray, *, ite_num_rows: int, ite_num_cols: int) -> None: ...


class _MaybeAutostartEffect(Protocol):
    def __call__(self, tray: _AutostartEffectTray) -> None: ...


class _MenuFactory(Protocol):
    SEPARATOR: object

    def __call__(self, *items: object) -> object: ...


class _ItemFactory(Protocol):
    def __call__(self, text: str, action: object | None = None, **kwargs: object) -> object: ...


class _PystrayIcon(Protocol):
    def run(self) -> None: ...


class _PystrayIconFactory(Protocol):
    def __call__(self, name: str, image: object, title: str, menu: object) -> _PystrayIcon: ...


class _PystrayRuntime(Protocol):
    Icon: _PystrayIconFactory
    Menu: _MenuFactory


class _GetPystray(Protocol):
    def __call__(self) -> tuple[_PystrayRuntime, _ItemFactory]: ...


class _CreateIconForState(Protocol):
    def __call__(self, *, config: Config, is_off: bool, backend: object | None) -> object: ...


class _TrayStartupProtocol(Protocol):
    config: Config
    backend: object | None
    icon: _PystrayIcon | None
    is_off: bool

    def _notify(self, title: str, message: str) -> None: ...


class _BuildMenu(Protocol):
    def __call__(self, tray: _TrayStartupProtocol, *, pystray: _PystrayRuntime, item: _ItemFactory) -> object: ...


class _FlushPendingNotifications(Protocol):
    def __call__(self, tray: _TrayStartupProtocol) -> None: ...


@dataclass(frozen=True)
class TrayInitBindings:
    load_tray_dependencies: _LoadTrayDependencies
    migrate_builtin_profile_brightness_best_effort: Callable[[Config], None]
    select_backend_with_introspection: _SelectBackend
    select_device_discovery_snapshot: _SelectDiscoverySnapshot
    create_effects_engine: _CreateEffectsEngine
    load_ite_dimensions: _LoadIteDimensions
    install_permission_error_callback_best_effort: _InstallPermissionCallback
    configure_engine_software_targets: Callable[[_LifecyclePollingTray], None]
    start_power_monitoring: _StartPowerMonitoring
    start_all_polling: _StartAllPolling
    maybe_autostart_effect: _MaybeAutostartEffect


@dataclass(frozen=True)
class TrayRunBindings:
    get_pystray: _GetPystray
    create_icon_for_state: _CreateIconForState
    build_menu: _BuildMenu
    flush_pending_notifications: _FlushPendingNotifications
    logger: logging.Logger


def initialize_tray_state(
    tray: object,
    *,
    bindings: TrayInitBindings,
    notify_permission_issue: _PermissionIssueCallback,
) -> None:
    EffectsEngine, Config, PowerManager = bindings.load_tray_dependencies()

    config = Config()
    bindings.migrate_builtin_profile_brightness_best_effort(config)
    setattr(tray, "config", config)

    backend, backend_probe, backend_caps = bindings.select_backend_with_introspection()
    setattr(tray, "backend", backend)
    setattr(tray, "backend_probe", backend_probe)
    setattr(tray, "backend_caps", backend_caps)
    setattr(tray, "device_discovery", bindings.select_device_discovery_snapshot())
    setattr(tray, "selected_device_context", str(getattr(config, "tray_device_context", "keyboard") or "keyboard"))

    engine = bindings.create_effects_engine(EffectsEngine, backend=backend)
    setattr(tray, "engine", engine)

    ite_rows, ite_cols = bindings.load_ite_dimensions()
    setattr(tray, "_ite_rows", ite_rows)
    setattr(tray, "_ite_cols", ite_cols)

    runtime_tray = cast(_LifecyclePollingTray, tray)
    bindings.install_permission_error_callback_best_effort(engine, notify_permission_issue)
    bindings.configure_engine_software_targets(runtime_tray)

    power_manager = bindings.start_power_monitoring(runtime_tray, power_manager_cls=PowerManager, config=config)
    setattr(tray, "power_manager", power_manager)

    bindings.start_all_polling(runtime_tray, ite_num_rows=ite_rows, ite_num_cols=ite_cols)
    bindings.maybe_autostart_effect(cast(_AutostartEffectTray, tray))


def run_tray(tray: _TrayStartupProtocol, *, bindings: TrayRunBindings) -> None:
    pystray, item = bindings.get_pystray()

    bindings.logger.info("Creating tray icon...")
    icon = pystray.Icon(
        "keyrgb",
        bindings.create_icon_for_state(config=tray.config, is_off=tray.is_off, backend=tray.backend),
        "KeyRGB",
        menu=bindings.build_menu(tray, pystray=pystray, item=item),
    )
    tray.icon = icon

    bindings.logger.info("KeyRGB tray app started")
    bindings.logger.info("Current effect: %s", tray.config.effect)
    bindings.logger.info("Speed: %s, Brightness: %s", tray.config.speed, tray.config.brightness)
    bindings.flush_pending_notifications(tray)
    icon.run()
