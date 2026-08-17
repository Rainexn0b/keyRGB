from __future__ import annotations

import threading
import time

import pytest


def _wait_for_revision(coordinator, expected: int) -> bool:
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if coordinator.capture_revision() >= expected:
            return True
        threading.Event().wait(0.001)
    return False


def test_coordinator_serializes_reentrant_transition_without_new_revision() -> None:
    from src.tray.controllers.runtime_coordinator import TrayRuntimeCoordinator

    coordinator = TrayRuntimeCoordinator()
    calls: list[str] = []

    def outer() -> str:
        calls.append("outer:start")
        nested = coordinator.run(lambda: calls.append("nested") or "nested-result")
        calls.append(nested)
        return "outer-result"

    try:
        assert coordinator.run(outer) == "outer-result"
        assert coordinator.capture_revision() == 1
        assert calls == ["outer:start", "nested", "nested-result"]
    finally:
        assert coordinator.stop_and_drain(timeout_s=1.0) is True


def test_coordinator_rejects_observation_captured_before_newer_transition() -> None:
    from src.tray.controllers.runtime_coordinator import TrayRuntimeCoordinator

    coordinator = TrayRuntimeCoordinator()
    calls: list[str] = []

    try:
        stale_revision = coordinator.capture_revision()
        coordinator.run(lambda: calls.append("manual-turn-on"))

        outcome = coordinator.run_if_current(
            stale_revision,
            lambda: calls.append("stale-hardware-off"),
        )

        assert outcome.accepted is False
        assert outcome.value is None
        assert calls == ["manual-turn-on"]
        assert coordinator.capture_revision() == 1
    finally:
        assert coordinator.stop_and_drain(timeout_s=1.0) is True


def test_coordinator_flushes_coalesced_ui_request_on_waiting_caller() -> None:
    from src.tray.controllers.runtime_coordinator import TrayRuntimeCoordinator, UiRefreshRequest

    coordinator = TrayRuntimeCoordinator()
    caller_thread_id = threading.get_ident()
    action_thread_ids: list[int] = []
    refreshes: list[tuple[int, UiRefreshRequest]] = []

    def action() -> None:
        action_thread_ids.append(threading.get_ident())
        assert coordinator.request_ui(icon=True) is True
        assert coordinator.request_ui(icon=True, menu=True, animate_icon=False) is True

    try:
        coordinator.run(
            action,
            after=lambda request: refreshes.append((threading.get_ident(), request)),
        )
    finally:
        assert coordinator.stop_and_drain(timeout_s=1.0) is True

    assert action_thread_ids != [caller_thread_id]
    assert refreshes == [(caller_thread_id, UiRefreshRequest(icon=True, menu=True, animate_icon=False))]


def test_coordinator_propagates_transition_exception_and_remains_usable() -> None:
    from src.tray.controllers.runtime_coordinator import TrayRuntimeCoordinator

    coordinator = TrayRuntimeCoordinator()

    try:
        with pytest.raises(RuntimeError, match="transition failed"):
            coordinator.run(lambda: (_ for _ in ()).throw(RuntimeError("transition failed")))

        assert coordinator.run(lambda: "recovered") == "recovered"
    finally:
        assert coordinator.stop_and_drain(timeout_s=1.0) is True


def test_coordinator_reports_stuck_owner_and_stops_accepting_new_work() -> None:
    from src.tray.controllers.runtime_coordinator import CoordinatorStoppedError, TrayRuntimeCoordinator

    coordinator = TrayRuntimeCoordinator()
    action_started = threading.Event()
    release_action = threading.Event()
    caller_finished = threading.Event()

    def blocked_action() -> None:
        action_started.set()
        release_action.wait()

    caller = threading.Thread(
        target=lambda: (coordinator.run(blocked_action), caller_finished.set()),
    )
    caller.start()
    assert action_started.wait(timeout=1.0)

    assert coordinator.stop_and_drain(timeout_s=0.0) is False
    with pytest.raises(CoordinatorStoppedError):
        coordinator.run(lambda: None)

    release_action.set()
    caller.join(timeout=1.0)
    assert caller_finished.is_set()
    assert coordinator.stop_and_drain(timeout_s=1.0) is True


def test_transition_adapter_defers_and_coalesces_ui_on_calling_thread() -> None:
    from types import SimpleNamespace

    from src.tray.controllers.runtime_coordination import defer_ui_refresh, run_tray_transition
    from src.tray.controllers.runtime_coordinator import TrayRuntimeCoordinator

    coordinator = TrayRuntimeCoordinator()
    caller_thread_id = threading.get_ident()
    action_threads: list[int] = []
    refresh_threads: list[int] = []
    tray = SimpleNamespace(
        runtime_coordinator=coordinator,
        _refresh_ui=lambda *, animate_icon=True: refresh_threads.append(threading.get_ident()),
    )

    def action() -> str:
        action_threads.append(threading.get_ident())
        assert defer_ui_refresh(tray, icon=True) is True
        assert defer_ui_refresh(tray, menu=True) is True
        return "done"

    try:
        assert run_tray_transition(tray, action) == "done"
    finally:
        assert coordinator.stop_and_drain(timeout_s=1.0) is True

    assert action_threads != [caller_thread_id]
    assert refresh_threads == [caller_thread_id]


def test_transition_adapter_keeps_coordinator_free_fakes_synchronous() -> None:
    from types import SimpleNamespace

    from src.tray.controllers.runtime_coordination import run_tray_transition

    caller_thread_id = threading.get_ident()
    action_threads: list[int] = []

    result = run_tray_transition(
        SimpleNamespace(),
        lambda: action_threads.append(threading.get_ident()) or "direct",
    )

    assert result == "direct"
    assert action_threads == [caller_thread_id]


def test_config_apply_cannot_finish_after_newer_serialized_user_turn_off() -> None:
    from types import SimpleNamespace

    from src.tray.controllers.runtime_coordination import run_tray_transition
    from src.tray.controllers.runtime_coordinator import TrayRuntimeCoordinator
    from src.tray.pollers.config_polling import _reload_and_apply_config_transition

    coordinator = TrayRuntimeCoordinator()
    apply_started = threading.Event()
    release_apply = threading.Event()
    config_finished = threading.Event()
    turn_off_finished = threading.Event()
    tray = SimpleNamespace(runtime_coordinator=coordinator, is_off=True)
    tray.config = SimpleNamespace(reload=lambda: None)

    def apply_from_config(*, cause: str) -> None:
        assert cause == "test"
        apply_started.set()
        release_apply.wait()
        tray.is_off = False

    config_thread = threading.Thread(
        target=lambda: (
            _reload_and_apply_config_transition(
                tray,
                cause="test",
                apply_from_config=apply_from_config,
            ),
            config_finished.set(),
        )
    )
    turn_off_thread = threading.Thread(
        target=lambda: (
            run_tray_transition(tray, lambda: setattr(tray, "is_off", True)),
            turn_off_finished.set(),
        )
    )

    try:
        config_thread.start()
        assert apply_started.wait(timeout=1.0)
        turn_off_thread.start()
        assert _wait_for_revision(coordinator, 2)
        release_apply.set()
        config_thread.join(timeout=1.0)
        turn_off_thread.join(timeout=1.0)
    finally:
        assert coordinator.stop_and_drain(timeout_s=1.0) is True

    assert config_finished.is_set()
    assert turn_off_finished.is_set()
    assert tray.is_off is True


def test_scheduler_apply_cannot_relight_after_newer_serialized_user_turn_off(monkeypatch) -> None:
    from types import SimpleNamespace

    from src.tray.controllers.runtime_coordination import run_tray_transition
    from src.tray.controllers.runtime_coordinator import TrayRuntimeCoordinator
    from src.tray.idle_power_state import TrayIdlePowerState
    from src.tray.pollers import time_scheduler

    coordinator = TrayRuntimeCoordinator()
    apply_started = threading.Event()
    release_apply = threading.Event()
    tray = SimpleNamespace(
        runtime_coordinator=coordinator,
        tray_idle_power_state=TrayIdlePowerState(),
        is_off=True,
        config=SimpleNamespace(),
    )

    def apply_brightness(*_args, **_kwargs) -> None:
        apply_started.set()
        release_apply.wait()
        tray.is_off = False

    monkeypatch.setattr(time_scheduler, "apply_layered_brightness_update", apply_brightness)
    scheduler = threading.Thread(
        target=lambda: time_scheduler._apply_time_scheduler_brightness(tray, 25, None),
    )
    turn_off = threading.Thread(
        target=lambda: run_tray_transition(tray, lambda: setattr(tray, "is_off", True)),
    )

    try:
        scheduler.start()
        assert apply_started.wait(timeout=1.0)
        turn_off.start()
        assert _wait_for_revision(coordinator, 2)
        release_apply.set()
        scheduler.join(timeout=1.0)
        turn_off.join(timeout=1.0)
    finally:
        release_apply.set()
        assert coordinator.stop_and_drain(timeout_s=1.0) is True

    assert not scheduler.is_alive()
    assert not turn_off.is_alive()
    assert tray.is_off is True
