"""UX-04 guided setup integration: cached-only evidence helpers (Tk-free).

Catalog/legend/slot lookups, read-only editor source capture, tray snapshot
parsing, and config writability checks. Everything here reads cached state
only (the ``KEYRGB_PERKEY_PREFLIGHT`` snapshot or the already-selected
backend/open ``kb``); nothing probes hardware. Only the narrow
``OSError``/``RuntimeError``/``TypeError``/``ValueError``/``AttributeError``
boundary is caught; unexpected exceptions propagate.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from keyrgb.core.resources.layout_legends import get_layout_legend_pack_ids, load_layout_legend_pack
from keyrgb.core.resources.layout_slots import get_layout_slot_states
from keyrgb.core.resources.layouts import LAYOUT_CATALOG

from ..model import SetupDraft, SetupSource
from . import integration_types as _types_module


def available_layouts() -> tuple[tuple[str, str], ...]:
    """Return ``(layout_id, label)`` pairs in catalog display order."""

    return tuple((layout.layout_id, layout.label) for layout in LAYOUT_CATALOG)


def legend_pack_choices(layout_id: str) -> list[tuple[str, str]]:
    """Return ``(pack_id, label)`` legend choices for a layout.

    Uses only the public legend APIs. ``"auto"`` (default legends) always
    leads; packs that fail to load keep their id as the label.
    """

    choices: list[tuple[str, str]] = [("auto", "Default legends")]
    seen_labels: set[str] = {"Default legends"}
    try:
        pack_ids = get_layout_legend_pack_ids(layout_id)
    except _types_module._EXPECTED_EVIDENCE_ERRORS:
        return choices
    for pack_id in pack_ids:
        try:
            pack = load_layout_legend_pack(str(pack_id))
            label = str((pack or {}).get("label") or pack_id).strip() or str(pack_id)
        except _types_module._EXPECTED_EVIDENCE_ERRORS:
            label = str(pack_id)
        if label in seen_labels:
            label = f"{label} ({pack_id})"
        seen_labels.add(label)
        choices.append((str(pack_id), label))
    return choices


def optional_slot_states(draft: SetupDraft) -> list[object]:
    """Return optional slot states for the draft layout/legend/overrides."""

    legend_pack_id = draft.legend_pack if draft.legend_pack and draft.legend_pack != "auto" else None
    try:
        return list(
            get_layout_slot_states(
                draft.physical_layout,
                dict(draft.slot_overrides),
                legend_pack_id=legend_pack_id,
            )
        )
    except _types_module._EXPECTED_EVIDENCE_ERRORS:
        return []


def _safe_str(value: object) -> str:
    return str(value) if isinstance(value, str) else ""


def _safe_mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


def _safe_float_mapping(value: object) -> Mapping[str, float] | None:
    if not isinstance(value, Mapping):
        return None
    out: dict[str, float] = {}
    for key, item in value.items():
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        out[str(key)] = float(item)
    return out


def _safe_override_mapping(value: object) -> Mapping[str, Mapping[str, object]] | None:
    if not isinstance(value, Mapping):
        return None
    out: dict[str, Mapping[str, object]] = {}
    for key, item in value.items():
        if not isinstance(item, Mapping):
            return None
        out[str(key)] = item
    return out


def _safe_per_key_mapping(value: object) -> Mapping[str, Mapping[str, float]] | None:
    if not isinstance(value, Mapping):
        return None
    out: dict[str, Mapping[str, float]] = {}
    for key, item in value.items():
        if not isinstance(item, Mapping):
            return None
        slot: dict[str, float] = {}
        for name, number in item.items():
            if isinstance(number, bool) or not isinstance(number, (int, float)):
                return None
            slot[str(name)] = float(number)
        out[str(key)] = slot
    return out


def capture_setup_source(editor: object) -> SetupSource:
    """Copy editor setup fields into a :class:`SetupSource` (read-only)."""

    typed = cast(_types_module._SetupEditorProtocol, editor)
    try:
        legend_raw: object = typed._layout_legend_pack
    except AttributeError:
        legend_raw = ""
    try:
        physical_raw: object = typed._physical_layout
    except AttributeError:
        physical_raw = ""
    raw_config = getattr(editor, "config", None)
    try:
        config_legend = getattr(raw_config, "layout_legend_pack", "")
    except _types_module._EXPECTED_EVIDENCE_ERRORS:
        config_legend = ""
    legend_pack = _safe_str(legend_raw) or _safe_str(config_legend)
    return SetupSource(
        physical_layout=_safe_str(physical_raw) or _safe_str(getattr(raw_config, "physical_layout", "")),
        legend_pack=legend_pack,
        profile_name=_safe_str(getattr(editor, "profile_name", "")),
        slot_overrides=_safe_override_mapping(getattr(editor, "layout_slot_overrides", None)),
        keymap=_safe_mapping(getattr(editor, "keymap", None)),
        layout_tweaks=_safe_float_mapping(getattr(editor, "layout_tweaks", None)),
        per_key_layout_tweaks=_safe_per_key_mapping(getattr(editor, "per_key_layout_tweaks", None)),
    )


def is_tray_managed(env: Mapping[str, str] | None = None) -> bool:
    """Return True when the tray-managed GUI marker is set in *env*."""

    source = os.environ if env is None else env
    try:
        raw = source.get(_types_module.TRAY_MANAGED_ENV_VAR, "")
    except _types_module._EXPECTED_EVIDENCE_ERRORS:
        return False
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _parse_snapshot_view(env: Mapping[str, str]) -> _types_module._SnapshotView:
    try:
        raw = env.get(_types_module.PREFLIGHT_ENV_VAR)
    except _types_module._EXPECTED_EVIDENCE_ERRORS:
        return _types_module._SnapshotView(present=False)
    if not isinstance(raw, str) or not raw.strip():
        return _types_module._SnapshotView(present=False)
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return _types_module._SnapshotView(present=False)
    if not isinstance(payload, dict):
        return _types_module._SnapshotView(present=False)
    try:
        capabilities = {
            "brightness": payload.get("brightness") is True,
            "per_key": payload.get("per_key") is True,
            "color": payload.get("color") is True,
            "hardware_effects": payload.get("hardware_effects") is True,
            "palette": payload.get("palette") is True,
        }
        name = payload.get("backend_name")
        backend_name = str(name).strip() or None if isinstance(name, str) else None
        dimensions = _types_module._validated_dimensions(payload.get("dimensions"))
    except _types_module._EXPECTED_EVIDENCE_ERRORS:
        return _types_module._SnapshotView(present=False)
    return _types_module._SnapshotView(
        present=True,
        capabilities=capabilities,
        backend_name=backend_name,
        dimensions=dimensions,
    )


def snapshot_declares_per_key(env: Mapping[str, str] | None = None) -> bool:
    """Return True when the tray snapshot itself declares per-key support."""

    source = os.environ if env is None else env
    try:
        view = _parse_snapshot_view(dict(source))
    except _types_module._EXPECTED_EVIDENCE_ERRORS:
        return False
    return bool(view.present and view.capabilities and view.capabilities.get("per_key", False))


def config_is_writable(config: object) -> bool:
    """Check config writability without writing anything.

    Fails open (True) when the location cannot be determined: blocking the
    workflow on an undeterminable check would be worse than the preflight
    gate degrading later at persist time, where failures roll back.
    """

    try:
        raw_file = getattr(config, "CONFIG_FILE", None)
        raw_dir = getattr(config, "CONFIG_DIR", None)
    except _types_module._EXPECTED_CONFIG_ERRORS:
        return True
    if raw_file is None and raw_dir is None:
        return True
    try:
        directory = Path(str(raw_file)).parent if raw_file is not None else Path(str(raw_dir))
    except _types_module._EXPECTED_CONFIG_ERRORS:
        return True
    try:
        if not os.access(str(directory), os.W_OK | os.X_OK):
            return False
        if raw_file is not None:
            candidate = Path(str(raw_file))
            if candidate.exists() and not os.access(str(candidate), os.W_OK):
                return False
    except _types_module._EXPECTED_CONFIG_ERRORS:
        return True
    return True
