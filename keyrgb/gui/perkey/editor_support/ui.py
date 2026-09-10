from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from keyrgb.gui.theme.focus import schedule_initial_focus
from keyrgb.gui.widgets.color_wheel import ColorWheel

from ..canvas import KeyboardCanvas
from ..lightbar_controls import LightbarControls
from ..overlay import OverlayControls
from ..ui.layout_setup import LayoutSetupControls, OptionalKeysControls
from ..ui.lighting_areas import LightingAreasPanel
from .ui_advanced import build_advanced_tab
from .ui_shell import build_shell
from .ui_tabs import build_tabs


def build_editor_ui(editor) -> None:
    main = build_shell(
        editor,
        ttk=ttk,
        tk=tk,
        KeyboardCanvas=KeyboardCanvas,
        ColorWheel=ColorWheel,
    )
    build_tabs(
        editor,
        main,
        ttk=ttk,
        LayoutSetupControls=LayoutSetupControls,
        OptionalKeysControls=OptionalKeysControls,
    )
    build_advanced_tab(
        editor,
        ttk=ttk,
        tk=tk,
        OverlayControls=OverlayControls,
        LightbarControls=LightbarControls,
        LightingAreasPanel=LightingAreasPanel,
    )

    editor.overlay_controls.sync_vars_from_scope()
    if editor.lightbar_controls is not None:
        editor.lightbar_controls.sync_vars_from_editor()

    # Intentional non-forcing initial focus (UX-05): the backdrop selector is
    # the first keyboard-operable control and always exists. The helper
    # schedules via `after`, never grabs, and never steals an already-focused
    # child. Keymap refresh after calibration is tied to calibrator process
    # completion, so ordinary focus movement performs no profile I/O.
    schedule_initial_focus(editor.root, editor._backdrop_mode_combo)
