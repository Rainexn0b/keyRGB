from __future__ import annotations

from keyrgb.core.runtime.imports import launch_module_subprocess


def launch_keymap_calibrator() -> None:
    """Launch the Tk keymap calibrator as a separate process."""

    launch_module_subprocess("keyrgb.gui.calibrator", anchor=__file__, no_bytecode=False)
