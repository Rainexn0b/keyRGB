#!/usr/bin/env python3

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk
from typing import Protocol, TypeAlias, cast
from weakref import WeakKeyDictionary


BindCallback: TypeAlias = Callable[[object | None], None]
AfterCallback: TypeAlias = Callable[[], None]


class _WrapTargetLabelProtocol(Protocol):
    def configure(self, **kwargs: object) -> None: ...


class _WrapTargetOwnerProtocol(Protocol):
    def winfo_width(self) -> int: ...


class _StyleProtocol(Protocol):
    def configure(self, name: str, **kwargs: object) -> None: ...

    def map(self, name: str, **kwargs: object) -> None: ...


class _StyleFactoryProtocol(Protocol):
    def __call__(self, master: object) -> _StyleProtocol: ...


class _WidgetProtocol(Protocol):
    def configure(self, **kwargs: object) -> None: ...

    def pack(self, *args: object, **kwargs: object) -> None: ...

    def grid(self, *args: object, **kwargs: object) -> None: ...

    def bind(self, sequence: str, callback: BindCallback, add: object = None) -> None: ...

    def focus_set(self) -> None: ...

    def columnconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None: ...

    def rowconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None: ...

    def winfo_width(self) -> int: ...

    def winfo_reqwidth(self) -> int: ...

    def winfo_reqheight(self) -> int: ...


class _TextWidgetProtocol(_WidgetProtocol, Protocol):
    def insert(self, index: str, value: str) -> None: ...


class _WidgetFactoryProtocol(Protocol):
    def __call__(self, parent: object | None = None, **kwargs: object) -> _WidgetProtocol: ...


class _TextWidgetFactoryProtocol(Protocol):
    def __call__(self, parent: object | None = None, **kwargs: object) -> _TextWidgetProtocol: ...


class _TtkModuleProtocol(Protocol):
    Style: _StyleFactoryProtocol
    Frame: _WidgetFactoryProtocol
    LabelFrame: _WidgetFactoryProtocol
    Label: _WidgetFactoryProtocol
    Button: _WidgetFactoryProtocol


class _ScrolledTextModuleProtocol(Protocol):
    ScrolledText: _TextWidgetFactoryProtocol


class _RootProtocol(Protocol):
    def after(self, delay_ms: int, callback: AfterCallback) -> None: ...


WrapTarget: TypeAlias = tuple[_WrapTargetLabelProtocol, _WrapTargetOwnerProtocol, int, int]
ButtonCommand: TypeAlias = Callable[[], None]
ActionRowSpec: TypeAlias = tuple[str, ButtonCommand, str]
CheckActionSpec: TypeAlias = tuple[str, ButtonCommand, str, str, str]
CenterWindowOnScreenFn: TypeAlias = Callable[[_RootProtocol], None]


class _SupportWindowProtocol(Protocol):
    root: _RootProtocol
    _bg_color: str
    _fg_color: str
    _main_frame: _WidgetProtocol
    _wrap_targets: list[WrapTarget]
    status_label: _WidgetProtocol
    checks_frame: _WidgetProtocol
    debug_frame: _WidgetProtocol
    discovery_frame: _WidgetProtocol
    issue_frame: _WidgetProtocol
    bundle_frame: _WidgetProtocol
    issue_meta_label: _WidgetProtocol
    txt_debug: _TextWidgetProtocol
    txt_discovery: _TextWidgetProtocol
    txt_issue: _TextWidgetProtocol
    btn_run_debug: _WidgetProtocol
    btn_run_speed_probe: _WidgetProtocol
    btn_run_discovery: _WidgetProtocol
    btn_copy_debug: _WidgetProtocol
    btn_save_debug: _WidgetProtocol
    btn_copy_discovery: _WidgetProtocol
    btn_save_discovery: _WidgetProtocol
    btn_copy_issue: _WidgetProtocol
    btn_save_issue: _WidgetProtocol
    btn_collect_evidence: _WidgetProtocol
    btn_open_issue: _WidgetProtocol
    btn_save_bundle: _WidgetProtocol

    def _apply_initial_focus(self) -> None: ...

    def run_debug(self) -> None: ...

    def run_backend_speed_probe(self, *, prompt: bool = True) -> None: ...

    def run_discovery(self) -> None: ...

    def copy_debug_output(self) -> None: ...

    def save_debug_output(self) -> None: ...

    def copy_discovery_output(self) -> None: ...

    def save_discovery_output(self) -> None: ...

    def copy_issue_report(self) -> None: ...

    def save_issue_report(self) -> None: ...

    def collect_missing_evidence(self, *, prompt: bool = True) -> None: ...

    def open_issue_form(self) -> None: ...

    def save_support_bundle(self) -> None: ...


class _RegisterWrapTargetFn(Protocol):
    def __call__(
        self,
        window: object,
        *,
        label: object,
        owner: object,
        padding: int,
        minimum: int,
    ) -> None: ...


_WRAP_SYNC_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)
_FALLBACK_WRAP_TARGETS: WeakKeyDictionary[object, list[WrapTarget]] = WeakKeyDictionary()


def wrap_targets_or_none(window: object) -> list[WrapTarget] | None:
    raw_targets = vars(window).get("_wrap_targets")
    if isinstance(raw_targets, list):
        return cast(list[WrapTarget], raw_targets)
    return _FALLBACK_WRAP_TARGETS.get(window)


def reset_wrap_targets(window: _SupportWindowProtocol) -> None:
    _FALLBACK_WRAP_TARGETS.pop(window, None)
    window._wrap_targets = []


def ensure_wrap_targets(window: object) -> list[WrapTarget]:
    targets = wrap_targets_or_none(window)
    if targets is not None:
        return targets

    targets = []
    _FALLBACK_WRAP_TARGETS[window] = targets
    return targets


def register_wrap_target(
    window: object,
    *,
    label: _WrapTargetLabelProtocol,
    owner: _WrapTargetOwnerProtocol,
    padding: int,
    minimum: int,
) -> None:
    ensure_wrap_targets(window).append((label, owner, int(padding), int(minimum)))


def sync_wrap_targets(window: object) -> None:
    targets = wrap_targets_or_none(window)
    if targets is None:
        return
    for label, owner, padding, minimum in targets:
        try:
            width = int(owner.winfo_width())
            if width <= 1:
                continue
            label.configure(wraplength=max(int(minimum), width - int(padding)))
        except _WRAP_SYNC_ERRORS:
            continue


def bind_wrap_sync(window: _SupportWindowProtocol, *widgets: _WidgetProtocol) -> None:
    def _sync(_event: object | None = None) -> None:
        sync_wrap_targets(window)

    for widget in widgets:
        try:
            widget.bind("<Configure>", _sync, add="+")
        except _WRAP_SYNC_ERRORS:
            continue

    try:
        window.root.after(0, _sync)
    except _WRAP_SYNC_ERRORS:
        return


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    value = str(color or "").strip().lstrip("#")
    if len(value) != 6:
        return (64, 64, 64)
    try:
        red = int(value[0:2], 16)
        green = int(value[2:4], 16)
        blue = int(value[4:6], 16)
    except ValueError:
        return (64, 64, 64)
    return red, green, blue


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


def configure_run_check_styles(window: _SupportWindowProtocol, *, ttk: _TtkModuleProtocol) -> None:
    style = ttk.Style(window.root)
    fg_color = str(window._fg_color or "#f0f0f0")
    bg_color = str(window._bg_color or "#2b2b2b")
    dark_theme = _color_luminance(bg_color) < 0.5

    palette: dict[str, tuple[str, str]] = {
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


_ACTION_ROW_LAYOUT_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)


def build_action_row(
    window: object,
    parent: _WidgetProtocol,
    *,
    ttk: _TtkModuleProtocol,
    actions: list[ActionRowSpec],
    columns: int,
) -> _WidgetProtocol:
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=(0, 8))

    total_columns = max(1, int(columns))
    for column in range(total_columns):
        try:
            row.columnconfigure(column, weight=1)
        except _ACTION_ROW_LAYOUT_ERRORS:
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
