"""Power management implementation."""

from __future__ import annotations

# @quality-exception file-size-analysis: PowerManager public facade after battery-saver extract; remaining methods are thin event/monitor delegates
import logging
import threading
import time
from typing import TYPE_CHECKING

from src.core.profile import profiles as perkey_profiles, runtime_activation as profile_runtime_activation

from ..policies import power_event_policy as _power_event_policy
from ..policies.power_source_loop_policy import PowerSourceLoopPolicy
from . import (
    _manager_battery_saver as _battery_saver,
    _manager_brightness_execution as _brightness_execution,
    _manager_power_events as _power_events,
    _manager_runtime_deps,
    _monitor_runner as power_monitor_runner,
)
from ._manager_config import read_power_management_config_bool, reload_power_management_config
from ._manager_helpers import (  # noqa: F401
    apply_power_source_actions,
    build_power_source_loop_inputs,
    is_intentionally_off,
)
from ._manager_source_iteration import classify_power_source_iteration  # noqa: F401

if TYPE_CHECKING:
    from src.core.config import Config

logger = logging.getLogger(__name__)

PowerEventInputs = _power_event_policy.PowerEventInputs
PowerEventPolicy = _power_event_policy.PowerEventPolicy
RestoreFromEvent = _power_event_policy.RestoreKeyboard
TurnOffFromEvent = _power_event_policy.TurnOffKeyboard

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
read_lid_state = _manager_runtime_deps.read_lid_state
read_on_ac_power = _manager_runtime_deps.read_on_ac_power
safe_int_attr = _manager_runtime_deps.safe_int_attr
set_system_power_mode = _manager_runtime_deps.set_system_power_mode
start_sysfs_lid_monitoring = _manager_runtime_deps.start_sysfs_lid_monitoring

get_active_perkey_profile = perkey_profiles.get_active_profile
list_perkey_profiles = perkey_profiles.list_profiles

# Stable test/monkeypatch seam retained from the battery-saver extraction.
_DEFAULT_POWER_SOURCE_POLL_INTERVAL_S = _battery_saver._DEFAULT_POWER_SOURCE_POLL_INTERVAL_S


def _run_tray_transition_if_available(tray: object, action):
    try:
        run_transition = vars(tray).get("run_runtime_transition")
    except TypeError:
        run_transition = None
    if run_transition is None and callable(getattr(type(tray), "run_runtime_transition", None)):
        run_transition = tray.run_runtime_transition  # type: ignore[attr-defined]
    return run_transition(action) if callable(run_transition) else action()


def _capture_tray_transition_revision(tray: object) -> int | None:
    if not callable(getattr(type(tray), "capture_runtime_transition_revision", None)):
        return None
    return tray.capture_runtime_transition_revision()  # type: ignore[attr-defined]


def _active_tray_transition_revision(tray: object) -> int | None:
    if not callable(getattr(type(tray), "active_runtime_transition_revision", None)):
        return None
    return tray.active_runtime_transition_revision()  # type: ignore[attr-defined]


def _tray_callable(tray: object, name: str):
    try:
        instance_callback = vars(tray).get(name)
    except TypeError:
        instance_callback = None
    if callable(instance_callback):
        return instance_callback
    attr = getattr(tray, name, None)
    if callable(attr):
        return attr
    return None


def activate_perkey_profile(tray: object, profile_name: str) -> None:
    def activate_transition() -> None:
        start_current_effect = _tray_callable(tray, "_start_current_effect")
        update_icon = _tray_callable(tray, "_update_icon")
        apply_transition = _tray_callable(tray, "_apply_power_source_perkey_profile_transition")

        def _is_power_forced_off() -> bool:
            try:
                tray_vars = vars(tray)
            except TypeError:
                tray_vars = {}
            if "_power_forced_off" in tray_vars:
                return bool(tray_vars["_power_forced_off"])
            owner = getattr(tray, "tray_idle_power_state", None)
            if owner is None:
                return False
            return getattr(owner, "power_forced_off", False) is True

        def _store_secondary_lighting(payload) -> None:
            try:
                vars(tray)["_active_secondary_lighting"] = payload
            except (AttributeError, TypeError):
                return

        def _mark_power_source_transition(name: str, changed_at: float) -> None:
            try:
                tray._last_power_source_transition_at = float(changed_at)  # type: ignore[attr-defined]
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
                pass
            try:
                tray._last_power_source_transition_profile_name = str(name)  # type: ignore[attr-defined]
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
                pass
            owner = getattr(tray, "tray_idle_power_state", None)
            if owner is None:
                return
            try:
                owner.last_power_source_transition_at = float(changed_at)
                owner.last_power_source_transition_profile_name = str(name)
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
                return

        def _set_is_off(value: bool) -> None:
            try:
                tray.is_off = bool(value)  # type: ignore[attr-defined]
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
                return

        profile_runtime_activation.activate_perkey_profile_runtime(
            getattr(tray, "config", None),
            profile_name,
            set_active_profile_fn=perkey_profiles.set_active_profile,
            load_per_key_colors_fn=perkey_profiles.load_per_key_colors,
            apply_profile_to_config_fn=perkey_profiles.apply_profile_to_config,
            load_secondary_lighting_fn=perkey_profiles.load_secondary_lighting,
            is_power_forced_off_fn=_is_power_forced_off,
            set_is_off_fn=_set_is_off,
            store_secondary_lighting_fn=_store_secondary_lighting,
            apply_runtime_transition_fn=((lambda: bool(apply_transition())) if apply_transition is not None else None),
            start_current_effect_fn=((lambda: start_current_effect()) if start_current_effect is not None else None),
            update_icon_fn=((lambda: update_icon()) if update_icon is not None else None),
            update_menu_fn=None,
            mark_power_source_transition_fn=_mark_power_source_transition,
            mark_power_source_transition=True,
            refresh_menu=False,
            monotonic_fn=time.monotonic,
        )

    _run_tray_transition_if_available(tray, activate_transition)


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
        self.monitor_thread: threading.Thread | None = None
        self._battery_thread: threading.Thread | None = None
        self._lid_thread: threading.Thread | None = None
        self._monitor_process: object | None = None
        self._monitor_process_lock = threading.Lock()
        self._power_event_generation = 0
        self._power_event_generation_lock = threading.Lock()
        self._power_event_context = threading.local()
        self._battery_iteration_context = threading.local()
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

    def prime_power_source_state(self) -> None:
        """Apply the current power-source policy once before monitor threads start.

        Tray autostart runs immediately after power monitoring starts.  Without
        this synchronous first classification, the background battery thread can
        race the initial effect prime and briefly expose the previous power
        source's profile and brightness.
        """

        policy = PowerSourceLoopPolicy(debounce_seconds=3.0)
        self._run_recoverable_runtime_boundary(
            lambda: self._run_battery_saver_iteration(policy, poll_interval_s=0.0),
            log_message="Initial power-source state application failed",
            fallback=False,
        )

    def start_monitoring(self):
        """Start monitoring power events in background thread."""
        # Still start monitoring even if disabled, so enabling it later in config works.
        # Actual actions are gated in the event handlers.
        power_monitor_runner.start_monitoring(self, thread_factory=threading.Thread)

    def stop_monitoring(self) -> bool:
        """Stop monitoring power events and report whether all workers stopped."""
        return power_monitor_runner.stop_monitoring(self, join_timeout_s=2)

    def _register_monitor_process(self, process: object) -> None:
        with self._monitor_process_lock:
            self._monitor_process = process
        if not self.monitoring:
            self._terminate_monitor_process()

    def _unregister_monitor_process(self, process: object) -> None:
        with self._monitor_process_lock:
            if self._monitor_process is process:
                self._monitor_process = None

    def _terminate_monitor_process(self) -> None:
        with self._monitor_process_lock:
            process = self._monitor_process
        terminate = getattr(process, "terminate", None)
        if not callable(terminate):
            return
        try:
            terminate()
        except _POWER_MANAGER_RUNTIME_ERRORS:
            logger.debug("Failed to terminate power-monitor subprocess", exc_info=True)

    # ---- battery saver (dim on AC unplug)

    def _run_battery_saver_iteration(self, policy, *, poll_interval_s: float) -> bool:
        def run_iteration_transition() -> bool:
            self._battery_iteration_context.defer_sleep = True
            try:
                return _battery_saver.run_battery_saver_iteration(
                    self,
                    policy,
                    poll_interval_s=poll_interval_s,
                    classify_fn=self._classify_battery_saver_iteration,
                    execute_plan_fn=self._execute_battery_saver_iteration_plan,
                    sync_lid_fn=self._sync_lid_state_from_system,
                    keyboard_is_power_event_forced_off_fn=self._keyboard_is_power_event_forced_off,
                    sleep_fn=lambda _seconds: None,
                )
            finally:
                del self._battery_iteration_context.defer_sleep

        did_sleep = bool(
            _run_tray_transition_if_available(
                self.kb_controller,
                run_iteration_transition,
            )
        )
        if did_sleep:
            time.sleep(poll_interval_s)
        return did_sleep

    def _sync_lid_state_from_system(self) -> None:
        _battery_saver.sync_lid_state_from_system(self)

    def _keyboard_is_power_event_forced_off(self) -> bool:
        return _battery_saver.keyboard_is_power_event_forced_off(self)

    def _classify_battery_saver_iteration(self, policy):
        return _battery_saver.classify_battery_saver_iteration(
            self,
            policy,
            stabilize_on_ac_fn=self._stabilize_on_ac_state,
            get_active_perkey_profile_fn=get_active_perkey_profile,
        )

    def _execute_battery_saver_iteration_plan(self, plan, *, poll_interval_s: float) -> bool:
        if bool(getattr(plan, "should_sleep", False)) and bool(
            getattr(self._battery_iteration_context, "defer_sleep", False)
        ):
            return True

        def execute_plan() -> bool:
            return _battery_saver.execute_battery_saver_iteration_plan(
                self,
                plan,
                poll_interval_s=poll_interval_s,
                apply_brightness_fn=self._apply_brightness_policy,
                activate_power_mode_fn=self._activate_power_source_mode,
                activate_perkey_profile_fn=self._activate_power_source_perkey_profile,
            )

        if bool(getattr(plan, "should_sleep", False)):
            return execute_plan()
        return bool(_run_tray_transition_if_available(self.kb_controller, execute_plan))

    def _battery_saver_loop(self) -> None:
        """Poll AC online state and apply a simple dim/restore policy."""

        _battery_saver.battery_saver_loop(
            self,
            run_recoverable_runtime_boundary_fn=self._run_recoverable_runtime_boundary,
            run_iteration_fn=self._run_battery_saver_iteration,
        )

    def _stabilize_on_ac_state(self, raw_on_ac: bool | None) -> bool | None:
        return _battery_saver.stabilize_on_ac_state(self, raw_on_ac)

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
        applied = _battery_saver.activate_power_source_mode(mode)
        if not applied:
            return
        self._refresh_system_power_view_best_effort()

    def _refresh_system_power_view_best_effort(self) -> None:
        """Keep the tray's power-mode view honest after an automatic apply.

        Refreshes the stored snapshot and requests one menu rebuild that the
        tray defers through the runtime coordinator until the transition
        completes — never mid-transition (KDE QMenu host crash).
        """
        refresh = getattr(self.kb_controller, "_refresh_system_power_view", None)
        if not callable(refresh):
            return
        try:
            refresh()
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.debug("System power view refresh failed after mode apply: %s", exc)

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
            should_invoke_fn=self._power_event_is_current,
        )

    def _begin_power_event(self) -> int:
        with self._power_event_generation_lock:
            self._power_event_generation += 1
            return self._power_event_generation

    def _power_event_is_current(self) -> bool:
        generation = getattr(self._power_event_context, "generation", None)
        if generation is None:
            return True
        with self._power_event_generation_lock:
            if int(generation) != self._power_event_generation:
                return False
        transition_revision = getattr(self._power_event_context, "transition_revision", None)
        if transition_revision is None:
            return True
        return _capture_tray_transition_revision(self.kb_controller) == int(transition_revision)

    def _run_received_power_event(self, action) -> None:
        generation = self._begin_power_event()
        self._power_event_context.generation = generation
        try:
            action()
        finally:
            del self._power_event_context.generation

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
        event_generation = getattr(self._power_event_context, "generation", None)

        def dispatch_transition() -> None:
            previous_generation = getattr(self._power_event_context, "generation", None)
            previous_transition_revision = getattr(self._power_event_context, "transition_revision", None)
            if event_generation is not None:
                self._power_event_context.generation = event_generation
            active_revision = _active_tray_transition_revision(self.kb_controller)
            if active_revision is not None:
                self._power_event_context.transition_revision = active_revision
            try:
                self._handle_power_event(
                    enabled=self._is_enabled(),
                    action_enabled=self._flag(flag_name, True),
                    log_message=log_message,
                    delay_s=delay_s,
                    policy_method=policy_method,
                    expected_action_type=expected_action_type,
                    kb_method_name=kb_method_name,
                )
            finally:
                if previous_generation is None:
                    try:
                        del self._power_event_context.generation
                    except AttributeError:
                        pass
                else:
                    self._power_event_context.generation = previous_generation
                if previous_transition_revision is None:
                    try:
                        del self._power_event_context.transition_revision
                    except AttributeError:
                        pass
                else:
                    self._power_event_context.transition_revision = previous_transition_revision

        _run_tray_transition_if_available(
            self.kb_controller,
            dispatch_transition,
        )

    def _on_suspend(self) -> None:
        """Called when system is about to suspend."""
        self._run_received_power_event(
            lambda: self._dispatch_power_event_route(
                flag_name="power_off_on_suspend",
                log_message="System suspending - turning off keyboard backlight",
                policy_method=self._event_policy.handle_power_off_event,
                expected_action_type=TurnOffFromEvent,
                kb_method_name="turn_off",
            )
        )

    def _on_resume(self) -> None:
        """Called when system resumes from suspend."""
        self._run_received_power_event(
            lambda: self._dispatch_power_event_route(
                flag_name="power_restore_on_resume",
                log_message="System resumed - restoring keyboard backlight",
                delay_s=0.5,
                policy_method=self._event_policy.handle_power_restore_event,
                expected_action_type=RestoreFromEvent,
                kb_method_name="restore",
            )
        )

    def _on_lid_close(self) -> None:
        """Called when lid is closed."""

        def handle_lid_close() -> None:
            self._lid_closed = True
            self._dispatch_power_event_route(
                flag_name="power_off_on_lid_close",
                log_message="Lid closed - turning off keyboard backlight",
                policy_method=self._event_policy.handle_power_off_event,
                expected_action_type=TurnOffFromEvent,
                kb_method_name="turn_off",
            )

        self._run_received_power_event(handle_lid_close)

    def _on_lid_open(self) -> None:
        """Called when lid is opened."""

        def handle_lid_open() -> None:
            self._lid_closed = False
            self._dispatch_power_event_route(
                flag_name="power_restore_on_lid_open",
                log_message="Lid opened - restoring keyboard backlight",
                policy_method=self._event_policy.handle_power_restore_event,
                expected_action_type=RestoreFromEvent,
                kb_method_name="restore",
            )

        self._run_received_power_event(handle_lid_open)
