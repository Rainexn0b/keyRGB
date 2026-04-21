from __future__ import annotations

import os
import subprocess
import sys

from src.core.runtime.imports import launcher_cwd_from


def launch_perkey_gui() -> None:
    """Launch the per-key editor GUI as a subprocess."""

    subprocess.Popen([sys.executable, "-B", "-m", "src.gui.perkey"], cwd=launcher_cwd_from(__file__))


def launch_uniform_gui(*, target_context: str = "keyboard", backend_name: str | None = None) -> None:
    """Launch the uniform color GUI as a subprocess."""

    env = dict(os.environ)
    env["KEYRGB_UNIFORM_TARGET_CONTEXT"] = str(target_context or "keyboard").strip().lower() or "keyboard"
    if backend_name:
        env["KEYRGB_UNIFORM_BACKEND"] = str(backend_name).strip().lower()
    else:
        env.pop("KEYRGB_UNIFORM_BACKEND", None)
    subprocess.Popen([sys.executable, "-B", "-m", "src.gui.windows.uniform"], cwd=launcher_cwd_from(__file__), env=env)


def launch_reactive_color_gui() -> None:
    """Launch the reactive typing color GUI as a subprocess."""

    subprocess.Popen([sys.executable, "-B", "-m", "src.gui.windows.reactive_color"], cwd=launcher_cwd_from(__file__))


def launch_power_gui() -> None:
    """Launch the Settings GUI (power rules + autostart) as a subprocess."""

    env = dict(os.environ)
    # Settings runs in a separate process; tell it the tray PID so it can
    # avoid flagging the tray as an "other" USB holder.
    env["KEYRGB_TRAY_PID"] = str(os.getpid())
    subprocess.Popen([sys.executable, "-B", "-m", "src.gui.settings"], cwd=launcher_cwd_from(__file__), env=env)


def launch_support_gui(*, focus: str = "debug") -> None:
    """Launch the support tools window as a subprocess."""

    env = dict(os.environ)
    env["KEYRGB_TRAY_PID"] = str(os.getpid())
    env["KEYRGB_SUPPORT_FOCUS"] = str(focus or "debug").strip().lower()
    subprocess.Popen([sys.executable, "-B", "-m", "src.gui.windows.support"], cwd=launcher_cwd_from(__file__), env=env)


def launch_tcc_profiles_gui() -> None:
    """Launch the TCC power profiles GUI as a subprocess."""

    subprocess.Popen([sys.executable, "-B", "-m", "src.gui.tcc.profiles"], cwd=launcher_cwd_from(__file__))
