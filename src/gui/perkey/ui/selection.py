from __future__ import annotations

from typing import Any


def select_visible_identity(editor: Any, *, slot_id: str | None = None, key_id: str | None = None) -> bool:
    select_slot = getattr(editor, "select_slot_id", None)
    if slot_id and callable(select_slot):
        select_slot(str(slot_id))
        return True

    resolved_key_id = str(key_id) if key_id else None
    if resolved_key_id is None and slot_id:
        key_lookup = getattr(editor, "_key_id_for_slot_id", None)
        if callable(key_lookup):
            key_value = key_lookup(slot_id)
            if key_value:
                resolved_key_id = str(key_value)

    if resolved_key_id is None:
        return False

    slot_lookup = getattr(editor, "_slot_id_for_key_id", None)
    resolved_slot_id = slot_lookup(resolved_key_id) if callable(slot_lookup) else None
    if resolved_slot_id and callable(select_slot):
        select_slot(str(resolved_slot_id))
        return True

    select_key = getattr(editor, "select_key_id", None)
    if callable(select_key):
        select_key(str(resolved_key_id))
        return True

    return False
