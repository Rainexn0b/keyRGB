"""Shared fakes for per-key editor UI unit-test modules."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import keyrgb.gui.perkey.editor_support.ui as editor_ui
import keyrgb.gui.perkey.ui._profile_actions_ui as profile_actions_ui


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
        self.focus_set_calls = 0
        self.width = int(kwargs.get("width", 360))
        self.reqwidth = int(kwargs.get("reqwidth", kwargs.get("width", 0)))
        self.children = []
        if hasattr(parent, "children"):
            parent.children.append(self)

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

    def focus_set(self) -> None:
        self.focus_set_calls += 1

    def winfo_width(self) -> int:
        return int(self.width)

    def winfo_reqwidth(self) -> int:
        return int(self.reqwidth)

    def winfo_children(self):
        return list(self.children)


class _FakeRoot:
    def __init__(self, *, bind_error: bool = False):
        self.bind_error = bind_error
        self.bind_calls = []
        self.bound_callbacks = {}
        self.after_calls = []
        self.focused = None

    def bind(self, event, callback, add=None) -> None:
        if self.bind_error:
            raise RuntimeError("bind failed")
        self.bind_calls.append((event, callback, add))
        self.bound_callbacks[event] = callback

    def after(self, delay_ms, callback) -> None:
        self.after_calls.append((delay_ms, callback))

    def focus_get(self):
        return self.focused


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
        self.reqwidth = int(kwargs.get("reqwidth", kwargs.get("size", 0)))
        if hasattr(parent, "children"):
            parent.children.append(self)

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def winfo_reqwidth(self) -> int:
        return int(self.reqwidth)


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


class _FakeLightbarControls(_FakeLayoutSetupControls):
    def __init__(self, parent=None, *, editor):
        super().__init__(parent, editor=editor)
        self.sync_calls = 0

    def sync_vars_from_editor(self) -> None:
        self.sync_calls += 1


class _FakeEditor:
    def __init__(self, root: _FakeRoot):
        self.root = root
        self.bg_color = "#202020"
        self.fg_color = "#efefef"
        self._right_panel_width = 320
        self._backdrop_mode_var = _FakeVar("builtin")
        self.backdrop_transparency = _FakeVar(45)
        self._last_non_black_color = (10, 20, 30)
        self._wheel_size = 180
        self.apply_all_keys = _FakeVar(False)
        self.sample_tool_enabled = _FakeVar(True)
        self._profile_name_var = _FakeVar("gaming")
        self.config = SimpleNamespace(ac_perkey_profile_name="movie", battery_perkey_profile_name=None)
        self._ac_power_source_profile_var = _FakeVar("movie")
        self._battery_power_source_profile_var = _FakeVar("Keep current profile")
        self._save_power_source_profile_policy_calls = 0
        self._on_backdrop_mode_changed_calls = 0

    def _on_backdrop_mode_changed(self, _event=None) -> None:
        self._on_backdrop_mode_changed_calls += 1

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

    def _hide_setup_panel(self) -> None:
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

    def _save_power_source_profile_policy(self) -> None:
        self._save_power_source_profile_policy_calls += 1


def _install_fake_ui(
    monkeypatch: pytest.MonkeyPatch,
    *,
    frame_width: int = 360,
    color_wheel_reqwidth: int = 0,
):
    registry = {
        "frames": [],
        "labels": [],
        "buttons": [],
        "scales": [],
        "checkbuttons": [],
        "radiobuttons": [],
        "comboboxes": [],
        "separators": [],
        "labelframes": [],
        "canvases": [],
        "wheels": [],
        "layout_controls": [],
        "overlay_controls": [],
        "lightbar_controls": [],
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

    class FakeRadiobutton(_FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            registry["radiobuttons"].append(self)

    class FakeCanvas(_FakeWidget):
        def create_rectangle(self, *_args, **_kwargs):
            return 1

        def delete(self, *_args, **_kwargs) -> None:
            return None

    class FakeCombobox(_FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            self.set_calls = []
            self.current_value = None
            registry["comboboxes"].append(self)

        def set(self, value) -> None:
            self.current_value = value
            self.set_calls.append(value)

        def get(self):
            return self.current_value

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
            Radiobutton=FakeRadiobutton,
            Combobox=FakeCombobox,
            Separator=FakeSeparator,
        ),
    )
    monkeypatch.setattr(
        editor_ui,
        "tk",
        SimpleNamespace(
            LEFT="left",
            BooleanVar=_FakeVar,
            StringVar=_FakeVar,
            Canvas=FakeCanvas,
        ),
    )

    def fake_keyboard_canvas(parent=None, **kwargs):
        canvas = _FakeKeyboardCanvas(parent, **kwargs)
        registry["canvases"].append(canvas)
        return canvas

    def fake_color_wheel(parent=None, **kwargs):
        wheel = _FakeColorWheel(parent, reqwidth=color_wheel_reqwidth, **kwargs)
        registry["wheels"].append(wheel)
        return wheel

    def fake_layout_controls(parent=None, *, editor):
        controls = _FakeLayoutSetupControls(parent, editor=editor)
        registry["layout_controls"].append(controls)
        return controls

    def fake_overlay_controls(parent=None, *, editor):
        controls = _FakeOverlayControls(parent, editor=editor)
        registry["overlay_controls"].append(controls)
        return controls

    def fake_lightbar_controls(parent=None, *, editor):
        controls = _FakeLightbarControls(parent, editor=editor)
        registry["lightbar_controls"].append(controls)
        return controls

    def fake_list_profiles() -> list[str]:
        registry["profiles_list_calls"] += 1
        return ["default", "gaming", "movie"]

    monkeypatch.setattr(editor_ui, "KeyboardCanvas", fake_keyboard_canvas)
    monkeypatch.setattr(editor_ui, "ColorWheel", fake_color_wheel)
    monkeypatch.setattr(editor_ui, "LayoutSetupControls", fake_layout_controls)
    monkeypatch.setattr(editor_ui, "OverlayControls", fake_overlay_controls)
    monkeypatch.setattr(editor_ui, "LightbarControls", fake_lightbar_controls)
    monkeypatch.setattr(profile_actions_ui.profiles, "list_profiles", fake_list_profiles)
    return registry


def _build_ui(
    monkeypatch: pytest.MonkeyPatch,
    *,
    bind_error: bool = False,
    frame_width: int = 360,
    color_wheel_reqwidth: int = 0,
    has_lightbar_device: bool = False,
):
    registry = _install_fake_ui(
        monkeypatch,
        frame_width=frame_width,
        color_wheel_reqwidth=color_wheel_reqwidth,
    )
    root = _FakeRoot(bind_error=bind_error)
    editor = _FakeEditor(root)
    editor.has_lightbar_device = has_lightbar_device
    editor.lightbar_overlay = {"visible": True, "length": 0.72}
    editor_ui.build_editor_ui(editor)
    return editor, root, registry
