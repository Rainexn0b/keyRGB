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


def _read_json_file(path: Path) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return _as_dict(raw)


def _layouts_from_file(path: Path) -> dict[str, object]:
    return _as_dict(_read_json_file(path).get("layouts"))


def _load_split_specs(manifest: dict[str, object]) -> dict[str, object]:
    base_dir_name = str(manifest.get("base_dir") or "reference_defaults_specs").strip()
    if not base_dir_name:
        return {}

    base_dir = _RESOURCES_DIR / base_dir_name
    meta_layouts = _layouts_from_file(base_dir / str(manifest.get("meta") or "meta.json"))
    keymap_layouts = _layouts_from_file(base_dir / str(manifest.get("keymaps") or "keymaps.json"))
    layout_tweak_layouts = _layouts_from_file(base_dir / str(manifest.get("layout_tweaks") or "layout_tweaks.json"))
    per_key_dir = base_dir / str(manifest.get("per_key_tweaks_dir") or "per_key_tweaks")

    layout_ids = set(meta_layouts) | set(keymap_layouts) | set(layout_tweak_layouts)
    if per_key_dir.is_dir():
        layout_ids.update(path.stem for path in per_key_dir.glob("*.json"))

    layouts: dict[str, object] = {}
    for layout_id in sorted(str(layout_id) for layout_id in layout_ids):
        spec = _as_dict(_copy_jsonish(meta_layouts.get(layout_id)))

        keymap = _as_dict(keymap_layouts.get(layout_id))
        if keymap:
            spec["keymap"] = keymap

        layout_tweaks = _as_dict(layout_tweak_layouts.get(layout_id))
        if layout_tweaks:
            spec["layout_tweaks"] = layout_tweaks

        per_key_payload = _read_json_file(per_key_dir / f"{layout_id}.json")
        per_key_tweaks = _as_dict(per_key_payload.get("per_key_tweaks"))
        if per_key_tweaks:
            spec["per_key_tweaks"] = per_key_tweaks

        if spec:
            layouts[layout_id] = spec

    return {"layouts": layouts}


@lru_cache(maxsize=1)
def _load_specs_file() -> dict[str, object]:
    raw = _read_json_file(_SPECS_PATH)
    if _as_dict(raw.get("layouts")):
        return raw
    if str(raw.get("schema") or "") == "split-reference-defaults-v1":
        return _load_split_specs(raw)
    return {}


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
