#!/usr/bin/env python3

from __future__ import annotations

from . import _support_window_ui_sections as support_window_ui_sections
from . import _support_window_ui_shared as support_window_ui_shared


BindCallback = support_window_ui_shared.BindCallback
AfterCallback = support_window_ui_shared.AfterCallback
_WrapTargetLabelProtocol = support_window_ui_shared._WrapTargetLabelProtocol
_WrapTargetOwnerProtocol = support_window_ui_shared._WrapTargetOwnerProtocol
_StyleProtocol = support_window_ui_shared._StyleProtocol
_StyleFactoryProtocol = support_window_ui_shared._StyleFactoryProtocol
_WidgetProtocol = support_window_ui_shared._WidgetProtocol
_TextWidgetProtocol = support_window_ui_shared._TextWidgetProtocol
_WidgetFactoryProtocol = support_window_ui_shared._WidgetFactoryProtocol
_TextWidgetFactoryProtocol = support_window_ui_shared._TextWidgetFactoryProtocol
_TtkModuleProtocol = support_window_ui_shared._TtkModuleProtocol
_ScrolledTextModuleProtocol = support_window_ui_shared._ScrolledTextModuleProtocol
_RootProtocol = support_window_ui_shared._RootProtocol
WrapTarget = support_window_ui_shared.WrapTarget
ButtonCommand = support_window_ui_shared.ButtonCommand
ActionRowSpec = support_window_ui_shared.ActionRowSpec
CheckActionSpec = support_window_ui_shared.CheckActionSpec
CenterWindowOnScreenFn = support_window_ui_shared.CenterWindowOnScreenFn
_SupportWindowProtocol = support_window_ui_shared._SupportWindowProtocol
_WRAP_SYNC_ERRORS = support_window_ui_shared._WRAP_SYNC_ERRORS
_FALLBACK_WRAP_TARGETS = support_window_ui_shared._FALLBACK_WRAP_TARGETS
_configure_run_check_styles = support_window_ui_shared.configure_run_check_styles
_build_action_row = support_window_ui_shared.build_action_row
_wrap_targets_or_none = support_window_ui_shared.wrap_targets_or_none
_reset_wrap_targets = support_window_ui_shared.reset_wrap_targets
_ensure_wrap_targets = support_window_ui_shared.ensure_wrap_targets
_register_wrap_target = support_window_ui_shared.register_wrap_target
_sync_wrap_targets = support_window_ui_shared.sync_wrap_targets
_bind_wrap_sync = support_window_ui_shared.bind_wrap_sync


def build_window(
    window: _SupportWindowProtocol,
    *,
    ttk: _TtkModuleProtocol,
    scrolledtext: _ScrolledTextModuleProtocol,
    center_window_on_screen: CenterWindowOnScreenFn,
) -> None:
    _configure_run_check_styles(window, ttk=ttk)

    main = ttk.Frame(window.root, padding=18)
    main.pack(fill="both", expand=True)
    window._main_frame = main
    _reset_wrap_targets(window)

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


def build_checks_section(window: _SupportWindowProtocol, parent: _WidgetProtocol, *, ttk: _TtkModuleProtocol) -> None:
    support_window_ui_sections.build_checks_section(
        window,
        parent,
        ttk=ttk,
        register_wrap_target=_register_wrap_target,
    )


def build_debug_section(
    window: _SupportWindowProtocol,
    parent: _WidgetProtocol,
    *,
    ttk: _TtkModuleProtocol,
    scrolledtext: _ScrolledTextModuleProtocol,
) -> None:
    support_window_ui_sections.build_debug_section(
        window,
        parent,
        ttk=ttk,
        scrolledtext=scrolledtext,
        register_wrap_target=_register_wrap_target,
    )


def build_discovery_section(
    window: _SupportWindowProtocol,
    parent: _WidgetProtocol,
    *,
    ttk: _TtkModuleProtocol,
    scrolledtext: _ScrolledTextModuleProtocol,
) -> None:
    support_window_ui_sections.build_discovery_section(
        window,
        parent,
        ttk=ttk,
        scrolledtext=scrolledtext,
        register_wrap_target=_register_wrap_target,
    )


def build_issue_section(
    window: _SupportWindowProtocol,
    parent: _WidgetProtocol,
    *,
    ttk: _TtkModuleProtocol,
    scrolledtext: _ScrolledTextModuleProtocol,
) -> None:
    support_window_ui_sections.build_issue_section(
        window,
        parent,
        ttk=ttk,
        scrolledtext=scrolledtext,
        register_wrap_target=_register_wrap_target,
    )


def build_bundle_section(window: _SupportWindowProtocol, parent: _WidgetProtocol, *, ttk: _TtkModuleProtocol) -> None:
    support_window_ui_sections.build_bundle_section(
        window,
        parent,
        ttk=ttk,
        register_wrap_target=_register_wrap_target,
    )


def apply_initial_focus(
    window: _SupportWindowProtocol,
    *,
    focus_env: str,
    tk_runtime_errors: tuple[type[BaseException], ...],
) -> None:
    try:
        if focus_env == "discovery":
            window.discovery_frame.focus_set()
            window.txt_discovery.focus_set()
        else:
            window.debug_frame.focus_set()
            window.txt_debug.focus_set()
    except tk_runtime_errors:
        return
