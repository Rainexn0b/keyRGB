from __future__ import annotations

import logging
from dataclasses import dataclass

from keyrgb.core.config import Config
from keyrgb.core.utils.logging_utils import log_throttled

logger = logging.getLogger(__name__)
_PREVIEW_SNAPSHOT_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_PREVIEW_RESTORE_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _full_black_map(*, rows: int, cols: int) -> dict[tuple[int, int], tuple[int, int, int]]:
    return {(r, c): (0, 0, 0) for r in range(rows) for c in range(cols)}


@dataclass
class KeyboardPreviewSession:
    """Manages temporary config changes while calibrating.

    The calibrator flashes a single matrix cell (white) using per-key mode.
    This session snapshots the original config values and restores them on exit.
    """

    cfg: Config
    rows: int
    cols: int

    def __post_init__(self) -> None:
        self._orig_effect = getattr(self.cfg, "effect", "rainbow")
        self._orig_speed = getattr(self.cfg, "speed", 5)
        self._orig_brightness = getattr(self.cfg, "brightness", 25)
        self._orig_color = tuple(getattr(self.cfg, "color", (255, 0, 0)) or (255, 0, 0))
        try:
            self._orig_per_key_colors = dict(getattr(self.cfg, "per_key_colors", {}) or {})
        except _PREVIEW_SNAPSHOT_ERRORS as exc:
            log_throttled(
                logger,
                "calibrator.preview.orig_per_key_colors",
                interval_s=120,
                level=logging.DEBUG,
                msg="Failed to snapshot per_key_colors; will restore empty map",
                exc=exc,
            )
            self._orig_per_key_colors = {}
        # Crash recovery: the journal records these originals before the
        # first preview mutation and is removed on orderly restore.  A stale
        # journal is recovered by the app before this session is created.
        self._journal_recorded = False
        self._adopt_retained_journal()

    def _adopt_retained_journal(self) -> None:
        """Keep a prior session's true originals after partial recovery."""

        from keyrgb.gui.calibrator import guided as preview_journal

        config_dir = preview_journal.config_dir_of(self.cfg)
        if config_dir is None:
            return
        snapshot = preview_journal.load_preview_snapshot(config_dir)
        if snapshot is None:
            return
        self._orig_effect = snapshot.effect
        self._orig_speed = snapshot.speed
        self._orig_brightness = snapshot.brightness
        self._orig_color = snapshot.color
        self._orig_per_key_colors = dict(snapshot.per_key_colors)
        self._journal_recorded = True

    def _record_preview_journal(self) -> None:
        # Imported lazily: this helper loads during calibrator package init,
        # so a top-level import would race the partially initialized package.
        from keyrgb.gui.calibrator import guided as preview_journal

        config_dir = preview_journal.config_dir_of(self.cfg)
        if config_dir is None:
            return
        if preview_journal.write_preview_journal(config_dir, preview_journal.snapshot_preview_state(self.cfg)):
            self._journal_recorded = True

    def apply_probe_cell(self, row: int, col: int) -> None:
        if not self._journal_recorded:
            self._record_preview_journal()
        colors = _full_black_map(rows=self.rows, cols=self.cols)
        colors[(row, col)] = (255, 255, 255)

        if getattr(self.cfg, "brightness", 0) <= 0:
            self.cfg.brightness = 50
        self.cfg.per_key_colors = colors

    def restore(self) -> bool:
        """Restore the snapshotted originals; report full success.

        Every field is attempted (best effort, order preserved), but the
        crash journal is cleared only when *all* assignments succeed.  On a
        partial restore the journal is retained so a later launch can retry,
        and ``False`` is returned with a logged warning.
        """

        restored_ok = True
        for key, value in (
            ("per_key_colors", self._orig_per_key_colors),
            ("color", self._orig_color),
            ("speed", int(self._orig_speed)),
            ("brightness", int(self._orig_brightness)),
            ("effect", str(self._orig_effect)),
        ):
            try:
                setattr(self.cfg, key, value)
            except _PREVIEW_RESTORE_ERRORS as exc:
                restored_ok = False
                log_throttled(
                    logger,
                    f"calibrator.preview.restore.{key}",
                    interval_s=120,
                    level=logging.DEBUG,
                    msg=f"Failed to restore config field: {key}",
                    exc=exc,
                )
        if not restored_ok:
            logger.warning(
                "calibrator preview restore partially failed; crash journal retained for retry",
            )
            return False
        # Lazily imported (see _record_preview_journal): this helper loads
        # during calibrator package init.
        from keyrgb.gui.calibrator import guided as preview_journal

        config_dir = preview_journal.config_dir_of(self.cfg)
        if config_dir is not None and not preview_journal.clear_preview_journal(config_dir):
            logger.warning("calibrator preview restore succeeded but its crash journal could not be removed")
            return False
        self._journal_recorded = False
        return True
