from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _expected_holder_pids() -> set[int]:
    expected: set[int] = set()

    try:
        tray_pid = os.environ.get("KEYRGB_TRAY_PID")
        if tray_pid:
            expected.add(int(tray_pid))
    except Exception:
        expected = set()

    # Fallback: if the tray didn't set KEYRGB_TRAY_PID (older build)
    # and Settings was launched as a subprocess, the parent PID is
    # typically the tray. Treat parent 'keyrgb' as expected.
    try:
        if not expected:
            ppid = int(os.getppid())
            comm_path = Path(f"/proc/{ppid}/comm")
            if comm_path.exists():
                parent_comm = comm_path.read_text(encoding="utf-8", errors="ignore").strip()
                if parent_comm == "keyrgb":
                    expected.add(ppid)
    except Exception:
        pass

    return expected


def _device_busy_warnings(payload: dict[str, Any], *, expected_holder_pids: set[int]) -> list[str]:
    warnings: list[str] = []

    try:
        usb_devices = payload.get("usb_devices")
        if not isinstance(usb_devices, list):
            return []

        for dev in usb_devices:
            if not isinstance(dev, dict):
                continue

            others = dev.get("devnode_open_by_others")
            if not isinstance(others, list) or not others:
                continue

            if expected_holder_pids:
                filtered: list[dict[str, object]] = []
                for h in others:
                    if not isinstance(h, dict):
                        continue
                    pid = h.get("pid")
                    try:
                        if pid is not None and int(pid) in expected_holder_pids:
                            continue
                    except Exception:
                        pass
                    filtered.append(h)
                others = filtered

            if not others:
                continue

            devnode = dev.get("devnode") or dev.get("sysfs_path") or "(unknown)"
            summaries: list[str] = []
            for h in others:
                if not isinstance(h, dict):
                    continue
                pid = h.get("pid")
                comm = h.get("comm")
                exe = h.get("exe")
                parts: list[str] = []
                if pid is not None:
                    parts.append(f"pid={pid}")
                if comm:
                    parts.append(f"comm={comm}")
                if exe:
                    parts.append(f"exe={exe}")
                if parts:
                    summaries.append(" ".join(parts))

            if summaries:
                warnings.append(f"Device busy: {devnode} is open by other process(es): " + "; ".join(summaries))
            else:
                warnings.append(f"Device busy: {devnode} is open by other process(es)")

        return warnings
    except Exception:
        return warnings


def collect_diagnostics_text(*, include_usb: bool = True) -> str:
    try:
        from src.core.diagnostics import collect_diagnostics
    except Exception:
        # Allow execution when run outside installed env.
        import sys

        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from src.core.diagnostics import collect_diagnostics

    diag = collect_diagnostics(include_usb=include_usb)
    payload = diag.to_dict()

    warnings = _device_busy_warnings(payload, expected_holder_pids=_expected_holder_pids())
    if warnings:
        payload["warnings"] = warnings

    return json.dumps(payload, indent=2, sort_keys=True)
