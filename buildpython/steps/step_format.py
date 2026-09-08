from __future__ import annotations

from ..utils.paths import repo_root
from ..utils.subproc import RunResult, python_exe, run
from .step_defs import POWER_HELPER_PATH


def ruff_format_check_runner() -> RunResult:
    root = repo_root()
    return run(
        [
            python_exe(),
            "-m",
            "ruff",
            "format",
            "--check",
            "keyrgb",
            "buildpython",
            "scripts/release",
            "scripts/dependency_audit.py",
            "tests",
            POWER_HELPER_PATH,
        ],
        cwd=str(root),
        env_overrides={"KEYRGB_HW_TESTS": "0"},
    )
