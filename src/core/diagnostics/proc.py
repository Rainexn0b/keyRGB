from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .io import read_text


def proc_open_holders(target_path: Path, *, limit: int = 10, pid_limit: int = 5000) -> list[dict[str, Any]]:
    """Best-effort scan of /proc/*/fd to find processes holding a file open.

    This is useful for diagnosing "device detected but can't control" issues
    caused by other software holding the USB device node.
    """

    proc_root = Path("/proc")
    holders: list[dict[str, Any]] = []

    try:
        target_str = str(target_path)
        target_real = str(target_path.resolve()) if target_path.exists() else target_str

        if not proc_root.exists():
            return []

        checked = 0
        for child in proc_root.iterdir():
            if len(holders) >= limit or checked >= pid_limit:
                break

            if not child.is_dir() or not child.name.isdigit():
                continue
            checked += 1

            pid = int(child.name)
            fd_dir = child / "fd"
            if not fd_dir.exists():
                continue

            matched = False
            try:
                for fd in fd_dir.iterdir():
                    try:
                        link = os.readlink(fd)
                    except Exception:
                        continue
                    if link == target_str or link == target_real:
                        matched = True
                        break
            except PermissionError:
                continue
            except Exception:
                continue

            if not matched:
                continue

            info: dict[str, Any] = {"pid": pid, "is_self": (pid == os.getpid())}
            comm = read_text(child / "comm")
            if comm:
                info["comm"] = comm
            try:
                exe = child / "exe"
                if exe.exists():
                    info["exe"] = str(exe.resolve())
            except Exception:
                pass

            # Best-effort command line (may be empty for kernel threads).
            try:
                cmdline_path = child / "cmdline"
                if cmdline_path.exists():
                    raw = cmdline_path.read_bytes()
                    # NUL-separated argv.
                    parts = [p.decode("utf-8", errors="ignore") for p in raw.split(b"\x00") if p]
                    if parts:
                        # Keep it short to avoid overly verbose diagnostics.
                        joined = " ".join(parts)
                        info["cmdline"] = joined[:300]
            except Exception:
                pass

            holders.append(info)

        return holders
    except Exception:
        return holders
