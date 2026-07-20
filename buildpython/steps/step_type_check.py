from __future__ import annotations

from ..utils.paths import repo_root
from ..utils.subproc import RunResult, python_exe, run


_GUI_PURE_MYPY_TARGETS = (
    "src/gui/perkey/ops/color_map_ops.py",
    "src/gui/perkey/ops/color_apply_ops.py",
    "src/gui/perkey/color_utils.py",
    "src/gui/perkey/editor_support/dirty_state.py",
    "src/gui/reference/overlay_geometry.py",
    "src/gui/settings/_settings_scheduler.py",
    "src/gui/utils/key_draw_style.py",
    "src/gui/windows/_support/_support_window_geometry.py",
)


def _combine_mypy_results(primary: RunResult, gui_pure: RunResult) -> RunResult:
    return RunResult(
        command_str=f"{primary.command_str} && {gui_pure.command_str}",
        stdout=primary.stdout + gui_pure.stdout,
        stderr=primary.stderr + gui_pure.stderr,
        exit_code=primary.exit_code or gui_pure.exit_code,
    )


def mypy_runner() -> RunResult:
    root = repo_root()

    # Use pyproject.toml configuration if present.
    # Keep the established runtime scope, then check a deliberately narrow
    # non-Tk GUI baseline without following imports into Tk-heavy surfaces.
    primary = run(
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
    gui_pure = run(
        [
            python_exe(),
            "-m",
            "mypy",
            "--follow-imports=skip",
            *_GUI_PURE_MYPY_TARGETS,
        ],
        cwd=str(root),
        env_overrides={"KEYRGB_HW_TESTS": "0"},
    )
    return _combine_mypy_results(primary, gui_pure)
