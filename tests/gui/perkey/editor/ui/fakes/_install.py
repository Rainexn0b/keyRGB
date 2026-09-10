"""Fake UI installer for per-key editor UI tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import keyrgb.gui.perkey.editor_support.ui as editor_ui
import keyrgb.gui.perkey.ui._profile_actions_ui as profile_actions_ui
from tests.gui.perkey.editor.ui.fakes._controls import (
    _FakeEditor,
    _FakeLayoutSetupControls,
    _FakeLightbarControls,
    _FakeLightingAreasPanel,
    _FakeOptionalKeysControls,
    _FakeOverlayControls,
)
from tests.gui.perkey.editor.ui.fakes._widgets import (
    _FakeColorWheel,
    _FakeKeyboardCanvas,
    _FakeRoot,
    _FakeVar,
    _FakeWidget,
)


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
