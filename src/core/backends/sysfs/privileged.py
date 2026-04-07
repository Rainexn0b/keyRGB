from __future__ import annotations

import os
import logging
import re
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_LED_NAME_RE = re.compile(r"^[A-Za-z0-9:_\-.]+$")
_HELPER_COLOR_KINDS = frozenset({"brightness", "multi_intensity", "color"})


def _power_helper() -> str:
    return os.environ.get("KEYRGB_POWER_HELPER", "/usr/local/bin/keyrgb-power-helper")


def helper_can_apply_led(led: str, *, color_kind: str = "brightness") -> bool:
    name = (led or "").strip()
    if not name or "/" in name or "\\" in name:
        return False
    if not _LED_NAME_RE.fullmatch(name):
        return False
    if "kbd_backlight" not in name.lower():
        return False

    kind = (color_kind or "brightness").strip().lower()
    return kind in _HELPER_COLOR_KINDS


def helper_supports_led_apply() -> bool:
    helper = _power_helper()
    if not Path(helper).exists():
        return False
    try:
        cp = subprocess.run([helper, "--help"], check=False, capture_output=True, text=True)
        out = (cp.stdout or "") + "\n" + (cp.stderr or "")
        return "led-apply" in out
    except OSError:
        return False


def run_led_apply(*, led: str, brightness: int, rgb: tuple[int, int, int] | None) -> bool:
    helper = _power_helper()
    argv: list[str] = [helper, "led-apply", str(led), "--brightness", str(int(brightness))]
    if rgb is not None:
        r, g, b = rgb
        argv += ["--rgb", str(int(r)), str(int(g)), str(int(b))]

    def _log(cp: subprocess.CompletedProcess[str], *, via: str) -> None:
        if not os.environ.get("KEYRGB_DEBUG"):
            return
        try:
            stderr = (cp.stderr or "").strip().replace("\n", " | ")
            if len(stderr) > 400:
                stderr = stderr[:400] + "..."
            stdout = (cp.stdout or "").strip().replace("\n", " | ")
            if len(stdout) > 200:
                stdout = stdout[:200] + "..."
            logger.info(
                "backend.sysfs.helper led-apply via=%s rc=%s stdout=%s stderr=%s",
                via,
                cp.returncode,
                stdout,
                stderr,
            )
        except Exception:  # @quality-exception exception-transparency: debug logging is a best-effort diagnostic boundary; broken logger/format handlers must not block hardware writes
            pass

    if os.geteuid() == 0:
        cp = subprocess.run(argv, check=False, capture_output=True, text=True)
        _log(cp, via="root")
        return cp.returncode == 0

    pkexec = shutil.which("pkexec")
    if pkexec:
        cp = subprocess.run([pkexec, *argv], check=False, capture_output=True, text=True)
        _log(cp, via="pkexec")
        return cp.returncode == 0

    sudo = shutil.which("sudo")
    if sudo:
        cp = subprocess.run([sudo, *argv], check=False, capture_output=True, text=True)
        _log(cp, via="sudo")
        return cp.returncode == 0

    return False


def power_helper_path() -> str:
    return _power_helper()
