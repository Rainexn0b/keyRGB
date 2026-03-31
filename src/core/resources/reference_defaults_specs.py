"""Inherited starter-default specs for reference keymaps and layout tweaks.

This models the built-in starter defaults the same way as the visual layouts:
one canonical ANSI base plus small per-layout override sets.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import cast


_RESOURCES_DIR = Path(__file__).resolve().parent
_SPECS_PATH = _RESOURCES_DIR / "reference_defaults_specs.json"


def _copy_jsonish(value: object) -> object:
    return json.loads(json.dumps(value))


def _as_dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


@lru_cache(maxsize=1)
def _load_specs_file() -> dict[str, object]:
    try:
        raw = json.loads(_SPECS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return _as_dict(raw)


def _merge_reference_defaults(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = cast(dict[str, object], _copy_jsonish(base))

    for section_name in ("keymap", "layout_tweaks", "per_key_tweaks"):
        section_value = override.get(section_name)
        if not isinstance(section_value, dict):
            continue
        base_section = _as_dict(merged.get(section_name))
        merged[section_name] = {**base_section, **cast(dict[str, object], _copy_jsonish(section_value))}

    for key in cast(list[str], override.get("remove_keymap_keys") or []):
        keymap = _as_dict(merged.get("keymap"))
        keymap.pop(key, None)
        merged["keymap"] = keymap

    for key in cast(list[str], override.get("remove_per_key_tweak_keys") or []):
        per_key = _as_dict(merged.get("per_key_tweaks"))
        per_key.pop(key, None)
        merged["per_key_tweaks"] = per_key

    return merged


@lru_cache(maxsize=16)
def load_reference_defaults_spec(layout_id: str) -> dict[str, object]:
    layouts = _as_dict(_load_specs_file().get("layouts"))
    requested = str(layout_id or "").strip().lower()
    raw_spec = _as_dict(layouts.get(requested))
    if not raw_spec:
        return {}

    base: dict[str, object] = {}
    extends = raw_spec.get("extends")
    if isinstance(extends, str) and extends.strip():
        parent_id = extends.strip().lower()
        if parent_id != requested:
            base = load_reference_defaults_spec(parent_id)

    return _merge_reference_defaults(base, raw_spec)


def clear_reference_defaults_spec_cache() -> None:
    _load_specs_file.cache_clear()
    load_reference_defaults_spec.cache_clear()


__all__ = ["clear_reference_defaults_spec_cache", "load_reference_defaults_spec"]
