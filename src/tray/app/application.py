"""Tray application class.

This module holds the `KeyRGBTray` class implementation.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time

from .backend import select_backend_with_introspection, select_device_discovery_snapshot
from . import callbacks
from ..controllers.lighting_controller import (
    apply_brightness_from_power_policy,
    power_restore,
    power_turn_off,
    start_current_effect,
)
from ..controllers.software_target_controller import configure_engine_software_targets
from .backend import load_ite_dimensions
from ..integrations.dependencies import load_tray_dependencies
from ..integrations import runtime
from .lifecycle import maybe_autostart_effect, start_all_polling, start_power_monitoring
from ..ui import icon as icon_mod
from ..ui import menu as menu_mod
from ..ui.refresh import update_icon as update_tray_icon
from ..ui.refresh import update_menu as update_tray_menu
from src.core.utils.exceptions import is_permission_denied
from src.core.utils.safe_attrs import safe_str_attr

logger = logging.getLogger(__name__)


class KeyRGBTray:
    """System tray application for KeyRGB."""

    def __init__(self) -> None:
        EffectsEngine, Config, PowerManager = load_tray_dependencies()

        self.config = Config()
        try:
            from src.core.profile import profiles as core_profiles

            core_profiles.migrate_builtin_profile_brightness(self.config)
        except Exception:  # @quality-exception exception-transparency: optional startup migration boundary
            pass
        self.icon = None
        self.is_off = False
        self._power_forced_off = False
        self._user_forced_off = False
        self._idle_forced_off = False
        self._dim_temp_active = False
        self._dim_temp_target_brightness = None
        self._last_brightness = 25
        self._last_resume_at = 0.0

        # Event log throttling state (key -> last log monotonic time).
        self._event_last_at: dict[str, float] = {}

        # Notification state.
        self._permission_notice_sent: bool = False
        self._pending_notifications: list[tuple[str, str]] = []

        # Backend selection is used for capability-driven UI gating.
        self.backend, self.backend_probe, self.backend_caps = select_backend_with_introspection()
        self.device_discovery = select_device_discovery_snapshot()
        self.selected_device_context = str(getattr(self.config, "tray_device_context", "keyboard") or "keyboard")

        try:
            self.engine = EffectsEngine(backend=self.backend)
        except TypeError:
            self.engine = EffectsEngine()
            set_backend = getattr(self.engine, "set_backend", None)
            if callable(set_backend):
                try:
                    set_backend(self.backend)
                except Exception:  # @quality-exception exception-transparency: compatibility backend fallback during engine init
                    pass

        self._ite_rows, self._ite_cols = load_ite_dimensions()

        # Allow the effects engine to surface permission issues (e.g. missing udev rules)
        # even when they happen in a background effect thread.
        try:
            setattr(self.engine, "_permission_error_cb", self._notify_permission_issue)
        except (AttributeError, RuntimeError):
            pass

        configure_engine_software_targets(self)

        self.power_manager = start_power_monitoring(self, power_manager_cls=PowerManager, config=self.config)
        start_all_polling(self, ite_num_rows=self._ite_rows, ite_num_cols=self._ite_cols)
        maybe_autostart_effect(self)

    # ---- notifications

    def _notify(self, title: str, message: str) -> None:
        """Best-effort user notification.

        Tries tray notifications first (pystray), then falls back to notify-send.
        If the icon isn't created yet (early startup), queues the message.
        """

        icon = getattr(self, "icon", None)
        if icon is None:
            self._pending_notifications.append((str(title), str(message)))
            return

        notify_fn = getattr(icon, "notify", None)
        if callable(notify_fn):
            try:
                notify_fn(str(message), str(title))
                return
            except TypeError:
                try:
                    notify_fn(str(message))
                    return
                except Exception:  # @quality-exception exception-transparency: best-effort tray notification fallback
                    pass
            except Exception:  # @quality-exception exception-transparency: best-effort tray notification backend boundary
                pass

        # Fallback for environments where pystray notifications are unavailable.
        try:
            if shutil.which("notify-send"):
                subprocess.run(
                    ["notify-send", str(title), str(message)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except OSError:
            return

    def _notify_permission_issue(self, exc: Exception | None = None) -> None:
        """Show a one-time notification for missing permissions."""

        if self._permission_notice_sent:
            return
        if exc is not None and not is_permission_denied(exc):
            return

        self._permission_notice_sent = True

        backend_name = safe_str_attr(self.backend, "name", default="") if self.backend is not None else ""

        repo_url = "https://github.com/Rainexn0b/keyRGB"

        # Keep the notification short; point to installer as the canonical fix.
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

        if exc is not None:
            logger.warning("Permission issue while applying lighting: %s", exc)

        self._notify("KeyRGB: Permission denied", "\n".join(msg_lines))

    # ---- logging helpers

    def _log_exception(self, msg: str, exc: Exception):
        logger.exception(msg, exc)

    def _log_event(self, source: str, action: str, **fields) -> None:
        """Log a human-readable event cause.

        Intended to help diagnose flicker by showing *why* brightness/off/effect
        changes are being applied (menu vs. pollers vs. power policy, etc.).
        """

        try:
            src = str(source)
            act = str(action)
        except Exception:  # @quality-exception exception-transparency: event logging must never break tray actions
            return

        parts: list[str] = []
        for k in sorted(fields.keys()):
            v = fields.get(k)
            try:
                parts.append(f"{k}={v}")
            except Exception:  # @quality-exception exception-transparency: tolerate broken field repr in debug logging
                parts.append(f"{k}=<unrepr>")

        msg = f"EVENT {src}:{act}"
        if parts:
            msg = f"{msg} " + " ".join(parts)

        # Throttle identical messages to avoid poller spam.
        try:
            now = time.monotonic()
            last = float(self._event_last_at.get(msg, 0.0) or 0.0)
            if now - last < 1.0:
                return
            self._event_last_at[msg] = now
        except Exception:  # @quality-exception exception-transparency: broken throttle state must not affect runtime
            pass

        try:
            logger.info("%s", msg)
        except Exception:  # @quality-exception exception-transparency: logging backend failure must not affect runtime
            return

    # ---- icon

    def _update_icon(self, *, animate: bool = True):
        update_tray_icon(self, animate=animate)

    # ---- menu

    def _update_menu(self):
        update_tray_menu(self)

    def _refresh_ui(self) -> None:
        """Refresh both icon and menu.

        Convenience wrapper to keep call sites small.
        """

        # Call the instance methods so unit tests can invoke this unbound on a
        # dummy object (without requiring real tray/icon dependencies).
        self._update_icon()
        self._update_menu()

    # ---- effect application

    def _start_current_effect(self, **kwargs):
        start_current_effect(self, **kwargs)

    # ---- menu callbacks

    def _on_effect_clicked(self, _icon, item):
        callbacks.on_effect_clicked(self, item)

    def _on_effect_key_clicked(self, effect_name: str) -> None:
        callbacks.on_effect_key_clicked(self, effect_name)

    def _on_speed_clicked(self, _icon, item):
        callbacks.on_speed_clicked_cb(self, item)

    def _on_brightness_clicked(self, _icon, item):
        callbacks.on_brightness_clicked_cb(self, item)

    def _on_device_context_clicked(self, context_key: str) -> None:
        callbacks.on_device_context_clicked(self, context_key)

    def _on_selected_device_color_clicked(self, _icon, _item):
        callbacks.on_selected_device_color_clicked(self)

    def _on_selected_device_brightness_clicked(self, _icon, item):
        callbacks.on_selected_device_brightness_clicked(self, item)

    def _on_selected_device_turn_off_clicked(self, _icon, _item):
        callbacks.on_selected_device_turn_off_clicked(self)

    def _on_software_effect_target_clicked(self, target_key: str) -> None:
        callbacks.on_software_effect_target_clicked(self, target_key)

    def _on_off_clicked(self, _icon, _item):
        callbacks.on_off_clicked(self)

    def _on_turn_on_clicked(self, _icon, _item):
        callbacks.on_turn_on_clicked(self)

    def _on_perkey_clicked(self, _icon, _item):
        callbacks.on_perkey_clicked()

    def _on_tuxedo_gui_clicked(self, _icon, _item):
        callbacks.on_uniform_gui_clicked()

    def _on_reactive_color_clicked(self, _icon, _item):
        callbacks.on_reactive_color_gui_clicked()

    def _on_hardware_static_mode_clicked(self, _icon, _item):
        callbacks.on_hardware_static_mode_clicked(self)

    def _on_hardware_color_clicked(self, _icon, _item):
        callbacks.on_hardware_color_clicked(self)

    def _on_power_settings_clicked(self, _icon, _item):
        callbacks.on_power_settings_clicked()

    def _on_support_debug_clicked(self, _icon, _item):
        callbacks.on_support_debug_clicked()

    def _on_backend_discovery_clicked(self, _icon, _item):
        callbacks.on_backend_discovery_clicked()

    def _on_tcc_profiles_gui_clicked(self, _icon, _item):
        callbacks.on_tcc_profiles_gui_clicked()

    def _on_tcc_profile_clicked(self, profile_id: str) -> None:
        callbacks.on_tcc_profile_clicked(self, profile_id)

    def _on_quit_clicked(self, icon, _item):
        self.power_manager.stop_monitoring()
        self.engine.stop()
        icon.stop()

    # ---- power callbacks (called by power manager)

    def turn_off(self):
        power_turn_off(self)

    def restore(self):
        power_restore(self)

    def apply_brightness_from_power_policy(self, brightness: int) -> None:
        """Best-effort brightness apply used by PowerManager battery-saver.

        This must never crash the tray.
        """

        apply_brightness_from_power_policy(self, brightness)

    # ---- run

    def run(self):
        pystray, item = runtime.get_pystray()

        logger.info("Creating tray icon...")
        self.icon = pystray.Icon(
            "keyrgb",
            icon_mod.create_icon_for_state(config=self.config, is_off=self.is_off, backend=self.backend),
            "KeyRGB",
            menu=menu_mod.build_menu(self, pystray=pystray, item=item),
        )

        logger.info("KeyRGB tray app started")
        logger.info("Current effect: %s", self.config.effect)
        logger.info("Speed: %s, Brightness: %s", self.config.speed, self.config.brightness)
        # Flush any queued notifications from early startup.
        pending_store = vars(self).get("_pending_notifications")
        pending = list(pending_store) if isinstance(pending_store, list) else []
        if isinstance(pending_store, list):
            pending_store.clear()
        for title, message in pending:
            self._notify(title, message)
        self.icon.run()
