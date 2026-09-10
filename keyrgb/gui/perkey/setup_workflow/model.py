"""UX-04 transactional setup draft core (pure, Tk-free).

Guided first-run setup stages -- physical layout, legend pack, optional slot
overrides, keymap, and global/per-key layout tweaks -- entirely in memory.
Back/Next navigation never persists; only an explicit finish commit writes,
and cancellation discards the draft without any writes.

This module is deliberately not bound to concrete editor internals: callers
supply plain data copied out of the editor, and the later Tk integration
supplies narrow commit callbacks (see ``transaction.py``).

Canonical slot IDs and legacy-loaded keymap payloads are treated as opaque:
they are deep-copied verbatim and never coerced or normalized here.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass, field

__all__ = [
    "KeymapValidation",
    "SetupDraft",
    "SetupSnapshot",
    "SetupSource",
    "cancel_setup",
    "draft_from_snapshot",
    "draft_from_source",
    "snapshot_copy",
    "snapshot_from_source",
    "validate_keymap_for_calibration_skip",
]


@dataclass(frozen=True)
class SetupSource:
    """Plain editor state supplied by the (later) Tk integration layer."""

    physical_layout: str = ""
    legend_pack: str = ""
    profile_name: str = ""
    slot_overrides: Mapping[str, Mapping[str, object]] | None = None
    keymap: Mapping[str, object] | None = None
    layout_tweaks: Mapping[str, float] | None = None
    per_key_layout_tweaks: Mapping[str, Mapping[str, float]] | None = None


@dataclass(frozen=True)
class SetupSnapshot:
    """Stored original state captured when the guided workflow opens.

    The dataclass is frozen, so attribute rebinding is blocked, but the
    contained mappings are plain (mutable) dicts by design: opaque
    legacy-loaded payloads must keep their exact shapes (a recursive
    freeze would turn ``[0, 0]`` lists into tuples and corrupt them).
    Isolation therefore comes from never sharing the stored instance:
    construction deep-copies the source, :func:`draft_from_snapshot`
    deep-copies each field into the draft, and :func:`cancel_setup` plus
    the finish rollback hand out fresh deep copies via
    :func:`snapshot_copy`.
    """

    physical_layout: str = ""
    legend_pack: str = ""
    profile_name: str = ""
    slot_overrides: dict[str, dict[str, object]] = field(default_factory=dict)
    keymap: dict[str, object] = field(default_factory=dict)
    layout_tweaks: dict[str, float] = field(default_factory=dict)
    per_key_layout_tweaks: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class SetupDraft:
    """Mutable copy-on-write working copy; Back/Next only touch this object.

    Holds its own deep copies plus the stored original snapshot for
    cancel/finish-rollback use. The stored original is never shared
    outward: cancel and rollback each receive a fresh deep copy, so a
    misbehaving caller cannot corrupt later retries. No method here
    performs I/O.
    """

    original: SetupSnapshot
    physical_layout: str = ""
    legend_pack: str = ""
    profile_name: str = ""
    slot_overrides: dict[str, dict[str, object]] = field(default_factory=dict)
    keymap: dict[str, object] = field(default_factory=dict)
    layout_tweaks: dict[str, float] = field(default_factory=dict)
    per_key_layout_tweaks: dict[str, dict[str, float]] = field(default_factory=dict)

    def set_physical_layout(self, layout_id: str) -> None:
        if not isinstance(layout_id, str) or not layout_id.strip():
            raise ValueError("physical layout must be a non-empty string")
        self.physical_layout = layout_id

    def set_legend_pack(self, legend_pack_id: str) -> None:
        if not isinstance(legend_pack_id, str) or not legend_pack_id.strip():
            raise ValueError("legend pack must be a non-empty string")
        self.legend_pack = legend_pack_id

    def put_slot_override(self, slot_id: str, override: Mapping[str, object]) -> None:
        _require_slot_id(slot_id)
        if not isinstance(override, Mapping):
            raise TypeError("slot override must be a mapping")
        # Values stay opaque: deep-copy verbatim, never coerced.
        self.slot_overrides[str(slot_id)] = copy.deepcopy(dict(override))

    def remove_slot_override(self, slot_id: str) -> None:
        _require_slot_id(slot_id)
        self.slot_overrides.pop(str(slot_id), None)

    def clear_slot_overrides(self) -> None:
        self.slot_overrides.clear()

    def set_keymap(self, keymap: Mapping[str, object]) -> None:
        if not isinstance(keymap, Mapping):
            raise TypeError("keymap must be a mapping")
        # Keys (canonical slot IDs) and legacy cell payloads stay opaque.
        self.keymap = copy.deepcopy(dict(keymap))

    def set_layout_tweak(self, name: str, value: float) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("layout tweak name must be a non-empty string")
        self.layout_tweaks[str(name)] = _coerce_tweak_value(name, value)

    def set_layout_tweaks(self, tweaks: Mapping[str, float]) -> None:
        if not isinstance(tweaks, Mapping):
            raise TypeError("layout tweaks must be a mapping")
        self.layout_tweaks = {str(name): _coerce_tweak_value(name, value) for name, value in tweaks.items()}

    def put_per_key_layout_tweak(self, slot_id: str, name: str, value: float) -> None:
        _require_slot_id(slot_id)
        if not isinstance(name, str) or not name.strip():
            raise ValueError("per-key tweak name must be a non-empty string")
        slot = self.per_key_layout_tweaks.setdefault(str(slot_id), {})
        slot[str(name)] = _coerce_tweak_value(name, value)

    def remove_per_key_layout_tweak(self, slot_id: str, name: str) -> None:
        slot = self.per_key_layout_tweaks.get(str(slot_id))
        if slot is not None:
            slot.pop(str(name), None)
            if not slot:
                self.per_key_layout_tweaks.pop(str(slot_id), None)

    def set_per_key_layout_tweaks(self, tweaks: Mapping[str, Mapping[str, float]]) -> None:
        if not isinstance(tweaks, Mapping):
            raise TypeError("per-key layout tweaks must be a mapping")
        rebuilt: dict[str, dict[str, float]] = {}
        for slot_id, slot_tweaks in tweaks.items():
            _require_slot_id(slot_id)
            if not isinstance(slot_tweaks, Mapping):
                raise TypeError(f"per-key tweaks for {slot_id!r} must be a mapping")
            rebuilt[str(slot_id)] = {
                str(name): _coerce_tweak_value(f"{slot_id}.{name}", value) for name, value in slot_tweaks.items()
            }
        self.per_key_layout_tweaks = rebuilt


def _require_slot_id(slot_id: object) -> str:
    if not isinstance(slot_id, str) or not slot_id.strip():
        raise ValueError("slot id must be a non-empty string")
    return slot_id


def _coerce_tweak_value(name: object, value: object) -> float:
    # bool is an int subclass; a tweak of True/False is a caller type bug.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"layout tweak {name!r} must be a number")
    return float(value)


def _deep_copy_slot_overrides(source: Mapping[str, Mapping[str, object]]) -> dict[str, dict[str, object]]:
    return copy.deepcopy({slot: dict(override) for slot, override in source.items()})


def _deep_copy_per_key_tweaks(source: Mapping[str, Mapping[str, float]]) -> dict[str, dict[str, float]]:
    return copy.deepcopy({slot: dict(tweaks) for slot, tweaks in source.items()})


def snapshot_from_source(source: SetupSource) -> SetupSnapshot:
    """Capture the stored original snapshot from supplied editor state."""
    return SetupSnapshot(
        physical_layout=str(source.physical_layout or ""),
        legend_pack=str(source.legend_pack or ""),
        profile_name=str(source.profile_name or ""),
        slot_overrides=_deep_copy_slot_overrides(source.slot_overrides or {}),
        keymap=copy.deepcopy(dict(source.keymap or {})),
        layout_tweaks=dict(source.layout_tweaks or {}),
        per_key_layout_tweaks=_deep_copy_per_key_tweaks(source.per_key_layout_tweaks or {}),
    )


def snapshot_copy(snapshot: SetupSnapshot) -> SetupSnapshot:
    """Return a fresh deep copy of the stored original.

    This is the only way the stored instance leaves this module's
    ownership: restore callbacks and cancel callers may mutate what they
    receive without corrupting later rollbacks or cancels.
    """
    return SetupSnapshot(
        physical_layout=snapshot.physical_layout,
        legend_pack=snapshot.legend_pack,
        profile_name=snapshot.profile_name,
        slot_overrides=copy.deepcopy(snapshot.slot_overrides),
        keymap=copy.deepcopy(snapshot.keymap),
        layout_tweaks=dict(snapshot.layout_tweaks),
        per_key_layout_tweaks=copy.deepcopy(snapshot.per_key_layout_tweaks),
    )


def draft_from_snapshot(snapshot: SetupSnapshot) -> SetupDraft:
    """Build an isolated working draft; edits never alias the snapshot."""
    return SetupDraft(
        original=snapshot,
        physical_layout=snapshot.physical_layout,
        legend_pack=snapshot.legend_pack,
        profile_name=snapshot.profile_name,
        slot_overrides=copy.deepcopy(snapshot.slot_overrides),
        keymap=copy.deepcopy(snapshot.keymap),
        layout_tweaks=dict(snapshot.layout_tweaks),
        per_key_layout_tweaks=copy.deepcopy(snapshot.per_key_layout_tweaks),
    )


def draft_from_source(source: SetupSource) -> SetupDraft:
    """Convenience: snapshot the source, then open an isolated draft on it."""
    return draft_from_snapshot(snapshot_from_source(source))


def cancel_setup(draft: SetupDraft) -> SetupSnapshot:
    """Discard the draft; pure because Back/Next/typed stages never write.

    Returns a fresh deep copy of the stored original so the caller can
    re-seed the editor UI if needed; mutating it cannot affect later
    cancels or rollbacks. No callbacks are invoked and nothing is persisted.
    """
    return snapshot_copy(draft.original)


@dataclass(frozen=True)
class KeymapValidation:
    """Result of checking whether calibration may be skipped."""

    valid: bool
    reason: str
    entry_count: int = 0
    cell_count: int = 0


def _is_int(value: object) -> bool:
    # type() check (not isinstance) so bool cells are rejected.
    return type(value) is int


def _is_valid_cell(cell: object, *, rows: int, cols: int) -> bool:
    if not isinstance(cell, (list, tuple)) or len(cell) != 2:
        return False
    row, col = cell[0], cell[1]
    if not _is_int(row) or not _is_int(col):
        return False
    return 0 <= row < rows and 0 <= col < cols


def validate_keymap_for_calibration_skip(
    keymap: Mapping[str, object] | None,
    *,
    rows: int,
    cols: int,
) -> KeymapValidation:
    """Check whether the current keymap may skip the calibration stage.

    Read-only: the keymap is never mutated or coerced, so canonical slot IDs
    and legacy-loaded payloads pass through untouched. Valid requires a
    non-empty mapping whose every value holds at least one cell with all
    cells (row, col) int pairs inside the supplied rows/cols bounds. bool,
    float, string, None, dict, or out-of-range cells invalidate the entry.
    """
    if not _is_int(rows) or not _is_int(cols) or rows <= 0 or cols <= 0:
        return KeymapValidation(valid=False, reason="invalid matrix dimensions")
    if not isinstance(keymap, Mapping) or not keymap:
        return KeymapValidation(valid=False, reason="keymap is empty")

    entry_count = 0
    cell_count = 0
    for key_id, raw_cells in keymap.items():
        entry_count += 1
        cells = _cells_of(raw_cells)
        if not cells:
            return KeymapValidation(
                valid=False,
                reason=f"keymap entry {key_id!r} has no usable cells",
                entry_count=entry_count,
                cell_count=cell_count,
            )
        for cell in cells:
            if not _is_valid_cell(cell, rows=rows, cols=cols):
                return KeymapValidation(
                    valid=False,
                    reason=f"keymap entry {key_id!r} has a malformed or out-of-range cell",
                    entry_count=entry_count,
                    cell_count=cell_count,
                )
        cell_count += len(cells)
    return KeymapValidation(
        valid=True, reason="keymap covers the matrix", entry_count=entry_count, cell_count=cell_count
    )


def _cells_of(raw: object) -> list[object]:
    """Split a legacy keymap value into candidate cells without coercion."""
    if isinstance(raw, (list, tuple)) and len(raw) == 2 and _looks_like_single_cell(raw):
        return [raw]
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return []


def _looks_like_single_cell(raw: list[object] | tuple[object, ...]) -> bool:
    first, second = raw[0], raw[1]
    if isinstance(first, (list, tuple, dict)) or isinstance(second, (list, tuple, dict)):
        return False
    return _is_int(first) or isinstance(first, (float, str))
