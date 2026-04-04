from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from typing import TYPE_CHECKING, Iterable, cast

from .layout_legends import get_layout_legend_labels


if TYPE_CHECKING:
    from src.core.resources.layout import KeyDef


@dataclass(frozen=True)
class LayoutSlotState:
    slot_id: str
    key_id: str
    label: str
    visible: bool
    default_label: str
    default_visible: bool = True


_OPTIONAL_SLOT_KEY_IDS_BY_LAYOUT: dict[str, tuple[str, ...]] = {
    "ansi": ("fn", "menu"),
    "iso": ("fn", "menu", "nonusbackslash", "nonushash", "rctrl"),
    "abnt": ("fn", "menu", "nonusbackslash", "nonushash", "abnt2slash", "rctrl"),
    "ks": ("fn", "menu", "ks_extra", "hanja", "hangul"),
    "jis": ("fn", "menu", "yen", "jp_at", "jp_colon", "jp_ro", "muhenkan", "henkan", "katakana", "rctrl"),
}


def _optional_slot_id(layout_id: str, key_id: str) -> str:
    from .layouts import slot_id_for_key_id

    return str(slot_id_for_key_id(layout_id, key_id) or key_id)


ALL_OPTIONAL_LAYOUT_KEY_IDS: frozenset[str] = frozenset(
    key_id for key_ids in _OPTIONAL_SLOT_KEY_IDS_BY_LAYOUT.values() for key_id in key_ids
)

ALL_OPTIONAL_LAYOUT_SLOT_IDS: frozenset[str] = ALL_OPTIONAL_LAYOUT_KEY_IDS


def _normalized_layout_id(layout_id: str | None) -> str:
    from .layouts import resolve_layout_id

    return resolve_layout_id(str(layout_id or "auto"))


@lru_cache(maxsize=16)
def _optional_slot_defs(layout_id: str) -> tuple[tuple[str, str], ...]:
    resolved_layout = _normalized_layout_id(layout_id)
    return tuple(
        (_optional_slot_id(resolved_layout, key_id), str(key_id))
        for key_id in _OPTIONAL_SLOT_KEY_IDS_BY_LAYOUT.get(resolved_layout, ())
    )


@lru_cache(maxsize=1)
def _all_optional_slot_ids() -> frozenset[str]:
    return frozenset(
        slot_id for layout_id in _OPTIONAL_SLOT_KEY_IDS_BY_LAYOUT for slot_id, _key_id in _optional_slot_defs(layout_id)
    )


@lru_cache(maxsize=32)
def _default_slot_labels(layout_id: str, legend_pack_id: str | None = None) -> dict[str, str]:
    resolved_layout = _normalized_layout_id(layout_id)
    key_map = get_layout_legend_labels(resolved_layout, legend_pack_id)
    return {slot_id: str(key_map.get(slot_id, key_id)) for slot_id, key_id in _optional_slot_defs(resolved_layout)}


def get_layout_slot_key_ids(layout_id: str | None) -> tuple[str, ...]:
    return tuple(slot_id for slot_id, _key_id in _optional_slot_defs(_normalized_layout_id(layout_id)))


def sanitize_layout_slot_overrides(raw: object, *, layout_id: str | None = None) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    if not isinstance(raw, dict):
        return out

    allowed_slot_ids = _all_optional_slot_ids()
    legacy_to_slot: dict[str, str] = {}
    if layout_id is not None:
        optional_defs = _optional_slot_defs(_normalized_layout_id(layout_id))
        allowed_slot_ids = frozenset(slot_id for slot_id, _key_id in optional_defs)
        legacy_to_slot = {key_id: slot_id for slot_id, key_id in optional_defs}

    for slot_id, payload in raw.items():
        if not isinstance(slot_id, str) or not isinstance(payload, dict):
            continue

        normalized_slot_id = str(slot_id)
        if normalized_slot_id not in allowed_slot_ids:
            normalized_slot_id = legacy_to_slot.get(normalized_slot_id, "")
        if normalized_slot_id not in allowed_slot_ids:
            continue

        cleaned: dict[str, object] = {}

        visible = payload.get("visible")
        if isinstance(visible, bool):
            cleaned["visible"] = visible

        label = payload.get("label")
        if isinstance(label, str):
            normalized_label = label.strip()
            if normalized_label:
                cleaned["label"] = normalized_label

        if cleaned:
            out[normalized_slot_id] = cleaned

    return out


def get_layout_slot_states(
    layout_id: str | None,
    slot_overrides: dict[str, dict[str, object]] | None = None,
    *,
    legend_pack_id: str | None = None,
) -> list[LayoutSlotState]:
    resolved_layout = _normalized_layout_id(layout_id)
    default_labels = _default_slot_labels(resolved_layout, legend_pack_id)
    overrides = sanitize_layout_slot_overrides(slot_overrides or {}, layout_id=resolved_layout)

    states: list[LayoutSlotState] = []
    for slot_id, key_id in _optional_slot_defs(resolved_layout):
        default_label = str(default_labels.get(slot_id, key_id))
        override = overrides.get(slot_id, {})
        visible = True if override.get("visible") is not False else False
        label_value = override.get("label")
        label = str(label_value).strip() if isinstance(label_value, str) and str(label_value).strip() else default_label
        states.append(
            LayoutSlotState(
                slot_id=slot_id,
                key_id=key_id,
                label=label,
                visible=visible,
                default_label=default_label,
            )
        )
    return states


def apply_layout_slot_overrides(
    keys: Iterable["KeyDef"],
    *,
    layout_id: str | None,
    legend_pack_id: str | None = None,
    slot_overrides: dict[str, dict[str, object]] | None = None,
) -> list["KeyDef"]:
    states_by_id = {
        state.slot_id: state
        for state in get_layout_slot_states(layout_id, slot_overrides, legend_pack_id=legend_pack_id)
    }
    out: list["KeyDef"] = []
    for key in keys:
        state = states_by_id.get(str(getattr(key, "slot_id", None) or key.key_id))
        if state is not None and not state.visible:
            continue
        if state is not None and state.label != key.label:
            out.append(cast("KeyDef", replace(key, label=state.label)))
            continue
        out.append(key)
    return out


def clear_layout_slot_cache() -> None:
    _all_optional_slot_ids.cache_clear()
    _optional_slot_defs.cache_clear()
    _default_slot_labels.cache_clear()


__all__ = [
    "ALL_OPTIONAL_LAYOUT_SLOT_IDS",
    "LayoutSlotState",
    "apply_layout_slot_overrides",
    "clear_layout_slot_cache",
    "get_layout_slot_key_ids",
    "get_layout_slot_states",
    "sanitize_layout_slot_overrides",
]
