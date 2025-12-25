from __future__ import annotations

from ..utils.paths import repo_root
from ..utils.subproc import RunResult, python_exe, run


def ruff_format_check_runner() -> RunResult:
    root = repo_root()
    return run(
        [python_exe(), "-m", "ruff", "format", "--check", "src"],
        cwd=str(root),
        env_overrides={"KEYRGB_HW_TESTS": "0"},
    )
