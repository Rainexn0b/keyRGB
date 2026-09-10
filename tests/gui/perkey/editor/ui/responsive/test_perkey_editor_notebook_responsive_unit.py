"""UX-03 refinement: notebook tabs use horizontal space side-by-side when wide."""

from __future__ import annotations

import pytest

from tests.gui.perkey.editor.ui._editor_ui_fakes import _build_ui

NARROW_WIDTH = 500
WIDE_WIDTH = 1500


def _sync(tab):
    for event, callback, _add in tab.bind_calls:
        if event == "<Configure>":
            assert callable(callback)
            return callback
    raise AssertionError("no responsive <Configure> binding")


def test_profiles_tab_stacks_narrow_and_restores_wide(monkeypatch: pytest.MonkeyPatch) -> None:
    editor, _root, _registry = _build_ui(monkeypatch)

    tab = editor._profiles_tab
    assert [call[0] for call in tab.bind_calls] == ["<Configure>"]
    assert editor._profiles_frame.grid_calls == [{"row": 0, "column": 0, "sticky": "nsew", "padx": (0, 6)}]
    assert editor._profiles_auto_frame.grid_calls == [{"row": 0, "column": 1, "sticky": "nsew", "padx": (6, 0)}]

    tab.width = NARROW_WIDTH
    _sync(tab)(None)
    assert editor._profiles_frame.grid_calls[-1] == {
        "row": 0,
        "column": 0,
        "columnspan": 2,
        "sticky": "nsew",
        "padx": 0,
    }
    assert editor._profiles_auto_frame.grid_calls[-1] == {
        "row": 1,
        "column": 0,
        "columnspan": 2,
        "sticky": "nsew",
        "padx": 0,
        "pady": (10, 0),
    }

    # Redundant sync in the same mode must not re-grid (no oscillation).
    frame_calls = len(editor._profiles_frame.grid_calls)
    auto_calls = len(editor._profiles_auto_frame.grid_calls)
    _sync(tab)(None)
    assert len(editor._profiles_frame.grid_calls) == frame_calls
    assert len(editor._profiles_auto_frame.grid_calls) == auto_calls

    tab.width = WIDE_WIDTH
    _sync(tab)(None)
    assert editor._profiles_frame.grid_calls[-1] == {
        "row": 0,
        "column": 0,
        "sticky": "nsew",
        "padx": (0, 6),
        "columnspan": 1,
    }
    assert editor._profiles_auto_frame.grid_calls[-1] == {
        "row": 0,
        "column": 1,
        "sticky": "nsew",
        "padx": (6, 0),
        "columnspan": 1,
        "pady": 0,
    }
    # Management stays left, automatic selection stays right with callbacks intact.
    assert editor._profiles_combo.parent is editor._profiles_frame
    assert editor._ac_power_source_profile_combo.parent is editor._profiles_auto_frame


def test_setup_tab_stacks_narrow_and_restores_wide(monkeypatch: pytest.MonkeyPatch) -> None:
    editor, _root, registry = _build_ui(monkeypatch)

    tab = editor._setup_tab
    assert [call[0] for call in tab.bind_calls] == ["<Configure>"]
    guided = next(b for b in registry["buttons"] if b.options["text"] == "Guided Setup…")
    calibrator = next(b for b in registry["buttons"] if b.options["text"] == "Run Keymap Calibrator")
    assert editor._layout_setup_controls.grid_calls == [{"row": 0, "column": 0, "sticky": "nsew", "padx": (0, 6)}]
    assert editor._optional_keys_controls.grid_calls == [{"row": 0, "column": 1, "sticky": "nsew", "padx": (6, 0)}]
    assert guided.grid_calls == [{"row": 1, "column": 0, "sticky": "ew", "padx": (0, 6), "pady": (10, 0)}]
    assert calibrator.grid_calls == [{"row": 1, "column": 1, "sticky": "ew", "padx": (6, 0), "pady": (10, 0)}]

    tab.width = NARROW_WIDTH
    _sync(tab)(None)
    assert editor._layout_setup_controls.grid_calls[-1] == {
        "row": 0,
        "column": 0,
        "columnspan": 2,
        "sticky": "nsew",
        "padx": 0,
    }
    assert editor._optional_keys_controls.grid_calls[-1] == {
        "row": 1,
        "column": 0,
        "columnspan": 2,
        "sticky": "nsew",
        "padx": 0,
        "pady": (10, 0),
    }
    assert guided.grid_calls[-1] == {
        "row": 2,
        "column": 0,
        "columnspan": 2,
        "sticky": "ew",
        "pady": (10, 0),
        "padx": 0,
    }
    assert calibrator.grid_calls[-1] == {
        "row": 3,
        "column": 0,
        "columnspan": 2,
        "sticky": "ew",
        "pady": (8, 0),
        "padx": 0,
    }

    calls = (
        len(editor._layout_setup_controls.grid_calls),
        len(editor._optional_keys_controls.grid_calls),
        len(guided.grid_calls),
        len(calibrator.grid_calls),
    )
    _sync(tab)(None)
    assert (
        len(editor._layout_setup_controls.grid_calls),
        len(editor._optional_keys_controls.grid_calls),
        len(guided.grid_calls),
        len(calibrator.grid_calls),
    ) == calls

    tab.width = WIDE_WIDTH
    _sync(tab)(None)
    assert editor._layout_setup_controls.grid_calls[-1] == {
        "row": 0,
        "column": 0,
        "sticky": "nsew",
        "padx": (0, 6),
        "columnspan": 1,
    }
    assert editor._optional_keys_controls.grid_calls[-1] == {
        "row": 0,
        "column": 1,
        "sticky": "nsew",
        "padx": (6, 0),
        "columnspan": 1,
        "pady": 0,
    }
    assert guided.grid_calls[-1] == {
        "row": 1,
        "column": 0,
        "sticky": "ew",
        "padx": (0, 6),
        "pady": (10, 0),
        "columnspan": 1,
    }
    assert calibrator.grid_calls[-1] == {
        "row": 1,
        "column": 1,
        "sticky": "ew",
        "padx": (6, 0),
        "pady": (10, 0),
        "columnspan": 1,
    }


def test_advanced_tab_without_secondaries_uses_two_columns_and_stacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KEYRGB_SIMULATE_SECONDARY_DEVICES", raising=False)
    editor, _root, _registry = _build_ui(monkeypatch)

    tab = editor._advanced_tab
    panel = editor._lighting_areas_panel
    assert panel.should_show is False
    assert panel.grid_remove_calls == 1
    assert editor._advanced_backdrop_frame.grid_calls == [{"row": 0, "column": 0, "sticky": "nsew", "padx": (0, 6)}]
    assert editor._overlay_setup_panel.grid_calls == [{"row": 0, "column": 1, "sticky": "nsew", "padx": (6, 0)}]

    tab.width = NARROW_WIDTH
    panel_calls = len(panel.grid_calls)
    _sync(tab)(None)
    assert editor._advanced_backdrop_frame.grid_calls[-1] == {
        "row": 0,
        "column": 0,
        "columnspan": 2,
        "sticky": "nsew",
        "padx": 0,
    }
    assert editor._overlay_setup_panel.grid_calls[-1] == {
        "row": 1,
        "column": 0,
        "columnspan": 2,
        "sticky": "nsew",
        "padx": 0,
        "pady": (10, 0),
    }
    # Hidden conditional must not be re-shown; only its stored canonical
    # options track the narrow stacked placement.
    assert len(panel.grid_calls) == panel_calls
    assert panel.grid_remove_calls == 1
    assert panel._grid_options == {
        "row": 2,
        "column": 0,
        "columnspan": 2,
        "sticky": "nsew",
        "pady": (10, 0),
        "padx": 0,
    }
    panel.grid()
    assert panel.grid_calls[-1] == panel._grid_options

    tab.width = WIDE_WIDTH
    _sync(tab)(None)
    assert editor._advanced_backdrop_frame.grid_calls[-1] == {
        "row": 0,
        "column": 0,
        "sticky": "nsew",
        "padx": (0, 6),
        "columnspan": 1,
    }
    assert editor._overlay_setup_panel.grid_calls[-1] == {
        "row": 0,
        "column": 1,
        "sticky": "nsew",
        "padx": (6, 0),
        "columnspan": 1,
        "pady": 0,
    }
    # Wide restore keeps the canonical right-column placement for re-show.
    assert panel._grid_options == {
        "row": 1,
        "column": 1,
        "sticky": "nsew",
        "padx": (6, 0),
        "pady": (10, 0),
        "columnspan": 1,
    }


def test_advanced_tab_with_secondaries_stacks_narrow_and_restores_wide(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KEYRGB_SIMULATE_SECONDARY_DEVICES", "1")
    editor, _root, _registry = _build_ui(monkeypatch)

    tab = editor._advanced_tab
    panel = editor._lighting_areas_panel
    assert panel.should_show is True
    assert panel.grid_calls == [{"row": 1, "column": 1, "sticky": "nsew", "padx": (6, 0), "pady": (10, 0)}]
    assert editor._overlay_setup_panel.grid_calls == [{"row": 0, "column": 1, "sticky": "nsew", "padx": (6, 0)}]

    tab.width = NARROW_WIDTH
    _sync(tab)(None)
    assert editor._advanced_backdrop_frame.grid_calls[-1] == {
        "row": 0,
        "column": 0,
        "columnspan": 2,
        "sticky": "nsew",
        "padx": 0,
    }
    assert editor._overlay_setup_panel.grid_calls[-1] == {
        "row": 1,
        "column": 0,
        "columnspan": 2,
        "sticky": "nsew",
        "padx": 0,
        "pady": (10, 0),
    }
    assert panel.grid_calls[-1] == {
        "row": 2,
        "column": 0,
        "columnspan": 2,
        "sticky": "nsew",
        "pady": (10, 0),
        "padx": 0,
    }

    tab.width = WIDE_WIDTH
    _sync(tab)(None)
    assert editor._advanced_backdrop_frame.grid_calls[-1] == {
        "row": 0,
        "column": 0,
        "sticky": "nsew",
        "padx": (0, 6),
        "columnspan": 1,
    }
    assert editor._overlay_setup_panel.grid_calls[-1] == {
        "row": 0,
        "column": 1,
        "sticky": "nsew",
        "padx": (6, 0),
        "columnspan": 1,
        "pady": 0,
    }
    assert panel.grid_calls[-1] == {
        "row": 1,
        "column": 1,
        "sticky": "nsew",
        "padx": (6, 0),
        "pady": (10, 0),
        "columnspan": 1,
    }
