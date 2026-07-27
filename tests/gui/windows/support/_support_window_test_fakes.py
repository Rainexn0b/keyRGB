"""Shared fakes for support-window unit-test modules."""

from __future__ import annotations

from types import SimpleNamespace

import src.gui.windows.support as support_window


class FakeWidget:
    def __init__(self, **kwargs) -> None:
        self.options = dict(kwargs)
        self.configure_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[str, object, object]] = []
        self.after_calls: list[tuple[int, object]] = []
        self.pack_calls: list[dict[str, object]] = []
        self.grid_calls: list[dict[str, object]] = []

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))
        self.options.update(kwargs)

    def focus_set(self) -> None:
        self.options["focused"] = True

    def pack(self, *args, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def grid(self, *args, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def bind(self, sequence: str, callback: object, add: object = None) -> None:
        self.bind_calls.append((sequence, callback, add))

    def after(self, delay_ms: int, callback) -> None:
        self.after_calls.append((delay_ms, callback))

    def columnconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None:
        self.options.setdefault("columnconfigure", []).append((index, weight))

    def rowconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None:
        self.options.setdefault("rowconfigure", []).append((index, weight))

    def winfo_width(self) -> int:
        return int(self.options.get("width_px", 640))

    def winfo_reqwidth(self) -> int:
        return int(self.options.get("reqwidth_px", self.winfo_width()))

    def winfo_reqheight(self) -> int:
        return int(self.options.get("reqheight_px", 480))


class FakeText(FakeWidget):
    def __init__(self, text: str = "") -> None:
        super().__init__(state="disabled")
        self.contents = text

    def delete(self, start: str, end: str) -> None:
        self.contents = ""

    def insert(self, index: str, value: str) -> None:
        self.contents = value


class FakeRoot:
    def __init__(self) -> None:
        self.clipboard_cleared = 0
        self.clipboard_values: list[str] = []
        self.after_calls: list[tuple[int, object]] = []
        self.title_text = ""
        self.geometry_value = ""
        self.minsize_value: tuple[int, int] | None = None
        self.resizable_value: tuple[bool, bool] | None = None
        self.update_idletasks_calls = 0
        self.root_x = 100
        self.root_y = 80
        self.root_width = 1240
        self.root_height = 920
        self.screen_width = 1920
        self.screen_height = 1080

    def clipboard_clear(self) -> None:
        self.clipboard_cleared += 1

    def clipboard_append(self, value: str) -> None:
        self.clipboard_values.append(value)

    def after(self, delay_ms: int, callback) -> None:
        self.after_calls.append((delay_ms, callback))

    def title(self, value: str) -> None:
        self.title_text = value

    def geometry(self, value: str) -> None:
        self.geometry_value = value

    def minsize(self, width: int, height: int) -> None:
        self.minsize_value = (width, height)

    def resizable(self, width: bool, height: bool) -> None:
        self.resizable_value = (width, height)

    def update_idletasks(self) -> None:
        self.update_idletasks_calls += 1

    def winfo_screenheight(self) -> int:
        return self.screen_height

    def winfo_screenwidth(self) -> int:
        return self.screen_width

    def winfo_rootx(self) -> int:
        return self.root_x

    def winfo_rooty(self) -> int:
        return self.root_y

    def winfo_width(self) -> int:
        return self.root_width

    def winfo_height(self) -> int:
        return self.root_height

    def mainloop(self) -> None:
        return


def flush_after(root: FakeRoot) -> None:
    for _delay_ms, callback in list(root.after_calls):
        callback()


def make_window(*, diagnostics_json: str = "", discovery_json: str = ""):
    window = support_window.SupportToolsGUI.__new__(support_window.SupportToolsGUI)
    window.root = FakeRoot()
    window._bg_color = "#111111"
    window._fg_color = "#eeeeee"
    window.status_label = FakeWidget(text="")
    window.issue_meta_label = FakeWidget(text="")
    window.txt_debug = FakeText("stale debug")
    window.txt_discovery = FakeText("stale discovery")
    window.txt_issue = FakeText("stale issue")
    window.btn_copy_debug = FakeWidget(state="disabled")
    window.btn_copy_discovery = FakeWidget(state="disabled")
    window.btn_save_debug = FakeWidget(state="disabled")
    window.btn_save_discovery = FakeWidget(state="disabled")
    window.btn_copy_issue = FakeWidget(state="disabled")
    window.btn_save_issue = FakeWidget(state="disabled")
    window.btn_collect_evidence = FakeWidget(state="disabled")
    window.btn_run_speed_probe = FakeWidget(state="disabled")
    window.btn_open_issue = FakeWidget(state="disabled")
    window.btn_save_bundle = FakeWidget(state="disabled")
    window.btn_run_debug = FakeWidget(state="normal")
    window.btn_run_discovery = FakeWidget(state="normal")
    window._diagnostics_json = diagnostics_json
    window._discovery_json = discovery_json
    window._supplemental_evidence = None
    window._issue_report = None
    window._capture_prompt_key = ""
    window._backend_probe_prompt_key = ""
    return window


def build_support_ui_modules() -> tuple[dict[str, list[FakeWidget]], SimpleNamespace, SimpleNamespace]:
    registry: dict[str, list[FakeWidget]] = {"frames": [], "labels": [], "buttons": [], "texts": []}

    def _frame(*args, **kwargs):
        widget = FakeWidget(**kwargs)
        registry["frames"].append(widget)
        return widget

    def _label(*args, **kwargs):
        widget = FakeWidget(**kwargs)
        registry["labels"].append(widget)
        return widget

    def _button(*args, **kwargs):
        widget = FakeWidget(**kwargs)
        registry["buttons"].append(widget)
        return widget

    def _text(*args, **kwargs):
        widget = FakeText("")
        widget.options.update(kwargs)
        registry["texts"].append(widget)
        return widget

    return registry, SimpleNamespace(Frame=_frame, Label=_label, Button=_button), SimpleNamespace(ScrolledText=_text)


def build_support_jobs_ttk() -> tuple[dict[str, list[FakeWidget]], SimpleNamespace]:
    registry: dict[str, list[FakeWidget]] = {"frames": [], "buttons": []}

    def _frame(*args, **kwargs):
        widget = FakeWidget(**kwargs)
        registry["frames"].append(widget)
        return widget

    def _button(*args, **kwargs):
        widget = FakeWidget(**kwargs)
        registry["buttons"].append(widget)
        return widget

    return registry, SimpleNamespace(Frame=_frame, Button=_button)
