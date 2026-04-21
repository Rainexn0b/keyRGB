from __future__ import annotations

from src.core.runtime.imports import launch_module_subprocess


def launch_keymap_calibrator() -> None:
    """Launch the Tk keymap calibrator as a separate process."""

    launch_module_subprocess("src.gui.calibrator", anchor=__file__, no_bytecode=False)
