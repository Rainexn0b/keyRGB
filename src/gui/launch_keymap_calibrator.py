from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def launch_keymap_calibrator() -> None:
    """Launch the Tk keymap calibrator as a separate process.

    Uses the repo root as cwd when available so `-m src.gui.calibrator` resolves
    correctly.
    """

    repo_root = Path(__file__).resolve().parent.parent.parent
    cwd = str(repo_root) if repo_root.exists() else None
    subprocess.Popen([sys.executable, "-m", "src.gui.calibrator"], cwd=cwd)
