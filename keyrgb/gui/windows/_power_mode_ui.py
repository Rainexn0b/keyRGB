"""Content construction for the Power Mode settings window.

Owns the help/copy strings and the ``ttk`` widget tree for
``PowerModeSettingsGUI`` so ``power_mode.py`` stays small. The caller passes
its (monkeypatchable) ``ttk`` module and focus helper; theme metrics are
shared directly since tests compare against them. Adds no behavior.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from types import ModuleType
from typing import Protocol, cast

from keyrgb.gui.theme import metrics as theme_metrics

logger = logging.getLogger(__name__)

_CONTENT_WRAP_PX = 760

_INTRO_TEXT = (
    "Tune KeyRGB's lightweight CPU power-mode integration. Changes here only affect "
    "what happens when you pick Extreme Saver from the tray."
)
_EXTREME_HELP_TEXT = (
    "Extreme Saver pins the CPU min/max frequency to the configured target, "
    "prefers the powersave governor, and turns boost off."
)
_BALANCED_HELP_TEXT = (
    "Balanced restores the CPU min/max frequency range, prefers the schedutil governor, and keeps boost on."
)
_PERFORMANCE_HELP_TEXT = (
    "Performance restores the CPU min/max frequency range, prefers the performance governor, and keeps boost on."
)
_CAP_NOTE_TEXT = (
    "The configured target is stored in KeyRGB config and applied the next time you "
    "choose Extreme Saver. KeyRGB clamps the final write to your CPU's supported "
    "min/max before pinning the range."
)


class _PackableWidget(Protocol):
    def pack(self, **kwargs: object) -> None: ...


class _GridWidget(Protocol):
    def grid(self, **kwargs: object) -> None: ...


class _ColumnConfigurableWidget(Protocol):
    def columnconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None: ...


class _FrameWidget(_PackableWidget, _ColumnConfigurableWidget, Protocol):
    pass


class _ButtonWidget(_GridWidget, Protocol):
    pass


class _ScaleWidget(_PackableWidget, Protocol):
    pass


class _PowerModeWindowState(Protocol):
    root: object
    _main_frame: _FrameWidget
    _status_var: object
    _save_status_var: object
    _live_freq_var: object
    _cap_var: object
    _cap_value_var: object
    scale_cap: _ScaleWidget
    btn_save: _ButtonWidget

    def _refresh_status(self) -> None: ...

    def _save(self) -> None: ...

    def _close(self) -> None: ...

    def _sync_cap_label(self, raw_value: object) -> None: ...


def build_power_mode_ui(
    gui: object,
    *,
    ttk: ModuleType,
    schedule_initial_focus_fn: Callable[..., None],
    cap_mhz_bounds: tuple[int, int],
) -> None:
    """Build the settings widget tree on *gui* (sets ``_main_frame`` etc.)."""

    gui_state = cast(_PowerModeWindowState, gui)

    main_frame = ttk.Frame(gui_state.root, padding=theme_metrics.OUTER_PADDING)
    main_frame.pack(fill="both", expand=True)
    gui_state._main_frame = main_frame

    ttk.Label(main_frame, text="Power Mode Settings", style=theme_metrics.TITLE_LABEL_STYLE).pack(
        anchor="w", pady=(0, theme_metrics.CONTROL_GAP_Y)
    )
    ttk.Label(
        main_frame,
        text=_INTRO_TEXT,
        style=theme_metrics.BODY_LABEL_STYLE,
        justify="left",
        wraplength=_CONTENT_WRAP_PX,
    ).pack(anchor="w", fill="x", pady=(0, theme_metrics.SECTION_GAP_Y))

    status_frame = ttk.LabelFrame(main_frame, text="Current Status", padding=10)
    status_frame.pack(fill="x", pady=(0, theme_metrics.SECTION_GAP_Y))
    ttk.Label(
        status_frame,
        textvariable=gui_state._status_var,
        style=theme_metrics.STATUS_LABEL_STYLE,
        justify="left",
        wraplength=_CONTENT_WRAP_PX,
    ).pack(anchor="w", fill="x")

    help_frame = ttk.LabelFrame(main_frame, text="What The Modes Do", padding=10)
    help_frame.pack(fill="x", pady=(0, theme_metrics.SECTION_GAP_Y))
    for text in (_EXTREME_HELP_TEXT, _BALANCED_HELP_TEXT, _PERFORMANCE_HELP_TEXT):
        ttk.Label(
            help_frame,
            text=text,
            style=theme_metrics.BODY_LABEL_STYLE,
            justify="left",
            wraplength=_CONTENT_WRAP_PX,
        ).pack(anchor="w", fill="x", pady=(0, theme_metrics.CONTROL_GAP_Y))

    cap_frame = ttk.LabelFrame(main_frame, text="Extreme Saver Target", padding=10)
    cap_frame.pack(fill="x", pady=(0, theme_metrics.SECTION_GAP_Y))

    header = ttk.Frame(cap_frame)
    header.pack(fill="x")
    header.columnconfigure(0, weight=1)

    ttk.Label(header, text="Configured CPU frequency target", style=theme_metrics.BODY_LABEL_STYLE).grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(header, textvariable=gui_state._cap_value_var, style=theme_metrics.VALUE_LABEL_STYLE).grid(
        row=0, column=1, sticky="e"
    )

    min_mhz, max_mhz = cap_mhz_bounds
    gui_state.scale_cap = ttk.Scale(
        cap_frame,
        from_=float(min_mhz),
        to=float(max_mhz),
        orient="horizontal",
        variable=gui_state._cap_var,
        command=gui_state._sync_cap_label,
    )
    gui_state.scale_cap.pack(fill="x", pady=(theme_metrics.CONTROL_GAP_Y, theme_metrics.CONTROL_GAP_Y))

    ttk.Label(
        cap_frame,
        text=_CAP_NOTE_TEXT,
        style=theme_metrics.BODY_LABEL_STYLE,
        justify="left",
        wraplength=_CONTENT_WRAP_PX,
    ).pack(anchor="w", fill="x")

    footer = ttk.Frame(main_frame)
    footer.pack(fill="x", pady=(theme_metrics.CONTROL_GAP_Y, 0))
    footer.columnconfigure(0, weight=1)
    footer.columnconfigure(1, weight=0)
    footer.columnconfigure(2, weight=0)
    footer.columnconfigure(3, weight=0)

    ttk.Label(
        footer,
        textvariable=gui_state._save_status_var,
        style=theme_metrics.STATUS_LABEL_STYLE,
        justify="left",
        wraplength=420,
    ).grid(
        row=0,
        column=0,
        columnspan=4,
        sticky="ew",
        pady=(0, theme_metrics.CONTROL_GAP_Y),
    )
    ttk.Button(footer, text="Refresh Status", command=gui_state._refresh_status).grid(
        row=1,
        column=1,
        sticky="ew",
        padx=(0, 8),
    )
    gui_state.btn_save = ttk.Button(
        footer,
        text="Save",
        command=gui_state._save,
        style=theme_metrics.PRIMARY_BUTTON_STYLE,
    )
    gui_state.btn_save.grid(row=1, column=2, sticky="ew", padx=(0, 8))
    ttk.Button(footer, text="Close", command=gui_state._close).grid(row=1, column=3, sticky="ew")
    ttk.Label(
        footer,
        textvariable=gui_state._live_freq_var,
        style=theme_metrics.STATUS_LABEL_STYLE,
        justify="left",
        wraplength=_CONTENT_WRAP_PX,
    ).grid(
        row=2,
        column=0,
        columnspan=4,
        sticky="w",
        pady=(theme_metrics.SECTION_GAP_Y, 0),
    )

    # Intentional non-forcing initial focus (UX-05): Save is the primary
    # action and is always present; the helper schedules via `after`,
    # never grabs, and never steals an already-focused child.
    schedule_initial_focus_fn(gui_state.root, gui_state.btn_save)
