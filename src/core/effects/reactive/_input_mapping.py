from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from src.core.resources.layouts import key_id_for_slot_id, slot_id_for_key_id

from ._evdev_specs import SPECIAL_KEY_NAMES

Key: TypeAlias = tuple[int, int]
KeyCells: TypeAlias = tuple[Key, ...]
KeyNameToKeyId: TypeAlias = Callable[[str], str | None]


def evdev_key_name_to_key_id(name: str) -> str | None:
    if not name:
        return None
    normalized_name = str(name).strip().upper()
    if normalized_name.startswith("KEY_"):
        normalized_name = normalized_name[4:]

    if normalized_name in SPECIAL_KEY_NAMES:
        return SPECIAL_KEY_NAMES[normalized_name]

    if normalized_name.startswith("F") and normalized_name[1:].isdigit():
        return normalized_name.lower()

    if normalized_name.startswith("KP") and normalized_name[2:].isdigit():
        return f"num{normalized_name[2:]}"

    if len(normalized_name) == 1 and ("A" <= normalized_name <= "Z" or "0" <= normalized_name <= "9"):
        return normalized_name.lower()

    return None


def key_id_to_slot_id(key_id: str, *, physical_layout: str = "auto") -> str:
    normalized_key_id = str(key_id).strip().lower()
    return str(slot_id_for_key_id(physical_layout, normalized_key_id) or normalized_key_id)


def normalize_key_cells(raw_cells: object) -> KeyCells:
    if isinstance(raw_cells, str):
        if "," not in raw_cells:
            return ()
        row_text, col_text = raw_cells.split(",", 1)
        try:
            return ((int(row_text), int(col_text)),)
        except (TypeError, ValueError):
            return ()

    if isinstance(raw_cells, (list, tuple)) and len(raw_cells) == 2:
        first, second = raw_cells
        if not isinstance(first, (list, tuple, dict)) and not isinstance(second, (list, tuple, dict)):
            try:
                return ((int(first), int(second)),)
            except (TypeError, ValueError):
                return ()

    if not isinstance(raw_cells, (list, tuple)):
        return ()

    out: list[Key] = []
    for cell in raw_cells:
        normalized = normalize_key_cells(cell)
        if not normalized:
            continue
        key = normalized[0]
        if key not in out:
            out.append(key)
    return tuple(out)


def normalize_profile_slot_identity(
    raw_identity: object,
    *,
    physical_layout: str = "auto",
    key_name_to_key_id: KeyNameToKeyId,
) -> str:
    normalized_identity = str(raw_identity or "").strip()
    if key_id_for_slot_id(physical_layout, normalized_identity):
        return normalized_identity.lower()

    mapped_key_id = key_name_to_key_id(normalized_identity) or normalized_identity.lower()
    return key_id_to_slot_id(mapped_key_id, physical_layout=physical_layout).lower()
