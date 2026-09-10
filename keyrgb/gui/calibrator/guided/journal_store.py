"""Preview journal storage: atomic record, load, and clear helpers.

Lock safety: journal writes/reads go through the shared
``json_storage`` helpers, which serialize JSON operations under the
config-level ``.profile-json.lock`` (fcntl) and replace files atomically
(tmp + fsync + rename).  All failure paths are best-effort with narrow
exception handling and logging; a broken journal must never prevent
calibration from starting.
"""

from __future__ import annotations

import logging
from pathlib import Path

from keyrgb.core.profile.json_storage import read_json_strict, write_json_atomic

from .journal_model import (
    PREVIEW_JOURNAL_FILENAME,
    PREVIEW_JOURNAL_VERSION,
    PreviewConfigProtocol,
    PreviewSnapshot,
    _is_int,
    _validated_color,
    validate_journal_payload,
)

logger = logging.getLogger(__name__)

_JOURNAL_READ_ERRORS = (OSError, ValueError, TypeError, AttributeError, LookupError)
_JOURNAL_WRITE_ERRORS = (OSError, ValueError, TypeError, AttributeError, LookupError)
_JOURNAL_CLEAR_ERRORS = (OSError,)


def journal_path(config_dir: str | Path) -> Path:
    """Return the calibrator preview journal path owned by this module."""

    return Path(config_dir) / PREVIEW_JOURNAL_FILENAME


def config_dir_of(cfg: object) -> Path | None:
    """Return the journal-owning config dir, or ``None`` when unavailable.

    Narrow legacy-fake compatibility shim: production ``Config`` always
    carries ``CONFIG_DIR``, but duck-typed test doubles may not, and such a
    config cannot own a journal.  This is the only untyped attribute read in
    this module; everything else goes through :class:`PreviewConfigProtocol`.
    """

    raw = getattr(cfg, "CONFIG_DIR", None)
    if isinstance(raw, Path):
        return raw
    if isinstance(raw, str) and raw.strip():
        return Path(raw)
    return None


def _serialize_per_key_map(raw: object) -> dict[str, list[int]]:
    """Serialize an in-memory ``{(row, col): (r, g, b)}`` map to JSON form."""

    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise TypeError(f"invalid per-key map: {type(raw).__name__}")
    out: dict[str, list[int]] = {}
    for cell, color in raw.items():
        if not isinstance(cell, (list, tuple)) or len(cell) != 2:
            raise TypeError(f"invalid per-key cell: {cell!r}")
        row, col = cell
        if not _is_int(row) or not _is_int(col):
            raise TypeError(f"invalid per-key cell: {cell!r}")
        validated = _validated_color(color)
        if validated is None:
            raise TypeError(f"invalid per-key color: {color!r}")
        out[f"{row},{col}"] = [validated[0], validated[1], validated[2]]
    return out


def snapshot_preview_state(cfg: PreviewConfigProtocol) -> dict[str, object]:
    """Snapshot the lighting fields the calibrator preview mutates."""

    try:
        per_key = _serialize_per_key_map(cfg.per_key_colors or {})
    except (AttributeError, TypeError, ValueError) as exc:
        logger.debug("calibrator preview journal: cannot serialize per-key map; snapshotting empty map", exc_info=exc)
        per_key = {}
    try:
        color = _validated_color(cfg.color or (255, 0, 0))
    except (AttributeError, TypeError, ValueError) as exc:
        logger.debug("calibrator preview journal: cannot serialize color; snapshotting default", exc_info=exc)
        color = None
    try:
        effect = str(cfg.effect or "rainbow")
        speed = int(cfg.speed)
        brightness = int(cfg.brightness)
    except (AttributeError, TypeError, ValueError) as exc:
        logger.debug("calibrator preview journal: cannot serialize scalars; snapshotting defaults", exc_info=exc)
        return {
            "version": PREVIEW_JOURNAL_VERSION,
            "effect": "rainbow",
            "speed": 5,
            "brightness": 25,
            "color": [255, 0, 0],
            "per_key_colors": {},
        }
    return {
        "version": PREVIEW_JOURNAL_VERSION,
        "effect": effect,
        "speed": speed,
        "brightness": brightness,
        "color": [color[0], color[1], color[2]] if color is not None else [255, 0, 0],
        "per_key_colors": per_key,
    }


def write_preview_journal(config_dir: str | Path, snapshot: dict[str, object]) -> bool:
    """Atomically record a preview snapshot; never raises on I/O failure."""

    try:
        write_json_atomic(journal_path(config_dir), dict(snapshot))
    except _JOURNAL_WRITE_ERRORS as exc:
        logger.debug("calibrator preview journal: failed to record snapshot", exc_info=exc)
        return False
    return True


def clear_preview_journal(config_dir: str | Path) -> bool:
    """Remove the journal after an orderly restore; report success."""

    try:
        journal_path(config_dir).unlink()
    except FileNotFoundError:
        return True
    except _JOURNAL_CLEAR_ERRORS as exc:
        logger.debug("calibrator preview journal: failed to remove journal", exc_info=exc)
        return False
    return True


def load_preview_snapshot(config_dir: str | Path) -> PreviewSnapshot | None:
    """Load a retained valid snapshot without applying or deleting it."""

    path = journal_path(config_dir)
    if not path.exists():
        return None
    try:
        return validate_journal_payload(read_json_strict(path))
    except _JOURNAL_READ_ERRORS as exc:
        logger.debug("calibrator preview journal: failed to load retained snapshot", exc_info=exc)
        return None
