from __future__ import annotations

from pathlib import Path

from keyrgb.gui import calibrator
from keyrgb.gui.calibrator import launch as calibrator_launch
from keyrgb.gui.calibrator.app import main as app_main


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

    launch_calls: list[dict[str, object]] = []

    def _fake_launch_module_subprocess(module_name: str, **kwargs):
        launch_calls.append({"module_name": module_name, **kwargs})

    monkeypatch.setattr(calibrator_launch, "__file__", str(anchor))
    monkeypatch.setattr(calibrator_launch, "launch_module_subprocess", _fake_launch_module_subprocess)

    calibrator_launch.launch_keymap_calibrator()

    assert launch_calls == [
        {
            "module_name": "keyrgb.gui.calibrator",
            "anchor": str(anchor),
            "no_bytecode": False,
        }
    ]
