from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_READ_TEXT_ERRORS = (OSError, UnicodeError)
_RUN_COMMAND_ERRORS = (OSError, TypeError, ValueError, subprocess.SubprocessError)
_READ_KV_FILE_ERRORS = (OSError,)
_PARSE_HEX_INT_ERRORS = (AttributeError, TypeError, ValueError)


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except _READ_TEXT_ERRORS:
        return None


def run_command(argv: list[str], *, timeout_s: float = 1.5) -> str | None:
    """Run a small diagnostic command in a best-effort, read-only way."""

    if not argv:
        return None

    exe = argv[0]
    if not shutil.which(exe):
        return None

    try:
        proc = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        out = (proc.stdout or "").strip()
        return out if out else None
    except _RUN_COMMAND_ERRORS:
        return None


def read_kv_file(path: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE files like /etc/os-release."""

    data: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip().strip('"')
            data[k.strip()] = v
    except _READ_KV_FILE_ERRORS:
        return {}
    return data


def parse_hex_int(text: str) -> int | None:
    try:
        s = text.strip().lower()
        s = s.removeprefix("0x")
        return int(s, 16)
    except _PARSE_HEX_INT_ERRORS:
        return None
