from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any


def sysfs_led_candidates_snapshot() -> dict[str, Any]:
    """Collect debug info for Tier 1 sysfs LED selection."""

    try:
        from ..backends.sysfs.common import _is_candidate_led, _leds_root, _score_led_dir  # type: ignore
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

    scored.sort(key=lambda item: (-item[0], item[1].lower()))

    out["candidates_count"] = len(candidates)
    out["top"] = []
    out["zones"] = _infer_zone_snapshot(scored)

    for score, name, led_dir in scored[:8]:
        entry = _build_led_entry(led_dir=led_dir, name=name, score=score, root_is_sys=root_is_sys)
        out["top"].append(entry)

    return out


def _infer_zone_snapshot(scored: list[tuple[int, str, Path]]) -> dict[str, Any]:
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

    try:
        inferred_zone_count = max((len(names) for names in groups.values()), default=0)
    except Exception:
        inferred_zone_count = 0

    return {
        "kbd_backlight_leds": kbd_names[:16],
        "groups": [
            {"base": base, "count": len(names), "names": sorted(names)[:16]}
            for base, names in sorted(groups.items(), key=lambda item: (-(len(item[1])), item[0].lower()))
        ][:8],
        "inferred_zone_count": int(inferred_zone_count),
    }


def _build_led_entry(*, led_dir: Path, name: str, score: int, root_is_sys: bool) -> dict[str, Any]:
    brightness_path = led_dir / "brightness"

    try:
        stat_result: os.stat_result | None = os.stat(brightness_path)
    except Exception:
        stat_result = None

    acl_present: bool | None = None
    try:
        if hasattr(os, "getxattr"):
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
        pass
    except Exception:
        pass

    entry: dict[str, Any] = {
        "name": name,
        "score": int(score),
        "has_multi_intensity": bool((led_dir / "multi_intensity").exists()),
        "has_color": bool((led_dir / "color").exists()),
        "has_brightness": bool(brightness_path.exists()),
        "brightness_readable": access_r,
        "brightness_writable": access_w,
    }

    _apply_device_info(entry=entry, led_dir=led_dir, root_is_sys=root_is_sys)

    if stat_result is not None:
        try:
            entry["brightness_uid"] = int(stat_result.st_uid)
            entry["brightness_gid"] = int(stat_result.st_gid)
            entry["brightness_mode"] = f"{int(stat_result.st_mode) & 0o777:04o}"
        except Exception:
            pass

    if acl_present is not None:
        entry["brightness_acl"] = acl_present
    if access_r_eff is not None:
        entry["brightness_readable_effective"] = access_r_eff
    if access_w_eff is not None:
        entry["brightness_writable_effective"] = access_w_eff
    if root_is_sys:
        entry["path"] = str(led_dir)

    return entry


def _apply_device_info(*, entry: dict[str, Any], led_dir: Path, root_is_sys: bool) -> None:
    try:
        dev_link = led_dir / "device"
        if not dev_link.exists():
            return
        resolved_dev = str(dev_link.resolve())
        if root_is_sys and resolved_dev.startswith("/sys/"):
            entry["device_path"] = resolved_dev
        driver_link = dev_link / "driver"
        if not driver_link.exists():
            return
        driver_name = driver_link.resolve().name
        if driver_name:
            entry["device_driver"] = driver_name
        module_link = driver_link / "module"
        if module_link.exists():
            module_name = module_link.resolve().name
            if module_name:
                entry["device_module"] = module_name
    except Exception:
        return
