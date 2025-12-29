from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root_dir() -> str:
    return str(Path(__file__).resolve().parents[2])


def launch_perkey_gui() -> None:
    """Launch the per-key editor GUI as a subprocess."""

    parent_path = _repo_root_dir()
    try:
        subprocess.Popen([sys.executable, "-m", "src.gui.perkey"], cwd=parent_path)
    except FileNotFoundError:
        subprocess.Popen([sys.executable, "-m", "src.gui_perkey_legacy"], cwd=parent_path)


def launch_uniform_gui() -> None:
    """Launch the uniform color GUI as a subprocess."""

    parent_path = _repo_root_dir()
    subprocess.Popen([sys.executable, "-m", "src.gui.uniform"], cwd=parent_path)


def launch_power_gui() -> None:
    """Launch the Settings GUI (power rules + autostart) as a subprocess."""

    parent_path = _repo_root_dir()
    subprocess.Popen([sys.executable, "-m", "src.gui.power"], cwd=parent_path)


def launch_tcc_profiles_gui() -> None:
    """Launch the TCC power profiles GUI as a subprocess."""

    parent_path = _repo_root_dir()
    subprocess.Popen([sys.executable, "-m", "src.gui.tcc_profiles"], cwd=parent_path)
