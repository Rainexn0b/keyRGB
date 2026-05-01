"""Delegation mixin for thin `KeyRGBTray` wrapper methods.

The methods in this module intentionally resolve helper aliases through
`src.tray.app.application` at call time so tests can keep monkeypatching the
module-level names exported there.
"""

from __future__ import annotations


def _application_module():
    from . import application

    return application


class KeyRGBTrayDelegateMixin:
    def _update_icon(self, *, animate: bool = True):
        _application_module().update_tray_icon(self, animate=animate)

    def _update_menu(self):
        _application_module().update_tray_menu(self)

    def _refresh_ui(self, *, animate_icon: bool = True) -> None:
        """Refresh both icon and menu.

        Convenience wrapper to keep call sites small.
        """

        try:
            self._update_icon(animate=animate_icon)
        except TypeError:
            self._update_icon()
        self._update_menu()

    def _start_current_effect(self, **kwargs):
        _application_module().start_current_effect(self, **kwargs)

    def _on_effect_clicked(self, _icon, item):
        _application_module().callbacks.on_effect_clicked(self, item)

    def _on_effect_key_clicked(self, effect_name: str) -> None:
        _application_module().callbacks.on_effect_key_clicked(self, effect_name)

    def _on_speed_clicked(self, _icon, item):
        _application_module().callbacks.on_speed_clicked_cb(self, item)

    def _on_brightness_clicked(self, _icon, item):
        _application_module().callbacks.on_brightness_clicked_cb(self, item)

    def _on_device_context_clicked(self, context_key: str) -> None:
        _application_module().callbacks.on_device_context_clicked(self, context_key)

    def _on_selected_device_color_clicked(self, _icon, _item):
        _application_module().callbacks.on_selected_device_color_clicked(self)

    def _on_selected_device_brightness_clicked(self, _icon, item):
        _application_module().callbacks.on_selected_device_brightness_clicked(self, item)

    def _on_selected_device_turn_off_clicked(self, _icon, _item):
        _application_module().callbacks.on_selected_device_turn_off_clicked(self)

    def _on_software_effect_target_clicked(self, target_key: str) -> None:
        _application_module().callbacks.on_software_effect_target_clicked(self, target_key)

    def _on_off_clicked(self, _icon, _item):
        _application_module().callbacks.on_off_clicked(self)

    def _on_turn_on_clicked(self, _icon, _item):
        _application_module().callbacks.on_turn_on_clicked(self)

    def _on_perkey_clicked(self, _icon, _item):
        _application_module().callbacks.on_perkey_clicked()

    def _on_tuxedo_gui_clicked(self, _icon, _item):
        _application_module().callbacks.on_uniform_gui_clicked()

    def _on_reactive_color_clicked(self, _icon, _item):
        _application_module().callbacks.on_reactive_color_gui_clicked()

    def _on_hardware_static_mode_clicked(self, _icon, _item):
        _application_module().callbacks.on_hardware_static_mode_clicked(self)

    def _on_hardware_color_clicked(self, _icon, _item):
        _application_module().callbacks.on_hardware_color_clicked(self)

    def _on_power_settings_clicked(self, _icon, _item):
        _application_module().callbacks.on_power_settings_clicked()

    def _on_support_debug_clicked(self, _icon, _item):
        _application_module().callbacks.on_support_debug_clicked()

    def _on_backend_discovery_clicked(self, _icon, _item):
        _application_module().callbacks.on_backend_discovery_clicked()

    def _on_tcc_profiles_gui_clicked(self, _icon, _item):
        _application_module().callbacks.on_tcc_profiles_gui_clicked()

    def _on_tcc_profile_clicked(self, profile_id: str) -> None:
        _application_module().callbacks.on_tcc_profile_clicked(self, profile_id)

    def _on_quit_clicked(self, icon, _item):
        self.power_manager.stop_monitoring()
        self.engine.stop()
        engine_close = getattr(self.engine, "close", None)
        if callable(engine_close):
            try:
                engine_close()
            except (AttributeError, OSError, RuntimeError, ValueError):
                pass
        icon.stop()

    def turn_off(self):
        _application_module().power_turn_off(self)

    def restore(self):
        _application_module().power_restore(self)

    def apply_brightness_from_power_policy(self, brightness: int) -> None:
        """Best-effort brightness apply used by PowerManager battery-saver.

        This must never crash the tray.
        """

        _application_module().apply_brightness_from_power_policy(self, brightness)
