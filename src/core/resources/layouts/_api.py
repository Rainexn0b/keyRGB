"""Public API helpers: resolve a layout_id and return its key list."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from .catalog import get_layout_def
from src.core.resources.layout_legends import apply_layout_legend_pack, clear_layout_legend_cache
from src.core.resources.layout_slots import apply_layout_slot_overrides, sanitize_layout_slot_overrides

if TYPE_CHECKING:
    from src.core.resources.layout import KeyDef


def clear_layout_cache() -> None:
    """Clear cached layout resolution and rendered-key lookups."""

    resolve_layout_id.cache_clear()
    _get_layout_keys_cached.cache_clear()
    _get_layout_lookup_cached.cache_clear()
    clear_layout_legend_cache()


@lru_cache(maxsize=16)
def resolve_layout_id(layout_id: str) -> str:
    """Resolve *layout_id* to a concrete, non-``"auto"`` ID.

    When *layout_id* is ``"auto"``, the sysfs detector is invoked.
    If detection returns ``"auto"`` (inconclusive), we default to ``"ansi"``.
    That is deliberately conservative: several laptop AT keyboard nodes expose
    ``KEY_102ND`` even on ANSI hardware, so showing phantom ISO-only keys is a
    worse default than asking the user to opt into a richer layout manually.
    """

    lid = str(layout_id or "auto").strip().lower()
    if lid != "auto":
        # Accept any known ID; unknown IDs fall back to "ansi" via the catalog.
        ld = get_layout_def(lid)
        return ld.layout_id if ld.layout_id != "auto" else "ansi"

    from .detect import detect_physical_layout as _detect

    detected = _detect()
    if detected in ("ansi", "iso", "ks", "abnt", "jis"):
        return detected
    return "ansi"  # inconclusive → conservative default


@lru_cache(maxsize=16)
def _get_layout_keys_cached(layout_id: str) -> tuple["KeyDef", ...]:
    ld = get_layout_def(layout_id)

    # Import here to avoid a circular dependency (layout.py imports from
    # this package for caching, this module imports build_layout for rendering).
    from src.core.resources.layout import build_layout

    return tuple(build_layout(variant=ld.layout_id))


@lru_cache(maxsize=16)
def _get_layout_lookup_cached(layout_id: str) -> tuple[dict[str, "KeyDef"], dict[str, "KeyDef"]]:
    keys = _get_layout_keys_cached(layout_id)
    by_key_id = {str(key.key_id): key for key in keys}
    by_slot_id = {str(key.slot_id): key for key in keys}
    return by_key_id, by_slot_id


def get_layout_keys(
    layout_id: str = "auto",
    *,
    legend_pack_id: str | None = None,
    slot_overrides: dict[str, dict[str, object]] | None = None,
) -> list["KeyDef"]:
    """Return the reference layout key list for *layout_id*.

    Resolves ``"auto"`` via sysfs detection, then delegates to
    :func:`src.core.resources.layout.build_layout`.
    """

    resolved = resolve_layout_id(layout_id)
    keys = apply_layout_legend_pack(_get_layout_keys_cached(resolved), layout_id=resolved, legend_pack_id=legend_pack_id)
    cleaned_overrides = sanitize_layout_slot_overrides(slot_overrides or {}, layout_id=resolved)
    if not cleaned_overrides:
        return keys
    return apply_layout_slot_overrides(
        keys,
        layout_id=resolved,
        legend_pack_id=legend_pack_id,
        slot_overrides=cleaned_overrides,
    )


def slot_id_for_key_id(layout_id: str, key_id: str) -> str | None:
    resolved = resolve_layout_id(layout_id)
    by_key_id, _by_slot_id = _get_layout_lookup_cached(resolved)
    key = by_key_id.get(str(key_id or ""))
    return str(key.slot_id) if key is not None and key.slot_id else None


def key_id_for_slot_id(layout_id: str, slot_id: str) -> str | None:
    resolved = resolve_layout_id(layout_id)
    _by_key_id, by_slot_id = _get_layout_lookup_cached(resolved)
    key = by_slot_id.get(str(slot_id or ""))
    return str(key.key_id) if key is not None else None
