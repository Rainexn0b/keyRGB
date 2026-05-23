"""Power management implementation."""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, cast

from src.core.profile import profiles as perkey_profiles
from src.core.profile import runtime_activation as profile_runtime_activation

from . import _manager_brightness_execution as _brightness_execution, _manager_power_events as _power_events
from . import _manager_runtime_deps, _monitor_runner as power_monitor_runner
from ._manager_config import read_power_management_config_bool, reload_power_management_config
from ._manager_helpers import apply_power_source_actions, build_power_source_loop_inputs, is_intentionally_off
from ._manager_source_iteration import PowerSourceIterationPlan, classify_power_source_iteration
from ..policies import power_event_policy as _power_event_policy
from ..policies.power_source_loop_policy import PowerSourceLoopPolicy

if TYPE_CHECKING:
    from src.core.config import Config

logger = logging.getLogger(__name__)

PowerEventInputs = _power_event_policy.PowerEventInputs
PowerEventPolicy = _power_event_policy.PowerEventPolicy
RestoreFromEvent = _power_event_policy.RestoreKeyboard
TurnOffFromEvent = _power_event_policy.TurnOffKeyboard
_DEFAULT_POWER_SOURCE_POLL_INTERVAL_S = 0.5

classify_brightness_execution = _brightness_execution.classify_brightness_execution
execute_brightness_execution = _brightness_execution.execute_brightness_execution
apply_brightness_policy = _brightness_execution.apply_brightness_policy
sync_config_brightness = _brightness_execution.sync_config_brightness

build_power_event_inputs = _power_events.build_power_event_inputs
execute_power_event_plan = _power_events.execute_power_event_plan
invoke_keyboard_method = _power_events.invoke_keyboard_method
orchestrate_power_event = _power_events.orchestrate_power_event

get_system_power_status = _manager_runtime_deps.get_system_power_status
monitor_acpi_events = _manager_runtime_deps.monitor_acpi_events
monitor_prepare_for_sleep = _manager_runtime_deps.monitor_prepare_for_sleep
read_on_ac_power = _manager_runtime_deps.read_on_ac_power
safe_int_attr = _manager_runtime_deps.safe_int_attr
set_system_power_mode = _manager_runtime_deps.set_system_power_mode
start_sysfs_lid_monitoring = _manager_runtime_deps.start_sysfs_lid_monitoring

get_active_perkey_profile = perkey_profiles.get_active_profile
list_perkey_profiles = perkey_profiles.list_profiles


def activate_perkey_profile(tray: object, profile_name: str) -> None:
    profile_runtime_activation.activate_perkey_profile_runtime(
        cast(object, tray),
        profile_name,
        set_active_profile_fn=perkey_profiles.set_active_profile,
        load_per_key_colors_fn=perkey_profiles.load_per_key_colors,
        apply_profile_to_config_fn=perkey_profiles.apply_profile_to_config,
        mark_power_source_transition=True,
        refresh_menu=False,
        monotonic_fn=time.monotonic,
    )


_POWER_MANAGER_RUNTIME_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_POWER_MANAGER_MONITOR_ERRORS = _POWER_MANAGER_RUNTIME_ERRORS + (ImportError,)


class PowerManager:
    """Monitor system power events and control keyboard accordingly."""

    def __init__(self, keyboard_controller, *, config: Config | None = None):
        """Initialize power manager.

        Args:
            keyboard_controller: The keyboard controller instance (should have turn_off/restore methods)
        """

        from src.core.config import Config as _Config

        self.kb_controller = keyboard_controller
        self._config = config or _Config()
        self.monitoring = False
        self.monitor_thread = None
        self._battery_thread = None
        self._saved_state = None
        self._event_policy = PowerEventPolicy()
        self._stable_on_ac: bool | None = None
        self._pending_on_ac: bool | None = None
        self._lid_closed = False

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
        if self._lid_closed and self._flag("power_off_on_lid_close", True):
            time.sleep(poll_interval_s)
            return True

        if self._keyboard_is_power_event_forced_off():
            time.sleep(poll_interval_s)
            return True

        plan = self._classify_battery_saver_iteration(policy)
        return self._execute_battery_saver_iteration_plan(plan, poll_interval_s=poll_interval_s)

    def _keyboard_is_power_event_forced_off(self) -> bool:
        if getattr(self.kb_controller, "_power_forced_off", None) is True:
            return True

        idle_state = getattr(self.kb_controller, "tray_idle_power_state", None)
        return getattr(idle_state, "power_forced_off", None) is True

    def _classify_battery_saver_iteration(
        self,
        policy: PowerSourceLoopPolicy,
    ) -> PowerSourceIterationPlan:
        now_mono = float(time.monotonic())
        raw_on_ac = read_on_ac_power()
        stable_on_ac = self._stabilize_on_ac_state(raw_on_ac)
        return classify_power_source_iteration(
            raw_on_ac=stable_on_ac,
            build_loop_inputs_fn=lambda on_ac: build_power_source_loop_inputs(
                self._config,
                self.kb_controller,
                on_ac=on_ac,
                now_mono=now_mono,
                get_power_mode_status_fn=get_system_power_status,
                get_active_perkey_profile_fn=get_active_perkey_profile,
                safe_int_attr_fn=safe_int_attr,
            ),
            policy=policy,
        )

    def _execute_battery_saver_iteration_plan(
        self,
        plan: PowerSourceIterationPlan,
        *,
        poll_interval_s: float,
    ) -> bool:
        if plan.should_sleep:
            time.sleep(poll_interval_s)
            return True

        apply_power_source_actions(
            kb_controller=self.kb_controller,
            actions=plan.actions,
            apply_brightness=self._apply_brightness_policy,
            activate_power_mode=self._activate_power_source_mode,
            activate_perkey_profile=self._activate_power_source_perkey_profile,
        )
        return False

    def _battery_saver_loop(self) -> None:
        """Poll AC online state and apply a simple dim/restore policy.

        Requirements:
        - no root required
        - debounce rapid toggling
        - don't fight manual brightness changes while on battery
        """

        policy = PowerSourceLoopPolicy(debounce_seconds=3.0)

        while self.monitoring:
            poll_interval_s = _DEFAULT_POWER_SOURCE_POLL_INTERVAL_S
            did_sleep = self._run_recoverable_runtime_boundary(
                lambda: self._run_battery_saver_iteration(policy, poll_interval_s=poll_interval_s),
                log_message="Battery saver monitoring iteration failed",
                fallback=False,
            )
            if did_sleep:
                continue

            time.sleep(poll_interval_s)

    def _stabilize_on_ac_state(self, raw_on_ac: bool | None) -> bool | None:
        if raw_on_ac is None:
            self._pending_on_ac = None
            return self._stable_on_ac

        current_raw = bool(raw_on_ac)
        if self._stable_on_ac is None:
            self._stable_on_ac = current_raw
            self._pending_on_ac = None
            return self._stable_on_ac

        if current_raw == self._stable_on_ac:
            self._pending_on_ac = None
            return self._stable_on_ac

        if self._pending_on_ac != current_raw:
            self._pending_on_ac = current_raw
            return self._stable_on_ac

        self._stable_on_ac = current_raw
        self._pending_on_ac = None
        return self._stable_on_ac

    def _apply_brightness_policy(self, brightness: int) -> None:
        """Best-effort brightness change driven by power policy."""
        apply_brightness_policy(
            self.kb_controller,
            brightness,
            run_boundary_fn=self._run_recoverable_runtime_boundary,
            config=self._config,
            sync_config_fn=self._sync_config_brightness,
        )

    def _sync_config_brightness(self, brightness: int) -> int:
        return sync_config_brightness(self._config, brightness, logger=logger)

    def _activate_power_source_mode(self, mode) -> None:
        applied = set_system_power_mode(mode, allow_interactive=False)
        if not bool(applied):
            logger.warning("Power-source mode activation did not apply for %s", getattr(mode, "value", mode))

    def _activate_power_source_perkey_profile(self, profile_name: str) -> None:
        available_profiles = {str(name) for name in list_perkey_profiles()}
        if str(profile_name) not in available_profiles:
            logger.warning("Skipping missing power-source lighting profile '%s'", profile_name)
            return
        activate_perkey_profile(self.kb_controller, str(profile_name))

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
        orchestrate_power_event(
            enabled=enabled,
            action_enabled=action_enabled,
            delay_s=delay_s,
            policy_method=policy_method,
            expected_action_type=expected_action_type,
            evaluate_policy_fn=self._evaluate_power_event_policy,
            execute_plan_fn=lambda plan: self._execute_power_event_plan(
                plan,
                log_message=log_message,
                kb_method_name=kb_method_name,
            ),
        )

    def _get_keyboard_intent_state(self):
        return self._run_recoverable_runtime_boundary(
            lambda: is_intentionally_off(
                kb_controller=self.kb_controller,
                config=self._config,
                safe_int_attr_fn=safe_int_attr,
            ),
            log_message="Power event intent-state evaluation failed",
        )

    def _evaluate_power_event_policy(self, *, enabled: bool, action_enabled: bool, policy_method):
        is_off = self._get_keyboard_intent_state()
        if is_off is None:
            return None

        inputs = build_power_event_inputs(
            enabled=enabled,
            action_enabled=action_enabled,
            is_off=is_off,
        )

        return self._run_recoverable_runtime_boundary(
            lambda: policy_method(inputs),
            log_message="Power event policy evaluation failed",
        )

    def _execute_power_event_plan(self, plan, *, log_message: str, kb_method_name: str) -> None:
        execute_power_event_plan(
            plan=plan,
            log_message=log_message,
            kb_method_name=kb_method_name,
            log_info_fn=logger.info,
            sleep_fn=time.sleep,
            invoke_keyboard_method_fn=self._invoke_keyboard_method,
        )

    def _invoke_keyboard_method(self, method_name: str) -> None:
        invoke_keyboard_method(
            kb_controller=self.kb_controller,
            method_name=method_name,
            run_recoverable_runtime_boundary_fn=self._run_recoverable_runtime_boundary,
        )

    def _dispatch_power_event_route(
        self,
        *,
        flag_name: str,
        log_message: str,
        policy_method,
        expected_action_type,
        kb_method_name: str,
        delay_s: float = 0.0,
    ) -> None:
        enabled = self._is_enabled()
        action_enabled = self._flag(flag_name, True)
        self._handle_power_event(
            enabled=enabled,
            action_enabled=action_enabled,
            log_message=log_message,
            delay_s=delay_s,
            policy_method=policy_method,
            expected_action_type=expected_action_type,
            kb_method_name=kb_method_name,
        )

    def _on_suspend(self):
        """Called when system is about to suspend."""
        self._dispatch_power_event_route(
            flag_name="power_off_on_suspend",
            log_message="System suspending - turning off keyboard backlight",
            policy_method=self._event_policy.handle_power_off_event,
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )

    def _on_resume(self):
        """Called when system resumes from suspend."""
        self._dispatch_power_event_route(
            flag_name="power_restore_on_resume",
            log_message="System resumed - restoring keyboard backlight",
            delay_s=0.5,
            policy_method=self._event_policy.handle_power_restore_event,
            expected_action_type=RestoreFromEvent,
            kb_method_name="restore",
        )

    def _on_lid_close(self):
        """Called when lid is closed."""
        self._lid_closed = True
        self._dispatch_power_event_route(
            flag_name="power_off_on_lid_close",
            log_message="Lid closed - turning off keyboard backlight",
            policy_method=self._event_policy.handle_power_off_event,
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )

    def _on_lid_open(self):
        """Called when lid is opened."""
        self._lid_closed = False
        self._dispatch_power_event_route(
            flag_name="power_restore_on_lid_open",
            log_message="Lid opened - restoring keyboard backlight",
            policy_method=self._event_policy.handle_power_restore_event,
            expected_action_type=RestoreFromEvent,
            kb_method_name="restore",
        )
