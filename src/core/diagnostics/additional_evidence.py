from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any


def _primary_candidate(discovery: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(discovery, dict):
        return None
    candidates = discovery.get("candidates")
    if not isinstance(candidates, list):
        return None
    for preferred_status in ("unrecognized_ite", "known_dormant", "known_unavailable", "experimental_disabled"):
        for candidate in candidates:
            if isinstance(candidate, dict) and str(candidate.get("status") or "") == preferred_status:
                return candidate
    return None


def _candidate_usb_id(candidate: dict[str, Any] | None) -> str:
    if not isinstance(candidate, dict):
        return ""
    usb_vid = str(candidate.get("usb_vid") or "").strip().lower().removeprefix("0x")
    usb_pid = str(candidate.get("usb_pid") or "").strip().lower().removeprefix("0x")
    if not usb_vid or not usb_pid:
        return ""
    return f"{usb_vid}:{usb_pid}"


def build_additional_evidence_plan(discovery: dict[str, Any] | None) -> dict[str, Any]:
    candidate = _primary_candidate(discovery)
    usb_id = _candidate_usb_id(candidate)
    if not usb_id:
        return {
            "usb_id": "",
            "candidate_status": "",
            "automated": [],
            "manual": [],
        }

    automated = [
        {
            "key": "lsusb_verbose",
            "label": "Full USB descriptor",
            "command": ["lsusb", "-v", "-d", usb_id],
            "requires_root": False,
        }
    ]

    descriptor_sizes = candidate.get("hidraw_descriptor_sizes") if isinstance(candidate, dict) else None
    if not isinstance(descriptor_sizes, list) or not descriptor_sizes:
        automated.append(
            {
                "key": "hid_descriptor_dump",
                "label": "HID report descriptor dump",
                "command": ["usbhid-dump", "-d", usb_id, "-e", "descriptor"],
                "requires_root": True,
            }
        )

    manual = [
        {
            "key": "windows_capture",
            "label": "Windows OEM traffic capture",
            "required": True,
        },
        {
            "key": "physical_confirmation",
            "label": "Physical zone and LED confirmation",
            "required": True,
        },
    ]

    return {
        "usb_id": usb_id,
        "candidate_status": str(candidate.get("status") or "") if isinstance(candidate, dict) else "",
        "automated": automated,
        "manual": manual,
    }


def _run_command(argv: list[str], *, requires_root: bool) -> dict[str, Any]:
    if not argv:
        return {"ok": False, "error": "empty command", "command": []}

    exe = str(argv[0])
    resolved = shutil.which(exe)
    if not resolved:
        return {
            "ok": False,
            "available": False,
            "error": f"{exe} not found",
            "command": list(argv),
            "requires_root": requires_root,
        }

    run_argv = list(argv)
    via = "direct"
    if requires_root and os.geteuid() != 0:
        pkexec = shutil.which("pkexec")
        sudo = shutil.which("sudo")
        if pkexec:
            run_argv = [pkexec, *argv]
            via = "pkexec"
        elif sudo:
            run_argv = [sudo, *argv]
            via = "sudo"
        else:
            return {
                "ok": False,
                "available": True,
                "error": "Need root privileges but neither pkexec nor sudo was found",
                "command": list(argv),
                "requires_root": True,
            }

    try:
        cp = subprocess.run(run_argv, check=False, capture_output=True, text=True)
    except Exception as exc:
        return {
            "ok": False,
            "available": True,
            "error": str(exc),
            "command": list(argv),
            "requires_root": requires_root,
            "via": via,
        }

    return {
        "ok": cp.returncode == 0,
        "available": True,
        "command": list(argv),
        "requires_root": requires_root,
        "via": via,
        "returncode": int(cp.returncode),
        "stdout": str(cp.stdout or ""),
        "stderr": str(cp.stderr or ""),
    }


def collect_additional_evidence(discovery: dict[str, Any] | None, *, allow_privileged: bool) -> dict[str, Any]:
    plan = build_additional_evidence_plan(discovery)
    captures: dict[str, Any] = {}
    for item in plan.get("automated") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "")
        command = item.get("command")
        requires_root = bool(item.get("requires_root"))
        if not key or not isinstance(command, list):
            continue
        if requires_root and not allow_privileged:
            captures[key] = {
                "ok": False,
                "available": True,
                "command": list(command),
                "requires_root": True,
                "error": "privileged capture not approved",
            }
            continue
        captures[key] = _run_command([str(part) for part in command], requires_root=requires_root)

    return {
        "usb_id": plan.get("usb_id") or "",
        "candidate_status": plan.get("candidate_status") or "",
        "captures": captures,
        "manual": list(plan.get("manual") or []),
    }