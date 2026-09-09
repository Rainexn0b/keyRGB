from __future__ import annotations

import pytest

from keyrgb.gui.theme.focus import INITIAL_FOCUS_DELAY_MS
from tests.gui.perkey.editor.ui._editor_ui_fakes import _build_ui


def test_build_editor_ui_shows_lighting_areas_panel_only_with_secondaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KEYRGB_SIMULATE_SECONDARY_DEVICES", "1")

    editor, _root, registry = _build_ui(monkeypatch)

    button_texts = [button.options["text"] for button in registry["buttons"]]
    assert "4. Lighting Areas" not in button_texts
    assert not any(text.startswith(("1.", "2.", "3.", "4.")) for text in button_texts)

    panel = editor._lighting_areas_panel
    assert panel is registry["lighting_areas_panels"][0]
    assert panel.parent is editor._advanced_tab
    assert panel.should_show is True
    # M2: two-column Advanced layout keeps lighting areas on the right.
    assert panel.grid_calls == [{"row": 0, "column": 1, "rowspan": 2, "sticky": "nsew", "padx": (6, 0)}]
    assert panel.grid_remove_calls == 0
    assert editor._advanced_tab.columnconfigure_calls == [
        {"index": 0, "weight": 1},
        {"index": 1, "weight": 1},
    ]
    assert editor._advanced_backdrop_frame.grid_calls == [{"row": 0, "column": 0, "sticky": "nsew", "padx": (0, 6)}]
    assert editor._overlay_setup_panel.grid_calls == [
        {"row": 1, "column": 0, "sticky": "nsew", "pady": (10, 0), "padx": (0, 6)}
    ]
    # The Advanced tab itself is never hidden when the panel is conditional.
    assert len(registry["notebooks"]) == 1
    assert [text for _child, text in registry["notebooks"][0].tabs] == [
        "Profiles",
        "Setup",
        "Advanced",
    ]


def test_build_editor_ui_hides_lighting_areas_panel_without_secondaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KEYRGB_SIMULATE_SECONDARY_DEVICES", raising=False)

    editor, _root, registry = _build_ui(monkeypatch)

    panel = editor._lighting_areas_panel
    assert panel.should_show is False
    # H1: canonical options are recorded even when hidden so a later
    # sync_from_editor() re-show cannot overlap row 0 / column 0.
    assert panel.grid_calls == [{"row": 0, "column": 1, "rowspan": 2, "sticky": "nsew", "padx": (6, 0)}]
    assert panel.grid_remove_calls == 1
    assert panel._grid_options == {"row": 0, "column": 1, "rowspan": 2, "sticky": "nsew", "padx": (6, 0)}
    # Re-show with no args must retain the canonical right-column placement.
    panel.grid()
    assert panel.grid_calls[-1] == {"row": 0, "column": 1, "rowspan": 2, "sticky": "nsew", "padx": (6, 0)}
    # Hidden branch: the left column spans both columns and column 1 is unweighted.
    assert editor._advanced_tab.columnconfigure_calls == [
        {"index": 0, "weight": 1},
        {"index": 1, "weight": 1},
        {"index": 1, "weight": 0},
    ]
    assert editor._advanced_backdrop_frame.grid_calls == [{"row": 0, "column": 0, "columnspan": 2, "sticky": "nsew"}]
    assert editor._overlay_setup_panel.grid_calls == [
        {"row": 1, "column": 0, "columnspan": 2, "sticky": "nsew", "pady": (10, 0)}
    ]
    assert len(registry["notebooks"]) == 1


def test_build_editor_ui_adds_lightbar_controls_when_lightbar_is_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    editor, _root, registry = _build_ui(monkeypatch, has_lightbar_device=True)

    assert editor.lightbar_controls is registry["lightbar_controls"][0]
    assert editor.lightbar_controls.parent is editor._overlay_setup_panel
    assert editor.lightbar_controls.grid_calls == [{"row": 1, "column": 0, "sticky": "ew", "pady": (10, 0)}]
    assert editor.lightbar_controls.sync_calls == 1


def test_build_editor_ui_schedules_initial_focus_on_backdrop_combo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    editor, root, _registry = _build_ui(monkeypatch)

    focus_calls = [call for call in root.after_calls if call[0] == INITIAL_FOCUS_DELAY_MS]
    assert len(focus_calls) == 1

    focus_calls[0][1]()
    assert editor._backdrop_mode_combo.focus_set_calls == 1


def test_build_editor_ui_initial_focus_does_not_steal_existing_focus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    editor, root, _registry = _build_ui(monkeypatch)
    root.focused = object()  # Focus already landed on another child.

    focus_callback = next(call[1] for call in root.after_calls if call[0] == INITIAL_FOCUS_DELAY_MS)
    focus_callback()

    assert editor._backdrop_mode_combo.focus_set_calls == 0


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


def test_build_editor_ui_expands_right_panel_for_requested_child_width(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    editor, root, registry = _build_ui(monkeypatch, color_wheel_reqwidth=361)

    main = registry["frames"][0]
    content = next(
        frame
        for frame in registry["frames"]
        if frame.parent is main and frame.pack_calls == [{"fill": "both", "expand": True}]
    )
    right = next(
        frame
        for frame in registry["frames"]
        if frame.parent is content and frame.grid_calls == [{"row": 0, "column": 1, "sticky": "ns", "padx": (16, 0)}]
    )

    root.after_calls[1][1]()

    assert editor._right_panel_width == 361
    assert right.configure_calls[-1] == {"width": 361}
    assert right.options["width"] == 361


class _UnexpectedStatusWrapError(Exception):
    pass


def test_build_editor_ui_tolerates_expected_status_wrap_runtime_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    editor, root, _registry = _build_ui(monkeypatch)

    def _raise_runtime_error(**_kwargs) -> None:
        raise RuntimeError("widget destroyed")

    editor.status_label.configure = _raise_runtime_error

    root.after_calls[0][1]()


def test_build_editor_ui_status_wrap_sync_propagates_unexpected_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    editor, root, _registry = _build_ui(monkeypatch)

    def _raise_unexpected_error(**_kwargs) -> None:
        raise _UnexpectedStatusWrapError("boom")

    editor.status_label.configure = _raise_unexpected_error

    with pytest.raises(_UnexpectedStatusWrapError, match="boom"):
        root.after_calls[0][1]()
