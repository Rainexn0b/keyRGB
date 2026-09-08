from __future__ import annotations

from pathlib import Path

from ..core.model import Step
from ..utils.paths import buildlog_dir, repo_root
from ..utils.subproc import python_exe, run

# Installed privileged helper: extensionless Python that must stay covered by
# every file-based quality gate. Kept as an explicit literal (not derived) so
# drift is greppable and unit tests can assert exact gate membership.
POWER_HELPER_PATH = "system/bin/keyrgb-power-helper"


def _log(name: str) -> Path:
    return buildlog_dir() / name


def steps() -> list[Step]:
    root = repo_root()

    def compileall_runner():
        compile_result = run(
            [python_exe(), "-m", "compileall", "-q", "keyrgb"],
            cwd=str(root),
            env_overrides={"KEYRGB_HW_TESTS": "0"},
        )
        if compile_result.exit_code != 0:
            return compile_result
        # compileall silently skips extensionless files, so byte-compile the
        # installed helper explicitly; syntax errors here must fail Compile.
        return run(
            [python_exe(), "-m", "py_compile", POWER_HELPER_PATH],
            cwd=str(root),
            env_overrides={"KEYRGB_HW_TESTS": "0"},
        )

    def pytest_runner():
        return pytest_runner_with_optional_coverage()

    def ruff_runner():
        return run(
            [
                python_exe(),
                "-m",
                "ruff",
                "check",
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

    from .appimage.build import appimage_build_runner
    from .appimage.smoke import appimage_smoke_runner
    from .code_hygiene.step import code_hygiene_runner
    from .coverage_step.step import coverage_runner, pytest_runner_with_optional_coverage
    from .exception_transparency.step import exception_transparency_runner
    from .file_size_analysis.step import file_size_runner
    from .step_architecture_validation import architecture_validation_runner
    from .step_black import black_check_runner
    from .step_dead_code import dead_code_runner
    from .step_format import ruff_format_check_runner
    from .step_import_scan import import_scan_runner
    from .step_imports import import_validation_runner
    from .step_loc_check import loc_check_runner
    from .step_pip import pip_check_runner
    from .step_quality import code_markers_runner
    from .step_repo_validation import repo_validation_runner
    from .step_shellcheck import shellcheck_runner
    from .step_type_check import mypy_runner

    return [
        Step(
            number=1,
            name="Compile",
            description="Compile keyrgb application sources (syntax check)",
            log_file=_log("step-01-compile.log"),
            runner=compileall_runner,
        ),
        Step(
            number=2,
            name="Pytest",
            description="Run tests with hardware tests disabled (KEYRGB_HW_TESTS=0)",
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
            description="Parse sources and probe external top-level imports",
            log_file=_log("step-09-import-scan.log"),
            runner=import_scan_runner,
        ),
        Step(
            number=10,
            name="Repo Validation",
            description="Validate repo packaging/install/metadata consistency",
            log_file=_log("step-10-repo-validation.log"),
            runner=repo_validation_runner,
        ),
        Step(
            number=11,
            name="Black",
            description="Check formatting with black (optional)",
            log_file=_log("step-11-black.log"),
            runner=black_check_runner,
        ),
        Step(
            number=12,
            name="LOC Check",
            description="Report large Python files by LOC buckets (tests use relaxed thresholds)",
            log_file=_log("step-12-loc-check.log"),
            runner=loc_check_runner,
        ),
        Step(
            number=13,
            name="Type Check",
            description="Type-check core, tray, GUI, buildpython, release/audit scripts, and buildpython tests",
            log_file=_log("step-13-type-check.log"),
            runner=mypy_runner,
        ),
        Step(
            number=14,
            name="AppImage",
            description="Build keyrgb-x86_64.AppImage",
            log_file=_log("step-14-appimage.log"),
            runner=appimage_build_runner,
        ),
        Step(
            number=15,
            name="AppImage Smoke",
            description="Smoke-test AppImage in minimal container (no system deps)",
            log_file=_log("step-15-appimage-smoke.log"),
            runner=appimage_smoke_runner,
        ),
        Step(
            number=16,
            name="Code Hygiene",
            description="Check defensive patterns, type discipline, test naming",
            log_file=_log("step-16-code-hygiene.log"),
            runner=code_hygiene_runner,
        ),
        Step(
            number=17,
            name="Architecture Validation",
            description="Validate architecture boundaries, write ownership, and lexical locks",
            log_file=_log("step-17-architecture.log"),
            runner=architecture_validation_runner,
        ),
        Step(
            number=18,
            name="Coverage",
            description="Build coverage debt summary and track coverage regressions",
            log_file=_log("step-18-coverage.log"),
            runner=coverage_runner,
        ),
        Step(
            number=19,
            name="Exception Transparency",
            description="Track broad exception debt and silent-failure hotspots",
            log_file=_log("step-19-exception-transparency.log"),
            runner=exception_transparency_runner,
        ),
        Step(
            number=20,
            name="Dead Code",
            description="Fail on unused functions/classes/imports in runtime code",
            log_file=_log("step-20-dead-code.log"),
            runner=dead_code_runner,
        ),
        Step(
            number=21,
            name="ShellCheck",
            description="Lint installer and helper shell scripts",
            log_file=_log("step-21-shellcheck.log"),
            runner=shellcheck_runner,
        ),
    ]
