from __future__ import annotations

import fcntl
import select
import struct
import time
import warnings
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, TypeAlias, cast


class _InputDeviceProtocol(Protocol):
    path: str

    def close(self) -> None: ...
    def read(self) -> Iterable[object]: ...


class _InputEventProtocol(Protocol):
    type: int
    code: int
    value: int

    def timestamp(self) -> float: ...


_InputDevice: TypeAlias = _InputDeviceProtocol

_RECOVERABLE_SYSFS_READ_EXCEPTIONS = (OSError, UnicodeError, ValueError, InterruptedError, BlockingIOError)
_RECOVERABLE_DEVICE_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)

# Linux input-event codes. A touchpad gesture on the affected KDE/Tongfang
# setup emits synthetic KEY_LEFTMETA through the physical AT keyboard fd, so
# device classification alone cannot distinguish it from typing. Require an
# actual non-modifier key-down before waking keyboard lighting.
_EV_KEY = 0x01
_KEY_DOWN = 0x01
_MODIFIER_KEY_CODES = frozenset(
    {
        29,  # KEY_LEFTCTRL
        42,  # KEY_LEFTSHIFT
        54,  # KEY_RIGHTSHIFT
        56,  # KEY_LEFTALT
        97,  # KEY_RIGHTCTRL
        100,  # KEY_RIGHTALT
        125,  # KEY_LEFTMETA
        126,  # KEY_RIGHTMETA
    }
)


def _is_keyboard_wake_key_down(event: object) -> bool:
    """Whether an evdev event is a non-modifier key-down suitable for wake."""

    typed_event = cast(_InputEventProtocol, event)
    try:
        event_type = int(typed_event.type)
        code = int(typed_event.code)
        value = int(typed_event.value)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return False
    return event_type == _EV_KEY and value == _KEY_DOWN and code not in _MODIFIER_KEY_CODES


def _set_monotonic_event_clock(device: _InputDevice) -> bool:
    """Set this fd's event clock only; never grab or write to the input device."""
    fd = getattr(device, "fd", None)
    if not isinstance(fd, int) or fd < 0:
        return False
    try:
        # Linux EVIOCSCLOCKID = _IOW('E', 0xa0, int). python-evdev has no wrapper.
        fcntl.ioctl(fd, 0x400445A0, struct.pack("i", time.CLOCK_MONOTONIC))
    except OSError:
        return False
    return True


def _wake_activity_time(event: object, *, now: float) -> float:
    """Genuine key/button down or pointer movement, with a trusted event time."""
    typed_event = cast(_InputEventProtocol, event)
    try:
        kind, code, value = int(typed_event.type), int(typed_event.code), int(typed_event.value)
        activity = (
            (kind == _EV_KEY and value == _KEY_DOWN and code > 0)
            or (kind == 0x02 and code in {0, 1, 6, 8, 11, 12} and value != 0)  # EV_REL: movement/scroll
            or (kind == 0x03 and code in {0, 1, 0x35, 0x36})  # ABS/MT position
            or (kind == 0x03 and code == 0x39 and value >= 0)  # MT contact begins
        )
        if activity:
            timestamp = float(typed_event.timestamp())
            if 0 < timestamp <= now:
                return timestamp
    except (AttributeError, TypeError, ValueError, OverflowError):
        pass
    return 0.0


def _read_udev_input_properties(device_path: str) -> dict[str, str]:
    """Read udev input-class properties for an evdev device."""

    try:
        stat_result = Path(device_path).stat()
        major_num = int(stat_result.st_rdev >> 8)
        minor_num = int(stat_result.st_rdev & 0xFF)
        data_path = Path(f"/run/udev/data/c{major_num}:{minor_num}")
        if not data_path.is_file():
            return {}
        props: dict[str, str] = {}
        for line in data_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.startswith("E:"):
                continue
            key, sep, value = line[2:].partition("=")
            if sep:
                props[key] = value.strip()
        return props
    except _RECOVERABLE_SYSFS_READ_EXCEPTIONS:
        return {}


def _is_user_input_device(device_path: str) -> bool:
    """Return True for keyboards, mice, touchpads and similar interactive devices."""

    props = _read_udev_input_properties(device_path)
    return (
        props.get("ID_INPUT_KEYBOARD") == "1"
        or props.get("ID_INPUT_MOUSE") == "1"
        or props.get("ID_INPUT_TOUCHPAD") == "1"
    )


def _is_keyboard_input_device(device_path: str) -> bool:
    """Return True only for physical/logical keyboard evdev devices."""

    return _read_udev_input_properties(device_path).get("ID_INPUT_KEYBOARD") == "1"


def _default_list_devices() -> Sequence[str]:
    try:
        import evdev
    except ImportError:
        return []
    try:
        return list(evdev.list_devices())
    except _RECOVERABLE_DEVICE_EXCEPTIONS:
        return []


def _default_open_device(path: str) -> _InputDevice:
    import evdev

    return cast(_InputDevice, evdev.InputDevice(path))


@dataclass
class InputIdleTracker:
    """Track time since the last user input event across evdev devices."""

    monotonic_fn: Callable[[], float] = time.monotonic
    list_devices_fn: Callable[[], Sequence[str]] = _default_list_devices
    open_device_fn: Callable[[str], _InputDevice] = _default_open_device
    is_input_device_fn: Callable[[str], bool] = _is_user_input_device
    is_keyboard_device_fn: Callable[[str], bool] = _is_keyboard_input_device
    select_fn: Callable[..., tuple[list, list, list]] = select.select
    refresh_interval_s: float = 30.0
    set_event_clock_fn: Callable[[_InputDevice], bool] = _set_monotonic_event_clock

    devices: list[_InputDevice] | None = field(default=None, init=False)
    last_activity_at: float = field(default=0.0, init=False)
    last_keyboard_activity_at: float = field(default=0.0, init=False)
    # Unlike last_activity_at, initialization/readiness alone never advances this.
    last_wake_activity_at: float = field(default=0.0, init=False)
    monotonic_device_paths: set[str] = field(default_factory=set, init=False)
    dropped_device_paths: set[str] = field(default_factory=set, init=False)
    last_refresh_at: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self.last_activity_at = float(self.monotonic_fn())

    def _open_devices(self) -> list[_InputDevice] | None:
        device_paths = self.list_devices_fn()
        if not device_paths:
            return None

        opened: list[_InputDevice] = []
        for path in device_paths:
            if not self.is_input_device_fn(path):
                continue
            try:
                device = self.open_device_fn(path)
                opened.append(device)
                if self.set_event_clock_fn(device):
                    self.monotonic_device_paths.add(str(path))
            except _RECOVERABLE_DEVICE_EXCEPTIONS:
                continue
        return opened or None

    def _refresh_devices(self) -> None:
        self.close()
        self.devices = self._open_devices()
        self.last_refresh_at = float(self.monotonic_fn())

    def close(self) -> None:
        self.monotonic_device_paths.clear()
        self.dropped_device_paths.clear()
        if not self.devices:
            self.devices = None
            return
        for dev in list(self.devices):
            try:
                # evdev 1.9.3 still calls asyncio.get_event_loop() from its
                # synchronous close path, which is deprecated when no loop is
                # installed on Python 3.13.  Keep the workaround scoped to the
                # exact upstream warning while still closing the descriptor.
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message="There is no current event loop",
                        category=DeprecationWarning,
                        module=r"evdev\.eventio_async",
                    )
                    dev.close()
            except _RECOVERABLE_DEVICE_EXCEPTIONS:
                pass
        self.devices = None

    def seconds_since_activity(self) -> float | None:
        """Return seconds since the last input event, or None if monitoring failed."""

        now = float(self.monotonic_fn())
        if self.devices is None or (now - self.last_refresh_at) >= self.refresh_interval_s:
            self._refresh_devices()

        if not self.devices:
            return None

        try:
            r, _, _ = self.select_fn(self.devices, [], [], 0)
            if r:
                # Reset idle to the start of this poll; the event happened at or
                # before the current moment.
                self.last_activity_at = float(now)
                # Drain the event queues of ready devices so we do not re-count
                # the same events on the next poll.
                keyboard_wake_key_down = False
                for dev in r:
                    try:
                        events = list(dev.read())
                    except _RECOVERABLE_DEVICE_EXCEPTIONS:
                        continue
                    if self.is_keyboard_device_fn(str(getattr(dev, "path", ""))) and any(
                        _is_keyboard_wake_key_down(event) for event in events
                    ):
                        keyboard_wake_key_down = True
                    if str(dev.path) in self.monotonic_device_paths:
                        read_at = float(self.monotonic_fn())
                        for event in events:
                            if getattr(event, "type", None) == 0:
                                if getattr(event, "code", None) == 3:  # SYN_DROPPED
                                    self.dropped_device_paths.add(str(dev.path))
                                elif getattr(event, "code", None) == 0:  # SYN_REPORT
                                    self.dropped_device_paths.discard(str(dev.path))
                            if str(dev.path) in self.dropped_device_paths:
                                continue
                            self.last_wake_activity_at = max(
                                self.last_wake_activity_at, _wake_activity_time(event, now=read_at)
                            )
                if keyboard_wake_key_down:
                    self.last_keyboard_activity_at = float(now)
        except _RECOVERABLE_DEVICE_EXCEPTIONS:
            self._refresh_devices()
            return None if not self.devices else self.seconds_since_activity()

        return float(self.monotonic_fn()) - self.last_activity_at
