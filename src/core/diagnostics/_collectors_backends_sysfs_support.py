from __future__ import annotations

import os
import traceback
from pathlib import Path
from typing import Any


_EXPECTED_RUNTIME_ERRORS = (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError)
_ACCESS_ERRORS = (NotImplementedError, OSError, TypeError, ValueError)


def _exception_snapshot(*, stage: str, exc: Exception, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "stage": stage,
        "type": exc.__class__.__name__,
        "message": str(exc),
        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).strip(),
    }
    if isinstance(extra, dict) and extra:
        payload.update(extra)
    return payload


def _append_error(
    container: dict[str, Any], *, stage: str, exc: Exception, extra: dict[str, Any] | None = None
) -> None:
    errors = container.setdefault("errors", [])
    if isinstance(errors, list):
        errors.append(_exception_snapshot(stage=stage, exc=exc, extra=extra))


def _safe_access(
    container: dict[str, Any], *, key: str, path: Path, mode: int, stage: str, effective_ids: bool = False
) -> bool | None:
    try:
        if effective_ids:
            return bool(os.access(path, mode, effective_ids=True))
        return bool(os.access(path, mode))
    except _ACCESS_ERRORS as exc:
        _append_error(
            container,
            stage=stage,
            exc=exc,
            extra={"path": str(path), "effective_ids": bool(effective_ids), "field": key},
        )
        return None


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

    inferred_zone_count = max((len(names) for names in groups.values()), default=0)

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

    entry: dict[str, Any] = {
        "name": name,
        "score": int(score),
        "has_multi_intensity": bool((led_dir / "multi_intensity").exists()),
        "has_color": bool((led_dir / "color").exists()),
        "has_brightness": bool(brightness_path.exists()),
        "brightness_readable": False,
        "brightness_writable": False,
    }

    stat_result: os.stat_result | None = None
    try:
        stat_result = os.stat(brightness_path)
    except (OSError, TypeError, ValueError) as exc:
        _append_error(entry, stage="brightness_stat", exc=exc, extra={"path": str(brightness_path)})

    acl_present: bool | None = None
    if hasattr(os, "getxattr"):
        try:
            os.getxattr(brightness_path, "system.posix_acl_access")  # type: ignore[arg-type]
            acl_present = True
        except OSError:
            acl_present = False
        except (TypeError, ValueError) as exc:
            _append_error(entry, stage="brightness_acl", exc=exc, extra={"path": str(brightness_path)})

    access_r = _safe_access(
        entry,
        key="brightness_readable",
        path=brightness_path,
        mode=os.R_OK,
        stage="brightness_access",
    )
    access_w = _safe_access(
        entry,
        key="brightness_writable",
        path=brightness_path,
        mode=os.W_OK,
        stage="brightness_access",
    )
    if access_r is not None:
        entry["brightness_readable"] = access_r
    if access_w is not None:
        entry["brightness_writable"] = access_w

    access_r_eff = _safe_access(
        entry,
        key="brightness_readable_effective",
        path=brightness_path,
        mode=os.R_OK,
        stage="brightness_effective_access",
        effective_ids=True,
    )
    access_w_eff = _safe_access(
        entry,
        key="brightness_writable_effective",
        path=brightness_path,
        mode=os.W_OK,
        stage="brightness_effective_access",
        effective_ids=True,
    )

    _apply_device_info(entry=entry, led_dir=led_dir, root_is_sys=root_is_sys)

    if stat_result is not None:
        entry["brightness_uid"] = int(stat_result.st_uid)
        entry["brightness_gid"] = int(stat_result.st_gid)
        entry["brightness_mode"] = f"{int(stat_result.st_mode) & 0o777:04o}"

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
    dev_link = led_dir / "device"
    if not dev_link.exists():
        return

    try:
        resolved_dev = str(dev_link.resolve())
    except (OSError, RuntimeError, ValueError) as exc:
        _append_error(entry, stage="resolve_device_link", exc=exc, extra={"led": led_dir.name})
        return

    if root_is_sys and resolved_dev.startswith("/sys/"):
        entry["device_path"] = resolved_dev

    driver_link = dev_link / "driver"
    if not driver_link.exists():
        return

    try:
        driver_name = driver_link.resolve().name
    except (OSError, RuntimeError, ValueError) as exc:
        _append_error(entry, stage="resolve_device_driver", exc=exc, extra={"led": led_dir.name})
        return

    if driver_name:
        entry["device_driver"] = driver_name

    module_link = driver_link / "module"
    if not module_link.exists():
        return

    try:
        module_name = module_link.resolve().name
    except (OSError, RuntimeError, ValueError) as exc:
        _append_error(entry, stage="resolve_device_module", exc=exc, extra={"led": led_dir.name})
        return

    if module_name:
        entry["device_module"] = module_name
