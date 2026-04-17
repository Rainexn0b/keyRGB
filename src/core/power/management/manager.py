"""Power management implementation."""

from __future__ import annotations

import logging
import threading
import time

from . import _monitor_runner as power_monitor_runner
from ._manager_config import read_power_management_config_bool, reload_power_management_config
from ._manager_helpers import apply_power_source_actions, build_power_source_loop_inputs, is_intentionally_off
from ..policies.power_event_policy import PowerEventInputs, PowerEventPolicy
from ..policies.power_event_policy import RestoreKeyboard as RestoreFromEvent, TurnOffKeyboard as TurnOffFromEvent
from ..policies.power_source_loop_policy import PowerSourceLoopPolicy
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

    def _run_recoverable_runtime_boundary(self, action, *, log_message: str, fallback=None):
        try:
            return action()
        except _POWER_MANAGER_RUNTIME_ERRORS:  # @quality-exception exception-transparency: shared power-manager policy/controller runtime seams must keep recoverable runtime failures logged and contained while unexpected defects still propagate
            logger.exception(log_message)
            return fallback

    def start_monitoring(self):
        """Start monitoring power events in background thread."""
        # Still start monitoring even if disabled, so enabling it later in config works.
        # Actual actions are gated in the event handlers.
        power_monitor_runner.start_monitoring(self, thread_factory=threading.Thread)

    def stop_monitoring(self):
        """Stop monitoring power events."""
        power_monitor_runner.stop_monitoring(self, join_timeout_s=2)

    # ---- battery saver (dim on AC unplug)

    def _run_battery_saver_iteration(
        self,
        policy: PowerSourceLoopPolicy,
        *,
        poll_interval_s: float,
    ) -> bool:
        on_ac = read_on_ac_power()
        if on_ac is None:
            time.sleep(poll_interval_s)
            return True

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
            return True

        result = policy.update(loop_inputs)

        if result.skip:
            time.sleep(poll_interval_s)
            return True

        apply_power_source_actions(
            kb_controller=self.kb_controller,
            actions=getattr(result, "actions", []) or [],
            apply_brightness=self._apply_brightness_policy,
        )
        return False

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
            did_sleep = self._run_recoverable_runtime_boundary(
                lambda: self._run_battery_saver_iteration(policy, poll_interval_s=poll_interval_s),
                log_message="Battery saver monitoring iteration failed",
                fallback=False,
            )
            if did_sleep:
                continue

            time.sleep(poll_interval_s)

    def _apply_brightness_policy(self, brightness: int) -> None:
        """Best-effort brightness change driven by power policy."""

        if brightness < 0:
            return

        brightness = int(brightness)

        def _apply() -> None:
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

        self._run_recoverable_runtime_boundary(_apply, log_message="Battery saver brightness apply failed")

    def _sync_config_brightness(self, brightness: int) -> None:
        try:
            self._config.brightness = brightness
        except (AttributeError, TypeError, ValueError, RuntimeError):
            logger.warning("Failed to mirror power-policy brightness into config", exc_info=True)

    # ---- lid/suspend monitoring

    def _monitor_loop(self):
        """Main monitoring loop - watches for lid and suspend events."""
        power_monitor_runner.run_monitor_loop(
            self,
            logger=logger,
            monitor_prepare_for_sleep_fn=monitor_prepare_for_sleep,
            monitor_errors=_POWER_MANAGER_MONITOR_ERRORS,
            start_lid_monitor_fn=self._start_lid_monitor,
            monitor_acpi_events_fn=self._monitor_acpi_events,
        )

    def _start_lid_monitor(self):
        """Start a separate thread to monitor lid switch via sysfs."""
        power_monitor_runner.start_lid_monitoring(
            self,
            logger=logger,
            start_sysfs_lid_monitoring_fn=start_sysfs_lid_monitoring,
        )

    def _monitor_acpi_events(self):
        """Fallback method using acpi_listen for lid events."""
        power_monitor_runner.run_acpi_monitoring(
            self,
            logger=logger,
            monitor_acpi_events_fn=monitor_acpi_events,
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
        def _evaluate():
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

        return self._run_recoverable_runtime_boundary(_evaluate, log_message="Power event policy evaluation failed")

    def _invoke_keyboard_method(self, method_name: str) -> None:
        def _invoke() -> None:
            fn = getattr(self.kb_controller, method_name, None)
            if callable(fn):
                fn()

        self._run_recoverable_runtime_boundary(
            _invoke,
            log_message=f"Power event keyboard action '{method_name}' failed",
        )

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
