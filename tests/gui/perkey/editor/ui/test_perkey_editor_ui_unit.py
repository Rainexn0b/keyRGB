from __future__ import annotations

import pytest

from tests.gui.perkey.editor.ui._editor_ui_fakes import _build_ui


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

    content = next(
        frame
        for frame in registry["frames"]
        if frame.parent is main and frame.pack_calls == [{"fill": "both", "expand": True}]
    )
    assert content.columnconfigure_calls == [{"index": 0, "weight": 1}, {"index": 1, "weight": 0}]
    assert content.rowconfigure_calls == [{"index": 0, "weight": 1}]

    left = next(
        frame
        for frame in registry["frames"]
        if frame.parent is content and frame.grid_calls == [{"row": 0, "column": 0, "sticky": "nsew"}]
    )
    right = next(
        frame
        for frame in registry["frames"]
        if frame.parent is content and frame.options.get("width") == editor._right_panel_width
    )

    assert left.columnconfigure_calls == [{"index": 0, "weight": 1}]
    assert left.rowconfigure_calls == [{"index": 0, "weight": 1}, {"index": 1, "weight": 0}]
    assert right.grid_calls == [{"row": 0, "column": 1, "sticky": "ns", "padx": (16, 0)}]
    assert right.pack_propagate_calls == []

    backdrop_row = next(
        frame
        for frame in registry["frames"]
        if frame.parent is right and frame.pack_calls == [{"fill": "x", "pady": (0, 6)}]
    )
    backdrop_buttons = next(
        frame
        for frame in registry["frames"]
        if frame.parent is right and frame.pack_calls == [{"fill": "x", "pady": (0, 10)}]
    )

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

    assert backdrop_row.columnconfigure_calls == [{"index": 1, "weight": 1}]
    assert editor._backdrop_mode_combo.grid_calls == [{"row": 0, "column": 1, "sticky": "ew", "padx": (8, 0)}]
    assert backdrop_buttons.columnconfigure_calls == [{"index": 0, "weight": 1}, {"index": 1, "weight": 1}]
    assert next(button for button in registry["buttons"] if button.options["text"] == "Set Backdrop...").grid_calls == [
        {"row": 0, "column": 0, "sticky": "ew", "padx": (0, 6)}
    ]
    assert next(button for button in registry["buttons"] if button.options["text"] == "Reset Backdrop").grid_calls == [
        {"row": 0, "column": 1, "sticky": "ew", "padx": (6, 0)}
    ]

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
    assert "Use on AC" in label_texts
    assert "Use on battery" in label_texts
    assert len(registry["separators"]) == 2
    assert all(
        separator.grid_calls == [{"row": 0, "column": 1, "sticky": "ew", "padx": (8, 0)}]
        for separator in registry["separators"]
    )
    assert len(registry["dropdowns"]) == 4
    assert editor._backdrop_mode_dropdown is registry["dropdowns"][0]

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
    assert dropdown is registry["dropdowns"][1]
    assert registry["profiles_list_calls"] == 2
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

    ac_combo = editor._ac_power_source_profile_combo
    battery_combo = editor._battery_power_source_profile_combo
    assert ac_combo.options["textvariable"] is editor._ac_power_source_profile_var
    assert battery_combo.options["textvariable"] is editor._battery_power_source_profile_var
    assert ac_combo.options["width"] == 22
    assert battery_combo.options["width"] == 22
    assert ac_combo.options["state"] == "readonly"
    assert battery_combo.options["state"] == "readonly"
    assert ac_combo.grid_calls == [{"row": 3, "column": 1, "sticky": "ew", "padx": (8, 0), "pady": (10, 0)}]
    assert battery_combo.grid_calls == [{"row": 4, "column": 1, "sticky": "ew", "padx": (8, 0), "pady": (8, 0)}]
    assert editor._ac_power_source_profile_var.get() == "movie"
    assert editor._battery_power_source_profile_var.get() == "Keep current profile"
    assert ac_combo.options["values"] == (
        "Keep current profile",
        "default",
        "gaming",
        "movie",
    )
    assert battery_combo.options["values"] == (
        "Keep current profile",
        "default",
        "gaming",
        "movie",
    )
    assert [call[0] for call in ac_combo.bind_calls] == ["<Button-1>", "<Down>", "<<ComboboxSelected>>"]
    assert [call[0] for call in battery_combo.bind_calls] == ["<Button-1>", "<Down>", "<<ComboboxSelected>>"]
    assert editor._ac_power_source_profile_dropdown is registry["dropdowns"][2]
    assert editor._battery_power_source_profile_dropdown is registry["dropdowns"][3]
    editor._ac_power_source_profile_dropdown.kwargs["set_value"]("gaming")
    editor._battery_power_source_profile_dropdown.kwargs["set_value"]("default")
    assert editor._ac_power_source_profile_var.get() == "gaming"
    assert editor._battery_power_source_profile_var.get() == "default"
    assert editor._save_power_source_profile_policy_calls == 2

    layout_controls = editor._layout_setup_controls
    overlay_controls = editor.overlay_controls
    overlay_panel = editor._overlay_setup_panel
    assert layout_controls is registry["layout_controls"][0]
    assert overlay_controls is registry["overlay_controls"][0]
    assert layout_controls.editor is editor
    assert overlay_controls.editor is editor
    assert layout_controls.grid_calls == [{"row": 0, "column": 0, "sticky": "nsew"}]
    assert overlay_controls.grid_calls == [{"row": 0, "column": 0, "sticky": "nsew"}]
    assert layout_controls.grid_remove_calls == 1
    assert overlay_panel.grid_calls == [{"row": 0, "column": 0, "sticky": "nsew"}]
    assert overlay_panel.grid_remove_calls == 1
    assert overlay_controls.sync_calls == 1
    assert editor.lightbar_controls is None
