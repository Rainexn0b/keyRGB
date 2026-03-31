from __future__ import annotations

from pathlib import Path

from src.core.config.paths import config_dir
from src.core.profile.json_storage import read_json, write_json_atomic
from src.core.resources.layout import resolve_physical_layout
from src.core.resources.layout_slots import get_layout_slot_key_ids, sanitize_layout_slot_overrides


def layout_slots_path() -> Path:
    return config_dir() / "layout_slots.json"


def _filter_layout_slot_overrides(
    physical_layout: str | None,
    raw: object,
) -> dict[str, dict[str, object]]:
    cleaned = sanitize_layout_slot_overrides(raw)
    allowed_key_ids = set(get_layout_slot_key_ids(physical_layout))
    return {key_id: dict(payload) for key_id, payload in cleaned.items() if key_id in allowed_key_ids}


def _load_all_layout_slot_overrides() -> dict[str, dict[str, dict[str, object]]]:
    raw = read_json(layout_slots_path())
    if not isinstance(raw, dict):
        return {}

    raw_layouts = raw.get("layouts", raw)
    if not isinstance(raw_layouts, dict):
        return {}

    out: dict[str, dict[str, dict[str, object]]] = {}
    for layout_id, payload in raw_layouts.items():
        if not isinstance(layout_id, str):
            continue
        resolved_layout = resolve_physical_layout(layout_id)
        filtered = _filter_layout_slot_overrides(resolved_layout, payload)
        if filtered:
            out[resolved_layout] = filtered
    return out


def _load_legacy_profile_slot_overrides(
    physical_layout: str | None,
    *,
    legacy_profile_name: str | None,
) -> dict[str, dict[str, object]]:
    if not isinstance(legacy_profile_name, str) or not legacy_profile_name.strip():
        return {}

    from src.core.profile.paths import safe_profile_name

    legacy_path = config_dir() / "profiles" / safe_profile_name(legacy_profile_name) / "layout_slots.json"
    return _filter_layout_slot_overrides(physical_layout, read_json(legacy_path))


def load_layout_slot_overrides(
    physical_layout: str | None,
    *,
    legacy_profile_name: str | None = None,
) -> dict[str, dict[str, object]]:
    resolved_layout = resolve_physical_layout(physical_layout or "auto")
    all_layouts = _load_all_layout_slot_overrides()
    current = all_layouts.get(resolved_layout)
    if current is not None:
        return dict(current)

    migrated = _load_legacy_profile_slot_overrides(
        resolved_layout,
        legacy_profile_name=legacy_profile_name,
    )
    if migrated:
        save_layout_slot_overrides(resolved_layout, migrated)
        return migrated

    return {}


def save_layout_slot_overrides(
    physical_layout: str | None,
    slot_overrides: dict[str, dict[str, object]] | None,
) -> dict[str, dict[str, object]]:
    resolved_layout = resolve_physical_layout(physical_layout or "auto")
    all_layouts = _load_all_layout_slot_overrides()
    cleaned = _filter_layout_slot_overrides(resolved_layout, slot_overrides or {})

    if cleaned:
        all_layouts[resolved_layout] = cleaned
    else:
        all_layouts.pop(resolved_layout, None)

    payload = {
        "layouts": {
            layout_id: {key_id: dict(layout_payload[key_id]) for key_id in sorted(layout_payload)}
            for layout_id, layout_payload in sorted(all_layouts.items())
        }
    }
    write_json_atomic(layout_slots_path(), payload)
    return cleaned


__all__ = [
    "layout_slots_path",
    "load_layout_slot_overrides",
    "save_layout_slot_overrides",
]
