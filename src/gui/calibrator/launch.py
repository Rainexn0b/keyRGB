from __future__ import annotations

import subprocess
import sys

from src.core.runtime.imports import repo_root_from


def _repo_root_dir() -> str | None:
    repo_root = repo_root_from(__file__)
    return str(repo_root) if repo_root.exists() else None


def launch_keymap_calibrator() -> None:
    """Launch the Tk keymap calibrator as a separate process."""

    subprocess.Popen([sys.executable, "-m", "src.gui.calibrator"], cwd=_repo_root_dir())
