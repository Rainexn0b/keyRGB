"""PowerManager battery-saver / AC power-source polling loop.

Extracted from ``manager.py`` (WS1 / A1 slice 1). Methods are bound via
the manager instance passed as ``manager``.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Protocol

from ._manager_helpers import is_power_event_forced_off
from ._manager_source_iteration import PowerSourceIterationPlan, stabilize_power_source_state

if TYPE_CHECKING:
    from src.core.config import Config

logger = logging.getLogger(__name__)

_DEFAULT_POWER_SOURCE_POLL_INTERVAL_S = 0.5


class BatterySaverManager(Protocol):
    """Typed state and callbacks used by the extracted polling helpers."""

    kb_controller: object
    monitoring: bool
    _config: Config
    _lid_closed: bool
    _stable_on_ac: bool | None
    _pending_on_ac: bool | None

    def _flag(self, name: str, default: bool = True) -> bool: ...

    def _on_lid_close(self) -> None: ...

    def _on_lid_open(self) -> None: ...


def _manager_module():
    """Resolve manager module at call time so monkeypatch seams stay on manager.py."""

    from src.core.power.management import manager as manager_module

    return manager_module


def run_battery_saver_iteration(
    manager: BatterySaverManager,
    policy,
    *,
    poll_interval_s: float,
    classify_fn,
    execute_plan_fn,
    sync_lid_fn,
    keyboard_is_power_event_forced_off_fn,
) -> bool:
    sync_lid_fn()

    sleep = _manager_module().time.sleep
    if manager._lid_closed and manager._flag("power_off_on_lid_close", True):
        sleep(poll_interval_s)
        return True

    if keyboard_is_power_event_forced_off_fn():
        sleep(poll_interval_s)
        return True

    plan = classify_fn(policy)
    return execute_plan_fn(plan, poll_interval_s=poll_interval_s)


def sync_lid_state_from_system(manager: BatterySaverManager) -> None:
    state = _manager_module().read_lid_state()
    if state == "closed" and not manager._lid_closed:
        logger.info("Power-source polling observed closed lid")
        manager._on_lid_close()
    elif state == "open" and manager._lid_closed:
        logger.info("Power-source polling observed open lid")
        manager._on_lid_open()


def keyboard_is_power_event_forced_off(manager: BatterySaverManager) -> bool:
    return is_power_event_forced_off(manager.kb_controller)


def classify_battery_saver_iteration(
    manager: BatterySaverManager,
    policy,
    *,
    stabilize_on_ac_fn,
    get_active_perkey_profile_fn,
) -> PowerSourceIterationPlan:
    mod = _manager_module()
    now_mono = float(time.monotonic())
    raw_on_ac = mod.read_on_ac_power()
    stable_on_ac = stabilize_on_ac_fn(raw_on_ac)
    return mod.classify_power_source_iteration(
        raw_on_ac=stable_on_ac,
        build_loop_inputs_fn=lambda on_ac: mod.build_power_source_loop_inputs(
            manager._config,
            manager.kb_controller,
            on_ac=on_ac,
            now_mono=now_mono,
            get_power_mode_status_fn=mod.get_system_power_status,
            get_active_perkey_profile_fn=get_active_perkey_profile_fn,
            safe_int_attr_fn=mod.safe_int_attr,
        ),
        policy=policy,
    )


def execute_battery_saver_iteration_plan(
    manager: BatterySaverManager,
    plan: PowerSourceIterationPlan,
    *,
    poll_interval_s: float,
    apply_brightness_fn,
    activate_power_mode_fn,
    activate_perkey_profile_fn,
) -> bool:
    if plan.should_sleep:
        _manager_module().time.sleep(poll_interval_s)
        return True

    _manager_module().apply_power_source_actions(
        kb_controller=manager.kb_controller,
        actions=plan.actions,
        apply_brightness=apply_brightness_fn,
        activate_power_mode=activate_power_mode_fn,
        activate_perkey_profile=activate_perkey_profile_fn,
    )
    return False


def battery_saver_loop(
    manager: BatterySaverManager,
    *,
    run_recoverable_runtime_boundary_fn,
    run_iteration_fn,
) -> None:
    """Poll AC online state and apply a simple dim/restore policy.

    Requirements:
    - no root required
    - debounce rapid toggling
    - don't fight manual brightness changes while on battery
    """

    policy = _manager_module().PowerSourceLoopPolicy(debounce_seconds=3.0)

    while manager.monitoring:
        poll_interval_s = _DEFAULT_POWER_SOURCE_POLL_INTERVAL_S
        did_sleep = run_recoverable_runtime_boundary_fn(
            lambda: run_iteration_fn(policy, poll_interval_s=poll_interval_s),
            log_message="Battery saver monitoring iteration failed",
            fallback=False,
        )
        if did_sleep:
            continue

        _manager_module().time.sleep(poll_interval_s)


def stabilize_on_ac_state(manager: BatterySaverManager, raw_on_ac: bool | None) -> bool | None:
    state = stabilize_power_source_state(
        raw_on_ac=raw_on_ac,
        stable_on_ac=manager._stable_on_ac,
        pending_on_ac=manager._pending_on_ac,
    )
    manager._stable_on_ac = state.stable_on_ac
    manager._pending_on_ac = state.pending_on_ac
    return manager._stable_on_ac


def activate_power_source_mode(mode: object) -> None:
    applied = _manager_module().set_system_power_mode(mode, allow_interactive=False)
    if not bool(applied):
        logger.warning("Power-source mode activation did not apply for %s", getattr(mode, "value", mode))
