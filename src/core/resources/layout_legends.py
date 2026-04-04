"""Layout legend-pack helpers.

Legend packs provide slot_id -> visible label overrides on top of a physical
layout family's built-in fallback labels. This keeps geometry and stable slot
identity separate from locale-facing legends.
"""

from __future__ import annotations

import json
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, cast


if TYPE_CHECKING:
    from src.core.resources.layout import KeyDef


def _resolve_layout_id(layout_id: str) -> str:
    from src.core.resources.layouts import resolve_layout_id

    return resolve_layout_id(layout_id)


_SPECS_PATH = Path(__file__).resolve().with_name("layout_legend_specs.json")


def _copy_jsonish(value: object) -> object:
    return json.loads(json.dumps(value))


def _as_dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


@lru_cache(maxsize=1)
def _load_specs_file() -> dict[str, object]:
    try:
        raw = json.loads(_SPECS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return _as_dict(raw)


def _merge_legend_pack(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = cast(dict[str, object], _copy_jsonish(base))

    labels = _as_dict(merged.get("labels"))
    labels.update(_as_dict(_copy_jsonish(override.get("labels"))))
    merged["labels"] = labels

    for key in cast(list[str], override.get("remove_labels") or []):
        labels.pop(str(key), None)

    for key in ("pack_id", "layout_id", "label"):
        value = override.get(key)
        if isinstance(value, str) and value.strip():
            merged[key] = value.strip()

    return merged


@lru_cache(maxsize=32)
def load_layout_legend_pack(pack_id: str) -> dict[str, object]:
    packs = _as_dict(_load_specs_file().get("packs"))
    requested = str(pack_id or "").strip().lower()
    raw_pack = _as_dict(packs.get(requested))
    if not raw_pack:
        return {}

    base: dict[str, object] = {}
    extends = raw_pack.get("extends")
    if isinstance(extends, str) and extends.strip():
        parent_id = extends.strip().lower()
        if parent_id != requested:
            base = load_layout_legend_pack(parent_id)

    merged = _merge_legend_pack(base, raw_pack)
    merged.setdefault("pack_id", requested)
    return merged


@lru_cache(maxsize=32)
def _fallback_slot_labels(layout_id: str) -> dict[str, str]:
    from src.core.resources.layout import build_layout

    resolved_layout = _resolve_layout_id(layout_id)
    return {
        str(getattr(key, "slot_id", None) or key.key_id): str(key.label)
        for key in build_layout(variant=resolved_layout)
    }


@lru_cache(maxsize=32)
def get_layout_legend_pack_ids(layout_id: str | None = None) -> tuple[str, ...]:
    packs = _as_dict(_load_specs_file().get("packs"))
    resolved_layout = _resolve_layout_id(str(layout_id or "auto")) if layout_id is not None else None

    out: list[str] = []
    for pack_id, raw_pack in packs.items():
        pack = _as_dict(raw_pack)
        pack_layout = str(pack.get("layout_id") or "").strip().lower()
        if resolved_layout is not None and pack_layout and pack_layout != resolved_layout:
            continue
        normalized_pack_id = str(pack_id).strip().lower()
        if normalized_pack_id and normalized_pack_id not in out:
            out.append(normalized_pack_id)
    return tuple(out)


def resolve_layout_legend_pack_id(layout_id: str, legend_pack_id: str | None = None) -> str:
    resolved_layout = _resolve_layout_id(layout_id)
    requested = str(legend_pack_id or "").strip().lower()
    if requested:
        pack = load_layout_legend_pack(requested)
        if pack and str(pack.get("layout_id") or resolved_layout).strip().lower() == resolved_layout:
            return requested

    fallback = f"{resolved_layout}-generic"
    return fallback if load_layout_legend_pack(fallback) else fallback


@lru_cache(maxsize=64)
def get_layout_legend_labels(layout_id: str, legend_pack_id: str | None = None) -> dict[str, str]:
    resolved_layout = _resolve_layout_id(layout_id)
    resolved_pack_id = resolve_layout_legend_pack_id(resolved_layout, legend_pack_id)

    labels = dict(_fallback_slot_labels(resolved_layout))
    pack = load_layout_legend_pack(resolved_pack_id)
    for slot_id, label in _as_dict(pack.get("labels")).items():
        if isinstance(slot_id, str) and isinstance(label, str) and label.strip():
            labels[str(slot_id)] = label.strip()
    return labels


def apply_layout_legend_pack(
    keys: Iterable["KeyDef"],
    *,
    layout_id: str,
    legend_pack_id: str | None = None,
) -> list["KeyDef"]:
    labels = get_layout_legend_labels(layout_id, legend_pack_id)
    out: list["KeyDef"] = []
    for key in keys:
        slot_id = str(getattr(key, "slot_id", None) or key.key_id)
        label = labels.get(slot_id)
        if label is None or label == key.label:
            out.append(key)
            continue
        out.append(cast("KeyDef", replace(key, label=label)))
    return out


def clear_layout_legend_cache() -> None:
    _load_specs_file.cache_clear()
    load_layout_legend_pack.cache_clear()
    _fallback_slot_labels.cache_clear()
    get_layout_legend_pack_ids.cache_clear()
    get_layout_legend_labels.cache_clear()


__all__ = [
    "apply_layout_legend_pack",
    "clear_layout_legend_cache",
    "get_layout_legend_labels",
    "get_layout_legend_pack_ids",
    "load_layout_legend_pack",
    "resolve_layout_legend_pack_id",
]
