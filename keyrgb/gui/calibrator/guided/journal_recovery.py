"""Preview journal recovery: deterministic automatic restore of stale journals.

Recovery design (documented choice): before the first preview mutation of a
session, the original values are recorded atomically under ``config_dir``;
an orderly restore removes the journal.  When a stale journal is found at
the next calibrator launch, it is restored deterministically and
automatically with a clear logged diagnostic.  An interactive prompt was
deliberately rejected: the calibrator is a short-lived tool that may be
launched unattended (e.g. from a parent guided flow), so blocking on user
input could strand the user's lighting in probe state indefinitely.  The
journal only ever restores lighting fields that this calibrator changed;
it never touches profiles, keymaps, or layout files, and it never uploads
anything.

Failure semantics: the journal schema (including ``version``) is narrowly
validated *before* any assignment, so a malformed journal is logged and
discarded without changing config.  A valid journal whose restore only
partially succeeds is *retained* for a later retry instead of being
cleared.  Only a fully successful restore removes the journal.
"""

from __future__ import annotations

import logging

from .journal_model import PreviewConfigProtocol, PreviewSnapshot, validate_journal_payload
from .journal_store import clear_preview_journal, config_dir_of, journal_path

logger = logging.getLogger(__name__)

_JOURNAL_READ_ERRORS = (OSError, ValueError, TypeError, AttributeError, LookupError)
_JOURNAL_RESTORE_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def apply_snapshot_to_config(cfg: PreviewConfigProtocol, snapshot: PreviewSnapshot) -> bool:
    """Restore one validated snapshot onto ``cfg``.

    Every field is attempted (best effort), but the return value reports
    whether *all* assignments succeeded.  Callers must retain the journal on
    ``False`` so a later launch can retry.
    """

    values: tuple[tuple[str, object], ...] = (
        ("per_key_colors", dict(snapshot.per_key_colors)),
        ("color", snapshot.color),
        ("speed", snapshot.speed),
        ("brightness", snapshot.brightness),
        ("effect", snapshot.effect),
    )
    failed: list[str] = []
    for key, value in values:
        try:
            setattr(cfg, key, value)
        except _JOURNAL_RESTORE_ERRORS as exc:
            logger.debug("calibrator preview journal: failed to restore %s", key, exc_info=exc)
            failed.append(key)
    if failed:
        logger.warning(
            "calibrator preview journal: partial restore (failed: %s); journal retained for retry",
            ", ".join(failed),
        )
        return False
    return True


def recover_stale_preview_journal(cfg: PreviewConfigProtocol) -> bool:
    """Restore a stale journal left by a crashed calibrator session.

    Returns ``True`` only when a valid journal was found and *fully*
    restored (deterministic automatic recovery with a logged diagnostic),
    after which the journal is removed.  Returns ``False`` when there was no
    journal, when it was corrupt/unusable (logged and discarded without
    changing config), or when the restore only partially succeeded (logged
    and the journal retained for retry).  Never raises and never blocks
    calibration.
    """

    from keyrgb.core.profile.json_storage import read_json_strict

    config_dir = config_dir_of(cfg)
    if config_dir is None:
        return False
    path = journal_path(config_dir)
    if not path.exists():
        return False
    try:
        payload = read_json_strict(path)
    except _JOURNAL_READ_ERRORS as exc:
        logger.warning("calibrator preview journal %s is unreadable; discarding it: %s", path, exc)
        clear_preview_journal(config_dir)
        return False
    snapshot = validate_journal_payload(payload)
    if snapshot is None:
        logger.warning(
            "calibrator preview journal %s failed schema validation; discarding it without changing config",
            path,
        )
        clear_preview_journal(config_dir)
        return False
    if not apply_snapshot_to_config(cfg, snapshot):
        return False
    if not clear_preview_journal(config_dir):
        logger.warning("calibrator preview journal %s was restored but could not be removed", path)
        return False
    logger.warning(
        "calibrator preview journal %s: previous session did not restore lighting; "
        "original effect/speed/brightness/color/per-key values were automatically restored",
        path,
    )
    return True
