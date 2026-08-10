from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE_LAUNCHER = ROOT / "keyrgb"


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _copy_source_launcher(tmp_path: Path) -> Path:
    launcher = tmp_path / "source" / "keyrgb"
    launcher.parent.mkdir()
    shutil.copy2(SOURCE_LAUNCHER, launcher)
    return launcher


def test_source_launcher_uses_installed_runtime_when_local_python_lacks_gi(tmp_path: Path) -> None:
    launcher = _copy_source_launcher(tmp_path)
    marker = tmp_path / "runtime.txt"
    pythonpath_marker = tmp_path / "pythonpath.txt"

    _write_executable(
        launcher.parent / ".venv" / "bin" / "python",
        '#!/bin/sh\nif [ "$1" = "-c" ]; then exit 1; fi\nprintf "local-python\\n" > "$KEYRGB_TEST_MARKER"\n',
    )
    local_console_script = launcher.parent / ".venv" / "bin" / "keyrgb"
    _write_executable(
        local_console_script,
        '#!/bin/sh\nprintf "wrong-local-console-script\\n" > "$KEYRGB_TEST_MARKER"\n',
    )
    external_runtime = tmp_path / "bin" / "keyrgb"
    _write_executable(
        external_runtime,
        "#!/bin/sh\n"
        'printf "installed-runtime:%s\\n" "$*" > "$KEYRGB_TEST_MARKER"\n'
        'printf "%s\\n" "$PYTHONPATH" > "$KEYRGB_TEST_PYTHONPATH_MARKER"\n',
    )

    env = dict(os.environ)
    env.update(
        {
            "KEYRGB_TEST_MARKER": str(marker),
            "KEYRGB_TEST_PYTHONPATH_MARKER": str(pythonpath_marker),
            "PATH": f"{local_console_script.parent}:{external_runtime.parent}:/usr/bin:/bin",
        }
    )
    result = subprocess.run(
        [str(launcher), "--probe"],
        cwd=tmp_path,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert marker.read_text(encoding="utf-8") == "installed-runtime:--probe\n"
    assert str(launcher.parent) in pythonpath_marker.read_text(encoding="utf-8").strip().split(os.pathsep)
    assert "using installed desktop runtime" in result.stderr


def test_source_launcher_keeps_local_python_when_gi_is_available(tmp_path: Path) -> None:
    launcher = _copy_source_launcher(tmp_path)
    marker = tmp_path / "runtime.txt"
    local_python = launcher.parent / ".venv" / "bin" / "python"
    _write_executable(
        local_python,
        '#!/bin/sh\nif [ "$1" = "-c" ]; then exit 0; fi\nprintf "%s\\n" "$*" > "$KEYRGB_TEST_MARKER"\n',
    )

    env = dict(os.environ)
    env.update(
        {
            "KEYRGB_TEST_MARKER": str(marker),
            "PATH": "/usr/bin:/bin",
        }
    )
    result = subprocess.run(
        [str(launcher), "--probe"],
        cwd=tmp_path,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert marker.read_text(encoding="utf-8") == "-B -m src.tray --probe\n"
    assert result.stderr == ""
