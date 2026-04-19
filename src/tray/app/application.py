"""Tray application facade.

This module keeps the stable `KeyRGBTray` surface and tray monkeypatch seams.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time

from . import _application_bindings as application_bindings
from . import _application_notifications as application_notifications
from . import _runtime_deps as app_runtime_deps
from . import _startup as tray_startup
from ._delegates import KeyRGBTrayDelegateMixin
from src.core.backends import BackendError, format_backend_error
from src.core.utils.safe_attrs import safe_str_attr


select_backend_with_introspection = app_runtime_deps.select_backend_with_introspection
select_device_discovery_snapshot = app_runtime_deps.select_device_discovery_snapshot
load_ite_dimensions = app_runtime_deps.load_ite_dimensions
build_permission_denied_message = tray_startup.build_permission_denied_message
create_effects_engine = tray_startup.create_effects_engine
flush_pending_notifications = tray_startup.flush_pending_notifications
install_permission_error_callback_best_effort = tray_startup.install_permission_error_callback_best_effort
migrate_builtin_profile_brightness_best_effort = tray_startup.migrate_builtin_profile_brightness_best_effort
apply_brightness_from_power_policy = app_runtime_deps.apply_brightness_from_power_policy
power_restore = app_runtime_deps.power_restore
power_turn_off = app_runtime_deps.power_turn_off
start_current_effect = app_runtime_deps.start_current_effect
configure_engine_software_targets = app_runtime_deps.configure_engine_software_targets
load_tray_dependencies = app_runtime_deps.load_tray_dependencies
maybe_autostart_effect = app_runtime_deps.maybe_autostart_effect
start_all_polling = app_runtime_deps.start_all_polling
start_power_monitoring = app_runtime_deps.start_power_monitoring
runtime = app_runtime_deps.runtime
icon_mod = app_runtime_deps.icon_mod
menu_mod = app_runtime_deps.menu_mod
update_tray_icon = app_runtime_deps.update_tray_icon
update_tray_menu = app_runtime_deps.update_tray_menu
is_permission_denied = app_runtime_deps.is_permission_denied
logger = logging.getLogger(__name__)
callbacks = app_runtime_deps.callbacks


def _init_bindings() -> application_bindings.TrayInitBindings:
    """Read current module aliases at call time to preserve monkeypatch seams."""

    return application_bindings.TrayInitBindings(
        load_tray_dependencies=load_tray_dependencies,
        migrate_builtin_profile_brightness_best_effort=migrate_builtin_profile_brightness_best_effort,
        select_backend_with_introspection=select_backend_with_introspection,
        select_device_discovery_snapshot=select_device_discovery_snapshot,
        create_effects_engine=create_effects_engine,
        load_ite_dimensions=load_ite_dimensions,
        install_permission_error_callback_best_effort=install_permission_error_callback_best_effort,
        configure_engine_software_targets=configure_engine_software_targets,
        start_power_monitoring=start_power_monitoring,
        start_all_polling=start_all_polling,
        maybe_autostart_effect=maybe_autostart_effect,
    )


def _run_bindings() -> application_bindings.TrayRunBindings:
    """Read current runtime collaborators at call time to preserve tests."""

    return application_bindings.TrayRunBindings(
        get_pystray=runtime.get_pystray,
        create_icon_for_state=icon_mod.create_icon_for_state,
        build_menu=menu_mod.build_menu,
        flush_pending_notifications=flush_pending_notifications,
        logger=logger,
    )


class KeyRGBTray(KeyRGBTrayDelegateMixin):
    """System tray application for KeyRGB."""

    backend: object | None

    def __init__(self) -> None:
        self.icon: object | None = None
        self.is_off = False
        self._power_forced_off = False
        self._user_forced_off = False
        self._idle_forced_off = False
        self._dim_temp_active = False
        self._dim_temp_target_brightness: int | None = None
        self._dim_backlight_baselines: dict[str, int] = {}
        self._dim_backlight_dimmed: dict[str, bool] = {}
        self._dim_screen_off = False
        self._dim_sync_suppressed_logged = False
        self._last_brightness = 25
        self._last_resume_at = 0.0

        # Event log throttling state (key -> last log monotonic time).
        self._event_last_at: dict[str, float] = {}

        # Notification state.
        self._permission_notice_sent: bool = False
        self._pending_notifications: list[tuple[str, str]] = []

        # Backend selection and startup wiring are used for capability-driven UI gating.
        application_bindings.initialize_tray_state(
            self,
            bindings=_init_bindings(),
            notify_permission_issue=self._notify_permission_issue,
        )

    # ---- notifications

    def _notify(self, title: str, message: str) -> None:
        """Best-effort user notification.

        Tries tray notifications first (pystray), then falls back to notify-send.
        If the icon isn't created yet (early startup), queues the message.
        """

        application_notifications.notify(
            self,
            title,
            message,
            logger=logger,
            shutil_module=shutil,
            subprocess_module=subprocess,
        )

    def _notify_permission_issue(self, exc: Exception | None = None) -> None:
        """Show a one-time notification for missing permissions."""

        application_notifications.notify_permission_issue(
            self,
            exc,
            logger=logger,
            is_permission_denied=is_permission_denied,
            build_permission_denied_message=build_permission_denied_message,
            backend_error_cls=BackendError,
            format_backend_error=format_backend_error,
            safe_str_attr=safe_str_attr,
        )

    # ---- logging helpers

    def _log_exception(self, msg: str, exc: Exception):
        application_notifications.log_exception(msg, exc, logger=logger)

    def _log_event(self, source: str, action: str, **fields) -> None:
        """Log a human-readable event cause.

        Intended to help diagnose flicker by showing *why* brightness/off/effect
        changes are being applied (menu vs. pollers vs. power policy, etc.).
        """

        application_notifications.log_event(
            self,
            source,
            action,
            logger=logger,
            monotonic_fn=time.monotonic,
            **fields,
        )

    # ---- run

    def run(self):
        application_bindings.run_tray(self, bindings=_run_bindings())
