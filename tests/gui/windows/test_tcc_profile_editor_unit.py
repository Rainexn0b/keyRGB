from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import src.gui.tcc.profile_editor as profile_editor


class _FakeWidget:
    def __init__(self, parent: object | None = None, **kwargs: object) -> None:
        self.parent = parent
        self.options: dict[str, object] = dict(kwargs)
        self.pack_calls: list[dict[str, object]] = []
        self.place_calls: list[dict[str, object]] = []
        self.configure_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[str, object]] = []

    def pack(self, **kwargs: object) -> None:
        self.pack_calls.append(dict(kwargs))

    def place(self, **kwargs: object) -> None:
        self.place_calls.append(dict(kwargs))

    def configure(self, **kwargs: object) -> None:
        self.configure_calls.append(dict(kwargs))
        self.options.update(kwargs)

    def bind(self, sequence: str, callback: object) -> None:
        self.bind_calls.append((sequence, callback))

    def winfo_width(self) -> int:
        return int(self.options.get("width_px", 720))

    def winfo_reqwidth(self) -> int:
        return int(self.options.get("reqwidth_px", self.winfo_width()))

    def winfo_reqheight(self) -> int:
        return int(self.options.get("reqheight_px", 520))


class _FakeToplevel:
    def __init__(self, parent: object, event_log: list[object]) -> None:
        self.parent = parent
        self._event_log = event_log
        self.title_calls: list[str] = []
        self.geometry_calls: list[str] = []
        self.minsize_calls: list[tuple[int, int]] = []
        self.after_calls: list[tuple[int, object]] = []
        self.update_idletasks_calls = 0
        self.destroy_calls = 0

    def title(self, value: str) -> None:
        self.title_calls.append(value)

    def geometry(self, value: str) -> None:
        self.geometry_calls.append(value)

    def minsize(self, width: int, height: int) -> None:
        self.minsize_calls.append((width, height))

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
        self._event_log.append(("destroy", None))


class _FakeFrame(_FakeWidget):
    pass


class _FakeLabel(_FakeWidget):
    pass


class _FakeScrollbar(_FakeWidget):
    def __init__(self, parent: object | None = None, **kwargs: object) -> None:
        super().__init__(parent, **kwargs)
        self.set_calls: list[tuple[object, ...]] = []

    def set(self, *args: object) -> None:
        self.set_calls.append(args)


class _FakeButton(_FakeWidget):
    pass


class _FakeText(_FakeWidget):
    def __init__(self, parent: object | None = None, **kwargs: object) -> None:
        super().__init__(parent, **kwargs)
        self.contents = ""
        self.insert_calls: list[tuple[str, str]] = []
        self.get_calls: list[tuple[str, str]] = []
        self.yview_calls: list[tuple[object, ...]] = []
        self.xview_calls: list[tuple[object, ...]] = []

    def insert(self, index: str, value: str) -> None:
        self.insert_calls.append((index, value))
        self.contents += value

    def get(self, start: str, end: str) -> str:
        self.get_calls.append((start, end))
        return self.contents

    def yview(self, *args: object) -> str:
        self.yview_calls.append(args)
        return "yview-result"

    def xview(self, *args: object) -> str:
        self.xview_calls.append(args)
        return "xview-result"


def _install_fake_ui(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    registry: dict[str, object] = {
        "buttons": [],
        "errors": [],
        "events": [],
        "frames": [],
        "labels": [],
        "scrollbars": [],
        "texts": [],
        "windows": [],
    }

    def fake_toplevel(parent: object) -> _FakeToplevel:
        window = _FakeToplevel(parent, registry["events"])
        registry["windows"].append(window)
        return window

    class FakeFrame(_FakeFrame):
        def __init__(self, parent: object | None = None, **kwargs: object) -> None:
            super().__init__(parent, **kwargs)
            registry["frames"].append(self)

    class FakeLabel(_FakeLabel):
        def __init__(self, parent: object | None = None, **kwargs: object) -> None:
            super().__init__(parent, **kwargs)
            registry["labels"].append(self)

    class FakeScrollbar(_FakeScrollbar):
        def __init__(self, parent: object | None = None, **kwargs: object) -> None:
            super().__init__(parent, **kwargs)
            registry["scrollbars"].append(self)

    class FakeButton(_FakeButton):
        def __init__(self, parent: object | None = None, **kwargs: object) -> None:
            super().__init__(parent, **kwargs)
            registry["buttons"].append(self)

    class FakeText(_FakeText):
        def __init__(self, parent: object | None = None, **kwargs: object) -> None:
            super().__init__(parent, **kwargs)
            registry["texts"].append(self)

    def fake_showerror(title: str, message: str, *, parent: object) -> None:
        registry["errors"].append({"title": title, "message": message, "parent": parent})

    monkeypatch.setattr(profile_editor.tk, "Toplevel", fake_toplevel)
    monkeypatch.setattr(profile_editor.tk, "Text", FakeText)
    monkeypatch.setattr(
        profile_editor,
        "ttk",
        SimpleNamespace(
            Frame=FakeFrame,
            Label=FakeLabel,
            Scrollbar=FakeScrollbar,
            Button=FakeButton,
        ),
    )
    monkeypatch.setattr(profile_editor, "messagebox", SimpleNamespace(showerror=fake_showerror))
    return registry


def _save_button(registry: dict[str, object]) -> _FakeButton:
    return next(button for button in registry["buttons"] if button.options.get("text") == "Save")


def test_open_profile_json_editor_creates_window_populates_text_and_wires_scrollbars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _install_fake_ui(monkeypatch)
    parent = object()
    payload = {"id": "demo", "name": "Cafe", "brightness": 42}

    profile_editor.open_profile_json_editor(
        parent,
        profile_name="Gaming",
        payload=payload,
        on_save=lambda _data: None,
        on_saved=lambda: None,
    )

    window = registry["windows"][0]
    text = registry["texts"][0]
    yscroll, xscroll = registry["scrollbars"]
    info = registry["labels"][0]

    assert window.parent is parent
    assert window.title_calls == ["Edit Profile - Gaming"]
    assert window.geometry_calls == ["720x556+280+172"]
    assert window.minsize_calls == [(560, 360)]
    assert window.after_calls and window.after_calls[0][0] == 0
    assert info.options["justify"] == "left"
    assert info.options["wraplength"] == 640
    assert text.insert_calls == [
        (
            "1.0",
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        )
    ]
    assert yscroll.options["orient"] == "vertical"
    assert xscroll.options["orient"] == "horizontal"
    assert yscroll.place_calls == [{"in_": text, "relx": 1.0, "rely": 0, "relheight": 1.0, "anchor": "ne"}]
    assert xscroll.pack_calls == [{"fill": "x"}]

    yscroll.options["command"]("moveto", 0.5)
    xscroll.options["command"]("scroll", 2, "units")
    text.options["yscrollcommand"](0.0, 1.0)
    text.options["xscrollcommand"](0.25, 0.75)

    assert text.yview_calls == [("moveto", 0.5)]
    assert text.xview_calls == [("scroll", 2, "units")]
    assert yscroll.set_calls == [(0.0, 1.0)]
    assert xscroll.set_calls == [(0.25, 0.75)]


def test_open_profile_json_editor_uses_requested_content_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _install_fake_ui(monkeypatch)
    seen: dict[str, object] = {}

    def _fake_compute(root, **kwargs):
        seen["root"] = root
        seen.update(kwargs)
        return "760x560+10+20"

    monkeypatch.setattr(profile_editor, "compute_centered_window_geometry", _fake_compute)

    profile_editor.open_profile_json_editor(
        object(),
        profile_name="Gaming",
        payload={"id": "demo"},
        on_save=lambda _data: None,
        on_saved=lambda: None,
    )

    window = registry["windows"][0]
    assert window.update_idletasks_calls == 1
    assert seen == {
        "root": window,
        "content_height_px": 520,
        "content_width_px": 720,
        "footer_height_px": 0,
        "chrome_padding_px": 36,
        "default_w": 720,
        "default_h": 520,
        "screen_ratio_cap": 0.95,
    }
    assert window.geometry_calls == ["760x560+10+20"]


def test_save_success_calls_on_save_then_destroy_then_on_saved(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _install_fake_ui(monkeypatch)
    events: list[object] = registry["events"]

    def on_save(payload: dict) -> None:
        events.append(("on_save", payload))

    def on_saved() -> None:
        events.append(("on_saved", None))

    profile_editor.open_profile_json_editor(
        object(),
        profile_name="Gaming",
        payload={"id": "original"},
        on_save=on_save,
        on_saved=on_saved,
    )

    registry["texts"][0].contents = '{"id": "updated", "enabled": true}\n'

    _save_button(registry).options["command"]()

    assert events == [
        ("on_save", {"id": "updated", "enabled": True}),
        ("destroy", None),
        ("on_saved", None),
    ]
    assert registry["windows"][0].destroy_calls == 1
    assert registry["errors"] == []


def test_save_with_invalid_json_shows_error_and_keeps_window_open(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _install_fake_ui(monkeypatch)
    on_save_calls: list[dict] = []
    on_saved_calls: list[str] = []

    profile_editor.open_profile_json_editor(
        object(),
        profile_name="Gaming",
        payload={"id": "original"},
        on_save=lambda payload: on_save_calls.append(payload),
        on_saved=lambda: on_saved_calls.append("saved"),
    )

    registry["texts"][0].contents = "not json\n"

    _save_button(registry).options["command"]()

    error = registry["errors"][0]
    assert error["title"] == "Invalid JSON"
    assert "Expecting value" in error["message"]
    assert error["parent"] is registry["windows"][0]
    assert on_save_calls == []
    assert on_saved_calls == []
    assert registry["windows"][0].destroy_calls == 0


def test_save_with_non_dict_top_level_json_shows_error(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _install_fake_ui(monkeypatch)

    profile_editor.open_profile_json_editor(
        object(),
        profile_name="Gaming",
        payload={"id": "original"},
        on_save=lambda _payload: None,
        on_saved=lambda: None,
    )

    registry["texts"][0].contents = '["not", "an", "object"]\n'

    _save_button(registry).options["command"]()

    assert registry["errors"] == [
        {
            "title": "Invalid JSON",
            "message": "Top-level JSON must be an object",
            "parent": registry["windows"][0],
        }
    ]
    assert registry["windows"][0].destroy_calls == 0


def test_save_callback_failure_shows_error_and_does_not_close(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _install_fake_ui(monkeypatch)
    on_saved_calls: list[str] = []

    def on_save(_payload: dict) -> None:
        raise RuntimeError("permission denied")

    profile_editor.open_profile_json_editor(
        object(),
        profile_name="Gaming",
        payload={"id": "original"},
        on_save=on_save,
        on_saved=lambda: on_saved_calls.append("saved"),
    )

    registry["texts"][0].contents = '{"id": "updated"}\n'

    _save_button(registry).options["command"]()

    assert registry["errors"] == [
        {
            "title": "Save failed",
            "message": "permission denied",
            "parent": registry["windows"][0],
        }
    ]
    assert registry["windows"][0].destroy_calls == 0
    assert on_saved_calls == []


def test_save_callback_propagates_unexpected_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _install_fake_ui(monkeypatch)

    def on_save(_payload: dict) -> None:
        raise AssertionError("unexpected save bug")

    profile_editor.open_profile_json_editor(
        object(),
        profile_name="Gaming",
        payload={"id": "original"},
        on_save=on_save,
        on_saved=lambda: None,
    )

    registry["texts"][0].contents = '{"id": "updated"}\n'

    with pytest.raises(AssertionError, match="unexpected save bug"):
        _save_button(registry).options["command"]()

    assert registry["errors"] == []
    assert registry["windows"][0].destroy_calls == 0
