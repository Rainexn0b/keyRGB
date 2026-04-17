from __future__ import annotations

from pathlib import Path

import src.gui.calibrator as calibrator
from src.gui.calibrator import launch as calibrator_launch
from src.gui.calibrator.app import main as app_main


def test_calibrator_package_re_exports_main() -> None:
    assert calibrator.main is app_main
    assert "main" in calibrator.__all__


def test_launch_keymap_calibrator_uses_structural_repo_root_for_packaged_layout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "usr" / "lib" / "keyrgb"
    anchor = runtime_root / "src" / "gui" / "calibrator" / "launch.py"
    anchor.parent.mkdir(parents=True)
    anchor.touch()
    (runtime_root / "src").mkdir(exist_ok=True)

    popen_calls: list[dict[str, object]] = []

    def _fake_popen(args, **kwargs):
        popen_calls.append({"args": list(args), **kwargs})
        return None

    monkeypatch.setattr(calibrator_launch, "__file__", str(anchor))
    monkeypatch.setattr(calibrator_launch.subprocess, "Popen", _fake_popen)

    calibrator_launch.launch_keymap_calibrator()

    assert popen_calls == [
        {
            "args": [calibrator_launch.sys.executable, "-m", "src.gui.calibrator"],
            "cwd": str(runtime_root),
        }
    ]
