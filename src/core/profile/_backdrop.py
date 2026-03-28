from __future__ import annotations

from .json_storage import read_json, write_json_atomic
from .paths import paths_for


def load_backdrop_transparency(name: str | None = None) -> int:
    """Load backdrop transparency for a profile as a percent."""

    raw = read_json(paths_for(name).backdrop_settings)
    if raw is None:
        return 0

    value = raw.get("transparency", 0) if isinstance(raw, dict) else 0
    try:
        out = int(value)
    except Exception:
        out = 0
    return max(0, min(100, out))


def save_backdrop_transparency(transparency: int, name: str | None = None) -> None:
    try:
        value = int(transparency)
    except Exception:
        value = 0
    write_json_atomic(paths_for(name).backdrop_settings, {"transparency": max(0, min(100, value))})