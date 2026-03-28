"""Power management implementation."""

from __future__ import annotations

import logging
import threading
import time

from ._manager_helpers import (
    apply_power_source_actions,
    build_power_source_loop_inputs,
    is_intentionally_off,
)
from ..monitoring.acpi_monitoring import monitor_acpi_events
from ..monitoring.lid_monitoring import start_sysfs_lid_monitoring
from ..monitoring.login1_monitoring import monitor_prepare_for_sleep
from ..monitoring.power_supply_sysfs import read_on_ac_power
from ..power_policies.power_event_policy import (
    PowerEventInputs,
    PowerEventPolicy,
    RestoreKeyboard as RestoreFromEvent,
    TurnOffKeyboard as TurnOffFromEvent,
)
from ..power_policies.power_source_loop_policy import (
    PowerSourceLoopPolicy,
)
from src.core.config import Config
from src.core.profile.paths import get_active_profile
from src.core.utils.safe_attrs import safe_int_attr

logger = logging.getLogger(__name__)


class PowerManager:
    """Monitor system power events and control keyboard accordingly."""

    def __init__(self, keyboard_controller, *, config: Config | None = None):
        """Initialize power manager.

        Args:
            keyboard_controller: The keyboard controller instance (should have turn_off/restore methods)
        """

        self.kb_controller = keyboard_controller
        self._config = config or Config()
        self.monitoring = False
        self.monitor_thread = None
        self._battery_thread = None
        self._saved_state = None
        self._event_policy = PowerEventPolicy()

    def _is_enabled(self) -> bool:
        try:
            self._config.reload()
            return bool(getattr(self._config, "power_management_enabled", True))
        except Exception:
            return True

    def _flag(self, name: str, default: bool = True) -> bool:
        try:
            self._config.reload()
            return bool(getattr(self._config, name, default))
        except Exception:
            return default

    def start_monitoring(self):
        """Start monitoring power events in background thread."""
        if self.monitoring:
            return

        # Still start monitoring even if disabled, so enabling it later in config works.
        # Actual actions are gated in the event handlers.

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

        self._battery_thread = threading.Thread(target=self._battery_saver_loop, daemon=True)
        self._battery_thread.start()

    def stop_monitoring(self):
        """Stop monitoring power events."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        if self._battery_thread:
            self._battery_thread.join(timeout=2)

    # ---- battery saver (dim on AC unplug)

    def _battery_saver_loop(self) -> None:
        """Poll AC online state and apply a simple dim/restore policy.

        Requirements:
        - no root required
        - debounce rapid toggling
        - don't fight manual brightness changes while on battery
        """

        poll_interval_s = 2.0
        policy = PowerSourceLoopPolicy(debounce_seconds=3.0)

        while self.monitoring:
            try:
                on_ac = read_on_ac_power()
                if on_ac is None:
                    time.sleep(poll_interval_s)
                    continue

                loop_inputs = build_power_source_loop_inputs(
                    self._config,
                    self.kb_controller,
                    on_ac=bool(on_ac),
                    now_mono=float(time.monotonic()),
                    get_active_profile_fn=get_active_profile,
                    safe_int_attr_fn=safe_int_attr,
                )
                if loop_inputs is None:
                    time.sleep(poll_interval_s)
                    continue

                result = policy.update(loop_inputs)

                if result.skip:
                    time.sleep(poll_interval_s)
                    continue

                apply_power_source_actions(
                    kb_controller=self.kb_controller,
                    actions=getattr(result, "actions", []) or [],
                    apply_brightness=self._apply_brightness_policy,
                )

            except Exception as exc:
                logger.exception("Battery saver monitoring error: %s", exc)

            time.sleep(poll_interval_s)

    def _apply_brightness_policy(self, brightness: int) -> None:
        """Best-effort brightness change driven by power policy."""

        if brightness < 0:
            return

        try:
            # Prefer a dedicated hook on the controller if present.
            apply_fn = getattr(self.kb_controller, "apply_brightness_from_power_policy", None)
            if callable(apply_fn):
                apply_fn(int(brightness))
                return

            # Fallback: try a few known patterns.
            if hasattr(self.kb_controller, "engine"):
                try:
                    self._config.brightness = int(brightness)
                except Exception:
                    pass
                self.kb_controller.engine.set_brightness(int(brightness))
        except Exception as exc:
            logger.exception("Battery saver brightness apply failed: %s", exc)

    # ---- lid/suspend monitoring

    def _monitor_loop(self):
        """Main monitoring loop - watches for lid and suspend events."""
        # Use dbus-monitor to watch systemd-logind signals
        try:
            logger.info("Power monitoring started using dbus-monitor")

            monitor_prepare_for_sleep(
                is_running=lambda: self.monitoring,
                on_started=self._start_lid_monitor,
                on_suspend=self._on_suspend,
                on_resume=self._on_resume,
            )

        except FileNotFoundError:
            logger.warning("dbus-monitor not available, trying alternative method")
            self._monitor_acpi_events()
        except Exception as exc:
            logger.exception("Power monitoring error: %s", exc)

    def _start_lid_monitor(self):
        """Start a separate thread to monitor lid switch via sysfs."""
        start_sysfs_lid_monitoring(
            is_running=lambda: self.monitoring,
            on_lid_close=self._on_lid_close,
            on_lid_open=self._on_lid_open,
            logger=logger,
        )

    def _monitor_acpi_events(self):
        """Fallback method using acpi_listen for lid events."""
        monitor_acpi_events(
            is_running=lambda: self.monitoring,
            on_lid_close=self._on_lid_close,
            on_lid_open=self._on_lid_open,
            logger=logger,
        )

    def _handle_power_event(
        self,
        *,
        enabled: bool,
        action_enabled: bool,
        log_message: str,
        delay_s: float = 0.0,
        policy_method,
        expected_action_type,
        kb_method_name: str,
    ) -> None:
        if not enabled:
            return

        # Always feed events into the policy so it can record pre-event state
        # even when actions are disabled via configuration.
        try:
            result = policy_method(
                PowerEventInputs(
                    enabled=bool(enabled),
                    action_enabled=bool(action_enabled),
                    is_off=is_intentionally_off(
                        kb_controller=self.kb_controller,
                        config=self._config,
                        safe_int_attr_fn=safe_int_attr,
                    ),
                )
            )
        except Exception:
            return

        did_delay = False
        did_log = False

        for action in getattr(result, "actions", []) or []:
            if not isinstance(action, expected_action_type):
                continue

            if not bool(action_enabled):
                continue

            if not did_log:
                did_log = True
                logger.info(log_message)

            if delay_s > 0 and not did_delay:
                did_delay = True
                time.sleep(float(delay_s))

            try:
                fn = getattr(self.kb_controller, kb_method_name, None)
                if callable(fn):
                    fn()
            except Exception:
                pass

    def _on_suspend(self):
        """Called when system is about to suspend."""
        enabled = self._is_enabled()
        allow = self._flag("power_off_on_suspend", True)
        self._handle_power_event(
            enabled=bool(enabled),
            action_enabled=bool(allow),
            log_message="System suspending - turning off keyboard backlight",
            policy_method=self._event_policy.handle_power_off_event,
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )

    def _on_resume(self):
        """Called when system resumes from suspend."""
        enabled = self._is_enabled()
        allow = self._flag("power_restore_on_resume", True)
        self._handle_power_event(
            enabled=bool(enabled),
            action_enabled=bool(allow),
            log_message="System resumed - restoring keyboard backlight",
            delay_s=0.5,  # Give hardware time to wake up
            policy_method=self._event_policy.handle_power_restore_event,
            expected_action_type=RestoreFromEvent,
            kb_method_name="restore",
        )

    def _on_lid_close(self):
        """Called when lid is closed."""
        enabled = self._is_enabled()
        allow = self._flag("power_off_on_lid_close", True)
        self._handle_power_event(
            enabled=bool(enabled),
            action_enabled=bool(allow),
            log_message="Lid closed - turning off keyboard backlight",
            policy_method=self._event_policy.handle_power_off_event,
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )

    def _on_lid_open(self):
        """Called when lid is opened."""
        enabled = self._is_enabled()
        allow = self._flag("power_restore_on_lid_open", True)
        self._handle_power_event(
            enabled=bool(enabled),
            action_enabled=bool(allow),
            log_message="Lid opened - restoring keyboard backlight",
            policy_method=self._event_policy.handle_power_restore_event,
            expected_action_type=RestoreFromEvent,
            kb_method_name="restore",
        )
