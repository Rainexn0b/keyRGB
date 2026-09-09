from __future__ import annotations

import subprocess

from keyrgb.core.runtime.imports import launch_module_subprocess


def launch_keymap_calibrator() -> subprocess.Popen[bytes]:
    """Launch the Tk keymap calibrator as a separate process."""

    return launch_module_subprocess("keyrgb.gui.calibrator", anchor=__file__, no_bytecode=False)
