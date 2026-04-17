#!/usr/bin/env python3

from __future__ import annotations

from . import _support_window_ui_shared as support_window_ui_shared


CheckActionSpec = support_window_ui_shared.CheckActionSpec
_ScrolledTextModuleProtocol = support_window_ui_shared._ScrolledTextModuleProtocol
_SupportWindowProtocol = support_window_ui_shared._SupportWindowProtocol
_TtkModuleProtocol = support_window_ui_shared._TtkModuleProtocol
_WidgetProtocol = support_window_ui_shared._WidgetProtocol
_RegisterWrapTargetFn = support_window_ui_shared._RegisterWrapTargetFn
configure_run_check_styles = support_window_ui_shared.configure_run_check_styles
_build_action_row = support_window_ui_shared.build_action_row


def build_checks_section(
    window: _SupportWindowProtocol,
    parent: _WidgetProtocol,
    *,
    ttk: _TtkModuleProtocol,
    register_wrap_target: _RegisterWrapTargetFn,
) -> None:
    desc_label = ttk.Label(
        parent,
        text=(
            "Run the three core support checks from one place. The guided backend speed probe uses the selected "
            "backend from the current diagnostics payload when available, or the selected backend from device "
            "discovery when that is the only result available."
        ),
        font=("Sans", 9),
        justify="left",
        wraplength=1120,
    )
    desc_label.pack(anchor="w", pady=(0, 10))
    register_wrap_target(window, label=desc_label, owner=parent, padding=28, minimum=320)

    grid = ttk.Frame(parent)
    grid.pack(fill="x")
    for column in range(3):
        grid.columnconfigure(column, weight=1)

    actions: list[CheckActionSpec] = [
        (
            "Run diagnostics",
            window.run_debug,
            "SupportChecks.Diagnostics.TButton",
            "Refresh the current backend, USB, system, and config snapshot used by the Debug pane.",
            "btn_run_debug",
        ),
        (
            "Run backend speed probe…",
            window.run_backend_speed_probe,
            "SupportChecks.Probe.TButton",
            "Temporarily switch the tray to the guided probe effect, step through the test speeds, then "
            "record your observation.",
            "btn_run_speed_probe",
        ),
        (
            "Scan devices",
            window.run_discovery,
            "SupportChecks.Discovery.TButton",
            "Refresh backend detection for supported, dormant, experimental-disabled, and unrecognized candidates.",
            "btn_run_discovery",
        ),
    ]

    for column, (label, command, style_name, caption, attr_name) in enumerate(actions):
        cell = ttk.Frame(grid)
        cell.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
        button = ttk.Button(cell, text=label, command=command, style=style_name, width=26)
        button.pack(fill="x")
        setattr(window, attr_name, button)
        caption_label = ttk.Label(cell, text=caption, font=("Sans", 8), justify="left", wraplength=300)
        caption_label.pack(anchor="w", pady=(6, 0))
        register_wrap_target(window, label=caption_label, owner=cell, padding=8, minimum=180)


def build_debug_section(
    window: _SupportWindowProtocol,
    parent: _WidgetProtocol,
    *,
    ttk: _TtkModuleProtocol,
    scrolledtext: _ScrolledTextModuleProtocol,
    register_wrap_target: _RegisterWrapTargetFn,
) -> None:
    desc_label = ttk.Label(
        parent,
        text=(
            "Collect a full read-only diagnostics report for the current setup, including backend probes, "
            "USB holders, and configuration state."
        ),
        font=("Sans", 9),
        justify="left",
        wraplength=520,
    )
    desc_label.pack(anchor="w", pady=(0, 8))
    register_wrap_target(window, label=desc_label, owner=parent, padding=28, minimum=240)

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
    window: _SupportWindowProtocol,
    parent: _WidgetProtocol,
    *,
    ttk: _TtkModuleProtocol,
    scrolledtext: _ScrolledTextModuleProtocol,
    register_wrap_target: _RegisterWrapTargetFn,
) -> None:
    desc_label = ttk.Label(
        parent,
        text=(
            "Scan for supported, dormant, experimental-disabled, and unrecognized ITE-class controller "
            "candidates using safe read-only probes."
        ),
        font=("Sans", 9),
        justify="left",
        wraplength=520,
    )
    desc_label.pack(anchor="w", pady=(0, 8))
    register_wrap_target(window, label=desc_label, owner=parent, padding=28, minimum=240)

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
        "1.0",
        "Click 'Scan devices' to identify supported and unsupported backend candidates.\n",
    )
    window.txt_discovery.configure(state="disabled")


def build_issue_section(
    window: _SupportWindowProtocol,
    parent: _WidgetProtocol,
    *,
    ttk: _TtkModuleProtocol,
    scrolledtext: _ScrolledTextModuleProtocol,
    register_wrap_target: _RegisterWrapTargetFn,
) -> None:
    desc_label = ttk.Label(
        parent,
        text=(
            "Review the recommended GitHub form before filing. The draft updates automatically from the current "
            "diagnostics and discovery results."
        ),
        font=("Sans", 9),
        justify="left",
        wraplength=1120,
    )
    desc_label.pack(anchor="w", pady=(0, 8))
    register_wrap_target(window, label=desc_label, owner=parent, padding=28, minimum=320)

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


def build_bundle_section(
    window: _SupportWindowProtocol,
    parent: _WidgetProtocol,
    *,
    ttk: _TtkModuleProtocol,
    register_wrap_target: _RegisterWrapTargetFn,
) -> None:
    desc_label = ttk.Label(
        parent,
        text=(
            "Save a single JSON bundle containing the current diagnostics report, device discovery snapshot, "
            "supplemental evidence such as backend probe observations, and the generated issue draft."
        ),
        font=("Sans", 9),
        justify="left",
        wraplength=1120,
    )
    desc_label.pack(anchor="w", pady=(0, 8))
    register_wrap_target(window, label=desc_label, owner=parent, padding=28, minimum=320)

    _build_action_row(
        window,
        parent,
        ttk=ttk,
        actions=[("Save full support bundle…", window.save_support_bundle, "btn_save_bundle")],
        columns=1,
    )
