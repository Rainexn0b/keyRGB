"""Shared fakes for window geometry-persistence tests."""

from __future__ import annotations

from typing import ClassVar


class _FakeGeometryTracker:
    """Stand-in for WindowGeometryTracker with per-test restore control."""

    next_restore_result = False
    instances: ClassVar[list[_FakeGeometryTracker]] = []

    def __init__(
        self,
        root,
        window_id: str,
        min_width: int,
        min_height: int,
        screen_ratio_cap: float = 0.95,
        debounce_ms: int = 500,
    ) -> None:
        self.root = root
        self.window_id = window_id
        self.min_width = int(min_width)
        self.min_height = int(min_height)
        self.screen_ratio_cap = float(screen_ratio_cap)
        self.restore_calls = 0
        self.start_tracking_calls = 0
        self.save_now_calls = 0
        type(self).instances.append(self)

    def restore(self) -> bool:
        self.restore_calls += 1
        if type(self).next_restore_result:
            self.root.geometry(f"restored:{self.window_id}")
            return True
        return False

    def start_tracking(self) -> None:
        self.start_tracking_calls += 1

    def save_now(self) -> bool:
        self.save_now_calls += 1
        events = getattr(self.root, "events", None)
        if events is not None:
            events.append("save")
        return True

    @classmethod
    def last(cls) -> _FakeGeometryTracker:
        assert cls.instances
        return cls.instances[-1]


class _FakeVar:
    def __init__(self, value=None) -> None:
        self._value = value

    def get(self):
        return self._value

    def set(self, value) -> None:
        self._value = value


class _FakeWidget:
    def __init__(self, **kwargs) -> None:
        self.kwargs = dict(kwargs)
        self.pack_calls: list[dict[str, object]] = []
        self.grid_calls: list[dict[str, object]] = []

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def bind(self, *args, **kwargs) -> None:
        return None

    def configure(self, **kwargs) -> None:
        self.kwargs.update(kwargs)

    def config(self, **kwargs) -> None:
        self.configure(**kwargs)

    def columnconfigure(self, *args, **kwargs) -> None:
        return None

    def rowconfigure(self, *args, **kwargs) -> None:
        return None

    def focus_set(self) -> None:
        return None

    def winfo_reqwidth(self) -> int:
        return int(self.kwargs.get("reqwidth_px", 640))

    def winfo_reqheight(self) -> int:
        return int(self.kwargs.get("reqheight_px", 520))

    def winfo_width(self) -> int:
        return int(self.kwargs.get("width_px", 640))


class _FakeRoot:
    def __init__(self) -> None:
        self.geometry_calls: list[str] = []
        self.after_calls: list[tuple[int, object]] = []
        self.protocol_calls: list[tuple[str, object]] = []
        self.bind_calls: list[tuple[str, object]] = []
        self.title_calls: list[str] = []
        self.minsize_calls: list[tuple[int, int]] = []
        self.destroy_calls = 0
        self.update_idletasks_calls = 0
        self.events: list[str] = []
        self.report_callback_exception = lambda *_args: None

    def title(self, text: str) -> None:
        self.title_calls.append(text)

    def geometry(self, value: str) -> None:
        self.geometry_calls.append(value)

    def minsize(self, width: int, height: int) -> None:
        self.minsize_calls.append((width, height))

    def resizable(self, _width: bool, _height: bool) -> None:
        return None

    def after(self, delay: int, callback):
        self.after_calls.append((int(delay), callback))
        return f"after-{len(self.after_calls)}"

    def protocol(self, name: str, callback) -> None:
        self.protocol_calls.append((name, callback))

    def bind(self, sequence: str, callback, add=None) -> None:
        self.bind_calls.append((sequence, callback))

    def update_idletasks(self) -> None:
        self.update_idletasks_calls += 1

    def focus_get(self):
        return None

    def winfo_screenwidth(self) -> int:
        return 1920

    def winfo_screenheight(self) -> int:
        return 1080

    def destroy(self) -> None:
        self.destroy_calls += 1
        self.events.append("destroy")


def _fire_after(root: _FakeRoot, delay: int) -> int:
    fired = 0
    for scheduled_delay, callback in list(root.after_calls):
        if scheduled_delay == delay:
            callback()
            fired += 1
    return fired


def _delays(root: _FakeRoot) -> list[int]:
    return [delay for delay, _callback in root.after_calls]


def _geometry_pass_scheduled(root: _FakeRoot, gui) -> bool:
    """Delay 50 is shared with initial-focus callbacks; match by identity."""
    return any(delay == 50 and callback == gui._apply_geometry for delay, callback in root.after_calls)


# ---------------------------------------------------------------------------
# Uniform Color window
