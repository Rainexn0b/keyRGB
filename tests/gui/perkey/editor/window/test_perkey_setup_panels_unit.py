from __future__ import annotations

from types import SimpleNamespace

from keyrgb.gui.perkey.editor import PerKeyEditor


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


class DummyLightbarPanel(DummyPanel):
    def __init__(self) -> None:
        super().__init__()
        self.sync_calls = 0

    def sync_vars_from_editor(self) -> None:
        self.sync_calls += 1


class DummyNotebook:
    def __init__(self) -> None:
        self.select_calls: list[object] = []
        self.selected: object = None

    def select(self, tab_id=None):
        if tab_id is None:
            return self.selected
        self.select_calls.append(tab_id)
        self.selected = tab_id
        return tab_id


def _editor(*, with_notebook: bool = False) -> SimpleNamespace:
    editor = SimpleNamespace(
        overlay_controls=DummyOverlayPanel(),
        lightbar_controls=DummyLightbarPanel(),
        _overlay_setup_panel=DummyPanel(),
        _layout_setup_controls=DummyPanel(),
        _lighting_areas_panel=DummyPanel(),
        _setup_panel_mode=None,
        _refresh_count=0,
    )
    if with_notebook:
        editor._editor_notebook = DummyNotebook()

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
    assert editor._overlay_setup_panel.grid_calls == 1
    assert editor.overlay_controls.sync_calls == 1
    assert editor.lightbar_controls.sync_calls == 1
    assert editor._layout_setup_controls.grid_calls == 0

    PerKeyEditor._show_setup_panel(editor, "layout")

    assert editor._setup_panel_mode == "layout"
    assert editor._overlay_setup_panel.grid_remove_calls == 2
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


def test_hide_setup_panel_reopens_lighting_areas() -> None:
    editor = _editor()
    editor._setup_panel_mode = "overlay"

    PerKeyEditor._hide_setup_panel(editor)

    assert editor._setup_panel_mode is None
    assert editor._lighting_areas_panel.grid_calls == 1


def test_notebook_tab_selection_mapping() -> None:
    editor = _editor(with_notebook=True)

    PerKeyEditor._show_setup_panel(editor, "layout")
    assert editor._setup_panel_mode == "layout"
    assert editor._editor_notebook.select_calls == [1]
    assert editor._refresh_count == 1
    # Notebook path never hides panels via grid_remove.
    assert editor._overlay_setup_panel.grid_remove_calls == 0
    assert editor._layout_setup_controls.grid_remove_calls == 0

    PerKeyEditor._show_setup_panel(editor, "overlay")
    assert editor._setup_panel_mode == "overlay"
    assert editor._editor_notebook.select_calls == [1, 2]
    assert editor.overlay_controls.sync_calls == 1
    assert editor.lightbar_controls.sync_calls == 1

    PerKeyEditor._hide_setup_panel(editor)
    assert editor._setup_panel_mode is None
    assert editor._editor_notebook.select_calls == [1, 2, 0]
    # Lighting panel stays conditionally visible inside Advanced; hiding
    # selects Profiles without touching its grid state.
    assert editor._lighting_areas_panel.grid_calls == 0
    assert editor._lighting_areas_panel.grid_remove_calls == 0


def test_notebook_toggles_select_profiles_setup_advanced() -> None:
    editor = _editor(with_notebook=True)

    PerKeyEditor._toggle_layout_setup(editor)
    assert editor._setup_panel_mode == "layout"
    PerKeyEditor._toggle_layout_setup(editor)
    assert editor._setup_panel_mode is None

    PerKeyEditor._toggle_overlay(editor)
    assert editor._setup_panel_mode == "overlay"
    PerKeyEditor._toggle_overlay(editor)
    assert editor._setup_panel_mode is None

    assert editor._editor_notebook.select_calls == [1, 0, 2, 0]


class ModeRecordingNotebook(DummyNotebook):
    """Record the editor mode observed while programmatic select runs."""

    def __init__(self, editor: SimpleNamespace) -> None:
        super().__init__()
        self.bound_editor = editor
        self.modes_seen: list[object] = []

    def select(self, tab_id=None):
        if tab_id is not None:
            self.modes_seen.append(self.bound_editor._setup_panel_mode)
        return super().select(tab_id)


class FailingNotebook:
    """Simulate a broken notebook selection (e.g. destroyed widget)."""

    def select(self, tab_id=None):
        if tab_id is None:
            return
        raise ValueError("notebook selection failed")


def test_show_sets_mode_before_programmatic_select() -> None:
    editor = _editor()
    recorder = ModeRecordingNotebook(editor)
    editor._editor_notebook = recorder

    PerKeyEditor._show_setup_panel(editor, "overlay")

    # The mode is already visible to a synchronously re-fired
    # <<NotebookTabChanged>> event, so the guard skips a duplicate sync.
    assert recorder.modes_seen == ["overlay"]
    assert editor._setup_panel_mode == "overlay"
    assert editor.overlay_controls.sync_calls == 1
    assert editor.lightbar_controls.sync_calls == 1


def test_show_selection_failure_falls_back_to_legacy_with_requested_mode() -> None:
    editor = _editor()
    editor._editor_notebook = FailingNotebook()  # type: ignore[assignment]

    PerKeyEditor._show_setup_panel(editor, "overlay")

    assert editor._setup_panel_mode == "overlay"
    assert editor._overlay_setup_panel.grid_calls == 1
    assert editor.overlay_controls.sync_calls == 1
    assert editor.lightbar_controls.sync_calls == 1


def test_show_selection_failure_from_layout_keeps_requested_mode() -> None:
    editor = _editor()
    editor._editor_notebook = FailingNotebook()  # type: ignore[assignment]
    editor._setup_panel_mode = "layout"

    PerKeyEditor._show_setup_panel(editor, "overlay")

    assert editor._setup_panel_mode == "overlay"
    assert editor._layout_setup_controls.grid_remove_calls == 1
    assert editor._overlay_setup_panel.grid_calls == 1
