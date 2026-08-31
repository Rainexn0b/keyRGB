from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_USER_INTEGRATION = _REPO_ROOT / "scripts" / "lib" / "user_integration.sh"
_COMMON_CORE = _REPO_ROOT / "scripts" / "lib" / "common_core.sh"


def test_install_icon_and_desktop_entries_writes_isolated_session_files(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    launcher = tmp_path / "bin" / "keyrgb"
    launcher.parent.mkdir()
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    launcher.chmod(0o755)

    script = textwrap.dedent(
        f"""
        set -euo pipefail
        source "{_COMMON_CORE}"
        source "{_USER_INTEGRATION}"
        install_icon_and_desktop_entries "{launcher}" "local"
        """
    )
    completed = subprocess.run(
        ["bash", "-c", script],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=_REPO_ROOT,
        env={
            **os.environ,
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
        },
    )
    if completed.returncode != 0:
        pytest.fail(f"desktop integration sandbox failed:\n{completed.stdout}")

    desktop = home / ".local" / "share" / "applications" / "keyrgb.desktop"
    autostart = home / ".config" / "autostart" / "keyrgb.desktop"
    assert desktop.is_file()
    assert autostart.is_file()
    desktop_text = desktop.read_text(encoding="utf-8")
    assert "Name=KeyRGB" in desktop_text
    assert f"Exec={launcher}" in desktop_text
    assert "X-KDE-autostart-after=plasma-workspace" in autostart.read_text(encoding="utf-8")

    # The Diagnostic Session desktop action must launch through the same
    # executable and must not alter the normal/autostart Exec lines.
    assert "Actions=DiagnosticSession;" in desktop_text
    assert "[Desktop Action DiagnosticSession]" in desktop_text
    assert "Name=Diagnostic Session" in desktop_text
    assert f"Exec={launcher} --diagnostic-session" in desktop_text
    assert "Terminal=false" in desktop_text
    action_block = desktop_text.split("[Desktop Action DiagnosticSession]", 1)[1]
    assert "Terminal=" not in action_block
    # Autostart entry must remain a plain normal launch (no diagnostic action).
    autostart_text = autostart.read_text(encoding="utf-8")
    assert f"Exec={launcher}" in autostart_text
    assert "DiagnosticSession" not in autostart_text
