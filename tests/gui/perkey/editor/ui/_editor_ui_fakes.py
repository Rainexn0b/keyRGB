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
        self.pack_calls = []

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def grid_remove(self) -> None:
        self.grid_remove_calls += 1

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))


class _FakeLightingAreasPanel(_FakeLayoutSetupControls):
    def __init__(self, parent=None, *, editor, tk_module=None, ttk_module=None, **kwargs):
        super().__init__(parent, editor=editor)
        import os as _os

        forced = getattr(editor, "_force_lighting_areas_visible", None)
        if forced is not None:
            self._should_show = bool(forced)
        else:
            self._should_show = _os.environ.get("KEYRGB_SIMULATE_SECONDARY_DEVICES") == "1"
        # Mirror production LightingAreasPanel._grid_options: grid() with no
        # args re-applies the canonical options instead of row 0 / col 0.
        self._grid_options: dict[str, object] = {}

    @property
    def should_show(self) -> bool:
        return bool(self._should_show)

    def grid(self, **kwargs) -> None:
        if kwargs:
            self._grid_options = dict(kwargs)
        self.grid_calls.append(dict(self._grid_options))

    def record_hidden_placement(self, options) -> None:
        self._grid_options = dict(options)


class _FakeOverlayControls(_FakeLayoutSetupControls):
    def __init__(self, parent=None, *, editor):
        super().__init__(parent, editor=editor)
        self.sync_calls = 0

    def sync_vars_from_scope(self) -> None:
        self.sync_calls += 1


class _FakeOptionalKeysControls(_FakeLayoutSetupControls):
    pass


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
        self._setup_panel_mode: str | None = None
        self._show_setup_panel_calls: list[str] = []

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

    def _show_setup_panel(self, mode: str) -> None:
        self._setup_panel_mode = str(mode)
        self._show_setup_panel_calls.append(str(mode))

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
        "optional_keys_controls": [],
        "overlay_controls": [],
        "lightbar_controls": [],
        "lighting_areas_panels": [],
        "notebooks": [],
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

    class FakeNotebook(_FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            self.tabs: list[tuple[object, str | None]] = []
            self.select_calls: list[object] = []
            self.selected: object = None
            self.selected_index: int = 0
            registry["notebooks"].append(self)

        def add(self, child, **kwargs) -> None:
            self.tabs.append((child, kwargs.get("text")))
            if self.selected is None:
                self.selected = child
                self.selected_index = 0

        def _widget_to_index(self, widget: object) -> int:
            for pos, (child, _text) in enumerate(self.tabs):
                if child is widget or child == widget:
                    return pos
            try:
                pos = int(widget)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                raise ValueError(f"unknown notebook tab: {widget!r}")
            if 0 <= pos < len(self.tabs):
                return pos
            raise ValueError(f"unknown notebook tab: {widget!r}")

        def select(self, tab_id=None):
            if tab_id is None:
                return self.selected
            if isinstance(tab_id, int) and not isinstance(tab_id, bool):
                pos = int(tab_id)
                if not 0 <= pos < len(self.tabs):
                    raise ValueError(f"unknown notebook tab: {tab_id!r}")
            else:
                pos = self._widget_to_index(tab_id)
            self.select_calls.append(pos)
            self.selected_index = pos
            self.selected = self.tabs[pos][0]
            return self.selected

        def index(self, tab_id=None) -> int:
            if tab_id is None or (isinstance(tab_id, str) and tab_id == "current"):
                return int(self.selected_index)
            if isinstance(tab_id, int) and not isinstance(tab_id, bool):
                return int(tab_id)
            return int(self._widget_to_index(tab_id))

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
            Notebook=FakeNotebook,
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

    def fake_optional_keys_controls(parent=None, *, editor):
        controls = _FakeOptionalKeysControls(parent, editor=editor)
        registry["optional_keys_controls"].append(controls)
        return controls

    def fake_overlay_controls(parent=None, *, editor):
        controls = _FakeOverlayControls(parent, editor=editor)
        registry["overlay_controls"].append(controls)
        return controls

    def fake_lightbar_controls(parent=None, *, editor):
        controls = _FakeLightbarControls(parent, editor=editor)
        registry["lightbar_controls"].append(controls)
        return controls

    def fake_lighting_areas_panel(parent=None, *, editor, tk_module=None, ttk_module=None, **kwargs):
        panel = _FakeLightingAreasPanel(parent, editor=editor, tk_module=tk_module, ttk_module=ttk_module, **kwargs)
        registry["lighting_areas_panels"].append(panel)
        return panel

    def fake_list_profiles() -> list[str]:
        registry["profiles_list_calls"] += 1
        return ["default", "gaming", "movie"]

    monkeypatch.setattr(editor_ui, "KeyboardCanvas", fake_keyboard_canvas)
    monkeypatch.setattr(editor_ui, "ColorWheel", fake_color_wheel)
    monkeypatch.setattr(editor_ui, "LayoutSetupControls", fake_layout_controls)
    monkeypatch.setattr(editor_ui, "OptionalKeysControls", fake_optional_keys_controls)
    monkeypatch.setattr(editor_ui, "OverlayControls", fake_overlay_controls)
    monkeypatch.setattr(editor_ui, "LightbarControls", fake_lightbar_controls)
    monkeypatch.setattr(editor_ui, "LightingAreasPanel", fake_lighting_areas_panel)
    monkeypatch.setattr(profile_actions_ui.profiles, "list_profiles", fake_list_profiles)
    return registry


def _build_ui(
    monkeypatch: pytest.MonkeyPatch,
    *,
    bind_error: bool = False,
    frame_width: int = 360,
    color_wheel_reqwidth: int = 0,
    has_lightbar_device: bool = False,
    lighting_areas_visible: bool | None = None,
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
    if lighting_areas_visible is not None:
        editor._force_lighting_areas_visible = bool(lighting_areas_visible)
    editor_ui.build_editor_ui(editor)
    return editor, root, registry
