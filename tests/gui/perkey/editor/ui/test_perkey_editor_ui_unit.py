from __future__ import annotations

import pytest

from keyrgb.gui.theme import metrics as theme_metrics
from tests.gui.perkey.editor.ui._editor_ui_fakes import _build_ui


def test_build_editor_ui_builds_layout_and_wires_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    editor, root, registry = _build_ui(monkeypatch)

    main = registry["frames"][0]
    assert main.parent is root
    assert main.options["padding"] == theme_metrics.OUTER_PADDING
    assert main.pack_calls == [{"fill": "both", "expand": True}]

    assert editor.status_label.options == {
        "text": "Click a key to start",
        "style": theme_metrics.STATUS_LABEL_STYLE,
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
    label_styles = {label.options.get("text"): label.options.get("style") for label in registry["labels"]}
    assert label_styles["Backdrop"] == theme_metrics.BODY_LABEL_STYLE
    assert label_styles["Backdrop transparency"] == theme_metrics.BODY_LABEL_STYLE
    assert label_styles["Config"] == theme_metrics.SECTION_LABEL_STYLE
    assert label_styles["Setup"] == theme_metrics.SECTION_LABEL_STYLE

    button_styles = {button.options["text"]: button.options.get("style") for button in registry["buttons"]}
    assert button_styles["Save"] == theme_metrics.PRIMARY_BUTTON_STYLE
    assert button_styles["Delete"] == theme_metrics.DESTRUCTIVE_BUTTON_STYLE
    assert button_styles["Clear All"] == theme_metrics.DESTRUCTIVE_BUTTON_STYLE
    assert button_styles["Fill All"] is None
    assert button_styles["New"] is None
    assert button_styles["Activate"] is None
    assert button_styles["Set as Default"] is None
    assert button_styles["Set Backdrop..."] is None
    assert button_styles["Reset Backdrop"] is None
    assert "font" not in editor.status_label.options
    assert all("font" not in label.options for label in registry["labels"])
    assert len(registry["separators"]) == 2
    assert all(
        separator.grid_calls == [{"row": 0, "column": 1, "sticky": "ew", "padx": (8, 0)}]
        for separator in registry["separators"]
    )
    assert "dropdowns" not in registry
    assert len(registry["comboboxes"]) == 4
    assert all(combobox.options["state"] == "readonly" for combobox in registry["comboboxes"])

    backdrop_combo = editor._backdrop_mode_combo
    assert backdrop_combo in registry["comboboxes"]
    assert backdrop_combo.options["state"] == "readonly"
    assert backdrop_combo.options["width"] == 16
    assert backdrop_combo.options["values"] == ["No backdrop", "Built-in seed", "Custom image"]
    assert backdrop_combo.get() == "Built-in seed"
    assert [call[0] for call in backdrop_combo.bind_calls] == ["<<ComboboxSelected>>"]
    backdrop_combo.set("No backdrop")
    backdrop_combo.bind_calls[0][1](None)
    assert editor._backdrop_mode_var.get() == "none"
    assert editor._on_backdrop_mode_changed_calls == 1

    assert editor._profiles_frame.options["text"] == "Lighting profiles"
    assert editor._profiles_frame.options["padding"] == 10
    assert editor._profiles_frame.grid_calls == [{"row": 0, "column": 0, "sticky": "nsew"}]
    assert editor._profiles_frame.columnconfigure_calls == [{"index": 1, "weight": 1}]

    combo = editor._profiles_combo
    assert combo in registry["comboboxes"]
    assert combo.options["textvariable"] is editor._profile_name_var
    assert combo.options["values"] == ["default", "gaming", "movie"]
    assert combo.options["width"] == 22
    assert combo.options["state"] == "readonly"
    assert combo.grid_calls == [{"row": 0, "column": 1, "sticky": "ew", "padx": (8, 0)}]
    assert combo.bind_calls == []
    # Regression: construction scans once and popup performs no I/O.
    assert "postcommand" not in combo.options
    assert registry["profiles_list_calls"] == 1
    # The construction snapshot is cached immutably on the editor so later
    # policy saves/syncs never touch the filesystem.
    assert editor._profile_names_snapshot == ("default", "gaming", "movie")

    ac_combo = editor._ac_power_source_profile_combo
    battery_combo = editor._battery_power_source_profile_combo
    assert ac_combo in registry["comboboxes"]
    assert battery_combo in registry["comboboxes"]
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
    assert [call[0] for call in ac_combo.bind_calls] == ["<<ComboboxSelected>>"]
    assert [call[0] for call in battery_combo.bind_calls] == ["<<ComboboxSelected>>"]
    # Regression: power-source popups perform no I/O; values come from the
    # single construction snapshot and preserve the configured profile.
    assert "postcommand" not in ac_combo.options
    assert "postcommand" not in battery_combo.options
    assert registry["profiles_list_calls"] == 1
    assert editor._save_power_source_profile_policy_calls == 0
    editor._ac_power_source_profile_var.set("gaming")
    ac_combo.bind_calls[0][1](None)
    assert editor._save_power_source_profile_policy_calls == 1
    editor._battery_power_source_profile_var.set("default")
    battery_combo.bind_calls[0][1](None)
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
