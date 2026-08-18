"""Delegation mixin for thin `KeyRGBTray` wrapper methods.

The methods in this module intentionally resolve helper aliases through
`src.tray.app.application` at call time so tests can keep monkeypatching the
module-level names exported there.
"""

from __future__ import annotations

import threading

from src.tray.controllers.runtime_coordination import (
    active_transition_revision,
    capture_transition_revision,
    defer_ui_refresh,
    run_tray_observation_if_current,
    run_tray_transition,
)


def _application_module():
    from . import application

    return application


class KeyRGBTrayDelegateMixin:
    def run_runtime_transition(self, action):
        return run_tray_transition(self, action)

    def capture_runtime_transition_revision(self) -> int | None:
        return capture_transition_revision(self)

    def active_runtime_transition_revision(self) -> int | None:
        return active_transition_revision(self)

    def run_runtime_observation_if_current(self, revision: int | None, action):
        outcome = run_tray_observation_if_current(self, revision, action)
        return outcome.accepted, outcome.value

    def _update_icon(self, *, animate: bool = True):
        if defer_ui_refresh(self, icon=True, animate_icon=animate):
            return
        _application_module().update_tray_icon(self, animate=animate)

    def _update_menu(self):
        if defer_ui_refresh(self, menu=True):
            return
        _application_module().update_tray_menu(self)

    def _refresh_ui(self, *, animate_icon: bool = True, refresh_menu: bool = True) -> None:
        """Refresh the tray icon and, by default, rebuild the live menu.

        Automatic power/idle/hardware paths must pass ``refresh_menu=False``.
        Rebuilding a live AppIndicator/SNI menu during AC/DC or idle transitions
        can crash KDE plasmashell while the menu or its hover timer is active.
        """

        try:
            self._update_icon(animate=animate_icon)
        except TypeError:
            self._update_icon()
        if refresh_menu:
            self._update_menu()

    def _refresh_system_power_view(self) -> None:
        """Refresh the stored power-mode snapshot, then request a menu rebuild.

        Automatic AC/DC mode applies use this so the Power Mode menu shows the
        real mode. The menu rebuild is deferred through the runtime
        coordinator and executes after the transition completes — never
        mid-transition (KDE plasmashell QMenu host crash).
        """

        def _refresh_view() -> None:
            _application_module().refresh_system_power_snapshot(self)
            self._update_menu()

        run_tray_transition(self, _refresh_view)

    def _start_current_effect(self, **kwargs) -> bool:
        return bool(run_tray_transition(self, lambda: _application_module().start_current_effect(self, **kwargs)))

    def _apply_power_source_perkey_profile_transition(self) -> bool:
        return bool(
            run_tray_transition(
                self,
                lambda: _application_module().apply_power_source_perkey_profile_transition(self),
            )
        )

    def _on_effect_clicked(self, _icon, item):
        run_tray_transition(self, lambda: _application_module().callbacks.on_effect_clicked(self, item))

    def _on_effect_key_clicked(self, effect_name: str) -> None:
        run_tray_transition(self, lambda: _application_module().callbacks.on_effect_key_clicked(self, effect_name))

    def _on_speed_clicked(self, _icon, item):
        run_tray_transition(self, lambda: _application_module().callbacks.on_speed_clicked_cb(self, item))

    def _on_brightness_clicked(self, _icon, item):
        run_tray_transition(self, lambda: _application_module().callbacks.on_brightness_clicked_cb(self, item))

    def _on_device_context_clicked(self, context_key: str) -> None:
        run_tray_transition(self, lambda: _application_module().callbacks.on_device_context_clicked(self, context_key))

    def _on_selected_device_color_clicked(self, _icon, _item):
        run_tray_transition(self, lambda: _application_module().callbacks.on_selected_device_color_clicked(self))

    def _on_selected_device_brightness_clicked(self, _icon, item):
        run_tray_transition(
            self,
            lambda: _application_module().callbacks.on_selected_device_brightness_clicked(self, item),
        )

    def _on_selected_device_turn_off_clicked(self, _icon, _item):
        run_tray_transition(self, lambda: _application_module().callbacks.on_selected_device_turn_off_clicked(self))

    def _on_selected_device_turn_on_clicked(self, _icon, _item):
        run_tray_transition(self, lambda: _application_module().callbacks.on_selected_device_turn_on_clicked(self))

    def _on_software_effect_target_clicked(self, target_key: str) -> None:
        run_tray_transition(
            self,
            lambda: _application_module().callbacks.on_software_effect_target_clicked(self, target_key),
        )

    def _on_off_clicked(self, _icon, _item):
        run_tray_transition(self, lambda: _application_module().callbacks.on_off_clicked(self))

    def _on_turn_on_clicked(self, _icon, _item):
        run_tray_transition(self, lambda: _application_module().callbacks.on_turn_on_clicked(self))

    def _on_perkey_clicked(self, _icon, _item):
        _application_module().callbacks.on_perkey_clicked()

    def _on_tuxedo_gui_clicked(self, _icon, _item):
        _application_module().callbacks.on_uniform_gui_clicked()

    def _on_reactive_color_clicked(self, _icon, _item):
        _application_module().callbacks.on_reactive_color_gui_clicked()

    def _on_hardware_static_mode_clicked(self, _icon, _item):
        run_tray_transition(self, lambda: _application_module().callbacks.on_hardware_static_mode_clicked(self))

    def _on_hardware_color_clicked(self, _icon, _item):
        run_tray_transition(self, lambda: _application_module().callbacks.on_hardware_color_clicked(self))

    def _on_power_settings_clicked(self, _icon, _item):
        _application_module().callbacks.on_power_settings_clicked()

    def _on_power_mode_settings_clicked(self, _icon, _item):
        _application_module().callbacks.on_power_mode_settings_clicked()

    def _on_support_debug_clicked(self, _icon, _item):
        _application_module().callbacks.on_support_debug_clicked()

    def _on_backend_discovery_clicked(self, _icon, _item):
        _application_module().callbacks.on_backend_discovery_clicked()

    def _on_quit_clicked(self, icon, _item):
        from .lifecycle import shutdown_tray_runtime_best_effort

        def shutdown_then_stop_icon() -> None:
            try:
                shutdown_tray_runtime_best_effort(self)
            finally:
                icon.stop()

        threading.Thread(
            target=shutdown_then_stop_icon,
            name="keyrgb-tray-shutdown",
            daemon=True,
        ).start()

    def turn_off(self):
        return run_tray_transition(self, lambda: _application_module().power_turn_off(self))

    def restore(self):
        return run_tray_transition(self, lambda: _application_module().power_restore(self))

    def apply_brightness_from_power_policy(self, brightness: int) -> None:
        """Best-effort brightness apply used by PowerManager battery-saver.

        This must never crash the tray.
        """

        run_tray_transition(
            self,
            lambda: _application_module().apply_brightness_from_power_policy(self, brightness),
        )
