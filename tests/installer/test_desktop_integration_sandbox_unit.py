from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_USER_INTEGRATION = _REPO_ROOT / "scripts" / "lib" / "user_integration.sh"
_COMMON_CORE = _REPO_ROOT / "scripts" / "lib" / "common_core.sh"
_MATCH_LIB = _REPO_ROOT / "scripts" / "lib" / "uninstall_match.sh"
_INSTALL_USER = _REPO_ROOT / "scripts" / "install_user.sh"
_UNINSTALL = _REPO_ROOT / "scripts" / "uninstall.sh"


def _run_bash(script: str, *, home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
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


def test_diagnostics_shim_install_writes_owned_forwarding_shim(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".local" / "bin").mkdir(parents=True)
    launcher = home / ".local" / "bin" / "keyrgb"
    launcher.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    launcher.chmod(0o755)
    shim = home / ".local" / "bin" / "keyrgb-diagnostics"

    script = textwrap.dedent(
        f"""
        set -euo pipefail
        source "{_COMMON_CORE}"
        source "{_MATCH_LIB}"
        source "{_USER_INTEGRATION}"
        install_appimage_diagnostics_shim "{shim}" "{launcher}"
        """
    )
    completed = _run_bash(script, home=home)
    assert completed.returncode == 0, completed.stdout

    assert shim.is_file()
    assert os.access(shim, os.X_OK)
    text = shim.read_text(encoding="utf-8")
    assert "KeyRGB AppImage diagnostics shim" in text
    assert f'KEYRGB_LAUNCHER="{launcher}"' in text
    assert 'exec "$KEYRGB_LAUNCHER" --diagnostics "$@"' in text


def test_diagnostics_shim_forwards_diagnostics_and_user_args(tmp_path: Path) -> None:
    home = tmp_path / "home"
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    launcher = bin_dir / "keyrgb"
    probe = tmp_path / "launcher-args.txt"
    launcher.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            printf '%s\\n' "$@" > "{probe}"
            """
        ),
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    shim = bin_dir / "keyrgb-diagnostics"

    install_script = textwrap.dedent(
        f"""
        set -euo pipefail
        source "{_COMMON_CORE}"
        source "{_MATCH_LIB}"
        source "{_USER_INTEGRATION}"
        install_appimage_diagnostics_shim "{shim}" "{launcher}"
        """
    )
    installed = _run_bash(install_script, home=home)
    assert installed.returncode == 0, installed.stdout

    forwarded = subprocess.run(
        ["bash", str(shim), "--text", "--no-usb"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={**os.environ, "HOME": str(home)},
    )
    assert forwarded.returncode == 0, forwarded.stdout
    assert probe.is_file()
    assert probe.read_text(encoding="utf-8").splitlines() == [
        "--diagnostics",
        "--text",
        "--no-usb",
    ]


def test_diagnostics_shim_does_not_replace_foreign_command(tmp_path: Path) -> None:
    home = tmp_path / "home"
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    launcher = bin_dir / "keyrgb"
    launcher.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    launcher.chmod(0o755)
    shim = bin_dir / "keyrgb-diagnostics"
    foreign_contents = "#!/usr/bin/env python3\n# pip console script\n"
    shim.write_text(foreign_contents, encoding="utf-8")

    script = textwrap.dedent(
        f"""
        set -euo pipefail
        source "{_COMMON_CORE}"
        source "{_MATCH_LIB}"
        source "{_USER_INTEGRATION}"
        install_appimage_diagnostics_shim "{shim}" "{launcher}"
        """
    )
    completed = _run_bash(script, home=home)

    assert completed.returncode == 0, completed.stdout
    assert "Not replacing existing non-AppImage command" in completed.stdout
    assert shim.read_text(encoding="utf-8") == foreign_contents


def test_diagnostics_shim_uninstall_is_marker_safe(tmp_path: Path) -> None:
    owned = tmp_path / "owned-shim"
    owned.write_text(
        '#!/usr/bin/env bash\n# KeyRGB AppImage diagnostics shim.\nexec keyrgb --diagnostics "$@"\n',
        encoding="utf-8",
    )
    foreign = tmp_path / "foreign-shim"
    foreign.write_text(
        '#!/usr/bin/env bash\n# pip-installed keyrgb-diagnostics entrypoint\nexec python -m keyrgb "$@"\n',
        encoding="utf-8",
    )

    script = textwrap.dedent(
        f"""
        set -euo pipefail
        source "{_MATCH_LIB}"
        is_keyrgb_managed_diagnostics_shim "{owned}"
        if is_keyrgb_managed_diagnostics_shim "{foreign}"; then
          echo "foreign shim incorrectly managed" >&2
          exit 2
        fi
        if should_remove_managed_file "{owned}" "{tmp_path}/missing-src" is_keyrgb_managed_diagnostics_shim; then
          rm -f "{owned}"
        else
          echo "owned shim not removable" >&2
          exit 3
        fi
        if should_remove_managed_file "{foreign}" "{tmp_path}/missing-src" is_keyrgb_managed_diagnostics_shim; then
          echo "foreign shim incorrectly removable" >&2
          exit 4
        fi
        echo ok
        """
    )
    completed = subprocess.run(
        ["bash", "-c", script],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=_REPO_ROOT,
    )
    assert completed.returncode == 0, completed.stdout
    assert "ok" in completed.stdout
    assert not owned.exists()
    assert foreign.is_file()


def test_install_user_refreshes_diagnostics_shim_alongside_launcher() -> None:
    text = _INSTALL_USER.read_text(encoding="utf-8")
    launcher_call = 'install_appimage_launcher "$LAUNCHER_DST" "$APPIMAGE_DST"'
    shim_call = 'install_appimage_diagnostics_shim "$DIAGNOSTICS_SHIM_DST" "$LAUNCHER_DST"'
    assert launcher_call in text
    assert shim_call in text
    # Refresh on updates: both calls must live on the shared install path, not
    # inside the first-install-only privileged-helper block.
    assert text.index(launcher_call) < text.index(shim_call)
    assert 'DIAGNOSTICS_SHIM_DST="$HOME/.local/bin/keyrgb-diagnostics"' in text


def test_uninstall_removes_shim_only_when_appimage_owned() -> None:
    text = _UNINSTALL.read_text(encoding="utf-8")
    assert "is_keyrgb_managed_diagnostics_shim" in text
    assert 'DIAGNOSTICS_SHIM="$HOME/.local/bin/keyrgb-diagnostics"' in text
    # Guarded removal: the rm must be conditional on the ownership check so
    # pip/user-provided files without the marker are never deleted.
    marker_guard = text.index('if is_keyrgb_managed_diagnostics_shim "$DIAGNOSTICS_SHIM"')
    shim_rm = text.index('rm -f "$DIAGNOSTICS_SHIM"')
    assert marker_guard < shim_rm
