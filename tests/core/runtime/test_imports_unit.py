from __future__ import annotations

import sys
from pathlib import Path

from keyrgb.core.runtime.imports import (
    launch_module_subprocess,
    launcher_cwd_from,
    launcher_python_argv,
    repo_root_from,
)


def test_repo_root_from_prefers_checkout_root_with_pyproject_and_package(tmp_path: Path) -> None:
    repo_root = tmp_path / "checkout"
    anchor = repo_root / "keyrgb" / "tray" / "ui" / "gui_launch.py"
    anchor.parent.mkdir(parents=True)
    anchor.touch()
    (repo_root / "keyrgb").mkdir(exist_ok=True)
    (repo_root / "pyproject.toml").write_text("[project]\nname = 'keyrgb'\n", encoding="utf-8")

    assert repo_root_from(anchor) == repo_root


def test_repo_root_from_supports_packaged_layout_without_pyproject(tmp_path: Path) -> None:
    runtime_root = tmp_path / "usr" / "lib" / "keyrgb"
    anchor = runtime_root / "keyrgb" / "gui" / "calibrator" / "launch.py"
    anchor.parent.mkdir(parents=True)
    anchor.touch()
    (runtime_root / "keyrgb").mkdir(exist_ok=True)

    assert repo_root_from(anchor) == runtime_root


def test_launcher_cwd_from_returns_existing_repo_root(tmp_path: Path) -> None:
    runtime_root = tmp_path / "usr" / "lib" / "keyrgb"
    anchor = runtime_root / "keyrgb" / "gui" / "calibrator" / "launch.py"
    anchor.parent.mkdir(parents=True)
    anchor.touch()
    (runtime_root / "keyrgb").mkdir(exist_ok=True)

    assert launcher_cwd_from(anchor) == str(runtime_root)


def test_launcher_python_argv_defaults_to_bytecode_disabled() -> None:
    assert launcher_python_argv("keyrgb.gui.perkey") == [sys.executable, "-B", "-m", "keyrgb.gui.perkey"]


def test_launcher_python_argv_can_keep_bytecode_generation() -> None:
    assert launcher_python_argv("keyrgb.gui.calibrator", no_bytecode=False) == [
        sys.executable,
        "-m",
        "keyrgb.gui.calibrator",
    ]


def test_launch_module_subprocess_uses_launcher_root_and_env(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "usr" / "lib" / "keyrgb"
    anchor = runtime_root / "keyrgb" / "tray" / "ui" / "gui_launch.py"
    anchor.parent.mkdir(parents=True)
    anchor.touch()
    (runtime_root / "keyrgb").mkdir(exist_ok=True)

    calls: list[dict[str, object]] = []

    def _fake_popen(args, **kwargs):
        calls.append({"args": list(args), **kwargs})

    import keyrgb.core.runtime.imports as runtime_imports

    monkeypatch.setattr(runtime_imports.subprocess, "Popen", _fake_popen)

    launch_module_subprocess(
        "keyrgb.gui.windows.uniform",
        anchor=anchor,
        env={"KEYRGB_UNIFORM_TARGET_CONTEXT": "keyboard"},
    )

    assert calls == [
        {
            "args": [sys.executable, "-B", "-m", "keyrgb.gui.windows.uniform"],
            "cwd": str(runtime_root),
            "env": {"KEYRGB_UNIFORM_TARGET_CONTEXT": "keyboard"},
        }
    ]
