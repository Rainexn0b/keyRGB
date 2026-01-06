from __future__ import annotations

from ..utils.paths import repo_root
from ..utils.subproc import RunResult, python_exe, run


def black_check_runner() -> RunResult:
    root = repo_root()

    # Keep this a check-only step; formatting is done by contributors locally.
    # Include both runtime code and build tooling.
    return run(
        [
            python_exe(),
            "-m",
            "black",
            "--check",
            "--diff",
            "src",
            "buildpython",
        ],
        cwd=str(root),
        env_overrides={"KEYRGB_HW_TESTS": "0"},
    )
