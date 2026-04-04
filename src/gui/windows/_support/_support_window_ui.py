#!/usr/bin/env python3

from __future__ import annotations

from typing import Any


def build_window(window: Any, *, ttk: Any, scrolledtext: Any, center_window_on_screen: Any) -> None:
    main = ttk.Frame(window.root, padding=18)
    main.pack(fill="both", expand=True)

    ttk.Label(main, text="Support Tools", font=("Sans", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(
        main,
        text=(
            "Run read-only support scans directly from the tray workflow.\n"
            "The Debug section explains the current setup; Detect New Backends highlights RGB-related devices that keyRGB sees but may not yet support."
        ),
        font=("Sans", 9),
        justify="left",
    ).pack(anchor="w", pady=(0, 12))

    window.status_label = ttk.Label(main, text="", font=("Sans", 9))
    window.status_label.pack(anchor="w", pady=(0, 10))

    window.debug_frame = ttk.LabelFrame(main, text="Debug", padding=12)
    window.debug_frame.pack(fill="both", expand=True, pady=(0, 12))
    build_debug_section(window, window.debug_frame, ttk=ttk, scrolledtext=scrolledtext)

    window.discovery_frame = ttk.LabelFrame(main, text="Detect New Backends", padding=12)
    window.discovery_frame.pack(fill="both", expand=True)
    build_discovery_section(window, window.discovery_frame, ttk=ttk, scrolledtext=scrolledtext)

    window.issue_frame = ttk.LabelFrame(main, text="Prepare Support Issue", padding=12)
    window.issue_frame.pack(fill="both", expand=True, pady=(12, 0))
    build_issue_section(window, window.issue_frame, ttk=ttk, scrolledtext=scrolledtext)

    center_window_on_screen(window.root)
    window.root.after(150, window._apply_initial_focus)


def build_debug_section(window: Any, parent: object, *, ttk: Any, scrolledtext: Any) -> None:
    ttk.Label(
        parent,
        text="Collect a full read-only diagnostics report for the current setup, including backend probes, USB holders, and configuration state.",
        font=("Sans", 9),
        justify="left",
        wraplength=860,
    ).pack(anchor="w", pady=(0, 8))

    row = ttk.Frame(parent)
    row.pack(fill="x", pady=(0, 8))

    window.btn_run_debug = ttk.Button(row, text="Run diagnostics", command=window.run_debug)
    window.btn_run_debug.pack(side="left")
    window.btn_copy_debug = ttk.Button(row, text="Copy output", command=window.copy_debug_output)
    window.btn_copy_debug.pack(side="left", padx=(8, 0))
    window.btn_save_debug = ttk.Button(row, text="Save diagnostics JSON…", command=window.save_debug_output)
    window.btn_save_debug.pack(side="left", padx=(8, 0))
    ttk.Button(row, text="Open issue", command=window.open_issue_form).pack(side="left", padx=(8, 0))

    probe_row = ttk.Frame(parent)
    probe_row.pack(fill="x", pady=(0, 8))
    ttk.Label(probe_row, text="Guided backend probe:", font=("Sans", 9)).pack(side="left")
    window.btn_run_speed_probe = ttk.Button(
        probe_row,
        text="Run backend speed probe…",
        command=window.run_backend_speed_probe,
    )
    window.btn_run_speed_probe.pack(side="left", padx=(8, 0))

    window.txt_debug = scrolledtext.ScrolledText(
        parent,
        height=12,
        wrap="word",
        background=window._bg_color,
        foreground=window._fg_color,
        insertbackground=window._fg_color,
    )
    window.txt_debug.pack(fill="both", expand=True)
    window.txt_debug.insert("1.0", "Click 'Run diagnostics' to collect the current support report.\n")
    window.txt_debug.configure(state="disabled")


def build_discovery_section(window: Any, parent: object, *, ttk: Any, scrolledtext: Any) -> None:
    ttk.Label(
        parent,
        text="Scan for supported, dormant, experimental-disabled, and unrecognized ITE-class controller candidates using safe read-only probes.",
        font=("Sans", 9),
        justify="left",
        wraplength=860,
    ).pack(anchor="w", pady=(0, 8))

    row = ttk.Frame(parent)
    row.pack(fill="x", pady=(0, 8))

    window.btn_run_discovery = ttk.Button(row, text="Scan devices", command=window.run_discovery)
    window.btn_run_discovery.pack(side="left")
    window.btn_copy_discovery = ttk.Button(row, text="Copy output", command=window.copy_discovery_output)
    window.btn_copy_discovery.pack(side="left", padx=(8, 0))
    window.btn_save_discovery = ttk.Button(row, text="Save discovery JSON…", command=window.save_discovery_output)
    window.btn_save_discovery.pack(side="left", padx=(8, 0))
    window.btn_save_bundle = ttk.Button(row, text="Save full support bundle…", command=window.save_support_bundle)
    window.btn_save_bundle.pack(side="left", padx=(8, 0))

    window.txt_discovery = scrolledtext.ScrolledText(
        parent,
        height=10,
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
    ttk.Label(
        parent,
        text=(
            "Review the recommended GitHub form before filing. The draft updates automatically from the current diagnostics and discovery results."
        ),
        font=("Sans", 9),
        justify="left",
        wraplength=860,
    ).pack(anchor="w", pady=(0, 8))

    window.issue_meta_label = ttk.Label(
        parent,
        text="Suggested template: run diagnostics or discovery first",
        font=("Sans", 9),
        justify="left",
    )
    window.issue_meta_label.pack(anchor="w", pady=(0, 8))

    row = ttk.Frame(parent)
    row.pack(fill="x", pady=(0, 8))

    window.btn_copy_issue = ttk.Button(row, text="Copy issue draft", command=window.copy_issue_report)
    window.btn_copy_issue.pack(side="left")
    window.btn_save_issue = ttk.Button(row, text="Save issue draft…", command=window.save_issue_report)
    window.btn_save_issue.pack(side="left", padx=(8, 0))
    window.btn_collect_evidence = ttk.Button(
        row, text="Collect missing evidence…", command=window.collect_missing_evidence
    )
    window.btn_collect_evidence.pack(side="left", padx=(8, 0))
    window.btn_open_issue = ttk.Button(row, text="Open suggested issue", command=window.open_issue_form)
    window.btn_open_issue.pack(side="left", padx=(8, 0))

    window.txt_issue = scrolledtext.ScrolledText(
        parent,
        height=11,
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
