"""Shared fakes/helpers for controller wake-settle tests (tray/runtime stage 1).

Private support for the sibling ``test_*_unit.py`` modules: the keyboard
stub, the duck-typed tray, the frozen-clock installer, the hardware-state
apply helper, and the poller-thread capture seam. No tests live here.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

SETTLE_S = 2.0


class _FakeKb:
    """Keyboard stub that records hardware writes and USB reads."""

    def __init__(self, *, settle_s: float | None = SETTLE_S):
        self.reads = 0
        self.writes: list[tuple] = []
        if settle_s is not None:
            self.keyrgb_controller_wake_settle_s = float(settle_s)

    def get_brightness(self) -> int:
        self.reads += 1
        return 0

    def is_off(self) -> bool:
        self.reads += 1
        return False

    def set_brightness(self, value: int) -> None:
        self.writes.append(("set_brightness", value))

    def turn_off(self) -> None:
        self.writes.append(("turn_off",))

    def enable_user_mode(self, *args, **kwargs) -> None:
        self.writes.append(("enable_user_mode",))


class _SettleTray:
    """Duck-typed tray with a real idle/power owner and recording seams."""

    def __init__(
        self,
        *,
        brightness: int = 25,
        settle_s: float | None = SETTLE_S,
        controller_sleep_off: bool = True,
        sleep_at: float = 100.0,
        start_result: bool = True,
    ):
        from tests.tray.fakes import attach_idle_power_owner, make_idle_power_owner

        self.config = SimpleNamespace(
            brightness=brightness,
            controller_sleep_respect=True,
            effect="none",
        )
        self.is_off = True
        self.kb = _FakeKb(settle_s=settle_s)
        self.engine = SimpleNamespace(
            kb=self.kb,
            kb_lock=threading.RLock(),
            running=False,
            _device_mode_off=False,
            stop=self._record_stop,
        )
        self.stop_calls: list[str] = []
        self.start_calls: list[dict] = []
        self.start_result = bool(start_result)
        self.events: list[tuple] = []
        self.exceptions: list[tuple] = []
        self.refresh_calls = 0
        self._start_current_effect = self._record_start
        attach_idle_power_owner(
            self,
            make_idle_power_owner(
                controller_sleep_off=controller_sleep_off,
                controller_sleep_off_at=sleep_at if controller_sleep_off else 0.0,
            ),
        )

    def _record_stop(self) -> None:
        self.stop_calls.append("stop")

    def _record_start(self, **kwargs) -> bool:
        self.start_calls.append(dict(kwargs))
        return self.start_result

    def _log_event(self, source: str, action: str, **fields) -> None:
        self.events.append((source, action, fields))

    def _log_exception(self, msg: str, exc: Exception) -> None:
        self.exceptions.append((msg, exc))

    def _refresh_ui(self, *, animate_icon: bool = True, refresh_menu: bool = True) -> None:
        self.refresh_calls += 1

    def settle_events(self) -> list[tuple]:
        return [event for event in self.events if event[1] == "controller_wake_settle_armed"]


def install_monotonic_clock(monkeypatch):
    import keyrgb.tray.pollers.hardware_polling as hp

    state = {"now": 100.0}
    monkeypatch.setattr(hp.time, "monotonic", lambda: state["now"])
    return state


def _apply(tray, *, brightness: int, off: bool = False, last_brightness: int = 0):
    from keyrgb.tray.pollers.hardware_polling import _apply_polled_hardware_state

    return _apply_polled_hardware_state(
        tray,
        current_brightness=brightness,
        current_off=off,
        last_brightness=last_brightness,
        last_off_state=True,
    )


class _FakeThread:
    def __init__(self, *, target, daemon: bool):
        self.target = target
        self.daemon = daemon

    def start(self) -> None:
        pass


def _capture_poll_target(monkeypatch, tray):
    import keyrgb.tray.pollers.hardware_polling as hp

    created: dict = {}

    def fake_thread(*, target, daemon: bool):
        thread = _FakeThread(target=target, daemon=daemon)
        created["thread"] = thread
        return thread

    monkeypatch.setattr(hp.threading, "Thread", fake_thread)
    hp.start_hardware_polling(tray)
    return created["thread"].target
