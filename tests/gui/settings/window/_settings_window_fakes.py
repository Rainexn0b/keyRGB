"""Shared fakes for settings-window unit-test modules."""

from __future__ import annotations

from keyrgb.core.power.system import PowerMode
from keyrgb.gui.settings.settings_state import SettingsValues


class _FakeVar:
    def __init__(self, value=None) -> None:
        self.value = value
        self.set_calls: list[object] = []

    def get(self):
        return self.value

    def set(self, value) -> None:
        self.set_calls.append(value)
        self.value = value


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.pack_calls = []
        self.grid_calls = []
        self.columnconfigure_calls = []
        self.configure_calls = []
        self.bbox_calls = []
        self.reqheight = 320
        self.reqwidth = 640

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def columnconfigure(self, index, **kwargs) -> None:
        self.columnconfigure_calls.append({"index": index, **kwargs})

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))

    def bbox(self, tag: object):
        self.bbox_calls.append(tag)
        return (1, 2, 3, 4)

    def winfo_reqheight(self) -> int:
        return self.reqheight

    def winfo_reqwidth(self) -> int:
        return self.reqwidth


class _FakeRoot:
    def __init__(self) -> None:
        self.title_calls: list[str] = []
        self.minsize_calls: list[tuple[int, int]] = []
        self.resizable_calls: list[tuple[bool, bool]] = []
        self.after_calls: list[tuple[int, object]] = []
        self.geometry_calls: list[str] = []
        self.update_calls = 0
        self.mainloop_calls = 0
        self.destroy_calls = 0

    def title(self, text: str) -> None:
        self.title_calls.append(text)

    def minsize(self, width: int, height: int) -> None:
        self.minsize_calls.append((width, height))

    def resizable(self, width: bool, height: bool) -> None:
        self.resizable_calls.append((width, height))

    def after(self, delay: int, callback) -> None:
        self.after_calls.append((delay, callback))

    def geometry(self, value: str) -> None:
        self.geometry_calls.append(value)

    def update_idletasks(self) -> None:
        self.update_calls += 1

    def mainloop(self) -> None:
        self.mainloop_calls += 1

    def destroy(self) -> None:
        self.destroy_calls += 1


class _FakeBottomBarPanel:
    def __init__(self, parent, *, on_close) -> None:
        self.parent = parent
        self.on_close = on_close
        self.frame = _FakeWidget(parent)
        self.status = _FakeWidget(parent)
        self.hint_calls: list[str] = []

    def set_hardware_hint(self, text: str) -> None:
        self.hint_calls.append(text)


class _FakeScrollArea:
    def __init__(self, parent, *, bg_color: str, padding: int) -> None:
        self.parent = parent
        self.bg_color = bg_color
        self.padding = padding
        self.frame = _FakeWidget(parent)
        self.canvas = _FakeWidget(parent)
        self.bind_mousewheel_calls: list[tuple[object, object]] = []
        self.finalize_calls = 0

    def bind_mousewheel(self, root, *, priority_scroll_widget=None) -> None:
        self.bind_mousewheel_calls.append((root, priority_scroll_widget))

    def finalize_initial_scrollbar_state(self) -> None:
        self.finalize_calls += 1


class _FakePanel:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self.apply_calls: list[dict[str, object]] = []
        self.frame = _FakeWidget()
        self.txt_diagnostics = _FakeWidget()

    def apply_enabled_state(self, **kwargs) -> None:
        self.apply_calls.append(dict(kwargs))

    def apply_state(self) -> None:
        self.apply_calls.append({"apply_state": True})


def _values() -> SettingsValues:
    return SettingsValues(
        power_management_enabled=True,
        power_off_on_suspend=False,
        power_off_on_lid_close=True,
        power_restore_on_resume=False,
        power_restore_on_lid_open=True,
        autostart=True,
        experimental_backends_enabled=False,
        ac_lighting_enabled=True,
        battery_lighting_enabled=False,
        ac_lighting_brightness=21,
        battery_lighting_brightness=9,
        ac_power_mode=PowerMode.BALANCED.value,
        battery_power_mode=None,
        screen_dim_sync_enabled=True,
        controller_sleep_respect=False,
        screen_dim_sync_mode="temp",
        screen_dim_temp_brightness=7,
        idle_dim_debounce_enter_polls=6,
        idle_dim_debounce_exit_polls=10,
        idle_fade_duration_s=0.6,
        time_scheduler_enabled=False,
        day_start_time="08:00",
        night_start_time="20:00",
        day_base_brightness=40,
        day_reactive_brightness=50,
        night_base_brightness=20,
        night_reactive_brightness=50,
        os_autostart_enabled=False,
        physical_layout="auto",
    )
