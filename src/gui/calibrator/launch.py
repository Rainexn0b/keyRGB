from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root_dir() -> str | None:
    # We want the directory that *contains* the `src/` package.
    # - Source checkout: <repo>/src/gui/calibrator/launch.py -> parents[3] == <repo>
    # - AppImage:        .../usr/lib/keyrgb/src/gui/calibrator/launch.py -> parents[3] == .../usr/lib/keyrgb
    repo_root = Path(__file__).resolve().parents[3]
    return str(repo_root) if repo_root.exists() else None


def launch_keymap_calibrator() -> None:
    """Launch the Tk keymap calibrator as a separate process."""

    subprocess.Popen([sys.executable, "-m", "src.gui.calibrator"], cwd=_repo_root_dir())
