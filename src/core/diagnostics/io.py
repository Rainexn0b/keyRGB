from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional


def read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def run_command(argv: list[str], *, timeout_s: float = 1.5) -> Optional[str]:
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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
        )
        out = (proc.stdout or "").strip()
        return out if out else None
    except Exception:
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
    except Exception:
        return {}
    return data


def parse_hex_int(text: str) -> Optional[int]:
    try:
        s = text.strip().lower()
        if s.startswith("0x"):
            s = s[2:]
        return int(s, 16)
    except Exception:
        return None
