from __future__ import annotations

import os
import shutil
import subprocess

from .models import TccProfileWriteError


_DEFAULT_TCCD_BIN = "/opt/tuxedo-control-center/resources/dist/tuxedo-control-center/data/service/tccd"


def _tccd_binary() -> str:
    return os.environ.get("KEYRGB_TCCD_BIN", _DEFAULT_TCCD_BIN)


def _run_root_command(argv: list[str]) -> subprocess.CompletedProcess[str]:
    if os.geteuid() == 0:
        return subprocess.run(argv, check=False, capture_output=True, text=True)

    pkexec = shutil.which("pkexec")
    if pkexec:
        return subprocess.run([pkexec, *argv], check=False, capture_output=True, text=True)

    sudo = shutil.which("sudo")
    if sudo:
        # Will prompt in terminal if needed.
        return subprocess.run([sudo, *argv], check=False, capture_output=True, text=True)

    raise TccProfileWriteError("Need root privileges to write TCC profiles/settings (pkexec or sudo not found)")


def _apply_new_profiles_file(path: str) -> None:
    tccd = _tccd_binary()
    if not os.path.exists(tccd):
        raise TccProfileWriteError(f"tccd binary not found at {tccd}")

    cp = _run_root_command([tccd, "--new_profiles", path])
    if cp.returncode != 0:
        msg = (cp.stderr or cp.stdout or "").strip()
        raise TccProfileWriteError(f"tccd --new_profiles failed: {msg or 'unknown error'}")


def _apply_new_settings_file(path: str) -> None:
    tccd = _tccd_binary()
    if not os.path.exists(tccd):
        raise TccProfileWriteError(f"tccd binary not found at {tccd}")

    cp = _run_root_command([tccd, "--new_settings", path])
    if cp.returncode != 0:
        msg = (cp.stderr or cp.stdout or "").strip()
        raise TccProfileWriteError(f"tccd --new_settings failed: {msg or 'unknown error'}")
