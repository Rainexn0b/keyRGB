from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from ._collectors_backends_sysfs_support import _ACCESS_ERRORS
from ._collectors_backends_sysfs_support import _EXPECTED_RUNTIME_ERRORS
from ._collectors_backends_sysfs_support import _append_error
from ._collectors_backends_sysfs_support import _build_led_entry
from ._collectors_backends_sysfs_support import _exception_snapshot
from ._collectors_backends_sysfs_support import _infer_zone_snapshot


def sysfs_led_candidates_snapshot() -> dict[str, Any]:
    """Collect debug info for Tier 1 sysfs LED selection."""

    try:
        from ..backends.sysfs.common import _is_candidate_led, _leds_root, _score_led_dir  # type: ignore
    except _EXPECTED_RUNTIME_ERRORS as exc:
        return {"errors": [_exception_snapshot(stage="import_sysfs_common", exc=exc)]}

    root: Path
    try:
        root = Path(os.fspath(_leds_root()))
    except _EXPECTED_RUNTIME_ERRORS as exc:
        return {"errors": [_exception_snapshot(stage="resolve_leds_root", exc=exc)]}

    root_txt = str(root)
    root_is_sys = root_txt.startswith("/sys/")
    out: dict[str, Any] = {
        "root": (root_txt if root_is_sys else "<overridden>"),
        "root_is_sysfs": root_is_sys,
        "exists": bool(root.exists()),
    }

    try:
        from ..backends.sysfs import privileged  # type: ignore

        helper_path = os.fspath(privileged.power_helper_path())
        helper_entry: dict[str, Any] = {
            "path": helper_path,
            "exists": bool(Path(helper_path).exists()),
            "supports_led_apply": bool(privileged.helper_supports_led_apply()),
        }
        try:
            helper_entry["executable"] = bool(os.access(helper_path, os.X_OK))
        except _ACCESS_ERRORS as exc:
            _append_error(out, stage="power_helper_access", exc=exc, extra={"path": helper_path})
        try:
            helper_st = os.stat(helper_path)
            helper_entry["uid"] = int(helper_st.st_uid)
            helper_entry["gid"] = int(helper_st.st_gid)
            helper_entry["mode"] = f"{int(helper_st.st_mode) & 0o777:04o}"
        except (OSError, TypeError, ValueError) as exc:
            _append_error(out, stage="power_helper_stat", exc=exc, extra={"path": helper_path})

        out["power_helper"] = helper_entry
    except _EXPECTED_RUNTIME_ERRORS as exc:
        _append_error(out, stage="power_helper_snapshot", exc=exc)

    try:
        pkexec_path = shutil.which("pkexec")
        sudo_path = shutil.which("sudo")
        out["pkexec_in_path"] = bool(pkexec_path)
        out["sudo_in_path"] = bool(sudo_path)
        if pkexec_path:
            out["pkexec_path"] = pkexec_path
        if sudo_path:
            out["sudo_path"] = sudo_path
    except (OSError, TypeError, ValueError) as exc:
        _append_error(out, stage="discover_auth_helpers", exc=exc)

    if not root.exists():
        return out

    candidates: list[Path] = []
    try:
        for child in root.iterdir():
            if child.is_dir() and _is_candidate_led(child.name):
                candidates.append(child)
    except _EXPECTED_RUNTIME_ERRORS as exc:
        out["candidates_count"] = 0
        _append_error(out, stage="scan_led_candidates", exc=exc, extra={"root": root_txt})
        return out

    scored: list[tuple[int, str, Path]] = []
    for led_dir in candidates:
        score = 0
        try:
            score = int(_score_led_dir(led_dir))
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            _append_error(out, stage="score_led_dir", exc=exc, extra={"candidate": led_dir.name})
        scored.append((score, led_dir.name, led_dir))

    scored.sort(key=lambda item: (-item[0], item[1].lower()))

    out["candidates_count"] = len(candidates)
    out["top"] = []
    out["zones"] = _infer_zone_snapshot(scored)

    for score, name, led_dir in scored[:8]:
        entry = _build_led_entry(led_dir=led_dir, name=name, score=score, root_is_sys=root_is_sys)
        out["top"].append(entry)

    return out


def sysfs_mouse_candidates_snapshot() -> dict[str, Any]:
    """Collect debug info for auxiliary sysfs mouse candidate selection."""

    try:
        from ..backends.sysfs_mouse.common import _leds_root, inspect_led_candidate  # type: ignore
    except _EXPECTED_RUNTIME_ERRORS as exc:
        return {"errors": [_exception_snapshot(stage="import_sysfs_mouse_common", exc=exc)]}

    root: Path
    try:
        root = Path(os.fspath(_leds_root()))
    except _EXPECTED_RUNTIME_ERRORS as exc:
        return {"errors": [_exception_snapshot(stage="resolve_sysfs_mouse_root", exc=exc)]}

    root_txt = str(root)
    root_is_sys = root_txt.startswith("/sys/")
    out: dict[str, Any] = {
        "root": (root_txt if root_is_sys else "<overridden>"),
        "root_is_sysfs": root_is_sys,
        "exists": bool(root.exists()),
    }

    if not root.exists():
        return out

    inspected: list[dict[str, Any]] = []
    try:
        for child in root.iterdir():
            if not child.is_dir():
                continue
            entry = dict(inspect_led_candidate(child))
            if not root_is_sys:
                entry["path"] = "<overridden>"
            inspected.append(entry)
    except _EXPECTED_RUNTIME_ERRORS as exc:
        out["candidates_count"] = 0
        _append_error(out, stage="scan_sysfs_mouse_candidates", exc=exc, extra={"root": root_txt})
        return out

    inspected.sort(
        key=lambda entry: (
            not bool(entry.get("eligible")),
            not bool(entry.get("matched")),
            -int(entry.get("score") or 0),
            str(entry.get("name") or "").lower(),
        )
    )

    out["candidates_count"] = len(inspected)
    out["matched_count"] = sum(1 for entry in inspected if bool(entry.get("matched")))
    out["eligible_count"] = sum(1 for entry in inspected if bool(entry.get("eligible")))
    out["top"] = inspected[:8]
    return out
