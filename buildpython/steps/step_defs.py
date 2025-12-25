from __future__ import annotations

from pathlib import Path

from ..core.model import Step
from ..utils.paths import buildlog_dir, repo_root
from ..utils.subproc import python_exe, run


def _log(name: str) -> Path:
    return buildlog_dir() / name


def steps() -> list[Step]:
    root = repo_root()

    def compileall_runner():
        return run(
            [python_exe(), "-m", "compileall", "-q", "src"],
            cwd=str(root),
            env_overrides={"KEYRGB_HW_TESTS": "0"},
        )

    def pytest_runner():
        return run(
            [python_exe(), "-m", "pytest", "-q", "-o", "addopts="],
            cwd=str(root),
            env_overrides={"KEYRGB_HW_TESTS": "0"},
        )

    # Optional: ruff (only runs if installed)
    def ruff_runner():
        return run(
            [python_exe(), "-m", "ruff", "check", "src"],
            cwd=str(root),
            env_overrides={"KEYRGB_HW_TESTS": "0"},
        )

    from .step_quality import code_markers_runner
    from .step_size import file_size_runner

    return [
        Step(
            number=1,
            name="Compile",
            description="Compile all Python sources (syntax check)",
            log_file=_log("step-01-compile.log"),
            runner=compileall_runner,
        ),
        Step(
            number=2,
            name="Pytest",
            description="Run tests (hardware tests opt-in)",
            log_file=_log("step-02-pytest.log"),
            runner=pytest_runner,
        ),
        Step(
            number=3,
            name="Ruff",
            description="Lint with ruff (optional)",
            log_file=_log("step-03-ruff.log"),
            runner=ruff_runner,
        ),
        Step(
            number=4,
            name="Code Markers",
            description="Scan for TODO/FIXME/HACK and refactoring markers",
            log_file=_log("step-04-code-markers.log"),
            runner=code_markers_runner,
        ),
        Step(
            number=5,
            name="File Size",
            description="Analyze large Python files (line thresholds)",
            log_file=_log("step-05-file-size.log"),
            runner=file_size_runner,
        ),
    ]
