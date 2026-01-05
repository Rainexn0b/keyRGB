from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _repo_root_dir() -> str:
    # We want the directory that *contains* the `src/` package.
    # - Source checkout: <repo>/src/tray/ui/gui_launch.py -> parents[3] == <repo>
    # - AppImage:        .../usr/lib/keyrgb/src/tray/ui/gui_launch.py -> parents[3] == .../usr/lib/keyrgb
    return str(Path(__file__).resolve().parents[3])


def launch_perkey_gui() -> None:
    """Launch the per-key editor GUI as a subprocess."""

    parent_path = _repo_root_dir()
    subprocess.Popen([sys.executable, "-B", "-m", "src.gui.perkey"], cwd=parent_path)


def launch_uniform_gui() -> None:
    """Launch the uniform color GUI as a subprocess."""

    parent_path = _repo_root_dir()
    subprocess.Popen([sys.executable, "-B", "-m", "src.gui.windows.uniform"], cwd=parent_path)


def launch_reactive_color_gui() -> None:
    """Launch the reactive typing color GUI as a subprocess."""

    parent_path = _repo_root_dir()
    subprocess.Popen([sys.executable, "-B", "-m", "src.gui.windows.reactive_color"], cwd=parent_path)


def launch_power_gui() -> None:
    """Launch the Settings GUI (power rules + autostart) as a subprocess."""

    parent_path = _repo_root_dir()
    env = dict(os.environ)
    # Settings runs in a separate process; tell it the tray PID so it can
    # avoid flagging the tray as an "other" USB holder.
    env["KEYRGB_TRAY_PID"] = str(os.getpid())
    subprocess.Popen([sys.executable, "-B", "-m", "src.gui.settings"], cwd=parent_path, env=env)


def launch_tcc_profiles_gui() -> None:
    """Launch the TCC power profiles GUI as a subprocess."""

    parent_path = _repo_root_dir()
    subprocess.Popen([sys.executable, "-B", "-m", "src.gui.tcc.profiles"], cwd=parent_path)
