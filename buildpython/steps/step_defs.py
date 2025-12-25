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
    from .step_imports import import_validation_runner
    from .step_format import ruff_format_check_runner
    from .step_pip import pip_check_runner
    from .step_import_scan import import_scan_runner

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
            name="Import Validation",
            description="Import core modules to catch missing deps / import errors",
            log_file=_log("step-04-imports.log"),
            runner=import_validation_runner,
        ),
        Step(
            number=5,
            name="Code Markers",
            description="Scan for TODO/FIXME/HACK and refactoring markers",
            log_file=_log("step-05-code-markers.log"),
            runner=code_markers_runner,
        ),
        Step(
            number=6,
            name="File Size",
            description="Analyze large Python files (line thresholds)",
            log_file=_log("step-06-file-size.log"),
            runner=file_size_runner,
        ),
        Step(
            number=7,
            name="Ruff Format",
            description="Check formatting with ruff format (optional)",
            log_file=_log("step-07-ruff-format.log"),
            runner=ruff_format_check_runner,
        ),
        Step(
            number=8,
            name="Pip Check",
            description="Validate installed dependencies (pip check)",
            log_file=_log("step-08-pip-check.log"),
            runner=pip_check_runner,
        ),
        Step(
            number=9,
            name="Import Scan",
            description="Parse imports and verify required modules import",
            log_file=_log("step-09-import-scan.log"),
            runner=import_scan_runner,
        ),
    ]
