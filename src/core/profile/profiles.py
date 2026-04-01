"""Profile storage for per-key tools.

Profiles are *local* (per-user) and stored under:
  ~/.config/keyrgb/profiles/<profile_name>/

A profile groups:
- Keymap (visual key_id -> matrix row,col)
- Overlay alignment tweaks (global + per-key overrides)
- Per-key colors

The tray app still applies lighting from `config.json`. Per-key tools load/apply
profile data by writing to config when you activate a profile.
"""

from __future__ import annotations

import logging
from typing import Dict, Tuple

from ._backdrop import load_backdrop_transparency, save_backdrop_transparency
from .json_storage import read_json, write_json_atomic
from .paths import (
    default_profile_path,
    DEFAULT_PROFILE_NAME,
    delete_profile,
    get_default_profile,
    get_active_profile,
    list_profiles,
    paths_for,
    profiles_root,
    safe_profile_name,
    set_active_profile,
    set_default_profile,
)
from src.core.config.layout_slots import load_layout_slot_overrides, save_layout_slot_overrides
from src.core.resources.defaults import (
    DEFAULT_COLORS,
    get_default_lightbar_overlay,
    get_default_keymap,
    get_default_layout_tweaks,
    get_default_per_key_tweaks,
)
from src.core.utils.logging_utils import log_throttled

# Backwards-compatible constant
_DEFAULT_PROFILE = DEFAULT_PROFILE_NAME
logger = logging.getLogger(__name__)
_MISSING = object()
_READ_FAILED = object()


__all__ = [
    "DEFAULT_PROFILE_NAME",
    "_DEFAULT_PROFILE",
    "default_profile_path",
    "apply_profile_to_config",
    "delete_profile",
    "get_default_profile",
    "get_active_profile",
    "list_profiles",
    "load_backdrop_transparency",
    "load_keymap",
    "load_layout_global",
    "load_layout_per_key",
    "load_layout_slots",
    "load_lightbar_overlay",
    "load_per_key_colors",
    "paths_for",
    "profiles_root",
    "safe_profile_name",
    "save_backdrop_transparency",
    "save_keymap",
    "save_layout_global",
    "save_layout_per_key",
    "save_layout_slots",
    "save_lightbar_overlay",
    "save_per_key_colors",
    "migrate_builtin_profile_brightness",
    "set_active_profile",
    "set_default_profile",
]


def _normalize_lightbar_overlay(raw: object) -> Dict[str, bool | float]:
    out: Dict[str, bool | float] = dict(get_default_lightbar_overlay())
    if isinstance(raw, dict):
        visible = raw.get("visible")
        if isinstance(visible, bool):
            out["visible"] = visible
        elif isinstance(visible, (int, float)):
            out["visible"] = bool(visible)

        for key in ("length", "thickness", "dx", "dy", "inset"):
            value = raw.get(key)
            if isinstance(value, (int, float)):
                out[key] = float(value)

    out["length"] = max(0.20, min(1.0, float(out.get("length", 0.72))))
    out["thickness"] = max(0.04, min(0.40, float(out.get("thickness", 0.12))))
    out["dx"] = max(-0.50, min(0.50, float(out.get("dx", 0.0))))
    out["dy"] = max(-0.50, min(0.50, float(out.get("dy", 0.0))))
    out["inset"] = max(0.0, min(0.25, float(out.get("inset", 0.04))))
    out["visible"] = bool(out.get("visible", True))
    return out


def load_keymap(name: str | None = None, *, physical_layout: str | None = None) -> Dict[str, Tuple[int, int]]:
    p = paths_for(name).keymap
    raw = read_json(p)
    if raw is None:
        raw = get_default_keymap(physical_layout)

    out: Dict[str, Tuple[int, int]] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(k, str) and isinstance(v, str) and "," in v:
                a, b = v.split(",", 1)
                try:
                    out[k] = (int(a), int(b))
                except (TypeError, ValueError):
                    continue
            elif isinstance(k, str) and isinstance(v, (list, tuple)) and len(v) == 2:
                try:
                    out[k] = (int(v[0]), int(v[1]))
                except (TypeError, ValueError):
                    continue
    return out


def save_keymap(keymap: Dict[str, Tuple[int, int]], name: str | None = None) -> None:
    p = paths_for(name).keymap
    payload = {k: f"{rc[0]},{rc[1]}" for k, rc in sorted(keymap.items())}
    write_json_atomic(p, payload)


def load_layout_global(name: str | None = None, *, physical_layout: str | None = None) -> Dict[str, float]:
    p = paths_for(name).layout_global
    raw = read_json(p)
    if raw is None:
        raw = get_default_layout_tweaks(physical_layout)

    out = {"dx": 0.0, "dy": 0.0, "sx": 1.0, "sy": 1.0, "inset": 0.06}
    if isinstance(raw, dict):
        for k in list(out.keys()):
            v = raw.get(k)
            if isinstance(v, (int, float)):
                out[k] = float(v)
    out["inset"] = max(0.0, min(0.20, float(out.get("inset", 0.06))))
    return out


def save_layout_global(tweaks: Dict[str, float], name: str | None = None) -> None:
    p = paths_for(name).layout_global
    payload = {
        "dx": float(tweaks.get("dx", 0.0)),
        "dy": float(tweaks.get("dy", 0.0)),
        "sx": float(tweaks.get("sx", 1.0)),
        "sy": float(tweaks.get("sy", 1.0)),
        "inset": float(tweaks.get("inset", 0.06)),
    }
    write_json_atomic(p, payload)


def load_layout_per_key(name: str | None = None, *, physical_layout: str | None = None) -> Dict[str, Dict[str, float]]:
    p = paths_for(name).layout_per_key
    raw = read_json(p)
    if raw is None:
        raw = get_default_per_key_tweaks(physical_layout)

    out: Dict[str, Dict[str, float]] = {}
    if isinstance(raw, dict):
        for key_id, tweaks in raw.items():
            if not isinstance(key_id, str) or not isinstance(tweaks, dict):
                continue
            t: Dict[str, float] = {}
            for k in ("dx", "dy", "sx", "sy", "inset"):
                v = tweaks.get(k)
                if isinstance(v, (int, float)):
                    t[k] = float(v)
            if t:
                # Clamp inset if present
                if "inset" in t:
                    t["inset"] = max(0.0, min(0.20, float(t["inset"])))
                out[key_id] = t
    return out


def save_layout_per_key(per_key: Dict[str, Dict[str, float]], name: str | None = None) -> None:
    p = paths_for(name).layout_per_key
    payload: Dict[str, Dict[str, float]] = {}
    for key_id, tweaks in (per_key or {}).items():
        if not isinstance(key_id, str) or not isinstance(tweaks, dict):
            continue
        t: Dict[str, float] = {}
        for k in ("dx", "dy", "sx", "sy", "inset"):
            if k in tweaks and isinstance(tweaks[k], (int, float)):
                t[k] = float(tweaks[k])
        if t:
            if "inset" in t:
                t["inset"] = max(0.0, min(0.20, float(t["inset"])))
            payload[key_id] = t
    write_json_atomic(p, payload)


def load_lightbar_overlay(name: str | None = None) -> Dict[str, bool | float]:
    p = paths_for(name).lightbar_overlay
    raw = read_json(p)
    if raw is None:
        raw = get_default_lightbar_overlay()
    return _normalize_lightbar_overlay(raw)


def save_lightbar_overlay(
    overlay: Dict[str, bool | float],
    name: str | None = None,
) -> Dict[str, bool | float]:
    p = paths_for(name).lightbar_overlay
    payload = _normalize_lightbar_overlay(overlay)
    write_json_atomic(p, payload)
    return payload


def load_layout_slots(
    name: str | None = None,
    *,
    physical_layout: str | None = None,
) -> Dict[str, Dict[str, object]]:
    return load_layout_slot_overrides(physical_layout or "auto", legacy_profile_name=name)


def save_layout_slots(
    layout_slots: Dict[str, Dict[str, object]],
    name: str | None = None,
    *,
    physical_layout: str | None = None,
) -> Dict[str, Dict[str, object]]:
    return save_layout_slot_overrides(physical_layout or "auto", layout_slots)


def load_per_key_colors(
    name: str | None = None,
) -> Dict[Tuple[int, int], Tuple[int, int, int]]:
    p = paths_for(name).per_key_colors
    raw = read_json(p)
    if raw is None:
        # Built-in presets: allow a profile to have a meaningful default even
        # before the user has saved any colors.
        prof = safe_profile_name(name or "")
        if prof == "dark":
            return {k: (0, 0, 0) for k in DEFAULT_COLORS.keys()}
        if prof == "dim":
            # Low-light typing preset: a faint white backlight.
            return {k: (255, 255, 255) for k in DEFAULT_COLORS.keys()}
        return DEFAULT_COLORS.copy()

    out: Dict[Tuple[int, int], Tuple[int, int, int]] = {}
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        try:
            rs, cs = str(k).split(",", 1)
            r = int(rs.strip())
            c = int(cs.strip())
            rr, gg, bb = v
            out[(r, c)] = (int(rr), int(gg), int(bb))
        except (TypeError, ValueError):
            continue
    return out


def save_per_key_colors(colors: Dict[Tuple[int, int], Tuple[int, int, int]], name: str | None = None) -> None:
    p = paths_for(name).per_key_colors
    payload: Dict[str, list[int]] = {}
    for (r, c), rgb in (colors or {}).items():
        try:
            rr, gg, bb = rgb
            payload[f"{int(r)},{int(c)}"] = [int(rr), int(gg), int(bb)]
        except (TypeError, ValueError):
            continue
    write_json_atomic(p, payload)


def _active_profile_name(*, default: str, log_key: str, log_msg: str) -> str:
    try:
        return safe_profile_name(get_active_profile())
    except Exception as exc:
        log_throttled(
            logger,
            log_key,
            interval_s=60,
            level=logging.DEBUG,
            msg=log_msg,
            exc=exc,
        )
        return default


def _read_attr_value(obj: object, attr_name: str, *, log_key: str, log_msg: str) -> object:
    try:
        return getattr(obj, attr_name)
    except AttributeError:
        return _MISSING
    except Exception as exc:
        log_throttled(
            logger,
            log_key,
            interval_s=60,
            level=logging.DEBUG,
            msg=log_msg,
            exc=exc,
        )
        return _READ_FAILED


def _coerce_int(value: object, *, default: int) -> int:
    if value is _MISSING or value is _READ_FAILED or value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _set_attr_value(obj: object, attr_name: str, value: int, *, log_key: str, log_msg: str) -> bool:
    try:
        setattr(obj, attr_name, int(value))
        return True
    except Exception as exc:
        log_throttled(
            logger,
            log_key,
            interval_s=60,
            level=logging.DEBUG,
            msg=log_msg,
            exc=exc,
        )
        return False


def _builtin_profile_brightness(name: str) -> int | None:
    prof = safe_profile_name(name)
    if prof == "light":
        return 50
    if prof == "dim":
        return 10
    return None


def migrate_builtin_profile_brightness(cfg) -> bool:
    """Repair the known stale built-in profile brightness states.

    Older builds could leave ``active_profile=dim`` while persisting
    ``brightness=25`` and only setting ``perkey_brightness=5``. Reactive
    effects use ``cfg.brightness`` as their steady-state hardware brightness,
    so the built-in dim profile would still render at the light baseline.

    Keep the migration narrow so it only heals the legacy mismatches and does
    not fight later manual brightness changes.
    """

    prof = _active_profile_name(
        default="",
        log_key="profiles.migrate_builtin_profile_brightness.active_profile",
        log_msg="Failed to resolve active profile during built-in brightness migration",
    )

    target = _builtin_profile_brightness(prof)
    if target is None:
        return False

    effect_brightness = _read_attr_value(
        cfg,
        "effect_brightness",
        log_key="profiles.migrate_builtin_profile_brightness.effect_brightness",
        log_msg="Failed to read effect brightness during built-in profile migration",
    )
    if effect_brightness is _MISSING:
        brightness = _coerce_int(
            _read_attr_value(
                cfg,
                "brightness",
                log_key="profiles.migrate_builtin_profile_brightness.brightness",
                log_msg="Failed to read brightness during built-in profile migration",
            ),
            default=0,
        )
    elif effect_brightness is _READ_FAILED:
        brightness = 0
    else:
        brightness = _coerce_int(effect_brightness, default=0)

    perkey_raw = _read_attr_value(
        cfg,
        "perkey_brightness",
        log_key="profiles.migrate_builtin_profile_brightness.perkey_brightness",
        log_msg="Failed to read per-key brightness during built-in profile migration",
    )
    perkey = _coerce_int(perkey_raw, default=brightness)

    should_migrate = False
    if prof == "dim":
        # Legacy built-in dim used 5. Later builds used 15. The current built-in
        # dim baseline is 10, so repair old persisted dim states when the
        # built-in profile is active.
        should_migrate = perkey in {5, 15} or brightness in {5, 15} or (perkey == 10 and brightness != 10)
    elif prof == "light":
        should_migrate = brightness in {5, 10, 15} and perkey in {5, 10, 15}

    if not should_migrate:
        return False

    brightness_attr = "effect_brightness" if effect_brightness is not _MISSING else "brightness"
    if effect_brightness is _READ_FAILED or not _set_attr_value(
        cfg,
        brightness_attr,
        target,
        log_key=f"profiles.migrate_builtin_profile_brightness.set_{brightness_attr}",
        log_msg=f"Failed to set {brightness_attr} during built-in profile migration",
    ):
        return False

    if perkey_raw is not _MISSING and perkey_raw is not _READ_FAILED:
        _set_attr_value(
            cfg,
            "perkey_brightness",
            target,
            log_key="profiles.migrate_builtin_profile_brightness.set_perkey_brightness",
            log_msg="Failed to set per-key brightness during built-in profile migration",
        )
    return True


def apply_profile_to_config(cfg, colors: Dict[Tuple[int, int], Tuple[int, int, int]]) -> None:
    # Profile-specific defaults.
    prof = _active_profile_name(
        default="",
        log_key="profiles.apply_profile_to_config.active_profile",
        log_msg="Failed to resolve active profile while applying a profile",
    )

    def _set_profile_brightness(value: int) -> None:
        effect_brightness = _read_attr_value(
            cfg,
            "effect_brightness",
            log_key="profiles.apply_profile_to_config.effect_brightness",
            log_msg="Failed to read effect brightness while applying a profile",
        )
        if effect_brightness is _MISSING:
            _set_attr_value(
                cfg,
                "brightness",
                value,
                log_key="profiles.apply_profile_to_config.set_brightness",
                log_msg="Failed to set brightness while applying a profile",
            )
        elif effect_brightness is not _READ_FAILED:
            _set_attr_value(
                cfg,
                "effect_brightness",
                value,
                log_key="profiles.apply_profile_to_config.set_effect_brightness",
                log_msg="Failed to set effect brightness while applying a profile",
            )

        perkey_brightness = _read_attr_value(
            cfg,
            "perkey_brightness",
            log_key="profiles.apply_profile_to_config.perkey_brightness",
            log_msg="Failed to read per-key brightness while applying a profile",
        )
        if perkey_brightness is not _MISSING and perkey_brightness is not _READ_FAILED:
            _set_attr_value(
                cfg,
                "perkey_brightness",
                value,
                log_key="profiles.apply_profile_to_config.set_perkey_brightness",
                log_msg="Failed to set per-key brightness while applying a profile",
            )

    # Ensure visible when activating a per-key profile.
    perkey_brightness = _read_attr_value(
        cfg,
        "perkey_brightness",
        log_key="profiles.apply_profile_to_config.read_perkey_brightness",
        log_msg="Failed to read per-key brightness while applying a profile",
    )
    if perkey_brightness is _MISSING:
        perkey_bri = _coerce_int(
            _read_attr_value(
                cfg,
                "brightness",
                log_key="profiles.apply_profile_to_config.read_brightness",
                log_msg="Failed to read brightness while applying a profile",
            ),
            default=0,
        )
    elif perkey_brightness is _READ_FAILED:
        perkey_bri = 0
    else:
        perkey_bri = _coerce_int(perkey_brightness, default=0)

    if perkey_bri <= 0:
        if hasattr(cfg, "perkey_brightness"):
            cfg.perkey_brightness = 50
        else:
            # Backward-compat for callers that pass in a stub config.
            cfg.brightness = 50

    # Built-in brightness presets should define the baseline keyboard level,
    # not just the per-key backdrop value.  Reactive effects read cfg.brightness
    # as their steady-state hardware brightness, so only changing
    # perkey_brightness leaves the built-in dim profile visually identical to
    # light for reactive typing.
    builtin_target = _builtin_profile_brightness(prof)
    if builtin_target is not None:
        _set_profile_brightness(builtin_target)
    cfg.effect = "perkey"
    cfg.per_key_colors = colors
