"""Grouped runtime dependency seam for the tray application facade."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING, Protocol, cast


if TYPE_CHECKING:
    from src.core.config import Config
    from src.core.utils import exceptions as _exceptions
    from src.tray.app import backend as _backend
    from src.tray.app import callbacks as _callbacks
    from src.tray.app import lifecycle as _lifecycle
    from src.tray.controllers import lighting_controller as _lighting_controller
    from src.tray.controllers import software_target_controller as _software_target_controller
    from src.tray.integrations import dependencies as _dependencies
    from src.tray.integrations import runtime as _runtime
    from src.tray.ui import icon as _icon
    from src.tray.ui import menu as _menu
    from src.tray.ui import refresh as _refresh

    from ._application_bindings import _PowerManagerFactory
    from .lifecycle import _LifecyclePollingTray, _MonitoringPowerManager

    # Keep lazy runtime imports invisible at runtime while restoring static
    # reachability for buildpython's usage graph.
    _STATIC_USAGE_GRAPH_IMPORTS = (
        _exceptions,
        _backend,
        _callbacks,
        _lifecycle,
        _lighting_controller,
        _software_target_controller,
        _dependencies,
        _runtime,
        _icon,
        _menu,
        _refresh,
    )


class _CallbacksModule(Protocol):
    def on_effect_clicked(self, tray: object, item: object) -> None: ...

    def on_effect_key_clicked(self, tray: object, effect_name: str) -> None: ...

    def on_speed_clicked_cb(self, tray: object, item: object) -> None: ...

    def on_brightness_clicked_cb(self, tray: object, item: object) -> None: ...

    def on_device_context_clicked(self, tray: object, context_key: str) -> None: ...

    def on_selected_device_color_clicked(self, tray: object) -> None: ...

    def on_selected_device_brightness_clicked(self, tray: object, item: object) -> None: ...

    def on_selected_device_turn_off_clicked(self, tray: object) -> None: ...

    def on_software_effect_target_clicked(self, tray: object, target_key: str) -> None: ...

    def on_off_clicked(self, tray: object) -> None: ...

    def on_turn_on_clicked(self, tray: object) -> None: ...

    def on_perkey_clicked(self) -> None: ...

    def on_uniform_gui_clicked(self) -> None: ...

    def on_reactive_color_gui_clicked(self) -> None: ...

    def on_hardware_static_mode_clicked(self, tray: object) -> None: ...

    def on_hardware_color_clicked(self, tray: object) -> None: ...

    def on_power_settings_clicked(self) -> None: ...

    def on_support_debug_clicked(self) -> None: ...

    def on_backend_discovery_clicked(self) -> None: ...

    def on_tcc_profiles_gui_clicked(self) -> None: ...

    def on_tcc_profile_clicked(self, tray: object, profile_id: str) -> None: ...


class _RuntimeModule(Protocol):
    def get_pystray(self) -> tuple[object, object]: ...


class _IconModule(Protocol):
    def create_icon_for_state(self, *, config: object, is_off: bool, backend: object | None) -> object: ...


class _MenuModule(Protocol):
    def build_menu(self, tray: object, *, pystray: object, item: object) -> object: ...


class LazyModuleRef:
    """Module-like proxy that imports its target on first attribute access."""

    def __init__(self, module_path: str) -> None:
        self._module_path = module_path
        self._module: ModuleType | None = None

    def _load(self) -> ModuleType:
        module = self._module
        if module is None:
            module = import_module(self._module_path)
            self._module = module
        return module

    def __getattr__(self, name: str) -> object:
        return getattr(self._load(), name)


def _module(module_path: str) -> ModuleType:
    return import_module(module_path)


def select_backend_with_introspection():
    return _module("src.tray.app.backend").select_backend_with_introspection()


def select_device_discovery_snapshot():
    return _module("src.tray.app.backend").select_device_discovery_snapshot()


def load_ite_dimensions():
    return _module("src.tray.app.backend").load_ite_dimensions()


def apply_brightness_from_power_policy(tray: object, brightness: int) -> None:
    _module("src.tray.controllers.lighting_controller").apply_brightness_from_power_policy(tray, brightness)


def power_restore(tray: object) -> None:
    _module("src.tray.controllers.lighting_controller").power_restore(tray)


def power_turn_off(tray: object) -> None:
    _module("src.tray.controllers.lighting_controller").power_turn_off(tray)


def start_current_effect(tray: object, **kwargs: object) -> None:
    _module("src.tray.controllers.lighting_controller").start_current_effect(tray, **kwargs)


def configure_engine_software_targets(tray: object) -> None:
    _module("src.tray.controllers.software_target_controller").configure_engine_software_targets(tray)


def load_tray_dependencies():
    return _module("src.tray.integrations.dependencies").load_tray_dependencies()


def maybe_autostart_effect(tray: object) -> None:
    _module("src.tray.app.lifecycle").maybe_autostart_effect(tray)


def start_all_polling(tray: object, *, ite_num_rows: int, ite_num_cols: int) -> None:
    _module("src.tray.app.lifecycle").start_all_polling(
        tray,
        ite_num_rows=ite_num_rows,
        ite_num_cols=ite_num_cols,
    )


def start_power_monitoring(
    tray: _LifecyclePollingTray,
    *,
    power_manager_cls: _PowerManagerFactory,
    config: Config | None,
) -> _MonitoringPowerManager:
    return _module("src.tray.app.lifecycle").start_power_monitoring(
        tray,
        power_manager_cls=power_manager_cls,
        config=config,
    )


def update_tray_icon(tray: object, *, animate: bool = True) -> None:
    _module("src.tray.ui.refresh").update_icon(tray, animate=animate)


def update_tray_menu(tray: object) -> None:
    _module("src.tray.ui.refresh").update_menu(tray)


def is_permission_denied(exc: BaseException) -> bool:
    return bool(_module("src.core.utils.exceptions").is_permission_denied(exc))


callbacks: _CallbacksModule = cast(_CallbacksModule, LazyModuleRef("src.tray.app.callbacks"))
runtime: _RuntimeModule = cast(_RuntimeModule, LazyModuleRef("src.tray.integrations.runtime"))
icon_mod: _IconModule = cast(_IconModule, LazyModuleRef("src.tray.ui.icon"))
menu_mod: _MenuModule = cast(_MenuModule, LazyModuleRef("src.tray.ui.menu"))
