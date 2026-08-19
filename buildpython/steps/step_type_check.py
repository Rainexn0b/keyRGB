from __future__ import annotations

from ..utils.paths import repo_root
from ..utils.subproc import RunResult, python_exe, run


def mypy_runner() -> RunResult:
    root = repo_root()

    # Use pyproject.toml configuration if present.
    # GUI is on the same follow-imports=normal gate as core/tray (C2 exit).
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
            "tests/buildpython",
        ],
        cwd=str(root),
        env_overrides={"KEYRGB_HW_TESTS": "0"},
    )
