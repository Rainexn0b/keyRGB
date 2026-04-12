"""Power management implementation."""

from __future__ import annotations

import logging
import threading
import time

from ._manager_config import read_power_management_config_bool, reload_power_management_config
from ._manager_helpers import (
    apply_power_source_actions,
    build_power_source_loop_inputs,
    is_intentionally_off,
)
from ..policies.power_event_policy import (
    PowerEventInputs,
    PowerEventPolicy,
    RestoreKeyboard as RestoreFromEvent,
    TurnOffKeyboard as TurnOffFromEvent,
)
from ..policies.power_source_loop_policy import (
    PowerSourceLoopPolicy,
)
from src.core.config import Config
from src.core.power.monitoring.acpi_monitoring import monitor_acpi_events
from src.core.power.monitoring.lid_monitoring import start_sysfs_lid_monitoring
from src.core.power.monitoring.login1_monitoring import monitor_prepare_for_sleep
from src.core.power.monitoring.power_supply_sysfs import read_on_ac_power
from src.core.profile.paths import get_active_profile
from src.core.utils.safe_attrs import safe_int_attr

logger = logging.getLogger(__name__)

_POWER_MANAGER_RUNTIME_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_POWER_MANAGER_MONITOR_ERRORS = _POWER_MANAGER_RUNTIME_ERRORS + (ImportError,)


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

    def _reload_config(self, *, context: str) -> bool:
        return reload_power_management_config(self._config, context=context, logger=logger)

    def _read_config_bool(self, *names: str, default: bool) -> bool:
        return read_power_management_config_bool(self._config, *names, default=default, logger=logger)

    def _power_management_enabled_value(self) -> bool:
        return self._read_config_bool("power_management_enabled", "management_enabled", default=True)

    def _is_enabled(self) -> bool:
        if not self._reload_config(context="power management enablement check"):
            return True

        return self._power_management_enabled_value()

    def _flag(self, name: str, default: bool = True) -> bool:
        if not self._reload_config(context=f"power management flag '{name}'"):
            return default

        return self._read_config_bool(name, default=default)

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

            except _POWER_MANAGER_RUNTIME_ERRORS:  # @quality-exception exception-transparency: battery-saver polling crosses sysfs monitoring, config/profile reads, policy evaluation, and controller actions and must remain non-fatal for recoverable failures
                logger.exception("Battery saver monitoring iteration failed")

            time.sleep(poll_interval_s)

    def _apply_brightness_policy(self, brightness: int) -> None:
        """Best-effort brightness change driven by power policy."""

        if brightness < 0:
            return

        brightness = int(brightness)

        try:
            # Prefer a dedicated hook on the controller if present.
            apply_fn = getattr(self.kb_controller, "apply_brightness_from_power_policy", None)
            if callable(apply_fn):
                apply_fn(brightness)
                return

            # Fallback: try a few known patterns.
            engine = getattr(self.kb_controller, "engine", None)
            if engine is not None:
                self._sync_config_brightness(brightness)
                engine.set_brightness(brightness)
        except _POWER_MANAGER_RUNTIME_ERRORS:  # @quality-exception exception-transparency: brightness application crosses a runtime controller boundary and must remain best-effort for recoverable failures
            logger.exception("Battery saver brightness apply failed")

    def _sync_config_brightness(self, brightness: int) -> None:
        try:
            self._config.brightness = brightness
        except (AttributeError, TypeError, ValueError, RuntimeError):
            logger.warning("Failed to mirror power-policy brightness into config", exc_info=True)

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
        except _POWER_MANAGER_MONITOR_ERRORS:  # @quality-exception exception-transparency: login1 monitoring is an external runtime boundary and power monitoring must remain available on recoverable runtime failures
            logger.exception("Power monitoring error")

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
        result = self._evaluate_power_event_policy(
            enabled=enabled,
            action_enabled=action_enabled,
            policy_method=policy_method,
        )
        if result is None:
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

            self._invoke_keyboard_method(kb_method_name)

    def _evaluate_power_event_policy(self, *, enabled: bool, action_enabled: bool, policy_method):
        try:
            return policy_method(
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
        except _POWER_MANAGER_RUNTIME_ERRORS:  # @quality-exception exception-transparency: power-event policy evaluation crosses controller-state sampling and policy boundaries and must remain non-fatal for recoverable failures
            logger.exception("Power event policy evaluation failed")
            return None

    def _invoke_keyboard_method(self, method_name: str) -> None:
        try:
            fn = getattr(self.kb_controller, method_name, None)
            if callable(fn):
                fn()
        except _POWER_MANAGER_RUNTIME_ERRORS:  # @quality-exception exception-transparency: power-event keyboard actions cross a runtime controller boundary and must remain non-fatal for recoverable monitor-thread failures
            logger.exception("Power event keyboard action '%s' failed", method_name)

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
