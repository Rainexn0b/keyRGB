from __future__ import annotations

from ..utils.paths import repo_root
from ..utils.subproc import RunResult, python_exe, run


def mypy_runner() -> RunResult:
    root = repo_root()

    # Use pyproject.toml configuration if present.
    # Keep scope limited to the main code and build tooling (exclude tests).
    return run(
        [
            python_exe(),
            "-m",
            "mypy",
            "src/core",
            "src/tray",
            "buildpython",
        ],
        cwd=str(root),
        env_overrides={"KEYRGB_HW_TESTS": "0"},
    )
