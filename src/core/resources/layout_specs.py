"""Declarative visual layout specs with lightweight inheritance.

These specs describe the standard keyboard families KeyRGB can render in the
per-key editor and calibrator. They intentionally model the *visual* layout
only; device-specific matrix mappings remain profile calibration data.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import cast


_SPECS_PATH = Path(__file__).resolve().with_name("layout_specs.json")


def _copy_jsonish(value: object) -> object:
    return json.loads(json.dumps(value))


@lru_cache(maxsize=1)
def _load_specs_file() -> dict[str, object]:
    try:
        raw = json.loads(_SPECS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return cast(dict[str, object], raw) if isinstance(raw, dict) else {}


def _merge_layout_spec(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = cast(dict[str, object], _copy_jsonish(base))
    for key, value in override.items():
        if key == "extends":
            continue
        if key == "rows" and isinstance(value, dict):
            rows = cast(dict[str, object], merged.get("rows") if isinstance(merged.get("rows"), dict) else {})
            out_rows = dict(rows)
            for row_name, row_items in value.items():
                out_rows[str(row_name)] = _copy_jsonish(row_items)
            merged["rows"] = out_rows
            continue
        if key == "special_keys" and isinstance(value, list):
            merged["special_keys"] = _copy_jsonish(value)
            continue
        merged[str(key)] = _copy_jsonish(value)
    return merged


@lru_cache(maxsize=16)
def load_layout_spec(layout_id: str) -> dict[str, object]:
    layouts = _load_specs_file().get("layouts")
    if not isinstance(layouts, dict):
        return {}

    requested = str(layout_id or "").strip().lower()
    raw_spec = layouts.get(requested)
    if not isinstance(raw_spec, dict):
        return {}

    extends = raw_spec.get("extends")
    if isinstance(extends, str) and extends.strip():
        parent_id = extends.strip().lower()
        if parent_id == requested:
            return _merge_layout_spec({}, raw_spec)
        return _merge_layout_spec(load_layout_spec(parent_id), raw_spec)

    return cast(dict[str, object], _copy_jsonish(raw_spec))


def clear_layout_spec_cache() -> None:
    _load_specs_file.cache_clear()
    load_layout_spec.cache_clear()


__all__ = ["clear_layout_spec_cache", "load_layout_spec"]
