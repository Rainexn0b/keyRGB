from __future__ import annotations

import subprocess
from typing import Optional


_TCCD_BUS_NAME = "com.tuxedocomputers.tccd"
_TCCD_OBJECT_PATH = "/com/tuxedocomputers/tccd"
_TCCD_INTERFACE = "com.tuxedocomputers.tccd"


def _busctl_call(*args: str) -> Optional[str]:
    """Call busctl and return stdout on success.

    Uses system bus because TCC daemon is system service.
    """

    cmd = [
        "busctl",
        "--system",
        "call",
        _TCCD_BUS_NAME,
        _TCCD_OBJECT_PATH,
        _TCCD_INTERFACE,
        *args,
    ]

    try:
        cp = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        return None

    if cp.returncode != 0:
        return None

    return cp.stdout.strip()


def _parse_busctl_string_reply(stdout: str) -> Optional[str]:
    """Parse busctl output for methods that return a single string.

    Example output: `s "{...}"`
    """

    if not stdout:
        return None

    # busctl formats as: <type> <value>
    # for strings: s "..."
    parts = stdout.split(" ", 1)
    if len(parts) != 2:
        return None

    sig, rest = parts
    if sig != "s":
        return None

    rest = rest.strip()
    if rest.startswith('"') and rest.endswith('"') and len(rest) >= 2:
        rest = rest[1:-1]

    # busctl keeps C-style escapes; json.loads handles standard escapes.
    try:
        return bytes(rest, "utf-8").decode("unicode_escape")
    except Exception:
        return rest


def _parse_busctl_bool_reply(stdout: str) -> Optional[bool]:
    if not stdout:
        return None
    parts = stdout.split(" ", 1)
    if len(parts) != 2:
        return None
    sig, rest = parts
    if sig != "b":
        return None
    rest = rest.strip().lower()
    if rest in ("true", "1"):
        return True
    if rest in ("false", "0"):
        return False
    return None
