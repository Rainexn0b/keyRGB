from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.gui.perkey.editor_ui as editor_ui


class _FakeVar:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def set(self, value) -> None:
        self._value = value


class _FakeWidget:
    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.options = dict(kwargs)
        self.configure_calls = []
        self.pack_calls = []
        self.grid_calls = []
        self.bind_calls = []
        self.columnconfigure_calls = []
        self.rowconfigure_calls = []
        self.grid_remove_calls = 0
        self.pack_propagate_calls = []
        self.width = int(kwargs.get("width", 360))

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))
        self.options.update(kwargs)

    config = configure

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def bind(self, event, callback, add=None) -> None:
        self.bind_calls.append((event, callback, add))

    def columnconfigure(self, index, **kwargs) -> None:
        self.columnconfigure_calls.append({"index": index, **kwargs})

    def rowconfigure(self, index, **kwargs) -> None:
        self.rowconfigure_calls.append({"index": index, **kwargs})

    def grid_remove(self) -> None:
        self.grid_remove_calls += 1

    def pack_propagate(self, flag) -> None:
        self.pack_propagate_calls.append(flag)

    def winfo_width(self) -> int:
        return int(self.width)


class _FakeRoot:
    def __init__(self, *, bind_error: bool = False):
        self.bind_error = bind_error
        self.bind_calls = []
        self.bound_callbacks = {}
        self.after_calls = []

    def bind(self, event, callback, add=None) -> None:
        if self.bind_error:
            raise RuntimeError("bind failed")
        self.bind_calls.append((event, callback, add))
        self.bound_callbacks[event] = callback

    def after(self, delay_ms, callback) -> None:
        self.after_calls.append((delay_ms, callback))


class _FakeKeyboardCanvas:
    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.options = dict(kwargs)
        self.pack_calls = []

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))


class _FakeColorWheel:
    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.options = dict(kwargs)
        self.pack_calls = []

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))


class _FakeDropdown:
    def __init__(self, **kwargs):
        self.kwargs = dict(kwargs)
        self.open_calls = []

    def open(self, event=None):
        self.open_calls.append(event)
        return "break"


class _FakeLayoutSetupControls:
    def __init__(self, parent=None, *, editor):
        self.parent = parent
        self.editor = editor
        self.grid_calls = []
        self.grid_remove_calls = 0

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def grid_remove(self) -> None:
        self.grid_remove_calls += 1


class _FakeOverlayControls(_FakeLayoutSetupControls):
    def __init__(self, parent=None, *, editor):
        super().__init__(parent, editor=editor)
        self.sync_calls = 0

    def sync_vars_from_scope(self) -> None:
        self.sync_calls += 1


class _FakeEditor:
    def __init__(self, root: _FakeRoot):
        self.root = root
        self.bg_color = "#202020"
        self.fg_color = "#efefef"
        self._right_panel_width = 320
        self.backdrop_transparency = _FakeVar(45)
        self._last_non_black_color = (10, 20, 30)
        self._wheel_size = 180
        self.apply_all_keys = _FakeVar(False)
        self.sample_tool_enabled = _FakeVar(True)
        self._profile_name_var = _FakeVar("gaming")

    def _set_backdrop(self) -> None:
        return None

    def _reset_backdrop(self) -> None:
        return None

    def _on_backdrop_transparency_changed(self, _value=None) -> None:
        return None

    def _on_color_change(self, *_args) -> None:
        return None

    def _on_color_release(self, *_args) -> None:
        return None

    def _on_sample_tool_toggled(self) -> None:
        return None

    def _fill_all(self) -> None:
        return None

    def _clear_all(self) -> None:
        return None

    def _toggle_layout_setup(self) -> None:
        return None

    def _toggle_overlay(self) -> None:
        return None

    def _run_calibrator(self) -> None:
        return None

    def _reload_keymap(self) -> None:
        return None

    def _new_profile(self) -> None:
        return None

    def _activate_profile(self) -> None:
        return None

    def _save_profile(self) -> None:
        return None

    def _delete_profile(self) -> None:
        return None

    def _set_default_profile(self) -> None:
        return None


def _install_fake_ui(monkeypatch: pytest.MonkeyPatch, *, frame_width: int = 360):
    registry = {
        "frames": [],
        "labels": [],
        "buttons": [],
        "scales": [],
        "checkbuttons": [],
        "comboboxes": [],
        "separators": [],
        "labelframes": [],
        "canvases": [],
        "wheels": [],
        "dropdowns": [],
        "layout_controls": [],
        "overlay_controls": [],
        "profiles_list_calls": 0,
    }

    class FakeFrame(_FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            if "width" not in kwargs:
                self.width = frame_width
            registry["frames"].append(self)

    class FakeLabel(_FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            registry["labels"].append(self)

    class FakeLabelFrame(FakeFrame):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            registry["labelframes"].append(self)

    class FakeButton(_FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            registry["buttons"].append(self)

    class FakeScale(_FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            registry["scales"].append(self)

    class FakeCheckbutton(_FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            registry["checkbuttons"].append(self)

    class FakeCombobox(_FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            registry["comboboxes"].append(self)

    class FakeSeparator(_FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            registry["separators"].append(self)

    monkeypatch.setattr(
        editor_ui,
        "ttk",
        SimpleNamespace(
            Frame=FakeFrame,
            Label=FakeLabel,
            LabelFrame=FakeLabelFrame,
            Button=FakeButton,
            Scale=FakeScale,
            Checkbutton=FakeCheckbutton,
            Combobox=FakeCombobox,
            Separator=FakeSeparator,
        ),
    )
    monkeypatch.setattr(editor_ui, "tk", SimpleNamespace(LEFT="left"))

    def fake_keyboard_canvas(parent=None, **kwargs):
        canvas = _FakeKeyboardCanvas(parent, **kwargs)
        registry["canvases"].append(canvas)
        return canvas

    def fake_color_wheel(parent=None, **kwargs):
        wheel = _FakeColorWheel(parent, **kwargs)
        registry["wheels"].append(wheel)
        return wheel

    def fake_dropdown(**kwargs):
        dropdown = _FakeDropdown(**kwargs)
        registry["dropdowns"].append(dropdown)
        return dropdown

    def fake_layout_controls(parent=None, *, editor):
        controls = _FakeLayoutSetupControls(parent, editor=editor)
        registry["layout_controls"].append(controls)
        return controls

    def fake_overlay_controls(parent=None, *, editor):
        controls = _FakeOverlayControls(parent, editor=editor)
        registry["overlay_controls"].append(controls)
        return controls

    def fake_list_profiles() -> list[str]:
        registry["profiles_list_calls"] += 1
        return ["default", "gaming", "movie"]

    monkeypatch.setattr(editor_ui, "KeyboardCanvas", fake_keyboard_canvas)
    monkeypatch.setattr(editor_ui, "ColorWheel", fake_color_wheel)
    monkeypatch.setattr(editor_ui, "UpwardListboxDropdown", fake_dropdown)
    monkeypatch.setattr(editor_ui, "LayoutSetupControls", fake_layout_controls)
    monkeypatch.setattr(editor_ui, "OverlayControls", fake_overlay_controls)
    monkeypatch.setattr(editor_ui.profiles, "list_profiles", fake_list_profiles)
    return registry


def _build_ui(monkeypatch: pytest.MonkeyPatch, *, bind_error: bool = False, frame_width: int = 360):
    registry = _install_fake_ui(monkeypatch, frame_width=frame_width)
    root = _FakeRoot(bind_error=bind_error)
    editor = _FakeEditor(root)
    editor_ui.build_editor_ui(editor)
    return editor, root, registry


def test_build_editor_ui_builds_layout_and_wires_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    editor, root, registry = _build_ui(monkeypatch)

    main = registry["frames"][0]
    assert main.parent is root
    assert main.options["padding"] == 16
    assert main.pack_calls == [{"fill": "both", "expand": True}]

    assert editor.status_label.options == {
        "text": "Click a key to start",
        "font": ("Sans", 9),
        "anchor": "w",
        "justify": "left",
    }
    assert editor.status_label.pack_calls == [{"fill": "x"}]

    assert root.bind_calls[0][0] == "<Configure>"
    assert root.bind_calls[0][2] is True
    assert root.after_calls[0][0] == 0

    content = next(frame for frame in registry["frames"] if frame.parent is main and frame.pack_calls == [{"fill": "both", "expand": True}])
    assert content.columnconfigure_calls == [{"index": 0, "weight": 1}, {"index": 1, "weight": 0}]
    assert content.rowconfigure_calls == [{"index": 0, "weight": 1}]

    left = next(frame for frame in registry["frames"] if frame.parent is content and frame.grid_calls == [{"row": 0, "column": 0, "sticky": "nsew"}])
    right = next(frame for frame in registry["frames"] if frame.parent is content and frame.options.get("width") == editor._right_panel_width)

    assert left.columnconfigure_calls == [{"index": 0, "weight": 1}]
    assert left.rowconfigure_calls == [{"index": 0, "weight": 1}, {"index": 1, "weight": 0}]
    assert right.grid_calls == [{"row": 0, "column": 1, "sticky": "ns", "padx": (16, 0)}]
    assert right.pack_propagate_calls == [False]

    canvas = editor.canvas
    assert canvas is registry["canvases"][0]
    assert canvas.options == {
        "editor": editor,
        "bg": editor.bg_color,
        "highlightthickness": 0,
    }
    assert canvas.pack_calls == [{"side": "left", "fill": "both", "expand": True}]

    scale = registry["scales"][0]
    assert scale.parent is right
    assert scale.options["from_"] == 0
    assert scale.options["to"] == 100
    assert scale.options["orient"] == "horizontal"
    assert scale.options["variable"] is editor.backdrop_transparency
    assert scale.options["command"].__self__ is editor
    assert scale.options["command"].__func__.__name__ == "_on_backdrop_transparency_changed"
    assert scale.pack_calls == [{"fill": "x", "pady": (0, 10)}]

    wheel = editor.color_wheel
    assert wheel is registry["wheels"][0]
    assert wheel.parent is right
    assert wheel.options["size"] == editor._wheel_size
    assert wheel.options["initial_color"] == editor._last_non_black_color
    assert wheel.options["callback"].__self__ is editor
    assert wheel.options["callback"].__func__.__name__ == "_on_color_change"
    assert wheel.options["release_callback"].__self__ is editor
    assert wheel.options["release_callback"].__func__.__name__ == "_on_color_release"
    assert wheel.options["show_rgb_label"] is False
    assert wheel.pack_calls == [{}]

    checkbuttons = {check.options["text"]: check for check in registry["checkbuttons"]}
    assert set(checkbuttons) == {"Apply to all keys", "Sample tool"}
    assert checkbuttons["Apply to all keys"].options["variable"] is editor.apply_all_keys
    assert "command" not in checkbuttons["Apply to all keys"].options
    assert checkbuttons["Sample tool"].options["variable"] is editor.sample_tool_enabled
    assert checkbuttons["Sample tool"].options["command"].__self__ is editor
    assert checkbuttons["Sample tool"].options["command"].__func__.__name__ == "_on_sample_tool_toggled"

    button_commands = {
        button.options["text"]: button.options["command"].__func__.__name__ for button in registry["buttons"]
    }
    assert button_commands == {
        "Set Backdrop...": "_set_backdrop",
        "Reset Backdrop": "_reset_backdrop",
        "Fill All": "_fill_all",
        "Clear All": "_clear_all",
        "1. Keyboard Setup": "_toggle_layout_setup",
        "2. Keymap Calibrator": "_run_calibrator",
        "3. Overlay Alignment": "_toggle_overlay",
        "New": "_new_profile",
        "Activate": "_activate_profile",
        "Save": "_save_profile",
        "Delete": "_delete_profile",
        "Set as Default": "_set_default_profile",
    }

    button_texts = [button.options["text"] for button in registry["buttons"]]
    assert button_texts[4:7] == [
        "1. Keyboard Setup",
        "2. Keymap Calibrator",
        "3. Overlay Alignment",
    ]

    label_texts = [label.options.get("text") for label in registry["labels"]]
    assert "Backdrop transparency" in label_texts
    assert "Config" in label_texts
    assert "Setup" in label_texts
    assert "Lighting profile" in label_texts
    assert len(registry["separators"]) == 2

    assert editor._profiles_frame.options["text"] == "Lighting profiles"
    assert editor._profiles_frame.options["padding"] == 10
    assert editor._profiles_frame.grid_calls == [{"row": 0, "column": 0, "sticky": "nsew"}]
    assert editor._profiles_frame.columnconfigure_calls == [{"index": 1, "weight": 1}]

    combo = editor._profiles_combo
    assert combo.options["textvariable"] is editor._profile_name_var
    assert combo.options["values"] == ["default", "gaming", "movie"]
    assert combo.options["width"] == 22
    assert combo.options["state"] == "readonly"
    assert combo.grid_calls == [{"row": 0, "column": 1, "sticky": "ew", "padx": (8, 0)}]

    dropdown = editor._profiles_dropdown
    assert dropdown is registry["dropdowns"][0]
    assert registry["profiles_list_calls"] == 1
    assert dropdown.kwargs["root"] is root
    assert dropdown.kwargs["anchor"] is combo
    assert dropdown.kwargs["values_provider"]() == ["default", "gaming", "movie"]
    assert dropdown.kwargs["get_current_value"]() == "gaming"
    dropdown.kwargs["set_value"]("movie")
    assert editor._profile_name_var.get() == "movie"
    assert dropdown.kwargs["bg"] == editor.bg_color
    assert dropdown.kwargs["fg"] == editor.fg_color
    assert [call[0] for call in combo.bind_calls] == ["<Button-1>", "<Down>"]
    for _event, callback, _add in combo.bind_calls:
        assert callback.__self__ is dropdown
        assert callback.__func__.__name__ == "open"

    layout_controls = editor._layout_setup_controls
    overlay_controls = editor.overlay_controls
    assert layout_controls is registry["layout_controls"][0]
    assert overlay_controls is registry["overlay_controls"][0]
    assert layout_controls.editor is editor
    assert overlay_controls.editor is editor
    assert layout_controls.grid_calls == [{"row": 0, "column": 0, "sticky": "nsew"}]
    assert overlay_controls.grid_calls == [{"row": 0, "column": 0, "sticky": "nsew"}]
    assert layout_controls.grid_remove_calls == 1
    assert overlay_controls.grid_remove_calls == 1
    assert overlay_controls.sync_calls == 1


def test_build_editor_ui_schedules_status_wrap_sync_on_bind_and_after(monkeypatch: pytest.MonkeyPatch) -> None:
    editor, root, _registry = _build_ui(monkeypatch, frame_width=360)

    scheduled_callback = root.after_calls[0][1]
    scheduled_callback()
    assert editor.status_label.configure_calls[-1] == {"wraplength": 352}

    status_row = editor.status_label.parent
    status_row.width = 120
    root.bound_callbacks["<Configure>"]()
    assert editor.status_label.configure_calls[-1] == {"wraplength": 200}


def test_build_editor_ui_tolerates_root_bind_failure_and_still_schedules_wrap_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    editor, root, _registry = _build_ui(monkeypatch, bind_error=True, frame_width=280)

    assert root.bind_calls == []
    assert root.bound_callbacks == {}
    assert root.after_calls[0][0] == 0

    root.after_calls[0][1]()
    assert editor.status_label.configure_calls[-1] == {"wraplength": 272}