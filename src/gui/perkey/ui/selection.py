from __future__ import annotations

from typing import Any


def _key_id_for_slot_id_or_none(editor: Any, slot_id: str | None) -> str | None:
    if slot_id is None:
        return None
    try:
        key_lookup = editor._key_id_for_slot_id
    except AttributeError:
        return None
    return key_lookup(slot_id) if callable(key_lookup) else None


def _slot_id_for_key_id_or_none(editor: Any, key_id: str | None) -> str | None:
    if key_id is None:
        return None
    try:
        slot_lookup = editor._slot_id_for_key_id
    except AttributeError:
        return None
    return slot_lookup(key_id) if callable(slot_lookup) else None


def select_visible_identity(editor: Any, *, slot_id: str | None = None, key_id: str | None = None) -> bool:
    select_slot = getattr(editor, "select_slot_id", None)
    if slot_id and callable(select_slot):
        select_slot(str(slot_id))
        return True

    resolved_key_id = str(key_id) if key_id else None
    if resolved_key_id is None and slot_id:
        key_value = _key_id_for_slot_id_or_none(editor, slot_id)
        if key_value:
            resolved_key_id = str(key_value)

    if resolved_key_id is None:
        return False

    resolved_slot_id = _slot_id_for_key_id_or_none(editor, resolved_key_id)
    if resolved_slot_id and callable(select_slot):
        select_slot(str(resolved_slot_id))
        return True

    select_key = getattr(editor, "select_key_id", None)
    if callable(select_key):
        select_key(str(resolved_key_id))
        return True

    return False
