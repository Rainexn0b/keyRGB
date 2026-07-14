from __future__ import annotations

import os

from src.core.runtime.imports import launch_module_subprocess


def _inherited_gui_environment() -> dict[str, str]:
    """Return the parent environment for GUI subprocesses."""
    return dict(os.environ)


def launch_perkey_gui() -> None:
    """Launch the per-key editor GUI as a subprocess."""

    launch_module_subprocess("src.gui.perkey", anchor=__file__, env=_inherited_gui_environment())


def launch_uniform_gui(*, target_context: str = "keyboard", backend_name: str | None = None) -> None:
    """Launch the uniform color GUI as a subprocess."""

    env = _inherited_gui_environment()
    env["KEYRGB_UNIFORM_TARGET_CONTEXT"] = str(target_context or "keyboard").strip().lower() or "keyboard"
    if backend_name:
        env["KEYRGB_UNIFORM_BACKEND"] = str(backend_name).strip().lower()
    else:
        env.pop("KEYRGB_UNIFORM_BACKEND", None)
    launch_module_subprocess("src.gui.windows.uniform", anchor=__file__, env=env)


def launch_reactive_color_gui() -> None:
    """Launch the reactive typing color GUI as a subprocess."""

    launch_module_subprocess("src.gui.windows.reactive_color", anchor=__file__)


def launch_power_gui() -> None:
    """Launch the Settings GUI (power rules + autostart) as a subprocess."""

    env = dict(os.environ)
    # Settings runs in a separate process; tell it the tray PID so it can
    # avoid flagging the tray as an "other" USB holder.
    env["KEYRGB_TRAY_PID"] = str(os.getpid())
    launch_module_subprocess("src.gui.settings", anchor=__file__, env=env)


def launch_power_mode_settings_gui() -> None:
    """Launch the lightweight power mode settings GUI as a subprocess."""

    launch_module_subprocess("src.gui.windows.power_mode", anchor=__file__)


def launch_support_gui(*, focus: str = "debug") -> None:
    """Launch the support tools window as a subprocess."""

    env = dict(os.environ)
    env["KEYRGB_TRAY_PID"] = str(os.getpid())
    env["KEYRGB_SUPPORT_FOCUS"] = str(focus or "debug").strip().lower()
    launch_module_subprocess("src.gui.windows.support", anchor=__file__, env=env)
