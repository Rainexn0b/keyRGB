#!/usr/bin/env python3

from __future__ import annotations

import tkinter as tk
from typing import Any


_WRAP_SYNC_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    value = str(color or "").strip().lstrip("#")
    if len(value) != 6:
        return (64, 64, 64)
    try:
        return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (64, 64, 64)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(255, int(channel))):02x}" for channel in rgb)


def _mix_colors(base: str, target: str, ratio: float) -> str:
    base_rgb = _hex_to_rgb(base)
    target_rgb = _hex_to_rgb(target)
    clamped = max(0.0, min(1.0, float(ratio)))
    mixed = tuple(round(base_rgb[index] + (target_rgb[index] - base_rgb[index]) * clamped) for index in range(3))
    return _rgb_to_hex(mixed)


def _color_luminance(color: str) -> float:
    red, green, blue = _hex_to_rgb(color)
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255.0


def _configure_run_check_styles(window: Any, *, ttk: Any) -> None:
    style = ttk.Style(window.root)
    fg_color = str(window._fg_color or "#f0f0f0")
    bg_color = str(window._bg_color or "#2b2b2b")
    dark_theme = _color_luminance(bg_color) < 0.5

    palette = {
        "SupportChecks.Diagnostics.TButton": ("#315c45", "#3e7558") if dark_theme else ("#d7e9dd", "#c4ddce"),
        "SupportChecks.Probe.TButton": ("#6b5831", "#836c3a") if dark_theme else ("#eee2bf", "#e6d6aa"),
        "SupportChecks.Discovery.TButton": ("#2f5467", "#3a6a80") if dark_theme else ("#d7e6ef", "#c6d9e7"),
    }
    disabled_bg = _mix_colors(bg_color, fg_color, 0.12)
    disabled_fg = _mix_colors(fg_color, bg_color, 0.45)

    for style_name, (button_bg, active_bg) in palette.items():
        style.configure(style_name, background=button_bg, foreground=fg_color, padding=(12, 8))
        style.map(
            style_name,
            background=[("disabled", disabled_bg), ("active", active_bg)],
            foreground=[("disabled", disabled_fg), ("!disabled", fg_color)],
        )


def _register_wrap_target(window: Any, *, label: object, owner: object, padding: int, minimum: int) -> None:
    targets = vars(window).get("_wrap_targets")
    if not isinstance(targets, list):
        targets = []
        setattr(window, "_wrap_targets", targets)
    targets.append((label, owner, int(padding), int(minimum)))


def _sync_wrap_targets(window: Any) -> None:
    targets = vars(window).get("_wrap_targets")
    if not isinstance(targets, list):
        return
    for label, owner, padding, minimum in targets:
        try:
            width = int(owner.winfo_width())
            if width <= 1:
                continue
            label.configure(wraplength=max(int(minimum), width - int(padding)))
        except _WRAP_SYNC_ERRORS:
            continue


def _bind_wrap_sync(window: Any, *widgets: object) -> None:
    def _sync(_event=None) -> None:
        _sync_wrap_targets(window)

    for widget in widgets:
        try:
            widget.bind("<Configure>", _sync, add="+")
        except _WRAP_SYNC_ERRORS:
            continue

    try:
        window.root.after(0, _sync)
    except _WRAP_SYNC_ERRORS:
        return


def _build_action_row(
    window: Any, parent: object, *, ttk: Any, actions: list[tuple[str, Any, str]], columns: int
) -> object:
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=(0, 8))

    total_columns = max(1, int(columns))
    for column in range(total_columns):
        try:
            row.columnconfigure(column, weight=1)
        except _WRAP_SYNC_ERRORS:
            continue

    for index, (label, command, attr_name) in enumerate(actions):
        grid_row = index // total_columns
        grid_column = index % total_columns
        button = ttk.Button(row, text=label, command=command)
        button.grid(
            row=grid_row,
            column=grid_column,
            sticky="ew",
            padx=(0 if grid_column == 0 else 8, 0),
            pady=(0 if grid_row == 0 else 8, 0),
        )
        setattr(window, attr_name, button)

    return row


def build_window(window: Any, *, ttk: Any, scrolledtext: Any, center_window_on_screen: Any) -> None:
    _configure_run_check_styles(window, ttk=ttk)

    main = ttk.Frame(window.root, padding=18)
    main.pack(fill="both", expand=True)
    window._main_frame = main
    window._wrap_targets = []

    ttk.Label(main, text="Support Tools", font=("Sans", 14, "bold")).pack(anchor="w", pady=(0, 6))
    intro_label = ttk.Label(
        main,
        text=(
            "Run read-only support scans directly from the tray workflow.\n"
            "The Debug section explains the current setup; Detect New Backends highlights RGB-related devices that keyRGB sees but may not yet support."
        ),
        font=("Sans", 9),
        justify="left",
        wraplength=1120,
    )
    intro_label.pack(anchor="w", pady=(0, 12))
    _register_wrap_target(window, label=intro_label, owner=main, padding=36, minimum=360)

    window.status_label = ttk.Label(main, text="", font=("Sans", 9))
    window.status_label.pack(anchor="w", pady=(0, 10))

    window.checks_frame = ttk.LabelFrame(main, text="Run Checks", padding=12)
    window.checks_frame.pack(fill="x", pady=(0, 12))
    build_checks_section(window, window.checks_frame, ttk=ttk)

    results_row = ttk.Frame(main)
    results_row.pack(fill="both", expand=True, pady=(0, 12))
    results_row.columnconfigure(0, weight=1, uniform="pane")
    results_row.columnconfigure(1, weight=1, uniform="pane")
    results_row.rowconfigure(0, weight=1)

    window.debug_frame = ttk.LabelFrame(results_row, text="Debug", padding=12)
    window.debug_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    build_debug_section(window, window.debug_frame, ttk=ttk, scrolledtext=scrolledtext)

    window.discovery_frame = ttk.LabelFrame(results_row, text="Detect New Backends", padding=12)
    window.discovery_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
    build_discovery_section(
        window,
        window.discovery_frame,
        ttk=ttk,
        scrolledtext=scrolledtext,
    )

    window.issue_frame = ttk.LabelFrame(main, text="Prepare Support Issue", padding=12)
    window.issue_frame.pack(fill="both", expand=True, pady=(0, 12))
    build_issue_section(window, window.issue_frame, ttk=ttk, scrolledtext=scrolledtext)

    window.bundle_frame = ttk.LabelFrame(main, text="Support Bundle", padding=12)
    window.bundle_frame.pack(fill="x")
    build_bundle_section(window, window.bundle_frame, ttk=ttk)

    _bind_wrap_sync(
        window,
        main,
        window.checks_frame,
        results_row,
        window.debug_frame,
        window.discovery_frame,
        window.issue_frame,
        window.bundle_frame,
    )

    center_window_on_screen(window.root)
    window.root.after(150, window._apply_initial_focus)


def build_checks_section(window: Any, parent: object, *, ttk: Any) -> None:
    desc_label = ttk.Label(
        parent,
        text=(
            "Run the three core support checks from one place. The guided backend speed probe uses the selected backend from the current diagnostics payload when available, or the selected backend from device discovery when that is the only result available."
        ),
        font=("Sans", 9),
        justify="left",
        wraplength=1120,
    )
    desc_label.pack(anchor="w", pady=(0, 10))
    _register_wrap_target(window, label=desc_label, owner=parent, padding=28, minimum=320)

    grid = ttk.Frame(parent)
    grid.pack(fill="x")
    for column in range(3):
        grid.columnconfigure(column, weight=1)

    actions = [
        (
            "Run diagnostics",
            window.run_debug,
            getattr(window, "btn_run_debug", None),
            "SupportChecks.Diagnostics.TButton",
            "Refresh the current backend, USB, system, and config snapshot used by the Debug pane.",
            "btn_run_debug",
        ),
        (
            "Run backend speed probe…",
            window.run_backend_speed_probe,
            getattr(window, "btn_run_speed_probe", None),
            "SupportChecks.Probe.TButton",
            "Temporarily switch the tray to the guided probe effect, step through the test speeds, then record your observation.",
            "btn_run_speed_probe",
        ),
        (
            "Scan devices",
            window.run_discovery,
            getattr(window, "btn_run_discovery", None),
            "SupportChecks.Discovery.TButton",
            "Refresh backend detection for supported, dormant, experimental-disabled, and unrecognized candidates.",
            "btn_run_discovery",
        ),
    ]

    for column, (label, command, _existing, style_name, caption, attr_name) in enumerate(actions):
        cell = ttk.Frame(grid)
        cell.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
        button = ttk.Button(cell, text=label, command=command, style=style_name, width=26)
        button.pack(fill="x")
        setattr(window, attr_name, button)
        caption_label = ttk.Label(cell, text=caption, font=("Sans", 8), justify="left", wraplength=300)
        caption_label.pack(anchor="w", pady=(6, 0))
        _register_wrap_target(window, label=caption_label, owner=cell, padding=8, minimum=180)


def build_debug_section(window: Any, parent: object, *, ttk: Any, scrolledtext: Any) -> None:
    desc_label = ttk.Label(
        parent,
        text="Collect a full read-only diagnostics report for the current setup, including backend probes, USB holders, and configuration state.",
        font=("Sans", 9),
        justify="left",
        wraplength=520,
    )
    desc_label.pack(anchor="w", pady=(0, 8))
    _register_wrap_target(window, label=desc_label, owner=parent, padding=28, minimum=240)

    _build_action_row(
        window,
        parent,
        ttk=ttk,
        actions=[
            ("Copy output", window.copy_debug_output, "btn_copy_debug"),
            ("Save diagnostics JSON…", window.save_debug_output, "btn_save_debug"),
        ],
        columns=2,
    )

    window.txt_debug = scrolledtext.ScrolledText(
        parent,
        height=8,
        wrap="word",
        background=window._bg_color,
        foreground=window._fg_color,
        insertbackground=window._fg_color,
    )
    window.txt_debug.pack(fill="both", expand=True)
    window.txt_debug.insert("1.0", "Click 'Run diagnostics' to collect the current support report.\n")
    window.txt_debug.configure(state="disabled")


def build_discovery_section(
    window: Any,
    parent: object,
    *,
    ttk: Any,
    scrolledtext: Any,
) -> None:
    desc_label = ttk.Label(
        parent,
        text="Scan for supported, dormant, experimental-disabled, and unrecognized ITE-class controller candidates using safe read-only probes.",
        font=("Sans", 9),
        justify="left",
        wraplength=520,
    )
    desc_label.pack(anchor="w", pady=(0, 8))
    _register_wrap_target(window, label=desc_label, owner=parent, padding=28, minimum=240)

    _build_action_row(
        window,
        parent,
        ttk=ttk,
        actions=[
            ("Copy output", window.copy_discovery_output, "btn_copy_discovery"),
            ("Save discovery JSON…", window.save_discovery_output, "btn_save_discovery"),
        ],
        columns=2,
    )

    window.txt_discovery = scrolledtext.ScrolledText(
        parent,
        height=8,
        wrap="word",
        background=window._bg_color,
        foreground=window._fg_color,
        insertbackground=window._fg_color,
    )
    window.txt_discovery.pack(fill="both", expand=True)
    window.txt_discovery.insert(
        "1.0", "Click 'Scan devices' to identify supported and unsupported backend candidates.\n"
    )
    window.txt_discovery.configure(state="disabled")


def build_issue_section(window: Any, parent: object, *, ttk: Any, scrolledtext: Any) -> None:
    desc_label = ttk.Label(
        parent,
        text=(
            "Review the recommended GitHub form before filing. The draft updates automatically from the current diagnostics and discovery results."
        ),
        font=("Sans", 9),
        justify="left",
        wraplength=1120,
    )
    desc_label.pack(anchor="w", pady=(0, 8))
    _register_wrap_target(window, label=desc_label, owner=parent, padding=28, minimum=320)

    window.issue_meta_label = ttk.Label(
        parent,
        text="Suggested template: run diagnostics or discovery first",
        font=("Sans", 9),
        justify="left",
    )
    window.issue_meta_label.pack(anchor="w", pady=(0, 8))

    _build_action_row(
        window,
        parent,
        ttk=ttk,
        actions=[
            ("Copy issue draft", window.copy_issue_report, "btn_copy_issue"),
            ("Save issue draft…", window.save_issue_report, "btn_save_issue"),
            ("Collect missing evidence…", window.collect_missing_evidence, "btn_collect_evidence"),
            ("Open suggested issue", window.open_issue_form, "btn_open_issue"),
        ],
        columns=2,
    )

    window.txt_issue = scrolledtext.ScrolledText(
        parent,
        height=5,
        wrap="word",
        background=window._bg_color,
        foreground=window._fg_color,
        insertbackground=window._fg_color,
    )
    window.txt_issue.pack(fill="both", expand=True)
    window.txt_issue.insert(
        "1.0",
        "Run diagnostics or discovery to generate a suggested issue draft and the recommended GitHub form.\n",
    )
    window.txt_issue.configure(state="disabled")


def build_bundle_section(window: Any, parent: object, *, ttk: Any) -> None:
    desc_label = ttk.Label(
        parent,
        text=(
            "Save a single JSON bundle containing the current diagnostics report, device discovery snapshot, supplemental evidence such as backend probe observations, and the generated issue draft."
        ),
        font=("Sans", 9),
        justify="left",
        wraplength=1120,
    )
    desc_label.pack(anchor="w", pady=(0, 8))
    _register_wrap_target(window, label=desc_label, owner=parent, padding=28, minimum=320)

    _build_action_row(
        window,
        parent,
        ttk=ttk,
        actions=[("Save full support bundle…", window.save_support_bundle, "btn_save_bundle")],
        columns=1,
    )


def apply_initial_focus(window: Any, *, focus_env: str, tk_runtime_errors: tuple[type[BaseException], ...]) -> None:
    try:
        if focus_env == "discovery":
            window.discovery_frame.focus_set()
            window.txt_discovery.focus_set()
        else:
            window.debug_frame.focus_set()
            window.txt_debug.focus_set()
    except tk_runtime_errors:
        return
