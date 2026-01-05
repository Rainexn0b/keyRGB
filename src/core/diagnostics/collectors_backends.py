from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _tier_for_backend_name(name: str) -> int | None:
    n = (name or "").strip().lower()
    if n == "sysfs-leds":
        return 1
    if n.startswith("ite"):
        return 2
    return None


def _provider_for_backend_name(name: str) -> str | None:
    n = (name or "").strip().lower()
    if n == "sysfs-leds":
        return "kernel-sysfs"
    if n.startswith("ite"):
        return "usb-userspace"
    return None


def _sysfs_led_candidates_snapshot() -> dict[str, Any]:
    """Collect debug info for Tier 1 sysfs LED selection.

    This is best-effort and intentionally avoids including non-/sys paths.
    """

    try:
        from ..backends.sysfs.backend import _leds_root, _is_candidate_led, _score_led_dir  # type: ignore
    except Exception:
        return {}

    root: Path
    try:
        root = _leds_root()
    except Exception:
        return {}

    root_txt = str(root)
    root_is_sys = root_txt.startswith("/sys/")
    out: dict[str, Any] = {
        "root": (root_txt if root_is_sys else "<overridden>"),
        "root_is_sysfs": root_is_sys,
        "exists": bool(root.exists()),
    }

    if not root.exists():
        return out

    candidates: list[Path] = []
    try:
        for child in root.iterdir():
            if child.is_dir() and _is_candidate_led(child.name):
                candidates.append(child)
    except Exception:
        out["candidates_count"] = 0
        return out

    scored: list[tuple[int, str, Path]] = []
    for led_dir in candidates:
        try:
            score = int(_score_led_dir(led_dir))
        except Exception:
            score = 0
        scored.append((score, led_dir.name, led_dir))

    scored.sort(key=lambda t: (-t[0], t[1].lower()))

    out["candidates_count"] = len(candidates)
    out["top"] = []
    for score, name, led_dir in scored[:8]:
        entry: dict[str, Any] = {
            "name": name,
            "score": int(score),
            "has_multi_intensity": bool((led_dir / "multi_intensity").exists()),
            "has_color": bool((led_dir / "color").exists()),
            "has_brightness": bool((led_dir / "brightness").exists()),
            "brightness_writable": bool(os.access(led_dir / "brightness", os.W_OK)),
        }
        # Only include full paths if they are clearly sysfs.
        if root_is_sys:
            entry["path"] = str(led_dir)
        out["top"].append(entry)

    return out


def backend_probe_snapshot() -> dict[str, Any]:
    """Collect backend probe results (best-effort)."""

    try:
        # Diagnostics is a subpackage under src/core, so backends live one level up.
        from ..backends.registry import iter_backends, select_backend
    except Exception:
        return {}

    # Safety: when diagnostics are collected under pytest, avoid any real USB scanning.
    # This prevents tests from triggering side effects (some controllers reset or turn off
    # lighting when poked via libusb).
    did_override_usb_scan = False
    restore_disable_usb_scan: str | None = None
    if (
        os.environ.get("PYTEST_CURRENT_TEST")
        and os.environ.get("KEYRGB_ALLOW_HARDWARE") != "1"
        and os.environ.get("KEYRGB_HW_TESTS") != "1"
    ):
        restore_disable_usb_scan = os.environ.get("KEYRGB_DISABLE_USB_SCAN")
        os.environ["KEYRGB_DISABLE_USB_SCAN"] = "1"
        did_override_usb_scan = True

    probes: list[dict[str, Any]] = []
    try:
        for backend in iter_backends():
            try:
                probe_fn = getattr(backend, "probe", None)
                if callable(probe_fn):
                    result = probe_fn()
                    available = bool(getattr(result, "available", False))
                    reason = str(getattr(result, "reason", ""))
                    confidence = int(getattr(result, "confidence", 0) or 0)
                    identifiers = getattr(result, "identifiers", None)
                else:
                    available = bool(backend.is_available())
                    reason = "is_available"
                    confidence = 50 if available else 0
                    identifiers = None
            except Exception as exc:
                available = False
                reason = f"probe exception: {exc}"
                confidence = 0
                identifiers = None

            entry: dict[str, Any] = {
                "name": getattr(backend, "name", backend.__class__.__name__),
                "available": available,
                "confidence": confidence,
                "reason": reason,
            }

            # Expose selection-relevant metadata.
            try:
                entry["priority"] = int(getattr(backend, "priority", 0) or 0)
            except Exception:
                entry["priority"] = 0

            tier = _tier_for_backend_name(str(entry.get("name") or ""))
            if tier is not None:
                entry["tier"] = tier
            provider = _provider_for_backend_name(str(entry.get("name") or ""))
            if provider is not None:
                entry["provider"] = provider

            if identifiers:
                entry["identifiers"] = dict(identifiers)
            probes.append(entry)
    finally:
        if did_override_usb_scan:
            if restore_disable_usb_scan is None:
                os.environ.pop("KEYRGB_DISABLE_USB_SCAN", None)
            else:
                os.environ["KEYRGB_DISABLE_USB_SCAN"] = restore_disable_usb_scan

    requested = (os.environ.get("KEYRGB_BACKEND") or "auto")

    # Mirror backend registry safety rules: under pytest, selection may be intentionally disabled.
    selection_blocked = False
    selection_blocked_reason: str | None = None
    if os.environ.get("PYTEST_CURRENT_TEST"):
        allow_hardware = os.environ.get("KEYRGB_ALLOW_HARDWARE") == "1" or os.environ.get("KEYRGB_HW_TESTS") == "1"
        if not allow_hardware:
            selection_blocked = True
            selection_blocked_reason = "selection disabled under pytest unless KEYRGB_ALLOW_HARDWARE=1"

    selected = None
    try:
        if not selection_blocked:
            selected_backend = select_backend()
            selected = getattr(selected_backend, "name", None) if selected_backend is not None else None
    except Exception:
        selected = None

    # Provide the auto-selection ordering for debugging.
    available_candidates: list[dict[str, Any]] = []
    for p in probes:
        if not isinstance(p, dict):
            continue
        if not p.get("available"):
            continue
        available_candidates.append(
            {
                "name": p.get("name"),
                "confidence": p.get("confidence"),
                "priority": p.get("priority"),
                "tier": p.get("tier"),
                "provider": p.get("provider"),
                "reason": p.get("reason"),
                "identifiers": p.get("identifiers"),
            }
        )

    try:
        available_candidates.sort(
            key=lambda e: (
                int(e.get("confidence") or 0),
                int(e.get("priority") or 0),
            ),
            reverse=True,
        )
    except Exception:
        pass

    return {
        "selected": selected,
        "requested": requested,
        "probes": probes,
        "selection": {
            "policy": "highest confidence wins; priority is tie-breaker",
            "requested_effective": requested,
            "blocked": selection_blocked,
            "blocked_reason": selection_blocked_reason,
            "disable_usb_scan": (os.environ.get("KEYRGB_DISABLE_USB_SCAN") == "1"),
        },
        "candidates_sorted": available_candidates,
        "sysfs_led_candidates": _sysfs_led_candidates_snapshot(),
    }
