from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from typing import TYPE_CHECKING, Iterable, cast


if TYPE_CHECKING:
    from src.core.resources.layout import KeyDef


@dataclass(frozen=True)
class LayoutSlotState:
    key_id: str
    label: str
    visible: bool
    default_label: str
    default_visible: bool = True


_OPTIONAL_SLOT_IDS_BY_LAYOUT: dict[str, tuple[str, ...]] = {
    "ansi": ("fn", "menu"),
    "iso": ("fn", "menu", "nonusbackslash", "nonushash", "rctrl"),
    "abnt": ("fn", "menu", "nonusbackslash", "nonushash", "abnt2slash", "rctrl"),
    "ks": ("fn", "menu", "ks_extra", "hanja", "hangul"),
    "jis": ("fn", "menu", "yen", "jp_at", "jp_colon", "jp_ro", "muhenkan", "henkan", "katakana", "rctrl"),
}

ALL_OPTIONAL_LAYOUT_SLOT_IDS: frozenset[str] = frozenset(
    key_id for key_ids in _OPTIONAL_SLOT_IDS_BY_LAYOUT.values() for key_id in key_ids
)


def _normalized_layout_id(layout_id: str | None) -> str:
    from .layouts import resolve_layout_id

    return resolve_layout_id(str(layout_id or "auto"))


@lru_cache(maxsize=16)
def _default_slot_labels(layout_id: str) -> dict[str, str]:
    from .layout import build_layout

    resolved_layout = _normalized_layout_id(layout_id)
    key_map = {key.key_id: key.label for key in build_layout(variant=resolved_layout)}
    return {
        key_id: str(key_map.get(key_id, key_id)) for key_id in _OPTIONAL_SLOT_IDS_BY_LAYOUT.get(resolved_layout, ())
    }


def get_layout_slot_key_ids(layout_id: str | None) -> tuple[str, ...]:
    return _OPTIONAL_SLOT_IDS_BY_LAYOUT.get(_normalized_layout_id(layout_id), ())


def sanitize_layout_slot_overrides(raw: object) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    if not isinstance(raw, dict):
        return out

    for key_id, payload in raw.items():
        if not isinstance(key_id, str) or key_id not in ALL_OPTIONAL_LAYOUT_SLOT_IDS or not isinstance(payload, dict):
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
            out[key_id] = cleaned

    return out


def get_layout_slot_states(
    layout_id: str | None,
    slot_overrides: dict[str, dict[str, object]] | None = None,
) -> list[LayoutSlotState]:
    resolved_layout = _normalized_layout_id(layout_id)
    default_labels = _default_slot_labels(resolved_layout)
    overrides = sanitize_layout_slot_overrides(slot_overrides or {})

    states: list[LayoutSlotState] = []
    for key_id in _OPTIONAL_SLOT_IDS_BY_LAYOUT.get(resolved_layout, ()):
        default_label = str(default_labels.get(key_id, key_id))
        override = overrides.get(key_id, {})
        visible = True if override.get("visible") is not False else False
        label_value = override.get("label")
        label = str(label_value).strip() if isinstance(label_value, str) and str(label_value).strip() else default_label
        states.append(
            LayoutSlotState(
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
    slot_overrides: dict[str, dict[str, object]] | None = None,
) -> list["KeyDef"]:
    states_by_id = {state.key_id: state for state in get_layout_slot_states(layout_id, slot_overrides)}
    out: list["KeyDef"] = []
    for key in keys:
        state = states_by_id.get(key.key_id)
        if state is not None and not state.visible:
            continue
        if state is not None and state.label != key.label:
            out.append(cast("KeyDef", replace(key, label=state.label)))
            continue
        out.append(key)
    return out


def clear_layout_slot_cache() -> None:
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
