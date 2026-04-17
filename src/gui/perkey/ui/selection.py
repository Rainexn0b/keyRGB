from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast


class _KeyLookupOwner(Protocol):
    def _key_id_for_slot_id(self, slot_id: str) -> str | None: ...


class _SlotLookupOwner(Protocol):
    def _slot_id_for_key_id(self, key_id: str) -> str | None: ...


class _SelectSlotIdOwner(Protocol):
    select_slot_id: Callable[[str], None]


class _SelectKeyIdOwner(Protocol):
    select_key_id: Callable[[str], None]


def _key_id_for_slot_id_or_none(editor: object, slot_id: str | None) -> str | None:
    if slot_id is None:
        return None
    try:
        key_lookup = cast(_KeyLookupOwner, editor)._key_id_for_slot_id
    except AttributeError:
        return None
    return key_lookup(slot_id) if callable(key_lookup) else None


def _slot_id_for_key_id_or_none(editor: object, key_id: str | None) -> str | None:
    if key_id is None:
        return None
    try:
        slot_lookup = cast(_SlotLookupOwner, editor)._slot_id_for_key_id
    except AttributeError:
        return None
    return slot_lookup(key_id) if callable(slot_lookup) else None


def _select_slot_id_if_present(editor: object, slot_id: str) -> bool:
    try:
        select_slot = cast(_SelectSlotIdOwner, editor).select_slot_id
    except AttributeError:
        return False
    if not callable(select_slot):
        return False
    select_slot(slot_id)
    return True


def _select_key_id_if_present(editor: object, key_id: str) -> bool:
    try:
        select_key = cast(_SelectKeyIdOwner, editor).select_key_id
    except AttributeError:
        return False
    if not callable(select_key):
        return False
    select_key(key_id)
    return True


def select_visible_identity(editor: object, *, slot_id: str | None = None, key_id: str | None = None) -> bool:
    if slot_id and _select_slot_id_if_present(editor, str(slot_id)):
        return True

    resolved_key_id = str(key_id) if key_id else None
    if resolved_key_id is None and slot_id:
        key_value = _key_id_for_slot_id_or_none(editor, slot_id)
        if key_value:
            resolved_key_id = str(key_value)

    if resolved_key_id is None:
        return False

    resolved_slot_id = _slot_id_for_key_id_or_none(editor, resolved_key_id)
    if resolved_slot_id and _select_slot_id_if_present(editor, str(resolved_slot_id)):
        return True

    if _select_key_id_if_present(editor, str(resolved_key_id)):
        return True

    return False
