from __future__ import annotations

import subprocess
from pathlib import Path

from keyrgb.core.runtime.imports import (
    launch_module_subprocess,
    launcher_cwd_from,
    launcher_python_argv,
)


def launch_keymap_calibrator() -> subprocess.Popen[bytes]:
    """Launch the Tk keymap calibrator as a separate process."""

    return launch_module_subprocess("keyrgb.gui.calibrator", anchor=__file__, no_bytecode=False)


def launch_guided_calibrator(session_path: str | Path) -> subprocess.Popen[bytes]:
    """Launch the calibrator in guided-session mode as a separate process.

    Uses the same interpreter, module target, and repo-root working directory
    as :func:`launch_keymap_calibrator`; the only difference is the appended
    ``--guided-session PATH`` argument.  Never uses a shell.
    """

    argv = [*launcher_python_argv("keyrgb.gui.calibrator", no_bytecode=False), "--guided-session", str(session_path)]
    return subprocess.Popen(argv, cwd=launcher_cwd_from(__file__))
