"""Private bootstrap and run bindings for the tray application facade."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast, overload

from ._application_state import TrayBootstrapState
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


@dataclass(frozen=True)
class TrayRunState:
    config: Config
    is_off: bool
    backend: object | None


def build_tray_bootstrap_state(*, bindings: TrayInitBindings) -> TrayBootstrapState:
    EffectsEngine, Config, PowerManager = bindings.load_tray_dependencies()

    config = Config()
    bindings.migrate_builtin_profile_brightness_best_effort(config)

    backend, backend_probe, backend_caps = bindings.select_backend_with_introspection()
    engine = bindings.create_effects_engine(EffectsEngine, backend=backend)

    ite_rows, ite_cols = bindings.load_ite_dimensions()

    return TrayBootstrapState(
        config=config,
        engine=engine,
        power_manager_factory=PowerManager,
        backend=backend,
        backend_probe=backend_probe,
        backend_caps=backend_caps,
        device_discovery=bindings.select_device_discovery_snapshot(),
        selected_device_context=str(getattr(config, "tray_device_context", "keyboard") or "keyboard"),
        ite_rows=ite_rows,
        ite_cols=ite_cols,
    )


def start_tray_runtime(
    tray: object,
    *,
    state: TrayBootstrapState,
    bindings: TrayInitBindings,
    notify_permission_issue: _PermissionIssueCallback,
) -> _MonitoringPowerManager:
    runtime_tray = cast(_LifecyclePollingTray, tray)

    bindings.install_permission_error_callback_best_effort(state.engine, notify_permission_issue)
    bindings.configure_engine_software_targets(runtime_tray)

    power_manager = bindings.start_power_monitoring(
        runtime_tray,
        power_manager_cls=cast(_PowerManagerFactory, state.power_manager_factory),
        config=state.config,
    )
    bindings.start_all_polling(runtime_tray, ite_num_rows=state.ite_rows, ite_num_cols=state.ite_cols)
    bindings.maybe_autostart_effect(cast(_AutostartEffectTray, tray))
    return power_manager


def build_tray_run_state(tray: _TrayStartupProtocol) -> TrayRunState:
    return TrayRunState(config=tray.config, is_off=tray.is_off, backend=tray.backend)


def run_tray(
    tray: _TrayStartupProtocol,
    *,
    bindings: TrayRunBindings,
    state: TrayRunState | None = None,
) -> None:
    if state is None:
        state = build_tray_run_state(tray)

    pystray, item = bindings.get_pystray()

    bindings.logger.info("Creating tray icon...")
    icon = pystray.Icon(
        "keyrgb",
        bindings.create_icon_for_state(config=state.config, is_off=state.is_off, backend=state.backend),
        "KeyRGB",
        menu=bindings.build_menu(tray, pystray=pystray, item=item),
    )
    tray.icon = icon

    bindings.logger.info("KeyRGB tray app started")
    bindings.logger.info("Current effect: %s", state.config.effect)
    bindings.logger.info("Speed: %s, Brightness: %s", state.config.speed, state.config.brightness)
    bindings.flush_pending_notifications(tray)
    icon.run()
