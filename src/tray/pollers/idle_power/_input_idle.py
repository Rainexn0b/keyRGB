from __future__ import annotations

import select
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional, Protocol, Sequence, TypeAlias, cast


class _InputDeviceProtocol(Protocol):
    path: str

    def close(self) -> None: ...
    def read(self) -> Iterable[object]: ...


class _EvdevModuleProtocol(Protocol):
    def list_devices(self) -> Sequence[str]: ...
    def InputDevice(self, path: str) -> _InputDeviceProtocol: ...


_InputDevice: TypeAlias = _InputDeviceProtocol

_RECOVERABLE_SYSFS_READ_EXCEPTIONS = (OSError, UnicodeError, ValueError, InterruptedError, BlockingIOError)
_RECOVERABLE_DEVICE_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


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


def _default_list_devices() -> Sequence[str]:
    try:
        import evdev  # type: ignore[import]
    except ImportError:
        return []
    try:
        return list(evdev.list_devices())
    except _RECOVERABLE_DEVICE_EXCEPTIONS:
        return []


def _default_open_device(path: str) -> _InputDevice:
    import evdev  # type: ignore[import]

    return cast(_InputDevice, evdev.InputDevice(path))


@dataclass
class InputIdleTracker:
    """Track time since the last user input event across evdev devices."""

    monotonic_fn: Callable[[], float] = time.monotonic
    list_devices_fn: Callable[[], Sequence[str]] = _default_list_devices
    open_device_fn: Callable[[str], _InputDevice] = _default_open_device
    is_input_device_fn: Callable[[str], bool] = _is_user_input_device
    select_fn: Callable[..., tuple[list, list, list]] = select.select
    refresh_interval_s: float = 30.0

    devices: list[_InputDevice] | None = field(default=None, init=False)
    last_activity_at: float = field(default=0.0, init=False)
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
                opened.append(self.open_device_fn(path))
            except _RECOVERABLE_DEVICE_EXCEPTIONS:
                continue
        return opened or None

    def _refresh_devices(self) -> None:
        self.close()
        self.devices = self._open_devices()
        self.last_refresh_at = float(self.monotonic_fn())

    def close(self) -> None:
        if not self.devices:
            self.devices = None
            return
        for dev in list(self.devices):
            try:
                dev.close()
            except _RECOVERABLE_DEVICE_EXCEPTIONS:
                pass
        self.devices = None

    def seconds_since_activity(self) -> Optional[float]:
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
                for dev in r:
                    try:
                        list(dev.read())
                    except _RECOVERABLE_DEVICE_EXCEPTIONS:
                        continue
        except _RECOVERABLE_DEVICE_EXCEPTIONS:
            self._refresh_devices()
            return None if not self.devices else self.seconds_since_activity()

        return float(self.monotonic_fn()) - self.last_activity_at
