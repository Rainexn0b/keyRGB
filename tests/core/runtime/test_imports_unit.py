from __future__ import annotations

from pathlib import Path

from src.core.runtime.imports import repo_root_from


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
