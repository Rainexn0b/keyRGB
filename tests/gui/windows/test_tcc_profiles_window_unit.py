from __future__ import annotations

from types import SimpleNamespace

import src.gui.tcc.profiles as tcc_profiles_window


class _FakeWidget:
    def __init__(self, parent: object | None = None, **kwargs: object) -> None:
        self.parent = parent
        self.options: dict[str, object] = dict(kwargs)
        self.pack_calls: list[dict[str, object]] = []
        self.grid_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[str, object]] = []
        self.configure_calls: list[dict[str, object]] = []
        self.columnconfigure_calls: list[tuple[int, int]] = []

    def pack(self, **kwargs: object) -> None:
        self.pack_calls.append(dict(kwargs))

    def grid(self, **kwargs: object) -> None:
        self.grid_calls.append(dict(kwargs))

    def bind(self, sequence: str, callback) -> None:
        self.bind_calls.append((sequence, callback))

    def configure(self, **kwargs: object) -> None:
        self.configure_calls.append(dict(kwargs))
        self.options.update(kwargs)

    def columnconfigure(self, index: int, weight: int = 0, **_kwargs: object) -> None:
        self.columnconfigure_calls.append((index, weight))

    def winfo_width(self) -> int:
        return int(self.options.get("width_px", 760))

    def winfo_reqwidth(self) -> int:
        return int(self.options.get("reqwidth_px", self.winfo_width()))

    def winfo_reqheight(self) -> int:
        return int(self.options.get("reqheight_px", 560))


class _FakeListbox(_FakeWidget):
    def __init__(self, parent: object | None = None, **kwargs: object) -> None:
        super().__init__(parent, **kwargs)
        self.delete_calls: list[tuple[object, object]] = []
        self.items: list[str] = []
        self.selection: tuple[int, ...] = ()

    def delete(self, start: object, end: object) -> None:
        self.delete_calls.append((start, end))
        self.items.clear()

    def insert(self, _index: object, label: str) -> None:
        self.items.append(label)

    def curselection(self):
        return self.selection

    def selection_clear(self, _start: object, _end: object) -> None:
        self.selection = ()

    def selection_set(self, index: int) -> None:
        self.selection = (int(index),)

    def activate(self, _index: int) -> None:
        return

    def see(self, _index: int) -> None:
        return

    def yview(self, *args: object) -> str:
        return "yview"


class _FakeScrollbar(_FakeWidget):
    def set(self, *_args: object) -> None:
        return


class _FakeRoot:
    def __init__(self) -> None:
        self.title_calls: list[str] = []
        self.geometry_calls: list[str] = []
        self.minsize_calls: list[tuple[int, int]] = []
        self.resizable_calls: list[tuple[bool, bool]] = []
        self.after_calls: list[tuple[int, object]] = []
        self.destroy_calls = 0
        self.update_idletasks_calls = 0

    def title(self, value: str) -> None:
        self.title_calls.append(value)

    def geometry(self, value: str) -> None:
        self.geometry_calls.append(value)

    def minsize(self, width: int, height: int) -> None:
        self.minsize_calls.append((width, height))

    def resizable(self, width: bool, height: bool) -> None:
        self.resizable_calls.append((width, height))

    def after(self, delay: int, callback) -> None:
        self.after_calls.append((delay, callback))

    def update_idletasks(self) -> None:
        self.update_idletasks_calls += 1

    def winfo_screenwidth(self) -> int:
        return 1280

    def winfo_screenheight(self) -> int:
        return 900

    def destroy(self) -> None:
        self.destroy_calls += 1


def test_constructor_uses_content_driven_geometry(monkeypatch) -> None:
    root = _FakeRoot()

    monkeypatch.setattr(tcc_profiles_window.tk, "Tk", lambda: root)
    monkeypatch.setattr(tcc_profiles_window.tk, "Listbox", _FakeListbox)
    monkeypatch.setattr(tcc_profiles_window.ttk, "Frame", _FakeWidget)
    monkeypatch.setattr(tcc_profiles_window.ttk, "LabelFrame", _FakeWidget)
    monkeypatch.setattr(tcc_profiles_window.ttk, "Label", _FakeWidget)
    monkeypatch.setattr(tcc_profiles_window.ttk, "Button", _FakeWidget)
    monkeypatch.setattr(tcc_profiles_window.ttk, "Scrollbar", _FakeScrollbar)
    monkeypatch.setattr(tcc_profiles_window, "apply_keyrgb_window_icon", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(tcc_profiles_window, "apply_clam_theme", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(tcc_profiles_window, "compute_centered_window_geometry", lambda *_args, **_kwargs: "760x596+10+20")
    monkeypatch.setattr(tcc_profiles_window.tcc_power_profiles, "is_tccd_available", lambda: True)
    monkeypatch.setattr(tcc_profiles_window.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tcc_profiles_window.tcc_power_profiles, "get_active_profile", lambda: None)

    gui = tcc_profiles_window.TccProfilesGUI()

    assert root.title_calls == ["KeyRGB - Power Profiles"]
    assert root.minsize_calls == [(620, 460)]
    assert root.geometry_calls == ["760x596+10+20"]
    assert any(delay == 50 for delay, _callback in root.after_calls)
    assert gui.btn_activate.options["state"] == "disabled"
    assert gui.profile_desc.options["wraplength"] == 640
    assert gui.status.options["wraplength"] == 640
    assert gui.profile_desc.pack_calls == [{"fill": "x", "anchor": "w"}]
    assert gui.status.pack_calls == [{"fill": "x", "anchor": "w", "pady": (8, 0)}]
    assert gui.btn_activate.grid_calls == [{"row": 0, "column": 0, "sticky": "ew"}]
    assert gui.btn_refresh.grid_calls == [{"row": 0, "column": 1, "sticky": "ew", "padx": (8, 0)}]
    assert gui.btn_close.grid_calls == [{"row": 0, "column": 2, "sticky": "ew", "padx": (8, 0)}]
    assert gui.btn_new.grid_calls == [{"row": 0, "column": 0, "sticky": "ew"}]
    assert gui.btn_delete.grid_calls == [{"row": 0, "column": 4, "sticky": "ew", "padx": (8, 0)}]


def test_apply_geometry_uses_requested_content_size(monkeypatch) -> None:
    gui = tcc_profiles_window.TccProfilesGUI.__new__(tcc_profiles_window.TccProfilesGUI)
    gui.root = _FakeRoot()
    gui._main_frame = _FakeWidget(reqwidth_px=840, reqheight_px=620)
    seen: dict[str, object] = {}

    def _fake_compute(root, **kwargs):
        seen["root"] = root
        seen.update(kwargs)
        return "840x656+10+20"

    monkeypatch.setattr(tcc_profiles_window, "compute_centered_window_geometry", _fake_compute)

    gui._apply_geometry()

    assert gui.root.update_idletasks_calls == 1
    assert seen == {
        "root": gui.root,
        "content_height_px": 620,
        "content_width_px": 840,
        "footer_height_px": 0,
        "chrome_padding_px": 36,
        "default_w": 760,
        "default_h": 560,
        "screen_ratio_cap": 0.95,
    }
    assert gui.root.geometry_calls == ["840x656+10+20"]


def test_constructor_schedules_destroy_when_tccd_is_unavailable(monkeypatch) -> None:
    root = _FakeRoot()
    errors: list[tuple[str, str]] = []

    monkeypatch.setattr(tcc_profiles_window.tk, "Tk", lambda: root)
    monkeypatch.setattr(tcc_profiles_window.tk, "Listbox", _FakeListbox)
    monkeypatch.setattr(tcc_profiles_window.ttk, "Frame", _FakeWidget)
    monkeypatch.setattr(tcc_profiles_window.ttk, "LabelFrame", _FakeWidget)
    monkeypatch.setattr(tcc_profiles_window.ttk, "Label", _FakeWidget)
    monkeypatch.setattr(tcc_profiles_window.ttk, "Button", _FakeWidget)
    monkeypatch.setattr(tcc_profiles_window.ttk, "Scrollbar", _FakeScrollbar)
    monkeypatch.setattr(tcc_profiles_window, "apply_keyrgb_window_icon", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(tcc_profiles_window, "apply_clam_theme", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(tcc_profiles_window.tcc_power_profiles, "is_tccd_available", lambda: False)
    monkeypatch.setattr(
        tcc_profiles_window.messagebox,
        "showerror",
        lambda title, message: errors.append((str(title), str(message))),
    )

    tcc_profiles_window.TccProfilesGUI()

    assert errors == [
        (
            "TCC daemon not available",
            "Could not talk to the TUXEDO Control Center daemon (tccd) over DBus.\n\n"
            "Make sure the backend is installed and running (system service), then try again.",
        )
    ]
    assert any(delay == 0 for delay, _callback in root.after_calls)