"""UX-04 guided setup integration: temp guided session I/O (Tk-free).

Temp session helpers reuse the guided session schema: atomically creating a
temp session file from the draft, reading/validating a finished calibrator
result (no profile/config I/O), adopting it into the controller draft, and
cleaning the temp file up. Only the narrow ``OSError``/``RuntimeError``/
``TypeError``/``ValueError``/``AttributeError`` boundary is caught;
unexpected exceptions propagate.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from ..model import SetupDraft
from .integration_types import _EXPECTED_SESSION_ERRORS, _SESSION_FILE_NAME, _SESSION_TMP_PREFIX

if TYPE_CHECKING:
    from .integration_controller import GuidedSetupController

logger = logging.getLogger(__name__)


def _guided_result_version() -> int:
    from keyrgb.gui.calibrator.guided import GUIDED_SESSION_RESULT_VERSION

    return int(GUIDED_SESSION_RESULT_VERSION)


def create_guided_session_file(
    draft: SetupDraft,
    *,
    rows: int,
    cols: int,
    directory: str | Path | None = None,
) -> Path:
    """Atomically create a temp guided session file from the draft.

    Payload follows the guided session schema (global overlay tweaks seed
    the session; per-key payloads ride along verbatim). Touches no
    profiles or config.
    """

    payload: dict[str, object] = {
        "dimensions": [rows, cols],
        "physical_layout": draft.physical_layout or "auto",
        "legend_pack": draft.legend_pack or "auto",
        "slot_overrides": copy.deepcopy(dict(draft.slot_overrides)),
        "keymap": copy.deepcopy(dict(draft.keymap)),
        "layout_tweaks": dict(draft.layout_tweaks),
        "per_key_layout_tweaks": copy.deepcopy(dict(draft.per_key_layout_tweaks)),
    }
    try:
        serialized = json.dumps(payload, indent=2, sort_keys=True, default=list) + "\n"
    except (TypeError, ValueError) as exc:
        raise ValueError(f"guided setup session is not JSON serializable: {exc}") from exc
    try:
        parent = Path(directory) if directory is not None else Path(tempfile.mkdtemp(prefix=_SESSION_TMP_PREFIX))
        parent.mkdir(parents=True, exist_ok=True)
        session_path = parent / _SESSION_FILE_NAME
        tmp_fd, tmp_name = tempfile.mkstemp(prefix=f".{_SESSION_FILE_NAME}.", suffix=".tmp", dir=str(parent))
        tmp_path = Path(tmp_name)
        fd_open = True
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
                fd_open = False
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, session_path)
        finally:
            if fd_open:
                try:
                    os.close(tmp_fd)
                except OSError:
                    logger.debug("guided setup session: failed to close temp file", exc_info=True)
            try:
                tmp_path.unlink()
            except OSError:
                pass
    except _EXPECTED_SESSION_ERRORS as exc:
        raise ValueError(f"guided setup session cannot be created: {exc}") from exc
    return session_path


def read_guided_result(
    session_path: str | Path,
    *,
    rows: int,
    cols: int,
    expected_layout: str | None = None,
) -> dict[str, tuple[tuple[int, int], ...]]:
    """Read/validate a guided calibrator result (no profile/config I/O).

    Validates version and layout, normalizes via the public ``profiles``
    APIs, and sanitizes cells to ``rows``/``cols``. Raises ``ValueError``
    (``TypeError`` for wrong-type payloads) on structural problems.
    """

    from keyrgb.core.profile import profiles
    from keyrgb.gui.perkey import profile_management

    path = Path(session_path).expanduser()
    try:
        raw_text = path.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        raise ValueError(f"guided setup result cannot be read: {exc}") from exc
    try:
        payload = json.loads(raw_text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"guided setup result is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise TypeError("guided setup result top-level JSON must be an object")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise TypeError("guided setup session has no calibrator result yet")
    try:
        version = result.get("version")
        result_layout = result.get("physical_layout")
        keymap_raw = result.get("keymap")
    except _EXPECTED_SESSION_ERRORS as exc:
        raise ValueError(f"guided setup result is malformed: {exc}") from exc
    if version != _guided_result_version():
        raise ValueError(f"guided setup result has an unsupported version: {version!r}")
    if expected_layout and str(expected_layout).strip().lower() not in ("", "auto"):
        expected = str(expected_layout).strip().lower()
        actual = str(result_layout).strip().lower() if isinstance(result_layout, str) else ""
        if actual != expected:
            raise ValueError(f"guided setup result layout {actual!r} does not match {expected!r}")
    if not isinstance(keymap_raw, Mapping):
        raise TypeError("guided setup result keymap must be an object")
    layout_for_normalize = expected_layout or (str(result_layout) if isinstance(result_layout, str) else "auto")
    try:
        normalized = profiles.normalize_keymap(dict(keymap_raw), physical_layout=layout_for_normalize)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"guided setup result keymap is invalid: {exc}") from exc
    try:
        sanitized = profile_management.sanitize_keymap_cells(normalized, num_rows=rows, num_cols=cols)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"guided setup result keymap is invalid: {exc}") from exc
    if not sanitized:
        raise ValueError("guided setup result keymap has no usable cells")
    return dict(sanitized)


def adopt_guided_result(
    controller: GuidedSetupController,
    session_path: str | Path | None = None,
) -> tuple[bool, str]:
    """Adopt a finished calibrator result into the draft (Tk-free).

    Validates the temp session ``result``, stores it via
    ``draft.set_keymap``, clears the child flag, and always cleans the
    temp file. Returns ``(adopted, message)``; failures keep the previous
    keymap for retry. Never touches profiles or config.
    """

    path = session_path if session_path is not None else controller.session_path
    if path is None:
        controller.note_child_finished()
        return False, "Guided calibrator closed without a session file."
    try:
        adopted = read_guided_result(
            path,
            rows=controller.rows,
            cols=controller.cols,
            expected_layout=controller.draft.physical_layout,
        )
    except _EXPECTED_SESSION_ERRORS as exc:
        controller.note_child_finished()
        cleanup_guided_session(path)
        return False, f"Guided calibrator closed without a usable result: {exc}"
    try:
        controller.draft.set_keymap(dict(adopted))
    except (TypeError, ValueError) as exc:
        controller.note_child_finished()
        cleanup_guided_session(path)
        return False, f"Guided calibrator result was rejected: {exc}"
    controller.note_child_finished()
    cleanup_guided_session(path)
    return True, "Guided calibrator result adopted."


def cleanup_guided_session(session_path: str | Path | None) -> None:
    """Remove a temporary guided session file (and its temp dir if ours)."""

    if session_path is None:
        return
    try:
        path = Path(session_path).expanduser()
    except _EXPECTED_SESSION_ERRORS:
        return
    try:
        path.unlink(missing_ok=True)
    except _EXPECTED_SESSION_ERRORS:
        return
    try:
        parent = path.parent
        if parent.name.startswith(_SESSION_TMP_PREFIX.rstrip("-")[: len("keyrgb-guided")]):
            parent.rmdir()
    except _EXPECTED_SESSION_ERRORS:
        pass
