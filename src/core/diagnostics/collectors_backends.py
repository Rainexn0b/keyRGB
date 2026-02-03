from __future__ import annotations

import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from src.core.utils.safe_attrs import safe_int_attr


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
        from ..backends.sysfs.common import _leds_root, _is_candidate_led, _score_led_dir  # type: ignore
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

    # Best-effort privileged write path hints.
    try:
        from ..backends.sysfs import privileged  # type: ignore

        helper_path = privileged.power_helper_path()
        helper_entry: dict[str, Any] = {
            "path": helper_path,
            "exists": bool(Path(helper_path).exists()),
            "supports_led_apply": bool(privileged.helper_supports_led_apply()),
        }
        try:
            helper_entry["executable"] = bool(os.access(helper_path, os.X_OK))
        except Exception:
            pass
        try:
            helper_st = os.stat(helper_path)
            helper_entry["uid"] = int(helper_st.st_uid)
            helper_entry["gid"] = int(helper_st.st_gid)
            helper_entry["mode"] = f"{int(helper_st.st_mode) & 0o777:04o}"
        except Exception:
            pass

        out["power_helper"] = helper_entry
    except Exception:
        pass

    try:
        pkexec_path = shutil.which("pkexec")
        sudo_path = shutil.which("sudo")
        out["pkexec_in_path"] = bool(pkexec_path)
        out["sudo_in_path"] = bool(sudo_path)
        if pkexec_path:
            out["pkexec_path"] = pkexec_path
        if sudo_path:
            out["sudo_path"] = sudo_path
    except Exception:
        pass

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

    # Infer likely keyboard lighting zones from common sysfs naming patterns.
    # Ex: rgb:kbd_backlight, rgb:kbd_backlight_1, rgb:kbd_backlight_2 -> 3 zones.
    kbd_names: list[str] = []
    for _, name, _led_dir in scored:
        if "kbd_backlight" in (name or "").lower():
            kbd_names.append(name)

    groups: dict[str, list[str]] = {}
    for name in kbd_names:
        base = name
        try:
            left, suffix = name.rsplit("_", 1)
            if suffix.isdigit() and "kbd_backlight" in left.lower():
                base = left
        except ValueError:
            pass
        groups.setdefault(base, []).append(name)

    inferred_zone_count = 0
    try:
        inferred_zone_count = max((len(v) for v in groups.values()), default=0)
    except Exception:
        inferred_zone_count = 0

    out["zones"] = {
        "kbd_backlight_leds": kbd_names[:16],
        "groups": [
            {"base": base, "count": len(names), "names": sorted(names)[:16]}
            for base, names in sorted(groups.items(), key=lambda kv: (-(len(kv[1])), kv[0].lower()))
        ][:8],
        "inferred_zone_count": int(inferred_zone_count),
    }

    for score, name, led_dir in scored[:8]:
        brightness_path = led_dir / "brightness"

        # Permission diagnostics: root-owned sysfs nodes are common; this makes it
        # obvious whether the issue is udev/uaccess/ACL/polkit versus detection.
        st: os.stat_result | None
        try:
            st = os.stat(brightness_path)
        except Exception:
            st = None

        acl_present: bool | None = None
        try:
            if hasattr(os, "getxattr"):
                # Presence check only; reading ACL contents requires extra parsing.
                os.getxattr(brightness_path, "system.posix_acl_access")  # type: ignore[arg-type]
                acl_present = True
        except OSError:
            acl_present = False
        except Exception:
            acl_present = None

        access_r = bool(os.access(brightness_path, os.R_OK))
        access_w = bool(os.access(brightness_path, os.W_OK))
        access_r_eff: bool | None = None
        access_w_eff: bool | None = None
        try:
            access_r_eff = bool(os.access(brightness_path, os.R_OK, effective_ids=True))
            access_w_eff = bool(os.access(brightness_path, os.W_OK, effective_ids=True))
        except TypeError:
            # effective_ids isn't available on some platforms/Pythons.
            pass
        except Exception:
            pass

        entry: dict[str, Any] = {
            "name": name,
            "score": int(score),
            "has_multi_intensity": bool((led_dir / "multi_intensity").exists()),
            "has_color": bool((led_dir / "color").exists()),
            "has_brightness": bool((led_dir / "brightness").exists()),
            "brightness_readable": access_r,
            "brightness_writable": access_w,
        }

        # Identify the kernel driver/module behind the LED node (best-effort).
        # This is extremely helpful to distinguish tuxedo/clevo/system76/etc.
        try:
            dev_link = led_dir / "device"
            if dev_link.exists():
                resolved_dev = str(dev_link.resolve())
                if root_is_sys and resolved_dev.startswith("/sys/"):
                    entry["device_path"] = resolved_dev
                driver_link = dev_link / "driver"
                if driver_link.exists():
                    driver_name = driver_link.resolve().name
                    if driver_name:
                        entry["device_driver"] = driver_name
                    module_link = driver_link / "module"
                    if module_link.exists():
                        module_name = module_link.resolve().name
                        if module_name:
                            entry["device_module"] = module_name
        except Exception:
            pass

        if st is not None:
            try:
                entry["brightness_uid"] = int(st.st_uid)
                entry["brightness_gid"] = int(st.st_gid)
                entry["brightness_mode"] = f"{int(st.st_mode) & 0o777:04o}"
            except Exception:
                pass

        if acl_present is not None:
            entry["brightness_acl"] = acl_present
        if access_r_eff is not None:
            entry["brightness_readable_effective"] = access_r_eff
        if access_w_eff is not None:
            entry["brightness_writable_effective"] = access_w_eff

        # Only include full paths if they are clearly sysfs.
        if root_is_sys:
            entry["path"] = str(led_dir)
        out["top"].append(entry)

    return out


@contextmanager
def _disable_usb_scan_under_pytest_if_needed():
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

    try:
        yield
    finally:
        if did_override_usb_scan:
            if restore_disable_usb_scan is None:
                os.environ.pop("KEYRGB_DISABLE_USB_SCAN", None)
            else:
                os.environ["KEYRGB_DISABLE_USB_SCAN"] = restore_disable_usb_scan


def _probe_backend(backend: object) -> dict[str, Any]:
    try:
        probe_fn = getattr(backend, "probe", None)
        if callable(probe_fn):
            result = probe_fn()
            available = bool(getattr(result, "available", False))
            reason = str(getattr(result, "reason", ""))
            confidence = safe_int_attr(result, "confidence", default=0)
            identifiers = getattr(result, "identifiers", None)
        else:
            available = bool(getattr(backend, "is_available")())
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

    try:
        entry["priority"] = safe_int_attr(backend, "priority", default=0)
    except Exception:
        entry["priority"] = 0

    tier = _tier_for_backend_name(str(entry.get("name") or ""))
    if tier is not None:
        entry["tier"] = tier
    provider = _provider_for_backend_name(str(entry.get("name") or ""))
    if provider is not None:
        entry["provider"] = provider

    if identifiers:
        try:
            entry["identifiers"] = dict(identifiers)
        except Exception:
            pass

    return entry


def _selection_is_blocked_under_pytest() -> tuple[bool, str | None]:
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        return False, None
    allow_hardware = os.environ.get("KEYRGB_ALLOW_HARDWARE") == "1" or os.environ.get("KEYRGB_HW_TESTS") == "1"
    if allow_hardware:
        return False, None
    return True, "selection disabled under pytest unless KEYRGB_ALLOW_HARDWARE=1"


def _collect_available_candidates(probes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    available_candidates: list[dict[str, Any]] = []
    for p in probes:
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

    return available_candidates


def backend_probe_snapshot() -> dict[str, Any]:
    """Collect backend probe results (best-effort)."""

    try:
        # Diagnostics is a subpackage under src/core, so backends live one level up.
        from ..backends.registry import iter_backends, select_backend
    except Exception:
        return {}

    probes: list[dict[str, Any]] = []
    with _disable_usb_scan_under_pytest_if_needed():
        for backend in iter_backends():
            probes.append(_probe_backend(backend))

    requested = os.environ.get("KEYRGB_BACKEND") or "auto"

    selection_blocked, selection_blocked_reason = _selection_is_blocked_under_pytest()

    selected = None
    try:
        if not selection_blocked:
            selected_backend = select_backend()
            selected = getattr(selected_backend, "name", None) if selected_backend is not None else None
    except Exception:
        selected = None

    available_candidates = _collect_available_candidates(probes)

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
