from __future__ import annotations

from pathlib import Path
import sys

from src.core.runtime.imports import (
    ensure_repo_root_on_sys_path_str,
    launcher_cwd_from,
    repo_root_from,
)


def test_repo_root_from_prefers_checkout_root_with_pyproject_and_src(tmp_path: Path) -> None:
    repo_root = tmp_path / "checkout"
    anchor = repo_root / "src" / "tray" / "ui" / "gui_launch.py"
    anchor.parent.mkdir(parents=True)
    anchor.touch()
    (repo_root / "src").mkdir(exist_ok=True)
    (repo_root / "pyproject.toml").write_text("[project]\nname = 'keyrgb'\n", encoding="utf-8")

    assert repo_root_from(anchor) == repo_root


def test_repo_root_from_supports_packaged_layout_without_pyproject(tmp_path: Path) -> None:
    runtime_root = tmp_path / "usr" / "lib" / "keyrgb"
    anchor = runtime_root / "src" / "gui" / "calibrator" / "launch.py"
    anchor.parent.mkdir(parents=True)
    anchor.touch()
    (runtime_root / "src").mkdir(exist_ok=True)

    assert repo_root_from(anchor) == runtime_root


def test_launcher_cwd_from_returns_existing_repo_root(tmp_path: Path) -> None:
    runtime_root = tmp_path / "usr" / "lib" / "keyrgb"
    anchor = runtime_root / "src" / "gui" / "calibrator" / "launch.py"
    anchor.parent.mkdir(parents=True)
    anchor.touch()
    (runtime_root / "src").mkdir(exist_ok=True)

    assert launcher_cwd_from(anchor) == str(runtime_root)


def test_ensure_repo_root_on_sys_path_str_inserts_once(tmp_path: Path) -> None:
    runtime_root = tmp_path / "usr" / "lib" / "keyrgb"
    anchor = runtime_root / "src" / "tray" / "ui" / "gui_launch.py"
    anchor.parent.mkdir(parents=True)
    anchor.touch()
    (runtime_root / "src").mkdir(exist_ok=True)

    runtime_root_str = str(runtime_root)
    original_path = list(sys.path)
    try:
        sys.path[:] = [entry for entry in sys.path if entry != runtime_root_str]

        assert ensure_repo_root_on_sys_path_str(anchor) == runtime_root_str
        assert sys.path[0] == runtime_root_str

        before = list(sys.path)
        assert ensure_repo_root_on_sys_path_str(anchor) == runtime_root_str
        assert sys.path == before
    finally:
        sys.path[:] = original_path
