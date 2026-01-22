from __future__ import annotations

import os
import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _power_helper() -> str:
    return os.environ.get("KEYRGB_POWER_HELPER", "/usr/local/bin/keyrgb-power-helper")


def helper_supports_led_apply() -> bool:
    helper = _power_helper()
    if not Path(helper).exists():
        return False
    try:
        cp = subprocess.run([helper, "--help"], check=False, capture_output=True, text=True)
        out = (cp.stdout or "") + "\n" + (cp.stderr or "")
        return "led-apply" in out
    except Exception:
        return False


def run_led_apply(*, led: str, brightness: int, rgb: tuple[int, int, int] | None) -> bool:
    helper = _power_helper()
    argv: list[str] = [helper, "led-apply", str(led), "--brightness", str(int(brightness))]
    if rgb is not None:
        r, g, b = rgb
        argv += ["--rgb", str(int(r)), str(int(g)), str(int(b))]

    if os.geteuid() == 0:
        cp = subprocess.run(argv, check=False, capture_output=True, text=True)
        return cp.returncode == 0

    pkexec = shutil.which("pkexec")
    if pkexec:
        cp = subprocess.run([pkexec, *argv], check=False, capture_output=True, text=True)
        return cp.returncode == 0

    sudo = shutil.which("sudo")
    if sudo:
        cp = subprocess.run([sudo, *argv], check=False, capture_output=True, text=True)
        return cp.returncode == 0

    return False


def power_helper_path() -> str:
    return _power_helper()
