from __future__ import annotations

from types import SimpleNamespace

from src.gui.perkey.editor import PerKeyEditor


class DummyPanel:
    def __init__(self) -> None:
        self.grid_calls = 0
        self.grid_remove_calls = 0

    def grid(self) -> None:
        self.grid_calls += 1

    def grid_remove(self) -> None:
        self.grid_remove_calls += 1


class DummyOverlayPanel(DummyPanel):
    def __init__(self) -> None:
        super().__init__()
        self.sync_calls = 0

    def sync_vars_from_scope(self) -> None:
        self.sync_calls += 1


def _editor() -> SimpleNamespace:
    editor = SimpleNamespace(
        overlay_controls=DummyOverlayPanel(),
        _layout_setup_controls=DummyPanel(),
        _setup_panel_mode=None,
        _refresh_count=0,
    )

    def _refresh_layout_slot_controls() -> None:
        editor._refresh_count += 1

    editor._refresh_layout_slot_controls = _refresh_layout_slot_controls
    editor._hide_setup_panel = lambda: PerKeyEditor._hide_setup_panel(editor)
    editor._show_setup_panel = lambda mode: PerKeyEditor._show_setup_panel(editor, mode)
    return editor


def test_show_setup_panel_swaps_from_overlay_to_layout() -> None:
    editor = _editor()

    PerKeyEditor._show_setup_panel(editor, "overlay")

    assert editor._setup_panel_mode == "overlay"
    assert editor.overlay_controls.grid_calls == 1
    assert editor.overlay_controls.sync_calls == 1
    assert editor._layout_setup_controls.grid_calls == 0

    PerKeyEditor._show_setup_panel(editor, "layout")

    assert editor._setup_panel_mode == "layout"
    assert editor.overlay_controls.grid_remove_calls == 2
    assert editor._layout_setup_controls.grid_calls == 1
    assert editor._refresh_count == 1


def test_toggle_methods_hide_when_same_mode_selected() -> None:
    editor = _editor()

    PerKeyEditor._toggle_layout_setup(editor)
    assert editor._setup_panel_mode == "layout"

    PerKeyEditor._toggle_layout_setup(editor)
    assert editor._setup_panel_mode is None

    PerKeyEditor._toggle_overlay(editor)
    assert editor._setup_panel_mode == "overlay"

    PerKeyEditor._toggle_overlay(editor)
    assert editor._setup_panel_mode is None