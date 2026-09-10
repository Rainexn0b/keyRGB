"""Guided-session file storage: load, encode, and atomic result writes.

Session schema (all keys optional except the top-level object)::

    {
      "physical_layout": "ansi",
      "legend_pack": "auto",
      "slot_overrides": {"key frm": {"label": "<>"}},
      "keymap": {"esc": [[0, 0]]},
      "layout_tweaks": {"dx": 1.5},
      "per_key_layout_tweaks": {"esc": {"dx": 0.25}},
      "result": {"keymap": {...}, "physical_layout": "ansi", "version": 1}
    }

Aliases accepted for forward compatibility: ``legend_pack_id`` for
``legend_pack``; ``layout_slot_overrides`` for ``slot_overrides``;
``layout_global``/``layout`` for ``layout_tweaks``; ``layout_per_key`` for
``per_key_layout_tweaks``.  Unknown top-level keys are ignored by the loader
and preserved verbatim by the result writer.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from keyrgb.core.profile import profiles
from keyrgb.gui.perkey import profile_management

from .session_protocol import GUIDED_SESSION_RESULT_VERSION, GuidedSession, GuidedSessionError

logger = logging.getLogger(__name__)

# Mirrors the profile keymap JSON shape ("r,c" single string or list) and the
# layout-tweak defaults owned by core profile storage.  Kept local so GUI
# code never imports private core.profile modules; public ``profiles``
# normalizers remain the single source of canonicalization.
_LAYOUT_TWEAK_DEFAULTS: dict[str, float] = {
    "dx": 0.0,
    "dy": 0.0,
    "sx": 1.0,
    "sy": 1.0,
    "inset": 0.06,
}
_LAYOUT_TWEAK_INSET_MIN = 0.0
_LAYOUT_TWEAK_INSET_MAX = 0.20

_SESSION_NORMALIZE_ERRORS = (AttributeError, LookupError, TypeError, ValueError)
_SESSION_WRITE_ERRORS = (OSError, TypeError, ValueError)


def _require_mapping(payload: object, *, field_name: str, path: Path) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise GuidedSessionError(f"guided session {path}: {field_name!r} must be an object")
    return {str(key): value for key, value in payload.items()}


def _validated_layout_id(raw: object, *, path: Path) -> str:
    if raw is None:
        return "auto"
    if isinstance(raw, bool) or not isinstance(raw, str):
        raise GuidedSessionError(f"guided session {path}: 'physical_layout' must be a string")
    return raw.strip() or "auto"


def _validated_legend_pack(raw: object, *, path: Path) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, str):
        raise GuidedSessionError(f"guided session {path}: 'legend_pack' must be a string")
    normalized = raw.strip()
    return normalized or None


def _validated_dimensions(raw: object, *, path: Path, fallback: tuple[int, int]) -> tuple[int, int]:
    if raw is None:
        return fallback
    pair = tuple(raw) if isinstance(raw, list) else raw
    if (
        not isinstance(pair, tuple)
        or len(pair) != 2
        or any(type(value) is not int for value in pair)
        or any(value <= 0 or value > 64 for value in pair)
    ):
        raise GuidedSessionError(f"guided session {path}: 'dimensions' must be a valid [rows, cols] pair")
    return int(pair[0]), int(pair[1])


def load_guided_session(path: str | Path, *, num_rows: int, num_cols: int) -> GuidedSession:
    """Load and narrowly validate a guided-session file without touching profiles.

    Raises :class:`GuidedSessionError` with a clear message when the path is
    missing, unreadable, not JSON, not an object, or structurally invalid.
    Individual out-of-range keymap cells are dropped (matching standalone
    sanitize behavior) rather than failing the whole session.
    """

    session_path = Path(path).expanduser()
    try:
        raw_text = session_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GuidedSessionError(f"guided session {session_path}: cannot read session file: {exc}") from exc
    try:
        payload = json.loads(raw_text)
    except ValueError as exc:
        raise GuidedSessionError(f"guided session {session_path}: invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise GuidedSessionError(f"guided session {session_path}: top-level JSON must be an object")

    effective_rows, effective_cols = _validated_dimensions(
        payload.get("dimensions"),
        path=session_path,
        fallback=(num_rows, num_cols),
    )

    physical_layout = _validated_layout_id(payload.get("physical_layout"), path=session_path)
    legend_pack = _validated_legend_pack(
        payload.get("legend_pack", payload.get("legend_pack_id")),
        path=session_path,
    )

    slot_raw = payload.get("slot_overrides", payload.get("layout_slot_overrides", {}))
    if slot_raw is None:
        slot_raw = {}
    slot_mapping = _require_mapping(slot_raw, field_name="slot_overrides", path=session_path)
    try:
        slot_overrides = profiles.normalize_layout_slot_overrides(slot_mapping, physical_layout=physical_layout)
    except _SESSION_NORMALIZE_ERRORS as exc:
        raise GuidedSessionError(f"guided session {session_path}: invalid 'slot_overrides': {exc}") from exc

    keymap_raw = payload.get("keymap", {})
    if keymap_raw is None:
        keymap_raw = {}
    _require_mapping(keymap_raw, field_name="keymap", path=session_path)
    try:
        normalized_keymap = profiles.normalize_keymap(keymap_raw, physical_layout=physical_layout)
    except _SESSION_NORMALIZE_ERRORS as exc:
        raise GuidedSessionError(f"guided session {session_path}: invalid 'keymap': {exc}") from exc
    keymap = profile_management.sanitize_keymap_cells(
        normalized_keymap,
        num_rows=effective_rows,
        num_cols=effective_cols,
    )

    tweaks_raw = payload.get("layout_tweaks", payload.get("layout_global", payload.get("layout", {})))
    if tweaks_raw is None:
        tweaks_raw = {}
    _require_mapping(tweaks_raw, field_name="layout_tweaks", path=session_path)
    try:
        layout_tweaks = _normalize_layout_tweaks(tweaks_raw)
    except _SESSION_NORMALIZE_ERRORS as exc:
        raise GuidedSessionError(f"guided session {session_path}: invalid 'layout_tweaks': {exc}") from exc

    per_key_raw = payload.get("per_key_layout_tweaks", payload.get("layout_per_key", {}))
    if per_key_raw is None:
        per_key_raw = {}
    _require_mapping(per_key_raw, field_name="per_key_layout_tweaks", path=session_path)
    try:
        per_key_layout_tweaks = profiles.normalize_layout_per_key_tweaks(per_key_raw, physical_layout=physical_layout)
    except _SESSION_NORMALIZE_ERRORS as exc:
        raise GuidedSessionError(f"guided session {session_path}: invalid 'per_key_layout_tweaks': {exc}") from exc

    return GuidedSession(
        source_path=session_path,
        num_rows=effective_rows,
        num_cols=effective_cols,
        physical_layout=physical_layout,
        legend_pack=legend_pack,
        slot_overrides=dict(slot_overrides),
        keymap=dict(keymap),
        layout_tweaks=dict(layout_tweaks),
        per_key_layout_tweaks={str(key): dict(value) for key, value in per_key_layout_tweaks.items()},
    )


def _normalize_layout_tweaks(raw: dict[str, object]) -> dict[str, float]:
    """Fill layout-tweak defaults and clamp, mirroring profile storage shape."""

    out = dict(_LAYOUT_TWEAK_DEFAULTS)
    for key in _LAYOUT_TWEAK_DEFAULTS:
        value = raw.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            out[key] = float(value)
    inset = out.get("inset", _LAYOUT_TWEAK_DEFAULTS["inset"])
    out["inset"] = max(_LAYOUT_TWEAK_INSET_MIN, min(_LAYOUT_TWEAK_INSET_MAX, float(inset)))
    return out


def _encode_keymap_payload(keymap: dict[str, tuple[tuple[int, int], ...]]) -> dict[str, str | list[str]]:
    """Encode a normalized keymap in the profile keymap JSON shape.

    Single-cell identities become one ``"row,col"`` string, multi-cell
    identities become a list; keys are sorted, matching profile saves.
    """

    payload: dict[str, str | list[str]] = {}
    for identity in sorted(keymap):
        cells = keymap[identity]
        if not isinstance(cells, (list, tuple)):
            raise GuidedSessionError(f"cannot encode guided result keymap entry {identity!r}")
        encoded: list[str] = []
        for cell in cells:
            if not isinstance(cell, (list, tuple)) or len(cell) != 2:
                raise GuidedSessionError(f"cannot encode guided result keymap entry {identity!r}")
            row, col = cell
            if isinstance(row, bool) or isinstance(col, bool):
                raise GuidedSessionError(f"cannot encode guided result keymap entry {identity!r}")
            try:
                encoded.append(f"{int(row)},{int(col)}")
            except (TypeError, ValueError) as exc:
                raise GuidedSessionError(f"cannot encode guided result keymap entry {identity!r}: {exc}") from exc
        if encoded:
            payload[str(identity)] = encoded[0] if len(encoded) == 1 else encoded
    return payload


def encode_guided_result_keymap(
    keymap: dict[str, tuple[tuple[int, int], ...]], *, physical_layout: str | None
) -> dict[str, object]:
    """Normalize a keymap exactly like profile saves and encode it for JSON.

    Canonicalization reuses the public ``profiles.normalize_keymap``; only
    the JSON shape encoding is local (see :func:`_encode_keymap_payload`).
    """

    try:
        normalized = profiles.normalize_keymap(dict(keymap or {}), physical_layout=physical_layout)
    except _SESSION_NORMALIZE_ERRORS as exc:
        raise GuidedSessionError(f"cannot normalize guided result keymap: {exc}") from exc
    return dict(_encode_keymap_payload(normalized))


def _atomic_replace_json(path: Path, payload: dict[str, object]) -> None:
    """Atomically replace *path* with *payload* (tmp file + fsync + rename).

    No sibling lock file is created so a parent-supplied temporary directory
    is left otherwise untouched.
    """

    try:
        serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    except (TypeError, ValueError) as exc:
        raise GuidedSessionError(f"guided session {path}: result is not JSON serializable: {exc}") from exc
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise GuidedSessionError(f"guided session {path}: cannot create parent directory: {exc}") from exc
    tmp_fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    fd_open = True
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
            fd_open = False
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except _SESSION_WRITE_ERRORS as exc:
        raise GuidedSessionError(f"guided session {path}: cannot write result: {exc}") from exc
    finally:
        if fd_open:
            try:
                os.close(tmp_fd)
            except OSError:
                logger.debug("guided session %s: failed to close temp file", path, exc_info=True)
        try:
            tmp_path.unlink()
        except OSError:
            pass


def write_guided_result(
    path: str | Path,
    keymap: dict[str, tuple[tuple[int, int], ...]],
    *,
    physical_layout: str | None,
) -> Path:
    """Write the normalized keymap result back into the session file.

    The existing session document is re-read (preserving parent-supplied and
    unknown fields) and only the ``result`` key is replaced, via an atomic
    local write.  Profile data is never touched.  Refuses to overwrite a
    missing or non-object session document.
    """

    session_path = Path(path).expanduser()
    try:
        raw_text = session_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GuidedSessionError(f"guided session {session_path}: cannot read session file: {exc}") from exc
    try:
        payload = json.loads(raw_text)
    except ValueError as exc:
        raise GuidedSessionError(f"guided session {session_path}: invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise GuidedSessionError(f"guided session {session_path}: top-level JSON must be an object")

    result_keymap = encode_guided_result_keymap(keymap, physical_layout=physical_layout)
    payload["result"] = {
        "keymap": result_keymap,
        "physical_layout": physical_layout or "auto",
        "version": GUIDED_SESSION_RESULT_VERSION,
    }
    _atomic_replace_json(session_path, payload)
    return session_path
