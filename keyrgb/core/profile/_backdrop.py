from __future__ import annotations

from .json_storage import read_json, update_json_atomic
from .paths import paths_for

BACKDROP_MODE_BUILTIN = "builtin"
BACKDROP_MODE_CUSTOM = "custom"
BACKDROP_MODE_NONE = "none"
VALID_BACKDROP_MODES = frozenset({BACKDROP_MODE_BUILTIN, BACKDROP_MODE_CUSTOM, BACKDROP_MODE_NONE})


def _load_backdrop_settings(name: str | None = None) -> dict[str, object]:
    raw = read_json(paths_for(name).backdrop_settings)
    return dict(raw) if isinstance(raw, dict) else {}


def _set_backdrop_setting(name: str | None, *, key: str, value: object) -> None:
    def apply_update(raw: object | None) -> dict[str, object]:
        settings = dict(raw) if isinstance(raw, dict) else {}
        settings[key] = value
        return settings

    update_json_atomic(paths_for(name).backdrop_settings, apply_update)


def normalize_backdrop_mode(mode: object) -> str:
    normalized = str(mode or BACKDROP_MODE_BUILTIN).strip().lower()
    return normalized if normalized in VALID_BACKDROP_MODES else BACKDROP_MODE_BUILTIN


def load_backdrop_mode(name: str | None = None) -> str:
    return normalize_backdrop_mode(_load_backdrop_settings(name).get("mode", BACKDROP_MODE_BUILTIN))


def save_backdrop_mode(mode: object, name: str | None = None) -> None:
    normalized = normalize_backdrop_mode(mode)
    _set_backdrop_setting(name, key="mode", value=normalized)


def _normalize_backdrop_transparency(value: object) -> int:
    try:
        out = int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError, OverflowError):
        out = 0
    return max(0, min(100, out))


def load_backdrop_transparency(name: str | None = None) -> int:
    """Load backdrop transparency for a profile as a percent."""

    value = _load_backdrop_settings(name).get("transparency", 0)
    return _normalize_backdrop_transparency(value)


def save_backdrop_transparency(transparency: object, name: str | None = None) -> None:
    normalized = _normalize_backdrop_transparency(transparency)
    _set_backdrop_setting(name, key="transparency", value=normalized)
