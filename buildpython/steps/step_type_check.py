from __future__ import annotations

from ..utils.paths import repo_root
from ..utils.subproc import RunResult, python_exe, run
from .step_defs import POWER_HELPER_PATH


def mypy_runner() -> RunResult:
    root = repo_root()

    # Use pyproject.toml configuration if present.
    # GUI is on the same follow-imports=normal gate as core/tray (C2 exit).
    # The installed helper is extensionless but valid mypy input when passed
    # explicitly; it must stay in this gate so typing drift fails Type Check.
    return run(
        [
            python_exe(),
            "-m",
            "mypy",
            "keyrgb/core",
            "keyrgb/tray",
            "keyrgb/gui",
            "buildpython",
            "scripts/release",
            "scripts/dependency_audit.py",
            "tests/buildpython",
            POWER_HELPER_PATH,
        ],
        cwd=str(root),
        env_overrides={"KEYRGB_HW_TESTS": "0"},
    )
