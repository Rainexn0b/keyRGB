from __future__ import annotations

import subprocess
import sys

from src.core.runtime.imports import launcher_cwd_from


def launch_keymap_calibrator() -> None:
    """Launch the Tk keymap calibrator as a separate process."""

    subprocess.Popen([sys.executable, "-m", "src.gui.calibrator"], cwd=launcher_cwd_from(__file__))
