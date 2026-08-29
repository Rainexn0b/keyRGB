from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

DIAGNOSTICS_BEFORE_NAME = "diagnostics-before.json"
DIAGNOSTICS_AFTER_NAME = "diagnostics-after.json"
JOURNAL_USER_NAME = "journal-user.log"
JOURNAL_KERNEL_NAME = "journal-kernel.log"
JOURNAL_COLLECTION_LINE_LIMIT = 2000
JOURNAL_COLLECTION_TIMEOUT_SECONDS = 30
_DIAGNOSTIC_SNAPSHOT_ERRORS = (OSError, RuntimeError, ValueError, TypeError, AttributeError, ImportError)


def _write_diagnostics_snapshot(target_path: Path, *, when: str) -> None:
    """Write a best-effort diagnostics snapshot; record a note on failure."""

    try:
        from keyrgb.core.diagnostics import collect_diagnostics

        # The canonical hardware diagnostic bundle always enumerates USB so
        # support has the full device picture.
        diag = collect_diagnostics(include_usb=True)
        target_path.write_text(
            json.dumps(diag.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except _DIAGNOSTIC_SNAPSHOT_ERRORS as exc:
        target_path.write_text(
            f"diagnostics snapshot ({when}) unavailable: {exc}\n",
            encoding="utf-8",
        )


def _collect_journal_log(target_path: Path, *, since: str, cmd: Sequence[str]) -> int | None:
    """Collect a journal slice into ``target_path``; write a readable note on failure.

    Read-only and bounded: ``--no-pager`` plus a line cap and a hard timeout.
    Returns the journalctl exit status (or ``None`` when unavailable).
    """

    try:
        with target_path.open("w", encoding="utf-8", errors="replace") as log_file:
            proc = subprocess.run(
                list(cmd),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
                timeout=JOURNAL_COLLECTION_TIMEOUT_SECONDS,
            )
    except FileNotFoundError:
        target_path.write_text(
            "journalctl is not available on this system; journal logs were not collected.\n",
            encoding="utf-8",
        )
        return None
    except (OSError, subprocess.TimeoutExpired) as exc:
        target_path.write_text(
            f"Journal log collection failed or timed out: {exc}\n",
            encoding="utf-8",
        )
        return None

    if proc.returncode != 0:
        with target_path.open("a", encoding="utf-8", errors="replace") as log_file:
            log_file.write(
                f"\n[journalctl exited with status {proc.returncode}; output may be partial]\n"
            )
    return proc.returncode


__all__ = [
    "DIAGNOSTICS_AFTER_NAME",
    "DIAGNOSTICS_BEFORE_NAME",
    "JOURNAL_COLLECTION_LINE_LIMIT",
    "JOURNAL_COLLECTION_TIMEOUT_SECONDS",
    "JOURNAL_KERNEL_NAME",
    "JOURNAL_USER_NAME",
    "_collect_journal_log",
    "_write_diagnostics_snapshot",
]
